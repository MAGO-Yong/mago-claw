#!/usr/bin/env bash
# 验证：主服务内启动「子服务/子进程」时的父子生命周期管理
#
# 背景（必读）：
#   guard / cowork 平台子应用跑在共享 Pod 里。业务常见反模式是主服务
#   spawn / fork 一个常驻子进程（python 推理 / node sidecar / ffmpeg
#   server / langgraph dev / sandbox runtime …），子进程自己 listen 一
#   个额外端口。这种场景下必须保证：
#
#     主进程被 kill 时，子进程一并销毁
#       - 否则子进程变孤儿（PPID=1），继续占住端口；
#       - 下次 Pod restart 主服务起来后，老子进程还在 → EADDRINUSE；
#       - 平台 OOM-killer 触发时只杀主进程不杀子进程 → 内存泄漏雪崩。
#
#   补充说明：
#     - 子进程端口号选择：业务自己负责，不在本 verifier 检测范围
#       （静态扫描端口字面量假阳性高，统一交业务和 LLM 自行判断）
#
# 拦截目标：
#   ❌ spawn(..., { detached: true })  或 child.unref() (Node)        → fail
#      （明确让子进程脱离父进程组，父进程死时不会带走子进程）
#   ❌ subprocess.Popen(..., start_new_session=True)        (Python)  → fail
#   ❌ subprocess.Popen(..., preexec_fn=os.setsid)          (Python)  → fail
#      （等价语义，父退出时子进程不被 SIGHUP）
#   ⚠️  父文件里有 spawn/fork/Popen，但找不到 SIGTERM/SIGINT 信号
#      处理 / atexit / process.on('exit') 等清理钩子                  → warn
#      （提示业务务必显式给子进程发 kill，让主进程退出前清理子进程）
#
# Skip 条件：
#   - 无 Node / Python 源码                  → 直接 OK
#   - 源码里完全没有 spawn/fork/Popen/exec   → OK（无子进程场景）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

export GVSP_WORK_DIR="$(pwd)"

exec python3 - <<'PY'
"""扫源码寻找：
  1) 启动「常驻」子进程的调用位点（Node: spawn/fork/execFile；Python: Popen/Process）
  2) detached:true / start_new_session=True / preexec_fn=os.setsid / child.unref()
     等明确脱离父进程组的反模式 → fail
  3) 启动子进程的源文件里是否有信号 / atexit 钩子 → 缺失 → warn

判定边界：
  - 排除 node_modules / dist / build / .next / .nuxt / .output / coverage / tmp / .git / __pycache__ / .venv / venv
  - 排除测试文件 *.test.* / *.spec.* / __tests__/ / tests/
  - 跳过纯注释行
  - detached 反例必须 ±10 行内有真实 spawn 调用才升级为 fail（防 docstring 伪代码误报）
"""
import os
import re
import sys
from pathlib import Path

WORK = Path(os.environ["GVSP_WORK_DIR"]).resolve()

EXCLUDE_DIRS = {
    "node_modules", ".next", ".nuxt", "dist", "build", "out",
    ".svelte-kit", ".output", ".guard-transform", ".git",
    "coverage", ".cache", ".turbo", ".vercel", "tmp",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode",
}
NODE_EXTS = (".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx")
PY_EXTS = (".py",)
ALL_EXTS = NODE_EXTS + PY_EXTS

# 子进程启动调用（Node）
NODE_SPAWN_RE = re.compile(
    r'\b(?:child_process\s*\.\s*)?'
    r'(spawn|fork|execFile|exec)\s*\('
)
NODE_DETACHED_RE = re.compile(r'\bdetached\s*:\s*true\b')
NODE_UNREF_RE = re.compile(r'\.\s*unref\s*\(\s*\)')

# 子进程启动调用（Python）
# 必须带 subprocess. 前缀，或裸 Popen(；裸 run(/call( 误报太严重（任何 def run() 都中招）
PY_POPEN_RE = re.compile(
    r'\bsubprocess\s*\.\s*(?:Popen|run|call|check_output|check_call|getoutput|getstatusoutput)\s*\('
    r'|(?<![\w.])Popen\s*\('
)
PY_NEW_SESSION_RE = re.compile(r'\bstart_new_session\s*=\s*True\b')
PY_PREEXEC_SETSID_RE = re.compile(r'\bpreexec_fn\s*=\s*os\.setsid\b')
# os.fork / os.execvp / multiprocessing.Process（也算子进程）
PY_OS_FORK_RE = re.compile(r'\bos\.fork\s*\(\s*\)')
PY_MP_PROCESS_RE = re.compile(r'\bmultiprocessing\s*\.\s*Process\s*\(')

# 信号 / 退出钩子（任一即视为「有桥接」）
# 放宽：只要文件里出现 SIGINT/SIGTERM 标识符（无论是字面量字符串还是循环
# 变量名），或 atexit / process.on('exit'|'beforeExit') / enableShutdownHooks，
# 就算父进程有「信号意识」。
# 假阳性容忍：本检测只决定 warn 是否输出，不决定 fail（fail 由 detached 反例驱动）。
SIGNAL_HOOK_RE = re.compile(
    r"\b(?:SIGINT|SIGTERM|SIGHUP)\b"
    r"|process\s*\.\s*on\s*\(\s*['\"](?:exit|beforeExit)['\"]"
    r"|\batexit\s*\.\s*register\s*\("
    r"|enableShutdownHooks\s*\("
)


def iter_src():
    for root, dirs, files in os.walk(WORK):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(ALL_EXTS):
                continue
            if (".test." in f) or (".spec." in f):
                continue
            p = Path(root) / f
            posix = p.as_posix()
            if "/__tests__/" in posix or "/test/" in posix or "/tests/" in posix:
                continue
            yield p


def is_comment_line(line: str, is_python: bool) -> bool:
    s = line.lstrip()
    if is_python:
        return s.startswith("#")
    return s.startswith("//") or s.startswith("*") or s.startswith("/*")


detached_hits = []           # [(rel, lineno, snippet, mode)]
parents_no_signal = []       # [(rel, lineno, snippet, lang)]  -- warn

# 「近邻 spawn」窗口大小：detached/setsid/unref 反例只在 ±N 行有真正 spawn
# 调用时才升级为 fail，否则视为文档/字符串字面量误报，降级为 warn 丢弃
SPAWN_NEIGHBOR_WINDOW = 10


def _has_spawn_near(spawn_lines: set[int], lineno: int) -> bool:
    """判定 lineno ±SPAWN_NEIGHBOR_WINDOW 行内是否有真实 spawn 调用。"""
    for delta in range(-SPAWN_NEIGHBOR_WINDOW, SPAWN_NEIGHBOR_WINDOW + 1):
        if (lineno + delta) in spawn_lines:
            return True
    return False


for f in iter_src():
    rel = f.relative_to(WORK).as_posix()
    is_py = f.suffix == ".py"
    try:
        text = f.read_text(errors="replace")
    except OSError:
        continue

    lines = text.splitlines()

    # 文件级：是否有信号/退出钩子（影响 warn 判定）
    has_signal_hook = bool(SIGNAL_HOOK_RE.search(text))

    file_has_spawn = False
    spawn_linenos: set[int] = set()  # 本文件所有真实 spawn 调用的行号
    pending_detached: list[tuple[int, str, str]] = []  # 暂存待护栏校验

    for lineno, line in enumerate(lines, start=1):
        if is_comment_line(line, is_py):
            continue

        # ---- 收集 spawn 调用 + detached 候选（后面用近邻护栏过滤）----
        if not is_py:
            if NODE_DETACHED_RE.search(line):
                pending_detached.append((lineno, line.strip(), "Node detached:true"))
            if NODE_UNREF_RE.search(line):
                pending_detached.append((lineno, line.strip(), "Node child.unref()"))
            if NODE_SPAWN_RE.search(line):
                file_has_spawn = True
                spawn_linenos.add(lineno)
        else:
            if PY_NEW_SESSION_RE.search(line):
                pending_detached.append(
                    (lineno, line.strip(), "Python start_new_session=True")
                )
            if PY_PREEXEC_SETSID_RE.search(line):
                pending_detached.append(
                    (lineno, line.strip(), "Python preexec_fn=os.setsid")
                )
            if (PY_POPEN_RE.search(line)
                    or PY_OS_FORK_RE.search(line)
                    or PY_MP_PROCESS_RE.search(line)):
                file_has_spawn = True
                spawn_linenos.add(lineno)

    # ---- 用近邻护栏过滤 detached：必须 ±N 行内有真实 spawn 调用才算 fail
    #      （挡掉 docstring / 字符串字面量里的 start_new_session=True 等伪代码）
    for lineno, snip, mode in pending_detached:
        if _has_spawn_near(spawn_linenos, lineno):
            detached_hits.append((rel, lineno, snip, mode))

    # ---- 父文件有 spawn 但无任何信号/atexit 钩子 → warn ----
    if file_has_spawn and not has_signal_hook:
        first_spawn = min(spawn_linenos)
        first_line = lines[first_spawn - 1].strip()
        parents_no_signal.append(
            (rel, first_spawn, first_line, "python" if is_py else "node")
        )


# ---- 输出 ----
fail = 0

if detached_hits:
    print(
        f"[FAIL] 检测到 {len(detached_hits)} 处「让子进程脱离父进程组」反模式"
        " —— 父进程被 kill 时子进程会变孤儿（PPID=1）继续占端口，"
        "导致下次重启 EADDRINUSE / 内存泄漏不被回收",
        file=sys.stderr,
    )
    for rel, lineno, snip, mode in detached_hits[:10]:
        print(f"    [{mode}] {rel}:{lineno}", file=sys.stderr)
        print(f"      | {snip[:200]}", file=sys.stderr)
    if len(detached_hits) > 10:
        print(f"    ... 余 {len(detached_hits) - 10} 处省略", file=sys.stderr)
    print("", file=sys.stderr)
    fail += 1

if parents_no_signal:
    print(
        f"[WARN] {len(parents_no_signal)} 个文件里启动了子进程，"
        "但同文件没找到任何 SIGTERM/SIGINT/atexit/process.on('exit') 钩子"
        "—— 主进程 kill 时无法主动 kill 子进程",
        file=sys.stderr,
    )
    for rel, lineno, snip, lang in parents_no_signal[:10]:
        print(f"    [{lang}] {rel}:{lineno}", file=sys.stderr)
        print(f"      | {snip[:200]}", file=sys.stderr)
    if len(parents_no_signal) > 10:
        print(f"    ... 余 {len(parents_no_signal) - 10} 处省略", file=sys.stderr)
    print("", file=sys.stderr)


if fail:
    print("修复建议（按推荐顺序）：", file=sys.stderr)
    print(
        "  1. 父进程必须接管 SIGTERM/SIGINT 把信号转发给子进程：",
        file=sys.stderr,
    )
    print("       Node:",
          file=sys.stderr)
    print("         const child = spawn(...)            // ★ 不要 detached:true / 不要 child.unref()",
          file=sys.stderr)
    print("         for (const sig of ['SIGINT','SIGTERM']) {",
          file=sys.stderr)
    print("           process.on(sig, () => { child.kill(sig); process.exit(0) })",
          file=sys.stderr)
    print("         }",
          file=sys.stderr)
    print("       Python:",
          file=sys.stderr)
    print("         proc = subprocess.Popen(...)        # ★ 不要 start_new_session=True / preexec_fn=os.setsid",
          file=sys.stderr)
    print("         import atexit, signal",
          file=sys.stderr)
    print("         atexit.register(lambda: proc.terminate())",
          file=sys.stderr)
    print("         for s in (signal.SIGINT, signal.SIGTERM):",
          file=sys.stderr)
    print("             signal.signal(s, lambda *_: (proc.terminate(), sys.exit(0)))",
          file=sys.stderr)
    print(
        "  2. ★ 强烈推荐：把「子服务」从业务代码里拆出去，直接塞进主进程同端口路由。"
        "子进程在云端 Pod 里的生存复杂度远高于本地开发，能不起最好不起。",
        file=sys.stderr,
    )
    sys.exit(1)

# 没有任何 fail：根据 warn 出最终状态
if parents_no_signal:
    print(f"[OK] 父子进程组合规；但有 {len(parents_no_signal)} 处子进程启动缺信号钩子（仅 warn，请人工确认）")
else:
    print("[OK] 未发现父子生命周期管理问题")
PY
