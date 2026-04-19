---
name: redoc
version: 1.0.0
description: hi 官方 REDoc 文档 Skill。当用户需要创建或编辑 REDoc 文档、修改文档内容、查看或回复文档评论、添加划词评论等文档操作时，必须使用此 skill。适用于通过 markdown 进行全文编辑、块级操作、查找替换、评论互动、文档历史版本恢复、创建文档副本
metadata: { 'openclaw': { 'requires': { 'bins': ["bun"] } } }
---

# hi-docs

技能核心能力通过 CLI 提供，在执行 CLI 命令时，必须查看运行命令的参数,**禁止**猜测命令用法：

```bash
bunx @xhs/hi-cli@0.2.15 docs --help              # 所有命令概览
```

# 文档 shortcutId

Hi 文档的 shortcutId 是文档的唯一标识符。

# 文档 spaceId

Hi 文档的 spaceId 是文档空间的唯一标识符。

## hash 说明

- 文档内容不变则 hash 不变；文档被任何人修改后 hash 会改变
- `hash` 是 `docs:edit` 的**必传参数**，用于版本校验（防止覆盖他人编辑）

# 创建文档

## 创建失败

如果发生网络相关错误，当需要重试的时候，你需要复用上一次调用时使用的 operateCode 来避免重复创建文档

## 文档空间与父目录规则

**注意：如果用户不主动强调，则这两个参数都不传，并在创建完文档后提示用户，文档已经创建在了个人文档空间根目录**

创建文档时，**文档空间（spaceId）** 和 **父目录（parentShortcutId）** 是二选一的关系，parentShortcutId 优先级高于 spaceId：

| 场景 | 效果 |
|------|------|
| 传入 parentShortcutId | 创建到**指定文档**的子目录 |
| 传入 spaceId | 创建到**指定文档空间**根目录 |
| parentShortcutId 和 spaceId 都没有传入 | 创建到**自己的文档空间**根目录 |

# 获取文档（docs:get）

1. `docs:get` 获取内容后会返回一个 `hash`。后续编辑操作均需携带该 `hash`；文档一旦被编辑，原 `hash` 就会失效，需要重新获取。
2. **正文输出模式**（均可用 `--offset` / `--limit` 分页）：
   - 默认 `--mode common`（可省略）：`content` 为**原始 Markdown 字符串**，适合通读全文、按 `target`/`replace` 编辑。
   - `--mode webFetch`：`content` 为**富文本条目数组**（如 `text` 文本段、`image` 含 `data`/`mimeType`），适合需要**按条目消费**、区分正文与内嵌图片等结构化场景；**编辑文档**仍以 `common` 的 Markdown 为准编写 `target`/`replace` 更稳妥。
3. 使用 `--mode blocks` 获取 `blocks` 字段（blockId → 缩略 Markdown 映射），用于**定位 blockId**，再用 `docs:edit --ops` 操作。以下场景需要先获取 blockId：
  - 在文档**末尾追加大量内容**（需要找到最后一个 blockId，用 `insert_after`）
  - 在某个**章节前/后插入**新内容（需要找到目标章节的 blockId）
  - **删除大批量内容**（需要找到该块的 blockId，用 `remove`）

## blocks 返回值格式

`blocks` 是一个 `Record<blockId, 缩略Markdown>` 对象：

- **key**：blockId（块的唯一标识符）
- **value**：该块的缩略 Markdown 内容
  - 内容 ≤ 100 字符：返回**完整文本**
  - 内容 > 100 字符：返回**前 50 字符 + `…` + 后 50 字符**

通过缩略内容可以快速定位目标块，无需阅读完整 Markdown。

# 编辑文档（docs:edit）

`docs:edit` 支持三种互斥的正文编辑模式。**--hash 和 --shortcut-id 是必传参数**

`--hash` 是 `docs:edit` 的**必传参数**，必须来自 `docs:get` 的返回值。

**版本校验机制**：提交编辑前，版本内容若与传入的 `--hash` 不一致，说明文档已被他人修改，**编辑会被拒绝并报错**。此时需重新调用 `docs:get` 获取最新内容和 hash，再重新编辑。

## 模式一：变更模式（--target + --replace）— 最推荐

适用于**修改已有内容**，无需知道 blockId。通过 `--target` 传入要匹配的原始文本，`--replace` 传入替换后的内容。`target` 匹配内容要尽量长，确保在文档中唯一。

**重要：不要使用匹配的 `target` 与空的 `replace` 当作匹配方式**。应在 `target` 中纳入变更位置**前后足够长的原文**，在 `replace` 中写出修改后的完整结果包括**未改动的部分**，适当加长 `target` / `replace` 中未改上下文可提升稳定性。

**使用流程**：
1. 调用 `docs:get` 获取文档内容和 `hash`
2. 从返回的 Markdown 中找到要修改的原始文本片段作为 `--target`
3. 调用 `docs:edit --hash <hash> --target '原始文本' --replace '替换后的内容'`

**注意**：
- `--target` 和 `--replace` 必须同时提供
- `target` 必须与 `docs:get` 返回的 Markdown **精确匹配**（支持空白规范化的跨 block 匹配），对应的 target 匹配内容要尽量长确保替换的唯一
- 匹配失败时会报错并提示 target 的前 100 字符，便于排查

## 模式二：块级操作（--ops）

适用于**插入新块**、**删除整个块**、**编辑标题**或**直接编辑指定块的内容**，**连续多次复杂的排版任务**，需要通过 `docs:get --mode blocks` 获取 blockId，来确定操作内容进行编排。

**使用流程**：
1. 调用 `docs:get --mode blocks` 获取 `hash` 和 `blocks`（blockId → 缩略 Markdown 映射）
2. 通过缩略内容定位目标块的 blockId
3. 调用 `docs:edit --hash <hash> --ops '[...]'`

**支持的操作**：

| op 类型 | 说明 | 参数 |
|---------|------|------|
| `edit` | 用新的 Markdown 内容**替换**目标块的全部内容 | `blockId` + `content` |
| `insert_before` | 在目标块**前方**插入新内容（Markdown） | `blockId` + `content` |
| `insert_after` | 在目标块**后方**插入新内容（Markdown） | `blockId` + `content` |
| `remove` | 删除目标块 | `blockId` |
| `move_before` | 将 `blockId` 块**移动到** `targetBlockId` 块的**前方** | `blockId` + `targetBlockId` |
| `move_after` | 将 `blockId` 块**移动到** `targetBlockId` 块的**后方** | `blockId` + `targetBlockId` |

**注意**：
- 多个操作按数组顺序依次执行
- `edit` 操作需要 `blockId` + `content`，会将该 block 的内容完全替换为 `content` 中的 Markdown
- 当 ops 内容较复杂时，推荐将操作数组写入 JSON 文件后通过 `文件路径` 传入，避免 shell 转义问题

## 模式三：全量替换（--content）

⚠️ **整篇改写时的最后手段**。传入完整 Markdown 内容，全量替换文档。

- **使用前必须向用户确认**

# 历史版本管理（docs:history）

当 `docs:edit` 编辑操作出现问题（如误修改、内容错误等），可使用 `docs:history` 命令查看或恢复本地保存的历史版本。

**注意!!! 在恢复前必须向用户确认，并向用户说明：恢复至所选历史版本后，该版本之后的所有编辑将丢失，是否继续。**

# 查看文档评论

- 使用 `### 划词内容：「anchorContent」` 按 anchor 分组
- 每组内用**表格**展示：评论者 | 内容 | 时间
- `imageUrlList` 中的图片追加在内容后：`![图片n](url)`
# 回复文档评论

回复前**必须先 `docs:comment-read`** 获取 anchorId。

- 回复**具体评论**时，自动 @该评论作者（邮箱加入 `mentionUserAccountIdList`，内容开头加 `@显示名称`），与用户手动 @的人叠加去重
- 仅在划词下发表评论（未指定具体评论）时，不自动 @
- `commentContent` 中有 @提及时，必须同步填入 `mentionUserAccountIdList`
- 待办事项必须用 `- [ ]` 格式，不用有序列表
- 回复评论时要使用 cli 参数来传入图片不支持 `![图片n](url)` 的格式

# 添加文档评论 ( 划词评论 )

通过 `docs:comment-add` 命令可以给文档中的 **指定文本** 划词添加评论。但如果你需要对已有的评论进行回复应该优先使用 **回复文档评论**
- 支持通过 `imageUrlList` 参数附带图片，暂不支持 @提及
- 如果你需要对已有评论进行回复优先使用 **回复文档评论**
- 回复评论时要使用 cli 参数来传入图片不支持 `![图片n](url)` 的格式

### 注意事项

- `blockId` 可通过 `docs:get --mode blocks` 获取
- `matchText` 必须是文档中实际存在的文本片段
- `commentContent` 中有 @提及时，必须同步填入 `mentionUserAccountIdList`
- 待办事项必须用 `- [ ]` 格式，不用有序列表

# 文档内容格式（REDoc-flavored Markdown）

> 完整语法规范见 [references/markdown-syntax.md](references/markdown-syntax.md)

文档使用 **REDoc-flavored Markdown** 格式，是标准 Markdown 的扩展版本。标准 Markdown 语法（标题、段落、列表、代码块、表格、图片、链接等）均正常支持，以下重点说明**扩展语法**和**使用注意点**。当 `docs:create` / `docs:edit` 报错提示 Markdown 解析失败时，通常需要检查普通文本中的特殊字符是否按 REDoc 规则转义。（见 `references/markdown-syntax.md`）

## 扩展语法速览

| 扩展功能 | 语法 | 关键限制 |
|---------|------|---------|
| 字体颜色 | `<font color="red">文字</font>` | 支持行内嵌套 |
| 表格多块 | 单元格内用 `<split/>` 分隔多个段落 | — |
| 分栏布局 | `<redoc-columns>` + `<redoc-column ratio={n}>` | **最多 5 列**；分栏内**不支持表格**；分栏**不能嵌套分栏** |
| 高亮块 | `<redoc-highlight emoji="..." fillColor="...">` | 支持段落、列表、图片、数学公式；**不支持表格、代码块、分栏** |
| 数学公式 | ` ```math ` 代码块，LaTeX 语法 | — |
| 流程图 | `<redoc-flow-diagram id width height url>` | `url` 只读，无法通过传入 url 修改流程图内容 |
| 绘图 | `<redoc-text-draw remoteTemplate theme>` | — |
| OKR | `<redoc-okr userOkrTaskId targetIds>` | — |
| 评论标记 | `<redoc-comment commentGid blockId>` | 元数据标签，**不要手动创建或修改** |

## 图片注意点

- 仅支持来源为 `https://xhs-doc.xhscdn.com/` 的图片；其他远端图片必须先下载，再通过 `docs:upload` 上传
- 本地图片须先创建文档再上传（依赖文档 shortcutId）
- 支持格式：jpeg、jpg、png、gif、webp；大小不超过 30M
- 上传时须按原图尺寸设置宽高，优先并行处理

## 其他注意点

- 标题仅支持 **1 ~ 4 级**，5 级及以上自动降级为 4 级
- 强制换行必须使用 `<br/>`，**不支持 `<br>`**
