---
name: xray-trace-search
description:
  '查询服务的 trace 链路数据，支持按服务名、时间范围、异常类名、pod、接口、耗时、traceId
  等多维度过滤。触发场景：(1) 用户提到某个服务某个接口的异常情况（如"分析 xxx 服务 /api/v1/foo
  接口的异常"、"查看 yyy 服务 queryXxx 接口报什么错"）——此时的"接口"指链路中的 endpoint，应使用本
  skill 做 trace 级别的接口异常聚合分析，而不是异常堆栈分析；(2) 具体的接口、trace
  搜索、链路查询、异常 trace、慢请求；(3) traceId 查询、错误链路、xray trace、调用链、pod
  异常、接口耗时；(4)
  用户说"分析某个服务的链路情况"、"查看服务链路"、"分析链路"等与服务链路相关的查询。'
version: 1.0.0
metadata:
  category: trace
  subcategory: batch-search
  platform: xray
  trigger: service_name/endpoint/time_range/errorNames
  input: [service, endpoint, st, et, errorNames]
  output: [spans, traceIds, aggregation_analysis]
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

| 参数            | 必填 | 说明                                                                                                                                                        |
| --------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app`           | 是   | 服务名（必须严格使用用户提供的原始值，不得拆分、补全或修改任何字符）                                                                                        |
| `start` / `end` | 是   | 时间范围，支持自然语言，转为秒级时间戳                                                                                                                      |
| `endpoint`      | 否   | 格式：`transactionType.transactionName`，如 `Http./api/v1/user`、`Service.com.xxx.SomeService`（服务端 RPC）或 `Call.下游服务名.下游接口`（客户端出站 RPC） |
| `errorNames`    | 否   | 异常类型过滤，如 `TimeoutException`                                                                                                                         |
| `limit`         | 否   | 返回条数，默认 500，最大 1000                                                                                                                               |

**时间收集原则：**

- 若用户说"最近 1 小时"→ `end=now, start=now-3600`
- 若用户说"今天上午 10 点到 11 点"→ 转换为对应时间段秒级时间戳
- 若用户未说明时间 → 主动询问
- 若用户提供时间范围字符串（如 `"2024-03-25 14:00:00 - 2024-03-25 15:10:10"`），使用
  `to_timestamp.py` 转换：
  ```bash
  python3 <skill_dir>/scripts/to_timestamp.py --range "2024-03-25 14:00:00 - 2024-03-25 15:10:10"
  # 输出为秒级时间戳，不是毫秒，直接作为 --start / --end 参数值使用
  # 也支持: --range "now-1h - now" / --start "2024-03-25 14:00" --end "2024-03-25 15:00"
  ```

**endpoint 收集原则：**

- 若用户只说了接口路径（未提及调用下游）：
  - 以 `/` 开头（如 `/api/v1/user`）→ HTTP 接口，补充 `Http.` 前缀 → `Http./api/v1/user`
  - 其他形式（如
    `com.xxx.SomeService`、`queryInterviewScheduleRecordSplitInfo`）→ 默认视为服务端 RPC，补充
    `Service.` 前缀
- 若用户说**作为客户端调用下游**的 RPC 接口，前缀用 `Call.` → `Call.${下游服务名}.${下游接口}`
  - 判断依据：用户描述中出现"调用下游"、"请求其他服务"、"出口"、"客户端"等字眼，或直接提供了 `Call.`
    格式
- 以上均无法判断时，追问用户接口类型以及是调用方还是被调用方
  - 示例：用户说"调用 order-service 的 com.xxx.OrderService/getOrder"→
    `Call.order-service.com.xxx.OrderService/getOrder`
  - 示例：用户说"调用 recruitcore-service-default 的 queryInterviewScheduleRecordSplitInfo"→
    `Call.recruitcore-service-default.queryInterviewScheduleRecordSplitInfo`
  - 判断依据：用户描述中出现"调用下游"、"请求其他服务"、"出口"、"客户端"等字眼，或直接提供了 `Call.`
    格式
- 若用户未提供 endpoint → 不传，查询整个服务的异常

### Step 2：调用接口

使用 Bash 工具执行 `scripts/analysis_search.py`（脚本位于 skill 目录下）：

```bash
python3 <skill_dir>/scripts/analysis_search.py \
  --app "<服务名>" \
  --start <秒级时间戳> \
  --end <秒级时间戳> \
  [--endpoint "transactionType.transactionName"] \
  [--error-names "TimeoutException,IOException"] \
  [--limit 500]
```

**参数映射：**

| 脚本参数        | 对应字段     | 说明                                         |
| --------------- | ------------ | -------------------------------------------- |
| `--app`         | `app`        | 服务名（必填，原样使用用户输入值，禁止修改） |
| `--start`       | `start`      | 开始时间秒级时间戳（必填）                   |
| `--end`         | `end`        | 结束时间秒级时间戳（必填）                   |
| `--endpoint`    | `endpoint`   | 接口过滤（选填）                             |
| `--error-names` | `errorNames` | 逗号分隔的异常类型（选填）                   |
| `--limit`       | `limit`      | 返回条数，默认 500（选填）                   |

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

列出所有去重后的 traceId，并在列表展示后**主动询问用户**：

> 已找到 N 个 traceId，是否需要进一步分析？
>
> 1. **单链路分析**（xray-single-trace-analysis）：针对某条 traceId 做异常 Span 定位与根因分析
> 2. **日志查询**（xray-log-query）：根据 traceId 查询关联的应用日志详情
> 3. 不需要，结束

根据用户选择：

- 选择 1 → 调用 `xray-single-trace-analysis` skill，让用户指定或从列表中选择一个 traceId 进行分析
- 选择 2 → 调用 `xray-log-query` skill，让用户指定或从列表中选择一个 traceId 查询日志
- 选择 1 和 2 → 依次执行以上两步
- 选择 3 或无需进一步分析 → 结束本次查询

---

## 注意事项

- **服务名原样透传**：`--app`
  参数必须严格使用用户提供的原始服务名，不得做任何拆分、补全或格式化。例如用户说
  `liveanchor-service-default`，则传
  `--app "liveanchor-service-default"`，禁止修改其中任何字符（如不要变成
  `liveanchor-service--default`）
- 接口**固定只查异常 Span**，无需用户指定，也无法查正常请求
- `total` 是命中总数，`spans` 列表受 `limit` 限制，两者可能不同
- 若 `total` 远大于 `limit`，提示用户缩小时间范围或增加 `errorNames` 过滤
- `endpoint` 用第一个 `.` 分割，`transactionName` 中的 `.` 不影响（如 `Http./api/v1.0/user`
  会被正确识别）
- 最大查询时间跨度为 7 天
