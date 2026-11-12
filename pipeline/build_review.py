"""Build the review registers: suggestions.csv and open_questions.csv.

The registers are editorial documents, so they are stored as markdown in
`research/` (editable, reviewable, diffable) and converted to CSV here. The same
rule the rest of the project follows applies: the published table is generated,
never hand-written, and the build refuses a register that does not satisfy the
invariants the pages claim.

Run:  python pipeline/build_review.py
Out:  data/processed/review_suggestions.csv
      data/processed/review_questions.csv
      data/processed/review_validation.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, write_json  # noqa: E402

SUGGESTIONS_MD = ROOT / "research" / "suggestions-register.md"
QUESTIONS_MD = ROOT / "research" / "open-questions-register.md"

# Hosts that count as official / primary for the review registers. A row whose
# source is not on this list must say so in plain text, which the build checks.
OFFICIAL_HOSTS = {
    "www.nfl.com", "nfl.com", "operations.nfl.com", "www.econometricsociety.org",
    "www.pm-research.com", "cris.tau.ac.il", "www.tandfonline.com",
    "support.fanduel.com", "docs.github.com",
}

SUGGESTION_STATUS = {"Proposed", "Under review", "Accepted", "Rejected", "Implemented"}
SUGGESTION_PRIORITY = {"P0 blocking", "P1 high", "P2 medium", "P3 low"}
SUGGESTION_COST = {"Low", "Medium", "High"}
QUESTION_STATUS = {"Open", "Answered", "Superseded"}
QUESTION_SEVERITY = {"Blocking", "High", "Medium", "Low"}
QUESTION_EFFORT = {"Low", "Medium", "High"}

REQUIRED_SUGGESTION = ["id", "area", "suggestion", "why_it_matters", "evidence_we_have",
                       "evidence_missing", "how_to_verify", "cost_risk", "priority", "status",
                       "linked_question", "source_url"]
REQUIRED_QUESTION = ["id", "blocking_decision", "question", "what_we_know", "what_we_dont_know",
                     "how_to_find_out", "effort", "severity", "status", "linked_suggestion",
                     "source_url"]


def parse_pipe_table(path: Path):
    """Return (header, rows) from the first markdown pipe table in the file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and line.strip().endswith("|"):
            start = i
            break
    if start is None:
        raise ValueError(f"no pipe table found in {path.name}")
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    rows = []
    for line in lines[start + 1:]:
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # separator row
        if cells == header:
            continue
        rows.append(cells)
    return header, rows


def check_row(name, header, cells, problems):
    if len(cells) != len(header):
        problems.append(f"{name}: row has {len(cells)} cells, header has {len(header)}")
        return None
    return dict(zip(header, cells))


def official_or_flagged(row: dict, problems, name: str) -> None:
    url = (row.get("source_url") or "").strip()
    if not url:
        problems.append(f"{name} {row.get('id')}: empty source_url")
        return
    if not re.match(r"^https://", url):
        problems.append(f"{name} {row.get('id')}: source_url is not https: {url!r}")
        return
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if host in OFFICIAL_HOSTS:
        return
    blob = " ".join(v for k, v in row.items() if k != "source_url")
    if re.search(r"no official source", blob, re.I):
        return
    problems.append(f"{name} {row.get('id')}: source host {host!r} is not official/primary "
                    f"and the row does not state that no official source was verified")


def build() -> None:
    problems: list[str] = []

    # ---------------- suggestions ----------------
    s_header, s_rows = parse_pipe_table(SUGGESTIONS_MD)
    if s_header != REQUIRED_SUGGESTION:
        problems.append(f"suggestions header mismatch: {s_header}")
    s_df = pd.DataFrame([check_row("suggestions", s_header, r, problems) for r in s_rows])
    s_df = s_df.dropna(how="all")
    if s_df.empty:
        problems.append("suggestions register is empty")
    for col in ("id", "area", "suggestion", "why_it_matters", "evidence_we_have",
                "evidence_missing", "how_to_verify", "source_url"):
        if col in s_df and s_df[col].astype(str).str.strip().eq("").any():
            bad = s_df.loc[s_df[col].astype(str).str.strip().eq(""), "id"].tolist()
            problems.append(f"suggestions: empty required column {col!r} for {bad}")
    if "id" in s_df:
        if s_df.id.duplicated().any():
            problems.append("suggestions: duplicate ids")
        if not s_df.id.str.match(r"^S-\d{2}$").all():
            problems.append("suggestions: ids must look like S-01")
    for col, allowed in (("status", SUGGESTION_STATUS), ("priority", SUGGESTION_PRIORITY),
                         ("cost_risk", SUGGESTION_COST)):
        if col in s_df and not s_df[col].isin(allowed).all():
            problems.append(f"suggestions: {col} has values outside {sorted(allowed)}")
    for _, r in s_df.iterrows():
        official_or_flagged(r.to_dict(), problems, "suggestions")

    # ---------------- questions ----------------
    q_header, q_rows = parse_pipe_table(QUESTIONS_MD)
    if q_header != REQUIRED_QUESTION:
        problems.append(f"questions header mismatch: {q_header}")
    q_df = pd.DataFrame([check_row("questions", q_header, r, problems) for r in q_rows])
    q_df = q_df.dropna(how="all")
    if q_df.empty:
        problems.append("questions register is empty")
    for col in ("id", "blocking_decision", "question", "what_we_know", "what_we_dont_know",
                "how_to_find_out", "source_url"):
        if col in q_df and q_df[col].astype(str).str.strip().eq("").any():
            bad = q_df.loc[q_df[col].astype(str).str.strip().eq(""), "id"].tolist()
            problems.append(f"questions: empty required column {col!r} for {bad}")
    if "id" in q_df:
        if q_df.id.duplicated().any():
            problems.append("questions: duplicate ids")
        if not q_df.id.str.match(r"^Q-\d{2}$").all():
            problems.append("questions: ids must look like Q-01")
    for col, allowed in (("status", QUESTION_STATUS), ("severity", QUESTION_SEVERITY),
                         ("effort", QUESTION_EFFORT)):
        if col in q_df and not q_df[col].isin(allowed).all():
            problems.append(f"questions: {col} has values outside {sorted(allowed)}")
    for _, r in q_df.iterrows():
        official_or_flagged(r.to_dict(), problems, "questions")

    # ---------------- cross references ----------------
    s_ids = set(s_df.id) if "id" in s_df else set()
    q_ids = set(q_df.id) if "id" in q_df else set()
    if "linked_question" in s_df:
        for ref in s_df.linked_question.dropna().unique():
            if ref and ref not in q_ids:
                problems.append(f"suggestions: linked_question {ref!r} does not exist")
    if "linked_suggestion" in q_df:
        for ref in q_df.linked_suggestion.dropna().unique():
            for one in re.split(r"[,;]\s*", str(ref)):
                if one and one not in s_ids:
                    problems.append(f"questions: linked_suggestion {one!r} does not exist")

    # ---------------- write ----------------
    s_df.to_csv(PROC / "review_suggestions.csv", index=False)
    q_df.to_csv(PROC / "review_questions.csv", index=False)

    pd.DataFrame([{"register": "suggestions", "rows": int(len(s_df))},
                  {"register": "open_questions", "rows": int(len(q_df))},
                  {"register": "validation", "problems": len(problems)}]).to_csv(
        PROC / "review_validation.csv", index=False)
    write_json(PROC / "review_summary.json", {
        "suggestions": int(len(s_df)),
        "open_questions": int(len(q_df)),
        "blocking_questions": int((q_df.severity == "Blocking").sum()) if "severity" in q_df else 0,
        "implemented_suggestions": int((s_df.status == "Implemented").sum()) if "status" in s_df else 0,
        "proposed_suggestions": int((s_df.status == "Proposed").sum()) if "status" in s_df else 0,
    })

    for p in problems:
        print("PROBLEM:", p)
    print(f"suggestions: {len(s_df)} rows · open questions: {len(q_df)} rows · "
          f"{len(problems)} problems")
    if problems:
        raise SystemExit("review register validation failed")


if __name__ == "__main__":
    build()
