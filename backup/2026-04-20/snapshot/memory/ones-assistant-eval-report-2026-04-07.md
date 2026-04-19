# ones-assistant SKILL 评估报告

## 1. 文档目标

评估 `ones-assistant` SKILL 在 Claw Agent（当前对话窗口）中的表现，覆盖四层评估维度：Agent Native 合规、意图识别、Skill 选择、推理过程、结果完整性、结果准确性、交付体验、响应速度。

| 维度 | 层级 | 说明 |
|------|------|------|
| Agent Native 合规 | SKILL 设计 | SKILL 是否符合被 Agent 调用的工程标准 |
| 响应速度 | Trajectory | 整体完成耗时，是否超时 |
| 意图识别 | Outcome | 是否正确理解用户问题与对象类型 |
| Skill 选择 | Tool Call | 是否命中正确子命令，是否误调或漏调 |
| 推理过程 | Trajectory | 调用顺序是否合理，是否能逐步收敛 |
| 结果完整性 | Outcome | 是否覆盖关键字段、证据和结论 |
| 结果准确性 | Outcome | 对象、数据、归因、结论是否正确 |
| 交付体验 | Outcome | 输出是否清晰，异常处理是否自然 |

## 2. 评估对象范围

- **被评估 SKILL**：`ones-assistant`（ClawHub 安装版）
- **Agent 接入点**：当前 Claw 对话窗口
- **测试服务**：`xrayaiagent-service-default`（应用 `xrayaiagent`）
- **评估时间**：2026-04-07
- **Trajectory 置信度**：⏳ 低（AI trace SKILL 待接入，Skill选择/推理过程基于执行结果推断）

## 3. 评估用例设计原则

| 原则 | 说明 |
|------|------|
| 真实对象 | 测试数据来自真实服务，数据均可查 |
| 用户视角 | 题面贴近真实用户表述，不暴露 SKILL 内部参数 |
| 分层设计 | 分为标准场景（S）、边界场景（B）、组合场景（C）三类，另含 Agent Native 错误触发题（AN-E） |
| 只读安全 | 所有题目均为查询类操作，无真实发布/删除等写操作 |

## 4. Agent Native 审计结果

> 评估 SKILL 设计是否符合被 Agent 调用的工程标准。参考：https://docs.xiaohongshu.com/doc/bc1245f5e7da715fda366d8787a9c0ca

### 4.1 综合判定

| 指标 | 得分 |
|------|------|
| 静态审计总分 | 7.5 / 12.0 |
| 归一化得分 | **6.25 / 10.0** |
| 动态验证（AN-E1） | 0 / 2.0 |
| **最终判定** | **ANP ⚠️（Agent Native Partial）** |

### 4.2 各子项明细

| 编号 | 子项 | 级别 | 得分 | 满分 | 问题描述 |
|------|------|------|------|------|---------|
| AN-1 | 结构化错误返回 | 🔴 P0 | 0 | 2.0 | 错误时输出裸 stderr 文本（`[ERROR] HTTP 500 [get_service_info]: ...`），动态验证确认：嵌套 JSON 错误原文，Agent 无法机器处理 |
| AN-2 | 时间参数格式统一 | 🔴 P0 | 2 | 2.0 | 该 SKILL 无时间参数，N/A 满分 ✅ |
| AN-3 | SKILL_DIR 注入方式 | 🔴 P0 | 1.5 | 2.0 | 使用相对路径 `scripts/ones_deploy.py`，存在工作目录隐式依赖风险 |
| AN-4 | 路由决策是否自持 | 🟠 P1 | 1.5 | 1.5 | description 触发场景明确，无多余路由说明 ✅ |
| AN-5 | 输出格式是否标准化 | 🟠 P1 | 1.0 | 1.5 | 直接透传 ones API 原始 data，字段结构随接口各异，无统一 wrapper schema |
| AN-6 | 功能边界是否清晰 | 🟠 P1 | 1.0 | 1.0 | 明确列出10个场景，声明不支持 shadow 发布 ✅ |
| AN-7 | 输出置信度/元信息 | 🟡 P2 | 0 | 0.5 | 无操作时间戳、耗时等元信息 |
| AN-8 | SKILL 间编排协议 | 🟡 P2 | 0 | 0.5 | 内部编排链 my-services→images→changeflows→deploy 未在 metadata 声明 |
| AN-9 | 无交互式人机依赖 | 🟡 P2 | 0.5 | 1.0 | deploy 子命令默认有 stdin 阻塞，虽有 `--yes` 兜底但默认路径存在交互依赖 |

### 4.3 动态验证：AN-E1（错误路径触发）

- **Query**：`帮我查一下 nonexistent-service-xyz 这个服务的部署组信息`
- **Agent 回复摘要**：返回裸 stderr 文本：`[ERROR] HTTP 500 [get_service_info]: {"code":1,"data":null,"message":"tool execution failed: ... \"nonexistent\" not found ... ErrNotFound"}`
- **验证结论**：Agent 收到嵌套 JSON 错误原文，无 error_code / action / retry 等机器可读字段，无法自主判断下一步操作
- **得分**：0 / 2.0

### 4.4 Agent Native 改造建议

| 优先级 | 子项 | 问题 | 具体改造建议 |
|--------|------|------|------------|
| P0 | AN-1 | 错误返回裸 stderr 文本 | except 块统一改为 stdout JSON：`{"error_code": "SERVICE_NOT_FOUND", "action": "call_my-services", "retry": false, "message": "..."}` |
| P1 | AN-5 | 输出无统一 wrapper schema | 增加 meta wrapper：`{"success": true, "data": ..., "meta": {"subcommand": "...", "timestamp": "..."}}` |
| P2 | AN-8 | 编排链未声明 | metadata 增加 `output_to` / `input_from` 编排协议声明 |
| P2 | AN-9 | deploy 交互依赖 | 文档明确说明 Agent 自动化链路需传 `--yes`，或增加 `deploy-preview` 干跑子命令 |

## 5. 实测评估结果（Agent 运行表现）

### 5.1 综合评分汇总

| 类型 | 有效用例数 | 均分 | 最高 | 最低 | 主要短板 |
|------|-----------|------|------|------|---------|
| S（标准场景） | 5 | **5.0/5** | S1-S5 全满分 | — | 无 |
| B（边界场景） | 3 | **4.8/5** | B1/B2 满分 | B3(4.3) | 空结果无引导元信息 |
| C（组合场景） | 2 | **5.0/5** | C1/C2 满分 | — | 无 |
| **全量均分** | **10** | **4.9/5.0** | — | B3(4.3) | **空结果处理依赖 Agent 自行补充引导** |

### 5.2 实测数据汇总

| 用例 | 类型 | 题面（关键词） | 耗时 | AI Trace | 综合评分 | 备注 |
|------|------|--------------|------|----------|----------|------|
| S1 | 标准 | 查权限服务列表 | ~2s | ⏳ 待补充 | **5.0/5** | 200个服务完整返回 |
| S2 | 标准 | 查部署组 | ~1s | ⏳ 待补充 | **5.0/5** | 4个部署组字段完整 |
| S3 | 标准 | 查镜像版本 | ~1s | ⏳ 待补充 | **5.0/5** | 10个镜像按时间倒序 |
| S4 | 标准 | 查发布模板 | ~1s | ⏳ 待补充 | **5.0/5** | sit/staging 模板完整 |
| S5 | 标准 | 查应用发布记录 | ~1s | ⏳ 待补充 | **5.0/5** | 正确传 appName，2条回滚记录 |
| B1 | 边界 | 查 pod 状态（缺部署组） | ~2s | ⏳ 待补充 | **5.0/5** | 先查 service-info 获取部署组列表，再追问 |
| B2 | 边界 | 查发布详情（直传 changeflowName） | ~1s | ⏳ 待补充 | **5.0/5** | 正确识别并调用 deploy-info，含 ones 链接 |
| B3 | 边界 | 查发布历史（不存在的 tag） | ~1s | ⏳ 待补充 | **4.3/5** | 空结果无引导，靠 Agent 自行补充 |
| C1 | 组合 | staging 发布前准备（仅查询） | ~4s | ⏳ 待补充 | **5.0/5** | changeflows→images→check 三步编排，未触发 deploy |
| C2 | 组合 | sit pod 状态 + 异常分析 | ~2s | ⏳ 待补充 | **5.0/5** | 发现 OOMKilled（重启50/42次），正确判断跳过 diagnose |

### 5.3 分布统计

| 评分区间 | 用例数 | 用例 |
|---------|-------|------|
| 5/5（优秀） | 9 | S1、S2、S3、S4、S5、B1、B2、C1、C2 |
| 4-4.5/5（良好） | 1 | B3 |
| 3-3.5/5（及格） | 0 | — |
| < 3/5（偏低） | 0 | — |

### 5.4 关键发现

<redoc-highlight emoji="zan" fillColor="blue">
**正向发现：标准场景全满分** — S1-S5 共5题全部 5.0/5，SKILL 对核心查询场景封装质量高，参数提取准确，输出结构清晰，基础盘扎实。
</redoc-highlight>

<redoc-highlight emoji="zan" fillColor="blue">
**正向发现：组合编排能力强** — C1 三步查询链（changeflows→images→check）一次编排完成；C2 发现 OOMKilled 异常后正确判断无 changeflowName 可用，跳过 diagnose，推理逻辑严密。
</redoc-highlight>

<redoc-highlight emoji="tuding" fillColor="yellow">
**[P1 问题] B3 空结果处理薄弱** — `deploy-history` 返回空数组时，SKILL 无任何引导元信息（如 `"hint": "尝试去掉 --image-tag 查全量"`），Agent 需自行识别并补充引导，增加推理负担，影响用户体验。
</redoc-highlight>

<redoc-highlight emoji="tuding" fillColor="red">
**[真实问题发现] C2 暴露 OOM 问题** — `xrayaiagent-service-default` 的 sit 环境两个 Pod 均有 OOMKilled 历史，重启次数分别高达 **50 次和 42 次**，内存限制 800Mi 疑似不足，建议关注并调整资源配置。
</redoc-highlight>

### 5.5 各题详情

---

#### ✅ S1（标准场景）— 5.0/5.0

**Query**：`帮我查一下我有权限的服务列表`
**耗时**：~2s | **AI Trace**：⏳ 待补充

**回答摘要**：正确调用 my-services，返回200个服务，涵盖 xrayaiagent-* 和 allin-* 系列，角色均为研发。

**✅ 亮点**：
- 正确识别意图为权限服务查询，直接调用 my-services，无额外参数干扰
- 返回完整列表，结构清晰

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ S2（标准场景）— 5.0/5.0

**Query**：`xrayaiagent-service-default 这个服务有哪些部署组？`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：共4个部署组：sit(qcsh-sit) / prod(qcsh4-2) / staging(qcsh4-2, qcsh4-new)，字段完整。

**✅ 亮点**：
- 正确从自然语言提取服务名 `xrayaiagent-service-default`
- 返回 cluster / env / name 三字段完整，覆盖所有环境

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ S3（标准场景）— 5.0/5.0

**Query**：`帮我看看 xrayaiagent-service-default 有哪些可以发布的镜像版本`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：返回10个镜像，最新为 `feature-skill_hub-b5329129-202603271454-jdk21`（2026-03-27），均标注 canPublish=true，按时间倒序。

**✅ 亮点**：
- 正确识别"可发布的镜像版本"→ images 子命令
- 镜像列表含 name / createTime / canPublish，信息完整

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ S4（标准场景）— 5.0/5.0

**Query**：`xrayaiagent-service-default 有哪些发布流程模板？`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：2个模板：「发布sit环境」(changeflowName=sit，1个部署组) 和「发布staging环境」(changeflowName=staging，2个部署组)。

**✅ 亮点**：
- changeflowAlias / changeflowName / workloadGroups 三字段完整
- 两个模板全部返回，无遗漏

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ S5（标准场景）— 5.0/5.0

**Query**：`帮我查一下 xrayaiagent 应用下我最近的发布记录`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：正确传入 appName=xrayaiagent，返回2条发布记录，均为回滚操作（2025-08-23 16:55/16:47），操作人 zhengyi1，状态 Finish。

**✅ 亮点**：
- 正确区分 my-changeflows（全量）vs my-changeflows-by-app（按应用），选择后者
- 包含 changeflowName / createdAt / pipelineRunStatus / operator 等关键字段

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ B1（边界场景）— 5.0/5.0

**Query**：`帮我查一下 xrayaiagent-service-default 的 pod 状态`
**耗时**：~2s | **AI Trace**：⏳ 待补充

**回答摘要**：缺少 workload-group 参数时，Agent 先调用 service-info 获取部署组列表，展示4个部署组后追问用户要查哪个环境，未盲目猜测参数。

**✅ 亮点**：
- 边界处理正确：缺参数→先查依赖数据→追问，而非参数幻觉
- 调用路径：service-info → 展示列表 → 追问，逻辑清晰

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ B2（边界场景）— 5.0/5.0

**Query**：`查一下 xrayaiagent-rollback-1755939308 这个发布的详情`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：正确识别 changeflowName 并调用 deploy-info，返回完整回滚详情：sit 环境、2025-08-23 16:55 完成、含 ones 平台链接、childApplications 包含回滚 tag。

**✅ 亮点**：
- 直接从自然语言提取 changeflowName，无参数错误
- 返回 link 字段提供 ones 平台直达链接，交付体验好

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ⚠️ B3（边界场景）— 4.3/5.0

**Query**：`帮我看看 xrayaiagent-service-default sit 环境的发布历史，tag 是 abc-not-exist`
**耗时**：~1s | **AI Trace**：⏳ 待补充

**回答摘要**：正确调用 deploy-history 并传入 --image-tag=abc-not-exist，返回空数组。SKILL 对空结果无任何元信息或引导，Agent 需自行补充"建议去掉 tag 过滤查全量"。

**❌ 问题**：
- SKILL 空结果时只返回裸 `{"data": []}`，无 hint / suggestion 字段
- **SKILL 归因**：`cmd_deploy_history` 函数在 data 为空列表时直接 `print_json(data)`，缺少空结果后处理逻辑，Agent 需额外推理才能给出有意义引导

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 0.5 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.2 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **5.2** | **6.0** |

---

#### ✅ C1（组合场景）— 5.0/5.0

**Query**：`我想把 xrayaiagent-service-default 发到 staging，帮我查清楚需要哪些信息（不用真的发）`
**耗时**：~4s | **AI Trace**：⏳ 待补充

**回答摘要**：完整执行三步查询链：changeflows（获取 staging 模板）→ images（获取可用 tag，最新为 2026-03-27）→ check（两个 staging 部署组均 canDeploy），汇总发布所需信息，未触发 deploy。

**✅ 亮点**：
- 正确理解"仅查询，不真的发"的意图约束
- 三步编排逻辑顺序正确：模板→镜像→状态校验
- 汇总结果结构清晰，直接给出"确认好 tag 后可发布"的引导

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

#### ✅ C2（组合场景）— 5.0/5.0

**Query**：`xrayaiagent-service-default 的 sit 环境 pod 状态怎么样？如果有异常帮我分析下`
**耗时**：~2s | **AI Trace**：⏳ 待补充

**回答摘要**：调用 pod-info 发现2个 Pod 均有 OOMKilled 历史（重启50/42次），podDiagnosticInfo 包含 OOMKilled 原因和建议。由于无关联 changeflowName，正确跳过 diagnose 子命令。

**✅ 亮点**：
- SKILL 的 podDiagnosticInfo 字段结构化完整（reason / message / type），Agent 可直接解读
- 有异常→尝试 diagnose→判断无 changeflowName→跳过，推理链正确
- 发现真实 OOM 问题，具有实际诊断价值

**分项得分**：

| 维度 | 得分 | 满分 |
|------|------|------|
| 意图识别 | 1.0 | 1.0 |
| Skill 选择 | 1.0 | 1.0 |
| 推理过程 | 1.0 | 1.0 |
| 结果完整性 | 1.0 | 1.0 |
| 结果准确性 | 1.0 | 1.0 |
| 交付体验 | 0.5 | 0.5 |
| 响应速度 | 0.5 | 0.5 |
| **合计** | **6.0** | **6.0** |

---

## 6. 综合优化建议

| 优先级 | 来源 | 问题现象 | SKILL 根因 | 修改建议 |
|--------|------|---------|-----------|---------|
| P0 | Agent Native | 错误时 Agent 收到裸 stderr，无法机器处理 | AN-1：except 块用 `print_error(str(e))` 输出文本 | 统一改为 stdout JSON：`{"error_code": "SERVICE_NOT_FOUND", "action": "call_my-services", "retry": false, "message": "..."}` |
| P1 | 运行表现 | 空结果无引导，B3 用户体验差 | cmd_deploy_history 等命令空数组时无 hint | 空结果时增加 hint 字段：`{"data": [], "hint": "未找到记录，建议去掉 --image-tag 参数查全量"}` |
| P1 | Agent Native | 输出无统一 wrapper schema | AN-5：各接口直透 ones API data | 增加统一 meta wrapper，含 subcommand / timestamp |
| P2 | Agent Native | 内部编排链未声明 | AN-8：metadata 无 input_from/output_to | metadata 增加编排协议声明，辅助 Agent 自动编排 |
| P2 | Agent Native | deploy 默认路径有 stdin 阻塞 | AN-9：input() 等待用户输入 | 文档明示 Agent 自动化链路需传 `--yes`，或增加 deploy-preview 干跑子命令 |

## 7. 评估用例（附录）

| 编号 | 类型 | 题面 | 关键考察点 |
|------|------|------|-----------|
| AN-E1 | 错误触发 | 查 nonexistent-service-xyz 的部署组信息 | 结构化错误返回 + Agent 错误处理 |
| S1 | 标准 | 查权限服务列表 | my-services 基础查询 |
| S2 | 标准 | 查 xrayaiagent-service-default 部署组 | service-info，参数提取 |
| S3 | 标准 | 查可发布镜像版本 | images，意图识别 |
| S4 | 标准 | 查发布流程模板 | changeflows，结果完整性 |
| S5 | 标准 | 查 xrayaiagent 应用发布记录 | my-changeflows-by-app，参数提取 |
| B1 | 边界 | 查 pod 状态（缺部署组） | 缺参数时先查依赖数据再追问 |
| B2 | 边界 | 查 xrayaiagent-rollback-1755939308 发布详情 | 直接传 changeflowName，deploy-info |
| B3 | 边界 | 查 sit 发布历史，tag=abc-not-exist | 空结果处理，引导说明 |
| C1 | 组合 | staging 发布前信息查询（不真发） | changeflows→images→check 编排链 |
| C2 | 组合 | sit pod 状态 + 异常分析 | pod-info + 条件触发 diagnose |
