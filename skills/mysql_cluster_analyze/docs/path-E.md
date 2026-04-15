### 场景五：Crash 诊断（路径 E）

**Step 0** Precheck（同路径 A）

**Step E1** 确认节点存活状态
```bash
python3 scripts/atomic/get_db_connectors.py --cluster <cluster>
```
- 节点不可达 → 标记 Crash，输出"建议联系 DBA 人工登录确认，查看 /data/mysql/error.log"
- 节点可达 → 可能已重启恢复，继续 Step E2

**Step E2** 查崩溃前慢查询（CK 聚合，时间窗口扩展到崩溃前 1 小时）
```bash
python3 scripts/atomic/get_slow_log_list.py \
    --cluster <cluster> \
    --start "<崩溃时间前1小时>" --end "<崩溃时间>" \
    --page_size 50 --sort desc \
    --output <OUT_DIR> --run_id <RUN_ID>
```

**Step E3** 输出报告，重点章节：
- 崩溃时间 / 崩溃前 TOP SQL
- 建议人工查看 error log：`/data/mysql/error.log`（通过 DMS 控制台）
- 建议确认是否有 OOM Killer 记录：`dmesg | grep -i oom`


**Step E4** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step E5** 生成复盘报告并推送

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
    --path E --path_label "Crash" \
    --severity P0 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

