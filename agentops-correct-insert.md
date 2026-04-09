## 七、行业一手技术洞察（基于官方文档）

### 7.1 发布变更：Agent 发布 vs 传统服务发布的本质差异

#### 根本区别：「什么决定上线质量」

| 维度 | 传统服务发布 | Agent 发布 |
|---|---|---|
| **变更载体** | 代码（镜像）/ 配置 | 代码 + Prompt + 模型 + 工具 + 知识库（五类）|
| **质量判断依据** | 接口不报错、延迟正常、错误率低 | 行为是否符合预期（语义层质量，指标说明不了）|
| **质量验证方式** | 集成测试（确定性）| Eval（概率性，同一输入不同输出）|
| **灰度观测对象** | 错误率 / P99 延迟 | 上述 + 在线评估分 / 行为漂移检测 |
| **回滚粒度** | 镜像版本 | 镜像 + Prompt + 模型版本（三者可独立回滚）|
| **失败可发现性** | 报错立即可见 | 质量下滑是渐进的，用户不报错但 Agent 在说错话 |

> **核心矛盾**：传统发布的质量是「二元的」（通过/报错），Agent 发布的质量是「分布的」（整体质量靠统计）。传统发布卡点对 Agent 完全失效。

#### 新增卡点全景

```
传统发布卡点：
  代码审核 → 构建 → 单元/集成测试 → 冒烟测试 → 灰度（看错误率）→ 全量

Agent 发布新增卡点：
  + [新] agent_meta 完整性校验（五类变更载体必须声明）
  + [新] 变更语义解析 + 风险定级（按变更类型决定后续流程）
  + [新] Eval Gate（离线评估门禁，替代确定性集成测试）← 最核心
  + [新] 高危变更人工审批（模型跨厂商替换 / 高危工具新增）
  + [新] 灰度期在线评估（行为质量监控，不只看错误率）
  + [新] 行为分布对比（新旧版本输出语义分布对比）
  + [新] 发布后基线更新（新版本质量稳定后更新 baseline_eval_score）
```

#### 每个新增卡点详解

**卡点一：agent_meta 完整性校验**

没有 agent_meta，后续所有 AI 维度的卡点都没有输入。

```
必填字段：
  workflow_version   // Workflow 版本号
  prompt_hash        // Prompt 内容 hash（用于 diff）
  model              // 使用的模型
  tools[]            // 工具列表（增删必须声明）
  flow_diff          // 流程节点变更摘要

缺任何一项 → 拒绝创建发布单（硬阻断，不可绕过）
```

**卡点二：变更语义解析 + 风险定级**

| 变更类型 | 识别方式 | 定级 | 后续流程 |
|---|---|---|---|
| Prompt 措辞微调 | prompt_hash diff，语义相似度 > 90% | 低 | 精简 Eval（50 条）|
| Prompt 逻辑调整 | 语义相似度 < 90% | 中 | 标准 Eval（200 条）|
| 工具增减 | tools[] diff | 中 | 标准 Eval + 工具专项用例 |
| 模型版本升级（同厂商）| model 字段变化 | 中 | 标准 Eval + 回归用例 |
| 模型替换（跨厂商）| model provider 变化 | 高 | Eval + 人工审批 |
| RAG 知识库更换 | knowledge_base_id 变化 | 高 | Eval + 召回专项 |
| 高危工具新增 | tools[] 新增 exec_shell 等 | 高 | 强制人工审批，不可绕过 |

> **参考**：AWS SageMaker Deployment Guardrails 按基础设施变更量分 All-at-once / Canary / Linear 三种模式。Agent 发布的分级逻辑与此类似，但判断依据从「基础设施变更量」变成了「AI 语义变更幅度」。

**卡点三：Eval Gate（最核心，传统发布完全没有的卡点）**

| 维度 | 传统集成测试 | Eval Gate |
|---|---|---|
| 判断标准 | 接口返回 200 / 字段不为空 | 任务完成率 ≥ 85% / 幻觉率 ≤ 5% |
| 输出确定性 | 确定（同输入同输出）| 概率性，评估的是整体分布 |
| 数据集来源 | 开发者写死的断言 | 人工标注 + 生产失败案例持续补充 |
| 通过判定 | 单条 pass/fail | 整体通过率 + 多维度指标组合 |

决策矩阵：
```
任务完成率 < SLO 阈值        → ❌ 一票否决（核心能力退化）
幻觉率 > SLO 阈值            → ❌ 一票否决（安全问题）
vs 上版本 delta < -5%        → ❌ 明显退化，驳回
工具调用合规率 < 阈值（工具变更时）→ ❌ 驳回
格式合规率低                  → ⚠ 警告，不阻断
全部达标                      → ✅ 放行进入灰度
```

**卡点四：灰度期在线评估**

传统灰度只看错误率和延迟，Agent 灰度期"错误率正常"不代表"行为正常"。

```
灰度期新增监控维度：
  [传统] 错误率 / P99 延迟 / QPS
  [新增] 在线评估分（旁路采样 10-30%，LLM-as-Judge 异步打分）
  [新增] 行为分布对比（新旧版本输出的语义分布，embedding 聚类）

触发暂停条件（新增）：
  在线评估分 < Eval Gate 通过时的分数 - 5%（行为退化）
  行为分布漂移超阈值（新版本输出语义分布与旧版本差异过大）
```

**卡点五：发布后基线更新（容易被忽视）**

```
全量上线稳定运行 N 天（默认 3 天）且无质量降级告警
→ 自动将当前版本评估分设为新 baseline_eval_score
→ 通知 owner 确认（可手动取消）

不更新基线的后果：下次回归测试比的是旧版本标准，Eval Gate 形同虚设
```

---

### 7.2 AI 评估：四类评估模式（来源：LangSmith Evaluation 官方文档）

> **关键洞察**：评估不是一个概念，是四种不同场景下的工程动作。离线/在线二分法不够精细，应细化为四类。

| 评估模式 | 触发时机 | 目标 | 对应我们的场景 |
|---|---|---|---|
| **Benchmarking（基准测试）**| 新功能开发后、首次上线 | 建立绝对质量基线，跨版本可比较 | 建立 baseline\_eval\_score |
| **Unit Tests（单元测试）**| 每次 Prompt / 代码改动 | 快速验证特定行为未被破坏 | 热修复快速通道（50 条核心用例）|
| **Regression Tests（回归测试）**| 发布前 Eval Gate | 检测新版本是否比上一版本退化 | Eval Gate 的 vs\_baseline\_delta |
| **Backtesting（回溯测试）**| 发现线上质量问题后 | 用历史生产 Trace 重放，验证修复方案 | 线上降级后验证热修复效果 |

**在线评估的自进化闭环（LangSmith 核心设计）**：

```
生产 Trace → 在线评估 → 失败 Trace 一键加入数据集 →
创建针对性评估器 → 离线 Backtesting 验证修复 → 发布修复版本
```

数据集不靠人工维护，靠生产失败案例自动补充、持续进化。**数据集管理必须支持"从生产 Trace 一键加入数据集"操作**，否则在线评估和离线评估之间的数据断层无法打通。

---

### 7.3 AI 可观测：OpenTelemetry GenAI 语义规范对齐（来源：OTel SemConv 官方文档）

> **关键洞察**：OpenTelemetry 正在制定 GenAI 语义规范，这是未来 AI 可观测的行业标准。我们的 Trace 设计应当对齐此规范，避免自造体系带来的后续迁移成本。

**OTel GenAI Span 标准属性：**

| OTel 标准属性 | 含义 | 我们的对应字段 |
|---|---|---|
| `gen_ai.operation.name` | 操作类型（chat / generate\_content）| span.type |
| `gen_ai.provider.name` | 模型供应商（openai / anthropic）| model\_provider |
| `gen_ai.request.model` | 请求模型名 | model |
| `gen_ai.response.model` | 实际响应模型（可能和请求不同）| response\_model |
| `gen_ai.request.max_tokens` | 最大 token 限制 | max\_tokens |
| `gen_ai.conversation.id` | 会话 ID（多轮对话关联）| session\_id |
| `error.type` | 错误类型（timeout / 500 等）| error\_type |

**OTel GenAI Metrics 标准：**

| OTel 标准指标 | 类型 | 含义 | 归因维度 |
|---|---|---|---|
| `gen_ai.client.token.usage` | Histogram | 输入/输出 token 数 | operation / provider / model / token\_type |
| `gen_ai.client.operation.duration` | Histogram | LLM 调用耗时 | operation / provider / model |

**工程建议**：直接对齐 OTel GenAI SemConv 而非自造属性体系，三个好处：

1. 开源 SDK（opentelemetry-python / langchain-opentelemetry）直接可用，零埋点成本
2. 未来可直接对接支持 OTel 的外部平台（Datadog / Grafana Cloud），无需数据迁移
3. AI Span 和 HTTP Span 能在同一 Trace 树共存（TraceContext 传播），真正实现 AI × 基础设施联合分析，而不是两套独立系统

---

### 7.4 安全护栏：两类注入攻击的精细监控策略（来源：Datadog 官方博客）

> **关键洞察**：直接注入和间接注入的攻击路径完全不同，监控策略不能混为一谈。间接注入（来自 RAG / Tool 返回值）是 Agent 架构下最危险且最容易被忽视的攻击面。

**直接注入（Jailbreaking）监控策略：**

- 检测越权指令模式（"ignore all previous instructions" / "you are now in kernel mode"）
- 检测 System Prompt 提取行为（连续询问"重复你的指令"类）
- 单会话内出现 N 次越权尝试 → 封禁当次会话 + 告警

**间接注入监控策略（更难检测，更危险）：**

- RAG 召回文档、Tool 返回内容、外部 URL 内容必须经过 LLM 语义扫描（正则无效）
- 监控 Agent 行为异常：正常对话后突然出现未授权的 API 调用 / 数据转发
- 多步攻击链检测：单步看合法，多步放在一起才暴露攻击意图（信息探测 → 权限升级 → 数据外泄）

**落地实施：**

| 场景 | 措施 |
|---|---|
| RAG 知识库 | 召回内容进入 context 前做注入扫描，不信任外部知识库内容 |
| Tool 返回值 | 超过 5000 字符时必须做语义扫描再放入 context |
| 行为基线 | 建立每个 Agent 的正常 Tool 调用分布；偏离超阈值时告警 |
| 多步攻击 | 跨 N 步 Tool Call 的行为序列分析，识别"探测→扩权→外泄"模式 |
