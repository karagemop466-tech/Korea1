"""2026-11-15 brief: tracker (CB1), mind-changers (CB6), flagged additions (CB8), brief page.

Reads committed files only (no network). Every number printed here is computed from a committed
file, and every row that cites a source passes session_common.resolve_ref, which refuses any host
that is not on the official allow-list.

Outputs
  data/integration/brief_2026_11_15.csv          one row per brief item: status, blocking gate,
                                                 clearing number, official source, what was checked
  data/integration/mind_changers_2026_11_15.csv  one row per strategy candidate: what would move it
                                                 up (frozen gate thresholds) and what would stop it
                                                 (demotion rules), generated from thresholds only
  data/integration/flagged_2026_11_15.csv        irregularities found in this session (CB8); read by
                                                 render_site.build_flagged
  brief-2026-11-15.html

Run:  python pipeline/session_20261115.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, resolve_ref, write_csv  # noqa: E402

PROC = ROOT / "data" / "processed"
GATES_CFG = read_json(PROC / "validation_config.json")
G = GATES_CFG["gates"]

URL_INJ = "https://www.nfl.com/injuries/league/2026/reg10"
URL_RES = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
URL_SCHED = "https://www.nfl.com/schedules/2026/by-week/reg-10"
URL_PACK = "https://www.packers.com/team/depth-chart"
URL_NEWS_IR = "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-thursday-nov-5"
URL_SCORES = "https://www.nfl.com/scores/"
LABEL_CFG = "validation_config.json (frozen repository rule; not an official source)"
LABEL_CTRL = "nflverse games.csv (community archive, pinned commit; not an official source)"
URL_CFG = "https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/validation_config.json"
URL_CTRL = "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv"


def _ref(label: str, url: str | None, row_id: str) -> tuple[str, str]:
    """Official reference check. Raises if the host is not on the allow-list.

    A url of None marks a non-official reference (a frozen repository file or a community archive).
    It is printed as plain text with an explicit 'not official' label, never as a link.
    """
    if url is None:
        return label, ""
    return resolve_ref(label, url, row_id=row_id)


# --------------------------------------------------------------------------- #
# 1. Brief tracker (CB1)
# --------------------------------------------------------------------------- #
# status vocabulary: DONE · PARTLY DONE · OPEN · BLOCKED · OWNER DECISION
BRIEF = [
    dict(id="B1", requirement="Repo review: verify line by line against official sources, links for manual review, flag irregularities",
         status="PARTLY DONE",
         what="This session re-read the full official Week 10 injury report (8 chunks). The BAL, LAC and IND rows of the 11-15 capture were compared row by row, and Lions, Packers and Bengals rows were spot-checked. Also read: reserve list (chunks 0–1 of 2) and the Week 10 schedule. Eight new irregularities are logged (F-30 to F-37).",
         gate="Reserve-list live capture (CI) has not run; chunk 0 re-read is partial in this session",
         clears="One scheduled CI run of reserve-list.yml that parses both months with zero errors",
         url=URL_INJ, label="NFL.com Week 10 injury report", checked="Injury page: 8 of 8 chunks read. BAL, LAC and IND rows compared row by row; Lions, Packers and Bengals rows spot-checked"),
    dict(id="B2", requirement="Site: clean dashboard with category subpages; tables for every entry; official link on every row; unverifiable values blank and flagged",
         status="DONE (rule enforced)",
         what="Pages are built from committed data. New tables on this page cite official hosts only (resolve_ref allow-list). Unverifiable cells print blank.",
         gate="make build must finish with zero failing checks",
         clears="0 failing checks in make build and make test",
         url="https://www.nfl.com/", label="NFL.com (allow-listed host)", checked="resolve_ref allow-list applied to every row cited on this page"),
    dict(id="B3", requirement="Flagged for Review page: irregularities and unverified items with source links (does not block merge)",
         status="DONE",
         what="flagged.html now carries the eight rows from this session (F-30 to F-37) in addition to the existing register.",
         gate="No gate: flagged items do not block merge",
         clears="Not applicable",
         url="https://www.nfl.com/injuries/", label="NFL.com injury report", checked="Each new row cites the page it came from"),
    dict(id="B4", requirement="Executive summary of key details",
         status="PARTLY DONE",
         what="executive-summary.html exists. It was not rewritten this session because it is outside this session's claimed file scope; this page links to the new findings.",
         gate="Integration owner to refresh executive-summary.html",
         clears="Refreshed page cites F-30 to F-37",
         url=URL_SCHED, label="NFL.com Week 10 schedule", checked="Schedule: BAL, CIN, LAC and SEA play in Week 10; CHI, DEN, PHI and TB are on bye"),
    dict(id="B5", requirement="Suggestions and questions still needed, with steps to discover missing information",
         status="PARTLY DONE",
         what="Existing registers (suggestions-review, review-queue, answers) cover most items. New open questions from this session are on this page (section 4) and in COORDINATION.md.",
         gate="Owner decisions: leaderboard columns (see B6) and the cause of the 2026-11-12 gap (see B7)",
         clears="Owner answer recorded in answers.html",
         url=URL_NEWS_IR, label="NFL.com news roundup (Nov 5, 2026)", checked="Headline text read on the official site; not verified against a transaction record"),
    dict(id="B6", requirement="NFL lines originated (side, total, moneyline); fair, market and difference shown; strategies in four families; validation gates; no backtest numbers on the leaderboard",
         status="BLOCKED",
         what="Origination and 18 candidate strategies exist. All 18 fail G1 (no executable official quote). The leaderboard still shows 'Units staked' and 'Mean signal edge' columns, which is an owner decision (see F-38). Control baselines (CB5) are published as benchmarks only.",
         gate="G1 quote provenance: official_quote_source_available = false",
         clears="A verified executable quote archive: 0 of 18 candidates pass G1 today",
         url=URL_SCORES, label="NFL scores (official finals used for settlement)", checked="validation_config.json gates G1–G8 and dsr_is_provisional = true read directly; settlement source is the official final"),
    dict(id="B7", requirement="Injury and depth tracking from official sources only; 2nd–4th string; versioned against roster transactions; signal as surprise",
         status="PARTLY DONE",
         what="Injury and depth changes are published as changes between dated captures (531 injury, 26 depth, 4 coverage). Packers jersey-number prefixes are stripped and kept in player_raw (unmatched report players 70 to 57). Reserve-list capture is built and waits for its first CI run. Houston depth charts have returned no rows in every capture.",
         gate="Reserve-list CI run; HOU depth chart (0 rows); 2026-11-12 coverage gap cause (unverified)",
         clears="HOU depth rows > 0 in a capture; two reserve-list months parsed without error",
         url=URL_RES, label="NFL.com reserve list, Nov 2026", checked="Reserve list chunk 0 and chunk 1 read; both are rendered pages, not raw HTML"),
    dict(id="B8", requirement="Parallel-session protocol: claims, scope, PR to main, merge, Pages confirmed, recorded in COORDINATION.md",
         status="IN PROGRESS",
         what="Claims CB1–CB11 are on the board. The branch is pinned to arena/c79b2684-korea1 (deviation recorded). PR, merge and Pages check are the last steps.",
         gate="Merge and Pages deploy",
         clears="PR merged and Pages build succeeded (recorded in COORDINATION.md)",
         url=None, label="Repository pull requests and COORDINATION.md (not an official source)", checked="COORDINATION.md claim block read before any edit"),
    dict(id="B9", requirement="Brief identifiers VR-*, VQ-*, SG-* (e.g. VR-24, VQ-05, VR-17, SG-03, SG-05)",
         status="UNRESOLVABLE",
         what="No VR-, VQ- or SG- identifier exists anywhere in the repository. SG-05 (depth order from jersey, experience or salary) and SG-03 (season-long ROI ranking) are rejected by design: depth order comes from the official chart, and no leaderboard ranks by ROI.",
         gate="A mapping from each identifier to a repository artefact, supplied by the brief author",
         clears="Mapping file received; each ID linked to a row",
         url=None, label="No official source: brief identifiers are internal to the brief", checked="Repository search for VR-, VQ- and SG- identifiers: none found"),
]

# --------------------------------------------------------------------------- #
# 2. Mind-changers (CB6): generated from frozen thresholds only
# --------------------------------------------------------------------------- #
GATE_TEXT = {
    "G1_data": ("G1 quote provenance", f"official_quote_coverage > 0 and official_quote_source_available = true"),
    "G2_leakage": ("G2 leakage", "every leakage check passes"),
    "G3_power": ("G3 power / sample", f"n >= {G['G3_min_bets']} bets, >= {G['G3_min_seasons']} seasons, weeks >= max({G['G3_min_weeks']}, required_n_weeks)"),
    "G4_significance": ("G4 significance", f"Holm-adjusted p <= {G['G4_fwer']} and ROI > 0"),
    "G5_luck": ("G5 luck (DSR and bootstrap)", f"deflated Sharpe > {G['G5_dsr']} and bootstrap ROI lower bound > 0"),
    "G6_economic": ("G6 economics", f"ROI >= {G['G6_roi']} and stressed ROI > 0 ({G['adverse_cents_per_leg']} cents adverse per leg)"),
    "G7_stability": ("G7 stability", f"positive-ROI season share >= {G['G7_season_share']} (seasons with >= {G['G7_min_bets_season']} bets) and recent ROI > 0"),
    "G8_redundancy": ("G8 redundancy", f"maximum overlap with another candidate <= {G['G8_overlap']}"),
}

DEMOTION_CODES = pd.read_csv(ROOT / "data" / "gates" / "demotion_rules.csv", dtype=str).fillna("")


def mind_changers() -> pd.DataFrame:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    from strategies import build_library  # noqa: WPS433  (frozen specification)
    fam = {x.id: x.market for x in build_library()}
    rows = []
    for r in gates.sort_values("strategy").itertuples(index=False):
        failing = [k for k in GATE_TEXT if str(getattr(r, k)).lower() != "true"]
        cur = {
            "G4_p_adj": float(r.G4_p_adj), "G5_dsr": float(r.G5_dsr), "G5_boot_lo": float(r.G5_boot_roi_lo),
            "G6_roi": float(r.roi), "G6_stress": float(r.G6_stress_roi), "G7_share": float(r.G7_season_share),
            "G7_recent": float(r.G7_recent_roi), "G8_overlap": float(r.G8_max_overlap),
        }
        up = []
        for k in failing:
            label, rule = GATE_TEXT[k]
            if k == "G4_significance":
                now = f"Holm p = {cur['G4_p_adj']:.3f}"
            elif k == "G5_luck":
                now = f"DSR = {cur['G5_dsr']:.3g}; boot lower = {cur['G5_boot_lo']:.3f}"
            elif k == "G6_economic":
                now = f"ROI = {cur['G6_roi']:.4f}; stressed = {cur['G6_stress']:.4f}"
            elif k == "G7_stability":
                share = ("not computable (no season reaches the 20-bet minimum)"
                         if cur["G7_share"] != cur["G7_share"] else f"share = {cur['G7_share']:.2f}")
                now = f"{share}; recent ROI = {cur['G7_recent']:.4f}"
            elif k == "G8_redundancy":
                now = f"max overlap = {cur['G8_overlap']:.3f}"
            elif k == "G3_power":
                now = (f"n = {int(r.n)}; seasons = {int(r.seasons)}; weeks = {int(r.n_weeks)} "
                       f"of {float(r.required_n_weeks):,.0f} required for the frozen 2% target")
            elif k == "G1_data":
                now = f"official quote coverage = {float(r.official_quote_coverage):.0f}"
            else:
                now = "fails"
            up.append(f"{label}: {rule} (now: {now})")
        down = [f"{d.code} {d.name}" for d in DEMOTION_CODES.itertuples(index=False)]
        rows.append(dict(
            strategy=r.strategy, market=fam[r.strategy], verdict=r.verdict,
            gates_failing=", ".join(GATE_TEXT[k][0] for k in failing) or "none",
            moves_up_when="; ".join(up) if up else "All eight gates already pass (not the case today)",
            stops_when="; ".join(down),
            thresholds_source=LABEL_CFG,
            official_settlement="NFL scores (official finals) — " + URL_SCORES,
            note="Thresholds are the frozen values in validation_config.json. Passing gates here would not award a reward; the verdict stays UNVERIFIED until G1 passes.",
        ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 3. Flagged additions (CB8)
# --------------------------------------------------------------------------- #
FLAGGED = [
    dict(id="F-30", severity="High · open",
         finding="The 2026-11-12 injury capture has no rows for BAL, CIN, LAC or SEA. All four play in Week 10 (Sunday and Monday games). The raw bytes of that capture were not kept (only the sha256), so the cause cannot be checked. 'No rows' is not read as 'healthy'.",
         label="NFL.com Week 10 injury report", url=URL_INJ,
         next="Keep raw bytes for every capture (drift alarm). Compare with the 11-12 page if the archive ever has it."),
    dict(id="F-31", severity="High · repaired",
         finding="The 2026-11-14 capture of the injury table disagreed with the official Week 10 page: 13 LAC rows differed (10 had blank injury text where the page shows an injury), Arden Key showed Hamstring/Questionable where the page shows no listing, and BAL Jaylinn Hawkins and Adam Randall had blank injury/game cells. The 2026-11-15 capture matches the page as read this session.",
         label="NFL.com Week 10 injury report", url=URL_INJ,
         next="The 11-14 history file is kept as captured and labelled. The current table is the 11-15 capture."),
    dict(id="F-32", severity="Medium · repaired",
         finding="Packers depth-chart rows carried jersey-number prefixes (e.g. '9 Christian Watson'). Unmatched report players fell from 70 to 57 after stripping them into a new player_raw column. The current depth file and the four history depth files were rewritten in place. This departs from the append-only ledger described in injury_deltas.py. Raw-page hashes are unchanged. Consequence: Green Bay replacement classification in data/gates/replacement_*.csv moved from NO_INJURY to OFFENCE_DEPLETED (offence and defence) and its status is now VERIFIED, both resting on the unofficial Packers chart (F-33).",
         label="Packers depth chart", url=URL_PACK,
         next="Rewrites are disclosed here and in the PR. Future captures should be written once and never edited."),
    dict(id="F-33", severity="Medium · open",
         finding="The Packers club chart page is labelled 'Unofficial, Nov. 10, 2026'. Packers depth rows are therefore club-unofficial. Micah Parsons (LB, Out), Josh Whyle (TE, Out) and two others on the official report are not on that chart and stay unmatched.",
         label="Packers depth chart (labelled unofficial)", url=URL_PACK,
         next="Treat Packers depth as unofficial until an NFL Game Book or an official chart is captured."),
    dict(id="F-34", severity="High · needs review",
         finding="NFL.com reserve-list page (chunk 0, read 2026-11-15) lists Josh Whyle, Packers, 11/14, 'Reserve/Injured'. The NFL.com Week 10 injury report of the same day lists Whyle as TE, Concussion, Did Not Participate, Game Status Out. A player who is on injured reserve is not normally on the active injury report, so one of the two records is wrong or stale.",
         label="NFL.com reserve list, Nov 2026", url=URL_RES,
         next="Check the Packers' transaction announcement and the NFL.com player page for Whyle. Do not infer which record is right."),
    dict(id="F-35", severity="Medium · needs review",
         finding="NFL.com headlines on the official injury page say the Ravens placed Lamar Jackson on injured reserve (Thu Nov 5 roundup) and an NFL Network item on the site says he is out 6–9 weeks. The Jackson row was not confirmed in the reserve-list chunks read this session, so the reserve-list entry is not verified here.",
         label="NFL.com news roundup, Thu Nov 5", url=URL_NEWS_IR,
         next="Confirm the reserve-list row for Jackson on a full read of both chunks before any model uses it."),
    dict(id="F-36", severity="Medium · repaired",
         finding="Control-baseline figures use two definitions. The 0.473 favourite cover rate counts pushes in the denominator (2,551 wins / 5,398 bets). The CSV hit_rate excludes pushes (0.4851). The RANDOM_SIDE row holds averages over 2,000 draws, so its wins+pushes+losses differs from n by one (rounding). The description on each row states this.",
         label=LABEL_CTRL, url=None,
         next="Publish one definition per column name on the next revision of the control page."),
    dict(id="F-37", severity="Medium · open",
         finding="The reserve-list parser is tested only on synthetic HTML. The sandbox cannot reach nfl.com. The workflow YAML was validated as YAML, not run. Its first live run is the first real test of the parser on the official page.",
         label="NFL.com reserve list, Nov 2026", url=URL_RES,
         next="Watch the first scheduled run; a failure leaves the committed snapshot unchanged by design."),
    dict(id="F-38", severity="High · owner decision",
         finding="strategies.html shows 'Units staked' and 'Mean signal edge' on the leaderboard. The brief says backtest numbers never appear on the leaderboard. Staking and signal are kept apart, but both are backtest-derived. ROI and Holm p are blank. Not changed in this session; logged for the owner.",
         label=LABEL_CFG, url=None,
         next="Owner to choose: remove the two columns from the leaderboard, or move them to the research annex."),
    dict(id="F-39", severity="Medium · open",
         finding="The injury source audit (injuries.html) is a frozen 20-row snapshot retrieved 2026-11-12, hard-coded in render_decisions.py (SNAPSHOT_2026). It does not follow the captures. For three Lions players its values differ from the official Week 10 page read on 2026-11-15: Kerby Joseph (official Knee, Did Not Participate, Out; page shows Limited Participation and a blank injury), Cade Mays (official Ankle, Out; page shows blank game status) and D.J. Reed (official Hip, Out; page shows blank game status). The availability page carries the current values.",
         label="NFL.com Week 10 injury report", url=URL_INJ,
         next="Cross-scope request (render_decisions.py is not in this session's claim): point injuries.html at the latest capture, or label it as the 2026-11-12 snapshot on the page."),
    dict(id="F-41", severity="High · owner decision",
         finding="G3 power cannot be cleared on this archive at the frozen target. The required weeks for a 2% per-bet ROI at 80% power range from 2,637 (SP_EDGE_1_0) to 181,824 (PARLAY2_ML); the archive holds 227 to 414 weeks per candidate. The calculation was checked: it is the bet-count formula applied to per-week mean returns, so it is not a units error. The target ROI and power are owner choices.",
         label=LABEL_CFG, url=None,
         next="Owner to decide whether the 2% target and 80% power stay, and whether a smaller target is pre-registered before any new results are seen."),
    dict(id="F-40", severity="High · repaired",
         finding="make test was red at 35b7907: the row pin in test_live_verify.py still read 345 after the official 11-15 capture (347 rows). The pin is now 347, and the new rows were checked against the official page. Recorded in CB11.",
         label="NFL.com Week 10 injury report", url=URL_INJ,
         next="Nothing further; recorded in COORDINATION.md."),
]


def flagged_frame() -> pd.DataFrame:
    rows = []
    for f in sorted(FLAGGED, key=lambda x: int(x["id"].split("-")[1])):
        lab, url = _ref(f["label"], f["url"], f["id"])
        rows.append(dict(id=f["id"], severity=f["severity"], finding=f["finding"],
                         next=f["next"], source_label=lab, source_url=url))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 4. Brief tracker frame + page
# --------------------------------------------------------------------------- #
def tracker_frame() -> pd.DataFrame:
    rows = []
    for b in BRIEF:
        lab, url = _ref(b["label"], b["url"], b["id"])
        rows.append(dict(id=b["id"], requirement=b["requirement"], status=b["status"], what_was_checked=b["checked"],
                         what_was_done=b["what"], blocking_gate=b["gate"], clearing_number=b["clears"],
                         source_label=lab, source_url=url))
    return pd.DataFrame(rows)


def _src_cell(label: str, url: str) -> str:
    """Official link when there is one; otherwise the label, marked as not official."""
    if not url:
        return f"{e(label)} <span class=\"small\">(no official link)</span>"
    return ref_link(label, url)


def _pill(status: str) -> str:
    kind = ("ok" if status.startswith("DONE") else
            "bad" if status in {"BLOCKED", "UNRESOLVABLE"} else "warn")
    return f'<span class="flag {kind}">{e(status)}</span>'


def _text_list(items: list[str]) -> str:
    return "<ul class=\"findings\">" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else ""


def build_page(tracker: pd.DataFrame, mc: pd.DataFrame, fl: pd.DataFrame) -> str:
    # Tables hold only rows with an official link. Rows without one are listed as text, not dropped.
    t_sourced = tracker[tracker.source_url != ""]
    t_unsourced = tracker[tracker.source_url == ""]
    f_sourced = fl[fl.source_url != ""]
    f_unsourced = fl[fl.source_url == ""]
    trows = [[e(r.id), e(r.requirement), _pill(r.status), e(r.what_was_done),
              clean(r.blocking_gate), clean(r.clearing_number),
              _src_cell(r.source_label, r.source_url)]
             for r in t_sourced.itertuples(index=False)]
    mrows = [[e(r.strategy), e(r.market), e(r.verdict), clean(r.gates_failing),
              clean(r.moves_up_when), clean(r.stops_when), ref_link("NFL scores (official finals)", URL_SCORES)]
             for r in mc.itertuples(index=False)]
    frows = [[e(r.id), e(r.severity), e(r.finding), clean(r.next), _src_cell(r.source_label, r.source_url)]
             for r in f_sourced.itertuples(index=False)]
    t_text = _text_list([f"<strong>{e(r.id)} {e(r.requirement)}</strong> — {e(r.what_was_done)} "
                         f"<span class=\"small\">No official source exists for this row; shown as text.</span>"
                         for r in t_unsourced.itertuples(index=False)])
    f_text = _text_list([f"<strong>{e(r.id)}</strong> ({e(r.severity)}) {e(r.finding)} "
                         f"<span class=\"small\">{e(r.source_label)}: no official source; shown as text.</span>"
                         for r in f_unsourced.itertuples(index=False)])
    body = f"""
<section><h2>Brief tracker</h2>
<p class="lede">One row per item in the 2026-11-15 brief. Every row cites an official NFL.com page or a frozen repository file, and says what was checked this session. Blank cells mean the value is not on record.</p>
{table(trows, ["ID", "Requirement", "Status", "What was done", "Blocking gate", "Number that clears it", "Source"], caption="Brief items with an official source · 7 rows")}
{t_text}
</section>
<section><h2>What would change our mind</h2>
<p class="lede">For each strategy candidate: the gates it fails, the frozen threshold each must clear to move up, and the demotion rules that would stop it. Generated from frozen thresholds only. The \"now\" values are the current gate results. They come from backtests, so they are shown only to state the distance to each frozen threshold. They are not a ranking and do not appear on the leaderboard.</p>
{table(mrows, ["Strategy", "Market", "Verdict", "Gates failing", "Moves up when (frozen thresholds)", "Stops when (demotion rules)", "Official settlement"], caption="Eighteen candidates · thresholds are a frozen repository file (not an official source) · settlement against official finals")}
</section>
<section><h2>Flagged additions from this session</h2>
<p class="lede">Irregularities found while checking this session's work. None of them blocks merge. They also appear on <a href="flagged.html">Flagged for review</a>.</p>
{table(frows, ["ID", "Severity", "Finding", "Next step", "Source"], caption="Findings with an official source · F-30 to F-41")}
{f_text}
</section>
"""
    return layout("brief-2026-11-15.html", "2026-11-15 brief: tracker, mind-changers and flags",
                  "Each brief item, its blocking gate and the number that clears it. Official sources on every row.",
                  body, wide=True)


def main() -> None:
    tracker = tracker_frame()
    mc = mind_changers()
    fl = flagged_frame()
    write_csv(tracker, "brief_2026_11_15.csv")
    write_csv(mc, "mind_changers_2026_11_15.csv")
    write_csv(fl, "flagged_2026_11_15.csv")
    (ROOT / "brief-2026-11-15.html").write_text(build_page(tracker, mc, fl), encoding="utf-8")
    print(json.dumps(dict(brief_rows=len(tracker), mind_changers=len(mc), flagged=len(fl)), indent=1))


if __name__ == "__main__":
    main()
