#!/usr/bin/env bash
# 验证代码引用的 db.properties key 不超出平台注入的 6 个标准 key
# 平台只注入: db.type / db.host / db.port / db.username / db.password / db.database
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

ALLOWED='db\.(type|host|port|username|password|database)'

SUSPECT=$(grep -rnE "['\"]db\.[a-z_]+['\"]" \
  --include='*.ts' --include='*.js' --include='*.cjs' --include='*.mjs' \
  --include='*.py' \
  src/ apps/ backend/ public-relay/apps/*/src 2>/dev/null \
  | grep -vE '(node_modules|\.test\.|\.spec\.|\.next/|dist/|build/|\.guard-transform)' \
  | grep -oE "['\"]db\.[a-z_]+['\"]" | sort -u \
  | grep -vE "^['\"]($ALLOWED)['\"]$" || true)

if [ -n "$SUSPECT" ]; then
  echo "[FAIL] 代码引用了平台不注入的 db.properties key:" >&2
  echo "$SUSPECT" | sed 's/^/    /' >&2
  echo "    平台只注入: db.type / db.host / db.port / db.username / db.password / db.database" >&2
  echo "    详见 transform_prompt.md § 四 \"自作主张加额外必填 key\"" >&2
  SUSPECT_INLINE=$(echo "$SUSPECT" | tr '\n' ' ')
  echo "[HINT] 目标文件：上面 grep 命中的源码文件（搜 ${SUSPECT_INLINE}）。把这些越权 key 改用 6 个标准 key 拼接（如 db.url 改为 \`\${db.type}://\${db.host}:\${db.port}/\${db.database}\`；db.schema/db.driver/db.pool_size 等代码内写默认值，不要从 properties 读）" >&2
  exit 1
fi

echo "[OK] db.properties 必填 key 未越权"
