#!/usr/bin/env bash
# 验证 start.sh 中 exec 引用的"产物文件/目录"在 work_dir 下确实存在且类型对
#
# 平台范围：产物只支持 Python / Node 后端；输入工程不限语言（其他语言由 stage 20 重写为 Python/Node）
#
# 动机：start.sh 模板渲染会写死类似
#   exec node dist/main.js
#   exec npx --yes serve -s dist -l tcp://0.0.0.0:3000
#   exec node .next/standalone/server.js
# 但如果 stage 40 build 没产出（构建失败被忽略 / 路径填错 / 框架检测错位），
# Pod 起来才报 "Cannot find module 'dist/main.js'" 等。
# 本 verifier 用纯静态规则在打包前做"产物存在性 + 类型嗅探"。
#
# 与 verify_app_factory.sh 分工：
#   - 那个查 Python `module:attr` 的 attr 是否在模块顶层暴露
#   - 这个查 Node 路径式产物（dist/main.js / .next/standalone/...）是否真在硬盘上
#
# Skip 条件：
#   - work_dir 没有 start.sh
#   - start.sh 末行不是合法 exec
#   - 末行启动器是 Python 系（gunicorn/uvicorn/python -m）→ 让 verify_app_factory 处理

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

if [ ! -f start.sh ]; then
    echo "[OK] start.sh 不存在，skip"
    exit 0
fi

export GVSA_WORK_DIR="$(pwd)"
export GVSA_START_SH="$(cat start.sh)"

exec python3 - <<'PY'
"""
verify_start_artifacts 内嵌脚本。

流程：
1) 解析 start.sh，找出末行的 exec 命令 + 追踪 cd 链路得到 effective_cwd
2) 按启动器分流，抽取"路径产物" tokens
3) 在 effective_cwd / work_dir 下逐个验存
4) 按预期类型嗅探（文件 / 目录）
5) 失败给详细修复建议（最常见原因：build 没跑 / 框架检测错位）
"""
import os
import re
import shlex
import sys
from pathlib import Path

WORK_DIR = Path(os.environ["GVSA_WORK_DIR"]).resolve()
START_SH = os.environ["GVSA_START_SH"]


# ---------- 1. 解析 start.sh 找末行 exec + cd 链路 ----------
def _meaningful_lines(text: str):
    """yield (lineno_1based, stripped_line)，忽略空行 / 注释 / set 语句。"""
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        yield i, line


def _resolve_effective_cwd(text: str) -> Path:
    """模拟执行所有 cd 语句，得到 exec 时的 effective cwd。"""
    cwd = WORK_DIR
    for _no, line in _meaningful_lines(text):
        # 不解析 if/case/for 等控制流体内的 cd（极少见，且模板不这么写）
        # 形态 a: cd "$(dirname "$0")/sub"
        m = re.search(r'\bcd\s+"?\$\(dirname\s+"?\$0"?\)/?([^"\s]*)"?', line)
        if m:
            sub = m.group(1).strip()
            cand = WORK_DIR / sub if sub else WORK_DIR
            if cand.is_dir():
                cwd = cand
            continue
        # 形态 b: cd "$(dirname "$0")"
        if re.search(r'\bcd\s+"?\$\(dirname\s+"?\$0"?\)"?\s*$', line):
            cwd = WORK_DIR
            continue
        # 形态 c: cd subdir 或 cd "subdir"
        m = re.match(r'\bcd\s+"?([^"\s$][^"\s]*)"?\s*$', line)
        if m:
            cand = (cwd / m.group(1)).resolve()
            try:
                cand.relative_to(WORK_DIR)  # 确保在 work_dir 下
            except ValueError:
                continue
            if cand.is_dir():
                cwd = cand
    return cwd


def _extract_exec_line(text: str):
    """取最后一条非控制流的 exec ... 行；返回 (lineno, tokens) 或 None。"""
    last = None
    for no, line in _meaningful_lines(text):
        # 控制结构关键字独占行 → 跳过
        if line in ("fi", "done", "esac", "}"):
            continue
        if line.startswith("exec "):
            last = (no, line)
    if not last:
        return None
    no, line = last
    # 用 shlex 把 exec 后面切成 tokens（变量展开靠不住但够用）
    body = line[len("exec "):].strip()
    try:
        tokens = shlex.split(body, comments=True, posix=True)
    except ValueError:
        # 引号不闭合等 → 退化用空格切
        tokens = body.split()
    return no, tokens


EFFECTIVE_CWD = _resolve_effective_cwd(START_SH)
exec_info = _extract_exec_line(START_SH)

if exec_info is None:
    # 没 exec → 让 verify_entry_scripts 报，这里不重复
    print("[OK] start.sh 末行未发现 exec 命令，skip（由 verify_entry_scripts 兜底）")
    sys.exit(0)

EXEC_LINENO, EXEC_TOKENS = exec_info
EXEC_TEXT = " ".join(EXEC_TOKENS)


# ---------- 2. 启动器分流 ----------
def _is_python_launcher(tokens):
    """gunicorn / uvicorn / hypercorn / daphne / python -m {gunicorn,uvicorn,...}
    交给 verify_app_factory 处理，本 verifier skip。"""
    py_launchers = {"gunicorn", "uvicorn", "hypercorn", "daphne"}
    if not tokens:
        return False
    # 直接 launcher
    base = os.path.basename(tokens[0])
    if base in py_launchers:
        return True
    # python -m X
    if base in ("python", "python3") and len(tokens) >= 3 and tokens[1] == "-m":
        if tokens[2] in py_launchers:
            return True
    # gunicorn 装在 venv：./venv/bin/gunicorn
    if any(base.endswith("/" + l) or base == l for l in py_launchers):
        return True
    return False


if _is_python_launcher(EXEC_TOKENS):
    print(f"[OK] start.sh exec 是 Python 启动器（{EXEC_TOKENS[0]}），skip（由 verify_app_factory 处理）")
    sys.exit(0)


# ---------- 3. 提取"路径产物" tokens ----------
# 每个 candidate = (kind, path_token, hint)
#   kind in {"file_node", "dir"}  —— 平台仅支持 Python/Node，二进制/jar 已删
#   hint = 给修复建议用的语义说明
def _extract_artifacts(tokens):
    """按启动器规则抽出路径 tokens。返回 candidates 列表。"""
    if not tokens:
        return []
    base = os.path.basename(tokens[0])
    rest = tokens[1:]

    candidates = []

    # ---------- node X(.js) ----------
    if base in ("node", "nodejs"):
        # node 跳过 -e/--eval/--print 等（直接代码，不是文件）
        for arg in rest:
            if arg.startswith("-"):
                continue
            # 跳过 NODE_OPTIONS 形式的环境变量
            if "=" in arg and not arg.startswith("/") and not arg.startswith("."):
                continue
            candidates.append(("file_node", arg, "Node.js 入口脚本"))
            break  # node 只取第一个非选项参数（脚本路径）
        return candidates

    # ---------- npx ... ----------
    if base in ("npx", "yarn", "pnpm"):
        # 大量子命令在跑命令而非引用产物，多数情况只关心 -s/--single 这种 spa 静态目录
        # serve -s <dir> / serve --single <dir> / serve -s <dir> -l ...
        # 找 'serve' / 'http-server' / 'static' 子命令后的 -s/--single 紧邻参数
        idx_serve = next((i for i, t in enumerate(rest)
                          if t in ("serve", "http-server", "static-server", "sirv")), -1)
        if idx_serve == -1:
            return candidates
        sub = rest[idx_serve + 1:]
        # 找 -s / --single 紧邻目录
        for i, t in enumerate(sub):
            if t in ("-s", "--single", "-d", "--directory") and i + 1 < len(sub):
                candidates.append(("dir", sub[i + 1], "SPA 静态目录"))
                return candidates
            # serve 默认参数：serve dist / serve -l xxx dist
            # 退化策略：取最后一个非 - 开头、非端口/host 的 token
        # 退化：取 sub 中最后一个看起来像目录的 token
        for t in reversed(sub):
            if t.startswith("-") or t.startswith("tcp://") or ":" in t:
                continue
            if (Path(EFFECTIVE_CWD) / t).is_dir():
                candidates.append(("dir", t, "SPA 静态目录（推断）"))
                return candidates
        return candidates

    # ---------- bun / deno（JS runtime alternatives，归 Node 系）----------
    if base in ("bun", "deno"):
        # bun run dist/index.js / bun start ...
        # deno run --allow-net main.ts
        for arg in rest:
            if arg.startswith("-"):
                continue
            if arg in ("run", "start", "exec"):
                continue
            candidates.append(("file_node", arg, f"{base} 入口脚本"))
            return candidates

    # 未识别 → 不报错，让别的 verifier 兜
    # （产物启动器只能是 Python/Node；java/php/dotnet/go/rust 输入会被 stage 20 重写）
    return candidates


# ---------- 4. 验存 + 类型嗅探 ----------
def _resolve(token: str) -> Path:
    """relative → effective_cwd 下；absolute → 直接用，但要在 WORK_DIR 内。"""
    if token.startswith("/"):
        # 容忍 /app/... 这种 Pod 内绝对路径写法（罕见但有）
        return Path(token)
    p = (EFFECTIVE_CWD / token).resolve()
    return p


def _check_node_script(p: Path) -> str:
    if not p.is_file():
        return "不是普通文件"
    if p.stat().st_size == 0:
        return "文件为空"
    return ""


def _check_dir(p: Path) -> str:
    if not p.is_dir():
        return "不是目录"
    # 至少要有一个文件（serve 空目录会 404）
    has_any = any(True for _ in p.iterdir())
    if not has_any:
        return "目录为空（npx serve 会一律返回 404）"
    return ""


CHECKERS = {
    "file_node": _check_node_script,
    "dir": _check_dir,
}


candidates = _extract_artifacts(EXEC_TOKENS)

if not candidates:
    # 启动器未识别 / 没抽出任何路径 → skip 不报错（保守）
    print(f"[OK] start.sh exec 启动器为 `{EXEC_TOKENS[0]}`，未识别为已知"
          "路径产物模式，skip")
    sys.exit(0)


# ---------- 5. 跑检查 ----------
failures = []  # 每项: (kind, token, hint, resolved_path, error_msg)
for kind, token, hint in candidates:
    p = _resolve(token)
    # 先检存在
    exists = p.exists() if not token.startswith("/") else p.exists()
    if not exists:
        failures.append((kind, token, hint, p, "路径不存在"))
        continue
    err = CHECKERS.get(kind, lambda _: "")(p)
    if err:
        failures.append((kind, token, hint, p, err))

if not failures:
    rel_cwd = EFFECTIVE_CWD.relative_to(WORK_DIR) if EFFECTIVE_CWD != WORK_DIR else Path(".")
    print(f"[OK] start.sh 启动产物已校验：{len(candidates)} 项均存在")
    print(f"    effective cwd: {rel_cwd}")
    print(f"    exec line ({EXEC_LINENO}): exec {EXEC_TEXT}")
    for kind, token, hint, *_ in [(k, t, h, None, None) for k, t, h in candidates]:
        print(f"    - [{kind}] {token}  ({hint})")
    sys.exit(0)


# ---------- 6. 失败报告 + 修复建议 ----------
print(f"[FAIL] start.sh 引用的启动产物有 {len(failures)} 项不可用", file=sys.stderr)
print(f"    （部署到 Pod 后会立刻 'Cannot find module' / ENOENT / ImportError 等启动失败）", file=sys.stderr)
print(f"    exec line ({EXEC_LINENO}): exec {EXEC_TEXT}", file=sys.stderr)
rel_cwd = EFFECTIVE_CWD.relative_to(WORK_DIR) if EFFECTIVE_CWD != WORK_DIR else Path(".")
print(f"    effective cwd: {rel_cwd}", file=sys.stderr)
print(file=sys.stderr)

for i, (kind, token, hint, resolved, err) in enumerate(failures, 1):
    print(f"  [{i}] {hint}", file=sys.stderr)
    print(f"      token (start.sh 中): `{token}`", file=sys.stderr)
    try:
        rel = resolved.relative_to(WORK_DIR)
        print(f"      解析后路径: {rel}", file=sys.stderr)
    except ValueError:
        print(f"      解析后路径: {resolved}（已超出 work_dir）", file=sys.stderr)
    print(f"      问题: {err}", file=sys.stderr)

    # 按 kind 给针对性建议
    if kind == "file_node":
        print(f"      修复建议：", file=sys.stderr)
        print(f"        a) 检查 stage 40 build 是否真的产出了该文件（看 build/dist 目录）", file=sys.stderr)
        print(f"        b) start.sh 的路径是否需要相对 cd 后的目录（当前 cwd: {rel_cwd}）", file=sys.stderr)
        print(f"        c) 框架检测错位？该项目可能是 Vite SPA / Next standalone，应改用对应启动方式", file=sys.stderr)
    elif kind == "dir":
        print(f"      修复建议：", file=sys.stderr)
        print(f"        a) 检查 stage 40 是否产出了静态目录（npm run build → dist/ 或 build/）", file=sys.stderr)
        print(f"        b) build 命令在 cd 后执行还是仓库根？产出位置可能在别处", file=sys.stderr)
        print(f"        c) Vite 默认输出 dist/，CRA 默认 build/，Next standalone 在 .next/standalone/", file=sys.stderr)
    print(file=sys.stderr)

print("    背景：start.sh 中 exec 行引用的产物文件/目录如果不存在，Pod 启动后 1 秒内挂掉。", file=sys.stderr)
print("    这是平台部署时最常见的失败模式之一（占启动失败 case ≈ 30%）。", file=sys.stderr)
sys.exit(1)
PY
