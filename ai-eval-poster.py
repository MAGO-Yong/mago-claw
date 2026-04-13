#!/usr/bin/env python3
"""AI 应用评估 竖版长海报 · 1080×3410"""

from PIL import Image, ImageDraw, ImageFont
import os

FONT_DIR = "/home/node/.openclaw/workspace/skills/canvas-design/canvas-fonts"
CN_BOLD  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CN_REG   = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
OUT = "/home/node/.openclaw/workspace/ai-eval-poster.png"

W, H = 1080, 3500
PAD  = 60
CW   = W - PAD*2

BLUE   = (22,  119, 255)
PURPLE = (114,  46, 209)
CYAN   = (0,   200, 240)
GREEN  = (82,  196,  26)
AMBER  = (250, 140,  16)
WHITE  = (255, 255, 255)
BG0    = (10,  15,  42)
BG1    = (20,   8,  52)
DIM    = (150, 170, 210)
DIMB   = (180, 200, 240)

def cn(sz, bold=False):
    return ImageFont.truetype(CN_BOLD if bold else CN_REG, sz)

def mono(sz, bold=False):
    name = "GeistMono-Bold.ttf" if bold else "GeistMono-Regular.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), sz)

def big_sh(sz):
    return ImageFont.truetype(os.path.join(FONT_DIR, "BigShoulders-Bold.ttf"), sz)

def nl(base):
    return Image.new("RGBA", base.size, (0,0,0,0))

def ac(base, lay):
    base.alpha_composite(lay)

def grad_bg(img):
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        s = abs(t-0.5)*2
        r = int(BG0[0]*s + BG1[0]*(1-s))
        g = int(BG0[1]*s + BG1[1]*(1-s))
        b = int(BG0[2]*s + BG1[2]*(1-s))
        d.line([(0,y),(W,y)], fill=(r,g,b))

def glow(base, cx, cy, r, color, amax=50):
    lay = nl(base); d = ImageDraw.Draw(lay)
    for i in range(r,0,-5):
        a = min(int(amax*(i/r)*(1-i/r)*4), amax)
        d.ellipse([cx-i,cy-i,cx+i,cy+i], fill=(*color,a))
    ac(base, lay)

def hline(base, y, a=160):
    lay = nl(base); d = ImageDraw.Draw(lay)
    for x in range(PAD, PAD+CW):
        t=(x-PAD)/CW
        r=int(BLUE[0]*(1-t)+PURPLE[0]*t); g=int(BLUE[1]*(1-t)+PURPLE[1]*t); b=int(BLUE[2]*(1-t)+PURPLE[2]*t)
        d.line([(x,y),(x,y+2)], fill=(r,g,b,a))
    ac(base, lay)

def card(base, x, y, w, h, r=16, bg=20, bdr=50, bc=WHITE):
    lay = nl(base); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x,y,x+w,y+h], radius=r, fill=(*WHITE,bg), outline=(*bc,bdr), width=1)
    ac(base, lay)

def topbar(base, x, y, w, r=16, color=BLUE, a=200):
    lay = nl(base); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x+1,y+1,x+w-1,y+5], radius=r, fill=(*color,a))
    ac(base, lay)

def lbar(base, x, y, h, color=BLUE, a=220):
    lay = nl(base); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x,y,x+4,y+h], radius=2, fill=(*color,a))
    ac(base, lay)

def pill(base, x, y, w, h, c1=BLUE, c2=PURPLE, a=220):
    lay = nl(base); d = ImageDraw.Draw(lay)
    for i in range(w):
        t=i/w; r=int(c1[0]*(1-t)+c2[0]*t); g=int(c1[1]*(1-t)+c2[1]*t); b=int(c1[2]*(1-t)+c2[2]*t)
        d.rectangle([x+i,y,x+i+1,y+h], fill=(r,g,b,a))
    mask = nl(base); ImageDraw.Draw(mask).rounded_rectangle([x,y,x+w,y+h], radius=h//2, fill=WHITE)
    lay.putalpha(Image.alpha_composite(nl(base), mask).split()[3])
    ac(base, lay)

def boxgrad(base, x, y, w, h, r=20, c1=BLUE, c2=PURPLE, a=45):
    lay = nl(base); d = ImageDraw.Draw(lay)
    for i in range(w):
        t=i/w; rv=int(c1[0]*(1-t)+c2[0]*t); gv=int(c1[1]*(1-t)+c2[1]*t); bv=int(c1[2]*(1-t)+c2[2]*t)
        d.rectangle([x+i,y,x+i+1,y+h], fill=(rv,gv,bv,a))
    mask = nl(base); ImageDraw.Draw(mask).rounded_rectangle([x,y,x+w,y+h], radius=r, fill=WHITE)
    lay.putalpha(Image.alpha_composite(nl(base), mask).split()[3])
    bdr = nl(base); ImageDraw.Draw(bdr).rounded_rectangle([x,y,x+w,y+h], radius=r, outline=(*WHITE,50), width=1)
    ac(base, lay); ac(base, bdr)

def dot(base, cx, cy, r, color, a=200):
    lay = nl(base); ImageDraw.Draw(lay).ellipse([cx-r,cy-r,cx+r,cy+r], fill=(*color,a))
    ac(base, lay)

def dotpat(base, x0,y0,x1,y1, step=44, a=14):
    lay = nl(base); d = ImageDraw.Draw(lay)
    for x in range(x0,x1,step):
        for y in range(y0,y1,step):
            d.ellipse([x-2,y-2,x+2,y+2], fill=(*WHITE,a))
    ac(base, lay)

def tc(d, text, cx, y, font, fill):
    bb = d.textbbox((0,0), text, font=font)
    d.text((cx-(bb[2]-bb[0])//2, y), text, font=font, fill=fill)

# ─── build ───
img = Image.new("RGB", (W, H), BG0)
grad_bg(img)
base = img.convert("RGBA")

glow(base, 200,  400, 380, BLUE,   38)
glow(base, 880,  700, 320, PURPLE, 32)
glow(base, 540, 1300, 280, (0,60,180), 25)
glow(base, 160, 1950, 340, PURPLE, 24)
glow(base, 930, 2600, 300, BLUE,   28)
glow(base, 300, 3100, 260, PURPLE, 20)
dotpat(base, 0, 0, W, 460)
dotpat(base, 0, 2800, W, H, a=10)

fH1  = cn(80, True);  fH2 = cn(48, True);  fH3 = cn(28, True)
fBd  = cn(24, True);  fBr = cn(24, False);  fSm = cn(21, False)
fMon = mono(18, False); fMonB = mono(18, True)

d = ImageDraw.Draw(base)

# ═══ S1 HERO ═══  y=72~412
pill(base, PAD, 72, 220, 36)
d.text((PAD+14, 80), "X-RAY  ·  新能力上线", font=fMon, fill=WHITE)
d.text((PAD, 132), "AI 应用评估", font=fH1, fill=WHITE)
d.text((PAD, 232), "让效果验证", font=fH2, fill=(160,210,255))
d.text((PAD, 288), "有依据 · 能追溯 · 可持续", font=fH2, fill=(190,165,255))
d.text((PAD, 362), "AI 应用上线后，你知道它好不好用吗？", font=fBr, fill=DIMB)
hline(base, 408)

# ═══ S2 PAIN  y=432~802 ═══
d.text((PAD, 432), "你是否遇到过？", font=fH3, fill=DIM)
PAINS = [
    (BLUE,   "线上效果没有持续观察机制",       "真实用户每天大量请求，靠人工根本覆盖不了"),
    (PURPLE, "版本迭代后说不清楚优化了还是劣化了","缺少统一评估口径，靠经验判断，无法长期积累"),
    (AMBER,  "发现的 bad case 沉淀不下来",      "没有机制持续复验，下次版本是否修复无从追踪"),
]
for i,(color,title,desc) in enumerate(PAINS):
    y = 484 + i*114
    card(base, PAD, y, CW, 100, r=14, bg=18, bdr=44, bc=color)
    lbar(base, PAD, y+10, 80, color)
    d.text((PAD+22, y+16), title, font=fBd, fill=WHITE)
    d.text((PAD+22, y+54), desc,  font=fSm, fill=DIMB)

# ═══ S3 定位  y=842~990 ═══
boxgrad(base, PAD, 842, CW, 148, r=20, c1=BLUE, c2=PURPLE, a=38)
d.text((PAD+28, 860),  "不是给结果打个分",           font=fBd, fill=(100,220,255))
d.text((PAD+28, 898),  "而是建立统一、可重复、可持续的", font=fBr, fill=WHITE)
d.text((PAD+28, 936),  "效果验证工作流",             font=fH2, fill=WHITE)

# ═══ S4 工作流  y=1034~1256 ═══
d.text((PAD, 1034), "核心工作流", font=fH3, fill=DIM)
STEPS = [
    (BLUE,        "准备规则",  "创建评估器\n定义评分标准"),
    (PURPLE,      "准备数据",  "线上链路\n或离线数据集"),
    ((0,170,220), "自动执行",  "任务周期调度\n持续自动运行"),
    (GREEN,       "查看结果",  "实验报告\n分析+明细"),
    (AMBER,       "回流沉淀",  "bad case 入库\n持续验证"),
]
SBW=162; SBH=148; SBG=(CW-5*SBW)//4; SBY=1082
for i,(color,title,desc) in enumerate(STEPS):
    x = PAD+i*(SBW+SBG)
    card(base, x, SBY, SBW, SBH, r=14, bg=20, bdr=50, bc=color)
    topbar(base, x, SBY, SBW, r=14, color=color)
    dot(base, x+SBW//2, SBY+34, 20, color, 180)
    tc(d, str(i+1), x+SBW//2, SBY+20, fBd, WHITE)
    tc(d, title,    x+SBW//2, SBY+64, fBd, (*color,))
    for j,line in enumerate(desc.split("\n")):
        tc(d, line, x+SBW//2, SBY+96+j*26, fSm, DIMB)
    if i<4:
        ax=x+SBW+SBG//2; ay=SBY+SBH//2
        arr=nl(base); ad=ImageDraw.Draw(arr)
        ad.line([(ax-10,ay),(ax+10,ay)], fill=(*WHITE,70), width=2)
        ad.polygon([(ax+7,ay-5),(ax+16,ay),(ax+7,ay+5)], fill=(*WHITE,70))
        ac(base, arr)

# ═══ S5 在线评估  y=1306~2008 ═══
pill(base, PAD, 1306, 100, 32, BLUE, PURPLE, 210)
d.text((PAD+12, 1313), "重点能力", font=fMonB, fill=WHITE)
d.text((PAD, 1354),  "在线链路评估",                 font=fH2, fill=WHITE)
d.text((PAD, 1410),  "配置一次，持续自动监控真实线上效果", font=fBr, fill=DIMB)

COL=(CW-28)//2; S5CY=1452

# 左栏
card(base, PAD, S5CY, COL, 400, r=18, bg=16, bdr=36)
d.text((PAD+20, S5CY+18), "怎么运行", font=fBd, fill=(100,200,255))
OSTEPS = [
    (BLUE,        "确认链路接入 X-RAY",  "trace、SPAN 数据在 X-RAY 可见"),
    (PURPLE,      "创建评估器",           "定义好坏标准，只需配置一次"),
    ((0,170,130), "建自动评估任务",       "选在线链路，设筛选条件和周期"),
    (GREEN,       "自动产出报告+回流",    "每次运行后实验报告自动生成"),
]
for i,(color,title,desc) in enumerate(OSTEPS):
    oy = S5CY+60+i*84
    dot(base, PAD+36, oy+16, 18, color)
    tc(d, str(i+1), PAD+36, oy+6, fBd, WHITE)
    d.text((PAD+68, oy+4),  title, font=fBd, fill=WHITE)
    d.text((PAD+68, oy+34), desc,  font=fSm, fill=DIMB)
    if i<3:
        vl=nl(base); ImageDraw.Draw(vl).line([(PAD+36,oy+36),(PAD+36,oy+84)], fill=(*color,60), width=2)
        ac(base,vl)

# 右栏
RX=PAD+COL+28
card(base, RX, S5CY, COL, 400, r=18, bg=16, bdr=36)
d.text((RX+20, S5CY+18), "你可以持续监控", font=fBd, fill=(100,200,255))
MONITORS=[
    (BLUE,        "整体效果趋势",   "P50/P90/P99 分布\n版本波动即时可见"),
    (PURPLE,      "分场景精细评估", "Trace 筛选，只评\n你关心的那条链路"),
    ((0,170,200), "低分样本定位",   "筛 bad case，查理由\n跳转链路追溯根因"),
    (AMBER,       "接入已有 Checker","幻觉检测、工具调用\n规则直接对接进来"),
]
for i,(color,title,desc) in enumerate(MONITORS):
    my=S5CY+60+i*84
    card(base, RX+14, my, COL-28, 72, r=12, bg=16, bdr=32, bc=color)
    lbar(base, RX+14, my+8, 54, color)
    d.text((RX+30, my+8),  title, font=fBd, fill=(*color,))
    for j,line in enumerate(desc.split("\n")):
        d.text((RX+30, my+36+j*22), line, font=fSm, fill=DIMB)

# 评估粒度
S5BY = S5CY + 416
d.text((PAD, S5BY), "评估粒度，三选一", font=fBd, fill=DIM)
MODES=[
    (BLUE,        "单 SPAN 评估","评某次 LLM 调用\nLLM/HTTP 均可 · 最常用"),
    ((0,160,200), "全链路评估",  "整条 Agent 链路\n仅支持 HTTP 评估器"),
    (GREEN,       "结果评估",    "只看最终输入输出\nLLM/HTTP 均可"),
]
MW=(CW-2*20)//3
for i,(color,title,desc) in enumerate(MODES):
    mx=PAD+i*(MW+20); my=S5BY+36
    card(base, mx, my, MW, 112, r=14, bg=20, bdr=50, bc=color)
    topbar(base, mx, my, MW, r=14, color=color)
    d.text((mx+16, my+14), title, font=fBd, fill=(*color,))
    for j,line in enumerate(desc.split("\n")):
        d.text((mx+16, my+48+j*28), line, font=fSm, fill=DIMB)

# ═══ S6 ALLIN  y=2048~2224 ═══
S6Y=2048
boxgrad(base, PAD, S6Y, CW, 168, r=20, c1=BLUE, c2=PURPLE, a=42)
d.text((PAD+28, S6Y+18),  "已与 ALLIN / REDNA 平台打通",     font=fBd, fill=WHITE)
d.text((PAD+28, S6Y+58),  "离线数据集评估时，直接从下拉选择你的智能体，", font=fSm, fill=DIMB)
d.text((PAD+28, S6Y+84),  "平台自动回放每条输入并统一评估。",              font=fSm, fill=DIMB)
d.text((PAD+28, S6Y+114), "不需要配 HTTP 接口，选一下就能跑。",            font=fBd, fill=WHITE)
for j,name in enumerate(["ALLIN","REDNA"]):
    lx=PAD+CW-200+j*108
    card(base, lx, S6Y+138, 88, 28, r=14, bg=50, bdr=90, bc=WHITE)
    bb=d.textbbox((0,0),name,font=fMonB)
    d.text((lx+44-(bb[2]-bb[0])//2, S6Y+145), name, font=fMonB, fill=WHITE)

# ═══ S7 评估器  y=2268~2664 ═══
S7Y=2268
d.text((PAD, S7Y), "两类评估器，各有专长", font=fH3, fill=DIM)
EW=(CW-24)//2; EY=S7Y+50; EH=248
for i,(color,name,tag,items) in enumerate([
    (BLUE,  "LLM 评估器","第一次搭体系，从这里开始",[
        "Prompt + 大模型语义判分",
        "相关性、正确性、幻觉检测",
        "支持单 SPAN / 结果评估",
        "上手快，快速验证思路",
    ]),
    (PURPLE,"HTTP 评估器","有成熟 checker 服务后补充",[
        "业务服务接口规则判分",
        "已有 checker 直接对接",
        "独有全链路评估能力",
        "稳定可控，复用已有逻辑",
    ]),
]):
    ex=PAD+i*(EW+24)
    card(base, ex, EY, EW, EH, r=18, bg=20, bdr=50, bc=color)
    topbar(base, ex, EY, EW, r=18, color=color)
    d.text((ex+18, EY+18), name, font=fBd, fill=(*color,))
    card(base, ex+18, EY+52, EW-36, 28, r=8, bg=30, bdr=60, bc=color)
    d.text((ex+26, EY+58), tag, font=fSm, fill=(*color,))
    for k,item in enumerate(items):
        d.text((ex+18, EY+94+k*36), "·  "+item, font=fSm, fill=DIMB)

NOTE_Y=EY+EH+14
card(base, PAD, NOTE_Y, CW, 48, r=10, bg=14, bdr=40, bc=(255,200,0))
d.text((PAD+18, NOTE_Y+12),
       "两类评估器均强制输出 score（得分）+ reason（原因），结果可被筛选、理解和复盘",
       font=fSm, fill=(255,220,120))

# ═══ S8 五模块  y=2726~3170 ═══
S8Y=NOTE_Y+48+40
d.text((PAD, S8Y), "五个模块 · 一条评估闭环", font=fH3, fill=DIM)
MODS=[
    (BLUE,        "LLM 配置",  "提供底层模型，决定评估效果和 token 成本"),
    (PURPLE,      "评估器",    "定义裁判标准：评什么维度、怎么打分"),
    ((0,160,120), "数据集",    "评估样本库，bad case 自动回流沉淀"),
    (AMBER,       "自动评估",  "执行中心，配置一次持续自动运行"),
    (GREEN,       "评估实验",  "每次运行的报告，分析+明细+链路追溯"),
]
MH=64
for i,(color,name,desc) in enumerate(MODS):
    my=S8Y+46+i*(MH+12)
    card(base, PAD, my, CW, MH, r=14, bg=18, bdr=40, bc=color)
    lbar(base, PAD, my+8, MH-16, color)
    d.text((PAD+22, my+8),  name, font=fBd, fill=(*color,))
    d.text((PAD+22, my+38), desc, font=fSm, fill=DIMB)

# ═══ S9 CTA ═══
S9Y=S8Y+46+5*(MH+12)+44
boxgrad(base, PAD, S9Y, CW, 64, r=32, c1=BLUE, c2=PURPLE, a=240)
tc(d, "查看完整使用手册  →", W//2, S9Y+18, fBd, WHITE)
d.text((PAD, S9Y+80),  "入口：X-RAY → AI 应用评估", font=fMon, fill=DIM)
d.text((PAD, S9Y+108), "docs.xiaohongshu.com/doc/10bd82c9c1bedd01879a3d78dfed4b26", font=fMon, fill=(90,110,150))
hline(base, S9Y+142, a=60)
d.text((PAD, S9Y+156), "AI 应用评估  ·  X-RAY 平台  ·  小红书技术风险", font=fMon, fill=(70,90,130))

final_h = S9Y + 190
final = base.convert("RGB").crop((0,0,W,final_h))
final.save(OUT, "PNG", quality=95)
print(f"Saved {W}x{final_h}")
