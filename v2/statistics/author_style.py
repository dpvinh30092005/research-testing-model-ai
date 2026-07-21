#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reproduce Kirinuki & Tanno's analysis style (their Table 2 / Figure 3) on our data.

Key points of the author's method:
  * Coverage is measured over EFFECTIVE viewpoints only
    (viewpoints covered by >=2 of the suites; the "Effective viewpoint?"=1 column).
  * Viewpoints are split into Basic vs Extracted type
    (Basic = category starting with "Basic Viewpoint"; else Extracted).
  * For each human X, a collaboration column X+ = union(X, ChatGPT) is reported.
  * Headline series: ChatGPT %, Participants avg %, Participants+ChatGPT avg %.

We extend it to the newer models (GPT-5.5, Sonnet 4.6, Gemini 3.1) and the two new apps.
Pure stdlib.
"""
import zipfile, re
import xml.etree.ElementTree as ET

import os
XLSX = os.path.join(os.path.dirname(__file__), "test perspective analysis 2.xlsx")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# columns per sheet: ai models, humans, effective flag, and which AI is the "ChatGPT" partner
SHEET_MAP = {
    "Password strength checker": dict(
        ai={"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "J"},
        human={"A": "K", "B": "L", "C": "M", "D": "N"}, eff="O", partner="ChatGPT"),
    "Unit converter": dict(
        ai={"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "J"},
        human={"A": "K", "B": "L", "C": "M", "D": "N"}, eff="O", partner="ChatGPT"),
    "Budget planner": dict(
        ai={"GPT-5.5": "D", "Sonnet 4.6": "F", "Gemini 3.1": "H", "ChatGPT": "I"},
        human={"A": "J", "B": "K", "C": "L", "D": "M"}, eff="N", partner="ChatGPT"),
    "Library fine calculator": dict(
        ai={"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        human={"A": "I", "B": "J", "C": "K"}, eff="L", partner="ChatGPT-5.5"),
    "Task manager": dict(
        ai={"Sonnet 4.6": "D", "Gemini 3.1": "F", "ChatGPT-5.5": "H"},
        human={"A": "I", "B": "J", "C": "K"}, eff="L", partner="ChatGPT-5.5"),
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


def ok(cell):
    return cell is not None and str(cell).strip().upper() == "OK"


def get(z, ss, sheets):
    data = {}
    for app, cfg in SHEET_MAP.items():
        rows = read_sheet(z, ss, sheets[app])
        vps = []
        for rn in sorted(rows):
            if rn < 2:
                continue
            row = rows[rn]
            vp = (row.get("B") or "").strip()
            if not vp:
                continue
            cat = (row.get("A") or "").strip()
            eff = (row.get(cfg["eff"]) or "").strip() == "1"
            cov = {lab: ok(row.get(col)) for lab, col in {**cfg["ai"], **cfg["human"]}.items()}
            typ = "Basic" if cat.lower().startswith("basic") else "Extracted"
            vps.append(dict(cat=cat, typ=typ, eff=eff, cov=cov))
        data[app] = dict(cfg=cfg, vps=vps)
    return data


def covered(vps, src, typ=None):
    sel = [v for v in vps if v["eff"] and (typ is None or v["typ"] == typ)]
    return sum(1 for v in sel if v["cov"][src])


def covered_union(vps, srcs, typ=None):
    sel = [v for v in vps if v["eff"] and (typ is None or v["typ"] == typ)]
    return sum(1 for v in sel if any(v["cov"][s] for s in srcs))


def eff_total(vps, typ=None):
    return sum(1 for v in vps if v["eff"] and (typ is None or v["typ"] == typ))


def table2(data, apps, title, collab=True):
    print("=" * 100)
    print(f"AUTHOR-STYLE TABLE 2 — {title}")
    note = "X+ = union of human X with ChatGPT (author's collaboration construct)" if collab \
        else "no fixed AI partner in this cohort -> synergy reported as Human+AI union only"
    print("(covered EFFECTIVE viewpoints; " + note + ")")
    print("=" * 100)
    # collect union of humans/models present
    grand = {}
    for app in apps:
        d = data[app]; cfg = d["cfg"]; vps = d["vps"]
        partner = cfg["partner"]
        humans = list(cfg["human"])
        models = list(cfg["ai"])
        print(f"\n### {app}")
        E = eff_total(vps); Eb = eff_total(vps, "Basic"); Ee = eff_total(vps, "Extracted")
        print(f"  effective viewpoints: Basic={Eb}  Extracted={Ee}  All={E}")
        # header
        cols = models + humans + ([h + "+" for h in humans] if collab else [])
        print(f"  {'type':<10}" + "".join(f"{c:>9}" for c in cols))
        for typ, lab in [("Basic", "Basic"), ("Extracted", "Extracted"), (None, "All")]:
            vals = []
            for m in models:
                vals.append(covered(vps, m, typ))
            for h in humans:
                vals.append(covered(vps, h, typ))
            if collab:
                for h in humans:
                    vals.append(covered_union(vps, [h, partner], typ))
            print(f"  {lab:<10}" + "".join(f"{v:>9}" for v in vals))
        # store for grand totals (All only)
        grand[app] = dict(E=E, partner=partner, humans=humans, models=models, vps=vps)
    # grand totals + percentages
    print("\n" + "-" * 100)
    print("TOTAL over effective viewpoints (All):")
    Etot = sum(g["E"] for g in grand.values())
    # per model total (only models present in every app of the set)
    common_models = set.intersection(*[set(g["models"]) for g in grand.values()])
    order_models = [m for m in ["GPT-5.5", "Sonnet 4.6", "Gemini 3.1", "ChatGPT", "ChatGPT-5.5"] if m in common_models]
    for m in order_models:
        c = sum(covered(g["vps"], m) for g in grand.values())
        print(f"  {m:<22}{c:>4}/{Etot}   {100*c/Etot:5.1f}%")
    # participants avg and participants+partner avg
    part_pcts, coll_pcts = [], []
    for h in ["A", "B", "C", "D"]:
        if all(h in g["humans"] for g in grand.values()):
            c = sum(covered(g["vps"], h) for g in grand.values())
            part_pcts.append(100 * c / Etot)
            if collab:
                cc = sum(covered_union(g["vps"], [h, g["partner"]]) for g in grand.values())
                coll_pcts.append(100 * cc / Etot)
                print(f"  Human {h:<10}{c:>4}/{Etot}   {100*c/Etot:5.1f}%     +ChatGPT: {cc:>3}/{Etot}  {100*cc/Etot:5.1f}%")
            else:
                print(f"  Human {h:<10}{c:>4}/{Etot}   {100*c/Etot:5.1f}%")
    ai_union_total = sum(covered_union(g["vps"], g["models"]) for g in grand.values())
    human_union_total = sum(covered_union(g["vps"], g["humans"]) for g in grand.values())
    combined_total = sum(covered_union(g["vps"], g["models"] + g["humans"]) for g in grand.values())
    print("-" * 100)
    if collab:
        partner_total = sum(covered(g["vps"], g["partner"]) for g in grand.values())
        print(f"  ChatGPT (partner = GPT-4)  {partner_total:>4}/{Etot}   {100*partner_total/Etot:5.1f}%")
    if part_pcts:
        print(f"  Human avg.                              {sum(part_pcts)/len(part_pcts):5.1f}%")
    if collab and coll_pcts:
        print(f"  Human + ChatGPT avg.                    {sum(coll_pcts)/len(coll_pcts):5.1f}%   <-- author's key synergy number")
    print(f"  AI union (all models)      {ai_union_total:>4}/{Etot}   {100*ai_union_total/Etot:5.1f}%")
    print(f"  Human union                {human_union_total:>4}/{Etot}   {100*human_union_total/Etot:5.1f}%")
    print(f"  Human + AI union combined  {combined_total:>4}/{Etot}   {100*combined_total/Etot:5.1f}%")


def minutes():
    print("\n" + "=" * 100)
    print("MANUAL TEST-DESIGN TIME (minutes) — author reported avg 198 min for 3 apps")
    z = zipfile.ZipFile(XLSX)
    ss = []
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
        ss.append("".join(t.text or "" for t in si.iter(NS + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    tgt = None
    for s in wb.iter(NS + "sheet"):
        if s.get("name") == "minutes for manual test design":
            tgt = "xl/" + relmap[s.get(REL + "id")]
    rows = read_sheet(z, ss, tgt)
    for rn in sorted(rows):
        vals = [rows[rn].get(c, "") for c in "ABCDEF"]
        print("  " + " | ".join(f"{v:>10}" for v in vals))


def main():
    z, ss, sheets = load()
    data = get(z, ss, sheets)
    table2(data, REPRODUCED, "REPRODUCED apps (Kirinuki human baseline) — compare directly to their Table 2", collab=True)
    table2(data, NEW, "NEW apps (3 students, written WITHOUT AI) — our extension", collab=False)
    minutes()


if __name__ == "__main__":
    main()
