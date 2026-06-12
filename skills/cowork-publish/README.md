# cowork-publish

小红书 Cowork 平台发布 + 项目改写（transform）AgentSkill 的独立仓库。

本仓库是一个标准的 [AgentSkill](https://github.com/openclaw/openclaw)，通过 ClawHub / SkillHub 分发给 OpenClaw 用户。

## 这个 Skill 做什么

- **创作**：从内置模板（FastAPI / Koa monorepo / Next.js / React+FastAPI monorepo）scaffold 出合规项目骨架，改完业务代码后直接发布到 Cowork 线上
- **纯前端**：纯静态站点 / 单页 H5 / 纯前端小游戏（无后端）不走模板，按 `references/pure-frontend.md` 规范写好后直接 publish，自动走「静态资源挂载」类型，拿 `cowork.xiaohongshu.com/f/<alias>/` 域名
- **发布**：把项目打包成 Guard 子应用，部署到 Cowork 平台并拿到 `cowork.xiaohongshu.com/s/<alias>` 固定域名（应用部署）。publish/redeploy 内部 detect 自动在「应用部署」与「静态资源挂载」之间分流
- **transform**：把任意现有工程改写为符合 Cowork / Guard 子应用规范的项目
- **管理**：发布 / 重部署 / 删除作品 / 改 alias / 改可见性 / 改元信息

详见 [SKILL.md](./SKILL.md)（agent 行为契约）。
后续迭代维护参考 [ARCHITECTURE.md](./ARCHITECTURE.md)（功能与代码地图：每个功能在哪块代码、改它动哪里）。

## 路由约定（skill 命中，易踩点）

OpenClaw runtime 按 `SKILL.md` frontmatter 的 `description` 做语义匹配决定走哪个 skill。两个反复踩过的坑，维护 `description` 时务必保住：

1. **frontmatter 必须是合法 YAML，`description` 长串别带破坏解析的字符**。曾出现 `description` 用未加引号的单行长串、内含 markdown 加粗 `**...**` / `→` / 成对全角引号等，导致 loader 解析失败、**静默丢弃 description**，结果 skill 在 `available_skills` 里只有 name 没有描述，Agent 扫列表时关联不上「做页面」。改 `description` 后务必用 YAML 解析器验一遍（`python3 -c "import yaml,re; yaml.safe_load(re.match(r'^---\\n(.*?)\\n---', open('SKILL.md').read(), 16).group(1))"`），实在长建议用块标量 `>-`。

2. **「带文档 / 数据做展示页」要走本 skill，不要被 Canvas 抢走**。用户说「给我做个展示页面，数据参考：<文档链接>」时，曾因为带了文档链接被路由去画 Canvas。本质是「做一个能打开能分享的页面」，必须走本 skill 出真实静态网址——Canvas 只是临时画布、给不了可访问 URL。为此 `description` 里保留了：展示页 / 数据展示 / 可视化 / 报告页 / 落地页 / H5 / 看板等触发词，以及明确的「即使给了数据源/参考文档，做页面也走本 skill、不要去 Canvas」消歧句；SKILL.md 创作决策树里也有对应的「先读文档→数据内联进页面→publish 出网址」执行引导。**精简 description 时不要删掉这条消歧。**

## 仓库布局

```
SKILL.md                 # AgentSkill 主入口，LLM 读这个决定行为
cowork.py                # 主 CLI：scaffold / transform / pack / precheck / publish / redeploy /
                         #        deploy / status / update / set-alias / delete / detail /
                         #        list-projects / link / memory / search-* 等子命令
ARCHITECTURE.md          # 功能与代码地图（后续迭代维护参考）
README.md                # 你正在看的文件
references/              # 子文档：AI 调用规范、API 参考、DB、SSO、模板说明等
references/templates-ref/# 4 套技术栈模板说明（fastapi-only / koa-monorepo / nextjs-fullstack / react-fastapi-monorepo）
templates/              # scaffold 用的 4 套项目骨架（新建项目）
scripts/                 # 辅助脚本
transform/               # 项目改写子系统（把存量工程改成 Guard 规范）
├── transform.sh         # transform 入口 shell → bin/guardx
├── bin/                 # guardx / cowork-login-check / cowork-package-verify 可执行 shim
├── guardx/              # Python 改写引擎（stages_py / 8 阶段流水线）
├── profiles/            # 5 个技术栈的改写 profile（按 match 匹配存量工程）
├── prompts/             # 改写流程中的 LLM prompt 模板
├── templates/           # 渲染 install/start/health 的 *.tpl
└── verifiers/           # 30 个 verifier shell 脚本，逐条校验 Guard 红线
```

## 依赖

- `python3`（cowork.py 主 CLI）
- `requests`（cowork.py HTTP 用）
- `bash`（transform/transform.sh 入口）
- transform 改写部分需要可访问 LLM 的运行环境（详见 `transform/README.md`）

## 通过 ClawHub 安装

```bash
clawhub install cowork-publish
clawhub update cowork-publish
```

## 直接命令行使用（不经 OpenClaw agent）

```bash
# 从模板新建合规项目骨架（4 个 profile）
python3 cowork.py scaffold <name> --template fastapi-only

# 把现有工程改写为 Guard 规范
python3 cowork.py transform <srcDir>

# 打包
python3 cowork.py pack <srcDir>

# Guard 红线检查（脚本三件套 / SSO / DB / AI 等）
python3 cowork.py precheck <srcDir|zip>

# 一键发布（pack + deploy + 上传封面 + save）
python3 cowork.py publish <srcDir|zip> --cover <png> --title "..." --visibility self

# 改代码后重部署已有作品（保留 alias，自增版本）
python3 cowork.py redeploy <workId>

# 列我的项目（本地草稿 + 远端作品）
python3 cowork.py list-projects
```

环境变量：

- `COWORK_VERIFY_SSL=1` — 启用 HTTPS 证书校验（本地直跑时推荐；OpenClaw pod 出口走 forward proxy 默认关闭）

## 与 codewiz-openclaw 仓库的关系

- 历史上本 skill 内嵌于 codewiz-openclaw 仓库的 `extensions/cowork/skills/cowork-publish/`
- 当前以独立仓库方式维护，通过 ClawHub 分发；agent 全程通过 `python3 cowork.py <子命令>` 与 cowork 平台交互，无 plugin tool 依赖
- OpenClaw 端的 `cowork` plugin（`extensions/cowork/src/`）只保留 Gateway RPC 供客户端 UI（Coral Studio 列表 / 一键发布按钮等）直调，不再向 agent 暴露 tool；plugin 与本 skill 解耦后可各自独立演进
- 本仓库版本号、changelog 由 `clawhub publish` 时显式声明

## 发布到 SkillHub

```bash
clawhub publish . --slug cowork-publish --version <x.y.z> --changelog "..."
```

发布前先 `clawhub inspect cowork-publish` 确认当前 visibility / version，避免漂移。

## 与上游 guard-transform 的同步关系（迭代必读）

本仓库的「**应用规范 / 从 0 到 1 创建项目 / 转写项目**」三块逻辑，规则源头是上游仓库
`ai-demo-platform-guard-transform-skill`（下称 **上游**，git 见 `transform/.cowork-extras-source.json`）。
上游每次更新这三块，本仓库需对照本章同步。

> **本仓库 ≠ 上游构建产物**：上游是「`core/` 引擎 + `skills/base/` 文档模板 + 多平台 `vars.env`」的构建系统；
> 本仓库 = 上游 **seal 变体落地** + 叠加发布层（`cowork.py`）。所以只同步**规则/引擎内容**，不照搬上游目录结构。
> 当前对齐基准 commit 记录在 `transform/.cowork-extras-source.json` 的 `upstream.commit`，每次同步后更新它。

### 一、references 规范文档 ← 上游 `subapp-spec/CLAUDE.md`

| 本仓库 references | ← CLAUDE.md 章节 |
| --- | --- |
| `db.md` | §6 数据库 |
| `sso.md` | §8 SSO |
| `ai.md` | §7 AI |
| `urls.md` | §9 路径 |
| `blacklist.md` | §2 + §3.2 + §10.3 + §11 |
| `checklist.md` | §12 自检 |
| `scripts-trio.md` | §4 三件套 + §5 端口/env |
| `deps-python.md` | §10.1 |
| `deps-node.md` | §10.2 |

同步方式：上游 CLAUDE.md 对应章节变更 → 覆盖对应 references 文件，**保持逐字一致**（仅可保留本仓库已加的"agent publish-first / SSO 安全增强"等本地备注）。

### 二、templates/ scaffold 骨架 ← 上游 `core/templates/projects/`

`templates/<profile>/`（4 个：fastapi-only / koa-monorepo / nextjs-fullstack / react-fastapi-monorepo）
逐文件同步上游 `core/templates/projects/<profile>/`。**注意上游 `koa-fastapi-monorepo` 在本仓库改名为 `koa-monorepo`**。

### 三、references/templates-ref/ 模板导读 ← ⚠️ 上游无对应物，本仓库自有

上游没有"逐模板代码讲解"这种文档。本仓库的 `templates-ref/*.md` 是**轻量导读**：只写
①目录结构 ②该模板特有的坑 ③指向 `templates/<profile>/` 真实骨架 + 横切规范 md。
**同步红线：禁止在导读里另写 SSO / AI / DB 实现代码块**（历史上这么做过，漂移出 SSO 后门 / base64 / 错误 AI 协议等违规代码）——SSO/AI/DB 一律引用 `sso.md`/`ai.md`/`db.md`。

### 四、transform/ 引擎 ← 上游 `core/` + `skills/base/`（按文件分三类）

`transform/` 是上游引擎的**镜像 + seal 适配**。同步时**按下面三类区别对待**——
**A 类直接覆盖、B 类重渲染、C 类保护不动**：

| 类 | 文件 | ← 上游来源 | 同步动作 |
| --- | --- | --- | --- |
| **A 直接镜像**（逐字一致，✅ 可直接覆盖） | `guardx/`（除 `cli.py`）、`prompts/`、`verifiers/`、`templates/*.tpl`、`npmrc.tpl`、`server.cjs.tpl`、`detect_rules.json`、`transform.sh`、`bin/`、`transform.md`、`examples.md`、`package.md`、`reference.md`、`choose-model.sh` | `core/` 同名 / `skills/base/` 同名 | 上游更新 → **直接覆盖** |
| **B 渲染产物**（含 seal 专属值，⚠️ 不能直接覆盖，要重渲染） | `default_env.sh` ← `skills/base/default_env.sh.tpl`；`troubleshooting-transform.md` ← `skills/base/troubleshooting.md`（改了文件名） | base 模板 + `skills/seal/vars.env` | 上游改模板 → 用 seal vars 重渲染（占位符 `{{IDE_NAME}}`→seal、`{{LLM_CLI}}`→codewiz-cc 等），不要把含 `{{}}` 的原始模板直接拷进来 |
| **C 本地差异**（🔒 保护，**同步时跳过 / 手动合并**） | ① `.cowork-extras-source.json`（上游溯源，仅更新 commit）<br>② `.guard_transform_home`（seal 运行时配置，内容 `auto`）<br>③ `profiles/koa-monorepo.json`（上游叫 `koa-fastapi-monorepo.json`，本仓库**有意改名**）<br>④ `guardx/cli.py`（本仓库**有意删了 `guardx create` 子命令**，脚手架统一走 `cowork.py scaffold`） | — | **不能无脑覆盖**。`cli.py` 需手动合并上游改动 + 保留删 create；其余保留 |

> **术语桥接**：`transform/transform.md` 等镜像文档里命令写的是底层 `guardx`，在本 skill 体系里 `guardx transform` ≡ `cowork.py transform`（后者是封装入口）。桥接说明写在 **SKILL.md**（适配层），**不改镜像文件**——保证 A 类可零冲突覆盖。

### 同步操作清单（上游更新时照做）

1. `git -C <上游> log -1` 拿最新 commit
2. **A 类**：把上游 `core/`、`skills/base/` 对应文件覆盖到 `transform/`
3. **B 类**：用 `skills/render.sh` + `skills/seal/vars.env` 重渲染 `default_env.sh` / `troubleshooting-transform.md`
4. **C 类**：跳过 ②③，`cli.py` 手动合并（保留删 create），`.cowork-extras-source.json` 更新 `upstream.commit`
5. **references / templates / templates-ref**：按上面一/二/三节同步
6. 跑核查：`SCAFFOLD_TEMPLATES` = `templates/` = `templates-ref/` 四要素一致；`cowork.py` 编译通过；无旧 venv / SSO 后门残留

## 贡献

- 修 bug / 加 verifier / 加 profile：直接在本仓库提交，提 MR
- 改 Cowork API 协议适配：改 `cowork.py` 顶部 endpoint 区
- 改 transform 改写策略：动 `transform/guardx/stages_py/` 对应 stage + 对应 `prompts/`
- 改公开 SKILL 行为契约：动 `SKILL.md`，必须 bump version
- 同步上游规范：见上方「与上游 guard-transform 的同步关系」对照表
