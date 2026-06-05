---
name: project-management
description: |
  技术PMO团队开发的项目管理SKILL。前提需要在 https://aipmo.devops.xiaohongshu.com/#/ 配置项目信息。

  支持能力：
  1. **Hi 消息发送**：发文字/图片/截图到项目群或指定人。Trigger: "发消息到{项目}群"、"截图发到{项目}群"
  2. **项目信息查询**：查 RedDoc 地址、Hi 群 chatId、负责人、列出所有项目或我相关的项目。Trigger: "查一下{项目}信息"、"列出所有项目"、"列出我的项目"、"我负责哪些项目"
  3. **Todo 完成情况**：读取最新周会文档 Todo/待办表格，输出完成/逾期清单。Trigger: "查看{项目}todo完成情况"
  4. **例会文档更新情况**：检查进展管理/进展大盘表格各方向进展列是否已填写，输出谁没更新。Trigger: "查看{项目}例会文档更新情况"
  5. **项目进展总结**：生成周进展摘要、OKR 整体进展或活动型项目进展报告，可发群。Trigger: "总结{项目}进展"、"对照KR看看{项目}进度"
  6. **遍历项目文档目录**：列出 RedDoc 空间完整目录树，定位周报/KO/纪要等文档。Trigger: "{项目}文档目录是什么"、"{项目}最新周报在哪"
  7. **项目管理知识库**：查询 XHS PMO 内部知识库（最佳实践/KO模板/周会模板/复盘模板/干系人识别）。Trigger: "怎么做干系人识别"、"给我周会模板"
  8. **生成会议纪要**：搜日历拿 meetingId → 拉取转写 → 结合项目上下文生成结构化纪要写入 RedDoc。Trigger: "帮我出{会议名}的纪要"、"生成会议纪要"
  9. **创建项目周例会文档**：浏览器克隆上一期文档副本，自动改标题、清空 Todo 已完成行（含骨架删除）、清空进展大盘进展列（含 image/card/mention）、移顶、更新会邀。Trigger: "帮我建周会文档"、"准备周会"
  10. **Hi 群成员查询**：拉取项目 Hi 群的成员列表，支持将邮箱转换为薯名(真名)格式。Trigger: "查看{项目}群成员"、"拉一下群成员列表"
---

# 项目管理 Skill

## 前提：pmo CLI

所有场景统一通过 `pmo` CLI 执行。**无需手动安装**，每条命令通过 npx 按需加载：

```bash
# 统一调用方式（内网 registry，http 7001 端口）
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest <command>

# 验证可用
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest --version
```

> npx 会自动缓存，首次略慢，后续调用很快。

## 用户配置

```
PROJECT_TOKEN = <your_project_token>   # 创建项目时后端返回，持有即可访问
```

首次使用若为占位符，询问用户 Token 后直接使用，无需再询问。

> 如需切换 SIT 等非生产环境，通过 `pmo config setup` 修改 CLI 本地配置（`~/.pmo/config.json`），与此处无关。

## 快速导航（按需读取对应 references 文件）

| 场景 | 读哪个文件 |
|------|-----------|
| API 接口 & 通用前置步骤 | `references/api.md` |
| Hi 消息发送/查询/撤回 | `references/hi-messaging.md` |
| Todo 完成情况、例会文档更新 | `references/scenarios-todo-weekly.md` |
| 项目进展总结（模板A/B/C） | `references/scenarios-progress.md` |
| 生成会议纪要 | `references/scenarios-minutes.md` |
| 创建周例会文档 | `references/scenarios-weekly-doc.md` |
| 遍历项目文档目录 | `references/redoc-tree.md` |
| PMO 知识库查询 | `references/knowledge-base.md` |

## 核心工作流

### 项目信息查询

```bash
# 查询单个项目信息
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest info "项目名"

# 列出所有项目
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest list

# 列出与当前用户相关的项目（按关系类型分组）
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest list --mine
```

- `info`：返回 RedDoc 地址、Hi 群 chatId、负责人信息。项目不存在时引导用户前往 https://aipmo.devops.xiaohongshu.com/#/ 配置。
- `list`：列出所有已配置的项目。
- `list --mine`：只列出与当前用户相关的项目，按三类分组展示：
  - 👑 **我负责的项目**（担任 owner 角色）
  - 🛠 **我创建的项目**（创建人为我，且非负责人）
  - 👥 **我参与的项目**（project_members 中有记录）

> 用户说"我的项目"、"我负责哪些项目"、"列出我的项目"时，优先使用 `list --mine`。

### Todo & 例会文档

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest todo "项目名"
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest check-update "项目名"
```

详细格式和发送规则见 `references/scenarios-todo-weekly.md`。

### 项目进展总结

**模板选择（三选一）：**
- 项目名含月日数字（如 `0327`）→ **模板C（日期型活动项目）**
- 本周/近期进展 → **模板A（周进展摘要）**
- 整体/对照OKR → **模板B（OKR总结）**

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest report "项目名"
```

详细输出格式见 `references/scenarios-progress.md`。

### 生成会议纪要

完整 SOP 见 `references/scenarios-minutes.md`。

**会议纪要标题格式：`MM月DD日 {会议标题}`，不带年份。**

### 创建周例会文档

**绝对不用 write-doc 或 create-doc**，必须通过浏览器「创建副本」克隆。

```bash
# Step 1：dry-run 确认上一期文档（浏览器克隆前先跑这个）
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest weekly "项目名" --date MMDD --dry-run

# Step 2：浏览器克隆上一期文档（见 references/scenarios-weekly-doc.md）
# 拿到新文档 ID 后：

# Step 3：一键完成标题修改 + Todo 清空 + 进展列清空 + 移顶
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest weekly "项目名" --date MMDD --new-id <新文档ID>

# 跳过移顶（测试用）
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest weekly "项目名" --date MMDD --new-id <新文档ID> --skip-move
```

`pmo weekly` 自动处理：
- ✅ 标题改为「MMDD {项目}周会」
- ✅ Todo 已完成行：清空行内容（通过 `docs:edit` target/replace 替换为空行）
- ✅ 进展大盘进展列：清空进展列内容，保留已完成行不动
- ✅ 移顶（置于上一期文档之前）

完整步骤（含浏览器克隆 + 更新会邀 + 发群通知）见 `references/scenarios-weekly-doc.md`。

### 遍历文档目录

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest tree "项目名"
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest tree "项目名" --summary
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest tree "项目名" --find weekly
```

详见 `references/redoc-tree.md`。

### 项目管理知识库

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest kb
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest kb "干系人"
```

核心文档链接见 `references/knowledge-base.md`。

### Hi 消息发送

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest send msg --project "项目名" "消息内容"
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest send msg --to "email@xiaohongshu.com" "消息内容"
```

详见 `references/hi-messaging.md`。

### Hi 群成员查询

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest members CHAT7651514247846641762
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest members -p "项目名"
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ npx --yes @xhs/pmo-cli@latest members CHAT7651514247846641762 --resolve-names
```

返回：群成员邮箱列表，可选解析为薯名(真名)格式。

## 依赖 Skill

| Skill | 用于 |
|-------|------|
| `hi-docs` | 所有 RedDoc 文档操作（读取 `docs:get`、编辑 `docs:edit`、创建 `docs:create`），pmo-cli 内部统一使用 `bunx @xhs/hi-cli` |
| `hi-calendar` | 创建周例会文档（更新会邀）、生成会议纪要（搜索日程） |
| `hi-meeting` | 生成会议纪要（拉取转写内容） |

调用对应场景前，检查依赖 skill 是否已安装（`~/.openclaw/workspace/skills/<name>/SKILL.md` 存在）。
