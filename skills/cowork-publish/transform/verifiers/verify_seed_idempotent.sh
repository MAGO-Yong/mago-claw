#!/usr/bin/env bash
# 验证：DB seed/初始化必须幂等（INSERT ... ON CONFLICT / 先查再插 / CREATE TABLE IF NOT EXISTS）
# 详见 transform_prompt.md § 四 "seed 必须幂等"
#
# 关键事实：
#   - install.sh 在 Pod 每次发布都会跑（不只是首次部署）
#   - 非幂等 seed 会在第二次部署时 INSERT 失败 → install.sh 退出非 0 → 部署失败
#
# 检查范围：
#   - app/seed/, backend/seed/, seeds/, db/seed/, migrations/seed*
#   - install.sh 中调用的 SQL 文件
#
# 检查项：
#   1) CREATE TABLE 必须带 IF NOT EXISTS
#   2) CREATE INDEX 必须带 IF NOT EXISTS（PG 9.5+ 支持）
#   3) INSERT INTO 必须带 ON CONFLICT 子句 或 在 NOT EXISTS 子查询里
#      （或者用 INSERT ... SELECT ... WHERE NOT EXISTS）
#   4) ALTER TABLE ADD COLUMN 必须带 IF NOT EXISTS（PG 9.6+）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# ---- 收集 seed SQL 文件 ----
SEED_FILES=""
for d in app/seed seed seeds backend/seed backend/seeds db/seed db/seeds \
         migrations/seed app/db/seed backend/db/seed; do
  [ -d "$d" ] || continue
  found=$(find "$d" -type f -name '*.sql' 2>/dev/null || true)
  [ -n "$found" ] && SEED_FILES="$SEED_FILES$found"$'\n'
done

# install.sh 里 source 的 .sql / psql -f xxx.sql
if [ -f install.sh ]; then
  INSTALLED_SQL=$(grep -oE 'psql[^|;]*-f[[:space:]]+[^[:space:]]+\.sql|psql[^|;]*<[[:space:]]*[^[:space:]]+\.sql|<[[:space:]]+[^[:space:]]+\.sql' install.sh 2>/dev/null \
    | grep -oE '[^[:space:]<]+\.sql' || true)
  for sql in $INSTALLED_SQL; do
    [ -f "$sql" ] && SEED_FILES="$SEED_FILES$sql"$'\n'
  done
fi

# 去重 + 去空行
SEED_FILES=$(printf '%s' "$SEED_FILES" | sort -u | grep -v '^$' || true)

if [ -z "$SEED_FILES" ]; then
  echo "[OK] 未发现 seed SQL 文件（跳过）"
  exit 0
fi

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

for f in $SEED_FILES; do
  [ -f "$f" ] || continue

  # 跳过空文件
  [ -s "$f" ] || continue

  # ---- 1. CREATE TABLE 缺 IF NOT EXISTS ----
  hits=$(grep -niE '^[[:space:]]*CREATE[[:space:]]+TABLE\b' "$f" 2>/dev/null \
    | grep -ivE 'IF[[:space:]]+NOT[[:space:]]+EXISTS' \
    | grep -ivE 'CREATE[[:space:]]+(TEMP|TEMPORARY|UNLOGGED)' || true)
  if [ -n "$hits" ]; then
    report "$f 中 CREATE TABLE 缺 IF NOT EXISTS（再次部署会报 already exists）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi

  # ---- 2. CREATE [UNIQUE] INDEX 缺 IF NOT EXISTS ----
  hits=$(grep -niE '^[[:space:]]*CREATE[[:space:]]+(UNIQUE[[:space:]]+)?INDEX\b' "$f" 2>/dev/null \
    | grep -ivE 'IF[[:space:]]+NOT[[:space:]]+EXISTS' || true)
  if [ -n "$hits" ]; then
    report "$f 中 CREATE INDEX 缺 IF NOT EXISTS:"
    echo "$hits" | sed 's/^/    /' >&2
  fi

  # ---- 3. INSERT INTO 必须带 ON CONFLICT 或 WHERE NOT EXISTS ----
  # 找出所有 INSERT INTO 行号；然后对每一段 INSERT ... ; 检查是否含 ON CONFLICT
  # 简化方法：先找 INSERT INTO 的行，再看到下一个 ; 之间是否有 ON CONFLICT / NOT EXISTS
  if grep -niE '^[[:space:]]*INSERT[[:space:]]+INTO\b' "$f" 2>/dev/null | head -1 | grep -q .; then
    # 用 awk 把 INSERT 段切出来，每段判断是否含 ON CONFLICT / WHERE NOT EXISTS
    BAD_INSERTS=$(awk '
      BEGIN { stmt=""; in_insert=0; start_line=0 }
      /^[[:space:]]*INSERT[[:space:]]+INTO\b/ {
        if (in_insert && stmt != "") {
          if (tolower(stmt) !~ /on[[:space:]]+conflict|where[[:space:]]+not[[:space:]]+exists/) {
            print start_line ": " stmt;
          }
        }
        in_insert=1; stmt=$0; start_line=NR; next
      }
      in_insert {
        stmt = stmt " " $0;
        if (/;[[:space:]]*$/ || /;[[:space:]]*--/) {
          if (tolower(stmt) !~ /on[[:space:]]+conflict|where[[:space:]]+not[[:space:]]+exists/) {
            sub(/^[[:space:]]+/, "", stmt);
            # 截断长 SQL 输出
            if (length(stmt) > 160) stmt = substr(stmt, 1, 160) "...";
            print start_line ": " stmt;
          }
          in_insert=0; stmt=""
        }
      }
      END {
        if (in_insert && stmt != "" && tolower(stmt) !~ /on[[:space:]]+conflict|where[[:space:]]+not[[:space:]]+exists/) {
          if (length(stmt) > 160) stmt = substr(stmt, 1, 160) "...";
          print start_line ": " stmt;
        }
      }
    ' "$f" | head -10 || true)
    if [ -n "$BAD_INSERTS" ]; then
      report "$f 中 INSERT 缺 ON CONFLICT 或 WHERE NOT EXISTS（再次部署会唯一键冲突）:"
      echo "$BAD_INSERTS" | sed 's/^/    /' >&2
    fi
  fi

  # ---- 4. ALTER TABLE ADD COLUMN 缺 IF NOT EXISTS ----
  hits=$(grep -niE '^[[:space:]]*ALTER[[:space:]]+TABLE.*ADD[[:space:]]+COLUMN\b' "$f" 2>/dev/null \
    | grep -ivE 'IF[[:space:]]+NOT[[:space:]]+EXISTS' || true)
  if [ -n "$hits" ]; then
    report "$f 中 ALTER TABLE ADD COLUMN 缺 IF NOT EXISTS:"
    echo "$hits" | sed 's/^/    /' >&2
  fi

  # ---- 5. CREATE TYPE / CREATE EXTENSION ----
  hits=$(grep -niE '^[[:space:]]*CREATE[[:space:]]+(TYPE|EXTENSION)\b' "$f" 2>/dev/null \
    | grep -ivE 'IF[[:space:]]+NOT[[:space:]]+EXISTS' || true)
  if [ -n "$hits" ]; then
    report "$f 中 CREATE TYPE/EXTENSION 缺 IF NOT EXISTS:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项 seed 不幂等问题 - 详见 transform_prompt.md § 四" >&2
  exit 1
fi
echo "[OK] seed SQL 全部幂等"
