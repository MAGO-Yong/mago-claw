#!/usr/bin/env bash
# 验证 start.sh 里 gunicorn/uvicorn 启动用的 'module:attr' 在目标 .py 模块顶层确实暴露了 attr
#
# 动机：用工厂函数 create_app() 模式时常见报错——
#   Failed to find attribute 'app' in 'app'.
#   [ERROR] Reason: App failed to load.
# gunicorn/uvicorn 拿到 'app:app' 后会 importlib.import_module('app') 然后 getattr('app')，
# 模块级没有这个名字就直接挂；本 verifier 在打包前用 ast 静态拦截。
#
# Skip 条件（任一）：
#   - work_dir 没有 start.sh
#   - start.sh 里既没 gunicorn 也没 uvicorn / python -m uvicorn
#   - 启动命令已显式带 --factory 标志（gunicorn 22+ / uvicorn 0.15+）
#   - module:attr 中 attr 带 () 后缀（gunicorn 老版 factory 写法 'app:create_app()'）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

if [ ! -f start.sh ]; then
    echo "[OK] start.sh 不存在，skip"
    exit 0
fi

# 快速判断：是否是 Python WSGI/ASGI 启动
if ! grep -qE '\b(gunicorn|uvicorn|hypercorn|daphne)\b' start.sh && \
   ! grep -qE 'python\s+-m\s+(gunicorn|uvicorn|hypercorn|daphne)' start.sh; then
    echo "[OK] start.sh 中未发现 gunicorn/uvicorn/hypercorn/daphne 启动命令，skip（非 Python WSGI/ASGI 项目）"
    exit 0
fi

export GVAF_WORK_DIR="$(pwd)"
export GVAF_START_SH="$(cat start.sh)"

exec python3 - <<'PY'
"""
verify_app_factory 内嵌脚本：
1. 解析 start.sh 抽出 gunicorn/uvicorn 命令的 module:attr
2. 把 module 转文件路径，在 work_dir 下 resolve
3. ast 扫该文件顶层，确认 attr 是 Assign / FunctionDef / ClassDef / ImportFrom 之一
4. 不是 → FAIL，并给出"是否存在 create_app/make_app 工厂函数"的额外提示
"""
import ast
import os
import re
import sys
from pathlib import Path

WORK_DIR = Path(os.environ["GVAF_WORK_DIR"]).resolve()
START_SH = os.environ["GVAF_START_SH"]

# ---------- 1. 抽出所有 gunicorn / uvicorn 启动行 ----------
# 一行可能是 `exec gunicorn --bind 0.0.0.0:3000 app.main:app`
# 也可能是 `exec python -m uvicorn app:app --host 0.0.0.0 --port 3000`
# 还可能多行 cd 后才跑 gunicorn → 取每个发生 gunicorn/uvicorn 的"逻辑行"

LAUNCHERS = ("gunicorn", "uvicorn", "hypercorn", "daphne")

def _iter_launch_lines(text: str):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for launcher in LAUNCHERS:
            if re.search(rf"\b{launcher}\b", line):
                yield launcher, line
                break

# ---------- 2. 也要追踪 cd 子目录（start.sh 模板会先 cd backend 再跑命令） ----------
# 搜集 cd 目标，启动命令的"模块查找根目录"= work_dir + 最近一次 cd 目标
def _resolve_search_root(text: str) -> Path:
    """取最后一个 cd 目标（相对/绝对），找不到 cd 就用 work_dir。"""
    root = WORK_DIR
    for raw in text.splitlines():
        line = raw.strip()
        # cd "$(dirname "$0")/backend" 或 cd backend
        m = re.search(r'\bcd\s+"?\$\(dirname\s+"?\$0"?\)/([^"\s]+)"?', line)
        if m:
            cand = WORK_DIR / m.group(1)
            if cand.is_dir():
                root = cand
            continue
        m = re.match(r'\bcd\s+"?([^"\s$][^"\s]*)"?\s*$', line)
        if m:
            cand = WORK_DIR / m.group(1)
            if cand.is_dir():
                root = cand
    return root

SEARCH_ROOT = _resolve_search_root(START_SH)

# ---------- 3. 从 launch line 抽 module:attr ----------
# 排除：
#   - --factory 标志已显式
#   - module:attr 后带 () 的（gunicorn 老 factory 写法）
#   - 形如 0.0.0.0:3000 这种 host:port（前部分非合法 Python 模块名）
_MODATTR_RE = re.compile(r"(?<![A-Za-z0-9._/-])([A-Za-z_][\w.]*):([A-Za-z_]\w*)(\(\))?(?![A-Za-z0-9._-])")

def _is_valid_module_token(s: str) -> bool:
    # 排除 0.0.0.0、localhost、127.0.0.1、http、https 等明显非模块的
    if not s or s[0].isdigit():
        return False
    if s.lower() in ("http", "https", "ws", "wss", "tcp", "unix", "fd"):
        return False
    return True

# (module, attr, raw_match) 三元组
hits: list[tuple[str, str, str]] = []
for launcher, line in _iter_launch_lines(START_SH):
    # 显式 --factory：跳过此行（uvicorn / gunicorn 22+ 都支持）
    if re.search(r"--factory(\s|=)", line):
        continue
    for m in _MODATTR_RE.finditer(line):
        mod, attr, paren = m.group(1), m.group(2), m.group(3)
        if not _is_valid_module_token(mod):
            continue
        if paren:
            # 'app:create_app()' 形式 = gunicorn 老 factory 写法，跳过
            continue
        # 排除常见 host:port 误捕（端口为纯数字时 attr 不会匹配 \w，但端口可能 alphanum）
        # 已被 _is_valid_module_token 过滤；额外排除 attr 全是数字的（理论不会，因正则要求首字母）
        hits.append((mod, attr, line))
        break  # 一行通常只有一个 module:attr

if not hits:
    print("[OK] start.sh 中未发现 module:attr 启动模式（可能是 --factory / 其他形式），skip")
    sys.exit(0)

# ---------- 4. module → 文件路径 resolve ----------
def _module_to_file(mod: str, root: Path) -> Path | None:
    """把 'a.b.c' 转成文件：优先找 root/a/b/c.py，再找 root/a/b/c/__init__.py。"""
    parts = mod.split(".")
    cand_file = root.joinpath(*parts[:-1], parts[-1] + ".py")
    if cand_file.is_file():
        return cand_file
    cand_pkg = root.joinpath(*parts) / "__init__.py"
    if cand_pkg.is_file():
        return cand_pkg
    # 兜底：在 work_dir 全局 find 一下（适配某些非标准布局）
    for guess in [root, WORK_DIR]:
        # 只找 module 最后一段同名的 .py
        for p in guess.rglob(f"{parts[-1]}.py"):
            # 跳过常见噪音目录
            rel = p.relative_to(guess).parts
            if any(x in rel for x in (".git", "node_modules", "__pycache__", ".venv", "venv", ".venv-build-check", "dist", "build", "tests", "test")):
                continue
            return p
    return None

# ---------- 5. ast 检查 attr 是否在模块顶层 ----------
def _module_top_names(file: Path) -> tuple[set[str], list[str]]:
    """返回 (顶层名字集合, 检测到的工厂函数列表)。

    顶层来源：Assign / AnnAssign / FunctionDef / AsyncFunctionDef / ClassDef / ImportFrom alias。
    工厂函数：函数名匹配 create_app / make_app / app_factory / build_app / get_app 之类。
    """
    factory_pat = re.compile(r"^(create|make|build|get|new|init)_?app$|^app_factory$", re.IGNORECASE)
    names: set[str] = set()
    factories: list[str] = []
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError):
        return names, factories
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
                elif isinstance(tgt, (ast.Tuple, ast.List)):
                    for elt in tgt.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            if factory_pat.match(node.name):
                factories.append(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
    return names, factories

# ---------- 6. 跑检查，收集失败 ----------
failures: list[str] = []
for mod, attr, line in hits:
    file = _module_to_file(mod, SEARCH_ROOT)
    if file is None:
        rel_root = SEARCH_ROOT.relative_to(WORK_DIR) if SEARCH_ROOT != WORK_DIR else Path(".")
        failures.append(
            f"启动行: `{line}`\n"
            f"      问题: 找不到模块 `{mod}` 对应的 .py 文件\n"
            f"      搜索根: {rel_root}\n"
            f"      尝试过: {rel_root}/{mod.replace('.', '/')}.py 和 {rel_root}/{mod.replace('.', '/')}/__init__.py\n"
            f"      修复建议: 检查 start.sh 的模块路径是否正确，或确认 cd 到了正确的目录"
        )
        continue
    rel = file.relative_to(WORK_DIR)
    names, factories = _module_top_names(file)
    if attr in names:
        continue  # 命中，OK
    # 失败：构造详细修复建议
    msg = (
        f"启动行: `{line}`\n"
        f"      问题: gunicorn/uvicorn 要从模块 `{mod}` 取属性 `{attr}`，但 `{rel}` 顶层未暴露 `{attr}`\n"
        f"      该模块顶层已有的名字: {sorted(names) if names else '(空)'}"
    )
    if factories:
        msg += (
            f"\n      检测到工厂函数: {factories}（典型的 'use create_app() pattern'）\n"
            f"      修复建议（任选其一）：\n"
            f"        a) 在 {rel} 末尾追加：app = {factories[0]}()\n"
            f"        b) 改 start.sh 用 factory 模式：\n"
            f"           - uvicorn:  python -m uvicorn --factory {mod}:{factories[0]} --host 0.0.0.0 --port 3000\n"
            f"           - gunicorn 22+:  gunicorn --factory --bind 0.0.0.0:3000 {mod}:{factories[0]}\n"
            f"           - gunicorn 旧版:  gunicorn --bind 0.0.0.0:3000 '{mod}:{factories[0]}()'"
        )
    else:
        msg += (
            f"\n      可能原因: 该 attr 在子模块里，需要 re-export；或 attr 命名不一致\n"
            f"      修复建议：\n"
            f"        a) 在 {rel} 顶层加：app = ...（实例化你的 ASGI/WSGI 应用）\n"
            f"        b) 在 {rel} 顶层加：from .somewhere import app\n"
            f"        c) 改 start.sh 的 module:attr 指向真正暴露 app 的模块"
        )
    failures.append(msg)

if not failures:
    print(f"[OK] start.sh 启动入口已校验：{len(hits)} 个 module:attr 均在模块顶层暴露")
    for mod, attr, _line in hits:
        print(f"    - {mod}:{attr}")
    sys.exit(0)

# ---------- 7. 失败报告 ----------
print(f"[FAIL] start.sh 启动入口不可用：{len(failures)} 个 module:attr 在模块顶层未暴露", file=sys.stderr)
print("    （等部署到 Pod 起 gunicorn/uvicorn 时会立即 'Failed to find attribute X in Y'）", file=sys.stderr)
print(file=sys.stderr)
for i, msg in enumerate(failures, 1):
    print(f"  [{i}] {msg}", file=sys.stderr)
    print(file=sys.stderr)
print("    背景：FastAPI / Flask 用工厂函数 create_app() 时，模块级必须显式实例化，", file=sys.stderr)
print("    否则 importlib.import_module(mod); getattr(mod, attr) 会 AttributeError。", file=sys.stderr)
sys.exit(1)
PY
