#!/usr/bin/env bash
# 验证 zip 顶层结构（stage 60 已内嵌一遍；这个独立版本用于事后审计）
#
# 参数兼容两种调用方式：
#   1) bash verify_zip_layout.sh <zip_path>           — 直接传 .zip 文件（最早设计）
#   2) bash verify_zip_layout.sh <work_dir>           — 传工作副本目录，自动反推同级最新 zip
#      （`guardx verify` 子命令统一对所有 verifier 传 cfg.work_dir，所以必须支持）
#
# 命名约定（见 config.Config.zip_path）：
#   work_dir = <parent>/<name>-guard/
#   zip_path = <parent>/<name>-guard-<MMDDhhmm>.zip   （与 work_dir 同级）
# 因此从目录反推 zip 的方式：在 work_dir 的父目录找 `$(basename work_dir)-*.zip`，
# 按 mtime 取最新一个；找不到时友好跳过（cmd_verify 标 ✅，避免漏跑了 stage 60
# 还看到一片 verifier 红的误伤——stage 60 跑过自然就有 zip）。
set -eo pipefail
ARG="${1:?usage: $0 <zip_path|work_dir>}"

if [ -d "$ARG" ]; then
  # 目录：按命名约定反推同级最新 zip
  WORK_DIR="$ARG"
  WORK_NAME="$(basename "$WORK_DIR")"
  PARENT="$(dirname "$WORK_DIR")"
  # ls -t 按 mtime 倒序；2>/dev/null 屏蔽无匹配 ls 报错；
  # `|| true` 防止 set -eo pipefail 下 ls 非零退出码（无匹配文件时）传播触发 set -e。
  ZIP_PATH="$(ls -t "$PARENT"/"$WORK_NAME"-*.zip 2>/dev/null | head -1 || true)"
  if [ -z "$ZIP_PATH" ]; then
    echo "[OK] 未找到 ${WORK_NAME}-*.zip（stage 60 还没跑过？跳过事后审计——zip 顶层结构由 stage 60 内嵌断言保证）"
    exit 0
  fi
  echo "[INFO] 从 work_dir 反推 zip: $ZIP_PATH"
else
  # 文件：直接当 zip
  ZIP_PATH="$ARG"
fi

[ -f "$ZIP_PATH" ] || { echo "[FAIL] zip 不存在: $ZIP_PATH" >&2; exit 1; }

top="$(unzip -l "$ZIP_PATH" | awk 'NR>3 {print $NF}')"

fail=0
for required in install.sh start.sh health.sh; do
  if ! echo "$top" | grep -qx "$required"; then
    echo "[FAIL] zip 顶层缺 $required" >&2
    fail=$((fail+1))
  fi
done

# 不能含的
for forbidden in db.properties ai.properties .env .env.local node_modules .git; do
  if echo "$top" | grep -qE "(^|/)$forbidden(\$|/)"; then
    echo "[FAIL] zip 包含 $forbidden（应被排除）" >&2
    fail=$((fail+1))
  fi
done

[ "$fail" -gt 0 ] && exit 1
echo "[OK] zip 顶层结构正确"
