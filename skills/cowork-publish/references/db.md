# 数据库（PostgreSQL via db.properties）

> **何时读**：**加任何持久化前必读**。包含：db.properties 6 个固定 key 格式、DB 连接为什么不能字符串拼 URL（password 含特殊字符崩）、DDL 必须幂等、文件存 PG Large Object（不写本地磁盘）、用 PG 模式替代 KV/MQ/Cache。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 6. 数据库（PostgreSQL 是唯一持久化）

### 6.1 `db.properties` 格式（6 个固定 key）

**文件位置（重要，常错）**：

- **物理路径**：**与 `install.sh` 完全同级**，即 `<zip 解压根>/db.properties`（**不是** `conf/db.properties`，也不是任何子目录）
- **生成方**：**平台运行时注入**——你**不要**在 zip 里带这个文件，也不要 commit 到 git；它若以任何路径出现在 zip 里都会被 [`stage_60_package.py`](../guardx/stages_py/stage_60_package.py) 的 `_assert_no_banned_in_zip` 拒绝
- **业务读取**：用 **相对路径** `"db.properties"`（前提：`start.sh` / `install.sh` 第一行的 `cd "$(dirname "$0")"` 已经把 cwd 切到 install.sh 所在目录）
- **.gitignore 必加**：

  ```gitignore
  db.properties
  ai.properties
  ```

文件内容格式（平台生成）—— **注意 key 全部带 `db.` 前缀**（与 `ai.properties` 的 `ai.` 前缀对称）：

```properties
db.type=postgresql
db.host=10.x.x.x
db.port=5432
db.username=app_user
db.password=raw-password-may-contain@:/?#
db.database=app_db
```

**注意**：

- key 严格是 `db.type` / `db.host` / `db.port` / `db.username` / `db.password` / `db.database`（**必须带 `db.` 前缀**；不是 `username` 也不是 `db.user` / `db.pwd` / `db.db`）
- 平台**只**注入这 6 个 key —— 不要在代码里读 `db.schema` / `db.driver` / `db.pool_size` / `db.url` 这类越权 key（verifier `verify_db_props_keys.sh` 会卡）；这些参数请在代码里写默认值
- `db.password` 是用户原始密码，几乎**一定包含 `@` `:` `/` `?` `#`** 等 URL 保留字符（→ §6.2）
- 本地开发时（**仅 power-user / 用户手动，不是 agent 路径**）自己手写一份放在仓库根的 `db.properties`（已被 gitignore），跑 `bash start.sh` 即可。**agent 默认 publish-first**，不要代用户本地起服务验证

读取示例（Python，路径相对 install.sh 所在目录）：

```python
# 平台 start.sh `cd "$(dirname "$0")"` 后再 exec，业务进程 cwd 即 install.sh 同级目录，
# 所以 "db.properties" 相对路径可直接命中；本地开发也保持同样 cwd 即可。
def load_db_props(path="db.properties"):
    props = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            k, _, v = line.partition("=")
            props[k.strip()] = v.strip()
    return props
```

### 6.2 DB 连接：**严禁** 字符串拼 password

这是 Guard 平台最常见的踩坑（verifier `verify_db_url_safe.sh` 会扫）。

```python
# ❌ 全错：password 含 @ : / 时，URL parser 会把 @ 之后的部分当 host → socket.gaierror
url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
url = "postgresql://%s:%s@%s/%s" % (user, password, host, db)
url = "postgresql://" + user + ":" + password + "@" + host

# ✅ Python SQLAlchemy —— props 的 key 全部带 db. 前缀
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(URL.create(
    "postgresql+asyncpg",
    username=props["db.username"],
    password=props["db.password"],
    host=props["db.host"],
    port=int(props["db.port"]),
    database=props["db.database"],
))

# ✅ Python asyncpg（关键字参数）
conn = await asyncpg.connect(
    user=props["db.username"], password=props["db.password"],
    host=props["db.host"], port=int(props["db.port"]),
    database=props["db.database"],
)
```

```javascript
// ❌ 全错
const url = `postgresql://${user}:${password}@${host}:${port}/${database}`
new Pool({ connectionString: url })

// ✅ Node pg（对象参数）—— props 的 key 全部带 db. 前缀
const { Pool } = require('pg')
const pool = new Pool({
  user:     props['db.username'],
  password: props['db.password'],
  host:     props['db.host'],
  port:     Number(props['db.port']),
  database: props['db.database'],
})
```

实在要拼字符串：先 `urllib.parse.quote(props["db.password"], safe='')` 或 `encodeURIComponent(props['db.password'])` 转义。

### 6.3 文件存储：用 PG Large Object，不要写本地磁盘

Pod 文件系统是临时的，重启即丢。用户上传的图片/附件/二进制必须落 PG。

```python
# 用 PG Large Object（LO）存二进制
# 表结构：
#   CREATE TABLE IF NOT EXISTS files (
#     id SERIAL PRIMARY KEY,
#     filename TEXT NOT NULL,
#     content_type TEXT,
#     oid OID NOT NULL,        -- 指向 LO
#     size BIGINT,
#     created_at TIMESTAMPTZ DEFAULT NOW()
#   );

async def save_file(conn, filename, content_type, blob):
    oid = await conn.fetchval("SELECT lo_create(0)")
    fd = await conn.fetchval("SELECT lo_open($1, $2)", oid, 0x40000)  # write
    await conn.execute("SELECT lowrite($1, $2)", fd, blob)
    await conn.execute("SELECT lo_close($1)", fd)
    await conn.execute(
        "INSERT INTO files (filename, content_type, oid, size) VALUES ($1, $2, $3, $4)",
        filename, content_type, oid, len(blob),
    )
```

**禁止反模式**（verifier `verify_no_file_db.sh` 会扫）：

- ❌ `fs.writeFileSync('data/users.json', ...)`（业务数据写本地）
- ❌ `sqlite3.connect("app.db")`（本地 sqlite 文件）
- ❌ `tinydb` / `shelve` / `lowdb` / `nedb` / `node-json-db` / `better-sqlite3` / `keyv-file`
- ❌ `json.dump(data, open("storage/x.json", "w"))`
- ❌ 顶层目录 `data/` / `db/` / `storage/` / `uploads/` 里放 `.json` / `.db` / `.csv`（这是"用文件当 DB"的强信号）
- ❌ 前端 `localStorage.setItem('users', ...)` 当业务持久化（前端只能缓存 UI 状态，多用户共享数据必须入 PG）

**例外**（合法）：写 `/tmp/` / `tempfile` / `.cache/` / `logs/` 是临时文件，不算 DB。

### 6.4 DB 初始化必须**幂等**（每次发布都跑 install.sh）

install.sh 每次发布都会跑，所以 `init_db.py` / `seed_db.py` 里所有 SQL **必须**满足：

```sql
-- ✅ 全部加 IF NOT EXISTS
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  ...
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname TEXT;
CREATE TYPE IF NOT EXISTS user_role AS ENUM ('admin', 'user');
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ✅ INSERT 必须带 ON CONFLICT
INSERT INTO users (email, nickname) VALUES ('admin@example.com', 'Admin')
  ON CONFLICT (email) DO NOTHING;

INSERT INTO config (key, value) VALUES ('version', '1.0')
  ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- ✅ 或者：WHERE NOT EXISTS 子查询
INSERT INTO roles (name)
SELECT 'admin' WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'admin');
```

**绝对禁止**（verifier `verify_seed_idempotent.sh` / `verify_no_migrations_tool.sh` 会卡）：

- ❌ 裸 `CREATE TABLE foo (...)`（第二次部署 `relation already exists`）
- ❌ 裸 `INSERT INTO users VALUES (...)`（第二次部署唯一键冲突）
- ❌ 用 Alembic / Knex / Sequelize / Prisma / TypeORM 的 migrations 目录 —— 平台不跑迁移工具
- ❌ 提交 `alembic.ini` / `knexfile.js` / `prisma/migrations/` / `migrations/*.js`

### 6.5 替代外部 KV / MQ / Cache 的 PG 模式

| 想用 | 用 PG 怎么做 |
|---|---|
| Redis cache | 表 `cache(key TEXT PRIMARY KEY, value JSONB, expires_at TIMESTAMPTZ)` + 定时 DELETE |
| Redis session | 表 `sessions(sid TEXT PRIMARY KEY, data JSONB, expires_at TIMESTAMPTZ)` |
| Redis pub/sub | PG `LISTEN` / `NOTIFY` |
| Redis 锁 | `SELECT pg_try_advisory_lock(hash)` |
| MQ / Bull | 表 `jobs(id, payload, status, locked_at, run_at)` + `SELECT ... FOR UPDATE SKIP LOCKED` |
| S3 文件 | PG Large Object（§6.3）|
| Elasticsearch 全文 | PG `tsvector` + `GIN` 索引 + `pg_trgm` 模糊 |

---
