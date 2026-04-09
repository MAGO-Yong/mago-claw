### 6.2 方向二：Agent Native

> 方向二解决"AgentOps 平台以什么姿态提供服务"。
>
> 传统思路：人 → 打开 Web 平台 → 点击操作。
> Agent Native：Agent → 调用 Skill / 订阅事件 → 自动完成。
>
> 当业务 Agent 本身就是 AI 生产出来的，它的 OPS 也应该能被 AI 消费——对话触发、Skill 调用、事件驱动。

三种服务形态：**Ops Agent（对话式）** + **Skill 化能力（原子操作）** + **事件总线（双向驱动）**

---

#### 6.2.1 形态一：Ops Agent（对话式治理）

**定位**：给研发/SRE 在 Claw 里直接对话使用，聚合所有 AgentOps 能力，有上下文记忆，可跨多轮对话完成复杂 OPS 任务。不是简单 API 封装，而是有推理能力的 Agent：能主动关联信息、给出建议、主动追问。

**七类意图 × 执行链路：**

| 意图类型 | 示例 | Ops Agent 执行 |
|---|---|---|
| 查 Agent 状态 | "帮我看看客服退款助手线上怎么样" | 查元数据 + SLO 达成 + 活跃告警 + 近 7 天评估分趋势 |
| 分析质量下滑 | "最近质量下滑是什么原因" | 查评估分趋势 + 关联变更 + 失败模式聚类 + 基础设施同期异常 + 知识库历史案例 |
| 查 Trace 链路 | "帮我查 trace_a3f9cd8e 这条请求" | 查 Trace 详情 + 识别失败 Span + 同类失败聚合 + 关联版本 |
| 查成本 | "今天花了多少钱，正常吗" | 查今日 Token/费用 + 对比历史基线 + 分析异常原因 |
| 触发发布 | "我想发布 v1.9.0" | 预检（meta/SLO/数据集）+ 二次确认 + 触发 Eval Gate + 灰度播报 |
| 触发回滚 | "帮我回滚" | 确认回滚信息（当前版本/目标版本/方式）+ 二次确认 + 执行 + 事后验证 |
| 触发评估 | "帮我跑一次离线评估" | 确认数据集和评估器 + 执行 + 结果解读 + 顺势询问是否发布 |

**高危操作处理**（不执行，引导走正规流程）：
```
用户：帮我跳过 Eval Gate 直接发布

Ops Agent：
  Eval Gate 不可跳过。如有紧急情况，有两个选项：
  1. 热修复快速通道（仅限 Prompt 修改，Eval 缩减到 50 条，约 1min）
  2. 人工审批覆盖（需 owner + oncall 双人签字，留审计记录）
```

**上下文记忆设计**：
- 记住当前操作的 Agent（第 1 轮说完，后续无需重复）
- 记住本轮已确认的操作结果（不重复查询）
- 跨会话记忆写入数据底座 Layer 3（用户偏好/操作习惯）
- 边界：敏感操作每次必须重新确认，不因"记住"而跳过确认

**与 Claw 的集成方式**：
- 作为 Claw Skill 安装：研发 @ 即用，无需打开 Web 平台
- 支持频道订阅：某个 Agent 出告警，直接推到研发的 Claw 频道
- 支持主动推送：Eval Gate 结果、灰度状态、质量恢复 → 主动发消息

---

#### 6.2.2 形态二：Skill 化能力（原子能力包）

**定位**：给其他 Agent 调用的原子操作封装，无状态、有明确 Schema、可组合。

与 Ops Agent 的区别：Ops Agent 是"有脑子的人"，知道上下文，能推理，面向研发对话；Skill 是"工具箱里的工具"，做一件具体的事，面向 Agent 程序化调用。

**10 个 Skill 全集：**

| Skill | 功能 | 典型调用方 |
|---|---|---|
| `agentops.meta.get` | 获取 Agent 完整元数据画像 | Ops Agent / 诊断 Agent / CI-CD Agent |
| `agentops.health.snapshot` | 获取 Agent 健康状态快照（轻量）| 任意 Agent 调用前的"看一眼" |
| `agentops.trace.query` | 查询 Trace 链路（支持精确/过滤查询）| Ops Agent / 排障 Agent |
| `agentops.eval.run` | 触发离线评估，返回报告 | Ops Agent / CI-CD Agent |
| `agentops.eval.gate.check` | 查询某版本 Eval Gate 状态（有记录则直接返回）| 发布 Agent |
| `agentops.deploy.trigger` | 触发发布/回滚（需 confirm_token）| Ops Agent / CI-CD Agent |
| `agentops.cost.query` | 查询 Token 消耗和费用数据 | 报表 Agent / 成本治理 Agent |
| `agentops.slo.status` | 查询 SLO 各维度达成情况 | 监控 Agent / 报表 Agent |
| `agentops.alert.query` | 查询告警事件列表 | 告警诊断 Agent / 值班 Agent |
| `agentops.knowledge.query` | 查询历史案例/SOP/Prompt 调优记录 | Ops Agent / 诊断 Agent |

**Skill 设计通用规范**：
- 输入：支持自然语言参数（内部做意图解析），必填参数缺失时返回结构化错误+修复指引
- 输出：结构化 JSON（便于程序化消费）+ `summary` 字段（便于 Ops Agent 转述用户）
- 错误返回：`{error_code, message, suggestion, retry_able}`
- 权限：查询类仅需查看权限；变更类（deploy/rollback）需 deploy 权限 + confirm_token
- 幂等性：变更 Skill 通过 confirm_token 保证幂等（同一 token 不重复执行）

---

#### 6.2.3 形态三：事件总线（双向事件驱动）

**定位**：系统间自动驱动，不依赖人主动触发。AgentDev 和 AgentOps 通过事件解耦联动，形成"AgentDev 定义 → AgentOps 治理 → AgentDev 响应"的自动闭环。

**12 个事件全集：**

**AgentDev → AgentOps（上行，4 个）：**

| 事件 | 触发时机 | AgentOps 自动响应 |
|---|---|---|
| `workflow.created` | 创建新 Workflow | 注册元数据 / 关联工程资产 / 下发埋点 / 引导 SLO 定义 |
| `workflow.updated` | 保存 Workflow 变更 | 更新 Layer 2 / 评估变更幅度 / 大幅变更时提醒基线重建 |
| `workflow.deprecated` | 下线 Workflow | 归档数据 / 触发知识沉淀 / 提炼最佳实践写入知识库 |
| `deploy.requested` | 发起发布申请 | 校验 agent_meta / 变更语义解析 / 触发 Eval Gate / 高风险触发人工审批 |

**AgentOps → AgentDev（下行，8 个）：**

| 事件 | 触发时机 | AgentDev 响应 |
|---|---|---|
| `eval.gate.passed` | Eval Gate 通过 | 发布流程继续，更新发布单状态，通知申请人 |
| `eval.gate.failed` | Eval Gate 不通过 | 发布终止，推送评估报告 + AI 修复建议，可直接重新提交 |
| `deploy.progress` | 灰度各阶段状态变化 | 实时更新 ALLIN 发布单，通知申请人 |
| `quality.degraded` | 在线评估检测质量下滑 | ALLIN 打标 ⚠，通知 owner（含根因关联信息）|
| `rollback.suggested` | 质量异常已关联到某次变更 | 推送回滚建议卡片（含一键回滚按钮）|
| `slo.violated` | SLO 指标持续违规 | 推送 SLO 违规通知，critical 时触发 oncall |
| `cost.threshold.exceeded` | 成本超预设阈值 | 通知 owner 已自动采取的降级措施 + 手动恢复指引 |
| `security.alert` | 安全护栏触发拦截 | 推送安全告警，critical 时通知安全团队 |

**事件总线技术演进路径：**

```
Phase 1（近期）: HTTP Webhook
  · 简单快速落地，缺点：无重试保证、无顺序保证

Phase 2（中期）: 内部 MQ（Kafka/RocketMQ）
  · 支持重试、顺序消费、死信队列
  · AgentDev 侧订阅感兴趣的 Topic

Phase 3（远期）: 统一 Agent 事件总线
  · 跨平台（所有 Agent 框架都能接入）
  · 标准化事件 Schema（CloudEvents 规范）
  · 事件历史可查、可回放（用于排障和审计）
```

---

#### 6.2.4 三种形态组合场景

**场景 A：研发 Claw vibe coding，AI 辅助 OPS**

研发写完 Agent → 在 Claw 问 Ops Agent "可以发布吗" → Ops Agent 调 Skill 跑 Eval → 返回结果 + 建议 → 研发确认 → Ops Agent 调 Skill 发布 → 事件总线播报灰度状态 → 全程无需打开 Web 平台

**场景 B：告警自动触发 → 自动诊断 → 推送处置建议**

在线评估检测质量下滑 → 事件总线发出 `quality.degraded` → 触发诊断 Agent（调 Trace 和知识库 Skill）→ 输出根因分析 → 事件总线发出 `rollback.suggested` → ALLIN 推送回滚建议卡片 → 研发点击回滚 → 全程无需人打开平台，只在需要决策时出现

**场景 C：业务 Agent 调用前先"看一眼"**

推荐 Agent 需要调用 NLP Agent → 先调 `agentops.health.snapshot` → 发现 health=degraded，eval_score 73% → 推荐 Agent 降级处理（不调用，用规则代替）→ 而不是盲目调用后才发现下游质量差

**场景 D：新 Agent 创建即自动纳入治理**

研发在 ALLIN 创建新 Workflow → 自动触发 `workflow.created` → AgentOps 自动注册/关联/下发埋点 → Ops Agent 推送给研发：SLO 配置引导 + 推荐 3 个相关数据集 → 研发在 Claw 里对话完成配置 → 从第一行代码开始就在 AgentOps 治理下
