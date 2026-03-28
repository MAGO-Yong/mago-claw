# 服务告警规则脚本输出字段说明

脚本：`scripts/get_alarm_rule.py <rule_id>`

适用于中间件、客户端、RPC 等基于阈值条件的告警规则。

## 顶层字段

| 字段 | 类型 | 含义 |
|------|------|------|
| `id` | int | 规则唯一 ID |
| `name` | string | 规则名称 |
| `status` | bool | `true` = 规则已启用；`false` = 规则已暂停 |
| `level` | string | 默认告警级别，如 `P0`、`P1`、`P2`、`P3` |
| `datasourceType` | string | 数据源类型，见下方枚举 |
| `alarmTarget` | string | 被监控的目标名称，如 `liveanchor-service-default` |
| `alarmTargetType` | string | 监控目标维度：`app`（应用级）、`instance`（实例级） |
| `step` | int | 采集步长（秒） |
| `pending` | int | 触发告警所需的连续命中次数 |
| `recover` | int | 恢复通知所需的连续未命中次数 |
| `silentTime` | int | 告警静默时间（分钟） |
| `conditions` | array | 多指标组合条件，所有条件同时满足才触发告警 |

## datasourceType 枚举

| 值 | 含义 |
|----|------|
| `middleware` | 中间件（MySQL、Redis、MQ 等） |
| `transaction` | 客户端调用（RPC、HTTP 等） |
| `jvm` | JVM 指标（GC、堆内存等） |
| `host` | 主机指标（CPU、内存、磁盘等） |

## conditions[] 字段

每个 condition 表示一个独立的指标及其触发条件，所有 condition 需同时满足。

| 字段 | 类型 | 含义 |
|------|------|------|
| `metric` | string | 指标名称，格式 `{显示名}({metric_key})`，含单位时追加 `({unit})` |
| `dimensions` | array\<string\> | 维度过滤条件，格式 `{维度名}={取值}`；有排除项时追加 `(排除:{值})` |
| `groupBy` | array\<string\> | 聚合维度，按此字段分组后对每个分组单独计算 |
| `conditions` | array\<string\> | 触发条件列表，格式见下 |

## conditions[].conditions[] 格式

```
时间段:{HH:MM}-{HH:MM} | {minute}min内{type}{operator}{threshold}命中{hit}次[；...]
```

| 片段 | 含义 |
|------|------|
| 时间段 | 规则在该时间窗口内生效 |
| `minute` | 取值时间窗口（分钟） |
| `type` | 聚合函数，见下方枚举 |
| `operator` | 比较运算符：`>=`、`>`、`<=`、`<` |
| `threshold` | 告警阈值 |
| `hit` | 滑动窗口内需命中的次数 |

多个子条件用 `；` 分隔，表示 **OR 关系**（任意一个满足即命中）。

## type 聚合函数枚举

| 值 | 含义 |
|----|------|
| `Max` | 窗口内最大值 |
| `Min` | 窗口内最小值 |
| `avg` | 窗口内平均值 |
| `Sum` | 窗口内累加值 |
| `LastWeekAvgOffsetPercent` | 与上周同时段均值的偏差百分比（周环比），正值=上涨，负值=下跌 |
| `YesterdayAvgOffsetPercent` | 与昨日同时段均值的偏差百分比（日环比） |

示例：`时间段:00:00-23:59 | 5min内LastWeekAvgOffsetPercent>=100命中3次`
- 全天生效；过去 5 分钟内指标相比上周同时段均值上涨 ≥100%，且连续满足 3 次，触发告警。

## 脚本输出示例

```json
{
  "id": 120828,
  "name": "【MySQL】平均 RT 周环比波动 >= 100% & QPS >= 50 & RT >= 50ms-liveanchor-service-default",
  "status": true,
  "level": "P2",
  "datasourceType": "middleware",
  "alarmTarget": "liveanchor-service-default",
  "alarmTargetType": "app",
  "step": 60,
  "pending": 1,
  "recover": 3,
  "silentTime": 10,
  "conditions": [
    {
      "metric": "MySQL 请求 QPS(mysql.request.qps)",
      "dimensions": ["ip=All", "method=All(排除:LiveReservationMapper.selectByIds)"],
      "groupBy": ["method"],
      "conditions": ["时间段:00:00-23:59 | 5min内LastWeekAvgOffsetPercent>=100命中3次；5min内LastWeekAvgOffsetPercent<=-100命中3次"]
    }
  ]
}
```
