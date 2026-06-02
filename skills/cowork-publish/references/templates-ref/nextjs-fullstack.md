# nextjs-fullstack 模板参考

> **何时读**：选用 `nextjs-fullstack` 模板后写业务代码时读。
>
> 适用场景：Next.js 全栈 / SSR / SEO 重要的页面 / 后台管理页 / 需要 React 生态丰富组件库。

## scaffold 已给好

调 `cowork.scaffold_app({ template: 'nextjs-fullstack' })` 后，目录下含：

```
<srcDir>/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # 根布局
│   ├── page.tsx            # / 首页
│   ├── health/route.ts     # /health 顶层路由（给 health.sh 探活）
│   └── api/
│       ├── health/route.ts # /api/health
│       └── whoami/route.ts # /api/whoami（SSO 解析）
├── next.config.js          # 必须 output: 'standalone'
├── package.json            # next 14 / react 18
├── tsconfig.json
├── .npmrc                  # @xhs 内网 + npmmirror 双路
├── install.sh              # standalone build 已自带 node_modules，install.sh 为 no-op
├── start.sh                # exec node .next/standalone/server.js
├── health.sh               # curl /health
├── prepack.sh              # build + patch standalone server.js（让它读 APP_HOSTNAME/APP_PORT）
└── README.md
```

## 关键：`next.config.js` 必须 `output: 'standalone'`

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // ⚠️ 必须，否则 Pod 起不来
  experimental: {},
}
module.exports = nextConfig
```

**不要配 basePath / assetPrefix**（router 自动加 `/s/<appId>/` 前缀，配了会双前缀 404）。

## 关键：prepack.sh 自动跑 build + patch server.js

cowork.publish 会自动 spawn prepack.sh，它做：

```bash
# prepack.sh 简化版（实际看 templates/nextjs-fullstack/prepack.sh）
npm ci
npm run build  # 出 .next/standalone/server.js

# patch standalone server.js：让它读 APP_HOSTNAME / APP_PORT
# 否则 Pod 注入的 APP_PORT=3001（蓝绿期）会被 server.js 内的 PORT=3000 覆盖
perl -i -pe 's/process\.env\.HOSTNAME\b/(process.env.APP_HOSTNAME || process.env.HOSTNAME)/g' .next/standalone/server.js
perl -i -pe 's/process\.env\.PORT\b/(process.env.APP_PORT || process.env.PORT)/g' .next/standalone/server.js

# link static/public 进 standalone
mkdir -p .next/standalone/.next
cp -r .next/static .next/standalone/.next/static
[ -d public ] && cp -r public .next/standalone/public
```

## /health endpoint

`app/health/route.ts`：

```typescript
import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({ ok: true })
}
```

⚠️ **必须在 app/ 顶层**（路径 `/health`），不能在 `app/(auth)/health/route.ts` 这种 group 下。health.sh 探的就是 `http://127.0.0.1:${APP_PORT}/health`。

## SSO 接入（Hard Rule #4 强制）

详见 `../sso.md`。Next.js 推荐 helper：

```typescript
// app/lib/sso.ts
import type { NextRequest } from 'next/server'

export interface SsoUser {
  email: string
  name: string
  userId: string
}

export function parseSsoUser(req: NextRequest): SsoUser | null {
  const header = req.headers.get('decrypted-userinfo')
  if (header) {
    try {
      const raw = Buffer.from(header, 'latin1').toString('utf8')
      const data = JSON.parse(Buffer.from(raw, 'base64').toString('utf8'))
      return {
        email: data.email ?? data.workEmail,
        name: data.name ?? data.displayName,
        userId: data.userId ?? data.id,
      }
    } catch {
      // fall through
    }
  }
  if (process.env.APP_ENV === 'sit') {
    const fallback = req.headers.get('sso-email')
    if (fallback) {
      return { email: fallback, name: fallback.split('@')[0], userId: 'sit-dev' }
    }
  }
  return null
}
```

业务 route 用法：

```typescript
// app/api/items/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { parseSsoUser } from '@/app/lib/sso'
import { query } from '@/app/lib/db'

export async function GET(req: NextRequest) {
  const user = parseSsoUser(req)
  if (!user) {
    return NextResponse.json({ error: 'not authenticated' }, { status: 401 })
  }
  const rows = await query(
    'SELECT id, name FROM items WHERE created_by = $1',
    [user.email],
  )
  return NextResponse.json({ items: rows })
}
```

## DB 接入（PostgreSQL via db.properties）

详见 `../db.md`。Node 推荐 `pg` 包（不要 sequelize / typeorm）：

```typescript
// app/lib/db.ts
import { Pool } from 'pg'
import fs from 'node:fs'
import path from 'node:path'

function loadDbProperties(): Record<string, string> {
  const p = path.resolve(process.cwd(), 'db.properties')
  if (!fs.existsSync(p)) return {}
  const out: Record<string, string> = {}
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const s = line.trim()
    if (!s || s.startsWith('#') || !s.includes('=')) continue
    const idx = s.indexOf('=')
    out[s.slice(0, idx).trim()] = s.slice(idx + 1).trim()
  }
  return out
}

const props = loadDbProperties()

// ⚠️ 用对象参数，不字符串拼 URL
export const pool = new Pool({
  host: props['db.host'],
  port: parseInt(props['db.port'] || '5432', 10),
  database: props['db.database'],
  user: props['db.username'],
  password: props['db.password'],
  max: 5,  // standalone Pod 内存有限，连接池别太大
})

export async function query<T = any>(sql: string, params: any[] = []): Promise<T[]> {
  const r = await pool.query(sql, params)
  return r.rows as T[]
}
```

**DB 初始化**：Next.js 没有传统 `install.sh`（standalone build 自带依赖），DDL 在**第一次 API 调用时懒初始化**或者**写到 `prepack.sh` 里**（不推荐，因为 prepack 在转写者机器跑，没生产 DB）。最稳的是单独写一个 `scripts/init-db.ts` 在 Pod 第一次健康检查通过后由业务代码自调（idempotent CREATE TABLE IF NOT EXISTS）。

```typescript
// app/lib/init-db.ts
import { query } from './db'

let initialized = false
const initPromise = (async () => {
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

export async function ensureDbInit() {
  if (!initialized) await initPromise
}
```

每个业务 route 开头调一下：

```typescript
export async function GET(req: NextRequest) {
  await ensureDbInit()
  // ...
}
```

## AI 接入（必须走 Runway，详见 `../ai.md`）

```typescript
// app/lib/ai.ts
import fs from 'node:fs'
import path from 'node:path'

function loadAiProperties() {
  const p = path.resolve(process.cwd(), 'ai.properties')
  if (!fs.existsSync(p)) return {}
  const out: Record<string, string> = {}
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const s = line.trim()
    if (!s || s.startsWith('#') || !s.includes('=')) continue
    const idx = s.indexOf('=')
    out[s.slice(0, idx).trim()] = s.slice(idx + 1).trim()
  }
  return out
}

const ai = loadAiProperties()

export async function callText(messages: any[], maxTokens = 2000): Promise<string> {
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
  if (data.error) throw new Error(`Runway error: ${JSON.stringify(data.error)}`)
  return data.content[0].text
}
```

## 该模板特有的 6 个坑

1. **`output: 'standalone'` 必须**：少了这条 `prepack.sh` 找不到 `.next/standalone/server.js`，install.sh 直接 fail。
2. **不要配 basePath / assetPrefix / publicPath**：router 自动加 `/s/<appId>/`，配了会双前缀。
3. **HOSTNAME / PORT 必须 patch**：Next standalone 默认读这俩；不 patch 蓝绿期注入的 `APP_PORT=3001` 不生效。prepack.sh 已 sed 替换。
4. **bg task / setInterval 不要**：Next.js Pod 是单实例长进程，但 cowork 平台可能蓝绿切换 → bg task 状态丢。重活走 DB 队列。
5. **App Router vs Pages Router**：scaffold 用 App Router（`app/`），不要混 `pages/`，路由会冲突。
6. **`use client` boundary**：API route 默认 server。组件加交互必须 `'use client'` 顶部。SSO/DB/AI 等 server 操作不能在 client 组件里直接调，要走 `/api/*` route。

## 完整参考实现

业务代码风格参考 `fastapi-only.md` 的结构（路由组织 / SSO middleware / DB 单例 / AI 调用），不同点：

- Python `app/main.py` → Next `app/page.tsx` + `app/api/*/route.ts`
- Python `app/db.py` 同步 → Next `app/lib/db.ts` 用 `pg.Pool` 异步
- Python `app/sso.py` → Next `app/lib/sso.ts`（参数从 `Request` 拿）

Cross-cutting:

- `../db.md` — DB 完整规范
- `../sso.md` — SSO 完整规范
- `../ai.md` — AI 完整规范
- `../urls.md` — URL / 静态资源 / Next router 注意事项
- `../deps-node.md` — Node 依赖 + .npmrc
- `../checklist.md` — 写完自检
