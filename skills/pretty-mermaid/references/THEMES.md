# 配色方案参考

基于小红书品牌色系设计的 4 套 Mermaid 配色方案。所有色值均通过 Mermaid `%%{init}%%` 指令和 `classDef` 内联应用。

---

## 品牌色基底

小红书品牌核心色：

| 色名 | 色值 | 用途 |
|------|------|------|
| 薯红 | `#FF2442` | 品牌主色，Logo 红 |
| 深红 | `#CC1D35` | 主色加深，边框/按压态 |
| 暖橙 | `#FF6B35` | 活力辅助色 |
| 柔粉 | `#FFE0E6` | 浅色背景/轻量填充 |
| 极浅粉 | `#FFF5F7` | 最浅底色 |
| 深灰 | `#2D2D2D` | 正文文字 |

---

## 方案一：薯红经典（redbook-classic）⭐ 默认

温暖、专业、辨识度高。适合绝大多数场景。

### 色板

| 角色 | 色值 | 预览 | 说明 |
|------|------|------|------|
| primary fill | `#FF2442` | 🟥 | 关键节点填充 |
| primary border | `#CC1D35` | 🟥 | 关键节点边框 |
| primary text | `#FFFFFF` | ⬜ | 关键节点文字 |
| secondary fill | `#FFE0E6` | 🟫 | 辅助节点填充 |
| secondary border | `#FFB3C1` | 🟫 | 辅助节点边框 |
| secondary text | `#2D2D2D` | ⬛ | 辅助节点文字 |
| accent fill | `#FF6B35` | 🟧 | 强调/特殊节点填充 |
| accent border | `#CC5529` | 🟧 | 强调节点边框 |
| accent text | `#FFFFFF` | ⬜ | 强调节点文字 |
| neutral fill | `#FFF5F7` | ⬜ | 中性节点填充 |
| neutral border | `#E8E8E8` | ⬜ | 中性节点边框 |
| line | `#8C8C8C` | ⬜ | 连接线 |
| text | `#2D2D2D` | ⬛ | 正文文字 |

### %%{init}%% 配置

```
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#FF2442',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#CC1D35',
    'secondaryColor': '#FFE0E6',
    'secondaryTextColor': '#2D2D2D',
    'secondaryBorderColor': '#FFB3C1',
    'tertiaryColor': '#FFF5F7',
    'tertiaryTextColor': '#2D2D2D',
    'tertiaryBorderColor': '#FFD6DE',
    'lineColor': '#8C8C8C',
    'textColor': '#2D2D2D',
    'fontSize': '14px',
    'fontFamily': '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
  }
}}%%
```

### classDef 定义

```
classDef primary fill:#FF2442,stroke:#CC1D35,color:#FFFFFF,stroke-width:2px,rx:12,ry:12
classDef secondary fill:#FFE0E6,stroke:#FFB3C1,color:#2D2D2D,stroke-width:1.5px,rx:8,ry:8
classDef accent fill:#FF6B35,stroke:#CC5529,color:#FFFFFF,stroke-width:2px,rx:8,ry:8
classDef neutral fill:#FFF5F7,stroke:#E8E8E8,color:#2D2D2D,stroke-width:1px,rx:8,ry:8
classDef decision fill:#FFF5F7,stroke:#FF2442,color:#2D2D2D,stroke-width:2px
```

### 适用场景
- 通用文档和说明
- 产品流程图
- 日常技术图表
- 团队协作文档

---

## 方案二：玫瑰高级（rose-premium）

红棕与玫瑰色调的高级质感配色。

### 色板

| 角色 | 色值 | 说明 |
|------|------|------|
| primary fill | `#E8364F` | 玫瑰红节点 |
| primary border | `#B8293E` | 深玫瑰边框 |
| primary text | `#FFFFFF` | 白色文字 |
| secondary fill | `#F5E6D3` | 暖米色节点 |
| secondary border | `#D4B896` | 棕色边框 |
| secondary text | `#1A1A2E` | 深色文字 |
| accent fill | `#C67A5C` | 暖棕色节点 |
| accent border | `#A66248` | 深棕色边框 |
| accent text | `#FFFFFF` | 白色文字 |
| neutral fill | `#FBF7F4` | 极浅暖色 |
| neutral border | `#E0D5CC` | 浅棕边框 |
| line | `#9E8E82` | 暖灰连线 |
| text | `#1A1A2E` | 墨色文字 |

### %%{init}%% 配置

```
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#E8364F',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#B8293E',
    'secondaryColor': '#F5E6D3',
    'secondaryTextColor': '#1A1A2E',
    'secondaryBorderColor': '#D4B896',
    'tertiaryColor': '#FBF7F4',
    'tertiaryTextColor': '#1A1A2E',
    'lineColor': '#9E8E82',
    'textColor': '#1A1A2E',
    'fontSize': '14px',
    'fontFamily': '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
  }
}}%%
```

### classDef 定义

```
classDef primary fill:#E8364F,stroke:#B8293E,color:#FFFFFF,stroke-width:2px,rx:12,ry:12
classDef secondary fill:#F5E6D3,stroke:#D4B896,color:#1A1A2E,stroke-width:1.5px,rx:8,ry:8
classDef accent fill:#C67A5C,stroke:#A66248,color:#FFFFFF,stroke-width:2px,rx:8,ry:8
classDef neutral fill:#FBF7F4,stroke:#E0D5CC,color:#1A1A2E,stroke-width:1px,rx:8,ry:8
```

### 适用场景
- 商务报告和演示
- 正式项目文档
- 客户交付文档
- 高端产品方案

---

## 方案三：珊瑚活力（coral-vibrant）

明亮活泼，充满活力。

### 色板

| 角色 | 色值 | 说明 |
|------|------|------|
| primary fill | `#FF4757` | 珊瑚红 |
| primary border | `#E63E4D` | 深珊瑚 |
| primary text | `#FFFFFF` | 白色文字 |
| secondary fill | `#FFF1F2` | 浅珊瑚底 |
| secondary border | `#FFB3B8` | 浅红边框 |
| secondary text | `#2F3542` | 深灰文字 |
| accent fill | `#FFA502` | 活力橙 |
| accent border | `#CC8402` | 深橙边框 |
| accent text | `#FFFFFF` | 白色文字 |
| highlight fill | `#E8F8F5` | 薄荷绿 |
| highlight border | `#A3D9D0` | 绿色边框 |
| line | `#747D8C` | 中灰连线 |
| text | `#2F3542` | 深灰文字 |

### %%{init}%% 配置

```
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#FF4757',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#E63E4D',
    'secondaryColor': '#FFF1F2',
    'secondaryTextColor': '#2F3542',
    'secondaryBorderColor': '#FFB3B8',
    'tertiaryColor': '#E8F8F5',
    'tertiaryTextColor': '#2F3542',
    'lineColor': '#747D8C',
    'textColor': '#2F3542',
    'fontSize': '14px',
    'fontFamily': '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
  }
}}%%
```

### classDef 定义

```
classDef primary fill:#FF4757,stroke:#E63E4D,color:#FFFFFF,stroke-width:2px,rx:12,ry:12
classDef secondary fill:#FFF1F2,stroke:#FFB3B8,color:#2F3542,stroke-width:1.5px,rx:8,ry:8
classDef accent fill:#FFA502,stroke:#CC8402,color:#FFFFFF,stroke-width:2px,rx:8,ry:8
classDef highlight fill:#E8F8F5,stroke:#A3D9D0,color:#2F3542,stroke-width:1.5px,rx:8,ry:8
```

### 适用场景
- 产品演示和原型
- 创意型流程图
- 用户旅程图
- 营销相关图表

---

## 方案四：深红暗夜（dark-crimson）

暗色模式，适合深色界面和技术文档。

### 色板

| 角色 | 色值 | 说明 |
|------|------|------|
| primary fill | `#FF2442` | 品牌红（暗底上更醒目） |
| primary border | `#A61D30` | 暗红边框 |
| primary text | `#FFFFFF` | 白色文字 |
| secondary fill | `#2A1F2D` | 深紫灰节点 |
| secondary border | `#4A3F50` | 暗色边框 |
| secondary text | `#F0E6F0` | 浅色文字 |
| accent fill | `#D4603A` | 暗橙色 |
| accent border | `#A64D2E` | 深橙边框 |
| accent text | `#FFFFFF` | 白色文字 |
| surface fill | `#231E26` | 暗面色 |
| surface border | `#3A3340` | 暗边框 |
| background | `#1A1520` | 极深背景 |
| line | `#6B5B73` | 暗紫灰连线 |
| text | `#F0E6F0` | 浅色文字 |

### %%{init}%% 配置

```
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#2A1F2D',
    'primaryTextColor': '#F0E6F0',
    'primaryBorderColor': '#4A3F50',
    'secondaryColor': '#231E26',
    'secondaryTextColor': '#F0E6F0',
    'tertiaryColor': '#1A1520',
    'lineColor': '#6B5B73',
    'textColor': '#F0E6F0',
    'mainBkg': '#1A1520',
    'fontSize': '14px',
    'fontFamily': '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
  }
}}%%
```

### classDef 定义

```
classDef primary fill:#FF2442,stroke:#A61D30,color:#FFFFFF,stroke-width:2px,rx:12,ry:12
classDef secondary fill:#2A1F2D,stroke:#4A3F50,color:#F0E6F0,stroke-width:1.5px,rx:8,ry:8
classDef accent fill:#D4603A,stroke:#A64D2E,color:#FFFFFF,stroke-width:2px,rx:8,ry:8
classDef surface fill:#231E26,stroke:#3A3340,color:#F0E6F0,stroke-width:1px,rx:8,ry:8
```

### 适用场景
- 技术架构图
- 开发者文档
- 深色模式 IDE/文档
- 系统监控面板

---

## 按场景选择方案

```
需要什么风格？
├── 通用 / 默认 → 薯红经典 ⭐
├── 正式 / 商务 → 玫瑰高级
├── 活泼 / 创意 → 珊瑚活力
└── 深色 / 技术 → 深红暗夜
```

---

## 时序图专用变量

时序图有额外的主题变量可以控制参与者、激活块、备注等样式：

```
'actorBkg': '#FF2442',           // 参与者背景
'actorTextColor': '#FFFFFF',     // 参与者文字
'actorBorder': '#CC1D35',        // 参与者边框
'activationBkgColor': '#FFE0E6', // 激活块背景
'activationBorderColor': '#FF2442', // 激活块边框
'signalColor': '#2D2D2D',       // 消息线颜色
'noteBkgColor': '#FFF5F7',      // 备注背景
'noteBorderColor': '#FFB3C1',   // 备注边框
'noteTextColor': '#2D2D2D',     // 备注文字
```

---

## 自定义配色

如果内置方案不满足需求，可以基于品牌色自定义：

### 最小自定义
只需修改 `primaryColor` 和 `lineColor` 即可获得不错的效果：

```
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#FF2442',
    'lineColor': '#8C8C8C'
  }
}}%%
```

### 配色原则
1. **主色**：使用 `#FF2442` 或其衍生色保持品牌一致性
2. **对比度**：深色填充配白色文字，浅色填充配深色文字
3. **层次**：最重要的节点用最醒目的颜色，次要节点用浅色
4. **连线**：使用中性灰色（`#8C8C8C`），不与节点争注意力
5. **一致性**：同一张图中的同类节点使用相同样式
