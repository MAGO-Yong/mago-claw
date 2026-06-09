# 推理服务管理

## 查询

1. 查询服务：`qs deploy list --format json -q`（默认我的，`--scope all` 全部，`--search`/`--gpu` 过滤）
2. 服务详情：`qs deploy get <service-name> --format json -q`
3. 部署组分布：`qs deploy workloads <service-name> --format json -q`（含 GPU/CPU 利用率，`-1` 表示暂无监控）
4. API 调用文档：`qs deploy api-doc <service-name> --language curl`

> 更多过滤选项（`--gpu`、`--deploy-type`、`--zone`、`--status` 等）可通过 `qs docs deploy` 查看。

## 创建推理服务

用户通常只提供模型名（甚至是模糊关键词），Agent 应**自动推断其余参数**，尽量减少交互轮次。

> **重要**：deploy create 的完整流程已在下方定义，**不要使用 creation-protocol.md 的通用流程**，也不需要运行 `qs docs deploy` 查参数文档，直接按 Step 1-4 执行即可。
>
> **交互原则**：需要用户决策时，**尽量用 AskUserQuestion 提供选项让用户选择，避免让用户手动输入**。
>
> **禁止**：不要用 `qs model list --scope all` 拉全量模型再用 python 过滤，**必须用 `--search` 参数**让服务端过滤。不要查询用户已经明确提供的信息。

### 自动决策流程

> **前置：提取用户已提供的参数**
>
> 执行 Step 之前，先从用户输入中提取已明确提供的参数（模型名/关键词、队列名、集群、卡型、服务名等）。**已提供的参数直接使用，跳过对应的自动发现逻辑。**

**Step 1 — 模型确认**

- 搜索命令（固定格式，不要加 `--scope`）：`qs model list --search "<用户原文中的模型名或关键词>" --format json -q`
- **将用户提供的完整模型名/关键词原样传入 `--search`，不要截断或简化**（例：用户说 `deepseek-coder-7b-instruct-v1.5` 就搜 `deepseek-coder-7b-instruct-v1.5`，不要缩短为 `deepseek-coder`）
- 搜索结果处理：
  - **仅一个匹配**：直接使用，告知用户匹配到的完整模型名
  - **多个匹配**：用 AskUserQuestion 列出所有匹配项让用户选择（展示完整模型名和系列），**不要自行筛选或排除任何结果**
  - **无匹配**：告知用户未找到，请提供更准确的名称
- **重要**：后续 `--model-name` 参数必须使用模型列表中返回的**完整 name 字段值**，不要截断或修改

**Step 2 — 队列 + 集群 + 卡型**

- **用户已提供队列名**：`qs resources queue list --keyword "<队列名>" --format json -q`，直接按名称过滤，不拉全量
- **用户未提供队列**：`qs resources queue list --format json -q`，查询全部队列，筛选有推理 quota 的（`application` 含 `"inference"`）

确定队列后，查询推理配额：`qs resources quota get --queue-id <id> --type inference --format json -q`
- **卡型优先级**：优先选择高性能卡型（H20 > H800 > A100 > A10 > 其他），同等卡型下选余量最大的集群
- 如果用户未指定队列且有多个推理队列，可并行查询各队列配额，按上述优先级选全局最优的
- GPU 卡数 `--gpu-num` 不需要指定，CLI 会自动推算

**Step 3 — 服务名（自动生成或用户提供）**

- 服务名格式为 `xxx-yyy-zzz`（三段式，仅小写字母和数字，single 模式最长 30 字符，distributed/pd 最长 20 字符）
- **第一段 xxx 是应用名**，必须是队列绑定的合法应用名。从 Step 2 获取的队列 `application` 字段中取得
- **应用名获取**：
  - **1 个应用名**：直接使用
  - **多个应用名**：用 AskUserQuestion 让用户选择
  - **0 个应用名**（`application` 为空数组）：无法自动生成服务名，不传 `--service-name`，由后端自动生成
- **自动生成规则**（有应用名时）：格式为 `{app}-{模型缩写}-{4位随机串}`
  - 第二段：从模型名提取关键部分，转小写，去掉非法字符，截断以确保总长度不超限
  - 第三段：4 位随机字母数字串（如 `a3x7`），避免与已有服务名冲突
  - 例：应用名 `myapp`，模型 `Qwen2.5-7B-Instruct` → `myapp-qwen257b-a3x7`
  - 例：应用名 `myapp`，模型 `DeepSeek-V3` → `myapp-dsv3-k9m2`
- 生成后在 Step 4 汇总中展示，用户可修改

**Step 4 — 预览、确认并执行**

1. 先用 `--dry-run` 预跑，获取完整配置（含自动推算的 GPU 数量、部署类型等）：
   `qs deploy create --model-name <name> --zone <zone> --gpu-type <type> --queue-id <id> --service-name <name> --yes --dry-run`
2. 从 dry-run 输出中提取完整参数，用 AskUserQuestion 展示给用户，提供「确认部署」和「修改参数」两个选项：
   - 模型名称
   - 队列名称（ID）
   - 集群（zone）
   - GPU 卡型 × 数量
   - 服务名
3. 用户选择「修改参数」时，用 AskUserQuestion 列出可修改项让用户选择要改哪个，再提供对应的候选值
4. 用户确认后，去掉 `--dry-run` 正式执行：
   `qs deploy create --model-name <name> --zone <zone> --gpu-type <type> --queue-id <id> --service-name <name> --yes`
5. 创建成功后查看服务状态：`qs deploy get <service-name> --format json -q`

### 参数说明

| 参数 | 是否必填 | Agent 行为 |
|------|---------|-----------|
| `--model-name` | 必填 | 从用户输入提取或搜索确认 |
| `--queue-id` | 必填 | 自动选择有推理 quota 的队列 |
| `--zone` | 必填 | 自动选余量最大的集群 |
| `--gpu-type` | 必填 | 自动从 quota 结果中取 |
| `--gpu-num` | 可选 | CLI 自动推算，无需指定 |
| `--deploy-type` | 可选 | CLI 自动推断 |
| `--service-name` | 可选 | 自动生成或用户提供 |
| `--image` | 可选 | 指定后自动推断引擎类型 |
| `--model-version` | 可选 | 默认使用最新版本 |

### 创建示例

```bash
# 最简单机部署（GPU 数量和引擎类型均自动推断）
qs deploy create --model-name Qwen2.5-7B-Instruct --zone hssh-gpu-2 --gpu-type H20 --queue-id 41 --yes

# 多机分布式部署
qs deploy create --model-name DeepSeek-V3.2 --zone hssh-gpu-2 --gpu-type H20 --gpu-num 8 --deploy-type distributed --queue-id 41 --yes

# 指定镜像（引擎类型自动从镜像名推断）
qs deploy create --model-name Qwen2.5-7B-Instruct --zone hssh-gpu-2 --gpu-type H20 --queue-id 41 --image media/rllm:v1.0.0 --yes

# 指定服务名
qs deploy create --model-name Qwen2.5-7B-Instruct --zone hssh-gpu-2 --gpu-type H20 --queue-id 41 --service-name myapp-qwen25-7b --yes
```
