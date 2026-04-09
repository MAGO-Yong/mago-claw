## 一、为什么要做 AgentOps

### 1.1 Agent 规模化带来的新挑战

2026 年基础技术各团队大规模孵化 Agent，运维侧面临三个结构性问题：

**① 传统监控感知不到 Agent 失效**

传统监控能感知 CPU 高、延迟高、5xx 升高，但无法感知 Agent 正在系统性地给出错误推荐、走偏的推理路径、质量下滑的输出。**"服务活着"和"服务做对了"，在 AI 系统里是两件完全不同的事。**

**② 变更的定义变了**

AI 系统存在三类传统流程完全感知不到的变更：

- Prompt 修改：不在代码里，不触发 CI/CD
- 模型版本静默升级：提供商无声更新，无任何告警
- RAG 知识库更新：内容变了但系统版本没变

**③ 没有评估就没有质量基线**

Agent 输出是非确定性的，不跑评估就不知道"健康状态"是什么样的，也就无法判断上线后是变好还是变差。

### 1.2 我们的独特优势

业界 AgentOps 平台（LangSmith、Langfuse、Arize Phoenix 等）普遍只解决"看得见"的问题，存在三个集体盲区：

| 盲区 | 业界现状 | 我们的优势 |
|------|---------|-----------|
| 发布变更 | 没有平台真正接管企业发布流水线 | **发布入口在手**，ALLIN/Darwin 必须调我们接口创建发布单 |
| AI × 基础设施打通 | 所有平台的观测止步于 AI 链路层 | XRay 同时拥有 AI Trace + HTTP/RPC/中间件数据 |
| 评估→发布硬性闭环 | 评估结果只能"看"，没有平台做到不达标不让上线 | 评估结果可直接驱动发布卡点 |

<redoc-highlight>
核心定位：业界能做"看得见 + 测得准"，我们能做**"管得住"**。
</redoc-highlight>

## 二、AgentOps 的完整领域与竞品对比

AgentOps 覆盖五个领域，**评估是所有领域的数据基础**：

```
发布变更 → AI 可观测 → AI 评估 → 成本治理 → 安全护栏
                           ↑
                 （所有领域依赖评估作为质量传感器）
```

### 2.1 发布变更

| 细分能力 | LangSmith | Coze Loop | Langfuse | Arize Phoenix | 补充参照 |
|---------|-----------|-----------|----------|--------------|--------|
| Agent 版本注册与管理 | ✅ 统一注册中心 | ⚠️ 轻量 | ❌ | ❌ | MLflow ✅ |
| 灰度发布 / 流量分割 | ❌ | ❌ | ❌ | ❌ | Vertex AI ✅ |
| 评估结果作发布门禁 | ❌ | ❌ | ❌ | ❌ | Braintrust ✅ PR 级 |
| Agent 变更语义感知 | ❌ | ❌ | ❌ | ❌ | **全部 ❌ 业界空白** |
| 回滚 | ✅ | ❌ | ❌ | ❌ | Vertex AI ✅ MLflow ✅ |
| 变更与运行期异常自动关联 | ❌ | ❌ | ❌ | ❌ | **全部 ❌ 业界空白** |
| 与企业内部发布平台打通 | ❌ | ❌ | ❌ | ❌ | **全部 ❌ 业界空白** |
| Human-in-the-loop 高危审批 | ✅ | ❌ | ❌ | ❌ | ❌ |

### 2.2 AI 可观测

| 细分能力 | LangSmith | Coze Loop | Langfuse | Arize Phoenix |
|---------|-----------|-----------|----------|--------------|
| 全链路 Trace（Tool/RAG/Memory/子Agent） | ✅ Agent-native | ✅ 覆盖全节点 | ✅ 嵌套Observation | ✅ OTel原生 |
| 异常聚类 / 失败模式自动发现 | ✅ Insights Agent | ❌ | ❌ | ❌ |
| 实时告警 | ✅ | ❌ | ✅ 基础 | ❌ |
| 与基础设施（HTTP/RPC/中间件）打通 | ❌ | ❌ | ❌ | ❌ |

### 2.3 AI 评估

| 细分能力 | LangSmith | Coze Loop | Langfuse | Arize Phoenix |
|---------|-----------|-----------|----------|--------------|
| 离线评估（数据集回放） | ✅ | ✅ | ✅ | ✅ |
| 在线评估（生产流量实时打分） | ✅ | ⚠️ | ✅ | ✅ |
| LLM-as-Judge | ✅ | ✅ | ✅ | ✅ |
| 自定义评估器 | ✅ | ✅ | ✅ | ✅ |
| 人工标注队列 | ✅ | ❌ | ✅ | ✅ |
| 评估结果硬性卡住发布 | ❌ | ❌ | ❌ | ❌ |

<redoc-highlight>
评估能力业界趋于同质化。唯一空白是把评估结果**硬性卡住发布**——大家只做到"看到结果"，没做到"不达标不让上线"。评估是入场券，发布卡点才是护城河。
</redoc-highlight>

### 2.4 成本治理

| 细分能力 | LangSmith | Coze Loop | Langfuse | Arize Phoenix |
|---------|-----------|-----------|----------|--------------|
| Token 消耗追踪 | ✅ | ✅ | ✅ | ✅ |
| 单会话成本估算 | ✅ | ✅ | ✅ | ✅ |
| 成本异常告警 | ✅ | ❌ | ⚠️ | ❌ |
| 成本归因到业务/团队 | ⚠️ | ❌ | ❌ | ❌ |
| Token 超限自动熔断 | ❌ | ❌ | ❌ | ❌ |

### 2.5 安全护栏

| 细分能力 | LangSmith | Coze Loop | Langfuse | Arize Phoenix |
|---------|-----------|-----------|----------|--------------|
| 输入检测（敏感信息/越权） | ❌ | ❌ | ❌ | ❌ |
| 输出过滤（幻觉/违规内容） | ❌ | ❌ | ❌ | ❌ |
| 运行时行为熔断 | ❌ | ❌ | ❌ | ❌ |
| 工具调用权限控制 | ❌ | ❌ | ❌ | ❌ |
| 审计日志 | ✅ 企业版 | ❌ | ✅ | ❌ |

<redoc-highlight>
护栏是**业界集体空白**，ToB 企业场景强刚需，差异化潜力最大。
</redoc-highlight>

## 三、差异化定位

| 领域 | 业界现状 | 我们的切入点 |
|------|---------|------------|
| 发布变更 | 各平台极薄，CI/CD 评测 → Runtime → 监控三段断裂 | 发布入口在手 + 变更数据（RCM）+ AI 语义层，三合一 |
| AI 可观测 | AI 链路完整，但止步于 AI 层 | AI Trace × 基础设施（HTTP/RPC/中间件）打通，结构性做不到 |
| AI 评估 | 能力同质，缺硬性卡点 | 评估结果直接驱动发布门禁，形成硬约束 |
| 成本治理 | 只能看，不能干预 | 成本超限熔断 + 团队级归因 |
| 安全护栏 | 集体空白 | 输入/输出/行为三层防护，企业级治理 |

## 四、与 AgentDev 平台的 AI Native 联动

### 4.1 现状与问题

当前两个平台的关系：ALLIN/Darwin 调接口创建发布单 → 发布单在我们这里 → 服务跑在我们这里。

问题是**变更粒度停在"服务级"**，Workflow 内部发生了什么（Prompt 改了什么、模型版本、工具集变化）发布平台完全不知道。

| 层级 | 谁知道 | 谁不知道 |
|------|--------|---------|
| 服务维度（镜像/实例/配置） | 发布平台 ✅ | ALLIN ❌ |
| Workflow 语义（Prompt/模型/工具） | ALLIN ✅ | 发布平台 ❌ |
| 运行期行为（Trace/质量/异常） | XRay ✅ | 两边都不完整 |

### 4.2 核心机制：Agent 元数据中心

两个平台共享的唯一数据源，贯穿 Agent 全生命周期**持续更新**（不是静态注册表，而是动态状态中心）：

<redoc-columns>
<redoc-column ratio="0.5">

**创建时写入**

- agent\_id、owner、intent
- capability\_boundary（允许/禁止的操作）
- slo\_definition（质量目标）
- embed\_config（埋点配置）

</redoc-column>
<redoc-column ratio="0.5">

**运行时实时刷新**

- current\_version、prompt\_hash
- last\_eval\_score（最近评估分）
- last\_anomaly\_at（最近异常时间）
- health：normal / degraded / critical

</redoc-column>
</redoc-columns>

### 4.3 全生命周期联动：五个阶段

#### 阶段一：创建期 · 注册即治理

<redoc-columns>
<redoc-column ratio="0.48">

**AgentDev（ALLIN）**

- 创建 Workflow（节点结构、工具列表、模型选择）
- 发送 `workflow.created` 事件，携带 agent\_id、owner、intent

</redoc-column>
<redoc-column ratio="0.04">

</redoc-column>
<redoc-column ratio="0.48">

**AgentOps（发布平台 + XRay）**

- 自动注册 Agent 元数据（写入元数据中心）
- 下发观测埋点配置（XRay App ID、采样率）
- 引导定义 SLO（task\_success\_rate、幻觉率、延迟阈值）

</redoc-column>
</redoc-columns>

#### 阶段二：开发期 · 基线先行

<redoc-columns>
<redoc-column ratio="0.48">

**AgentDev（ALLIN）**

- 迭代 Workflow（修改 Prompt、调整节点逻辑）
- 发送 `workflow.updated` 事件，携带变更 diff

</redoc-column>
<redoc-column ratio="0.04">

</redoc-column>
<redoc-column ratio="0.48">

**AgentOps（XRay + 评估）**

- **创建即采集**：开发态 Trace 实时上报，不等上线
- 用测试数据集跑离线 Eval，建立质量基线快照
- 更新元数据：baseline\_eval\_score

</redoc-column>
</redoc-columns>

#### 阶段三：发布期 · 评估门禁

<redoc-columns>
<redoc-column ratio="0.48">

**AgentDev（ALLIN）**

- 调接口创建发布单，新增携带 `agent_meta` 字段：

```
workflow_version: "v2.3.1"
prompt_hash:      "a3f9cd..."
model:            "gpt-4o"
tools:            ["search", "db_query"]
flow_diff:        { 新增节点 B }
```

</redoc-column>
<redoc-column ratio="0.04">

</redoc-column>
<redoc-column ratio="0.48">

**AgentOps（发布平台）**

- 写入变更语义记录（发布单绑定 agent\_meta）
- 触发 **Eval Gate**：用历史数据集回放新版本
  - task\_success\_rate ≥ 85% → 放行
  - task\_success\_rate < 85% → 驳回 + 附评估报告
- 灰度：默认 1% 流量先上，监控异常后扩量
- 高危工具（如 exec\_shell）强制人工审批

</redoc-column>
</redoc-columns>

**发布期双向事件：**

| 方向 | 事件 | 说明 |
|------|------|------|
| ALLIN → AgentOps | `deploy.requested` | 发起发布，触发 Eval Gate |
| AgentOps → ALLIN | `eval.gate.passed` | 评估通过，放行发布 |
| AgentOps → ALLIN | `eval.gate.failed` | 评估不通过，驳回 + 附报告 |

#### 阶段四：运行期 · 持续治理

<redoc-columns>
<redoc-column ratio="0.48">

**AgentDev（ALLIN）**

- 接收 AgentOps 推送的质量告警
- 查看异常归因（关联到哪次变更）
- 响应回滚建议（人工审批后执行）
- 在 ALLIN 侧可见该版本质量状态标记

</redoc-column>
<redoc-column ratio="0.04">

</redoc-column>
<redoc-column ratio="0.48">

**AgentOps（XRay + 评估）**

- 生产流量持续 Eval 采样（LLM-as-Judge）
- 质量下滑 → 自动关联最近变更记录
- AI Trace × 基础设施异常联合分析
- 分级处置：
  - 轻：ALLIN 打标 ⚠ 质量异常
  - 中：推送回滚建议单（人工审批）
  - 重：P0 自动触发回滚（需提前授权）

</redoc-column>
</redoc-columns>

**运行期双向事件：**

| 方向 | 事件 | 说明 |
|------|------|------|
| AgentOps → ALLIN | `quality.degraded` | 质量下滑告警 + 关联变更版本 |
| AgentOps → ALLIN | `rollback.suggested` | 回滚建议（人工审批） |
| AgentOps → ALLIN | `slo.violated` | SLO 违规告警 |
| ALLIN → AgentOps | `workflow.deprecated` | 下线，触发归档 |

#### 阶段五：退役期 · 沉淀知识

Agent 下线后，AgentOps 归档完整历史（版本记录、评估分、异常记录），沉淀为下一个同类 Agent 创建时的参考案例。

## 五、分阶段落地路径

| 阶段 | 目标 | 关键交付 |
|------|------|---------|
| **Phase 1（近期）** <br/> 数据层打通 | 两个平台"认识彼此" | <split/> · ALLIN 发布时传 agent\_meta 字段 <split/> · AgentOps 建 Agent 元数据中心 <split/> · 观测埋点前置到创建期 <split/> · 评估基线在测试期建立 |
| **Phase 2（中期）** <br/> 评估层接入 | AgentOps "能判断好坏" | <split/> · 发布期 Eval Gate 上线 <split/> · SLO 写入元数据，持续对齐 <split/> · 在线评估：生产流量实时打分 <split/> · AI Trace × 基础设施异常关联 |
| **Phase 3（远期）** <br/> 治理闭环 | AgentOps 从"观测"变"治理" | <split/> · 双向事件总线建设 <split/> · 质量下滑自动关联变更 + 回流 ALLIN <split/> · 安全护栏：三层实时拦截 <split/> · 成本超限熔断 + 团队级归因 |

## 六、核心主张

<redoc-highlight>
**传感器（持续评估）+ 执行器（发布卡点/护栏/回滚）= 负反馈闭环**<br/><br/>
AgentDev 负责"定义 Agent 是什么"，AgentOps 负责"治理 Agent 怎么跑"——两平台共同维护 Agent 全生命周期状态。<br/><br/>
让 Agent 不只是"跑起来"，而是**"跑得稳、跑得好、跑得省"**。
</redoc-highlight>
