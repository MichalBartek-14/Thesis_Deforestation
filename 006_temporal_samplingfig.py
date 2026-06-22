import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#D3D1C7"
WHITE     = "#FAFAF8"
AMBER     = "#BA7517"
TEAL      = "#0F6E56"
PURPLE    = "#534AB7"
CORAL     = "#D85A30"
BLUE      = "#185FA5"
GRAY      = "#888780"
RED       = "#E24B4A"
DARK_TEXT = "#2C2C2A"
LIGHT_TEXT= "#FAFAF8"

# ── Layout ────────────────────────────────────────────────────────────────────
YEARS = [2022, 2023, 2024, 2025]
N_MONTHS = 48
MONTHS_ABBR = ["J","F","M","A","M","J","J","A","S","O","N","D"] * 4

CELL_W  = 0.38   # narrower columns
CELL_H  = 0.90   # taller rows
ROW_GAP = 0.30
LABEL_W = 3.8
CH_W    = 1.2

# ── Row definitions ───────────────────────────────────────────────────────────
# Row 0: s2_quarterly (R1·R4·R5·R6 — 1yr window shown separately below)
# Row 1: P1 single mean
# Row 2: s2_quarterly R6 — 2 years prior only  ← NEW
# Row 3: annual R7
# Row 4: quarterly R8
# Row 5: monthly R9
ROWS = [
    ("s2q sampling", "R1 · R4 · R5", "", AMBER),
    ("single mean imagery", "R2 · R3", "", TEAL),
    ("s2q · extra temp. context", "R6", "", AMBER),
    ("annual steps", "R7", "", PURPLE),
    ("quarterly steps", "R8", "", CORAL),
    ("monthly steps", "R9", "", BLUE),
]
"""ROWS = [
    ("s2q", "R1 · R4 · R5", "M02 M05 M08 M11", AMBER),
    ("P1 · single mean", "R2 · R3", "M02 M05 M08 M11→composite", TEAL),
    ("s2q ·  R6", "2 years prior context", "M02 M05 M08 M11", AMBER),
    ("annual ·  R7", "mean of all 12 months / year", "3 timesteps total", PURPLE),
    ("quarterly ·  R8", "mean of 3 months / quarter", "12 timesteps total", CORAL),
    ("monthly ·  R9", "", "36 timesteps total", BLUE),
]"""
N_ROWS = len(ROWS)

FIG_W = LABEL_W + N_MONTHS * CELL_W + CH_W + 0.4
FIG_H = N_ROWS * (CELL_H + ROW_GAP) + 4.0

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=400)
ax.set_aspect('equal')
ax.set_xlim(-LABEL_W, N_MONTHS * CELL_W + CH_W + 0.2)
ax.set_ylim(-(N_ROWS * (CELL_H + ROW_GAP)) - 1.8, 2.0)
ax.axis('off')
fig.patch.set_facecolor(WHITE)

def row_y(ri):
    return -(ri * (CELL_H + ROW_GAP))

def col_x(mi):
    return mi * CELL_W

# ── Year header bands ─────────────────────────────────────────────────────────
year_colors = ["#E8E6DE", "#E8E6DE", "#F5DFD0", "#E8E6DE"]
year_labels = ["2022  (pre-disturbance)", "2023  (pre-disturbance)",
               "2024  (disturbance year)", "2025  (post-disturbance)"]
for yi in range(4):
    x0 = col_x(yi * 12)
    rect = mpatches.FancyBboxPatch(
        (x0 + 0.03, 0.32), 12*CELL_W - 0.06, 0.72,
        boxstyle="round,pad=0.04", linewidth=0.6,
        edgecolor=GRAY, facecolor=year_colors[yi])
    ax.add_patch(rect)
    ax.text(x0 + 6*CELL_W, 0.68, year_labels[yi],
            ha='center', va='center', fontsize=16,
            color=DARK_TEXT, fontweight='bold')

# ── Month letters ─────────────────────────────────────────────────────────────
for mi, lbl in enumerate(MONTHS_ABBR):
    ax.text(col_x(mi) + CELL_W/2, 0.14, lbl,
            ha='center', va='center', fontsize=8, color=DARK_TEXT)

# ── Vertical year separators ──────────────────────────────────────────────────
for yi in range(1, 4):
    x = col_x(yi * 12)
    ax.plot([x, x],
            [-(N_ROWS*(CELL_H+ROW_GAP)) - 0.15, 1.06],
            color=GRAY, linewidth=0.7, linestyle='--', alpha=0.6)

# ── Row backgrounds ───────────────────────────────────────────────────────────
for ri in range(N_ROWS):
    y = row_y(ri)
    shade = "#F1EFE8" if ri % 2 == 0 else WHITE
    ax.add_patch(mpatches.Rectangle(
        (-LABEL_W, y - CELL_H), LABEL_W + N_MONTHS*CELL_W + CH_W + 0.2, CELL_H,
        facecolor=shade, edgecolor='none', zorder=0))

# ── Helpers ───────────────────────────────────────────────────────────────────
def cell(ax, mi, ri, color, alpha=0.88):
    x = col_x(mi)
    y = row_y(ri) - CELL_H
    r = mpatches.FancyBboxPatch(
        (x + 0.03, y + 0.05), CELL_W - 0.06, CELL_H - 0.10,
        boxstyle="round,pad=0.03",
        facecolor=color, alpha=alpha,
        edgecolor=color,
        zorder=2)
    ax.add_patch(r)

def wide_cell(ax, m_start, m_end, ri, color, alpha=0.45,
              label=None, dashed=False, text_color=None):
    x  = col_x(m_start)
    y  = row_y(ri) - CELL_H
    w  = (m_end - m_start) * CELL_W - 0.06
    ls = (0, (4, 2)) if dashed else '-'
    r  = mpatches.FancyBboxPatch(
        (x + 0.03, y + 0.05), w, CELL_H - 0.10,
        boxstyle="round,pad=0.04",
        facecolor=color, alpha=alpha,
        edgecolor=color, linewidth=0.7,
        linestyle=ls, zorder=2)
    ax.add_patch(r)
    if label:
        tc = text_color or LIGHT_TEXT
        ax.text(x + w / 2, y + CELL_H / 2, label,
                ha='center', va='center',
                fontsize=14, color=tc, fontweight='bold', zorder=3)

def quarter_cell(ax, m_start, ri, color, alpha, label, highlight=False):
    x  = col_x(m_start)
    y  = row_y(ri) - CELL_H
    w  = 3 * CELL_W - 0.06
    lw = 1.0 if highlight else 0.5
    ec = color if highlight else color
    r  = mpatches.FancyBboxPatch(
        (x + 0.03, y + 0.05), w, CELL_H - 0.10,
        boxstyle="round,pad=0.04",
        facecolor=color, alpha=alpha,
        edgecolor=ec, linewidth=lw, zorder=2)
    ax.add_patch(r)
    tc = DARK_TEXT
    ax.text(x + w/2, y + CELL_H/2, label,
            ha='center', va='center',
            fontsize=14.0, color=tc, fontweight='bold', zorder=3)

# ── ROW 0: s2_quarterly (R1·R4·R5·R6 — 1yr window: 2023+2024+2025) ───────────
for yi in range(1, 4):
    for m in [1, 4, 7, 10]:
        cell(ax, yi*12 + m, 0, AMBER, alpha=0.92)

# ── ROW 1: P1 single mean ─────────────────────────────────────────────────────
for yi in [0, 1]:
    wide_cell(ax, yi*12, yi*12+12, 1, GRAY, alpha=0.10,
              label="not used", text_color=GRAY)

wide_cell(ax, 25, 26, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 28, 29, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 31, 32, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 34, 35, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 24, 36, 1, TEAL, alpha=0.30,
          label="R2 · mean 2024", text_color=DARK_TEXT)
wide_cell(ax, 37, 38, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 40, 41, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 43, 44, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 46, 47, 1, TEAL, alpha=0.55, text_color=LIGHT_TEXT)
wide_cell(ax, 36, 48, 1, TEAL, alpha=0.30,
          label="R3 · mean 2025", dashed=True, text_color=DARK_TEXT)

# ── ROW 2: s2_quarterly R6 — 2 years prior only (2022 + 2023) ── NEW ROW ─────
# Active: 2022 (yi=0) and 2023 (yi=1) quarters at M02/M05/M08/M11
for yi in range(0, 4):
    for m in [1, 4, 7, 10]:
        cell(ax, yi*12 + m, 2, AMBER, alpha=0.92)
# 2024 and 2025 — not used


# ── ROW 3: annual R7 — skip 2022 (no purple polygon there) ───────────────────
# Only draw 2023, 2024, 2025 (yi = 1, 2, 3)
labels_ann = {1: "mean 2023", 2: "mean 2024", 3: "mean 2025"}
for yi, lbl in labels_ann.items():
    wide_cell(ax, yi*12, yi*12+12, 3, PURPLE, alpha=0.38,
              label=lbl, text_color=LIGHT_TEXT)
# Arrow connectors between the 3 active year blocks
for yi in range(2, 4):
    xarr = col_x(yi*12) - 0.10
    yarr = row_y(3) - CELL_H/2
    ax.annotate("", xy=(xarr + 0.18, yarr), xytext=(xarr, yarr),
                arrowprops=dict(arrowstyle='->', color=PURPLE, lw=0.9))

# ── ROW 4: quarterly R8 ───────────────────────────────────────────────────────
for yi in range(1, 4):
    for q in range(4):
        m_start = yi*12 + q*3
        quarter_cell(ax, m_start, 4, CORAL,
                     alpha=0.28,
                     label=f"Q{q+1}")

# ── ROW 5: monthly R9 ─────────────────────────────────────────────────────────
for mi in range(12, 48):
    cell(ax, mi, 5, BLUE, alpha=0.28)

# ── Row labels ────────────────────────────────────────────────────────────────
for ri, (line1, line2, line3, color) in enumerate(ROWS):
    yc = row_y(ri) - CELL_H/2
    ax.text(-0.18, yc + 0.22, line1,
            ha='right', va='center', fontsize=15,
            color=color, fontweight='bold')
    ax.text(-0.18, yc + 0.00, line2,
            ha='right', va='center', fontsize=15, color=GRAY)
    ax.text(-0.18, yc - 0.22, line3,
            ha='right', va='center', fontsize=13, color=GRAY)

# ── Channel counts
ch_counts = [" ", "6 ch", "96 ch", "18 ch", "72 ch", "216 ch"]
for ri, (ch, (_, _, _, color)) in enumerate(zip(ch_counts, ROWS)):
    yc = row_y(ri) - CELL_H/2
    ax.text(N_MONTHS * CELL_W + 0.18, yc, ch,
            ha='left', va='center', fontsize=15,
            color=color, fontweight='bold')

# ── Title
ax.text(-LABEL_W + 7, 1.75,
        "",
        ha='left', va='center', fontsize=15,
        color=DARK_TEXT, fontweight='bold')

# ── Legend
legend_y  = row_y(N_ROWS) - 0.45
leg_items = [
    (AMBER,  "s2_quarterly  (R1 · R4 · R5 · R6)"),
    (TEAL,   "P1 single mean  (R2 · R3)"),
    (PURPLE, "annual  (R7)"),
    (CORAL,  "quarterly  (R8)"),
    (BLUE,   "monthly  (R9)"),
]
total_w = LABEL_W + N_MONTHS * CELL_W
col_w   = total_w / 3
for i, (color, label) in enumerate(leg_items):
    cx = -LABEL_W + (i % 3) * col_w + 5
    cy = legend_y - (i // 3) * 0.42
    sq = mpatches.FancyBboxPatch(
        (cx, cy - 0.14), 0.34, 0.28,
        boxstyle="round,pad=0.02",
        facecolor=color, edgecolor='none', alpha=0.88, zorder=3)
    ax.add_patch(sq)
    ax.text(cx + 0.48, cy, label,
            ha='left', va='center', fontsize=15, color=DARK_TEXT)



plt.tight_layout(pad=0.2)
plt.savefig(r"C:/Users/misko/Documents/Michal/Master/A_Thesis/Actual_Scripts/outputs/Final/temporal_sampling_v3.png",
            dpi=400, bbox_inches='tight', facecolor=WHITE)
print("Done.")