# 告警/故障/诊断卡片设计调研报告

> 调研时间：2026-04-17
> 调研平台：Datadog、PagerDuty、Grafana Alerting、飞书/钉钉、Sentry、阿里云 ARMS/CloudMonitor、Zendesk、Microsoft Teams Adaptive Cards

---

## 1. Datadog

### 1.1 Monitor Alert 告警通知卡片

**信息字段**：
- Monitor Name（告警名称）
- Monitor Message（告警消息正文）
- 告警状态：ALERT / WARN / OK / No Data
- 触发时间（Triggered at）
- 触发值（Current metric value）
- 环境标签（env / service / host 等 Tag）
- 受影响资源（Host、Pod、Service 等）
- 图表快照（Graph Snapshot，支持 Email 和 Slack 内嵌）
- Runbook 链接（可自定义插入）
- On-call 联系人（通过 @mention 指定）

**交互设计**：
- Slack 中可直接点击链接跳转 Monitor 详情页
- 通过 `/datadog` 命令在 Slack 内管理告警
- 支持在 Slack 中声明/协作/解决 Incident
- 告警支持 @channel、@user、@team 的 mention 语法
- 支持条件模板（if-else）动态调整消息内容

**截图**：
![Datadog Monitor Notification Configuration](https://docs.dd-static.net/images/monitors/guide/notification_message_best_practices/monitor_notification_message.bf73a18a39d1708a45b2b5de4c966fc7.png)

**参考来源**：https://docs.datadoghq.com/monitors/notify/

---

### 1.2 Watchdog AI 诊断卡片

**信息字段**：
- Status：`ongoing` / `resolved` / `expired`（超 48h 自动 expired）
- Timeline：异常发生时间段
- Message：异常描述（自然语言）
- Graph：异常指标可视化图（标注异常区间与 expected bounds）
- Tags：异常范围（env、service、endpoint 等）
- Impact（影响分析）：受影响的用户/页面/服务
- Suggested Next Steps：调查建议步骤
- Associated Monitors：关联的已有告警规则
- Root Cause（RCA，需 APM）：根因分析结果

**交互设计**：
- 点击卡片展开详情面板（Overview tab）
- "Show expected bounds" 复选框切换图表视图
- "Enable Monitor" 按钮一键创建建议的告警规则
- 支持按 Alert Category、Status、Service 等维度筛选

**截图**：
![Watchdog Alert Explorer](https://docs.dd-static.net/images/watchdog/watchdog.764cd47e3927b6742a16238848b11171.png)
![Watchdog Alert Card Detail](https://docs.dd-static.net/images/watchdog/alerts/alerts_overview.db3ef881bd05e9f274be666fe5bcf461.png)

**优势**：
1. AI 主动发现：无需预设阈值，自动检测异常，降低漏报
2. 影响分析：自动关联受影响终端用户/页面，直接回答"影响了谁"
3. 根因分析（RCA）：APM 场景下自动推断根因，减少人工溯源时间
4. 图表内嵌：通知卡片直接附带异常指标图，无需跳转
5. 上下文丰富：Suggested Next Steps + Runbook 链接，行动指引清晰
6. 一致的模板变量系统：全面支持动态变量，定制性强

**劣势**：
1. 不支持 Prometheus/外部 Alertmanager，与自建 Prometheus 生态兼容性差
2. 通知卡片视觉定制受限，Slack 通知的 Block 结构不能自定义
3. 截图依赖 Email/Slack，其他渠道（钉钉、飞书）无原生图表嵌入支持
4. Watchdog 是 Pro/Enterprise 功能，价格较高
5. 复杂告警规则学习曲线陡

**参考来源**：https://docs.datadoghq.com/watchdog/alerts/

---

## 2. PagerDuty — Incident 卡片 + Slack 集成卡片

**信息字段**：
- Incident ID 和 Incident Title
- 状态：Triggered / Acknowledged / Resolved
- 优先级（Priority）：P1～P5
- 受影响服务（Service）
- 分配的 On-call 人员（Assigned to）
- 上报策略（Escalation Policy）
- 触发时间（Triggered at）
- 最新更新时间
- 状态更新（Status Notes）：可在 Slack 直接添加
- AI 状态摘要（PagerDuty Advance 订阅，自动生成）

**交互设计**：
- Acknowledge：一键确认告警
- Resolve：一键解决告警
- Join incident channel：快速加入专属响应频道
- Add Responder：增加响应人
- Create Dedicated Channel：为本次 Incident 创建专属 Slack 频道
- Slash 命令：`/pd declare` / `/pd oncall` / `/pd trigger` / `/pd resolve`
- 专属响应频道支持完整事件生命周期协作

**优势**：
1. 完整 Incident 生命周期管理：触发→确认→升级→解决，全流程 Slack 内可操作
2. 双频道模式：通知频道（广播）+ 专属频道（响应协作），清晰分层
3. 卡片实时更新：通知卡片会随 Incident 状态变化自动刷新
4. AI 辅助（PagerDuty Advance）：自动生成状态摘要和 Incident 洞察
5. On-call 路由可见：卡片直接显示当前值班人，责任链清晰

**劣势**：
1. 功能依赖账号关联：Slack 用户须先与 PagerDuty 账号绑定才能操作，初始配置繁琐
2. 通知频道上限 3 个：每个 Incident 最多关联 3 个通知频道
3. AI 功能需高级订阅：PagerDuty Advance 另收费
4. 卡片样式不可自定义，企业品牌化定制空间有限
5. Thread 更新默认关闭聚合，需手动配置

**参考来源**：https://support.pagerduty.com/main/docs/slack-user-guide

---

## 3. Grafana Alerting — 告警通知卡片

**信息字段**：
- Alert Title（自定义模板）
- Alert Status：Firing / Resolved
- 触发时间 / 恢复时间
- 告警规则名称（Alert Rule Name）
- Labels：告警标签（env、service、instance 等）
- Values（触发阈值和当前值）
- Annotations（Summary / Description，可自定义模板）
- 面板截图（Panel Screenshot，需 Image Renderer 插件）
- 跳转链接（"Go to alert rule" 链接）

**交互设计**：
- Slack 中通过 Thread 聚合同一告警所有通知（Firing + Resolved）
- Critical 级别通知单独推送到频道
- 通过 Notification Templates 完全自定义 Title 和 Body（Go 模板语法）
- 支持面板截图附件

**优势**：
1. 模板自定义极强：Go 模板语法支持完全自定义通知内容
2. 面板截图内嵌：支持将触发时的 Grafana 面板图截图附在通知中
3. Thread 聚合：同一告警所有状态变更统一在同一 Thread
4. 开源免费：核心 Alerting 功能完全开源
5. 对接渠道丰富：Email、Slack、PagerDuty、钉钉、飞书、Webhook 等

**劣势**：
1. 图表截图配置复杂：需单独安装 Image Renderer 插件 + 配置云存储
2. 交互能力弱：通知仅为只读，无法在 Slack 内直接操作告警
3. 卡片视觉设计基础：Slack Block 格式简单，无法展示复杂卡片布局
4. 模板语法学习成本：Go 模板对非开发人员不友好
5. 每次通知最多 2 张截图，无实时更新

**参考来源**：https://grafana.com/docs/grafana/latest/alerting/

---

## 4. 飞书/钉钉 — 监控告警自定义卡片

### 4.1 飞书

**信息字段**：
- 标题区：图标 + 颜色标记（红/橙/绿区分严重性）+ 告警名称
- 告警时间 / 告警级别（P0/P1/P2）
- 触发指标 + 当前值
- 受影响服务/应用
- 告警描述/摘要
- 详情链接
- 处理人（@mention）
- 状态标识（告警中/已恢复）

**交互设计**：
- 确认/认领/查看详情/静音按钮
- 按钮点击后卡片内容实时更新（无需刷新）
- 支持 @群成员 mention
- 告警触发可自动拉群

### 4.2 钉钉

**信息字段**：
- 卡片头部区：告警图标 + 告警标题（高亮颜色）
- 告警类型 / 告警名称 / 告警时间
- 告警规则/条件（如 `cpu_usage > 80`）
- 告警值 / 所属应用/集群
- 指标走势图（ARMS Prometheus 支持）
- 告警状态（告警中/已恢复）
- @联系人

**交互设计**：
- 确认/屏蔽/查看详情 按钮
- 互动卡片支持按钮点击后状态实时更新
- 支持卡片三部分结构：头部区 / 内容区 / 操作区

**优势**：
1. 可交互性强：卡片支持按钮点击后实时更新状态，实现告警闭环操作
2. 自动拉群：告警触发可自动创建响应群组
3. 中国生态集成：与阿里云 ARMS/Prometheus 原生打通，支持指标走势图内嵌
4. @精准通知：支持通过 IM 账号字段 @具体负责人
5. 无需跳转：核心操作在 IM 内完成

**劣势**：
1. 卡片开发成本较高：互动卡片需要使用搭建器开发，定制复杂
2. 跨平台能力弱：飞书卡片仅限飞书生态
3. 图表嵌入有限制：走势图仅 ARMS Prometheus 支持
4. 高级交互需企业版授权
5. 历史记录管理差：IM 群内告警历史检索能力弱

**参考来源**：
- https://www.feishu.cn/hc/zh-CN/articles/743833203207
- https://help.aliyun.com/zh/arms/alarm-operation-center/configure-a-metric-trend-chart-in-a-prometheus-alert-notification

---

## 5. Sentry — 错误告警卡片

**信息字段**：

Issue Alert 字段：
- Issue Title（错误标题/异常类型）
- Project / Environment / Issue Level（fatal/error/warning/info）
- Culprit（触发问题的代码位置）
- Tags（browser、os、release 等）
- 最后发生时间 / 首次发生时间 / 发生次数 / 受影响用户数

Metric Alert 额外包含：
- 指标状态图（含触发后图表段，内嵌）
- Thread 聚合：同一告警所有通知在 Thread 内

**交互设计**：
- Resolve 按钮：直接从 Slack 标记 Issue 为已解决
- Archive 按钮：将 Issue 归档
- Select Assignee 下拉菜单：指定 Issue 负责人
- Metric Alert 的通知通过 Thread 管理，Critical 级别单独广播

**优势**：
1. 错误上下文丰富：Culprit（代码定位）+ Tags（环境/用户属性）帮助快速定界
2. Metric Alert 图表内嵌：指标趋势图直接附在 Slack 通知中
3. Slack 内直接操作：Resolve/Archive/Assign，无需跳转
4. Thread 聚合机制：同一告警所有状态变更在 Thread 内
5. 支持个人/团队通知

**劣势**：
1. Issue Alert 无图表：只有 Metric Alert 才有图表
2. 通知格式定制空间有限：只能选择是否展示特定 Tags
3. 大量告警时噪音高：事件风暴场景下缺乏聚合能力
4. Assignee 功能有限：只能分配给 Sentry 内已有成员
5. 时延数字格式不够精炼

**参考来源**：https://docs.sentry.io/organization/integrations/notification-incidents/slack/

---

## 6. 阿里云 ARMS / CloudMonitor — 告警卡片

**信息字段**：
- 告警标题 / 告警状态（触发/恢复）/ 触发时间
- 告警规则/条件（PromQL 条件）/ 告警值
- 所属集群/应用/服务 / 命名空间
- 指标走势图（ARMS Prometheus 支持）
- 查看详情链接 / @联系人 / 告警 ID

CloudMonitor 通用变量：`$RuleName`、`$Namespace`、`$ResourceId`、`$MetricName`、`$Condition`、`$CurValue`、`$StartTime`、`$EndTime`

**交互设计**：
- 确认告警 / 屏蔽告警 / 查看详情 按钮
- CloudMonitor 通知模板支持 Markdown 自定义格式
- 通知渠道：电话、短信、邮件、钉钉、飞书、企业微信、Slack、Webhook

**优势**：
1. 多源告警聚合：支持 Prometheus、CMS、SLS、Zabbix、Nagios 等 10+ 告警源统一汇聚
2. 指标走势图内嵌：ARMS Prometheus 告警可在钉钉卡片中嵌入 PromQL 趋势图
3. 与 IM 生态深度打通：钉钉/飞书内可直接处理告警
4. 通知模板灵活：支持 Markdown 自定义，变量系统完整
5. 告警聚合降噪：支持事件压缩、去重、降噪处理流

**劣势**：
1. 免费额度有限：每天 15 次短信 + 3 次电话，超额收费
2. 走势图支持有限：仅 ARMS Prometheus 支持图表内嵌
3. 国际化弱：主要服务国内客户
4. 卡片定制能力弱于原生开发方案
5. 跨云告警聚合能力有限

**参考来源**：https://help.aliyun.com/document_detail/2929470.html

---

## 7. Zendesk — 工单/事件通知卡片

**信息字段**：
- Ticket ID / Ticket Subject（工单标题）
- Priority（Low/Normal/High/Urgent）
- Status（New/Open/Pending/Solved/Closed）
- Requester（提交人）/ Assignee（处理人）/ Group（处理团队）
- 创建时间 / 更新时间 / SLA 到期时间
- Tags（自定义标签）
- Description（问题描述，支持富文本）
- Channel（来源渠道：Email/Chat/Phone/Web 等）
- Satisfaction rating（满意度评分）

**交互设计**：
- Slack 集成：工单创建/更新通知推送到指定频道
- 直接回复通知可添加工单评论
- 支持从 Slack 创建工单
- 工单更新支持实时 Webhook 推送

**优势**：
1. SLA 可视化：直接在卡片中展示 SLA 到期时间，催促处理
2. 全渠道来源标注：清楚标识工单来自哪个渠道（客服/技术/销售）
3. 富文本描述：支持格式化问题描述，信息完整
4. 完善的状态流转：New→Open→Pending→Solved，状态语义清晰
5. 可配置触发器：灵活定义何时发送通知

**劣势**：
1. 告警场景不够原生：Zendesk 主要为客服设计，技术告警场景需大量定制
2. IM 集成交互弱：Slack 通知主要为只读，操作能力有限
3. 无图表能力：不支持指标趋势图等可视化
4. 卡片信息量受限：Slack 通知字段数量有上限
5. 高级功能需企业版

**参考来源**：https://support.zendesk.com/hc/en-us/articles/4408887153818

---

## 8. Microsoft Teams Adaptive Cards — 监控告警场景

**信息字段**（Adaptive Card 标准）：
- 卡片标题（TextBlock，支持颜色/大小/加粗）
- 图片区（Image，支持 URL 内嵌）
- 键值对（FactSet，如 告警级别/时间/服务名）
- 文本内容区（TextBlock，支持 Markdown 子集）
- 操作区（ActionSet）：按钮列表
- Container 分组（多区块布局）

**交互设计**：
- Action.OpenUrl：打开外部链接
- Action.Submit：提交数据到后端（可触发告警操作）
- Action.ShowCard：展开嵌套子卡片（折叠详情）
- Action.Execute（Universal Actions）：在 Teams 内直接执行操作并更新卡片
- 支持下拉选择框（Input.ChoiceSet）
- 支持文本输入（Input.Text，如添加备注）

**优势**：
1. 交互能力最强：Universal Actions 支持卡片内操作后实时刷新，无需重发
2. 布局灵活：Container/Column 嵌套支持复杂布局
3. 跨平台一致性：Adaptive Card 规范跨 Teams/Outlook/Bot Framework 统一
4. 输入组件丰富：支持文本输入/下拉/日期选择，可实现复杂交互
5. 折叠展开：ShowCard 可隐藏详情，保持卡片简洁

**劣势**：
1. 渲染差异问题：不同 Teams 版本/平台渲染结果略有差异
2. 样式能力有限：颜色/字体选择有限，不如 Web 富文本灵活
3. 图表不原生支持：需嵌入图片URL，不能渲染动态图表
4. 开发调试成本高：需要用 Adaptive Card Designer 调试，学习曲线存在
5. 国内使用受限：Teams 在国内使用体验不稳定

**参考来源**：https://adaptivecards.io/explorer/

---

## 设计模式总结

### 常见信息字段（按出现频率排序）

| 字段 | 覆盖平台数 |
|------|-----------|
| 告警名称/标题 | 8/8 |
| 告警状态（Triggered/Resolved） | 8/8 |
| 触发时间 | 8/8 |
| 严重级别（P0/P1 或 CRITICAL） | 7/8 |
| 受影响服务/资源 | 7/8 |
| 处理人/On-call | 6/8 |
| 当前指标值/触发条件 | 6/8 |
| 跳转详情链接 | 8/8 |
| 指标趋势图 | 4/8 |
| 根因分析/AI 诊断 | 2/8（Datadog Watchdog、PagerDuty Advance）|
| 处置建议/Next Steps | 2/8（Datadog Watchdog）|

### 常见交互模式

1. **一键操作**：Acknowledge / Resolve / Assign（PagerDuty、Sentry、飞书/钉钉）
2. **Thread 聚合**：同一告警所有通知在同一 Thread（Grafana、Sentry、PagerDuty）
3. **卡片实时更新**：状态变化后卡片内容自动刷新（PagerDuty、飞书互动卡片、Teams Universal Actions）
4. **折叠展开**：卡片展示摘要，点击展开详情（Datadog Watchdog、Teams ShowCard）
5. **自动拉群**：告警触发自动创建响应群组（PagerDuty 专属频道、飞书）

### 诊断卡片 vs 告警卡片的设计差异

| 维度 | 告警卡片 | 诊断卡片 |
|------|---------|---------|
| 核心信息 | 什么触发了告警 | 为什么触发/影响了什么 |
| 指标展示 | 当前值 vs 阈值 | 异常区间 + 期望范围 |
| 行动指引 | Acknowledge/Resolve | 建议调查步骤/推荐操作 |
| 上下文 | 告警规则/标签 | 关联服务/历史案例/根因 |
| 状态流转 | Triggered → Resolved | Ongoing → Resolved → Expired |
| AI 能力 | 无或弱 | 异常检测 + 根因推断 + 影响分析 |

### AI 诊断卡片设计趋势（2024-2026）

1. **主动发现替代被动阈值**：AI 自动检测异常，不依赖人工设置规则（Datadog Watchdog）
2. **影响范围自动关联**：自动分析影响了哪些用户/服务/页面
3. **根因置信度排序**：多个可能根因按置信度排序展示
4. **行动闭环**：从诊断结论到处置操作在同一卡片完成（一键操作）
5. **状态生命周期管理**：ongoing/resolved/expired 明确的状态机

### 对告警诊断产品设计的核心启发

1. **卡片分层设计**：告警摘要卡片（快速感知）+ 右侧抽屉/对话窗口（深度排查），两层信息密度
2. **状态实时更新**：卡片随诊断进度动态刷新（诊断中 → 已完成），避免重复发卡片造成噪音
3. **影响分析前置**：第一屏展示"影响了什么"比"指标值是多少"更重要
4. **根因 + 置信度**：多根因按置信度排序，辅助决策
5. **一键闭环**：从卡片直接完成确认/屏蔽/处置，减少跳转
