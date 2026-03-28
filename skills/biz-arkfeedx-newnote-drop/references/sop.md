# 排查 SOP · biz-arkfeedx-newnote-drop

## 执行原则

- 对比分析法：所有指标同时查当前值、-1d、-7d 三点综合判断
- 异常判断：当前值 < -1d 且 < -7d → 可能故障；仅比 -1d 低 → 可能昨天偏高回归正常
- 特殊日期排除：法定节假日、开学季、重大活动期间需结合业务背景判断

## 决策树

```
告警触发
  │
  ▼
Step1：确认下跌（先行，串行）
  查 1h 占比 + 24h 占比，对比 -1d / -7d
  ├─ 双向下跌 + 非特殊日期 → 确认异常，进入 Step2
  └─ 单向下跌 或 特殊日期  → 继续观察，终止
  │
  ▼
Step2：定位阶段（串行）
  查各阶段1h新笔记占比（by phase），对比 -1d / -7d
  ├─ postrank 双向下跌 → 召回问题，进入 Step3
  └─ postrank 正常     → 精排/重排问题（本 Skill 范围外），终止
  │
  ▼
Step3：召回渠道排查（串行）
  查各渠道召回量占比（by name），对比 -1d / -7d
  ├─ 某渠道双向下跌 → 记录异常渠道，进入 Step4
  └─ 渠道量均正常   → 进入 Step5（索引问题）
  │
  ▼
Step4：召回根因分析（分支节点，3个出口）
  同时查：种子个数（by reason_type）/ 笔记平均年龄（by type）/ 索引池quota（by name）
  对比 -1d / -7d
  ├─ 种子数双向下跌  → 进入 Step6（内容供给）
  ├─ 笔记年龄双向变老 → 进入 Step5（索引排查）
  └─ quota 配置变化  → 联系推荐策略，终止
  │
  ▼
Step5：索引排查（子步骤节点，两个入口：来自Step3渠道正常 或 Step4年龄变老）
  │
  ├─ 5.0 前置检测
  │     PromQL 检测笔记年龄变老且超阈值（比 -7d 变老 > 20%）
  │     ├─ 有数据返回 → 记录 type（异常渠道名）→ 进入 5.1
  │     └─ 无数据返回 → 直接进入 5.2
  │
  ├─ 5.1 向量索引池 quota
  │     查 vec_reason_and_pool_cnt（by reason_type=5.0返回值, name）
  │     对比 -1d / -7d
  │     有异常 → 调用 index-switch-check(name=异常索引表名)
  │       ├─ 切换卡住/未切换 → 联系索引侧同学，终止
  │       └─ 正常            → 进入 5.2
  │
  └─ 5.2 omega 侧笔记年龄
        查 {__name__=~".*note_age_one_hour"}（vms-search）
        过滤前/后对比：
        ├─ 过滤前正常，过滤后异常（年龄变老）→ 索引表未切换 → 联系索引，终止
        ├─ 过滤前异常                         → 消息断流 → 进入 Step6
        └─ 均正常                             → 其他原因，人工排查
  │
  ▼
Step6：内容供给排查（并行检查4项）
  ├─ 内容池1h新笔记数：zebraindex_inc_note_cnt（group_type=3600, vms-recommend）
  ├─ 内容池24h新笔记数：zebraindex_inc_note_cnt（group_type=86400, vms-recommend）
  ├─ 审核重试任务数：postnotescanner_singleshardtablescanner（vms-shequ）
  ├─ 转码延迟P95：post_task_finish_seconds（vms-shequ）
  └─ 发布QPS：api_request_count（endpoint=newnote|editnote, vms-shequ）
  对比 -1d / -7d，输出结论：
  ├─ 审核重试上涨 或 转码延迟上涨 → 联系社区安审，终止
  ├─ 发布QPS下跌                  → 联系社区发布链路，终止
  └─ 内容池笔记数减少              → 上游供给问题，上报，终止
```

## 特殊日期排除

| 类型 | 影响特征 |
|------|---------|
| 法定节假日（春节/国庆/五一等）| 全平台笔记量自然下降 |
| 学生寒暑假（1-2月/7-8月）| 学生用户增长，新笔记年龄段变化 |
| 开学季（2月/9月初）| 学生用户下降 |
| 重大社会事件 | 内容审核策略调整 |
