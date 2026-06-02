---
name: ai-demo-platform-guard-transform-skill-seal
description: 把任意工程转写为符合 CoWork 平台子应用规范，并完成「打包」部署前置任务。两大子能力：(1) 项目转写：把现有 React / Next.js / Vite SPA / Vue / FastAPI / Flask / Koa / Express 等单仓或 monorepo 工程改造成 CoWork 子应用，生成 install.sh / start.sh / health.sh、移除 Redis / MQ / S3 / ES 等外部基础设施、把文件存储迁到 PostgreSQL Large Object、把 OpenAI / Anthropic SDK 改写成 Runway Bedrock 协议、把 SSO 改成 Decrypted-Userinfo header 模式；(2) 项目打包：用 shell 验证器校验 start/install/health 合规性、前后端分离场景检测前端构建产物是否过期、打成可直接交付平台的 zip。触发关键词：cowork / co-work / cowork 子应用 / cowork subapp / cowork 转写 / cowork 改造 / cowork 构建 / cowork 打包 / cowork 平台 / cowork zip / cowork 部署 / 部署到 cowork / 转写成 cowork / 改造成 cowork / convert to cowork subapp / package as cowork zip / cowork app / cowork 应用 / 子应用规范。
---

# cowork-app 技能（Seal IDE 版）

> 本版本专为小红书 Seal IDE 设计：
> - **部署模式**：zip 上传（开发者本地跑 `bash skills/seal/build.sh` 产出 `dist/cowork-app-*.zip`，在 Seal IDE 里上传），**不再走 install.sh 写本地目录**
> - **默认 LLM 后端** = `seal`（内部 CLI 名 `codewiz-cc`，是 Claude Code 的 fork，参数完全兼容）
> - **默认模型**：STRONG / FAST 均默认 `claude-4.6-sonnet-google` 非 thinking（保持分级机制但默认值对齐，省钱省时）
> - **seal 后端实际可用模型仅两个**：`claude-4.6-sonnet-google`（Sonnet 4.6，速度快）/ `claude-4.5-haiku-google`（Haiku 4.5，轻量快）。其它 anthropic 原生 id（claude-opus-4-6 等）在 seal 后端下跑不起来；如需用更强模型请切到非 seal 后端，详见 [`scripts/choose-model.sh`](scripts/choose-model.sh)
> - **目录结构**（zip 解压后）：`SKILL.md` / `reference.md` / `examples.md` / 子能力 `*.md` 在顶层；`scripts/` 下是整个 guard-transform 工具（transform.sh / bin/ / guardx/ / profiles/ / prompts/ / templates/ / verifiers/）

本 skill 现在覆盖 CoWork 子应用部署的**两大子能力**，按用户意图分发到对应子流程：

| # | 子能力 | 何时触发 | 详细文档 |
|---|---|---|---|
| 1 | **项目转写** | "改成 / 转写成 cowork 子应用"、"按 cowork 规范跑一遍" | [`transform.md`](transform.md) |
| 2 | **项目打包** | "打个 cowork zip"、"再打包一次"、"重新打包"、用户手改完 `<src>-guard/` 后想再生成 zip | [`package.md`](package.md) |

完整索引见 [`reference.md`](reference.md)；典型对话示例见 [`examples.md`](examples.md)。

如果用户的请求**同时**涉及多项（例如"改成 cowork 子应用并打包"），按顺序串行执行：**先 1 转写 → 再 2 打包**。两者天然有依赖关系，不要并发跑。

## 何时使用此技能

**自动触发**（说出下列任一意图）：

- 涉及转写："把这个工程改成 / 转成 / 转写成 CoWork 子应用"、"按 CoWork 子应用规范跑一遍"、"convert this project to a cowork subapp"
- 涉及打包："打个 cowork zip"、"重新打包"、"再打个 zip"、"打包 / 改造成 CoWork subapp zip"
- 涉及流水线整体："迁移 / 部署到 CoWork 平台"、用户明确提到 `transform.sh` / `guardx` / 想跑 8 个 stage 流水线

**部署/打包触发**（开发者想构建一份新的 skill zip 时）：

- "打个 cowork-app skill zip" / "构建 seal skill 包" / "build the seal skill"
- "更新 cowork-app skill"（解读为重新构建并上传）

→ 直接在 [`ai-demo-platform-guard-transform-skill/skills/seal/`](.) 下执行 `bash build.sh`，产出 `dist/cowork-app-<ts>.zip`，再让用户在 Seal IDE 里上传。详见下方 [构建与部署](#构建与部署zip-上传模式)。

> **注意**：终端用户在 Seal IDE 里用本 skill 时**不会**说"安装 skill"——他们只会说"改造工程 / 打包"。"安装"对终端用户透明（已经在云端预装好或一次性 zip 上传完）。

**不要使用本技能的情形**：

- 用户只想了解 CoWork 子应用规范是什么 → 直接读规范文档解释，不要跑流程
- 用户已经有改写好的工程、**只想验证合规性** → 直接 `$GUARD_TRANSFORM_HOME/bin/guardx verify <src>`，不需要走完整流水线
- 用户在调试 transform 工具自身的代码 → 你是开发者助手，按常规代码任务做
- 不确定的时候，**先问用户一句**："你是想（1）整工程改写成 cowork 子应用，还是（2）只重新打个 zip？"

## 构建与部署（zip 上传模式）

> 本节面向**开发者**（构建 zip 并上传到 Seal IDE 的人）；终端用户在 Seal IDE 里使用时不需要关心。

### 构建步骤

```bash
# 1. 进入 skills/seal 目录
cd "<path>/ai-demo-platform-guard-transform-skill/skills/seal"

# 2. 跑构建脚本（产出 dist/cowork-app-<timestamp>.zip + dist/cowork-app-latest.zip 软链）
bash build.sh

# 3. 自定义输出位置（可选）
bash build.sh --output ~/Desktop
bash build.sh --name cowork-app --output ./build
```

构建产物是一个**完全自包含**的 zip，内部结构（解压后）：

```
cowork-app/
├── SKILL.md            （必需 —— Seal 启动时加载的主入口）
├── reference.md        （详细参考索引；按需加载）
├── examples.md         （使用示例；按需加载）
├── transform.md        （子能力 1 详细流程）
├── package.md          （子能力 2 详细流程）
├── troubleshooting.md  （失败诊断速查）
├── BUILD_INFO.txt      （构建时间 / git head，便于调试）
└── scripts/            （会被【执行】而不是被【加载】的工具）
    ├── transform.sh           （8 stage 流水线入口）
    ├── default_env.sh         （默认 GUARD_LLM=seal / sonnet 非 thinking）
    ├── choose-model.sh        （交互式换模型；仅 macOS）
    ├── .guard_transform_home  （绑定文件 = "auto"，运行时由 default_env.sh 推导）
    ├── detect_rules.json      （技术栈识别规则）
    ├── README.md              （工具自身文档）
    ├── bin/                   （cowork-package-verify / cowork-login-check / guardx）
    ├── guardx/                （Python 包：8 stage 流水线实现）
    ├── profiles/              （框架 profile）
    ├── prompts/               （LLM 提示词模板）
    ├── templates/             （install.sh / start.sh / health.sh / server.cjs 模板）
    └── verifiers/             （shell 校验器）
```

### 上传到 Seal IDE

1. 打开 Seal IDE 的 **Skill 管理面板**（或对应的 zip 上传入口）
2. 选择 `dist/cowork-app-latest.zip` 上传
3. Seal 自动解压并把 `cowork-app/SKILL.md` 作为入口加载
4. 在任意工程目录里说"把这个工程改成 CoWork 子应用 / 打个 cowork zip"即可触发

### 升级（重新构建并重传）

```bash
cd "<path>/ai-demo-platform-guard-transform-skill"
git pull
cd skills/seal && bash build.sh
# 再把新的 dist/cowork-app-latest.zip 在 Seal IDE 里上传覆盖
```

> **开发者约束**：如果你在**本次构建会话**里又被要求"立刻试一下 skill / 用它转写一个工程"，**不要直接在本会话动手**——因为本会话上下文已经被 skill 源码污染（刚读过 SKILL.md / transform.md / build.sh），容易把"改 skill 源码"当成任务。正确做法：先 `ask_followup_question` 提醒用户"skill 已构建/上传完毕，请新开一个 Seal 会话再触发 skill 转写你的目标工程"。

## 运行模式判定（交互 vs 非交互）⚠️ 必读

两大子能力**共用同一套**运行模式判定。执行任何子流程前**必须**先跑下面这段，决定后续是否要询问用户：

> **核心策略**：**默认 non-interactive**（不询问、按推荐方案自动执行），只有命中下列任一才切到 interactive：
>
> 1. 用户显式 `export GUARD_INTERACTIVE=1`
> 2. 操作系统是 macOS（`uname -s` = `Darwin`）
>
> 设计理由：
>
> - 服务端 / Linux 容器 / CI / openclaw / 远程 ssh 占绝大多数生产场景，非交互更安全（不会读 stdin 卡死）
> - macOS 桌面通常是开发者本机，交互能让用户校对识别结果、做关键决策
> - 用户随时可用 `GUARD_NONINTERACTIVE=1` / `GUARD_INTERACTIVE=1` 显式覆盖

### 自动判定（一次性跑下面这段，按命中即定）

```bash
# 用户显式覆盖优先级最高（GUARD_NONINTERACTIVE 优先，更安全）
if [ "${GUARD_NONINTERACTIVE:-0}" = "1" ]; then
    GUARD_RUN_MODE=non-interactive
elif [ "${GUARD_INTERACTIVE:-0}" = "1" ]; then
    GUARD_RUN_MODE=interactive
# 默认：仅 macOS 桌面才 interactive，其余（Linux / WSL / 容器 / CI / 远程 ssh）一律 non-interactive
elif [ "$(uname -s)" = "Darwin" ]; then
    GUARD_RUN_MODE=interactive
else
    GUARD_RUN_MODE=non-interactive
fi
export GUARD_RUN_MODE
echo "[cowork-skill] 运行模式: $GUARD_RUN_MODE  (uname=$(uname -s), GUARD_INTERACTIVE=${GUARD_INTERACTIVE:-0}, GUARD_NONINTERACTIVE=${GUARD_NONINTERACTIVE:-0})"
```

> **简单口诀**：macOS 默认交互；其它一切默认不交互。

### 服务端模式预设（一行替代一堆 export）

为了**精简 openclaw 等服务端场景的环境变量配置**，本 skill 提供 `GUARD_PROFILE=server` 一键预设。在 source `default_env.sh` 前 export 这一个变量，等价于一次性 export 下面这套服务端推荐值：

```bash
export GUARD_PROFILE=server   # 一键展开为以下所有值（除非你预先 export 同名变量覆盖）
# 等价于：
#   GUARD_NONINTERACTIVE=1
#   GUARD_LLM_VERIFY=1                       # 启用 stage 50 LLM 综合 review
#   GUARD_SMOKE_FULL=0                       # ⚠️ 安全红线：服务端禁开真启动烟测
#   GUARD_SMOKE_ALLOW_INFRA_MISS=0
#   GUARD_LLM_TIMEOUT=1800
#   GUARD_LLM_HEARTBEAT=60
```

- 单一变量取代多行 export，**openclaw.md 现在只需要一行 `export GUARD_PROFILE=server`**
- 任何已 export 的同名变量始终优先（`${VAR:=default}` 语义）
- 本地交互模式下**不要** export 它，保持 `default_env.sh` 默认（即 `GUARD_PROFILE` 留空 / `local`）

> 详见 [`transform.md`](transform.md) "如何覆盖默认值"。

### 行为差异速查（两大子能力共用）

| 决策点 | 交互模式（macOS / 显式 `GUARD_INTERACTIVE=1`） | 非交互模式（默认 / `GUARD_PROFILE=server`） |
| --- | --- | --- |
| 转写 detect 后是否继续 | 询问用户确认 | **自动继续**（仅在 `framework: unknown` 且无 fallback 时 abort） |
| 转写主命令 | 不带 `-y` | **强制带 `-y`** |
| 转写 stage 失败 routing | 问用户三选一 | **自动按优先级重试**（见 [`transform.md`](transform.md) Step 5） |
| 打包 verify fail | 问用户三选一 | **自动选方案 1**：`--from-stage 50 -y` 走 LLM autofix |
| 打包发现前端产物过期 | 询问用户是否重新 build | **自动 abort** 退出非零，让调用方决定（拒绝带过期产物上线） |
| 报告产出 | Markdown 给用户读 | Markdown + 在 stdout 末尾输出**机器可读路径**（`GUARD_OUTPUT_ZIP=...`） |

### 非交互模式的"绝对不做"（两大子能力共用）

下面这些**即使**非交互也**必须** abort、退出非零、把诊断打到 stderr，**不要**自动绕过：

- ❌ 自动加 `--no-strict` / `GUARD_STRICT=0` 跳过 verifier 强行打包 —— 带伤产物上线
- ❌ 自动加 `--skip-llm` 绕过 LLM 改写 —— 产出未改造的副本
- ❌ 自动 `apply_diff` 改 `<work>` 副本里的源码绕过 verifier
- ❌ 连续 3 次失败仍循环重试 —— 视为不可恢复，让调用方人工介入
- ❌ `codewiz-cc` / `claude` / `codewiz` CLI 鉴权 401 —— 立即 fail，不要重试

### 用户显式覆盖

| 想要 | 命令 |
| --- | --- |
| 强制非交互（macOS 桌面跑长任务想完全不打扰） | `export GUARD_NONINTERACTIVE=1` |
| 强制交互（Linux 但你坐在终端前想被询问） | `export GUARD_INTERACTIVE=1` |
| 一键展开服务端推荐配置 | `export GUARD_PROFILE=server` |

> ⚠️ `GUARD_NONINTERACTIVE` 与 `GUARD_INTERACTIVE` 同时设置时 `GUARD_NONINTERACTIVE=1` 优先（更保守）。

## 前置检查（执行任何子流程前先做）

### 1. 定位工具根目录（zip 模式自动推导）

zip 解压后，所有工具脚本都位于 `<skill 根>/scripts/` 下。`scripts/default_env.sh` 通过 `BASH_SOURCE` 自动把 `$GUARD_TRANSFORM_HOME` 推导为 scripts/ 自身路径，**无须任何安装动作**：

```bash
# Seal 在加载 skill 后会把 SKILL.md 所在目录（=cowork-app/）注入运行环境，
# 用 SKILL_DIR 或对应的环境变量定位 scripts/，再 source default_env.sh
SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)}"
GUARD_TRANSFORM_HOME="$SKILL_DIR/scripts"
[ -f "$GUARD_TRANSFORM_HOME/default_env.sh" ] \
    || { echo "[FAIL] 未找到 scripts/default_env.sh，请确认 zip 解压完整" >&2; exit 1; }
source "$GUARD_TRANSFORM_HOME/default_env.sh"   # 内部会重新推导并 export GUARD_TRANSFORM_HOME
```

之后所有命令都用 `$GUARD_TRANSFORM_HOME/transform.sh`、`$GUARD_TRANSFORM_HOME/bin/guardx`、`$GUARD_TRANSFORM_HOME/bin/cowork-package-verify` 引用工具。

> **简化版**：如果你完全不知道 SKILL_DIR，但已 `cd` 到 skill 根目录下任意位置，直接 `source ./scripts/default_env.sh` 或 `source <skill 根>/scripts/default_env.sh` 即可，`default_env.sh` 内部用 `BASH_SOURCE` 自己推导路径，不依赖 cwd。

### 2. 检查 runtime

```bash
python3 --version && command -v codewiz-cc && command -v git && command -v unzip
```

- Python 必须 3.8+（Seal 云端运行环境通常满足；推荐 3.10+）
- `codewiz-cc` CLI 缺失 → Seal IDE 云端环境通常已自带；若仍找不到请联系 Seal 平台同学
- 想切到 standalone `claude` CLI → 编辑 `$GUARD_TRANSFORM_HOME/default_env.sh` 把 `GUARD_LLM=seal` 改成 `GUARD_LLM=claude`，并确保 `claude` 可用
- 其它缺失 → 按需提示（Linux 装 `apt install unzip`）

### 3. 确认源工程路径（两大子能力共用）

**推断逻辑（完全自动，不询问用户）**：

1. **用户在对话里明确给了路径** → 直接用，转成绝对路径
2. **用户没有给路径** → 直接用 `$PWD`（openclaw 两种调用方式 CWD 都已指向工程根）

```bash
if [ -n "<用户明确给的路径>" ]; then
    SRC_PROJECT="$(cd "<用户明确给的路径>" && pwd)"
else
    SRC_PROJECT="$PWD"
fi
```

路径必须满足（不满足则**立即 abort 退出非零**，不询问）：

- **不能**位于 `$GUARD_TRANSFORM_HOME` 内部
- 路径下必须有可识别的栈标志（`package.json` / `requirements.txt` / `next.config.*` / `vite.config.*` 等）

## 子能力入口分发

完成上述前置后，按用户意图调用对应子文档：

### 入口 1：项目转写 → [`transform.md`](transform.md)

适用：源工程**未经过**转写，需要完整跑 8 stage 流水线（detect → LLM 改写 → 模板渲染 → build → 烟测 → 打包 → 报告）。

```bash
# 1. 加载默认环境（包含 GUARD_PROFILE 展开逻辑）
source "$GUARD_TRANSFORM_HOME/default_env.sh"

# 2. 跑完整 transform（按运行模式分流，详见 transform.md Step 3）
export PYTHONUNBUFFERED=1
if [ "$GUARD_RUN_MODE" = "non-interactive" ]; then
    "$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" -y 2>&1
else
    "$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" 2>&1
fi
```

### 入口 2：项目打包 → [`package.md`](package.md)

适用：

- 转写已完成，用户在 `<src>-guard/` 工作副本里**手改**过文件后想重新打包
- 项目本身已合规（无须 LLM 改写），用户只想做最终的"合规体检 + 打包"
- 前后端分离项目，用户在前端改了源码、想确认产物是否已重建

```bash
# 1. 跑独立的打包前体检（合规验证 + 前端构建产物 mtime 检查）
"$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" "$SRC_PROJECT"

# 2. 全 OK → 直接打包；有 fail → 按 package.md 三选一分流
"$GUARD_TRANSFORM_HOME/transform.sh" "$SRC_PROJECT" --from-stage 60 -y
```

## 关键边界（两大子能力共用，绝对不要做）

按照 `transform_prompt.origin.md` 与 README 的设计哲学：

1. ❌ **不要把 transform 内部的 8 stage 自己用 claude 跑一遍** —— guard-transform 是确定性 Python pipeline，绕开等于回到 2575 行老 prompt
2. ❌ **不要修改 `prompts/*.md` / `verifiers/*.sh` / `templates/*.tpl`** 来"绕过"某个失败 —— 这些是工具契约，改了等于 silently 降低质量
3. ❌ **不要伪造 stdout / 不要伪造 `db.properties`** —— 任何"结果"必须基于真实文件或真实接口返回
4. ❌ **副本路径不要落在源工程目录下** —— 推荐用绝对路径调用，避免 `zip -r` 自吞
5. ❌ **不要忽略 AI 模型覆盖范围声明** —— transform 跑完后 report.md 里这一段必须给用户看
6. ❌ **detect 后用户补充技术栈信息（"有 DB / 有 SSO / 有 Redis"）时，不要回答"LLM 阶段会自动处理"** —— 这是常见幻觉。stage 30 (render_scripts) / stage 50 (verifier) 强依赖 `stack.json` 的 `has_db` / `has_sso` / `has_external_infra` flag，**必须先 apply_diff 改 stack.json 把对应字段从 0 改 1，再用 `--from-stage 20 -y` 续跑**。详见 [`transform.md`](transform.md) Step 1.5
7. ❌ **转写完成后不要继续把"再改一下"/"再打个 zip" 解析到原工程路径** —— 必须切到 `<src>-guard/` 副本（默认强制切换，给用户一个着重提示；用户主动说"切回源工程"才退回）。详见 [`transform.md`](transform.md) Step 4.5

## Additional resources

- **子能力 1 详细流程**：[`transform.md`](transform.md)
- **子能力 2 详细流程**：[`package.md`](package.md)
- **典型场景示例**：[`examples.md`](examples.md) —— 完整对话样例（安装 / Next.js / FastAPI / monorepo / 续跑 / 失败诊断）
- **失败诊断速查**：[`troubleshooting.md`](troubleshooting.md) —— 按 stage 编号查根因
- **参考索引**：[`reference.md`](reference.md) —— 文档地图、关键脚本路径、环境变量速查
- **完整设计文档**：`$GUARD_TRANSFORM_HOME/README.md`（zip 内 `scripts/README.md`）—— 调用链路图、Python 重构架构、LLM CLI 抽象层
- **Guard 子应用规范**：guard-transform 基于的 2575 行权威定义（在 ai-demo-platform-guard-rust 仓库根目录的 `transform_prompt.origin.md`，**zip 不携带**）
- **模型选择工具**：`$GUARD_TRANSFORM_HOME/choose-model.sh` —— 3 阶段菜单（backend → STRONG → FAST）永久切换默认 LLM 模型。**仅 macOS 终端**可跑；Seal 云端 Linux 环境请直接编辑 `default_env.sh` 或 `export GUARD_LLM*` 环境变量。
- **构建脚本**：[`build.sh`](build.sh) —— 把本目录打包成 `dist/cowork-app-*.zip`，供 Seal IDE 上传
