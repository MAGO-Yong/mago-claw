# 2026-W20 成长报告（2026-05-11 ~ 2026-05-17）

> 生成时间：2026-05-17 20:00 CST
> 数据来源：memory/2026-05-13.md, memory/2026-05-14.md, memory/self-improving.md, memory/corrections.md

---

## 📌 重点：本周最重要的事

**XRay AI 评估系统从「现状探查 → 高保真 Prototype → 真实前端升级」全链路推进，是本周最大产出。**

用户在 M2 窗口（5/12-5/25）重启密集执行，本周聚焦 AI 评估方向，完成了从理解现有系统到产出可落地前端样式的完整闭环。

---

## 📋 详情

### P0：XRay AI 评估系统

| 日期 | 事件 | 状态 |
|------|------|------|
| 5/13 17:32 | XRay AI 评估页面全面探查（5 个 TAB 逐个点击查看，含编辑抽屉和详情） | ✅ |
| 5/13 17:00 | XRay AI 应用评估封面图生成（Signal Silence 设计语言，v6 final） | ✅ |
| 5/13 19:00 | 高保真 Prototype v1 制作（NEX/Linear 极简风格，5 TAB + 多个抽屉） | ✅ |
| 5/13 19:17 | Prototype v2 迭代（顶部 TAB 导航替代 sidebar，完整子路由覆盖） | ✅ |
| 5/13 20:26 | 真实前端样式升级（数据集 TAB 5 个 Vue 文件，只改 `<style>`） | ✅ |
| 5/13 全天 | 需求管理系统建立（requirements.md + requirements-board.html，REQ-001 11 个子需求定级） | ✅ |

**关键数据（来自系统探查）：**
- 数据集 122 个版本，每天自动创建 `Sug 粗筛数据集`，549 条数据项/批
- 自动评估任务 2 个，sug粗筛 开启中，完成率 98.68%
- 评估实验 128 条，全部已完成
- 评估器 9 个（8 个 LLM + 1 个 HTTP）
- 得分分布：77% 为 0 分（粗筛有效过滤噪声）
- LLM Judge 评估成本：7126 token/条

### P1：开发环境与工具链

| 日期 | 事件 | 状态 |
|------|------|------|
| 5/13 晚 | formula-cli dev server 启动探索，确认容器环境无法运行（需 hosts 绑定 + 外网 CDN） | ✅ 确认限制 |
| 5/14 | LangChain Deep Agents HTML 文件加序号重命名 + 重新打包 | ✅ |
| 5/14 | claude-proxy + Claude Code 配置折腾（端口冲突、环境变量残留、credentials 优先级问题） | ⚠️ 部分解决 |
| 5/14 | LangChain 学习笔记收集机制建立（`langchain-learning-notes.md`） | ✅ 待用户学习 |

### P2：其他

| 日期 | 事件 | 状态 |
|------|------|------|
| 5/14 | 用户自写 OKR Skill 查找（本地/skills/memory/ClawHub 均未找到） | ⚠️ 未找到 |

---

## 🧬 我学到了什么

### 认知升级

1. **容器 dev server 的边界**：formula dev 依赖本地 hosts 绑定（`local.xiaohongshu.com:1391`）+ 公网 CDN（`fe-static.xhscdn.com`），容器环境两者都不满足。交付方式改为 patch 文件，通过 curl 下载应用到用户本地。这是「云端 Agent 帮本地开发」的标准交付模式。

2. **Proxy 端口冲突根因**：`.zshrc` 自动启动逻辑 + 手动 `proxy &` 同时跑，导致 `Address already in use`。Claude Code settings.json 中 credentials 优先级高于环境变量，需要先 `/logout` 再走 proxy。这些坑本质是「多层配置优先级」问题，不是 bug 而是设计选择。

3. **需求管理机制从对话到工具**：用户从「口头说需求」转向「Agent 维护结构化看板」，这是协作模式升级。requirements.md 作为数据源 + requirements-board.html 作为可视化 + localStorage 持久化状态，形成轻量但可操作的闭环。

### 规则新增

**交付模式：容器环境 → patch 文件 → 本地应用**
- 当 Agent 需要修改用户本地前端代码但无法在容器跑 dev server 时
- 生成 patch 文件 → 启动 HTTP 服务 → 用户在本地 `curl | git apply`
- 避免尝试在容器环境模拟本地开发环境（hosts/CDN/鉴权都不满足）

**Proxy 配置排查顺序**
- 1) 确认 proxy 在跑（`lsof -ti :8089`）
- 2) 确认环境变量 `ANTHROPIC_BASE_URL` 指向正确端口
- 3) 确认 Claude Code 已 `/logout` 清除本地 credentials
- 4) 再启动 Claude Code

### 错误与纠正

| 错误 | 纠正 | 根因 |
|------|------|------|
| formula dev server 在容器跑不起来，花了很多时间尝试 | 确认限制后改用 patch 交付 | 没有先评估环境依赖（hosts/CDN/鉴权）就盲目尝试 |
| claude-proxy 重复启动（zshrc 自动 + 手动） | 识别到端口冲突，kill 后单一起动 | zshrc 自动启动逻辑本身就有隐患 |
| 用户找自己的 OKR Skill 但找不到 | 全面搜索（本地 skills/MEMORY.md/work-log/ClawHub），确认丢失 | 可能从未保存为文件，或存在旧对话中未持久化 |

---

## 🔑 核心洞察

### 1. XRay AI 评估 = 数据飞轮正在运转

从系统探查数据看，sug 粗筛的数据飞轮已经完整运转：
```
在线链路 → 7% 采样 → LLM Judge 评估 → score ≥ 2 → 自动回流数据集 → 下一轮评估对比
```
- 每天稳定产出 537-617 条回流数据
- 122 个数据集版本，累计 4 个月
- 77% 得分为 0（有效过滤），23% 有价值数据自动沉淀

**意义**：这不是概念验证，是已经在跑的 production system。REQ-001 要做的是把它从 Langfuse 独立界面融合到 XRay/REDNA 统一平台，提升可用性和可管理性。

### 2. M2 窗口执行重启

M1 窗口（4/28-5/11）几乎零执行，用户 5/2-5/24 自驾旅行。5/12 M2 窗口开启后，用户 5/13 立即密集执行 AI 评估相关工作，说明：
- 用户对 AI 评估方向的优先级高于其他方向
- 假期后重新建立上下文的速度比预期快（5/13 就进入深度执行）
- Agent 整理的上下文（requirements.md/Prototype）有效降低了冷启动成本

### 3. Prototype 迭代模式验证

从探查 → v1（sidebar）→ v2（顶部 TAB）→ 真实前端升级，仅用 2 小时完成。关键因素：
- 用户提供了 NEX 参考页面（`nex.devops.xiaohongshu.com`）
- 反馈直接、具体（"太老、丑、不简洁"→ 改为 NEX 风格）
- Agent 有明确的设计参考，不是凭空创作
- **再次验证**：给参考 > 给选项 > 凭空创作

---

## 📊 本周 vs 上周对比

| 维度 | W19（假期周） | W20 |
|------|--------------|-----|
| 活跃天数 | 0 | 2（5/13, 5/14） |
| 核心产出 | 无 | Prototype v2 + 前端升级 + 需求管理 |
| 规则新增 | 0 | 2（patch 交付模式、proxy 排查顺序） |
| 错误纠正 | 0 | 3 |
| 待办推进 | 0 | REQ-001 子需求定级完成 |

---

## 📋 下周待跟进（W21 / 5/18-5/24）

### P0
- [ ] REQ-001-3 数据集上传功能开发（P0，待开发）
- [ ] XRay AI 评估其余 TAB 前端样式升级（自动评估/评估实验/评估器/LLM 配置，4 批待做）
- [ ] claude-proxy 最终确认 Claude Code 是否成功走 proxy（5/14 遗留问题）

### P1
- [ ] LangChain Deep Agents 学习开始（用户已拿到带序号的 12 个 HTML 文件）
- [ ] Trace 维度评估框架落文（5/15 讨论完成 5 维度体系，但未写正式文档）
- [ ] 用户 OKR Skill 文件尝试从旧对话/历史仓库找回

### P2
- [ ] XRay AI 评估封面图已知优化点（左侧底部空白、标签第二行偏空）
- [ ] 新项目 `mahengyang/obs-token` 流水线创建确认
- [ ] QS AutoFlow 合作方案 + 与小庄约讨论

### 跨周待办（持续跟踪）
- [ ] execute_tool Span 框架层采集现状确认（拖延 35 天+）
- [ ] 告警诊断需求文档 v0.6 与对话 v0.2 合并归档（拖延 35 天+）
- [ ] xray-log-query P0 SKILL 修复（拖延 35 天+）

---

*报告生成：OpenClaw Agent · 2026-05-17 20:00*
*下次周报：2026-W21（2026-05-24）*
