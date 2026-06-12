# 纯前端应用（静态资源挂载）

> **何时读**：用户要做的是**纯前端**站点/应用（只有 HTML/CSS/JS、无后端进程、不需要数据库/AI/SSO），或 `cowork publish` 时 detect 判定为 `STATIC_RESOURCE` 时读。
>
> 纯前端走「静态资源挂载」类型，**与应用部署完全不同的链路**：直接把打包后的静态资源挂到 `cowork-static-server`，同步返回，不跑 install.sh / start.sh / health.sh，不分配 Pod，不轮询。

---

## 1. 两种部署类型对照

| 维度 | 应用部署 `APP_DEPLOY` | 静态资源挂载 `STATIC_RESOURCE` |
|---|---|---|
| 适用 | 有后端进程（Node/Python 服务）、需要 DB/AI/SSO | 纯前端（HTML/CSS/JS），无后端 |
| 三件套 install/start/health | ✅ 必须 | ❌ 不需要 |
| 打包入口 | 顶层 `install.sh` | 顶层 `index.html` |
| 后端能力（PG/AI/SSO） | ✅ 平台注入 | ❌ 没有，别用 |
| 部署方式 | `deploy_zip` → 轮询 `wait_deploy` | `static-deploy` 同步返回 |
| 返回 | `deploymentId` | `staticResourceId`（appId 前缀 `sr_`） |
| 访问 URL | `https://cowork.xiaohongshu.com/s/<alias>` | `https://cowork.xiaohongshu.com/f/<alias 优先，无则 sr_appId>/` |
| save_work 关键字段 | `deploymentId` + `workDeployType=APP_DEPLOY` | `staticResourceId` + `workDeployType=STATIC_RESOURCE` |

> **自动分流**：`cowork publish` / `cowork redeploy` 内部 pack 完后会调一次 `detect-code-package-type` 自动判类型，命中 `STATIC_RESOURCE` 就走本文链路，无需手动指定。

---

## 2. 纯静态打包规范（硬规则）

### 2.1 必须

- ✅ **根目录必须有 `index.html`**（挂载入口，也是 detect 判 STATIC_RESOURCE 的锚点）。
- ✅ 所有资源用**相对路径**引用（`./assets/x.js`、`assets/x.css`），不要绝对路径 `/assets/...`——平台 router 会自动注入访问前缀，绝对路径会 404。
- ✅ 构建产物（如 Vite/React 的 `dist/`）**摊平到 zip 顶层**：让 `index.html` 在根，而不是 `dist/index.html`。

### 2.2 扩展名白名单

静态挂载只接受以下扩展名的文件，其它会被忽略/拒绝：

```
.html .htm  .css  .js .mjs .cjs  .json  .map
.png .jpg .jpeg .gif .svg .webp .ico .bmp
.woff .woff2 .ttf .otf .eot
.txt .xml .csv  .pdf  .mp4 .webm .mp3 .wav
```

> 需要其它类型先确认是否真的纯前端必需；动态内容应改走应用部署。

### 2.3 黑名单文件（禁止出现在 zip 里）

纯前端 zip 里出现这些会被判为「未转写的应用部署」或直接拒绝：

- ❌ `install.sh` / `start.sh` / `health.sh`（三件套——有它就是应用部署）
- ❌ `package.json` / `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml`
- ❌ `node_modules/`
- ❌ `requirements.txt` / `pyproject.toml` / `Pipfile` / `*.py`
- ❌ `Dockerfile` / `docker-compose.yml` / `Makefile`
- ❌ `vite.config.*` / `webpack.config.*` / `tsconfig.json` 等构建配置（产物已 build 好，源配置不上传）
- ❌ `.env` / `.env.*`
- ❌ `.git/` / `.idea/` / `.vscode/` / `*.log`

> 简记：**纯前端 zip 里只放浏览器要的东西**（白名单里那些），构建工具、依赖清单、源配置一概不放。

---

## 3. 最小骨架

```
my-page/
├── index.html          # 必须，挂载入口
├── assets/
│   ├── app.js
│   └── style.css
└── img/
    └── logo.png
```

`index.html` 用相对路径引用：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Page</title>
  <link rel="stylesheet" href="./assets/style.css">
</head>
<body>
  <div id="app"></div>
  <img src="./img/logo.png" alt="logo">
  <script src="./assets/app.js"></script>
</body>
</html>
```

> Vite/React/Vue 项目：`npm run build` 后把 `dist/` 里的内容（含 `index.html`）摊平到一个目录，确保 `index.html` 在顶层，再 `cowork publish` 该目录。Vite 记得设 `base: './'` 让产物用相对路径。

---

## 4. 发布 / 更新

发布和更新命令与应用部署**一样**，detect 会自动分流：

```bash
# 首发
cowork publish ./my-page --title "我的页面" --intro "一句话简介"

# 更新（重新发布到同一个 work）
cowork redeploy ./my-page --work-id <workId>
```

- 静态挂载 `static-deploy` **同步返回**，成功即 `status=MOUNT_SUCCESS`，没有轮询等待。
- 别名：`--alias <name>` 自定义访问短链，访问 URL 变成 `/f/<alias>/`；不传则用 `/f/sr_<appId>/`。
- 发布后 `.cowork.json` 会写入 `workDeployType=STATIC_RESOURCE`、`staticResourceId`、`accessUrl` 等，更新时据此回传，避免丢数据。
- 发布 / 更新成功后**直接把 `accessUrl` 给用户在浏览器打开查看即可**，挂载好的线上页面就是最终效果，**不需要再去 Canvas 画一遍预览**。

---

## 5. 常见误区

| 误区 | 正解 |
|---|---|
| 「纯前端也要写 install.sh」 | ❌ 纯前端不需要三件套，有 install.sh 反而会被判成应用部署 |
| 「资源用 `/assets/x.js` 绝对路径」 | ❌ 用相对路径 `./assets/x.js`，平台会注入前缀 |
| 「把整个项目（含 node_modules、源码、配置）打包」 | ❌ 只打 build 产物，黑名单文件一律不放 |
| 「`dist/index.html` 嵌一层目录」 | ❌ 摊平到顶层，`index.html` 必须在 zip 根 |
| 「纯前端里调 PG/AI」 | ❌ 静态挂载没有后端能力，要用就改走应用部署 |
| 「静态页要加后端 → 新建一个全栈作品」 | ❌ 直接对原作品 `cowork.py redeploy <workId>` 升级即可，同一作品支持静态↔应用来回切换（detect 自动切类型、两通道后端共存），不要新建作品 |
| 「static-deploy 后还要轮询查状态」 | ❌ 同步返回 `MOUNT_SUCCESS` 即完成 |
| 「发布/更新静态资源后再去 Canvas 画一遍预览」 | ❌ 没必要——挂载好的线上页面就是最终效果，直接把 `accessUrl` 给用户在浏览器打开看即可 |
