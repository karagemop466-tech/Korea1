"""Strict official/primary-source row check; an arbitrary external URL is not enough."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.verify_site import Collector,official_refs,ROOT
PAGES=["index.html","executive-summary.html","lines.html","strategies.html","validation.html","audit.html",
       "correlations.html","props.html","methodology.html","requirements.html","flagged.html","sources.html","availability.html","decision-board.html","open-questions.html"]
def main():
    problems=[]; total=0
    for name in PAGES:
        p=ROOT/name
        if not p.exists(): problems.append(f"missing {name}"); continue
        c=Collector();c.feed(p.read_text());total+=len(c.rows)
        for i,row in enumerate(c.rows,1):
            if not official_refs([h for _,hrefs in row for h in hrefs]): problems.append(f"{name} row {i}: no official/primary source")
            if len(row)!=c.tables and False: pass
        if c.captions!=c.tables: problems.append(f"{name}: uncaptioned table")
    print(f"checked {len(PAGES)} canonical pages, {total} rows")
    for p in problems[:40]: print(p)
    print("strict official/primary reference check passed" if not problems else f"{len(problems)} failures")
    return bool(problems)
if __name__=="__main__":sys.exit(main())
