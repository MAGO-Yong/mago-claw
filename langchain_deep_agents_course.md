# LangChain Deep Agents 入门课

> 学习来源：https://docs.langchain.com/oss/python/deepagents/overview
> 整理时间：2026-04-19

---

## 一、什么是 Deep Agents

Deep Agents 是 LangChain 推出的**开源深度智能体框架**，核心定位：让 AI Agent 能**自主完成复杂、多步骤任务**，而不仅仅是简单问答。

### 1.1 核心哲学：Context Engineering（上下文工程）

Deep Agents 的设计核心不是"给 Agent 更多工具"，而是**管理 Agent 看到的上下文**。关键原则：

- **渐进式披露（Progressive Disclosure）**：Agent 启动时只看到精简的系统提示，需要时才加载完整文档/Skill
- **上下文隔离**：子 Agent 的工作不会污染主 Agent 的上下文
- **自动压缩**：长对话自动总结，释放上下文窗口空间

### 1.2 Harness（智能体框架）的 7 大核心能力

| 能力 | 说明 |
|------|------|
| **任务规划** | `write_todos` 工具，Agent 自动维护任务清单（pending/in_progress/completed） |
| **虚拟文件系统** | ls/read_file/write_file/edit_file/glob/grep，支持多模态文件（图片/视频/音频/PDF） |
| **文件系统权限** | 声明式权限规则（allow/deny + glob 路径），首次匹配原则 |
| **任务委派（子Agent）** | `task` 工具，主 Agent 可创建临时子 Agent 并行执行 |
| **上下文管理** | 自动压缩/卸载/隔离，支持超长任务 |
| **代码执行** | 沙箱内执行 shell 命令，隔离环境 |
| **人在回路** | 敏感操作暂停等待人工审批 |

---

## 二、快速上手

### 2.1 SDK 方式（Python）

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful assistant",
)
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Create a snake game in Python"}]}
)
```

### 2.2 CLI 方式（终端）

```bash
# 安装
curl -LsSf https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/main/libs/cli/scripts/install.sh | bash

# 设置 API Key
export ANTHROPIC_API_KEY="your-key"

# 运行
deepagents
```

### 2.3 CLI 内置工具

| 工具 | 说明 | 需审批 |
|------|------|--------|
| `ls` | 列出目录 | - |
| `read_file` | 读文件（支持多模态） | - |
| `write_file` | 写文件 | ✅ |
| `edit_file` | 精准编辑 | ✅ |
| `execute` | 执行 shell 命令 | ✅ |
| `web_search` | 网络搜索（Tavily） | ✅ |
| `fetch_url` | 获取网页转 markdown | ✅ |
| `task` | 委派给子 Agent | ✅ |
| `compact_conversation` | 压缩对话释放上下文 | ✅ |
| `write_todos` | 任务清单管理 | - |

### 2.4 CLI Slash 命令

- `/model` — 切换模型
- `/remember` — 审查对话并更新记忆
- `/skill:<name>` — 直接调用技能
- `/offload` — 卸载消息到存储
- `/tokens` — 查看 token 使用
- `/threads` — 浏览历史对话
- `/mcp` — 查看 MCP 服务器
- `/trace` — 在 LangSmith 中打开当前线程

---

## 三、模型支持

### 3.1 支持的模型提供商

| 提供商 | 推荐模型 | 特点 |
|--------|---------|------|
| **Anthropic** | claude-sonnet-4-6 | 最大上下文（200K），最强推理 |
| **OpenAI** | gpt-5.2 / gpt-5-codex | 快速，编码优化 |
| **Google** | gemini-3.1-pro-preview | 最大上下文（200K），成本更低 |
| **Bedrock** | claude-sonnet-4-6 / nova-pro | 企业合规 |
| **Azure** | gpt-5.2 | 企业合规 |

### 3.2 模型选择指南

| 场景 | 推荐 |
|------|------|
| 默认 | `anthropic:claude-sonnet-4-6` |
| 需要 200K 上下文 | `google_genai:gemini-3.1-pro-preview` |
| 需要快速响应 | `openai:gpt-5.2` |
| 编码任务 | `openai:gpt-5-codex` |
| 企业合规 | `bedrock:anthropic.claude-sonnet-4-6` |
| 成本控制 | `openai:gpt-5-nano` |

---

## 四、上下文工程（核心）

### 4.1 上下文窗口管理

| 技术 | 说明 |
|------|------|
| **渐进式披露** | 启动时只加载精简提示，按需加载完整内容 |
| **子Agent隔离** | 重型工作隔离到子Agent，主Agent只收到结果 |
| **自动卸载** | Token 超阈值时自动压缩对话 |
| **对话压缩** | `compact_conversation` 工具手动触发 |

### 4.2 渐进式披露的三层

1. **系统提示** — 启动时加载（精简指令）
2. **Skills** — 按需加载（启动时只读 frontmatter 描述，匹配时才读全文）
3. **Memory** — 始终加载（持久化上下文）

---

## 五、子Agent（Subagents）

### 5.1 为什么需要子Agent？

解决**上下文膨胀问题**。当 Agent 使用大量工具（搜索/读文件/查询数据库），上下文窗口很快被中间结果填满。子Agent 隔离这些工作——主Agent 只收到最终结果。

### 5.2 同步子Agent

```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    "model": "openai:gpt-5.2",  # 可选，覆盖主Agent模型
}
```

### 5.3 异步子Agent（v0.5.0 预览）

| 维度 | 同步子Agent | 异步子Agent |
|------|------------|------------|
| 执行模型 | 主Agent 阻塞等待 | 立即返回，主Agent 继续 |
| 并发 | 并行但阻塞 | 并行且非阻塞 |
| 中途更新 | 不支持 | 支持 `update_async_task` |
| 取消 | 不支持 | 支持 `cancel_async_task` |
| 状态 | 无状态 | 有状态 |

### 5.4 子Agent 配置项

| 字段 | 说明 | 继承 |
|------|------|------|
| `name` | 唯一标识 | - |
| `description` | 描述，主Agent据此决定何时委派 | - |
| `system_prompt` | 子Agent指令 | 不继承 |
| `tools` | 可用工具 | 不继承（覆盖） |
| `model` | 模型 | 继承主Agent |
| `skills` | 技能集 | 不继承 |
| `permissions` | 文件权限 | 继承主Agent（可覆盖） |

---

## 六、Memory（持久化记忆）

### 6.1 记忆维度

| 维度 | 问题 | 选项 |
|------|------|------|
| **持续时间** | 持续多久？ | 短期（单次对话）/ 长期（跨对话） |
| **信息类型** | 什么类型？ | 情景记忆（经验）/ 程序记忆（技能）/ 语义记忆（事实） |
| **范围** | 谁能看到？ | 用户级 / Agent级 / 组织级 |
| **更新策略** | 何时写入？ | 对话中（默认）/ 对话间（后台合并） |
| **检索方式** | 如何读取？ | 加载到提示词 / 按需读取（Skills） |
| **权限** | 能写吗？ | 读写（默认）/ 只读 |

### 6.2 Agent 级记忆（共享）

所有用户共享同一份记忆文件，Agent 积累知识和偏好。

```python
backend=CompositeBackend(
    routes={
        "/memories/": StoreBackend(
            namespace=lambda rt: (rt.server_info.assistant_id,),
        ),
    },
)
```

### 6.3 用户级记忆（隔离）

每个用户独立的记忆，用户A的偏好不会泄漏到用户B。

```python
backend=CompositeBackend(
    routes={
        "/memories/": StoreBackend(
            namespace=lambda rt: (rt.server_info.user.identity,),
        ),
    },
)
```

### 6.4 情景记忆

通过 `checkpointer` 持久化每次对话线程，Agent 可以搜索过去的对话来复现解决方案。

---

## 七、Skills（技能）

### 7.1 什么是 Skill

遵循 [Agent Skills 标准](https://agentskills.io/)，每个 Skill 是一个目录，包含 `SKILL.md` 文件和可选的脚本/模板/参考文档。

### 7.2 渐进式加载

1. **启动时**：只读每个 SKILL.md 的 frontmatter（名称+描述）
2. **匹配时**：Agent 认为当前任务需要某个 Skill，才加载完整内容
3. **执行时**：Skill 目录下的所有资源可用

### 7.3 Skill 目录结构

```
skills/
├── code-review/
│   └── SKILL.md
├── data-analysis/
│   ├── SKILL.md
│   └── templates/
└── web-research/
    ├── SKILL.md
    └── scripts/
```

### 7.4 SKILL.md 格式

```markdown
---
name: code-review
description: Review code for quality and consistency
---

# Code Review

Instructions for the skill...
```

---

## 八、沙箱（Sandboxes）

### 8.1 支持的沙箱提供商

| 提供商 | 特点 |
|--------|------|
| **LangSmith** | 零配置，与 LangSmith 生态集成 |
| **Daytona** | 快速启动，可配置环境 |
| **Modal** | GPU 支持，弹性扩展 |
| **Runloop** | 高性能，自定义镜像 |

### 8.2 文件传输

- `upload_file(source, dest)` — 上传到沙箱
- `download_file(source, dest)` — 从沙箱下载

---

## 九、权限系统

### 9.1 声明式权限规则

```python
permissions=[
    {"operations": ["read", "write"], "paths": ["/workspace/**"], "mode": "allow"},
    {"operations": ["write"], "paths": ["/workspace/src/important/**"], "mode": "deny"},
    {"operations": ["read", "write"], "paths": [".env", "**/.env"], "mode": "deny"},
]
```

- **首次匹配原则**：第一条匹配的规则生效
- **默认放行**：没有匹配的规则时允许操作

### 9.2 子Agent 权限继承

- 默认继承父Agent 权限
- 可通过 `permissions` 字段完全覆盖

---

## 十、人在回路（Human-in-the-loop）

### 10.1 配置方式

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    interrupt_on={
        "edit_file": True,         # 每次编辑前暂停
        "execute": {"approve": True, "reason": "执行命令"},
    },
)
```

### 10.2 交互方式

- 用户输入 `y` 批准
- 用户输入 `n` 拒绝
- 用户输入消息修改工具输入
- 用户可以要求解释

---

## 十一、后端（Backends）

| 后端类型 | 用途 |
|----------|------|
| **StateBackend** | 对话状态（短期记忆） |
| **StoreBackend** | 持久化存储（记忆/Skills） |
| **FilesystemBackend** | 本地文件系统 |
| **CompositeBackend** | 组合多个后端，按路径路由 |

---

## 十二、部署（Deploy）

### 12.1 项目结构

```
my-agent/
├── deepagents.toml       # Agent配置
├── AGENTS.md             # 系统提示
├── .env                  # API Key
├── mcp.json              # MCP服务器配置
├── skills/               # 技能目录
│   ├── code-review/SKILL.md
│   └── data-analysis/SKILL.md
├── subagents/            # 子Agent目录
│   └── researcher/
│       ├── deepagents.toml
│       └── AGENTS.md
└── user/                 # 用户级记忆
    └── AGENTS.md
```

### 12.2 部署命令

```bash
deepagents init my-agent          # 初始化项目
deepagents dev                    # 本地开发
deepagents deploy                 # 部署到 LangSmith
```

### 12.3 对比 Claude Managed Agents

| 特性 | Deep Agents | Claude Managed Agents |
|------|------------|----------------------|
| 模型 | 多提供商 | 仅 Anthropic |
| Harness | 开源（MIT） | 闭源 |
| 沙箱 | 多提供商 | 内置 |
| MCP | ✅ | ✅ |
| Skills | ✅ | ✅ |
| AGENTS.md | ✅ | ❌ |
| Agent端点 | MCP/A2A/Agent Protocol | 专有 |
| 自托管 | ✅ | ❌ |

---

## 十三、ACP（Agent Client Protocol）

### 13.1 什么是 ACP

标准化的 Agent-编辑器通信协议，让 Deep Agent 可以在 IDE 中运行。

### 13.2 支持的客户端

- **Zed** — 原生支持
- **JetBrains** — 通过 ACP 插件
- **VS Code** — 通过 vscode-acp 插件
- **Neovim** — 通过 ACP 兼容插件

### 13.3 与 MCP 的区别

| 协议 | 用途 |
|------|------|
| **ACP** | Agent 与 IDE/编辑器通信 |
| **MCP** | Agent 调用外部服务器工具 |

---

## 十四、与 OpenClaw 的对比

### 14.1 架构对比

| 维度 | Deep Agents | OpenClaw |
|------|------------|----------|
| 定位 | 单Agent框架 | 多Agent平台 |
| 子Agent | 同步/异步子Agent | sessions_spawn 多Agent |
| 记忆 | 文件系统+后端存储 | MEMORY.md + memory/*.md |
| 技能 | SKILL.md (agentskills.io) | SKILL.md (自有格式) |
| 部署 | LangSmith | 自建Gateway |
| 协议 | MCP/A2A/ACP/Agent Protocol | 自有 + MCP |
| 人在回路 | 工具级审批 | 审批模式 |
| 定时任务 | 无 | Cron + Heartbeat |
| 通知 | 无 | Hi/Telegram/Discord等 |

### 14.2 可借鉴的设计

1. **Context Engineering 哲学** — 管理上下文比堆工具更重要
2. **渐进式披露** — 启动只加载精简内容，按需加载详细
3. **子Agent上下文隔离** — 解决主Agent上下文膨胀
4. **声明式权限** — 首次匹配原则的权限规则
5. **异步子Agent** — 非阻塞并行任务
6. **记忆维度框架** — 6维度记忆分类（持续时间/类型/范围/更新策略/检索/权限）
7. **后台记忆合并** — 对话间自动总结更新记忆
8. **情景记忆** — 搜索历史对话复现解决方案

---

## 十五、关键概念总结

| 概念 | 一句话解释 |
|------|-----------|
| **Deep Agent** | 能自主完成复杂多步骤任务的AI智能体 |
| **Harness** | 赋予Agent规划/文件/权限/委派/上下文/执行/人在回路能力的框架 |
| **Context Engineering** | 管理Agent看到的上下文，而非堆砌内容 |
| **Progressive Disclosure** | 按需加载信息，启动时保持精简 |
| **Subagent** | 主Agent创建的临时Agent，用于隔离工作和并行执行 |
| **Async Subagent** | 非阻塞子Agent，主Agent可继续交互 |
| **Skill** | 可复用的专业知识和操作指令目录 |
| **Memory** | 跨对话持久化记忆，分Agent级/用户级/组织级 |
| **Sandbox** | 隔离代码执行环境，保护主机系统 |
| **Human-in-the-loop** | 敏感操作暂停等待人工审批 |
| **Backend** | 文件/记忆的存储后端，支持组合路由 |
| **Deploy** | 打包Agent配置部署为LangSmith服务 |
| **ACP** | Agent与IDE通信的标准协议 |
| **MCP** | Agent调用外部工具的标准协议 |
