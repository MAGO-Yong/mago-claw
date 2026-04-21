# X-RAY × RedLobi | Skills V2 全面升级 + xray-cli 正式发布 🚀

> 🔥 "CPU 飙高了，想看火焰图，要先开 Profiling、等采集、再下载、再分析……等你搞完，告警早处理完了"
> 😰 "AI Agent 跑了一条链路，想知道哪个 LLM 调用最慢、Token 烧了多少，翻 Langfuse 页面翻半天"
> 😤 "告警来了，想查事件详情、看规则配置、再看日志，要在三个 Skill 里来回切，还得记 event_id"
> 🤯 "服务出问题，不知道从哪下手——是上游打爆了？下游超时了？还是内部在炸？"

V1 上线以来，我们一直在做一件事：**把排障路径上每一个「需要手动搬运」的环节，变成 AI 直接可以做到的事。**

今天，V2 带来了三个大方向的更新：**5 个全新 Skill + 4 个存量 Skill 大升级 + xray-cli 正式发布**。

---

## 📦 V2 新增了什么

### 一、xray-cli 正式上线（2026-04-20）

**和 Skill 平级的全新入口——终端里的 XRay 全链路。**

Skills 解决的是「人对话 AI，AI 查 XRay」的场景。但研发同学还有另一个需求：**在 Coding Agent、CI/CD、脚本里让 AI 直接驱动 XRay**，不经过对话，不依赖人工搬运。

`xray-cli` 就是为此而生。**AI-first 设计**：默认非交互、结构化 JSON 输出、严格枚举校验，Agent 可直接驱动；需要人用时，加 `--human` 进入交互模式。

| 功能模块 | 能力 |
|---------|------|
| **告警管理** | `alarm event list` 查事件、按应用/严重度过滤、追踪处理状态 |
| **日志排查** | `log query` 结构化检索、`log download` 导出 CSV、自动关联 CAT messageId |
| **指标查询** | `metric` 查询 Prometheus 指标趋势，支持 PromQL 与预置模板 |
| **CAT 链路追踪** | `cat explore` 查趋势、`cat sample list` 定位失败请求、`cat timeline get` 完整调用链 |
| **大盘管理** | `dashboard create` 创建多面板大盘，支持 Prometheus + Cat 混合埋点 |
| **应用与服务** | `app` / `service` 查应用元信息，支持模糊匹配与拼写纠正 |

```bash
# 安装
npm install -g @xhs/xray-cli --registry=http://npm.devops.xiaohongshu.com:7001

# 登录
xray-cli auth login

# 直接用自然语言驱动
xray-cli agent ask "xrayaiagent 最近有什么告警"
```

> 想先体验？访问[在线演示页](https://xray-ai.devops.sit.xiaohongshu.com/xray-cli/)，无需安装，浏览器里直接跑。

---

### 二、5 个全新 Skill

#### 🔥 xray-performance-analysis · Java 性能深度分析

**再也不用手动跑 JStack、等火焰图、找 GC 日志。**

一句话触发，AI 帮你跑完整条 CPU 或内存分析路径：

- **CPU 分析**：指标总览 → 线程 CPU 快照 → JStack 锁诊断 → 火焰图热点定位
- **内存分析**：内存指标 → 线程内存快照 → GC 日志分析

> "xxx 服务 CPU 飙到 90% 了，帮我分析一下"
> "看看 yyy 服务有没有内存泄漏，GC 频率怎么样"
> "给我一张 xxx 服务最近 5 分钟的火焰图"

[前往安装](https://codewiz.devops.xiaohongshu.com/hub/xray-performance-analysis)

---

#### 🕸️ xray-topology · 服务拓扑关系查询

**不知道谁调我、我依赖了谁？一句话看清楚。**

支持三种拓扑模式：
- **服务拓扑**：查某服务的上下游依赖，含性能指标（QPS/成功率/耗时）
- **HTTP 入口拓扑**：按 URL 查上下游完整链路
- **CAT 拓扑**：降级场景下的树形拓扑

> "xxx 服务依赖了哪些下游，现在健康状态怎么样"
> "谁在调用 yyy 服务，流量多大"
> "这个 HTTP 入口 /api/v1/foo 的上下游关系是什么"

[前往安装](https://codewiz.devops.xiaohongshu.com/hub/xray-topology)

---

#### 🤖 xray-ai-trace-analysis · Langfuse AI 链路分析

**专为 AI/Agent 排障设计的 Skill——看清楚 LLM 调用链里发生了什么。**

当你的 Agent 出了问题，这个 Skill 能帮你：
- 重建 AI 调用链拓扑（哪个步骤调了哪个模型）
- 定位性能瓶颈（哪次 LLM 调用最慢）
- 分析 Token 消耗与成本分布
- 检测异常与报错
- 支持单条 trace、双 trace 对比、会话（session）多 trace 分析

> "分析一下这条 AI 链路，哪一步最慢"
> "这个 Agent session 的 Token 消耗怎么这么高"
> "帮我对比一下这两条 Langfuse trace，哪里不一样"

[前往安装](https://codewiz.devops.xiaohongshu.com/hub/xray-ai-trace-analysis)

---

#### 🔬 xray-exception-analysis · 异常堆栈聚类 + 错慢采样

**不再是一条条看日志——AI 帮你把异常归类，直接找最典型的那条。**

两条排查链路：
- **异常堆栈链路**：输入服务名 + 异常类型，获取聚类堆栈分布，自动关联 messageId 查完整 Logview
- **错慢采样链路**：按接口类型抓失败/最慢/成功样本的 messageId，直接进入 Logview 分析

> "帮我查 xxx 服务最近一小时的 TimeoutException 堆栈分布"
> "给我一个 yyy 服务 /api/v1/foo 接口最慢请求的 Logview"
> "看看 zzz 服务有什么异常，聚类一下"

[前往安装](https://codewiz.devops.xiaohongshu.com/hub/xray-exception-analysis)

---

#### 🩺 xray-service-analysis · 服务整体健康分析

**不知道从哪下手时，先问它。**

适合「知道服务出问题，但不知道是哪块」的场景。一次分析三个维度：
- 服务内部异常情况
- 本服务提供的接口健康状况
- 下游调用的健康状况

自动引导至日志、堆栈或链路的深度分析。

> "xxx 服务现在整体状况怎么样"
> "帮我看看 yyy 服务最近一小时有没有问题"

[前往安装](https://codewiz.devops.xiaohongshu.com/hub/xray-service-analysis)

---

### 三、存量 Skill 升级

#### 📋 xray-log-query · 日志查询大升级

**从"查应用日志"到"查所有类型日志"。**

V2 新增支持 6 类日志，不再只有通用业务日志：

| 日志类型 | 适用场景 |
|---------|---------|
| 通用业务日志（application） | 线上服务报错、异常排查 |
| 🆕 百川 Flink 作业日志（flink） | Flink 任务失败、数据延迟排查 |
| 🆕 Larc 训练任务日志（larc） | 模型训练任务异常 |
| 🆕 云原生事件日志（event） | K8s 事件、Pod 异常 |
| 🆕 云原生审计日志（audit） | 操作审计、权限变更追踪 |
| 🆕 接入层网关日志（rgw/edith） | 网关流量、接入层排查 |

同时新增**自然语言直查**模式——不用学 Lucene 语法，直接描述需求，AI 自动解析查询条件。

> "查一下 xxx Flink 任务最近的报错"
> "最近一小时 K8s 有没有 Pod 被驱逐的事件"
> "查 karen-gateway 最近的异常流量"

---

#### 🚨 xray-alarm · 告警四合一

**原来的 4 个告警 Skill 合并为一个，再也不用记用哪个。**

`alarm-rule-search`、`alarm-rule-detail`、`alarm-event-query`、`alarm-event-detail` 统一整合进 `xray-alarm`，一个 Skill 覆盖告警全链路：查事件列表 → 看事件详情 → 搜规则 → 查规则配置。

新增：支持按**产品线/业务线**粒度查询，不只限于 app 级别。

> "xxx 产品线昨天有哪些告警事件"
> "告警 event_id 171238413 的详情是什么"
> "xxx 服务有哪些 PQL 告警规则"

---

## 📊 V2 全量 Skill 一览

| Skill | 场景 | 安装 |
|-------|------|------|
| 📊 **xray-metric-query** | 指标查询：CPU/内存/JVM/RPC/Redis/MySQL/PQL/Cat | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-metric-query) |
| 📋 **xray-log-query** | 多类日志查询：业务/Flink/Larc/网关/云原生 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-log-query) |
| 🔗 **xray-trace-search** | Trace 批量搜索：ERROR/SLOW 双模式 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-trace-search) |
| 🔍 **xray-single-trace-analysis** | 单链路根因分析（TraceId） | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-single-trace-analysis) |
| 🔗 **xray-logview-analysis** | CAT Logview 调用链分析（MessageId） | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-logview-analysis) |
| 🔬 **xray-exception-analysis** | 异常堆栈聚类 + 错慢采样 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-exception-analysis) |
| 🩺 **xray-service-analysis** | 服务整体健康分析 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-service-analysis) |
| 🕸️ **xray-topology** | 服务拓扑关系查询 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-topology) |
| 🔥 **xray-performance-analysis** | Java CPU/内存深度性能分析 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-performance-analysis) |
| 🤖 **xray-ai-trace-analysis** | Langfuse AI 链路分析 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-ai-trace-analysis) |
| 🚨 **xray-alarm** | 告警全链路（事件+规则）四合一 🆕 | [安装](https://codewiz.devops.xiaohongshu.com/hub/xray-alarm) |

---

## 欢迎反馈

有问题、有反馈、有新场景想孵化？欢迎进群交流 🎉
