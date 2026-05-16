=== Diff: MEMORY.md ===
--- backup/2026-05-16/snapshot/MEMORY.md	2026-05-16 02:01:30.854920016 +0800
+++ backup/2026-05-17/snapshot/MEMORY.md	2026-05-17 02:01:07.013472473 +0800
@@ -13,9 +13,10 @@
 
 ### 待跟进（一次性）
 - [ ] REQ-001 子需求推进（5/12 用户上线定级）：P0-1 页面嵌入（前端已排期✅）、P0-2 Langfuse 同步（接口已有✅）、P0-3 数据集上传（待开发）；P1×3、P2×4 → 详见 requirements.md + requirements-board.html
-- [ ] execute_tool Span 框架层采集现状确认（拖延 33 天+，跨 M1/M2）
-- [ ] 告警诊断需求文档 v0.6 与对话 v0.2 合并归档（拖延 33 天+，跨 M1/M2）
-- [ ] xray-log-query P0 SKILL 修复（subApplication 参数格式说明，拖延 33 天+，跨 M1/M2）
+- [ ] execute_tool Span 框架层采集现状确认（拖延 35 天+，跨 M1/M2）
+- [ ] 告警诊断需求文档 v0.6 与对话 v0.2 合并归档（拖延 35 天+，跨 M1/M2）
+- [ ] xray-log-query P0 SKILL 修复（subApplication 参数格式说明，拖延 35 天+，跨 M1/M2）
+- [ ] Trace 维度评估框架落为正式文档（REDoc 或文件，5/15 讨论完成 5 维度体系但未落文）
 - [ ] 新项目 `mahengyang/obs-token` 云效流水线创建（4/29 启动，Agent 已给 3 个方案，待用户确认语言栈和类型）
 - [ ] LangChain Deep Agents 学习笔记收集（4/29 建立协作机制，用户开始学习中，`langchain-learning-notes.md`）
 - [ ] 5-6 月双月 OKR 转 REDoc 文档（定稿已完成，待归档）
@@ -40,10 +41,19 @@
   - **XRAY-CLI 正式上线（2026-05-13）**：AI-First 设计，默认非交互 + 结构化 JSON 输出，`--human` 进入交互模式
   - Skill = 语言接口（人→AI→XRay），CLI = 程序接口（程序→XRay→JSON）
   - 架构方向：诊断 Skill 内数据采集可换 CLI，Skill 专注推理判断
+  - **Trace 维度评估框架（2026-05-15）**：基于 Trace 的 Skill 评估 5 维度体系
+    1. 准确性（最终 output vs 真实答案、有无幻觉）
+    2. 效率（span 数量、duration、token 消耗）
+    3. 路径合理性（span 顺序、冗余/遗漏）
+    4. 错误处理（降级、静默失败检测、结构化错误）
+    5. 覆盖率（关键数据源是否查全）
+    → 可直接作为公司内部 AI Skill 评估标准规范
+    → seal-sync SKILL 首次实战审计（4.17/10，发现 2 个 P0 问题）
 
 **第二大方向：PM 工作流自动化**
 - 把整个产品研发流程 Agent Native 化（革自己的命）
 - 链路：需求收集→创建→评审→设计→分发→上线文档
+- **claude-proxy + obs-token 调通（2026-05-15）**：内网 LLM 调用链路打通，PM 自动化基础设施就绪。根因：Claude Code settings.json 优先级高于环境变量（port 8090 vs 8089 冲突）
 - 当前状态：方向确定，落地方案待深入讨论
 
 **第三大方向：公司内部 AI 应用规范**

=== Diff: SOUL.md ===

=== Diff: AGENTS.md ===

=== Diff: memory/ ===
只在 backup/2026-05-17/snapshot/memory/daily-digest 存在：2026-05-15.md
只在 backup/2026-05-17/snapshot/memory/work-log 存在：2026-05-16.md

