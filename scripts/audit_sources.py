#!/usr/bin/env python3
"""T10 audit: classify every table row on the root pages by the kind of source it links to.

Official = nfl.com / operations.nfl.com.  Community = github.com/nflverse (open-data mirror, NOT run
by the NFL).  The inventory is taken from the pages as published at BASELINE (the commit this audit started from),
so that adding the audit's own rows cannot change the counts it reports.
Output: data/audit/source_tier_inventory.csv
"""
BASELINE = "3453d41ddb9d81821fb3b01a762d9469b46a0301"
import csv, os, re, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index","executive-summary","lines","strategies","validation","correlations","props","methodology","flagged","sources"]
TBODY = re.compile(r"<tbody>(.*?)</tbody>", re.S); TR = re.compile(r"<tr>(.*?)</tr>", re.S)
HREF = re.compile(r'href="(https?://[^"]+)"')
out = []
for p in PAGES:
    t = subprocess.run(["git", "show", f"{BASELINE}:{p}.html"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    c = dict(rows=0, official=0, community=0, other_external=0, no_external=0)
    for body in TBODY.findall(t):
        for tr in TR.findall(body):
            if "<td" not in tr: continue
            c["rows"] += 1
            hosts = [re.sub(r"^https?://", "", h).split("/")[0] + ("/nflverse" if "github.com/nflverse" in h else "") for h in HREF.findall(tr)]
            if any(h.endswith("nfl.com") for h in hosts): c["official"] += 1
            elif any(h.endswith("/nflverse") for h in hosts): c["community"] += 1
            elif hosts: c["other_external"] += 1
            else: c["no_external"] += 1
    out.append(dict(page=p + ".html", **c))
tot = {k: sum(o[k] for o in out) for k in out[0] if k != "page"}
out.append(dict(page="TOTAL", **tot))
with open(os.path.join(ROOT, "data/audit/source_tier_inventory.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for o in out: print(o)
