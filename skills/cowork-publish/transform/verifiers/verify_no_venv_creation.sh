#!/usr/bin/env bash
# 验证：install.sh / 业务任意 .sh 不得在工程内创建嵌套 .venv（`python3 -m venv ...`）。
#
# ============================================================
# 反转后的设计动机（替代原 verify_venv_activation.sh）
# ============================================================
#   旧规则要求"既然你建了 venv 就必须激活它"——治标不治本，并且引入了一连串问题：
#
#   1. bookworm 镜像 `python3-venv` 单包不带 ensurepip 的 pip wheel
#      （pip 在 python3-pip 包里）；嵌套 `python3 -m venv .venv` 创建出
#      没有 pip 的半成品 venv，install.sh 的 pip install 立刻 not found。
#
#   2. pip 装出来的 console_script（`.venv/bin/gunicorn` 等）shebang 写死
#      创建时刻的 venv python 绝对路径，例如 `#!/home/app/sub-process-next/.venv/bin/python3.11`。
#      guard-rust 启动期会把工程目录 `fs::rename` 到 `releases/<url_key>/`，
#      路径变了但 shebang 不变 → execve ENOENT → start.sh 报
#      `bash: .venv/bin/gunicorn: cannot execute: required file not found`。
#
#   3. `.venv/` 经常被误打进 zip（用户手动打包 / 排除规则没覆盖到非 `.venv` 名字
#      的 venv），把以上问题原封带进 Pod。
#
#   根治方案：完全不在工程内建 venv。Pod 镜像 Dockerfile 已 `ENV PATH=/opt/venv/bin:$PATH`
#   提供全局 venv；install.sh 直接 `python3 -m pip install` 装到 /opt/venv，
#   start.sh 直接 `exec python3 -m gunicorn ...`——绝对路径稳定，不被 rename 影响。
#
# ============================================================
# Skip 条件
# ============================================================
#   - 项目无 *.py 文件（非 Python 项目）
#
# ============================================================
# FAIL 条件（任一 .sh 含创建 venv 的语句）
# ============================================================
#   - `python -m venv <path>` / `python3 -m venv <path>` / `python3.11 -m venv ...`
#   - `virtualenv <path>` / `python -m virtualenv <path>`
#
# 不区分目标路径名（.venv / venv / env / .myenv 都拦），因为它们都会触发
# pip 写绝对路径 shebang + 不被 stage 60 排除（除 .venv 外）。
#
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# ---- Skip：非 Python 项目 ----
HAS_PY=$(find . \
    -type d \( \
        -name '.git' -o -name 'node_modules' -o -name '__pycache__' \
        -o -name '.venv' -o -name 'venv' -o -name '.venv-build-check' \
        -o -name 'dist' -o -name 'build' -o -name '.next' \
        -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \
    \) -prune -o -type f -name '*.py' -print 2>/dev/null \
    | head -1)
if [ -z "$HAS_PY" ]; then
    echo "[OK] 非 Python 项目，skip"
    exit 0
fi

# ---- 收集所有 .sh ----
SH_FILES=$(find . \
    -type d \( \
        -name '.git' -o -name 'node_modules' -o -name '__pycache__' \
        -o -name '.venv' -o -name 'venv' -o -name '.venv-build-check' \
        -o -name 'dist' -o -name 'build' -o -name '.next' \
        -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \
    \) -prune -o -type f -name '*.sh' -print 2>/dev/null \
    | sort)

# venv 创建语句的统一正则：
#   - `python[3[.X]] -m venv <path>` / `python[3[.X]] -m virtualenv <path>`
#   - `virtualenv <path>`（独立 CLI）
# 边界处理：行首或非标识符前缀；末尾要有空白或 `"`/`'` 引号边界，避免误吃 `mvenv` 等。
VENV_CREATE_RE='(^|[^A-Za-z0-9_./-])(python[0-9.]*[[:space:]]+-m[[:space:]]+(venv|virtualenv)|virtualenv)([[:space:]]+|$)'

fail=0
last_file=""
emit_fail() {
    local file="$1" line="$2" cmd="$3"
    if [ "$file" != "$last_file" ]; then
        last_file="$file"
        echo "" >&2
        echo "  [$file]" >&2
    fi
    echo "    第 $line 行: $cmd" >&2
    fail=$((fail+1))
}

for sh in $SH_FILES; do
    rel="${sh#./}"
    # 整行注释剥掉，避免说明文字里写过示例被误判
    line_no=0
    while IFS= read -r raw || [ -n "$raw" ]; do
        line_no=$((line_no+1))
        stripped=$(printf '%s' "$raw" | sed 's/^[[:space:]]*//')
        case "$stripped" in
            ""|"#"*) continue ;;
        esac
        # 行尾注释也剥掉（避免 `# ... python3 -m venv ...` 字符串误命中）
        nocomment=$(printf '%s' "$raw" | sed 's/[[:space:]]#.*$//')
        if echo "$nocomment" | grep -qE "$VENV_CREATE_RE"; then
            emit_fail "$rel" "$line_no" "$stripped"
        fi
    done < "$sh"
done

if [ "$fail" -gt 0 ]; then
    echo "" >&2
    echo "[FAIL] $fail 处 .sh 在工程内创建 venv（python -m venv / virtualenv），违反平台契约" >&2
    echo "" >&2
    echo "  根因：嵌套 venv 会触发三类问题（详见本 verifier 头部注释）：" >&2
    echo "        1) bookworm 镜像缺 python3-pip 时新建 venv 没 pip → install.sh 立刻挂" >&2
    echo "        2) pip 写死绝对路径 shebang → guard-rust rename 工程目录后 execve ENOENT" >&2
    echo "           （现场报：'.venv/bin/gunicorn: cannot execute: required file not found'）" >&2
    echo "        3) .venv/ 被误打进 zip → 把以上问题原封带进 Pod" >&2
    echo "" >&2
    echo "  正确做法：依赖 Pod 镜像已提供的全局 venv（/opt/venv，已在 PATH 上）：" >&2
    echo "" >&2
    echo "    install.sh 装依赖：" >&2
    echo "        python3 -m pip install --no-cache-dir -r requirements.txt" >&2
    echo "" >&2
    echo "    start.sh 启动：" >&2
    echo "        exec python3 -m gunicorn --bind 0.0.0.0:\${APP_PORT} app:app" >&2
    echo "" >&2
    echo "  guard-transform 当前模板（stage 30 渲染）已不再创建 .venv；如果你看到" >&2
    echo "  这条 fail，多半是手改了 install.sh 或工程自带 build/setup 脚本残留。" >&2
    exit 1
fi

echo "[OK] 所有 .sh 均未在工程内创建嵌套 venv（依赖镜像 /opt/venv 全局 venv）"
