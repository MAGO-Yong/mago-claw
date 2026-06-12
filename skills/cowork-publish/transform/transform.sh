#!/usr/bin/env bash
# guard-transform 主入口
#
# 转发到 Python 版 guardx CLI。
# 历史的 GUARD_LEGACY=1 兼容通道（transform.legacy.sh）已移除，统一走 Python 调度。
# 所有 stage 仍可通过 GUARDX_FORCE_BASH=1 强制走 bash 实现（仅对存在 bash 版的 stage 20-70 生效）。
#
# 用法：./transform.sh <源工程路径|zip> [--from-stage NN] [--skip-llm] [--resume|--reset|-y]
#                     [--no-autofix] [--choose-model]
#   --choose-model  跳过 transform，直接调 choose-model.sh 让用户重选模型后退出
set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── --choose-model 透传：直接调本目录下的 choose-model.sh ────────────────
# 设计：用户 / agent 想随时换模型时只需 `transform.sh --choose-model`，
# 而不必记住 choose-model.sh 的具体路径。
for _arg in "$@"; do
    if [ "$_arg" = "--choose-model" ]; then
        if [ -x "$SCRIPT_DIR/choose-model.sh" ]; then
            exec "$SCRIPT_DIR/choose-model.sh"
        else
            echo "[transform.sh] 错误：未找到 $SCRIPT_DIR/choose-model.sh（请重装 skill）" >&2
            exit 1
        fi
    fi
done
unset _arg

# ── 自动 source 兄弟 default_env.sh（若存在）──────────────────────────────
# 设计：skills/codewiz/ / skills/claude/ 的 install.sh 会在安装目录写 default_env.sh，
# 内含 `: "${GUARD_LLM:=codewiz}"` / `: "${GUARD_LLM:=claude}"` 等默认值。
#
# 历史上要求 agent / SKILL.md 在调 transform.sh 前自己 source 它，但实测 codewiz
# agent 经常漏掉这一步（每个 bash 工具调用都是独立 shell，前一次 source 的 env
# 不会带到这一次），导致 default 失效、guardx 回退到 llm.py 内置 GUARD_LLM=claude
# → 在 codewiz skill 装机下却用了 claude CLI，鉴权失败 / 找不到 token。
#
# 把 source 责任从 agent 移到工具自身：transform.sh 启动时先 source 一次，让
# default 永远生效；用户预先 export 的同名变量因 `${VAR:=default}` 仍优先（不破坏覆盖）。
# 用 GUARD_QUIET=1 抑制 source 时的回显，避免重复刷屏（guardx 进程会再次 banner 打印）。
if [ -f "$SCRIPT_DIR/default_env.sh" ]; then
    GUARD_QUIET="${GUARD_QUIET:-1}" . "$SCRIPT_DIR/default_env.sh"
fi

# ── 首次跑：interactive 模式 + marker=initial → 自动调起 choose-model.sh ──
# 设计动机：
#   install.sh 写入 default_env.sh 时在末尾埋了 `# CHOOSE_MODEL_MARKER:initial`，
#   choose-model.sh 改写后会换成 `:chosen`。
#   首次跑 transform.sh 时若 marker 还是 initial 且当前是 interactive 模式（macOS
#   交互终端），自动调起 choose-model.sh 让用户确认模型，避免"用户不知道默认
#   是什么模型就跑了几小时"的体验问题。
#
# 跳过场景（任一满足即跳过）：
#   - GUARD_RUN_MODE=non-interactive（CI / openclaw / 服务端）
#   - GUARD_NONINTERACTIVE=1
#   - stdin 不是 tty（被 pipe / 重定向调用）
#   - default_env.sh 不存在 / 没有 marker / 已经是 chosen
#   - 用户显式 export GUARD_SKIP_CHOOSE_MODEL=1（CI 自动化）
if [ -f "$SCRIPT_DIR/default_env.sh" ] \
   && [ -x "$SCRIPT_DIR/choose-model.sh" ] \
   && [ "${GUARD_SKIP_CHOOSE_MODEL:-0}" != "1" ] \
   && [ "${GUARD_RUN_MODE:-}" = "interactive" ] \
   && [ "${GUARD_NONINTERACTIVE:-0}" != "1" ] \
   && [ -t 0 ] \
   && grep -q "^# CHOOSE_MODEL_MARKER:initial" "$SCRIPT_DIR/default_env.sh"; then
    echo ""
    echo "════════════════════════════════════════════════════════════════════"
    echo " [首次跑提示] 检测到 default_env.sh 还是装机初始状态"
    echo "              强烈建议先确认 LLM 后端 + 分级模型再开始转写"
    echo "              （转写一般要 10-60 分钟，跑到一半发现模型不对就亏了）"
    echo "════════════════════════════════════════════════════════════════════"
    echo ""
    printf "是否现在调起 choose-model.sh 选模型？[Y/n/skip] > " >&2
    read -r _ans </dev/tty || _ans=""
    case "${_ans:-Y}" in
        n|N|no|NO)
            echo "[transform.sh] 已沿用装机默认（下次再问；export GUARD_SKIP_CHOOSE_MODEL=1 可永久跳过）"
            ;;
        skip|SKIP)
            # 不再询问：写入 chosen marker，等同用户主动跳过
            # 用 python in-place 改写，避免 sed -i 在 GNU/BSD 间的语义差异和遗留备份文件
            python3 - "$SCRIPT_DIR/default_env.sh" <<'PY' || true
import re, sys
p = sys.argv[1]
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()
s = re.sub(r'^# CHOOSE_MODEL_MARKER:.*$', '# CHOOSE_MODEL_MARKER:chosen', s, flags=re.M)
with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
PY
            echo "[transform.sh] 已标记 chosen，下次不再自动询问（重选请跑 choose-model.sh）"
            ;;
        *)
            "$SCRIPT_DIR/choose-model.sh"
            # choose-model.sh 退出后再次 source 让新值在本次 transform 生效
            GUARD_QUIET="${GUARD_QUIET:-1}" . "$SCRIPT_DIR/default_env.sh"
            ;;
    esac
    unset _ans
fi

# ── 启动 banner：醒目打印本次使用的 CLI / 模型 ────────────────────────────
# 设计：default_env.sh 自身的回显被 GUARD_QUIET=1 静默了，guardx 进入流水线后
# 才会再次打印完整 LLM 四件套（_log_llm_config）；但用户/agent 希望"启动瞬间"
# 就能看到本次到底用了哪个 CLI（尤其在 codewiz skill / claude skill 两套默认值
# 容易混淆时），所以这里独立打一行简洁 banner，醒目且不重复 guardx 详细输出。
#
# 抑制方法：export GUARD_TRANSFORM_QUIET_BANNER=1（少数 CI 场景嫌噪音）
# 内容刻意只展示 GUARD_LLM / GUARD_LLM_MODEL（用户最关心的两项）；想看完整
# 后端/超时/strong/fast 分级，等 guardx 启动后 _log_llm_config 的四件套即可。
if [ "${GUARD_TRANSFORM_QUIET_BANNER:-0}" != "1" ]; then
    _g_llm="${GUARD_LLM:-claude}"   # 与 guardx/llm.py 内置 fallback 一致
    # GUARD_LLM_MODEL 仅 codewiz 后端生效（其它后端 guardx 内部会忽略）；
    # 所以非 codewiz 时把模型字段改写成"由该 CLI 自身决定"，避免 banner 误导
    # （比如用户切到 claude 但 default_env.sh 仍含 codewiz 的模型默认值时）。
    if [ "$_g_llm" = "codewiz" ]; then
        _g_mdl="${GUARD_LLM_MODEL:-<后端默认/分级路由>}"
    else
        _g_mdl="<由 $_g_llm CLI 自身决定>"
    fi
    printf '\n\033[1;36m>>> guard-transform 启动：CLI=%s  |  模型=%s <<<\033[0m\n\n' \
        "$_g_llm" "$_g_mdl" >&2
    unset _g_llm _g_mdl
fi

# ── LLM CLI 登录 / 模型可用性预检 ──────────────────────────────────────────
# 设计：本地交互模式下，agent 选好模型后立刻验证 CLI 已登录 + 模型可用，
# 失败时让用户在终端跑 `claude login` / `codewiz providers` 后按 Enter 重试，
# 避免跑到 stage 20 第一次 LLM 调用才发现 401 / token 过期，浪费 N 分钟。
#
# 跳过场景（脚本内部自处理，不影响这里）：
#   - GUARD_RUN_MODE=non-interactive / GUARD_NONINTERACTIVE=1（CI / openclaw / 服务端）
#   - stdin / stderr 不是 tty（被 pipe / 重定向调用）
#   - GUARD_LOGIN_CHECK=0（用户显式关闭）
# 不影响 detect / verify / clean 这些不调 LLM 的子命令（它们不经过 transform.sh）
if [ "${GUARD_LOGIN_CHECK:-1}" = "1" ] && [ -x "$SCRIPT_DIR/bin/cowork-login-check" ]; then
    if ! "$SCRIPT_DIR/bin/cowork-login-check"; then
        rc=$?
        case "$rc" in
            1) echo "[transform.sh] 用户主动退出登录预检，abort" >&2 ;;
            2) echo "[transform.sh] LLM CLI 鉴权预检未通过（exit=2），abort" >&2 ;;
            *) echo "[transform.sh] cowork-login-check 异常退出 exit=$rc，abort" >&2 ;;
        esac
        exit "$rc"
    fi
fi

exec "$SCRIPT_DIR/bin/guardx" transform "$@"
