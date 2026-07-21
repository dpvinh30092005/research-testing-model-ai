#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate figures for the research proposal (PNG in RP/figures/)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import wilcoxon_test as wt  # reuse parsing (SHEET_MAP, get_viewpoints)

OUT = os.path.join(os.path.dirname(__file__), "../figures")
os.makedirs(OUT, exist_ok=True)

z, ss, sheets = wt.load()
data = wt.get_viewpoints(z, ss, sheets)

APPS = wt.REPRODUCED + wt.NEW
SHORT = {"Password strength checker": "Password", "Unit converter": "Unit conv.",
         "Budget planner": "Budget", "Library fine calculator": "Library fine",
         "Task manager": "Task mgr."}
MODEL_COLOR = {"GPT-5.5": "#1f4e79", "Sonnet 4.6": "#2e75b6", "Gemini 3.1": "#5b9bd5",
               "ChatGPT": "#9dc3e6", "ChatGPT-5.5": "#9dc3e6"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})


def cov_pct(app, src):
    d = data[app]; tot = len(d["vps"])
    return 100.0 * sum(1 for v in d["vps"] if v["cov"][src]) / tot


def union(app, group):
    d = data[app]; tot = len(d["vps"]); srcs = d[group]
    return 100.0 * sum(1 for v in d["vps"] if any(v["cov"][s] for s in srcs)) / tot


def combined(app):
    d = data[app]; tot = len(d["vps"])
    n = sum(1 for v in d["vps"] if any(v["cov"][s] for s in d["ai"]) or any(v["cov"][s] for s in d["human"]))
    return 100.0 * n / tot


# ---------- Fig 1: per-model vs best human, per application ----------
# IMPORTANT: the reproduced cohort (Password, Unit conv., Budget -- reused
# Human A-D + GPT-4 baseline from Kirinuki & Tanno, extended with newly-run
# GPT-5.5/Sonnet 4.6/Gemini 3.1) and the new cohort (Library fine, Task mgr.
# -- entirely newly-collected students vs. newly-run LLMs) are two
# methodologically different comparisons (see Section 4.2, "Data
# Provenance"). They must NOT be drawn as one combined bar chart, since that
# visually implies a single, homogeneous "AI vs human" experiment across all
# 5 apps. Each cohort gets its own figure.
def _fig1_for(apps, models, title, fname):
    import numpy as np
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    x = np.arange(len(apps))
    present = []
    for m in models:
        vals = [cov_pct(a, m) if m in data[a]["ai"] else None for a in apps]
        if any(v is not None for v in vals):
            present.append((m, vals))
    best_human = [max(cov_pct(a, h) for h in data[a]["human"]) for a in apps]
    n = len(present) + 1
    w = 0.8 / n
    for i, (m, vals) in enumerate(present):
        xs = [x[j] + (i - (n - 1) / 2) * w for j in range(len(apps))]
        ys = [v if v is not None else 0 for v in vals]
        ax.bar(xs, ys, w, label=m, color=MODEL_COLOR.get(m, "#888"))
    xs = [x[j] + (len(present) - (n - 1) / 2) * w for j in range(len(apps))]
    ax.bar(xs, best_human, w, label="Best human", color="#ed7d31")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[a] for a in apps])
    ax.set_ylabel("Viewpoint coverage (%)"); ax.set_ylim(0, 105)
    ax.set_title(title, fontsize=10)
    ax.legend(ncol=3, fontsize=8, loc="lower center", framealpha=0.9)
    fig.tight_layout(); fig.savefig(f"{OUT}/{fname}", dpi=150); plt.close(fig)


def fig1():
    _fig1_for(
        wt.REPRODUCED, ["GPT-5.5", "Sonnet 4.6", "Gemini 3.1", "ChatGPT"],
        "Figure 1a. Reproduced cohort: newly-added LLMs vs.\n"
        "reused Human A-D baseline (Kirinuki & Tanno)",
        "fig1a_coverage_reproduced.png",
    )
    _fig1_for(
        wt.NEW, ["Sonnet 4.6", "Gemini 3.1", "ChatGPT-5.5"],
        "Figure 1b. New cohort: newly-generated LLMs vs.\n"
        "newly-collected 3rd-year students",
        "fig1b_coverage_new.png",
    )


# ---------- Fig 2: synergy — stacked bar showing shared/AI-only/human-only/blind-spot ----------
# Same cohort-separation rule as fig1: reproduced (reused human baseline)
# and new (newly-collected human baseline) are plotted as two figures.
def _fig2_for(apps, title, fname):
    import numpy as np

    both, ai_only, hu_only, blind = [], [], [], []
    for a in apps:
        d = data[a]; tot = len(d["vps"])
        ai_set   = {i for i, v in enumerate(d["vps"]) if any(v["cov"][s] for s in d["ai"])}
        hu_set   = {i for i, v in enumerate(d["vps"]) if any(v["cov"][s] for s in d["human"])}
        all_set  = set(range(tot))
        both.append   (100 * len(ai_set & hu_set) / tot)
        ai_only.append(100 * len(ai_set - hu_set) / tot)
        hu_only.append(100 * len(hu_set - ai_set) / tot)
        blind.append  (100 * len(all_set - ai_set - hu_set) / tot)

    x  = np.arange(len(apps))
    w  = 0.5
    c1 = "#2e75b6"   # Covered by both
    c2 = "#9dc3e6"   # AI only
    c3 = "#f4b942"   # Human only
    c4 = "#c00000"   # Blind spot (neither)

    b1 = np.array(both)
    b2 = np.array(ai_only)
    b3 = np.array(hu_only)
    b4 = np.array(blind)

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.bar(x, b1,          w, label="Covered by BOTH",       color=c1)
    ax.bar(x, b2, w, bottom=b1,          label="AI only",          color=c2)
    ax.bar(x, b3, w, bottom=b1 + b2,     label="Human only",       color=c3)
    ax.bar(x, b4, w, bottom=b1 + b2 + b3, label="Blind spot (neither)", color=c4)

    for j in range(len(apps)):
        comb_val = 100 - blind[j]
        ax.text(x[j], 101, f"Combined={comb_val:.0f}%", ha="center", fontsize=8,
                fontweight="bold", color="#1a1a1a")

    ax.set_xticks(x); ax.set_xticklabels([SHORT[a] for a in apps], fontsize=10)
    ax.set_ylabel("Proportion of total viewpoints (%)"); ax.set_ylim(0, 110)
    ax.set_title(title, fontsize=10)
    ax.legend(ncol=2, fontsize=8, loc="lower center", framealpha=0.9)
    fig.tight_layout(); fig.savefig(f"{OUT}/{fname}", dpi=150); plt.close(fig)


def fig2():
    _fig2_for(
        wt.REPRODUCED,
        "Figure 2a. Synergy breakdown -- reproduced cohort\n(reused Human A-D baseline)",
        "fig2a_synergy_reproduced.png",
    )
    _fig2_for(
        wt.NEW,
        "Figure 2b. Synergy breakdown -- new cohort\n(newly-collected students)",
        "fig2b_synergy_new.png",
    )


# ---------- Fig 3: category-level AI - Human diff (Wilcoxon input) ----------
def fig3():
    ai, hu, names = wt.category_level(data, APPS)
    diffs = [100 * (a - h) for a, h in zip(ai, hu)]
    order = sorted(range(len(diffs)), key=lambda i: diffs[i])
    d = [diffs[i] for i in order]; nm = [names[i] for i in order]
    colors = ["#c00000" if v < 0 else ("#bfbfbf" if v == 0 else "#2e75b6") for v in d]
    fig, ax = plt.subplots(figsize=(9, 9.5))
    y = range(len(d))
    ax.barh(list(y), d, color=colors)
    ax.set_yticks(list(y)); ax.set_yticklabels(nm, fontsize=6.5)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Coverage difference (AI − Human), percentage points")
    ax.set_title("Figure 3. Per-category AI−Human coverage gap\n(all 5 apps; Wilcoxon exact p = 0.00002, AI > Human)")
    ax.margins(y=0.005)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig3_category_diff.png", dpi=150); plt.close(fig)


fig1(); fig2(); fig3()
print("figures written to", OUT)
for f in os.listdir(OUT):
    print(" -", f)
