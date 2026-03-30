---
name: xray-log-query
description:
  '查询小红书内部 Xray 日志平台的应用日志（application
  表，tid=33）。支持按服务名、TraceId、关键词等条件查询日志详情（/logs）和日志数量分布（/charts）。适用于以下场景：上下文中包含traceId、异常相关的信息，排查线上服务异常、根据
  xrayTraceId 追踪请求链路、统计某时间段内的日志数量趋势、查询某用户或某 Pod
  的相关日志。当用户说"帮我查日志"、"查一下 xxx 服务的错误"、"这个 traceId
  的日志是什么"、"最近一小时有多少 error"时触发本 skill。'
version: 1.0.0
metadata:
  category: log
  subcategory: application-log
  platform: xray
  trigger: service_name/traceId/keyword/time_range
  input: [query, st, et, page, pageSize]
  output: [log_list, log_count, log_clusters]
  impl: http-api
---

# Xray 日志查询

## 概述

通过调用 Xray 日志平台的 HTTP API，查询小红书应用日志（application 表）。  
详细接口文档和查询语法见 [references/api.md](references/api.md)。

## 与 xray-single-trace-analysis 的职责区分

**本 skill（xray-log-query）** 和 **xray-single-trace-analysis** 都支持以 Trace
ID 为输入，但职责不同，需根据用户意图选择：

| 对比维度 | xray-log-query（本 skill）                            | xray-single-trace-analysis                     |
| -------- | ----------------------------------------------------- | ---------------------------------------------- |
| 数据类型 | **日志数据**：应用输出的文本日志（application 表）    | **链路数据**：Span 调用链、耗时分布、异常 Span |
| 核心能力 | 搜索/过滤日志内容、日志聚类、趋势统计                 | 分析 Span 拓扑、定位慢/异常节点、根因分析      |
| 典型问题 | "这个 traceId 对应的日志是什么？"、"有没有报错信息？" | "这条链路为什么慢？"、"哪个服务出了异常？"     |

**意图判断规则**（用户提供 Trace ID 时）：

- 用户想查看**该 trace 对应的应用日志内容、日志文本** → 本 skill 处理
- 用户想了解**调用链路结构、Span 耗时、哪个节点异常** →
  **转交 xray-single-trace-analysis**，告知用户："您的需求是分析链路数据，请使用 xray-single-trace-analysis
  skill"

## 工作流程

### Step 1：理解用户意图，确定查询参数

根据用户描述，确定以下参数：

| 参数        | 确定方式                                                              |
| ----------- | --------------------------------------------------------------------- |
| `query`     | 从用户描述中提取服务名、TraceId、关键词等，组合 Lucene 语法           |
| `st` / `et` | 从用户描述中提取时间范围，转换为 Unix 秒；未指定则默认最近 1 小时     |
| 查询类型    | 用户要看"数量/趋势" → charts；要看"具体日志内容" → logs；通常两个都调 |

**query 构建原则（重要）：**

- **服务名原样透传**：query 中的服务名必须严格使用用户提供的原始值，不得做任何拆分、补全或格式化。例如用户说
  `liveanchor-service-default`，则 query 中写
  `subApplication:liveanchor-service-default`，禁止修改其中任何字符（如不要变成
  `liveanchor-service--default`）
- application 表强制要求 query 中至少包含
  `subApplication`、`xrayTraceId`、`_pod_name_`、`traceId`、`userId` 之一，否则报错
- 优先使用 `subApplication:服务名` 作为基础条件
- 按 TraceId 查时用 `xrayTraceId:xxxxx`，同时设置 `searchTraceApp=true`
- 多个条件用 `AND` 连接

**时间参数说明：**

- 按 TraceId 查时，时间范围可适当放宽（如前后各 5 分钟），系统会自动从 traceId 中解码精确时间并压缩
- 最大查询时间跨度为 5 天
- 若用户提供时间字符串（如 `"2024-03-25 14:00:00 - 2024-03-25 15:10:10"`），先用 `to_timestamp.py`
  转换为 Unix 秒：
  ```bash
  python3 scripts/to_timestamp.py --range "2024-03-25 14:00:00 - 2024-03-25 15:10:10"
  # 输出为秒级时间戳，不是毫秒，直接作为 --st / --et 使用
  # 也支持: --range "now-1h - now" / --start "2024-03-25 14:00" --end "2024-03-25 15:00"
  ```

### Step 2：设置鉴权

所有查询脚本均内置鉴权逻辑，ticket 生成规则为 `Base64(app&token&timestamp_ms)`，请求头字段名为
`xray_ticket`。

**Token 获取策略（按优先级）：**

1. 读取环境变量 `XRAY_AUTH_TOKEN`（推荐，在 `.env` 或 shell profile 中预先配置）
2. 若环境变量未设置，脚本运行时会在终端提示用户交互式输入

**app 来源：**

- 优先读取环境变量 `XRAY_APP`；未设置时默认使用 `xray`

**推荐配置方式：**

```bash
export XRAY_AUTH_TOKEN="your_token_here"   # 在 XRay 平台申请并审批后获取
# export XRAY_APP="your_app_name"          # 可选，默认 xray
```

Token 申请地址：[xray.devops.xiaohongshu.com/config/token](http://xray.devops.xiaohongshu.com/config/token)（申请后需联系 @阿普 或 @荀诩 审批，QPS 上限 20）

`scripts/` 目录下共 6 个脚本：

| 脚本                            | 说明                                                                    |
| ------------------------------- | ----------------------------------------------------------------------- |
| `scripts/auth.py`               | **鉴权公共模块**：ticket 生成、token 读取（被其他脚本复用，不直接调用） |
| `scripts/nl_to_xql.py`          | 自然语言 → XQL 查询参数（支持规则模式和 LLM 模式）                      |
| `scripts/validate_query.py`     | 前置参数校验，尽早发现问题（必须在调用接口前执行）                      |
| `scripts/query_charts.py`       | `/charts` 接口：查询日志数量分布，同时为 /logs 预热缓存                 |
| `scripts/query_logs.py`         | `/logs` 接口：查询日志详情列表                                          |
| `scripts/query_cluster_logs.py` | `/cluster-logs` 接口：查询日志聚类模板                                  |

**当用户用自然语言描述查询意图时**，先调用 `nl_to_xql.py` 生成 query/st/et 参数，再进入 Step
3 流程。

```bash
# 规则模式（无需 LLM，基于正则匹配）
python scripts/nl_to_xql.py --text "查一下 my-service 最近 1 小时的 error 日志"
# 输出 {"query": "subApplication:my-service AND level:error", "st": ..., "et": ..., ...}

# LLM 模式（更准确，需配置 API Key）
python scripts/nl_to_xql.py --text "..." --llm-api-key $LLM_API_KEY
```

`nl_to_xql.py` 输出 JSON，字段含义：

- `query` / `st` / `et`：直接传给后续脚本
- `search_trace_app`：含 xrayTraceId 时为 true，需传给 query_logs.py
- `confidence`：high/medium/low；low 时 exit 2，建议人工确认或启用 LLM 模式

### Step 3：前置校验（必须）

在调用任何接口脚本前，先用 `validate_query.py` 校验参数。校验失败（exit
1）时终止流程并告知用户错误原因。

```bash
python scripts/validate_query.py \
  --query "<XQL查询条件>" \
  --st <开始Unix秒> \
  --et <结束Unix秒>
# exit 0 → 通过，继续；exit 1 → 失败，输出 {"valid": false, "errors": [...]}
```

校验内容（来自服务端同名逻辑）：

- query 非空，且不含 `| SELECT` 注入
- query 含 `subApplication` / `xrayTraceId` / `_pod_name_` 等必要字段之一
- `xrayTraceId` 格式为 32 位十六进制
- `ET > ST`，时间跨度不超过 5 天（与 Apollo `max_query_time_range_day` 一致）
- `pageSize` 在 [1, 10000] 范围内

### Step 4：先调 query_charts.py，再并行调 query_cluster_logs.py 和 query_logs.py

**第一步：调用 query_charts.py（必须最先调，为 /logs 预热缓存）**

```bash
python scripts/query_charts.py \
  --query "<Lucene查询条件>" \
  --st <开始Unix秒> \
  --et <结束Unix秒> \
  [--page-size 20]
```

**第二步：同时调用 query_cluster_logs.py 和 query_logs.py（可并行）**

调用 query_cluster_logs.py：

```bash
python scripts/query_cluster_logs.py \
  --query "<Lucene查询条件>" \
  --st <开始Unix秒> \
  --et <结束Unix秒> \
  [--compare-st <对比开始Unix秒> --compare-et <对比结束Unix秒>]
```

调用 query_logs.py：

```bash
python scripts/query_logs.py \
  --query "<Lucene查询条件>" \
  --st <开始Unix秒> \
  --et <结束Unix秒> \
  [--page 1] [--page-size 20] [--order desc] \
  [--search-trace-app]   # 按 TraceId 查时加上
```

### Step 5：解读并呈现结果

**charts 结果解读：**

- 提取 `data.count` 作为总日志数
- 遍历 `data.histograms`，找出数量最多的时间段
- 如有 `details`（level 分色），汇总各 level 占比

**聚类结果优先策略（重要）：**

优先检查 `/cluster-logs` 的 `data.templates` 是否非空：

- **有聚类数据**（`templates` 长度 > 0）：
  - 优先基于聚类分析，按 `count` 降序呈现各模板
  - 解读模板文本（`[*]` 是变量占位符，代表实际值）
  - 重点标出 count 最高的 top 3~5 个模板，说明它们代表的典型日志模式
  - 再用 /logs 的原始日志补充具体上下文（如时间、level、traceId 等）
  - 向用户说明："以下是按日志内容聚类的分析结果，共 N 种模式"

- **无聚类数据**（`templates` 为空数组）：
  - 不报错，静默降级，直接使用 /logs 原始日志进行分析
  - 如有必要，向用户说明："聚类数据暂不可用（可能是该服务日志量较少或聚类模型尚未训练），以下为原始日志分析"

**logs 结果解读：**

- 提取 `data.logs`
  数组，重点展示：`_time_second_`、`level`、`msg`、`subApplication`、`xrayTraceId`、`_pod_name_`
- 报告 `data.cost`（查询耗时）和 `data.where`（实际过滤条件）
- 如果 `data.count` 为 0，告知用户未找到日志，建议放宽时间范围或调整查询条件

**错误处理：**

- `code != 0`：直接将 `msg` 字段告知用户
- 包含"没有对应的访问权限"：提示用户申请权限，响应中通常含申请链接
- 包含"查询超出限制"：建议缩小时间范围或增加 subApplication 过滤条件
- 包含"必须含有 subApplication"：提示用户在 query 中补充服务名等必要字段
- /cluster-logs 返回错误时：不影响主流程，降级为纯 /logs 分析

### Step 6：分页处理（如需）

如用户需要更多日志，递增 `page` 参数继续调用 /logs，直到 `data.count < pageSize` 表示已到末页。

## 快速示例

### 从自然语言到完整查询（端到端流程）

```bash
# Step 0：自然语言 → XQL 参数
python scripts/nl_to_xql.py --text "查一下 my-service 最近 1 小时的 error 日志"
# → {"query": "subApplication:my-service AND level:error", "st": ..., "et": ...}

# Step 1：前置校验
python scripts/validate_query.py \
  --query "subApplication:my-service AND level:error" \
  --st $(($(date +%s) - 3600)) --et $(date +%s)
# → {"valid": true}

# Step 2-4：正常查询（见下方示例）
```

### 查询某服务最近 1 小时的错误日志（含聚类分析）

```bash
# Step 1：前置校验
python scripts/validate_query.py \
  --query "subApplication:my-service AND level:error" \
  --st $(($(date +%s) - 3600)) --et $(date +%s)

# Step 2：先获取分布（为 logs 预热缓存）
python scripts/query_charts.py \
  --query "subApplication:my-service AND level:error" \
  --st $(($(date +%s) - 3600)) --et $(date +%s)

# Step 2：并行获取聚类 + 原始日志
python scripts/query_cluster_logs.py \
  --query "subApplication:my-service AND level:error" \
  --st $(($(date +%s) - 3600)) --et $(date +%s)

python scripts/query_logs.py \
  --query "subApplication:my-service AND level:error" \
  --st $(($(date +%s) - 3600)) --et $(date +%s) \
  --page-size 20 --order desc

# 若 cluster-logs 的 templates 非空 → 优先展示聚类分析
# 若 cluster-logs 的 templates 为空  → 直接展示 logs 原始日志
```

### 按 TraceId 查询链路日志

```bash
# Step 1：先获取分布
python scripts/query_charts.py \
  --query "xrayTraceId:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4" \
  --st $((ts - 300)) --et $((ts + 600))

# Step 2：获取详情（traceId 场景通常不适合聚类，直接查 logs）
python scripts/query_logs.py \
  --query "xrayTraceId:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4" \
  --st $((ts - 300)) --et $((ts + 600)) \
  --search-trace-app --order asc --page-size 100
```

### 聚类对比分析（排查两个时段的变化）

```bash
# 对比"当前1小时"与"昨天同一时段"的日志模式变化
python scripts/query_cluster_logs.py \
  --query "subApplication:my-service" \
  --st $((now - 3600)) --et $now \
  --compare-st $((yesterday - 3600)) --compare-et $yesterday

# diffType=0 (新增模式) / diffType=1 (数量增加) 是排查问题的重点
```
