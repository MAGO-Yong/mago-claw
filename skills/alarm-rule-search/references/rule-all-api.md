# 服务告警规则搜索脚本输出字段说明

脚本：`scripts/search_alarm_rules.py --app <name> [--page N] [--size N]`

适用于中间件、客户端、RPC、Cat 等基于阈值条件的告警规则。

## 顶层字段

| 字段         | 类型  | 含义                   |
| ------------ | ----- | ---------------------- |
| `total`      | int   | 符合条件的规则总数     |
| `page`       | int   | 当前页码               |
| `total_page` | int   | 总页数                 |
| `page_size`  | int   | 本页条数               |
| `rows`       | array | 本页规则列表，字段见下 |

## rows[] 字段

| 字段          | 类型   | 含义                                                                           |
| ------------- | ------ | ------------------------------------------------------------------------------ |
| `ruleId`      | string | 规则唯一标识；模板规则格式为 `{templateId}_{bindId}`，自定义规则为纯数字字符串 |
| `type`        | string | 数据源类型，见下方枚举                                                         |
| `name`        | string | 规则名称                                                                       |
| `alarmTarget` | string | 被监控目标名称（app/service 名，或 bizLine 名）                                |
| `level`       | string | 告警级别：`P0`、`P1`、`P2`、`P3`                                               |
| `status`      | string | `启用` / `停用`                                                                |
| `modifyTime`  | string | 最后修改时间，格式 `YYYY-MM-DD HH:MM:SS`                                       |
| `modifier`    | string | 最后修改人                                                                     |

## type 枚举

| 值            | 含义                          |
| ------------- | ----------------------------- |
| `middleware`  | 中间件（MySQL、Redis、MQ 等） |
| `transaction` | 客户端调用（RPC、HTTP 等）    |
| `problem`     | Cat Problem 类指标            |
| `jvm`         | JVM 指标（GC、堆内存等）      |
| `host`        | 主机指标（CPU、内存、磁盘等） |

## 脚本输出示例

```json
{
  "total": 6,
  "page": 1,
  "total_page": 2,
  "page_size": 5,
  "rows": [
    {
      "ruleId": "197570",
      "type": "problem",
      "name": "服务诊断 problem 告警",
      "alarmTarget": "xrayaiagent-service-diagnosis",
      "level": "P2",
      "status": "启用",
      "modifyTime": "2026-02-12 16:20:11",
      "modifier": "傑洛(路修远)"
    },
    {
      "ruleId": "1_15",
      "type": "problem",
      "name": "[模版]Error异常兜底告警",
      "alarmTarget": "obs",
      "level": "P3",
      "status": "启用",
      "modifyTime": "2026-03-23 16:33:02",
      "modifier": "荀诩(韩奇祺)"
    }
  ]
}
```
