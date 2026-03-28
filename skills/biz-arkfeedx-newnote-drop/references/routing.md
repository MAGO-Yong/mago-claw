# 原子 Skill 路由 · biz-arkfeedx-newnote-drop

## 路由表

| 节点 | 数据特征 | 原子 Skill | 置信度 |
|------|---------|-----------|--------|
| Step1 确认下跌 | 单指标，多时间点对比（当前/-1d/-7d） | metrics-compare | high |
| Step2 定位阶段 | 多维度分组（by phase），找异常分组 | metrics-breakdown | high |
| Step3 召回渠道 | 多维度分组（by name），找异常渠道 | metrics-breakdown | high |
| Step4 召回根因 | 3个指标同时分析，含条件分支判断 | metrics-multi-compare | high |
| Step5.0 前置检测 | 复合 PromQL 检测，返回异常渠道名 | metrics-compare | high |
| Step5.1 索引池quota | 指标分析 + 工具调用 | metrics-compare + tool-invoke | medium |
| Step5.2 omega笔记年龄 | 跨datasource指标，过滤前/后对比 | metrics-compare | high |
| Step6 内容供给 | 4个指标并行，跨datasource | metrics-multi-compare | high |

## 特殊工具

| 工具 | 触发条件 | 参数 |
|------|---------|------|
| index-switch-check | Step5.1 发现索引池 quota 异常 | name=异常索引表名（来自5.1查询结果） |

## 分支路由逻辑

```
Step3 结果 → 渠道量下跌 → Step4
Step3 结果 → 渠道量正常 → Step5

Step4 结果 → 种子数下跌   → Step6
Step4 结果 → 笔记年龄变老  → Step5
Step4 结果 → quota配置变化 → [人工] 联系推荐策略

Step5.2 结果 → 过滤后异常（年龄变老）→ [人工] 联系索引侧
Step5.2 结果 → 过滤前异常（消息断流）→ Step6
```
