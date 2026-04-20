# XRay Agent 评估记录 - 2026-04-01

**评估目标**：https://xray-agent.devops.sit.xiaohongshu.com/chat?agentId=xray_agent  
**评估环境**：SIT  
**评估文档**：https://docs.xiaohongshu.com/doc/7fb721e2bfd9f9499fb0b39e384ad002  
**评估人**：马恒洋  
**评估时间**：2026-04-01 19:08 起

---

## 本次评估用例（从3层各抽取）

| 编号 | 类型 | 目标Skill | 题面 |
|------|------|-----------|------|
| s1 | 单Skill | xray-log-query | searchpangu-secondary-goodsnote 最近30分钟error日志，按模式归类，3类+各举1条代表日志 |
| s5 | 单Skill | metrics-query-by-template | arksearchaiask-service-default 最近半小时服务异常波动，看耗时/错误率/流量，一句话结论 |
| m3 | 多Skill | xray-trace-search → xray-single-trace-analysis | arkwukong-20-default 最近30分钟较慢trace，分析可疑慢span |
| m6 | 多Skill | service-tree-query → alarm-event-query | 确认arksearchaiask-service-default服务树归属，查最近24h告警事件，总结风险 |
| c5 | 复杂场景 | 多能力综合 | arkwukong-20-default 最近1小时快速异常巡检，综合多能力，告知最值得跟进的3个问题 |

---

## s1 评估结果

**题面**：帮我查一下 searchpangu-secondary-goodsnote 最近 30分钟的 error 日志，按报错模式归类，总结最常见的 3 类问题，并各举 1 条代表日志。

**Langfuse Trace**：https://xray-langfuse-ot.devops.sit.xiaohongshu.com/langfuse-microapp/project/cmmd6clwb000jjf07x5bq816e/traces/4937c86a8c08f79c03417986d37a45e6?timestamp=2026-04-01T11:16:54.714Z

**工具调用链**：
`read_file × 2` → `ls` → `execute(query_charts)` → `execute(query_cluster，Redis不可用)` → `read_file × 2` → `execute × 7（手动换策略排查）`

**关键推理节点**：
- 先尝试调 query_cluster_logs.py（聚类接口），发现 Redis 不可用，主动降级
- NOT 语法不支持后，改用不同 logger 关键词多次过滤查其他类型
- 最终识别出3类错误并各取代表日志

**输出结果摘要**：
| 优先级 | 类型 | 根因 | 影响 |
|--------|------|------|------|
| ⚡最高 | LDS seekLastN 超时（>99%，约79,185条） | LDS 服务响应慢/不可用 | 全量商品召回失败，影响搜索结果质量 |
| 中 | ES 健康检查超时（数百条） | qcsh4 zone ES 节点抖动 | 仅影响健康探针，实际查询可能正常 |
| 低 | LSE status:-1（极少量） | LSE 接口异常 | 仅影响直播卡片话题召回场景 |

**各维度评分**：
| 维度 | 评分 | 说明 |
|------|------|------|
| 响应速度 | 3/5 | 总耗时约 3~4 分钟，偏长 |
| 意图识别 | 5/5 | 准确识别"按模式归类 + 各举1条代表日志" |
| Skill选择 | 4/5 | 正确选xray-log-query，失败后能降级 |
| 推理过程 | 5/5 | 降级路径清晰，遇阻后主动换策略 |
| 结果完整性 | 5/5 | 3类+代表日志+堆栈+根因+结论表格 |
| 结果准确性 | 5/5 | 均有真实日志佐证 |
| 交互体验 | 4/5 | 过程透明，结构清晰；工具调用次数略多但合理 |

**综合得分：4.4/5**

**亮点**：Redis不可用时主动降级、遇到API限制后换策略的自适应能力强

---

## s5 评估结果

**题面**：帮我分析 arksearchaiask-service-default 最近半小时服务有没有明显异常波动，重点看耗时、错误率和流量变化，并给一句话结论。

**工具调用链**：`read_file` → `ls` → `execute(problem + rpc 两种并行)` → `execute(计算关键数值)` → 输出

**关键推理节点**：
- 同时并行拉取 problem 和 rpc 两个维度数据
- 计算后发现 historyUpdate 接口 18:55~18:58 出现错误率毛刺，峰值 9.4%

**一句话结论**：
> 服务整体平稳，但 historyUpdate 接口在 18:55~18:58 出现明显错误率毛刺，峰值达 9.4%，随后已自动恢复，耗时和流量无异常。

**输出结果摘要**：
- 内部异常：无（exceptions 为空）
- 下游调用：无异常（callAnomalies 为空）
- 接口异常：historyUpdate 被标记为 critical

| 时间 | 总QPS | 失败QPS | 错误率 |
|------|-------|---------|--------|
| 18:55 | 51.6 | 1.92 | 3.7% |
| **18:56** | **51.5** | **4.84** | **9.4% ← 峰值** |
| 18:57 | 50.8 | 1.93 | 3.8% |
| 18:58 | 53.5 | 4.30 | 8.0% |
| 18:59之后 | ~52 | ~0.3 | ~0.6% |

- 流量：全程稳定在 50~54 QPS，无波动
- 耗时：无异常

**各维度评分**：
| 维度 | 评分 | 说明 |
|------|------|------|
| 响应速度 | 4/5 | 约 1.5 分钟，明显快于 s1 |
| 意图识别 | 5/5 | 准确抓住耗时/错误率/流量三个维度 |
| Skill选择 | 5/5 | metrics-query-by-template，并行拉两个维度 |
| 推理过程 | 5/5 | 并行查询+数值计算，定位到 historyUpdate 18:56 峰值 |
| 结果完整性 | 5/5 | 三维度全覆盖，有数据表格+建议 |
| 结果准确性 | 5/5 | 异常时间点精确，数值清晰 |
| 交互体验 | 5/5 | 结构极清晰，一句话结论+详情分离 |

**综合得分：4.9/5**

**亮点**：并行拉取、精确定位毛刺时间窗口（4分钟）、一句话结论高度概括

---

## m3 评估结果

> 待填写

---

## m6 评估结果

> 待填写

---

## c5 评估结果

> 待填写

---

## 总体评估结论

> 待填写（5道题跑完后汇总）
