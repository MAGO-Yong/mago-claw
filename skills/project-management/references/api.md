# aipmo API 参考

> 所有接口均通过 **browser** 访问（沙盒中 curl/requests 会超时）。
> BASE_URL = `https://aipmo.devops.xiaohongshu.com`

## 认证

| 接口类型 | 方式 |
|---------|------|
| `get` / `get-with-token` / `update` / `delete` | 传 `project_token` 参数 |
| `list` | 无需认证，后端通过 SSO 自动识别 |
| 无权限时 | 返回 `{ "success": false, "message": "无权限查看此项目配置" }` |

## 接口列表

### GET /api/project-config/get
查询单个项目配置。

参数：`project_name`（支持智能匹配）、`project_token`（必填）

返回关键字段：
- `data.projectName` — 项目名称
- `data.redocUrl` — RedDoc 文档地址
- `data.redocSpaceUrl` — RedDoc 空间地址
- `data.hiGroupId` — Hi 群聊 ChatID
- `data.projectOwnerId` — 项目负责人 ID
- `data.createdBy` — 配置创建者邮箱

智能匹配：先精确查，未命中自动加/去"项目"后缀重试。

---

### GET /api/project-config/list
列出所有项目（后端按 SSO 身份过滤，管理员可见全部）。

参数：`userId`（可选，管理员专用）

---

### GET /api/project-config/get-with-token
查询项目配置 + 获取负责人 UAT（自动刷新过期 token）。

参数：`project_name`、`project_token`（必填）

返回额外字段：
- `data.ownerInfo.accessToken` → UAT，用于后续 RedDoc 操作

---

### GET /api/account/email-by-redname
通过薯名/域账号名查工作邮箱。

参数：`red_name`（最少 2 个字符）

返回：`data[].accountMail`、`data[].name`、`data[].redName`、`data[].accountName`、`data[].displayName`（格式：`薯名(真名)`）、`data[].departmentNamePath`

反查域账号名时，用 `accountName === 传入值` 精确匹配。

---

## 通用前置步骤（先拿 UAT）

所有需要读 RedDoc 的场景，先执行：

```
browser navigate → {BASE_URL}/api/project-config/get-with-token
  ?project_name={项目名}&project_token={PROJECT_TOKEN}
```

提取：
- `data.projectConfig.redocUrl`
- `data.projectConfig.redocSpaceUrl`
- `data.projectConfig.hiGroupId`
- `data.ownerInfo.accessToken`（UAT）

## 错误处理

| 场景 | 返回 | 处理 |
|------|------|------|
| 项目不存在 | `data: null` | 提示检查名称；若 list 也无，引导至 aipmo 平台配置 |
| 无权限 | `success: false` + 无权限 message | 提示无权限 |
| 服务异常 | `success: false` | 提示稍后重试 |
