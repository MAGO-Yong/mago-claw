#!/usr/bin/env bash
# guard-transform codewiz skill 默认环境（skills/codewiz/）
# 由 install.sh 自动生成；SKILL.md / examples.md / openclaw.md 中所有调用前会 source 本文件
#
# 三层优先级（从高到低）：
#   1. 用户预先 export 的同名变量（最高优先，profile 和默认值都不会覆盖）
#   2. GUARD_PROFILE=<name> 预设展开（一键填一批服务端 / 调试 / 离线场景的合理值）
#   3. 内置默认值（最低，仅作兜底）
#
# 实现：全部用 ${VAR:=default} 语义 —— "未设置或空才填"，已 export 的值永远赢
#
# === 默认配置（最低优先级）===
#   GUARD_LLM              = codewiz                                # 与 codewiz vscode 插件共享 provider/token
#   GUARD_LLM_MODEL        = (留空)                                  # 一刀切模型；留空才能让分级路由生效
#   GUARD_LLM_MODEL_STRONG = codewiz/Claude-4.6-opus(thinking)      # stage 20 跨文件大改写专用（推荐 opus）
#   GUARD_LLM_MODEL_FAST   = codewiz/Claude-4.6-sonnet              # stage 10 brief / autofix 局部小修专用（FAST 不推荐 thinking）
#   GUARD_LLM_TIMEOUT      = 1800                                   # 单次 LLM 调用 30 分钟超时（适合复杂改写）
#   GUARD_LLM_HEARTBEAT    = 60                                     # 1 分钟一次心跳，避免长任务被误判 hang
#
# 模型分级优先级：GUARD_LLM_MODEL（一刀切，最高）> GUARD_LLM_MODEL_STRONG/FAST（分级）> 内置默认
# 默认行为：GUARD_LLM_MODEL 留空 + 分级填好 → stage 20 自动用 opus，其它 stage 用 sonnet
# 想一刀切：设置 GUARD_LLM_MODEL（如 export 或在本文件填值）即可压过分级
# 想换分级：跑 $GUARD_TRANSFORM_HOME/choose-model.sh 交互选择 / 直接编辑本文件
#
# === GUARD_PROFILE 一键预设 ===
#   server   服务端 / openclaw / CI 场景：无交互、开 LLM 自动修复、关重量级 smoke
#            等价于一次性 export 这一坨：
#              GUARD_RUN_MODE=non-interactive
#              GUARD_NONINTERACTIVE=1
#              GUARD_LLM_VERIFY=1
#              GUARD_SMOKE_FULL=0
#              GUARD_LLM_TIMEOUT=1800
#              GUARD_LLM_HEARTBEAT=60
#            用法：export GUARD_PROFILE=server && source "$GUARD_TRANSFORM_HOME/default_env.sh"
#   (空)     不设 profile → 沿用各变量已有的默认（本地交互场景）
#
# === 如何覆盖 ===
#   1) 临时覆盖（仅当前 shell）：先 export，再 source（${VAR:=default} 会保留你的值）
#        export GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)'   # 切到更强模型
#        export GUARD_LLM=claude                                       # 切到其它后端
#        source "$GUARD_TRANSFORM_HOME/default_env.sh"
#   2) 永久覆盖：直接编辑本文件，把下面 default 改成你想要的；下次 source 即生效
#   3) 静默回显：export GUARD_QUIET=1 后再 source（仅抑制提示，仍正常设置变量）

# --- 自动导出 GUARD_TRANSFORM_HOME（从本文件位置推导）---
# 注意：必须用 BASH_SOURCE[0]，$0 在 source 场景下指向调用方而非本文件
if [ -z "${GUARD_TRANSFORM_HOME:-}" ]; then
    GUARD_TRANSFORM_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    export GUARD_TRANSFORM_HOME
fi

# --- GUARD_PROFILE 预设展开（必须在自动判定 GUARD_RUN_MODE 之前）---
# 用 ${VAR:=default} 语义 → 用户预先 export 的值会被尊重；只填那些用户没设的
case "${GUARD_PROFILE:-}" in
    server)
        # 服务端 / openclaw / CI：一键展开服务端模式所需的全部变量
        : "${GUARD_RUN_MODE:=non-interactive}"
        : "${GUARD_NONINTERACTIVE:=1}"
        : "${GUARD_LLM_VERIFY:=1}"
        : "${GUARD_SMOKE_FULL:=0}"
        : "${GUARD_LLM_TIMEOUT:=1800}"
        : "${GUARD_LLM_HEARTBEAT:=60}"
        export GUARD_RUN_MODE GUARD_NONINTERACTIVE GUARD_LLM_VERIFY GUARD_SMOKE_FULL
        ;;
    "")
        : # 不设 profile → 走下面自动判定 + 通用默认
        ;;
    *)
        echo "[cowork-skill] [WARN] 未知 GUARD_PROFILE=$GUARD_PROFILE（已知值: server / 留空）" >&2
        ;;
esac

# --- 自动判定运行模式（仅当 profile 没填且用户没 export 时）---
# macOS 默认 interactive；其他系统默认 non-interactive
# 上层 SKILL.md / bin/* 都消费 GUARD_RUN_MODE 来决定是否提问
if [ -z "${GUARD_RUN_MODE:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ]; then
        GUARD_RUN_MODE="interactive"
    else
        GUARD_RUN_MODE="non-interactive"
    fi
fi

# --- 通用默认（最低优先级）---
: "${GUARD_LLM:=codewiz}"
# GUARD_LLM_MODEL 默认留空 → 让 STRONG/FAST 分级路由真正生效
# 如需一刀切：手动 export GUARD_LLM_MODEL='codewiz/Claude-4.6-sonnet(thinking)' 或填本行
: "${GUARD_LLM_MODEL:=}"
# 分级路由模型（推荐默认；choose-model.sh 可交互改写）
: "${GUARD_LLM_MODEL_STRONG:=codewiz/Claude-4.6-opus(thinking)}"
: "${GUARD_LLM_MODEL_FAST:=codewiz/Claude-4.6-sonnet}"
: "${GUARD_LLM_TIMEOUT:=1800}"
: "${GUARD_LLM_HEARTBEAT:=60}"
export GUARD_LLM GUARD_LLM_MODEL GUARD_LLM_MODEL_STRONG GUARD_LLM_MODEL_FAST GUARD_LLM_TIMEOUT GUARD_LLM_HEARTBEAT GUARD_TRANSFORM_HOME GUARD_RUN_MODE

# --- 模型选择 marker：transform.sh 在 interactive 模式下检测到 initial 会自动调起 choose-model.sh ---
# choose-model.sh 改写本文件后会把这一行替换为 # CHOOSE_MODEL_MARKER:chosen
# CHOOSE_MODEL_MARKER:initial

# --- 信息回显（可被 GUARD_QUIET=1 静默）---
if [ "${GUARD_QUIET:-0}" != "1" ]; then
    echo "[cowork-skill] 运行模式: $GUARD_RUN_MODE${GUARD_PROFILE:+ (profile=$GUARD_PROFILE)}" >&2
    if [ -n "${GUARD_LLM_MODEL:-}" ]; then
        echo "[cowork-skill] LLM 后端: $GUARD_LLM / 模型(一刀切): $GUARD_LLM_MODEL / 超时: ${GUARD_LLM_TIMEOUT}s / 心跳: ${GUARD_LLM_HEARTBEAT}s" >&2
    else
        echo "[cowork-skill] LLM 后端: $GUARD_LLM / 模型: <分级路由生效> / 超时: ${GUARD_LLM_TIMEOUT}s / 心跳: ${GUARD_LLM_HEARTBEAT}s" >&2
        echo "[cowork-skill] 分级路由: STRONG=${GUARD_LLM_MODEL_STRONG:-<内置默认>} / FAST=${GUARD_LLM_MODEL_FAST:-<内置默认>}" >&2
    fi
    echo "[cowork-skill] 覆盖方法: export GUARD_LLM=... / GUARD_LLM_MODEL_STRONG='...' / GUARD_LLM_MODEL_FAST='...'，或编辑 $GUARD_TRANSFORM_HOME/default_env.sh，或跑 $GUARD_TRANSFORM_HOME/choose-model.sh" >&2
fi
