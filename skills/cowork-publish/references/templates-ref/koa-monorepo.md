# koa-monorepo 模板导读

> **何时读**：选用 `koa-monorepo` 模板（`cowork.py scaffold <name> --template koa-monorepo`）后、写业务代码前读。
>
> **本文只讲该模板特有的结构与坑**。SSO / AI / DB / 路径等横切规范统一看 `../sso.md` / `../ai.md` / `../db.md` / `../urls.md`。
> **真实可运行的骨架代码以 `templates/koa-monorepo/` 下的实际文件为准**（scaffold 会原样 cp），本文不贴代码副本。

适用场景：**前端 Node + 后端 Node 分仓**。前端 React + Vite，后端 Koa（可换 Express / Fastify）。整个项目纯 Node 技术栈，无 Python。

## scaffold 生成的真实结构

```
<srcDir>/
├── backend/
│   ├── src/server.js       # Koa：/health + /api/health + /api/whoami + 静态托管 + SPA fallback
│   │                       #   已内置 parseSsoUser / requireUser（latin-1→JSON 两步，401，无后门）
│   ├── package.json
│   └── .npmrc              # 双路内网 registry
├── frontend/               # React + Vite SPA
│   ├── src/{App.tsx,main.tsx}
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts      # 不配 base / publicPath
│   ├── tsconfig.json
│   └── .npmrc
├── install.sh              # cd backend && npm ci --omit=dev
├── start.sh                # cd backend && exec node src/server.js（监听 ${APP_PORT:-3000}）
├── health.sh               # curl /health
├── prepack.sh              # cowork pack 自动跑：build frontend/dist（含 fast-path 复用）
└── README.md
```

> ⚠️ `install.sh` / `start.sh` / `health.sh` / `prepack.sh` 是规范产物，**不要手改**。

## 骨架已内置（直接用，别重写）

`backend/src/server.js` 里已写好且**符合最新规范**：

- `parseSsoUser(headerValue)`：**latin-1 → JSON 两步**（`Buffer.from(h,'latin1').toString('utf8')` 后 `JSON.parse`，**没有 base64**），拿不到返 null
- `requireUser(ctx)`：拿不到 → **401**，**无 `APP_ENV==='sit'` 后门 / 无 `sso-email` 自造 header**（precheck 会拦）
- `/health` 顶层 + `/api/health` + `/api/whoami`
- koa-static 静态托管 + SPA fallback（404 且非 `/api/` → index.html）

加 DB / AI 时**按 `../db.md` / `../ai.md` 的标准实现自己建** `backend/src/db.js` / `ai.js`（骨架默认不带），不要凭印象写。

> ⚠️ **AI 调用别想当然**：Runway 文本网关用 `header: token:`（不是 `Authorization: Bearer`），读 `ai.base_url` / `ai.api_key`（不是 `ai.text.endpoint`），检查 `data.Code || data.Error`（不是 `data.error`）。务必照抄 `../ai.md`，不要凭 OpenAI 习惯写。

## 该模板特有的坑

1. **profile 名无 fastapi**：纯 Node 技术栈（历史命名遗留），别真去装 fastapi/Python。
2. **`/health` 顶层**：health.sh 探的是 `/health`，不是 `/api/health`。
3. **API 路由 `/api` 前缀**：否则跟 SPA fallback 冲突。
4. **中间件顺序**：先 `router.routes()` → 再 `koa-static` → 最后 SPA fallback。顺序错了 dist 返不出或全部返 index.html。
5. **`backend/.npmrc` 必须在**：双路 registry，否则 install.sh 里 `npm ci` 拉公网失败。
6. **prepack 必须 build frontend**：否则 Pod 里 `frontend/dist` 不存在，访问 `/` 返 503。
7. **换 Express / Fastify**：改 `backend/package.json` + `server.js`，**不动** install.sh / start.sh / health.sh。

## 横切规范（必读）

- `../db.md` / `../sso.md` / `../ai.md` — DB / SSO / AI 标准实现（Node 写法）
- `../urls.md` — URL / 静态 / SPA fallback
- `../deps-node.md` — Node 依赖 + .npmrc
- `../checklist.md` — 写完自检
