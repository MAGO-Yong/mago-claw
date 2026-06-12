#!/usr/bin/env bash
# guard-transform seal skill 默认环境（skills/seal/）
# 由 render.sh 自动生成；SKILL.md / examples.md / openclaw.md 中所有调用前会 source 本文件
#
# 三层优先级（从高到低）：
#   1. 用户预先 export 的同名变量（最高优先，profile 和默认值都不会覆盖）
#   2. GUARD_PROFILE=<name> 预设展开（一键填一批服务端 / 调试 / 离线场景的合理值）
#   3. 内置默认值（最低，仅作兜底）
#
# 实现：全部用 ${VAR:=default} 语义 —— "未设置或空才填"，已 export 的值永远赢
#
# === 默认配置（最低优先级）===
#   GUARD_LLM              = seal
#   GUARD_LLM_MODEL        = (留空)              一刀切模型 id；留空才能让分级路由生效
#   GUARD_LLM_MODEL_STRONG = claude-4.6-sonnet-google     stage 20 跨文件大改写专用
#   GUARD_LLM_MODEL_FAST   = claude-4.6-sonnet-google      stage 10 brief / autofix 局部小修专用
#   GUARD_LLM_TIMEOUT      = 1800                单次 LLM 调用 30 分钟超时
#   GUARD_LLM_HEARTBEAT    = 60                  1 分钟一次心跳，避免长任务被误判 hang
#
# 模型分级优先级：GUARD_LLM_MODEL（一刀切，最高）> GUARD_LLM_MODEL_STRONG/FAST（分级）> 内置默认
# 想换分级：跑 `guardx change-model` 交互选择 / 跑 `guardx change-model --strong <id> --fast <id>` 直写

# --- 自动导出 GUARD_TRANSFORM_HOME（从本文件位置推导）---
# 注意：必须用 BASH_SOURCE[0]，$0 在 source 场景下指向调用方而非本文件
if [ -z "${GUARD_TRANSFORM_HOME:-}" ]; then
    GUARD_TRANSFORM_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    export GUARD_TRANSFORM_HOME
fi

# --- GUARD_PROFILE 预设展开（必须在自动判定 GUARD_RUN_MODE 之前）---
case "${GUARD_PROFILE:-}" in
    server)
        : "${GUARD_RUN_MODE:=non-interactive}"
        : "${GUARD_NONINTERACTIVE:=1}"
        : "${GUARD_LLM_VERIFY:=1}"
        : "${GUARD_SMOKE_FULL:=0}"
        : "${GUARD_LLM_TIMEOUT:=1800}"
        : "${GUARD_LLM_HEARTBEAT:=60}"
        export GUARD_RUN_MODE GUARD_NONINTERACTIVE GUARD_LLM_VERIFY GUARD_SMOKE_FULL
        ;;
    "")
        :
        ;;
    *)
        echo "[cowork-skill] [WARN] 未知 GUARD_PROFILE=$GUARD_PROFILE（已知值: server / 留空）" >&2
        ;;
esac

# --- 自动判定运行模式 ---
if [ -z "${GUARD_RUN_MODE:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ]; then
        GUARD_RUN_MODE="interactive"
    else
        GUARD_RUN_MODE="non-interactive"
    fi
fi

# --- 通用默认（最低优先级）---
: "${GUARD_LLM:=seal}"
: "${GUARD_LLM_MODEL:=}"
: "${GUARD_LLM_MODEL_STRONG:=claude-4.6-sonnet-google}"
: "${GUARD_LLM_MODEL_FAST:=claude-4.6-sonnet-google}"
: "${GUARD_LLM_TIMEOUT:=1800}"
: "${GUARD_LLM_HEARTBEAT:=60}"
export GUARD_LLM GUARD_LLM_MODEL GUARD_LLM_MODEL_STRONG GUARD_LLM_MODEL_FAST GUARD_LLM_TIMEOUT GUARD_LLM_HEARTBEAT GUARD_TRANSFORM_HOME GUARD_RUN_MODE

# --- 模型选择 marker：transform.sh 在 interactive 模式下检测到 initial 会自动调起 choose-model.sh ---
# choose-model.sh / `guardx change-model` 改写本文件后会把这一行替换为 # CHOOSE_MODEL_MARKER:chosen
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
    echo "[cowork-skill] 覆盖方法: \`guardx change-model\` / 编辑 \$GUARD_TRANSFORM_HOME/default_env.sh / export GUARD_LLM_MODEL=..." >&2
fi
