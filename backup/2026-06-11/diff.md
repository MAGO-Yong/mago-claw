# 每日备份差异报告 - 2026-06-11 vs 2026-06-10

生成时间: 2026-06-11 02:01:40 CST

## 核心文件变更

### MEMORY.md
- 变更行数: 13
- 文件大小变化: 44300B → 45154B

```diff
182a183,195
> ### RedGarden vs REDoc 区分（2026-06-09 发现）
> - `redgarden.xiaohongshu.com` = RedGarden（内网知识分享/内容花园平台），不是 REDoc
> - `docs.xiaohongshu.com` = REDoc（内部文档平台）
> - `hi docs:get` 只能读 REDoc 文档，不能读 RedGarden
> - 遇到内部文档链接时先确认平台类型
> 
> ### OpenClaw vs Codex 能力架构差异（2026-06-09）
> - **OpenClaw**：平台内置工具函数（`cowork_publish` 等）+ Skills（说明书，可调用工具函数）
> - **Codex**：`~/.codex/skills/<name>/SKILL.md`（只能执行 Shell 命令）+ `~/.codex/prompts/<name>.md`（Slash commands）
> - **核心差异**：Codex 没有工具函数，SKILL.md 不是跨平台通用的
> - **推荐方案**：Codex 负责编码 + OpenClaw 负责发布（方案 C），零成本分工
> - Codex 已有 skills：qs；已有 prompts：xray
> 
```

### SOUL.md ✅ 无变更

### AGENTS.md ✅ 无变更

### ROUTING.md ✅ 无变更

### USER.md ✅ 无变更

### TOOLS.md ✅ 无变更


## memory/ 新增文件

无新增

## agents/ 变更


