# report-spec.md · MySQL 集群诊断报告生成通用规范

> 本文档是所有路径（A/B/B2/C1/C2/D/E/F/G）HTML 报告生成的通用准则。
> AI 在生成任何路径的主报告或复盘报告前，必须先读本文档。
> 路径专属字段细节见各 `docs/path-*.md` 的报告生成步骤。

---

## 一、核心准则（强制，所有路径适用）

### 总准则

1. **AI 生成报告**：最终 HTML 由 AI 直接 `write` 生成，不调用任何脚本或模板渲染。AI 有完整诊断上下文，质量优于脚本模板。
2. **脚本只做发布**：`publish_report.py` 只做 dms_upload + run_meta + notify 三步，不含任何分析或渲染逻辑。
3. **Skill 不膨胀**：规范细节在 `docs/`，SKILL.md 只引用不展开。

### AI 生成 HTML 的三要素

1. **上下文足够丰富**：AI 在诊断阶段已读取并分析所有 raw 数据，生成报告时直接利用这些上下文，无需再次读文件。
2. **规范提供结构约束**：本文档描述 8 章节结构、风格约定、通用设计原则——是方向约束，不是精确字段映射。
3. **AI 综合判断填充细节**：字段选取、措辞、数据呈现方式由 AI 根据实际诊断上下文决定。路径专属字段指引见各 `path-*.md`，供参考，不强制逐条遵守。

### AI 是最终裁决者

规范给结构基线，AI 决定细节。以下情况 AI 可主动调整，无需请示：
- 某章节数据完全缺失时，保留章节但改为「推断 + 跳转指引」，禁止空白章节
- 路径特性导致某章节内容与通用描述不符时，按实际情况填充
- 有更好的呈现方式时，可偏离规范建议，但不得删减章节数量

---

## 二、8 章节结构定义

> **风格一致性约束**：8 章节必须全部存在，不得缩减或合并。章节顺序固定。
> AI 是内容裁决者，但章节骨架不变。

---

### §1 · 告警概览（Alert Overview）

**目标**：让读者 5 秒内拿到最关键的数字和结论。

**典型内容方向**：
- Banner 顶部大数字 KPI（3~6 个），含变化量和 vs 基线对比
- 故障窗口（北京时间）、集群、子路径标签
- P0 Checkbox 清单（值班 DBA 逐条确认，见§三·通用设计原则）
- 右侧 meta 信息卡：集群 / 主库节点 / Skill / 故障等级

**降级原则**：
- 告警数值（CPU%/QPS）未采集时，KPI 格显示「告警触发」而非具体数值，不用「未采集」黄框
- 故障等级由 AI 综合现有证据判断（P0/P1/P2），不要求精确数值支撑
- **KPI 格必须展示「当前值 vs 监控阈值」对比**，格式：`当前值 N（⚠️ 超过 monitoring_rules.md 规则X 阈值 M）`；阈值未知时展示「当前值 N（阈值参考 monitoring_rules.md）」
- **§1 Banner 必须显著标注数据采集时间**：`数据采集时间：YYYY-MM-DD HH:MM:SS（北京时间）`，所有状态描述用过去时态

---

### §2 · 故障时间线（Timeline）

**目标**：展示故障从触发到恢复的完整过程，帮助 DBA 还原现场。

**典型内容方向**：
- 慢查询/指标分钟级图表（JavaScript Canvas 动态渲染）
  - 数据来源：`get_raw_slow_log.data.timeline` 或 xray_metrics 时序
  - X 轴：北京时间（UTC+8）；双 Y 轴：数量（蓝色柱）+ 时长/速率（橙色线）
- 事件链（每个关键节点一张卡片）
  - 节点类型：`trigger`（橙）/ `root`（红）/ `effect`（紫）/ `recover`（绿）
  - 每张卡片右上角加 `ds-tag` 标注数据来源文件名

**降级原则**：
- 无时序数据时，事件链节点改为「AI 根据告警时间 + 诊断上下文推断」，并标注「推断」
- 图表数据点 < 3 个时，降级为纯文字事件链，不强行渲染图表
- **图表数据点必须来自实际 raw JSON，禁止用 AI 推断值构造坐标轴数据点**

---

### §3 · 根因分析（Root Cause Analysis）

**目标**：帮助 DBA 理解「为什么发生」，区分已确认结论和推断。

**典型内容方向**：
- 一句话根因（红色高亮框）
- 三段式结构（⚠️ 强制，见§三·证据/推断/排除分层）：
  - **已确认证据**：有 raw JSON 字段直接映射的结论，必须引用字段名和值
  - **合理推断**：两个及以上字段交叉推导的结论，必须写出推导链，标注「⚠️ 推断」
  - **已排除假说**：列出排查过但排除的方向及排除依据
- 根因归纳表：按层次（业务层/数据层/索引层/参数层）分行，每行标注优先级颜色
- DBA 行动路径（蓝色区块）：4 步以内的具体操作指引，含 DMS 页面跳转路径

**降级原则**：
- 持锁者身份无直接采集数据时，必须标注「持锁者身份未采集到直接证据，以下为推断」
- 不得将推断写成结论，不得用「根因：xxx」句式描述未经验证的推断

---

### §4 · 慢查询 Top SQL 分布

**目标**：定位最消耗资源的 SQL，帮助 DBA 找到优化目标。

**典型内容方向**：
- 数据来源：`get_raw_slow_log.data.top_sql[]`
- 关键字段（字段名以实际 API 返回为准）：
  - 执行次数：`query_count`（**注意：不是 `count`**）
  - 时长：`avg_query_time` / `max_query_time`
  - 锁等待：`avg_lock_time` / `max_lock_time`
  - 扫描行：`avg_rows_examined` / `max_rows_examined`（若存在）
- 来源服务：从 `data.details[].sql_text` 正则提取
  - 正则：`r'XHS_SERVICE:([^;*/\s]+?)(?:;|CLIENT_IP)'`
  - 去重，过滤 `null`
- SQL 类型：从 `sql_template` 去掉注释头后提取第一个关键词（SELECT/UPDATE/INSERT/DELETE）
- lock%：`avg_lock_time / avg_query_time × 100`

**降级原则**：
- `sql_template` 在注释头处截断、无 SQL 语义时：展示服务名 + SQL 类型 + 执行次数 + 扫描行，去掉 sql_template 列
- `databases` 字段为空时：不展示 database 列
- lock% 全为 0 时：去掉「角色」列，不做持锁者/等锁受害判断

---

### §5 · 表统计信息 & 执行计划

**目标**：定位数据层问题（索引失效、统计信息失准、数据倾斜）。

**典型内容方向**：
- 表名来源：优先从 `explain_sql.json` 提取；无 EXPLAIN 时从 `get_raw_slow_log.data.details[].sql_text` 反引号内提取（正则：`` r'`(t_[^`]+)`' ``）
- 表统计：`table_rows` / `data_length(MB)` / `index_length(MB)` / `update_time`
- 索引区分度：`cardinality / table_rows`，< 5% 标红，< 1% 标「极低 ⚠️」
- EXPLAIN：`type` / `key` / `rows` / `filtered` / `Extra`，type=ALL 标红，Using filesort 标橙

**降级原则**：
- EXPLAIN / 表统计未采集时（B2 路径常见）：
  - 从 `details` 取 `rows_examined` 最高前 3 条，展示推断目标表
  - 明确标注：`⚪ EXPLAIN / 表统计未采集，以下为慢日志扫描行数推断值`
  - **禁止黄色「数据未采集」框**，改用灰色推断值注释
  - 补充：「建议通过 DMS → 执行计划页面对高频 SQL 执行 EXPLAIN」
- `sql_text` 因 myhub 截断无法提取表名时：明确说明「表名因 myhub 路由层截断无法提取」，不用「未识别」掩盖

---

### §6 · 影响范围（Impact Assessment）

**目标**：量化故障影响，帮助判断定级和通报范围。

**典型内容方向**：
- 受影响实例：`get_db_connectors.data[]` 全部节点，标注角色（master/slave）
- 受影响业务服务：从 `details[].sql_text` 提取 XHS_SERVICE，去重过滤 null
- 故障等级：AI 综合 row_lock_count / 慢查询量级 / 持续时间判断（P0/P1/P2）
- 用户可见影响：AI 根据业务服务列表 + 堆积程度综合描述
- 数据完整性：事务最终状态（提交/回滚）

**降级原则**：
- QPS 跌幅未采集时：去掉该行，不用「未采集」占位

---

### §7 · 改进建议（Recommendations）

**目标**：给 DBA 和研发可执行的行动项，优先级分明。

**典型内容方向**：
- 卡片网格布局（P0/P1/P2/专业四类）
- **P0（立即）**：直接消除根因，必须具体到表名/SQL/参数，说明「为什么是 P0」
- **P1（本周内）**：防止复发
- **P2（迭代内）**：架构优化
- 每张卡片：优先级标签 + 标题 + 具体描述 + 可执行的 SQL 或配置命令

**降级原则**：
- 无法确定具体表名/参数时，描述操作方向而非具体命令，但必须注明「需结合实际情况确认」

---

### §8 · 附录（Appendix）

**目标**：可信度声明 + 原始数据留存，供 DBA 复核。

**典型内容方向**：
- 数据采集状态表（五列：数据项 / 接口文件 / 状态 ✅/⚠️/⚪ / 覆盖节点 / 采集时间窗口）
  - **覆盖节点列**：列出本次诊断实际采集的节点（vm_name + IP:Port），未采集节点标 ⚠️
  - **采集时间窗口列**：展示实际传入的 start~end 时间参数及时区，供 DBA 验证时区是否正确
  - 覆盖率 < 100% 时，§1 KPI 格显示「⚠️ 采集覆盖率 N/M 节点，可能存在漏采」
  - 数据矛盾说明：若两个数据源同一字段值不一致，在此行标注并说明采用哪个、理由
- 核心 SQL 样本：`lock_time` 或 `rows_examined` 最高的原始 `sql_text`（`<pre>` 代码块）
- TEST MODE 标注（若适用）：`[TEST MODE · run_id: xxx]`

---

## 三、通用设计原则

### 3.1 证据 / 推断 / 排除 分层（§3 强制，其他章节推荐）

| 类型 | 判断标准 | 展示方式 |
|------|---------|---------|
| **已确认证据** | 有 raw JSON 字段直接映射，字段值非 None/空 | 直接陈述，引用「字段名=值」 |
| **合理推断** | 两个及以上字段交叉推导，无直接字段支撑 | 标注「⚠️ 推断」，写出推导链（A AND B → C）|
| **已排除** | 有反向证据或字段值为 0/None | 标注「✅ 已排除」，说明排除依据 |

> ⚠️ 禁止将推断写成结论。DBA 依据报告执行操作（KILL/改参数），错误的根因判断比数字错误更危险。

---

### 3.2 P0 Checkbox 清单（§1 Banner 底部，强制）

- 每份报告的 Banner 底部必须有 P0 Checkbox 清单（2~4 条）
- 使用原生 `<input type="checkbox" class="check-box">` + `accent-color:#cf222e`
- 内容：值班 DBA 最紧急的行动项，必须具体（含操作路径或命令）
- 不是「建议」的复制，是「现在立刻能做的最重要的 2~4 件事」

---

### 3.3 数据矛盾处理

- 两个数据源同一字段值不一致时（如 active_sessions.total_active ≠ system_lock.total_active）：
  - 在 §1 KPI 格或 §8 附录标注矛盾
  - 说明采用哪个值及理由（通常以采样时间更接近告警时刻的为准）
  - 不得静默取其中一个值、不做说明

---

### 3.4 降级展示原则

- **禁止黄色「未采集」框**：数据缺失时改为灰色推断值注释 + 跳转指引
- **禁止空白章节**：数据完全缺失的章节改为「未采集说明 + 建议补采方式」
- **禁止把「数据未采集」当成占位符到处粘贴**：每处降级内容必须有具体说明（缺的是什么、为什么缺、怎么补）

---

### 3.5 ds-tag 数据来源角标

- 时间线事件卡片、根因结论、KPI 数字，建议标注数据来源文件
- 格式：右上角小角标 `<span class="ds-tag">filename.json</span>`
- 让 DBA 能追溯每个结论的原始数据

---

## 四、风格规范

### 4.1 色彩体系（亮色主题，v7 DBA 版基准）

| 用途 | 色值 |
|------|------|
| 页面背景 | `#f9f9fb` |
| 卡片背景 | `#ffffff` |
| 卡片边框 | `#d0d7de` |
| P0 / 严重告警 | `#cf222e` |
| P1 / 警告 | `#9a6700` |
| P2 / 正常 / 恢复 | `#1a7f37` |
| 链接 / 行动路径 | `#0969da` |
| 次要文字 | `#57606a` |
| Banner top-bar（P0）| `linear-gradient(90deg, #cf222e, #9a0000, #5c0000)` |
| Banner top-bar（P1）| `linear-gradient(90deg, #9a6700, #7d4e00)` |

### 4.2 布局约定

- **全宽布局**：`body { padding: 48px; }`，不设 `max-width`
- **Section 标题**：左侧 3px 蓝色竖条（`border-left: 3px solid #0969da`），Grafana 风格
- **卡片投影**：`box-shadow: 0 1px 3px rgba(0,0,0,0.06)`
- **表格**：斑马纹（`nth-child(even) background: rgba(0,0,0,0.02)`）；数字列右对齐 + tabular-nums；表头 12px，非全大写
- **Banner 分区**：左侧内容区 + 右侧 meta 信息卡（`grid-template-columns: 1fr 280px`）
- **锚点 KPI**：Banner 底部横排，竖线分隔，数字 28px font-weight:800

### 4.3 组件约定

| 组件 | 规范 |
|------|------|
| Badge / 标签 | `display:inline-flex; padding:3px 10px; border-radius:6px; border:1px solid` |
| P0 Checkbox | `<input type="checkbox" accent-color:#cf222e>` |
| ds-tag | `font-size:10px; font-family:monospace; background:#f6f8fa; border:1px solid #d0d7de; float:right` |
| 根因红框 | `background:#fff0ee; border-left:3px solid #cf222e; border-radius:6px` |
| 行动路径蓝框 | `background:#f0f8ff; border-left:3px solid #0969da; border-radius:6px` |
| 推断标注 | `⚠️ 推断` badge，`background:#fff8c5; color:#7d4e00` |

### 4.4 Canvas 图表约定

- Canvas 只负责绘制几何图形（柱、线、点、网格线）
- X 轴标签 / Y 轴数字 / 图例：优先用 DOM 元素（`<div>` 绝对定位覆盖），避免 `ctx.font` 跨平台兼容问题
- 若用 `ctx.fillText`：字体必须用单一字体名（`'12px monospace'`），不写逗号分隔的回退栈

---

## 五、数据准备阶段规则

> 以下规则在**诊断阶段**执行（EXPLAIN 前、数据整合时），不是报告生成时执行。

### SQL 清洗规则

```python
import re
# 1. 去掉 TRACE / CLIENT 注释块
sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL).strip()
# 2. SELECT 字段列表替换为 *（避免 created_at/created_by 触发服务端关键词检测）
sql = re.sub(r'(?i)(SELECT)\s+.+?\s+(FROM\b)', r'SELECT * \2', sql, flags=re.DOTALL)
```

### 业务 SQL 过滤规则

以下 SQL 视为非业务，跳过不分析：
- 包含 `information_schema.TABLES`、`information_schema.STATISTICS`、`performance_schema.`
- 以 `-- 表使用数据`、`-- 索引使用数据` 开头（DMS 自身采集 SQL）
- 所涉及 database 全部为系统库（`information_schema` / `mysql` / `sys` / `performance_schema`）

---

## 六、风控红线（优先级高于所有其他章节）

> ⚠️ **强制约束**：本节内容优先级高于§一~§五的所有描述。出现冲突时，以本节为准。
> 完整风控规则集（含触发条件/违反后果/正确做法三段式）见 `docs/report-risk-rules.md`。

### 6.1 写操作命令句式禁止

P0 Checkbox 和 §7 P0/P1 建议中，禁止出现以命令句式描述的写操作：

| 禁止 | 允许 |
|------|------|
| `立即执行：PURGE BINARY LOGS TO ...` | `建议 DBA 设置 binlog_expire_logs_seconds 自动清理` |
| `立即执行：KILL thread_id=xxx` | `建议 DBA 评估是否 KILL 以下连接（确认业务影响后执行）` |
| `执行 STOP SLAVE / SET GTID_NEXT` | `如需操作，参考命令见§8附录，执行前确认 Last_Error 类型` |

**P0 Checkbox 只能是确认类**：`☐ 确认持锁者身份` / `☐ 确认影响范围` / `☐ 联系高级 DBA`

### 6.2 推断必须标注

§3 根因分析中，推断性结论必须标注 `⚠️ 推断：`，不得用「根因是：」确定性句式描述未经 raw 字段直接支撑的判断。

### 6.3 数据时效性声明

- §1 Banner 必须标注数据采集时间
- 所有状态描述用过去时态（「采集时刻有 N 条...」而非「当前有 N 条...」）
- §7 每条建议加：「⚠️ 执行前请重新确认当前集群状态」

### 6.4 分型不确定禁止给恢复命令（路径 C2）

`Last_SQL_Error` 为空或类型不明时，禁止给任何 SQL Thread 操作建议。输出：「复制中断类型无法确认，请 DBA 登录节点执行 `SHOW SLAVE STATUS\G` 后再判断」。

### 6.5 DTS 运维行为识别前置（路径 F）

发现 `Command=Binlog Dump` 时，先在报告 §3 输出疑似 DTS 声明，确认是计划内操作后才定性，未确认前不给处置建议。

---

*最后更新：2026-04-10 · 来源：DBA视角/内核专家/风控视角/开发者视角四轮评审综合*
