#!/usr/bin/env bash
# 验证：所有业务代码读的环境变量都以 APP_ 开头
# 详见 transform_prompt.md § 一 + § 七.5
#
# 关键事实：
#   - 平台只允许业务声明以 APP_ 开头的 env（如 APP_FOO_BAR / APP_PORT）
#   - 系统级 env（HOST / HOSTNAME / PORT / NODE_ENV / PATH 等）由平台/Node 自己注入
#   - 业务代码读 process.env.HOSTNAME 会拿到系统主机名而不是业务想要的 host
#   - DB / AI 走 conf/db.properties + conf/ai.properties，不通过 env
#
# 白名单（业务代码可以读，不需要 APP_ 前缀）：
#   - NODE_ENV, NODE_OPTIONS, PYTHONPATH, PATH, HOME, TZ, LANG, LC_*
#   - Next.js standalone server.js 自动读：HOSTNAME, PORT（仅入口文件）
#   - npm 内部：npm_config_*, npm_package_*

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# 注意：grep -E 用的是 POSIX ERE，**不支持** PCRE lookahead `(?!...)` / `(?=...)`，
# BSD grep（macOS 默认）会直接报 "repetition-operator operand invalid"。
# 因此 EXCLUDE 里不放 `.next/` 排除，改用下面的 filter_excludes() awk 单独处理：
# "排除 .next/ 但保留 .next/standalone"（Next.js standalone 入口必须读 HOSTNAME/PORT）。
EXCLUDE='(node_modules|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|/test/|/tests/|__tests__|\.d\.ts$)'

# 系统级 env 白名单（业务代码读这些不报错）
WHITELIST_ENV='NODE_ENV|NODE_OPTIONS|NODE_PATH|PYTHONPATH|PYTHONUNBUFFERED|PATH|HOME|TZ|LANG|LC_[A-Z]+|TERM|SHELL|USER|PWD|TMPDIR|TEMP|TMP|CI|DEBUG|FORCE_COLOR|NO_COLOR|HTTP_PROXY|HTTPS_PROXY|NO_PROXY|http_proxy|https_proxy|no_proxy|npm_config_[a-zA-Z_]+|npm_package_[a-zA-Z_]+|YARN_[A-Z_]+|PNPM_[A-Z_]+|VIRTUAL_ENV'

# 公共过滤：剔除 EXCLUDE 模式 + 单独处理 .next/ 例外（POSIX awk，跨 BSD/GNU 通吃）
filter_excludes() {
  grep -vE "$EXCLUDE" | awk '!/\.next\// || /\.next\/standalone/'
}

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- Node: process.env.XXX / process.env["XXX"] ----
# 抓所有 process.env.<NAME>，过滤掉 APP_*、白名单
NODE_HITS=$(grep -rnoE "process\.env\.[A-Z][A-Z0-9_]+" \
  --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' --include='*.tsx' --include='*.jsx' \
  src/ app/ apps/ backend/ frontend/ api/ server/ pages/ lib/ middleware/ middlewares/ . 2>/dev/null \
  | filter_excludes \
  | grep -vE 'process\.env\.APP_' \
  | grep -vE "process\.env\.($WHITELIST_ENV)\b" \
  | sort -u || true)

# 排除 .next/standalone/server.js（Next 自己生成的，必须读 HOSTNAME/PORT）
NODE_HITS=$(echo "$NODE_HITS" | grep -vE '\.next/standalone/server\.js' || true)
# 排除 next.config.* 配置文件里的（构建期读，不属于运行时业务代码）
NODE_HITS=$(echo "$NODE_HITS" | grep -vE 'next\.config\.(js|mjs|cjs|ts):' || true)

if [ -n "$NODE_HITS" ]; then
  # 进一步过滤 process.env["FOO"] 数组式访问
  report "Node 业务代码读了非 APP_ 前缀 env（业务 env 必须 APP_*）:"
  echo "$NODE_HITS" | head -20 | sed 's/^/    /' >&2
fi

# Node 中括号写法：process.env["XXX"] / process.env['XXX']
NODE_BRACKET_HITS=$(grep -rnoE "process\.env\[\s*[\"'][A-Z][A-Z0-9_]+[\"']" \
  --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' --include='*.tsx' --include='*.jsx' \
  src/ app/ apps/ backend/ frontend/ api/ server/ pages/ lib/ . 2>/dev/null \
  | filter_excludes \
  | grep -vE "process\.env\[\s*[\"']APP_" \
  | grep -vE "process\.env\[\s*[\"']($WHITELIST_ENV)[\"']" \
  | head -20 || true)
if [ -n "$NODE_BRACKET_HITS" ]; then
  report "Node 业务代码用 process.env[\"XXX\"] 读了非 APP_ 前缀 env:"
  echo "$NODE_BRACKET_HITS" | sed 's/^/    /' >&2
fi

# ---- Python: os.environ.get / os.environ[...] / os.getenv ----
PY_HITS=$(grep -rnE "os\.(environ\.get|environ\[|getenv)\s*\(?\s*[\"'][A-Z][A-Z0-9_]+[\"']" \
  --include='*.py' \
  src/ app/ apps/ backend/ api/ server/ . 2>/dev/null \
  | filter_excludes \
  | grep -vE "[\"']APP_" \
  | grep -vE "[\"']($WHITELIST_ENV)[\"']" \
  | head -20 || true)
if [ -n "$PY_HITS" ]; then
  report "Python 业务代码读了非 APP_ 前缀 env（业务 env 必须 APP_*）:"
  echo "$PY_HITS" | sed 's/^/    /' >&2
fi

# Python: from os import environ; environ["XXX"]
PY_BARE_HITS=$(grep -rnE "(^|[^.a-zA-Z_])environ(\.get|\[)\s*\(?\s*[\"'][A-Z][A-Z0-9_]+[\"']" \
  --include='*.py' \
  src/ app/ apps/ backend/ api/ server/ . 2>/dev/null \
  | filter_excludes \
  | grep -vE "[\"']APP_" \
  | grep -vE "[\"']($WHITELIST_ENV)[\"']" \
  | grep -vE "os\.environ" \
  | head -10 || true)
if [ -n "$PY_BARE_HITS" ]; then
  report "Python 业务代码用 environ[\"XXX\"] 读了非 APP_ 前缀 env:"
  echo "$PY_BARE_HITS" | sed 's/^/    /' >&2
fi

# ---- 反向检查：APP_PORT 字面量必须出现 ----
# Node 入口 / start.sh 里至少有一处 APP_PORT 引用，否则平台注入的 APP_PORT 没人读
HAS_APP_PORT=0
if [ -f start.sh ] && grep -qE 'APP_PORT' start.sh 2>/dev/null; then
  HAS_APP_PORT=1
fi
if [ "$HAS_APP_PORT" = "0" ]; then
  if grep -rE 'APP_PORT' \
    --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' --include='*.py' \
    src/ app/ apps/ backend/ api/ server/ . 2>/dev/null \
    | filter_excludes | head -1 | grep -q .; then
    HAS_APP_PORT=1
  fi
fi
if [ "$HAS_APP_PORT" = "0" ]; then
  report "工程未读 APP_PORT（平台会注入 APP_PORT；start.sh 或入口必须 export PORT=\$APP_PORT 或直读 APP_PORT）"
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项 env 命名违反 - 详见 transform_prompt.md § 一" >&2
  exit 1
fi
echo "[OK] 所有业务 env 均 APP_ 前缀 / 白名单"
