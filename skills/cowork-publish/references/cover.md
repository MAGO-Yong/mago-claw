# Cowork 封面 / 头图生成规范

> **何时读**：需要用 Python/PIL 生成 `cover.png` / 头图 / 卡片图时必须读。目标：避免中文渲染成 □□□（tofu 方块）。

## 红线

- ❌ 不要用 `ImageFont.load_default()` 画中文；它不含中文 glyph，必然变方块。
- ❌ 不要默认用 DejaVu / Arial / Helvetica 画中文；多数环境不含 CJK glyph。
- ✅ 必须显式加载 CJK 字体：优先 Noto Sans CJK SC。
- ✅ 如果找不到 CJK 字体：**不要画中文文字**，改为纯色/图标/英文，避免产出方块封面。

## OpenClaw Pod 默认可用字体

当前部署镜像通常有：

```text
/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc
/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc
```

可用命令确认：

```bash
fc-list :lang=zh | head
```

## 推荐 PIL helper（直接复制）

```python
from pathlib import Path
from PIL import ImageFont

CJK_FONT_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",        # macOS fallback
        "/System/Library/Fonts/STHeiti Light.ttc",
    ],
    "bold": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
}


def load_cjk_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    style = "bold" if bold else "regular"
    for p in CJK_FONT_CANDIDATES[style]:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    # 不要 fallback 到 ImageFont.load_default() 画中文 —— 会变 □□□
    raise RuntimeError(
        "No CJK font found. Install Noto Sans CJK or generate a no-text cover. "
        "Do not use ImageFont.load_default() for Chinese."
    )
```

## 最小示例

```python
from PIL import Image, ImageDraw

W, H = 1200, 675
img = Image.new("RGB", (W, H), "#fff7f8")
d = ImageDraw.Draw(img)

title_font = load_cjk_font(92, bold=True)
sub_font = load_cjk_font(38)

# Pillow 新版可用 anchor="mm" 居中
d.text((W/2, 270), "问问帝江", font=title_font, fill="#222", anchor="mm")
d.text((W/2, 350), "给帝江留个问题，他会在这里回复你", font=sub_font, fill="#666", anchor="mm")

img.save("cover.png")
```

## 生成后自检

- 打开图片肉眼确认中文不是 `□□□`。
- 如果无法截图/查看，至少运行一次：

```bash
python3 - <<'PY'
from PIL import ImageFont
p = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
f = ImageFont.truetype(p, 40)
print(f.getbbox("问问帝江 已部署"))
PY
```

## 设计建议

- 中文标题建议 Noto Sans CJK Bold；正文 Noto Sans CJK Regular。
- 封面尺寸建议 1200×675 或 800×450，避免太小导致列表里糊。
- 文字不要超过 2 行；长标题优先换行，不要缩到 20px 以下。
- 如果不确定字体是否存在，宁可生成**无文字封面**，不要生成方块字。 
