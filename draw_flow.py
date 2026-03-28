from PIL import Image, ImageDraw, ImageFont
import os

W, H = 2000, 820
img = Image.new("RGB", (W, H), "#F5F7FA")
draw = ImageDraw.Draw(img)

def get_font(size):
    for path in [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    return ImageFont.load_default()

font_title = get_font(28)
font_step  = get_font(19)
font_sub   = get_font(14)

# ---- 标题 ----
draw.text((W//2, 36), "P0/P1 告警智能诊断 — 完整处理流程", font=font_title, fill="#1A2B4A", anchor="mm")

# ---- 节点定义 ----
nodes = [
    {
        "title": "告警触发",
        "subs": ["P0/P1 告警触发"],
        "color": "#E74C3C", "bg": "#FDEDEC",
    },
    {
        "title": "智能降噪",
        "subs": ["重复告警?", "已恢复?", "低优先级?"],
        "color": "#E67E22", "bg": "#FEF5EC",
        "branch_down": "是 → 自动关闭/降优先级",
        "branch_label": "否",
    },
    {
        "title": "多Agent\n并行诊断",
        "subs": ["Metrics Agent", "Logs Agent", "Change Agent", "Topology Agent"],
        "color": "#2980B9", "bg": "#EAF4FB",
        "badge": "2-3 分钟",
    },
    {
        "title": "根因综合判定",
        "subs": ["汇总诊断结果", "生成根因报告", "推荐修复方案"],
        "color": "#8E44AD", "bg": "#F5EEF8",
    },
    {
        "title": "结构化诊断报告",
        "subs": ["根因判定 75%+", "影响面分析", "修复建议", "相关上下文"],
        "color": "#27AE60", "bg": "#EAFAF1",
    },
    {
        "title": "智能处置",
        "subs": ["低风险: 自动执行", "高风险: 人工确认", "复杂: SRE 介入"],
        "color": "#16A085", "bg": "#E8F8F5",
        "branch_down_multi": [
            ("低风险: 自动执行", "#27AE60", "#EAFAF1"),
            ("高风险: 人工确认", "#E67E22", "#FEF5EC"),
            ("复杂: SRE 介入",  "#E74C3C", "#FDEDEC"),
        ],
    },
    {
        "title": "复盘优化",
        "subs": ["事件时间线", "沉淀诊断知识", "优化Agent模型"],
        "color": "#7F8C8D", "bg": "#F2F3F4",
    },
]

n = len(nodes)
box_w  = 200
box_h  = 200   # 足够高，容纳所有子项
gap_x  = 44
total_w = n * box_w + (n - 1) * gap_x
off_x  = (W - total_w) // 2
main_y = 90    # 主流程顶部 y

def draw_node(x, y, w, h, node):
    # 背景
    draw.rounded_rectangle([x, y, x+w, y+h], radius=12,
                            fill=node["bg"], outline=node["color"], width=3)
    # 顶部色条（高度 38）
    draw.rounded_rectangle([x, y, x+w, y+38], radius=12, fill=node["color"])
    draw.rectangle([x, y+26, x+w, y+38], fill=node["color"])
    # 标题
    draw.text((x+w//2, y+19), node["title"], font=font_step,
              fill="white", anchor="mm")
    # 分割线
    draw.line([(x+12, y+42), (x+w-12, y+42)], fill=node["color"], width=1)

    # 子条目 — 均匀分布在剩余高度内
    subs = node["subs"]
    content_h = h - 50   # 顶部色条 38 + 分割线 4 + padding 8
    line_h = content_h // (len(subs) + 1)
    for i, s in enumerate(subs):
        sy = y + 50 + (i + 0) * line_h + line_h // 2
        draw.text((x+w//2, sy), s, font=font_sub, fill=node["color"], anchor="mm")

    # badge（如 "2-3 分钟"）
    if "badge" in node:
        bw, bh = 88, 22
        bx = x + w//2 - bw//2
        by = y + h - bh - 6
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=6,
                                fill=node["color"])
        draw.text((x+w//2, by+bh//2), node["badge"], font=font_sub,
                  fill="white", anchor="mm")

def draw_arrow(x1, y, x2, color):
    draw.line([(x1, y), (x2-10, y)], fill=color, width=3)
    draw.polygon([(x2-10, y-7), (x2, y), (x2-10, y+7)], fill=color)

# ---- 绘制主流程 ----
for i, node in enumerate(nodes):
    x = off_x + i * (box_w + gap_x)
    draw_node(x, main_y, box_w, box_h, node)

    # 主流程箭头
    if i < n - 1:
        ax1 = x + box_w
        ax2 = x + box_w + gap_x
        ay  = main_y + box_h // 2
        next_color = nodes[i+1]["color"]
        draw_arrow(ax1, ay, ax2, next_color)

        # 降噪节点 "否" 标签
        if "branch_label" in node:
            draw.text(((ax1+ax2)//2, ay - 14), node["branch_label"],
                      font=font_sub, fill=node["color"], anchor="mm")

# ---- 降噪分支（向下）----
branch_idx = 1
bx = off_x + branch_idx * (box_w + gap_x)
bcx = bx + box_w // 2
by_bot = main_y + box_h
branch_y = by_bot + 52
bbox_w, bbox_h = 190, 38

draw.line([(bcx, by_bot+2), (bcx, branch_y)], fill="#E67E22", width=2)
draw.rounded_rectangle(
    [bcx - bbox_w//2, branch_y, bcx + bbox_w//2, branch_y + bbox_h],
    radius=8, fill="#FDEBD0", outline="#E67E22", width=2)
draw.text((bcx, branch_y + bbox_h//2), "是 → 自动关闭 / 降优先级",
          font=font_sub, fill="#9D4E0A", anchor="mm")

# ---- 智能处置分支（向下）----
proc_idx = 5
px = off_x + proc_idx * (box_w + gap_x)
pcx = px + box_w // 2
py_bot = main_y + box_h
proc_branch_y = py_bot + 52

sub_boxes = nodes[proc_idx]["branch_down_multi"]
sub_w, sub_h = 162, 38
gap_sb = 12
total_sb = len(sub_boxes) * sub_w + (len(sub_boxes)-1) * gap_sb
sb_start_x = pcx - total_sb // 2

# 竖线 + 横线
draw.line([(pcx, py_bot+2), (pcx, proc_branch_y - 10)], fill="#16A085", width=2)
draw.line([(sb_start_x + sub_w//2, proc_branch_y - 10),
           (sb_start_x + (len(sub_boxes)-1)*(sub_w+gap_sb) + sub_w//2, proc_branch_y - 10)],
          fill="#16A085", width=2)

for k, (label, col, bg) in enumerate(sub_boxes):
    sx = sb_start_x + k * (sub_w + gap_sb)
    scx = sx + sub_w // 2
    draw.line([(scx, proc_branch_y - 10), (scx, proc_branch_y)], fill=col, width=2)
    draw.rounded_rectangle([sx, proc_branch_y, sx+sub_w, proc_branch_y+sub_h],
                            radius=8, fill=bg, outline=col, width=2)
    draw.text((scx, proc_branch_y + sub_h//2), label,
              font=font_sub, fill=col, anchor="mm")

# ---- 底部说明 ----
draw.text((W//2, H - 24),
          "目标：10 分钟内完成诊断并给出修复建议  |  根因定位准确率 75%+  |  MTTR ↓ 50%",
          font=font_sub, fill="#999", anchor="mm")

out = "/home/node/.openclaw/workspace/xpilot_flow.png"
img.save(out)
print(f"saved: {out}")
