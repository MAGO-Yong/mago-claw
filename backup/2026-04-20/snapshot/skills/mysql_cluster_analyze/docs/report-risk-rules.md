# report-risk-rules.md · 报告生成风控规则集

> **使用方式（强制）**：AI 在生成任何路径报告的 HTML 之前，必须逐条对照本文档第一层「输出禁止项」核查即将生成的内容，确认无违规后才能执行 `write` 文件。
>
> **优先级**：本文档优先级高于 report-spec.md 和各路径 path-*.md 中的所有描述。出现冲突时，以本文档为准。

---

## 第一层：输出禁止项（生成前逐条核查）

以下内容**禁止出现**在报告的 P0 Checkbox（§1 Banner 底部）和 §7 改进建议的 P0/P1 段落中。违反任一条，报告视为无效，必须重新生成。

### 禁1：写操作命令句式

**触发条件**：报告里出现以下任意一种句式：
- 「立即执行：`PURGE BINARY LOGS TO ...`」
- 「立即执行：`SET GLOBAL SQL_SLAVE_SKIP_COUNTER=1; START SLAVE`」
- 「立即执行：`SET GTID_NEXT='...'; BEGIN; COMMIT`」
- 「立即执行：`KILL <thread_id>`」
- 「立即执行：`STOP SLAVE`」
- 「立即执行：`SET GLOBAL innodb_io_capacity=...`」
- P0 Checkbox 里有动词命令句（「执行 xxx」「删除 xxx」「停止 xxx」）

**违反后果**：DBA 误以为 AI 已验证操作安全性，直接执行 → 可能导致复制中断、数据丢失、集群写入失败。

**正确做法**：
- 操作类建议一律改为建议句式：「建议 DBA 评估是否执行 xxx，执行前确认 yyy」
- P0 Checkbox 内容限定为**确认类**：「☐ 确认持锁者身份」「☐ 确认影响范围」「☐ 联系高级 DBA 评估恢复方案」
- 命令参考（供 DBA 知晓操作方式）可出现在 **§8 附录** 的「参考命令」区，附注「⚠️ 执行前请 DBA 人工确认当前集群状态」

**禁止 vs 允许边界**：

| 禁止（命令句式） | 允许（建议句式） |
|---------------|--------------|
| `立即执行：PURGE BINARY LOGS TO 'mysql-bin.00100'` | `建议 DBA 设置 binlog_expire_logs_seconds，让 MySQL 自动安全清理` |
| `P0：KILL thread_id=1234` | `建议 DBA 评估是否 KILL 以下连接（确认业务影响后执行）：thread_id=1234` |
| `执行 STOP SLAVE SQL_THREAD` | `建议 DBA 确认 Last_SQL_Error 后，评估是否暂停 SQL Thread` |
| `SET GLOBAL SQL_SLAVE_SKIP_COUNTER=1` | `如需跳过事务，参考命令见§8附录，执行前必须确认 Last_Error 类型` |

---

### 禁2：推断写成结论

**触发条件**：报告 §3 根因分析里，将 AI 的推断性判断以确定性语气输出，如：
- 「根因是：xxx」（无证据字段直接支撑）
- 「持锁者是：adcenter-scheduler」（基于正则推断，非直接字段）
- 「Buffer Pool 发生了正反馈循环」（内核机制，不可直接观测）

**违反后果**：DBA 信任 AI 结论，跳过自身验证，按错误根因处置。

**正确做法**：
- 有 raw 字段直接支撑的：写「已确认：xxx」
- 逻辑推断的：写「⚠️ 推断：xxx（基于 yyy 字段间接推断，建议 DBA 确认）」
- 内核机制解释（如正反馈循环图）：放在「推断」段，不放「已确认证据」段

---

### 禁3：误报数据时效性

**触发条件**：报告用现在时态描述集群状态：
- 「当前有 16 条行锁等待」
- 「现在 CPU 使用率 78%」

**违反后果**：DBA 阅读报告时，集群状态可能已变化。按旧状态操作（KILL 已消失的连接、PURGE 从库已追上的 binlog）导致误操作。

**正确做法**：
- 所有状态描述用过去时态：「采集时刻（HH:MM:SS）有 16 条行锁等待」
- §1 Banner 必须显著标注数据采集时间：「数据采集时间：YYYY-MM-DD HH:MM:SS（北京时间）」
- §7 每条建议前加：「⚠️ 执行前请重新确认当前集群状态，本建议基于采集时刻快照」

---

### 禁4：分型不确定时给恢复命令

**触发条件**（路径 C2 专属）：
- `Last_SQL_Error` 为空，或错误码不在已知列表（主键冲突/GTID断层/网络/权限）
- 中断类型无法唯一确认

**违反后果**：给出错误恢复命令（如把 GTID 断层误判为主键冲突），执行后事务被跳过，数据永久丢失且无法通过重建从库恢复。

**正确做法**：
```
⚠️ 复制中断类型无法根据当前采集数据确认。
禁止执行任何 SQL Thread 操作。
请 DBA 登录节点执行 SHOW SLAVE STATUS\G 获取实时 Last_SQL_Error 后再判断。
```
宁可不给建议，也不给错误建议。

---

### 禁5：DTS 运维行为误报为异常

**触发条件**（路径 F 专属）：
- processlist 里有 `Command=Binlog Dump`
- 尚未向用户确认是否有计划内 DTS/Checksum 任务

**违反后果**：DBA 按报告建议 KILL DTS 连接，中断正在进行的数据迁移，可能导致数据不一致，迁移任务需要人工重新评估。

**正确做法**：
- 发现 `Command=Binlog Dump` 时，先在报告 §3 输出：「⚠️ 检测到 Binlog Dump 连接，疑似 DTS/主从复制流量，建议确认是否为计划内运维操作后再决定处置方向」
- 确认是计划内操作后，标注「当前带宽占用为计划内 DTS 操作」，不定性为异常
- 未确认前不给任何处置建议

---

## 第二层：必须标注项（生成时随手检查）

| 场景 | 标注要求 |
|------|---------|
| §3 推断性判断 | 加 `⚠️ 推断：` 前缀 |
| §1 所有 KPI 数值 | 加采集时间戳，加 vs 监控阈值对比（引用 monitoring_rules.md 规则编号） |
| EXPLAIN 来自已采集文件 | 注明「来源：explain_top1.json，非实时执行」 |
| sql_template 截断无语义 | 注明「SQL模板截断（myhub注释头），以下分析基于 details[].sql_text」 |
| 从库慢日志未采集 | 注明「log_slow_slave_statements=OFF，以下为主库侧推断，非从库回放直接证据」 |
| GTID 模式下 PURGE 安全条件 | 注明「需确认所有从库 Executed_Gtid_Set 已包含目标 binlog 全部事务」 |
| 任何建议的操作 | 注明「⚠️ 执行前请重新确认当前集群状态，本建议基于采集时刻快照」 |

---

## 第三层：必须核查项（生成前前置判断）

### 核查1：路径 C2 分型前置

生成 §3 根因分析前，必须先确认 `Last_SQL_Error` / `Last_IO_Error` 是否已采集且非空。
- 已采集且有明确错误码 → 按错误码分型，进入对应处置方向
- 未采集或为空 → 触发禁4，不给恢复命令

### 核查2：System lock 子类型前置（路径 B2）

生成 §3 根因分析前，必须先读 `system_lock_status.subtype`：
- `subtype=AutoInc` → 持锁者判断切换为「PROCESSLIST State=System lock + SQL类型为 INSERT IGNORE/REPLACE/INSERT SELECT」，**不依赖 lock_time**（System lock 不进慢日志，lock_time=0s 是正常的）
- `subtype=row_lock` → 持锁者判断用 pitfalls.md 坑4标准：`lock_ratio < 5% AND avg_query_time 高`

### 核查3：多分片覆盖检查

§8 数据采集状态表必须包含：
- 覆盖节点列表（vm_name + IP:Port，来自 `get_db_connectors` 的全节点返回）
- 未采集节点（若有）标注 ⚠️
- 采集时间窗口（start ~ end，标注时区）
- 若覆盖率 < 100%，§1 KPI 格显示「⚠️ 采集覆盖率 N/M 节点，可能存在漏采」

### 核查4：时区参数验证

- `get_raw_slow_log` 的 `--start/--end` 必须是 **UTC 时间**（北京时间 -8h）
- `query_xray_metrics` 的 `--start/--end` 必须是 **北京时间**
- 验证方法：检查 `get_raw_slow_log` 返回的 `start_offset_pct`，若 > 95% 说明时间传错

### 核查5：数据页损坏最高优先级（路径 E）

生成任何章节前，先扫描 `error_log` 是否含关键词：`corruption` / `corrupt page` / `checksum mismatch`。
- 若命中：在 §1 Banner 最顶部输出红色大字警告（优先级高于一切其他结论）：
  ```
  🔴 检测到可能的数据页损坏信号，数据完整性存疑。
  请 DBA 立即执行 mysqlcheck 或联系内核团队，暂缓其他操作。
  ```
- 未命中：正常生成报告

---

## 附：GTID 模式 PURGE BINARY LOGS 安全验证步骤（参考）

> 以下为参考命令，**AI 不执行**，仅供 DBA 知晓操作方式。

1. 在所有从库执行 `SHOW SLAVE STATUS\G`，记录 `Executed_Gtid_Set`
2. 在主库执行 `SHOW BINLOG EVENTS IN 'mysql-bin.00XXX' LIMIT 5`，确认该文件内第一个 GTID
3. 确认所有从库的 `Executed_Gtid_Set` 已包含目标文件内全部 GTID 后，才能执行 `PURGE`
4. 推荐方式：设置 `binlog_expire_logs_seconds`，让 MySQL 自动安全清理，无需手动判断从库位点

---

*最后更新：2026-04-10 · 来源：DBA视角/内核专家/风控视角三轮评审综合*
