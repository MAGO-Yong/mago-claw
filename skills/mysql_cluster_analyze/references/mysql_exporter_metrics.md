# MySQL Exporter 可用指标参考

> **⚠️ 集群专属快照**：采集自 **redtao_antispam** 主库 (exporter port 9104)，2026-04-02。
> 不同集群的 exporter 版本和可用指标可能不同，本文件仅作参考，不代表所有集群。
>
> 用途：作为 query_xray_metrics.py 的 PromQL 输入参考，无需 SSH 到机器发现指标

---

# Part 1：关注项 — 运行状态指标（故障诊断核心数据源）

> 以下指标反映 MySQL 实时运行状态，是故障诊断、性能分析的核心输入。
> 使用方式：作为 `query_xray_metrics.py --pql` 的输入，查询完整时序。

## InnoDB Buffer Pool（缓冲池）

> 故障关键：wait_free > 0 表示 buffer pool 不够用，page_cleaner 跟不上脏页淘汰

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_buffer_pool_dirty_pages` | gauge | Innodb buffer pool dirty pages. |
| `mysql_global_status_buffer_pool_page_changes_total` | counter | Innodb buffer pool page state changes. |
| `mysql_global_status_buffer_pool_pages` | gauge | Innodb buffer pool pages by state. |
| `mysql_global_status_innodb_buffer_pool_bytes_data` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_bytes_dirty` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_read_ahead` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_read_ahead_evicted` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_read_ahead_rnd` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_read_requests` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_reads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_wait_free` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_buffer_pool_write_requests` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## InnoDB I/O & Redo Log（磁盘读写与日志）

> data_reads/writes 反映磁盘 I/O 压力，log_waits > 0 表示 redo log 写入等待

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_innodb_data_fsyncs` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_pending_fsyncs` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_pending_reads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_pending_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_read` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_reads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_data_written` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_dblwr_pages_written` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_dblwr_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_log_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_os_log_fsyncs` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_os_log_pending_fsyncs` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_os_log_pending_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_os_log_written` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_pages_created` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_pages_read` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_pages_written` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## InnoDB Row Lock & Deadlock（行锁与死锁）

> row_lock_waits 持续增长表示锁竞争严重，deadlocks > 0 需要关注事务设计

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_innodb_row_lock_current_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_row_lock_time` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_row_lock_time_avg` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_row_lock_time_max` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_row_lock_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Connections & Threads（连接与线程）

> threads_running 高 → CPU 高；threads_connected 接近 max_connections → 连接池耗尽
> aborted_connects 高 → 认证失败或网络问题

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_aborted_clients` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_aborted_connects` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_connections` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_max_used_connections` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_threads_cached` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_threads_connected` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_threads_created` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_threads_extra_connected` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_threads_running` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Commands & QPS（命令计数与查询量）

> rate(commands_total[1m]) 可算各类型 QPS；questions 是总查询数

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_commands_total` | counter | Total number of executed MySQL commands. |
| `mysql_global_status_qcache_queries_in_cache` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_queries` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_questions` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slow_queries` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Replication（主从复制）

> slave_open_temp_tables 关注临时表泄漏；binlog 相关关注 binlog 生成速率

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_binlog_cache_disk_use` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_binlog_cache_use` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_binlog_stmt_cache_disk_use` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_binlog_stmt_cache_use` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_slave_status` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slave_heartbeat_period` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slave_open_temp_tables` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slave_received_heartbeats` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slave_retried_transactions` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slave_running` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Table & File（表与文件句柄）

> open_tables 接近 table_open_cache → 频繁开关表

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_innodb_num_open_files` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_open_files` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_open_tables` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_table_locks_immediate` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_table_locks_waited` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_table_open_cache_hits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_table_open_cache_misses` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_table_open_cache_overflows` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Sort & Temp Table（排序与临时表）

> created_tmp_disk_tables 高 → 排序/GROUP BY 用了磁盘临时表，需优化 SQL

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_created_tmp_disk_tables` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_created_tmp_files` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_created_tmp_tables` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_sort_merge_passes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_sort_range` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_sort_rows` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_sort_scan` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Network（网络流量）

> 监控实例进出流量

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_bytes_received` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_bytes_sent` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## Select（查询类型计数）

> select_full_join 高 → 有全表 JOIN；select_scan 高 → 全表扫描多

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_select_full_join` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_select_full_range_join` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_select_range` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_select_range_check` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_select_scan` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## InnoDB 其他

> 其余 InnoDB 运行指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_innodb_available_undo_logs` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_log_write_requests` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_log_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_page_size` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_innodb_row_ops_total` | counter | Total number of MySQL InnoDB row operations. |
| `mysql_global_status_innodb_truncated_status_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## 其他 status 指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_global_status_compression` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_connection_errors_total` | counter | Total number of MySQL connection errors. |
| `mysql_global_status_delayed_errors` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_delayed_insert_threads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_delayed_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_flush_commands` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_fail_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_follower_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_free_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_ignore_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_insert_dup` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_leader_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_reuse_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_same_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_group_update_total_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_handlers_total` | counter | Total number of executed MySQL handlers. |
| `mysql_global_status_key_blocks_not_flushed` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_blocks_unused` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_blocks_used` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_read_requests` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_reads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_write_requests` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_key_writes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_last_query_cost` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_last_query_partial_plans` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_locked_connects` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_max_execution_time_exceeded` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_max_execution_time_set` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_max_execution_time_set_failed` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_not_flushed_delayed_rows` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ongoing_anonymous_transaction_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_open_streams` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_open_table_definitions` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_opened_files` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_opened_table_definitions` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_opened_tables` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_performance_schema_lost_total` | counter | Total number of MySQL instrumentations that could not be loaded or created due to memory constraints. |
| `mysql_global_status_prepared_stmt_count` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_free_blocks` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_free_memory` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_hits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_inserts` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_lowmem_prunes` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_not_cached` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_qcache_total_blocks` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_redsql_hotspot_queue_times` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_redsql_jemalloc_enable` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_clients` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_net_avg_wait_time` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_net_wait_time` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_net_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_no_times` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_no_tx` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_status` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_timefunc_failures` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_tx_avg_wait_time` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_tx_wait_time` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_tx_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_wait_pos_backtraverse` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_wait_sessions` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_rpl_semi_sync_master_yes_tx` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_slow_launch_threads` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_accept_renegotiates` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_accepts` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_callback_cache_hits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_client_connects` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_connect_renegotiates` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_ctx_verify_depth` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_ctx_verify_mode` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_default_timeout` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_finished_accepts` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_finished_connects` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_session_cache_hits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_session_cache_misses` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_session_cache_overflows` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_session_cache_size` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_session_cache_timeouts` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_sessions_reused` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_used_session_cache_entries` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_verify_depth` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_ssl_verify_mode` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_tc_log_max_pages_used` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_tc_log_page_size` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_tc_log_page_waits` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_uptime` | untyped | Generic metric from SHOW GLOBAL STATUS. |
| `mysql_global_status_uptime_since_flush_status` | untyped | Generic metric from SHOW GLOBAL STATUS. |

## mysql_info_schema（元数据指标）

> 来自 information_schema 的统计信息

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `mysql_info_schema_innodb_cmp_compress_ops_ok_total` | counter | Number of times a B-tree page of the size PAGE_SIZE has been successfully compressed. |
| `mysql_info_schema_innodb_cmp_compress_ops_total` | counter | Number of times a B-tree page of the size PAGE_SIZE has been compressed. |
| `mysql_info_schema_innodb_cmp_compress_time_seconds_total` | counter | Total time in seconds spent in attempts to compress B-tree pages. |
| `mysql_info_schema_innodb_cmp_uncompress_ops_total` | counter | Number of times a B-tree page of the size PAGE_SIZE has been uncompressed. |
| `mysql_info_schema_innodb_cmp_uncompress_time_seconds_total` | counter | Total time in seconds spent in uncompressing B-tree pages. |
| `mysql_info_schema_innodb_cmpmem_pages_free_total` | counter | Number of blocks of the size PAGE_SIZE that are currently available for allocation. |
| `mysql_info_schema_innodb_cmpmem_pages_used_total` | counter | Number of blocks of the size PAGE_SIZE that are currently in use. |
| `mysql_info_schema_innodb_cmpmem_relocation_ops_total` | counter | Number of times a block of the size PAGE_SIZE has been relocated. |
| `mysql_info_schema_innodb_cmpmem_relocation_time_seconds_total` | counter | Total time in seconds spent in relocating blocks. |

---

# Part 2：配置项 — mysql_global_variables（当前参数值）

> 以下为 SHOW GLOBAL VARIABLES 导出的配置参数，反映实例当前配置。
> 通常不用于时序查询，但诊断时可查看当前值判断配置是否合理。
> 例如：innodb_buffer_pool_size 是否与物理内存匹配、max_connections 是否过小等。
>
> **⚠️ 单位说明**：当前值列中的单位后缀（M/G）为 AI 采集时粗略换算，**部分存在误标**。
> 例如 `lock_wait_timeout=30M` 实际为 30 秒，`max_binlog_cache_size=17179869184.0G` 实际为字节。
> 诊断时应以 MySQL `SHOW GLOBAL VARIABLES` 原始值为准，本文件仅供快速索引参考。

### InnoDB 相关配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_innodb_adaptive_flushing` | gauge | 1.0 |
| `mysql_global_variables_innodb_adaptive_flushing_lwm` | gauge | 10.0 |
| `mysql_global_variables_innodb_adaptive_hash_index` | gauge | 0.0 |
| `mysql_global_variables_innodb_adaptive_hash_index_parts` | gauge | 8.0 |
| `mysql_global_variables_innodb_adaptive_max_sleep_delay` | gauge | 150000.0 |
| `mysql_global_variables_innodb_api_bk_commit_interval` | gauge | 5.0 |
| `mysql_global_variables_innodb_api_disable_rowlock` | gauge | 0.0 |
| `mysql_global_variables_innodb_api_enable_binlog` | gauge | 0.0 |
| `mysql_global_variables_innodb_api_enable_mdl` | gauge | 0.0 |
| `mysql_global_variables_innodb_api_trx_level` | gauge | 0.0 |
| `mysql_global_variables_innodb_autoextend_increment` | gauge | 64.0 |
| `mysql_global_variables_innodb_autoinc_lock_mode` | gauge | 1.0 |
| `mysql_global_variables_innodb_buffer_pool_chunk_size` | gauge | 128M |
| `mysql_global_variables_innodb_buffer_pool_dump_at_shutdown` | gauge | 1.0 |
| `mysql_global_variables_innodb_buffer_pool_dump_now` | gauge | 0.0 |
| `mysql_global_variables_innodb_buffer_pool_dump_pct` | gauge | 100.0 |
| `mysql_global_variables_innodb_buffer_pool_instances` | gauge | 8.0 |
| `mysql_global_variables_innodb_buffer_pool_load_abort` | gauge | 0.0 |
| `mysql_global_variables_innodb_buffer_pool_load_at_startup` | gauge | 1.0 |
| `mysql_global_variables_innodb_buffer_pool_load_now` | gauge | 0.0 |
| `mysql_global_variables_innodb_buffer_pool_size` | gauge | 82.0G |
| `mysql_global_variables_innodb_change_buffer_max_size` | gauge | 25.0 |
| `mysql_global_variables_innodb_checksums` | gauge | 1.0 |
| `mysql_global_variables_innodb_cmp_per_index_enabled` | gauge | 0.0 |
| `mysql_global_variables_innodb_commit_concurrency` | gauge | 0.0 |
| `mysql_global_variables_innodb_compression_failure_threshold_pct` | gauge | 5.0 |
| `mysql_global_variables_innodb_compression_level` | gauge | 6.0 |
| `mysql_global_variables_innodb_compression_pad_pct_max` | gauge | 50.0 |
| `mysql_global_variables_innodb_concurrency_tickets` | gauge | 5000.0 |
| `mysql_global_variables_innodb_deadlock_detect` | gauge | 1.0 |
| `mysql_global_variables_innodb_disable_sort_file_cache` | gauge | 1.0 |
| `mysql_global_variables_innodb_doublewrite` | gauge | 1.0 |
| `mysql_global_variables_innodb_fast_shutdown` | gauge | 1.0 |
| `mysql_global_variables_innodb_file_format_check` | gauge | 1.0 |
| `mysql_global_variables_innodb_file_per_table` | gauge | 1.0 |
| `mysql_global_variables_innodb_fill_factor` | gauge | 100.0 |
| `mysql_global_variables_innodb_flush_log_at_timeout` | gauge | 1.0 |
| `mysql_global_variables_innodb_flush_log_at_trx_commit` | gauge | 2.0 |
| `mysql_global_variables_innodb_flush_neighbors` | gauge | 0.0 |
| `mysql_global_variables_innodb_flush_sync` | gauge | 1.0 |
| `mysql_global_variables_innodb_flushing_avg_loops` | gauge | 30.0 |
| `mysql_global_variables_innodb_force_load_corrupted` | gauge | 0.0 |
| `mysql_global_variables_innodb_force_recovery` | gauge | 0.0 |
| `mysql_global_variables_innodb_ft_cache_size` | gauge | 8M |
| `mysql_global_variables_innodb_ft_enable_diag_print` | gauge | 0.0 |
| `mysql_global_variables_innodb_ft_enable_stopword` | gauge | 1.0 |
| `mysql_global_variables_innodb_ft_max_token_size` | gauge | 84.0 |
| `mysql_global_variables_innodb_ft_min_token_size` | gauge | 3.0 |
| `mysql_global_variables_innodb_ft_num_word_optimize` | gauge | 2000.0 |
| `mysql_global_variables_innodb_ft_result_cache_limit` | gauge | 1.9G |
| `mysql_global_variables_innodb_ft_sort_pll_degree` | gauge | 2.0 |
| `mysql_global_variables_innodb_ft_total_cache_size` | gauge | 610M |
| `mysql_global_variables_innodb_io_capacity` | gauge | 5000.0 |
| `mysql_global_variables_innodb_io_capacity_max` | gauge | 10000.0 |
| `mysql_global_variables_innodb_large_prefix` | gauge | 1.0 |
| `mysql_global_variables_innodb_lock_wait_timeout` | gauge | 50.0 |
| `mysql_global_variables_innodb_locks_unsafe_for_binlog` | gauge | 0.0 |
| `mysql_global_variables_innodb_log_buffer_size` | gauge | 10M |
| `mysql_global_variables_innodb_log_checksums` | gauge | 1.0 |
| `mysql_global_variables_innodb_log_compressed_pages` | gauge | 1.0 |
| `mysql_global_variables_innodb_log_file_size` | gauge | 4.0G |
| `mysql_global_variables_innodb_log_files_in_group` | gauge | 10.0 |
| `mysql_global_variables_innodb_log_write_ahead_size` | gauge | 8192.0 |
| `mysql_global_variables_innodb_lru_scan_depth` | gauge | 1024.0 |
| `mysql_global_variables_innodb_max_dirty_pages_pct` | gauge | 75.0 |
| `mysql_global_variables_innodb_max_dirty_pages_pct_lwm` | gauge | 0.0 |
| `mysql_global_variables_innodb_max_purge_lag` | gauge | 0.0 |
| `mysql_global_variables_innodb_max_purge_lag_delay` | gauge | 0.0 |
| `mysql_global_variables_innodb_max_undo_log_size` | gauge | 1.0G |
| `mysql_global_variables_innodb_numa_interleave` | gauge | 0.0 |
| `mysql_global_variables_innodb_old_blocks_pct` | gauge | 37.0 |
| `mysql_global_variables_innodb_old_blocks_time` | gauge | 1000.0 |
| `mysql_global_variables_innodb_online_alter_log_max_size` | gauge | 128M |
| `mysql_global_variables_innodb_open_files` | gauge | 42949.0 |
| `mysql_global_variables_innodb_optimize_fulltext_only` | gauge | 0.0 |
| `mysql_global_variables_innodb_page_cleaners` | gauge | 4.0 |
| `mysql_global_variables_innodb_page_size` | gauge | 16384.0 |
| `mysql_global_variables_innodb_print_all_deadlocks` | gauge | 1.0 |
| `mysql_global_variables_innodb_purge_batch_size` | gauge | 300.0 |
| `mysql_global_variables_innodb_purge_rseg_truncate_frequency` | gauge | 128.0 |
| `mysql_global_variables_innodb_purge_threads` | gauge | 4.0 |
| `mysql_global_variables_innodb_random_read_ahead` | gauge | 0.0 |
| `mysql_global_variables_innodb_read_ahead_threshold` | gauge | 56.0 |
| `mysql_global_variables_innodb_read_io_threads` | gauge | 16.0 |
| `mysql_global_variables_innodb_read_only` | gauge | 0.0 |
| `mysql_global_variables_innodb_redsql_bp_load_fast` | gauge | 1.0 |
| `mysql_global_variables_innodb_redsql_unique_key_optimize` | gauge | 0.0 |
| `mysql_global_variables_innodb_replication_delay` | gauge | 0.0 |
| `mysql_global_variables_innodb_rollback_on_timeout` | gauge | 0.0 |
| `mysql_global_variables_innodb_rollback_segments` | gauge | 128.0 |
| `mysql_global_variables_innodb_sort_buffer_size` | gauge | 524288.0 |
| `mysql_global_variables_innodb_spin_wait_delay` | gauge | 6.0 |
| `mysql_global_variables_innodb_stats_auto_recalc` | gauge | 1.0 |
| `mysql_global_variables_innodb_stats_include_delete_marked` | gauge | 0.0 |
| `mysql_global_variables_innodb_stats_on_metadata` | gauge | 0.0 |
| `mysql_global_variables_innodb_stats_persistent` | gauge | 1.0 |
| `mysql_global_variables_innodb_stats_persistent_sample_pages` | gauge | 20.0 |
| `mysql_global_variables_innodb_stats_sample_pages` | gauge | 8.0 |
| `mysql_global_variables_innodb_stats_transient_sample_pages` | gauge | 8.0 |
| `mysql_global_variables_innodb_status_output` | gauge | 0.0 |
| `mysql_global_variables_innodb_status_output_locks` | gauge | 0.0 |
| `mysql_global_variables_innodb_strict_mode` | gauge | 1.0 |
| `mysql_global_variables_innodb_support_xa` | gauge | 1.0 |
| `mysql_global_variables_innodb_sync_array_size` | gauge | 1.0 |
| `mysql_global_variables_innodb_sync_spin_loops` | gauge | 30.0 |
| `mysql_global_variables_innodb_table_locks` | gauge | 1.0 |
| `mysql_global_variables_innodb_thread_concurrency` | gauge | 0.0 |
| `mysql_global_variables_innodb_thread_sleep_delay` | gauge | 10000.0 |
| `mysql_global_variables_innodb_undo_log_truncate` | gauge | 1.0 |
| `mysql_global_variables_innodb_undo_logs` | gauge | 128.0 |
| `mysql_global_variables_innodb_undo_tablespaces` | gauge | 2.0 |
| `mysql_global_variables_innodb_use_native_aio` | gauge | 1.0 |
| `mysql_global_variables_innodb_write_io_threads` | gauge | 16.0 |

### 复制相关配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_binlog_cache_size` | gauge | 4M |
| `mysql_global_variables_binlog_direct_non_transactional_updates` | gauge | 0.0 |
| `mysql_global_variables_binlog_group_commit_sync_delay` | gauge | 0.0 |
| `mysql_global_variables_binlog_group_commit_sync_no_delay_count` | gauge | 0.0 |
| `mysql_global_variables_binlog_gtid_simple_recovery` | gauge | 1.0 |
| `mysql_global_variables_binlog_max_flush_queue_time` | gauge | 0.0 |
| `mysql_global_variables_binlog_order_commits` | gauge | 1.0 |
| `mysql_global_variables_binlog_rows_query_log_events` | gauge | 1.0 |
| `mysql_global_variables_binlog_stmt_cache_size` | gauge | 32768.0 |
| `mysql_global_variables_binlog_transaction_dependency_history_size` | gauge | 25000.0 |
| `mysql_global_variables_enforce_gtid_consistency` | gauge | 1.0 |
| `mysql_global_variables_gtid_executed_compression_period` | gauge | 1000.0 |
| `mysql_global_variables_gtid_mode` | gauge | 1.0 |
| `mysql_global_variables_log_slave_updates` | gauge | 1.0 |
| `mysql_global_variables_log_slow_slave_statements` | gauge | 0.0 |
| `mysql_global_variables_master_verify_checksum` | gauge | 0.0 |
| `mysql_global_variables_max_binlog_cache_size` | gauge | 17179869184.0G |
| `mysql_global_variables_max_binlog_size` | gauge | 1.0G |
| `mysql_global_variables_max_binlog_stmt_cache_size` | gauge | 17179869184.0G |
| `mysql_global_variables_max_relay_log_size` | gauge | 0.0 |
| `mysql_global_variables_relay_log_purge` | gauge | 1.0 |
| `mysql_global_variables_relay_log_recovery` | gauge | 1.0 |
| `mysql_global_variables_relay_log_space_limit` | gauge | 0.0 |
| `mysql_global_variables_rpl_semi_sync_master_enabled` | gauge | 0.0 |
| `mysql_global_variables_rpl_semi_sync_master_timeout` | gauge | 10000.0 |
| `mysql_global_variables_rpl_semi_sync_master_trace_level` | gauge | 32.0 |
| `mysql_global_variables_rpl_semi_sync_master_wait_for_slave_count` | gauge | 1.0 |
| `mysql_global_variables_rpl_semi_sync_master_wait_no_slave` | gauge | 1.0 |
| `mysql_global_variables_rpl_semi_sync_slave_enabled` | gauge | 0.0 |
| `mysql_global_variables_rpl_semi_sync_slave_trace_level` | gauge | 32.0 |
| `mysql_global_variables_rpl_stop_slave_timeout` | gauge | 30M |
| `mysql_global_variables_slave_allow_batching` | gauge | 0.0 |
| `mysql_global_variables_slave_checkpoint_group` | gauge | 512.0 |
| `mysql_global_variables_slave_checkpoint_period` | gauge | 300.0 |
| `mysql_global_variables_slave_compressed_protocol` | gauge | 0.0 |
| `mysql_global_variables_slave_max_allowed_packet` | gauge | 1.0G |
| `mysql_global_variables_slave_net_timeout` | gauge | 10.0 |
| `mysql_global_variables_slave_parallel_workers` | gauge | 16.0 |
| `mysql_global_variables_slave_pending_jobs_size_max` | gauge | 1.0G |
| `mysql_global_variables_slave_preserve_commit_order` | gauge | 0.0 |
| `mysql_global_variables_slave_skip_errors` | gauge | 0.0 |
| `mysql_global_variables_slave_sql_verify_checksum` | gauge | 1.0 |
| `mysql_global_variables_slave_transaction_retries` | gauge | 10.0 |
| `mysql_global_variables_sql_slave_skip_counter` | gauge | 0.0 |
| `mysql_global_variables_sync_binlog` | gauge | 1000.0 |
| `mysql_global_variables_sync_master_info` | gauge | 10000.0 |
| `mysql_global_variables_sync_relay_log` | gauge | 10000.0 |
| `mysql_global_variables_sync_relay_log_info` | gauge | 10000.0 |

### 连接与线程配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_ccl_wait_timeout` | gauge | 86400.0 |
| `mysql_global_variables_connect_timeout` | gauge | 10.0 |
| `mysql_global_variables_extra_max_connections` | gauge | 1000.0 |
| `mysql_global_variables_interactive_timeout` | gauge | 28800.0 |
| `mysql_global_variables_lock_wait_timeout` | gauge | 30M |
| `mysql_global_variables_max_connections` | gauge | 15000.0 |
| `mysql_global_variables_net_buffer_length` | gauge | 16384.0 |
| `mysql_global_variables_net_read_timeout` | gauge | 30.0 |
| `mysql_global_variables_net_retry_count` | gauge | 10.0 |
| `mysql_global_variables_net_write_timeout` | gauge | 60.0 |
| `mysql_global_variables_performance_schema_max_thread_classes` | gauge | 50.0 |
| `mysql_global_variables_performance_schema_max_thread_instances` | gauge | -1.0 |
| `mysql_global_variables_thread_cache_size` | gauge | 1024.0 |
| `mysql_global_variables_thread_stack` | gauge | 262144.0 |
| `mysql_global_variables_wait_timeout` | gauge | 600.0 |

### 日志相关配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_expire_logs_days` | gauge | 7.0 |
| `mysql_global_variables_general_log` | gauge | 0.0 |
| `mysql_global_variables_log_bin` | gauge | 1.0 |
| `mysql_global_variables_log_bin_trust_function_creators` | gauge | 0.0 |
| `mysql_global_variables_log_bin_use_v1_row_events` | gauge | 0.0 |
| `mysql_global_variables_log_builtin_as_identified_by_password` | gauge | 0.0 |
| `mysql_global_variables_log_error_verbosity` | gauge | 3.0 |
| `mysql_global_variables_log_queries_not_using_indexes` | gauge | 0.0 |
| `mysql_global_variables_log_slow_admin_statements` | gauge | 0.0 |
| `mysql_global_variables_log_statements_unsafe_for_binlog` | gauge | 1.0 |
| `mysql_global_variables_log_syslog` | gauge | 0.0 |
| `mysql_global_variables_log_syslog_include_pid` | gauge | 1.0 |
| `mysql_global_variables_log_throttle_queries_not_using_indexes` | gauge | 0.0 |
| `mysql_global_variables_log_warnings` | gauge | 2.0 |
| `mysql_global_variables_long_query_time` | gauge | 0.1 |
| `mysql_global_variables_slow_query_log` | gauge | 1.0 |
| `mysql_global_variables_sql_log_bin` | gauge | 1.0 |
| `mysql_global_variables_sql_log_off` | gauge | 0.0 |

### 性能与缓存配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_have_query_cache` | gauge | 1.0 |
| `mysql_global_variables_join_buffer_size` | gauge | 524288.0 |
| `mysql_global_variables_max_heap_table_size` | gauge | 16M |
| `mysql_global_variables_max_tmp_tables` | gauge | 32.0 |
| `mysql_global_variables_myisam_sort_buffer_size` | gauge | 8M |
| `mysql_global_variables_open_files_limit` | gauge | 95918.0 |
| `mysql_global_variables_query_cache_limit` | gauge | 1M |
| `mysql_global_variables_query_cache_min_res_unit` | gauge | 4096.0 |
| `mysql_global_variables_query_cache_size` | gauge | 1M |
| `mysql_global_variables_query_cache_type` | gauge | 0.0 |
| `mysql_global_variables_query_cache_wlock_invalidate` | gauge | 0.0 |
| `mysql_global_variables_read_buffer_size` | gauge | 524288.0 |
| `mysql_global_variables_read_rnd_buffer_size` | gauge | 524288.0 |
| `mysql_global_variables_sort_buffer_size` | gauge | 524288.0 |
| `mysql_global_variables_table_definition_cache` | gauge | 42949.0 |
| `mysql_global_variables_table_open_cache` | gauge | 42949.0 |
| `mysql_global_variables_table_open_cache_instances` | gauge | 16.0 |
| `mysql_global_variables_tmp_table_size` | gauge | 16M |

### 其他配置

| 指标名 | 类型 | 当前值 |
|--------|------|--------|
| `mysql_global_variables_auto_generate_certs` | gauge | 1.0 |
| `mysql_global_variables_auto_increment_increment` | gauge | 1.0 |
| `mysql_global_variables_auto_increment_offset` | gauge | 1.0 |
| `mysql_global_variables_autocommit` | gauge | 1.0 |
| `mysql_global_variables_automatic_sp_privileges` | gauge | 1.0 |
| `mysql_global_variables_avoid_temporal_upgrade` | gauge | 0.0 |
| `mysql_global_variables_back_log` | gauge | 1024.0 |
| `mysql_global_variables_big_tables` | gauge | 0.0 |
| `mysql_global_variables_bulk_insert_buffer_size` | gauge | 8M |
| `mysql_global_variables_ccl_enable` | gauge | 0.0 |
| `mysql_global_variables_ccl_forbidden_enable` | gauge | 0.0 |
| `mysql_global_variables_ccl_max_waiting_count` | gauge | 0.0 |
| `mysql_global_variables_check_proxy_users` | gauge | 0.0 |
| `mysql_global_variables_core_file` | gauge | 1.0 |
| `mysql_global_variables_default_password_lifetime` | gauge | 0.0 |
| `mysql_global_variables_default_week_format` | gauge | 0.0 |
| `mysql_global_variables_delay_key_write` | gauge | 1.0 |
| `mysql_global_variables_delayed_insert_limit` | gauge | 100.0 |
| `mysql_global_variables_delayed_insert_timeout` | gauge | 300.0 |
| `mysql_global_variables_delayed_queue_size` | gauge | 1000.0 |
| `mysql_global_variables_disconnect_on_expired_password` | gauge | 1.0 |
| `mysql_global_variables_div_precision_increment` | gauge | 4.0 |
| `mysql_global_variables_end_markers_in_json` | gauge | 0.0 |
| `mysql_global_variables_eq_range_index_dive_limit` | gauge | 200.0 |
| `mysql_global_variables_event_scheduler` | gauge | 0.0 |
| `mysql_global_variables_explicit_defaults_for_timestamp` | gauge | 1.0 |
| `mysql_global_variables_extra_port` | gauge | 3301.0 |
| `mysql_global_variables_flush` | gauge | 0.0 |
| `mysql_global_variables_flush_time` | gauge | 0.0 |
| `mysql_global_variables_foreign_key_checks` | gauge | 1.0 |
| `mysql_global_variables_ft_max_word_len` | gauge | 84.0 |
| `mysql_global_variables_ft_min_word_len` | gauge | 4.0 |
| `mysql_global_variables_ft_query_expansion_limit` | gauge | 20.0 |
| `mysql_global_variables_group_concat_max_len` | gauge | 102400.0 |
| `mysql_global_variables_have_compress` | gauge | 1.0 |
| `mysql_global_variables_have_crypt` | gauge | 1.0 |
| `mysql_global_variables_have_dynamic_loading` | gauge | 1.0 |
| `mysql_global_variables_have_geometry` | gauge | 1.0 |
| `mysql_global_variables_have_openssl` | gauge | 0.0 |
| `mysql_global_variables_have_profiling` | gauge | 1.0 |
| `mysql_global_variables_have_rtree_keys` | gauge | 1.0 |
| `mysql_global_variables_have_ssl` | gauge | 0.0 |
| `mysql_global_variables_have_statement_timeout` | gauge | 1.0 |
| `mysql_global_variables_have_symlink` | gauge | 1.0 |
| `mysql_global_variables_host_cache_size` | gauge | 1103.0 |
| `mysql_global_variables_hotspot_group_update_enable` | gauge | 1.0 |
| `mysql_global_variables_hotspot_hint_enable` | gauge | 1.0 |
| `mysql_global_variables_hotspot_lock_type` | gauge | 1.0 |
| `mysql_global_variables_hotspot_max_thd_num` | gauge | 2.0 |
| `mysql_global_variables_hotspot_update_max_wait_time` | gauge | 100.0 |
| `mysql_global_variables_ignore_builtin_innodb` | gauge | 0.0 |
| `mysql_global_variables_keep_files_on_create` | gauge | 0.0 |
| `mysql_global_variables_key_buffer_size` | gauge | 32M |
| `mysql_global_variables_key_cache_age_threshold` | gauge | 300.0 |
| `mysql_global_variables_key_cache_block_size` | gauge | 1024.0 |
| `mysql_global_variables_key_cache_division_limit` | gauge | 100.0 |
| `mysql_global_variables_keyring_operations` | gauge | 1.0 |
| `mysql_global_variables_large_files_support` | gauge | 1.0 |
| `mysql_global_variables_large_page_size` | gauge | 0.0 |
| `mysql_global_variables_large_pages` | gauge | 0.0 |
| `mysql_global_variables_local_infile` | gauge | 0.0 |
| `mysql_global_variables_locked_in_memory` | gauge | 0.0 |
| `mysql_global_variables_low_priority_updates` | gauge | 0.0 |
| `mysql_global_variables_lower_case_file_system` | gauge | 0.0 |
| `mysql_global_variables_lower_case_table_names` | gauge | 0.0 |
| `mysql_global_variables_max_allowed_packet` | gauge | 1.0G |
| `mysql_global_variables_max_connect_errors` | gauge | 100.0 |
| `mysql_global_variables_max_delayed_threads` | gauge | 20.0 |
| `mysql_global_variables_max_digest_length` | gauge | 1024.0 |
| `mysql_global_variables_max_error_count` | gauge | 64.0 |
| `mysql_global_variables_max_execution_time` | gauge | 0.0 |
| `mysql_global_variables_max_insert_delayed_threads` | gauge | 20.0 |
| `mysql_global_variables_max_join_size` | gauge | 17179869184.0G |
| `mysql_global_variables_max_length_for_sort_data` | gauge | 1024.0 |
| `mysql_global_variables_max_points_in_geometry` | gauge | 65536.0 |
| `mysql_global_variables_max_prepared_stmt_count` | gauge | 16382.0 |
| `mysql_global_variables_max_seeks_for_key` | gauge | 17179869184.0G |
| `mysql_global_variables_max_sort_length` | gauge | 1024.0 |
| `mysql_global_variables_max_sp_recursion_depth` | gauge | 0.0 |
| `mysql_global_variables_max_user_connections` | gauge | 8000.0 |
| `mysql_global_variables_max_write_lock_count` | gauge | 17179869184.0G |
| `mysql_global_variables_metadata_locks_cache_size` | gauge | 1024.0 |
| `mysql_global_variables_metadata_locks_hash_instances` | gauge | 8.0 |
| `mysql_global_variables_min_examined_row_limit` | gauge | 0.0 |
| `mysql_global_variables_multi_range_count` | gauge | 256.0 |
| `mysql_global_variables_myisam_data_pointer_size` | gauge | 6.0 |
| `mysql_global_variables_myisam_max_sort_file_size` | gauge | 8589934592.0G |
| `mysql_global_variables_myisam_mmap_size` | gauge | 17179869184.0G |
| `mysql_global_variables_myisam_recover_options` | gauge | 0.0 |
| `mysql_global_variables_myisam_repair_threads` | gauge | 1.0 |
| `mysql_global_variables_myisam_use_mmap` | gauge | 0.0 |
| `mysql_global_variables_mysql_native_password_proxy_users` | gauge | 0.0 |
| `mysql_global_variables_new` | gauge | 0.0 |
| `mysql_global_variables_ngram_token_size` | gauge | 2.0 |
| `mysql_global_variables_offline_mode` | gauge | 0.0 |
| `mysql_global_variables_old` | gauge | 0.0 |
| `mysql_global_variables_old_alter_table` | gauge | 0.0 |
| `mysql_global_variables_old_passwords` | gauge | 0.0 |
| `mysql_global_variables_optimizer_prune_level` | gauge | 1.0 |
| `mysql_global_variables_optimizer_search_depth` | gauge | 62.0 |
| `mysql_global_variables_optimizer_trace_limit` | gauge | 1.0 |
| `mysql_global_variables_optimizer_trace_max_mem_size` | gauge | 16384.0 |
| `mysql_global_variables_optimizer_trace_offset` | gauge | -1.0 |
| `mysql_global_variables_parser_max_mem_size` | gauge | 17179869184.0G |
| `mysql_global_variables_performance_schema` | gauge | 1.0 |
| `mysql_global_variables_performance_schema_accounts_size` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_digests_size` | gauge | 10000.0 |
| `mysql_global_variables_performance_schema_events_stages_history_long_size` | gauge | 10000.0 |
| `mysql_global_variables_performance_schema_events_stages_history_size` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_events_statements_history_long_size` | gauge | 10000.0 |
| `mysql_global_variables_performance_schema_events_statements_history_size` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_events_transactions_history_long_size` | gauge | 10000.0 |
| `mysql_global_variables_performance_schema_events_transactions_history_size` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_events_waits_history_long_size` | gauge | 10000.0 |
| `mysql_global_variables_performance_schema_events_waits_history_size` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_hosts_size` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_cond_classes` | gauge | 80.0 |
| `mysql_global_variables_performance_schema_max_cond_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_digest_length` | gauge | 1024.0 |
| `mysql_global_variables_performance_schema_max_file_classes` | gauge | 80.0 |
| `mysql_global_variables_performance_schema_max_file_handles` | gauge | 32768.0 |
| `mysql_global_variables_performance_schema_max_file_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_index_stat` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_memory_classes` | gauge | 320.0 |
| `mysql_global_variables_performance_schema_max_metadata_locks` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_mutex_classes` | gauge | 210.0 |
| `mysql_global_variables_performance_schema_max_mutex_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_prepared_statements_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_program_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_rwlock_classes` | gauge | 50.0 |
| `mysql_global_variables_performance_schema_max_rwlock_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_socket_classes` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_max_socket_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_sql_text_length` | gauge | 1024.0 |
| `mysql_global_variables_performance_schema_max_stage_classes` | gauge | 150.0 |
| `mysql_global_variables_performance_schema_max_statement_classes` | gauge | 195.0 |
| `mysql_global_variables_performance_schema_max_statement_stack` | gauge | 10.0 |
| `mysql_global_variables_performance_schema_max_table_handles` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_table_instances` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_max_table_lock_stat` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_session_connect_attrs_size` | gauge | 512.0 |
| `mysql_global_variables_performance_schema_setup_actors_size` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_setup_objects_size` | gauge | -1.0 |
| `mysql_global_variables_performance_schema_users_size` | gauge | -1.0 |
| `mysql_global_variables_port` | gauge | 33071.0 |
| `mysql_global_variables_preload_buffer_size` | gauge | 32768.0 |
| `mysql_global_variables_profiling` | gauge | 0.0 |
| `mysql_global_variables_profiling_history_size` | gauge | 15.0 |
| `mysql_global_variables_protocol_version` | gauge | 10.0 |
| `mysql_global_variables_query_alloc_block_size` | gauge | 8192.0 |
| `mysql_global_variables_query_prealloc_size` | gauge | 8192.0 |
| `mysql_global_variables_range_alloc_block_size` | gauge | 4096.0 |
| `mysql_global_variables_range_optimizer_max_mem_size` | gauge | 8M |
| `mysql_global_variables_read_only` | gauge | 0.0 |
| `mysql_global_variables_redsql_max_read_row_count` | gauge | 0.0 |
| `mysql_global_variables_redsql_max_result_row_count` | gauge | 0.0 |
| `mysql_global_variables_redsql_max_transaction_size` | gauge | 0.0 |
| `mysql_global_variables_report_port` | gauge | 33071.0 |
| `mysql_global_variables_require_secure_transport` | gauge | 0.0 |
| `mysql_global_variables_secure_auth` | gauge | 1.0 |
| `mysql_global_variables_server_id` | gauge | 164M |
| `mysql_global_variables_server_id_bits` | gauge | 32.0 |
| `mysql_global_variables_session_track_gtids` | gauge | 0.0 |
| `mysql_global_variables_session_track_schema` | gauge | 1.0 |
| `mysql_global_variables_session_track_state_change` | gauge | 0.0 |
| `mysql_global_variables_session_track_transaction_info` | gauge | 0.0 |
| `mysql_global_variables_sha256_password_auto_generate_rsa_keys` | gauge | 1.0 |
| `mysql_global_variables_sha256_password_proxy_users` | gauge | 0.0 |
| `mysql_global_variables_show_compatibility_56` | gauge | 1.0 |
| `mysql_global_variables_show_create_table_verbosity` | gauge | 0.0 |
| `mysql_global_variables_show_old_temporals` | gauge | 0.0 |
| `mysql_global_variables_skip_external_locking` | gauge | 1.0 |
| `mysql_global_variables_skip_name_resolve` | gauge | 1.0 |
| `mysql_global_variables_skip_networking` | gauge | 0.0 |
| `mysql_global_variables_skip_show_database` | gauge | 0.0 |
| `mysql_global_variables_slow_launch_time` | gauge | 2.0 |
| `mysql_global_variables_sql_auto_is_null` | gauge | 0.0 |
| `mysql_global_variables_sql_big_selects` | gauge | 1.0 |
| `mysql_global_variables_sql_buffer_result` | gauge | 0.0 |
| `mysql_global_variables_sql_notes` | gauge | 1.0 |
| `mysql_global_variables_sql_quote_show_create` | gauge | 1.0 |
| `mysql_global_variables_sql_safe_updates` | gauge | 0.0 |
| `mysql_global_variables_sql_select_limit` | gauge | 17179869184.0G |
| `mysql_global_variables_sql_warnings` | gauge | 0.0 |
| `mysql_global_variables_stored_program_cache` | gauge | 256.0 |
| `mysql_global_variables_super_read_only` | gauge | 0.0 |
| `mysql_global_variables_sync_frm` | gauge | 1.0 |
| `mysql_global_variables_transaction_alloc_block_size` | gauge | 8192.0 |
| `mysql_global_variables_transaction_prealloc_size` | gauge | 4096.0 |
| `mysql_global_variables_transaction_read_only` | gauge | 0.0 |
| `mysql_global_variables_tx_read_only` | gauge | 0.0 |
| `mysql_global_variables_unique_checks` | gauge | 1.0 |
| `mysql_global_variables_updatable_views_with_limit` | gauge | 1.0 |
