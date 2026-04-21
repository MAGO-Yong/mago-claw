# Meal Order CLI 使用指南

本文档介绍如何使用 meal-order CLI 工具完成订餐操作。

## 快速开始

### 1. 配置认证信息

首次使用前，需要配置认证码（code）：

```bash
python meal.py config --code <your_code>
```

**获取 code 的方法：**
1. 在浏览器中访问 `https://xz.xiaohongshu.com/muse-redcity`
2. 按 F12 打开开发者工具 → Application → Cookies
3. 找到 `code` 字段的值
4. 复制并执行上述命令

### 2. 查看今日菜单

```bash
python meal.py reserve
```

### 3. 一键订餐

```bash
python meal.py book --goods <商品ID> --date <日期> --store <商户ID>
```

示例：
```bash
python meal.py book --goods 1029893 --date 2026-03-13 --store 12610 --interval 2
```

## 命令参考

### config - 配置认证信息

```bash
python meal.py config --code <your_code>
```

**参数：**
- `--code`: 用户认证码（必需）
- `--client-type`: 客户端类型（可选，默认 sso）
- `--jsessionid`: JSESSIONID（可选）

**示例：**
```bash
python meal.py config --code xxxxx
```

---

### reserve - 查询可预订商户

查询今日可预订的商户和菜品列表。

```bash
python meal.py reserve [选项]
```

**参数：**
- `--date`: 使用日期（YYYY-MM-DD，可选，默认今天）
- `--interval`: 时段编号（2=午餐，3=晚餐，可选）
- `--all`: 查询午餐和晚餐两个时段（默认行为）
- `--raw`: 输出原始 JSON 格式

**示例：**

```bash
# 查询午餐和晚餐（默认）
python meal.py reserve

# 只查询午餐
python meal.py reserve --interval 2

# 只查询晚餐
python meal.py reserve --interval 3

# 查询明天的菜单
python meal.py reserve --date 2026-03-14
```

**输出示例：**
```
📅 2026-03-13 供应商列表

共 15 家商户

【左庭右院(大悦城)】store_id=11534
--------------------------------------------------------------------------------
商品ID       商品名称                         价格     时段       评分     月售
--------------------------------------------------------------------------------
1023395    原汤鲜牛肉捞烫杯套餐B                  ¥30   午餐       4.0    12
1023396    鲜牛肉捞烫杯套餐C                    ¥30   午餐       4.6    5
```

---

### guide - 获取订餐指引

查看指定日期的订餐状态和当前订单。

```bash
python meal.py guide [选项]
```

**参数：**
- `--date`: 使用日期（YYYY-MM-DD，可选，默认今天）
- `--raw`: 输出原始 JSON 格式

**示例：**

```bash
# 查看今天
python meal.py guide

# 查看指定日期
python meal.py guide --date 2026-03-12
```

**输出示例：**
```
📋 2026-03-13 订餐状态

======================================================================

🍱 午餐
----------------------------------------------------------------------
  菜品: 烤鸡腿肉烤熟谷物能量碗
  订单号: 210377211
  取餐柜: A06
  取餐时间: 12:00:00
  状态: 📦 已送达
  订餐状态: 已结束

🍱 晚餐
----------------------------------------------------------------------
  菜品: 便携式阿克苏苹果一箱
  订单号: 210337932
  取餐柜: 039
  取餐时间: 18:00:00
  状态: 🚚 配送中
  订餐状态: 已结束

======================================================================
```

---

### book - 一键订餐

确认订单并完成支付（最常用命令）。

```bash
python meal.py book --goods <商品ID> --date <日期> --store <商户ID> [选项]
```

**参数：**
- `--goods`: 商品ID（必需）
- `--date`: 使用日期（YYYY-MM-DD，必需）
- `--store`: 商户门店ID（必需）
- `--interval`: 时段编号（2=午餐，3=晚餐，默认 2）
- `--raw`: 输出原始 JSON 格式

**示例：**

```bash
# 订午餐
python meal.py book --goods 1029893 --date 2026-03-13 --store 12610 --interval 2

# 订晚餐
python meal.py book --goods 1070718 --date 2026-03-13 --store 13590 --interval 3
```

**输出示例：**
```
======================================================================
🍽️ 订餐结果
======================================================================
✅ 订单确认成功
✅ 支付成功
----------------------------------------------------------------------
  订单号: 210377211
  取餐码: A06
  取餐柜: A06
  取餐时间: 12:00:00
  商户: kpro
  菜品: 烤鸡腿肉烤熟谷物能量碗
======================================================================
```

---

### cancel - 取消订单

取消已预订的订单。

```bash
python meal.py cancel [选项]
```

**参数：**
- `--order-id`: 订单ID（可选，不指定则显示可取消订单列表）
- `--raw`: 输出原始 JSON 格式

**示例：**

```bash
# 查看可取消的订单列表
python meal.py cancel

# 取消指定订单
python meal.py cancel --order-id 210377211
```

**交互式取消示例：**
```
📋 您当前可以取消的订单:
  1. 午餐 - 烤鸡腿肉烤熟谷物能量碗 (订单号: 210377211) - 状态: 配送中
  2. 晚餐 - 便携式阿克苏苹果一箱 (订单号: 210337932) - 状态: 待配送

请使用 --order-id 参数指定要取消的订单
例如: python meal.py cancel --order-id 210377211
```

---

### history - 查询历史订单

查看最近 N 天的订餐历史记录。

```bash
python meal.py history [选项]
```

**参数：**
- `--days`: 查询最近多少天（可选，默认 7）
- `--raw`: 输出原始 JSON 格式

**示例：**

```bash
# 查询最近 7 天（默认）
python meal.py history

# 查询最近 14 天
python meal.py history --days 14
```

**输出示例：**
```
📜 历史订单记录 (共 8 条)

================================================================================

【1】订单号: 210337932
--------------------------------------------------------------------------------
  时段: 晚餐
  菜品: 便携式阿克苏苹果一箱
  用餐日期: 2026-03-13
  取餐柜: 039
  状态: 🚚 配送中

【2】订单号: 210377211
--------------------------------------------------------------------------------
  时段: 午餐
  菜品: 烤鸡腿肉烤熟谷物能量碗
  用餐日期: 2026-03-13
  取餐柜: A06
  状态: 📦 已送达

================================================================================
```

---

## 使用场景示例

### 场景 1：完整订餐流程

```bash
# 1. 配置认证（只需执行一次）
python meal.py config --code d544000a-01f0-4ec2-8a5f-fc8e9a6f4cd1

# 2. 查看今日菜单
python meal.py reserve

# 3. 选择菜品预订（假设选择了烤鸡腿肉能量碗）
python meal.py book --goods 1029893 --date 2026-03-13 --store 12610 --interval 2

# 4. 查看订餐状态
python meal.py guide
```

### 场景 2：取消并重新订餐

```bash
# 1. 查看当前订单
python meal.py guide

# 2. 取消指定订单
python meal.py cancel --order-id 210377211

# 3. 重新预订其他菜品
python meal.py book --goods 1025603 --date 2026-03-13 --store 12534 --interval 2
```

### 场景 3：批量查看历史记录

```bash
# 查看最近 30 天的订餐记录
python meal.py history --days 30
```

---

## 状态图标说明

| 图标 | 含义 |
|------|------|
| 🚚 | 配送中 |
| ✅ | 已完成 |
| ❌ | 已取消 |
| ⏳ | 待配送 |
| 📦 | 已送达 |

---

## 常见问题

### Q1: 提示"未配置认证信息"

**解决方法：**
```bash
python meal.py config --code <your_code>
```

### Q2: 如何获取商品ID和商户ID？

**解决方法：**
```bash
python meal.py reserve
```
查看输出中的 `商品ID` 和 `store_id`。

### Q3: code 过期了怎么办？

**解决方法：**
1. 重新访问 `https://xz.xiaohongshu.com/muse-redcity`
2. 从浏览器 Cookie 中获取新的 code
3. 执行 `python meal.py config --code <new_code>`

### Q4: 如何输出原始 JSON 数据？

**解决方法：**
所有命令都支持 `--raw` 参数：
```bash
python meal.py reserve --raw
python meal.py guide --raw
python meal.py book --goods xxx --date xxx --store xxx --raw
```

### Q5: 配置文件在哪里？

配置文件存储在当前工作目录下的 `.meal_config.json`：
```json
{
  "code": "your-auth-code",
  "client_type": "sso"
}
```

---

## 注意事项

1. **code 有效期**：code 会过期，如遇认证失败请重新获取
2. **订餐截止时间**：
   - 午餐截止：09:29
   - 晚餐截止：09:30
3. **配置文件**：`.meal_config.json` 存储在当前目录，不同目录需要重新配置
4. **依赖**：需要安装 Python 3 和 requests 库

---

## 完整命令速查表

| 命令 | 用途 | 示例 |
|------|------|------|
| `config` | 配置认证 | `python meal.py config --code xxx` |
| `reserve` | 查询菜单 | `python meal.py reserve` |
| `guide` | 查看状态 | `python meal.py guide` |
| `book` | 一键订餐 | `python meal.py book --goods xxx --date xxx --store xxx` |
| `cancel` | 取消订单 | `python meal.py cancel --order-id xxx` |
| `history` | 历史记录 | `python meal.py history --days 7` |
