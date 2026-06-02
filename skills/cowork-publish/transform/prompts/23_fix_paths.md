# 任务：URL 全裸路径 + 移除前缀配置

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

让 subapp 完全不知道自己挂在什么前缀下，源码全写裸路径，让 Guard router 在响应阶段动态注入前缀。

## 必须做的事

### 1. 移除前缀配置

下面这些字段如果出现，**全部删掉**（router 注入前缀，配了就会双前缀 404）：

| 文件 | 字段 |
|---|---|
| `next.config.{js,mjs,ts}` | `assetPrefix` / `basePath` |
| `vite.config.{js,ts}` | `base` |
| `vue.config.{js}` | `publicPath` |
| `nuxt.config.{js,ts}` | `app.baseURL` / `router.base` |
| `webpack.config.js` | `output.publicPath` |
| `package.json` | `homepage`（CRA） |

保持默认 `/`。

### 2. 源码 URL 全部裸路径

- HTML: `<a href="/foo">` `<script src="/...">` `<img src="/...">` 全保留 `/`
- JS fetch: `fetch("/api/foo")` 保留 `/`
- **不要**自己拼 `/s/<app_id>/api/foo`——router 会注入

### 3. redirect 全部相对路径

- FastAPI: `RedirectResponse("./")` 或 `RedirectResponse(url=...)`
- Express: `res.redirect("foo")`（相对，不要 `res.redirect("/foo")` 也不要拼协议）
- Django: `HttpResponseRedirect("foo")`
- **不要**用 `request.url_for()` / `req.protocol + "://"` / `reverse()` 拼绝对 URL

### 4. CSS 不能含 `url(/...)` 绝对路径

router body_filter 不改 text/css，会丢前缀：

```css
/* ❌ */
background: url(/images/bg.png);
/* ✅ */
background: url(../images/bg.png);
/* 或者 import 进 JS 让构建器哈希 */
```

### 5. 上游不能主动压缩

router 的 body_filter 需要明文 HTML：

- Next.js: `next.config.mjs` 设 `compress: false`
- Express: 移除 `app.use(compression())`
- FastAPI/Starlette: 移除 `GZipMiddleware`

### 6. 静态资源挂载放在所有 API 之后

后端如果同时挂 SPA 静态产物 + API：API 路由必须先注册，最后才挂 `StaticFiles(html=True)`。

### 7. FastAPI StaticFiles(html=True) 的 307 陷阱

Starlette `StaticFiles(html=True)` 给目录补斜杠时返回 307 Location 是绝对 URL，泄漏 Pod 内部地址。**必须自定义子类把 Location 改相对**：

```python
from starlette.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

class RelStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if isinstance(resp, RedirectResponse):
            loc = resp.headers.get("location", "")
            # 把绝对 URL 改成只保留 path
            if "://" in loc:
                from urllib.parse import urlparse
                resp.headers["location"] = urlparse(loc).path
        return resp
```

## 例外：服务端拼绝对外链时读 X-Proxy-Base-URL

仅当业务需要生成绝对外链（OAuth 回调、邮件 deep link）时：

```python
base = req.headers.get("X-Proxy-Base-URL", "")           # /s/abc12345
proto = req.headers.get("X-Forwarded-Proto", "https")
host = req.headers.get("X-Forwarded-Host") or req.headers.get("Host", "")
callback_url = f"{proto}://{host}{base}/api/callback"
```

绝大多数业务用不到。

## 验证

外层会跑 `verifiers/verify_no_url_absolute.sh` 和 `verifiers/verify_css_no_abs_url.sh`。
