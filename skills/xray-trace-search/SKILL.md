---
name: xray-trace-search
description: "查询服务的trace 链路数据，支持按服务名、时间范围、异常类名、pod、接口、耗时、traceId 等多维度过滤。触发词：具体的接口和异常、trace 搜索、链路查询、异常 trace、慢请求、traceId 查询、错误链路、xray trace、调用链、pod 异常、接口耗时时触发skill。"
version: 1.0.0
metadata:
  category: trace
  subcategory: batch-search
  platform: xray
  trigger: service_name/interface/time_range
  input: [service, interface, st, et]
  output: [span_list, traceId_list, aggregation_analysis]
  impl: http-api
---

# XRay 异常 Span 批量查询

## 概述

调用 `/analysisSearch` 接口，查询指定服务+接口在某时间段内的**异常 Span**，输出：
- 异常 Span 精简列表（最多 1000 条）
- 去重后的 traceId 列表
- 调用链路中（机房、Pod、接口、异常类型等分布）

接口参数与响应字段详见 [references/api.md](references/api.md)。

所有请求统一使用 `xray_ticket: pass` 通过鉴权，无需用户提供 token。

---

## 工作流程

### Step 1：收集参数

向用户收集以下信息（必要时追问）：

| 参数 | 必填 | 说明 |
|------|------|------|
| `app` | 是 | 服务名 |
| `start` / `end` | 是 | 时间范围，支持自然语言，转为秒级时间戳 |
| `endpoint` | 否 | 格式：`transactionType.transactionName`，如 `Http./api/v1/user` 或 `Service.com.xxx.SomeService` |
| `errorNames` | 否 | 异常类型过滤，如 `TimeoutException` |
| `limit` | 否 | 返回条数，默认 500，最大 1000 |

**时间收集原则：**
- 若用户说"最近 1 小时"→ `end=now, start=now-3600`
- 若用户说"今天上午 10 点到 11 点"→ 转换为对应时间段秒级时间戳
- 若用户未说明时间 → 主动询问

**endpoint 收集原则：**
- 若用户只说了接口路径（如 `/api/v1/user`），默认补充 `Http.` 前缀 → `Http./api/v1/user`
- 若用户说 RPC 接口（如 `com.xxx.SomeService`），前缀用 `Service.` → `Service.com.xxx.SomeService`
- 若用户未提供 endpoint → 不传，查询整个服务的异常

### Step 2：调用接口

使用 Bash 工具执行 `scripts/analysis_search.py`（脚本位于 skill 目录下）：

```bash
python3 <skill_dir>/scripts/analysis_search.py \
  --app <服务名> \
  --start <秒级时间戳> \
  --end <秒级时间戳> \
  [--endpoint "transactionType.transactionName"] \
  [--error-names "TimeoutException,IOException"] \
  [--limit 500]
```

**参数映射：**

| 脚本参数 | 对应字段 | 说明 |
|----------|---------|------|
| `--app` | `app` | 服务名（必填） |
| `--start` | `start` | 开始时间秒级时间戳（必填） |
| `--end` | `end` | 结束时间秒级时间戳（必填） |
| `--endpoint` | `endpoint` | 接口过滤（选填） |
| `--error-names` | `errorNames` | 逗号分隔的异常类型（选填） |
| `--limit` | `limit` | 返回条数，默认 500（选填） |

脚本内置 `xray_ticket: pass` 鉴权头，无需额外配置。

### Step 3：解析并输出结果

返回结果按以下结构展示：

#### 1. 概览
- 命中异常 Span 总数（`total`）
- 返回 Span 数（`spans` 列表长度）
- 去重 traceId 数量

#### 2. 8 维度聚合分析（重点展示，按 count 降序）

优先展示以下维度（有数据才展示）：
- **异常类型分布** `errorTypeDistribution` — 主要报什么错
- **接口分布** `spanNameDistribution` — 哪些接口异常最集中
- **Pod 分布** `podDistribution` — 是否存在单 Pod 热点
- **机房分布** `zoneDistribution` / `downstreamZoneDistribution` — 异常是否集中在某机房
- **跨机房占比** `crossZoneRatio`
- **下游集群分布** `downstreamIpDistribution`
- **入口分布** `entryDistribution`

#### 3. 异常 Span 列表摘要（取前 10 条展示）

每条展示：`traceId`、`startTimestamp`、`durationMs`、`spanType`、`errorTypes`、`podName`、`zone`

#### 4. traceId 列表

列出所有去重后的 traceId，并提示用户可使用 xray-logview-analyzer 做单链路分析。

---

## 注意事项

- 接口**固定只查异常 Span**，无需用户指定，也无法查正常请求
- `total` 是命中总数，`spans` 列表受 `limit` 限制，两者可能不同
- 若 `total` 远大于 `limit`，提示用户缩小时间范围或增加 `errorNames` 过滤
- `endpoint` 用第一个 `.` 分割，`transactionName` 中的 `.` 不影响（如 `Http./api/v1.0/user` 会被正确识别）
- 最大查询时间跨度为 7 天
