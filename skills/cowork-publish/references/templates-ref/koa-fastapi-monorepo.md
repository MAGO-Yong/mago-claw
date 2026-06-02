# koa-fastapi-monorepo 模板参考

> **何时读**：选用 `koa-fastapi-monorepo` 模板后写业务代码时读。
>
> 适用场景：**前端 Node + 后端 Node 分仓**。profile 名字里有 "fastapi" 是历史命名，**实际后端是 Koa/Express**（不是 Python）。
>
> 整个项目纯 Node 技术栈：前端 React + Vite，后端 Koa（可换 Express / Fastify）。

## scaffold 已给好

调 `cowork.scaffold_app({ template: 'koa-fastapi-monorepo' })` 后：

```
<srcDir>/
├── backend/                 # Koa 后端
│   ├── src/
│   │   ├── server.js        # Koa app + 路由 + 静态托管
│   │   ├── db.js            # pg 连接 + 关键字参数
│   │   ├── init-db.js       # DDL 幂等
│   │   ├── sso.js           # Decrypted-Userinfo 解析
│   │   └── ai.js            # Runway 调用
│   ├── package.json
│   ├── package-lock.json
│   └── .npmrc
├── frontend/                # React + Vite SPA
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── .npmrc
├── install.sh               # cd backend && npm ci --omit=dev
├── start.sh                 # cd backend; exec node src/server.js
├── health.sh                # curl /health
├── prepack.sh               # build frontend dist
└── README.md
```

## 关键：backend Koa 静态托管 frontend/dist

`backend/src/server.js`：

```javascript
const Koa = require('koa')
const Router = require('@koa/router')
const serve = require('koa-static')
const path = require('path')
const fs = require('fs')

const PORT = parseInt(process.env.APP_PORT || '3000', 10)
const HOST = '0.0.0.0'
const FRONTEND_DIST = path.resolve(__dirname, '..', '..', 'frontend', 'dist')
const INDEX_HTML = path.join(FRONTEND_DIST, 'index.html')

const app = new Koa()
const router = new Router()

// ⚠️ /health 顶层（health.sh 探的就是这个）
router.get('/health', (ctx) => {
  ctx.body = { ok: true }
})

// API 路由用 /api/* 前缀
router.get('/api/health', (ctx) => {
  ctx.body = { ok: true, service: 'koa-monorepo' }
})

// ... 业务 API 在这里 ...

app.use(router.routes()).use(router.allowedMethods())

// 静态文件：frontend/dist 下的所有文件
app.use(serve(FRONTEND_DIST, { index: false }))

// SPA history fallback：除 /api/* 以外的路径都返 index.html
app.use(async (ctx, next) => {
  if (ctx.method !== 'GET' || ctx.path.startsWith('/api/')) {
    return next()
  }
  if (fs.existsSync(INDEX_HTML)) {
    ctx.type = 'html'
    ctx.body = fs.createReadStream(INDEX_HTML)
  } else {
    ctx.status = 503
    ctx.body = { error: 'frontend/dist 未 build' }
  }
})

app.listen(PORT, HOST, () => {
  console.log(`[server] listening on http://${HOST}:${PORT}`)
})

// 优雅退出
process.on('SIGTERM', () => process.exit(0))
process.on('SIGINT', () => process.exit(0))
```

## SSO 接入（Hard Rule #4 强制）

详见 `../sso.md`。Koa 推荐 middleware：

```javascript
// backend/src/sso.js
function parseSsoUser(headerValue, fallbackEmail) {
  if (headerValue) {
    try {
      const raw = Buffer.from(headerValue, 'latin1').toString('utf8')
      const data = JSON.parse(Buffer.from(raw, 'base64').toString('utf8'))
      return {
        email: data.email || data.workEmail,
        name: data.name || data.displayName,
        userId: data.userId || data.id,
      }
    } catch (e) {
      // fall through
    }
  }
  if (fallbackEmail && process.env.APP_ENV === 'sit') {
    return { email: fallbackEmail, name: fallbackEmail.split('@')[0], userId: 'sit-dev' }
  }
  return null
}

// Koa middleware
function requireSso() {
  return async (ctx, next) => {
    const user = parseSsoUser(
      ctx.headers['decrypted-userinfo'],
      ctx.headers['sso-email'],
    )
    if (!user) {
      ctx.status = 401
      ctx.body = { error: 'not authenticated' }
      return
    }
    ctx.state.user = user
    await next()
  }
}

module.exports = { parseSsoUser, requireSso }
```

业务路由用法：

```javascript
const { requireSso } = require('./sso')
const { query } = require('./db')

router.get('/api/items', requireSso(), async (ctx) => {
  const rows = await query(
    'SELECT id, name FROM items WHERE created_by = $1',
    [ctx.state.user.email],
  )
  ctx.body = { items: rows }
})
```

## DB 接入

详见 `../db.md`。Node 用 `pg` 包：

```javascript
// backend/src/db.js
const { Pool } = require('pg')
const fs = require('fs')
const path = require('path')

function loadDbProperties() {
  const p = path.resolve(__dirname, '..', 'db.properties')
  if (!fs.existsSync(p)) return {}
  const out = {}
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const s = line.trim()
    if (!s || s.startsWith('#') || !s.includes('=')) continue
    const i = s.indexOf('=')
    out[s.slice(0, i).trim()] = s.slice(i + 1).trim()
  }
  return out
}

const props = loadDbProperties()

// ⚠️ 用对象参数，不字符串拼 URL（password 含 @ : / 会崩）
const pool = new Pool({
  host: props['db.host'],
  port: parseInt(props['db.port'] || '5432', 10),
  database: props['db.database'],
  user: props['db.username'],
  password: props['db.password'],
  max: 5,
})

async function query(sql, params = []) {
  const r = await pool.query(sql, params)
  return r.rows
}

module.exports = { pool, query }
```

DDL 初始化：`backend/src/init-db.js` 在 server.js 启动时调一次：

```javascript
// backend/src/init-db.js
const { query } = require('./db')

let initialized = false
let initPromise = null

async function ensureDbInit() {
  if (initialized) return
  if (!initPromise) {
    initPromise = (async () => {
      await query(`
        CREATE TABLE IF NOT EXISTS items (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
      `)
      initialized = true
    })()
  }
  return initPromise
}

module.exports = { ensureDbInit }
```

server.js 启动时：

```javascript
const { ensureDbInit } = require('./init-db')
ensureDbInit().catch((e) => {
  console.error('[init-db] failed:', e)
  process.exit(1)
})
```

## AI 接入（必须走 Runway，详见 `../ai.md`）

```javascript
// backend/src/ai.js
const fs = require('fs')
const path = require('path')

function loadAiProperties() {
  const p = path.resolve(__dirname, '..', 'ai.properties')
  if (!fs.existsSync(p)) return {}
  const out = {}
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const s = line.trim()
    if (!s || s.startsWith('#') || !s.includes('=')) continue
    const i = s.indexOf('=')
    out[s.slice(0, i).trim()] = s.slice(i + 1).trim()
  }
  return out
}

const ai = loadAiProperties()

async function callText(messages, maxTokens = 2000) {
  const r = await fetch(ai['ai.text.endpoint'], {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${ai['ai.text.api_key']}`,
      'Content-Type': 'application/json',
      'anthropic-version': 'bedrock-2023-05-31',
    },
    body: JSON.stringify({
      anthropic_version: 'bedrock-2023-05-31',
      max_tokens: maxTokens,
      messages,
    }),
  })
  if (!r.ok) throw new Error(`Runway ${r.status}: ${await r.text()}`)
  const data = await r.json()
  if (data.error) throw new Error(`Runway: ${JSON.stringify(data.error)}`)
  return data.content[0].text
}

module.exports = { callText }
```

## 该模板特有的 7 个坑

1. **profile 名字误导**：叫 "koa-fastapi" 但**没有 fastapi**，纯 Node。这是历史命名，别真去装 fastapi。
2. **/health 顶层**：不能放 `/api/health`。health.sh 探的是 `/health`。
3. **API 路由前缀 `/api`**：否则跟 SPA fallback 冲突。
4. **静态托管 + SPA fallback 顺序**：先 router → 再 koa-static → 最后 SPA fallback 中间件。顺序错了 dist 文件返不出来或者所有路径都返 index.html。
5. **`backend/.npmrc` 必须**：内网 + npmmirror 双路。否则 `npm ci` 在 install.sh 里跑会拉公网失败。
6. **没有 dev hot reload**：本地 dev 用 `npm run dev`（scaffold 已配 nodemon），生产用 `node src/server.js`。两边一致。
7. **prepack.sh 必须 build frontend**：否则 Pod 里 `frontend/dist` 不存在，访问 `/` 返 503。

## 切换到 Express / Fastify

scaffold 默认用 Koa。想换 Express：

1. `backend/package.json` 把 `koa` `@koa/router` `koa-static` 换成 `express`
2. `backend/src/server.js` 把 Koa API 改成 Express（中间件链类似）
3. 不动 install.sh / start.sh / health.sh

Fastify 类似。

## 完整参考实现

后端业务路由组织 / SSO 中间件 / DB 单例 模式参考 `fastapi-only.md`（结构通用，只是语言不同）。

Cross-cutting:

- `../db.md` — DB 完整规范（Node 例在 §6.2 末尾）
- `../sso.md` — SSO 完整规范
- `../ai.md` — AI 完整规范
- `../urls.md` — URL / 静态 / SPA fallback
- `../deps-node.md` — Node 依赖 + .npmrc
- `../checklist.md` — 写完自检
