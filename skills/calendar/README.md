# Calendar

Calendar 提供红薯日历查询、会议工作流与 Focus Time 工作流，供 Agent 获取用户日程与会议室占用等信息。

## 快速开始

1. 在仓库根目录执行：

```bash
./scripts/install.sh cli
```

2. 准备认证：

- 存在 `CLAW_ENV`：确认 `HTTP_PROXY` / `HTTPS_PROXY` 已配置
- 不存在 `CLAW_ENV`：确认本地认证文件 `~/.xhs-auth/token.json` 已准备完成

3. 验证：

```bash
./calendar/run.sh get-personal-settings
./calendar/run.sh query-meeting-rooms --area-id 2 --date 2026-03-03 --max-rooms 10
./calendar/run.sh preview-create-conference --title "测试会议" --begin-time "2026-03-18T10:00:00+08:00" --end-time "2026-03-18T11:00:00+08:00" --participant-names "林浔" --format json
./calendar/run.sh preview-create-focus-time --title "写方案" --begin-time "2026-04-09T10:00:00+08:00" --end-time "2026-04-09T11:00:00+08:00" --format json
```

## 创建会议

- 高阶命令：`preview-create-conference` / `create-conference`
- 支持单次会议与每周重复会议；重复参数使用 `--day-of-week`、`--sequence-end-date`，可选 `--interval-value`
- `run.sh` 仍然只做薄封装，搜人、搜会议室、文档解析、`conferenceReserveCheck` 等固定编排在 CLI 内部完成
- 测试链路时，测试参会人只使用 `林浔`

示例：

```bash
./calendar/run.sh preview-create-conference \
  --title "测试会议" \
  --begin-time "2026-03-18T10:00:00+08:00" \
  --end-time "2026-03-18T11:00:00+08:00" \
  --participant-names "林浔" \
  --document-urls "https://docs.xiaohongshu.com/doc/5b9e614cd512096842f55f3cc1e9f41c" \
  --format json

./calendar/run.sh preview-create-conference \
  --title "带会议室测试" \
  --begin-time "2026-03-17T10:00:00+08:00" \
  --end-time "2026-03-17T11:00:00+08:00" \
  --participant-names "林浔" \
  --meeting-room-name "E201机场" \
  --area-name "上海" \
  --format json

./calendar/run.sh preview-create-conference \
  --title "每周周会" \
  --begin-time "2026-04-08T15:00:00+08:00" \
  --end-time "2026-04-08T15:30:00+08:00" \
  --participant-names "林浔" \
  --day-of-week WEDNESDAY \
  --sequence-end-date 2026-04-29 \
  --format json
```

## 修改与删除会议

- 修改高阶命令：`preview-edit-conference` / `edit-conference`
- 删除命令：`delete-conference`，兼容旧命令 `cancel-conference`
- 重复会议默认按“单次实例”处理；若要编辑整个系列，显式传 `--edit-series`
- 当前重复能力按前端已验证字段实现，范围为“每周重复”；未覆盖月度 / 自定义 RRULE

示例：

```bash
./calendar/run.sh preview-edit-conference 5970029 \
  --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" \
  --format json

./calendar/run.sh edit-conference 5970029 \
  --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" \
  --format json

./calendar/run.sh preview-edit-conference 22262009 --format json

./calendar/run.sh preview-edit-conference 22262009 --edit-series --format json

./calendar/run.sh delete-conference 5970029 --format json
```

## Focus Time

- 预检查命令：`preview-create-focus-time` / `preview-edit-focus-time`
- 真实写入命令：`create-focus-time` / `edit-focus-time`
- 删除命令：`delete-focus-time`，兼容旧命令 `cancel-focus-time`
- Focus Time 没有 `reserveCheck` 接口；预检查命令仅返回解析后的 payload
- 支持单次 Focus Time 与每周重复 Focus Time；编辑整个重复系列时同样使用 `--edit-series`

示例：

```bash
./calendar/run.sh preview-create-focus-time \
  --title "写方案" \
  --begin-time "2026-04-09T10:00:00+08:00" \
  --end-time "2026-04-09T11:00:00+08:00" \
  --day-of-week THURSDAY \
  --sequence-end-date 2026-04-30 \
  --format json

./calendar/run.sh create-focus-time \
  --title "深度工作" \
  --begin-time "2026-04-10T09:30:00+08:00" \
  --end-time "2026-04-10T11:00:00+08:00" \
  --format json
```

## Skill Bundle

发布到任意 skill 目录后，可直接使用：

```bash
<skill-dir>/calendar/run.sh <command> [options]
```

## Skill 文档

- 路由规则、命令模板与示例：[./SKILL.md](./SKILL.md)

## 常见问题

### 调用返回认证错误

- 若存在 `CLAW_ENV`：检查 `HTTP_PROXY` / `HTTPS_PROXY`
- 若不存在 `CLAW_ENV`：检查 `~/.xhs-auth/token.json` 是否存在且包含可用的 common token

### 工具不可见

- 本地 CLI：确认 `./calendar/run.sh` 存在且可执行
- Skill bundle：确认 `<skill-dir>/calendar/run.sh` 存在且可执行

### UserID 缓存到哪里

- 自动识别当前用户时会缓存到：`$HOME/.xhs-calendar-user-cache.json`

### 办公区/楼栋缓存到哪里

- 缓存文件：`$HOME/.xhs-calendar-office-cache.json`
- 默认缓存有效期 7 天，可通过环境变量 `CALENDAR_OFFICE_CACHE_TTL_HOURS` 调整
- 需要立即刷新时，传 `--force-refresh`
