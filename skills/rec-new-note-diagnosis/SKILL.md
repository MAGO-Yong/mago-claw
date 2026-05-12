---
name: rec-new-note-diagnosis
description: "推荐系统外流新笔记下跌诊断。当用户说"新笔记诊断"、"新笔记下跌了"、"外流新笔记量不对"、"帮我看看新笔记链路"、"新笔记数据异常"、"新笔记占比下降"时，主动按 SOP 步骤逐一排查推荐外流新笔记链路，不用人工确认，一查到底，给出每步的诊断结论，最终汇总异常点和建议。SOP 文档：https://docs.xiaohongshu.com/doc/431589c956b59ffde7ddff305505e8c2"
---

# 推荐外流新笔记下跌诊断

## 概述

本 Skill 用于诊断推荐系统**外流新笔记**链路的异常，使用 `xray-metrics-query` 按照标准 SOP 逐步排查，无需用户手动贴文档链接。

SOP 原文：[外流新笔记下跌故障排查 SOP](https://docs.xiaohongshu.com/doc/431589c956b59ffde7ddff305505e8c2)

---

## 触发场景

用户说以下任意关键词时启动本 Skill：

- 新笔记诊断 / 新笔记下跌 / 新笔记数量异常 / 新笔记链路
- 外流新笔记 / 推荐新笔记 / 新内容占比
- "帮我看看新笔记" / "新笔记有没有问题"

---

## 核心约定

### 执行原则

**不用人工确认，一查到底** — 检测到异常后自动按决策树完成全链路排查，无需中途询问用户。

### 数据查询方法

- **核心工具**：`xray-metrics-query`
- **核心方法**：三时点对比（当前值 / -1d / -7d）
- **分桶策略**：
  - 6 小时窗口：`step=300s`（5 分钟）
  - 1 天窗口：`step=600s`（10 分钟）
- **聚合分析**：计算 avg / max / min / std / p95，综合判断，避免单点波动干扰

### PromQL 大小写警告（极其重要）

> ⚠️ **永远不要依赖 `web_fetch` 读取 Redoc 文档的结果来执行 PromQL**。
> `web_fetch` 会将文档内容强制小写，导致 PromQL 标签值失真。
> 以下大小写已经过人工校验，以本文件为准，严格按原样使用。

| 步骤 | 关键大小写规范 |
|------|--------------|
| Step 2.1 | `subPhase="after"`（P 大写） |
| Step 3.1 | `name` 标签值全大写，如 `DSSM_MODEL_BASE`、`MLLM_CLUSTER_MLP_1W`、`ES`、`FOLLOW` 等 |
| Step 4.1 | `reason_type=~"DSSM_LOW_ENGAGE"`（全大写） |
| Step 4.2 | `type=~"MLLM_CLUSTER_MLP_1W"`（全大写），datasource=`vms-recommend` |
| Step 5.1 | `reason_type=~"DSSM_MODEL_BASE"`（全大写），datasource=`vms-recommend`（非 vms-search） |
| Step 5.2 | datasource=`vms-search`（omega 指标） |
| Step 6.2 | 指标名驼峰 `postnotescanner_SingleShardTableScanner_scanSingleShard_needRetryTaskNumber`，`code="NOTE_SPAM"`/`"COMPLETED"`，`biz` 值全大写 |
| Step 6.3 | `endpoint=~"newNote\|editNote"`（驼峰） |

---

## 排查路径总览

```
确认异常 → 定位阶段 → 召回排查 → 根因分析 → 索引排查 → 内容供给
```

---

## 诊断流程（严格按 SOP 执行）

> 全程严格使用 SOP 文档原样 PromQL，不修改字母大小写。
> 每步给出明确结论：✅ 正常 / ❌ 异常 / ⚠️ 需关注。

### Step 1：确认异常 — 外流新笔记量/占比是否真实下跌

使用 `xray-metrics-query` 查询外流新笔记整体指标，做三时点对比（当前 / -1d / -7d）。

确认以下问题：
- 新笔记**绝对量**还是**占比**下跌，还是两者都有？
- 影响**全场景**还是**特定场景**？

若指标确认下跌，进入 Step 2。

---

### Step 2：定位阶段 — 定位下跌发生在链路哪个阶段

#### Step 2.1：分阶段漏斗对比

查询各阶段新笔记量，使用：
- `subPhase="after"`（注意：P 大写）

对召回后、粗排后、精排后、重排后各阶段分别做三时点对比，找到量开始明显下跌的阶段。

**决策**：
- 召回阶段已下跌 → 进入 Step 3（召回排查）
- 召回正常，粗排/精排后下跌 → 进入 Step 4（根因分析）
- 精排正常，重排后下跌 → 重排策略或业务干预问题，联系推荐策略同学

---

### Step 3：召回排查 — 各路召回通道逐一检查

#### Step 3.1：各召回通道量对比

查询各路召回通道新笔记量，`name` 标签值使用**全大写**，如：
- `DSSM_MODEL_BASE`
- `MLLM_CLUSTER_MLP_1W`
- `ES`
- `FOLLOW`
- （其他通道参考 SOP 原文完整列表）

三时点对比，找出掉量或掉零的通道。

**决策**：
- 某通道掉零或大幅下降 → 该通道异常，进入 Step 4/5 进一步定位根因
- 所有通道均匀下降 → 可能是供给侧问题，进入 Step 6（内容供给）

---

### Step 4：根因分析 — 召回下跌的具体原因

#### Step 4.1：DSSM 低交互过滤量排查

查询 DSSM 低交互被过滤的笔记量：
- `reason_type=~"DSSM_LOW_ENGAGE"`（全大写）

若该项数值大幅上升，说明新笔记因低交互被过滤增多，可能是模型分数问题或阈值调整。

#### Step 4.2：MLLM 模型召回量排查

查询 MLLM 模型召回新笔记量：
- `type=~"MLLM_CLUSTER_MLP_1W"`（全大写）
- datasource=`vms-recommend`

三时点对比，确认该路召回是否正常。

**决策**：
- DSSM_LOW_ENGAGE 过滤量上升 → 联系推荐策略（quota/策略配置问题）
- MLLM 召回量下降 → 进入 Step 5（索引排查）

---

### Step 5：索引排查 — 召回依赖的索引是否异常

#### Step 5.1：DSSM 索引新笔记量

查询 DSSM 索引中新笔记存量：
- `reason_type=~"DSSM_MODEL_BASE"`（全大写）
- datasource=`vms-recommend`（注意：不是 vms-search）

#### Step 5.2：Omega 索引新笔记量

查询 omega 索引新笔记存量：
- datasource=`vms-search`

#### Step 5.3：索引表切换判断

> ⚠️ **当前能力缺口**："索引表是否切换"的判断需 darwin 平台提供 skills 支持，**当前正在开发中**。
> 遇到此类情况请联系**索引侧同学**人工确认。

**决策**：
- 索引量正常，但召回量下降 → 索引切换或配置问题，联系索引侧同学
- 索引量本身下降 → 进入 Step 6（内容供给）

---

### Step 6：内容供给 — 新笔记生产侧是否出现问题

#### Step 6.1：新笔记整体入库量

查询新笔记入库总量，三时点对比，确认是否供给侧整体下降。

#### Step 6.2：审核积压排查

查询审核积压指标：
- 指标名（驼峰）：`postnotescanner_SingleShardTableScanner_scanSingleShard_needRetryTaskNumber`
- `code="NOTE_SPAM"` / `code="COMPLETED"`
- `biz` 值使用**全大写**

若积压量显著上升，说明审核延迟导致新笔记无法及时入库。

#### Step 6.3：发布 QPS 排查

查询新笔记发布接口 QPS：
- `endpoint=~"newNote|editNote"`（注意驼峰，不是全小写）

若 QPS 大幅下降，说明用户发布行为减少（供给侧问题）。

**决策**：
- 审核积压上升 → 联系社区安审
- 发布 QPS 下降 → 联系社区发布链路
- 转码延迟 → 联系社区安审

---

## 诊断报告模板

```
## 外流新笔记下跌诊断报告（{date}）

### 现象确认
- 时间范围：xxx
- 下跌类型：绝对量 / 占比 / 两者
- 影响场景：全场景 / 特定场景（xxx）

### 链路各阶段排查
| 阶段 | 结论 | 数据详情（当前 / -1d / -7d） |
|------|------|--------------------------|
| 召回后 | ✅/❌/⚠️ | xxx / xxx / xxx |
| 粗排后 | ✅/❌/⚠️ | xxx / xxx / xxx |
| 精排后 | ✅/❌/⚠️ | xxx / xxx / xxx |
| 重排后 | ✅/❌/⚠️ | xxx / xxx / xxx |

### 召回通道排查（如适用）
| 通道 | 结论 | 数据详情 |
|------|------|---------|
| DSSM_MODEL_BASE | ✅/❌/⚠️ | xxx |
| MLLM_CLUSTER_MLP_1W | ✅/❌/⚠️ | xxx |
| ES | ✅/❌/⚠️ | xxx |
| FOLLOW | ✅/❌/⚠️ | xxx |

### 根因分析（如适用）
| 检查项 | 结论 | 数据详情 |
|--------|------|---------|
| DSSM_LOW_ENGAGE 过滤量 | ✅/❌/⚠️ | xxx |
| MLLM 召回量 | ✅/❌/⚠️ | xxx |

### 索引排查（如适用）
| 检查项 | 结论 | 数据详情 |
|--------|------|---------|
| DSSM 索引新笔记量 | ✅/❌/⚠️ | xxx |
| Omega 索引新笔记量 | ✅/❌/⚠️ | xxx |
| 索引表切换 | ⚠️ 需人工确认 | 联系索引侧同学 |

### 内容供给排查（如适用）
| 检查项 | 结论 | 数据详情 |
|--------|------|---------|
| 新笔记入库量 | ✅/❌/⚠️ | xxx |
| 审核积压量 | ✅/❌/⚠️ | xxx |
| 发布 QPS | ✅/❌/⚠️ | xxx |

### 根因判断
- 疑似根因：xxx
- 置信度：高 / 中 / 低

### 建议动作 & 联系人
- xxx → 联系 xxx
```

---

## 联系人

| 问题类型 | 联系人 |
|---------|-------|
| 索引切换 / 消息流问题 | 索引侧同学（darwin skills 开发中） |
| 召回 quota / 策略配置问题 | 推荐策略 |
| 审核积压 / 转码延迟 | 社区安审 |
| 发布 QPS 异常 | 社区发布链路 |

---

## 参考资料

- SOP 原文：[外流新笔记下跌故障排查 SOP](https://docs.xiaohongshu.com/doc/431589c956b59ffde7ddff305505e8c2)
- 关键工具：`xray-metrics-query`
- 待建设：darwin 索引切换判断 skill（Step 5.3）
