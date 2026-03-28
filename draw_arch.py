from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 900
img = Image.new("RGB", (W, H), "#F0F4F8")
draw = ImageDraw.Draw(img)

# 尝试加载字体
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

font_title = get_font(32)
font_layer = get_font(24)
font_item  = get_font(18)
font_arrow = get_font(28)
font_head  = get_font(36)

# ---- 标题 ----
draw.text((W//2, 38), "XPILOT 告警智能诊断 — 四层架构全景", font=font_head, fill="#1A2B4A", anchor="mm")

# ---- 层定义 ----
layers = [
    {
        "name": "诊断场景层",
        "color": "#4A90D9",
        "bg":    "#EAF3FB",
        "items": ["告警场景", "RCA场景", "日常场景", "发布场景"],
        "item_color": "#2C6FAC",
    },
    {
        "name": "诊断执行层",
        "color": "#E67E22",
        "bg":    "#FEF5EC",
        "items": ["整体定界", "深度诊断", "智能处置", "复盘优化"],
        "item_color": "#9D4E0A",
    },
    {
        "name": "能力中心层",
        "color": "#27AE60",
        "bg":    "#EAFAF1",
        "items": ["Agent中控", "Skill调度", "知识库", "反馈学习"],
        "item_color": "#1A7A40",
    },
    {
        "name": "智能数据层",
        "color": "#8E44AD",
        "bg":    "#F5EEF8",
        "items": ["原始数据", "U-MODEL", "服务画像", "高阶算法"],
        "item_color": "#5E2D8A",
    },
]

# 布局参数
margin_x = 60
layer_h   = 150
gap_y     = 28        # 层间箭头区域高度
start_y   = 90

for i, layer in enumerate(layers):
    y0 = start_y + i * (layer_h + gap_y)
    y1 = y0 + layer_h

    # 外框
    draw.rounded_rectangle([margin_x, y0, W - margin_x, y1],
                            radius=14, fill=layer["bg"],
                            outline=layer["color"], width=3)

    # 左侧色块 + 层名
    draw.rounded_rectangle([margin_x, y0, margin_x + 220, y1],
                            radius=14, fill=layer["color"])
    draw.text((margin_x + 110, (y0 + y1) // 2),
              layer["name"], font=font_layer, fill="white", anchor="mm")

    # 右侧四个子模块
    inner_x0 = margin_x + 240
    inner_w   = (W - margin_x - inner_x0 - 20) // 4
    box_h     = 64
    box_y0    = (y0 + y1) // 2 - box_h // 2

    for j, item in enumerate(layer["items"]):
        bx0 = inner_x0 + j * (inner_w + 10)
        bx1 = bx0 + inner_w
        by0 = box_y0
        by1 = box_y0 + box_h

        draw.rounded_rectangle([bx0, by0, bx1, by1],
                                radius=10, fill="white",
                                outline=layer["color"], width=2)
        draw.text(((bx0 + bx1) // 2, (by0 + by1) // 2),
                  item, font=font_item, fill=layer["item_color"], anchor="mm")

        # 层内箭头（→）
        if j < len(layer["items"]) - 1:
            ax = bx1 + 5
            ay = (by0 + by1) // 2
            draw.text((ax, ay), "→", font=font_arrow,
                      fill=layer["color"], anchor="lm")

    # 层间向下箭头
    if i < len(layers) - 1:
        ax = W // 2
        ay = y1 + gap_y // 2
        draw.text((ax, ay), "↓", font=font_arrow, fill="#555", anchor="mm")

out = "/home/node/.openclaw/workspace/xpilot_arch.png"
img.save(out)
print(f"saved: {out}")
