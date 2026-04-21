只在 backup/2026-04-22/snapshot/memory 存在：2026-04-21.md
只在 backup/2026-04-22/snapshot/memory/daily-digest 存在：2026-04-20.md
文件 backup/2026-04-21/snapshot/memory/self-improving.md 和 backup/2026-04-22/snapshot/memory/self-improving.md 不同
只在 backup/2026-04-22/snapshot/memory/work-log 存在：2026-04-20.md
文件 backup/2026-04-21/snapshot/MEMORY.md 和 backup/2026-04-22/snapshot/MEMORY.md 不同
只在 backup/2026-04-22/snapshot/memory 存在：2026-04-21.md
只在 backup/2026-04-22/snapshot/memory/daily-digest 存在：2026-04-20.md
diff -ru backup/2026-04-21/snapshot/memory/self-improving.md backup/2026-04-22/snapshot/memory/self-improving.md
--- backup/2026-04-21/snapshot/memory/self-improving.md	2026-04-21 02:01:04.721700320 +0800
+++ backup/2026-04-22/snapshot/memory/self-improving.md	2026-04-22 02:01:01.252301835 +0800
@@ -134,6 +134,22 @@
 
 ---
 
+### 每日/每周总结格式（2026-04-21 确立）
+- ❌ 不要：罗列流水账，P0/P1/P2 混在一起
+- ✅ 要：三层结构
+  1. **📌 重点**：今天最重要的 1-2 件事，一句话说清楚
+  2. **📋 详情**：P0/P1/P2 分层，每个带结论/状态
+  3. **🧬 我学到了什么**：自己的认知变化（不是重复用户知道了什么）
+     - 认知升级：我之前以为X，实际是Y
+     - 规则新增：以后遇到类似情况应该...
+     - 待验证：不确定，需要后续确认
+
+### 用户说"我刚才发给你了"时的处理
+- 先回溯上文仔细查找，不要再次确认
+- 2026-04-20 犯过的错：用户发了聊天记录，Agent 没识别出来反而问"内容还没发"
+
+---
+
 ## 本周新增规则（2026-W15）
 
 ### 调研方式：直接去官方文档拿具体数字
只在 backup/2026-04-22/snapshot/memory/work-log 存在：2026-04-20.md
diff -ru backup/2026-04-21/snapshot/MEMORY.md backup/2026-04-22/snapshot/MEMORY.md
--- backup/2026-04-21/snapshot/MEMORY.md	2026-04-21 02:01:04.719700331 +0800
+++ backup/2026-04-22/snapshot/MEMORY.md	2026-04-22 02:01:01.251301848 +0800
@@ -15,9 +15,11 @@
 - [x] ~~2026-04-18 确认 execute_tool Span 框架层采集现状，更新可观测规范第五章~~ → W16 未跟进，需重新确认
 - [x] ~~万豪 Q1 注册截止 2026-04-26~~ ✅ 用户要求取消跟踪（2026-04-18）
 - [ ] 告警诊断需求文档 v0.6 与对话 v0.2 合并，写入正式文档
-- [ ] 第二大方向（PM 工作流自动化）落地方案讨论
+- [ ] 第二大方向（PM 工作流自动化）落地方案讨论 → 2026-04-20 与小庄探讨 QS AutoFlow 合作可能，待正一整理想法后继续沟通
 - [ ] AgentOps REDoc 文档 18 条评论改造（用户确认后执行）
 - [ ] xray-log-query P0 SKILL 修复（subApplication 参数格式说明）
+- [ ] execute_tool Span 框架层采集现状确认（W16 遗留，可观测规范第五章待更新）
+- [ ] AI 诊断卡片设计确认后进原设计稿节点 3 集成
 
 ---
 
