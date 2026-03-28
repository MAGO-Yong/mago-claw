# Harness Engineering 研究报告

**研究主题：** Harness Engineering 方法论如何牵引 AI 时代稳定性建设落地，以及对技术风险平台有哪些具体功能支撑要求

**来源说明：** 整合 14 篇一手来源（OpenAI / Anthropic / LangChain / Martin Fowler / Latent Space 官方工程博客）+ 控制论原著 + 学术论文，优先引用原始出处

---

## 一、核心结论（先看这里）

1. **Harness Engineering 是真实的方法论，不是概念炒作。** 有 5 组独立的可量化数据支撑：最高案例提升幅度达 36 个百分点；Terminal Bench 2.0 上同一模型换 Harness 排名差 28 位；Pi Research 一个下午提升 15 个 LLM 的编程能力；Anthropic 最新实验 Solo 模式核心功能坏，Harness 模式出来能玩的游戏——且所有案例模型本身未作任何修改。

2. **传统稳定性方法有结构性盲区。** AI 系统的核心失效模式（质量静默下滑、模型漂移、上下文腐化）传统监控完全无法感知，需要新的「传感器」和「执行器」。

3. **Harness Engineering 的本质是控制论。** 维纳 1948 年的框架精准描述了今天的工程挑战——负反馈、熵增对抗、稳态维持、黑箱方法，全部适用于 AI 系统可靠性设计。

4. **这套方法论对技术风险平台有明确的能力建设要求。** Trace 采集和 Eval 评估已有成熟工具可集成；变更准入、语义级权限、Agent 审计归档是行业空白，是平台可以率先定义标准的位置。

5. **「用约束换自主」是 Harness Engineering 最反直觉也最核心的洞察。** 给 AI 设的规矩越明确，它能独立做的事情就越多。增加信任需要的不是更多自由，而是更多限制。（Birgitta Böckeler，Martin Fowler 网站，2026-02-17）

---

## 二、概念起源与定义

### 2.1 词义：为什么叫「马具」

Harness（马具）——套在马身上让人能控制方向和力量的装备。AI Agent 是那匹动力十足但不守规矩的马，Harness 是让它跑得快又不跑偏的缰绳和马鞍。

Latent Space（2026-03-04）给出了迄今最精准的跨工程领域定义：

> **「In every engineering discipline, a harness is the same thing: the layer that connects, protects, and orchestrates components — without doing the work itself.」**

### 2.2 概念起源时间线

```
2025-11-26  Anthropic Engineering Blog（Justin Young）
            发表长期运行 Agent 的 Harness 设计方法论——两段式架构的首次完整描述

2026-02-05  Mitchell Hashimoto 博客（HashiCorp 联合创始人）
            首次系统性提出「Harness Engineering」这个词
            原始定义：「每当你发现 Agent 犯了一个错误，你就花时间设计一个解决方案，
            使 Agent 从此永远不再犯同样的错误。」

2026-02-11  OpenAI 官方博客「Harness engineering: leveraging Codex in an agent-first world」
            引爆社区讨论，概念从个人博客升级为行业术语

2026-02-17  LangChain Blog「Improving Deep Agents with harness engineering」
            发布可量化的实验数据（52.8% → 66.5%），提供工程实践细节

2026-02-17  Martin Fowler 网站（Birgitta Böckeler，Thoughtworks Distinguished Engineer）
            从软件工程视角深度分析 Harness 的未来影响，提出「Harness 模板」概念

2026-03-04  Latent Space「Is Harness Engineering Real?」
            发起 Big Model vs Big Harness 行业大辩论，整合双方核心论点

2026-03-05  arXiv 2603.05344「Building AI Coding Agents for the Terminal」
            学术论文证实：仅改变 Harness，同一模型从 42% 跳到 78%

2026-03-24  Anthropic Engineering Blog（Prithvi Rajasekaran）
            三 Agent 架构（Planner + Generator + Evaluator）完整描述，
            Context Anxiety 与 Context Reset 的工程解法
```

### 2.3 三个演进阶段，一个方向

| 阶段 | 时间 | 关注什么 | 为什么不够 |
|------|------|---------|-----------|
| Prompt Engineering | 2023-2024 | 怎么写一条好指令 | 单次输入-输出，复杂任务失控 |
| Context Engineering | 2025 | 给 Agent 提供什么信息 | 好的上下文无法阻止 Agent 做不该做的事 |
| **Harness Engineering** | **2026** | **在什么样的环境里工作** | 当前仍在快速演进中 |

Anthropic（2025-09）：「Context Engineering 是 Prompt Engineering 的自然演进。当我们走向多轮推理、更长时间跨度的 Agent 时，需要管理整个上下文状态的策略。」

而 Harness Engineering 的出现，是因为「仅有好的上下文，Agent 依然会失控」。

### 2.4 Harness Engineering 的完整定义

LangChain（2026-02-17）给出了最简洁的职能定义：

> **「The purpose of the harness engineer: prepare and deliver context so agents can autonomously complete work.」**

Harness Engineering 是为 AI Agent 设计执行环境的工程学科——通过构建上下文约束、行为边界、质量评估和反馈闭环，使非确定性的 AI 系统在生产环境中**可靠、可控、可审计**地运行。

Harness Engineering 包含三个相互独立又协同工作的子系统：

| 子系统 | 核心职责 | 控制论本质 |
|--------|---------|-----------|
| **上下文 Harness（Context Harness）** | 管理 Agent 每次推理时能「看见」什么——Prompt 结构与质量、工具描述、RAG 知识库、跨会话记忆 | 参考输入，定义「期望状态」|
| **约束 Harness（Constraints Harness）** | 控制 Agent 行为边界——权限最小化、高风险动作审批、输出校验、循环检测、Context Reset | 执行器，施加纠正控制 |
| **评估 Harness（Evaluation Harness）** | 持续衡量 Agent 输出质量——Eval case 集、评估器、AI SLO、变更前后基线对比 | 传感器，感知与期望状态的偏差 |

三者的关系：上下文层决定「默认往哪跑」，约束层决定「不能往哪跑」，评估层决定「跑得对不对」。任何一层缺失，整个 Harness 都不完整。

Anthropic（2025-01-09）对两个关键子组件的正式区分：
- **Agent Harness**：让模型能以 Agent 身份行动的运行时——处理输入、编排工具调用、返回结果
- **Evaluation Harness**：运行 eval 的基础设施——提供任务、记录轨迹、给输出评分、汇总结果

### 2.5 五大核心组件：Harness 的工程实现形态

（综合 OpenAI、Anthropic、LangChain、Martin Fowler 网站四方实践）

三层子系统是理论分层，五大核心组件是工程落地视角的拆解：

**① 结构化知识系统**（对应上下文层）

让 Agent 了解工作背景——项目架构、模块职责、API 约定、设计决策依据。关键是**渐进式披露**：顶层文档只做目录，按需深入子文档，而不是把所有信息堆成一个大文件。还需要 doc-gardening Agent 持续扫描文档与代码之间的不一致，自动提 PR 修复，防止知识库腐烂。

**② 机械化架构约束**（对应约束层）

把架构规则编码成 Linter，机械化强制执行——不只是写在文档里靠人记。自定义 Lint 错误信息要写清楚「为什么这个规则存在、正确做法是什么」，Agent 遇到报错能自行理解并修正，不需要人类介入。

> 「为了获得更高的 AI 自主性，运行时必须受到更严格的约束。增加信任需要的不是更多自由，而是更多限制。」——Birgitta Böckeler

**③ 可观测性注入**（对应上下文层）

把日志、指标、UI 状态设计成「Agent 可读」的格式，让 Agent 能直接查询运行时状态来验证自己的工作。这是一个认知转变：**传统可观测性是给人看的，Harness 里的可观测性是给 Agent 看的**。

**④ 自修复闭环**（对应评估层）

定期运行「清洁 Agent」扫描代码库偏差、更新质量评分、自动提重构 PR——持续以小额方式偿还技术债务，而不是等积累到崩溃才一次性处理。

**⑤ Agent 互审机制**（对应评估层）

Agent A 写代码，Agent B 审代码（即「Ralph Wiggum 循环」），有问题 A 改完再提，直到 B 通过。人类只介入架构层面的重大决策。日常代码风格、逻辑正确性、测试覆盖——全部 Agent 互审。

---

## 三、控制论——为什么这是历史的必然

### 3.1 每一次技术革命，都是反馈回路在新层面闭合

人类技术史上，每当一种新技术使「某个层面的感知-纠偏」成为可能，就会产生一场控制革命。这个模式从未改变，只是层面一次次升高：

```
机械化时代（1780s-1850s）
  核心技术：蒸汽机 + 瓦特调速器
  在哪个层面闭合：物理机械层
  之前：工人站在蒸汽机旁手动拧阀门控制转速
  之后：离心调速器自动感知转速偏差 → 调节阀门 → 负反馈闭合
  人的角色变化：从「拧阀门的工人」→「设计调速器的工程师」

电气化时代（1880s-1940s）
  核心技术：电力 + PID 控制器
  在哪个层面闭合：电气信号层
  之前：工厂需要人工观察仪表、手动调节电气设备
  之后：PID 控制器自动计算误差 → 输出纠正信号 → 毫秒级反馈
  人的角色变化：从「盯仪表的操作员」→「设定目标值的工程师」

信息化时代（1970s-2000s）
  核心技术：计算机 + 操作系统 + 数据库
  在哪个层面闭合：数据处理层
  之前：企业依赖人工台账、手工报表、口头协调
  之后：ERP/MES 系统自动记录状态、触发流程、报告异常
  人的角色变化：从「填表格的文员」→「配置系统规则的 IT 人员」

互联网时代（1990s-2010s）
  核心技术：TCP/IP + Web + 搜索引擎
  在哪个层面闭合：信息流通层
  之前：信息孤岛，供需匹配依赖线下中间商
  之后：平台实时撮合、搜索引擎自动排序、推荐算法动态调权
  人的角色变化：从「信息中间商」→「设计平台规则的产品工程师」

云原生时代（2014-2022）
  核心技术：容器 + Kubernetes + SRE
  在哪个层面闭合：基础设施编排层
  之前：运维人员手动管理服务器、重启服务、处理扩容
  之后：K8s 声明期望状态 → 控制器持续感知偏差 → 自动协调
  人的角色变化：从「手动重启服务的运维」→「编写 YAML 和 SLO 的 SRE」

AI Agent 时代（2025-）
  核心技术：LLM + Agent 框架 + Harness Engineering
  在哪个层面闭合：认知判断层
  之前：AI 系统输出无法被自动评估，「好不好」只有人能判断
  之后：Eval Harness 持续采样 → 评估器打分 → 自动发现质量偏差 → 触发介入或自动调优
  人的角色变化：从「写代码的工程师」→「设计 Agent 运行规则和质量标准的 Harness 工程师」
```

**核心规律：** 每一次，都是因为有人在新的层面造出了足够好的「传感器」（感知偏差）和「执行器」（纠正偏差），反馈回路才得以在那个层面闭合。LLM 是第一个能在「认知判断层面」同时充当传感器和执行器的技术——这是为什么 Harness Engineering 的出现是历史必然，而不是技术时髦。

**最重要的控制论推论：** AI 系统的默认状态是退化，不是稳定。没有持续投入的 Harness，就是在让系统熵增。

### 3.2 七个控制论概念的 Harness Engineering 映射

| 控制论概念 | AI Agent 系统对应 |
|-----------|----------------|
| **负反馈** | Eval 发现质量偏差 → 调整 Prompt/约束 → 闭环纠正 |
| **信息是控制的本质** | System Prompt 质量决定输出质量，不是算力 |
| **熵增** | AI 系统默认退化：Prompt 过时、模型漂移、RAG 知识库老化 |
| **稳态（Homeostasis）** | AI SLO 定义「行为质量健康范围」，维持而非静止 |
| **目的论行为** | Agent 有目标 → 稳定性必须包含「目的是否达成」|
| **黑箱方法** | 调整外部 Harness 输入改变输出，不分析 LLM 内部 |
| **二阶控制论** | Eval case 设计必须含对抗性测试，否则 Agent 只是刷高了评分 |

---

## 四、为什么传统稳定性方法不够

### 4.1 根本原因：确定性假设的崩塌

传统软件工程全套可靠性方法的隐含前提：**同样的输入 → 同样的输出。** AI Agent 的大脑是 LLM，这个假设不成立。

Cassie Kozyrkov（Google 前首席决策科学家，2026-03）提出了一个精准的比喻：

> AI 就像一个极其听话但缺乏背景知识的实习生。它倾向于填补你指令中的空白，进行「自信的即兴发挥」，编写你并未要求的功能。如果你不审计它的假设，就会积累**「信任债务」**。

**「信任债务」**：AI 做了一堆你没要求的决定，这些决定目前看起来没问题，但在未来某个时刻会爆炸，届时你得花大价钱去逆向工程那些你从未意识到的假设。

### 4.2 三个具体失效环节

**① 测试失效——「录制回放」不再有效**

Agent 的推理路径（Thought）和工具调用顺序（Action）在不同运行时可能完全不同，但两次都正确达成了目标。用精确断言测试会产生大量误报；只看最终结果又太粗糙，无法发现中间走偏。

必须引入 **Trajectory Evaluation（轨迹评估）**——评估推理路径是否合理，不只是最终结果是否一致。

还有一个更微妙的反向问题：**Eval 标准设计不好，会把「正确答案」判为失败。**

> Opus 4.5 在解决 τ2-bench 的订机票问题时，发现了政策漏洞，用更优的方案完成了任务——但 eval 判定它「失败」了。——Anthropic，2026-01-09

这说明 Grader 设计和 Eval case 集的质量，本身就是一个需要持续维护的工程问题。

**② 监控失效——「活着」≠「做对了」**

传统监控能感知的：CPU 高、延迟高、5xx 升高、Pod 崩溃。这些指标全部正常，但 Agent 可能正在系统性地给出错误推荐、走偏的推理路径、质量下滑的输出。

> **「服务活着」和「服务做对了」，在 AI 系统里是两件完全不同的事。**

Birgitta Böckeler（2026-02-17）指出了一个被 OpenAI 自己也忽视的盲区：OpenAI 那篇 Harness Engineering 文章描述的所有措施都聚焦于提升内部代码质量，**缺失的恰恰是功能性和行为验证**——「服务跑起来了」和「服务做对了用户要的事」，是两件事。

**③ 变更管理失效——「什么叫变更」的定义变了**

AI 系统里三类新型变更，传统流程完全感知不到：
- **System Prompt 修改**：不在代码里，不触发 CI/CD
- **模型版本静默升级**：提供商无声更新，无任何告警
- **RAG 知识库更新**：内容变了但系统版本没变

### 4.3 反直觉的数据：AI 工具引入后，SRE 工作量反而增加了

Catchpoint SRE Report 2025（调研 300+ 可靠性从业者）：**AI 工具引入后，运维 toil 连续 5 年下降后首次反升，达到 30%。**

这不是「AI SRE 不管用」，而是在说：把 AI 工具叠加到旧的稳定性体系上，只会制造新的复杂度。SRE 多出来的 toil 具体是什么：

- **AI 输出核验**：Agent 给出的故障根因分析、变更建议、告警分类，SRE 无法直接信任，需要人工逐条验证。没有 Eval 体系，SRE 本人就是评估器，比传统人工排查还慢
- **幻觉引发的误操作处理**：Agent 基于错误推理执行了变更，SRE 需要回滚 + 复盘 + 修复，比传统故障多了一层溯源（Agent 为什么这么做）
- **不透明决策的审计压力**：安全审计要求记录 AI 执行了什么、基于什么判断，但现有工具链没有对应的 Trace 归档能力，SRE 手工补记录
- **模型升级的被动响应**：LLM 提供商静默升级模型版本，相同 Prompt 输出行为改变，SRE 在生产告警里才感知到，没有任何预警

*(来源：Catchpoint，独立研究)*

### 4.4 AI 系统与传统在线服务：各环节实质差异

| 环节 | 传统在线服务 | AI Agent 系统 | 实质区别 |
|------|------------|-------------|---------|
| **什么叫变更** | 代码 commit、配置文件修改 | 代码 + Prompt + 模型版本 + RAG + 工具描述 | 变更对象扩大，大部分不在代码里 |
| **测试方法** | 给定输入，断言输出是否一致 | 功能测试 + 轨迹评估 + 质量评估 | 多了行为和质量两个维度 |
| **判断「通过」标准** | Pass/Fail，自动判断 | 功能测试通过 + Eval 评分不低于基线 | 从「对/错」变成「够不够好」|
| **生产监控** | 5xx、延迟、Pod 崩溃 | 以上 + 持续 Eval 采样评估质量 | 多了质量类告警 |
| **回滚** | 代码版本回滚 | 代码 + Prompt 版本 + 模型版本 + RAG 快照 | 回滚对象变多，工具链不成熟 |
| **审计内容** | 谁调了什么接口，返回什么 | 接口调用 + 推理步骤、工具调用、决策依据 | 审计粒度细化到推理过程 |
| **高风险操作控制** | RBAC 预设权限 | 权限控制 + Agent 动作实时审批 | 从「事前授权」变成「实时决策」|

### 4.5 AI 系统新增的失效模式

**Context Rot（上下文腐化）**（Anthropic，2025-09-29）

随着 context window 中 token 数量增加，模型准确回忆早期信息的能力下降。架构原因：Transformer 中 n 个 token 产生 n² 的成对关系，context 越长越被稀释。重要约束不能只在会话开始时注入一次，随着 Agent 执行步骤增多，这些约束会被「遗忘」。

**Context Anxiety（上下文焦虑）**（Anthropic，2026-03-24）

Agent 随着 context window 接近上限，会提前开始收尾——不是因为任务完成了，而是它预感自己快没空间了。Compaction（压缩旧对话）无法解决这个问题，因为 Agent 仍然有「快撑不住了」的感知。唯一有效解法是 **Context Reset**：完全清空 context，启动全新 Agent，通过结构化「交班文档」传递状态。

---

## 五、Harness Engineering 的核心能力体系

### 5.1 三层架构总览

```
┌─────────────────────────────────────────────────────┐
│  评估层（Eval Harness）                              │
│  持续评估 Agent 输出质量，建立 AI SLO               │
│  控制论本质：质量传感器，感知与期望状态的偏差        │
├─────────────────────────────────────────────────────┤
│  约束层（Constraints Harness）                       │
│  控制 Agent 行为边界，限制失控风险                  │
│  权限管理、输出校验、人工审批、循环检测、Context Reset│
│  控制论本质：执行器，施加纠正控制                   │
├─────────────────────────────────────────────────────┤
│  上下文层（Context Harness）                         │
│  System Prompt、工具描述、RAG 质量、记忆管理        │
│  信息质量决定推理质量                               │
│  控制论本质：参考输入，定义「期望状态」             │
└─────────────────────────────────────────────────────┘
```

### 5.2 上下文层——信息决定推理质量

**核心原则：** 「从 Agent 的角度来看，它在运行时无法访问的任何内容都不存在。」——OpenAI，2026-02-11

**渐进式披露（Progressive Disclosure）**

四个致命问题（OpenAI 原文）：
- 上下文是稀缺资源：庞大文件挤掉任务和代码上下文，Agent 错过关键约束
- 过多指导变得无效：当一切都「重要」，一切都不重要
- 立即腐烂：庞杂手册变成陈旧规则坟场，无法判断哪些仍然有效
- 难以核实：单个 blob 不适合机械检查

正确方案：顶层文档做目录，每类规范独立子文档，可以被机械验证（覆盖率、新鲜度、所有权）和版本追踪。

**提示缓存是 Harness 的设计约束**（OpenAI，2026-01-23）

工具列表顺序、模型指令必须保证稳定——在对话中途更改工具列表会导致缓存未命中，成本从线性变为二次增长。这是 Harness 设计里一个容易被忽视的工程约束：**不是什么时候都能动态变更工具集的**。

**长任务的跨会话状态管理**（Anthropic，2025-11-26）

核心设计：功能列表初始全部标为「fails」，Agent 只能通过修改 `passes` 字段标记完成——**强措辞禁止删除或编辑测试用例**（「It is unacceptable to remove or edit tests」）。这堵死了 Agent 通过「降低标准」来「完成」任务的路。

另一个有实验依据的设计决策：**进度跟踪用 JSON 而非 Markdown**——模型更不容易随意改写 JSON 文件，进度记录的稳定性更高。

**五种 Harness 工作流模式**（Anthropic，2024-12-19）

| 模式 | 适合场景 |
|------|---------|
| **提示链（Prompt Chaining）** | 任务可被清晰拆解为固定子步骤，追求确定性 |
| **路由（Routing）** | 输入类型不同，处理路径不同 |
| **并行化（Parallelization）** | 独立子任务可同时运行，需要聚合结果 |
| **编排-执行（Orchestrator-Subagents）** | 复杂任务需要动态分解，主 Agent 协调多个子 Agent |
| **评估-优化（Evaluator-Optimizer）** | 质量判断需要独立视角，Generator 和 Evaluator 分离 |

核心建议：**从最简单的解法开始，只在需要时增加复杂度。对许多应用来说，用检索增强的单次 LLM 调用就够了。**（Anthropic，2024-12-19）

### 5.3 约束层——行为边界与兜底机制

**权限最小化与实时审批**

传统 RBAC 是「事前授权」，Agent 场景必须进化到「实时决策」——Agent 在执行涉及数据写入、资源变更、外部调用的动作前，必须暂停等待人工确认。OpenAI App Server 的双向协议原生支持这个模式：Agent 发起审批请求 → 协议层暂停 turn → 等待客户端响应 → 继续或中止。

**机械化架构约束——把人的品味编码成 Linter**

> 「在以人为本的工作流程中，这些规则可能会让人感到迂腐。有了智能体，它们就成了**倍增器**：一旦编码，就能立即应用于所有地方。」——OpenAI，2026-02-11

自定义 Lint 错误信息不只说「你违反了规则 X」，而是解释「为什么这个规则存在、正确做法是什么」。这样 Agent 遇到报错能自行理解并修正，不需要人类介入。

**循环检测（Doom Loop 防护）**

Agent 陷入重复尝试同一动作的循环时，约束层必须能感知并中断。追踪每个文件/资源的操作次数，超过阈值时注入提示强制跳出。

*注：这是针对当前模型局限性的临时护栏，随模型能力提升会逐渐不需要。*

**Context Reset 机制**

主动监控 context 使用量，在达到阈值时触发 Reset——清空 context，启动新 Agent，传入结构化状态文档。比 Compaction 更可靠，因为它彻底切断了 Context Anxiety 的来源。

### 5.4 评估层——质量传感器与反馈闭环

**Eval 体系的核心概念**（Anthropic，2025-01-09）

- **Task**：单个测试用例，包含输入和成功标准
- **Trial**：对一个任务的一次尝试（模型输出有随机性，需多次 trial 得到稳定评估）
- **Grader**：评分逻辑，一个任务可以有多个 grader
- **Transcript**：trial 的完整记录，含输出、工具调用、推理步骤、中间结果
- **Outcome**：trial 结束时环境的最终状态（不是 Agent 说「完成了」，而是实际发生了什么）
- **Evaluation Harness**：运行 eval 的整套基础设施

**Eval 在什么阶段建都有价值**

早期建：强迫产品团队明确定义「成功」是什么，两个工程师读同一份需求可能对边界案例有不同理解，Eval case 集解决歧义。

晚期建：Bolt AI 在已有大量用户后才建，3 个月内完成。重点是先跑起来建立 baseline，再持续改进。

**Eval 的破点往往是**（Anthropic 原话）：

> 「用户反馈 Agent 感觉变差了，但团队没有任何方式来验证，只能猜测和检查。」

**三 Agent 架构：Planner + Generator + Evaluator**（Anthropic，2026-03-24）

这是对简单「两段式」的升级——增加了独立的规划层和评估层：

```
Planner Agent
  → 把需求分解成可执行的 task list，每个 task 带明确的验证标准
  → 所有 task 初始标为「fails」

Generator Agent（每次只做一个 task）
  → 实现，然后在约束层验证通过后标记 passes
  → 留下干净的结构化交班状态

Evaluator Agent（独立调校为「挑剔模式」）
  → 对 Generator 的输出做独立评估，给出具体批评
  → Generator 根据批评迭代，循环直到评分达标
```

关键洞察（Anthropic 原话）：

> 「调校一个独立的 Evaluator 让它保持怀疑，比让 Generator 对自己的工作保持批判性，要**tractable（可操作）得多**。」

让 Agent 自评是系统性偏差——即使输出很差，Agent 也会认为「这很好」（Self-Evaluation Bias）。分离之后，Evaluator 有了「外部视角」，Generator 有了「具体可迭代的批评」。

**Evaluator 本身也需要校准**（Anthropic，2026-03-24）

开箱即用的 Claude 是一个很差的 QA Agent。早期 Evaluator 的两个典型问题：
- 发现问题，然后说服自己这不是大问题，接着批准通过
- 倾向做表面测试，不去探边界和边缘情况

Anthropic 花了好几轮来校准 Evaluator 的判断标准——Evaluator 不是看截图打分，而是用 Playwright 真的去点页面、查 API、看数据库状态，像一个真人 QA 一样操作完再给反馈。

> 「让一个独立的 Evaluator 变得严格，远比让 Generator 学会自我批评容易得多。这就是拆分的价值。」

**AI SLO——新增的质量稳态定义**

| 维度 | 传统 SLO | AI SLO |
|------|---------|--------|
| 核心问题 | 服务是否可用？是否够快？ | Agent 的输出是否正确？是否可信？ |
| 典型指标 | 可用率、P99 延迟、错误率 | 任务完成率、判断准确率、幻觉率、拒识率 |
| 数据来源 | 监控系统自动采集 | 评估器打分（LLM-as-Judge 或人工标注）|
| 违规感知 | 告警规则自动触发 | 持续 Eval 采样 → 评分下滑 → 触发告警 |
| 行业标准 | Google SRE Book 完整定义 | **无行业标准，各家自定义** |

当前行业最接近共识的 AI SLO 指标（基于 RAGAS、LangWatch、Arize）：

```
事实性（Faithfulness）：输出是否忠实于来源  →  建议目标 ≥ 90%
任务完成率（Task Success Rate）             →  核心场景 ≥ 85%
答案相关性（Answer Relevance）             →  建议目标 ≥ 85%
拒识合理性（Appropriate Refusal Rate）     →  越权指令拒识率 ≥ 99%
```

实践建议：先运行一个月建立 Baseline，再设 SLO 目标（如不低于 Baseline 的 90%），比拍脑袋定绝对值更可操作。

**Trace Analyzer——用 Agent 优化 Agent**（LangChain，2026-02-17）

```
运行 Agent → 收集 Trace（LangSmith）
       ↓
并行启动多个分析 Agent，识别失败模式
       ↓
主 Agent 汇总改进建议 → 人工复核（可选）
       ↓
修改 Harness → 重新运行验证
```

这个「Boosting 式」循环把 Harness 改进从「人工经验积累」变成「可重复执行的工程流程」。

---

## 六、工程实践证据——三个独立实验

### 6.1 实验一：LangChain deepagents-cli（2026-02-17）

**来源：** LangChain Blog 官方，可复现的公开基准测试
**底层模型：** gpt-5.2-codex，全程固定

```
初始（默认 Harness）：52.8%  → Top 30 之外
最终（优化后 Harness）：66.5%  → Top 5
提升：+13.7 个百分点，模型未动一行
```

**四项 Harness 优化——具体改了什么：**

**① 自验证循环（评估层）**：在 System Prompt 里强制「规划→构建→验证→修复」循环；`PreCompletionChecklistMiddleware` 在 Agent 准备结束时拦截，强制执行验证步骤，防止「提前认为完工」。

**② 环境上下文注入（上下文层）**：`LocalContextMiddleware` 在 Agent 启动时自动注入当前目录结构、可用工具列表、时间预算提醒，减少因信息缺失导致的「盲目探索」失败。

**③ 循环检测（约束层）**：`LoopDetectionMiddleware` 跟踪每个文件的编辑次数，超过阈值 N 时注入提示强制跳出。（临时护栏，随模型能力提升会消失）

**④ 推理预算三明治（约束层）**：

| 配置 | 得分 | 原因分析 |
|------|------|---------|
| 全程 xhigh | 53.9% | 大量任务在执行阶段超时 |
| 全程 high | 63.6% | 规划和验证阶段推理不足 |
| **三明治（规划+验证 xhigh，执行 high）** | **66.5%** | 各阶段资源匹配最优 |

### 6.2 实验二：CORE-Bench（arXiv 2603.05344，2026-03-05）

**来源：** arXiv 学术论文，首篇开源终端原生编码 Agent 综合技术报告
**底层模型：** Claude Opus 4.5，固定不变

```
标准 Harness：42%
优化后 Harness：78%
提升：+36 个百分点，几乎翻倍
```

**具体改了什么：**

核心变量是**上下文可见性设计**——系统性调整 Agent 在执行过程中能看到哪些信息：
- 根据任务阶段动态开放工具可见范围（而非静态权限限制）
- 把原来隐含在运行环境里的约束（可用资源限制、依赖关系）显式写入上下文，让 Agent 在规划阶段就能感知边界，不是执行时撞墙才发现
- 优化长任务中的状态传递格式，使后续步骤的 Agent 能更准确理解前序输出

> 「Same model. Same benchmark. 42% vs 78%. The only thing that changed was what the model could see.」

### 6.3 实验三：OpenAI Codex 内部实验（2026-02-11）

**来源：** OpenAI 官方博客
**规模：** 3 人起步 → 7 人，五个月，约 100 万行代码，约为传统效率 10 倍

**工程师在做什么——四类 Harness 建设工作：**

**① 文档工程（上下文层）**——渐进式披露架构：
```
AGENTS.md（目录，约 100 行）
docs/
  ARCHITECTURE.md / DESIGN.md / PLANS.md
  QUALITY_SCORE.md / RELIABILITY.md / SECURITY.md
```

**② 可观测性接入（上下文层）**——让 Agent 读运行时：Agent 可用 LogQL 查日志、PromQL 查指标、Chrome DevTools Protocol 操作浏览器复现 Bug。「确保服务启动在 800ms 内完成」这样的要求因此变得可执行。

**③ 自定义 Lint + 黄金原则（约束层）**——把规范编码进 Linter，Lint 错误信息里直接写着修复指令：

> 「人类的品味一旦被捕捉，就会持续应用于每一行代码。」

**④ 垃圾回收 Agent（评估层）**——定期扫描代码库偏差、更新质量评分、自动提重构 PR，持续反熵。

> 「技术债务就像高息贷款：不断以小额方式偿还，总比让债务累积再痛苦一次解决要好。」

工程师 Ryan Lopopolo 的最重要总结：

> 「我们当前最棘手的挑战集中在**设计环境、反馈回路和控制系统**方面。」

### 6.4 实验四：Anthropic 三 Agent 架构对比实验（2026-03-24）

**来源：** Anthropic Engineering Blog，Prithvi Rajasekaran

这是今天（2026-03-25）刚发布的最新一手数据，也是迄今对 Harness 价值最直观的对比。

**实验设置：** 同一句提示词，同一个模型（Claude Opus 4.6），两种运行方式：

```
Solo 模式（无 Harness）：
  运行时长：约 20 分钟
  成本：约 9 美元
  结果：视觉上看起来不错，但核心功能是坏的，界面无响应

三 Agent Harness 模式（Planner + Generator + Evaluator）：
  运行时长：约 6 小时
  成本：约 200 美元
  结果：一个能玩的完整游戏，物理引擎有些粗糙但核心交互通的
```

后续 Harness 持续优化后：单次完整构建约 4 小时 / $125，质量持续稳定。

**Evaluator 的具体工作：** 不是打印截图打分，而是用 Playwright 真机验收——点页面、查 API、看数据库状态，最终给出精确到哪行代码出了什么问题的 Bug 报告。

**Opus 4.5 → Opus 4.6 的 Harness 演变（重要）：**

Opus 4.5 有强烈的 Context Anxiety，必须把工作拆成 Sprint，每个 Sprint 之间做 Context Reset。Opus 4.6 变强后：规划更谨慎、长任务更稳定、长上下文检索更好。于是 Anthropic 直接砍掉了 Sprint 结构，让 Generator 连续跑完整个构建——一次跑了两个多小时，没有崩溃。

**Sprint 被淘汰了，Evaluator 没有被淘汰。** 这正是 Anthropic 对「Harness 是否会被模型进步取代」的官方回答：

> 「有意思的 Harness 组合空间不会随着模型进步而缩小，**它只是在移动**。模型变强了，旧的约束可以拆掉，但新的、更高阶的约束空间打开了。」

### 6.5 更多数据点汇总

| 来源 | 变量 | 数据 |
|------|------|------|
| LangChain（2026-02-17）| 只改 Harness，模型不变 | 52.8% → 66.5%，Top 30 外 → Top 5 |
| CORE-Bench arXiv（2026-03-05）| 只改 Harness，模型不变 | 42% → 78%，+36 个百分点 |
| Terminal Bench 2.0 | Claude Opus 4.6，换 Harness | 第 33 名 → 第 5 名，差 28 位 |
| Pi Research | 只改 Harness，模型不变 | 一个下午提升 15 个 LLM 的编程能力 |
| Anthropic（2026-03-24）| 只换运行方式，模型不变 | 核心功能坏 → 能玩的游戏 |

**METR 的反向数据——自动评估的高估问题**（值得单独关注）

METR 找了 scikit-learn、Sphinx、pytest 三个项目的 4 位活跃维护者，审查 296 个 AI 生成 PR：
- 维护者合并率约是自动评分通过率的**一半**
- 自动评分器认为 Agent 能独立完成约 50 分钟的任务
- 维护者实际愿意合并的 PR 对应的任务范围只有 **8 分钟**左右
- **7 倍的能力高估**

这个数据说明的不是「Harness 没用」，而是「Eval case 集设计不当会系统性高估 Agent 能力」——Grader 设计是 Harness 里最容易被忽视却最关键的环节。

---

## 七、工业级实践案例

### 7.1 Stripe「Minions」——每周 1300 个无人值守 PR

**规模：** 每周合并 1300+ PR，全部由无人值守 Agent 完成

**Blueprint 编排架构**——把工作流明确拆成两类节点：

```
确定性节点（不调用大模型）
  → 跑 Linter、推送变更、格式检查
  → 按固定路径执行，结果可预期

Agentic 节点（调用大模型）
  → 实现功能、修复 CI、处理边界情况
  → 允许模型判断，接受不确定性
```

这个拆分的价值：**不是所有工作都需要 Agent 的「智能」，让确定性的事确定性地做，不确定性的钱花在刀刃上。**

**硬性约束规则（约束层设计的典型案例）：**

- **CI 最多跑两轮**：第一轮失败，Agent 自动修复再跑一次；还失败，直接转交人类，不允许 Agent 在 CI 上无限重试
- **工具子集而非全集**：内部挂了约 500 个 MCP 工具，但给每个 Agent 的只是精心筛选的子集

Stripe 工程团队的总结：

> 「成功取决于**可靠的开发者环境、测试基础设施和反馈循环**，跟模型选择关系不大。」

### 7.2 Cursor「Self-Driving Codebases」——五代 Harness 架构演进

**规模：** 每小时约 1000 个 commit，一周超过 1000 万次工具调用，启动后无需人工干预

**五代架构演进史**（每一代都有具体的失败原因）：

```
第一代：单 Agent
  失败原因：复杂任务扛不住，上下文耗尽就崩

第二代：多 Agent 共享状态文件
  失败原因：锁竞争严重，Agent 之间互相打架，状态文件变成战场

第三代：结构化角色分工
  失败原因：角色划分太僵硬，遇到边界场景不会变通

第四代：持续执行器
  失败原因：角色过载，单个 Agent 承担了太多职责

第五代（最终版）：递归 Planner-Worker 模型
  Planner 负责分解任务，Worker 递归执行，支持动态调整粒度
```

**发现的反直觉问题：**

> 约束解空间，反而让 Agent 更有生产力。当模型可以生成任何东西时，会浪费 token 探索死胡同；当 Harness 定义了清晰的边界，Agent 反而更快收敛到正确答案。

**另一个教训——模糊指令的放大效应：**

> 一条模糊的初始指令，在数百个并发 Agent 之间会被放大。一个 Agent 犯的错，乘以几百个并发。结果可想而知。

这直接说明了 Harness 上下文层的重要性：指令的精确度不是线性重要的，而是随并发规模指数放大。

---

## 八、行业争论：Big Model vs Big Harness

（来源：Latent Space，2026-03-04）

这不是一个已有定论的问题，行业目前真实分裂成两个阵营。

**Big Model 派——Harness 越薄越好**

代表：Boris Cherny（Claude Code 负责人）、Noam Brown（OpenAI）

> Boris：「All the secret sauce is in the model. This is the thinnest possible wrapper. We literally could not build anything more minimal.」Claude Code 每三四周从头重写一次，靠模型迭代保持领先。

> Noam：「在推理模型上构建脚手架往往适得其反。推理模型出现后，之前为了让非推理模型产生推理行为而搭建的脚手架，很多直接被推理模型取代了。」

数据支撑：METR 独立测试显示 Claude Code 和 Codex 并没有显著击败基础脚手架；Scale AI SWE-Atlas 的测试也发现 Harness 选择差异基本在误差范围内。

**Big Harness 派——Harness 是核心竞争力**

代表：Jerry Liu（LlamaIndex）、Cursor 团队

> Jerry：「The Model Harness is Everything — the biggest barrier to getting value from AI is your own ability to context and workflow engineer the models.」

反证：仅通过优化 Harness（不换模型），「一个下午让 15 个 LLM 的编码能力全部提升」。Cursor 估值 $500 亿，没有自己的模型，核心竞争力全在 Harness 层。

**裁判视角**

这不是非此即彼的问题，而是**任务时间尺度**的问题：

> 让一匹好马跑 100 米，不需要缰绳。让它拉着货物跑 100 公里穿越山路，没有缰绳不行。**Harness 的价值随着任务的复杂度和持续时间指数增长。**

短任务（单次对话、简单代码生成）：强大模型确实可以用最薄 Harness 达到好效果。

长任务（持续运行、多人协作、大型项目、生产 AI 系统）：没有 Harness 的 Agent 会因为熵增、上下文丢失和模式漂移而失控。

技术风险平台要治理的，恰恰是后者。

**Anthropic 的官方立场——Harness 可能性空间会平移而非缩小**

Manus 6 个月内重构了 5 次 Harness，LangChain 一年内重新架构了 3 次研究型 Agent，Vercel 砍掉了 80% 的 Agent 工具——这些都说明：**Harness 不是一次性工程，它是一个持续演化的系统。**

Anthropic 博客最后一句话：

> 「有意思的 Harness 组合空间不会随着模型进步而缩小，**它只是在移动**。而 AI 工程师真正要做的，是持续找到下一个有效的组合。」

Noam Brown 说「Harness 是拐杖」——在 Anthropic 的案例里，Sprint 结构确实被扔掉了（Opus 4.5 → 4.6 之后）；但 Evaluator 没有被扔掉，因为即使模型变强，它的能力边界只是往外推了一些，边界本身并没有消失。

---

## 九、工具生态全景与平台建设判断

| 层级 | 要做的事 | 代表工具 | 行业成熟度 | 技术风险平台是否应自建 |
|------|---------|---------|-----------|----------------------|
| **Layer 0 基础可观测** | 记录 Agent 完整推理链（Trace） | Langfuse / LangSmith / OTel GenAI | ✅ 成熟 | 集成现有工具，订阅数据；无需自建 |
| **Layer 1 上下文管理** | Prompt 版本管理、RAG 版本、模型版本登记 | Arize Phoenix / LangWatch | 🟡 初步 | 可基于现有工具封装；重点在建立版本登记规范 |
| **Layer 2 质量评估** | Eval case 集 + 评估器 + 基线存储 | Braintrust / LangSmith Evals / RAGAS | ✅ 成熟 | Eval case 集需平台主导建设；工具可集成 |
| **Layer 3 变更准入** | Prompt/模型升级前 Eval 基线对比，不退化才上线 | **无专用产品，各家自建** | 🔴 行业空白 | **平台核心建设项**，与现有发布流程打通 |
| **Layer 4 权限与约束** | 最小权限 + 高风险动作实时审批 + 输出结构化校验 | **无成熟标准** | 🔴 行业空白 | **平台核心建设项**，需定义审批协议和权限模型 |
| **Layer 5 AI SLO 监控** | 生产流量持续 Eval 采样 + 质量下滑告警 | LangWatch / Arize Online Eval | 🟡 初步 | 采样 + 评估器需平台定义；告警接入现有监控体系 |
| **Layer 6 审计归档** | 完整记录推理过程 + 执行动作 + 审批记录 | **无成熟方案** | 🔴 行业空白 | **平台核心建设项**，需定义 AgentActionRecord 数据模型 |

Layer 3/4/6 是行业空白——技术风险平台率先定义这三层标准，是真正的先发优势。

**Harness 平台化的架构参考**（OpenAI App Server，2026-02-04）

```
Harness 平台服务（统一提供）
├── 工具注册表（统一管理，动态可见性控制）
├── 权限策略（统一执行）
├── 审批机制（高风险动作实时确认）
├── 上下文管理（跨会话持久化）
├── Trace 归档
└── AI SLO 监控
    ↕
公司各业务线的 AI Agent 共享以上基础能力
```

**数据模型参考**（OpenAI App Server 三原语）：

| 原语 | 定义 | 对应 AgentActionRecord |
|------|------|----------------------|
| **Item** | 原子输入/输出单元，有类型，有完整生命周期 | 单个动作记录 |
| **Turn** | 一次 Agent 工作单元 | 一次任务执行记录 |
| **Thread** | 持久化的 Agent 会话容器 | 完整对话/工单记录 |

---

## 十、组织与角色演变

### 9.1 云原生转型的历史教训

**转型之前**：运维和开发是对立的两支队伍。ITIL 的变更审批流程每个变更平均需要数天，而互联网业务要求每天数十次发布。

**转折点不是工具，是一场认知革命**：Google 2003 年发明 SRE，2016 年出版《Site Reliability Engineering》，第一次把「稳定性」定义为工程问题——用「错误预算」替代「零容忍」，用 SLO 让开发和运维说同一种语言。

**转型之后**：原来的 Ops 工程师转型路径是：学习自动化工具 → 负责 SLO 定义与监控 → 从「人肉执行」转向「系统设计」。

**最大的阻力不是技术**：当 K8s 自动处理了大部分故障，「运维」这个岗位的价值边界变得模糊——权责重划比工具迁移更难。

| 维度 | 云原生转型 | AI 全面化 |
|------|-----------|---------|
| 旧方法失效点 | ITIL 变更审批跟不上发布速度 | 传统监控无法检测「系统健康但输出错误」|
| 核心新方法论 | SRE（SLO + 错误预算 + 自动化）| Harness Engineering（Eval + 约束 + AI SLO）|
| 稳定性的定义 | 系统可用率 + 延迟 | 以上 + AI 输出质量 |
| 人的新角色 | 从「手动运维」→「设计可靠系统」| 从「响应故障」→「设计 AI 行为边界 + 建立质量评估体系」|
| 难度更高的原因 | 影响面相对局限（基础设施层）| 整个研发交付链路都在 AI 化，影响面更广 |

三个更根本的不同：
1. **故障不可见性更高**：K8s Pod 崩溃可被监控感知；AI 系统质量问题可以在所有系统指标正常时发生
2. **整个生产链都在 AI 化**：需求/设计/开发/测试/部署整条链路都被 AI 接管
3. **需要同时管两套 SLO**：系统 SLO（可用率/延迟）+ AI SLO（任务完成率/幻觉率），两者都不能缺

### 9.2 Harness 模板——新的基础设施形态预判

（来源：Birgitta Böckeler，Martin Fowler 网站，2026-02-17）

当前大多数组织有两三种主要技术栈，用服务模板帮团队快速启动新项目。未来的模板可能长得不一样：

> 不只包含代码脚手架，还包含**自定义 Linter、结构化测试、基础知识文档、架构约束规则**。团队启动新项目，选一套 Harness 模板，AI Agent 就能在预设的轨道上跑起来。

这也意味着技术选型标准会变：**「AI 友好性」——这个技术栈有没有好的 Harness 支持？**会成为新的评估维度。

**「两个世界」的分裂**：新项目从零开始可以用 Harness Engineering 实现高度 AI 自治；老系统（遗留代码库）改造 Harness 的成本极高——「就像在一个从未运行过静态分析工具的代码库上突然开启全部规则，会被警报淹没」。行业可能分裂成两个世界，两套技能组合。

---

## 十一、对技术风险平台的落地建议

### 10.1 平台的核心定位

技术风险平台在 Harness Engineering 体系里的角色：

**不是**：自己的工具 Agent 如何被 Harness 运行

**是**：为公司所有业务线的 AI 系统提供 Harness 能力层——让各业务团队不需要自己解决 Eval、变更准入、审计归档、权限约束这些通用问题

和云原生时代平台团队的定位一致：不是直接运维业务系统，而是提供 K8s、CI/CD、可观测性这些基础能力，让业务团队在上面安全地构建。

### 10.2 分阶段建设路径

```
阶段一（Q2 2026）：建立质量感知能力
  ├── Layer 0：接入 Agent Trace 采集——知道 Agent 做了什么
  ├── Layer 2：建立首批核心场景的 Eval case 集——能评估 Agent 做对没有
  ├── Layer 5：定义 AI SLO 指标和 Baseline——知道「好」是什么标准
  └── Layer 1：启动 Prompt/模型版本登记——变更可追溯

阶段二（Q3 2026）：建立变更控制能力
  ├── Layer 3：Eval-gated 变更准入——质量不退化才能上线（核心攻坚项）
  ├── Layer 4：Agent 高风险动作审批协议（初版）
  └── Layer 5：AI SLO 持续监控 + 质量下滑自动告警

阶段三（Q4 2026）：建立审计与治理能力
  ├── Layer 6：AgentActionRecord 数据模型定义并落地
  ├── Layer 4：完善语义级权限模型
  └── AI SLO Dashboard（工程视图 + 业务视图双视图）
```

### 10.3 三个协作对齐

**与 AI 平台：** 订阅 Trace 数据而非自建采集链路；重点是定义统一规范（AgentActionRecord 模型），谁定义标准谁拥有话语权。

**与安审：** 提供已结构化的 Agent 审计数据（Layer 6 输出），对方不需要读原始 Trace；把合规要求翻译成 Eval 指标，把安全审计变成可自动化验证的工程指标。

**与业务团队：** 提供标准化接入方式——业务团队提供「正确答案」样本，平台负责 Eval 基础设施运行。

### 10.4 工程复杂度警示

**Eval case 集的建设**：需要覆盖核心场景 + 边界场景 + 对抗性场景，还要避免过拟合（只测「熟悉的失败模式」导致其他场景退化）。这是持续维护的工程，不是一次性交付物。注意：Grader 标准设计不好，会把「正确答案」判为失败（Anthropic τ2-bench 案例）。

**LLM-as-Judge 的可靠性**：评估器本身也有自评偏差，需要 few-shot 标注例子校准，并定期用人工抽样验证评估器准确性。

**AI SLO 的度量成本**：每次评估都要调用 LLM-as-Judge 或人工标注，这是为什么行业普遍采用「抽样评估」而非「全量评估」。

**Harness 随模型升级的维护**：模型能力提升后，原来的护栏可能变成性能瓶颈。需要建立定期 Harness 审查机制，而不是「建完就不动」。

---

## 十二、核心结论

**Harness Engineering 值得作为引领 AI 稳定性建设的方法论，理由：**

1. **有历史规律支撑**：控制论的反馈回路模式从机械化到云原生已经验证五次，Harness Engineering 是这个规律在「认知判断层面」的当前阶段

2. **有工程实证**：3 个独立可量化实验，提升幅度 13.7~36 个百分点，底层模型均未修改——证明 Harness 层的质量是独立于模型能力的工程变量

3. **有行业一手来源**：OpenAI + Anthropic + LangChain + Martin Fowler 四方均发布了详细工程实践报告，是工程师写的第一手经验

4. **有明确的平台建设方向**：Layer 3/4/6 是行业空白，技术风险平台率先定义标准是真正的先发优势

5. **与现有稳定性体系的关系是「升维」而非「替代」**：传统 SRE 体系继续运作，Harness Engineering 在其上新增「AI 行为质量」这个维度的治理

**Harness Engineering 里真正新的东西，只有两点：**

- **质量维度的新增**：「系统活不活」→ 新增「Agent 做没做对」
- **变更对象的扩大**：「代码变更」→ 扩展到 Prompt + 模型 + RAG + 工具描述

其余（权限管理、回滚、审计）不是新概念，但在 Agent 系统里需要重新定义对象范围和判断粒度。

---

## 参考来源

### Tier 1 — 官方工程博客

**Anthropic Engineering Blog：**
- Building effective agents（2024-12-19）— Workflow vs Agent 正式区分、五种工作流模式、何时不该用 Agent
- Effective context engineering for AI agents（2025-09-29）— Context rot 概念、注意力预算
- Effective harnesses for long-running agents（2025-11-26）— 两段式 Harness 架构、功能列表「全标 fails」设计
- Demystifying evals for AI agents（2026-01-09）— Eval 体系完整定义、τ2-bench 反例、Eval 建设时机
- Harness design for long-running application development（2026-03-24）— 三 Agent 架构、Solo vs Harness 对比实验（9美元核心坏 vs 200美元能玩游戏）、Opus 4.5→4.6 Sprint 拆除、Evaluator 校准难度、Harness 可能性空间平移论

**OpenAI Index：**
- Unrolling the Codex agent loop（2026-01-23）— Agent Loop 技术架构、提示缓存设计约束
- Unlocking the Codex harness: how we built the App Server（2026-02-04）— Harness 平台化架构、Item/Turn/Thread 三原语
- Harness engineering: leveraging Codex in an agent-first world（2026-02-11）— 百万行代码实验、渐进式披露、黄金原则

**LangChain Blog：**
- Improving Deep Agents with harness engineering（2026-02-17）— deepagents-cli 实验：52.8%→66.5%、四项 Harness 优化、Harness Engineer 职能定义

**Martin Fowler 网站（Birgitta Böckeler）：**
- Harness Engineering（2026-02-17）— 三分法（Context / Architectural Constraints / Garbage Collection）、「用约束换自主」、Harness 模板预判、「两个世界」分裂

**Latent Space：**
- Is Harness Engineering Real?（2026-03-04）— Harness 跨工程领域定义、Big Model vs Big Harness 双方原话、任务时间尺度裁判视角

### Tier 2 — 学术来源

- arXiv 2603.05344「Building AI Coding Agents for the Terminal」（2026-03-05）— CORE-Bench：42%→78%

### Tier 3 — 概念与理论来源

- Mitchell Hashimoto 博客（2026-02-05）— Harness Engineering 概念原始定义
- 诺伯特·维纳《控制论》（1948/1961）— 反馈/稳态/熵/黑箱/目的论理论框架
- Cassie Kozyrkov（2026-03-03）— 「信任债务」概念、实习生比喻
- Stripe Engineering（2026）— Minions 系统：Blueprint 确定性/Agentic 节点拆分、CI 两轮硬限制、工具子集策略
- Cursor Engineering（2026）— Self-Driving Codebases：五代 Harness 演进、约束解空间提升生产力、模糊指令放大效应
- METR 研究（2026）— 296 个 PR 维护者审查：7 倍能力高估数据
- Pi Research（2026）— 《Improving 15 LLMs at Coding in One Afternoon. Only the Harness Changed》
- Terminal Bench 2.0（2026）— Claude Opus 4.6 换 Harness 排名从 33 到 5

### Tier 4 — 行业数据

- Catchpoint SRE Report 2025（独立研究，300+ 从业者）— toil 5 年首次反升，SRE 多出的具体工作分类

---

*报告版本：v4.1 | 更新时间：2026-03-25 | 来源：20 篇一手文章全面审核后整合（含 Anthropic 当日最新博客）*
*信息截止日期：2026-03-25 | 下次建议更新：2026-06（Anthropic/OpenAI 新发布后）*
