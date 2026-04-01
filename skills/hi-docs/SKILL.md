---
name: redoc
version: 1.0.0
description: hi 官方 REDoc 文档 Skill。支持创建 REDoc 文档，支持通过 markdown 的语法，修改 REDoc 的内容，支持查看文档评论，回复文档评论，添加划词评论
metadata: { 'openclaw': { 'requires': { 'bins': ["pnpm"] } } }
---

# hi-docs

技能核心能力通过 CLI 提供，在执行 CLI 命令时，**禁止**猜测命令用法：

```bash
pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs --help              # 所有命令概览
```

# 文档 shortcutId

Hi 文档的 shortcutId 是文档的唯一标识符。

# 文档 spaceId

Hi 文档的 spaceId 是文档空间的唯一标识符。

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

## 文档编辑（docs:edit）— 推荐的编辑方式

`docs:edit` 命令支持两种编辑模式，均通过协同 WebSocket 提交，**不会丢失其他用户的并发编辑**：

### 模式一：块级操作（--ops）

通过 `--ops` 对文档进行**精细的块级增删改移**操作，无需全量替换文档内容。这是**最推荐的编辑方式**，因为它：

- 支持在一次调用中执行**多个操作**（批量编辑、插入、删除、移动）
- 使用精细 diff 算法，**保留 blockId 和评论等元数据**

#### 使用流程

1. 先通过 `docs:get` 获取文档内容和各块的 `blockId`
2. 构造 ops JSON 数组，描述要执行的操作
3. 调用 `docs:edit --ops` 提交操作

#### ops JSON 格式

`--ops` 参数接收一个 JSON 数组，每个元素是一个操作项（OPItem）。支持以下 6 种操作：

| op 类型 | 说明 | 必需字段 |
|---------|------|----------|
| `edit` | 替换目标块内容（精细 diff） | `blockId`, `content`（Markdown） |
| `insert_before` | 在目标块**前方**插入新内容 | `blockId`, `content`（Markdown） |
| `insert_after` | 在目标块**后方**插入新内容 | `blockId`, `content`（Markdown） |
| `remove` | 删除目标块 | `blockId` |
| `move_before` | 将源块移到目标块**前方** | `blockId`（源块）, `targetBlockId`（目标块） |
| `move_after` | 将源块移到目标块**后方** | `blockId`（源块）, `targetBlockId`（目标块） |

#### 示例

```bash
# 编辑单个块
pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --ops '[{"op":"edit","blockId":"blk1","content":"修改后的 **加粗** 内容"}]'

# 批量操作：编辑 + 在块后插入 + 删除
pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --ops '[
  {"op":"edit","blockId":"blk1","content":"更新的段落"},
  {"op":"insert_after","blockId":"blk1","content":"## 新章节\n\n新段落内容"},
  {"op":"remove","blockId":"blk3"}
]'

# 移动块
pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --ops '[
  {"op":"move_before","blockId":"blk5","targetBlockId":"blk1"}
]'

# 从 stdin 读取 ops（适合大量操作）
cat ops.json | pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --ops -
```

#### 注意事项

- `content` 字段使用 REDoc-flavored Markdown 语法（见下方语法规范）尤其注意内容的转义
- 多个操作按数组顺序依次执行，后续操作基于前序操作执行后的文档状态
- `edit` 操作会使用 blockDiff 引擎产出最小操作集，保留块内的评论等元数据
- `blockId` 可通过 `docs:get` 获取
- **`edit` 操作的 `content` 中，未更改的部分应尽量与原始 Markdown 内容保持一致**，避免对未修改的文本进行不必要的重写或格式变更，以减少 diff 噪音并保留评论等元数据

### 模式二：全量替换（--content）

⚠️ **整篇改写时使用**。通过 `--content` 传入完整的 Markdown 内容，全量替换文档。

- **评论锚点会全部丢失**，在**使用前必须要向用户确认**
- `--ops` 和 `--content` 互斥，不能同时使用

#### 示例

```bash
# 全量替换文档内容
pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --content '# 新标题\n\n全量替换的内容'

# 从 stdin 读取内容（适合大文档）
cat document.md | pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:edit --shortcut-id doc_abc123 --content -
```

# 历史版本管理（docs:history）

当 `docs:edit` 编辑操作出现问题（如误修改、内容错误等），可使用 `docs:history` 命令查看或恢复本地保存的历史版本。

**注意!!! 在恢复前必须向用户确认，并向用户说明：恢复至所选历史版本后，该版本之后的所有编辑将丢失，是否继续。**

### 工作原理

- 每次 `docs:edit` 执行前，会自动在本地 `~/.hws/docs-history/` 目录中保存编辑前的文档 SlateJSON 快照，恢复也会被认为是个编辑操作
- 每个文档（shortcutId）按时间顺序维护最多 **30 个历史版本**，超出上限时自动删除最旧的版本
- 整个历史目录最多保留最近操作的 **20 个文档**的历史记录，超出上限时自动删除最久未操作的文档历史目录

# 查看文档评论

- 使用 `### 划词内容：「anchorContent」` 按 anchor 分组
- 每组内用**表格**展示：评论者 | 内容 | 时间
- `imageUrlList` 中的图片追加在内容后：`![图片n](url)`，多张用空格分隔

# 回复文档评论

回复前**必须先 `docs:comment-read`** 获取 anchorId。

- 回复**具体评论**时，自动 @该评论作者（邮箱加入 `mentionUserAccountIdList`，内容开头加 `@显示名称`），与用户手动 @的人叠加去重
- 仅在划词下发表评论（未指定具体评论）时，不自动 @
- `commentContent` 中有 @提及时，必须同步填入 `mentionUserAccountIdList`
- 待办事项必须用 `- [ ]` 格式，不用有序列表

# 添加文档评论 ( 划词评论 )

通过 `docs:comment-add` 命令可以给文档中的 **指定文本** 划词添加评论。但如果你需要对已有的评论进行回复应该优先使用 **回复文档评论**
- 支持通过 `imageUrlList` 参数附带图片，暂不支持 @提及
- 如果你需要对已有评论进行恢复优先使用 **回复文档评论**

### 注意事项

- `blockId` 可通过 `docs:get` 获取
- `matchText` 必须是文档中实际存在的文本片段
- `commentContent` 中有 @提及时，必须同步填入 `mentionUserAccountIdList`
- 待办事项必须用 `- [ ]` 格式，不用有序列表

# 文档内容格式 REDoc-flavored Markdown 语法规范

文档内容使用 **REDoc-flavored Markdown** 格式，这是标准 Markdown 的扩展版本。

**REDoc-flavored Markdown** 这是标准 Markdown 的扩展版本，支持Redoc文档的自定义格式。

## ⚠️ Markdown 内容特殊字符转义规则（重要）

在创建文档（`docs:create`）、编辑文档（`docs:edit`）时，**Markdown 内容中的特殊字符必须进行转义**，否则会导致解析报错或内容渲染异常。

### 转义规则对照表

| 原始字符 | 转义写法 | 说明 |
|---------|---------|------|
| `<` | `&lt;` | 小于号，避免被解析为 HTML/JSX 标签 |
| `>` | `&gt;` | 大于号，避免被解析为引用块或 HTML 标签 |
| `\|` | `&#124;` | 竖线，避免被解析为表格分隔符 |
| `{` | `&#123;` | 左花括号，避免被解析为 JSX 表达式 |
| `}` | `&#125;` | 右花括号，避免被解析为 JSX 表达式 |

### 何时需要转义

- 当 `<`、`>` 作为**普通文本**出现（非 HTML/JSX 标签用途）时，必须转义
  - 例：`3 &lt; 5` 、`x &gt; 0`、`泛型 List&lt;String&gt;`
- 当 `|` 出现在**表格单元格内容**中且非表格分隔符时，必须转义
- 当 `{`、`}` 出现在**普通文本**中（非 JSX 属性如 `ratio={0.5}` 的用途）时，必须转义
  - 例：`JSON 格式 &#123;"key": "value"&#125;`

### 不需要转义的场景

- **代码块内部**（` ``` ` 包裹的内容）：代码块内不需要转义
- **行内代码**（`` ` `` 包裹的内容）：行内代码内不需要转义
- **HTML/JSX 标签**本身：如 `<font color="red">文字</font>` 中的 `<font>` 不需要转义
- **JSX 属性值**：如 `ratio={0.5}` 中的 `{` `}` 不需要转义

### 示例

```markdown
<!-- ❌ 错误写法 —— 会导致解析失败 -->
如果 x > 0 且 y < 10，则条件成立。
返回值格式：{code: 200, data: {...}}

<!-- ✅ 正确写法 -->
如果 x &gt; 0 且 y &lt; 10，则条件成立。
返回值格式：&#123;code: 200, data: &#123;...&#125;&#125;
```


## 一、标题

支持 **1 ~ 4 级** 标题。5 级及以上标题会被自动降级处理为 4 级标题。

**语法：**

```markdown
# 一级标题
## 二级标题
### 三级标题
#### 四级标题
##### 五级标题（等同于四级）
```

> **注意**：Redoc Markdown 最多渲染 4 个视觉级别的标题，请避免使用 5 级或更深层次的标题结构。

---

## 二、段落与换行

**普通段落**：一段或多段文字，段落之间以空行分隔。

```markdown
这是第一段内容。

这是第二段内容。
```

**强制换行**：在行尾添加两个空格，可在段落内强制换行。

```markdown
第一行内容
第二行内容（两个空格后换行）
```

也可使用 HTML `<br>` 标签：

```markdown
第一行内容<br>第二行内容
```

---

## 三、文本格式

支持标准的行内文本格式标记，可互相嵌套。

| 效果 | 语法 |
|------|------|
| **加粗** | `**加粗文字**` 或 `__加粗文字__` |
| *斜体* | `*斜体文字*` 或 `_斜体文字_` |
| ~~删除线~~ | `~~删除线文字~~` |
| `行内代码` | `` `行内代码` `` |
| ***加粗+斜体*** | `***加粗且斜体***` |

**示例：**

```markdown
这段话包含 **加粗**、*斜体*、~~删除线~~ 和 `行内代码`。

***又粗又斜*** 的文字。
```

---

## 四、字体颜色

使用 `<font>` 标签为文字添加颜色和背景色，支持行内嵌套使用。

**语法：**

```markdown
<font color="颜色值">文字内容</font>

<font color="颜色值" backgroundColor="颜色值">文字内容</font>
```

**支持的颜色格式：**

| 格式 | 示例 |
|------|------|
| 十六进制（3位） | `#F00` |
| 十六进制（6位） | `#FF0000` |
| 十六进制（8位，含透明度） | `#FF0000CC` |
| RGB | `rgb(255, 0, 0)` |
| RGBA | `rgba(255, 0, 0, 0.5)` |
| HSL | `hsl(0, 100%, 50%)` |
| HSLA | `hsla(0, 100%, 50%, 0.5)` |
| CSS 命名颜色 | `red`、`blue`、`transparent` 等 100+ 种 |

**示例：**

```markdown
这是<font color="red">红色文字</font>，这是<font color="#0066FF" backgroundColor="rgba(0,102,255,0.1)">带背景色的蓝色文字</font>。
```

**支持嵌套：**

```markdown
<font color="red">红色<font color="blue">蓝色（覆盖父级）</font>继续红色</font>
```

---

## 五、列表

### 5.1 无序列表

使用 `-`、`*` 或 `+` 作为列表符号（子级缩进 2 或 4 个空格）。

```markdown
- 一级项目 A
- 一级项目 B
  - 二级嵌套项目
  - 二级嵌套项目
    - 三级嵌套项目
- 一级项目 C
```

### 5.2 有序列表

使用 `数字.` 作为列表符号。

```markdown
1. 第一项
2. 第二项
   1. 嵌套第一项
   2. 嵌套第二项
3. 第三项
```

> **注意**：有序列表的编号起始值由 Markdown 中的实际数字决定，后续编号会自动递增。

### 5.3 任务列表（Checkbox）

在无序列表项前添加 `[x]`（已完成）或 `[ ]`（未完成）标记，支持嵌套。

```markdown
- [x] 已完成的任务
- [ ] 待完成的任务
  - [x] 嵌套的已完成子任务
  - [ ] 嵌套的待完成子任务
```

---

## 六、引用块

使用 `>` 前缀表示引用，可**多行连续**或**嵌套**使用。引用块内部支持嵌套段落、列表等内容。

```markdown
> 这是一段引用文字。
> 可以跨多行书写。

> 第一段引用。
>
> 同一引用块的第二段内容。
```

---

## 七、代码块

使用三个反引号（` ``` `）包裹代码，并在开头注明语言。

**语法：**

````markdown
```语言标识符
代码内容
```
````

**支持的语言（42 种）及其别名：**

| 语言 | 标准标识符 | 可用别名 |
|------|-----------|---------|
| JavaScript | `javascript` | `js`、`node`、`nodejs` |
| TypeScript | `typescript` | `ts` |
| JSX | `jsx` | `react` |
| TSX | `tsx` | — |
| Python | `python` | `py`、`python3`、`py3` |
| Java | `java` | — |
| C | `c` | — |
| C++ | `cpp` | `c++`、`cplusplus` |
| C# | `csharp` | `c#`、`cs` |
| Go | `go` | `golang` |
| Rust | `rust` | `rs` |
| Ruby | `ruby` | `rb` |
| Swift | `swift` | — |
| Kotlin | `kotlin` | `kt` |
| Dart | `dart` | — |
| PHP | `php` | `php3`~`php5` |
| SQL | `sql` | `mysql`、`postgresql`、`postgres`、`plsql` |
| HTML | `html` | `htm` |
| CSS | `css` | `scss`、`sass`、`stylus` |
| Less | `less` | — |
| XML | `xml` | `svg` |
| JSON | `json` | `json5` |
| YAML | `yaml` | `yml` |
| Bash | `bash` | — |
| Shell | `shell` | `sh`、`zsh`、`fish` |
| Markdown | `markdown` | `md` |
| GraphQL | `graphql` | `gql` |
| HTTP | `http` | `https` |
| Nginx | `nginx` | `nginxconf` |
| PowerShell | `powershell` | `ps1`、`pwsh` |
| Objective-C | `objectivec` | `objc`、`objective-c` |
| LaTeX | `latex` | `tex` |
| MATLAB | `matlab` | — |
| Django/Jinja | `django` | `jinja`、`jinja2` |
| Prolog | `prolog` | — |
| Visual Basic | `vb` | `vbnet`、`visualbasic` |
| R | `r` | — |
| CMake | `cmake` | — |
| GLSL | `glsl` | — |
| 纯文本 | `plaintext` | `text`、`txt` |

> 未识别的语言标识符会自动降级为 `plaintext`。

**示例：**

````markdown
```javascript
function greet(name) {
  return `Hello, ${name}!`
}
```

```python
def greet(name):
    return f"Hello, {name}!"
```
````

---

## 八、数学公式

使用语言标识符 `math` 的代码块来书写数学公式（LaTeX 语法）。

**语法：**

````markdown
```math
公式内容（LaTeX 格式）
```
````

**示例：**

````markdown
```math
E = mc^2
```

```math
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
```
````

---

## 九、表格

遵循 GFM 表格语法，支持**三种列对齐方式**。

**语法：**

```markdown
| 列标题1 | 列标题2 | 列标题3 |
|:--------|:-------:|--------:|
| 左对齐  |  居中   |  右对齐 |
| 数据    |  数据   |    数据 |
```

**对齐标记说明：**

| 对齐方式 | 分隔符格式 |
|---------|-----------|
| 左对齐（默认） | `|------|` 或 `|:-----|` |
| 居中对齐 | `|:----:|` |
| 右对齐 | `|-----:|` |

**特性：**
- 列宽根据单元格内容自动计算（支持中英文混合）
- 表头单独占第一行
- 单元格内支持行内格式（加粗、斜体、链接、行内代码等）
- 单元格内支持多个块（段落），使用 `<split/>` 标签分隔

**示例：**

```markdown
| 功能模块 | 完成状态 | 负责人 |
|:---------|:-------:|------:|
| 用户登录 | **已完成** | 张三 |
| 数据统计 | 进行中 | 李四 |
| 报表导出 | 未开始 | — |
```

### 9.1 单元格内多块内容（`<split/>`）

> **Redoc Markdown 扩展语法**

标准 GFM 表格的单元格只能包含一行内容。Redoc Markdown 通过 `<split/>` 标签扩展了这一限制，允许单元格内包含**多个独立的块级内容**（段落、列表、代码等）。

**语法：**

在单元格内使用 `<split/>` 分隔不同的块。每个 `<split/>` 前后的内容会被解析为独立的块节点。

```markdown
| 列标题1 | 列标题2 |
|---------|---------|
| 第一段内容 <split/> 第二段内容 | 简单内容 |
| **加粗文字** <split/> *斜体文字* | 多段 <split/> 效果 |
```

**说明：**
- `<split/>` 是自闭合标签，前后的内容会分别成为单元格中独立的段落（paragraph）
- 单元格中可以使用多个 `<split/>` 分隔出多个块
- `<split/>` 分隔的每个块内支持完整的行内 Markdown 语法（加粗、斜体、链接、颜色等）
- 若单元格只有一个段落，不需要使用 `<split/>`

**SlateJSON 对应结构：**

一个包含两个段落的单元格在 SlateJSON 中的结构为：

```json
{
  "type": "td",
  "children": [{
    "type": "table-cell-block",
    "children": [
      { "type": "paragraph", "children": [{ "text": "第一段内容" }] },
      { "type": "paragraph", "children": [{ "text": "第二段内容" }] }
    ]
  }]
}
```

---

## 十、图片

**语法：**

```markdown
![替代文字](https://xhs-doc.xhscdn.com/example/arch.png?redoc-key=xxx&redoc-w=xxx&redoc-h=xxx)
```

- redoc-key：文件 fileId
- redoc-w：图片宽度
- redoc-h：图片高度

**远端图片：** 仅支持 `https://xhs-doc.xhscdn.com/` 图片来源，在**创建文档**和**更新文档**阶段其他远端链接必须先下载再通过 `pnpm dlx @xhs/hi-workspace-cli@0.2.5 docs:upload` 上传才能更新

**本地图片：** 新文档内插入图片必须先创建文档，才能上传图片，因为图片上传依赖文档 shortcutId

**上传&下载最佳实践：**

- 优先考虑并行优化
- 上传场景在用户没有要求的前提下，必须按原图尺寸设置宽高

**注意：**仅支持 jpeg, jpg, png, gif, webp 格式的图片文件，大小不能超过 30 M

---

## 十一、链接

**语法：**

```markdown
[链接文字](URL)
```

**示例：**

```markdown
[访问官网](https://www.xiaohongshu.com)
```

**特殊链接说明：**

以下内部平台链接会被自动识别，并以卡片或预览形式呈现：

- **RedBI 数据平台**：`https://redbi.devops.xiaohongshu.com/...`
- **财务 AI 工作台**：对应内部财务系统链接
- **X-Ray 可观测平台**：对应内部监控系统链接

---

## 十二、分割线

在单独一行使用三个或更多 `-`、`*` 或 `_`，产生水平分割线。

```markdown
---

***

___
```

---

## 十三、分栏（扩展）

> **Redoc Markdown 扩展语法**

使用 `<redoc-columns>` 和 `<redoc-column>` JSX 标签创建多列布局, **多列布局最多支持5列，不能超过这个值**。

**语法：**

```markdown
<redoc-columns>
  <redoc-column ratio={列宽比例} fillColor="背景色">
    此处填写列内容（支持标准 Markdown 语法）
  </redoc-column>
  <redoc-column ratio={列宽比例} fillColor="背景色">
    此处填写列内容
  </redoc-column>
</redoc-columns>
```

**属性说明：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `ratio` | `number` | 该列占总宽度的比例，范围 `0.12 ~ 1`，多列之和应为 `1` |
| `fillColor` | `string` | 列背景色，见下方色值表 |

**`fillColor` 可选值：**

| 值 | 背景颜色 |
|----|---------|
| `white` | 白色 `#ffffff` |
| `grey` | 浅灰 `rgba(0, 0, 0, 0.05)` |
| `red` | 浅红 `rgba(229, 0, 0, 0.09)` |
| `orange` | 浅橙 `rgba(229, 83, 0, 0.09)` |
| `yellow` | 浅黄 `rgba(229, 182, 0, 0.09)` |
| `green` | 浅绿 `rgba(0, 178, 83, 0.09)` |
| `blue` | 浅蓝 `rgba(0, 48, 229, 0.09)` |
| `purple` | 浅紫 `rgba(77, 0, 229, 0.09)` |

**⚠️ 注意：分栏的列内仅支持以下类型语法：**

- 段落、标题（h1 ~ h4）
- 无序/有序/任务列表
- 图片、代码块
- 引用块、高亮块、分割线
- 数学公式、流程图、OKR

**示例——两栏等分布局：**

```markdown
<redoc-columns>
  <redoc-column ratio={0.5} fillColor="grey">
    ## 左栏标题

    这里是左栏的正文内容，可以包含任意 Markdown 语法。

    - 列表项 1
    - 列表项 2
  </redoc-column>
  <redoc-column ratio={0.5} fillColor="white">
    ## 右栏标题

    这里是右栏的正文内容。

    ```javascript
    console.log("代码也可以放在栏内");
```
  </redoc-column>
</redoc-columns>
```

**示例——三栏布局：**

```markdown
<redoc-columns>
  <redoc-column ratio={0.33}>左栏内容</redoc-column>
  <redoc-column ratio={0.34}>中栏内容</redoc-column>
  <redoc-column ratio={0.33}>右栏内容</redoc-column>
</redoc-columns>
```

**示例——非均等分栏：**

```markdown
<redoc-columns>
  <redoc-column ratio={0.3} fillColor="yellow">侧边栏（30%）</redoc-column>
  <redoc-column ratio={0.7}>主内容区（70%）</redoc-column>
</redoc-columns>
```

---

## 十四、高亮块（扩展）

> **Redoc Markdown 扩展语法**

高亮块用于突出显示重要信息，可配置背景色和前缀图标。

**语法：**

```markdown
<redoc-highlight emoji="图标名" fillColor="背景色">
  内容（支持标准 Markdown 语法）
</redoc-highlight>
```

**属性说明：**

| 属性 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `emoji` | `string` | 否 | 前缀图标，见下方图标列表 |
| `fillColor` | `string` | 否 | 背景色，见下方色值表 |

**`fillColor` 可选值：**

| 值 | 背景颜色 |
|----|---------|
| `grey` | 浅灰 |
| `red` | 浅红 |
| `orange` | 浅橙 |
| `yellow` | 浅黄 |
| `green` | 浅绿 |
| `cyan-blue` | 浅青蓝 |
| `blue` | 浅蓝 |
| `purple` | 浅紫 |

**`emoji` 可选值（65 种）：**

| 类别 | 图标名 |
|------|--------|
| 常用提示 | `dengpao`（灯泡）、`tuding`（图钉）、`dui`（对勾）、`cuo`（叉号）、`gantanhao`（感叹号）、`laba`（喇叭）、`todo` |
| 表情动作 | `hecai`（喝彩）、`dianzan`（点赞）、`dianzan1`、`goushou`（勾手）、`woshou`（握手）、`guzhang`（鼓掌）、`jiayou`（加油）、`nuli`（努力）、`ganen`（感恩）、`ye`（耶）、`ok`、`zhiyou`（指右） |
| 交流沟通 | `goutong`（沟通）、`nenya`（念呀）、`lihe`（礼盒）、`xiaohongshu`（小红书） |
| 自然天气 | `taiyang`（太阳）、`yueliang`（月亮）、`caihong`（彩虹）、`huoyan`（火焰）、`shuidi`（水滴）、`meigui`（玫瑰）、`yinghua`（樱花） |
| 动物 | `haitun`（海豚）、`laohu`（老虎）、`zhuzhu`（猪猪）、`mianyang`（绵羊） |
| 食物饮品 | `pijiu`（啤酒）、`kafei`（咖啡）、`dangao`（蛋糕）、`lizi`（梨子）、`taozi`（桃子）、`caomei`（草莓）、`huanggua`（黄瓜）、`lajiao`（辣椒）、`hongshu`（红薯） |
| 物品 | `feiji`（飞机）、`liwu`（礼物）、`gouwuche`（购物车）、`fangdajing`（放大镜）、`qiqiu`（气球）、`zhadan`（炸弹）、`xiaodao`（小刀）、`fu`（符文） |
| 财富 | `facai`（发财）、`jin`（金）、`man`（满）、`ke`（可）、`dun`（盾）、`you`（优）、`jia1`（甲） |
| 眼睛表情 | `yanjing`（眼睛）、`huanglian`（黄脸）、`heilian`（黑脸） |
| 数字 | `0` ~ `9` |

**高亮块内支持的内容类型：**

- 段落、标题（h1 ~ h4）
- 无序/有序/任务列表
- 图片、数学公式

**示例：**

```markdown
<redoc-highlight emoji="tuding" fillColor="yellow">
  **重要提示**：这是一条重要信息，请务必注意！
</redoc-highlight>

<redoc-highlight emoji="dui" fillColor="green">
  操作成功，以下是执行步骤：

  1. 第一步
  2. 第二步
  3. 完成
</redoc-highlight>

<redoc-highlight emoji="cuo" fillColor="red">
  **已知问题**：该功能在某些场景下可能存在异常。
</redoc-highlight>

<redoc-highlight emoji="dengpao" fillColor="blue">
  小提示：无需填写任何属性即可使用默认样式。
</redoc-highlight>
```

**仅设置背景色（无图标）：**

```markdown
<redoc-highlight fillColor="grey">
  这是一个灰色背景的提示块，没有前缀图标。
</redoc-highlight>
```

---

## 十五、流程图（扩展）

> **Redoc Markdown 扩展语法**

嵌入流程图组件（内容在编辑器内单独配置）。**你可以通过流程图的 url 来拿到对应的图片地址。但不能通过 传入 url 来更改流程图内容**

**语法：**

```markdown
<redoc-flow-diagram id="唯一标识" width={宽度} height={高度} url="图片地址"></redoc-flow-diagram>
```

**属性说明：**

| 属性 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `id` | `string` | 否 | 流程图唯一标识 |
| `width` | `number` | 否 | 渲染宽度（像素） |
| `height` | `number` | 否 | 渲染高度（像素） |
| `url` | `string` | 否 | 图片地址 |

**示例：**

```markdown
<redoc-flow-diagram id="architecture-v1" width={800} height={600} url="https://xhs-doc.xhscdn.com/example/arch.png"></redoc-flow-diagram>
```

---

## 十六、绘图（扩展）

> **Redoc Markdown 扩展语法**

嵌入基于模板的绘图组件（如时序图、架构图等）。

**语法：**

```markdown
<redoc-text-draw remoteTemplate="模板内容" remoteView="远程视图地址" theme="主题"></redoc-text-draw>
```

**属性说明：**

| 属性 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `remoteTemplate` | `string` | 否 | 绘图模板内容（多行文本） |
| `remoteView` | `string` | 否 | 远程预览地址 |
| `theme` | `string` | 否 | 主题（如 `light`、`dark`） |

**示例：**

```markdown
<redoc-text-draw remoteTemplate="graph TD\nA-->B" theme="light"></redoc-text-draw>
```

---

## 十七、OKR（扩展）

> **Redoc Markdown 扩展语法**

嵌入 OKR 目标管理组件，关联具体的 OKR 任务数据。

**语法：**

```markdown
<redoc-okr userOkrTaskId="任务ID" targetIds="目标ID1,目标ID2"></redoc-okr>
```

**属性说明：**

| 属性 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `userOkrTaskId` | `string` | 否 | 用户 OKR 任务 ID |
| `targetIds` | `string` | 否 | 目标 ID 列表，多个以英文逗号分隔 |


**示例：**

```markdown
<redoc-okr userOkrTaskId="task-2026-q1" targetIds="obj-1,obj-2,obj-3"></redoc-okr>
```

---

## 十八、评论（扩展）

> **Redoc Markdown 扩展语法**

评论标记用于在 Markdown 文本中保留 Redoc 文档的批注（评论）信息，实现 SlateJSON ↔ Markdown 的双向无损转换。

> **注意**：评论标记是**元数据标签**，用于在 Markdown 格式中保留评论的关联信息。评论的实际内容（评论文本、回复等）存储于 Redoc 服务端，Markdown 中仅记录关联 ID。

### 18.1 内联评论

当文档中某段文字被标注了评论时，该文字片段会被 `<redoc-comment>` 标签包裹。

**语法：**

```markdown
<redoc-comment commentGid="评论组ID" blockId="所在块ID">被评论的文字</redoc-comment>
```

**属性说明：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `commentGid` | `string` | 评论组全局唯一 ID（由 Redoc 服务端生成），多个 ID 用英文逗号分隔 |
| `blockId` | `string` | 该评论所在块节点的 blockId |

**示例：**

```markdown
这是一段包含<redoc-comment commentGid="7620881188339128345" blockId="c38b57a47a98dd173e48e75ed6199c19">评论标注</redoc-comment>的文字。
```

**多评论标注：** 若同一文字片段被多个评论标注，多个评论 ID 用逗号连接写入同一个 `commentGid` 属性中（单个标签，不嵌套）：

```markdown
<redoc-comment commentGid="7620881188339128345,7620881819699159918" blockId="c38b57a47a98dd173e48e75ed6199c19">同时被两个评论标注的文字</redoc-comment>
```

### 18.2 块级评论

当评论标注在整个块节点（如图片、流程图等 void 块）上时，整个块的 Markdown 输出会被 `<redoc-comment>` 包裹：

**示例（图片块评论）：**

```markdown
<redoc-comment commentGid="7620869329934387633" blockId="cb05db8c4874dd4d4a3a24be47970b54">![](https://xhs-doc.xhscdn.com/104004dg31tmk7gibmo00td7120)</redoc-comment>
```

### 18.3 SlateJSON 对应格式

在 SlateJSON 中，评论信息以以下方式存储：

**内联文本节点（Text）：**

```json
{
  "text": "被评论的文字",
  "commentGroupIds": ["7620881188339128345", "7620881819699159918"],
  "COMMENT_7620881188339128345": 1,
  "COMMENT_7620881819699159918": 1
}
```

**块节点（Descendant）：**

```json
{
  "type": "image",
  "blockId": "cb05db8c4874dd4d4a3a24be47970b54",
  "commentGroupIds": ["7620869329934387633"],
  "COMMENT_7620869329934387633": 1,
  "url": "https://xhs-doc.xhscdn.com/...",
  "children": [{ "text": "" }]
}
```

### 18.4 转换规则

| 方向 | 规则 |
|------|------|
| SlateJSON → Markdown | 文本节点有 `commentGroupIds` → 所有 ID 逗号连接写入单个 `<redoc-comment>` 标签；块节点有 `commentGroupIds` → 整块输出被 `<redoc-comment>` 包裹 |
| Markdown → SlateJSON | 解析 `<redoc-comment>` 标签 → 将 `commentGid` 按逗号分割恢复为 `commentGroupIds` 数组 |

---

## 十九、嵌套规则

使用扩展组件时，请遵守以下嵌套限制：

### 高亮块（`<redoc-highlight>`）内可嵌套的内容：

- 段落、标题（h1 ~ h4）
- 无序/有序/任务列表
- 图片
- 数学公式（`inline-equation`）

### 分栏列（`<redoc-column>`）内可嵌套的内容：

- 段落、标题（h1 ~ h4）
- 无序/有序/任务列表
- 图片、代码块
- 引用块、**高亮块**（支持高亮块嵌套在分栏内）
- 分割线
- 数学公式、流程图、OKR

### 不支持的嵌套：

- 分栏不能嵌套分栏（`<redoc-columns>` 内不能再放 `<redoc-columns>`）
- 表格不能放在分栏或高亮块当中

---

## 完整示例

以下是一个综合运用 Redoc Markdown 各种语法的文档示例：

````markdown
# 项目技术文档

本文档描述了 **XXX 系统** 的核心功能与技术规范。

---

## 功能概览

<redoc-highlight emoji="tuding" fillColor="yellow">
**版本提示**：以下内容适用于 v2.0 及以上版本。
</redoc-highlight>

<redoc-columns>
  <redoc-column ratio={0.5} fillColor="grey">
    ### 已上线功能

    - [x] 用户认证
    - [x] 数据看板
    - [x] 报表导出
  </redoc-column>
  <redoc-column ratio={0.5} fillColor="white">
    ### 规划中功能

    - [ ] 多语言支持
    - [ ] 移动端适配
    - [ ] 离线模式
  </redoc-column>
</redoc-columns>

---

## 接口规范

| 接口名称 | 方法 | 路径 | 说明 |
|:---------|:----:|:-----|:-----|
| 用户登录 | `POST` | `/api/auth/login` | 返回 JWT Token |
| 获取用户信息 | `GET` | `/api/user/info` | 需要鉴权 |
| 数据查询 | `POST` | `/api/data/query` | 支持分页 |

---

## 代码示例

```typescript
async function fetchUserInfo(token: string): Promise<User> {
  const response = await fetch('/api/user/info', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.json()
}
```

---

## 公式说明

系统采用如下算法计算用户活跃度：

```math
\text{活跃度} = \frac{\text{DAU}}{\text{MAU}} \times 100\%
```

---

## 架构图

<redoc-flow-diagram id="system-arch" width={900} height={500}></redoc-flow-diagram>

---

## 字体颜色示例

<font color="red">**警告**</font>：请勿在生产环境直接执行以下操作。

操作状态：<font color="green">成功</font> / <font color="#FF6600">警告</font> / <font color="red">失败</font>
````
