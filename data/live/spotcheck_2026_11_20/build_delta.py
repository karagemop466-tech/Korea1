"""Compare the live Week 11 official read (w11_official_read.csv) with the stored
Week 10 capture (data/availability/injuries.csv). Publishes only what both sides
contain; anything unmatched is listed, never filled in."""
import csv, collections, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
EXPECTED = {"IND": 11, "HOU": 15, "PIT": 10, "PHI": 15}   # counts printed on the official page
w11 = list(csv.DictReader(open(pathlib.Path(__file__).with_name("w11_official_read.csv"))))
w10 = {}
for r in csv.DictReader(open(ROOT / "data/availability/injuries.csv")):
    if r["week"] == "WEEK 10":
        w10[(r["team"], r["player"])] = r
counts = collections.Counter(r["team"] for r in w11)
assert dict(counts) == EXPECTED, f"row-count drift vs official page: {dict(counts)}"
out = []
for r in w11:
    p = w10.get((r["team"], r["player"]))
    if p is None:
        out.append({**r, "w10_found": "no", "w10_injury": "", "w10_practice": "", "w10_game": "",
                    "changed_fields": "unmatched"})
        continue
    ch = [f for f, a, b in (("injury", p["injury"], r["injury"]),
                             ("practice", p["practice_status"], r["practice_status"]),
                             ("game_status", p["game_status"], r["game_status"])) if a != b]
    out.append({**r, "w10_found": "yes", "w10_injury": p["injury"], "w10_practice": p["practice_status"],
                "w10_game": p["game_status"], "changed_fields": ";".join(ch) or "none"})
fields = list(out[0].keys())
with open(pathlib.Path(__file__).with_name("w11_vs_w10_delta.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)
s = collections.Counter(("matched" if o["w10_found"] == "yes" else "unmatched") for o in out)
c = collections.Counter(o["changed_fields"] for o in out)
print("rows", len(out), dict(s)); print(dict(c))
