---
name: qs
description: "QuickSilver (QS) 平台 CLI 工具助手，管理数据集、训练任务、推理服务、批量推理、模型评测、量化压缩、MaaS、Pod 操作等。触发词：qs、quicksilver、训练任务、数据集、pod日志、推理服务、部署、deploy、模型评测、评测报告、maas、配额申请、token用量、batch-infer、批量推理、批推、compress、量化、压缩、qs exec、qs logs、qs dataset、qs deploy、qs eval。"
---

# QS CLI 助手

帮助用户通过 QuickSilver 平台 CLI 工具 `qs` 完成日常操作。用户可通过 `/qs <question>` 传入问题，Agent 根据意图构造并执行对应的 `qs` 命令。

## Agent 行为指南

### 前置检查（仅会话首次）

1. 运行 `which qs`，未找到则执行 `npm install -g @xhs/qs-cli --registry=http://npm.devops.xiaohongshu.com:7001` 安装
2. 首次安装后或遇退出码 3（认证失败）时，用 AskUserQuestion 分别询问薯名邮箱前缀和 QS Token，收集后执行 `qs config set qs_user <邮箱前缀>` 和 `qs config set qs_token <token>` 自动配置
3. **不要读取 `~/.qs/settings.json`，其中包含用户 Token**

### 核心原则

1. **直接执行**：用户描述意图时，直接构造并运行 qs 命令，不要只给出命令让用户自己跑
2. **解析输出**：运行命令后解读结果，用简洁中文总结关键信息，不要原样转发大段输出
3. **链式操作**：多步操作自动串联（如：查找数据集 → 获取版本 → 查看同步状态）
4. **错误恢复**：命令失败时根据退出码诊断原因，参考下方错误处理表

### 命令发现（首选方式）

操作前，**先读取对应的 references 文档**（见下方"典型场景"表）。如果 reference 中定义了专用流程，**严格按 reference 流程执行，不使用本节通用规则**。reference 未覆盖时，再通过 `qs docs <module>` 获取参数文档：

```bash
qs docs                  # 列出所有模块
qs docs <module>         # 查看模块完整参数文档（必填/可选/默认值/示例）
qs <command> --help      # 子命令用法
```

### 交互与安全

| 场景 | Agent 行为 |
|------|-----------|
| 查询类（list、get） | 直接运行，加 `--format json -q` 获取结构化数据 |
| 交互命令（config、选择容器） | 提示用户 `! qs <command>` 自行运行 |
| 创建操作 | 必须按 [creation-protocol.md](references/creation-protocol.md) 的 UCP 六步流程（EXTRACT→LOAD→RESOLVE→PREVIEW→EXECUTE→RECOVER）执行。LOAD 步骤读取对应模块的 [profile YAML](references/profiles/)，获取参数依赖链、查询命令和选择策略。reference 有专用 playbook（如 [training-finetune.md](references/training-finetune.md)）时，playbook 补充 UCP 未覆盖的模块特有决策树 |
| 危险操作（delete、stop） | 执行前必须确认用户意图 |

### 结果附带平台链接

命令输出中如果包含平台链接，**在结果摘要末尾附上**，方便用户直接跳转查看。

### 易错点

- **`dataset create --dataset-format`** 指数据集格式（alpaca/sharegpt 等），**不是**全局输出格式 `-o json`
- **`qs logs` 对存活 pod 会持续流式输出**，Agent 必须设置 Bash timeout（如 30000ms）避免挂起
- **流式命令**（logs、exec）不支持 `--format json`，仅资源管理命令支持
- **eval 的 `--models`/`--datasets`/`--metrics`/`--params` 参数为 JSON 字符串**，需用单引号包裹，格式见 [references/eval.md](references/eval.md#json-参数格式)
- **`deploy scale`/`update-image` 仅支持 staging 环境**（标 * 的子命令），`--env` 默认值为 `staging`（非必填）
- **`batch-infer create` 的 `--parameters` 参数为 JSON 字符串**，需用单引号包裹
- **`compress create` 的 `--hyperparameters` 参数为 JSON 字符串**，需用单引号包裹
- **`batch-infer resume` 是续推操作**，从上次检查点继续，不是重新创建任务
- **`training finetune` 的 `--model-name` 支持按名称自动解析模型 ID**（先查官方模型再查个人模型），可替代 `--model-id`；但 `compress create` 的 `--model-name` 需配合 `--model-version` 使用，行为不同

### 创建型任务

所有创建操作必须遵循 [Universal Creation Protocol (UCP)](references/creation-protocol.md) 六步流程。LOAD 步骤会读取对应模块的 [profile YAML](references/profiles/)（如 `profiles/training-finetune.yaml`），获取参数依赖链、查询命令模板和选择策略。部分模块有专用 playbook（如 [training-finetune.md](references/training-finetune.md)）提供模块特有的决策树和 AskUserQuestion 边界。

## 命令索引

> 快速索引，具体参数以 `qs docs <module>` 输出为准。

| 模块 | 说明 | 关键子命令 |
|------|------|-----------|
| `config` | 凭证配置（交互式，需用户 `! qs config`） | `show`, `init`, `set qs_user/qs_token/qs_base_url` |
| `exec` | 进入 Pod 容器 | 交互式需 `! qs exec`，非交互 `qs exec <pod> -- <cmd>` |
| `logs` | 查看 Pod/Trial 日志 | `qs logs <pod/trialId> [-c container] [-n tail]` |
| `dataset` | 数据集 CRUD、版本、同步 | `list`, `get`, `create`, `delete`, `version list/get/delete`, `sync`, `storage-path`, `clusters` |
| `training` | 训练任务管理 | `list`, `get`, `search`, `create`, `finetune`, `stop`, `diagnose`, `list-trials`, `list-container`, `filter` |
| `deploy` | 推理服务部署与管理 | `list`, `get`, `create`, `copy`, `workloads`, `api-doc`, `monitor`, `scale`*, `update-image`* |
| `eval` | 模型评测（任务/版本/报告/对比） | `list`, `get`, `create`, `delete`, `stop`, `report`, `report-download`, `compare`, `next-version-name`, `predatasets`, `version list/get/create/delete` |
| `model` | 模型管理 | `list`, `version list` |
| `resources` | 训练资源（队列/云区/集群/套餐/配额） | `queue list`, `cloud list`, `cluster list`, `pack list`, `quota get` |
| `cloudfs` | 云盘路径查询 | `list` |
| `memory` | 使用记忆管理 | `list`, `clear`, `export` |
| `skill` | Skill 安装管理 | `list`, `install` |
| `docs` | 查看命令参数文档 | `qs docs [module]` |
| `batch-infer` | 批量推理（批推）任务管理（创建/查询/停止/续推） | `list`, `get`, `create`, `delete`, `stop`, `resume`, `ray-yaml`, `supported-clouds` |
| `compress` | 大模型量化压缩（创建/查询/诊断） | `list`, `get`, `create`, `stop`, `diagnose`, `list-trials` |
| `maas` | MaaS 模型即服务（服务查询/配额申请/用量/Token） | `server list`, `server stop`, `quota apply`, `usage get`, `usage list`, `config list`, `token list`, `brand list` |
| `pet` | 宠物陪伴系统 | `set`, `draw`, `off`, `status`, `list` |
| `upgrade` | 升级 CLI | `qs upgrade` |

### 全局选项

| Flag | 说明 |
|------|------|
| `-o, --format <table\|json>` | 输出格式，默认 table（exec/logs 不支持） |
| `-q, --quiet` | 静默模式，仅输出数据 |
| `--dry-run` | 预览请求，不实际执行（仅变更操作支持） |
| `--config <file>` | 指定 YAML 配置文件路径 |
| `--page-all` | 自动翻页获取全部数据 |
| `--page-limit <n>` | 翻页最大条数限制 |
| `--page-delay <ms>` | 翻页请求间隔（毫秒） |

凭证解析顺序：`~/.qs/settings.json` → `$QS_USER/$QS_TOKEN` → 交互式输入

## 典型场景

按需查阅对应模块的操作手册（Agent 按用户意图加载对应文件即可）：

| 场景 | 参考文档 |
|------|----------|
| 日志排查 | [references/logs.md](references/logs.md) |
| 数据集管理 | [references/dataset.md](references/dataset.md) |
| 推理服务管理 | [references/deploy.md](references/deploy.md) |
| 训练任务管理 | [references/training.md](references/training.md) |
| 精调（finetune）创建 | [references/training-finetune.md](references/training-finetune.md) + [profiles/training-finetune.yaml](references/profiles/training-finetune.yaml) |
| 模型评测管理 | [references/eval.md](references/eval.md) |
| 批量推理管理 | [references/batch_infer.md](references/batch_infer.md) |
| 量化压缩管理 | [references/compress.md](references/compress.md) |
| MaaS 模型即服务 | [references/maas.md](references/maas.md) |

## 训练任务诊断

当用户描述训练任务异常（卡住/失败/报错/重启/崩溃），**必须先读取 [references/training-diagnose.md](references/training-diagnose.md) 的完整流程和强制规则后再开始诊断**。

## 错误处理

| 退出码 | 含义 | Agent 行为 |
|--------|------|------------|
| 0 | 成功 | 解析输出，呈现结果 |
| 2 | 参数错误 | 查看错误输出中列出的缺失参数，运行 `qs docs <module>` 查看完整参数文档 |
| 3 | 认证失败 | 提示 `! qs config` 配置凭证 |
| 4 | 资源不存在 | 确认 ID，用 list 查看可用资源 |
| 5 | 权限不足 | 告知用户联系管理员 |
