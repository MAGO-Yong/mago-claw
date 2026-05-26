---
name: alipayservice-success-rate-diagnosis
version: 0.1.0
description: "alipayservice 电商域 C 端成功率下跌告警自动诊断 Skill。适用于告警规则 151469（【全域监控】电商域- C端-关键监控组【成功率】）。自动执行：异常报错聚类分析。依赖缺口：RPC 拓扑指标（中间件版本限制）、变更查询（无 xray-cli 原子能力）。"
---

# alipayservice 成功率下跌告警诊断

## 适用场景

- **告警名称**：【全域监控】电商域- C端-关键监控组【成功率】
- **规则 ID**：151469
- **服务**：alipayservice
- **触发条件**：最近 6 分钟，后 3 分钟均值相对前 3 分钟下跌 ≥ 1%
- **典型持续时长**：10-20 分钟

## 输入参数

| 参数 | 来源 | 说明 |
|------|------|------|
| `event_id` | 告警事件 ID | 必填，如 197871451 |
| `app` | 固定值 | `alipayservice` |
| `trigger_time` | 告警事件 basic.trigger_time | 用于计算时间窗口 |
| `restore_time` | 告警事件 basic.restore_time | 用于确定结束时间（可为空） |

## 自动执行步骤

### Step 1：获取告警事件基本信息

```bash
xray-cli alarm event get <event_id> --output-format json
```

提取：`trigger_time`、`restore_time`、`level`、`alarm_details.trigger_rules`

时间窗口计算：
- `start` = trigger_time - 5 分钟
- `end` = restore_time（若已恢复）或 trigger_time + 30 分钟（若未恢复）

### Step 2：异常报错聚类（Problem 分析）

```bash
xray-cli trace search --app alipayservice \
  --mode error \
  --start "<start>" \
  --end "<end>" \
  --output-format json
```

分析：
- `total` > 0 时，提取 error span 聚类，按数量排序取 Top5
- `total` = 0 时，输出"告警期间无 error span，服务自身报错排除"

```bash
xray-cli trace exception --app alipayservice \
  --exceptions "java.lang.Exception,java.lang.RuntimeException,java.util.concurrent.TimeoutException,com.xiaohongshu.exception.XhsException" \
  --start "<start>" \
  --end "<end>" \
  --output-format json
```

分析：
- 有异常聚类时，按 count 降序取 Top3，输出异常类名 + 出现次数 + 堆栈摘要（前 5 行）
- 无异常时，输出"告警期间无 Java 异常，服务内部错误排除"

## 依赖缺口（需人工跟进）

### 缺口1：RPC 上下游指标

**原因**：`alipayservice` 中间件版本不满足 `xray-cli trace topology service` 要求（需 ≥ 3.3.31.3-RELEASE）

**人工操作**：
1. 打开 XRay 拓扑页：https://xray.devops.xiaohongshu.com/d/topology?app=alipayservice
2. 查看上下游服务的调用量、错误率、耗时是否在告警时间段内异常
3. 重点关注：调用方（上游）流量是否突增、被调用方（下游）错误率是否上升

### 缺口2：变更查询

**原因**：`xray-cli` 暂无变更查询原子能力

**人工操作**：
1. 打开变更查询页：https://xray.devops.xiaohongshu.com/event/search?app=alipayservice
2. 筛选告警触发时间前后 30 分钟内的变更记录
3. 重点关注：服务发布、配置变更、限流规则变更

## 失败策略

| 情况 | 输出 |
|------|------|
| `alarm event get` 失败 | `status: blocked`，附 stderr |
| `trace search` 无数据 | `error_spans: none`，继续执行 exception |
| `trace exception` 超时/失败 | `exceptions: unknown`，附错误信息 |
| 认证失败 | `status: blocked`，输出 `xray-cli auth login` 提示，不伪装成正常结果 |

## 输出报告格式

```json
{
  "skill": "alipayservice-success-rate-diagnosis",
  "event_id": "<event_id>",
  "trigger_time": "<trigger_time>",
  "restore_time": "<restore_time | null>",
  "duration_minutes": "<N>",
  "analysis": {
    "error_spans": {
      "status": "none | found | unknown",
      "total": 0,
      "top_errors": []
    },
    "exceptions": {
      "status": "none | found | unknown",
      "top_exceptions": []
    }
  },
  "dependency_gaps": [
    {
      "name": "RPC拓扑指标",
      "reason": "中间件版本不满足 topology service 查询要求",
      "manual_url": "https://xray.devops.xiaohongshu.com/d/topology?app=alipayservice"
    },
    {
      "name": "变更查询",
      "reason": "xray-cli 暂无变更查询原子能力",
      "manual_url": "https://xray.devops.xiaohongshu.com/event/search?app=alipayservice"
    }
  ],
  "conclusion": "auto_cleared | error_found | dependency_gap_required",
  "suggested_actions": []
}
```

### conclusion 判定规则

- `error_found`：error_spans.total > 0 或 exceptions.top_exceptions 非空
- `auto_cleared`：两项均为 none（无报错，建议结合人工跟进 RPC/变更排除）
- `dependency_gap_required`：任一自动步骤 status=unknown 时

## 运行约束

- Python 3.12，只用标准库（`json`、`subprocess`、`datetime`、`sys`）
- 所有 xray-cli 调用只读，无写操作
- 运行时无交互，认证失败直接输出 `blocked` 不等待
- 临时文件写 `/tmp/alipayservice-diagnosis-<event_id>/`，运行结束不清理（供调试）
