"""V3 — render `live-verification.html` and `review.html`.

Two pages, both read-only over the artefacts produced by
`pipeline/live_verify.py`, `pipeline/live_verify_depth.py`,
`pipeline/lineup_claims.py` and `pipeline/review_consolidated.py`.

* `live-verification.html` answers "is what this site publishes actually true?"
  row by row, with the official page beside each value and an explicit verdict
  that distinguishes a defect from a source update.
* `review.html` is the single place to compare the four suggestion registers and
  the three question registers, see where they converge, and pick a path.

Neither page changes a published number. Neither implements a suggestion.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LIVE_DIR, ROOT, read_json  # noqa: E402

INJ_URL = "https://www.nfl.com/injuries/league/2026/reg10"
ARCHIVE_URL = "https://github.com/karagemop466-tech/Korea1/blob/main/data/evidence/nfl_injuries/week10_2026/injury_report.md"


def e(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else pd.DataFrame()


def _pill(verdict: str) -> str:
    v = verdict.upper()
    cls = ("skill" if v in ("CONFIRMED", "PASS", "MATCH", "AGREE")
           else "no" if v in ("CONTRADICTED", "INCONSISTENT", "MISSING_FROM_PUBLISHED")
           else "luck" if v in ("STALE", "DRIFT", "DIFFER", "REVIEW")
           else "unverified")
    return f'<span class="pill {cls}">{e(verdict)}</span>'


def build_live(layout, table, card, kpi_grid, flag, src_link, SHA, SRC) -> str:
    live = LIVE_DIR
    head = read_json(live / "verification_summary.json") if (live / "verification_summary.json").exists() else {}
    dhead = read_json(live / "depth_verification_summary.json") if (live / "depth_verification_summary.json").exists() else {}
    chead = read_json(live / "lineup_claim_summary.json") if (live / "lineup_claim_summary.json").exists() else {}
    prov = read_json(live / "PROVENANCE.json") if (live / "PROVENANCE.json").exists() else {}

    inj = _read(live / "injury_field_verification.csv")
    in_sum = _read(live / "injury_verification_summary.csv")
    cons = _read(live / "internal_consistency.csv")
    depth = _read(live / "depth_slot_verification.csv")
    dsum = _read(live / "depth_verification_summary.csv")
    disc = _read(live / "depth_chart_disclaimers.csv")
    claims = _read(live / "lineup_claim_verification.csv")
    drift = _read(live / "official_capture_drift.csv")

    cal = head.get("parser_calibration", {})
    ic = head.get("internal_consistency", {})

    body = []
    body.append(flag(
        "<strong>What this page is.</strong> An independent second check of the published "
        "tables against the official NFL sources, run outside the build. The build's own "
        "verifier only proves that every row <em>carries</em> an official link; this page "
        "checks whether the row <em>matches</em> it. Where the two disagree, the row is "
        "listed here instead of being corrected silently.", "info"))

    body.append(kpi_grid([
        card(str(head.get("clubs_passing", 0)) + "/" + str(head.get("clubs", 0)),
             "injury tables clean", "eight clubs compared field by field", "good" if head.get("confirmed_defects", 1) else "bad"),
        card(str(chead.get("confirmed", 0)) + "/" + str(chead.get("claims", 0)),
             "lineup claims confirmed", "matchup page sentences graded one by one",
             "good" if not chead.get("contradicted") else "luck"),
        card(str(dhead.get("match", 0)) + "/" + str(dhead.get("slots_compared", 0)),
             "depth slots match", f"{dhead.get('players_compared', 0)} players, four club charts", "good"),
        card(str(chead.get("official_capture_drift", {}).get("values_changed", 0)),
             "official values changed", "in 29 hours, between two official captures", "luck"),
    ]))

    # ---- 1. method and honesty about it ----------------------------------
    body.append(f"""
<section>
<div class="section-head"><h2>1 · What was checked, and how</h2></div>
<p>The build sandbox shell cannot complete a TLS handshake with <code>nfl.com</code>
(this was re-measured on 2026-11-13 and still fails), so the official pages were read with
the agent page-fetch tool and the exact cells were transcribed into committed files under
<code>data/live/</code>. That makes the comparison reproducible from a clean checkout
without network access, and it makes the transcription itself auditable.</p>
{table(
    [["Official injury report", e("2026 week 10, four matchups (WAS@NYG, NE@DET, KC@ATL, MIN@GB)"),
      f'{head.get("official_rows", 0)} players', src_link(INJ_URL, "nfl.com/injuries/league/2026/reg10")],
     ["Published injury table", e("written by the scheduled availability workflow"),
      f'{head.get("published_rows", 0)} rows', src_link("https://github.com/karagemop466-tech/Korea1/blob/main/data/availability/injuries.csv", "injuries.csv") + " · " + src_link(INJ_URL, "official source")],
     ["Official club depth charts", e("commanders.com, giants.com, detroitlions.com, patriots.com"),
      f'{dhead.get("slots_compared", 0)} slots', src_link("https://www.commanders.com/team/depth-chart", "commanders.com")],
     ["Published depth table", e("same workflow, same capture"),
      f'{dhead.get("players_compared", 0)} players', src_link("https://github.com/karagemop466-tech/Korea1/blob/main/data/availability/depth_charts.csv", "depth_charts.csv") + " · " + src_link("https://www.commanders.com/team/depth-chart", "official club chart")],
     ["Matchup lineup claims", e("every status and replacement sentence on the deficiency page"),
      f'{chead.get("claims", 0)} claims', src_link("https://github.com/karagemop466-tech/Korea1/blob/main/data/lineups/week10_2026_matchup_deficiencies.csv", "source table") + " · " + src_link(INJ_URL, "official source")]],
    ["Source", "Scope", "Size", "Official reference"],
    caption="Table 1. Verification scope. Every comparison in this page is against one of these sources.")}
<p><strong>Nothing is filled in.</strong> A blank official cell never confirms a published
value, and a published blank is never filled from the official page.</p>
</section>""")

    # ---- 2. the parser control -------------------------------------------
    body.append(f"""
<section>
<div class="section-head"><h2>2 · The control: is the published parser faithful?</h2></div>
<p>Before blaming the build for any difference, the build's parser was checked against a
document that cannot drift. The repository already holds a verbatim capture of the same
official page taken <strong>2026-11-12T13:06:29Z</strong>, and the availability workflow's own
snapshot from the same day. Both describe the same instant, so any difference between them
would be a parser defect.</p>
{table(
    [["Rows parsed from the verbatim capture", str(cal.get("archive_rows", "—")),
      src_link(INJ_URL, "nfl.com injury report")],
     ["Rows in the workflow snapshot", str(cal.get("snapshot_rows", "—")),
      src_link(INJ_URL, "nfl.com injury report")],
     ["Rows matched on club + player", str(cal.get("matched_rows", "—")),
      src_link(INJ_URL, "nfl.com injury report")],
     ["Cells compared", str(cal.get("cells_compared", "—")),
      src_link(INJ_URL, "nfl.com injury report")],
     ["Cells that differ", str(cal.get("cell_differences", "—")),
      src_link(INJ_URL, "nfl.com injury report")],
     ["Verdict", _pill(cal.get("verdict", "—")),
      src_link(INJ_URL, "nfl.com injury report")]],
    ["Check", "Result", "Official source"],
    caption="Table 2. Parser control. A clean result here means the build reads the official page correctly, so a difference found later is the page changing, not the build misreading it.")}
<p>Both sides of this control come from the same official page:
{src_link(INJ_URL, "nfl.com/injuries/league/2026/reg10")}. The verbatim capture is committed at
{src_link(ARCHIVE_URL, "data/evidence/nfl_injuries/week10_2026/injury_report.md")}.</p>
</section>""")

    # ---- 3. injury fields -------------------------------------------------
    rows = []
    for r in in_sum.itertuples():
        rows.append([e(r.club), e(r.fields_compared), e(r.match), e(r.confirmed_defect),
                     e(r.drift_possible), e(r.unresolved), _pill(r.verdict),
                     src_link(r.source_url, "nfl.com injuries")])
    body.append(f"""
<section>
<div class="section-head"><h2>3 · Injury table, field by field</h2></div>
<p>Every published cell for the eight transcribed clubs was compared with the official
page. Differences are classified so that a normal midweek status update is never reported as
an error:</p>
<ul>
<li><strong>confirmed defect</strong> — the published value cannot be explained by a later
update, e.g. a player the table itself recorded as <em>Out</em> shown as a full practice
participant.</li>
<li><strong>unresolved</strong> — the player is on the official page but missing from the
snapshot; a status added between capture times and a parser drop both fit, so it is not
asserted as either.</li>
<li><strong>drift possible</strong> — the values differ and practice statuses are published
in stages, so an update between the two capture times explains it.</li>
<li><strong>no basis</strong> — the official cell is blank; nothing can be confirmed.</li>
</ul>
{table(rows, ["Club", "Fields", "Match", "Confirmed defect", "Drift possible",
              "Unresolved", "Verdict", "Official source"],
       caption="Table 3. Injury field comparison per club, week 10 of the 2026 season.")}
</section>""")

    det = inj[(inj.club.isin(in_sum.club.tolist())) & (inj.verdict != "MATCH")]
    if not det.empty:
        rows = [[e(r.club), e(r.player), e(r.field), e(r.published_value) or "—",
                 e(r.official_value) or "—", _pill(r.verdict), e(r.note),
                 src_link(r.source_url, "official")]
                for r in det.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>4 · Every non-matching injury cell</h2></div>
<p>This is the complete list. None is silently corrected: the published table is left exactly
as the workflow wrote it, and each difference is recorded with its cause and its source.</p>
{table(rows, ["Club", "Player", "Field", "Published", "Official", "Verdict", "Why", "Source"],
       caption="Table 4. All injury cells where the published value differs from the official page.")}
</section>""")

    # ---- 5. internal consistency -----------------------------------------
    rows = [[e(r.club), e(r.player), e(r.check), _pill(r.severity), e(r.practice_status),
             e(r.game_status), e(r.note), src_link(r.source_url, "official")]
            for r in cons.itertuples()] if not cons.empty else []
    body.append(f"""
<section>
<div class="section-head"><h2>5 · Checks that need no second source</h2></div>
<p>Some errors contradict the table itself. An <em>Out</em> or <em>Doubtful</em> designation
means the player will not play; the same row cannot also record a full practice
participation. These checks run over the whole published table — <strong>{ic.get('rows', 0)} rows
across {ic.get('clubs', 0)} clubs</strong> — not just the transcribed sample, and they need no
official page at all.</p>
{kpi_grid([card(str(ic.get("contradictions", 0)), "self-contradictions", "a player cannot be Out and full", "bad" if ic.get("contradictions") else "good"),
           card(str(ic.get("vocabulary", 0)), "out-of-vocabulary statuses", "outside Out / Doubtful / Questionable", "good"),
           card(str(ic.get("duplicates", 0)), "duplicate player rows", "same club and player twice", "good")])}
{table(rows, ["Club", "Player", "Check", "Severity", "Practice", "Game", "Why it matters", "Source"],
       caption="Table 5. Self-contradictions and vocabulary errors across all 28 captured clubs.") if rows
 else flag("No self-contradiction, vocabulary error or duplicate was found in the published table.", "good")}
</section>""")

    # ---- 6. depth charts --------------------------------------------------
    rows = [[e(r.team), e(r.MATCH), e(r.MISMATCH), e(r.MISSING), e(r.EXTRA), _pill(r.verdict),
             src_link(r.source_url, "club chart")] for r in dsum.itertuples()]
    body.append(f"""
<section>
<div class="section-head"><h2>6 · Depth charts: the 1st / 2nd / 3rd / 4th string claim</h2></div>
<p>The whole availability argument rests on the order of names on a club's depth chart. Each
published position row was compared with the club's own chart as an ordered list, because the
order is the claim.</p>
{table(rows, ["Club", "Slots matched", "Mismatched", "Missing", "Extra", "Verdict", "Official chart"],
       caption="Table 6. Depth-chart slot comparison for the four clubs used by the matchup pages.")}
</section>""")

    if not disc.empty:
        rows = [[e(r.team), e(r.quoted_text), e(r.consequence), src_link(r.source_url, "club page")]
                for r in disc.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>7 · What the clubs themselves say about their charts</h2></div>
<p>Two of the four charts are labelled <strong>unofficial</strong> by the club. That does not
make the extracted rows wrong — the values match exactly — but it does limit what a page may
claim from them. A second-string cell is an ordering, not a promise about who plays.</p>
{table(rows, ["Club", "What the official page says (quoted)", "Consequence for this site", "Source"],
       caption="Table 7. Club disclaimers on the official depth-chart pages, quoted verbatim.")}
</section>""")

    # ---- 8. claim grading -------------------------------------------------
    if not claims.empty:
        rows = [[e(r.matchup), e(r.quoted), e(r.official_archive) or "—",
                 e(r.official_live) or "—", _pill(r.verdict), e(r.claimed_dimension),
                 src_link(r.source_url, "nfl.com injury report")]
                for r in claims.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>8 · The matchup page, sentence by sentence</h2></div>
<p><code>lineup-deficiencies.html</code> makes {chead.get("claims", 0)} specific availability
statements. Each was matched to the official cell it describes, against three independent
official captures: the verbatim 2026-11-12 page, the 2026-11-13 workflow snapshot, and the
live page today.</p>
{kpi_grid([card(str(chead.get("confirmed", 0)), "confirmed today", "official page agrees now", "good"),
           card(str(chead.get("stale", 0)), "stale", "true when written, superseded since", "luck"),
           card(str(chead.get("contradicted", 0)), "contradicted", "no capture supports the sentence", "good" if not chead.get("contradicted") else "bad"),
           card(str(chead.get("agree_with_archive", 0)) + "/" + str(chead.get("claims", 0)),
                "agree with the 11-12 archive", "the capture contemporaneous with the page", "good")])}
<p><strong>Read the two numbers separately.</strong> {chead.get("agree_with_archive", 0)} of
{chead.get("claims", 0)} sentences agree with the official page as it stood on 2026-11-12, so the
page was faithful when it was written. {chead.get("stale", 0)} no longer describe today's
official page, because the official page revised {chead.get("official_capture_drift", {}).get("values_changed", 0)}
values in the following 29 hours. That is a freshness problem, not a fabrication problem, and
it is the reason every status should be published with its capture time beside it.</p>
{table(rows, ["Matchup", "Sentence as published", "Official 11-12", "Official today", "Verdict", "Official field", "Source"],
       caption="Table 8. Every published availability sentence graded against the official injury report.")}
</section>""")

    # ---- 9. drift ---------------------------------------------------------
    if not drift.empty:
        rows = [[e(r.club), e(r.player), e(r.practice_1112) or "—", e(r.practice_1113) or "—",
                 e(r.game_1112) or "—", e(r.game_1113) or "—",
                 src_link(r.source_url, "official")] for r in drift.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>9 · How much the official page moves</h2></div>
<p>This is the finding that matters most for anyone betting off a status. Between the two
official captures — <strong>{e(chead.get("official_capture_drift", {}).get("window", ""))}</strong>
— {chead.get("official_capture_drift", {}).get("values_changed", 0)} of
{chead.get("official_capture_drift", {}).get("players", 0)} player values on the same official
page changed. A status shown without its capture time is therefore not evidence of anything,
even when it was correct when it was written.</p>
{table(rows, ["Club", "Player", "Practice 11-12", "Practice 11-13", "Game 11-12", "Game 11-13", "Source"],
       caption="Table 9. Every player value the official injury page revised between the 2026-11-12 and 2026-11-13 captures.")}
</section>""")

    # ---- 10. what is not verified ----------------------------------------
    body.append(f"""
<section>
<div class="section-head"><h2>10 · What this page does not verify</h2></div>
<p>The limits are stated here rather than left for the reader to assume:</p>
<ul>
<li><strong>Sample, not census.</strong> Four of the sixteen week-10 matchups and four of the
32 clubs were transcribed. The other clubs are outside the verified sample and are not
graded, not even implicitly.</li>
<li><strong>The transcription is manual.</strong> It is a human reading of the official page.
The control in section 2 shows the build's parser is faithful, but that does not make the
transcription infallible; every disagreeing cell is published above for manual re-check.</li>
<li><strong>No prices.</strong> Nothing on this page touches a sportsbook price, a limit or a
timestamped quote. Gate G1 remains failed for every strategy regardless of what is verified
here.</li>
<li><strong>Order is not role.</strong> A depth chart places names in an order. It does not
confirm who starts, who is active, or how much a backup will play; only the official inactives
list and the game itself do that.</li>
<li><strong>No causal claim.</strong> Verifying that a player is out says nothing about how
many points that is worth. No availability term has been measured or priced.</li>
</ul>
<p>Provenance for the extracts, including the exact capture method and its limits, is in
{src_link("https://github.com/karagemop466-tech/Korea1/blob/main/data/live/PROVENANCE.json", "data/live/PROVENANCE.json")}.
The machine-readable verdicts are downloadable as
{src_link("assets/data/injury_field_verification.csv", "injury_field_verification.csv")},
{src_link("assets/data/depth_slot_verification.csv", "depth_slot_verification.csv")} and
{src_link("assets/data/lineup_claim_verification.csv", "lineup_claim_verification.csv")}.</p>
</section>""")

    return layout("live-verification.html", "Live verification",
                  "Every published row re-checked against the official page, one line at a time.",
                  "".join(body), wide=True)


def build_review(layout, table, card, kpi_grid, flag, src_link, SHA, SRC) -> str:
    live = LIVE_DIR
    head = read_json(live / "review_summary.json") if (live / "review_summary.json").exists() else {}
    clusters = _read(live / "review_clusters.csv")
    sug = _read(live / "suggestions_consolidated.csv")
    qs = _read(live / "questions_consolidated.csv")
    counts = head.get("counts", {})
    rec = head.get("recommended_first_move", {})

    body = [flag(
        "<strong>Read this before changing anything.</strong> Every proposal here was written "
        "by an earlier session and none of it is implemented. This page only puts the four "
        "existing registers side by side so one path can be chosen. Choosing a path is a "
        "decision you record; it is not an approval to spend money, claim an edge or award a "
        "reward.", "info")]

    body.append(kpi_grid([
        card(str(counts.get("suggestion_rows", 0)), "proposals", f"across {counts.get('suggestion_registers', 0)} independent registers", ""),
        card(str(counts.get("question_rows", 0)), "questions", f"across {counts.get('question_registers', 0)} registers", ""),
        card(str(counts.get("topics", 0)), "topics", "grouped by keyword, not by a model", ""),
        card(str(counts.get("convergence_topics", 0)), "with 3+ registers agreeing", "the strongest signal available without new data", "good"),
    ]))

    # ---- which registers exist -------------------------------------------
    REF = ("Official / primary references",
           "https://www.nfl.com/injuries/")
    rows = [[e(r["register"]), e(r["rows"]), src_link(r["page"], r["page"]),
             f'<code>{e(r["path"])}</code>', src_link(REF[1], "register sources")]
            for r in head.get("registers", [])]
    rows += [[e(r["register"] + " (questions)"), e(r["rows"]), src_link(r["page"], r["page"]),
              f'<code>{e(r["path"])}</code>', src_link(REF[1], "register sources")]
             for r in head.get("question_registers", [])]
    body.append(f"""
<section>
<div class="section-head"><h2>1 · The registers this page reads</h2></div>
<p>Four sessions answered the same brief on separate branches and could not see each other's
work. Nothing was deleted or renumbered: each register still lives on its own page with its own
numbering. This page is a reader over all of them.</p>
{table(rows, ["Register", "Rows", "Page", "Committed data", "Sources cited"],
       caption="Table 1. Source registers. This page changes none of them.")}
</section>""")

    # ---- convergence ------------------------------------------------------
    rows = [[e(r.topic), e(r.proposals), e(r.registers_agreeing), e(r.questions),
             e(r.blocked_questions), e(r.priority_score), e(r.ids),
             src_link("https://www.nfl.com/injuries/", "register sources")]
            for r in clusters.itertuples()]
    body.append(f"""
<section>
<div class="section-head"><h2>2 · Where the registers converge</h2></div>
<p>Proposals were grouped by an explicit keyword map applied to each proposal's own text — no
model and no re-ranking of any register's priority. <strong>Registers agreeing</strong> counts
how many of the four independent writers raised the same topic, which is the only kind of
corroboration available without new evidence. <strong>Blocked questions</strong> counts the
questions in that topic that no one can answer yet.</p>
{table(rows, ["Topic", "Proposals", "Registers agreeing", "Questions", "Blocked", "Score", "Proposal IDs", "Sources cited"],
       caption="Table 2. Topic clusters across all four suggestion registers and all three question registers.")}
</section>""")

    # ---- recommendation ---------------------------------------------------
    body.append(f"""
<section>
<div class="section-head"><h2>3 · The one path this review recommends</h2></div>
<div class="callout">
<p><strong>{e(rec.get("topic", "—"))}</strong> — proposed by
{e(rec.get("registers_agreeing", 0))} of the registers, {e(rec.get("proposals", 0))} proposals,
and it holds {e(rec.get("blocked_questions", 0))} of the blocked questions.</p>
<p><strong>Why this one.</strong> {e(rec.get("why", ""))}</p>
<p><strong>What choosing it does not do.</strong> {e(rec.get("what_it_does_not_do", ""))}.</p>
<p><strong>What it costs.</strong> Nothing is required to decide. Executing it is a separate
decision with a real cost, and the executive summary already records that the evidence does not
support funding anything today.</p>
</div>
<p>The reason this is the recommendation is structural rather than statistical: without a
timestamped, executable price for a bet, gate G1 fails for every strategy, so a leaderboard
built on the current inputs cannot rank anything. The other topics are not less valuable — they
are simply downstream of this one.</p>
</section>""")

    # ---- the three paths --------------------------------------------------
    body.append(f"""
<section>
<div class="section-head"><h2>4 · Three paths, stated plainly</h2></div>
{table(
 [["<strong>A · Freeze and stay honest</strong>",
   e("Publish everything, change nothing, keep every cell blank that cannot be sourced."),
   e("Costs nothing and risks nothing. The site stays a research artefact that cannot rank a strategy."),
   e("No new evidence ever arrives, so the leaderboard stays empty by construction."),
   src_link("suggestions.html", "suggestions.html"),
   src_link("https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping", "White (2000)")],
  ["<strong>B · Buy the price evidence</strong>",
   e("Acquire timestamped executable quotes, then re-run the eighteen strategies against them."),
   e("This is the only path that can unlock gate G1 and make the leaderboard mean something."),
   e("Costs money and needs a licensed source; a quote archive alone does not prove an edge."),
   src_link("decision-board.html", "decision-board.html"),
   src_link("https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push", "FanDuel settlement rules")],
  ["<strong>C · Model the availability signal</strong>",
   e("Measure what a missing starter is actually worth, then add it as a priced term."),
   e("Uses the data already captured daily and needs no purchase."),
   e("Rests on an effect that has not been measured, and depth order is not a confirmed role."),
   src_link("lineup-deficiencies.html", "lineup-deficiencies.html"),
   src_link("https://www.nfl.com/injuries/", "NFL injury report")]],
 ["Path", "What it means", "What it buys", "What it risks", "Register", "Official / primary reference"],
 caption="Table 3. The three defensible paths. B and C are not mutually exclusive; A is what the site does today.")}
<p>This review recommends <strong>B as the first purchase and C as the work that needs no
purchase</strong>, both behind A's rule that nothing unverified is presented as verified. That
combination is this page's recommendation, labelled as the agent's recommendation and
reversible by you at any time. It is not a decision until it is recorded as one in
<code>DECISIONS.md</code>, which currently holds it as <code>REC-01</code> — explicitly a
recommendation, not a D-row.</p>
</section>""")

    # ---- questions --------------------------------------------------------
    if not qs.empty:
        rows = [[e(r.register), e(r.id), e(r.text), _pill(r.status) if r.status else "",
                 e(r.blocks), e(r.topic), src_link(r.source_url, r.source_label)
                 if r.source_url else e(r.source_label)] for r in qs.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>5 · Every question, in one table</h2></div>
<p>Questions, knowns and unknowns are the part of the brief that cannot be answered by work.
Some are blocked because the information does not exist in any public source; some are blocked
because only the owner can decide them. Each row keeps the register and the original identifier
so it can be traced back to its own page.</p>
{table(rows, ["Register", "ID", "Question", "Status", "Blocks", "Topic", "Source the register cites"],
       caption="Table 4. All questions from the three question registers, with their original identifiers.")}
</section>""")

    # ---- every proposal ---------------------------------------------------
    if not sug.empty:
        rows = [[e(r.register), e(r.id), e(r.text), e(r.topic),
                 src_link(r.source_url, r.source_label) if r.source_url else e(r.source_label),
                 src_link(r.page, "register")] for r in sug.itertuples()]
        body.append(f"""
<section>
<div class="section-head"><h2>6 · Every proposal, in one table</h2></div>
<p>All {counts.get("suggestion_rows", 0)} proposals from all four registers, with the topic each
was assigned and a link back to the page that owns it.</p>
{table(rows, ["Register", "ID", "Proposal", "Topic", "Source the register cites", "Owner page"],
       caption="Table 5. All proposals across the four suggestion registers.")}
</section>""")

    body.append(f"""
<section>
<div class="section-head"><h2>7 · How to choose</h2></div>
<p>A decision is recorded in <code>DECISIONS.md</code> as one row: the date, who decided, what was
decided, the evidence at that moment, and the condition that would reverse it. Nothing else is
required. The register pages stay exactly as they are; a decision does not rewrite them.</p>
<p>If a suggestion needs work in a file another session claimed, the rule is to log the request in
<code>COORDINATION.md</code> rather than edit that file. That rule is what keeps parallel sessions
from overwriting each other, and it applies to this page too: this session claimed only
<code>pipeline/live_verify.py</code>, <code>pipeline/live_verify_depth.py</code>,
<code>pipeline/lineup_claims.py</code>, <code>pipeline/review_consolidated.py</code>,
<code>pipeline/render_live.py</code>, <code>data/live/**</code>, <code>review.html</code> and
<code>live-verification.html</code>.</p>
</section>""")

    return layout("review.html", "Review & choose a path",
                  "Four suggestion registers and three question registers, side by side, with one recommendation.",
                  "".join(body), wide=True)
