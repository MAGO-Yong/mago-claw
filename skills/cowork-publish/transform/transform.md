# 子能力 1：项目转写

> 本文档由 [`SKILL.md`](SKILL.md) 的 "入口 1：项目转写" 分发而来。所有命令默认 `$GUARD_TRANSFORM_HOME` 已 export，`$SRC_PROJECT` 已确认是合法源工程绝对路径，`$GUARD_RUN_MODE` 已判定为 `interactive` / `non-interactive`。

## 概览

项目转写 = 把任意外部工程**整体改造**为 CoWork 子应用合规副本，输出可直接交付平台的 zip。底层是 guard-transform 的 8 stage Python 流水线：

```
00_prepare → 10_detect_stack → 20_rewrite_loop → 30_render_scripts
          → 40_build → 50_smoke_test → 60_package → 70_report
```

整个过程通常 **5–30 分钟**，会真实调 LLM 改写源码（移除 Redis/MQ、改写 SSO / AI 调用、生成 install/start/health、自动 build 前端等），产物在 `<src>-guard/`、`<src>-guard-<MMDDhhmm>.zip`、`.guard-transform-<名字>-guard/` 三处。

## Step 1：先跑 detect（强烈推荐）

跑完整流水线前，先**只跑栈识别**让用户/调用方校对。这步不调 LLM、不改文件、约 5 秒：

```bash
"$GUARD_TRANSFORM_HOME/bin/guardx" detect "$SRC_PROJECT"
```

完成后读 `.guard-transform-<名字>-guard/stack.json` + `profile.json`，汇报：

> 识别到的技术栈：
>
> - 语言/框架：`<lang>` / `<framework>`
> - 是否有 DB：`has_db=<bool>`
> - 是否有文本 AI 调用：`has_ai_text=<bool>`（OpenAI / Anthropic / Bedrock 等对话）
> - 是否有图像 AI 调用：`has_ai_image=<bool>`（DALL·E / 万相 / SD / Flux 等生成）
> - 是否有 Redis/MQ：`has_external_infra=<bool>`
> - 匹配到的 profile：`<profile_name>`
>
> （`has_ai` 字段保留向后兼容，`has_ai_text` 或 `has_ai_image` 任一为 1 时它也为 1。）

**按运行模式分流**：

- **交互模式**：追加一句 "是否按这个识别结果继续？"，等用户回答；识别错（如 monorepo 识成单仓）时让用户告知正确栈或挑 profile 强制使用
- **非交互模式（服务端 / CI / openclaw）**：**不询问，直接进入 Step 2/3**。识别明显错时：在 transform.log 写 WARN 后**继续**，让 stage 50 verifier 兜底；只有 `framework: unknown` 且无 fallback profile 时才 abort 退出非零

### Step 1.1：LLM 辅助检测（自动，无需干预）

detect 完成后，stage 10 会**自动**调一次 LLM（fast profile / sonnet）读取源码，生成 `project_brief.md`：

```
.guard-transform-<名字>-guard/
└── project_brief.md    # LLM 生成的项目简述（架构摘要 + 关键文件索引 + 技术栈信号）
```

**两个作用**：

1. **补全 shell 静态扫描漏掉的 flag**：shell 只扫 `package.json` / `requirements.txt` 依赖声明，无法识别通过环境变量 / HTTP 直调 / 配置文件使用的 DB / AI / SSO。LLM 读源码后把补全的 `has_db` / `has_ai_text` / `has_ai_image` / `has_sso` / `has_external_infra` merge 回 `stack.json`（只允许 0→1，不允许 1→0，避免误删已确认信号）。`has_ai_text` / `has_ai_image` 任一被补全为 1 时，`has_ai` 也会联动置 1。

2. **作为后续所有 LLM 调用的上下文前缀**：stage 20/30/40/50 每次调 LLM 时，`_compose_prompt()` 会自动把 `project_brief.md` 拼入 prompt 前缀，让 LLM 不必从头 Glob/Read 全仓，减少 token 消耗、提升改写准确率。

**agent 注意事项**：

- 这步**全自动**，agent 不需要手动触发，也不需要等待用户确认
- 通常 30–60 秒；失败时只 warn 不 die（brief 是增强功能，不影响后续 stage）
- `GUARD_DETECT_LLM=0` 可跳过（`--skip-llm` 时自动跳过）
- 汇报 detect 结果时，可以顺带提一句 "LLM 辅助检测已完成，project_brief.md 已生成"（若 brief 生成成功）

### ⚠️ Step 1.5：用户对识别结果有补充时必须先改 stack.json（agent 强约束）

`stack.json` 是**整条流水线的契约输入**——stage 30 (render_scripts) 根据 `has_db`/`has_sso` 决定是否注入 `db.properties` 和 Decrypted-Userinfo 中间件；stage 50 verifier 根据 `has_db` 决定要不要跑 `verify_db_properties`；stage 20 LLM 改写也会参考这些 flag 决定改写策略。

**因此，如果用户在交互里补充了静态扫描没识别到的特性**，agent 在跑 `transform.sh` 之前**必须先用 `Edit`/`apply_diff` 改写 `<state>/stack.json` 对应字段**，**不能**回答"LLM 阶段会自动分析、detect 只是粗判，不影响"——这是常见幻觉，会导致后续 stage 30/50 用旧 flag 跑出错的脚本。

**用户补充 → 字段映射对照表**：

| 用户说 / 补充 | 必须修改的 stack.json 字段 |
| --- | --- |
| "有 DB" / "用了 SQLite/PG/MySQL" / "我有数据库要迁到 PG" | `"has_db": 1` |
| "有用户身份" / "有 SSO" / "要读 Decrypted-Userinfo header" / "要识别登录态" | `"has_sso": 1` |
| "调了 OpenAI / Anthropic / Claude / 大模型对话" | `"has_ai_text": 1`（同时把 `"has_ai": 1`） |
| "调了 DALL·E / 万相 / Stable Diffusion / Flux / Midjourney 等图像生成" | `"has_ai_image": 1`（同时把 `"has_ai": 1`） |
| "用了 Redis / 缓存 / 消息队列 / Kafka / MQ" | `"has_external_infra": 1`（并按需 `"has_redis": 1` / `"has_mq": 1`） |
| "有 S3 / 对象存储 / OSS / COS" | `"has_external_infra": 1`, `"has_s3": 1` |
| "用了 ES / Elasticsearch / OpenSearch" | `"has_external_infra": 1`, `"has_es": 1` |
| "前端在 xxx 目录" / "后端在 yyy 目录"（monorepo 识别错） | `"backend_dir"` / `"frontend_dir"` 写明确路径 |
| "这其实是 Next.js 不是 vite" 等框架纠错 | `"framework"` 字段改成正确值，必要时 `"lang"` 也改 |

**改完后续跑流水线**（stage 20/30/40/50/60/70 都直接读 `stack.json`，新 flag 立即生效）：

```bash
# 1. 用 Edit/apply_diff 改 .guard-transform-<名字>-guard/stack.json
#    举例：把 "has_db": 0 改成 "has_db": 1；"has_sso": 0 改成 "has_sso": 1
#    需要时同步把 "has_external_infra" / "has_redis" / "has_s3" 等改对
#    （不要改 lang/framework 字段除非用户明确指出框架识别错了）

# 2. 直接跑 transform 续跑：stage 20 起的所有 stage 都会读改后的 stack.json
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" --from-stage 20 -y
#    --from-stage 20 会跳过 stage 10 detect（避免覆盖用户的改动），
#    从 stage 20 (LLM 改写) 开始，让 stage 30 (render) 按新 has_db/has_sso 注入 db.properties 和 SSO 中间件

# 3. （可选）若用户问起 profile.json 为何没更新：
#    profile.json 是给人看的产物，不影响运行（stage 20-70 全部读 stack.json）；
#    想让它跟着更新，可以让 agent 备份后重跑 detect：
#       cp "$STATE_DIR/stack.json" "$STATE_DIR/stack.user.json"
#       "$GUARD_TRANSFORM_HOME/bin/guardx" detect "$SRC_PROJECT"   # 会覆盖 stack.json
#       cp "$STATE_DIR/stack.user.json" "$STATE_DIR/stack.json"    # 用用户改后的版本覆盖回
```

> ⚠️ **agent 回答用户补充时的禁语清单**（这些都是错的）：
>
> - ❌ "detect 阶段只是静态粗判，不影响 LLM 实际改写时的全面分析" —— 错，stage 30/50 硬依赖 stack.json
> - ❌ "LLM 改写阶段会自动检测 DB 并补 db.properties" —— 错，stage 30 是 deterministic 模板渲染，不调 LLM；它只看 has_db flag
> - ❌ "这个补充我记下了，跑完后我们再看" —— 错，stage 30/50 已经跳过 SSO/DB 注入，跑完才发现就晚了
>
> **正确回答模板**：
>
> > 收到补充：✅ 有 DB（SQLite 要迁 PG）、✅ 有用户身份（Decrypted-Userinfo header）。
> >
> > 这两点静态扫描没识别到（项目用的是 mock/注释形式），但 stage 30/50 强依赖 `stack.json`，我先帮你把 `has_db` 和 `has_sso` 都改成 1，再续跑流水线。

**特殊情况**：如果用户**否定**了静态扫描里识别到的特性（如 "我虽然 import 了 redis 但实际没用"），同样要把 `stack.json` 对应字段从 1 改回 0，避免 stage 30 多注入无用配置。

## Step 2：加载默认环境

本 skill 的**默认 LLM 后端**是 `claude` CLI（复用 Claude Code 已有的 OAuth / API key）。`install.sh` 自动写入的 `default_env.sh` 设置了以下默认值，**source 一次即可**：

```bash
source "$GUARD_TRANSFORM_HOME/default_env.sh"
# 终端会回显（可被 GUARD_QUIET=1 静默）：
#   [cowork-skill] LLM 后端: claude / 超时: 1800s / 心跳: 60s / profile: local（可覆盖）
#   [cowork-skill] 覆盖方法: export GUARD_PROFILE=server 或 GUARD_LLM=... 或编辑 default_env.sh
```

### 服务端模式一键预设（GUARD_PROFILE=server）⭐ openclaw 强烈推荐

为了减少 openclaw / CI 调起本 skill 时的环境变量负担，**只要 export 一个变量** `GUARD_PROFILE=server`，就会一键展开所有服务端推荐值：

```bash
export GUARD_PROFILE=server                           # 一行替代多行 export
source "$GUARD_TRANSFORM_HOME/default_env.sh"         # 自动展开
```

展开后等价于：

| 变量 | 服务端预设值 | 含义 |
| --- | --- | --- |
| `GUARD_NONINTERACTIVE` | `1` | 强制非交互模式（不读 stdin） |
| `GUARD_LLM_VERIFY` | `1` | stage 50 启用 LLM 综合 review，捕捉规则 verifier 抓不到的问题 |
| `GUARD_SMOKE_FULL` | `0` | ⚠️ 服务端**安全红线**：禁止 verify_runtime_full 真启动业务进程（凭据外泄 / RCE / SSRF 风险） |
| `GUARD_SMOKE_ALLOW_INFRA_MISS` | `0` | 同上，服务端不放行 infra-miss 降级 |
| `GUARD_LLM_TIMEOUT` | `1800` | 单次 LLM 调用 30 分钟超时 |
| `GUARD_LLM_HEARTBEAT` | `60` | 1 分钟一次心跳 |

> **预设原则**：所有变量都用 `${VAR:=default}` 语义；任何在 source 前已经 export 的同名变量**始终优先**，不会被覆盖。所以你随时可以这么做：
>
> ```bash
> export GUARD_PROFILE=server                              # 一键预设
> export GUARD_LLM=codewiz                                 # 单独覆盖 LLM 后端
> export GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)' # 单独覆盖模型
> source "$GUARD_TRANSFORM_HOME/default_env.sh"
> ```

### 其它四种覆盖姿势（仅当用户明确要求）

**方式 0：用户在 macOS 终端跑一次 `choose-model.sh`（永久换默认，最推荐）**

```bash
# 入口 1：transform.sh 透传 flag
"$GUARD_TRANSFORM_HOME/transform.sh" --choose-model

# 入口 2：直接调脚本
"$GUARD_TRANSFORM_HOME/choose-model.sh"           # 3 阶段菜单：backend → STRONG → FAST
"$GUARD_TRANSFORM_HOME/choose-model.sh" --show    # 查当前默认
"$GUARD_TRANSFORM_HOME/choose-model.sh" --reset   # 恢复 build.sh 写入的初始默认 + marker:initial
```

写回后**所有后续 transform** 都用新默认，agent 不需要每次都改 / 都问。zip 解压后初始 `STRONG=claude-4.6-sonnet-google` / `FAST=claude-4.6-sonnet-google`（seal skill 硬需求：STRONG/FAST 都默认 sonnet 非 thinking）。

> **首次跑自动调起**：zip 解压后 `default_env.sh` 末尾写有 `# CHOOSE_MODEL_MARKER:initial`。首次跑 `transform.sh` 在 interactive 模式 + 交互终端会先弹 `是否现在调起 choose-model.sh 选模型？[Y/n/skip]`；选完后 marker 改成 `:chosen`，之后不再询问。CI / Seal 云端 `export GUARD_SKIP_CHOOSE_MODEL=1` 永久跳过。

**方式 1：临时覆盖单次调用** — 先 export，再 source（`${VAR:=default}` 会保留你的值）：

```bash
# 切到 codewiz 后端 + opus(thinking) 跑难度极高的语义重构
export GUARD_LLM=codewiz
export GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)'
source "$GUARD_TRANSFORM_HOME/default_env.sh"
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT"
```

| 用户口头要求 | 对应 export |
| --- | --- |
| "用最强的 / 用 opus" | `export GUARD_LLM=codewiz; export GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)'` |
| "用快的 / 用便宜的" | `export GUARD_LLM=codewiz; export GUARD_LLM_MODEL='codewiz/Claude-4.6-sonnet'` |
| "用 haiku / 简单任务" | `export GUARD_LLM=codewiz; export GUARD_LLM_MODEL='codewiz/Claude-4.5-haiku'` |
| "用 qwen / 不用 claude" | `export GUARD_LLM=qwen-code` |

> ⚠️ 模型名带 `()` / `/`，**必须单引号包裹**，否则 zsh 报错。

**方式 2：永久覆盖默认值** — 直接编辑 `$GUARD_TRANSFORM_HOME/default_env.sh`，把 `${GUARD_LLM:=claude}` 冒号后面的 default 改成你想要的；下次 source 即生效。`install.sh --force` 不会覆盖（除非重装）。

**方式 3：完全跳过 source** — 自己手工 export 全套，不走 `default_env.sh`：

```bash
export GUARD_LLM=qwen-code GUARD_LLM_TIMEOUT=1800
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT"
```

### agent 行为约定（重要）

- **不要**用 `ask_followup_question` 问用户"用哪个模型 / 是否 source"——任何询问在 openclaw / 自动化场景会 hang 住流水线
- 默认值就是合适的，**不要替用户切模型**；用户没明确说"换"就直接用默认跑
- 服务端场景**永远先 `export GUARD_PROFILE=server`**，其它复杂 export 都能省

## Step 3：跑完整 transform

按运行模式分流：

```bash
# PYTHONUNBUFFERED=1：禁止 Python 缓冲输出，确保 guardx 日志实时流向 claude bash 工具
# 2>&1：合并 stderr → stdout，让 claude 的 bash 工具捕获所有日志并通过 stream-json 输出
export PYTHONUNBUFFERED=1

if [ "$GUARD_RUN_MODE" = "non-interactive" ]; then
    # 服务端 / CI / openclaw：强制 -y，禁止 transform.sh 内部询问 / 等 stdin
    "$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" -y 2>&1
else
    # 桌面交互：默认即可
    "$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" 2>&1
fi
```

**重要**：

- 上一步已 source `default_env.sh`，已设置默认 `GUARD_LLM=claude` + 默认超时/心跳，无需在命令前再写一遍
- 流水线启动时 `guardx` 会再次 banner 打印当前生效的 LLM 后端 / 超时 / 心跳，方便核对
- 这条命令通常 **5–30 分钟**，会实时打日志到终端 + 写文件
- 不要打断它；CTRL+C 会被 `process.py` 干净拦截，下次 `--resume` 可续跑
- 跑的过程中**不要**主动调 LLM、不要试图"加速"
- **非交互模式必须带 `-y`**：transform.sh 在已存在 checklist 时默认走 `ask` 流程读 stdin，无 tty 会卡死

### 工作副本目录（`<src>-guard`）已存在时

第一次跑会把源工程 copy 到 `<src>-guard/` 作为"工作副本"，后续所有改写都发生在副本上、不污染源码。**第二次及以后**再跑同一个源工程时，副本目录已经存在，需要决定怎么处理它：

- 你在 `<src>-guard/` 里**已有手改**（如调过 profile.json / 改过 install.sh / 加了 patch 文件），想保留这些改动继续跑 → 用 `--reuse-copy`
- 想丢弃副本里所有改动、从源工程**重新 copy 一份干净的**开始 → 用 `--recopy`
- 不传 flag：
  - **交互终端（tty）**：弹出选单让用户选 `1=使用现有 / 2=清空重 copy / q=退出`，30 秒无输入按 `1` 默认走 reuse
  - **非交互（CI / openclaw / `-y` / `GUARD_NONINTERACTIVE=1`）**：静默走 reuse，并打 `[fresh-copy] 非交互环境，自动选择「使用现有副本」` 日志

```bash
# 显式保留副本中已有的改动
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" --reuse-copy

# 强制清空副本、重新从源工程 copy
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" --recopy

# 也可用环境变量（适合 CI 矩阵）：
GUARD_FRESH_COPY_MODE=recopy "$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" -y
```

> 优先级：**CLI flag (`--reuse-copy` / `--recopy`) > `GUARD_FRESH_COPY_MODE` env > `-y/GUARD_NONINTERACTIVE` 暗示 `reuse` > 交互终端弹问 > 默认 `reuse`**。
>
> `--reuse-copy` / `--recopy` 与 `--resume` / `--reset` 互补：前者管"物理副本是否要清空 + 重新 copy"，后者管 "stage checklist 进度文件是否要清空"。一般组合：`--reuse-copy --resume`（继续上次跑到一半的流水线）/ `--recopy --reset`（彻底从头来）。

## Step 4：解读结果

跑完后产物在 3 个位置：

```
<源工程>-guard/                              # 工作副本（已改写 + 已 build）
<源工程>-guard-<MMDDhhmm>.zip                # ★ 交付给 CoWork 平台的 zip（带本次打包时间戳）
.guard-transform-<源工程>-guard/             # 过程产物
└── report.md                                # 必读：完整 checklist + AI/SSO 覆盖范围声明
```

> zip 文件名带 `MMDDhhmm` 时间戳后缀（如 `mm-app-guard-05141604.zip`），每次跑都会产出新文件，**不会覆盖**上次产物，方便对比 / 回滚 / 提交多版本到平台做 A/B 验证。完整路径在 stage 70 报告 `report.md` 顶部 + cli 流水线结束 banner 里同时给出，**以 banner 为准**。
>
> 如需固化文件名（CI 流水线对接外部存储）：`export GUARD_ZIP_TIMESTAMP=12251200` 后再跑 transform。

**必须做的事**：

1. 用 `read_file` 读 `.guard-transform-<名字>-guard/report.md` 全文
2. 把 report 摘要给用户，重点：
   - 8 个 stage 的状态（ok / fail / skip）
   - AI 模型覆盖范围声明（哪些迁移到 Runway / 哪些保留原 SDK）
   - 是否有"已知带伤"的 stage（`GUARD_STRICT=0` 时可能有 warn）
3. 用 `list_files` 确认 zip 已生成（注意带时间戳后缀，按 mtime 取最新）
4. **若被 openclaw 调用**：把产出 zip 复制为 `$PWD/output.zip`（固定名，供 openclaw pipeline 消费）：

```bash
# 从 banner 或 GUARD_OUTPUT_ZIP 环境变量拿到实际 zip 路径，复制为固定名
cp "$GUARD_OUTPUT_ZIP" "$PWD/output.zip"
```

> `$GUARD_OUTPUT_ZIP` 由 guardx 流水线结束时写入；若未设置，用 `ls -t "$SRC_PROJECT"*-guard-*.zip 2>/dev/null | head -1` 拿最新。
> 若 cp 失败（zip 不存在），**立即 abort 退出非零**，不要给 openclaw 一个空的 output.zip。

### ⚠️ Step 4.5：上下文切换（交互模式必做、非交互静默生效）

转写完成后**所有后续修改/重打包/再 verify 都必须发生在 `<源工程>-guard/` 副本里**，不能再回去改原工程。原因：

- 副本是改写后的合规版本（已移除 Redis/MQ、改完 SSO/AI 调用、注入 install/start/health、build 完前端产物）
- 改原工程不会影响最终 zip（除非用户主动 `--recopy` 重跑完整 8 stage 流水线，重新把原工程 copy 进副本——这通常不是用户想要的）
- 改原工程还会被下一次 `--reuse-copy` 跳过，造成"我明明改了为啥还是老问题"的困惑

**agent 必须做的事（无论交互/非交互模式）**：

1. **关键语义分离**——`$SRC_PROJECT` 始终保持指向**原源工程**（命令族传参用），但 agent 后续读写文件**全部**改用 `$GUARD_WORK_DIR`（副本路径）：
   ```bash
   # $SRC_PROJECT 不动！它是 transform.sh / bin/guardx / cowork-package-verify 的入参
   # （这些命令内部自己会推导出 <src>-guard 作为 work_dir）
   GUARD_WORK_DIR="${SRC_PROJECT}-guard"
   [ -d "$GUARD_WORK_DIR" ] || { echo "[FAIL] 副本目录 $GUARD_WORK_DIR 不存在，转写产物缺失" >&2; exit 1; }
   export GUARD_ACTIVE_DIR="$GUARD_WORK_DIR"
   ```

2. **明确告诉用户**已切换（着重提示，不要藏在脚注里）：

   > ✅ 转写完成。**已自动把后续修改的上下文从源工程 `<src>` 切换到副本 `<src>-guard/`**。
   >
   > 这意味着：
   > - 你接下来说"再改一下 xxx 文件"，我会改 `<src>-guard/xxx`，而非源工程的同名文件
   > - 你说"再打个 zip"，我会基于 `<src>-guard/` 现状重打，不会重跑 LLM 改写流水线
   > - 你说"再 verify 一下"，我会跑 `bin/guardx verify <src>`，verifier 也是读 `<src>-guard/` 的内容
   >
   > 如果你确实想**改回原工程后重新走完整转写流水线**，明确说"切回源工程上下文"或"用原工程重跑"，我会把 agent 改文件的目标切回 `<src>` 并提示你需要 `--recopy` 重跑。

3. **后续会话路径解析规则**（agent 自我约束）：

   | 用户说的话 | agent 解析为 |
   | --- | --- |
   | "改一下 config.py" | 用 `Read`/`Edit` 改 `$GUARD_WORK_DIR/config.py`（原 `$SRC_PROJECT/config.py` 不动） |
   | "看下 start.sh / install.sh / health.sh" | `Read $GUARD_WORK_DIR/start.sh` 等（这些是 stage 30 模板渲染出来的，源工程里压根没有） |
   | "再打个 zip" / "重新打包" | 走 [`package.md`](package.md) Step 0 入口：`cowork-package-verify "$SRC_PROJECT"` + `transform.sh "$SRC_PROJECT" --from-stage 60 -y`<br>⚠️ 命令入参始终用**源工程路径** `$SRC_PROJECT`，命令内部自动找 `${SRC_PROJECT}-guard/` 副本做 verify/打包；**不要**把副本路径传进去（会被推导成 `<src>-guard-guard/` 崩溃）。stage 00 默认 `--reuse-copy` 模式复用现有副本，不会重 copy 覆盖你的改动 |
   | "再 verify" | `bin/guardx verify "$SRC_PROJECT"`（同上，入参用源工程路径，内部对副本做 verify） |
   | "切回源工程上下文" / "用原工程重跑" | 把 agent 改文件的目标切回 `$SRC_PROJECT`；告诉用户"后续改动会落在源工程，下次 transform 时若不加 `--recopy`，副本里的旧改动仍会保留；若加 `--recopy --reset` 则副本被源工程覆盖、checklist 重置从头跑" |
   | "丢弃副本改动重新转写" | `transform.sh "$SRC_PROJECT" --recopy --reset -y` |

4. **若 transform 失败导致没有有效副本**：跳过本节，继续走原 `$SRC_PROJECT` 的失败 routing（Step 5）。

> **为什么要"默认强制切换"而非"问用户选"**：用户反馈过实际场景里 agent 经常改错了文件——改原工程导致下一次 `--reuse-copy` 跳过新改动、改原工程导致 zip 里没生效。默认切换 + 着重提示是更安全的策略；想保留旧行为的用户可以主动说"切回源工程"。

## Step 5：失败时的 routing（不要自己瞎修）

如果命令 `exit 1`：

1. 读 `.guard-transform-<名字>-guard/transform.log` 末尾 200 行确认失败 stage
2. 按下表 routing（详见 [`troubleshooting.md`](troubleshooting.md)）：

| 失败 stage | 看哪个文件 | 典型修法 |
| --- | --- | --- |
| 20 LLM 没改对 | `_retry-*.md` + `llm-*.log` | 调高 `--autofix-max` 重试 / 切到 codewiz opus 模型 |
| 30 模板渲染缺端口 | `<work>/start.sh` + `verify-verify_port_3000.log` | 检查 profile.json 是否正确 |
| 40 build 失败 | `<work>` 手动 `npm install && npm run build` | 通常是依赖问题，autofix 已尝试 |
| 50 烟测失败 | `verify-*.log` 全集 | `cd <work>; bash $GUARD_TRANSFORM_HOME/verifiers/verify_xxx.sh .` 复现 |
| claude CLI 鉴权超时 | `.guard-transform-*/llm-*.log` | 让用户跑 `claude login` 重新登录 |

### 交互模式（默认）

> Stage `<NN>` 失败了。我已经看了 `<具体日志文件>`，失败原因看起来是 `<一句话总结>`。
>
> 推荐下一步（任选）：
>
> 1. 修完根因后续跑：`$GUARD_TRANSFORM_HOME/transform.sh <src> --resume`
> 2. 跳过这个 stage 看后面能不能走通：`--from-stage <NN+10>`（仅调试用）
> 3. 关 autofix 直接看原始失败：`--no-autofix`
>
> 想我做哪个？

### 非交互模式（服务端 / CI）— **不要询问用户，按下面优先级自动执行**

为防止 autofix 死循环，agent 应在 `.guard-transform-<名字>-guard/_skill_retry_count` 里记录"同一 stage 已自动重试次数"（初始 0，每次 +1）：

| 当前重试次数 | 自动选择的修法 | 命令 |
| --- | --- | --- |
| 第 1 次失败 | 走 autofix 默认通路 + 加大 retry | `"$GUARD_TRANSFORM_HOME/transform.sh" "<src>" --resume --autofix-max 20` |
| 第 2 次同 stage 仍失败 | 同模型再 resume 一次（**不切后端、不换模型**） | `"$GUARD_TRANSFORM_HOME/transform.sh" "<src>" --resume --autofix-max 20` |
| 第 3 次仍失败 | **abort 退出非零** | 输出 `transform.log` 末尾 200 行 + 失败 stage 名 + 失败 verifier 列表，**不要**再自动重试，**不要**自动加 `--no-strict` |

> ⚠️ **claude skill 的硬性约束**：自动重试**始终保持** `GUARD_LLM=claude`，让 claude CLI 自己决定底层模型版本（4.6 / 4.7 / opus / sonnet 都跟随用户当前 claude CLI 配置）。**不要**为了"提高成功率"在 retry 时偷偷切后端 / 升降级模型——切了等于跑了一份完全不同的产物。

**特殊情况立即 abort（不进入重试）**：

| 情况 | 立即处理 |
| --- | --- |
| `claude` / `codewiz` CLI 鉴权 401 / token 过期 | abort + 提示"请在 CI 环境配置好 LLM CLI 鉴权" |
| 源工程 / 路径不存在 / 不可读 | abort，原样回 stderr |
| 磁盘满 / 权限不足 | abort，让运维/CI 介入 |
| `framework: unknown` 且无 fallback profile | abort，让调用方提供正确栈 |

**最终成功后的机器可读输出**（让 CI 抓）：

```
GUARD_OUTPUT_ZIP=<absolute path to .zip>
GUARD_OUTPUT_REPORT=<absolute path to report.md>
```

把这两行**单独**打到 stdout 末尾（除了正常报告外）。

## 高级场景

### 续跑 / 中断恢复

每次跑会把进度持久化到 `.guard-transform-<名字>-guard/checklist.tsv`。再次执行同一源工程时按 `RESUME_MODE` 决定：

| 用户意图 | 命令 |
| --- | --- |
| 继续上次（跳过已完成步骤） | `--resume` 或 `-y` |
| 全部从头来 | `--reset` |
| 让工具问我 | 不传参（默认 `ask`，非交互场景默认 continue） |
| 只重跑某个 stage 之后 | `--from-stage NN` |

CI / 流水线场景默认带 `-y`。

### 自检流水线（不真调 LLM）

```bash
GUARD_LLM=mock SKIP_LLM=1 "$GUARD_TRANSFORM_HOME/transform.sh" <合法样本路径>
# 或：
"$GUARD_TRANSFORM_HOME/transform.sh" <src> --skip-llm
```

### 单独跑 verifier 集合

用户已经手改过 `<work>` 副本，只想验证合规性：

```bash
"$GUARD_TRANSFORM_HOME/bin/guardx" verify "$SRC_PROJECT"
```

跑全部 shell 验证脚本，输出 ok / fail 列表，**不调 LLM、不改文件**。完整 verifier 一览见 [`package.md`](package.md) "verifier 速查表"。

### 清理状态目录

调试时反复试错，磁盘占用大：

```bash
"$GUARD_TRANSFORM_HOME/bin/guardx" clean "$SRC_PROJECT" -y
```

会删 `<work_dir>` + `<state_dir>`。

## 通用「不要做」

- ❌ 不要自己 `Edit`/`apply_diff` 去改 `<work>` 副本里 LLM 已经改写的源码——改完不跑 verifier 等于没改（注意：转写完成后用户主动要求改 `<work>` 副本里的脚本/配置文件是允许的，见 Step 4.5）
- ❌ 不要为了"看起来成功"加 `GUARD_STRICT=0` ——那只是降级 die 为 warn，问题还在
- ❌ 非交互模式下**不要**自动加 `--no-strict` / `--skip-llm` / `GUARD_STRICT=0` 这些"绕过开关"
- ❌ **detect 后用户补充技术栈信息时**，不要回答"LLM 阶段会自动处理 / detect 只是粗判 / 不影响"——详见 Step 1.5，stage 30/50 强依赖 `stack.json` flag，**必须先 Edit 改 stack.json 再续跑**
- ❌ 转写完成后**不要**继续把用户的"再改一下 xxx"指令解析到原工程路径——详见 Step 4.5，必须切到 `<src>-guard/` 副本（默认强制切换，用户主动说"切回源工程"才退回）

## 完整命令参数速查

```
"$GUARD_TRANSFORM_HOME/transform.sh" <源工程路径|zip 文件> [选项]

  --from-stage NN     从指定 stage 续跑（00/10/20/30/40/50/60/70）
  --skip-llm          跳过所有 LLM 调用（同 SKIP_LLM=1）
  --resume            续跑：自动跳过已完成步骤，不询问
  --reset             重置：清空 checklist 重新开始，不询问
  -y, --yes           同 --resume（兼容 CI / 非交互场景）
  --no-autofix        关闭 verifier 失败时的 LLM 自愈
  --autofix-max N     每个 verifier 最多 LLM 修复次数，默认 10
  --no-strict         verifier autofix 仍失败时不 die，带伤继续到 60_package
  -h, --help          帮助

环境变量（命令行参数优先；未传时自动用环境变量兜底）：
  GUARD_PROFILE       ⭐ 一键预设。可选值：local（默认）/ server（服务端）
                      server 会一键展开为 NONINTERACTIVE=1 + LLM_VERIFY=1 +
                      SMOKE_FULL=0 + LLM_TIMEOUT=1800 + LLM_HEARTBEAT=60
                      已 export 的同名变量优先
  GUARD_LLM           后端: claude / codewiz / qwen-code / codex / gemini / mock
  GUARD_LLM_MODEL     仅 codewiz 生效，model 标识，如 'codewiz/Claude-4.6-sonnet(thinking)'
  GUARD_LLM_TIMEOUT   单次 LLM 调用超时秒数，默认 600s（seal skill 默认 1800s；0=不超时）
  GUARD_LLM_HEARTBEAT 心跳间隔秒数，默认 30s（seal skill 默认 60s）
  SKIP_LLM=1          跳过 LLM
  GUARD_AUTOFIX=0     关闭 verifier 失败的 LLM 自愈
  GUARD_AUTOFIX_MAX   每个 verifier 最多 autofix 次数（默认 10）
  GUARD_STRICT=0      stage 50 verifier 仍失败时仅 warn 不 die（带伤继续，仅调试用）
  GUARD_SMOKE_FULL=1  stage 50 启用 verify_runtime_full 完整链烟测：
                       install.sh + start.sh + health.sh + asset 200/MIME 全套
                       默认按 GUARD_RUN_MODE：interactive=自动开 / 其它=自动 skip
                       ☁️ 云端转写：⚠️ 必须保持 0 或 unset（GUARD_PROFILE=server 自动归 0）。
                                  Pod 内真启动 = 执行未经审计的业务代码，
                                  凭据外泄 / RCE / SSRF / 资源耗尽风险
                       💻 本地转写：推荐开启（受信环境，1-5min 端到端验证）
  GUARD_LLM_VERIFY=1  stage 50 启用 verify_start_sh_llm.sh LLM 综合 review（默认 skip）
                       ☁️ 云端转写：⭐推荐开启（GUARD_PROFILE=server 自动设为 1）
                       💻 本地转写：推荐开启
                       read-only：git stash 锁基线 + 跑后 checkout 撤销 LLM 任何意外改动
  GUARD_SMOKE_ALLOW_INFRA_MISS=1
                       仅本地：health.sh 30s 未通过时，若 start/health 日志命中 PG/ROS/COS 等
                       外部依赖缺失关键词，降级 [OK-WARN] exit 0；install + start 仍严格
                       ⚠️ 只放行 Phase 3 health；Phase 4 asset 仍严格；云端禁开
  GUARD_SMOKE_EXTRA_INFRA_MISS_PATTERNS
                       追加用户自定义 infra-miss 关键词（egrep 语法 | 分隔），如
                       'TimeoutError.*kafka|mongo.*ENOTFOUND'，仅在 ALLOW_INFRA_MISS=1 生效
  GUARD_DETECT_LLM    stage 10 detect 后是否调 LLM 生成 project_brief.md（默认 1=开启）
                       0=跳过（--skip-llm 时自动跳过）；brief 生成失败时只 warn 不 die
  GUARD_DETECT_TIMEOUT stage 10 LLM 辅助扫描专属超时秒数（默认 max(GUARD_LLM_TIMEOUT,1800)）
                       读全仓远比单文件改写慢，默认至少 1800s；显式设置后优先级最高
```
