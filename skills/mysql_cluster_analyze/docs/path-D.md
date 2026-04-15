### 场景四：磁盘满诊断（路径 D）

**Step 0** Precheck（同路径 A）

**Step D1** 查磁盘用量
```bash
python3 scripts/atomic/get_disk_usage.py \
    --cluster <cluster> [--vm_name <vm_name>]
    --output <OUT_DIR> --run_id <RUN_ID>
```
DMS API 不支持时：降级输出人工排查指引（脚本自动处理）

**Step D2** 按磁盘大头分类处置：

| 大头 | 处理方法 |
|------|---------|
| data 文件大 | 数据归档 / 扩容 / 增加分片 |
| binlog 大 | 缩短 `expire_logs_days`，清理旧 binlog |
| relay log 大 | 检查复制状态（转 路径 C Step C1）|
| slow log 大 | 清理或轮转 slow.log |

**Step D3** 多节点对比，识别数据倾斜
- 各分片磁盘用量对比，是否某分片独高
- 倾斜 → 评估单独扩容或重新均衡分片路由

**Step D4** 输出报告（含磁盘专项章节，阈值参考 pitfalls.md）


**Step D5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step D6** 生成复盘报告并推送

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
    --path D --path_label "磁盘满" \
    --severity P0 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

