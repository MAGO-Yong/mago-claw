### 场景七：复制中断诊断（路径 C2）

**触发条件**：`Slave_SQL_Running=No` 或 `Slave_IO_Running=No`（区别于延迟路径 C1）
**典型案例**：复制异常告警（占 P0 告警 1.3%），sns_note / qa_srap_common

**Step C2-1** 确认中断状态
```bash
python3 scripts/atomic/get_slave_status.py \
    --cluster <cluster> \
    --output <OUT_DIR> --run_id <RUN_ID>
```
读取关键字段：
- `Slave_IO_Running` / `Slave_SQL_Running`
- `Last_IO_Error` / `Last_SQL_Error`（中断原因）
- `Retrieved_Gtid_Set` vs `Executed_Gtid_Set`（GTID Gap）
- `Relay_Log_File` / `Relay_Log_Pos`（断点位置）

> ⚠️ **Last_Error 可能已清空**：从库复制线程恢复后 `Last_IO_Error`/`Last_SQL_Error` 会自动清空。若两者均为空但告警已触发，需进入可选 Step C2-2b 补采 error_log 覆盖故障时刻。

**Step C2-2** 识别中断类型

| Last_Error 特征 | 中断类型 | 处置方向 |
|----------------|---------|---------|
| `Duplicate entry ... for key 'PRIMARY'` | 主键冲突 | 跳过该事务或同步主库数据 |
| `Table ... doesn't exist` | 表不存在 | 从库缺表，需同步 DDL |
| `Error 'Lock wait timeout'` | 锁超时 | 从库有长事务占锁，Kill 后重启 SQL Thread |
| GTID Gap / `Could not find first log` | GTID 断层 | 需重建从库或手动指定 GTID |
| `Connection refused` / IO Thread 失败 | 网络/权限问题 | 检查主库连接性和 replication 权限 |

**Step C2-2b（可选）** Last_Error 为空时补采 error_log

> 触发条件：Step C2-1 返回 `Last_IO_Error` 和 `Last_SQL_Error` 均为空，但告警已触发。

```bash
# 节点 VM 名从 get_db_connectors 返回的 vmName 字段获取
# k8s 动态调度环境下节点名与集群注册名不一致，不能直接用集群名推断
python3 scripts/atomic/get_error_log.py \
    --hostname <vmName>          \
    --start    "<故障时刻-30min>" \
    --end      "<故障时刻+30min>"
```

> ⚠️ **k8s 节点名说明**：`--hostname` 必须传 VM 名（如 `qsh8-db-sns-note-extra-d-zsiha-1`），从 `get_db_connectors` 输出的 `vmName` 字段获取；k8s 动态调度可能导致 Pod 名与 DB 注册名不一致，直接猜节点名会导致接口返回空。

**Step C2-3** 给出恢复方向建议（AI 不执行任何操作，只给建议）

> ⚠️ **风控强制（见 `docs/report-risk-rules.md` 禁4）**：`Last_SQL_Error` 为空或类型不明时，禁止给任何 SQL Thread 操作建议，输出「复制中断类型无法确认，请 DBA 登录节点执行 `SHOW SLAVE STATUS\G` 获取实时状态后再判断」。

| 中断类型 | 恢复方向（建议句式，不是命令句式） |
|---------|--------------------------------|
| 主键冲突 | 建议 DBA 确认冲突行后，评估是否跳过该事务；参考命令见§8附录 |
| GTID 断层 | 建议 DBA 评估是否重建从库（安全）或手动指定 GTID（高风险，需内核团队确认）；参考命令见§8附录 |
| 网络/权限 | 建议 DBA 检查主库防火墙和 replication 账号密码后重新 `START SLAVE IO_THREAD` |

参考命令（仅供 DBA 知晓，AI 不执行，执行前必须再次确认 Last_Error 类型）见 §8 附录。

**Step C2-4** 输出 HTML 报告（新增"复制中断专项"章节，含 GTID Gap 分析）


**Step C2-5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step C2-6** 生成复盘报告并推送

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
    --path C2 --path_label "复制中断" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

### 场景八：机器带宽诊断（路径 F）

> ⚠️ **完整 SOP 见 [`docs/path-F.md`](docs/path-F.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**


