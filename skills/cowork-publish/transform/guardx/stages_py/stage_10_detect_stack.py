"""stage 10: 探测技术栈，输出 stack.json。

历史上有 bash 版 stages/10_detect_stack.sh + lib/stack_detect.sh，已被本 Python 实现完全取代并删除。

输出 JSON 字段（stages/20-70.sh 仍以下列顺序消费）：
    lang / framework / entry / needs_build /
    has_db / has_ai / has_ai_text / has_ai_image /
    has_redis / has_external_infra / has_sso / has_static_spa /
    backend_dir / frontend_dir

注：has_redis 字段保留向后兼容；新代码请使用 has_external_infra（覆盖
Redis/MQ/S3/ES）。Pod 不提供这些外部基础设施，命中即触发 stage 20 子任务。

注：has_ai 字段保留向后兼容；新代码请使用 has_ai_text / has_ai_image 分别判断。
has_ai_text=1 触发 stage 20 的 rewrite_ai_calls 子任务（文本对话迁 Runway Bedrock）。
has_ai_image=1 触发 stage 20 的 rewrite_image_calls 子任务（图像生成迁 Runway Google GenerateContent）。

注意：阶段 4 引入 profiles/*.json 后，框架识别规则（now hardcoded）会迁出去
到 profile 的 `detect` 字段，本文件只保留 monorepo 探测 + 信号扫描骨架。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from .. import config, llm, log, profile

# detect_rules.json 提供数据驱动的 signal 关键词；缺文件时 fallback 到内置 _DEFAULT_RULES
_DEFAULT_RULES: dict[str, list[str]] = {
    "db_keywords": [
        "psycopg", "sqlalchemy", '"pg"', "sequelize", "prisma",
        "mongoose", "sqlite3", "mysql", "asyncpg",
    ],
    "ai_keywords": [
        "openai", "anthropic", "@anthropic-ai", "google-generativeai",
        "@google/generative-ai", "zhipuai", "dashscope", "langchain",
    ],
    "ai_text_keywords": [
        "openai", "anthropic", "@anthropic-ai/sdk", "google-generativeai",
        "@google/generative-ai", "zhipuai", "langchain",
        "langchain-openai", "langchain-anthropic",
        "@langchain/openai", "@langchain/anthropic",
        "bedrock_runtime", "anthropic_version",
    ],
    "ai_image_keywords": [
        # 图像专用 SDK / 厂商关键词（避免 openai/dashscope/zhipuai 等多用途包导致误判）
        "dall-e", "dalle", "stability_sdk", "stability-sdk",
        "@google/genai", "google-genai",
        "nova-canvas", "nova_canvas", "midjourney", "wanx",
        # 图像专用方法名
        "ImageSynthesis", r"images\.create", r"images\.generate", r"images\.edit",
        # 通用图像关键词 / 已转写后的关键词
        "image-synthesis", "text-to-image", "image_generation", "imagegeneration",
        "responseModalities", "inlineData",
        r"ai\.image_base_url", r"ai\.image_api_key",
    ],
    "redis_keywords": [
        '"(ioredis|redis|node-redis|bullmq)"',
        "^(redis|aioredis|celery|hotqueue|rq)([><=!~ ]|$)",
    ],
    "mq_keywords": [
        '"(amqplib|amqp-connection-manager|rhea|kafkajs|@nestjs/microservices|nats|node-rdkafka|@confluentinc/kafka-javascript)"',
        "^(pika|kombu|aio-pika|aiokafka|confluent-kafka|nats-py|stomp\\.py)([><=!~ ]|$)",
    ],
    "s3_keywords": [
        '"(@aws-sdk/client-s3|aws-sdk|minio|@minio/minio|@google-cloud/storage|cos-nodejs-sdk-v5|ali-oss)"',
        "^(boto3|aioboto3|minio|google-cloud-storage|cos-python-sdk-v5|oss2)([><=!~ ]|$)",
    ],
    "es_keywords": [
        '"(@elastic/elasticsearch|@opensearch-project/opensearch|@meilisearch/meilisearch|meilisearch|typesense)"',
        "^(elasticsearch|opensearch-py|meilisearch|typesense)([><=!~ ]|$)",
    ],
    "sso_dep_keywords": [
        '"(passport|passport-[a-z-]+|next-auth|@auth/.*|@nextauth/.*|express-session|cookie-session|@auth0/.*|firebase-auth)"',
        "^(flask-login|flask-jwt|flask-jwt-extended|authlib|django-allauth|python-jose|pyjwt|fastapi-users)([><=!~ ]|$)",
    ],
    "sso_code_keywords": [
        "Decrypted-Userinfo",
        "x-decrypted-userinfo",
    ],
    "docker_db_image_keywords": [r"image:\s*(postgres|mysql|mariadb|mongo)"],
    "docker_redis_image_keywords": [r"image:\s*redis"],
    "docker_external_infra_image_keywords": [
        r"image:\s*(redis|valkey|memcached|rabbitmq|kafka|cp-kafka|cp-zookeeper|nats|activemq|minio|localstack|elasticsearch|opensearch|meilisearch|typesense)",
    ],
}


def _load_rules(home: Path) -> dict[str, list[str]]:
    """从 detect_rules.json 读 signal 关键词；缺文件用内置默认。"""
    rules_file = home / "detect_rules.json"
    if not rules_file.is_file():
        return _DEFAULT_RULES
    try:
        data = json.loads(rules_file.read_text())
        # 用文件覆盖默认（仅取已知 key，忽略 _doc 等元字段）
        return {k: data.get(k, _DEFAULT_RULES[k]) for k in _DEFAULT_RULES}
    except (OSError, json.JSONDecodeError) as e:
        log.warn(f"detect_rules.json 解析失败，回退默认: {e}")
        return _DEFAULT_RULES


def _compile_or(keywords: list[str], multiline: bool = False) -> re.Pattern[str]:
    """把关键词列表 OR 拼成一个正则。"""
    pattern = "|".join(f"(?:{k})" for k in keywords)
    return re.compile(pattern, re.MULTILINE if multiline else 0)

# ---- 框架探测：候选目录 ----
_BACKEND_CANDIDATES = (
    "backend", "server", "api", "app", "src",
    "apps/api", "apps/server", "apps/backend",
    "packages/api", "packages/server", "packages/backend",
    "services/api", "services/server", "services/backend",
)

_FRONTEND_CANDIDATES = (
    "frontend", "web", "ui", "client",
    "apps/web", "apps/frontend", "apps/ui", "apps/client",
    "packages/web", "packages/frontend", "packages/ui", "packages/client",
)

# ---- 入口候选 ----
_ENTRY_CANDIDATES_PY = (
    "main.py", "app.py", "app/main.py", "backend/main.py", "src/main.py",
)
_ENTRY_CANDIDATES_NODE = (
    "server.js", "src/server.ts", "dist/server.js",
    "index.js", "src/main.ts", "dist/main.js",
)

# 框架结构性 regex（不参与数据化抽取，跟代码强耦合）
_RE_NEXT_STANDALONE = re.compile(r"""output:\s*['"]standalone['"]""")


_BACKEND_FRAMEWORKS = {"fastapi", "flask", "django", "node-backend", "python-other"}
_FRONTEND_FRAMEWORKS = {"nextjs", "nextjs-standalone", "nuxt", "vite-spa", "node-other"}
_SPA_FRAMEWORKS = {"vite-spa", "nextjs", "nuxt"}


class _DetectResult:
    __slots__ = ("lang", "framework", "needs_build", "entry")

    def __init__(self) -> None:
        self.lang: str = "unknown"
        self.framework: str = "unknown"
        self.needs_build: int = 0
        self.entry: str = ""


def _read_text_safe(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except OSError:
        return ""


def _grep_py_imports_fastapi(d: Path) -> bool:
    """递归找 *.py 文件中 'from fastapi' 导入。等价 bash 版 grep -qrE。"""
    for f in d.rglob("*.py"):
        # 跳过虚拟环境等
        if any(part in {"node_modules", ".venv", "venv", "__pycache__"} for part in f.parts):
            continue
        text = _read_text_safe(f)
        for line in text.splitlines():
            if line.startswith("from fastapi"):
                return True
        # 性能保护：单文件最多扫前若干行（rglob 已经全扫，文件级早返回）
    return False


def _detect_in_dir(d: Path) -> _DetectResult:
    """在指定目录探测语言/框架。逻辑对齐 bash 版 _detect_in_dir。"""
    r = _DetectResult()
    if not d.is_dir():
        return r

    pkg = d / "package.json"
    req = d / "requirements.txt"
    pyproj = d / "pyproject.toml"
    pipfile = d / "Pipfile"
    cargo = d / "Cargo.toml"
    gomod = d / "go.mod"

    # 语言
    if pkg.is_file():
        r.lang = "node"
    elif req.is_file() or pyproj.is_file() or pipfile.is_file():
        r.lang = "python"
    elif cargo.is_file():
        r.lang = "rust"
    elif gomod.is_file():
        r.lang = "go"

    # 框架
    if r.lang == "node":
        pkg_text = _read_text_safe(pkg)
        if '"next"' in pkg_text:
            r.framework, r.needs_build = "nextjs", 1
            # 检查 next.config.* 是否 standalone
            for conf in d.glob("next.config.*"):
                if _RE_NEXT_STANDALONE.search(_read_text_safe(conf)):
                    r.framework = "nextjs-standalone"
                    break
        elif '"nuxt"' in pkg_text:
            r.framework, r.needs_build = "nuxt", 1
        elif '"vite"' in pkg_text:
            r.framework, r.needs_build = "vite-spa", 1
        elif re.search(r'"(express|@nestjs/core|koa|fastify)"', pkg_text):
            r.framework = "node-backend"
            if '"build"' in pkg_text:
                r.needs_build = 1
        else:
            r.framework = "node-other"
    elif r.lang == "python":
        req_text = _read_text_safe(req).lower() if req.is_file() else ""
        if re.search(r"^fastapi", req_text, re.MULTILINE) or _grep_py_imports_fastapi(d):
            r.framework = "fastapi"
        elif re.search(r"^flask", req_text, re.MULTILINE):
            r.framework = "flask"
        elif re.search(r"^django", req_text, re.MULTILINE):
            r.framework = "django"
        else:
            r.framework = "python-other"

    # 入口推断
    if r.framework in ("fastapi", "flask"):
        for cand in _ENTRY_CANDIDATES_PY:
            if (d / cand).is_file():
                r.entry = cand
                break
    elif r.framework == "nextjs-standalone":
        r.entry = ".next/standalone/server.js"
    elif r.framework == "nextjs":
        r.entry = "(use next start)"
    elif r.framework == "node-backend":
        for cand in _ENTRY_CANDIDATES_NODE:
            if (d / cand).is_file():
                r.entry = cand
                break
    elif r.framework == "vite-spa":
        r.entry = "(static dist/, served by sibling backend or serve)"

    return r


def _detect_stack(work_dir: Path) -> dict:
    has_db = 0
    has_ai = 0
    has_ai_text = 0
    has_ai_image = 0
    has_redis = 0
    has_mq = 0
    has_s3 = 0
    has_es = 0
    has_sso = 0
    has_static_spa = 0
    backend_dir = ""
    frontend_dir = ""

    top = _detect_in_dir(work_dir)
    lang = top.lang
    framework = top.framework
    needs_build = top.needs_build
    entry = top.entry

    # ---- monorepo backend 探测 ----
    if lang == "unknown":
        # 第一轮：找 backend framework 命中
        for cand in _BACKEND_CANDIDATES:
            sub = work_dir / cand
            if not sub.is_dir():
                continue
            r = _detect_in_dir(sub)
            if r.framework in _BACKEND_FRAMEWORKS or r.lang != "unknown":
                backend_dir = cand
                lang, framework, needs_build = r.lang, r.framework, r.needs_build
                if r.entry:
                    entry = f"{cand}/{r.entry}"
                break

        # 第二轮：任何识别到 lang 的子目录都当 backend
        if lang == "unknown":
            for cand in _BACKEND_CANDIDATES:
                sub = work_dir / cand
                if not sub.is_dir():
                    continue
                r = _detect_in_dir(sub)
                if r.lang != "unknown":
                    backend_dir = cand
                    lang, framework, needs_build = r.lang, r.framework, r.needs_build
                    if r.entry:
                        entry = f"{cand}/{r.entry}"
                    break

    # ---- 前端目录探测（独立，用于 has_static_spa）----
    for fcand in _FRONTEND_CANDIDATES:
        sub = work_dir / fcand
        if not sub.is_dir():
            continue
        r = _detect_in_dir(sub)
        if r.framework in _FRONTEND_FRAMEWORKS or r.lang == "node":
            frontend_dir = fcand
            if r.framework in _SPA_FRAMEWORKS:
                has_static_spa = 1
            # 顶层 + backend 都没探到 lang，前端框架顶上
            if lang == "unknown":
                lang, framework, needs_build = r.lang, r.framework, r.needs_build
                if r.entry:
                    entry = f"{fcand}/{r.entry}"
            break

    # ---- DB / AI / Redis 信号 ----
    search_files: list[Path] = []
    for cand in (
        work_dir / "package.json",
        work_dir / "requirements.txt",
        work_dir / backend_dir / "package.json" if backend_dir else None,
        work_dir / backend_dir / "requirements.txt" if backend_dir else None,
        work_dir / frontend_dir / "package.json" if frontend_dir else None,
    ):
        if cand is not None and cand.is_file():
            search_files.append(cand)

    rules = _load_rules(config.home_dir())
    re_db = _compile_or(rules["db_keywords"])
    re_ai = _compile_or(rules["ai_keywords"])
    re_ai_text = _compile_or(rules.get("ai_text_keywords", []) or rules["ai_keywords"])
    re_ai_image = _compile_or(rules.get("ai_image_keywords", []) or ["(?!x)x"])
    re_redis = _compile_or(rules["redis_keywords"], multiline=True)
    re_mq = _compile_or(rules.get("mq_keywords", []) or ["(?!x)x"], multiline=True)
    re_s3 = _compile_or(rules.get("s3_keywords", []) or ["(?!x)x"], multiline=True)
    re_es = _compile_or(rules.get("es_keywords", []) or ["(?!x)x"], multiline=True)
    re_sso_dep = _compile_or(
        rules.get("sso_dep_keywords", []) or ["(?!x)x"], multiline=True
    )
    re_sso_code = _compile_or(rules.get("sso_code_keywords", []) or ["(?!x)x"])
    re_dc_db = _compile_or(rules["docker_db_image_keywords"])
    re_dc_redis = _compile_or(rules["docker_redis_image_keywords"])
    re_dc_infra = _compile_or(
        rules.get("docker_external_infra_image_keywords", [])
        or rules["docker_redis_image_keywords"]
    )

    if search_files:
        combined = "\n".join(_read_text_safe(p) for p in search_files)
        if re_db.search(combined):
            has_db = 1
        if re_ai.search(combined):
            has_ai = 1
        if re_ai_text.search(combined):
            has_ai_text = 1
        if re_ai_image.search(combined):
            has_ai_image = 1
        if re_redis.search(combined):
            has_redis = 1
        if re_mq.search(combined):
            has_mq = 1
        if re_s3.search(combined):
            has_s3 = 1
        if re_es.search(combined):
            has_es = 1
        if re_sso_dep.search(combined):
            has_sso = 1

    # docker-compose.yml 也是强信号
    for compose_name in ("docker-compose.yml", "docker-compose.yaml"):
        compose = work_dir / compose_name
        if compose.is_file():
            text = _read_text_safe(compose)
            if re_dc_db.search(text):
                has_db = 1
            if re_dc_redis.search(text):
                has_redis = 1
            if re_dc_infra.search(text):
                # docker-compose 里出现外部基础设施 image，统一 mark 为 external_infra
                # 不细分到 has_mq/s3/es（image 名字不一定能精确归类），由
                # has_external_infra 兜住即可
                pass  # 单独累加在 has_external_infra 计算里

    # ---- has_sso：扫源码里 SSO 语义信号 ----
    # 三类信号（任一命中即为 1）：
    #   1. 已接入 Decrypted-Userinfo header（平台 SSO 标准接入方式）
    #   2. 后端有获取当前用户的 API 路由/函数（如 /api/me、getCurrentUser、req.user）
    #      ——即使当前用 mock 实现，也说明业务需要 SSO，转写时必须接入
    #   3. 前端有展示当前用户信息的 hook/组件/store（如 useUser、userStore、user.name）
    #      ——即使当前用 mock 数据，也说明前端依赖用户身份，转写时必须接入
    if not has_sso:
        scan_roots = [work_dir]
        # 限制只扫常见业务目录，避免全仓 rglob 太慢
        for sub in ("src", "app", "apps", "backend", "api", "server",
                    "pages", "routes", "lib", "middleware", "middlewares",
                    "hooks", "store", "stores", "context", "contexts",
                    "components", "views"):
            p = work_dir / sub
            if p.is_dir():
                scan_roots.append(p)
        SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
        SKIP_PARTS = {
            "node_modules", ".next", "dist", "build", ".git",
            ".venv", "venv", "__pycache__", ".guard-transform",
        }
        # 扫描时设上限，避免巨型仓库阻塞
        scanned = 0
        SCAN_LIMIT = 2000
        for root in scan_roots:
            if has_sso:
                break
            for f in root.rglob("*"):
                if scanned >= SCAN_LIMIT:
                    break
                if not f.is_file() or f.suffix not in SOURCE_EXT:
                    continue
                if any(part in SKIP_PARTS for part in f.parts):
                    continue
                scanned += 1
                if re_sso_code.search(_read_text_safe(f)):
                    has_sso = 1
                    break

    # ---- has_external_infra：redis/mq/s3/es 任一命中即为 1 ----
    has_external_infra = 1 if (has_redis or has_mq or has_s3 or has_es) else 0
    # docker-compose 里命中外部基础设施 image 也算
    if not has_external_infra:
        for compose_name in ("docker-compose.yml", "docker-compose.yaml"):
            compose = work_dir / compose_name
            if compose.is_file() and re_dc_infra.search(_read_text_safe(compose)):
                has_external_infra = 1
                break

    # 字段顺序：保留 has_redis / has_ai 在原位向后兼容；新增字段追加在后面
    return {
        "lang": lang,
        "framework": framework,
        "entry": entry,
        "needs_build": needs_build,
        "has_db": has_db,
        "has_ai": has_ai,
        "has_ai_text": has_ai_text,
        "has_ai_image": has_ai_image,
        "has_redis": has_redis,
        "has_mq": has_mq,
        "has_s3": has_s3,
        "has_es": has_es,
        "has_external_infra": has_external_infra,
        "has_sso": has_sso,
        "has_static_spa": has_static_spa,
        "backend_dir": backend_dir,
        "frontend_dir": frontend_dir,
    }


def _llm_generate_brief(cfg: "config.Config", stack: dict) -> None:
    """调 LLM 读源码生成 project_brief.md，并把补全的 flag merge 回 stack.json。

    - 受 GUARD_DETECT_LLM=0 控制（默认开启）
    - 用 fast profile（sonnet），只读文件不改代码
    - 大仓 + thinking 模型可能需要数百秒，超时默认调高到至少 1800s
      （可用 GUARD_DETECT_TIMEOUT 单独覆盖，优先级高于 GUARD_LLM_TIMEOUT）
    - brief 落盘到 state_dir/project_brief.md，供后续所有 LLM 调用拼入 prompt
    - brief 里的 has_* flag 只允许 0→1（不允许 1→0），merge 回 stack.json
    """
    if os.environ.get("GUARD_DETECT_LLM", "1") == "0":
        log.log("GUARD_DETECT_LLM=0，跳过 LLM 辅助检测（project_brief.md 不生成）")
        return

    home = config.home_dir()
    brief_prompt = home / "prompts" / "10_project_brief.md"
    if not brief_prompt.is_file():
        log.warn("prompts/10_project_brief.md 不存在，跳过 LLM 辅助检测")
        return

    # detect 子任务（读全仓源码 → 生成 brief）远比单文件改写耗时；
    # 默认超时调高到至少 1800s，避免大仓 + thinking 模型被 600s 默认值打断。
    # 优先级：GUARD_DETECT_TIMEOUT > max(GUARD_LLM_TIMEOUT, 1800) > 1800
    _env_detect = os.environ.get("GUARD_DETECT_TIMEOUT", "").strip()
    _env_global = int(os.environ.get("GUARD_LLM_TIMEOUT", "600") or "600")
    if _env_detect.isdigit() and int(_env_detect) > 0:
        detect_timeout = int(_env_detect)
    else:
        detect_timeout = max(_env_global, 1800)

    log.log(
        "调 LLM 读源码生成 project_brief.md（GUARD_DETECT_LLM=0 可跳过）；"
        f"detect 子任务超时已调高到 {detect_timeout}s（GUARD_DETECT_TIMEOUT 可覆盖）..."
    )
    llm_cfg = llm.LLMConfig.for_profile("fast", timeout=detect_timeout)
    result = llm.call(
        brief_prompt,
        cfg.work_dir,
        cfg.state_dir,
        cfg=llm_cfg,
        log_label="10:project_brief",
    )
    if not result.ok:
        log.warn("LLM 生成 project_brief.md 失败，继续（不影响后续 stage）")
        return

    # brief 落盘位置：LLM 写到 work_dir/project_brief.md，我们把它移到 state_dir
    # 同时在 work_dir 保留一份软链接，方便 LLM 在后续调用里直接 Read
    brief_in_work = cfg.work_dir / "project_brief.md"
    brief_in_state = cfg.state_dir / "project_brief.md"

    if brief_in_work.is_file():
        brief_in_state.write_text(brief_in_work.read_text())
        # work_dir 里的 brief 保留（后续 LLM 调用的 --dir 锁在 work_dir，
        # 需要能直接 Read project_brief.md）
        log.ok(f"project_brief.md 已生成：{brief_in_state}")
    else:
        log.warn("LLM 未在 work_dir 写出 project_brief.md，跳过 flag merge")
        return

    # ---- 从 brief 里解析 has_* flag，merge 回 stack.json（只允许 0→1）----
    brief_text = brief_in_state.read_text()
    flag_map = {
        "has_db": False,
        "has_ai": False,
        "has_ai_text": False,
        "has_ai_image": False,
        "has_sso": False,
        "has_external_infra": False,
    }
    for flag in flag_map:
        # 匹配 "- has_db：1" 或 "- has_db: 1"（冒号后可有空格）
        m = re.search(rf"[-*]\s*{flag}[：:]\s*([01])", brief_text)
        if m and m.group(1) == "1":
            flag_map[flag] = True

    out_path = cfg.state_dir / "stack.json"
    try:
        current = json.loads(out_path.read_text())
    except (OSError, json.JSONDecodeError):
        log.warn("stack.json 读取失败，跳过 flag merge")
        return

    updated = False
    for flag, llm_says_1 in flag_map.items():
        if llm_says_1 and not current.get(flag):
            log.log(f"  LLM 补全 flag: {flag} 0→1（shell 静态扫描漏掉）")
            current[flag] = 1
            updated = True
            # has_ai 联动：has_ai_text 或 has_ai_image 任一为 1 时也置 1
            if flag in ("has_ai_text", "has_ai_image"):
                current["has_ai"] = 1
            # has_external_infra 联动：redis/mq/s3/es 任一为 1 时也置 1
            if flag in ("has_redis", "has_mq", "has_s3", "has_es"):
                current["has_external_infra"] = 1

    if updated:
        out_path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
        log.log("stack.json 已更新（LLM 补全）：")
        for line in out_path.read_text().rstrip("\n").splitlines():
            log.log(f"    {line}")
    else:
        log.log("LLM 检测与 shell 扫描结果一致，stack.json 无需更新")


def run(cfg: config.Config) -> int:
    stack = _detect_stack(cfg.work_dir)

    out_path = cfg.state_dir / "stack.json"
    out_path.write_text(json.dumps(stack, indent=2, ensure_ascii=False) + "\n")

    log.log("栈检测结果（shell 静态扫描）：")
    # 缩进打印到 stderr，与 bash 版 sed 's/^/    /' 等价
    for line in out_path.read_text().rstrip("\n").splitlines():
        log.log(f"    {line}")

    # 输入不限语言；产物只能是 Python / Node
    # 非 Python/Node 原工程会在 stage 20 由 LLM 重写为 Python/Node 后端
    lang = stack["lang"]
    if lang in ("rust", "go", "java", "dotnet", "cpp", "c"):
        log.warn(
            f"检测到原工程语言为 {lang}，平台产物只支持 Python / Node。"
            "stage 20 的重写循环会把后端转写为 Python / Node 实现"
            "（参照 transform_prompt.md § 一）。"
        )
    elif lang == "unknown":
        log.warn("未识别到明确语言，后续 stage 可能需要手动干预")

    # 阶段 4：根据 stack 匹配 profile，落盘 STATE_DIR/profile.json
    home = config.home_dir()
    profile.detect_and_save(
        stack=stack,
        profiles_dir=home / "profiles",
        out_path=cfg.state_dir / "profile.json",
    )

    # ---- LLM 辅助检测：读源码生成 project_brief.md + 补全 stack.json flag ----
    # 在 profile 匹配之后跑，brief 里的 flag 补全不影响 profile 选择
    # （profile 已经落盘；stage 20 直接读 stack.json，brief 里的补全对 stage 20 生效）
    _llm_generate_brief(cfg, stack)

    log.ok("stage 10 完成")
    return 0
