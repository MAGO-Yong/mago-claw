# 任务：移除外部基础设施 SDK，迁到 PostgreSQL

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

工程里出现了平台**不提供**的外部基础设施依赖（Redis / MQ / S3 / Elasticsearch / Memcached 等）。把它们**整体迁到 PostgreSQL**，并清干净依赖、配置、伴生进程。

## 检测信号（grep 自查）

- **Node 依赖**：`ioredis` / `redis` / `node-redis` / `bullmq` / `bull` / `kafkajs` / `amqplib` / `nats` / `@aws-sdk/client-s3` / `aws-sdk` / `minio` / `@elastic/elasticsearch` 等
- **Python 依赖**：`redis` / `aioredis` / `celery` / `rq` / `pymemcache` / `kafka-python` / `pika` / `boto3` / `minio` / `elasticsearch` 等
- **代码模式**：`new Redis(...)` / `createClient({url:...})` / `redis.set/get/hset` / `await redis.xxx` / `redisKey(...)`
- **配置**：`REDIS_URL` / `REDIS_HOST` / `KAFKA_BROKERS` / `RABBITMQ_URL` 等环境变量
- **代码硬编**：`127.0.0.1:6379` / `:11211` / `:9092` / `:5672`
- **伴生进程**：`redis-bridge` / `bullmq-worker` / `celery-worker` 等

## 怎么迁

| 原 | 改成 |
|---|---|
| Redis 当 KV 存业务实体 | PG 表 + UNIQUE 索引；字段固定就拆列，不固定就 JSONB |
| Redis TTL (`SET k v EX N`) | 加 `expires_at TIMESTAMPTZ` 列 + 后台清理 |
| INCR/INCRBY | `UPDATE counters SET v=v+1 WHERE k=$1 RETURNING v`（行级锁天然原子） |
| LIST/STREAM 当队列 | PG `queue` 表 + `SELECT ... FOR UPDATE SKIP LOCKED` |
| PUB/SUB | PG `LISTEN`/`NOTIFY`；多数业务直接同步 |
| 分布式锁 (`SET NX EX`) | PG `pg_advisory_lock(<key_hash>)` |
| BullMQ / Celery 任务队列 | 评估是否真异步：多数场景同步执行；必须异步用 PG `jobs` 表 + 同进程 worker |
| S3 / MinIO 存文件 | PostgreSQL Large Object（**不是 BYTEA**）；schema + 实现见下文 |
| Elasticsearch 全文检索 | PG `tsvector` + `GIN` 索引 |
| Memcached | 同 Redis，迁 PG |

## LO 文件存储模板（处理 S3 / 上传文件时强制用这套）

DDL（请加进 init_db）：
```sql
CREATE EXTENSION IF NOT EXISTS lo;
CREATE TABLE IF NOT EXISTS attachments (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  mime          TEXT NOT NULL,
  size_bytes    BIGINT NOT NULL,
  sha256        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_oid   OID NOT NULL
);
DROP TRIGGER IF EXISTS attachments_lo_cleanup ON attachments;
CREATE TRIGGER attachments_lo_cleanup
BEFORE UPDATE OR DELETE ON attachments
FOR EACH ROW EXECUTE FUNCTION lo_manage(content_oid);
```

## 必须做的清理

1. `package.json` / `requirements.txt` 移除上述所有 SDK
2. 删除"伴生进程"启动脚本（`startManagedRedisBridge()` 等）
3. 删除环境变量配置（`.env.example` 里的 `REDIS_URL` 等）
4. **不要**保留 `if (redis) { ... } else { pool.query(...) }` 双写折中——拆要拆干净

## seed / 初始化必须幂等（install.sh 每次发布都跑）

`install.sh` 在 Pod 上**每次发布都会执行**，不只是首次部署。任何非幂等 SQL 都会让第二次部署失败。

把 seed/初始化 SQL 写成：

```sql
-- ✅ 表创建
CREATE TABLE IF NOT EXISTS items (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  ...
);

-- ✅ 索引
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items (created_at);

-- ✅ 列追加
ALTER TABLE items ADD COLUMN IF NOT EXISTS extra JSONB;

-- ✅ INSERT seed 数据：UNIQUE/PK 冲突时跳过
INSERT INTO items (name, qty) VALUES ('foo', 1)
ON CONFLICT (name) DO NOTHING;

-- ✅ 或者用 NOT EXISTS 子查询
INSERT INTO items (name, qty)
SELECT 'bar', 2
WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'bar');

-- ✅ EXTENSION / TYPE
CREATE EXTENSION IF NOT EXISTS lo;
```

**反例**（第二次部署直接挂）：

```sql
-- ❌ relation "items" already exists
CREATE TABLE items (...);
-- ❌ duplicate key value violates unique constraint
INSERT INTO items (name) VALUES ('foo');
-- ❌ column "extra" already exists
ALTER TABLE items ADD COLUMN extra JSONB;
```

**ORM 替代**：如果用 SQLAlchemy / TypeORM 的 `create_all()` / `synchronize`，那已是幂等的；但**不要再叠加** Alembic / TypeORM-migrations 之类的迁移工具——平台不跑迁移，只跑 install.sh。

## PG 连接配置（坑大，单独拎出来）

迁到 PG 后，业务要从 `db.properties` 读 6 个标准 key（`db.host` / `db.port` / `db.database` / `db.username` / `db.password` / `db.schema`）拼连接。

**关键陷阱**：`db.password` 是平台用户在表单里填的**原始密码**，几乎一定含 `@` `:` `/` `?` `#` 等 URL 保留字符。f-string 拼 URL 会让 parser 把 `@` 之后的部分误识别成 host，运行时抛 `socket.gaierror: Name or service not known`。

**必须**用结构化 API（不要拼字符串）：

```python
# ✅ Python SQLAlchemy
from sqlalchemy import URL
engine = create_async_engine(URL.create(
    "postgresql+asyncpg",
    username=props["db.username"], password=props["db.password"],
    host=props["db.host"],         port=int(props["db.port"]),
    database=props["db.database"],
))

# ✅ Python asyncpg 直连
conn = await asyncpg.connect(
    user=u, password=p, host=h, port=int(port), database=d,
)

# ✅ Node pg
const pool = new Pool({user, password, host, port: Number(port), database});
```

```python
# ❌ 永远不要这样：含 @ : / ? # 的密码会让 host 解析错位
DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
```

实在要字符串（如写入旧版 ORM 的 conninfo）：先 `urllib.parse.quote(password, safe='')` / `encodeURIComponent(password)` 再拼。

## 验证（外层会自动跑）

- `verifiers/verify_no_external_infra.sh` —— 任何一项依赖 / 端口 / 配置残留都会报 FAIL
- `verifiers/verify_db_url_safe.sh` —— 检测到 `f"postgres...:{password}@"` / `${password}@` 这种危险拼接会报 FAIL
- `verifiers/verify_no_file_db.sh` —— 任何"文件当 DB"的反模式（lowdb/nedb/sqlite/json.dump 业务路径）都会报 FAIL
- `verifiers/verify_seed_idempotent.sh` —— seed SQL 缺 `IF NOT EXISTS` / `ON CONFLICT` 会报 FAIL
- `verifiers/verify_no_migrations_tool.sh` —— Alembic / Flyway / TypeORM-migrations / Knex-migrations 残留会报 FAIL
