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

用户触发评估时，先确认三件事：

```
① 目标 SKILL 路径（或名称）是什么？
② 是否有 Agent/Chatbot 接入点可以实际调用？（提供调用方式）
③ 有没有业务上下文？（服务名、事件 ID 等具体测试数据）
```

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

**分组策略**：将题目按 5 题一组，每组 spawn 一个独立 sub-agent 执行。

每个 sub-agent 的任务：
1. 接收题目列表
2. 对每道题，以用户身份向目标 Agent 发出 Query
3. 记录完整的问答过程
4. 提取可观测数据（执行时间、响应长度等）
5. 返回结构化执行结果

**执行结果格式：**
```json
{
  "question_id": "Q1",
  "query": "原始 Query",
  "response": "Agent 完整回答",
  "execution_ms": 12000,
  "observations": {
    "tool_calls": ["tool_a", "tool_b"],
    "llm_rounds": 3,
    "had_error": false,
    "error_message": null
  }
}
```

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
→ skill-evaluator 确认：你可以用它直接在对话里调用吗？有具体的测试服务名吗？

用户：可以，服务名用 ark0，最近1小时
→ 进入精评模式，基于 ark0 生成针对性题目，执行，出报告

用户：帮我快速评估一下 alarm-event-detail，不需要配置
→ 进入零配置模式，读 SKILL.md 自动生成10题，展示后确认，执行，出报告
```

---

## Evaluation（自我评估标准）

- 典型输入：SKILL 路径 + 可选的业务上下文
- 预期输出：结构化评估报告，包含综合得分、bad patterns、优化建议
- 成功标准：报告覆盖三层评估体系，每道题有具体得分和判定，bad patterns 可操作
- 已知边界：
  - 无法访问 Langfuse trace 数据时，降级为纯 LLM-Judge 模式（无 Trajectory 客观数据）
  - 需要目标 Agent 可以在当前会话中调用（如果无法访问则无法执行）
