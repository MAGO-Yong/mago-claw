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
