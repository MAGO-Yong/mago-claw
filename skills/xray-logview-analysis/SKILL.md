---
name: xray-logview-analysis
description: '根据 CAT MessageId 分析 XRay Logview 调用链。用于以下场景：(1) 用户提供 MessageId，需要分析请求调用链、耗时分布、性能瓶颈；(2) 定位某次请求的异常根因；(3) 查看某次调用的下游依赖健康状态（SLA等级/强弱依赖）；(4) 排查慢请求或失败请求。触发词包括：在上下文中包含messageId，分析 logview、分析 messageId、查看调用链、分析这个请求、根因分析、性能瓶颈分析等。'
version: 1.0.0
metadata:
  category: trace
  subcategory: logview
  platform: xray
  trigger: messageId
  input: [messageId, base_url, token, source]
  output: [call_chain, latency_distribution, exception_nodes, dependency_health]
  impl: python-script
---

# XRay Logview 分析

## 工作流程

1. 从用户处获取 `messageId` 和 `base_url`（xray-api 地址）
2. 调用 `scripts/analyze_logview.py` 获取并分析数据
3. 输出结构化分析报告，包含：基本信息、异常节点、失败 Transaction、耗时 TOP10、调用链树、性能瓶颈、下游依赖

## 获取输入

向用户询问（如未提供）：
- **messageId**: CAT 消息 ID，格式 `{domain}-{ip}-{hour}-{index}`（例：`order-service-c0a80101-456789-1`）
- **base_url**: xray 平台地址（例：`https://xray.devops.xiaohongshu.com`），未提供时使用默认值

## 鉴权说明

所有接口请求统一使用 `xray_ticket: pass` 通过鉴权，无需用户提供 token 或 source。

## 执行分析

```bash
# 通过 API 获取并分析（使用 xray_ticket: pass 鉴权）
python3 scripts/analyze_logview.py <messageId> \
  --base-url <base_url>

# 直接分析用户粘贴的 JSON（保存为临时文件后执行）
python3 scripts/analyze_logview.py --json /tmp/logview.json
```

脚本路径相对于 skill 目录：`scripts/analyze_logview.py`

## 报告解读指引

拿到输出后，重点关注并给出结论：

| 部分 | 关注点 |
|------|--------|
| 数据状态 code | 1003=数据缺失，1004=已归档，需告知用户 |
| 异常节点 | 列出所有 Error/RuntimeException/Exception，说明所在调用位置 |
| 失败 Transaction | status 非 0/success 的节点，通常是根因所在 |
| 耗时 TOP10 | 找出占总耗时比例最高的节点 |
| 性能瓶颈 | 单节点耗时 > 总耗时 30% 即为瓶颈，重点说明 |
| 下游依赖 | 失败的强依赖（strongDependence=true）是服务不可用的高风险点 |

## 分析结论格式

报告输出后，用中文总结：

```
## 根因分析结论

**请求概况**: [服务名] 在 [时间] 发起请求，总耗时 [X]ms，状态 [成功/失败]

**异常/失败**: [有/无] — [具体描述]

**性能瓶颈**: [具体节点] 耗时 [X]ms，占 [Y]%

**根因判断**: [一句话结论]

**建议**: [针对性建议]
```

## 参考文档

- API 接口和数据结构详情：[references/logview-api.md](references/logview-api.md)
