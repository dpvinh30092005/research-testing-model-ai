#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viewpoint-coverage analysis for
"A Comparative Study of GenAI-Generated and Human-Authored Black-Box Test Suites"

Reads "test perspective analysis 2.xlsx" and computes, per application and per
source (each LLM + each human tester), the metrics defined in the mentor's note:

    viewpoint coverage      = covered viewpoints / total viewpoints
    category coverage       = covered viewpoints in category / total in category
    missing rate            = missed viewpoints / total viewpoints
    unique contribution     = viewpoints covered ONLY by that source
    human-AI combined       = union(human) U union(AI) / total viewpoints
    overlap (AI n Human)    = viewpoints covered by >=1 AI and >=1 human / total

A viewpoint is "covered" by a source when its cell == "OK"
(i.e. the source produced >= 1 test case for that viewpoint).

Only pure-stdlib is used (zipfile + ElementTree) so no pip install is needed.
"""

import zipfile
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

import os
XLSX = os.path.join(os.path.dirname(__file__), "test perspective analysis 2.xlsx")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# --- Which columns hold which source, per sheet -----------------------------
# key = sheet name; value = dict(source_label -> column_letter)
# "kind" marks AI vs human so we can build union sets.
SHEET_MAP = {
    "Password strength checker": {
        "ai":    {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT (GPT-4)": "J"},
        "human": {"Human A": "K", "Human B": "L", "Human C": "M", "Human D": "N"},
        "effective": "O",
    },
    "Unit converter": {
        "ai":    {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT (GPT-4)": "J"},
        "human": {"Human A": "K", "Human B": "L", "Human C": "M", "Human D": "N"},
        "effective": "O",
    },
    "Budget planner": {
        "ai":    {"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT (GPT-4)": "I"},
        "human": {"Human A": "J", "Human B": "K", "Human C": "L", "Human D": "M"},
        "effective": "N",
    },
    "Library fine calculator": {
        "ai":    {"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        "human": {"Student A": "I", "Student B": "J", "Student C": "K"},  # only 3 students
        "effective": "L",
    },
    "Task manager": {
        "ai":    {"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        "human": {"Student A": "I", "Student B": "J", "Student C": "K"},  # only 3 students
        "effective": "L",
    },
}

# Which apps are reproduced from Kirinuki & Tanno vs newly added by the group
REPRODUCED = {"Password strength checker", "Unit converter", "Budget planner"}
NEW_SPECS = {"Library fine calculator", "Task manager"}


def load_workbook(path):
    z = zipfile.ZipFile(path)
    # shared strings
    ss = []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root:
        ss.append("".join(t.text or "" for t in si.iter(NS + "t")))
    # sheet name -> target xml
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sheets = {}
    for s in wb.iter(NS + "sheet"):
        rid = s.get(REL + "id")
        sheets[s.get("name")] = "xl/" + relmap[rid]
    return z, ss, sheets


def read_sheet(z, ss, target):
    """Return {row_number: {col_letter: value}}"""
    r = ET.fromstring(z.read(target))
    rows = {}
    for c in r.iter(NS + "c"):
        ref = c.get("r")
        v = c.find(NS + "v")
        if v is None:
            continue
        val = ss[int(v.text)] if c.get("t") == "s" else v.text
        m = re.match(r"([A-Z]+)(\d+)", ref)
        col, rn = m.group(1), int(m.group(2))
        rows.setdefault(rn, {})[col] = val
    return rows


def is_covered(cell):
    return cell is not None and str(cell).strip().upper() == "OK"


def analyze_sheet(name, rows, cfg):
    ai_cols = cfg["ai"]
    human_cols = cfg["human"]
    eff_col = cfg["effective"]

    data_rows = [rn for rn in sorted(rows) if rn >= 2]

    viewpoints = []   # list of dicts per viewpoint
    for rn in data_rows:
        row = rows[rn]
        category = (row.get("A") or "").strip()
        vp = (row.get("B") or "").strip()
        if not vp:
            continue  # skip blank rows
        eff_raw = (row.get(eff_col) or "").strip()
        effective = eff_raw == "1"
        cov = {}
        for label, col in {**ai_cols, **human_cols}.items():
            cov[label] = is_covered(row.get(col))
        viewpoints.append({
            "category": category,
            "vp": vp,
            "effective": effective,
            "cov": cov,
        })

    total = len(viewpoints)
    all_sources = list(ai_cols) + list(human_cols)

    # per-source coverage
    per_source = {}
    for src in all_sources:
        covered = sum(1 for v in viewpoints if v["cov"][src])
        per_source[src] = covered

    # unique contribution: covered by exactly one source (across ALL sources)
    unique = defaultdict(int)
    for v in viewpoints:
        holders = [s for s in all_sources if v["cov"][s]]
        if len(holders) == 1:
            unique[holders[0]] += 1

    # union sets
    ai_union = sum(1 for v in viewpoints if any(v["cov"][s] for s in ai_cols))
    human_union = sum(1 for v in viewpoints if any(v["cov"][s] for s in human_cols))
    combined = sum(1 for v in viewpoints
                   if any(v["cov"][s] for s in ai_cols) or any(v["cov"][s] for s in human_cols))
    overlap = sum(1 for v in viewpoints
                  if any(v["cov"][s] for s in ai_cols) and any(v["cov"][s] for s in human_cols))

    # category coverage per source
    cats = {}
    cat_names = []
    for v in viewpoints:
        c = v["category"] or "(uncategorised)"
        if c not in cats:
            cats[c] = {"total": 0, "src": {s: 0 for s in all_sources}}
            cat_names.append(c)
        cats[c]["total"] += 1
        for s in all_sources:
            if v["cov"][s]:
                cats[c]["src"][s] += 1

    return {
        "name": name,
        "total": total,
        "sources_ai": list(ai_cols),
        "sources_human": list(human_cols),
        "per_source": per_source,
        "unique": dict(unique),
        "ai_union": ai_union,
        "human_union": human_union,
        "combined": combined,
        "overlap": overlap,
        "cats": cats,
        "cat_names": cat_names,
    }


def pct(n, d):
    return f"{100.0*n/d:5.1f}%" if d else "  n/a"


def print_report(res):
    name = res["name"]
    total = res["total"]
    tag = "reproduced (Kirinuki & Tanno)" if name in REPRODUCED else "NEW spec (this study)"
    print("=" * 78)
    print(f"{name}  [{tag}]")
    print(f"  Total test viewpoints: {total}")
    print("-" * 78)
    print(f"  {'Source':<20}{'Covered':>9}{'Coverage':>11}{'Miss rate':>12}{'Unique':>9}")
    for grp, srcs in (("AI", res["sources_ai"]), ("HUMAN", res["sources_human"])):
        print(f"  --- {grp} ---")
        for s in srcs:
            cov = res["per_source"][s]
            miss = total - cov
            uni = res["unique"].get(s, 0)
            print(f"  {s:<20}{cov:>9}{pct(cov,total):>11}{pct(miss,total):>12}{uni:>9}")
    print("-" * 78)
    print(f"  AI union coverage      : {res['ai_union']:>3}/{total}  ({pct(res['ai_union'],total).strip()})")
    print(f"  Human union coverage   : {res['human_union']:>3}/{total}  ({pct(res['human_union'],total).strip()})")
    print(f"  Human+AI combined      : {res['combined']:>3}/{total}  ({pct(res['combined'],total).strip()})")
    print(f"  AI n Human overlap     : {res['overlap']:>3}/{total}  ({pct(res['overlap'],total).strip()})")
    print()


def print_category_table(res):
    print(f"  Category coverage - {res['name']}")
    srcs = res["sources_ai"] + res["sources_human"]
    hdr = "    " + f"{'Category':<42}{'N':>4}" + "".join(f"{s.split()[0][:7]:>8}" for s in srcs)
    print(hdr)
    for c in res["cat_names"]:
        cat = res["cats"][c]
        row = "    " + f"{c[:42]:<42}{cat['total']:>4}"
        for s in srcs:
            row += f"{cat['src'][s]:>8}"
        print(row)
    print()


def main():
    z, ss, sheets = load_workbook(XLSX)
    results = []
    for name, cfg in SHEET_MAP.items():
        if name not in sheets:
            print("!! sheet not found:", name)
            continue
        rows = read_sheet(z, ss, sheets[name])
        res = analyze_sheet(name, rows, cfg)
        results.append(res)

    print("\n########## PER-APPLICATION VIEWPOINT COVERAGE ##########\n")
    for res in results:
        print_report(res)

    print("\n########## CATEGORY BREAKDOWN ##########\n")
    for res in results:
        print_category_table(res)

    # ---- aggregate across the two cohorts -------------------------------
    print("\n########## AGGREGATE BY COHORT ##########\n")

    def aggregate(group):
        tot = sum(r["total"] for r in results if r["name"] in group)
        # average per-source coverage % (only sources present in every app of the group)
        common = None
        for r in results:
            if r["name"] in group:
                s = set(r["per_source"])
                common = s if common is None else (common & s)
        common = sorted(common or [])
        print(f"  Cohort total viewpoints: {tot}")
        for s in common:
            cov = sum(r["per_source"].get(s, 0) for r in results if r["name"] in group)
            print(f"    {s:<20}{cov:>4}/{tot}  {pct(cov,tot).strip()}")
        aiu = sum(r["ai_union"] for r in results if r["name"] in group)
        huu = sum(r["human_union"] for r in results if r["name"] in group)
        com = sum(r["combined"] for r in results if r["name"] in group)
        print(f"    {'AI union':<20}{aiu:>4}/{tot}  {pct(aiu,tot).strip()}")
        print(f"    {'Human union':<20}{huu:>4}/{tot}  {pct(huu,tot).strip()}")
        print(f"    {'Human+AI combined':<20}{com:>4}/{tot}  {pct(com,tot).strip()}")
        print()

    print("  >>> Reproduced apps (Kirinuki & Tanno human baseline):")
    aggregate(REPRODUCED)
    print("  >>> New apps (3rd-year student baseline):")
    aggregate(NEW_SPECS)


if __name__ == "__main__":
    main()
