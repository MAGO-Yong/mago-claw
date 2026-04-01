---
name: hi-calendar
version: 1.0.0
description: 'hi 官方日历 Skill，支持查询会议室区域与预约情况、自动定位空闲会议室、创建/编辑普通日程和循环日程（按周重复）、取消日程，支持关联腾讯会议、添加参会人、文档自动赋权'
metadata: { 'openclaw': { 'requires': { 'bins': ["pnpm"] } } }
---

# hi-calendar

调用任何 cli 命令之前，请先检查它：

```bash
pnpm dlx @xhs/hi-workspace-cli@0.2.5 calendar --help

# 查看具体命令的参数（含输出格式）
pnpm dlx @xhs/hi-workspace-cli@0.2.5 calendar:<method> --help
```

以下是 `--help` 中没有的约束和指引。

## 时间参数

- 当前时间必须以**系统时间**为唯一依据，禁止自行假设当前日期、当前时间、当前时区。
- 所有时间参数均使用 **ISO 8601 格式**
- 所有相对时间表达（今天、明天、昨天、本周、当前、最近）都必须基于当前时间

## 通用规则

- **幂等**：每个创建操作须单独调用 `generate-operate-code` 获取新的 operateCode，不同操作之间不得共用。同一操作失败重试时复用同一 operateCode，最多 3 次
- **参会人确认**：通过 `search:employee` 查找参会人时，若存在多个同名人员，须向用户确认具体是哪一位
- **区域选择**：`areaId` 禁止猜测或默认，必须让用户明确选择。用户仅提供会议室名称/关键词但未指定区域时，先询问具体区域

## 操作约束

### create / create-recurring

- 确保时间、参会人、会议室三项信息完整，缺失时主动询问（用户明确说不需要的可跳过）
- 目标会议室在所选时段已有日程时，须告知用户冲突详情并建议调整，不要直接尝试预约
- 使用 `--doc-auto-empower-list` 或 `--doc-module-links` 前，必须向用户确认文档标题和链接正确
- **循环日程**：beginTime 对应的星期几应包含在 weekdays 中。创建前须确认用户期望的持续时间以设置 sequenceEndTime

### edit-schedule

- 须先通过 `get-schedule-detail` 获取当前日程详情，确认变更内容后再执行编辑。仅 `hasDetailPermission=true` 的日程可编辑，否则应告知用户无权限
- 采用 **patch 模式**：仅传变更部分，未传字段保持不变。增删类参数（`--add-*` / `--remove-*`）可只传其中一个

### cancel-schedule

- 须向用户确认具体日程（标题、时间等），操作不可逆
- 循环实例（scheduleInstanceType=3）须询问用户是仅取消这一次还是取消整个系列，取消整个系列时 `--schedule-id` 须传**主日程 ID**

## 查询约束

### get-user-schedules

- 时间范围 ≤ 30 天（2592000000ms），`accountIdList` ≤ 30 个
- 分页：按用户独立分页，每个用户各自有 hasMore

### get-room-schedules

- 时间范围 ≤ 1 天（86400000ms），跨多天须按天拆分多次查询后合并
- 分页：全局分页，固定 50 条/页

### query-room-schedule

- 时间范围 ≤ 30 天（2592000000ms）
- 分页：按会议室独立分页，每个会议室各自有 hasMore

### 分页策略

是否自动翻页取决于用户意图：

- **需要完整数据时自动翻页**：判断空闲时段、多人交叉分析、计数汇总
- **展示即可时只取首页**：浏览日程列表、查找会议室（首页已有可用结果时无需翻页）
- **不确定时**：先展示首页，询问用户是否需要更多

## 核心概念

### 循环日程模型

- `scheduleInstanceType`：`1`=普通日程，`2`=循环主日程，`3`=循环子日程
- type=2 时 scheduleId 即主日程 ID
- type=3 时 scheduleId 是子日程 ID，`sequenceScheduleId` 指向主日程 ID
- 取消系列用主日程 ID + type=series，取消单次用子日程 ID + type=occurrence

### 文档 URL 与 shortcutId

```
URL:        https://docs.xiaohongshu.com/doc/{shortcutId}
shortcutId: URL 末段路径，也是 search:doc 返回的 bizId
```
