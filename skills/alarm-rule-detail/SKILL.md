---
name: alarm-rule-detail
description:
  根据 rule_id 查询 Xray 告警规则的完整配置。支持 PQL 告警（PromQL
  表达式类）和服务告警（中间件/客户端/RPC 阈值类）两类规则。当用户提供 rule_id
  并需要查看规则详情时触发。
version: 1.0.0
metadata:
  category: alarm
  subcategory: rule
  platform: xray
  trigger: rule_id
  input: [rule_id]
  output: [rule_config]
  impl: python-script
---

# 告警规则查询

## 两类规则说明

| 类型             | 适用场景                                                    | 脚本                            |
| ---------------- | ----------------------------------------------------------- | ------------------------------- |
| PQL 告警（默认） | 基于 PromQL 表达式的指标告警，如自定义监控、SLO 告警        | `scripts/get_alarm_pql_rule.py` |
| 服务告警         | 基于阈值条件的中间件/客户端告警（MySQL、RPC、客户端 RT 等） | `scripts/get_alarm_rule.py`     |

**默认使用 PQL 告警脚本。** 若用户明确说明是服务告警、中间件告警、或
`source=rule`，则使用服务告警脚本。

## 工作流程

### Step 1：确定规则类型

- 用户未说明 → 使用 PQL 告警脚本
- 用户说明是服务/中间件/客户端告警 → 使用服务告警脚本

### Step 2：执行脚本获取数据

**PQL 告警规则：**

```bash
python3 {SKILL_DIR}/scripts/get_alarm_pql_rule.py <rule_id>
```

**服务告警规则：**

```bash
python3 {SKILL_DIR}/scripts/get_alarm_rule.py <rule_id>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

### Step 3：输出结果

将脚本的 JSON 输出原样返回给用户，不做额外解读或推断。

## 错误处理

| 错误情况                  | 处理方式                                                |
| ------------------------- | ------------------------------------------------------- |
| 脚本退出码非 0            | 将 stderr 内容返回用户                                  |
| API 返回 `success: false` | 脚本已处理，直接透传错误信息                            |
| rule_id 不存在            | 告知用户 rule_id 无效，建议确认来源（PQL 还是服务告警） |
| 网络不通                  | 提示用户确认是否在内网环境                              |

## 参考文档

- **PQL 告警脚本输出字段说明**：[references/pql-rule-api.md](references/pql-rule-api.md)
- **服务告警脚本输出字段说明**：[references/rule-api.md](references/rule-api.md)
