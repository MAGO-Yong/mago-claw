# 写完自检 Checklist

> **何时读**：**写完业务代码、调 cowork.publish 之前必读**。逐项过一遍：三件套 / 业务代码 / AI / SSO / 路径 / 依赖 / Zip 顶层。任何一条没过 → 部署多半 FAILED。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 12. 自检 Checklist（写完一定跑）

写完代码、准备打 zip 前，逐项打钩：

### 三件套
- [ ] 顶层有 `install.sh` / `start.sh` / `health.sh` 三个文件，都可执行
- [ ] `start.sh` 末行是 `exec ...`
- [ ] `start.sh` 用 `--port "${APP_PORT:-3000}"`（或业务源码读 `APP_PORT`），bind `0.0.0.0`
- [ ] start.sh 或业务源码至少一处出现 `APP_PORT` 字面量（verifier 反向检查）
- [ ] `health.sh` 探的是 `/health`（不是 `/api/health` 等）
- [ ] `health.sh` 用 `${APP_PORT:-3000}`

### 业务代码
- [ ] 如生成中文封面/头图，已按 `references/cover.md` 显式加载 CJK 字体（NotoSansCJK 等），没有 `ImageFont.load_default()` 导致的 `□□□`
- [ ] 主 app 顶层（不在带 prefix 的 router 上）有 `GET /health` 返 200
- [ ] 所有业务 env 都 `APP_` 前缀，没有裸读 `PORT` / `HOSTNAME` / `HOST`
- [ ] DB 连接用结构化 API（`URL.create` / 关键字参数 / `new Pool({})`），没 f-string / 模板拼 `password`
- [ ] DB 连接读 `db.properties` 的 6 个 key（**全部带 `db.` 前缀**：`db.type` / `db.host` / `db.port` / `db.username` / `db.password` / `db.database`）
- [ ] `db.properties` / `ai.properties` 都用顶层相对路径（如 `open("db.properties")`），**没**写成 `conf/db.properties` / `config/...`
- [ ] 没有越权读 `db.schema` / `db.driver` / `db.pool_size` / `db.url` 等平台不注入的 key
- [ ] 没有 `fs.writeFileSync` 写业务数据；用户上传走 PG Large Object
- [ ] 没有依赖 `redis` / `bullmq` / `aws-sdk` / `elasticsearch` / `mongodb` / `sqlite3` / `lowdb` 等
- [ ] 没有 Alembic / Knex / Sequelize / Prisma migrations
- [ ] `init_db.py` 里所有 `CREATE TABLE` / `CREATE INDEX` / `ALTER ... ADD COLUMN` / `CREATE TYPE` 都带 `IF NOT EXISTS`
- [ ] 所有 `INSERT INTO` 都带 `ON CONFLICT` 或 `WHERE NOT EXISTS`

### AI
- [ ] 没有 `openai` / `anthropic` / `langchain` SDK 直连，都走 Runway
- [ ] 文本调 `${ai.base_url}/bedrock_runtime/model/invoke`，header 用 `token:`
- [ ] 请求体含 `anthropic_version: "bedrock-2023-05-31"` + `max_tokens` + `messages`
- [ ] 请求体**不含** `model` / `temperature` / `top_p`
- [ ] 调用后 `if (data.Code || data.Error) throw`
- [ ] （如有图像）调 `${ai.image_base_url}/google/v1:generateContent`，header 用 `api-key:`
- [ ] 图像请求体含 `responseModalities: ["TEXT","IMAGE"]` 和 `maxOutputTokens >= 32768`
- [ ] 图像响应检查 `finishReason`
- [ ] 没有 `image_api_key or api_key` 这种 fallback

### SSO
- [ ] 从 `Decrypted-Userinfo` header 读用户
- [ ] 做了 `latin-1 → utf-8` 重编码（`Buffer.from(raw, 'latin1').toString('utf-8')` / `raw.encode('latin-1').decode('utf-8')`）
- [ ] 没有 `jsonwebtoken` / `passport` / `next-auth`
- [ ] 首次见到的 SSO 用户自动 upsert 到业务 user 表

### 路径
- [ ] 源码所有 fetch / `<img src>` / `router.push` 都用裸路径，不带应用前缀
- [ ] `next.config.*` / `vite.config.*` 里没有 `assetPrefix` / `basePath` / `base`
- [ ] CSS 里没有 `url(/...)`
- [ ] 没用 `compression` 中间件
- [ ] 前端有 `dist/` 或 `.next/standalone/` 已构建产物

### 依赖与安装
- [ ] `install.sh` 里 `pip install` 带 `-i http://pypi.devops.xiaohongshu.com/simple/ --trusted-host pypi.devops.xiaohongshu.com`
- [ ] `.npmrc` 在 zip 顶层，值不带引号
- [ ] `install.sh` 里没有 `apt-get` / `yum` / `brew` / `curl|sh` / `git clone https://github`
- [ ] `install.sh` 里没有 `alembic upgrade` / `prisma migrate` / `knex migrate` / `flyway` / `liquibase`

### Zip 顶层
- [ ] 没有 `Dockerfile` / `docker-compose*` / `Makefile`
- [ ] 没有 `.env` / `.env.*`
- [ ] 没有 `k8s/` / `helm/` / `.github/` / `.gitlab-ci.yml` / `Jenkinsfile`
- [ ] 没有 `node_modules/` / `__pycache__/` / `.venv/` / `.git/` / `.idea/` / `.vscode/`
- [ ] 没有 `*.log` / `tmp/` / `coverage/`

---
