---
name: ones-assistant
description: "ones 发布平台操作助手。当用户需要进行以下操作时触发：查询有权限的应用/服务、查看服务部署组信息、查询可用镜像版本、查询或浏览发布流程模板、触发 SIT 或 staging 环境发布、查询发布进度或发布详情、查询发布历史、查询 Pod 状态、诊断发布卡住或异常、查询我的发布列表。Use when: deploying services to ones platform, checking deploy status, querying workload groups, browsing image tags, or diagnosing deploy failures."
---

# ones 发布平台操作助手

## Overview

本 skill 封装了 ones 发布平台的所有 Agent Tool 接口，支持从服务查询、镜像选择、发布创建，
到发布状态追踪和异常诊断的完整发布闭环。

所有操作通过调用 Python 脚本 `scripts/ones_deploy.py` 完成，
脚本调用 `https://ones.devops.xiaohongshu.com/api/v1/x/a/tools/{tool_name}` 接口，
认证由框架层自动注入，用户身份从登录态自动获取。

---

## 工具手册

详细接口参数和返回字段说明见 `references/tools.md`。

---

## 工作流

### 0. 场景识别

| 用户意图 | 推荐子命令 |
|----------|-----------|
| 查我有权限的应用 | `my-apps` |
| 查我有权限的服务 | `my-services` |
| 查服务部署组 | `service-info <service>` |
| 查可发布的镜像 | `images <service>` |
| 查发布流程模板 | `changeflows <service>` |
| 发布到 sit/staging | `deploy <service> --changeflow ... --workload-groups ... --tag ...` |
| 查发布进度/详情 | `deploy-info <changeflowName>` |
| 查我的发布列表 | `my-changeflows` 或 `my-changeflows-by-app <app>` |
| 查发布历史 | `deploy-history <service> <wg>` |
| 查 Pod 状态 | `pod-info <service> <wg>` |
| 发布卡住/失败排查 | `diagnose <changeflowName>` |

---

### 1. 完整发布流程编排

当用户发起发布请求时，按以下步骤执行：

#### Step 1 — 确认服务权限

```bash
python scripts/ones_deploy.py my-services
```

解析返回列表，确认目标服务存在且用户有权限。若服务不在列表中，告知用户无权限并停止。

#### Step 2 — 选择发布镜像

```bash
python scripts/ones_deploy.py images <service>
```

展示可用 tag 列表（按时间倒序），询问用户选择哪个版本，或根据上下文（如用户提到 commit/版本号）自动匹配。

#### Step 3 — 查询发布流程模板

```bash
python scripts/ones_deploy.py changeflows <service>
```

返回 `changeflowInfoName`（模板名）及其关联的 `workloadGroups`（部署组列表）。
若用户未指定模板，展示列表供用户选择；若只有一个模板，可自动选择。

#### Step 4 — 校验部署组发布状态

```bash
python scripts/ones_deploy.py check <service> <wg1> [<wg2> ...]
```

校验各部署组的发布状态，返回可发布 / 正在发布 / 需要审批 / 首次发布的部署组分类列表。

#### Step 5 — 用户确认并创建发布

```bash
python scripts/ones_deploy.py deploy <service> \
  --changeflow <changeflowInfoName> \
  --workload-groups <wg1> [<wg2> ...] \
  --tag <imageTag> \
  [--description "发布描述"]
```

脚本会展示发布参数并要求用户输入 `y` 确认。
若在非交互场景（模型已代用户确认），可加 `--yes` 跳过提示。

脚本返回包含 `changeflowName` 和 ones 页面 `link` 的 JSON。

#### Step 6 — 轮询发布进度（可选）

```bash
python scripts/ones_deploy.py deploy-info <changeflowName>
```

可定期调用查询发布进度，直到 `status` 为 `success` 或 `failed`。
将 ones 页面链接提供给用户，供其在 ones 平台查看实时进度。

#### Step 7 — 发布异常时诊断

```bash
python scripts/ones_deploy.py diagnose <changeflowName>
```

返回各阶段状态、Pod YAML 和日志摘要，帮助定位发布卡住或失败的原因。

---

### 2. 发布环境说明

- ones 后端负责发布环境安全校验，线上环境发布需要通过 ones 平台审批流程。
- 部署组命名规则：
  - `{zone}.{serviceName}` → sit 环境
  - `{zone}.{serviceName}.staging` → staging 环境
  - `{zone}.{serviceName}.{laneName}` → 泳道环境

---

### 3. 纯查询操作（无需发布确认）

以下操作只读，可直接执行：

```bash
# 查我有权限的应用
python scripts/ones_deploy.py my-apps

# 查我有权限的服务
python scripts/ones_deploy.py my-services

# 查应用详情（含所有服务和部署组）
python scripts/ones_deploy.py app-info <appName>

# 查服务部署组
python scripts/ones_deploy.py service-info <service>

# 查我最近的发布列表
python scripts/ones_deploy.py my-changeflows

# 查我在某应用下的发布列表
python scripts/ones_deploy.py my-changeflows-by-app <appName>

# 查发布历史
python scripts/ones_deploy.py deploy-history <service> <workloadGroup>

# 查 Pod 状态
python scripts/ones_deploy.py pod-info <service> <workloadGroup>
```

---

## 输出格式

所有子命令均输出 JSON（标准输出），供模型解析。
错误和状态信息输出到 stderr（`[INFO]` / `[WARN]` / `[ERROR]` 前缀）。

---

## 注意事项

1. **用户身份自动注入**：所有涉及"当前用户"的接口（如 my-apps、my-services、my-changeflows）
   无需传入用户参数，ones 框架从登录态自动获取。

2. **发布确认**：`deploy` 子命令默认会展示参数并等待用户确认（输入 `y`），
   模型代用户决策时可加 `--yes` 跳过。在未获得用户明确意图前，**不要自动加 `--yes`**。

3. **changeflowName vs changeflowInfoName**：
   - `changeflowInfoName`：发布流程**模板**名，固定不变，来自 `changeflows` 子命令
   - `changeflowName`：发布流程**实例**名，每次发布生成新的，来自 `deploy` 返回值

4. **发布历史查询**：`deploy-history` 可不传 `--image-tag`，返回全部历史；
   传入 tag 可过滤特定版本的发布记录。

5. **不支持 shadow 发布**：当前 ones-assistant 暂不支持 shadow 发布，请勿尝试触发。
   如有 shadow 发布需求，请前往 ones 平台手动操作。

6. **遇到 agent-platform 未识别错误**：若调用接口时提示 agent-platform 未识别或相关鉴权失败，
   说明当前 REDLobi 版本尚未适配本 skill，请联系 REDLobi 负责同学升级 REDLobi 版本后再试。
