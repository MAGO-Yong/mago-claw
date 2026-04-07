---
name: rec-new-note-diagnosis
description: 推荐系统外流新笔记下跌自动诊断。当用户说"新笔记诊断"、"新笔记下跌了"、"外流新笔记量不对"、"帮我看看新笔记链路"时触发。自动执行Step 1-6完整排查流程，无需手动干预。
---

# rec-new-note-diagnosis

推荐系统外流新笔记下跌自动诊断技能。

## 触发条件

- "新笔记诊断"
- "新笔记下跌了"
- "外流新笔记量不对"
- "帮我看看新笔记链路"
- "新笔记数据异常"
- "新笔记占比下降"

## 快速使用

```bash
# 完整自动诊断（Step 1-6）
python3 skills/rec-new-note-diagnosis/scripts/diagnose.py

# 从指定步骤开始
python3 skills/rec-new-note-diagnosis/scripts/diagnose.py --step 2
```

## 诊断流程

```
Step 1: 查询新笔记指标 → 自动判断是否异常
    ↓ （异常时自动继续）
Step 2: 定位下跌阶段
    ↓
Step 3: 召回渠道排查
    ↓
Step 4: 召回根因分析
    ↓
Step 5: 索引排查
    ↓
Step 6: 内容供给排查
    ↓
输出诊断总结
```

## 依赖

- `xray_metrics_query` - 查询指标
- `xray_changevent_query` - 查询变更
- `index-switch-check` - 检查索引
- `data-fe-common-sso` - 登录态

## 参考文档

| 文件 | 说明 |
|------|------|
| `references/sop.md` | SOP方法论与关键参数 |
| `references/promql-collection.json` | PromQL查询语句 |
| `references/decision-tree.json` | 诊断决策树 |
| `references/config-watchlist.json` | 高风险配置清单 |
| `references/appendix.md` | 历史故障案例 |
