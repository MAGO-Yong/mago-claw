# Calendar API Analysis

## 范围

本文只记录日历“会议创建 / 修改 / 删除”相关接口事实，不掺杂 CLI 设计和验证流水。

环境基线：

- 页面入口：`https://city.xiaohongshu.com/calendar/v2/creation`
- 环境：`PROD`
- 当前前端 bundle：`hi-calendar v0.0.45`
- 测试参会人限制：只使用 `林浔`

## 主链路接口

### 创建 / 保存

- `POST /conferencemanager/conference/conferenceReserveController/conferenceReserve`
- `POST /conferencemanager/conference/conferenceReserveController/conferenceReserveCheck`

关键结论：

- 创建和编辑最终都走 `conferenceReserve`
- `conferenceReserveCheck` 是保存前的固定预检查
- 不带会议室时，`costQuote` / `remainQuote` 可能是 `null`
- 带会议室时，`resultStateList` 可能出现 `room_less_man`

### 编辑回填

- `POST /conferencemanager/conference/conferenceReserveController/conferenceEditQuery`

关键结论：

- 编辑会议前，前端先用 `conferenceEditQuery` 回填现有详情
- 非重复会议回填里可直接拿到：
  - `id`
  - `title`
  - `content`
  - `beginTime`
  - `endTime`
  - `creatorNo`
  - `participantUserList`
  - `meetingRoomVos`
  - `documentModule`
  - `canParticipantsEdit`
  - `tencentMeeting`
  - `sequenceEvent`
- 当前实测的非重复会议返回里：
  - `sequenceEvent=false`
  - `mainId=null`
  - `meetingRoomVos=null`
  - `documentModule=[]` 或真实文档数组
- 重复会议实例回填可按：

```json
{
  "id": "<instance-id>",
  "mainId": false,
  "sequence": true
}
```

- 关键返回特征：
  - `id=<instance-id>`
  - `mainId=<sequenceMasterId>`
  - `sequenceEvent=false`
  - `recurrenceTime` 有值
  - `patternType` / `dayOfWeek` / `intervalValue` / `sequenceStartTime` / `sequenceEndTime` 可能为空
- 重复会议主系列回填可按：

```json
{
  "id": "<sequenceMasterId>",
  "mainId": true,
  "sequence": true
}
```

- 关键返回特征：
  - `id=<sequenceMasterId>`
  - `mainId=null`
  - `sequenceEvent=true`
  - `patternType=END_DATE`
  - `dayOfWeek=["MONDAY"]` 等
  - `intervalValue=1`
  - `sequenceStartTime` / `sequenceEndTime` 为整条系列范围

### 删除 / 取消

- `POST /conferencemanager/conference/conferenceReserveController/conferenceCancel`

关键结论：

- 当前 CLI 的删除本质就是取消会议
- 前端删除会议时走 `conferenceCancel`
- 当前已确认可工作的最小请求体：

```json
{
  "id": "5970029",
  "mainId": false,
  "sequenceEvent": false,
  "needNotifyCreator": false
}
```

- 接口成功时可能返回空对象 `{}`
- 当前已确认的通知控制只有 `needNotifyCreator`
- 暂未发现 `needNotifyOrigin` 等更细粒度取消通知参数的前端用法或实测证据
- 删除后查询结果存在短暂延迟，不能假设同步消失

### Focus Time

- `POST /conferencemanager/conference/focusTimeController/createOrEditFocusTime`
- `POST /conferencemanager/conference/focusTimeController/cancelFocusTime`

关键结论：

- 前端枚举里存在 `scheduleType=focus_time`
- Focus Time 不走 `conferenceReserveCheck`
- 保存时走独立接口 `createOrEditFocusTime`
- 删除时走独立接口 `cancelFocusTime`
- Focus Time payload 与会议 payload 大体同构，但有两个关键差异：
  - `conferenceType` 固定为 `focus_time`
  - `beginTime` / `endTime` / `sequenceStartTime` / `sequenceEndTime` 使用字符串时间戳
- 当前 CLI 已接入上述 payload 形态，并提供 preview 命令；尚未执行真实落库写入验证

## 辅助接口

### 创建人 / 参会人

- `GET /conferencemanager/conference/userConfig/userStaticConfig/get`
- `POST /conferencemanager/conference/conferenceReserveController/searchParticipantByName`

关键结论：

- `createUserId` 不能直接用 SSO ID，必须用 `userStaticConfig.get` 返回的日历 `userId`
- 已确认当前账号日历 `userId` 为 `167842507`
- `林浔` 当前可稳定解析到：
  - `redName=林浔`
  - `userID=162526538`

`searchParticipantByName` 请求模型：

```json
{
  "keyword": "林浔",
  "beginTime": "2026-03-18T10:00:00+08:00",
  "endTime": "2026-03-18T10:30:00+08:00",
  "creatorId": "167842507",
  "filterUserIds": "",
  "searchWithTimeStatus": true
}
```

### 文档关联 / 读评

- `GET /conferencemanager/docgateway/api/document/queryUrlTitleInfoByUrl`
- `POST /conferencemanager/conference/scheduleManagerController/queryCurrUserDocPermission`
- `POST /conferencemanager/conference/conferenceReserveController/queryTaskCountForDoc`
- `GET /conferencemanager/conference/scheduleManagerController/queryDocPermissionApplyStatus`
- `POST /conferencemanager/conference/scheduleManagerController/queryParticipantDocPermission`

关键结论：

- `documentModule` 负责挂文档与 `haveCreateTask`
- `docAutoEmpowerList` 负责自动授权文档
- 当前 CLI 的 `haveCreateTask` 判定边界：
  - 只对 `DOC` 开启
  - 过去时间关闭
  - 仅组织者一人关闭
  - 超过 200 人关闭
  - 文档已删除关闭
  - 当前用户无读权限关闭
  - 任务数达到上限关闭

文档字段形态：

```json
{
  "documentModule": [
    {
      "docLink": "https://docs.xiaohongshu.com/doc/846cc90b8ced25a9a196da5fb4ea0a9e",
      "haveCreateTask": true
    }
  ],
  "docAutoEmpowerList": []
}
```

### 会议室 / 区域

- `GET /conferencemanager/conference/meetingRoomManagerController/areaListQuery`
- `GET /conferencemanager/conference/meetingRoomManagerController/buildingListByAreaIdQuery`
- `POST /conferencemanager/conference/conferenceReserveController/meetingRoomReserveQuery`
- `POST /conferencemanager/conference/conferenceReserveController/searchMeetingRoomByAreaAndName`
- `POST /conferencemanager/conference/conferenceReserveController/meetingRoomReservePageQuery`
- `POST /conferencemanager/conference/conferenceReserveController/meetingRoomScheduleQuery`

关键结论：

- 当前 CLI 高阶命令主要复用现有 `query_meeting_rooms`
- `conferenceReserveCheck` 会对带会议室的 payload 返回额度信息

## `conferenceReserve` 请求模型

当前已确认的核心字段：

```json
{
  "title": "示例会议",
  "content": "",
  "createUserId": "167842507",
  "beginTime": 1773813600000,
  "endTime": 1773815400000,
  "userTimeZone": "Asia/Shanghai",
  "participantList": [
    "167842507",
    "162526538"
  ],
  "isTencentMeeting": true,
  "meetingRoomVos": [],
  "attachmentVoList": [],
  "documentModule": [],
  "docAutoEmpowerList": [],
  "needNotifyCreator": true,
  "needNotifyOrigin": true,
  "isSkype": false,
  "isInvite": false,
  "isMobile": false,
  "isWechat": false,
  "pathName": "https://city.xiaohongshu.com/calendar/v2/creation",
  "canParticipantsEdit": false,
  "can_participants_edit": false,
  "sequenceEvent": false
}
```

每周重复会议在同一 payload 上额外追加：

- `sequenceEvent=true`
- `patternType="WEEKLY"`
- `dayOfWeek=["MONDAY"]`
- `intervalValue=1`
- `sequenceStartTime=<系列开始日 00:00:00.000>`
- `sequenceEndTime=<系列结束日 23:59:59.999>`

编辑时额外追加：

- `id`
- `mainId`（布尔，编辑整个系列时为 `true`）
- `sequenceMasterId`（编辑单个重复实例时使用）

保守结论：

- 非重复会议编辑只需要追加 `id`
- 每周重复会议编辑需要结合：
  - `sequenceEvent`
  - `mainId`
  - `sequenceMasterId`
  - `patternType`
  - `dayOfWeek`
  - `intervalValue`
  - `sequenceStartTime`
  - `sequenceEndTime`

## 当前已确认限制

- 删除能力当前等价于取消会议
- 取消会议当前只暴露 `needNotifyCreator`，通知粒度有限
- 高阶周期能力当前只覆盖“每周重复”，未覆盖月度 / 自定义 RRULE
- Focus Time 已确认接口名、枚举值与 payload 结构，但尚未做真实 create / cancel 落库验证
