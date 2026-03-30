---
name: metrics-query-by-template
description: Prometheus系统/中间件指标数据查询，通过指标名称查询固定模板的指标（例如CPU、JVM、RPC等），结果根据数据量智能返回原始数据或特征数据。如果指标的维度数量超过10个，为了控制响应大小，只返回整体特征而不分时间段。适用于分析指标的时间趋势、发现异常时间段、了解指标的整体分布特征。。当用户想要查询服务指标数据、分析指标趋势、获取指标统计特征时使用此skill。
---

# 智能指标数据查询 Metrics Query by Template

这个skill用于智能查询服务的系统/中间件指标数据，自动根据数据量选择最合适的返回格式。如果出现了metricIds范围外的指标，需要告知用户不支持自定义指标。

## 使用场景

当用户想要：

- 查询服务的指标数据
- 分析指标趋势
- 获取指标的统计特征
- 按维度分组查询指标

## 工作流程

### Step 1: 获取有效Token

```bash
python ~/.claude/skills/metrics-query-by-template/scripts/check_token.py
```

---

### Step 2: 收集必需参数

**从用户问题中提取信息，只询问缺失的内容。**

**必需参数**:

- **app**: 服务名称
- **start / end**: 时间范围 `yyyy-MM-dd HH:mm:ss`
- **metricIds**: 指标ID列表

**可选参数**:

- **scope**: 查询范围 (CLUSTER表示集群/服务粒度，ZONE表示机房/可用区，CONTAINER表示单机/容器/POD视角)，默认CLUSTER
- **groupBys**: 分组维度列表

---

### Step 3: 调用API

```bash
python ~/.claude/skills/metrics-query-by-template/scripts/api_client.py \
  --app "creator-service-default" \
  --start "2024-03-18 00:00:00" \
  --end "2024-03-18 01:00:00" \
  --metric-ids "CPU_USAGE,MEMORY_USAGE"
```

---

### Step 4: 灵活呈现结果

**根据用户问题灵活调整输出：**

1. **"CPU使用率是多少？"** → 只回答当前值或平均值
2. **"CPU使用率的趋势如何？"** → 描述趋势（上升/下降/平稳）和关键数据点
3. **"CPU和内存的数据"** → 展示两个指标的关键统计信息
4. **"帮我看看这些指标"** → 完整的指标数据和统计特征

**输出要点**:

- 当前值、平均值、最大值、最小值
- 趋势描述
- 异常点识别
- 根据问题决定详细程度

---

## 参数说明

**metricIds** - 支持两种类型：模板（自动展开）和具体指标

### 一、模板类型（会自动展开为多个具体指标）

使用模板可以一次性查询某个类别下的所有指标：

- **SYSTEM**: 系统指标（包含CPU、内存、网络、磁盘等所有系统级指标）
- **THREAD**: 线程指标（线程利用率、线程数上限、线程队列数、线程执行时长）
- **JVM**: JVM指标（GC次数、GC耗时、内存使用、线程数等）
- **RPC**: RPC指标（包含RPC客户端和服务端的所有指标）
- **MYSQL**: MySQL指标（包含MySQL请求和连接池的所有指标）
- **HTTP**: HTTP指标（包含HTTP客户端和服务端的所有指标）
- **REDIS**: Redis指标（QPS、耗时、连接池、命中率等）
- **MQ**: MQ指标（包含MQ消费者和生产者的所有指标）
- **SCHEDULE**: Schedule调用相关指标（任务执行耗时、失败数、QPS等）
- **AI_INFRA**: AI基础设施监控指标（GPU使用率、显存、温度、功率等）
- **SENTINEL**: Sentinel监控指标（限流、熔断、鉴权、超时等）
- **AI_APP**: AI应用监控（算子、模型、Token、RAG、Embedding、Tool等）

**示例**:

- 查询所有系统指标：`["SYSTEM"]`
- 查询JVM和RPC：`["JVM", "RPC"]`

---

### 二、具体指标列表

#### 1. 系统监控指标

**CPU相关**:

- `CPU_USAGE` - CPU使用率
- `KERNEL_UTILIZATION` - 内核态占用率
- `USER_UTILIZATION` - 用户态占用率
- `CPU_CYCLES_PER_SECOND` - 每秒执行的CPU时间周期数
- `CPU_CYCLES_THROTTLED_CONTAINER_PER_MINUTE` - 每分钟容器被限制的CPU时间周期数

**内存相关**:

- `MEMORY_UTILIZATION` - 内存占用率
- `MEM_USAGE` - 内存使用率
- `MEM_CACHE_USAGE` - 内存中的cache用量
- `MEM_WORKING_SET_USAGE` - 内存工作集使用量
- `MEM_WORKING_SET_OCCUPIED` - 内存工作集占用量
- `SWAP_SPACE_USAGE` - 交换分区用量
- `RECORD_MAXIMUM_MEM_USAGE` - 最大内存使用量的记录
- `MEM_ALLOCATION_FAILURE_COUNT` - 每分钟申请内存失败次数计数
- `CONTAINER_MEMORY_MAPPED_FILE_MEMORY_USAGE` - 容器中内存映射文件使用内存量

**网络相关**:

- `NET_IN` - 网络入流量
- `NET_OUT` - 网络出流量
- `SEND_THROUGHPUT_PER_MINUTE` - 以太网每分钟发送吞吐量
- `RECEIVE_THROUGHPUT_PER_MINUTE` - 以太网每分钟接收吞吐量
- `ACCEPT_PACKETS_COUNT` - 每秒接收到的packets数量
- `SEND_PACKETS_COUNT` - 每秒发送的packets数量
- `RECEIVE_PACKET_DROP_COUNT` - 接收时丢弃的packet数量
- `SEND_PACKETS_DROPPED_COUNT` - 发送时丢弃的packet数量
- `RECEIVE_FAILURE_COUNT` - 接收时出现的错误次数
- `SEND_FAILURE_COUNT` - 发送时出现的错误次数

**磁盘相关**:

- `DISK_USAGE` - 磁盘使用量
- `DISK_WRITE_IO` - 磁盘写I/O
- `DISK_READ_IO` - 磁盘读I/O
- `OPEN_FILE_HANDLES_COUNT` - 打开的文件句柄数
- `INODE_TOTAL_COUNT` - inode总量
- `INODE_FREE_COUNT` - inode剩余量
- `FILESYSTEM_AVAILABLE_DISK_SPACE` - 文件系统可用的磁盘空间量
- `CONTAINER_FILESYSTEM_IO_OPERATION_COUNT` - 容器文件系统I/O操作数
- `IO_TIME_PER_MINUTE` - 每分钟I/O操作花费的时间
- `IO_READ_TIME_PER_MINUTE` - 每分钟I/O读操作花费的时间
- `IO_WRITE_TIME_PER_MINUTE` - 每分钟I/O写操作花费的时间

#### 2. 线程指标

- `THREAD_USAGE` - 线程利用率
- `THREAD_MAX_COUNT` - 线程数上限
- `THREAD_QUEUE_COUNT` - 线程队列数
- `THREAD_EXECUTION_DURATION` - 线程执行时长

#### 3. JVM指标

**GC相关**:

- `JVM_OLD_GC_COUNT` - JVM老年代GC次数
- `JVM_OLD_GC_TIME` - JVM老年代GC耗时
- `JVM_YOUNG_GC_COUNT` - JVM年轻代GC次数
- `JVM_YOUNG_GC_TIME` - JVM年轻代GC耗时

**内存相关**:

- `JVM_OLD_USED` - JVM老年代使用内存
- `JVM_EDEN_USED` - JVM eden区使用内存
- `JVM_SURVIVOR_USED` - JVM survivor区使用内存
- `JVM_METASPACE_USED` - JVM metaspace使用内存
- `JVM_METASPACE_USAGE` - JVM metaspace使用率
- `JVM_CODE_CACHE_USAGE` - JVM code cache使用率

**线程相关**:

- `JVM_LIVE_THREAD_COUNT` - JVM live线程总数

#### 4. RPC指标

**RPC服务端**:

- `RPC_SERVICE_SUCCESS_RATE` - RPC服务端调用成功率
- `RPC_SERVICE_QPS` - RPC服务端调用QPS
- `RPC_SERVICE_TIME` - RPC服务端调用耗时

**RPC客户端**:

- `RPC_CLIENT_SUCCESS_RATE` - RPC客户端调用成功率
- `RPC_CLIENT_QPS` - RPC客户端调用QPS
- `RPC_CLIENT_TIME` - RPC客户端调用耗时

#### 5. MySQL指标

**MySQL请求**:

- `MYSQL_SUCCESS_RATE` - MySQL调用成功率
- `MYSQL_QPS` - MySQL调用QPS
- `MYSQL_TIME` - MySQL调用平均耗时
- `MYSQL_TP95_TIME` - MySQL请求调用耗时tp95
- `MYSQL_TP99_TIME` - MySQL请求调用耗时tp99

**MySQL连接池**:

- `CONNECTION_TOTAL_COUNT` - 连接总数
- `ACTIVE_CONNECTED_COUNT` - 活跃连接数
- `FREE_CONNECTION_COUNT` - 空闲连接数
- `WAITING_CONNECTION_COUNT` - 等待连接数
- `CONNECTION_TIMEOUT_COUNT` - 建立连接超时数
- `MAX_CONNECTION_COUNT` - 最大连接数
- `CONNECTION_CREATED_TIME` - 连接创建耗时
- `GET_CONNECTED_TIME` - 连接获取耗时
- `CONNECTION_HOLD_TIME` - 连接占用耗时

#### 6. Redis指标

- `REDIS_SUCCESS_RATE` - Redis调用成功率
- `REDIS_QPS` - Redis调用QPS
- `REDIS_TIME` - Redis调用耗时
- `REDIS_TP95_TIME` - Redis请求耗时tp95
- `REDIS_TP99_TIME` - Redis请求耗时tp99
- `REDIS_CONNECTION_POOL_QUEUED` - Redis连接池排队数
- `REDIS_GET_CONNECTED_TIME` - Redis获取连接耗时
- `REDIS_HIT_RATE` - Redis命中率

#### 7. HTTP指标

**HTTP服务端**:

- `HTTP_SERVICE_SUCCESS_RATE` - HTTP服务端调用成功率
- `HTTP_SERVICE_QPS` - HTTP服务端调用QPS
- `HTTP_SERVICE_TIME` - HTTP服务端调用耗时

**HTTP客户端**:

- `HTTP_CLIENT_SUCCESS_RATE` - HTTP客户端调用成功率
- `HTTP_CLIENT_QPS` - HTTP客户端调用QPS
- `HTTP_CLIENT_TIME` - HTTP客户端调用耗时

#### 8. MQ指标

**MQ消费者**:

- `MQ_CONSUMPTION_SUCCESS_RATE` - MQ消费成功率
- `MQ_CONSUMER_QPS` - MQ消费者QPS
- `MQ_CONSUMPTION_AVERAGE_TIME` - MQ消费平均耗时
- `MQ_CONSUMPTION_TP95_TIME` - MQ消费耗时tp95
- `MQ_CONSUMPTION_TP99_TIME` - MQ消费耗时tp99

**MQ生产者**:

- `MQ_PRODUCTION_SUCCESS_RATE` - MQ生产成功率
- `MQ_PRODUCER_QPS` - MQ生产者QPS
- `MQ_PRODUCTION_AVERAGE_TIME` - MQ生产平均耗时
- `MQ_PRODUCTION_TP95_TIME` - MQ生产耗时tp95
- `MQ_PRODUCTION_TP99_TIME` - MQ生产耗时tp99

#### 9. Schedule调度指标

- `SINGLE_TASK_EXECUTION_TIME` - 单任务执行耗时
- `SINGLE_TASK_EXECUTION_FAILED` - 单任务执行失败
- `SINGLE_JOB_EXECUTION_QPS` - 单Job执行QPS
- `RUNNING_JOB` - 运行中的Job

#### 10. AI基础设施指标

**GPU相关**:

- `GPU_USAGE` - GPU使用率
- `TENSOR_CORE_USAGE` - TensorCore使用率
- `GPU_BANDWIDTH_USAGE` - 显卡带宽使用率
- `GPU_MEM_USED` - 显存占用
- `GPU_MEM_USAGE` - 显存占用率
- `GPU_MEM_ACTIVE` - 显存利用率
- `GPU_MEM_TEMPERATURE` - GPU显存温度
- `GPU_CORE_TEMPERATURE` - GPU核心温度
- `GPU_POWER` - GPU功率
- `GPU_SM_USAGE` - GPU SM设备使用率
- `GPU_SM_OCC_USAGE` - GPU SM_OCC使用率

**PCIE相关**:

- `PCIE_OUTPUT` - PCI-E发送数据速率
- `PCIE_INPUT` - PCI-E接收数据速率

#### 11. Sentinel指标

**单机限流**:

- `SINGLE_NODE_LIMIT_QPS_COUNT` - 单机限流QPS总数
- `QPS_TARGET_THRESHOLD` - QPS目标阈值
- `RATE_LIMITED_REJECTED_QPS` - 触发限流后拒绝的QPS
- `SUCCESSFUL_PROCESSED_QPS` - 通过并执行成功的QPS
- `FAILED_PROCESSED_QPS` - 通过并执行失败的QPS
- `RATE_LIMITED_REJECTED_QPM` - 触发限流后拒绝的QPM
- `SINGLE_NODE_RATE_LIMITED_LEVEL` - 单机限流水位
- `DRYRUN_ALLOWED_QPS` - 开启DryRun下应限流但放行的QPS

**鉴权**:

- `AUTHORIZATION_SUCCESSFUL_QPS` - 鉴权通过的QPS
- `AUTHORIZATION_FAILED_QPS` - 鉴权拦截的QPS
- `DRYRUN_ALLOWED_QPS_SHOULD_BE_DENNY` - 开启DryRun下应拦截但放行的QPS

**并发限流**:

- `CURRENT_CONCURRENCY_COUNT` - 当前并发数
- `MAX_CONCURRENCY_COUNT` - 最大并发数
- `DENNY_QPS` - 拒绝的请求QPS
- `DENNY_COUNT` - 拒绝的请求数量
- `DRYRUN_ALLOWED_SHOULD_BE_DENNY` - 开启DryRun后通过的应该拒绝的请求QPS

**过载保护**:

- `CPU_OVERLOAD_PROTECTED_QPS` - CPU过载保护block QPS
- `CPU_USAGE_RATIO` - 系统CPU使用比

**超时**:

- `SERVICE_DYNAMIC_TIMEOUT_CONFIG` - 服务治理动态超时配置
- `RPC_CLIENT_REAL_TIME_TIMEOUT_CONFIG` - RPC-Client实时生效超时配置
- `TRIGGER_TIMEOUT_QPS` - 触发超时QPS

**熔断**:

- `SENTINEL_TOTAL_REQUEST_QPS` - Sentinel总请求QPS
- `TRIGGER_CIRCUIT_BREAK_QPS` - 触发熔断的QPS
- `DOWNSTREAM_FAILURE_QPS` - 请求下游失败(未发生熔断)的QPS
- `DOWNSTREAM_SUCCEED_QPS` - 请求下游成功(未发生熔断)的QPS
- `DRYRUN_ALLOWED_BLOCKED_REQUEST_QPS` - 开启DryRun后通过的应该阻塞的请求QPS

**集群限流**:

- `CLUSTER_RATE_LIMITED_QPS_COUNT` - 集群限流总请求QPS
- `RATE_LIMITED_CLUSTER_REJECTED_QPS` - 触发集群限流后拒绝的QPS
- `CLUSTER_RATE_LIMITED_REQUEST_PASSED_QPS` - 集群限流请求通过QPS
- `CLUSTER_RATE_LIMITED_REQUEST_FALLBACK_QPS` - 集群限流请求fallback QPS
- `CLUSTER_RATE_LIMITED_PASSED_BLOCKED_REQUEST_QPS` - 集群限流通过的阻塞请求QPS
- `CLUSTER_RATE_LIMITED_THRESHOLD_QPS` - 集群限流阈值QPS
- `REDIS_CLUSTER_REQUEST_QPS` - Redis集群请求QPS
- `SERVICE_INSTANCE_COUNT` - 服务实例数量
- `CLUSTER_RATE_LIMITED_LEVEL` - 集群限流水位

#### 12. AI应用指标

**算子相关**:

- `OPERATOR_REQUEST_QPS` - 算子调用QPS
- `OPERATOR_REQUEST_SUCCESS_RATE` - 算子调用成功率
- `OPERATOR_AVERAGE_TIME` - 算子调用平均耗时
- `OPERATOR_P50_TIME` - 算子调用耗时p50
- `OPERATOR_P90_TIME` - 算子调用耗时p90
- `OPERATOR_P95_TIME` - 算子调用耗时p95

**模型相关**:

- `MODEL_REQUEST_QPS` - 模型调用QPS
- `MODEL_REQUEST_SUCCESS_RATE` - 模型调用成功率
- `MODEL_AVERAGE_TIME` - 模型调用平均耗时
- `MODEL_P50_TIME` - 模型调用耗时p50
- `MODEL_P90_TIME` - 模型调用耗时p90
- `MODEL_P95_TIME` - 模型调用耗时p95
- `MODEL_AVERAGE_TTFT` - 模型调用平均TTFT
- `MODEL_MAX_TTFT` - 模型调用最大TTFT
- `MODEL_P50_TTFT` - 模型调用p50TTFT
- `MODEL_P90_TTFT` - 模型调用p90TTFT
- `MODEL_P95_TTFT` - 模型调用p95TTFT
- `MODEL_AVERAGE_TPOT` - 模型调用平均TPOT
- `MODEL_MAX_TPOT` - 模型调用最大TPOT
- `MODEL_P50_TPOT` - 模型调用p50TPOT
- `MODEL_P90_TPOT` - 模型调用p90TPOT
- `MODEL_P95_TPOT` - 模型调用p95TPOT
- `MODEL_AVERAGE_E2E` - 模型调用平均E2E
- `MODEL_MAX_E2E` - 模型调用最大E2E
- `MODEL_P50_E2E` - 模型调用p50E2E
- `MODEL_P90_E2E` - 模型调用p90E2E
- `MODEL_P95_E2E` - 模型调用p95E2E

**Token相关**:

- `MODEL_CALL_TOKEN_COUNT` - 模型调用总token数
- `MODEL_CALL_INPUT_TOKEN_COUNT` - 模型调用输入token数
- `MODEL_CALL_OUTPUT_TOKEN_COUNT` - 模型调用输出token数

**RAG相关**:

- `VECTOR_DB_CALL_QPS` - 向量数据库调用QPS
- `VECTOR_DB_CALL_SUCCESS_RATE` - 向量数据库调用成功率
- `VECTOR_DB_CALL_AVERAGE_TIME` - 向量数据库调用平均耗时
- `VECTOR_DB_CALL_P50_TIME` - 向量数据库调用耗时p50
- `VECTOR_DB_CALL_90_TIME` - 向量数据库调用耗时p90
- `VECTOR_DB_CALL_95_TIME` - 向量数据库调用耗时p95
- `VECTOR_DB_AVERAGE_RETRIEVAL_COUNT` - 向量数据库平均召回数
- `VECTOR_DB_ZERO_RETRIEVAL_COUNT` - 向量数据库0召回数
- `VECTOR_DB_P50_RETRIEVAL_COUNT` - 向量数据库召回数p50
- `VECTOR_DB_P90_RETRIEVAL_COUNT` - 向量数据库召回数p90

**Embedding相关**:

- `EMBEDDING_CALL_QPS` - embedding调用QPS
- `EMBEDDING_CALL_SUCCESS_RATE` - embedding调用成功率
- `EMBEDDING_CALL_AVERAGE_TIME` - embedding调用平均耗时
- `EMBEDDING_CALL_P50_TIME` - embedding调用耗时p50
- `EMBEDDING_CALL_P90_TIME` - embedding调用耗时p90
- `EMBEDDING_CALL_P95_TIME` - embedding调用耗时p95
- `EMBEDDING_CALL_ALL_TOKEN_COUNT` - embedding调用总token数
- `AVERAGE_TOKENS_PER_EMBEDDING_CALL` - embedding平均每次消耗token数
- `EMBEDDING_TOKEN_CONSUMPTION_P50` - embedding token消耗p50
- `EMBEDDING_TOKEN_CONSUMPTION_P90` - embedding token消耗p90
- `EMBEDDING_TOKEN_CONSUMPTION_P95` - embedding token消耗p95

**Tool相关**:

- `TOOL_CALL_QPS` - 工具调用QPS
- `TOOL_CALL_SUCCESS_RATE` - 工具调用成功率
- `TOOL_CALL_AVERAGE_TIME` - 工具调用平均耗时
- `TOOL_CALL_P50_TIME` - 工具调用耗时p50
- `TOOL_CALL_P90_TIME` - 工具调用耗时p90
- `TOOL_CALL_P95_TIME` - 工具调用耗时p95

---

### 使用示例

**单个指标**:

```json
["CPU_USAGE"]
```

**多个指标**:

```json
["CPU_USAGE", "MEMORY_UTILIZATION", "DISK_USAGE"]
```

**使用模板（自动展开）**:

```json
["SYSTEM"] // 会自动展开为所有系统相关指标
```

**混合使用**:

```json
["SYSTEM", "JVM", "RPC_SERVICE_QPS"] // 模板+具体指标
```

**常见场景**:

- 查看系统资源：`["CPU_USAGE", "MEMORY_UTILIZATION", "DISK_USAGE"]`
- 查看JVM状态：`["JVM_OLD_GC_COUNT", "JVM_YOUNG_GC_COUNT", "JVM_METASPACE_USAGE"]`
- 查看RPC性能：`["RPC_SERVICE_QPS", "RPC_SERVICE_SUCCESS_RATE", "RPC_SERVICE_TIME"]`
- 查看数据库性能：`["MYSQL_QPS", "MYSQL_SUCCESS_RATE", "MYSQL_TP95_TIME"]`
- 查看GPU状态：`["GPU_USAGE", "GPU_MEM_USAGE", "GPU_CORE_TEMPERATURE"]`

---

### 其他参数

**scope**:

- `CLUSTER`: 集群级别（默认）
- `POD`: Pod级别
- `HOST`: 主机级别

**groupBys**: 分组维度数组，如 `["zone", "pod"]`
