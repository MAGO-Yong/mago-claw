# 常见坑 & 注意事项

## ⚠️ 坑1：慢日志接口必须传 UTC 时间

**现象**：`total_slow_queries = 1`，`start_offset_pct > 95%`  
**原因**：二分法把起始偏移定到文件末尾，实际没有扫到数据  
**正确做法**：入参 `start_time` 和 `end_time` 必须是 **UTC 时间**

```
北京时间 00:00:00 → UTC 传 前一天 16:00:00
北京时间 00:10:00 → UTC 传 前一天 16:10:00
```

验证方法：检查响应中的 `start_offset_pct`，正常应该 < 95%；如果接近 100%，说明时间传错了。

---

## ⚠️ 坑2：get-db-connectors 必须用 open-claw 路径，不能用 v1 路径

**现象**：用 `/dms-api/v1` 的 `get-db-connectors` 拿到 myhub LB 地址后，调 `get-table-stats` 报 `Incorrect database name`  
**原因**：myhub 中间件不支持 `information_schema` 查询  
**正确做法**：

```bash
# ✅ 用 open-claw 版（返回 CMDB 直连 slave IP）
curl "https://dms.devops.xiaohongshu.com/dms-api/open-claw/meta-data/mysql/get-db-connectors?..."

# ❌ 不要用（返回 myhub LB，不支持 information_schema）
curl "https://dms.devops.xiaohongshu.com/dms-api/v1/mysql/sql-query/get-db-connectors?..."
```

---

## ⚠️ 坑3：get-sql-explain 接口不加 EXPLAIN 前缀

**现象**：传 `"EXPLAIN UPDATE ..."` 报 SQL 语法错误  
**原因**：接口内部自动加 EXPLAIN，不需要也不能手动加  
**正确做法**：`sql_to_explain` 字段传原始 SQL，不带 `EXPLAIN` 前缀

---

## ⚠️ 坑4：lock_ratio 低 ≠ 无问题，可能是持锁者

反直觉：**lock_ratio 最低的 SQL 往往是根因**（持锁者），因为它几乎不等别人的锁，但自己持锁极长。  
等锁受害者的 lock_ratio 反而很高（80%~96%），因为大部分时间在等锁。

判断规则：
- `lock_ratio < 5%` + `avg_query_time 高` → **持锁者，根因**
- `lock_ratio > 80%` + `avg_lock_time ≈ avg_query_time` → **等锁受害者**
- heartbeat 被锁（`avg_lock_time > 10s`）→ 锁风暴已蔓延全局

---

## ⚠️ 坑5：rows_examined 峰值超过 table_rows 估算值

**原因**：`table_rows` 是 InnoDB 基于采样的估算值（`innodb_stats_persistent_sample_pages=20`），实际行数可能远高于估算。  
**意义**：当 `rows_examined > table_rows 估算值` 时，说明统计信息严重低估了表的实际规模，优化器的代价计算完全失真。  
**应对**：查 `index_stats` 的各列 `cardinality`，计算区分度，找出数据倾斜的列。

---

## ⚠️ 坑6：get-raw-slow-log 时间窗口限制 ≤ 10 分钟

`get-raw-slow-log` 接口要求 `start_time` 到 `end_time` 的差值 ≤ 10 分钟。  
如果故障窗口超过 10 分钟，需要分段查询（例如两次 5 分钟）然后合并分析。

---

## 关键接口速查

所有接口统一使用 `https://dms.devops.xiaohongshu.com`

| 接口路径 | 方法 | 用途 |
|----------|------|------|
| `/dms-api/open-claw/meta-data/mysql/get-raw-slow-log` | POST | 原机慢查询日志（UTC 入参）|
| `/dms-api/open-claw/meta-data/mysql/get-db-connectors` | GET | 获取直连 connector（供 stats 接口用）|
| `/dms-api/open-claw/meta-data/mysql/get-table-stats` | GET | 表行数、大小、update_time |
| `/dms-api/open-claw/meta-data/mysql/get-index-stats` | GET | 索引基数 / 区分度 |
| `/dms-api/open-claw/meta-data/mysql/explain-sql` | POST | EXPLAIN 执行计划（不加 EXPLAIN 前缀）|
| `/dms-api/v1/mysql/base/instance/get-variables` | GET | innodb_stats_* 参数查询 |
| `/dms-api/v1/goc/alarm/get-event-detail` | GET | GOC 告警详情 |

---

## ⚠️ 坑7：Phase 0 问题类型识别失误（2026-03-26 实战）

**现象**：用户说"慢查询告警"，但 CK 聚合慢查询为 0，原机慢日志也为 0  
**原因**：
1. CK 只收录 ≥1s 的慢查询，DTS Checksum（100~200ms）完全不在 CK 里
2. 原机慢日志查的是主库 hostname，但 DTS Checksum 只在从库产生慢查询
3. 两路采集同时失效，导致误判为"无慢查询问题"

**正确做法**：
- 双路采集均为 0 时，触发动态回溯，不要轻易结案
- 补充探测 D（get_slave_status），确认是否是主从延迟或复制断裂
- 检查 `file_size_mb`，如果为 0.0，说明节点可能 Crash 或 slow_query_log=OFF

---

## ⚠️ 坑8：动态回溯触发信号速查（Phase 0）

排查途中发现以下信号，立即暂停当前路径，保留已采集数据，重走 Phase 0 分诊：

| 信号 | 出现步骤 | 可能真实类型 |
|------|---------|------------|
| CK + 原机慢日志双路均为 0 | Step 2 | 非慢 SQL（磁盘满/Crash/主从延迟）|
| `file_size_mb = 0.0` | Step 2b | slow_query_log=OFF 或节点 Crash |
| `get_db_connectors` Invalid param | Step 1 | 集群名/db 有误 |
| 大量 `Waiting for relay log` | 路径 B | 主从延迟 |
| `Slave_SQL_Running=No` / `Last_Error` 非空 | 路径 C | 复制链路断裂 |
| 节点完全不可达 | 任意 | Crash |
| 磁盘用量 > 95% | 路径 D | 磁盘 P0，可与其他类型并存 |

---

## ⚠️ 坑9：复制中断 vs 复制延迟的快速识别（路径 C1 vs C2）

**现象**：用户报告"主从延迟"，但实际是复制线程已停止  
**区分方法**：
- 先看 `Slave_SQL_Running` / `Slave_IO_Running`：有一个为 `No` → **复制中断（路径 C2）**
- 都是 `Yes` 但 `Seconds_Behind_Master > 30` → **复制延迟（路径 C1）**
- 延迟路径（C1）的诊断链对中断场景无效：延迟看 relay log 积压，中断要看 `Last_Error`

**正确做法**：
- 中断 → 读 `Last_SQL_Error` / `Last_IO_Error` → 识别错误类型（主键冲突/GTID断层/网络）
- 绝不跳过 `Last_Error` 直接建议重启 SQL Thread（跳过的事务会丢数据）

---

## ⚠️ 坑10：带宽告警 DTS 场景的误判

**现象**：带宽告警，AI 判断为"业务异常"，实际是 DTS 迁移任务正常拉取 binlog  
**原因**：DTS binlog 拉取会产生持续高出方向流量，外观上与大查询难以区分  
**正确做法**：
1. 先查 processlist 确认是否有 `Command=Binlog Dump` 线程
2. 核实 DTS 任务时间表（向用户确认是否有计划内迁移）
3. 持续型流量（pattern=sustained）≠ 异常，突发型（pattern=burst）才更可疑
4. 结论区分：DTS 迁移导致 → 标注"运维操作，评估是否超机器上限"，不要定性为"业务问题"

---

## ⚠️ 坑11：连接数异常 ≠ CPU 高（路径 B2 独立于路径 B）

**现象**：`total_active > 100` 告警，AI 直接进路径 B（CPU 高），但 CPU 只有 40%  
**原因**：连接堆积可以独立于 CPU 高发生（连接池泄漏、慢查询堵塞线程池）  
**正确做法**：
- `total_active > 100` 且 `cpu_usage < 70%` → **路径 B2（连接堆积）**
- `total_active > 100` 且 `cpu_usage > 70%` → 路径 B（CPU 高），连接是结果不是原因
- 连接堆积重点看：Sleep 连接持续时间、锁等待比例、来源 User/Host

---

## ⚠️ 坑12：多分片集群必须覆盖所有从库节点

**现象**：只采集第一个从库的慢日志，漏掉了最严重的分片  
**教训来源**：2026-03-27 redtao_tns 分析，只采集 5fpli-2（_00510/_00766）  
  → 漏掉 5fpli-3（_00875/_00507），后者 rows_examined=11,922,717（是前者的 3000 倍）  
**正确做法**：
- `get_db_connectors.py` 现已返回所有 slave 节点列表（`list_slave_connectors`）
- 诊断时对所有从库并发采集慢日志，合并后按 `rows_examined` 降序排列
- 报告中明确注明覆盖了哪些节点，避免漏掉高负载分片

---

## ⚠️ 坑13：get_table_stats / get_index_stats 在分库分表集群报错，误判为接口废弃

**现象**：对分库分表集群（如 redtao_tns）调用 `get-table-stats` / `get-index-stats`，
返回 500 `Unknown database 'redtao_tns'`，误以为接口 404 废弃

**根因**：这两个接口需要通过 `connector`（物理节点 IP:Port）直连，
分库分表集群的**逻辑库名**（如 `redtao_tns`）在物理节点上不存在，
物理节点上只有分片库名（如 `redtao_tns_p00000`）

**接口实际状态**：
- `GET /dms-api/open-claw/meta-data/mysql/get-table-stats` — ✅ **正常可用**
- `GET /dms-api/open-claw/meta-data/mysql/get-index-stats` — ✅ **正常可用**，返回真实 cardinality
- `GET /dms-api/v1/mysql/sql-query/get-table-normal-info` — 也可用，但无需 connector，精度略低

**正确用法**：
- 普通集群：直接传逻辑库名，正常工作
- 分库分表集群（redhub/myhub 类型）：
  - 用逻辑表名调用 `get-create-table` 获取 DDL（逻辑层可用）
  - `get-table-stats` / `get-index-stats` 需传**物理分片库名**（如 `redtao_tns_p00000`）才能正确执行
  - 或改用 `get-table-normal-info`（无需 connector，直接传逻辑库名）

**历史错误**：2026-04-01 将两个脚本错误改为 DDL 解析方案，导致 cardinality 丢失，已于当天回滚


---

## ⚠️ 坑14：CK 有慢查询记录但原机慢日志为空 — long_query_time 差异

**现象**：CK 聚合显示大量慢查询（如 50万次），但原机 slow log 里一条目标 SQL 都没有

**根因**：
- MySQL `long_query_time` 决定原机 slow log 的记录门槛（通常 0.5s~2s）
- CK 平台的采集门槛更低（可能 0.1s 甚至更低），所以 CK 能采到但 slow log 不记录
- 症状：`file_size_mb` 不为 0（说明慢日志功能正常），但指定时段内 association/目标 SQL 为 0

**诊断时的处理**：
1. 不要误判为"采集失败"——是 SQL 本身 Query_time < long_query_time
2. 改从 DDL 结构 + CK 执行次数 + 业务侧 metrics 推断影响
3. 若需精确 rows_examined，建议向业务方申请临时调低 `long_query_time=0.1`，低峰期抓一次
4. 在报告中明确注明"原机慢日志无记录，原因为 Query_time < long_query_time，以下分析基于 DDL 推断"

**pitfall 识别信号**：
- `file_size_mb > 0`（慢日志正常工作）
- `total_slow_queries = 0`（目标时段无记录）
- CK 同时段有大量同表的慢查询计数

---

## ⚠️ 坑15：INSERT IGNORE 比普通 INSERT 更容易触发 System lock

**现象**：同一张分表，普通 `INSERT INTO ... VALUES (...)` 并发无问题，改成 `INSERT IGNORE` 后并发写入触发 System lock 堆积，活跃连接数超阈值告警

**根因**：MySQL 内部将 `INSERT IGNORE`（以及 `INSERT ... SELECT`、`REPLACE INTO`、`LOAD DATA`）归类为 **bulk insert**（因为行数不确定——可能插入 0 行或 1 行）。在不同的 `innodb_autoinc_lock_mode` 下：

| 语句类型 | mode=0 | mode=1 | mode=2 |
|---------|--------|--------|--------|
| 普通 `INSERT VALUES (...)` | 表级锁 | 轻量 mutex | 轻量 mutex |
| `INSERT IGNORE` | 表级锁 | **表级锁（！）** | 轻量 mutex |
| `INSERT ... SELECT` | 表级锁 | **表级锁（！）** | 轻量 mutex |
| `REPLACE INTO` | 表级锁 | **表级锁（！）** | 轻量 mutex |

**关键差异**：mode=1（连续，MySQL 5.7 默认值）下，普通 INSERT 已优化为轻量锁，但 INSERT IGNORE 仍持**表级 AUTO-INC 锁**直到语句结束，高并发时退化为串行。

**识别信号**：
- `SHOW PROCESSLIST` State = **System lock**（不是 Waiting for lock，不是 Locked）
- SQL 类型为 INSERT IGNORE / REPLACE / INSERT ... SELECT
- `Query_time = 0s`，`Lock_time = 0s`（等待时间不计入，不进慢日志）
- CPU/IOWait 极低（非资源瓶颈）
- `SHOW VARIABLES LIKE 'innodb_autoinc_lock_mode'` 返回 0 或 1

**诊断时的处理**：
1. 确认 `innodb_autoinc_lock_mode` 值（0 或 1 → 需升级为 2）
2. 不要去找慢日志——System lock 等待不记录在慢日志中，这是正确行为
3. 通过 `SHOW ENGINE INNODB STATUS\G` 找 AUTO-INC 锁等待记录（关键字 `auto_increment`）
4. 统计 PROCESSLIST 中 System lock 的表名，确认是否集中在同一分表号段（热点信号）

**处置方案**（优先级顺序）：
1. **立即**：调整 `innodb_autoinc_lock_mode=2`（交错模式），消除 AUTO-INC 表级锁
2. **立即**：调用方改批量写入（多行合并一次 INSERT，减少锁申请次数）
3. **本周**：调用方对同一分表并发写入限流（令牌桶，≤20 QPS/分表）
4. **排期**：评估去掉自增主键，改用业务主键（user_id+create_time），彻底消除 AUTO-INC 锁

**预防监控**：
- 添加 PromQL：`SHOW PROCESSLIST` State='System lock' 数量 > 3 → P1 预警，> 10 → P0
- 比"活跃连接数超阈值"提前 1~2 分钟感知，变滞后告警为预警

**实战案例**：2026-04-01 sns_user_extra 集群 lshm-db-user-9，INSERT IGNORE INTO user_location_1d? 6条并发 System lock，活跃连接数从正常值升至 125+，P0 告警，客户可感知。innodb_autoinc_lock_mode=1 是根因之一。
