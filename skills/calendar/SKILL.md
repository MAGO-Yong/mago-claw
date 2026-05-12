---
name: calendar
description: 查询和管理小红书内部日历系统（红薯日历）数据：个人设置、订阅、用户日程、会议室空闲情况、节假日，以及会议和 Focus Time 的预检查、创建、修改、删除。当用户提到日程、会议安排、找会议室、查节假日、查看某人日程或空闲时间，或需要创建/修改/取消会议与 Focus Time 时使用。即使用户没有明说"日历"或"会议"，只要涉及时间安排、约人、查空闲、"我明天有没有空"、"帮我定个会"、"找个大家都有空的时间"，也应使用此 Skill。
---

# Calendar

## Configuration

- 仓库内直接调用：`./calendar/run.sh ...`
- Skill 内执行时，优先使用 Skill 根目录命令：`./run.sh ...`

## 刚性规则

- 查自己日程时，可直接 `query-user-schedules`；只有查他人日程且目标用户不明确时，才先 `search-users` 或 `list-subscriptions`。
- `query-user-schedules` 结果需包含文档链接；无文档时返回空数组，视为正常权限裁剪。
- 查他人日程返回 `(无标题)` 不是异常。
- `query-meeting-rooms` 必须至少提供 `--area-id` 或 `--meeting-room-name`。
- 创建会议时，优先使用高阶命令 `preview-create-conference` / `create-conference`，不要手动拼接搜人、搜会议室、文档解析、`conferenceReserveCheck`。
- 修改会议时，优先使用高阶命令 `preview-edit-conference` / `edit-conference`，不要手动拼 `conferenceEditQuery` / `conferenceReserve`。
- 创建 / 修改 Focus Time 时，优先使用 `preview-create-focus-time` / `create-focus-time` / `preview-edit-focus-time` / `edit-focus-time`。
- 周期能力当前按“每周重复”支持；若显式传重复参数，必须同时给 `--sequence-end-date`。
- 会议室结果必须用完整地址：`<楼栋>-<楼层>-<会议室名称>`。
- 返回空闲会议室时，必须标注具体空闲时段，而不是只说“全段空闲”。
- 默认输出 `markdown`；仅在明确要求结构化输出时用 `--format json`。

## 推荐调用链

1. 查日程：
   - 查自己：`run.sh query-user-schedules ...`
   - 查他人且目标不明确：`run.sh search-users <关键词>`（可选）
   - 再执行：`run.sh query-user-schedules ...`
2. 查会议室：
   - `run.sh list-meeting-areas`
   - `run.sh list-buildings-by-area <id>`（可选）
   - `run.sh query-meeting-rooms ...`
3. 其他：
   - `run.sh get-personal-settings`
   - `run.sh list-subscriptions`
   - `run.sh get-entrust-users`
   - `run.sh get-working-calendar`
4. 创建会议：
   - 先执行：`run.sh preview-create-conference ...`
   - 明确需要落库时再执行：`run.sh create-conference ...`
5. 修改会议：
   - 先执行：`run.sh preview-edit-conference <schedule-id> ...`
   - 明确需要落库时再执行：`run.sh edit-conference <schedule-id> ...`
   - 若要修改整个重复系列：追加 `--edit-series`
6. Focus Time：
   - 创建前先执行：`run.sh preview-create-focus-time ...`
   - 修改前先执行：`run.sh preview-edit-focus-time <schedule-id> ...`
   - 明确需要落库时再执行：`run.sh create-focus-time ...` / `run.sh edit-focus-time <schedule-id> ...`
   - 删除：`run.sh delete-focus-time <schedule-id>`
7. 删除会议：
   - `run.sh delete-conference <schedule-id>`

## 命令路由

- 我的设置：`run.sh get-personal-settings`
- 我的订阅：`run.sh list-subscriptions [--limit N]`
- 搜人或会议室：`run.sh search-users <关键词>`
- 某人日程：`run.sh query-user-schedules ...`
- 空闲会议室 / 占用：`run.sh query-meeting-rooms ...`
- 园区 / 楼栋：`run.sh list-meeting-areas` / `run.sh list-buildings-by-area <id>`
- 受托人：`run.sh get-entrust-users`
- 节假日：`run.sh get-working-calendar --year <year> [--month <month>]`
- 会议预检查：`run.sh preview-create-conference ...`
- 创建会议：`run.sh create-conference ...`
- 会议修改预检查：`run.sh preview-edit-conference <schedule-id> ...`
- 修改会议：`run.sh edit-conference <schedule-id> ...`
- 删除会议：`run.sh delete-conference <schedule-id>`
- Focus Time 预检查：`run.sh preview-create-focus-time ...` / `run.sh preview-edit-focus-time <schedule-id> ...`
- Focus Time 创建 / 修改：`run.sh create-focus-time ...` / `run.sh edit-focus-time <schedule-id> ...`
- 删除 Focus Time：`run.sh delete-focus-time <schedule-id>`

## 常用命令

```bash
run.sh get-personal-settings
run.sh list-subscriptions --limit 30
run.sh search-users "王昌旭"
run.sh query-user-schedules --user-ids 167842507 --date 2026-03-03
run.sh query-user-schedules --user-ids 167842507,167842508 --begin-time "2026-03-04T13:00:00+08:00" --end-time "2026-03-04T18:00:00+08:00" --format json
run.sh list-meeting-areas
run.sh list-meeting-areas --force-refresh
run.sh list-buildings-by-area 2
run.sh query-meeting-rooms --area-id 2 --date 2026-03-03 --max-rooms 10
run.sh query-meeting-rooms --area-id 2 --building-id-list 14 --begin-time "2026-03-04T13:00:00+08:00" --end-time "2026-03-04T18:00:00+08:00" --max-events-per-room 10 --format json
run.sh get-entrust-users
run.sh get-working-calendar --year 2026 --month 3
run.sh preview-create-conference --title "测试会议" --begin-time "2026-03-18T10:00:00+08:00" --end-time "2026-03-18T11:00:00+08:00" --participant-names "<参会人姓名>" --document-urls "https://docs.xiaohongshu.com/doc/5b9e614cd512096842f55f3cc1e9f41c" --format json
run.sh preview-create-conference --title "带会议室测试" --begin-time "2026-03-17T10:00:00+08:00" --end-time "2026-03-17T11:00:00+08:00" --participant-names "<参会人姓名>" --meeting-room-name "E201机场" --area-name "上海" --format json
run.sh preview-create-conference --title "每周周会" --begin-time "2026-04-08T15:00:00+08:00" --end-time "2026-04-08T15:30:00+08:00" --participant-names "<参会人姓名>" --day-of-week WEDNESDAY --sequence-end-date 2026-04-29 --format json
run.sh create-conference --title "正式会议" --begin-time "2026-03-18T10:00:00+08:00" --end-time "2026-03-18T11:00:00+08:00" --participant-names "<参会人姓名>"
run.sh preview-edit-conference 5970029 --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" --format json
run.sh preview-edit-conference 22262009 --edit-series --format json
run.sh edit-conference 5970029 --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" --format json
run.sh delete-conference 5970029 --format json
run.sh preview-create-focus-time --title "写方案" --begin-time "2026-04-09T10:00:00+08:00" --end-time "2026-04-09T11:00:00+08:00" --day-of-week THURSDAY --sequence-end-date 2026-04-30 --format json
run.sh create-focus-time --title "深度工作" --begin-time "2026-04-10T09:30:00+08:00" --end-time "2026-04-10T11:00:00+08:00" --format json
run.sh delete-focus-time 1234567 --format json
```

## 缓存

- 用户 ID：`$HOME/.xhs-calendar-user-cache.json`
- 办公区 / 楼栋：`$HOME/.xhs-calendar-office-cache.json`

## 扩展参考

- 总览入口：`./references/README.md`
- 接口事实：`./references/api-analysis.md`
- CLI / 分层设计：`./references/cli-design.md`
- 真实回放结果：`./references/verification.md`

## 失败处理

- 用户未传 `--user-ids` 且自动识别失败：提示显式传入 `--user-ids`。
- 会议室查询参数不足：提示至少提供 `--area-id` 或 `--meeting-room-name`。
- 创建会议搜人命中多个候选：提示改用 `--participant-user-ids`。
- 创建会议搜会议室命中多个候选：提示补充 `--area-name` 或改用 `--meeting-room-ids`。
- 周期会议 / Focus Time 传了重复参数但没传 `--sequence-end-date`：提示补充结束日期。
- 修改整个重复系列：提示追加 `--edit-series`。
- `edit-focus-time` / `delete-focus-time` 指向的不是 Focus Time：明确报错并提示改用会议命令。
- 401/403：提示检查 `~/.token/sso_token.json` 是否存在且包含有效 token。
