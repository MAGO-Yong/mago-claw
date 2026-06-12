#!/bin/sh
# cowork pack 在副本里跑 — 用户原工程已 build 时直接复用,避免重跑 30-120s 的 npm ci + next build
# 触发 OpenClaw pi-agent waitForIdle 30s cleanup bug (#8643)
set -e
if ! command -v npm >/dev/null 2>&1; then
  echo "[prepack] ❌ npm not found; nextjs-fullstack needs Node.js"
  exit 1
fi

SERVER=".next/standalone/server.js"

# === fast path: standalone server.js 已存在且不旧于源码,直接复用(仍要做 env patch + static link) ===
NEED_BUILD=1
if [ -f "$SERVER" ]; then
  STALE=$(find app src pages components lib \
    package.json package-lock.json \
    next.config.js next.config.mjs next.config.ts \
    tsconfig.json \
    -type f -newer "$SERVER" -print 2>/dev/null | head -1)
  if [ -z "$STALE" ]; then
    echo "[prepack] ✅ .next/standalone 已是最新,跳过 npm ci + next build"
    NEED_BUILD=0
  else
    echo "[prepack] .next/standalone 过期 (新于 server.js 的文件: $STALE), 重 build"
  fi
fi

# === slow path: 真跑 npm ci + next build ===
if [ "$NEED_BUILD" = "1" ]; then
  echo "[prepack] npm ci (内部 registry via .npmrc)"
  npm ci
  echo "[prepack] next build (standalone)"
  npm run build
  test -f "$SERVER" || { echo "[prepack] ❌ $SERVER 不存在;next.config.js 是否含 output:'standalone'?"; exit 1; }
fi

# === 后续 patch:env 改写 + static / public link(无论 fast / slow 都要做,因为副本是干净 copy) ===
# patch HOSTNAME/PORT → APP_HOSTNAME/APP_PORT
echo "[prepack] patch env vars in $SERVER"
perl -i -pe 's/process\.env\.HOSTNAME\b/(process.env.APP_HOSTNAME || process.env.HOSTNAME)/g' "$SERVER"
perl -i -pe 's/process\.env\.PORT\b/(process.env.APP_PORT || process.env.PORT)/g' "$SERVER"

# standalone 不会自动 link .next/static / public
mkdir -p .next/standalone/.next
[ -d .next/static ] && [ ! -e .next/standalone/.next/static ] && cp -r .next/static .next/standalone/.next/static
[ -d public ] && [ ! -e .next/standalone/public ] && cp -r public .next/standalone/public

echo "[prepack] ✅ .next/standalone/server.js ready"
