# 方向二：Agent Native — 三种服务形态（细化版）

---

## 核心命题再明确

> 方向一解决的是"AgentOps 平台能做什么"
> 方向二解决的是"AgentOps 平台以什么姿态提供服务"
>
> 本质区别：
> - 传统思路：人 → 打开 Web 平台 → 点击操作
> - Agent Native：Agent → 调用 Skill / 订阅事件 → 自动完成
>
> 当业务 Agent 本身就是 AI 生产出来的（vibe coding / Claw 开发），
> 它的 OPS 也应该能被 AI 消费——对话触发、Skill 调用、事件驱动。

---

## 形态一：Ops Agent（对话式治理）

### 定位
**给研发/SRE 在 Claw 里直接对话使用**，聚合所有 AgentOps 能力，有上下文记忆，
可以跨多轮对话完成复杂 OPS 任务。

不是简单的 API 封装，而是有推理能力的 Agent：
- 能主动关联信息（"你问质量下滑，我帮你顺便看最近的变更"）
- 能给出建议（"评估分 73%，我建议先回滚，原因是..."）
- 能主动追问（"你要发布 v1.9，但 SLO 还没定义，现在要设吗？"）

---

### 能力设计：意图 × 执行链路

#### 查询类（直接返回，无需确认）

**意图 1：看 Agent 当前状态**
```
用户：帮我看看客服退款助手线上怎么样

Ops Agent 执行链路：
① 查 Agent 元数据（当前版本 / health / 最近部署时间）
② 查 SLO 达成情况（近 24h 各指标 vs 阈值）
③ 查活跃告警（未处理的告警列表）
④ 查近 7 天评估分趋势

输出格式：
┌──────────────────────────────────────┐
│ 客服退款助手 · v1.8.3 · ⚠ 降级       │
├──────────────────────────────────────┤
│ 评估分：73.2%（基线 85.3%，下滑 14%）│
│ SLO：任务完成率 73% < 85% ⚠           │
│ 活跃告警：2 条（质量降级 + 成本异常） │
│ 最近变更：昨天 14:02 Prompt 修改      │
├──────────────────────────────────────┤
│ 建议：质量下滑与昨天 Prompt 修改高度  │
│ 相关，建议回滚或热修复。              │
└──────────────────────────────────────┘
```

**意图 2：分析质量下滑原因**
```
用户：最近质量下滑是什么原因

Ops Agent 执行链路：
① 查评估分趋势（找到下滑起始时间点）
② 查该时间点前后的变更记录（关联变更）
③ 查同期 Trace 失败模式聚类（找失败规律）
④ 查基础设施同期异常（XRay：RPC/DB/模型接口）
⑤ 查知识库（历史是否有类似案例）
⑥ 综合推理：输出根因分析 + 置信度 + 参考案例

输出格式：
根因分析（置信度 87%）：
  昨天 14:02 的 Prompt 修改后 30min，评估分从 85% 降至 73%
  失败模式：63% 的失败样本都是"工具调用顺序错误"（未先查订单就处理退款）
  历史参考：2025-12 有类似案例，根因是 Prompt 修改破坏了工具调用前置条件
  
建议：
  1. 立即回滚至 v1.8.2（修复时间预计 5min）
  2. 或 Prompt 热修复：在退款步骤前增加「必须先调用 order_query」的约束
  
  你想怎么做？
```

**意图 3：查 Trace 链路**
```
用户：帮我查一下 trace_a3f9cd8e 这条请求

Ops Agent 执行链路：
① 查 Trace 详情（各 Span 耗时 / 状态）
② 识别失败 Span（标红 + 详情）
③ 查同一 Agent 近期同类失败（是否系统性问题）
④ 关联变更（该 Trace 发生时是哪个版本）

输出：瀑布图摘要（文字版）+ 失败定位 + 关联信息
```

**意图 4：查成本**
```
用户：客服退款助手今天花了多少钱，正常吗

Ops Agent 执行链路：
① 查今日 Token 消耗和费用
② 对比历史基线（同比 / 环比）
③ 分析异常原因（哪个维度超了：单次请求过长 / 高频调用 / 模型升级）

输出：
  今日消耗：¥318（基线 ¥130，超出 145%）⚠
  超支原因：平均每次请求 5,214 tokens（基线 1,820），context 过长
  建议：检查是否有不必要的历史对话堆积，考虑开启 context 压缩
```

---

#### 变更类（必须二次确认，明确告知影响范围）

**意图 5：触发发布**
```
用户：我想发布客服退款助手 v1.9.0

Ops Agent 执行链路：
① 查 v1.9.0 的 agent_meta（是否完整）
② 查 SLO 定义（是否已有）
③ 查绑定数据集（是否已有）
④ 预估 Eval Gate 耗时

确认提示：
  发布前检查：
  ✓ agent_meta 完整
  ✓ SLO 已定义（任务完成率≥85%）
  ✓ 数据集已绑定（refund_qa_v3，248条）
  ✓ 变更摘要：Prompt 修改退款判断逻辑（中风险）
  
  预计流程：Eval Gate（~4min）→ 灰度 1%（15min）→ 扩量
  
  确认发起发布？[是 / 否]

用户：是

Ops Agent：
  已发起。Eval Gate 进行中，预计 4 分钟后出结果，我来播报。
  
  [4分钟后]
  Eval Gate 通过 ✅ 评估分 88.4%（基线 85.3%）
  正在切 1% 灰度流量，15 分钟后看情况...
  
  [15分钟后]
  灰度正常，无异常。是否扩量至 10%？[是 / 否 / 继续观察]
```

**意图 6：触发回滚**
```
用户：帮我回滚客服退款助手

Ops Agent：
  确认回滚信息：
  · 当前版本：v1.8.3（评估分 73.2% ⚠）
  · 目标版本：v1.8.2（评估分 85.3%，上线时间 3天前）
  · 回滚方式：快速通道（灰度窗口 5min）
  · 预计完成：约 10 分钟
  
  确认回滚？[是 / 否]

用户：是

Ops Agent：
  回滚中... 1% 流量已切至 v1.8.2
  [5min后] 无异常，已全量。评估分恢复至 84.1%，接近基线。
  已归档本次事件（根因：Prompt 修改，MTTR 23min）
```

**意图 7：触发评估**
```
用户：帮我对 v1.9.0 跑一次离线评估

Ops Agent：
  使用数据集：refund_qa_v3（248条，上次使用：今天 14:02）
  评估器：GPT-4o Judge + 规则评估器
  预计耗时：约 4 分钟
  
  开始？[是 / 否]

用户：是

Ops Agent：
  评估中... [进度播报]
  
  结果：
  总分 88.4% ✅（基线 85.3%）
  · 任务完成率：91.2%（+5.9% vs 基线）
  · 幻觉率：2.8%（优于基线 3.1%）
  · 失败样本：22 条（主要是边界用例）
  
  达到 Eval Gate 标准，可以发布。要现在发布吗？
```

---

#### 高危操作（不执行，引导走正规流程）

```
用户：帮我跳过 Eval Gate 直接发布

Ops Agent：
  抱歉，Eval Gate 不可跳过，这是保障线上质量的核心卡点。
  
  如果是紧急情况，有两个选项：
  1. 走热修复快速通道（仅限 Prompt 修改，Eval 缩减到 50 条核心用例，约 1min）
  2. 申请人工审批覆盖（需要 owner + oncall 双人签字，留审计记录）
  
  你需要哪种方式？
```

---

### 上下文记忆设计

Ops Agent 在多轮对话中保持记忆，不需要用户重复说明背景：

```
第1轮：用户说"帮我看客服退款助手"
        → Ops Agent 记住当前操作对象是"客服退款助手"

第2轮：用户说"那帮我跑个评估"
        → 不需要再说是哪个 Agent，Ops Agent 知道
        
第3轮：用户说"通过了吗？发布吧"
        → 知道是刚才评估的那个版本，直接发起发布确认
```

**记忆范围：**
- 当前操作的 Agent 上下文（直到用户切换）
- 本轮对话中已确认的操作结果（不需要再查）
- 用户偏好（如"我喜欢看趋势图"→ 下次自动附上）

**记忆边界：**
- 敏感操作每次必须重新确认（不因"记住"而跳过确认）
- 跨会话记忆写入数据底座 Layer 3（用户偏好 / 操作习惯）

---

### 与 Claw 的集成方式

```
研发在 Claw 中 @ AgentOps 或直接对话
          │
          ▼
    agentops-skill（Claw 侧安装）
          │
          ▼
    Ops Agent（AgentOps 侧运行）
    · 调用各 Skill 获取数据
    · 调用数据底座 API 获取上下文
    · 访问知识库获取历史案例
          │
          ▼
    AgentOps 平台核心能力
```

**集成形态：**
- 作为 Claw Skill 安装：研发 @ 即用，无需打开 Web 平台
- 支持频道订阅：某个 Agent 出告警，直接推到研发的 Claw 频道
- 支持主动推送：Eval Gate 结果、灰度状态、质量恢复 → 主动发消息

---

## 形态二：Skill 化能力（原子能力包）

### 定位
**给其他 Agent 调用的原子操作封装**，无状态、有明确 Schema、可组合。

与 Ops Agent 的区别：
- Ops Agent 是"有脑子的人"，知道上下文，能推理，面向研发对话
- Skill 是"工具箱里的工具"，做一件具体的事，面向 Agent 调用

---

### Skill 全集设计

#### Skill 1：`agentops.meta.get` — 查询 Agent 元数据
```yaml
描述: 获取指定 Agent 的完整元数据画像
输入:
  agent_id: string（必填）
  fields: array（可选，默认返回全量）
    可选值: [identity, engineering, ai_attrs, capability, state, slo]
输出:
  agent_id: string
  health: normal | degraded | critical | unknown
  current_version: string
  owner: string
  ones_service_id: string      # 关联的 ONES 服务
  xray_app_id: string          # 观测数据存储空间
  git_repo: string             # 代码仓库
  model: string                # 当前使用的模型
  tools: array                 # 工具列表
  slo: object                  # SLO 定义
  last_deploy_at: timestamp
  active_alerts: array         # 活跃告警列表
错误码:
  AGENT_NOT_FOUND: Agent 未注册
  PERMISSION_DENIED: 无查询权限
典型调用方: Ops Agent / 诊断 Agent / vibe coding AI / CI-CD Agent
```

#### Skill 2：`agentops.health.snapshot` — 获取健康快照
```yaml
描述: 获取 Agent 当前健康状态快照（轻量，适合决策前快速判断）
输入:
  agent_id: string
  window: 1h | 6h | 24h（默认 1h）
输出:
  health: normal | degraded | critical
  eval_score: float             # 当前评估分
  eval_score_delta: float       # vs 基线的变化
  slo_status:
    task_success_rate: {current, target, status}
    hallucination_rate: {current, target, status}
    p99_latency: {current, target, status}
  active_alert_count: int
  last_change: {type, at, risk_level}  # 最近一次变更
  cost_today: float             # 今日成本（¥）
典型调用方: 任意 Agent 在调用该 Agent 前的"看一眼"
设计意图: 用最小代价判断"现在能不能/该不该调用这个 Agent"
```

#### Skill 3：`agentops.trace.query` — 查询 Trace 链路
```yaml
描述: 查询 Agent 的 Trace 数据
输入:
  agent_id: string（可选，和 trace_id 二选一）
  trace_id: string（精确查询）
  filter:
    status: ok | error | slow（可选）
    time_range: {start, end}
    min_latency_ms: int（慢请求过滤）
  limit: int（默认 20）
  include_spans: bool（是否返回完整 Span 树，默认 false）
输出:
  traces: array
    - trace_id, agent_id, status, latency_ms
    - tokens_total, cost, timestamp
    - spans（include_spans=true 时返回）:
        span_id, type(llm/tool/rag/memory), name
        status, latency_ms, input_hash, output_summary
        error_message（失败时）
错误码:
  TRACE_NOT_FOUND
  TIME_RANGE_TOO_LARGE（最大查询窗口 7 天）
典型调用方: Ops Agent / XRay 告警诊断 Agent / 排障 Agent
```

#### Skill 4：`agentops.eval.run` — 触发离线评估
```yaml
描述: 对指定 Agent 版本触发离线评估，返回评估报告
输入:
  agent_id: string
  version: string（可选，默认当前最新版本）
  dataset_id: string（可选，默认绑定的数据集）
  mode: standard | quick | full
    standard: 默认，200条，完整评估器组合
    quick: 50条核心用例，仅规则评估器（热修复用）
    full: 全量数据集 + 全评估器（大版本用）
  async: bool（默认 false，true 时立即返回 job_id）
输出（同步）:
  eval_id: string
  total_score: float
  dimensions:
    task_success_rate: {score, threshold, passed}
    hallucination_rate: {score, threshold, passed}
    format_compliance: {score, threshold, passed}
    vs_baseline_delta: {delta, threshold, passed}
  passed: bool
  failed_samples: array（前 10 条失败样本）
  duration_seconds: int
输出（异步，async=true）:
  job_id: string
  estimated_seconds: int
  # 完成后通过事件总线推送 eval.completed 事件
典型调用方: Ops Agent / CI-CD Agent / 发布 Agent
```

#### Skill 5：`agentops.eval.gate.check` — 查询 Eval Gate 状态
```yaml
描述: 查询某次发布的 Eval Gate 结果（已有记录则直接返回，无需重跑）
输入:
  agent_id: string
  version: string
输出:
  status: passed | failed | pending | not_run
  eval_report_id: string（有记录时）
  passed_at: timestamp
  score: float
  dimensions: object
  can_override: bool  # 是否允许人工审批覆盖
错误码:
  NO_EVAL_RECORD: 该版本未跑过 Eval Gate
典型调用方: 发布 Agent / Ops Agent / CI-CD Agent
```

#### Skill 6：`agentops.deploy.trigger` — 触发发布/回滚
```yaml
描述: 触发 Agent 发布或回滚
输入:
  agent_id: string
  action: deploy | rollback
  version: string（deploy 时为目标版本，rollback 时为回滚目标，默认上一版）
  canary_strategy: standard | fast | aggressive
    standard: 1%→10%→50%→100%（默认）
    fast: 1%→100%（回滚快速通道）
    aggressive: 直接100%（仅限紧急且已授权）
  confirm_token: string  # 必填，防止误触发（由 confirm 接口生成）
输出:
  deploy_id: string
  status: started
  estimated_completion_seconds: int
  # 过程通过事件总线推送 deploy.progress 事件
副作用: 真实触发发布流程，不可逆（除非再次触发回滚）
权限要求: 需要 agent 的 deploy 权限
确认机制: 必须先调用 agentops.deploy.confirm 获取 confirm_token
错误码:
  EVAL_GATE_NOT_PASSED: Eval Gate 未通过
  APPROVAL_REQUIRED: 需要人工审批
  PERMISSION_DENIED
典型调用方: Ops Agent（用户二次确认后）/ CI-CD Agent（自动化流水线）
```

#### Skill 7：`agentops.cost.query` — 查询成本数据
```yaml
描述: 查询 Agent Token 消耗和费用数据
输入:
  agent_id: string（可选，不传则查全局）
  time_range: {start, end}
  granularity: hour | day | week | month（默认 day）
  group_by: agent | team | model | tool（可选，多选）
输出:
  total_cost_cny: float
  total_tokens: int
  breakdown: array（按 group_by 维度）
  trend: array（按 granularity 维度，{timestamp, cost, tokens}）
  anomalies: array（异常时间点 + 疑似原因）
  budget_status:
    monthly_budget: float
    monthly_used: float
    usage_rate: float
    predicted_monthly_total: float  # 按当前趋势预测
典型调用方: Ops Agent / 报表 Agent / 成本治理 Agent
```

#### Skill 8：`agentops.slo.status` — 查询 SLO 达成情况
```yaml
描述: 查询 Agent SLO 各维度的当前达成情况
输入:
  agent_id: string
  window: 1h | 6h | 24h | 7d（默认 24h）
输出:
  overall_status: meeting | at_risk | violated
  dimensions:
    task_success_rate:
      current: float
      target: float
      status: meeting | at_risk | violated
      trend: up | down | stable
    hallucination_rate: {current, target, status, trend}
    p99_latency_ms: {current, target, status, trend}
    cost_per_session: {current, target, status, trend}
  history: array（按 window 粒度的历史数据点）
典型调用方: 监控 Agent / Ops Agent / 报表 Agent
```

#### Skill 9：`agentops.alert.query` — 查询告警事件
```yaml
描述: 查询 Agent 的告警事件列表
输入:
  agent_id: string（可选）
  status: open | resolved | all（默认 open）
  severity: warning | critical | emergency（可选）
  time_range: {start, end}（默认最近 24h）
  limit: int（默认 10）
输出:
  alerts: array
    - alert_id, agent_id, severity, type
    - title, description
    - triggered_at, resolved_at
    - related_change: {version, change_type, changed_at}  # 关联变更
    - suggested_action: string
典型调用方: Ops Agent / 告警诊断 Agent / 值班 Agent
```

#### Skill 10：`agentops.knowledge.query` — 查询知识库
```yaml
描述: 从 AgentOps 知识库查询历史案例、SOP、Prompt 调优记录
输入:
  query: string（自然语言查询）
  type: case | sop | prompt_tuning | baseline（可选，默认全类型）
  agent_id: string（可选，限定某个 Agent）
  top_k: int（默认 5）
输出:
  results: array
    - type: case | sop | prompt_tuning
    - title: string
    - summary: string
    - relevance_score: float
    - content: object（根据 type 不同结构不同）
      case: {symptom, root_cause, resolution, mttr}
      sop: {steps, applicable_conditions}
      prompt_tuning: {version_from, version_to, eval_delta, lesson}
典型调用方: Ops Agent / 诊断 Agent / 开发辅助 Agent
```

---

### Skill 设计通用规范

**输入规范：**
- 所有 Skill 支持自然语言参数（Skill 内部做意图解析，转为结构化输入）
- 必填参数缺失时返回结构化错误，说明缺什么、怎么补
- 不确定的参数给出候选值（如 agent_id 不确定时，返回名称匹配的列表）

**输出规范：**
- 查询 Skill 始终返回结构化 JSON，便于 Agent 程序化消费
- 同时提供 `summary` 字段（自然语言摘要），便于 Ops Agent 直接转述给用户
- 错误返回：`{error_code, message, suggestion, retry_able}`

**权限规范：**
- 查询类 Skill：只要有 Agent 的查看权限即可
- 变更类 Skill（deploy/rollback）：需要 deploy 权限 + confirm_token
- 敏感数据 Skill（trace with full IO）：需要更高权限，默认脱敏

**幂等性：**
- 查询 Skill 天然幂等
- 变更 Skill 通过 confirm_token 保证幂等（同一 token 不重复执行）

---

## 形态三：事件总线（双向事件驱动）

### 定位
**系统间自动驱动，不依赖人主动触发**。
AgentDev 侧（ALLIN/Darwin）和 AgentOps 侧通过事件解耦联动，
形成"AgentDev 定义 → AgentOps 治理 → AgentDev 响应"的自动闭环。

---

### 事件全集设计（完整版）

#### AgentDev → AgentOps（上行事件：业务 Agent 侧驱动）

**事件 1：`workflow.created`**
```yaml
触发时机: ALLIN/Darwin 创建新 Workflow
Payload:
  agent_id: string
  owner: string
  intent: string
  framework: string（ALLIN | Darwin | ARKAI）
  tools: array
  model: string
  workflow_version: string
AgentOps 响应:
  · 自动注册元数据（Layer 1 全量初始化）
  · 关联工程资产（自动匹配 ONES 服务 / XRay App）
  · 下发埋点配置
  · 引导 SLO 定义（推送引导消息给 owner）
  · 推送欢迎通知："客服退款助手已注册 AgentOps，建议完成 SLO 配置"
```

**事件 2：`workflow.updated`**
```yaml
触发时机: ALLIN/Darwin 保存 Workflow 变更
Payload:
  agent_id: string
  workflow_version: string
  prompt_hash: string
  flow_diff: object（新增/删除/修改的节点）
  change_summary: string（研发填写的变更说明，可选）
AgentOps 响应:
  · 更新 Layer 2（prompt_hash / flow_diff / updated_at）
  · 评估变更幅度（diff Prompt hash）
  · 变更幅度 > 30% → 推送提醒："检测到大幅 Prompt 变更，建议触发基线评估"
  · 开发期 Trace 埋点配置保持 100% 采样
```

**事件 3：`workflow.deprecated`**
```yaml
触发时机: ALLIN/Darwin 下线 Workflow
Payload:
  agent_id: string
  reason: string（可选）
AgentOps 响应:
  · 检查活跃告警（有则推送提醒，等待确认）
  · 元数据状态更新为 deprecated
  · Trace 数据进入归档流程（默认保留 90 天）
  · 触发知识沉淀：提炼最佳 Prompt 版本 / 历史案例 → 写入知识库
  · 推送归档通知
```

**事件 4：`deploy.requested`**
```yaml
触发时机: ALLIN/Darwin 发起发布申请
Payload:
  agent_id: string
  version: string
  agent_meta:
    workflow_version: string
    prompt_hash: string
    model: string
    tools: array
    flow_diff: object
    change_risk: low | medium | high（研发自评，可选）
  requester: string（发布申请人）
AgentOps 响应:
  · 校验 agent_meta 完整性
  · 触发变更语义解析（自动判断风险等级）
  · 触发 Eval Gate
  · 写入变更记录
  · 高风险变更 → 同时触发人工审批流程
```

---

#### AgentOps → AgentDev（下行事件：AgentOps 侧驱动）

**事件 5：`eval.gate.passed`**
```yaml
触发时机: Eval Gate 评估通过
Payload:
  agent_id: string
  version: string
  eval_report_id: string
  total_score: float
  dimensions: object
  passed_at: timestamp
AgentDev 响应:
  · 发布流程继续（进入灰度阶段）
  · 在 ALLIN 发布单上更新状态
  · 通知申请人
```

**事件 6：`eval.gate.failed`**
```yaml
触发时机: Eval Gate 评估不通过
Payload:
  agent_id: string
  version: string
  eval_report_id: string
  total_score: float
  failed_dimensions: array（哪些维度不达标）
  failed_samples: array（前 5 条失败样本）
  suggested_fix: string（AI 生成的修复建议）
AgentDev 响应:
  · 发布流程终止
  · 在 ALLIN 发布单上标记"Eval Gate 未通过"
  · 通知申请人（附评估报告 + 修复建议）
  · 研发修复后可直接重新提交（不需要重新人工审批）
```

**事件 7：`deploy.progress`**
```yaml
触发时机: 灰度发布各阶段状态变化
Payload:
  agent_id: string
  deploy_id: string
  stage: canary_1pct | canary_10pct | canary_50pct | full | paused | completed
  metrics:
    error_rate: float
    eval_score: float（在线评估当前分）
    p99_latency_ms: int
  paused_reason: string（仅 stage=paused 时）
AgentDev 响应:
  · 在 ALLIN 发布单上实时更新状态
  · 通知申请人（可配置：仅关键节点通知 or 全程通知）
```

**事件 8：`quality.degraded`**
```yaml
触发时机: 在线评估检测到质量下滑超阈值
Payload:
  agent_id: string
  severity: warning | critical | emergency
  current_score: float
  baseline_score: float
  delta: float
  window: string（检测窗口，如 1h）
  related_change:
    version: string
    change_type: string
    changed_at: timestamp
    confidence: float（根因关联置信度）
  failed_pattern: string（失败模式描述）
AgentDev 响应:
  · 在 ALLIN 该 Agent 页面打标 ⚠
  · 通知 owner（含根因关联信息）
  · critical/emergency 时通知 oncall
```

**事件 9：`rollback.suggested`**
```yaml
触发时机: 质量异常根因已关联到某次变更，建议回滚
Payload:
  agent_id: string
  current_version: string
  suggested_rollback_version: string
  reason: string
  evidence:
    quality_delta: float
    related_change_version: string
    correlation_confidence: float
    failed_patterns: array
  urgency: normal | urgent（urgent 时推送更紧迫的通知）
AgentDev 响应:
  · 在 ALLIN 推送回滚建议卡片（含一键回滚按钮）
  · 等待 owner 确认（urgent 时同时通知 oncall）
  · 超过 30min 未响应 → 升级告警
```

**事件 10：`slo.violated`**
```yaml
触发时机: 某个 SLO 指标持续违规（超过配置的容忍时长）
Payload:
  agent_id: string
  violated_dimensions: array
    - dimension: string
      current: float
      target: float
      violation_duration_minutes: int
  overall_health: degraded | critical
AgentDev 响应:
  · 推送 SLO 违规通知（含各维度详情）
  · critical 时同时触发 oncall
```

**事件 11：`cost.threshold.exceeded`**
```yaml
触发时机: 成本超过预设阈值（L3 模型降级或 L4 限流时）
Payload:
  agent_id: string
  threshold_type: daily | monthly
  current_cost: float
  threshold: float
  action_taken: model_downgrade | rate_limit | circuit_break
  action_detail: string
AgentDev 响应:
  · 通知 owner（告知已自动采取的降级措施）
  · 提供手动恢复的操作指引
```

**事件 12：`security.alert`**
```yaml
触发时机: 安全护栏触发（输入/输出/行为层拦截）
Payload:
  agent_id: string
  alert_type: prompt_injection | privilege_escalation | data_leak | dangerous_tool_call
  severity: medium | high | critical
  request_trace_id: string
  blocked_content_summary: string（脱敏摘要）
  user_id: string（触发的用户，脱敏）
AgentDev 响应:
  · 推送安全告警（含拦截详情）
  · high/critical 时通知安全团队
  · critical 时自动暂停该 Agent 对该用户的服务
```

---

### 事件总线技术演进路径

```
Phase 1（近期）: HTTP Webhook
  · AgentOps 推送到 ALLIN 注册的 Webhook URL
  · 简单、快速落地
  · 缺点：无重试保证、无顺序保证
  · 适合：事件量小、可容忍少量丢失的场景

Phase 2（中期）: 内部 MQ（消息队列）
  · 接入公司内部消息队列（如 Kafka/RocketMQ）
  · 支持重试、顺序消费、死信队列
  · AgentDev 侧订阅感兴趣的事件 Topic
  · 适合：高可靠、高并发场景

Phase 3（远期）: 统一 Agent 事件总线
  · 跨平台（不只是 ALLIN/Darwin，所有 Agent 框架都能接入）
  · 标准化事件 Schema（CloudEvents 规范）
  · 支持事件过滤、路由、转换
  · 事件历史可查、可回放（用于排障和审计）
  · 终态：Agent 世界的"消息中枢"
```

---

### 三种形态的组合场景

**场景 A：研发用 Claw vibe coding，AI 辅助 OPS**
```
研发用 Claw 写完 Agent 代码
  → 发布前问 Ops Agent："这个版本可以发布吗？"
  → Ops Agent 调用 agentops.eval.run（Skill）
  → 返回评估结果 + 建议
  → 研发确认后，Ops Agent 调用 agentops.deploy.trigger（Skill）
  → 事件总线推送 deploy.progress 事件
  → Ops Agent 实时播报灰度状态
  → 无需打开任何 Web 平台
```

**场景 B：告警自动触发 → 自动诊断 → 推送处置建议**
```
在线评估检测质量下滑
  → 事件总线发出 quality.degraded 事件
  → 触发诊断 Agent（调用 agentops.trace.query + agentops.knowledge.query）
  → 诊断 Agent 输出根因分析
  → 事件总线发出 rollback.suggested 事件
  → ALLIN 推送回滚建议卡片给研发
  → 研发点击"回滚"→ 触发 agentops.deploy.trigger（Skill）
  → 全程无需人打开平台，只在需要人决策时出现在研发面前
```

**场景 C：业务 Agent 调用前先"看一眼"**
```
推荐 Agent 需要调用 NLP Agent 的接口
  → 调用 agentops.health.snapshot（Skill）
  → 发现 NLP Agent health=degraded，eval_score 只有 73%
  → 推荐 Agent 决策：降级处理（不调用 NLP Agent，用规则代替）
  → 而不是盲目调用后才发现下游质量差
```

**场景 D：新 Agent 创建即自动纳入治理**
```
研发在 ALLIN 创建新 Workflow
  → 自动触发 workflow.created 事件
  → AgentOps 自动注册元数据 / 关联工程资产 / 下发埋点
  → Ops Agent 推送给研发："你的 Agent 已注册，建议完成以下配置：
      1. 定义 SLO（参考同类 Agent 的建议值）
      2. 绑定评估数据集（已为你推荐 3 个相关数据集）"
  → 研发在 Claw 里对话完成配置
  → 从第一行代码开始，就在 AgentOps 治理下
```
