# Cowork koa-monorepo scaffold

按 ai-demo-platform-guard-transform-skill / koa-monorepo profile 规范产物。

注意 profile 名字虽叫 "koa-fastapi"，实际是 **Node 前端 + Node 后端（Koa/Express）monorepo**。
backend 用 Koa 跑，frontend 用 React + Vite。

```
backend/     # Koa 后端（API + 静态托管 frontend/dist）
frontend/    # Vite + React SPA
prepack.sh   # cowork pack 自动跑：build 前端
```
