# Xray 日志查询 API 参考

Base URL: `https://xray-ai.devops.xiaohongshu.com/open/skill/logging`

## 认证方式

所有请求需在 Header 中携带 `xray_ticket`，其值由以下三部分拼接后做 Base64 编码生成：

```
xray_ticket = Base64( app + "&" + token + "&" + currentTimeMillis )
```

| 字段                | 说明                                            |
| ------------------- | ----------------------------------------------- |
| `app`               | 调用方名称/来源标识，不能为空，后台会做来源校验 |
| `token`             | 在 XRay 平台申请并审批通过的 token              |
| `currentTimeMillis` | 当前毫秒时间戳，后台做时效性验证，务必现场生成  |

**Java 示例（官方）：**

```java
String app = "test";
String token = "abc";
long time = System.currentTimeMillis();
String encode = Base64.encodeBase64String((app + "&" + token + "&" + time).getBytes(StandardCharsets.UTF_8));
// Header: xray_ticket: {encode}
```

**Python 示例：**

```python
import base64, time
ticket = base64.b64encode(f"{app}&{token}&{int(time.time()*1000)}".encode()).decode()
# Header: xray_ticket: {ticket}
```

> 注意：ticket 含毫秒时间戳，有时效限制，**每次调用都必须现场生成**，不可复用。

日志表 ID（tid）固定为 `33`（application 应用日志表）。

---

## 接口一：查询日志数量分布（charts）

```
GET /api/v1/tables/33/charts
```

用于获取指定时间范围内的日志数量柱状图，也作为 `/logs`
接口的前置调用（系统会将 charts 结果存入缓存，帮助 logs 自动缩小时间查询范围，提升性能）。

### 请求参数（Query String）

| 参数            | 类型    | 必填 | 说明                                 |
| --------------- | ------- | ---- | ------------------------------------ |
| `query`         | string  | 是   | Lucene 语法查询条件，见下方语法说明  |
| `st`            | int64   | 是   | 开始时间，Unix 秒                    |
| `et`            | int64   | 是   | 结束时间，Unix 秒                    |
| `pageSize`      | float64 | 否   | 每页条数，默认 20                    |
| `page`          | uint32  | 否   | 页码，默认 1                         |
| `orderKeywords` | string  | 否   | 排序：`asc` 或 `desc`（默认 `desc`） |

### 响应示例

```json
{
  "code": 0,
  "data": {
    "histograms": [
      { "count": 120, "from": 1700000000, "to": 1700003600, "details": [
          {"key": "error", "color": "#E74C3C", "count": 30},
          {"key": "warn",  "color": "#F39C12", "count": 50},
          {"key": "info",  "color": "#2ECC71", "count": 40}
      ]},
      { "count": 85, "from": 1700003600, "to": 1700007200, "details": [...] }
    ],
    "count": 205,
    "query": "SELECT toStartOfInterval(...) AS f, level, COUNT(*) ..."
  },
  "msg": "ok"
}
```

| 字段         | 说明                                                                              |
| ------------ | --------------------------------------------------------------------------------- |
| `count`      | 时间范围内日志总数                                                                |
| `histograms` | 柱状图数组，每项含 `from`/`to`（Unix秒）、`count`、`details`（按 level 分色明细） |

---

## 接口二：查询日志详情（logs）

```
GET /api/v1/tables/33/logs
```

查询具体的日志条目列表。**建议先调用 `/charts` 再调用
`/logs`**，系统会利用 charts 的缓存结果自动缩小时间扫描范围。

### 请求参数（Query String）

| 参数             | 类型    | 必填 | 说明                                                    |
| ---------------- | ------- | ---- | ------------------------------------------------------- |
| `query`          | string  | 是   | Lucene 语法查询条件                                     |
| `st`             | int64   | 是   | 开始时间，Unix 秒                                       |
| `et`             | int64   | 是   | 结束时间，Unix 秒                                       |
| `page`           | uint32  | 否   | 页码，默认 1                                            |
| `pageSize`       | float64 | 否   | 每页条数，默认 20，最大 10000                           |
| `orderKeywords`  | string  | 否   | `asc` 或 `desc`（默认 `desc`）                          |
| `searchTraceApp` | bool    | 否   | 按 TraceId 查询时是否自动关联查找涉及的服务，默认 false |

### 响应示例

```json
{
  "code": 0,
  "data": {
    "count": 3,
    "logs": [
      {
        "_time_second_": "2024-11-15T10:30:00+08:00",
        "subApplication": "my-service",
        "level": "error",
        "msg": "NullPointerException at UserService.java:42",
        "xrayTraceId": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
        "_pod_name_": "my-service-pod-xyz",
        "ext": {"uid": "12345", "requestId": "req-001"}
      }
    ],
    "keys": [...],
    "query": "SELECT * FROM `db`.`application` WHERE ...",
    "where": "`subApplication` = 'my-service' AND `level` = 'error'",
    "cost": 230,
    "hiddenFields": ["_raw_log_"],
    "downloadFields": [...]
  },
  "msg": "ok"
}
```

| 字段    | 说明                                |
| ------- | ----------------------------------- |
| `count` | 本次返回的日志条数                  |
| `logs`  | 日志条目数组，每条含所有字段        |
| `cost`  | 查询耗时（毫秒）                    |
| `where` | 实际执行的 WHERE 条件（便于调试）   |
| `query` | 实际执行的 SQL（去除 LIMIT/OFFSET） |

---

## 查询语法（Lucene DSL）

| 语法     | 示例                                 | 等价 SQL                              |
| -------- | ------------------------------------ | ------------------------------------- |
| 字段等值 | `subApplication:my-service`          | `` `subApplication` = 'my-service' `` |
| 多值 OR  | `level:(error OR warn)`              | `` `level` IN ('error', 'warn') ``    |
| 否定     | `NOT level:debug`                    | `` `level` != 'debug' ``              |
| AND 组合 | `subApplication:svc AND level:error` | 两个条件 AND                          |
| Map 字段 | `ext.uid:12345`                      | `ext['uid'] = '12345'`                |
| TraceId  | `xrayTraceId:abc123...def`           | 自动压缩时间范围                      |

**重要约束（application 表）：** 查询条件中必须包含以下至少一个字段，否则报错：

- `subApplication`（推荐，必须精确匹配服务名）
- `xrayTraceId`（32位16进制，触发自动时间压缩）
- `_pod_name_`
- `traceId` / `ID` / `catMsgId` / `catRootId`
- `userId`（需同时满足时间范围 ≤ Apollo 配置的 userIdTimeLimit）

**同时查询服务数量上限**：默认最多 3 个 subApplication（由 Apollo 动态配置）。

---

## 常用查询场景示例

### 场景 1：按服务名查询最近错误日志

```
query = subApplication:my-service AND level:error
st    = now - 3600  (最近1小时)
et    = now
```

### 场景 2：按 TraceId 查询链路日志

```
query = xrayTraceId:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
st    = traceId 中解码的时间戳 - 5分钟  （可适当放宽，系统会自动压缩）
et    = traceId 中解码的时间戳 + 10分钟
searchTraceApp = true  （让系统自动找涉及的服务）
```

### 场景 3：按服务名+关键词查询

```
query = subApplication:my-service AND msg:NullPointerException
st    = now - 1800
et    = now
```

### 场景 4：查询某用户相关日志

```
query = subApplication:my-service AND ext.uid:12345
st    = now - 3600
et    = now
```

---

## 接口三：查询日志聚类（cluster-logs）

```
GET /api/v1/tables/33/cluster-logs
```

将指定时间范围内的日志按内容模板聚类（Drain 算法），返回各聚类的模板文本和日志数量。  
**仅支持 application 表（tid=33）**。

> **重要**：聚类功能依赖离线 Daemon（每5秒训练一次）和 CK 中的 `logClusterId`
> 列（由日志采集端写入）。如果某服务从未触发过聚类训练，或所有日志均为
> `logClusterId=0/NULL`（未分类），则返回空列表。调用方必须做好无数据的兜底处理。

### 请求参数（Query String）

| 参数        | 类型   | 必填 | 说明                                                                               |
| ----------- | ------ | ---- | ---------------------------------------------------------------------------------- |
| `query`     | string | 是   | Lucene 语法查询条件，规则与 `/logs` 完全相同，必须包含 `subApplication` 等必要字段 |
| `st`        | int64  | 是   | 开始时间，Unix 秒                                                                  |
| `et`        | int64  | 是   | 结束时间，Unix 秒                                                                  |
| `compareST` | int64  | 否   | 对比时间段开始，Unix 秒；与 `compareET` 同时传才生效                               |
| `compareET` | int64  | 否   | 对比时间段结束，Unix 秒                                                            |

> 不需要
> `page`/`pageSize`/`orderKeywords`，接口内部固定返回数量最多的前 1000 个聚类，按 count 降序。

### 响应示例（有数据）

```json
{
  "code": 0,
  "data": {
    "templates": [
      {
        "id": 42,
        "count": 1523,
        "template": "Failed to connect to [*] after [*] retries, error: [*]",
        "newClusterID": "logs__application__subApplication__my-service__42",
        "diffType": 0,
        "diffNum": 0,
        "diffRate": 0
      },
      {
        "id": 7,
        "count": 380,
        "template": "User [*] login success from [*]",
        "newClusterID": "logs__application__subApplication__my-service__7",
        "diffType": 0,
        "diffNum": 0,
        "diffRate": 0
      }
    ]
  },
  "msg": "ok"
}
```

### 响应示例（无数据 / 聚类未就绪）

```json
{
  "code": 0,
  "data": {
    "templates": []
  },
  "msg": "ok"
}
```

### 响应字段说明

| 字段                       | 类型    | 说明                                                                                      |
| -------------------------- | ------- | ----------------------------------------------------------------------------------------- |
| `templates`                | array   | 聚类模板列表，可能为空数组                                                                |
| `templates[].id`           | int64   | 聚类 ID（对应 Drain 模型中的 cluster ID）                                                 |
| `templates[].count`        | int     | 该时间段内命中此模板的日志数                                                              |
| `templates[].template`     | string  | 模板文本，变量部分用 `[*]` 替代                                                           |
| `templates[].newClusterID` | string  | 完整聚类标识，格式：`logs__application__subApplication__{svc}__{id}`                      |
| `templates[].diffType`     | int     | 对比类型（仅在传了 compareST/compareET 时有意义）：`0`=新增, `1`=增加, `2`=相同, `3`=减少 |
| `templates[].diffNum`      | int     | 对比时段的数量差值（正为增加，负为减少）                                                  |
| `templates[].diffRate`     | float32 | 相对变化率，`(current - origin) / origin`                                                 |

### 无数据的常见原因

1. **聚类未训练**：该 subApplication 的日志从未触发过 Daemon 训练（可能日志量极少，或功能未开启）
2. **所有日志未分类**：CK 中该服务的日志 `logClusterId` 全为 `0` 或 `NULL`（由采集端决定）
3. **时间范围内确实没有日志**：本身就是空结果
4. **Redis 模型缓存失效**：模型 TTL 为 7 天，过期后需等待 Daemon 重新训练

---

## 错误码

| code   | 含义                         |
| ------ | ---------------------------- |
| `0`    | 成功                         |
| 非 `0` | 失败，`msg` 字段包含错误描述 |

**常见错误：**

- `查询超出限制，请缩小查询范围或优化查询语句` — 扫描量超阈值，缩小时间范围或加更多过滤条件
- `必须含有subApplication、traceId...中的一个或多个字段` — 缺少必要过滤条件
- `你没有对应的访问权限` — 没有该 subApplication 的查询权限，响应中含申请链接
- `此服务查询被禁止` — 该服务在黑名单中
- `查询时间区间过长` — 超过最大查询天数（默认 5 天）
- `日志表已下线` — 该表已停用
