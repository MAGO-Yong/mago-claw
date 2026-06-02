#!/usr/bin/env bash
# 用 LLM 对 start.sh / install.sh / health.sh 做综合可运行性 review
#
# 与其他 verifier 的差异：
#   - 其他 verifier 是纯规则；本 verifier 调 LLM 做"语义级跨文件 review"
#   - 默认 skip！必须 export GUARD_LLM_VERIFY=1 才启用（避免每次烧 token + 10-30s）
#   - read-only：跑完强制 git checkout . 撤销任何 LLM 意外改动
#
# 与 verify_start_artifacts.sh 的分工：
#   - verify_start_artifacts.sh：纯规则，毫秒级，0 成本，覆盖 80% 常见 case
#   - verify_start_sh_llm.sh：LLM，秒级 + 烧 token，覆盖发散场景（框架检测错位 /
#     install→start 产物链路断裂 / 框架 + 端口 + health 跨文件不一致）
#
# 启用条件（任一不满足 → skip 不阻塞）：
#   - GUARD_LLM_VERIFY=1
#   - 找到 guardx 模块
#   - LLM CLI 可用且未 SKIP_LLM=1
#   - work_dir 有 start.sh
#
# 退出码：0=OK 或 skip；1=LLM 报告 ok=false（含 error 级问题）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

# ---- 1. 默认 skip 闸 ----
if [ "${GUARD_LLM_VERIFY:-0}" != "1" ]; then
    echo "[OK] GUARD_LLM_VERIFY!=1，skip（设 GUARD_LLM_VERIFY=1 启用 LLM 综合 review）"
    exit 0
fi

# ---- 2. 推断 GUARD_TRANSFORM_HOME ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD_HOME="${GUARD_TRANSFORM_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if [ ! -d "$GUARD_HOME/guardx" ]; then
    echo "[OK] 找不到 guardx 模块（GUARD_TRANSFORM_HOME=$GUARD_HOME），skip" >&2
    exit 0
fi

# ---- 3. 必要文件检查 ----
if [ ! -f "$WORK_DIR/start.sh" ]; then
    echo "[OK] start.sh 不存在，skip"
    exit 0
fi

export GVSL_WORK_DIR="$(cd "$WORK_DIR" && pwd)"
export GVSL_GUARD_HOME="$GUARD_HOME"

exec python3 - <<'PY'
"""
verify_start_sh_llm 内嵌脚本。

read-only 三重保险：
  1) prompt 头部强约束"禁止修改文件"
  2) 跑前用 git stash --keep-index --include-untracked 锁住基线
  3) 跑后强制 git checkout . + 清理 untracked，硬撤销任何意外改动
     （即使 LLM 真的改了，对外也表现为 read-only）
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORK_DIR = Path(os.environ["GVSL_WORK_DIR"]).resolve()
GUARD_HOME = Path(os.environ["GVSL_GUARD_HOME"]).resolve()

# 让 guardx 包可导入
sys.path.insert(0, str(GUARD_HOME))

try:
    from guardx import llm as guardx_llm
except Exception as e:  # noqa: BLE001
    print(f"[OK] guardx 模块导入失败：{e}，skip", file=sys.stderr)
    sys.exit(0)


# ---- LLM 配置：缩短 timeout，禁掉自动 SKIP ----
# LLMConfig 在收到非法 GUARD_LLM 时会 log.die（直接 sys.exit）；verifier 要容错。
try:
    cfg = guardx_llm.LLMConfig()
except SystemExit:
    print(f"[OK] GUARD_LLM={os.environ.get('GUARD_LLM','')} 非法，skip", file=sys.stderr)
    sys.exit(0)
cfg.timeout = int(os.environ.get("GUARD_LLM_VERIFY_TIMEOUT", "180"))

if cfg.skip_llm:
    print("[OK] SKIP_LLM=1，skip", file=sys.stderr)
    sys.exit(0)

if not cfg.available():
    print(f"[OK] LLM 后端 '{cfg.backend}' CLI 不可用，skip", file=sys.stderr)
    sys.exit(0)


# ---- 收集上下文 ----
NOISE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".venv-build-check",
    "dist-cache", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
}


def _read(p: Path, line_limit: int = 300, byte_limit: int = 12000) -> str | None:
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return None
    if len(text) > byte_limit:
        text = text[:byte_limit] + f"\n... (truncated, total {len(text)} bytes)"
    lines = text.splitlines()
    if len(lines) > line_limit:
        return "\n".join(lines[:line_limit]) + f"\n... (truncated, total {len(lines)} lines)"
    return text


def _ls(d: Path, depth: int = 2, max_entries: int = 200) -> str:
    out = []
    base_depth = len(d.parts)
    for root, dirs, files in os.walk(d):
        rel = Path(root).relative_to(d)
        d_depth = 0 if str(rel) == "." else len(rel.parts)
        # 砍噪音目录
        dirs[:] = [x for x in dirs if x not in NOISE_DIRS and not x.startswith(".guard-transform-")]
        if d_depth > depth:
            dirs[:] = []
            continue
        for f in files:
            entry = (rel / f).as_posix() if str(rel) != "." else f
            out.append(entry)
        if len(out) > max_entries * 2:
            break
    out = sorted(out)[:max_entries]
    return "\n".join(out)


ctx_parts: list[str] = ["# Guard 子应用启动配置 review 上下文\n"]

for fn in ("start.sh", "install.sh", "health.sh"):
    body = _read(WORK_DIR / fn)
    if body is not None:
        ctx_parts.append(f"\n## `{fn}`\n```bash\n{body}\n```\n")

# 业务侧关键配置（按存在情况附）
# 输入工程不限语言：原工程文件（pom.xml/Cargo.toml/go.mod 等）即使存在也保留给 LLM
# 看见，便于判断"原工程是 Java/Rust/Go，转写为 Python/Node 产物"是否合理；
# 产物配置（package.json/requirements.txt 等）由 LLM 校验产物链路。
for fn in (
    # —— 产物配置（必须存在的目标语言配置）——
    "package.json", "requirements.txt", "pyproject.toml",
    "next.config.js", "next.config.mjs", "vite.config.ts", "vite.config.js",
    "deploy.yaml",
    # —— 原工程残留配置（用于让 LLM 看见原工程上下文）——
    "pom.xml", "build.gradle", "build.gradle.kts",
    "Cargo.toml", "go.mod",
):
    body = _read(WORK_DIR / fn, line_limit=120)
    if body is not None:
        ctx_parts.append(f"\n## `{fn}`\n```\n{body}\n```\n")

# 关键产物目录（如已构建）
# 注：target/ 是 Java/Rust 中间产物——产物中**不应**保留，但若被 LLM 看见可作"残留"信号
for d in ("dist", "build", ".next", "out", "public", "target"):
    p = WORK_DIR / d
    if p.is_dir():
        listing = _ls(p, depth=2, max_entries=80)
        if listing:
            ctx_parts.append(f"\n## ls `{d}/` (depth=2)\n```\n{listing}\n```\n")

# 顶层
ctx_parts.append(f"\n## ls work_dir (top level, depth=1)\n```\n{_ls(WORK_DIR, depth=1, max_entries=200)}\n```\n")

CONTEXT = "".join(ctx_parts)


# ---- prompt ----
PROMPT_TPL = """你是 Guard 平台子应用部署专家。请对下方提供的 Guard 子应用启动配置做**静态可运行性 review**。

# 【绝对约束】（违反将被认为评测失败）
1. **read-only**：禁止修改、创建、删除任何文件；禁止运行任何命令、不要 build 或 install。
2. **只能输出 JSON**：你最终的有效产出 = 标准输出末尾的一段 JSON 块（用 ```json ... ``` 围起来），且只能有一个 JSON 块。

# 【检查重点】
1. **产物链路衔接**：install.sh 解出来 / 拷贝到位的产物 → start.sh 中 exec 引用的路径，是否首尾相接？是否有"start.sh exec 一个根本没人放进去的文件"？
2. **框架检测错位**（产物只能是 Python/Node 启动器）：例如代码看起来是 Vite SPA，start.sh 却用 `node dist/main.js`；或者明明是 Next.js standalone，却没用 `.next/standalone/server.js`；或者 Python 项目用了 `python app.py` 而不是 gunicorn/uvicorn 工厂模式；**绝对禁止**产物 start.sh 出现 `java -jar`、`./bin/server`、`go run`、`cargo run` 等非 Python/Node 启动器（说明 stage 20 没有完成转写）。
3. **端口与 health**：start.sh 必须 listen `0.0.0.0:3000`；health.sh 必须探测 `127.0.0.1:3000/health` 或 `/healthz`；不能用 0.0.0.0 当探测目标。
4. **shebang / set -e / exec**：start.sh 末行必须 exec 前台启动；install.sh 不能跑 build。
5. **跨文件一致性**：package.json scripts.start vs start.sh / next.config.js output:'standalone' 与 start.sh 是否匹配 / requirements.txt 中的 ASGI server（gunicorn/uvicorn/hypercorn）vs start.sh 实际启动器；如果 work_dir 还残留 `pom.xml`/`Cargo.toml`/`go.mod` 但 start.sh 已转为 Python/Node，要确认产物里**没**残留 `target/`、`*.jar`、Go/Rust 编译产物（应在 install.sh 中清理）。
6. **Pod 限制**：禁止外部基础设施（Redis、MQ、S3）；禁止依赖公网包安装；不能用 SQLite 等文件 DB。

# 【输出 JSON 格式】（严格遵守）
```json
{
  "ok": true,
  "summary": "一句话总体结论（中文）",
  "issues": [
    {
      "severity": "error",
      "category": "missing_artifact",
      "where": "start.sh L7",
      "message": "问题描述",
      "fix": "建议怎么改（具体到代码改动）"
    }
  ]
}
```

字段约定：
- `ok`：布尔；只要 issues 中有一条 severity="error" → ok=false
- `severity`："error"（阻塞，会让 verifier 失败） / "warn"（不阻塞，只是建议）
- `category`：枚举 missing_artifact | framework_mismatch | port | health | install_chain | shebang | external_infra | other
- `where`：定位（文件名 + 行号 / 段落）
- `fix`：必须给出建议改法，不能只描述问题

无任何问题时：`{"ok": true, "summary": "...", "issues": []}`

---

# 子应用上下文

""" + CONTEXT


# ---- read-only 兜底：用 stash 锁基线 ----
# 设计：跑 LLM 前如果 work tree 有任何变更，先 stash --include-untracked 走，
#       跑完先 git checkout . + 删 untracked（撤销 LLM 任何意外改动），
#       再 stash pop 回填基线。这样既硬撤销 LLM，又不破坏用户原有未提交改动。
HAS_GIT = (WORK_DIR / ".git").is_dir()


def _git_run(*args):
    return subprocess.run(
        ["git", *args],
        cwd=WORK_DIR,
        capture_output=True,
        text=True,
    )


def _stash_baseline() -> bool:
    """非空时 stash 走基线，返回是否真的 stash 了东西。"""
    if not HAS_GIT:
        return False
    r = _git_run("status", "--porcelain")
    if not r.stdout.strip():
        return False
    r = _git_run(
        "stash", "push", "--include-untracked", "--quiet",
        "-m", "guard-llm-verify-start-baseline",
    )
    return r.returncode == 0


def _restore_readonly(stashed: bool):
    """硬撤销 LLM 在 work_dir 的任何改动 + 把基线 stash 还原。"""
    if not HAS_GIT:
        return
    # 1) 撤销 tracked 文件改动（LLM 改的）
    _git_run("checkout", "--", ".")
    # 2) 删 LLM 留下的所有 untracked（基线已 stash 走，这些必为 LLM 新增）
    r = _git_run("ls-files", "--others", "--exclude-standard")
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            f = line.strip()
            if not f:
                continue
            p = WORK_DIR / f
            try:
                if p.is_file() or p.is_symlink():
                    p.unlink()
            except OSError:
                pass
    # 3) pop 回基线
    if stashed:
        pop_result = _git_run("stash", "pop", "--quiet")
        if pop_result.returncode != 0:
            print(
                f"[WARN] stash pop 失败，基线变更仍在 stash 中（可手动 git stash pop 还原）: "
                f"{pop_result.stderr.strip()}",
                file=sys.stderr,
            )


baseline_stashed = _stash_baseline()


# ---- 跑 LLM ----
state_dir = Path(tempfile.mkdtemp(prefix="guard-llm-verify-start-"))
prompt_file = state_dir / "prompt.md"
prompt_file.write_text(PROMPT_TPL)

print(f"[INFO] LLM start.sh review 开始 (backend={cfg.backend}, timeout={cfg.timeout}s)...", file=sys.stderr)
print(f"    work_dir: {WORK_DIR}", file=sys.stderr)
print(f"    prompt: {prompt_file}", file=sys.stderr)

try:
    result = guardx_llm.call(
        prompt_file, WORK_DIR, state_dir,
        cfg=cfg,
        log_label="verify-start-llm",
    )
finally:
    # 不管成败：硬撤销 LLM 任何改动 + 还原基线
    _restore_readonly(baseline_stashed)


def _cleanup():
    shutil.rmtree(state_dir, ignore_errors=True)


# ---- LLM 调用层失败：不阻塞 ----
if not result.ok:
    print(f"[WARN] LLM 调用失败 (rc={result.returncode}, timed_out={getattr(result, 'timed_out', False)})", file=sys.stderr)
    print("    不阻塞流水线（LLM 是辅助检查，纯规则 verifier 已覆盖核心场景）", file=sys.stderr)
    _cleanup()
    sys.exit(0)

# ---- 读 LLM 输出 ----
log_text = ""
if result.log_path and result.log_path.is_file():
    log_text = result.log_path.read_text(errors="ignore")

if not log_text:
    print("[WARN] LLM 输出为空，跳过校验", file=sys.stderr)
    _cleanup()
    sys.exit(0)


# ---- 抽 JSON 块（取最后一个，避免 prompt 中的示例被误抓） ----
def _extract_json(text: str) -> dict | None:
    # 1) ```json ... ``` 围栏：取最后一个
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if blocks:
        for b in reversed(blocks):
            try:
                return json.loads(b)
            except json.JSONDecodeError:
                continue
    # 2) 裸 JSON：从末尾向前找 { 平衡
    end = len(text)
    while True:
        idx = text.rfind('"ok"', 0, end)
        if idx < 0:
            return None
        # 向前找最近的 {
        start = text.rfind("{", 0, idx)
        if start < 0:
            return None
        # 向后找匹配的 }
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        end = start
    return None


report = _extract_json(log_text)
if report is None:
    print("[WARN] LLM 未输出可解析的 JSON 报告，跳过校验", file=sys.stderr)
    print(f"    LLM 日志路径: {result.log_path}", file=sys.stderr)
    print(f"    日志末尾 600 字:", file=sys.stderr)
    for line in log_text[-600:].splitlines():
        print(f"      {line}", file=sys.stderr)
    _cleanup()
    sys.exit(0)


# ---- 解析报告 ----
ok = bool(report.get("ok", True))
summary = str(report.get("summary", "")).strip() or "(LLM 未给 summary)"
issues = report.get("issues") or []
if not isinstance(issues, list):
    issues = []

errors = [i for i in issues if str(i.get("severity", "")).lower() == "error"]
warns = [i for i in issues if str(i.get("severity", "")).lower() == "warn"]

# 留个 LLM 报告副本到 /tmp，方便人工审
report_copy = Path(tempfile.gettempdir()) / "guard-llm-verify-start-last.json"
try:
    report_copy.write_text(json.dumps(report, indent=2, ensure_ascii=False))
except OSError:
    pass

_cleanup()


# ---- 决策 ----
if ok and not errors:
    print(f"[OK] LLM start.sh review 通过：{summary}")
    if warns:
        print(f"    （另有 {len(warns)} 个 warn 不阻塞）")
        for w in warns[:5]:
            print(f"    - [warn] {w.get('where','?')}: {w.get('message','')}")
    print(f"    LLM 报告已存：{report_copy}")
    sys.exit(0)


# FAIL
print(f"[FAIL] LLM start.sh review 不通过：{summary}", file=sys.stderr)
print(f"    error={len(errors)}  warn={len(warns)}", file=sys.stderr)
print(f"    LLM 报告：{report_copy}", file=sys.stderr)
print(file=sys.stderr)

for i, e in enumerate(errors, 1):
    print(f"  [{i}] [{e.get('category','?')}] {e.get('where','?')}", file=sys.stderr)
    print(f"      问题: {e.get('message','')}", file=sys.stderr)
    print(f"      建议: {e.get('fix','')}", file=sys.stderr)
    print(file=sys.stderr)

for j, w in enumerate(warns, 1):
    print(f"  [warn-{j}] [{w.get('category','?')}] {w.get('where','?')}: {w.get('message','')}", file=sys.stderr)

sys.exit(1)
PY
