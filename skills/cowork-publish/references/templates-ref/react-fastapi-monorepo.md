# react-fastapi-monorepo 模板参考

> **何时读**：选用 `react-fastapi-monorepo` 模板后写业务代码时读。
>
> 适用场景：**最常见的中型项目布局**——前端 React + 后端 FastAPI 分仓。前端跑 SPA，后端提供 API 同时静态托管前端 build 产物。

## scaffold 已给好

调 `cowork.scaffold_app({ template: 'react-fastapi-monorepo' })` 后：

```
<srcDir>/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # FastAPI app + 路由 + 静态 SPA fallback
│   │   ├── db.py            # PostgreSQL 连接 / 关键字参数 / asyncpg
│   │   ├── init_db.py       # DDL 幂等
│   │   ├── sso.py           # Decrypted-Userinfo 解析
│   │   └── ai.py            # Runway 调用
│   ├── requirements.txt
│   └── .venv/               # install.sh 创建
├── frontend/                # React + Vite SPA
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   └── api.ts           # 调 /api/* 的 fetch 包装
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts       # 不要配 base / publicPath
│   ├── tsconfig.json
│   └── .npmrc
├── install.sh               # Linux: venv 隔离 + cd backend && pip install
├── start.sh                 # cd backend; exec $PYTHON -m uvicorn app.main:app ...
├── health.sh                # curl /health
├── prepack.sh               # 先 build 前端 dist，让 backend 能静态托管
└── README.md
```

**install.sh / start.sh / health.sh / prepack.sh 都不要手改**——是官方 guard-transform 渲染产物。

## 关键：backend 静态托管 frontend/dist

`backend/app/main.py` 里：

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent.parent  # 到 monorepo 根
FRONTEND_DIST = ROOT / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"

app = FastAPI()

# ⚠️ 必须把 /api/* 路由先注册，否则被 SPA fallback 吞掉
@app.get("/api/health")
def api_health():
    return {"ok": True, "service": "react-fastapi-monorepo"}

# ... 其他 /api/* 路由 ...

# ✅ /health 必须挂主 app 顶层（不能挂 prefix router 下，否则路径不对）
@app.get("/health")
def health():
    return {"ok": True}

# 静态资源（CSS/JS）— FastAPI StaticFiles
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

# SPA history fallback：所有其他路径 → index.html
@app.get("/")
def index():
    if not INDEX_HTML.exists():
        return JSONResponse({"error": "frontend/dist 未 build"}, status_code=503)
    return FileResponse(INDEX_HTML)

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "API not found"}, status_code=404)
    real = FRONTEND_DIST / full_path
    if real.is_file():
        return FileResponse(real)
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return JSONResponse({"error": "frontend/dist 未 build"}, status_code=503)
```

## prepack.sh：必须先 build 前端

cowork.publish 自动跑 prepack.sh：

```bash
# prepack.sh
set -e
cd frontend
npm ci
npm run build
test -f dist/index.html || exit 1
# 回到根目录，cowork pack 会把 frontend/dist 收进 zip
```

否则 zip 进 Pod 后 `frontend/dist` 不存在，访问 `/` 返 503。

## SSO 接入（Hard Rule #4 强制）

详见 `../sso.md`。FastAPI 推荐用 Depends：

```python
# backend/app/sso.py
import base64, json, os
from typing import Optional
from fastapi import Header, HTTPException

def parse_sso_user(
    decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"),
    sso_email: Optional[str] = Header(None, alias="sso-email"),
):
    if decrypted_userinfo:
        try:
            raw = decrypted_userinfo.encode("latin-1").decode("utf-8")
            data = json.loads(base64.b64decode(raw).decode("utf-8"))
            return {
                "email": data.get("email") or data.get("workEmail"),
                "name": data.get("name") or data.get("displayName"),
                "userId": data.get("userId") or data.get("id"),
            }
        except Exception:
            pass
    if sso_email and os.environ.get("APP_ENV") == "sit":
        return {"email": sso_email, "name": sso_email.split("@")[0], "userId": "sit-dev"}
    raise HTTPException(status_code=401, detail="not authenticated")
```

业务 route：

```python
from fastapi import Depends
from app.sso import parse_sso_user
from app.db import get_conn

@app.get("/api/items")
def list_items(user: dict = Depends(parse_sso_user)):
    with get_conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, name FROM items WHERE created_by = %s", (user["email"],))
        rows = cur.fetchall()
    return {"items": [{"id": r[0], "name": r[1]} for r in rows]}
```

前端 `src/api.ts` 调 API：

```typescript
// frontend/src/api.ts
// ⚠️ 不要配 baseUrl 加 /s/<appId>，router 自动加，cookie 自动带
const apiFetch = async (path: string, init?: RequestInit) => {
  const r = await fetch(`/api${path}`, {
    credentials: 'include',  // 必须，带 Decrypted-Userinfo cookie
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (r.status === 401) {
    window.location.reload()  // SSO 失效让用户重新登录
    return null
  }
  return r.json()
}

export const api = {
  whoami: () => apiFetch('/whoami'),
  listItems: () => apiFetch('/items'),
  createItem: (name: string) =>
    apiFetch('/items', { method: 'POST', body: JSON.stringify({ name }) }),
}
```

## DB / AI

跟 `fastapi-only.md` 完全一样——只是路径前缀变 `backend/app/db.py` / `backend/app/ai.py`。详见：

- `../db.md` — DB 完整规范
- `../ai.md` — AI 完整规范

## frontend Vite 配置注意

`frontend/vite.config.ts`：

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ⚠️ 不要配 base / publicPath！router 自动加 /s/<appId>/，
// 配了会变成 /s/<appId>//s/<appId>/assets/foo.js → 404
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // assets 输出在 dist/assets/ 下，跟 backend StaticFiles 挂载匹配
  },
})
```

## 该模板特有的 7 个坑

1. **API 路由前缀必须 `/api`**：否则跟 SPA fallback 冲突。`@app.get("/items")` 会被 `@app.get("/{full_path:path}")` 吃掉。
2. **/health 不要放 `/api/health`**：health.sh 默认探 `/health`（顶层），不是 `/api/health`。
3. **前端 SPA history 模式**：用 `react-router-dom`'s `BrowserRouter`（不是 HashRouter）。fallback 已经在 backend 处理。
4. **CORS 不需要**：前后端同源（都从 cowork.xiaohongshu.com 出），fetch 自动带 cookie。
5. **prepack.sh 必须成功**：build 失败 → zip 里没 `frontend/dist` → 访问 `/` 503。本地 `cd frontend && npm run build` 验证一遍再 publish。
6. **frontend/.npmrc 是双路 registry**：`@xhs:registry=` 走内网 + `registry=` 走 npmmirror。不要手改。
7. **backend cwd**：start.sh 已 `cd backend`，所以 `db.properties` 应该放在 `backend/` 下（不是项目根）。

## 完整参考实现

backend 业务代码风格参考 `fastapi-only.md`（只是文件路径前缀加 `backend/app/`）。frontend 是 React + Vite，没有 cowork 特殊性，按 React 通用最佳实践写。

Cross-cutting:

- `../db.md` — DB 完整规范（backend 用）
- `../sso.md` — SSO 完整规范
- `../ai.md` — AI 完整规范
- `../urls.md` — URL 路由（**这里特别重要**：monorepo 路由优先级 / vite base 配置）
- `../deps-python.md` + `../deps-node.md`
- `../checklist.md` — 写完自检
