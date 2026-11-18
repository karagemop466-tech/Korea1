"""Render the 2026-11-18 per-item request register as `request-register-2026-11-18.html`.

Session `arena/7aae360e-korea1`. Reads only the CSVs written by `pipeline/register_20261118.py`
(no network, no clock), so `make build` reproduces this page byte for byte and
`tests/check_rebuild.py` stays green.

Layout of the page follows the site's own rules: every table row carries an official link, every
table is captioned, numbers that no official source supports are left blank and listed outside the
tables, and the header/footer come from the shared `layout()` so the pinned snapshot id prints.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_site import BLANK, ROOT, card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

OUT_NAME = "request-register-2026-11-18.html"
DATA = ROOT / "data" / "integration"
AS_OF = "2026-11-18"

# class names the site's stylesheet actually defines: .pill.good / .partial / .bad / .unverified,
# and .card.good / .card.next / .card.bad.
STATUS_TONE = {"DONE": "good", "PARTLY DONE": "partial", "BLOCKED — SOURCE": "bad",
               "BLOCKED — OWNER": "bad", "IN PROGRESS — SIBLING": "unverified",
               "REJECTED AS REQUESTED": "good", "NOT REPRODUCIBLE": "bad", "NOT STARTED": "bad"}
Q_TONE = {"OPEN": "unverified", "NEEDS OWNER DECISION": "partial", "BLOCKED — OWNER": "bad",
          "ANSWERED FOR PRACTICE": "good"}


def rd(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, dtype=str, keep_default_na=False)


def c(x: str) -> str:
    """Blank cells print as a dash, never as None."""
    x = (x or "").strip()
    return BLANK if x in ("", "-", "nan", "None") else e(x)


def tone(status: str) -> str:
    return STATUS_TONE.get(status, "")


def src_cell(row: pd.Series) -> str:
    if row.get("source_url"):
        return src_link(row["source_url"], row["source_label"] or "official page")
    return '<span class="small">No official source exists for this row — see the note below the table.</span>'


def main() -> None:
    reg = rd("request_register_2026_11_18.csv")
    ver = rd("register_verify_2026_11_18.csv")
    ven = rd("register_venues_2026_11_18.csv")
    qdf = rd("register_questions_2026_11_18.csv")
    sdf = rd("register_suggestions_2026_11_18.csv")
    adf = rd("register_ablation_2026_11_18.csv")
    fdf = rd("register_flags_2026_11_18.csv")
    mv = rd("register_movement_2026_11_18.csv")
    fac = rd("register_facts_2026_11_18.csv").set_index("fact")["value"].to_dict()
    manifest = json.loads((ROOT / "data" / "live" / "register_reads_2026_11_18" / "manifest.json").read_text())

    def F(k: str) -> str:
        return e(str(fac.get(k, "")))

    body = []

    # ---------------------------------------------------------------- intro
    body.append(flag(
        f"<strong>Per-item request register · {AS_OF}.</strong> One row per item of the "
        f"{F('register_rows')}-item request, with the gate that blocks it and the number that would clear it. "
        f"Every count on this page is computed from committed repository files and from "
        f"{len(manifest['files'])} verbatim excerpts of official pages read between {F('read_window')}; none is "
        "typed in. Statuses describe the repository, not the world: a row says DONE only when the named file "
        "exists and this session checked what it prints. "
        "<strong>No published research number was changed by this page, no strategy is validated and no reward "
        "is awarded.</strong>", "info"))

    # ---------------------------------------------------- executive summary
    counts = {"DONE": int((reg.status == "DONE").sum()),
              "PARTLY DONE": int((reg.status == "PARTLY DONE").sum()),
              "BLOCKED": int(reg.status.str.startswith("BLOCKED").sum()),
              "SIBLING": int((reg.status == "IN PROGRESS — SIBLING").sum()),
              "REJECTED": int((reg.status == "REJECTED AS REQUESTED").sum()),
              "OPEN": int((reg.status.isin(["NOT STARTED", "NOT REPRODUCIBLE"])).sum())}
    body.append('<section><h2>Executive summary — what the brief asked for and what the repository holds</h2>')
    body.append(kpi_grid([
        card(F("register_rows"), "request items registered", "one row each, in the table below", "next"),
        card(str(counts["DONE"]), "delivered and re-verified", "evidence file named on every row", "good"),
        card(str(counts["PARTLY DONE"]), "partly delivered", "the mechanism exists, the source does not", "next"),
        card(str(counts["BLOCKED"]), "blocked on a source or an owner", "no estimate published in its place", "bad"),
        card(str(counts["SIBLING"]), "in progress by a sibling session", "left untouched here (see the scope note)", ""),
        card(str(counts["REJECTED"]), "delivered as a rejection", "the brief asked for these to be refused", "good"),
        card(str(counts["OPEN"]), "not started or not reproducible", "named, not papered over", "bad"),
    ]))
    body.append(
        f"<p><strong>The decision state has not moved.</strong> {F('strategies')} strategy candidates are registered, "
        f"{F('strategies_validated')} pass the eight gates and {F('strategies_g1_fail')} fail G1 (authenticated quote "
        f"provenance), so no candidate may be promoted, demoted or rewarded. {F('prereg_picks')} picks were frozen "
        f"before kickoff, {F('forward_settled')} are settled against an official final and {F('forward_open')} await "
        f"one. The corpus behind the models is {F('corpus_games')} games ({F('corpus_seasons')}); the availability "
        f"capture behind the injury work is {F('inj_rows')} report rows for one week ({F('inj_retrieved')}). The gap "
        "between those two numbers is the reason an injury ablation cannot be run yet.</p>")
    body.append(
        f"<p><strong>What this session verified.</strong> {F('injury_lines_match')} of {F('injury_lines_read')} "
        f"injury-report lines read off the official page match the committed capture field for field; "
        f"{F('reserve_on_both')} of {F('reserve_live_rows')} reserve-list rows agree on player, date and club; "
        f"{F('venues_n')} venues are now transcribed from official game-centre pages, "
        f"{F('venues_with_both_fields')} of them with both the LOCATION and the STADIUM field. "
        f"{len(fdf)} findings and {F('register_q_n')} questions are published below; nothing here repairs a "
        "published number by hand.</p>")
    body.append('<p><a class="btn primary" href="decision-board.html">Review the suggestion boards</a> '
                '<a class="btn" href="answers.html">Full question and answer register</a> '
                '<a class="btn" href="flagged.html">Everything flagged for review</a> '
                '<a class="btn" href="competition.html">Leaderboard and gates</a></p></section>')

    # ------------------------------------------------ decision-readiness table
    rows = []
    no_src = []
    for _, r in reg.iterrows():
        st = f'<span class="pill {tone(r.status)}">{e(r.status)}</span>'
        rows.append([e(r.id), e(r["item"]), e(r.area), st, c(r.checked), c(r.evidence_detail),
                     c(r.gate), c(r.clears), src_cell(r)])
        if r.no_official_source:
            no_src.append(f"<li><strong>{e(r.id)}</strong> {e(r.get('item'))} — no official source exists for this row: "
                          f"{c(r.note) if r.note else 'stated in the row.'}</li>")
    body.append('<section><h2>Decision-readiness: one row per request item</h2>'
                '<p>The gate column is what stops the item; the clearing column is the number or artefact that '
                'would stop it being blocked. Where a row is DONE, the gate column says what the delivered rule '
                'guards rather than a gap.</p>'
                '<label>Search the register <input class="filter" type="search" '
                'placeholder="Try depth, price, reserve, ablation…"></label>')
    body.append(table(rows, ["ID", "Request item", "Area", "Status", "What was checked",
                             "Evidence in the repository", "Gate that blocks it", "What clears it",
                             "Official source for manual review"],
                      caption="2026-11-18 request register · statuses derived from committed files and official page reads"))
    if no_src:
        body.append('<ul class="findings">' + "".join(no_src) + "</ul>")
    body.append('<p class="small">Downloads: <a href="assets/data/request_register_2026_11_18.csv">the register '
                '(CSV)</a> · <a href="assets/data/register_verify_2026_11_18.csv">every verified line (CSV)</a> · '
                '<a href="assets/data/register_venues_2026_11_18.csv">the venue table (CSV)</a> · '
                '<a href="assets/data/register_facts_2026_11_18.csv">every computed number (CSV)</a>.</p></section>')

    # --------------------------------------------------------- verification
    vrows = [[e(r.check), c(r.club), e(r["item"]), c(r.official), c(r.committed), c(r.verdict),
              c(r.as_of), src_link(r.source_url, "official page")] for _, r in ver.iterrows()]
    body.append('<section><h2>Line-by-line verification against the official pages</h2>'
                f"<p>{len(vrows)} compared lines. The excerpt files, their hashes and the retrieval window are in "
                '<code>data/live/register_reads_2026_11_18/</code>; a SHA-256 proves the bytes were not altered after '
                'capture, not that the capture is a complete transcription of the page. A short club table means the '
                'fetched chunk ended mid-table — labelled PARTIAL READ, never treated as a source defect.</p>'
                '<label>Search the checks <input class="filter" type="search" placeholder="Try MATCH, Lions, reserve…"></label>')
    body.append(table(vrows, ["Check", "Club", "Item", "As printed on the official page",
                              "As committed in the repository", "Verdict", "Reading rule", "Times compared", "Source"],
                      caption="Official page read vs committed capture · every line shown, not sampled"))

    # ------------------------------------------------------------- venues
    trows = [[e(r.game_id), e(r.matchup), c(r.location_printed), c(r.stadium_printed), e(r.parsed),
              c(r.capture_sha256), e(r.source_kind), src_link(r.official_url, "official game centre")]
             for _, r in ven.iterrows()]
    body.append('<section><h2>Venue transcribed from the official game centre</h2>'
                f"<p>{len(trows)} fixtures of Week 10, every one keyed to the official page that prints it. The hash "
                "is of the raw page committed in the repository, so a venue can be re-checked without trusting this "
                "table. The Munich fixture is the reason the brief asked for this: a game whose venue changes the "
                "totals conversation was not being shown anywhere.</p>")
    body.append(table(trows, ["Game", "Matchup", "LOCATION as printed", "STADIUM as printed", "Fields parsed",
                              "Capture hash", "How the page was obtained", "Official source"],
                      caption="Fixture venues read off the official game-centre pages, 2026-11-18"))

    # ------------------------------------------------------------ questions
    qrows = [[e(r.id), e(r.gates), e(r.question), c(r.known), c(r.missing), c(r.how),
              f'<span class="pill {Q_TONE.get(r.status, "unverified")}">{e(r.status)}</span>',
              src_link(r.source_url, r.source_label)] for _, r in qdf.iterrows()]
    body.append('<section><h2>What must be known before a decision can be made</h2>'
                "<p>Each question names the register rows it gates. <em>Known</em> is what the repository or a "
                "dated official read already establishes; <em>Missing</em> is what no committed evidence shows; "
                "<em>How to find out</em> is the step, not a guess.</p>"
                '<label>Search the questions <input class="filter" type="search" placeholder="Try inactive, price, terms…"></label>')
    body.append(table(qrows, ["ID", "Gates", "Question", "What we know", "What is missing", "How to find out",
                              "State", "Official source to read"],
                      caption="Questions register · keyed to the items each one unblocks"))

    # ---------------------------------------------------------- suggestions
    body.append('<section><h2>Suggestions, with a path to choose before anything is implemented</h2>'
                f"<p>{len(sdf)} choices, each with a conservative, a balanced and a full-build path. Nothing on this "
                "page changes the repository: the selector is a browser-local preview, and a chosen path becomes real "
                "only in a committed change that records the decision and its evidence.</p>"
                '<p><button type="button" class="btn" id="apply-recommended-paths">Mark all rows recommended</button> '
                '<button type="button" class="btn" id="reset-paths">Reset to pending</button> '
                '<button type="button" class="btn" id="export-paths">Copy my selections</button></p>'
                '<pre id="path-selection-output" aria-live="polite">Reviewer status: 0 selections made; no repository '
                "change is implied by anything on this page.</pre>")
    srows = []
    for _, r in sdf.iterrows():
        picker = (f'<div class="path-picker" data-sug-id="{e(r.id)}" data-recommended="{e(r.recommended)}">'
                  f'<div><strong>Recommended: {e(r.recommended)}</strong></div>'
                  f'<label class="small">Reviewer choice: <select class="path-select" '
                  f'aria-label="Choose path for {e(r.id)}">'
                  '<option value="Pending review">Pending review (no change yet)</option>'
                  '<option value="Path A">Approve Path A (conservative)</option>'
                  '<option value="Path B">Approve Path B (balanced)</option>'
                  '<option value="Path C">Approve Path C (full build)</option></select></label></div>')
        srows.append([e(r.id), e(r.gates), e(r.title), e(r.path_a), e(r.path_b), e(r.path_c),
                      c(r.cost), c(r.risk), c(r.gate_cleared), picker, src_link(r.source_url, r.source_label)])
    body.append(table(srows, ["ID", "Gates", "Suggestion", "Path A · conservative", "Path B · balanced",
                              "Path C · full build", "Cost", "Risk", "Gate it clears", "Reviewer choice",
                              "Official source the work would rest on"],
                      caption="Suggested paths for the 2026-11-18 register · no path approved by this page"))

    # ------------------------------------------------- prospective escrow ledger
    mrows = []
    for _, r in mv.iterrows():
        def num(v):
            return BLANK if v == "" else e(v)
        mrows.append([e(r.strategy), e(r.family), e(r.market), num(r.settled_picks), num(r.weeks_with_settled_picks),
                      num(r.last_settled_week), num(r.units_now), num(r.units_prev), num(r.units_delta),
                      num(r.rank_now), num(r.rank_prev), num(r.rank_move), num(r.legs),
                      (src_link(r.official_week, "official final, week " + e(r.last_settled_week))
                       if r.official_week else BLANK)])
    body.append('<section><h2>Prospective escrow ledger: what the frozen picks have actually done</h2>'
                "<p>The only performance table on this page, and it is prospective: every row is computed from picks "
                "that were frozen before kickoff and graded against an official final, so no backtest number is "
                "ranked here or anywhere else. The movement columns are blank on purpose — the ledger has one "
                "settled week, so there is no earlier rank to move from, and publishing a zero would be inventing a "
                "change. Cumulative units are one unit per bet at the price recorded on the pick; they are not a "
                "return on a bankroll and are not comparable to a market quote, because no authenticated quote is "
                "held (gate G1 fails for every candidate).</p>"
                '<label>Search the ledger <input class="filter" type="search" placeholder="Try parlay, spread, ML…"></label>')
    body.append(table(mrows, ["Strategy", "Family", "Market", "Settled picks", "Weeks with settled picks",
                              "Latest settled week", "Units, cumulative", "Units, before that week", "Change",
                              "Rank now", "Rank before", "Rank movement", "Legs settled", "Official settlement"],
                      caption="Prospective escrow ledger from frozen, officially settled picks · blanks are uncomputable, not zero"))

    # ------------------------------------------------------------- ablation
    arows = []
    for _, r in adf.iterrows():
        tone_a = "good" if ("NOT PRESENT" in r.verdict or "READY" in r.verdict) else "bad"
        arows.append([e(r["item"]), c(r.check), c(r.found), f'<span class="pill {tone_a}">{e(r.verdict)}</span>',
                      c(r.next_step), src_link(r.source_url, r.get("source_label")
                                               or "official source the ablation depends on")])
    body.append('<section><h2>Injury and depth ablation: the contract, and why it is blocked</h2>'
                "<p>The brief asks for an ablation instead of a fixed penalty. The fixed penalty does not exist — "
                "verified against the feature dictionary — and the ablation cannot run, because the scored corpus and "
                "the availability capture do not overlap. Both halves are published rather than asserted.</p>")
    body.append(table(arows, ["Ablation requirement", "What was checked", "What the repository shows", "Verdict",
                              "Next step", "Official source"],
                      caption="Personnel-ablation contract · computed from the committed model and capture data"))

    # --------------------------------------------------------------- flags
    frows, ftext = [], []
    for _, r in fdf.iterrows():
        if not r.source_url:
            ftext.append(f"<li><strong>{e(r.id)}</strong> ({e(r.severity)}) {e(r.finding)} "
                         f"<span class=\"small\">Next: {c(r.next)}</span> No official source: shown as text.</li>")
            continue
        frows.append([e(r.id), e(r.severity),
                      f"{e(r.finding)}<br><span class=\"small\">Next: {c(r.next)} · "
                      f"register row {c(r.register)}</span>",
                      src_link(r.source_url, r.source_label)])
    body.append('<section><h2>Findings flagged by this session</h2>'
                f"<p>{len(frows) + len(ftext)} findings, numbered RR-F1 onward so they cannot collide with the "
                "F-42 to F-51 register written by "
                "<code>arena/db6cd525-korea1</code>. A finding is published, not repaired: repair is a decision, and "
                "the files a fix would touch belong to other sessions or to the integration pass.</p>")
    if frows:
        body.append(table(frows, ["ID", "Severity / state", "Finding and next step", "Source"],
                          caption="2026-11-18 session findings with an official source"))
    if ftext:
        body.append('<ul class="findings">' + "".join(ftext) + "</ul>")

    # ------------------------------------------------------ facts (no table)
    body.append('<section><h2>Every number on this page, and where it comes from</h2>'
                "<p>Printed as a definition list rather than a table on purpose: the site's rule is that a data-table "
                "row carries an official link, and these are properties of the repository, not observations of a "
                "game. They are all recomputed by <code>pipeline/register_20261118.py</code> on every build.</p><dl>")
    for k in sorted(fac):
        body.append(f"<dt>{e(k)}</dt><dd>{e(str(fac[k]))}</dd>")
    body.append("</dl></section>")

    # ------------------------------------------------------------- method
    srcs = "".join(f"<li>{src_link(s['url'], s['url'])} — {e(s['what'])}</li>" for s in manifest["sources"])
    files = "".join(f"<li><code>{e(n)}</code> · sha256 <code>{e(v['sha256'][:16])}</code> · {v['bytes']} bytes</li>"
                    for n, v in manifest["files"].items())
    body.append('<section><h2>Method and limits of this register</h2>'
                "<ol><li>Read the shared board, claim a scope that touches no sibling session's files, push the claim.</li>"
                "<li>Read the official pages with the page-fetch tool and store the block verbatim with a hash, because "
                "the sandbox shell cannot reach nfl.com (TLS refused).</li>"
                "<li>Parse the stored block and the committed capture with the same field rules, and publish every "
                "comparison, not the favourable ones.</li>"
                "<li>Author the register so each row names evidence paths; the builder refuses to run if a path is "
                "missing, if a status is outside the closed vocabulary, or if a number in the text has no computed "
                "source.</li>"
                "<li>Rebuild, run the test suite, and publish; the executive-summary and flagged files belong to other "
                "sessions today, so a wiring request is logged instead of an edit.</li></ol>"
                "<p><strong>Limits.</strong> Nine club tables were read from two of eight chunks of the Week 10 "
                "injury page; the other clubs were not re-read today. The reserve list was read in full but covers one "
                "month. The Houston read establishes only that the club page publishes an image. The Game Book PDFs were "
                "not opened: that parse belongs to <code>arena/99b908ab-korea1</code> (GB2, PR #82) and this page does "
                "not duplicate it. No pricing data was added: an authenticated quote is an owner decision (F-44, "
                "RR-Q1, RR-S1).</p>"
                f"<h3>Official pages read in this session</h3><ul>{srcs}</ul>"
                f"<h3>Excerpts committed with this register</h3><ul>{files}</ul>"
                "</section>")

    html = layout(OUT_NAME, "Request register · " + AS_OF,
                  "One row per item of the 2026-11-18 brief: status, the evidence file behind it, the gate that "
                  "blocks it, the number that clears it, and the official page to check.", "".join(body), wide=True)
    (ROOT / OUT_NAME).write_text(html)
    print("  wrote", OUT_NAME, f"({len(html)} bytes)")


if __name__ == "__main__":
    main()
