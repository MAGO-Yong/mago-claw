# 知识索引（按需加载）

> 诊断 Agent 根据分诊结果和当前 Step，按需加载对应知识文件。
> 不要一次性加载所有文件——只加载当前需要的。

## 故障类型 → 知识文件映射

| 触发条件 | 加载文件 | 加载时机 |
|---------|---------|---------|
| recall 矛盾判断（quota正常但指标跌）| `index-switch.md` | Step 4 出现矛盾判断时 |
| 索引切换慢 / dssmbase下跌 | `index-switch.md` | Step 5 开始前 |
| Kafka lag / Flink 延迟 / 多渠道同时延迟 | `data-flow.md` | Step 6 开始前 |
| zk zxid / Lindorm 故障 | `data-flow.md` | Step 6 开始前 |
| 视频权重变更命中 watchlist | `gradual-failure-cases.md` | GATE A 后发现变更时 |
| 混排变更 / hf_new_mix_ad_power | `gradual-failure-cases.md` | GATE A 后发现变更时 |
| 阴跌型异常（无急剧跌点） | `gradual-failure-cases.md` | Step 2 判断为阴跌时 |

## 关键词速查

- **索引**：OOM / RIS2.0 / shardbase / 切换慢 / dssm_inst → `index-switch.md`
- **数据流**：Flink / Kafka / Lindorm / backbone / zk → `data-flow.md`
- **渐进式**：发布后阴跌 / 凌晨暴跌 / 视频权重 / fp_all_video / hf_new_mix → `gradual-failure-cases.md`

## 不需要额外加载的情况

- Step 1-2（指标查询 + 变更定位）：只需 rules/ 和 references/config-watchlist.json
- Fast Path 全程：不加载 knowledge/（变更查询 + watchlist 匹配已足够）
- Standard Path Step 3-4：根据 Step 4 矛盾判断结果决定是否加载 index-switch.md
