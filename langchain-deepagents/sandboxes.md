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
