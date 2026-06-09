# 模型评测管理

1. 查看评测任务：`qs eval list --format json -q`
2. 任务详情：`qs eval get <taskId> --format json -q`
3. 创建评测任务：按 [creation-protocol.md](creation-protocol.md) UCP 流程执行。RESOLVE 要点：name 自动生成 `eval-<model_short>-<YYYYMMDD>`；eval-method 默认 auto；eval-type 默认 score；models 从用户意图提取后用 `qs model list --search` 确认；datasets 用 `qs eval predatasets -o json -q` 匹配预置集。所有必填参数 resolve 完毕后 PREVIEW → 确认 → `qs eval create ... --yes`
4. 发起新一轮评测（创建版本）：
   - 先获取推荐名称：`qs eval next-version-name <taskId>`
   - 必填：`--task-id`、`--name`、`--eval-method`、`--eval-type`、`--datasets`、`--models`
   - 执行：`qs eval version-create ... --yes`
5. 查看进度：`qs eval versions <taskId> --format json -q`（关注 status 和 progress_percent）
6. 查看报告：`qs eval report <taskId> <versionId> --format json -q`
7. 多版本对比：`qs eval compare --version-ids <id1,id2> --format json -q`
8. 下载报告：`qs eval report-download <taskId> <versionId> --file-type csv`
9. 停止运行中的版本：`qs eval stop <taskId> <versionId> --yes`

## JSON 参数格式

eval 的创建命令涉及 JSON 参数，用单引号包裹：

| 参数 | JSON 结构示例 |
|------|---------------|
| `--models` | `'[{"model_id":"gpt-4","type":"official"}]'` |
| `--datasets` | `'[{"type":"preset","name":"ds1"}]'` 或 `'[{"type":"custom","path":"oss://..."}]'` |
| `--metrics` | `'[{"name":"准确率","value":"acc"}]'` |
| `--params` | `'{"temperature":0.7}'` |

状态枚举：`running`、`success`、`failed`、`stopped`、`pending`、`canceled`
