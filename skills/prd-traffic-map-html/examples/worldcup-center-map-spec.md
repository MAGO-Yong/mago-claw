# 26 世界杯中心页流量地图示例 Spec

Source REDoc:

- `https://docs.xiaohongshu.com/doc/a9150c0b65f863943f937552f2db1657`
- Title: `【重开版PRD】26世界杯-中心页`

Generated HTML:

- `/Users/mahengyang/Documents/Codex CLI/CC-generate/worldcup-center-flow-map.html`

## V1 Baseline Contract

This file and `templates/worldcup-center-flow-map.html` are the V1 baseline for future collaboration.

Anyone continuing the World Cup traffic map should:

1. start from the V1 HTML, not from a blank diagram;
2. preserve the current PRD-backed entry, hierarchy, node choices, evidence drawer content, and layout rules unless a later PRD/user correction supersedes them;
3. apply new feedback as incremental edits to the node set, edges, layout, or drawer evidence;
4. update this spec when a new correction becomes a reusable modeling rule;
5. rerun static validation after every meaningful edit.

The baseline is not "final truth"; it is the current shared working version.

## PRD Conclusions

中心页定位：

- 围绕直播、赛事搭建内容分发中心场。
- 预热期通过预约直播抽大奖和裂变回流打声量。
- 正式期通过顶部直播信息流大卡牵引用户进入直播间观赛、聊球。

入口判断：

- PRD 明确写“不上发现子频道，直接上顶 Tab”。
- 因此地图入口应为：`用户进入小红书 App -> 世界杯 Tab -> 世界杯中心页/主会场`。
- `Home Feed` 不应作为和世界杯 Tab 并列的初始入口。文档里的 `feed流` 更像中心页模块/内容消费，`Mainfeed推流` 更像预约成功后的触达。

架构判断：

- 预热期和正式期的中心页架构基本一致。
- 只有顶部阶段区随阶段切换：预热态顶部区 / 正式态顶部区。
- 其他功能模块作为主会场平级节点展示，不单独抽象成“通用固定能力区”。

## Current Node Hierarchy

```text
用户进入小红书 App
└── 世界杯 Tab
    └── 世界杯中心页/主会场
        ├── 顶部阶段区
        │   ├── 预热态顶部区
        │   │   ├── 预约直播抽奖卡
        │   │   ├── 预约挂件
        │   │   └── 预约抽奖玩法
        │   │       └── 立即抽奖
        │   │           ├── 晒一晒
        │   │           └── 邀好友预约
        │   │               └── 分享海报
        │   └── 正式态顶部区
        │       └── 直播信息流大卡
        │           ├── 直播卡预约按钮
        │           ├── 直播间
        │           ├── 赛程页入口
        │           └── 回放页入口
        ├── 活动背包
        ├── 我的主队
        ├── 页面分享
        ├── 4 个金刚位
        │   ├── 赛程数据
        │   ├── 有奖竞猜
        │   ├── 金球兑换
        │   └── 一起聊球
        └── 动态内容楼层
            ├── 比赛看点
            │   └── 笔记详情页
            ├── 大家都在发
            │   └── 发布模板/发布器
            ├── 热门球迷圈
            │   └── 圈子详情/聚合页
            └── 赛事热点
                └── 搜索结果页
```

## Important Modeling Decisions

- `赛事直播` / `运营自制直播` / `运营类笔记` are material types inside `直播信息流大卡`, not independent map nodes.
- `直播卡预约按钮` is a formal-period live card state/path, not the preheat lottery reservation.
- `赛事预约入口` should not be duplicated under preheat unless PRD shows a separate visible entry.
- `赛程页入口` comes from the match-info hot area after live starts.
- `回放页入口` comes from the live card button state `查看回放`.
- `活动规则` is too granular for this traffic map and was removed.
- `比赛看点`, `大家都在发`, `热门球迷圈`, and `赛事热点` are the same layer under dynamic content floor.
- The next drilldown layer is `笔记详情页`, `发布模板/发布器`, `圈子详情/聚合页`, and `搜索结果页`.

## Collaboration Corrections To Preserve

These are the product/layout corrections made during the drawing process. Apply the same principles when continuing this map or drawing a similar PRD map.

1. **Remove non-entry routes from the top**
   - Initial draft had `小红书 App -> 世界杯 Tab / Home Feed`.
   - PRD evidence showed the real top entry is `小红书 App -> 世界杯 Tab -> 世界杯中心页/主会场`.
   - `Home Feed` was removed from nodes, details, and edges.

2. **Do not show interaction states as topology nodes**
   - `Push 授权`, `中断路径`, and similar action/state nodes made the map noisy.
   - Keep them in drawer evidence if they explain conversion or success conditions.

3. **Merge duplicate venue labels**
   - `世界杯中心页` and `世界杯主会场` were treated as one node: `世界杯中心页/主会场`.

4. **Only the top phase area changes**
   - The user clarified that preheat/formal differences are concentrated in the top area.
   - Stable modules should be peer nodes under the main venue, not duplicated into preheat/formal rows.

5. **Avoid abstract fixed-area grouping**
   - `通用固定能力` as a container made the map less clear.
   - Show `活动背包`, `我的主队`, `页面分享`, `4 个金刚位`, and `动态内容楼层` as peer modules.

6. **One logical layer equals one visual row**
   - Same-level nodes must stay on one row even when the canvas gets wider.
   - Do not wrap same-level nodes into two rows or let one child node appear in a parent row.

7. **Put real children one layer lower**
   - `分享海报` belongs under `邀好友预约`.
   - `搜索结果页` belongs under `赛事热点`.
   - `笔记详情页`, `发布模板/发布器`, `圈子详情/聚合页`, and `搜索结果页` are a drilldown row under the four content-floor modules.

8. **Use evidence drawer, not dense node text**
   - Product screenshots and PRD descriptions moved into the right drawer.
   - Drawer appears only on hover; no drawer when cursor is not over a node.

9. **Validate with real card height**
   - A bug appeared when `邀好友预约` and `分享海报` visually stuck together.
   - The validation heuristic was updated to use a card height closer to the rendered card including `依据` text.

10. **Question screenshots against PRD source**
   - When a screenshot or node felt questionable, the fix was to re-open the relevant PRD section and adjust the model, not rely on the current diagram.

## Evidence Images Used

Architecture:

- Preheat architecture: `https://xhs-doc.xhscdn.com/104004dg320jofddmmo0ehehlnc?redoc-w=1179&redoc-h=8265&redoc-key=104004dg320jofddmmo0ehehlnc`
- Formal architecture: `https://xhs-doc.xhscdn.com/104004dg320joftgrli0a5s5a18?redoc-w=1179&redoc-h=9453&redoc-key=104004dg320joftgrli0a5s5a18`

Preheat:

- Reservation flow/card: `https://xhs-doc.xhscdn.com/104004dg320jnmmqplk0adk6o9o?redoc-w=674&redoc-h=1438&redoc-key=104004dg320jnmmqplk0adk6o9o`
- Reservation card: `https://xhs-doc.xhscdn.com/104004dg320hem4br5k0bv2qljo?redoc-w=698&redoc-h=1454&redoc-key=104004dg320hem4br5k0bv2qljo`
- Reservation widget: `https://xhs-doc.xhscdn.com/104004dg320juuo53li0538p338?redoc-w=698&redoc-h=1460&redoc-key=104004dg320juuo53li0538p338`
- Draw popup: `https://xhs-doc.xhscdn.com/104004dg320hhsvmv6o0cstmo74?redoc-w=548&redoc-h=1170&redoc-key=104004dg320hhsvmv6o0cstmo74`
- Invite list: `https://xhs-doc.xhscdn.com/104004dg320hi6hkq5k01goc8tg?redoc-w=1512&redoc-h=1532&redoc-key=104004dg320hi6hkq5k01goc8tg`

Formal live:

- Live info card: `https://xhs-doc.xhscdn.com/104004dg320jqbnr96o03r9jjq0?redoc-w=870&redoc-h=1246&redoc-key=104004dg320jqbnr96o03r9jjq0`
- Live card hot area: `https://xhs-doc.xhscdn.com/104004dg320j881nale08dtg5q8?redoc-w=124&redoc-h=76&redoc-key=104004dg320j881nale08dtg5q8`

Content floor:

- Match highlights: `https://xhs-doc.xhscdn.com/104004dg320j252rg5k0fbsu5hk?redoc-w=594&redoc-h=454&redoc-key=104004dg320j252rg5k0fbsu5hk`
- Event hot: `https://xhs-doc.xhscdn.com/104004dg320ju7g9alc05dkr9j0?redoc-w=1102&redoc-h=676&redoc-key=104004dg320ju7g9alc05dkr9j0`
- Publish template: `https://xhs-doc.xhscdn.com/104004dg320ju3iqi5i08maqgos?redoc-w=1158&redoc-h=946&redoc-key=104004dg320ju3iqi5i08maqgos`
- 4 king slots: `https://xhs-doc.xhscdn.com/104004dg320jt0iqkmo00b4jj84?redoc-w=1188&redoc-h=810&redoc-key=104004dg320jt0iqkmo00b4jj84`

## Latest Validation

Latest known static validation after entry correction and spacing fix:

```json
{
  "nodes": 35,
  "edges": 35,
  "hasFeedNode": false,
  "missingDetails": [],
  "extraDetails": [],
  "overlaps": [],
  "missingEdgeNodes": []
}
```
