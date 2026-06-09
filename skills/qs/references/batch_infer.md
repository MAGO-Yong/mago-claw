# 批量推理管理（批推）

1. 查看任务列表：`qs batch-infer list --format json -q`（`--scope my/all`、`--status`、`--name` 过滤）
2. 任务详情：`qs batch-infer get <taskId> --format json -q`
3. 创建批量推理任务：按 [creation-protocol.md](creation-protocol.md) UCP 流程执行。RESOLVE 要点：
   - name 自动生成 `batch-<model_short>-<YYYYMMDD>`
   - infer-type 从用户意图推导（提到 MaaS/API → maas；提到自定义模型 → user）
   - model（MaaS）：用 `qs maas server list -o json -q` 查在线服务匹配
   - 输入源：从用户提供的路径推导 source 类型（/cloudfs/ → local, oss:// → oss）
   - 输出源：自动生成 `/cloudfs/<user>/batch-output/<model_short>-<YYYYMMDD>/`
   - 所有必填参数 resolve 完毕后 PREVIEW → 确认 → `qs batch-infer create ... --yes`
4. 预览配置：`qs batch-infer create ... --generate-config` 仅生成配置不提交
5. 续推（从检查点继续）：`qs batch-infer resume <taskId> --yes`
6. 停止任务：`qs batch-infer stop <taskId> --yes`（需先确认用户意图）
7. 下载 Ray YAML 模板：`qs batch-infer ray-yaml <taskId> --output ./ray.yaml`
8. 查看支持的数据源云区：`qs batch-infer supported-clouds --format json -q`
