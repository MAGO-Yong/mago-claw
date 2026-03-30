# 告警事件查询脚本输出字段说明

脚本：`scripts/query_alarm_events.py [--apps APPS] [--start DATETIME] [--end DATETIME] [--receive-users EMAILS] [--receive-chats CHAT_IDS] [--page N] [--page-size N]`

## 顶层字段

| 字段         | 类型  | 含义                   |
| ------------ | ----- | ---------------------- |
| `total`      | int   | 符合条件的事件总数     |
| `page`       | int   | 当前页码               |
| `total_page` | int   | 总页数                 |
| `page_size`  | int   | 本页条数               |
| `rows`       | array | 本页事件列表，字段见下 |

## rows[] 字段

| 字段                 | 类型          | 含义                                                       |
| -------------------- | ------------- | ---------------------------------------------------------- |
| `id`                 | int           | 事件 ID                                                    |
| `rule_id`            | string        | 规则 ID，可传入 `alarm-rule-detail` skill 查看完整规则配置 |
| `rule_name`          | string        | 规则名称（含告警类型前缀，如 `[PromQL告警][...]`）         |
| `app`                | string        | 关联的 app 名称                                            |
| `level`              | string        | 告警级别：`P0`、`P1`、`P2`、`P3`                           |
| `trigger_time`       | string        | 告警触发时间，ISO 8601 格式（如 `2026-03-26T19:10:15`）    |
| `restore_time`       | string        | 告警恢复时间，未恢复则为 `null`                            |
| `duration`           | string        | 持续时长，人类可读格式（如 `5分11秒`、`2小时3分`）         |
| `reacted`            | bool          | 是否已有人对该事件做出响应操作                             |
| `receive_users`      | array[string] | 接收告警的用户邮箱列表                                     |
| `receive_user_names` | array[string] | 接收告警的用户中文薯名列表（与 `receive_users` 一一对应）  |
| `receive_chats`      | array[string] | 接收告警的群 ID 列表                                       |
| `receive_chat_names` | array[string] | 接收告警的群名称列表（与 `receive_chats` 一一对应）        |

## 脚本输出示例

```json
{
  "total": 16,
  "page": 1,
  "total_page": 2,
  "page_size": 10,
  "rows": [
    {
      "id": 169038014,
      "rule_id": "43269",
      "rule_name": "[PromQL告警][Victoriametrics 5分钟内重启>=2]",
      "app": "victoriametrics",
      "level": "P1",
      "trigger_time": "2026-03-26T19:10:15",
      "restore_time": "2026-03-26T19:15:26",
      "duration": "5分11秒",
      "reacted": false,
      "receive_users": ["zuoci@xiaohongshu.com", "luxiuyuan1@xiaohongshu.com"],
      "receive_user_names": ["左慈(陆中旸)", "傑洛(路修远)"],
      "receive_chats": ["CHAT7551410169108121378"],
      "receive_chat_names": ["reddog - prometheus-server告警群"]
    }
  ]
}
```
