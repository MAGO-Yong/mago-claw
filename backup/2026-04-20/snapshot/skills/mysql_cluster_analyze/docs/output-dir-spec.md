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
