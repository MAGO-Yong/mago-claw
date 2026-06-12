#!/usr/bin/env bash
# guard-transform · 模型选择器（claude skill 版，macOS / 交互式终端用）
#
# 用途：交互式选择 LLM 后端 + 分级路由模型（STRONG/FAST），写回
#       $GUARD_TRANSFORM_HOME/default_env.sh，下次跑 transform.sh 自动生效。
#
# 与 codewiz skill/choose-model.sh 对称镜像，差别仅在候选清单：
#   - 后端默认 claude（直接复用 Claude Code OAuth）
#   - 模型 id 用 anthropic 命名（claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-5）
#
# 用法：
#   $GUARD_TRANSFORM_HOME/choose-model.sh           # 3 阶段菜单
#   $GUARD_TRANSFORM_HOME/choose-model.sh --show    # 只打印当前默认值
#   $GUARD_TRANSFORM_HOME/choose-model.sh --reset   # 恢复 install.sh 初始默认 + marker:initial
#
# 安全：每次写前备份 default_env.sh.bak（仅保留最近一次）

set -eo pipefail

# ---------------------------------------------------------------------------
# 平台与终端校验：仅 macOS + TTY 才允许交互
# ---------------------------------------------------------------------------
if [ "$(uname -s)" != "Darwin" ]; then
    echo "[ERROR] choose-model.sh 仅支持 macOS（当前: $(uname -s)）" >&2
    echo "        Linux/容器/CI 请直接 export GUARD_LLM* 或编辑 default_env.sh" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 定位 default_env.sh
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${GUARD_TRANSFORM_HOME:-}"
if [ -z "$HOME_DIR" ] && [ -f "$SCRIPT_DIR/.guard_transform_home" ]; then
    HOME_DIR="$(cat "$SCRIPT_DIR/.guard_transform_home")"
fi
HOME_DIR="${HOME_DIR:-$SCRIPT_DIR}"

DEFAULT_ENV="$HOME_DIR/default_env.sh"
if [ ! -f "$DEFAULT_ENV" ]; then
    echo "[ERROR] 未找到 $DEFAULT_ENV" >&2
    echo "        请先安装 claude skill: bash <skill-src>/install.sh" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 工具函数（先定义，后调用）
# ---------------------------------------------------------------------------
parse_default() {
    local var="$1"
    sed -nE "s/^[[:space:]]*:[[:space:]]*\"\\\$\\{${var}:=([^}]*)\\}\".*/\1/p" "$DEFAULT_ENV" | head -n1
}

escape_sed_replace() {
    printf '%s' "$1" | sed -e 's/[&]/\\&/g'
}

write_back() {
    local var="$1" val="$2" val_esc
    val_esc="$(escape_sed_replace "$val")"
    if grep -qE "^[[:space:]]*:[[:space:]]*\"\\\$\\{${var}:=" "$DEFAULT_ENV"; then
        sed -i '' -E \
            "s|^([[:space:]]*:[[:space:]]*\")\\\$\\{${var}:=[^}]*\\}(\".*)$|\1\\\$\\{${var}:=${val_esc}\\}\2|" \
            "$DEFAULT_ENV"
    else
        echo "[WARN] default_env.sh 里没找到 \${${var}:=...} 行，跳过（请手动添加）" >&2
    fi
}

# ---------------------------------------------------------------------------
# 当前生效默认值
# ---------------------------------------------------------------------------
current_llm="$(parse_default GUARD_LLM)"
current_model="$(parse_default GUARD_LLM_MODEL)"
current_strong="$(parse_default GUARD_LLM_MODEL_STRONG)"
current_fast="$(parse_default GUARD_LLM_MODEL_FAST)"

# install.sh 写入的初始推荐默认
INITIAL_LLM="claude"
INITIAL_MODEL=""
INITIAL_STRONG="claude-opus-4-6"
INITIAL_FAST="claude-sonnet-4-6"

if [ "${1:-}" = "--show" ]; then
    echo "[guard-transform] 当前 default_env.sh 默认值："
    echo "    GUARD_LLM               = ${current_llm:-<未设置>}"
    echo "    GUARD_LLM_MODEL         = ${current_model:-<留空，分级路由生效>}"
    echo "    GUARD_LLM_MODEL_STRONG  = ${current_strong:-<未设置，走 guardx 内置>}"
    echo "    GUARD_LLM_MODEL_FAST    = ${current_fast:-<未设置，走 guardx 内置>}"
    echo "    文件位置                : $DEFAULT_ENV"
    if grep -q "^# CHOOSE_MODEL_MARKER:chosen" "$DEFAULT_ENV"; then
        echo "    模型选择状态            : chosen（用户已确认）"
    elif grep -q "^# CHOOSE_MODEL_MARKER:initial" "$DEFAULT_ENV"; then
        echo "    模型选择状态            : initial（首次跑 transform.sh 会自动弹本脚本）"
    fi
    exit 0
fi

if [ "${1:-}" = "--reset" ]; then
    cp "$DEFAULT_ENV" "$DEFAULT_ENV.bak"
    write_back GUARD_LLM "$INITIAL_LLM"
    write_back GUARD_LLM_MODEL "$INITIAL_MODEL"
    write_back GUARD_LLM_MODEL_STRONG "$INITIAL_STRONG"
    write_back GUARD_LLM_MODEL_FAST "$INITIAL_FAST"
    if grep -q "^# CHOOSE_MODEL_MARKER:" "$DEFAULT_ENV"; then
        sed -i '' -E 's|^# CHOOSE_MODEL_MARKER:.*|# CHOOSE_MODEL_MARKER:initial|' "$DEFAULT_ENV"
    fi
    echo "[OK] 已恢复 install.sh 初始默认（含 marker:initial）"
    echo "     备份: $DEFAULT_ENV.bak"
    exit 0
fi

# ---------------------------------------------------------------------------
# 候选清单（claude 系列；用户改后端为 codewiz 后可手动 export GUARD_LLM_MODEL_*）
# ---------------------------------------------------------------------------
BACKEND_OPTIONS=(
    "claude|🌟 默认推荐：standalone Claude CLI（直接复用 Claude Code OAuth）"
    "codewiz|☁️  切到 codewiz CLI（codewiz vscode 插件 token；模型 id 须改成 codewiz/... 系列）"
    "qwen-code|🧧 千问 Coder CLI（国内带宽友好）"
    "codex|✳️  OpenAI codex CLI"
    "gemini|🔷 Google gemini CLI"
    "mock|🧪 mock 后端（不调 LLM，仅跑骨架，调试用）"
)

# STRONG 候选；第 1 项始终是"使用推荐默认"
STRONG_OPTIONS=(
    "__DEFAULT__|🌟 使用推荐默认（$INITIAL_STRONG）— 回车即可"
    "claude-opus-4-6|🚀 opus 4.6，最强（贵且慢）— 与 guardx 内置默认一致"
    "claude-opus-4-7|🧪 opus 4.7 实验性，最新"
    "claude-sonnet-4-6|⚡ sonnet 4.6，省钱方案（与 FAST 合一）"
    "__CUSTOM__|✏️  手动输入完整 model id"
    "__CLEAR__|🚫 清空（让 guardx 走内置默认 $INITIAL_STRONG）"
)

# FAST 候选
FAST_OPTIONS=(
    "__DEFAULT__|🌟 使用推荐默认（$INITIAL_FAST）— 回车即可"
    "claude-sonnet-4-6|⚡ sonnet 4.6，质量/速度平衡 — 与 guardx 内置默认一致"
    "claude-haiku-4-5|💨 haiku 4.5 极速，分类/格式化"
    "claude-opus-4-6|🚀 opus 4.6，极致质量（贵，仅小批量推荐）"
    "__CUSTOM__|✏️  手动输入完整 model id"
    "__CLEAR__|🚫 清空（让 guardx 走内置默认 $INITIAL_FAST）"
)

# ---------------------------------------------------------------------------
# 通用菜单函数
# ---------------------------------------------------------------------------
prompt_menu() {
    local arr_name="$1" title="$2" current_val="$3"
    local -a opts
    eval "opts=( \"\${${arr_name}[@]}\" )"
    echo "" >&2
    echo "──────────────────────────────────────────────────────────────────" >&2
    echo " $title" >&2
    echo "   当前默认: ${current_val:-<未设置>}" >&2
    echo "──────────────────────────────────────────────────────────────────" >&2
    local i=1
    for opt in "${opts[@]}"; do
        local desc="${opt##*|}"
        printf "  %2d) %s\n" "$i" "$desc" >&2
        i=$((i+1))
    done
    echo "" >&2
    local reply
    while :; do
        printf "请输入序号 [1-%d]（回车默认 1）> " "${#opts[@]}" >&2
        read -r reply </dev/tty
        reply="${reply:-1}"
        if [[ "$reply" =~ ^[0-9]+$ ]] && [ "$reply" -ge 1 ] && [ "$reply" -le "${#opts[@]}" ]; then
            local picked="${opts[$((reply-1))]}"
            echo "${picked%%|*}"
            return 0
        fi
        echo "  无效输入，请输入 1-${#opts[@]}" >&2
    done
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo " guard-transform · 模型选择器（claude skill · 3 阶段菜单）"
echo "════════════════════════════════════════════════════════════════════"
echo " 当前默认: GUARD_LLM=${current_llm:-<未设置>}"
echo "           GUARD_LLM_MODEL=${current_model:-<留空，分级路由生效>}"
echo "           GUARD_LLM_MODEL_STRONG=${current_strong:-<未设置>}"
echo "           GUARD_LLM_MODEL_FAST  =${current_fast:-<未设置>}"
echo " 文件位置: $DEFAULT_ENV"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo " 设计提醒："
echo "   · 一刀切 GUARD_LLM_MODEL 留空时，分级路由才生效；本脚本只编辑分级"
echo "   · 想一刀切：选完后手动编辑 default_env.sh 填 GUARD_LLM_MODEL，或临时 export"
echo "   · 切到 codewiz 后端后，模型 id 命名要换成 codewiz/... 系列（参考 codewiz skill）"
echo "   · Ctrl+C 任意阶段中止（未确认前不会写文件）"
echo ""

# ── 阶段 1：选后端 ──────────────────────────────────────────────────────
new_backend="$(prompt_menu BACKEND_OPTIONS '阶段 1/3 · 选择 LLM 后端（GUARD_LLM）' "$current_llm")"

# ── 阶段 2：选 STRONG 模型 ─────────────────────────────────────────────
strong_pick="$(prompt_menu STRONG_OPTIONS '阶段 2/3 · 选择 STRONG 模型（GUARD_LLM_MODEL_STRONG）— stage 20 跨文件大改写' "$current_strong")"
case "$strong_pick" in
    __DEFAULT__) new_strong="$INITIAL_STRONG" ;;
    __CLEAR__)   new_strong="" ;;
    __CUSTOM__)
        printf "请输入完整 model id（如 claude-opus-4-6）> " >&2
        read -r new_strong </dev/tty
        ;;
    *) new_strong="$strong_pick" ;;
esac

# ── 阶段 3：选 FAST 模型 ───────────────────────────────────────────────
fast_pick="$(prompt_menu FAST_OPTIONS '阶段 3/3 · 选择 FAST 模型（GUARD_LLM_MODEL_FAST）— stage 10 brief / autofix' "$current_fast")"
case "$fast_pick" in
    __DEFAULT__) new_fast="$INITIAL_FAST" ;;
    __CLEAR__)   new_fast="" ;;
    __CUSTOM__)
        printf "请输入完整 model id（如 claude-sonnet-4-6）> " >&2
        read -r new_fast </dev/tty
        ;;
    *) new_fast="$fast_pick" ;;
esac

# ── 二次确认 ─────────────────────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────────────────────────────"
echo " 即将写入 $DEFAULT_ENV："
echo "   GUARD_LLM              = $new_backend"
echo "   GUARD_LLM_MODEL_STRONG = ${new_strong:-<清空>}"
echo "   GUARD_LLM_MODEL_FAST   = ${new_fast:-<清空>}"
echo "   GUARD_LLM_MODEL        = ${current_model:-<保持留空，分级路由生效>}（本脚本不动）"
echo "──────────────────────────────────────────────────────────────────"
printf "确认写入？[Y/n] > " >&2
read -r confirm </dev/tty
confirm="${confirm:-Y}"
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "[ABORT] 未确认，退出（未修改任何文件）"
    exit 1
fi

# ── 写回 ────────────────────────────────────────────────────────────────
cp "$DEFAULT_ENV" "$DEFAULT_ENV.bak"
write_back GUARD_LLM "$new_backend"
write_back GUARD_LLM_MODEL_STRONG "$new_strong"
write_back GUARD_LLM_MODEL_FAST "$new_fast"

if grep -q "^# CHOOSE_MODEL_MARKER:" "$DEFAULT_ENV"; then
    sed -i '' -E 's|^# CHOOSE_MODEL_MARKER:.*|# CHOOSE_MODEL_MARKER:chosen|' "$DEFAULT_ENV"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "[OK] 已写回 default_env.sh"
echo "    文件: $DEFAULT_ENV"
echo "    备份: $DEFAULT_ENV.bak  （仅保留最近一次）"
echo "════════════════════════════════════════════════════════════════════"
echo ""
printf '\033[1;36m>>> 新默认：CLI=%s  |  STRONG=%s  |  FAST=%s <<<\033[0m\n\n' \
    "$new_backend" "${new_strong:-<内置默认>}" "${new_fast:-<内置默认>}"
echo "下次跑 transform 时 transform.sh 自动 source 新默认；立即验证："
echo ""
echo "    $SCRIPT_DIR/$(basename "$0") --show"
echo ""
