import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

# ══════════════════════════════════════════════════════════════════════════════
# EDIT THIS SECTION FOR EACH RQ
# ══════════════════════════════════════════════════════════════════════════════

TITLE = 'RQ? · Test Set Performance  (AOI_4 + AOI_5)'
#OUTPUT = 'figA_F1scores.png'
OUTPUT = r"C:\Users\misko\Documents\Michal\Master\A_Thesis\Actual_Scripts\outputs\general\figA_F1scores.png"

# One entry per run. Label appears under the bar group (use \n for line break).
RUNS = [
    {'id': 'R1', 'label': 'R1 · Temporal Stack\n(3-yr quarterly, 72 ch)',
     'bb': 0.880, 'mg': 0.403, 'wt': 0.072, 'macro': 0.451},
    {'id': 'R2', 'label': 'R2 · Mean Composite\n(GT year 2024, 6 ch)',
     'bb': 0.738, 'mg': 0.182, 'wt': 0.121, 'macro': 0.347},
    {'id': 'R3', 'label': 'R3 · Mean Composite\n(Post year 2025, 6 ch)',
     'bb': 0.755, 'mg': 0.043, 'wt': 0.000, 'macro': 0.266},
]

# ══════════════════════════════════════════════════════════════════════════════

BB_COL  = '#BA7517'   # bark beetle amber
MG_COL  = '#3B6D11'   # management green
WT_COL  = '#534AB7'   # windthrow purple
MAC_COL = '#2C2C2A'   # macro F1 dark
GRID_C  = '#D3D1C7'
DARK    = '#2C2C2A'
MID     = '#5F5E5A'

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE
# ══════════════════════════════════════════════════════════════════════════════
n       = len(RUNS)
labels  = [r['label']  for r in RUNS]
bb_vals = [r['bb']     for r in RUNS]
mg_vals = [r['mg']     for r in RUNS]
wt_vals = [r['wt']     for r in RUNS]
mac_vals= [r['macro']  for r in RUNS]

fig, ax = plt.subplots(figsize=(10, 5.5), facecolor='white')
fig.subplots_adjust(left=0.08, right=0.97, top=0.85, bottom=0.20)

x = np.arange(n)
w = 0.18
offsets = [-1.5*w, -0.5*w, 0.5*w, 1.5*w]

b_bb = ax.bar(x+offsets[0], bb_vals, w, color=BB_COL, zorder=3, linewidth=1)
b_mg = ax.bar(x+offsets[1], mg_vals, w, color=MG_COL, zorder=3, linewidth=1)
b_wt = ax.bar(x+offsets[2], wt_vals, w, color=WT_COL, zorder=3, linewidth=1)

# Macro F1 diamond markers + labels
for xi, mv in zip(x, mac_vals):
    ax.plot(xi+offsets[3], mv, marker='D', color=MAC_COL, markersize=10, zorder=5)
    ax.text(xi+offsets[3], mv+0.028, f'{mv:.3f}',
            ha='center', va='bottom', fontsize=9, color=MAC_COL, fontweight='bold')

# Value labels on bars (skip near-zero)
for bars, vals in [(b_bb, bb_vals), (b_mg, mg_vals), (b_wt, wt_vals)]:
    for bar, v in zip(bars, vals):
        if v > 0.02:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.014,
                    f'{v:.3f}', ha='center', va='bottom', fontsize=8.5, color=DARK)

ax.set_xlim(-0.55, n-0.45)
ax.set_ylim(0, 1.12)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9.5, color=DARK)
ax.set_ylabel('F1-Score', fontsize=10, color=DARK)
ax.set_title(TITLE, fontsize=12, fontweight='bold', color=DARK, pad=10)
ax.yaxis.set_major_locator(plt.MultipleLocator(0.2))
ax.tick_params(axis='y', labelsize=9, colors=MID)
ax.tick_params(axis='x', length=0)
ax.set_axisbelow(True)
ax.yaxis.grid(True, color=GRID_C, linewidth=0.7, zorder=0)
ax.spines[['top', 'right', 'left']].set_visible(False)
ax.spines['bottom'].set_color(GRID_C)

legend_elements = [
    mpatches.Patch(facecolor=BB_COL, label='Bark beetle'),
    mpatches.Patch(facecolor=MG_COL, label='Management'),
    mpatches.Patch(facecolor=WT_COL, label='Windthrow'),
    Line2D([0],[0], marker='D', color='w', markerfacecolor=MAC_COL,
           markersize=9, label='Macro F1'),
]
ax.legend(handles=legend_elements, fontsize=9.5, frameon=True,
          framealpha=0.95, edgecolor=GRID_C, loc='upper right',
          handlelength=1.4, handleheight=1.1)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight', facecolor='white')
print(f'Saved {OUTPUT}')
