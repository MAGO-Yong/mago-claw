# Calendar Verification

## 说明

本文只记录基于真实登录态的验证结果，不展开长篇接口推导。

环境：

- 验证日期：2026-03-16
- 环境：`PROD`
- 测试参会人：只使用 `林浔`

已确认测试对象：

- 当前账号日历 `userId=167842507`
- `林浔 -> userID=162526538`

## 创建会议验证

### 用例

- 命令：

```bash
./run.sh create-conference \
  --title "【测试勿动】calendar创建验证 2026-03-18 10:00" \
  --content "AgentTools calendar create-conference 实际创建验证" \
  --begin-time "2026-03-18T10:00:00+08:00" \
  --end-time "2026-03-18T10:30:00+08:00" \
  --participant-names "林浔" \
  --format json
```

### 结果

- `conferenceReserveCheck` 通过
- 真实创建成功
- 返回主事件：
  - `id=5969654`
  - `eventId=5969654`

### 结论

- 创建链路已真实打通
- 参会人解析、预检查、真实保存都可用

## 删除会议验证

### 用例

- 命令：

```bash
./run.sh cancel-conference 5969654 --format json
```

### 结果

- 接口返回成功
- 再次查询时间窗后，你自己和 `林浔` 的日程里都已消失

### 结论

- `conferenceCancel` 当前可用
- 单次非重复会议可直接按：
  - `id`
  - `mainId=false`
  - `sequenceEvent=false`
  - `needNotifyCreator=false`
 进行删除

## 编辑会议加文档验证

### 基线会议

先创建一条测试会议：

```bash
./run.sh create-conference \
  --title "【测试勿动】edit验证初始会议 2026-03-18 14:00" \
  --content "edit workflow baseline" \
  --begin-time "2026-03-18T14:00:00+08:00" \
  --end-time "2026-03-18T14:30:00+08:00" \
  --participant-names "林浔" \
  --format json
```

返回：

- `id=5970029`

### 编辑预检查

```bash
./run.sh preview-edit-conference 5970029 \
  --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" \
  --format json
```

关键结果：

- `mode=preview-edit`
- `targetScheduleId=5970029`
- `reserveCheck` 通过
- 文档解析结果：
  - `shortcutId=846cc90b8ced25a9a196da5fb4ea0a9e`
  - `permissionStatus=READ`
  - `haveCreateTask=true`

### 真实编辑

```bash
./run.sh edit-conference 5970029 \
  --document-urls "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e" \
  --format json
```

关键结果：

- `mode=edit`
- `reserveResult.id=5970029`
- 回查 `conferenceEditQuery` 可见：

```json
{
  "documentModule": [
    {
      "docLink": "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e",
      "haveCreateTask": true,
      "shortcutId": "846cc90b8ced25a9a196da5fb4ea0a9e"
    }
  ]
}
```

### 结论

- 非重复会议修改链路已真实打通
- `conferenceEditQuery -> conferenceReserveCheck -> conferenceReserve` 方案可用
- 当前 CLI 支持在编辑时补充文档

## 删除编辑后的会议验证

### 用例

```bash
./run.sh delete-conference 5970029 --format json
```

### 结果

- 删除接口立即返回成功
- 约 5 秒后再次查询对应时间窗：
  - 你自己的日程中 `5970029` 已消失
  - `林浔` 的日程中也已消失
- 再调 `conferenceEditQuery` 会返回：
  - `当前会议已取消，无法查看`

### 结论

- `delete-conference` 当前作为 `cancel-conference` 别名可用
- 删除后存在短暂最终一致性延迟

## 每周重复会议预检查验证

### 创建预检查

```bash
./run.sh preview-create-conference \
  --title "【测试勿动】weekly preview 2026-04-08" \
  --begin-time "2026-04-08T15:00:00+08:00" \
  --end-time "2026-04-08T15:30:00+08:00" \
  --participant-names "林浔" \
  --day-of-week WEDNESDAY \
  --sequence-end-date 2026-04-29 \
  --format json
```

关键结果：

- `mode=preview-create`
- `reserveCheck` 成功返回
- `payload.sequenceEvent=true`
- `payload.patternType=WEEKLY`
- `payload.dayOfWeek=["WEDNESDAY"]`
- `payload.sequenceStartTime` / `payload.sequenceEndTime` 已正确生成

### 单个重复实例编辑预检查

```bash
./run.sh preview-edit-conference 22262009 --format json
```

关键结果：

- `mode=preview-edit`
- `targetScheduleId=22262009`
- `editSeries=false`
- `payload.id=22262009`
- `payload.sequenceMasterId=5719013`
- `payload.mainId=false`
- `reserveCheck` 成功返回

### 整个重复系列编辑预检查

```bash
./run.sh preview-edit-conference 22262009 --edit-series --format json
```

关键结果：

- `mode=preview-edit`
- `targetScheduleId=22262009`
- `editSeries=true`
- `payload.id=5719013`
- `payload.mainId=true`
- `payload.dayOfWeek=["MONDAY"]`
- `payload.sequenceStartTime` / `payload.sequenceEndTime` 为整条系列范围
- `reserveCheck` 成功返回

### 结论

- CLI 已能对每周重复会议做创建预检查
- CLI 已能对重复会议实例和整个系列做编辑预检查
- 当前仅验证到预检查层；未执行真实重复会议落库写入

## Focus Time 预检查验证

### 创建预检查

```bash
./run.sh preview-create-focus-time \
  --title "写方案" \
  --begin-time "2026-04-09T10:00:00+08:00" \
  --end-time "2026-04-09T11:00:00+08:00" \
  --day-of-week THURSDAY \
  --sequence-end-date 2026-04-30 \
  --format json
```

关键结果：

- `mode=preview-create-focus-time`
- `payload.conferenceType=focus_time`
- `payload.title="Focus time | 写方案"`
- `payload.beginTime` / `payload.endTime` 为字符串时间戳
- `payload.sequenceEvent=true`
- `payload.patternType=WEEKLY`
- `payload.dayOfWeek=["THURSDAY"]`

### 结论

- Focus Time payload 已按前端 bundle 形态生成
- Focus Time 预检查命令可用
- 当前未执行真实 `create-focus-time` / `edit-focus-time` / `delete-focus-time` 写入验证
