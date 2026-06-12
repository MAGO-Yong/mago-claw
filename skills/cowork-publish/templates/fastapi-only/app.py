"""Cowork fastapi-only scaffold — minimal hello + /health.

按 Cowork Guard 子应用规范开发：
  - 用 Decrypted-Userinfo header 拿用户身份（_parse_sso_user）
  - 持久化用 db.properties + psycopg[binary] (PostgreSQL)
  - /health 返 JSON 给 health.sh 探测
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse


def _load_db_properties(path: str = "db.properties") -> dict[str, str]:
    p = Path(__file__).resolve().parent / path
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _parse_sso_user(decrypted_userinfo: Optional[str]) -> Optional[dict]:
    """从 Decrypted-Userinfo header 解 SSO 用户（latin-1 → JSON 两步）。

    生产环境上 Cowork Guard 网关会注入 header；header 值是被 HTTP 层用 latin-1
    解码过的 UTF-8 字节，必须重编码后才能 json.loads。

    本地 dev 调试时 header 缺失，不走任何环境变量 bypass，请用浏览器插件
    （ModHeader / Header Editor）手动注入一段 mock JSON。安全规范不允许
    “生产跳 SSO”类后门（precheck 会拦）。
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
        "raw": data,
    }


def _require_user(decrypted_userinfo: Optional[str]) -> dict:
    """拿不到用户 → 401，Cowork Guard 会自动跳 SSO 登录页。所有业务路由 MUST 调。"""
    user = _parse_sso_user(decrypted_userinfo)
    if not user:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return user


app = FastAPI(title="Cowork fastapi-only scaffold")


@app.get("/")
def index() -> dict:
    return {
        "service": "fastapi-only-scaffold",
        "msg": "Cowork sub-app skeleton is live. Edit app.py to add business logic.",
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/whoami")
def whoami(
    decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"),
) -> JSONResponse:
    user = _require_user(decrypted_userinfo)
    return JSONResponse({"email": user["email"], "name": user["name"], "userId": user["userId"]})
