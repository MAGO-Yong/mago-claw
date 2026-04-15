---
name: pingcode-query-workitem
description: 根据筛选条件查询工作项(需求、缺陷、子任务)。当用户想要查询工作项时使用，例如：查询我最近10天创建的需求、查询我最近7天负责的缺陷、查询普兰最近50天建的工作项。支持按负责人、创建人、日期范围、工作项类型、状态、所属空间等条件筛选。
---

# 查询工作项（Query Work Item）

## 上下文信息

| 信息 | 来源 |
|------|------|
| 当前登录用户邮箱 | 环境变量 `XHS_USER_EMAIL` |

> 当用户使用"我"指代自己时（如"查询我负责的工作项"），**必须先通过 `echo $XHS_USER_EMAIL` 读取环境变量，获取真实邮箱地址**，再将该邮箱地址作为筛选条件的值传入脚本。禁止将 `XHS_USER_EMAIL` 字符串本身作为参数值传入。

---

## 工作流程

### Step 1：获取筛选字段

调用脚本 `scripts/get_workitem_filter_fields.py`，获取：
- 可用筛选字段列表
- 筛选条件构建规则
- 提示信息

**调用方式：**
```bash
python scripts/get_workitem_filter_fields.py
```

> **重要**：必须先执行此脚本，才能执行 Step 2。返回结果中的提示信息须严格遵守。

---

### Step 2：根据筛选条件查询工作项

调用脚本 `scripts/search_workitem_by_condition.py`，返回符合条件的工作项列表。

**调用方式：**
```bash
python scripts/search_workitem_by_condition.py \
    --filter-condition '<filterCondition JSON>'
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `--filter-condition` | JSON string | 筛选条件，key 为筛选字段，value 为筛选值 |

> `--filter-condition` 的 key 和 value 必须依据 Step 1 返回的筛选字段和构建规则来构造。

## 规则

1. 执行 `search_workitem_by_condition.py` 前，**必须**先执行 `get_workitem_filter_fields.py`。
2. 脚本返回结果中包含提示信息，**必须严格遵守**这些提示信息。
