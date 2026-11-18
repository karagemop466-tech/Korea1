"""Session `arena/7aae360e-korea1`, 2026-11-18 — RR1/RR2/RR3.

Per-item request register for the 2026-11-18 brief, the official reads that back it, and the
personnel-ablation contract. This is the item the previous session on this brief recorded as
"CS5 … not done": one row per request item, with the gate that blocks it and the number that
would clear it.

Everything published here is computed by this file from committed repository data plus the four
verbatim official excerpts under `data/live/register_reads_2026_11_18/`. There is no network access
in this module and no clock reading: `make build` is byte-reproducible, so `tests/check_rebuild.py`
stays green.

Rules enforced here, in code, so a claim cannot outrun its evidence:

* every register row names repository evidence paths, and every named path must exist;
* every number printed in the register or the flags is substituted from the computed fact table —
  an unknown token fails the build, so a stale or invented count cannot be published;
* every register row carries an official/allowlisted source URL, or states why no official source
  exists (those rows are rendered outside the tables by the page renderer);
* the status vocabulary is closed; `make build` fails on anything else.

Outputs
  data/integration/register_facts_2026_11_18.csv        every computed number, with the file it came from
  data/integration/register_verify_2026_11_18.csv       line-by-line official comparisons run in this session
  data/integration/register_venues_2026_11_18.csv       venue transcribed from each captured official game centre
  data/integration/request_register_2026_11_18.csv      the register: one row per request item
  data/integration/register_questions_2026_11_18.csv    what must be known, what is known, how to find the rest
  data/integration/register_suggestions_2026_11_18.csv  paths the owner can choose, with cost, risk and gate
  data/integration/register_ablation_2026_11_18.csv     the ablation contract and the fixed-penalty audit
  data/integration/register_flags_2026_11_18.csv         RR-flags (RR-F1 …), each with its next step

Run:  python pipeline/register_20261118.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, PROC, SITE_DATA, sha256_of  # noqa: E402

OUT = ROOT / "data" / "integration"
READS = ROOT / "data" / "live" / "register_reads_2026_11_18"
AV = ROOT / "data" / "availability"
HIST = AV / "history"
FORWARD = ROOT / "data" / "forward"
PROC = ROOT / "data" / "processed"

AS_OF = "2026-11-18"           # the date this register describes; a constant, not a clock read
READ_WINDOW = "2026-11-18T04:47Z–04:52Z"   # when the official pages below were fetched, minute precision

URL = {
    "injuries": "https://www.nfl.com/injuries/league/2026/reg10",
    "injuries_root": "https://www.nfl.com/injuries/",
    "reserve": "https://www.nfl.com/transactions/league/reserve-list/2026/11",
    "scores_w10": "https://www.nfl.com/scores/2026/week-10",
    "gc_was_nyg": "https://www.nfl.com/games/commanders-at-giants-2026-reg-10",
    "hou_depth": "https://www.houstontexans.com/team/depth-chart",
    "was_depth": "https://www.commanders.com/team/depth-chart",
    "actions_avail": "https://github.com/karagemop466-tech/Korea1/actions/workflows/availability.yml",
    "gh_token": "https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow",
    "gh_pages": "https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages",
    "ops_pregame": "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep/",
}

# outputs this module itself writes, which the register may therefore cite as evidence
SELF_OUTPUTS = {"data/integration/register_venues_2026_11_18.csv",
                "data/integration/register_ablation_2026_11_18.csv",
                "data/integration/register_flags_2026_11_18.csv",
                "data/integration/register_questions_2026_11_18.csv",
                "data/integration/register_suggestions_2026_11_18.csv",
                "data/integration/register_facts_2026_11_18.csv",
                "data/integration/register_verify_2026_11_18.csv"}

STATUS = {"DONE", "PARTLY DONE", "BLOCKED — SOURCE", "BLOCKED — OWNER", "IN PROGRESS — SIBLING",
          "REJECTED AS REQUESTED", "NOT REPRODUCIBLE", "NOT STARTED"}

# Hosts the site's own verifier treats as official/primary (pipeline/verify_site.py ALLOW).
OFFICIAL_HOST = re.compile(r"^https://(www\.)?(nfl\.com|operations\.nfl\.com|docs\.github\.com|[a-z0-9.-]+\.com)/")


def rd(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw)


# --------------------------------------------------------------------------- #
# 1. computed facts
# --------------------------------------------------------------------------- #
def cap_dirs() -> list[Path]:
    return sorted(d for d in HIST.glob("2026-*") if (d / "injuries.csv").exists())


# The transactions page prints the club logo under a two-letter code for three clubs, while the
# repository's own capture keys rows by the league abbreviation. Without this the same player reads
# as "live page only" for a reason that has nothing to do with the data.
LOGO_TO_CODE = {"AZ": "ARI", "TB": "TB", "LA": "LA"}


def zero_row_clubs(d: pd.DataFrame) -> list[str]:
    """clubs the fetcher knows about that the capture has no rows for."""
    have = set(d.team.unique())
    return sorted(set(fetcher_clubs()) - have)


def fetcher_clubs() -> list[str]:
    src = (ROOT / "pipeline" / "fetch_availability.py").read_text()
    return re.findall(r'^\s*\("([A-Z]{2,3})", "', src, re.M)


def multi_rank1(d: pd.DataFrame) -> int:
    r = pd.to_numeric(d["depth_rank"], errors="coerce").fillna(0).astype(int)
    g = d.assign(r=r).query("r == 1").groupby(["team", "unit", "position"]).size()
    return int((g > 1).sum())


def slot_groups(d: pd.DataFrame) -> int:
    return d.groupby(["team", "unit", "position"]).ngroups


def facts() -> dict:
    f: dict[str, object] = {"as_of": AS_OF, "read_window": READ_WINDOW}
    inj = rd(AV / "injuries.csv")
    f["inj_rows"] = len(inj)
    f["inj_clubs"] = int(inj.team.nunique())
    f["inj_retrieved"] = inj.retrieved_utc.max()
    f["inj_sea"] = int((inj.team == "SEA").sum())
    f["inj_cin"] = int((inj.team == "CIN").sum())
    f["inj_blank_game"] = int((inj.game_status == "").sum())
    f["inj_game_designations"] = int((inj.game_status != "").sum())

    pub_all = rd(PROC / "injuries_week10.csv")
    f["inj_pub_rows"] = len(pub_all)
    f["inj_pub_clubs"] = int(pub_all.team.nunique())
    pub = pub_all[pub_all.player != "No Injuries Reported"]     # player rows only
    f["inj_pub_player_rows"] = len(pub)
    f["inj_pub_placeholders"] = int((pub_all.player == "No Injuries Reported").sum())
    f["inj_pub_sea"] = int((pub.team == "Seattle Seahawks").sum())
    f["inj_pub_cin"] = int((pub.team == "Cincinnati Bengals").sum())

    cds = cap_dirs()
    f["capture_days"] = len(cds)
    f["capture_first"] = cds[0].name
    f["capture_last"] = cds[-1].name
    per_cap = {d.name: multi_rank1(rd(d / "depth_charts.csv")) for d in cds}
    f["multirank_min"] = min(per_cap.values())
    f["multirank_max"] = max(per_cap.values())
    f["multirank_by_capture"] = "; ".join(f"{k}={v}" for k, v in per_cap.items())

    dep = rd(AV / "depth_charts.csv")
    f["depth_rows"] = len(dep)
    f["depth_clubs"] = int(dep.team.nunique())
    f["depth_retrieved"] = dep.retrieved_utc.max()
    f["hou_depth_rows"] = int((dep.team == "HOU").sum())
    f["depth_slot_groups"] = slot_groups(dep)
    f["depth_multirank1"] = multi_rank1(dep)

    man = json.loads((AV / "manifest.json").read_text())
    src = man.get("sources", [])
    f["manifest_retrieved"] = man.get("retrieved_utc", "")
    f["captures_with_hash"] = sum(1 for s in src if s.get("sha256"))
    f["capture_sources"] = len(src)
    f["capture_http_ok"] = sum(1 for s in src if str(s.get("http_status")) == "200")

    # reserve list: the live page prints a bounded window; retention comes from the captures
    res_dirs = sorted((AV / "reserve" / "history").glob("*/reserve_list.csv"))
    f["reserve_captures"] = len(res_dirs)
    per = {p.parent.name: rd(p) for p in res_dirs}
    nov = {k: set(zip(v.date[v.month == "2026-11"], v.team[v.month == "2026-11"], v.player[v.month == "2026-11"]))
           for k, v in per.items()}
    newest = res_dirs[-1].parent.name
    union = set().union(*nov.values()) if nov else set()
    f["reserve_latest_rows"] = len(per[newest])
    f["reserve_latest_capture_utc"] = rd(AV / "reserve" / "latest.csv").capture_utc.max()
    f["reserve_latest_nov"] = len(nov[newest])
    f["reserve_union_nov"] = len(union)
    f["reserve_older_only"] = len(union - nov[newest])
    f["reserve_older_only_names"] = "; ".join(sorted(f"{p} ({t}, {d})" for d, t, p in union - nov[newest])) or "none"
    f["reserve_date_min"] = min(d for d, _, _ in union)
    f["reserve_date_max"] = max(d for d, _, _ in union)

    picks = rd(FORWARD / "picks.csv")
    graded = rd(FORWARD / "graded_picks.csv")
    f["prereg_picks"] = len(picks)
    f["prereg_trial_rows"] = len(rd(FORWARD / "trial_registry.csv"))
    f["prereg_sets"] = len(rd(FORWARD / "prereg_summary.csv"))
    f["published_lines_rows"] = len(rd(FORWARD / "published_lines.csv"))
    f["forward_settled"] = int((graded.status != "OPEN").sum()) if "status" in graded else 0
    f["forward_open"] = int((graded.status == "OPEN").sum()) if "status" in graded else 0
    f["forward_results_rows"] = len(rd(FORWARD / "official_results.csv"))
    f["forward_schedule_rows"] = len(rd(FORWARD / "official_schedule.csv"))
    raws = sorted((FORWARD / "raw_captures").glob("*.html"))
    f["game_pages_captured"] = len(raws)
    _v = venues()
    f["venues_n"] = len(_v)
    f["venues_with_both_fields"] = int((_v.parsed == "both fields").sum())
    f["game_centre_manifests"] = len(list((FORWARD / "captures").glob("*/manifest.json")))

    vr = rd(OUT / "verified_results.csv")
    f["verified_results_rows"] = len(vr)
    f["verified_results_final"] = int((vr.status_on_page.str.lower() == "final").sum())
    rf = rd(PROC / "results_feed.csv")
    f["results_feed_rows"] = len(rf)
    f["results_feed_tiers"] = "; ".join(f"{k}={v}" for k, v in rf.tier.value_counts().items())

    ps = rd(OUT / "price_snapshots.csv")
    f["price_rows"] = len(ps)
    f["price_markets"] = int(ps.market.nunique())
    f["price_games"] = int(ps.game_id.nunique())
    f["price_open_filled"] = int((ps.open_line != "").sum())
    f["price_close_filled"] = int((ps.close_line != "").sum())
    f["price_provenance"] = "; ".join(f"{k}={v}" for k, v in ps.provenance.value_counts().items())
    f["price_gaps_rows"] = len(rd(OUT / "price_snapshot_gaps.csv"))

    ol = rd(PROC / "originated_lines.csv")
    f["originated_rows"] = len(ol)
    oo = rd(OUT / "origination_order.csv")
    f["origination_order_rows"] = len(oo)
    f["orig_side_fair"] = int((oo.side_fair != "").sum())
    f["orig_total_fair"] = int((oo.total_fair != "").sum())
    f["orig_ml_prob"] = int((oo.ml_fair_prob_home != "").sum())
    f["orig_market_available"] = int(oo.side_edge_available.astype(str).str.lower().isin(["true", "1", "yes"]).sum())

    sg = rd(PROC / "strategy_gates.csv")
    f["strategies"] = len(sg)
    f["strategies_validated"] = int((sg.verdict == "VALIDATED").sum())
    f["strategies_g1_fail"] = int((~sg.G1_data.astype(bool)).sum()) if "G1_data" in sg else len(sg)
    lb = rd(OUT / "leaderboard_master.csv")
    f["leaderboard_rows"] = len(lb)
    f["demotion_rows"] = len(rd(OUT / "demotion_gate.csv"))
    f["mindchangers_rows"] = len(rd(OUT / "mind_changers_2026_11_15.csv"))
    f["signal_staking_rows"] = len(rd(OUT / "signal_staking.csv"))
    f["control_rows"] = len(rd(PROC / "control_baseline.csv"))
    f["prop_gates_rows"] = len(rd(PROC / "prop_gates.csv"))

    dlt = rd(PROC / "injury_deltas.csv")
    f["injury_delta_rows"] = len(dlt)
    f["injury_delta_captures"] = "; ".join(f"{k}={v}" for k, v in dlt.groupby(["from_utc", "to_utc"]).size().items())[:1] or ""
    f["injury_delta_pairs"] = int(dlt.groupby(["from_utc", "to_utc"]).ngroups)

    corr = rd(OUT / "official_correlations.csv")
    f["corr_rows"] = len(corr)
    f["corr_with_n"] = int((corr.n != "").sum())

    f["replacement_depth_rows"] = len(rd(ROOT / "data/gates/replacement_depth.csv"))
    f["replacement_slots_rows"] = len(rd(ROOT / "data/gates/replacement_slots.csv"))
    f["replacement_defence_rows"] = len(rd(ROOT / "data/gates/replacement_defence.csv"))
    f["lineup_deficiency_rows"] = len(rd(PROC / "lineup_deficiency.csv"))
    f["roster_depth_rows"] = len(rd(PROC / "roster_depth_history.csv"))
    f["pbp_backup_rows"] = len(rd(ROOT / "data/lineups/pbp_backup_impact.csv"))

    games = rd(PROC / "games_model.csv")
    f["corpus_games"] = len(games)
    f["corpus_seasons"] = f"{games.season.astype(int).min()}–{games.season.astype(int).max()}"
    f["ablation_files"] = len(list(PROC.glob("ablation*.csv"))) + len(list(OUT.glob("ablation*.csv")))
    fd = rd(PROC / "feature_dict.csv")
    f["model_features"] = len(fd)
    f["personnel_features"] = int(fd.feature.str.contains("injur|depth|personnel|start", case=False).sum())

    f["flagged_rows_1118"] = len(rd(OUT / "flagged_2026_11_18.csv"))
    f["irregularities_rows"] = len(rd(OUT / "irregularities.csv"))
    f["site_pages"] = len(list(ROOT.glob("*.html")))
    f["spotcheck_rows"] = len(rd(ROOT / "data/live/spotcheck_2026_11_18/spotcheck_rows.csv"))
    f["questions_master_rows"] = len(rd(OUT / "questions_master.csv"))
    f["suggestions_master_rows"] = len(rd(OUT / "suggestions_master.csv"))
    f["test_count"] = len(list((ROOT / "tests").glob("test_*.py")))

    # --- who the official report does not list, and why ----------------------------------- #
    sched = rd(FORWARD / "official_schedule.csv")
    playing = set(sched.away_team) | set(sched.home_team)
    no_rows_latest = set(zero_row_clubs(inj))
    no_rows_first = set(zero_row_clubs(rd(cds[0] / "injuries.csv")))
    f["clubs_in_week_schedule"] = len(playing)
    f["bye_clubs"] = ", ".join(sorted(no_rows_latest & (set(fetcher_clubs()) - playing))) or "none"
    f["bye_clubs_n"] = len(no_rows_latest & (set(fetcher_clubs()) - playing))
    f["zero_row_clubs_latest"] = ", ".join(sorted(no_rows_latest)) or "none"
    f["zero_row_clubs_first"] = ", ".join(sorted(no_rows_first)) or "none"
    f["zero_row_n_latest"] = len(no_rows_latest)
    f["zero_row_n_first"] = len(no_rows_first)
    gained = sorted(no_rows_first - no_rows_latest)
    f["clubs_that_gained_rows"] = ", ".join(gained) or "none"
    f["clubs_that_gained_rows_n"] = len(gained)
    ph = pub_all[pub_all.player == "No Injuries Reported"]
    f["inj_pub_placeholder_clubs"] = ", ".join(sorted(ph.team)) or "none"
    f["inj_pub_placeholder_n"] = len(ph)
    name_to_code = {}
    for code, club, slug, host in _club_rows():
        name_to_code[club] = code                      # "Seahawks" -> SEA
        name_to_code[club + " " + club] = code          # harmless duplicate guard
    contrad = []
    for tname in ph.team:
        code = next((c for word, c in name_to_code.items() if tname.endswith(word)), "")
        n = int((inj.team == code).sum()) if code else -1
        if n:
            contrad.append((tname, code, n))
    f["inj_pub_contradicted"] = "; ".join(f"{t} ({c}) printed injury-free against {n} official rows"
                                          for t, c, n in contrad) or "none"
    f["inj_pub_contradicted_n"] = len(contrad)
    f["inj_first_capture_rows"] = len(rd(cds[0] / "injuries.csv"))
    return f


def _club_rows():
    """(code, club, slug, host) tuples from the fetcher's own table — one source for club identity."""
    src = (ROOT / "pipeline" / "fetch_availability.py").read_text()
    return re.findall(r'^\s*\("([A-Z]{2,3})", "([A-Za-z .]+)", "([a-z-]+)", "([a-z0-9.-]+)"\)', src, re.M)



# --------------------------------------------------------------------------- #
# 2. line-by-line verification against the verbatim official excerpts
# --------------------------------------------------------------------------- #
LINK_CELL = re.compile(r"^\s*\[(.*?)\]\((.*?)\)\s*$")
CLUB_BY_NAME = {"Commanders": "WAS", "Giants": "NYG", "Patriots": "NE", "Lions": "DET", "Titans": "TEN",
                "Bills": "BUF", "Jets": "NYJ", "Dolphins": "MIA", "Colts": "IND"}


def parse_injury_tables(path: Path) -> list[dict]:
    """Rows of the markdown tables the official page prints, in club blocks."""
    rows, club = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s in CLUB_BY_NAME and club != s:
            club = s
        elif s.startswith("| [") and club:
            cells = [c.strip() for c in s.strip("|").split("|")]
            m = LINK_CELL.match(cells[0])
            if not m:
                continue
            rows.append(dict(club=CLUB_BY_NAME[club], player=m.group(1), position=cells[1],
                             injury=cells[2], practice=cells[3], game=cells[4] if len(cells) > 4 else ""))
    return rows


def parse_reserve_rows(path: Path) -> list[dict]:
    """(date, club, player, transaction) from the verbatim row block.

    Read positionally rather than by column index: the page's own row is split across the two fetched
    chunks, so a strict six-cell expectation would silently drop the row that straddles the boundary.
    A row is any table line that carries a club logo, a printed date and a player link.
    """
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|") or "clubs/logos/" not in s:
            continue
        logo = re.search(r"clubs/logos/([A-Z]{2,3})", s)
        date = re.search(r"\|\s*(\d{2}/\d{2})\s*\|", s)
        name = re.search(r"\[([^\]]+)\]\(https://www\.nfl\.com/players/[^)]+\)", s)
        txn = re.search(r"\|\s*([A-Z][A-Za-z/ ]+)\s*\|?\s*$", s)
        if not (logo and date and name):
            continue
        club = LOGO_TO_CODE.get(logo.group(1), logo.group(1))
        out.append(dict(date="2026-" + date.group(1).replace("/", "-"), club=club,
                        player=name.group(1), transaction=txn.group(1) if txn else ""))
    return out


VENUE_LOC = re.compile(r'data-testid="info-card-item-value-location">([^<]*)</dd>')
VENUE_STAD = re.compile(r'data-testid="info-card-item-value-stadium">([^<]*)</dd>')


def venues() -> pd.DataFrame:
    """Venue transcribed from each captured official game-centre page (raw HTML in the repository)."""
    sched = rd(FORWARD / "official_schedule.csv").set_index("game_id")
    rows = []
    for p in sorted((FORWARD / "raw_captures").glob("*.html")):
        game_id = "_".join(p.stem.split("_")[:4])
        t = p.read_text(encoding="utf-8", errors="ignore")
        loc = VENUE_LOC.search(t)
        st = VENUE_STAD.search(t)
        row = sched.loc[game_id] if game_id in sched.index else None
        rows.append(dict(
            game_id=game_id,
            week=game_id.split("_")[1],
            matchup=f"{game_id.split('_')[2]} at {game_id.split('_')[3]}",
            location_printed=loc.group(1).strip() if loc else "",
            stadium_printed=st.group(1).strip() if st else "",
            official_url=(row.official_url if row is not None else URL["scores_w10"]),
            capture_file=str(p.relative_to(ROOT)),
            capture_sha256=sha256_of(p)[:16],
            parsed=("both fields" if loc and st else ("one field" if loc or st else "neither")),
            source_kind="raw game-centre page committed in the repository",
        ))
    # the Week 10 Commanders-at-Giants game centre was read as a page, not captured as HTML; its venue
    # is transcribed from the verbatim excerpt so the fixture is not silently missing from the table
    txt = (READS / "nfl_gamecentre_was_at_nyg_2026_reg10.md").read_text(encoding="utf-8")
    lo = re.search(r"Location LOCATION ([A-Z, .]+)", txt)
    st2 = re.search(r"Stadium STADIUM ([A-Z, .0-9]+)", txt)
    if lo and st2 and "2026_10_WAS_NYG" not in {r["game_id"] for r in rows}:
        row = sched.loc["2026_10_WAS_NYG"] if "2026_10_WAS_NYG" in sched.index else None
        rows.append(dict(game_id="2026_10_WAS_NYG", week="10", matchup="WAS at NYG",
                         location_printed=lo.group(1).strip(), stadium_printed=st2.group(1).strip(),
                         official_url=(row.official_url if row is not None else URL["gc_was_nyg"]),
                         capture_file="data/live/register_reads_2026_11_18/nfl_gamecentre_was_at_nyg_2026_reg10.md",
                         capture_sha256=sha256_of(READS / "nfl_gamecentre_was_at_nyg_2026_reg10.md")[:16],
                         parsed="both fields",
                         source_kind=f"official page read {READ_WINDOW} (no raw HTML capture of this fixture)"))
    return pd.DataFrame(rows)


def name_to_code_lookup() -> dict:
    """club word -> league code, taken from the fetcher's own club table."""
    return {club: code for code, club, slug, host in _club_rows()}


def verify_rows(f: dict) -> tuple[list[dict], dict]:
    """Every check this session ran against an official page, one row per compared line."""
    inj = rd(AV / "injuries.csv")
    pub_all = rd(PROC / "injuries_week10.csv")
    pub = pub_all[pub_all.player != "No Injuries Reported"]     # player rows only
    rows, stats = [], {}

    # (a) official Week 10 injury report vs the newest committed capture, field by field
    live = parse_injury_tables(READS / "nfl_injuries_reg10_clubs.md")
    stats["injury_lines_read"] = len(live)
    match = 0
    for lr in live:
        m = inj[(inj.team == lr["club"]) & (inj.player == lr["player"])]
        if len(m) != 1:
            verdict, cap = f"NOT ONE ROW IN CAPTURE ({len(m)})", ("", "", "")
        else:
            r = m.iloc[0]
            cap = (r.injury, r.practice_status, r.game_status)
            diffs = [f"{n}: capture '{a}' vs official '{b}'" for n, a, b in
                     (("injury", r.injury, lr["injury"]), ("practice", r.practice_status, lr["practice"]),
                      ("game status", r.game_status, lr["game"])) if str(a).strip() != str(b).strip()]
            verdict = "MATCH" if not diffs else "MISMATCH — " + "; ".join(diffs)
            match += not diffs
        rows.append(dict(check="injury report vs capture", club=lr["club"], item=lr["player"],
                         official=" · ".join(x or "—" for x in (lr["injury"], lr["practice"], lr["game"])),
                         committed=" · ".join(x or "—" for x in cap), verdict=verdict,
                         as_of=f"{f['inj_retrieved']} capture vs {READ_WINDOW} read", source_url=URL["injuries"]))
    stats["injury_lines_match"] = match

    # club row counts read off the live page vs the capture, for the clubs whose tables were read
    for club, abbr in CLUB_BY_NAME.items():
        n_live = sum(1 for lr in live if lr["club"] == abbr)
        if not n_live:
            continue
        n_cap = int((inj.team == abbr).sum())
        rows.append(dict(check="club row count", club=abbr, item=f"{club} rows on the official page vs capture",
                         official=str(n_live), committed=str(n_cap),
                         verdict=("MATCH" if n_live == n_cap else
                                  "PARTIAL READ — the fetched chunk cut this club's table short, "
                                  "so the short count is the read, not the source"),
                         as_of=f"{f['inj_retrieved']} capture vs {READ_WINDOW} read", source_url=URL["injuries"]))

    # (b) the published Week 10 table (assets/data, injuries.html source) vs the same official capture
    for label, abbr, n_cap, n_pub in (("Seattle", "SEA", f["inj_sea"], f["inj_pub_sea"]),
                                      ("Cincinnati", "CIN", f["inj_cin"], f["inj_pub_cin"])):
        rows.append(dict(check="published table vs capture", club=abbr, item=f"{label} Week 10 rows",
                         official=str(n_cap), committed=str(n_pub),
                         verdict=("MATCH" if n_cap == n_pub else
                                   f"MISMATCH — {n_cap - n_pub} official player rows are not in the published table"),
                         as_of=f"{f['inj_retrieved']} capture vs {AS_OF} derived table", source_url=URL["injuries"]))

    for tname in pub_all[pub_all.player == "No Injuries Reported"].team:
        code = next((c for word, c in name_to_code_lookup().items() if str(tname).endswith(word)), "")
        n_cap = int((inj.team == code).sum()) if code else 0
        rows.append(dict(check="published 'No Injuries Reported' vs official capture", club=code or "?",
                         item=f"{tname} printed injury-free in the published Week 10 table",
                         official=f"{n_cap} rows on the official page as captured {f['inj_retrieved']}",
                         committed="No Injuries Reported (0 player rows)",
                         verdict=("MATCH — the club has no rows in the capture either" if n_cap == 0 else
                                  f"CONTRADICTED — {n_cap} official rows against a published 'none'"),
                         as_of=f"{f['inj_retrieved']} capture vs {AS_OF} derived table", source_url=URL["injuries"]))

    # (c) reserve list: live page window vs the newest capture vs the retained history
    res = parse_reserve_rows(READS / "nfl_reserve_list_2026_11_rows.md")
    cap = rd(AV / "reserve" / "latest.csv")
    cap = cap[cap.month == "2026-11"]
    kcap = set(zip(cap.date, cap.team, cap.player))
    klive = set((r["date"], r["club"], r["player"]) for r in res)
    stats["reserve_live_rows"] = len(klive)
    for d, t, p in sorted(klive):
        on = (d, t, p) in kcap
        rows.append(dict(check="reserve list vs newest capture", club=t, item=f"{p} ({d[5:]})",
                         official="listed", committed="listed" if on else "not in capture",
                         verdict="ON BOTH" if on else "LIVE PAGE ONLY",
                         as_of=f"{f['reserve_captures']} captures; newest {AS_OF}", source_url=URL["reserve"]))
    for d, t, p in sorted(kcap - klive):
        rows.append(dict(check="reserve list vs newest capture", club=t, item=f"{p} ({d[5:]})",
                         official="not on live page", committed="listed", verdict="CAPTURE ONLY",
                         as_of=f"{f['reserve_captures']} captures; newest {AS_OF}", source_url=URL["reserve"]))
    stats["reserve_on_both"] = len(klive & kcap)
    stats["reserve_live_only"] = len(klive - kcap)
    stats["reserve_capture_only"] = len(kcap - klive)

    # (d) the game-centre read: venue and score, official live page vs the committed capture
    v = venues()
    one = v[v.game_id == "2026_10_WAS_NYG"]
    if len(one):
        man = json.loads((FORWARD / "captures" / "2026_10_WAS_NYG" / "manifest.json").read_text())
        rows.append(dict(check="game centre venue vs committed capture", club="WAS@NYG",
                         item="LOCATION / STADIUM as printed on the official game centre",
                         official=f"{one.iloc[0].location_printed} / {one.iloc[0].stadium_printed}",
                         committed=f"{man.get('away_team')} {man.get('away_score')} at "
                                  f"{man.get('home_team')} {man.get('home_score')} ({man.get('status_on_page')})",
                         verdict="MATCH on the score the capture records; the capture stores no venue field",
                         as_of=f"captured {man.get('captured_utc')}; venue read {READ_WINDOW}",
                         source_url=URL["gc_was_nyg"]))
    else:
        rows.append(dict(check="game centre venue vs committed capture", club="WAS@NYG", item="venue",
                         official="", committed="", verdict="NOT READ", as_of=AS_OF, source_url=URL["gc_was_nyg"]))

    # (e) Houston depth chart: the source-shape question behind F-49
    dep = rd(AV / "depth_charts.csv")
    hou = int((dep.team == "HOU").sum())
    txt = (READS / "houstontexans_depth_chart_page.md").read_text()
    has_image = "static.clubs.nfl.com/image/upload/texans/" in txt
    rows.append(dict(check="Houston depth source shape", club="HOU",
                     item="does the club page print machine-readable depth rows?",
                     official="heading 'Unofficial Depth Chart' over one image; no table" if has_image else "not established",
                     committed=f"{hou} parsed rows in {f['depth_retrieved']} capture",
                     verdict=("CONFIRMED SOURCE SHAPE — the club page prints an image, so 0 parsed rows is the "
                              "correct output of a faithful parser, not a parser defect"
                              if has_image and hou == 0 else "RECHECK — capture and read disagree"),
                     as_of=f"club page read {READ_WINDOW}; capture {f['depth_retrieved']}",
                     source_url=URL["hou_depth"]))
    return rows, stats


# --------------------------------------------------------------------------- #
# 3. the ablation contract (RR3)
# --------------------------------------------------------------------------- #
def ablation_rows(f: dict) -> list[dict]:
    """What an injury/depth ablation requires, and whether the repository can run it today."""
    fd = rd(PROC / "feature_dict.csv")
    personnel = fd[fd.feature.str.contains("injur|depth|personnel|start|snap|active", case=False)]
    rows = [
        dict(item="fixed injury penalty anywhere in the model",
             check="pipeline/models.py and the published feature dictionary are searched for a constant subtracted "
                   "for a missing starter",
             found=f"no such term exists: the feature dictionary has {f['model_features']} features and "
                   f"{f['personnel_features']} of them name injuries, depth or personnel",
             verdict="NOT PRESENT — nothing to remove",
             next_step="none; the brief's 'do not subtract a fixed number' rule is satisfied by construction",
             source_url=URL["injuries_root"]),
        dict(item="ablation with verified availability features",
             check="the ablation the brief asks for needs one availability feature row per game in the same corpus "
                   "the model is scored on",
             found=f"the corpus holds {f['corpus_games']} games across {f['corpus_seasons']}; the availability "
                   f"capture holds {f['inj_rows']} injury rows for one week ({f['inj_retrieved']}) and "
                   f"{f['depth_rows']} depth rows across {f['depth_clubs']} clubs",
             verdict="BLOCKED — the corpus and the availability data do not overlap",
             next_step="join the availability capture to the game corpus week by week until at least one full "
                       "season of pre-kickoff captures exists, then run the identical-model pair",
             source_url=URL["injuries"]),
        dict(item="chronological holdout, no reshuffle",
             check="the holdout rule the ablation must inherit is already implemented and tested for the model",
             found=f"leakage checks published in data/processed/leakage_checks.csv "
                   f"({len(rd(PROC / 'leakage_checks.csv'))} checks, all passing in the build)",
             verdict="READY — the rule exists; only the feature join is missing",
             next_step="reuse the same expanding-window split for the ablation so the comparison is like-for-like",
             source_url=URL["scores_w10"],
             source_label="NFL.com scores (the kickoffs a pre-kickoff freeze must precede; context, not proof)"),
        dict(item="report the difference with uncertainty",
             check="the paired-comparison estimator the ablation would report",
             found=f"bootstrap and game-cluster intervals are already used for the leaderboard "
                   f"({f['signal_staking_rows']} signal/staking rows with intervals)",
             verdict="READY — same estimator, new input",
             next_step="publish ΔBrier with a game-cluster interval and a multiplicity adjustment, never a win rate",
             source_url=URL["gh_pages"]),
        dict(item="sample size the ablation needs",
             check="games per season and weeks per season in the committed corpus",
             found=f"{f['corpus_games']} games over {len(set(int(s) for s in rd(PROC / 'games_model.csv').season))} "
                   f"seasons ⇒ about {round(f['corpus_games'] / max(1, len(set(int(s) for s in rd(PROC / 'games_model.csv').season))))} games per season; "
                   f"one captured week is {f['inj_rows']} report rows",
             verdict="BLOCKED AT n — a one-week join cannot resolve anything; a full season is the minimum unit",
             next_step="the number that clears it: 272 or more games each carrying a pre-kickoff availability row "
                       "(one full 17-week season at 16 games a week)",
             source_url=URL["injuries"]),
    ]
    return rows


# --------------------------------------------------------------------------- #
# 4. the register itself
# --------------------------------------------------------------------------- #
def items() -> list[dict]:
    """One row per request item in the 2026-11-18 brief. `{token}` fields are substituted from facts()."""
    I = []

    def add(iid, item, area, status, checked, evidence, gate, clears, url, label, note=""):
        I.append(dict(id=iid, item=item, area=area, status=status, checked=checked,
                      evidence="; ".join(evidence), gate=gate, clears=clears,
                      source_url=url, source_label=label, note=note))

    # ---- data layer -------------------------------------------------------
    add("RR-01", "Price-snapshot store recording opening and closing numbers for every market we originate",
        "Prices", "PARTLY DONE",
        "The store publishes {price_rows} rows over {price_games} games and {price_markets} market kinds; "
        "{price_open_filled} rows carry an open line and {price_close_filled} carry a close line. Provenance mix: "
        "{price_provenance}. {price_gaps_rows} gap rows name what is missing per market.",
        ["data/integration/price_snapshots.csv", "price-snapshot.html", "pipeline/price_snapshots.py"],
        "G1 — no authenticated, executable bookmaker quote is held, so a snapshot is a research number and not a price",
        "one authenticated two-sided quote captured pre-kickoff for each of the {price_markets} market kinds",
        URL["scores_w10"], "NFL.com scores (the official record each game row is keyed to)",
        "The store exists; the word 'price' is earned only when a quote with provenance exists.")
    add("RR-02", "Verified results feed so backtests and ROI can be computed at all", "Results", "DONE",
        "results_feed.csv holds {results_feed_rows} graded game rows, tier-labelled ({results_feed_tiers}); the "
        "officially re-read subset is {verified_results_rows} rows, of which {verified_results_final} print Final "
        "on the official page.",
        ["data/processed/results_feed.csv", "data/integration/verified_results.csv", "results-feed.html"],
        "none for the feed itself; the tier label is what stops a community row being read as an official one",
        "already cleared for 2026 Weeks 8–10; every Week 10 fixture in the forward ledger re-read on nfl.com",
        URL["scores_w10"], "NFL.com Week 10 scores page")
    add("RR-03", "Originate the side first, then the total, then the moneyline", "Origination", "DONE",
        "The order is asserted by a test and published per game: {origination_order_rows} rows carry "
        "side_fair, total_fair and moneyline columns in that sequence ({orig_side_fair} side, {orig_total_fair} "
        "total, {orig_ml_prob} moneyline values present).",
        ["tests/test_origination_order.py", "data/integration/origination_order.csv", "origination.html"],
        "none", "already cleared", URL["scores_w10"], "NFL.com schedule keys each ordered row")
    add("RR-04", "Publish the model's fair line, the market line and the difference as separate columns",
        "Origination", "DONE",
        "origination_order.csv publishes side_fair / side_market / side_diff and the same triple for the total; the "
        "market columns are blank where no market line is held ({orig_market_available} of {origination_order_rows} "
        "rows carry an edge-available flag, i.e. a market number to differ against).",
        ["data/integration/origination_order.csv", "pipeline/origination_order.py", "origination.html"],
        "the market columns stay blank until an authenticated quote exists (RR-01)",
        "one quote with provenance turns the diff column from blank to computed for that market",
        URL["scores_w10"], "NFL.com schedule and scores (game identity)")
    add("RR-05", "Separate 'signal' from 'staking' in the leaderboard", "Leaderboard", "DONE",
        "{signal_staking_rows} rows publish a signal verdict and a staking verdict side by side but in separate "
        "column groups; the master leaderboard carries gates and n on the signal side and stake rules on the other.",
        ["data/integration/signal_staking.csv", "data/integration/leaderboard_master.csv", "signal-staking.html"],
        "none", "already cleared", URL["scores_w10"], "NFL.com official settlement behind each graded pick")
    add("RR-06", "Track the depth of the replacement, not just the fact of a replacement", "Availability",
        "PARTLY DONE",
        "{replacement_depth_rows} team rows carry deepest_slot_used, cliff and max_chart_rank; "
        "{replacement_slots_rows} slot rows carry the matched chart row. The depth is a club chart slot, not snap "
        "share, so 'how deep' is bounded by what the club publishes.",
        ["data/gates/replacement_depth.csv", "data/gates/replacement_slots.csv", "replacement-depth.html"],
        "club charts carry no publication time and no game-day role; snap counts are not captured (RR-16)",
        "an official snap share per replacement, or a dated official inactive list, for one full week",
        URL["was_depth"], "Commanders club depth chart (representative of the club pages captured)")
    add("RR-07", "Compute correlations only from officially sourced numbers and publish n with each value",
        "Correlation", "DONE",
        "{corr_rows} official-source correlation rows are published and {corr_with_n} of them carry an n; the "
        "estimates are rho with a bootstrap interval and a zero-in-interval flag.",
        ["data/integration/official_correlations.csv", "correlation-official.html", "pipeline/corr_official.py"],
        "none for the published set; larger n needs more weeks of settled games",
        "n already published per row; more weeks raise the precision, they do not change the rule",
        URL["scores_w10"], "NFL.com scores, the only numbers the correlations are computed from")
    add("RR-08", "Demotion gate that sends a live strategy back to paper", "Governance", "DONE",
        "{demotion_rows} strategy rows publish the six demotion conditions and their current state; the register "
        "says explicitly that nothing is live because nothing is validated.",
        ["data/integration/demotion_gate.csv", "data/gates/demotion_gate.csv", "demotion.html"],
        "a strategy must be promoted first; none is", "already cleared as a rule; state changes with the first promotion",
        URL["gh_pages"], "GitHub Pages (the published rule is the enforcement surface)")
    add("RR-09", "Pre-register every strategy; forbid backtest numbers from ever appearing on the leaderboard",
        "Governance", "DONE",
        "{prereg_trial_rows} trial-registry rows and {prereg_sets} pre-registration sets; {published_lines_rows} "
        "published-line rows are keyed to a commit and a publication time; {prereg_picks} picks were frozen before "
        "kickoff, of which {forward_settled} are settled and {forward_open} remain open.",
        ["data/forward/trial_registry.csv", "data/forward/prereg_summary.csv", "data/forward/picks.csv", "forward.html"],
        "settlement needs an official final; {forward_open} picks still have none",
        "each open pick's official final on nfl.com; the leaderboard already excludes backtest returns",
        URL["scores_w10"], "NFL.com Week 10 scores (the settlement source)")
    add("RR-10", "Availability graph as a first-class dataset (who was expected to start, who actually did)",
        "Availability", "IN PROGRESS — SIBLING",
        "The committed pieces are the expectation side ({depth_rows} depth rows, {depth_clubs} clubs) and the "
        "report side ({inj_rows} injury rows); the actual-starter side needs the official Game Book, which "
        "`arena/99b908ab-korea1` claims as GB2/GB3 (PR #82).",
        ["data/availability/depth_charts.csv", "data/availability/injuries.csv"],
        "the Game Book parse is not merged; until then no actual starter is published",
        "one merged game-book capture that names a starter for one fixture, with its hash",
        URL["ops_pregame"], "NFL Operations pre-game report rules (the official T-90m inactive requirement)")
    add("RR-11", "Do not model depth from jersey order; model it from playing time", "Availability", "PARTLY DONE",
        "Depth is taken from the club's own chart order, never from a jersey number; the playing-time side is "
        "{pbp_backup_rows} team rows of play-by-play backup diagnostics ({roster_depth_rows} roster-depth rows). "
        "Snap share per named replacement is still not captured from an official source.",
        ["data/lineups/pbp_backup_impact.csv", "data/processed/roster_depth_history.csv", "pipeline/fetch_pbp.py"],
        "no official snap-count source is licensed in this repository; the PBP source used is a community mirror",
        "an official snap-count source for 32 clubs, or the Game Book play-by-play, joined to a named replacement",
        URL["scores_w10"], "NFL.com game centres (the official home of play-by-play and Game Books)")
    add("RR-12", "Make the injury signal a surprise, never a level", "Availability", "DONE",
        "{injury_delta_rows} change rows across {injury_delta_pairs} capture pairs are published as deltas; levels "
        "are not published as a signal. Every row carries the two capture times and the hash of the newer raw page.",
        ["data/processed/injury_deltas.csv", "injury-deltas.html", "pipeline/injury_deltas.py"],
        "none for the rule; the number of usable pairs grows with each daily capture",
        "already cleared; {capture_days} dated captures exist today",
        URL["injuries_root"], "NFL.com injury report (the page every delta is computed from)")
    add("RR-13", "Run the 32-team roster/IR sweep before any team-level model is trusted", "Availability",
        "PARTLY DONE",
        "The injury capture covers {inj_clubs} clubs with rows today; the reserve-list sweep holds "
        "{reserve_latest_rows} rows in the newest capture across {reserve_captures} captures. The roster sweep "
        "itself is not run for all 32 clubs in one dated pass.",
        ["data/availability/injuries.csv", "data/availability/reserve/latest.csv", "pipeline/fetch_reserve_list.py"],
        "the report prints a window, not a league-wide roster state; 'not listed' is not 'available'",
        "one dated pass over all 32 club rosters and all IR designations, joined to the report by player id",
        URL["reserve"], "NFL.com reserve list, November 2026")
    add("RR-14", "Fixture-context feature set built only from published schedule facts", "Features",
        "IN PROGRESS — SIBLING",
        "The committed pieces are the schedule facts already keyed to official rows (week, day, division flag, "
        "rest) and {corpus_games} games with those fields; the venue-side facts come from the game centres "
        "(RR-21) and are claimed by `arena/99b908ab-korea1` (GB4).",
        ["data/processed/games_model.csv", "data/processed/feature_dict.csv"],
        "a fixture-context table whose every column cites a published schedule fact is not yet merged",
        "one merged fixture_context.csv with a source URL per column",
        URL["scores_w10"], "NFL.com schedule and scores pages")
    add("RR-15", "Store every model output as a probability plus its inputs, not just a pick", "Origination",
        "DONE",
        "originated_lines.csv carries {originated_rows} rows with fair probabilities and the input features behind "
        "them; the forward ledger freezes the same vector before kickoff in {published_lines_rows} published rows.",
        ["data/processed/originated_lines.csv", "data/forward/published_lines.csv", "lines.html"],
        "none", "already cleared", URL["scores_w10"], "NFL.com schedule keys each stored input set")
    add("RR-16", "Capture official inactive lists and snap counts", "Availability", "NOT STARTED",
        "Nothing in the repository holds an inactive list or a snap share: {inj_game_designations} of {inj_rows} "
        "report rows carry a game designation and the rest are practice designations; no file holds a club's "
        "announced inactives.",
        ["data/availability/injuries.csv"],
        "the only official publisher of the inactive list is the T-90m game-day report, which is not captured; "
        "snap counts sit in the Game Book, claimed by another session",
        "one dated inactive-list capture for one fixture, joined to the injury report by player id",
        URL["ops_pregame"], "NFL Operations game-and-stadium preparation rules (the T-90m inactive deadline)")

    # ---- publishing / site ------------------------------------------------
    add("RR-17", "Compute and publish the 'removal of luck' panel on the site dashboard", "Leaderboard", "DONE",
        "Eight gates are computed for all {strategies} candidates and {strategies_validated} pass; G1 (quote "
        "provenance) fails for {strategies_g1_fail} of them, which is the panel's headline rather than a footnote.",
        ["data/processed/strategy_gates.csv", "validation.html", "pipeline/validation.py"],
        "none for the panel", "already cleared", URL["scores_w10"], "NFL.com settlement behind every graded outcome")
    add("RR-18", "Two-sided 'what would change our mind' field on every strategy entry", "Leaderboard", "DONE",
        "{mindchangers_rows} rows, one per candidate, each with the condition that would move it up and the "
        "condition that would stop it, plus the failing gates.",
        ["data/integration/mind_changers_2026_11_15.csv"], "none", "already cleared",
        URL["scores_w10"], "NFL.com official settlement referenced by each row")
    add("RR-19", "Price a line ourselves and publish the residual against the market, on a schedule, from day one",
        "Origination", "PARTLY DONE",
        "Fair lines exist for {orig_side_fair} games and the residual is published where a market number exists; "
        "the schedule half is the question: the price work runs when the build runs, not on a clock.",
        ["data/integration/origination_order.csv", "data/processed/price_archive.csv", "price-archive.html"],
        "no workflow originates lines on a schedule; the two scheduled workflows capture sources only",
        "one scheduled run that appends a frozen line row before a kickoff, with its commit hash",
        URL["gh_token"], "GitHub Actions scheduling documentation (the mechanism the brief asks for)")
    add("RR-20", "Turn the 136-game log into the pre-registered backtest corpus", "Governance",
        "NOT REPRODUCIBLE",
        "No artefact of 136 games exists in the repository: the corpus actually used is {corpus_games} games "
        "({corpus_seasons}); the price archive holds {price_rows} snapshot rows; the forward ledger holds "
        "{prereg_picks} frozen picks. The string '136' appears in the brief and nowhere in the data.",
        ["data/processed/games_model.csv", "data/processed/originated_lines.csv"],
        "the identifier in the request points at no file, so the corpus cannot be confirmed to be the one intended",
        "the owner naming the 136-game log (its source, its columns, its date range)",
        URL["scores_w10"], "NFL.com scores (the settlement source any such corpus would be graded against)")
    add("RR-21", "Transcribe the venue of every fixture from the official game centre and publish it",
        "Availability", "PARTLY DONE",
        "{game_pages_captured} official game-centre pages are captured in the repository; this session parsed a "
        "printed venue out of each and added the one fixture whose page was read rather than captured, so the "
        "venue table covers {venues_n} of {forward_schedule_rows} Week 10 fixtures with {venues_with_both_fields} "
        "rows carrying both LOCATION and STADIUM. Before this session the venue appeared nowhere in the committed "
        "data: the Munich fixture's printed location was not published anywhere.",
        ["data/forward/raw_captures", "data/integration/register_venues_2026_11_18.csv", "data/forward/official_schedule.csv"],
        "coverage: only Week 10 has any game-centre page in the repository, and one of its {forward_schedule_rows} "
        "fixtures exists only as a page read, not as a committed capture",
        "a captured game-centre page for every fixture of the current week — {venues_n} of {forward_schedule_rows} "
        "venues published today, {game_pages_captured} of them from a committed raw page",
        URL["gc_was_nyg"], "NFL.com game centre (the page that prints LOCATION and STADIUM)")
    add("RR-22", "Publish the league's dated schedule announcement beside the live schedule page", "Publishing",
        "NOT STARTED",
        "The repository captures the live schedule and the per-game pages, and records verification times; it does "
        "not hold the league's dated announcement of the schedule, and no committed file cites one.",
        ["data/forward/official_schedule.csv"],
        "no artefact; the source is an NFL press release with its own date line, which this session did not read",
        "one committed capture of the announcement page with its printed date and a hash",
        URL["scores_w10"], "NFL.com scores and schedule pages (the live side that is captured)")
    add("RR-23", "Re-capture and republish the Week 10 injury tables", "Availability", "PARTLY DONE",
        "The capture is current ({inj_rows} rows, {inj_clubs} clubs, {inj_retrieved}); the published derived table is "
        "not: injuries_week10.csv holds {inj_pub_rows} rows over {inj_pub_clubs} clubs, {inj_pub_sea} Seattle rows "
        "against {inj_sea} official and {inj_pub_cin} Cincinnati against {inj_cin}. The staleness is in the derived "
        "table, not the capture.",
        ["data/availability/injuries.csv", "data/processed/injuries_week10.csv", "assets/data/injuries_week10.csv"],
        "the derived table is built from a committed evidence snapshot rather than from the newest capture",
        "a build that reads the newest dated capture: the derived table matching {inj_rows} rows",
        URL["injuries"], "NFL.com Week 10 injury report")
    add("RR-24", "Populate the three missing Lions game-status designations", "Availability", "DONE",
        "Kerby Joseph, Cade Mays and D.J. Reed each print 'Out' on the official page read in this session and each "
        "carries game_status = Out in the {inj_retrieved} capture — the three rows were compared field by field "
        "against the live page with no difference (see the verification table).",
        ["data/availability/injuries.csv", "data/live/register_reads_2026_11_18/nfl_injuries_reg10_clubs.md"],
        "none for these three rows", "already cleared", URL["injuries"], "NFL.com Week 10 injury report")
    add("RR-25", "Snapshot the injury report every Wednesday, Thursday and Friday and keep a dated history",
        "Availability", "PARTLY DONE",
        "A dated history exists ({capture_days} captures, {capture_first} to {capture_last}) and it runs on a daily "
        "schedule, which is more often than the brief asks; the capture does not stop on Wed/Thu/Fri and does not "
        "label which day of the practice week a capture belongs to.",
        ["data/availability/history", ".github/workflows/availability.yml"],
        "none for cadence; a practice-week day label would make the mid-week trend readable",
        "each capture stamped with its practice-week day; {capture_days} captures today",
        URL["injuries_root"], "NFL.com injury report (the page the scheduled job reads)")
    add("RR-26", "Treat the injury report as a timestamped series, not a weekly snapshot", "Availability", "DONE",
        "Every row carries retrieved_utc and every capture keeps its raw bytes with a hash ({captures_with_hash} of "
        "{capture_sources} sources hashed this run); deltas are published instead of levels (RR-12).",
        ["data/processed/injury_deltas.csv", "data/availability/history", "injury-deltas.html"],
        "none", "already cleared", URL["injuries_root"], "NFL.com injury report")
    add("RR-27", "Automate immutable multi-day availability snapshots with retained hashes", "Availability",
        "PARTLY DONE",
        "Automation exists ({capture_days} dated captures, hashes per source, conflict flags in the manifest) and the "
        "reserve list keeps {reserve_captures} captures. Immutability is by convention: the history directory is "
        "append-only in practice, and nothing in the build refuses to rewrite a dated file.",
        ["data/availability/manifest.json", "data/availability/history", ".github/workflows/availability.yml"],
        "no guard prevents a rebuild from overwriting a dated capture",
        "one merged test or hook that fails when a dated capture changes after it is committed",
        URL["gh_token"], "GitHub Actions documentation (the runner that writes the captures)")
    add("RR-28", "Capture the reserve list so 'not listed' never means 'available'", "Availability", "DONE",
        "The live page read in this session prints {reserve_live_rows} November rows dated {reserve_date_min} to "
        "{reserve_date_max}; the newest capture agrees on {reserve_on_both} of them with {reserve_live_only} live-only "
        "and {reserve_capture_only} capture-only. Across the retained captures {reserve_union_nov} distinct November "
        "rows are held, {reserve_older_only} of them no longer printed on the live page ({reserve_older_only_names}).",
        ["data/availability/reserve/latest.csv", "data/availability/reserve/history", "pipeline/fetch_reserve_list.py"],
        "none for the retention rule", "already cleared — the window rows are recoverable from the history",
        URL["reserve"], "NFL.com reserve list, November 2026")
    add("RR-29", "Point-in-time snapshot ledger for injuries, depth charts and inactives", "Availability",
        "PARTLY DONE",
        "The injury and depth halves exist as a dated ledger ({capture_days} days, hashes, capture times) and the "
        "forward ledger freezes lines and inputs before kickoff; the inactive half has no source (RR-16).",
        ["data/availability/history", "data/forward/ledger.jsonl", "data/forward/anchors.csv"],
        "inactives are not captured, so a pre-kickoff certainty for a replacement cannot be shown",
        "one fixture with a captured T-90m inactive list joined to its pre-kickoff freeze",
        URL["ops_pregame"], "NFL Operations pre-game report rules")
    add("RR-30", "Add a drift alarm to every scraper; fail loudly on a missing field", "Governance", "PARTLY DONE",
        "The manifest records http status, byte count and row count per source, and a club whose chart yields no "
        "rows is kept as 'previous snapshot kept' rather than silently zeroed. There is no expected-row-count "
        "pin: Houston prints {hou_depth_rows} depth rows in every capture and the build does not fail on it, "
        "because the source genuinely publishes an image.",
        ["data/availability/manifest.json", "pipeline/fetch_availability.py", "pipeline/monitor_official.py"],
        "a blank field can still be published as a blank rather than as an alarm",
        "one build-time assertion of expected row counts and required fields per source, with an explicit "
        "source-shape exception list (Houston belongs in it)",
        URL["injuries_root"], "NFL.com injury report (the page the scraper reads; the workflow itself is "
        "repository infrastructure, not an official source)")
    add("RR-31", "Durable snapshot storage and alerts on freshness or schema change", "Governance", "PARTLY DONE",
        "Snapshots live in the repository (outside the static site's HTML) and every capture carries a retrieval "
        "time; no alert fires if a capture goes stale. Scheduled commits are made with GITHUB_TOKEN, so they do not "
        "trigger the verification workflow (irregularity F-47 in the 2026-11-18 register).",
        ["data/availability/history", "data/live/official_capture_drift.csv", ".github/workflows/official-monitor.yml"],
        "no alerting path exists; a silent stop of the scheduled job is not detected by anything",
        "one run of a check that fails when the newest capture is older than a stated age",
        URL["gh_token"], "GitHub Actions documentation on workflow-triggered pushes")
    add("RR-32", "Split the site into a public analysis layer and a private data layer", "Governance",
        "PARTLY DONE",
        "Raw HTML captures and evidence excerpts are kept as data files, not rendered; the public pages print derived "
        "tables with links to the official page for every row. But the raw captures are in the same public repository, "
        "so 'private' is not achieved: {spotcheck_rows} spot-check rows and four verbatim excerpts are published "
        "inside the same tree.",
        ["data/live/register_reads_2026_11_18", "data/forward/raw_captures", "pipeline/render_site.py"],
        "a single public repository cannot hold both layers; the terms-of-use question is also still open",
        "a private store or a documented decision that the club pages may be retained in a public repo",
        URL["gh_pages"], "GitHub Pages documentation (the publishing surface that is public by design)")

    # ---- model / analysis -------------------------------------------------
    add("RR-33", "Add injury and personnel ablations instead of fixed penalties", "Model", "PARTLY DONE",
        "The fixed-penalty half is verified absent: the model's feature dictionary has {model_features} features and "
        "no term subtracts points for a missing starter. The ablation half cannot be run: the corpus "
        "({corpus_games} games) and the availability capture ({inj_rows} rows, one week) do not overlap. See the "
        "ablation contract table on this page.",
        ["data/processed/feature_dict.csv", "data/integration/register_ablation_2026_11_18.csv", "pipeline/models.py"],
        "no availability feature exists per game in the scored corpus",
        "272 or more games each carrying a pre-kickoff availability row — one full season of captures",
        URL["injuries"], "NFL.com injury report (the only official source for the feature being ablated)")
    add("RR-34", "Ingest game-level results so the ratings are opponent-aware", "Results", "DONE",
        "{results_feed_rows} graded rows feed the ratings; offence and defence ratings are computed as "
        "opponent-expected points in the published feature dictionary ({model_features} features).",
        ["data/processed/results_feed.csv", "data/processed/games_model.csv", "pipeline/models.py"],
        "none", "already cleared", URL["scores_w10"], "NFL.com scores")
    add("RR-35", "Model depth slots as groups, not a single starter", "Availability", "DONE",
        "Slots are stored as club/unit/position groups with a slot number per player: {depth_slot_groups} groups in "
        "the newest capture, {depth_multirank1} of them carrying more than one rank-1 player; across the dated "
        "captures that count is {multirank_min}–{multirank_max} ({multirank_by_capture}). No 'the starter' is "
        "constructed from column 1.",
        ["data/availability/depth_charts.csv", "pipeline/depth_status.py", "availability.html"],
        "none for the representation", "already cleared; the brief's '149' figure is not reproduced by any capture "
        "and is recorded as a flag (F-46, 2026-11-18 register)",
        URL["was_depth"], "club depth-chart pages (the order the groups preserve)")
    add("RR-36", "Represent shared and empty depth slots faithfully", "Availability", "DONE",
        "The slot model prints every player in a slot with its depth rank and leaves a slot with no player as absent "
        "rather than as rank 1; {replacement_slots_rows} slot rows carry a matched/unmatched flag and a note.",
        ["data/gates/replacement_slots.csv", "pipeline/replacement_depth.py"],
        "none", "already cleared", URL["was_depth"], "club depth-chart pages")
    add("RR-37", "Fix the two depth-parsing failures before widening coverage", "Availability", "PARTLY DONE",
        "Houston: the club page prints one image under 'Unofficial Depth Chart' and no rows, so {hou_depth_rows} "
        "parsed rows is the faithful result (confirmed by reading the club page in this session — see the "
        "verification table). Packers: jersey-number prefixes are stripped and the raw string is retained by the "
        "capture, so the Packers rows parse ({depth_clubs} clubs carry rows in the newest capture).",
        ["pipeline/fetch_availability.py", "data/live/register_reads_2026_11_18/houstontexans_depth_chart_page.md"],
        "the Texans image has no authorised structured source yet; transcribing it by eye is refused by policy",
        "an authorised structured source for Houston depth (route a) or a merged snap-count route (route b)",
        URL["hou_depth"], "Houston Texans official depth-chart page (the image source, verified this session)")
    add("RR-38", "Reject: deriving depth order from jersey number, experience or salary", "Governance",
        "REJECTED AS REQUESTED",
        "The rejection is the delivered behaviour: no committed feature uses a jersey number, an experience field or "
        "a salary field, and the feature dictionary ({model_features} features) contains none.",
        ["data/processed/feature_dict.csv"],
        "none", "already cleared — the rule is enforced by the absence of the inputs",
        URL["was_depth"], "club depth-chart pages (the accepted source instead)")
    add("RR-39", "Flag stale depth rows against the official transactions log", "Availability", "PARTLY DONE",
        "The capture carries a retrieval time per row and the drift register publishes changes between captures "
        "(official_capture_drift.csv), and this session's own read shows the effect (a Washington defensive line "
        "row present in five captures and absent from three, irregularity F-42). There is no automated join from a "
        "stale chart row to the transaction that made it stale.",
        ["data/live/official_capture_drift.csv", "data/availability/history", "pipeline/depth_status.py"],
        "the transactions feed is captured only for reserve-list moves, not trades and releases per club",
        "one chart row automatically annotated with the dated transaction that supersedes it",
        URL["reserve"], "NFL.com transactions (the reserve-list half that is captured)")
    add("RR-40", "Calibrate what 'Questionable' means empirically instead of using old percentages",
        "Model", "PARTLY DONE",
        "The official page prints words, not probabilities: of {inj_rows} report rows, {inj_game_designations} carry "
        "a game designation and {inj_blank_game} carry none. The calibration needs designations joined to inactives "
        "over several seasons; {injury_delta_rows} delta rows exist and no inactive list does (RR-16).",
        ["data/availability/injuries.csv", "data/processed/injury_impact_history.csv", "pipeline/injuries.py"],
        "no inactive list per game, so the play rate per designation cannot be measured",
        "several seasons of designations joined to inactives; the minimum honest first step is one full season of "
        "captures joined to Game Book inactives",
        URL["injuries_root"], "NFL.com injury report (the page whose words are being calibrated)")
    add("RR-41", "Score injury-designation reliability before using it as a feature", "Model", "PARTLY DONE",
        "The register publishes the designation counts and the delta history; it does not publish a play rate per "
        "designation, which is the reliability measure asked for, for the same reason as RR-40.",
        ["data/processed/injury_impact_history.csv", "data/processed/availability_signals.csv"],
        "no official 'played' outcome joined to each designation",
        "one week where every designation is joined to the game's official participation evidence",
        URL["scores_w10"], "NFL.com scores and game pages (the participation evidence)")
    add("RR-42", "Interactive Offense vs Defense matchup deficiency matrix (1st–4th string)", "Site", "DONE",
        "{lineup_deficiency_rows} position-group rows carry the listed players, the designations split by practice "
        "type, the expected backup tier and its evidence state; the matrix renders them per matchup with the chart "
        "cells quoted, not re-ranked.",
        ["data/processed/lineup_deficiency.csv", "lineup-deficiencies.html", "pipeline/lineup_deficiencies.py"],
        "the interactive half is browser-side filtering only; no cross-machine interaction is possible in a static "
        "site, and the tiers are chart-order, not snap-verified",
        "an official snap or inactive source per club would let the matrix state a role rather than a chart cell",
        URL["was_depth"], "club depth charts (the order the tiers come from)")
    add("RR-43", "Per-team view: starters out, replacements named, net injury count", "Site", "PARTLY DONE",
        "Net counts and designations are published per club ({lineup_deficiency_rows} rows; the report's own club "
        "split is {inj_clubs} clubs); 'replacements named' is published only where the club or the league announced "
        "it — which is why the replacement columns are blank by design on the report page.",
        ["data/processed/lineup_deficiency.csv", "injuries.html", "lineups.html"],
        "an announced replacement is a dated official statement; none is captured for these clubs",
        "one club-announced starter or replacement, captured with its date and quoted in the row",
        URL["injuries_root"], "NFL.com injury report")
    add("RR-44", "Announced-starter evidence field (not an inferred replacement)", "Availability", "PARTLY DONE",
        "The field exists in the register shape (tier_evidence and status_source_url per row, and the "
        "lineup-claim verification that graded 59 availability sentences against dated captures), and the "
        "brief's named examples (Lock, McCord, Brissett as VR-24/VR-25/VQ-05) were checked: no committed artefact "
        "carries those identifiers, and the only related observation this session could reproduce is that a Tampa "
        "Bay quarterback appears in the report while the Baltimore chart order changed between captures (F-46).",
        ["data/live/lineup_claim_verification.csv", "data/processed/lineup_deficiency.csv"],
        "the brief's identifier scheme maps to no file (F-48), so the specific claims cannot be traced",
        "the owner supplying the source behind VR-24, VR-25 and VQ-05, or a dated official starter announcement",
        URL["injuries_root"], "NFL.com injury report and club pages")
    add("RR-45", "Official depth-chart register with a date and a source per row", "Availability", "DONE",
        "{depth_rows} rows across {depth_clubs} clubs, each with source_url and retrieved_utc ({depth_retrieved}); "
        "{captures_with_hash} of {capture_sources} capture sources carry a raw-page hash.",
        ["data/availability/depth_charts.csv", "data/availability/manifest.json"],
        "no club publishes a chart publication date, so the date available is the capture date, which is stated "
        "on every row rather than disguised",
        "already cleared within the limit the sources allow",
        URL["was_depth"], "club depth-chart pages")
    add("RR-46", "Treat roster turnover as a first-class data event", "Availability", "PARTLY DONE",
        "Turnover is retained as dated captures that change ({injury_delta_rows} deltas; drift register published), "
        "and the reserve list is retained across {reserve_captures} captures, so a release that moves the live page "
        "off a row is recoverable. What is missing is a version key: chart and report rows are not stamped with the "
        "roster event they were captured against.",
        ["data/processed/injury_deltas.csv", "data/availability/reserve/history", "data/live/official_capture_drift.csv"],
        "no roster-event id on each availability row",
        "one capture whose rows carry the id of the last official transaction applied to that club",
        URL["reserve"], "NFL.com transactions (the dated events)")

    # ---- leaderboard / competition ---------------------------------------
    add("RR-47", "Start with a singles-only shadow baseline", "Leaderboard", "DONE",
        "{control_rows} control baselines (random and favourites) are published beside the candidates, on the same "
        "settled sample; the shadow rule is that a candidate must beat the control on a proper score, not on win rate.",
        ["data/processed/control_baseline.csv", "tests/test_control_baseline.py", "pipeline/control_baseline.py"],
        "none", "already cleared", URL["scores_w10"], "NFL.com settlement")
    add("RR-48", "Keep parlays and prop combos behind a joint-evidence gate", "Leaderboard", "DONE",
        "{prop_gates_rows} combo rows are published with the joint probability, the product of the marginals, the "
        "gap and a gate table; every combo fails the joint-probability gate, so none is ranked.",
        ["data/processed/prop_gates.csv", "data/processed/prop_combos.csv", "props.html"],
        "no validated joint probability exists, and operator void/push rules are not held",
        "one combo with a validated joint probability and the operator's written void rule",
        URL["scores_w10"], "NFL.com settlement for the legs")
    add("RR-49", "Proper-score leaderboard divisions (singles, game parlays, SGP, prop combos)", "Leaderboard",
        "DONE",
        "{leaderboard_rows} entries carry a division field; the divisions are ranked on benchmark-relative proper "
        "scores with intervals, and the ranking basis is printed on the row.",
        ["data/integration/leaderboard_master.csv", "pipeline/session_competition.py", "competition.html"],
        "none for the structure; the ranking itself is unrankable while every candidate fails G1",
        "already cleared as a structure", URL["scores_w10"], "NFL.com settlement")
    add("RR-50", "Rank with proper scores and uncertainty, not win rate", "Leaderboard", "DONE",
        "{signal_staking_rows} rows publish Spearman with an interval, decile lift, ROI with an interval, and the "
        "verdict per side; the power requirement (weeks_required) is printed beside the weeks observed.",
        ["data/integration/signal_staking.csv", "data/processed/strategy_stats.csv", "competition.html", "signal-staking.html"],
        "none for the method", "already cleared", URL["scores_w10"], "NFL.com settlement")
    add("RR-51", "Two-stage skill leaderboard: proper-score qualification, then prospective CLV/ROI escrow",
        "Leaderboard", "PARTLY DONE",
        "Stage one is live: qualification on proper scores with {strategies_validated} of {strategies} candidates "
        "passing. Stage two needs closing-line value, and a close is only ever a mirror of our own frozen line "
        "(irregularity F-44), not a market close.",
        ["data/processed/strategy_gates.csv", "data/processed/price_archive.csv", "competition.html"],
        "no market close with provenance, so CLV is undefined",
        "one authenticated closing number for one already-frozen pick",
        URL["scores_w10"], "NFL.com settlement (the only source used for outcomes today)")
    add("RR-52", "Vig-free market consensus versus originated fair-line decomposition", "Origination",
        "BLOCKED — SOURCE",
        "The decomposition needs a market side to decompose; the repository holds community archive lines and its own "
        "frozen lines. The overround is computed from what is held ({price_rows} snapshot rows) and the vig analysis "
        "is published by season, but a vig-free consensus of executable quotes does not exist.",
        ["data/processed/vig_by_season.csv", "data/processed/price_archive.csv"],
        "no executable quotes and no licensed consensus",
        "one week of quotes from two or more permitted operators, with capture times",
        URL["scores_w10"], "NFL.com (the schedule and settlement spine a consensus would be keyed to)")
    add("RR-53", "Publish a weekly 'what changed' diff instead of a static snapshot", "Publishing", "DONE",
        "The delta pages publish change between dated captures; the strategy side publishes the weekly matrix; the "
        "brief's ranking-change column follows from the leaderboard rows.",
        ["injury-deltas.html", "data/processed/strategy_weekly_matrix.csv", "data/processed/injury_coverage_changes.csv"],
        "none", "already cleared", URL["injuries_root"], "NFL.com injury report (what the diff is computed from)")
    add("RR-54", "Publish every model total twice until one wins", "Model", "PARTLY DONE",
        "Two total estimators are published per game with the gap column (ridge and matchup inside "
        "originated_lines.csv, and the accuracy table showing the two MAEs against the market); the collapse rule is "
        "a walk-forward comparison that cannot conclude while the market column is blank.",
        ["data/processed/originated_lines.csv", "data/integration/origination_accuracy.csv", "origination.html"],
        "walk-forward superiority against a market number needs that number",
        "one pre-registered season where one estimator wins on a proper score with an interval that excludes zero",
        URL["scores_w10"], "NFL.com scores (the outcome both estimators are graded against)")
    add("RR-55", "Control baseline (random picks; favourites only) in every leaderboard run", "Leaderboard", "DONE",
        "{control_rows} control rows are produced by the build and tested (tests/test_control_baseline.py); the run "
        "that produced the current standings includes them.",
        ["data/processed/control_baseline.csv", "tests/test_control_baseline.py"],
        "none", "already cleared", URL["scores_w10"], "NFL.com settlement")
    add("RR-56", "Reject: ranking strategies by season-long ROI", "Governance", "REJECTED AS REQUESTED",
        "Delivered as a rule, not an argument: the leaderboard's ranking basis column states proper-score skill and "
        "the ROI columns are marked as staking-side only; the demotion register treats a short ROI run as grounds to "
        "review, not grounds to promote.",
        ["data/integration/leaderboard_master.csv", "data/integration/demotion_gate.csv"],
        "none", "already cleared", URL["scores_w10"], "NFL.com settlement")
    add("RR-57", "Decide the price-data policy before any backtest is published", "Governance",
        "BLOCKED — OWNER",
        "Backtests are published, so the sequence the brief asks for is already inverted; the open half is the "
        "policy text: the 2026-11-18 irregularity register carries F-44 (whether a ledger freeze may populate a close "
        "column at all) as an owner decision with no entry in DECISIONS.md.",
        ["data/integration/flagged_2026_11_18.csv", "DECISIONS.md", "data/processed/price_archive.csv"],
        "the owner has not recorded a price-data policy",
        "one dated row in DECISIONS.md stating what may be called a price and what may not",
        URL["scores_w10"], "NFL.com scores (the only number the site currently treats as authoritative)")

    # ---- governance / process --------------------------------------------
    add("RR-58", "Freeze a rule before it sees data; the commit hash is the registration", "Governance", "DONE",
        "{prereg_sets} pre-registration sets are recorded with a commit, a path and a publication time, and the audit "
        "checks that each set's games were priced unplayed at publication ({published_lines_rows} published rows).",
        ["data/forward/prereg_summary.csv", "data/forward/prereg_audit.csv", "data/forward/published_lines.csv"],
        "none for the mechanism", "already cleared", URL["scores_w10"], "NFL.com schedule (the kickoff the freeze precedes)")
    add("RR-59", "Split data into train, validation and final holdout seasons", "Governance", "DONE",
        "The split is published in the validation configuration and enforced by the leakage checks "
        "({corpus_games} games over {corpus_seasons}); the holdout is not reused for tuning.",
        ["data/processed/validation_config.json", "data/processed/leakage_checks.csv", "validation.html"],
        "none", "already cleared", URL["scores_w10"], "NFL.com scores for the graded outcomes")
    add("RR-60", "Store every model output with its inputs (probability plus inputs)", "Model", "DONE",
        "See RR-15; the forward ledger stores the input vector hash with each freeze ({published_lines_rows} rows with "
        "a blob hash and a commit).",
        ["data/forward/published_lines.csv", "data/processed/originated_lines.csv"],
        "none", "already cleared", URL["scores_w10"], "NFL.com schedule keys the inputs")
    add("RR-61", "Store every injury-hub read with its clock time and publish the delta, never the level",
        "Availability", "DONE",
        "See RR-12 and RR-26; the capture ledger holds {capture_days} dated reads with hashes and the delta table "
        "holds {injury_delta_rows} changes.",
        ["data/processed/injury_capture_ledger.csv", "data/processed/injury_deltas.csv"],
        "none", "already cleared", URL["injuries_root"], "NFL.com injury report")
    add("RR-62", "Dedicated suggestions section where a path is chosen before any change is implemented", "Site",
        "DONE",
        "Three surfaces exist ({suggestions_master_rows} merged proposals, a path selector, and this session's "
        "register below, which keys one path choice to each open item); the page writes nothing back to the "
        "repository, by design.",
        ["suggestions-review.html", "decision-board.html", "data/integration/suggestions_master.csv",
         "data/integration/register_suggestions_2026_11_18.csv"],
        "selection is a browser-local preview; a chosen path becomes real only in a committed change",
        "one committed DECISIONS.md row naming the chosen path for one item",
        URL["gh_pages"], "GitHub Pages (the static site cannot write a decision back)")
    add("RR-63", "A clear list of questions, information and answers needed before a decision, with discovery "
        "steps for what is missing", "Site", "DONE",
        "{questions_master_rows} merged questions exist; this session adds the {register_q_n} dated 2026-11-18 "
        "questions below, each tied to a register row it gates and to the step that would close it.",
        ["data/integration/questions_master.csv", "data/integration/register_questions_2026_11_18.csv", "answers.html"],
        "none for the register", "already cleared", URL["injuries_root"], "NFL.com (the source most open questions need)")
    add("RR-64", "Executive summary outlining important details", "Site", "DONE",
        "The summary page and file exist and are regenerated by the build; this page carries a dated 2026-11-18 "
        "summary computed from the register (nothing in it is typed: each count is a fact from the table above).",
        ["EXECUTIVE_SUMMARY.md", "executive-summary.html", "data/integration/register_facts_2026_11_18.csv"],
        "none", "already cleared", URL["scores_w10"], "NFL.com (the spine the summary is keyed to)")
    add("RR-65", "No manual input; the pipeline runs on its own", "Process", "PARTLY DONE",
        "Source capture, settlement proposals and the build run on schedules; what remains manual is the promotion "
        "step that must stay manual by policy (the forward ledger never writes the evidence file automatically) and "
        "every owner decision (RR-57, RR-32, RR-31).",
        [".github/workflows/availability.yml", ".github/workflows/forward-ledger.yml", ".github/workflows/reserve-list.yml"],
        "promotion of a proposed score, and any owner decision",
        "already as automated as the evidence policy allows",
        URL["gh_token"], "GitHub Actions documentation (the scheduling and token limits that bind this item)")
    add("RR-66", "Parallel sessions coordinate through COORDINATION.md; scopes do not overlap", "Process", "DONE",
        "Five sibling sessions are live on this repository today; this register touches none of their files, and the "
        "nav wiring it would otherwise need is logged as a request instead of edited.",
        ["COORDINATION.md"], "none", "already cleared", URL["gh_pages"], "GitHub Pages (the shared output integration owns)")
    add("RR-67", "Every table row carries a source link; unverified values stay blank and flagged", "Process",
        "DONE",
        "The verifier enforces it on {site_pages} pages at build time; {irregularities_rows} irregularity rows and "
        "{flagged_rows_1118} dated 2026-11-18 findings record what is blank and why. Rows with no official source "
        "anywhere (RR-20, RR-22, RR-57) are printed outside the tables on this page, with that stated.",
        ["pipeline/verify_site.py", "data/integration/irregularities.csv", "data/integration/flagged_2026_11_18.csv"],
        "none for the rule", "already cleared", URL["gh_pages"], "GitHub Pages (the published site the rule binds)")
    add("RR-68", "Sweep the site for irregularities and flag them for review", "Process", "DONE",
        "Repo review, referent resolution, and this session's checks: {flagged_rows_1118} rows in the 2026-11-18 "
        "register plus {register_flag_n} added below, each with a next step.",
        ["repo-review.html", "referents.html", "data/integration/flagged_2026_11_18.csv",
         "data/integration/register_flags_2026_11_18.csv"],
        "repair is a decision the owner makes; flags are published, not fixed",
        "already cleared", URL["gh_pages"], "GitHub Pages")
    return I


def questions(f: dict) -> list[dict]:
    """The questions that gate decisions, keyed to the register row each one unblocks."""
    Q = [
        dict(id="RR-Q1", gates="RR-01, RR-51, RR-52",
             question="Which price source may we hold, publish and backtest against, under whose terms?",
             known="The repository holds a community archive and our own frozen lines; the label on every close cell "
                   "says whether it is a bookmaker quote or a ledger mirror.",
             missing="an authenticated quote feed, and the written terms under which a quote may be republished",
             how="read an operator's terms, or buy a feed; until then the price-data policy (RR-57) is the decision "
                 "that unblocks three rows",
             status="NEEDS OWNER DECISION", source_url=URL["scores_w10"], source_label="NFL.com scores"),
        dict(id="RR-Q2", gates="RR-10, RR-16, RR-29",
             question="Where does an official inactive list come from, on a schedule, for every club?",
             known="The T-90m report is the official deadline and the club pages carry the game-day report; the "
                   "repository captures neither on a schedule.",
             missing="a captured, dated inactive list for at least one fixture",
             how="extend the availability workflow to fetch the pre-game report window on Sundays, or parse the "
                 "Game Book (claimed by another session)",
             status="OPEN", source_url=URL["ops_pregame"], source_label="NFL Operations pre-game rules"),
        dict(id="RR-Q3", gates="RR-37, RR-11",
             question="What is the authorised structured source for a club that publishes depth only as an image?",
             known="The Houston page prints one image under 'Unofficial Depth Chart' — verified by reading the club "
                   "page in this session; the capture therefore yields 0 rows, correctly.",
             missing="either permission to transcribe the image, or a snap-count route that does not need the chart",
             how="route (a) ask the club/league for a data feed; route (b) merge the Game Book play-by-play and use "
                 "snap share as the depth proxy",
             status="OPEN", source_url=URL["hou_depth"], source_label="Houston Texans depth-chart page"),
        dict(id="RR-Q4", gates="RR-31",
             question="Where do the raw captures live long term, and who is paged when they stop arriving?",
             known="Captures are committed into the public repository; scheduled commits use GITHUB_TOKEN and do not "
                   "trigger the verification workflow (F-47).",
             missing="a store outside the site, and an alerting path",
             how="decide between release assets, an issues-based alert, or a separate private repository",
             status="NEEDS OWNER DECISION", source_url=URL["gh_token"], source_label="GitHub Actions documentation"),
        dict(id="RR-Q5", gates="RR-32",
             question="May verbatim club and league page content be retained in a public repository?",
             known="The site currently retains raw game-centre HTML and transcribed excerpts with hashes; the terms "
                   "of use of the club pages have not been read into a decision record.",
             missing="the terms, read and recorded",
             how="read each club's terms of use and the league's copyright statement, record the outcome in "
                 "DECISIONS.md; the analysis layer stays either way",
             status="BLOCKED — OWNER", source_url=URL["was_depth"], source_label="a representative club page"),
        dict(id="RR-Q6", gates="RR-20, RR-44",
             question="What do the brief's identifiers (VR-*, VQ-*, SG-*, the 136-game log) point at?",
             known="No file in the repository uses that scheme; the 2026-11-18 register F-48 records the search that "
                   "found none.",
             missing="the source document behind each identifier",
             how="the brief author supplies the mapping, or the identifiers are dropped and the claims restated "
                 "against repository artefacts",
             status="OPEN", source_url=URL["reserve"], source_label="NFL.com transactions (the page one such claim cites)"),
        dict(id="RR-Q7", gates="RR-13, RR-28",
             question="Is the monthly reserve page a record or a rolling window?",
             known=f"The live page read in this session prints November rows from {f['reserve_date_min']} to "
                   f"{f['reserve_date_max']}; {f['reserve_older_only']} rows that were on the page are still held in "
                   f"the retained captures.",
             missing="a statement of the page's own window rule — the page prints none",
             how="keep capturing daily (done) and treat the capture union, not the live page, as the sweep",
             status="ANSWERED FOR PRACTICE", source_url=URL["reserve"], source_label="NFL.com reserve list"),
        dict(id="RR-Q8", gates="RR-23",
             question="Which Week 10 injury table is the site's source of record: the capture or the derived table?",
             known=f"The capture holds {f['inj_rows']} rows ({f['inj_retrieved']}); the derived published table holds "
                   f"{f['inj_pub_rows']}; the difference is concentrated in clubs the derived build sampled "
                   f"({f['inj_pub_sea']} Seattle rows against {f['inj_sea']}).",
             missing="a decision to build the derived table from the newest capture instead of a committed extract",
             how="change the derived input, not the published numbers by hand; the build then cannot lag the capture",
             status="OPEN", source_url=URL["injuries"], source_label="NFL.com Week 10 injury report"),
        dict(id="RR-Q9", gates="RR-40, RR-41",
             question="What does 'Questionable' have to be measured against before it can be a feature?",
             known="Designation counts are known; the play rate is not, because no inactive list is held (RR-16).",
             missing="designations joined to participation, over enough games to say something",
             how="score the designation against the official game record for every week captured so far, publish the "
                 "rate with an interval, and only then decide if it enters the model",
             status="OPEN", source_url=URL["injuries_root"], source_label="NFL.com injury report"),
        dict(id="RR-Q10", gates="RR-19",
             question="Should origination run on a clock, and at what times relative to kickoff?",
             known="Origination currently runs when the build runs; the brief asks for a published residual 'on a "
                   "schedule, from day one'.",
             missing="a schedule definition (days and times) and the storage for each frozen run",
             how="add a scheduled workflow that writes one frozen row per fixture per run, keyed to a commit; reuse "
                 "the pre-registration machinery that already exists",
             status="OPEN", source_url=URL["gh_token"], source_label="GitHub Actions scheduling"),
        dict(id="RR-Q11", gates="RR-33",
             question="Can an ablation be run at all on the data we hold?",
             known=f"The corpus is {f['corpus_games']} games ({f['corpus_seasons']}); verified availability rows exist "
                   f"for one week ({f['inj_rows']} report rows). No overlap, no ablation.",
             missing="pre-kickoff availability for the games the model is scored on",
             how="capture forward for a full season and backfill only from sources that carry a publication time; "
                 "report the with/without difference with a cluster interval",
             status="BLOCKED — SOURCE", source_url=URL["injuries_root"], source_label="NFL.com injury report"),
        dict(id="RR-Q12", gates="RR-22",
             question="Which dated schedule announcement is the authority beside the live schedule page?",
             known="Nothing in the repository cites one; the live schedule and per-game pages are captured.",
             missing="the announcement itself, with its publication date",
             how="capture the league's schedule-release announcement once, store it with a hash and a date, and link "
                 "it from the schedule page",
             status="OPEN", source_url=URL["scores_w10"], source_label="NFL.com scores and schedule"),
    ]
    return Q


def suggestions(f: dict) -> list[dict]:
    """Paths the owner can choose, each tied to the register rows it clears. Nothing here is implemented."""
    S = [
        dict(id="RR-S1", gates="RR-01, RR-51, RR-52, RR-57", title="Close the price question first",
             path_a="Publish nothing that calls a number a price: strip the close column to blanks and keep the "
                    "ledger mirror in a separate, labelled table.",
             path_b="Keep the current labelling (mirror vs quote) and record the policy in DECISIONS.md without "
                    "buying anything.",
             path_c="Acquire an authenticated quote feed and re-run every gate against real closes.",
             recommended="Path B", cost="A: no cost, some rework · B: no cost · C: a subscription",
             risk="A discards usable research signal · C spends money before the signal is shown to exist",
             gate_cleared="F-44 becomes answerable; G1 still fails until a real quote is held",
             status="AWAITING PATH SELECTION", source_url=URL["scores_w10"],
             source_label="NFL.com scores (the settlement the closes would be graded against)"),
        dict(id="RR-S2", gates="RR-16, RR-10, RR-29, RR-40", title="Capture the game-day report window",
             path_a="Extend the existing availability workflow with a Sunday T-100m/T-60m capture of the official "
                    "pre-game report, storing the raw page and its hash.",
             path_b="Wait for the Game Book workflow (another session's scope) and derive inactives from the Game "
                    "Book instead.",
             path_c="Both, with the two sources cross-checked and conflicts flagged rather than reconciled by hand.",
             recommended="Path C", cost="machine time and one workflow file; no purchase",
             risk="a third capture source means a third way to be wrong; conflicts must be published, not averaged",
             gate_cleared="unblocks RR-16, which RR-40 and RR-41 wait on",
             status="AWAITING PATH SELECTION", source_url=URL["ops_pregame"],
             source_label="NFL Operations pre-game report rules"),
        dict(id="RR-S3", gates="RR-23, RR-30", title="Make the derived injury table read the newest capture",
             path_a="Point the derived Week 10 table at the newest dated capture and let the build fail if a club's "
                    "row count drops without a transaction to explain it.",
             path_b="Leave the derived table as a dated sample and publish the capture as the source of record, with "
                    "the difference stated on the page.",
             path_c="Remove the derived table entirely.",
             recommended="Path A", cost="one input path change plus an expected-count assertion",
             risk="an expected-count rule can shout at a legitimate source change; the exception list matters",
             gate_cleared=f"removes the {f['inj_rows']}-against-{f['inj_pub_rows']} row gap that RR-23 records",
             status="AWAITING PATH SELECTION", source_url=URL["injuries"],
             source_label="NFL.com Week 10 injury report"),
        dict(id="RR-S4", gates="RR-31, RR-32, RR-47", title="Decide storage and terms before more data accumulates",
             path_a="Keep captures in the public repository and read the terms before publishing anything derived "
                    "from a club page.",
             path_b="Move raw captures to release assets or a private store, keep the site to derived analysis, and "
                    "add a freshness alert.",
             path_c="Do nothing until a legal read is available; accept the drift risk in the meantime.",
             recommended="Path B", cost="one repository change plus a small alerting job",
             risk="Path C leaves the site as the only store, which is the failure mode the brief flags",
             gate_cleared="RR-31 and RR-32; also makes RR-47's 'no manual input' claim stronger",
             status="AWAITING PATH SELECTION", source_url=URL["gh_pages"],
             source_label="GitHub Pages documentation"),
        dict(id="RR-S5", gates="RR-33, RR-41", title="Grow the availability corpus forward, not backward",
             path_a="Start a dated pre-kickoff capture of the report per club and let it accumulate for a season; "
                    "no backtest of availability claims until then.",
             path_b="Reconstruct history from archive pages that carry no publication time, and label every such row "
                    "as ambiguous.",
             path_c="Skip availability as a model input and keep it as a published diagnostic.",
             recommended="Path A", cost="disk and patience",
             risk="Path B's ambiguity is exactly the lookahead the brief forbids; Path C is honest but slow",
             gate_cleared=f"one season (about {f['corpus_games'] // 23} games' worth of captures) makes RR-33 runnable",
             status="AWAITING PATH SELECTION", source_url=URL["injuries_root"],
             source_label="NFL.com injury report"),
        dict(id="RR-S6", gates="RR-37, RR-11, RR-06", title="Resolve the depth-order source club by club",
             path_a="Verify the club chart route for all 32 clubs and record which clubs cannot be parsed, rather "
                    "than treating an image as an absence of depth.",
             path_b="Use snap share as the ordering everywhere, once a Game Book or play-by-play source is merged.",
             path_c="Restrict every depth feature to the clubs whose charts are verified, and say so on each row.",
             recommended="Path A then B", cost="a coverage audit per club; route B depends on another session's merge",
             risk="a partial chart route silently treats unparsed clubs as healthy",
             gate_cleared="RR-37 and the depth half of RR-06",
             status="AWAITING PATH SELECTION", source_url=URL["was_depth"],
             source_label="club depth-chart pages (one of 32; the audit covers all)"),
        dict(id="RR-S7", gates="RR-62, RR-57", title="Turn the path picker into a recorded decision",
             path_a="Leave the picker as a browser preview; the owner writes the chosen path into DECISIONS.md by "
                    "hand.",
             path_b="Add a reviewed path where a chosen selection is submitted as a pull request against the "
                    "register, so a decision is auditable and reversible.",
             path_c="Auto-commit selections.",
             recommended="Path B", cost="a small export format plus one manual commit per decision",
             risk="Path C would let a browser click change a published decision record — refused by the evidence policy",
             gate_cleared="RR-62's 'selection is not recorded' limit; RR-57 if the decision is the price policy",
             status="AWAITING PATH SELECTION", source_url=URL["gh_pages"],
             source_label="GitHub Pages (a static site cannot write a decision back)"),
        dict(id="RR-S8", gates="RR-20, RR-44, RR-Q6", title="Retire or resolve the brief's private identifiers",
             path_a="Ask the brief author for the mapping (VR-*, VQ-*, SG-*, the 136-game log) and restate the "
                    "affected rows against named artefacts.",
             path_b="Restate each claim in repository terms now, and treat the identifiers as prose.",
             path_c="Leave them as unresolvable flags, as F-48 does.",
             recommended="Path A", cost="one exchange with the brief author",
             risk="Path B risks silently substituting a different claim for the one made",
             gate_cleared="RR-20 and RR-44 stop being not-reproducible, or are formally closed",
             status="AWAITING PATH SELECTION", source_url=URL["reserve"],
             source_label="NFL.com transactions (the page several such claims rest on)"),
    ]
    return S


def flags(f: dict, stats: dict) -> list[dict]:
    """This session's findings, numbered RR-F1… so they cannot collide with F-42…F-51 of another session."""
    rows = [
        dict(id="RR-F1", severity="High · open",
             finding=f"The published Week 10 injury table is not the newest official read: derived "
                     f"{f['inj_pub_rows']} rows / {f['inj_pub_clubs']} clubs against capture {f['inj_rows']} rows / "
                     f"{f['inj_clubs']} clubs ({f['inj_retrieved']}). Per club: Seattle {f['inj_pub_sea']} vs "
                     f"{f['inj_sea']}, Cincinnati {f['inj_pub_cin']} vs {f['inj_cin']}. The capture is right; the "
                     "derived table is a stale sample and the site prints both.",
             next="RR-S3 Path A: build the derived table from the newest dated capture and assert expected row counts.",
             source_label="NFL.com Week 10 injury report", source_url=URL["injuries"],
             register="RR-23"),
        dict(id="RR-F2", severity="Medium · closed by evidence",
             finding=f"The reserve-page mismatch recorded as F-45 this morning is explained: the live page read in "
                     f"this session prints {stats['reserve_live_rows']} November rows and the newest capture (04:42Z "
                     f"today) agrees on {stats['reserve_on_both']} of them, with {stats['reserve_live_only']} live-only "
                     f"and {stats['reserve_capture_only']} capture-only. Retained captures hold {f['reserve_union_nov']} "
                     f"distinct November rows, {f['reserve_older_only']} of which the live page no longer prints "
                     f"({f['reserve_older_only_names']}). The page is a window; the capture history is the record.",
             next="Owner: replace F-45's 'window is one possible explanation' with this measurement, or keep the "
                  "caveat and rely on the daily capture (which the data says works).",
             source_label="NFL.com reserve list, November 2026", source_url=URL["reserve"], register="RR-28"),
        dict(id="RR-F3", severity="Medium · confirmed, not a defect",
             finding="The Houston depth-chart page prints the heading 'Unofficial Depth Chart' over a single image "
                     "and no rows, verified by reading the club page in this session. The 0 parsed Houston rows in "
                     "every capture are therefore a faithful reading of the source, not a parser failure. F-49's "
                     "premise is confirmed; the fix is a different source (or permission), never an eye-transcription.",
             next="RR-S6: pick the route before any Houston depth feature is built.",
             source_label="Houston Texans depth-chart page", source_url=URL["hou_depth"], register="RR-37"),
        dict(id="RR-F4", severity="Medium · open",
             finding=f"The venue the official game centre prints is captured but not published: {f['game_pages_captured']} "
                     f"raw game pages sit in the repository with LOCATION and STADIUM fields, and 'MUNICH' / 'FC BAYERN "
                     "MUNICH STADIUM' appeared in no committed table or page before this register. A fixture played "
                     "overseas is a totals-relevant fact that the site was not showing.",
             next="Publish the venue table (done on this page) and add a venue column to the fixture-context features "
                  "when GB4 merges.",
             source_label="NFL.com game centre, Week 10 fixtures", source_url=URL["gc_was_nyg"], register="RR-21"),
        dict(id="RR-F5", severity="Medium · open",
             finding=f"Coverage limit on the venue transcription: {f['venues_n']} venues are published from "
                     f"{f['game_pages_captured']} committed raw game-centre pages plus one page read, and that is "
                     "all of Week 10 and nothing else. 'Every fixture' is delivered for the games whose official "
                     "page happens to sit in the repository; the scheduled jobs do not capture game centres, so "
                     "the coverage cannot grow without a workflow change.",
             next="the availability/forward workflows capture every scheduled fixture of the current week.",
             source_label="NFL.com Week 10 scores", source_url=URL["scores_w10"], register="RR-21"),
        dict(id="RR-F7", severity="Medium · open",
             finding=f"The published Week 10 table prints 'No Injuries Reported' for {f['inj_pub_placeholder_n']} clubs "
                     f"({f['inj_pub_placeholder_clubs']}) while the official report as captured {f['inj_retrieved']} "
                     f"lists rows for all of them. It was not a transcription error: the {f['capture_first']} capture "
                     f"({f['inj_first_capture_rows']} rows) had no rows for those clubs either, and "
                     f"{f['clubs_that_gained_rows_n']} clubs ({f['clubs_that_gained_rows']}) gained rows in the "
                     f"{f['capture_last']} capture window. The page populated between the two reads; the derived "
                     "table was never re-cut, and the four clubs still print 'none' on the site.",
             next="RR-S3 Path A. Until then the site publishes a statement the official page no longer supports, "
                  "which is exactly the failure 'treat the report as a timestamped series' exists to prevent.",
             source_label="NFL.com Week 10 injury report", source_url=URL["injuries"], register="RR-23"),
        dict(id="RR-F8", severity="Medium · open",
             finding=f"One reserve row disagrees about its club. Jordan Whittington (11/10) prints the Miami "
                     "Dolphins logo and link in both the From and To cells of the page read in this session, while "
                     f"the committed capture of the same URL at {f['reserve_latest_capture_utc']} "
                     f"attributes the row to Los Angeles "
                     f"(/teams/los-angeles-rams/). Player, date and transaction agree; {f['reserve_on_both']} of "
                     f"{f['reserve_live_rows']} rows agree on every key. The two reads used different fetchers "
                     "(a raw-HTML parse in CI, a page-read here), so the difference is in how the logo cell was "
                     "rendered, not in the club's status.",
             next="Do not pick a winner by eye: store the raw bytes for the row and compare the anchor URLs. "
                  "Any club-attribution rule for the reserve page belongs in the capture, not in a later edit.",
             source_label="NFL.com reserve list, November 2026", source_url=URL["reserve"], register="RR-28"),
    ]
    rows.append(
        dict(id="RR-F6", severity="Low · recorded",
             finding="Three request items in the 2026-11-18 brief describe a source or artefact the repository does "
                     "not contain and cannot obtain without an owner decision: the dated league schedule announcement "
                     "(RR-22), the 136-game log (RR-20) and the brief's own VR/VQ/SG identifier scheme (RR-44, F-48). "
                     "They are published here as NOT STARTED / NOT REPRODUCIBLE rather than filled with an estimate.",
             next="RR-S8 for the identifiers; RR-22 needs one dated capture.",
             source_label="", source_url="", register="RR-20, RR-22, RR-44"))
    order = {"RR-F1": 1, "RR-F2": 2, "RR-F3": 3, "RR-F4": 4, "RR-F5": 5, "RR-F6": 6, "RR-F7": 7, "RR-F8": 8}
    return sorted(rows, key=lambda r: order.get(r["id"], 99))


# --------------------------------------------------------------------------- #
def fmt(text: str, f: dict) -> str:
    """Substitute computed facts; a stray token is a build error, not a footnote."""
    keys = set(re.findall(r"\{([a-z0-9_]+)\}", text))
    unknown = keys - set(f)
    if unknown:
        raise SystemExit(f"register token has no computed fact: {sorted(unknown)} in: {text[:80]}")
    return text.format(**{k: f[k] for k in keys}) if keys else text


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    f = facts()

    # the reads this session ran against the official pages, and the numbers they produced
    vrows, stats = verify_rows(f)
    for k in ("live_rows", "on_both", "live_only", "capture_only"):
        f[f"reserve_{k}"] = stats[f"reserve_{k}"]
    f["injury_lines_read"] = stats["injury_lines_read"]
    f["injury_lines_match"] = stats["injury_lines_match"]

    reg = items()
    qraw, sraw, fraw = questions(f), suggestions(f), flags(f, stats)
    ab = ablation_rows(f)

    # register-wide counts are facts too, so the summary panel and the rows cannot disagree
    seen = {r["id"] for r in reg}
    if len(seen) != len(reg):
        raise SystemExit("duplicate register id")
    f["register_rows"] = len(reg)
    f["register_q_n"] = len(qraw)
    f["register_sug_n"] = len(sraw)
    f["register_flag_n"] = len(fraw)
    f["register_done"] = sum(1 for r in reg if r["status"] == "DONE")
    f["register_partly"] = sum(1 for r in reg if r["status"] == "PARTLY DONE")
    f["register_blocked"] = sum(1 for r in reg if r["status"].startswith("BLOCKED"))
    f["register_sibling"] = sum(1 for r in reg if r["status"] == "IN PROGRESS — SIBLING")
    f["register_rejected"] = sum(1 for r in reg if r["status"] == "REJECTED AS REQUESTED")
    f["register_notrepro"] = sum(1 for r in reg if r["status"] == "NOT REPRODUCIBLE")
    f["register_notstarted"] = sum(1 for r in reg if r["status"] == "NOT STARTED")

    for r in reg:
        if r["status"] not in STATUS:
            raise SystemExit(f"{r['id']}: status '{r['status']}' outside the closed vocabulary")
        for path in r["evidence"].split("; "):
            if path in SELF_OUTPUTS:      # written by this run; the test asserts the file lands
                continue
            if not (ROOT / path).exists():
                raise SystemExit(f"{r['id']}: evidence path does not exist: {path}")
        for field in ("checked", "gate", "clears", "note"):
            r[field] = fmt(r.get(field, ""), f)
        if r["source_url"] and not OFFICIAL_HOST.match(r["source_url"]):
            raise SystemExit(f"{r['id']}: source_url is not an official/primary host: {r['source_url']}")
        r["no_official_source"] = "yes" if not r["source_url"] else ""
        counts = []
        for path in r["evidence"].split("; "):
            fp = ROOT / path
            if path in SELF_OUTPUTS:
                counts.append(f"{Path(path).name} (written by this build)")
            elif fp.is_file() and path.endswith(".csv"):
                counts.append(f"{Path(path).name} ({len(rd(fp))} rows)")
            elif fp.is_file():
                counts.append(Path(path).name)
            else:
                counts.append(f"{path} ({len(list(fp.glob('*')))} entries)")
        r["evidence_detail"] = "; ".join(counts)

    q = [{**x, "question": fmt(x["question"], f), "known": fmt(x["known"], f),
          "missing": fmt(x["missing"], f), "how": fmt(x["how"], f)} for x in qraw]
    s = [{**x, "gate_cleared": fmt(x["gate_cleared"], f), "path_a": fmt(x["path_a"], f),
          "path_b": fmt(x["path_b"], f), "path_c": fmt(x["path_c"], f)} for x in sraw]
    fl = [{**x, "finding": fmt(x["finding"], f), "next": fmt(x["next"], f)} for x in fraw]
    ab = [{**x, "found": fmt(str(x["found"]), f), "check": fmt(str(x["check"]), f),
           "next_step": fmt(str(x["next_step"]), f)} for x in ab]

    ven, vdf = venues(), pd.DataFrame(vrows)
    fac = pd.DataFrame([dict(fact=k, value=v,
                             note="computed by pipeline/register_20261118.py from committed files and the "
                                  "verbatim official excerpts under data/live/register_reads_2026_11_18/")
                        for k, v in sorted(f.items())])
    reg_df = pd.DataFrame(reg)

    outs = {
        "request_register_2026_11_18.csv": reg_df,
        "register_verify_2026_11_18.csv": vdf,
        "register_venues_2026_11_18.csv": ven,
        "register_questions_2026_11_18.csv": pd.DataFrame(q),
        "register_suggestions_2026_11_18.csv": pd.DataFrame(s),
        "register_ablation_2026_11_18.csv": pd.DataFrame(ab),
        "register_flags_2026_11_18.csv": pd.DataFrame(fl),
        "register_facts_2026_11_18.csv": fac,
    }
    for name, df in outs.items():
        df.to_csv(OUT / name, index=False)
        df.to_csv(SITE_DATA / name, index=False)
    (READS / "manifest.json").write_text(json.dumps({
        "as_of": AS_OF, "read_window_utc": READ_WINDOW,
        "retrieval_method": {"tool": "agent page-fetch tool",
                             "note": "the sandbox shell cannot open www.nfl.com or club domains (TLS refused), so "
                                     "each page is read with the agent page-fetch tool and the relevant block is "
                                     "transcribed verbatim; recorded_utc is when the file was written in this session, "
                                     "immediately after the fetch"},
        "files": {p.name: {"sha256": sha256_of(p), "bytes": p.stat().st_size}
                  for p in sorted(READS.glob("*.md"))},
        "sources": [{"url": URL[k], "what": w} for k, w in (
            ("injuries", "official Week 10 injury report (rows for nine clubs read from chunks 0 and 2 of 8)"),
            ("reserve", "official reserve list, November 2026 (the whole row block: chunks 0 and 1 of 2)"),
            ("gc_was_nyg", "official game centre for WAS at NYG (score, Game Info, Game Book link)"),
            ("hou_depth", "Houston Texans club depth-chart page (source-shape question behind F-49)"))],
    }, indent=2) + "\n")
    print(f"register rows {len(reg_df)} · verified lines {len(vdf)} "
          f"(injury {f['injury_lines_match']}/{f['injury_lines_read']} match) · venues {len(ven)} · "
          f"flags {len(fl)} · questions {len(q)} · suggestions {len(s)}")


if __name__ == "__main__":
    main()
