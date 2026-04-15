### 场景六：连接堆积诊断（路径 B2）

**触发条件**：`total_active > 100` 且 `cpu_usage < 70%`（区别于路径 B）
**典型案例**：活跃连接数告警（占 P0 告警 3.9%），shequ_feed_ads / sns_user_extra 高发

---

#### Step B2-0 · System lock 专项采集（子路径判断分叉，新增）

> ⚠️ 必须在 `get_active_sessions.py` 之后立即执行，用于判断走哪条子路径。
> `get_active_sessions.py` 的 `state_dist` 当前存在数据缺失问题（返回空字符串），本脚本作为专项补充。

```bash
python3 scripts/atomic/get_system_lock_status.py \
    --ip      <master_ip> \
    --port    <master_port> \
    --cluster <cluster> \
    --output <OUT_DIR> --run_id <RUN_ID>
```

> ℹ️ `--ip` 和 `--port` 为必填参数（ai-api/v1 `get_cur_process_list` 要求节点级寻址），从 Step 1 的 `get_db_connectors.json` 中读取主库 IP/Port。

读取 `_analysis.subtype` 字段，按以下规则分叉：

| subtype | 含义 | 对应子路径 |
|---------|------|-----------|
| `autoinc` | INSERT IGNORE / REPLACE 触发 AUTO-INC 表级锁堆积 | → **B2-AutoInc**（见下） |
| `row_lock` | 行锁 / MDL 锁等待堆积 | → **B2-RowLock**（见下） |
| `sleep_leak` | Sleep 连接泄漏（time > 3600s） | → **B2-Leak**（见下） |
| `mixed` | System lock + 行锁并存 | → **B2-AutoInc** 优先，兼顾行锁 |
| `normal` | 无明显锁，可能已自愈 | → 向用户说明，等待确认 |

---

#### 子路径 B2-AutoInc：AUTO-INC 锁堆积（System lock）

**典型场景**：INSERT IGNORE / REPLACE INTO 高并发写入同一分表，innodb_autoinc_lock_mode ≠ 2

**Step B2-1a** 确认 AUTO-INC 锁现场
- 读取 `get_system_lock_status._analysis.hot_tables` → 定位热点分表
- 读取 `get_system_lock_status._analysis.system_lock_sqls` → 确认是 INSERT IGNORE / REPLACE
- 读取 `get_system_lock_status._analysis.autoinc_risk` → True 则确认为 AUTO-INC 锁

**Step B2-1b** 获取分表 DDL（确认主键结构）
```bash
# 判断表是否有 AUTO_INCREMENT 主键（是否能去掉换业务主键）
curl -s "https://dms.devops.xiaohongshu.com/dms-api/v1/mysql/sql-query/get-create-table?cluster_name=<cluster>&db_name=<db>&table_name=<table>" \
  -H "dms-claw-token: $DMS_CLAW_TOKEN"
```
重点看：
- 是否有 `AUTO_INCREMENT` 主键 → 有则建议调 `innodb_autoinc_lock_mode=2`
- 是否可改为业务主键（user_id + create_time 之类）→ 记录在建议章节

**Step B2-2a** 处置建议输出

| 优先级 | 措施 | 说明 |
|--------|------|------|
| P0 立即 | `SET GLOBAL innodb_autoinc_lock_mode=2` | 交错模式，消除表级 AUTO-INC 锁，同步修改 my.cnf |
| P0 立即 | 调用方改批量写入（50~200行/批） | 减少锁申请次数 |
| P0 立即 | 同一分表写入限流（令牌桶，≤20 QPS） | 防止并发峰值触发堆积 |
| P1 本周 | 评估去掉 AUTO_INCREMENT 主键，改业务主键 | 彻底消除 AUTO-INC 锁，需 DDL 审批 |
| P1 本周 | 分片路由增加打散因子（时间维度） | 消除热点号段集中写入 |

> ⚠️ **注意**：`innodb_autoinc_lock_mode` 改为 2 后 AUTO_INCREMENT 值不再连续，需确认业务不依赖连续性。

---

#### 子路径 B2-RowLock：行锁 / MDL 锁堆积

**典型场景**：长事务持锁，后续写入等待行锁；或 DDL 操作持 MDL 锁，读写全阻塞

**Step B2-1b** 查持锁事务
```bash
# 通过原机慢日志找长事务（Lock_time 高的 SQL）
python3 scripts/atomic/get_raw_slow_log.py \
    --cluster <cluster> --hostname <master_vm_name> \
    --start "<告警时间UTC-5min>" --end "<告警时间UTC>" \
    --min_query_time 0.001 --limit 200
```
关注：`lock_time > 1s` 的 SQL → 持锁者

**Step B2-2b** 处置建议

| 优先级 | 措施 |
|--------|------|
| P0 立即 | KILL 持锁连接（DMS 控制台或 `KILL <id>`） |
| P1 | 调低事务超时（`innodb_lock_wait_timeout`，建议 ≤ 10s） |
| P1 | 检查是否有未提交的长事务（OLAP 查询混入 OLTP 库） |

---

#### 子路径 B2-Leak：Sleep 连接泄漏

**典型场景**：应用侧连接池未正确归还连接，Sleep 连接 time > 3600s 大量堆积

**Step B2-1c** 分析泄漏来源
- 读取 `get_system_lock_status._analysis.sleep_leak_count` → 泄漏连接数
- 从活跃会话找 User/Host 分布 → 定位来源服务

**Step B2-2c** 处置建议

| 优先级 | 措施 |
|--------|------|
| P0 立即 | `SET GLOBAL wait_timeout=300`（建议值），自动回收长 Sleep 连接 |
| P0 立即 | KILL 存量 Sleep 连接（time > 3600s） |
| P1 | 排查应用连接池配置（maxIdle、testOnBorrow、validationQuery） |
| P1 | 应用侧添加连接健康检查（定期 ping，避免僵尸连接） |

---

**Step B2-5** 生成并发布 HTML 报告

> ⚠️ **HTML 由 AI 直接生成**，不调用 `generate_report.py` 或任何渲染脚本。
> 生成前必须读取 `docs/report-spec.md`（通用风格规范）。
> 以下是 B2-RowLock 路径的 8 章节内容规范，AI 结合诊断上下文 + 采集数据 + 本规范直接生成 HTML。

---

##### B2-RowLock 路径 · 8 章节 HTML 报告规范

> 样式风格见 `docs/report-spec.md`（深色 Banner + 卡片布局 + KPI 格子 + 图表 + 链式时间线）。
> 以下各章节定义覆盖通用规范中不适用于 B2-RowLock 的内容。

**Banner**
- 标题：`<cluster> 连接堆积诊断报告`
- 副标题：一句话根因（AI 根据 `get_system_lock_status._analysis` + 慢日志综合判断）
- Meta 标签：集群、主库 vm_name、故障窗口（北京时间）、子路径（B2-RowLock）

**第 1 章 · 告警概览**

KPI 格子（有数据填数据，无数据标"未采集"）：

| KPI | 数据来源 |
|-----|---------|
| 行锁等待线程数 | `get_system_lock_status._analysis.row_lock_count` |
| 活跃连接总数 | `get_system_lock_status._analysis.total_active` |
| 慢查询总数（10min 窗口）| `get_raw_slow_log.data.summary.total_slow_queries` |
| 最慢查询时长（s）| `get_raw_slow_log.data.details` 按 `query_time` 降序第一条 |
| 最大扫描行数 | `get_raw_slow_log.data.details` 按 `rows_examined` 降序第一条 |
| 受影响节点数 | `get_db_connectors.data` 列表长度 |

**第 2 章 · 故障时间线**

1. **慢查询分钟级图表**（JavaScript Canvas 动态渲染）：
   - 数据来源：`get_raw_slow_log.data.timeline[]`
   - X 轴：`minute` 字段（格式 `2026-04-10 01:54`，UTC，+8h 后取 `HH:MM`）
   - Y 轴左（蓝色柱）：`query_count`
   - Y 轴右（橙色线）：`float(max_query_time)`
2. **事件链**：AI 根据 `_analysis.risks` + 慢日志时序 + 告警时间推断，节点类型 `trigger/root/effect/recover`，颜色编码见 `report-spec.md`

**第 3 章 · 根因分析（B2-RowLock 专属）**

1. **一句话根因**（红色高亮框）
2. **行锁现场**：`get_system_lock_status._analysis`（`row_lock_count` / `risks` / `recommended_subpath`）
3. **持锁候选 SQL**：`get_raw_slow_log.data.details` 中 `lock_time` 最高的前 3 条，含 `sql_text` / `lock_time` / `rows_examined` / `database`
4. **根因归纳表**：按业务层 / 数据层 / 参数层分层，每行标注优先级颜色

**第 4 章 · 慢查询 Top 10 分布**

数据来源：`get_raw_slow_log.data.top_sql[]`

| 列名 | 字段名（以实际 API 返回为准）|
|------|--------------------------|
| SQL 模板（最多 120 字符）| `sql_template` |
| 来源服务 | 从 `data.details[].sql_text` 提取 `XHS_SERVICE:xxx` 与 `CLIENT_IP` 之间的值，去重、过滤 `null` |
| 执行次数 | `query_count`（**注意：不是 `count`**）|
| avg_qt(s) | `avg_query_time` |
| max_qt(s) | `max_query_time` |
| avg_lock(s) | `avg_lock_time` |
| lock% | `avg_lock_time / avg_query_time × 100` |
| 角色 | `lock% < 5%` → 持锁者；`lock% > 50%` → 等锁受害 |

**第 5 章 · 表统计信息 & 执行计划**

- 优先读 `explain_sql.json` / `table_stats.json`（若存在）
- **未采集时（B2-RowLock 常见）**：
  - 从 `get_raw_slow_log.data.details` 取 `rows_examined` 最高的前 3 条，提取 `sql_text` 中反引号内 `t_` 开头的表名作为推断目标表
  - 展示时标注：`⚠️ EXPLAIN / 表统计未采集，以下为慢日志扫描行数推断值`
  - **禁止显示黄色「数据未采集」框，改用灰色推断值注释**

**第 6 章 · 影响范围**

| 维度 | 数据来源 |
|------|---------|
| 受影响实例 | `get_db_connectors.data[].vm_name` 全部列出 |
| 受影响业务服务 | `get_raw_slow_log.data.details[].sql_text`，正则提取 `XHS_SERVICE:([^;*/\s]+?)(?:;|CLIENT_IP)`，去重过滤 `null` |
| 故障等级 | AI 根据 `row_lock_count` + 慢查询总数 + 告警持续时间综合判断（P0/P1/P2）|
| 用户可见影响 | AI 根据行锁堆积程度和业务服务列表综合描述 |
| 数据完整性 | 事务最终状态（提交 / 回滚，结合 lock_time 和业务判断）|

**第 7 章 · 改进建议**

卡片网格布局（P0/P1/P2），内容对应 Step B2-2b 的 B2-RowLock 处置方案：
- **P0 立即**：KILL 持锁连接
- **P1 本周**：`innodb_lock_wait_timeout` 调低至 ≤ 10s；排查长事务来源
- **P2 迭代内**：评估 OLAP/OLTP 混用问题；业务侧优化高锁等待 SQL 的事务粒度

**第 8 章 · 附录**

1. **数据来源说明**（三列表：数据项 / 接口文件 / 状态）：

| 数据项 | 接口 / 文件 | 状态 |
|--------|-----------|------|
| 集群节点列表 | `get_db_connectors.json` | ✅ / ❌ |
| 原机慢查询日志 | `get_raw_slow_log.json` | ✅ / ❌ |
| System Lock 状态 | `get_system_lock_status.json` | ✅ / ❌ |
| 活跃会话快照 | `get_active_sessions.json` | ✅ / ❌ |
| EXPLAIN / 表统计 | `explain_sql` / `get_table_stats` | ⚠️ 未采集（固定）|

2. **核心 SQL 样本**：`lock_time` 最高的原始 `sql_text`（`<pre>` 代码块，保留完整原文）

---

生成 HTML 后执行发布：

```bash
python3 scripts/common/publish_report.py \
    --html_path <html_file> \
    --out_dir   <OUT_DIR> \
    --cluster   <cluster> \
    --time_range "<HH:MM>~<HH:MM>" \
    --path B2 --path_label RowLock \
    --severity  <P0/P1/P2> \
    --root_cause "<一句话根因>" \
    --p0_action  "<P0 处置建议>"
```

验收：脚本输出 `✅ 上传成功` + `✅ run_meta.json 已写入 main_report_url` + `✅ 推送成功`


**Step B2-6** 推送主报告 Webhook（已由 Step B2-5 的 `publish_report.py` 完成，此步骤仅作手动补救备用）

```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --dms_url    <dms_url>
```

验收：脚本输出包含 `✅ 推送成功`

**Step B2-7** 生成复盘报告并推送

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
    --path B2 --path_label "连接堆积" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

