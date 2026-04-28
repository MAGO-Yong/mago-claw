# LangChain Deep Agents 完整中文翻译

> 原文来源：[LangChain Deep Agents Docs](https://docs.langchain.com/oss/python/deepagents/)
> 翻译日期：2026-04-27

## 目录

1. [Quickstart（快速入门）](#quickstart快速入门)
2. [Customization（自定义）](#customization自定义)
3. [Models（模型）](#models模型)
4. [Backends（后端）](#backends后端)
5. [Sandboxes（沙箱）](#sandboxes沙箱)
6. [Permissions（权限）](#permissions权限)
7. [Human-in-the-loop（人在回路中）](#human-in-the-loop人在回路中)
8. [Skills（技能）](#skills技能)
9. [Context Engineering（上下文工程）](#context-engineering上下文工程)
10. [CLI Overview（CLI 概览）](#cli-overviewcli-概览)
11. [ACP（Agent Client Protocol）](#acpagent-client-protocol)

# Quickstart（快速入门）

> 原文：[https://docs.langchain.com/oss/python/deepagents/quickstart](https://docs.langchain.com/oss/python/deepagents/quickstart)

> 在几分钟内构建你的第一个 deep agent（深度智能体）。

## Installation（安装）

```bash
pip install deepagents
# 或
uv add deepagents
```

## 创建你的第一个 agent（智能体）

Deep agents（深度智能体）是内置了 filesystem access（文件系统访问）、planning（规划）和 subagent（子智能体）能力的 agents（智能体）。它们能够执行多步骤的编码任务——例如 plan → implement → run tests → fix（规划 → 实现 → 运行测试 → 修复）。

```python
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-sonnet-4-6")
agent = create_deep_agent(model=model)
```

### 调用 agent

```python
from langchain_core.messages import HumanMessage

result = agent.invoke({
    "messages": [HumanMessage(content="创建一个 hello.py 脚本，打印 Hello, World!")]
})
print(result["messages"][-1].content)
```

### 启用检查点（持久化）

添加一个 checkpointer（检查点）来跨对话持久化状态：

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    model=model,
    checkpointer=MemorySaver(),
)

config = {"configurable": {"thread_id": "session-1"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "创建一个 greet.py 脚本"}]},
    config=config,
)
```

使用相同的 `thread_id`（线程 ID）来恢复对话。

## 核心概念

Deep agents（深度智能体）有四个核心支柱：

1. **System prompt（系统提示词）** — 控制 agent 的角色和行为
2. **Tools（工具）** — agent 可以采取的行动，如文件系统操作和代码执行
3. **Subagents（子智能体）** — 将任务委托给专门的智能体
4. **Backends（后端）** — agent 可以读写的存储层

## 下一步

- [Customization（自定义）](/oss/python/deepagents/customization) — 自定义提示词、工具和中间件
- [Models（模型）](/oss/python/deepagents/models) — 模型配置和切换
- [Backends（后端）](/oss/python/deepagents/backends) — 文件系统和远程存储
- [Sandboxes（沙箱）](/oss/python/deepagents/sandboxes) — 远程代码执行
- [Permissions（权限）](/oss/python/deepagents/permissions) — 控制文件系统访问

---

# Customization（自定义）

> 原文：[https://docs.langchain.com/oss/python/deepagents/customization](https://docs.langchain.com/oss/python/deepagents/customization)

> 自定义系统提示词（system prompt（系统提示词））、工具（tools（工具））、中间件（middleware（中间件））和内存（memory（内存）），以调整 deep agent（深度智能体）的行为。

## System prompt（系统提示词）

你的自定义系统提示词会前置到内置系统提示词。使用它来定义 agent（智能体）的角色、行为和知识。

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    system_prompt=(
        "你是一个专注于科学文献的研究助手。"
        "始终引用来源。使用子智能体（subagents）对不同主题进行并行研究。"
    ),
)
```

`system_prompt` 参数是静态的，意味着它不会在每次调用时改变。对于某些用例，你可能需要动态提示词：例如告诉模型"你有管理员权限"与"你只有只读权限"，或注入用户偏好（如"用户偏好简洁回答"）。如果你的提示词依赖上下文或 `runtime.store`，请使用 `@dynamic_prompt` 来构建上下文感知指令。参见 [LangChain 上下文工程指南](/oss/python/langchain/context-engineering#system-prompt) 获取示例。

## Tools（工具）

通过 `tools` 参数传递自定义工具。工具的描述（来自工具 schema（模式））会发送给模型。

```python
from deepagents import create_deep_agent
from langchain.tools import tool

@tool(parse_docstring=True)
def calculate(expression: str) -> str:
    """计算数学表达式。
    
    当用户需要进行数学运算时使用此工具。
    
    Args:
        expression: 要计算的数学表达式字符串
    """
    return str(eval(expression))

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    tools=[calculate],
)
```

对于你提供的工具，确保提供清晰的名称、描述和参数描述。这些指导模型推理何时以及如何使用工具。在描述中包含**何时**使用该工具，并描述每个参数的作用。

### 通过中间件（Middleware）添加工具

你还可以添加 [自定义中间件](/oss/python/langchain/middleware)，添加工具并追加自己的系统提示词指令。参见 [LangChain 中间件文档](/oss/python/langchain/middleware) 获取详情。

## Memory（内存）

内存文件（[`AGENTS.md`](https://agents.md/)）提供持久化上下文，**始终加载**到系统提示词中。用于项目规范、用户偏好和应该应用于每次对话的关键指南：

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    memory=["/project/AGENTS.md", "~/.deepagents/preferences.md"],
)
```

与 Skills（技能）不同，内存始终注入——没有渐进式披露（progressive disclosure（渐进式披露））。保持内存最小化以避免上下文过载；对详细工作流和领域特定内容使用 [skills](/oss/python/deepagents/skills)。

### 只读与可写内存

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    memory=[
        "/project/AGENTS.md",         # 默认只读
        "~/.deepagents/preferences.md",  # 只读
    ],
)
```

参见 [Memory（内存）](/oss/python/deepagents/customization#memory) 了解配置详情。

## Middleware（中间件）

中间件允许你在 agent 执行前后运行自定义逻辑。用于添加工具、修改系统提示词或注入上下文。

```python
from langchain.agents.middleware import AgentMiddleware, AgentState
from typing import Any

class MyMiddleware(AgentMiddleware[AgentState, Any, Any]):
    def before_agent(self, state, runtime):
        # 在 agent 执行前运行
        pass

    def after_agent(self, state, runtime, result):
        # 在 agent 执行后运行
        pass

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    middleware=[MyMiddleware()],
)
```

---

# Models（模型）

> 原文：[https://docs.langchain.com/oss/python/deepagents/models](https://docs.langchain.com/oss/python/deepagents/models)

> 为 Deep Agents（深度智能体）配置模型提供商和参数。

Deep Agents 可与任何支持 [tool calling（工具调用）](/oss/python/langchain/models#tool-calling) 的 [LangChain 聊天模型](/oss/python/langchain/models) 配合使用。

## 支持的模型

以 `provider:model` 格式指定模型（例如 `google_genai:gemini-3.1-pro-preview`、`openai:gpt-5.4` 或 `anthropic:claude-sonnet-4-6`）。有效的提供商字符串请参见 [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model) 的 `model_provider` 参数。关于特定提供商的配置，请参见 [聊天模型集成](/oss/python/integrations/chat)。

### 推荐模型

以下模型在 [Deep Agents 评测套件](https://github.com/langchain-ai/deepagents/tree/main/libs/evals#readme)（测试基本 agent 操作）上表现良好。通过这些评测是获得良好性能的必要条件，但对于更长、更复杂的任务来说还不够充分。

| Provider（提供商） | Models（模型） |
|---|---|
| [Google](/oss/python/integrations/providers/google) | `gemini-3.1-pro-preview`、`gemini-3-flash-preview` |
| [OpenAI](/oss/python/integrations/providers/openai) | `gpt-5.4`、`gpt-4o`、`o4-mini`、`gpt-5.2-codex`、`gpt-4o-mini`、`o3` |
| [Anthropic](/oss/python/integrations/providers/anthropic) | `claude-opus-4-6`、`claude-opus-4-5`、`claude-sonnet-4-6`、`claude-sonnet-4`、`claude-sonnet-4-5`、`claude-haiku-4-5`、`claude-opus-4-1` |
| 开放权重模型 | `GLM-5`、`Kimi-K2.5`、`MiniMax-M2.5`、`qwen3.5-397B-A17B`、`devstral-2-123B` |

开放权重模型可通过 [Baseten](/oss/python/integrations/providers/baseten)、[Fireworks](/oss/python/integrations/providers/fireworks)、[OpenRouter](/oss/python/integrations/providers/openrouter) 和 [Ollama](/oss/python/integrations/providers/ollama) 等提供商获取。

## 配置模型参数

将模型字符串以 `provider:model` 格式传递给 [`create_deep_agent`](https://reference.langchain.com/python/deepagents/graph/create_deep_agent)，或传递已配置的模型实例以实现完全控制。底层通过 [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model) 解析模型字符串。

要配置模型特定参数，请使用 [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model) 或直接实例化提供商模型类：

```python
# 方式一：使用 init_chat_model
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

model = init_chat_model(
    model="google_genai:gemini-3.1-pro-preview",
    thinking_level="medium",
)
agent = create_deep_agent(model=model)
```

```python
# 方式二：直接使用提供商包
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview",
    thinking_level="medium",
)
agent = create_deep_agent(model=model)
```

> 可用参数因提供商而异。请参阅 [聊天模型集成](/oss/python/integrations/chat) 页面获取特定于提供商的配置选项。

## 运行时选择模型

如果你的应用程序允许用户选择模型（例如使用 UI 中的下拉菜单），请使用 [middleware（中间件）](/oss/python/langchain/middleware) 在运行时交换模型，而无需重新构建 agent。

通过 [runtime context（运行时上下文）](/oss/python/langchain/agents#dynamic-model) 传递用户的模型选择，然后使用 `wrap_model_call` 中间件在每次调用时覆盖模型：

```python
from dataclasses import dataclass
from langchain.chat_models import init_chat_model
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from deepagents import create_deep_agent
from typing import Callable


@dataclass
class Context:
    model: str

@wrap_model_call
def configurable_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    model_name = request.runtime.context.model
    model = init_chat_model(model_name)
    return handler(request.override(model=model))

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    middleware=[configurable_model],
    context_schema=Context,
)

# 使用用户选择的模型进行调用
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Hello!"}]},
    context=Context(model="openai:gpt-5.4"),
)
```

> 有关更多动态模型模式（例如基于对话复杂性或成本优化进行路由），请参见 LangChain agent 指南中的 [Dynamic model（动态模型）](/oss/python/langchain/agents#dynamic-model)。

## 了解更多

* [LangChain 中的模型](/oss/python/langchain/models)：聊天模型功能，包括工具调用、结构化输出和多模态

---

# Backends（后端）

> 原文：[https://docs.langchain.com/oss/python/deepagents/backends](https://docs.langchain.com/oss/python/deepagents/backends)

> 选择和配置 Deep Agents 的文件系统后端。你可以指定不同路由到不同后端、实现虚拟文件系统以及强制执行策略。

Deep Agents 通过 `ls`、`read_file`、`write_file`、`edit_file`、`glob` 和 `grep` 等工具向 agent（智能体）暴露文件系统接口。这些工具通过可插拔的后端运行。`read_file` 工具在所有后端上原生支持图像文件（`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`），将其作为多模态内容块返回。

沙箱和 [`LocalShellBackend`](https://reference.langchain.com/python/deepagents/backends/local_shell/LocalShellBackend) 还提供 `execute` 工具。

本页解释如何：
- [选择后端](#指定后端)
- [将不同路径路由到不同后端](#路由到不同后端)
- [实现你自己的虚拟文件系统](#使用虚拟文件系统)（如 S3 或 Postgres）
- [设置文件系统访问权限](#权限)
- [遵守后端协议](#协议参考)

## 快速开始

以下是几个可直接与 deep agent（深度智能体）配合使用的预构建文件系统后端：

| 内置后端 | 描述 |
|---|---|
| [默认（StateBackend）](#statebackend-临时) | `agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview")`<br/>临时存储在状态中。agent 的默认文件系统后端存储在 `langgraph` 状态中。注意：此文件系统仅对**单个线程**持久。 |
| [本地文件系统持久化](#filesystembackend-本地磁盘) | `agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview", backend=FilesystemBackend(root_dir="/Users/nh/Desktop/"))`<br/>使 deep agent 能够访问本地机器的文件系统。你可以指定 agent 可访问的根目录。注意：提供的 `root_dir` 必须是绝对路径。 |
| [持久化存储（LangGraph store）](#storebackend-langgraph-存储) | `agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview", backend=StoreBackend())`<br/>使 agent 能够访问**跨线程持久**的长期存储。适用于存储跨多次执行适用的长期记忆或指令。 |
| [沙箱](/oss/python/deepagents/sandboxes) | `agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview", backend=sandbox)`<br/>在隔离环境中执行代码。沙箱提供文件系统工具加上用于运行 shell 命令的 `execute` 工具。可选择 Modal、Daytona、Deno 或本地 VFS。 |
| [本地 Shell](#localshellbackend-本地-shell) | `agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview", backend=LocalShellBackend(root_dir=".", env={"PATH": "/usr/bin:/bin"}))`<br/>直接在主机上执行文件系统和 shell。无隔离——仅在受控开发环境中使用。参见下方[安全注意事项](#localshellbackend-本地-shell)。 |
| [复合后端（Composite）](#compositebackend-路由器) | 默认临时，`/memories/` 持久。Composite 后端最为灵活。你可以指定文件系统中的不同路径指向不同的后端。参见下方复合路由获取可直接粘贴的示例。 |

## 内置后端

### StateBackend（临时）

```python
# 默认情况下提供 StateBackend
agent = create_deep_agent(model="google_genai:gemini-3.1-pro-preview")

# 底层实现如下
from deepagents.backends import StateBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=StateBackend()
)
```

**工作原理：**
- 通过 [`StateBackend`](https://reference.langchain.com/python/deepagents/backends/state/StateBackend) 将文件存储在当前线程的 LangGraph agent 状态中。
- 通过检查点在同一线程的多个 agent 回合间持久。

**适用场景：**
- 供 agent 写入中间结果的暂存区。
- 自动淘汰大型工具输出，agent 可逐段读回。

注意：此后端在 supervisor agent（主管智能体）和 subagents（子智能体）之间共享，子智能体写入的任何文件在该子智能体执行完成后仍将保留在 LangGraph agent 状态中。这些文件将继续对 supervisor agent 和其他子智能体可用。

### FilesystemBackend（本地磁盘）

[`FilesystemBackend`](https://reference.langchain.com/python/deepagents/backends/filesystem/FilesystemBackend) 在可配置的根目录下读写真实文件。

> ⚠️ 此后端赋予 agent 直接的文件系统读写访问权限。请谨慎使用，且仅在适当的环境中使用。
>
> **适用场景：**
> - 本地开发 CLI（编码助手、开发工具）
> - CI/CD 流水线（参见下方安全注意事项）
>
> **不适用场景：**
> - Web 服务器或 HTTP API——请改用 `StateBackend`、`StoreBackend` 或 [沙箱后端](/oss/python/deepagents/sandboxes)
>
> **安全风险：**
> - Agent 可读取任何可访问的文件，包括密钥（API 密钥、凭据、`.env` 文件）
> - 结合网络工具时，密钥可能通过 SSRF 攻击被外泄
> - 文件修改是永久且不可逆的
>
> **推荐防护措施：**
> 1. 启用 [Human-in-the-Loop（人在回路中）中间件](/oss/python/deepagents/human-in-the-loop) 审查敏感操作。
> 2. 从可访问的文件系统路径中排除密钥（尤其在 CI/CD 中）。
> 3. 对需要文件系统交互的生产环境使用 [沙箱后端](/oss/python/deepagents/sandboxes)。
> 4. **始终**使用 `virtual_mode=True` 配合 `root_dir` 以启用基于路径的访问限制（阻止 `..`、`~` 和根目录外的绝对路径）。注意默认值（`virtual_mode=False`）即使设置了 `root_dir` 也不提供安全保障。

```python
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=FilesystemBackend(root_dir=".", virtual_mode=True)
)
```

**工作原理：**
- 在可配置的 `root_dir` 下读写真实文件。
- 可选择设置 `virtual_mode=True` 以在 `root_dir` 下沙箱化和规范化路径。
- 使用安全路径解析，尽可能防止不安全的符号链接遍历，可使用 ripgrep 实现快速 `grep`。

**适用场景：**
- 本地机器上的项目
- CI 沙箱
- 挂载的持久卷

### LocalShellBackend（本地 Shell）

> ⚠️ 此后端赋予 agent 直接的文件系统读写访问权限**以及**在主机上不受限制的 shell 执行权限。请极其谨慎地使用，且仅在适当的环境中使用。
>
> **适用场景：**
> - 本地开发 CLI（编码助手、开发工具）
> - 你信任 agent 代码的个人开发环境
> - 具有适当密钥管理的 CI/CD 流水线
>
> **不适用场景：**
> - 生产环境（如 Web 服务器、API、多租户系统）
> - 处理不可信用户输入或执行不可信代码
>
> **安全风险：**
> - Agent 可以**任意 shell 命令**以你的用户权限执行
> - Agent 可读取任何可访问文件，包括密钥
> - 密钥可能暴露
> - 文件修改和命令执行是**永久且不可逆**的
> - 命令直接在主机系统上运行
> - 命令可能消耗无限制的 CPU、内存、磁盘
>
> **推荐防护措施：**
> 1. 启用 [Human-in-the-Loop（人在回路中）中间件](/oss/python/deepagents/human-in-the-loop) 在执行前审查和批准操作。**强烈建议**。
> 2. 仅在专用开发环境中运行。切勿在共享或生产系统上使用。
> 3. 对需要 shell 执行的生产环境使用 [沙箱后端](/oss/python/deepagents/sandboxes)。
>
> **注意：** 启用 shell 访问后，`virtual_mode=True` 不提供安全保障，因为命令可访问系统上的任何路径。

```python
from deepagents.backends import LocalShellBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=LocalShellBackend(root_dir=".", env={"PATH": "/usr/bin:/bin"})
)
```

**工作原理：**
- 扩展 `FilesystemBackend`，添加 `execute` 工具用于在主机上运行 shell 命令。
- 使用 `subprocess.run(shell=True)` 直接在机器上运行命令，无沙箱。
- 支持 `timeout`（默认 120 秒）、`max_output_bytes`（默认 100,000）、`env` 和 `inherit_env`。
- Shell 命令使用 `root_dir` 作为工作目录，但可访问系统上的任何路径。

### StoreBackend（LangGraph 存储）

```python
from langgraph.store.memory import InMemoryStore
from deepagents.backends import StoreBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=StoreBackend(
        namespace=lambda ctx: (ctx.runtime.context.user_id,),
    ),
    store=InMemoryStore()  # 适用于本地开发；部署到 LangSmith 时省略
)
```

> 部署到 [LangSmith Deployment](/langsmith/deployment) 时，省略 `store` 参数。平台会自动为你的 agent 配置存储。

> `namespace` 参数控制数据隔离。对于多用户部署，始终设置 [namespace 工厂](/oss/python/deepagents/backends#namespace-factories) 以按用户或租户隔离数据。

**工作原理：**
- [`StoreBackend`](https://reference.langchain.com/python/deepagents/backends/store/StoreBackend) 将文件存储在运行时提供的 LangGraph [`BaseStore`](https://reference.langchain.com/python/langchain-core/stores/BaseStore) 中，实现跨线程持久存储。

**适用场景：**
- 已配置 LangGraph 存储时（例如 Redis、Postgres 或 [`BaseStore`](https://reference.langchain.com/python/langchain-core/stores/BaseStore) 背后的云实现）。
- 通过 [LangSmith Deployment](/langsmith/deployment) 部署 agent 时（自动为 agent 配置存储）。

#### Namespace 工厂

Namespace 工厂控制 `StoreBackend` 在何处读写数据。它接收 LangGraph [`Runtime`](https://reference.langchain.com/python/langgraph/runtime/Runtime) 并返回用作存储命名空间的字符串元组。使用 namespace 工厂来隔离用户、租户或 assistant 之间的数据。

构建 `StoreBackend` 时将 namespace 工厂传递给 `namespace` 参数：

```python
NamespaceFactory = Callable[[Runtime], tuple[str, ...]]
```

`Runtime` 提供：
- `rt.context` — 通过 LangGraph [context schema](https://langchain-ai.github.io/langgraph/concepts/runtime/) 传递的用户提供上下文（例如 `user_id`）
- `rt.server_info` — 在 LangGraph Server 上运行时的服务器特定元数据（assistant ID、graph ID、认证用户）
- `rt.execution_info` — 执行身份信息（线程 ID、运行 ID、检查点 ID）

> `Runtime` 参数在 `deepagents>=0.5.2` 中可用。早期 0.5.x 版本传递的是 `BackendContext`——参见下方[从 `BackendContext` 迁移](#从-backendcontext-迁移)。`rt.server_info` 和 `rt.execution_info` 需要 `deepagents>=0.5.0`。

**常见 namespace 模式：**

```python
from deepagents.backends import StoreBackend

# 每用户：每个用户获得独立的存储
backend = StoreBackend(
    namespace=lambda rt: (rt.server_info.user.identity,),
)

# 每 assistant：同一 assistant 的所有用户共享存储
backend = StoreBackend(
    namespace=lambda rt: (
        rt.server_info.assistant_id,
    ),
)

# 每线程：存储限定在单个对话内
backend = StoreBackend(
    namespace=lambda rt: (
        rt.execution_info.thread_id,
    ),
)
```

你可以组合多个组件创建更细粒度的范围——例如 `(user_id, thread_id)` 实现每用户每对话隔离，或追加后缀如 `"filesystem"` 以在相同范围使用多个存储命名空间时消歧。

Namespace 组件只能包含字母数字字符、连字符、下划线、点、`@`、`+`、冒号和波浪号。通配符（`*`、`?`）被拒绝以防止 glob 注入。

> `namespace` 参数在 v0.5.0 中将变为**必需**。新代码请始终显式设置。

> 未提供 namespace 工厂时，旧版默认使用 LangGraph 配置元数据中的 `assistant_id`。这意味着同一 [assistant](/langsmith/assistants) 的所有用户共享相同存储。对于多用户[投入生产](/oss/python/deepagents/going-to-production)，始终提供 namespace 工厂。

### CompositeBackend（路由器）

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(),
        }
    ),
    store=InMemoryStore()  # Store 传递给 create_deep_agent，而非 backend
)
```

**工作原理：**
- [`CompositeBackend`](https://reference.langchain.com/python/deepagents/backends/composite/CompositeBackend) 根据路径前缀将文件操作路由到不同后端。
- 在列表和搜索结果中保留原始路径前缀。

**适用场景：**
- 当你希望 agent 同时拥有临时和跨线程存储时，`CompositeBackend` 允许你同时提供 `StateBackend` 和 `StoreBackend`
- 当你有多个信息源希望作为单个文件系统提供给 agent 时
  - 例如：长期记忆存储在 `/memories/` 下的一个 Store 中，同时有一个自定义后端在 `/docs/` 下提供文档

## 指定后端

- 将后端实例传递给 `create_deep_agent(model=..., backend=...)`。文件系统中间件将其用于所有工具。
- 后端必须实现 `BackendProtocol`（例如 `StateBackend()`、`FilesystemBackend(root_dir=".")`、`StoreBackend()`）。
- 如果省略，默认为 `StateBackend()`。

## 路由到不同后端

将命名空间的不同部分路由到不同后端。常用于持久化 `/memories/*` 而保持其他所有内容为临时。

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": FilesystemBackend(root_dir="/deepagents/myagent", virtual_mode=True),
        },
    )
)
```

行为：
- `/workspace/plan.md` → `StateBackend`（临时）
- `/memories/agent.md` → `/deepagents/myagent` 下的 `FilesystemBackend`
- `ls`、`glob`、`grep` 聚合结果并显示原始路径前缀。

注意：
- 更长的前缀优先（例如路由 `"/memories/projects/"` 可覆盖 `"/memories/"`）。
- 对于 StoreBackend 路由，确保通过 `create_deep_agent(model=..., store=...)` 提供 store 或由平台配置。

## 使用虚拟文件系统

构建自定义后端，将远程或数据库文件系统（如 S3 或 Postgres）投射到工具命名空间。

设计指南：
- 路径是绝对的（`/x/y.txt`）。决定如何将它们映射到你的存储键/行。
- 高效实现 `ls` 和 `glob`（服务器端过滤，否则本地过滤）。
- 对于外部持久化（S3、Postgres 等），在 write/edit 结果中返回 `files_update=None`（Python）或省略 `filesUpdate`（JS）——只有内存状态后端需要返回文件更新字典。
- 使用 `ls` 和 `glob` 作为方法名。
- 返回带 `error` 字段的结构化结果类型（不要抛出异常）。

## 权限

使用 [permissions（权限）](/oss/python/deepagents/permissions) 以声明式控制 agent 可读写哪些文件和目录。权限应用于内置文件系统工具，在后端被调用之前评估。

```python
from deepagents import create_deep_agent, FilesystemPermission

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: (rt.server_info.user.identity,),
            ),
            "/policies/": StoreBackend(
                namespace=lambda rt: (rt.context.org_id,),
            ),
        },
    ),
    permissions=[
        FilesystemPermission(
            operations=["write"],
            paths=["/policies/**"],
            mode="deny",
        ),
    ],
)
```

有关完整选项集（包括规则排序、子智能体权限和复合后端交互），请参见[权限指南](/oss/python/deepagents/permissions)。

## 添加策略钩子

对于超出基于路径的允许/拒绝规则的自定义验证逻辑（速率限制、审计日志、内容检查），通过子类化或包装后端来强制执行企业规则。

在选定前缀下阻止写入/编辑（子类化）：

```python
from deepagents.backends.filesystem import FilesystemBackend
from deepagents.backends.protocol import WriteResult, EditResult

class GuardedBackend(FilesystemBackend):
    def __init__(self, *, deny_prefixes: list[str], **kwargs):
        super().__init__(**kwargs)
        self.deny_prefixes = [p if p.endswith("/") else p + "/" for p in deny_prefixes]

    def write(self, file_path: str, content: str) -> WriteResult:
        if any(file_path.startswith(p) for p in self.deny_prefixes):
            return WriteResult(error=f"Writes are not allowed under {file_path}")
        return super().write(file_path, content)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        if any(file_path.startswith(p) for p in self.deny_prefixes):
            return EditResult(error=f"Edits are not allowed under {file_path}")
        return super().edit(file_path, old_string, new_string, replace_all)
```

通用包装器（适用于任何后端）：

```python
from deepagents.backends.protocol import (
    BackendProtocol, WriteResult, EditResult, LsResult, ReadResult, GrepResult, GlobResult,
)

class PolicyWrapper(BackendProtocol):
    def __init__(self, inner: BackendProtocol, deny_prefixes: list[str] | None = None):
        self.inner = inner
        self.deny_prefixes = [p if p.endswith("/") else p + "/" for p in (deny_prefixes or [])]

    def _deny(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.deny_prefixes)

    def ls(self, path: str) -> LsResult:
        return self.inner.ls(path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return self.inner.read(file_path, offset=offset, limit=limit)
    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        return self.inner.grep(pattern, path, glob)
    def glob(self, pattern: str, path: str = "/") -> GlobResult:
        return self.inner.glob(pattern, path)
    def write(self, file_path: str, content: str) -> WriteResult:
        if self._deny(file_path):
            return WriteResult(error=f"Writes are not allowed under {file_path}")
        return self.inner.write(file_path, content)
    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        if self._deny(file_path):
            return EditResult(error=f"Edits are not allowed under {file_path}")
        return self.inner.edit(file_path, old_string, new_string, replace_all)
```

## 从后端工厂迁移

> 后端工厂模式自 `deepagents` 0.5.0 起**已弃用**。请直接传递预构造的后端实例而非工厂函数。

以前，`StateBackend` 和 `StoreBackend` 等后端需要接收运行时对象的工厂函数，因为它们需要运行时上下文（状态、存储）来操作。后端现在通过 LangGraph 的 `get_config()`、`get_store()` 和 `get_runtime()` 助手在内部解析此上下文，因此你可以直接传递实例。

### 变更内容

| 之前（已弃用） | 之后 |
|---|---|
| `backend=lambda rt: StateBackend(rt)` | `backend=StateBackend()` |
| `backend=lambda rt: StoreBackend(rt)` | `backend=StoreBackend()` |
| `backend=lambda rt: CompositeBackend(default=StateBackend(rt), ...)` | `backend=CompositeBackend(default=StateBackend(), ...)` |

### 已弃用的 API

| 已弃用 | 替代方案 |
|---|---|
| 在 `create_deep_agent` 中传递可调用对象给 `backend=` | 直接传递后端实例 |
| `StateBackend(runtime)` 的 `runtime` 构造函数参数 | `StateBackend()`（无需参数） |
| `StoreBackend(runtime)` 的 `runtime` 构造函数参数 | `StoreBackend()` 或 `StoreBackend(namespace=..., store=...)` |
| `WriteResult` 和 `EditResult` 上的 `files_update` 字段 | 状态写入现在由后端内部处理 |
| 中间件 write/edit 工具中的 `Command` 包装 | 工具返回纯字符串；无需 `Command(update=...)` |

> 工厂模式在运行时仍然有效，但会发出弃用警告。请在下一个大版本之前更新代码以使用直接实例。

### 迁移示例

```python
# 之前（已弃用）
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt, namespace=lambda rt: (rt.server_info.user.identity,))},
    ),
)

# 之后
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,))},
    ),
)
```

### 从 `BackendContext` 迁移

在 `deepagents>=0.5.2`（Python）和 `deepagents>=1.9.1`（TypeScript）中，namespace 工厂直接接收 LangGraph [`Runtime`](https://reference.langchain.com/python/langgraph/runtime/Runtime)，而非 `BackendContext` 包装器。旧的 `BackendContext` 形式仍通过向后兼容的 `.runtime` 和 `.state` 访问器工作，但这些访问器会发出弃用警告，并将在 `deepagents>=0.7` 中移除。

**变更内容：**
- 工厂参数现在是 `Runtime`，而非 `BackendContext`。
- 移除 `.runtime` 访问器——例如 `ctx.runtime.context.user_id` 变为 `rt.server_info.user.identity`。
- `ctx.state` 没有直接替代方案。命名空间信息应该是只读且在运行生命周期内稳定的，而状态是可变的且随步骤变化——从中派生命名空间可能导致数据最终在不一致的键下。如果你的用例需要读取 agent 状态，请[提交 issue](https://github.com/langchain-ai/deepagents/issues)。

```python
# 之前（已弃用，在 v0.7 中移除）
StoreBackend(
    namespace=lambda ctx: (ctx.runtime.context.user_id,),
)

# 之后
StoreBackend(
    namespace=lambda rt: (rt.server_info.user.identity,),
)
```

## 协议参考

后端必须实现 [`BackendProtocol`](https://reference.langchain.com/python/deepagents/backends/protocol/BackendProtocol)。

必需方法：

- `ls(path: str) -> LsResult`
  - 返回条目，至少包含 `path`。包含 `is_dir`、`size`、`modified_at`（如可用）。按 `path` 排序以确保输出确定性。
- `read(file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult`
  - 成功时返回文件数据。文件不存在时返回 `ReadResult(error="Error: File '/x' not found")`。
- `grep(pattern: str, path: Optional[str] = None, glob: Optional[str] = None) -> GrepResult`
  - 返回结构化匹配。出错时返回 `GrepResult(error="...")`（不要抛出异常）。
- `glob(pattern: str, path: str = "/") -> GlobResult`
  - 返回匹配文件为 `FileInfo` 条目（无匹配返回空列表）。
- `write(file_path: str, content: str) -> WriteResult`
  - 仅创建。冲突时返回 `WriteResult(error=...)`。成功时设置 `path`，对于状态后端设置 `files_update={...}`；外部后端应使用 `files_update=None`。
- `edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult`
  - 强制执行 `old_string` 唯一性，除非 `replace_all=True`。找不到时返回错误。成功时包含 `occurrences`。

支持类型：
- `LsResult(error, entries)` — `entries` 成功时为 `list[FileInfo]`，失败时为 `None`。
- `ReadResult(error, file_data)` — `file_data` 成功时为 `FileData` 字典，失败时为 `None`。
- `GrepResult(error, matches)` — `matches` 成功时为 `list[GrepMatch]`，失败时为 `None`。
- `GlobResult(error, matches)` — `matches` 成功时为 `list[FileInfo]`，失败时为 `None`。
- `WriteResult(error, path, files_update)`
- `EditResult(error, path, files_update, occurrences)`
- `FileInfo` 字段：`path`（必需），可选 `is_dir`、`size`、`modified_at`。
- `GrepMatch` 字段：`path`、`line`、`text`。
- `FileData` 字段：`content`（str）、`encoding`（`"utf-8"` 或 `"base64"`）、`created_at`、`modified_at`。

---

# Sandboxes（沙箱）

> 原文：[https://docs.langchain.com/oss/python/deepagents/sandboxes](https://docs.langchain.com/oss/python/deepagents/sandboxes)

> 在隔离环境中使用沙箱后端执行代码。

Agent（智能体）生成代码、与文件系统交互并运行 shell 命令。由于我们无法预测 agent 可能做什么，其运行环境必须是隔离的，以便无法访问凭据、文件或网络。沙箱通过在 agent 执行环境与你的主机系统之间创建边界来提供这种隔离。

在 Deep Agents 中，**沙箱是 [backends（后端）](/oss/python/deepagents/backends)**，定义了 agent 运行的环境。与其他后端（State、Filesystem、Store）仅暴露文件操作不同，沙箱后端还为 agent 提供 `execute` 工具以运行 shell 命令。当你配置沙箱后端时，agent 获得：

- 所有标准文件系统工具（`ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`）
- 用于在沙箱中运行任意 shell 命令的 `execute` 工具
- 保护你的主机系统的安全边界

## 为什么使用沙箱？

沙箱用于安全。它们让 agent 能够执行任意代码、访问文件和使用网络，而不会危及你的凭据、本地文件或主机系统。当 agent 自主运行时，这种隔离至关重要。

沙箱特别适用于：

- **编码 agent**：自主运行的 agent 可以使用 shell、git、克隆仓库（许多提供商提供原生 git API，例如 [Daytona 的 git 操作](https://www.daytona.io/docs/en/git-operations/)），以及运行 Docker-in-Docker 进行构建和测试流水线。
- **数据分析 agent**：在安全的隔离环境中加载文件、安装数据分析库（pandas、numpy 等）、运行统计计算并创建输出（如 PowerPoint 演示文稿）。

> **使用 Deep Agents CLI？** CLI 内置沙箱支持，通过 `--sandbox` 标志。参见[使用远程沙箱](/oss/python/deepagents/cli/overview#use-remote-sandboxes)获取 CLI 特定的设置、标志（`--sandbox-id`、`--sandbox-setup`）和示例。

## 基本用法

这些示例假设你已使用提供商的 SDK 创建了沙箱/devbox 并设置了凭据。有关注册、身份验证和提供商特定生命周期的详情，请参见[可用提供商](#可用提供商)。

### Modal

```bash
pip install langchain-modal
# 或
uv add langchain-modal
```

```python
import modal
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from langchain_modal import ModalSandbox

app = modal.App.lookup("your-app")
modal_sandbox = modal.Sandbox.create(app=app)
backend = ModalSandbox(sandbox=modal_sandbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    system_prompt="你是一个具有沙箱访问权限的 Python 编码助手。",
    backend=backend,
)
try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个小型 Python 包并运行 pytest",
                }
            ]
        }
    )
finally:
    modal_sandbox.terminate()
```

### Runloop

```bash
pip install langchain-runloop
# 或
uv add langchain-runloop
```

```python
import os
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from langchain_runloop import RunloopSandbox
from runloop_api_client import RunloopSDK

client = RunloopSDK(bearer_token=os.environ["RUNLOOP_API_KEY"])
devbox = client.devbox.create()
backend = RunloopSandbox(devbox=devbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    system_prompt="你是一个具有沙箱访问权限的 Python 编码助手。",
    backend=backend,
)

try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个小型 Python 包并运行 pytest",
                }
            ]
        }
    )
finally:
    devbox.shutdown()
```

### Daytona

```bash
pip install langchain-daytona
# 或
uv add langchain-daytona
```

```python
from daytona import Daytona
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from langchain_daytona import DaytonaSandbox

sandbox = Daytona().create()
backend = DaytonaSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    system_prompt="你是一个具有沙箱访问权限的 Python 编码助手。",
    backend=backend,
)

try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个小型 Python 包并运行 pytest",
                }
            ]
        }
    )
finally:
    sandbox.stop()
```

### LangSmith

> LangSmith 沙箱目前处于私有 beta 阶段。

```bash
pip install "langsmith[sandbox]"
# 或
uv add "langsmith[sandbox]"
```

```python
from deepagents import create_deep_agent
from deepagents.backends import LangSmithSandbox
from langchain_anthropic import ChatAnthropic
from langsmith.sandbox import SandboxClient

client = SandboxClient()
ls_sandbox = client.create_sandbox(template_name="my-template")
backend = LangSmithSandbox(sandbox=ls_sandbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    system_prompt="你是一个具有沙箱访问权限的 Python 编码助手。",
    backend=backend,
)
try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个小型 Python 包并运行 pytest",
                }
            ]
        }
    )
finally:
    client.delete_sandbox(ls_sandbox.name)
```

## 可用提供商

有关提供商特定设置、身份验证和生命周期的详情，请参见[沙箱集成](/oss/python/integrations/sandboxes)。

未看到你的提供商？你可以实现自己的沙箱后端。参见[贡献沙箱集成](/oss/python/contributing/integrations-langchain)。

## 生命周期和作用域

沙箱在关闭之前会消耗资源并产生费用。如何管理它们的生命周期取决于你的应用程序。

选择沙箱生命周期如何映射到你的应用程序资源。有关此决策的更多信息，请参见[投入生产](/oss/python/deepagents/going-to-production#sandboxes)。

### 线程作用域（默认）

每个对话获得自己的沙箱。沙箱在第一次运行开始时创建，并在同一线程的后续消息中重用。当线程被清理（或沙箱 TTL 过期）时，沙箱被销毁。这是大多数 agent 的正确默认值。

示例：一个数据分析机器人，每个对话从干净的环境开始。

### Assistant 作用域

给定 [assistant](/langsmith/assistants) 的所有线程共享一个沙箱。沙箱 ID 存储在 assistant 的配置中，因此每次对话都返回相同的环境。文件、已安装的包和克隆的仓库在对话之间持久。当 agent 维护一个长期运行的工作区时使用此模式。

示例：一个在对话之间维护克隆仓库和已安装依赖的编码助手。

> Assistant 作用域的沙箱会随时间累积文件、已安装的包和其他沙箱内状态。为你的沙箱提供商配置 TTL，定期使用快照重置，或实现清理逻辑以防止沙箱磁盘和内存无限增长。线程作用域沙箱通过每次对话重新开始来避免此问题。

### 基本生命周期

```python
# Daytona
from daytona import Daytona
from langchain_daytona import DaytonaSandbox

sandbox = Daytona().create()
backend = DaytonaSandbox(sandbox=sandbox)
result = backend.execute("echo hello")
# ... 使用沙箱
sandbox.stop()
```

```python
# Modal
import modal
from langchain_modal import ModalSandbox

app = modal.App.lookup("your-app")
modal_sandbox = modal.Sandbox.create(app=app)
backend = ModalSandbox(sandbox=modal_sandbox)
result = backend.execute("echo hello")
# ... 使用沙箱
modal_sandbox.terminate()
```

```python
# Runloop
from runloop_api_client import RunloopSDK
from langchain_runloop import RunloopSandbox

client = RunloopSDK(bearer_token="...")
devbox = client.devbox.create()
backend = RunloopSandbox(devbox=devbox)
result = backend.execute("echo hello")
# ... 使用沙箱
devbox.shutdown()
```

```python
# AgentCore
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from langchain_agentcore_codeinterpreter import AgentCoreSandbox

interpreter = CodeInterpreter(region="us-west-2")
interpreter.start()
backend = AgentCoreSandbox(interpreter=interpreter)
result = backend.execute("echo hello")
# ... 使用沙箱
interpreter.stop()
```

```python
# LangSmith
from langsmith.sandbox import SandboxClient
from deepagents.backends.langsmith import LangSmithSandbox

client = SandboxClient()
ls_sandbox = client.create_sandbox(template_name="deepagents-deploy")
backend = LangSmithSandbox(sandbox=ls_sandbox)
result = backend.execute("echo hello")
# ... 使用沙箱
client.delete_sandbox(backend.id)
```

### 每次对话的生命周期

在聊天应用程序中，对话通常由 `thread_id` 表示。通常，每个 `thread_id` 应使用其唯一的沙箱。

将沙箱 ID 和 `thread_id` 之间的映射存储在你的应用程序中，或在沙箱提供商允许将元数据附加到沙箱时与沙箱一起存储。

> **聊天应用程序的 TTL。** 当用户可以在空闲时间后重新参与时，你通常不知道他们是否会或何时返回。在沙箱上配置存活时间（TTL）——例如 TTL 到归档或 TTL 到删除——以便提供商自动清理空闲沙箱。许多沙箱提供商支持此功能。

以下示例展示了使用 Daytona 的 get-or-create 模式。对于其他提供商，请参阅沙箱提供商 API 获取等效的标签、元数据和 TTL 选项：

```python
from langchain_core.utils.uuid import uuid7
from daytona import CreateSandboxFromSnapshotParams, Daytona
from deepagents import create_deep_agent
from langchain_daytona import DaytonaSandbox

client = Daytona()
thread_id = str(uuid7())

# 通过 thread_id 获取或创建沙箱
try:
    sandbox = client.find_one(labels={"thread_id": thread_id})
except Exception:
    params = CreateSandboxFromSnapshotParams(
        labels={"thread_id": thread_id},
        # 添加 TTL 以便在空闲时清理沙箱
        auto_delete_interval=3600,
    )
    sandbox = client.create(params)

backend = DaytonaSandbox(sandbox=sandbox)
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=backend,
    system_prompt="你是一个具有沙箱访问权限的编码助手。你可以在沙箱中创建和运行代码。",
)

try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个 hello world Python 脚本并运行它",
                }
            ]
        },
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )
    print(result["messages"][-1].content)
except Exception:
    # 可选：在异常时主动删除沙箱
    client.delete(sandbox)
    raise
```

## 集成模式

有两种架构模式用于将 agent 与沙箱集成，取决于 agent 运行的位置。

### Agent 在沙箱内模式

Agent 在沙箱内部运行，你通过网络与其通信。你构建一个预装了 agent 框架的 Docker 或 VM 镜像，在沙箱内运行它，然后从外部连接以发送消息。

优点：
- ✅ 接近本地开发体验。
- ✅ Agent 与环境紧密耦合。

权衡：
- 🔴 API 密钥必须存在于沙箱内（安全风险）。
- 🔴 更新需要重建镜像。
- 🔴 需要通信基础设施（WebSocket 或 HTTP 层）。

要在沙箱内运行 agent，构建镜像并安装 deepagents：

```dockerfile
FROM python:3.11
RUN pip install deepagents-cli
```

然后在沙箱内运行 agent。要在沙箱内使用 agent，你必须添加额外基础设施来处理你的应用程序与沙箱内 agent 之间的通信。

### 沙箱作为工具模式

Agent 在你的机器或服务器上运行。当需要执行代码时，它调用沙箱工具（如 `execute`、`read_file` 或 `write_file`），这些工具调用提供商的 API 在远程沙箱中运行操作。

优点：
- ✅ 即时更新 agent 代码，无需重建镜像。
- ✅ Agent 状态与执行之间更清晰的分离。
  - API 密钥保留在沙箱外。
  - 沙箱故障不会丢失 agent 状态。
  - 可选择在多个沙箱中并行运行任务。
- ✅ 仅按执行时间付费。

权衡：
- 🔴 每次执行调用都有网络延迟。

```python
from daytona import Daytona
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_daytona import DaytonaSandbox

load_dotenv()

# 也可以使用 AgentCore、E2B、Runloop、Modal
sandbox = Daytona().create()
backend = DaytonaSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=backend,
    system_prompt="你是一个具有沙箱访问权限的编码助手。你可以在沙箱中创建和运行代码。",
)

try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "创建一个 hello world Python 脚本并运行它",
                }
            ]
        }
    )
    print(result["messages"][-1].content)
except Exception:
    # 可选：在异常时主动停止沙箱
    sandbox.stop()
    raise
```

本文档中的示例使用沙箱作为工具模式。当你的提供商的 SDK 处理通信层且你希望生产环境接近本地开发时，选择 agent 在沙箱内模式。当你需要快速迭代 agent 逻辑、将 API 密钥保留在沙箱外或更喜欢关注点更清晰分离时，选择沙箱作为工具模式。

## 沙箱如何工作

### 隔离边界

所有沙箱提供商都保护你的主机系统免受 agent 的文件系统和 shell 操作影响。Agent 无法读取你的本地文件、访问你机器上的环境变量或干扰其他进程。但是，仅靠沙箱**不能**防止：

- **上下文注入**：控制 agent 输入部分的攻击者可以指示它在沙箱内运行任意命令。沙箱是隔离的，但 agent 在其中拥有完全控制权。
- **网络外泄**：除非阻止网络访问，否则上下文注入的 agent 可以通过 HTTP 或 DNS 将数据从沙箱发送出去。一些提供商支持阻止网络访问（例如 Modal 上的 `blockNetwork: true`）。

参见[安全注意事项](#安全注意事项)了解如何处理密钥并缓解这些风险。

### `execute` 方法

沙箱后端架构简单：提供商必须实现的唯一方法是 `execute()`，它运行 shell 命令并返回其输出。所有其他文件系统操作（`read`、`write`、`edit`、`ls`、`glob`、`grep`）都由 [`BaseSandbox`](https://reference.langchain.com/python/deepagents/backends/sandbox/BaseSandbox) 基类在 `execute()` 之上构建，该类构造脚本并通过 `execute()` 在沙箱内运行它们。

这意味着：
- **添加新提供商很简单。** 实现 `execute()`——基类处理其余一切。
- **`execute` 工具是有条件可用的。** 在每次模型调用时，harness 检查后端是否实现了 [`SandboxBackendProtocol`](https://reference.langchain.com/python/deepagents/backends/protocol/SandboxBackendProtocol)。如果没有，工具被过滤掉，agent 永远看不到它。

当 agent 调用 `execute` 工具时，它提供 `command` 字符串并获取组合的 stdout/stderr、退出代码，以及输出过大时的截断通知。

你也可以在应用程序代码中直接调用后端 `execute()` 方法。

### 文件访问的两个层面

文件进出沙箱有两种截然不同的方式，了解何时使用每种方式很重要：

**Agent 文件系统工具**：`read_file`、`write_file`、`edit_file`、`ls`、`glob`、`grep` 和 `execute` 是 LLM 在执行期间调用的工具。这些在沙箱内通过 `execute()` 运行。Agent 使用它们来读取代码、写入文件并在任务中运行命令。

**文件传输 API**：你的应用程序代码调用的 `uploadFiles()` 和 `downloadFiles()` 方法。这些使用提供商的原生文件传输 API（而非 shell 命令），旨在在你的主机环境和沙箱之间移动文件。使用它们来：
- **预置沙箱**：在 agent 运行之前用源代码、配置或数据填充沙箱
- **检索产物**：在 agent 完成后检索生成的代码、构建输出、报告
- **预填充依赖**：agent 需要的依赖

## 处理文件

Deepagents 沙箱后端支持文件传输 API，用于在你的应用程序和沙箱之间移动文件。

### 预置沙箱

使用 `upload_files()` 在 agent 运行之前填充沙箱。路径必须是绝对路径，内容为 `bytes`：

```python
backend.upload_files(
    [
        ("/src/index.py", b"print('Hello')\n"),
        ("/pyproject.toml", b"[project]\nname = 'my-app'\n"),
    ]
)
```

### 检索产物

使用 `download_files()` 在 agent 完成后从沙箱检索文件：

```python
results = backend.download_files(["/src/index.py", "/output.txt"])
for result in results:
    if result.content is not None:
        print(f"{result.path}: {result.content.decode()}")
    else:
        print(f"Failed to download {result.path}: {result.error}")
```

> 在沙箱内部，agent 使用文件系统工具（`read_file`、`write_file`）。`upload_files` 和 `download_files` 方法用于你的应用程序代码在主机和沙箱之间移动文件。

## 安全注意事项

沙箱将代码执行与你的主机系统隔离，但它们不能防止**上下文注入**。控制 agent 输入部分的攻击者可以指示它读取文件、运行命令或从沙箱内外泄数据。这使得沙箱内的凭据特别危险。

> **永远不要在沙箱内放置密钥。** 注入沙箱的 API 密钥、令牌、数据库凭据和其他密钥（通过环境变量、挂载文件或 `secrets` 选项）可以被上下文注入的 agent 读取和外泄。这甚至适用于短期或有范围的凭据——如果 agent 可以访问它们，攻击者也可以。

### 安全处理密钥

如果你的 agent 需要调用经过身份验证的 API 或访问受保护的资源，你有两个选择：

1. **将密钥保留在沙箱外的工具中。** 定义在你的主机环境中运行（而非沙箱内）的工具并在那里处理身份验证。Agent 按名称调用这些工具，但永远看不到凭据。这是推荐的方法。

2. **使用注入凭据的网络代理。** 一些沙箱提供商支持拦截来自沙箱的传出 HTTP 请求并附加凭据（例如 `Authorization` 标头）后再转发。Agent 永远看不到密钥——它只是向 URL 发出普通请求。这种方法尚未在提供商中广泛可用。

> 如果你必须向沙箱注入密钥（不推荐），请采取以下预防措施：
> - 为**所有**工具调用启用 [human-in-the-loop](/oss/python/deepagents/human-in-the-loop) 审批，而不仅仅是敏感工具
> - 阻止或限制从沙箱的网络访问以限制外泄路径
> - 使用最窄的凭据范围和最短的存活时间
> - 监控沙箱网络流量中的异常出站请求
>
> 即使有这些安全保障，这仍然是不安全的变通方法。足够有创意的上下文注入攻击可以绕过输出过滤和 HITL 审查。

### 一般最佳实践

- 在应用程序中对沙箱输出进行审查后再采取行动
- 在不需要时阻止沙箱网络访问
- 使用 [middleware（中间件）](/oss/python/langchain/middleware) 过滤或编辑工具输出中的敏感模式
- 将沙箱内产生的所有内容视为不可信输入

---

# Permissions（权限）

> 原文：[https://docs.langchain.com/oss/python/deepagents/permissions](https://docs.langchain.com/oss/python/deepagents/permissions)

> 使用文件系统权限规则控制 agent（智能体）对文件和目录的访问。

文件系统权限为 agent（智能体）可读写哪些路径提供**声明式控制**。与中间件中的命令式策略（策略钩子）不同，文件系统权限是声明性的：你指定允许/拒绝哪些操作和哪些路径，权限系统为你强制执行。

它们用于实现诸如"agent 可以写入 `/workspace` 但不能写入 `/secrets`"或"所有子智能体对 `/public/*` 有只读权限"等场景。

## 快速开始

将 [`FilesystemPermission`](https://reference.langchain.com/python/deepagents/permissions/FilesystemPermission) 对象列表传递给 `create_deep_agent` 上的 `permissions` 参数：

```python
from deepagents import create_deep_agent, FilesystemPermission

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    permissions=[
        FilesystemPermission(
            operations=["write", "edit"],
            paths=["/workspace/**"],
        ),
        FilesystemPermission(
            operations=["read", "write", "edit"],
            paths=["/secrets/**"],
            mode="deny",
        ),
    ],
)
```

在此配置中，agent 可以对 `/workspace` 中的文件执行 `write` 和 `edit` 操作，但会被阻止对 `/secrets` 目录执行任何操作。

> 权限应用于**内置文件系统工具**（`read_file`、`write_file`、`edit_file`、`ls`、`glob`、`grep`）。要控制 `execute` 工具的权限，请改用中间件（例如 [`HumanInTheLoopMiddleware`](/oss/python/deepagents/human-in-the-loop)）。

## FilesystemPermission 选项

每个权限由以下字段定义：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `operations` | `list[Literal["read", "write", "edit"]]` | 必需 | 此规则适用的操作。 |
| `paths` | `list[str]` | 必需 | 此规则适用的路径。支持 `**` glob 模式。必须使用绝对路径。 |
| `mode` | `Literal["allow", "deny"]` | `"allow"` | 权限模式。使用 `"deny"` 阻止特定操作。 |
| `description` | `str` | `""` | 规则的人类可读描述。当向 agent 解释权限限制时用于上下文。 |
| `agents` | `Literal["supervisor", "subagent"]` | `"supervisor"` | 此规则适用的 agent。使用 `"subagent"` 来限制规则仅对子智能体生效。 |

## 规则排序

规则按**顺序评估**——第一条匹配的规则生效。将拒绝规则放在允许规则之前以实现更严格的限制，或在允许规则之后放置拒绝规则以创建例外。

```python
permissions=[
    # 允许对整个 workspace 的读写
    FilesystemPermission(operations=["read", "write"], paths=["/workspace/**"]),
    # 但在 config 子目录中只允许读
    FilesystemPermission(operations=["write"], paths=["/workspace/config/**"], mode="deny"),
]
```

## 子智能体权限

默认情况下，权限应用于 supervisor agent（主管智能体）。使用 `agents="subagent"` 将规则限定到子智能体：

```python
permissions=[
    # Supervisor 可以读写一切
    FilesystemPermission(operations=["read", "write", "edit"], paths=["/**"]),
    # 子智能体只能读取 /public 和 /workspace
    FilesystemPermission(
        operations=["read", "write"],
        paths=["/public/**", "/workspace/**"],
        agents="subagent",
    ),
]
```

使用子智能体权限来：
- 将子智能体限制在文件系统的特定部分
- 允许子智能体写入暂存区但防止覆盖关键文件
- 为每个子智能体创建不同的权限范围

## 与复合后端交互

权限评估应用于后端解析文件路径**之前**。当使用 [`CompositeBackend`](/oss/python/deepagents/backends#compositebackend-路由器) 时，权限规则针对 agent 看到的原始路径进行评估。

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.permissions import FilesystemPermission

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": StoreBackend()},
    ),
    permissions=[
        # 此规则应用于 agent 看到的 "/memories/" 前缀
        FilesystemPermission(
            operations=["write"],
            paths=["/memories/readonly/**"],
            mode="deny",
        ),
    ],
)
```

权限不知道后端路由——它只看到 agent 请求的路径。路由仍然决定哪个后端处理操作。

---

# Human-in-the-loop（人在回路中）

> 原文：[https://docs.langchain.com/oss/python/deepagents/human-in-the-loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop)

> 在 agent（智能体）采取行动之前进行人工审批。

Deep agents（深度智能体）通过 LangGraph 的内置中断系统支持 **human-in-the-loop（人在回路中，HITL）**。当 agent 尝试执行需要审批的操作时，执行暂停，等待人工决定后再继续。

## 快速开始

在 `create_deep_agent` 中使用 `interrupt_on` 参数指定哪些工具调用应触发中断：

```python
from deepagents import create_deep_agent
from deepagents.middleware.hitl import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    middleware=[
        HumanInTheLoopMiddleware(
            rules=[
                {"tools": "write_file"},
                {"tools": "edit_file"},
                {"tools": "execute"},
            ],
        ),
    ],
    checkpointer=MemorySaver(),
)
```

你需要配置一个 `checkpointer`（检查点）来持久化 agent 状态，以便在中断和恢复之间保存。

## HumanInTheLoopMiddleware 选项

每条规则支持以下字段：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `tools` | `str \| list[str]` | 必需 | 应触发中断的工具名称。支持通配符（`"*"` 表示全部）。 |
| `decisions` | `list[str]` | `["approve", "edit", "reject"]` | 人工可做的决定类型。 |
| `description` | `str` | `""` | 在审批提示中显示的人类可读描述。 |

决定类型：
- **`"approve"`** — 使用原始参数执行工具。
- **`"edit"`** — 修改参数后再执行。
- **`"reject"`** — 跳过工具调用，向 agent 返回拒绝响应。

## 示例

### 特定工具

```python
from deepagents.middleware.hitl import HumanInTheLoopMiddleware

middleware = HumanInTheLoopMiddleware(
    rules=[
        {"tools": ["write_file", "edit_file"], "decisions": ["approve", "reject"]},
        {"tools": "execute", "description": "Shell execution — review before running"},
    ],
)
```

### 所有工具

```python
middleware = HumanInTheLoopMiddleware(
    rules=[
        {"tools": "*", "decisions": ["approve", "reject"]},
    ],
)
```

### 多个规则

```python
middleware = HumanInTheLoopMiddleware(
    rules=[
        {"tools": "write_file", "decisions": ["approve"]},
        {"tools": "edit_file", "decisions": ["approve", "edit"]},
        {"tools": "execute", "decisions": ["approve", "edit", "reject"]},
    ],
)
```

## 与 CLI 一起使用

Deep Agents CLI 内置 HITL 支持。在交互模式中，可能具有破坏性的操作（写入文件、编辑、执行 shell 命令）需要确认。

使用 `-y` 或 `--auto-approve` 跳过审批：

```bash
deepagents -y
# 或
deepagents --auto-approve
```

## 高级：可编程 HITL

你可以实现自定义审批逻辑，而非对所有调用统一要求审批：

```python
from deepagents.middleware.hitl import HumanInTheLoopMiddleware, HitlDecision

def should_interrupt(tool_call):
    """仅在写入敏感文件时中断"""
    if tool_call.get("name") == "write_file":
        args = tool_call.get("args", {})
        path = args.get("path", "")
        return "/secrets/" in path or ".env" in path
    return False

middleware = HumanInTheLoopMiddleware(
    rules=[
        {
            "tools": ["write_file", "edit_file"],
            "should_interrupt": should_interrupt,
            "description": "Review writes to sensitive paths",
        },
    ],
)
```

`should_interrupt` 函数接收工具调用字典并返回 `bool`。仅在返回 `True` 时触发中断。

---

# Skills（技能）

> 原文：[https://docs.langchain.com/oss/python/deepagents/skills](https://docs.langchain.com/oss/python/deepagents/skills)

> 了解如何使用技能（skills（技能））扩展 deep agent（深度智能体）的能力。

技能（Skills）是可复用的 agent（智能体）能力，提供专门的工作流和领域知识。

你可以使用 [Agent Skills](https://agentskills.io/) 为 deep agent 提供新能力和专业知识。关于提升 agent 在 LangChain 生态系统任务上性能的即用型技能，请参见 [LangChain Skills](https://github.com/langchain-ai/langchain-skills) 仓库。

Deep agent 技能遵循 [Agent Skills 规范](https://agentskills.io/specification)。

## 什么是技能

技能是文件夹目录，每个文件夹包含一个或多个文件，其中包含 agent 可使用的上下文：

- 一个 `SKILL.md` 文件，包含技能的指令和元数据
- 额外的脚本（可选）
- 额外的参考信息，如文档（可选）
- 额外的资源，如模板和其他资源（可选）

> 任何额外的资源（脚本、文档、模板或其他资源）必须在 `SKILL.md` 文件中引用，并包含文件内容和使用方法的信息，以便 agent 可以决定何时使用它们。

## 技能如何工作

当你创建 deep agent 时，你可以传入包含技能的目录列表。当 agent 启动时，它会读取每个 `SKILL.md` 文件的 frontmatter（前元数据）。

当 agent 收到提示时，agent 会检查是否可以在完成提示时使用任何技能。如果找到匹配的提示，它会然后审查其余技能文件。这种仅在需要时才审查技能信息的模式称为**渐进式披露（progressive disclosure（渐进式披露））**。

## 示例

你可能有一个技能文件夹，其中包含使用特定文档网站的技能，以及另一个搜索 arXiv 预印本研究论文库的技能：

```
skills/
├── langgraph-docs
│   └── SKILL.md
└── arxiv_search
    ├── SKILL.md
    └── arxiv_search.py # 用于搜索 arXiv 的代码
```

`SKILL.md` 文件始终遵循相同的模式，以 frontmatter 中的元数据开头，后跟技能指令。

以下示例展示了在提示时提供相关 langgraph 文档的技能：

```md
---
name: langgraph-docs
description: 使用此技能获取 LangGraph 相关请求，以获取相关文档并提供准确、最新的指导。
---

# langgraph-docs

## 概述

此技能说明如何访问 LangGraph Python 文档，以帮助回答问题并指导实现。

## 指令

### 1. 获取文档索引

使用 fetch_url 工具读取以下 URL：
https://docs.langchain.com/llms.txt

这提供了所有可用文档的结构化列表及描述。

### 2. 选择相关文档

根据问题，从索引中识别 2-4 个最相关的文档 URL。优先：
- 实现问题的具体操作指南
- 理解问题的核心概念页面
- 端到端示例教程
- API 详情的参考文档

### 3. 获取选定的文档

使用 fetch_url 工具读取选定的文档 URL。

### 4. 提供准确指导

阅读文档后，完成用户的请求。
```

更多示例技能，请参见 [Deep Agents 示例技能](https://github.com/langchain-ai/deepagents/tree/main/libs/cli/examples/skills)。

> **重要**
>
> 请参考完整的 [Agent Skills 规范](https://agentskills.io/specification) 获取编写技能文件时的约束和最佳实践。特别是：
>
> - `description` 字段如果超过 1024 个字符会被截断。
> - 在 Deep Agents 中，`SKILL.md` 文件必须小于 10 MB。超过此限制的文件在技能加载时会被跳过。

### 完整示例

以下示例展示了使用所有可用 frontmatter 字段的 `SKILL.md` 文件：

```md
---
name: langgraph-docs
description: 使用此技能获取 LangGraph 相关请求，以获取相关文档并提供准确、最新的指导。
license: MIT
compatibility: 需要互联网访问以获取文档 URL
metadata:
  author: langchain
  version: "1.0"
allowed-tools: fetch_url
---

# langgraph-docs

## 概述

此技能说明如何访问 LangGraph Python 文档，以帮助回答问题并指导实现。

## 指令

### 1. 获取文档索引

使用 fetch_url 工具读取以下 URL：
https://docs.langchain.com/llms.txt

这提供了所有可用文档的结构化列表及描述。

### 2. 选择相关文档

根据问题，从索引中识别 2-4 个最相关的文档 URL。优先：
- 实现问题的具体操作指南
- 理解问题的核心概念页面
- 端到端示例教程
- API 详情的参考文档

### 3. 获取选定的文档

使用 fetch_url 工具读取选定的文档 URL。

### 4. 提供准确指导

阅读文档后，完成用户的请求。
```

## 用法

创建 deep agent 时传入技能目录：

```python
from urllib.request import urlopen
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

skill_url = "https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/main/libs/cli/examples/skills/langgraph-docs/SKILL.md"
with urlopen(skill_url) as response:
    skill_content = response.read().decode('utf-8')

skills_files = {
    "/skills/langgraph-docs/SKILL.md": create_file_data(skill_content)
}

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    skills=["/skills/"],
    checkpointer=checkpointer,
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "What is langgraph?",
            }
        ],
        # 为默认 StateBackend 的内存文件系统播种（虚拟路径必须以 "/" 开头）。
        "files": skills_files
    },
    config={"configurable": {"thread_id": "12345"}},
)
```

使用 StoreBackend：

```python
from urllib.request import urlopen
from deepagents import create_deep_agent
from deepagents.backends import StoreBackend
from deepagents.backends.utils import create_file_data
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

skill_url = "https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/main/libs/cli/examples/skills/langgraph-docs/SKILL.md"
with urlopen(skill_url) as response:
    skill_content = response.read().decode('utf-8')

store.put(
    namespace=("filesystem",),
    key="/skills/langgraph-docs/SKILL.md",
    value=create_file_data(skill_content)
)

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=StoreBackend(),
    store=store,
    skills=["/skills/"]
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "What is langgraph?",
            }
        ]
    },
    config={"configurable": {"thread_id": "12345"}},
)
```

使用 FilesystemBackend：

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents.backends.filesystem import FilesystemBackend

checkpointer = MemorySaver()

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    backend=FilesystemBackend(root_dir="/Users/user/{project}"),
    skills=["/Users/user/{project}/skills/"],
    interrupt_on={
        "write_file": True,
        "read_file": False,
        "edit_file": True
    },
    checkpointer=checkpointer,
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "What is langgraph?",
            }
        ]
    },
    config={"configurable": {"thread_id": "12345"}},
)
```

> `skills` 参数（类型 `list[str]`，可选）：技能源路径列表。路径必须使用正斜杠，且相对于后端的根目录。
>
> - 如果省略，不加载任何技能。
> - 使用 `StateBackend`（默认）时，通过 `invoke(files={...})` 提供技能文件。使用 `deepagents.backends.utils` 中的 `create_file_data()` 格式化文件内容；不支持原始字符串。
> - 使用 `FilesystemBackend` 时，技能从磁盘相对于后端的 `root_dir` 加载。
>
> 后面的源覆盖前面的源，同名技能以后者为准。

> SDK 仅加载你在 `skills` 中传入的源。它不会自动扫描 CLI 目录如 `~/.deepagents/...` 或 `~/.agents/...`。
>
> 关于 CLI 存储约定，请参见 [应用数据](/oss/python/deepagents/data-locations)。

## 源优先级

当多个技能源包含同名的技能时，`skills` 数组中后面列出的源中的技能优先（后者胜出）。这让你可以从不同来源分层加载技能。

```python
# 如果两个源都包含名为 "web-search" 的技能，
# "/skills/project/" 中的技能胜出（最后加载）。
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    skills=["/skills/user/", "/skills/project/"],
    ...
)
```

## 子智能体的技能

当你使用 [subagents（子智能体）](/oss/python/deepagents/subagents) 时，你可以配置每种类型可以访问哪些技能：

- **通用子智能体**：当你向 `create_deep_agent` 传递 `skills` 时，自动继承主 agent 的技能。无需额外配置。
- **自定义子智能体**：不继承主 agent 的技能。在每个子智能体定义中添加 `skills` 参数，包含该子智能体的技能源路径。

技能状态完全隔离：主 agent 的技能对子智能体不可见，子智能体的技能对主 agent 不可见。

```python
from deepagents import create_deep_agent

research_subagent = {
    "name": "researcher",
    "description": "具有专门技能的研究助手",
    "system_prompt": "你是一个研究员。",
    "tools": [web_search],
    "skills": ["/skills/research/", "/skills/web-search/"],  # 子智能体专用技能
}

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    skills=["/skills/main/"],  # 主 agent 和通用子智能体获得这些
    subagents=[research_subagent],  # 研究者只获得自己的技能
)
```

有关子智能体配置和技能继承的更多信息，请参见 [Subagents（子智能体）](/oss/python/deepagents/subagents)。

## Agent 看到什么

配置技能后，"Skills System（技能系统）"部分会注入到 agent 的系统提示词中。Agent 使用此信息遵循三步流程：

1. **匹配（Match）**——当用户提示到达时，agent 检查是否有任何技能的描述与任务匹配。
2. **读取（Read）**——如果技能适用，agent 使用其技能列表中显示的路径读取完整的 `SKILL.md` 文件。
3. **执行（Execute）**——agent 遵循技能指令，并根据需要访问任何支持文件（脚本、模板、参考文档）。

> 在 `SKILL.md` frontmatter 中编写清晰、具体的描述。Agent 仅基于描述决定是否使用技能——详细的描述带来更好的技能匹配。

## 在沙箱中执行技能脚本

技能可以在 `SKILL.md` 文件旁边包含脚本，例如执行搜索或数据转换的 Python 文件。Agent 可以从任何后端**读取**这些脚本，但要**执行**它们，agent 需要访问 shell——只有 [沙箱后端](/oss/python/deepagents/sandboxes) 提供。

当你使用 [CompositeBackend](https://reference.langchain.com/python/deepagents/backends/composite/CompositeBackend) 将技能路由到 [StoreBackend](https://reference.langchain.com/python/deepagents/backends/store/StoreBackend) 进行持久化，同时使用沙箱作为默认后端时，技能文件存在于存储中，而非代码运行的沙箱中。为了让沙箱能够使用脚本，你必须使用 [自定义中间件](/oss/python/langchain/middleware/custom) 在 agent 启动之前将技能脚本上传到沙箱中：

```python
import asyncio
from pathlib import Path
from typing import Any

from daytona import Daytona
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from deepagents.backends.utils import create_file_data
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_daytona import DaytonaSandbox
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

# 每个用户的相同技能包：一个共享存储命名空间。
SKILLS_SHARED_NAMESPACE = ("skills", "builtin")


class SkillSandboxSyncMiddleware(AgentMiddleware[AgentState, Any, Any]):
    """在每次 agent 运行之前，将共享技能文件从存储复制到沙箱中。"""

    def __init__(self, backend: CompositeBackend) -> None:
        super().__init__()
        self.backend = backend

    async def abefore_agent(self, state: AgentState, runtime: Runtime[Any]) -> None:
        store = runtime.store

        files: list[tuple[str, bytes]] = []
        for item in await store.asearch(SKILLS_SHARED_NAMESPACE):
            key = str(item.key)
            if ".." in key or any(c in key for c in ("*", "?")):
                msg = f"Invalid key: {key}"
                raise ValueError(msg)
            normalized = key if key.startswith("/") else f"/{key}"
            # CompositeBackend 将路径路由并批量上传到正确的后端。
            files.append((f"/skills{normalized}", item.value["content"].encode()))

        if files:
            await self.backend.aupload_files(files)


async def seed_skill_store(store: InMemoryStore) -> None:
    """将规范技能文件从磁盘加载到共享存储命名空间（部署时运行一次）。"""
    skills_dir = Path(__file__).resolve().parent / "skills"
    for file_path in sorted(p for p in skills_dir.rglob("*") if p.is_file()):
        rel = file_path.relative_to(skills_dir).as_posix()
        key = f"/{rel}"
        await store.aput(
            SKILLS_SHARED_NAMESPACE,
            key,
            create_file_data(file_path.read_text(encoding="utf-8")),
        )


async def main() -> None:
    store = InMemoryStore()
    await seed_skill_store(store)

    daytona = Daytona()
    sandbox = daytona.create()
    sandbox_backend = DaytonaSandbox(sandbox=sandbox)

    backend = CompositeBackend(
        default=sandbox_backend,
        routes={
            "/skills/": StoreBackend(
                store=store,
                namespace=lambda _rt: SKILLS_SHARED_NAMESPACE,
            ),
        },
    )

    try:
        agent = create_deep_agent(
            model="google_genai:gemini-3.1-pro-preview",
            backend=backend,
            skills=["/skills/"],
            store=store,
            middleware=[SkillSandboxSyncMiddleware(backend)],
        )
    finally:
        sandbox.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

中间件的 `before_agent` 钩子在每次 agent 调用之前运行，从共享命名空间读取技能文件并上传到沙箱文件系统。同步完成后，agent 可以像沙箱中的任何其他文件一样使用 `execute` 工具执行脚本。

## 技能与内存

技能（Skills）和 [内存](/oss/python/deepagents/customization#memory)（`AGENTS.md` 文件）服务于不同目的：

| | 技能（Skills） | 内存（Memory） |
|---|---|---|
| **目的** | 按需能力，通过渐进式披露发现 | 启动时始终加载的持久化上下文 |
| **加载** | 仅在 agent 确定相关性时读取 | 始终注入系统提示词 |
| **格式** | 命名目录中的 `SKILL.md` | `AGENTS.md` 文件 |
| **分层** | 用户 → 项目（后者胜出） | 用户 → 项目（合并） |
| **使用场景** | 指令是任务特定且可能较大的 | 上下文始终相关（项目规范、偏好） |

## 何时使用技能和工具

以下是一些使用工具和技能的一般指南：

- 当有大量上下文时，使用技能以减少系统提示词中的 token 数量。
- 使用技能将能力打包成更大的操作，并提供超出单个工具描述的额外上下文。
- 如果 agent 无法访问文件系统，则使用工具。

---

# Context engineering in Deep Agents（Deep Agents 中的上下文工程）

> 原文：[https://docs.langchain.com/oss/python/deepagents/context-engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)

> 控制你的 deep agent（深度智能体）可以访问哪些上下文，以及如何在长时间运行的任务中管理上下文。

上下文工程（Context engineering（上下文工程））是以正确的格式提供正确的信息和工具，使你的 deep agent 能够可靠地完成任务。

Deep agents 可以访问多种类型的上下文。有些来源在 agent 启动时提供；其他来源在运行时变得可用，例如用户输入。Deep agents 包含内置机制来管理长时间运行会话的上下文。

本页概述你的 deep agent 可以访问和管理的不同类型上下文。

> 刚接触上下文工程？请参见[概念概述](/oss/python/concepts/context)了解不同类型的上下文及其使用时机。

## 上下文类型

| 上下文类型 | 你控制的内容 | 范围 |
|---|---|---|
| **[输入上下文](#输入上下文)** | 启动时进入 agent 提示词的内容（系统提示词、内存、技能） | 静态，每次运行应用 |
| **[运行时上下文](#运行时上下文)** | 调用时传入的静态配置（用户元数据、API 密钥、连接） | 每次运行，传播到子智能体 |
| **[上下文压缩](#上下文压缩)** | 内置的卸载和摘要，以保持上下文在窗口限制内 | 自动，接近限制时触发 |
| **[上下文隔离](#使用子智能体进行上下文隔离)** | 使用子智能体隔离繁重工作，仅将结果返回主 agent | 每个子智能体，委托时 |
| **[长期内存](#长期内存)** | 使用虚拟文件系统在跨线程持久存储 | 跨对话持久 |

## 输入上下文

输入上下文是在启动时提供给 deep agent 并成为其系统提示词一部分的信息。最终提示词由几个来源组成：

- **系统提示词（System prompt）**：你提供的自定义指令加上内置 agent 指导。
- **内存（Memory）**：配置后始终加载的持久 `AGENTS.md` 文件。
- **技能（Skills）**：相关时加载的按需能力（渐进式披露）。
- **工具提示词（Tool prompts）**：使用内置工具或自定义工具的指令。

### 系统提示词

你的自定义系统提示词会前置到内置系统提示词，后者包含关于规划、文件系统工具和子智能体的指导。使用它来定义 agent 的角色、行为和知识：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    system_prompt=(
        "你是一个专注于科学文献的研究助手。"
        "始终引用来源。使用子智能体（subagents）对不同主题进行并行研究。"
    ),
)
```

`system_prompt` 参数是静态的，意味着它不随每次调用而变化。对于某些用例，你可能需要动态提示词：例如告诉模型"你有管理员权限"与"你只有只读权限"，或从[长期内存](#长期内存)注入用户偏好（如"用户偏好简洁回答"）。如果你的提示词依赖上下文或 `runtime.store`，请使用 `@dynamic_prompt` 构建上下文感知指令。你的中间件可以读取 `request.runtime.context` 和 `request.runtime.store`。

仅当工具单独使用上下文或 `runtime.store` 时，你**不**需要中间件；工具直接接收 [ToolRuntime](https://reference.langchain.com/python/langchain/tools/#langchain.tools.ToolRuntime) 对象（包括 `runtime.context` 和 `runtime.store`）。仅当工具应打包系统提示词更新时才添加中间件。

### 内存

内存文件（[`AGENTS.md`](https://agents.md/)）提供**始终加载**到系统提示词中的持久上下文。用于项目规范、用户偏好和应应用于每次对话的关键指南：

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    memory=["/project/AGENTS.md", "~/.deepagents/preferences.md"],
)
```

与技能不同，内存始终注入——没有渐进式披露。保持内存最小化以避免上下文过载；对详细工作流和领域特定内容使用 [技能](/oss/python/deepagents/skills)。

### 技能

技能提供**按需**能力。Agent 在启动时读取每个 `SKILL.md` 的 frontmatter，然后仅在确定技能相关时加载完整的技能内容。这减少了 token 使用，同时仍然提供专门的工作流：

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    skills=["/skills/research/", "/skills/web-search/"],
)
```

保持每个技能专注于单个工作流或领域；宽泛或重叠的技能会稀释相关性并在加载时膨胀上下文。在技能内部，保持主要内容简洁，并将详细的参考资料移至技能文件中引用的单独文件。将始终相关的约定放在[内存](#内存)中。

### 工具提示词

[工具](/oss/python/langchain/tools)提示词是指引模型如何使用工具的指令。所有工具都暴露元数据（通常是模式（schema（模式））和描述），模型在其提示词中看到。你通过 `tools` 参数传递的工具将该工具元数据（模式和描述）暴露给模型。Deep agent 的内置工具打包在中间件中，通常还会用更多这些工具指导更新系统提示词。

**内置工具**——添加 harness 能力（规划、文件系统、子智能体）的中间件自动将工具特定指令追加到系统提示词，创建解释如何有效使用这些工具的工具提示词：

- 规划提示词——`write_todos` 维护结构化任务列表的指令
- 文件系统提示词——`ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep` 的文档（使用沙箱后端时加上 `execute`）
- 子智能体提示词——使用 `task` 工具委托工作的指导
- Human-in-the-loop 提示词——在指定工具调用时暂停的用法（当 `interrupt_on` 设置时）
- 本地上下文提示词——当前目录和项目信息（仅 CLI）

**你提供的工具**——通过 `tools` 参数传递的工具获取其描述（来自工具模式）发送给模型。你也可以添加[自定义中间件](/oss/python/langchain/middleware)，添加工具并追加自己的系统提示词指令。

对于你提供的工具，确保提供清晰的名称、描述和参数描述。这些指导模型推理何时以及如何使用工具。在描述中包含**何时**使用该工具，并描述每个参数的作用。

```python
@tool(parse_docstring=True)
def search_orders(
    user_id: str,
    status: str,
    limit: int = 10
) -> str:
    """按状态搜索用户订单。

    当用户询问订单历史或想检查订单状态时使用。始终过滤提供的状态。

    Args:
        user_id: 用户的唯一标识符
        status: 订单状态：'pending'、'shipped' 或 'delivered'
        limit: 要返回的最大结果数
    """
    # 实现
    ...
```

### 完整的系统提示词

Deep agent 的系统消息——模型在运行开始时接收的组装好的系统提示词——由以下部分组成：

1. 自定义 `system_prompt`（如果提供）
2. [基础 agent 提示词](https://github.com/langchain-ai/deepagents/blob/e18e9dcd0e6edc72c0a4a5b76ae752c4bc539752/libs/deepagents/deepagents/graph.py#L37)
3. 待办列表提示词：如何使用待办列表进行规划的指令
4. 内存提示词：`AGENTS.md` + 内存使用指南（仅在提供 `memory` 时）
5. 技能提示词：技能位置 + 带有 frontmatter 信息的技能列表 + 用法（仅在提供技能时）
6. 虚拟文件系统提示词（文件系统 + 执行工具文档，如适用）
7. 子智能体提示词：Task 工具用法
8. 用户提供的中间件提示词（如果提供自定义中间件）
9. Human-in-the-loop 提示词（当 `interrupt_on` 设置时）

## 运行时上下文

运行时上下文是你在调用 agent 时传入的每次运行配置。它不会自动包含在模型提示词中；模型仅在某工具、中间件或其他逻辑读取它并将其添加到消息或系统提示词时才看到它。将运行时上下文用于用户元数据（ID、偏好、角色）、API 密钥、数据库连接、功能标志或工具和 harness 需要的其他值。

使用 `context_schema` 定义该数据的形状：使用 `dataclasses.dataclass` 或 `typing.TypedDict` 类。通过 **`context`** 参数传递值给 `invoke` / `ainvoke`。

在工具内部，从注入的 [ToolRuntime](https://reference.langchain.com/python/langchain/tools/#langchain.tools.ToolRuntime) 读取上下文：

```python
from dataclasses import dataclass
from deepagents import create_deep_agent
from langchain.tools import tool, ToolRuntime

@dataclass
class Context:
    user_id: str
    api_key: str

@tool
def fetch_user_data(query: str, runtime: ToolRuntime[Context]) -> str:
    """获取当前用户的数据。"""
    user_id = runtime.context.user_id
    return f"Data for user {user_id}: {query}"

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    tools=[fetch_user_data],
    context_schema=Context,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Get my recent activity"}]},
    context=Context(user_id="user-123", api_key="sk-..."),
)
```

运行时上下文**传播到所有子智能体**。当子智能体运行时，它接收与父级相同的运行时上下文。

## 上下文压缩

长时间运行的任务会产生大量工具输出和长对话历史。上下文压缩在保留与任务相关细节的同时减少 agent 工作内存中的信息大小。以下技术是确保传递给 LLM 的上下文保持在上下文窗口限制内的内置机制：

### 卸载（Offloading）

Deep agents 使用[内置文件系统工具](/oss/python/deepagents/harness#virtual-filesystem-access)自动卸载内容并在需要时搜索和检索该卸载的内容。当工具调用输入或结果超过 token 阈值（默认 20,000）时发生内容卸载：

1. **工具调用输入超过 20,000 token**：文件写入和编辑操作在 agent 对话历史中留下包含完整文件内容的工具调用。由于这些内容已持久化到文件系统，通常是冗余的。当会话上下文超过模型可用窗口的 85% 时，deep agents 截断旧的工具调用，用磁盘上文件的指针替换它们，减少活跃上下文的大小。

2. **工具调用结果超过 20,000 token**：此时，deep agent 将响应卸载到配置的后端，并用文件路径引用和前 10 行预览替换它。然后 agent 可以根据需要重新读取或搜索内容。

### 摘要（Summarization）

当上下文大小超过模型的上下文窗口限制（例如 `max_input_tokens` 的 85%），且没有更多上下文符合卸载条件时，deep agent 会摘要消息历史。

此过程有两个组件：

- **上下文内摘要**：LLM 生成会话的结构化摘要，包括会话意图、创建的工件和下一步——这替换了 agent 工作内存中的完整对话历史。
- **文件系统持久化**：完整的原始对话消息作为规范记录写入文件系统。

这种双管齐下的方法确保 agent 保持对其目标和进展的认识（通过摘要），同时保留在需要时恢复具体细节的能力（通过文件系统搜索）。

**配置：**
- 在模型的 `max_input_tokens` 的 85% 时触发，来自其[模型配置文件](/oss/python/langchain/models#model-profiles)
- 保留 10% 的 token 作为近期上下文
- 如果模型配置文件不可用，回退到 170,000 token 触发 / 保留 6 条消息
- 如果任何模型调用引发标准 [ContextOverflowError](https://reference.langchain.com/python/langchain-core/exceptions/ContextOverflowError)，deep agent 立即回退到摘要并使用摘要 + 近期保留的消息重试
- 旧消息由模型摘要

> Agent 的[流式 token](/oss/python/deepagents/streaming#llm-tokens) 通常包括摘要步骤生成的 token。你可以使用其关联的元数据过滤这些 token：
>
> ```python
> for chunk in agent.stream(
>     {"messages": [...]},
>     stream_mode="messages",
>     version="v2",
> ):
>     token, metadata = chunk["data"]
>     if metadata.get("lc_source") == "summarization":
>         continue
>     else:
>         ...
> ```

## 使用子智能体进行上下文隔离

子智能体解决了**上下文膨胀问题**。当主 agent 使用具有大输出的工具（网络搜索、文件读取、数据库查询）时，上下文窗口迅速填满。子智能体隔离这些工作——主 agent 仅接收最终结果，而非产生结果的数十次工具调用。你还可以将每个子智能体与主 agent 分开配置（例如模型、工具、系统提示词和技能）。

**工作原理：**
- 主 agent 有 `task` 工具来委托工作
- 子智能体使用自己的全新上下文运行
- 子智能体自主执行直到完成
- 子智能体向主 agent 返回单个最终报告
- 主 agent 的上下文保持干净

**最佳实践：**

1. **委托复杂任务**：对多步骤工作使用子智能体，以免混乱主 agent 的上下文。

2. **保持子智能体响应简洁**：指导子智能体返回摘要，而非原始数据：

   ```python
   research_subagent = {
       "name": "researcher",
       "description": "对主题进行研究",
       "system_prompt": """你是一个研究助手。
       重要：仅返回基本摘要（500 字以内）。
       不要包含原始搜索结果或详细的工具输出。""",
       "tools": [web_search],
   }
   ```

3. **对大型数据使用文件系统**：子智能体可以将结果写入文件；主 agent 读取它需要的内容。

## 长期内存

使用默认文件系统时，你的 deep agent 将其工作内存文件存储在 agent 状态中，这仅在线程内持久。长期内存使你的 deep agent 能够跨不同线程和对话持久信息。Deep agents 可以使用长期内存来存储用户偏好、累积知识、研究进展或任何应在单次会话之外持久的信息。

要使用长期内存，你必须使用 `CompositeBackend`，将特定路径（通常是 `/memories/`）路由到 LangGraph Store，后者提供持久的跨线程持久化。`CompositeBackend` 是一个混合存储系统，其中一些文件无限期持久，而另一些则限定在单个线程内。

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

def make_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={"/memories/": StoreBackend(runtime)},
    )

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    store=InMemoryStore(),
    backend=make_backend,
    system_prompt="""当用户告诉你他们的偏好时，将它们保存到
    /memories/user_preferences.txt，以便你在未来对话中记住它们。""",
)
```

你不需要预先填充 `/memories/` 中的文件。你提供后端配置、存储和系统提示指令，告诉 agent *保存什么*和*保存到哪里*。例如，你可以提示 agent 将偏好存储在 `/memories/preferences.txt` 中。路径开始时为空，当用户分享值得记住的信息时，agent 使用其文件系统工具（`write_file`、`edit_file`）按需创建文件。

要预播种内存，在 LangSmith 上部署时使用 [Store API](/langsmith/custom-store)。

## 最佳实践

1. **从正确的输入上下文开始**——保持内存最小化，用于始终相关的约定；对特定于任务的能力使用聚焦的技能。
2. **利用子智能体进行繁重工作**——将多步骤、输出密集的任务委托给子智能体，以保持主 agent 的上下文干净。
3. **在配置中调整子智能体输出**——如果你在调试时注意到子智能体生成长输出，你可以在子智能体的 `system_prompt` 中添加指导，要求创建摘要和综合发现。
4. **使用文件系统**——将大输出持久化到文件（例如子智能体写入或[自动卸载](#卸载)），以便活跃上下文保持较小；模型可以在需要细节时使用 `read_file` 和 `grep` 拉入片段。
5. **记录长期内存结构**——告诉 agent `/memories/` 中有什么以及如何使用它。
6. **为工具传递运行时上下文**——对工具需要的用户元数据、API 密钥和其他静态配置使用 `context`。

---

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

---

# Agent Client Protocol (ACP)

> 原文：[https://docs.langchain.com/oss/python/deepagents/acp](https://docs.langchain.com/oss/python/deepagents/acp)

> 通过 Agent Client Protocol (ACP) 将 Deep Agents 暴露给代码编辑器和 IDE 集成。

[Agent Client Protocol (ACP)](https://agentclientprotocol.com/get-started/introduction) 标准化了编码 agent（智能体）与代码编辑器或 IDE 之间的通信。使用 ACP 协议，你可以将自定义 deep agent（深度智能体）与任何 ACP 兼容的客户端配合使用，使你的代码编辑器能够提供项目上下文并接收丰富的更新。

> ACP 专为 agent-编辑器集成设计。如果你希望 agent 调用外部服务器托管的工具，请参见 [Model Context Protocol (MCP)](/oss/python/langchain/mcp/)。

## 快速开始

安装 ACP 集成包：

```bash
pip install deepagents-acp
# 或
uv add deepagents-acp
```

然后通过 ACP 暴露 deep agent。

这会启动一个 stdio 模式的 ACP 服务器（从 stdin 读取请求，向 stdout 写入响应）。实践中，你通常将其作为 ACP 客户端（例如你的编辑器）启动的命令运行，然后通过 stdio 与服务器通信。

```python
import asyncio

from acp import run_agent
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents_acp.server import AgentServerACP


async def main() -> None:
    agent = create_deep_agent(
        model="google_genai:gemini-3.1-pro-preview",
        # 你可以在此自定义 deep agent：设置自定义提示词、
        # 添加你自己的工具、附加中间件或组合子智能体。
        system_prompt="You are a helpful coding assistant",
        checkpointer=MemorySaver(),
    )

    server = AgentServerACP(agent)
    await run_agent(server)


if __name__ == "__main__":
    asyncio.run(main())
```

> `deepagents-acp` 包包含一个开箱即用的示例编码 agent，具有文件系统和 shell 支持。参见 [demo_agent.py](https://github.com/langchain-ai/deepagents/blob/main/libs/acp/examples/demo_agent.py)。

## 客户端

Deep agents 可以在任何你能运行 ACP agent 服务器的地方使用。一些值得注意的 ACP 客户端包括：

- [Zed](https://zed.dev/docs/ai/external-agents)
- [JetBrains IDEs](https://www.jetbrains.com/help/ai-assistant/acp.html)
- Visual Studio Code（通过 [vscode-acp](https://github.com/formulahendry/vscode-acp)）
- Neovim（通过 ACP 兼容插件）

### Zed

`deepagents` 仓库包含一个 [示例 ACP 入口点](https://github.com/langchain-ai/deepagents/blob/main/libs/acp/run_demo_agent.sh)，你可以在 [Zed](https://zed.dev/docs/ai/external-agents) 中注册：

1. 克隆 `deepagents` 仓库并安装依赖：

```bash
git clone https://github.com/langchain-ai/deepagents.git
cd deepagents/libs/acp
uv sync --all-groups
chmod +x run_demo_agent.sh
```

2. 为 demo agent 配置凭据：

```bash
cp .env.example .env
```

然后在 `.env` 中设置 `ANTHROPIC_API_KEY`。

3. 在 Zed 的 `settings.json` 中配置你的 ACP agent 服务器命令：

```json
{
  "agent_servers": {
    "DeepAgents": {
      "type": "custom",
      "command": "/your/absolute/path/to/deepagents/libs/acp/run_demo_agent.sh"
    }
  }
}
```

4. 打开 Zed 的 Agents 面板并启动 DeepAgents 线程。

### Toad

如果你想在本地开发工具中运行 ACP agent 服务器，可以使用 [Toad](https://github.com/batrachianai/toad) 来管理进程。

```bash
uv tool install -U batrachian-toad

toad acp "python path/to/your_server.py" .
# 或
toad acp "uv run python path/to/your_server.py" .
```

> 参见上游 ACP 文档获取协议详情和编辑器支持：
>
> - 介绍：[https://agentclientprotocol.com/get-started/introduction](https://agentclientprotocol.com/get-started/introduction)
> - 客户端/编辑器：[https://agentclientprotocol.com/get-started/clients](https://agentclientprotocol.com/get-started/clients)

---

