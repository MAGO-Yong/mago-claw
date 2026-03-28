import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
from matplotlib.patches import FancyArrowPatch

font_regular = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font_bold    = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

fp_r  = fm.FontProperties(fname=font_regular, size=9)
fp_b  = fm.FontProperties(fname=font_bold,    size=10)
fp_t  = fm.FontProperties(fname=font_bold,    size=14)
fp_s  = fm.FontProperties(fname=font_regular, size=9)
fp_bd = fm.FontProperties(fname=font_bold,    size=7.5)
fp_lp = fm.FontProperties(fname=font_bold,    size=8)

# ── canvas ──────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(22, 5.8))
ax.set_xlim(0, 22)
ax.set_ylim(0, 5.8)
ax.axis('off')
bg = '#FFFFFF'
fig.patch.set_facecolor(bg)
ax.set_facecolor(bg)

# ── palette ──────────────────────────────────────────────────────────────────
STEPS = [
    ("诊断结果生成",   "Result Generated",  '#4285F4'),
    ("用户打标",       "正确 / 错误",        '#34A853'),
    ("Feedback Pool", "数据沉淀",           '#FF6D00'),
    ("Bad Case 分析", "定期审查",           '#EA4335'),
    ("模型重训练",     "规则调整",           '#9C27B0'),
    ("A/B 测试",      "验证效果",           '#00897B'),
    ("全量发布",       "新版本上线",         '#1565C0'),
    ("继续收集反馈",   "下一轮开始",         '#4285F4'),
]

N      = len(STEPS)
BOX_W  = 2.10
BOX_H  = 1.80
GAP    = 0.40
Y      = 2.90          # box center y
START  = 0.55

xs = [START + i * (BOX_W + GAP) for i in range(N)]

# ── draw boxes ───────────────────────────────────────────────────────────────
for i, (top, bot, col) in enumerate(STEPS):
    x  = xs[i]
    xc = x + BOX_W / 2

    # shadow
    shadow = mpatches.FancyBboxPatch(
        (x + 0.06, Y - BOX_H/2 - 0.06), BOX_W, BOX_H,
        boxstyle="round,pad=0.12",
        facecolor='#00000018', edgecolor='none', zorder=2
    )
    ax.add_patch(shadow)

    # main box
    box = mpatches.FancyBboxPatch(
        (x, Y - BOX_H/2), BOX_W, BOX_H,
        boxstyle="round,pad=0.12",
        facecolor=col, edgecolor='white', linewidth=1.8, zorder=3
    )
    ax.add_patch(box)

    # step badge
    badge = plt.Circle((x + 0.26, Y + BOX_H/2 - 0.26), 0.19,
                        color='white', zorder=4)
    ax.add_patch(badge)
    ax.text(x + 0.26, Y + BOX_H/2 - 0.26, str(i + 1),
            ha='center', va='center', fontproperties=fp_bd, color=col, zorder=5)

    # top label (Chinese main)
    ax.text(xc, Y + 0.24, top,
            ha='center', va='center', fontproperties=fp_b, color='white', zorder=4)
    # bottom label (sub)
    ax.text(xc, Y - 0.34, bot,
            ha='center', va='center', fontproperties=fp_r, color=(1,1,1,0.82), zorder=4)

# ── forward arrows ────────────────────────────────────────────────────────────
for i in range(N - 1):
    x0 = xs[i] + BOX_W + 0.05
    x1 = xs[i + 1] - 0.05
    ax.annotate('', xy=(x1, Y), xytext=(x0, Y),
                arrowprops=dict(
                    arrowstyle='->', color='#BDBDBD',
                    lw=1.8, mutation_scale=16
                ), zorder=2)

# ── loop-back line (clean horizontal route at the bottom) ────────────────────
LY   = Y - BOX_H/2 - 0.38   # horizontal rail y
LX0  = xs[-1] + BOX_W / 2
LX1  = xs[0]  + BOX_W / 2
TICK = 0.26                  # vertical drop from box bottom to rail

# right drop
ax.annotate('', xy=(LX0, LY), xytext=(LX0, Y - BOX_H/2),
            arrowprops=dict(arrowstyle='-', color='#FBBC04', lw=2.0), zorder=2)
# horizontal rail (right → left)
ax.annotate('', xy=(LX1, LY), xytext=(LX0, LY),
            arrowprops=dict(arrowstyle='-', color='#FBBC04', lw=2.0), zorder=2)
# left rise with arrowhead
ax.annotate('', xy=(LX1, Y - BOX_H/2), xytext=(LX1, LY),
            arrowprops=dict(
                arrowstyle='->', color='#FBBC04',
                lw=2.0, mutation_scale=14
            ), zorder=2)

# label on the rail
ax.text((LX0 + LX1) / 2, LY - 0.14, '持续迭代闭环',
        ha='center', va='top', fontproperties=fp_lp, color='#E08000', zorder=3)

# ── title & subtitle ─────────────────────────────────────────────────────────
ax.text(11.0, 5.50, '持续学习闭环  ——  4.2.4 复盘优化',
        ha='center', va='center', fontproperties=fp_t, color='#212121', zorder=3)
ax.text(11.0, 5.08, '每次故障都是学习机会，用户反馈驱动模型持续进化',
        ha='center', va='center', fontproperties=fp_s, color='#757575', zorder=3)

# ── thin top accent line ──────────────────────────────────────────────────────
ax.plot([0.5, 21.5], [5.72, 5.72], color='#4285F4', lw=3, solid_capstyle='round', zorder=3)

plt.tight_layout(pad=0.3)
plt.savefig('/home/node/.openclaw/workspace/learning_loop_flow.png',
            dpi=160, bbox_inches='tight', facecolor=bg)
print("Done!")
