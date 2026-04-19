---
name: xray-metrics-query
description: 查询 XRay 平台的 Prometheus/VictoriaMetrics 指标数据。支持即时查询(instant)和范围查询(range)两种模式。当用户询问"查XRay指标"、"查询Prometheus数据"、"查看监控指标"、"XRay指标查询"、"监控语句"、"监控查询"、"PromQl"、"prometheus语句" 时触发。
---

# XRay 指标查询 Skill

通过 XRay 平台 API 查询 Prometheus/VictoriaMetrics 指标数据，支持即时查询和时间范围查询。

## 快速使用

```bash
python3 scripts/query.py '{
  "promql": "up",
  "datasource": "vms-infra",
  "start_time": "now-1h",
  "end_time": "now",
  "instant": false
}'
```

## 参数说明

| 参数 | 说明 | 示例值 | 必填 |
|------|------|--------|------|
| `promql` | Prometheus 查询语句 (PromQL) | `"up"`, `"rate(http_requests_total[5m])"` | 是 |
| `datasource` | 数据源名称 | `"vms-infra"`, `"vms-recommend"`, `"vms-search"`, `"vms-shequ"` | 是 |
| `start_time` | 开始时间 | `"now-1h"`, `"1709546400"`, `"2026-03-13T10:00:00Z"` | 是 |
| `end_time` | 结束时间/查询时间点 | `"now"`, `"1709550000"`, `"2026-03-13T11:00:00Z"` | 是 |
| `instant` | 查询类型 | `true`=即时查询，`false`=范围查询 | 否（默认false） |

## 认证配置

从 `~/.openclaw/workspace/.redInfo` 文件读取 SSO token，**无需手动配置**。

路径可通过环境变量覆盖：

```bash
export OPENCLAW_WORKSPACE="/custom/path"   # 自定义 workspace 目录
export RED_INFO_PATH="/custom/.redInfo"    # 或直接指定 .redInfo 文件路径
```

请确保已完成 SSO 登录，登录态文件存在且未过期。

## 查询类型说明

### 即时查询 (Instant Query)
返回某个时间点的即时数据。适用于查询当前状态或某个特定时刻的指标值。

```bash
python3 scripts/query.py '{
  "promql": "up",
  "datasource": "vms-infra",
  "start_time": "now-1h",
  "end_time": "now",
  "instant": true
}'
```

### 范围查询 (Range Query)
返回时间范围内的时序数据。适用于查看趋势、绘制图表等场景。

```bash
python3 scripts/query.py '{
  "promql": "rate(http_requests_total[5m])",
  "datasource": "vms-recommend",
  "start_time": "now-1h",
  "end_time": "now",
  "instant": false
}'
```

## 时间格式支持

支持多种时间格式：

### 相对时间
- `now` - 当前时间
- `now-5m` - 5分钟前
- `now-1h` - 1小时前
- `now-1d` - 1天前

### 时间戳
- `1709546400` - 秒级时间戳（自动转换为毫秒）
- `1709546400000` - 毫秒级时间戳

### ISO 格式
- `2026-03-13T10:00:00Z` - ISO 8601 格式
- `2026-03-13 10:00:00` - 标准日期时间格式

## 常用数据源

| 数据源 | 说明 |
|--------|------|
| `vms-infra` | 基础设施监控 |
| `vms-recommend` | 推荐系统监控 |
| `vms-search` | 搜索系统监控 |
| `vms-shequ` | 社区系统监控 |

## 常用场景

**查询服务存活状态**
```bash
python3 scripts/query.py '{
  "promql": "up{job=\"my-service\"}",
  "datasource": "vms-infra",
  "start_time": "now",
  "end_time": "now",
  "instant": true
}'
```

**查询过去1小时的请求率**
```bash
python3 scripts/query.py '{
  "promql": "rate(http_requests_total[5m])",
  "datasource": "vms-recommend",
  "start_time": "now-1h",
  "end_time": "now",
  "instant": false
}'
```

**查询CPU使用率趋势**
```bash
python3 scripts/query.py '{
  "promql": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
  "datasource": "vms-infra",
  "start_time": "now-6h",
  "end_time": "now",
  "instant": false
}'
```

**查询内存使用情况**
```bash
python3 scripts/query.py '{
  "promql": "node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100",
  "datasource": "vms-infra",
  "start_time": "now-1h",
  "end_time": "now",
  "instant": false
}'
```

## 输出格式

脚本输出 JSON 到 stdout：

**成功响应：**
```json
{
  "success": true,
  "query_type": "range",
  "query": {
    "promql": "up",
    "datasource": "vms-infra",
    "start_time": "now-1h",
    "end_time": "now"
  },
  "data": {
    "status": "success",
    "data": {
      "resultType": "matrix",
      "result": [...]
    }
  }
}
```

**失败响应：**
```json
{
  "success": false,
  "error": "HTTP错误: 401",
  "detail": "认证失败"
}
```

## 注意事项

- 脚本依赖 `httpx` 库，需安装：`pip3 install httpx`
- SSO token 有效期有限，过期后需重新完成 SSO 登录
- 查询时间跨度过大可能导致超时，建议单次查询不超过24小时
- PromQL 语法参考：https://prometheus.io/docs/prometheus/latest/querying/basics/
