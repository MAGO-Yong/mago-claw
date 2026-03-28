# PQL 告警规则脚本输出字段说明

脚本：`scripts/get_alarm_pql_rule.py <rule_id>`

## 顶层字段

| 字段 | 类型 | 含义 |
|------|------|------|
| `id` | int | 规则唯一 ID |
| `name` | string | 规则名称，通常包含业务含义 |
| `status` | bool | `true` = 规则已启用；`false` = 规则已暂停 |
| `bizLine` | string | 业务线，如 `deal`、`creator` |
| `prdLine` | string | 产品线，如 `fulishe`、`community` |
| `app` | string | 关联的服务名（Service Tree 节点），如 `shoppingguide-service-default` |
| `datasource` | string | 数据源名称，如 `vms-fulishe` |
| `datasourceId` | int | 数据源 ID |
| `expression` | string | PromQL 查询表达式 |
| `step` | int | 查询步长（秒） |
| `offset` | int | 时间偏移（秒），用于规避数据延迟 |
| `ruleConfig` | string | 触发规则的人类可读摘要，格式见下 |

## ruleConfig 格式

```
{模式}：{时间段} {count}次中命中{hit}次触发{level}告警，间隔{interval}s
```

| 片段 | 含义 |
|------|------|
| 模式 | `简单模式`（固定阈值）或 `高级模式`（多阈值组合） |
| 时间段 | `HH:MM-HH:MM`，规则在该时间窗口内生效 |
| `count` | 滑动窗口大小（采样点数） |
| `hit` | 需命中（超过阈值）的次数；`0` 表示 ≥1 次即触发 |
| `level` | 告警级别，如 `P0`、`P1`、`P2`、`P3` |
| `interval` | 告警静默间隔（秒） |

示例：`简单模式：00:00-23:59 100次中命中0次触发P2告警，间隔120s`
- 全天生效；最近 100 次采样只要有 ≥1 次超过阈值即触发 P2 告警；告警后静默 120 秒。

## 脚本输出示例

```json
{
  "id": 100,
  "name": "feeds接口rt告警（1m）",
  "status": true,
  "bizLine": "deal",
  "prdLine": "fulishe",
  "app": "shoppingguide-service-default",
  "datasource": "vms-fulishe",
  "datasourceId": 240024,
  "expression": "avg by (source, endpoint) (...)",
  "step": 60,
  "offset": 60,
  "ruleConfig": "简单模式：00:00-23:59 100次中命中0次触发P2告警，间隔120s"
}
```
