---
name: alarm-rule-search
description:
  按 app/service 名称、产品线或业务线搜索 Xray 告警规则列表，支持 PQL
  告警和服务告警两类。当用户需要查询某个服务/产品线/业务线下有哪些告警规则时触发。
version: 1.0.0
metadata:
  category: alarm
  subcategory: rule
  platform: xray
  trigger: service_name/prdLine/bizLine
  input: [app, service, prdLine, bizLine]
  output: [rule_list]
  impl: python-script
---

# 告警规则搜索

## 两类规则说明

| 类型             | 适用场景                                                     | 脚本                                |
| ---------------- | ------------------------------------------------------------ | ----------------------------------- |
| PQL 告警（默认） | 基于 PromQL 表达式的指标告警，如自定义监控、SLO 告警         | `scripts/search_alarm_pql_rules.py` |
| 服务告警         | 中间件/客户端/RPC 等阈值类告警（MySQL、Cat、transaction 等） | `scripts/search_alarm_rules.py`     |

**默认同时执行两个脚本。** 若用户明确说明只查某一类，则只执行对应脚本。

## 服务树层级说明

xhs 服务树层级：`prdLine（产品线）> bizLine（业务线）> app > service`

`app` 与 `service` 可混用：传入具体 service 名称（如 `xrayaiagent-service-diagnosis`）时使用 `--app`
参数。

## 工作流程

### Step 1：确定过滤维度

| 用户输入            | 使用参数    | 示例                                  |
| ------------------- | ----------- | ------------------------------------- |
| app 或 service 名称 | `--app`     | `--app xrayaiagent-service-diagnosis` |
| 产品线名称          | `--prdLine` | `--prdLine fulishe`                   |
| 业务线名称          | `--bizLine` | `--bizLine usergrowth`                |

### Step 2：执行脚本获取规则列表

**PQL 告警：**

```bash
python3 {SKILL_DIR}/scripts/search_alarm_pql_rules.py --app <app_or_service>
```

**服务告警：**

```bash
python3 {SKILL_DIR}/scripts/search_alarm_rules.py --app <app_or_service>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

### Step 3：输出结果

将两个脚本的 JSON 数组合并后返回给用户，并标注规则类型。

如需查看某条规则的完整配置（PromQL 表达式、触发条件等），使用 `alarm-rule-detail` skill，传入对应
`id`。

## 错误处理

| 错误情况                  | 处理方式                             |
| ------------------------- | ------------------------------------ |
| 脚本退出码非 0            | 将 stderr 内容返回用户               |
| API 返回 `success: false` | 脚本已处理，直接透传错误信息         |
| 结果为空数组              | 告知用户该维度下暂无对应类型告警规则 |
| 网络不通                  | 提示用户确认是否在内网环境           |

## 参考文档

- **PQL 告警脚本输出字段说明**：[references/pql-rule-all-api.md](references/pql-rule-all-api.md)
- **服务告警脚本输出字段说明**：[references/rule-all-api.md](references/rule-all-api.md)
- **规则详情查询**：使用 `alarm-rule-detail` skill
