#!/usr/bin/env python3
"""
X-RAY AI 应用评估 封面生成器 v6 — final masterpiece
Design Philosophy: Signal Silence
"""

from PIL import Image, ImageDraw, ImageFont
import math, random

FONTS    = "/home/node/.openclaw/workspace/skills/canvas-design/canvas-fonts/"
CJK_REG  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
OUT      = "/home/node/.openclaw/workspace/xray-eval-cover.png"

W, H = 1200, 1600

BG_TOP   = (8,  13, 40)
BG_MID   = (12, 10, 48)
BG_BOT   = (16,  5, 50)
BG_DARK  = (5,   8, 30)
INDIGO   = (22, 119, 255)
VIOLET   = (114, 46, 209)
COBALT   = (55, 140, 255)
WARM     = (250, 140, 22)
WHITE    = (255, 255, 255)
GREEN    = (82, 196, 26)

def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))

def en(path, size):
    return ImageFont.truetype(FONTS + path, size)

def cn(size, bold=False):
    path = CJK_BOLD if bold else CJK_REG
    return ImageFont.truetype(path, size, index=2)

# ── Base canvas with gradient ─────────────────────────────────────────────────
img = Image.new("RGB", (W, H), BG_TOP)
draw = ImageDraw.Draw(img, "RGBA")

# Upper half: BG_TOP → BG_MID, lower half: BG_MID → BG_BOT
for y in range(H):
    t = y / H
    c = lerp(BG_TOP, BG_MID, min(t/0.5,1)) if t<0.5 else lerp(BG_MID, BG_BOT, (t-0.5)/0.5)
    draw.line([(0,y),(W,y)], fill=c)

# Bottom dark strip (footer zone)
FOOTER_Y = H - 160
for y in range(FOOTER_Y, H):
    t = (y - FOOTER_Y) / 160
    c = lerp(BG_BOT, BG_DARK, t)
    draw.line([(0,y),(W,y)], fill=c)

# Diagonal fine grid
for i in range(-H, W+H, 64):
    draw.line([(i,0),(i+H,H)], fill=(255,255,255,4), width=1)

# ── Orbital system ────────────────────────────────────────────────────────────
cx, cy = W//2, 280

# Cross-hair
draw.line([(cx-400,cy),(cx+400,cy)], fill=(255,255,255,7), width=1)
draw.line([(cx,cy-400),(cx,cy+400)], fill=(255,255,255,7), width=1)

# Rings
for r,col,a in [
    (395,WHITE,  16),
    (270,INDIGO, 90),
    (165,VIOLET,110),
    ( 78,COBALT, 74),
]:
    for off,oa in [(0,1.0),(1,0.45),(-1,0.45)]:
        draw.ellipse([(cx-r+off,cy-r+off),(cx+r-off,cy+r-off)],
                     outline=(*col,int(a*oa)), width=1)

# Ring dots
for ring_r,n,dot_r,col,a in [
    (395,72,1.3,WHITE, 17),
    (270,40,2.0,COBALT,88),
    (165,26,2.6,VIOLET,130),
    ( 78,12,2.0,COBALT,104),
]:
    for i in range(n):
        angle = 2*math.pi*i/n
        dx = cx + ring_r*math.cos(angle)
        dy = cy + ring_r*math.sin(angle)
        draw.ellipse([(dx-dot_r,dy-dot_r),(dx+dot_r,dy+dot_r)],fill=(*col,a))

# Spokes
for a_deg in range(0,360,30):
    a = math.radians(a_deg)
    draw.line([(cx+20*math.cos(a),cy+20*math.sin(a)),
               (cx+390*math.cos(a),cy+390*math.sin(a))],
              fill=(255,255,255,7), width=1)

# Central node
for gr,ga in [(92,9),(66,19),(44,34),(30,55),(19,78)]:
    draw.ellipse([(cx-gr,cy-gr),(cx+gr,cy+gr)], fill=(*INDIGO,ga))
for ri in range(17,0,-1):
    draw.ellipse([(cx-ri,cy-ri),(cx+ri,cy+ri)], fill=lerp(INDIGO,VIOLET,ri/17))

# Scan lines (upper zone only)
for y in range(30,700,5):
    a = int(8*(1 - abs(y-cy)/500))
    if a > 0:
        draw.line([(0,y),(W,y)], fill=(255,255,255,a), width=1)

# Satellite nodes
f_sat = cn(17)
for ang_deg,label,col in [
    ( 72,"评估器",VIOLET),
    (162,"数据集",COBALT),
    (252,"任务",  INDIGO),
    (342,"报告",  VIOLET),
]:
    ang = math.radians(ang_deg)
    sx = cx+165*math.cos(ang); sy = cy+165*math.sin(ang)
    draw.ellipse([(sx-5,sy-5),(sx+5,sy+5)],fill=(*col,225),outline=(255,255,255,90),width=1)
    lx = cx+208*math.cos(ang); ly = cy+208*math.sin(ang)
    draw.line([(sx+6*math.cos(ang),sy+6*math.sin(ang)),(lx,ly)],fill=(255,255,255,20),width=1)
    tw = draw.textlength(label,font=f_sat)
    draw.text((lx-tw/2,ly-9), label, font=f_sat, fill=(255,255,255,80))

# Particles
random.seed(42)
for _ in range(300):
    px,py = random.randint(0,W),random.randint(0,H)
    pr = random.uniform(0.4,1.8)
    draw.ellipse([(px-pr,py-pr),(px+pr,py+pr)],fill=(255,255,255,random.randint(7,30)))

# Left gutter ticks
for i in range(20):
    yp = 60+i*44; tl = 13 if i%2==0 else 6
    draw.line([(56,yp),(56+tl,yp)], fill=(255,255,255,25), width=1)

# Gutter labels
f_ref = en("GeistMono-Regular.ttf",12)
for i,lbl in enumerate(["SIG_01","SIG_02","SIG_03","SIG_04","SIG_05"]):
    draw.text((14,110+i*132), lbl, font=f_ref, fill=(255,255,255,18))

# Ambient blobs
for bx,by,br,col,ma in [
    (W-280,H-80,600,VIOLET,24),
    (-80,  220, 320,INDIGO,16),
]:
    blob = Image.new("RGBA",(W,H),(0,0,0,0))
    bd   = ImageDraw.Draw(blob)
    for ri in range(br,0,-1):
        bd.ellipse([(bx-ri,by-ri),(bx+ri,by+ri)],fill=(*col,int(ma*(1-ri/br))))
    img = Image.alpha_composite(img.convert("RGBA"),blob).convert("RGB")
    draw = ImageDraw.Draw(img,"RGBA")

# ══════════════════════════════════════════════════════
# TEXT ZONE
# ══════════════════════════════════════════════════════

# Badge
bx0,by0 = 64,108
f_badge = cn(18)
btxt = "X-RAY  ·  AI 应用评估  ·  正式上线"
bw = int(draw.textlength(btxt,font=f_badge))+44
draw.rounded_rectangle([(bx0,by0-4),(bx0+bw,by0+26)],
    radius=18,fill=(255,255,255,17),outline=(255,255,255,44),width=1)
draw.ellipse([(bx0+14,by0+6),(bx0+22,by0+14)],fill=(*GREEN,240))
draw.text((bx0+28,by0),btxt,font=f_badge,fill=(255,255,255,215))

# Section label + thin rule
hy = 700
draw.line([(64,hy-18),(W-64,hy-18)],fill=(255,255,255,14),width=1)
f_lbl = en("GeistMono-Regular.ttf",14)
draw.text((64,hy-15),"EVALUATION GUIDE  ·  SIGNAL INTELLIGENCE",font=f_lbl,fill=(255,255,255,28))

# Headline
f_h = cn(108,bold=True)
draw.text((64,hy+2),  "你的 Agent", font=f_h, fill=WHITE)
draw.text((64,hy+116),"表现如何？", font=f_h, fill=COBALT)

# Wave underline
ul_y = hy+237
for sx in range(64,700,16):
    t = (sx-64)/636
    a = int(30*math.sin(math.pi*t))
    if a>0:
        draw.line([(sx,ul_y),(sx+12,ul_y)],fill=(*COBALT,a),width=1)

# Subtitle
f_sub = cn(26)
draw.text((64,hy+254),"Agent 的输出是模型、工具、知识库和",font=f_sub,fill=(255,255,255,145))
draw.text((64,hy+288),"多轮交互的综合结果——你用什么来判断？",font=f_sub,fill=(255,255,255,145))

# Divider 1
d1y = hy+338
draw.line([(64,d1y),(W-64,d1y)],fill=(255,255,255,18),width=1)

# 4 Pillars
pils = [
    (INDIGO,"建立认知","误解 → 正确理解"),
    (VIOLET,"评估地图","四阶段 · 数据飞轮"),
    (COBALT,"配置机制","评估器 · 任务 · 结果"),
    (WARM,  "开始行动","A / B 两条起点"),
]
py0 = d1y+20; pw = (W-128-36)//4
f_pt = cn(21,bold=True); f_pd = cn(15)
for i,(col,title,desc) in enumerate(pils):
    px = 64+i*(pw+12)
    draw.rectangle([(px,py0),(px+26,py0+3)],fill=(*col,255))
    draw.text((px,py0+12),title,font=f_pt,fill=(255,255,255,228))
    draw.text((px,py0+42),desc, font=f_pd, fill=(255,255,255,98))
for i in range(1,4):
    vx = 64+i*(pw+12)-7
    draw.line([(vx,py0),(vx,py0+64)],fill=(255,255,255,12),width=1)

# Divider 2
d2y = py0+80
draw.line([(64,d2y),(W-64,d2y)],fill=(255,255,255,14),width=1)

# 3 Stats
stats = [("4 层","从认知到行动的完整框架"),("3 档","代码 · LLM · 人工协同评估"),("∞","数据飞轮持续积累价值")]
sy0 = d2y+22; sw=(W-128)//3
f_sn = cn(34,bold=True); f_sd = cn(15)
for i,(num,desc) in enumerate(stats):
    sx = 64+i*sw
    draw.text((sx,sy0),num, font=f_sn,fill=(*COBALT,205))
    draw.text((sx,sy0+48),desc,font=f_sd,fill=(255,255,255,92))

# Divider 3
d3y = sy0+96
draw.line([(64,d3y),(W-64,d3y)],fill=(255,255,255,13),width=1)

# ── FOOTER ZONE ───────────────────────────────────────────────────────────────
# CTA text
cta_y = d3y+32
f_cta_cn = cn(18)
f_cta_en = en("GeistMono-Regular.ttf",17)
draw.text((64,cta_y),"打开 X-RAY · 开始第一次评估",font=f_cta_cn,fill=(255,255,255,125))
url = "xray.devops.xiaohongshu.com  →"
uw  = int(draw.textlength(url,font=f_cta_en))
draw.text((W-64-uw,cta_y+2),url,font=f_cta_en,fill=(*COBALT,155))

# Horizontal gradient line (decorative)
for xi in range(64, W-64):
    t = (xi - 64) / (W - 128)
    col = lerp(INDIGO, VIOLET, t)
    a = int(55 * math.sin(math.pi * t))
    draw.point((xi, cta_y+38), fill=(*col, a))

# Data pulse visualization in footer zone
pulse_y = H - 120
for xi in range(64, W-64, 2):
    t = (xi - 64) / (W - 128)
    # ECG-like signal using multiple sin waves
    val  = 0.35 * math.sin(t * 40 * math.pi)
    val += 0.15 * math.sin(t * 80 * math.pi)
    val += 0.08 * math.sin(t * 13 * math.pi + 1.2)
    # Spike at t≈0.42
    if 0.40 < t < 0.46:
        spike_t = (t - 0.40) / 0.06
        val += 1.4 * math.exp(-((spike_t - 0.5)**2) / 0.005) * math.sin(spike_t * math.pi)
    py_val = pulse_y + int(val * 22)
    a = int(110 * (0.5 + 0.5 * math.sin(t * math.pi)))
    col = lerp(INDIGO, COBALT, t)
    draw.point((xi, py_val), fill=(*col, a))
    draw.point((xi, py_val+1), fill=(*col, a//2))

# Thin meta at very bottom
meta_y = H-52
draw.line([(64,meta_y-14),(W-64,meta_y-14)],fill=(255,255,255,15),width=1)
f_mcn = cn(14); f_men = en("GeistMono-Regular.ttf",14)
draw.text((64,meta_y),"X-RAY · 小红书技术风险",font=f_mcn,fill=(255,255,255,55))
url2 = "xray.devops.xiaohongshu.com"
uw2 = int(draw.textlength(url2,font=f_men))
draw.text((W-64-uw2,meta_y),url2,font=f_men,fill=(255,255,255,42))

# Right vertical label
f_vert = en("GeistMono-Regular.ttf",13)
vt = "AI APPLICATION EVALUATION"
vi = Image.new("RGBA",(len(vt)*8,22),(0,0,0,0))
vd = ImageDraw.Draw(vi)
vd.text((0,2),vt,font=f_vert,fill=(255,255,255,28))
vr = vi.rotate(90,expand=True)
ia = img.convert("RGBA")
ia.paste(vr,(W-26,(H-vr.height)//2),vr)
img = ia.convert("RGB")

img.save(OUT,"PNG",dpi=(300,300))
print("Done →",OUT)
