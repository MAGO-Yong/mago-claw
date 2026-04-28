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
