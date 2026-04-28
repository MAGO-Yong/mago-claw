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
