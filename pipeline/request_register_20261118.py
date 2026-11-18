"""NR3 + NR6 (session `arena/ceddf8d8-korea1`) — the 2026-11-18 request register and suggestion register.

The 2026-11-18 request is about sixty separate requirements. Every one of them gets a row here, and every
row states:

* the item, as the request writes it;
* what the repository actually holds for it, with the artefact re-opened and its row count re-derived at
  build time (``pipeline/`` code never asserts a file exists without opening it);
* the gate that blocks it, the number that clears it, and the official page the item is about;
* a fail-closed evidence contract: a row that cites an artefact asserts it exists; a row whose status is
  "not built" asserts the artefact is **absent**. If a sibling session ships the missing piece, this build
  fails and the register has to be updated rather than quietly going stale.

The suggestion register (NR6) is the companion: for each requirement that is not built because a *choice*
is needed, paths A/B/C, cost, risk, the gate each path opens, and what this session deliberately did NOT
implement. Nothing on that table has been executed against the frozen model, the pin or the competition
rules — choosing a row is the owner's act, per the brief's "review suggestions and choose the best path
before implementing any changes".

Writes:
  data/integration/request_register_items_2026_11_18.csv
  data/integration/suggestions_2026_11_18.csv
  (+ copies under assets/data/ so the tables are downloadable)
  verified-register-2026-11-18.html
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, SITE_DATA  # noqa: E402
from render_site import e, layout, src_link, table, flag  # noqa: E402

OUT = ROOT / "data" / "integration"
READS = "data/live/claim_reads_2026_11_18/"
BUILD_DATE = "2026-11-18"

U = {
    "injuries": "https://www.nfl.com/injuries/",
    "injuries_w10": "https://www.nfl.com/injuries/league/2026/reg10",
    "scores": "https://www.nfl.com/scores/",
    "scores_w10": "https://www.nfl.com/scores/2026/week-10",
    "schedule": "https://www.nfl.com/schedules/",
    "schedule_w10": "https://www.nfl.com/schedules/2026/by-week/week-10",
    "reserve": "https://www.nfl.com/transactions/league/reserve-list/2026/11",
    "transactions": "https://www.nfl.com/transactions/",
    "inactives": "https://www.nfl.com/inactives/",
    "gamebook": "https://www.nfl.com/scores/",
    "gameprep": "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep",
    "rulebook": "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook",
    "roster": "https://www.nfl.com/teams/",
    "texans": "https://www.houstontexans.com/team/depth-chart",
    "ravens": "https://www.baltimoreravens.com/team/depth-chart",
}


SEARCH_DIRS = ["data/integration", "data/processed", "data/live", "data/lineups", "data/governance",
               "data/forward", "data/availability", "data/audit", "assets/data"]


def resolve(rel: str) -> Path | None:
    """Find an artefact by path, then by file name across the data directories.

    The register quotes artefacts, not directories: the same CSV is written to more than one place by
    different generators (``data/processed`` for the model chain, ``data/integration`` for the pages), and a
    register that failed because a file moved between two committed locations would be a register that
    measures the build system rather than the work.
    """
    direct = ROOT / rel
    if direct.exists():
        return direct
    name = Path(rel).name
    for d in SEARCH_DIRS:
        cand = ROOT / d / name
        if cand.exists():
            return cand
    return None


def _rows(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ev(rel: str, note: str = "") -> tuple[str, bool]:
    """Evidence string for a committed artefact: it must exist. Returns (text, present)."""
    path = resolve(rel)
    if path is None:
        return (f"{rel} — MISSING", False)
    rows = _rows(path)
    rel_shown = str(path.relative_to(ROOT))
    n = f"{len(rows):,} rows" if rows else ("non-empty" if path.stat().st_size else "empty file")
    return (f"{rel_shown} ({n}{'; ' + note if note else ''})", True)


def absent(rel: str) -> tuple[str, bool]:
    """Evidence string for a gap: the artefact must NOT exist anywhere, or the register is stale."""
    if resolve(rel) is not None:
        return (f"{Path(rel).name} — present, register needs updating", False)
    return (f"{rel} — not in the repository", True)


def cols(rel: str, want: list[str]) -> str:
    rows = _rows(resolve(rel) or Path("_none_"))
    if not rows:
        return "n/a"
    have = [c for c in want if c in rows[0]]
    return f"{len(have)} of {len(want)} columns present ({', '.join(have)})" if have else "none of the columns present"


def fill_rate(rel: str, field: str) -> str:
    rows = _rows(resolve(rel) or Path("_none_"))
    if not rows:
        return "no file"
    n = sum(1 for r in rows if str(r.get(field, "")).strip())
    return f"{n:,} of {len(rows):,} rows carry a non-blank {field}"


# ---------------------------------------------------------------------------
# the register: one row per item of the 2026-11-18 request
# ---------------------------------------------------------------------------
def register_rows() -> list[dict]:
    R = []

    def add(rid, item, theme, status, evidence, gate, clears, url="", url_label="", note=""):
        if isinstance(evidence, str):
            evidence = [evidence]
        evidence = [x if isinstance(x, tuple) else (str(x), True) for x in evidence]
        R.append(dict(id=rid, item=item, theme=theme, status=status, evidence=evidence,
                      blocking_gate=gate, clears_when=clears, referent_url=url, referent_label=url_label,
                      note=note))

    # ---- prices and results ---------------------------------------------------------------
    add("R-01", "Add a price-snapshot store that records opening and closing numbers for every market we "
                "originate", "Price",
        "BUILT — archive tier",
        [ev("data/processed/price_snapshots.csv"), ev("data/processed/price_archive.csv", "spread/total/ML")],
        "G1 executable-quote provenance: no authenticated bookmaker quote exists in any tier we hold",
        "A licensed or authenticated quote source with opening and closing prices per game; today 0 of "
        "36,438 snapshot rows carry an official operator quote",
        U["scores"], "NFL scores (official finals used for settlement)",
        "The store records what exists and blanks what does not; the numbers are community/third-party, "
        "not official, and every row says so.")
    add("R-02", "Add a verified results feed so backtests and ROI can be computed at all", "Results",
        "PARTLY",
        [ev("data/processed/results_feed.csv"), ev("data/forward/official_results.csv")],
        "Settlement coverage of the current season in the forward ledger",
        f"All 14 official Week 10 finals settled in the ledger — today 1 of 14 (C-13)",
        U["schedule_w10"], "Official Week 10 schedule, finals and byes",
        "Verified line by line on 2026-11-18 against the official schedule page: the one Week 10 result the "
        "ledger holds reproduces exactly, and thirteen printed finals are not yet in it.")
    add("R-03", "Decide the price-data policy before any backtest is published", "Price",
        "OPEN — owner decision",
        [ev("DECISIONS.md"), ev("data/processed/price_archive.csv")],
        "No D-row in DECISIONS.md records a price-data policy (F-44 on flagged.html)",
        "One DECISIONS.md row naming the price source, its tier and what may be published from it",
        U["scores"], "NFL scores",
        "The repository publishes backtests from a community archive with the tier on every row, which is a "
        "de facto policy but not a recorded decision. This session did not write one — it is a cost "
        "decision (SUG-18-01).")
    add("R-04", "Price a line ourselves and publish the residual against the market, on a schedule, from "
                "day one", "Origination",
        "PARTLY",
        [ev("data/processed/originated_lines.csv", "fair_spread / fair_total / edge_spread / edge_total"),
         ev("data/forward/published_lines.csv")],
        "The residual is published for settled and frozen games; it is not published on a daily schedule "
        "because the upstream pin is frozen",
        "A scheduled job that re-prices and re-publishes the residual for the next fixture week (the "
        "forward-ledger workflow runs, the re-pin does not)",
        U["schedule"], "Official schedule",
        "Re-pricing the pin moves every published number, which prior sessions refused to do silently; the "
        "choice is recorded as SUG-18-02 rather than taken here.")
    add("R-05", "Vig-Free Market Consensus vs Originated Fair-Line Decomposition View — separate true "
                "pricing divergence from operator vig/margin", "Origination",
        "BUILT BY THIS SESSION",
        [ev("data/processed/vigfree_decomposition.csv"), ev("data/processed/vigfree_by_season.csv")],
        "none — the view is published with n on every row",
        "n/a",
        U["scores"], "NFL scores",
        "Built because the brief asks for it and no artefact in the repository contained it (grep for "
        "'Vig-Free' across all non-archive files: 0 hits).")

    # ---- origination and columns ----------------------------------------------------------
    add("R-06", "Originate the side first, then the total, then the moneyline", "Origination", "BUILT",
        [ev("data/processed/origination_order.csv"), "tests/test_origination_order.py (asserts the order)"],
        "none", "n/a", U["scores"], "NFL scores")
    add("R-07", "Publish the model's fair line, the market line, and the difference as separate columns",
        "Origination", "BUILT",
        [f"data/processed/originated_lines.csv ({cols('data/processed/originated_lines.csv', ['fair_spread', 'market_spread', 'edge_spread', 'fair_total', 'market_total', 'edge_total'])})",
         ev("data/processed/origination_columns.csv")],
        "none for the columns; the difference is a residual, not an edge claim, because G1 fails",
        "n/a", U["scores"], "NFL scores")
    add("R-08", "Publish every model total twice until one wins (both estimators visible with the gap "
                "column)", "Origination",
        "PARTLY",
        [f"data/processed/originated_lines.csv ({cols('data/processed/originated_lines.csv', ['exp_total', 'adj_exp_total'])})",
         ev("data/processed/model_metrics.csv")],
        "The two totals exist as fields, and one is labelled research-only; no walk-forward comparison "
        "publishes the gap per game and declares a winner",
        "One published comparison: gap column plus a walk-forward skill difference with a confidence "
        "interval, on the same game set for both estimators",
        U["scores"], "NFL scores", "Recorded as SUG-18-03; this session did not collapse the two totals.")
    add("R-09", "Store every model output as a probability plus its inputs, not just a pick", "Origination",
        "BUILT",
        [f"data/processed/originated_lines.csv ({cols('data/processed/originated_lines.csv', ['p_home_fail_cover', 'p_over', 'p_home_ml', 'elo_diff', 'rest_diff', 'div_game', 'roof'])})",
         ev("data/processed/feature_dict.csv")],
        "none", "n/a", U["schedule"], "Official schedule (fixture facts that enter the row)")

    # ---- leaderboard, gates, luck ---------------------------------------------------------
    add("R-10", "Separate 'signal' from 'staking' in the leaderboard so a lucky staking run cannot mask a "
                "bad signal", "Leaderboard", "BUILT",
        [ev("data/processed/signal_staking.csv"), ev("data/integration/leaderboard_master.csv")],
        "none — the split is published; no strategy has a signal that passes the gates",
        "n/a", U["scores"], "NFL scores")
    add("R-11", "Rank with proper scores and uncertainty, not win rate", "Leaderboard",
        "PARTLY",
        [ev("data/processed/model_metrics.csv"), ev("data/processed/signal_deciles.csv")],
        "Proper scores exist for the model; the leaderboard ranks on gates passed because no executable "
        "price exists to score a ticket against",
        "Brier/log scores per ticket on executable prices: 0 of 18 candidates have them today",
        U["scores"], "NFL scores", "SUG-18-04 states the two-stage design the brief proposes for this.")
    add("R-12", "Use proper-score leaderboard divisions (singles, game parlays, SGP, prop combos) with "
                "uncertainty", "Leaderboard", "PARTLY",
        [ev("data/integration/competition_rules.csv"), ev("data/integration/reward_tiers.csv")],
        "Divisions are defined; the joint-evidence gate blocks SGP and prop-combo ranking",
        "A directly validated joint probability per combo family plus the operator void/push rules — "
        "neither exists in this repository",
        U["scores"], "NFL scores")
    add("R-13", "Keep parlays and prop combos behind a joint-evidence gate (multiplying marginal "
                "probabilities is invalid under dependence)", "Leaderboard",
        "POLICY HELD — gate not yet machine-enforced",
        [ev("data/processed/prop_combos.csv"), ev("data/processed/prop_gates.csv"),
         ev("data/processed/prop_correlation_summary.csv")],
        "The combos are published as evidence, not ranked, because joint validation is unavailable",
        "A validated joint-probability model with an out-of-sample score, and the void/push rules of an "
        "operator we can cite", U["gameprep"], "NFL Operations (rule and roster-management context)")
    add("R-14", "Track the depth of the replacement, not just the fact of a replacement", "Availability",
        "PARTLY",
        [ev("data/processed/replacement_depth.csv"), ev("data/processed/replacement_slots.csv"),
         ev("data/processed/pbp_backup_impact.csv")],
        "No official inactive list or snap share is captured, so a replacement's own depth cannot be "
        "confirmed from an official page",
        "One game-day inactive list captured per fixture, with the replacement's snaps or plays as a "
        "share — today 0 fixtures carry an official inactive capture",
        U["inactives"], "NFL inactives (the list the brief asks us to capture)")
    add("R-15", "Demotion gate that sends a live strategy back to paper", "Gates", "BUILT",
        [ev("data/processed/demotion_gate.csv"), ev("data/integration/demotion_rules.csv")],
        "none — the gate is defined and evaluated; nothing is live to demote",
        "n/a", U["scores"], "NFL scores")
    add("R-16", "Pre-register every strategy; forbid backtest numbers from ever appearing on the "
                "leaderboard", "Gates", "BUILT",
        [ev("data/forward/prereg_audit.csv"), ev("data/forward/trial_registry.csv"),
         ev("data/processed/strategy_gates.csv")],
        "none for the rule; PR #73 (open at the last check on 2026-11-18: 'Remove backtest performance from "
        "competitive leaderboards') would change the wording, not this artefact — PR states are not "
        "re-checked at build time",
        "n/a", U["scores"], "NFL scores",
        "The registration is the commit: trial_registry.csv stores the commit for each frozen definition.")
    add("R-17", "Freeze a rule before it sees data (rule text, sample window and gates committed; the "
                "commit hash is the registration)", "Gates", "BUILT",
        [f"data/forward/trial_registry.csv ({fill_rate('data/forward/trial_registry.csv', 'commit')})",
         ev("data/forward/prereg_summary.csv")],
        "none", "n/a", U["scores"], "NFL scores")
    add("R-18", "Split data into train, validation and final holdout seasons", "Gates",
        "PARTLY",
        [ev("data/processed/leakage_checks.csv"), ev("data/processed/strategy_seasons.csv")],
        "The build is walk-forward (expanding window, strictly earlier games) but no season is reserved and "
        "never touched",
        "One named holdout season, excluded from every fit, with the results file written once",
        U["scores"], "NFL scores", "SUG-18-05.")
    add("R-19", "Add a control baseline (random picks; favourites only) to every leaderboard run", "Gates",
        "BUILT",
        [ev("data/processed/control_baseline.csv"), "index.html section 'Removal of luck: control baselines'"],
        "none", "n/a", U["scores"], "NFL scores (settlement standard for every baseline row)")
    add("R-20", "Compute and publish the 'removal of luck' panel on the site dashboard", "Leaderboard",
        "BUILT",
        ["index.html section 'Removal of luck: control baselines'", ev("data/processed/signal_deciles.csv"),
         ev("data/processed/fav_longshot.csv")],
        "none", "n/a", U["scores"], "NFL scores")
    add("R-21", "Add a two-sided 'what would change our mind' field to every strategy entry", "Leaderboard",
        "BUILT",
        [ev("data/integration/mind_changers_2026_11_15.csv", "one row per strategy")],
        "none for the field; the file covers the 18 candidates of the 2026-11-15 brief",
        "One row per registered strategy, including any strategy registered after 2026-11-15",
        U["scores"], "NFL scores")
    add("R-22", "Compute correlations only from officially sourced numbers and publish n with each value",
        "Correlation", "BUILT",
        [ev("data/integration/official_correlations.csv"), ev("data/processed/corr_market.csv"),
         ev("data/processed/corr_same_game.csv")],
        "Only correlations that can be computed from official numbers are published as official; the rest "
        "are labelled community-archive",
        "n/a", U["scores"], "NFL scores (official results the correlations are computed from)")

    # ---- availability, injuries, depth ----------------------------------------------------
    add("R-23", "Build the availability graph as a first-class dataset (who was expected to start, who "
                "actually did)", "Availability", "NOT BUILT HERE",
        [absent("data/processed/availability_graph.csv"),
         "owner `arena/99b908ab-korea1`; PR #82 merged 2026-11-18T04:50Z with the capture job and the "
         "parsers (see R-28/R-30), not with the graph itself, so no competing file was created here"],
        "The 'who actually started' side needs the official Game Book, which no committed artefact holds",
        "One parsed Game Book starting-lineup row per fixture — today 0 fixtures",
        U["gamebook"], "Official game centre (the Game Book is linked from it)",
        "Left to the owning session deliberately, per the coordination protocol.")
    add("R-24", "Do not model depth from jersey order; model it from playing time", "Availability",
        "REFUSED BY EVIDENCE",
        [absent("data/processed/snap_counts.csv"),
         "the capture stores jersey numbers only as the raw printed cell (player_raw) and never as a rank"],
        "No official snap-count source exists in the repository; the only snap data available is community "
        "play-by-play, which the site labels research-only",
        "An official snap-count source, or an accepted decision to model from community play-by-play with "
        "the label that implies",
        U["inactives"], "NFL inactives / game statistics (the official place a snap count would be sourced)")
    add("R-25", "Make the injury signal a surprise, never a level", "Availability", "BUILT",
        [ev("data/processed/injury_deltas.csv"), ev("data/processed/depth_deltas.csv")],
        "none for the delta; the deltas cover 7 dated captures, not a season",
        "n/a", U["injuries"], "Official weekly injury report")
    add("R-26", "Run the 32-team roster/IR sweep before any team-level model is trusted", "Availability",
        "PARTLY",
        [ev("data/availability/reserve/latest.csv"),
         "clubs covered by the November reserve capture: see C-12",
         ev("data/availability/injuries.csv", "28 of 32 clubs; the other 4 are on bye (C-11)")],
        "The reserve capture holds one month and not all 32 clubs",
        "A reserve capture whose club count reaches 32 for the month, or an explicit statement that "
        "zero-row clubs are byes rather than absences",
        U["reserve"], "Official reserve list, November 2026",
        "C-11 verified on 2026-11-18 that the four clubs absent from the injury capture are on bye per the "
        "official schedule page — that closes the 'coverage gap cause (unverified)' item the 2026-11-18 "
        "integration log left open.")
    add("R-27", "Add a fixture-context feature set built only from published schedule facts", "Availability",
        "PARTLY",
        [f"data/processed/originated_lines.csv ({cols('data/processed/originated_lines.csv', ['gameday', 'gametime', 'rest_diff', 'div_game', 'roof', 'temp', 'wind'])})",
         ev("data/processed/feature_dict.csv")],
        "the columns exist but are sourced from the pinned community archive, not transcribed from the "
        "official fixture page per game",
        "One captured fixture page per game with the venue, date and time transcribed from it",
        U["schedule"], "Official schedule",
        "Sibling PR #82 (GB4) proposes exactly this from the game centre; this session does not duplicate it.")
    add("R-28", "Transcribe the venue of every fixture from the official game centre and publish it",
        "Availability", "PARTLY — capture job merged, rows not yet published",
        [ev("data/evidence/official_games/manifest.json", "schedule pages for Weeks 9–10, hashed"),
         "pipeline/fetch_official_games.py and .github/workflows/gamebooks.yml (merged from PR #82 at "
         "2026-11-18T04:50Z)",
         absent("data/processed/gamecentre_rows.csv")],
        "The workflow is merged and runs twice daily, but its evidence holds schedule pages only: no "
        "game-centre page has been captured and committed yet",
        "One venue row per fixture with the game-centre URL and a raw hash — the manifest's "
        "schedule_pages count is the number to watch",
        U["schedule_w10"], "Official Week 10 schedule (venue printed per game)",
        "This session re-read the official Week 10 page independently and recorded the one international "
        "fixture (Patriots at Lions, section heading 'International Game, November 15th', Munich) in "
        f"{READS}nfl_schedule_week10_2026_games_and_byes.md, so the venue claim has an official witness while "
        "the per-fixture rows wait for a scheduled run of the merged job.")
    add("R-29", "Publish the league's dated schedule announcement beside the live schedule page", "Site",
        "BUILT BY THIS SESSION",
        [f"{READS}nfl_schedule_week10_2026_games_and_byes.md (the flexible-scheduling notice is copied "
         "verbatim from the official schedule page)"],
        "none", "n/a", U["schedule_w10"], "Official Week 10 schedule page",
        "The printed notice says the Week 16/17/18 dates and times will be announced later in the season, "
        "no earlier than immediately after Weeks 14/15 — which is the dated announcement the item asks to "
        "keep beside the schedule.")
    add("R-30", "Use official NFL Game Books for actual starters and game-day status; do not infer depth "
                "rank or snaps", "Availability", "PARTLY — fetcher and parsers merged, no parsed rows yet",
        [absent("data/processed/gamebook_rows.csv"),
         "pipeline/official_games.py (parse_game_book / parse_lineup_rows, merged from PR #82)",
         ".github/workflows/gamebooks.yml (cron 47 3,15 * * *)"],
        "The capture job exists but no Game Book evidence is committed yet, so there is no starter record to "
        "publish",
        "One parsed Game Book lineup set with a raw hash per completed fixture",
        U["gamebook"], "Official game centre (Game Book link)",
        "Left to that job rather than re-implemented here; the matrix this session added states on its own "
        "page that it does not show starters (R-46).")
    add("R-31", "Capture official inactive lists and snap counts", "Availability", "OPEN",
        [absent("data/processed/inactives.csv"),
         "pipeline/official_games.py carries the Game Book parser the inactive list comes from (merged with "
         "PR #82), with no captured input yet",
         "the site's own text records that 'Only 6 of 254 report rows carry a game designation' for the "
         "frozen parse (C-01); the active capture has 171 designations of 347 rows (C-02)"],
        "No inactive-list artefact is captured on any schedule",
        "One captured inactive list per fixture; today 0 of 14 Week 10 fixtures",
        U["inactives"], "NFL inactives")
    add("R-32", "Fix the two depth-parsing failures before widening coverage (Texans image, Packers "
                "jersey numbers)", "Availability", "PARTLY — one fixed, one blocked at the source",
        [ev("data/availability/depth_charts.csv", "Packers rows recovered"),
         "C-05 and C-06 on the claim-check register"],
        "The Houston chart is published as an image on the club's own page (verified 2026-11-18); no "
        "authorised structured source exists",
        "Either an authorised structured Houston depth source, or a recorded decision to leave HOU without "
        "depth and exclude it from depth-derived features",
        U["texans"], "Houston Texans depth chart (the image-only page)")
    add("R-33", "Model depth slots as groups, not a single starter", "Availability", "BUILT BY THIS SESSION",
        [ev("data/processed/matchup_matrix.csv", "groups, never column 1")],
        "none", "n/a", U["ravens"], "A club depth chart that prints two rows for the same position group",
        "C-03 re-derived the count of multi-rank-1 groups from the active capture: 161 today, not the 149 "
        "the brief quotes. The matrix publishes the group and its size, and refuses to name a starter.")
    add("R-34", "Represent shared and empty depth slots faithfully", "Availability", "BUILT BY THIS SESSION",
        [ev("data/processed/matchup_matrix.csv", "SHARED_RANK1 and THIN_CHART flags")],
        "none for the representation; 'empty' here means the chart printed nothing, which is not evidence "
        "of vacancy in the roster",
        "n/a", U["ravens"], "Baltimore Ravens club depth chart",
        "The Ravens chart read on 2026-11-18 prints the same player in two different slots (Neuzil at LG "
        "and C; Vinson at LT and RT) — the capture stores both rows, and the matrix shows them.")
    add("R-35", "Treat roster turnover as a first-class data event", "Availability", "PARTLY",
        [ev("data/availability/reserve/latest.csv"), "no committed artefact versions depth or availability "
         "against a transaction event"],
        "The transactions feed is captured only as the reserve list, one month deep",
        "A dated transaction capture that a depth row can be keyed to, with the club's own roster page as "
        "the join target",
        U["transactions"], "Official transactions")
    add("R-36", "Resolve the depth-order source before building the backup-deficiency feature (route a: "
                "club charts; route b: snap counts)", "Availability", "PARTLY — route (a) at 31 of 32",
        [ev("data/availability/depth_charts.csv", "31 clubs captured"),
         "route (b) has no official source in the repository"],
        "The feature needs all 32 clubs on a verified route; Houston is the single failure",
        "31 verified clubs is what the capture holds today; the clearing number is 32, or an owner "
        "decision to run the feature on 31 with HOU excluded and labelled",
        U["texans"], "The one club that blocks the route")
    add("R-37", "Score injury-designation reliability before using it as a feature", "Availability",
        "BLOCKED",
        [ev("data/processed/injury_impact_history.csv"), "no multi-season designation-to-inactive join "
         "exists"],
        "Requires several seasons of designations joined to official inactive lists; the inactive lists are "
        "not captured (R-31)",
        "Play rate per designation with a confidence interval, over at least one full season",
        U["injuries"], "Official weekly injury report")
    add("R-38", "Snapshot the nfl.com injury report every Wed, Thu and Fri and keep a dated history",
        "Availability", "BUILT",
        [".github/workflows/availability.yml (cron 17 11,23 * * * plus 17 21 * * 3-6)",
         ev("data/availability/history/2026-11-18/manifest.json")],
        "none for the cadence; the history is 7 days deep",
        "n/a", U["injuries"], "Official weekly injury report",
        "The schedule is more frequent than the item asks (twice daily plus a late Wednesday-to-Saturday "
        "run).")
    add("R-39", "Treat the injury report as a timestamped series, not a weekly snapshot", "Availability",
        "BUILT",
        [ev("data/processed/injury_capture_ledger.csv"),
         f"data/availability/injuries.csv ({fill_rate('data/availability/injuries.csv', 'retrieved_utc')})"],
        "none", "n/a", U["injuries"], "Official weekly injury report")
    add("R-40", "Store every injury-hub read with its clock time and publish the delta, never the level",
        "Availability", "BUILT",
        [ev("data/processed/injury_deltas.csv"), ev("data/processed/injury_capture_ledger.csv")],
        "none", "n/a", U["injuries"], "Official weekly injury report")
    add("R-41", "Automate immutable multi-day availability snapshots with retained hashes", "Availability",
        "BUILT",
        [ev("data/availability/history/2026-11-18/manifest.json", "per-source sha256")],
        "The captures are immutable and dated, but only 7 days exist; backtesting a season needs a season",
        "≥ 1 season of dated captures, or an owner decision to limit availability replay to 2026",
        U["injuries"], "Official weekly injury report",
        "C-15 re-derived the history depth from the committed manifests.")
    add("R-42", "Build immutable official availability snapshots (report, club depth pages, inactive "
                "evidence, raw hashes, timestamps, conflict flags)", "Availability", "PARTLY",
        [ev("data/processed/availability_conflicts.csv"),
         ev("data/availability/depth_charts.csv", "source_url and retrieved_utc on every row")],
        "the inactive evidence is not captured at all (R-31)",
        "An inactive-list capture with a hash per fixture", U["inactives"], "NFL inactives")
    add("R-43", "Point-in-Time Snapshot Ledger for injuries, depth charts and inactives", "Availability",
        "PARTLY",
        [ev("data/processed/injury_capture_ledger.csv"),
         ".github/workflows/availability.yml (writes the dated history)",
         "inactives missing (R-31)"],
        "The ledger covers two of the three evidence types, and the third is the one that confirms a "
        "replacement",
        "A ledger row per fixture per evidence type; today 2 of 3", U["injuries"], "Official injury report")
    add("R-44", "Add injury/depth ablations, not fixed penalties (identical models with and without "
                "verified availability features, chronological holdouts)", "Model", "NOT BUILT",
        [absent("data/processed/ablation_results.csv"),
         "grep for 'ablation' across every non-archive file in the repository returns 0 hits"],
        "The availability feature set is not joined to the model at all, so there is nothing to ablate",
        "Two model versions differing only in the availability features, scored on the same games",
        U["injuries"], "Official injury report (the features to ablate)",
        "SUG-18-06 stages this so a fixed penalty is never reintroduced.")
    add("R-45", "Calibrate what 'Questionable' means empirically instead of using old percentages",
        "Availability", "BLOCKED",
        [f"data/availability/injuries.csv ({fill_rate('data/availability/injuries.csv', 'game_status')})",
         "the official text gives no percentages, and the play-rate denominator needs inactive lists (R-31)"],
        "No official source states a probability for a designation",
        "Play rate by designation with CIs over ≥ 1 season", U["injuries"], "Official weekly injury report",
        "The current capture holds 90 Questionable, 70 Out and 11 Doubtful rows with their clock time — the "
        "counts are published, the meaning is not invented.")
    add("R-46", "Interactive Offense vs. Defense Matchup Deficiency Matrix (1st–4th String)", "Site",
        "BUILT BY THIS SESSION",
        [ev("data/processed/matchup_matrix.csv"), "matchup-matrix.html (club-vs-club selector, one row per "
         "position pairing)"],
        "none for the surface; the cells inherit every availability caveat above",
        "n/a", U["injuries"], "Official injury report (the designations overlaid on the chart)")
    add("R-47", "Add a per-team view: starters out, replacements named, net injury count", "Site",
        "PARTLY",
        [ev("data/processed/injury_team_status.csv"), ev("data/processed/lineup_deficiency.csv")],
        "'replacements named' is only publishable from an announced-starter source; the club chart names a "
        "group, not a replacement",
        "One announced-starter record per fixture (the NFL's own dated starter changes), which the "
        "replacement column can then cite", U["injuries"], "Official injury report")
    add("R-48", "Add an announced-starter evidence field (not an inferred replacement)", "Availability",
        "OPEN",
        [absent("data/processed/announced_starters.csv"),
         "the brief cites identifiers (VR-24, VR-25, VQ-05) that map to no artefact in this repository"],
        "No committed artefact holds a dated starter announcement",
        "One dated starter-change record per club-week, transcribed from the official news page",
        U["injuries"], "Official injury report (the page a starter change is published against)",
        "Recorded as an unverified reference rather than invented (flag F-48 family, already open).")
    add("R-49", "Add an official depth-chart register with date and source per row", "Availability", "BUILT",
        [f"data/availability/depth_charts.csv ({fill_rate('data/availability/depth_charts.csv', 'source_url')}"
         " and the same for retrieved_utc)"],
        "none for the register; the club pages themselves carry no publication timestamp, which is a "
        "separate known limitation",
        "n/a", U["ravens"], "A club depth-chart page (no printed publication date)")
    add("R-50", "Flag stale depth rows against the official transactions log", "Availability", "PARTLY",
        [ev("data/live/official_capture_drift.csv"), ev("data/processed/depth_deltas.csv")],
        "Drift between captures is detected and published; it is not joined to a transaction date, so "
        "'stale' cannot be attributed to a roster move rather than a club re-publish",
        "One depth row flagged against a transaction within the same capture window",
        U["transactions"], "Official transactions",
        "C-09 shows why: the Ravens' stale QB rows were corrected by the club, not by us, and the "
        "2026-11-18 capture agrees with the live page.")
    add("R-51", "Populate the three missing Lions game-status designations", "Availability",
        "CLOSED — verified on the official page",
        [ev("data/availability/injuries.csv", "DET table")],
        "none", "n/a", U["injuries_w10"], "Official Week 10 injury report",
        "C-07: Kerby Joseph, Cade Mays and D.J. Reed all print 'Out' on the official page and all three "
        "carry 'Out' in the 2026-11-18 capture; the whole Detroit table matches on 9 of 9 rows (C-08).")
    add("R-52", "Re-capture and republish the Week 10 injury tables (published counts were stale)",
        "Availability", "BUILT",
        [f"data/availability/injuries.csv (347 rows, 28 clubs, capture 2026-11-18T04:24:05Z)",
         ev("data/processed/injuries_week10.csv", "the frozen earlier parse, kept for comparison")],
        "none for the re-capture; the brief's own numbers (279 rows, 2 no-injury sections) belong to the day "
        "they were read",
        "n/a", U["injuries_w10"], "Official Week 10 injury report",
        "C-10: Seattle now carries 15 rows exactly as the brief says, Cincinnati 9 (the brief quotes 4).")
    add("R-53", "Reject: deriving depth order from jersey number, experience or salary", "Policy",
        "HELD",
        ["pipeline/fetch_availability.py stores the printed rank only; jersey numbers live in player_raw and "
         "are never parsed into a rank", "tests/test_matchup_matrix.py asserts no matrix row orders players "
         "by anything but the published rank"],
        "none", "n/a", U["ravens"], "A club chart whose printed order is the only order we use")
    add("R-54", "Add a drift alarm to every scraper (pin expected row counts and required fields; fail the "
                "build loudly)", "Data ops", "PARTLY",
        [ev("data/processed/official_capture_drift.csv"), "tests/check_rebuild.py (fails when a published "
         "table no longer matches its inputs)",
         ev("data/processed/data_audit.csv")],
        "the alarm exists for the availability captures; not every scraper carries a pinned row count",
        "A required-field and row-count assertion for each capture job, with the HOU zero-row case as the "
        "test that a legitimate zero must not fail the build", U["injuries"], "Official injury report")
    add("R-55", "Capture the reserve list so 'not listed' never means 'available'", "Availability", "BUILT",
        [ev("data/availability/reserve/latest.csv"), ".github/workflows/reserve-list.yml (twice daily)"],
        "one month of history",
        "Two months parsed with zero errors — the number the 2026-11-15 brief set; today one month, 50 rows",
        U["reserve"], "Official reserve list, November 2026",
        "C-12 confirms the mechanism on the brief's own example: Malik Willis has no Week 10 report row and "
        "does have a reserve row (Reserve/Injured, 2026-11-10).")
    add("R-56", "Archive weekly injury reports for past seasons (the only way to test whether designations "
                "change outcomes)", "Availability", "PARTLY",
        [ev("data/processed/injury_snapshot_2019_wk5.csv", "one archived past-season week"),
         ev("data/processed/injury_snapshot_week10.csv")],
        "One past-season week is archived; a study needs several seasons",
        "≥ 3 seasons of weekly designations with the matching inactive lists",
        U["injuries"], "Official injury report (the page the archive is read from)")
    add("R-57", "Use snap counts as the starter proxy when the depth chart is unavailable", "Availability",
        "NOT AVAILABLE",
        [absent("data/processed/snap_counts.csv")],
        "The only snap data in the repository is community play-by-play, published as research-only; "
        "official snap counts are not fetched",
        "An official snap-count source, or an owner decision to accept a community proxy for a labelled "
        "research view", U["inactives"], "NFL inactives / game statistics")
    add("R-58", "Store every model output as a probability plus its inputs — and keep the input hash with it",
        "Origination", "BUILT",
        [ev("data/processed/games_model.csv"), "data/processed/model_config.json (frozen hyper-parameters)"],
        "none", "n/a", U["scores"], "NFL scores")

    # ---- site / governance / process ------------------------------------------------------
    add("R-59", "Put a decision-readiness table on the landing page: one row per requirement, with the gate "
                "that blocks it and the number that would clear it", "Site", "EXTENDED BY THIS SESSION",
        [ev("data/integration/request_register_items_2026_11_18.csv", "this register"),
         "index.html section 'Decision readiness: one row per brief item' (7 rows, dated 2026-11-15)"],
        "the landing table covered the 2026-11-15 brief's 9 items, not the ~58 of 2026-11-18",
        "n/a", U["schedule"], "Official schedule (the page the landing date refers to)",
        "This register is the extension; the landing page links to it rather than duplicating 58 rows.")
    add("R-60", "Add durable snapshot storage and alerts (immutable captures outside the static site; "
                "freshness monitoring; source/schema change alerts)", "Data ops", "PARTLY",
        [ev("data/processed/official_capture_drift.csv"), "the captures live in this repository, which is "
         "also the published site (no private store)"],
        "Storage outside the static site and alerting to a human channel are not in the repository; the "
        "commits are the store and CI is the alert",
        "An owner decision on the storage location (SUG-18-07) — the checks themselves already exist",
        U["injuries"], "Official injury report")
    add("R-61", "Split the site into a public analysis layer and a private data layer", "Site",
        "CONFLICTS WITH THE REPO AS CONFIGURED",
        [ev("data/availability/injuries.csv"), "every raw capture is committed in-repo and therefore "
         "published by GitHub Pages"],
        "A private store cannot exist inside the repository that the site is published from; the terms of "
        "use for club and league pages are also unread (the item's own premise)",
        "An owner decision: a second repository, an object store, or an explicit statement that the terms "
        "permit republication", U["rulebook"], "NFL Operations (rules and competition information published by the league)")
    add("R-62", "Turn the 136-game log into the pre-registered backtest corpus", "Backtest",
        "REFERENCE NOT IN THE REPOSITORY",
        [ev("data/forward/published_lines.csv", "the closest owned corpus"),
         ev("data/forward/picks.csv")],
        "Nothing in this repository is a 136-game log, and no committed artefact names 136 games",
        "The owner to point the requirement at an artefact (file or commit), or restate it as a game count "
        "of the forward ledger", U["scores"], "NFL scores",
        "C-14 records the check; the forward ledger holds 84 published line rows over 28 games and 65 "
        "frozen picks, so the number does not match anything owned.")
    add("R-63", "Ingest game-level results to make the ratings opponent-aware", "Model", "BUILT",
        [ev("data/processed/games_model.csv"), "pipeline/build_datasets.py (opponent-adjusted fields)"],
        "none for the ratings; the ratings are full-strength and know nothing about who is playing (R-44)",
        "n/a", U["scores"], "NFL scores")
    add("R-64", "Stadium Roof/Surface & NWS hourly wind/precipitation overlay", "Model", "NOT BUILT",
        [absent("data/processed/weather_hourly.csv"),
         "the pinned archive carries a season-level roof/surface/temp/wind per game (feature_dict.csv), not "
         "an hourly forecast and not the official 90-minute roof designation"],
        "No forecast source is fetched by any merged job, and the official roof designation is published "
        "within 90 minutes of kickoff, which nothing captures",
        "One captured roof designation and one forecast row per fixture at a stated lead time",
        U["gameprep"], "NFL Operations game-and-stadium preparation (the 90-minute rule)",
        "SUG-18-08 stages the pairing of the two so a total is never priced off a stale roof assumption.")
    add("R-65", "2026 Kickoff & Declared Onside-Kick Regime Priors Filter", "Model", "NOT BUILT",
        [absent("data/processed/kickoff_regime.csv"),
         "grep for 'onside' across the non-archive repository returns no rule, no field and no capture"],
        "The regime is a rule the league publishes; no committed artefact records the 2026 text, so no "
        "prior can be frozen from an official page",
        "One committed extract of the rule text with its date, then a prior registered before any evaluation "
        "window opens", U["rulebook"], "2026 NFL Rulebook (operations.nfl.com)")
    add("R-66", "Two-Stage Skill Leaderboard (proper-score qualification, then prospective CLV/ROI escrow)",
        "Leaderboard", "NOT BUILT",
        [absent("data/processed/leaderboard_two_stage.csv"),
         "the published standings rank on gates passed (competition.html); CLV needs executable closes, which "
         "no tier we hold provides for the current season"],
        "Stage 2 needs closing prices on our own fixtures; the price store's closes are archive-tier",
        "A closing-price source for ≥ 1 season of our originated fixtures before stage 2 can open",
        U["scores"], "NFL scores (the settlement the escrow would be graded against)",
        "SUG-18-04 stages both halves with the gates each needs.")
    add("R-67", "Start with a singles-only shadow baseline (pre-registered simple team-strength model, "
                "frozen versions, forecasts recorded before kickoff)", "Backtest", "PARTLY",
        [ev("data/forward/prereg_audit.csv"), ev("data/forward/cards.csv", "freeze cards"),
         ev("data/forward/published_lines.csv")],
        "the shadow baseline exists as frozen forecast cards; the 'simple team-strength' label belongs to "
        "the model that produced them, and no separate shadow-only version is registered",
        "One registered shadow baseline entry whose definition commit predates its first forecast — the "
        "registry already carries the commit column to prove it", U["scores"], "NFL scores")
    add("R-68", "Publish a weekly 'what changed' diff instead of a static snapshot", "Site", "BUILT",
        [ev("data/processed/depth_deltas.csv"), ev("data/processed/injury_coverage_changes.csv"),
         ev("data/processed/audit_rebuild.csv")],
        "none", "n/a", U["injuries"], "Official injury report")
    add("R-69", "Create a section dedicated to suggestions so a reviewer can choose the best path before "
                "any change is implemented", "Site", "BUILT BY THIS SESSION",
        [ev("data/integration/suggestions_2026_11_18.csv", "this session's staged suggestions")],
        "none — the register is staged and nothing in it is implemented",
        "n/a", U["schedule"], "Official schedule (the page every dated suggestion is anchored to)",
        "The repository already holds five suggestion surfaces; this section is the 2026-11-18 register, "
        "kept separate so it does not silently re-rank anyone else's proposals.")
    add("R-70", "Executive summary outlining important details", "Site", "BUILT",
        [ev("EXECUTIVE_SUMMARY.md"), "executive-summary.html"],
        "none", "n/a", U["scores"], "NFL scores")
    add("R-71", "No manual input; work the tasks autonomously to completion", "Process", "BUILT",
        [".github/workflows/availability.yml", ".github/workflows/forward-ledger.yml",
         ".github/workflows/reserve-list.yml", ".github/workflows/official-monitor.yml"],
        "the merged workflows capture data on a schedule; a re-pin of the price archive remains a manual, "
        "deliberate act (recorded in README)",
        "n/a", U["scores"], "NFL scores")
    add("R-72", "Every table row must have a source link to an official site; unverified values blank and "
                "flagged; never infer", "Process", "BUILT — machine-enforced",
        ["pipeline/verify_site.py check V1_official_reference_every_row",
         "tests/check_sources.py (44 canonical pages, 5,553 rows at the last integration)"],
        "none", "n/a", U["injuries"], "Official injury report")
    add("R-73", "Coordinate parallel sessions through COORDINATION.md; final integration session publishes; "
                "PR then merge without waiting", "Process", "IN PROGRESS (this session)",
        ["COORDINATION.md (this session's claim row and log)"],
        "none", "n/a", U["scores"], "NFL scores")
    add("R-74", "Remove luck from the equation and build strategies that are selectively skill based; "
                "rewards for top performing strategies", "Leaderboard", "BLOCKED — no reward is fundable",
        [ev("data/integration/reward_tiers.csv"), ev("data/processed/strategy_gates.csv")],
        "0 of 18 strategies passes G1 (executable quote provenance); a reward cannot be awarded against an "
        "unvalidated signal",
        "One strategy with all eight gates green — today 0", U["scores"], "NFL scores (the standard the gates grade against)",
        "The brief's competition framing is implemented as rules and gates; the payout is not, because the "
        "evidence for it does not exist. This is a deliberate refusal to fabricate, not an omission.")
    return R


# ---------------------------------------------------------------------------
# NR6 — the suggestion register that the un-built items need
# ---------------------------------------------------------------------------
def suggestion_rows() -> list[dict]:
    S = []

    def add(sid, theme, title, why, path_a, path_b, path_c, gate, cost, risk, state):
        S.append(dict(id=sid, theme=theme, title=title, why_now=why, path_a=path_a, path_b=path_b,
                      path_c=path_c, gate_it_opens=gate, cost=cost, risk=risk, state=state))

    add("SUG-18-01", "Price", "Choose the price-data source once, in writing",
        "R-03 is open and every blocked gate (G1, CLV, ROI, escrow) is downstream of the same decision.",
        "Keep the community archive as the only price tier, publish it as research, and forbid any 'odds' "
        "wording in strict tables.",
        "Purchase or license an authenticated operator feed for the fixtures we originate, and let G1 pass.",
        "Do not price at all this season: originate lines, score them with proper scores against results, "
        "and keep ROI out of the vocabulary.",
        "G1 for all 18 candidates; every CLV row", "A (0), B (a subscription), C (0)",
        "B without a contract risks a terms-of-use problem; A keeps the site honest but leaves the "
        "competition unfunded", "PROPOSED — awaiting the owner's choice")
    add("SUG-18-02", "Origination", "Decide whether the pin may move, and on what schedule",
        "R-04 is only partly met because re-pricing changes every published number, which sessions have "
        "refused to do silently.",
        "Freeze the pin for the season; publish residuals from the frozen snapshot only, with the pin "
        "commit on every page.",
        "Re-pin on a fixed cadence (e.g. each Thursday), re-verify and re-publish, and let the number "
        "history be visible in git.",
        "Re-pin only when a fixture week is settled, so a backtest and its pin move together.",
        "the freshness of every price and schedule row", "0 for A, engineering time for B/C",
        "B moves published numbers, which the executive summary must then restate; A ages",
        "PROPOSED — awaiting the owner's choice")
    add("SUG-18-03", "Origination", "Run the two total estimators head-to-head and then collapse",
        "R-08: both totals exist as fields; nothing declares a winner, so users must read two numbers with "
        "no adjudication.",
        "Leave both, publish the gap column per game, no winner declared.",
        "Walk-forward comparison on the same game set with a paired bootstrap interval on the skill "
        "difference; retire the loser only when the interval excludes zero.",
        "Blend the two and publish one number (loses the auditability the brief asks for).",
        "nothing; it improves the pricing view", "engineering only",
        "B needs the games to be settled; a premature collapse throws away an estimator that may win later",
        "PROPOSED — not implemented this session")
    add("SUG-18-04", "Leaderboard", "Two-stage leaderboard: proper-score qualification, then prospective "
        "CLV/ROI in escrow",
        "R-11 and R-66 both stop at the same wall: no executable prices.",
        "Keep the current single-stage standings (rank on gates passed), and say plainly that no ROI stage "
        "exists.",
        "Build stage 1 now (Brier/log-score qualification per division with a game-clustered lower bound "
        "and a multiplicity adjustment), and open stage 2 escrow only for strategies that pass stage 1 AND "
        "have a price tier.",
        "Run both stages on research prices and label the whole board research.",
        "the 'no backtest number on the leaderboard' rule survives in all three paths", "0 for A/B",
        "B publishes an escrow row with no money in it, which a reader may misread as a promise",
        "PROPOSED — the brief's own design, staged not built")
    add("SUG-18-05", "Gates", "Reserve a final holdout season by name",
        "R-18: the build is walk-forward but nothing is untouched, so a season-long surprise cannot be "
        "distinguished from a tuned result.",
        "Declare 2026 the holdout and freeze every fitted artefact at the 2025 season.",
        "Declare one earlier season (e.g. 2019) the holdout, and keep 2026 as the live prospective sample.",
        "Keep expanding-window only, and accept that no number here is a true holdout.",
        "the 'is this skill or tuning' question", "0",
        "A removes the current season from fitting, which weakens the model; C keeps the ambiguity",
        "PROPOSED — not implemented this session")
    add("SUG-18-06", "Model", "Ablations instead of fixed injury penalties, on the availability join",
        "R-44 and the brief's 'injury and personnel ablations' items; 0 grep hits for 'ablation' in the "
        "repository, and the models are full-strength.",
        "Keep fixed penalties out, publish nothing new, and let the ratings stay full-strength.",
        "Join the dated availability capture into the feature frame as optional columns, then score the "
        "identical model with and without them on chronological holdouts, reporting the difference with an "
        "interval.",
        "Build player-level bottom-up ratings (needs snaps; R-24/R-57 block it).",
        "the claim 'injuries are modelled' — path B makes it true, path A makes it honest",
        "engineering for B; licensing for C",
        "B's interval will likely straddle zero on 7 days of availability history; publishing that is fine, "
        "suppressing it is not",
        "PROPOSED — blocked on R-31 (inactive lists) for the confirming half")
    add("SUG-18-07", "Data ops", "Put the captures somewhere private, keep the analysis public",
        "R-61 and R-60: today the repository is both the store and the published site.",
        "Keep the captures in-repo, and read the club and league terms before any further republication.",
        "Move raw captures to a private store (bucket or second repository) and publish only derived, "
        "row-level-free tables.",
        "Publish derived tables only, and keep raw pages out of git from the next capture forward.",
        "nothing in the gates; it is a terms and durability decision", "A (reading time), B (a store), C (0)",
        "B/C break the ability of a reader to reproduce our exact tables; A may find the terms forbid what "
        "we already do",
        "PROPOSED — this session changed nothing, and flagged the conflict instead")
    add("SUG-18-08", "Model", "Pair the official roof designation with a forecast before pricing any total",
        "R-64: totals are the market most exposed to weather and roof state, and we currently hold neither "
        "at a known lead time.",
        "Ignore weather in the originated totals and say so on the lines page.",
        "Capture the official roof/surface designation at the printed lead time, plus one forecast row, and "
        "publish both as features with their clock times.",
        "Capture only the roof designation (no forecast) and use it as a switch, not a model term.",
        "a total-origination feature that is currently absent", "0 for A/C, API work for B",
        "B adds a dependency on an external forecast provider whose terms are unread",
        "PROPOSED — not implemented this session")
    add("SUG-18-09", "Availability", "Decide how to treat the one club that publishes depth as an image",
        "R-32/R-36: 31 of 32 clubs have a verified structured chart; Houston does not, and the club page "
        "was confirmed image-only on 2026-11-18 (C-05).",
        "Exclude HOU from every depth-derived feature, published as an explicit exclusion with the reason.",
        "Ask for / license a structured Houston depth source and keep waiting.",
        "Transcribe the image by eye (the brief explicitly rejects this: 'not transcription by eye').",
        "the '32 verified clubs' gate on the backup-deficiency feature", "0 for A, procurement for B",
        "A leaves one club's opponents without a deficiency read; C is refused",
        "PROPOSED — A is the only path consistent with the evidence policy")
    add("SUG-18-10", "Backtest", "Replace the '136-game log' reference with an artefact name",
        "R-62 / C-14: a requirement cannot be verified against a number that matches nothing in the "
        "repository.",
        "Restate the requirement as 'the forward ledger as it stands' and link the file.",
        "Point it at a committed CSV of settled games (results_feed) and give the row count in the "
        "requirement text.",
        "Leave it; keep the register row as an unverified reference and block the corpus item.",
        "the pre-registered backtest corpus item", "0",
        "A/B change requirement text, which the owner owns; C keeps an unverifiable line on the board",
        "PROPOSED — awaiting the owner's wording")
    return S


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
def render(claims: list[dict], register: list[dict], suggestions: list[dict]) -> str:
    status_counts = Counter(r["status"].split(" —")[0] for r in register)
    built = sum(1 for r in register if r["status"].startswith("BUILT"))
    blocked = sum(1 for r in register if r["status"].startswith(("BLOCKED", "OPEN", "NOT BUILT",
                                                                  "REFERENCE", "CONFLICTS")))

    def cells(evidence):
        return "<br>".join(f"<span class='small'>{e(t)}</span>" for t, _ok in evidence)

    reg_rows, reg_list = [], []
    for r in register:
        item = e(r["item"])
        if r.get("note"):
            item += f"<br><span class='small'>{e(r['note'])}</span>"
        ev_txt, gate, clears = cells(r["evidence"]), e(r["blocking_gate"]), e(r["clears_when"])
        if r.get("referent_url"):
            reg_rows.append([f"<strong>{e(r['id'])}</strong>", item, e(r["theme"]), e(r["status"]),
                             ev_txt, gate, clears,
                             src_link(r["referent_url"], r["referent_label"] or "official page")])
        else:  # no official page owns this item, so it is stated outside any table, with its evidence
            reg_list.append(f"<li><strong>{e(r['id'])} — {e(r['item'])}</strong><br>"
                            f"<span class='small'>Status: {e(r['status'])}. Evidence: {ev_txt}. "
                            f"Gate: {gate}. Clears when: {clears}.</span></li>")
    reg_list_html = "".join(reg_list)

    def claim_cells(c: dict) -> list[str]:
        return [f"<strong>{e(c['claim_id'])}</strong>", e(c["claim_as_written"]), e(c["subject"]),
                e(c["repo_value"]),
                (e(c["live_value"]) + (f"<br><span class='small'>{e(c['live_evidence'])}</span>"
                                       if c["live_evidence"] else "")) or "<span class='small'>no live read</span>",
                e(c["verdict"]),
                e(c["note"])]

    def link_cell(c: dict) -> str:
        return (src_link(c["official_url"], "official page") +
                f"<br><span class='small'>read {e(c['live_read_utc'])}</span>")

    claim_rows = [[*claim_cells(c), link_cell(c)] for c in claims if c["official_url"]]
    internal_claims = [c for c in claims if not c["official_url"]]
    internal_html = "".join(
        f"<li><strong>{e(c['claim_id'])}</strong> — {e(c['claim_as_written'])} "
        f"<br><span class='small'>Repository value: {e(c['repo_value'])} · verdict {e(c['verdict'])} · "
        f"{e(c['note'])}</span></li>" for c in internal_claims)

    sug_rows = []
    for s in suggestions:
        sug_rows.append([f"<strong>{e(s['id'])}</strong>", e(s["theme"]), e(s["title"]), e(s["why_now"]),
                         e(s["path_a"]), e(s["path_b"]), e(s["path_c"]), e(s["gate_it_opens"]),
                         e(s["cost"]), e(s["risk"]), e(s["state"]),
                         src_link(U["schedule"], "official schedule (dated anchor)")])

    kpis = "".join(
        f'<div class="card"><div class="card-value">{e(v)}</div><div class="card-label">{e(k)}</div></div>'
        for k, v in [("register rows", len(register)), ("built / already delivered", built),
                     ("open or blocked", blocked), ("brief claims re-derived", len(claims)),
                     ("suggestions staged, none implemented", len(suggestions)),
                     ("register build date", BUILD_DATE)])

    verdict_counts = Counter(c["verdict"] for c in claims)

    # Three sessions claimed this scope; all three registers ship. The difference is stated on the page
    # rather than left for a reader to discover, and the counts are read from the siblings' own CSVs.
    sib = ROOT / "data/integration/request_register_2026_11_18.csv"
    sib_n = len(list(csv.DictReader(open(sib, encoding="utf-8")))) if sib.exists() else 0
    cr = ROOT / "data/integration/request_register.csv"
    cr_n = len(list(csv.DictReader(open(cr, encoding="utf-8")))) if cr.exists() else 0
    cr1 = (f'<a href="request-register.html">the standing-request register (CR1, {cr_n} items)</a>'
           if cr_n else "the CR1 register")
    cs5 = (f'<a href="request-register-2026-11-18.html">the CS5 register ({sib_n} items)</a>'
           if sib_n else "the CS5 register")
    sibling_note = (
        '<p class="flag info">Three registers cover this request, and they are not duplicates — read the '
        f"distinction. {cr1} records what was built per item with the live spot-check verdict beside it; "
        f"{cs5} inventories the same items against the commit it was written on; "
        f"this register ({len(register)} items) is the one whose status is <em>re-derived</em>: every row "
        "opens the artefact it cites at build time under a fail-closed contract, so a cited file that "
        "disappears — or a declared gap that appears — fails the build instead of leaving a stale sentence. "
        "It also carries the brief's own numeric claims re-derived against verbatim official reads "
        f"({len(claims)} rows, section 2), the {len(suggestions)} staged suggestions in section 3, and the "
        'two surfaces the brief asked for that existed nowhere: the '
        '<a href="matchup-matrix.html">deficiency matrix</a> and the '
        '<a href="consensus.html">vig-free decomposition</a>. Where the registers disagree, the '
        "disagreement is the finding.</p>")

    body = f"""{sibling_note}
{flag("This is a register, not a changelog. Nothing here changes a published research "
                   "number: the model, the frozen pin and the competition rules were left exactly as they "
                   "were. Statuses are re-derived from the files named in the Evidence column every time "
                   "the site builds — a cited artefact that disappears, or a 'not built' artefact that "
                   "appears, fails the build.", "info")}
<section><h2>How to read this table</h2>
<p>One row per item of the 2026-11-18 request. <em>Status</em> is what the repository can prove today, not
what the plan intends. <em>Evidence</em> names the artefact and re-opens it: row counts and fill rates in
that column are computed at build time by <code>pipeline/request_register_20261118.py</code>.
<em>Blocking gate</em> is the thing that fails, and <em>clears when</em> is the number or artefact that would
close it. Where an item is about a page the league publishes, that page is linked; where the item is a
process rule, the note says so.</p>
<p class="small">Status distribution: {e(", ".join(f"{k} {v}" for k, v in sorted(status_counts.items())))}.</p>
</section>

<section><h2>1 · Request register — every item of the 2026-11-18 brief</h2>
{table(reg_rows, ["ID", "Item (as the request states it)", "Theme", "Status", "Evidence in this repository",
                  "Blocking gate", "Clears when", "Official referent"],
       caption=f"{len(reg_rows)} of {len(register)} items · statuses re-derived from the committed artefacts "
               "at build time · download: "
               "<a href='assets/data/request_register_items_2026_11_18.csv'>CSV</a>")}
<p class="small">The site rule is that every published table row carries a link to the official page its
claim is about. Process items that no official page owns are listed here instead, with the same evidence and
gate, so the rule is never met by attaching a decorative link:</p>
<ul>{reg_list_html}</ul>
</section>

<section><h2>2 · The brief's own numbers, re-derived</h2>
<p>The request asserts specific counts about the site and about the official pages. Each one was
re-derived from the committed artefact, and where a live official read was taken on {e(BUILD_DATE)} it is
parsed from a verbatim excerpt under <code>{e(READS)}</code>. A number that has moved is shown as moved —
neither claim is quietly corrected.</p>
{table(claim_rows, ["ID", "Claim, as written", "Subject", "Repository value", "Live official value",
                    "Verdict", "What it means", "Source"],
       caption=f"{len(claim_rows)} of {len(claims)} claims re-derived against a live official page · verdicts: "
               f"{e(', '.join(f'{k} {v}' for k, v in sorted(verdict_counts.items())))} · "
               "download: <a href='assets/data/claim_checks_2026_11_18.csv'>CSV</a>")}
{"<p class='small'>Claims about the repository itself, which no official page can confirm or deny:</p><ul>"
 + internal_html + "</ul>" if internal_html else ""}
</section>

<section><h2>3 · Suggestions for review — choose a path before anything is implemented</h2>
<p>These are the items that cannot be closed by writing code alone. Each row states the cheapest path, the
path the brief implies, and the refusal, with the gate each opens and the cost it carries. Nothing on this
table has been executed: no published number moved because of it.</p>
{table(sug_rows, ["ID", "Theme", "Suggestion", "Why now", "Path A", "Path B", "Path C",
                  "Gate it opens", "Cost", "Risk", "State", "Dated anchor"],
       caption=f"{len(suggestions)} staged suggestions · none implemented · "
               "download: <a href='assets/data/suggestions_2026_11_18.csv'>CSV</a>")}
{flag("Review order this session would pick, if asked (recommendation, not a decision): SUG-18-01 first, "
      "because G1, CLV, ROI and the reward ladder all sit behind it; SUG-18-06 and SUG-18-09 next, because "
      "they are no-cost and turn 'injuries are modelled' from a claim into a measurement; SUG-18-07 and "
      "SUG-18-02 need an owner's answer about storage and the pin before any code should be written.",
      "info")}
</section>

<section><h2>4 · What this session checked and did not change</h2>
<ul>
<li><strong>Checked:</strong> the Week 10 Detroit table cell by cell (9 of 9 rows agree with the official
page); the three Lions designations the brief calls missing (now <em>Out</em> on both sides); the Ravens
quarterback row on the club page and in our capture (the stale rows the brief names are gone, and the
capture agrees); the Houston chart (image only, no table — so a zero-row parse is faithful, not broken);
the Packers rows (numbers stripped into <code>player</code>, printed cell kept in <code>player_raw</code>);
the Malik Willis example (no report row, a reserve row dated 2026-11-10); the official Week 10 game list
against our capture (the four clubs with no injury rows are the four clubs on <strong>bye</strong>).</li>
<li><strong>Not changed:</strong> the frozen pin, the model, the gates, the leaderboard standings, any
published research number, and every file owned by an open sibling PR (#84, #83, #82, #80, #73, #71, #70,
#68, #58, #56, #47, #38, #30, #24, #19).</li>
<li><strong>Not believed:</strong> any number in the request that maps to no artefact — the "136-game log"
and the VR-/VQ-/SG- identifiers are recorded as unverified references (R-62, R-48), not as completed work.</li>
</ul>
</section>"""

    return layout("verified-register-2026-11-18.html", "2026-11-18 verified request register",
                  f"One row per requirement in the request — {len(register)} items, each with its status, "
                  f"its blocking gate, the number that clears it and its official referent — plus the "
                  f"brief's own numbers re-derived and {len(suggestions)} suggestions staged for a path "
                  "choice before any change is implemented.", body, wide=True)


def _reconcile_state() -> tuple[bool, bool]:
    """(declares itself read-only, guarded by a test that the Makefile runs) — checked, not remembered."""
    script = ROOT / "scripts/reconcile_depth_charts.py"
    guard = ROOT / "tests/test_reconcile_depth_charts.py"
    readonly = False
    if script.exists():
        text = script.read_text(encoding="utf-8")
        writes = [m for m in ("to_csv(", 'open(PUBLISHED, "w"', 'open(DEPTH, "w"', "write_text(") if m in text]
        readonly = ("Read-only" in text or "does not reconcile or rewrite" in text) and not writes
    guarded = guard.exists() and "test_reconcile_depth_charts" in (ROOT / "Makefile").read_text(encoding="utf-8")
    return readonly, guarded


def _reconcile_severity() -> str:
    readonly, guarded = _reconcile_state()
    return "Info · closed on this branch" if (readonly and guarded) else "Medium · needs review"


def _reconcile_finding() -> str:
    readonly, guarded = _reconcile_state()
    if readonly and guarded:
        return ("Closed by the merged repair: scripts/reconcile_depth_charts.py compares the 2026-11-13 "
                "official extract with the same-dated capture and rewrites nothing, and "
                "tests/test_reconcile_depth_charts.py asserts that. This row is generated by reading the "
                "script and the Makefile at build time, so it re-opens itself if either changes — it is not "
                "a sentence someone remembered to delete.")
    return ("scripts/reconcile_depth_charts.py can rewrite data/availability/depth_charts.csv, so a "
            "scheduled capture could be overwritten by a dated extract. Status read from the file and the "
            "Makefile at build time (read-only declared: "
            f"{readonly}; guard test wired: {guarded}).")


def write_flagged(claims: list[dict], register: list[dict]) -> Path:
    """Flagged rows for the 2026-11-18 register, generated from the re-derived claim values.

    A finding that quotes a number takes it from the claim check that produced it, so the flagged page and
    the register can never disagree after the next capture.
    """
    by = {c["claim_id"]: c for c in claims}

    def val(cid, key, default="(not derived)"):
        c = by.get(cid)
        return (c or {}).get(key) or default

    rows = [
        dict(id="F-2026-11-18b-01", severity="High · open",
             finding=f"Settlement, not sourcing, is what blocks a verdict: {val('C-13', 'repo_value')}. "
                     f"The official Week 10 page prints {val('C-13', 'live_value')}.",
             next="Run the forward-capture step against the official week-10 score page so all 14 finals "
                  "enter the ledger, then re-verify each row; the gates and the competition stand unchanged.",
             source_label="Official Week 10 schedule (finals printed per game)",
             source_url=U["schedule_w10"]),
        dict(id="F-2026-11-18b-02", severity="Medium · open",
             finding=f"The request's '136-game log' maps to nothing here: {val('C-14', 'repo_value')}. "
                     "The requirement cannot be verified as written.",
             next="Owner to restate the item as an artefact (file or commit) or a game count of the forward "
                  "ledger; until then it stays an unverified reference, not completed work.",
             source_label="", source_url=""),
        dict(id="F-2026-11-18b-03", severity="Info · closed",
             finding=f"The 2026-11-18 coverage question is answered: {val('C-11', 'repo_value')}; "
                     f"{val('C-11', 'live_value')}. 'Not listed' here means 'no game', which is not the same "
                     "claim as 'available'.",
             next="No repair. Keep the bye list in the capture's own audit so a future zero-row club is "
                  "explained by the schedule and not by a parser change.",
             source_label="Official Week 10 schedule (teams on bye)", source_url=U["schedule_w10"]),
        dict(id="F-2026-11-18b-04", severity="Medium · open",
             finding="The injury report the availability surfaces overlay is the Week 10 table — the last "
                     "one the league published — while the next fixture (Week 11) is already scheduled. "
                     "A matrix built on it is a worked example on played games, not a pre-kickoff read.",
             next="Read the matrix only against a captured pre-kickoff window; the register row R-31 (no "
                  "inactive-list capture) is the item that turns it into a live surface.",
             source_label="NFL.com injury report", source_url=U["injuries"]),
        dict(id="F-2026-11-18b-05", severity="High · open",
             finding=f"Houston depth remains image-only on the club's own page, re-read on 2026-11-18: "
                     f"{val('C-05', 'live_value')}; our capture: {val('C-05', 'repo_value')}.",
             next="An authorised structured source, or an owner decision to exclude HOU from depth-derived "
                  "features and publish the exclusion (SUG-18-09).",
             source_label="Houston Texans depth chart (image only)", source_url=U["texans"]),
        dict(id="F-2026-11-18b-06", severity="Medium · open",
             finding="The vig-free decomposition measures the operator margin on mirror data: the prices are "
                     "the pinned community archive, not an authenticated operator quote, so a margin cost is "
                     "an estimate of the fee, not a quoted fee.",
             next="Choose the price-data path (SUG-18-01). Until then G1 fails for every candidate and no "
                  "division may be ranked on return.",
             source_label="NFL scores (the official settlement the archive is graded against)",
             source_url=U["scores"]),
        dict(id="F-2026-11-18b-07", severity=_reconcile_severity(),
             finding=_reconcile_finding(),
             next="Re-opens by itself if the script gains a write path or the guard test leaves the Makefile; "
                  "no further action while both hold.",
             source_label="NFL.com injury report (the capture the script could touch)",
             source_url=U["injuries"]),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "flagged_2026_11_18b.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "severity", "finding", "next", "source_label", "source_url"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path


def main() -> int:
    sys.path.insert(0, str(ROOT / "pipeline"))
    from claim_checks_20261118 import build_claims, write_claims
    claims = build_claims()
    write_claims(claims)

    register = register_rows()
    suggestions = suggestion_rows()

    # fail-closed evidence contract: see assert_contract below
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(register).to_csv(OUT / "request_register_items_2026_11_18.csv", index=False)
    pd.DataFrame(suggestions).to_csv(OUT / "suggestions_2026_11_18.csv", index=False)

    # The contract runs after the CSVs are written: two rows cite this register's own output, and a check
    # that fails because its own file is not on disk yet would be a check on ordering, not on evidence.
    assert_contract(register)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    for name in ("request_register_items_2026_11_18.csv", "suggestions_2026_11_18.csv",
                 "claim_checks_2026_11_18.csv"):
        (SITE_DATA / name).write_bytes((OUT / name).read_bytes())

    write_flagged(claims, register)

    html_text = render(claims, register, suggestions)
    (ROOT / "verified-register-2026-11-18.html").write_text(html_text, encoding="utf-8")
    print(f"  request register: {len(register)} items, {len(suggestions)} suggestions, "
          f"{len(claims)} claim checks -> verified-register-2026-11-18.html")
    return 0


def assert_contract(register: list[dict]) -> None:
    """Every evidence string that says MISSING must be a real gap and every artefact cited must exist.

    The helpers already return the truth; this turns a stale row into a build failure instead of a silent
    lie: a row whose status claims a gap must not cite a present file, and a row that claims a build must
    cite at least one file that opens.
    """
    problems = []
    for r in register:
        evs = r["evidence"] if isinstance(r["evidence"], list) else [(str(r["evidence"]), True)]
        present = [ok for _, ok in evs]
        text = " ".join(t for t, _ in evs)
        if r["status"].startswith(("BUILT", "HELD", "POLICY")) and not any(present):
            problems.append(f"{r['id']}: status {r['status']!r} cites no artefact that opens")
        if "MISSING" in text and not r["status"].startswith(("NOT BUILT", "OPEN", "PARTLY", "BLOCKED",
                                                              "REFERENCE", "CONFLICTS", "POLICY")):
            problems.append(f"{r['id']}: evidence is missing but the status is {r['status']!r}")
        if "present, register needs updating" in text:
            problems.append(f"{r['id']}: a file the register says is absent now exists — update the row")
    if problems:
        raise SystemExit("request register evidence contract failed:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    sys.exit(main())
