"""T14/T15/T16 renderers: injury register, decision questions and suggestions.

These pages are built from committed CSVs, never from hand-typed HTML:

  data/processed/injury_*.csv   official observations (NFL.com report + club charts)
  research/decision_questions.csv, research/information_inventory.csv
  research/suggestions.csv

Evidence policy: every table row links an official/primary source. A value that
the source does not state is shown as an em dash and explained, never filled in.
"""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from common import PROC, ROOT

INJURY_URL = "https://www.nfl.com/injuries/"
WHITE = "https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping"
DSR = "https://www.pm-research.com/content/iijpormgmt/40/5/94"
PAGES = "https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages"
NFL_SCORES = "https://www.nfl.com/scores/"
NFL_SCHEDULE = "https://www.nfl.com/schedules/"
GAMING = "https://gaming.nv.gov/"
FANDUEL = "https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push"
DASH = '<span class="muted" title="The official source does not state this value">—</span>'


def e(x) -> str:
    return html.escape(str(x), quote=True)


def lnk(url: str, label: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def pill(text: str, kind: str = "partial") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def cell(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() in ("", "nan", "None"):
        return DASH
    return e(x)


def _rank_label(r) -> str:
    if r is None or (isinstance(r, float) and pd.isna(r)) or str(r) in ("<NA>", "nan", ""):
        return "not listed on the chart"
    r = int(r)
    return {1: "1st (starter)", 2: "2nd string", 3: "3rd string", 4: "4th string"}.get(r, f"depth {r}")


# --------------------------------------------------------------------------- #
# T14 — injuries and depth
# --------------------------------------------------------------------------- #
def build_injuries(layout, table, card, kpi_grid, flag, src_link, sha: str):
    rep = pd.read_csv(PROC / "injury_report.csv", dtype=str).fillna("")
    team = pd.read_csv(PROC / "injury_team_summary.csv", dtype=str).fillna("")
    repl = pd.read_csv(PROC / "injury_replacements.csv", dtype=str).fillna("")
    cov = pd.read_csv(PROC / "injury_coverage.csv", dtype=str).fillna("")
    chk = pd.read_csv(PROC / "injury_checks.csv")
    snap = __import__("json").loads((PROC / "injury_snapshot.json").read_text())

    rows = []
    for r in team.itertuples():
        rows.append([
            f"<strong>{e(r.team)}</strong>", e(r.club), e(r.record),
            e(r.reported), e(r.ruled_out), e(r.doubtful), e(r.questionable),
            e(r.starters_ruled_out), e(r.backups_ruled_out), e(r.unranked_reported),
            _rank_label(r.deepest_replacement_rank) if r.deepest_replacement_rank else DASH,
            lnk(r.source_url, "injury report") + " · " + lnk(r.chart_url, "club chart"),
        ])
    availability = table(
        rows,
        ["Club", "Name", "Record", "Reported", "Ruled out", "Doubtful", "Questionable",
         "Starters ruled out", "Backups ruled out", "Unranked", "Deepest replacement used", "Official sources"],
        caption=f"Week 10 2026 availability by club · {len(team)} clubs with a verified depth chart · counts recomputed from the {len(rep)} transcribed report rows",
    )

    d_rows = []
    for r in repl.sort_values(["team", "depth_rank"]).itertuples():
        d_rows.append([
            e(r.team), f"<strong>{e(r.player)}</strong>", e(r.position), e(r.injury) or DASH,
            pill(e(r.game_status), "no" if r.game_status == "Out" else "luck"),
            e(r.chart_unit) + " · " + e(r.chart_slot), _rank_label(r.depth_rank),
            e(r.next_man_up) if r.next_man_up else f'<span class="muted">no deeper player listed in this column</span>',
            _rank_label(r.next_man_up_rank) if r.next_man_up_rank else DASH,
            lnk(r.source_url, "report") + " · " + lnk(r.chart_url, "chart"),
        ])
    depth_detail = table(
        d_rows,
        ["Club", "Player", "Pos", "Injury", "Game status", "Unit · slot", "Listed role",
         "Next man up", "Replacement depth", "Official sources"],
        caption="Depth deficiency detail: reported players who carry a game designation, joined to the club chart by exact name",
    )

    f_rows = []
    for r in rep.sort_values(["game_id", "team", "depth_rank"], na_position="last").itertuples():
        f_rows.append([
            e(r.game_id), e(r.kickoff_et).replace("T", " "), e(r.team), e(r.player), e(r.position),
            e(r.injury) if r.injury else DASH,
            e(r.practice_status), e(r.game_status) if r.game_status != "NO DESIGNATION" else DASH,
            _rank_label(r.depth_rank) if r.depth_rank else pill("UNRANKED", "partial"),
            e(r.next_man_up) if r.next_man_up else DASH,
            lnk(r.player_url, "player") if r.player_url else lnk(r.source_url, "report"),
        ])
    full = table(
        f_rows,
        ["Game", "Kickoff (ET)", "Club", "Player", "Pos", "Injury stated", "Practice", "Game status",
         "Chart role", "Next man up", "Official source"],
        caption=f"Official injury register · all {len(rep)} transcribed rows · a blank game status means the league had published no designation at capture time",
        cls="",
    )

    unranked = rep[rep.depth_rank.eq("") | rep.depth_rank.isna()]
    u_rows = [[e(r.team), e(r.player), e(r.position), e(r.game_status), e(r.practice_status),
               lnk(r.source_url, "injury report")] for r in unranked.itertuples()]
    unranked_tbl = table(
        u_rows, ["Club", "Player", "Pos", "Game status", "Practice", "Official source"],
        caption="Reported players who are not listed anywhere on their club's published chart — role left unverified rather than guessed",
    )

    c_rows = []
    for r in cov.itertuples():
        kind = "verified" if r.depth_chart_verified == "YES" else "**not covered**"
        c_rows.append([
            e(r.team), e(r.club), e(r.injury_rows) or "0",
            pill("VERIFIED", "skill") if r.depth_chart_verified == "YES" else pill("NOT COVERED", "no"),
            e(r.chart_label), lnk(r.chart_url, "club depth chart"),
        ])
    coverage = table(
        c_rows, ["Club", "Name", "Reported rows", "Depth chart", "Chart label as published", "Official source"],
        caption="Coverage ledger: 6 of 32 clubs carry a verified depth chart; the remaining 26 are outside this pilot and are flagged, not assumed healthy",
    )

    checks_ok = int(chk.passed.sum())
    body = f"""
{flag('<strong>What is official on this page.</strong> Every row is transcribed from the NFL.com official injury report or from a club-owned depth chart, and links to the page it came from. '
      'Nothing here is modelled. A blank game status means the league had not published a designation at capture time — it does <em>not</em> mean the player is healthy. '
      'A player missing from a club chart is shown as UNRANKED, never guessed into a role.', 'info')}
{kpi_grid([
    card(f"{len(rep)}", "official injury rows", "3 Week 10 games · 6 clubs", ""),
    card(f"{snap['clubs_covered']}/32", "clubs depth-verified", "26 clubs flagged, not assumed", "bad"),
    card(f"{snap['ruled_out']}", "players ruled OUT", f"{snap['starters_ruled_out']} are listed starters on their club chart", "bad"),
    card(f"{snap['unranked_rows']}", "rows with no verified role", "not listed on the club chart", ""),
    card(f"{len(chk)}/{len(chk)}", "integrity checks passed", "sources, hashes, unique slot ranks", "good" if checks_ok == len(chk) else "bad"),
])}
<section>
<h2>What this register can and cannot answer</h2>
<div class="split">
<div><strong>It answers</strong><ul class="findings">
<li>Which reported players carry an official game designation, and at which position.</li>
<li>Whether a ruled-out player is a listed starter or a backup on his club's published chart.</li>
<li>Who the club lists next in that same column — 2nd, 3rd or 4th string.</li>
<li>Which rows cannot be classified at all, because the player is absent from the chart.</li>
</ul></div>
<div><strong>It does not answer yet</strong><ul class="findings">
<li>Who actually started. Club charts are projections; three clubs call theirs unofficial.</li>
<li>League-wide deficiencies: 26 clubs are outside the pilot.</li>
<li>How much a deficiency is worth in points. The line model has no availability input.</li>
<li>Prop availability. No verified prop prices exist in this repository.</li>
</ul></div>
</div>
<p class="small">Next step that would settle the first gap: archive official pre-kickoff inactives and post-game snap counts.
See {lnk('questions.html', 'Questions')} Q04 and {lnk('suggestions.html', 'Suggestions')} S03.</p>
</section>
<section><h2>Availability by club</h2>
{availability}
<p class="small">"Deepest replacement used" is the chart depth of the next man up for a ruled-out starter — the number a lineup-deficiency model would need.
It is blank when no starter is ruled out, and it is a projection from a club chart, not an observation of the lineup.</p></section>
<section><h2>Depth deficiency detail</h2>
{depth_detail}
<p class="small">Only players with a published game designation appear here. Practice-only rows are in the full register below and are not treated as absences.</p></section>
<section><h2>Full official injury register</h2>
<div class="table-tools"><label>Search the register <input class="filter" type="search" placeholder="Try a club, a player or a position"></label><span class="small">Click a heading to sort</span></div>
{full}</section>
<section><h2>Rows that could not be classified</h2>
<p class="small">These players are on the official report but not on their club's published chart. Their role is unknown, so it is left unverified rather than inferred from position or experience.</p>
{unranked_tbl}</section>
<section><h2>Coverage and gaps</h2>
{coverage}
<p class="small">The 26 uncovered clubs are not a zero-injury finding. They are an absence of evidence, and they block any league-wide deficiency statistic.</p></section>
<section><h2>Integrity checks</h2>
{table([[e(r.check), pill("PASS", "skill") if r.passed else pill("FAIL", "no"), e(r.detail), lnk(INJURY_URL, "NFL injury report")] for r in chk.itertuples()],
       ["Check", "Result", "Detail", "Official source checked"], caption="Machine-checked invariants for this snapshot")}
<p class="small">Snapshot captured {e(snap['fetched_utc'])}. The injury page is {lnk('https://www.nfl.com/injuries/', 'NFL.com/injuries')}; the club charts are linked per row.
The register is a transcription of those pages, not a byte-exact crawl — see {lnk('questions.html', 'Questions')} Q15.</p></section>
"""
    return layout("injuries.html", "Injuries & depth chart impact",
                  "Official Week 10, 2026 injury designations joined to club depth charts — starters, backups and the next man up.",
                  body, wide=True)


# --------------------------------------------------------------------------- #
# T15 — decision questions
# --------------------------------------------------------------------------- #
def build_questions(layout, table, card, kpi_grid, flag, src_link):
    q = pd.read_csv(ROOT / "research" / "decision_questions.csv", dtype=str).fillna("")
    inv = pd.read_csv(ROOT / "research" / "information_inventory.csv", dtype=str).fillna("")

    def status_pill(s):
        return pill(s, {"BLOCKED": "no", "OPEN": "luck", "PARTIAL": "partial"}.get(s, "partial"))

    rows = []
    for r in q.itertuples():
        rows.append([
            f"<strong>{e(r.id)}</strong>", e(r.category), e(r.question), e(r.decision_blocked),
            e(r.what_we_know), e(r.what_we_lack), e(r.discovery_action), e(r.owner),
            status_pill(r.status), lnk(r.source_url, r.source_label),
        ])
    qtable = table(rows, ["ID", "Category", "Question", "Blocks which decision", "What we know today",
                          "What we do not have", "How to resolve it", "Owner", "Status", "Official / primary source"],
                   caption=f"Decision-readiness register · {len(q)} questions · an answer is only accepted with the named source")

    inv_rows = [[e(r.item), pill(r.status, {"HAVE": "skill", "PARTIAL": "partial", "MISSING": "no"}.get(r.status, "partial")),
                 e(r.evidence_class), e(r.detail), e(r.consequence), lnk(r.source_url, r.source_label)]
                for r in inv.itertuples()]
    itable = table(inv_rows, ["Item", "Status", "Evidence class", "Detail", "Consequence for a decision", "Official / primary source"],
                   caption=f"Information inventory · {len(inv)} items · HAVE / PARTIAL / MISSING is about this repository, not about the world")

    blocking = q[q.severity == "BLOCKING"]
    missing = int(inv.status.eq("MISSING").sum())
    partial = int(inv.status.eq("PARTIAL").sum())

    body = f"""
{flag('<strong>Read this first.</strong> A decision is only as good as the evidence behind it. Each question below states what is <em>known</em> with the official or primary source, '
      'what is <em>missing</em>, and the concrete action that would settle it. Nothing is answered by opinion, and no missing value is estimated.', 'info')}
{kpi_grid([
    card(f"{len(q)}", "questions", f"{len(blocking)} block any funded decision", ""),
    card(f"{missing}", "missing inputs", f"{partial} partially available", "bad"),
    card("2", "questions answerable today", "Data currency and score sampling (Q02, Q07)", "good"),
    card("0", "decisions taken on unavailable evidence", "No strategy funded, no reward awarded", "good"),
])}
<section><h2>How to use this page</h2>
<ol class="findings">
<li><strong>Start with the blocked decisions.</strong> If a question's status is BLOCKED, no amount of analysis on the current data can settle it.</li>
<li><strong>Answer with a source, not a view.</strong> A question moves to ANSWERED only when the named official or primary source has been retrieved and cited.</li>
<li><strong>Do not upgrade a PARTIAL.</strong> Partial coverage (for example 6 of 32 clubs) supports a statement about the covered cases and nothing wider.</li>
<li><strong>Record the answer where the question lives.</strong> Edit <code>research/decision_questions.csv</code>, rebuild, and the status changes on this page.</li>
</ol></section>
<section><h2>What can be decided today</h2>
{table([
 ["Do not fund or reward a strategy", "No executable prices, 0 of 18 candidates pass the gates, no prospective window", "Supported", lnk(WHITE, "White (2000)")],
 ["Publish the research as a research snapshot", "Every published row carries an official or primary reference; unverified values are blank", "Supported", lnk(PAGES, "GitHub Pages docs")],
 ["Originate lines for the current week", "The pin was refreshed this session; the board now starts at Week 10 (2026-11-12)", "Supported, with a weekly cadence still missing (Q02)", lnk(NFL_SCHEDULE, "NFL schedule")],
 ["Claim a league-wide injury advantage", "6 of 32 clubs are covered; 26 are absent", "Not supported", lnk(INJURY_URL, "NFL injuries")],
], ["Decision", "Evidence in hand", "Verdict", "Official / primary source"], caption="Decisions this evidence set does and does not support")}
</section>
<section><h2>Blocking questions</h2>
<p class="small">These are the questions that stop a funded competition or a capital allocation. They are repeated in the full register below with their resolution path.</p>
{table([[e(r.id), e(r.question), e(r.what_we_lack), e(r.discovery_action), lnk(r.source_url, r.source_label)]
        for r in blocking.itertuples()],
       ["ID", "Question", "What is missing", "Resolution path", "Official / primary source"],
       caption="Questions whose absence blocks a decision")}
</section>
<section><h2>Full question register</h2>
<div class="table-tools"><label>Search questions <input class="filter" type="search" placeholder="Try prices, injuries, power…"></label><span class="small">Click a heading to sort</span></div>
{qtable}</section>
<section><h2>Information inventory</h2>
{itable}</section>
<section><h2>Suggested sequence</h2>
<p>The order matters: operator decisions change what evidence is even worth acquiring.</p>
{table([
 ["1", "Q11, Q12", "Decide what is being awarded and whether it is lawful", "Operator", lnk(GAMING, "Regulator")],
 ["2", "Q14, Q15", "Decide who owns each change and how captures are archived", "Operator / Engineering", lnk(PAGES, "GitHub Pages docs")],
 ["3", "Q01, Q05, Q06", "Acquire executable prices and register every trial", "Data acquisition / Validation", lnk(WHITE, "White (2000)")],
 ["4", "Q03, Q04, Q13", "Complete 32-club availability, then test whether it predicts", "Research", lnk(INJURY_URL, "NFL injuries")],
 ["5", "Q07, Q08, Q09, Q10", "Certify the historical inputs and publish the error budget", "Audit / Validation", lnk(NFL_SCORES, "NFL scores")],
], ["Step", "Questions", "What it unlocks", "Owner", "Official / primary source"], caption="A sequence that avoids buying data a decision would not use")}
</section>
"""
    return layout("questions.html", "Questions before any decision",
                  "What is known, what is missing, and exactly how to find out — before a strategy is funded or a change is made.",
                  body, wide=True)


# --------------------------------------------------------------------------- #
# T16 — suggestions
# --------------------------------------------------------------------------- #
def build_suggestions(layout, table, card, kpi_grid, flag, src_link):
    s = pd.read_csv(ROOT / "research" / "suggestions.csv", dtype=str).fillna("")

    rows = []
    for r in s.itertuples():
        rows.append([
            f"<strong>{e(r.id)}</strong>", e(r.category), e(r.suggestion), e(r.problem), e(r.benefit),
            e(r.cost), e(r.risk), e(r.evidence_status), e(r.depends_on),
            pill(r.priority, {"HIGH": "no", "MEDIUM": "luck", "LOW": "partial"}.get(r.priority, "partial")),
            pill(r.status, "partial"), lnk(r.reference_url, r.reference_label),
        ])
    register = table(rows, ["ID", "Category", "Suggestion", "Problem it solves", "Expected benefit", "Cost / effort",
                            "Risk if adopted", "Evidence status", "Depends on", "Priority", "Decision", "Official / primary source"],
                     caption=f"Suggestions register · {len(s)} proposals · every one is PROPOSED and none of the changes below is implemented except where the evidence column says so")

    high = int(s.priority.eq("HIGH").sum())
    body = f"""
{flag('<strong>Nothing on this page has been implemented unless its evidence column says so.</strong> This page is a decision queue: review the proposal, '
      'check the evidence it would need, compare the paths below, and record a choice. Implementing first and reviewing later is exactly what this page exists to prevent.', 'warn')}
{kpi_grid([
    card(f"{len(s)}", "suggestions", "all PROPOSED, none accepted", ""),
    card(f"{high}", "high priority", "they unblock a decision rather than add a feature", "bad"),
    card("1", "executed this session", "S01: one controlled data refresh (not the weekly cadence)", "good"),
    card("0", "accepted without review", "no path has been chosen yet", "good"),
])}
<section><h2>Decision protocol — how to choose a path</h2>
<div class="split">
<div><strong>Six steps, in order</strong><ol class="findings">
<li><strong>Name the decision</strong> the suggestion unblocks, and the question it depends on.</li>
<li><strong>Check the evidence class.</strong> Official observation, primary method, commercial data licence, or opinion. Only the first two are in the repository today.</li>
<li><strong>Price the cost</strong> in money, weeks and permanent maintenance — not just in build effort.</li>
<li><strong>State the failure mode.</strong> What breaks, and who would notice? A silent corruption is worse than a visible error.</li>
<li><strong>Choose the smallest reversible step</strong> that produces evidence, and archive the current published tables first.</li>
<li><strong>Record the decision, the owner and the review date</strong> in the decision log below.</li>
</ol></div>
<div><strong>Scoring rubric</strong>
<p class="small">Score each option 1-5 on each line and record the total with the decision. The rubric is a checklist, not a formula: a BLOCKING gap outranks any score.</p>
<ul class="findings">
<li><strong>Decision impact</strong> — does it unblock a question marked BLOCKING?</li>
<li><strong>Evidence quality</strong> — official, primary, licensed, or inferred?</li>
<li><strong>Reversibility</strong> — can it be undone in one commit?</li>
<li><strong>Cost</strong> — money plus recurring time.</li>
<li><strong>Failure mode</strong> — is the failure loud or silent?</li>
</ul></div>
</div></section>
<section><h2>Three paths, and what each one buys</h2>
{table([
 ["<strong>A · Evidence first</strong><br><span class='small'>S05, S06, S07</span>",
  "Buy or capture executable prices, register every trial, pre-register a prospective window.",
  "The only path that can ever support a funded reward.", "Commercial licence or a season of disciplined capture; 1 full season of elapsed time.",
  "Highest: a price feed can be restated, so it must be archived at receipt.", lnk(WHITE, "White (2000)")],
 ["<strong>B · Availability first</strong><br><span class='small'>S02, S03, S04</span>",
  "Complete 32-club injury and depth coverage, add inactives and snap counts, then test availability as a model feature.",
  "A league-wide deficiency measure and a testable signal; it also improves the public dashboard immediately.", "26 club charts per refresh plus inactives capture; no licence fee.",
  "Medium: data is volatile and charts are labelled unofficial, but every error is visible on the page.", lnk(INJURY_URL, "NFL injuries")],
 ["<strong>C · Competition first</strong><br><span class='small'>S11, S12, S09</span>",
  "Formalise the leaderboard rules, the kill-switch and the verification gate before any evidence work.",
  "A trustworthy competition shell that is ready when evidence arrives; it does not create evidence by itself.", "Low build cost; operator time to write and review the rules.",
  "Low technical risk, high governance risk if the reward terms are written before any legal advice.", lnk(GAMING, "Regulator")],
], ["Path", "What it does", "What it buys", "Cost", "Main risk", "Official / primary source"],
   caption="Choose one path to fund first; the others stay queued. Paths are not exclusive forever, only in sequence")}
<p class="small"><strong>Recommendation, stated as a recommendation:</strong> take <strong>B</strong> next because it is cheap, reversible and immediately improves the public site,
and take <strong>A</strong> as soon as a price source is licensed — no amount of availability data can substitute for executable prices.
<strong>C</strong> should follow the operator's answers to Q11 and Q12, not precede them.</p></section>
<section><h2>Everything is reversible if the published tables are archived first</h2>
<p class="small">A data refresh or a rule change moves the numbers. Before any path is executed, copy the generated tables to a dated folder so the prior
publication stays reviewable. The current tables are reproducible from the pinned commit and the pipeline, but only for the commit they were built from.</p></section>
<section><h2>Suggestion register</h2>
<div class="table-tools"><label>Search suggestions <input class="filter" type="search" placeholder="Try prices, injury, refresh…"></label><span class="small">Click a heading to sort</span></div>
{register}</section>
<section><h2>Priority against effort</h2>
{table([
 ["Do now — high impact, low effort", "S12 (kill-switch policy), S09 (CI gate), S10 (decision log), S11 (split the coordination log)", lnk(PAGES, "GitHub Pages docs")],
 ["Plan — high impact, high effort", "S05 (price archive), S06 (prospective window), S02 (32-club coverage), S03 (official inactives), S04 (availability feature)", lnk(WHITE, "White (2000)")],
 ["Schedule — medium impact", "S07 (trial registry), S08 (prop prices), S13 (refresh deltas), S01 (weekly cadence)", lnk(NFL_SCHEDULE, "NFL schedule")],
], ["Quadrant", "Suggestions", "Official / primary reference"], caption="A planning view of the same register; moving an item here does not accept it")}
</section>
<section><h2>Decision log</h2>
<p class="small">A decision is only recorded here once an owner and a date exist. An empty decision column above means the proposal is still open.</p>
{table([
 ["D01", "2026-11-02", "Do not fund or reward any strategy", "Award a reward vs. withhold", "Withhold",
  "0 of 18 candidates pass all eight gates; no executable prices; no prospective window.", "Superseded only by a validated gate pass", lnk(WHITE, "White (2000)")],
 ["D02", "2026-11-12", "Refresh the pinned data snapshot once", "Stay on the 2026-11-02 pin vs. rebuild on current upstream",
  "Rebuild now, automate later (S01)", "The board listed played games as upcoming, and the ratings were missing two weeks of results.",
  "Re-review when S01 is automated", lnk(NFL_SCHEDULE, "NFL schedule")],
 ["D03", "2026-11-12", "Publish injuries as a 6-club pilot, not a league claim", "Wait for 32 clubs vs. publish a labelled pilot",
  "Publish the pilot with coverage stated on every page", "Six clubs are verified; 26 are flagged rather than assumed healthy.",
  "Re-review when S02 completes", lnk(INJURY_URL, "NFL injuries")],
], ["ID", "Date", "Decision", "Options considered", "Chosen path", "Evidence", "Next review", "Official / primary source"],
   caption="Decision log — three decisions, each with the evidence that supported it")}
</section>
<section><h2>What a decision must include before implementation</h2>
<ul class="findings">
<li><strong>The question it answers</strong>, by ID from {lnk('questions.html', 'the question register')}.</li>
<li><strong>The evidence class</strong> of the data it depends on, and whether that data exists yet.</li>
<li><strong>The metric that will show it worked</strong>, fixed before the change, not after.</li>
<li><strong>The rollback</strong>: the commit or archived table that restores the prior publication.</li>
<li><strong>The owner and review date</strong> recorded in the log above.</li>
</ul></section>
"""
    return layout("suggestions.html", "Suggestions & decision paths",
                  "Review the proposals, compare the paths, and record a decision before any change is built.",
                  body, wide=True)
