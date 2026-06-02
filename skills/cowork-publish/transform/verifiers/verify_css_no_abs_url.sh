#!/usr/bin/env bash
# 验证 CSS 不含 url(/...) 绝对路径（router body_filter 不改 text/css）
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

CSS_HITS=""
for d in dist .next/standalone/.next/static .next/static public/assets static/assets src/assets; do
  [ -d "$d" ] || continue
  hits=$(grep -rE 'url\(\s*/[a-zA-Z]' "$d" --include='*.css' 2>/dev/null \
    | grep -vE 'url\(\s*//' || true)
  [ -n "$hits" ] && CSS_HITS="$CSS_HITS$hits"$'\n'
done

if [ -n "$CSS_HITS" ]; then
  echo "[FAIL] CSS 含 url(/...) 绝对路径（router 不改 text/css 会丢前缀）:" >&2
  echo "$CSS_HITS" | head -10 | sed 's/^/    /' >&2
  echo "    改相对路径 url(../images/x.png) 或 import 进 JS 让构建器哈希" >&2
  exit 1
fi
echo "[OK] CSS 无 url(/...) 绝对路径"
