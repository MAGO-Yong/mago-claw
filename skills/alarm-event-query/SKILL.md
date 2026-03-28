---
name: alarm-event-query
description: 查询 Xray 告警事件记录。当用户需要查询某告警规则的历史触发事件、告警通知记录时触发。
version: 1.0.0
metadata:
  category: alarm
  subcategory: event
  platform: xray
  trigger: rule_id/time_range
  input: [rule_id, st, et]
  output: [event_list]
  impl: http-api
---

# 告警事件查询

> TODO: 补充具体工作流程
