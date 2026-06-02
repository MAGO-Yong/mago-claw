#!/usr/bin/env bash
# 验证 Python 项目里所有第三方 import 都已声明在 requirements*.txt
#
# 动机：stage 40 build 只跑 `pip install -r requirements.txt`，能保证
# **声明的能装上**；但如果代码 import 了某个包却没写进 requirements，
# pip install 不会报错（venv 里碰巧已装的 transitive 依赖能 import），
# 等部署到 Pod 拉新 venv 才 ModuleNotFoundError —— 排查成本极高。
#
# 本 verifier 用 ast 扫描所有 .py 的顶层 import，与所有 requirements*.txt
# 已声明的包名做差集，报告缺失项。
#
# Skip 条件（任一满足）：
#   - work_dir 下没有任何 .py 文件
#   - work_dir 下没有任何 requirements*.txt 文件（非 Python 项目，由别的检查兜底）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

# 快速 skip：非 Python 项目
HAS_PY=$(find . \
    -type d \( \
        -name '.git' -o -name 'node_modules' -o -name '__pycache__' \
        -o -name '.venv' -o -name 'venv' -o -name '.venv-build-check' \
        -o -name 'dist' -o -name 'build' -o -name '.next' \
        -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \
        -o -name '.guard-transform-*-guard' \
    \) -prune -o -type f -name '*.py' -print 2>/dev/null \
    | head -1)
if [ -z "$HAS_PY" ]; then
    echo "[OK] 非 Python 项目（无 .py 文件），skip"
    exit 0
fi

# 收集所有 requirements*.txt（兼容 macOS bash 3.2，不用 mapfile）
REQ_LIST=$(find . \
    -type d \( \
        -name '.git' -o -name 'node_modules' -o -name '__pycache__' \
        -o -name '.venv' -o -name 'venv' -o -name '.venv-build-check' \
        -o -name '.guard-transform-*-guard' \
    \) -prune -o -type f \( -name 'requirements.txt' -o -name 'requirements-*.txt' -o -name 'requirements_*.txt' \) -print 2>/dev/null \
    | sort)

if [ -z "$REQ_LIST" ]; then
    # 有 .py 但完全没 requirements*.txt → 直接 FAIL
    # （Pod 装不了任何依赖，业务必跑不起来）
    echo "[FAIL] 项目含 .py 文件但未发现任何 requirements*.txt" >&2
    echo "    Guard 子应用规范要求 Python 后端必须用 requirements.txt 声明依赖" >&2
    echo "    建议：在后端目录下 \`pip freeze > requirements.txt\` 或手写依赖清单" >&2
    exit 1
fi

# 把 requirements 清单通过环境变量传给内嵌 python
# （stdin 被 heredoc 占了，argv 又有空格路径风险，env 是最稳的）
# 注意：上面已 cd 进 WORK_DIR，所以用 $(pwd) 拿绝对路径，避免 python 再 resolve 一次出错
export GVPR_WORK_DIR="$(pwd)"
export GVPR_REQ_LIST="$REQ_LIST"
exec python3 - <<'PY'
"""
verify_python_requirements 内嵌脚本：
- 扫所有 .py 抽顶层 import 名
- 扫所有 requirements*.txt 抽包名（处理 == >= ~= [extras] ; -r 等）
- 排除 stdlib + 项目本地包
- 用别名表把 import 名映射回 pip 包名做差集
- 缺失项 → 输出 [FAIL] + 在哪些文件 import + exit 1
"""
import ast
import os
import re
import sys
from pathlib import Path

WORK_DIR = Path(os.environ["GVPR_WORK_DIR"]).resolve()
REQ_FILES = [Path(p).resolve() for p in os.environ["GVPR_REQ_LIST"].splitlines() if p.strip()]

# ---------- import 名 → pip 包名 别名表 ----------
# 仅列常见的 import 名 与 pip 包名 不一致 的情况，覆盖 ~80% 实际场景
# 没列的按"归一化等价"匹配（lowercase + - / _ / . 互通）
ALIASES = {
    "pil":              "pillow",
    "yaml":             "pyyaml",
    "cv2":              "opencv-python",
    "bs4":              "beautifulsoup4",
    "sklearn":          "scikit-learn",
    "skimage":          "scikit-image",
    "dotenv":           "python-dotenv",
    "jose":             "python-jose",
    "jwt":              "pyjwt",
    "magic":            "python-magic",
    "dateutil":         "python-dateutil",
    "crontab":          "python-crontab",
    "attr":             "attrs",
    "openssl":          "pyopenssl",
    "serial":           "pyserial",
    "nacl":             "pynacl",
    "mysqldb":          "mysqlclient",
    "psycopg2":         "psycopg2-binary",
    "levenshtein":      "python-levenshtein",
    "win32com":         "pywin32",
    "win32api":         "pywin32",
    "yaml_include":     "pyyaml-include",
    "snappy":           "python-snappy",
    "zstd":             "zstandard",
    "memcache":         "python-memcached",
    "ldap":             "python-ldap",
    "twisted":          "twisted",
    "cryptography":     "cryptography",
    "rsa":              "rsa",
    "discord":          "discord.py",
    "telegram":         "python-telegram-bot",
    "ujson":            "ujson",
    "orjson":           "orjson",
    "msgpack":          "msgpack",
    "thrift":           "thrift",
    "lxml":             "lxml",
    "babel":            "babel",
    "graphql":          "graphql-core",
    "ariadne":          "ariadne",
    "strawberry":       "strawberry-graphql",
    "alembic":          "alembic",
    "sqlalchemy":       "sqlalchemy",
    "asyncpg":          "asyncpg",
    "aiomysql":         "aiomysql",
    "aiohttp":          "aiohttp",
    "httpx":            "httpx",
    "anthropic":        "anthropic",
    "openai":           "openai",
}

# ---------- "前缀豁免" 命名空间包：import google → 任何 google-* 包都算满足 ----------
# 适用于 namespace package（PEP 420）实践
NAMESPACE_PREFIXES = ("google", "azure", "aws_cdk", "awscdk", "tencentcloud", "alibabacloud", "ms_graph", "msgraph")

# ---------- 不该被算为"第三方"的顶层名 ----------
# 1) Python stdlib（用 sys.stdlib_module_names，3.10+ 才有，旧版本 fallback 硬编码）
try:
    STDLIB = set(sys.stdlib_module_names)  # py3.10+
except AttributeError:
    # 保底硬编码常用 stdlib 包，覆盖 py3.7+ 跑得动
    STDLIB = {
        "abc","argparse","array","ast","asyncio","base64","bisect","builtins",
        "calendar","cmath","collections","concurrent","configparser","contextlib",
        "contextvars","copy","csv","ctypes","dataclasses","datetime","decimal","difflib",
        "dis","email","enum","errno","faulthandler","fcntl","filecmp","fileinput",
        "fnmatch","fractions","functools","gc","getopt","getpass","gettext","glob",
        "graphlib","gzip","hashlib","heapq","hmac","html","http","imaplib","importlib",
        "inspect","io","ipaddress","itertools","json","keyword","linecache","locale",
        "logging","lzma","math","mimetypes","mmap","modulefinder","multiprocessing",
        "netrc","numbers","operator","optparse","os","pathlib","pdb","pickle","pkgutil",
        "platform","plistlib","poplib","posix","posixpath","pprint","profile","pstats",
        "pty","pwd","py_compile","pyclbr","pydoc","queue","quopri","random","re",
        "readline","reprlib","resource","runpy","sched","secrets","select","selectors",
        "shelve","shlex","shutil","signal","site","smtpd","smtplib","sndhdr","socket",
        "socketserver","sqlite3","ssl","stat","statistics","string","stringprep",
        "struct","subprocess","sunau","symtable","sys","sysconfig","syslog","tabnanny",
        "tarfile","telnetlib","tempfile","termios","textwrap","threading","time",
        "timeit","tkinter","token","tokenize","tomllib","trace","traceback","tracemalloc",
        "tty","turtle","types","typing","unicodedata","unittest","urllib","uuid",
        "venv","warnings","wave","weakref","webbrowser","wsgiref","xdrlib","xml",
        "xmlrpc","zipapp","zipfile","zipimport","zlib","zoneinfo","__future__",
        "__main__",
    }
# 兼容 setuptools / pip 等总会安装的元包
ALWAYS_PRESENT = {"setuptools", "pip", "wheel", "pkg_resources", "_distutils_hack"}

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__",
    ".venv", "venv", ".venv-build-check", "env", ".env",
    "dist", "build", ".next",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "tests", "test",  # 测试代码的额外依赖通常用 requirements-dev.txt 单独管理；保守起见不扫
}

def _is_excluded(p: Path) -> bool:
    parts = p.relative_to(WORK_DIR).parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if any(part.startswith(".guard-transform-") and part.endswith("-guard") for part in parts):
        return True
    return False

def _normalize(name: str) -> str:
    """pip 包名归一化（PEP 503）：lowercase，- _ . 统一为 -"""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()

# ---------- 解析 requirements*.txt ----------
def _parse_req(file: Path) -> set[str]:
    pkgs = set()
    try:
        for raw in file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            # -r other.txt / -c constraints.txt / -e ./local
            if line.startswith(("-r ", "--requirement ", "-c ", "--constraint ")):
                continue
            if line.startswith(("-e ", "--editable ")):
                # 本地 editable 包：跳过（不影响公网装包检查）
                continue
            # URL 直接装：git+https://... / file://...
            if "://" in line:
                # 取 #egg=name 或文件名
                m = re.search(r"[#&]egg=([A-Za-z0-9_.\-]+)", line)
                if m:
                    pkgs.add(_normalize(m.group(1)))
                continue
            # 截掉 ; 环境标记
            line = line.split(";", 1)[0].strip()
            # 截掉 [extras]
            line = re.sub(r"\[.*?\]", "", line)
            # 截掉版本说明符
            line = re.split(r"[<>=!~ ]", line, maxsplit=1)[0].strip()
            if line:
                pkgs.add(_normalize(line))
    except OSError as e:
        print(f"[warn] 读 {file} 失败: {e}", file=sys.stderr)
    return pkgs

DECLARED: set[str] = set()
for req in REQ_FILES:
    DECLARED |= _parse_req(req)

# ---------- 计算"项目本地模块名"（避免误报）----------
# 顶层目录中的可能包：work_dir 直接子目录里有 __init__.py 或 .py 入口的目录名
LOCAL_MODULES: set[str] = set()
for child in WORK_DIR.iterdir():
    if not child.is_dir() or child.name in EXCLUDE_DIRS:
        continue
    if child.name.startswith(".guard-transform-") and child.name.endswith("-guard"):
        continue
    # 若该目录下有 .py 或 __init__.py，算本地包
    if (child / "__init__.py").is_file() or any(child.glob("*.py")):
        LOCAL_MODULES.add(_normalize(child.name))
    # 常见的 backend 二级目录：backend/app, backend/src 等
    for sub in child.iterdir() if child.is_dir() else []:
        if sub.is_dir() and sub.name not in EXCLUDE_DIRS:
            if (sub / "__init__.py").is_file():
                LOCAL_MODULES.add(_normalize(sub.name))

# 常见本地"应用代码"目录别名
LOCAL_MODULES |= {"app", "apps", "src", "lib", "core", "common", "utils", "config", "conf",
                  "models", "model", "services", "service", "api", "apis", "router", "routers",
                  "routes", "controllers", "schemas", "schema", "db", "database", "migrations",
                  "tests", "test", "scripts"}

# ---------- 扫所有 .py 抽 import ----------
# imports[top_module] = [file1, file2, ...]
imports: dict[str, list[str]] = {}

def _add_import(mod: str, file: Path) -> None:
    top = mod.split(".", 1)[0].strip()
    if not top or top.startswith("_"):
        return
    norm = _normalize(top)
    if norm in STDLIB or norm in {_normalize(s) for s in STDLIB}:
        return
    if norm in ALWAYS_PRESENT:
        return
    if norm in LOCAL_MODULES:
        return
    rel = str(file.relative_to(WORK_DIR))
    files = imports.setdefault(norm, [])
    if rel not in files:  # 同一文件多次命中只记一次（避免 "start.sh, start.sh"）
        files.append(rel)

for py in WORK_DIR.rglob("*.py"):
    if _is_excluded(py):
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"), filename=str(py))
    except (SyntaxError, OSError):
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add_import(alias.name, py)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # 相对 import: from . / .. import x → 本地包
                continue
            if node.module:
                _add_import(node.module, py)

# ---------- 额外：扫 shell 脚本中的 Python CLI 运行时依赖 ----------
# 动机：gunicorn / uvicorn / celery 等 WSGI/ASGI 服务器和任务队列，业务代码
# 通常**不会** `import gunicorn`，它们只在 start.sh / 子脚本里以命令行形式被
# 调用（`gunicorn --bind 0.0.0.0:3000 app:app`）。如果 requirements.txt 漏写，
# `pip install -r` 不报错，等 Pod 起 start.sh 才 `gunicorn: command not found`。
#
# 覆盖范围（递归，过滤 EXCLUDE_DIRS）：
#   - 所有 *.sh         —— 不限根目录，monorepo / sub-process/start.sh 同样会扫
#
# 本扫描把已知的 Python CLI 工具当作"运行时依赖"，与 .py import 一同做差集。
PYTHON_CLI_DEPS = {
    "gunicorn", "uvicorn", "hypercorn", "daphne",  # WSGI/ASGI servers
    "celery", "flower", "rq",                       # task queues
    "alembic",                                      # DB migration（Guard 禁，但仍检查）
    "flask",                                        # `flask run`
    "django-admin",                                 # 命令名带横线
}

# 用于 `python -m X` 形式：X 也算依赖
PY_DASH_M_DEPS = PYTHON_CLI_DEPS | {"http.server", "venv"}

# `command` (基础名) → pip 包名（少数命令名 ≠ pip 包名时用）
CLI_TO_PKG = {
    "django-admin": "django",
}

def _scan_shell_runtime_deps() -> None:
    """递归扫 *.sh，把已知 Python CLI 工具计入 imports。

    递归是为了覆盖 monorepo / 多子应用结构（如 `sub-process/start.sh`），
    避免根目录 start.sh 没问题但子目录里 `exec gunicorn` 漏过去 → Pod
    报 `gunicorn: not found`。
    """
    cli_pat = re.compile(
        r'(?<![A-Za-z0-9_./-])'                     # 左边不是标识符字符
        r'(?:exec\s+)?'                             # 允许 exec 前缀
        r'(?:[^\s|;&<>"\']*/)?'                     # 允许绝对/相对路径前缀
        r'(' + '|'.join(re.escape(c) for c in PYTHON_CLI_DEPS) + r')'
        r'\b'
    )
    py_dash_m_pat = re.compile(
        r'(?<![A-Za-z0-9_./-])(?:python|python3)\s+-m\s+([A-Za-z_][\w.]*)'
    )

    def _scan_text(text: str, src: Path) -> None:
        """逐行扫文本：抽 CLI 命令 + python -m 形式。"""
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            for m in cli_pat.finditer(line):
                cmd = m.group(1)
                pkg = CLI_TO_PKG.get(cmd, cmd)
                _add_import(pkg, src)
            for m in py_dash_m_pat.finditer(line):
                mod = m.group(1).split(".", 1)[0]
                if mod in PY_DASH_M_DEPS:
                    pkg = CLI_TO_PKG.get(mod, mod)
                    _add_import(pkg, src)

    # 递归 *.sh —— 覆盖 monorepo / 子应用结构（sub-process/start.sh 这类）
    for sh in WORK_DIR.rglob("*.sh"):
        if _is_excluded(sh):
            continue
        try:
            _scan_text(sh.read_text(encoding="utf-8", errors="ignore"), sh)
        except OSError:
            continue


_scan_shell_runtime_deps()

# ---------- 满足性检查 ----------
def _is_satisfied(import_name: str) -> bool:
    """已声明的 DECLARED 集合能否覆盖该 import 名"""
    norm = _normalize(import_name)
    # 1. 直接命中
    if norm in DECLARED:
        return True
    # 2. 别名表
    aliased = ALIASES.get(norm)
    if aliased and _normalize(aliased) in DECLARED:
        return True
    # 3. namespace 前缀豁免：import google → 任何 google-* 都算
    for prefix in NAMESPACE_PREFIXES:
        if norm == prefix or norm.startswith(prefix + "-"):
            for d in DECLARED:
                if d == prefix or d.startswith(prefix + "-"):
                    return True
    # 4. 反向 alias 兜底（被声明 pillow，import 写 PIL）
    for src, dst in ALIASES.items():
        if _normalize(dst) == norm and _normalize(src) in DECLARED:
            return True
    return False

missing: dict[str, list[str]] = {}
for name, files in imports.items():
    if not _is_satisfied(name):
        missing[name] = files

if not missing:
    print("[OK] 所有 Python import 均已在 requirements*.txt 中声明")
    print(f"    扫描了 {len(REQ_FILES)} 个 requirements 文件，{len(DECLARED)} 个已声明包")
    sys.exit(0)

# ---------- 失败报告 ----------
print(f"[FAIL] 发现 {len(missing)} 个第三方 import 未在 requirements*.txt 中声明：", file=sys.stderr)
print(f"    requirements 文件: {[str(p.relative_to(WORK_DIR)) for p in REQ_FILES]}", file=sys.stderr)
print(file=sys.stderr)
for name in sorted(missing):
    files = missing[name]
    files_show = files[:3]
    more = "" if len(files) <= 3 else f" 等 {len(files)} 处"
    suggested = ALIASES.get(name, name)
    # 区分：来源是 .sh shell 命令调用 vs .py 代码 import
    has_sh = any(f.endswith(".sh") for f in files)
    has_py = any(f.endswith(".py") for f in files)
    if has_sh and not has_py:
        source_hint = "在 shell 中以命令调用（CLI 工具）"
    elif has_sh and has_py:
        source_hint = "代码 import + shell 命令调用"
    else:
        source_hint = "代码 import"
    print(f"    - 缺包: {name}", file=sys.stderr)
    print(f"      建议加到 requirements.txt（pip 包名）: {suggested}", file=sys.stderr)
    print(f"      引用来源 ({source_hint}): {', '.join(files_show)}{more}", file=sys.stderr)
print(file=sys.stderr)
print("    修复建议（任选其一）：", file=sys.stderr)
print("      a) 把上述包名加到对应的 requirements.txt（指定版本号）", file=sys.stderr)
print("      b) 若是误报（属本地模块），把所在顶层目录加到 LOCAL_MODULES 排除", file=sys.stderr)
print("      c) 若是 stdlib（罕见的 py3.x 新增模块），升级 verifier", file=sys.stderr)
sys.exit(1)
PY
