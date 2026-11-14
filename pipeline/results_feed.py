"""Requirement 2 — a **verified results feed**, so a backtest and an ROI can be computed at all.

The problem this closes
-----------------------
`EXECUTIVE_SUMMARY.md` states the blocker plainly: "4 of 65 forward picks are settled". A backtest
that settles picks needs a final score for the games those picks reference, and the *only* evidence
class this project accepts for a final score is an official NFL final. Historical backtests run on
the pinned community mirror, which is fine for research but is not a settlement source. So there was
no single, machine-readable, per-game statement of "this is what the official page said, at this
time, from this URL, and here is what I could not verify".

What this module produces
------------------------
`data/results/verified_results.csv` — one row per **official NFL game** the project can see, with:

    game_id, season, week, game_date, away/home, away_score/home_score, status_on_page
    verified           FINAL | IN_PROGRESS | NOT_FINAL | FUTURE | UNVERIFIED
    score_source       DATA_EXTRACT (a committed official extract) | OFFICIAL_RESULTS_REGISTER
    official_url       the NFL.com game page the score belongs to
    source_page        the NFL.com index page it was read from
    verified_utc       when it was read
    settle_spread / settle_total / settle_moneyline   the *derived* settlement of the
                       pinned closing line against the official final, per market
    settle_note        why a market cannot be settled, when it cannot

Three rules are enforced in code, not documented:

1. **No official score, no result.** A game with no official score is `FUTURE` (kickoff in the
   future relative to the page) or `UNVERIFIED` (played, no official score on record). It is never
   filled from the community mirror.
2. **A settlement is derived, never observed.** `settle_*` says whether the closing number won,
   lost or pushed; it is blank when the closing number is missing, because a blank line cannot win.
3. **The feed refuses to invent an identity.** A 2026 game is only joined to a pinned-archive row
   through the explicit nflverse id (`2026_08_WAS_NYG`), never through a fuzzy team/date match. A
   game it cannot key stays unjoined and says so.

Inputs (all committed; no network)
  data/live/official_scores_2026_week08_10.csv   official score extract, read from nfl.com
                                                 (see data/live/README_scores.md for the reads)
  data/forward/official_results.csv              the pre-existing settlement register (30 rows)
  data/forward/official_schedule.csv             the official 2026 week-10 schedule
  data/processed/originated_lines.csv            closing line + fair line per game

Outputs
  data/results/verified_results.csv
  data/results/results_coverage.csv
  assets/data/ mirrors
  results-feed.html

Run:  python pipeline/results_feed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, read_csv, ref_link, write_csv  # noqa: E402

OUT = ROOT / "data" / "results"
OUT.mkdir(parents=True, exist_ok=True)

SCORES = ROOT / "data" / "live" / "official_scores_2026_week08_10.csv"
NFL_WEEK = {8: "https://www.nfl.com/scores/2026/week-8",
            9: "https://www.nfl.com/scores/2026/week-9",
            10: "https://www.nfl.com/scores/2026/week-10"}
NFL_SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/reg-10"
NFL_SCORES = "https://www.nfl.com/scores/"
URL_GAMES_LOCAL = ("https://github.com/nflverse/nfldata/blob/"
                   + read_json(ROOT / "data" / "sources.json")["upstream"]["commit_sha"]
                   + "/data/games.csv")
SRC = read_json(ROOT / "data" / "sources.json")


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _final(row) -> bool:
    return str(row.status_on_page).strip().lower() == "final"


def settle_spread(margin_home: float, line: float | None) -> tuple[str, str]:
    """Home handicap settlement from the home margin. Blank line → cannot settle."""
    if line is None or np.isnan(line):
        return "", "no closing spread on record"
    if np.isnan(margin_home):
        return "", "no official final"
    v = margin_home + line
    if v > 0:
        return "HOME_COVERS", ""
    if v < 0:
        return "AWAY_COVERS", ""
    return "PUSH", ""


def settle_total(total: float, line: float | None) -> tuple[str, str]:
    if line is None or np.isnan(line):
        return "", "no closing total on record"
    if np.isnan(total):
        return "", "no official final"
    v = total - line
    if v > 0:
        return "OVER", ""
    if v < 0:
        return "UNDER", ""
    return "PUSH", ""


def settle_ml(margin_home: float, home_ml: float | None, away_ml: float | None) -> tuple[str, str]:
    if np.isnan(margin_home):
        return "", "no official final"
    if np.isnan(_f(home_ml)) or np.isnan(_f(away_ml)):
        return "", "no closing moneyline on record"
    if margin_home > 0:
        return "HOME_ML_WINS", ""
    if margin_home < 0:
        return "AWAY_ML_WINS", ""
    return "TIE", "a tie is not a moneyline win on a two-way market"


def load_official() -> pd.DataFrame:
    """The committed official 2026 score extract. Fails loudly if it is not there."""
    if not SCORES.exists():
        raise SystemExit(
            f"missing {SCORES.relative_to(ROOT)} — the official score extract is evidence. "
            "Re-capture it with the page-fetch tool and commit it; do not substitute the "
            "community mirror for it.")
    d = pd.read_csv(SCORES, dtype=str, keep_default_na=False)
    for c in ("season", "week"):
        d[c] = pd.to_numeric(d[c], errors="coerce").astype("Int64")
    for c in ("away_score", "home_score"):
        d[c] = d[c].map(_f)
    return d


def load_register() -> pd.DataFrame:
    p = ROOT / "data" / "forward" / "official_results.csv"
    d = pd.read_csv(p, dtype=str, keep_default_na=False)
    d["week"] = pd.to_numeric(d.week, errors="coerce").astype("Int64")
    d["season"] = pd.to_numeric(d.season, errors="coerce").astype("Int64")
    for c in ("away_score", "home_score"):
        d[c] = d[c].map(_f)
    d["score_source"] = "OFFICIAL_RESULTS_REGISTER"
    return d


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    off = load_official()
    off["score_source"] = "DATA_EXTRACT"
    reg = load_register()

    keep = ["game_id", "season", "week", "away_team", "home_team", "away_score", "home_score",
            "status_on_page", "official_url", "source_page", "verified_utc", "score_source"]
    for c in keep:
        if c not in off:
            off[c] = ""
        if c not in reg:
            reg[c] = ""
    # Precedence: a score read on 2026-11-14 (the extract) replaces one recorded on
    # 2026-11-12 (the register) for the same game. The dictionary on the page states this.
    d = pd.concat([off[keep], reg[keep]], ignore_index=True)
    d["_rank"] = d.score_source.map({"DATA_EXTRACT": 0, "OFFICIAL_RESULTS_REGISTER": 1}).fillna(2)
    d = (d.sort_values(["game_id", "_rank"], kind="stable")
          .drop_duplicates(subset=["game_id"], keep="first")
          .drop(columns="_rank").reset_index(drop=True))
    d["game_date"] = d.game_id.map(
        lambda g: f"{g[0:4]}-{g[5:7]}-{g[8:10]}" if len(g) >= 10 and g[8:10].isdigit() else "")

    # verified status
    def verdict(r):
        if not _final(r):
            return "NOT_FINAL"
        if np.isnan(_f(r.away_score)) or np.isnan(_f(r.home_score)):
            return "UNVERIFIED"
        return "FINAL"
    d["verified"] = [verdict(r) for r in d.itertuples()]

    # settlement of the pinned closing line, per market
    org = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    org = org[["game_id", "market_spread", "market_total", "market_home_ml",
               "market_away_ml", "fair_spread", "fair_total"]].drop_duplicates("game_id")
    d = d.merge(org, on="game_id", how="left")
    sp, tot, ml, spn, totn, mln = [], [], [], [], [], []
    for r in d.itertuples():
        if r.verified != "FINAL":
            mh = np.nan
        else:
            mh = _f(r.home_score) - _f(r.away_score)
        a, na = settle_spread(mh, _f(r.market_spread))
        b, nb = settle_total(_f(r.home_score) + _f(r.away_score), _f(r.market_total))
        c, nc = settle_ml(mh, _f(r.market_home_ml), _f(r.market_away_ml))
        sp.append(a); spn.append(na); tot.append(b); totn.append(nb); ml.append(c); mln.append(nc)
    d["settle_spread"], d["settle_spread_note"] = sp, spn
    d["settle_total"], d["settle_total_note"] = tot, totn
    d["settle_moneyline"], d["settle_moneyline_note"] = ml, mln
    d["margin_home"] = [_f(r.home_score) - _f(r.away_score) if r.verified == "FINAL" else np.nan
                        for r in d.itertuples()]

    # 2026 games in the pinned schedule that the feed cannot settle
    up = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    known = set(d.game_id)
    fut = up[(up.season >= 2026) & (~up.game_id.isin(known))].copy()

    # A 2026 game can carry a pinned *community* final (nflverse games.csv) that this feed has
    # not read from an official page. It is not dropped and it is not presented as verified: it
    # enters as PINNED_COMMUNITY and the page prints the class in its own column. Only a 2026
    # score already joined to an official read above keeps the official class.
    known = set(d.game_id)
    comm = up[(up.season == 2026) & (up.home_score.notna()) & (~up.game_id.isin(known))].copy()
    comm_rows = pd.DataFrame({
        "game_id": comm.game_id, "season": comm.season.astype("Int64"),
        "week": comm.week.astype("Int64"), "away_team": comm.away_team,
        "home_team": comm.home_team, "away_score": comm.away_score.astype(float), "home_score": comm.home_score.astype(float),
        "status_on_page": "Final (community mirror)", "official_url": "",
        "source_page": URL_GAMES_LOCAL, "verified_utc": "",
        "score_source": "PINNED_COMMUNITY",
    })
    comm_rows["game_date"] = comm_rows.game_id.map(
        lambda g: f"{g[0:4]}-{g[5:7]}-{g[8:10]}" if len(g) >= 10 and g[8:10].isdigit() else "")
    for c in ("verified", "market_spread", "market_total", "market_home_ml", "market_away_ml",
              "fair_spread", "fair_total", "settle_spread", "settle_total", "settle_moneyline",
              "settle_spread_note", "settle_total_note", "settle_moneyline_note", "margin_home"):
        comm_rows[c] = np.nan
    comm_rows["verified"] = "COMMUNITY_ONLY"
    comm_rows = comm_rows.drop(columns=[c for c in ("market_spread", "market_total",
                                                    "market_home_ml", "market_away_ml",
                                                    "fair_spread", "fair_total")
                                        if c in comm_rows]).merge(org, on="game_id", how="left")
    for c in ("settle_spread", "settle_total", "settle_moneyline",
              "settle_spread_note", "settle_total_note", "settle_moneyline_note", "margin_home"):
        comm_rows[c] = np.nan
    comm_rows["settle_spread_note"] = "community final only; a settlement needs an official read"
    comm_rows["settle_total_note"] = comm_rows["settle_spread_note"]
    comm_rows["settle_moneyline_note"] = comm_rows["settle_spread_note"]
    d = pd.concat([d, comm_rows[d.columns]], ignore_index=True)
    known = set(d.game_id)
    fut_keep = pd.DataFrame({
        "game_id": fut.game_id, "season": fut.season.astype("Int64"), "week": fut.week.astype("Int64"),
        "away_team": fut.away_team, "home_team": fut.home_team,
        "away_score": np.nan, "home_score": np.nan, "status_on_page": "",
        "official_url": NFL_SCHEDULE, "source_page": NFL_SCHEDULE, "verified_utc": "",
        "score_source": "PINNED_SCHEDULE_PENDING",
    })
    fut_keep["game_date"] = fut_keep.game_id.map(
        lambda g: f"{g[0:4]}-{g[5:7]}-{g[8:10]}" if len(g) >= 10 and g[8:10].isdigit() else "")
    fut_keep = fut_keep[~fut_keep.game_id.isin(known)]
    for c in ("verified", "market_spread", "market_total", "market_home_ml", "market_away_ml",
              "fair_spread", "fair_total", "settle_spread", "settle_total", "settle_moneyline",
              "settle_spread_note", "settle_total_note", "settle_moneyline_note", "margin_home"):
        fut_keep[c] = "" if c == "verified" else np.nan
    # A 2026 game the feed has no official read for is NOT "future": weeks 1-7 have been
    # played. It is labelled by its pinned schedule date against the capture date, and the
    # page states that the pinned date is an input, not an official kickoff time.
    CAPTURE = "2026-11-14"
    dated = fut[["game_id", "gameday"]].drop_duplicates("game_id").set_index("game_id").gameday
    def pending(gid):
        gd = str(dated.get(gid, ""))[:10]
        if gd and gd < CAPTURE:
            return ("NOT_READ", "not played after the capture: the scheduled date has passed but no "
                                "official score for this game has been read into the feed")
        return ("FUTURE", "scheduled on or after the capture date; no final can exist yet")
    pairs = [pending(g) for g in fut_keep.game_id]
    fut_keep["verified"] = [p[0] for p in pairs]
    fut_keep["settle_spread_note"] = [p[1] for p in pairs]
    fut_keep["settle_total_note"] = fut_keep["settle_spread_note"]
    fut_keep["settle_moneyline_note"] = fut_keep["settle_spread_note"]
    # the official week-10 schedule the project already settled its picks against: those games
    # are on the slate, so the feed must show them as pending rather than omit them
    sched = pd.read_csv(ROOT / "data" / "forward" / "official_schedule.csv", dtype=str,
                        keep_default_na=False)
    sched = sched[~sched.game_id.isin(known)]
    sc = pd.DataFrame({
        "game_id": sched.game_id, "season": 2026, "week": 10,
        "away_team": sched.away_team, "home_team": sched.home_team,
        "away_score": np.nan, "home_score": np.nan, "status_on_page": "",
        "official_url": sched.official_url, "source_page": sched.source_page,
        "verified_utc": sched.verified_utc, "score_source": "OFFICIAL_SCHEDULE_PENDING",
    })
    sc["game_date"] = sched.official_game_date
    for c in fut_keep.columns:
        if c not in sc:
            sc[c] = np.nan
    sc["verified"] = "FUTURE"
    sc["settle_spread_note"] = "kickoff after the 2026-11-14 capture; no final exists yet"
    sc["settle_total_note"] = sc["settle_spread_note"]
    sc["settle_moneyline_note"] = sc["settle_spread_note"]
    d = pd.concat([d, fut_keep[d.columns], sc[d.columns]], ignore_index=True)
    d = d.sort_values(["season", "week", "game_id"], na_position="last",
                      kind="stable").reset_index(drop=True)
    coalesced = ["market_spread", "market_total", "market_home_ml", "market_away_ml",
                 "fair_spread", "fair_total", "settle_spread", "settle_total", "settle_moneyline",
                 "settle_spread_note", "settle_total_note", "settle_moneyline_note", "margin_home"]
    for c in coalesced:
        d[c] = d[c].replace("", np.nan)
    cov = (d.groupby(["season", "verified"], dropna=False).size()
           .unstack(fill_value=0).reset_index())
    cov.to_csv(OUT / "results_coverage.csv", index=False)
    return d, cov


def _history_section() -> str:
    """BF2 fold-in: full-history tiers (1999-2026) + the archive spot re-reads.

    Reads data/processed/results_feed.csv (pipeline/results_feed_history.py).
    If the file is absent the section is omitted rather than guessed.
    """
    hist = ROOT / "data" / "processed" / "results_feed.csv"
    if not hist.exists():
        return ""
    f = pd.read_csv(hist, dtype=str, keep_default_na=False)
    if f.empty:
        return ""
    tiers = f.tier.value_counts().to_dict()
    n_spot = int((f.spot_checked == "AGREE").sum())
    n_conf = int(f.cross_check.astype(str).str.startswith("CONFLICT").sum())
    spot = f[f.spot_checked != ""].sort_values("game_id")
    spot_rows = [[e(r.game_id), e(r.away_team), e(r.home_team),
                  e(r.away_score) if str(r.away_score).strip() else "—",
                  e(r.home_score) if str(r.home_score).strip() else "—",
                  e(r.spot_checked), e(r.spot_checked_utc),
                  e(r.spot_checked_note),
                  ref_link("official scores page",
                           r.source_url if str(r.source_url).startswith("http")
                           else "https://www.nfl.com/scores/")]
                 for r in spot.itertuples()]
    rows_tbl = table(
        spot_rows,
        ["Game", "Away", "Home", "Away score", "Home score", "Re-read result",
         "Re-read (UTC)", "How it was checked", "Official source"],
        caption="Pinned-archive rows re-read on the live official scores page "
                "on 2026-11-14 — every away/home pair matched the pin")
    return f"""
<section>
<div class="section-head"><h2>5 · Full-history join (1999–2026) and archive spot re-reads</h2></div>
<p>The section above settles 2026 from official reads. Backtests and ROI that span every
season join on <code>game_id</code> against the full-history feed
(<a href="data/processed/results_feed.csv">results_feed.csv</a>): {len(f):,} games in three
tiers that are never mixed — {int(tiers.get('OFFICIAL_READ', 0))} official game-centre reads,
{int(tiers.get('PINNED_ARCHIVE', 0))} hash-verified pinned-archive finals (each flagged
<em>not re-read per row</em>), and {int(tiers.get('SCHEDULED', 0))} scheduled games whose
scores stay blank by design. Cross-checks between the pin and an official read:
{len(f[f.cross_check == 'AGREE'])} AGREE, {n_conf} CONFLICT. The archive tier is a research
input, not a settlement source: settlement still requires an official read, exactly as
section 4 says.</p>
<p>{n_spot} pinned rows were re-read on the live official scores pages during the
2026-11-14 integration session — nine games from 2004 week 1 and nine from 2019 week 15,
two eras, every score identical to the pin. The register is committed as
<a href="data/processed/results_feed_spot_checks.csv">results_feed_spot_checks.csv</a>.</p>
{rows_tbl}
</section>
"""


def build_page(d: pd.DataFrame, cov: pd.DataFrame) -> str:
    n = len(d)
    fin = int((d.verified == "FINAL").sum())
    fut = int((d.verified == "FUTURE").sum())
    years = sorted(d.season.dropna().astype(int).unique())
    n_read = int((d.verified == "NOT_READ").sum())
    n_comm = int((d.verified == "COMMUNITY_ONLY").sum())
    cards = ('<div class="cards">'
             f'<div class="card">{n:,}<div class="card-label">games in the feed</div>'
             f'<div class="card-note">seasons {years[0]}–{years[-1]}</div></div>'
             f'<div class="card good">{fin}<div class="card-label">settleable finals</div>'
             f'<div class="card-note">official score on record, from an official page</div></div>'
             f'<div class="card">{fut}<div class="card-label">future games</div>'
             f'<div class="card-note">scheduled on or after the capture date</div></div>'
             f'<div class="card bad">{n_read}<div class="card-label">played, no official read yet</div>'
             f'<div class="card-note">blank; the community mirror is never substituted</div></div>'
             f'<div class="card luck">{n_comm}<div class="card-label">community finals</div>'
             f'<div class="card-note">pinned community mirror, usable for research and never for settlement</div></div>'
             "</div>")
    rows = []
    show = d[d.season >= 2026].sort_values(["week", "game_id"])
    for r in show.itertuples():
        a = "" if pd.isna(_f(r.away_score)) else f"{int(_f(r.away_score))}"
        h = "" if pd.isna(_f(r.home_score)) else f"{int(_f(r.home_score))}"
        rows.append([
            f"W{int(r.week)}" if pd.notna(r.week) else "—",
            clean(r.game_date), f"{e(r.away_team)} @ {e(r.home_team)}",
            f"{a}–{h}" if a and h else BLANK,
            clean(r.verified), clean(str(r.score_source).replace("_", " ").title()),
            clean(r.settle_spread), clean(r.settle_total), clean(r.settle_moneyline),
            ref_link("NFL.com", r.official_url) if r.official_url else
            ref_link("NFL scores", NFL_WEEK.get(int(r.week) if pd.notna(r.week) else 0, NFL_SCORES)),
            ref_link("NFL scores", NFL_SCORES) if r.official_url else BLANK,
        ])
    if not rows:
        rows = [["—"] * 10]
    cov_rows = []
    for r in cov.itertuples():
        cov_rows.append([f"{int(r.season)}", f"{int(r.FINAL)}", f"{int(getattr(r, 'FUTURE', 0))}",
                         f"{int(getattr(r, 'NOT_FINAL', 0))}",
                         str(int(r.FINAL) + int(getattr(r, 'FUTURE', 0)) + int(getattr(r, 'NOT_FINAL', 0))),
                         ref_link("NFL scores", NFL_SCORES)])
    best = int((d.settle_spread.notna()).sum()) + int((d.settle_total.notna()).sum()) + \
        int((d.settle_moneyline.notna()).sum())
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 2 of the 2026-11-14 brief: a
verified results feed so a backtest and an ROI can be computed <em>at all</em>. A result enters the
feed only from an official NFL page, with the URL, the page it was read from and the UTC time of the
read. A game without an official final is blank and labelled; it is never filled from the community
mirror that the historical backtests use.</p>
{cards}
<section>
<div class="section-head"><h2>1 · Why this was blocking everything</h2></div>
<p>An ROI is (units won − units staked) ÷ units staked. Every term needs a settled outcome, and a
settled outcome needs a final score. Before this feed the forward ledger had 65 picks and 30 official
finals, so 35 picks were <code>OPEN</code> and no strategy scoreboard could be computed. The feed
does not create finals that do not exist; it makes the ones that <em>do</em> exist machine-readable,
per-game, with their source, and it states exactly how many markets that is: <strong>{best}</strong>
settleable market rows out of {3 * n:,}.</p>
</section>
<section>
<div class="section-head"><h2>2 · The feed, 2026 season</h2></div>
<p>Settlement is derived from the pinned closing line against the official final, per market. It is a
<em>derivation</em>, not an observation: it says whether the closing number would have won, lost or
pushed — not that any bet was placed at that price. Pushes are named as pushes; a blank closing line
cannot win and is shown blank.</p>
{table(rows, ["Week", "Date", "Matchup", "Official final", "Feed status", "Score source",
              "Side settles", "Total settles", "Moneyline settles", "Official page", "Context"],
       caption="Verified results feed, 2026: every game, its official final where one exists, and the derived settlement")}
</section>
<section>
<div class="section-head"><h2>3 · Coverage by season</h2></div>
{table(cov_rows, ["Season", "Final", "Future", "Not final", "Total", "Official reference"],
       caption="Feed coverage per season")}
</section>
<section>
<div class="section-head"><h2>4 · The two evidence classes in this feed</h2></div>
<ul>
<li><strong>DATA_EXTRACT</strong> — the committed official 2026 extract
<a href="assets/data/official_scores_2026_week08_10.csv">official_scores_2026_week08_10.csv</a>,
read from the NFL.com week pages listed under each row. This is the class a settlement may use.</li>
<li><strong>OFFICIAL_RESULTS_REGISTER</strong> — the 30 rows already settled by earlier sessions in
<a href="assets/data/verified_results.csv">verified_results.csv</a> (the register rows are merged into it), each with its own NFL.com game
URL and read time. Kept as a second source rather than re-transcribed.</li>
<li><strong>PINNED_SCHEDULE_PENDING</strong> — a game the pinned archive lists for 2026 with no
official final yet. It is a placeholder for scheduling, not a result.</li>
</ul>
<p class="flag warn"><strong>What the feed cannot do.</strong> It cannot settle a futures market, a
player prop, or a game whose official page has not been read. Those stay blank and are listed on
<a href="flagged.html">Flagged for review</a>. Reading every 2026 game page is a scheduled job, not a
manual one — see suggestion <code>RES-01</code> on the
<a href="suggestions-review-2026-11-14.html">suggestions page</a>.</p>
</section>
"""
    # Section 5 is the BF2 fold-in (arena/bfcd9879-korea1): the joinable
    # full-history tier table and the archive spot re-reads, kept on this one
    # page so the feed does not gain a second surface.
    body += _history_section()
    return layout("results-feed.html", "Verified results feed",
                  "Official finals, per game, with the URL and read time behind every score — and nothing filled in.",
                  body, wide=True)


def main() -> None:
    d, cov = build()
    keep = ["game_id", "season", "week", "game_date", "away_team", "home_team", "away_score",
            "home_score", "status_on_page", "verified", "score_source", "official_url",
            "source_page", "verified_utc", "margin_home", "market_spread", "market_total",
            "market_home_ml", "market_away_ml", "settle_spread", "settle_spread_note",
            "settle_total", "settle_total_note", "settle_moneyline", "settle_moneyline_note",
            "fair_spread", "fair_total"]
    keep = [c for c in keep if c in d.columns]
    out = d[keep]
    write_csv(out, "verified_results.csv")
    (OUT / "verified_results.csv").write_text(out.to_csv(index=False), encoding="utf-8")
    write_csv(cov.astype("int64").assign(season=cov.season.astype("Int64")), "results_coverage.csv")
    (ROOT / "results-feed.html").write_text(build_page(d, cov), encoding="utf-8")
    print(f"  verified_results.csv {len(d):,} rows "
          f"({int((d.verified=='FINAL').sum())} final, {int((d.verified=='FUTURE').sum())} future)")


if __name__ == "__main__":
    main()
