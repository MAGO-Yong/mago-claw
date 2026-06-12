# guard-transform 工具本体（core/）

这是 guard-transform 的**具体实现层**，包含所有运行时需要的脚本、Python 包、prompts、verifiers、templates、profiles 与 detect_rules。

三套适配层 [`skills/claude/`](../skills/claude)、[`skills/codewiz/`](../skills/codewiz)、[`skills/seal/`](../skills/seal) 通过 `install.sh` / `build.sh` 把本目录整体复制到各自部署目标里。

## 目录结构

```
core/
├── transform.sh           # 顶层编排：detect → adapt → ... → package
├── detect_rules.json      # 栈识别规则
├── README.md              # 本文件
├── bin/                   # 命令行入口
│   ├── guardx             # 主 CLI（detect / adapt / fix / package / clean / status / clone）
│   ├── cowork-package-verify
│   └── cowork-login-check
├── guardx/                # Python 包：scaffold / packaging / verifier 编排 / clone 等
├── prompts/               # LLM 提示词模板（stage 编号 + 中文标题）
├── verifiers/             # 各类校验 shell（路径、SSE、DB、SDK 等）
├── templates/             # install.sh / start.sh / health.sh / default_env.sh 等模板
└── profiles/              # 不同技术栈的 stage 流水线 YAML
```

## 单独运行

如果你已经把 `core/` 复制到目标位置，并设置好 `GUARD_TRANSFORM_HOME` 指向该副本：

```bash
export GUARD_TRANSFORM_HOME=/path/to/core
"$GUARD_TRANSFORM_HOME/bin/guardx" detect /path/to/source-project
"$GUARD_TRANSFORM_HOME/bin/guardx" transform /path/to/source-project
```

## 关于适配层

- [`skills/claude/install.sh`](../skills/claude/install.sh)：把 `core/` 复制到 `~/.claude/skills/cowork-app/scripts/`
- [`skills/codewiz/install.sh`](../skills/codewiz/install.sh)：把 `core/` 复制到 `~/.codewiz/skills/cowork-app/scripts/`
- [`skills/seal/build.sh`](../skills/seal/build.sh)：把 `core/` 打包进 `dist/cowork-app-<ts>.zip` 的 `cowork-app/scripts/`，供 Seal IDE 上传

完整的整体说明（含三套 skill 对比、调度模型等）见仓库根 [`../README.md`](../README.md) 与 [`../ARCHITECTURE.md`](../ARCHITECTURE.md)。
