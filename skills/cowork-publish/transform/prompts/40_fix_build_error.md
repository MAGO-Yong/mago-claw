# 任务：修复 build 失败

（系统约束已在上面前置注入；以下是本次原子任务）

## 背景

外层在改写机上跑 `npm install` / `npm run build` / `pip install -r requirements.txt` 时失败了。
你的工作是**修依赖配置 / 构建配置**让 build 能通过，**不要去修业务源码**。

## 你拿到的信息

- `BUILD_DIR`：build 跑失败的目录（可能是 `backend/` / `frontend/` / `.`）
- `BUILD_LOG`：失败时的命令输出
- `PACKAGE_JSON` 或 `REQUIREMENTS`：相关的依赖文件内容
- `ATTEMPT`：第几次尝试（≥1）；前几次失败的修复尝试也会附在 prompt 末尾

## 允许做的修复

1. **删 lockfile + 改 install 策略**：删 `package-lock.json` / `pnpm-lock.yaml` 重装；npm 加 `--legacy-peer-deps`
2. **降级/升级依赖到兼容版本**：改 `package.json` 的 `dependencies` / `devDependencies` 里某个包的版本范围
3. **临时移除阻塞 build 的 lint/typecheck 步骤**：例如 `"build": "vue-tsc && vite build"` → `"build": "vite build"`，配套加注释说明
4. **修 tsconfig 错误**：删非法 compilerOption、给 `composite: true` 的 reference 加这个字段
5. **改 requirements.txt 的版本约束**：把 `<` 改 `<=`、删过严的 pin
6. **加 .npmrc / pip 配置**：但**不要加内部镜像地址**（改写机有公网，install.sh 渲染会处理 Pod 镜像）

## 不允许做的事

- ❌ 改 `$BUILD_DIR/src/` 下任何业务代码
- ❌ 删 `.git/` / 删整个项目目录
- ❌ 改 `guard-transform/` 任何文件
- ❌ 跑 `curl` / `wget` 下载二进制
- ❌ 写解释文档 / README
- ❌ 加大量注释

## 已知好用的修复套路

| 错误特征 | 修复 |
|---|---|
| `Cannot find module '../index.js'` from `node_modules/.bin/<x>` | `node_modules/.bin/<x>` shim 损坏；删除 node_modules 整个目录后重装能修，不要改源码 |
| `Unknown compiler option 'xxx'` | 删 `tsconfig.json` 里这个非法字段 |
| `Referenced project must have setting "composite": true` | 给被 reference 的 tsconfig 加 `"composite": true` |
| `peer dep` 冲突 | npm 加 `--legacy-peer-deps`，写到 .npmrc |
| `python: error: subprocess-exited-with-error` (pip) | 看具体包；通常降级或换更松版本约束 |
| `OOM` / `JavaScript heap out of memory` | 已经设了 NODE_OPTIONS=4096，可调 8192 |

## 输出

- 直接改文件
- 改完外层会自动重跑 build；通过即视为成功
- 多次仍无法修复时，输出一行 `CANNOT_FIX: <原因简短>` 让外层标 fail 不阻塞
