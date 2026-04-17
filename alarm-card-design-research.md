# 告警 / 故障 / 诊断卡片设计调研报告

> 调研时间：2026-04-17  
> 调研范围：监控/可观测、BI、ITSM、IM集成、其他平台  
> 调研目标：信息字段、交互设计、诊断类卡片特殊设计、截图、优劣势分析

---

## 一、监控 / 可观测平台

### 1.1 Datadog

#### 1.1.1 普通 Monitor 告警通知卡片

**卡片类型：** Monitor Alert Notification（发送至 Slack、Email、PagerDuty 等）

**信息字段：**
| 字段 | 说明 |
|------|------|
| 告警标题 | `[ALERT] Monitor Name` 格式，含状态标识 |
| 状态 | ALERT / WARNING / NO DATA / RESOLVED，用颜色区分（红/黄/灰/绿） |
| 告警条件 | 触发阈值描述（如 `avg(last_5m) > 90`） |
| 指标快照图 | 内嵌 metric 折线图，标注触发时刻 |
| Tags | env、service、host 等标签，支持条件变量过滤 |
| 触发时间 | UTC 时间戳 |
| @mention | 被通知的人员或频道 |
| Runbook 链接 | 可选，跳转处置文档 |
| 告警详情页链接 | 一键跳转 Datadog 控制台 |

**Slack 卡片特有字段：**
- 支持 `/datadog incident declare` 直接发起 Incident
- 告警图内联图片（metric snapshot）
- 条件变量：`{{#is_alert}}...{{/is_alert}}` 分状态显示不同文案

**交互设计：**
- Slack 中支持 `/dd mute` 静默、`/dd resolve` 解除
- 点击卡片中的图片可跳转到对应 Dashboard
- 支持双向同步：Datadog 内操作同步回 Slack 线程

**参考截图：**
> Datadog Slack 通知卡片（官方文档）：

![Datadog Monitor Notification](https://docs.dd-static.net/images/monitors/notifications/slack_monitor_notification.png)

#### 1.1.2 Watchdog AI 告警卡片（诊断类）

**卡片类型：** Watchdog Alert Card（AI 自动检测异常）

**信息字段：**
| 字段 | 说明 |
|------|------|
| Status | ongoing / resolved / expired |
| Timeline | 异常发生时间段 |
| Message | AI 生成的异常描述 |
| Graph | 异常时段可视化，支持"显示预期边界" |
| Tags | 异常范围标签（service、env、endpoint） |
| Impact | 受影响的用户数、页面路径、下游服务 |
| Suggested Next Steps | AI 建议的排查步骤 |
| Related Monitors | 关联的已有 Monitor 列表 |

**Watchdog RCA 诊断卡片三段式结构：**
1. **Root Cause（根因）**：版本变更 / 流量突增 / AWS实例故障 / 磁盘满
2. **Critical Failure（关键失效）**：首个受影响的服务，延迟/错误率飙升
3. **Impact（影响面）**：级联受影响的下游服务、RUM用户路径

**设计亮点：**
- 无需人工配置，全自动检测
- RCA 卡片将"症状→因果链→根因"可视化呈现
- 内嵌 Flame Graph 入口，点击 trace 样本可溯源

**参考截图（官方文档）：**

![Watchdog Alert Explorer](https://docs.dd-static.net/images/watchdog/watchdog.764cd47e3927b6742a16238848b11171.png)

![Watchdog Alert Card 详情](https://docs.dd-static.net/images/watchdog/alerts/alerts_overview.db3ef881bd05e9f274be666fe5bcf461.png)

![Watchdog RCA 根因分析](https://docs.dd-static.net/images/watchdog/rca/root_cause_cropped.9f55d64e9abbe037aacc3703ffbc2401.png)

![Watchdog RCA 影响面](https://docs.dd-static.net/images/watchdog/rca/views_impacted.f176e0a27b9997cbd63a976202ddf3ee.png)

**✅ 优势：**
1. **RCA 三段式结构**清晰（根因 → 关键失效 → 影响面），认知负担低
2. **Impact Analysis** 量化终端用户影响，帮助 on-call 快速判断优先级
3. AI 自动标注"预期边界"与"异常区间"，图形直观
4. 与 APM、Logs、RUM、基础设施打通，数据源丰富
5. 嵌入式操作（Slack 声明 Incident）减少上下文切换

**❌ 劣势：**
1. Watchdog RCA **强依赖 APM 接入**，没有 tracing 数据则根因分析缺失
2. **根因类型覆盖有限**（仅4种：版本变更/流量/EC2/磁盘），自定义场景无法识别
3. Slack 卡片不支持自定义 Block Kit，视觉设计灵活性低
4. 置信度/概率信息**不显式展示**，用户难以判断 AI 可信程度

---

### 1.2 PagerDuty

**卡片类型：** Incident Notification Card（多渠道：Slack/Email/SMS/Push/Phone）

**信息字段：**
| 字段 | 说明 |
|------|------|
| Incident ID | 唯一编号（如 #100） |
| Incident Title | 告警触发来源的描述 |
| Service | 触发告警的服务名 |
| Severity | critical / high / error / warning / info |
| Status | Triggered / Acknowledged / Resolved |
| Assigned To | 当前 on-call 负责人 |
| Escalation Policy | 升级策略名称 |
| Triggered At | 触发时间 |
| Description | 告警原始描述内容 |
| Conference Bridge | 战情室链接（电话会议/视频） |
| Runbook | 处置手册链接 |
| Detail Link | 深链跳转 PagerDuty 详情页 |

**Slack 卡片交互（PagerDuty for Slack）：**
- 一键 **Acknowledge**（确认接单）
- 一键 **Resolve**（关闭告警）
- 一键 **Escalate**（升级至下一级）
- 添加 Note（备注）
- 运行 Incident Workflow
- GenAI：`@PagerDuty what changed?`、`@PagerDuty draft a status update`
- 支持 Incident 专属频道（Dedicated Channel），所有操作双向同步
- 支持告警聚合，高峰期多个 incident 合并为 bundle 通知
- 支持 Jeli 导入 Slack 数据做 Post-Incident Review

**Incident 详情页字段（Web/Mobile）：**
- 时间轴（Timeline）：所有操作记录按时序展示
- Responders：参与处理人员列表
- Custom Fields：可配置业务字段
- Status Updates：对利益干系人的广播

**诊断/AI 能力（PagerDuty Advance）：**
- AI 生成状态更新草稿
- AI 自动生成事后总结
- AI Runbook 自动生成（Early Access）
- 上下文问答：@PagerDuty 回答"最近什么改变了"

**参考来源：**
- https://support.pagerduty.com/main/docs/slack-integration-guide
- https://support.pagerduty.com/main/docs/notification-content-and-behavior

**✅ 优势：**
1. **Slack 交互设计最成熟**，Acknowledge/Resolve/Escalate 一步到位
2. **GenAI 深度集成**，状态草稿、post-mortem、上下文问答覆盖全流程
3. **束状通知（Bundling）**有效防止告警轰炸
4. **Dedicated Channel** 机制为每个 incident 创建专属协作空间
5. 多渠道统一（Slack / SMS / Phone / Push），都支持交互响应

**❌ 劣势：**
1. **诊断能力薄弱**，本身不做根因分析，依赖接入方（Datadog/New Relic）提供诊断
2. 卡片字段较为固定，**自定义字段灵活性**不如飞书消息卡片
3. GenAI 功能仅在高级计划（AIOps）开放，基础用户无法使用
4. 通知内容**缺乏趋势图/指标图**，仅有文字描述

---

### 1.3 OpsGenie（Atlassian）

**卡片类型：** Alert Notification Card

**信息字段：**
| 字段 | 说明 |
|------|------|
| Alert ID / Alias | 唯一标识，用于去重 |
| Message | 告警标题/摘要 |
| Description | 详细描述 |
| Priority | P1（Critical）/ P2（High）/ P3（Moderate）/ P4（Low）/ P5（Informational） |
| Source | 来源系统/集成名 |
| Tags | 自定义标签 |
| Teams | 负责团队 |
| Responders | 直接响应人 |
| Actions | 自定义操作按钮（Acknowledge / Close / Snooze / Add Note / Assign） |
| Created At | 创建时间 |
| Details | 自定义 key-value 扩展字段 |

**交互设计：**
- Slack 集成：内联按钮 Acknowledge / Close / Add Note
- 支持 Snooze（延迟处理）操作
- 支持 On-call Schedule 展示（查看谁在值班）
- 告警分组和降噪（Alert Grouping）
- 支持 Heartbeat 监控（定期检测失败告警）

**诊断能力：** 无原生 AI 诊断，主要依赖告警路由和过滤规则减少噪音

**参考来源：**
- https://support.atlassian.com/opsgenie/docs/

**✅ 优势：**
1. **P1~P5 五级优先级**设计直观，与 ITIL 标准对齐
2. **自定义 Actions 按钮**灵活，可配置业务相关操作
3. **On-call 排班**与告警紧密结合，知道谁在值守
4. 与 Jira Service Management 深度集成，工单无缝流转

**❌ 劣势：**
1. **无 AI 诊断**能力，停留在规则路由层面
2. 告警卡片**视觉设计相对简单**，信息密度偏低
3. 已被 Atlassian 收购后，与 JSM 存在功能重叠，**定位有所模糊**
4. 趋势图/指标内嵌能力缺失

---

### 1.4 Grafana Alerting

**卡片类型：** Alerting Notification（支持 Slack、Email、Teams、PagerDuty、Webhook 等 Contact Points）

**Slack 通知卡片信息字段：**
| 字段 | 说明 |
|------|------|
| 告警标题 | 支持自定义模板（Go template） |
| 状态 | Firing / Resolved |
| 触发时间 | 时间戳 |
| Labels | 告警规则标签（env、job、instance 等） |
| Annotations | summary、description、runbook_url 等注释字段 |
| 告警面板截图 | 需安装 image rendering plugin，可附加 Panel 图片 |
| 值 | 触发时的指标当前值 |
| 跳转链接 | 到 Grafana Panel / Alert Rule 的深链 |

**交互设计：**
- **不支持**在 Slack 卡片内直接操作（Silence/Acknowledge），需跳转 Grafana UI
- 支持 Go 模板语言自定义消息结构（可选择/隐藏特定字段）
- **AI 生成模板**（Grafana Cloud）：用自然语言描述，AI 生成 Go 模板代码
- Contact Points 支持多渠道，同一模板可复用

**诊断能力：** Grafana IRM（Incident Response & Management，原 Grafana OnCall）
- Correlate alerts → Group into incidents
- 支持 runbook 关联
- 无内置 AI 根因分析

**✅ 优势：**
1. **模板灵活性最高**，Go template 可完全自定义消息内容和结构
2. **AI 模板生成**（Cloud 版）降低配置门槛
3. 面板截图内嵌，**直观展示异常时序**
4. 开源生态丰富，Contact Point 对接渠道覆盖面广

**❌ 劣势：**
1. **不支持 Slack 内联操作**，必须跳转 Web UI 处理，中断工作流
2. Slack 卡片**视觉设计固定**，无法使用 Slack Block Kit 自定义布局
3. 图片内嵌需要额外安装 renderer plugin，**配置复杂**
4. AI 诊断能力几乎为零，缺乏智能降噪和根因分析

---

### 1.5 New Relic

**卡片类型：** Issue/Alert Notification（通过 Workflows → Destinations 发送）

**Issue 核心字段：**
| 字段 | 说明 |
|------|------|
| Issue ID | 唯一标识 |
| Issue Name | 来自 Condition 的标题 |
| Priority | Critical / High / Medium / Low |
| State | Created / Activated / Acknowledged / Investigating / Closed |
| Condition Name | 触发的告警条件 |
| Entity | 受影响的实体（应用/主机/服务） |
| Threshold | 触发阈值 |
| Runbook URL | 处置文档链接 |
| Team Tag | 负责团队标签 |
| Account | 账户信息 |
| 事件触发器 | Activated / Acknowledged / Investigating / Closed / Priority Changed |

**Workflow 机制：**
- Issue 聚合（多个 Alert Event 合并为 Issue，减少噪音）
- 支持 NRQL 筛选器过滤 Issue
- 通知触发器可精细配置（优先级变化才触发）

**AI 能力（Applied Intelligence）：**
- **Anomaly Detection**：自动学习基线，检测异常（无需手动设阈值）
- **Incident Intelligence**：相关 Issue 自动关联合并
- **Alert Quality Management**：告警质量评分，识别嘈杂告警

**描述模板变量（丰富）：**
```
{{conditionName}} / {{targetName}} / {{timestamp}} 
{{tags.fullHostname}} / {{tags.aws.awsRegion}}
{{tags.label.owning_team}} / {{nrqlQuery}}
```

**✅ 优势：**
1. **Issue 聚合机制**精密，Incident Intelligence 自动相关性分析减少噪音
2. **描述模板变量**极为丰富，支持所有 entity 标签、AWS 元数据等
3. **Anomaly Detection** 无需手动设阈值，自适应基线检测
4. 告警质量管理（AQM）帮助识别和清除嘈杂规则

**❌ 劣势：**
1. **UI 复杂**，Workflows + Destinations + Conditions 三层配置学习曲线陡
2. 通知卡片**无内联图表**，视觉信息弱
3. AI 能力（Applied Intelligence）**与普通告警体系割裂**，用户难以统一使用
4. 中国区访问**延迟高**，国内团队体验差

---

### 1.6 Dynatrace

**卡片类型：** Problem Card（由 Davis® AI 自动生成）

**Problem Feed 字段（列表视图）：**
| 字段 | 说明 |
|------|------|
| Problem ID | 唯一编号（含 display_id） |
| Problem Name | Davis 自动生成的问题标题 |
| Status | Active / Closed |
| Category | Slowdown / Error / Resource / Availability |
| Impact | Frontend / Service / Infrastructure / Environment |
| Duration | 持续时长 |
| Root Cause Entity | 根因实体名称 |
| Affected Entities | 受影响实体数量 |
| Alert Profile | 触发的告警配置名 |

**Problem 详情卡片（诊断类）字段：**
| 字段 | 说明 |
|------|------|
| Root Cause | Davis 推断的根因实体及变更事件 |
| Impact Timeline | 问题演进时间轴 |
| Affected Services | 受影响服务列表+降级程度 |
| Events | 关联的部署事件、配置变更事件 |
| Davis Copilot | 内嵌 AI 对话（"为什么会发生这个问题？"） |
| Business Flow Impact | 受影响的业务流程（如支付、登录） |
| Response Time Degradation | 响应时间劣化图 |
| Error Rate Increase | 错误率升高图 |

**Dynatrace 独特设计：**
- **确定性 AI（Causal AI）**：不是统计相关，而是基于拓扑关系推断因果
- **自动根因判断**，无需配置规则
- Problem 生命周期自动管理（发现→确认→恢复→关闭）
- 与 Business Flows 打通，可量化业务影响
- Davis Copilot：用自然语言问"这个问题是什么原因"

**Problem Notification（推送字段）：**
- Problem title、severity、URL、impact、root cause、affected entities、tags

**参考截图（官方文档）：**

![Dynatrace Problems App Feed](https://dt-cdn.net/images/problems-app-problem-feed-view-1920-f7f665e813.png)

**✅ 优势：**
1. **Causal AI（因果 AI）** 是最强的根因分析能力，基于拓扑推断而非相关性
2. **Problem 自动生命周期管理**，无需人工确认根因；恢复后自动关闭
3. **Business Flow 影响量化**，将技术问题映射到业务损失
4. Davis Copilot 支持**自然语言问答**，SRE 可对话式排查
5. 全栈覆盖（基础设施/应用/用户体验/业务），信息最全

**❌ 劣势：**
1. **学习曲线极陡**，Problem 卡片信息密度过高，新用户难以快速消化
2. **专有性强**，深度依赖 Dynatrace 全栈接入，部分采用 hybrid 监控方案的团队难以使用
3. **自定义通知卡片灵活性差**，飞书/钉钉集成需通过 webhook + 自定义开发
4. 价格昂贵，全功能版本对中小团队不友好

---

### 1.7 阿里云 ARMS / CloudMonitor

**卡片类型：** 告警通知（支持钉钉/飞书/企业微信/邮件/短信/电话）

**告警通知字段（ARMS 告警中心）：**
| 字段 | 说明 |
|------|------|
| 告警名称 | 规则名称 |
| 告警级别 | 紧急/严重/警告/信息 |
| 告警状态 | 触发中 / 已恢复 |
| 触发时间 | 时间戳 |
| 持续时长 | 告警持续时间 |
| 告警内容 | 触发条件描述 |
| 集成来源 | Prometheus/ARMS/自定义 |
| 处理人 | 认领人（支持群内操作） |
| 详情链接 | 跳转控制台 |

**ARMS 告警中心特色（群内处理）：**
- 飞书/钉钉群卡片支持：**认领**、**屏蔽**、**关闭** 操作
- 操作结果回写到群内，告知所有人
- 支持告警聚合（相似告警合并），减少刷屏
- 告警风暴防护（同类告警只发一次）
- 自定义通知模板（支持变量替换）

**CloudMonitor 字段：**
- 产品名称、实例名、监控项、统计周期、阈值、当前值、告警时间

**通知渠道（腾讯云 CM 类似）：**
- 邮件/短信/微信/企业微信/电话（轮询/同时拨打）
- 接口回调（Webhook → 飞书/钉钉/Slack 机器人）
- 支持值班表（On-call Rotation）

**参考来源：**
- https://help.aliyun.com/zh/arms/alarm-operation-center/handle-alerts-in-group-chats

**✅ 优势：**
1. **群内操作认领/关闭**设计贴近中国团队使用习惯
2. **告警风暴防护**（聚合 + 降噪）比较完善
3. **通知渠道多样**（电话轮询/同时拨打等细粒度配置）
4. 与阿里云产品深度集成，开箱即用

**❌ 劣势：**
1. **无 AI 诊断**能力，停留在阈值规则层面
2. 卡片**视觉设计较为朴素**，信息结构不够清晰
3. 群内操作**权限控制弱**，任何群成员都可以操作
4. 跨云/混合云场景下，**集成能力有限**

---

### 1.8 腾讯云 CM（云监控）

**信息字段：**
- 策略名称、告警内容、告警对象（实例名）、告警时间、当前值、阈值
- 通知类型：告警触发 / 告警恢复（均可配置独立模板）
- 通知语言：中文 / 英文
- 渠道：邮件、短信、微信、企业微信、电话

**企业微信/飞书机器人集成：**
- 通过 Webhook 回调推送告警
- 支持 `@群成员`（需填写 userid）
- 告警推送最多重试 3 次，超时 5s

**✅ 优势：**
1. **值班表**（On-call Rotation）功能与通知模板直接绑定
2. 电话告警支持**DTMF 按键确认**（按1确认/按2屏蔽）
3. 日志服务（CLS）告警数据投递，支持后续检索分析

**❌ 劣势：**
1. **通知卡片无法自定义布局**，仅支持文本模板
2. 无 AI 根因分析能力
3. IM 集成依赖 Webhook 回调，不支持群内交互操作

---

### 1.9 AWS CloudWatch Alarms

**卡片类型：** SNS 通知 / AWS User Notifications / Chatbot

**核心字段（Email/SNS）：**
| 字段 | 说明 |
|------|------|
| Alarm Name | 告警名 |
| Alarm Description | 描述 |
| AWS Account | 账户 ID |
| Region | 区域 |
| State | ALARM / OK / INSUFFICIENT_DATA |
| Previous State | 状态变化 from → to |
| Reason | 触发原因描述（含指标值和阈值） |
| Timestamp | 状态变化时间 |
| Metric | 指标名称 + 维度 |
| Period | 统计周期 |
| Threshold | 阈值配置 |

**AWS Chatbot（Slack 集成）：**
- 支持将 CloudWatch Alarms 推送至 Slack 频道
- 可通过 EventBridge filter 按 alarm 名/状态 精细过滤
- 支持 User Notifications 聚合（同一时间多个 alarm 合并）
- 不支持 Slack 内联 Acknowledge/Resolve

**✅ 优势：**
1. **原生 AWS 集成**，无需额外配置，与 EC2/RDS/Lambda 等一键关联
2. **EventBridge 过滤**极为灵活，可按任意字段精细控制通知
3. **User Notifications** 支持 Email/Chatbot/Mobile App 统一管理

**❌ 劣势：**
1. 默认告警邮件**格式丑陋**，缺乏视觉层次，大量 JSON 原始数据
2. **无内置图表**，需额外开发 Lambda 生成带图通知
3. **无 AI 诊断**，完全依赖规则阈值
4. Slack 内**不能直接操作**，无 Acknowledge/Resolve 按钮

---

## 二、BI / 数据平台

### 2.1 飞书/钉钉（通用消息卡片平台）

> BI 平台告警通常通过飞书/钉钉的消息卡片发送，因此单独分析消息卡片能力。

**飞书消息卡片能力：**

| 能力 | 说明 |
|------|------|
| 结构化布局 | 支持 column_set、grid 等灵活布局 |
| 内嵌图表 | 支持折线图、柱状图、饼图等 chart 组件 |
| 交互按钮 | 支持 button（跳转/回传）、select（下拉）、date_picker（日期） |
| 二次确认弹窗 | 按钮点击可触发确认弹窗（防误操作） |
| 状态更新 | 用户操作后，卡片内容自动更新（无需重发） |
| 变量系统 | 支持卡片变量，同一模板在不同群发送不同数据 |
| 多场景复用 | 同一卡片模板可复用到不同群/场景 |
| @mention | 支持 @特定用户 |

**监控告警典型卡片结构（飞书）：**
```
[Header] 🚨 告警触发 - CPU 使用率超阈值           [状态标签: 严重]
────────────────────────────────────────────────
[指标名称]  CPU 使用率
[当前值]    95.3%     [阈值]  > 90%
[实例]      prod-k8s-node-01
[时间]      2026-04-17 14:32:00
[环境]      生产 / 华东 1
────────────────────────────────────────────────
[图表组件]  📈 过去 1 小时趋势图（折线图）
────────────────────────────────────────────────
[按钮]  [认领]  [屏蔽 30min]  [查看详情↗]
```

**✅ 优势：**
1. **图表组件原生支持**，告警卡片可直接内嵌趋势图，无需外链
2. **状态实时更新**，用户认领后卡片自动变更状态，全群可见
3. **交互组件丰富**（按钮/下拉/日期选择），定制化程度高
4. **变量系统**支持同一模板多场景复用，维护成本低

**❌ 劣势：**
1. 需要**开发接入**，卡片 JSON 配置复杂，门槛较高
2. 图表组件**数据格式要求严格**，不能直接嵌入 Prometheus 图
3. 卡片**字数有上限**，复杂诊断信息需要折叠设计

---

### 2.2 Tableau / Looker / Metabase / Superset（BI 告警）

> BI 平台的告警设计相对简单，主要关注数据异常通知。

**通用字段：**
| 字段 | 说明 |
|------|------|
| 指标名称 | 监控的业务指标 |
| 当前值 | 触发告警时的值 |
| 阈值/基线 | 配置的触发条件 |
| 变化率 | 同比/环比变化 |
| 维度 | 下钻维度（如城市、渠道） |
| 时间 | 触发时间 |
| 报表链接 | 跳转到对应数据集/看板 |
| 快照图 | 当前指标截图（部分平台支持） |

**Metabase 告警：**
- 支持 Email + Slack 通知
- 字段：问题名称、当前值、阈值、查看详情链接
- 图表：内嵌问题（Question）的当前渲染截图

**阿里云 Quick BI：**
- 支持钉钉/邮件通知
- 字段：报表名、指标名、当前值、同比/环比、告警规则说明

**✅ 优势：**
- 业务语义强，面向 PM/运营，字段语言更贴近业务

**❌ 劣势：**
- 几乎无交互（纯通知），不支持群内操作
- 诊断能力缺失，仅告知"出问题了"，不说明"为什么"

---

## 三、客诉 / 工单 / ITSM 平台

### 3.1 ServiceNow

**卡片类型：** Incident Card（Major Incident / Standard Incident）

**核心字段：**
| 字段 | 说明 |
|------|------|
| Incident Number | INC000XXXXX |
| Short Description | 一句话摘要 |
| Priority | 1-Critical / 2-High / 3-Moderate / 4-Low / 5-Planning |
| State | New / In Progress / On Hold / Resolved / Closed / Canceled |
| Category | 问题分类（Hardware / Software / Network 等） |
| Assignment Group | 负责团队 |
| Assigned To | 负责人 |
| Caller | 报障人 |
| CI (Configuration Item) | 关联的配置项（服务器/应用） |
| Business Impact | 业务影响描述 |
| Urgency | 紧迫程度（1-3） |
| Impact | 影响范围（1-3） |
| Resolution Notes | 解决说明 |
| SLA | 响应/解决时限 |
| Work Notes | 内部操作记录 |

**Now Assist（AI 能力）：**
- **Case Summarization**：AI 自动生成 Incident 摘要
- **Resolution Recommendations**：基于历史 Incident 推荐解决方案
- **Agent Assist**：实时建议下一步操作
- **Virtual Agent**：自然语言驱动的自助服务机器人

**Slack/Teams 集成：**
- 支持在 Teams/Slack 中创建 Incident
- 可查看 Incident 状态，但主要交互仍在 ServiceNow UI

**✅ 优势：**
1. **字段最完整**，覆盖 ITIL 全流程，企业级合规
2. **Now Assist AI** 提供摘要和历史推荐，有实用价值
3. **SLA 追踪**内置，自动计算响应/解决时限
4. **CI（配置管理数据库 CMDB）关联**，Incident 自动关联受影响资产

**❌ 劣势：**
1. **卡片信息极其繁杂**，字段数量过多，认知过载
2. **UI 老旧**，移动端体验差
3. **IM 集成较弱**，Slack/Teams 内功能受限
4. AI 能力（Now Assist）**需要高价附加模块**，基础版无法使用

---

### 3.2 Jira Service Management（JSM）

**卡片类型：** Request / Incident Notification

**核心字段：**
| 字段 | 说明 |
|------|------|
| Issue Key | PROJ-1234 |
| Summary | 标题摘要 |
| Priority | Blocker / Critical / Major / Minor / Trivial |
| Status | 状态（自定义工作流） |
| Assignee | 负责人 |
| Reporter | 报告人 |
| Components | 组件 |
| Labels | 标签 |
| Created/Updated | 时间 |
| SLA | 响应/解决时限（含剩余时间） |

**Slack 通知字段：**
- Issue Key、Summary、Priority、Status、Assignee、链接

**与 OpsGenie 集成：**
- 告警触发 → 自动创建 JSM Incident
- 双向同步状态

**✅ 优势：**
1. **工作流高度可配置**，状态机灵活
2. **SLA 可视化**（剩余时间倒计时）直观
3. 与 Confluence（文档）/Bitbucket（代码）/OpsGenie（告警）深度集成

**❌ 劣势：**
1. **诊断能力弱**，需要接入 Rovo AI 才有 AI 辅助
2. 通知卡片**字段较少**，信息不完整（点进去才能看全）
3. **学习曲线高**，配置复杂度不低于 ServiceNow

---

### 3.3 Zendesk

**卡片类型：** Ticket Notification（Email/Slack/SMS）

**核心字段：**
| 字段 | 说明 |
|------|------|
| Ticket ID | #12345 |
| Subject | 标题 |
| Priority | Urgent / High / Normal / Low |
| Status | New / Open / Pending / On-hold / Solved / Closed |
| Assignee | 负责人 |
| Requester | 用户/报障人 |
| Tags | 标签 |
| Description | 问题描述 |
| Updated At | 更新时间 |

**AI 能力（Zendesk AI）：**
- **Intent Detection**：自动识别工单意图，自动分类和路由
- **Sentiment Analysis**：情感分析，识别愤怒/紧急用户
- **Suggested Replies**：AI 建议回复内容
- **Intelligent Triage**：智能分流

**✅ 优势：**
1. **AI 智能分类和情感分析**，减少人工处理
2. **用户体验导向**，报障路径对终端用户友好
3. **多渠道统一**（Email/Chat/Social/Phone）

**❌ 劣势：**
1. **面向客服场景**，技术运维场景适配性差
2. 缺少技术字段（无 metrics、无指标图、无根因分析）
3. Slack 集成有限，通知内容简单

---

## 四、IM 集成卡片（Slack / 飞书 / Teams）

### 4.1 Datadog → Slack 告警卡片

**典型结构：**
```
🔴 [ALERT] High CPU Usage on prod-server-01
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 [内嵌指标折线图，标注异常区间]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Metric: system.cpu.user
• Value: 94.3% (threshold: >90%)
• Host: prod-server-01
• Environment: production
• Time: 2026-04-17 14:32 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@on-call-team | View in Datadog ↗
```

**交互：**
- `/dd mute prod-server-01`
- `/datadog incident declare`
- 图片点击直达 Dashboard

**✅ 优势：** 内嵌图片、双向同步、Incident 声明一体化  
**❌ 劣势：** 无 Block Kit 自定义布局，按钮交互有限

---

### 4.2 PagerDuty → Slack Incident 卡片

**典型结构（新版 Block Kit）：**
```
🚨 PagerDuty Incident #1234
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service:    Payment API
Summary:    Error rate spike > 5%
Severity:   🔴 Critical
Assigned:   @jane.smith
Triggered:  2026-04-17 14:30 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Acknowledge]  [Resolve]  [Escalate]  [Add Note]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 @PagerDuty what changed recently?
```

**GenAI 加持：**
- AI 状态更新草稿（Status Update）
- AI 会议摘要
- AI Runbook 生成（Early Access）

**✅ 优势：** 按钮交互最完整，GenAI 深度集成，专属频道协作  
**❌ 劣势：** 无内置图表，诊断信息依赖上游提供

---

### 4.3 飞书自定义消息卡片（监控场景）

**飞书卡片架构：**
- **Header**：标题 + 颜色标签（红/橙/绿）
- **Column Set**：多列布局，字段对齐
- **Chart**：折线图/柱状图/饼图
- **Button Group**：操作按钮（带二次确认）
- **状态更新**：操作后卡片内容实时刷新

**典型告警卡片设计（最佳实践）：**
```
[🔴 严重告警] 支付服务错误率超阈值
─────────────────────────────────
指标        错误率
当前值      5.3%        阈值  > 2%
服务        payment-svc
环境        生产 / 华东1
时间        2026-04-17 14:32:08
─────────────────────────────────
[📈 过去1小时趋势图]
─────────────────────────────────
[认领]  [屏蔽30分钟]  [查看Runbook]  [跳转详情↗]
─────────────────────────────────
已认领: ⬜ 无人认领
```

**操作后卡片更新：**
```
已认领: ✅ @张三 于 14:33 认领
```

**✅ 优势：**
1. **图表原生支持**，无需外链，可视化最强
2. **状态实时更新**，全群可见操作记录
3. **二次确认防误操作**，更安全
4. **变量系统**支持多场景卡片复用

**❌ 劣势：**
1. 开发配置**复杂度高**（JSON Schema），需专业开发
2. 图表数据**不支持实时刷新**（仅发送时快照）
3. 卡片更新需要 Bot Token 保持活跃，**稳定性依赖**

---

### 4.4 Microsoft Teams Adaptive Cards（告警场景）

**Adaptive Card 结构：**
```json
{
  "type": "AdaptiveCard",
  "body": [
    {"type": "TextBlock", "text": "🚨 Alert: High Memory", "weight": "bolder"},
    {"type": "FactSet", "facts": [
      {"title": "Service", "value": "auth-service"},
      {"title": "Value", "value": "92%"},
      {"title": "Threshold", "value": "> 85%"}
    ]},
    {"type": "Image", "url": "[metric_graph_url]"}
  ],
  "actions": [
    {"type": "Action.OpenUrl", "title": "View Dashboard", "url": "..."},
    {"type": "Action.Http", "title": "Acknowledge", "method": "POST"}
  ]
}
```

**特点：**
- JSON Schema 驱动，跨平台（Teams/Outlook/Cortana）
- 支持 Action.Submit（提交数据）、Action.OpenUrl、Action.ShowCard（展开子卡）
- Adaptive Cards Designer 可视化设计工具

**✅ 优势：**
1. **跨平台标准**，同一卡片可在 Teams/Outlook 复用
2. **设计工具完善**（Adaptive Cards Designer 所见即所得）
3. **Action.ShowCard** 支持折叠展开，信息层次丰富

**❌ 劣势：**
1. Action.Http **双向同步困难**，操作后卡片更新机制复杂
2. **图表支持弱**，只能嵌入静态图片 URL，无原生图表组件
3. 样式自定义**受限于 Teams 主题**，视觉差异化难

---

## 五、其他平台

### 5.1 Sentry（错误告警）

**卡片类型：** Issue Alert / Metric Alert

**Issue Alert 字段：**
| 字段 | 说明 |
|------|------|
| Issue Title | 错误名/异常类型（如 `ValueError: invalid literal`） |
| Project | 所属项目 |
| Environment | production / staging |
| Release | 版本号（Git tag/commit） |
| Platform | Python / JavaScript / iOS 等 |
| Level | fatal / error / warning / info / debug |
| Culprit | 出错的函数/文件（自动识别） |
| First Seen | 首次出现时间 |
| Last Seen | 最近出现时间 |
| Times Seen | 发生次数 |
| Users Affected | 受影响用户数 |
| Tags | 自定义标签（browser/os/server 等） |
| Stack Trace 摘要 | 部分平台支持 Slack 中显示前几帧 |

**Metric Alert 字段：**
- Alert Name、Status（Warning/Critical/Resolved）、触发阈值、当前值

**AI 能力（Sentry AI）：**
- **Autofix**：AI 自动分析错误根因，生成修复 PR
- **Issue Summary**：AI 自动总结问题（What happened / Possible cause / Suggested Next Steps）
- **Suspect Commits**：自动定位可疑提交（导致错误的 commit）
- **Similar Issues**：聚合相似问题，防止重复处理

**Sentry AI Issue Summary 卡片（诊断类设计）：**
```
📌 What happened
   Users are experiencing a 500 error when submitting checkout forms.
   
🔍 Possible Cause
   A NullPointerException in PaymentService.processCard() 
   introduced in commit a3f5d12 (Deploy: 2026-04-16)
   
💡 Suggested Next Steps
   1. Rollback to version v2.3.1
   2. Review changes in payment/processor.py lines 142-168
   3. Add null check for card.token field
```

**✅ 优势：**
1. **Suspect Commits** 精准定位引入 Bug 的代码变更，极大缩短排查时间
2. **Autofix AI** 可以自动生成修复 PR，是最接近"自动修复"的设计
3. **Similar Issues** 聚合减少噪音，防止同一问题重复告警
4. Issue Summary 的三段式（发生了什么/可能原因/建议步骤）结构清晰

**❌ 劣势：**
1. **仅覆盖代码错误层面**，不涉及基础设施/网络/数据库等维度
2. Autofix **仅对 Python/JavaScript** 等特定语言成熟，覆盖范围有限
3. Slack 通知卡片**无内联图表**（仅文本）
4. AI 功能**需要付费 Seer 计划**，基础版体验有限

---

### 5.2 GitHub / GitLab（CI/CD 失败通知）

**GitHub Actions 失败通知字段：**
| 字段 | 说明 |
|------|------|
| Repository | 仓库名 |
| Workflow | 工作流名称 |
| Job | 失败的 Job 名 |
| Branch / PR | 触发的分支或 PR |
| Commit | 触发提交（SHA + 摘要） |
| Author | 提交作者 |
| Status | failure / cancelled / success |
| Duration | 执行时长 |
| Run URL | 详情链接 |
| Failed Steps | 失败步骤列表 |

**Slack 集成（GitHub for Slack）：**
```
❌ GitHub Actions: Build failed
Repository:  myorg/payment-service
Branch:      feature/add-3ds
Commit:      a3f5d12 "Add 3DS authentication support" by @alice
Workflow:    CI/CD Pipeline
Failed Job:  unit-tests (3m 24s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
[View Failed Run ↗]  [View Commit ↗]
```

**GitLab CI/CD 通知（额外字段）：**
- Pipeline ID、Stage 名称、失败原因、Artifact 链接

**✅ 优势：**
1. **直接关联代码**，Commit SHA/作者清晰，责任明确
2. **失败步骤（Failed Steps）** 清单，快速定位问题位置
3. 与代码 PR/MR 深度集成，构建→测试→部署全链路追踪

**❌ 劣势：**
1. 告警**不包含错误详情**（只有链接），需跳转查看日志
2. 无内嵌图表（无 test coverage 趋势、无 build time 趋势）
3. 无 AI 诊断（GitHub Copilot 暂未集成 Actions 告警分析）

---

### 5.3 Linear（工程项目管理）

**Incident 集成（Linear → Slack）：**
- Issue Title、Priority（Urgent/High/Medium/Low/No Priority）
- Status、Assignee、Team、Labels、Due Date
- Project、Milestone、Comments Count

**特色：**
- 极简主义设计，字段少但核心
- 支持 Slack 内快速创建 Issue / 更新状态
- Incident 与 Issue 自动关联（如部署失败 → Linear Issue）

**✅ 优势：**
1. **极简设计**，信息高度浓缩，降低噪音
2. **与工程师工作流天然贴合**（Issue Tracker + Incident）

**❌ 劣势：**
1. **监控/诊断能力几乎为零**，仅是项目管理工具
2. 缺少指标、图表、根因等技术信息

---

## 六、设计模式总结

### 6.1 常见信息字段归类（按出现频率排序）

| 排名 | 字段类别 | 具体字段 | 覆盖平台数 |
|------|----------|----------|-----------|
| 1 | **标题/描述** | 告警名称、摘要、描述 | 全部（10/10） |
| 2 | **时间戳** | 触发时间、持续时长、恢复时间 | 全部（10/10） |
| 3 | **严重级别** | severity/priority（P1-P5 或 Critical/High/Medium/Low） | 9/10 |
| 4 | **状态** | Triggered/Active/Acknowledged/Resolved | 9/10 |
| 5 | **来源/服务** | 服务名、主机名、应用名 | 9/10 |
| 6 | **负责人** | Assignee、on-call 人、团队 | 8/10 |
| 7 | **详情链接** | 深链跳转到详情页 | 8/10 |
| 8 | **触发条件/阈值** | 当前值、阈值、触发条件描述 | 8/10 |
| 9 | **环境/标签** | env、region、cluster、tags | 7/10 |
| 10 | **指标图/趋势图** | 内嵌折线图/快照 | 5/10（Datadog/Grafana/飞书） |
| 11 | **根因信息** | 根因描述、可能原因、Suspect Commits | 4/10（Datadog/Dynatrace/Sentry/PagerDuty-AI） |
| 12 | **影响面** | 受影响用户数、服务数 | 3/10（Datadog/Dynatrace/Sentry） |
| 13 | **处置建议** | Suggested Next Steps、Runbook 链接 | 4/10 |
| 14 | **置信度** | AI 推断置信度 | 0/10（所有平台均缺失！） |

---

### 6.2 常见交互模式

| 交互模式 | 代表平台 | 说明 |
|----------|---------|------|
| **Acknowledge（接单）** | PagerDuty、OpsGenie、ARMS | 最常见的一键操作 |
| **Resolve（关闭）** | PagerDuty、OpsGenie、ARMS | 处理完成关闭告警 |
| **Snooze/Mute（延迟/静默）** | OpsGenie、Datadog | 临时屏蔽，防止打扰 |
| **Escalate（升级）** | PagerDuty、OpsGenie | 上升到下一级处理 |
| **Add Note（备注）** | PagerDuty、Zendesk | 协作记录 |
| **跳转详情（深链）** | 全部 | 查看完整信息 |
| **状态更新回显** | 飞书、PagerDuty | 操作后卡片实时更新 |
| **AI 问答（自然语言）** | PagerDuty Advance、Dynatrace Copilot | 新兴交互模式 |
| **折叠/展开** | Teams Adaptive Card、ServiceNow | 控制信息密度 |
| **一键声明 Incident** | Datadog | 从告警直升 incident |

---

### 6.3 诊断卡片 vs 告警卡片的设计差异

| 维度 | 告警卡片（Alert Card） | 诊断卡片（Diagnosis Card） |
|------|----------------------|--------------------------|
| **核心问题** | "出了什么问题？" | "为什么出问题？" |
| **信息层次** | 单层（状态 + 数据） | 多层（症状→因果→根因→影响） |
| **图表** | 单指标时序图 | 多指标对比 + 因果关系图 |
| **内容生产者** | 规则引擎（阈值判断） | AI 引擎（推断分析） |
| **时效性** | 实时触发 | 需要分析时间（秒级~分钟级） |
| **互动方式** | 操作按钮（ACK/Resolve） | 追问（Copilot / @Bot 问答） |
| **置信度** | 不适用 | 应展示但普遍缺失 |
| **处置建议** | Runbook 链接 | AI 生成的具体步骤 |
| **代表产品** | CloudWatch / Grafana | Datadog Watchdog / Dynatrace Davis / Sentry AI |

---

### 6.4 AI 诊断卡片的设计趋势（2024-2026）

1. **三段式结构标准化**  
   `What happened`（发生了什么）→ `Possible Cause`（可能原因）→ `Suggested Next Steps`（建议步骤）  
   已被 Sentry、PagerDuty Advance 等平台采用，逐渐成为共识。

2. **置信度可视化（缺口机会）**  
   目前所有平台均**未显式展示 AI 推断的置信度**，用户无法判断 AI 有多确定。这是一个明显的设计缺口，尤其对 AIOps 场景至关重要。

3. **自然语言追问（Copilot 模式）**  
   Dynatrace Davis Copilot、PagerDuty Advance Assistant 已支持 `@AI what changed?` 式追问。告警卡片正在从"静态通知"向"对话入口"演进。

4. **根因可视化（因果链拓扑图）**  
   Dynatrace 的"根因 → 关键失效 → 影响面"三段式因果链可视化是最先进的设计，Datadog Watchdog RCA 类似但不展示拓扑图。

5. **跨信号关联（Correlation）**  
   告警 + 日志 + Trace + 部署事件的四维关联正在成为标准，Datadog/Dynatrace 均已实现，但 IM 卡片中的展示仍然简单。

6. **操作闭环（Action in Card）**  
   从"查看告警→跳转处理"向"卡片内一键处置"演进，飞书卡片 + 状态更新是最接近理想态的设计。

---

### 6.5 对告警诊断产品设计的核心启发（5条）

#### 启发 1：分层信息架构——"先摘要，后细节"
> **问题：** 当前多数告警通知把所有字段平铺展示，导致认知过载。  
> **启发：** 采用三层信息架构：  
> - **Layer 1（摘要层）**：5 秒能判断严重性的核心字段（标题 + 级别 + 状态 + 时间）  
> - **Layer 2（诊断层）**：可折叠展开的根因分析（根因 + 影响面 + 置信度）  
> - **Layer 3（操作层）**：ACK / Runbook / 跳转详情  

#### 启发 2：置信度是 AI 诊断卡片的必备字段
> **问题：** 所有现有平台的 AI 诊断卡片均**未展示置信度**，用户无法判断是否相信 AI 的推断。  
> **启发：** 在根因分析结论旁明确标注置信度（如 `可信度：高 85%` / `需人工确认`），帮助 on-call 快速决策"是否执行 AI 建议"。

#### 启发 3：状态更新回显是协作的关键
> **来源：** 飞书卡片的"操作后实时更新"设计。  
> **启发：** 告警卡片发送后，任何人的操作（认领/关闭/屏蔽）都应立即更新卡片状态，并显示"谁 × 何时 × 做了什么"，避免多人重复处理或不知道进展。

#### 启发 4：诊断结论用"结论先行"，而非"数据堆砌"
> **来源：** Dynatrace Davis 的"Problem Card"会直接给出"部署变更导致此次问题"的结论，而不是展示大量指标让人自己判断。  
> **启发：** AI 诊断卡片应该先给结论（`根因：v2.3.2 部署引入了内存泄漏`），再给证据（相关指标图、日志模式），而非相反。这符合"倒金字塔"信息设计原则。

#### 启发 5：卡片要成为"对话入口"而非"终态通知"
> **来源：** PagerDuty Advance、Dynatrace Copilot 的对话式 AI 设计。  
> **启发：** 高价值的告警诊断卡片不应该是"读完就关掉"的终态，而应该是一个**交互入口**：支持 `@AI 这个问题上次是怎么解决的？`、`@AI 当前影响了多少用户？` 等追问，让 AI 在卡片上下文中回答，极大提升排