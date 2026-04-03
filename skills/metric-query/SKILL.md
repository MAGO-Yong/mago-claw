---
name: metric-query
description:
  统一指标数据查询，支持三种查询模式：1)
  系统/中间件模板指标查询（CPU、内存、JVM、RPC、Redis、MySQL、MQ、HTTP、线程池、Sentinel 等）；2)
  PromQL(PQL) 自定义查询；3) Cat 指标查询（transaction/event/problem 的
  QPS、耗时、成功率等）。根据数据量智能返回原始数据或特征数据。当用户想要查询服务的系统指标、中间件指标、JVM
  信息、Cat 指标（transaction/event/problem）、或执行 PQL/PromQL 查询时使用此 skill。
---

# 统一指标数据查询 Metric Query

这个 skill 是统一的指标数据查询入口，支持三种查询模式，覆盖所有常见的指标查询场景。

## 工作流程

### Step 1: 判断查询模式

根据用户输入判断使用哪种查询模式，**按以下优先级**：

1. **pql 模式** — 用户提供了 PromQL / PQL 表达式 → `--mode pql`
2. **cat 模式**
   — 用户明确提到 cat、transaction、event、problem 关键词，或想查询特定接口（type/name 维度）的 QPS/耗时/成功率 →
   `--mode cat`
3. **system 模式**（默认） — 用户提到具体的指标名称（CPU、内存、JVM、RPC、Redis 等） →
   `--mode system`

> **歧义处理**：当用户说「RPC 耗时」「Redis
> QPS」等不带 Cat 特征的表述时，优先走 system 模式。仅当用户明确使用 Cat / transaction / event /
> problem 等词时才走 cat 模式。

---

### Step 2: 收集参数

**从用户问题中尽可能提取参数，只主动询问缺失的必需参数。**

#### 公共参数

| 参数      | 必需   | 说明                                 |
| --------- | ------ | ------------------------------------ |
| `--start` | 是     | 开始时间，格式 `yyyy-MM-dd HH:mm:ss` |
| `--end`   | 是     | 结束时间，格式 `yyyy-MM-dd HH:mm:ss` |
| `--app`   | 视模式 | 服务名，system/cat 必填，pql 可选    |

#### system 模式参数

| 参数             | 必需 | 说明                                                                                                 |
| ---------------- | ---- | ---------------------------------------------------------------------------------------------------- |
| `--metric-names` | 是   | 指标名称，逗号分隔。参考「指标映射表」章节                                                           |
| `--view`         | 否   | 查询视角：`cluster`（默认，表示服务、集群视角）/ `zone`（机房、可用区） / `container`（单机、单pod） |
| `--group-bys`    | 否   | 分组维度，逗号分隔                                                                                   |

#### pql 模式参数

| 参数           | 必需 | 说明                                   |
| -------------- | ---- | -------------------------------------- |
| `--pql`        | 是   | PromQL 表达式                          |
| `--app`        | 否   | 辅助数据源解析，当无 datasource 时使用 |
| `--datasource` | 否   | VMS 数据源名称，优先级最高             |

> 数据源三级降级：`datasource` > `app` > PQL 中解析 metric name

#### cat 模式参数

| 参数       | 必需 | 说明                                                                                                 |
| ---------- | ---- | ---------------------------------------------------------------------------------------------------- |
| `--theme`  | 否   | 主题：`transaction`（默认）/ `event` / `problem`                                                     |
| `--metric` | 否   | 指标：`qps`（默认）/ `avg` / `tp99` / `tp95` / `tp90` / `count` / `fail_percent` / `success_percent` |
| `--type`   | 否   | Cat 类型，单选：`Call` / `Service` / `Http` / `URL` 等                                               |
| `--types`  | 否   | Cat 类型，多选（逗号分隔），与 `--type` 互斥。默认 `Service,Http`                                    |
| `--names`  | 否   | 接口名称，逗号分隔。默认 `All`                                                                       |
| `--zones`  | 否   | 机房列表，逗号分隔。默认 `All`                                                                       |
| `--ips`    | 否   | IP 列表，逗号分隔。默认 `All`                                                                        |
| `--step`   | 否   | 步长（秒），默认 60                                                                                  |

---

### Step 3: 调用 API

```bash
# system 模式 — 查询模板指标
python {SKILL_DIR}/scripts/query.py --mode system \
  --app "creator-service-default" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --metric-names "cpu.usage,mem.usage"

# pql 模式 — 执行 PromQL
python {SKILL_DIR}/scripts/query.py --mode pql \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --pql 'sum(rate(rpc_server_requests_total{app="creator-service-default"}[5m]))'

# cat 模式 — 查询 Cat 指标
python {SKILL_DIR}/scripts/query.py --mode cat \
  --app "creator-service-default" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --theme transaction --metric qps --type Call
```

---

### Step 4: 灵活呈现结果

**根据用户问题灵活调整输出**：

- **「CPU 使用率是多少？」** → 只回答平均值和当前值
- **「CPU 趋势如何？」** → 描述趋势（上升/下降/平稳）和关键数据点
- **「系统全面检查」** → 展示多个指标的摘要信息
- **「transaction QPS 多少？」** → Cat 模式结果概要

**输出要点**：

- 当前值、平均值、最大值、最小值
- 趋势描述
- 异常点识别
- 根据问题决定详细程度

---

## 指标映射表（system 模式）

使用 system 模式时，需要将用户的自然语言描述映射为 `--metric-names` 的值。

### 分组模板

当用户说「查看 XXX 类指标」时，自动展开为对应的指标列表：

**SYSTEM**（系统基础）:
`cpu.usage, mem.usage, mem.used, network.in.io, network.out.io, disk.write.io, disk.read.io`

**JVM**:
`jvm.young.gc.count, jvm.young.gc.duration, jvm.old.gc.count, jvm.old.gc.duration, jvm.eden.space.used, jvm.survivor.space.used, jvm.old.space.used, jvm.metaspace.used, jvm.live.threads`

**THREAD**（线程池）:
`executor.threads.usage, executor.threads.count.max, executor.queued.task.count, executor.execution.duration`

**RPC**:
`rpc.client.request.qps, rpc.client.request.success, rpc.client.request.duration.avg, rpc.server.request.qps, rpc.server.request.success, rpc.server.request.duration.avg`

**HTTP**:
`http.client.request.qps, http.client.request.success, http.client.request.duration.avg, http.server.request.qps, http.server.request.success, http.server.request.duration.avg`

**MYSQL**: `mysql.request.qps, mysql.request.success, mysql.request.duration.avg`

**REDIS**:
`redis.jedis.request.qps, redis.jedis.request.success, redis.jedis.request.duration.avg, redis.jedis.connection.wait`

**MQ**（RocketMQ）:
`rocketmq.producer.qps, rocketmq.producer.success, rocketmq.producer.duration.avg, rocketmq.consumer.qps, rocketmq.consumer.success, rocketmq.consumer.duration.avg`

**SENTINEL**: `sentinel.request.qps, sentinel.block.qps, sentinel.fail.qps`

**SCHEDULE**:
`xschedule.trigger.qps, xschedule.trigger.duration, xschedule.trigger.error, redschedule.task.processing.total`

---

### 完整指标列表

#### 1. 系统监控 (SYSTEM)

**CPU**:

- `cpu.usage` — CPU 使用率
- `cpu.cfs.periods.total` — 每秒执行的 CPU 时间周期数
- `cpu.cfs.throttled.periods.total` — 每分钟容器被限制的 CPU 时间周期数

**内存**:

- `mem.usage` — 内存使用率
- `mem.used` — 已使用内存
- `mem.total` — 总内存
- `mem.cache` — 内存中的 cache 用量
- `mem.swap` — 交换分区用量
- `mem.working.set` — 当前内存工作集使用量
- `mem.max.usage.bytes` — 最大内存使用量的记录
- `mem.failcnt` — 每分钟申请内存失败次数
- `mem.failures.total` — 每分钟累计内存申请错误次数
- `mem.mapped.file` — 内存映射文件使用内存量

**网络**:

- `network.in.io` — 网络入流量
- `network.out.io` — 网络出流量

**磁盘/IO**:

- `disk.write.io` — 磁盘写 I/O
- `disk.read.io` — 磁盘读 I/O
- `fs.write.seconds.total` — 每分钟 I/O 写操作花费的时间

**日志**:

- `logback.error.count` — 错误日志数量

#### 2. JVM

**GC**:

- `jvm.young.gc.count` — JVM Young GC 次数
- `jvm.young.gc.duration` — JVM Young GC 耗时
- `jvm.old.gc.count` — JVM Old GC 次数
- `jvm.old.gc.duration` — JVM Old GC 耗时

**内存区域**:

- `jvm.eden.space.used` — JVM Eden 区使用内存
- `jvm.survivor.space.used` — JVM Survivor 区使用内存
- `jvm.old.space.used` — JVM Old 区使用内存
- `jvm.metaspace.used` — JVM Metaspace 使用内存

**线程**:

- `jvm.live.threads` — JVM Live 线程总数

#### 3. 线程池 (THREAD)

- `executor.threads.usage` — 线程池利用率
- `executor.threads.count.max` — 线程池最大线程数
- `executor.queued.task.count` — 线程池排队数
- `executor.execution.duration` — 线程池任务处理耗时

#### 4. RPC

**客户端**:

- `rpc.client.request.success` — RPC 客户端请求成功率
- `rpc.client.request.qps` — RPC 客户端请求 QPS
- `rpc.client.request.duration.avg` — RPC 客户端请求平均耗时
- `rpc.client.request.duration.tp95` — RPC 客户端请求耗时 TP95
- `rpc.client.request.duration.tp99` — RPC 客户端请求耗时 TP99
- `rpc.client.request.duration.tp999` — RPC 客户端请求耗时 TP999

**服务端**:

- `rpc.server.request.success` — RPC 服务端请求成功率
- `rpc.server.request.qps` — RPC 服务端请求 QPS
- `rpc.server.request.duration.avg` — RPC 服务端请求平均耗时
- `rpc.server.request.duration.tp95` — RPC 服务端请求耗时 TP95
- `rpc.server.request.duration.tp99` — RPC 服务端请求耗时 TP99
- `rpc.server.request.duration.tp999` — RPC 服务端请求耗时 TP999

**C++ RPC**:

- `cpp.rpc.client.request.time.TP<999` — RPC 客户端耗时 TP<999
- `cpp.rpc.client.request.time.TP9999` — RPC 客户端耗时 TP9999
- `cpp.rpc.server.request.time.TP<999` — RPC 服务端耗时 TP<999
- `cpp.rpc.server.request.time.TP9999` — RPC 服务端耗时 TP9999

#### 5. HTTP

**客户端**:

- `http.client.request.qps` — HTTP 客户端请求 QPS
- `http.client.request.success` — HTTP 客户端请求成功率
- `http.client.request.duration.avg` — HTTP 客户端请求平均耗时
- `http.client.request.duration.tp95` — HTTP 客户端请求耗时 TP95
- `http.client.request.duration.tp99` — HTTP 客户端请求耗时 TP99

**服务端**:

- `http.server.request.success` — HTTP 服务端请求成功率
- `http.server.request.qps` — HTTP 服务端请求 QPS
- `http.server.request.duration.avg` — HTTP 服务端请求平均耗时
- `http.server.request.duration.tp95` — HTTP 服务端请求耗时 TP95
- `http.server.request.duration.tp99` — HTTP 服务端请求耗时 TP99

#### 6. MySQL

- `mysql.request.success` — MySQL 请求成功率
- `mysql.request.qps` — MySQL 请求 QPS
- `mysql.request.duration.avg` — MySQL 请求平均耗时
- `mysql.request.duration.tp95` — MySQL 请求耗时 TP95
- `mysql.request.duration.tp99` — MySQL 请求耗时 TP99

#### 7. Redis

**Jedis**:

- `redis.jedis.request.success` — Redis(Jedis) 请求成功率
- `redis.jedis.request.qps` — Redis(Jedis) 请求 QPS
- `redis.jedis.request.duration.avg` — Redis(Jedis) 请求平均耗时
- `redis.jedis.request.duration.tp95` — Redis(Jedis) 请求耗时 TP95
- `redis.jedis.request.duration.tp99` — Redis(Jedis) 请求耗时 TP99
- `redis.jedis.connection.wait` — Redis(Jedis) 连接池排队数
- `redis.jedis.connection.duration.avg` — Redis(Jedis) 获取连接耗时

**Lettuce**:

- `lettuce.ops.count` — Redis 请求 QPS (Lettuce)
- `lettuce.conn.count` — Redis 建联 (Lettuce)
- `lettuce.failover.down` — Redis 实例摘除 (Lettuce)
- `lettuce.failover.recovered` — Redis 实例恢复 (Lettuce)
- `lettuce.ops` — Redis 请求耗时 (Lettuce)
- `lettuce.timeout` — Redis 生效的 soTimeout 配置 (Lettuce)
- `redis.lettuce.request.success` — Redis 请求成功率 (Lettuce)

**通用**:

- `infra_redis_hit_total` — Redis 命中率

#### 8. MQ (RocketMQ)

**生产者**:

- `rocketmq.producer.qps` — RocketMQ 生产者 QPS
- `rocketmq.producer.success` — RocketMQ 生产成功率
- `rocketmq.producer.duration.avg` — RocketMQ 生产平均耗时
- `rocketmq.producer.duration.tp95` — RocketMQ 生产耗时 TP95
- `rocketmq.producer.duration.tp99` — RocketMQ 生产耗时 TP99

**消费者**:

- `rocketmq.consumer.qps` — RocketMQ 消费者 QPS
- `rocketmq.consumer.success` — RocketMQ 消费成功率
- `rocketmq.consumer.duration.avg` — RocketMQ 消费平均耗时
- `rocketmq.consumer.duration.tp95` — RocketMQ 消费耗时 TP95
- `rocketmq.consumer.duration.tp99` — RocketMQ 消费耗时 TP99

#### 9. Sentinel

**基础限流**:

- `sentinel.request.qps` — Sentinel 请求 QPS
- `sentinel.block.qps` — Sentinel Block QPS
- `sentinel.fail.qps` — Sentinel Fail QPS

**动态限流 (dynamicLimiter)**:

- `sentinel.dynamicLimiter.request.qps` — 总请求 QPS
- `sentinel.dynamicLimiter.block.qps` — 触发 Block QPS
- `sentinel.dynamicLimiter.fail.qps` — Fail QPS
- `sentinel.dynamicLimiter.success.qps` — Success QPS
- `sentinel.dynamic.qps` — 阈值 QPS
- `sentinel.rate.dynamicLimiter.block.qps` — Block 高流量 QPS

**熔断 (circuitBreaker)**:

- `sentinel.circuitBreaker.request.qps` — 总请求 QPS
- `sentinel.circuitBreaker.block.qps` — 触发 Block QPS
- `sentinel.circuitBreaker.fail.qps` — Fail QPS
- `sentinel.circuitBreaker.success.qps` — Success QPS
- `sentinel.rate.circuitBreaker.block.qps` — 触发熔断 QPS

**超时/其他**:

- `red.rpc.cds.timeout` — 服务治理动态超时配置
- `triggered.timeout.qps` — 触发超时 QPS
- `distributed_rate_limiter_waterLevel` — 集群限流水位

#### 10. Schedule (RedSchedule)

- `xschedule.trigger.qps` — 单 Job 执行 QPS
- `xschedule.trigger.duration` — 单任务执行耗时(ms)
- `xschedule.trigger.error` — 单任务执行失败
- `redschedule.task.processing.total` — 运行中的 Job

---

## Cat 指标说明（cat 模式）

Cat 指标用于查询应用的 Transaction / Event / Problem 维度的时序数据。

### theme（主题）

| 值            | 说明                                               |
| ------------- | -------------------------------------------------- |
| `transaction` | 调用链指标（默认），如接口调用的 QPS、耗时、成功率 |
| `event`       | 事件指标                                           |
| `problem`     | 异常/问题指标                                      |

### metric（指标类型）

| 值                | 说明               |
| ----------------- | ------------------ |
| `qps`             | 每秒请求数（默认） |
| `avg`             | 平均耗时(ms)       |
| `tp50`            | 耗时 TP50          |
| `tp90`            | 耗时 TP90          |
| `tp95`            | 耗时 TP95          |
| `tp99`            | 耗时 TP99          |
| `tp999`           | 耗时 TP999         |
| `count`           | 总数               |
| `fail_percent`    | 失败率(%)          |
| `success_percent` | 成功率(%)          |

### type / types（Cat 类型）

`--type`（单选）和 `--types`（多选）互斥，常用值：

| 值        | 说明                   |
| --------- | ---------------------- |
| `Call`    | 下游调用（RPC 客户端） |
| `Service` | 服务端处理             |
| `Http`    | HTTP 请求              |
| `URL`     | URL 请求               |

如果用户未指定，默认使用 `--types "Service,Http"`。

### 常见用法示例

```bash
# 查看 transaction 的 QPS（默认 Service+Http 类型）
--mode cat --app xxx --theme transaction --metric qps

# 查看 Call 类型的平均耗时
--mode cat --app xxx --metric avg --type Call

# 查看特定接口的 TP99
--mode cat --app xxx --metric tp99 --type Service --names "UserService.getUser"

# 查看 event 的数量
--mode cat --app xxx --theme event --metric count
```

---

## PQL 查询说明（pql 模式）

直接执行 PromQL 表达式查询 VMS 数据。

### 数据源解析优先级

1. `--datasource` — 直接指定 VMS 数据源名称
2. `--app` — 通过服务名反查数据源
3. 自动从 PQL 表达式中解析 metric name 来查找数据源

### 常见用法示例

```bash
# 提供 app 辅助数据源解析
--mode pql --app "creator-service-default" \
  --pql 'sum(rate(rpc_server_requests_total[5m]))'

# 直接指定数据源
--mode pql --datasource "vms-prod" \
  --pql 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))'

# 不提供 app 和 datasource，自动从 PQL 解析
--mode pql --pql 'node_cpu_seconds_total{mode="idle"}'
```

---

## 使用场景示例

### 场景 1：查看服务 CPU 和内存

用户：「看一下 creator-service-default 最近一小时的 CPU 和内存」

```bash
python {SKILL_DIR}/scripts/query.py --mode system \
  --app "creator-service-default" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --metric-names "cpu.usage,mem.usage"
```

### 场景 2：JVM 全面检查

用户：「检查一下 xxx 服务的 JVM 状况」

```bash
python {SKILL_DIR}/scripts/query.py --mode system \
  --app "xxx-service" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --metric-names "jvm.young.gc.count,jvm.young.gc.duration,jvm.old.gc.count,jvm.old.gc.duration,jvm.eden.space.used,jvm.old.space.used,jvm.metaspace.used,jvm.live.threads"
```

### 场景 3：查看 Cat Transaction QPS

用户：「看一下 creator-service-default 的 transaction QPS」

```bash
python {SKILL_DIR}/scripts/query.py --mode cat \
  --app "creator-service-default" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --theme transaction --metric qps
```

### 场景 4：查看特定接口的 TP99

用户：「creator-service-default 的 Call 类型接口 TP99 是多少」

```bash
python {SKILL_DIR}/scripts/query.py --mode cat \
  --app "creator-service-default" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --metric tp99 --type Call
```

### 场景 5：执行自定义 PQL

用户：「帮我查一下这个 PQL：sum(rate(rpc_server_requests_total{app="xxx"}[5m]))」

```bash
python {SKILL_DIR}/scripts/query.py --mode pql \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --pql 'sum(rate(rpc_server_requests_total{app="xxx"}[5m]))'
```

### 场景 6：RPC + MySQL + Redis 综合排查

用户：「全面看一下 xxx 服务的中间件指标」

```bash
python {SKILL_DIR}/scripts/query.py --mode system \
  --app "xxx-service" \
  --start "2025-05-30 10:00:00" --end "2025-05-30 11:00:00" \
  --metric-names "rpc.server.request.qps,rpc.server.request.success,rpc.server.request.duration.avg,mysql.request.qps,mysql.request.success,mysql.request.duration.avg,redis.jedis.request.qps,redis.jedis.request.success,redis.jedis.request.duration.avg"
```
