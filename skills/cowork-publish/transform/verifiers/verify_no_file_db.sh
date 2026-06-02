#!/usr/bin/env bash
# 验证：runtime 路径里没有"文件当 DB"反模式
# 详见 transform_prompt.md § 四 "文件当 DB 反模式"（§ 十 checklist 第 2125-2129 行）
#
# 检查项：
#   1) Node 文件 backend：lowdb / nedb / node-json-db / better-sqlite3 / sqlite3 / keyv 文件 backend
#   2) Python 文件 backend：tinydb / shelve / dbm / sqlite3.connect("xxx.db")
#   3) 通用文件落地：fs.writeFileSync / fs.appendFile / json.dump / pickle.dump
#      写到非 /tmp 非 logs 路径
#   4) 写到看着像数据的目录：data/ db/ storage/ uploads/ cache/
#
# 排除策略：
#   - test / spec / migration / seed 目录的文件落地是合法的（不是 runtime 路径）
#   - log / logs / tmp / .cache 目录是临时文件，不算 DB

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

EXCLUDE='(node_modules|\.next/|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|/test/|/tests/|__tests__|/migrations?/|/seed/|/seeders/|/fixtures/|\.d\.ts$)'

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. Node 文件 DB 依赖 ----
BANNED_NODE_FILE_DB='"(lowdb|nedb|node-json-db|better-sqlite3|sqlite3|keyv|@keyv/sqlite|level|leveldown|classic-level|jsondb|json-server)"'
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json frontend/package.json; do
  [ -f "$pkg" ] || continue
  hits=$(grep -nE "$BANNED_NODE_FILE_DB" "$pkg" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "$pkg 含文件型本地 DB 依赖（这些数据应该走 PostgreSQL）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 2. Python 文件 DB 依赖 ----
BANNED_PY_FILE_DB='^[[:space:]]*(tinydb|shelve|sqlitedict|pickleshare|diskcache)([><=!~ ]|$)'
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -nE "$BANNED_PY_FILE_DB" "$req" 2>/dev/null | grep -vE '^\s*#' || true)
  if [ -n "$hits" ]; then
    report "$req 含文件型本地 DB 依赖（这些数据应该走 PostgreSQL）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 3. Python sqlite3.connect("xxx.db") 直连 ----
hits=$(grep -rnE "sqlite3\.connect\(\s*[\"'][^\"']*\.(db|sqlite3?)" \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -vE ':memory:|/tmp/|tempfile' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Python sqlite3.connect 直连本地文件 DB（迁到 PostgreSQL）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 4. import shelve / dbm / tinydb 在业务代码里 ----
hits=$(grep -rnE '^[[:space:]]*(import|from)[[:space:]]+(shelve|dbm|tinydb|sqlitedict|pickleshare)\b' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Python 业务代码 import 文件 DB 模块（迁到 PostgreSQL）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 5. Node 业务代码里 fs.writeFileSync 写非 tmp 非 log 路径 ----
# 策略：在 src / app / backend / api / server / pages / routes 等业务目录下查
# 排除：写到 /tmp / .tmp / log / logs / .next / dist / build / .cache 是合法的
hits=$(grep -rnE 'fs\.(writeFileSync|writeFile|appendFile|appendFileSync)\(' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  src/ app/ apps/ backend/ api/ server/ pages/ routes/ . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -vE '/tmp/|os\.tmpdir|tempfile|process\.env\.TMPDIR|\.cache/|/log[s]?/|\.log[\\)\"'"'"',]' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Node 业务代码 fs.writeFileSync 写到非 tmp 非 log 路径（业务数据应入 PG）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 6. Python json.dump / pickle.dump 写到业务目录 ----
hits=$(grep -rnE '\b(json\.dump|pickle\.dump)\(' \
  --include='*.py' \
  src/ app/ apps/ backend/ api/ server/ . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -vE '/tmp/|tempfile|/log[s]?/|\.cache/' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Python 业务代码 json.dump / pickle.dump 写到业务目录（业务数据应入 PG）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 7. 顶层数据目录（data/ db/ storage/ uploads/）含 .json / .db / .sqlite 文件 ----
# 这是"用文件当持久化"的强信号
DATA_DIR_FILES=""
for d in data db storage uploads cache backend/data backend/storage app/data; do
  [ -d "$d" ] || continue
  # 排除 .gitkeep / README 等占位
  found=$(find "$d" -maxdepth 3 -type f \
    \( -name '*.json' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \
       -o -name '*.csv' -o -name '*.pickle' -o -name '*.pkl' \) \
    -not -name 'package.json' -not -name 'tsconfig.json' \
    -not -path '*/node_modules/*' 2>/dev/null | head -5)
  if [ -n "$found" ]; then
    DATA_DIR_FILES="$DATA_DIR_FILES$found"$'\n'
  fi
done
if [ -n "$DATA_DIR_FILES" ]; then
  report "顶层数据目录含 .json / .db / .csv 文件（看着像运行时数据；如确为静态资源/seed 应放到 app/seed/ 由 install.sh 灌入 PG）:"
  printf '%s' "$DATA_DIR_FILES" | sed 's/^/    /' >&2
fi

# ---- 8. localStorage / sessionStorage 当多用户业务存储用 ----
# 仅在前端代码里查；只看是否存了用户业务数据（用 setItem("user...", ...) 这类强信号）
hits=$(grep -rnE 'localStorage\.setItem\(\s*[\"'"'"'](users?|orders?|items?|cart|todos?|posts?|comments?|messages?|drafts?|notes?)' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "前端 localStorage 当业务存储（多用户共享业务数据应入 PG，前端只缓存 UI 状态）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项文件当 DB 反模式 - 详见 transform_prompt.md § 四" >&2
  exit 1
fi
echo "[OK] 无文件当 DB 反模式残留"
