# XRay Exception & Logview API 规范

## 目录

1. [基础信息与鉴权](#基础信息与鉴权)
2. [接口一：/stack/cluster — 异常堆栈聚类分析](#接口一stackcluster--异常堆栈聚类分析)
3. [接口二：/sample — 错慢请求采样 MessageId](#接口二sample--错慢请求采样-messageid)
4. [接口三：/{messageId}/json — Logview 详情查询](#接口三messageidjson--logview-详情查询)
5. [响应数据结构](#响应数据结构)

---

## 基础信息与鉴权

- **Base URL**: `https://xray.devops.xiaohongshu.com`
- **接口前缀**: `/openapi/application/r`
- **完整前缀**: `https://xray.devops.xiaohongshu.com/openapi/application/r`

### 鉴权：xray_ticket

所有接口均通过 HTTP Header `xray_ticket` 鉴权，值为 Base64 编码的字符串。

**生成规则**:
```
ticket = Base64("{source}&{token}&{timestamp_ms}")
```

| 参数 | 说明 |
|------|------|
| `source` | 来源标识，不能为空（固定填 `codewiz`） |
| `token` | 在 XRay 平台申请并审批后的 token（向用户询问） |
| `timestamp_ms` | 当前毫秒时间戳，ticket 有效期约 3 分钟，每次请求自动重新生成 |

**Python 生成示例**:
```python
import base64, time
source, token = "codewiz", "<用户提供的token>"
raw = f"{source}&{token}&{int(time.time() * 1000)}"
ticket = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
# headers["xray_ticket"] = ticket
```

### 统一响应包装

```json
{
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

---

## 接口一：/stack/cluster — 异常堆栈聚类分析

**完整 URL**: `POST https://xray.devops.xiaohongshu.com/openapi/application/r/p/stack/cluster`

**功能**: 对指定服务、时间范围内的一批异常类型进行聚类分析，返回每种异常的堆栈分布（按出现比例降序），并附带关联的 messageId 列表。

### 请求体

```json
{
  "app": "your-service-name",
  "start": 1700000000,
  "end":   1700003600,
  "exceptions": [
    "java.util.concurrent.TimeoutException",
    "java.net.SocketTimeoutException"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app` | string | 是 | 服务 appkey |
| `start` | long | 是 | 开始时间，**秒级 Unix 时间戳** |
| `end` | long | 是 | 结束时间，**秒级 Unix 时间戳** |
| `exceptions` | string[] | 是 | 异常类全名列表 |

### 响应

```json
{
  "code": 0,
  "data": {
    "exceptions": [
      {
        "exception": "java.util.concurrent.TimeoutException",
        "tags": [
          {
            "hash": 123456789,
            "count": 450,
            "ratio": 0.75,
            "stack": "java.util.concurrent.TimeoutException: ...\n\tat com.example...",
            "type": "clustering",
            "messageIds": ["svc-abc123-1700001234", "svc-def456-1700001235"]
          }
        ]
      }
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `exception` | 异常类全名 |
| `tags[].hash` | 堆栈指纹，同 hash 代表同一根因 |
| `tags[].count` | 该堆栈在时间窗口内的出现次数 |
| `tags[].ratio` | 占该异常总数的比例（0~1），按此字段降序排列 |
| `tags[].stack` | 完整堆栈字符串 |
| `tags[].type` | 固定为 `"clustering"` |
| `tags[].messageIds` | 关联的 CAT messageId 列表，可传入接口三查 Logview |

### 注意事项

- 若某异常无聚类数据，该异常不出现在响应中
- `messageIds` 可能为空列表

---

## 接口二：/sample — 错慢请求采样 MessageId

**完整 URL**: `GET https://xray.devops.xiaohongshu.com/openapi/application/r/t/sample`

**功能**: 根据服务名、接口 type/name、时间范围，获取一个具有代表性的采样 messageId。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app` | string | 是 | 服务 appkey |
| `type` | string | 是 | Transaction 类型（接口分类前缀，见下表） |
| `name` | string | 否 | 具体接口名称，为空时查该 type 下聚合 |
| `ip` | string | 是 | 机器 IP，无特殊需求传 `ALL` |
| `zone` | string | 否 | 机房，不传或传 `ALL` 表示全机房 |
| `startTime` | long | 是 | 开始时间，秒级 Unix 时间戳 |
| `endTime` | long | 是 | 结束时间，秒级 Unix 时间戳 |
| `sampleType` | string | 是 | `fail` / `longest` / `success` |

### type 参数速查表

| 接口类型（用户描述） | `type` 值 | `name` 示例 |
|---------------------|-----------|------------|
| RPC 接口（服务端被调用） | `Service` | `UserService.getUserById` |
| HTTP 接口 | `URL` | `/api/v1/user/info` |
| RPC 客户端调用 | `Call` | `UserService.getUserById` |
| Redis 操作 | `Redis.<集群名>` | `GET` / `SET` |
| MySQL 操作 | `SQL` | `user.select` |

### sampleType 说明

| 值 | 含义 | 适用场景 |
|----|------|---------|
| `fail` | 随机一条失败请求 | 排查错误原因 |
| `longest` | 耗时最长的请求 | 排查慢请求根因 |
| `success` | 最新的成功请求 | 对比正常链路 |

### 响应

```json
{
  "code": 0,
  "data": "svc-name-abc123-1700001234"
}
```

`data` 为 messageId 字符串，若为 `null` 表示该时段无采样数据。

---

## 接口三：/{messageId}/json — Logview 详情查询

**完整 URL**: `GET https://xray.devops.xiaohongshu.com/openapi/application/r/logview/{messageId}/json`

**功能**: 根据 CAT messageId 查询完整的请求调用链。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `{messageId}` | string | 是 | 路径参数，CAT messageId |
| `startTime` | long | 否 | 当前版本未实际使用 |
| `endTime` | long | 否 | 当前版本未实际使用 |

### 响应

```json
{
  "code": 0,
  "data": {
    "domain": "your-service-name",
    "hostName": "pod-abc123",
    "ipAddress": "10.x.x.x",
    "zone": "sh001",
    "startTime": "2024-01-01 12:00:00.000",
    "durationInMills": 1234,
    "messageId": "svc-abc123-1700001234",
    "parentMessageId": "upstream-svc-xyz-1700001234",
    "rootMessageId": "entry-svc-000-1700001234",
    "traceId": "abc123def456",
    "code": 200,
    "message": {
      "type": "Service",
      "name": "UserService.getUserById",
      "status": "0",
      "timestamp": 1700001234000,
      "durationInMillis": 1234,
      "error": false,
      "data": "",
      "children": [
        {
          "type": "Call",
          "name": "OrderService.getOrders",
          "status": "0",
          "durationInMillis": 500,
          "error": false,
          "children": []
        },
        {
          "type": "Error",
          "name": "java.util.concurrent.TimeoutException",
          "status": "ERROR",
          "durationInMillis": -1,
          "error": true,
          "data": "java.util.concurrent.TimeoutException: ...\n\tat ..."
        }
      ]
    }
  }
}
```

### data.code 含义

| code | 含义 |
|------|------|
| 200  | 成功 |
| 1003 | 数据缺失（在保留期内未找到） |
| 1004 | 数据已过期归档 |

### MessageDTO 关键字段

| 字段 | 说明 |
|------|------|
| `type` | 消息类型（Service/Call/URL/SQL/Redis.xxx/Error 等） |
| `name` | 接口名或异常类名 |
| `status` | `"0"` 成功，其他失败 |
| `durationInMillis` | 耗时（ms），`-1` 表示 Event 类型（无耗时） |
| `error` | `true` 表示异常节点（type 为 Error/RuntimeException/Exception） |
| `data` | 异常节点时为完整堆栈；Call 节点可能含 `slaLevel=X&strongDependence=true` |
| `children` | 子调用列表，递归结构 |

### messageType 判断

- `durationInMillis >= 0` → transaction（有耗时的调用）
- `durationInMillis == -1` → event（瞬时事件，如异常上报）

---

## 响应数据结构

### ProblemStackVO（接口一响应 data）

```
ProblemStackVO
└── exceptions: ExceptionStackVO[]
    ├── exception: string         // 异常类全名
    └── tags: StackVO[]           // 按 ratio 降序
        ├── hash: long            // 堆栈指纹
        ├── count: long           // 出现次数
        ├── ratio: double         // 占比 (0~1)
        ├── stack: string         // 堆栈文本
        ├── type: string          // "clustering"
        └── messageIds: string[]  // 关联 messageId 列表
```

### LogViewDTO（接口三响应 data）

```
LogViewDTO
├── domain / hostName / ipAddress / zone
├── startTime: string             // "yyyy-MM-dd HH:mm:ss.SSS"
├── durationInMills: long         // 总耗时(ms)
├── messageId / parentMessageId / rootMessageId / traceId
├── code: int                     // 200 / 1003 / 1004
└── message: MessageDTO           // 调用树根节点
    ├── type / name / status / timestamp / data / error
    ├── durationInMillis: long    // -1 = Event
    └── children: MessageDTO[]    // 递归
```
