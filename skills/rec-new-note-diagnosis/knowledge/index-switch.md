# 索引切换知识（Step 5 按需加载）

## 一、三大切换杀手

| 问题 | 特征信号 | 止损方式 |
|------|---------|---------|
| **RIS2.0 追 kafka 慢** | 批增量延迟 10-20min（正常 2-5s） | 切回 redindex1.0 |
| **内存 OOM** | Pod 重启，内存使用率 >90% | 扩容 / 迁移 RIS 节点 |
| **shardbase 阈值触发** | 触发全量 segment 构建 | 调整 shardbase 配置阈值 |

## 二、关键指标阈值

| 指标 | 正常范围 | 异常阈值 | 告警级别 |
|------|---------|---------|---------|
| 索引切换耗时 | < 10min | > **30min** | 🔴 Critical |
| Kafka 消费延迟 | < 5min | > **30min** | 🔴 Critical |
| 索引构建 QPS | > 10K/s | < **5K/s** | 🟠 High |
| 内存使用率 | < 75% | > **90%** | 🟠 High |
| 批增量追数速度 | 2-5s/batch | > **10min/batch** | 🔴 Critical |

## 三、关键索引表

| 表名 | 对应渠道 | 切换周期 |
|------|---------|---------|
| `dssm_inst_v1_oo_1day` | DSSM_INST（1H新笔记） | 每日 |
| `dssm_topk_30d` | DSSM_BASE（topk天级） | 每日 |
| `mllm_cluster_*` | MLLM_CLUSTER_MLP_1W | 每日 |
| `omega-hf-new-note-2-*` | 新笔记专属向量 | 实时增量 |

## 四、排查命令

```bash
# 基础模式
python3 skills/index-switch-check/scripts/check_switch.py dssm_inst_v1_oo_1day

# 深度模式（含运行时指标）
python3 skills/index-switch-check/scripts/check_switch.py dssm_inst_v1_oo_1day --deep \
  --cluster omega-hf-inv \
  --start "2026-03-25T10:00:00+08:00" \
  --end "2026-03-25T12:00:00+08:00"
```

## 五、矛盾判断处理

**场景**：recall 阶段量正常，但各召回渠道 quota 也正常 → 可能是索引新鲜度问题

**验证方法**：
1. 检查笔记平均年龄（avg_note_age 指标）
   - 若年龄变老 → 索引新鲜度问题（切换慢）
   - 若年龄正常 → 审核积压 or 数据流延迟
2. 检查 `dssm_inst_v1_oo_1day` 切换状态
3. 检查 Kafka 消费 lag
