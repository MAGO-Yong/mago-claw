# 外流新笔记下跌故障排查 SOP — 关键参数速查

> 本文件记录已人工校验的关键参数。
> **完整 PromQL 查询语句请查看：`references/promql-collection.json`**

---

## PromQL 关键大小写（人工校验版）

> ⚠️ 以下内容经过人工校验，严格原样使用。

| 步骤 | 标签/字段 | 正确写法 |
|------|---------|---------|
| Step 2.1 | subPhase 值 | `subPhase="after"`（P 大写） |
| Step 3.1 | name 标签（DSSM） | `DSSM_MODEL_BASE` |
| Step 3.1 | name 标签（MLLM） | `MLLM_CLUSTER_MLP_1W` |
| Step 3.1 | name 标签（ES） | `ES` |
| Step 3.1 | name 标签（关注） | `FOLLOW` |
| Step 4.1 | reason_type | `reason_type=~"DSSM_LOW_ENGAGE"` |
| Step 4.2 | type | `type=~"MLLM_CLUSTER_MLP_1W"` |
| Step 4.2 | datasource | `vms-recommend` |
| Step 5.1 | reason_type | `reason_type=~"DSSM_MODEL_BASE"` |
| Step 5.1 | datasource | `vms-recommend`（非 vms-search） |
| Step 5.2 | datasource | `vms-search` |
| Step 6.2 | 指标名 | `postnotescanner_SingleShardTableScanner_scanSingleShard_needRetryTaskNumber`（驼峰） |
| Step 6.2 | code | `code="NOTE_SPAM"` / `code="COMPLETED"` |
| Step 6.2 | biz | 全大写 |
| Step 6.3 | endpoint | `endpoint=~"newNote\|editNote"`（驼峰） |

---

## 召回通道完整列表

Step 3.1 中 `name` 标签的全量枚举值：

---

## 召回通道完整列表

Step 3.1 中 `name` 标签的全量枚举值：

| 通道名 | 说明 |
|--------|------|
| `DSSM_MODEL_BASE` | 基础 DSSM |
| `DSSM_INST` | 即时 DSSM |
| `MLLM_CLUSTER` | MLLM 聚类 |
| `MLLM_CLUSTER_10W` | MLLM 聚类(10W) |
| `MLLM_CLUSTER_MLP_1W` | MLLM 聚类(MLP 1W) |
| `ES` | 倒排召回 |
| `FOLLOW` | 关注召回 |
| `DSSM_LOW_ENGAGE` | 低互动 DSSM |

---

## 异常判定阈值

| 对比维度 | 阈值 | 说明 |
|----------|------|------|
| 当前 vs -1d | 下跌 > 10% | 视为异常 |
| 当前 vs -7d | 下跌 > 10% | 视为异常 |
| 趋势对比 | 趋势相反 | 视为异常 |

---

## 变更查询匹配规则

### 实验平台变更（racingweb）

匹配字段：
- `resource_name` - 实验名称
- `tags` - 业务标签数组
- `details._flags` - 实验涉及的所有flag名称（从 `parasChangeEvents.flagValueMap` 提取）

匹配规则（按优先级）：
1. **检查details._flags**（最高优先级）
   - 遍历 `details._flags` 数组（flag名称列表）
   - 检查每个flag是否匹配 config-watchlist.json 中的 patterns
   - 例如：`hf_lve_merge_age_*`, `newnote_weight_*`, `first_screen_newnote_*`

2. **检查tags**
   - `tags` 包含 `"外流推荐"` → 中风险

3. **检查实验名称**（备用）
   - `resource_name` 匹配 patterns

### Apollo配置变更（apollo）

匹配字段：
- `resource_name` - 配置名称（如 arkfeedx-1-default）
- `details.key` - 配置key
- `details.value` - 配置value

匹配规则：
1. 检查 `resource_name` 是否包含 `arkfeedx` 或 `arkmixrank`
2. 检查 `details.key` 是否匹配 `config-watchlist.json` 中 `apollo_configs.critical` 和 `apollo_configs.high` 列表里的配置key（**必须逐个匹配**，不是示例中的几个）
3. 检查 `details.value` 是否包含新笔记相关关键词

> **注意**：完整的配置key列表请查看 `references/config-watchlist.json` 文件，脚本会自动读取并匹配其中定义的所有配置key。

---

## 变更详细信息字段说明

### 实验平台变更（racingweb）

| 字段 | 说明 | 示例 |
|------|------|------|
| `time` | 变更时间 | 2026-03-20 14:02:30 |
| `resource_name` | 实验名称 | saim_exp_0312 |
| `event` | 变更类型 | Flag变更(灰度阶段) / 参数变更(全量阶段) |
| `stage` | 发布阶段 | 灰度 / 全量 / 关闭 |
| `operator` | 变更人 | 沐雨(黄梦依) |
| `env` | 环境 | prod |
| `level` | 级别 | P0 / P1 / P2 |
| `status` | 状态 | SUCCESS / CANCEL / FAIL |
| `pdl` | PDL部门 | rec / search / ads |
| `biz` | 业务线 | 可选 |
| `tags` | 业务标签 | ["外流推荐", "算法(Rec)"] |
| `link` | 变更链接 | https://racing.devops.xiaohongshu.com/... |

### Apollo配置变更（apollo）

| 字段 | 说明 | 示例 |
|------|------|------|
| `time` | 变更时间 | 2026-03-20 14:02:30 |
| `resource_name` | 配置名称 | arkfeedx-1-default |
| `event` | 变更类型 | 配置发布 |
| `stage` | 发布阶段 | 灰度 / 全量 |
| `operator` | 变更人 | Apollo系统自动/人工 |
| `env` | 环境 | prod |
| `level` | 级别 | P0 / P1 / P2 |
| `status` | 状态 | success / fail |
| `details.key` | 配置Key | hf_lve_merge_age_1h_ratio |
| `details.value` | 配置Value | 0.5 |
| `link` | 变更链接 | https://apollo.xiaohongshu.com/... |

---

## 文档说明

- 本文件为 SOP 关键参数速查文档
- 完整 SOP 流程见：`SKILL.md`
- 结构化数据见：`references/` 目录下各 JSON 文件
- 故障案例见：`references/appendix.md`
- 配置清单见：`references/config-watchlist.json`
