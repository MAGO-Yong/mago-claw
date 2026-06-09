# 训练任务管理

## Job 与 Trial 的区别

- **Job**：一项训练工作的业务单元（精调或自定义训练），承载任务配置（名称、镜像、资源、数据集等）
- **Trial**：Job 下的一次实际运行。首次创建 Job 时自动生成第一个 Trial，后续重跑或调参在同一 Job 下新增 Trial
- 关系：一个 Job 包含多个 Trial（1:N），`list-trials` 可查看某 Job 的全部运行记录
- CLI 中大部分操作以 **trialId** 为粒度（get、stop、diagnose、logs），创建和查看历史以 **jobId** 为粒度

## 操作手册

1. 查看/搜索任务：`qs training list --format json -q` 或 `qs training search <keyword> --format json -q`
2. 任务详情：`qs training get <trialId> --format json -q`
3. 查询资源：创建任务前按链路 `queue list → cloud list → cluster list → pack list` 逐步获取所需 ID，或用 `qs resources quota get --queue-id <queueId>` 快速查看各集群空闲 GPU。精调还需查 `qs model list` 和 `qs dataset list`
4. 创建自定义任务：按 [creation-protocol.md](creation-protocol.md) UCP 流程执行。资源参数按 memory → queue list → cloud list → cluster list → pack list 链路自动推导（支持 `--*-name` 替代 `--*-id`）。所有必填参数 resolve 完毕后 PREVIEW → 确认 → `qs training create ... --yes`
5. 创建大模型精调：**完整流程见 [training-finetune.md](training-finetune.md)**（参数依赖链见 [profiles/training-finetune.yaml](profiles/training-finetune.yaml)）
6. 在已有 Job 下重跑：`qs training create --from-job-id <jobId> ... --yes`
7. 停止任务：`qs training stop <trialId> --yes`（需先确认用户意图）
8. 诊断问题：`qs training diagnose <trialId> -o json -q`，获取完整诊断数据（含日志规则匹配 + 节点健康）。完整诊断流程见 [training-diagnose.md](training-diagnose.md)
9. 查看历史 Trial：`qs training list-trials <jobId> --format json -q`
