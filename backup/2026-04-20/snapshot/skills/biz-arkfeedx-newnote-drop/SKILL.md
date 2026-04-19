---
name: biz-arkfeedx-newnote-drop
version: v1.0
created: 2026-03-26
description: >
  外流推荐（arkfeedx）新笔记曝光占比下跌故障排障。
  触发时机：收到告警「外流1h新笔记曝光占比 周同比下跌超过10%」。
  适用服务：arkfeedx。
trigger:
  type: alert
  rule: arkfeedx · 外流1h新笔记曝光占比下跌_P1
  condition: 外流1h新笔记曝光占比 周同比下跌 > 10%
  severity: P1
---

# biz-arkfeedx-newnote-drop

## 触发场景

收到告警：**arkfeedx · 外流1h新笔记曝光占比下跌_P1**

触发条件：外流1h新笔记曝光占比 周同比下跌 > 10%

## 执行原则

- 不用人工确认，一查到底——检测到异常后自动按决策树完成全链路排查
- 所有指标查询同时查当前值、-1d、-7d 三个时间点，综合判断
- 发现异常时段后，后续步骤仅针对异常时段查询（token 优化）

## 排查链路

完整 SOP 见 [references/sop.md](references/sop.md)

## 数据绑定

指标配置见 [references/metrics.md](references/metrics.md)

## 原子 Skill 路由

见 [references/routing.md](references/routing.md)

## 联系人

| 问题类型 | 联系对象 |
|---------|--------|
| 索引切换/消息断流 | 索引侧同学 |
| 召回quota/策略配置 | 推荐策略 |
| 审核积压/转码延迟 | 社区安审 |
| 发布QPS异常 | 社区发布链路 |
