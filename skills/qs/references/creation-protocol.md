# Universal Creation Protocol (UCP)

所有创建类任务的标准执行流程。与 Module Profile（`profiles/*.yaml`）配合使用。

## 六步流程

### 1. EXTRACT — 意图解析

从用户自然语言中提取：

| 字段 | 说明 | 示例 |
|------|------|------|
| `module` | 目标模块 | training / deploy / eval / dataset / compress / batch-infer |
| `action` | 目标动作 | create / finetune |
| `explicit_params` | 用户明确给出的参数值 | model_name=Qwen3-8B |
| `intent_hints` | 隐含信息 | "测试用" → env=staging |
| `repeat_mode` | 复用上次配置 | "再来一次" / "跟上次一样" / "复用上次配置" |

### 2. LOAD — 加载模块档案

读取 `references/profiles/<module>.yaml`，获取 dependency_chain、inference_rules、queries、selection、defaults、memory_keys。

### 3. RESOLVE — 参数解析

按 dependency_chain 有序逐个解析。每个参数按六级优先级尝试：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| ① explicit | 用户输入 | 用户在自然语言中明确给出的值 |
| ② infer | 推理 | 从已解析参数推导（规则在 Profile.inference_rules） |
| ③ memory | 记忆 | `qs memory list --format json` 读最近使用值，需 query 验证仍有效 |
| ④ query | 查询 | 运行 Profile.queries 中的 CLI 命令，按 Profile.selection 选最优 |
| ⑤ default | 默认 | Profile.defaults 中的固定值 |
| ⑥ ask | 询问 | 最后手段。AskUserQuestion 必须带推荐选项和理由 |

**repeat_mode**：检测到复用意图时，从 memory 批量加载上次成功的模块完整配置，只覆盖用户显式修改的参数，其余走 query 验证后直接用。

**多候选选择策略**：

| 场景 | 策略 |
|------|------|
| 多个队列 | 选可用 GPU 最多的 |
| 多个模型版本 | 选最新版本 |
| 多个 zone | 选配额剩余最多的 |
| 多个集群 | 选与目标 cloud 匹配且资源最充足的 |
| 名称搜索多匹配 | 精确匹配优先；无精确匹配 → ask（真歧义） |

### 4. PREVIEW — 执行确认

展示完整方案表格。每个参数标注来源：

```
准备用这组参数提交：
• model: Qwen3-8B v1.2 [用户指定]
• gpu_type: H20 [推理: 从 deploy options 推荐]
• gpu_num: 2 [推理: 从 deploy options 推荐]
• zone: zone-a [查询: 配额剩余最多]
• queue: gpu-queue-01 [记忆: 上次使用]
• service_name: qwen3-8b-infer-20260507 [默认: 自动生成]

将执行：qs deploy create --model-id 123 --model-version 456 ...

要改哪项？不改就说 go。
```

Preview 是必须步骤，即使零提问也要展示。这是自主与失控之间的安全边界。

### 5. EXECUTE — 执行

1. 拼装完整 CLI 命令（所有 flag 显式填写 + `--yes`）
2. 执行并返回结果 + 平台链接
3. Memory 由 CLI 自动写入

### 6. RECOVER — 失败恢复

| 错误类型 | 识别 | 处置 |
|---------|------|------|
| 网络/5xx | timeout / 500-599 | 自动重试一次 |
| 参数错误 | 4xx + 字段报错 | 回到 RESOLVE 重新解析出错参数 |
| 名称冲突 | 409 / "already exists" | 换名后重新 EXECUTE |
| 配额不足 | "quota" / "资源不足" | 告知用户 + 给出 `qs maas quota` 和申请链接 |
| 认证失败 | 401 / 403 | 提示 `qs config set` 重新配置 |
| 未知 | 其他 | 原样透传 stdout + stderr，不自动重试 |

## 反模式（严禁）

- **试错式执行**：绝对不要在 RESOLVE 完成前执行 create/delete/scale/sync 等写操作。"先跑 CLI 看报什么错再补参数"是错误做法——必须先 RESOLVE 所有参数、过 PREVIEW、用户确认后才 EXECUTE
- **跳过 PREVIEW**：即使所有参数已 resolve，也必须展示方案表格让用户确认。不展示就执行 = 失控
- **RESOLVE 阶段有答案却问用户**：Profile 的 selection 规则给出了自动选择策略（如"选使用率最低的集群"），就不应该 fallthrough 到 ask。只有 selection 规则无法覆盖的真歧义才 ask
- **遗漏 required 参数**：Profile.required_for_noninteractive 列出了所有必填 flag。RESOLVE 必须覆盖每一个，不能"执行时才发现缺了"

## 约定

- 所有 CLI 查询加 `--format json -q` 获取结构化输出
- 优先用 id 而非 name 传参，避免名字歧义
- RESOLVE 阶段只允许读操作（docs、list、options、clusters 等查询命令）
- RESOLVE 中发现缺少 CLI 子命令能力时，降级到 ask
- EXECUTE 阶段才执行写操作（create/delete/scale/sync），且命令必须包含所有 required flag + `--yes`
