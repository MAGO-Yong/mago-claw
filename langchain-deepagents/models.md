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
