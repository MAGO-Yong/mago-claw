# alarm-skill-agent 能力边界

这份文档用于 `diagnosis-skill-builder` 在生成告警诊断 Skill 前查询目标运行环境边界。它描述的是 `/Users/luxiuyuan1/Documents/proj/xray-platform/alarm-skill-agent` 当前代码暴露出来的能力，不是告警诊断 SOP。

## 核心结论

- 目标 Agent 是 EasyAgent SDK 应用，Skill 通过 `SKILL.md` 触发，可带 `scripts/` 和 `references/`。
- 容器内默认从 `/skills` 加载 Skill；deepagents 执行时也会使用 `/tmp/.easyagent/skills`。
- Gateway Skill 可以 lazy load 到本地 skill 目录；已安装 skill 也可能被后台刷新，不要依赖本地持久状态。
- Agent 原生暴露 `xray_cli` tool，可以非交互执行 `xray-cli` 子命令。
- 运行请求可以通过 `invoke_config.configurable.allowed_skills` 控制可见和可执行的 Skill。
- 单次 run、工具调用次数和 `xray_cli` 命令都有上限，生成的告警 Skill 应保持步骤有限、失败可报告。

## 可依赖的能力

生成的告警 Skill 可以依赖：

- 开发和验证阶段要求 `xray-cli v0.0.31` 或以上，低版本需要先升级后再执行 upload/test。
- `xray_cli` tool：传入 `arguments: string[]`，只传 `xray-cli` 子命令和参数，不包含 `xray-cli` 可执行文件名。
- `xray_cli` 默认会补 `--output-format json`；除非明确需要 raw/text。
- `xray_cli` 会返回 `command`、`returncode`、`stdout`、`stderr`、`timed_out`，失败原因必须如实进入报告。
- 随 Skill 打包的脚本可以作为实现细节，但应只调用 `xray-cli` 或做本地解析；不要把其他 Skill 当运行时依赖。
- 如果脚本使用 Python，必须按 `alarm-skill-agent` 当前 Python 3.12 编写，并且只使用 Python 标准库。不要依赖 alarm-skill-agent 项目依赖、第三方包或运行时安装。
- 临时文件只可作为运行过程缓存，优先放 `/tmp`；不要假设跨请求持久。

## 不应依赖的能力

生成的告警 Skill 不应依赖：

- 运行时安装或升级 `xray-cli`。
- 其他 Skill 的脚本、输出或安装状态。
- ONES、REDoc、浏览器 cookie、剪贴板、用户交互、直接 HTTP API、`curl`、kubectl、自定义外部 CLI。
- 交互式 `xray-cli auth login`。
- Python 第三方包、`pip install`、`uv add` 或宿主项目内的业务模块。
- `/skills` 或 `/tmp/.easyagent/skills` 下的持久缓存。
- 超长循环、无限重试或大批量探索式查询。

## 运行限制

当前代码中的关键默认值：

- Python 运行时对齐 3.12：`pyproject.toml` 声明 `requires-python = ">=3.12"`，`Dockerfile` / `Dockerfile.amd64` 使用 `python:3.12`，ruff target 为 `py312`。
- `xray_cli` 单次命令默认超时 120 秒，允许范围 1 到 600 秒。
- `xray_cli` stdout/stderr 默认最多返回 20000 字符，超出会截断。
- 单次 run 默认最大 1800 秒，可由 `invoke_config.configurable.max_duration_seconds` 覆盖。
- 单次 run 默认最多 15 次模型调用、30 次工具调用。
- `xray_cli` 参数最多 128 个，单个参数最多 4096 字符。

生成告警 Skill 时应把这些限制转成方法论约束：少量明确查询、显式超时/空数据处理、不要把“试探直到成功”写成运行时策略。

## allowed_skills 语义

`allowed_skills` 是运行期能力边界的一部分：

- 不传：沿用当前 session 既有白名单；如果没有白名单则不过滤。
- `null`：清空白名单，恢复不过滤。
- `[]`：过滤掉所有 Skill。
- 非空列表：只允许列表内 Skill 可见和可执行。

Builder 生成的告警 Skill 要假设自己可能是唯一被允许的 Skill，所以必须自洽，不依赖别的 Skill 协作。

## 对 Builder 的要求

生成前最少确认：

- 这个 Skill 能否只靠 `xray_cli` 和自身脚本完成自动取证。
- 运行时是否不需要用户确认或交互式登录。
- 每个自动节点是否有明确输入、查询方式、失败策略和报告字段。
- 非 `xray-cli` 证据是否已标成依赖缺口或人工背景。
- Python 脚本是否按 Python 3.12 编写，并且只使用标准库。
- 需要临时写入时是否限定到 `/tmp`。

不要把这份边界扩展成诊断模板。诊断流程仍由用户场景、SOP 和用户接受的建议决定。

## 来源

- `AGENTS.md`：Skill 结构、加载路径、项目约定。
- `src/agent.py`：EasyAgentSDK 初始化、`tools=TOOLS`、SkillProvider、gateway lazyload、recursion limit。
- `src/tool.py`：`xray_cli` tool 的参数、输出、超时和执行方式。
- `src/middleware_settings.py`：模型/工具调用上限与 run duration 默认值。
- `src/middlewares/skill_visibility.py`：`allowed_skills` 可见性语义。
- `src/middlewares/skill_execute_gate.py`：白名单外 Skill 执行硬拦截。
- `src/middlewares/skill_ls_filter.py`：skill 文件系统访问过滤。
- `src/gateway_lazy_loader.py`：gateway skill lazyload 和刷新行为。
- `Dockerfile` / `Dockerfile.amd64`：镜像内置 `/usr/bin/xray-cli`、`AUTO_UPDATE=0`、`CI=1` 和 xray auth material。
