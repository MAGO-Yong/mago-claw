# 告警事件详情脚本输出字段说明

脚本：`scripts/get_alarm_event_detail.py <event_id>`

## 顶层结构

输出包含三个主要部分：

| 字段            | 类型  | 含义           |
| --------------- | ----- | -------------- |
| `basic`         | dict  | 基本信息       |
| `operations`    | array | 操作记录列表   |
| `alarm_details` | dict  | 聚合的告警详情 |

---

## basic 字段

事件的基本元数据。

| 字段           | 类型           | 含义                                     |
| -------------- | -------------- | ---------------------------------------- |
| `source`       | string         | 事件来源，如 `xray`                      |
| `prdline`      | string         | 产品线                                   |
| `bizline`      | string         | 业务线                                   |
| `app`          | string         | 应用名称                                 |
| `name`         | string         | 告警名称（含类型前缀）                   |
| `rule_id`      | string         | 规则 ID，可用于查询规则详情              |
| `level`        | string \| null | 告警级别：`P0`、`P1`、`P2`、`P3`         |
| `trigger_time` | string         | 首次触发时间，ISO 8601 格式              |
| `operate_time` | string \| null | 操作时间（认领/处理等），未操作为 `null` |
| `restore_time` | string \| null | 恢复时间，未恢复为 `null`                |

---

## operations[] 字段

事件平台的操作记录历史。

| 字段           | 类型           | 含义                          |
| -------------- | -------------- | ----------------------------- |
| `operator`     | string         | 操作者，如 `事件平台`、用户名 |
| `user_name`    | string \| null | 用户中文名（用户操作时）      |
| `trigger_time` | string         | 操作触发时间                  |
| `create_time`  | string         | 记录创建时间                  |
| `links`        | dict           | 快捷链接，见下方说明          |

### operations[].links 字段

| 字段       | 类型   | 含义         |
| ---------- | ------ | ------------ |
| `规则配置` | string | 规则编辑页面 |
| `指标详情` | string | 指标监控页面 |
| `变更事件` | string | 变更事件查询 |

---

## alarm_details 字段

聚合展示告警详情，包括受影响的机器、监控项、触发规则等。

| 字段                 | 类型           | 含义                              |
| -------------------- | -------------- | --------------------------------- |
| `name`               | string         | 告警模板名称                      |
| `metric`             | string         | 监控项名称                        |
| `trigger_rules`      | array<string>  | 触发规则列表                      |
| `affected_machines`  | array<string>  | 受影响的机器列表（已排序）        |
| `machine_count`      | int            | 受影响机器数量                    |
| `first_trigger_time` | string         | 首次触发时间                      |
| `last_restore_time`  | string \| null | 最后恢复时间，未恢复为 `null`     |
| `sample_values`      | array          | 采样值示例（最多 10 条）          |
| `total_samples`      | int            | 总采样记录数                      |
| `links`              | dict           | 快捷链接（同 operations[].links） |

### alarm_details.sample_values[] 字段

| 字段           | 类型           | 含义                      |
| -------------- | -------------- | ------------------------- |
| `machine`      | string         | 机器名称                  |
| `value`        | string         | 当前值（JSON 数组字符串） |
| `trigger_time` | string         | 该采样触发时间            |
| `restore_time` | string \| null | 该采样恢复时间            |

---

## 脚本输出示例

```json
{
  "basic": {
    "source": "xray",
    "prdline": "ep",
    "bizline": "efficiency",
    "app": "redimbiztask",
    "name": "[阈值告警][Middleware][【RedIM模板】Redis命中率下跌-redimbiztask-service-default]",
    "rule_id": "98338",
    "level": "P3",
    "trigger_time": "2026-03-31T10:05:36",
    "operate_time": null,
    "restore_time": "2026-03-31T11:59:29"
  },
  "operations": [
    {
      "operator": "事件平台",
      "user_name": "",
      "trigger_time": "2026-03-31T11:59:30",
      "create_time": "2026-03-31T11:59:30",
      "links": {
        "规则配置": "http://xray.devops.xiaohongshu.com/alarm/rule/98338/update?...",
        "指标详情": "http://xray.devops.xiaohongshu.com/d/metric/detail/...",
        "变更事件": "http://xray.devops.xiaohongshu.com/event/search?..."
      }
    }
  ],
  "alarm_details": {
    "name": "【RedIM模板】Redis命中率下跌-redimbiztask-service-default",
    "metric": "infra_redis_hit_total",
    "trigger_rules": ["[过去3个点内所有点的值<=0.5]"],
    "affected_machines": [
      "redimbiztask-service-default-22js2",
      "redimbiztask-service-default-9v2mk",
      "redimbiztask-service-default-bv27z"
    ],
    "machine_count": 20,
    "first_trigger_time": "2026-03-31T10:05:36",
    "last_restore_time": "2026-03-31T11:59:30",
    "sample_values": [
      {
        "machine": "redimbiztask-service-default-vsqkr",
        "value": "[0.333,0,0]",
        "trigger_time": "2026-03-31T11:56:09",
        "restore_time": "2026-03-31T11:59:29"
      }
    ],
    "total_samples": 210,
    "links": {
      "规则配置": "http://xray.devops.xiaohongshu.com/alarm/rule/98338/update?...",
      "指标详情": "http://xray.devops.xiaohongshu.com/d/metric/detail/...",
      "变更事件": "http://xray.devops.xiaohongshu.com/event/search?..."
    }
  }
}
```

---

## 使用 --show-link 选项

默认情况下，输出中不包含 `links` 字段。如需查看快捷链接，使用 `--show-link` 参数：

```bash
python3 scripts/get_alarm_event_detail.py 171238413 --show-link
```

这将使 `operations[].links` 和 `alarm_details.links` 字段被包含在输出中。
