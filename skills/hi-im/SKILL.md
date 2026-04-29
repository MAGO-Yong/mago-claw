---
name: hi-im
version: 1.0.0
description: hi 官方即时通讯 Skill。当用户需要上传文件或图片到 Hi 时，必须使用此 skill
metadata: { 'openclaw': { 'requires': { 'bins': ["node", "hi"] } } }
---

# 环境准备

若执行 `hi` 命令时提示 `command not found`，通过以下任一方式全局安装：

```bash
# 方式一：npm
npm install -g @xhs/hi-cli

# 方式二：bun
bun install -g @xhs/hi-cli
```

技能核心能力通过 CLI 提供，在执行 CLI 命令时，必须查看运行命令的参数，**禁止**猜测命令用法：

```bash
# 查看具体命令的参数、示例和输出格式
hi im --help
```

# 基础规则

## 文件上传

### 限制

- 文件大小上限 **30 MB**，超出会被拒绝
- 文件路径必须是**本地绝对路径**或相对于当前工作目录的路径
- 上传失败时，最多重试 3 次
