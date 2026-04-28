# Deep Agents CLI

> 原文：[https://docs.langchain.com/oss/python/deepagents/cli/overview](https://docs.langchain.com/oss/python/deepagents/cli/overview)

> 基于 Deep Agents SDK 构建的终端编码 agent（智能体）。

Deep Agents CLI 是一个基于 [Deep Agents SDK](/oss/python/deepagents/quickstart) 构建的开源终端编码 agent。它保留持久化内存、跨会话维护上下文、学习项目规范、使用可自定义的技能（skills（技能）），并在执行代码时带有审批控制。

Deep Agents CLI 内置以下能力：

- **文件操作** — 读取、写入和编辑文件，使 agent 能够管理和修改代码和文档。
- **Shell 执行** — 执行命令来运行测试、构建项目、管理依赖和与版本控制交互。
- **网络搜索** — 搜索网络以获取最新信息和文档（需要 Tavily API 密钥）。
- **HTTP 请求** — 向 API 和外部服务发出 HTTP 请求，用于数据获取和集成任务。
- **任务规划和跟踪** — 将复杂任务分解为离散步骤并跟踪进度。
- **内存存储和检索** — 跨会话存储和检索信息，使 agent 能够记住项目规范和学习到的模式。
- **上下文压缩和卸载** — 摘要旧对话消息并将原始消息卸载到存储，在长时间会话期间释放上下文窗口空间。
- **Human-in-the-loop（人在回路中）** — 要求人工审批敏感工具操作。
- **技能** — 通过自定义专业知识和指令扩展 agent 能力。
- **[MCP 工具](/oss/python/deepagents/cli/mcp-tools)** — 从 [Model Context Protocol](https://modelcontextprotocol.io/) 服务器加载外部工具。
- **[Tracing（追踪）](/oss/python/deepagents/cli/overview#tracing-with-langsmith)** — 在 LangSmith 中追踪 agent 操作，用于可观测性和调试。

## 内置工具

Agent 附带以下内置工具，无需配置即可使用：

| 工具 | 描述 | Human-in-the-Loop |
|---|---|---|
| `ls` | 列出文件和目录 | - |
| `read_file` | 读取文件内容；对选定模型支持多模态内容 | - |
| `write_file` | 创建或覆盖文件 | 必需<sup>1</sup> |
| `edit_file` | 对现有文件进行针对性编辑 | 必需<sup>1</sup> |
| `glob` | 查找匹配模式的文件 | - |
| `grep` | 跨文件搜索文本模式 | - |
| `execute` | 本地或在远程沙箱中执行 shell 命令 | 必需<sup>1</sup> |
| `web_search` | 使用 Tavily 搜索网络 | 必需<sup>1</sup> |
| `fetch_url` | 获取网页并转换为 Markdown | 必需<sup>1</sup> |
| `task` | 将工作委托给子智能体并行执行 | 必需<sup>1</sup> |
| `ask_user` | 向用户提出自由形式或多项选择题 | - |
| `compact_conversation` | 摘要旧消息，将原始消息卸载到后端存储，并在上下文中用摘要替换 | 混合<sup>2</sup> |
| `write_todos` | 为复杂工作创建和管理任务列表 | - |

<sup>1</sup>：可能具有破坏性的操作在执行前需要用户审批。要跳过人工审批，你可以切换自动审批（shift+tab）或使用以下选项启动：

```bash
deepagents -y
# 或
deepagents --auto-approve
```

> 以非交互方式运行 CLI 时（通过 `-n` 或管道 stdin），即使使用 `-y`/`--auto-approve`，shell 执行默认也被禁用。使用 `-S`/`--shell-allow-list` 来允许特定命令（如 `-S "pytest,git,make"`）、`recommended` 获取安全默认值，或 `all` 允许任何命令。也支持 `DEEPAGENTS_CLI_SHELL_ALLOW_LIST` 环境变量。参见[非交互模式和管道](#非交互模式和管道)获取详情。

<sup>2</sup>：当 token 使用超过模型感知阈值时，CLI 会在后台自动卸载对话。卸载通过 LLM 摘要旧消息，并将原始消息弹出到存储（`/conversation_history/{thread_id}.md`），在上下文中用摘要替换它们。Agent 仍可从卸载的文件中检索完整历史（如果需要）。`compact_conversation` 工具让 agent（或你）按需触发卸载。作为工具调用时，默认需要用户审批。

> [观看演示视频](https://youtu.be/IrnacLa9PJc?si=3yUnPbxnm2yaqVQb) 了解 Deep Agents CLI 的工作方式。

> Deep Agents CLI 在 Windows 上不受官方支持。Windows 用户可以尝试在 [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install) 下运行。

## 快速开始

### 1. 设置模型凭据

将你的提供商 API 密钥导出为环境变量，或添加到 `~/.deepagents/.env`：

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Google
export GOOGLE_API_KEY="your-api-key"
```

> 为避免在每个终端会话中设置密钥，将它们添加到 `~/.deepagents/.env`。参见[环境变量](/oss/python/deepagents/cli/configuration#environment-variables)。

CLI 可与任何支持工具调用的 LLM 配合使用。OpenAI、Anthropic 和 Google 默认安装。对于其他提供商（Ollama、Groq、xAI 等），参见[提供商](#提供商)。

### 2. 安装并运行

OpenAI、Anthropic 和 Google 默认包含。其他提供商（Ollama、Groq、xAI 等）作为可选额外组件安装——参见[提供商](#提供商)获取详情。

```bash
# 使用安装脚本
curl -LsSf https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/main/libs/cli/scripts/install.sh | bash

# 可选额外组件
DEEPAGENTS_EXTRAS="ollama,groq" curl -LsSf https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/main/libs/cli/scripts/install.sh | bash

# 或使用 uv
uv tool install 'deepagents-cli[ollama,groq]'
```

```bash
deepagents
```

### 3. 给 agent 一个任务

```txt
Create a Python script that prints "Hello, World!"
```

Agent 在修改文件之前会提出带有 diff 的更改供你审批。

### 4. 启用 Tracing（可选）

要在 LangSmith 中查看 agent 操作、工具调用和决策，将以下内容添加到 `~/.deepagents/.env` 或在 shell 中导出变量：

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=optional-project-name  # 指定项目名称或默认为 "deepagents-cli"
```

## 提供商

OpenAI、Anthropic 和 Google 开箱即含。其他提供商分别安装，因此你只拉取需要的内容。

```bash
# 向现有安装添加额外提供商
uv tool install deepagents-cli --with langchain-xai
```

有关支持的提供商完整列表，请参见[模型提供商](/oss/python/deepagents/cli/providers)。

## 交互模式

像聊天界面一样自然地输入。Agent 将使用其内置工具、技能和内存来帮助你完成任务。

### 斜杠命令

在 CLI 会话中使用这些命令：

- `/model` — 切换模型或打开交互式模型选择器。参见[切换模型](#切换模型)获取详情
- `/agents` — 在预配置的 agent 之间热切换，无需重新启动。参见[切换 agent](#切换-agents)获取详情
- `/remember [context]` — 审查对话并更新内存和技能。可选择传递额外上下文
- `/skill:<name> [args]` — 按名称直接调用技能。技能的 `SKILL.md` 指令连同你提供的任何参数一起注入提示词
- `/skill-creator [args]` — 创建有效 agent 技能的指南
- `/offload`（别名 `/compact`）— 通过将消息卸载到存储并带有摘要占位符来释放上下文窗口空间。Agent 可在需要时从卸载文件中检索完整历史
- `/tokens` — 显示当前上下文窗口 token 使用量细分
- `/clear` — 清除对话历史并开始新线程
- `/threads` — 浏览和恢复之前的对话线程
- `/mcp` — 显示活跃的 MCP 服务器和工具
- `/reload` — 重新读取 `.env` 文件、刷新配置并重新发现技能，无需重启。对话状态保留。参见[`DEEPAGENTS_CLI_` 前缀](/oss/python/deepagents/cli/configuration#deepagents_cli_-prefix)获取覆盖行为
- `/theme` — 打开交互式主题选择器以切换颜色主题。可使用内置主题和任何[用户定义主题](/oss/python/deepagents/cli/configuration#themes)
- `/update` — 内联检查和安装 CLI 更新。检测你的安装方法（uv、Homebrew、pip）并运行相应的升级命令
- `/auto-update` — 切换自动更新的开关
- `/trace` — 在 LangSmith 中打开当前线程（需要 `LANGSMITH_API_KEY`）
- `/editor` — 在外部编辑器（`$VISUAL` / `$EDITOR`）中打开当前提示词。参见[外部编辑器](/oss/python/deepagents/cli/configuration#external-editor)
- `/changelog` — 在浏览器中打开 CLI 变更日志
- `/docs` — 在浏览器中打开文档
- `/feedback` — 打开 GitHub issues 页面提交 bug 报告或功能请求
- `/version` — 显示已安装的 `deepagents-cli` 和 SDK 版本
- `/help` — 显示帮助和可用命令
- `/quit` — 退出 CLI

### Shell 命令

输入 `!` 进入 shell 模式，然后输入你的命令。

```bash
git status
npm test
ls -la
```

### 键盘快捷键

**通用**

| 快捷键 | 操作 |
|---|---|
| `Enter` | 提交提示词 |
| `Shift+Enter`、`Ctrl+J`、`Alt+Enter` 或 `Ctrl+Enter` | 插入新行 |
| `Ctrl+A` | 选择输入中的所有文本 |
| `@filename` | 自动补全文件并注入内容 |
| `Shift+Tab` 或 `Ctrl+T` | 切换自动审批 |
| `Ctrl+U` | 删除到行首 |
| `Ctrl+X` | 在外部编辑器中打开提示词 |
| `Ctrl+O` | 展开/折叠最近的工具输出 |
| `Escape` | 中断当前操作 |
| `Ctrl+C` | 中断或退出 |
| `Ctrl+D` | 退出 |

## 非交互模式和管道

使用 `-n` 运行单个任务，无需启动交互式 UI：

```bash
deepagents -n "Write a Python script that prints hello world"
```

你也可以通过 stdin 管道输入。当输入是管道时，CLI 自动以非交互方式运行：

```bash
echo "Explain this code" | deepagents
cat error.log | deepagents -n "What's causing this error?"
git diff | deepagents -n "Review these changes"
git diff | deepagents --skill code-review -n 'summarize changes'
```

当将管道输入与 `-n` 或 `-m` 结合时，管道内容先出现，后面是你传递给标志的文本。

> 最大管道输入大小为 10 MiB。

非交互模式下，shell 执行默认禁用。使用 `-S`/`--shell-allow-list` 启用特定命令（如 `-S "pytest,git,make"`）、`recommended` 获取安全默认值，或 `all` 允许任何命令。

### 使用 `--max-turns` 限制回合数

CI/CD 流水线中长时间运行或行为不当的 agent 可能无限循环。`--max-turns N` 给操作者一个硬性上限，无需触碰 SDK 内部：

```bash
deepagents -n "fix the failing tests" --max-turns 10
```

`N` 必须是正整数，并覆盖否则限制失控循环的内部安全默认值。超出预算时退出码为 124（匹配 GNU `timeout`），因此 CI 可以区分预算命中和一般故障。需要 `-n` 或管道 stdin；否则退出码为 2。

### 清洁输出和缓冲

使用 `-q` 获取适合管道传输到其他命令的清洁输出，使用 `--no-stream` 在写入 stdout 之前缓冲完整响应（而非流式）：

```bash
deepagents -n "Generate a .gitignore for Python" -q > .gitignore
deepagents -n "List dependencies" -q --no-stream | sort
```

在非交互模式下，agent 被指示做出合理假设并自主进行，而非提出澄清问题。它也偏向非交互式命令变体（如 `npm init -y`、`apt-get install -y`）。

### Shell 执行示例

```bash
# 允许特定命令（针对列表验证）
deepagents -n "Run the tests and fix failures" -S "pytest,git,make"

# 使用精选的安全命令列表
deepagents -n "Build the project" -S recommended

# 允许任何 shell 命令
deepagents -n "Fix the build" -S all
```

> **谨慎使用。** `-S all`（或 `--shell-allow-list all`）让 agent 在无人工确认的情况下执行任意 shell 命令。

## 启动时运行命令

使用 `--startup-cmd` 在会话接受第一个提示词之前运行一次 shell 命令。输出在会话顶部显示，方便在输入第一个提示词之前检查 `git status`、列出文件或验证环境设置。

```bash
# 交互模式：在第一个提示词之前显示 git status
deepagents --startup-cmd "git status"

# 与初始提示词组合——命令先运行，然后提交提示词
deepagents --startup-cmd "ls -la" -m "Summarize what's in this directory"

# 非交互模式：在任务运行之前查看环境状态
deepagents --startup-cmd "git diff --stat" -n "Review these changes"
```

命令在任何 `-m` 提示词或 `--skill` 调用分发之前运行，并尊重你的 shell 环境。非零退出和超时发出警告但不中止会话。非交互模式下，命令有 60 秒超时。

> 输出**不**注入 agent 的消息历史——LLM 看不到它。要将命令输出交给 agent，改为通过 stdin 管道输入（如 `git diff | deepagents -n "Review these changes"`）。

## 切换模型

你可以在会话期间使用 `/model` 命令切换模型，无需重启 CLI，或在启动时使用 `--model` 标志：

```txt
> /model anthropic:claude-opus-4-6
> /model openai:gpt-5.4
```

```bash
deepagents --model openai:gpt-5.4
```

运行 `/model` 打开交互式模型选择器，按提供商分组显示可用模型。

有关切换模型、设置默认值和添加自定义模型提供商的完整详情，请参见[模型提供商](/oss/python/deepagents/cli/providers)。

### 交互式模型选择器

选择器为高亮模型显示详细页脚，包含上下文窗口大小、输入模式（文本、图像、音频、PDF、视频）和能力（推理、工具调用、结构化输出）。

被 `--profile-override` 或 `config.toml` 覆盖的值用黄色 `*` 前缀标记。

### 模型参数

在会话中间切换时，使用 `--model-params` 传递额外模型构造函数参数：

```txt
> /model --model-params '{"temperature": 0.7}' anthropic:claude-opus-4-7
> /model --model-params '{"temperature": 0.7}'  # 打开选择器，将参数应用于所选模型
```

这些是会话级覆盖，具有最高优先级，覆盖配置文件 `params` 中的值。`--model-params` 不能与 `--default` 组合使用。

## 切换 agents

运行 `/agents` 打开 agent 选择器并在 `~/.deepagents/` 中的 agent 之间热切换，无需重新启动。切换会重置对话线程并刷新技能发现。选择会被持久化，因此下次裸 `deepagents` 启动时继续同一 agent。`-a`/`--agent` 始终覆盖；`-r`/`--resume` 恢复线程的原始 agent。

## 配置

CLI 将所有配置存储在 `~/.deepagents/` 下。在该目录中，每个 agent 获得自己的子目录（默认：`agent`）：

| 路径 | 用途 |
|---|---|
| `~/.deepagents/config.toml` | 模型默认值、提供商设置、构造函数参数、配置文件覆盖、主题、更新设置、MCP 信任存储 |
| `~/.deepagents/.env` | 全局 API 密钥和密钥。参见[配置](/oss/python/deepagents/cli/configuration#environment-variables) |
| `~/.deepagents/hooks.json` | 生命周期事件钩子（会话开始/结束、任务完成等） |
| `~/.deepagents/<agent_name>/` | 每个 agent 的内存、技能和对话线程 |
| `.deepagents/`（项目根目录） | 项目特定的内存和技能，在 git 仓库内运行时加载 |

```bash
# 列出所有配置的 agent
deepagents agents list
```

有关完整参考——包括 `config.toml` 模式、提供商参数、配置文件覆盖和钩子配置——请参见[配置](/oss/python/deepagents/cli/configuration)。

## 内存

自定义任何 agent 有两种主要方式：

- **内存（Memory）**：跨会话持久的 `AGENTS.md` 文件和自动保存的内存。用于一般编码风格、偏好和学习到的规范。
- **技能（Skills）**：全局和项目特定的上下文、规范、指南或指令。用于仅在执行特定任务时需要的上下文。

使用 `/remember` 明确提示 agent 从当前对话更新其内存和技能。

### 自动内存

当你使用 agent 时，它会自动使用 memory-first 协议将信息存储在 `~/.deepagents/<agent_name>/memories/` 中，作为 Markdown 文件：

1. **研究**：在开始任务之前搜索相关上下文
2. **响应**：在执行期间不确定时检查内存
3. **学习**：自动保存新信息供未来会话使用

Agent 按主题组织内存，使用描述性文件名：

```
~/.deepagents/backend-dev/memories/
├── api-conventions.md
├── database-schema.md
└── deployment-process.md
```

当你教 agent 规范时：

```bash
deepagents --agent backend-dev
> Our API uses snake_case and includes created_at/updated_at timestamps
```

它会在未来会话中记住：

```bash
> Create a /users endpoint
# 无需提示即可应用规范
```

### AGENTS.md 文件

[`AGENTS.md` 文件](https://agents.md/) 提供在会话开始时始终加载的持久上下文：

- **全局**：`~/.deepagents/<agent_name>/AGENTS.md` — 每次会话加载。
- **项目**：任何 git 项目根目录中的 `.deepagents/AGENTS.md` — 当 CLI 在该项目内运行时加载。

两个文件都在启动时追加到系统提示词中。

Agent 可能在回答项目特定问题或当你引用过去工作或模式时读取其内存文件。

当你提供关于它应该如何行为的信息、对其工作的反馈或记住某些内容的指令时，它会更新 `AGENTS.md`。当它从你的交互中识别模式或偏好时，也会更新其内存。

要添加更多结构化的项目知识到额外内存文件中，将它们添加到 `.deepagents/` 并在 `AGENTS.md` 文件中引用它们。你必须在 `AGENTS.md` 文件中引用额外文件，这样 agent 才能知道它们。额外文件不会在启动时读取，但 agent 可以在需要时引用和更新它们。

**全局 `AGENTS.md`**（`~/.deepagents/agent/AGENTS.md`）：
- 你的个性、风格和通用编码偏好
- 基调和沟通风格
- 通用编码偏好（格式化、类型提示等）
- 适用于所有地方的工具使用模式
- 不随项目变化的工作流和方法论

**项目 `AGENTS.md`**（项目根目录中的 `.deepagents/AGENTS.md`）：
- 项目特定上下文和规范
- 项目架构和设计模式
- 此代码库特定的编码规范
- 测试策略和部署流程
- 团队指南和项目结构

## 使用技能

技能是可复用的 agent 能力，提供专门的工作流和领域知识。你可以使用 [技能](/oss/python/deepagents/skills) 为 deep agent 提供新能力和专业知识。Deep agent 技能遵循 [Agent Skills 标准](https://agentskills.io/)。添加技能后，你的 deep agent 会自动使用它们并在使用 agent 和提供额外信息时更新它们。

使用 `/remember` 明确提示 agent 从当前对话更新技能和内存。

### 添加技能

1. 创建技能：

```bash
# 用户技能（存储在 ~/.deepagents/<agent_name>/skills/）
deepagents skills create test-skill

# 项目技能（存储在 .deepagents/skills/）
deepagents skills create test-skill --project
```

这会生成：

```
skills/
└── test-skill
    └── SKILL.md
```

2. 打开生成的 `SKILL.md` 并编辑文件以包含你的指令。

3. 可选择添加额外的脚本或其他资源到 `test-skill` 文件夹。有关更多信息，请参见[示例](/oss/python/deepagents/skills#example)。

你也可以直接将现有技能复制到 agent 的文件夹：

```bash
mkdir -p ~/.deepagents/<agent_name>/skills
cp -r examples/skills/web-research ~/.deepagents/<agent_name>/skills/
```

### 安装社区技能

你可以使用 Vercel 的 [Skills CLI](https://github.com/vercel-labs/skills) 等工具在你的环境中安装社区 [Agent Skills](https://agentskills.io/)，并使它们对你的 deep agent 可用：

```bash
# 全局安装技能
npx skills add vercel-labs/agent-skills --skill web-design-guidelines -a deepagents -g -y

# 列出已安装的技能
npx skills ls -a deepagents -g
```

全局安装（`-g`）将技能符号链接到 `~/.deepagents/agent/skills/`——默认 agent 的用户级技能目录。项目级安装（省略 `-g`）将技能放在相对于当前目录的 `.deepagents/skills/` 中，使它们对在该项目中运行的任何 agent 可用，无论 agent 名称如何。

> 全局安装仅针对默认 `agent` 目录。如果你使用自定义命名的 agent，请使用项目级安装或手动将技能符号链接到 `~/.deepagents/{your-agent}/skills/`。

### 技能发现

启动时，CLI 从 Deep Agents 和共享别名目录发现技能：

```
~/.deepagents/<agent_name>/skills/
~/.agents/skills/
.deepagents/skills/
.agents/skills/
~/.claude/skills/          （实验性）
.claude/skills/            （实验性）
```

当存在重复技能名称时，后优先级的目录覆盖前面的目录（参见[应用数据](/oss/python/deepagents/data-locations#skills)）。

对于项目特定技能，项目的根文件夹必须有 `.git` 文件夹。当你在项目文件夹内任何位置启动 CLI 时，CLI 会通过检查包含的 `.git` 文件夹找到项目的根文件夹。

对于每个技能，CLI 从 `SKILL.md` 文件的 frontmatter 读取名称和描述。当你使用 CLI 时，如果任务与技能描述匹配，agent 会读取技能文件并遵循其指令。

你也可以直接使用 `/skill:<name> [args]` 调用技能。技能发现在启动时和 `/reload` 时运行。

### 从命令行调用技能

使用 `--skill` 在启动时调用技能，无需交互式输入斜杠命令：

```bash
# 打开 TUI 并立即运行技能
deepagents --skill code-review

# 向技能传递请求
deepagents --skill code-review -m 'review the auth module'

# 管道内容到技能
cat diff.txt | deepagents --skill code-review

# 管道内容并添加请求
cat diff.txt | deepagents --skill code-review -m 'focus on security'
```

`--skill` 也可以在非交互模式下工作：

```bash
# 无头运行技能
deepagents --skill code-review -n 'review this patch'

# 静默模式（仅 agent 输出到 stdout）
deepagents --skill code-review -n 'review this patch' -q
```

> `--skill` 配合 `--quiet` 或 `--no-stream` 需要 `-n`（非交互模式）。

### 列出技能

```bash
# 列出所有用户技能
deepagents skills list

# 列出项目技能
deepagents skills list --project

# 获取特定技能的详情
deepagents skills info test-skill
deepagents skills info test-skill --project
```

## 子智能体

将自定义 [subagents（子智能体）](/oss/python/deepagents/subagents) 定义为 Markdown 文件，以便 CLI agent 可以将专门任务委托给它们。每个子智能体位于自己的文件夹中，带有 `AGENTS.md` 文件：

```
.deepagents/agents/{subagent-name}/AGENTS.md   # 项目级
~/.deepagents/{agent}/agents/{subagent-name}/AGENTS.md  # 用户级
```

项目子智能体覆盖同名的用户子智能体（参见[优先级规则](/oss/python/deepagents/data-locations#subagents)）。

Frontmatter 需要 `name` 和 `description`（与 [`SubAgent` 字典规范](/oss/python/deepagents/subagents#subagent-dictionary-based) 相同）。Markdown 主体成为子智能体的 `system_prompt`。除了基础规范外，`AGENTS.md` 文件还支持可选的 `model` frontmatter 字段，为此子智能体覆盖主 agent 的模型。使用 `provider:model-name` 格式（如 `anthropic:claude-opus-4-6`、`openai:gpt-5.4`）。省略则继承主 agent 的模型。

> 其他 `SubAgent` 字段（`tools`、`middleware`、`interrupt_on`、`skills`）目前无法通过 `AGENTS.md` frontmatter 配置——以这种方式定义的自定义子智能体继承主 agent 的工具。直接使用 SDK 获取完整控制。

### 文件格式

子智能体 `AGENTS.md` 文件使用 YAML frontmatter，后跟 Markdown 主体：

```markdown
---
name: researcher
description: 在编写内容之前在网上研究主题
model: anthropic:claude-haiku-4-5-20251001
---

你是一个具有网络搜索访问权限的研究助手。

## 你的流程
1. 搜索相关信息
2. 清晰总结发现
```

### 示例：成本优化的子智能体

对简单委托任务使用更便宜、更快的模型，同时保持主 agent 使用更强大的模型：

```markdown
---
name: general-purpose
description: 用于研究和多步任务的通用 agent
model: anthropic:claude-haiku-4-5-20251001
---

你是一个通用助手。高效完成任务并返回简洁的摘要。
```

这覆盖了内置的通用子智能体，将所有委托任务路由到更便宜的模型。参见[覆盖通用子智能体](/oss/python/deepagents/subagents#override-the-general-purpose-subagent)获取更多信息。

## 使用 MCP 工具

使用外部 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 服务器的工具扩展 CLI。在项目的根目录放置 `.mcp.json`，CLI 会自动发现它。参见 [MCP 工具指南](/oss/python/deepagents/cli/mcp-tools) 获取配置格式、自动发现和故障排除。

## 使用远程沙箱

CLI 使用 [沙箱即工具](/oss/python/deepagents/sandboxes#sandbox-as-tool-pattern) 模式：CLI 进程（LLM 循环、内存、工具分发）在你的机器上运行，但 agent 工具调用（`read_file`、`write_file`、`execute` 等）目标指向远程沙箱，而非本地文件系统。要将文件传入沙箱，使用[设置脚本](#设置脚本)或提供商的文件传输 API（参见[处理文件](/oss/python/deepagents/sandboxes#working-with-files)）。

有关沙箱架构、集成模式和安全最佳实践的深入了解，请参见 [Sandboxes（沙箱）](/oss/python/deepagents/sandboxes)。

> LangSmith 沙箱支持默认包含在 CLI 中。AgentCore、Modal、Daytona 和 Runloop 需要安装额外组件。

### 安装提供商依赖

```bash
# LangSmith — 安装 deepagents-cli 时默认包含，无需额外安装

# Daytona
uv tool install deepagents-cli --with langchain-daytona

# Modal
uv tool install deepagents-cli --with langchain-modal

# Runloop
uv tool install deepagents-cli --with langchain-runloop

# AgentCore
uv tool install deepagents-cli --with langchain-agentcore-codeinterpreter
```

### 设置提供商凭据

```bash
# LangSmith
export LANGSMITH_API_KEY="your-key"

# Daytona
export DAYTONA_API_KEY="your-key"

# Modal
modal setup

# Runloop
export RUNLOOP_API_KEY="your-key"

# AgentCore
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_SESSION_TOKEN="session-token"
export AWS_REGION="us-west-2"
```

### 使用沙箱运行 CLI

```bash
# LangSmith
deepagents --sandbox langsmith

# Daytona
deepagents --sandbox daytona

# Modal
deepagents --sandbox modal

# Runloop
deepagents --sandbox runloop

# AgentCore
deepagents --sandbox agentcore
```

### 沙箱标志

| 标志 | 描述 |
|---|---|
| `--sandbox TYPE` | 要使用的沙箱提供商：`langsmith`、`agentcore`、`modal`、`daytona` 或 `runloop`（默认：`none`） |
| `--sandbox-id ID` | 通过 ID 重用现有沙箱而非创建新的。跳过创建和清理。请参阅你的沙箱文档 |
| `--sandbox-setup PATH` | 创建时在沙箱内运行的设置脚本路径 |

示例：

```bash
# 创建新的 Daytona 沙箱
deepagents --sandbox daytona

# 重用现有沙箱（跳过创建和清理）
deepagents --sandbox runloop --sandbox-id dbx_abc123

# 在沙箱创建后运行设置脚本
deepagents --sandbox modal --sandbox-setup ./setup.sh
```

### 设置脚本

使用 `--sandbox-setup` 在创建后在沙箱内运行 shell 脚本。这对于克隆仓库、安装依赖和配置环境变量很有用。

```bash
#!/bin/bash
set -e

# 使用 GitHub token 克隆仓库
git clone https://x-access-token:${GITHUB_TOKEN}@github.com/username/repo.git $HOME/workspace
cd $HOME/workspace

# 使环境变量持久化
cat >> ~/.bashrc <<'EOF'
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
cd $HOME/workspace
EOF
source ~/.bashrc
```

CLI 使用你的本地环境变量展开设置脚本中的 `${VAR}` 变量引用。将密钥存储在本地 `.env` 文件中，以便设置脚本访问。

> 沙箱隔离代码执行，但 agent 仍然容易受到不可信输入的提示词注入攻击。使用人工审批、短期密钥和仅可信的设置脚本。参见[安全注意事项](/oss/python/deepagents/sandboxes#security-considerations)获取详情。

## 使用 LangSmith Tracing

启用 [LangSmith](https://smith.langchain.com/) 追踪以在 LangSmith 项目中查看 agent 操作、工具调用和决策。

将你的追踪密钥添加到 `~/.deepagents/.env`，以便在每个会话中启用追踪，无需每次导出：

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=optional-project-name  # 指定项目名称或默认为 "deepagents-cli"
```

要为特定项目覆盖，在项目目录中添加相同的密钥到 `.env`。参见[环境变量](/oss/python/deepagents/cli/configuration#environment-variables)获取完整加载顺序。

你也可以将这些设置为 shell 环境变量。Shell 导出始终优先于 `.env` 值，因此这是临时覆盖或测试的好选项：

```bash
export LANGSMITH_TRACING=false
```

配置后，CLI 显示带有 LangSmith 项目链接的状态行。在支持的终端中，点击链接直接打开它。你也可以使用 `/trace` 打印 URL 并在浏览器中打开它。

```sh
✓ LangSmith tracing: 'my-project'
```

### 将 agent 追踪与应用追踪分离

当从 LangChain 应用程序以编程方式调用 CLI 时（例如作为[非交互模式](#非交互模式和管道)中的子进程），你的应用程序和 CLI 都产生 LangSmith 追踪。默认情况下，这些都落在同一项目中。

要将 CLI 追踪发送到专用项目，设置 `DEEPAGENTS_CLI_LANGSMITH_PROJECT`：

```bash
DEEPAGENTS_CLI_LANGSMITH_PROJECT=my-deep-agent-execution
```

然后为你的父应用程序的追踪配置 `LANGSMITH_PROJECT`：

```bash
LANGSMITH_PROJECT=my-app-traces
```

这保持你的应用级可观测性干净，同时仍在单独项目中捕获 agent 的内部执行。

你也可以使用 [`DEEPAGENTS_CLI_` 前缀](/oss/python/deepagents/cli/configuration#deepagents_cli_-prefix)将 LangSmith 凭据限定到 CLI（如 `DEEPAGENTS_CLI_LANGSMITH_API_KEY`）。

## 命令参考

```bash
# 使用特定的 agent 配置
deepagents --agent mybot

# 使用特定的模型（提供商:模型格式或自动检测）
deepagents --model anthropic:claude-opus-4-7
deepagents --model gpt-5.4

# 自动审批工具使用（跳过人在回路中提示）
deepagents -y
```

### 命令行选项

| 选项 | 描述 |
|---|---|
| `-a`, `--agent NAME` | 使用命名 agent，具有单独的内存。覆盖 `config.toml` 中的 `[agents].recent`。默认：`agent`（或如果设置了 `[agents].recent` 则为最近使用的 agent） |
| `-M`, `--model MODEL` | 使用特定模型（`provider:model`） |
| `--model-params JSON` | 作为 JSON 字符串传递给模型的额外参数（如 `'{"temperature": 0.7}'`） |
| `--default-model [MODEL]` | 设置默认模型 |
| `--clear-default-model` | 清除默认模型 |
| `-r`, `--resume [ID]` | 恢复会话：`-r` 表示最近，`-r <ID>` 表示特定线程 |
| `-m`, `--message TEXT` | 会话启动时自动提交的初始提示词（交互模式） |
| `--skill NAME` | 启动时调用技能 |
| `--startup-cmd CMD` | 启动时运行的 shell 命令，在第一个提示词之前。输出呈现在转录中供参考，但**不**添加到 agent 的消息历史。非零退出和超时发出警告但不中止；非交互模式应用 60 秒超时。参见[启动时运行命令](#启动时运行命令) |
| `-n`, `--non-interactive TEXT` | 非交互方式运行单个任务并退出。除非设置 `--shell-allow-list`，否则 shell 被禁用 |
| `--max-turns N` | 非交互模式下限制 agent 回合数。超出预算时退出码 124 |
| `-S`, `--shell-allow-list LIST` | 非交互模式下允许的 shell 命令（`-S "pytest,git"`、`recommended` 或 `all`） |
| `-y`, `--auto-approve` | 跳过所有工具的人类审批 |
| `-q`, `--quiet` | 清洁输出到 stdout（无 UI 渲染） |
| `--no-stream` | 缓冲完整响应后再写入 stdout |
