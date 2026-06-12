"""Cowork react-fastapi-monorepo / backend — minimal FastAPI + 静态托管前端 dist."""
from __future__ import annotations

import json, os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent           # backend/
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"


def _parse_sso_user(decrypted_userinfo: Optional[str]):
    """从 Decrypted-Userinfo header 解 SSO 用户（latin-1 → JSON 两步）。

    本地 dev 调试用浏览器插件手动注入 header，不走环境变量 bypass。
    安全规范禁“生产跳 SSO”后门（precheck 会拦）。
    """
    if not decrypted_userinfo:
        return None
    try:
        fixed = decrypted_userinfo.encode("latin-1").decode("utf-8")
        data = json.loads(fixed)
    except Exception:
        return None
    return {
        "email": data.get("email") or data.get("workEmail"),
        "name": data.get("name") or data.get("displayName"),
        "userId": data.get("userId") or data.get("id"),
    }


def _require_user(decrypted_userinfo: Optional[str]) -> dict:
    """拿不到用户 → 401。所有业务路由 MUST 调。"""
    user = _parse_sso_user(decrypted_userinfo)
    if not user:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user


app = FastAPI(title="Cowork react-fastapi-monorepo backend")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "service": "react-fastapi-monorepo"}


@app.get("/api/whoami")
def whoami(
    decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"),
):
    u = _require_user(decrypted_userinfo)
    return JSONResponse(u)


# ---- 静态前端托管 ----
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
def index():
    if not INDEX_HTML.exists():
        return HTMLResponse(
            "<h1>frontend/dist 不存在</h1><p>请在转写者机器先跑 prepack.sh（或 npm run build）</p>",
            status_code=503,
        )
    return FileResponse(INDEX_HTML)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    real = FRONTEND_DIST / full_path
    if real.is_file():
        return FileResponse(real)
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return JSONResponse({"error": "frontend/dist 未 build"}, status_code=503)
