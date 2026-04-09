---
name: hi-im
version: 1.0.0
description: 'hi 官方即时通讯 Skill，支持上传文件到 Hi IM 服务，返回 fileId 和 fileUrl'
metadata: { 'openclaw': { 'requires': { 'bins': ["bun"] } } }
---

# hi-im

上传文件到 Hi 即时通讯服务。

## 错误处理

若接口调用失败，必要时可重试，但**最多自动重试 3 次**（含首次调用）。

## 发现命令

**在调用任何命令前，先用 `--help` 查询可用命令和参数，不要猜测 flag 名称。**

```bash
# 列出所有 im 子命令
bunx @xhs/hi-workspace-cli@0.2.10 im --help

# 查看具体命令的参数（含输出格式）
bunx @xhs/hi-workspace-cli@0.2.10 im:<method> --help
```

## 文件上传

### 限制

- 文件大小上限 **30 MB**，超出会被拒绝。
- 文件路径必须是**本地绝对路径**或相对于当前工作目录的路径。

### 输出

上传成功后返回 `fileId` 和 `fileUrl`，可直接用于 IM 消息发送或文档嵌入等后续操作。
