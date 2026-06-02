#!/usr/bin/env bash
# guard-transform · 模型选择器（seal skill 版，macOS / 交互式终端用）
#
# 用途：交互式选择 LLM 后端 + 分级路由模型（STRONG/FAST），写回
#       $GUARD_TRANSFORM_HOME/default_env.sh，下次跑 transform.sh 自动生效。
#
# 与 claude skill/choose-model.sh 对称镜像，差别仅在候选清单：
#   - 后端默认 seal（实际调用 codewiz-cc CLI，Claude Code fork，参数完全兼容）
#   - 模型候选仅放 seal 后端通过 codewiz-cc 实际可用的 google 路由模型：
#       · claude-4.6-sonnet-google  Sonnet 4.6（Google 路由）⭐ 速度快
#       · claude-4.5-haiku-google   Haiku 4.5（Google 路由）⭐ 轻量快
#   - 默认 STRONG/FAST 都用 claude-4.6-sonnet-google 非 thinking（用户硬需求，不一刀切）
#   - anthropic 原生 id（claude-sonnet-4-6 等）在 seal 后端跑不起来，菜单不再提供避免误选
#
# 用法：
#   $GUARD_TRANSFORM_HOME/choose-model.sh           # 3 阶段菜单
#   $GUARD_TRANSFORM_HOME/choose-model.sh --show    # 只打印当前默认值
#   $GUARD_TRANSFORM_HOME/choose-model.sh --reset   # 恢复 build.sh 写入的初始默认 + marker:initial
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
    echo "        请先在 Seal IDE 里上传由 skills/seal/build.sh 产出的 zip" >&2
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

# build.sh 写入的初始推荐默认（用于 --reset 恢复 + 菜单第 1 项标签提示）
# seal skill 硬需求：STRONG/FAST 都用 sonnet 非 thinking（保持分级机制，但默认值对齐）
INITIAL_LLM="seal"
INITIAL_MODEL=""
INITIAL_STRONG="claude-4.6-sonnet-google"
INITIAL_FAST="claude-4.6-sonnet-google"

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
    echo "[OK] 已恢复 build.sh 初始默认（含 marker:initial）"
    echo "     备份: $DEFAULT_ENV.bak"
    exit 0
fi

# ---------------------------------------------------------------------------
# 候选清单（seal 后端通过 codewiz-cc 实际支持的模型列表）
#
# ⚠️ 强约束：seal skill 默认走 seal 后端，可用模型仅以下两个（codewiz-cc 路由的 google 通道）：
#       - claude-4.6-sonnet-google  Sonnet 4.6（Google 路由）⭐ 速度快
#       - claude-4.5-haiku-google   Haiku 4.5（Google 路由）⭐ 轻量快
#   任何 anthropic 原生模型 id（claude-sonnet-4-6 / claude-opus-4-6 等）在 seal 后端下都跑不起来，
#   故菜单不再提供这些选项，避免用户误选。如确需切到 anthropic / codewiz / qwen 等后端，
#   先在 BACKEND 阶段切换，再手动用 __CUSTOM__ 输入对应后端的 model id。
# ---------------------------------------------------------------------------
BACKEND_OPTIONS=(
    "seal|🌟 默认推荐：Seal IDE 内置 CLI（codewiz-cc，复用 Seal 鉴权）"
    "claude|☁️  standalone Claude CLI（直接复用 Claude Code OAuth；切后请手动输入 anthropic 原生 model id）"
    "codewiz|🧩 codewiz CLI（codewiz vscode 插件 token；模型 id 须改成 codewiz/... 系列）"
    "qwen-code|🧧 千问 Coder CLI（国内带宽友好；切后请手动输入 qwen-* model id）"
    "codex|✳️  OpenAI codex CLI（切后请手动输入 OpenAI model id）"
    "gemini|🔷 Google gemini CLI（切后请手动输入 gemini-* model id）"
    "mock|🧪 mock 后端（不调 LLM，仅跑骨架，调试用）"
)

# STRONG 候选（stage 20 跨文件大改写）；第 1 项始终是"使用推荐默认"
# seal 后端只放 sonnet——haiku 跑跨文件大改写质量不够；不提供 anthropic 原生 id 防止误选
STRONG_OPTIONS=(
    "__DEFAULT__|🌟 使用推荐默认（$INITIAL_STRONG，非 thinking）— 回车即可"
    "claude-4.6-sonnet-google|⚡ Sonnet 4.6（Google 路由），速度快 — seal 场景唯一推荐 STRONG"
    "__CUSTOM__|✏️  手动输入完整 model id（仅切到非 seal 后端时使用）"
)

# FAST 候选（stage 10 brief + autofix 局部小修）
# seal 后端只放两个 google 路由的模型，覆盖"质量+速度"两档；不提供 anthropic 原生 id 防止误选
FAST_OPTIONS=(
    "__DEFAULT__|🌟 使用推荐默认（$INITIAL_FAST，非 thinking）— 回车即可"
    "claude-4.6-sonnet-google|⚡ Sonnet 4.6（Google 路由），速度快 — 与 STRONG 对齐"
    "claude-4.5-haiku-google|💨 Haiku 4.5（Google 路由），轻量快 — 适合 autofix / 格式化"
    "__CUSTOM__|✏️  手动输入完整 model id（仅切到非 seal 后端时使用）"
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
echo " guard-transform · 模型选择器（seal skill · 3 阶段菜单）"
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
echo "   · seal skill 默认 STRONG/FAST 都是 claude-4.6-sonnet-google 非 thinking（用户硬需求）"
echo "   · seal 后端实际可用模型仅 2 个：claude-4.6-sonnet-google（速度快） / claude-4.5-haiku-google（轻量快）"
echo "   · 切到 claude / codewiz / qwen 等非 seal 后端后，必须用 __CUSTOM__ 手动输入对应后端的 model id"
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
        printf "请输入完整 model id（seal 后端可用：claude-4.6-sonnet-google，非 seal 后端请用对应命名）> " >&2
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
        printf "请输入完整 model id（seal 后端可用：claude-4.6-sonnet-google / claude-4.5-haiku-google，非 seal 后端请用对应命名）> " >&2
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

# 兼容性提醒：seal 后端仅支持 *-google 后缀的 model id；其它后端用 google id 会跑不起来
# 反之亦然——非 seal 后端用了 google id，或 seal 后端用了非 google id，都给出提示
warn_incompat() {
    local backend="$1" model="$2" label="$3"
    [ -z "$model" ] && return 0
    if [ "$backend" = "seal" ]; then
        case "$model" in
            *-google) : ;;  # 兼容
            *)
                echo "[WARN] $label='$model' 在 seal 后端下大概率跑不起来" >&2
                echo "       seal 后端实际可用：claude-4.6-sonnet-google / claude-4.5-haiku-google" >&2
                ;;
        esac
    else
        case "$model" in
            *-google)
                echo "[WARN] $label='$model' 是 google 路由 id，只能在 seal 后端下用" >&2
                echo "       后端=$backend，请改用对应后端的 model id（例如 claude → claude-sonnet-4-6）" >&2
                ;;
        esac
    fi
}
warn_incompat "$new_backend" "$new_strong" "GUARD_LLM_MODEL_STRONG"
warn_incompat "$new_backend" "$new_fast" "GUARD_LLM_MODEL_FAST"

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
