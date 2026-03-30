---
name: alarm-event-query
description:
  查询 Xray 告警事件记录。当用户需要查询某 app
  在指定时间段内的历史告警事件、告警通知记录、触发/恢复时间等信息时触发。
version: 1.0.0
metadata:
  category: alarm
  subcategory: event
  platform: xray
  trigger: app/time_range/receive_user/receive_chat
  input: [apps, start, end, receive_users, receive_chats, page, page_size]
  output: [event_list]
  impl: python-script
---

# 告警事件查询

## 工作流程

### Step 1：确定过滤条件

| 用户输入                 | 对应参数          | 示例                                                               |
| ------------------------ | ----------------- | ------------------------------------------------------------------ |
| app 名称（一个或多个）   | `--apps`          | `--apps victoriametrics` 或 `--apps "victoriametrics,xrayaiagent"` |
| 时间范围起点             | `--start`         | `--start "2026-03-26 09:00:00"`                                    |
| 时间范围终点             | `--end`           | `--end "2026-03-26 21:00:00"`                                      |
| 接收人邮箱（一个或多个） | `--receive-users` | `--receive-users "foo@xiaohongshu.com"`                            |
| 接收群 ID（一个或多个）  | `--receive-chats` | `--receive-chats "CHAT123,CHAT456"`                                |
| 页码                     | `--page`          | `--page 2`（默认 1）                                               |
| 每页条数                 | `--page-size`     | `--page-size 50`（默认 20）                                        |

所有参数均为可选，不传则不限制该维度。

### Step 2：执行脚本

```bash
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps <apps> \
  --start "<start_datetime>" \
  --end "<end_datetime>" \
  --receive-users "<emails>" \
  --receive-chats "<chat_ids>" \
  --page <page> \
  --page-size <page_size>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

### Step 3：输出结果

将脚本 JSON 输出返回给用户，按需聚合或高亮关键字段（如
`rule_name`、`level`、`duration`、`reacted`）。

如需查看某条规则的完整配置（PromQL 表达式、触发条件等），使用 `alarm-rule-detail` skill，传入对应
`rule_id`。

## 错误处理

| 错误情况          | 处理方式                         |
| ----------------- | -------------------------------- |
| 脚本退出码非 0    | 将 stderr 内容返回用户           |
| API `code` 非 200 | 脚本已处理，直接透传错误信息     |
| 结果 `total` 为 0 | 告知用户该条件下暂无告警事件记录 |
| 网络不通          | 提示用户确认是否在内网环境       |

## 参考文档

- **脚本输出字段说明**：[references/event-api.md](references/event-api.md)
- **规则详情查询**：使用 `alarm-rule-detail` skill，传入 `rule_id`
