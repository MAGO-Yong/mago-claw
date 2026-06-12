#!/usr/bin/env bash
# 验证：交付物里没有迁移工具
# 详见 transform_prompt.md § 四
#
# 平台范围：产物（output）只支持 Python / Node 后端；输入工程不限语言
#   - Python 系：Alembic
#   - Node 系：TypeORM-migrations / Knex / Sequelize / Prisma migrate
#   - 防御性检查（输入可能是 Java/Spring）：Flyway / Liquibase 不能残留进 install.sh
# 为什么：
#   - 平台不跑 alembic upgrade / typeorm migration:run / prisma migrate / knex migrate / flyway / liquibase
#   - 平台只跑 install.sh
#   - 留这些工具会让运维误以为要手工执行迁移
#   - 所有"迁移"都改成 install.sh 执行的幂等 SQL（CREATE TABLE IF NOT EXISTS / ALTER ... IF NOT EXISTS）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. Python: alembic ----
hits=$(find . -maxdepth 3 -type f \( -name 'alembic.ini' -o -name 'env.py' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' -not -path '*/.venv/*' -not -path '*/venv/*' \
  2>/dev/null | head -10 || true)
ALEMBIC_INI=$(echo "$hits" | grep -E '/alembic\.ini$' || true)
if [ -n "$ALEMBIC_INI" ]; then
  report "工程含 alembic.ini（平台不跑 alembic upgrade，应改成 install.sh 跑幂等 SQL）:"
  echo "$ALEMBIC_INI" | sed 's/^/    /' >&2
fi
ALEMBIC_DIRS=$(find . -maxdepth 3 -type d \( -name 'alembic' -o -name 'migrations' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' -not -path '*/.venv/*' 2>/dev/null | head -10 || true)
if [ -n "$ALEMBIC_DIRS" ]; then
  for d in $ALEMBIC_DIRS; do
    # 仅当目录里含 versions/ + env.py 才算 alembic
    if [ -d "$d/versions" ] && [ -f "$d/env.py" ]; then
      report "$d 是 alembic migrations 目录（应迁到 app/seed/init.sql）"
    fi
  done
fi

# Python 依赖里 alembic
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -niE '^[[:space:]]*alembic([><=!~ ]|$)' "$req" 2>/dev/null | grep -vE '^\s*#' || true)
  if [ -n "$hits" ]; then
    report "$req 含 alembic 依赖:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 2. Node: TypeORM migrations / Knex / Sequelize migrations / Prisma migrate ----
# Knex
hits=$(find . -maxdepth 3 -type f -name 'knexfile.*' \
  -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null | head -5 || true)
if [ -n "$hits" ]; then
  report "工程含 knexfile（Knex migrate）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# Prisma migrate（仅当 prisma/migrations 目录存在）
if [ -d prisma/migrations ] && [ "$(ls prisma/migrations 2>/dev/null | head -1)" ]; then
  report "工程含 prisma/migrations 目录（平台不跑 prisma migrate；改用 prisma db push 或 SQL）"
fi
if [ -d backend/prisma/migrations ] && [ "$(ls backend/prisma/migrations 2>/dev/null | head -1)" ]; then
  report "工程含 backend/prisma/migrations 目录"
fi

# Sequelize
SEQ_DIRS=$(find . -maxdepth 4 -type d -name 'migrations' \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' -not -path '*/alembic/*' 2>/dev/null | head -10 || true)
for d in $SEQ_DIRS; do
  # 含 .js / .ts 文件 + 有 sequelize / typeorm 依赖才算
  if [ -n "$(find "$d" -maxdepth 1 -type f \( -name '*.js' -o -name '*.ts' \) 2>/dev/null | head -1)" ]; then
    HAS_SEQ_OR_TYPEORM=0
    for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json; do
      [ -f "$pkg" ] || continue
      grep -qE '"(sequelize|typeorm|@mikro-orm/migrations)"' "$pkg" 2>/dev/null && HAS_SEQ_OR_TYPEORM=1 && break
    done
    if [ "$HAS_SEQ_OR_TYPEORM" = "1" ]; then
      report "$d 是 Sequelize/TypeORM/MikroORM migrations 目录（平台不跑 ORM migrate；改 install.sh 幂等 SQL）"
    fi
  fi
done

# package.json 里有 typeorm migration / sequelize-cli 命令
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$pkg" ] || continue
  hits=$(grep -nE '"(typeorm[[:space:]]+migration|sequelize-cli|sequelize[[:space:]]+db:migrate|prisma[[:space:]]+migrate|knex[[:space:]]+migrate)' "$pkg" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "$pkg scripts 含迁移命令（install.sh 不会调用，运维会被误导）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 3. install.sh 不能调用迁移工具 ----
if [ -f install.sh ]; then
  # 防御性检查：即使输入是 Java/Spring，转写后 install.sh 也不能残留 flyway/liquibase 调用
  hits=$(grep -nE 'alembic[[:space:]]+(upgrade|downgrade|revision)|flyway[[:space:]]+(migrate|info)|liquibase[[:space:]]+(update|status)|typeorm[[:space:]]+migration:run|sequelize[[:space:]]+db:migrate|prisma[[:space:]]+migrate|knex[[:space:]]+migrate' \
    install.sh 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "install.sh 调用迁移工具（应改成 psql -f app/seed/init.sql 执行幂等 SQL）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项迁移工具残留 - 详见 transform_prompt.md § 四" >&2
  exit 1
fi
echo "[OK] 无迁移工具残留（install.sh 走幂等 SQL）"
