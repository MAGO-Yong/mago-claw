# Agent 关键技术演进史

> 从 2022 到 2026，Agent 的核心能力是怎么一步步被发明出来的
> 每个技术：什么问题 → 旧方案 → 新方案 → 谁最早落地

---

## 一、Agent 技术演进时间线

```
2022.11  ChatGPT 发布        → 对话式 AI 爆发，但只能聊天
    ↓
2023.01  ReAct 论文          → 第一次证明 LLM 可以"推理+行动"交替
    ↓
2023.03  LangChain 发布      → 第一个 Agent 编排框架，Chain 概念
    ↓
2023.06  AutoGPT 爆火        → 自主 Agent 第一次被大众认知，但不可靠
    ↓
2023.10  OpenAI Function Calling → 结构化调用工具成为标准能力
    ↓
2024.01  MCP 协议提出        → Anthropic 发明 Agent 工具的"USB 接口"
    ↓
2024.03  CrewAI 发布         → 多 Agent 角色分工协作
    ↓
2024.06  LangGraph 发布      → 人在回路 + 可控 Agent 图
    ↓
2024.08  Claude Artifacts    → Agent 可以"做东西"而不仅仅是聊天
    ↓
2024.10  OpenAI Operator     → Agent 直接操作浏览器/桌面
    ↓
2025.01  Agent Skills 规范   → 技能打包标准化
    ↓
2025.03  Claude Code         → 编码 Agent 进入生产可用阶段
    ↓
2025.06  上下文工程兴起       → 从"给更多"到"管理好"的范式转变
    ↓
2025.09  OpenClaw 落地       → 多 Agent 平台 + 记忆系统 + 定时任务
    ↓
2026.01  LangChain Deep Agents → 开源生产级 Agent 框架成熟
    ↓
2026.04  异步子 Agent        → 非阻塞并行，Agent 可以同时干多件事
```

---

## 二、十大核心技术的发明史

### 1. Tool Calling（工具调用）

**问题**：LLM 只能生成文字，怎么让它"动手"？

**旧方案（2022-2023 初）**：
- 在 Prompt 里写"如果你想搜索，就输出 `SEARCH:关键词`"
- Agent 用正则匹配输出来判断该调用什么工具
- 脆弱：格式一变就解析失败，参数解析靠字符串处理

**突破（2023.10）**：
- **OpenAI 发布 Function Calling**——LLM 原生支持结构化输出工具调用
- 不再靠正则匹配文本，而是 LLM 直接返回 `{name: "search", args: {query: "..."}}`
- 框架解析 JSON，执行工具，结果喂回

**谁最早落地**：
- OpenAI gpt-3.5-turbo-0613（2023 年 6 月）第一个支持
- LangChain 在 2023 年中整合了这个能力
- Anthropic Claude 在 2024 年初跟进

**演进**：
```
正则匹配文本 → OpenAI Function Calling → Anthropic Tool Use → 统一抽象（各框架通用）
```

> 💡 **本质变化**：工具调用从"让 LLM 假装调用"变成了"LLM 原生能力"。

---

### 2. ReAct（推理+行动交替）

**问题**：Agent 怎么像人一样"想一步，做一步，看结果，再想下一步"？

**旧方案**：
- 一次性给所有信息，让 LLM 直接回答
- 或者预先写好固定流程（if-else），LLM 只是每个步骤的执行者

**突破（2022.11）**：
- **斯坦福论文《ReAct: Synergizing Reasoning and Acting in Language Models》**
- 证明 LLM 可以在"Thought（我想做什么）→ Action（我去做）→ Observation（我看到了什么）"之间循环
- 不是一次性给出答案，而是迭代推理

**谁最早落地**：
- 论文作者：Yao et al., Princeton + Google（2022 年 11 月）
- LangChain 在 2023 年 3 月实现了 ReAct Agent
- 后来几乎所有 Agent 框架都采用了这个模式

**演进**：
```
一次性回答 → ReAct 循环 → 带 TODO 列表的 ReAct → 带子 Agent 委派的 ReAct
```

> 💡 **本质变化**：Agent 从"问答机器"变成了"迭代推理者"。

---

### 3. Chain / Workflow（工作流编排）

**问题**：复杂任务不是单步能完成的，怎么编排多步骤流程？

**旧方案**：
- 硬编码：用 if-else 和 for 循环写死流程
- 灵活性为零，换个任务就要改代码

**突破（2023.03）**：
- **LangChain 发布**——提出"Chain（链）"概念
- 把 LLM 调用、工具调用、提示词模板组合成可复用的"链条"
- LLMChain（LLM + Prompt）、AgentChain（LLM + Tools + ReAct）

**谁最早落地**：
- LangChain（Harrison Chase, 2023 年 3 月）
- 后来演变为 LCEL（LangChain Expression Language）
- LlamaIndex 提出了自己的 Workflow 概念
- LangGraph 进一步提出了"图"的概念（不只是链，可以有分支、循环）

**演进**：
```
硬编码流程 → Chain 链 → LCEL 表达式 → LangGraph 图 → 异步子 Agent
```

> 💡 **本质变化**：从"写死流程"到"声明式编排"。

---

### 4. 长期记忆（Long-term Memory）

**问题**：Agent 每次对话都失忆，怎么记住长期信息？

**旧方案**：
- 把所有历史对话塞进上下文窗口
- 问题：上下文窗口有限，对话多了就撑爆，而且贵

**各家的解法**：

| 时间 | 方案 | 谁 | 思路 |
|------|------|----|------|
| 2023.04 | 向量数据库记忆 | LangChain | 对话存向量库，按需检索相似记忆 |
| 2023.06 | 摘要记忆 | AutoGPT | 定期总结对话历史，保留摘要 |
| 2023.08 | 反思记忆 | GenAgent | Agent 自己回顾经验，提取教训 |
| 2024.06 | 文件记忆 | Claude Projects | 上传文档作为持久上下文 |
| 2024.10 | 分层记忆 | OpenClaw | MEMORY.md（长期）+ 日记（短期）+ 规则（HOT） |
| 2025.01 | 情景记忆 | LangSmith | 搜索历史线程，复现排查路径 |
| 2025.09 | 后台记忆合并 | LangChain Deep Agents | 对话间自动总结，不占用用户时间 |

**关键发现（2025）**：
- 向量检索记忆不可靠——Agent 很难精确检索到自己需要的信息
- 文件记忆反而更靠谱——直接加载，不需要检索
- 记忆分层是关键——有些永远加载（偏好），有些按需加载（技能），有些事后加载（历史经验）

> 💡 **本质变化**：记忆从"塞进上下文"变成了"分层管理"。

---

### 5. MCP（Model Context Protocol）

**问题**：每个 Agent 框架都要自己对接每个工具，对接成本是 N×M。

**旧方案（2024 年前）**：
- LangChain 要写 langchain-github、langchain-slack、langchain-jira……
- OpenClaw 要写 hi-search skill、hi-calendar skill、metric-query skill……
- 每个框架自己对接每个工具，重复劳动

**突破（2024.01）**：
- **Anthropic 提出 MCP 协议**——标准化 Agent 连接工具的方式
- 工具提供方写一个 MCP Server，任何支持 MCP 的 Agent 都能用
- 类比：USB-C 接口，一次接入，到处可用

**谁最早落地**：
- Anthropic 最早提出（2024 年 1 月）
- Claude Desktop 第一个支持 MCP 的客户端
- 2024 年中开源，社区开始大量 MCP Server
- LangChain 在 2024 年底支持 MCP
- OpenClaw 通过 mcporter 技能支持 MCP

**MCP 架构**：
```
Agent（Host）←─── MCP 协议 ───→ MCP Server（工具提供方）
                                  ├── GitHub MCP Server
                                  ├── Slack MCP Server
                                  ├── 数据库 MCP Server
                                  └── 自定义业务 MCP Server
```

**为什么重要**：
- 工具提供方只需要写一次 MCP Server
- 任何 Agent 框架（LangChain、OpenClaw、Claude）都能用
- 打破了"框架锁定"——你换框架不需要重写工具对接

**当前局限**：
- MCP 主要解决工具接入，不解决工具发现（Agent 怎么知道有哪些工具可用）
- 性能：每次调用都要走网络
- 安全：MCP Server 的权限控制还没有统一标准

> 💡 **本质变化**：工具对接从"N 个框架各写各的"变成了"一次写，到处用"。

---

### 6. Skill（技能）

**问题**：工具是单步操作，但很多任务是"多步骤 + 专业知识"的复合流程。

**旧方案**：
- 把所有 SOP 写在系统提示词里
- 问题：系统提示词太长，浪费上下文，而且每次都要加载

**突破**：
- **技能 = 按需加载的专业知识包**
- Agent 启动时只看技能的"标题和简介"（很轻）
- 判断需要时才加载完整内容
- 这叫"渐进式披露"（Progressive Disclosure）

**谁最早落地**：

| 时间 | 方案 | 谁 | 特点 |
|------|------|----|------|
| 2023.06 | 自定义 Agent 指令 | AutoGPT | 最早的可插拔指令概念 |
| 2024.06 | Claude Projects 指令 | Anthropic | 项目级持久指令 |
| 2024.08 | Claude 自定义指令 | Anthropic | 用户级持久指令 |
| 2024.10 | AGENTS.md 规范 | 社区 | 开源标准，项目级指令文件 |
| 2025.01 | Agent Skills 规范 | agentskills.io | 第一个技能打包标准 |
| 2025.03 | OpenAI Codex Skills | OpenAI | Codex 的技能系统 |
| 2025.06 | OpenClaw SKILL.md | OpenClaw | 内部技能生态，66+ 个技能 |
| 2025.09 | LangChain Deep Agents Skills | LangChain | 集成到官方框架 |

**Skill 的标准结构**（AgentSkills.io 规范）：
```
skill-name/
├── SKILL.md          # 元数据 + 指令（必须）
├── scripts/          # 辅助脚本（可选）
├── docs/             # 参考文档（可选）
└── templates/        # 模板文件（可选）
```

**SKILL.md 的核心设计**：
```markdown
---
name: cpu-anomaly
description: CPU 指标异常时自动排查（触发条件）
---
# 排查步骤
1. 查 CPU 趋势...
2. 查进程列表...
3. ...
```

**为什么渐进式加载比全加载好**：
- 全加载：100 个 Skill × 平均 2KB = 200KB，上下文直接爆
- 渐进式：100 个描述 × 50 字 = 约 5KB，匹配时才加载完整内容

> 💡 **本质变化**：专业知识从"一次性全塞进 Prompt"变成了"按需加载的技能包"。

---

### 7. Subagent（子 Agent）

**问题**：单个 Agent 做复杂任务时，上下文窗口被中间过程撑爆。

**旧方案**：
- 一个 Agent 干到底，所有中间结果都留在上下文里
- 问题：步骤多了以后，早期信息被压缩/丢失，推理质量下降

**突破**：
- **子 Agent = 隔离的工作空间**
- 主 Agent 委派任务给子 Agent
- 子 Agent 做了 100 步操作，主 Agent 只收到最终结论
- 上下文开销从 100 步压缩到 1 个结论

**谁最早落地**：

| 时间 | 方案 | 谁 | 特点 |
|------|------|----|------|
| 2023.06 | AutoGPT 子任务 | AutoGPT | 最早的子任务概念 |
| 2024.03 | CrewAI 角色 | CrewAI | 多 Agent 角色分工 |
| 2024.06 | AutoGen 群组对话 | Microsoft | 多 Agent 协作对话 |
| 2025.01 | LangGraph 子图 | LangChain | 图级别的子 Agent |
| 2025.06 | OpenClaw sessions_spawn | OpenClaw | 多 Agent 路由 + 并发执行 |
| 2025.09 | LangChain Deep Agents task 工具 | LangChain | 统一的子 Agent 委派 |
| 2026.01 | 异步子 Agent | LangChain v0.5 | 非阻塞，主 Agent 可继续交互 |

**两种子 Agent 模式**：

```
同步模式（主流）：
主 Agent → 启动子 Agent → 等待 → 子 Agent 完成 → 收到结果 → 继续

异步模式（2026 新能力）：
主 Agent → 启动子 Agent → 继续和用户对话 → 子 Agent 后台跑 → 完成后汇报
```

**异步子 Agent 为什么是突破**：
- 同步模式：用户必须等，子 Agent 跑 5 分钟，用户就等 5 分钟
- 异步模式：子 Agent 后台跑，主 Agent 可以继续服务用户
- 类比：同步是"你帮我查个东西，我等你查完再说别的"；异步是"你帮我查着，我先跟你说另一件事"

> 💡 **本质变化**：从"一个 Agent 干到底"变成了"指挥官 + 执行团队"。

---

### 8. Human-in-the-loop（人在回路）

**问题**：Agent 执行危险操作（删数据、重启服务）时，谁来把关？

**旧方案**：
- 完全自动——Agent 自己决定，出事了再修复
- 或者完全手动——人做所有决策，Agent 只是执行器

**突破**：
- **人在关键节点介入审批**
- Agent 正常流程自己跑，遇到敏感操作暂停，等人工审批
- 三种选择：批准、修改参数后执行、拒绝

**谁最早落地**：

| 时间 | 方案 | 谁 | 特点 |
|------|------|----|------|
| 2023.06 | AutoGPT 确认模式 | AutoGPT | 每个命令前问 Y/N |
| 2024.06 | LangGraph interrupt | LangChain | 编程化中断 + 恢复 |
| 2024.08 | Claude 确认操作 | Claude | 危险操作前弹窗确认 |
| 2025.01 | OpenAI 操作审批 | ChatGPT | 发送/删除等操作需确认 |
| 2025.06 | OpenClaw exec 审批 | OpenClaw | 高危命令 /approve |
| 2025.09 | Deep Agents interrupt_on | LangChain | 声明式配置哪些工具需要审批 |

**LangChain Deep Agents 的声明式配置**：
```python
interrupt_on={
    "delete_file": True,           # 默认：批准/编辑/拒绝
    "send_email": {"approve": True, "edit": True},  # 只允许批准和编辑
    "read_file": False,            # 不需要审批
}
```

**为什么重要**：
- 没有人在回路，Agent 不敢上生产
- 有了人在回路，Agent 可以处理 90% 的常规操作，人只把关 10% 的关键决策
- 这是"AI 辅助"和"AI 替代"之间的平衡点

> 💡 **本质变化**：从"全自动或全手动"变成了"AI 跑流程，人把关关键节点"。

---

### 9. 上下文工程（Context Engineering）

**问题**：Agent 的信息太多（系统提示、对话历史、工具结果、记忆文件），上下文窗口不够用。

**旧方案**：
- 把一切信息都塞进上下文
- 问题：信息越多，推理质量越差，成本越高

**突破**：
- **不是"给更多"，而是"管理好"**
- 核心原则：Agent 看到什么信息，比 Agent 有什么能力更重要

**谁提出的**：
- 概念最早来自 DBreunig 的博客《How to Fix Your Context》（2025 年 6 月）
- 总结了"上下文隔离"（Context Quarantine）模式
- LangChain Deep Agents 把这个概念融入了框架设计

**四大技术手段**：

| 技术 | 原理 | 例子 |
|------|------|------|
| **渐进式披露** | 启动只加载精简信息，按需加载详细 | Skill 启动只读描述，匹配后才读全文 |
| **子 Agent 隔离** | 重型工作交给子 Agent，主 Agent 只收结论 | 100 步排查压缩为 1 个结论 |
| **对话压缩** | 自动总结早期对话，释放空间 | compact_conversation 工具 |
| **记忆分层** | 有些记忆永远加载，有些按需加载 | AGENTS.md 永远加载，history/ 按需检索 |

**关键认识转变**：
```
2023 年："上下文窗口越大越好" → 堆信息
2025 年："上下文管理比窗口大小更重要" → 精简信息
2026 年："渐进式披露是 Agent 架构的核心设计原则"
```

> 💡 **本质变化**：从"能力堆砌"到"信息管理"——Agent 架构的范式转变。

---

### 10. Agent 评估（Agent Evaluation）

**问题**：Agent 做得好不好？怎么量化？

**旧方案**：
- 人眼看——"感觉回答还行"
- 问题：无法量化改进，无法持续优化

**突破**：
- **用基准测试集 + 自动评分来评估 Agent**
- 不是评"模型好不好"，而是评"Agent 整体表现好不好"

**谁最早落地**：

| 时间 | 方案 | 谁 | 特点 |
|------|------|----|------|
| 2024.01 | AgentBench | 清华 | 第一个 Agent 综合基准 |
| 2024.03 | LangSmith 评估 | LangChain | 商业化的 Agent 追踪和评估平台 |
| 2024.06 | SWE-bench | Princeton | 编码 Agent 评估（GitHub Issue 解决率） |
| 2024.10 | Tau-bench | 清华 | Agent 任务完成率基准 |
| 2025.01 | Langfuse 追踪 | Langfuse | 开源的 Agent 追踪和评估 |
| 2025.06 | XRay Agent 51 题评估 | 小红书 | 真实业务场景的 Agent 评估 |
| 2026.01 | LangSmith Traces | LangChain | 每一步操作的精确追踪 |

**评估的三个层次**：

| 层次 | 评什么 | 方法 |
|------|--------|------|
| **模型层** | LLM 推理能力 | MMLU、GSM8K 等基准 |
| **Agent 层** | 工具调用 + 规划 | 给定任务，看完成率和效率 |
| **业务层** | 真实效果 | MTTR 降了多少？准确率多少？ |

**关键发现（2025-2026）**：
- Agent 评估 ≠ 模型评估——好模型不等于好 Agent
- **Skill 工程质量决定 Agent 上限**——工具描述不清、文件路径成本高，Agent 就做得差
- 评估需要精确到"每一步操作"——不是"回答对不对"，而是"哪一步做错了"

> 💡 **本质变化**：从"感觉好不好"到"精确到每一步操作的量化评估"。

---

## 三、技术演进的三条主线

### 主线一：从"能做"到"可控"

```
2023: Agent 能自主执行了（AutoGPT）→ 但不可控，经常跑飞
2024: 人在回路（LangGraph）→ 人能介入关键节点
2025: 权限控制 + 沙箱 → 限定 Agent 的能力边界
2026: 声明式安全策略 → 安全策略可配置、可审计
```

### 主线二：从"单干"到"协作"

```
2023: 单个 Agent（LangChain Chain）→ 只能做简单任务
2024: 多 Agent 角色（CrewAI/AutoGen）→ 分工协作
2025: 平台级多 Agent（OpenClaw）→ 按场景路由
2026: 异步子 Agent → 非阻塞并行，真正的团队协作
```

### 主线三：从"堆能力"到"管信息"

```
2023: 给 Agent 更多工具 → 工具越来越多
2024: 给 Agent 更多记忆 → 记忆越来越多
2025: 给 Agent 更多技能 → 技能越来越多
2026: 管理 Agent 看到什么 → 渐进式披露，精简上下文
```

---

## 四、对未来产品经理的启示

### 4.1 技术的" commoditization（商品化）"趋势

| 2024 年的稀缺能力 | 2026 年的状态 |
|------------------|--------------|
| Tool Calling | 所有主流模型标配 |
| MCP 协议 | 开源标准，到处可用 |
| 子 Agent | 各框架都有 |
| 人在回路 | 标准能力 |
| 记忆系统 | 标配 |
| Skill 系统 | 标配 |

**结论**：框架层面的能力差异在缩小。真正的壁垒在：
1. **工具和 SOP 的质量**——你的 Agent 有哪些好用的 Skill？
2. **评估体系**——你能否量化并持续改进 Agent 表现？
3. **安全治理**——你的 Agent 敢不敢上生产？

### 4.2 还没被解决的问题

| 问题 | 当前状态 | 为什么难 |
|------|---------|---------|
| Agent 可靠性 | 不稳定，同样的输入偶尔给不同结果 | LLM 本身是非确定性的 |
| 自动学习 | 不能从经验中自动改进 | 需要反馈循环 + 评估 + 更新机制 |
| 长任务成功率 | 步骤越多失败率越高 | 每步都有出错概率，累积放大 |
| 多 Agent 协调成本 | 通信开销大 | 每个 Agent 都是一次 LLM 调用 |
| 成本可控性 | 难以预估一次任务花多少钱 | 工具调用次数不确定 |

### 4.3 下一个突破点可能在

| 方向 | 可能性 | 谁在做 |
|------|--------|--------|
| **Agent 自我评估/自改进** | 高 | LangChain（后台记忆合并） |
| **模型动态路由** | 高 | OpenClaw（按任务复杂度选模型） |
| **Skill 生态标准化** | 中 | agentskills.io（社区标准） |
| **端到端可观测性** | 高 | LangSmith、Langfuse |
| **Agent 间协议（A2A）** | 中 | Google（A2A 协议） |
| **Agent 自主编程** | 中 | Claude Code、OpenAI Codex |

---

## 五、核心概念一句话总结

| 技术 | 解决了什么痛点 | 谁发明的 | 什么时候 |
|------|--------------|---------|---------|
| **Tool Calling** | LLM 不能"动手" | OpenAI | 2023.10 |
| **ReAct** | Agent 不会迭代推理 | 斯坦福论文 | 2022.11 |
| **Chain** | 复杂任务怎么编排 | LangChain | 2023.03 |
| **长期记忆** | Agent 每次都失忆 | 多家各自解 | 2023-2026 |
| **MCP** | 工具对接成本 N×M | Anthropic | 2024.01 |
| **Skill** | 专业知识怎么按需加载 | agentskills.io 社区 | 2025.01 |
| **Subagent** | 上下文被中间过程撑爆 | 多家各自解 | 2023-2026 |
| **人在回路** | Agent 做危险操作谁来把关 | LangGraph | 2024.06 |
| **上下文工程** | 信息太多上下文不够用 | DBreunig 博客 | 2025.06 |
| **Agent 评估** | Agent 做得好不好怎么量化 | LangSmith + 学术界 | 2024 |
