---
name: rca-incident-query
description: >
  Use when the user wants to query, search, or look up incidents/故障 from the RCA platform
  (https://rca.devops.xiaohongshu.com). Handles flexible field-based queries by extracting
  keywords from natural language, calling the RCA API via script, formatting results, and
  providing stability improvement advice on follow-up questions.
  Trigger keywords: 故障查询, 查故障, RCA, 故障列表, 稳定性建议, incident query, search incidents.
---

# RCA 故障查询 Skill

## 概述

从用户自然语言中提取查询条件 → 调用脚本查询 RCA API → 格式化展示结果 → 追问时给出稳定性建议。

## 工作流程

### 第一步：从自然语言提取查询参数

分析用户输入，提取以下字段（未提及的字段不传，脚本会使用默认值）：

| 字段 | 类型 | 示例值 | 说明 |
|------|------|--------|------|
| title | string | "支付" | 标题关键词 |
| level | string[] | ["P0","P1"] | 故障级别：P0/P1/P2/P3/P4/Notice |
| scene | string[] | ["电商购物车结算"] | 故障场景 |
| business_line | string[] | ["电商","推荐"] | 业务线 |
| case_type | string[] | ["服务端"] | 类型：服务端/前端/数据问题/非技术 |
| rca_review_status | string[] | ["未复盘"] | RCA状态：已复盘/未复盘 |
| case_status | string | "fixed" | 故障状态：fixed/unfix |
| start | string | "2026-03-11 00:00:00" | 创建时间起始，格式：`YYYY-MM-DD HH:MM:SS` |
| end | string | "2026-03-13 23:59:59" | 创建时间结束，格式：`YYYY-MM-DD HH:MM:SS` |
| pageNo | int | 2 | 页码，默认1 |
| pageSize | int | 10 | 每页数量，默认20 |

**时间格式规范：**
- 标准格式：`YYYY-MM-DD HH:MM:SS`，例如 `2026-03-11 00:00:00`
- 若用户输入格式不标准，**必须转换**后再传入脚本：
  - `2026/03/11` → `2026-03-11 00:00:00`（start）/ `2026-03-11 23:59:59`（end）
  - `03-11` / `3月11日` → 补全年份为当前年，start 补 `00:00:00`，end 补 `23:59:59`
  - `2026-03-11` → start 补 `00:00:00`，end 补 `23:59:59`
  - `最近3天` / `本周` 等自然语言 → 计算对应的具体日期时间范围
  - 只说"今天" → start = 今日 `00:00:00`，end = 今日 `23:59:59`

**提取示例：**
- "查电商业务线最近的 P0 故障" → `{"business_line": ["电商"], "level": ["P0"]}`
- "搜索标题含支付、未复盘的故障，第2页" → `{"title": "支付", "rca_review_status": ["未复盘"], "pageNo": 2}`
- "查一下服务端故障" → `{"case_type": ["服务端"]}`
- "查3月11日到3月13日的电商P4故障" → `{"business_line": ["电商"], "level": ["P4"], "start": "2026-03-11 00:00:00", "end": "2026-03-13 23:59:59"}`
- "查本周故障" → 计算本周一 `00:00:00` 到今天 `23:59:59`

### 第二步：调用查询脚本

将提取到的参数构建为 JSON，执行脚本：

```bash
python .kiro/skills/rca-incident-query/scripts/query.py '<JSON参数>'
```

**示例：**
```bash
python .kiro/skills/rca-incident-query/scripts/query.py '{"business_line": ["电商"], "level": ["P0"], "pageSize": 10}'
```

脚本会输出 JSON 结果到 stdout，格式为：
```json
{
  "success": true,
  "total": 100,
  "pageNo": 1,
  "pageSize": 10,
  "list": [ ... ]
}
```

若 `success` 为 `false`，输出中会有 `error` 字段说明原因，直接将错误信息告知用户。

### 第三步：格式化展示结果

将脚本返回的 `list` 格式化为可读文本：

```
查询结果：共 {total} 条，第 {pageNo} 页，每页 {pageSize} 条

1. [{level}] {title}
---
ID: {id}
标题: {title}
级别: {level}
场景: {scene}
状态: {case_status}        （fixed=已修复 / unfix=未修复）
类型: {case_type}
业务线: {business_line}
创建人: {creator}
创建时间: {create_time}
结束时间: {finish_time}
是否RCA: {is_rca}
RCA复盘状态: {rca_review_status}
描述: {desc}               ← 仅当 desc 非空时展示
---
```

**空值规则：** 字段为 `null`、`""` 或 `"null"` 时显示为 **"暂无"**。

### 第四步：追问时提供稳定性建议

当用户追问稳定性相关问题时（关键词：稳定性、建议、改进、优化、治理、加固、预防、措施），基于上一次查询返回的故障列表进行分析。

**分析维度：**
1. 故障级别分布（level）
2. 高频故障场景（scene）
3. 高频业务线（business_line）
4. 故障类型分布（case_type）

**输出格式：**
```
## 稳定性改进建议

基于 {N} 条故障数据分析：

### 故障级别分布
- P0: X 次  ...

### 高频故障场景
- {top_scene}: X 次  ...

### 高频业务线
- {top_biz}: X 次  ...

### 故障类型分布
- 服务端: X 次  ...

### 改进建议
1. 【高频场景】{top_scene} 场景故障频发（X次），建议加强监控告警和容量规划。
2. 【高频业务线】{top_biz} 业务线故障最多（X次），建议开展专项稳定性治理。
3. 【故障类型】{top_type} 类故障占比最高，建议制定专项应急预案。
```

若上下文中没有故障数据，提示用户先执行查询。

## 注意事项

- 脚本依赖 Python 3 标准库，无需额外安装依赖
- 若用户未指定 pageSize，默认使用 20 条，避免输出过长
- 若结果超过 5 条，可提示用户"如需查看更多，可指定页码或缩小查询范围"
