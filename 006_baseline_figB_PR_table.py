import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

TITLE  = 'RQ1 · Precision-Recall and Result Summary  (Test Set)'
OUTPUT = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Actual_Scripts/outputs/Final/RQ1_figB_PR_table.png"
RESULTS_FILE = r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Data/Result_table.xlsx"

# Precision-recall per run per class.
# Each entry: 'id', 'label' (short, for legend), 'marker',
# and per-class (precision, recall) tuples.

excel_read = pd.read_excel(RESULTS_FILE)
RUN_ID = excel_read.columns[2]
RUNS = [
    {
        'id': 'R1', 'label': 'R1 · Temporal stack', 'marker': 'o',
        'bb': (0.88, 0.88), 'mg': (0.46, 0.36), 'wt': (0.06, 0.11),
    },
    {
        'id': 'R2', 'label': 'R2 · GT year mean', 'marker': 's',
        'bb': (0.83, 0.67), 'mg': (0.23, 0.15), 'wt': (0.07, 0.45),
    },
    {
        'id': 'R3', 'label': 'R3 · Post year mean', 'marker': '^',
        'bb': (0.77, 0.74), 'mg': (0.05, 0.04), 'wt': (0.00, 0.00),
    },
]

# Table rows — test set metrics only.
# Columns after the first three are numeric F1 values (used for best-cell highlight).
TABLE_COL_LABELS = [
    'Run', 'Method', 'Config',
    'Bark\nBeetle F1', 'Mgmt\nF1', 'Windthrow\nF1', 'Macro\nF1'
]
TABLE_ROWS = [
    ['R1', 'Temporal Stack',   'Multi-temporal · 72 ch', '0.880', '0.403', '0.072', '0.451'],
    ['R2', 'Mean (GT Year)',   'Single-temporal · 6 ch', '0.738', '0.182', '0.121', '0.347'],
    ['R3', 'Mean (Post Year)', 'Single-temporal · 6 ch', '0.755', '0.043', '0.000', '0.266'],
]

N_LABEL_COLS = 3

BB_COL  = '#BA7517'
MG_COL  = '#3B6D11'
WT_COL  = '#534AB7'
TBL_HDR = '#1a3a2a'
TBL_HLT = '#d6edd8'
#GRID_C  = '#D3D1C7'
GRID_C = '#1a3a2a'
DARK    = '#2C2C2A'
MID     = '#5F5E5A'
LIGHT   = '#F1EFE8'
WHITE   = '#FAFAF8'

fig = plt.figure(figsize=(13, 8), facecolor=MID)
gs  = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[1.2, 0.8], hspace=0.55)
fig.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.04)

ax_pr  = fig.add_subplot(gs[0])
ax_tbl = fig.add_subplot(gs[1])
ax_tbl.axis('off')

fig.text(0.5, 0.94, TITLE, ha='center', va='top',
         fontsize=14, fontweight='bold', color=DARK)

# ── Precision-Recall scatter ──────────────────────────────────────────────────
class_colors = {'bb': BB_COL, 'mg': MG_COL, 'wt': WT_COL}

for run in RUNS:
    for cls in ['bb', 'mg', 'wt']:
        prec, rec = run[cls]
        ax_pr.scatter(rec, prec,
                      color=class_colors[cls],
                      marker=run['marker'],
                      s=180, zorder=4,
                      edgecolors=WHITE, linewidths=1.5)
        ax_pr.annotate(run['id'], xy=(rec, prec),
                       xytext=(7, 4), textcoords='offset points',
                       fontsize=12, fontweight = 'bold',color=MID)

ax_pr.plot([0, 1], [0, 1], '--', color=GRID_C, linewidth=1.0, zorder=1)
ax_pr.set_xlim(-0.02, 1.01)
ax_pr.set_ylim(-0.02, 1.01)
ax_pr.set_xlabel('Recall', fontsize=14, color=DARK)
ax_pr.set_ylabel('Precision', fontsize=14, color=DARK)
ax_pr.tick_params(labelsize=12, colors=MID)
ax_pr.set_axisbelow(True)
ax_pr.grid(True, color=GRID_C, linewidth=0.4, zorder=0)
ax_pr.spines[['top', 'right']].set_visible(False)
ax_pr.spines[['left', 'bottom']].set_color(GRID_C)

leg_class = [
    mpatches.Patch(facecolor=BB_COL, label='Bark beetle'),
    mpatches.Patch(facecolor=MG_COL, label='Management'),
    mpatches.Patch(facecolor=WT_COL, label='Windthrow'),
]
leg_run = [
    Line2D([0],[0], marker=r['marker'], color='w',
           markerfacecolor='#888780', markersize=12, label=r['label'])
    for r in RUNS
]
l1 = ax_pr.legend(handles=leg_class, fontsize=12, frameon=True,
                   framealpha=0.95 ,edgecolor=GRID_C ,loc='lower right')
ax_pr.add_artist(l1)
ax_pr.legend(handles=leg_run, fontsize=12, frameon=True,
             framealpha=0.95, edgecolor=GRID_C, loc='upper left')

# ── Table ─────────────────────────────────────────────────────────────────────
n_cols   = len(TABLE_COL_LABELS)
n_rows   = len(TABLE_ROWS)

# Column widths — adjust the raw values to taste, they get normalised
col_ws_raw = [0.07, 0.16, 0.18] + [0.13] * (n_cols - N_LABEL_COLS)
total      = sum(col_ws_raw)
col_ws     = [w / total for w in col_ws_raw]

T_LEFT, T_RIGHT = 0.03, 0.97
T_TOP   = 0.88
ROW_H   = 0.22
HDR_H   = 0.28
TOTAL_W = T_RIGHT - T_LEFT

x_pos = [T_LEFT]
for w in col_ws[:-1]:
    x_pos.append(x_pos[-1] + w * TOTAL_W)

# Identify best value per numeric column
best_in_col = {}
for ci in range(N_LABEL_COLS, n_cols):
    vals = [float(row[ci]) for row in TABLE_ROWS]
    best_in_col[ci] = max(vals)

def draw_rect(ax, x, y, w, h, fc, ec=WHITE, lw=0.5):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle='square,pad=0',
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ax.transAxes, clip_on=False))

def draw_text(ax, x, y, s, fs=8.5, bold=False, color=DARK, ha='center'):
    ax.text(x, y, s, transform=ax.transAxes,
            fontsize=fs, fontweight='bold' if bold else 'normal',
            color=color, ha=ha, va='center',
            clip_on=False, multialignment='center')

#Header row
for ci, (lbl, xp, cw) in enumerate(zip(TABLE_COL_LABELS, x_pos, col_ws)):
    draw_rect(ax_tbl, xp, T_TOP-HDR_H, cw*TOTAL_W, HDR_H, TBL_HDR)
    draw_text(ax_tbl, xp+cw*TOTAL_W/2, T_TOP-HDR_H/2, lbl,
              fs=8, bold=True, color=WHITE)

ax_tbl.text(0.5, T_TOP+0.06, 'Test Set Results',
            transform=ax_tbl.transAxes, ha='center', va='bottom',
            fontsize=9.5, fontweight='bold', color=DARK)

# Data rows
for ri, row in enumerate(TABLE_ROWS):
    y_top  = T_TOP - HDR_H - ri * ROW_H
    row_bg = LIGHT if ri % 2 == 0 else WHITE
    for ci, (val, xp, cw) in enumerate(zip(row, x_pos, col_ws)):
        is_best = ci >= N_LABEL_COLS and float(val) == best_in_col[ci]
        fc  = TBL_HLT if is_best else row_bg
        draw_rect(ax_tbl, xp, y_top-ROW_H, cw*TOTAL_W, ROW_H,
                  fc, ec=GRID_C, lw=0.4)
        bold = is_best or ci == 0
        tc   = '#1a3a2a' if is_best else (DARK if ci < N_LABEL_COLS else MID)
        draw_text(ax_tbl, xp+cw*TOTAL_W/2, y_top-ROW_H/2, val,
                  fs=8.5, bold=bold, color=tc)

ax_tbl.set_xlim(0, 1)
ax_tbl.set_ylim(0, 1)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight', facecolor=WHITE)
print(f'Saved {OUTPUT}')
