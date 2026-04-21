---
name: meal-order
description: |
  自动订餐助手，处理所有与订餐相关的请求。
  
  **必须使用此 skill 当用户提到以下任何内容时：**
  - 订餐、订外卖、订午餐/晚餐
  - "帮我订餐"、"订明天午餐"、"看看有什么吃的"
  - 查询餐品、查看菜单、预订食物
  - 取餐码、订餐系统、公司订餐
  - 即使只是询问今天有什么餐厅/菜品可选
---

# Meal Order Skill

帮助用户完成自动订餐流程。所有 CLI 命令**默认输出 JSON**，由 AI 解析后用自然语言回复用户。

## 工作流程

```
用户: "帮我订明天午餐"
    │
    ▼
【步骤1】检查 .meal_config.json 是否存在且 code 有效
    │
    ├── 有效 ──► 继续
    └── 无效 ──► 提示用户配置: python meal.py config --code <code>
    │
    ▼
【步骤2】python meal.py reserve --date <明天>
    │
    ▼
【步骤3】解析 JSON，提取商户/菜品列表，用自然语言展示给用户
    │
    ▼
【步骤4】用户选择菜品
    │
    ▼
【步骤5】python meal.py book --goods <id> --date <date> --store <store_id>
    │
    ▼
【步骤6】解析 JSON，向用户展示订餐结果（取餐码、取餐柜等）
```

## 命令速查

| 命令 | 用途 | 示例 |
|------|------|------|
| `config` | 配置认证信息 | `python meal.py config --code xxx` |
| `position` | 查询可用取餐地点 | `python meal.py position` |
| `bind-position` | 绑定用餐地点 | `python meal.py bind-position --position-id 5951` |
| `reserve` | 查询可预订菜单 | `python meal.py reserve` |
| `guide` | 查看当日订单状态 | `python meal.py guide` |
| `book` | 一键订餐（确认+支付） | `python meal.py book --goods 1025596 --date 2026-03-12 --store 11534` |
| `cancel` | 取消订单 | `python meal.py cancel` 或 `python meal.py cancel --order-id 210336461` |
| `history` | 查询历史订单 | `python meal.py history` 或 `python meal.py history --days 14` |
| `evaluate` | 列出待评价订单 | `python meal.py evaluate` |
| `evaluate --order-id <id> --zt-star <1-5> --taste-star <1-5> --fl-star <1-5>` | 提交三维度评价 ⭐ | `python meal.py evaluate --order-id 211757660 --zt-star 5 --taste-star 4 --fl-star 4 --content "轻食不错"` |

**注意：** 所有命令均输出 JSON，无需 `--raw`。

## 关键 JSON 字段说明

### reserve 返回结构

```json
{
  "lunch": {
    "data": {
      "nowDate": "2026-03-13",
      "goodVoList": [
        {
          "id": 1025596,
          "goodName": "麻辣鲜牛肉捞烫杯",
          "merchantStoreId": 11534,
          "merchantStoreName": "左庭右院",
          "goodPrice": 3000,
          "score": 4.8,
          "monthSale": 320
        }
      ]
    }
  },
  "dinner": { ... }
}
```

### guide 返回结构（关键字段）

```json
{
  "data": {
    "currentDatePeriod": {
      "useDate": "2026-03-12",
      "timeIntervalList": [
        {
          "name": "午餐",
          "orderId": 210309356,
          "goodName": "麻辣鲜牛肉捞烫杯",
          "dinnerTime": "12:00",
          "remainTimeStr": "配送中",
          "book": false,
          "lateOrder": {
            "boxNumber": "B16",
            "orderStatus": "IS_SENDING"
          }
        }
      ]
    }
  }
}
```

### book 返回结构

```json
{
  "success": true,
  "pay": {
    "data": {
      "orderId": 210309356,
      "boxNumber": "B16",
      "cabinet": "B",
      "dinnerTime": "12:00",
      "merchantName": "左庭右院",
      "goodsName": "麻辣鲜牛肉捞烫杯"
    }
  }
}
```

### cancel（无 order-id）返回结构

```json
{
  "hint": "请使用 --order-id 指定要取消的订单",
  "orders": [
    {
      "orderId": 210377211,
      "mealType": "午餐",
      "goodName": "烤鸡腿肉烤熟谷物能量碗",
      "status": "配送中"
    }
  ]
}
```

## 状态码含义

| 原始值 | 含义 |
|--------|------|
| `IS_SENDING` | 配送中 |
| `IS_COMPLETE` | 已完成 |
| `IS_CANCEL` | 已取消 |
| `IS_WAIT` | 待配送 |
| `IS_DONE` | 已送达 |

## 典型交互场景

### 场景1：帮我订明天午餐

```
1. python meal.py reserve --date 2026-03-13 --interval 2
2. 解析 JSON，列出所有商户和菜品
3. 用户选择后: python meal.py book --goods <id> --date 2026-03-13 --store <store_id> --interval 2
4. 解析 pay.data，告知用户取餐码和取餐时间
```

### 场景2：查看今天的订餐

```
1. python meal.py guide
2. python meal.py position   # 获取当前绑定地点名称（data.positionId 对应的 name）
3. 解析 timeIntervalList，按午餐/晚餐分别展示菜品、状态、取餐柜
4. 在回复中明确告知用户当前取餐地点（如"取餐地点：上海 LuOne-23 楼"），避免误会
```

### 场景3：取消订单

```
1. python meal.py cancel         # 先列出可取消订单
2. python meal.py cancel --order-id <id>   # 执行取消
```

### 场景5：评价已完成的订单

```
1. python meal.py evaluate              # 列出所有待评价订单（pendingEvaluations）
2. 展示给用户：orderId、goodName、storeName、sendDate
3. 询问用户三个维度的评分（总体/口味/份量）和评价内容
4. python meal.py evaluate --order-id <id> --zt-star <1-5> --taste-star <1-5> --fl-star <1-5> --content "xxx"
5. 解析返回的 success 字段，告知用户结果
```

**评价三个维度说明（均 1-5 星，默认 5）**：
- `--zt-star`：**总体**评分
- `--taste-star`：**口味**评分
- `--fl-star`：**份量**评分
- `--content`：文字评论（可选）

**注意**：
- 只有 `hasEvaluate=true` 且 `evaluateStar=0` 的订单才可评价
- 重复评价接口会返回 `"请勿重复评价"`

### 场景4：查询并切换取餐地点

```
1. python meal.py position                              # 获取地点列表
2. 解析返回的地点列表，让用户选择
3. python meal.py bind-position --position-id <id>     # 绑定选中地点
4. 解析返回结果，告知用户绑定是否成功
```

## 配置说明

配置文件位于 skill 目录下的 `.meal_config.json`，由 CLI 自动管理。

**获取 code 的方式：**

- 方式1（自动，优先）：使用 browser 工具（**沙箱浏览器，不需要 profile=user**）打开 `https://xz.xiaohongshu.com/muse-redcity`，等页面加载完成后，用 `evaluate` action 执行 `() => document.cookie` 读取 Cookie，提取其中的 `code=` 字段值。该网站会携带 SSO session 自动登录，沙箱浏览器通常已有缓存 session 可直接使用。
- 方式2（手动）：请用户提供 SSO code

**配置命令：**
```bash
python meal.py config --code <your_sso_code>
```

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 未配置认证 | 提示运行 `python meal.py config --code xxx` |
| `code` 过期（401/403） | 提示重新配置 |
| 网络错误（含 `error` 字段） | 提示检查网络，可重试一次 |
| `success: false` | 读取 `result` 字段获取具体失败原因 |

## 实现说明

CLI 工具路径：`cli/meal.py`

所有命令的成功/失败判断：
- 返回 JSON 中包含 `"error"` 字段 → 失败
- `code` 字段为 `"500"/"400"/"401"/"403"` → 失败
- `book` 命令额外有顶层 `"success": false` 字段
