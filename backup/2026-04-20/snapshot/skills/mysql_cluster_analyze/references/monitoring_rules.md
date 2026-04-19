# MySQL 集群监控预警规则

> 本文档记录推荐的 PromQL 告警规则，覆盖当前 P0 告警中"滞后感知"场景。
> 所有规则均为**预警型**（在现有告警触发前 1~3 分钟感知），与 GOC 现有告警互补。
>
> 来源：基于 2026-02-26 ~ 2026-03-26 P0 告警分析（153条），以及 2026-04-01 实战复盘。

---

## 一、System lock 专项预警（新增，优先级最高）

### 背景

System lock 堆积（INSERT IGNORE / REPLACE 并发写入触发 AUTO-INC 锁）是当前活跃连接数
告警的主要根因之一，但现有监控只在"连接数超阈值"时才感知，属于**滞后告警**。

System lock 堆积 → 连接无法释放 → 连接数超阈值 → 告警触发
这个传导链通常需要 1~3 分钟，加 System lock 预警可提前发现。

### 规则

```yaml
# 规则1：System lock 预警（P1）
# 比活跃连接数超阈值早 1~2 分钟
- alert: MySQLSystemLockBuildup
  expr: |
    mysql_info_schema_processlist_state_count{state="System lock"} > 3
  for: 30s
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} System lock 堆积（{{ $value }}条）"
    description: |
      集群 {{ $labels.cluster }} 实例 {{ $labels.instance }} 检测到 System lock 堆积。
      可能原因：INSERT IGNORE / REPLACE INTO 高并发写入，innodb_autoinc_lock_mode ≠ 2。
      处置：检查 innodb_autoinc_lock_mode，考虑升级为 2（交错模式）。

# 规则2：System lock 严重（P0）
- alert: MySQLSystemLockCritical
  expr: |
    mysql_info_schema_processlist_state_count{state="System lock"} > 10
  for: 10s
  labels:
    severity: P0
  annotations:
    summary: "{{ $labels.cluster }} System lock 严重堆积（{{ $value }}条），连接数即将超阈值"
    description: |
      立即执行：
      1. SHOW PROCESSLIST 确认 System lock SQL
      2. 检查 innodb_autoinc_lock_mode（目标值：2）
      3. 必要时 KILL 持锁连接
```

### innodb_autoinc_lock_mode 配置检查

```yaml
# 规则3：AUTO-INC 锁模式风险检查（P2，定期巡检）
- alert: MySQLAutoIncLockModeRisk
  expr: |
    mysql_global_variables_innodb_autoinc_lock_mode{} < 2
  for: 5m
  labels:
    severity: P2
  annotations:
    summary: "{{ $labels.cluster }} innodb_autoinc_lock_mode={{ $value }}，INSERT IGNORE 高并发有 System lock 风险"
    description: |
      当前值 {{ $value }}（0=传统，1=连续，2=交错）。
      建议升级到 2（交错模式），消除 INSERT IGNORE / REPLACE 的表级 AUTO-INC 锁。
      注意：mode=2 下 AUTO_INCREMENT 不保证连续，需确认业务无依赖。
```

---

## 二、连接堆积细分预警

### 背景

现有"活跃连接数超阈值"告警无法区分根因（System lock / 行锁 / Sleep 泄漏），
导致每次告警都需要人工逐步排查。细分规则可在触发时直接指向根因。

```yaml
# 规则4：Sleep 连接泄漏（P1）
# 修复说明：Prometheus 标签匹配不支持范围比较（time > 3600 是非法 PromQL）。
# 正确做法：将连接持续时间作为 gauge 指标值查询，再用 > 阈值过滤后 count 聚合。
# 前提：exporter 需暴露 mysql_info_schema_processlist_seconds{command="Sleep"} 指标
#       （如 mysqld_exporter >= 0.14，或自定义 recording rule 预聚合）。
- alert: MySQLSleepConnectionLeak
  expr: |
    count by (cluster, instance) (
      mysql_info_schema_processlist_seconds{command="Sleep"} > 3600
    ) > 5
  for: 5m
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} Sleep 连接泄漏（{{ $value }}条 time > 3600s）"
    description: |
      应用侧连接池未正确归还连接。
      处置：SET GLOBAL wait_timeout=300；KILL 存量 Sleep 连接；排查应用连接池配置。

# 规则5：行锁/MDL 等待（P1）
- alert: MySQLRowLockWaiting
  expr: |
    mysql_info_schema_innodb_metrics_lock_row_lock_current_waits > 10
  for: 30s
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} 行锁等待（{{ $value }}条）"
    description: |
      可能有长事务持锁。查 SHOW ENGINE INNODB STATUS 找持锁 trx，考虑 KILL。
```

---

## 三、主从延迟分级预警

### 背景

主从延迟告警（占 P0 告警 39.9%，最高比例），当前只有一个告警阈值，
无法区分"正在恶化"和"已经严重"，处置优先级不明。

```yaml
# 规则6：主从延迟预警（P1，提前感知）
- alert: MySQLSlaveDelayWarning
  expr: mysql_slave_status_seconds_behind_master > 30
  for: 1m
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} 主从延迟 {{ $value }}s"

# 规则7：主从延迟严重（P0）
- alert: MySQLSlaveDelayCritical
  expr: mysql_slave_status_seconds_behind_master > 300
  for: 30s
  labels:
    severity: P0
  annotations:
    summary: "{{ $labels.cluster }} 主从延迟严重（{{ $value }}s），读流量可能受损"

# 规则8：复制中断（P0，立即）
- alert: MySQLReplicationInterrupted
  expr: |
    mysql_slave_status_slave_sql_running == 0
    OR mysql_slave_status_slave_io_running == 0
  for: 10s
  labels:
    severity: P0
  annotations:
    summary: "{{ $labels.cluster }} 复制中断（SQL_Running 或 IO_Running = 0）"
    description: |
      立即执行：SHOW SLAVE STATUS\G 查 Last_Error。
      常见原因：主键冲突、表不存在、GTID Gap、网络中断。
```

---

## 四、磁盘容量分级预警

### 背景

磁盘告警（占 P0 告警 19%，>90% 和 >95% 两个级别），但当前无增长趋势预警，
往往到 90% 才发现，无法提前干预。

```yaml
# 规则9：磁盘预警（P2，提前干预）
- alert: MySQLDiskWarning
  expr: mysql_node_disk_usage_percent > 75
  for: 10m
  labels:
    severity: P2
  annotations:
    summary: "{{ $labels.cluster }} {{ $labels.vm_name }} 磁盘使用 {{ $value }}%，接近 80% 告警线"

# 规则10：磁盘告警（P1）
- alert: MySQLDiskHigh
  expr: mysql_node_disk_usage_percent > 85
  for: 5m
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} {{ $labels.vm_name }} 磁盘使用 {{ $value }}%"

# 规则11：磁盘增长速率过快（P1，趋势预警）
- alert: MySQLDiskGrowthFast
  expr: |
    rate(mysql_node_disk_usage_bytes[1h]) * 3600 > 10 * 1024 * 1024 * 1024
  for: 30m
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} {{ $labels.vm_name }} 磁盘增长过快（>10GB/h），请人工评估距 90% 剩余时间"
```

---

## 五、告警噪声抑制建议

### 背景

DTS Checksum 操作会触发带宽告警（fls_fulfillment 13条、fls_inventory 12条），属于预期运维行为，
每次都触发 P0 是噪声。

```yaml
# 规则12：带宽告警（DTS 期间静默）
- alert: MySQLNetworkBandwidthHigh
  expr: mysql_node_network_in_mbps > 500 OR mysql_node_network_out_mbps > 500
  for: 2m
  labels:
    severity: P1
  annotations:
    summary: "{{ $labels.cluster }} 网络带宽异常（{{ $value }} Mbps）"
  # 建议：DTS Checksum 窗口期（通常凌晨）配置 silence，避免误报
  # silence_label: dts_operation="checksum"
```

### DTS 运维窗口静默配置（Alertmanager）

```yaml
# Alertmanager inhibit_rules 示例
inhibit_rules:
  - source_match:
      alertname: DTSChecksumRunning   # DTS 操作中告警
    target_match:
      alertname: MySQLNetworkBandwidthHigh
    equal: ['cluster']
```

---

## 六、规则优先级总览

| # | 规则 | severity | 对应 P0 告警类型 | 预警提前量 |
|---|------|---------|----------------|----------|
| 1 | System lock 预警（>3条） | P1 | 活跃连接数异常 | 1~2 min |
| 2 | System lock 严重（>10条） | P0 | 活跃连接数异常 | 30s |
| 3 | AUTO-INC 锁模式风险 | P2 | 活跃连接数异常 | 配置级 |
| 4 | Sleep 连接泄漏（>5条 >1h） | P1 | 活跃连接数异常 | 5 min |
| 5 | 行锁等待（>10条） | P1 | 活跃连接数异常 | 30s |
| 6 | 主从延迟预警（>30s） | P1 | 复制延迟 | 1 min |
| 7 | 主从延迟严重（>300s） | P0 | 复制延迟 | 30s |
| 8 | 复制中断 | P0 | 复制异常 | 10s |
| 9 | 磁盘预警（>75%） | P2 | 磁盘>90% | 数小时 |
| 10 | 磁盘告警（>85%） | P1 | 磁盘>90% | 数小时 |
| 11 | 磁盘增长速率过快 | P1 | 磁盘>90% | 趋势预警 |
| 12 | 带宽异常（+DTS静默） | P1 | 机器带宽 | 2 min |

---

*最后更新：2026-04-01 · 来源：P0 告警复盘 + sns_user_extra System lock 实战案例*
