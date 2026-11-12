"""G2/G3/G4 HTML builders for:
  * suggestions-review.html  — Dedicated Suggestions Review Queue (review & choose path before changes)
  * decision-readiness.html  — Pre-Decision Questions, Knowns/Unknowns & Missing-Info Discovery
  * lineup-deficiencies.html — Offense & Defense Injuries + 1st/2nd/3rd/4th-String Backup Tracker
plus modular sections embedded into index.html, audit.html, flagged.html, and requirements.html.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json  # noqa: E402

GOV_DIR = ROOT / "data" / "governance"
LIN_DIR = ROOT / "data" / "lineups"

BLANK = '<span class="blank" aria-label="blank: unverified"></span>'
BLANK_SOURCE = '<span class="blank" aria-label="blank: not listed on source"></span> <span class="unverified">UNVERIFIED · blank on source</span>'


def _e(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return html.escape(str(x), quote=True)


def _cell_or_blank(val: str) -> str:
    s = "" if val is None or (isinstance(val, float) and pd.isna(val)) else str(val).strip()
    return _e(s) if s else BLANK_SOURCE


def _tier_pill(tier: str) -> str:
    t = str(tier)
    if any(k in t for k in ("OUT", "3RD_4TH", "DEPLETED", "CHAIN", "BLOCKS CAPITAL")):
        cls = "no"
    elif any(k in t for k in ("DNP", "LIMITED", "MULTI", "ELEVATED", "DISCREPANCY", "QUESTIONABLE", "BLOCKS LIVE", "PROPOSED")):
        cls = "luck"
    elif "FULL" in t or "RESOLVED" in t:
        cls = "skill"
    else:
        cls = "unverified"
    return f'<span class="pill {cls}">{_e(t.replace("_", " "))}</span>'


def load_governance_data() -> dict:
    return {
        "suggestions": pd.read_csv(GOV_DIR / "suggestions_review.csv"),
        "questions": pd.read_csv(GOV_DIR / "decision_questions.csv"),
        "discovery": pd.read_csv(GOV_DIR / "missing_info_discovery.csv"),
        "post_scores": pd.read_csv(GOV_DIR / "post_pin_nfl_scores_2026_11_12.csv"),
        "repo_review": pd.read_csv(GOV_DIR / "repo_verification_2026_11_12.csv"),
        "gov_summary": read_json(GOV_DIR / "summary_2026_11_12.json"),
        "wk10_lineups": pd.read_csv(LIN_DIR / "week10_2026_injuries_depth.csv", keep_default_na=False),
        "wk10_matchups": pd.read_csv(LIN_DIR / "week10_2026_matchup_deficiencies.csv", keep_default_na=False),
        "pbp_impact": pd.read_csv(LIN_DIR / "pbp_backup_impact.csv"),
        "lineup_sources": read_json(LIN_DIR / "sources_lineups.json"),
    }


def build_suggestions_page(layout, table, card, kpi_grid, flag, src_link) -> str:
    g = load_governance_data()
    sug = g["suggestions"]
    n_total = len(sug)
    n_p0 = int(sug["priority"].str.startswith("P0").sum())
    n_cats = int(sug["category"].nunique())

    cards = kpi_grid([
        card(str(n_total), "staged site & model suggestions", "All held for review before model/gate edits", ""),
        card(str(n_p0), "P0 critical-blocker items", "Quote logging, 90m inactives & depth reconciliation", "bad"),
        card(str(n_cats), "decision categories", "Lineups · Provenance · UX · Validation", ""),
        card("0", "unauthorized model mutations", "Canonical backtest & gates stay frozen until path chosen", "good"),
    ])

    rows = []
    for r in sug.itertuples(index=False):
        options_html = (
            f"<div><strong>A:</strong> {_e(r.path_a)}</div>"
            f"<div class='opt-mid'><strong>B:</strong> {_e(r.path_b)}</div>"
            f"<div><strong>C:</strong> {_e(r.path_c)}</div>"
        )
        selector_html = (
            f'<div class="path-picker" data-sug-id="{_e(r.id)}" data-recommended="{_e(r.recommended_path)}">'
            f'<div><strong>Recommended: {_e(r.recommended_path)}</strong></div>'
            f'<label class="small">Reviewer choice: '
            f'<select class="path-select" aria-label="Choose path for {_e(r.id)}">'
            f'<option value="Pending review">Pending review (no change yet)</option>'
            f'<option value="Path A">Approve Path A (Conservative)</option>'
            f'<option value="Path B">Approve Path B (Balanced)</option>'
            f'<option value="Path C">Approve Path C (Full build)</option>'
            f'<option value="Defer">Defer / Reject</option>'
            f'</select></label>'
            f'<div>{_tier_pill(r.review_state)}</div></div>'
        )
        rows.append([
            f'<strong>{_e(r.id)}</strong><br><span class="small">{_e(r.priority)}</span><br><span class="muted">{_e(r.category)}</span>',
            f'<strong>{_e(r.title)}</strong><br><span class="small"><strong>Gap:</strong> {_e(r.current_gap)}</span><br><span class="small"><strong>Decision impact:</strong> {_e(r.decision_impact)}</span>',
            options_html,
            f'{_e(r.tradeoff_summary)}<br><span class="muted">Gates: {_e(r.gate_affected)}</span>',
            selector_html,
            src_link(r.official_ref_url, r.official_ref_label),
        ])

    cat_rows = []
    for cat_name, sub in sug.groupby("category", sort=False):
        ids = ", ".join(sub["id"].tolist())
        rec = ", ".join(f"{r.id}→{r.recommended_path}" for r in sub.itertuples())
        ref_url = sub.iloc[0]["official_ref_url"]
        ref_lbl = sub.iloc[0]["official_ref_label"]
        cat_rows.append([
            _e(cat_name),
            str(len(sub)),
            _e(ids),
            _e(rec),
            "Staged for human path selection — zero unapproved changes applied",
            src_link(ref_url, ref_lbl),
        ])

    body = f"""
{flag('<strong>Review-before-implementation governance.</strong> Every suggestion below is staged in a dedicated review queue so a decision-maker can compare Conservative (Path A), Balanced (Path B), and Full (Path C) options and choose the best path <strong>before</strong> altering the frozen line-origination model, historical pin, or validation-gate thresholds.', 'info')}
{cards}
<section id="reviewer-console">
  <div class="section-head">
    <h2>Reviewer path-selection summary</h2>
    <div class="actions">
      <button type="button" class="btn primary" id="apply-recommended-paths">Pre-fill recommended paths (preview only)</button>
      <button type="button" class="btn" id="reset-paths">Reset all to Pending</button>
      <button type="button" class="btn" id="export-paths">Copy decision record JSON</button>
    </div>
  </div>
  <p class="small">Selections are stored locally in your browser for review only and never mutate repository files or model outputs until explicitly implemented. Without JavaScript, the full comparison matrix below remains 100% readable.</p>
  <pre class="pipeline" id="path-selection-output" aria-live="polite">Reviewer status: all {n_total} suggestions are currently PENDING REVIEW (no changes implemented).</pre>
  {table(cat_rows, ["Category", "Count", "Suggestion IDs", "Recommended defaults", "Governance state", "Official / primary reference"],
         caption="Summary of improvement suggestions by decision category")}
</section>

<section id="suggestions-matrix">
  <div class="section-head">
    <h2>Complete site &amp; decision-making suggestions register</h2>
    <a href="assets/data/suggestions_review.csv">Download suggestions CSV →</a>
  </div>
  <div class="table-tools">
    <label>Filter suggestions <input class="filter" type="search" placeholder="Search lineup, parlay, quote, P0, Path B…"></label>
    <span class="small">All {n_total} suggestions shown · click any column header to sort</span>
  </div>
  {table(rows, ["ID & priority", "Suggestion, verified gap & decision impact", "Candidate paths (A / B / C)", "Trade-offs & gates", "Path review & state", "Official reference"],
         caption="Dedicated review register — choose a path before implementing model, data, or rule changes")}
</section>

<section id="recommended-sequence">
  <h2>Recommended phased roadmap (if approved by reviewer)</h2>
  <ol class="findings">
    <li><strong>Phase 1 — Zero-cost provenance &amp; safety gates (SUG-03 Path B, SUG-05 Path B, SUG-09 Path B, SUG-12 Path A):</strong> Separate the weekly 2026 score sync from the frozen 1999–2025 backtest pin, start logging timestamped multi-book pre-kickoff quotes, and enforce an append-only strategy trial ledger.</li>
    <li><strong>Phase 2 — Lineup &amp; stadium timing integration (SUG-01 Path B, SUG-02 Path B, SUG-08 Path B, SUG-10 Path B):</strong> Ingest T-90m official club inactive lists + prior-week NFL Gamebook offensive/defensive snap shares + T-60m stadium roof/weather locks to adjust starter-blind team and prop estimates.</li>
    <li><strong>Phase 3 — Dashboard matchup workflow &amp; SGP quote testing (SUG-04 Path B, SUG-06 Path B, SUG-07 Path A/B, SUG-11 Path B):</strong> Pair standalone prop prices against actual SGP combo quotes and surface unified per-game readiness cards.</li>
  </ol>
</section>
"""
    return layout(
        "suggestions-review.html",
        "Suggestions for review",
        "Structured improvement proposals, candidate paths, and trade-offs — staged for review before implementing model or rule changes.",
        body,
        wide=True,
    )


def build_decision_readiness_page(layout, table, card, kpi_grid, flag, src_link) -> str:
    g = load_governance_data()
    dq = g["questions"]
    mi = g["discovery"]
    ps = g["post_scores"]

    n_q = len(dq)
    n_cap = int((dq["blocker_severity"] == "BLOCKS CAPITAL & REWARDS").sum())
    n_live = int((dq["blocker_severity"] == "BLOCKS LIVE SLATE PRICING").sum())
    n_mi = len(mi)

    cards = kpi_grid([
        card(str(n_q), "pre-decision questions", "Mapped to knowns, unknowns & current answers", ""),
        card(str(n_cap), "block capital & rewards", "Must be resolved before funding any strategy", "bad"),
        card(str(n_live), "block live slate pricing", "Lineup strings, depth lag & post-pin schedule sync", ""),
        card(str(n_mi), "discovery protocols", "Concrete blueprints to acquire missing evidence", "good"),
    ])

    q_rows = []
    for r in dq.itertuples(index=False):
        q_rows.append([
            f'<strong>{_e(r.id)}</strong><br><span class="muted">{_e(r.domain)}</span>',
            f'<strong>{_e(r.question)}</strong>',
            _e(r.info_we_have),
            _e(r.info_we_lack),
            f'{_e(r.current_answer)}<br>{_tier_pill(r.blocker_severity)}',
            _e(r.discovery_action),
            src_link(r.official_ref_url, r.official_ref_label),
        ])

    mi_rows = []
    for r in mi.itertuples(index=False):
        mi_rows.append([
            f'<strong>{_e(r.id)}</strong>',
            f'<strong>{_e(r.missing_information)}</strong>',
            _e(r.why_currently_missing),
            _e(r.discovery_method),
            f'{_e(r.timing_cadence)}<br><span class="muted">Unlocks: {_e(r.unlocks_gates)}</span>',
            src_link(r.official_ref_url, r.official_ref_label),
        ])

    ps_rows = []
    for r in ps.itertuples(index=False):
        ps_rows.append([
            f'<code>{_e(r.game_id)}</code>',
            f'Week {int(r.week)} · {_e(r.gameday)}',
            _e(r.matchup),
            f'<strong>{_e(r.nfl_com_final)}</strong>',
            f'{BLANK} <span class="unverified">UNVERIFIED / UPCOMING in pin</span>',
            _tier_pill(r.audit_flag),
            src_link(r.nfl_com_url, "NFL.com Game Center"),
        ])

    body = f"""
{flag('<strong>Decision-readiness principle.</strong> No capital allocation, live line release, parlay/prop bet, or leaderboard reward is reasonable until the blocking questions below have verified answers. Every cell separates <em>what we already have</em> from <em>what we do not have</em>, without guessing.', 'warn')}
{cards}
<section id="questions-register">
  <div class="section-head">
    <h2>Questions, known information, missing information &amp; answers ({n_q} items)</h2>
    <a href="assets/data/decision_questions.csv">Download Q&amp;A CSV →</a>
  </div>
  <div class="table-tools">
    <label>Filter questions <input class="filter" type="search" placeholder="Search parlays, props, defense, depth chart, luck…"></label>
    <span class="small">Click any column heading to sort</span>
  </div>
  {table(q_rows,
         ["ID & domain", "Question to address before deciding", "Information we already have (verified)", "Information we do NOT have (missing)", "Evidence-based answer & blocker", "Suggestion to discover missing info", "Official reference"],
         caption="Pre-decision question, evidence, and answer register")}
</section>

<section id="missing-info-discovery">
  <div class="section-head">
    <h2>Suggestions to discover missing information ({n_mi} protocols)</h2>
    <a href="assets/data/missing_info_discovery.csv">Download discovery blueprint CSV →</a>
  </div>
  <p>Each discovery workflow targets a specific missing input identified above, aligns collection timestamps with official NFL pregame deadlines, and names the validation gates it unlocks.</p>
  {table(mi_rows,
         ["ID", "Missing information", "Why current repository lacks it", "Concrete discovery workflow", "Cadence & gates unlocked", "Official reference"],
         caption="Actionable blueprints to discover missing market, lineup, prop, and environmental evidence")}
</section>

<section id="post-pin-reconciliation">
  <div class="section-head">
    <h2>Concrete freshness proof: {len(ps)} post-pin games settled on NFL.com (Weeks 8–9, 2026)</h2>
    <a href="assets/data/post_pin_nfl_scores_2026_11_12.csv">Download reconciliation CSV →</a>
  </div>
  <p>The pinned archive (<code>a270278f3ac4</code>, captured 2026-11-01) intentionally does not auto-refresh so historical backtests stay byte-identical. As of <strong>2026-11-12</strong> (Week 10), all 28 Week 8 and Week 9 games below are <strong>Final on NFL.com</strong> while still appearing in <code>upcoming.csv</code> — directly illustrating why DQ-06 and <a href="suggestions-review.html">SUG-05</a> must be resolved before live-slate use.</p>
  <div class="table-tools">
    <label>Filter games <input class="filter" type="search" placeholder="Search week 9, KC, DET, MIN, GB…"></label>
  </div>
  {table(ps_rows,
         ["Game ID", "Week & date", "Matchup", "Official NFL.com result (read 2026-11-12)", "Pinned archive score", "Audit status", "Official Game Center"],
         caption="All 28 Week 8 and Week 9 2026 games settled on NFL.com after the 2026-11-01 repository snapshot")}
</section>
"""
    return layout(
        "decision-readiness.html",
        "Pre-decision Q&A & missing information",
        "What we know, what we do not know, what answers block a reasonable decision today, and how to discover every missing input.",
        body,
        wide=True,
    )


def build_lineups_page(layout, table, card, kpi_grid, flag, src_link) -> str:
    g = load_governance_data()
    wk = g["wk10_lineups"]
    mm = g["wk10_matchups"]
    pbp = g["pbp_impact"]
    lsrc = g["lineup_sources"]

    def_df = wk[wk["unit"] == "Defense"]
    off_df = wk[wk["unit"] == "Offense"]
    n_3rd4th = int(wk["deficiency_tier"].str.contains("3RD|4TH|DEPLETED|CHAIN|MULTI").sum())

    cards = kpi_grid([
        card(str(len(wk)), "Week 10 lineup entries verified", "8 NFL clubs · 4 complete Week 10 matchups (2026-11-12)", ""),
        card(str(len(def_df)), "defensive injury/depth rows", "Tracks 1st-string outs & 2nd/3rd/4th-string backups", ""),
        card(str(len(off_df)), "offensive injury/depth rows", "Tracks QB/RB/WR/TE/OL starters & 2nd–4th strings", ""),
        card(str(n_3rd4th), "multi-string / 3rd–4th string alerts", "Positions stressed beyond primary 2nd-string cover", "bad"),
    ])

    def _unit_rows(sub: pd.DataFrame) -> list[list[str]]:
        out = []
        for r in sub.itertuples(index=False):
            srcs = (
                src_link(r.player_url, "NFL.com player") + " · " +
                src_link(r.official_injury_url, "NFL Week 10 report") + "<br>" +
                src_link(r.club_depth_url, f"{r.club} depth chart")
            )
            out.append([
                f'<strong>{_e(r.club)}</strong><br><span class="muted">{_e(r.matchup)}</span>',
                f'<strong>{_e(r.pos_depth)}</strong><br><span class="muted">Report pos: {_e(r.pos_injury)}</span>',
                f'<strong>{_e(r.player)}</strong><br><span class="small">{_e(r.player_string)}</span>',
                f'Injury: {_cell_or_blank(r.injury)}<br>Practice: <strong>{_e(r.practice_status)}</strong><br>Game status: {_cell_or_blank(r.game_status)}',
                _cell_or_blank(r.string_1),
                _cell_or_blank(r.string_2),
                _cell_or_blank(r.string_3),
                _cell_or_blank(r.string_4),
                f'<strong>{_e(r.active_replacement)}</strong><br>{_tier_pill(r.deficiency_tier)}<br><span class="small">{_e(r.deficiency_note)}</span>',
                srcs,
            ])
        return out

    matchup_rows = [
        [
            f'<strong>{_e(r.matchup)}</strong><br><span class="muted">{_e(r.kickoff)}</span>',
            _e(r.away_offense_state),
            _e(r.home_defense_state),
            _e(r.home_offense_state),
            _e(r.away_defense_state),
            _e(r.net_lineup_flags),
            src_link(r.official_source, "NFL Week 10 injuries"),
        ]
        for r in mm.itertuples(index=False)
    ]

    club_rows = []
    for club, meta in lsrc["official_sources"]["club_depth_charts"].items():
        club_rows.append([
            f'<strong>{_e(club)}</strong>',
            _e(meta["disclaimer"]),
            "Cross-checked against NFL.com Week 10 Injury Report on 2026-11-12; unlisted players flagged rather than inferred",
            src_link("https://www.nfl.com/injuries/", "NFL Week 10 injuries") + " · " + src_link(meta["url"], f"{club} club depth chart"),
        ])

    protocol_rows = [
        ["Wednesday–Friday Practice & Game Status Reports", "Clubs report Did Not Participate, Limited, or Full practice participation plus Out / Doubtful / Questionable game designations.", "Verified live for 2026 Week 10 on 2026-11-12; blank cells on NFL.com remain blank here.", src_link("https://www.nfl.com/injuries/", "NFL.com Injuries")],
        ["T-90 Minutes: Officiating Meeting & Game Day Administration Report", "Club PR directors deliver the official Inactive List, primary/backup C2P helmet designations, and retractable roof/wall state to the Referee.", "Authoritative starter/backup lock; NFL.com/inactives returned a blank placeholder on 2026-11-12, so club PR feeds are required.", src_link(lsrc["official_sources"]["nfl_game_prep_90min_rule"], "NFL Operations Countdown")],
        ["T-60 Minutes: Medical Meeting, Warm-ups & Roof Lock", "Head team physicians, AT spotters, UNCs, and Referee meet; stadium roof/wall locked in designated position; official warm-ups begin.", "Late warm-up scratches after T-90m remain active on roster but may yield zero snaps — requires post-game snap audit.", src_link(lsrc["official_sources"]["nfl_game_prep_90min_rule"], "NFL Operations Countdown")],
        ["In-Game ATC Spotters & Concussion Protocol", "Independent Certified Athletic Trainers and unaffiliated neurotrauma consultants can halt play and remove injured starters mid-game.", "Mid-game starter exits cannot be predicted pre-kickoff; affects prop variance and SGP void/settlement risk.", src_link(lsrc["official_sources"]["nfl_player_health_safety"], "NFL Player Health & Safety")],
    ]

    pbp_rows = []
    for r in pbp.itertuples(index=False):
        pbp_rows.append([
            f'<strong>{_e(r.role)}</strong>',
            _e(r.lineup_state),
            str(int(r.n_team_games)),
            BLANK,
            BLANK,
            '<span class="pill unverified">UNVERIFIED</span> <span class="small">community PBP proxy; see CSV</span>',
            src_link(r.official_context_url, "NFL Week 10 injuries"),
        ])

    body = f"""
{flag('<strong>Offense &amp; defense lineup deficiency tracking (verified 2026-11-12).</strong> Every Week 10 injury status and 1st-, 2nd-, 3rd-, and 4th-string replacement chain below was verified line by line against <a href="https://www.nfl.com/injuries/">NFL.com Injuries</a> and official NFL club depth charts. Where an official source leaves an injury, game status, or 3rd/4th-string slot blank—or where a club depth chart lags a trade (e.g., Kirk Cousins on MIN, Micah Parsons on GB, Lucas Patrick on WAS)—the cell is left blank and explicitly flagged.', 'info')}
{cards}

<section id="matchup-matrix">
  <div class="section-head">
    <h2>Week 10 matchup-level offense vs defense deficiency summary</h2>
    <a href="assets/data/week10_2026_matchup_deficiencies.csv">Download matchup CSV →</a>
  </div>
  <p>Evaluates offensive starter/backup health directly against the opposing defense's 1st–4th string deficiencies before any line or prop decision is considered.</p>
  {table(matchup_rows,
         ["Matchup & kickoff", "Away offense (starters vs backups)", "Home defense (starters vs backups)", "Home offense (starters vs backups)", "Away defense (starters vs backups)", "Matchup deficiency synthesis", "Official source"],
         caption="Side-by-side offense vs defense starter and backup string synthesis for four Week 10 2026 matchups")}
</section>

<section id="defensive-deficiencies">
  <div class="section-head">
    <h2>Defensive injuries &amp; 1st / 2nd / 3rd / 4th-string replacement tracker ({len(def_df)} entries)</h2>
    <a href="assets/data/week10_2026_injuries_depth.csv">Download full lineup CSV →</a>
  </div>
  <div class="table-tools">
    <label>Filter defensive rows <input class="filter" type="search" placeholder="Search CB, LB, Out, 3rd string, DET, NE, GB…"></label>
    <span class="small">Blank source fields are never inferred</span>
  </div>
  {table(_unit_rows(def_df),
         ["Club & game", "Position", "Tracked defender & role", "Official NFL.com status", "1st string (starter)", "2nd string", "3rd string", "4th string", "Replacement & deficiency diagnosis", "Official sources"],
         caption="Verified Week 10 2026 defensive injuries mapped across 1st, 2nd, 3rd, and 4th depth-chart strings")}
</section>

<section id="offensive-deficiencies">
  <div class="section-head">
    <h2>Offensive injuries &amp; 1st / 2nd / 3rd / 4th-string replacement tracker ({len(off_df)} entries)</h2>
    <a href="assets/data/week10_2026_injuries_depth.csv">Download full lineup CSV →</a>
  </div>
  <div class="table-tools">
    <label>Filter offensive rows <input class="filter" type="search" placeholder="Search QB, RB, OL, Out, 4th string, MIN, NE, GB…"></label>
    <span class="small">Blank source fields are never inferred</span>
  </div>
  {table(_unit_rows(off_df),
         ["Club & game", "Position", "Tracked offensive player & role", "Official NFL.com status", "1st string (starter)", "2nd string", "3rd string", "4th string", "Replacement & deficiency diagnosis", "Official sources"],
         caption="Verified Week 10 2026 offensive injuries mapped across 1st, 2nd, 3rd, and 4th depth-chart strings")}
</section>

<section id="historical-backup-research">
  <div class="section-head">
    <h2>Walk-forward starter vs backup impact diagnostics (2019–2022 research archive)</h2>
    <a href="assets/data/pbp_backup_impact.csv">Download calculated research CSV →</a>
  </div>
  <p>Using strictly prior-game usage in <code>prop_player_games.csv</code> (zero lookahead, prefix-stability tested), team-games were grouped by whether the pregame 1st-string starter, 2nd-string backup, or 3rd/4th-string emergency replacement led usage, then compared against the starter-blind <code>originated_lines.csv</code> expectation. Numeric point estimates stay blank in this strict public table because community play-by-play is not an official 90-minute inactive census; inspect <code>assets/data/pbp_backup_impact.csv</code> for the full research figures.</p>
  {table(pbp_rows,
         ["Offensive role", "Lineup string state (prior-usage rank)", "Research sample (team-games)", "Estimate: mean team pts", "Estimate: starter-blind residual", "Evidence status", "Official context"],
         caption="Strict public view of historical starter-vs-backup diagnostics; unverified community-PBP estimates remain blank")}
</section>

<section id="governance-and-disclaimers">
  <h2>Official NFL pregame countdown &amp; club depth-chart provenance</h2>
  {table(protocol_rows,
         ["Milestone", "Official NFL operational rule", "Implication for line & prop modeling", "Official source"],
         caption="Official NFL Football Operations pregame availability and stadium governance timeline")}
  {table(club_rows,
         ["Club", "Verbatim depth-chart provenance / disclaimer (read 2026-11-12)", "Verification disposition", "Official links"],
         caption="Provenance of the eight NFL club depth charts audited for Week 10 2026")}
</section>
"""
    return layout(
        "lineup-deficiencies.html",
        "Injuries & 1st–4th string lineup deficiencies",
        "Tracking offensive and defensive starter absences, 2nd/3rd/4th-string replacements, and depth-chart discrepancies from official NFL sources.",
        body,
        wide=True,
    )


def render_landing_governance_sections(table, src_link) -> str:
    """Dedicated Suggestions-for-Review section + Pre-Decision Q&A & Lineup Deficiency highlights
    for the landing dashboard (index.html)."""
    g = load_governance_data()
    sug = g["suggestions"].head(6)
    dq = g["questions"].head(6)
    mm = g["wk10_matchups"]

    sug_rows = [
        [
            f'<strong>{_e(r.id)}</strong> · {_e(r.priority.split("·")[0].strip())}',
            _e(r.category),
            f'<strong>{_e(r.title)}</strong>',
            f'<strong>{_e(r.recommended_path)}</strong> (of Paths A / B / C)',
            _tier_pill(r.review_state),
            src_link(r.official_ref_url, r.official_ref_label),
        ]
        for r in sug.itertuples(index=False)
    ]

    dq_rows = [
        [
            f'<strong>{_e(r.id)}</strong>',
            _e(r.question),
            _e(r.info_we_lack),
            f'{_e(r.current_answer.split(".")[0])}.<br>{_tier_pill(r.blocker_severity)}',
            src_link(r.official_ref_url, r.official_ref_label),
        ]
        for r in dq.itertuples(index=False)
    ]

    mm_rows = [
        [
            f'<strong>{_e(r.matchup)}</strong><br><span class="muted">{_e(r.kickoff)}</span>',
            _e(r.net_lineup_flags),
            src_link(r.official_source, "NFL Week 10 injuries"),
        ]
        for r in mm.itertuples(index=False)
    ]

    return f"""
<section id="suggestions-for-review">
  <div class="section-head">
    <h2>Suggestions for review (choose best path before implementing changes)</h2>
    <a href="suggestions-review.html">Open full 12-suggestion review queue &amp; path selector →</a>
  </div>
  <p>Per governance rules, improvement proposals are staged here for human review and path selection (Path A Conservative · Path B Balanced · Path C Full) <strong>before</strong> modifying the frozen canonical model or validation gates.</p>
  {table(sug_rows,
         ["ID", "Category", "Proposed improvement", "Recommended path", "Review status", "Official reference"],
         caption="Top staged suggestions awaiting reviewer path selection (6 of 12 shown)")}
</section>

<section id="pre-decision-readiness">
  <div class="section-head">
    <h2>Pre-decision questions, missing information &amp; lineup alerts</h2>
    <a href="decision-readiness.html">All 14 questions &amp; 8 discovery protocols →</a>
  </div>
  {table(dq_rows,
         ["ID", "Critical question before any decision", "Missing information to discover", "Current answer & blocker", "Official reference"],
         caption="Core decision-readiness blockers separating known facts from missing evidence (6 of 14 shown)")}
  <div class="section-head">
    <h3>Week 10 (2026-11-12) offensive &amp; defensive starter / backup string alerts</h3>
    <a href="lineup-deficiencies.html">Full 1st–4th string offense &amp; defense tracker →</a>
  </div>
  {table(mm_rows,
         ["Week 10 matchup", "Verified offensive & defensive 2nd/3rd/4th-string deficiency summary", "Official source"],
         caption="Official Week 10 2026 injury and depth-chart synthesis across four audited games")}
</section>
"""


def render_flagged_2026_11_12_rows(src_link) -> list[list[str]]:
    """New irregularities discovered during the 2026-11-12 line-by-line official verification pass."""
    return [
        [
            "IR-2026-11-12-01",
            "High · open (flagged)",
            "Pinned snapshot `a270278f3ac4` (2026-11-01) predates 28 settled NFL regular-season games (13 in Week 8, 15 in Week 9) verified Final on NFL.com on 2026-11-12; those games still appear in `upcoming.csv` / `lines.html`. Reconciled in `post_pin_nfl_scores_2026_11_12.csv`; dual-pin separation staged as SUG-05.",
            src_link("https://www.nfl.com/scores/2026/REG9", "NFL.com 2026 Week 9 scores"),
        ],
        [
            "IR-2026-11-12-02",
            "Medium · open (flagged)",
            "Official `https://www.nfl.com/inactives/` page returned 'Please check back soon for NFL Inactive Reports for this Season' on 2026-11-12, so automated 90-minute active/inactive tracking must read club PR Game Day Administration releases rather than that URL.",
            src_link("https://www.nfl.com/inactives/", "NFL.com Inactives") + " · " + src_link("https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep", "NFL Operations 90m rule"),
        ],
        [
            "IR-2026-11-12-03",
            "High · open (flagged)",
            "Official NFL club depth charts carry explicit 'Unofficial' writer disclaimers (`patriots.com`, `detroitlions.com`, `chiefs.com`, `vikings.com`, `packers.com`) and lag real roster/injury state: Kirk Cousins (MIN trade acquisition on NFL.com news) is absent from `vikings.com/team/depth-chart`, Micah Parsons (Limited on `nfl.com/injuries/` for GB) is absent from `packers.com/team/depth-chart`, and Lucas Patrick (Out at C on `nfl.com/injuries/` for WAS) is absent from `commanders.com/team/depth-chart`.",
            src_link("https://www.nfl.com/injuries/", "NFL.com Week 10 injuries") + " · " + src_link("https://www.nfl.com/news/vikings-wont-commit-to-kirk-cousins-starting-packers", "NFL.com Vikings QB report"),
        ],
        [
            "IR-2026-11-12-04",
            "Medium · repaired",
            "14 HTML classes emitted by `pipeline/render_site.py` (`.skip-link`, `.hero`, `.eyebrow`, `.actions`, `.btn.primary`, `.hero-status`, `.status-dot`, `.section-head`, `.table-tools`, `.filter`, `.pill.unverified`, `.unverified`, `.blank`, `.card.good`) were missing from `assets/style.css`, leaving Skip-to-content visible in normal flow and `.blank` unverified cells visually empty. Repaired in CSS.",
            src_link("https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages", "GitHub Pages documentation"),
        ],
        [
            "IR-2026-11-12-05",
            "Low · repaired",
            "`tests/check_sources.py` checked 12 canonical pages and omitted `verification.html` (which `verify_site.py` and `check_links.py` checked). Synchronized all canonical root pages across all three checkers.",
            src_link("https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages", "GitHub Pages documentation"),
        ],
        [
            "IR-2026-11-12-06",
            "High · open (staged in SUG-01/SUG-08)",
            "Canonical `models.py` and `props_model.py` contain zero offensive or defensive injury / backup-string covariates. Staged for path selection in `suggestions-review.html` rather than mutating frozen historical benchmarks without review.",
            src_link("https://www.nfl.com/injuries/", "NFL.com Week 10 injuries"),
        ],
    ]


def render_audit_2026_11_12_section(table, src_link) -> str:
    g = load_governance_data()
    rv = g["repo_review"]
    rows = [
        [
            f'<strong>{_e(r.review_id)}</strong>',
            f'<code>{_e(r.scope_path)}</code>',
            _e(r.verification_performed),
            _e(r.status),
            _e(r.irregularity_flag),
            src_link(r.official_ref_url, "Official / primary source"),
        ]
        for r in rv.itertuples(index=False)
    ]
    return f"""
<h2>2026-11-12 Repository &amp; Freshness Audit (`arena/d6b3fd34-korea1`)</h2>
<p>Line-by-line review of all active modules, workflows, tests, and official NFL Week 8–10 pages conducted on 2026-11-12. Full 28-game Week 8–9 score reconciliation is published on <a href="decision-readiness.html#post-pin-reconciliation">Pre-decision Q&amp;A</a>, and 39 Week 10 offensive/defensive injury + depth-chart checks are published on <a href="lineup-deficiencies.html">Injuries &amp; Backup Strings</a>.</p>
{table(rows, ["ID", "Repository / source scope", "Line-by-line check performed", "Disposition", "Irregularity / note", "Source"],
       caption="2026-11-12 repository module and official-source audit log")}
"""
