# cowork-publish 架构与功能地图

> 本文面向 **后续迭代维护者**（人 + agent），不是使用手册。
> 它回答的是：「某个功能在哪块代码？改它要动哪里？模块之间怎么串？」
> 使用方法看 [SKILL.md](./SKILL.md)（agent 行为契约）和 [README.md](./README.md)（安装/CLI）。

---

## 1. 顶层结构

```
cowork-publish/
├── SKILL.md            # agent 行为契约（LLM 读这个决定怎么做）；改公开行为必 bump version
├── cowork.py           # 主 CLI（~4000 行，纯 Python + requests）：全部对外能力的实现
├── README.md           # 安装 / CLI 用法（面向使用者）
├── ARCHITECTURE.md     # 本文（面向维护者）
├── references/         # agent 按需 read 的主题文档（DB / SSO / AI / 模板说明 等）
├── templates/          # scaffold 用的 4 套项目骨架（新建项目）
└── transform/          # 改写子系统（把存量工程改成 Guard 规范）
    ├── transform.sh    # 入口 shell → bin/guardx
    ├── bin/            # guardx / cowork-login-check / cowork-package-verify 三个可执行 shim
    ├── guardx/         # Python 改写引擎（stages_py 流水线 + profile/llm/verifier 等）
    ├── profiles/       # 5 个技术栈 profile（按 match 字段匹配存量工程）
    ├── prompts/        # 改写流程的 LLM prompt 模板
    ├── templates/      # 渲染 install/start/health 的 *.tpl
    └── verifiers/      # 30 个 verify_*.sh 硬校验脚本
```

**两条独立子系统**：
- **主 CLI（`cowork.py`）** —— 所有对外能力的唯一入口，纯 Python，零业务依赖（只依赖 requests）。
- **transform 引擎（`transform/`）** —— 改写存量工程，shell + Python 混合，依赖可访问的 LLM CLI。
  主 CLI 通过 `cmd_transform` thin wrapper 调 `transform.sh`，两者解耦。

---

## 2. 五大功能模块

> 下表是「功能 → 代码落点」的速查；详细见后续各节。

| 功能 | 入口命令 | 核心代码 |
| --- | --- | --- |
| ① 项目规范（新建 / 改写） | `scaffold` / `transform` | `cmd_scaffold` / `cmd_transform` + `transform/` |
| ② 部署 / 轮询 / 发布 | `publish` / `deploy` / `redeploy` / `status` | `cmd_publish` / `deploy_zip` / `wait_deploy` / `save_work` |
| ③ 作品管理（别名 / 可见性 / 元信息） | `set-alias` / `set-visibility` / `update` / `delete` | `cmd_set_alias` / `cmd_set_visibility` / `cmd_update` / `cmd_delete` |
| ④ 本地数据联动（manifest / memory / ID） | （内嵌在各命令）/ `list-projects` / `link` | `_ensure_manifest` / `_memory_*` / `cmd_list_projects` / `cmd_link` |
| ⑤ 组织架构查询（可见性配置辅助） | `search-users` / `search-contacts` / `resolve-department-names` | `cmd_search_*` / `cmd_resolve_department_names` |

---

## 3. 功能①：项目规范 —— 新建 / 改写

「产出一个符合 Guard 子应用规范的源码目录」。两条路径 + 一套共用校验。

### 3.1 从 0 到 1 新建（scaffold）

| 代码 | 职责 |
| --- | --- |
| `cmd_scaffold` | 从内置模板拷贝生成骨架，写 `.cowork.json` |
| `SCAFFOLD_TEMPLATES` | 支持的 4 个 profile（见下） |
| `_scaffold_templates_root` | 定位 `templates/` 目录 |
| `_scaffold_pack_keep` | 各模板 pack 时要保留的前端构建产物目录 |
| `_scaffold_copytree` | 拷贝并保留可执行位（install/start/health.sh 的 +x） |

**4 个模板**（`templates/<name>/`，与 `references/templates-ref/<name>.md` 一一对应）：
`fastapi-only` / `koa-monorepo` / `nextjs-fullstack` / `react-fastapi-monorepo`

**迭代提示**：加新模板 = ① `templates/<name>/` 加骨架 ② `references/templates-ref/<name>.md` 加说明 ③ `cowork.py` 的 `SCAFFOLD_TEMPLATES` + `_scaffold_pack_keep` 同步 ④ SKILL.md 模板速查表同步。四处必须一致。

### 3.2 改写存量工程（transform）

| 代码 | 职责 |
| --- | --- |
| `cmd_transform`（cowork.py） | thin wrapper，`subprocess` 调 `transform/transform.sh` |
| `transform/transform.sh` | 入口 shell：选模型 / 登录预检 → `exec bin/guardx transform` |
| `transform/bin/guardx` | shim：设 `GUARD_TRANSFORM_HOME` + `PYTHONPATH` → `python3 -m guardx` |
| `transform/guardx/cli.py` | guardx CLI（子命令：transform/detect/verify/pack/logs/stop/status/clean/change-model） |
| `transform/guardx/pipeline.py` | 编排 8 个 stage |
| `transform/guardx/stages_py/stage_NN_*.py` | 流水线各阶段 |
| `transform/profiles/*.json` | 5 个技术栈 profile（含 flask-only，按 `match` 匹配存量工程） |
| `transform/prompts/*.md` | 各改写步骤的 LLM prompt |
| `transform/templates/*.tpl` | 渲染 install/start/health 脚本的模板 |
| `transform/verifiers/verify_*.sh` | 30 个硬校验脚本 |

**8 阶段流水线**（`pipeline.py` 的 `STAGES`）：
`00_prepare → 10_detect_stack → 20_rewrite_loop → 30_render_scripts → 40_build → 50_smoke_test → 60_package → 70_report`

**迭代提示**：
- 改改写策略 → 动对应 `stage_NN_*.py` + 对应 `prompts/`
- 加新技术栈支持 → 加 `profiles/<name>.json`（靠 `match` 字段匹配，`name` 仅标识）
- 加新红线校验 → 加 `verifiers/verify_*.sh`，并在 `stage_50_smoke_test.py` 的 verifier 列表里登记

> 注意：scaffold（新建）和 transform（改写）是**两套独立的模板体系**——scaffold 用根 `templates/`，transform 用 `transform/templates/*.tpl` + `profiles/`。命名相近但互不复用。

### 3.3 共用校验（红线）

| 代码 | 校验内容 |
| --- | --- |
| `precheck_zip` / `precheck_dir` | install/start/health 三件套、端口、build 产物 |
| `_check_sso_compliance` / `_scan_sso_backdoor` | 强制 SSO 接入 + 拦截 bypass 后门 |
| `_check_db_properties_keys` | db.properties key 白名单（只允许 6 个 key） |
| `_run_transform_verifiers` | 复用 transform 的 3 个核心 verifier（db/ai/sso）作硬卡层 |

---

## 4. 功能②：部署 / 轮询 / 发布

「把源码送上 Cowork 平台并对外可访问」。底层是 5 步全链路，上层是几个组合命令。

### 4.1 底层 5 步（API 封装，可被复用 import）

| 代码 | 职责 | 对应 API |
| --- | --- | --- |
| `pack_dir` | 打包源码成 zip（剥 node_modules/.next 等，按 manifest `pack.keep` 保留产物） | — |
| `get_permit` + `ros_put` + `upload_file` | 上传 zip/封面到 OSS | edith permit + PUT ROS |
| `deploy_zip` | 触发部署 | `POST works/deploy` |
| `deployment_status` + `wait_deploy` | **轮询**部署状态机 UPLOADING→INSTALLING→STARTING→RUNNING | `GET deployment/{id}/status` |
| `save_work` | 创建/更新作品记录 | `POST works/save` |
| `_emit_progress` | 向上游 stream 部署进度（`PROGRESS:{json}` 行） | — |

### 4.2 组合命令

| 命令 | 代码 | 说明 |
| --- | --- | --- |
| `publish` | `cmd_publish` | 一键：pack → deploy → wait → 上传封面 → save → 写 manifest |
| `deploy` | `cmd_deploy` | 只部署不创建作品（quick test） |
| `save-after-deploy` | `cmd_save_after_deploy` | deploy 后单独补 save（三段式发布的 step-3） |
| `status` | `cmd_status` | 单独查部署状态 |
| `redeploy` | `cmd_redeploy` | 改代码后重部署，保留 alias、自增版本 |
| `upload` | `cmd_upload` | 裸上传文件 |

**迭代提示**：Cowork API 协议变更 → 改 `cowork.py` 顶部 endpoint 常量区（`COWORK_API` / `EDITH_HOST` 等）+ 对应底层函数。

---

## 5. 功能③：作品管理（别名 / 可见性 / 元信息）

作品发布后的管理操作，不重新部署代码。

| 命令 | 代码 | 职责 | API |
| --- | --- | --- | --- |
| `set-alias` | `cmd_set_alias` + `set_deployment_alias` | 改自定义域名后缀 | `PUT deployment/{id}/alias` |
| `set-visibility` | `cmd_set_visibility` | 改可见范围（UI 专用） | — |
| `update` | `cmd_update` | 改标题/简介/封面/标签/可见性/alias | `POST works/save` |
| `delete` | `cmd_delete` | 删作品 | `POST works/delete` |
| `detail` | `cmd_detail` | 查作品详情 | `GET works/{id}` |

**支撑逻辑**：`normalize_visibility` + `VISIBILITY`（self/partial/all ↔ 后端枚举，含新旧名兼容）、`ALIAS_REGEX`（alias 格式）、`SCENE_TAGS`（标签中英映射）、`cowork_app_url`（workId → 作品管理页 URL 混淆编码）。

**安全约束**：CLI 层硬拒绝"放大可见范围"（self → partial/all），引导用户去 Cowork Studio Web 端手动改。见 `cmd_update` 里的 visibility 拦截。

---

## 6. 功能④：本地数据联动（manifest / memory / ID）

**把平台返回的 ID 和元信息落盘到本地固定位置，并维护本地↔远端一致性。** 这是各命令共用的底座。

### 6.1 项目 manifest（`.cowork.json`）

| 代码 | 职责 |
| --- | --- |
| `MANIFEST_FILENAME` = `.cowork.json` / `COWORK_PROJECT_SCHEMA` | 文件名 + schema 版本 |
| `_manifest_path` / `_load_manifest` / `_save_manifest` | 读写（原子写 .tmp→replace） |
| `_ensure_manifest` | 创建/更新，兜底 schema/id/时间戳 |
| `_new_project_id` | 生成 projectId（`cw_proj_xxx`） |

**manifest 维护的 ID/元信息**：`id`(projectId) / `srcDir` / `name` / `stack` / `pack.keep` / `cowork.workId` / `cowork.alias` / `cowork.accessUrl` / `cowork.deploymentId` / `cowork.visibility` / `cowork.version` 等。

### 6.2 路径约定

| 常量 | 路径 | 用途 |
| --- | --- | --- |
| `COWORK_PROJECT_ROOT` | `~/.openclaw/workspace/cowork/` | 所有项目根目录约定 |
| `LEGACY_PROJECT_ROOT` | `~/.openclaw/workspace/code/` | 历史兼容 |
| `_diag_log_path` | `/tmp/cowork-publish-*.log` | 诊断日志（publish hang 排查用） |

### 6.3 项目 memory（决策记录）

| 代码 | 职责 |
| --- | --- |
| `_memory_init` / `_memory_append` | 写 memory.md（关键决策/已知问题/避坑教训/发布历史） |
| `_ensure_memory_link` / `_memory_link_path` | 集中索引到 `~/memory/cowork-memory/<slug>.md` |
| `_memory_index_refresh` | 刷新 INDEX |
| `cmd_memory`（list/show/append） | memory CLI |

### 6.4 本地↔远端连接

| 命令 | 代码 | 职责 |
| --- | --- | --- |
| `list-projects` | `cmd_list_projects` + `_lp_*` | 扫本地 manifest + 拉远端作品 merge，3 状态（🟢published/🟡local-only/🔵cowork-only） |
| `list-my-apps` | `cmd_list_my_apps` | 只拉远端已发布作品 |
| `list` | `cmd_list` | 旧接口（新代码用 list-my-apps） |
| `link` | `cmd_link` | 把已发布作品 link 回本地 srcDir，回填 manifest |
| `_find_manifest_by_work_id` | — | 按 workId 反查本地项目 |

> **关键同步副作用**：`set-alias` / `update` / `redeploy` 成功后会自动回写 `.cowork.json` + `memory.md`，保持本地元信息与平台一致。改这些命令时务必保留同步逻辑。

---

## 7. 功能⑤：组织架构查询

给「部门/人员可见性」配置做辅助（查 userId / departmentId）。

| 命令 | 代码 | 职责 |
| --- | --- | --- |
| `search-users` | `cmd_search_users` | 员工搜索（EHR findUserInfoByValue） |
| `search-contacts` | `cmd_search_contacts` | 部门+人员+群聊混合搜索（redcity 网关） |
| `resolve-department-names` | `cmd_resolve_department_names` | 按 ID 反查部门名字+路径 |

---

## 8. 鉴权 / 运行环境

| 代码 | 职责 |
| --- | --- |
| `session` / `load_cookies` | requests session；pod 内走 forward proxy 自动注入 SSO cookie，本地需 `COWORK_COOKIE` |
| `api_call` | 统一 cowork API 调用（含超时、错误处理） |
| `_VERIFY_SSL` | `COWORK_VERIFY_SSL=1` 开启 TLS 校验（pod 内默认关，proxy 自签） |
| `__version__` / `_read_skill_version` | 版本号单一真相源：读 SKILL.md frontmatter 的 `version` |

---

## 9. 迭代时的「动哪里」速查

| 想改什么 | 动哪里 |
| --- | --- |
| Cowork API 协议适配 | `cowork.py` 顶部 endpoint 常量区 + 对应底层函数 |
| 加 scaffold 新模板 | `templates/` + `templates-ref/` + `SCAFFOLD_TEMPLATES` + `_scaffold_pack_keep` + SKILL.md（四处同步） |
| 改 transform 改写策略 | `transform/guardx/stages_py/stage_NN_*.py` + 对应 `transform/prompts/` |
| 加 transform 技术栈 | `transform/profiles/<name>.json`（靠 match 匹配） |
| 加 / 改红线校验 | `transform/verifiers/verify_*.sh` + `stage_50_smoke_test.py` 登记；precheck 侧改 `precheck_*` / `_run_transform_verifiers` |
| 改可见性枚举 | `VISIBILITY` / `VISIBILITY_LEGACY` / `normalize_visibility` |
| 改标签 | `SCENE_TAGS` |
| 改 manifest 字段 | `_ensure_manifest` + 各命令的 manifest 回写块 |
| 改公开 agent 行为 | `SKILL.md`（必 bump frontmatter version） |
| 版本号 | 只改 `SKILL.md` frontmatter 的 `version`，其余自动跟随 |
```
