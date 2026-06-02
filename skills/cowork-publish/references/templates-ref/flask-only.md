# flask-only 模板参考

> **何时读**：选用 `flask-only` 模板后写业务代码时读。
>
> 适用场景：Flask 后端 / 老项目迁移中间站 / 不需要 SPA 的简单 web 工具。

## scaffold 已给好

调 `cowork.scaffold_app({ template: 'flask-only' })` 后，目录下含：

```
<srcDir>/
├── app.py              # Flask app，含 / / /health / /whoami（SSO 解析）
├── requirements.txt    # flask==3.0.3 / gunicorn==23.0.0 / psycopg[binary]==3.2.3
├── install.sh          # venv 隔离 + pip install
├── start.sh            # 末行 exec gunicorn --bind 0.0.0.0:${APP_PORT}
├── health.sh           # curl -fsS http://127.0.0.1:${APP_PORT}/health
└── README.md
```

**install.sh / start.sh / health.sh / .npmrc 都不要手改**——是官方 guard-transform 渲染产物。

## /health endpoint 框架代码

`app.py` 里已有：

```python
@app.get("/health")
def health():
    return jsonify(ok=True)
```

⚠️ **必须挂主 app 顶层**，不能挂 `Blueprint` 带 prefix 下（路径会变 `/<prefix>/health` 探不到）。

## DB 接入（PostgreSQL via db.properties）

详见 `../db.md`。Flask 推荐用 `psycopg[binary]==3.2.3`（不要 psycopg2）+ 关键字参数：

```python
# app/db.py
import psycopg, contextlib
from pathlib import Path

def _load_db_properties(path="db.properties"):
    p = Path(__file__).resolve().parent / path
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

_PROPS = _load_db_properties()

@contextlib.contextmanager
def get_conn():
    # ⚠️ 必须用关键字参数，不能字符串拼 URL（password 含 @ : / 会崩）
    conn = psycopg.connect(
        host=_PROPS["db.host"],
        port=int(_PROPS.get("db.port", 5432)),
        dbname=_PROPS["db.database"],
        user=_PROPS["db.username"],
        password=_PROPS["db.password"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

DB DDL 在 `install.sh` 里跑（必须幂等）：

```bash
# install.sh 末尾
.venv/bin/python -c "
from app.db import get_conn
with get_conn() as c:
    c.cursor().execute('''
        CREATE TABLE IF NOT EXISTS items (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')
"
```

## SSO 接入（Hard Rule #4 强制）

详见 `../sso.md`。Flask 推荐 helper：

```python
# app/sso.py
import base64, json, os
from flask import request

def parse_sso_user():
    """从 Decrypted-Userinfo header 解析当前用户。
    生产环境必有；本地 SIT 兜底用 sso-email header（仅 APP_ENV=sit 时生效）。
    """
    header = request.headers.get("Decrypted-Userinfo")
    if header:
        try:
            raw = header.encode("latin-1").decode("utf-8")
            data = json.loads(base64.b64decode(raw).decode("utf-8"))
            return {
                "email": data.get("email") or data.get("workEmail"),
                "name": data.get("name") or data.get("displayName"),
                "userId": data.get("userId") or data.get("id"),
            }
        except Exception:
            pass
    if os.environ.get("APP_ENV") == "sit":
        email = request.headers.get("sso-email")
        if email:
            return {"email": email, "name": email.split("@")[0], "userId": "sit-dev"}
    return None
```

业务 route 用法：

```python
from flask import abort
from app.sso import parse_sso_user

@app.get("/api/items")
def list_my_items():
    user = parse_sso_user()
    if not user:
        abort(401)
    with get_conn() as c:
        rows = c.cursor().execute(
            "SELECT id, name FROM items WHERE created_by = %s",
            (user["email"],)
        ).fetchall()
    return jsonify(items=[{"id": r[0], "name": r[1]} for r in rows])
```

## AI 接入（必须走 Runway，详见 `../ai.md`）

```python
# app/ai.py
import os, requests
from pathlib import Path

def _load_ai_properties():
    p = Path(__file__).resolve().parent / "ai.properties"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

_AI = _load_ai_properties()

def call_text(messages, model=None, max_tokens=2000):
    """Runway Bedrock (Anthropic Messages 协议)。"""
    url = _AI["ai.text.endpoint"]
    headers = {
        "Authorization": f"Bearer {_AI['ai.text.api_key']}",
        "Content-Type": "application/json",
        "anthropic-version": "bedrock-2023-05-31",
    }
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    r = requests.post(url, json=body, headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    # ⚠️ Runway 200 OK 也可能返业务错，必须检查
    if "error" in data:
        raise RuntimeError(f"Runway error: {data['error']}")
    return data["content"][0]["text"]
```

## 业务路由完整示例

```python
# app.py
from flask import Flask, jsonify, request, abort
from app.sso import parse_sso_user
from app.db import get_conn
from app.ai import call_text

app = Flask(__name__)

@app.get("/")
def index():
    return jsonify(service="my-flask-tool", msg="ok")

@app.get("/health")
def health():
    return jsonify(ok=True)

@app.post("/api/items")
def create_item():
    user = parse_sso_user()
    if not user:
        abort(401)
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify(error="name required"), 400
    with get_conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO items (name, created_by) VALUES (%s, %s) RETURNING id",
            (name, user["email"])
        )
        item_id = cur.fetchone()[0]
    return jsonify(id=item_id, name=name)

@app.post("/api/ai/summarize")
def ai_summarize():
    user = parse_sso_user()
    if not user:
        abort(401)
    text = (request.get_json(silent=True) or {}).get("text", "")
    if not text:
        return jsonify(error="text required"), 400
    summary = call_text([
        {"role": "user", "content": f"用一句话总结：\n{text}"}
    ], max_tokens=500)
    return jsonify(summary=summary)
```

## 该模板特有的 5 个坑

1. **gunicorn worker 数**：start.sh 默认单 worker。Flask 同步 IO 时如需更高并发，加 `--workers 4`，但 cowork pod 内存有限，3-4 是上限。
2. **session 不要用文件**：Flask `session` 默认 cookie-based 即可。**不要**用 `flask-session` + filesystem backend——pod 重启丢。需要 server-side session 走 PG。
3. **静态文件**：`app.static_folder = 'static'`（默认）即可。**不要**写绝对路径 `/static/foo.css`，CSS 用相对路径。详见 `../urls.md` §9.3。
4. **请求体最大 size**：`app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024` 设上限（16MB 默认够），超限返 413。
5. **bg task**：Flask 没有 Celery 这种东西。**不能**起后台进程（pod 一进程模型）。重活同步跑、不能超过 health check 间隔（30s）。

## 完整参考实现

复杂业务可以照搬 `fastapi-only.md`（结构一样，只是 FastAPI 路由 → Flask 路由）。其他 cross-cutting：

- `../db.md` — DB 完整规范
- `../sso.md` — SSO 完整规范
- `../ai.md` — AI 完整规范
- `../urls.md` — URL / 静态资源
- `../deps-python.md` — Python 依赖管理
- `../checklist.md` — 写完自检
- `../blacklist.md` — 禁项速查
