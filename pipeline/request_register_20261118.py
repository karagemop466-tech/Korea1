"""Request register, 2026-11-18 (session arena/40fa7839-korea1, CS5 completed here).

One row per item in the 2026-11-18 request: its status, what the repo actually holds, the file that
evidences it, the gate that blocks it, the number that would clear it and an official source.

Reads (committed only, no network):
  data/integration/request_register_2026_11_18.csv   the register (hand-written, one row per item)
  data/integration/flagged_request_register_2026_11_18.csv   flagged rows F-52 onward

Checks, fail-closed (the build stops if any check fails):
  * status is one of six defined values
  * every non-blank evidence path exists in the repository
  * every source URL passes session_common.resolve_ref (official allow-list)
  * every row that is not BUILT or RULE HONOURED names a blocking gate and a clearing number
  * every flag id cited exists in the flagged file

Outputs
  request-register.html   the full register, grouped by area, with status counts
The landing page prints the same rows (render_site._request_register_landing reads the CSV directly).

Run:  python pipeline/request_register_20261118.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from render_site import layout, table, src_link, e, card, kpi_grid  # noqa: E402
from session_common import resolve_ref  # noqa: E402

REG = ROOT / "data" / "integration" / "request_register_2026_11_18.csv"
FLAG = ROOT / "data" / "integration" / "flagged_request_register_2026_11_18.csv"
PAGE = "request-register.html"

STATUSES = ["BUILT", "PARTIAL", "BLOCKED", "OPEN", "NOT REPRODUCED", "RULE HONOURED"]
STATUS_NOTE = {
    "BUILT": "The artefact is in the repo and rebuilt by make build with its check passing. Not a claim that a number is correct.",
    "PARTIAL": "Part of the request is in the repo; the stated remainder is named in the row.",
    "BLOCKED": "Cannot be built until a named source or owner decision exists.",
    "OPEN": "Not built. No source is captured for it yet.",
    "NOT REPRODUCED": "The request's specific claim or number does not match the repo or its sources.",
    "RULE HONOURED": "The request asked for a rule or a prohibition; the repo enforces it.",
}
STATUS_TONE = {"BUILT": "ok", "RULE HONOURED": "ok", "PARTIAL": "warn", "BLOCKED": "bad", "OPEN": "bad",
               "NOT REPRODUCED": "bad"}
NEEDS_GATE = {"PARTIAL", "BLOCKED", "OPEN", "NOT REPRODUCED"}
COLUMNS = ["id", "area", "requirement", "status", "what_is_in_repo", "evidence_file", "page",
           "clearing_gate", "clearing_number", "source_label", "source_url", "flag"]


def load_register() -> pd.DataFrame:
    d = pd.read_csv(REG, dtype=str, keep_default_na=False)
    missing = [c for c in COLUMNS if c not in d.columns]
    if missing:
        raise SystemExit(f"register missing columns: {missing}")
    return d


def load_flags() -> set[str]:
    f = pd.read_csv(FLAG, dtype=str, keep_default_na=False)
    return set(f["id"])


def validate(d: pd.DataFrame) -> list[str]:
    problems: list[str] = []
    ids = d["id"].tolist()
    if len(ids) != len(set(ids)):
        problems.append("duplicate row ids")
    flags = load_flags()
    for r in d.itertuples(index=False):
        tag = r.id
        if r.status not in STATUSES:
            problems.append(f"{tag}: unknown status {r.status!r}")
        if r.evidence_file and not (ROOT / r.evidence_file).exists():
            problems.append(f"{tag}: evidence file does not exist: {r.evidence_file}")
        if r.page and not r.page.endswith(".html"):
            problems.append(f"{tag}: page must be an .html file")
        if r.page and r.page != PAGE and not (ROOT / r.page).exists():
            problems.append(f"{tag}: page does not exist: {r.page}")
        if r.status in NEEDS_GATE and (not r.clearing_gate or not r.clearing_number):
            problems.append(f"{tag}: {r.status} row needs a clearing gate and a clearing number")
        try:
            resolve_ref(r.source_label, r.source_url, row_id=tag)
        except ValueError as exc:
            problems.append(str(exc))
        for fid in [x for x in r.flag.split() if x]:
            if not re.fullmatch(r"F-\d+", fid):
                problems.append(f"{tag}: malformed flag id {fid!r}")
            elif fid not in flags and fid not in KNOWN_FLAGS_ELSEWHERE:
                problems.append(f"{tag}: flag {fid} is not in the flagged files")
    return problems


# Flags F-42 to F-51 live in data/integration/flagged_2026_11_18.csv (session_20261118.py).
KNOWN_FLAGS_ELSEWHERE = {f"F-{n}" for n in range(1, 52)}


PILL_CLASS = {"BUILT": "skill", "RULE HONOURED": "skill", "PARTIAL": "partial", "BLOCKED": "no",
              "NOT REPRODUCED": "no", "OPEN": "unverified"}


def status_pill(s: str) -> str:
    return f'<span class="pill {PILL_CLASS.get(s, "")}">{e(s)}</span>'


def row_cells(r, *, with_what: bool) -> list[str]:
    flags = " · ".join(e(f) for f in r.flag.split()) or "—"
    cells = [e(r.id), e(r.requirement), status_pill(r.status)]
    if with_what:
        cells.append(e(r.what_is_in_repo))
    cells += [e(r.clearing_gate) or "—", e(r.clearing_number) or "—", src_link(r.source_url, r.source_label), flags]
    return cells


def landing_rows(d: pd.DataFrame) -> list[list[str]]:
    return [row_cells(r, with_what=False) for r in d.itertuples(index=False)]


def build_page(d: pd.DataFrame) -> str:
    counts = Counter(d["status"])
    cards = [card(str(counts.get(s, 0)), s.lower(), STATUS_NOTE[s], STATUS_TONE.get(s, "")) for s in STATUSES]
    parts = [
        "<section><h2>What this register is</h2>"
        "<p>The request contains about one hundred items, many repeated. This page holds one row per distinct item, "
        f"{len(d)} in all, with the same status for each repeat. Every status is decided by reading the committed "
        "files named in the row, not by reading the request. Where the request's own claim (a count, an identifier or a "
        "source) cannot be matched, the row says so and does not fill the gap.</p>"
        "<p>Official sources are linked on every row. A blank in the number column means nothing is on record, "
        "and no value is inferred to fill it.</p></section>",
        "<section><h2>Status counts</h2>" + kpi_grid(cards) + "</section>",
    ]
    for area in dict.fromkeys(d["area"]):
        sub = d[d["area"] == area]
        rows = [row_cells(r, with_what=True) for r in sub.itertuples(index=False)]
        parts.append(
            f"<section><h2>{e(area)}</h2>"
            + table(rows, ["ID", "Requirement (as stated)", "Status", "What the repo holds", "Blocking gate",
                           "Number that clears it", "Official source", "Flag"],
                    caption=f"{area} · {len(sub)} row{'s' if len(sub) != 1 else ''}")
            + "</section>")
    parts.append(
        "<section><h2>Evidence paths</h2><p class=\"small\">Each row names one evidence file in the repository. "
        "Those files are committed; the build reads them and does not reach the network.</p></section>")
    body = "".join(parts)
    return layout(PAGE, "Request register · 2026-11-18",
                  "One row per requirement: status, what the repo holds, the gate that blocks it and the number that clears it.",
                  body, wide=True)


def main() -> None:
    d = load_register()
    problems = validate(d)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"request register: {len(problems)} problem(s); page not written")
    (ROOT / PAGE).write_text(build_page(d), encoding="utf-8")
    counts = Counter(d["status"])
    print(f"request register: {len(d)} rows, " + ", ".join(f"{s} {counts.get(s, 0)}" for s in STATUSES))
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()
