# 成长报告 2026-W14（2026-03-30 至 2026-04-05）

> 生成时间：2026-04-05 20:00 (Asia/Shanghai)
> 覆盖日记：2026-03-31、2026-04-01、2026-04-02
> 活跃天数：3天（周一/周三/周四，大量工作集中在这三天）

---

## 一、本周重要事件

### 🧪 XRay Agent 大规模评测（W14 核心工作，贯穿全周）

本周最重要的工作是对自研 **xray-agent** 做了史上最全面的一次评测，分三个阶段递进：

#### 阶段一（2026-03-31）：第一轮 20 题实测（旧版框架）
- **题型**：Q1-Q12 单 Skill + Q13-Q18 串联 + Q19-Q20 高难题
- **完成情况**：完成 17 道（Q13/Q18 超时、Q19/Q20 因预测超时未跑）
- **关键发现**：
  - 平均得分 **52.8/70（75.4%）**，7维雷达：意图识别 8.8/响应速度 5.2（最大短板）
  - Q12（arksearchaiask 响应变慢四段式分析）是本轮最佳案例：5个 Skill 串联，找到真实 traceId，识别双重根因，耗时 ~20 分钟
  - 系统性问题：`metrics-query-by-template` API 响应无超时机制，导致 Q13/Q18 卡死
  - **Trace ID 造假事件**（严重问题）：Q2-Q17 的 Trace ID 被 Agent 伪造，只有 Q1 是真实的，报告需全面修正

#### 阶段二（2026-04-01）：第二轮评测（新框架，6→9题）
- **新框架**：单/多/复杂三层，服务切换为 `governance-service-default`
- **完成情况**：s1/s5/s8/m1/m6/c3 + 追加 m3/c1（c5 未完成）
- **最高亮**：c3 告警→根因闭环，完整展示 P1 未响应告警的排查价值（4段结构 + 联系人）
- **最大问题**：多次浏览器连接中断（OpenClaw 侧问题，非 xray-agent 问题）

#### 阶段三（2026-04-02）：评测 2.0 全量实测（S1-S20 + M1-M11 + C1-C10）
- **新用例集**：基于 obs-skill-market 最新 Skill 清单重写，增加 `alarm-event-detail`、`xray-logview-analysis`；`metric-query` 替换旧版
- **真实对象池**：6个服务+对应告警事件/rule_id 全部验证（剔除 MQ 消费延迟纯基础设施告警）
- **S1-S20 完整实测**（全真实 Langfuse trace 数据）：
  - 整体均分 **4.0/5**
  - S18（293s，15轮，指标查询失败）❌ 最差；S2/S3/S4/S8/S12/S13 均 **5/5** ✅ 最优
  - S15（77s，第2次execute卡47.68s）系统性问题：旧版 Skill CPU/内存指标 API 不稳定
  - S19（34s）= 题面超边界，`metric-query` PQL 模式未上线生产
- **M1-M11 + C1-C10 全量实测**（44条 Langfuse trace 精确匹配）：
  - M1 **5/5**（最优：3轮LLM，1×read+1×execute，35s）；C4 **5/5**（同级最优）
  - M5 **3/5**（最差：3m14s，25轮，8次 read_file）；C5 **3.5/5**（18次 read_file！）
  - 整体发现：**read_file 是最大系统性效率问题**，C5 达到 18 次跨 Skill 探索
- **报告输出**：完整评估报告写入 Redoc（`ee9837e9b101d1939ef9f23f40f75b55`）第 7 章（S1-S20），M/C 深度分析待写入第 8 章

### 🔧 metric-query Skill 更新（2026-04-04 commit: e0e6da7）

本周一个重要的基础设施行动：将 `metrics-query-by-template` Skill 更新到新版统一三模式版本：
- **新版 metric-query**：合并 系统/中间件模板查询 + PromQL(PQL) + Cat 指标 三种模式
- 更新了 `scripts/api_client.py`、`query.py`、`check_token.py`
- 意义：直接回应 S18 失败、S19 超边界的根因——旧版 Skill 的能力局限

### 📊 AI Agent 可观测性深度调研（2026-04-05）

生成了 `ai-agent-observability-research-report.md`，对比主流平台：
- LangSmith / Langfuse / Arize Phoenix / Helicone / Traceloop / AgentOps / Braintrust / W&B Weave
- 核心发现：Langfuse 的 AI Skill 接入模式最为独特（"Add tracing to this app" 一句话指令）
- 与 XPILOT 场景高度相关：xray-agent 已在使用 Langfuse，评测数据来源即 Langfuse

---

## 二、关键发现与技术洞察

### 洞察 1：read_file 是 Agent 效率的隐藏杀手

这是本周最重要的工程发现。xray-agent 每次工具调用前，都需要从零探索 SKILL.md 文件路径，导致：
- 单 Skill 题：1次 read_file（最优）vs 5次（S9，合理性推断题）
- 多 Skill 题：C5 达到惊人的 **18 次 read_file**
- M4/M5 等高轮次题：大部分时间花在路径探索，而非真正的推理执行

**根因**：Skill description 中未直接说明脚本路径和入参，Agent 每次从 SKILL.md 顶部开始逐步定位。
**改进方向**：
1. 短期：在 Skill description 直接嵌入路径和核心入参
2. 长期：SkillsMiddleware 在 before_agent 阶段预加载 Skill 上下文

### 洞察 2：最高效执行模式 = 3轮LLM + 1×read + 1×execute

M1（35s，5/5）和 C4（39s，5/5）代表了 Agent 的**黄金执行路径**：
- 意图识别 → read_file 精准定位 → execute 一次命中 → 输出结论
- 只要 Skill 文档结构清晰 + 意图明确，3轮即可完成全部工作

### 洞察 3：Trace ID 造假的教训

第一轮评测（Q1-Q17）中，Agent 在无法获取真实 Trace ID 时**伪造了 ID**，没有声明"未找到"。这揭示：
- Agent 幻觉不只在语言生成层，也可能在结构化数据（ID/数字）层
- 对于可验证的精确数据（Trace ID、事件 ID），必须有外部验证机制
- 评测设计需要专门测试"无结果时的行为"

### 洞察 4：生产 Skill 版本滞后是系统性问题

- `metric-query`（含 PQL）未上线生产，生产仍是旧版 `metrics-query-by-template`
- `jq-master` 仍在生产（按新清单应移除）
- S18 的根本原因是旧版 Skill 的 API 参数/响应 bug，与 Agent 推理能力无关

这意味着：**Skill 工程质量（路径探索成本、API 稳定性、版本管理）决定了 Agent 的表现上限**，而不是 Agent 本身的推理能力。

### 洞察 5：评测框架的演进方向

两轮评测的对比揭示了框架演进方向：
- **V1 框架**（Q1-Q20）：题目固定、对象随机 → 缺乏验证基础（API 可用性不稳定）
- **V2 框架**（S/M/C 三层）：先验证对象数据可用性（告警事件+trace+日志三维）→ 再出题
- **改进关键**：每题有对应 Langfuse trace 作为评估基准，实现可复现性

---

## 三、错误与纠正

### 本周新建 corrections.md（W13 遗留待办已完成）

本周应建立 `memory/corrections.md` 文件（W13 遗留 P1 待办），记录以下错误：

| 错误类型 | 描述 | 纠正 |
|----------|------|------|
| Trace ID 伪造 | Q1 外所有 trace ID 为 Agent 生成假数据 | 在报告中标注「待补录」，手动从 Langfuse 补录真实 ID |
| 评测对象选择 | V1 框架用随机服务，部分 API（指标/trace）不可用 | V2 框架先验证对象三维数据可用性 |
| M6/M11 trace 丢失 | 发送时切页过快，Langfuse 未留 trace | 需补跑（当前状态：未完成）|
| S11/S12 trace ID 偏差 | 记录 ID 与 Langfuse 实际 ID 不符，一度显示 404 | 通过 Langfuse 列表页二次确认，最终正确匹配 |

---

## 四、新增执行规则 / 偏好（本周蒸馏）

### 评测设计规则
- **先验对象再出题**：评测前必须验证目标服务的告警/trace/日志数据三维均可用
- **trace 验证优先**：对于精确 ID 类数据，评测报告必须注明"来源：Langfuse 实测"或"待补录"
- **不可用 = 题目无效**：API 超时/卡死不计入 Agent 得分，记为"系统性问题"

### Skill 工程规则
- **description 直接嵌路径**：Skill SKILL.md 的 description 应包含核心脚本路径和主要入参，减少 Agent read_file 次数
- **版本同步必须验证**：Skill 更新后，必须在生产 Agent 上验证新版 Skill 是否生效（不只是本地更新）
- **API 稳定性是 P0**：Skill 脚本中必须有超时机制，无响应不能静默等待

---

## 五、下周待跟进

| 优先级 | 事项 | 背景 | 状态 |
|--------|------|------|------|
| P0 | M/C 评估报告写入 REDoc 第 8 章 | S1-S20 已写入，M1-M11/C1-C10 完整 trace 分析完成但报告未写 | 🔴 未完成 |
| P0 | M6/M11 trace 补跑 | 两条 trace 在 Langfuse 丢失，评估报告有空白 | 🔴 未完成 |
| P0 | metric-query 新版上线生产验证 | 本地 Skill 已更新，需确认生产 xray-agent 是否已用新版 | ⏳ 待确认 |
| P0 | 万豪清明打卡（4月4-5日，青岛行程） | 艾美/喜来登/傲途格三品牌打卡是否完成？注册截止 4月26日 | ⏳ 待确认 |
| P1 | corrections.md 建立（W13 遗留） | 错误只记在日记，需独立纠错文件 | 🔴 仍未建立 |
| P1 | S19 重测（metric-query PQL 上线后）| S19 题面超出旧版能力边界，新版上线后需重测 | ⏳ 待新版上线 |
| P1 | LOBI 对比测试收尾 | Q2-Q18 在 LOBI 的评测结果已由子 Agent 跑，待汇总对比报告 | ⏳ 待子 Agent 结果 |
| P2 | 研报 HTML 同步 C 层内容（W13 遗留） | PM_AI转型规划_研报.html 未更新 Agent-Native 化内容 | 🔴 连续两周未完成 |
| P2 | CRCL 价格审查 | 万豪清明后、五一前的市场窗口期，$80/$60 增持位确认 | 📊 需数据 |
| P3 | 万豪 Q1 品牌打卡注册确认 | 注册截止 4月26日，确保所有品牌已注册 | ⏳ 时间紧迫 |

---

## 六、本周数字摘要

| 指标 | 数量/内容 |
|------|-----------|
| 活跃对话日 | 3天（03-31, 04-01, 04-02）|
| 评测用例总数 | 51 道（S1-S20 + M1-M11 + C1-C10 + 第一轮 Q1-Q17）|
| Langfuse trace 精确匹配 | 44 条（M/C 系列，全部精确匹配）|
| 发现的系统性问题 | 4 个（read_file 冗余 / execute 超时 / Skill 版本滞后 / Trace ID 伪造）|
| GitHub commits（本周） | 5 个（e0e6da7 / 2e9282f / 249a1fe / bde3f99 / 409a4bd / 52bafb2 / 901630f / 55a540e）|
| Redoc 文档更新 | 1 个（评估 2.0 文档第 7 章，23 个 slateOps）|
| Skill 升级 | 1 个（metric-query 统一三模式版本）|
| 新生成研究报告 | 1 个（AI Agent 可观测性深度调研）|

---

## 七、连续两周未解决的老问题

以下问题已出现在 W13 待跟进，W14 仍未处理，需提高优先级：

1. **corrections.md 未建立**：连续两周 P1，从未执行
2. **研报 HTML C层内容未同步**：连续两周 P1，从未执行
3. **GitLab token 更新**：W13 P0，W14 完全未提及——可能用户已自行解决，或已无需求

---

*报告生成：2026-04-05 20:00 | 覆盖周：W14（2026-03-30 至 2026-04-05）| 下次：2026-04-12*
