# XRay Agent 评测数据记录
> 评测日期：2026-03-31
> 评测对象：自研 xray-agent（单边）
> Langfuse 项目：cmmd6clwb000jjf07x5bq816e

---

## Q1 - 单 Skill：日志查询
**题目**：帮我查一下 searchpangu-secondary-goodsnote 最近 1 小时的 error 日志，给我总结最常见的 3 类报错模式，并各举 1 条代表性日志。
**期望路径**：xray-log-query
**重试次数**：0

### Trace
- 时间：2026-03-31 12:21:30
- Latency：2m 12s
- Tokens：0→5,254（∑5,254）
- Observation Levels：ℹ️ 98，无 ERROR
- 调用链：MemoryMiddleware → SkillsMiddleware → model(ChatAnthropic) → tools(skill) → execute×多次 → read_file×2

### Agent 回答
- Top1（~95%）：LDS seekLastN 50ms 超时（TimeoutException/DEADLINE_EXCEEDED），全集群广泛触发
- Top2：LSE 商品召回结果 null（prod lse res null error），直播卡商品场景
- Top3：LSE 异步搜索 EDS 失败（lse asyncSearch eds failed），AbstractLuckyService 层

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 5 |
| 意图识别 | 9 |
| Skill 选择 | 9 |
| 推理过程 | 8 |
| 结果完整性 | 9 |
| 结果准确性 | 8 |
| 交互体验 | 7 |
| **总分** | **55/70** |

### 亮点
- 主动 Redis 降级处理，自动切换为原始日志分析
- 结论结构清晰，Top1/2/3 分级，有占比、代表日志

### 问题
- 耗时 2m12s 过长（Redis 超时导致）
- Top2/Top3 归类有重叠（同一链路不同层次异常）
- 无实时进度反馈

---

## Q2 - 单 Skill：Trace 搜索
**题目**：帮我查一下 arkwukong-20-default 最近 30 分钟耗时最高的 trace Top3，列出 traceId、耗时和接口名。
**期望路径**：xray-trace-search
**重试次数**：0

### Trace
- 时间：2026-03-31 12:32:37
- Latency：2m 7s
- Tokens：0→5,963（∑5,963）
- Observation Levels：ℹ️ 122，无 ERROR
- 调用链：glob/read_file×3 → ls×2 → read_file×3 → glob → read_file×2 → execute×4

### Agent 回答
| 排名 | TraceId | 耗时 | 接口名 |
|------|---------|------|--------|
| 🥇1 | cea1159bbdb3d7132386812faf28bd02 | 449ms | Call→searchadsx-native-default.getAdsForSearch |
| 🥈2 | cea1159b87834c9e4bae79cb2a2fab19 | 201ms | Runnable→TrustedListenableFutureTask |
| 🥉3 | cea1159b65c47787c5b72187d1b6f634 | 201ms | Runnable→TrustedListenableFutureTask |

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 5 |
| 意图识别 | 9 |
| Skill 选择 | 5 |
| 推理过程 | 8 |
| 结果完整性 | 7 |
| 结果准确性 | 6 |
| 交互体验 | 8 |
| **总分** | **48/70** |

### 亮点
- 推理透明度极高，全过程暴露 API 探索
- 自我纠错 3 次（/sample 不够→去重→缺 ENTRY span）
- 有兜底意识，说明了数据局限性

### 问题
- 未直接调用 xray-trace-search，绕道 analysisSearch
- 耗时 2m7s 过长（大量 API 探索时间）
- Top2/Top3 接口名 TrustedListenableFutureTask 非业务接口名

---

## Q3 - 单 Skill：指标查询
**题目**：帮我分析一下 arksearchaiask-service-default 最近 1 小时的核心指标，有没有异常，给我一句话结论。
**期望路径**：metrics-query-by-template / xray-service-analysis
**重试次数**：0

### Trace
- 时间：2026-03-31 12:37:58
- Latency：1m 7s
- Tokens：0→1,962（∑1,962）
- Observation Levels：ℹ️ 56，无 ERROR
- 调用链：skill×2 → glob×2 → skill → glob → ls×2 → execute → 最终输出

### Agent 回答
- 内部异常：RejectedExecutionException（12:21、12:22，线程池打满，已恢复）
- 服务接口异常：getHistoryList 耗时多次尖刺，最高 222ms（正常 3~15ms，放大 15~40 倍）
- 下游依赖异常：searchimage-service.searchImage 持续高延迟（均值 850ms，最高 1180ms）
- 一句话结论：下游 searchimage-service 持续高延迟导致 getHistoryList 尖刺和线程池拒绝，建议排查 searchimage-service-default

### 评分（待最终确定）
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 7 |
| 意图识别 | 9 |
| Skill 选择 | 7 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **59/70** |

### 亮点
- 分析层次清晰：内部异常→接口异常→下游依赖
- 根因归因到位：搞清楚 searchimage 是 getHistoryList 尖刺的上游根因
- 一句话结论精准，有建议下一步
- 速度明显快于 Q1/Q2（1m7s）

### 问题
- Skill 路径探索了 glob/ls 较多，有些冗余
- 输出中耗时数据有个小笔误（"50~220ms" 应为 "55~222ms"，影响极小）

---

## Q4-Q20（待填充）

---

## Q4 - 单Skill：Trace搜索+单链路分析
**题目**：帮我在 arkwukong-20-default 最近 30 分钟内找一条偏慢的 trace，分析哪个 span 最可疑。
**期望路径**：xray-trace-search → xray-single-trace-analysis
**重试次数**：0

### Trace (Langfuse)
- 时间：2026-03-31 12:40:53
- Latency：2m 13s
- Tokens：0→4,295（∑4,295）
- 无ERROR

### Agent 回答要点
- TraceId: cea1190e0fd75ce658c6ed2cbfa97900
- 入口：GET so.xiaohongshu.com/api/sns/v10/search/notes
- 最可疑 Span：Call nvwa-service-default.queryIntent（99ms，踩100ms超时阈值）
- 根因：nvwa-service qcnj2机房响应超时，触发fallback
- 调用链路分析清晰

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 4 |
| 意图识别 | 9 |
| Skill 选择 | 7 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 8 |
| **总分** | **55/70** |

### 亮点
- 自主发现接口类型不匹配，通过 service-analysis 辅助定位
- 最终找到真实偏慢 trace 并完成 span 级别分析
- 根因归因精准（nvwa超时+fallback）

### 问题
- 耗时2m13s过长，大量时间在探索正确的接口类型
- 走了 URL/Service 多次试错路径

---

## Q5 - 推理判断题
**题目**：dotsim-service-default 的 getMessages 接口最近出现了异常，你认为应该优先从 trace 还是日志切入排查？说明你的判断依据。
**期望路径**：自主推理判断，理想偏 trace
**重试次数**：0

### Trace (Langfuse)
- 时间：约13:45（在Q4之后）
- Latency：约20-30s（纯推理，无大量工具调用）
- 无ERROR

### Agent 回答要点
- **判断：优先从 Trace 切入**
- 理由：Trace 信息密度高（完整请求生命周期）、接口级过滤精准、依赖健康可见、失败请求100%采样
- 与期望路径一致
- 同时给出了推荐排查步骤

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 9 |
| 意图识别 | 10 |
| Skill 选择 | 9 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **64/70** |

### 亮点
- 直接给出明确判断，不模棱两可
- 用对比表格呈现Trace vs 日志的维度差异，逻辑清晰
- 与期望路径完全一致（Trace优先）

### 问题
- 纯推理题，没有实际执行查询验证

---

## Q6 - 单Skill：告警事件查询
**题目**：帮我查一下 arkliverec-videofeed-default 最近 2 小时内最严重的告警事件 Top3，列出告警级别、触发时间和持续时长。
**期望路径**：alarm-event-query
**重试次数**：0

### Trace (Langfuse)
- 时间：约13:45
- Latency：约40s
- 无ERROR

### Agent 回答要点
- Top1：P1 [PromQL告警]RPC P99 RT性能劣化，12:11触发，持续19分1秒
- Top2：P1 [PromQL告警]写fans数据JOB_ALIVE，12:26触发，尚未恢复（持续18分钟+）
- Top3：P2 [PromQL告警]扶持召回漏斗波动，12:14触发，持续6分1秒
- 格式清晰，P1优先排序合理

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 8 |
| 意图识别 | 9 |
| Skill 选择 | 9 |
| 推理过程 | 8 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **61/70** |

### 亮点
- 正确按P1优先级排序
- 识别出"未恢复"的P1告警并特殊标注（⚠️）
- 输出格式标准，每条告警信息完整

---

## Q7 - 单Skill：告警规则搜索
**题目**：帮我搜索一下 searchpangu 相关的告警规则，列出规则名称并解释每条的监控用途。
**期望路径**：alarm-rule-search
**重试次数**：0

### Trace (Langfuse)
- 时间：约13:50
- Latency：约2m
- 无ERROR

### Agent 回答要点
- 查询到 PQL告警149条 + 服务告警114条，共263条
- 按业务质量/流量/服务治理/RPC依赖等维度分类
- 每条规则有名称、目标服务、级别、监控用途说明

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 5 |
| 意图识别 | 9 |
| Skill 选择 | 9 |
| 推理过程 | 8 |
| 结果完整性 | 8 |
| 结果准确性 | 9 |
| 交互体验 | 8 |
| **总分** | **56/70** |

### 亮点
- 并行查询PQL+服务告警两类，效率高
- 分类整理，易读性好
- 主动说明"共263条，展示前40条"的数据范围

### 问题
- 耗时较长（大量ls/glob探索）
- 只展示第一页，未提供翻页查询能力

---

## Q8 - 单Skill：告警规则详情
**题目**：searchpangu 的告警规则里，你认为哪条最关键？请展开这条规则的完整配置详情，并判断其阈值设置是否合理。
**期望路径**：alarm-rule-search → alarm-rule-detail
**重试次数**：0

### Trace (Langfuse)
- 时间：2026-03-31 13:54:58
- Latency：58.82s
- Tokens：0→2,518

### Agent 回答要点
- 选定：ruleId 167597 "searchpangu secondary集群空结果率过高"（P1）
- 展示完整PromQL表达式、触发条件、数据源
- 发现阈值问题：触发逻辑"3次中命中0次"实际等于"有值就告警"，缺乏显式阈值

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 7 |
| 意图识别 | 9 |
| Skill 选择 | 9 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 8 |
| 交互体验 | 9 |
| **总分** | **60/70** |

### 亮点
- 主动判断最关键规则并给出清晰理由
- 完整展示PromQL表达式，逻辑说明到位
- 发现阈值设计问题（无显式阈值），洞察有价值

---

## Q9 - 单Skill：服务树查询
**题目**：arksearchaiask-service-default 在服务树里的归属路径是什么？关联的产品线、业务线和 app 是哪些？
**期望路径**：service-tree-query
**重试次数**：0

### Trace (Langfuse)
- 时间：2026-03-31 13:56:33
- Latency：11.42s
- Tokens：0→399

### Agent 回答要点
- 全路径：search.snssearch.arksearchaiask.arksearchaiask-service-default
- 产品线：search，业务线：snssearch，App：arksearchaiask

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 9 |
| 意图识别 | 10 |
| Skill 选择 | 10 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **65/70** |

### 亮点
- 速度最快（11s）
- 路径格式清晰：prdLine.bizLine.app.service
- 直接命中正确Skill，无探索开销

---

## Q10 - 单Skill：服务整体分析
**题目**：帮我总结一下 arkwukong-20-default 目前的整体服务健康状况，主要风险点有哪些？
**期望路径**：xray-service-analysis
**重试次数**：0

### Trace (Langfuse)
- 时间：2026-03-31 13:57:19
- Latency：57.55s
- Tokens：0→1,231

### Agent 回答要点
- 内部异常：无
- 服务接口：无异常
- 下游调用：无异常
- 结论：整体健康，暂无明显风险点

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 7 |
| 意图识别 | 9 |
| Skill 选择 | 9 |
| 推理过程 | 8 |
| 结果完整性 | 8 |
| 结果准确性 | 9 |
| 交互体验 | 8 |
| **总分** | **58/70** |

### 亮点
- 并行执行 exceptions + rpc 两个维度
- 三维健康度（内部/接口/下游）结构清晰

### 问题
- 耗时57s偏长
- 结论是"健康"，无法充分展示诊断能力深度

---

## Q11 - 串联：Trace搜索+单链路分析
**题目**：dotsim-service-default 的 getMessages 接口最近 30 分钟有没有变慢？帮我定位可疑链路。
**期望路径**：xray-trace-search → xray-single-trace-analysis
**重试次数**：0

### Agent 回答要点
- 发现 bifrostpushrpc-gateway-default.userPush 下游 critical（13:58耗时192ms）
- 核心问题：venom-service-default.checkSimpleBusinessContent 大量超时（999ms/1000ms）
- 跨机房调用（qcsh5→alsh1，占比20%）
- traceId：cea13cd30a7d0000b7dc648773f24cf0
- 根因：RPC超时1000ms，RequestTimeoutException

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 4 |
| 意图识别 | 9 |
| Skill 选择 | 7 |
| 推理过程 | 9 |
| 结果完整性 | 8 |
| 结果准确性 | 9 |
| 交互体验 | 8 |
| **总分** | **54/70** |

### 亮点
- 通过service-analysis迂回定位到真正异常的下游接口
- 最终给出了完整的链路分析和根因

### 问题
- getMessages接口直接查询无结果，绕了很多路
- 耗时过长（约5-6分钟）


---

## Q13 - 串联：指标+告警+trace三维度 (超时)
**题目**：arkliverec-videofeed-default 最近 1 小时有抗动，结合指标+告警+trace三个维度判断问题起点
**状态**：⏳ 超时（execute阶段卡死>40分钟）
**原因**：指标查询API无响应，xray-agent一直hang在execute阶段

---

## Q14 - 串联：告警规则合理性+验证+日志
**题目**：searchpangu-secondary-goodsnote空结果率告警规则，展示配置+判断合理性+查触发记录+日志验证
**状态**：✅ 完成
**Latency**：约8分钟

### Agent回答要点
- 找到规则：ruleId=167597 "searchpangu secondary集群空结果率过高"（P1）
- 展示完整PromQL表达式、触发条件、数据源配置
- 判断阈值合理性问题：触发逻辑"3次中命中0次"实际等于"有值就告警"，缺乏显式阈值

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 5 |
| 意图识别 | 9 |
| Skill选择 | 8 |
| 推理过程 | 8 |
| 结果完整性 | 8 |
| 结果准确性 | 8 |
| 交互体验 | 8 |
| **总分** | **54/70** |

---

## Q15 - 串联：Trace→日志→归因分类
**题目**：dotsim.getMessages异常，找失败trace分析原因+日志确认+归因分类（本服务bug/下游超时/其他）
**状态**：✅ 完成
**Latency**：约25分钟

### Agent回答要点
- TraceId: cea15e2d2e0680009c15af76dfc96466
- 最耗时Span：Call_venom-service-default.checkSimpleBusinessContent（RPC Client，999ms超时）
- 归因：下游依赖超时（venom风控服务），非本服务bug

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 4 |
| 意图识别 | 9 |
| Skill选择 | 8 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 8 |
| **总分** | **56/70** |

---

## Q16 - 串联：服务归属+异常排查
**题目**：arkwukong-20-default先确认服务归属（产品线/业务线/app），再排查最近1小时异常
**状态**：✅ 完成
**Latency**：约5分钟

### Agent回答要点
- 服务归属：search.snssearch.arkwukong.arkwukong-20-default
- 发现ZProfileException（用户画像服务异常）从14:55开始突增，峰值201次/分钟
- 并行执行service-tree-query + service-analysis，效率高

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 7 |
| 意图识别 | 10 |
| Skill选择 | 9 |
| 推理过程 | 9 |
| 结果完整性 | 9 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **62/70** |

---

## Q17 - 串联：慢请求→Span分析→日志错误模式
**题目**：searchpangu-secondary-goodsnote最近30分钟慢请求，找慢trace分析最耗时span+日志看错误模式
**状态**：✅ 完成
**Latency**：约15分钟

### Agent回答要点（质量极高）
- TraceId: cea16082fd0cb82a20cd2621ca3d8da1
- 最耗时Span：Call_lds-ec-note-merger-default.seekLastN（50ms超时）
- 日志错误模式：54,329条error，100%为LDS gRPC超时/DEADLINE_EXCEEDED
- 给出P0/P1/P2三级根因和处置建议

### 评分
| 维度 | 得分/10 |
|------|---------|
| 响应速度 | 5 |
| 意图识别 | 10 |
| Skill选择 | 9 |
| 推理过程 | 10 |
| 结果完整性 | 10 |
| 结果准确性 | 9 |
| 交互体验 | 9 |
| **总分** | **62/70** |

---

## Q18 - 高难：自主规划排查顺序 (超时)
**题目**：arksearchaiask-service-default效果变差，自主判断排查维度+顺序+执行+输出结论
**状态**：⏳ 超时（execute阶段卡死>60分钟）
**原因**：指标查询API无响应

---
