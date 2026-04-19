### 场景三：主从延迟诊断（路径 C）

**Step 0** Precheck（同路径 A）

**Step 1** 获取连接器（含从库 vm_name）
```bash
python3 scripts/atomic/get_db_connectors.py --cluster <cluster>
```

**Step C1** 查复制状态
```bash
python3 scripts/atomic/get_slave_status.py \
    --cluster <cluster> --hostname <slave_vm_name> \
    --output <OUT_DIR> --run_id <RUN_ID>
```

验收：重点看 `_analysis`：
- `Slave_SQL_Running=No` 或 `Last_Error` 非空 → 复制链路断裂，输出报告，建议人工修复
- `Slave_SQL_Running=Yes` 但 `Seconds_Behind_Master` 大 → 疑似慢 SQL 堵塞回放 → 继续 Step 2~6（路径 A）

**Step C2**（可选）检查 Relay log 磁盘占用
```bash
python3 scripts/atomic/get_disk_usage.py \
    --cluster <cluster> --vm_name <slave_vm_name>
```
Relay log 异常大（几十 GB）→ 补充到报告磁盘风险章节


**Step C4** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step C5** 生成复盘报告并推送

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
    --path C1 --path_label "主从延迟" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

