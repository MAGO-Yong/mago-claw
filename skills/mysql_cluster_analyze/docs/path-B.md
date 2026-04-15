### 场景二：CPU 高诊断（路径 B）

> **数据采集与路径 A 完全一致**：Step 0 → Step 1 → Step 2（2a~2f） → Step 3 → Step 5 → Step 6。
> 其中 Step 2f **扩展组必采**。
> **区别在 Step 4 分析视角 + 报告 8 章节内容定义**。

---

#### ⚡ CDB 环境识别（Phase 0-B 后立即判断）

`get_db_connectors` 返回节点 vmId 含 `cdbro-` / `cdb-` → 标记 `cluster_type=CDB`，执行以下跳过规则：

| 步骤 | CDB 行为 | 替代 |
|------|---------|------|
| Step 2a `get_raw_slow_log` | ❌ 跳过（HTTP 500） | Phase 0-A `get_slow_log_list` CK 聚合已覆盖 |
| Step 2d `get_error_log` | ❌ 跳过（不可达） | 报告标注「CDB 盲区」 |
| Step 2f `query_xray_metrics` | ❌ 跳过（0 series） | Phase 0-C `get_active_sessions` + EXPLAIN 替代 |

> **直接跳过，不等失败**（避免 30s+ 无效等待）。根因结论不受影响：CK 聚合 + EXPLAIN + 活跃会话快照三路已足够。

---

#### Step 4 · 整合数据 & 分析（路径 B 专用）

> ⚠️ 路径 B 的分析核心是 **InnoDB 引擎状态 + 系统资源**，不是 SQL。
> 必须先完成下方 ①~⑤ 全部分析步骤，再写报告。

> 📌 **连接数时序数据来源说明**：路径 B 的连接数分析使用 `query_xray_metrics` 采集的 `threads_connected` 指标（15s 粒度，完整时序，已在 Step 2f 采集）。`get_connection_timeline.py` 是 Layer 1 点查工具，输出格式与 xray 指标不同，**不在路径 B 的 SOP 中使用**。

**① 构建 15s 多维指标矩阵（核心）**

从 2f 各指标 JSON 中，**按 timestamp 对齐**构建时序矩阵表。每行一个 15s 时间点，列为：

| 时间（北京） | handler_commit/s | group_commit 效率 | dirty(GB) | dirty_ratio% | wait_free/s | pages_free | pages_flushed/s | data_written(MB/s) | threads_running | threads_connected | 事件 |
|---|---|---|---|---|---|---|---|---|---|---|---|

构建方法：
- `handler_commit/s` = `handler_commit_rate` 的值
- `group_commit 效率` = `handler_commit_rate / os_log_fsyncs_rate`（txn/fsync，正常 > 3）
- `dirty(GB)` = `dirty_bytes / 1024^3`
- `dirty_ratio%` = `dirty_bytes / data_bytes × 100`
- `wait_free/s` = `wait_free_rate` 的值（已在 PromQL 中用 `rate(...[1m])` 转换）
- `pages_free` = `pages_free` 的值（= 0 是核心异常信号）
- `pages_flushed/s` = `pages_flushed_rate` 的值
- `data_written(MB/s)` = `data_written_rate / 1024^2`
- `threads_running` / `threads_connected` = 直接取值
- `事件` = 从 2d Error Log / 2e 活跃会话中按时间匹配填入

> 此矩阵直接用于报告第 2 章的时间线表格。

**② InnoDB 健康评估**

从矩阵和配置变量中评估以下维度：

> **⚠️ 阈值参考**：以下阈值基于 redtao_antispam（82GB buffer pool、SSD、高写入负载）实战校准。
> 不同集群的 buffer pool 大小、磁盘类型、写入量级不同，阈值需按实际情况调整。

| 维度 | 健康 | 亚健康 | 危险 |
|------|------|--------|------|
| Dirty Ratio | < 60% | 60-75% | > 75%（超过 max_dirty_pages_pct） |
| Free Pages | > 10,000 | 1,000-10,000 | < 1,000 或 = 0 |
| Wait Free | = 0 | 1-50/s | > 50/s（用户线程在做 page cleaner 的工作）|
| Page Cleaner 效率 | pages_flushed > 20,000/s | 10,000-20,000/s | < 10,000/s |
| Group Commit 效率 | > 4 txn/fsync | 2-4 | < 2（事务延迟高） |
| Cache Miss Rate | < 2% | 2-5% | > 5%（大量磁盘读，加剧 free page 压力）|
| Redo Log 压力 | log_waits_rate = 0/s | - | log_waits_rate > 0/s（持续有新增等待）|
| IO 排队 | os_log_pending_fsyncs = 0 | 偶尔 > 0 | 持续 > 0 |

**配置合理性评估**（从 ⑱ 配置变量组获取）：
- `innodb_page_cleaners` vs `innodb_buffer_pool_instances`：应 1:1，小于 1:1 表示部分 instance 无专属 cleaner
- `innodb_buffer_pool_size` vs 实际 `data_bytes`：buffer pool 被数据页占满（free=0）则需扩容
- `innodb_lru_scan_depth`：控制 LRU flush 吞吐的关键参数，默认 1024
- `innodb_flush_neighbors`：SSD 应为 0

**③ 因果链推理（核心）**

> 判断顺序：**写入型负载** → InnoDB 资源层 → SQL 层（三类互斥，按序命中第一条即止）

- **写入型负载突增**（InnoDB 无异常）：wait_free=0 且 row_lock_waits≈0，且 INSERT/DELETE irate 同一 15s 窗口从 0 跳到 N/s（比值≈1.0 = 归档任务）→ 根因是批量写入/归档任务，建议错峰/限速

- **SQL → 资源**（根因在 SQL 层）：
  - 慢 SQL 出现时间 **早于** CPU/wait_free 升高
  - wait_free 在告警前为 0，告警后才升高
  - 业务 SQL 的 rows_examined 异常大
  → 转路径 A 的 SQL 分析视角

- **资源 → SQL**（根因在 InnoDB/资源层）：
  - wait_free **在告警前已持续非零**（前置亚稳态）
  - pages_free = 0 在告警前已成立
  - 慢 SQL 数量在 CPU 升高后才激增
  → 根因是 Buffer Pool / InnoDB 配置问题

- **正反馈循环检测**（参考 redtao_antispam 案例）：
  ```
  wait_free > 0 持续 N 分钟（亚稳态运行，零安全裕度）
    → 随机 mutex 竞争抖动
    → 单事务延迟增加 → group commit 效率下降
    → 同时在线事务增多 → threads_running ↑
    → 更多线程竞争 LRU mutex → 正反馈
    → page_cleaner 自身也拿不到 mutex → 刷脏吞吐崩溃
    → 级联瘫痪
  ```
  判断信号：
  - wait_free 在 **告警前 30 分钟+** 就持续非零 → 亚稳态确认
  - group_commit 效率在触发点突降 > 10% → 正反馈开始
  - threads_running 突然飙升 → 线程风暴
  - pages_flushed 突然暴跌 → page cleaner 饥饿（对应 mysqld.log 中的 page_cleaner 告警）

**④ Error Log 深度分析**

从 2d Error Log 中提取并分类：

| 日志类型 | 关键词 | 含义 |
|---------|--------|------|
| Page Cleaner 饥饿 | `page_cleaner: 1000ms intended loop took` | 循环耗时远超 1s，page cleaner 被 mutex 阻塞 |
| 从库断连 | `zombie dump thread`, `failed on flush_net()` | 主库过载到无法发送 binlog |
| 监控断连 | `Got an error reading communication packets` | 所有监控/管理连接同时超时 |
| OOM | `Out of memory`, `killed process` | 内存不足导致进程被杀 |
| 死锁 | `LATEST DETECTED DEADLOCK` | 事务死锁 |

对 page_cleaner 告警，**必须计算等效吞吐**：
```
等效吞吐/s = (flushed + evicted) / 实际耗时(s)
正常吞吐 ≈ 20,000-25,000/s
```
等效吞吐暴跌 > 90% → 确认 page cleaner 饥饿，可作为报告第 5 章的核心证据

**⑤ 假说排除矩阵**

构建排除表，**每个假说必须有对应指标证据**：

| 假说 | 证据指标 | 判定 |
|------|---------|------|
| Redo log sync flush | checkpoint_age vs sync 阈值, log_waits_rate | 排除/成立 |
| Dirty pages 缓慢累积 | dirty_bytes 时序趋势（上升 vs 稳态振荡） | 排除/成立 |
| 硬件 I/O 抖动 | data_write_time（如可用）, os_log_pending_fsyncs | 排除/成立 |
| Redo log I/O 阻塞 | os_log_pending_fsyncs, os_log_pending_writes | 排除/成立 |
| 行锁竞争 | row_lock_waits_rate | 排除/成立 |
| io_capacity_max 不足 | pages_flushed vs io_capacity_max（LRU flush 不受此限） | 排除/误解澄清 |
| max_dirty_pages_pct 过高 | dirty_ratio vs max_dirty_pages_pct（page cleaner 已全力刷）| 排除/成立 |
| 慢 SQL 根因 | 慢 SQL 出现时间 vs 指标异常时间 | 排除/成立 |

> ⚠️ 此表直接输出到报告第 3 章的"排除的假说"小节。

---

#### 路径 B 专用 · 8 章节 HTML 报告规范

> 路径 B 的报告结构与路径 A 的 8 章节一一对应，但第 1/2/3/4/5 章的**内容定义完全不同**。
> 样式风格统一使用亮色主题，见 `docs/report-spec.md §四`（v7 DBA 版基准）。

**Banner**：
- 标题：`<cluster> 根因分析报告`
- 副标题：一句话根因
- 左侧 badge：路径标签（如「路径 B · CPU高」）+ 严重度（P0/P1/P2）
- **右侧 `.header-meta` 竖列（必须包含，对齐 ads_ad_core 参考样式）**：

| 字段 | 内容 |
|------|------|
| 故障时间 | 告警触发时间（北京时间） |
| 节点 | vm_name（IP:Port） |
| Skill | mysql-monitor |
| 贡献团队 | 关系数据库团队 |
| 诊断耗时 | 从 run_meta start_time 到报告生成时间（分:秒） |
| Token 消耗 | 从 run_meta 读取，无则显示「-」 |

- 布局：**全宽铺满**，body padding 48px，不设 max-width（避免宽屏两侧留白）

**第 1 章 · 告警概览**

KPI 格子（红/橙/绿色标注健康度）：

| KPI | 数据来源 |
|-----|---------|
| Dirty Ratio | dirty_bytes / data_bytes |
| Free Buffers | pages_free 的值 |
| wait_free/s | wait_free rate |
| Page Cleaner 循环延迟 | 2d Error Log 中 page_cleaner 告警（无则标"未采集"）|
| INSERT/Commit 跌幅 | handler_commit_rate 的 max→min 变化% |
| 线程风暴峰值 | threads_running max |
| 稳态 INSERT/Commit | handler_commit_rate 告警前均值 |
| 磁盘写延迟 | os_log_pending_fsyncs（= 0 标绿"正常"）|
| Redo Log Waits | log_waits_rate（= 0 标绿"正常"，> 0 标红"等待中"）|

关键配置表（从 ⑱ 配置变量组获取）：

| 参数 | 值 | 评估（标签颜色） |
|------|---|---------|
| innodb_buffer_pool_size | X GB (Y pages) | 对比 data_bytes 评估是否偏小 |
| innodb_max_dirty_pages_pct | N | 对比实际 dirty_ratio 评估 |
| innodb_io_capacity / max | N / M | 说明仅控制 flush list |
| innodb_page_cleaners | N | 对比 buffer_pool_instances |
| innodb_buffer_pool_instances | N | - |
| innodb_lru_scan_depth | N | 说明控制 LRU flush 吞吐 |
| innodb_flush_neighbors | N | SSD 应为 0 |

**第 2 章 · 故障时间线**

1. **15s 粒度关键指标矩阵**（来自 Step 4 ① 的矩阵表）：
   - 每行一个 15s 时间点
   - 关键变化行高亮（橙色 = 触发、红色 = 崩溃、紫色 = 影响、绿色 = 恢复）
   - 每行最后一列"事件"关联 Error Log / 活跃会话异常

2. **事件链**（timeline 可视化）：
   - 每个关键节点一条：时间 + 标题 + 描述
   - 节点类型/颜色：
     - `trigger`（橙）：前置亚稳态运行阶段
     - `root`（红）：触发正反馈的拐点
     - `effect`（紫）：级联影响（从库断连、线程风暴、page cleaner 饥饿）
     - `recover`（绿）：恢复阶段

**第 3 章 · 根因分析**

1. **一句话根因**（红色高亮框）
2. **三层证据链**（每层一个证据框 `<div class="ev">`）：
   - 证据 A：xray 15s 指标数据（如 wait_free 持续非零 N 分钟）
   - 证据 B：活跃会话快照（如 SHOW GLOBAL STATUS 卡 N 秒）
   - 证据 C：mysqld.log 告警（如 page_cleaner 循环 21-47s）
3. **正反馈循环机制图**（ASCII 流程图，`<pre>` 块）⚠️ 此图属于「推断」段（内核机制，不可直接观测），必须在图上方标注「⚠️ 推断：以下为 InnoDB 内核行为推断，基于 wait_free / dirty_ratio 等指标间接推导」，不得放入「已确认证据」区
4. **"为什么是这个时间点"分析**（橙色框）
5. **排除的假说表**（来自 Step 4 ⑤ 的假说排除矩阵）

**第 4 章 · Buffer Pool 深度分析**（替代路径 A 的"慢查询 Top 10 分布"）

1. **容量分布可视化**（ASCII 柱状图）：
   ```
   ██████████████████████████████████ Dirty XX GB (XX%)
   ██████ Clean XX GB (XX%)
   ▏ Free ~0 (XX%)
   ```
2. **Dirty Bytes 15s 时序表**：时间 + dirty(GB) + Δ(MB/15s) + 说明
3. **Buffer Pool Cache Miss Rate**：
   - 逻辑读：`mysql_global_status_innodb_buffer_pool_read_requests`（counter，取 rate）
   - 物理读：`mysql_global_status_innodb_buffer_pool_reads`（counter，取 rate）
   - miss_rate = `reads_rate / read_requests_rate × 100%`
   - 降级：若上述 label 在 xray_metrics 未采集，标注「Buffer Pool 读命中率未采集，建议通过 DMS 监控面板查看」，不展示空格
4. **刷脏吞吐分解**（若数据充分）：
   - Flush list flush（受 io_capacity_max 限制）
   - LRU list flush（受 lru_scan_depth 控制）
   - 用户线程 single-page flush（wait_free）

**第 5 章 · mysqld.log / InnoDB 内核分析**（替代路径 A 的"表统计信息 & EXPLAIN"）

1. **Page Cleaner 告警表**（若 2d Error Log 采集到）：
   | 时间 | 计划 1s 实际耗时 | flushed | evicted | 等效吞吐/s |
   - 等效吞吐 = (flushed + evicted) / 实际耗时
   - 正常 vs 故障对比，计算暴跌百分比

2. **从库 Binlog Dump 异常**（若 Error Log 中有 zombie dump / flush_net 失败）
3. **监控连接断开**（若 Error Log 中有 communication packets 错误）

> 若 2d Error Log 采集失败（API 未部署），本章内容标注"⚠️ Error Log 采集失败，以下分析基于 xray 指标推断"，仍可从指标时序推断 page cleaner 行为（pages_flushed 突降 = page cleaner 饥饿的间接证据）

**第 6 章 · 影响范围**（与路径 A 相同结构，但内容侧重不同）

| 维度 | 内容 |
|------|------|
| 受影响实例 | 主库 + 从库 |
| 从库影响 | 是否 binlog dump 断连、复制延迟 |
| INSERT/Commit 跌幅 | handler_commit 正常值 → 最低值，跌幅% |
| 线程风暴 | threads_running 正常值 → 峰值 |
| 连接暴增 | threads_connected 变化 |
| 监控失联 | 监控连接是否超时断开 |
| 故障持续时间 | 从触发到恢复 |
| 数据完整性 | 事务最终状态 |
| 故障等级 | P0/P1/P2 |

**第 7 章 · 改进建议**

卡片网格布局，必须包含：
- **无效建议排除**（橙色框）：列出对本案例无效的常见建议（如"调高 io_capacity_max"——仅管 flush list，LRU flush 不受此限）
- **P0（立即）**：
  - `innodb_page_cleaners` 调整（若 < buffer_pool_instances）
  - `innodb_buffer_pool_size` 扩容（根据 dirty ratio 和 free pages 计算目标值）
  - 具体公式：`目标 = dirty_bytes / 0.65`（使 dirty ratio 稳态 < 65%）
- **P1（本周内）**：
  - `innodb_lru_scan_depth` 调整
  - 添加 `wait_free` 监控告警（WARNING > 50/s 持续 5 分钟，CRITICAL > 200/s 持续 1 分钟）
  - 添加 `page_cleaner loop` 延迟告警（CRITICAL > 5000ms）
- **P2（迭代内）**：
  - 降低单节点写入压力（分片拆分 / 批量 INSERT 合并）
  - 评估非双1配置的可行性

**第 8 章 · 附录**

1. **数据来源说明**：每类数据对应的接口/脚本/粒度
2. **完整证据链**（红色框 `<pre>` 块）：
   - `[配置根因]` → `[稳态症状]` → `[触发]` → `[级联]` → `[page_cleaner 饥饿]` → `[旁证]` → `[恢复]`
   - 最终结论指向唯一瓶颈点
3. **关键 PromQL**：列出本次分析用到的所有 PromQL 查询表达式


**Step B4** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step B5** 生成复盘报告并推送

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
    --path B --path_label "CPU 高" \
    --severity P1 \
    --root_cause "<根因一句话>" \
    --p0_action  "<P0 处置建议>" \
    --meta_key   review_report_url
```
验收：AI 生成复盘报告 HTML 后，`publish_report.py` 输出 `✅ 上传成功` + `✅ 推送成功`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

### 场景三：主从延迟诊断（路径 C）
