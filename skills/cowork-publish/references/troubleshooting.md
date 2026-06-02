# Cowork 部署排错指南

## 部署阶段错误

### `[Install] Required script not found: /home/app/sub-process-next/install.sh`

zip 套了一层目录。

```sh
# 错误打包（套一层目录）
zip -r app.zip myapp/    # 解压后是 myapp/install.sh

# 正确（裸文件）
cd myapp && zip -r ../app.zip .   # 解压后直接 install.sh
```

或用 cowork.py：`pack` 命令默认裸打。

### `install failed: pip install ... timeout` 或 `npm: command not found`

install.sh 调了公网域名 / 用了 Pod 没有的工具。检查：
- 公网 URL：替换成内部镜像
- 系统命令：`apt-get` / `yum` 都没有
- 编译型：Go/Java/Rust 都没有 runtime

### `health check failed`

start.sh 起来但 health.sh 不返回 0。检查：
- bind 是 `0.0.0.0` 不是 `127.0.0.1` ✗（health.sh 用 127.0.0.1 没问题，但服务必须 bind 0.0.0.0）
- 端口是 3000
- 有 `/health` 路由（必须返 200）
- `app.py` / `server.js` 没卡在启动期（DB connect 阻塞、循环引用等）

### `OOM: exit 137 during install`

install.sh 跑了 build（next build / vite build / webpack）。Pod 1-2GB 内存，build 必爆。
**fix**：本地 build → 把产物（.next/standalone, dist/）打进 zip → install.sh 只装 runtime deps。

### `dev server hangs`

start.sh 跑了 `npm run dev` / `vite dev` / `next dev`。dev server 不退出，PM2 会卡。**fix**：用 production server (`next start` / `vite preview` / 自己的 `node server.js`)。

### `worker bind to <container-id>:3000`

Next.js standalone `server.js` 读了 `process.env.HOSTNAME`，Pod 把 HOSTNAME 设成容器 ID。**fix**：build 后 sed `server.js`，把 `process.env.HOSTNAME` 换成 `process.env.APP_HOSTNAME || '0.0.0.0'`。

---

## 上传阶段错误

### `getUploadTempPermit error0!bizCloudConfig-list-empty`

permit 时 `biz_name` 写错。必须 `ep`（不是 `cowork` / `spectrum`）。

### `request reject! cause: old channel closed!`

permit 时没传 `subsystem=web_resource`。这是新通道的强制参数。

### `403 Forbidden` from ROS PUT

permit token 过期或 fileId 不匹配。permit 默认 1-2 小时过期，按需重新拿。

### `SSL_CERT_VERIFY_FAILED`（CLI）

OpenClaw pod 出口走 MITM forward proxy。cowork.py 默认 `verify=False`。不要设 `COWORK_VERIFY_SSL=1`。

---

## save 阶段错误

### `请填写完整信息`

通常是缺 `name` / `imagesJson`（封面图必须）/ `deploymentId`。

### `alias 已被占用`

`deploymentAlias` 全局唯一。换个名或不传走自动 appId。

### `visibility=PARTIAL 时必须指定 visibleUserIds`

部分可见模式下，必须提供 user id 数组或 department id 数组。普通用户用 `SELF_ONLY` 或 `ALL` 更简单。

---

## 应用上线后访问异常

### 浏览器打开 `/s/<alias>/` 报 404

- 检查 `cowork.py status <deploymentId>` 看是不是 RUNNING
- 看 alias 是不是真生效（`cowork.py detail <workId>` 看 `deploymentAlias` 字段）
- 直接试 `/s/<appId>/`（raw 形式）

### 静态资源 404 / 双前缀

源码里配了 `assetPrefix` / `basePath` / `publicPath`，导致变成 `/s/abc/s/abc/_next/...`。删掉这些配置重新 build → redeploy。

### API 请求路径不对

前端 fetch 用 `/api/foo` 而不是 `/s/<id>/api/foo`。Guard router 会自动加前缀，**不要自己拼**。

### 跳转后页面空白

`window.location.href = '/foo'` 这种硬跳走 router 会加前缀，OK；但用 SPA 内部 router（pushState/router.push）有时丢前缀。优先 SPA router 用相对 path（`./foo`）。

---

## 调试技巧

### 用 deploy 单步验证

```sh
# 只部署不发布作品，省得 cowork 列表上看到失败的
python3 cowork.py deploy ./app.zip
# 拿到 deploymentId 后多次 status 查日志
python3 cowork.py status <id>
```

### ⚠️ 不要本地起服务做验证（agent 路径）

**❌ 不要做**：在 OpenClaw pod 里跑 `bash start.sh`、`uvicorn`、`npm run dev`、`curl 127.0.0.1` 等。

**为什么**：

1. **环境不一致**：Cowork Guard 容器 vs OpenClaw pod 镜像不一样，本地起进程跟生产环境永远有差异——验过也白验
2. **会污染 pod**：未管理的后台进程可能撑爆内存 / 端口冲突 / 把 gateway 一并干 crash（真实事故）
3. **耗时长**：本地装依赖 + 起服务通常比直接 `cowork.publish` 还慢

**✅ 正确做法**：直接调 `cowork.publish` → 让 Cowork Guard 平台跑 install.sh / start.sh / health.sh → 拿到结果

如果 publish 失败：

- 读 `deploymentStatus` + `errorMessage`（**真实**的远端日志），定位问题
- 修代码后重新 publish
- **不要本地复现**

如果用户**明确要求**「先本地跑跑看」（极少数场景），让用户**自己**在终端执行：

```sh
# 用户自己跑，不是 agent 跑
python3 cowork.py dev start ./my-app
```

agent 不要代用户执行这个命令。

### 抓官方规范

```sh
# 拿当前规范 CDN url
python3 -c "
import sys; sys.path.insert(0, '/home/node/.openclaw/workspace/skills/cowork-publish')
import cowork
print(cowork.api_call('GET', '/community/works/transform/prompt')['downloadUrl'])
"
# 然后 curl 拿下来给 Claude/CodeWiz 看
```
