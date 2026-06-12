# nextjs-fullstack 模板导读

> **何时读**：选用 `nextjs-fullstack` 模板（`cowork.py scaffold <name> --template nextjs-fullstack`）后、写业务代码前读。
>
> **本文只讲该模板特有的结构与坑**。SSO / AI / DB / 路径等横切规范统一看 `../sso.md` / `../ai.md` / `../db.md` / `../urls.md`。
> **真实可运行的骨架代码以 `templates/nextjs-fullstack/` 下的实际文件为准**（scaffold 会原样 cp），本文不贴代码副本。

适用场景：Next.js 14 App Router 全栈 / SSR / SEO 重要的页面 / 后台管理页 / 需要 React 生态丰富组件库。

## scaffold 生成的真实结构

```
<srcDir>/
├── app/                        # Next.js App Router
│   ├── layout.tsx              # 根布局
│   ├── page.tsx                # / 首页
│   ├── health/route.ts         # /health 顶层（给 health.sh 探活）
│   └── api/
│       ├── health/route.ts     # /api/health
│       └── whoami/route.ts     # /api/whoami（内置 parseSsoUser / requireUser，可 import 复用）
├── next.config.js              # output: 'standalone'（必须）
├── package.json                # next 14 / react 18
├── tsconfig.json
├── .npmrc                      # 双路内网 registry
├── install.sh                  # standalone build 自带 node_modules，install 基本 no-op
├── start.sh                    # exec node .next/standalone/server.js（读 APP_PORT）
├── health.sh                   # curl /health
├── prepack.sh                  # build + patch standalone server.js（读 APP_HOSTNAME/APP_PORT）+ link static/public
└── README.md
```

> ⚠️ `install.sh` / `start.sh` / `health.sh` / `prepack.sh` / `next.config.js` 是规范产物，**不要手改**。

## 骨架已内置（直接用，别重写）

`app/api/whoami/route.ts` 里已写好且**符合最新规范**，并 `export` 出来供业务路由 import：

- `parseSsoUser(headerValue)`：**latin-1 → JSON 两步**（`Buffer.from(h,'latin1').toString('utf8')` 后 `JSON.parse`，**没有 base64**），拿不到返 null
- `requireUser(req)`：拿不到 → **401**，**无 `APP_ENV==='sit'` 后门 / 无 `sso-email` 自造 header**（precheck 会拦）
- `app/health/route.ts`（顶层 `/health`）+ `app/api/health/route.ts`

业务 route 直接 `import { requireUser } from '@/app/api/whoami/route'` 复用，不要另写一套 SSO 解析。

加 DB / AI 时**按 `../db.md` / `../ai.md` 的标准实现自己建** `app/lib/db.ts` / `ai.ts`（骨架默认不带）。

> ⚠️ **AI 调用别想当然**：Runway 文本网关用 `header: token:`（不是 `Authorization: Bearer`），读 `ai.base_url` / `ai.api_key`（不是 `ai.text.endpoint`），检查 `data.Code || data.Error`（不是 `data.error`）。务必照抄 `../ai.md`。

## 该模板特有的坑

1. **`output: 'standalone'` 必须**：少了 `prepack.sh` 找不到 `.next/standalone/server.js`，部署直接 fail。
2. **不配 basePath / assetPrefix / publicPath**：平台 router 自动加 `/s/<appId>/`，配了双前缀 404（详见 `../urls.md`）。
3. **HOSTNAME / PORT 必须 patch**：Next standalone 默认读 `HOSTNAME`/`PORT`；prepack.sh 已 sed 替换成读 `APP_HOSTNAME`/`APP_PORT`，否则蓝绿期注入的 `APP_PORT` 不生效。
4. **`/health` 必须在 `app/health/route.ts`**（顶层），不要放 `app/(group)/health/` 之类 group 下。
5. **DB 懒初始化**：Next 没传统 install.sh DDL 时机，DDL 放业务首次调用时 `ensureDbInit()`（幂等 `CREATE TABLE IF NOT EXISTS`）；不要用 migrations 工具（详见 `../db.md`）。
6. **App Router 不混 Pages Router**：scaffold 用 `app/`，别加 `pages/`。
7. **`'use client'` 边界**：SSO / DB / AI 等 server 操作只能在 route handler（server）里，client 组件走 `/api/*` 调。

## 横切规范（必读）

- `../db.md` / `../sso.md` / `../ai.md` — DB / SSO / AI 标准实现
- `../urls.md` — URL / 静态资源 / Next standalone 注意事项
- `../deps-node.md` — Node 依赖 + .npmrc
- `../checklist.md` — 写完自检
