#!/usr/bin/env bash
# 验证 SSO 身份接入符合 Guard 契约（详见 transform_prompt.md § 六）
#
# 检查项：
#   1) 不能有自建 SSO 验签 / JWT 中间件 / OAuth callback 路由残留
#   2) 读 Decrypted-Userinfo header 处必须做 latin-1 → utf-8 重编码
#   3) 前端不能硬编 Guest / Demo / Anonymous / 游客 / 测试 等 mock displayName
#   4) 不能引用 hrUserId / department / employeeType 等不在 header 里的字段（静默兜空陷阱）
#
# 设计原则：本工程**未必**用 SSO，所以策略是：
#   - 检测到任何 Decrypted-Userinfo / 认证依赖 / SSO 关键词 → 进入"严格模式"逐项查
#   - 否则跳过（纯无状态工具应用允许整段忽略）
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

EXCLUDE='(node_modules|\.next/|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|test/|tests/|__tests__)'

# ---- 先决条件：是否需要 SSO？----
USES_USERINFO=0
if grep -rqIE 'Decrypted-Userinfo|decrypted-userinfo|decrypted_userinfo' . 2>/dev/null \
     --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
     --include='*.py' --exclude-dir=node_modules --exclude-dir=.git \
     --exclude-dir=.next --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv \
     --exclude-dir=__pycache__; then
  USES_USERINFO=1
fi

HAS_AUTH_DEPS=0
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json frontend/package.json; do
  [ -f "$pkg" ] || continue
  if grep -qE '"(passport|passport-jwt|next-auth|@auth/core|jsonwebtoken|express-session|express-jwt)"' "$pkg"; then
    HAS_AUTH_DEPS=1
    break
  fi
done
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  if grep -qiE '^[[:space:]]*(flask-login|flask-jwt-extended|python-jose|pyjwt|authlib|django-allauth)([><=!~ ]|$)' "$req"; then
    HAS_AUTH_DEPS=1
    break
  fi
done

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. 自建 SSO / JWT 中间件残留 ----
# 即便没用 Decrypted-Userinfo，也要拦自建 SSO 残留依赖（这是死代码也要清干净）
if [ "$HAS_AUTH_DEPS" = "1" ]; then
  HITS=""
  for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json frontend/package.json; do
    [ -f "$pkg" ] || continue
    h=$(grep -nE '"(passport|passport-jwt|next-auth|@auth/core|jsonwebtoken|express-session|express-jwt)"' "$pkg" 2>/dev/null || true)
    [ -n "$h" ] && HITS="$HITS\n$pkg:\n$h"
  done
  for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
    [ -f "$req" ] || continue
    h=$(grep -niE '^[[:space:]]*(flask-login|flask-jwt-extended|python-jose|pyjwt|authlib|django-allauth)([><=!~ ]|$)' "$req" 2>/dev/null || true)
    [ -n "$h" ] && HITS="$HITS\n$req:\n$h"
  done
  if [ -n "$HITS" ]; then
    report "工程含自建 SSO / JWT 依赖（Guard 已做 ECDSA 验签 + 权限校验，子应用不能再做一次）:"
    printf '%b\n' "$HITS" | sed 's/^/    /' >&2
  fi
fi

# 自建 /auth/callback 路由（Next.js / Express 常见）
if grep -rnE "['\"]/(auth|login)/callback['\"]" \
     --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
     --include='*.py' . 2>/dev/null \
     | grep -vE "$EXCLUDE" \
     | head -10 | grep -q .; then
  CB=$(grep -rnE "['\"]/(auth|login)/callback['\"]" \
       --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
       --include='*.py' . 2>/dev/null | grep -vE "$EXCLUDE" | head -5)
  report "工程含自建 /auth/callback 或 /login/callback 路由（Guard 已处理回调，子应用别再做）:"
  printf '%s\n' "$CB" | sed 's/^/    /' >&2
fi

# ---- 2. Decrypted-Userinfo 读取必须做 latin-1 → utf-8 重编码 ----
if [ "$USES_USERINFO" = "1" ]; then
  # 收集所有引用 Decrypted-Userinfo 的文件
  USERINFO_FILES=$(grep -rlIE 'Decrypted-Userinfo|decrypted-userinfo|decrypted_userinfo' . 2>/dev/null \
                   --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
                   --include='*.py' --exclude-dir=node_modules --exclude-dir=.git \
                   --exclude-dir=.next --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv \
                   --exclude-dir=__pycache__ || true)

  MISSING=""
  for f in $USERINFO_FILES; do
    # 重编码模式（覆盖 Python / Node 各种写法）
    if ! grep -qE '\.encode\(["'"'"']latin-1["'"'"']\)\.decode\(["'"'"']utf-8["'"'"']\)|Buffer\.from\([^,]+,\s*["'"'"']latin1?["'"'"']\)\.toString\(\s*["'"'"']utf-?8["'"'"']\s*\)|iconv\.|latin1-to-utf-?8' "$f" 2>/dev/null; then
      MISSING="$MISSING $f"
    fi
  done
  if [ -n "$MISSING" ]; then
    report "下列文件读 Decrypted-Userinfo 但未做 latin-1→utf-8 重编码（中文会变 mojibake）:"
    for f in $MISSING; do echo "    $f" >&2; done
    echo "    Python:  raw.encode('latin-1').decode('utf-8')" >&2
    echo "    Node.js: Buffer.from(raw, 'latin1').toString('utf-8')" >&2
  fi

  # ---- 4. 引用 hrUserId / department / employeeType 静默兜空 ----
  if grep -rnIE '["'"'"'](hrUserId|department|employeeType)["'"'"']' \
       --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
       --include='*.py' . 2>/dev/null \
       | grep -vE "$EXCLUDE" | head -5 | grep -q .; then
    HR=$(grep -rnIE '["'"'"'](hrUserId|department|employeeType)["'"'"']' \
         --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
         --include='*.py' . 2>/dev/null | grep -vE "$EXCLUDE" | head -5)
    report "代码引用 hrUserId / department / employeeType（不在 Decrypted-Userinfo header 里，自己按 email 查通讯录）:"
    printf '%s\n' "$HR" | sed 's/^/    /' >&2
  fi
fi

# ---- 3. 前端 mock 身份字符串硬编 ----
# 仅当代码里出现 displayName / currentUser / user.name 时才做严格 grep
HAS_USER_SLOT=0
if grep -rqIE 'displayName|currentUser|user\.name|userInfo' \
     --include='*.tsx' --include='*.jsx' --include='*.vue' --include='*.svelte' . 2>/dev/null; then
  HAS_USER_SLOT=1
fi

if [ "$HAS_USER_SLOT" = "1" ]; then
  MOCK_HITS=$(grep -rnIE \
    "(displayName|currentUser|user\.name|userInfo)\s*[:=]\s*[\"'](Guest|Demo|Anonymous|guest|demo|游客|测试|匿名|test user|示例用户)[\"']|\
\|\|\s*[\"'](Guest|Demo|Anonymous|guest|demo|游客|测试|匿名)[\"']" \
    --include='*.tsx' --include='*.jsx' --include='*.vue' --include='*.svelte' \
    --include='*.ts' --include='*.js' . 2>/dev/null \
    | grep -vE "$EXCLUDE" | head -10 || true)
  if [ -n "$MOCK_HITS" ]; then
    report "前端身份槽位硬编 mock 字符串（应通过 /api/session/me 取 SSO 真值）:"
    printf '%s\n' "$MOCK_HITS" | sed 's/^/    /' >&2
  fi
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项 SSO 接入违反 - 详见 transform_prompt.md § 六" >&2
  exit 1
fi
echo "[OK] SSO 身份接入合规"
