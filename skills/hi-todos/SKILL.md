---
name: hi-todos
version: 1.0.0
description: 'hi 官方待办 Skill。支持查询待办列表、待办详情；支持为用户创建、关闭、完成待办事项'
metadata: { 'openclaw': { 'requires': { 'bins': ["pnpm"] } } }
---

# hi-todos

创建和管理待办任务。

## 错误处理

- **可重试** 最多 3 次（包含首次）

## 发现命令

**在调用任何命令前，先用 `--help` 查询可用命令和参数，不要猜测 flag 名称。**

```bash
# 列出所有 todos 子命令
pnpm dlx @xhs/hi-workspace-cli@0.2.5 todos --help

# 查看具体命令的参数（含输出格式）
pnpm dlx @xhs/hi-workspace-cli@0.2.5 todos:<method> --help
```

以下是 `--help` 中没有的约束和指引。

## 时间参数

- 当前时间必须以**系统时间**为唯一依据，禁止自行假设当前日期、当前时间、当前时区。
- 所有时间参数均使用 **ISO 8601 格式**
- 所有相对时间表达（今天、明天、昨天、本周、当前、最近）都必须基于当前时间

## 操作约束

### create

- **幂等**：每次新建任务须单独调用 `todos:generate-operate-code` 获取新的 `operateCode`，不同任务之间不得共用。同一任务因网络失败重试时复用同一 `operateCode`，最多重试 3 次
- **参与人确认**：通过 `search:employee` 查找参与人时，若存在多个同名人员，须向用户确认具体是哪一位

### close-task / complete-task

- 操作不可逆，执行前须向用户确认任务 ID 或任务标题，避免误操作
