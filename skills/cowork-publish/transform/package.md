# 子能力 2：项目打包

> 本文档由 [`SKILL.md`](SKILL.md) 的 "入口 2：项目打包" 分发而来。所有命令默认 `$GUARD_TRANSFORM_HOME` / `$SRC_PROJECT` / `$GUARD_RUN_MODE` 已就绪。

## ⚠️ Step 0：路径语义澄清 + 入口判定

> **重要语义**：`cowork-package-verify` / `transform.sh` / `bin/guardx verify` 这一族命令的入参**永远是源工程路径**（如 `~/code/my-app/`），命令**内部**会自动在同级查找 `<src>-guard/` 副本目录并对它做 verify / 打包。**不要**直接把 `<src>-guard/` 副本路径传进去——那会让命令内部推导出 `<src>-guard-guard/` 不存在的双重目录然后崩溃。
>
> 所以"打包"流程里 `$PKG_TARGET` 始终是**源工程路径**（无 `-guard` 后缀）；副本（`<src>-guard/`）由命令自己推导。**真正会变的**是 agent 在会话里 read_file 时**该操作哪个目录**——那是 `transform.md` Step 4.5 已经处理的另一件事（操作副本，不动源工程）。

**必做的入口判定**（agent 拿到"打包/重新打包"意图时一律先跑一次）：

```bash
# 优先级：
#   1. 用户在本次对话里明确给了路径 → 用它，转绝对路径；如果用户误传了 -guard/ 副本路径，自动剥掉后缀指回源工程
#   2. 上一轮 transform.md Step 4.5 记下的 GUARD_ACTIVE_DIR（指副本）→ 剥 `-guard` 后缀得到源工程
#   3. $SRC_PROJECT 已是源工程 → 直接用，但要求同级必须有 <name>-guard/ 副本，否则警告"工程没转写过"
PKG_TARGET=""
if [ -n "<用户本次明确给的路径>" ]; then
    p="$(cd "<用户明确给的路径>" && pwd)"
    case "$p" in
        *-guard) PKG_TARGET="${p%-guard}"
                 echo "[cowork-skill] 用户传入的是副本路径 $p，已自动剥 -guard 后缀指回源工程 $PKG_TARGET" >&2 ;;
        *)       PKG_TARGET="$p" ;;
    esac
elif [ -n "$GUARD_ACTIVE_DIR" ] && [ -d "$GUARD_ACTIVE_DIR" ]; then
    # GUARD_ACTIVE_DIR 是副本路径（transform.md Step 4.5 切过的），剥后缀拿回源工程
    PKG_TARGET="${GUARD_ACTIVE_DIR%-guard}"
elif [ -n "$SRC_PROJECT" ]; then
    PKG_TARGET="$SRC_PROJECT"
else
    echo "[cowork-skill] [FAIL] 无法判定源工程路径（$SRC_PROJECT 和 $GUARD_ACTIVE_DIR 都为空）" >&2
    exit 4
fi
export PKG_TARGET

# 检查副本是否存在（首次打包时副本可能不存在；这种工程必须本身已合规）
if [ ! -d "${PKG_TARGET}-guard" ]; then
    echo "[cowork-skill] ⚠️ 未发现副本 ${PKG_TARGET}-guard/，将直接对源工程 $PKG_TARGET 跑 verify+打包" >&2
    echo "[cowork-skill] ⚠️ 这要求 $PKG_TARGET 本身已符合 CoWork 子应用规范（install.sh/start.sh/health.sh 等）" >&2
fi

echo "[cowork-skill] 打包目标源工程: $PKG_TARGET（副本: ${PKG_TARGET}-guard/）"
```

> **下面 Step 1/2/3 所有命令都用 `$PKG_TARGET`**（源工程路径）。命令内部会自己找 `${PKG_TARGET}-guard/` 副本做 verify 和打包。

## 概览

项目打包 = 在**已经转写过的**（或本身已合规的）工程上做"**打包前体检 + 实际打包**"，避免把带伤产物上传到平台。两个核心动作：

1. **基础合规验证**（shell 脚本，~30 秒）：复用 guard-transform 的 25+ 个 verifier，校验 `install.sh` / `start.sh` / `health.sh` 是否符合 CoWork 子应用规范
2. **前端构建产物时效性检查**（前后端分离专用）：扫描前端目录的源码 mtime 与构建产物 mtime，**产物若早于源码 → 产物已过期**，需要重新 build

通过后，调起 `transform.sh --from-stage 60 -y` 完成 zip 打包（带 `MMDDhhmm` 时间戳，不覆盖历史产物）。

> **为什么不直接调 `--from-stage 60`**：stage 60_package 只做 zip 打包，**不跑 verifier**；用户在 `<src>-guard/` 手改可能引入新违规、或让前端产物过期，这些问题在云端部署时才暴露 → 白屏 / 容器起不来 / 探活超时。

## Step 1：跑独立打包前体检（cowork-package-verify）

```bash
"$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" "$PKG_TARGET"
```

脚本输出格式：

```
=== Phase 1: 基础合规验证（25 个 verifier）===
[OK]   verify_entry_scripts
[OK]   verify_health_consistency
[FAIL] verify_frontend_built  → 详见 .guard-transform-*-guard/verify-verify_frontend_built.log
...

=== Phase 2: 前端构建产物时效性检查 ===
[FE]   检测到 1 个前端目录: frontend/
       构建产物: frontend/dist/index.html (mtime: 2025-05-20 10:32:11)
       源码最新修改: frontend/src/App.tsx (mtime: 2025-05-20 14:55:03)
[STALE] 源码新于产物 4h22m，产物已过期，建议重新构建

=== 总结 ===
基础验证: 24 PASS / 1 FAIL
前端产物: 1 STALE / 0 OK
退出码: 2  (0=全OK / 1=基础验证fail / 2=前端产物stale / 3=两者都有问题)
```

退出码语义：

| 退出码 | 含义 | 推荐处理 |
| --- | --- | --- |
| 0 | 全部通过 | 直接进入 Step 3 打包 |
| 1 | 仅基础验证失败 | 进入 Step 2A 处理 verifier fail |
| 2 | 仅前端产物过期 | 进入 Step 2B 处理前端 stale |
| 3 | 两者都失败 | 先按 Step 2B 重 build 前端，再按 Step 2A 修 verifier |

## Step 2A：有 verifier fail 时（基础合规失败）→ 按运行模式分流

> 无论哪种模式，都**不要**自己 `apply_diff` 偷修源码——那等于跳过 verifier 自我欺骗。

### 交互模式（默认 macOS）

汇报 fail 列表给用户（一个 fail 一行，附"看哪个日志/根因猜测"），三选一：

> 检测到 N 个 verifier 失败：
>
> - `verify_xxx`：<一句话总结，从 `.guard-transform-*-guard/verify-verify_xxx.log` 末尾几行提取>
> - `verify_yyy`：...
>
> 请选一个继续方式：
>
> 1. **【★ 推荐】先修复再打包**：让 stage 50 LLM autofix 自动修，修完自动续到 stage 60 打新 zip
>    ```bash
>    "$GUARD_TRANSFORM_HOME/transform.sh" "<src>" --from-stage 50 -y
>    ```
> 2. **手动修后再让我重 verify**：你自己改 `<src>-guard/` 下的文件，改完告诉我，我再跑 Step 1
> 3. **强行打包（带伤上线，仅临场调试用）**：明确知道这些 fail 不影响交付时
>    ```bash
>    GUARD_STRICT=0 "$GUARD_TRANSFORM_HOME/transform.sh" "<src>" --from-stage 50 -y
>    ```
>    （会让 stage 50 verifier 仍 fail 时仅 warn 不 die；新 zip 上的 verify 失败项会写进 report.md）
>
> 你选哪个？

**等用户明确回答后再执行**；不要默认替用户做选择。

### 非交互模式（服务端 / CI / openclaw）

**不询问**，直接执行方案 1（最稳的修复路径），并把 fail 列表 + 自动选择的理由写到 stderr 让调用方有迹可循：

```bash
echo "[cowork-skill] 检测到 N 个 verifier fail: verify_xxx, verify_yyy ... 自动选方案 1（LLM autofix）" >&2
"$GUARD_TRANSFORM_HOME/transform.sh" "$PKG_TARGET" --from-stage 50 -y
```

autofix 完成后**再跑一次 Step 1**：

- 全 OK → 进入 Step 3 打包
- 仍有 fail → 在 stdout / stderr 列出**仍未修复**的 verifier 列表，**abort 退出非零**，**不要**自动走方案 3（`GUARD_STRICT=0`）。让调用方决定是否人工介入。

## Step 2B：前端产物过期时（STALE）→ 按运行模式分流

`cowork-package-verify` 通过扫描前端目录的源码 mtime 与构建产物 mtime 来判定 STALE。它会列出：

- 前端目录路径（如 `frontend/` / `web/`，识别规则同 stage 30）
- 最近修改的源文件路径 + mtime
- 最近的构建产物路径 + mtime（`dist/index.html` / `build/index.html` / `.next/BUILD_ID` / `out/index.html` 等任一）
- 源码 vs 产物的时间差

### 交互模式

> 检测到前端产物已过期：
>
> - 前端目录：`frontend/`
> - 最新源码：`frontend/src/App.tsx`（修改于 14:55:03）
> - 当前产物：`frontend/dist/index.html`（生成于 10:32:11，已过期 **4h22m**）
>
> 请选一个继续方式：
>
> 1. **【★ 推荐】重新构建前端再打包**：自动跑 `npm run build`（或对应包管理器），完成后再跑 Step 1
>    ```bash
>    cd "<src>/frontend" && npm run build
>    cd - && "$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" "<src>"
>    ```
> 2. **跳过前端重建（强行用旧产物打包）**：仅在你确定源码改动**不影响**前端运行时
>    ```bash
>    "$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" "<src>" --skip-stale-check
>    ```
> 3. **取消打包**：先去整理前端代码 / 决定是否要构建
>
> 你选哪个？

**等用户明确回答后再执行**。

### 非交互模式（服务端 / CI / openclaw）

**直接 abort 退出非零**——非交互场景**拒绝**带过期产物上线（与"绕过 verifier"同性质）。把诊断打到 stderr：

```
[cowork-skill] [FATAL] 前端产物已过期 4h22m（frontend/src/App.tsx > frontend/dist/index.html）
[cowork-skill] [FATAL] 非交互模式拒绝带过期产物打包。请先在源工程里跑前端 build，再重试。
[cowork-skill] 建议命令：cd <src>/frontend && npm install && npm run build
exit 2
```

> ⚠️ 服务端模式 / openclaw 场景**不要自动**帮用户跑 `npm run build` —— 那相当于在 Pod 内执行未审计的构建脚本（可能 spawn 子进程 / 外发 HTTP / 加载 secret），违反"只校验不运行"的安全边界。让调用方决定是否在更受信的环境里完成构建。

## Step 3：实际打包

`cowork-package-verify` 全 OK（exit=0）或用户明确选择"强行打包"后：

```bash
source "$GUARD_TRANSFORM_HOME/default_env.sh"
"$GUARD_TRANSFORM_HOME/transform.sh" "$PKG_TARGET" --from-stage 60 -y
```

> **机制说明**：`--from-stage 60` 会**自动重置 60+70 stage 的 checklist 状态**，再真正重跑这两个 stage —— 一定会产出**新时间戳的 zip**。早期版本（< 2024-12）`--from-stage` 只控起始迭代点不动 checklist，会出现"命令秒退、没新 zip"的坑，已修复。

打完后按 [`transform.md`](transform.md) "Step 4：解读结果" 走（读 report.md + 给最新 zip 路径 + 必要时复制 output.zip）。

## verifier 速查表（按 stage 50 执行顺序）

| 序号 | verifier | 检查目标 |
| --- | --- | --- |
| 1 | `verify_entry_scripts` | shebang/权限/语法、start.sh 必须 `exec`、health.sh host:port=127.0.0.1:3000 |
| 2 | `verify_health_consistency` | **单向强制 `/health`**：所有应用在端口 3000 暴露 HTTP `/health`；非 `/health` 路径一律 fail；过滤 ping/进程检查等假探活 |
| 3 | `verify_port_3000` | 进程必须 listen 3000 |
| 4 | `verify_app_factory` | Python 工厂函数 `module:create_app` 模式 |
| 5 | `verify_start_artifacts` | Python / Node 启动入口产物存在性 |
| 6 | `verify_frontend_built` | **前端构建产物已落盘**：`dist/index.html` / `build/index.html` / `.next/BUILD_ID` 等任一存在；否则 fail |
| 7 | `verify_startup_log_stream` | **start.sh exec 启动行必须用 shell 级 `2>&1` 收敛 stderr** |
| 8 | `verify_subprocess_lifecycle` | **业务 spawn 子服务的父子进程组底线**：禁止 `detached:true` / `start_new_session=True` 等让子进程脱离父进程组 |
| 9 | `verify_python_requirements` | requirements.txt vs `.py` import + 递归扫所有 `*.sh` 中的 CLI 工具缺口检查 |
| 10 | `verify_venv_activation` | **venv-installed Python CLI 必须在同 `.sh` 内激活 venv 或用绝对路径** |
| 22 | `verify_start_sh_llm` | LLM 综合 review（`GUARD_LLM_VERIFY=1` 启用，read-only 三重保险） |
| ★ | **前端产物时效性**（cowork-package-verify Phase 2） | 源码 mtime > 产物 mtime → STALE |

> `verify_health_consistency` 常见拦截：
> - health.sh 探 `/api/health` / `/healthz` / `/actuator/health`：fail，要求 autofix 改回 `/health`
> - 业务用 `APIRouter(prefix="/api")` + `@router.get("/health")` 实际只暴露 `/api/health`：fail，要求把 `/health` 装饰器移到主 app 顶层

## 易错速查

| 反例 | 正确做法 |
| --- | --- |
| 用户说"再打个 zip" → 直接跑 `--from-stage 60` | ✅ 先跑 `cowork-package-verify`，根据 exit code 决定后续 |
| 前端 verify fail → 自己 `apply_diff` 改 work_dir | ✅ 走 stage 50 LLM autofix，不是 agent 直接动手 |
| 想拦 verify 但走的是 `--from-stage 60 --no-strict` | ✅ `--no-strict` 只在 stage 50 内生效；既然 from-stage=60 就不会跑 verify，必须用 `--from-stage 50` |
| 用户改了 `.tsx` 没 build → `verify_frontend_built` fail → 在 install.sh 加 `npm run build` | ✅ 推荐让用户在 `frontend/` 本地跑 build 再走打包；服务端模式拒绝在 install.sh 内联网构建 |
| verify 全 OK → 仍跑 `--from-stage 50 -y` 走一遍 LLM autofix | ⚠️ 浪费 LLM 配额；verify 全 OK 直接 `--from-stage 60 -y` 即可 |
| 跑 `--from-stage 60 -y` 后没看到新 zip / 命令秒退 | ✅ 已修复——若仍复现请确认用的是当前版本（应在日志里看到 `--from-stage 60 隐含重置 checklist (X 项)`）；旧版本需更新 `~/.claude/skills/cowork-app/` 重装 |

## 命令速查

```
"$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" <源工程路径> [选项]

  --skip-stale-check    跳过前端产物时效性检查（Phase 2），仅做基础验证
  --skip-verify         跳过基础验证（Phase 1），仅做前端产物检查
  --json                输出 JSON 格式结果（机器可读，供 CI 抓）
  -h, --help            帮助

退出码：
  0   全部通过
  1   仅基础验证失败
  2   仅前端产物过期
  3   两者都失败
  4   源工程路径不合法 / 工具调用失败
```
