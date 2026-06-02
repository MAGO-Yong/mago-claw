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
| `verify_port_3000` | start.sh 没监听 :3000 | 改 start.sh 启动命令加 `--port 3000` 或对应框架的端口参数 |
| `verify_no_external_infra` | 代码引用 redis/elasticsearch/s3 | 把 redis 改成进程内字典；es 改成数据库 like 查询 |
| `verify_install_no_internet` | install.sh 跑了 `pip install` 走公网 | 加 `-i 内部镜像` 或改成 `--index-url` |
| `verify_db_props_keys` | db.properties.example 多了非标准 key | 只保留 host/port/db/user/password/schema 6 个 key |
| `verify_no_url_absolute` | 源码出现 `http://localhost:8080/api` | 改成裸路径 `/api/...` |
| `verify_css_no_abs_url` | CSS 含 `url(/...)` | 改成相对路径 `url(./...)` 或 `url(../...)` |
| `verify_runtime_full` (Phase 4: asset) | 起服务后某 asset 404 / MIME 错 / 应用层二次 gzip / Next standalone 烧死 prefix | 检查 next.config 的 assetPrefix / vite base 移除前缀配置；Next.js 必须 `compress: false`；asset 路由 MIME 修正 |
| `verify_runtime_full` (Phase 1-3: install/start/health) | install 装包失败 / start 进程秒崩 / health 30s 没通 | 看脚本末 40 行日志按提示修：联网拉包改内部镜像、health 探测端口与 start 监听端口不一致、业务初始化报错 |
| `verify_entry_scripts` | start.sh / install.sh 缺 shebang / 缺 `+x` / 含 BOM 或 CRLF / 缺 `set -eo pipefail` / `bash -n` 语法错 | 按报错对症加 shebang / chmod +x / `dos2unix` / 加 `set -eo pipefail` / 改语法 |
| `verify_db_url_safe` | f-string / 模板字符串把 `db.password` 拼进 connection URL | 改成结构化 API：Python `URL.create(...)` 或 `asyncpg.connect(user=, password=...)`；Node `new Pool({user, password, ...})`。详见 `prompts/20_remove_external_infra.md` 的"PG 连接配置"段 |
| `verify_health_consistency` | health.sh 探非 `/health`（如 `/api/health`、`/healthz`、`/actuator/health`） **或** 业务代码没暴露顶层 `/health` endpoint | 失败原因：违反 Guard 子应用规范——规范统一约定所有子应用必须在端口 3000 上暴露 HTTP `/health`。**两件事都要做**：① 把 `health.sh` 的探测路径改回 `curl http://127.0.0.1:3000/health`（保留 host/port，仅改 path）；② 在主应用顶层加 `/health` endpoint，**必须挂在 `@app.xxx`、不能挂在带 `prefix` 的 router/blueprint**——FastAPI: `@app.get("/health") def health(): return {"ok": True}`；Express: `app.get('/health', (req, res) => res.json({ok: true}))`；Spring: `@RestController class HealthCtrl { @GetMapping("/health") public Map<String,Object> h(){...} }`；Gin: `r.GET("/health", func(c *gin.Context){ c.JSON(200, gin.H{"ok":true}) })`。原有的 `/api/health` 等业务路由可保留共存 |
| `verify_frontend_built` | 前端工程（react/vue/next/vite/svelte/...）有 build script，但 `dist/`、`build/`、`.next/`、`out/`、`.svelte-kit/output/`、`.output/` 全部不存在。云端部署后会缺前端文件（白屏 / 404） | **唯一修复方案：本地构建**。在每个缺产物的前端目录跑 `npm install && npm run build`（autofix 阶段你有 Bash 工具），构建产物会被 stage 60 一并打进 zip。根因常是 stack.json 的 `frontend_dir` 字段未识别正确导致 stage 40 漏跑前端 build，可同时修 `.guard-transform-*-guard/stack.json` 的 `frontend_dir`（但只改 work_dir 内的产物即可让 verifier 通过）。**⚠️ 严禁在 install.sh 中加 build 命令**——Pod 容器通常只有 1C2G，前端 build（webpack/vite/next build）内存开销巨大，会导致 OOM → 容器无限重启 |
| `verify_entry_scripts`(build) | install.sh 含 `npm run build` / `next build` / `vite build` 等构建命令 | **必须删除 install.sh 中的 build 命令**。Pod 容器资源有限（通常 1C2G），前端 build 会导致 OOM 重启。所有构建必须在本地 stage 40 完成，产物打进 zip 交付 |
| `verify_subprocess_lifecycle` | 业务在主服务里 `spawn` / `fork` / `subprocess.Popen` 了一个**常驻子服务**（python 推理 / node sidecar / ffmpeg server / langgraph dev / sandbox …），并踩中以下父子进程组底线：Node `spawn(..., { detached: true })` / `child.unref()` / Python `Popen(..., start_new_session=True)` / `preexec_fn=os.setsid` —— 让子进程**脱离父进程组**，父进程被 kill 时子进程变孤儿（PPID=1）继续占端口/占内存，下次重启 EADDRINUSE，OOM 时不被回收。warn：起了子进程但同文件无 SIGINT/SIGTERM/atexit/`process.on('exit')` 钩子 —— 主进程被 kill 时无法主动 kill 子进程 | **二选一**（按推荐顺序）：**A 父进程必须接管 SIGTERM/SIGINT 转发给子进程**，Node：`const child = spawn(...) /* 不要 detached:true / 不要 child.unref() */; for (const sig of ['SIGINT','SIGTERM']) process.on(sig, () => { child.kill(sig); process.exit(0) })`；Python：`proc = subprocess.Popen(...) /* 不要 start_new_session=True / 不要 preexec_fn=os.setsid */; import atexit, signal; atexit.register(lambda: proc.terminate()); for s in (signal.SIGINT, signal.SIGTERM): signal.signal(s, lambda *_: (proc.terminate(), sys.exit(0)))`；**B ★ 终极方案**：把「子服务」从业务代码里彻底拆出去——业务侧只跑主端口 3000，子服务功能塞进主进程同一端口下的不同路由。⚠️ 端口选择由业务自行负责（建议 49152-65535 IANA Dynamic 范围或 `listen(0)` 动态分配），本 verifier 不再拦截 |
| `verify_venv_activation` | 真实事故：`/home/app/sub-process/start.sh: line 16: exec: gunicorn: not found`。requirements.txt 写了 gunicorn ✓ + install.sh 用 `python3 -m venv .venv` 装包 ✓ —— 但业务**手写**的非根 `.sh`（子进程 / 自定义启动器）调用了 venv-installed Python CLI (`gunicorn` / `uvicorn` / `celery` / `hypercorn` / `daphne` / `flower` / `rq` / `alembic` / `flask` / `django-admin`)，**同文件没激活 venv 也没用 `.venv/bin/X` 绝对路径**。Guard runner 起这些 `.sh` 时 `$PATH` 里只有系统 python3，命令名解析失败立即崩。⚠️ guard-transform 模板渲染的根目录 `start.sh` 已自动注入 `. .venv/bin/activate`，**报错的几乎都是业务自己写的子目录脚本** | **三选一**（按推荐顺序）：**A ★ 脚本头激活 venv（最通用）**：在 `.sh` 头部 `cd "$(dirname "$0")"` 之后加一行 `[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate`（相对路径按子目录层级调整，子目录在 backend_dir 下用 `../`，在更深目录用 `../../` 以此类推）。如果只有 Pod 部署一种场景，可直接写绝对路径 `. /home/app/.venv/bin/activate`。**B 绝对路径调用**：`exec /home/app/.venv/bin/gunicorn ...` —— 不依赖 PATH 解析，最稳但耦合部署路径。**C 删脚本 / 合并到根 start.sh**：如果这个子进程其实可以塞进主进程（同端口 3000 不同路由），直接删除子进程 `.sh` 是更彻底的修复。⚠️ **不要**改成 `exec python -m gunicorn` —— 系统 python3 同样找不到 venv 里的包；唯一例外是 A/B 已实施后再用 `python -m`，那时 `python` 就是 `.venv/bin/python`。⚠️ 不要去删 venv —— Guard pod Python 部署的标准实践就是 venv 隔离，删 venv 会让依赖污染系统 site-packages 且违反隔离性 |

## 输出

- **不要写报告、不要解释**，直接改文件
- 改完外层会自动重跑 verifier；通过即视为成功
- 若你判断这个失败**不是源码问题**（如 verifier 自身 bug、依赖缺失），简短输出一行 `CANNOT_FIX: <原因>` 即可，外层会标记 fail 但不阻塞流水线
