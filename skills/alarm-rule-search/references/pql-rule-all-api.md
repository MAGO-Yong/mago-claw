# PQL 告警规则搜索脚本输出字段说明

脚本：`scripts/search_alarm_pql_rules.py --app <name> [--page N] [--size N]`

## 顶层字段

| 字段         | 类型  | 含义                   |
| ------------ | ----- | ---------------------- |
| `total`      | int   | 符合条件的规则总数     |
| `page`       | int   | 当前页码               |
| `total_page` | int   | 总页数                 |
| `page_size`  | int   | 本页条数               |
| `rows`       | array | 本页规则列表，字段见下 |

## rows[] 字段

| 字段          | 类型   | 含义                                                   |
| ------------- | ------ | ------------------------------------------------------ |
| `ruleId`      | int    | 规则 ID，可传入 `alarm-rule-detail` skill 查看完整配置 |
| `type`        | string | 固定为 `pql`                                           |
| `name`        | string | 规则名称                                               |
| `alarmTarget` | string | 关联的 app/service 名称                                |
| `level`       | string | 告警级别：`P0`、`P1`、`P2`、`P3`                       |
| `status`      | string | `启用` / `停用`                                        |
| `modifyTime`  | string | 最后修改时间，格式 `YYYY-MM-DD HH:MM:SS`               |
| `modifier`    | string | 最后修改人                                             |

## 脚本输出示例

```json
{
  "total": 5,
  "page": 1,
  "total_page": 2,
  "page_size": 3,
  "rows": [
    {
      "ruleId": 461201,
      "type": "pql",
      "name": "大模型推理成功率低",
      "alarmTarget": "xrayaiagent-service-diagnosis",
      "level": "P1",
      "status": "启用",
      "modifyTime": "2026-02-26 20:00:59",
      "modifier": "傑洛(路修远)"
    }
  ]
}
```
