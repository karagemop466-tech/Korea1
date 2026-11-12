"""Strict official/primary-source row check across all canonical root pages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.verify_site import Collector, ROOT, official_refs

PAGES = [
    "index.html", "executive-summary.html", "lines.html", "injuries.html", "lineups.html",
    "strategies.html", "validation.html", "correlations.html", "props.html",
    "questions.html", "suggestions.html", "decisions.html", "methodology.html",
    "requirements.html", "flagged.html", "sources.html", "audit.html", "verification.html",
]


def main():
    problems = []
    total = 0
    for name in PAGES:
        p = ROOT / name
        if not p.exists():
            problems.append(f"missing {name}")
            continue
        c = Collector()
        c.feed(p.read_text(encoding="utf-8"))
        total += len(c.rows)
        for i, row in enumerate(c.rows, 1):
            if not official_refs([h for _, hrefs in row for h in hrefs]):
                problems.append(f"{name} row {i}: no official/primary source")
        if c.captions != c.tables:
            problems.append(f"{name}: uncaptioned table")
    print(f"checked {len(PAGES)} canonical pages, {total} rows")
    for p in problems[:40]:
        print(p)
    print("strict official/primary reference check passed" if not problems else f"{len(problems)} failures")
    return bool(problems)


if __name__ == "__main__":
    sys.exit(main())
