# react-fastapi-monorepo 模板导读

> **何时读**：选用 `react-fastapi-monorepo` 模板（`cowork.py scaffold <name> --template react-fastapi-monorepo`）后、写业务代码前读。
>
> **本文只讲该模板特有的结构与坑**。SSO / AI / DB / 路径等横切规范统一看 `../sso.md` / `../ai.md` / `../db.md` / `../urls.md`。
> **真实可运行的骨架代码以 `templates/react-fastapi-monorepo/` 下的实际文件为准**（scaffold 会原样 cp），本文不贴代码副本。

适用场景：**最常见的中型布局**——前端 React + Vite SPA，后端 FastAPI 提供 API 并静态托管前端 build 产物（单进程同源）。

## scaffold 生成的真实结构

```
<srcDir>/
├── backend/
│   ├── app.py              # FastAPI：/health + /api/health + /api/whoami + 静态托管 + SPA fallback
│   │                       #   已内置 _parse_sso_user / _require_user（latin-1→JSON 两步，401，无后门）
│   └── requirements.txt
├── frontend/               # React + Vite SPA
│   ├── src/{App.tsx,main.tsx}
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts      # 不配 base / publicPath（router 自动加前缀）
│   ├── tsconfig.json
│   └── .npmrc              # 双路内网 registry
├── install.sh              # cd backend && python3 -m pip install -r requirements.txt（禁 venv）
├── start.sh                # cd backend && exec python3 -m uvicorn app:app --host 0.0.0.0 --port ${APP_PORT:-3000}
├── health.sh               # curl /health
├── prepack.sh              # cowork pack 自动跑：先 build frontend/dist（含 fast-path 复用）
└── README.md
```

> ⚠️ `install.sh` / `start.sh` / `health.sh` / `prepack.sh` 是规范产物，**不要手改**。

## 骨架已内置（直接用，别重写）

`backend/app.py` 里已写好且**符合最新规范**：

- `_parse_sso_user` / `_require_user`：**latin-1 → JSON 两步**（没有 base64），拿不到 → **401**，**无 `APP_ENV=="sit"` 后门**（precheck 会拦）
- `/health` 挂主 app 顶层；`/api/health`、`/api/whoami` 走 `/api` 前缀
- 静态托管 `frontend/dist` + SPA history fallback（`/{full_path:path}`，`api/` 开头返 404 不被吞）

加 DB / AI 时**按 `../db.md` / `../ai.md` 的标准实现自己建** `backend/app/db.py` 等（骨架默认不带），不要凭印象写。

## 该模板特有的坑

1. **API 路由必须 `/api` 前缀**：否则被 SPA fallback `@app.get("/{full_path:path}")` 吞掉。
2. **`/health` 不要放 `/api/health`**：health.sh 探的是顶层 `/health`。
3. **`vite.config.ts` 不配 `base` / `publicPath`**：平台 router 自动加 `/s/<appId>/`，配了会双前缀 404（详见 `../urls.md`）。
4. **prepack 必须产出 `frontend/dist`**：否则 zip 里没产物，访问 `/` 返 503。prepack.sh 有 fast-path（dist 不旧于源码就跳过重 build）。
5. **前端路由用 `BrowserRouter`**（不是 HashRouter）；history fallback 已在 backend 处理。
6. **db.properties 位置**：start.sh 已 `cd backend`，所以业务进程 cwd 在 `backend/`，`db.properties` 用相对路径读即可（平台注入在 install.sh 同级 = 项目根；如需 backend 内读，注意路径，详见 `../db.md`）。
7. **前后端同源**：不需要 CORS，fetch 自动同域。

## 横切规范（必读）

- `../db.md` / `../sso.md` / `../ai.md` — DB / SSO / AI 标准实现
- `../urls.md` — **本模板尤其重要**：monorepo 路由优先级 + vite base 禁配
- `../deps-python.md` / `../deps-node.md` — 依赖与镜像
- `../checklist.md` — 写完自检
