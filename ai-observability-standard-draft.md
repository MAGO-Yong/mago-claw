# AI Agent/Skill 可观测性标准

> 版本：v0.1 草稿
> 负责人：技术风险（正一）
> 状态：WIP

---

## 一、为什么要单独立这个标准

传统可观测性的隐含前提是：**同样的输入 → 同样的输出**。AI Agent/Skill 打破了这个假设。

传统监控能感知的是「系统是否活着」，但 AI 系统还需要回答两个更难的问题：
- **AI 在做什么？**（行为是否符合预期）
- **AI 做得好不好？**（输出质量是否达标）

这三个问题，对应三种不同的传感器：传统 Metrics/Logs/Traces 解决第一个，链路追踪规范解决第二个，SLO + 效果评测解决第三个。缺任何一层，可观测都是不完整的。

**业界背景**：OpenTelemetry 在 2024 年发布了 GenAI 语义规范（Semantic Conventions for Generative AI），专门定义 LLM/Agent/Tool 的 Span、Metrics、Events 标准字段，说明行业已经认可：AI 系统需要一套独立的可观测规范。

---

## 二、适用范围与核心原则

### 2.1 适用范围

本标准适用于公司所有接入 LLM 能力的在线应用，包括但不限于：
- 基于大模型的 Agent 系统（含编排引擎、多 Agent 协作）
- Skill 插件（各平台：lobi / allin / bigbai / drawin 等）
- RAG 管道、Embedding 服务
- 大模型推理服务直接调用场景

### 2.2 核心原则

1. **全链路 100% 覆盖**：从用户请求到模型推理的完整链路，不允许断层
2. **三层可观测**：系统可用性 + 行为可见性 + 效果可评测，缺一不可
3. **异常可告警**：每个监控指标必须有对应告警，禁止无主告警
4. **根因可定位**：出现问题可追溯到具体 Skill、模型调用或推理步骤
5. **效果有基线**：每次上线必须建立效果基线，劣化可量化、可感知
6. **隐私红线**：可观测建设不能突破数据安全红线，四级数据禁止进入任何监控系统

---

## 三、全链路指标规范（Metrics）

### 3.1 六层指标体系

指标覆盖必须贯穿以下六层，**禁止断层**。

#### 业务层
面向产品与用户，感知最终结果。

| 指标 | 说明 | 类型 | 要求 |
|------|------|------|------|
| 会话成功率 | 用户发起的会话中成功完成的比例 | Gauge | 强制 |
| 端到端耗时（P50/P99） | 从用户发起请求到完整响应的总耗时 | Histogram | 强制 |
| 用户报错率 | 用户侧感知到错误的比例 | Gauge | 强制 |
| 任务完成率 | Agent 达成用户意图的比例（见效果评测章节） | Gauge | 强制（S0/S1） |

#### Agent/应用层
感知 AI 应用的编排与决策质量。

| 指标 | 说明 | 类型 | 要求 |
|------|------|------|------|
| 规划成功率 | Agent 生成合法执行计划的比例 | Gauge | 强制 |
| 工具调用成功率 | Skill/Tool 调用成功的比例 | Gauge | 强制 |
| 推理轮次分布 | 单次会话中 LLM 被调用的次数分布 | Histogram | 推荐 |
| 会话并发量 | 当前并发会话数 | Gauge | 强制 |
| Context 使用率 | 当前 context window 使用比例 | Gauge | 推荐（接近上限时质量可能劣化） |
| Token 消耗量（input/output） | 每次请求的 token 用量 | Histogram | 强制（成本归因） |
| 推理成本 | 每次推理的估算费用 | Counter | 推荐 |

#### Skill 层
感知每个 Skill 插件的健康状态。

| 指标 | 说明 | 类型 | 要求 |
|------|------|------|------|
| 调用成功率 | 按 Skill 名称分维度 | Gauge | 强制 |
| 平均耗时 / P99 耗时 | 每个 Skill 的响应时间分布 | Histogram | 强制 |
| 异常率 | 异常类型分类（超时 / 业务错误 / 系统错误） | Gauge | 强制 |
| 限流 / 熔断触发次数 | 触发频率反映 Skill 稳定性压力 | Counter | 强制 |

#### 网关层
感知流量入口的管控情况。

| 指标 | 说明 | 类型 | 要求 |
|------|------|------|------|
| 请求量（QPS） | 按接口/应用维度 | Counter | 强制 |
| 成功率 | 网关侧成功率（含鉴权失败分类） | Gauge | 强制 |
| 拒绝率 / 限频触发次数 | 过载保护触发情况 | Counter | 强制 |
| 鉴权失败率 | 异常调用检测 | Gauge | 强制 |

#### 推理引擎层
感知模型推理底层的性能与健康状态。

| 指标 | 说明 | 类型 | 要求 | 参考阈值 |
|------|------|------|------|---------|
| TTFT（首 Token 延迟） | 从请求发出到第一个 Token 返回的耗时 | Histogram | 强制 | 告警 ≥5s，熔断 ≥10s |
| TPOT（每 Token 生成耗时） | 持续生成能力的核心指标 | Histogram | 强制 | - |
| E2E 推理耗时 | 端到端推理总时长 | Histogram | 强制 | 按模型类型分级 |
| 推理成功率 | 按错误类型分类（OOM / 超时 / 模型错误） | Gauge | 强制 |  |
| GPU 显存占用 | 显存水位监控 | Gauge | 强制 |  |
| GPU 利用率 | 算力使用效率 | Gauge | 强制 |  |
| 吞吐量（Token/s） | 模型整体输出能力 | Gauge | 推荐 |  |
| KV Cache 命中率 | 缓存效率，影响成本与延迟 | Gauge | 推荐 |  |
| 队列等待时长 | 请求积压情况 | Histogram | 强制 |  |

> **说明**：TTFT 是 AI 链路健康的最敏感指标。TTFT 劣化通常是模型过载的前兆，早于成功率下降出现。强制要求接入 TTFT 监控。

#### 基础设施层

| 指标 | 说明 | 要求 |
|------|------|------|
| 节点 CPU / 内存 / 磁盘使用率 | 资源水位 | 强制 |
| 网络带宽 | 大模型推理对带宽敏感 | 强制 |
| 容器健康状态 | Pod 重启次数、崩溃原因 | 强制 |
| 副本数 / 扩缩容事件 | 弹性伸缩情况 | 强制 |

### 3.2 成本可视化要求

AI 应用的 Token 消耗和推理成本必须有大盘可查、可预算、有告警：
- 按业务线 / 应用 / 模型维度归因
- 超配额自动触发告警
- 定期复盘低利用率服务

---

## 四、分布式链路追踪规范（Tracing）

### 4.1 平台标准

公司统一使用 **OpenTelemetry 协议 + XRay Langfuse** 平台：
- 上报地址（prod）：`https://xray-langfuse.devops.xiaohongshu.com/api/public/otel/v1/traces`
- 上报地址（sit）：`https://xray-langfuse.devops.sit.xiaohongshu.com/api/public/otel/v1/traces`
- 鉴权：`Authorization: Basic <base64(public_key:secret_key)>`

### 4.2 Trace 模型

```
一个用户会话
  └─ 根 Trace（langfuse.internal.as_root = "true"，当上游未接入 Langfuse 时必须设置）
       ├─ 意图理解 Span（invoke_agent）
       │    └─ LLM 推理 Span（chat）
       ├─ Skill 调用 Span（execute_tool）
       │    └─ 下游 RPC/HTTP（关联 XRay TraceId）
       └─ 最终响应 Span（chat）
```

**核心规则**：
1. 一个用户会话 = 一个根 Trace，以 `langfuse.session.id` 串联
2. 每次 LLM 调用、每次 Skill 调用 = 独立子 Span
3. **禁止链路断裂**：多模型串联、多 Agent 协作场景，Trace ID 必须跨模型透传
4. Langfuse 链路必须与 XRay 下游链路打通（AI 调用可关联到后续 RPC/HTTP 链路）
5. 多 Agent 并发场景，并发子 Agent 各自的 Span 均挂载在同一根 Trace 下

### 4.3 Span 类型规范

基于 OpenTelemetry GenAI 语义规范（`gen_ai.operation.name` 字段）：

| Span 类型 | `gen_ai.operation.name` 值 | Langfuse Observation 类型 | 适用场景 |
|---------|--------------------------|--------------------------|---------|
| LLM 对话推理 | `chat` | GENERATION | 对话、问答 |
| 内容生成 | `generate_content` | GENERATION | 多模态生成 |
| 文本补全 | `text_completion` | GENERATION | 补全类场景 |
| Agent 调用（调用远程） | `invoke_agent` | AGENT | 调用子 Agent |
| Agent 创建 | `create_agent` | AGENT | 创建 Agent 实例 |
| Skill/工具执行 | `execute_tool` | TOOL | 调用 Skill 插件 |
| 向量检索 | `embeddings` / `retrieval` | EMBEDDING | RAG 召回 |

### 4.4 必填 Attributes 规范

#### 强制字段（违反则视为链路不合规）

| 字段 | 说明 | 数据类型 |
|------|------|---------|
| `gen_ai.operation.name` | Span 类型，驱动 Langfuse 数据分类 | string（枚举） |
| `gen_ai.provider.name` | 模型提供商（如 `arkai`、`openai`） | string |
| `langfuse.session.id` | 会话 ID，用于 Session 维度分析（仅有真实会话 ID 时必须设置） | string |
| `langfuse.internal.as_root` | 上游未接入 Langfuse 时，LLM 入口 Span 必须设为 `"true"`（字符串类型） | string |

#### 有条件必须字段

| 字段 | 条件 | 说明 |
|------|------|------|
| `gen_ai.input.messages` | 有输入时 | 输入内容，**必须脱敏**，禁止含四级数据 |
| `gen_ai.output.messages` | 有输出时 | 输出内容，**必须脱敏** |
| `error.type` | 发生错误时 | 错误类型（timeout / oom / model_error 等） |
| `gen_ai.request.model` | 有模型信息时 | 模型名称（用于版本追踪） |
| `gen_ai.conversation.id` | 有会话 ID 时 | 会话/线程唯一标识 |

#### 推荐字段

| 字段 | 说明 |
|------|------|
| `langfuse.user.id` | 用户 ID（脱敏） |
| `langfuse.environment` | 环境标识（prod / sit） |
| `langfuse.trace.tags` | 业务标签，JSON 数组字符串 |
| `langfuse.observation.level` | 观测级别（DEBUG / DEFAULT / WARNING / ERROR） |
| `gen_ai.request.temperature` | 推理温度参数 |
| `gen_ai.response.finish_reasons` | 停止原因（stop / length / tool_calls 等） |
| `source.name` | 调用来源（业务标识） |

#### 成本追踪字段（必须为数字类型）

| 字段 | 说明 |
|------|------|
| `gen_ai.usage.input_tokens` | 输入 token 数 |
| `gen_ai.usage.output_tokens` | 输出 token 数 |
| `gen_ai.usage.total_tokens` | 总 token 数 |
| `gen_ai.usage.cost` | 估算成本 |
| `langfuse.observation.completion_start_time` | 首 token 时间（ISO8601 格式，带时区） |

### 4.5 隐私与安全要求

- `gen_ai.input.messages` / `gen_ai.output.messages` 必须脱敏后记录
- 四级数据（战略规划 / 用户隐私 / 核心源码 / 未公开业务数据）**禁止写入任何 Trace 字段**
- S0/S1 应用关键决策的输入输出必须在 Langfuse 持久化留存（脱敏后），保留时长 ≥ 6 个月

---

## 五、结构化日志规范（Logging）

### 5.1 基本要求

1. 必须使用公司统一结构化日志规范，禁止非结构化纯文本日志
2. 统一接入 XRay 日志平台（application 表）
3. 与 Langfuse Trace 通过 `langfuse.session.id` / TraceId 关联，支持跨系统追踪

### 5.2 强制打印字段

每条 AI 相关日志必须包含以下字段：

| 字段 | 说明 |
|------|------|
| `trace_id` | 与链路追踪打通 |
| `session_id` | 会话 ID |
| `user_id` | 用户 ID（脱敏） |
| `app_name` | 应用名 |
| `skill_name` | Skill 名称（有 Skill 调用时） |
| `model_name` | 模型名称 |
| `latency_ms` | 本步骤耗时（毫秒） |
| `status_code` | 执行状态码 |
| `error_msg` | 错误信息（无错误时可为空） |

### 5.3 禁止记录的内容

- 明文密钥、AK/SK、Token
- 用户隐私数据（手机号、身份证等四级数据）
- 公司机密数据（未经脱敏的业务核心数据）
- 完整的用户对话内容（除非业务侧有单独审批）

### 5.4 日志留存要求

| 日志类型 | 最低留存时长 |
|---------|------------|
| 核心业务日志 | 6 个月 |
| 审计日志（含 AI 接口调用记录） | 1 年 |

---

## 六、SLO 规范

### 6.1 为什么 AI 需要两套 SLO

传统 SLO 回答「服务是否可用」，AI 应用还必须回答「AI 做得好不好」。两套 SLO 都是强制要求，缺一不可。

### 6.2 稳定性 SLO（传统 SLO）

| 指标 | S0 目标 | S1 目标 | 说明 |
|------|---------|---------|------|
| 会话可用率 | ≥ 99.9% | ≥ 99.5% | 核心链路不可用率 |
| TTFT P99 | ≤ 5s | ≤ 10s | 首 Token 延迟 |
| E2E P99 | 按业务定义 | 按业务定义 | 不同模型差异大，需业务方确认 |
| Skill 调用成功率（核心 Skill） | ≥ 99.9% | ≥ 99.5% | 单 Skill 维度 |
| 错误预算消耗速率 | 参照 Google SRE Burn Rate | 同左 | 超速消耗触发告警 |

### 6.3 AI SLO（质量稳态）— 小红书需自定义

**行业现状**：目前无统一行业标准。参考 RAGAS、LangWatch、Arize 等工具的实践，当前最接近共识的 AI SLO 维度如下：

| 维度 | 含义 | 参考目标 | 数据来源 |
|------|------|---------|---------|
| 任务完成率（Task Success Rate） | Agent 是否达成用户意图 | 核心场景 ≥ 85% | Eval 评测 |
| Skill 命中率 | Agent 是否选择了正确的工具 | ≥ 90% | Trace 统计 |
| 输出事实性（Faithfulness） | 输出是否忠实于知识来源（RAG 场景） | ≥ 90% | LLM-as-Judge |
| 答案相关性（Answer Relevance） | 回答是否切题 | ≥ 85% | LLM-as-Judge |
| 拒识合理性 | 越权指令拒识率 | ≥ 99% | 规则检测 |
| 幻觉率 | 输出伪造信息的比例 | ≤ 5% | LLM-as-Judge |

#### Baseline 优先原则（关键机制）

**禁止拍脑袋设定 AI SLO 绝对值**。正确流程：

1. 上线后运行 **至少 2 周**，持续采样评测数据
2. 以采样结果的均值作为 **Baseline**
3. SLO 目标 = **Baseline × 90%**（即允许不超过 10% 的劣化）
4. 之后每次 Prompt / 模型 / Skill 变更，重新评测并对比 Baseline

#### SLO 违规响应

AI SLO 违规触发 P2 告警，响应流程：
1. 自动触发效果评测（见第八章）
2. 排查近期变更（Prompt / 模型版本 / Skill 变更）
3. 若根因明确，按变更回滚；若根因不明，上报进行人工分析

### 6.4 SLO 大盘要求

必须建设以下大盘，接入公司统一监控平台：

- **业务大盘**：会话成功率、端到端耗时、用户报错率、任务完成率
- **稳定性大盘**：全链路成功率、TTFT、各层异常率、资源水位
- **AI 质量大盘**：AI SLO 趋势、Eval 评分趋势、各模型/Skill 质量分布

大盘必须支持下钻：从宏观指标 → 具体请求 → 具体链路 → 具体 Trace。

---

## 七、告警规范（Alerting）

### 7.1 告警分级与响应时效

| 级别 | 定义 | 响应时效 | 恢复时效 | 通知渠道 |
|------|------|---------|---------|---------|
| P0（核心故障） | 服务不可用、核心业务中断 | 10 分钟内 | 30 分钟内 | 短信 + 企业微信 + 电话 |
| P1（严重异常） | 核心指标恶化、大面积用户受影响 | 30 分钟内 | 2 小时内 | 企业微信 + 电话 |
| P2（一般异常 / 效果劣化） | 局部异常、AI SLO 违规 | 2 小时内 | 24 小时内 | 企业微信 |
| P3（预警） | 资源水位预警、配置异常 | 1 个工作日内 | - | 企业微信 |

### 7.2 AI 特有的强制告警配置

S0/S1 应用必须配置以下告警，缺失则视为可观测不达标：

**推理层告警**（强制）：
- TTFT P99 ≥ 5s → P1
- TTFT P99 ≥ 10s → P0（熔断联动）
- 推理成功率 < 99% → P1
- GPU 显存使用率 > 85% → P1
- KV Cache 耗尽 → P0

**应用层告警**（强制）：
- 会话成功率 < 99% → P1
- Skill 调用成功率（核心 Skill）< 99.5% → P1
- Token 消耗超配额 → P2

**效果层告警**（强制，S0/S1）：
- AI SLO 中任一维度连续 2 次评测下降 > 10% → P2
- 幻觉率 > 10% → P1

### 7.3 告警质量要求

- **禁止告警风暴**：同一 root cause 引发的多个告警必须收敛聚合
- **禁止无主告警**：每条告警必须有明确的 Owner 和处理预案
- **禁止无效告警**：定期清理无人处理的历史告警，告警有效处理率 > 90%
- **告警通知渠道**：必须接入公司统一告警平台，禁止私搭告警渠道

---

## 八、效果评测规范（Eval Harness）

### 8.1 为什么需要单独的效果评测

传统监控无法感知 AI 特有的静默失效：
- **模型漂移**：模型提供商静默升级，相同 Prompt 输出行为改变，成功率指标无异常但效果劣化
- **质量静默下滑**：系统「活着」但 Agent 在系统性给出错误推荐、走偏的推理路径
- **Context 腐化**：随着会话轮次增加，模型对早期约束的遵循能力下降

效果评测是感知这些问题的唯一手段。（来源：Anthropic Engineering，2026-01-09）

### 8.2 核心概念定义

| 概念 | 定义 |
|------|------|
| **Task（任务）** | 单个测试用例，含输入和明确的成功标准 |
| **Trial（试次）** | 对一个 Task 的一次执行（模型输出有随机性，需多次 Trial 得到稳定结论） |
| **Grader（评分器）** | 评分逻辑，一个 Task 可以有多个 Grader，含多条断言 |
| **Transcript（轨迹）** | 一次 Trial 的完整记录，含输出、工具调用顺序、推理步骤、中间结果 |
| **Outcome（结果）** | Trial 结束时环境的最终状态（不是 Agent 说「完成了」，而是实际发生了什么） |
| **Eval Suite（评测集）** | 一组 Task 的集合，用于测量特定能力维度 |

> **关键区分**：Outcome 是环境状态，不是模型输出内容。例如，订机票 Agent 的 Outcome 是「数据库里是否存在预订记录」，而不是「Agent 说了什么」。

### 8.3 强制触发评测的时机

以下情况必须在上线前完成效果评测，且评分不低于上一版本 Baseline：

| 触发事件 | 说明 |
|---------|------|
| Prompt 变更 | 包括 System Prompt、Few-shot 示例变更 |
| 模型版本切换 | 包括提供商静默升级（必须监控模型版本变化） |
| 核心 Skill 逻辑变更 | Skill 入参/出参/调用逻辑变更 |
| AI SLO 效果告警触发 | P2 及以上告警必须触发评测 |
| 定期回归 | S0 应用每两周一次，S1 应用每月一次 |

### 8.4 评测方式

#### 离线评测（Golden Dataset 回归）

- 维护一套 Golden Dataset（核心场景 Task 集合），每次变更后必须跑完
- Dataset 质量要求：覆盖核心场景 + 边界场景 + 对抗性场景（恶意输入、越权指令等）
- 评分维度：任务完成率 + Skill 命中率 + 输出质量（LLM-as-Judge）
- 每次评测结果必须记录并与上一版本对比，出现劣化 > 5% 必须 Block 上线

#### 在线评测（生产流量采样）

- S0/S1 应用必须配置生产流量采样评测（采样率 ≥ 1%）
- 采样 Trace 自动送入 LLM-as-Judge 评分管道
- 评分结果汇入 AI 质量大盘，驱动 SLO 监控

### 8.5 Grader 设计要求

评分器质量直接决定评测结论的可信度，需要遵循以下原则：

1. **禁止只看最终输出**：必须结合 Transcript（轨迹）评估推理路径是否合理，不只是最终答案是否正确
2. **禁止 Agent 自评**：Agent 自评存在系统性偏差（Self-Evaluation Bias），必须使用独立的 Evaluator
3. **Grader 需要定期校准**：每季度检查 Grader 打分结论与人工判断的一致性，偏差 > 15% 时需要重新校准
4. **对抗性测试必须覆盖**：Eval Suite 必须包含越权指令、幻觉诱导、边界输入等对抗性用例

> **业界案例**：METR 研究发现，自动评分器认为 Agent 能完成 ~50 分钟的任务，但人类维护者实际愿意接受的对应约 8 分钟的任务——7 倍的能力高估。根因正是 Grader 设计不当。（来源：METR，2025）

### 8.6 效果评测数据留存

- 每次评测的 Transcript 和评分结果必须保留，留存时长 ≥ 6 个月
- 各版本的 Baseline 必须永久保留（用于历史对比）

---

## 九、可视化大盘规范

### 9.1 三类核心大盘（强制）

| 大盘类型 | 面向对象 | 核心指标 |
|---------|---------|---------|
| **业务大盘** | 产品 / 业务方 | 会话成功率、任务完成率、端到端耗时、用户报错率 |
| **稳定性大盘** | 研发 / SRE | 全链路成功率、TTFT、各层异常率、GPU 资源水位 |
| **AI 质量大盘** | 算法 / 产品 | AI SLO 趋势、Eval 评分趋势、幻觉率、模型版本分布 |

### 9.2 大盘能力要求

- 支持从宏观指标下钻到具体请求、链路、Trace
- 时间维度支持：实时（分钟级）+ 历史趋势（天/周/月）
- 支持按业务线 / 应用 / 模型 / Skill 多维度筛选

---

## 十、强制项与禁止项汇总

### 强制项（MUST）

- 所有 AI 应用必须完成全链路可观测建设，6 层指标 100% 覆盖
- 所有 AI 服务调用必须接入 Langfuse，Trace 覆盖率 100%，禁止断链
- S0/S1 应用关键决策输入输出必须在 Langfuse 持久化记录（脱敏后）
- S0/S1 应用必须配置推理延迟（TTFT/TPOT/E2E）、成功率、GPU 显存告警
- S0/S1 应用必须有 AI SLO 定义和效果评测体系
- 所有应用上线前必须有 Prompt/模型版本的效果 Baseline
- 日志必须使用结构化格式，含 TraceId、SessionId 等必填字段
- 必须建设业务大盘、稳定性大盘、AI 质量大盘三类核心大盘
- S0 应用压测基线距今不超过 90 天

### 禁止项（MUST NOT）

- 禁止无监控上线（无告警 / 无大盘 / 无链路追踪）
- 禁止链路断裂（Trace ID 不透传）
- 禁止日志打印明文敏感信息（密钥、用户隐私、四级数据）
- 禁止四级数据进入任何 Trace / 日志 / 指标字段
- 禁止告警风暴、无主告警、无效告警
- 禁止在没有 Baseline 的情况下上线 Prompt / 模型 / Skill 变更
- 禁止 Agent 自评（必须用独立 Evaluator）
- 禁止只看最终输出评分（必须结合 Transcript 轨迹评估）

---

## 附录：业界参考

| 来源 | 内容 | 链接 |
|------|------|------|
| OpenTelemetry GenAI 语义规范 | Span、Metrics、Events 字段标准（Development 状态） | https://opentelemetry.io/docs/specs/semconv/gen-ai/ |
| Anthropic Engineering：Demystifying Evals | AI Agent 评测体系设计，Task/Trial/Grader/Transcript/Outcome 定义 | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents |
| Anthropic Engineering：Multi-Agent Research | 多 Agent 系统可观测与评测实践 | https://www.anthropic.com/engineering/multi-agent-research-system |
| Harness Engineering 研究报告（内部） | Eval Harness 三层架构，AI SLO 框架，控制论视角 | 内部文档 |
| AI 应用高可用架构规范（内部） | TTFT/TPOT 告警阈值，Langfuse 接入强制要求 | 内部文档 |
