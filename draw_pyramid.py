from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1300, 900
img = Image.new("RGB", (W, H), "#F5F7FA")
draw = ImageDraw.Draw(img)

def get_font(size, bold=False):
    for path in [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    return ImageFont.load_default()

font_title    = get_font(28, bold=True)
font_tier_tag = get_font(13)
font_card_top = get_font(14, bold=True)
font_value    = get_font(26, bold=True)
font_bench_lbl= get_font(12)
font_bench_val= get_font(13, bold=True)
font_bottom   = get_font(12)

# ---- 标题 ----
draw.text((W//2, 36), "XPILOT 告警智能诊断 — 指标体系与业界对标", font=font_title, fill="#1A2B4A", anchor="mm")

# ---- 金字塔几何 ----
apex_x      = W // 2
apex_y      = 82
base_y      = 680
base_half_w = 470

total_h = base_y - apex_y
y1 = apex_y + int(total_h * 0.27)
y2 = apex_y + int(total_h * 0.56)

def tri_x(y):
    t = (y - apex_y) / (base_y - apex_y)
    hw = base_half_w * t
    return apex_x - hw, apex_x + hw

colors_fill   = ["#E8604C", "#F0933A", "#3A8DC4"]
colors_border = ["#C0392B", "#D35400", "#1F6FA0"]
tier_ys = [(apex_y, y1), (y1, y2), (y2, base_y)]

for i, (yt, yb) in enumerate(tier_ys):
    xl_top, xr_top = tri_x(yt)
    xl_bot, xr_bot = tri_x(yb)
    pts = [(apex_x, yt), (xr_bot, yb), (xl_bot, yb)] if i == 0 \
          else [(xl_top, yt), (xr_top, yt), (xr_bot, yb), (xl_bot, yb)]
    draw.polygon(pts, fill=colors_fill[i])
    draw.polygon(pts, outline=colors_border[i], width=2)

for yt, _ in [(y1, y1), (y2, y2)]:
    xl, xr = tri_x(yt)
    draw.line([(xl, yt), (xr, yt)], fill="white", width=2)

tier_labels = ["北极星指标", "过程指标", "支撑指标"]
for i, (yt, yb) in enumerate(tier_ys):
    cy = (yt + yb) // 2
    xl, _ = tri_x(cy)
    tx = xl - 16
    draw.line([(tx+6, yt+6), (tx+6, yb-6)], fill=colors_border[i], width=2)
    draw.text((tx, cy), tier_labels[i], font=font_tier_tag,
              fill=colors_border[i], anchor="rm")

# ---- 卡片：指标名 + 目标值 + 业界对标小条 ----
def draw_card(cx, cy, title, value, benches, border_col, w=240, h=158):
    """
    benches: [(company, val), ...]  显示在卡片下半部分
    """
    x0, y0 = cx - w//2, cy - h//2

    # 白底卡片
    draw.rounded_rectangle([x0, y0, x0+w, y0+h],
                            radius=10, fill="white", outline=border_col, width=2)
    # 顶部色条
    draw.rounded_rectangle([x0, y0, x0+w, y0+30], radius=10, fill=border_col)
    draw.rectangle([x0, y0+18, x0+w, y0+30], fill=border_col)
    draw.text((cx, y0+15), title, font=font_card_top, fill="white", anchor="mm")

    # 目标值
    draw.text((cx, y0+56), value, font=font_value, fill=border_col, anchor="mm")

    # 分割线
    draw.line([(x0+12, y0+78), (x0+w-12, y0+78)], fill="#EEE", width=1)

    # 业界对标：每个占一列
    n = len(benches)
    col_w = (w - 16) // n
    for k, (company, bval) in enumerate(benches):
        bx = x0 + 8 + k * col_w + col_w // 2
        draw.text((bx, y0+92),  company, font=font_bench_lbl, fill="#999",       anchor="mm")
        draw.text((bx, y0+112), bval,    font=font_bench_val, fill=border_col,   anchor="mm")

    # 底部"业界标杆"标签
    draw.text((cx, y0+h-12), "业界标杆", font=font_bench_lbl, fill="#BBB", anchor="mm")


# ---- L1 北极星 ----
cy1 = (apex_y + y1) // 2
draw_card(apex_x, cy1,
    title="告警排障时间缩短率（MTTR）",
    value="目标 50%",
    benches=[("Metoro","81%"), ("Meta","50%"), ("字节","40%")],
    border_col="#C0392B",
    w=290, h=155,
)

# ---- L2 过程指标 ----
cy2 = (y1 + y2) // 2
draw_card(apex_x - 210, cy2,
    title="根因定位准确率",
    value="目标 75%",
    benches=[("Meta","80%+"), ("字节","75%+"), ("Dynatrace","85%+")],
    border_col="#D35400",
    w=250, h=155,
)
draw_card(apex_x + 210, cy2,
    title="告警降噪率",
    value="目标 70%",
    benches=[("BigPanda","95%"), ("字节","70%+"), ("PagerDuty","60%")],
    border_col="#D35400",
    w=250, h=155,
)

# ---- L3 支撑指标 ----
cy3 = (y2 + base_y) // 2
draw_card(apex_x - 330, cy3,
    title="P2+ 告警覆盖率",
    value="目标 80%",
    benches=[("Dynatrace","90%+"), ("PagerDuty","70%+")],
    border_col="#1F6FA0",
    w=240, h=155,
)
draw_card(apex_x, cy3,
    title="排障 Skill 数",
    value="目标 50+",
    benches=[("Datadog","500+"), ("字节","100+")],
    border_col="#1F6FA0",
    w=240, h=155,
)
draw_card(apex_x + 330, cy3,
    title="Skill WAU",
    value="待定 XX",
    benches=[("行业均值","TBD"), ("内部基线","TBD")],
    border_col="#1F6FA0",
    w=240, h=155,
)

# ---- 底部说明 ----
draw.text((W//2, H - 26),
          "卡片下方为业界标杆参考值  |  北极星 → 过程指标 → 支撑指标，逐层支撑，形成完整度量闭环",
          font=font_bottom, fill="#999", anchor="mm")

out = "/home/node/.openclaw/workspace/xpilot_pyramid.png"
img.save(out)
print(f"saved: {out}")
