# pure-spa-vite 模板参考

> **何时读**：选用 `pure-spa-vite` 模板后写业务代码时读。
>
> 适用场景：**纯前端 SPA**（不需要 Node 后端）。Vue / React / Svelte 任选。生产用 `server.cjs + serve-handler` 托管 dist，**自带 /health endpoint**。

## scaffold 已给好

调 `cowork.scaffold_app({ template: 'pure-spa-vite' })` 后：

```
<srcDir>/
├── src/                    # Vue 3 + vue-router（也可改 React/Svelte）
│   ├── main.ts
│   ├── App.vue
│   └── pages/
│       ├── Home.vue
│       └── About.vue
├── index.html
├── package.json            # vite + vue + vue-router
├── vite.config.ts          # 不配 base / publicPath
├── tsconfig.json
├── .npmrc                  # @xhs 内网 + npmmirror 双路
├── server.cjs              # 生产托管入口（serve-handler + /health）
├── install.sh              # 装 .guard-runtime/serve-handler
├── start.sh                # exec node server.cjs
├── health.sh               # curl /health
├── prepack.sh              # npm ci + npm run build → dist/
└── README.md
```

## 关键：生产用 server.cjs 托管，不是 vite preview

`server.cjs`（scaffold 已写好，**不要手改**）：

```javascript
// server.cjs - 纯前端 SPA 托管入口
'use strict';
const fs = require('fs')
const http = require('http')
const path = require('path')

const RUNTIME_DIR = path.resolve(__dirname, '.guard-runtime')
module.paths.unshift(path.join(RUNTIME_DIR, 'node_modules'))
const handler = require('serve-handler')

const STATIC_DIR = path.resolve(__dirname, 'dist')
const INDEX_HTML = path.join(STATIC_DIR, 'index.html')
const PORT = parseInt(process.env.APP_PORT || process.env.PORT || '3000', 10)

const server = http.createServer(async (req, res) => {
  const pathname = (req.url || '/').split('?')[0]

  // /health endpoint
  if (pathname === '/health') {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ ok: true, ts: Date.now() }))
    return
  }

  // SPA history fallback：无扩展名 → index.html
  const baseName = pathname.split('/').pop() || ''
  if (!baseName.includes('.') && fs.existsSync(INDEX_HTML)) {
    req.url = '/index.html' + (req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '')
  }

  await handler(req, res, { public: STATIC_DIR, cleanUrls: false })
})

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[server] listening on http://0.0.0.0:${PORT}`)
})

process.on('SIGTERM', () => server.close(() => process.exit(0)))
process.on('SIGINT', () => server.close(() => process.exit(0)))
```

## install.sh：装 .guard-runtime/serve-handler

scaffold 已给好。关键设计：**不污染业务 package.json**。

```bash
# install.sh
mkdir -p .guard-runtime
cat > .guard-runtime/package.json <<'JSON'
{
  "name": "guard-static-runtime",
  "dependencies": { "serve-handler": "^6.1.5" }
}
JSON
cd .guard-runtime
npm install --no-audit --omit=dev  # 走根 .npmrc 内网镜像
```

## vite.config.ts 配置（不要手改）

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  // ❌ 不要配 base / publicPath！router 自动加 /s/<appId>/ 前缀，
  //    自己再配会变成 /s/<appId>//s/<appId>/assets/foo.js → 404
})
```

## vue-router 配置：history 模式

```typescript
// src/main.ts
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),   // ← 必须 history 模式
  routes: [
    { path: '/', component: () => import('./pages/Home.vue') },
    { path: '/about', component: () => import('./pages/About.vue') },
  ],
})
```

**不要用 `createWebHashHistory`** —— Hash 模式 URL 带 `#`，分享不友好，且 cowork router `/s/<appId>/#/about` 解析混乱。

server.cjs 已经处理 SPA fallback（无扩展名路径 → index.html），所以 history 模式刷新不 404。

## 业务代码：纯前端，不调后端

pure-spa-vite **没有后端**。如果你需要 API，选错模板了——应该用 `react-fastapi-monorepo` 或 `koa-fastapi-monorepo`。

但如果只是**调外部 API**（比如某个内网 API 服务），可以前端直调：

```typescript
// src/api.ts
const apiBase = '/api'  // 假设有人挂了 backend 在 /api 路径

export async function fetchSomething() {
  // 注意：纯前端无法解 Decrypted-Userinfo（那是 server header）。
  // 如果需要拿用户身份，必须有后端。
  const r = await fetch(`${apiBase}/something`)
  return r.json()
}
```

## SSO 怎么办？

⚠️ Hard Rule #4 要求所有项目接入 SSO。但 **pure-spa-vite 没后端**，无法解析 `Decrypted-Userinfo` header（那是 server-side header，前端 JS 拿不到）。

**两种合规方案**：

**方案 A**：仅展示型 demo（不需要用户身份）—— 不接入 SSO 的具体业务逻辑，但**必须**让 cowork 平台 SSO 流转能跑（默认就跑，前端啥都不做就行，因为认证发生在 nginx 层）。访问者必须登录公司账号才能打开页面，但前端代码看不到他是谁。

**方案 B**：需要识别用户身份 → **换模板**。pure-spa-vite 不适合你的需求，换 `react-fastapi-monorepo` 用 backend 解 SSO。

## prepack.sh：必须 build 出 dist

```bash
# prepack.sh
set -e
test -d node_modules || npm ci
npm run build
test -f dist/index.html || { echo "build failed"; exit 1; }
```

cowork.publish 会自动跑。

> ⚠️ **agent 不要本地起服务 verify**（会污染 pod / 撑爆内存 / 可能干 crash gateway）。直接调 `cowork.publish` 让 Cowork Guard 平台验即可。
>
> 仅下面 power-user / 用户手动调试时参考：
>
> ```bash
> # 用户手动跑，不是 agent
> npm ci && npm run build
> ls dist/index.html
> node server.cjs &
> curl http://localhost:3000/health
> ```

## 该模板特有的 6 个坑

1. **没有后端**：所有业务逻辑必须前端搞定（或调外部 API）。需要 DB / SSO 业务逻辑 → 选错模板了。
2. **vite.config.ts 不要配 base**：会双前缀 404。
3. **vue-router 用 history 模式**：不要 hash 模式。
4. **server.cjs / install.sh 不要手改**：是 guard-transform 渲染产物。
5. **CSS 不能 `url(/...)`**：详见 `../urls.md` §9.3。assets 走相对路径或 Vite import。
6. **prepack 必须本地 build 验证**：dist 缺了 / build 错了 → Pod 起来后 / 路径 503。

## Express + Vite 变体（可选）

如果非要在单服务里给 SPA 加一点 API（不想拆 monorepo），可以把 pure-spa-vite 改造成 Express + Vite 单仓：

```javascript
// server/app.js（替换 server.cjs）
const express = require('express')
const path = require('path')

const app = express()

// /health 顶层
app.get('/health', (req, res) => res.json({ ok: true }))

// SSO middleware
app.use((req, res, next) => {
  const raw = req.headers['decrypted-userinfo']
  if (raw) {
    try {
      const fixed = Buffer.from(raw, 'latin1').toString('utf-8')
      req.sso = JSON.parse(Buffer.from(fixed, 'base64').toString('utf-8'))
    } catch {}
  }
  next()
})

// API 路由
app.get('/api/whoami', (req, res) => {
  if (!req.sso) return res.status(401).json({ error: 'not authenticated' })
  res.json(req.sso)
})

// 静态前端
app.use(express.static(path.join(__dirname, '..', 'dist')))

// SPA history fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'dist', 'index.html'))
})

const PORT = parseInt(process.env.APP_PORT || '3000', 10)
app.listen(PORT, '0.0.0.0', () => console.log(`listening on :${PORT}`))
```

但**更推荐**直接用 `react-fastapi-monorepo` 或 `koa-fastapi-monorepo`——结构更清晰。

## 完整参考实现

Cross-cutting:

- `../urls.md` — URL 路由 / SPA fallback / vite base 配置（**最重要**）
- `../deps-node.md` — Node 依赖 + .npmrc
- `../checklist.md` — 写完自检（特别注意"frontend 必须 prebuilt"那一条）
- `../blacklist.md` — 禁项
