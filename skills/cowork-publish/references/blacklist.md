# 禁止清单（黑名单速查）

> **何时读**：**写代码前不确定能不能做时读**。涵盖：平台不提供啥（§2）、zip 顶层禁项（§3.2）、不能装系统包（§10.3）、网络/部署/端口/持久化/DB/AI/SSO/路径 7 大类禁项（§11）。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 2. 平台提供 / 不提供

| 能力 | 平台提供 | 你必须自己做 |
|---|---|---|
| Python 3 / Node.js 运行时 | ✅ | — |
| PostgreSQL | ✅ 唯一持久化 | 业务表、幂等 seed、文件落 LO |
| AI 调用（Runway 网关） | ✅ 文本(Bedrock) + 图像(Google) | 用平台规定的协议调（§7） |
| SSO 用户身份 | ✅ `Decrypted-Userinfo` HTTP header | 解析 + auto-provision（§8） |
| 凭据注入 | ✅ `db.properties` + `ai.properties`（与 install.sh 同级） | 读这两个文件（§6.1 / §7.1）|
| 端口 3000 | ✅ 平台监听 | 业务 listen `0.0.0.0:${APP_PORT:-3000}`（默认 3000，平台可注入 `APP_PORT` 覆盖）|
| 蓝绿/灰度切流量 | ✅ 注入 `APP_PORT` | start.sh / 业务源码读 `APP_PORT`，**不要裸读** `PORT`（§5.2）|
| Redis / MQ / S3 / ES | ❌ **不提供** | 全部用 PG 替代 |
| Docker / K8s / Helm | ❌ 平台自己管 | **不要写** Dockerfile / Compose / K8s yaml |
| 公网出口 | ❌ Pod 无公网 | install.sh 只能用内部镜像 |
| 持久化磁盘 | ❌ Pod 文件系统是临时的 | 用户上传/生成的文件落 PG LO |
| 系统级 env（HOST/PORT/HOSTNAME） | ⚠️ 被 Node/系统占用 | 业务 env 必须 `APP_` 前缀（§5.3）|

---


### 3.2 顶层 zip 必须只有上述这些 + 业务源码

**禁止**出现在顶层（verifier `verify_zip_layout.sh` / `verify_no_dev_artifacts.sh` 会卡）：

- ❌ `Dockerfile` / `docker-compose.yml` / `.dockerignore`
- ❌ `Makefile`（平台不跑 make）
- ❌ `.env` / `.env.*`（业务 env 走平台表单 + `APP_` 前缀）
- ❌ `k8s/` / `helm/` / `chart/` / `*.yaml`（K8s 资源描述）
- ❌ `.github/` / `.gitlab-ci.yml` / `Jenkinsfile`（CI 配置）
- ❌ `node_modules/`（install.sh 会装）
- ❌ `.git/` / `.idea/` / `.vscode/`
- ❌ `__pycache__/` / `*.pyc` / `.pytest_cache/`
- ❌ `*.log` / `tmp/` / `coverage/`

---


### 10.3 禁止系统包安装

```bash
# ❌ install.sh 里出现就直接拒绝
apt-get install ffmpeg
yum install -y postgresql-client
brew install jq
```

如果实在需要某个二进制（ffmpeg / poppler / ...），告诉平台运维加进基础镜像，**不要**自己 install.sh 装。

---


## 11. 禁止清单（黑名单速查）

> 写完代码后用这个清单 grep 一遍，命中任何一项都要修。

### 11.1 网络/部署相关

| 模式 | 为什么禁 |
|---|---|
| `Dockerfile` / `docker-compose*` | 平台自己管容器 |
| `Makefile` | 平台不跑 make |
| `.env` / `.env.production` | 业务 env 走平台表单 + `APP_` 前缀 |
| `k8s/` / `helm/` / `Chart.yaml` | 平台自己管编排 |
| `.github/` / `.gitlab-ci.yml` / `Jenkinsfile` | 平台自己管 CI |
| `apt-get install ...` | 无公网 + 无 root |
| `curl https://... \| sh` | 无公网 |
| `pip install foo`（缺 `-i` 内部镜像） | 走公网失败 |
| `npm install foo`（缺 `.npmrc`） | 走公网失败 |

### 11.2 端口/Env

| 模式 | 为什么禁 |
|---|---|
| `app.listen(8080)` / `--port 8000`（写死非 3000） | 必须默认 3000 |
| `app.listen(3000)` 完全写死 | 必须用 `APP_PORT` 带 3000 默认值，verifier 反向检查 |
| `app.listen(port, 'localhost')` / `'127.0.0.1'` | bind host 必须 `0.0.0.0` |
| `process.env.PORT` / `os.environ.get("PORT")` | 系统 env 污染，应读 `APP_PORT` |
| `process.env.HOSTNAME` | 系统 env 污染，业务 env 必须 `APP_` 前缀 |
| `process.env.FOO_BAR`（缺 `APP_` 前缀） | 平台不注入 |

### 11.3 持久化/外部组件

| 模式 | 替代方案 |
|---|---|
| `redis` / `ioredis` / `aioredis` | PG 表 + advisory lock + LISTEN/NOTIFY |
| `bullmq` / `bull` / `celery` 用 Redis broker | PG `jobs` 表 + `FOR UPDATE SKIP LOCKED` |
| `kafka-node` / `amqplib` / `pika` | PG NOTIFY |
| `aws-sdk` S3 / `@aws-sdk/client-s3` | PG Large Object |
| `@elastic/elasticsearch` | PG `tsvector` + GIN |
| `mongodb` / `mongoose` | PG JSONB |
| `mysql` / `mysql2` | PG（平台只装 PG）|
| `sqlite3` / `better-sqlite3` / `lowdb` / `nedb` | PG |
| `tinydb` / `shelve` / `dbm` | PG |
| `multer.diskStorage` / `formidable` 写本地 | LO |
| `fs.writeFileSync('data/...')` | LO |
| `localStorage.setItem('users', ...)` | PG |

### 11.4 DB 连接

| 模式 | 为什么禁 |
|---|---|
| `f"postgresql://{user}:{password}@{host}/{db}"` | password 含 `@:/?#` 时 host 解析错位 |
| `\`postgresql://${user}:${password}@${host}\`` | 同上 |
| `"postgres://%s:%s@%s" % (...)` | 同上 |
| `new Pool({ connectionString: url })`（自己拼 URL） | 同上 |
| Alembic / Knex / Sequelize / Prisma / TypeORM migrate | 平台不跑迁移工具 |
| 裸 `CREATE TABLE foo` | 必须 `IF NOT EXISTS` |
| 裸 `INSERT INTO foo` | 必须 `ON CONFLICT` |

### 11.5 AI 调用

| 模式 | 为什么禁 |
|---|---|
| `import openai` / `OpenAI()` | 必须走 Runway 网关 |
| `import anthropic` / `from anthropic import` | 同上 |
| `@google/genai` / `google-generativeai`（直连） | 同上 |
| 直连 `api.openai.com` / `api.anthropic.com` | 同上 |
| `Authorization: Bearer xxx`（文本通路） | Runway 用 `token:` |
| 请求体传 `model` / `temperature` | 网关不接受 |
| 漏 `anthropic_version: "bedrock-2023-05-31"` | 网关拒绝 |
| 漏 `if (data.Code \|\| data.Error)` | 200 OK 业务错没人发现 |
| 图像调用用 `token:`（应该 `api-key:`） | 两条链路不互通 |
| 图像 `image_api_key or api_key` fallback | 独立计配额，缺时应 503 |

### 11.6 SSO

| 模式 | 为什么禁 |
|---|---|
| `jsonwebtoken` / `pyjwt` 自签 token | 平台已注入 SSO header |
| `passport` / `next-auth` / `clerk` | 同上 |
| 自己写 OAuth callback | 同上 |
| `req.session` / `cookie-session` | 每次读 header 即可 |
| 直接 `JSON.parse(req.headers['decrypted-userinfo'])` | 不重编码 → 中文乱码 |

### 11.7 路径/前端

| 模式 | 为什么禁 |
|---|---|
| `assetPrefix` / `basePath` / `publicPath` / `base` | 平台 router 自动注入前缀 |
| `fetch('/my-app/api/...')` | 同上 |
| `<img src="/my-app/...">` | 同上 |
| CSS `url(/images/x.png)` | router 不改 text/css |
| `app.use(compression())` | 废掉 router body filter |
| install.sh 里 `npm run build` | build 在改写机已做 |

---
