# 成长报告 2026-W15（2026-04-07 至 2026-04-13）

> 生成时间：2026-04-12 20:00 (Asia/Shanghai)
> 覆盖日记：2026-04-06、2026-04-07、2026-04-08、2026-04-09
> 活跃天数：4天（周一至周四，密集产出）

---

## 一、本周重要事件

### 🧪 xray-log-query SKILL 完整评估（2026-04-06）

本周开局以完整的 SKILL 评估收场，形成了 W15 的第一个重要交付物。

**评估对象**：`xray-log-query` SKILL  
**接入点**：`https://xray-agent.devops.xiaohongshu.com/`  
**综合得分**：4.33/5.0，PASS ✅（10 题通过率 9/10）

| 用例 | 得分 | 判定 | 说明 |
|------|------|------|------|
| S1（error日志聚类） | 4.67 | ✅ | 稳定 |
| S2（趋势查询） | 4.17 | ✅ | 正常 |
| S3（关键词搜索OOM） | 4.50 | ✅ | 正常 |
| S4（traceId查日志） | 4.83 | ✅ | 最佳 |
| S5（pod名过滤） | 3.67 | ⚠️ | 唯一WARN |
| B1（不存在服务名） | 5.00 | ✅ | 满分 |
| B2（未来时间段） | 5.00 | ✅ | 满分 |
| B3（24h全量降级） | 4.17 | ✅ | 正常 |
| C1（日志+traceId关联） | 4.17 | ✅ | 正常 |
| C2（归因+建议） | 4.83 | ✅ | 近满分 |

**4 个核心问题（均归因到 SKILL 设计）**：
1. **P0**：pod 名被误识别为服务名（`subApplication` 参数缺少格式描述）
2. **P1**：内部接口路径 `/charts` 泄露到回答（description 使用技术词汇暴露内部实现）
3. **P1**：响应普遍 70-145s（未约束返回字段/数据量，全量返回拖慢速度）
4. **P2**：24h 降级策略静默执行，无 `sampled: true` 标记

**同日另一成果**：`skill-evaluator` SKILL 持续优化  
- commit `a670d75`：Phase 0 增加 Agent 接入点强制确认  
- commit `8b1a5e0`：执行阶段进度反馈 + 各题详情展开 + 问题归因到 SKILL  
- commit `70a1481`：对齐参考报告格式

**`corrections.md` 终于建立**（连续 W13/W14 未执行，今日补上）。

---

### 📄 AI Agent/Skill 可观测性规范文档编写（2026-04-07）

用户主导编写小红书内部《AI Agent/Skill 可观测性标准》，作为 TC 会上工程底线规范之一。整日与用户深度协作，历经多轮迭代最终定稿 v9。

**文档结构（最终版 v9）**：
```
一、适用分级与对象说明（三类对象：LLM推理引擎/Skill/Agent）
二、指标监控（Metrics）—— 按对象分节 2.1/2.2/2.3
三、链路追踪（Tracing）—— 按对象分节 3.1平台/3.2LLM/3.3Skill/3.4Agent
四、日志规范（Logging）—— 4.1公共/4.2Skill/4.3Agent+全链路行为轨迹
五、告警规范 —— 5.1LLM/5.2Skill/5.3Agent
六、效果评测与SLO —— 6.1评测/6.2SLO规范/6.3变更管控衔接
```

**核心设计决策**：
- **三类对象区分**：LLM推理服务/Skill/Agent，失控形态不同，观测重点不同
- **强制收窄原则**：只强制"没有会出严重问题"的条款，每条强制加"为什么"
- **SLO建立方式**：跑 30 天 Baseline，目标 = Baseline × 90%，禁止拍脑袋定绝对值
- **阈值不一刀切**：TTFT 参考值 5s，按模型和场景设定，不写死绝对值
- **"AI 全链路行为轨迹"** 替代"Transcript"（全文 7 处已替换）

**萧峰评论处理**（当晚 22:59 完成第八章完整重构）：
- 推理失败率 P1→P0
- TTFT 改为"按模型和场景设定，参考值5s"
- 高危 Skill 临时定义：写操作类，待 Skill 规范出台后正式化
- Skill 日志加 `caller_id` 字段

**文档 URL**：https://docs.xiaohongshu.com/doc/dbd504a41040e770af1d35ebc19c81fa

---

### 🖥️ XRay 告警诊断 Hi IM 交互原型（2026-04-08，高强度设计日）

全天密集迭代，产出了 XRay 告警 AI Native 化的完整交互原型。

**最终主文件**：`xray-native-v2.html`（136KB）  
**最新链接**：https://ep-redim-i2.xhscdn.com/redcity_open/20260408/7b90710804744864aba04fe289f028e8.html

**五节点产品结构（最终）**：
1. **产品链路全貌** — A/B/C 三条链路，共享能力底座，场景关系图
2. **节点2 · 绑定闭环** — 对话绑定 + 页面绑定双 Tab（iframe 内联改造）
3. **节点3 · 诊断报告** — 四状态告警卡片（已诊断/诊断中/未绑定/诊断失败）
4. **节点4 · 天级日报** — AI 判断置顶 + 行动项 + 数据下沉
5. **Claw 配置链路** — Claw × XPILOT A链路配置方案

**关键设计决策**：
- Claw 只负责 A 链路（配置阶段），B/C 链路（Hi IM 推送+诊断）完全不变
- 诊断报告新增「推理过程」折叠块（6步透明化）
- Hi IM 群是告警推送主战场（多人协作场景），Claw 是个人补充入口
- 智能预选：Claw 根据规则名称和 SKILL 描述自动预选，减少用户判断负担

**踩坑记录（HTML 工程教训）**：
- iframe 嵌入在 `file://` 跨域白屏 → 改为完整内联（加 `.xps-` 前缀）
- switchScene 依赖 `event.currentTarget`，通过 switchSceneById 跳转时无 event → 建议不依赖 event 对象
- 修改局部结构时标签不对称导致整个 DOM 崩溃 → 改局部时必须仔细核对开闭标签

---

### 🏗️ AgentOps 平台规划深度输出（2026-04-09，最密集工作日）

全天完成从框架到细节的完整 AgentOps 规划输出。

**REDoc 正式文档**：https://docs.xiaohongshu.com/doc/a0168b4690f635223bf562b8f880b43e  
**本地原稿**：`agentops-ops-detail.md`（600行）+ `agentops-native-detail.md`（836行）

**两大方向框架**：

**方向一：OPS for Agent**（平台做什么）
- 五个能力柱子：发布变更 / AI 评估 / AI 可观测 / 成本治理 / 安全护栏
- AI 评估是质量传感器，驱动其他四柱决策
- 三条最佳实践流程：A 发布流 / B 质量异常响应流 / C 全生命周期主线（C 为总纲）
- 全局 13 个卡点清单

**方向二：Agent Native**（以什么姿态提供服务）
- Ops Agent：7 类意图，上下文记忆，Claw 接入
- Skill 化能力：10 个原子 Skill，完整 Schema
- 事件总线：12 个双向事件，三阶段演进（Webhook→MQ→统一总线）

**行业一手技术洞察（深度调研）**：
- **安全护栏**：间接 Prompt 注入是最高危攻击面（RAG 召回/Tool 返回值里埋指令）
- **NeMo**：并行 Rail 编排，延迟仅 +0.5s，检测率 +1.4x
- **OTel GenAI SemConv**：应对齐 OpenTelemetry 语义规范，AI Span 和 HTTP Span 才能在同一 Trace 树共存
- **LangSmith 四类评估模式**：Benchmarking / Unit Tests / Regression Tests / Backtesting

**⚠️ 重要错误事件**（当晚 20:14 发现）：  
调研内容误写入旧文档 `5c54ceabcf4076bb51ba92eeab3dfd7a`（Agent DevOPS），正确目标是 `a0168b4690f635223bf562b8f880b43e`（AgentOps 平台规划）。已在正确文档写入第七章，两个文档定位已明确区分。

**文档重构记录**（当晚修复，21:17 完成）：
- `docs:get` 仅返回前 100 块（API 限制），全量读取需 `--offset/--limit` 分批
- 全量写入用 `cat file | docs:edit --content -`（stdin 方式），不用 `$CONTENT` 变量（换行会转义）
- REDoc Markdown：`**bold**` 在 redoc-highlight 内会报 parsing error，改用 `<strong>` 标签

**用户评论 18 条分析（当晚）**，形成文档改造方向：
1. AI 可观测改为三视角：稳定性/效果/成本
2. 成本治理并入 AI 可观测（柱子缩为四个）
3. 行业洞察章节融入对应章节（不独立存在）
4. Agent Native 升维为整个 OPS 平台 Native 化

---

## 二、新增执行规则 / 用户偏好

### 调研方式规则（2026-04-09 确立）
- ❌ 不要：泛泛搜索综述文章
- ✅ 要：先列出具体技术术语（如 prompt injection / OTel SemConv / LangSmith API），直接去主流框架**官方文档**找对应章节
- 提取**具体工程结论**（API 设计/数据格式/性能数字），而非概念描述

### REDoc 操作规则（补充/强化）
- `docs:get` API 限制最多返回 100 块，全量读取需 `--offset/--limit` 分批
- 全量写入：`cat file | docs:edit --content -`（stdin），不用 `$VAR`（换行转义导致错乱）
- `redoc-highlight` 中 `**bold**` 会报 parsing error，改用 `<strong>text</strong>`
- delete op 的正确 key 是 `"remove"` 而非 `"delete"`

### HTML 原型工程规则（2026-04-08 确立）
- 修改局部结构时必须核对开闭标签，DOM 树破坏会导致整个页面崩溃
- 避免函数依赖 `event.currentTarget`，程序调用（非点击触发）时无 event 对象
- iframe 在 `file://` 协议有跨域限制 → 生产环境前必须内联 CSS/HTML/JS

### 规范文档写作规则（2026-04-07 确立）
- 强制条款只写"没有会出严重问题"的内容，每条必须加"为什么"说明
- 阈值给出参考值 + 标注"需与业务确认"，不拍死也不空洞占位
- SLO 建立策略：Baseline × 90%，禁止拍脑袋定绝对值

---

## 三、错误与纠正

### [纠正] 评估方式绕过 Agent 接入点（2026-04-06）
- **错误**：初次评估时直接调底层脚本，未通过 Agent 接入点
- **纠正**：必须通过浏览器访问真实 Agent 接入点
- **修复**：skill-evaluator Phase 0 增加强制确认步骤

### [纠正] 跳过 Phase 1.5 试跑（2026-04-06）
- **错误**：用户确认题目后直接 spawn 全量 10 题
- **纠正**：必须先试跑 2-3 题打分展示给用户确认
- **修复**：Phase 2 入口增加强制前提检查，Phase 1.5 明确"禁止跳过"

### [纠正] 内容写入错误文档（2026-04-09）
- **错误**：AgentOps 行业洞察写入了旧文档 `5c54ceabcf` 而非正式文档 `a0168b4690`
- **纠正**：在正确文档写入第七章，两文档定位已区分并记录在日记
- **根因**：shortcutId 相似，切换操作上下文时未核对

---

## 四、核心洞察

### 1. Skill 工程质量是 Agent 能力天花板
xray-log-query 评估再次验证：Skill 设计缺陷（参数描述不清/内部路径泄露/无数据量约束）直接映射为 Agent 的行为缺陷，而非 Agent 推理能力问题。**修 SKILL，而不是责怪 Agent。**

### 2. 规范文档的力量在"强制收窄"
AI 可观测性规范的核心价值不是"列出所有可观测的东西"，而是"只强制那些没有就会出严重问题的条款"。这个原则适用于所有工程规范文档。

### 3. 竞品调研的正确姿态
"泛泛综述"和"官方文档具体数字"的信息密度差距在 10 倍以上。Prompt injection +1.4x 检测率、OTel SemConv span attribute 名称——这些才是规划文档的工程底气。

### 4. AgentOps = OPS 平台 Agent Native 化
AgentOps 不只是针对 AI Agent 的运维能力，而是整个 OPS 平台以 Agent 作为使用方的 Native 化改造。这个定位升维解决了"Ops Agent 是否有必要独立"的争议。

### 5. Hi IM 群是 AI 告警推送的天然场景
多人协作排障的本质决定了：AI 诊断结论必须推到团队频道（Hi IM 群），而不是个人 1v1 对话框。Claw 是个人操作补充，不是主战场。

### 6. 文档结构管理：API 限制和全量写入
大型 REDoc 文档（>100 块）必须分批读取，全量写入只能用 stdin 管道，不能用变量注入。这是工具层面的硬约束，记住它能省掉大量调试时间。

---

## 五、下周待跟进

### 高优先级（P0/P1）
- [ ] **AgentOps 文档按 18 条评论改造**：AI 可观测三视角重写 / 成本并入 / 行业洞察融合 / Agent Native 升维表述（用户确认后执行）
- [ ] **万豪 Q1 注册截止 2026-04-26**，清明已打卡品牌需更新进度（距截止仅 14 天！）
- [ ] **xray-log-query SKILL 优化**：P0 问题（subApplication 参数格式说明）需本周修复
- [ ] **AI 可观测规范文档**：五个系统性优化方向（Skill 生命周期治理 / Langfuse 自动化 / 成熟度分级）待用户确认是否纳入

### 中优先级（P2）
- [ ] **AgentOps Mockup** 继续迭代（方向一文档改完后同步更新 UI 稿）
- [ ] **数据底座细化**：OPS 数据底座按方向一同等深度输出（用户认可方向，尚未输出）
- [ ] **AgentOps 竞品精准对比表**（Task A，两次搁置，下周尝试推进）

### 持续任务
- [ ] **corrections.md 维护**：每次出错同步记录，不只写日记
- [ ] **MEMORY.md 更新**：本周重大成果蒸馏（已在本文件底部执行）

---

## 六、统计数据

| 维度 | 数据 |
|------|------|
| 活跃工作天数 | 4天（周一至周四）|
| 日记文件数 | 4个（04-06/07/08/09）|
| REDoc 文档输出 | 2篇（可观测规范 + AgentOps 规划）|
| HTML 原型文件 | 7个（xray-native-v2 等）|
| Skill 评估完成 | 1个（xray-log-query，10题）|
| corrections.md 记录 | 3条（均有修复措施）|
| 代码 commits | 3个（skill-evaluator 优化）|

---

*生成时间: 2026-04-12 20:00 Asia/Shanghai*  
*下一份: 2026-W16-growth-report.md*
