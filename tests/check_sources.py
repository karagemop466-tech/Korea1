"""Strict official/primary-source row check; an arbitrary external URL is not enough."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.verify_site import Collector,official_refs,ROOT
PAGES=["week-11.html","suggestions-hub.html","index.html","executive-summary.html","lines.html","price-snapshot.html","price-archive.html","results-feed.html","strategies.html","validation.html","audit.html",
       "correlations.html","props.html","methodology.html","requirements.html","verification.html",
       "flagged.html","sources.html","decisions.html","suggestions.html","questions.html",
       "lineups.html","injuries.html","availability.html","decision-board.html","open-questions.html",
       "suggestions-review.html","decision-readiness.html","lineup-deficiencies.html",
       "referents.html", "forward.html", "live-verification.html", "review.html",
       # X1-X4 (session arena/132e7ca2-korea1).
       "review-queue.html", "answers.html", "competition.html", "repo-review.html",
       # T43 (session arena/6b1f0c9a-korea1)
       "results-feed.html", "correlation-official.html", "replacement-depth.html",
       "origination.html", "price-annex.html", "signal-staking.html", "demotion.html",
       "suggestions-review-2026-11-14.html", "brief-2026-11-15.html",
       # CR1 (arena/f84bc1d7-korea1)
       "request-register.html", "request-register-2026-11-18.html", "requirement-annex-2026-11-18.html",
       # NR3-NR5 (arena/ceddf8d8-korea1, 2026-11-18): the verified register, the deficiency matrix and the
       # vig-free view — three pages, all built from committed artefacts, all carrying an official link per
       # row. Listed apart from CR1's and CS5's registers, which check the same request from the other side.
       "verified-register-2026-11-18.html", "matchup-matrix.html", "consensus.html",
       # RX1 (arena/7aae360e-korea1, 2026-11-18): the register evidence annex.
       "register-evidence-2026-11-18.html",
       # E5 (arena/eeba949e-korea1, 2026-11-19): the official Game Book evidence page.
       "gamebooks.html"]
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
