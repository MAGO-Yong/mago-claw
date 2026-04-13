---
name: mysql-monitor
description: >
  MySQL/MyHub 集群 AI 诊断能力，分为两层。
  【强制】触发任何诊断请求时，必须严格按照本 SKILL.md 规定的步骤和顺序执行，不得跳过、简化或自行替换任何步骤；
  每个 Step 必须通过验收条件后才能进入下一步；最终必须输出符合 8 章节规范的 HTML 报告并推送 webhook 通知。
  Layer 1（原子能力）：监控指标查询、explain-sql、get-table-stats、get-index-stats、get-raw-slow-log 等单接口调用，无副作用，可独立使用。
  Layer 2（多类型故障诊断）：强制先执行 Phase 0 分诊（AI 主动探测推理问题类型）→ 再按类型进入对应路径（慢SQL/CPU高/主从延迟/磁盘满/Crash）。
  触发词：查集群监控/性能/指标 → Layer 1；诊断/分析/出报告/性能问题/故障排查 → Layer 2（必须先走 Phase 0 分诊）。
---

# mysql-monitor

MySQL/MyHub 集群 AI 诊断能力，分为两层：

- **Layer 1（原子能力）**：单接口调用，返回原始数据，无副作用，可独立使用
- **Layer 2（诊断场景）**：编排多个原子能力，输出完整 HTML 报告并推送 webhook 通知

---

## 前置要求

API 调用采用**双 Token 体系**：

| Token | 环境变量 | Header 名 | 用途 |
|-------|----------|-----------|------|
| `DMS_AI_TOKEN` | `DMS_AI_TOKEN` | `DMS-AI-Token` | **优先**，走 `/dms-api/ai-api/v1`（新接口） |
| `DMS_CLAW_TOKEN` | `DMS_CLAW_TOKEN` | `dms-claw-token` | **兜底**，走 `/dms-api/open-claw`（旧接口） |

两者**至少配置一个**。优先配置 `DMS_AI_TOKEN`；若 v1 接口出现网络/HTTP 异常，脚本自动降级到 open-claw。

> **Token 等价说明**：`DMS_AI_TOKEN` 和 `DMS_CLAW_TOKEN` 的**值完全相同**，均来自同一套授权流程，区别仅在于：
> - 调用 v1 接口时放在 `DMS-AI-Token` header
> - 调用 open-claw 接口时放在 `dms-claw-token` header
>
> 当前暂时维护两个环境变量，保持向后兼容。后续 `DMS_CLAW_TOKEN` 会逐步下掉，统一使用 `DMS_AI_TOKEN`。

**AI 启动时检查**：若 `.env` 中两个 Token 都没有，必须先完成下方授权流程再继续。

---

### 获取 DMS_AI_TOKEN（推荐，一次性，AI 主动引导用户完成）

**AI 执行步骤如下（不要让用户手动操作）：**

#### Step A · 生成授权链接（AI 执行）

```bash
curl -s -X POST \
  "https://dms.devops.xiaohongshu.com/dms-api/ai-api/v1/auth/generate-session" \
  | python3 -m json.tool
# 返回：{ "data": { "session_id": "xxx", "authorize_url": "https://...", "expires_in": 300 } }
```

拿到 `session_id` 和 `authorize_url` 后，把链接发给用户：
> 📎 请点击以下链接完成 DMS 授权（需已登录 DMS，链接 5 分钟内有效）：
> `authorize_url`

#### Step B · 用户点击链接授权（用户操作）

用户在浏览器中打开链接，完成 SSO 登录授权，页面会提示"授权成功"。

#### Step C · 获取 Token（AI 执行，用户授权后立即轮询）

```bash
curl -s "https://dms.devops.xiaohongshu.com/dms-api/ai-api/v1/auth/get-token?session_id=<session_id>"
# 返回：{ "data": { "dms_ai_token": "...", "header_name": "DMS-AI-Token" } }
```

若返回 `status: pending`，等待用户确认后再重试。

#### Step D · 保存 Token（AI 执行）

```bash
echo 'DMS_AI_TOKEN=<token>' >> ~/.openclaw/workspace/.env
```

保存后告知用户：「✅ Token 已保存，可以开始使用 mysql-monitor 了。」

---

### 获取 DMS_CLAW_TOKEN（备用 / 兜底）

若 `DMS_AI_TOKEN` 暂时无法获取，可先获取 `DMS_CLAW_TOKEN` 作为兜底：

```bash
# Step 1：生成会话
curl -s -X POST \
  "https://dms.devops.xiaohongshu.com/dms-api/ai-api/v1/auth/generate-session" \
  | python3 -m json.tool
# Step 2：用户在浏览器中访问 authorize_url 完成授权
# Step 3：获取 token（返回字段为 dms_ai_token，同一流程）
curl -s "https://dms.devops.xiaohongshu.com/dms-api/ai-api/v1/auth/get-token?session_id=<session_id>"
```

> Token 两种认证方式共用同一授权流程，区别仅在保存的环境变量名。

---

### 验证 Token 是否有效

```bash
# 验证 DMS_AI_TOKEN
python3 scripts/common/precheck.py
# 输出：✅ DMS_AI_TOKEN 已配置（长度=xxx） + ✅ DMS 服务可达

# 或手动验证（直接调 v1 health check）
curl -s -H "DMS-AI-Token: $DMS_AI_TOKEN" \
     -H "X-AI-Agent-Id: test" -H "X-AI-Session-Id: test" \
     -H "X-AI-Intent: test" -H "X-AI-Version: 1.0" \
  "https://dms.devops.xiaohongshu.com/dms-api/ai-api/v1/base/health_check" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Token 有效' if 'data' in d else f'❌ {d}')"
```

---

## 触发规则

| 用户说 | 走哪层 | 执行什么 |
|--------|--------|---------|
| "查 XX 集群连接数/QPS/慢查询数" | Layer 1 | `scripts/mysql_monitor.py` |
| "帮我 explain 这个 SQL" | Layer 1 | `scripts/atomic/explain_sql.py` |
| "查一下 XX 表的索引情况" | Layer 1 | `scripts/atomic/get_index_stats.py` |
| "XX 表有多少行/多大" | Layer 1 | `scripts/atomic/get_table_stats.py` |
| "获取 XX 集群的 connector" | Layer 1 | `scripts/atomic/get_db_connectors.py` |
| "查 XX 集群有哪些慢 SQL/慢查询模板" | Layer 1 | `scripts/atomic/get_slow_log_list.py` |
| "采集 XX 实例某时段的原始慢查询" | Layer 1 | `scripts/atomic/get_raw_slow_log.py` |
| "采集 XX 实例的 error log / mysqld.log" | Layer 1 | `scripts/atomic/get_error_log.py` |
| "mysql_exporter 有哪些指标可查" | Layer 1 | 参考 `references/mysql_exporter_metrics.md` |
| "查 XX 指标的完整时序 / 用 PromQL 查" | Layer 1 | `scripts/atomic/query_xray_metrics.py` |
| "帮我诊断/分析 XX 集群的慢查询" | Layer 2 | Phase 0 分诊 → 对应路径 |
| "给我出一份性能/故障分析报告" | Layer 2 | Phase 0 分诊 → 对应路径 |
| "XX 集群发告警了" / "帮我排查一下" | Layer 2 | Phase 0 分诊 → 对应路径 |
| "XX 节点磁盘满了" | Layer 2 | Phase 0 分诊 → 路径 D（磁盘满）|
| "XX 集群主从延迟" | Layer 2 | Phase 0 分诊 → 路径 C1（主从延迟）|
| "XX 集群复制中断/复制停了" | Layer 2 | Phase 0 分诊 → 路径 C2（复制中断）|
| "XX 节点 CPU 高" | Layer 2 | Phase 0 分诊 → 路径 B（CPU 高）|
| "XX 节点 Crash 了" | Layer 2 | Phase 0 分诊 → 路径 E（Crash）|
| "XX 集群带宽告警/网络告警" | Layer 2 | Phase 0 分诊 → 路径 F（机器带宽）|
| "XX 节点 IOWait 高" | Layer 2 | Phase 0 分诊 → 路径 G（IOWait 异常）|
| "XX 集群连接数告警/活跃连接异常" | Layer 2 | Phase 0 分诊 → 路径 B2（连接堆积）|

---

## Layer 1：原子能力

### 1-A. 集群监控指标（现有能力）

```python
from scripts.mysql_monitor import MySQLMonitor

monitor = MySQLMonitor(openclaw_token=os.environ["DMS_CLAW_TOKEN"])  # mysql_monitor.py 沿用 open-claw

# MySQL 集群
overview = monitor.get_mysql_cluster_overview("sns_userauth")

# MyHub 集群
overview = monitor.get_myhub_cluster_overview("sns_userauth")

# 按 DB 名查找集群
clusters = monitor.find_clusters_by_db("userauth", "mysql")
```

支持指标：连接数、活跃线程、QPS（按类型）、慢查询数、InnoDB 缓存命中率、CPU、内存、磁盘、网络流量。

---

### 1-B. 获取数据库连接器

**接口**：`GET /dms-api/ai-api/v1/mysql/meta_data/get_db_connectors`（优先）/ `GET /dms-api/open-claw/meta-data/mysql/get-db-connectors`（兜底）

```bash
# ✅ 推荐：只传集群名，自动识别类型 + 自动选 db_name
python3 scripts/atomic/get_db_connectors.py \
    --cluster redtao_tns \
    [--include_master]
    [--output output/ --run_id my_run_001]

# 手动指定 db_name（覆盖自动推断）
python3 scripts/atomic/get_db_connectors.py \
    --cluster redtao_tns \
    --db      redtao_tns_p00001
```

**自动推断逻辑**：
1. 调用 `cluster/search` 判断 `connectType`
2. `redhub` → 调用 `get-db-list` 枚举物理分片，取第一个 `_p` 分片作为 db_name
3. `mysql/myhub` → 调用 `get-db-list` 取第一个真实业务库名（排除系统库）
4. 全部失败时降级为集群名本身

**返回**：connector 列表 + `_meta` 附加字段：
```json
{
  "_meta": {
    "cluster_type": "redhub",
    "db_name_used": "redtao_tns_p00000",
    "logical_db":   "redtao_tns",
    "shards":       ["redtao_tns_p00000", "redtao_tns_p00001"]
  }
}
```

**关键用途**：后续 explain-sql / get-table-stats / get-index-stats 均需传 `connector`（格式 `normal:ip:port`）。

> ⚠️ 脚本已内置 v1 → open-claw 自动兜底，无需手动切换。connector 返回的是 CMDB 实例直连 IP，支持 `information_schema` 查询。
>
> ⚠️ **分库分表集群**：`_meta.shards` 列出所有物理分片，诊断时需遍历每个分片分别获取 connector，不能只用第一个分片的节点。

---

### 1-C. 执行 EXPLAIN

**接口**：`POST /dms-api/ai-api/v1/mysql/meta_data/explain_sql`（优先）/ `POST /dms-api/open-claw/meta-data/mysql/explain-sql`（兜底）

```bash
python3 scripts/atomic/explain_sql.py \
    --cluster  fls_product \
    --db       my_database \
    --sql      "SELECT * FROM orders WHERE user_id=?" \
    --connector normal:10.0.0.1:3306 \   # 从 get_db_connectors 获取
    [--label top1]                         # 输出文件名标签
    [--output output/ --run_id my_run_001]
```

**stderr 自动输出风险检测**：全表扫描（type=ALL）、全索引扫描、Using filesort、Using temporary。

---

### 1-D. 查询表统计信息

**接口**：`GET /dms-api/ai-api/v1/mysql/meta_data/get_table_stats`（优先）/ `GET /dms-api/open-claw/meta-data/mysql/get-table-stats`（兜底）

```bash
python3 scripts/atomic/get_table_stats.py \
    --cluster   fls_product \
    --db        my_database \
    --table     orders \
    --connector normal:10.0.0.1:3306 \
    [--node_role slave]
    [--output output/ --run_id my_run_001]
```

**返回**：`table_rows`、`data_length`、`index_length`、`update_time` 等。

---

### 1-E. 查询索引统计与区分度

**接口**：`GET /dms-api/ai-api/v1/mysql/meta_data/get_index_stats`（优先）/ `GET /dms-api/open-claw/meta-data/mysql/get-index-stats`（兜底）

```bash
python3 scripts/atomic/get_index_stats.py \
    --cluster    fls_product \
    --db         my_database \
    --table      orders \
    --connector  normal:10.0.0.1:3306 \
    [--index     idx_user_id]       # 不传则返回所有索引
    [--table_rows 5000000]          # 传入则自动计算区分度 = cardinality/table_rows
    [--output output/ --run_id my_run_001]
```

**stderr 自动输出风险检测**：区分度 < 1% 标记"极低区分度（可能数据倾斜）"。

---

### 1-F. 采集原机慢查询日志

**接口**：`POST /dms-api/ai-api/v1/mysql/meta_data/get_raw_slow_log`（优先）/ `POST /dms-api/open-claw/meta-data/mysql/get-raw-slow-log`（兜底）

```bash
python3 scripts/atomic/get_raw_slow_log.py \
    --cluster  fls_product \
    --hostname qsh5-db-fls-product-122 \   # vm_name，从 get_db_connectors include_master 拿主库
    --start   "2026-03-25 06:00:00" \      # UTC 时间
    --end     "2026-03-25 06:10:00" \      # UTC，窗口 ≤ 10 分钟
    [--db              my_db] \
    [--min_query_time  1.0] \
    [--limit           200]
    [--output output/ --run_id my_run_001]
```

**返回**：`summary`（总数、唯一模板数）、`details`（明细）、`top_sql`（聚合排序）、`timeline`（分钟级时间线）。

> ⚠️ `start_time` / `end_time` 为 **UTC** 时间，北京时间 -8 小时换算。时间窗口不能超过 10 分钟。

#### 🔄 超过 10 分钟时：自动切分循环调用

**当诊断时间窗口超过 10 分钟时**（如需采集 17:10~17:30 共 20 分钟），**必须按 10 分钟切分，循环调用，合并结果**。

```python
# AI 编排时使用此模式（伪代码）
from datetime import datetime, timedelta
import os, json

def fetch_slow_log_range(cluster, hostname, start_bj, end_bj, out_dir):
    """
    start_bj / end_bj：北京时间字符串，如 "2026-03-30 17:10:00"
    自动按 10min 切分，每段调用一次 get_raw_slow_log，
    所有段结果合并输出到 out_dir/get_raw_slow_log_merged.json
    """
    start = datetime.strptime(start_bj, "%Y-%m-%d %H:%M:%S")
    end   = datetime.strptime(end_bj,   "%Y-%m-%d %H:%M:%S")
    window = timedelta(minutes=10)
    seg_no = 0
    all_raw_texts = []

    cur = start
    while cur < end:
        seg_end = min(cur + window, end)
        # 北京 → UTC（-8h）
        utc_start = (cur     - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        utc_end   = (seg_end - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        seg_dir   = f"{out_dir}/seg_{seg_no:02d}_{cur.strftime('%H%M')}_{seg_end.strftime('%H%M')}"

        os.system(f"""python3 scripts/atomic/get_raw_slow_log.py \
            --cluster {cluster} --hostname {hostname} \
            --start "{utc_start}" --end "{utc_end}" \
            --limit 500 --output {seg_dir} --run_id seg_{seg_no}""")

        seg_json = f"{seg_dir}/raw/get_raw_slow_log.json"
        if os.path.exists(seg_json):
            d = json.load(open(seg_json))
            raw = (d.get("data") or {}).get("raw_text") or ""
            if raw:
                all_raw_texts.append(raw)

        seg_no += 1
        cur = seg_end

    return "\n".join(all_raw_texts)
```

> ⚠️ **关键**：接口 `data` 字段中，慢日志是**原始文本**（MySQL slow log 格式），不是结构化 JSON 数组。必须用正则解析 `# Time:` 分隔块，不能直接用 `data.slow_logs[]` 字段。

---

### 1-G. 慢日志聚合列表（CK）

**接口**：`GET /dms-api/ai-api/v1/mysql/slow_query/slow_log_list`（优先）/ `GET /dms-api/v1/mysql/slow-query/slow-log-list`（兜底）

```bash
python3 scripts/atomic/get_slow_log_list.py \
    --cluster  fls_product \
    --start   "2026-03-25 00:00:00" \   # 本地时间（非 UTC）
    --end     "2026-03-25 01:00:00" \   # 时间范围不限
    [--db              my_db] \
    [--keyword         keyword] \
    [--page            1] \
    [--page_size       20] \
    [--sort            desc]            # 按慢查询数排序
    [--output output/ --run_id my_run_001]
```

**返回**：按库/SQL 模板聚合的慢查询列表，含分页。

---

### 1-H. 活跃会话（双路采集）

**接口**：
- CK 历史快照：`POST /dms-api/v1/mysql/session-manage/get-his-process-count-list` + `POST /dms-api/v1/mysql/session-manage/get-his-process-group-and-detail-list`
- 实时采集：`POST /dms-api/v1/mysql/session-manage/get-cur-process-list`

```bash
python3 scripts/atomic/get_active_sessions.py \
    --cluster  <cluster> \
    --vm_name  <master_vm_name> \          # 从 get_db_connectors 获取主库 vm_name
    --ip       <master_ip> \               # 主库 IP
    --port     <master_port> \             # 主库 Port
    --fault_time "<北京时间 YYYY-MM-DD HH:MM:SS>" \   # 故障时刻，用于 CK 选点
    [--min_time 0] \                       # 实时采集：过滤运行超过 N 秒的线程
    [--output output/ --run_id <RUN_ID>]
```

**返回结构**：
```json
{
  "history_snapshot": {
    "snapshot_time": "2026-04-01 10:00:00",   // CK 存档时刻（最近 ≤ 故障时刻）
    "note": "CK 历史快照，故障时刻存档",
    "connectionList": [...],                   // 每条连接明细（ID/User/DB/SQLText/State/Time）
    "processGroupList": [...],                 // SQL 指纹聚合（fingerprint/total_num/state_count）
    "connectionCount": 42
  },
  "realtime": {
    "collect_time": "2026-04-01 10:05:00",    // 实际采集时刻
    "note": "实时采集，故障可能已缓解，仅供参考",
    "connectionList": [...],
    "connectionCount": 8
  },
  "_analysis": {                              // 基于实时数据，供 Phase 0 推理
    "total_active": 8,
    "long_running_count": 2,
    "lock_waiters_count": 0,
    "relay_waiters_count": 0,
    "risks": [...]
  }
}
```

**关键说明**：
- `history_snapshot`：故障发生时的真实现场，CK 每 1~2 分钟采集一次，选最近 ≤ fault_time 的时间点
- `realtime`：当前时刻的快照，**故障可能已自愈**，分析时须注明时间差
- `_analysis.risks` 兼容 Phase 0 推理矩阵（`lock_waiters_count`、`relay_waiters_count` 等字段）

---

### 1-I. 采集 Error Log（mysqld.log）

**接口**：`POST /dms-api/ai-api/v1/mysql/meta_data/get_error_log`（优先）/ `POST /dms-api/open-claw/meta-data/mysql/get-error-log`（兜底）

```bash
python3 scripts/atomic/get_error_log.py \
    --hostname qsh8-db-redtao-antispam-u5trt-11 \
    --start "2026-04-02 04:25:00" \   # 北京时间
    --end   "2026-04-02 04:35:00" \   # 北京时间，窗口 ≤ 60 分钟
    [--level_filter "Error,Warning"] \ # 可选，逗号分隔
    [--keyword "page_cleaner"] \       # 可选，关键词过滤
    [--output output/ --run_id my_run_001]
```

**返回**：`summary`（error/warning/note 计数、关键词命中）、`entries`（每行一条：timestamp、thread_id、level、message）、`raw_text`（原始文本）。

**与 get_raw_slow_log 的区别**：
- 采集的是 `@@global.log_error`（mysqld.log），不是 slow log
- 时间输入为**北京时间**（非 UTC），时间窗口放宽到 60 分钟
- mysqld.log 每行一条（ISO 格式时间戳），解析更简单
- 返回按行结构化，无需聚合模板

**适用场景**：
- Crash 诊断（路径 E）：查看崩溃前后的 Error/Warning 日志
- InnoDB 性能问题：`page_cleaner`、`buffer pool` 相关告警
- 锁/死锁分析：`deadlock`、`killed` 关键词检测

---

### 1-J. mysql_exporter 指标参考

**静态参考文件**：`references/mysql_exporter_metrics.md`

采集自 redtao_antispam 主库 (exporter port 9104)，包含 mysql_exporter 暴露的全部 MySQL 指标。

**文件结构**：
- **Part 1：关注项**（运行状态指标）— 故障诊断核心数据源，按功能分类：Buffer Pool、I/O & Redo Log、Row Lock、Connections、Commands、Slow Queries、Replication、Table/Open Resources、Network、Uptime、Info Schema 等
- **Part 2：配置项**（全局变量）— InnoDB 配置、复制配置、连接配置等，含当前值

**使用方式**：
- 需要查某个指标的 PromQL 名称时，直接查阅此文件
- 找到指标名后，用 `query_xray_metrics.py --pql '<指标名>{cluster_name="xxx"}'` 查询完整时序

**适用场景**：
- 发现可用的监控指标名（如 `mysql_global_status_innodb_buffer_pool_wait_free`）
- 了解指标的类型（counter/gauge/untyped）和含义
- 作为 `query_xray_metrics.py` 的 PromQL 输入参考

---

### 1-K. 任意 PromQL 完整时序查询

**接口**：`POST /dms-api/ai-api/v1/grafana/fetch_data_by_pql`（优先）/ `POST /dms-api/open-claw/grafana/fetch-data-by-pql`（兜底）

```bash
python3 scripts/atomic/query_xray_metrics.py \
    --pql 'rate(mysql_global_status_innodb_buffer_pool_wait_free{cluster_name="redtao_antispam"}[1m])' \
    --start "2026-04-02 04:15:00" \   # 北京时间
    --end   "2026-04-02 04:45:00" \   # 北京时间
    [--step 15] \                      # 采样间隔，默认 15 秒
    [--vmname "qsh8-db-redtao-antispam-u5trt-11"] \  # 客户端过滤
    [--datasource vms-db] \            # 默认 vms-db
    [--label wait_free_rate] \         # 输出文件名标签
    [--output output/ --run_id my_run_001]
```

**返回**：每个 series 含完整 `data_points`（timestamp、time_beijing、value）和 `_summary`（min、max、avg、data_points）。

**与 mysql_monitor.py 的区别**：

| | `mysql_monitor.py` | `query_xray_metrics.py` |
|---|---|---|
| 形态 | Python 类方法 | 独立 CLI 脚本 |
| PromQL | 硬编码固定指标 | 任意 PQL |
| 返回 | 只取 `values[-1]` | 完整时序 |
| step | 默认 30 | 默认 15 |
| 时间输入 | Unix timestamp | 北京时间字符串 |
| vmname 过滤 | 不支持 | 支持客户端过滤 |
| 摘要统计 | 无 | `_summary: {min, max, avg, data_points}` |

**适用场景**：
- 需要查看指标在某个时间段的**变化趋势**（而非一个点）
- 需要 15 秒粒度的精细时序数据
- 需要用自定义 PromQL（如 rate、histogram_quantile）查询

---

### 慢查询两种采集方式对比

| | `get_slow_log_list`（CK） | `get_raw_slow_log`（原机 DMS API） |
|---|---|---|
| 数据源 | ClickHouse 聚合表 | 业务机 slow log 文件（DMS 后端采集） |
| 时间范围 | 不限 | ≤ 10 分钟（UTC 入参） |
| 返回粒度 | 按库/模板聚合 | 原始明细 + 聚合 + timeline |
| 需要 hostname | ❌ | ✅（vm_name 或 IP） |
| 适用场景 | 宏观定位：哪个库/哪类 SQL 慢 | 精确分析：某实例某时段的原始慢 SQL |

**选择建议**：
- 先用 `get_slow_log_list` 宏观定位问题库和 SQL 模板
- 再用 `get_raw_slow_log` 精确定位具体实例的原始慢查询明细

---

### ⚠️ 时区速查表

> 除 `get_raw_slow_log.py` 需要 **UTC**（北京时间 -8h）外，其余脚本 `--start`/`--end` 一律填**北京时间**。

| 脚本 | 入参时区 | 备注 |
|------|---------|------|
| `query_xray_metrics.py` | 北京时间 | 内部自动转 UTC，输出 `time_beijing` |
| `get_slow_log_list.py` | 北京时间 | - |
| `get_error_log.py` | 北京时间 | 窗口 ≤ 60 分钟 |
| `get_network_traffic.py` | 北京时间 | 内部自动转 UTC |
| `get_active_sessions.py` | 北京时间 | `--fault_time` 参数 |
| `get_raw_slow_log.py` | ⚡ **UTC** | 北京 -8h，窗口 ≤ 10 分钟，跨日注意日期 |

---

## Layer 2：诊断场景

> ⚠️ **强制规则**
> 1. **AI 是编排者**，直接逐步调用 atomic 脚本，无任何中间编排脚本
> 2. **必须先完成 Phase 0 分诊**，确认问题类型后再进入对应路径，不得跳过
> 3. 必须在**所有数据收集完毕后**，才能开始分析和生成报告
> 4. 不得因"用户已提供部分信息"而跳过任何数据收集步骤
> 5. 报告必须严格遵循下方 **8 章节 HTML 规范**，不得缩减

---

### Phase 0 · 问题类型分诊（所有路径的统一入口，不可跳过）

**P0-1 · 提取基本信息**

从用户输入提取（告警类型不强求，AI 主动探测）：

| 字段 | 是否必须 | 说明 |
|------|---------|------|
| 集群名 | ✅ 必须 | 无则追问 |
| 告警时间 | ✅ 必须 | 无则追问 |
| 告警节点 vm_name | 可选 | 有则探测更精准 |
| 告警原文/类型 | 可选 | 用户能清晰描述则直接进 P0-3，否则 AI 主动探测 |

---

**P0-2 · AI 主动探测推理**

> 用户未提供明确告警类型时，AI 并发执行以下 3 路探测（约 10~15 秒），自主推理问题类型。
> ⚠️ 三路探测必须**同时发起**（后台并发），不得串行等待。

**探测 A · CK 慢查询量化 + SQL 分类（Phase 0 专用模式）**
```bash
python3 scripts/atomic/get_slow_log_list.py \
    --cluster <cluster> \
    --start "<告警时间前1小时 本地时间>" \
    --end   "<告警时间 本地时间>" \
    --phase0
# 输出 _phase0_summary，关键字段：
#   total         — 总慢查询条数
#   level         — none / light / moderate / severe
#   by_type       — business / info_schema / dts 各自数量
#   noise_dominated — True → info_schema > 90%，大概率背景噪声
#   dts_dominated   — True → DTS Checksum 主导
#   risks         — 推理结论列表
```

**探测 B · 节点可达性 + 从库延迟**
```bash
# Step B1：获取节点列表（验证集群可达）
python3 scripts/atomic/get_db_connectors.py \
    --cluster <cluster> --db mysql
# 正常返回 → 节点存活；报错 → 可能 Crash 或集群名有误

# Step B2：查从库延迟（取第一个从库 vm_name）
python3 scripts/atomic/get_slave_status.py \
    --cluster <cluster> --hostname <slave_vm_name>
# sqlDelay > 30  → 主从延迟信号
# sqlDelay > 300 → 严重延迟
# sqlDelay = 0   → 复制正常
# sqlDelay = None → 可能是主库节点，换其他从库重试
```

**探测 C · 活跃连接 & 线程堆积（双路采集）**
```bash
# 双路模式（推荐）：CK 历史快照（故障时刻） + 实时采集（当前）
python3 scripts/atomic/get_active_sessions.py \
    --cluster <cluster> \
    --vm_name <vm_name> \
    --ip <ip> \
    --port <port> \
    --fault_time "YYYY-MM-DD HH:MM:SS"   # 故障时刻（北京时间），用于 CK 历史快照选点
# 若仅需实时采集（告警已缓解时），省略 --fault_time 即可

# 输出结构：
#   history_snapshot.connectionCount  — CK 快照连接数（故障时刻）
#   history_snapshot.processGroupList — CK 快照 SQL 聚合（各指纹执行数量）
#   realtime.connectionCount          — 当前实时连接数
#   _analysis.total_active            — 活跃线程总数（> 100 → 连接堆积）
#   _analysis.long_running_count      — 运行 >30s 线程数（> 5 → 线程池趋于饱和）
#   _analysis.lock_waiters_count      — 锁等待线程数（> 0 → 锁竞争）
#   _analysis.relay_waiters_count     — relay log 等待（> 0 → 主从延迟）

# 查连接数时序（10s 粒度，适合定位锁爆发时刻）：
# 直接调用 DMS API：
# POST /dms-api/v1/mysql/session-manage/get-his-process-count-list
# Body: {"vm_name":"<vm_name>","start_time":"YYYY-MM-DD HH:MM:SS","end_time":"YYYY-MM-DD HH:MM:SS","filter":{"show_system_session":false}}
# 返回 [{createTime, count}] 列表，可绘制连接数时序曲线
```

> 💡 **磁盘告警**：仅当用户**明确说磁盘/空间告警**时，在 Phase 0 中追加探测 D：
> ```bash
> python3 scripts/atomic/get_disk_usage.py --cluster <cluster>
> ```

---

**推理矩阵（量化多维信号 → 推理类型）**

> 优先级从上到下，命中第一条则停止。

| 探测 A（CK 慢查询） | 探测 B（节点/延迟） | 探测 C（活跃连接） | 推理类型 |
|-------------------|------------------|--------------------|---------|
| level=none/light，任意 | 不可达 | 任意 | **Crash → 路径 E** |
| 任意 | 不可达 | 任意 | **Crash + 慢查询并发 → 路径 E 优先，路径 A 待恢复后分析** |
| level=severe/moderate，business > 0，noise_dominated=False，dts_dominated=False | 正常，delay < 30s | relay_waiters = 0 | **业务慢 SQL → 路径 A** |
| level=severe/moderate，noise_dominated=True | 正常，delay < 30s | 正常 | **背景噪声主导**，告警来源需确认；进路径 A 但优先分析业务 SQL，标注 info_schema 为背景噪声 |
| level=severe/moderate，dts_dominated=True | 正常，delay < 30s | 正常 | **DTS Checksum → 路径 A**，根因标注为运维操作非业务问题 |
| level=moderate/severe，任意 | 正常，delay > 30s | relay_waiters > 0 | **主从延迟（慢 SQL 是表象）→ 路径 C** |
| level=none/light | 正常，delay > 30s | 任意 | **主从延迟 → 路径 C** |
| level=none/light | 正常，delay < 30s | total_active > 100 且 cpu_usage < 70% | **连接堆积 → 路径 B2**（独立于 CPU 高，见注1）|
| level=none/light | 正常，delay < 30s | total_active > 100 或 long_running > 5 | **CPU 高 → 路径 B** |
| level=none/light | `Slave_SQL_Running=No` 或 `Slave_IO_Running=No` | 任意 | **复制中断 → 路径 C2**（区别于延迟，见注2）|
| level=none/light | 正常，delay < 30s | 正常 | 用户说"带宽告警" → **机器带宽 → 路径 F** |
| level=none/light | 正常，delay < 30s | 正常 | 用户说"IOWait 高" → **IOWait 异常 → 路径 G** |
| level=none/light | 正常，delay < 30s | 正常 | **不确定 / 告警已自愈**，向用户说明并等待确认 |
| 任意（用户明确说磁盘） | 正常 | 任意 | **磁盘满 → 路径 D** |
| level=moderate/severe，任意 | 正常，delay < 30s | 正常 | **业务慢 SQL + 磁盘风险待确认 → 路径 A**，建议人工核查磁盘 |

**关键推理规则（必须遵守）：**

1. **noise_dominated=True 时不能直接定性为慢 SQL 根因**：info_schema 高频查询是 ORM/监控系统副作用，必须单独说明，重点分析业务库的慢 SQL
2. **delay > 30s 时，慢 SQL 数量多不代表慢 SQL 是根因**：主从延迟会导致从库堆积大量慢查询，路径 C 优先
3. **level=light 时优先考虑告警已自愈**：不要直接跳路径 A，先向用户确认告警是否还在
4. **dts_dominated=True 时根因标注为运维操作**：DTS Checksum 是正常运维行为，结论中应标注"非业务 SQL 问题"
5. **注1：连接堆积 ≠ CPU 高**：`total_active > 100` 但 `cpu_usage < 70%` 时，走路径 B2（连接堆积），不走路径 B（CPU 高）。两者根因不同：CPU 高是计算资源耗尽，连接堆积是连接池泄漏或慢查询堵塞线程
6. **注2：复制中断 ≠ 复制延迟**：`Slave_SQL_Running=No / Slave_IO_Running=No` 是复制链路断裂（路径 C2），`sqlDelay > 30s` 是复制延迟（路径 C1）。中断必须先查 `Last_Error`，不能走延迟诊断链
7. **带宽告警触发词优先于慢查询**：用户说"带宽"/"network"/"机器带宽"时，即使慢查询 level=moderate，也优先走路径 F，两者可能并存

---

**P0-3 · 推理置信度评估 → 确认或直接执行**

> **置信度规则（新）：推理结论唯一命中推理矩阵且无歧义信号时，不停下来等确认，直接进入对应路径执行完整分析，直到出 HTML 报告。**

**置信度 HIGH（直接执行）条件（同时满足）：**
- 推理矩阵只命中一行（无歧义）
- 探测 A/B/C 三路均返回有效数据（无 HTTP 400 / 无空结果）
- 无动态回溯触发信号

**置信度 LOW（向用户确认）条件（满足任一）：**
- 推理矩阵命中多行（存在歧义）
- 任一探测路全部失败（无法支撑推理）
- 发现动态回溯触发信号
- 用户的告警描述与探测数据明显矛盾

**置信度 HIGH 时的输出格式：**

```
📊 Phase 0 探测完成，置信度高，直接进入路径 X：
  · 慢查询：{total} 条（{level}），业务 {business} / info_schema {info_schema} / DTS {dts}
  · 节点：正常 / 从库延迟：{N}s
  · 活跃线程：{total_active}（长查询 {long_running}，锁等待 {lock_waiters}）
  · 推理：命中"XX → 路径 X"，依据：{命中条件描述}
  ▶ 开始执行路径 X...
```

**置信度 LOW 时的输出格式（等确认）：**

输出格式（必须展示量化探测依据，不能只给结论）：

```
📊 Phase 0 探测结果：
  · 慢查询（CK）：{total} 条，量级 {level}
      业务 SQL：{business} 条 / info_schema：{info_schema} 条 / DTS：{dts} 条
      噪声主导：{是/否} / DTS 主导：{是/否}
  · 节点可达性：{正常/不可达}
  · 从库延迟：sqlDelay={N}s
  · 活跃线程：{total_active} 个（长查询 {long_running} 个，锁等待 {lock_waiters} 个）

🔍 推理结论：
  主要问题：XX 类型
  依据：（列出命中的推理矩阵条件）
  附加风险：XX（若有）
  ⚠️ 背景噪声：（若 noise_dominated=True，单独标注）

📌 建议按【XX 路径】排查，确认继续？（或说"不对"让我重新判断）
```

用户回复"对/继续" → 进入对应路径
用户回复"不对" → 追问哪里不对 → 修正后重走 P0-2

---

**动态回溯触发信号**

排查途中发现以下信号时，立即暂停当前路径，保留已采集数据，重走推理矩阵：

| 信号 | 出现步骤 | 可能真实类型 |
|------|---------|------------|
| CK + 原机慢日志双路均为 0 | Step 2 | 非慢 SQL，重走推理 |
| `file_size_mb = 0.0` | Step 2b | slow_query_log=OFF 或 Crash |
| `get_db_connectors` Invalid param | Step 1 | 集群名/db 有误 |
| 大量 `Waiting for relay log` | 路径 B/A | 主从延迟 → 路径 C |
| `sqlDelay > 300` | 任意路径 | 切换路径 C |
| 节点完全不可达 | 任意 | Crash → 路径 E |
| 路径 A 中发现慢 SQL 全为 info_schema | Step 2 | 背景噪声，标注后继续寻找业务 SQL |
| 路径 A 中发现 DTS Checksum SQL | Step 2 | 标注为运维操作，结论写"非业务 SQL 问题" |

---

### 路径选择

| 路径 | 问题类型 | 说明 |
|------|---------|------|
| 路径 A | 慢 SQL | → 场景一：慢查询诊断（原 Step 0~6，不变）|
| 路径 B | CPU 高 | → 场景二：CPU 高诊断 |
| 路径 B2 | 连接堆积（cpu < 70%） | → 场景六：连接堆积诊断 |
| 路径 C1 | 主从延迟（delay > 30s） | → 场景三：主从延迟诊断 |
| 路径 C2 | 复制中断（SQL/IO Thread=No） | → 场景七：复制中断诊断 |
| 路径 D | 磁盘满 | → 场景四：磁盘满诊断 |
| 路径 E | Crash | → 场景五：Crash 诊断 |
| 路径 F | 机器带宽告警 | → 场景八：机器带宽诊断 |
| 路径 G | IOWait 异常 | → 场景九：IOWait 诊断 |

---

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
> - 已识别至少 1 个"持锁者"SQL（lock_ratio < 20% 且 query_time 最长）
> - 已计算所有业务表的索引区分度
> - 已整合 2d/2e/2f 辅助数据（采集失败的标注"未采集"）
> - 8 章节内容全部有对应数据填充（无数据的字段标"未采集"而非留空）

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

```bash
# 1. 自动生成复盘报告（从 raw/*.json 扫描组装 §1~§7）
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>
# → 输出：<OUT_DIR>/report_process_review_<RUN_ID>.html

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-slow_query-process_review.html
# → 获得 review_dms_url

# 3. 记录复盘报告 URL 到 run_meta.json
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送复盘报告链接
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：慢查询\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```

> **📦 交付物**：`report_process_review_<RUN_ID>.html`，DMS URL 已推送到群
>
> **✅ 验收条件**：
> - `generate_process_review.py` 输出 `✅ 复盘报告已生成`，文件存在
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
> - 若复盘报告不存在，自动先调用 `generate_process_review.py` 补生成
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

> ⚠️ 报告必须严格包含以下全部 8 章节，不得缩减或合并。
> 样式风格参考 `fls_product_incident_report.html`（深色 Banner + 卡片布局 + KPI 格子 + 图表 + 链式时间线）。

---

**第 1 章 · 告警概览（Alert Overview）**

必须包含以下 KPI 指标格子（有数据填数据，无数据标"未采集"）：

| KPI | 数据来源 |
|-----|---------|
| CPU 峰值（%） | 告警事件 / 用户提供 |
| Load Average | 告警事件 / 用户提供 |
| QPS 变化（正常值 → 告警值） | 告警事件 / 用户提供 |
| 慢查询总数（条） | raw_slow_log.summary.total_slow_queries |
| 唯一 SQL 模板数 | raw_slow_log.summary.unique_templates |
| 最长慢查询时长（s） | raw_slow_log 明细 max(query_time) |
| 最长锁等待时长（s） | raw_slow_log 明细 max(lock_time) |
| 故障持续时间 | 用户提供 / 时间线推断 |
| 受影响分片 & 机器 | get_db_connectors master vm_name |

---

**第 2 章 · 故障时间线（Timeline）**

必须包含：
1. **慢查询分钟级柱状图**（JavaScript Canvas/DOM 动态渲染）：
   - X 轴：北京时间（分钟）
   - Y 轴左：慢查询数量（蓝色柱）
   - Y 轴右：max_query_time（橙色柱）
   - 数据来源：`raw_slow_log.data.timeline`
2. **事件链（chain）**：每个关键节点一条，格式为 `时间 · 事件标题 · 事件描述`
   - 节点类型：trigger（触发）/ root（根因）/ effect（影响）/ recover（恢复）
   - 颜色编码：橙=trigger、红=root、紫=effect、绿=recover

---

**第 3 章 · 根因分析（Root Cause Analysis）**

必须包含：
1. **直接触发者**：执行次数最多 or query_time 最长的持锁 SQL，含完整表格（SQL 模板、条数、avg_qt、max_qt、avg_lock、rows_examined、执行计划结论）
2. **数据倾斜证据**：`index_stats` 中区分度最低的索引，配合 rows_examined 峰值说明倾斜倍数
3. **锁传导链（lock chain）**：lock_ratio > 50% 的 SQL 作为"等锁受害者"，用卡片形式列出（参考 fls_product_incident_report.html 中的 `.lock-grid`）
4. **根因归纳表**：按层次（业务层/数据层/索引层/参数层）逐条归纳，每行对应 tag 颜色标注优先级

---

**第 4 章 · 慢查询 Top 10 分布（Top 10 Slow Queries）**

必须包含：
1. **水平条形图**（avg_query_time 为宽度，lock% 标注）：数据来源 `raw_slow_log.top_sql` + `slow_log_list`
2. **详细表格**（每行一个 SQL 模板）：

| 列名 | 来源 |
|------|------|
| # | 排名 |
| SQL 模板（脱敏，保留结构，最多 120 字符）| raw_slow_log.top_sql[].sql_template |
| 来源服务 | raw_slow_log 明细中的 user / host 字段 |
| 执行次数 | top_sql[].count |
| avg_qt(s) | top_sql[].avg_query_time |
| max_qt(s) | top_sql[].max_query_time |
| avg_lock(s) | top_sql[].avg_lock_time |
| lock% | avg_lock / avg_qt × 100 |
| 角色 | lock% < 5% → 持锁者；lock% > 50% → 等锁受害 |

---

**第 5 章 · 表统计信息 & 执行计划（Table Stats & EXPLAIN）**

对每张涉及的业务表，输出：
1. **表统计**（来源 `table_stats_<table>.json`）：
   - table_rows、data_length（MB）、index_length（MB）、update_time
2. **索引区分度表**（来源 `index_stats_<table>.json`）：
   - 每个索引每列的 cardinality、区分度 = cardinality/table_rows
   - 区分度 < 5% 标红，< 1% 标"极低 ⚠️"
3. **EXPLAIN 结果表**（来源 `explain_top*.json`）：
   - id、select_type、table、type、possible_keys、key、rows、filtered、Extra
   - type=ALL 标红，type=range/ref 标蓝，Using filesort/temporary 标橙
   - 附"优化器估算 vs 实际 rows_examined"对比（说明统计信息是否失准）

---

**第 6 章 · 影响范围（Impact Assessment）**

表格形式，必须包含以下维度：

| 维度 | 内容 |
|------|------|
| 受影响实例 | 主库 + 从库（从 get_db_connectors 获取所有节点）|
| 受影响业务服务 | 从 raw_slow_log 明细的 user/host 字段提取 |
| QPS 跌幅 | 正常值 → 告警值，跌幅百分比 |
| 用户可见影响 | 写入积压 / 超时 / 降级（根据业务判断）|
| 数据完整性 | 事务最终状态（提交/回滚）|
| 故障等级 | P0/P1/P2（根据 QPS 跌幅 + 持续时间判断）|

---

**第 7 章 · 改进建议（Recommendations）**

卡片网格布局（参考 `.rec-grid`），必须包含：
- **P0（立即）**：直接消除故障根因的措施，必须具体到表名/SQL/参数
- **P1（本周内）**：防止复发的中期措施
- **P2（迭代内）**：架构优化/长期改进

每张建议卡片必须包含：优先级标签 + 标题 + 具体描述（含可执行的 SQL 或配置）。

---

**第 8 章 · 附录（Appendix）**

必须包含：
1. **数据来源说明**：每类数据对应的接口/脚本
2. **核心 SQL 样本**（`<pre>` 代码块）：持锁者原始 SQL（来自 raw_slow_log 明细）
3. **等锁受害者样本**：lock_ratio 最高的 SQL 原始文本

---

#### SQL 清洗规则（EXPLAIN 前执行）

```python
import re
# 1. 去掉 TRACE 注释块
sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL).strip()
# 2. SELECT 字段列表替换为 *（避免 created_at/created_by 触发服务端关键词检测）
sql = re.sub(r'(?i)(SELECT)\s+.+?\s+(FROM\b)', r'SELECT * \2', sql, flags=re.DOTALL)
```

---

#### 业务 SQL 过滤规则

以下 SQL 视为非业务，跳过不分析：
- SQL 中包含 `information_schema.TABLES`、`information_schema.STATISTICS`、`performance_schema.`
- SQL 以 `-- 表使用数据`、`-- 索引使用数据` 开头（DMS 自身采集 SQL）
- SQL 涉及的 database 全部为系统库（`information_schema`、`mysql`、`sys`、`performance_schema`）

---

## 输出目录结构

每次 Layer 2 诊断在 `mysql-monitor/output/<RUN_ID>/` 下产出：

```
output/live_ds_20260326_103319/
  raw/
    get_db_connectors.json       # Step 1 产出，connector 列表
    get_raw_slow_log.json        # Step 2 产出，慢日志原始数据
    explain_top1.json            # Step 3 产出，TOP 1 SQL EXPLAIN
    explain_top2.json            # Step 3 产出，TOP 2 SQL EXPLAIN
    explain_top3.json            # Step 3 产出，TOP 3 SQL EXPLAIN
    table_stats_<table>.json     # Step 3 产出，各表统计
    index_stats_<table>.json     # Step 3 产出，各表索引统计
  report_live_ds_20260326_103319.html   # Step 5 产出，AI 直接生成
```

> `output/` 目录不提交到仓库（已加入 .gitignore）。
> `table_stats` + `index_stats` 在 Step 4 由 AI 在内存中整合，不需要额外写文件。

---

## 集群类型说明

| 类型 | cluster_name 格式 | 示例 |
|------|-----------------|------|
| MySQL | 下划线格式 | `sns_userauth` |
| MyHub | 下划线格式（自动转连字符） | `sns_userauth` → `sns-userauth` |
| redhub（分库分表） | 下划线格式 | `redtao_tns`，物理分片为 `redtao_tns_p00000` / `redtao_tns_p00001` |

---

## 分库分表集群（redhub 类型）信息获取规范

> ⚠️ redhub 集群的数据分散在多个物理分片上，信息获取方式与普通集群不同。
> 以下规范基于 2026-04-01 redtao_tns 实战验证。

### Step 0：判断是否为分库分表集群

```bash
curl -s "https://dms.devops.xiaohongshu.com/dms-api/v1/mysql/base/cluster/search?key_word=<cluster_name>" \
  -H "dms-claw-token: $DMS_CLAW_TOKEN" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
for c in d.get('data',[]):
    print(f\"connectType={c.get('connectType')} shardNum={c.get('shardNum')}\")
"
# connectType=redhub → 分库分表，走本节规范
# connectType=mysql  → 普通集群，正常流程
```

### Step 1：枚举物理分片库名

```bash
# get-db-list 返回逻辑库名 + 所有物理分片库名
curl -s "https://dms.devops.xiaohongshu.com/dms-api/v1/mysql/base/get-db-list?cluster_name=<cluster>" \
  -H "dms-claw-token: $DMS_CLAW_TOKEN" \
  | python3 -c "
import sys,json
dbs=json.load(sys.stdin).get('data',[])
shards=[d for d in dbs if '_p' in d]   # 物理分片：含 _p00000 格式
print('物理分片:', shards)
"
# redtao_tns 返回：['redtao_tns', 'redtao_tns_p00000', 'redtao_tns_p00001']
# 过滤出 _p 开头的即为物理分片库
```

### Step 2：各接口的 db_name 选择规则

| 接口 | 传哪个 db_name | 原因 |
|------|--------------|------|
| `get-create-table`（DDL） | **逻辑库名** `redtao_tns` | DMS 元数据层，逻辑层统一管理 |
| `get-table-list` | **逻辑库名** `redtao_tns` | 同上，返回逻辑表名 |
| `get_db_connectors` | **物理分片库名** `redtao_tns_p00000` | 获取该分片的实际节点 IP |
| `get-table-stats` | **物理分片库名** `redtao_tns_p00000` | 直连物理节点查 information_schema |
| `get-index-stats` | **物理分片库名** `redtao_tns_p00000` | 同上，cardinality 来自物理节点统计 |
| `get-raw-slow-log` | 不需要 db_name | 传 hostname（物理节点 vm_name）即可 |
| `get-slow-log-list`（CK） | **物理分片库名** `redtao_tns_p00000` | CK 按物理库记录 |

> ⚠️ **常见错误**：对 redhub 集群传逻辑库名调用 `get-table-stats` / `get-index-stats`，
> 返回 500 `Unknown database 'xxx'`。这不是接口废弃，是因为逻辑库名在物理节点不存在。

### Step 3：完整信息获取流程

```bash
CLUSTER="redtao_tns"
SHARD="redtao_tns_p00000"   # 取第一个物理分片（或遍历所有分片）
LOGICAL_DB="redtao_tns"
TABLE="association_tns_str"

# 3a. 获取 connector（必须用物理分片库名）
python3 scripts/atomic/get_db_connectors.py \
    --cluster $CLUSTER --db $SHARD

# 3b. 获取 DDL（用逻辑库名）
curl -s "https://dms.devops.xiaohongshu.com/dms-api/v1/mysql/sql-query/get-create-table\
?cluster_name=$CLUSTER&db_name=$LOGICAL_DB&table_name=$TABLE" \
    -H "dms-claw-token: $DMS_CLAW_TOKEN"

# 3c. 获取表统计（用物理分片库名 + connector）
python3 scripts/atomic/get_table_stats.py \
    --cluster $CLUSTER --db $SHARD --table $TABLE \
    --connector normal:<ip>:<port> --node_role slave

# 3d. 获取索引统计（用物理分片库名 + connector）
python3 scripts/atomic/get_index_stats.py \
    --cluster $CLUSTER --db $SHARD --table $TABLE \
    --connector normal:<ip>:<port> --node_role slave
```

### Step 4：多分片数据聚合说明

`get-index-stats` 对分库分表会返回**每个物理分片各自的统计**（cardinality 因分片数据分布而异）：

```
# 示例：redtao_tns_p00000 的 association_tns_str PRIMARY KEY
分片1 cardinality: from_id=9,609,808  assoc_type=11,574,983  to_id=21,207,814
分片2 cardinality: from_id=8,706,342  assoc_type=13,069,295  to_id=19,701,768
```

**聚合建议**：
- `table_rows`：各分片求和（反映总数据量）
- `cardinality`：取各分片均值（反映整体区分度）
- 数据倾斜判断：各分片 `table_rows` 的最大值 / 最小值 > 2 → 存在分片倾斜

### Step 5：慢查询分析注意事项

- CK 慢查询按**物理分片库名**分组（`redtao_tns_p00000`），不会聚合到逻辑库
- p00000 和 p00001 的执行次数可能差异悬殊（数据倾斜导致，如 p00000:501445次 vs p00001:21次）
- 诊断时需**逐分片分析**，不能只看其中一个
- 超级节点（某 from_id 边数异常多）只会出现在特定分片，其他分片表现正常

---

## 常见问题

**Q：get_db_connectors 返回空或 LB 地址？**
脚本已内置 v1 → open-claw 自动兜底。若两个接口均返回空，确认集群名是否正确，或检查 Token 是否有效。

**Q：get_raw_slow_log 超时或无数据？**
- 确认 `hostname` 是 vm_name 而非 IP
- 时间窗口不超过 10 分钟
- 时间为 UTC，注意北京时间 -8 小时

**Q：EXPLAIN type=ALL 怎么处理？**
参考 `references/pitfalls.md` 中的索引优化建议。

**Q：DMS 文件上传失败？**
确认 `DMS_AI_TOKEN` 或 `DMS_CLAW_TOKEN` 已配置且有效，DMS 服务可达（需内网/VPN）。可运行 `python3 scripts/common/precheck.py` 验证。

---

## Shell 执行规范（AI 编排必读）

> ⚠️ 以下规则是真实踩坑总结。AI 在 Layer 2 中调用 atomic 脚本时必须遵守，违反会导致脚本静默失败、产出物为空。

### 陷阱 1：后台进程（`&`）不继承未 export 的变量

```bash
# ❌ 错误：$S 在后台子进程里可能展开为空
S=/home/node/.openclaw/workspace/skills/mysql-monitor/scripts
python3 $S/atomic/explain_sql.py ... &

# ✅ 正确：export 确保后台子进程继承
export S=/home/node/.openclaw/workspace/skills/mysql-monitor/scripts
python3 $S/atomic/explain_sql.py ... &
```

### 陷阱 2：`&&` 链 + `&` 后台组合在非交互式 bash 里不稳定

```bash
# ❌ 危险：&&链中变量赋值不能保证传入后台子进程
export S=foo && python3 $S/script.py ... &

# ✅ 正确：赋值与后台启动分开写，export 单独一行
export S=/home/node/.openclaw/workspace/skills/mysql-monitor/scripts
export OUT=/home/node/.openclaw/workspace/skills/mysql-monitor/output/...
python3 $S/atomic/explain_sql.py ... &
PID1=$!
python3 $S/atomic/get_table_stats.py ... &
PID2=$!
wait $PID1 $PID2
```

### 陷阱 3：路径必须用硬编码绝对路径，不得依赖 cd + 相对路径

```bash
# ❌ 危险：后台进程继承的 cwd 不确定
cd /some/dir && python3 scripts/atomic/foo.py ... &

# ✅ 正确：始终硬编码绝对路径
python3 /home/node/.openclaw/workspace/skills/mysql-monitor/scripts/atomic/foo.py ... &
```

### 陷阱 4：后台任务要单独 wait 并检查退出码

```bash
# ❌ 错误：统一 wait 后才看输出，失败发现太晚
wait $P1 $P2 $P3
# 此时才发现 P2 失败，但 P3 已经跑完了

# ✅ 正确：每个任务 wait 后立即验收
wait $P1 || { echo "❌ explain_top1 失败，终止"; exit 1; }
wait $P2 || { echo "❌ table_stats 失败，终止"; exit 1; }
```

### 总结：AI 执行 atomic 脚本的黄金规则

| 规则 | 说明 |
|------|------|
| 所有路径变量必须 `export` | 保证后台子进程能继承 |
| 路径一律用硬编码绝对路径 | 避免 cwd 不确定导致路径解析失败 |
| 并发数 ≤ 3 时优先顺序执行 | 简单、可靠、易调试 |
| 并发时每个 `$PID` 单独 wait | 失败立刻发现，不要等所有任务跑完 |
| 每个 Step 完成后立即检查产出文件是否存在 | 对应验收条件，不跳过 |

---

## 参考资料

- 踩坑记录：`references/pitfalls.md`
- Layer 1 接口白名单：参见 `dms-readonly-api` skill
- 慢查询诊断历史案例：`references/pitfalls.md`

---

### 场景二：CPU 高诊断（路径 B）

> **数据采集与路径 A 完全一致**：Step 0 → Step 1 → Step 2（2a~2f） → Step 3 → Step 5 → Step 6。
> 其中 Step 2f **扩展组必采**。
> **区别在 Step 4 分析视角 + 报告 8 章节内容定义**。

---

#### Step 4 · 整合数据 & 分析（路径 B 专用）

> ⚠️ 路径 B 的分析核心是 **InnoDB 引擎状态 + 系统资源**，不是 SQL。
> 必须先完成下方 ①~⑤ 全部分析步骤，再写报告。

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
> 样式风格不变（深色 Banner + 卡片布局 + KPI 格子 + 表格 + 链式时间线）。

**Banner**：
- 标题：`<cluster> <分片> 根因分析报告`
- 副标题：一句话根因（如"Buffer Pool LRU Mutex 竞争引发 Page Cleaner 饥饿与级联崩溃"）
- Meta 标签：集群、主库 vm_name、IP:Port、故障窗口、数据粒度（xray 15s + mysqld.log）、MySQL 版本

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
3. **正反馈循环机制图**（ASCII 流程图，`<pre>` 块）
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
3. **Buffer Pool Cache Miss Rate**：read_requests/s + disk_reads/s + miss_rate%
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

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-cpu_high-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：CPU 高\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

### 场景三：主从延迟诊断（路径 C）

**Step 0** Precheck（同路径 A）

**Step 1** 获取连接器（含从库 vm_name）
```bash
python3 scripts/atomic/get_db_connectors.py --cluster <cluster>
```

**Step C1** 查复制状态
```bash
python3 scripts/atomic/get_slave_status.py \
    --cluster <cluster> --hostname <slave_vm_name> \
    --output <OUT_DIR> --run_id <RUN_ID>
```

验收：重点看 `_analysis`：
- `Slave_SQL_Running=No` 或 `Last_Error` 非空 → 复制链路断裂，输出报告，建议人工修复
- `Slave_SQL_Running=Yes` 但 `Seconds_Behind_Master` 大 → 疑似慢 SQL 堵塞回放 → 继续 Step 2~6（路径 A）

**Step C2**（可选）检查 Relay log 磁盘占用
```bash
python3 scripts/atomic/get_disk_usage.py \
    --cluster <cluster> --vm_name <slave_vm_name>
```
Relay log 异常大（几十 GB）→ 补充到报告磁盘风险章节


**Step C4** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step C5** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-replication_lag-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：主从延迟\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

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

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-disk_full-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：磁盘满\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

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

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-process_down-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：Crash\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

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

**Step B2-5** 输出 HTML 报告（连接堆积专项章节）
- 第 3 章根因：输出 subtype + 子路径判断依据 + 持锁 SQL / 热点分表
- 第 7 章建议：按 B2-AutoInc / B2-RowLock / B2-Leak 对应处置方案输出
- 附录：`get_system_lock_status._analysis` 完整数据


**Step B2-6** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step B2-7** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-conn_spike-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：连接堆积\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

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

**Step C2-2** 识别中断类型

| Last_Error 特征 | 中断类型 | 处置方向 |
|----------------|---------|---------|
| `Duplicate entry ... for key 'PRIMARY'` | 主键冲突 | 跳过该事务或同步主库数据 |
| `Table ... doesn't exist` | 表不存在 | 从库缺表，需同步 DDL |
| `Error 'Lock wait timeout'` | 锁超时 | 从库有长事务占锁，Kill 后重启 SQL Thread |
| GTID Gap / `Could not find first log` | GTID 断层 | 需重建从库或手动指定 GTID |
| `Connection refused` / IO Thread 失败 | 网络/权限问题 | 检查主库连接性和 replication 权限 |

**Step C2-3** 给出恢复建议（不执行任何操作，只给建议）
- 轻度（可跳过事务）：`SET GLOBAL SQL_SLAVE_SKIP_COUNTER=1; START SLAVE;`
- 重度（GTID 断层）：建议 DBA 重建从库或 `CHANGE MASTER TO MASTER_AUTO_POSITION=1`
- 网络问题：检查主库防火墙 / replication 账号密码

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

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-replication_lag-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：复制中断\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

### 场景八：机器带宽诊断（路径 F）

**触发条件**：用户说"带宽告警"/"网络告警"/"network_usage 超阈值"
**典型案例**：机器带宽告警 38 条（占 P0 告警 24.8%，第二高频），fls_fulfillment / fls_inventory 高发，多为 DTS 迁移节点批量触发

**Step F1** 查网络流量时序
```bash
python3 scripts/atomic/get_network_traffic.py \
    --cluster <cluster> \
    --start "<告警时间前30分钟>" --end "<告警时间后30分钟>" \
    --output <OUT_DIR> --run_id <RUN_ID>
```
解读 `_network_summary`：
- `pattern=sustained`：持续型 → 大概率 DTS 迁移
- `pattern=burst`：突发型 → 大概率业务大查询/大结果集
- `is_high=False`：流量已回落，告警可能已自愈

**Step F2** 识别流量来源（查 processlist）
```bash
python3 scripts/atomic/get_active_sessions.py --cluster <cluster>
```
重点看：
- 是否有大量 DTS binlog 拉取线程（Command=Binlog Dump）
- 是否有大结果集 SQL（Sending data + rows_sent 极大）

**Step F3** 判断处置策略

| 场景 | 判断依据 | 处置建议 |
|------|---------|---------|
| DTS 迁移期间（预期） | Binlog Dump 线程 + 时序与迁移任务吻合 | 评估是否超上限，可调 DTS 限速 |
| DTS 迁移（意外超限） | 流量超机器上限（通常 1~10 Gbps） | 暂停迁移任务，错峰执行 |
| 业务大查询 | Sending data + 慢查询时序吻合 | 转路径 A 分析 SQL 根因 |
| 未知 | 两种信号都有 | 向用户确认是否有计划内的 DTS 任务 |

**Step F4** 输出 HTML 报告（新增"机器带宽专项"章节）
- 流量时序图描述（峰值 / 均值 / 模式）
- DTS 任务识别结论
- 处置建议


**Step F5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step F6** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-net_bandwidth-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：机器带宽\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。

---

### 场景九：IOWait 诊断（路径 G）

**触发条件**：用户说"IOWait 高"/"io_wait 告警"，或路径 A/B 排查途中发现 IOWait 异常
**典型案例**：IOWait 异常告警 4 条（占 P0 告警 2.6%），fls_payment_user 集群连续触发

**Step G1** 查 IOWait 时序（监控指标）
从 Layer 1 监控面板查询 `iowait` / `io_util` 指标，确认：
- 告警窗口内 IOWait 峰值
- IOWait 高的节点（主库 vs 从库）
- 持续时间（短暂 vs 持续超 30 分钟）

**Step G2** 查 InnoDB 磁盘读写量
读取以下指标（可通过 get_active_sessions 或监控面板）：
- `Innodb_data_reads` / `Innodb_data_writes`（读写 IOPS）
- `Innodb_buffer_pool_pages_dirty`（脏页比例）
- `Innodb_os_log_written`（redo log 写入量）

**Step G3** 识别 IOWait 根因

| 指标特征 | 可能根因 | 处置方向 |
|---------|---------|---------|
| 读 IOPS 高 + Buffer Pool 命中率低 | 冷数据读放大（Buffer Pool Miss） | 扩大 innodb_buffer_pool_size |
| 写 IOPS 高 + 脏页比例高 | Checkpoint 风暴（刷脏页过快） | 调整 innodb_io_capacity / innodb_max_dirty_pages_pct |
| redo log 写入量激增 + 大事务 | 大批量写入 / 未拆分大事务 | 业务侧拆批，分批提交 |
| IOWait 高但 IOPS 正常 | 磁盘性能退化（物理故障） | 联系运维检查磁盘健康 |
| 从库 IOWait 高 + 复制延迟 | 从库 IO 跟不上 binlog 回放速度 | 调整并行复制参数，或升级从库磁盘 |

**Step G4** 给出建议，输出 HTML 报告（新增"IOWait 专项"章节）

**Step G5** 推送主报告 Webhook
```bash
python3 scripts/common/notify.py \
    --cluster    <cluster> \
    --time_range "<北京时间start> ~ <北京时间end>" \
    --cdn_url    <dms_url>   # 注：参数名沿用 cdn_url，实际传 DMS URL
```
验收：脚本输出包含 `✅ 推送成功`

**Step G6** 生成复盘报告并推送

> ⚠️ **强制步骤**：复盘报告由脚本自动生成，不得手写 HTML 或跳过。

```bash
# 1. 自动生成复盘报告
python3 scripts/common/generate_process_review.py \
    --out_dir <OUT_DIR> \
    --run_id  <RUN_ID>

# 2. 上传 DMS
python3 scripts/common/dms_upload.py <OUT_DIR>/report_process_review_<RUN_ID>.html \
    --file-name <cluster>-<yyyymmddHHMMSS>-unknown-process_review.html
# → 获得 review_dms_url

# 3. 记录 URL
python3 scripts/common/run_meta.py set \
    --out_dir <OUT_DIR> --key review_report_url --value "<review_dms_url>"

# 4. 推送
REVIEW_URL=<review_dms_url>
CLUSTER=<cluster>
TIME_RANGE="<北京时间start> ~ <北京时间end>"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"## 📋 MySQL 诊断复盘报告 · \`$CLUSTER\`\\n> **类型**：IOWait\\n> **诊断窗口**：$TIME_RANGE\\n> 📋 复盘报告 → [**点击查看诊断过程复盘**]($REVIEW_URL)\"} }" \
  "${DMS_WEBHOOK_URL:-https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40}"
```
验收：`generate_process_review.py` 输出 `✅ 复盘报告已生成`；curl 响应 `"code":0`；向用户同时回复主报告 URL 和复盘报告 URL。
**⚠️ 容错**：上传或推送失败时向用户说明，不影响主报告状态；生成失败需检查 `run_meta.json` 是否存在。
