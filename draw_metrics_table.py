from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1400, 620
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

font_title  = get_font(26, bold=True)
font_header = get_font(15, bold=True)
font_cell   = get_font(15)
font_target = get_font(20, bold=True)
font_bench  = get_font(13)
font_tag    = get_font(12)

# ---- 标题 ----
draw.text((W//2, 36), "XPILOT 告警智能诊断 — 北极星指标体系与业界对标", font=font_title, fill="#1A2B4A", anchor="mm")

# ---- 数据定义 ----
# rows: (层级, 指标名, 目标值, 目标颜色, [(公司, 数值, 颜色), ...])
STAR  = "#C0392B"
PROC  = "#D35400"
SUPP  = "#1F6FA0"
GREEN = "#27AE60"
GRAY  = "#7F8C8D"

rows = [
    ("北极星", "告警MTTR缩短率",   "50%",  STAR,
     [("Metoro","81%",GREEN), ("Meta","50%",GREEN), ("字节","40%",GREEN), ("PagerDuty","50%",GREEN)]),
    ("过程",   "根因定位准确率",   "75%+", PROC,
     [("Meta","80%+",PROC), ("字节","75%+",PROC), ("Dynatrace","85%+",PROC), ("—","—",GRAY)]),
    ("过程",   "告警降噪率",       "70%+", PROC,
     [("BigPanda","95%",PROC), ("PagerDuty","60%",PROC), ("字节","70%+",PROC), ("—","—",GRAY)]),
    ("支撑",   "P0/P1告警覆盖率",  "80%+", SUPP,
     [("Dynatrace","90%+",SUPP), ("PagerDuty","70%+",SUPP), ("—","—",GRAY), ("—","—",GRAY)]),
    ("支撑",   "排障Skill数",      "50+",  SUPP,
     [("Datadog","500+",SUPP), ("字节","100+",SUPP), ("—","—",GRAY), ("—","—",GRAY)]),
    ("体验",   "NPS评分",          "50+",  GRAY,
     [("Atera","55+",GREEN), ("Datadog","48",GREEN), ("—","—",GRAY), ("—","—",GRAY)]),
]

# ---- 布局 ----
margin_x = 48
table_x  = margin_x
table_y  = 72
table_w  = W - margin_x * 2

# 列宽设计
col_tier_w   = 80
col_name_w   = 190
col_target_w = 110
# 4个业界标杆列平分剩余
bench_count  = 4
bench_w      = (table_w - col_tier_w - col_name_w - col_target_w) // bench_count

row_h     = 68
header_h  = 42

bench_companies = ["Metoro", "Meta / Dynatrace", "字节跳动", "PagerDuty / BigPanda"]

# ---- 表头 ----
hdr_y = table_y
# 整体表头背景
draw.rounded_rectangle([table_x, hdr_y, table_x + table_w, hdr_y + header_h],
                        radius=10, fill="#1A2B4A")
draw.rectangle([table_x, hdr_y + 10, table_x + table_w, hdr_y + header_h], fill="#1A2B4A")

headers = ["层级", "指标名称", "XPILOT目标"]
col_widths = [col_tier_w, col_name_w, col_target_w]
cx = table_x
for i, (hdr, cw) in enumerate(zip(headers, col_widths)):
    draw.text((cx + cw//2, hdr_y + header_h//2), hdr,
              font=font_header, fill="white", anchor="mm")
    cx += cw

# 业界标杆大标题
bench_total_w = bench_count * bench_w
draw.text((cx + bench_total_w//2, hdr_y + 14), "业界标杆",
          font=font_header, fill="#FFD700", anchor="mm")
# 子列公司名
bench_labels = ["Metoro", "Meta / Dynatrace", "字节跳动", "PagerDuty / BigPanda"]
for k, bl in enumerate(bench_labels):
    bx = cx + k * bench_w + bench_w // 2
    draw.text((bx, hdr_y + 30), bl, font=font_tag, fill="#AAD4FF", anchor="mm")

# ---- 数据行 ----
# 层级颜色映射
tier_bg = {"北极星": "#FDEDEC", "过程": "#FEF5EC", "支撑": "#EAF4FB", "体验": "#F2F3F4"}
tier_col = {"北极星": STAR, "过程": PROC, "支撑": SUPP, "体验": GRAY}

prev_tier = None
for ri, (tier, name, target, tcol, benches) in enumerate(rows):
    ry = table_y + header_h + ri * row_h
    bg = tier_bg.get(tier, "#FFF")

    # 行背景
    is_last = (ri == len(rows) - 1)
    r = 10 if is_last else 0
    if is_last:
        draw.rounded_rectangle([table_x, ry, table_x + table_w, ry + row_h],
                                radius=10, fill=bg)
        draw.rectangle([table_x, ry, table_x + table_w, ry + row_h - 10], fill=bg)
    else:
        draw.rectangle([table_x, ry, table_x + table_w, ry + row_h], fill=bg)

    # 行下分割线
    draw.line([(table_x, ry + row_h), (table_x + table_w, ry + row_h)],
              fill="#DDD", width=1)

    cx = table_x

    # 层级标签（相同层级合并显示，仅第一次出现时画）
    if tier != prev_tier:
        col = tier_col[tier]
        lw, lh = 56, 26
        lx = cx + (col_tier_w - lw) // 2
        ly = ry + (row_h - lh) // 2
        draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=6, fill=col)
        draw.text((lx + lw//2, ly + lh//2), tier, font=font_tag, fill="white", anchor="mm")
    prev_tier = tier
    cx += col_tier_w

    # 指标名称
    draw.text((cx + col_name_w//2, ry + row_h//2), name,
              font=font_cell, fill="#333", anchor="mm")
    cx += col_name_w

    # 目标值（大字+颜色）
    draw.text((cx + col_target_w//2, ry + row_h//2), target,
              font=font_target, fill=tcol, anchor="mm")
    cx += col_target_w

    # 业界标杆值
    for k, (company, val, vcol) in enumerate(benches):
        bx = cx + k * bench_w + bench_w // 2
        # 有数据的标一个浅底色小标签
        if val != "—":
            tw_half = 38
            th = 22
            tx0 = bx - tw_half
            ty0 = ry + row_h//2 - th//2
            draw.rounded_rectangle([tx0, ty0, tx0+tw_half*2, ty0+th],
                                    radius=5, fill="#fff", outline=vcol, width=1)
            draw.text((bx, ry + row_h//2), val, font=font_bench, fill=vcol, anchor="mm")
        else:
            draw.text((bx, ry + row_h//2), "—", font=font_bench, fill="#CCC", anchor="mm")

# 表格外框
total_rows_h = header_h + len(rows) * row_h
draw.rounded_rectangle([table_x, table_y, table_x + table_w, table_y + total_rows_h],
                        radius=10, outline="#CCC", width=2)

# 列分割线（竖线）
vline_xs = [
    table_x + col_tier_w,
    table_x + col_tier_w + col_name_w,
    table_x + col_tier_w + col_name_w + col_target_w,
]
for k in range(1, bench_count):
    vline_xs.append(table_x + col_tier_w + col_name_w + col_target_w + k * bench_w)

for vx in vline_xs:
    draw.line([(vx, table_y), (vx, table_y + total_rows_h)], fill="#DDD", width=1)

# ---- 底部说明 ----
note_y = table_y + total_rows_h + 18
draw.text((W//2, note_y),
          "业界标杆数据来源：Metoro、Datadog、字节跳动、PagerDuty、BigPanda、Dynatrace 公开数据",
          font=font_tag, fill="#999", anchor="mm")

out = "/home/node/.openclaw/workspace/xpilot_metrics_table.png"
img.save(out)
print(f"saved: {out}")
