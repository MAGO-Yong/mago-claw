# Calendar CLI Design

## 目标

本文记录 `calendar` 当前命令层的设计边界，重点说明为什么复杂流程固化在 `cli.ts`，而底层 API 必须留在 `service`。

## 分层

### `run.sh`

职责：

- 只做薄封装
- 确保 `build/cli.js` 存在
- 把参数原样转发给 CLI

不负责：

- 业务流程拼装
- 接口调用
- 参数语义补全

### `src/service.ts`

职责：

- 根公共出口
- 对 CLI 暴露共享能力

当前导出来源：

- `service/core.ts`
  - 认证、HTTP、时区、环境归一化
- `service/tools.ts`
  - 查询类 tool 注册与 `runTool`
- `service/create.ts`
  - 创建 / 修改 / 删除相关底层 API 封装

### `src/cli.ts`

职责：

- 对外命令定义
- 高阶工作流编排
- 参数解析
- 调用 `service` 暴露的底层能力

不负责：

- 直接碰 `proxy`
- 直接实现 HTTP 层
- 自己维护一份 API endpoint 常量

## 当前命令集

### 查询类

- `get-personal-settings`
- `list-subscriptions`
- `search-users`
- `query-user-schedules`
- `list-meeting-areas`
- `list-buildings-by-area`
- `query-meeting-rooms`
- `get-entrust-users`
- `get-working-calendar`

### 会议工作流

- `preview-create-conference`
- `create-conference`
- `preview-edit-conference`
- `edit-conference`
- `cancel-conference`
- `delete-conference`

### Focus Time 工作流

- `preview-create-focus-time`
- `create-focus-time`
- `preview-edit-focus-time`
- `edit-focus-time`
- `cancel-focus-time`
- `delete-focus-time`

## 创建会议工作流

### 对外命令

- `preview-create-conference`
- `create-conference`
- 常用控制项：
  - `--notify-creator`
  - `--notify-origin` / `--no-notify-origin`
  - `--use-tencent-meeting`
  - `--can-participants-edit`
  - `--day-of-week`
  - `--sequence-end-date`
  - `--interval-value`

### 固定内部流程

1. 解析 `creatorUserId`
2. 搜参会人
3. 搜会议室
4. 解析文档与读评开关
5. 组装 payload
6. 若显式传重复参数，则补齐每周重复字段
7. 调 `conferenceReserveCheck`
8. 预检查模式直接返回；创建模式再调 `conferenceReserve`

### 设计原则

- Agent 不手动拼搜人 / 搜会议室 / 文档解析
- 预检查和真实创建分成两条高阶命令

## 修改会议工作流

### 对外命令

- `preview-edit-conference <schedule-id>`
- `edit-conference <schedule-id>`
- 常用控制项：
  - `--notify-creator`
  - `--notify-origin` / `--no-notify-origin`
  - `--use-tencent-meeting`
  - `--can-participants-edit`

### 固定内部流程

1. 根据是否传 `--edit-series` 决定回填模式：
   - 单次会议：`mainId=false, sequence=false`
   - 重复实例：`mainId=false, sequence=true`
   - 整个重复系列：优先解析 `sequenceMasterId`，再用 `mainId=true, sequence=true`
2. 对用户显式传入的字段做覆盖
3. 未传入的字段保留原会议值
4. 文档支持：
   - 传新文档时替换为新集合
   - `--clear-documents` 时清空
   - 否则保留原文档
5. 会议室支持：
   - 显式传房间参数时重新解析
   - `--clear-meeting-room` 时清空
   - 否则保留原会议室
6. 若是重复会议，则补齐每周重复字段
7. 调 `conferenceReserveCheck`
8. 预检查模式直接返回；修改模式再调 `conferenceReserve`

### 当前限制

- 周期能力当前只覆盖“每周重复”
- 还没有高阶月度 / 自定义 RRULE 命令面

## Focus Time 工作流

### 对外命令

- `preview-create-focus-time`
- `create-focus-time`
- `preview-edit-focus-time <schedule-id>`
- `edit-focus-time <schedule-id>`
- `delete-focus-time <schedule-id>`

### 设计说明

- Focus Time 走独立接口：`createOrEditFocusTime` / `cancelFocusTime`
- 仍然复用 `conferenceEditQuery` 做回填
- 预检查命令只返回 payload，不调用后端写接口
- 重复 Focus Time 仍按每周重复字段表达，并复用 `--edit-series`
- Focus Time 不暴露参会人 / 会议室 / 文档等复杂输入，保持命令面最小化

## 删除会议工作流

### 对外命令

- `delete-conference <schedule-id>`
- `cancel-conference <schedule-id>`

### 设计说明

- 两个命令当前等价
- `delete-conference` 是更直白的别名
- 当前统一走 `conferenceCancel`
- 当前已确认只支持 `needNotifyCreator`，没有像创建/编辑那样的取消通知细粒度开关
- 重复会议删除由调用方显式控制：
  - 单个实例：`mainId=false, sequenceEvent=true`
  - 整个系列：`mainId=true, sequenceEvent=true`

### 删除后的回查策略

- 不把接口返回 `{}` 直接当成最终证据
- 需要再查一次对应时间窗日程
- 当前实测存在几秒延迟

## 参数设计原则

- 优先业务参数，不强迫 Agent 传底层 ID
- 只在需要兜底时允许直接传 ID

示例：

- 参会人优先 `--participant-names`
- 会议室优先 `--meeting-room-name`
- 文档优先 `--document-urls`
- 周期优先 `--day-of-week` + `--sequence-end-date`

## 当前建议维护规则

- 新增会议工作流相关 API 时，先加到 `service/create.ts`
- 只有形成固定业务流程后，才在 `cli.ts` 暴露高阶命令
- 不要把底层 HTTP / 认证实现搬回 `cli.ts`
