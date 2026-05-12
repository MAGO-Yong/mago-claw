---
name: hi-assistant-profile
version: 1.0.0
description: 'hi 官方个人助理基本信息管理 Skill。当用户需要修改、更换、设置、更新助理/机器人/bot 的名称、头像或签名时，必须使用此 skill'
metadata: { 'openclaw': { 'requires': { 'bins': ["node", "hi"] } } }
---

技能核心能力通过 CLI 提供，在执行 CLI 命令时，必须查看运行命令的参数，**禁止**猜测命令用法：

```bash
# 查看具体命令的参数、示例和输出格式
hi assistant-profile --help
```

# 环境准备

若执行 `hi` 命令时提示 `command not found`，通过以下任一方式全局安装：

```bash
# 方式一：npm
npm install -g @xhs/hi-cli --registry=http://npm.devops.xiaohongshu.com:7001

# 方式二：bun
bun install -g @xhs/hi-cli --registry=http://npm.devops.xiaohongshu.com:7001
```

# 基础规则

**头像图片要求**：

- 下载目标图片时保留原始文件后缀（如 `.png`、`.jpg`）；如果 URL 中无后缀，默认使用 `.png`。
- 超过 **30 MB** 的图片会**自动压缩**到 25 MB 以内（GIF 格式除外，不支持自动压缩）。
- 支持格式：jpeg、jpg、png、gif、webp。
