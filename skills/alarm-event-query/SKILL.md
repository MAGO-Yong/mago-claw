---
name: alarm-event-query
description:
  查询 Xray 告警事件记录。当用户需要查询某 app
  在指定时间段内的历史告警事件、告警通知记录、触发/恢复时间等信息时触发。
metadata:
  category: alarm
  subcategory: event
  platform: xray
  trigger: app/time_range/receive_user/receive_chat/rule_id
  input: [apps, start, end, receive_users, receive_chats, rule_id, page, page_size]
  output: [event_list]
  impl: python-script
---

# 告警事件查询

## 工作流程

### Step 1：确定过滤条件

| 用户输入                  | 对应参数          | 示例                                                                                                          |
| ------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------- |
| 产品线/业务线/app/service | `--apps`          | `--apps base` 或 `--apps base.obs` 或 `--apps base.obs.xrayaiagent` 或 `--apps xrayaiagent-service-diagnosis` |
| 时间范围起点              | `--start`         | `--start "2026-03-26 09:00:00"`                                                                               |
| 时间范围终点              | `--end`           | `--end "2026-03-26 21:00:00"`                                                                                 |
| 接收人邮箱（一个或多个）  | `--receive-users` | `--receive-users "foo@xiaohongshu.com"`                                                                       |
| 接收群 ID（一个或多个）   | `--receive-chats` | `--receive-chats "CHAT123,CHAT456"`                                                                           |
| 规则 ID（一个或多个）     | `--rule-id`       | `--rule-id "183910,183911"`                                                                                   |
| 页码                      | `--page`          | `--page 2`（默认 1）                                                                                          |
| 每页条数                  | `--page-size`     | `--page-size 50`（默认 20）                                                                                   |

### 关于 `--apps` 参数

`--apps` 参数支持三种粒度，同一次调用只能使用同一粒度，多个值用英文逗号分隔：

| 格式                        | 示例                            | HTTP 参数                               |
| --------------------------- | ------------------------------- | --------------------------------------- |
| `<prdLine>`                 | `base`                          | `pdls=base&bizs=&apps=`                 |
| `<prdLine>.<bizLine>`       | `base.obs`                      | `pdls=base&bizs=obs&apps=`              |
| `<prdLine>.<bizLine>.<app>` | `base.obs.xrayaiagent`          | `pdls=&bizs=&apps=base.obs.xrayaiagent` |
| service 名称（含连字符）    | `xrayaiagent-service-diagnosis` | 自动解析为完整路径后同上                |

**完整示例：**

```bash
# 按产品线查询
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps base \
  --start "2026-03-26 09:00:00" \
  --end "2026-03-26 21:00:00"

# 按业务线查询
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps base.obs \
  --start "2026-03-26 09:00:00" \
  --end "2026-03-26 21:00:00"

# 按完整 app 路径查询（直接查询，最快）
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps base.obs.xrayaiagent \
  --start "2026-03-26 09:00:00" \
  --end "2026-03-26 21:00:00"

# 使用 service 名称（自动解析）
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps xrayaiagent-service-diagnosis \
  --start "2026-03-26 09:00:00" \
  --end "2026-03-26 21:00:00"
```

### Step 2：执行脚本

```bash
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --apps <apps> \
  --start "<start_datetime>" \
  --end "<end_datetime>" \
  --receive-users "<emails>" \
  --receive-chats "<chat_ids>" \
  --rule-id "<rule_id>" \
  --page <page> \
  --page-size <page_size>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

**按规则 ID 查询示例：**

```bash
# 查询指定规则的告警事件
python3 {SKILL_DIR}/scripts/query_alarm_events.py \
  --rule-id "183910,183911" \
  --start "2026-03-26 09:00:00" \
  --end "2026-03-26 21:00:00"
```

### Step 3：输出结果

将脚本 JSON 输出返回给用户，按需聚合或高亮关键字段（如
`rule_name`、`level`、`duration`、`reacted`）。

如需查看某条规则的完整配置（PromQL 表达式、触发条件等），使用 `alarm-rule-detail` skill，传入对应
`rule_id`。

## 错误处理

| 错误情况             | 处理方式                                               |
| -------------------- | ------------------------------------------------------ |
| 脚本退出码非 0       | 将 stderr 内容返回用户                                 |
| API `code` 非 200    | 脚本已处理，直接透传错误信息                           |
| 结果 `total` 为 0    | 告知用户该条件下暂无告警事件记录                       |
| 网络不通             | 提示用户确认是否在内网环境                             |
| Service 匹配多个节点 | 返回所有匹配节点的 full_path，提示用户指定更精确的名称 |

## 参考文档

- **脚本输出字段说明**：[references/event-api.md](references/event-api.md)
- **规则详情查询**：使用 `alarm-rule-detail` skill，传入 `rule_id`
