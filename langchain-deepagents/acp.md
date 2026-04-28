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
