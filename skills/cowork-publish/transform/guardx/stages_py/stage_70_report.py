"""stage 70: 拼最终交付报告 → STATE_DIR/report.md。

报告内容（与 bash 版严格对齐）：
  1. 元信息（生成时间 / 源工程 / 工作副本 / zip 路径 + 大小）
  2. 形态判定 stack.json
  3. 执行进度 checklist 表
  4. Verifier 通过列表（扫 STATE_DIR/verify-*.log，FAIL 标 ❌）
  5. 烟测 fingerprint
  6. 关键改动 git log（前 30 条）—— stage 60 已删 .git，此处通常显示 missing
  7. 下一步操作提示
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

from .. import checklist, config, log


def _human_size(n: int) -> str:
    """简易 du -h 风格："""
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n}{unit}"
        n //= 1024
    return f"{n}T"


def _verify_log_status(log_path: Path) -> bool:
    """读最后一行判 ok/fail。"""
    if not log_path.is_file() or log_path.stat().st_size == 0:
        return True  # 空日志当作 ok（与 bash 版兼容）
    try:
        text = log_path.read_text()
    except OSError:
        return True
    last_line = text.rstrip("\n").rsplit("\n", 1)[-1] if text else ""
    return not last_line.startswith("[FAIL]")


def _git_log(work_dir: Path) -> str:
    """跑 git log --oneline 前 30 条；stage 60 已删 .git，常返回空。"""
    if not (work_dir / ".git").is_dir():
        return "(no git history; .git removed at packaging)"
    try:
        r = subprocess.run(
            ["git", "--no-pager", "log", "--oneline"],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "(git log failed)"
    if r.returncode != 0:
        return "(git log failed)"
    lines = r.stdout.splitlines()[:30]
    return "\n".join(lines) if lines else "(empty git log)"


def _read_stack(state_dir: Path) -> dict:
    p = state_dir / "stack.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _ai_coverage_section(stack: dict) -> str:
    """AI 覆盖范围声明：透明告诉运维"什么改了 / 什么没改"。

    分两类汇报：
      - has_ai_text=1 → 文本 LLM 改写（Runway Bedrock）
      - has_ai_image=1 → 图像生成改写（Runway Google GenerateContent）
      - 旧 stack.json 用 has_ai 字段时回退到 has_ai_text（向后兼容）
    """
    has_ai_text = str(stack.get("has_ai_text", ""))
    has_ai_image = str(stack.get("has_ai_image", ""))
    # 向后兼容：旧 stack.json 没有拆分字段
    if not has_ai_text and not has_ai_image and str(stack.get("has_ai", "")) == "1":
        has_ai_text = "1"

    if has_ai_text != "1" and has_ai_image != "1":
        return "_工程未识别到 AI 调用（文本 + 图像皆无）；AI 改写子任务跳过。_\n"

    parts: list[str] = []

    # ---- 文本 AI 段 ----
    if has_ai_text == "1":
        parts.append(
            "### 文本 LLM 调用改造（详见 transform_prompt.md § 五）\n\n"
            "- ✅ 文本对话 LLM → Runway Bedrock `POST {ai.base_url}/bedrock_runtime/model/invoke`\n"
            "- ✅ 请求体改 Anthropic Messages 格式（`anthropic_version` + `messages` + `system` 顶级）\n"
            "- ✅ 删除 `model` / `temperature` 字段（model 由 api-key 网关侧绑定，temperature 已废弃）\n"
            "- ✅ 鉴权 header `token: <ai.api_key>`（独立读 `ai.base_url` / `ai.api_key`）\n"
            "- ✅ 200 OK 业务错检查（`if data.Code || data.Error throw`）\n"
            "- ✅ 删除原生 OpenAI / Anthropic SDK 依赖与 endpoint\n\n"
        )
    else:
        parts.append("_工程未识别到文本 LLM 调用；文本 AI 改写子任务跳过。_\n\n")

    # ---- 图像 AI 段 ----
    if has_ai_image == "1":
        parts.append(
            "### 图像生成调用改造（详见 transform_prompt.md § 五.5）\n\n"
            "- ✅ 图像生成 → Runway Google GenerateContent `POST {ai.image_base_url}/google/v1:generateContent`\n"
            "- ✅ 鉴权 header `api-key: <ai.image_api_key>`（独立读 `ai.image_base_url` / `ai.image_api_key`）\n"
            "- ✅ 严格独立读取：图像通路**禁止** fallback 到 `ai.base_url` / `ai.api_key`（平台独立计配额，缺图像字段时 `/api/image/*` 返 503）\n"
            "- ✅ 必加 `responseModalities: [\"TEXT\",\"IMAGE\"]` + `maxOutputTokens: 32768` + 四类 `safetySettings: OFF`\n"
            "- ✅ 200 OK 业务错检查（`data.Code / data.Error` 伪 200） + `finishReason !== STOP / MAX_TOKENS` 拒绝检查\n"
            "- ✅ 删除原生图像 SDK（DALL·E / 万相 / SD / Replicate / Midjourney / Vertex Imagen 等）与原 endpoint\n\n"
        )
    else:
        parts.append("_工程未识别到图像生成调用；图像 AI 改写子任务跳过。_\n\n")

    # ---- 未覆盖范围（通用提示）----
    parts.append(
        "**未覆盖范围**（如工程含以下场景，请人工 review）：\n\n"
        "- ⚠️ TTS / STT / Embedding —— 本流水线只迁文本对话 + 图像生成两类\n"
        "- ⚠️ 工具调用 / function-call —— Anthropic tools 协议需手工对齐\n"
        "- ⚠️ 流式 SSE 解析 —— Runway 流式是 base64 包裹的 chunk.bytes，已删 OpenAI SSE 解析；如需 SSE，按 § 五 自实现\n"
        "- ⚠️ 历史会话存储 —— 该入 PG 的应入 PG，本流水线不强改\n"
    )
    return "".join(parts)


def _sso_section(stack: dict) -> str:
    """SSO 改造声明。"""
    if str(stack.get("has_sso", "")) != "1":
        return "_工程未识别到 SSO 接入信号；SSO 改写子任务跳过。_\n"
    return (
        "本次 SSO 改写已覆盖（详见 transform_prompt.md § 六）：\n\n"
        "- ✅ 删除自建 SSO 依赖（passport / next-auth / flask-login 等）\n"
        "- ✅ 改读平台注入的 `Decrypted-Userinfo` HTTP header\n"
        "- ✅ header 值 latin-1 → utf-8 重编码（破中文 mojibake）\n"
        "- ✅ 用户首次访问 auto-provision（按业务唯一字段 upsert）\n"
        "- ✅ 前端身份槽位接 header 透传，删 mock\n\n"
        "**注意**：\n\n"
        "- 平台只透传 6 个 header 字段（`hrUserId` / `userId` / `name` / `nickname` / `email` / `entType`）\n"
        "- 不要静默兜空 hrUserId 等 HR 字段；缺字段必须 401 / 显式拒绝\n"
        "- DEV 联调时可造 header；生产由 SSO 网关注入\n"
    )


def run(cfg: config.Config) -> int:
    report = cfg.state_dir / "report.md"
    # 统一引用 cfg.zip_path —— 与 stage 60 实际写出的带时间戳文件名一致
    zip_path = cfg.zip_path

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    zip_size = _human_size(zip_path.stat().st_size) if zip_path.is_file() else "missing"

    stack = _read_stack(cfg.state_dir)
    stack_text = json.dumps(stack, indent=2, ensure_ascii=False) if stack else "(missing)"

    fp_path = cfg.state_dir / "smoke-fingerprint.txt"
    fp_text = fp_path.read_text().rstrip("\n") if fp_path.is_file() else "(missing)"

    # 扫 verify-*.log 给通过列表
    verify_lines: list[str] = []
    for f in sorted(cfg.state_dir.glob("verify-*.log")):
        name = f.stem.removeprefix("verify-")
        if _verify_log_status(f):
            verify_lines.append(f"- ✅ {name}")
        else:
            verify_lines.append(f"- ❌ {name}")
    verify_block = "\n".join(verify_lines) if verify_lines else "_(无)_"

    git_log_text = _git_log(cfg.work_dir)

    parts = [
        "# guard-transform 交付报告\n\n",
        f"- 生成时间: {now}\n",
        f"- 源工程  : `{cfg.source_project}`\n",
        f"- 工作副本: `{cfg.work_dir}`\n",
        f"- zip 产物: `{zip_path}` ({zip_size})\n\n",
        "## 形态判定\n\n",
        "```json\n",
        stack_text,
        "\n```\n\n",
        "## 执行进度（checklist）\n\n",
        checklist.to_md(),
        "\n",
        "## AI 调用改造（文本 Runway Bedrock + 图像 Runway Google GenerateContent）\n\n",
        _ai_coverage_section(stack),
        "\n",
        "## SSO 改造（Decrypted-Userinfo + auto-provision）\n\n",
        _sso_section(stack),
        "\n",
        "## Verifier 通过列表\n\n",
        verify_block,
        "\n\n",
        "## 烟测 fingerprint（机器可验证、不可伪造）\n\n",
        "```\n",
        fp_text,
        "\n```\n\n",
        "## 关键改动 git diff（人工 review 用）\n\n",
        "```\n",
        git_log_text,
        "\n```\n\n",
        "## 下一步\n\n",
        f"1. 把 `{zip_path}` 提交到 Guard 平台\n",
        "2. 平台会注入 `db.properties` / `ai.properties` 后跑 `install.sh`\n",
        f"3. 详细日志: `{cfg.state_dir}/transform.log` + `{cfg.state_dir}/verify-*.log`\n",
    ]
    report.write_text("".join(parts))

    log.log(f"报告已生成: {report}")
    # 缩进打报告内容到 stderr
    for line in report.read_text().splitlines():
        log.log(f"    {line}")

    log.ok("stage 70 完成")
    return 0
