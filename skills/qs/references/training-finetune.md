# Training Finetune Playbook

> **本文件是 UCP 框架下 finetune 模块的详细决策树补充。**
> 通用流程见 `creation-protocol.md`，参数依赖链和推理规则见 `profiles/training-finetune.yaml`。
> 本文件提供 finetune 特有的：dataset sync 检查、cloud-first 资源启发式、超参 preset、Preview 8-bullet 格式。

精调主链 SOP：用户自然语言需求 → 参数收敛 → Preview 确认 → Execute 提交 → 交付 job-id。

与 `qs` skill 的 training reference（命令字典）互补——本文件给"端到端决策流"。

## 1. 适用范围

- 精调（`--task-type sft|dpo` 默认 sft，`--train-way lora|full` 默认 lora），非自定义训练
- `--data-source dataset`：平台数据集（MVP）；不做 diagnose / search，失败原样报错

## 2. Pre-flight 检查

所有解析由 `qs ...` 真实数据驱动。**先跑再说**：不要基于 cwd、路径（如 `.worktrees/xxx`）、CLAUDE.md 等推断 `qs` 是否可用——先真跑。`exit != 0` 才是环境不可用的权威证据；失败原样透传 stderr（§7）。

### 2.1 Dataset 解析

1. `qs dataset list --name <user-input>`
   - 1 条 → 用这个 ID
   - 0 条 / 多条 → 走 §8.1 AskUserQuestion 兜底（不直接报错）
2. `qs dataset version list <dataset-id>` → 输出每条形如 `版本 <numeric-id> <name>`（`name` 是字符串如 `v1`，`numeric-id` 才是 API 真正接收的 `--dataset-version-id`；二者不可混用，如 dataset 2 的 v1 版本其 numeric id 多半是 2 而非 1）。默认取 list 第一条的 **numeric id**；用户显式指定版本时按 name 或 id 匹配后仍落到 **numeric id**

### 2.2 Model 解析

相同思路：`qs model list --name <name>` → 1 条用；0/多走 §8.2。版本同 §2.1。

### 2.3 Resource 解析

finetune 必填 queue / cloud / cluster / resource-package；**禁止**捏造 `default` 类占位名。**cloud 必须跟随 dataset 的同步归属**（dataset 在哪个 cloud 就只能在那个 cloud 训，否则跨云 Execute 必炸）。按 §3 启发式挑候选，Preview 全部列出。

## 3. Resource 启发式（cloud-first）

1. **Cloud**（来自 dataset）：`qs dataset version get <ds-id> <v-id>` → 解析"同步信息"里 `cloud_id=<X>`（挑"已完成"状态；多条完成取第一条）
2. **Queue**：`qs resources queue list --keyword train`（备选 keyword：`llm` / `NLP`）→ 对候选逐个跑 `qs resources cloud list --queue-id <qid>` → 第一个 cloud list 含 step-1 cloud-id 的 queue 即用
3. **Cluster**：`qs resources cluster list --queue-id <qid> --cloud-id <cid>` → 取第一条
4. **Pack**：`qs resources pack list` 过滤 `1Gpu` / `gpu` 关键字 → 取第一条

失败兜底：
- step 1 dataset 未同步到任何 cloud → 报错并提示 `qs dataset sync`，不猜
- step 2 无训练 queue 支持该 cloud → §8.3（option：同步 dataset 到新 cloud / 换 queue）
- step 3/4 0 候选 → §8.3

`--data-source dataset` 固定。命中全部 → 记 `name + id`。

## 4. Preset 推测

不询问超参；默认 **"领域适应" preset**：

| 超参 | 默认 | 决定方式 |
|---|---|---|
| `--train-way` | `lora` | 固定 |
| `--task-type` | `sft` | 固定 |
| `--epochs` | `3` | 数据量 < 1k 降到 `2`；> 10k 保持 `3` |
| `--lr` | `1e-4` | lora 固定；Execute 可被覆盖 |
| `--worker-num` | `1` | 固定 |

> MVP 不做 GPU-hour 估算（公式与模型大小无关，误导用户），Preview 不显示。

## 5. Preview 阶段

本阶段与 §6 Execute 阶段共享主 agent 同一会话上下文；dataset/model/资源 id 和 preset 在 turn 之间自然保留，不需要任何消息载体。

### 5.1 硬安全线（Pattern B 零决策卡）

**禁止** 本阶段 Bash 中出现 `qs training finetune`（任何形式，哪怕带 `--dry-run` 也不行）。只允许只读查询（`qs dataset list/get`、`qs model list`、`qs resources *`）。违反 = MVP 质量事故。

不弹 AskUserQuestion 决策卡——只返回 Preview 文本 + "要改哪项？不改就说'跑'"一行。仅当命中 §8 的三类硬边界才允许 AskUserQuestion。

### 5.2 组装流程

1. Pre-flight 拿齐 dataset / model / 4 项资源的 `name + id`
2. 套 §4 Preset defaults
3. 返回 Preview 文本（**严格 8 bullet**；查不到用 `?` 占位，不捏造；禁止新增或改名字段）：

```
准备用这组参数提交：
• base: <model-name> (<model-id>@<version>)
• dataset: <dataset-name>（<version-name>, id=<version-numeric-id>, <rows> 行）
• preset: 领域适应（lora, epochs=3, lr=1e-4）
• queue: <queue-name> (id=<queue-id>)
• cloud: <cloud-name> (id=<cloud-id>)
• cluster: <cluster-name> (id=<cluster-id>)
• resource-pack: <pack-name>
• task-name: ft-<model>-<dataset>-<YYYYMMDD>

要改哪项？不改就说"跑"。
```

4. Pre-flight 失败时不进 Preview，按 §7 / §8 处理

## 6. Execute 阶段

Preview 阶段拿到的 id / preset 直接从当前会话上下文复用（上一 turn 刚跑完、就在视野里），**无需**再次查询。

### 6.1 进入条件（意图识别）

用户在 Preview 之后出现下列任一意图 → 直接组命令：

- 明确确认：`跑` / `go` / `确认` / `提交` / `没问题` / `ok` / `ship it`
- 改参后确认：`lr 改 5e-5 跑` / `queue 换 NLP_train, 提交` / `改成 epochs 5 然后 go`

识别不出、或是"再看看/等等/取消"类否定意图 → 不进入 Execute，保持 Preview 原状。

### 6.2 参数调整

用户若在 Preview 后说 "lr 改 5e-5 跑" 或 "queue 换成 NLP_train"，解析自然语言覆盖对应 id/preset。无法解析或多义 → 走 §8 兜底。

### 6.3 命令组装 & 执行

```bash
qs training finetune --yes \
  --name "<ft-...>" --data-source dataset \
  --dataset-id <id> --dataset-version-id <vid> \
  --model-id <id> --model-version <ver> \
  --queue-id <qid> --cloud-id <cid> \
  --cluster-id <clid> --resource-package-name <pack> \
  --task-type sft --train-way lora \
  --epochs 3 --lr 1e-4 --worker-num 1
```

（优先 id 避免名字歧义；pack 用 name 因 list 未暴露 id）

### 6.4 job-id 解析

从 stdout 匹配 `trn_[a-zA-Z0-9]+`；匹配失败 → 原样透传 stdout + stderr。

### 6.5 返回 4 行 handoff

```
✅ 已提交训练任务
job-id: <job-id>
参数：<model-name> + <dataset-name> + <关键改动一句话>
等 15-30 分钟可以回来问进度
```

## 7. 失败处理（保守策略）

| 失败类型 | 识别 | 处置 |
|---|---|---|
| dataset/model not found | stderr 含 `not found` + 名字 | 走 §8.1 / §8.2 兜底（不 fuzzy） |
| quota exceeded | stderr 含 `quota` / `资源不足` | 提示 `qs maas quota`，不切池 |
| auth failed | stderr 含 `401` / `unauthorized` / `token` | 提示 `qs login`，不 retry |
| 其他 | 未识别失败 | 原样透传 stdout + stderr |

**非协商**：绝不 auto-retry / 切换资源 / fuzzy match / 继续下一步。

## 8. AskUserQuestion 硬边界

3 种情况用决策卡（其余走 Preview 文本 + 自然语言）：

### 8.1 dataset 0/多匹配 或未给且账下 > 3

- `qs dataset list [--name <input>]` 拉候选，取前 5
- option label: `<name> · <rows> 行 · <updated>`（如 `xhs-demo-v3 · 12000 行 · 2d ago`）
- Other 由 AskUserQuestion 自动提供

### 8.2 base model 0/多匹配 或未给且账下 > 3

同 §8.1，换成 `qs model list`；label 含参数量/架构（如 `Qwen2.5-0.5B · Qwen2`）。

### 8.3 资源启发式失败

3 类触发场景：
- **dataset 未同步到任何 cloud** — option：`qs dataset sync <ds> <v> --cloud-id <X>`（列可用 cloud 前 5）或换 dataset
- **无训练 queue 支持 dataset cloud** — option：(a) 同步 dataset 到某个有训练 queue 的 cloud，(b) 列其他 cloud 的 queue 让用户选（但要提示"会跨云，dataset 需先同步"）
- **cluster/pack 0 候选** — 列 list 前 10 条让用户选

选完后继续下一级资源解析（保留层级依赖）。

## 9. 示例（精简）

```
User: 用 xhs-demo-v3 微调 Llama3-8B
[Preview turn] 主 agent 跑 Pre-flight 5 套查询 → 按 §5.2 返回 8 bullet
User: lr 改 5e-5, 跑
[Execute turn] 主 agent 识别意图（§6.1），从上一 turn 上下文复用 id
  → 按 §6.3 组命令带 --lr 5e-5 → §6.5 handoff
```
