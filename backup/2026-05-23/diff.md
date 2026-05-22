Comparing with backup/2026-05-22...
Generated: 2026-05-23 02:01:38 CST

## `MEMORY.md` — 14 lines changed
```diff
--- backup/2026-05-22/MEMORY.md	2026-05-22 02:01:16.535634057 +0800
+++ backup/snapshot/MEMORY.md	2026-05-22 08:02:51.356636893 +0800
@@ -16,7 +16,8 @@
 - [ ] execute_tool Span 框架层采集现状确认（拖延 38 天+，跨 M1/M2）
 - [ ] 告警诊断需求文档 v0.6 与对话 v0.2 合并归档（拖延 38 天+，跨 M1/M2）
 - [ ] xray-log-query P0 SKILL 修复（subApplication 参数格式说明，拖延 38 天+，跨 M1/M2）
-- [ ] Trace 维度评估框架落为正式文档（REDoc 或文件，5/15 讨论完成 5 维度体系但未落文）
+- [ ] Trace 维度评估框架落为正式文档（REDoc 或文件，5/15 讨论完成 5 维度体系但未落文）—— 拖延至第 7 天
+- [ ] diagnosis-skill-builder V1 与 biz-diagnosis-creator 的关系理清（合并 or 分工 or 保留两个）
 - [ ] 新项目 `mahengyang/obs-token` 云效流水线创建（4/29 启动，Agent 已给 3 个方案，待用户确认语言栈和类型）
 - [ ] LangChain Deep Agents 学习笔记收集（4/29 建立协作机制，用户开始学习中，`langchain-learning-notes.md`）
 - [ ] 5-6 月双月 OKR 转 REDoc 文档（定稿已完成，待归档）
@@ -164,6 +165,17 @@
 - **核心叙事是操作不是查询**：认领、静默等操作能力才是卖点，查询只是入口
 - **部署方式一句话带过**：「一份 Skill，多种入口」即可，不需要三个卡片展开
 
+### Problem 类告警通用排查框架（2026-05-21 确认）
+- 三层递进：① Problem 异常趋势 → 定位具体飙升的 exception；② RPC 指标 → 判断上下游依赖问题；③ 服务自身 → CPU/内存/变更
+- 素材来源：adcenter-service-tob 真实 P1 告警（#194554127，UncheckedTApplicationException）
+- 可推广为 KR1 通用诊断能力的基础模板
+
+### 搜索广告 Trigger 告警 SOP（2026-05-21 确认）
+- 6 步排查链：流量突增 → 一/二段式时延判断 → 一段式算子级时延 → 二段式算子级时延 → 近期变更查询 → 原因未知
+- 数据源：vms-search（proxy:75）、vms-ads、XRay 变更查询
+- 时延四分支判断：仅一段涨/仅二段涨/都涨/都不涨，分别导向不同排查路径
+- 关键发现：searchadstrigger 的可用性告警规则未在平台注册，是独立自定义 PromQL
+
 ### 投资关注
 - 重点关注AI产业链：英伟达、AMD、台积电、SK海力士、三星
 - 特别关心HBM（高带宽内存）市场动态
```

## `SOUL.md` — no changes

## `AGENTS.md` — no changes

## `ROUTING.md` — no changes

## `TOOLS.md` — no changes

## `USER.md` — no changes

## `IDENTITY.md` — no changes

## `HEARTBEAT.md` — no changes

## memory/ directory
No new files

---
**Snapshot size:** 1.4M
**Total files:** 142
