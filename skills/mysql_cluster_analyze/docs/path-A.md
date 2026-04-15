### 场景一：慢查询诊断（路径 A）

**触发词**：诊断/分析 XX 集群慢查询、给我出一份性能报告、帮我看下 XX 实例的慢查询情况

**所需参数**：

| 参数 | 必填 | 说明 |
|------|------|------|
| cluster | ✅ | 集群名称 |
| db | ✅ | 集群下真实存在的库名，用于获取 connector |
| hostname | ✅ | 主库 vm_name（从 Step 1 get_db_connectors 获取）|
| 时间窗口 | ✅ | 北京时间，AI 自动换算 UTC（窗口 ≤ 10 分钟）|
| min_query_time | 可选 | 慢查询阈值，默认 0（采集全量）|

---

#### 输出目录约定（每次诊断开始前确定，所有步骤统一使用）

```
RUN_ID  = "<cluster>_<YYYYmmdd_HHMMSS>"          # 例：fls_product_20260326_110000
OUT_DIR = "~/.openclaw/workspace/skills/mysql_cluster_analyze/output/<RUN_ID>"
RAW_DIR = "<OUT_DIR>/raw/"

> ⚠️ **`--output` 参数传的是父目录，不含 RUN_ID**：
> atomic 脚本内部会自动拼接 `<--output>/<run_id>/raw/`。
> 正确传法：`--output output/ --run_id <RUN_ID>`（raw 写入 `output/<RUN_ID>/raw/`）
> 错误传法：`--output output/<RUN_ID> --run_id <RUN_ID>`（会产生 `output/<RUN_ID>/<RUN_ID>/raw/` 双层嵌套，报告读不到数据）
```

所有 atomic 脚本均附加 `--output <OUT_DIR> --run_id <RUN_ID>`，
结果自动写入 `<RAW_DIR>/<script_name>[_label].json`。

---

#### 执行 Checklist

**Step 0 · Precheck**

执行：
```bash
python3 scripts/common/precheck.py
```

> **📦 交付物**：无文件产出，仅环境确认。
>
> **✅ 验收条件**（全部满足才能进入 Step 1）：
> - 输出包含 `✅ DMS_AI_TOKEN 已配置` 或 `✅ DMS_CLAW_TOKEN 已配置`（至少一个，子串匹配即可）
> - 输出包含 `✅ DMS 服务可达`
> - 脚本退出码为 0
>
> **❌ 失败处理**：立即终止，提示用户配置 `DMS_AI_TOKEN` 或 `DMS_CLAW_TOKEN`（参照前置要求章节），不得跳过继续执行。

---

**Step 0b · 初始化诊断元信息（run_meta.json）**

紧接 Step 0 之后执行，记录本次诊断的基本信息，供复盘报告自动生成使用。

```bash
python3 scripts/common/run_meta.py init \
    --out_dir   <OUT_DIR> \
    --cluster   <cluster> \
    --run_id    <RUN_ID> \
    --path      <路径类型：A/B/B2/C1/C2/D/E/F/G> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    [--fault_time "<故障时刻 北京时间>"]
```

> **📦 交付物**：`<OUT_DIR>/run_meta.json`
>
> **✅ 验收条件**：文件存在，内容包含 `cluster`、`run_id`、`path` 三个字段。
>
> **ℹ️ 用途**：诊断过程中如有改进建议（接口异常、绕过方式、踩坑记录），随时追加：
> ```bash
> python3 scripts/common/run_meta.py note \
>     --out_dir <OUT_DIR> \
>     --text "get_error_log 接口返回 404，建议平台补全"
> ```
> 主报告上传后，更新 URL：
> ```bash
> python3 scripts/common/run_meta.py set \
>     --out_dir <OUT_DIR> --key main_report_url --value "<url>"
> ```

---

**Step 1 · 获取连接器**

执行：
```bash
python3 scripts/atomic/get_db_connectors.py \
    --cluster <cluster> --db <db> --include_master \
    --output <OUT_DIR> --run_id <RUN_ID>
```

> **📦 交付物**：`<RAW_DIR>/get_db_connectors.json`
>
> **✅ 验收条件**（全部满足才能进入 Step 2）：
> - 文件 `get_db_connectors.json` 存在且非空
> - `data[]` 中包含至少一个 `role=slave` 的条目
> - `data[]` 中包含至少一个 `role=master` 的条目
> - 已从返回值提取并记录：
>   - `slave_connector`：格式 `normal:<ip>:<port>`（用于 explain/stats）
>   - `master_vm_name`：master 节点的 `vm_name`（用于慢日志采集）

---

**Step 2 · 多路并发采集**

以下 2a~2f 同时运行，结果互补。**2a、2b 必须完成**才能进入 Step 3；2d~2f 为辅助采集，失败时跳过不阻断流程。

**2a · CK 聚合慢日志（slow_log_list）**

执行：
```bash
python3 scripts/atomic/get_slow_log_list.py \
    --cluster <cluster> --db <db> \
    --start "<北京时间start>" --end "<北京时间end>" \
    --page_size 50 --sort desc \
    --output <OUT_DIR> --run_id <RUN_ID>
```

用途：获取**模板级别**聚合统计（count、avg_qt、max_qt、sum_qt、服务名）。

> **📦 交付物**：`<RAW_DIR>/get_slow_log_list.json`
>
> **✅ 验收条件**：
> - 文件存在且非空
> - 响应中包含 `data` 字段（即使为空列表也视为成功）

**2b · 原机原始慢日志（raw_slow_log）**

北京时间 → UTC（-8h），窗口 ≤ 10 分钟，执行：
```bash
python3 scripts/atomic/get_raw_slow_log.py \
    --cluster <cluster> --hostname <master_vm_name> \
    --start "<utc_start>" --end "<utc_end>" \
    --min_query_time 0 --limit 200 \
    --output <OUT_DIR> --run_id <RUN_ID>
```

用途：获取**原始明细**（每条 sql_text、rows_examined、lock_time、来源 IP/服务、时间戳）。

> **📦 交付物**：`<RAW_DIR>/get_raw_slow_log.json`
>
> **✅ 验收条件**：
> - 文件存在且非空
> - `data.summary.total_slow_queries` 字段存在
> - `data.details[]` 非空（若为空，向用户说明原因，询问是否调整时间窗口后重试）

**2c · 识别 TOP 3 业务慢 SQL**

从 `data.details[]` 明细中：
- 过滤非业务 SQL（见下方"业务 SQL 过滤规则"）
- 按 `query_time` 降序，取 TOP 3
- 从原始 `sql_text`（非脱敏模板）提取真实业务**表名**

> **📦 交付物**：内存中的 `top3_sqls[]` 列表和 `business_tables[]` 列表（供 Step 3 使用）
>
> **✅ 验收条件**：
> - `top3_sqls` 至少有 1 条（若全部被过滤，向用户说明过滤结果并展示被过滤的 SQL，询问是否手动指定）
> - `business_tables` 至少有 1 张表

**2d · 采集 Error Log（辅助，失败不阻断）**

与 2a/2b 并发执行，采集故障时段的 mysqld.log：
```bash
python3 scripts/atomic/get_error_log.py \
    --hostname <master_vm_name> \
    --start "<北京时间start>" --end "<北京时间end>" \
    --level_filter "Error,Warning" \
    --output <OUT_DIR> --run_id <RUN_ID>
```

用途：发现 InnoDB 告警（page_cleaner、buffer pool wait_free）、死锁、OOM 等异常，辅助根因定位。

> **📦 交付物**：`<RAW_DIR>/get_error_log.json`
>
> **✅ 验收条件**：
> - **采集成功**：文件存在且 `data.summary` 字段存在，将 error/warning 计数和关键词命中纳入报告第 2 章"现场数据"
> - **采集失败**：跳过，在报告中标注"⚠️ Error Log 采集失败（接口不可用），建议通过 DMS 控制台查看 mysqld.log"，**不阻断流程**

**2e · 采集活跃会话（辅助，失败不阻断）**

与 2a/2b 并发执行，双路采集故障时刻的活跃连接：
```bash
python3 scripts/atomic/get_active_sessions.py \
    --cluster <cluster> \
    --vm_name <master_vm_name> \
    --ip <master_ip> --port <master_port> \
    --fault_time "<北京时间>" \
    --output <OUT_DIR> --run_id <RUN_ID>
```

用途：查看故障时刻的连接堆积、锁等待、长事务，辅助判断慢查询是否由锁竞争/连接堆积导致。

> **📦 交付物**：`<RAW_DIR>/get_active_sessions.json`
>
> **✅ 验收条件**：
> - **采集成功**：文件存在且 `_analysis` 字段存在，将 `history_snapshot.connectionCount`、`lock_waiters_count`、`long_running_count` 纳入报告
> - **采集失败**：跳过，在报告中标注"⚠️ 活跃会话采集失败，建议人工查看 DMS 会话管理"，**不阻断流程**

**2f · 采集 InnoDB / 系统指标时序（辅助，失败不阻断）**

与 2a/2b 并发执行，通过 `query_xray_metrics.py`（1-K）采集故障时段的关键指标时序。
指标名参考 `references/mysql_exporter_metrics.md`（1-J）。

> ⚠️ **采集时间窗口**：路径 B（CPU 高）建议采集 **故障前 30 分钟 ~ 故障后 10 分钟**，以捕获前置亚稳态运行阶段。路径 A（慢查询）按原始告警窗口即可。

以下指标**逐个查询**，每个指标一次调用（`--label` 区分输出文件）。
按优先级分组：**核心组（必采）** 和 **扩展组（路径 B 必采，路径 A 可选）**。

**核心组（路径 A/B 均采集）**：

```bash
# ① CPU 使用率（平台自定义指标，非 mysql_exporter 原生，部分集群可能不可用）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_cpu_usage{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label cpu_usage \
    --output <OUT_DIR> --run_id <RUN_ID>

# ② Buffer Pool Wait Free Rate（counter 指标，必须用 rate 转换为 /s）
#    > 0 = buffer pool 没有空闲页，用户线程被迫做 LRU flush
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_buffer_pool_wait_free{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label wait_free_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ③ Threads Running（并发执行线程数）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_threads_running{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label threads_running \
    --output <OUT_DIR> --run_id <RUN_ID>

# ④ InnoDB Row Lock Waits Rate（行锁等待趋势）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_row_lock_waits{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label row_lock_waits_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑤ InnoDB Data Writes Rate（磁盘写 IOPS）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_data_writes{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label data_writes_rate \
    --output <OUT_DIR> --run_id <RUN_ID>
```

**扩展组（路径 B 必采，路径 A 可选）**：

```bash
# ⑥ Buffer Pool Dirty Bytes（脏页总量，计算 dirty ratio 的分子）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_innodb_buffer_pool_bytes_dirty{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label dirty_bytes \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑦ Buffer Pool Data Bytes（数据页总量，计算 dirty ratio 的分母）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_innodb_buffer_pool_bytes_data{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label data_bytes \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑧ Buffer Pool Free Pages（空闲页数，= 0 是 wait_free 的根因）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_buffer_pool_pages{cluster_name="<cluster>",state="free"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label pages_free \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑨ Pages Flushed Rate（page cleaner 实际刷脏吞吐）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_buffer_pool_pages_flushed{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label pages_flushed_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑩ Handler Commit Rate（事务提交速率，对应 INSERT/UPDATE QPS）
# 注意：label 名因 exporter 版本而异，可能是 handler="commit" 或 type="commit"
# 若返回空 series，请尝试替换 label 名
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_handlers_total{cluster_name="<cluster>",handler="commit"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label handler_commit_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑪ InnoDB OS Log Fsyncs Rate（redo log fsync 次数，与 handler_commit 算 group commit 效率）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_os_log_fsyncs{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label os_log_fsyncs_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑫ InnoDB Data Written Rate（写入字节量 MB/s，区别于写 IOPS）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_data_written{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label data_written_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑬ Buffer Pool Read Requests Rate（逻辑读，cache miss rate 分母）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_buffer_pool_read_requests{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label bp_read_requests_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑭ Buffer Pool Reads Rate（物理读，cache miss rate 分子）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_buffer_pool_reads{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label bp_reads_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑮ Threads Connected（总连接数，区别于 threads_running）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_threads_connected{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label threads_connected \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑯ InnoDB Log Waits Rate（redo log 空间不足等待速率，排除 redo 瓶颈假说）
# 注意：innodb_log_waits 是累积 counter，必须用 rate() 转为每秒增量
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_log_waits{cluster_name="<cluster>"}[1m])' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label log_waits_rate \
    --output <OUT_DIR> --run_id <RUN_ID>

# ⑰ InnoDB OS Log Pending Fsyncs（redo fsync 排队数，排除 IO 瓶颈假说）
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'mysql_global_status_innodb_os_log_pending_fsyncs{cluster_name="<cluster>"}' \
    --start "<北京时间start>" --end "<北京时间end>" --step 15 \
    --vmname "<master_vm_name>" --label os_log_pending_fsyncs \
    --output <OUT_DIR> --run_id <RUN_ID>
```

**SQL 命令速率组（路径 B 必采，路径 A 可选）**：

```bash
# ⑱ DML+SELECT irate（15s 粒度）——归档任务/批量写入识别
for cmd in insert delete update select; do
  python3 scripts/atomic/query_xray_metrics.py \
      --pql "irate(mysql_global_status_commands_total{cluster_name=\"<cluster>\",command=\"${cmd}\"}[15s])" \
      --start "<北京时间start>" --end "<北京时间end>" --step 15 \
      --vmname "<master_vm_name>" --label "cmd_${cmd}" \
      --output <OUT_DIR> --run_id <RUN_ID>
done
```

> **归档任务识别**（Step 4 计算）：`INSERT_avg/DELETE_avg ≈ 1.0` 且两者同一 15s 窗口从 0 跳到 N/s → 归档任务特征（INSERT 新行 + DELETE 旧行各一次/事务）

**配置变量组（一次性采集，取最后一个点即可）**：

```bash
# ⑲ InnoDB 关键配置（取 end 前 1 分钟即可）
for var in innodb_buffer_pool_size innodb_max_dirty_pages_pct innodb_io_capacity \
           innodb_io_capacity_max innodb_page_cleaners innodb_buffer_pool_instances \
           innodb_lru_scan_depth innodb_flush_neighbors; do
  python3 scripts/atomic/query_xray_metrics.py \
      --pql "mysql_global_variables_${var}{cluster_name=\"<cluster>\"}" \
      --start "<end前1分钟>" --end "<北京时间end>" --step 60 \
      --vmname "<master_vm_name>" --label "var_${var}" \
      --output <OUT_DIR> --run_id <RUN_ID>
done
```

用途：提供故障时段的系统资源和 InnoDB 引擎运行状态时序数据，辅助判断是 SQL 导致资源瓶颈，还是资源瓶颈导致 SQL 变慢。

**派生指标（Step 4 中计算）**：
- **Dirty Ratio** = `dirty_bytes / data_bytes × 100%`
- **Group Commit 效率** = `handler_commit_rate / os_log_fsyncs_rate`（txn/fsync）
- **Cache Miss Rate** = `bp_reads_rate / bp_read_requests_rate × 100%`
- **Data Written (MB/s)** = `data_written_rate / 1024 / 1024`

> **📦 交付物**：`<RAW_DIR>/query_xray_metrics_<label>.json`（每个指标一个文件）
>
> **✅ 验收条件**：
> - **核心组**：至少 ①②③ 采集成功（缺失任一则在报告标注"⚠️ 核心指标缺失"）
> - **扩展组**（路径 B）：至少 ⑥⑧⑩ 采集成功（缺失则无法构建 Buffer Pool 深度分析章节，降级标注）
> - **SQL 命令速率组**（路径 B）：⑱ 四条全部采集成功，否则无法识别归档任务型根因
> - **配置变量组**：采集失败时标注"⚠️ 配置参数未采集，建议人工确认"
> - **采集失败**：跳过该指标，在报告中标注"⚠️ 指标采集失败"，**不阻断流程**

---

**Step 3 · 并发采集 EXPLAIN + 表/索引统计**

以下所有任务并发执行，**全部完成**后才能进入 Step 4。

**对每条 TOP SQL（top1 / top2 / top3）执行 EXPLAIN**（先按清洗规则处理 SQL）：
```bash
python3 scripts/atomic/explain_sql.py \
    --cluster <cluster> --db <db> \
    --sql "<清洗后SQL>" --connector <slave_connector> \
    --label top1 \
    --output <OUT_DIR> --run_id <RUN_ID>
```

**对每张业务表执行表统计**：
```bash
python3 scripts/atomic/get_table_stats.py \
    --cluster <cluster> --db <db> --table <table> \
    --connector <slave_connector> \
    --output <OUT_DIR> --run_id <RUN_ID>
```

**对每张业务表执行索引统计**（table_stats 完成后取 table_rows 传入）：
```bash
python3 scripts/atomic/get_index_stats.py \
    --cluster <cluster> --db <db> --table <table> \
    --connector <slave_connector> \
    --table_rows <从 table_stats 取> \
    --output <OUT_DIR> --run_id <RUN_ID>
```

> **📦 交付物**：
> - `<RAW_DIR>/explain_top1.json`、`explain_top2.json`、`explain_top3.json`
> - `<RAW_DIR>/table_stats_<table>.json`（每张表一个）
> - `<RAW_DIR>/index_stats_<table>.json`（每张表一个）
>
> **✅ 验收条件**：
> - 每个 explain 文件存在（若 400 失败，记录失败原因，在报告第 5 章注明"EXPLAIN 采集失败：xxx"，不阻塞流程）
> - 每张业务表的 table_stats 文件存在且包含 `table_rows` 字段
> - 每张业务表的 index_stats 文件存在且包含至少一个索引条目

---

**Step 4 · 整合数据 & 分析**

> **⚠️ 禁止在 Step 0~3 全部通过验收前输出任何分析结论或报告内容。**

执行：
- 内存中合并 `table_stats_<table>.json` + `index_stats_<table>.json`，计算各索引区分度 = `cardinality / table_rows`
- 综合 slow_log_list（模板聚合）+ raw_slow_log（原始明细）+ explain + stats，识别持锁者、等锁受害者、数据倾斜
- 整合 2d Error Log、2e 活跃会话、2f 指标时序，交叉验证因果关系
- 按下方 **8 章节 HTML 规范** 组织全部内容

**路径 A（慢查询）分析侧重**：
- 核心聚焦 SQL 执行计划 + 索引区分度 + 锁链分析
- 2f 指标时序作为辅助验证（如 wait_free_rate > 0 说明慢 SQL 导致了 buffer pool 压力）
- 第 3 章根因以"哪条 SQL 导致问题"为核心

**路径 B（CPU 高）分析侧重**：
- 见下方「场景二：CPU 高诊断」中的 Step 4 专用分析视角
- 核心聚焦资源瓶颈（CPU/InnoDB/锁），SQL 作为验证
- 第 3 章根因以"什么资源瓶颈导致 CPU 升高"为核心

> **📦 交付物**：内存中完整的报告数据结构（供 Step 5 直接写 HTML）
>
> **✅ 验收条件**：
> - 已识别至少 1 个"持锁者"SQL（`lock_ratio < 5%` 且 `avg_query_time` 高，见 `references/pitfalls.md` 坑4）
> - 已计算所有业务表的索引区分度
> - 已整合 2d/2e/2f 辅助数据（采集失败的标注"未采集"）
> - 8 章节内容全部有对应数据填充（无数据时按降级原则处理，禁止黄色「未采集」框，见 `docs/report-spec.md §3.4`）

---

**Step 5 · 生成 HTML 报告并上传**

AI 直接编写完整 HTML 文件，遵循下方 **8 章节规范**，保存到：
```
<OUT_DIR>/report_<RUN_ID>.html
```

上传：
```bash
python3 scripts/common/dms_upload.py <OUT_DIR>/report_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-slow_query.html
```

> **📦 交付物**：
> - 本地文件：`<OUT_DIR>/report_<RUN_ID>.html`
> - DMS 文件 URL：从 `dms_upload.py` 输出中提取
>
> **✅ 验收条件**：
> - HTML 文件存在，大小 > 10KB
> - HTML 包含全部 8 个章节标题（`section-title` 共 8 个）
> - 文件 URL 已成功获取（`https://` 开头）
> - 在浏览器可正常渲染（无 JS 报错、无空白章节）

---

**Step 6 · 推送通知**

执行：
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url> \
    --top_sqls   "<TOP1 SQL摘要>|<avg_qt>s" \
                 "<TOP2 SQL摘要>|<avg_qt>s" \
                 "<TOP3 SQL摘要>|<avg_qt>s"
```

> **📦 交付物**：webhook 推送消息（含集群名、时间范围、TOP 3 慢 SQL 摘要、报告链接）
>
> **✅ 验收条件**：
> - 脚本输出包含 `✅ 推送成功`
> - 向用户回复最终报告 URL 和推送状态摘要


**Step 7 · 生成复盘报告并推送**

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

> ~~**⚠️ 已废弃**：`generate_process_review.py` 禁止调用。~~
>
> **复盘报告由 AI 直接生成 HTML**，规范见 `docs/process-review-spec.md`（7 章节）。
> 生成后文件路径：`<OUT_DIR>/report_process_review_<RUN_ID>.html`

```bash
# 上传 DMS（AI 生成 HTML 后执行）

# 2. 上传 DMS
python3 scripts/common/publish_report.py \
    --html_path <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --out_dir   <OUT_DIR> \
    --cluster   <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --path A --path_label "慢查询" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```

> **📦 交付物**：`report_process_review_<RUN_ID>.html`，DMS URL 已推送到群
>
> **✅ 验收条件**：
> - AI 生成复盘报告 HTML 文件存在（`<OUT_DIR>/report_process_review_<RUN_ID>.html`）
> - curl 响应 `"code":0`
> - 向用户同时回复主报告 URL 和复盘报告 URL
>
> **⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

**Step 8 · Skill 自迭代（挂载 skill-self-evolve）**

```bash
python3 scripts/common/trigger_self_evolve.py \
    --out_dir  <OUT_DIR> \
    --run_id   <RUN_ID>
```

> **行为说明**：
> - 若复盘报告不存在，AI 根据当前诊断上下文重新生成（参考 `docs/process-review-spec.md`）
> - 提示用户："🔄 诊断报告已就绪，是否触发 skill 自迭代？(y/N)"
> - 用户回复 `y` → 自动执行 parse → generate_patch → apply_patch → validate 四步
> - 用户回复 `N` 或不回复 → 静默跳过，不影响本次诊断产出
>
> **✅ 验收条件**：
> - 用户确认后，四个子步骤均输出 `✅`
> - `CHANGELOG.md` 有新增记录（时间戳在本次诊断之后）
>
> **⚠️ 容错**：任一子步骤失败时仅打印 warning，不影响主流程。

---

#### HTML 报告规范（8 章节，固定结构，内容由 AI 根据实际数据填充）

> **路径 A 专属章节内容定义**，优先级高于 `docs/report-spec.md` 通用描述；两者不一致时以本文件为准。
> 风格规范（色彩/布局/组件）统一遵循 `docs/report-spec.md §四`。

---

**§1 · 告警概览**

| KPI 字段 | 数据来源 | 备注 |
|---------|---------|------|
| 慢查询总数 | `get_slow_log_list.data.total` | 故障时段内 |
| 最大执行时长 | `top_sql[0].max_query_time` | 秒 |
| 最大扫描行数 | `top_sql[0].max_rows_examined` | |
| 受影响节点数 | `get_db_connectors.data[]` 长度 | 标注 master/slave |
| 行锁等待数 | `get_system_lock_status.data.row_lock_count`（若有） | |
| 故障等级 | AI 综合判断 P0/P1/P2 | |

KPI 格展示格式：`当前值 N（⚠️ 超过 monitoring_rules.md 规则X 阈值 M）`
P0 Checkbox（仅确认类，不含操作命令）：
- `☐ 确认持锁者身份（见§3分析结论）`
- `☐ 确认受影响业务服务（见§6）`
- `☐ 已通知业务方 / 联系 DBA 评估止血方案`

**降级**：KPI 未采集时显示「告警触发」，不用黄框。

---

**§2 · 故障时间线**

- 分钟级柱状图：X轴北京时间，Y轴慢查询数量（蓝色柱）+ 平均执行时长（橙色线）
- 数据来源：`get_raw_slow_log.data.timeline[]`
- 事件链关键节点：trigger（告警触发）→ root（持锁者 SQL 最早出现）→ effect（等锁堆积）→ recover（堆积消散）

**降级**：无时序数据时用纯文字事件链，标注「⚠️ 推断」。禁止用 AI 推断值构造坐标轴数据点。

---

**§3 · 根因分析**

三段式（强制，见 `report-risk-rules.md` 禁2）：
- **已确认证据**：有 raw 字段直接支撑（引用字段名+值）
  - 持锁者判断：`lock_ratio < 5%`（`avg_lock_time / avg_query_time`）AND `avg_query_time` 高 → 持锁者（见 `pitfalls.md` 坑4）
  - 等锁受害者：`lock_ratio > 80%` AND `avg_lock_time ≈ avg_query_time`
- **⚠️ 推断**：两个及以上字段交叉推导，必须写出推导链
- **已排除假说**：列出排查过但排除的方向及依据

根因归纳表：业务层/数据层/索引层/参数层，每行标优先级颜色。

**风控注意**：`lock_ratio < 20%` 是错的阈值，必须用 `< 5%`（见 `pitfalls.md` 坑4）。

---

**§4 · Top SQL 分布**

- 数据来源：`get_raw_slow_log.data.top_sql[]`
- 展示字段：`query_count` / `avg_query_time` / `max_query_time` / `avg_lock_time` / `avg_rows_examined` / XHS_SERVICE（正则提取）/ `lock%`（计算列）
- `sql_template` 截断时（myhub 注释头）：展示服务名+SQL类型+执行次数+扫描行，去掉 sql_template 列；改从 `details[].sql_text` 提取 SQL 类型（见 `pitfalls.md` 坑4 + 本次 ads_ad_core 案例）

---

**§5 · 表结构 & 执行计划**

- EXPLAIN 来源：`explain_top*.json`（已采集文件，非实时执行），必须注明「来源：explain_topN.json」
- 表统计：`table_rows` / `data_length(MB)` / `index_length(MB)` / `update_time`；索引区分度：`cardinality / table_rows`，< 5% 标红
- 分库分表集群（myhub/redhub）：`get-table-stats` 需传物理分片库名，返回 500 时切换为 `get-table-normal-info`（见 `pitfalls.md` 坑13）

**降级**：EXPLAIN 未采集时，从 `details[].rows_examined` 最高前 3 条推断目标表，标注「⚪ 推断值，建议 DBA 在 DMS 执行计划页面手动验证」，禁止黄框。

---

**§6 · 影响范围**

- 受影响节点：`get_db_connectors.data[]` 全部节点（vm_name + IP:Port + role）
- 受影响业务服务：`details[].sql_text` 正则提取 XHS_SERVICE，去重过滤 null
- 多分片集群：必须覆盖所有从库（见 `pitfalls.md` 坑12），§8 状态表展示覆盖率

---

**§7 · 改进建议**

P0/P1/P2/专业 四类卡片，每张含优先级标签 + 标题 + 描述。

**风控强制（见 `report-risk-rules.md` 禁1）**：
- P0 卡片中写**建议句式**：「建议 DBA 评估是否执行 xxx，执行前确认 yyy」
- 禁止命令句式：`立即执行：KILL xxx` / `立即执行：ANALYZE TABLE xxx`
- 每条建议末尾加：「⚠️ 执行前请重新确认当前集群状态，本建议基于采集时刻快照」
- 参考命令（KILL/ANALYZE）移入§8附录「参考命令」区

---

**§8 · 附录**

数据采集状态表（五列）：

| 数据项 | 接口/文件 | 状态 | 覆盖节点 | 采集时间窗口 |
|--------|---------|------|---------|------------|
| 慢查询列表 | get_slow_log_list | ✅/⚠️/⚪ | vm_name(IP:Port) | start~end (UTC+8) |
| 原机慢日志 | get_raw_slow_log | ✅/⚠️/⚪ | vm_name(IP:Port) | start~end (UTC，北京-8h) |
| ... | ... | ... | ... | ... |

- 覆盖率 < 100% 节点标 ⚠️
- 核心 SQL 样本：`rows_examined` 最高的原始 `sql_text`（`<pre>`）
- 参考命令区：高风险操作的参考命令（每条注明「⚠️ AI 不执行，执行前 DBA 确认」）
