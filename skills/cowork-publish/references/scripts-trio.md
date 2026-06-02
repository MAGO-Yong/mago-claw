# 三件套脚本规范（install.sh / start.sh / health.sh）+ 端口环境变量

> **何时读**：改三件套脚本 / 改端口 / 改环境变量时读。scaffold 已经给好这三个脚本，**正常情况下不要手改**——只在 scaffold 出来跑不起来时再读。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 4. 三件套脚本（install.sh / start.sh / health.sh）

> **重要**：这三个文件**必须在 zip 顶层**，文件名必须**完全一致**，必须是 `#!/usr/bin/env bash` 或 `#!/bin/sh` 开头，必须可执行（`chmod +x`）。
>
> 推荐做法：**直接复用** [`templates/install.sh.tpl`](../templates/install.sh.tpl) / [`templates/start.sh.tpl`](../templates/start.sh.tpl) / [`templates/health.sh.tpl`](../templates/health.sh.tpl) 渲染出来的版本，下面给出最小可用骨架。

### 4.1 `install.sh`（每次发布都会跑，必须幂等）

```bash
#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"

# Python 依赖：内部 pypi 镜像
if [ -f requirements.txt ]; then
  if [ "$(uname)" = "Linux" ]; then
    python3 -m venv .venv
    . .venv/bin/activate
    pip install --no-cache-dir -r requirements.txt \
      -i http://pypi.devops.xiaohongshu.com/simple/ \
      --trusted-host pypi.devops.xiaohongshu.com
    deactivate
  fi
fi

# Node 依赖：.npmrc 已配双路内部 registry
if [ -f package.json ] && [ ! -f .next/standalone/server.js ]; then
  npm ci --omit=dev
fi

# DB 初始化：必须幂等（CREATE TABLE IF NOT EXISTS / ON CONFLICT）
if [ -f app/init_db.py ]; then
  [ -f .venv/bin/activate ] && . .venv/bin/activate
  python -m app.init_db
fi

echo "[install] done"
```

**绝对禁止**（verifier `verify_install_no_internet.sh` / `verify_no_migrations_tool.sh` 会卡）：

- ❌ `apt-get install` / `yum install` / `brew install`（平台 Pod 没有 root，也没公网）
- ❌ `curl https://... | sh` / `wget https://github.com/...`（无公网）
- ❌ `pip install foo`（缺 `-i 内部镜像 --trusted-host`，会去公网）
- ❌ `npm install foo`（缺 `.npmrc`，会去公网）
- ❌ `alembic upgrade` / `prisma migrate` / `knex migrate` / `sequelize db:migrate` / `typeorm migration:run` / `flyway` / `liquibase`（平台不跑迁移工具，所有 DDL 改成 `init_db.py` 里的幂等 SQL）

### 4.2 `start.sh`（拉起业务主进程，末行必须 `exec`）

```bash
#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"

# 激活 venv（仅 Linux + 有 Python 依赖时）
[ -f .venv/bin/activate ] && . .venv/bin/activate

# 末行 exec：让业务进程接管 PID 1，正确接收 SIGTERM
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-3000}"
# Node 版本：APP_PORT="${APP_PORT:-3000}" exec node dist/server.js
# Next standalone: APP_PORT="${APP_PORT:-3000}" exec node .next/standalone/server.js
```

**关键点**：

- 末行必须 `exec ...`（不能后台跑、不能 `&`、不能多条 nohup），否则平台 SIGTERM 收不到 → 优雅停机失败
- `--host 0.0.0.0`（不是 `127.0.0.1`，不是 `localhost`，否则平台 ingress 转不进来）
- 端口**强烈推荐** `"${APP_PORT:-3000}"`（`APP_PORT` 是平台官方注入的业务 env，默认值 3000 兜底本地开发）
  - ❌ **不要**裸读 `process.env.PORT` / `os.environ.get("PORT")` —— `PORT` 是系统 env，Node / Pod 环境会被污染
  - ❌ **不要**完全写死 `--port 3000` —— verifier `verify_app_env_naming.sh` 会反向检查 start.sh 或业务源码至少一处出现 `APP_PORT` 字面量
  - 详见 §5.1 / §5.2
- 输出必须直写 stdout/stderr（不要 `> log.txt`，平台从 stdout 收日志）

### 4.3 `health.sh`（探活，必须探 `/health`）

```sh
#!/bin/sh
curl -fsS -o /dev/null --max-time 3 "http://127.0.0.1:${APP_PORT:-3000}/health" || exit 1
```

**关键点**（verifier `verify_health_consistency.sh` 会卡）：

- 路径**必须**是 `/health`（不能 `/api/health` / `/healthz` / `/actuator/health` / `/ping`）—— 这是 Guard 平台对所有子应用的**统一探活契约**
- 端口必须用 `${APP_PORT:-3000}` 写法 —— 蓝绿场景平台会用 `APP_PORT=3001` 起新版本探活
- 业务必须真的在主 app 顶层暴露 `GET /health`（**不能挂在带 prefix 的 router/blueprint 上**，否则真实路径会变 `/api/health`，探活 404）

正确的 `/health` 实现（必须挂主 app 顶层）：

```python
# FastAPI ✅
@app.get("/health")
def health(): return {"ok": True}

# ❌ 错误：挂在带 prefix 的 router 上
router = APIRouter(prefix="/api")
@router.get("/health")  # 真实路径变 /api/health，探活 404
def health(): return {"ok": True}
```

```javascript
// Express ✅
app.get('/health', (req, res) => res.json({ ok: true }))
// Koa ✅
router.get('/health', ctx => { ctx.body = { ok: true } })
```

---


## 5. 端口与环境变量

### 5.1 端口契约

- **默认端口** `3000`（不是 8000 / 8080 / 5000）—— 这是 Guard 平台对所有子应用的统一约定
- **业务实际监听** `0.0.0.0:${APP_PORT:-3000}`（**强烈推荐**用 `APP_PORT` 带 3000 默认值，不要把 3000 完全写死）
- **bind host 必须** `0.0.0.0`（不是 `127.0.0.1` / `localhost`，否则平台 ingress 转不进来）
- **探活走** `127.0.0.1:${APP_PORT:-3000}/health`（与监听端口一致）

### 5.2 `APP_PORT`（必须读，verifier 会反向检查）

- 平台会在 Pod 启动时注入 `APP_PORT` 环境变量；蓝绿/灰度切流量时可能用 `APP_PORT=3001` 起新版本
- **必须**：start.sh 或业务源码至少一处出现 `APP_PORT` 字面量 —— verifier `verify_app_env_naming.sh` 没找到会 FAIL
- **推荐姿势（任选其一即可）**：
  - 在 `start.sh` 里 `exec ... --port "${APP_PORT:-3000}"`（最简单，业务源码不用改）
  - 业务源码读 `APP_PORT`（见 §5.3 示例），start.sh 里 `export APP_PORT="${APP_PORT:-3000}"` 后再 exec
- **绝对禁止**：
  - ❌ 裸读 `process.env.PORT` / `os.environ.get("PORT")` —— `PORT` 是系统 env，Node / 平台基础设施会污染
  - ❌ 把 3000 完全写死（如 `app.listen(3000)`）—— 蓝绿场景平台端口注入失效，且 verifier 反向检查不过

### 5.3 业务 env 必须 `APP_` 前缀

平台只允许业务声明 **以 `APP_` 开头** 的环境变量。原因：

- Node 自动注入 `HOSTNAME` `PORT` `NODE_ENV` 等系统 env，业务裸读会拿到错值
- DB / AI 走顶层的 `db.properties` / `ai.properties`（与 install.sh 同级），不是 env

```javascript
// ❌ 错误：裸读系统 env / 写死端口
const port = process.env.PORT                  // 系统 env，会被污染
const port = 3000                              // 完全写死，蓝绿场景注入失效 + verifier FAIL
const host = process.env.HOSTNAME              // 系统 env，会被 Pod 主机名污染
const feature = process.env.FEATURE_FLAG      // 业务 env 必须 APP_ 前缀

// ✅ 正确：APP_PORT 带 3000 默认值 + 业务 env APP_ 前缀
const port = Number(process.env.APP_PORT) || 3000   // ⭐ APP_PORT 在白名单
const host = '0.0.0.0'                              // host 固定 0.0.0.0
const feature = process.env.APP_FEATURE_FLAG        // 业务 env 必须 APP_*
```

```python
# ❌ 错误
port = int(os.environ.get("PORT", "3000"))     # PORT 是系统 env
port = 3000                                    # 完全写死，蓝绿注入失效
api_url = os.environ.get("API_URL")            # 缺 APP_ 前缀

# ✅ 正确
port = int(os.environ.get("APP_PORT", "3000")) # ⭐ APP_PORT 带 3000 默认值
api_url = os.environ.get("APP_API_URL")        # 业务 env 必须 APP_ 前缀
```

**白名单（允许裸读，不需要 `APP_` 前缀）**：`NODE_ENV` / `NODE_OPTIONS` / `PYTHONPATH` / `PATH` / `HOME` / `TZ` / `LANG` / `LC_*` / `npm_config_*` / `npm_package_*` / `VIRTUAL_ENV` / `APP_PORT`。Next.js standalone 的 `.next/standalone/server.js` 自动读 `HOSTNAME` / `PORT` 是平台兼容的例外，不算违规。

---
