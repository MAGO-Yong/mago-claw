---
name: xray_changevent_query
description: >
  查询 XRay 平台（https://xray.devops.xiaohongshu.com）的变更事件时间线，支持按时间范围、变更系统、标签、环境、事件类型、服务等多维度过滤。
  当用户遇到以下情况时触发本 Skill：
  查询变更事件："查一下最近的变更"、"有没有 XX 服务的变更"、"XX 时间段有哪些变更事件"、"查一下 apollo 的变更记录"；
  变更关联排查："XX 时间点前后有哪些变更"、"查一下外流推荐相关变更"、"有哪些 human 变更"；
  故障辅助分析："查变更时间线"、"有没有可疑的变更"、"列出 prod 环境的变更"。
---

# XRay 变更事件时间线查询 Skill

通过 XRay 平台 API（`/api/change/event_timeline`）查询变更事件时间线，支持时间范围、系统、标签、环境、服务等多维度过滤。

## 快速使用

```bash
# 查询最近1小时的所有 human 变更（默认 prod 环境）
python3 scripts/query.py --start "now-1h"

# 查询指定时间段的变更
python3 scripts/query.py --start "2026-03-23 19:00:00" --end "2026-03-23 20:00:00"

# 按变更系统过滤
python3 scripts/query.py --start "now-2h" --system apollo racingweb

# 按标签过滤（外流推荐相关变更）
python3 scripts/query.py --start "now-2h" --tag 外流推荐

# 按服务过滤（多个服务）
python3 scripts/query.py --start "now-1h" --service arkfeedx-1-default arkmixrank-77-default arkfeedx-1-exp

# 组合过滤：系统 + 标签 + 服务
python3 scripts/query.py \
  --start "2026-03-23 19:00:00" \
  --end "2026-03-23 20:00:00" \
  --system apollo racingweb \
  --tag 外流推荐 \
  --service arkfeedx-1-default arkmixrank-77-default arkfeedx-1-exp

# 查询 system 类型事件
python3 scripts/query.py --start "now-1h" --event-type system

# 查询非 prod 环境
python3 scripts/query.py --start "now-1h" --env staging
```

## 参数说明

| 参数 | 说明 | 示例值 | 必填 |
|------|------|--------|------|
| `--start` | 开始时间 | `now-1h` / `now-30m` / `"2026-03-23 19:00:00"` / Unix时间戳 | **是** |
| `--end` | 结束时间（默认 now） | `now` / `"2026-03-23 20:00:00"` | 否 |
| `--system` | 变更系统，可多选 | `apollo racingweb` | 否（默认不限） |
| `--tag` | 变更标签，可多选 | `外流推荐` | 否（默认不限） |
| `--custom-tag` | 自定义标签，可多选 | | 否（默认为空） |
| `--env` | 环境，可多选 | `prod` / `staging` | 否（默认 prod） |
| `--event-type` | 事件类型，可多选 | `human` / `system` | 否（默认 human） |
| `--service` | 服务名，可多选 | `arkfeedx-1-default arkmixrank-77-default` | 否（默认不限） |
| `--experiment` | 实验过滤，可多选 | `all` / 实验ID | 否（默认 all） |
| `--app` | 应用过滤，可多选 | `all` | 否（默认 all） |
| `--db` | 数据库过滤，可多选 | `all` | 否（默认 all） |
| `--preplan` | 预案过滤，可多选 | `all` | 否（默认 all） |
| `--domain` | 域名过滤，可多选 | `all` | 否（默认 all） |
| `--strategy` | 策略过滤，可多选 | `all` | 否（默认 all） |
| `--index` | 索引过滤，可多选 | `all` | 否（默认 all） |
| `--model` | 模型过滤，可多选 | `all` | 否（默认 all） |
| `--job-id` | 任务ID过滤，可多选 | `all` | 否（默认 all） |
| `--other` | 其他过滤，可多选 | `all` | 否（默认 all） |

### 时间格式支持

| 格式 | 示例 |
|------|------|
| 相对时间 | `now-5m`, `now-1h`, `now-2h`, `now-7d` |
| 秒级时间戳 | `1742727600` |
| 毫秒级时间戳 | `1742727600000` |
| 标准日期时间 | `"2026-03-23 19:00:00"` |
| 仅日期 | `"2026-03-23"` |

## 认证配置

从 `~/.openclaw/workspace/.redInfo` 文件读取 SSO token，**无需手动配置**。

路径可通过环境变量覆盖：

```bash
export OPENCLAW_WORKSPACE="/custom/path"   # 自定义 workspace 目录
export RED_INFO_PATH="/custom/.redInfo"    # 或直接指定 .redInfo 文件路径
```

请确保已完成 SSO 登录，登录态文件存在且未过期。

## 返回字段说明

每条 event 包含以下字段（脚本已从 `info` 字段中自动解析变更详情）：

| 字段 | 说明 | 来源 |
|------|------|------|
| `time` | 变更时间（GMT+8） | 接口字段 `start` |
| `system` | 变更系统（apollo/racingweb/autobots 等） | 接口字段 `system_name` |
| `operator` | 操作人花名（真名） | 接口字段 `operator_name` |
| `resource_name` | 变更资源名（apollo namespace 或实验名） | 接口字段 `resource_name` |
| `action` | 变更动作（配置变更/Flag变更/实验上线 等） | 接口字段 `event_cn_name` |
| `env` | 环境 | 接口字段 `env` |
| `link` | 变更详情链接 | 接口字段 `link` |
| `change_object` | 具体变更的 key 名（apollo 变更） | 从 `info.change_object` 解析 |
| `before_value` | 变更前的值（已解嵌套 JSON） | 从 `info.before_value` 解析 |
| `after_value` | 变更后的值（已解嵌套 JSON） | 从 `info.after_value` 解析 |
| `param_changes` | 实验参数 diff 列表（racingweb 变更） | 从 `info.after_value.parasChangeEvents` 解析 |
| `info_raw` | 原始 info 字段（当无法解析详情时展示，截断 500 字符） | fallback |

**`param_changes` 格式：**
```json
[
  {
    "varId": 482881,
    "before_params": {"hf_new_mix_ad_power": "1"},
    "after_params":  {"hf_new_mix_ad_power": "4"}
  }
]
```

**Apollo 变更限制：** XRay 接口对 apollo 变更只返回 namespace，不返回具体 key/value，因此 `change_object`/`before_value`/`after_value` 对大部分 apollo 变更为空。需要去 redcloud 查具体 key diff：`https://redcloud.devops.xiaohongshu.com/redconf/app/nameSpaceList?appId={namespace}&confEnv=PRO`

**示例输出：**
```json
{
  "success": true,
  "count": 2,
  "events": [
    {
      "time": "2026-03-25 19:53:16",
      "system": "racingweb",
      "operator": "剑晨(剑晨)",
      "resource_name": "外流大混排框架重构",
      "action": "Flag变更(全量阶段)",
      "env": "prod",
      "link": "https://racing.devops.xiaohongshu.com/...",
      "param_changes": [
        {
          "varId": 482881,
          "before_params": {"hf_new_mix_ad_power": "1"},
          "after_params":  {"hf_new_mix_ad_power": "4"}
        }
      ]
    },
    {
      "time": "2026-03-25 19:44:00",
      "system": "apollo",
      "operator": "缝魂(刘亮彤)",
      "resource_name": "arkfeedx",
      "action": "配置变更",
      "env": "prod",
      "link": "https://redcloud.devops.xiaohongshu.com/...",
      "change_object": "hf_high_quality_boost_v2_apollo_config",
      "after_value": {"configMap": {"config1": {"hfHighQualityNoteBoostV2TagList": [888902]}}}
    }
  ]
}
```

### 失败响应

```json
{
  "success": false,
  "error": "HTTP错误: 401"
}
```

## 常见查询场景

### 故障复盘：查某时间段前后的变更

```bash
python3 scripts/query.py --start "2026-03-23 18:30:00" --end "2026-03-23 20:30:00"
```

### 查某服务最近1小时的变更

```bash
python3 scripts/query.py --start "now-1h" --service arkfeedx-1-default
```

### 查外流推荐相关系统的变更

```bash
python3 scripts/query.py --start "now-2h" --tag 外流推荐 --system apollo racingweb
```

### 查所有类型（human + system）的变更

```bash
python3 scripts/query.py --start "now-1h" --event-type human system
```

## 注意事项

- 脚本使用 Python 3 标准库，**无需额外安装依赖**
- SSO token 有效期有限，过期后需重新完成 SSO 登录
- `--system`、`--tag`、`--service` 均为可选，不传则不限制该维度
- 接口返回的 events 字段结构以实际响应为准，不同变更系统字段可能有所差异
- `--event-type` 常用值：`human`（人工变更）、`system`（系统自动变更）
