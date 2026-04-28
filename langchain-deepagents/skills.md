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
