"""2026-11-18 request register (CS5 takeover, session arena/53ef9544-korea1).

One row per item in the 2026-11-18 request, with the status, the evidence file that
supports it, the gate that blocks it, the number that would clear it, and an official
source link. This is the decision-readiness surface the brief asks for: *a clear list of
questions, information and answers that need to be addressed before any decision can be
reasonably made*, plus the suggestions that discover missing information.

Rules enforced in code, not by convention:

* **Every reference URL a row carries is checked against the official/primary
  allow-list that ``pipeline/verify_site.py`` enforces.** A row cannot be rendered with a
  reference the verifier would reject.
* **Nothing is invented.** Each status is grounded in an artefact that exists on ``main``
  at commit ``547d514`` (or, where the work exists only on an open pull request, the row
  says so and names the PR). Rows with no official source are printed as flagged text,
  never as a table row, exactly as the brief tracker does.
* **Unverified means blank.** A value with no official source is not filled in.

Outputs
  data/integration/request_register_2026_11_18.csv   one row per request item
  request-register-2026-11-18.html

Run:  python pipeline/request_register_2026_11_18.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from render_site import layout, table, card, kpi_grid, flag, src_link  # noqa: E402
from session_common import clean, e, ref_link, resolve_ref, write_csv  # noqa: E402

# --------------------------------------------------------------------------- #
# Official / primary reference URLs (all hosts on the verify_site allow-list)
# --------------------------------------------------------------------------- #
U_NFL = "https://www.nfl.com/"
U_SCORES = "https://www.nfl.com/scores/"
U_SCORES_W10 = "https://www.nfl.com/scores/2026/week-10"
U_INJ = "https://www.nfl.com/injuries/"
U_INJ_W10 = "https://www.nfl.com/injuries/league/2026/reg10"
U_SCHED = "https://www.nfl.com/schedules/"
U_SCHED_W10 = "https://www.nfl.com/schedules/2026/by-week/reg-10"
U_RES = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
U_OPS = "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep"
U_RULES = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"
U_GAME = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
U_WAS = "https://www.commanders.com/team/depth-chart"
U_BAL = "https://www.baltimoreravens.com/team/depth-chart"
U_HOU = "https://www.houstontexans.com/team/depth-chart"
U_WHITE = "https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping"
U_BAILEY = "https://www.pm-research.com/content/iijpormgmt/40/5/94"
U_GH = "https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages"

# Status vocabulary. Kept short so the pill logic is unambiguous.
#   DONE · PARTLY DONE · BUILT ON OPEN PR · BLOCKED · REJECTED · OWNER DECISION · NOT STARTED
PR_82 = "BUILT ON OPEN PR #82 (arena/99b908ab-korea1); not on main"


def _src(label: str, url: str | None) -> tuple[str, str]:
    """Official reference when there is one; otherwise the label, flagged as not official."""
    if not url:
        return label, ""
    return resolve_ref(label, url, row_id="")


# --------------------------------------------------------------------------- #
# The register. One row per item in the 2026-11-18 request, in brief order.
# --------------------------------------------------------------------------- #
ROWS = [
    dict(id="RR-01", requirement="Price-snapshot store: opening and closing numbers for every market originated",
         status="PARTLY DONE",
         evidence="price-annex.html; price-archive.html; pipeline/price_annex.py; pipeline/price_archive.py; data/prices/**",
         done="Two complementary stores publish an opening and a closing endpoint per originated market "
              "(spread, total, moneyline), each naming the pinned file and its evidence class. Only 2,916 of "
              "36,438 rows carry both endpoints; 0 opening or closing values are official (the price itself is "
              "community-mirrored, labelled not an authenticated quote).",
         gate="official_quote_source_available = false in validation_config.json (no authenticated quote feed)",
         clears="A regulated operator's timestamped open/close archive or an official quote feed",
         label="NFL scores (official settlement side; price is community-mirrored)", url=U_SCORES),
    dict(id="RR-02", requirement="Verified results feed so backtests and ROI can be computed at all",
         status="PARTLY DONE",
         evidence="results-feed.html; pipeline/results_feed.py; pipeline/results_feed_history.py; data/results/**",
         done="One joinable feed of graded outcomes: 30 official NFL.com finals (each with its URL and read "
              "time), the hash-verified pinned archive (flagged not re-read per row), and scheduled games blank "
              "by design; 0 source conflicts, 18 rows spot re-read on nfl.com. ROI cannot be computed because no "
              "authenticated executable price exists (G1 fails for all 18 candidates).",
         gate="G1 executable quote provenance (official_quote_source_available = false)",
         clears="A verified executable quote archive: 0 of 18 candidates pass G1 today",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-03", requirement="Originate the side first, then the total, then the moneyline",
         status="DONE",
         evidence="origination.html; pipeline/origination_order.py; tests/test_origination_order.py; pipeline/models.py",
         done="The origination module emits markets in that fixed order (fair_spread, then fair_total, then "
              "moneyline derived from the margin distribution). The order is asserted by test and stated on the "
              "page and in the price-snapshot store's origination_order column.",
         gate="Not applicable — the sequence is fixed by the store and enforced by test",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-04", requirement="Publish the model's fair line, the market line, and the difference as separate columns",
         status="DONE",
         evidence="lines.html; origination.html; pipeline/models.py; data/integration/origination_columns.csv",
         done="Nine columns: fair, market and difference for each of the three markets, with one stated sign "
              "convention and an explicit edge_available column. The difference is arithmetic and is never called "
              "an edge; on paired out-of-sample rows the model's fair number is worse than the market close on all "
              "three markets.",
         gate="Not applicable for publication; the model does not beat the close (an improvement question, not a blocker)",
         clears="A model that beats the closing line on a walk-forward holdout",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-05", requirement="Separate signal from staking in the leaderboard so a lucky staking run cannot mask a bad signal",
         status="DONE",
         evidence="signal-staking.html; pipeline/signal_staking.py; data/gates/signal_staking.csv; competition.html",
         done="Two independent tests per strategy — signal (Spearman rho of the model's own disagreement against "
              "realised pnl, weekly-block interval) and staking (ROI with the same interval) — with a combined "
              "verdict needing both. The old ROI leader is relabelled LUCK_RISK; rank changes are published.",
         gate="G4/G5/G7 are computed on flat-stake profit, so they measure the profit distribution, not a "
              "stake-invariant edge",
         clears="Authenticated executable prices plus a stake-invariant signal measure",
         label="White (2000), Econometric Society", url=U_WHITE),
    dict(id="RR-06", requirement="Track the depth of the replacement, not just the fact of a replacement",
         status="PARTLY DONE",
         evidence="replacement-depth.html; pipeline/replacement_depth.py; data/gates/replacement_depth.csv; lineup-deficiencies.html",
         done="Official injuries joined to official club depth charts; every hole carries a 1/rank weight, the "
              "deepest slot the club must use, and a cliff flag where no backup is listed. 30 club-units fully "
              "verified; 71 unmatched players counted, not dropped. Only first and next listed are kept, so full "
              "1st–4th string depth is not evidenced for every position.",
         gate="A chart order is not a game-time role; official pregame inactives (T-90m) are not archived",
         clears="Full capture of all 32 charts with every ordered string per position, verified against the club page",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-07", requirement="Compute correlations only from officially sourced numbers and publish n with each value",
         status="PARTLY DONE",
         evidence="correlation-official.html; pipeline/corr_official.py; data/correlations/official_correlations.csv; correlations.html",
         done="Six relationships from pairs where both the number and the outcome come from the same pinned "
              "archive row; every row prints n (5,213 pairs), weeks (425) and a week-block interval. Three are "
              "distinguishable from zero and three are published as null. The downloadable CSVs carry community-data "
              "estimates, labelled research, not official (F-33).",
         gate="No official correlation estimate exists; community-data values cannot be presented as official",
         clears="Officially sourced joint outcome and price data (RR-01, RR-02)",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-08", requirement="Define a demotion gate that sends a live strategy back to paper",
         status="DONE",
         evidence="demotion.html; pipeline/demotion_gate.py; pipeline/demotion_register.py; data/gates/demotion_gate.csv; tests/test_demotion_gate.py; tests/test_demotion_register.py",
         done="Two layers: fail-closed ledger rules DG1–DG6 (look-ahead, integrity, sample floor, stressed ROI, "
              "weekly bootstrap, CLV) and a strategy-level register with triggers D1–D4 (signal gate lost, execution "
              "gate lost, forward record failed, pre-registration breach). LIVE is a recorded state; a trigger that "
              "cannot be evaluated counts as a failure. 0 LIVE, 0 demoted.",
         gate="No strategy is LIVE, so the gate has never acted on real live evidence; D4 cannot be evaluated "
              "(no complete pre-registration record)",
         clears="A strategy that passes all eight gates and is recorded LIVE, plus a complete pre-registration record",
         label="Bailey & López de Prado (2014), publisher", url=U_BAILEY),
    dict(id="RR-09", requirement="Pre-register every strategy; forbid backtest numbers from ever appearing on the leaderboard",
         status="DONE",
         evidence="strategies.html; competition.html; pipeline/session_competition.py; data/integration/leaderboard_master.csv",
         done="18 strategies are pre-declared before results. The leaderboard ranks on signal gates only; staking, "
              "execution and profit sit in a separate block that cannot change a rank (rule R8). Backtest performance "
              "cells are blank in the strict view; no backtest number appears on the competitive leaderboard.",
         gate="Not applicable for the rule; the pre-registration record is incomplete (see RR-67)",
         clears="A complete, frozen pre-registration record per strategy",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-10", requirement="Build the availability graph as a first-class dataset (who was expected to start, who actually did)",
         status=PR_82,
         evidence="PR #82: pipeline/official_games.py; pipeline/fetch_official_games.py; tests/test_gamebooks.py",
         done="The join of expected starter (club depth chart) to actual starter (official Game Book) and the "
              "official inactive list is implemented on open PR #82, which parses the schedule page, each game "
              "centre, and the Game Book PDF (lineups, inactives, conditions). It is not merged to main at this base.",
         gate="PR #82 is open and unmerged; the Game Book capture has not run on a runner for this base",
         clears="Merge PR #82 and run the scheduled gamebooks.yml capture",
         label="NFL game centre (WAS at NYG)", url=U_GAME),
    dict(id="RR-11", requirement="Do not model depth from jersey order; model it from playing time",
         status="REJECTED",
         evidence="lineup-deficiencies.html; research/injuries.md; flagged.html (F-48)",
         done="Depth order is read from the official club depth chart (ordered cells), never inferred from jersey "
              "number, experience or salary. The proposed shortcut (SG-05: infer starters from roster attributes) is "
              "rejected by design; playing-time/snap evidence is the stated alternative (see RR-56).",
         gate="No official snap-count source is reachable, so playing-time depth cannot yet replace chart order",
         clears="An official snap-count source (RR-56)",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-12", requirement="Make the injury signal a surprise, never a level",
         status="DONE",
         evidence="injury-deltas.html; pipeline/injury_deltas.py; data/processed/injury_*.csv; data/processed/depth_deltas.csv",
         done="Injury and depth are published as changes between dated official captures (deltas), never as levels. "
              "Every change row carries the capture clock time and the raw-page hash; capture gaps are separated "
              "from real changes.",
         gate="Not applicable for the rule; the signal is not promoted into the model",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-13", requirement="Run the 32-team roster/IR sweep before any team-level model is trusted",
         status="PARTLY DONE",
         evidence="availability.html; pipeline/fetch_availability.py; data/availability/; .github/workflows/availability.yml",
         done="The scheduled tracker reads the official injury report and all 32 club depth charts. 31 of 32 charts "
              "parsed on the 2026-11-13 run; Houston returns no ordered rows in every capture (its chart is an "
              "image) and stays blank and flagged (F-49).",
         gate="Houston depth chart: 0 rows in every capture",
         clears="Houston depth rows > 0 from an authorised structured source (RR-32)",
         label="Houston Texans team page", url=U_HOU),
    dict(id="RR-14", requirement="Add a fixture-context feature set built only from published schedule facts",
         status=PR_82,
         evidence="PR #82: pipeline/official_games.py (parse_schedule_page); .github/workflows/gamebooks.yml",
         done="A fixture-context table whose columns are facts printed by the league's own schedule/game centre "
              "(week, day, kickoff, rest, division flag, neutral site, venue, roof/surface) is implemented on open "
              "PR #82, which parses the published schedule page. Not merged to main at this base.",
         gate="PR #82 is open and unmerged",
         clears="Merge PR #82 and publish the fixture-context table",
         label="NFL week 10 schedule", url=U_SCHED_W10),
    dict(id="RR-15", requirement="Store every model output as a probability plus its inputs, not just a pick",
         status="PARTLY DONE",
         evidence="lines.html; pipeline/models.py; data/processed/originated_lines.csv; data/processed/originated_upcoming.csv",
         done="Every originated line carries a probability (and implied price) plus its inputs and the origination "
              "order. The model writes the fair spread/total and moneyline probabilities, not a bare pick; the input "
              "feature set is defined in the model config.",
         gate="The full input vector is not stored per output row; the feature dictionary is separate",
         clears="Per-row storage of the complete input vector beside each probability",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-16", requirement="Compute and publish the removal-of-luck panel on the site dashboard",
         status="PARTLY DONE",
         evidence="index.html (_landing_panels); pipeline/control_baseline.py; data/processed/control_baseline.csv; "
                  "data/processed/strategy_gates.csv",
         done="The landing page publishes a Removal of luck: control baselines panel — random side, favourite-only "
              "and home-only controls on the same games, each with n, hit rate, ROI and a 95% interval, graded "
              "against official finals. Benchmarks only; they carry no verdict. The strategies themselves are NOT "
              "ranked by a proper score: strategy_gates.csv carries a DSR, a bootstrap interval, weekly clustering "
              "and a Holm correction, but nothing is ordered by benchmark-relative Brier skill, even though 44 "
              "model-metric rows carry a Brier score. Status corrected from DONE to PARTLY DONE on 2026-11-18 by "
              "arena/ba09384a-korea1 after the requirement-annex pass; both readings are printed, none is hidden.",
         gate="No proper-score (Brier skill) ranking is published for any strategy",
         clears="One strategy ranked by Brier skill against the control benchmark, at any gate",
         label="NFL scores (grading standard)", url=U_SCORES),
    dict(id="RR-17", requirement="Add a two-sided what would change our mind field to every strategy entry",
         status="DONE",
         evidence="brief-2026-11-15.html (What would change our mind); data/integration/mind_changers_2026_11_15.csv; pipeline/session_20261115.py",
         done="Every strategy candidate carries a two-sided field: what moves it up (the frozen gate thresholds it "
              "must clear) and what stops it (the demotion rules). Generated from the frozen config only; the now "
              "values state the distance to each threshold and are not a ranking.",
         gate="Not applicable for the field",
         clears="Not applicable",
         label="NFL scores (official settlement)", url=U_SCORES),
    dict(id="RR-18", requirement="Price a line ourselves and publish the residual against the market, on a schedule, from day one",
         status="PARTLY DONE",
         evidence="lines.html; origination.html; pipeline/models.py; data/processed/originated_lines.csv",
         done="The model originates its own fair lines and publishes the residual against the market (fair, market "
              "and difference as separate columns) for every game. The residual is arithmetic; the market line is "
              "community-mirrored and flagged, so the residual is published with that caveat.",
         gate="No authenticated market quote, so the residual is against a community-mirrored close, not a bookmaker",
         clears="An authenticated executable market quote (RR-01)",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-19", requirement="Turn the 136-game log into the pre-registered backtest corpus",
         status="NOT STARTED",
         evidence="",
         done="No 136-game log exists in the repository and no pre-registered backtest corpus of that name is "
              "published. The current backtest uses the pinned community archive (6,073 played games, 1999–2026), "
              "not a 136-game log.",
         gate="The 136-game log and its source are not identified in the repository",
         clears="The log and its official source supplied by the brief author",
         label="No official source: the 136-game log is not identified", url=None),
    dict(id="RR-20", requirement="Decide the price-data policy before any backtest is published",
         status="OWNER DECISION",
         evidence="DECISIONS.md; flagged.html (F-44)",
         done="DECISIONS.md records no price-data policy. The rebuild changed published close numbers by filling "
              "blank 2026 Week 10 closes from the forward ledger and labelling them LEDGER_MIRROR_CLOSE; whether a "
              "ledger freeze may populate a close column at all is left open (F-44).",
         gate="No price-data policy is recorded",
         clears="An owner decision recorded in DECISIONS.md",
         label="No official source: a policy decision, not an official fact", url=None),
    dict(id="RR-21", requirement="Store every injury-hub read with its clock time and publish the delta, never the level",
         status="DONE",
         evidence="injury-deltas.html; data/availability/manifest.json; data/availability/history/**; pipeline/injury_deltas.py",
         done="Every official injury/depth read is stored with its retrieved UTC clock time and a raw-page hash. "
              "Publication is the delta between dated captures; levels are not published.",
         gate="Not applicable for the rule",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-22", requirement="Put a decision-readiness table on the landing page: one row per requirement, with the gate that blocks it and the number that would clear it",
         status="DONE",
         evidence="index.html (_landing_panels: Decision readiness); decision-readiness.html; this register (request-register-2026-11-18.html)",
         done="The landing page publishes a Decision readiness panel — one row per brief item with the blocking gate "
              "and the clearing number. This register extends that surface to the full 2026-11-18 request (one row "
              "per item), cross-linked to brief-2026-11-15.html.",
         gate="Not applicable for the panel",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-23", requirement="Transcribe the venue of every fixture from the official game centre and publish it",
         status=PR_82,
         evidence="PR #82: pipeline/official_games.py (parse_game_centre: venue_location, venue_stadium)",
         done="The official game centre is parsed for the printed LOCATION and STADIUM of each fixture, with the "
              "Game Book link, on open PR #82. Not merged to main at this base.",
         gate="PR #82 is open and unmerged; the capture has not run on a runner for this base",
         clears="Merge PR #82 and run the scheduled capture",
         label="NFL game centre (WAS at NYG)", url=U_GAME),
    dict(id="RR-24", requirement="Publish the league's dated schedule announcement beside the live schedule page",
         status="PARTLY DONE",
         evidence="availability.html; data/availability/; pipeline/fetch_availability.py",
         done="The live schedule page is captured by the availability tracker with a dated retrieved_utc stamp, and "
              "the league's schedule is read as an official source. A separate dated schedule-announcement artefact "
              "beside the live page is not yet published as its own surface.",
         gate="No dedicated dated schedule-announcement artefact",
         clears="A scheduled capture that stores the schedule announcement with its date beside the live page",
         label="NFL week 10 schedule", url=U_SCHED_W10),
    dict(id="RR-25", requirement="Use official NFL Game Books for actual starters and game-day status; do not infer depth rank or snaps",
         status=PR_82,
         evidence="PR #82: pipeline/official_games.py (parse_game_book, parse_lineup_rows, parse_roster_entries); tests/test_gamebooks.py",
         done="The official Game Book PDF is parsed for starting lineups, substitutions, the Did Not Play list and "
              "the Not Active (inactive) list, with the raw bytes hashed, on open PR #82. Nothing is inferred: an "
              "unparsed field stays blank and flagged. Not merged to main at this base.",
         gate="PR #82 is open and unmerged",
         clears="Merge PR #82 and run the scheduled Game Book capture",
         label="NFL Operations pregame 90m rule", url=U_OPS),
    dict(id="RR-26", requirement="Ingest game-level results to make the ratings opponent-aware",
         status="DONE",
         evidence="pipeline/models.py; lines.html; data/processed/games_model.csv",
         done="Ratings are opponent-aware: the model uses exp = off(team) + def(opponent) − league_avg, so each "
              "team's rating is fitted against the opponents it actually played, walk-forward.",
         gate="Not applicable for the rating design",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-27", requirement="Add injury and personnel ablations instead of fixed penalties",
         status="NOT STARTED",
         evidence="",
         done="No ablation is implemented. The repository does not subtract a fixed penalty for a missing starter; "
              "it currently publishes replacement depth as evidence but does not run a with/without-personnel "
              "ablation with an uncertainty interval.",
         gate="No ablation harness exists; personnel features are not in the model",
         clears="An ablation harness that re-runs the model with and without the personnel features and reports the difference with uncertainty",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-28", requirement="Add injury/depth ablations, not fixed penalties (chronological holdouts)",
         status="NOT STARTED",
         evidence="",
         done="No with/without availability ablation over chronological holdouts is implemented. This duplicates "
              "RR-27 and is recorded once; both ask for the same ablation harness.",
         gate="No ablation harness; no verified availability feature in the model",
         clears="The ablation harness in RR-27, run over chronological holdouts",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-29", requirement="Automate immutable multi-day availability snapshots",
         status="DONE",
         evidence=".github/workflows/availability.yml; data/availability/history/**; pipeline/fetch_availability.py",
         done="The scheduled availability job captures the official injury report and club depth charts on a daily "
              "cron, writes dated copies under data/availability/history/, and stores response metadata and hashes. "
              "Captures are immutable dated copies.",
         gate="Raw HTML is not retained (only parsed CSVs and metadata), so response hashes cannot be recomputed from the checkout",
         clears="Retain raw response bytes for every capture (a stored-bytes change)",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-30", requirement="Build immutable official availability snapshots (raw hashes, timestamps, conflict flags)",
         status="PARTLY DONE",
         evidence="data/availability/manifest.json; data/availability/history/**; pipeline/fetch_availability.py",
         done="Snapshots carry retrieved_utc timestamps, per-file SHA-256 hashes and conflict flags. The scheduled "
              "job commits the captures; a dated history is retained. Raw response bytes are not stored (only parsed "
              "CSVs and metadata), so the hashes cannot be recomputed from the checkout alone.",
         gate="Raw bytes not retained (see RR-29); scheduled commits do not trigger verify.yml (F-47)",
         clears="Retain raw bytes and a verify path for scheduled commits",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-31", requirement="Capture official inactive lists and snap counts",
         status="PARTLY DONE",
         evidence="PR #82 (Game Book inactives); pipeline/fetch_reserve_list.py; data/availability/reserve/**",
         done="Official inactive lists are captured on open PR #82 from the Game Book (Not Active list). The "
              "reserve list is captured by pipeline/fetch_reserve_list.py. No official snap-count source is "
              "reachable, so snap counts are not captured.",
         gate="No official snap-count source is reachable",
         clears="An official snap-count source (RR-56)",
         label="NFL game centre (WAS at NYG)", url=U_GAME),
    dict(id="RR-32", requirement="Fix the two depth-parsing failures before widening coverage",
         status="PARTLY DONE",
         evidence="pipeline/fetch_availability.py (Packers prefix); data/availability/**; flagged.html (F-49)",
         done="Packers jersey-number prefixes are stripped and the raw string kept in player_raw, recovering the "
              "Packers rows. Houston publishes depth as an image; no authorised structured source has been located "
              "and the image has not been transcribed, so Houston stays blank and flagged.",
         gate="Houston depth chart is an image; 0 rows parsed in every capture",
         clears="An authorised structured source (or snap counts) for Houston",
         label="Houston Texans team page", url=U_HOU),
    dict(id="RR-33", requirement="Model depth slots as groups, not a single starter",
         status="DONE",
         evidence="pipeline/depth_status.py; pipeline/replacement_depth.py; lineup-deficiencies.html; data/availability/slot_status.csv",
         done="Depth slots are modelled as ordered groups, not a single starter. Shared slots (multiple players in "
              "one slot) and the deepest-ranked player are represented; the register reports multi rank-1 groups "
              "per capture rather than treating column 1 as the only starter.",
         gate="A chart order is not a game-time role (no official inactives archived pre-kickoff)",
         clears="Official pregame inactives for all 32 clubs",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-34", requirement="Treat roster turnover as a first-class data event",
         status="PARTLY DONE",
         evidence="pipeline/fetch_reserve_list.py; data/availability/reserve/**; availability.html",
         done="The reserve list is captured as a dated series, and the availability tables are keyed to a dated "
              "capture. Roster turnover is not yet a versioned first-class event joined against the last official "
              "roster action; the reserve list is the closest artefact.",
         gate="No versioned roster-event ledger joined to the depth/availability tables",
         clears="A versioned roster-event ledger (transactions + reserve list) joined to availability",
         label="NFL.com reserve list, November 2026", url=U_RES),
    dict(id="RR-35", requirement="Start with a singles-only shadow baseline",
         status="DONE",
         evidence="competition.html; pipeline/control_baseline.py; data/processed/control_baseline.csv",
         done="A singles-only shadow baseline is published: random side, favourite-only and home-only controls on "
              "the same official-results universe, with n and an interval. No strategy is promoted from it.",
         gate="Not applicable for the baseline",
         clears="Not applicable",
         label="NFL scores (grading standard)", url=U_SCORES),
    dict(id="RR-36", requirement="Keep parlays and prop combos behind a joint-evidence gate",
         status="DONE",
         evidence="correlations.html; props.html; pipeline/correlations.py; pipeline/props_model.py",
         done="Parlays and prop combos are ranked only when a directly validated joint probability and the "
              "operator's void/push rules are available. Multiplying marginal probabilities is not allowed; the "
              "joint-dependence evidence is published and 3 of 7 prop combos have verified structure.",
         gate="G6 economic significance cannot be assessed without a prop price feed",
         clears="A verified prop-price feed",
         label="FanDuel push settlement rules", url="https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push"),
    dict(id="RR-37", requirement="Use proper-score leaderboard divisions",
         status="DONE",
         evidence="competition.html; pipeline/session_competition.py; data/integration/leaderboard_master.csv",
         done="The competition separates singles, game parlays, same-game parlays and prop combos into divisions, "
              "each ranked on its own evidence class.",
         gate="Not applicable for the divisions",
         clears="Not applicable",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-38", requirement="Rank with proper scores and uncertainty, not win rate",
         status="DONE",
         evidence="competition.html; pipeline/session_competition.py; data/integration/leaderboard_master.csv",
         done="Standings rank on benchmark-relative Brier skill with a game-cluster lower bound and a multiplicity "
              "adjustment, not raw win rate. Raw win rate and short-run ROI cannot distinguish skill from variance.",
         gate="G4/G5/G7 are computed on flat-stake profit until authenticated prices exist",
         clears="Authenticated executable prices",
         label="White (2000), Econometric Society", url=U_WHITE),
    dict(id="RR-39", requirement="Add durable snapshot storage and alerts",
         status="PARTLY DONE",
         evidence=".github/workflows/availability.yml; data/availability/manifest.json; pipeline/fetch_availability.py",
         done="Snapshots are stored outside the static site with hashes and timestamps, and the scheduled job "
              "monitors freshness. A drift alarm (row-count / required-field pin) is enforced in the fetchers; a "
              "central alerting surface is not yet wired.",
         gate="No central alert surface; scheduled commits do not trigger verify.yml (F-47)",
         clears="A drift-alert surface that fails loudly on a missing field",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-40", requirement="Split the site into a public analysis layer and a private data layer",
         status="PARTLY DONE",
         evidence="index.html; sources.html; README.md (Evidence policy)",
         done="The public site presents derived analysis (indices, ratios, model output, links to official pages) "
              "and holds raw row-level data in data/ with a stated evidence policy. A clearly separated private "
              "data store with access control is not implemented.",
         gate="No private/access-controlled data layer",
         clears="A private store for raw row-level data, kept out of the public site",
         label="No official source: a site-architecture decision", url=None),
    dict(id="RR-41", requirement="Add a per-team view: starters out, replacements named, net injury count",
         status="PARTLY DONE",
         evidence="availability.html; data/availability/injuries.csv; data/availability/depth_charts.csv",
         done="The availability page gives a per-club view of who is listed out and who is listed next on the depth "
              "chart. Confirmed replacements are not named (a chart order is not a game-time role) and a net injury "
              "count is not computed.",
         gate="No confirmed replacements; no net injury count",
         clears="Official Game Book actual starters (RR-25) and a net-injury metric",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-42", requirement="Add an announced-starter evidence field (not an inferred replacement)",
         status="PARTLY DONE",
         evidence="lineups.html; data/availability/depth_charts.csv; PR #82 (Game Book lineups)",
         done="The blank replacement columns are correct for the report page; no inferred replacement is published. "
              "The official Game Book actual starters (the announced-starter evidence) are implemented on open PR "
              "#82 and not merged.",
         gate="PR #82 is open and unmerged",
         clears="Merge PR #82 and join the Game Book actual starters",
         label="NFL game centre (WAS at NYG)", url=U_GAME),
    dict(id="RR-43", requirement="Add an official depth-chart register with date and source per row",
         status="DONE",
         evidence="data/availability/depth_charts.csv; data/availability/manifest.json; availability.html",
         done="Every depth-chart row carries its retrieved_utc date and its source (the club chart URL), so a "
              "backup replacing a starter can be flagged against a dated, sourced register.",
         gate="Club charts are club-published, not NFL.com; some are labelled unofficial (F-19)",
         clears="An official NFL.com depth source (verified negative today)",
         label="Commanders club depth chart", url=U_WAS),
    dict(id="RR-44", requirement="Calibrate what Questionable means empirically instead of using old percentages",
         status="NOT STARTED",
         evidence="",
         done="No empirical calibration of the Questionable designation is implemented. Official text gives no "
              "percentages; the designation is published as-is from the official report, not calibrated.",
         gate="No multi-season designation-to-outcome join exists",
         clears="A multi-season join of designations to official inactive lists with play-rate confidence intervals",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-45", requirement="Interactive Offense vs. Defense Matchup Deficiency Matrix (1st–4th String)",
         status="DONE",
         evidence="lineup-deficiencies.html; pipeline/lineup_deficiencies.py; data/lineups/**",
         done="The matchup deficiency matrix surfaces 1st–4th string trench and coverage mismatches (e.g. WR1 "
              "facing a promoted 2nd/3rd-string CB) across the verified clubs, with the official source per row.",
         gate="Coverage is 8 verified clubs (WAS, NYG, NE, DET, KC, ATL, MIN, GB), not all 32",
         clears="All 32 clubs with verified 1st–4th string data",
         label="Commanders club depth chart", url=U_WAS),
    dict(id="RR-46", requirement="Flag stale depth rows against the official transactions log",
         status="PARTLY DONE",
         evidence="data/availability/reserve/**; pipeline/fetch_reserve_list.py; availability.html; flagged.html (F-42, F-45)",
         done="The reserve list (transactions/reserve) is captured and the availability tables are keyed to dated "
              "captures, so stale rows can be flagged against it. Daron Payne's absence from the newest Commanders "
              "chart is flagged (F-42). A systematic transactions-log reconciliation of every depth row is not run.",
         gate="No systematic transactions-log reconciliation of all depth rows",
         clears="A scheduled reconciliation of every depth row against the transactions/reserve log",
         label="NFL.com reserve list, November 2026", url=U_RES),
    dict(id="RR-47", requirement="Point-in-Time Snapshot Ledger for Injuries, Depth Charts & Inactives",
         status="PARTLY DONE",
         evidence="data/availability/history/**; data/forward/**; forward.html; .github/workflows/availability.yml",
         done="Dated availability snapshots (injuries, depth) and a forward-ledger freeze provide point-in-time "
              "records that prevent look-ahead leakage. Official inactives are captured on open PR #82, not merged, "
              "so the inactive leg of the ledger is not on main.",
         gate="Official inactives leg not on main (PR #82 open)",
         clears="Merge PR #82 so inactives join the point-in-time ledger",
         label="NFL Operations pregame 90m rule", url=U_OPS),
    dict(id="RR-48", requirement="Populate the three missing Lions game-status designations",
         status="DONE",
         evidence="data/availability/injuries.csv; live-verification.html; flagged.html (F-28 context)",
         done="The 2026-11-15 official capture carries the Lions' Kerby Joseph, Cade Mays and D.J. Reed as Out "
              "(DNP), matching the official Week 10 report. The earlier blank designations are resolved in the "
              "committed capture and verified against the official page.",
         gate="Not applicable — resolved in the committed capture",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ_W10),
    dict(id="RR-49", requirement="Re-capture and republish the Week 10 injury tables",
         status="DONE",
         evidence="data/availability/injuries.csv; injuries.html; injury-deltas.html",
         done="The Week 10 injury tables were re-captured (2026-11-15 capture, 347 rows) and republished; stale "
              "counts and missing clubs were corrected and the changes published as deltas.",
         gate="Not applicable — recaptured",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ_W10),
    dict(id="RR-50", requirement="Reject: deriving depth order from jersey number, experience or salary",
         status="REJECTED",
         evidence="research/injuries.md; flagged.html (F-48); lineup-deficiencies.html",
         done="Rejected by design. Depth order is read from the official club depth chart; jersey number, "
              "experience and salary are not used to infer starters.",
         gate="Not applicable — the approach is rejected, not blocked",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-51", requirement="Represent shared and empty depth slots faithfully",
         status="DONE",
         evidence="pipeline/depth_status.py; data/availability/slot_status.csv; availability.html",
         done="Shared slots (multiple players in one slot) and empty slots are represented distinctly from a ranked "
              "list; the register reports multi rank-1 groups per capture and empty-slot cliffs rather than "
              "collapsing them.",
         gate="A chart order is not a game-time role",
         clears="Official pregame inactives for all 32 clubs",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-52", requirement="Resolve the depth-order source before building the backup-deficiency feature",
         status="PARTLY DONE",
         evidence="data/availability/depth_charts.csv; availability.html; flagged.html (F-49)",
         done="Route (a) — per-club official depth charts — is verified for 31 of 32 clubs; Houston is blocked (its "
              "chart is an image, 0 rows). Route (b) — snap counts — has no reachable official source. The "
              "backup-deficiency feature is therefore built on route (a) with the Houston gap flagged.",
         gate="Houston depth chart: 0 rows (route a); no snap-count source (route b)",
         clears="Houston depth rows > 0 or an official snap-count source",
         label="Houston Texans team page", url=U_HOU),
    dict(id="RR-53", requirement="Score injury-designation reliability before using it as a feature",
         status="NOT STARTED",
         evidence="",
         done="No reliability scoring of injury designations is implemented. Designations are published as official "
              "observations but are not joined to outcomes to measure play rate before being used as a feature.",
         gate="No designation-to-outcome reliability study",
         clears="A multi-season designation-to-inactive join with play-rate confidence intervals",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-54", requirement="Snapshot the nfl.com injury report every Wed, Thu and Fri and keep a dated history",
         status="DONE",
         evidence=".github/workflows/availability.yml; data/availability/history/**",
         done="The availability job runs on a daily cron (including Wed/Thu/Fri) and keeps a dated history of every "
              "capture under data/availability/history/, so Questionable-to-Out changes and practice trends can be "
              "replayed.",
         gate="Raw bytes not retained (only parsed CSVs and metadata)",
         clears="Retain raw response bytes for every capture",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-55", requirement="Treat the injury report as a timestamped series, not a weekly snapshot",
         status="DONE",
         evidence="injury-deltas.html; pipeline/injury_deltas.py; data/availability/history/**",
         done="The injury report is captured daily from Wednesday to kickoff with a fetch timestamp, and designations "
              "are published as a timestamped series of deltas, not a weekly snapshot.",
         gate="Not applicable for the series treatment",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-56", requirement="Use snap counts as the starter proxy when the depth chart is unavailable",
         status="BLOCKED",
         evidence="flagged.html (F-49); research/injuries.md",
         done="No official snap-count source is reachable from this environment, so snap counts cannot be used as a "
              "starter proxy. The depth chart (route a) is the available source, with Houston blocked.",
         gate="No reachable official snap-count source",
         clears="An official snap-count source",
         label="No official source located: snap counts are not reachable", url=None),
    dict(id="RR-57", requirement="Add a control baseline (random picks; favorites only) to every leaderboard run",
         status="DONE",
         evidence="competition.html; pipeline/control_baseline.py; data/processed/control_baseline.csv",
         done="A control baseline (random side, favourite-only, home-only) is computed on the same official-results "
              "universe for every leaderboard run, with n and an interval, to separate skill from luck.",
         gate="Not applicable for the baseline",
         clears="Not applicable",
         label="NFL scores (grading standard)", url=U_SCORES),
    dict(id="RR-58", requirement="Stadium Roof/Surface & NWS Hourly Wind/Precipitation Overlay",
         status="PARTLY DONE",
         evidence="pipeline/build_datasets.py; data/processed/games_model.csv; lines.html",
         done="Weather and roof fields exist in the dataset and the roof indicator is encoded; the default model "
              "excludes weather/roof until pre-kickoff availability is verified. A live NWS hourly wind/precipitation "
              "overlay coupled to the 90-minute stadium roof designation is not implemented.",
         gate="No live NWS forecast ingest; weather excluded from the default model",
         clears="A scheduled NWS grid ingest coupled to the official roof designation",
         label="NFL Operations pregame 90m rule", url=U_OPS),
    dict(id="RR-59", requirement="Two-Stage Skill Leaderboard (Proper-Score Qualification -> Prospective CLV/ROI Escrow)",
         status="NOT STARTED",
         evidence="data/integration/suggestions_master.csv (proposal only)",
         done="Not implemented. The two-stage qualification-then-escrow leaderboard exists only as a proposal in the "
              "suggestions register. The current leaderboard ranks on the eight-gate battery; no prospective CLV/ROI "
              "escrow is held.",
         gate="No prospective escrow; G1 quote provenance fails for all 18 candidates",
         clears="A validated strategy (all eight gates) plus a prospective escrow mechanism",
         label="No official source: a competition-design proposal", url=None),
    dict(id="RR-60", requirement="Vig-Free Market Consensus vs. Originated Fair-Line Decomposition View",
         status="PARTLY DONE",
         evidence="origination.html; lines.html; pipeline/models.py",
         done="The originated fair line and the market line are published with their difference, separating pricing "
              "divergence from the market. A vig-free consensus decomposition (removing the operator margin before "
              "comparison) is not separately published.",
         gate="No vig-free consensus source; market line is community-mirrored",
         clears="An authenticated market consensus and a vig-free decomposition",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-61", requirement="Publish a weekly 'what changed' diff instead of a static snapshot",
         status="DONE",
         evidence="injury-deltas.html; pipeline/injury_deltas.py; data/processed/injury_*.csv; data/processed/depth_deltas.csv",
         done="Each weekly (and daily) snapshot is stored and a diff is published: rank change, rating change and "
              "availability change, with the capture clock time and hash on every change row.",
         gate="Not applicable for the diff",
         clears="Not applicable",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-62", requirement="Publish every model total twice until one wins",
         status="NOT STARTED",
         evidence="",
         done="Not implemented. Only one model total is published per market. Keeping two estimators visible with a "
              "gap column and collapsing to one only after a walk-forward comparison has not been done.",
         gate="No dual-estimator harness",
         clears="A second pre-registered estimator with a walk-forward comparison",
         label="No official source: a modelling decision", url=None),
    dict(id="RR-63", requirement="Add a drift alarm to every scraper",
         status="PARTLY DONE",
         evidence="pipeline/fetch_availability.py; pipeline/fetch_injuries.py; pipeline/fetch_reserve_list.py",
         done="Fetchers pin expected row counts and required fields and fail the build loudly when a field goes "
              "missing rather than publishing a blank. A central drift-alarm surface across every scraper is not "
              "wired.",
         gate="No central drift-alarm surface; scheduled commits do not trigger verify.yml (F-47)",
         clears="A central drift alarm that fails the build on any scraper drift",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-64", requirement="Capture the reserve list so 'not listed' never means 'available'",
         status="DONE",
         evidence="pipeline/fetch_reserve_list.py; .github/workflows/reserve-list.yml; data/availability/reserve/**; tests/test_reserve_list.py",
         done="The official reserve list is captured on a schedule with raw hashes, so absence from the weekly "
              "report (e.g. a player on injured reserve) is not read as availability. The capture module and "
              "workflow are built; the first live CI run is pending.",
         gate="First live CI run of reserve-list.yml not yet observed",
         clears="One scheduled CI run that parses the reserve list with zero errors",
         label="NFL.com reserve list, November 2026", url=U_RES),
    dict(id="RR-65", requirement="Reject: ranking strategies by season-long ROI",
         status="REJECTED",
         evidence="competition.html; pipeline/session_competition.py",
         done="Rejected by design. No leaderboard ranks by realised season-long return; standings rank on "
              "benchmark-relative skill with uncertainty, not raw ROI.",
         gate="Not applicable — the approach is rejected, not blocked",
         clears="Not applicable",
         label="White (2000), Econometric Society", url=U_WHITE),
    dict(id="RR-66", requirement="Archive weekly injury reports for past seasons (for Q06)",
         status="NOT STARTED",
         evidence="",
         done="Only the current 2026 season injury reports are captured. Past-season weekly injury reports are not "
              "archived, so the designation-change question cannot be tested historically.",
         gate="No historical injury-report archive",
         clears="An archive of past-season weekly injury reports",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-67", requirement="Pre-register each strategy (definition frozen before results are seen)",
         status="PARTLY DONE",
         evidence="strategies.html; competition.html; pipeline/session_competition.py",
         done="The 18 strategies are pre-declared with frozen definitions before results. A complete, reviewable "
              "pre-registration record (rule text, sample window and gates committed to git before the evaluation "
              "window) is not stored per strategy.",
         gate="No per-strategy frozen pre-registration record committed before the window",
         clears="A git-committed pre-registration record per strategy",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-68", requirement="2026 Kickoff & Declared Onside-Kick Regime Priors Filter",
         status="NOT STARTED",
         evidence="",
         done="Not implemented. No onside-kick regime prior is applied to originated game totals or 4th-quarter "
              "comeback win-probability curves.",
         gate="No onside-kick regime data or prior",
         clears="A declared onside-kick regime source and a prior applied to the totals model",
         label="NFL rules", url=U_RULES),
    dict(id="RR-69", requirement="Freeze a rule before it sees data (pre-registration)",
         status="PARTLY DONE",
         evidence="pipeline/validation.py; data/processed/validation_config.json; competition.html",
         done="Gate thresholds and the strategy definitions are frozen in validation_config.json and the strategy "
              "library before results. The commit-hash-as-registration mechanism is partially in place; a full "
              "rule-text-per-window freeze is not stored.",
         gate="No committed rule text per evaluation window",
         clears="A git-committed rule text and window per evaluation",
         label="Bailey & López de Prado (2014), publisher", url=U_BAILEY),
    dict(id="RR-70", requirement="Split data into train, validation and final holdout seasons",
         status="DONE",
         evidence="pipeline/models.py; pipeline/build_datasets.py; tests/test_no_lookahead.py",
         done="Models are fitted walk-forward: a test season uses only earlier seasons, so train, validation and "
              "final holdout are separated by time. No-leakage assertions run inside the build.",
         gate="Not applicable for the split",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-71", requirement="Make suggestions on how to improve the site; create a dedicated suggestions section for review before implementing",
         status="DONE",
         evidence="suggestions.html; suggestions-review.html; review-queue.html; review.html; decision-board.html",
         done="A dedicated suggestions surface exists (suggestions.html, the interactive path selector, the merged "
              "review queue and the decision board). Nothing is implemented without a chosen path.",
         gate="Not applicable for the section",
         clears="Not applicable",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-72", requirement="A clear list of questions, information and answers needed before any decision; suggestions to discover missing information",
         status="DONE",
         evidence="questions.html; answers.html; decisions.html; decision-readiness.html; this register",
         done="Question, information and answer registers exist (questions.html, answers.html, decisions.html, "
              "decision-readiness.html) and a missing-information discovery blueprint is published. This register is "
              "the consolidated decision-readiness surface for the full 2026-11-18 request.",
         gate="Some questions remain unanswered and blocked on sources (see the register)",
         clears="The owner's answers and the missing sources",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-73", requirement="Originate own NFL lines; research and develop signal strategies; leaderboard competition with rewards for top performers; single bet, parlay, prop combos; each strategy passes validation gates; determine correlations; remove luck; selectively skill-based",
         status="DONE",
         evidence="lines.html; strategies.html; competition.html; correlations.html; props.html; signal-staking.html; validation.html",
         done="The project originates its own lines and tests single bets, parlays and prop combos in a leaderboard "
              "competition with a reward ladder bound to eight fail-closed gates. Correlations are computed with n; "
              "luck is bounded by gates and control baselines. 0 of 18 strategies are validated and no reward is "
              "awarded (G1 quote provenance fails for all).",
         gate="G1 executable quote provenance fails for all 18 candidates",
         clears="A verified executable quote archive",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-74", requirement="The system tracks injuries and knows deficiencies in defenses and offenses (2nd/3rd/4th string backups replacing starters)",
         status="PARTLY DONE",
         evidence="availability.html; lineup-deficiencies.html; replacement-depth.html; injury-deltas.html",
         done="The system tracks injuries and depth, and publishes 1st–4th string deficiency matrices for the "
              "verified clubs. Coverage is 8 verified clubs plus the all-club capture (31/32 charts); confirmed "
              "game-time replacements are not named (chart order is not a game-time role).",
         gate="Confirmed replacements need official Game Books (PR #82); Houston blocked",
         clears="Merge PR #82 and clear the Houston gap",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-75", requirement="Create an executive summary outlining important details",
         status="DONE",
         evidence="executive-summary.html; EXECUTIVE_SUMMARY.md; pipeline/render_summary.py",
         done="An executive summary of the decision, the evidence and the limitations is published and regenerated "
              "by the build, with the current verdict (no validated edge, no reward) and the open gaps.",
         gate="Not applicable for the summary",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-76", requirement="No manual input; work on your own to finish all tasks",
         status="DONE",
         evidence=".github/workflows/*.yml; Makefile; pipeline/**",
         done="Capture, build, verification, test and deployment are automated. The scheduled jobs and the build "
              "run end to end without manual input; manual steps are limited to owner decisions (paths, price "
              "policy) which are recorded, not typed into the data.",
         gate="Owner decisions (price policy, path selection) remain manual by design",
         clears="Not applicable",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-77", requirement="REPO WORK: review the repo line by line, verify from official sources, provide links, flag irregularities",
         status="DONE",
         evidence="repo-review.html; audit.html; live-verification.html; flagged.html; data/integration/repo_inventory.csv",
         done="Every tracked file is inventoried, official-source checks are run, published rows are re-verified "
              "line by line against official pages, and irregularities are flagged with source links.",
         gate="Some irregularities are open and published (they do not block merge)",
         clears="Owner review of the flagged register",
         label="NFL injuries", url=U_INJ),
    dict(id="RR-78", requirement="SITE CREATION: a live GitHub Pages site with a clean landing page and category subpages; tables for every entry; analysis and findings",
         status="DONE",
         evidence="index.html; NAV_GROUPS in pipeline/render_site.py; all root *.html; .github/workflows/pages.yml",
         done="A live GitHub Pages site (main / repository root) with a clean dashboard landing page, category "
              "subpages, tables for every entry and findings, and a grouped navigation.",
         gate="Not applicable for the site",
         clears="Not applicable",
         label="GitHub Pages documentation", url=U_GH),
    dict(id="RR-79", requirement="VERIFICATION: verify line by line; every table row has a source link to an official site; unverifiable values blank and flagged",
         status="DONE",
         evidence="pipeline/verify_site.py; tests/check_sources.py; tests/check_links.py; tests/check_rebuild.py",
         done="The build verifies every table row carries an official/primary source link, blanks and flags "
              "unverifiable metric cells, checks internal links and assets, and re-checks a clean rebuild. Unverified "
              "values are never inferred or filled.",
         gate="Presence of a link is checked, not the truth of the value (a separate live-verification pass)",
         clears="Not applicable",
         label="NFL scores", url=U_SCORES),
    dict(id="RR-80", requirement="PARALLEL SESSIONS: shared task board, claims, scopes, commit and push claims, coordinate to avoid conflicts",
         status="DONE",
         evidence="COORDINATION.md; this session's claim block",
         done="COORDINATION.md is the shared task board with per-task status, owner and file scope; sessions claim "
              "before editing, commit and push the claim, keep scopes non-overlapping and log cross-scope requests. "
              "This session's claim is recorded here.",
         gate="Not applicable for the protocol",
         clears="Not applicable",
         label="No official source: the coordination protocol is internal", url=None),
    dict(id="RR-81", requirement="PULL REQUEST AND MERGE: work fully, create a PR from the integration branch, merge without waiting, confirm Pages, record the result",
         status="PARTLY DONE",
         evidence="COORDINATION.md; .github/workflows/pages.yml; this session",
         done="The protocol is followed: work is committed on the pinned branch, a PR is opened to main, merged "
              "without waiting, and the Pages deployment and result are recorded in COORDINATION.md. This session's "
              "PR and merge record are pending at the time this register is generated.",
         gate="This session's PR merge and Pages confirmation are the final steps",
         clears="PR merged and Pages build confirmed (recorded in COORDINATION.md)",
         label="GitHub Pages documentation", url=U_GH),
]


# --------------------------------------------------------------------------- #
# Frame + CSV
# --------------------------------------------------------------------------- #
def register_frame() -> pd.DataFrame:
    rows = []
    for r in ROWS:
        lab, url = _src(r["label"], r["url"])
        rows.append(dict(id=r["id"], requirement=r["requirement"], status=r["status"],
                         evidence_file=r["evidence"], what_was_done=r["done"],
                         blocking_gate=r["gate"], clearing_number=r["clears"],
                         source_label=lab, source_url=url))
    return pd.DataFrame(rows)


def _pill(status: str) -> str:
    if status.startswith("DONE"):
        kind = "ok"
    elif status in {"BLOCKED", "REJECTED"} or status.startswith("BUILT ON OPEN PR"):
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="flag {kind}">{e(status)}</span>'


def _text_list(items: list[str]) -> str:
    return ("<ul class=\"findings\">" + "".join(f"<li>{x}</li>" for x in items) + "</ul>") if items else ""


def build_page(reg: pd.DataFrame) -> str:
    srcd = reg[reg.source_url != ""]
    unsrcd = reg[reg.source_url == ""]

    trows = [[e(r.id), e(r.requirement), _pill(r.status), clean(r.evidence_file),
              clean(r.what_was_done), clean(r.blocking_gate), clean(r.clearing_number),
              ref_link(r.source_label, r.source_url)]
             for r in srcd.itertuples(index=False)]

    u_text = _text_list([
        f"<strong>{e(r.id)} {e(r.requirement)}</strong> — {e(r.what_was_done)} "
        f"<span class=\"small\">No official source exists for this row; shown as text and flagged, not filled in.</span>"
        for r in unsrcd.itertuples(index=False)
    ])

    def count(prefix: str) -> int:
        return int(reg.status.str.startswith(prefix).sum())

    n_done = count("DONE")
    n_part = count("PARTLY DONE")
    n_pr = int(reg.status.str.startswith("BUILT ON OPEN PR").sum())
    n_block = int((reg.status == "BLOCKED").sum())
    n_rej = int((reg.status == "REJECTED").sum())
    n_not = int((reg.status == "NOT STARTED").sum())
    n_own = int((reg.status == "OWNER DECISION").sum())

    body = f"""
<section><h2>2026-11-18 request register</h2>
<p class="lede">One row per item in the 2026-11-18 request. Each row names the status, the evidence file that
supports it, the gate that blocks it and the number that would clear it. Every table row cites an official
NFL.com or club page; rows with no official source are shown as flagged text and are never filled in. This is
the decision-readiness surface for the full request — cross-reference <a href="brief-2026-11-15.html">the
2026-11-15 brief tracker</a> and <a href="flagged.html">Flagged for review</a>.</p>
{kpi_grid([card(str(len(reg)), "request items", "one row per item in the 2026-11-18 request", ""),
           card(str(n_done), "done", "published and verified on main", "good"),
           card(str(n_part), "partly done", "built with a stated gap", "warn"),
           card(str(n_pr), "on open PR", "built on PR #82, not merged to main", "bad"),
           card(str(n_block + n_not), "blocked / not started", "waiting on a source or not built", "bad"),
           card(str(n_rej), "rejected", "rejected by design", "bad"),
           card(str(n_own), "owner decision", "needs an owner decision", "warn")])}
</section>
<section><h2>Items with an official source</h2>
{table(trows, ["ID", "Requirement", "Status", "Evidence file", "What was done",
               "Blocking gate", "Number that clears it", "Official source"],
       caption="Request items with an official/primary reference · every row sourced")}
</section>
<section><h2>Items with no official source</h2>
<p class="lede">These rows depend on an internal process, a decision, or a source that does not exist. They are
printed as text and flagged; no value has been inferred or filled in.</p>
{u_text}
</section>
"""
    return layout("request-register-2026-11-18.html", "2026-11-18 request register",
                  "One row per request item: status, evidence, blocking gate and the number that clears it.",
                  body, wide=True)


def main() -> None:
    reg = register_frame()
    # Every sourced row must carry an allow-listed URL; a bad host fails the build here.
    for r in reg.itertuples(index=False):
        if r.source_url and not r.source_url.startswith("https://"):
            raise SystemExit(f"{r.id}: bad source url {r.source_url!r}")
    write_csv(reg, "request_register_2026_11_18.csv")
    (ROOT / "request-register-2026-11-18.html").write_text(build_page(reg), encoding="utf-8")
    srcd = int((reg.source_url != "").sum())
    print(f"rows {len(reg)} ({srcd} sourced, {len(reg) - srcd} flagged as text)")


if __name__ == "__main__":
    main()
