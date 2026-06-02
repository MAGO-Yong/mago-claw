# 任务：SSO 身份接入按 Guard 契约重写

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

把工程里**所有用户身份**相关的获取代码统一改成"从 `Decrypted-Userinfo` request header 读 JSON + latin-1→utf-8 重编码"，
并彻底删除自建 SSO 验签 / JWT 中间件 / OAuth callback / session cookie 等代码。
Guard 平台已在反代层做完 ECDSA 验签 + OA-Office 权限校验，**子应用不能再做一次**。

## 检测信号（grep 自查）

- 自建 SSO 残留：`/auth/callback` / `/api/login` 走密码 / `passport` / `passport-jwt` / `next-auth` / `@auth/core` /
  `flask-login` / `flask-jwt-extended` / `python-jose` / `pyjwt` 中间件 / `session_cookie`
- 业务代码里读身份的旧入口（这些都要改）：
  - Node：`req.session.user` / `req.user` / `jwt.verify(...)` / `cookies.token` / `localStorage.getItem('token')`
  - Python：`request.session.get("user")` / `current_user` / `Depends(get_current_user)` 内部走 JWT 解码
- 前端 mock 字符串硬编：`Guest` / `Demo` / `Anonymous` / `游客` / `测试` 写在 `displayName` / `currentUser` / `user.name` 默认值上
- 前端身份槽位代码（头像 / 用户名显示）但**没有**调 `/api/session/me`

## 怎么改

### 1. Header 读取（**latin-1→utf-8 必修**）

#### Python（FastAPI）

```python
from fastapi import Request, HTTPException, Depends
import json

def get_user(request: Request) -> dict:
    raw = request.headers.get("Decrypted-Userinfo")
    if not raw:
        raise HTTPException(401, "Not authenticated")
    try:
        raw = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return json.loads(raw)

@app.get("/api/session/me")
async def me(user: dict = Depends(get_user)):
    # 业务表用 UUID 主键时必须 auto-provision，详见下文
    return {"userId": user["userId"], "displayName": user["displayName"], "avatar": user.get("avatar", "")}
```

#### Node.js（Express / Next.js / Koa / NestJS）

```js
function getUser(req) {
  const raw = req.headers["decrypted-userinfo"];   // 自动 lowercase
  if (!raw) return null;
  const fixed = Buffer.from(raw, "latin1").toString("utf-8");
  try { return JSON.parse(fixed); } catch { return null; }
}
```

### 2. Header 字段（**只有 6 个**，业务别自己塞别的）

```json
{"avatar":"https://...","displayName":"张三","email":"...","userId":"60a...","name":"zhangsan","emailAlias":"zhangsan"}
```

`hrUserId` / `department` / `employeeType` 等 HR 字段**不在这里**，业务自己按 `email` 查通讯录，**不要** `user.get("hrUserId", "")` 静默兜空。

### 3. 必须删除的代码

| 类型 | 处理 |
|---|---|
| 自建 `/auth/callback` 路由 | 整段删（Guard 已处理） |
| JWT 中间件 / 验签 | 删（Guard 已签过） |
| session cookie 设置 / 解析 | 删 |
| `passport` / `next-auth` / `flask-login` / `pyjwt` 等依赖 | `package.json` / `requirements.txt` 移除 |
| 自有 `/api/login` 走密码登录 | **仅当面向 SSO 域外用户时保留**；普通内网应用整段删 |

### 4. UUID 主键场景：auto-provision

业务表的 user 行用 UUID 主键（不是 SSO email/userId）时，`/api/session/me` 必须做：

```python
# 伪代码
async def me(user: dict = Depends(get_user)):
    db_user = await db.fetchrow("SELECT id FROM users WHERE email = $1", user["email"])
    if not db_user:
        # 首次访问，按 email 本地段建行
        db_user = await db.fetchrow(
            "INSERT INTO users (email, display_name) VALUES ($1, $2) RETURNING id",
            user["email"], user["displayName"]
        )
    return {"userId": str(db_user["id"]), "displayName": user["displayName"]}  # 返回 DB UUID
```

### 5. 前端身份槽位连线

任何**已有**用户头像 / 用户名显示位的页面，**必须**通过 `/api/session/me` 取真值后渲染：

```jsx
// ❌ 别这么写
const displayName = user?.displayName || "Guest"

// ✅ 这样
const { data: me } = useSWR("/api/session/me", fetcher)
const displayName = me?.displayName  // 没拿到就 loading，不要 fallback "Guest"
const avatar = me?.avatar || "/default-avatar.png"  // avatar 空用占位图
```

**严禁**保留 `Guest` / `Demo` / `Anonymous` / `游客` / `测试` 等 mock 字符串。

## 不要做的事

- ❌ 自己再做一遍 SSO 验签
- ❌ 在前端 localStorage 存 token / userId
- ❌ 把 `Decrypted-Userinfo` 透传给 cookie
- ❌ 因为 avatar 为空就整个头像区不渲染（要用占位图兜底）
- ❌ 业务级权限不做（OA-Office 已经校验完"该用户对该 app 是否有权访问"；细粒度业务鉴权仍是 subapp 的事）

## 验证（外层会自动跑）

- `verifiers/verify_sso_correct.sh` —— 检：
  - 不能有自建 SSO 验签 / JWT 中间件残留
  - `Decrypted-Userinfo` 读取处必须做 `latin-1→utf-8` 重编码
  - 前端不能有 `Guest` / `游客` 等 mock 字符串硬编
