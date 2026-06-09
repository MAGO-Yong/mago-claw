# 训练任务诊断

当用户描述训练任务异常（卡住/失败/报错/重启/崩溃），**必须读取本文档完整流程后再开始诊断**。

**强制规则**（不可跳过）：
1. **Phase 1 数据预加载**：并行执行 `qs training diagnose` 和 `aischeduler-cli job get-trial-context`，两个都必须执行
2. **Phase 2 分析全部 5 个维度**：调度上下文 → 调度事件 → Pod Events → 日志诊断 → 节点健康
3. **出报告前必须查 K8s 上下文**：`aischeduler-cli k8s get-k8s-context`，获取 CRD 失败条件、Pod 详情、exit code
4. **报告必须包含调度链路分析段落**：即使调度正常也要输出"调度链路无异常"并附时间线证据
5. **报告必须按 Phase 4 模板输出**
6. **分布式训练遇到超时/协调错误时**：必须至少再拉 1 个其他 Pod 日志对比

## 工作流

### Phase 1: 数据预加载（两个都必须执行）

```bash
# 命令 1: 平台数据
qs training diagnose <trialId> -o json -q

# 命令 2: 调度上下文
aischeduler-cli job get-trial-context --trial-id <trial_id> --biz quicksilver
```

从命令 2 提取后续需要的 ID：
- Job DB ID: `jobs.result.data[].id`（id 最大的是最新 job）
- Job 完整名称: `{name}-ai-{db_id}`
- 业务 cluster_id: `resource_pools[].result.data[0].cluster_id`

### Phase 2: 5 维度分析（全部要做，每个输出一行发现摘要）

| 维度 | 数据来源 | 看什么 |
|------|---------|--------|
| 调度上下文 | get-trial-context | Job 状态/配额（deserved vs allocated）/restart 次数/资源池 |
| 调度事件 | diagnose.scheduling_events | 各阶段耗时是否正常（Uncommit→Pending < 30s, Pending→Running < 2min） |
| Pod Events | diagnose.pod_events | FailedScheduling/OOMKilled/Killing/Evicted。谁先退出？谁被连锁 Kill？ |
| 日志诊断 | diagnose.log_diagnose | hit_details 中 priority ≥ 80 的规则命中；not_hit_logs 中未匹配的 ERROR |
| 节点健康 | diagnose.node_health | is_healthy=false 的节点及 node_problem_reason |

### Phase 3: 按需深入

根据 Phase 2 的发现选择方向。**出报告前必须执行 K8s 上下文查询。**

**获取 K8s 上下文**（必做）：
```bash
aischeduler-cli k8s get-k8s-context --cluster-id <biz_cluster_id> --job-db-id <job_db_id> --job-name <job_full_name>
```
提取：CRD 失败条件、异常 Pod（exit code/role/rank/node）、volume mounts、init container 状态。

**获取 Pod 日志**（运行时故障时）：
```bash
aischeduler-cli k8s get-pod-logs --cluster-id <id> --namespace <ns> --pod-name <pod> --container pytorch --tail-lines 500 [--previous]
```

**分布式训练强制规则**：看到超时/协调/通信类错误时，必须至少再拉 1 个其他 Pod 的日志对比路径、时间戳、错误信息。

**调度链路深入**（调度异常时）：
```bash
# 节点资源
aischeduler-cli k8s get-node-resources --cluster-id <id> --label-selector "amhub.xiaohongshu.com/resource-pool-id=<rp_id>"
# 超节点调度诊断
aischeduler-cli k8s diagnose-scheduling --cluster-id <id> --label-selector "..." --required-gpu <n>
```

**文件不存在时**：不能停在"文件不存在"，必须查 Pod 的 volume mounts 确认是路径错误还是云盘未挂载。

### Phase 4: 按模板输出报告（每个段落必填）

```
## 训练任务诊断结果

**任务**: {biz}/{trial_id} (Job DB ID: {job_db_id})
**名称**: {job_full_name}
**状态**: {status}
**CRD 类型**: PyTorchJob / VolcanoJob / RayJob
**规格**: {N} Master + {M} Worker, 每节点 {gpu}×{gpu_type} (共 {total} GPU)
**集群**: {cluster_zone} | 资源池: {resource_pool_id}

### 调度链路分析
{即使正常也要写。列出时间线 + 配额状态 + 结论}

### 失败定位
**异常 Pod**: {pod} (role={role}, rank={rank}, 节点 {node_ip})
**CRD 失败条件**: {conditions}

### 错误分类
{见下方错误速查表}

### 根因
{一句话，深入到真正原因}

### 关键证据
{日志行 + exit code + K8s Events + volume mounts}

### 失败链
{因果链：A → B → C → Job Failed}

### 影响范围
- 根因 Pod: ...
- 连锁影响: ...

### 建议修复
1. ...

### 是否可自动恢复
- auto_restart_times: {X}, current_restart_num: {Y}
- {判断：重启能否恢复}
```

---

## 错误速查表

### 调度层

| Job 状态 | 数据特征 | 根因 | 排查命令 |
|---------|---------|------|---------|
| Waiting > 30s | `not enough resource` | 配额不足 | 查 quotas: deserved vs in_quota_allocated |
| Waiting > 30s | `stuck by job id=X` | 队首阻塞 | 查同队列同资源池的活跃 Job |
| Waiting | `resource pool X not schedulable` | 资源池有 Pending Pod 未调度 | 查该资源池 Pending Job |
| Waiting | `blocked due to machine-error-migration` | 故障机驱逐阻塞（5min 自动解除） | 等待 |
| Permit 反复 | `dry run failed` | 物理资源不足 | `k8s get-node-resources` 逐节点查 |
| Permit 反复 | `schedulePodGroupByNetworkGroups failed` | 超节点组 GPU 不够 | `k8s diagnose-scheduling` |
| Pending > 5min | CRD 存在但无 Pod | 控制器问题 | 查 training-operator/volcano-controller Pod 状态 |
| Pending > 5min | Pod 无 nodeName | K8s 调度失败 | `k8s get-k8s-context` 看 FailedScheduling 事件 |
| Pending > 5min | Pod 有 node 但 InitContainer 卡住 | precheck 失败 | 查 precheck 容器日志 |
| Pending → Waiting 循环 | `start reschedule` | ReSchedule 超时重调度 | 查 Pod 为何无法调度 |

### 运行时

| 信号 / 日志关键词 | 错误分类 | 根因 | 排查方向 |
|------------------|---------|------|---------|
| exit 137 (SIGKILL) | Host OOM | 内存超限 | 查 memory limit、num_workers |
| exit 139 (SIGSEGV) | 段错误 | GPU 驱动 / 内存损坏 | 查节点 GPU 健康 |
| exit 143 (SIGTERM) | 优雅终止 | preemption / 超时 / 用户取消 | 查 Pod Events |
| `CUDA out of memory` | GPU OOM | batch size 过大 / 模型超显存 | 减 batch size / 混合精度 |
| `CUDA error: device-side assert` | CUDA 错误 | 张量索引越界 | 查 label vs vocab size |
| `Xid` / `GPU has fallen off the bus` | GPU 硬件故障 | 节点 GPU 坏 | 加 IP 黑名单重试 |
| `NCCL timeout` / `Watchdog caught collective` | NCCL 通信 | 某 rank 崩溃或网络故障 | **找第一个报错的 rank** |
| `FileNotFoundError` / `No such file` | 存储/路径 | 路径错误或云盘未挂载 | **查 volume mounts** |
| `Error loading checkpoint` / `size mismatch` | Checkpoint | 模型结构变更 / 并行度改变 | 检查 TP/PP 配置 |
| `init_process_group timeout` | 分布式初始化 | MASTER_ADDR/PORT 错误 | 查网络连通性 |
| `no space left on device` | 磁盘满 | checkpoint 占满空间 | 清理磁盘 |
| `GPU memory leak detected` | precheck | GPU 显存泄漏 | IP 加黑名单重试 |
| `3fs mount` / `mount failed` | 存储挂载 | 3FS 服务异常 | 查节点 3FS 状态 |
| `NCCL barrier timeout` (precheck) | precheck NCCL | RDMA 故障 | IP 加黑名单重试 |

### 节点健康

| node_problem_reason | 含义 | 严重程度 |
|--------------------|------|---------|
| `nvlink-inactive` | NVLink 连接不活跃 | High |
| `GuestReboot` | 虚机重启 | High |
| `MemoryPressure` | 内存压力 | Medium |
| `DiskPressure` | 磁盘压力 | Medium |
| `NetworkUnavailable` | 网络不可用 | Critical |
| `KernelPanic` | 内核崩溃 | Critical |
| `HardwareFailure` | 硬件故障 | Critical |
