---
name: xray-service-analysis

description:
  "提供“服务异常分析”和“接口性能分析”能力。支持分析指定时段内的服务内部异常（exceptions）、本服务提供接口（serviceAnomalies）以及下游调用接口（callAnomalies）的健康状况，并基于分析结果引导至日志、堆栈或链路的深度分析。适用场景:
  用于在询问中对于接口、异常没有明确的指定，询问服务整体情况。"
version: 1.0.0
metadata:
  category: diagnosis
  subcategory: service-analysis
  platform: xray
  trigger: service_name/time_range/analysis_type
  input: [analysis_type, service, startTime, endTime]
  output: [anomalies, serviceAnomalies, callAnomalies, diagnosis_summary]
  impl: python-script
---

# 服务异常与接口分析

## 能力说明

本 Skill 包含两类核心分析能力：

| 分析类型                   | 适用场景                           | 对应 API 路径                             |
| -------------------------- | ---------------------------------- | ----------------------------------------- |
| **错误异常分析 (Problem)** | 识别服务异常、错误总结             | `/api/diagnosis/service/analysis/problem` |
| **接口服务分析 (Service)** | 接口性能评估、流量状态、可用性分析 | `/api/diagnosis/service/analysis/rpc`     |

## 工作流程

### Step 1：确定分析类型与参数

从用户输入中提取以下参数：

- **analysis_type**: `problem`（异常分析）或 `rpc`（接口分析）。若未指明，默认执行 `problem` 分析。
- **service**: 服务名称（如
  `mewtwo-service-default`）。必须严格使用用户提供的原始服务名，不得做任何拆分、补全或格式化
- **startTime**: 开始时间，支持以下任意格式（脚本会自动转换）：
  - 相对时间：`now-15m`、`now-1h`、`now-2d`、`now`
  - Unix 秒时间戳：`1700000000`
  - Unix 毫秒时间戳：`1700000000000`（自动识别并除以 1000）
  - 日期时间字符串：`"2026-03-26 13:20:00"`、`"2026-03-26T13:20:00"`、`"2026-03-26 13:20"`
- **endTime**: 结束时间，格式同 startTime

> **注意**：时间转换在脚本内部完成，无需 LLM 提前格式化。将用户原始输入（如"最近15分钟"对应的
> `now-15m`、时间戳等）直接传给脚本即可。

### Step 2：执行诊断脚本

```bash
python3 {SKILL_DIR}/scripts/analyze_service.py \
  --type <problem|service> \
  --service "<service>" \
  --startTime "<startTime>" \
  --endTime "<endTime>"
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径。
>
> 脚本会在调用接口前自动将 `--startTime` / `--endTime` 转换为 `YYYY-MM-DD HH:MM:SS`
> 格式，并在 stderr 打印转换结果供确认，例如：
>
> ```
> [INFO] 时间范围: 'now-15m' → 2026-03-26 13:21:00  |  'now' → 2026-03-26 13:36:00
> ```
>
> **调用示例：**
>
> ```bash
> # 最近 15 分钟
> python3 {SKILL_DIR}/scripts/analyze_service.py --type problem --service my-service \
>   --startTime now-15m --endTime now
>
> # Unix 毫秒时间戳（自动转换）
> python3 {SKILL_DIR}/scripts/analyze_service.py --type service --service my-service \
>   --startTime 1700000000000 --endTime 1700003600000
>
> # datetime 字符串
> python3 {SKILL_DIR}/scripts/analyze_service.py --type problem --service my-service \
>   --startTime "2026-03-26 13:00:00" --endTime "2026-03-26 13:30:00"
> ```

### Step 3：输出结果

将脚本返回的诊断结果进行结构化展示。重点关注返回 JSON 中的异常数组，并按以下格式总结（参考
[JSON 响应示例](./references/examples.md)）：

#### 结果解读指引 (通用)

| 字段                 | 含义说明             | 关注点                                                                   |
| -------------------- | -------------------- | ------------------------------------------------------------------------ |
| `exceptions`         | **内部异常分析**     | 关注服务抛出的 Java/SQL 异常（如 `DuplicateKeyException`）。             |
| `serviceAnomalies`   | **服务提供接口分析** | 关注本服务提供的 RPC 接口（如 `saveMessageApi`）的 QPS 和成功率。        |
| `callAnomalies`      | **服务下游调用分析** | 关注下游依赖接口（如 `chattrade-service.bizMenuCommit`）的耗时和成功率。 |
| `target`             | **分析对象标识**     | 异常类名、本服务接口名或下游接口名。                                     |
| `metrics[].metric`   | **核心监控指标**     | QPS、成功率、平均耗时、异常计数值等。                                    |
| `metrics[].outliers` | **离群点/突发异常**  | 明确标出的异常时间点及数值。                                             |
| `status`             | **健康状态评分**     | `critical` 表示存在显著异常，需要优先排查。                              |

#### 分析结论模板

```markdown
## 诊断分析结论

**分析时段**: [startTime] 至 [endTime] **服务名称**: [service]

### 1. 异常分析

- **分析对象 (target)**: [异常类名，如 java.sql.SQLException]
- **异常状态**: [status]
- **受影响指标**: [metric]
- **问题时间段**: [通过 outliers 或 timeSeries 识别的时间区间]
- **异常表现**: [描述异常数值的变化情况]

### 2. 服务提供接口分析

- **分析对象 (target)**: [本服务接口名，如 saveMessageApi]
- **异常状态**: [status]
- **关键指标异常**:
  - **[指标1]**: 在 [时间段] 出现异常，数值为 [value]
  - **[指标2]**: 在 [时间段] 出现异常，数值为 [value]
- **有问题的可用区 (anomalyZones)**: [列出 anomalyZones 中的具体可用区，如：sh-zone-a]
- **接口影响描述**: [如：接口成功率大幅下降，影响服务可用性]

### 3. 服务调用接口分析

- **分析对象 (target)**: [下游接口名，如 chattrade-service.bizMenuCommit]
- **异常状态**: [status]
- **下游依赖表现**:
  - **[指标1]**: 在 [时间段] 异常，数值为 [value]
- **有问题的可用区 (anomalyZones)**: [列出下游受影响的可用区]
- **依赖风险描述**: [如：下游接口响应变慢，导致本服务出现堆积]

**总结**: [简述整体诊断结论及建议]
```

## 进阶排查指引 (Deep-Dive)

在完成服务级诊断后，根据发现的具体问题，应引导用户进行以下深入分析：

### 1. 发现特定异常 (Exception) 时

若 `anomalies` 中存在明显的 Java 异常（如 `TimeoutException`, `NullPointerException`）：

- **关联动作**: 建议使用 `xray-exception-analysis` 技能。
- **目标**: 获取该类异常的**聚类堆栈**，定位具体代码行。
- **话术示例**: "检测到服务存在 `[ExceptionName]`，建议使用 `xray-exception-analysis`
  获取该异常的聚类堆栈分析。"

### 2. 发现接口性能或成功率问题 (Service/Call) 时

若 `serviceAnomalies` 中接口状态为 `critical`：

- **关联动作**: 建议使用 `xray-trace-search` 。
- **目标**: 获取具体的 `traceId` 并查看 **xray-single-trace-analysis
  (调用链)**，分析耗时分布或错误节点。
- **话术示例**: "接口 `[endpoint]` 成功率下降/耗时增加，建议使用 `xray-exception-analysis`
  对该接口的 `fail` 或 `longest` 请求进行采样并查看 Logview。"

### 3. 需要查看具体业务日志时

若需要确认接口请求的参数、上下文或业务报错日志：

- **关联动作**: 建议使用 `xray-log-query` 技能。
- **目标**: 查询该时段内包含特定关键词或 `traceId` 的 **应用日志**。
- **话术示例**: "如需查看该时段的具体业务日志，请使用 `xray-log-query` 查询
  `subApplication:[service]` 的日志详情。"

### 4. 已获取到具体 TraceId/MessageId 时

若通过上述步骤获取到了具体的请求标识：

- **关联动作**: 建议使用 `xray-single-trace-analysis` 技能。
- **目标**: 进行**单链路精细化分析**，定位根因。
- **话术示例**: "已定位到异常请求，建议使用 `xray-single-trace-analysis` 对 TraceId `[TraceId]`
  进行深入分析。"

## 接口详情

- **Base URL**: `https://xray-ai.devops.xiaohongshu.com`
- **Headers**:
  - `Content-Type: application/json`
  - `User-Agent: Apipost client Runtime`
- **Payload 示例**:
  ```json
  {
    "service": "clue-marketing-platform",
    "startTime": "2026-03-26 13:20:00",
    "endTime": "2026-03-26 13:36:00"
  }
  ```

## 注意事项

- **服务名原样透传**：`--service`
  参数必须严格使用用户提供的原始服务名，不得做任何拆分、补全或格式化。例如用户说
  `liveanchor-service-default`，则传
  `--service "liveanchor-service-default"`，禁止修改其中任何字符（如不要变成
  `liveanchor-service--default`）

## 错误处理

| 错误情况     | 处理方式                                 |
| ------------ | ---------------------------------------- |
| 脚本返回非 0 | 输出 stderr 报错信息                     |
| API 返回超时 | 提示用户服务诊断可能耗时较长，请稍后重试 |
| 无分析结果   | 告知用户该时段内数据不足或未发现明显异常 |
