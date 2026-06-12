#!/usr/bin/env bash
# start.sh - 由 Guard 应用拉起业务主进程；末行必须 exec
# 由 guard-transform 模板渲染生成
set -eo pipefail
cd "$(dirname "$0")"



cd "$(dirname "$0")/backend"
export APP_PORT="${APP_PORT:-3000}"
export PORT="${APP_PORT}" NODE_ENV=production
exec node src/server.js 2>&1
