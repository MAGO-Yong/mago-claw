---
name: code-search
description: Search across all Xiaohongshu company code repositories using keywords, function names, class names, file names, and more. Use this skill whenever users want to find code implementations, locate specific functions or classes, understand how features are implemented across repositories, debug issues by finding similar code patterns, discover API usage examples, or explore unfamiliar codebases. This should be used even when users don't explicitly say "search code" - trigger it when they ask questions like "how is X implemented", "where is function Y used", "find examples of Z", "which repos use this API", or "show me error handling patterns". Also use this when users need to understand code structure before diving into specific files.
---

# Code Search - 小红书代码搜索

小红书 CodeSearch 是基于 Zoekt 构建的代码搜索引擎,为开发者提供快速、精准的代码搜索服务,帮助您在海量代码库中快速定位所需的代码片段。

## When to Use Code Search

Code Search is designed to help you discover and explore code across the entire company codebase. Understanding when and why to use it will help you work more efficiently:

### 🎯 Use Code Search When:

**Discovering implementations across unknown repositories**
- Why: You often don't know which repository contains the code you need. Code Search lets you cast a wide net across all repositories to find relevant implementations, which is far more efficient than guessing repository names or browsing through dozens of repos manually.
- Example: "How do other teams handle user authentication?" → Search `sym:UserAuth` or `content:"JWT token"`

**Finding usage examples and patterns**
- Why: The best way to learn how to use an API or pattern is to see real-world examples from production code. Code Search shows you how other engineers solved similar problems, helping you follow established patterns and avoid reinventing solutions.
- Example: "How should I use the payment API?" → Search `sym:PaymentService lang:java`

**Understanding feature implementations**
- Why: Before modifying or extending a feature, you need to understand how it currently works across the codebase. Code Search helps you locate all related code, including edge cases and dependencies you might otherwise miss.
- Example: "Where is the coupon validation logic?" → Search `sym:CouponValidator` or `content:"coupon validation"`

**Debugging and troubleshooting**
- Why: When investigating bugs, you need to find all occurrences of error messages, similar patterns, or related code. Code Search makes it easy to track down where issues might originate and how they're handled elsewhere.
- Example: "Where does this error come from?" → Search the exact error message in quotes

**Code refactoring and impact analysis**
- Why: Before renaming a function or changing an API, you need to know everywhere it's used. Code Search reveals all usages across repositories, preventing breaking changes and helping you assess the scope of refactoring work.
- Example: "What would break if I change this API?" → Search `sym:OldAPIName` to see all call sites

### 🔄 Combine Code Search with Other Tools:

**Code Search + Direct File Reading**
- Start with Code Search to discover which files are relevant, then use Read tool to examine specific files in detail
- Why: Code Search gives you the "map" of where things are, but reading full files gives you the complete context

**Code Search + CodeWiki**
- Use Code Search to find repositories, then use CodeWiki to understand their architecture and design
- Why: Code Search shows you "where" the code is, CodeWiki explains "how" the system is structured
- Workflow: Search → Find project ID → Query CodeWiki for architecture docs → Search again with better context

### ⚠️ When NOT to Use Code Search:

**You already know the exact file path**
- If you know the repository and file location, directly read the file instead
- Why: Direct file access is faster and gives you complete file contents with proper context

**Analyzing a single repository's structure**
- Use CodeWiki for understanding repository architecture, domain models, and design docs
- Why: CodeWiki provides curated, high-level architecture information that's better for understanding system design

**Very generic keywords**
- Avoid searching for common terms like "get", "set", "data" without additional filters
- Why: These will return thousands of irrelevant results. Always combine generic terms with language filters, repository filters, or use symbol search

## 功能特性

### 🔍 搜索范围
- **全公司代码覆盖**: 支持搜索全公司所有代码仓库
- **主分支搜索**: 当前仅支持搜索主分支 T+1 代码
- **快速索引**: 基于 Zoekt 引擎,提供毫秒级搜索响应

### ⚡ 搜索能力
- **Zoekt 语法**: 完全兼容 Zoekt 搜索语法,提供强大的搜索能力
- **正则表达式**: 支持复杂的正则表达式匹配
- **多维度过滤**: 支持按文件名、语言、仓库、分支等多维度过滤
- **符号搜索**: 直接搜索函数名、类名、方法名等代码符号

### 🔐 权限机制
- ✅ **无障碍搜索**: 可以搜索到全公司所有代码仓库主分支的结果
- ✅ **结果展示**: 即使是无权限的仓库,搜索结果也会正常展示
- ⚠️ **详情限制**: 对于无权限的仓库,无法查看完整代码详情
- 🔑 **权限申请**: 如需查看更多代码细节,请前往云效申请相应仓库权限

## 快速开始

```bash
# 基础搜索
./scripts/code_search.sh "function_name"

# 搜索符号(方法名/类名)
./scripts/code_search.sh "sym:GitResponse"

# 按编程语言搜索
./scripts/code_search.sh "error handling lang:go"

# 分页查询
./scripts/code_search.sh "wangtianyi" --page 2

# 增加上下文行数
./scripts/code_search.sh "GitResponse" --context 5
```

## Zoekt 搜索语法详解

### 1️⃣ 基础搜索

#### 关键字搜索
```bash
# 多个字符串在相同文件中搜索 (AND 操作)
./scripts/code_search.sh "error handler"

# 精确字符串匹配
./scripts/code_search.sh '"user login"'

# 多行代码搜索
./scripts/code_search.sh '"import os
import json"'
```

#### 符号搜索
```bash
# 搜索方法名、类名等符号
./scripts/code_search.sh "sym:GitResponse"
./scripts/code_search.sh "sym:UserService"
```

### 2️⃣ 字段过滤器

| 字段 | 别名 | 值类型 | 描述 | 示例 |
|------|------|--------|------|------|
| `file:` | `f:` | 文本/正则 | 搜索文件名 | `file:"main.go"` |
| `content:` | `c:` | 文本/正则 | 搜索文件内容 | `content:"search term"` |
| `lang:` | `l:` | 文本 | 按编程语言过滤 | `lang:python` |
| `repo:` | `r:` | 文本/正则 | 按仓库名过滤 | `repo:ee/backend` |
| `sym:` | - | 文本 | 搜索符号名称 | `sym:"MyFunction"` |
| `case:` | - | yes/no/auto | 大小写敏感匹配 | `case:yes content:"Foo"` |
| `regex:` | - | 正则表达式 | 使用正则匹配 | `regex:foo.*bar` |
| `branch:` | `b:` | 文本 | 在特定分支搜索 | `branch:main` |
| `archived:` | `a:` | yes/no | 过滤归档仓库 | `archived:no` |
| `fork:` | - | yes/no | 过滤 fork 仓库 | `fork:no` |
| `public:` | - | yes/no | 过滤公开仓库 | `public:yes` |
| `type:` | `t:` | filematch/filename/file/repo | 限制结果类型 | `type:filematch` |

### 3️⃣ 逻辑运算符

```bash
# AND 运算 (隐式,空格分隔)
./scripts/code_search.sh "user service"

# OR 运算
./scripts/code_search.sh '(repo:"project1" or repo:"project2") content:"bug"'

# NOT 运算 (使用 - 符号)
./scripts/code_search.sh 'content:"function" -file:test'

# 复杂布尔逻辑 (使用括号分组)
./scripts/code_search.sh '(lang:go or lang:java) (repo:"backend" or repo:"service")'
```

### 4️⃣ 正则表达式

```bash
# 搜索 Python 函数定义
./scripts/code_search.sh 'lang:python regex:/def\s+\w+\s*\(/'

# 搜索 Go 接口定义
./scripts/code_search.sh 'lang:go regex:/type\s+\w+\s+interface/'

# 匹配特定文件扩展名
./scripts/code_search.sh 'file:/.*\.(go|java|py)$/ content:"TODO"'
```

## 实际使用示例

### 场景 1: 查找特定功能实现
```bash
# 搜索用户登录相关代码
./scripts/code_search.sh "sym:UserLogin lang:java"

# 在特定仓库中搜索
./scripts/code_search.sh 'sym:UserLogin repo:ee/auth-service'
```

### 场景 2: 代码审查和学习
```bash
# 查找错误处理模式
./scripts/code_search.sh 'lang:go content:"error handling"'

# 查找公开仓库中的最佳实践
./scripts/code_search.sh 'public:yes lang:go content:"context"'
```

### 场景 3: 跨仓库搜索
```bash
# 在多个仓库中查找
./scripts/code_search.sh '(repo:"backend" or repo:"service") sym:Database'

# 排除测试文件的搜索
./scripts/code_search.sh 'content:"function" -file:test lang:go'
```

### 场景 4: 调试和问题定位
```bash
# 搜索特定错误信息
./scripts/code_search.sh '"NullPointerException" lang:java'

# 查找 TODO 注释
./scripts/code_search.sh 'content:"TODO" lang:python'
```

### 场景 5: API 和接口搜索
```bash
# 搜索 gRPC 服务定义
./scripts/code_search.sh 'file:"*.proto" content:"service"'

# 搜索 REST API 端点
./scripts/code_search.sh 'lang:go content:"@GetMapping" or content:"@PostMapping"'
```

## 命令行选项

```bash
Usage: code_search.sh <query> [OPTIONS]

参数:
  query                 搜索查询语句 (支持 Zoekt 语法)

选项:
  -p, --page           页码 (默认: 1)
  -s, --page-size      每页结果数, 1-100 (默认: 20)
  -c, --context        匹配行周围的上下文行数 (默认: 2)
  -h, --help          显示帮助信息
```

## API 响应格式

搜索 API 返回以下 JSON 结构:

```json
{
  "files": [
    {
      "repo": "ee/backend",
      "fileName": "src/main/java/Service.java",
      "projectId": 12345,
      "lineMatches": [
        {
          "lineNumber": 42,
          "line": "    public void handleRequest() {"
        }
      ]
    }
  ],
  "statistics": {
    "languages": {...},
    "repositories": {...}
  },
  "total": 150,
  "hasNext": true,
  "hasPrevious": false
}
```

### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `files` | Array | 匹配的文件列表 |
| `files[].repo` | String | 仓库名称 |
| `files[].fileName` | String | 文件路径 |
| `files[].projectId` | Integer | 项目 ID (用于生成链接) |
| `files[].lineMatches` | Array | 匹配的代码行 |
| `statistics` | Object | 按语言和仓库的统计信息 |
| `total` | Integer | 总匹配数 |
| `hasNext` | Boolean | 是否有下一页 |
| `hasPrevious` | Boolean | 是否有上一页 |

## 最佳实践

### ✅ 推荐做法

1. **使用符号搜索查找函数和类**
   ```bash
   ./scripts/code_search.sh "sym:UserService lang:java"
   ```
   **Why**: Symbol search is specifically designed to find function names, class names, and method definitions. It filters out comments, strings, and other non-declaration occurrences, giving you exactly what you need without noise. This is much more precise than content search when you're looking for where something is defined rather than where it's mentioned.

2. **组合多个过滤器缩小搜索范围**
   ```bash
   ./scripts/code_search.sh "error lang:go -file:test"
   ```
   **Why**: Combining filters dramatically improves result quality by removing irrelevant matches. Language filters ensure you get code in the right ecosystem, file exclusions remove test noise, and repository filters help you focus on relevant codebases. Starting broad and getting thousands of results is wasteful; starting narrow saves time and cognitive load.

3. **使用正则表达式处理模式匹配**
   ```bash
   ./scripts/code_search.sh 'regex:/func\s+\w+\(.*\)\s+error/'
   ```
   **Why**: Regular expressions let you match structural patterns rather than exact strings. This is essential when you want to find "all functions that return errors" or "all class definitions following a pattern" - things that can't be captured with simple keyword search. Regex gives you the power to express complex search intent precisely.

4. **适当增加上下文行数**
   ```bash
   ./scripts/code_search.sh "sym:Init" -c 10
   ```
   **Why**: The default 2 lines of context often isn't enough to understand how code is used. More context lines let you see the surrounding logic, function parameters, error handling, and usage patterns without having to open each file separately. This is especially valuable when deciding which search result to investigate further. Balance this against readability - too much context makes results hard to scan.

5. **使用引号进行精确匹配**
   ```bash
   ./scripts/code_search.sh '"connection timeout"'
   ```
   **Why**: Without quotes, the search engine treats words separately and may return results where "connection" and "timeout" appear anywhere in the file. Quotes ensure you find the exact phrase, which is critical for finding specific error messages, log statements, or multi-word identifiers.

### ❌ 避免的做法

1. **❌ 搜索过于宽泛的关键词 (如 "get", "set")**
   - **Why it's bad**: Common words like "get" or "set" appear thousands of times across any codebase - in method names, variable names, comments, strings, and documentation. You'll get overwhelming results with very low signal-to-noise ratio. Always add filters like language, repository, or symbol search to make generic keywords useful.

2. **❌ 不使用语言过滤导致结果混乱**
   - **Why it's bad**: Different languages have different syntax, patterns, and conventions. Without language filtering, you'll see Java methods mixed with Go functions mixed with Python classes, making it hard to understand results and learn from them. Each language has its own idioms - filtering lets you focus on relevant examples.

3. **❌ 忘记排除测试文件导致噪音过多**
   - **Why it's bad**: Test files often contain mock implementations, example data, and edge cases that look like real implementations but aren't. Including them doubles or triples your result count with code you don't actually need. Use `-file:test` or `-file:_test` to see production code first, then search tests separately if needed.

4. **❌ 不使用引号导致精确匹配失败**
   - **Why it's bad**: When you search for `error handling` without quotes, you're asking for files containing both "error" AND "handling" anywhere in the file - not necessarily together as a phrase. This can return code that mentions "error" in one function and "handling" in another, which isn't what you want. Quotes enforce phrase matching.

## 与 CodeWiki 配合使用

**Why use both tools**: CodeSearch and CodeWiki serve complementary purposes. CodeSearch answers "where is this code?" while CodeWiki answers "how is this system designed?". Using them together gives you both the forest (architecture) and the trees (specific implementations).

CodeSearch excels at finding needle-in-a-haystack details across all repositories, but it can't tell you about system architecture, design decisions, or domain concepts. CodeWiki provides curated architectural documentation, domain models, and design patterns, but can't show you specific code implementations. Combining them creates a powerful workflow for understanding unfamiliar code.

### 推荐工作流程

1️⃣ **Start with CodeSearch to discover repositories**
```bash
./scripts/code_search.sh "CouponRepository"
```
**Why this first**: You often don't know which repositories are relevant. Code Search helps you discover where the functionality exists by searching across everything. The search results include `projectId` which you'll need for CodeWiki.

2️⃣ **Use CodeWiki to understand architecture** (see [code-analysis](../code-analysis/SKILL.md))
```bash
# Get repository overview and architecture
./scripts/codewiki.sh --project-id 24135

# Understand domain models and entities
./scripts/codewiki.sh --project-id 24135 --domain-models
```
**Why this second**: Once you know which repository to explore, CodeWiki gives you the big picture - how the system is structured, what the key components are, what design patterns are used. This contextual understanding helps you ask better search questions and interpret the code you find.

3️⃣ **Return to CodeSearch with better context**
```bash
# Now you understand the architecture, so search for specific implementations
./scripts/code_search.sh "sym:CouponRepository lang:java"
```
**Why this third**: Armed with architectural knowledge from CodeWiki, you can now search more precisely. You know the correct terminology, understand which components interact, and can focus on specific implementation details that matter for your task.

### 实际应用场景

**Scenario: Understanding a new microservice**
- Search `repo:payment-service` to see what's there
- Use CodeWiki to read architecture docs and domain models
- Search specific symbols you learned about from the docs

**Scenario: Debugging cross-service issues**
- Search error message across all repos to find where it originates
- Use CodeWiki on relevant repos to understand service boundaries
- Search for interface definitions and API contracts

**Scenario: Adding a feature similar to existing code**
- Search for similar features: `sym:CouponProcessor`
- Use CodeWiki to understand the design pattern being used
- Search for all related classes now that you understand the pattern

## 技术支持

如有疑问或需要技术支持,请联系 **@CodeWiz人工服务**

## 注意事项

- 🔒 代理会自动处理认证,无需配置 token
- 📅 搜索结果为 T+1 主分支代码,可能存在延迟
- 🔑 无权限仓库只能看到搜索结果,无法查看详情
- ⚡ 建议使用具体的搜索条件,避免返回过多结果
