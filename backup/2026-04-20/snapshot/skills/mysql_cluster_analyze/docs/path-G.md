**触发条件**：用户说"IOWait 高"/"io_wait 告警"，或路径 A/B 排查途中发现 IOWait 异常
**典型案例**：IOWait 异常告警 4 条（占 P0 告警 2.6%），fls_payment_user 集群连续触发

**Step G1** 查 IOWait 时序（监控指标）
从 Layer 1 监控面板查询 `iowait` / `io_util` 指标，确认：
- 告警窗口内 IOWait 峰值
- IOWait 高的节点（主库 vs 从库）
- 持续时间（短暂 vs 持续超 30 分钟）

**Step G2** 查 InnoDB 磁盘读写量
读取以下指标（可通过 get_active_sessions 或监控面板）：
- `Innodb_data_reads` / `Innodb_data_writes`（读写 IOPS）
- `Innodb_buffer_pool_pages_dirty`（脏页比例）
- `Innodb_os_log_written`（redo log 写入量）

**Step G3** 识别 IOWait 根因

| 指标特征 | 可能根因 | 处置方向 |
|---------|---------|---------|
| 读 IOPS 高 + Buffer Pool 命中率低 | 冷数据读放大（Buffer Pool Miss） | 扩大 innodb_buffer_pool_size |
| 写 IOPS 高 + 脏页比例高 | Checkpoint 风暴（刷脏页过快） | 调整 innodb_io_capacity / innodb_max_dirty_pages_pct |
| redo log 写入量激增 + 大事务 | 大批量写入 / 未拆分大事务 | 业务侧拆批，分批提交 |
| IOWait 高但 IOPS 正常 | 磁盘性能退化（物理故障） | 联系运维检查磁盘健康 |
| 从库 IOWait 高 + 复制延迟 | 从库 IO 跟不上 binlog 回放速度 | 调整并行复制参数，或升级从库磁盘 |

**Step G4** 给出建议，输出 HTML 报告（新增"IOWait 专项"章节）

**Step G5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step G6** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

> ~~**⚠️ 已废弃**：`generate_process_review.py` 禁止调用。~~
>
> **复盘报告由 AI 直接生成 HTML**，规范见 `docs/process-review-spec.md`（7 章节）。
> 生成后调 `publish_report.py` 上传发布：

```bash
# 上传 DMS
python3 scripts/common/publish_report.py \
    --html_path <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --out_dir   <OUT_DIR> \
    --cluster   <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --path G --path_label "IOWait" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。
