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

> ⚠️ **【必读，最高优先级】** 进入任何 Layer 2 诊断路径前，必须先执行：
> `read docs/path-X.md`（X 对应当前路径字母，如 F → `docs/path-F.md`）
> **不得凭记忆或摘要推进，不得跳步骤。违反 = 本次诊断无效。**

> ⚠️ **报告生成全局规则**：主报告和复盘报告均由 AI 直接 `write` 生成，不得调用脚本代替；即使已有相同集群历史报告，本次仍必须重新生成；不得跳过任何报告生成步骤。
>
> ⚠️ **风控前置（所有路径强制）**：生成任何路径 HTML 前，必须逐条核查 [`docs/report-risk-rules.md`](docs/report-risk-rules.md) 输出禁止项，确认无违规后才能执行 `write`。
>
> ⚠️ **Banner "Powered By" 全局规范**（所有路径、所有报告类型统一执行）：
> Banner 右侧必须渲染纯文本 "Powered By 关系型数据库 AI 诊断助手"，不得添加任何超链接或跳转引导。
>
> ⚠️ **复盘报告专项约定（2026-04-10）**：
> - 复盘报告由 AI 直接生成 HTML，结构规范见 `docs/process-review-spec.md`（7 章节）
> - 生成后调 `publish_report.py` 上传发布（upload + run_meta + webhook）
> - **`generate_process_review.py` 已废弃，禁止调用**——该脚本只能读 run_meta 元字段，无法获取完整诊断上下文，输出必然简陋
> - 各路径 SOP 文档（path-*.md）中的 `generate_process_review.py` 调用示例已标记为废弃，执行时忽略，改用 AI 生成


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

> ⚠️ **端点说明（禁止修改）**：`open-claw/auth/*` 匿名可用，无需调用方 DMS Session，能正常返回 `authorize_url`。
> `ai-api/v1/auth/*` 需要调用方有 DMS Session，匿名调用返回「无登录信息」，**禁止用于 generate-session / get-token**。

```bash
curl -s -X POST \
  "https://dms.devops.xiaohongshu.com/dms-api/open-claw/auth/generate-session" \
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
curl -s "https://dms.devops.xiaohongshu.com/dms-api/open-claw/auth/get-token?session_id=<session_id>"
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
  "https://dms.devops.xiaohongshu.com/dms-api/open-claw/auth/generate-session" \
  | python3 -m json.tool
# Step 2：用户在浏览器中访问 authorize_url 完成授权
# Step 3：获取 token（返回字段为 dms_ai_token，同一流程）
curl -s "https://dms.devops.xiaohongshu.com/dms-api/open-claw/auth/get-token?session_id=<session_id>"
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
| "查 XX 节点连接数时序（点查）" | Layer 1 | `scripts/atomic/get_connection_timeline.py` ⚠️ 只有 `--output-json`，无 `--output/--run_id` |
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

> ⚠️ **myhub 集群注意**：`get-db-connectors` 接口对 myhub 集群返回 400，脚本会自动 fallback 到
> `/mysql/base/instance/get-by-cluster`，返回全量节点（含全部分片）。
> **禁止手动改用 `white-screen-instance-list/get-by-cluster`**，该接口仅返回白屏展示用的部分分片，会漏掉跨机房节点（历史案例：ads_ad_core 漏掉全部 lshn 节点）。

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

## 计划生成 + 评审循环 SOP

> 适用于：生成任何诊断执行计划、路径迁移计划、报告改进计划等多步骤技术计划时。

### 评审循环流程

1. **生成计划**：起草执行计划 JSON，包含 tasks / execution_order / success_criteria / risks
2. **发给评审助手**：通过 `sessions_list` 实时查询 `label=运维skill评审助手` 获取 session key（不硬编码），调用 `sessions_send` 发送，消息头部附带格式要求：
   ```
   请用新的输出格式评审以下计划（输出格式：{ confidence_score: int, structural_issues: [{target, desc}], suggestions: [{target, desc, impact}] }）：
   ```
3. **检查终止条件**：`confidence_score >= 90 AND structural_issues == 0 AND suggestions[impact=high|medium] == 0`
4. **未终止**：吸收 `review_patches`，自行修订计划，重新发送（不把 blocking 甩给成烽，除非确实无法自行判断）
5. **终止**：展示最终计划 + 每轮评审摘要（轮次 / 分数 / 主要修订点）给成烽
6. **等成烽说「执行」才动手**

### 评审助手 session key 查询方式

```python
# 每次运行时实时查询，不依赖硬编码 key
sessions_list(label="运维skill评审助手")
# 取返回结果中的 sessionKey
```

> ⚠️ session key 形如 `agent:main:draft:xxxx`，会随助手重建而变化，必须实时查询。

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

**P0-0 · 写入诊断开始时间（三路探测前必须执行）**

在三路探测开始前，立即执行以下命令记录 `start_time`，供后续路径脚本统计 token 消耗窗口：

```bash
python3 scripts/common/run_meta.py set \
  --out_dir output/<RUN_ID> \
  --key start_time \
  --value $(python3 -c "import time; print(time.time())")
```

> ⚠️ 此步骤必须在 Phase 0 三路探测**之前**执行，否则 token 统计窗口过短，报告中 Token 消耗将显示 0。

---

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

> ⚠️ **完整 SOP 见 [`docs/path-A.md`](docs/path-A.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

#### HTML 报告规范（8 章节，固定结构）

> 完整规范见 [`docs/report-spec.md`](docs/report-spec.md)。风控红线见 [`docs/report-risk-rules.md`](docs/report-risk-rules.md)。

## 输出目录结构

> 完整规范见 [`docs/output-dir-spec.md`](docs/output-dir-spec.md)。

### 场景二：CPU 高诊断（路径 B）

> ⚠️ **完整 SOP 见 [`docs/path-B.md`](docs/path-B.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景三：主从延迟诊断（路径 C1）

> ⚠️ **完整 SOP 见 [`docs/path-C1.md`](docs/path-C1.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景四：磁盘满诊断（路径 D）

> ⚠️ **完整 SOP 见 [`docs/path-D.md`](docs/path-D.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景五：Crash 诊断（路径 E）

> ⚠️ **完整 SOP 见 [`docs/path-E.md`](docs/path-E.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景六：连接堆积诊断（路径 B2）

> ⚠️ **完整 SOP 见 [`docs/path-B2.md`](docs/path-B2.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景七：复制中断诊断（路径 C2）

> ⚠️ **完整 SOP 见 [`docs/path-C2.md`](docs/path-C2.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

### 场景八：机器带宽诊断（路径 F）

> ⚠️ **完整 SOP 见 [`docs/path-F.md`](docs/path-F.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**


### 场景九：IOWait 诊断（路径 G）

> ⚠️ **完整 SOP 见 [`docs/path-G.md`](docs/path-G.md)，执行前必须用 `read` 工具读取该文件，不得凭记忆推进。**

---

> 🧪 **测试规范见 [`docs/testing-guide.md`](docs/testing-guide.md)**，执行可用性测试前必须确认测试集群合规。

> 📋 **复盘报告风格锚点**：生成复盘报告前必须 `read docs/examples/process-review-example.html`，参照其 CSS 和整体结构（§1~§7），**不复用示例中的业务数据**，§2 Phase 流程按本次实际诊断过程还原。

