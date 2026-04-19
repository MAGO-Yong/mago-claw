---
name: index-switch-check
description: 检查索引表的切换状态，判断是否存在以下四类异常：「切换卡住」「构建下发延迟」「索引构建延迟」「上游数据停止更新」。用户说「检查索引切换」「索引有没有卡」「表切换状态」「切换异常」等时触发。
---

# 索引切换状态检查

## ⚠️ 回复规则（强制执行）

执行脚本后，**必须**将结果按以下三层格式整理后回复给用户，**禁止**直接粘贴脚本原始输出。

## 使用方式

1. 询问用户 `dataSourceName`（必填），`tableName`（选填，默认同 dataSourceName）
2. 执行脚本获取原始数据：

```bash
python3 skills/index-switch-check/scripts/check_switch.py <dataSourceName> [tableName]
```

3. 将脚本输出整理为下方「回复格式」后发给用户

## 分析流程

```
数据版本(build/version/info) → 推算数据更新间隔 → GAP = 间隔 × 2
构建版本(index/history/v2)   → 最新 buildVersion + 对应数据版本
部署信息(deployment/list)    → 每个 zone 独立分析:
  A. targetVersion 距当前时间 > GAP?
     是 → B. tgt 落后 build > GAP?  → ⚠️ 构建下发延迟
          C. build 落后最新数据 > GAP? → ⚠️ 索引构建延迟
  D. cur != tgt 且切换耗时 > GAP?   → 🔴 切换卡住
  始终输出: cur距今 / cur→build / tgt→build / data→build 四项 gap
```

## 回复格式（三层结构，严格遵守）

### 【第一层】基本信息（纯客观，不含任何判断）
```
索引表：<ds_name>
最新构建版本：<build_version>
构建对应数据：<build_data_ver>（构建完成 <build_time>）
上游最新数据：<latest_data_ver>（版本时间 <latest_data_time>）
```

### 【第二层】Zone 切换明细（纯客观，不含任何判断）
用表格展示，每个 zone 一行，**必须包含以下所有字段**：

| zone | 当前版本 | 目标版本 | 切换状态 |
|---|---|---|---|
| <zone> | <cur_vid> | <tgt_vid> | 已完成 / 切换中（progress=x/y 耗时=Nmin） |

### 【第三层】结论与建议
- ✅ 无异常：一句话说明
- 有异常：逐条列出，每条包含异常类型 + 具体数据 + 建议操作

### 接口失败时（完全替代上面三层）
直接说明：
- 哪个接口查询失败
- 失败原因（表名不存在 / 无数据 / 不匹配等）
- 具体建议（如何修正）

详细判断逻辑见 `scripts/check_switch.py`。
