# REDoc-flavored Markdown 语法规范

文档内容使用 **REDoc-flavored Markdown** 格式，是标准 Markdown 的扩展版本，支持 Redoc 文档的自定义格式。

---

## ⚠️ 特殊字符转义规则（重要）

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
  - 例：`3 &lt; 5`、`x &gt; 0`、`泛型 List&lt;String&gt;`
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

---

## 标准 Markdown 支持

以下为标准 GFM/CommonMark 语法，REDoc 均支持，无特殊限制：

- **标题**：支持 1 ~ 4 级（`#` ~ `####`），5 级及以上自动降级为 4 级
- **文本格式**：加粗（`**`）、斜体（`*`）、删除线（`~~`）、行内代码（`` ` ``）
- **列表**：无序列表（`-`/`*`/`+`）、有序列表（`数字.`）、任务列表（`- [ ]` / `- [x]`）
- **引用块**：`>` 前缀，支持多行与嵌套
- **代码块**：三个反引号包裹，支持 42 种语言（见下方语言列表）
- **表格**：GFM 表格语法，支持左对齐 `|:----|`、居中 `|:----:|`、右对齐 `|----:|`
- **图片**：`![alt](url)` 语法，详见图片规则
- **链接**：`[文字](URL)` 语法
- **分割线**：`---` / `***` / `___`

### 代码块支持的语言（42 种）

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
| 数学公式 | `math` | — |

> 未识别的语言标识符会自动降级为 `plaintext`。
> `math` 使用 LaTeX 语法渲染数学公式。

---

## 扩展语法

以下为 REDoc 专有扩展，标准 Markdown 不支持。

### 字体颜色（`<font>`）

使用 `<font>` 标签为文字添加颜色和背景色，支持行内嵌套使用。

```markdown
<font color="颜色值">文字内容</font>
<font color="颜色值" backgroundColor="颜色值">文字内容</font>
```

**支持的颜色格式**：十六进制（`#F00`、`#FF0000`、`#FF0000CC`）、RGB、RGBA、HSL、HSLA、CSS 命名颜色（`red`、`blue` 等 100+ 种）

```markdown
这是<font color="red">红色文字</font>，这是<font color="#0066FF" backgroundColor="rgba(0,102,255,0.1)">带背景色的蓝色文字</font>。
```

---

### 表格单元格多块内容（`<split/>`）

标准 GFM 表格单元格只能包含一行内容。REDoc 通过 `<split/>` 标签允许单元格内包含**多个独立的块级内容**。

```markdown
| 列标题1 | 列标题2 |
|---------|---------|
| 第一段内容 <split/> 第二段内容 | 简单内容 |
| **加粗文字** <split/> *斜体文字* | 多段 <split/> 效果 |
```

- `<split/>` 是自闭合标签，前后内容会成为独立段落
- 单元格可使用多个 `<split/>` 分隔多个块
- 每块内支持完整的行内 Markdown 语法

---

### 分栏布局（`<redoc-columns>`）

使用 `<redoc-columns>` 和 `<redoc-column>` 创建多列布局。

**⚠️ 重要限制：**
- **最多支持 5 列**，不能超过
- **分栏不能嵌套分栏**（`<redoc-columns>` 内不能再放 `<redoc-columns>`）
- **表格不能放在分栏内**

```markdown
<redoc-columns>
  <redoc-column ratio={0.5} fillColor="grey">
    ## 左栏标题

    这里是左栏的正文内容。

    - 列表项 1
    - 列表项 2
  </redoc-column>
  <redoc-column ratio={0.5} fillColor="white">
    ## 右栏标题

    这里是右栏的正文内容。
  </redoc-column>
</redoc-columns>
```

**`<redoc-column>` 属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `ratio` | `number` | 该列占总宽度的比例，范围 `0.12 ~ 1`，多列之和应为 `1` |
| `fillColor` | `string` | 列背景色：`white`、`grey`、`red`、`orange`、`yellow`、`green`、`blue`、`purple` |

**分栏列内支持的内容类型：**
段落、标题（h1 ~ h4）、无序/有序/任务列表、图片、代码块、引用块、高亮块、分割线、数学公式、流程图、OKR

---

### 高亮块（`<redoc-highlight>`）

用于突出显示重要信息，可配置背景色和前缀图标。

```markdown
<redoc-highlight emoji="图标名" fillColor="背景色">
  内容（支持标准 Markdown 语法）
</redoc-highlight>
```

**属性说明：**

| 属性 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `emoji` | `string` | 否 | 前缀图标，见下方图标列表 |
| `fillColor` | `string` | 否 | 背景色：`grey`、`red`、`orange`、`yellow`、`green`、`cyan-blue`、`blue`、`purple` |

**`emoji` 可选值（65 种）：**

| 类别 | 图标名 |
|------|--------|
| 常用提示 | `dengpao`（灯泡）、`tuding`（图钉）、`dui`（对勾）、`cuo`（叉号）、`gantanhao`（感叹号）、`laba`（喇叭）、`todo` |
| 表情动作 | `hecai`、`dianzan`、`dianzan1`、`goushou`、`woshou`、`guzhang`、`jiayou`、`nuli`、`ganen`、`ye`、`ok`、`zhiyou` |
| 交流沟通 | `goutong`、`nenya`、`lihe`、`xiaohongshu` |
| 自然天气 | `taiyang`、`yueliang`、`caihong`、`huoyan`、`shuidi`、`meigui`、`yinghua` |
| 动物 | `haitun`、`laohu`、`zhuzhu`、`mianyang` |
| 食物饮品 | `pijiu`、`kafei`、`dangao`、`lizi`、`taozi`、`caomei`、`huanggua`、`lajiao`、`hongshu` |
| 物品 | `feiji`、`liwu`、`gouwuche`、`fangdajing`、`qiqiu`、`zhadan`、`xiaodao`、`fu` |
| 财富 | `facai`、`jin`、`man`、`ke`、`dun`、`you`、`jia1` |
| 眼睛表情 | `yanjing`、`huanglian`、`heilian` |
| 数字 | `0` ~ `9` |

**高亮块内支持的内容类型：** 段落、标题（h1 ~ h4）、无序/有序/任务列表、图片、数学公式

**⚠️ 注意：** 高亮块内**不支持**表格、分栏、代码块

```markdown
<redoc-highlight emoji="tuding" fillColor="yellow">
  **重要提示**：这是一条重要信息，请务必注意！
</redoc-highlight>

<redoc-highlight emoji="dui" fillColor="green">
  操作成功！
</redoc-highlight>

<redoc-highlight emoji="cuo" fillColor="red">
  **已知问题**：该功能在某些场景下可能存在异常。
</redoc-highlight>
```

---

### 流程图（`<redoc-flow-diagram>`）

嵌入流程图组件。**注意：只能通过 `url` 读取图片，不能通过传入 `url` 来更改流程图内容。**

```markdown
<redoc-flow-diagram id="唯一标识" width={宽度} height={高度} url="图片地址"></redoc-flow-diagram>
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 流程图唯一标识 |
| `width` | `number` | 渲染宽度（像素） |
| `height` | `number` | 渲染高度（像素） |
| `url` | `string` | 图片地址（只读） |

---

### 绘图（`<redoc-text-draw>`）

嵌入基于模板的绘图组件（如时序图、架构图等）。

```markdown
<redoc-text-draw remoteTemplate="graph TD\nA-->B" theme="light"></redoc-text-draw>
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `remoteTemplate` | `string` | 绘图模板内容（多行文本） |
| `remoteView` | `string` | 远程预览地址 |
| `theme` | `string` | 主题：`light`、`dark` |

---

### OKR（`<redoc-okr>`）

嵌入 OKR 目标管理组件，关联具体的 OKR 任务数据。

```markdown
<redoc-okr userOkrTaskId="task-2026-q1" targetIds="obj-1,obj-2,obj-3"></redoc-okr>
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `userOkrTaskId` | `string` | 用户 OKR 任务 ID |
| `targetIds` | `string` | 目标 ID 列表，多个以英文逗号分隔 |

---

### 评论标记（`<redoc-comment>`）

评论标记用于在 Markdown 中保留 Redoc 文档的批注关联信息，实现 SlateJSON ↔ Markdown 双向无损转换。

> **注意**：这是**元数据标签**，评论的实际内容存储于 Redoc 服务端，Markdown 中仅记录关联 ID。**不要手动创建或修改此标签。**

**内联评论**（某段文字被标注评论）：

```markdown
这是一段包含<redoc-comment commentGid="7620881188339128345" blockId="c38b57a47a98dd173e48e75ed6199c19">评论标注</redoc-comment>的文字。
```

**块级评论**（整个块节点被标注）：

```markdown
<redoc-comment commentGid="7620869329934387633" blockId="cb05db8c4874dd4d4a3a24be47970b54">![](https://xhs-doc.xhscdn.com/104004dg31tmk7gibmo00td7120)</redoc-comment>
```

---

## 图片规则

```markdown
![替代文字](https://xhs-doc.xhscdn.com/example/arch.png?redoc-key=xxx&redoc-w=xxx&redoc-h=xxx)
```

- `redoc-key`：文件 fileId
- `redoc-w`：图片宽度
- `redoc-h`：图片高度

**⚠️ 注意：**
- 仅支持 `https://xhs-doc.xhscdn.com/` 图片来源；其他远端链接必须先下载，再通过 `docs:upload` 上传
- 本地图片须先创建文档，再上传（图片上传依赖文档 shortcutId）
- 仅支持 jpeg、jpg、png、gif、webp 格式，大小不超过 30M
- 上传时须按原图尺寸设置宽高；优先并行上传

---

## 嵌套限制速查

| 容器 | 可嵌套 | 不可嵌套 |
|------|--------|---------|
| `<redoc-columns>` 内的列 | 段落、标题、列表、图片、代码块、引用块、高亮块、分割线、数学公式、流程图、OKR | 表格、分栏（不能嵌套分栏） |
| `<redoc-highlight>` | 段落、标题、列表、图片、数学公式 | 表格、分栏、代码块 |
