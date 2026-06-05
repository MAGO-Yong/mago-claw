# RedDoc 目录遍历参考

## pmo tree 命令

```bash
# 遍历项目文档目录（自动从 aipmo 获取 redocUrl / spaceUrl）
pmo tree "项目名"

# 快速定位文档
pmo tree "项目名" --find weekly      # 最新周会文档
pmo tree "项目名" --find ko          # KO 文档
pmo tree "项目名" --find minutes-dir # 纪要目录

# 控制深度
pmo tree "项目名" --depth 4

# 输出结构摘要（适合初始化项目上下文）
pmo tree "项目名" --summary

# 输出适合写入 memory/projects/xxx.md 的上下文文本
pmo tree "项目名" --context
```

## 空间类型识别（自动）

| redocUrl | spaceUrl | 类型 | 策略 |
|----------|----------|------|------|
| /doc/xxx | /space/xxx | `standard` | 以 redocUrl 为根，按编号识别各节目录 |
| /doc/xxx | /doc/xxx（相同） | `single_doc` | 单文档项目 |
| /doc/xxx | /doc/yyy（不同） | `custom` | 以 redocUrl 为根自由遍历 |
| 空 | /space/xxx | `space_only` | ⚠️ 需与用户确认范围 |
| 空 | /doc/xxx | `doc_as_root` | 以 spaceUrl 文档为根 |

## space_only 场景处理

先 `pmo tree "项目名" --summary` 展示根目录，再询问用户：

```bash
# 整个空间
pmo tree "项目名" --space-scope full

# 指定子目录
pmo tree "项目名" --space-scope sub --sub-dir-id <shortcutId>
```

## 典型工作流：初始化项目文档上下文

```bash
# 1. 摘要了解结构
pmo tree "项目名" --summary

# 2. 完整目录
pmo tree "项目名"

# 3. 写入 memory
pmo tree "项目名" --context > memory/projects/xxx.md
```
