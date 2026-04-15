# testing-guide.md — Skill 测试规范

> 适用于：`mysql_cluster_analyze` Skill 的所有 atomic 脚本、路径脚本、common 脚本的可用性测试。

---

## 测试集群白名单

| 集群名 | 用途说明 |
|--------|---------|
| `live_ds` | 默认测试集群，流量低、非核心业务，适合脚本调用验证 |

**执行测试前必须确认使用白名单内的集群。**

---

## 禁用集群（生产敏感，禁止用于测试）

| 集群名 | 禁止原因 |
|--------|---------|
| `ads_ad_core` | 广告核心业务集群，真实业务流量，任何误查询均有影响风险 |
| 所有 `sns_*` 集群 | 社区内容核心链路 |
| 所有 `user_*` 集群 | 用户账号核心数据 |

**禁用原则：凡承载核心业务流量的生产集群，一律不得用于 Skill 测试。**

---

## 测试注意事项

### get_raw_slow_log
- 时间参数为 **UTC 时间**（北京时间 -8h），窗口 **≤ 10 分钟**
- 示例：北京时间 `2026-04-09 00:06:49` → UTC `2026-04-08 16:06:49`

### get_table_stats / get_index_stats
- **必须传 `--connector normal:<ip>:<port>`**，否则服务端返回 400
- connector 格式从 `get_db_connectors` 结果中提取 slave 节点

### get_connection_timeline
- 只有 `--output-json <path>` 参数，**无标准 `--output/--run_id`**
- 调用时需手动拼写输出路径：`<OUT_DIR>/<RUN_ID>/raw/get_connection_timeline.json`

### query_xray_metrics
- 时间参数为**北京时间**（与 get_raw_slow_log 相反，注意区分）
- vmname 过滤为客户端过滤，支持子串匹配

---

## 可用性测试标准流程

```bash
CLUSTER="live_ds"
RUN_ID="live_ds_test_$(date +%Y%m%d_%H%M%S)"
OUTDIR="output/$RUN_ID"

# 1. 获取节点信息
python3 scripts/atomic/get_db_connectors.py \
    --cluster $CLUSTER --output $OUTDIR --run_id $RUN_ID

# 2. 用 slave connector 测试 table_stats
CONNECTOR="normal:<slave_ip>:<port>"   # 从上一步结果中提取
python3 scripts/atomic/get_table_stats.py \
    --cluster $CLUSTER --db <db> --table <table> \
    --connector $CONNECTOR \
    --output $OUTDIR --run_id $RUN_ID
```

---

*更新于 2026-04-09，由成烽明确要求固化。*
