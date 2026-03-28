---
name: xray-exception-analysis
description: '分析小红书 XRay 平台的异常堆栈和 Logview 调用链。支持两条排查链路：(1) 异常堆栈链路——通过服务名、时间范围、异常类名（如 java.util.concurrent.TimeoutException）获取聚类堆栈分布及关联的 messageId，再查询完整 Logview；(2) 错慢采样链路——通过服务名、接口类型（RPC 服务端用 Service，HTTP 用 URL，RPC 客户端用 Call）、时间范围、采样类型（fail/longest/success）获取采样 messageId，再查询完整 Logview 进行耗时分析。触发场景：上下文中包含exception 堆栈、错误堆栈、logview、异常详情、NullPointerException 堆栈、exception stack、堆栈查询、发现某个Exception、用户对话中包含"帮我查一下某服务的 TimeoutException"、"分析某接口的慢请求"、"看看这个异常的堆栈"、"帮我拿一个失败请求的 logview"、"排查 xxx 服务的报错"时使用本 skill。'
version: 1.0.0
metadata:
  category: trace
  subcategory: exception-analysis
  platform: xray
  trigger: service_name/exception_class/time_range/interface
  input: [app, start, end, exceptions, type, name, sample_type, messageId]
  output: [stack_cluster, messageId, logview, root_cause_summary]
  impl: python-script
---

# XRay Exception & Logview 排查

## 概述

两条独立排查链路，每条链路对应独立的 Python 脚本：

- **链路一（异常堆栈）**: `scripts/stack_cluster.py` → `scripts/logview.py`
- **链路二（错慢采样）**: `scripts/sample.py` → `scripts/logview.py`

所有接口请求统一使用 `xray_ticket: pass` 通过鉴权，无需用户提供 token。

接口完整规范见 [references/api-spec.md](references/api-spec.md)。

---

## 链路一：异常堆栈分析

**适用场景**: 排查某类异常的根因堆栈，如 TimeoutException、NullPointerException。

### Step 1 — 聚类分析异常堆栈

```bash
python3 scripts/stack_cluster.py \
  --app <服务appkey> \
  --start <秒级时间戳> \
  --end <秒级时间戳> \
  --exceptions java.util.concurrent.TimeoutException
  # 多个异常用空格分隔：--exceptions ExcA ExcB
```

从输出中读取：
- **堆栈 #1**（ratio 最大）→ 最主要根因，向用户展示 stack 内容
- **关联 messageId** → 取第一个用于 Step 2

### Step 2 — 查询 Logview

```bash
python3 scripts/logview.py --message-id <messageId>
```

输出为原始 JSON，分析要点见下方"Logview 分析要点"。

---

## 链路二：错慢请求采样分析

**适用场景**: 排查某个接口的慢请求或失败请求。

### Step 1 — 获取采样 MessageId

```bash
python3 scripts/sample.py \
  --app <服务appkey> \
  --type <接口类型> \
  --name <接口名称> \
  --start <秒级时间戳> \
  --end <秒级时间戳> \
  --sample-type fail   # fail / longest / success
  # --ip ALL（默认） --zone <机房>（可选）
```

**`--type` 速查**：

| 用户描述 | `--type` 值 | `--name` 示例 |
|---------|------------|--------------|
| RPC 接口（服务端被调用） | `Service` | `UserService.getUserById` |
| HTTP 接口 | `URL` | `/api/v1/user/info` |
| RPC 客户端调用 | `Call` | `UserService.getUserById` |
| Redis 操作 | `Redis.<集群名>` | `GET` |
| MySQL 操作 | `SQL` | `user.select` |

输出中的 messageId 即为采样结果。若为"未获取到采样 messageId"，说明该时段无记录。

### Step 2 — 查询 Logview

```bash
python3 scripts/logview.py --message-id <messageId>
```

---

## Logview 分析要点

拿到 `data.message`（调用树 JSON）后：

1. **定位异常**: 找 `"error": true` 的节点，`data` 字段为完整堆栈
2. **定位慢调用**: 找 `durationInMillis` 最大的子节点，逐层下钻
3. **节点类型判断**:
   - `durationInMillis >= 0` → transaction（有耗时的调用）
   - `durationInMillis == -1` → event（瞬时事件，如异常上报）
4. **追溯上游**: 用 `parentMessageId` / `rootMessageId` 追溯调用来源
5. **数据过期**: `data.code` 非 200（1003=数据缺失，1004=已归档）时告知用户

输出分析结论格式：

```
## 根因分析结论

**请求概况**: [服务名] 在 [时间] 发起请求，总耗时 [X]ms，状态 [成功/失败]

**异常/失败**: [有/无] — [具体描述]

**性能瓶颈**: [具体节点] 耗时 [X]ms，占总耗时 [Y]%

**根因判断**: [一句话结论]

**建议**: [针对性建议]
```
