### 6.1.9 行业一手技术洞察补充（基于官方文档）

#### 柱子三：AI 可观测 — OpenTelemetry GenAI 语义规范（OTel SemConv）

**来源**：opentelemetry.io/docs/specs/semconv/gen-ai/

> **关键洞察**：OpenTelemetry 正在制定 GenAI 语义规范，这是未来 AI 可观测的行业标准。我们的 Trace 设计应当对齐此规范，确保与开源生态互通，也保留接入外部可观测平台的可能。

**OTel GenAI Span 标准属性（对照我们的 Trace 设计）：**

| OTel 标准属性 | 含义 | 我们的对应字段 |
|---|---|---|
| `gen_ai.operation.name` | 操作类型（chat / generate\_content）| span.type |
| `gen_ai.provider.name` | 模型供应商（openai / anthropic）| model\_provider |
| `gen_ai.request.model` | 请求模型名 | model |
| `gen_ai.response.model` | 实际响应模型名（可能和请求不同）| response\_model |
| `gen_ai.request.max_tokens` | 最大 token 限制 | max\_tokens |
| `gen_ai.conversation.id` | 会话 ID（多轮对话关联）| session\_id |
| `error.type` | 错误类型（timeout / 500 等）| error\_type |

**OTel GenAI Metrics 标准（对照我们的成本治理）：**

| OTel 标准指标 | 类型 | 含义 | 归因维度 |
|---|---|---|---|
| `gen_ai.client.token.usage` | Histogram | 输入/输出 token 数 | operation / provider / model / token\_type |
| `gen_ai.client.operation.duration` | Histogram | LLM 调用耗时 | operation / provider / model |

**工程建议**：直接对齐 OTel GenAI SemConv，而非自定义 Span 属性体系。好处有三：
1. 开源 SDK（opentelemetry-python / langchain-opentelemetry）直接可用，零埋点成本
2. 未来可直接对接支持 OTel 的外部平台（Datadog / Grafana Cloud / Honeycomb），不需要数据迁移
3. AI Trace 与 HTTP Span 在同一 Trace 树中共存（TraceContext 传播），实现真正的 AI × 基础设施联合 Trace

**对 XRay 的具体意义**：XRay 目前是 HTTP/RPC 粒度的 Trace。AI Trace 对齐 OTel SemConv 后，LLM Span 和 HTTP Span 可以在同一 Trace 中共存，而不是两套独立系统——这才能真正做到"AI 质量下滑 → 自动关联下游 RPC 超时"。

---

#### 柱子二：AI 评估 — 四类评估模式精细化

**来源**：docs.langchain.com/langsmith/evaluation

> **关键洞察**：评估不是一个概念，是四种不同场景下的工程动作。我们的离线/在线二分法需要细化为四类，每类对应不同触发时机和目标。

| 评估模式 | 触发时机 | 目标 | 对应我们的场景 |
|---|---|---|---|
| **Benchmarking（基准测试）** | 新功能开发后、首次上线 | 建立绝对质量基线，跨版本可比较 | 建立 baseline\_eval\_score |
| **Unit Tests（单元测试）** | 每次 Prompt / 代码改动 | 快速验证特定行为未被破坏 | 热修复快速通道（50 条核心用例）|
| **Regression Tests（回归测试）** | 发布前 Eval Gate | 检测新版本是否比上一版本退化 | Eval Gate 的 vs\_baseline\_delta |
| **Backtesting（回溯测试）** | 发现线上质量问题后 | 用历史生产 Trace 重放，验证修复方案 | 线上降级后验证热修复效果 |

**在线评估的自进化闭环（LangSmith 核心设计）**：

在线评估 → 失败 Trace 一键加入数据集 → 创建针对性评估器 → 离线 Backtesting 验证修复 → 发布修复版本

这个闭环使数据集不靠人工维护，靠生产失败案例自动补充、持续进化。**我们的数据集管理必须支持"从生产 Trace 一键加入数据集"操作**，否则在线评估和离线评估之间的数据断层无法打通。

---

#### 柱子五：安全护栏 — 两类注入攻击的精细监控策略

**来源**：datadoghq.com/blog/monitor-llm-prompt-injection-attacks/

> **关键洞察**：直接注入和间接注入的攻击路径完全不同，监控策略不能混为一谈。尤其是间接注入（来自 RAG / Tool 返回值），是 Agent 架构下最危险且最容易被忽视的攻击面。

**直接注入（Jailbreaking）监控策略：**

- 检测越权指令模式（"ignore all previous instructions" / "you are now in kernel mode"）
- 检测 System Prompt 提取行为（连续询问"重复你的指令"类）
- 触发策略：单会话内出现 N 次越权尝试 → 封禁该用户当次会话 + 告警

**间接注入监控策略（更难检测，更危险）：**

- RAG 召回文档、Tool 返回内容、外部 URL 内容必须经过 LLM 语义扫描（正则无效）
- 监控 Agent 行为异常：正常对话后突然出现未经授权的 API 调用 / 数据转发
- 多步攻击链检测：单步看合法，多步放在一起才暴露攻击意图（信息探测 → 权限升级 → 数据外泄）

**我们的落地补充：**

| 场景 | 措施 |
|---|---|
| RAG 知识库 | 召回内容进入 context 前做注入扫描，不信任外部知识库内容 |
| Tool 返回值 | 超过 5000 字符时必须做语义扫描再放入 context |
| 行为基线 | 建立每个 Agent 的正常 Tool 调用分布；偏离超过阈值时告警 |
| 多步攻击 | 跨 N 步 Tool Call 的行为序列分析，识别"探测→扩权→外泄"模式 |
