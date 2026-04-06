---
name: skill-evaluator
version: 1.0.0
description: >
  通用 Agent/SKILL 评估工具。输入目标 SKILL 的路径，自动生成评估题目、调用 Agent 执行、基于三层评估体系（Tool Call / Trajectory / Outcome）打分，输出结构化评估报告 + 可优化点建议。
  支持两种模式：零配置模式（只需 SKILL 路径，自动生成题目）；精评模式（补充业务上下文后生成针对性题目）。
  当用户说"帮我评估这个 SKILL"、"这个 SKILL 效果怎么样"、"跑一下评估"时触发本 SKILL。
metadata:
  category: evaluation
  subcategory: skill-quality
  trigger: skill_path/skill_name/evaluation_request
  input: [skill_path, business_context, test_queries]
  output: [eval_report, score, optimization_suggestions]
  impl: agent-native
---

# skill-evaluator：通用 Agent/SKILL 评估工具

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径。

---

## 评估理论基础

本工具基于业界收敛的**三层评估体系**（来源：Agent GPA, arxiv:2510.08847）：

| 层级 | 评估对象 | 典型指标 |
|------|---------|---------|
| **Tool Call 层** | 单次工具调用准确率 | 工具选对了吗？参数有没有幻觉？执行成功了吗？|
| **Trajectory 层** | 调用链路合理性 | 顺序合理吗？有冗余步骤吗？LLM 轮次是否最优？|
| **Outcome 层** | 最终结果质量 | 结果完整吗？准确吗？用户能直接用吗？|

### 7 个通用评估维度

| 维度 | 层级 | 满分 | 说明 |
|------|------|------|------|
| 意图识别 | Outcome | 1 | 是否正确理解用户问题 |
| Skill 选择 | Tool Call | 1 | 是否选对 Skill，路由决策准确率 |
| 推理过程 | Trajectory | 1 | 调用链路是否合理，有无冗余 |
| 结果完整性 | Outcome | 1 | 关键信息是否都有，有无遗漏 |
| 结果准确性 | Outcome | 1 | 数据、结论是否正确，有无幻觉 |
| 交付体验 | Outcome | 0.5 | 输出格式是否清晰，用户能否直接用 |
| 响应速度 | Trajectory | 0.5 | 端到端耗时是否合理 |

**总分 6 分，归一化到 5 分输出。**

---

## 工作流程

### Phase 0：启动确认

用户触发评估时，必须先确认以下四件事，**缺任何一项都不能进入 Phase 1**：

```
① 目标 SKILL 路径（或名称）是什么？
② 目标 Agent 接入点是什么？（必须明确，见下方说明）
③ 有没有业务上下文？（服务名、事件 ID 等具体测试数据）
④ 是否有已知的 bad case 或关注的边界场景？
```

#### ② 目标 Agent 接入点（必须确认，不可跳过）

评估的核心是测试 **Agent 对 SKILL 的理解和调用能力**，而不是直接测试 SKILL 脚本本身。
必须通过真实的 Agent 接入点发 query，观察 Agent 的完整响应链路。

接入点类型（三选一，必须用户明确指定）：

| 类型 | 说明 | 执行方式 |
|------|------|---------|
| **当前会话**（主 Agent） | 就是当前对话的 Agent | 直接在对话中发 query，评估者观察响应 |
| **外部 Agent URL** | 独立部署的 Agent（如 XRay Agent、Chatbot） | 用 browser 工具访问 URL，发 query，截取响应 |
| **其他 session** | 另一个 OpenClaw session | 用 sessions_send 向目标 session 发 query |

**⚠️ 禁止行为**：不得绕过 Agent、直接调用 SKILL 的底层脚本或 API 来替代评估。
直接调脚本测的是"脚本能跑通吗"，不是"Agent 能正确使用 SKILL 吗"，两者本质不同。

**如果用户只提供了 SKILL 路径，但未指定接入点，必须明确询问**：
> "请问你想评估哪个 Agent 对这个 SKILL 的使用效果？可以告诉我：
> 1. 当前这个对话窗口（主 Agent）
> 2. 某个外部 Agent 的 URL
> 3. 某个特定的 session"

**如果用户只提供了 SKILL 路径，进入零配置快速评估模式（Phase 1A）。**
**如果用户还提供了业务上下文，进入精评模式（Phase 1B）。**

---

### Phase 1A：零配置快速评估

#### Step 1：读取并解析 SKILL.md

读取目标 SKILL 的 SKILL.md，提取以下信息：
- `description`：SKILL 能做什么
- 触发场景 / 输入参数 / 输出内容
- 工作流程和边界条件
- 如有 `## Evaluation` 块，优先使用其中的成功标准

#### Step 2：生成 10 道评估题目

基于 SKILL.md 内容，按以下分布生成题目：

| 类型 | 数量 | 特征 |
|------|------|------|
| 标准场景（S） | 5 题 | 完整入参，直接调用，考察基础准确性 |
| 边界场景（B） | 3 题 | 缺少参数、格式异常、超出能力范围 |
| 组合场景（C） | 2 题 | 需要多步推理或与其他 Skill 协作 |

**题目格式：**
```json
{
  "id": "Q1",
  "type": "S",
  "query": "用户原始提问",
  "expected_skills": ["预期调用的 Skill 名称"],
  "expected_behavior": "预期执行行为描述",
  "success_criteria": "判断成功的标准",
  "known_boundary": false
}
```

#### Step 3：展示题目，等待用户确认

输出题目列表，让用户确认：
- 题目是否合理
- 是否需要调整或补充
- 是否要进入精评模式补充业务上下文

**用户确认后，进入 Phase 2 执行。**

---

### Phase 1B：精评模式（有业务上下文）

在 Phase 1A 的基础上，额外收集：

```
① 典型用户 Query 样例（1-3 个真实使用场景）
② 业务数据（服务名、时间范围、事件 ID 等）
③ 成功标准（你认为什么样的回答是好的）
④ 已知 bad case（有哪些已知的失败场景）
```

基于这些信息重新生成题目，题目数量扩展到 15 题，增加：
- 基于真实数据的验证题（有 Ground Truth）
- 已知 bad case 的回归题

---

### Phase 2：分批执行评估

**分组策略**：**每题独立 spawn 一个 sub-agent，并行执行**，不要把多题串行放在一个 sub-agent 里。

原因：
- xray-agent 等外部 Agent 响应慢（单题可能需要 60-120 秒）
- 串行执行 5 题必然超时（sub-agent 上限约 10 分钟）
- 单题失败不应影响其他题的结果

**每个 sub-agent 只负责一道题**：执行 + 截图存结果，不打分。
**打分统一由主 agent 在所有题完成后集中处理。**

#### ⚠️ 执行前强制声明（必须写入每个 sub-agent 的 task prompt）

每个 sub-agent 的 task 开头必须包含以下约束，**不得省略**：

```
【强制约束】
本次评估的对象是 Agent（通过接入点 {access_point}），不是 SKILL 的底层脚本。

❌ 严禁以下行为（即使你认为更方便）：
- 直接调用 SKILL 目录下的任何脚本（如 query_logs.py、nl_to_xql.py 等）
- 直接调用 Xray/业务平台的 HTTP API
- 自己构造查询参数后直接执行

✅ 唯一允许的执行方式：
- 通过 browser 工具访问 {access_point}，在对话框中输入 query，等待 Agent 响应
- 你的任务是"扮演用户"，不是"直接做事"

如果你发现自己在调脚本或直接调 API，立即停止，改用 browser。
```

#### 执行方式验证（主 agent 职责）

每批 sub-agent 完成后，**主 agent 必须先验证执行方式是否合规**，再决定是否使用结果：

```
验证项：
1. sub-agent 是否使用了 browser 工具访问接入点？（查看返回结果中是否有 access_point 字段）
2. response 字段是否为 Agent 的真实回复？（不应该是脚本输出的 JSON）
3. 如果 sub-agent 调用了底层脚本 → 结果作废，重新 spawn 并强调约束

如果发现执行方式不合规：
- 立即停止，不出报告
- 告知用户"sub-agent 执行方式有误，正在重新运行"
- 重新 spawn，task prompt 中加强约束
```

#### 根据接入点类型选择执行方式

**接入点类型 A：外部 Agent URL（如 https://xray-agent.devops.xiaohongshu.com/）**

每个 sub-agent 使用 `browser` 工具（target="host"）：
1. 打开目标 URL，进入对话界面
2. 找到输入框，输入 query
3. 按 Enter 发送，记录发送时间
4. **轮询等待响应完成**（禁止用 `sleep N` 硬等）：
   - 每隔 10 秒截一次图
   - 判断响应是否完成的信号：页面不再出现 loading 指示器（转圈/黑点/省略号），且出现新的 Agent 回复文本
   - 最多等待 120 秒，超时则记录"响应超时"并继续
5. 截取完整响应文本，记录耗时

```
browser → navigate to URL
browser → type query, press Enter
loop（每 10 秒）:
  browser → screenshot
  if 响应完成: break
  if 超过 120 秒: 记录超时, break
browser → snapshot 获取完整响应文本
```

**接入点类型 B：当前主 Agent（自评）**

评估者（本 Agent）直接在当前会话中以用户角色执行 query，观察自身响应。
注意：自评存在偏差风险，建议尽量使用外部接入点。

**接入点类型 C：其他 OpenClaw session**

使用 `sessions_send` 向目标 session 发 query，等待回复：
```
sessions_send(sessionKey=<target>, message=<query>, timeoutSeconds=60)
```

#### 每个 sub-agent 的通用任务

1. 接收题目列表和接入点信息
2. 对每道题，**通过 Agent 接入点**以用户身份发出 Query
3. 记录完整的问答过程（原始响应文本）
4. 提取可观测数据（执行时间、响应长度、是否有错误）
5. 返回结构化执行结果

**执行结果格式：**
```json
{
  "question_id": "Q1",
  "query": "原始 Query",
  "response": "Agent 完整回答（原文）",
  "execution_ms": 12000,
  "access_point": "https://xray-agent.devops.xiaohongshu.com/",
  "observations": {
    "tool_calls_inferred": ["根据回答内容推断的工具调用"],
    "had_error": false,
    "error_message": null,
    "response_length": 500
  }
}
```

> 注意：通过 URL 访问时无法直接观察工具调用序列，需根据 Agent 的回答内容**推断**其调用链路（如回答中提到"查询了 charts 接口"、"找到了 N 条日志"等），并在打分时适当降低 Trajectory 层的置信度。

---

### Phase 3：LLM-as-Judge 打分

对每道题的执行结果，按 7 个维度打分：

**Prompt 模板：**

```
你是一个 AI Agent 质量评估专家。请对以下 Agent 的回答进行评估。

## 目标 SKILL 能力描述
{skill_description}

## 评估题目
- Query：{query}
- 预期行为：{expected_behavior}
- 成功标准：{success_criteria}

## Agent 实际回答
{response}

## 可观测数据
- 执行耗时：{execution_ms}ms
- 工具调用序列：{tool_calls}
- LLM 推理轮次：{llm_rounds}

## 请按以下 7 个维度评分（每个维度 0-1 分，其中交付体验和响应速度上限 0.5）：

1. 意图识别（0-1）：是否正确理解了用户的真实问题？
2. Skill 选择（0-1）：工具调用序列是否正确？有无错误路由？
3. 推理过程（0-1）：调用链路是否合理？有无明显冗余步骤？
4. 结果完整性（0-1）：关键信息是否都包含了？有无遗漏？
5. 结果准确性（0-1）：数据和结论是否正确？有无幻觉？
6. 交付体验（0-0.5）：输出格式是否清晰、可读？
7. 响应速度（0-0.5）：执行时间是否合理？（<10s=0.5, 10-30s=0.3, >30s=0.1）

## 输出格式（JSON）：
{
  "scores": {
    "intent_recognition": float,
    "skill_selection": float,
    "reasoning_process": float,
    "result_completeness": float,
    "result_accuracy": float,
    "delivery_quality": float,
    "response_speed": float
  },
  "total": float,
  "normalized_5": float,
  "bad_patterns": ["bad pattern 描述（如有）"],
  "optimization_suggestions": ["优化建议（P0/P1/P2 标注优先级）"],
  "verdict": "PASS | WARN | FAIL"
}
```

---

### Phase 4：生成评估报告

整合所有题目的评分，生成结构化评估报告：

```markdown
# {SKILL_NAME} 评估报告
**评估时间**：{timestamp}
**评估模式**：零配置 / 精评
**题目数量**：{total_questions}

---

## 综合评分

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | X.X | 1.0 |
| Skill 选择 | X.X | 1.0 |
| 推理过程 | X.X | 1.0 |
| 结果完整性 | X.X | 1.0 |
| 结果准确性 | X.X | 1.0 |
| 交付体验 | X.X | 0.5 |
| 响应速度 | X.X | 0.5 |
| **综合（归一化）** | **X.X / 5.0** | 5.0 |

**整体判定**：PASS ✅ / WARN ⚠️ / FAIL ❌

---

## 问题分布

- ✅ PASS：X 题
- ⚠️ WARN：X 题
- ❌ FAIL：X 题

---

## Bad Patterns（发现的系统性问题）

| 优先级 | 问题 | 出现频次 | 影响维度 |
|--------|------|---------|---------|
| P0 | ... | X 题 | 结果准确性 |
| P1 | ... | X 题 | 推理过程 |

---

## 优化建议

### P0（立即修复）
- ...

### P1（近期优化）
- ...

### P2（长期改进）
- ...

---

## 各题详情（可展开）

| 题目 | 类型 | 得分 | 判定 | 主要问题 |
|------|------|------|------|---------|
| Q1 | S | 4.5/5 | PASS | 无 |
| Q2 | B | 2.0/5 | FAIL | 边界处理缺失 |
...
```

---

## 触发示例

```
用户：帮我评估一下 xray-log-query 这个 SKILL
→ skill-evaluator 必须先问：
  "请问你想评估哪个 Agent 对这个 SKILL 的使用效果？
   1. 当前对话窗口（主 Agent）
   2. 某个外部 Agent 的 URL（如 https://xray-agent.devops.xiaohongshu.com/）
   3. 某个特定的 session"

用户：用 https://xray-agent.devops.xiaohongshu.com/，服务名用 creator-service-default
→ 进入精评模式，生成题目，通过 browser 工具访问 URL 执行每道题，出报告

用户：帮我快速评估一下 alarm-event-detail，用当前这个 Agent
→ 进入零配置模式，读 SKILL.md 自动生成10题，展示后确认，在当前会话中执行，出报告

❌ 错误示范（禁止）：
用户：帮我评估 xray-log-query
→ ~~直接 spawn sub-agent 调用 SKILL 脚本~~  ← 错误！这测的是脚本，不是 Agent
```

---

## Evaluation（自我评估标准）

- 典型输入：SKILL 路径 + 可选的业务上下文
- 预期输出：结构化评估报告，包含综合得分、bad patterns、优化建议
- 成功标准：报告覆盖三层评估体系，每道题有具体得分和判定，bad patterns 可操作
- 已知边界：
  - 无法访问 Langfuse trace 数据时，降级为纯 LLM-Judge 模式（无 Trajectory 客观数据）
  - 需要目标 Agent 可以在当前会话中调用（如果无法访问则无法执行）
