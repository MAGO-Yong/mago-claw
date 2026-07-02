# ROUTING.md - 多 Agent 路由规则

> 主 Agent 读此文件，判断是否派发给子 Agent

## 架构

```
用户消息
    ↓
主 Agent（意图识别 + 路由）
    ├── 🏢 Work Agent    → agents/work/SOUL.md
    ├── 🏠 Life Agent    → agents/life/SOUL.md
    └── 💰 Invest Agent  → agents/invest/SOUL.md
```

## 路由规则

### 🏢 Work Agent
**触发关键词/场景**：
- XPILOT、AIOps、告警、诊断、XRay、可观测性
- 技术风险 PM、汇报材料、架构图、方案设计
- 小红书内部项目、排障、稳定性
- 代码搜索、日志查询、Trace 分析

**派发方式**：`sessions_spawn(mode=run, task=...)`，在 task 中附上用户原始问题 + 相关 memory

---

### 🏠 Life Agent
**触发关键词/场景**：
- 万豪、积分、打卡、品牌、酒店
- 出行、行程、预订、清明、五一
- 日程、提醒、生活安排

**派发方式**：同上，附上 marriott checklist 内容

---

### 💰 Invest Agent
**触发关键词/场景**：
- 英伟达、AMD、台积电、SK 海力士、三星、HBM
- CRCL、Circle、USDC、加密
- 股价、涨跌、市值、投资、持仓

**派发方式**：同上，附上 CRCL 分析 + 当前基线数据

---

## 不派发的情况（主 Agent 自己处理）
- 闲聊、打招呼
- 关于 Agent 架构本身的问题
- 跨领域综合问题（主 Agent 综合多个子 Agent 结果）
- 需要实时工具调用（exec/browser）的快速任务

## 子 Agent 调用模板

```javascript
sessions_spawn({
  mode: "run",
  task: `
你是 [Work/Life/Invest] Agent。
读取以下 SOUL 文件：agents/[work|life|invest]/SOUL.md
读取相关记忆文件。

用户问题：${userMessage}

请直接处理并给出结果，无需询问主 Agent。
  `,
  streamTo: "parent"  // 结果流式返回给主 Agent
})
```

---

*建立时间：2026-03-28*
