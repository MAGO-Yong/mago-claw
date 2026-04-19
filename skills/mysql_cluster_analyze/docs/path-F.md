### 场景八：机器带宽诊断（路径 F）

**触发条件**：用户说"带宽告警"/"网络告警"/"network_usage 超阈值"
**典型案例**：机器带宽告警 38 条（占 P0 告警 24.8%，第二高频），fls_fulfillment / fls_inventory 高发，多为 DTS 迁移节点批量触发

**Step F1** 三路并发采集

```bash
# F1-a：告警窗口网络 pattern
# ⚠️ 告警节点 IP 必须传入 --vm_ip：vms-db 无数据时自动回退 vms-vm（覆盖非 DMS 管控节点）
python3 scripts/atomic/get_network_traffic.py \
    --cluster <cluster> \
    --vm_ip <master_ip> \
    --start "<告警时间前30分钟>" --end "<告警时间后30分钟>" \
    --output <OUT_DIR> --run_id <RUN_ID>

# F1-b：12h 主库出流量（node transmit，step=600）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'increase(node_network_transmit_bytes_total{cluster_name="<cluster>",device!="lo"}[10m])' \
    --start "<告警日> 03:50:00" --end "<告警日> 15:50:00" \
    --step 600 --vmname "<master_vmname>" \
    --output <OUT_DIR> --run_id <RUN_ID> --label net_transmit_12h

# F1-c：12h 主库命令量（select/insert/update/delete，各一次，同模板）
for cmd in select insert update delete; do
  python3 scripts/atomic/query_xray_metrics.py \
    --pql "increase(mysql_global_status_commands_total{cluster_name=\"<cluster>\",command=\"${cmd}\"}[10m])" \
    --start "<告警日> 03:50:00" --end "<告警日> 15:50:00" \
    --step 600 --vmname "<master_vmname>" \
    --output <OUT_DIR> --run_id <RUN_ID> --label "cmd_${cmd}_12h"
done
```

> `master_vmname` 从 Phase 0 `get_db_connectors` 主库节点读取；myhub 集群未返回主库时省略（集群维度聚合）。

解读要点：
- `F1-a` `pattern=sustained`：持续型；`burst`：突发型；`is_high=False`：已回落
- `F1-b/c` 重点看是否有**拐点**：出流量拐点与 DML 拐点时刻吻合 → 写入激增是根因；全程平稳 → DTS 常态背景

**Step F2** 识别流量来源（查 processlist）
```bash
python3 scripts/atomic/get_active_sessions.py --cluster <cluster>
```
重点看：
- 是否有 `Command=Binlog Dump` 线程（DTS binlog 拉取）
- 是否有大结果集 SQL（`Sending data` + `rows_sent` 极大）

**Step F3** 判断处置策略

| 场景 | 判断依据 | 处置建议 |
|------|---------|---------|
| 写入激增驱动（DML 有拐点） | F1-b 出流量拐点与 F1-c DML 拐点时刻吻合 | 查 DML 来源（批量任务/业务发布），协调限速或错峰 |
| DTS 背景流量（无拐点） | 12h 出流量全程平稳，Binlog Dump 线程老旧（运行数天以上） | 告警阈值评估，非业务异常 |
| DTS 迁移意外超限 | Binlog Dump 线程新建（运行时间短） + 流量突发 | 暂停迁移任务，错峰执行 |
| 业务大查询 | `Sending data` + 慢查询时序吻合，无 Binlog Dump | 转路径 A 分析 SQL 根因 |
| 未知 | 信号混合 | 向用户确认是否有计划内 DTS 任务或批量写入 |

**Step F4** 输出 HTML 报告（新增"机器带宽专项"章节）
- 12h 出流量趋势图（Canvas，标注拐点时刻）
- 12h 命令量趋势图（SELECT / INSERT / UPDATE / DELETE，标注拐点）
- 根因结论：写入激增驱动 / DTS 常态背景 / 业务大查询
- 处置建议


**Step F5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --dms_url    "$MAIN_URL"
```
验收：脚本输出包含 `✅ 推送成功`

**Step F6** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

> ~~**⚠️ 已废弃**：`generate_process_review.py` 禁止调用。~~
>
> **复盘报告由 AI 直接生成 HTML**，规范见 `docs/process-review-spec.md`（7 章节）。
> 生成后调 `publish_report.py` 上传发布：

```bash
python3 scripts/common/publish_report.py \
    --html_path <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --out_dir   <OUT_DIR> \
    --cluster   <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --path F --path_label "机器带宽" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态。

---

### 场景九：IOWait 诊断（路径 G）
