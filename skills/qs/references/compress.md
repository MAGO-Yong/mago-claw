# 量化压缩管理

1. 查看压缩任务列表：`qs compress list --format json -q`（`--scope`、`--query` 过滤）
2. 任务详情：`qs compress get <trialId> --format json -q`
3. 创建压缩任务：按 [creation-protocol.md](creation-protocol.md) UCP 流程执行。RESOLVE 要点：
   - 模型：用 `qs model list --search` 确认，version 默认最新
   - 压缩策略：从用户意图推导（提到 INT4/GPTQ/AWQ → W4A16；提到 INT8/FP8 → W8A8-FP8）；无明确意图默认 W4A16
   - 资源：按 memory → `qs resources queue list` → cloud → cluster → pack 链路自动推导
   - 数据源：默认 preset；用户提供路径时推导 source 类型
   - 导出名：自动生成 `<model_short>-<strategy>-<YYYYMMDD>`
   - 所有必填参数 resolve 完毕后 PREVIEW → 确认 → `qs compress create ... --yes`
4. 在已有 Job 下新建 Trial：`qs compress create --job-id <jobId> ... --yes`
5. 停止任务：`qs compress stop <trialId> --yes`（需先确认用户意图）
6. 诊断问题：`qs compress diagnose <jobId> <trialId>`，分析调度事件和 Pod 状态
7. 查看历史 Trial：`qs compress list-trials <jobId> --format json -q`
