#!/usr/bin/env bash
# 验证：所有调用 venv-installed Python CLI（gunicorn/uvicorn/celery 等）的 .sh
# 必须在同文件内激活 venv（. .venv/bin/activate），或使用 .venv/bin/X 绝对路径。
#
# ============================================================
# 动机（真实 bug 复盘）
# ============================================================
#   Guard runner 日志：
#     /home/app/sub-process/start.sh: line 16: exec: gunicorn: not found
#   排查路径：
#     1. requirements.txt 里其实写了 gunicorn ✓
#     2. install.sh 走 `python3 -m venv .venv && pip install -r requirements.txt`，
#        gunicorn 被装到了 `.venv/bin/gunicorn`，不在系统 PATH
#     3. 业务自己写的 sub-process/start.sh 没 `. .venv/bin/activate`，
#        也没用 `.venv/bin/gunicorn` 绝对路径，Guard runner 起这些 .sh 时
#        PATH 里只有系统 python3，命令名直接解析失败
#   guard-transform 模板渲染的根目录 start.sh 由 stage_30 注入了 venv 激活
#   （TPL_VENV_ACTIVATE），所以本身没问题；但业务**手写**的其他 .sh
#   (子进程脚本 / install hook / 自定义启动器) 不在模板控制内，必须静态拦截。
#
# ============================================================
# Skip 条件（任一满足）
# ============================================================
#   - 非 Python 项目（没有 .py 文件）
#   - install.sh 不创建 venv（依赖装到系统 site-packages，PATH 自带，无此风险）
#
# ============================================================
# 合法形式（任一满足，逐文件判定）
# ============================================================
#   1) 文件内出现 `. .venv/bin/activate` / `source .venv/bin/activate`
#      （前缀路径任意，支持 `../.venv/bin/activate` / `/home/app/.venv/bin/activate`）
#   2) 文件内出现 `PATH=.../.venv/bin...`（手动注入 PATH）
#   3) 命令带 `.venv/bin/X` 或 `venv/bin/X` 路径前缀（绝对调用，不依赖 PATH）
#
# 不合法（FAIL）示例
# ============================================================
#   exec gunicorn -b 0.0.0.0:3000 main:app    # 裸命令，无 PATH 支撑
#   exec python -m uvicorn main:app           # python 是系统 python，找不到 uvicorn 模块
#   exec celery -A tasks worker               # 同上
#
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# ---- Skip 1：非 Python 项目 ----
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

# ---- Skip 2：install.sh 不用 venv ----
# 用法：install.sh 里若没有 `python3 -m venv .venv` 这类创建 venv 的语句，
# 说明依赖最终落到系统 site-packages（pip --user / root pip install），
# 此时 PATH 里有 system python 的 bin，gunicorn/uvicorn 可直接被找到，本检查无意义。
if [ ! -f install.sh ] || ! grep -qE '\b(python|python3)[[:space:]]+-m[[:space:]]+venv\b' install.sh; then
    echo "[OK] install.sh 未创建 venv（依赖装系统 site-packages），skip"
    exit 0
fi

# Python CLI 工具（与 verify_python_requirements.sh 的 PYTHON_CLI_DEPS 保持一致）
CLI_RE='(gunicorn|uvicorn|hypercorn|daphne|celery|flower|rq|alembic|flask|django-admin)'

# ---- 递归收集所有 .sh（避开 EXCLUDE_DIRS）----
SH_FILES=$(find . \
    -type d \( \
        -name '.git' -o -name 'node_modules' -o -name '__pycache__' \
        -o -name '.venv' -o -name 'venv' -o -name '.venv-build-check' \
        -o -name 'dist' -o -name 'build' -o -name '.next' \
        -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \
    \) -prune -o -type f -name '*.sh' -print 2>/dev/null \
    | sort)

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

# venv 激活痕迹的统一判定（同文件级判定，避免每行 grep 一次拖慢）
file_has_activation() {
    local f="$1"
    # 先剥掉「整行注释」（首列只含空白后跟 `#` 的行），避免
    # 注释里写 `# 提示：可以 . .venv/bin/activate` 被当成真激活。
    # 行尾注释（命令 + ` # xxx`）较罕见且即便误判风险也低，不做处理。
    local nocomment
    nocomment=$(sed 's/^[[:space:]]*#.*$//' "$f")

    # 形式 1：`. /path/.venv/bin/activate` / `source /path/.venv/bin/activate`
    #   - 左边界：行首或空白/分号/&&/||
    #   - 中间允许：`. ` 或 `source `
    #   - 路径允许：相对或绝对，最终段 `.venv/bin/activate` 或 `venv/bin/activate`
    #   - 右边界：词边界（任何非 alnum/_ 的字符，含 `"` `'` 空白 EOL）
    #     —— guard 模板渲染产物会写 `. ".venv/bin/activate"`（带引号），要兼容
    if printf '%s\n' "$nocomment" | grep -qE '(^|[[:space:]]|[;&|])(\.|source)[[:space:]]+[^[:space:];|&]*[/.]?v?env/bin/activate([^A-Za-z0-9_]|$)'; then
        return 0
    fi
    # 形式 2：PATH=.../.venv/bin... （含 export PATH）
    if printf '%s\n' "$nocomment" | grep -qE 'PATH=.*[/.]v?env/bin'; then
        return 0
    fi
    return 1
}

for sh in $SH_FILES; do
    rel="${sh#./}"

    # 同文件已激活 → 整文件豁免
    if file_has_activation "$sh"; then
        continue
    fi

    line_no=0
    while IFS= read -r raw || [ -n "$raw" ]; do
        line_no=$((line_no+1))
        # 跳过空行 / 注释
        stripped=$(printf '%s' "$raw" | sed 's/^[[:space:]]*//')
        case "$stripped" in
            ""|"#"*) continue ;;
        esac

        # 1) `.venv/bin/X` / `venv/bin/X` 绝对路径调用 → 安全
        if echo "$raw" | grep -qE "[/.]v?env/bin/$CLI_RE([[:space:]]|$)"; then
            continue
        fi

        # 2) 裸命令（含 exec 前缀）→ FAIL
        #    匹配：行首或非标识符字符开头 + 可选 exec + CLI 命令名 + 词边界
        if echo "$raw" | grep -qE "(^|[^A-Za-z0-9_./-])(exec[[:space:]]+)?$CLI_RE([[:space:]]|$)"; then
            emit_fail "$rel" "$line_no" "$stripped"
            continue
        fi

        # 3) `python -m <CLI>` / `python3 -m <CLI>` → FAIL（系统 python 找不到 venv 里的包）
        if echo "$raw" | grep -qE "(^|[^A-Za-z0-9_./-])(exec[[:space:]]+)?python[0-9.]*[[:space:]]+-m[[:space:]]+$CLI_RE([[:space:]]|$)"; then
            emit_fail "$rel" "$line_no" "$stripped"
        fi
    done < "$sh"
done

if [ "$fail" -gt 0 ]; then
    echo "" >&2
    echo "[FAIL] $fail 处 .sh 调用 venv-installed Python CLI，但所在文件未激活 venv 也未用绝对路径" >&2
    echo "" >&2
    echo "  根因：install.sh 用 \`python3 -m venv .venv\` 把 gunicorn/uvicorn/celery 等装到" >&2
    echo "        \`.venv/bin/\` 下，不在系统 PATH。Guard runner 起这些 .sh 时同文件没激活 venv," >&2
    echo "        立即报 \`exec: <cmd>: not found\`。" >&2
    echo "" >&2
    echo "  修复（任选其一，按推荐顺序）：" >&2
    echo "    a) 脚本头激活 venv（最通用）：" >&2
    echo "         #!/bin/bash" >&2
    echo "         set -eo pipefail" >&2
    echo "         cd \"\$(dirname \"\$0\")\"" >&2
    echo "         [ -f ../.venv/bin/activate ] && . ../.venv/bin/activate    # 相对位置按子目录层级调整" >&2
    echo "         exec gunicorn ..." >&2
    echo "    b) 绝对路径调用（不依赖 PATH 解析）：" >&2
    echo "         exec /home/app/.venv/bin/gunicorn ..." >&2
    echo "    c) 该 .sh 本就不该跑 Python CLI（删脚本 / 改用根 start.sh 单进程模式）" >&2
    echo "" >&2
    echo "  注：guard-transform 模板渲染的根目录 start.sh 由 TPL_VENV_ACTIVATE 自动注入激活行，" >&2
    echo "      报错的通常是业务**手写**的子进程脚本 / 自定义启动器。" >&2
    exit 1
fi

echo "[OK] 所有调用 venv-installed Python CLI 的 .sh 均已激活 venv 或使用绝对路径"
