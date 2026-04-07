# ones Agent Tool 接口手册

## 接口规范

- **Base URL**: `https://ones.devops.xiaohongshu.com`
- **发布路由**: `POST /api/v1/x/a/tools/{tool_name}`
- **Request Body**: `{ "arguments": { ...参数字段 } }`
- **认证**: Cookie 和 Agent-Platform 由框架层自动注入，调用方无需处理
- **列出所有 tool**: `GET /api/v1/x/a/tools`

---

## 权限查询类

### get_applications_with_permission_by_user

查询当前登录用户有权限的应用列表。

- **参数**: 无（用户身份由框架自动注入）
- **返回**: 应用列表，每项包含 `appName`、`alias` 等字段

---

### get_services_with_permission_by_user

查询当前登录用户有权限的服务列表。

- **参数**: 无
- **返回**: 服务列表，每项包含 `serviceName`、`appName` 等字段

---

## 应用 / 服务信息类

### get_application_info_with_services

查询应用详情，含该应用下的所有服务及部署组信息。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| appName | string | 是 | 应用名 |

- **返回**: 应用信息对象，含 `services` 数组（每项含服务名、部署组列表）

---

### get_service_info

查询服务的部署组详细信息（zone、name、env、副本数等）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| service | string | 是 | 服务名 |
| application | string | 否 | 应用名，可从服务名第一段自动推断 |

- **返回**: 服务信息，含 `workloadGroups` 数组

---

### get_service_image_repo_info

查询服务可用的镜像版本列表（用于选择发布 tag）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| applicationChildName | string | 是 | 服务名（子应用名） |

- **返回**: 镜像版本列表，每项含 `tag`、`createTime` 等，按时间倒序排列

---

## 发布流程模板类

### get_changeflows_with_workload_groups_by_service

查询服务下的发布流程模板列表，及每个模板关联的部署组。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| applicationChildName | string | 是 | 服务名 |

- **返回**: changeflow 模板列表，每项含：
  - `changeflowInfoName`: 模板名（发布时使用）
  - `changeflowAlias`: 模板别名（人类可读）
  - `workloadGroups`: 关联的部署组列表

---

### check_workload_groups_for_changeflow

校验部署组发布前的状态，在创建发布前调用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| applicationChildName | string | 是 | 服务名 |
| workloadGroups | []string | 是 | 部署组名称列表 |

- **返回**:
  - `canDeploy`: bool，是否可以发布
  - `deploying`: bool，是否有正在进行的发布
  - `requireApproval`: bool，是否需要审批
  - `firstDeploy`: bool，是否为首次发布（会自动初始化）

---

## 发布操作类

### create_deploy_with_watch

创建发布流程实例并开启值守（监控发布进度）。

**注意**：ones 后端会对发布环境做安全校验，线上环境发布需经过审批流程。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| applicationChildName | string | 是 | 服务名 |
| changeflowInfoName | string | 是 | 发布流程模板名（来自 get_changeflows_with_workload_groups_by_service） |
| workloadGroups | []string | 是 | 目标部署组列表 |
| repoTag | string | 是 | 镜像 tag（来自 get_service_image_repo_info） |
| description | string | 否 | 发布描述 |

- **返回**: 发布流程实例信息，含：
  - `changeflowName`: 实例名，用于后续查询
  - `link`: ones 平台页面链接
  - 其他发布状态字段

---

## 发布查询类

### get_deploy_info_by_changeflow_name

根据发布流程实例名查询完整发布详情（状态、阶段、进度等）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| changeflowName | string | 是 | 发布流程实例名（create_deploy_with_watch 返回） |

- **返回**: 发布详情，含状态、各阶段执行情况、失败原因等

---

### list_changeflow_by_user

查询当前用户最近 7 天的发布流程列表。

- **参数**: 无（用户身份由框架自动注入）
- **返回**: 发布流程列表，每项含 `changeflowName`、`status`、`createTime` 等

---

### list_changeflow_by_user_and_app

查询当前用户在指定应用下的发布流程列表。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| appName | string | 是 | 应用名 |

- **返回**: 同 list_changeflow_by_user，过滤到指定应用

---

### get_deploy_history_by_workload_group_and_image_tag

查询指定部署组的发布历史记录。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| applicationChildName | string | 是 | 服务名 |
| workloadGroupName | string | 是 | 部署组名 |
| imageTag | string | 否 | 镜像 tag（可选，用于过滤特定版本的发布历史） |

- **返回**: 发布历史列表，每项含镜像版本、发布时间、发布人、状态等

---

## Pod / 工作负载类

### get_workload_group_workloads

查询部署组下的工作负载及 Pod 详情（副本数、健康状态、Pod IP 等）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| service | string | 是 | 服务名 |
| workloadGroupName | string | 是 | 部署组名 |

- **返回**: workload 列表，含 Pod 详情（IP、健康状态、镜像版本等）

---

## 诊断类

### check_step_pipelinerun_running_stages_status

诊断发布流程各阶段 / Pipeline 任务的运行状态，用于发布卡住或异常时排查。
返回内容含 Pod YAML、运行日志摘要等诊断信息。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| changeflowName | string | 是 | 发布流程实例名 |

- **返回**: 各阶段状态列表，含 `stageName`、`status`、`podYaml`、`logs` 等

---

## 完整发布流程推荐顺序

```
1. get_services_with_permission_by_user
   → 确认用户对目标服务有权限

2. get_service_image_repo_info
   → 选择要发布的镜像 tag

3. get_changeflows_with_workload_groups_by_service
   → 确认发布流程模板名和目标部署组

4. check_workload_groups_for_changeflow
   → 确认部署组状态（无正在进行的发布、无审批阻断）

5. create_deploy_with_watch           ← 需用户确认后执行
   → 创建发布，获取 changeflowName

6. get_deploy_info_by_changeflow_name  ← 可轮询查询进度
   → 查询发布状态直到完成

7. check_step_pipelinerun_running_stages_status  ← 发布异常时
   → 诊断卡住或失败的原因
```