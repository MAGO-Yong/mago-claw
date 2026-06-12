# fastapi-only 模板导读

> **何时读**：选用 `fastapi-only` 模板（`cowork.py scaffold <name> --template fastapi-only`）后、写业务代码前读。
>
> **本文只讲该模板特有的结构与坑**。SSO / AI / DB / 路径等横切规范不在这里重复，统一看 `../sso.md` / `../ai.md` / `../db.md` / `../urls.md`。
> **真实可运行的骨架代码以 `templates/fastapi-only/` 下的实际文件为准**（scaffold 会原样 cp 给你），本文不再贴一份可能漂移的副本。

适用场景：纯后端 Python API / 表单 / dashboard / 不需要独立前端构建的小工具（默认模板）。

## scaffold 生成的真实结构

```
<srcDir>/
├── app.py              # FastAPI 入口：/ + /health + /whoami（内置 _parse_sso_user / _require_user）
├── requirements.txt    # fastapi / uvicorn / （按需加 psycopg[binary] / httpx）
├── install.sh          # python3 -m pip install -r requirements.txt（禁 venv，详见 ../deps-python.md）
├── start.sh            # exec python3 -m uvicorn app:app --host 0.0.0.0 --port ${APP_PORT:-3000}
├── health.sh           # curl /health
└── README.md
```

> ⚠️ `install.sh` / `start.sh` / `health.sh` 是规范产物，**正常不要手改**——只在 scaffold 出来跑不起来时对照 `../scripts-trio.md` 排查。

## 骨架已内置（直接用，别重写）

`app.py` 里已经写好且**符合最新规范**的部分，直接复用：

- `_parse_sso_user(decrypted_userinfo)`：从 `Decrypted-Userinfo` header 解用户，**latin-1 → JSON 两步**（没有 base64 那一步），拿不到返 None
- `_require_user(...)`：拿不到用户 → **401**（Cowork Guard 自动跳登录页）。所有业务路由 MUST 调，**禁止任何 `APP_ENV=="sit"` 之类后门**（precheck 会拦）
- `GET /health`：挂在主 app 顶层（不要挪到带 prefix 的 router 下，否则探活 404）

## 加业务时怎么扩

| 要加什么 | 怎么做 | 先读 |
|---|---|---|
| 业务 API 路由 | 在 `app.py` 直接加 `@app.get/post(...)`，或拆 `APIRouter(prefix="/api")` 后 `include_router` | `../urls.md` |
| 数据库 | `requirements.txt` 加 `psycopg[binary]` 或 `sqlalchemy`+`asyncpg`，读 `db.properties` 6 个 key | `../db.md` |
| AI 调用 | `requirements.txt` 加 `httpx`，走 Runway 网关（文本 Bedrock / 图像 Google） | `../ai.md` |
| 文件上传 | 落 PG Large Object，**不要**写本地磁盘 | `../db.md` §6.3 |

> 骨架默认**不带** `db.py` / `ai.py` / `init_db.py`——这些按需自己建（参考 `../db.md` / `../ai.md` 里的标准实现），不要凭印象写。

## 该模板特有的坑

1. **单文件起步**：骨架就一个 `app.py`，业务变大再拆 `app/` 包（注意 `start.sh` 的 `app:app` 入口要同步改成 `app.main:app`）。
2. **/health 必须顶层**：`@app.get("/health")` 直接挂 `app`，不要挂到 `prefix="/api"` 的 router 上。
3. **端口读 `APP_PORT`**：start.sh 已用 `${APP_PORT:-3000}`，业务源码内若再读端口也用 `os.environ.get("APP_PORT")`，别裸读 `PORT`（详见 `../scripts-trio.md` §5）。

## 写完自检

业务写完、`cowork.py publish` 之前，对照 `../checklist.md` 逐项过一遍。
