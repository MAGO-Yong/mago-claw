# URL 与路径

> **何时读**：改路由 / 重定向 / 静态托管 / 前端构建产物时读。**不要加 basePath/prefix**（router 自动加 `/s/<appId>/`，自己配会双前缀 404）。CSS 不能用 `url(/...)` 绝对路径。FastAPI StaticFiles 307 redirect 陷阱。前端必须 prebuilt（不能在 Pod 里 build）。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 9. URL 与路径

### 9.1 全部用裸路径，**不配** prefix

```javascript
// ❌ 禁止
// next.config.js
module.exports = { assetPrefix: '/my-app', basePath: '/my-app' }

// vite.config.js
export default { base: '/my-app/' }

// webpack
output.publicPath = '/my-app/'
```

```javascript
// ✅ 正确：源码全裸路径，不配 prefix
fetch('/api/users')                   // 不是 fetch('/my-app/api/users')
<img src="/images/logo.png" />        // 不是 src="/my-app/images/logo.png"
router.push('/dashboard')             // 不是 router.push('/my-app/dashboard')
```

**原因**：平台 router 会在响应里做 body filter 把前缀注入到 HTML/JS，源码里写死 prefix 会被双重注入变 `/my-app/my-app/api/...` 404。

### 9.2 重定向必须相对

```python
# ❌
return RedirectResponse("/login")

# ✅
return RedirectResponse("login")          # 相对当前路径
# 或
return RedirectResponse("./login")
# 或带 query
return RedirectResponse("?error=1")
```

### 9.3 CSS 不能 `url(/...)` 绝对路径

```css
/* ❌ verifier verify_css_no_abs_url.sh 会卡 */
.logo { background: url(/images/logo.png); }

/* ✅ 相对路径 */
.logo { background: url(../images/logo.png); }
/* ✅ 或 import 进 JS 让构建器哈希处理 */
```

**原因**：平台 router 的 body filter 不改 `text/css` 内容，CSS 里的绝对路径会丢前缀。

### 9.4 FastAPI StaticFiles 的 307 陷阱

```python
# ❌ 会 307 redirect /static → /static/ → 平台 router 失效
app.mount("/static", StaticFiles(directory="dist/assets"))

# ✅ 显式 html=True + 用 follow_redirects 处理；或直接把静态资源前置由前端 nginx 层处理
app.mount("/static", StaticFiles(directory="dist/assets", html=True))
```

### 9.5 前端必须 **prebuilt**（不要在 Pod 里 build）

```
dist/                  # ✅ 构建产物必须 commit，install.sh 不跑 npm run build
├── index.html
└── assets/...

# ❌ 禁止：install.sh 里跑 npm run build
# 原因：build 依赖 devDependencies + 公网，Pod 装不动
```

verifier `verify_frontend_built.sh` 会检查 `dist/` 或 `.next/standalone/` 是否存在。

### 9.6 不要用压缩中间件

```javascript
// ❌ compression 会把 router body filter 注入前缀的能力废掉
app.use(compression())

// ✅ 不要装 compression 中间件，平台 router 层自己处理
```

---
