---
name: seal-sync-skills
description: 把 SealWorkspace 里的 skills 以软链接方式同步到本机的 Claude Code skill 目录（~/.codewiz/skills 和 ~/.claude/skills）。当用户说"同步 seal skills"、"link seal skills"、"软链接 seal"、"sync seal"、"seal 的 skill 同步"、"把 seal 的 skill 链过来"时触发本 skill。SealWorkspace 有新 skill 加入时也应提示用户运行本 skill。
---

## 执行

```bash
bash ~/.codewiz/skills/seal-sync-skills/scripts/sync.sh [SOURCE_DIR]
```

不传参数时，源目录默认为 `~/SealWorkspace/$USER/skills`（自动用系统用户名），适配不同用户的机器。

也可手动指定源目录：

```bash
bash ~/.codewiz/skills/seal-sync-skills/scripts/sync.sh /path/to/your/skills
```

## 逻辑

- 遍历源目录下所有子目录，分别在 `~/.codewiz/skills/` 和 `~/.claude/skills/` 中创建软链接
- 若目标位置已是真实目录（非软链接），则跳过，保护手动维护的 skill
- 若目标是旧软链接，则刷新
- 目标目录不存在时自动创建
- 最终汇报创建数量和跳过列表
