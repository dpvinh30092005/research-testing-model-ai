#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wilcoxon signed-rank test (AI vs Human black-box viewpoint coverage).

Follows the method taught in note_for_research_3.pdf:
  1. diff_i = AI_i - Human_i for each paired unit
  2. drop zero differences (ties)
  3. rank the |diff| (average ranks for ties)
  4. W+ = sum of ranks with positive diff, W- = sum with negative diff
  5. W  = min(W+, W-)
  6. exact two-sided p = (# of the 2^n sign assignments whose min rank-sum <= W) / 2^n
     -- computed exactly with a DP over rank sums (ranks doubled to integers),
        which reproduces the note's 12/2^10 = 0.0117 example.

Pairing units used:
  Test 1  per application (n = 5)          mean-AI vs mean-Human coverage %
  Test 2  per category, reproduced apps    (consistent Kirinuki human baseline)
  Test 3  per category, all 5 apps pooled

Pure stdlib only.
"""

import zipfile, re
import xml.etree.ElementTree as ET
from math import erf, sqrt
from fractions import Fraction

import os
XLSX = os.path.join(os.path.dirname(__file__), "test perspective analysis 2.xlsx")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

SHEET_MAP = {
    "Password strength checker": {
        "ai": {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "J"},
        "human": {"H-A": "K", "H-B": "L", "H-C": "M", "H-D": "N"}},
    "Unit converter": {
        "ai": {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "J"},
        "human": {"H-A": "K", "H-B": "L", "H-C": "M", "H-D": "N"}},
    "Budget planner": {
        "ai": {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "I"},
        "human": {"H-A": "J", "H-B": "K", "H-C": "L", "H-D": "M"}},
    "Library fine calculator": {
        "ai": {"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        "human": {"S-A": "I", "S-B": "J", "S-C": "K"}},
    "Task manager": {
        "ai": {"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        "human": {"S-A": "I", "S-B": "J", "S-C": "K"}},
}
REPRODUCED = ["Password strength checker", "Unit converter", "Budget planner"]
NEW = ["Library fine calculator", "Task manager"]


def load():
    z = zipfile.ZipFile(XLSX)
    ss = []
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
        ss.append("".join(t.text or "" for t in si.iter(NS + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sheets = {s.get("name"): "xl/" + relmap[s.get(REL + "id")] for s in wb.iter(NS + "sheet")}
    return z, ss, sheets


def read_sheet(z, ss, target):
    rows = {}
    for c in ET.fromstring(z.read(target)).iter(NS + "c"):
        v = c.find(NS + "v")
        if v is None:
            continue
        val = ss[int(v.text)] if c.get("t") == "s" else v.text
        m = re.match(r"([A-Z]+)(\d+)", c.get("r"))
        rows.setdefault(int(m.group(2)), {})[m.group(1)] = val
    return rows


def covered(cell):
    return cell is not None and str(cell).strip().upper() == "OK"


def get_viewpoints(z, ss, sheets):
    """Return {app: {'ai':[labels], 'human':[labels], 'vps':[{cat, cov{label:bool}}]}}"""
    data = {}
    for app, cfg in SHEET_MAP.items():
        rows = read_sheet(z, ss, sheets[app])
        ai, hu = list(cfg["ai"]), list(cfg["human"])
        vps = []
        for rn in sorted(rows):
            if rn < 2:
                continue
            row = rows[rn]
            vp = (row.get("B") or "").strip()
            if not vp:
                continue
            cov = {}
            for lab, col in {**cfg["ai"], **cfg["human"]}.items():
                cov[lab] = covered(row.get(col))
            vps.append({"cat": (row.get("A") or "").strip(), "cov": cov})
        data[app] = {"ai": ai, "human": hu, "vps": vps}
    return data


# ---------------- Wilcoxon signed-rank (exact via DP) ----------------
def rankdata(vals):
    """Average ranks (1-based) of vals."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average of positions i..j (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def wilcoxon(ai, human):
    """ai, human: paired lists. Returns dict with W, p_exact, p_norm, n, direction."""
    diffs = [a - h for a, h in zip(ai, human)]
    nz = [d for d in diffs if d != 0]
    n = len(nz)
    if n == 0:
        return {"n": 0, "note": "all pairs tied"}
    absr = rankdata([abs(d) for d in nz])
    Wp = sum(r for r, d in zip(absr, nz) if d > 0)
    Wm = sum(r for r, d in zip(absr, nz) if d < 0)
    W = min(Wp, Wm)

    # exact two-sided p via DP over doubled ranks (ranks are multiples of 0.5)
    r2 = [int(round(r * 2)) for r in absr]
    total = sum(r2)
    dp = [0] * (total + 1)
    dp[0] = 1
    for r in r2:
        for s in range(total, r - 1, -1):
            dp[s] += dp[s - r]
    w2 = int(round(W * 2))
    count = 0
    for s in range(total + 1):
        if s <= w2 or s >= total - w2:
            count += dp[s]
    p_exact = Fraction(count, 2 ** n)

    # normal approximation with continuity correction (for cross-check)
    mu = n * (n + 1) / 4.0
    sigma = sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    z = (abs(W - mu) - 0.5) / sigma if sigma > 0 else 0.0
    p_norm = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))

    return {"n": n, "Wp": Wp, "Wm": Wm, "W": W,
            "p_exact": float(p_exact), "p_exact_frac": p_exact,
            "z": z, "p_norm": p_norm,
            "median_diff": sorted(diffs)[len(diffs) // 2],
            "mean_diff": sum(diffs) / len(diffs),
            "n_pos": sum(1 for d in diffs if d > 0),
            "n_neg": sum(1 for d in diffs if d < 0),
            "n_tie": sum(1 for d in diffs if d == 0)}


def fmt(res, label):
    print(f"\n[{label}]")
    if res.get("n", 0) == 0:
        print("  n=0 (all tied) - test not applicable")
        return
    print(f"  pairs: n={res['n']} usable  (+{res['n_pos']} AI>Human, -{res['n_neg']} Human>AI, ={res['n_tie']} tie)")
    print(f"  mean diff (AI-Human) = {res['mean_diff']:+.3f}   median diff = {res['median_diff']:+.3f}")
    print(f"  W+ = {res['Wp']:.1f}   W- = {res['Wm']:.1f}   W = {res['W']:.1f}")
    print(f"  EXACT two-sided p = {res['p_exact']:.5f}  ( = {res['p_exact_frac']} )")
    print(f"  normal-approx p   = {res['p_norm']:.5f}   (z={res['z']:.3f})")
    sig = "SIGNIFICANT (reject H0)" if res['p_exact'] < 0.05 else "not significant at 0.05"
    print(f"  -> {sig}")


# ---------------- build pairs ----------------
def app_level(data, apps):
    """One pair per app: mean AI coverage% vs mean Human coverage%."""
    ai_v, hu_v, names = [], [], []
    for app in apps:
        d = data[app]
        tot = len(d["vps"])
        ai_cov = [sum(1 for v in d["vps"] if v["cov"][s]) / tot for s in d["ai"]]
        hu_cov = [sum(1 for v in d["vps"] if v["cov"][s]) / tot for s in d["human"]]
        ai_v.append(sum(ai_cov) / len(ai_cov))
        hu_v.append(sum(hu_cov) / len(hu_cov))
        names.append(app)
    return ai_v, hu_v, names


def category_level(data, apps):
    """One pair per (app, category): mean AI cover-fraction vs mean Human cover-fraction."""
    ai_v, hu_v, names = [], [], []
    for app in apps:
        d = data[app]
        cats = {}
        for v in d["vps"]:
            cats.setdefault(v["cat"], []).append(v)
        for cat, vs in cats.items():
            tot = len(vs)
            ai_cov = [sum(1 for v in vs if v["cov"][s]) / tot for s in d["ai"]]
            hu_cov = [sum(1 for v in vs if v["cov"][s]) / tot for s in d["human"]]
            ai_v.append(sum(ai_cov) / len(ai_cov))
            hu_v.append(sum(hu_cov) / len(hu_cov))
            names.append(f"{app[:12]}::{cat[:22]}")
    return ai_v, hu_v, names


def show_pairs(ai, hu, names):
    print(f"  {'unit':<40}{'AI%':>8}{'Hum%':>8}{'diff':>8}")
    for a, h, n in zip(ai, hu, names):
        print(f"  {n:<40}{100*a:>7.1f}{100*h:>7.1f}{100*(a-h):>+8.1f}")


def main():
    z, ss, sheets = load()
    data = get_viewpoints(z, ss, sheets)

    print("=" * 70)
    print("SANITY CHECK - reproduce note example (n=10, expect p=0.0117)")
    ex_ai = [0.45, 0.49, 0.50, 0.36, 0.58, 0.53, 0.43, 0.47, 0.55, 0.40]
    ex_hu = [0.42, 0.51, 0.47, 0.33, 0.56, 0.49, 0.41, 0.45, 0.52, 0.38]
    fmt(wilcoxon(ex_ai, ex_hu), "note sanity check")

    print("\n" + "=" * 70)
    print("TEST 1 - per application (n=5): mean AI vs mean Human coverage")
    ai, hu, names = app_level(data, REPRODUCED + NEW)
    show_pairs(ai, hu, names)
    fmt(wilcoxon(ai, hu), "Test 1: all 5 apps")

    print("\n" + "=" * 70)
    print("TEST 2 - per category, REPRODUCED apps (consistent Kirinuki baseline)")
    ai, hu, names = category_level(data, REPRODUCED)
    show_pairs(ai, hu, names)
    fmt(wilcoxon(ai, hu), "Test 2: reproduced categories")

    print("\n" + "=" * 70)
    print("TEST 3 - per category, ALL 5 apps pooled")
    ai, hu, names = category_level(data, REPRODUCED + NEW)
    fmt(wilcoxon(ai, hu), "Test 3: all categories pooled")


if __name__ == "__main__":
    main()
