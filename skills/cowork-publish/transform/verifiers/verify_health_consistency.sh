#!/usr/bin/env bash
# 验证 health.sh 健康检查与业务代码"对齐到 Guard 子应用规范约定的 `/health`"
#
# 单向强制（重要）：
#   Guard 子应用规范约定：所有子应用必须在 HTTP 端口 3000 上暴露 `/health` 健康检查接口，
#   平台用这个统一约定来探活、判断容器是否就绪、决定是否切流量。子应用如果换路径
#   （/api/health、/healthz、/actuator/health）就破坏了这个统一契约，平台无法识别。
#
#   因此：
#     1) 如果 health.sh 用 HTTP 探活 → probe path 必须是 `/health`（Guard 规范统一约定，
#        不能 /api/health / /healthz / /actuator/health）
#     2) 业务代码必须真的暴露 `/health` endpoint（顶层挂在主 app，不能挂带 prefix 的 router）
#     3) 否则报 error，让 stage 20 LLM autofix 去：
#        a) 在主应用顶层加 `@app.get("/health")`（或对应框架等价代码）
#        b) 同步把 health.sh 改回探 `/health`
#
# 三种健康检查方式：
#   1) HTTP 探活：进入"严格 /health 强制"逻辑（上面）
#   2) TCP only（nc / </dev/tcp/）：warn——TCP 通仅说明端口 listen，不等于业务可用；
#      Guard 规范要求 HTTP `/health`，业务最好仍暴露
#   3) ping / 进程检查：error——假探活；进程在 ≠ 服务可用，ICMP 通 ≠ 应用响应
#
# 与 verify_entry_scripts.sh 的分工：
#   - verify_entry_scripts: 基础格式（shebang/语法/host/port=3000/不能 0.0.0.0）
#   - verify_health_consistency: 强制对齐 Guard 子应用规范 `/health` + 业务跨语言路由扫描
#
# Skip 条件：
#   - work_dir 没有 health.sh（前一阶段 stage 30 没渲染，跳过让 entry_scripts 报）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

if [ ! -f health.sh ]; then
    echo "[OK] health.sh 不存在，skip"
    exit 0
fi

export GVHC_WORK_DIR="$(pwd)"
export GVHC_HEALTH_SH="$(cat health.sh)"

exec python3 - <<'PY'
"""
verify_health_consistency 内嵌脚本。

流程：
1) 解析 health.sh，分类探测方式（http_path / tcp_only / ping / process / unknown）
2) 跨语言扫业务代码路由 + router prefix
3) 匹配 health.sh probe path 到业务声明（精确 / 后缀兼容 router prefix）
4) Actuator 等特例豁免
5) 输出 OK/warn/FAIL 与详细修复建议
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

WORK_DIR = Path(os.environ["GVHC_WORK_DIR"]).resolve()
HEALTH_SH = os.environ["GVHC_HEALTH_SH"]


# ------------------------------ 1. 解析 health.sh ------------------------------
# 探测方式分类
HTTP_PROBES: list[dict] = []  # [{"host":..., "port":..., "path":..., "raw":...}]
TCP_PROBES: list[dict] = []   # [{"host":..., "port":...}]
PING_PROBES: list[str] = []
PROCESS_PROBES: list[str] = []

# HTTP: curl/wget/httpx/http
# 1. 完整 URL 形式：http(s)://host:port/path
# 2. host:port/path（curl 接受省略 http://，wget 也可）
HTTP_RE = re.compile(
    r'(?:curl|wget|httpx?|http)\b[^|;&\n]*?'                    # 命令前缀（取到第一个分隔符前）
    r'(?:https?://)?'                                            # 可选 scheme
    r'(?P<host>127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])'      # host
    r':(?P<port>\d+)'                                            # port
    r'(?P<path>/[\w\-./%~?=&+:@!,()*]*?)?'                       # path（可选）
    r'(?=[\s\'"`|;&]|$)',                                        # 终止
    re.IGNORECASE | re.MULTILINE,
)

# TCP: nc -z host port / </dev/tcp/host/port
NC_RE = re.compile(
    r'\bnc\s+(?:-[a-zA-Z]+\s+)*'
    r'(?P<host>127\.0\.0\.1|localhost|0\.0\.0\.0)\s+(?P<port>\d+)\b'
)
DEVTCP_RE = re.compile(
    r'/dev/tcp/(?P<host>127\.0\.0\.1|localhost)/(?P<port>\d+)'
)

# Ping
PING_RE = re.compile(r'\bping\s+(?:-[a-zA-Z]+\s+\d*\s*)*(?:127\.0\.0\.1|localhost|0\.0\.0\.0)\b')

# Process check
PROCESS_RE = re.compile(r'\b(?:pgrep|pidof)\b|\bps\s+(?:-[a-zA-Z]+\s*)*\|.*\bgrep\b')


def _parse_health_sh():
    for raw in HEALTH_SH.splitlines():
        line = raw.split("#", 1)[0]  # 砍尾注释
        if not line.strip():
            continue
        # HTTP
        for m in HTTP_RE.finditer(line):
            path = m.group("path") or "/"
            # 砍掉 query string（探活看 path）
            path = path.split("?", 1)[0].split("#", 1)[0]
            if not path.startswith("/"):
                path = "/" + path
            HTTP_PROBES.append({
                "host": m.group("host"),
                "port": int(m.group("port")),
                "path": path,
                "raw": line.strip(),
            })
        # TCP
        for m in NC_RE.finditer(line):
            TCP_PROBES.append({
                "host": m.group("host"), "port": int(m.group("port")), "raw": line.strip(),
            })
        for m in DEVTCP_RE.finditer(line):
            TCP_PROBES.append({
                "host": m.group("host"), "port": int(m.group("port")), "raw": line.strip(),
            })
        # Ping
        if PING_RE.search(line):
            PING_PROBES.append(line.strip())
        # Process
        if PROCESS_RE.search(line):
            PROCESS_PROBES.append(line.strip())


_parse_health_sh()


def _info_probe_summary() -> str:
    parts = []
    if HTTP_PROBES:
        for p in HTTP_PROBES:
            parts.append(f"HTTP {p['host']}:{p['port']}{p['path']}")
    if TCP_PROBES:
        for p in TCP_PROBES:
            parts.append(f"TCP {p['host']}:{p['port']}")
    if PING_PROBES:
        parts.append(f"PING x{len(PING_PROBES)}")
    if PROCESS_PROBES:
        parts.append(f"PROCESS x{len(PROCESS_PROBES)}")
    return ", ".join(parts) or "(未识别)"


# ------------------------------ 2. 扫业务代码 HTTP 路由 ------------------------------
# 路由规则: (file_glob, regex, capture_group, needs_prefix)
#   needs_prefix=False: 装饰器对象本身就是应用实例（@app.xxx），声明的 path 直接暴露
#   needs_prefix=True : 装饰器对象是 router/blueprint 等，真实暴露 path = prefix + 声明 path；
#                       若没有 prefix，则直接暴露
#
# 关键区分：FastAPI `@app.get("/health")` 真实路径 = /health；
#         FastAPI `@router.get("/health")` + `APIRouter(prefix="/api")` 真实路径 = /api/health
ROUTE_RULES = [
    # ---------- Python ----------
    # FastAPI/Starlette/Sanic: @app.get/post/put/delete/patch/head/options/api_route("/x")
    ("*.py", re.compile(r'@app\.(?:get|post|put|delete|patch|head|options|api_route)\s*\(\s*["\']([^"\']+)["\']'), 1, False),
    ("*.py", re.compile(r'@(?!app\b)\w+\.(?:get|post|put|delete|patch|head|options|api_route)\s*\(\s*["\']([^"\']+)["\']'), 1, True),
    # Flask/Quart/Sanic: @app.route("/x")  vs  @bp.route("/x")
    ("*.py", re.compile(r'@app\.route\s*\(\s*["\']([^"\']+)["\']'), 1, False),
    ("*.py", re.compile(r'@(?!app\b)\w+\.route\s*\(\s*["\']([^"\']+)["\']'), 1, True),
    # 显式 add_api_route / add_url_rule（直接挂应用实例上时 = app_route，挂 router 时 = sub_route，无法精准区分时按 needs_prefix=True 兜底）
    ("*.py", re.compile(r'\bapp\.add_(?:api_route|url_rule)\s*\(\s*["\']([^"\']+)["\']'), 1, False),
    ("*.py", re.compile(r'(?<!app)\.add_(?:api_route|url_rule)\s*\(\s*["\']([^"\']+)["\']'), 1, True),
    # Django urls: path("x/", ...), re_path(r'^x/$', ...) — Django urlpatterns 通常已是完整路径
    ("*.py", re.compile(r'(?:^|\W)(?:path|re_path|url)\s*\(\s*r?["\']([^"\']+)["\']'), 1, True),
    # Bottle 顶层: @route("/x") / @get("/x") （顶层装饰器，无 router 概念）
    ("*.py", re.compile(r'(?:^|\n)\s*@(?:route|get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'), 1, False),

    # ---------- Node.js (Express/Koa/Fastify/Hono) ----------
    # app.get/use/...：直挂应用
    ("*.js,*.ts,*.cjs,*.mjs", re.compile(r'\b(?:app|server|fastify|hono)\.(?:get|post|put|delete|patch|all|head|options)\s*\(\s*["\'`]([^"\'`]+)["\'`]'), 1, False),
    # router.get/use/...：sub_routes
    ("*.js,*.ts,*.cjs,*.mjs", re.compile(r'\b(?:router|route)\.(?:get|post|put|delete|patch|all|head|options)\s*\(\s*["\'`]([^"\'`]+)["\'`]'), 1, True),
    # NestJS: @Get("/x")  通常配 @Controller("/api") 在 PREFIX_RULES
    ("*.ts", re.compile(r'@(?:Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*["\']([^"\']*)["\']'), 1, True),

    # 平台产物只支持 Python / Node 后端；Java/Go/Rust 由 stage 20 重写为 Python/Node
]

# router prefix 提取
PREFIX_RULES = [
    # Python: APIRouter(prefix="/api"), include_router(router, prefix="/v1"),
    #         Blueprint(..., url_prefix="/api"), register_blueprint(bp, url_prefix="/api")
    ("*.py", re.compile(r'(?:APIRouter|include_router|Blueprint|Router|register_blueprint)\s*\([^)]*?(?:url_)?prefix\s*=\s*["\']([^"\']+)["\']'), 1),
    # Node Express: app.use("/api", router) / app.use("/v1", someRouter)
    ("*.js,*.ts,*.cjs,*.mjs", re.compile(r'\b(?:app|server|router)\.use\s*\(\s*["\'`](/[^"\'`]*)["\'`]\s*,'), 1),
    # Fastify: fastify.register(routes, { prefix: '/api' })
    ("*.js,*.ts,*.cjs,*.mjs", re.compile(r'\.register\s*\([^)]*?prefix\s*:\s*["\'`](/[^"\'`]*)["\'`]'), 1),
    # NestJS: @Controller("/api") - class 级 prefix
    ("*.ts", re.compile(r'@Controller\s*\(\s*["\']([^"\']+)["\']'), 1),
]

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".venv-build-check",
    "dist", "build", ".next", "target", "out",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode",
}


def _is_excluded(p: Path) -> bool:
    parts = p.relative_to(WORK_DIR).parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if any(part.startswith(".guard-transform-") and part.endswith("-guard") for part in parts):
        return True
    # tests 目录路由通常是测试 mock，不算
    if any(part in ("tests", "test", "__tests__") for part in parts):
        return True
    return False


def _file_matches_glob(p: Path, globs: str) -> bool:
    suffixes = [g.lstrip("*") for g in globs.split(",")]
    name = p.name
    return any(name.endswith(s) for s in suffixes)


# 按文件分组扫描，区分 app_routes（直挂应用）与 sub_routes（router/bp，需 prefix 拼接）
files_data: list[dict] = []
files_scanned = 0

# 收集所有源码扩展名
SRC_GLOBS = sorted({g for rule in ROUTE_RULES + PREFIX_RULES for g in rule[0].split(",")})
EXTS = tuple(g.lstrip("*") for g in SRC_GLOBS)

for src in WORK_DIR.rglob("*"):
    if not src.is_file():
        continue
    if not src.name.endswith(EXTS):
        continue
    if _is_excluded(src):
        continue
    files_scanned += 1
    try:
        text = src.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    fd = {"path": src, "app_routes": set(), "sub_routes": set(), "prefixes": set()}
    # routes
    for globs, pat, grp, needs_prefix in ROUTE_RULES:
        if not _file_matches_glob(src, globs):
            continue
        for m in pat.finditer(text):
            r = m.group(grp).strip()
            if not r:
                continue
            if needs_prefix:
                fd["sub_routes"].add(r)
            else:
                fd["app_routes"].add(r)
    # prefixes
    for globs, pat, grp in PREFIX_RULES:
        if not _file_matches_glob(src, globs):
            continue
        for m in pat.finditer(text):
            r = m.group(grp).strip()
            if r:
                fd["prefixes"].add(r)
    if fd["app_routes"] or fd["sub_routes"] or fd["prefixes"]:
        files_data.append(fd)


# ------------------------------ 3. 匹配工具函数（前置定义，给后面聚合用） ------------------------------
def _normalize(p: str) -> str:
    """trim 尾 /，保留首 /；空 → /"""
    p = p.strip()
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def _join(pf: str, r: str) -> str:
    pf = pf.rstrip("/")
    r = r.lstrip("/")
    return _normalize(pf + "/" + r) if r else (pf or "/")


# ------------------------------ 全局聚合 ------------------------------
app_routes_set: set[str] = set()         # 直接暴露的路径（不需要拼 prefix）
all_sub_routes: set[str] = set()          # 所有 sub_route 原始 path（无 prefix 拼接）
all_prefixes: set[str] = set()            # 所有声明的 prefix
expanded_routes: set[str] = set()         # prefix × sub_route 笛卡尔积后的真实路径
sub_route_files: list[Path] = []          # 含 sub_route 的文件，用于报错提示

for fd in files_data:
    app_routes_set |= {_normalize(r) for r in fd["app_routes"]}
    all_sub_routes |= {_normalize(r) for r in fd["sub_routes"]}
    all_prefixes |= {_normalize(p) for p in fd["prefixes"]}
    if fd["sub_routes"]:
        sub_route_files.append(fd["path"])
    # 同文件内：prefix × sub_route 笛卡尔积
    for pf in fd["prefixes"]:
        for r in fd["sub_routes"]:
            expanded_routes.add(_join(pf, r))

# 跨文件兜底：全局 prefix × 全局 sub_route（覆盖 main.py 写 include_router(prefix=...) + routes.py 写 @router.get 的常见模式）
for pf in all_prefixes:
    for r in all_sub_routes:
        expanded_routes.add(_join(pf, r))

# 若整个项目根本没有任何 prefix 声明，则 sub_routes 直接当 app_routes（无需拼接）
if all_sub_routes and not all_prefixes:
    app_routes_set |= all_sub_routes


# ------------------------------ 3. 匹配逻辑 ------------------------------
def _match_route(probe_path: str) -> tuple[str, str | None]:
    """
    返回 (kind, hit_route)
        kind = "exact"     - probe_path 直接命中 app_routes（顶层装饰器声明）
        kind = "prefix"    - probe_path 命中 prefix×sub_route 笛卡尔积（router/blueprint）
        kind = "sub_only"  - probe_path 仅命中 sub_route 原始 path 但项目存在 prefix 声明
                              → 业务真实路径很可能被 prefix 改写过，probe 实际探不到
        kind = "suffix"    - 仅后缀匹配（router 嵌套未抓全的兜底，warn 级）
        kind = "none"      - 完全不匹配
    """
    np = _normalize(probe_path)

    # 1) app_routes 精确匹配（业务直挂 @app.xxx，无 prefix 困扰）
    if np in app_routes_set:
        return "exact", np

    # 2) prefix × sub_route 展开后精确匹配
    if np in expanded_routes:
        return "prefix", np

    # 3) 命中 sub_route 原始 path（无 prefix 拼接）
    #    → 项目有 prefix 声明时，sub_route 的真实暴露路径很可能 ≠ 原始 path，判定为可疑错误
    if np in all_sub_routes:
        return "sub_only", np

    # 4) 后缀兜底
    candidates = app_routes_set | all_sub_routes | expanded_routes
    for r in candidates:
        if r != "/" and np.endswith("/" + r.lstrip("/")):
            return "suffix", r
    return "none", None


# ------------------------------ 4. 决策 ------------------------------
errors: list[str] = []
warns: list[str] = []
infos: list[str] = []


# 4.1 完全没识别出探测方式
if not (HTTP_PROBES or TCP_PROBES or PING_PROBES or PROCESS_PROBES):
    warns.append(
        "health.sh 中识别不出任何探测方式（curl/wget/nc/ping/pgrep 都没匹配）。"
        "请确认 health.sh 真的在做有效探活。"
    )

# 4.2 Process / Ping → warn（不阻塞，但提醒）
for ln in PROCESS_PROBES:
    warns.append(
        f"health.sh 用进程检查（pgrep/ps grep）做探活：`{ln}`。"
        "进程在不等于服务可用，Guard 子应用规范要求暴露 HTTP `/health`，强烈建议改 HTTP 探测。"
    )
for ln in PING_PROBES:
    errors.append(
        f"health.sh 用 ping 探活：`{ln}`。"
        "ICMP 只验证网络，不验业务可用；Pod 网络层永远通，等于没探。"
    )

# Guard 子应用规范约定：所有子应用必须在端口 3000 上暴露 HTTP `/health` 健康检查接口
PLATFORM_REQUIRED_PATH = "/health"

# 4.3 TCP-only → warn（不阻塞，但仍要提醒业务必须暴露 /health 满足 Guard 规范）
if TCP_PROBES and not HTTP_PROBES:
    # 业务有没有 /health？没有也得报 error，违反 Guard 子应用规范
    kind_h, _ = _match_route(PLATFORM_REQUIRED_PATH)
    for tp in TCP_PROBES:
        warns.append(
            f"health.sh 仅做 TCP 探测 {tp['host']}:{tp['port']}，没有 HTTP path。"
            "Guard 子应用规范要求 HTTP `/health` 健康检查，仅 TCP 通不等于业务可用；"
            "建议 health.sh 也加 `curl http://127.0.0.1:3000/health` 与规范对齐。"
        )
    if kind_h not in ("exact", "prefix"):
        errors.append(
            f"业务代码没有暴露 `{PLATFORM_REQUIRED_PATH}` endpoint，"
            f"违反 Guard 子应用规范（统一约定所有子应用在端口 3000 暴露 HTTP `/health`）。\n"
            "      修复（任选一种，autofix 应优先 a）:\n"
            "        a) 在主应用里加 `/health`，例如 FastAPI:\n"
            "             @app.get(\"/health\") def health(): return {\"ok\": True}\n"
            "        b) Flask:    @app.route('/health') def health(): return {'ok': True}\n"
            "        c) Express:  app.get('/health', (req, res) => res.json({ok: true}))\n"
            "        d) Koa:      router.get('/health', ctx => { ctx.body = {ok: true} })"
        )

# 4.4 HTTP probes：单向强制对齐 `/health`
all_declared_for_hint = sorted(app_routes_set | expanded_routes | all_sub_routes)

for hp in HTTP_PROBES:
    probe_path = _normalize(hp["path"])

    # ① probe path 必须是 /health
    if probe_path != PLATFORM_REQUIRED_PATH:
        # 顺便检查业务是否已经有 /health（用于给 autofix 提示该改哪边）
        kind_h, _ = _match_route(PLATFORM_REQUIRED_PATH)
        biz_has_health = kind_h in ("exact", "prefix")
        errors.append(
            f"health.sh 探的 path `{probe_path}` 不是 Guard 子应用规范约定的 `{PLATFORM_REQUIRED_PATH}`。\n"
            f"      health.sh 行: `{hp['raw']}`\n"
            f"      Guard 子应用规范统一约定：所有子应用在端口 3000 上暴露 HTTP `/health`，"
            f"不能用 /api/health / /healthz / /actuator/health 等其它路径，否则破坏平台对所有子应用的统一探活契约。\n"
            f"      修复（必须两件事都做）:\n"
            f"        1) 改 health.sh 探 `/health`：\n"
            f"             curl -fsS -o /dev/null --max-time 3 http://127.0.0.1:3000/health || exit 1\n"
            f"        2) " + (
                f"业务已暴露 `/health`，无需新增 endpoint，仅改 health.sh 即可。"
                if biz_has_health else
                "在主应用里新增 `/health` endpoint，例如 FastAPI:\n"
                "             @app.get(\"/health\") def health(): return {\"ok\": True}\n"
                "           Express: app.get('/health', (req, res) => res.json({ok: true}))\n"
                f"           （注意：`{probe_path}` 这种带 prefix 的业务路径可以保留共存，但必须额外暴露顶层 `/health`）"
            )
        )
        continue

    # ② probe path == /health → 检查业务是否真的实现了 /health
    kind, hit = _match_route(PLATFORM_REQUIRED_PATH)
    if kind == "exact":
        infos.append(f"HTTP probe `/health` 与业务 app 路由精确匹配 ✓")
    elif kind == "prefix":
        infos.append(f"HTTP probe `/health` 由 router prefix + route 拼接得到，命中 `{hit}` ✓")
    elif kind == "sub_only":
        # 命中了 sub_route 但有 prefix 改写
        possible_real = sorted({_join(pf, "/health") for pf in all_prefixes if _join(pf, "/health") != "/health"})[:5]
        errors.append(
            f"业务代码在 router/blueprint 上声明了 `/health`，但同时存在 router prefix（{sorted(all_prefixes)}），"
            f"实际暴露的真实路径很可能是 {possible_real}，访问 `/health` 仍会 404，违反 Guard 子应用规范。\n"
            f"      health.sh 行: `{hp['raw']}`\n"
            f"      修复（必须改业务代码）：\n"
            f"        把 `/health` 装饰器从带 prefix 的 router 移到主 app 顶层：\n"
            f"          # ❌ 错误（被 prefix 改写）\n"
            f"          @router.get(\"/health\")  # APIRouter(prefix=\"/api\") → 真实路径 /api/health\n"
            f"          # ✅ 正确（顶层 /health，绕过 prefix，符合 Guard 子应用规范）\n"
            f"          @app.get(\"/health\")\n"
            f"          def health(): return {{\"ok\": True}}"
        )
    elif kind == "suffix":
        warns.append(
            f"HTTP probe `/health` 与业务路由 `{hit}` 仅后缀匹配，verifier 扫描规则可能没覆盖完全。"
            "请人工确认主应用真的暴露了顶层 `/health`。"
        )
    else:  # none
        sample = all_declared_for_hint[:8]
        more = "" if len(all_declared_for_hint) <= 8 else f" 等 {len(all_declared_for_hint)} 条"
        errors.append(
            f"业务代码没有暴露 `/health` endpoint，违反 Guard 子应用规范。\n"
            f"      health.sh 行: `{hp['raw']}`\n"
            f"      已扫描业务源码: {files_scanned} 文件，识别到 {len(app_routes_set)} 条 app 路由 + "
            f"{len(all_sub_routes)} 条 sub 路由 + {len(all_prefixes)} 条 prefix\n"
            f"      路由示例: {sample}{more}\n"
            f"      Guard 子应用规范约定：所有子应用必须在端口 3000 暴露 HTTP `/health`。修复:\n"
            f"        a) FastAPI:  @app.get(\"/health\") def health(): return {{\"ok\": True}}\n"
            f"        b) Flask:    @app.route('/health') def health(): return {{'ok': True}}\n"
            f"        c) Express:  app.get('/health', (req, res) => res.json({{ok: true}}))\n"
            f"        d) Koa:      router.get('/health', ctx => {{ ctx.body = {{ok: true}} }})\n"
            f"      ⚠️  必须挂在 **主 app 顶层**（不能挂带 prefix 的 router/blueprint，否则会被改写成 /<prefix>/health）"
        )


# ------------------------------ 5. 输出 ------------------------------
print(f"探测方式汇总: {_info_probe_summary()}")
print(
    f"业务路由: 扫描 {files_scanned} 文件，"
    f"识别 {len(app_routes_set)} 条 app 路由 + {len(all_sub_routes)} 条 sub 路由 "
    f"+ {len(all_prefixes)} 条 prefix（展开后 {len(expanded_routes)} 条真实路径）"
)

for s in infos:
    print(f"  [info] {s}")

if not errors:
    if warns:
        print(f"[OK] health.sh 已对齐 Guard 子应用规范 `/health`（{len(warns)} 条建议）")
        for w in warns:
            print(f"  [warn] {w}")
    else:
        print(f"[OK] health.sh 与业务 `/health` endpoint 完全对齐 Guard 子应用规范")
    sys.exit(0)


# FAIL
print(f"[FAIL] health.sh 与 Guard 子应用规范 `/health` 不对齐，{len(errors)} 个 error / {len(warns)} 个 warn", file=sys.stderr)
print("    Guard 子应用规范统一约定：所有子应用必须在端口 3000 上暴露 HTTP `/health`，", file=sys.stderr)
print("    health.sh 必须探 `/health`，业务必须在主 app 顶层实现 `/health` endpoint。", file=sys.stderr)
print(file=sys.stderr)

# 输出 [HINT] 单行精简版（autofix prompt 抽取用，比 [error N] 详细描述更易被 LLM 直接执行）
biz_has_health = _match_route(PLATFORM_REQUIRED_PATH)[0] in ("exact", "prefix")
non_health_probes = [p for p in HTTP_PROBES if _normalize(p["path"]) != PLATFORM_REQUIRED_PATH]
if non_health_probes:
    bad_paths = ",".join(sorted({_normalize(p["path"]) for p in non_health_probes}))
    print(f"[HINT] 目标文件 health.sh：把 curl 探测路径从 {bad_paths} 改为 /health（保留 host=127.0.0.1 port=3000）", file=sys.stderr)
if not biz_has_health:
    print("[HINT] 目标文件：业务主入口（FastAPI main.py / Express app.js 等顶层文件）。新增一个挂在主 app 上的 /health endpoint（不能挂带 prefix 的 router/blueprint），例如 `@app.get(\"/health\") def health(): return {\"ok\": True}`", file=sys.stderr)
elif all_prefixes and PLATFORM_REQUIRED_PATH in all_sub_routes:
    print(f"[HINT] 目标文件：声明 router prefix 的主入口文件。把 /health 装饰器从带 prefix（当前: {sorted(all_prefixes)}）的 router 移到主 app 顶层 @app.get，避免被改写为 /<prefix>/health", file=sys.stderr)

for i, e in enumerate(errors, 1):
    print(f"  [error {i}] {e}", file=sys.stderr)
    print(file=sys.stderr)
if warns:
    for j, w in enumerate(warns, 1):
        print(f"  [warn {j}] {w}", file=sys.stderr)
sys.exit(1)
PY
