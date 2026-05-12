# 外流新笔记下跌故障排查 SOP — 关键参数速查

> 原文地址：https://docs.xiaohongshu.com/doc/431589c956b59ffde7ddff305505e8c2
> 本文件记录已人工校验的关键参数，以防 web_fetch 强制小写导致 PromQL 失真。

---

## PromQL 关键大小写（人工校验版）

> ⚠️ web_fetch 读取 Redoc 文档时会强制小写，以下内容以人工校验版本为准，严格原样使用。

| 步骤 | 标签/字段 | 正确写法 |
|------|---------|---------|
| Step 2.1 | subPhase 值 | `subPhase="after"`（P 大写） |
| Step 3.1 | name 标签（DSSM） | `DSSM_MODEL_BASE` |
| Step 3.1 | name 标签（MLLM） | `MLLM_CLUSTER_MLP_1W` |
| Step 3.1 | name 标签（ES） | `ES` |
| Step 3.1 | name 标签（关注） | `FOLLOW` |
| Step 4.1 | reason_type | `reason_type=~"DSSM_LOW_ENGAGE"` |
| Step 4.2 | type | `type=~"MLLM_CLUSTER_MLP_1W"` |
| Step 4.2 | datasource | `vms-recommend` |
| Step 5.1 | reason_type | `reason_type=~"DSSM_MODEL_BASE"` |
| Step 5.1 | datasource | `vms-recommend`（非 vms-search） |
| Step 5.2 | datasource | `vms-search` |
| Step 6.2 | 指标名 | `postnotescanner_SingleShardTableScanner_scanSingleShard_needRetryTaskNumber`（驼峰） |
| Step 6.2 | code | `code="NOTE_SPAM"` / `code="COMPLETED"` |
| Step 6.2 | biz | 全大写 |
| Step 6.3 | endpoint | `endpoint=~"newNote\|editNote"`（驼峰） |

---

## 待补充内容

请将 SOP 原文中以下内容补充到此处：

1. **各步骤完整 PromQL**：包含完整的指标名、label 过滤条件
2. **召回通道完整列表**：Step 3.1 中 `name` 标签的全量枚举值
3. **异常判定阈值**：各指标三时点对比的告警阈值（如下跌 X% 视为异常）
4. **Grafana 看板链接**：各步骤对应的面板地址

---

## 填写方法

在 Redoc 平台将文档授权给 codewiz 小助手后，可让 AI 自动提取并填写。
