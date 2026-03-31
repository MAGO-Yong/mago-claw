# Backup Diff: 2026-03-31 → 2026-04-01

Generated: 2026-04-01 02:00 (Asia/Shanghai)

## 核心文件变更
MEMORY.md、SOUL.md、AGENTS.md、ROUTING.md：**无变更**（内容与 2026-03-31 快照一致）

## 新增文件

### memory/
- `memory/2026-03-31.md`（208 行）：3月31日日记，记录当日对话和活动
- `memory/lobi-eval-data.md`（331 行）：Lobi 评测原始数据
- `memory/xray-agent-eval-data.md`（538 行）：XRay Agent 评测原始数据

### agents/ 结构新增
- `agents/invest/memory/` 目录：Invest Agent 记忆目录（新建）
- `agents/investment/` 目录：投资模块独立目录（新建）
- `agents/life/marriott/` 目录：万豪打卡资料目录（新建）
  - `marriott_q1_checklist.md`：Q1 2026 品牌打卡清单
- `agents/life/memory/` 目录：Life Agent 记忆目录（新建）
- `agents/travel/` 目录：旅行模块独立目录（新建）
- `agents/work/deliverables/` 目录：工作交付物目录（新建）
- `agents/work/memory/` 目录：Work Agent 记忆目录（新建）

## 删除/移除
无

## 总结
本次 diff 主要是 agents 子目录结构的扩展（各 Agent 新增了 memory/、deliverables/ 等专属目录），以及 memory/ 目录新增了 3 个数据文件（31日日记 + 两份评测数据）。核心身份文件未发生变化。
