# /analysisSearch 接口参考文档

## 接口信息

- **完整地址**: `POST https://xray.devops.xiaohongshu.com/api/trace/analysisSearch`
- **Content-Type**: `application/json`
- **功能**: 批量查询指定服务+接口在某时间段内的**异常 Span**，返回精简 Span 列表 +
  8 维度聚合分析结论

---

## 请求参数

```json
{
  "app": "string", // 必填：服务名（如 xray-server）
  "endpoint": "string", // 选填：接口，格式 transactionType.transactionName（如 URL./api/v1/user）
  "start": 1700000000, // 必填：开始时间（秒级 Unix 时间戳）
  "end": 1700003600, // 必填：结束时间（秒级 Unix 时间戳）
  "errorNames": ["NullPointerException"], // 选填：异常类型白名单（精确匹配）
  "limit": 500 // 选填：返回条数上限，默认 500，最大 1000
}
```

### 参数说明

| 参数         | 类型           | 必填 | 说明                                                                                           |
| ------------ | -------------- | ---- | ---------------------------------------------------------------------------------------------- |
| `app`        | String         | 是   | 服务/应用名                                                                                    |
| `endpoint`   | String         | 否   | 格式：`transactionType.transactionName`，如 `Http./api/v1/user`、`Service.com.xxx.SomeService` |
| `start`      | Long           | 是   | 秒级时间戳，开始时间                                                                           |
| `end`        | Long           | 是   | 秒级时间戳，结束时间，必须 > start                                                             |
| `errorNames` | List\<String\> | 否   | 异常类名白名单，如 `["IOException", "TimeoutException"]`                                       |
| `limit`      | Integer        | 否   | 默认 500，最大 1000                                                                            |

### 校验规则

- `end > start`
- `end - start <= 7 * 24 * 3600`（最大跨度 7 天）
- `limit ∈ (0, 1000]`
- 接口**固定只查询失败/异常 Span**（status=1），无需用户指定

---

## 响应结构

```json
{
  "success": true,
  "code": "200",
  "data": {
    "total": 1234,
    "spans": [...],
    "traceIds": ["abc123", "def456"],
    "aggregation": {...}
  }
}
```

### `spans[]` — SpanAnalysisBrief 字段

| 字段              | 类型           | 说明                         |
| ----------------- | -------------- | ---------------------------- |
| `traceId`         | String         | 链路 ID                      |
| `segmentId`       | String         | Segment ID                   |
| `spanId`          | Integer        | Span ID                      |
| `app`             | String         | 所属服务                     |
| `transactionType` | String         | 事务类型（如 URL、RPC）      |
| `transactionName` | String         | 事务名（如 /api/v1/user）    |
| `startTimestamp`  | Instant        | Span 开始时间（微秒精度）    |
| `durationMs`      | Long           | 耗时（毫秒）                 |
| `podName`         | String         | Pod 名称                     |
| `ip`              | String         | Pod IP                       |
| `zone`            | String         | 所在机房                     |
| `downstreamIp`    | String         | 下游 IP                      |
| `downstreamZone`  | String         | 下游机房                     |
| `hasException`    | Boolean        | 是否有异常                   |
| `errorTypes`      | List\<String\> | 异常类型列表                 |
| `entry`           | String         | 来源入口                     |
| `acrossZone`      | Boolean        | 是否跨机房                   |
| `spanType`        | String         | ENTRY / EXIT / LOCAL         |
| `bizType`         | String         | RPC / CACHE / DB / MQ / HTTP |
| `readWriteFlag`   | Integer        | 1=读, 2=写                   |

### `aggregation` — 8 维度聚合

| 字段                         | Key 格式                          | 说明                     |
| ---------------------------- | --------------------------------- | ------------------------ |
| `spanNameDistribution`       | `transactionType:transactionName` | 哪个接口异常最集中       |
| `downstreamIpDistribution`   | `ip`                              | 访问哪个下游集群异常最多 |
| `entryDistribution`          | `entry`                           | 异常来自哪个入口         |
| `podDistribution`            | `podName:ip`                      | 是否单 POD 热点          |
| `crossZoneRatio`             | 百分比                            | 跨机房调用占比           |
| `zoneDistribution`           | `zone`                            | 异常集中机房             |
| `downstreamZoneDistribution` | `downstreamZone`                  | 下游哪个机房返回异常最多 |
| `errorTypeDistribution`      | `errorType`                       | 主要异常类型分布         |

所有分布类字段均为 `Map<String, Long>`，按 count 降序排列。

---

## 时间格式转换参考

用户输入的自然语言时间转为秒级 Unix 时间戳：

- "今天上午10点" → 当天 10:00:00 的秒级时间戳
- "最近1小时" → `end = now(), start = now() - 3600`
- "2024-03-25 14:00 到 15:00" → 对应时间段的秒级时间戳

---

## 示例请求

```bash
python3 <skill_dir>/scripts/analysis_search.py \
  --app xray-server \
  --start 1711339200 \
  --end 1711342800 \
  --endpoint "Http./api/trace/search" \
  --error-names "TimeoutException" \
  --limit 200
```

## 注意事项

- `endpoint` 使用第一个 `.` 分割：左侧为 `transactionType`，右侧为 `transactionName`。若
  `transactionName` 本身含 `.`，需确保格式正确
- 接口只返回**异常 Span**，正常 Span 不包含在内
- `limit` 仅控制返回的 Span 数量，`total` 是实际命中总数
- 若 `traceIds` 数量很大，建议配合 traceId 单链路分析接口进一步排查
