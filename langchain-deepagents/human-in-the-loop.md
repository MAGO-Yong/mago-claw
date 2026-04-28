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
