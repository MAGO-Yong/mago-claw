# rec-new-note-diagnosis 依赖配置

## 外部 Skills 依赖

本 skill 依赖以下外部 skills，使用前请确保已安装：

| 依赖 Skill | 用途 | 安装命令 | 必需 |
|------------|------|----------|------|
| `xray_changevent_query` | 查询 XRay 变更事件（Apollo配置+实验变更） | `openclaw skill install xray_changevent_query` | ✅ |
| `xray_metrics_query` | 查询 XRay 监控指标 | `openclaw skill install xray_metrics_query` | ✅ |
| `index-switch-check` | 检查索引切换状态 | `openclaw skill install index-switch-check` | ✅ |
| `data-fe-common-sso` | 获取登录态 | `openclaw skill install data-fe-common-sso` | ✅ |

## 依赖检测机制

### 1. 启动时检测

在 skill 被调用时，首先检测依赖项：

```bash
# 检测依赖脚本
python3 scripts/check_dependencies.py
```

### 2. 缺失依赖提示

如果检测到依赖缺失，输出提示：

```
❌ 缺少必需的 skill 依赖：

1. xray_changevent_query - 用于查询 Apollo/实验变更
   安装命令：openclaw skill install xray_changevent_query

2. xray_metrics_query - 用于查询监控指标
   安装命令：openclaw skill install xray_metrics_query

请安装上述依赖后重试。
```

### 3. 依赖路径约定

依赖 skills 的安装路径约定：

```
~/.openclaw/workspace/skills/
├── rec-new-note-diagnosis/          # 本 skill
├── xray_changevent_query/           # 依赖：变更查询（XRay平台）
├── xray_metrics_query/              # 依赖：指标查询
├── index-switch-check/              # 依赖：索引检查
└── data-fe-common-sso/              # 依赖：登录态
```

## Skill 调用方式

### 调用 xray_changevent_query

```bash
# 查询 Apollo 配置变更
python3 ~/.openclaw/workspace/skills/xray_changevent_query/scripts/query.py \
    --start "2026-03-23 00:00:00" \
    --end "2026-03-23 23:59:59" \
    --system apollo \
    --service arkfeedx arkfeedx-1-default

# 查询实验平台变更
python3 ~/.openclaw/workspace/skills/xray_changevent_query/scripts/query.py \
    --start "2026-03-23 00:00:00" \
    --end "2026-03-23 23:59:59" \
    --system racingweb \
    --tag 外流推荐
```

### 调用 xray_metrics_query

```bash
# 查询 Prometheus 指标
python3 ~/.openclaw/workspace/skills/xray_metrics_query/scripts/query.py '{
    "promql": "sum(rate(new_note_cnt_sum{...}[1m]))",
    "datasource": "vms-recommend",
    "start_time": "now-1h",
    "end_time": "now"
}'
```

### 调用 index-switch-check

```bash
# 检查索引切换状态
python3 ~/.openclaw/workspace/skills/index-switch-check/scripts/check_switch.py \
    dssm_inst_v1_oo_1day --deep
```

### 调用 data-fe-common-sso

```bash
# 获取登录态
~/.openclaw/workspace/skills/data-fe-common-sso/script/run-sso.sh \
    "/home/node/.openclaw/workspace"
```

## 配置变更检测流程

使用外部 skills 的配置变更检测流程：

```
rec-new-note-diagnosis 被调用
    ↓
Step 0: 检测依赖项
    ↓
检查 xray_changevent_query 是否安装
    ├─ 未安装 → 提示安装命令，退出
    └─ 已安装 → 继续
    ↓
检查 data-fe-common-sso 是否安装
    ├─ 未安装 → 提示安装命令，退出
    └─ 已安装 → 继续
    ↓
获取 SSO Token
    ↓
调用 xray_changevent_query 查询变更
    ├─ Apollo 配置变更（arkfeedx 相关）
    └─ 实验平台变更（外流推荐标签）
    ↓
与 config-watchlist.json 对比筛选高风险变更
    ↓
进入对应 SOP 步骤
```

## 文件结构

```
rec-new-note-diagnosis/
├── SKILL.md                      # 主文档
├── DEPENDENCIES.md               # 依赖说明
├── scripts/
│   ├── check_dependencies.py     # 依赖检测脚本
│   └── diagnose.py               # 主诊断脚本
├── references/
│   ├── promql-collection.json    # PromQL集合
│   ├── decision-tree.json        # 决策树
│   ├── config-watchlist.json     # 配置监控清单
│   ├── appendix.md               # 附录
│   └── sop.md                    # SOP文档
```

## 变更查询与筛选流程

### Step 0.3: 查询配置变更

```python
# 1. 查询 Apollo 配置变更
python3 skills/xray_changevent_query/scripts/query.py \
    --start "now-24h" \
    --system apollo \
    --service arkfeedx arkfeedx-1-default arkfeedxmerchant

# 2. 查询实验平台变更
python3 skills/xray_changevent_query/scripts/query.py \
    --start "now-24h" \
    --system racingweb \
    --tag 外流推荐
```

### 与 config-watchlist.json 对比筛选

筛选逻辑：

1. **Apollo 变更匹配**：
   - 检查 `change_object` 是否匹配 `apollo_configs.critical/high/medium` 中的 `key`
   - 检查 `resource_name` 是否为 `arkfeedx`、`arkfeedx-1-default`、`arkmixrank`

2. **实验变更匹配**：
   - 检查实验标签是否包含 `外流推荐`
   - 检查 `resource_name` 或 `change_object` 是否匹配 `experiment_flags` 中的 `pattern`

### 高风险变更识别

| 配置/Flag | 风险等级 | 匹配字段 |
|-----------|----------|----------|
| `hf_lve_merge_age_*_ratio` | 🔴 极高 | `change_object` |
| `hf_all_lve_merge_age_*_ratio` | 🔴 极高 | `change_object` |
| `enable_fdx_filter_note_time` | 🔴 高 | `change_object` |
| `feedx_life_time_filter_min_create_hour` | 🔴 高 | `change_object` |
| `*mix*rank*` | 🟠 高 | `resource_name` |
| `*first*screen*` | 🟠 高 | `resource_name` |

## 使用说明

### 首次使用

1. 安装依赖 skills：
```bash
openclaw skill install xray_changevent_query
openclaw skill install xray_metrics_query
openclaw skill install index-switch-check
openclaw skill install data-fe-common-sso
```

2. 验证依赖：
```bash
python3 skills/rec-new-note-diagnosis/scripts/check_dependencies.py
```

3. 开始使用：
```bash
# 触发诊断
python3 skills/rec-new-note-diagnosis/scripts/diagnose.py

# 检查过去48小时
python3 skills/rec-new-note-diagnosis/scripts/diagnose.py --hours 48

# 从 Step 2 开始
python3 skills/rec-new-note-diagnosis/scripts/diagnose.py --step 2
```

### 自动检测

每次调用 skill 时自动检测依赖：

```python
# diagnose.py
import subprocess
import sys

# 先检测依赖
def check_deps():
    result = subprocess.run(
        ["python3", "scripts/check_dependencies.py"],
        capture_output=True
    )
    return result.returncode == 0

if __name__ == "__main__":
    if not check_deps():
        sys.exit(1)
    # 继续诊断...
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v3.1 | 2026-03-24 | 替换 change-event-locator 为 xray_changevent_query |
| v3.0 | 2026-03-23 | 新增变更预检（Step 0），支持精细化趋势对比 |
| v2.0 | 2026-02-20 | 初始版本 |
