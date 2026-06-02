# fastapi-only 完整参考实现

> **何时读**：scaffold 出来的 fastapi-only 项目，**写业务代码时按本文复制粘贴**。含：完整文件树、main.py / db.py / init_db.py / sso.py / ai.py / routes/users.py 全套实现。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

### 13.1 FastAPI 单仓最小骨架

```
my-subapp/
├── install.sh                  # 见 §4.1
├── start.sh                    # 见 §4.2
├── health.sh                   # 见 §4.3
├── db.properties               # 平台注入（与 install.sh 同级，gitignore）
├── ai.properties               # 平台注入（与 install.sh 同级，gitignore，没用 AI 可不注入）
├── .npmrc                      # 仅有前端 SPA 时需要
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py                 # 见下
│   ├── init_db.py              # 见下
│   ├── db.py                   # 见下
│   ├── ai.py                   # 见下
│   ├── sso.py                  # 见下
│   └── routes/
│       └── users.py
└── dist/                       # 前端构建产物（如果有）
```

#### `app/main.py`

```python
from fastapi import FastAPI
from app.routes import users

app = FastAPI()

# ⭐ /health 必须挂主 app 顶层
@app.get("/health")
def health():
    return {"ok": True}

# 业务路由可以挂 prefix router
app.include_router(users.router, prefix="/api")
```

#### `app/db.py`

```python
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine

def _load_props(path):
    props = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, _, v = line.partition("=")
                props[k.strip()] = v.strip()
    return props

_p = _load_props("db.properties")
engine = create_async_engine(URL.create(
    "postgresql+asyncpg",
    username=_p["db.username"], password=_p["db.password"],
    host=_p["db.host"],         port=int(_p["db.port"]),
    database=_p["db.database"],
))
```

#### `app/init_db.py`

```python
"""install.sh 调用：python -m app.init_db。必须幂等。"""
import asyncio
from app.db import engine
from sqlalchemy import text

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_users (
  id SERIAL PRIMARY KEY,
  sso_id TEXT NOT NULL UNIQUE,
  email TEXT,
  username TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email);

CREATE TABLE IF NOT EXISTS files (
  id SERIAL PRIMARY KEY,
  owner_id INTEGER REFERENCES app_users(id),
  filename TEXT NOT NULL,
  content_type TEXT,
  oid OID NOT NULL,
  size BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

SEED = """
INSERT INTO app_users (sso_id, email, username)
VALUES ('admin', 'admin@example.com', 'admin')
ON CONFLICT (sso_id) DO NOTHING;
"""

async def main():
    async with engine.begin() as conn:
        await conn.execute(text(SCHEMA))
        await conn.execute(text(SEED))
    print("[init_db] done")

if __name__ == "__main__":
    asyncio.run(main())
```

#### `app/sso.py`

```python
import json
from fastapi import Request, HTTPException

def get_user(request: Request) -> dict:
    raw = request.headers.get("decrypted-userinfo")
    if not raw:
        raise HTTPException(401, "no sso header")
    # ⚠️ latin-1 → utf-8 重编码（解决中文乱码）
    fixed = raw.encode("latin-1").decode("utf-8")
    return json.loads(fixed)
```

#### `app/ai.py`

```python
import httpx

def _load_props(path):
    props = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, _, v = line.partition("=")
                props[k.strip()] = v.strip()
    return props

_ai = _load_props("ai.properties")
TEXT_BASE = _ai["ai.base_url"]
TEXT_KEY  = _ai["ai.api_key"]
IMG_BASE  = _ai.get("ai.image_base_url")
IMG_KEY   = _ai.get("ai.image_api_key")

async def llm_chat(messages: list[dict], max_tokens: int = 4096) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{TEXT_BASE}/bedrock_runtime/model/invoke",
            headers={"token": TEXT_KEY, "Content-Type": "application/json"},
            json={
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": messages,
            },
        )
    data = resp.json()
    if data.get("Code") or data.get("Error"):
        raise RuntimeError(f"AI failed: {data}")
    return data["content"][0]["text"]

async def gen_image(prompt: str) -> bytes:
    if not (IMG_BASE and IMG_KEY):
        raise RuntimeError("image AI not configured")  # ❌ 不 fallback
    import base64
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{IMG_BASE}/google/v1:generateContent",
            headers={"api-key": IMG_KEY, "Content-Type": "application/json"},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "maxOutputTokens": 32768,
                },
            },
        )
    data = resp.json()
    if data.get("Code") or data.get("Error"):
        raise RuntimeError(f"image failed: {data}")
    cand = data["candidates"][0]
    reason = cand.get("finishReason")
    if reason and reason not in ("STOP", "MAX_TOKENS"):
        raise RuntimeError(f"image rejected: {reason}")
    for part in cand["content"]["parts"]:
        if "inlineData" in part:
            return base64.b64decode(part["inlineData"]["data"])
    raise RuntimeError("no image in response")
```

#### `app/routes/users.py`

```python
from fastapi import APIRouter, Depends
from app.sso import get_user
from app.db import engine
from sqlalchemy import text

router = APIRouter()

@router.get("/me")
async def me(sso: dict = Depends(get_user)):
    async with engine.begin() as conn:
        row = (await conn.execute(text("""
            INSERT INTO app_users (sso_id, email, username)
            VALUES (:sid, :email, :name)
            ON CONFLICT (sso_id) DO UPDATE
              SET email=EXCLUDED.email, username=EXCLUDED.username
            RETURNING id, sso_id, email, username
        """), {"sid": sso["userId"], "email": sso.get("email"), "name": sso.get("username")})).mappings().first()
    return dict(row)
```

#### `requirements.txt`

```
fastapi
uvicorn[standard]
sqlalchemy
asyncpg
httpx
```
