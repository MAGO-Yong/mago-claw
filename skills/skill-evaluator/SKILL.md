---
name: skill-evaluator
version: 2.0.0
description: >
  通用 Agent/SKILL 评估工具。输入目标 SKILL 的路径和 Agent 接入点，自动生成评估题目、
  通过真实 Agent 接入点执行（browser/session_send），基于三层评估体系打分，输出结构化报告。
  当用户说"帮我评估这个 SKILL"、"这个 SKILL 效果怎么样"、"跑一下评估"时触发。
metadata:
  category: evaluation
  subcategory: skill-quality
  trigger: skill_path/skill_name/evaluation_request
  input: [skill_path, agent_url, business_context]
  output: [eval_report, score, optimization_suggestions]
  impl: agent-native
---

# skill-evaluator：通用 Agent/SKILL 评估工具

---

## 核心原则（必读）

**评估对象是 Agent，不是 SKILL 的脚本。**

- ✅ 正确：用户发 query → Agent 收到 → Agent 选 SKILL → SKILL 执行 → Agent 呈现结果 → 我们评估
- ❌ 错误：直接调 SKILL 脚本 / 直接调底层 API → 这测的是脚本，Agent 根本不在链路里

两者发现的问题完全不同：
- 脚本层：API 封装是否正确、参数解析是否准确
- Agent 层：意图识别、SKILL 路由选择、多轮追问、错误引导

---

## 三层评估体系

| 层级 | 评估对象 | 典型问题 |
|------|---------|---------|
| **Tool Call 层** | 单次工具调用 | 工具选对了吗？参数有幻觉吗？ |
| **Trajectory 层** | 调用链路 | 顺序合理吗？有冗余步骤吗？ |
| **Outcome 层** | 最终结果 | 完整吗？准确吗？用户能直接用吗？ |

### 7 个评分维度

| 维度 | 层级 | 满分 |
|------|------|------|
| 意图识别 | Outcome | 1.0 |
| Skill 选择 | Tool Call | 1.0 |
| 推理过程 | Trajectory | 1.0 |
| 结果完整性 | Outcome | 1.0 |
| 结果准确性 | Outcome | 1.0 |
| 交付体验 | Outcome | 0.5 |
| 响应速度 | Trajectory | 0.5 |

**总分 6.0，归一化到 5.0 输出（× 5/6）。**
判定：PASS ≥ 4.0 / WARN ≥ 3.0 / FAIL < 3.0

---

## 工作流程

### Phase 0：启动确认（必须完成，缺一不可）

触发评估后，先确认以下内容：

**① 目标 SKILL**
- 读取 SKILL.md，提取：description、触发场景、输入参数、输出内容、边界条件

**② Agent 接入点（必须用户明确指定）**

| 类型 | 说明 | 执行方式 |
|------|------|---------|
| 外部 URL | 独立部署的 Agent（如 xray-agent） | browser 工具（target="host"） |
| 当前会话 | 就是正在对话的 Agent | 直接在本对话中发 query |
| 其他 session | 另一个 OpenClaw session | sessions_send |

如果用户没有指定接入点，**必须询问**：
> "请告诉我评估哪个 Agent 对这个 SKILL 的使用效果？
> 1. 外部 Agent URL（如 https://xray-agent.devops.xiaohongshu.com/）
> 2. 当前这个对话窗口
> 3. 某个特定 session 的 key"

**③ 业务上下文**（服务名、时间范围、事件 ID 等测试数据）

**④ 是否有已知 bad case**

---

### Phase 1：生成题目

基于 SKILL.md 内容，按以下分布生成题目（默认 10 题，有业务上下文可扩展到 15 题）：

| 类型 | 数量 | 特征 |
|------|------|------|
| 标准场景（S） | 5 题 | 完整入参，考察基础准确性 |
| 边界场景（B） | 3 题 | 缺少参数、超范围、跨 SKILL 路由 |
| 组合场景（C） | 2 题 | 需要多步推理或跨 SKILL 协作 |

**题目格式：**
```json
{
  "id": "S1",
  "type": "S",
  "query": "用户原始提问（自然语言，直接发给 Agent）",
  "expected_behavior": "Agent 应该做什么",
  "success_criteria": "什么样的回答算成功"
}
```

生成后展示给用户确认，用户确认后进入 Phase 2。

---

### Phase 2：执行评估

#### 关键规则

1. **每道题独立 spawn 一个 sub-agent**（不要把多题放进一个 sub-agent，会超时）
2. **所有题并行 spawn**，不要等一题完成再跑下一题
3. **sub-agent 只负责执行 + 截图**，不打分
4. **主 agent 收集所有结果后统一打分**（Phase 3）
5. **收到 sub-agent 结果后，主 agent 必须先验证执行方式**（见下方验证规则）

#### Sub-agent task prompt 模板（必须照此格式，不得自行发挥）

```
你是评估执行员，任务是扮演用户向目标 Agent 发送一道测试题，记录完整响应后返回结构化结果。

【强制约束 - 不得违反】
评估对象是 Agent（接入点：{ACCESS_POINT}），不是 SKILL 底层脚本。

❌ 严禁：
- 直接调用任何 SKILL 脚本（*.py、*.sh 等）
- 直接调用业务平台 HTTP API
- 自己构造参数执行查询

✅ 唯一允许的方式：
- 通过 browser 工具访问 {ACCESS_POINT}，在对话框输入 query，等待 Agent 响应

---

## 本题信息

- **Query**（原样发送，不要修改）：{QUERY}
- **预期行为**：{EXPECTED_BEHAVIOR}
- **成功标准**：{SUCCESS_CRITERIA}
- **接入点**：{ACCESS_POINT}
- **接入点类型**：{ACCESS_POINT_TYPE}（url / current_session / other_session）

---

## 执行步骤（外部 URL 类型）

1. `browser action=navigate url={ACCESS_POINT} target="host"`
2. 找到对话输入框（通常是 textarea 或 contenteditable div）
3. 输入 query 文本，按 Enter 发送，记录发送时间戳
4. **轮询等待响应**（禁止 sleep 硬等）：
   - 每隔 10 秒：`browser action=screenshot target="host"`
   - 判断完成信号：loading 指示器消失 + 出现新的 Agent 回复文本
   - 最多等 120 秒；超时记录 timed_out=true
5. 响应完成后：`browser action=snapshot target="host"` 获取完整文本

## 执行步骤（current_session 类型）

说明当前 task 是在 sub-agent 里执行，无法直接向主 session 发 query。
改为：将本题 query 和预期行为原样返回，标注 execution_method=skipped_self_eval。
（自评由主 agent 直接处理，不 spawn sub-agent）

## 执行步骤（other_session 类型）

`sessions_send(sessionKey={SESSION_KEY}, message={QUERY}, timeoutSeconds=120)`
记录返回的 response。

---

## 返回格式（JSON，只返回这个，不要其他说明）

{
  "question_id": "{QUESTION_ID}",
  "query": "{QUERY}",
  "access_point": "{ACCESS_POINT}",
  "execution_method": "browser | sessions_send | timed_out | error",
  "response_text": "Agent 完整回答原文（尽量完整，不要截断）",
  "execution_seconds": 45,
  "timed_out": false,
  "error_message": null
}
```

#### 执行方式验证（主 agent 收到结果后必做）

收到每个 sub-agent 的结果，逐一检查：

```
验证项：
✅ execution_method 为 "browser" 或 "sessions_send"（不是 "error" 或其他）
✅ response_text 是 Agent 的自然语言回复（不是脚本 JSON 输出、不是 API 响应体）
✅ access_point 字段与预期一致

如果验证失败：
→ 该题结果作废
→ 告知用户："Q{id} 执行方式有误（{原因}），正在重试"
→ 重新 spawn 该题的 sub-agent，task 开头加一行：
   "【重要】上一次执行违反了约束（{具体原因}），本次必须通过 browser 访问接入点执行"
```

---

### Phase 3：打分（主 agent 执行）

收集完所有题的执行结果后，主 agent 对每道题按 7 个维度打分：

**对每道题，结合以下信息判断：**
- SKILL.md 中该 SKILL 的能力描述和边界
- 本题的预期行为和成功标准
- sub-agent 返回的 response_text（Agent 真实回答）
- execution_seconds（用于响应速度评分）

**响应速度评分标准（外部 Agent，标准放宽）：**
- < 30s → 0.5
- 30-60s → 0.3
- 60-120s → 0.1
- 超时 → 0.0

**打分输出格式（每题）：**
```json
{
  "id": "S1",
  "query": "...",
  "response_summary": "Agent 回答摘要（50字以内）",
  "scores": {
    "intent_recognition": 0.0,
    "skill_selection": 0.0,
    "reasoning_process": 0.0,
    "result_completeness": 0.0,
    "result_accuracy": 0.0,
    "delivery_quality": 0.0,
    "response_speed": 0.0
  },
  "total": 0.0,
  "normalized_5": 0.0,
  "verdict": "PASS | WARN | FAIL",
  "bad_patterns": [],
  "optimization_suggestions": []
}
```

---

### Phase 4：生成报告

所有题打完分后，输出：

```markdown
# {SKILL_NAME} 评估报告

**时间**：{timestamp}  
**接入点**：{access_point}  
**题目数**：{n} 题  

---

## 综合评分

| 维度 | 均分 | 满分 |
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
**通过率**：X/N（PASS+WARN）

---

## 各题得分

| 题目 | 类型 | 得分 | 判定 | 核心问题 |
|------|------|------|------|---------|
| S1 | S | X.X | ✅ | 无 |
| B2 | B | X.X | ❌ | ... |

---

## Bad Patterns（系统性问题）

| 优先级 | 问题 | 出现频次 |
|--------|------|---------|
| P0 | ... | X 题 |
| P1 | ... | X 题 |

---

## 优化建议

### P0（立即修复）
- ...

### P1（近期优化）
- ...

### P2（长期改进）
- ...
```

---

## 触发示例

```
用户：帮我评估 xray-log-query
→ 必须先问接入点：
  "用哪个 Agent 来评估？
   1. https://xray-agent.devops.xiaohongshu.com/
   2. 当前对话窗口
   3. 其他 session key"

用户：用 https://xray-agent.devops.xiaohongshu.com/，服务名用 creator-service-default
→ 读 xray-log-query SKILL.md → 生成10题 → 展示给用户确认
→ 用户确认后 → 每题并行 spawn 一个 sub-agent（共10个）
→ 收集结果 → 验证执行方式 → 主 agent 统一打分 → 出报告
```

---

## 已知边界

- 外部 URL 接入点：无法直接观察 Agent 的工具调用序列，只能从回答内容推断，Trajectory 层置信度较低
- 当前会话自评：存在评分偏差风险，主 agent 打分时需额外严格
- 单题 sub-agent 超时上限约 10 分钟，所以必须每题独立 spawn（不能串行）
