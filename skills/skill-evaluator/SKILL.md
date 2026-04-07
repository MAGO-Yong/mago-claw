---
name: skill-evaluator
version: 2.1.0
description: >
  通用 Agent/SKILL 评估工具。输入目标 SKILL 的路径和 Agent 接入点，自动生成评估题目、
  通过真实 Agent 接入点执行（browser/session_send），基于三层评估体系打分，输出结构化报告。
  新增 Agent Native 审计（Phase 0.5）：静态读取 SKILL 设计 + 动态触发错误边界题，评估 SKILL
  是否符合被 Agent 调用的工程标准（结构化错误、参数规范、路由设计、编排协议等）。
  当用户说"帮我评估这个 SKILL"、"这个 SKILL 效果怎么样"、"跑一下评估"时触发。
metadata:
  category: evaluation
  subcategory: skill-quality
  trigger: skill_path/skill_name/evaluation_request
  input: [skill_path, agent_url, business_context]
  output: [eval_report, agent_native_score, score, optimization_suggestions]
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

## 四层评估体系

| 层级 | 评估对象 | 典型问题 |
|------|---------|---------|
| **Agent Native 层** | SKILL 设计规范 | SKILL 本身是否符合被 Agent 调用的工程标准？ |
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

**① 目标 SKILL 路径（必须用户明确指定）**

如果用户没有提供 SKILL 路径，**必须先询问**，不能跳过：
> "请告诉我要评估哪个 SKILL？可以提供：
> 1. SKILL.md 的本地路径（如 `~/.openclaw/workspace/skills/xray-log-query/SKILL.md`）
> 2. SKILL 的名称（我会在 workspace/skills/ 下查找）"

用户提供后，读取 SKILL.md，提取：description、触发场景、输入参数、输出内容、边界条件。

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

### Phase 0.5：Agent Native 审计（静态 + 动态，必须完成）

> 在生成评测题目之前，先对 SKILL 本身做一次 Agent Native 合规审计。
> 评估的不是"Agent 用得好不好"，而是"SKILL 设计是否符合被 Agent 调用的工程标准"。
> 参考：https://docs.xiaohongshu.com/doc/bc1245f5e7da715fda366d8787a9c0ca

#### 步骤 1：静态分析（读 SKILL.md + 脚本文件）

读取 SKILL.md 及 scripts/ 目录下的实现脚本，按以下 9 个子项打分：

| 编号 | 子项 | 严重级别 | 满分 | 评估方法 |
|------|------|---------|------|---------|
| AN-1 | 结构化错误返回 | 🔴 P0 | 2 | 脚本错误处理是否返回 JSON（含 error_code、action、retry 字段），而非裸 stderr 文本 |
| AN-2 | 时间参数格式统一 | 🔴 P0 | 2 | 时间参数是否统一规范（优先 ISO 8601 字符串），脚本内部自行转换 |
| AN-3 | SKILL_DIR 注入方式 | 🔴 P0 | 2 | {SKILL_DIR} 是否由框架注入，而非暴露给 Agent 手动替换 |
| AN-4 | 路由决策是否自持 | 🟠 P1 | 1.5 | description 里是否避免大量"什么时候用别人"的说明（路由职责不应压给 Agent） |
| AN-5 | 输出格式是否标准化 | 🟠 P1 | 1.5 | 是否有统一输出 schema，避免"有时 JSON 有时自然语言"的混用 |
| AN-6 | 功能边界是否清晰 | 🟠 P1 | 1 | 与相近 SKILL 的差异是否在 description 中明确声明 |
| AN-7 | 输出置信度/元信息 | 🟡 P2 | 0.5 | 输出是否附带 confidence、evidence_count、data_source 等元信息 |
| AN-8 | SKILL 间编排协议 | 🟡 P2 | 0.5 | metadata 是否声明 input_from / output_to |
| AN-9 | 无交互式人机依赖 | 🟡 P2 | 1 | 是否不依赖弹窗、OAuth 等人工介入步骤（Agent 自动化链路中无法处理） |

**静态审计总分：满分 12 分，归一化到 10 分输出（× 10/12）。**

判定：
- Agent Native Ready（ANR）：≥ 8.0
- Agent Native Partial（ANP）：5.0 ~ 7.9
- Agent Native Unready（ANU）：< 5.0

**输出格式：**
```json
{
  "phase": "0.5-static",
  "items": [
    {
      "id": "AN-1",
      "name": "结构化错误返回",
      "level": "P0",
      "score": 0.0,
      "max_score": 2.0,
      "finding": "当前错误处理直接输出 Python traceback，Agent 收到后无法机器处理",
      "suggestion": "在 except 块中返回 JSON: {\"error_code\": \"...\", \"action\": \"...\", \"retry\": false}"
    }
  ],
  "raw_total": 0.0,
  "normalized_10": 0.0,
  "verdict": "ANR | ANP | ANU"
}
```

#### 步骤 2：动态验证（跑 1 道错误触发题）

静态分析完成后，设计 **1 道专门触发 SKILL 错误路径的边界题**，通过 Agent 接入点执行：

**题目设计原则**：
- 传入必然导致 SKILL 报错的参数（如：不存在的服务名、格式错误的 ID、超出时间范围的查询）
- 目标：看 Agent 收到 SKILL 错误响应后，能否基于结构化错误信息自主给出有意义的引导

**题目格式**：
```json
{
  "id": "AN-E1",
  "type": "error-trigger",
  "query": "（自然语言，设计为必然触发 SKILL 错误的请求）",
  "expected_behavior": "Agent 应能识别错误类型并给出有意义的引导（而非直接抛出错误原文）",
  "success_criteria": "Agent 回复包含：错误类型说明 + 下一步建议（如：重新认证/换参数/换 SKILL）"
}
```

**执行方式**：通过 browser 工具访问 Agent 接入点，发送 AN-E1 的 query，记录完整响应。

**动态验证打分**（独立，不进入主评分体系）：

| 表现 | 得分 |
|------|------|
| Agent 能识别错误类型 + 给出可操作建议 | 2 / 2 |
| Agent 识别到出错但只给模糊说明 | 1 / 2 |
| Agent 将 SKILL 错误文本原样甩给用户 | 0 / 2 |

动态验证结果作为 AN-1（结构化错误返回）的实证，**若动态得分 < 静态 AN-1 得分，以动态结果为准（向下修正）**。

#### 步骤 3：输出审计摘要，决定是否继续

将静态 + 动态审计结果整合，告知用户：

```
🔍 Agent Native 审计完成

📋 静态分析：{normalized_10}/10.0（{ANR/ANP/ANU}）
⚡ 动态验证（错误路径 AN-E1）：{dynamic_score}/2

🔴 P0 问题（{n} 项）：
  - AN-1: {finding}
  - AN-2: {finding}

🟠 P1 问题（{n} 项）：
  - AN-4: {finding}

🟡 P2 改进机会（{n} 项）：
  - AN-7: {finding}

判定：{verdict}
{若 ANU：建议先修复 P0 问题再继续完整评测，是否继续？}
{若 ANP/ANR：继续生成评测题目。}
```

**特殊处理**：
- 若 verdict = **ANU**（< 5.0）：提示用户 SKILL 存在严重的 Agent Native 缺陷，建议先修复 P0 问题，询问是否仍要继续完整评测
- 若 verdict = **ANP / ANR**：直接进入 Phase 1 生成题目，不需要用户确认

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

### Phase 1.5：试跑验证（必须，不可跳过）

**在用户确认题目后，禁止直接全量 spawn。必须先试跑。**

#### 执行步骤

1. 从题目中随机选 **2-3 题**（覆盖 S/B/C 至少两种类型）
2. spawn 一个 sub-agent 只跑这 2-3 题（runTimeoutSeconds = 题数 × 180）
3. 收到结果后：
   - 验证执行方式合规（execution_method=browser，response_text 为自然语言回复）
   - 对这 2-3 题打分，展示给用户

4. 向用户确认：

> "试跑了 {n} 题，结果如下：
> {题号} — {得分}/5 — {一句话摘要}
> ...
> 评估效果是否符合预期？确认后继续跑剩余 {X} 题。"

**只有用户明确回复"确认"/"继续"/"OK"后，才进入 Phase 2 全量执行。**

如果用户对题目或打分标准有异议，先修改再重新试跑，不要直接全量跑。

#### 为什么不能跳过

- 验证接入点是否可正常访问（避免全量跑完才发现无法访问）
- 验证打分维度与用户预期是否一致（避免 20-30 分钟白跑）
- 提前发现 SKILL 明显异常（如全部超时、全部乱码）

---

### Phase 2：执行评估

> ⚠️ **进入此阶段的前提：Phase 1.5 试跑已完成，用户已明确确认。**
> 未完成试跑确认直接进入此阶段是错误的执行，必须退回 Phase 1.5。

#### 关键规则

1. **spawn 一个 sub-agent 串行执行所有题目**（不要并行，browser 共用同一页面，并行会互相干扰）
2. **每题完成后刷新页面开新对话**，避免上下文污染
3. **sub-agent 只负责执行 + 记录响应**，不打分
4. **主 agent 收集所有结果后统一打分**（Phase 3）
5. **sub-agent runTimeoutSeconds 必须设置为 题目数 × 180**（每题最多 3 分钟）
6. **收到 sub-agent 结果后，主 agent 必须先验证执行方式**（见下方验证规则）

#### 阶段性进度反馈（主 agent 职责）

评估耗时较长（10题约25-30分钟），**主 agent 必须在以下时机主动向用户推送进度**，不能等全部完成才回复：

- **sub-agent 启动后立即告知**：
  > "✅ 已启动评估，共 {n} 题，预计 {n×3} 分钟。我会在结果回来后第一时间告知你。"

- **sub-agent 返回结果后立即告知**（验证执行方式通过后）：
  > "📊 已完成 {n} 题评估，正在打分中，稍后输出完整报告。"

- **如果 sub-agent 超时或执行方式有误**，立即告知用户并说明处理方式：
  > "⚠️ 执行异常：{原因}，正在重试。"

#### Sub-agent task prompt 模板（直接复用，填入变量，不得自行改动结构）

```
你是评估执行员。你的唯一任务是：扮演用户，按顺序向目标 Agent 发送每道测试题，记录完整响应，最终返回结构化 JSON。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【强制约束 - 违反即作废】

评估对象是 Agent（接入点：{ACCESS_POINT}），不是 SKILL 底层脚本。

❌ 严禁（无论理由）：
- 直接调用任何 SKILL 脚本（.py / .sh 等）
- 直接调用业务平台 HTTP API
- 自己构造参数执行查询
- 用 exec 运行任何脚本

✅ 唯一允许的执行方式：
- browser 工具（target="host"）访问 {ACCESS_POINT}，在对话框输入 query，等待 Agent 响应
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 接入点信息

- URL：{ACCESS_POINT}
- 类型：外部 URL（browser）

## 题目列表

{QUESTIONS_JSON}

## 每道题的执行步骤

### 步骤 1：导航到接入点（第一题前执行一次）
browser action=navigate url={ACCESS_POINT} target="host"
截图确认页面已加载，找到 Agent 对话入口（如有选择，选择与被评估 SKILL 匹配的 Agent）

### 步骤 2：发送 query
- 找到输入框（textarea 或 contenteditable div）
- 输入题目的 query 文本（原样输入，不要修改）
- 按 Enter 发送
- 记录发送时间

### 步骤 3：轮询等待响应（禁止 sleep 硬等）
- 每隔 10 秒执行一次 browser action=screenshot target="host"
- 判断完成信号：页面上 loading 动画/转圈/黑点消失，且出现新的 Agent 回复文本块
- 最多等待 150 秒
- 超时则记录 timed_out=true，继续下一题

### 步骤 4：获取完整响应
browser action=snapshot target="host"
从 snapshot 中提取 Agent 的完整回复文本

### 步骤 5：刷新页面，准备下一题
browser action=navigate url={ACCESS_POINT} target="host"
等页面加载完成后执行下一题

---

## 返回格式（只返回此 JSON，不要任何其他说明）

{
  "access_point": "{ACCESS_POINT}",
  "execution_method": "browser",
  "results": [
    {
      "id": "S1",
      "query": "原始 query 文本",
      "response_text": "Agent 完整回答原文（不要截断，尽量完整）",
      "execution_seconds": 45,
      "timed_out": false,
      "error_message": null
    }
  ]
}
```

#### 执行方式验证（主 agent 收到结果后必做）

收到 sub-agent 结果后，检查：

```
✅ execution_method == "browser"
✅ results 中每条 response_text 是 Agent 的自然语言回复
   （不是脚本 JSON 输出、不是 API 响应体、不是 "无法执行" 类说明）

如果验证失败：
→ 结果作废，告知用户执行方式有误
→ 重新 spawn，task 开头追加：
  "【警告】上次执行违反了约束：{原因}。本次必须且只能通过 browser 访问接入点。"
```

---

### Phase 2.5：查询 AI 链路 Trace（每题执行后）

> ⏳ **当前状态：等待 AI 链路 trace 查询 SKILL 孵化完成后接入，当前步骤跳过，记录占位。**

**背景**：Agent 处理每道题时，内部会产生 LLM 调用链路（tool call 序列、推理轮次、token 消耗等）。这些数据存在 AI 链路 trace 系统中，是 Trajectory 层评估的客观依据。

**目标**：在 sub-agent 返回响应后，立即查询该次对话对应的 AI trace，获取：

| 数据项 | 用途 |
|--------|------|
| tool call 序列 | 验证 Agent 实际调用了哪些工具（而非从回答内推断） |
| LLM 推理轮次 | 评估推理过程是否有冗余 |
| 总 token 消耗 | 辅助评估响应效率 |
| 端到端耗时分布 | 精确响应速度，区分 Agent 思考耗时 vs 工具执行耗时 |

**接入后的执行流程**（SKILL ready 后替换占位）：

```
# 当前：占位，跳过
trace_data = "等待补充 trace"

# 接入后：
# 1. 从 sub-agent 返回结果中提取 session_id 或 conversation_id
# 2. 调用 AI trace 查询 SKILL，传入 session_id + 时间范围
# 3. 提取 tool_calls、llm_rounds、token_count、latency_breakdown
# 4. 将 trace_data 传入 Phase 3 打分，补充 Trajectory 层客观数据
```

**对评分的影响**：
- trace 可用时：Skill 选择、推理过程两个维度基于客观 trace 数据打分，置信度高
- trace 不可用时（当前）：从 response_text 内容推断，在评分结果中标注 `trajectory_confidence: low`

---

### Phase 3：打分（主 agent 执行）

收集完所有题的执行结果后，主 agent 对每道题按 7 个维度打分：

**对每道题，结合以下信息判断：**
- SKILL.md 中该 SKILL 的能力描述和边界
- 本题的预期行为和成功标准
- sub-agent 返回的 response_text（Agent 真实回答）
- execution_seconds（用于响应速度评分）
- trace_data（当前为"等待补充 trace"，接入后为真实 trace 数据）

**当 trace_data 为"等待补充 trace"时**，在每题打分结果中追加：
```json
"trajectory_confidence": "low",
"trajectory_note": "Skill选择/推理过程维度基于回答内容推断，非客观 trace 数据，待 AI trace SKILL 接入后重评"
```

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
  "trajectory_confidence": "low | high",
  "trajectory_note": "low 时说明原因；high 时留空",
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

所有题打完分后，输出以下结构的报告（参考格式：docs.xiaohongshu.com/doc/ee9837e9b101d1939ef9f23f40f75b55）：

```markdown
# {SKILL_NAME} 评估报告

## 1. 文档目标

本文档评估 {SKILL_NAME} 在 {AGENT_NAME} 中的表现，评估维度覆盖：

| 维度 | 层级 | 说明 |
|------|------|------|
| Agent Native 合规 | SKILL 设计 | SKILL 是否符合被 Agent 调用的工程标准 |
| 响应速度 | Trajectory | 整体完成耗时，是否超时 |
| 意图识别 | Outcome | 是否正确理解用户问题与对象类型 |
| Skill 选择 | Tool Call | 是否命中正确 Skill，是否误调或漏调 |
| 推理过程 | Trajectory | 调用顺序是否合理，是否能逐步收敛 |
| 结果完整性 | Outcome | 是否覆盖关键字段、证据和结论 |
| 结果准确性 | Outcome | 对象、数据、归因、结论是否正确 |
| 交付体验 | Outcome | 输出是否清晰，异常处理是否自然 |

## 2. 评估对象范围

- **被评估 SKILL**：{skill_path}
- **Agent 接入点**：{access_point}
- **测试服务/对象**：{test_objects}
- **评估时间**：{timestamp}
- **Trajectory 置信度**：⏳ 低（AI trace SKILL 待接入，Skill选择/推理过程基于回答内容推断）

## 3. 评估用例设计原则

| 原则 | 说明 |
|------|------|
| 真实对象 | 测试数据来自真实服务，数据均可查 |
| 用户视角 | 题面贴近真实用户表述，不暴露 SKILL 内部参数 |
| 分层设计 | 分为标准场景（S）、边界场景（B）、组合场景（C）三类，另含 Agent Native 错误触发题（AN-E） |
| 可执行 | 题面避免依赖无法稳定获取的数据 |

## 4. Agent Native 审计结果

> 评估 SKILL 设计是否符合被 Agent 调用的工程标准。参考：https://docs.xiaohongshu.com/doc/bc1245f5e7da715fda366d8787a9c0ca

### 4.1 综合判定

| 指标 | 得分 |
|------|------|
| 静态审计总分 | {raw_total} / 12.0 |
| 归一化得分 | **{normalized_10} / 10.0** |
| 动态验证（AN-E1） | {dynamic_score} / 2.0 |
| **最终判定** | **{ANR ✅ / ANP ⚠️ / ANU ❌}** |

### 4.2 各子项明细

| 编号 | 子项 | 级别 | 得分 | 满分 | 问题描述 |
|------|------|------|------|------|---------|
| AN-1 | 结构化错误返回 | 🔴 P0 | {score} | 2.0 | {finding 或 "通过"} |
| AN-2 | 时间参数格式统一 | 🔴 P0 | {score} | 2.0 | {finding 或 "通过"} |
| AN-3 | SKILL_DIR 注入方式 | 🔴 P0 | {score} | 2.0 | {finding 或 "通过"} |
| AN-4 | 路由决策是否自持 | 🟠 P1 | {score} | 1.5 | {finding 或 "通过"} |
| AN-5 | 输出格式是否标准化 | 🟠 P1 | {score} | 1.5 | {finding 或 "通过"} |
| AN-6 | 功能边界是否清晰 | 🟠 P1 | {score} | 1.0 | {finding 或 "通过"} |
| AN-7 | 输出置信度/元信息 | 🟡 P2 | {score} | 0.5 | {finding 或 "通过"} |
| AN-8 | SKILL 间编排协议 | 🟡 P2 | {score} | 0.5 | {finding 或 "通过"} |
| AN-9 | 无交互式人机依赖 | 🟡 P2 | {score} | 1.0 | {finding 或 "通过"} |

### 4.3 动态验证：AN-E1（错误路径触发）

- **Query**：`{AN-E1 query}`
- **Agent 回复摘要**：{50字摘要}
- **验证结论**：{Agent 能否基于结构化错误信息给出可操作建议？}
- **得分**：{dynamic_score} / 2.0

### 4.4 Agent Native 改造建议

| 优先级 | 子项 | 问题 | 具体改造建议 |
|--------|------|------|------------|
| P0 | AN-1 | {问题描述} | {具体改法} |
| P0 | AN-2 | {问题描述} | {具体改法} |
| P1 | AN-4 | {问题描述} | {具体改法} |
| P2 | AN-7 | {问题描述} | {具体改法} |

---

## 5. 实测评估结果（Agent 运行表现）

### 5.1 综合评分汇总

| 类型 | 有效用例数 | 均分 | 最高 | 最低 | 主要短板 |
|------|-----------|------|------|------|---------|
| S（标准场景） | X | **X.X/5** | {题号} | {题号} | {主要问题} |
| B（边界场景） | X | **X.X/5** | {题号} | {题号} | {主要问题} |
| C（组合场景） | X | **X.X/5** | {题号} | {题号} | {主要问题} |
| **全量均分** | **X** | **X.X/5** | — | — | **{一句话总结}** |

### 5.2 实测数据汇总

| 用例 | 类型 | 题面（关键词） | 耗时 | AI Trace | 综合评分 | 备注 |
|------|------|--------------|------|----------|----------|------|
| S1 | 标准 | {题面关键词} | {n}s | ⏳ 待补充 | **{x}/5** | {一句话说明亮点或问题} |
| S2 | 标准 | ... | ... | ⏳ 待补充 | **{x}/5** | ... |
| B1 | 边界 | ... | ... | ⏳ 待补充 | **{x}/5** | ... |
| C1 | 组合 | ... | ... | ⏳ 待补充 | **{x}/5** | ... |

> AI Trace 列：AI trace SKILL 接入后自动替换为 Langfuse trace 链接，用于查看 tool_calls、LLM 轮次、token 等客观数据。

### 5.3 分布统计

| 评分区间 | 用例数 | 用例 |
|---------|-------|------|
| 5/5（优秀） | X | {题号列表} |
| 4-4.5/5（良好） | X | {题号列表} |
| 3-3.5/5（及格） | X | {题号列表} |
| < 3/5（偏低） | X | {题号列表} |

### 5.4 关键发现

> 用高亮块突出最重要的发现（P0 级用红色，P1 级用橙色，正向发现用蓝色）

**[P0 问题]** {现象描述}：{数据支撑}。**SKILL 根因**：{定位到 SKILL 具体模块}。

**[P1 问题]** {现象描述}：{数据支撑}。**SKILL 根因**：{定位到 SKILL 具体模块}。

**[正向发现]** {描述表现好的地方}：{数据支撑}。

### 5.5 各题详情

每道题展开说明，突出亮点与问题，归因到 SKILL 设计层面。

---

#### ✅/⚠️/❌ {题号}（{类型}场景）— {得分}/5.0

**Query**：`{原始 query}`  
**耗时**：{n}s | **AI Trace**：⏳ 待补充

**回答摘要**：{50-100字摘要，抓住回答核心}

**✅ 亮点**：
- {具体描述，例如：正确识别用户意图为链路分析而非日志查询，调用了 logview 能力}

**❌ 问题**：
- {现象描述，例如：将 pod 名 creator-service-default-5nmsq 识别为服务名传入 subApplication}
- **SKILL 归因**：{定位到 SKILL 哪个环节，例如：xray-log-query 的 nl_to_query 参数提取逻辑未区分 pod 名（格式：{service}-{5位随机串}）与服务名，需在参数校验模块增加 pod 名格式识别}

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | x.x | 1.0 |
| Skill 选择 | x.x | 1.0 |
| 推理过程 | x.x | 1.0 |
| 结果完整性 | x.x | 1.0 |
| 结果准确性 | x.x | 1.0 |
| 交付体验 | x.x | 0.5 |
| 响应速度 | x.x | 0.5 |
| **合计** | **x.x** | **6.0** |

---

（每题一节，按 S1→...→B1→...→C1→... 顺序排列）

## 6. 综合优化建议（针对 SKILL）

> 整合 Agent Native 审计 + 运行表现两个维度的问题，统一优先级排列。

| 优先级 | 来源 | 问题现象 | SKILL 根因 | 修改建议 |
|--------|------|---------|-----------|---------|
| P0 | Agent Native | {现象} | {AN 子项} | {具体怎么改} |
| P0 | 运行表现 | {现象} | {SKILL 的哪个模块/逻辑} | {具体怎么改} |
| P1 | Agent Native | {现象} | {AN 子项} | {具体怎么改} |
| P1 | 运行表现 | {现象} | {SKILL 的哪个模块/逻辑} | {具体怎么改} |
| P2 | Agent Native | {现象} | {AN 子项} | {具体怎么改} |

## 7. 评估用例（附录）

> 仅在题目数量少或与结果无重复时展示，题目较多时可省略。

| 编号 | 类型 | 题面 | 关键考察点 |
|------|------|------|-----------|
| AN-E1 | 错误触发 | {query} | 结构化错误返回 + Agent 错误处理能力 |
| S1 | 标准 | {query} | {考察点} |
| B1 | 边界 | {query} | {考察点} |
| C1 | 组合 | {query} | {考察点} |
```

---

### Phase 5：交付报告

报告生成后，根据用户环境决定交付方式：

#### 判断逻辑

```
if 用户在 OpenClaw/Claw 环境：
    → 优先创建 REDoc 文档（hi-docs SKILL）
    → 同时生成本地 markdown 备份
else（用户不在 Claw 环境 / hi-docs 不可用）：
    → 只生成本地 markdown 文件，提供路径
```

#### 创建 REDoc 文档

使用 hi-docs SKILL（`pnpm dlx @xhs/hi-workspace-cli@0.2.5`）创建：

```bash
cat {report_file}.md | pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:create \
  --title "{SKILL_NAME} SKILL 评估报告（{YYYY-MM-DD}）" \
  --content - \
  --operate-code "{skill_name}-eval-{YYYYMMDD}"
```

- `operate-code` 格式：`{skill_name}-eval-{YYYYMMDD}`，确保幂等（重试不重复创建）
- 创建成功后输出 shortcutId 和 URL，提供给用户

#### 生成本地 markdown 备份

无论是否创建了 REDoc，都保存一份本地 markdown 文件：

```
路径：workspace/memory/{skill_name}-eval-report-{YYYY-MM-DD}.md
内容：完整评估报告（与 REDoc 内容一致）
```

保存后执行：

```bash
cd {workspace} && git add memory/{skill_name}-eval-report-{YYYY-MM-DD}.md && git commit -m "docs: {SKILL_NAME} 评估报告 {YYYY-MM-DD}

RedDoc: {url}（若无则省略此行）
Agent Native: {an_score}/10.0 {ANR/ANP/ANU}
综合得分: {score}/5.0 {PASS/WARN/FAIL}，通过率{n}/{total}"
```

#### 最终交付消息模板

```
评估报告已生成：

🔍 Agent Native 审计：{an_score}/10.0 {ANR ✅ / ANP ⚠️ / ANU ❌}
📊 运行综合得分：{score}/5.0 {PASS ✅ / WARN ⚠️ / FAIL ❌}
📝 REDoc 文档：{url}（若无则省略）
💾 本地备份：memory/{skill_name}-eval-report-{YYYY-MM-DD}.md

Agent Native 核心问题：
- [P0] AN-1: {问题1}
- [P1] AN-4: {问题2}

运行核心问题：
- [P0] {问题1}
- [P1] {问题2}
```

#### 评估局限性提醒（必须在交付消息后追加）

在交付消息结束后，**必须**追加以下提醒（不可省略）：

```
---
💡 **关于本次评估的局限性**

本次评估属于**初步通用框架评估**，覆盖 Agent Native 合规性和基础运行表现。如需进一步提升 SKILL 质量，建议考虑：

1. **精细化业务效果评估**：针对你的具体业务场景，设计覆盖率更高的评估数据集（golden dataset），并引入 LLM as Judge 对每道题的回答质量做自动化评分；

2. **持续在线评估**：基于 SKILL 上线后的真实链路数据，持续监控效果并迭代优化，而非仅依赖离线题目；

3. **评估体系建设**：参考小红书内部 AI 效果评估方法论，了解如何系统化地构建数据集、评估器和监控闭环：
   👉 https://docs.xiaohongshu.com/doc/10bd82c9c1bedd01879a3d78dfed4b26
```

---

## 触发示例

```
用户：帮我评估 xray-log-query
→ Phase 0 两问缺一不可：

  问①（SKILL 路径）：
  "要评估哪个 SKILL？
   1. 提供 SKILL.md 路径
   2. 提供 SKILL 名称（我在 workspace/skills/ 下查找）"

  用户：skills/xray-log-query/SKILL.md
  → 读取 SKILL.md，提取能力边界

  问②（Agent 接入点）：
  "用哪个 Agent 来评估？
   1. https://xray-agent.devops.xiaohongshu.com/
   2. 当前对话窗口
   3. 其他 session key"

  用户：用 https://xray-agent.devops.xiaohongshu.com/，服务名用 creator-service-default

→ 生成 10 题 → 展示给用户确认
→ 用户确认后：
  sessions_spawn(
    task = <sub-agent task prompt 模板，填入 ACCESS_POINT 和 QUESTIONS_JSON>,
    mode = "run",
    runTimeoutSeconds = 10 * 180  # 题目数 × 180 秒
  )
→ 等 sub-agent 完成 → 验证执行方式 → 主 agent 统一打分 → 出报告 → 交付（REDoc + markdown）
```

## 已知边界

- 外部 URL 接入点：无法直接观察 Agent 的工具调用序列，只能从回答内容推断，Trajectory 层置信度较低
- 当前会话自评：存在评分偏差风险，主 agent 打分时需额外严格
- browser 共用同一页面，必须串行执行（每题后刷新），不能并行
- 单题响应最长约 150 秒，10 题总计约 25-30 分钟，runTimeoutSeconds 需相应设置


