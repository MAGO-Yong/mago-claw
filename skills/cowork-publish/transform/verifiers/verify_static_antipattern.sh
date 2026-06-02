#!/usr/bin/env bash
# 验证：静态资源服务路径不踩"全局拦截器吃掉 _next/static"等反模式
# 详见 transform_prompt.md § 七 "静态资源 fallthrough"
#
# 检查项：
#   1) Express/Koa：app.use(express.static(...)) 必须出现在所有 app.get(...)/app.use(router) 之前
#   2) NestJS：@UseInterceptors / @UseGuards 全局 + .forRoutes('*') 会吃 /_next/static
#      改写：.forRoutes(...).exclude('/_next/(.*)', '/static/(.*)', '/health')
#   3) FastAPI：StaticFiles(directory="...") 不能挂在 /api/ 等被路由覆盖的前缀
#   4) Next.js：next.config.* 不能含 assetPrefix / basePath 写死的绝对地址
#   5) Express SPA fallback：app.get('*', sendFile(index.html)) 必须出现在 static 之后
#
# 仅当工程含相关框架信号时执行，避免对纯 SSR/纯 API 误报。

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# 注意：grep -E 用的是 POSIX ERE，**不支持** PCRE lookahead `(?!...)` / `(?=...)`，
# BSD grep（macOS 默认）会直接报 "repetition-operator operand invalid"。
# 因此 EXCLUDE 里不放 `.next/` 排除，改用下面的 filter_excludes() awk 单独处理：
# "排除 .next/ 但保留 .next/standalone"（Next.js standalone 入口必须读 HOSTNAME/PORT）。
EXCLUDE='(node_modules|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|/tests?/|__tests__|\.d\.ts$)'

# 公共过滤：剔除 EXCLUDE 模式 + 单独处理 .next/ 例外（POSIX awk，跨 BSD/GNU 通吃）
filter_excludes() {
  grep -vE "$EXCLUDE" | awk '!/\.next\// || /\.next\/standalone/'
}

# ---- 先决条件：是否有 web 服务框架 ----
USES_NODE_HTTP=0
USES_NEST=0
USES_NEXT=0
USES_FASTAPI=0

for f in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$f" ] || continue
  grep -qE '"(express|koa|fastify|hapi|@hapi/hapi)"' "$f" 2>/dev/null && USES_NODE_HTTP=1
  grep -qE '"@nestjs/(core|common)"' "$f" 2>/dev/null && USES_NEST=1
  grep -qE '"next"' "$f" 2>/dev/null && USES_NEXT=1
done
for f in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$f" ] || continue
  grep -qiE '^(fastapi|starlette)([><=!~ ]|$)' "$f" 2>/dev/null && USES_FASTAPI=1
done

if [ "$USES_NODE_HTTP$USES_NEST$USES_NEXT$USES_FASTAPI" = "0000" ]; then
  echo "[OK] 工程未使用 Express/Nest/Next/FastAPI（跳过）"
  exit 0
fi

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. NestJS forRoutes('*') 全局守卫/拦截器吃 _next/static ----
if [ "$USES_NEST" = "1" ]; then
  hits=$(grep -rnE "\.forRoutes\(\s*['\"]\*['\"]\s*\)|\.forRoutes\(\s*\{[^}]*path:\s*['\"]\*['\"]" \
    --include='*.ts' --include='*.js' . 2>/dev/null \
    | filter_excludes \
    | head -10 || true)
  if [ -n "$hits" ]; then
    report "NestJS .forRoutes('*') 会拦截 /_next/static/* 静态资源（必须 .exclude('/_next/(.*)', '/static/(.*)', '/health')）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi

  # @UseGuards / @UseInterceptors 用在 app 级别但没 exclude
  hits=$(grep -rnE "useGlobalGuards|useGlobalInterceptors|useGlobalFilters|useGlobalPipes" \
    --include='*.ts' --include='*.js' . 2>/dev/null \
    | filter_excludes \
    | head -5 || true)
  if [ -n "$hits" ]; then
    # 此处仅给出 INFO，因为全局 Guard 不一定是反模式（取决于 Guard 实现）
    echo "[INFO] 检测到全局 Nest Guard/Interceptor，请人工确认它对静态路径短路放行:" >&2
    echo "$hits" | sed 's/^/    /' >&2
  fi
fi

# ---- 2. Express SPA fallback 必须在 static 之后 ----
if [ "$USES_NODE_HTTP" = "1" ]; then
  for ENTRY in $(find . -type f \
      \( -name 'server.[jt]s' -o -name 'app.[jt]s' -o -name 'index.[jt]s' \
         -o -name 'main.[jt]s' \) \
      -not -path '*/node_modules/*' -not -path '*/dist/*' -not -path '*/build/*' \
      -not -path '*/.next/*' -not -path '*/.git/*' 2>/dev/null | head -10); do
    # 行号：static / sendFile fallback
    STATIC_LINES=$(grep -nE "express\.static\(|app\.use\(\s*['\"]?/?[^'\"]*['\"]?\s*,\s*express\.static" "$ENTRY" 2>/dev/null | cut -d: -f1)
    FALLBACK_LINES=$(grep -nE "app\.get\(\s*['\"]\*['\"]|app\.use\(\s*['\"]\*['\"]|sendFile\(.*index\.html|res\.sendFile\(" "$ENTRY" 2>/dev/null | cut -d: -f1)
    [ -z "$STATIC_LINES" ] && continue
    [ -z "$FALLBACK_LINES" ] && continue

    FIRST_STATIC=$(echo "$STATIC_LINES" | sort -n | head -1)
    FIRST_FALLBACK=$(echo "$FALLBACK_LINES" | sort -n | head -1)
    if [ -n "$FIRST_STATIC" ] && [ -n "$FIRST_FALLBACK" ] && [ "$FIRST_FALLBACK" -lt "$FIRST_STATIC" ]; then
      report "$ENTRY:$FIRST_FALLBACK SPA fallback (app.get('*') / sendFile) 出现在 express.static (第 $FIRST_STATIC 行) 之前，会吃掉 /_next/static / /static 请求"
    fi
  done
fi

# ---- 3. FastAPI: StaticFiles 挂在 /api 前缀下 ----
if [ "$USES_FASTAPI" = "1" ]; then
  hits=$(grep -rnE "app\.mount\(\s*['\"]/api[^'\"]*['\"]\s*,\s*StaticFiles" \
    --include='*.py' . 2>/dev/null \
    | filter_excludes \
    | head -5 || true)
  if [ -n "$hits" ]; then
    report "FastAPI app.mount(\"/api...\", StaticFiles) 容易被 API router 覆盖；建议挂在 / 或 /static:"
    echo "$hits" | sed 's/^/    /' >&2
  fi

  # FastAPI: StaticFiles 用绝对路径 directory（不可移植）
  hits=$(grep -rnE "StaticFiles\([^)]*directory\s*=\s*['\"]/[^'\"]+['\"]" \
    --include='*.py' . 2>/dev/null \
    | filter_excludes \
    | grep -vE 'directory\s*=\s*["'"'"']/tmp' \
    | head -5 || true)
  if [ -n "$hits" ]; then
    report "FastAPI StaticFiles 用绝对路径 directory（应相对入口或用 BASE_DIR.joinpath）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
fi

# ---- 4. Next.js next.config.* 含写死的 assetPrefix / basePath ----
if [ "$USES_NEXT" = "1" ]; then
  for cfg in next.config.js next.config.mjs next.config.cjs next.config.ts \
             apps/*/next.config.* packages/*/next.config.*; do
    [ -f "$cfg" ] || continue
    hits=$(grep -nE "assetPrefix\s*:\s*['\"]?(http|/[a-zA-Z])|basePath\s*:\s*['\"]/[a-zA-Z]" "$cfg" 2>/dev/null | head -3 || true)
    if [ -n "$hits" ]; then
      report "$cfg 含写死的 assetPrefix/basePath（Pod 上访问路径前缀不固定，必须保留默认）:"
      echo "$hits" | sed 's/^/    /' >&2
    fi
    # compress: true 是默认行为，平台会重复 gzip
    if grep -nE "compress\s*:\s*true" "$cfg" 2>/dev/null | head -3 | grep -q .; then
      report "$cfg 含 compress:true（必须 compress:false，平台已做 gzip）:"
      grep -nE "compress\s*:\s*true" "$cfg" 2>/dev/null | head -3 | sed 's/^/    /' >&2
    fi
  done
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项静态资源服务反模式 - 详见 transform_prompt.md § 七" >&2
  exit 1
fi
echo "[OK] 静态资源服务路径无反模式"
