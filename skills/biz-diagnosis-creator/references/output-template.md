# 业务排障 Skill 输出模板

Creator 生成的排障 Skill 固定结构如下：

```
{skill-name}/
├── SKILL.md          # 触发描述（轻量，仅元信息）
└── references/
    ├── sop.md        # 排查链路（结构化SOP）
    ├── metrics.md    # 数据绑定（图表→PQL映射）
    └── routing.md    # 原子Skill路由表
```

---

## SKILL.md 模板

```yaml
---
name: {skill-name}
description: >
  业务排障：{异常场景一句话描述}。
  触发时机：{触发条件，如"收到XX告警"或"巡检发现XX指标下跌超过YY%"}。
  适用服务：{service}。
  使用时需提供：告警触发时间（或排查时间范围）。
---

# {业务名称} 排障 Skill

## 使用方式

告知排查时间范围，Skill 将按 SOP 逐步执行并输出结论。

## 排查链路

见 [references/sop.md](references/sop.md)

## 数据绑定

见 [references/metrics.md](references/metrics.md)

## 原子 Skill 路由

见 [references/routing.md](references/routing.md)
```

---

## references/sop.md 模板

排查链路的完整描述，包含条件分支和并行关系。

```markdown
# 排查链路 SOP

## 基本信息

- **异常场景**：{场景描述}
- **触发方式**：{告警触发 / 定时巡检 / 用户反馈}
- **触发条件**：{具体阈值或条件}
- **服务**：{service_name}
- **严重级别**：{P0紧急 / P1一般 / 定时巡检}

## 排查步骤

### Step 1：{步骤名称}

- **目的**：{这一步想确认什么}
- **执行方式**：串行 / 并行（与Step X并行）
- **数据**：→ 见 metrics.md #step-1
- **判断逻辑**：
  - 若 {条件A} → 进入 Step 2
  - 若 {条件B} → 进入 Step 3（跳过Step 2）
  - 若 {条件C} → 结论：{直接给出结论}

### Step 2：{步骤名称}

- **前置条件**：Step 1 中 {条件A} 成立
- **目的**：{这一步想确认什么}
- **执行方式**：并行（Step 2a / 2b / 2c 同时执行）
- **数据**：→ 见 metrics.md #step-2
- **判断逻辑**：
  - 若 {子步骤2a} 有突变 → 定位到 {模块}，进入 Step 3a
  - 若 {子步骤2b} 有突变 → 定位到 {模块}，进入 Step 3b
  - 若均无突变 → 结论：{上报，人工介入}

# （以下按实际步骤数量继续）

## 结论输出格式

每步分析完成后输出：
- **当前值** vs **基准值**（1d前 / 7d前）
- **变化幅度**（绝对值 + 百分比）
- **是否异常**（是/否 + 判断依据）
- **下一步动作**（进入哪个Step / 给出结论）

最终输出：
- **根因定位**：{模块/阶段/渠道}
- **异常表现**：{具体指标变化}
- **建议动作**：{回滚 / 扩容 / 联系XX团队 / 继续观察}
```

---

## references/metrics.md 模板

每个步骤绑定的图表和数据查询配置。

```markdown
# 数据绑定

## Step 1 {步骤名称} {#step-1}

| 字段 | 值 |
|------|----|
| 大盘 | {dashboard_name} |
| 图表 | [{panel_name}]({panel_url}) |
| 数据类型 | metrics / logs / trace |
| Datasource | {datasource} |
| PQL | `{pql}` |
| 对比基准 | offset=1d / offset=7d / 无 |
| 异常阈值 | {如：下跌>5% 视为异常} |
| 分析维度 | {如：按stage分组 / 按source分组} |

## Step 2a {步骤名称} {#step-2a}

（同上格式）

## Step 2b {步骤名称} {#step-2b}

（同上格式）
```

---

## references/routing.md 模板

步骤到原子 Skill 的映射，供 Agent 执行时查找。

```markdown
# 原子 Skill 路由表

| Step | 原子Skill ID | 调用参数覆盖 | 文档 |
|------|-------------|-------------|------|
| Step 1 | metrics-compare | offset=7d, threshold=0.05 | [查看](https://xray.devops.../skills/metrics-compare) |
| Step 2（并行） | metrics-multi-compare | group_by=stage | [查看](https://xray.devops.../skills/metrics-multi-compare) |
| Step 2a | metrics-breakdown | group_by=channel, top_n=10 | [查看](https://xray.devops.../skills/metrics-breakdown) |
| Step 2b | metrics-threshold | threshold=0.95, direction=below | [查看](https://xray.devops.../skills/metrics-threshold) |
| Step 2c | metrics-compare | offset=1d | [查看](https://xray.devops.../skills/metrics-compare) |

## 并行执行说明

- Step 2a / 2b / 2c：并行执行，等待全部完成后汇总判断
- Step 3a / 3b：条件触发，根据 Step 2 结果选择其一执行
```
