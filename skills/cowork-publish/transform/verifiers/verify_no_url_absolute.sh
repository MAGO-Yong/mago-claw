#!/usr/bin/env bash
# 验证：源码不烧绝对路径前缀（assetPrefix / basePath / publicPath / base）
# 验证：HTML / JS 里 fetch 不写绝对 URL
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# -- 1. 前端 config 不能配 assetPrefix / basePath / publicPath / base --
hits=$(grep -rnE '(assetPrefix|basePath|publicPath|^\s*base\s*:)' \
  next.config.* vite.config.* vue.config.* nuxt.config.* webpack.config.* \
  frontend/next.config.* frontend/vite.config.* frontend/vue.config.* 2>/dev/null \
  | grep -vE '(//|/\*|node_modules)' | head -10 || true)
if [ -n "$hits" ]; then
  report "前端 config 烧了前缀（router 注入会双前缀 404）:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 next.config.* / vite.config.* / vue.config.* / nuxt.config.* / webpack.config.* / 同名 frontend/* 副本。删除 assetPrefix / basePath / publicPath / base 这些配置项（router 会动态注入前缀，业务自己烧会双前缀 404）" >&2
fi

# -- 2. HTML 模板硬编**协议头 / 内部 host** (href="http://..." / src="//cdn..." 等) --
#
# ⚠️ 与 prompts/23_fix_paths.md §2 对齐：规范明确要求 HTML 里的 `href="/foo"`/`src="/static/x.png"`/
#    `action="/submit"` **保留 `/` 裸路径**——router 会在响应阶段动态注入前缀，业务无需感知。
#    所以本 verifier **不应**拦 HTML 模板里的裸路径 `/xxx`；只该拦下面这两类真正的违规：
#
#      ❌ `href="http://..."` / `src="https://..."` —— 协议头硬编，router body_filter 不会改写
#      ❌ `href="//cdn.example.com/..."` —— 协议相对 URL，等同硬编 host
#      ❌ `src="http://localhost:8080/api/..."` —— 内部 host 硬编，泄漏 Pod 内部地址
#
#    （历史版本曾拦 `="/字母"` 与 23_fix_paths.md 自相矛盾，已修正；裸路径不再拦截。
#     CSS 里的 `url(/...)` 由 verifiers/verify_css_no_abs_url.sh 单独负责。）
hits=$(grep -rnE '(href|src|action)="(https?:)?//' \
  --include='*.html' --include='*.htm' . 2>/dev/null \
  | grep -vE '(node_modules|\.next/|dist/|build/|\.guard-transform)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "HTML 模板含协议头硬编 / 内部 host 绝对 URL (router 改写不到模板):"
  echo "$hits" | sed 's/^/    /' >&2
  echo "    提示：裸路径 \"/foo\" 是规范允许的（router 会注入前缀），本检查只拦 \"http://...\" / \"//host/...\" 这两类" >&2
  echo "[HINT] 目标文件：上面 grep 列出的 *.html / *.htm。把 \`href/src/action=\"http(s)://host/path\"\` 或 \`=\"//host/path\"\` 改为裸路径 \`=\"/path\"\`（router body_filter 只改写裸 \`/\` 开头的路径，协议头/双斜杠 host 不会被改写）" >&2
fi

# -- 3. 上游主动压缩 --
hits=$(grep -rnE '(compress\s*:\s*true|app\.use\(\s*compression|GZipMiddleware|require\([\x27"]compression[\x27"])' \
  next.config.* server.* backend/src/ src/ 2>/dev/null \
  | grep -vE '(node_modules|compress\s*:\s*false|//|\.guard-transform)' | head -5 || true)
if [ -n "$hits" ]; then
  report "上游主动压缩 (router body_filter 要明文 HTML):"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 next.config.* / server.* / src/。删除 compression / GZipMiddleware 中间件，或把 \`compress: true\` 改为 \`compress: false\`（router 需要明文 HTML 才能注入前缀，被压缩后无法 body_filter）" >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项绝对路径 / 前缀配置违反" >&2
  exit 1
fi
echo "[OK] 路径裸路径 + 前端配置无烧前缀"
