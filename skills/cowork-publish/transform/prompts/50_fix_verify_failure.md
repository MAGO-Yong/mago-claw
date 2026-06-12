# 任务：修复 verifier 失败

（系统约束已在上面前置注入；以下是本次原子任务）

## 背景

外层 verifier 跑失败了。你的工作是**根据 verifier 的失败日志和 verifier 脚本自身的判定逻辑**，最小化地修改 `$WORK_DIR` 下的源码或产物，让 verifier 下一次能通过。

## 你拿到的信息

- `VERIFIER_NAME`：失败 verifier 的名字
- `VERIFIER_SCRIPT`：verifier 脚本的内容（让你知道它检查什么）
- `VERIFY_LOG`：verifier 失败时的 stdout+stderr
- `STACK_INFO`：当前项目的 stack.json 摘要（lang/framework/backend_dir/frontend_dir）

## 必须做的事

1. **先理解 verifier 检查什么**：读 `VERIFIER_SCRIPT`，知道判定标准
2. **再读失败日志**：定位是哪些文件 / 哪些行触发了失败
3. **最小修改**：用 Read/Edit/Glob/Grep 工具直接改 `$WORK_DIR` 下的文件
4. **不要改 verifier 自身、不要改 guard-transform/ 目录、不要改 .git/**

## 你不能做的事

- ❌ 改 verifier 脚本（在你工作目录之外）
- ❌ 修改 guard-transform/ 下任何文件
- ❌ 删除整个目录或大段业务代码
- ❌ 联网下载（pip/npm install 都不允许；这些应该在 install.sh 里）
- ❌ 留长篇注释解释你为什么改
- ❌ 大段重构（只动跟 verifier 失败相关的最少行）

## 常见失败模式速查

| verifier | 常见失败 | 典型修复 |
|---|---|---|
| `verify_port_3000` | start.sh / 业务源码端口被写死成字面量 3000；或裸读 `PORT`；或缺 `APP_PORT` 引用 | **start.sh**：顶部 `export APP_PORT="${APP_PORT:-3000}"`，exec 行用 `--port ${APP_PORT}` / `--bind 0.0.0.0:${APP_PORT}`，**不要**写 `--port 3000`。**业务源码**：`process.env.APP_PORT \|\| 3000` / `int(os.environ.get('APP_PORT', '3000'))`，**不要** `app.listen(3000)` / 裸读 `process.env.PORT` |
| `verify_no_external_infra` | 代码引用 redis/elasticsearch/s3 | 把 redis 改成进程内字典；es 改成数据库 like 查询 |
| `verify_install_no_internet` | install.sh 在 pip/npm 行里硬编码了 `-i <URL>` / `--index-url` / `--registry=<URL>` | 删除这些参数，让 Pod 环境的 `PIP_INDEX_URL` / `.npmrc` / `NPM_CONFIG_REGISTRY` 决定源 |
| `verify_db_props_keys` | db.properties.example 多了非标准 key | 只保留 host/port/db/user/password/schema 6 个 key |
| `verify_no_url_absolute` | 源码出现 `http://localhost:8080/api` | 改成裸路径 `/api/...` |
| `verify_css_no_abs_url` | CSS 含 `url(/...)` | 改成相对路径 `url(./...)` 或 `url(../...)` |
| `verify_runtime_full` (Phase 4: asset) | 起服务后某 asset 404 / MIME 错 / 应用层二次 gzip / Next standalone 烧死 prefix | 检查 next.config 的 assetPrefix / vite base 移除前缀配置；Next.js 必须 `compress: false`；asset 路由 MIME 修正 |
| `verify_runtime_full` (Phase 1-3: install/start/health) | install 装包失败 / start 进程秒崩 / health 30s 没通 | 看脚本末 40 行日志按提示修：联网拉包失败（确认 Pod 环境注入了正确的 `PIP_INDEX_URL` / `.npmrc`）、health 探测端口与 start 监听端口不一致、业务初始化报错 |
| `verify_entry_scripts` | start.sh / install.sh 缺 shebang / 缺 `+x` / 含 BOM 或 CRLF / 缺 `set -eo pipefail` / `bash -n` 语法错 | 按报错对症加 shebang / chmod +x / `dos2unix` / 加 `set -eo pipefail` / 改语法 |
| `verify_db_url_safe` | f-string / 模板字符串把 `db.password` 拼进 connection URL | 改成结构化 API：Python `URL.create(...)` 或 `asyncpg.connect(user=, password=...)`；Node `new Pool({user, password, ...})`。详见 `prompts/20_remove_external_infra.md` 的"PG 连接配置"段 |
| `verify_health_consistency` | health.sh 探非 `/health`（如 `/api/health`、`/healthz`、`/actuator/health`） **或** 业务代码没暴露顶层 `/health` endpoint | 失败原因：违反 Guard 子应用规范——规范统一约定所有子应用必须在 `APP_PORT`（默认 3000）上暴露 HTTP `/health`。**两件事都要做**：① 把 `health.sh` 的探测路径改回 `curl -fsS http://127.0.0.1:${APP_PORT:-3000}/health`（保留 host=127.0.0.1 + `${APP_PORT:-3000}`，仅改 path）；② 在主应用顶层加 `/health` endpoint，**必须挂在 `@app.xxx`、不能挂在带 `prefix` 的 router/blueprint**——FastAPI: `@app.get("/health") def health(): return {"ok": True}`；Express: `app.get('/health', (req, res) => res.json({ok: true}))`；Spring: `@RestController class HealthCtrl { @GetMapping("/health") public Map<String,Object> h(){...} }`；Gin: `r.GET("/health", func(c *gin.Context){ c.JSON(200, gin.H{"ok":true}) })`。原有的 `/api/health` 等业务路由可保留共存 |
| `verify_frontend_built` | 前端工程（react/vue/next/vite/svelte/...）有 build script，但 `dist/`、`build/`、`.next/`、`out/`、`.svelte-kit/output/`、`.output/` 全部不存在。云端部署后会缺前端文件（白屏 / 404） | **唯一修复方案：本地构建**。在每个缺产物的前端目录跑 `npm install && npm run build`（autofix 阶段你有 Bash 工具），构建产物会被 stage 60 一并打进 zip。根因常是 stack.json 的 `frontend_dir` 字段未识别正确导致 stage 40 漏跑前端 build，可同时修 `.guard-transform-*-guard/stack.json` 的 `frontend_dir`（但只改 work_dir 内的产物即可让 verifier 通过）。**⚠️ 严禁在 install.sh 中加 build 命令**——Pod 容器通常只有 1C2G，前端 build（webpack/vite/next build）内存开销巨大，会导致 OOM → 容器无限重启 |
| `verify_entry_scripts`(build) | install.sh 含 `npm run build` / `next build` / `vite build` 等构建命令 | **必须删除 install.sh 中的 build 命令**。Pod 容器资源有限（通常 1C2G），前端 build 会导致 OOM 重启。所有构建必须在本地 stage 40 完成，产物打进 zip 交付 |
| `verify_subprocess_lifecycle` | 业务在主服务里 `spawn` / `fork` / `subprocess.Popen` 了一个**常驻子服务**（python 推理 / node sidecar / ffmpeg server / langgraph dev / sandbox …），并踩中以下父子进程组底线：Node `spawn(..., { detached: true })` / `child.unref()` / Python `Popen(..., start_new_session=True)` / `preexec_fn=os.setsid` —— 让子进程**脱离父进程组**，父进程被 kill 时子进程变孤儿（PPID=1）继续占端口/占内存，下次重启 EADDRINUSE，OOM 时不被回收。warn：起了子进程但同文件无 SIGINT/SIGTERM/atexit/`process.on('exit')` 钩子 —— 主进程被 kill 时无法主动 kill 子进程 | **二选一**（按推荐顺序）：**A 父进程必须接管 SIGTERM/SIGINT 转发给子进程**，Node：`const child = spawn(...) /* 不要 detached:true / 不要 child.unref() */; for (const sig of ['SIGINT','SIGTERM']) process.on(sig, () => { child.kill(sig); process.exit(0) })`；Python：`proc = subprocess.Popen(...) /* 不要 start_new_session=True / 不要 preexec_fn=os.setsid */; import atexit, signal; atexit.register(lambda: proc.terminate()); for s in (signal.SIGINT, signal.SIGTERM): signal.signal(s, lambda *_: (proc.terminate(), sys.exit(0)))`；**B ★ 终极方案**：把「子服务」从业务代码里彻底拆出去——业务侧只跑主端口 3000，子服务功能塞进主进程同一端口下的不同路由。⚠️ 端口选择由业务自行负责（建议 49152-65535 IANA Dynamic 范围或 `listen(0)` 动态分配），本 verifier 不再拦截 |
| `verify_no_venv_creation` | 真实事故（语义反转后的根因）：`bash: .venv/bin/gunicorn: cannot execute: required file not found`。requirements.txt 写了 gunicorn ✓ + install.sh 用 `python3 -m venv .venv && pip install` 装包 ✓ —— 但 (1) bookworm 镜像 `python3-venv` 单包不带 ensurepip 的 pip wheel（pip 在 `python3-pip` 里），新建嵌套 .venv 没 pip → install.sh 立刻挂；(2) pip 写出的 console_script (`.venv/bin/gunicorn` / `uvicorn` …) shebang 写死创建时刻的 venv python 绝对路径（如 `#!/home/app/sub-process-next/.venv/bin/python3.11`），guard-rust 启动期会 `fs::rename` 工程目录到 `releases/<url_key>/`，路径变了 shebang 没变 → execve ENOENT → bash 把 ENOENT 翻译成上面那行误导性报错；(3) `.venv/` 还经常被误打进 zip 把上面两个问题原封带进 Pod。**根治方案是不在工程内建 venv**，依赖 Pod 镜像 Dockerfile `ENV PATH=/opt/venv/bin:$PATH` 提供的全局 venv | **删掉所有 venv 创建语句，改用全局 venv**：`install.sh` 装依赖直接 `python3 -m pip install --no-cache-dir -r requirements.txt`（无需 venv 创建/激活；解析到 `/opt/venv/bin/python3` 装到 `/opt/venv/lib/python*/site-packages/`）；`start.sh` 启动直接 `exec python3 -m gunicorn --bind 0.0.0.0:${APP_PORT} app:app 2>&1`（同样靠 PATH 解析到 `/opt/venv/bin/python3`，由 `python3 -m` 加载 gunicorn 模块，不走 console_script，shebang 路径稳定）。⚠️ **不要**留 `python3 -m venv ...` 兜底分支 —— guard-rust rename 之后所有这种 .venv 都会爆，没有"鲁棒"的写法。⚠️ **不要**留 `[ -f .venv/bin/activate ] && source .venv/bin/activate` 残留 —— 一旦它生效又会复现 ENOENT。⚠️ **不要**改成 `exec gunicorn` 裸命令 —— gunicorn console_script 自身的 shebang 同样会被 rename 干掉，必须走 `python3 -m gunicorn` |

## 输出

- **不要写报告、不要解释**，直接改文件
- 改完外层会自动重跑 verifier；通过即视为成功
- 若你判断这个失败**不是源码问题**（如 verifier 自身 bug、依赖缺失），简短输出一行 `CANNOT_FIX: <原因>` 即可，外层会标记 fail 但不阻塞流水线
