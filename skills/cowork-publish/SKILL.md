---
name: cowork-publish
version: 0.1.0
description: Cowork 创作 + 发布的唯一入口 skill。覆盖两类意图：(A) **创作路由**——用户要做小工具 / dashboard / form / mini-app / 内部工具 / 表单 / 抽奖 / 后台页面 / 仪表盘时，按本 SKILL 的 Creation Mode 决定走 cowork_scaffold_app → cowork_publish 默认路径，含 precheck 三选一拦截、SSO + DB + AI Hard Rules、模板选择。(B) **发布操作**——把小红书内部小工具（前端 / 全栈 / FastAPI / Vite SPA / Next.js 等）打包成 Guard 子应用，部署到 Cowork 平台并拿到 `cowork.xiaohongshu.com/s/<alias>` 固定域名；含发布 / 重部署 / 删除作品；也支持把任意现有工程 transform 改写为 Cowork / Guard 子应用规范。**任何 cowork_scaffold_app / cowork_publish / cowork_redeploy / cowork transform 调用前必读。**触发词覆盖：发布到 cowork / 在 cowork 上线 / 打包 cowork zip / cowork 部署 / 拿 cowork 固定域名 / redeploy / 删 cowork 作品 / cowork 转写 / cowork 改写 / cowork 子应用规范 / convert to cowork subapp / 把 backlog/okr/dashboards 等本地 supervisord 项目搬到 cowork。
metadata: { "openclaw": { "requires": { "bins": ["python3"] } } }
---

# Cowork Creation Mode（路由决策，read first）

**触发**：用户要做 small tool / dashboard / form / mini-app / 内部工具 / 发布到 Cowork。
不属于这些场景时，**忽略本段全部规则**，直接看下方「这个 Skill 做什么」。

## 创建路径（默认）

全新需求 → `cowork_scaffold_app` 生骨架 → 写业务代码 → `cowork_publish`。这是默认路径，不需要询问用户「要发到哪里」。

## 发布现有项目（有拦截）

用户拿一个已存在的项目说「发布/上线/部署」时，先按下表判断，**不要直接硬调 cowork_publish**（tool handler 也有 guard 会报错）：

```
检查 srcDir 状态
├─ 有 .cowork.json                    → 已是 Cowork 项目，直接 cowork_redeploy
├─ 无 .cowork.json，Guard precheck 全绿 → 确认首发到 Cowork，调 cowork_publish
├─ 无 .cowork.json，Guard precheck 有 ❌  → 询问用户三选一：
│     a) 改写成 Cowork 子应用 → 跑 `python3 cowork.py transform <srcDir>`，改写完自动 cowork_publish（visibility=self）
│     b) 发布到其他平台 → 让用户指明平台，切换对应发布 skill
│     c) 取消
└─ 不确定 srcDir                      → 问用户是哪个项目
```

默认偏好：用户明确说「发到 Cowork」 / a) 改写后 Cowork，都算在 Cowork 路径里。仅在用户明确选 b) 时才跳其他平台。

## ⚠️ Creation Hard Rules（违反必 FAILED）

**下面提到的 `references/...` 绝对路径都是**
`/home/node/.openclaw/workspace/skills/cowork-publish/references/...`。用 `read` 工具读。

1. 用 `cowork.scaffold_app` 生成项目骨架；**禁止手写 install.sh / start.sh / health.sh**。
2. 写业务代码前 **MUST `read references/templates-ref/<选定模板>.md`**——不读 = 100% 编错凭印象写。
3. 加 DB / SSO / AI / 文件上传 / 复杂路由前 **MUST `read references/<对应主题>.md`**（见下方文件地图）。
4. **所有项目必须接入 SSO**（含 demo / dashboard / 抽奖，公司安全规范，无例外）。修改任何 SSO 相关代码前 **MUST 先 read `references/sso.md`**；precheck 会物理拦截匿名 fallback / env bypass 等偷懒。
5. AI 调用 **必须走 Runway 网关**（文本 Bedrock / 图像 Gemini），禁直接调 anthropic / openai / google SDK。
6. 持久化 **只能用 PostgreSQL via `db.properties`**，禁 Redis / S3 / MQ / ES / 向量库 / 本地磁盘。
7. **严格 publish-first，禁止本地验证**：scaffold → 改代码 → `cowork.publish` → 给用户线上 URL。
   - ❌ 不要起 `uvicorn` / `gunicorn` / `python3 app.py` / `npm run dev` 等任何本地服务做 health 检查
   - ❌ 不要 `curl 127.0.0.1:3000/...` 或 `curl localhost/health` 验接口
   - ❌ 不要跑 `bash start.sh` + `bash health.sh` 试探
   - ✅ 直接调 `cowork.publish`，让 Cowork Guard 平台跑 install.sh / start.sh / health.sh 给你结果
   - ✅ publish 报错就读错误消息修代码 → 重新 publish，不要本地复现
   - ✅ precheck 在 publish 内部跑，不需要 agent 提前手动跑
   - 理由：Cowork Guard 容器才是真实运行环境（同样的镜像、同样的 SSO、同样的 db.properties），本地起进程**永远跟生产环境有差异**，验过也白验；且耗时长易卡。
   - 如果用户**主动要求**「先本地跑跑看」，让用户自己执行 `python3 cowork.py dev start ./srcDir` —— 不是 agent 帮忙起。
8. 首次发布 `visibility="self"`（仅自己可见）；想改全公司 / 部门可见 → **不要调 tool**，让用户去 `coworkAppUrl` 手动改（防误挥）。
9. 后续每次代码改动 **默认自动 `cowork.redeploy`**（保留 alias / 元信息），不要每次问「要不要重新部署」。

## 模板选择速查

| profile                  | 场景                                         | 生产启动                             |
| ------------------------ | -------------------------------------------- | ------------------------------------ |
| `fastapi-only`           | Python 后端 / API / 表单 / dashboard（默认） | `uvicorn app:app`                    |
| `flask-only`             | Flask 老项目迁移                             | `gunicorn app:app`                   |
| `pure-spa-vite`          | 纯前端 SPA（Vue/React/Svelte）               | `node server.cjs`                    |
| `nextjs-fullstack`       | Next.js SSR / 后台                           | `node .next/standalone/server.js`    |
| `react-fastapi-monorepo` | 前 React + 后 FastAPI                        | backend uvicorn + 托管 frontend/dist |
| `koa-fastapi-monorepo`   | 前 Node + 后 Koa/Express                     | backend node + 托管 frontend/dist    |

## 按需 read 的 references 文件地图

路径前缀统一为 `/home/node/.openclaw/workspace/skills/cowork-publish/references/`。下表只列后缀。

| 改动                   | read 后缀                         |
| ---------------------- | --------------------------------- |
| 选定模板 → 写业务代码  | `templates-ref/<模板>.md` ⚠️ MUST |
| 加 DB                  | `db.md`                           |
| 加 AI（文本 / 图像）   | `ai.md`                           |
| 加 SSO                 | `sso.md`                          |
| 生成封面 / 头图（PIL） | `cover.md`                        |
| 路由 / 静态 / 重定向   | `urls.md`                         |
| Python 依赖            | `deps-python.md`                  |
| Node 依赖              | `deps-node.md`                    |
| 写完自检               | `checklist.md`                    |
| 不确定能不能做         | `blacklist.md`                    |
| 部署失败               | `troubleshooting.md`              |

上表里 topic refs + 6 个 template ref 已足够覆盖所有场景。官方完整规范 1266 行原文以拆到上述文件中。

## Creation Don't

- ❌ 调 `cowork.update_metadata` 改 visibility 为 partial / all（让用户去 Studio 改）
- ❌ 修改 `.cowork.json`（plugin / tool 写，agent 不动）
- ❌ 在 `install.sh` 跑 build / lint / npm 公网源
- ❌ pip 走公网（必须 `pypi.devops.xiaohongshu.com` 内网镜像）
- ❌ 端口写死 `--port 3000`，必须读 `${APP_PORT:-3000}`

## 失败响应

- `cowork.publish` / `cowork.redeploy` 失败 → read `references/troubleshooting.md` 找原因，修一次再试
- 连续 3 次失败 → **停手**，把 errorMessage + 你尝试过的修复贴给用户，让用户决定

---

# 这个 Skill 做什么

Cowork (https://cowork.xiaohongshu.com) 是小红书内部的 AI 作品社区 + 部署平台。
任何符合 **Guard 子应用规范** 的 zip 都能 1 分钟内拿到 `https://cowork.xiaohongshu.com/s/<alias>/` 这种**固定域名**，全公司可直接打开使用。

---

# Plugin Tool 速查（agent 看名字不够时查本表）

system prompt 里 14 个 `cowork_*` tool 的 description 被压缩极简（代价 ~30 字以下）。详细参数和使用场景看这里。

## 创建 / 发布 链路（默认走这些）

| Tool                              | 什么时候调            | 关键参数                                                                                                                                                                |
| --------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cowork_scaffold_app`             | 新建项目（每次 1 次） | `{ template: 'fastapi-only'\|'flask-only'\|'pure-spa-vite'\|'nextjs-fullstack'\|'react-fastapi-monorepo'\|'koa-fastapi-monorepo', description?: str, targetDir?: str }` |
| `cowork_suggest_publish_metadata` | 首发前拿默认 metadata | `{ projectId }` 返回 `{ title, intro, description, alias, tags, coverPath }`                                                                                            |
| `cowork_publish`                  | 首发作品              | `{ projectId, srcDir, title, alias, intro?, desc?, tags?, coverPath, visibility: 'self' }`（visibility 只能 'self'）                                                    |

> 用 PIL 生成中文封面/头图前，先读 `references/cover.md`。必须显式加载 CJK 字体（如 NotoSansCJK），禁止 `ImageFont.load_default()` 画中文，否则会变 □□□。
> | `cowork_redeploy` | 改代码后重部署（默认自动走，保留 alias）| `{ workId }` |
> | `cowork_memory_append` | **对话收尾时记一条**：记意图/选型理由，不记 commit message | `{ projectId, section?, content }` 详见下面「memory_append 使用准则」 |

## memory_append 使用准则（重要、agent 常记乱）

`cowork_memory_append` 是给 **未来的用户/agent 查「当初为什么这么干」** 的，不是 commit log，也不是部署日志。

### 何时调

默认**不调**。仅在下面这些强信号出现时调一次：

- 本轮对话即将结束（publish/redeploy 后交付用户之前）且本轮做了 **非显然的决定**：选了架构/技术栈/交互路径。**一次总结一条**。
- 用户明说“记下来 / 创建决策记录”。
- 有明确的 **踩坑教训**（未来同场景还会踩），比如 “PIL 必须加载 NotoSansCJK，否则中文乱码”。

### 记什么 (high-value)

- **意图层面**：“用户要协作 todo 但要求 ‘不端着’，所以用了卷卷子动漫风 + 嘻哈哈其事场景文案”
- **trade-off**：“游客模式 vs 强制 SSO 选后者，因为内部工具不需要兼容外部”
- **避坎**：“PIL 中文 tofu——必须用 NotoSansCJK，DejaVu fallback 会乱码”
- **数据口径**：“投票按 createdAt 倒序，匿名投票按 sessionId 去重”
- **已知限制**：“方案投票只支持单选，多选 v2 再做”

### 不记什么 (noise)

- ~~部署状态~~：“首发成功 / redeploy 完成” → 【发布历史】段 cowork.py 自动写，不需 agent 补
- ~~bug fix~~：“修了点击不生效问题” → commit message 够了
- ~~文案/样式调整~~：“按钮换了文案 / 颜色换成财财 色”
- ~~状态性描述~~：“项目创建完成 / scaffold 走了哪个模板” → manifest 里有

### 判断标准

写之前问自己：**「三个月后另一个 agent 接手这个项目时，他必须知道这件事才不会重蹈覆辙吗？」**。

- 是 → 记
- 不是 → 不记。git log + manifest + 代码本身能表达的均不记

### section 选择

- `关键决策`（默认）：架构/选型/trade-off
- `已知问题`：没解决的 bug / 设计局限
- `避坎教训`：踩过的坑与原因

---

## 修改已发布作品（用户明示说才走）

| Tool                     | 什么时候调                   | 关键参数                                                                                                                                             |
| ------------------------ | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cowork_set_alias`       | 用户说「改 alias / 换名字」  | `{ workId, alias: '3-32 位小写/数字/-' }`                                                                                                            |
| `cowork_update_metadata` | 用户说「改 title/封面/简介」 | `{ workId, title?, intro?, desc?, coverPath?, visibility?: 'self', tags? }`。**visibility 只能改 'self'**，改 partial/all 让用户去 coworkAppUrl 手动 |
| `cowork_delete_work`     | 用户说「删作品」             | `{ workId, confirm: true }`。**需 confirm:true 防误删**                                                                                              |

## 改写（transform）能力——现有工程 → Cowork 子应用

如果用户拿一个**已有项目**说要上 Cowork，但不符合 Guard 规范（缺 install.sh/start.sh/health.sh、用 redis、直调 openai SDK、SSO 不对等），
**不要手改**。跑一行：

```bash
python3 ~/.openclaw/workspace/skills/cowork-publish/cowork.py transform <srcDir>
```

实际实现在 `transform/transform.sh`（原 cowork-app skill 资产，2026-05-28 合并进本 skill），能自动：

- 生成/修复 install.sh / start.sh / health.sh
- 移除禁用依赖（redis / mongo / s3 / es / 向量库）
- LLM 调用改写为 Runway 网关
- 文件存储转 PG Large Object
- SSO 接入（严禁匿名 fallback / env bypass）
- db.properties key 权限收敛

改写完会调 28 个 verifier 硬校验（`transform/verifiers/verify_*.sh`），全过才结束。然后 agent **默认自动调 `cowork_publish`（visibility=self）**、不需二次确认。

> precheck 同步调用 `verify_db_props_keys.sh` / `verify_ai_calls.sh` / `verify_sso_correct.sh`，防止笨蛋模型绕过改写手写代码违规（如「让用户去管理页面配 PG」这种鬼话）。

---

## 不再暴露为插件 tool（client UI 走 RPC / agent 走 CLI）

以下能力不作为 agent 可调 plugin tool：

- **列举项目** → `cowork.list_projects` RPC（Coral Studio 列表直调）
- **本地 dev 预览** → `cowork.py dev start/stop/list` CLI（power-user）
- **绑定作品到本地代码** → agent 直接调 `cowork.py link` CLI（详下）

### 何时走 `cowork.py link`

用户说以下句型时：

- 「这个项目我之前发过 cowork / 这是 workId=X 的代码」
- 「我在新机器 clone 了代码，接上已发布的作品」
- 「这个目录是从别的地方 cp 来的，补上 manifest」
- 「studio 看到一个 cowork-only 作品，想把它 link 到 /repo/foo」

```bash
python3 /home/node/.openclaw/workspace/skills/cowork-publish/cowork.py link <workId> <srcDir>
```

**CLI 内部流程**（agent 不需手走这些步）：

1. 跑 precheck（不合规拒绝）→ 不合规时提示先 `python3 cowork.py transform <srcDir>` 改写
2. 检查 srcDir 未被别的 workId 占用，检查该 workId 未被别的目录 link（避免 split-brain）
3. 拉远端 detail 拿 alias / accessUrl / visibility / version
4. 写 `<srcDir>/.cowork.json`（workId/alias/accessUrl/coworkAppUrl/visibility 全入 cowork 块）

**成功后**：下次 list_projects 该项目从 🟡 cowork-only 升级为 🟢 published，redeploy 走这份 srcDir。

以上是默认「插件 tool」之外的能力。下面是底层 `cowork.py` CLI（插件 tool 多数都是这个 CLI 的包装）。

---

本 skill 把"打包 + 上传 OSS + 触发部署 + 等 RUNNING + 创建作品 + 绑定自定义域名"封装成一条命令：

```bash
python3 /home/node/.openclaw/workspace/skills/cowork-publish/cowork.py publish ./app.zip \
  --cover ./cover.png \
  --title "我的小工具" \
  --intro "一句话简介" \
  --alias my-tool \
  --tags 效率提升 \
  --visibility self
# → 返回 https://cowork.xiaohongshu.com/s/my-tool
```

适用场景：

- 写完一个本地 demo（FastAPI/Flask/Express/Next.js/Vite SPA），想让别人能用
- 把已经在 supervisord 上跑的小项目（backlog / dashboards）正式发布给团队
- Coral 客户端「一键发布」集成（直接复用 `cowork.py` 里的函数）

---

# 项目目录约定（必须遵守）

所有 Cowork 项目（无论是从零创建、scaffold、还是由非标准工程改写而来）统一放在：

```text
~/.openclaw/workspace/cowork/<project-slug>/
```

不要默认放到 `~/.openclaw/workspace/` 根目录，也不要新建到 `~/.openclaw/workspace/code/`（那是 legacy 兼容）。

原因：Cowork Studio / plugin 只扫描以下项目根：

1. `~/.openclaw/workspace/cowork/`（primary，新项目必须在这里）
2. `~/.openclaw/workspace/code/`（legacy，兼容历史项目）

不会扫描整个 workspace 根目录，避免误收 skills/memory/临时目录。

如果用户给了一个已有工程路径，需要改写成 Cowork 标准项目时，默认输出到：

```text
~/.openclaw/workspace/cowork/<source-name>-guard/
```

并在该目录写入 `.cowork.json`。

# 标准工作流

## 1. 打包（pack）

```bash
python3 cowork.py pack ./my-app
# 默认建副本 ./my-app-guard/，剥 node_modules/.next/dist 等
# 生成 ./my-app.zip
# 同时跑 precheck
```

- `--in-place`：不建副本，原地 zip（debug 用）
- `--skip-precheck`：跳过校验
- `-o my-app.zip`：自定义输出路径

## 1.5 本地调试（dev）—— **仅 power-user 手动，agent 不要调**

> ⚠️ **重要**：agent 默认走 publish-first 路径（直接 `cowork.publish`），**不要**代用户本地起进程。
> 下面 `cowork.py dev` 是给用户手动调试用的，为了避免：
>
> 1. 本地进程跟生产环境不一致——验过也白验
> 2. 未管理进程重负荷 / 端口冲突 → 可能把 gateway 一并干 crash（真实事故）
> 3. 额外耗时、不创造价值
>
> agent 正确路径：scaffold → 改代码 → `cowork.publish` → 看远端 errorMessage 修
>
> 仅当用户明确要求「帮我本地跑起来」时，**告诉用户自己执行下面命令**，不代跱。

```bash
# 用户手动跑
PYTHONHOME= python3 cowork.py dev start ./my-app --title "我的小工具" --alias my-tool
# → http://10.40.121.204:8901/?__cw=cw_xxxxxxxx
# → 同时输出 MINI_TOOL_OPEN:{...} 供 Coral Chat 侧识别并打开独立调试窗口
```

状态文件：`~/.openclaw/workspace/.cowork-dev/sessions.json`

常用命令（仍是用户跑，不是 agent）：

```bash
python3 cowork.py dev list --json
python3 cowork.py dev stop cw_xxxxxxxx
```

## 2. 预检（precheck）

```bash
python3 cowork.py precheck ./my-app.zip
```

会检查：

- 根目录是否有 install.sh / start.sh / health.sh
- install.sh 不含 build / 公网域名
- start.sh 末行 exec + 监听 3000 + bind 0.0.0.0
- 前端栈是否包含 build 产物（.next/standalone, dist, build, out）

输出 `❌` 是 blocker，`⚠️` 是建议。

## 3. 一键发布（publish）— 最常用

```bash
python3 cowork.py publish ./my-app.zip \
  --cover ./cover.png \
  --title "我的小工具" \
  --intro "一句话简介（可选）" \
  --desc "详细介绍，支持多行" \
  --alias my-tool \
  --tags 效率提升 代码开发 \
  --visibility self    # 锁死仅 self；释放为 partial/all 请去 Cowork Studio Web 手动调
```

参数：

- `--title`（必填）：作品标题
- `--cover`（必填）：封面图（jpg/png/gif），作品列表展示
- `--alias`（可选）：自定义 URL 后缀，3-32 位小写字母/数字/-，不填走自动 appId
- `--visibility`：**仅支持 `self`**（默认，仅自己可见）。释放为 `partial`/`all` 请发后点作品管理页 `coworkAppUrl`（`https://cowork.xiaohongshu.com/app/<encoded>` 格式，不是 `/s/<alias>` 预览页）中的 Edit Metadata 手动调，防误挥
- `--tags`：场景标签（中文 or enum，可多个）
- `--notify`：发布时通知关注者
- `--version`：默认 "1.0"
- `--timeout`：等待部署完成的秒数，默认 240
- `--force`：precheck 失败也强发

返回 JSON 包含 `workId` / `appId` / `accessUrl`。

## 4. 单步操作（更细粒度）

```bash
# 只部署不发布作品（quick test）
python3 cowork.py deploy ./my-app.zip
# → 拿到 deploymentId/appId/accessUrl，作品列表里**不会**出现

# 查部署状态（轮询）
python3 cowork.py status 268

# 我的作品
python3 cowork.py list

# 作品详情
python3 cowork.py detail 427

# 删除作品（不可恢复，需 --yes）
python3 cowork.py delete 427 --yes

# 更新已有作品的 zip（保留 alias 和元数据，只换代码）
python3 cowork.py redeploy 427 ./my-app-v2.zip

# 设置/修改已发布作品的 alias（走 PUT /deployment/{id}/alias，支持多次修改）
python3 cowork.py set-alias 449 my-new-alias --json
# 【同步副作用】会自动同步以下位置，勿手动改：
#  1. <srcDir>/.cowork.json          (cowork.alias / cowork.accessUrl)
#  2. <srcDir>/.cowork/memory.md     (frontmatter + 「部署历史」加一行)
#  3. ~/.openclaw/workspace/.cowork-dev/sessions.json  (如果该 src 正在跑 dev)
# alias 格式：3-32 位小写字母/数字/-，不能以 - 开头/结尾，不能连续 --
```

⚠️ **alias 变更后、旧 URL `/s/<old-alias>` 会 301 跳转到新 alias**（cowork 路由层能高处理），但外部书签/分享/Hi 里贴过的链接建议告知用户手动更新。`update_metadata` 同时改 alias 也会走同样的同步逻辑。

---

# 标签 enum

| 中文     | enum                        |
| -------- | --------------------------- |
| 效率提升 | efficiency_improvement      |
| 内容生成 | content_generation          |
| 数据分析 | data_analysis               |
| 研究洞察 | research_insight            |
| 沟通协作 | communication_collaboration |
| 代码开发 | code_development            |
| 设计创意 | design_creativity           |
| 其他     | other                       |

`--tags` 可以混用中英文，CLI 会自动转。

---

# 鉴权

- **OpenClaw pod 内运行**（默认）：出口走 forward proxy，自动注入 SSO cookie，**无需配置**
- **本地终端运行**：必须设环境变量 `COWORK_COOKIE`（从浏览器 devtools 拷 `Cookie` 头）
- 本地运行如果想严格校验 TLS：设 `COWORK_VERIFY_SSL=1`（pod 内不要设，会因为 proxy 自签失败）

---

# 真实跑通验证

2026-05-18 帝江第一次跑通的样例：

- zip：FastAPI 单页"狗腿子海豹掷骰子"
- 命令：`publish seal-dice.zip --cover cover.png --title 狗腿子海豹掷骰子 --alias seal-dice --visibility self`
- 输出：`{"workId":427,"appId":"1c3cd509","accessUrl":"https://cowork.xiaohongshu.com/s/seal-dice"}`
- 部署耗时：~15 秒（UPLOADING → INSTALLING → STARTING → RUNNING）

---

# 集成到其他工具（Coral 客户端 / 其他 skill）

`cowork.py` 内所有函数都可直接 `from cowork import publish, deploy_zip, upload_file, save_work, ...` 调用（pure Python，依赖 requests）。

Coral 客户端"一键发布"集成思路：

1. 调 `upload_file(zip_path)` 拿 zip 的 fileId
2. 调 `deploy_zip(file_id) + wait_deploy(deployment_id)` 拿 appId
3. 调 `upload_file(cover_path)` 拿封面 meta
4. 调 `save_work(...)` 创建作品
5. 把 `accessUrl` 显示在 UI 上

---

# 关键接口速查（细节见 references/api-reference.md）

| 接口          | 端点                                                           | 备注                                                                                                  |
| ------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 拿上传 token  | `GET edith.xiaohongshu.com/api/media/v1/upload/web/permit`     | 参数 `biz_name=ep&scene=oa_attachments&file_format=zip&file_count=1&version=1&subsystem=web_resource` |
| PUT 到 ROS    | `PUT ros-upload.xiaohongshu.com/<fileId>`                      | Header: `X-Cos-Security-Token: <permit.token>`                                                        |
| 触发部署      | `POST cowork/community/works/deploy`                           | body: `{"fileIdJson":"<json>"}` 内层 `fileId/business/scene/name`                                     |
| 轮询状态      | `GET cowork/community/works/deployment/{id}/status`            | 状态：UPLOADING→INSTALLING→STARTING→RUNNING / FAILED                                                  |
| 保存作品      | `POST cowork/community/works/save`                             | body 见 references/api-reference.md                                                                   |
| 我的作品      | `GET cowork/community/user-profile/works?email=<x>&tab=recent` |                                                                                                       |
| 作品详情      | `GET cowork/community/works/{id}`                              |                                                                                                       |
| 删除作品      | `POST cowork/community/works/delete`                           | body: `{"id": <int>}`                                                                                 |
| 拿规范 prompt | `GET cowork/community/works/transform/prompt`                  | 返回官方 guard-spec md 的 CDN url                                                                     |

---

# 常见错误

- **`Required script not found: install.sh`** → zip 套了一层目录，重新打包，install.sh 必须在根
- **`request reject! cause: old channel closed!`** → permit 时没传 `subsystem=web_resource`（旧通道下线）
- **`deploymentStatus: FAILED, errorMessage 含 OOM (exit 137)`** → 没在本地打 build 就上 zip 让 Pod build（违反硬约束）。本地 build 后再 zip
- **`getUploadTempPermit error0!bizCloudConfig-list-empty`** → `biz_name` 写错（必须 `ep`）
- **CLI 提示 SSL_CERT_VERIFY_FAILED** → pod 内 forward proxy 自签，确保没设 `COWORK_VERIFY_SSL=1`

---

# 仅自己可见 vs 全公司可见

**第一次发新工具，先用 `--visibility self` 测试**。验证完没问题需要释放可见范围时，**去 Cowork Studio Web 手动调**（CLI / agent 不帮你改为 partial/all，避免误挥）。

`SELF_ONLY` 状态下：作品在「我的创作」可见，公司其他人**搜不到也打不开作品页**，但**部署的 `/s/<alias>/` 仍然全公司可访问**（因为是 Guard 网关层挂载，不走作品权限）。所以即使设了仅自己可见，alias URL 也可以提前分享给个别同事试用。
