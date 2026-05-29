# 备份差异报告 — 2026-05-30

对比基准：2026-05-29 → 2026-05-30

## 新增文件

- `HEARTBEAT.md` — heartbeat 配置文件（昨日 snapshot 中缺失，已补入）
- `memory/daily-digest/2026-05-28.md` — 每日摘要
- `memory/work-log/2026-05-29.md` — 工作日志

## 变更文件

### memory/.dreams/events.jsonl
- 新增 1 条事件记录：`memory.recall.recorded` (2026-05-29T00:03:35)
- 查询：`work log daily report 2026-05`，返回 9 条匹配结果

### memory/.dreams/short-term-recall.json
- `updatedAt` 更新：`2026-05-28T00:03:35` → `2026-05-29T00:03:35`
- 新增 279 条 recall 记录（M2 第 1 周回顾相关记忆索引）
- 涉及文件：`memory/work-log/2026-05-17.md` 等多个工作日志片段

### memory/self-improving/projects/pending_tasks.md
- Trace 维度评估框架落文任务：拖延天数从 7 天 → 14 天
- 3 个 M2 已关闭任务状态更新：
  - searchadstrigger SOP：`M2 已关闭，M3 承接` → `顺延 4 天，M3 承接`
  - 广告收入诊断 SOP：`M2 已关闭，M3 承接` → `顺延 4 天，M3 承接`
  - RPC 异常排查 SOP：`M2 已关闭，M3 承接` → `顺延 4 天，M3 承接`

## 未变更文件

- `MEMORY.md` — 无变化
- `SOUL.md` — 无变化
- `AGENTS.md` — 无变化
- `ROUTING.md` — 无变化
- `USER.md` — 无变化
- `IDENTITY.md` — 无变化
- `TOOLS.md` — 无变化
- `agents/` 目录 — 无变化
- `memory/` 目录下其余文件 — 无变化

## 摘要

| 指标 | 数值 |
|------|------|
| 新增文件 | 3 |
| 变更文件 | 3 |
| 未变更核心文件 | 7 |
| 核心配置文件变更 | 0 |
