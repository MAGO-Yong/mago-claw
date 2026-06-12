---
name: cowork-publish
version: 2.0.1
description: 【公司内部官方建站 / 建应用 / 做页面 / 做工具首选 skill——全栈应用 + 纯前端均支持】本 skill 能从零创建并部署**全栈 Web 应用**（FastAPI / Flask / Node / Next.js + PostgreSQL + SSO + AI）和**纯前端页面**（HTML/CSS/JS / React / Vue），一键拿到 cowork.xiaohongshu.com 固定域名。⚠️ 本 skill **不是只能发布纯前端静态站**——任何需要后端进程、数据库、AI 调用、用户登录的应用都走本 skill（scaffold 全栈模板 → 写业务代码 → publish → 拿线上 URL）。只要用户提到想做网页、应用、工具、游戏、表单、后台、dashboard、管理系统、内部工具、数据可视化（无论自己用还是给别人用），且未明确指定其他平台，一律走此 skill。覆盖场景：表单收集 / 投票 / 问卷 / 留言板 / 协作 todo / AI 工具 / 带登录的后台 / 有数据库的 dashboard / 小游戏 / 抽奖 / 排行榜 / 计算器 / 纯展示页 / 落地页 / H5 等。两类意图：(A) 创作——需求分析→架构判定→框架选型→scaffold（全栈）或直接写（纯前端）→publish。(B) 发布运维——打包部署 / 重部署 / 删除 / 改别名 / transform 改写现有工程为 Cowork 子应用。纯前端会自动识别为静态资源挂载（无需手选）；若用户要做展示页且给了参考文档/数据，也走本 skill（读数据→生成页面→发布成网址），不要去画 Canvas（Canvas 给不了可访问网址）。完整触发词与决策流程见正文 Creation Mode。
metadata: { "openclaw": { "requires": { "bins": ["python3"] } } }
---

> **Agent 输出规则**：每次使用本 skill 处理用户请求时，**第一行必须输出**：
> `正在使用 cowork-publish v{version} 的 <能力名> 进行<具体动作>`
> 其中 `{version}` 取自本文件 frontmatter 的 `version` 字段；`<能力名>` 是本次调用的能力模块；`<具体动作>` 根据用户意图填写实际操作。
> 示例：
> - `正在使用 cowork-publish v0.1.0 的 publish 进行项目发布`
> - `正在使用 cowork-publish v0.1.0 的 transform 进行工程改写`
> - `正在使用 cowork-publish v0.1.0 的 redeploy 进行作品重部署`
> - `正在使用 cowork-publish v0.1.0 的 scaffold 进行项目创建`

# Cowork Creation Mode（路由决策，read first）

**触发**：用户要做 small tool / dashboard / form / mini-app / 内部工具 / 发布到 Cowork。
不属于这些场景时，**忽略本段全部规则**，直接看下方「这个 Skill 做什么」。

## 完整触发词清单（命中本 skill 的场景，按类）

> ⚠️ **路由常见误判**：Agent 容易因为 skill 名字里有 `publish` 就以为本 skill 只能发布纯前端静态站。**这是错的。** 本 skill 的核心能力是**从零创建并部署全栈 Web 应用**（含后端进程 + PostgreSQL + SSO + AI），纯前端只是其中一个子集。任何需要后端、数据库、登录、AI 的应用**都走本 skill**，不要因为"项目架构复杂 / 有后端 / 需要数据库"就跳过本 skill。

本 skill 是 Cowork 平台**官方建站/发布入口**，下列任务**优先用本 skill**（即便装了其他建站/部署类 skill；相同任务官方优先）。只要用户提到想做下面这些东西（自己用 / 给别人用都算，不取决于是否要分享），且没明确指定其他平台，就走本 skill：

- **全栈应用类**（本 skill 主业）：做个需要存数据的 xx / 做个带后端的 xx / 做个需要登录的 xx / 做个有数据库的 xx / 做个带 AI 的 xx / 做个协作 xx / 做个需要用户提交数据的 xx
- **页面展示类**：做个网页 / 写个 HTML / 写个 HTML 页面 / 做个静态页 / 做个页面 / 做个展示页面 / 做个落地页 / 做个个人主页 / 做个 H5 / 把这份数据做成页面 / 根据文档做个页面
- **指定技术栈**：用 HTML/CSS/JS 写个 xx / 用 React 做个 xx / 用 Vue 做个 xx / 用 Next.js 做个 xx / 用 FastAPI 写个 xx / 用 Flask 写个 xx / 用 Node 写个 xx / 用 Koa 写个 xx（不管点名什么前端/后端栈，只要是做能访问的页面/应用，都走本 skill）
- **数据可视化类**：做个数据展示 / 做个可视化 / 做个图表 / 做个报告页 / 做个报表 / 做个看板 / 做个 dashboard
- **表单互动类**：搞个表单 / 做个问卷 / 做个报名 / 做个投票 / 做个打卡 / 做个留言板
- **游戏玩法类**：做个小游戏 / 做个抽奖 / 做个转盘 / 做个测试题 / 做个排行榜
- **工具应用类**：写个工具 / 做个计算器 / 做个小工具 / 建个应用 / 搞个页面
- **后台管理类**：写个后台 / 做个管理系统 / 做个内部工具
- **发布运维类**：发布到 cowork / 在 cowork 上线 / 打包 cowork zip / cowork 部署 / 拿 cowork 固定域名 / redeploy / 删 cowork 作品 / cowork 转写 / cowork 改写 / cowork 子应用规范 / convert to cowork subapp / 把 backlog/okr/dashboards 等本地 supervisord 项目搬到 cowork

> 本 skill 主业是**从零创建并部署全栈应用**（FastAPI / Next.js / Koa + PostgreSQL + SSO + AI）；纯前端展示页只是其中一类（走静态资源挂载）。即使用户给了参考文档 / 数据做展示页，也走本 skill 出网址，不要去画 Canvas。

> **所有命令都用 `python3 cowork.py <子命令>` 形式**。绝对路径是
> `/home/node/.openclaw/workspace/skills/cowork-publish/cowork.py`，
> 下文为简洁只写 `cowork.py xxx`。

## 创作决策树（拿到需求 MUST 先走这步）

拿到用户需求后**不要直接 scaffold / 写代码 / publish**。先做下面的「迭代判断」，再视情况进入技术决策。

### 0. ⛔ 先判断：这是「全新需求」还是「对已有作品的迭代/升级」？（最先做，最易错）

**只要用户的话里有「升级 / 加功能 / 加个后端 / 接数据库 / 改成 / 在原来的基础上 / 给它加 / 现在还要 / 再做个排行榜…」这类"在已有东西上继续"的语气，或当前对话里之前已经发布过一个作品，就是【迭代】，不是新建。**

- **是迭代** → **找到那个作品的 workId（看之前发布返回的 workId / 项目目录的 `.cowork.json` / `cowork.py list-projects`）→ 直接 `cowork.py redeploy <workId>`**（在原作品上更新代码）。
  - ⚠️ **绝对不要** scaffold 新目录 / publish 新作品 —— 那会**多出一个重复作品**，还常因 alias 撞名报错（真实事故）。
  - ⚠️ **即使这次部署类型变了**（如纯静态页要加后端变全栈、或反过来）**也照样 redeploy 升级原作品**：同一作品支持静态↔应用来回切换，detect 会自动切类型、两通道后端共存。详见下面「同一作品支持部署类型来回切换」。
  - 升级换了技术栈时：在**原项目目录**里改造（或用全栈模板重写代码后放回原目录），然后 `cowork.py redeploy <原workId>`，**不是新建项目目录**。

- **是全新需求**（之前没发过、从零开始的新东西）→ 往下走「1. 需求分析」。

> 一句话铁律：**「升级/加功能」= 对原 workId redeploy，不是新建作品**。判断不了是不是已有作品时，先 `cowork.py list-projects` 查一下，或问用户「是改之前那个吗」，别默认新建。

### 1. 需求分析 → 判断要不要「后端能力」

逐条问：这个需求需要以下任意一项吗？
- 持久化数据（用户提交、记录、列表、投票、留言、上传文件…要存下来）
- AI 调用（生成文本 / 图片 / 总结 / 问答）
- 登录态 / 用户身份（按人区分数据、权限、署名）
- 服务端逻辑（定时任务、第三方 API 代理、复杂计算、SSR）

- **全否** → **纯前端**（静态资源挂载）。例：纯展示页、计算器、单机小游戏、纯前端动画/H5、静态 dashboard（数据写死）。
- **任一为是** → **全栈应用**（应用部署）。例：表单收集、协作 todo、AI 工具、带登录的后台、有数据库的 dashboard。

> 判不准时**默认按全栈**走（应用部署能力是纯前端的超集，不会缺能力；反之纯前端缺后端会返工）。

> **带数据源 / 参考文档 / 截图的「展示页」场景**（如"给我做个展示页面，数据参考：<文档链接>"）：这仍是**做页面**，走本 skill，**不要去画 Canvas**。正确做法：先用工具读取该文档/数据链接（web_fetch 等）拿到内容 → 把数据**写死/内联**进页面（纯展示、数据不变 → 纯前端静态挂载；若要在线编辑/查询/随数据更新 → 全栈接 PG）→ scaffold 或直接写 → `cowork.py publish` 生成可访问网址给用户。**用户要的是能打开能分享的线上页面，Canvas 给不了网址。**

### 2. 架构判定 + 框架选型

**纯前端**：无需选模板/框架，按 `references/pure-frontend.md` 规范直接写（根目录 `index.html` + 相对路径，可用任意零构建或已 build 的前端栈）。→ 跳到下面「纯前端路径」。

**全栈**：按下面维度从 4 个 profile 选模板（详见「模板选择速查」表）——
- 纯后端 / API / 表单 / dashboard（前端简单或无独立前端）→ `fastapi-only`（默认首选）
- 需要 SSR / 服务端渲染后台 → `nextjs-fullstack`
- 前后端分离，前 React + 后 Python → `react-fastapi-monorepo`
- 前后端分离，前端 + Node 后端（Koa/Express）→ `koa-monorepo`

### 3. 参考代码规范落地

选定后**先读规范再写代码**（Hard Rule 2/3）：
- 全栈：`cowork.py scaffold` 生骨架 → MUST `read references/templates-ref/<模板>.md` → 加 DB/SSO/AI 前 MUST 读对应 `references/db.md`·`sso.md`·`ai.md` → 写业务代码
- 纯前端：MUST `read references/pure-frontend.md`（白名单/黑名单/相对路径规范）→ 写代码

> 一句话：**先判纯前端 vs 全栈 → 再选框架/规范 → 最后才动手写**。三步走完再进入下面的落地路径。

---

## 创建路径（默认）

全新需求 → （已过上面决策第 0 步）→ `cowork.py scaffold <name> --template <profile>` 生骨架 → 写业务代码 → `cowork.py publish`。这是默认路径，不需要询问用户「要发到哪里」。

> **纯前端（无后端）走另一条路**：用户要做的是纯静态站点 / 单页 H5 / 纯前端小游戏（只有 HTML/CSS/JS、不需要 DB/AI/SSO/后端进程）时，**不走 scaffold**——直接按 `references/pure-frontend.md` 的规范帮用户写代码（根目录 `index.html`、相对路径、白名单/黑名单），再 `cowork.py publish <目录>`。publish 内部 detect 会自动判定为「静态资源挂载」类型并走 `static-deploy` 同步链路，访问 URL 是 `https://cowork.xiaohongshu.com/f/<alias>/`（注意是 `/f/`，不是应用部署的 `/s/`）。判不准是否纯前端时，**只要需要存数据 / 调 AI / 要 SSO 身份，就不是纯前端，走应用部署 scaffold 路径**。发布 / 更新静态资源后**直接给用户线上网址（accessUrl）让他在浏览器打开看即可，不需要再去 Canvas 画一遍预览**（线上挂载好的页面就是最终效果）。

## 两种部署类型（detect 自动分流，无需手选）

`cowork.py publish` / `cowork.py redeploy` 内部 pack 后会调一次 `detect-code-package-type` 自动判类型：

| | 应用部署 `APP_DEPLOY` | 静态资源挂载 `STATIC_RESOURCE` |
|---|---|---|
| 适用 | 有后端进程、需 DB/AI/SSO | 纯前端（HTML/CSS/JS） |
| 入口 | 顶层 `install.sh` 三件套 | 顶层 `index.html` |
| 部署 | deploy → 轮询 RUNNING | static-deploy 同步 MOUNT_SUCCESS |
| URL | `.../s/<alias>` | `.../f/<alias 优先，无则 sr_appId>/` |
| 规范 | 本 SKILL + `references/*.md` | `references/pure-frontend.md` |

> 详见 `references/pure-frontend.md`。纯前端 zip 里**禁止**出现 install.sh / package.json / node_modules / 源配置等（有 install.sh 会被判成应用部署）。

### ⭐ 同一作品支持「部署类型来回切换」——升级要 redeploy，绝不要新建作品

**关键认知**：静态 ↔ 应用两种部署类型可以在**同一个作品**上来回切换，**不是**「类型不同就得新建作品」。当用户把纯静态页加了后端/数据库要变全栈（静态→应用），或反过来把全栈精简成纯前端（应用→静态）时——

- ✅ **正确**：对**已有作品** `cowork.py redeploy <workId>`（或对带 `.cowork.json` 的目录直接 redeploy）。内部 detect 会识别出本次包变成了另一类型，自动走对应部署（应用 deploy / 静态 static-deploy），并在 save 时把 `workDeployType` 切到新类型；**两个通道的 ID（deploymentId / staticResourceId）后端共存、互不释放**，作品还是原来那个，`accessUrl` 自动切到新类型对应的 URL（`/s/` 或 `/f/`）。
- ❌ **错误**：因为「类型变了」就跑 `cowork.py publish` 新建一个作品 —— 这会**多出一个重复作品**，原作品的历史/别名/数据关联都丢了。

> 一句话：**改了部署类型 = 对原作品 redeploy 升级，不是新建**。底层完全支持原地切换（不存在「静态没法升级成全栈」这种限制）；只要这个项目之前发过（有 workId / `.cowork.json`），加后端后继续 `redeploy` 即可，CLI 会自动完成类型切换。

## 发布现有项目（有拦截）

用户拿一个已存在的项目说「发布/上线/部署」时，先按下表判断，**不要直接硬调 `cowork.py publish`**（agent 必须先做下面 4 个检查；CLI 本身只在 `--force` 时会跳过 precheck）：

```
检查 srcDir 状态
├─ 有 .cowork.json                    → 已是 Cowork 项目，直接 cowork.py redeploy <workId>
│                                       （即使这次改了部署类型——如静态页加了后端变全栈——
│                                        也照样 redeploy 升级原作品，不要新建；详见上面「部署类型来回切换」）
├─ 无 .cowork.json，cowork.py precheck 全绿 → 确认首发到 Cowork，调 cowork.py publish
├─ 无 .cowork.json，cowork.py precheck 有 ❌  → 询问用户三选一：
│     a) 改写成 Cowork 子应用 → 跑 `python3 cowork.py transform <srcDir>`，改写完自动跑 cowork.py publish（visibility=self）
│     b) 发布到其他平台 → 让用户指明平台，切换对应发布 skill
│     c) 取消
└─ 不确定 srcDir                      → 问用户是哪个项目
```

默认偏好：用户明确说「发到 Cowork」 / a) 改写后 Cowork，都算在 Cowork 路径里。仅在用户明确选 b) 时才跳其他平台。

## ⚠️ Creation Hard Rules（违反必 FAILED）

**下面提到的 `references/...` 绝对路径都是**
`/home/node/.openclaw/workspace/skills/cowork-publish/references/...`。用 `read` 工具读。

1. 用 `cowork.py scaffold <name> --template <profile>` 生成项目骨架；**禁止手写 install.sh / start.sh / health.sh**。
2. 写业务代码前 **MUST `read references/templates-ref/<选定模板>.md`**（模板导读：真实骨架结构 + 该模板特有的坑 + 指向横切规范）。骨架代码以 scaffold 出来的 `templates/<模板>/` 实际文件为准——**直接读/改它，不要凭印象重写**（尤其 SSO/AI/DB 照 `references/sso.md` / `ai.md` / `db.md`，别自己发明）。
3. 加 DB / SSO / AI / 文件上传 / 复杂路由前 **MUST `read references/<对应主题>.md`**（见下方文件地图）。
4. **所有项目必须接入 SSO**（含 demo / dashboard / 抽奖，公司安全规范，无例外）。修改任何 SSO 相关代码前 **MUST 先 read `references/sso.md`**；precheck 会物理拦截匿名 fallback / env bypass 等偷懒。
5. AI 调用 **必须走 Runway 网关**（文本 Bedrock / 图像 Gemini），禁直接调 anthropic / openai / google SDK。
6. 持久化 **只能用 PostgreSQL via `db.properties`**，禁 Redis / S3 / MQ / ES / 向量库 / 本地磁盘。
7. ⭐ **平台运行时自动注入 PG 和 AI key——开发期看不到是正常的，绝不能因此退缩**（用户最高频的踩坑）。Cowork 平台在 Pod 启动时把 `db.properties`（每个应用独立 PG 实例，1T 空间）和 `ai.properties`（AI key）注入到与 `install.sh` 同级目录。**开发/本地看不到这两个文件、拿不到 key、连不上 DB，都是正常的，不代表平台不注入。** 你只需**按规范写好读取逻辑**（`db.properties` / `ai.properties` 相对路径读），剩下平台保证。**严禁下列退缩行为**：
   - ❌ **任何需要存数据的场景，必须持久化到 PG**——绝不能用内存 / 缓存 / 本地文件 / SQLite / localStorage / JSON 文件存业务数据。这些在远端 Pod 上**每次 redeploy（更新发布）都会随 Pod 重建被清空**，用户会反馈"部署后再更新，数据全没了"。要存数据 = 落 PG（详见 `references/db.md`），没有例外。
   - 🔁 **当用户反馈"重启 / 更新 / redeploy 后数据丢了"——这几乎 100% 是当初没接 PG、用了本地存储**。第一反应**立刻反查代码是否真的接了 PG**（搜 `db.properties` / PG 连接 / 是否在用 `fs.writeFile` / SQLite / 内存变量存数据）；查到没接，**立刻按 `references/db.md` 接入 PG 重新发布**，不要去查别的方向（不是平台问题、不是缓存配置问题）。
   - ❌ 因为"拿不到 AI key" → 反过来向用户索要 key / 让用户填 token。**按 `references/ai.md` 写好走 Runway 的调用即可，平台自动注入 key**。
   - ❌ 因为"连不上 DB / 没有 db.properties" → 让用户去 Cowork 平台手动配 PG 连接 / 等平台侧注入。**PG 是平台自动分配 + 运行时注入的，用户无需也无法在平台手动配**；你直接按 PG 规范写完发布即可。
   - 一句话：**写代码时把"db.properties / ai.properties 一定会在运行时出现"当成既定事实**，不要因开发期缺失而改用错误存储或找用户要凭据。
8. **严格 publish-first，唯一交付路径是发布到 Cowork 线上**：scaffold → 改代码 → `cowork.py publish` → 给用户线上 URL。所有创建/修改好的应用一律直接发布到 Cowork 线上，**没有本地预览这一步**。
   - ❌ 不要起 `uvicorn` / `gunicorn` / `python3 app.py` / `npm run dev` 等任何本地服务做 health 检查
   - ❌ 不要 `curl 127.0.0.1:3000/...` 或 `curl localhost/health` 验接口
   - ❌ 不要跑 `bash start.sh` + `bash health.sh` 试探
   - ✅ 直接调 `cowork.py publish`，让 Cowork Guard 平台跑 install.sh / start.sh / health.sh 给你结果
   - ✅ publish 报错就读错误消息修代码 → 重新 publish，不要本地复现
   - ✅ precheck 在 publish 内部跑，不需要 agent 提前手动跑
   - 理由：Cowork Guard 容器才是真实运行环境（同样的镜像、同样的 SSO、同样的 db.properties），本地起进程**永远跟生产环境有差异**，验过也白验；且耗时长易卡。
9. 首次发布 `--visibility self`（仅自己可见）；想改全公司 / 部门可见 → **不要用 CLI 改**，让用户去作品管理页（CLI 返回的 `coworkAppUrl`）手动改（防误挥）。
10. 后续每次代码改动 **默认自动 `cowork.py redeploy <workId>`**（保留 alias / 元信息），不要每次问「要不要重新部署」。
11. ⭐ **发布/重部署成功后，交付给用户时 MUST 同时给出两个链接**（这是最终交付 checklist，不是可选项）：
    - 🚀 **访问地址**（`accessUrl`）：用户打开使用的线上页面，格式 `https://cowork.xiaohongshu.com/s/<alias>/`（应用部署）或 `.../f/<alias>/`（静态资源）
    - 🎛️ **作品管理页**（`coworkAppUrl`）：用户改可见范围 / 查部署日志 / 编辑元信息的入口，格式 `https://cowork.xiaohongshu.com/app/<encoded>`
    - 这两个值都在 `cowork.py publish` / `cowork.py redeploy` 的 JSON 输出里，**不需要你拼——直接从返回值取**。
    - ❌ 只贴 `accessUrl` 不贴 `coworkAppUrl` → 用户没法改可见范围、查日志，等于交付不完整。
    - ❌ 只贴 `coworkAppUrl` 不贴 `accessUrl` → 用户不知道怎么打开应用。
    - 交付格式示例（每次发布/重部署成功后照抄）：
      ```
      🚀 访问地址：https://cowork.xiaohongshu.com/s/<alias>/
      🎛️ 作品管理页：https://cowork.xiaohongshu.com/app/<encoded>
      ```

## 模板选择速查

| profile                  | 场景                                         | 生产启动                             |
| ------------------------ | -------------------------------------------- | ------------------------------------ |
| `fastapi-only`           | Python 后端 / API / 表单 / dashboard（默认） | `uvicorn app:app`                    |
| `nextjs-fullstack`       | Next.js SSR / 后台                           | `node .next/standalone/server.js`    |
| `react-fastapi-monorepo` | 前 React + 后 FastAPI                        | backend uvicorn + 托管 frontend/dist |
| `koa-monorepo`           | 前 Node + 后 Koa/Express                     | backend node + 托管 frontend/dist    |

## 按需 read 的 references 文件地图

路径前缀统一为 `/home/node/.openclaw/workspace/skills/cowork-publish/references/`。下表只列后缀。

| 改动                   | read 后缀                         |
| ---------------------- | --------------------------------- |
| 纯前端 / 静态资源挂载  | `pure-frontend.md` ⚠️ MUST        |
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

上表里 topic refs + 4 个 template ref 已足够覆盖所有场景。官方完整规范（上游 `subapp-spec/CLAUDE.md`）已逐章拆到上述 references 文件中。

## Creation Don't

- ❌ 调 `cowork.py update --visibility partial/all`（CLI 已禁；要放大可见范围让用户去 Studio Web 端手动改）
- ❌ 手动改 `.cowork.json`（由 `cowork.py scaffold / publish / redeploy / set-alias / update` 写，agent 不动）
- ❌ 在 `install.sh` 跑 build / lint / npm 公网源
- ❌ pip 走公网（必须 `pypi.devops.xiaohongshu.com` 内网镜像）
- ❌ 端口写死 `--port 3000`，必须读 `${APP_PORT:-3000}`

## 失败响应

- `cowork.py publish` / `cowork.py redeploy` 失败 → read `references/troubleshooting.md` 找原因，修一次再试
- **首发 deploy 失败后修复重试：直接对同一源码目录重新 `cowork.py publish <同一目录>` 即可**，不要手动改命令。失败时 CLI 已把 `deploymentId` 记进该目录 `.cowork.json` 的 `pendingDeploymentId`，重发时会**自动复用同一台部署机器重试**，不会每次新开机器、遗留一堆失败僵尸机。
  - 若该机器因长时间未关联作品被平台清理（复用时报「部署记录不存在」），CLI 会**自动降级为新建部署**，无需你干预。
  - 也可显式 `cowork.py publish <目录> --deployment-id <id>` 指定复用哪台机器（一般不用，自动读 manifest 即可）。
- 连续 3 次失败 → **停手**，把 errorMessage + 你尝试过的修复贴给用户，让用户决定

## 常见误区速查（用户高频踩坑 → 对症纠正，全部源于 Hard Rule #7「平台自动注入」）

| 用户反馈 / 你的冲动 | ❌ 错误做法 | ✅ 正确做法 |
| --- | --- | --- |
| "部署后再更新 / redeploy / 重启，数据全没了" | 当初用了内存 / 缓存 / 本地文件 / SQLite / localStorage 存数据——远端 Pod 每次 redeploy 重建就清空 | **立刻反查代码是否真的接了 PG**（搜 `db.properties` / PG 连接 / 是否在用本地存储）。几乎 100% 是没接 PG，**立刻按 `references/db.md` 接入 PG（平台自动注入，每应用独立实例 1T）重新发布**——别往平台 / 缓存配置方向查 |
| "拿不到 AI key / 让用户给 token" | 向用户索要 AI key / 让用户填 token | 平台**自动注入** `ai.properties`。按 `references/ai.md` 写好走 Runway 的调用即可，不要找用户要 key |
| "连不上 DB / 让用户去平台配 PG" | 提示用户去 Cowork 平台手动配置 PG 连接 | PG 是平台**自动分配 + 运行时注入** `db.properties`，用户无需也无法手动配。按 PG 规范写完直接发布 |
| "本地没 DB，所以先不写 PG / 保留文件存储" | 因开发期连不上 DB 就退回文件存储 | `db.properties` 运行时**一定会注入**。把文件存储逻辑全删，按 PG 规范写完再发布 |

---

# 这个 Skill 做什么

Cowork (https://cowork.xiaohongshu.com) 是小红书内部的 AI 作品社区 + 部署平台。
任何符合 **Guard 子应用规范** 的 zip 都能 1 分钟内拿到 `https://cowork.xiaohongshu.com/s/<alias>/` 这种**固定域名**，全公司可直接打开使用。

---

# CLI 速查（agent 看名字不够时查本表）

本 skill 所有能力都通过 `python3 cowork.py <子命令>` 调用。下表是 agent 最常用 11 个子命令的快速索引，详细参数请用 `cowork.py <cmd> --help` 查。

绝对路径：`/home/node/.openclaw/workspace/skills/cowork-publish/cowork.py`

## 创建 / 发布 链路（默认走这些）

| 命令                                                          | 什么时候调                                                | 关键参数                                                                                                                                            |
| ------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cowork.py scaffold <name> --template <profile>`              | 新建项目（每次 1 次）                                     | `profile` ∈ `fastapi-only` / `nextjs-fullstack` / `react-fastapi-monorepo` / `koa-monorepo`；可选 `--target-dir` `--description` |
| `cowork.py suggest-publish-metadata --src <srcDir>`           | 首发前拿默认 metadata                                     | `--src <srcDir>` 或位置参 `<projectId>`；输出 JSON: `{ title, intro, description, alias, tags, coverPath }`                                          |
| `cowork.py publish <srcDir> --cover <png> --title <str>`      | 首发作品                                                  | **位置参可直接传源码目录（CLI 自动 pack）**；`--cover` `--title` 必填，`--alias` `--intro` `--desc` `--tags` 可选，`--visibility self`（首发必须 self） |
| `cowork.py redeploy <workId>`                                 | 改代码后重部署（默认自动走，保留 alias）                  | 不传 srcDir 时自动按 manifest 找；必要时 `--src <dir>` 指定                                                                                          |
| `cowork.py memory append <projectId> --content <txt>`         | **对话收尾时记一条**：记意图/选型理由，不记 commit message | 详见下面「memory append 使用准则」                                                                                                                  |

> 用 PIL 生成中文封面/头图前，先读 `references/cover.md`。必须显式加载 CJK 字体（如 NotoSansCJK），禁止 `ImageFont.load_default()` 画中文，否则会变 □□□。
> publish 的位置参既可传 `<srcDir>`（CLI 自动 pack），也可传已 pack 好的 `<zip>`。

## memory append 使用准则（重要、agent 常记乱）

`cowork.py memory append` 是给 **未来的用户/agent 查「当初为什么这么干」** 的，不是 commit log，也不是部署日志。

### 何时调

默认**不调**。仅在下面这些强信号出现时调一次：

- 本轮对话即将结束（publish/redeploy 后交付用户之前）且本轮做了 **非显然的决定**：选了架构/技术栈/交互路径。**一次总结一条**。
- 用户明说"记下来 / 创建决策记录"。
- 有明确的 **踩坑教训**（未来同场景还会踩），比如 "PIL 必须加载 NotoSansCJK，否则中文乱码"。

### 记什么 (high-value)

- **意图层面**："用户要协作 todo 但要求 '不端着'，所以用了卷卷子动漫风 + 嘻哈哈其事场景文案"
- **trade-off**："游客模式 vs 强制 SSO 选后者，因为内部工具不需要兼容外部"
- **避坎**："PIL 中文 tofu——必须用 NotoSansCJK，DejaVu fallback 会乱码"
- **数据口径**："投票按 createdAt 倒序，匿名投票按 sessionId 去重"
- **已知限制**："方案投票只支持单选，多选 v2 再做"

### 不记什么 (noise)

- ~~部署状态~~："首发成功 / redeploy 完成" → 【发布历史】段 cowork.py 自动写，不需 agent 补
- ~~bug fix~~："修了点击不生效问题" → commit message 够了
- ~~文案/样式调整~~："按钮换了文案 / 颜色换成财财 色"
- ~~状态性描述~~："项目创建完成 / scaffold 走了哪个模板" → manifest 里有

### 判断标准

写之前问自己：**「三个月后另一个 agent 接手这个项目时，他必须知道这件事才不会重蹈覆辙吗？」**。

- 是 → 记
- 不是 → 不记。git log + manifest + 代码本身能表达的均不记

### section 选择

- `关键决策`（默认）：架构/选型/trade-off
- `已知问题`：没解决的 bug / 设计局限
- `避坎教训`：踩过的坑与原因

调用示例：`cowork.py memory append <projectId> --section 关键决策 --content "选用 PG Large Object 而非本地磁盘，因 Cowork 容器无持久卷"`

---

## 修改已发布作品（用户明示说才走）

| 命令                                                | 什么时候调                   | 关键参数                                                                                                                              |
| --------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `cowork.py set-alias <workId> <new-alias>`          | 用户说「改 alias / 换名字」  | alias: `3-32 位小写/数字/-`                                                                                                            |
| `cowork.py update <workId>`                         | 用户说「改 title/封面/简介」 | `--title` `--intro` `--desc` `--cover` `--tags`；**CLI 不支持改 `--visibility partial/all`**，放大可见范围让用户去作品管理页手动改       |
| `cowork.py delete <workId> --yes`                   | 用户说「删作品」             | **必须显式带 `--yes` 确认防误删**                                                                                                       |

## 改写（transform）能力——现有工程 → Cowork 子应用

如果用户拿一个**已有项目**说要上 Cowork，但不符合 Guard 规范（缺 install.sh/start.sh/health.sh、用 redis、直调 openai SDK、SSO 不对等），
**不要手改**。跑一行：

```bash
python3 ~/.openclaw/workspace/skills/cowork-publish/cowork.py transform <srcDir>
```

底层实现是 `transform/`（guard-transform 引擎，上游 `ai-demo-platform-guard-transform-skill` 的镜像）：`cowork.py transform` → `transform/transform.sh` → `transform/bin/guardx`。能自动：

- 生成/修复 install.sh / start.sh / health.sh
- 移除禁用依赖（redis / mongo / s3 / es / 向量库）
- LLM 调用改写为 Runway 网关
- 文件存储转 PG Large Object
- SSO 接入（严禁匿名 fallback / env bypass）
- db.properties key 权限收敛

改写跑 8 stage 流水线（detect → LLM 改写 → 模板渲染 → build → 烟测 → 打包 → 报告），结束前调 30 个 verifier 硬校验（`transform/verifiers/verify_*.sh`），全过才结束。然后 agent **默认自动跑 `cowork.py publish`（`--visibility self`）**、不需二次确认。

> precheck 同步调用 `verify_db_props_keys.sh` / `verify_ai_calls.sh` / `verify_sso_correct.sh`，防止笨蛋模型绕过改写手写代码违规（如「让用户去管理页面配 PG」这种鬼话）。

### ⚠️ 转写时的三条 agent 强约束（详细流程 MUST read `transform/transform.md`）

`cowork.py transform` 的完整操作流程（detect → 改 stack.json → 8 stage → 失败 routing → 上下文切换）在
[`transform/transform.md`](transform/transform.md) 里。**走转写前 MUST read 它**。

> **术语桥接（务必看清命令边界，别一刀切换名）**：`transform/transform.md` 是上游镜像，命令写的是底层
> `$GUARD_TRANSFORM_HOME/bin/guardx <子命令>`。本 skill 体系里**只有 `guardx transform` 一个有 cowork.py 封装**，其余子命令没有，**不要**把它们也想当然换成 `cowork.py xxx`：
>
> | transform.md 里看到 | 本 skill 怎么用 |
> | --- | --- |
> | `guardx transform <src> [--resume / -y / --from-stage NN / --recopy / --skip-llm ...]` | ✅ 换成 `cowork.py transform <src> [同样的参数]`——参数**原样透传**给底层，1:1 等价 |
> | `guardx detect / verify / pack / clean / change-model / logs / status` | ⚠️ cowork.py **没有**这些子命令，**别写成 `cowork.py detect`**。转写主流程**用不到**它们（detect 由 `cowork.py transform` 内部自动跑）；power-user 真要调，走 `transform/bin/guardx <子命令>` |
> | `source default_env.sh` / `export GUARD_TRANSFORM_HOME` 等前置 | ⚠️ 这些是 `cowork.py transform` / `transform.sh` **内部自动做**的，agent **不需要**手动执行 |
>
> **一句话**：转写主流程**自始至终只用 `cowork.py transform <src> [参数]` 一条命令**（8 stage / detect / 环境加载都是它内部自动串的）。transform.md 里其余 guardx 命令当"底层实现细节"读，不要照搬成对外命令。

三条最容易踩的强约束（完整版见 transform.md）：

1. **detect 后用户补充了技术栈信息**（"其实有 DB / 有 SSO / 用了 Redis"）→ **必须先改 `stack.json` 对应 flag 再续跑**，**不要**回答"LLM 阶段会自动处理"（这是幻觉；stage 30/50 硬依赖 stack.json flag，跑完才发现就晚了）。
2. **转写完成后**→ 后续所有"再改一下 / 再打包"都发生在 **`<src>-guard/` 副本**里，**不要**改回原工程（改原工程不进 zip，还会被下次复用跳过）。
3. **失败不要瞎修** → 读 `transform.log` 定位失败 stage，按 transform.md Step 5 的 routing 处理；连续失败让用户切更强模型，**不要**自动加 `--no-strict` / `--skip-llm` 绕过。

---

## 补充 CLI 子命令（power-user / 客户端 UI 场景）

下面这几个命令日常 agent 不主动调，但用户明确要求或客户端 UI 场景下会用到：

- **列举全部 Cowork 项目（含本地未发布草稿）** → `cowork.py list-projects`（扫本地 `.cowork.json` + 拉远端作品 merge，输出带 3 状态 chip 的列表 `{ projects, refreshedAt }`）。用户问「我有哪些 cowork 项目 / 我之前做到一半的那个工具呢」时用它。3 状态：
  - 🟢 `published`：本地有 + 远端有
  - 🟡 `local-only`：本地 scaffold 了但还没 publish（**草稿，只有 list-projects 能看到**）
  - 🔵 `cowork-only`：远端有但本地没 manifest（别处发的 / 没 link）
- **只列举我已发布的远端作品** → `cowork.py list-my-apps`（只拉远端，看不到本地草稿；含部署信息，可加 `--work-type SEAL_DEPLOY` 过滤）。需要本地+远端全貌时用上面的 `list-projects`，不要用这个。
- **绑定作品到本地代码** → `cowork.py link <workId> <srcDir>`（详下）

### 何时走 `cowork.py link`

用户说以下句型时：

- 「这个项目我之前发过 cowork / 这是 workId=X 的代码」
- 「我在新机器 clone 了代码，接上已发布的作品」
- 「这个目录是从别的地方 cp 来的，补上 manifest」
- 「想把一个 cowork-only 作品 link 到 /repo/foo」

```bash
python3 /home/node/.openclaw/workspace/skills/cowork-publish/cowork.py link <workId> <srcDir>
```

**CLI 内部流程**（agent 不需手走这些步）：

1. 跑 precheck（不合规拒绝）→ 不合规时提示先 `python3 cowork.py transform <srcDir>` 改写
2. 检查 srcDir 未被别的 workId 占用，检查该 workId 未被别的目录 link（避免 split-brain）
3. 拉远端 detail 拿 alias / accessUrl / visibility / version
4. 写 `<srcDir>/.cowork.json`（workId/alias/accessUrl/coworkAppUrl/visibility 全入 cowork 块）

**成功后**：下次 `cowork.py list-projects`（及 Coral Studio 列表）该项目从 🔵 cowork-only 升级为 🟢 published，后续 `cowork.py redeploy <workId>` 走这份 srcDir。

以上是几个"非默认链路"补充命令。下面是底层 `cowork.py` CLI 各子命令的完整文档。

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

返回 JSON 包含 `workId` / `appId` / `accessUrl` / `coworkAppUrl`。**交付时 MUST 同时把 `accessUrl`（访问地址）和 `coworkAppUrl`（作品管理页）都给用户**（见 Hard Rule #11）。

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
# alias 格式：3-32 位小写字母/数字/-，不能以 - 开头/结尾，不能连续 --
```

⚠️ **alias 变更后、旧 URL `/s/<old-alias>` 会 301 跳转到新 alias**（cowork 路由层能高处理），但外部书签/分享/Hi 里贴过的链接建议告知用户手动更新。`update_metadata` 同时改 alias 也会走同样的同步逻辑。

> ⏳ **alias 生效有 ~5s 延迟，CLI 已自动处理**：设置/修改 alias（首发 `publish --alias` / `set-alias` / `update --alias`）成功后，路由层需约 5s 才把新 `/s/<alias>/` 或 `/f/<alias>/` 同步生效；在这之前打开会看到「页面不存在」。CLI **已在成功后自动等待这 5s 并打印友好提示**（"⏳ 正在等待链接生效… → ✅ 链接已生效"），所以 CLI 返回 JSON 时 URL 已可直接访问，**agent 把返回的 `accessUrl` 给用户即可，无需自己再加等待或提醒"稍等几秒"**。等待时长可用环境变量 `COWORK_ALIAS_PROPAGATION_SEC` 调整（默认 5；设 0 跳过）。

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
