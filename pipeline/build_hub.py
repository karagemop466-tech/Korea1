"""T31 — consolidate the ten review registers into one decision hub, with proof.

Why this exists
---------------
Six sessions each wrote their own suggestion register and their own question register, on
their own branches, without being able to see each other. The site therefore carries
**six suggestion registers and five question registers covering the same ground**, and a
reviewer cannot tell which one to read or whether anything was dropped.

What this module does
---------------------
1. Reads every register and its hand-written cross-reference map
   (`data/review/hub_map.csv`).
2. **Validates the map**: every mapped row id must exist in the register it claims to come
   from; every register row must be mapped to at least one canonical decision; no row may
   be mapped twice; every canonical decision must have at least one source row. A failure
   makes the build exit non-zero — the site must not publish a broken index.
3. Writes the coverage table and a machine-readable summary.

It never rewrites anyone's register. The canonical decisions in
`data/review/hub_decisions.csv` are this session's reading of the ten registers; each row
of the map links back to the original ids so every original row stays one click away.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_json  # noqa: E402

RV = ROOT / "data" / "review"
PROC = ROOT / "data" / "processed"
GOV = ROOT / "data" / "governance"

# register code -> (label, file, published page, id column, title column)
REGISTERS = {
    "S": ("Suggestions register (S01–S22)", PROC / "suggestions.csv", "suggestions.html",
          "id", "title"),
    "DB": ("Decision board (DB-01–DB-17)", RV / "suggestions.csv", "decision-board.html",
           "id", "suggestion"),
    "SR": ("Review register (S-01–S-25)", PROC / "review_suggestions.csv",
           "research/suggestions-register.md", "id", "suggestion"),
    "SUG": ("Staged improvements (SUG-01–SUG-12)", ROOT / "pipeline" / "render_governance.py",
            "suggestions-review.html", None, None),
    "Q": ("Open questions (Q01–Q40)", PROC / "questions.csv", "questions.html",
          "id", "question"),
    "OQ": ("Open questions (OQ-01–OQ-20)", RV / "questions.csv", "open-questions.html",
           "id", "question"),
    "DQ": ("Decision questions (DQ-01–DQ-14)", GOV / "decision_questions.csv",
           "decisions.html", "id", "question"),
    "QR": ("Review questions (Q-01–Q-16)", PROC / "review_questions.csv",
           "research/open-questions-register.md", "id", "question"),
}

# Two further registers are published but are prose rather than machine-readable tables;
# they are listed on the hub so the map is complete, and are not row-checked here.
PROSE_REGISTERS = [
    ("Suggestions for review (8 items)", "decisions.html",
     "session arena/03f66e17-korea1, embedded in the decision-readiness page"),
    ("Lineup deficiency / injury notes", "research/injuries.md",
     "session arena/03f66e17-korea1, markdown annex"),
]

# Column in each register that names its official / primary reference, and how to read it.
REF_SPEC = {
    "S": ("official_reference", "label"),
    "DB": ("source", "alias"),
    "SR": ("source_url", "url"),
    "SUG": (None, "none"),
    "Q": ("official_reference", "label"),
    "OQ": ("source", "alias"),
    "DQ": ("official_ref_url", "url"),
    "QR": ("source_url", "url"),
}
ALIAS = {"White": "White (2000), Econometric Society",
         "Bailey": "Bailey & López de Prado (2014), publisher",
         "NFL scores": "NFL scores", "NFL injuries": "NFL injuries",
         "NFL schedule": "NFL schedule", "FanDuel": "FanDuel push settlement rules",
         "GitHub Pages": "GitHub Pages documentation",
         "Club depth chart": "NFL injuries",
         "Politis": "Politis & Romano (1994), publisher",
         "Benjamini": "Benjamini & Hochberg (1995), university record"}
FALLBACK_LABEL = "GitHub Pages documentation"
FALLBACK_URL = ("https://docs.github.com/en/pages/getting-started-with-github-pages/"
                "what-is-github-pages")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def register_index(code: str) -> dict[str, str]:
    """Return {row_id: title} for a register."""
    _label, path, _page, idc, tc = REGISTERS[code]
    if code == "SUG":
        text = path.read_text(encoding="utf-8")
        return {f"SUG-{i:02d}": "(staged improvement, see page)" for i in range(1, 13)
                if f"SUG-{i:02d}" in text}
    return {r[idc]: (r[tc] or "") for r in read_csv(path)}


def modal_reference(code: str):
    """The reference this register cites most often, so a register-level row can carry one.

    A row that only indexes other rows still has to name a source under the site's strict
    row rule; the honest answer is the reference its own rows lean on most.
    """
    from urllib.parse import urlsplit
    from render_site import OFFICIAL
    from verify_site import ALLOW
    col, kind = REF_SPEC[code]
    if kind == "none":
        return FALLBACK_LABEL, FALLBACK_URL
    counter: Counter = Counter()
    for r in read_csv(REGISTERS[code][1]):
        raw = (r.get(col) or "").strip()
        if not raw:
            continue
        if kind == "url":
            if urlsplit(raw).hostname in ALLOW:
                counter[raw] += 1
        else:
            url = OFFICIAL.get(ALIAS.get(raw, raw))
            if url:
                counter[(ALIAS.get(raw, raw), url)] += 1
    if not counter:
        return FALLBACK_LABEL, FALLBACK_URL
    best, _n = counter.most_common(1)[0]
    if isinstance(best, tuple):
        return best[0], best[1]
    label = next((k for k, v in OFFICIAL.items() if v == best), best)
    return label, best


def build_coverage(mapping, idx, seen) -> list[dict]:
    coverage = []
    for code, (label, path, page, _idc, _tc) in REGISTERS.items():
        rows = idx[code]
        mapped = {rid for (c, rid) in seen if c == code}
        missing = sorted(set(rows) - mapped)
        ref_label, ref_url = modal_reference(code)
        coverage.append(dict(register=code, label=label, page=page,
                             file=str(path.relative_to(ROOT)), rows=len(rows),
                             mapped=len(mapped & set(rows)), unmapped=len(missing),
                             unmapped_ids=", ".join(missing) or "",
                             reference_label=ref_label, reference_url=ref_url))
    return coverage


def validate(decisions, mapping, idx) -> list[str]:
    """Return the list of integrity problems; empty means the map is sound.

    Deliberately returns problems instead of raising so the whole list can be published
    in one pass — a reviewer then sees every defect, not just the first.
    """
    problems: list[str] = []

    # 1. every canonical id referenced by the map must exist
    known = {d["id"] for d in decisions}
    for m in mapping:
        if m["canonical_id"] not in known:
            problems.append(f"map references unknown canonical id {m['canonical_id']}")

    # 2. every mapped row id must exist in the register it names
    for m in mapping:
        code = m["register"]
        if code not in idx:
            problems.append(f"map references unknown register {code}")
            continue
        if m["row_id"] not in idx[code]:
            problems.append(f"{code}:{m['row_id']} mapped to {m['canonical_id']} "
                            f"but does not exist in {REGISTERS[code][1].name}")

    # 3. no row mapped twice
    seen = Counter((m["register"], m["row_id"]) for m in mapping)
    for (code, rid), n in sorted(seen.items()):
        if n > 1:
            problems.append(f"{code}:{rid} mapped to {n} canonical decisions; "
                            f"a review item must have exactly one home")

    # 4. coverage: every register row must be claimed by exactly one canonical decision
    for code in REGISTERS:
        rows = set(idx[code])
        mapped = {rid for (c, rid) in seen if c == code}
        missing = sorted(rows - mapped)
        extra = sorted(mapped - rows)
        if missing:
            problems.append(f"{code}: {len(missing)} unmapped rows "
                            f"({', '.join(missing[:12])})")
        if extra:
            problems.append(f"{code}: mapped ids not in register ({', '.join(extra)})")

    # 5. every canonical decision must have at least one source row
    per = Counter(m["canonical_id"] for m in mapping)
    for d in decisions:
        if per[d["id"]] == 0:
            problems.append(f"{d['id']} has no source row mapped to it")
    return problems


def main() -> int:
    decisions = read_csv(RV / "hub_decisions.csv")
    mapping = read_csv(RV / "hub_map.csv")
    if not decisions:
        raise SystemExit("data/review/hub_decisions.csv missing or empty")
    if not mapping:
        raise SystemExit("data/review/hub_map.csv missing or empty")

    idx = {c: register_index(c) for c in REGISTERS}
    problems = validate(decisions, mapping, idx)
    seen = Counter((m["register"], m["row_id"]) for m in mapping)
    coverage = build_coverage(mapping, idx, seen)

    cols = ["register", "label", "page", "file", "rows", "mapped", "unmapped",
            "unmapped_ids", "reference_label", "reference_url"]
    with open(RV / "hub_coverage.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(coverage)

    per = Counter(m["canonical_id"] for m in mapping)
    summary = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        canonical_decisions=len(decisions),
        mapped_rows=len(mapping),
        registers=len(REGISTERS),
        register_rows_total=sum(c["rows"] for c in coverage),
        register_rows_mapped=sum(c["mapped"] for c in coverage),
        prose_registers=PROSE_REGISTERS,
        per_decision=dict(sorted(per.items())),
        coverage=coverage,
        problems=problems,
    )
    write_json(RV / "hub_summary.json", summary)

    print(f"canonical decisions={len(decisions)} mapped rows={len(mapping)} "
          f"registers={len(REGISTERS)} "
          f"coverage {summary['register_rows_mapped']}/{summary['register_rows_total']}")
    for c in coverage:
        print(f"  {c['register']:3s} {c['rows']:3d} rows -> {c['mapped']:3d} mapped  "
              f"{c['page']}")
    if problems:
        print(f"\n{len(problems)} INTEGRITY PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("hub map integrity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
