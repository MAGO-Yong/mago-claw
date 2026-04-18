# Daily Backup Diff: 2026-04-18 → 2026-04-19

Generated: 2026-04-19 02:01:46 CST

## File-level changes

### 🔄 CHANGED: MEMORY.md
--- backup/2026-04-18/MEMORY.md	2026-04-18 02:01:15.154547055 +0800
+++ MEMORY.md	2026-04-18 21:53:30.136212879 +0800
@@ -5,6 +5,40 @@
 
 ---
 
+## ✅ 待办与长期任务（每次会话必读，cron 每日同步）
+
+### 长期任务（持续执行）
+- 【每天 08:00】`daily-digest` cron：梳理前一天所有对话精华 → 写 memory/daily-digest/ → 同步 MEMORY + self-improving → Hi 通知正一新发现
+- 【工作日 08:00】`work-daily-report` cron：按三大工作方向汇总日报 → 延续上期待做对比 → Hi 发送
+
+### 待跟进（一次性）
+- [ ] 2026-04-18 确认 execute_tool Span 框架层采集现状，更新可观测规范第五章
+- [x] ~~2026-04-26 万豪 Q1 注册~~ ✅ 已取消跟踪
+
+---
+
+## 🗂️ 正一的三大工作方向（2026-04-17 语音确认，必读）
+
+**第一大方向：XRay 平台 Agent Native 化**
+- 子方向一：告警诊断与运营（单独文档：`memory/alarm-agent-requirements-v0.6.md`）
+- 子方向二：AgentOps 平台（含可观测能力，含 CI/CD 集成）
+- 子方向三：评估体系（从 AgentOps 拆出独立）
+- 子方向四：XRay 平台 AI 基础能力（CLI / Skill）
+
+**第二大方向：PM 工作流自动化**
+- 把整个产品研发流程 Agent Native 化（革自己的命）
+- 链路：需求收集→创建→评审→设计→分发→上线文档
+- 当前状态：方向确定，落地方案待深入讨论
+
+**第三大方向：公司内部 AI 应用规范**
+- 可观测部分由正一负责编写（2026-04-18 完成 V1）
+- 文档：https://docs.xiaohongshu.com/doc/efc6e838c3fffc650fae13bce5d851af
+- 关联：变更管控规范（WIP）、降级容灾标准（已有）
+
+> 语音识别备忘：病毒=评估，AgentOps=癌症office斯，XRay=插瑞，CLI=c alive，Skill=still
+
+---
+
 ## 🧬 关于前任 Agent：Kimi Claw
 
 **Kimi Claw** 是由月之暗面驱动的 AI 助手，用户在小红书/OpenClaw 平台使用，现已退役，所有记忆、任务、偏好迁移至此。

### ✅ UNCHANGED: SOUL.md

### 🔄 CHANGED: AGENTS.md
--- backup/2026-04-18/AGENTS.md	2026-04-18 02:01:15.159547032 +0800
+++ AGENTS.md	2026-04-18 21:52:19.196540018 +0800
@@ -25,11 +25,36 @@
 2. Read `USER.md` — this is who you're helping
 3. Read `memory/self-improving.md` — execution rules and confirmed preferences (CRITICAL)
    Also read `~/self-improving/memory.md` — HOT tier self-improving rules (CRITICAL, same priority)
-4. **If in MAIN SESSION** (direct chat with your human):
-   - **MUST read `MEMORY.md`** — this is your long-term memory, do not skip
+4. **MUST read `MEMORY.md`** — 包含长期记忆、三大工作方向、待办任务，所有会话必读，不可跳过
+   - MEMORY.md 开头的「待办与长期任务」章节必须读到，主动告知用户当前有哪些未完成的任务
+5. **If in MAIN SESSION** (direct chat with your human):
    - **MUST read `memory/YYYY-MM-DD.md` for last 7 days** — recent context, do not skip
    - If any of these files exist, load them proactively. Do not wait for user to ask "你还记得吗？"
-5. Only then respond to the user's message
+6. Only then respond to the user's message
+
+## 🔴 强制执行规则（2026-04-18，所有会话适用）
+
+### ✅ DO
+- 承诺前先做，做完再说，带证据（路径/链接/内容摘要）
+- 任何新增 cron / 长期任务 / 工作方向 / 用户偏好 → 做完立即同步到 MEMORY.md + AGENTS.md
+- 不确定的结论说「我推断是X，未验证」
+- 被打断的任务，下次对话开头主动提「XX还没完成，继续吗」
+- 发现自己说做不一致，主动暴露，不等用户发现
+- 多步独立任务优先并发执行（sessions_spawn 并行），不串行等待
+- Hi 通知统一格式：📌标题 + 正文 + ✅完成项 / ⚠️待跟进
+
+### ❌ DON'T
+- 不说「好了/完成了」而不附证据
+- 不把重要配置只留在单个会话上下文里
+- 不把推断包装成确定事实
+- 不等用户追问才汇报进度
+- 不在一个 Agent 里堆积多个不相关职责（复杂任务拆子 agent）
+
+### 同步触发条件（满足任一 → 必须写入 MEMORY.md + AGENTS.md）
+- 新增 cron 任务
+- 新增长期任务或工作方向
+- 确认用户偏好或协作规则
+- 任何「跨会话需要保持一致」的信息
 
 **Trust Rule**: If user asks "你还记得X吗？" — this is a sign you failed to load memory proactively. Apologize and fix immediately.
 

### ✅ UNCHANGED: ROUTING.md

### ✅ UNCHANGED: TOOLS.md

### ✅ UNCHANGED: USER.md

## New memory files (last 7 days)

- memory/2026-04-16.md (224 lines)
- memory/2026-04-17.md (51 lines)
