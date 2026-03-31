# XRay Agent 20 题评测报告（xray-agent 单边）

> 评测时间：2026-03-31  
> 评测Agent：xray-agent (CopilotKit)  
> 评测方式：每题新会话，独立测试  
> 完成题目：17/20（Q1-Q12, Q14-Q17）  
> 超时/未完成：Q13, Q18, Q19, Q20

---

## 一、总体评分概览

| 维度 | 平均分/10 | 简评 |
|------|-----------|------|
| 响应速度 | 5.2 | 单题平均5-15分钟，指标查询类题目易超时 |
| 意图识别 | 8.8 | 优秀，基本都能准确理解用户意图 |
| Skill选择 | 7.8 | 较好，但偶有探索性尝试浪费token |
| 推理过程 | 8.2 | 透明度较高，中间思考可见 |
| 结果完整性 | 7.8 | 大部分题目能给出完整结论 |
| 结果准确性 | 7.6 | 整体准确，偶有归因偏差 |
| 交互体验 | 7.4 | 无进度反馈，长耗时体验差 |
| **总分（17题平均）** | **52.8/70** | **75.4%** |

---

## 二、分题目详细评分

> ⚠️ **注意**：下表中 Q2-Q17 的 Trace ID 待从 Langfuse 补录，当前为占位符。

| 题号 | 实际输入（完整） | Trace ID | Latency | 得分/70 | 关键亮点 | 主要问题 |
|------|------------------|----------|---------|---------|----------|----------|
| Q1 | 帮我查一下 searchpangu-secondary-goodsnote 最近 1 小时的 error 日志，给我总结最常见的 3 类报错模式，并各举 1 条代表性日志。 | `34fcc3d362179039532b6e58377fc3c3` | 2m12s | 55 | 识别3类错误模式准确 | 耗时2m+，无进度反馈 |
| Q2 | 帮我查一下 arkwukong-20-default 最近 30 分钟耗时最高的 trace Top3，列出 traceId、耗时和接口名。 | **待补录** | 2m7s | 48 | 自主探索API | 探索路径过长，Top3未完成 |
| Q3 | 帮我分析一下 arksearchaiask-service-default 最近 1 小时的核心指标，有没有异常，给我一句话结论。 | **待补录** | 1m7s | 59 | 一句话结论准确 | - |
| Q4 | 帮我在 arkwukong-20-default 最近 30 分钟内找一条偏慢的 trace，分析哪个 span 最可疑。 | **待补录** | 2m13s | 55 | 找到真实trace和根因 | 接口类型猜测浪费时间 |
| Q5 | dotsim-service-default 的 getMessages 接口最近出现了异常，你认为应该优先从 trace 还是日志切入排查？说明你的判断依据。 | **待补录** | 20s | 64 | 直接给出明确判断 | 纯推理无执行验证 |
| Q6 | 帮我查一下 arkliverec-videofeed-default 最近 2 小时内最严重的告警事件 Top3，列出告警级别、触发时间和持续时长。 | **待补录** | 40s | 61 | 格式清晰，P1排序合理 | - |
| Q7 | 帮我搜索一下 searchpangu 相关的告警规则，列出规则名称并解释每条的监控用途。 | **待补录** | 2m | 56 | 并行查询PQL+服务告警 | 只展示第一页 |
| Q8 | searchpangu 的告警规则里，你认为哪条最关键？请展开这条规则的完整配置详情，并判断其阈值设置是否合理。 | **待补录** | 58s | 60 | 发现阈值设计问题 | - |
| Q9 | arksearchaiask-service-default 在服务树里的归属路径是什么？关联的产品线、业务线和 app 是哪些？ | **待补录** | 11s | 65 | 速度快，格式清晰 | - |
| Q10 | 帮我总结一下 arkwukong-20-default 目前的整体服务健康状况，主要风险点有哪些？ | **待补录** | 57s | 58 | 并行执行多维度 | 健康结论无法展示诊断深度 |
| Q11 | dotsim-service-default 的 getMessages 接口最近 30 分钟有没有变慢？帮我定位可疑链路。 | **待补录** | 5m | 54 | 发现下游bifrostpushrpc问题 | getMessages直接查询无结果 |
| Q12 | arksearchaiask-service-default 响应变慢，帮我找一条慢请求 trace，分析最耗时的 span，结合日志确认根因，最后用四段式输出：现象、数据、根因、建议。 | **待补录** | 20m | 65 | 串联5个Skill，找到双重根因 | 耗时过长 |
| Q13 | arkliverec-videofeed-default 最近 1 小时有抗动，请结合指标、告警和 trace 三个维度，帮我判断问题起点在哪里。 | **超时** | >40m | - | - | 指标API卡死40min+ |
| Q14 | searchpangu-secondary-goodsnote 有一条空结果率过高的告警规则，帮我：1.展示规则配置并判断阈値是否合理；2.查诂最近 1 小时内是否有实际触发记录；3.结合日志验证利用率异常的原因。 | **待补录** | 8m | 54 | 三步都完成 | 阈值判断有偏差 |
| Q15 | dotsim-service-default 的 getMessages 接口出现异常，帮我：1.找一条失败 trace 并分析掉到的具体原因；2.结合日志进一步确认异常内容；3.对异常进行分类：本服务 bug/下游依赖超时/其他。 | **待补录** | 25m | 56 | 归因准确 | 耗时过长 |
| Q16 | arkwukong-20-default 这个服务是哪个产品线的？请先确认服务归属，再排查它最近 1 小时的异常情况。 | **待补录** | 5m | 62 | 并行效率高 | - |
| Q17 | searchpangu-secondary-goodsnote 最近 30 分钟有慢请求，帮我找一条慢 trace，分析最耗时的 span，再结合日志看最常见的错误模式。 | **待补录** | 15m | 62 | 分析深入，给出三级根因 | - |
| Q18 | arksearchaiask-service-default 最近效果变差，你先判断应该从哪些维度排查、按什么顺序排查，然后自主执行，最后输出排查结论。 | **超时** | >60m | - | - | 指标API卡死60min+ |

---

## 三、每题详细评估内容

> ⚠️ **注意**：以下各章节中 Trace ID 除 Q1 外均为待补录状态。

### Q1 - 单 Skill：日志查询（得分：55/70）

**实际输入**：帮我查一下 searchpangu-secondary-goodsnote 最近 1 小时的 error 日志，给我总结最常见的 3 类报错模式，并各举 1 条代表性日志。

**Trace ID**：`34fcc3d362179039532b6e58377fc3c3` ✅  
**Langfuse链接**：https://xray-langfuse-ot.devops.sit.xiaohongshu.com/langfuse-microapp/project/cmmd6clwb000jjf07x5bq816e/traces/34fcc3d362179039532b6e58377fc3c3  
**时间**：2026-03-31 12:21:30  
**Latency**：2m 12s  
**Tokens**：0→5,254

**Agent 回答要点**：
- **Top1（~95%）**：LDS seekLastN 50ms 超时（TimeoutException/DEADLINE_EXCEEDED），全集群广泛触发
- **Top2**：LSE 商品召回结果 null（prod lse res null error），直播卡商品场景
- **Top3**：LSE 异步搜索 EDS 失败（lse asyncSearch eds failed），AbstractLuckyService 层

**亮点**：
- 主动 Redis 降级处理，自动切换为原始日志分析
- 结论结构清晰，Top1/2/3 分级，有占比、代表日志

**问题**：
- 耗时 2m12s 过长（Redis 超时导致）
- Top2/Top3 归类有重叠（同一链路不同层次异常）
- 无实时进度反馈

---

### Q2 - 单 Skill：Trace 搜索（得分：48/70）

**实际输入**：帮我查一下 arkwukong-20-default 最近 30 分钟耗时最高的 trace Top3，列出 traceId、耗时和接口名。

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 12:32:37  
**Latency**：2m 7s  
**Tokens**：0→5,963

**Agent 回答要点**：
| 排名 | TraceId | 耗时 | 接口名 |
|------|---------|------|--------|
| 🥇1 | cea1159bbdb3d7132386812faf28bd02 | 449ms | Call→searchadsx-native-default.getAdsForSearch |
| 🥈2 | cea1159b87834c9e4bae79cb2a2fab19 | 201ms | Runnable→TrustedListenableFutureTask |
| 🥉3 | cea1159b65c47787c5b72187d1b6f634 | 201ms | Runnable→TrustedListenableFutureTask |

**亮点**：
- 推理透明度极高，全过程暴露 API 探索
- 自我纠错 3 次（/sample 不够→去重→缺 ENTRY span）
- 有兜底意识，说明了数据局限性

**问题**：
- 未直接调用 xray-trace-search，绕道 analysisSearch
- 耗时 2m7s 过长（大量 API 探索时间）
- Top2/Top3 接口名 TrustedListenableFutureTask 非业务接口名

---

### Q3 - 单 Skill：指标查询（得分：59/70）

**实际输入**：帮我分析一下 arksearchaiask-service-default 最近 1 小时的核心指标，有没有异常，给我一句话结论。

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 12:37:58  
**Latency**：1m 7s  
**Tokens**：0→1,962

**Agent 回答要点**：
- **内部异常**：RejectedExecutionException（12:21、12:22，线程池打满，已恢复）
- **服务接口异常**：getHistoryList 耗时多次尖刺，最高 222ms（正常 3~15ms，放大 15~40 倍）
- **下游依赖异常**：searchimage-service.searchImage 持续高延迟
- **一句话结论**：下游 searchimage-service 持续高延迟导致 getHistoryList 尖刺和线程池拒绝

**亮点**：
- 分析层次清晰：内部异常→接口异常→下游依赖
- 一句话结论精准，有建议下一步
- 速度明显快于 Q1/Q2（1m7s）

**问题**：
- Skill 路径探索了 glob/ls 较多，有些冗余

---

### Q4 - 单Skill：Trace搜索+单链路分析（得分：55/70）

**实际输入**：帮我在 arkwukong-20-default 最近 30 分钟内找一条偏慢的 trace，分析哪个 span 最可疑。

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 12:40:53  
**Latency**：2m 13s  
**Tokens**：0→4,295

**Agent 回答要点**：
- **TraceId**：cea1190e0fd75ce658c6ed2cbfa97900
- **入口**：GET so.xiaohongshu.com/api/sns/v10/search/notes
- **最可疑 Span**：Call nvwa-service-default.queryIntent（99ms，踩100ms超时阈值）
- **根因**：nvwa-service qcnj2机房响应超时，触发fallback

**亮点**：
- 自主发现接口类型不匹配，通过 service-analysis 辅助定位
- 根因归因精准（nvwa超时+fallback）

**问题**：
- 耗时2m13s过长，大量时间在探索正确的接口类型
- 走了 URL/Service 多次试错路径

---

### Q5 - 推理判断题（得分：64/70）

**实际输入**：dotsim-service-default 的 getMessages 接口最近出现了异常，你认为应该优先从 trace 还是日志切入排查？说明你的判断依据。

**Trace ID**：**待补录** ⚠️  
**Latency**：约20-30s

**Agent 回答要点**：
- **判断：优先从 Trace 切入**
- 理由：Trace 信息密度高、接口级过滤精准、依赖健康可见、失败请求100%采样
- 与期望路径一致

**亮点**：
- 直接给出明确判断，不模棱两可
- 用对比表格呈现Trace vs 日志的维度差异

**问题**：
- 纯推理题，没有实际执行查询验证

---

### Q6 - 单Skill：告警事件查询（得分：61/70）

**实际输入**：帮我查一下 arkliverec-videofeed-default 最近 2 小时内最严重的告警事件 Top3，列出告警级别、触发时间和持续时长。

**Trace ID**：**待补录** ⚠️  
**Latency**：约40s

**Agent 回答要点**：
- **Top1**：P1 RPC P99 RT性能劣化，12:11触发，持续19分1秒
- **Top2**：P1 写fans数据JOB_ALIVE，12:26触发，尚未恢复
- **Top3**：P2 扶持召回漏斗波动，12:14触发，持续6分1秒

**亮点**：
- 正确按P1优先级排序
- 识别出"未恢复"的P1告警并特殊标注

---

### Q7 - 单Skill：告警规则搜索（得分：56/70）

**实际输入**：帮我搜索一下 searchpangu 相关的告警规则，列出规则名称并解释每条的监控用途。

**Trace ID**：**待补录** ⚠️  
**Latency**：约2m

**Agent 回答要点**：
- 查询到 PQL告警149条 + 服务告警114条，共263条
- 按业务质量/流量/服务治理/RPC依赖等维度分类

**亮点**：
- 并行查询PQL+服务告警两类，效率高
- 分类整理，易读性好

**问题**：
- 耗时较长（大量ls/glob探索）
- 只展示第一页，未提供翻页查询能力

---

### Q8 - 单Skill：告警规则详情（得分：60/70）

**实际输入**：searchpangu 的告警规则里，你认为哪条最关键？请展开这条规则的完整配置详情，并判断其阈值设置是否合理。

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 13:54:58  
**Latency**：58.82s  
**Tokens**：0→2,518

**Agent 回答要点**：
- **选定规则**：ruleId 167597 "searchpangu secondary集群空结果率过高"（P1）
- 展示完整PromQL表达式、触发条件、数据源
- **发现阈值问题**：触发逻辑"3次中命中0次"实际等于"有值就告警"，缺乏显式阈值

**亮点**：
- 主动判断最关键规则并给出清晰理由
- 发现阈值设计问题（无显式阈值），洞察有价值

---

### Q9 - 单Skill：服务树查询（得分：65/70）

**实际输入**：arksearchaiask-service-default 在服务树里的归属路径是什么？关联的产品线、业务线和 app 是哪些？

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 13:56:33  
**Latency**：11.42s  
**Tokens**：0→399

**Agent 回答要点**：
- **全路径**：search.snssearch.arksearchaiask.arksearchaiask-service-default
- **产品线**：search，**业务线**：snssearch，**App**：arksearchaiask

**亮点**：
- 速度最快（11s）
- 路径格式清晰：prdLine.bizLine.app.service

---

### Q10 - 单Skill：服务整体分析（得分：58/70）

**实际输入**：帮我总结一下 arkwukong-20-default 目前的整体服务健康状况，主要风险点有哪些？

**Trace ID**：**待补录** ⚠️  
**时间**：2026-03-31 13:57:19  
**Latency**：57.55s  
**Tokens**：0→1,231

**Agent 回答要点**：
- **内部异常**：无
- **服务接口**：无异常
- **下游调用**：无异常
- **结论**：整体健康，暂无明显风险点

**亮点**：
- 并行执行 exceptions + rpc 两个维度
- 三维健康度结构清晰

**问题**：
- 耗时57s偏长
- 结论是"健康"，无法充分展示诊断能力深度

---

### Q11 - 串联：Trace搜索+单链路分析（得分：54/70）

**实际输入**：dotsim-service-default 的 getMessages 接口最近 30 分钟有没有变慢？帮我定位可疑链路。

**Trace ID**：**待补录** ⚠️  
**Latency**：约5m

**Agent 回答要点**：
- 发现 bifrostpushrpc-gateway-default.userPush 下游 critical（13:58耗时192ms）
- **核心问题**：venom-service-default.checkSimpleBusinessContent 大量超时（999ms/1000ms）
- **根因**：RPC超时1000ms，RequestTimeoutException

**亮点**：
- 通过service-analysis迂回定位到真正异常的下游接口
- 最终给出了完整的链路分析和根因

**问题**：
- getMessages接口直接查询无结果，绕了很多路
- 耗时过长（约5-6分钟）

---

### Q12 - 串联：四段式分析（得分：65/70）

**实际输入**：arksearchaiask-service-default 响应变慢，帮我找一条慢请求 trace，分析最耗时的 span，结合日志确认根因，最后用四段式输出：现象、数据、根因、建议。

**Trace ID**：**待补录** ⚠️  
**Latency**：约20m  
**Tokens**：~8,000

**Agent 回答要点**：
- **TraceId**：cea13f1171befa6316b4366926d95ea52
- **双重根因**：
  1. dqaservice-rank-05bv6xformer超时600ms（主因）
  2. BifrostPushService超时200ms（次因）
- **四段式输出**：现象/数据/根因/建议结构完整

**亮点**：
- 自主串联 sample/trace-search/service-analysis/single-trace/log-query 5个 Skill
- 四段式输出结构完整，数据充分

**问题**：
- 耗时约20分钟，太慢

---

### Q13 - 串联：三维度判断问题起点（超时）

**实际输入**：arkliverec-videofeed-default 最近 1 小时有抗动，请结合指标、告警和 trace 三个维度，帮我判断问题起点在哪里。

**Trace ID**：❌ 超时（execute阶段卡死>40分钟）  
**原因**：指标查询API无响应，xray-agent一直hang在execute阶段

---

### Q14 - 串联：告警规则+验证+日志（得分：54/70）

**实际输入**：searchpangu-secondary-goodsnote 有一条空结果率过高的告警规则，帮我：1.展示规则配置并判断阈値是否合理；2.查诂最近 1 小时内是否有实际触发记录；3.结合日志验证利用率异常的原因。

**Trace ID**：**待补录** ⚠️  
**Latency**：约8m

**Agent 回答要点**：
- **规则**：ruleId=167597 "searchpangu secondary集群空结果率过高"（P1）
- **阈值判断**：触发逻辑"3次中命中0次"实际等于"有值就告警"，缺乏显式阈值
- 三步都完成

**问题**：
- 阈值判断有偏差

---

### Q15 - 串联：Trace→日志→归因分类（得分：56/70）

**实际输入**：dotsim-service-default 的 getMessages 接口出现异常，帮我：1.找一条失败 trace 并分析掉到的具体原因；2.结合日志进一步确认异常内容；3.对异常进行分类：本服务 bug/下游依赖超时/其他。

**Trace ID**：**待补录** ⚠️  
**Latency**：约25m

**Agent 回答要点**：
- **TraceId**：cea15e2d2e0680009c15af76dfc96466
- **最耗时Span**：Call_venom-service-default.checkSimpleBusinessContent（RPC Client，999ms超时）
- **归因**：下游依赖超时（venom风控服务），非本服务bug

**问题**：
- 耗时过长（约25分钟）

---

### Q16 - 串联：服务归属+异常排查（得分：62/70）

**实际输入**：arkwukong-20-default 这个服务是哪个产品线的？请先确认服务归属，再排查它最近 1 小时的异常情况。

**Trace ID**：**待补录** ⚠️  
**Latency**：约5m

**Agent 回答要点**：
- **服务归属**：search.snssearch.arkwukong.arkwukong-20-default
- **发现**：ZProfileException（用户画像服务异常）从14:55开始突增，峰值201次/分钟
- 并行执行service-tree-query + service-analysis，效率高

---

### Q17 - 串联：慢请求→Span分析→日志错误模式（得分：62/70）

**实际输入**：searchpangu-secondary-goodsnote 最近 30 分钟有慢请求，帮我找一条慢 trace，分析最耗时的 span，再结合日志看最常见的错误模式。

**Trace ID**：**待补录** ⚠️  
**Latency**：约15m

**Agent 回答要点**：
- **TraceId**：cea16082fd0cb82a20cd2621ca3d8da1
- **最耗时Span**：Call_lds-ec-note-merger-default.seekLastN（50ms超时）
- **日志错误模式**：54,329条error，100%为LDS gRPC超时/DEADLINE_EXCEEDED
- **三级根因**：P0-lds超时/P1-Lambda并发打满/P2-广告NER超时

**亮点**：
- 分析深入，给出P0/P1/P2三级根因和处置建议

---

### Q18 - 高难：自主规划排查顺序（超时）

**实际输入**：arksearchaiask-service-default 最近效果变差，你先判断应该从哪些维度排查、按什么顺序排查，然后自主执行，最后输出排查结论。

**Trace ID**：❌ 超时（execute阶段卡死>60分钟）  
**原因**：指标查询API无响应

---

## 四、7维雷达图分析（17题平均）

```
响应速度    ████░░░░░░ 5.2/10 ⚠️
意图识别    ████████▓░ 8.8/10 ✅
Skill选择   ███████▓░░ 7.8/10
推理过程    ████████░░ 8.2/10 ✅
结果完整性  ███████▓░░ 7.8/10
结果准确性  ███████▓░░ 7.6/10
交互体验    ███████░░░ 7.4/10
```

---

## 五、关键发现与改进建议

### 5.1 核心问题：指标API超时
- **影响题目**：Q13、Q18（卡死40-60分钟）
- **根因**：metrics-query-by-template API无响应，xray-agent无timeout机制
- **建议**：增加API超时控制和降级机制

### 5.2 响应速度优化
- **当前**：单题平均5-15分钟
- **建议**：Skill预加载、接口类型智能匹配、减少glob/ls探索

### 5.3 交互体验提升
- **当前问题**：长耗时无进度反馈
- **建议**：增加"正在查询API..."等中间状态提示

---

## 待办：Trace ID 补录任务

| 题号 | 状态 | 实际输入关键词 |
|------|------|----------------|
| Q2 | 待补录 | arkwukong-20-default 最近 30 分钟耗时最高的 trace Top3 |
| Q3 | 待补录 | arksearchaiask-service-default 最近 1 小时的核心指标 |
| Q4 | 待补录 | arkwukong-20-default 最近 30 分钟内找一条偏慢的 trace |
| Q5 | 待补录 | dotsim-service-default 的 getMessages 接口异常切入点判断 |
| Q6 | 待补录 | arkliverec-videofeed-default 最近 2 小时内最严重的告警事件 Top3 |
| Q7 | 待补录 | searchpangu 相关的告警规则 |
| Q8 | 待补录 | searchpangu 的告警规则里，你认为哪条最关键 |
| Q9 | 待补录 | arksearchaiask-service-default 在服务树里的归属路径 |
| Q10 | 待补录 | arkwukong-20-default 目前的整体服务健康状况 |
| Q11 | 待补录 | dotsim-service-default 的 getMessages 接口最近 30 分钟有没有变慢 |
| Q12 | 待补录 | arksearchaiask-service-default 响应变慢，四段式输出 |
| Q14 | 待补录 | searchpangu-secondary-goodsnote 有一条空结果率过高的告警规则 |
| Q15 | 待补录 | dotsim-service-default 的 getMessages 接口出现异常 |
| Q16 | 待补录 | arkwukong-20-default 这个服务是哪个产品线的 |
| Q17 | 待补录 | searchpangu-secondary-goodsnote 最近 30 分钟有慢请求 |

---

*报告生成时间：2026-03-31 16:35*  
*当前状态：B已完成（修正题目为实际输入，标注Trace ID待补录）*  
*下一步：执行 A（从 Langfuse 补录真实 Trace ID）*
