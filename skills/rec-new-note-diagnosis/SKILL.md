---
name: rec-new-note-diagnosis
description: 推荐系统外流新笔记下跌自动诊断（渐进式 v4.0）。支持三条路径：Fast（无 GATE 快速结论）/ Standard（2个GATE，Step 0-4）/ Deep（4个GATE，Step 0-6 + 结论自检）。支持断点续诊（--resume）和全自动无人值守（--auto）。当用户说"新笔记诊断"、"新笔记下跌了"、"外流新笔记量不对"、"帮我看看新笔记链路"时触发。
---

# rec-new-note-diagnosis v4.0

推荐系统外流新笔记下跌自动诊断技能（渐进式 + 无人值守）。

## 触发条件

- "新笔记诊断"
- "新笔记下跌了"
- "外流新笔记量不对"
- "帮我看看新笔记链路"
- "新笔记数据异常"
- "新笔记占比下降"

## 三条诊断路径

| 路径 | 触发条件 | GATE数 | 覆盖步骤 |
|------|---------|-------|---------|
| 🟢 **Fast Path** | 跌幅<5%，watchlist 0命中 | 无 | Step 0 + Step 1-2（T0定位+变更查询） |
| 🟡 **Standard Path** | 跌幅5-15%，命中Medium/High | A + B | Step 0-4 |
| 🔴 **Deep Path** | 跌幅>15% / Critical命中 / 矛盾判断 | A+B+C+D | Step 0-6 + 自检 |

路径由 Step 0 指标数据和 watchlist 命中情况**自动决定**，也可手动强制：

```bash
python3 scripts/diagnose.py --fast    # 强制 Fast Path
python3 scripts/diagnose.py --deep    # 强制 Deep Path
python3 scripts/diagnose.py --auto    # 全自动，跳过所有 GATE
```

## 使用方法

```bash
# 标准用法（自动分诊）
python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py

# 全自动无人值守
python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py --auto

# 查看历史诊断会话
python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py --list-sessions

# 从上次断点恢复
python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py --resume sessions/2026-04-02_10-36.json

# 独立分诊（已有跌幅数据时快速判断路径）
python3 skills/rec-homefeed-newnote-diagnosis/scripts/triage.py \
  --drop-1h -18.5 --drop-24h 1.5 --watchlist-hits 2 --hit-levels high,medium

# 对已完成的诊断做结论自检
python3 skills/rec-homefeed-newnote-diagnosis/scripts/conclusion_review.py \
  --session sessions/2026-04-02_10-36.json
```

## GATE 指令说明

在每个 GATE 暂停时，可输入以下指令：

| 指令 | 说明 |
|------|------|
| `/continue` | 继续下一个诊断阶段 |
| `/skip-deep` | 跳过深度排查，输出当前结论（仅 GATE A 可用）|
| `/go-deep` | 升级为 Deep Path（若当前为 Standard Path）|
| `/save` | 保存当前状态并退出，稍后用 `--resume` 恢复 |

GATE 等待超时（默认300s）后自动继续，等价于 `/continue`。

## 目录结构

```
rec-homefeed-newnote-diagnosis/
├── SKILL.md                        # 本文件
├── agents/
│   ├── triage-prompt.md            # 分诊 Agent 提示词（路径决策规则）
│   ├── diagnosis-prompt.md         # 深度诊断 Agent 提示词（Evidence 铁律）
│   └── conclusion-reviewer.md      # 结论审查 Agent 提示词（上下文隔离）
├── rules/
│   ├── rec-context.md              # 推荐系统拓扑（始终加载）
│   └── sre-redlines.md             # 止损操作红线（始终加载）
├── knowledge/
│   ├── index.md                    # 知识索引（触发条件 → 对应文件）
│   ├── index-switch.md             # 索引切换知识（Step 5 前加载）
│   ├── data-flow.md                # 数据流知识（Step 6 前加载）
│   └── gradual-failure-cases.md    # 渐进式故障案例（视频/混排变更时加载）
├── sessions/                       # 诊断会话快照（断点续诊）
├── scripts/
│   ├── diagnose.py                 # 主入口（v4.0 渐进式路由）
│   ├── triage.py                   # 独立分诊脚本
│   ├── session_manager.py          # 会话快照管理
│   └── conclusion_review.py        # 结论自检脚本
└── references/                     # 核心参考文档（不变）
    ├── sop.md                      # SOP 方法论（v3.9）
    ├── config-watchlist.json       # 高风险配置清单（v4.0）
    ├── promql-collection.json      # PromQL 查询语句
    ├── decision-tree.json          # 诊断决策树
    └── appendix.md                 # 历史故障案例库
```

## 依赖 Skills

### 必需依赖

| Skill | 说明 | 安装命令 |
|-------|------|---------|
| `xray_metrics_query` | 查询 XRay 监控指标（Prometheus/VictoriaMetrics） | `openclaw skill install xray_metrics_query` |
| `xray_changevent_query` | 查询 XRay 变更事件（Apollo 配置 + 实验变更） | `openclaw skill install xray_changevent_query` |
| `index-switch-check` | 检查索引切换状态（RIS/Omega） | `openclaw skill install index-switch-check` |

> **SSO 登录态**：直接读取 `/home/node/.token/sso_token.json`（由 OpenClaw 自动维护），无需额外安装 skill。

### 可选依赖

| Skill | 说明 | 安装命令 |
|-------|------|---------|
| `hi-redoc-curd` | 上传诊断报告到 Redoc | `openclaw skill install hi-redoc-curd` |

### 快速安装

**一键安装所有依赖：**
```bash
openclaw skill install xray_metrics_query xray_changevent_query index-switch-check
```

**检查依赖是否完整：**
```bash
python3 skills/rec-homefeed-newnote-diagnosis/scripts/check_dependencies.py
```

运行诊断脚本时会自动检查依赖，缺失时会提示安装命令。

## 核心设计原则（v4.0）

1. **渐进式复杂度**：简单问题不承担复杂流程的成本
2. **Evidence 铁律**：每个判断必须有数据出处（数值+时间点）
3. **GATE 机制**：每阶段完成后暂停确认，避免方向跑偏
4. **知识按需加载**：根据分诊结果和故障类型，只加载对应 knowledge/ 文件
5. **断点续诊**：会话状态持久化到 sessions/，支持中断后恢复
6. **结论自检**：Deep Path 完成后，用隔离上下文验证结论自洽性
