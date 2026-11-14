"""Requirement 9 — the **dedicated suggestions section** for the 2026-11-14 brief.

The brief asks for a place where suggestions can be reviewed and a path chosen *before* anything is
implemented, and for a clear list of the questions, information and answers that have to exist before
a decision can be made. The repository already carries 76 suggestions from five earlier registers and
90 questions from four registers, merged on `review-queue.html` and `answers.html`. Those registers
predate the nine requirements in this brief, so this page does two things and does not repeat them:

1. **Brief items** — one row per requirement in the 2026-11-14 brief, with what was built, what it
   proved, what it did *not* prove, and the decision it leaves open. This is the review surface for
   this session's work.
2. **New suggestions** — the proposals this session's evidence produces that are not already in the
   76-row register (checked by title against it, and the check is recorded on the page). Each carries
   the evidence that motivates it, its cost, its risk and what it unblocks.
3. **Pre-decision questions** — the questions this session's findings raise that a decision-maker must
   answer before choosing a path, each with what is known today, what is missing, and the cheapest way
   to close it. Cross-referenced to the existing 90-question register where one already asks it.

Nothing is implemented from this page. Every row has a status cell that reads `AWAITING PATH
SELECTION`, which is the point: the review happens before the change.

Outputs
  data/integration/brief_2026_11_14.csv        the nine requirement rows
  data/integration/suggestions_2026_11_14.csv  the new proposals
  data/integration/questions_2026_11_14.csv    the pre-decision questions
  assets/data/ mirrors
  suggestions-review-2026-11-14.html

Run:  python pipeline/session_20261114.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
URL_CLOSING = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/closing_lines.csv"
URL_GAMES = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/games.csv"
URL_SCORES = "https://www.nfl.com/scores/"
URL_OFFICIAL = "https://www.nfl.com/scores/"
URL_SCORES_W9 = "https://www.nfl.com/scores/2026/week-9"
URL_INJURIES = "https://www.nfl.com/injuries/league/2026/reg10"
URL_SCHED = "https://www.nfl.com/schedules/2026/by-week/reg-10"
URL_GAMEBOOK = ("https://static.www.nfl.com/image/upload/v1794570519/gamecenter/"
                "ab5828d9-4feb-11f1-abca-2c54536568a9.pdf")

# --------------------------------------------------------------------------- #
# 1. The nine brief items: claim, evidence, limitation, open decision
# --------------------------------------------------------------------------- #
BRIEF = [
    ("R1", "Price-snapshot store: open + close for every market",
     "Built. One row per game / market / side with an opening and a closing endpoint, each naming the "
     "pinned file it came from and its evidence class.",
     "price-annex.html; data/prices/price_snapshots.csv (36,438 rows)",
     "Every originated market HAS a snapshot row (requirement met literally). Only 2,916 rows carry "
     "BOTH endpoints, all of them the spread in 2013–2018. The total has an opener only in 2021; the "
     "moneyline has no opener anywhere in the archive.",
     "No official price feed is reachable. Buying one is PRICE-01 and is the only way to close this."),
    ("R2", "Verified results feed so a backtest and ROI can be computed",
     "Built. Per-game official finals with URL, the page they were read from, the read time and the "
     "evidence class; derived settlement per market from the closing line.",
     "results-feed.html; data/results/verified_results.csv (150 rows: 29 FINAL, 1 UNVERIFIED, 13 FUTURE, "
     "107 COMMUNITY_ONLY)",
     "All 30 already-settled games and 14 freshly read Week 8 finals are in one feed. Weeks 1–7 carry "
     "only community finals and are labelled as such, so a settlement can use 30 games, not 108.",
     "nfl.com now hides scores from this client on some pages (the 'Hidden Score' text). Reading every "
     "game page or the Game Book PDF is a scheduled job: RES-01."),
    ("R3", "Originate side, then total, then moneyline",
     "Built. The origination module emits markets in that fixed order, with the reason each is where "
     "it is, and the moneyline is derived from the margin distribution rather than modelled twice.",
     "origination.html; data/gates/origination_order.csv (6,073 games)",
     "The order is enforced in the data layout and on the page. The moneyline fair price is a "
     "transform of the side distribution, stated on every row.",
     "Whether to model the moneyline separately (it would need its own features and its own "
     "walk-forward window) is Q3."),
    ("R4", "Fair line, market line and difference as separate columns",
     "Built. Nine columns: fair, market and difference for each of the three markets, with one stated "
     "sign convention and an explicit `edge_available` column.",
     "origination.html; data/gates/origination_columns.csv",
     "The difference is arithmetic and is never called an edge. On paired out-of-sample rows the "
     "model's fair number is WORSE than the market close on all three markets (side 10.523 vs 10.215 "
     "MAE; total 10.762 vs 10.527; moneyline 0.449 vs 0.424).",
     "The model as it stands does not beat the closing line. Improving it, or beating a different "
     "number (an opener, a stale line), is Q2."),
    ("R5", "Separate signal from staking on the leaderboard",
     "Built. Two independent tests per strategy — signal (Spearman ρ of the model's own disagreement "
     "against realised pnl, weekly-block interval) and staking (ROI with the same interval) — with a "
     "combined verdict that needs both.",
     "signal-staking.html; data/gates/signal_staking.csv (18 strategies)",
     "The old number-one by ROI, WIND_UNDER (+9.15% on 456 bets), has ρ = −0.021 with an interval "
     "containing zero: it is now labelled LUCK_RISK and ranks 13th. BUY_LOW_ATS is the only strategy "
     "with signal evidence (ρ = +0.064, interval [+0.012, +0.111]) and its ROI is still negative.",
     "One signal in 18 tests is close to what multiple testing produces by chance. Nothing here is "
     "promoted; the Holm correction on the old page remains the authority."),
    ("R6", "Track the depth of the replacement, not the fact of a replacement",
     "Built. Official injuries joined to official club depth charts; every hole carries a 1/rank "
     "weight, the deepest slot the club must use, and a cliff flag where no backup is listed.",
     "replacement-depth.html; data/gates/replacement_depth.csv (96 club×unit rows)",
     "30 club-units are fully verified, 9 partial, 3 have no chart (Houston publishes an image). "
     "89 of 160 unavailable or at-risk players could be matched to a chart slot; 71 could not and are "
     "counted, not dropped. Example: Washington's TE #8 has no listed backup behind rank 2.",
     "A chart order is not a game-time role. Official pregame inactives (T-90m) are not archived, so "
     "no depth claim is made about who actually plays: DEP-01."),
    ("R7", "Correlations only from officially sourced numbers, with n published",
     "Built. Six relationships from pairs where both the market number and the outcome come from the "
     "same pinned archive row; every row prints n, weeks, a week-block interval and a signed "
     "convention.",
     "correlation-official.html; data/correlations/official_correlations.csv",
     "n = 5,213 pairs, 425 weeks for every row. Three are distinguishable from zero (side vs moneyline "
     "ρ = +0.806; moneyline vs margin ρ = −0.441; signed model edge vs margin ρ = +0.178) and three "
     "are not (margin vs total ρ = +0.014; covers vs over ρ = −0.002; spread line vs total line "
     "ρ = −0.002).",
     "The 'officially sourced' label means the values are the league's own numbers as mirrored by the "
     "pinned archive, not that they were read from nfl.com. Two sign errors were found and fixed while "
     "building this page — see F-2026-11-14-02."),
    ("R8", "A demotion gate that sends a live strategy back to paper",
     "Built. Four states and six fail-closed triggers; any one trigger demotes. The gate executes "
     "against every strategy on every build.",
     "demotion.html; data/gates/demotion_gate.csv",
     "No strategy is LIVE, so nothing can be demoted; the gate reports that instead of a green tick. "
     "The four strategies with a settled forward pick have one each, and D1/D2 report 'not computable' "
     "rather than a pass.",
     "The gate has never been exercised on real live evidence. A paper-trading period is what would "
     "exercise it: COMP-01."),
    ("R9", "A dedicated suggestions section, reviewed before any change",
     "Built. This page: nine brief items, the new proposals this session's evidence produced, and the "
     "pre-decision questions, each cross-referenced to the existing registers.",
     "suggestions-review-2026-11-14.html",
     "Nothing on this page is implemented. The new proposals are checked against the 76 existing "
     "titles and the overlaps are listed rather than duplicated. Requirements.html, from the "
     "parallel session, marks the same three items MET rather than delivered-with-a-caveat.",
     "A path has to be chosen before any of the proposals runs. That is the owner's decision."),
]

# --------------------------------------------------------------------------- #
# 2. New proposals, each motivated by evidence produced in this session
# --------------------------------------------------------------------------- #
SUGGESTIONS = [
    ("PS-01", "Price-snapshot store", "Add a licensed, timestamped price feed and snapshot it at "
     "T-24h, T-90m and T-5m for every originated market",
     "46,020 of the 72,876 originated market rows in the store have no opening endpoint and 20,708 "
     "have neither endpoint; no official price exists in the archive at all.",
     "A licensed feed subscription, plus a scheduled job that writes one immutable file per snapshot.",
     "Subscription cost is unknown until quotes are requested; a trial feed may not be representative.",
     "Closes G1 (the gate that fails every strategy) and makes the opening/closing gap closable.",
     "AWAITING PATH SELECTION", URL_CLOSING),
    ("RES-01", "Results feed", "Read every played 2026 game page and the official Game Book PDF each "
     "week, and write the finals into the verified results feed",
     "nfl.com renders the score as the literal text 'Hidden Score' on some pages (weeks 9+); the Game "
     "Book PDF carries the score but must be read separately and linked from the game page.",
     "One scheduled workflow run per week; no subscription. The Game Book URL is discoverable from the "
     "game page, so the job is mechanical.",
     "The PDF layout can change without notice; a parser failure must fail closed and leave the game "
     "UNVERIFIED rather than guess.",
     "Turns 30 settleable games into ~108 and lets the forward test score itself weekly.",
     "AWAITING PATH SELECTION", URL_GAMEBOOK),
    ("RES-02", "Results feed", "Read weeks 1–7 of 2026 from official pages so the feed is not two-thirds "
     "community-sourced",
     "107 of 150 games in the feed carry a community final and only 29 carry an official read.",
     "The same job as RES-01, run back over the season once.",
     "Historical pages may be archived differently from current ones; the read must fail closed.",
     "Makes an official backtest of the second half of 2026 possible at all.",
     "AWAITING PATH SELECTION", URL_SCORES),
    ("SIG-01", "Signal vs staking", "Re-rank every existing leaderboard view by the signal verdict, "
     "not by ROI, and publish the ROI ordering beside it as a second column",
     "WIND_UNDER ranked first on ROI (+9.15%, 456 bets) and has no signal evidence (ρ = −0.021, "
     "interval contains zero).",
     "One page rebuild; the data already exists in signal_staking.csv.",
     "Re-ranking is a presentation change that could hide a strategy the owner wanted to see; the old "
     "order is kept in a column, so the risk is contained.",
     "Stops a lucky staking run from topping the board.",
     "AWAITING PATH SELECTION", URL_CLOSING),
    ("SIG-02", "Signal vs staking", "Run a pre-registered multiplicity correction across the signal "
     "tests before any signal verdict is allowed to promote a strategy",
     "1 of 18 strategies shows signal evidence at 95%; with 18 tests the family-wise chance of at "
     "least one is about 60%.",
     "Reuse the existing Holm machinery on the signal p-values; no new data.",
     "No technical cost; it may leave zero strategies with a signal, which is the honest outcome.",
     "Prevents the signal column itself from becoming a multiple-testing artefact.",
     "AWAITING PATH SELECTION", URL_CLOSING),
    ("DEP-01", "Replacement depth", "Archive the official T-90m pregame inactive list for every club "
     "and replace the chart-order assumption with the confirmed inactive set",
     "The depth page can say who is Out but not who actually starts; 71 of 160 injured players could "
     "not even be matched to a chart slot.",
     "The pregame report is published by the league 90 minutes before kickoff; a scheduled job can "
     "capture it for all 32 clubs.",
     "A capture five minutes late misses a game; the job must start 2 hours before the earliest "
     "kickoff and stamp each club's capture time.",
     "Turns replacement depth from a published order into a game-day fact.",
     "AWAITING PATH SELECTION",
     "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep"),
    ("DEP-02", "Replacement depth", "Estimate the relationship between depth loss and scoring, out of "
     "sample, before depth is allowed into a signal",
     "The depth measure exists but has never been tested against a result; using it as a signal today "
     "would be an untested factor.",
     "Needs the historical roster/depth archive and the official results feed; a walk-forward fit.",
     "The historical depth archive is a community mirror, so the estimate would carry the same caveat "
     "as the model.",
     "Would be the first signal in the library derived from availability rather than price.",
     "AWAITING PATH SELECTION", URL_INJURIES),
    ("CO-01", "Correlations", "Replace the archive-mirrored correlation inputs with officially read "
     "game results for the whole sample, and publish the difference",
     "The current register is explicit that 'officially sourced' means the league's numbers as "
     "mirrored by the pinned archive, not read from nfl.com.",
     "The results feed plus a scheduled read; the estimator is already written.",
     "Reading 5,213 games from nfl.com is a large, slow job and would need a rate policy.",
     "Would let the correlations claim the same evidence class as the forward test.",
     "AWAITING PATH SELECTION", URL_SCORES_W9),
    ("COMP-01", "Competition", "Run a funded-free paper-trading season so the demotion gate is "
     "exercised on real live evidence",
     "No strategy is LIVE, so the demotion gate has never fired and cannot be shown to work.",
     "Zero cash: a paper bankroll, the existing forward ledger, and one settlement read per week.",
     "A paper season takes a full season to produce enough weeks; nothing is learned quickly.",
     "Exercises the demotion gate, the promotion checklist and the staking/signal split together.",
     "AWAITING PATH SELECTION", URL_SCORES),
    ("NAV-02", "Site", "Consolidate the three duplicate surfaces created by two sessions answering "
     "the same nine-item brief: two demotion explanations, two price stores, two nine-item status tables",
     "Rebasing onto main revealed that arena/b400d3ae-korea1 and arena/fcba7eb5-korea1 had already "
     "shipped a demotion gate, a price-snapshot store and a nine-item requirements trace. Both are now "
     "linked and neither contradicts the other, but a reader has to find both.",
     "One pass over the navigation and one canonical page per concept; the data is already built.",
     "A consolidation can drop a page another session cites; the map has to be written first.",
     "Makes the nine-item brief read as one answer instead of two implementations of it.",
     "AWAITING PATH SELECTION", URL_SCORES),
    ("NAV-01", "Site", "Group the navigation into three guided paths — Prove it, Price it, Pick it — "
     "so 45 pages do not present as a flat list",
     "The site now has 48 pages and the nav is a single column of 40 links; the new correctness pages "
     "sit beside seven duplicated review surfaces from earlier sessions.",
     "One navigation change in the renderer; no data change.",
     "Any nav change breaks anchors other pages link to; the page set is unchanged, only the grouping.",
     "Makes the decision surfaces findable, which is the difference between a site and an archive.",
     "AWAITING PATH SELECTION", URL_SCORES),
]

# --------------------------------------------------------------------------- #
# 3. Pre-decision questions raised by this session
# --------------------------------------------------------------------------- #
QUESTIONS = [
    ("BQ-01", "R1 / R4", "Is a closing line the right benchmark for a line-origination system?",
     "The market close is the hardest number in the market and the model loses to it on all three "
     "markets (paired MAE 10.523 vs 10.215 on the side).",
     "Whether any date from origination to close is a fair comparison — the opener, a T-24h number, or "
     "the close — has not been decided, and the archive cannot support T-24h.",
     "Decide the benchmark first; then the accuracy table on origination.html reads as a verdict "
     "instead of a curiosity.", "AWAITING PATH SELECTION", PROC.name),
    ("BQ-02", "R1", "Does a community-mirrored closing line count as 'officially sourced'?",
     "The repository's evidence policy says a community mirror is not an official NFL source; the "
     "correlation page had to label its inputs 'officially sourced values, not read from nfl.com'.",
     "No owner statement exists on whether 'officially sourced' means (a) the league's own numbers, "
     "however obtained, or (b) only what was read from an nfl.com page by this process.",
     "A one-line decision settles the language on every page; option (b) makes the correlation page "
     "unpublishable until CO-01 ships, which is the honest reading.", "AWAITING PATH SELECTION",
     URL_SCORES),
    ("BQ-03", "R5", "Is one signal in eighteen tests evidence of skill?",
     "BUY_LOW_ATS passes the signal test at 95% (ρ = +0.064); 18 tests were run.",
     "Whether the signal test should be corrected for multiplicity before it can promote anything "
     "(SIG-02), and what the pre-registered threshold is.",
     "Pre-register the correction and the threshold now, before the forward window, rather than after "
     "seeing the result.", "AWAITING PATH SELECTION", URL_SCORES),
    ("BQ-04", "R6", "What counts as a confirmed replacement?",
     "The depth page documents the published chart order and explicitly refuses to claim a game-time "
     "role, because no chart carries a publication time.",
     "Whether the T-90m inactive list is sufficient, or whether a snap-count threshold is required "
     "before a player counts as 'replaced'.",
     "DEP-01 decides the capture; the threshold is a separate choice with a cost (snap counts need "
     "another data source).", "AWAITING PATH SELECTION", URL_INJURIES),
    ("BQ-05", "R8", "Who may demote, and who may re-promote?",
     "The demotion gate is defined and armed but has never fired; the promotion checklist explicitly "
     "leaves the funding decision to the owner.",
     "Whether a demotion is automatic (as coded) and whether a re-promotion needs a fresh prospective "
     "window or can reuse the old evidence.",
     "A rule for re-promotion is needed before the first demotion, or the gate creates a one-way door.",
     "AWAITING PATH SELECTION", URL_SCORES),
    ("BQ-06", "R2", "How is a settlement defined when the score cannot be read?",
     "nfl.com renders 'Hidden Score' on some game pages; the Game Book PDF carries the score. The feed "
     "leaves those games UNVERIFIED.",
     "Whether a Game Book PDF read by a parser is acceptable evidence for settlement, or whether a "
     "second independent read is required per game.",
     "Decide the evidence standard for a settlement, then RES-01 can be automated against it.",
     "AWAITING PATH SELECTION", URL_GAMEBOOK),
    ("BQ-07", "R3", "Should the moneyline be modelled separately?",
     "The moneyline fair price is a monotone transform of the margin distribution; it is the weakest "
     "of the three columns against the market (0.449 vs 0.424 MAE in probability terms).",
     "Whether a separate moneyline model (with its own features) would be better, and whether the data "
     "supports the extra parameters.",
     "Test it walk-forward against the transform before adopting it; the current design is stated, not "
     "accidental.", "AWAITING PATH SELECTION", URL_SCORES),
    ("BQ-08", "R7", "How should a null correlation be used in parlay pricing?",
     "Three of the six relationships are indistinguishable from zero, including the side/total pair "
     "that a same-game parlay price depends on.",
     "Whether 'not distinguishable from zero' should be treated as zero for pricing, or whether the "
     "ticket price should be widened for the uncertainty.",
     "A conservative rule (treat as zero, add a margin) is the safe default, but it is a choice the "
     "owner should record.", "AWAITING PATH SELECTION", URL_CLOSING),
    ("BQ-09", "Across", "Which of the 76 existing proposals does this session's evidence make "
     "obsolete, and which does it make urgent?",
     "Several existing proposals (prices, availability, review surfaces) now have a different starting "
     "point because the snapshot store, results feed and depth register exist.",
     "No mapping exists from the nine brief items to the 76-row register beyond the overlap table on "
     "this page.",
     "A single pass over the register with the nine items in hand; the overlap column on the "
     "suggestions table below is the starting point.", "AWAITING PATH SELECTION", URL_SCORES),
]


def overlap_check(titles: list[str]) -> dict[str, str]:
    """Check each new proposal against the 76 existing titles; return the closest match per id."""
    p = ROOT / "data" / "integration" / "suggestions_master.csv"
    if not p.exists():
        return {}
    old = pd.read_csv(p, dtype=str, keep_default_na=False)
    out = {}
    for s in SUGGESTIONS:
        sid, title = s[0], s[1]
        words = set(w.lower().strip(".,:;()") for w in (title + " " + s[2]).split() if len(w) > 4)
        best, score = "", 0
        for r in old.itertuples():
            t = set(w.lower().strip(".,:;()") for w in (str(r.title) + " " + str(r.proposal)).split()
                    if len(w) > 4)
            common = len(words & t)
            if common > score:
                best, score = f"{r.master_id} — {r.title}", common
        out[sid] = best if score >= 3 else "no close match in the 76-row register"
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    brief = pd.DataFrame(BRIEF, columns=["id", "requirement", "what_was_built", "evidence",
                                         "what_it_proves_and_does_not", "decision_left_open"])
    ov = overlap_check([s[1] for s in SUGGESTIONS])
    sug = pd.DataFrame([dict(id=s[0], area=s[1], title=s[2], evidence=s[3], cost=s[4], risk=s[5],
                             unblocks=s[6], status=s[7], reference=s[8], existing_register=ov.get(s[0], ""))
                        for s in SUGGESTIONS])
    qs = pd.DataFrame([dict(id=q[0], relates_to=q[1], question=q[2], known=q[3], missing=q[4],
                            how_to_close=q[5], status=q[6], reference=q[7]) for q in QUESTIONS])
    return brief, sug, qs


def build_page(brief: pd.DataFrame, sug: pd.DataFrame, qs: pd.DataFrame) -> str:
    brief_rows = []
    for r in brief.itertuples():
        brief_rows.append([clean(r.id), clean(r.requirement), clean(r.what_was_built), clean(r.evidence),
                           clean(r.what_it_proves_and_does_not), clean(r.decision_left_open),
                           ref_link("official", URL_OFFICIAL)])
    sug_rows = []
    for r in sug.itertuples():
        sug_rows.append([clean(r.id), clean(r.area), clean(r.title), clean(r.evidence), clean(r.cost),
                         clean(r.risk), clean(r.unblocks), clean(r.existing_register),
                         f'<span class="pill unverified">{e(r.status)}</span>',
                         ref_link("official", URL_OFFICIAL),
                         (ref_link("evidence", r.reference) if str(r.reference).startswith("http")
                          else clean(r.reference))])
    q_rows = []
    for r in qs.itertuples():
        q_rows.append([clean(r.id), clean(r.relates_to), clean(r.question), clean(r.known),
                       clean(r.missing), clean(r.how_to_close),
                       f'<span class="pill unverified">{e(r.status)}</span>',
                       ref_link("official", URL_OFFICIAL),
                       (ref_link("evidence", r.reference) if str(r.reference).startswith("http")
                        else clean(r.reference))])
    n_cross = int((sug.existing_register != "no close match in the 76-row register").sum())
    cards = (
        '<div class="cards">'
        f'<div class="card good">{len(brief)}<div class="card-label">brief items delivered</div>'
        f'<div class="card-note">each with what it proves and what it does not</div></div>'
        f'<div class="card">{len(sug)}<div class="card-label">new proposals</div>'
        f'<div class="card-note">{n_cross} overlap an existing register row and link to it</div></div>'
        f'<div class="card">{len(qs)}<div class="card-label">pre-decision questions</div>'
        f'<div class="card-note">what must be settled before a path is chosen</div></div>'
        f'<div class="card bad">0<div class="card-label">proposals implemented</div>'
        f'<div class="card-note">every row is awaiting a path selection</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>Read this beside <code>requirements.html</code>, not instead of it.</strong>
A parallel session (<code>arena/fcba7eb5-korea1</code>) also answered the nine requirements, and its
trace — 3 MET and 6 PARTIAL — is published on <a href="requirements.html">Requirements</a> and merged
on <code>main</code> before this page existed. The two pages agree on every substantive point and
differ in one place worth knowing: that trace marks T3, T5 and T9 MET, on the grounds that the
sequence, the split and the review surface exist in the software. This page keeps those three at
"built, and it proves less than the title suggests", because a delivered mechanism is not the same
claim as a validated one — T3's ordering is a computation order with no timestamped record behind it,
and T5's 18 strategies produce exactly one signal. Both readings are defensible; the owner should
pick one and the other page should follow, rather than the site publishing two status vocabularies.</p>
<p class="flag info"><strong>What this page is.</strong> The dedicated review surface for the
2026-11-14 brief (requirement 9). It lists the nine requirements and what each one actually proved,
the new proposals this session's evidence produced, and the questions that must be answered before a
path is chosen. <strong>Nothing on this page is implemented.</strong> Every row reads
<em>awaiting path selection</em>, which is the point: the review happens before the change.</p>
{cards}
<section>
<div class="section-head"><h2>1 · The nine requirements: delivered, and what each one proved</h2></div>
<p>The fifth column is the important one. Every item was built, and every item proved less than its
title suggests. That gap is the content of this review, not a footnote to it.</p>
{table(brief_rows, ["#", "Requirement", "What was built", "Evidence", "What it proves — and does not", "Decision it leaves open", "Official reference"],
       caption="The nine requirements of the 2026-11-14 brief, each with its evidence and its limit")}
</section>
<section>
<div class="section-head"><h2>2 · New proposals</h2></div>
<p>Ten proposals, each motivated by something this session measured rather than by opinion. The
<em>existing register</em> column checks each title against the 76 rows already on
<a href="review-queue.html">Suggestions queue</a>; where a close match exists it is named, so the same
idea is not proposed twice under a new id.</p>
{table(sug_rows, ["ID", "Area", "Proposal", "Evidence", "Cost", "Risk", "Unblocks",
                  "Existing register", "Status", "Official reference", "Evidence"],
       caption="New proposals, each with the evidence that motivates it; none implemented")}
</section>
<section>
<div class="section-head"><h2>3 · Questions to answer before a path is chosen</h2></div>
<p>Each question states what is known today, what is missing, and the cheapest way to close it. None of
them is answerable from the data in the repository alone, which is why they are questions and not
tasks.</p>
{table(q_rows, ["ID", "Relates to", "Question", "Known today", "What is missing", "Cheapest way to close",
                "Status", "Official reference", "Evidence"],
       caption="Pre-decision questions: known, missing, and how to close each gap")}
</section>
<section>
<div class="section-head"><h2>4 · How to choose a path</h2></div>
<p>The proposals do not compete: they form four dependency chains, and the first move in each is cheap
and reversible.</p>
<ol>
<li><strong>Prove the results.</strong> RES-01 → RES-02 → CO-01. No new cost; the binding question is
the evidence standard (BQ-06). Without it the site can settle 30 games.</li>
<li><strong>Price the market.</strong> PS-01 is the only proposal with a subscription cost, and it is
the only one that can make G1 pass. Nothing else in the library can be validated until it does.</li>
<li><strong>Test the signal properly.</strong> SIG-02 → SIG-01. Free, and it protects the two-test
board from becoming a multiple-testing artefact itself (BQ-03).</li>
<li><strong>Make availability a fact.</strong> DEP-01 → DEP-02. Free at the capture end; the modelling
end should wait for the capture.</li>
</ol>
<p class="flag warn">The honest recommendation, given the evidence on this site, is to do (1) and (3)
first: they cost nothing, they make every existing table more trustworthy, and they do not commit the
owner to a subscription. That is a recommendation, not a decision — the decision is recorded in
<code>DECISIONS.md</code> when the owner makes it.</p>
<p>Downloads: <a href="assets/data/brief_2026_11_14.csv">brief_2026_11_14.csv</a> ·
<a href="assets/data/suggestions_2026_11_14.csv">suggestions_2026_11_14.csv</a> ·
<a href="assets/data/questions_2026_11_14.csv">questions_2026_11_14.csv</a>.
The earlier registers are unchanged and still live on
<a href="review.html">Review &amp; choose a path</a>, <a href="review-queue.html">Suggestions queue</a>
and <a href="answers.html">Questions &amp; answers</a>.</p>
</section>
"""
    return layout("suggestions-review-2026-11-14.html",
                  "Suggestions review · 2026-11-14 brief",
                  "The nine brief items, ten new proposals and nine pre-decision questions — reviewed before anything is implemented.",
                  body, wide=True)


def main() -> None:
    brief, sug, qs = build()
    write_csv(brief, "brief_2026_11_14.csv")
    write_csv(sug, "suggestions_2026_11_14.csv")
    write_csv(qs, "questions_2026_11_14.csv")
    for name, df in (("brief_2026_11_14.csv", brief), ("suggestions_2026_11_14.csv", sug),
                     ("questions_2026_11_14.csv", qs)):
        (ROOT / "data" / "integration" / name).write_text(df.to_csv(index=False), encoding="utf-8")
    (ROOT / "suggestions-review-2026-11-14.html").write_text(build_page(brief, sug, qs),
                                                             encoding="utf-8")
    print(f"  brief {len(brief)} · suggestions {len(sug)} · questions {len(qs)}")


if __name__ == "__main__":
    main()
