# SSO 用户身份

> **何时读**：**Hard Rule #4：所有项目必须接入 SSO，公司安全规范**。从 `Decrypted-Userinfo` HTTP header 解（latin-1 → JSON 两步，不是三步，没有 base64 那一步）。scaffold 已封装 helper，调 helper 即可。不需要识别用户身份的场景仍然要写流转代码（只是业务里 ignore parsed user）。
>
> **严禁 SSO bypass 后门**：
>
> - “SSO 拼不出用户”唯一正确处理是 **return 401**（或抛 401），让 Cowork Guard 处理登录跳转。禁止改成 `user = {"email":"anonymous"}`、`user = {"userId":"anon"}`、`user = {"name":"Guest"}` 这类匿名 fallback。
> - 禁止写 `if APP_ENV == "sit": return mock_user`、`if DEV_SSO_BYPASS == "1"`、`if NODE_ENV != "production"` 类环境变量跳 SSO 逻辑。
> - 禁止自造 `sso-email` / `x-user-email` header 作为兜底身份。
> - publish precheck 会拦上述模式。本地调试请用浏览器插件（ModHeader / Header Editor）手动注入 `Decrypted-Userinfo` header，不要改代码绕过。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 8. SSO 用户身份

### 8.1 平台注入 header

平台在所有请求头里注入：

```
Decrypted-Userinfo: {"userId":"123","username":"jun_zhi","email":"jun_zhi@xiaohongshu.com",...}
```

**坑**：这个 header 的值是 UTF-8 字节序列被 HTTP 层用 latin-1 解码后塞进来的，**直接 `json.parse` 会乱码**（中文用户名变 `ä¸­æ–‡`）。必须先重编码：

```python
# ✅ FastAPI / Starlette
import json
from fastapi import Request, HTTPException

def get_user(request: Request):
    raw = request.headers.get("decrypted-userinfo")  # header 不区分大小写
    if not raw:
        raise HTTPException(401, "no sso header")
    # ⚠️ latin-1 → utf-8 重编码
    fixed = raw.encode("latin-1").decode("utf-8")
    return json.loads(fixed)
```

```javascript
// ✅ Express
function getUser(req) {
  const raw = req.headers['decrypted-userinfo']
  if (!raw) throw new Error('no sso header')
  // ⚠️ latin-1 → utf-8 重编码
  const fixed = Buffer.from(raw, 'latin1').toString('utf-8')
  return JSON.parse(fixed)
}
```

### 8.2 Auto-Provision（首次登录自动建用户）

平台不会替你建业务侧用户表，第一次见到一个 SSO 用户时要自动 upsert：

```python
async def get_or_create_user(conn, sso):
    row = await conn.fetchrow(
        """
        INSERT INTO app_users (sso_id, email, username, created_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (sso_id) DO UPDATE SET
          email = EXCLUDED.email,
          username = EXCLUDED.username
        RETURNING id, sso_id, email, username
        """,
        sso["userId"], sso["email"], sso["username"],
    )
    return dict(row)
```

### 8.3 SSO 禁项（verifier `verify_sso_correct.sh` 会卡）

- ❌ 自己实现 JWT 签发/校验（`jsonwebtoken` / `pyjwt` / `python-jose`）
- ❌ 用 `passport` / `next-auth` / `auth0` / `firebase-auth` / `clerk`
- ❌ 自己写登录页面 / OAuth callback
- ❌ 用 `req.session` / `cookie-session` 维持登录态（直接每次读 header 即可）
- ❌ 不做 latin-1 → utf-8 重编码（中文/特殊字符用户全部乱码）
- ❌ 缓存 sso → user 映射后不及时更新（用户改名 / 换邮箱后业务侧仍是旧值）

---
