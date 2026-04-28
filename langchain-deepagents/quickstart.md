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
