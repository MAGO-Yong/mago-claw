# Cowork API 完整参考（2026-05-18 帝江实测抓包）

## 鉴权

- 所有请求走 SSO cookie（`web_session` 等）
- OpenClaw pod 出口的 forward proxy 自动注入
- 浏览器手工抓的话从 `https://cowork.xiaohongshu.com` 任意页面 devtools 拷
- TLS：pod 内 MITM 自签，CLI 默认 `verify=False`

## Host

| host | 用途 |
|------|------|
| `https://city.xiaohongshu.com/oasis/api/oa-office/cowork` | cowork 业务接口（创建/部署/查询） |
| `https://edith.xiaohongshu.com` | 上传 token 获取 |
| `https://ros-upload.xiaohongshu.com` | 实际 PUT 上传（小红书自研对象存储 ROS） |
| `https://ros-preview.xhscdn.com` | 上传后的 CDN preview URL |
| `https://cowork.xiaohongshu.com/s/<alias-or-appId>/` | 部署完成后的访问入口 |

---

## 1. 上传文件（两段式）

### 1.1 拿 permit

```
GET https://edith.xiaohongshu.com/api/media/v1/upload/web/permit
  ?bizName=ep
  &scene=oa_attachments
  &fileCount=1
  &biz_name=ep
  &file_format=zip          # 文件后缀（zip / png / jpg）
  &file_count=1
  &version=1
  &subsystem=web_resource   # ⚠️ 必填，否则 "old channel closed"
  &_t=<ms>__<rand>          # 防缓存
```

响应：
```json
{
  "code": 0,
  "success": true,
  "data": {
    "result": {"success": true},
    "uploadTempPermits": [{
      "cloudType": 4,
      "region": "unknown",
      "fileIds": ["oa_attachments/KXXp...zip"],
      "token": "MfusYd41IAHb8-uZ...",
      "uploadAddr": "ros-upload.xiaohongshu.com",
      "expireTime": 1779192390860,
      "qos": 1,
      "bucket": "unknown",
      "uploadId": 446
    }]
  }
}
```

### 1.2 PUT 上传

```
PUT https://<permit.uploadAddr>/<permit.fileIds[0]>
Headers:
  Content-Type: application/zip (或对应 MIME)
  X-Cos-Security-Token: <permit.token>
  Authorization: <permit.token>   # 双保险
Body: 文件原始字节
```

成功后 `fileIds[0]` 就是后续要用的 fileId（形如 `oa_attachments/<hash>.zip`）。

---

## 2. 部署 zip

### 2.1 触发

```
POST https://city.xiaohongshu.com/oasis/api/oa-office/cowork/community/works/deploy
Content-Type: application/json

{
  "fileIdJson": "{\"fileId\":\"oa_attachments/xxx.zip\",\"business\":\"ep\",\"scene\":\"oa_attachments\",\"name\":\"app.zip\"}",
  "deploySource": "SEAL",
  "extPlatformId": "cw_proj_xxxxxxxx",
  "workId": 449
}
```

⚠️ `fileIdJson` 是字符串化的 JSON，**不是嵌套对象**。

Seal 链路额外必填/优选：
- `deploySource=SEAL`（区分原 cowork web 链路 `COWORK`）
- `extPlatformId`：Seal 侧项目唯一 ID，顶层 `.cowork.json.id`（`cw_proj_xxx`）。后端拿这个跨部署记录关联
- `workId`：重发布 / 发布新版本时传，后端会复用原 alias，免 save
- `deploymentId`：同一部署记录 retry

响应：
```json
{
  "alertMsg": "操作成功",
  "data": {
    "deploymentId": 267,
    "deploymentStatus": "UPLOADING",
    "appId": null,
    "accessUrl": null,
    "rawAccessUrl": null,
    "realPath": null,
    "alias": null,
    "errorMessage": null,
    "workId": null
  },
  "success": true
}
```

### 2.2 轮询状态

```
GET https://city.xiaohongshu.com/oasis/api/oa-office/cowork/community/works/deployment/<deploymentId>/status
```

状态机：
- `UPLOADING` → zip 在传到平台
- `INSTALLING` → 跑 install.sh
- `STARTING` → 跑 start.sh
- `RUNNING` → 健康检查通过，可访问
- `FAILED` → errorMessage 是日志尾巴

每 2 秒轮一次即可，平均 15-30s 进 RUNNING。

成功响应：
```json
{
  "data": {
    "deploymentId": 267,
    "deploymentStatus": "RUNNING",
    "appId": "635f401c",
    "accessUrl": "https://cowork.xiaohongshu.com/s/635f401c/",
    "rawAccessUrl": "https://cowork.xiaohongshu.com/s/635f401c/",
    "realPath": "635f401c"
  }
}
```

注意此时 `alias=null`，`accessUrl` 是 raw appId 形式。要拿自定义后缀，必须在 `save` 时传 `deploymentAlias`。

---

## 3. 保存作品

```
POST https://city.xiaohongshu.com/oasis/api/oa-office/cowork/community/works/save
Content-Type: application/json

{
  "name": "狗腿子海豹掷骰子",
  "imagesJson": "[{\"fileId\":\"oa_attachments/xxx.jpg\",\"business\":\"ep\",\"scene\":\"oa_attachments\",\"name\":\"cover.jpg\",\"mimeType\":\"image/jpeg\",\"url\":\"https://ros-preview.xhscdn.com/...\",\"type\":\"cover\"}]",
  "sceneTagsJson": "[\"efficiency_improvement\"]",
  "version": "1.0",
  "visibilityScope": "SELF_ONLY",
  "oneLineIntro": "...",
  "description": "...",
  "linksJson": "[{\"title\":\"...\",\"url\":\"https://cowork.xiaohongshu.com/s/seal-dice\"}]",
  "notifyOnPublish": false,
  "workType": "SEAL_DEPLOY",
  "displayInCommunity": false,
  "deploymentId": 267,
  "deploymentAlias": "seal-dice"
}
```

字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 作品标题（必填） |
| `imagesJson` | str(JSON 数组) | 至少 1 张图，第一张 `type:"cover"`；图片走步骤 1 上传，url 是 permit 返回值的 preview |
| `sceneTagsJson` | str(JSON 数组) | enum：efficiency_improvement / content_generation / data_analysis / research_insight / communication_collaboration / code_development / design_creativity / other |
| `version` | str | "1.0" |
| `visibilityScope` | str | `PUBLIC` / `DEPARTMENTS` / `SELF_ONLY`（旧名 `ALL` / `PARTIAL` / `SELF_ONLY` 后端调整后不再接受，CLI 不论传旧名还是新名 normalize_visibility 会自动转成新名） |
| `visibleUserIds` | str[] | visibilityScope=DEPARTMENTS 时与 visibleDepartmentIds 至少填一；SELF_ONLY 时传了会报错 |
| `visibleDepartmentIds` | str[] | 同上。更新作品时 不沿用原值，必须同时传 `visibilityScope` + 这两个列表 |
| `oneLineIntro` | str | 一句话简介（最长 512，可空） |
| `description` | str | 详细描述（可空） |
| `linksJson` | str(JSON 数组) | 相关链接 `[{title, url}]`，最多 10 条 |
| `notifyOnPublish` | bool | 是否通知关注者（默认 true，新建时传） |
| `workType` | str | **Seal 链路固定 `SEAL_DEPLOY`**；`EXTERNAL_RESOURCE`（默认，外链）；`COWORK_DEPLOY`（原 cowork web zip 部署） |
| `displayInCommunity` | bool | **Seal 链路固定 `false`**；其他类型 `true` |
| `deploymentId` | int | 步骤 2 返回的 ID，**仅 SEAL_DEPLOY / COWORK_DEPLOY 时传** |
| `deploymentAlias` | str | 自定义 URL 后缀，3-32 位小写字母/数字/-，不填走 appId |
| `id` | int | 已存在的 workId（更新模式） |

响应：
```json
{"alertMsg":"操作成功","data": 426 /* workId */, "success": true}
```

---

## 4. 查询

### 我的作品

```
GET cowork/community/user-profile/works?email=<email>&tab=recent
```

`tab` 可选 `recent` / `all`。

### 作品详情

```
GET cowork/community/works/<workId>
```

返回完整字段，包括 deploymentAccessUrl / deploymentAppId / deploymentAlias / imagesJson / linksJson 等。

### 部署历史

```
GET cowork/community/works/deployment/<deploymentId>/status
```

---

## 5. 删除

```
POST cowork/community/works/delete
Content-Type: application/json

{"id": 426}
```

---

## 6. 重新部署（更新已发作品）

流程：
1. 上传新 zip → 拿 fileId
2. POST `community/works/deploy` 拿新 deploymentId
3. 轮询到 RUNNING（appId 可能变 alias 不变？需进一步验证）
4. POST `community/works/save` 带原 workId + 新 deploymentId + 原 alias

---

## 7. 拿规范 prompt

```
GET cowork/community/works/transform/prompt
```

返回：
```json
{
  "data": {
    "downloadUrl": "https://ep-redflow-s2.xhscdn.com/oa_attachments/.../eibumrm.md?sign=...&t=..."
  }
}
```

下载 markdown 即官方 guard 规范，可作为 LLM 改写 prompt 喂给 Claude/CodeWiz。

---

## 8. 已知未覆盖的接口

从 JS bundle 抓到但 CLI 尚未封装的：

- `community/works/editor-pick` — 编辑精选（管理员）
- `community/works/hot` — 热门作品
- `community/works/check-access/app/{appId}` — 访问权限校验
- `community/skills/save` / `community/skills/inspect` / `community/skills/updateArtifact` — Skill 类作品发布（不同于 COWORK_DEPLOY，可能是给 seal/cursor 用的 skill）
- `community/posts/*` — 讨论广场（feed/帖子）
- `community/comments/*` — 评论
- `community/link-resolve` — 解析 URL 元信息（标题/封面）
- `community/ranking/hot-builders` / `hot-works` — 排行榜

需要时再补到 CLI。
