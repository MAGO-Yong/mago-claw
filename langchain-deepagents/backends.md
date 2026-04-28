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
