#!/usr/bin/env bash
# 验证：DB connection URL 不能用 f-string / 模板字符串拼接 password
#
# 背景（详见 prompts/20_remove_external_infra.md "PG 连接配置" 段）：
#   Guard 平台注入的 db.password 是用户在表单填的原始密码，几乎一定含
#   @ : / ? # 等 URL 保留字符。f-string 拼 URL 会让 SQLAlchemy / pg parser
#   把 @ 之后的部分误识别成 host，运行时抛 socket.gaierror: Name or
#   service not known，且没有可读上下文，极难定位。
#
# 必须用结构化 API：
#   - SQLAlchemy:  URL.create(drivername, username=, password=, host=, ...)
#   - asyncpg:     await asyncpg.connect(user=, password=, host=, ...)
#   - psycopg:     psycopg.connect(user=, password=, host=, ...)
#   - Node pg:     new Pool({user, password, host, port, database})
#
# 本 verifier 静态扫描以下危险模式，命中即 FAIL：
#   ① Python f-string:    f"...://...:{password}@..."
#   ② Node template:       `...://...:${password}@...`
#   ③ % / .format() 拼接： "...://...:%s@..." % (..., password, ...)
#   ④ 字符串 + 拼接：       "...://" + user + ":" + password + "@" + host

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# 共用排除：不扫 node_modules / build 产物 / 状态目录 / lock 文件
EXCLUDE_DIRS='(node_modules/|\.next/|dist/|build/|\.guard-transform|venv/|\.venv/|__pycache__/)'

# ── ① + ②：URL 字符串里的 ${...pass...} / {...pass...} 占位符 ────────────
# 匹配语义：
#   :// 之后到 @ 之前，出现一个 ${...pass...} 或 {...pass...} 占位符
#   不限定 driver 前缀，因为 mysql/mongodb/redis 拼字符串也是同样的 bug
#
# 关键正则段：
#   ://         scheme 分隔符
#   [^"'\`@]{1,80}  非引号/反引号/@ 的若干字符（user 段）
#   :           user-password 分隔
#   \$?\{       Python 的 { 或 Node 的 ${
#   [^}]{0,40}  花括号内任意字符
#   [Pp][Aa][Ss][Ss]   pass 关键字（不区分大小写）
#   [^}]{0,40}\}  花括号闭合
#   [^"'\`@]{0,30}@  随后到 @
#
# 注：不用 grep -i，因为 [Pp][Aa][Ss][Ss] 比 -i 更精确（避免 PASSING / passes 等单词命中）
PLACEHOLDER='://[^"'"'"'\`@]{1,80}:\$?\{[^}]{0,40}[Pp][Aa][Ss][Ss][^}]{0,40}\}[^"'"'"'\`@]{0,30}@'

hits=$(grep -rnE "$PLACEHOLDER" \
  --include='*.py' --include='*.js' --include='*.ts' \
  --include='*.mjs' --include='*.cjs' --include='*.jsx' --include='*.tsx' \
  . 2>/dev/null \
  | grep -vE "$EXCLUDE_DIRS" \
  | grep -vE '^[^:]+:[0-9]+:[[:space:]]*(#|//|\*)' \
  | head -20 || true)

if [ -n "$hits" ]; then
  report "DB connection URL 用了 \${password} 占位符拼接（密码含 @ : / 时会让 host 解析错位）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ── ③：Python "%s://...:%s@..." % (..., password, ...) ────────────────
# 关键：URL 字符串里 :%s@ + 同一行/紧邻有 password 入 % 元组
PCT_PATTERN='://[^"'"'"']{1,80}:%[sd][^"'"'"']{0,30}@'

hits=$(grep -rnE "$PCT_PATTERN" --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE_DIRS" \
  | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' \
  | grep -iE 'pass' \
  | head -20 || true)

if [ -n "$hits" ]; then
  report "Python DB URL 用了 % 占位符 + password 元组拼接（同 \${password} 风险）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ── ④：字符串 + 拼接 password ────────────────────────────────────────
# 模式: "://" + user + ":" + password + "@"
# 行内必须同时含 :// 和 + password 关键词
hits=$(grep -rnE '"://".*\+.*\bpassword\b.*\+.*"@"' \
  --include='*.py' --include='*.js' --include='*.ts' \
  --include='*.mjs' --include='*.cjs' --include='*.jsx' --include='*.tsx' \
  . 2>/dev/null \
  | grep -vE "$EXCLUDE_DIRS" \
  | head -20 || true)

if [ -n "$hits" ]; then
  report "DB URL 用 + 拼接 password（同 \${password} 风险）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

if [ "$fail" -gt 0 ]; then
  cat >&2 <<'EOF'
[FAIL] DB connection URL 含不安全的 password 拼接

修复方案（详见 prompts/20_remove_external_infra.md "PG 连接配置"）:

  Python SQLAlchemy:
    from sqlalchemy import URL
    create_async_engine(URL.create(
        "postgresql+asyncpg",
        username=user, password=password,
        host=host, port=int(port), database=db,
    ))

  Python asyncpg:
    await asyncpg.connect(user=u, password=p, host=h, port=int(port), database=d)

  Node pg:
    new Pool({user, password, host, port: Number(port), database})

  实在要字符串：先 urllib.parse.quote(password, safe='') 再拼。
EOF
  exit 1
fi
echo "[OK] DB connection URL 拼接安全"
