#!/usr/bin/env bash
# 验证：依赖清单 + 代码 + 配置都不引用平台不提供的外部基础设施
# 覆盖：Redis / MQ / S3 / ES / Vector DB / Memcached
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

BANNED_NODE='"(ioredis|redis|node-redis|redis-mock|memjs|memcached|bullmq|bull|bee-queue|agenda|kafkajs|node-rdkafka|amqplib|nats|@aws-sdk/client-s3|aws-sdk|minio|@elastic/elasticsearch|meilisearch|typesense|@pinecone-database/pinecone|weaviate-client|@qdrant/js-client-rest)"'

# -- Node 依赖 --
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json frontend/package.json; do
  [ -f "$pkg" ] || continue
  hits=$(grep -nE "$BANNED_NODE" "$pkg" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "$pkg 含禁用外部基础设施 SDK:"
    echo "$hits" | sed 's/^/    /' >&2
    echo "[HINT] 目标文件 $pkg：从 dependencies/devDependencies 整段删掉上面所有禁用 SDK，并把代码中 import/require 改为：缓存→内存 Map / lru-cache；任务队列→同步执行；S3→PostgreSQL Large Object；ES→PostgreSQL ILIKE / pg_trgm；MQ→直接调函数" >&2
  fi
done

# -- Python 依赖 --
BANNED_PY='^[[:space:]]*(redis|aioredis|aredis|redis-py-cluster|celery|rq|dramatiq|huey|pymemcache|kafka-python|confluent-kafka|pika|nats-py|boto3|minio|elasticsearch|meilisearch|qdrant-client|pinecone-client|weaviate-client)([><=!~ ]|$)'
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -nE "$BANNED_PY" "$req" 2>/dev/null | grep -vE '^\s*#' || true)
  if [ -n "$hits" ]; then
    report "$req 含禁用外部基础设施 SDK:"
    echo "$hits" | sed 's/^/    /' >&2
    echo "[HINT] 目标文件 $req：删掉上面禁用包；同步删 import：redis/aioredis→functools.lru_cache 或 dict 兜底；celery/rq/dramatiq→同步函数调用；boto3/minio→读写 PostgreSQL Large Object（lo_create/lo_write）；elasticsearch→PostgreSQL ILIKE 或 pg_trgm" >&2
  fi
done

# -- 代码硬编本地基础设施端口 --
# 三条 pattern 并集：紧凑 host:port / 分离 port:6379 / 字符串 ":6379"
PORT_PATTERN='((127\.0\.0\.1|localhost):(6379|11211|9092|5672|6380|2181|9200|9300)|port[[:space:]]*[:=][[:space:]]*[\x27"]?(6379|11211|9092|5672|6380|2181|9200|9300)\b|[\x27"](:?(6379|11211|9092|5672|6380|2181|9200|9300))[\x27"])'
hits=$(grep -rnE "$PORT_PATTERN" \
  --include='*.ts' --include='*.js' --include='*.cjs' --include='*.mjs' \
  --include='*.py' --include='*.env*' --include='*.yaml' --include='*.yml' \
  --include='*.json' --include='*.toml' \
  . 2>/dev/null \
  | grep -vE '(node_modules|\.next/|dist/|build/|\.guard-transform|package-lock)' \
  | head -20 || true)
if [ -n "$hits" ]; then
  report "代码引用了 6379/11211/9092 等本地服务端口（Pod 上无人监听）:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的源码 / 配置文件。删除对应连接代码：6379(redis) / 11211(memcached) → 内存 dict / lru_cache；9092(kafka) / 5672(rabbitmq) → 同步调用；9200/9300(es) → PostgreSQL 全文检索。不要保留任何连这些端口的客户端实例化代码" >&2
fi

# -- 环境变量配置 --
hits=$(grep -rnE '(REDIS_URL|REDIS_HOST|KAFKA_BROKERS?|RABBITMQ_URL|CELERY_BROKER_URL|S3_BUCKET|ES_HOST|ELASTIC_URL)' \
  --include='*.env*' --include='*.yaml' --include='*.yml' --include='*.toml' \
  . 2>/dev/null \
  | grep -vE '(node_modules|\.guard-transform)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "配置含外部基础设施 URL（平台不注入这些 env）:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 .env / yaml / toml 配置文件。删除 REDIS_*/KAFKA_*/RABBITMQ_*/CELERY_BROKER_URL/S3_*/ES_*/ELASTIC_* 所有这些 env 行（平台 Pod 不会注入），同步从读取代码中删掉对应 os.environ.get / process.env 引用" >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项外部基础设施反模式残留 - 详见 transform_prompt.md § 四" >&2
  exit 1
fi
echo "[OK] 无禁用外部基础设施依赖"
