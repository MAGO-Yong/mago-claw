---
name: alarm-event-detail
description:
  查询 Xray 告警事件详情。当用户提供事件 ID 需要查看完整的事件信息、操作记录、告警详情时触发。
metadata:
  category: alarm
  subcategory: event
  platform: xray
  trigger: event_id
  input: [event_id]
  output: [basic, operations, alarm_details]
  impl: python-script
---

# 告警事件详情查询

## 用途

根据事件 ID 查询单条告警事件的完整信息，包括：

- **基本信息**：产品线、业务线、app、告警名称、级别、触发/恢复时间等
- **操作记录**：事件平台的操作历史（如认领、处理等）
- **告警详情**：聚合展示受影响的机器、监控项、触发规则、当前值分布等
- **快捷链接**：规则配置、指标详情、变更事件等链接

## 工作流程

### Step 1：获取事件 ID

事件 ID 可通过以下方式获得：

- 从 `alarm-event-query` skill 的输出中获取
- 从告警通知消息中获取
- 从 Xray 平台事件列表中获取

### Step 2：执行脚本

```bash
python3 {SKILL_DIR}/scripts/get_alarm_event_detail.py <event_id>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

**示例：**

```bash
python3 /path/to/skills/alarm-event-detail/scripts/get_alarm_event_detail.py 171238413
```

### Step 3：输出结构

# 偾警事件详情查询

根据事件 ID 获取告警事件的完整信息，包括基本字段、操作记录、告警详情（通过 `--show-link`
控制是否显示快捷链接)。

---

示例 %(prog)s 171238413 %(prog)s 171238413 --show-link

````
```json
{
  "source": "xray",
  "prdline": "ep",
  "bizline": "efficiency",
  "app": "redimbiztask",
  "name": "[阈值告警][Middleware][【RedIM模板】Redis命中率下跌-redimbiztask-service-default]",
  "rule_id": "98338",
  "level": "P3",
  "trigger_time": "2026-03-31T10:05:36",
  "operate_time": null,
  "restore_time": null
}
````

#### 2. operations - 操作记录

```json
[
  {
    "operator": "事件平台",
    "user_name": "",
    "trigger_time": "2026-03-31T11:59:30",
    "create_time": "2026-03-31T11:59:30",
    "links": {
      "规则配置": "http://xray.devops.xiaohongshu.com/alarm/rule/98338/...",
      "指标详情": "http://xray.devops.xiaohongshu.com/d/metric/detail/...",
      "变更事件": "http://xray.devops.xiaohongshu.com/event/search?..."
    }
  }
]
```

#### 3. alarm_details - 告警详情（聚合）

```json
{
  "name": "【RedIM模板】Redis命中率下跌-redimbiztask-service-default",
  "metric": "infra_redis_hit_total",
  "trigger_rules": ["[过去3个点内所有点的值<=0.5]"],
  "affected_machines": [
    "redimbiztask-service-default-22js2",
    "redimbiztask-service-default-9v2mk",
    "redimbiztask-service-default-bv27z"
  ],
  "machine_count": 15,
  "first_trigger_time": "2026-03-31T10:05:36",
  "last_restore_time": "2026-03-31T11:59:30",
  "sample_values": [
    {
      "machine": "redimbiztask-service-default-tnjtm",
      "value": "[0.333,0,0]",
      "trigger_time": "2026-03-31T11:56:09",
      "restore_time": "2026-03-31T11:59:29"
    }
  ],
  "total_samples": 42,
  "links": {
    "规则配置": "http://...",
    "指标详情": "http://...",
    "变更事件": "http://..."
  }
}
```

### Step 4：后续操作

根据查询结果，可以：

- 查看**规则配置**：使用 `alarm-rule-detail` skill，传入 `rule_id`
- 查看**指标详情**：点击 `links.指标详情` 链接
- 查看**变更事件**：点击 `links.变更事件` 链接
- 分析**受影响机器**：根据 `affected_machines` 列表进行排查

## 错误处理

| 错误情况          | 处理方式                     |
| ----------------- | ---------------------------- |
| 脚本退出码非 0    | 将 stderr 内容返回用户       |
| API `code` 非 200 | 脚本已处理，直接透传错误信息 |
| 事件 ID 不存在    | API 返回错误，提示用户确认   |
| 网络不通          | 提示用户确认是否在内网环境   |

## 与其他 Skill 的协作

```
alarm-event-query（查询事件列表）
  └── 获取 event_id
      └── alarm-event-detail（本 skill，查看详情）
          ├── 查看规则详情 ──→ alarm-rule-detail
          └── 查看指标数据 ──→ metrics-query-by-template
```

## 输出字段说明

### basic 字段

| 字段         | 说明                  |
| ------------ | --------------------- |
| source       | 事件来源（xray）      |
| prdline      | 产品线                |
| bizline      | 业务线                |
| app          | 应用名称              |
| name         | 告警名称              |
| rule_id      | 告警规则 ID           |
| level        | 告警级别（P1/P2/P3）  |
| trigger_time | 首次触发时间          |
| operate_time | 操作时间（认领/处理） |
| restore_time | 恢复时间              |

### alarm_details 字段

| 字段               | 说明                           |
| ------------------ | ------------------------------ |
| name               | 告警模板名称                   |
| metric             | 监控项名称                     |
| trigger_rules      | 触发规则列表                   |
| affected_machines  | 受影响的机器列表               |
| machine_count      | 受影响机器数量                 |
| first_trigger_time | 首次触发时间                   |
| last_restore_time  | 最后恢复时间                   |
| sample_values      | 采样值示例（前 10 条）         |
| total_samples      | 总采样数                       |
| links              | 快捷链接（规则配置/指标/变更） |
