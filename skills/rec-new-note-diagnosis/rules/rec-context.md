# 推荐系统拓扑（始终加载）

> 诊断过程中始终参考本文件，了解调用链层次关系，避免排查方向跑偏。

## 一、首页推荐外流核心调用链骨架

```
客户端 App
  → snscontentpresentation-service-homefeed  (主流量入口，~85%，880ms avg)
  → arkproxy-service-default（推荐代理层，中枢）

客户端 App
  → bootestribe-service-homefeed             (旧链路，~15%，136ms avg)
  → arkproxy-service-default

  ⚠️ bootestribe 虽为旧链路但仍承载 ~15% 流量，其侧的新笔记过滤/排序逻辑
     若出问题，会导致 15% 流量的新笔记占比下跌，而主链路指标可能正常。
     排查时需注意：若整体跌幅在 10%~20% 且主链路无异常，优先检查 bootestribe 配置。

  其他入口（极少/无流量）：
  - aceflow-homefeed-default → arkproxy（历史遗留，count=-1）
  - snsnoteweb / mozart / rpas → arkproxy（极少量）

arkproxy-service-default（5条并行链路）
├── arkfeedx-1-default          正式主链路（全量用户）
├── arkfeedx-1-exp              实验链路（AB桶用户）
├── arkfeedx-service-degrade    降级链路（主链超时兜底，仍有mixRank调用）
├── arkfeedx-service-share      分享场景
└── arkmixrank-77-default       混排层（挂在arkproxy下，不经arkfeedx）
    ├── Lambdahomefeed-mixrank          基础混排
    ├── Lambdahomefeed-mixrank-exp      实验混排（8个autoreg_*自回归模型）
    └── Lambdahomefeed-onemodel-mixrank OneModel混排（mrom系列模型）

dedup-homefeed-merger-default  首页去重（去重后回调实验/降级链路补量）
├── corvus-redkv-dedup-service
├── corvus-redkv-dedup-degrade
├── corvus-redkv-homefeed-dedup-cache
└── corvus-redkv-smallbiz-dedup-service

arkfeedx-1-default（主链路漏斗）
├── [召回]  Lambdahomefeed-recall → 38个向量模型
├── [粗排]  Lambdahomefeed-firstrank-heter-cpu/gpu
├── [精排]  Lambdahomefeed-finalrank-heter-cpu-batch
└── [后排]  Lambdapostrank-es-hyperparam
```

## 二、新笔记专属索引服务

| 服务 | 作用 | 异常影响 |
|------|------|---------|
| `omega-hf-new-note-2-searcher-default` | 新笔记专属向量索引（1H） | 切换慢 → 1H新笔记供给直降 |
| `dssm_inst_v1_oo_1day` | DSSM单稿实时索引 | OOM/切换慢 → DSSM_INST渠道下跌 |
| `lds-hf-nt-bd-searcher-default` | 倒排索引（Lindorm） | 延迟高 → recall端倒排渠道下跌 |

## 三、新笔记数据流链路

```
笔记发布
  → mq（消息队列）
  → backbone（骨干网数据同步）
  → kafka（实时消费）
  → Flink（实时处理）
  → Lindorm/HIVE（存储）
  → 索引构建
  → 正/倒排检索服务
```

关键监控点：
- **Kafka lag**：>30min 为异常
- **Flink checkpoint**：>20min 超时为异常
- **Lindorm P99**：突增 → 数据同步延迟

## 四、跨场景边界（排查停止条件）

以下服务属于跨场景边界，遇到时停止向下追溯：
- `redis` 相关（60个，含 corvus-rec-homefeed-feedpool）
- `redkv` 相关（41个，含 corvus-redkv-dedup-*）
- `框架升级(lds/omega)` 相关（33个）
- `信息流广告` — adpack4jfeed / feedxad-hf-default
- `交易算法-推荐` — arkfeedxmerchant-service-*
- `基础服务` — featurestore-homefeed-service / zprofile / aceflow
