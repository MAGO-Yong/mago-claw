# 优化计划 001 · Phase 0 问题类型分诊

**状态**：已完成  
**提出时间**：2026-03-26 21:00  
**提出人**：成烽  
**版本**：v1.2

---

## 背景与问题

原版 `mysql_cluster_analyze` Layer 2 流程没有问题类型判断，默认所有告警都是慢查询，直接进入"获取连接器 → 双路采集 → EXPLAIN"流程。

**实战暴露的问题：**
- 磁盘满/主从延迟/Crash 告警进来，AI 仍去采 CK 慢查询、跑 EXPLAIN → 完全无意义
- DTS Checksum 走完整 EXPLAIN 流程 → 浪费时间且结论错误
- Step 1 采集失败（db_name 错/原机慢日志为空）时，流程卡死，不知下一步该做什么
- **（v1.1 新增）** Phase 0 一次性线性决策，排查途中发现类型判断错误时无法修正
- **（v1.2 新增）** P0-2 依赖用户提供告警原文做关键字匹配，用户说不清楚时分诊失效

---

## 优化目标

1. 在 Step 0（Precheck）之前插入 **Phase 0 分诊**：在动手采数据之前，先确认问题类型，选对排查路径
2. **（v1.1 新增）** 引入**动态回溯机制**：排查途中若发现异常信号，能回到 Phase 0 重新分诊，不丢弃已有数据
3. **（v1.2 新增）** P0-2 改为 **AI 主动探测推理**：不依赖用户描述，AI 自己并发拉数据，推理类型后向用户确认

---

## 5 种问题类型定义

| 类型 | 关键字 / 触发特征 | 排查路径 |
|------|----------------|---------|
| 慢 SQL | 慢查询告警、SQL 响应慢、QPS 下跌 | 原有 Step 0~6 |
| CPU 高 | CPU 使用率告警、Load 高、线程堆积 | 活跃连接分析 + 慢 SQL |
| 主从延迟 | Seconds_Behind_Master 超阈值 | 复制状态 + Relay log + 慢 SQL 验证 |
| 磁盘满 | 磁盘使用率超阈值 | 磁盘空间分析（data/binlog/relaylog/slowlog）|
| Crash | mysqld 重启、实例不可用 | error log + 崩溃前慢查询/锁情况 |

---

## 完整流程

```
┌─────────────────────────────────────────────────────────┐
│                   Phase 0 · 问题类型分诊                  │
│             （所有 Step 之前，必须先完成）                  │
└─────────────────────────────────────────────────────────┘

P0-1 · 提取基本信息
  从用户输入提取（仅以下 3 项必须，告警类型不强求）：
  ① 集群名                    ← 必须
  ② 告警节点 vm_name          ← 可选，有则更精准
  ③ 告警时间                  ← 必须
  （告警原文/类型：用户能提供最好，提供不了 AI 主动探测）

P0-2 · AI 主动探测推理（v1.2 核心改动）
  不依赖用户描述，AI 并发执行 3 路轻量探测，约 5~10 秒出结果：

  探测 A · CK 慢查询计数
    get_slow_log_list --cluster XX
      --start 告警时间前1小时 --end 告警时间 --page_size 1
    → 有数据 → 有慢查询信号
    → 无数据 → 排除慢 SQL（或低于 CK 阈值）

  探测 B · 节点可达性验证
    get_db_connectors --cluster XX
    → 正常返回   → 节点存活
    → 空/报错    → 可能 Crash 或集群名有误

  探测 C · 磁盘用量快查
    get_disk_usage --cluster XX [--vm_name XX]
    → > 85%      → 有磁盘风险信号
    → API 不支持 → 降级，后续人工确认

  三路探测结果推理矩阵：
  ┌──────────┬──────────┬──────────┬─────────────────────────┐
  │ 探测A慢查 │ 探测B节点 │ 探测C磁盘 │ 推理类型                 │
  ├──────────┼──────────┼──────────┼─────────────────────────┤
  │ 有数据   │ 正常     │ 正常     │ 慢 SQL → 路径A            │
  │ 有数据   │ 正常     │ > 85%    │ 慢SQL + 磁盘风险 → A+D并行 │
  │ 无数据   │ 正常     │ > 85%    │ 磁盘满 → 路径D            │
  │ 无数据   │ 不可达   │ 任意     │ Crash → 路径E             │
  │ 无数据   │ 正常     │ 正常     │ 不确定 → 补充探测D         │
  └──────────┴──────────┴──────────┴─────────────────────────┘

  补充探测 D（仅当三路探测无法定性时）：
    get_slave_status --cluster XX --hostname XX
    → Seconds_Behind_Master > 0  → 主从延迟 → 路径C
    → Last_Error 非空            → 复制断裂 → 路径C
    → 均正常                     → 可能CPU高 → 路径B
                                   或告警已恢复，向用户说明

P0-3 · 向用户确认推理结论
  输出探测过程 + 推理结论（让用户看到依据，不是黑盒）：

  示例输出：
  ┌──────────────────────────────────────────┐
  │ 📊 Phase 0 探测结果                       │
  │  · 慢查询（CK）：1小时内 3058 条  ✅ 有信号│
  │  · 节点可达性：lusse11a-xxx 正常  ✅ 存活  │
  │  · 磁盘用量：9rb4f-3 节点 97.6%  ⚠️ 高风险│
  │                                          │
  │ 🔍 推理结论                               │
  │  主要问题：慢 SQL                         │
  │  附加风险：磁盘满（独立事件）              │
  │                                          │
  │ 📌 按慢SQL路径排查，同步关注磁盘风险       │
  │  确认继续？（或说"不对"让我重新判断）      │
  └──────────────────────────────────────────┘

  用户只需回复"对"/"继续"/"不对"，无需自己描述问题。
  用户说"不对" → 追问哪里不对 → 修正后重走 P0-2。

        ┌──────┬────────┬─────────┬──────┐
     慢SQL  CPU高  主从延迟  磁盘满  Crash
        │      │        │         │      │
        ▼      ▼        ▼         ▼      ▼
    路径A   路径B    路径C     路径D  路径E
```

---

### 路径 A · 慢 SQL（原有 Step 0~6，不变）

```
Step 0  Precheck（cdn-upload 工具检查）
Step 1  获取连接器（get_db_connectors）
Step 2  双路采集慢查询
          2a CK 聚合慢日志（get_slow_log_list）
          2b 原机原始慢日志（get_raw_slow_log）
          2c 识别 TOP3 业务慢 SQL
Step 3  并发 EXPLAIN + 表/索引统计
Step 4  整合分析
Step 5  生成 HTML 报告 + CDN 上传
Step 6  Webhook 推送
```

---

### 路径 B · CPU 高

```
Step 0  Precheck
Step 1  获取连接器（get_db_connectors）
Step B1 查活跃连接 & 线程堆积（get_active_sessions）
          重点：State 分布（Waiting for.../Locked/Sending data）
          重点：是否有大量长时间运行的 SQL
Step B2 判断分叉：
          └ 发现大量慢 SQL / 长事务 → 继续 Step 2~6（慢 SQL 路径）
          └ 发现大量锁等待           → 记录持锁者，继续 Step 2~6
          └ 无明显慢 SQL             → 输出活跃连接分析报告，标注"未发现慢 SQL 根因"
```

---

### 路径 C · 主从延迟

```
Step 0  Precheck
Step 1  获取连接器（get_db_connectors）
Step C1 查复制状态（get_slave_status / SHOW SLAVE STATUS）
          重点：Seconds_Behind_Master 峰值
          重点：Slave_SQL_Running / Slave_IO_Running 是否正常
          重点：Last_Error 是否为空
          重点：Relay_Log_Space 是否持续增长
Step C2 判断分叉：
          └ Last_Error 非空 / Slave_SQL_Running=No
                → 复制链路断裂，输出报告，建议人工介入修复复制
          └ Last_Error 为空 / Slave_SQL_Running=Yes 但延迟大
                → 疑似慢 SQL 堵塞回放，继续 Step 2~6（慢 SQL 路径）
Step C3 （可选）检查 Relay log 大小（get_disk_usage）
          └ Relay log 异常大 → 补充到报告磁盘风险章节
```

---

### 路径 D · 磁盘满

```
Step 0  Precheck
Step D1 查磁盘用量（get_disk_usage）
          └ DMS API 支持 → 直接返回各节点磁盘详情
          └ DMS API 不支持 → 输出人工排查指引（SSH 命令 + DMS 控制台路径）
Step D2 按磁盘大头分类：
          ┌ data 文件大    → 数据归档 / 扩容 / 增加分片
          ├ binlog 大      → 缩短 expire_logs_days / 清理旧 binlog
          ├ relay log 大   → 检查复制状态（转 路径C Step C1）
          └ slow log 大    → 清理或轮转 slow.log
Step D3 识别数据倾斜（多节点对比，是否某分片独高）
Step D4 输出 HTML 报告（磁盘专项报告）
```

---

### 路径 E · Crash

```
Step 0  Precheck
Step E1 确认节点状态（通过 get_db_connectors 验证节点是否可达）
          └ 节点不可达 → 标记为 Crash，输出"建议联系 DBA 人工登录确认"
          └ 节点可达   → 可能是已重启恢复，继续 Step E2
Step E2 查崩溃前慢查询（CK 聚合，时间范围扩展到崩溃前 1 小时）
          └ get_slow_log_list，时间窗口：崩溃时间前推 1 小时
Step E3 输出 HTML 报告（Crash 专项报告）
          重点章节：崩溃时间 / 崩溃前 TOP SQL / 建议查 error log
          注明：error log 需人工 SSH 查看（/data/mysql/error.log）
```

---

## 动态回溯机制（v1.1 新增）

**核心原则：排查途中若发现以下异常信号，立即暂停当前路径，带着已有数据重走 P0-2，修正类型判断。**

### 触发重新分诊的信号

| 信号 | 出现在哪步 | 可能的真实类型 |
|------|-----------|--------------|
| CK 慢查询 + 原机慢日志**双路均为 0** | Step 2 | 非慢 SQL（磁盘满/Crash/主从延迟）|
| `file_size_mb = 0.0`（slow.log 是空文件） | Step 2b | slow_query_log=OFF 或节点 Crash |
| `get_db_connectors` 返回 Invalid param | Step 1 | 集群名/db 有误，需重新确认基本信息 |
| 活跃连接中大量 `Waiting for relay log` | 路径B Step B1 | 主从延迟堵塞，切换到路径 C |
| `Slave_SQL_Running=No` 或 `Last_Error` 非空 | 路径C Step C1 | 复制链路断裂，非慢 SQL 引起的延迟 |
| 节点完全不可达 | 任意 Step 1 | Crash |
| 磁盘用量 > 95% | 路径D Step D1 | 补充磁盘 P0 风险到报告（可与其他类型并存）|

### 回溯流程

```
发现异常信号
    ↓
暂停当前路径（保留已采集数据，不丢弃）
    ↓
向用户说明："在 Step XX 发现异常信号【XX】，原判断【XX 类型】可能有误"
    ↓
带着已有数据重走 P0-2（重新匹配类型）
    ↓
输出修正后的类型和路径
    ↓
用户确认后，从新路径的第一个 Step 继续
（已采集的有效数据直接复用，不重复采集）
```

---

## 改动范围

| 文件 | 改动类型 | 内容 |
|------|---------|------|
| `SKILL.md` | 修改 | Layer 2 开头插入 Phase 0 + 动态回溯机制，新增路径 B/C/D/E |
| `scripts/atomic/get_disk_usage.py` | 新增 | 磁盘查询（复用 mysql-cluster-analyze-001 已有版本）|
| `scripts/atomic/get_slave_status.py` | 新增 | Slave 复制状态查询 |
| `scripts/atomic/get_active_sessions.py` | 新增 | 活跃连接/线程堆积查询 |
| `references/pitfalls.md` | 修改 | 补充"问题类型识别失误"和"动态回溯触发场景"踩坑记录 |

## 不改的东西

- Step 1~6 原有慢查询诊断流程**完全不动**
- 原有 7 个 atomic 脚本**不修改**，只新增
- HTML 报告 8 章节规范**不变**

---

## 执行 Checklist（待执行）

- [x] 1. 修改 `SKILL.md`：Layer 2 开头插入 Phase 0 + 动态回溯机制，补充路径 B/C/D/E
- [x] 2. 新增 `get_disk_usage.py`（复用 mysql-cluster-analyze-001 已有版本）
- [x] 3. 新增 `get_slave_status.py`
- [x] 4. 新增 `get_active_sessions.py`
- [x] 5. 更新 `references/pitfalls.md`（新增坑7、坑8）
- [x] 6. 验证：Phase 0/路径选择/动态回溯/5条路径/3个新脚本全部确认存在

---

## 变更历史

| 版本 | 时间 | 内容 |
|------|------|------|
| v1.0 | 2026-03-26 21:00 | 初稿，成烽提出，Phase 0 分诊 + 5 种类型 |
| v1.1 | 2026-03-26 21:06 | 新增动态回溯机制，补充触发信号表和回溯流程 |
| v1.2 | 2026-03-26 21:11 | P0-2 改为 AI 主动探测推理，不依赖用户描述；新增 3 路并发探测 + 推理矩阵 + 补充探测 D；P0-3 输出可视化探测结果供用户确认 |
