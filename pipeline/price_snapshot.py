"""Requirement 1 — a price-snapshot store: **opening and closing numbers for every originated market.**

Why this module exists
----------------------
The site already published a model line (`data/processed/originated_lines.csv`) but no price
*snapshot*: there was one column per market and no record of when a number was taken, so no reader
could tell an opener from a closer, and no backtest could separate the price the model was
originated against from the price the game actually closed at. That is the first requirement in the
2026-11-14 brief.

What is recorded
----------------
One row per (game, market, side) with, for each of two snapshot points, the number and the price:

    market   SIDE | TOTAL | MONEYLINE            (the three markets requirement 3 orders)
    side     HOME | AWAY | OVER | UNDER
    open_*   the earliest number the pinned archive carries for that game/market/side
    close_*  the latest number the pinned archive carries for that game/market/side
    open_source, close_source   the exact pinned URL the value came from
    open_book, close_book       which book or consensus the pinned file names
    provenance                  OFFICIAL_SCHEDULE | PINNED_COMMUNITY | MODEL_ONLY | MISSING
    n_markets, markets_originated, markets_snapshotted   per game

`provenance` is not decoration. The repository's evidence policy is that a community price is
never described as an official observation, so each value carries the class it belongs to and the
page that publishes it prints that class in its own column. A value the pinned archive does not
carry is **blank**, never zero and never interpolated from a neighbouring week.

Sources, and exactly what each one can support
----------------------------------------------
1. **nflverse/nfldata, pinned commit** (`data/sources.json` → `upstream.commit_sha`). This is a
   community mirror; it is hash-pinned and reproducible but it is **not** an official NFL source.
   * `closing_lines.csv` — per-side `line` + `odds` for SPREAD, TOTAL and MONEYLINE, 2006–2018.
     The spread/total **odds are mostly blank in that file** (5,820 of 6,830 spread rows carry no
     price), so a closing *number* exists far more often than a closing *price*. The module records
     that distinction instead of hiding it: `close_price` is blank where the file is blank, and the
     page reports the price-coverage count.
   * `initial_lines.csv` — 2021 openers only, one book (`WSGT`), SPREAD and TOTAL, **no** prices.
   * `sc_lines.csv` — SuperContest consensus lines 2013–2020, spread only, **no** prices.
   * `games.csv` — the closing spread/total/moneyline used as a cross-check, and the official
     schedule identity (date, kickoff, teams) that ties a snapshot row to a game.
2. **The model's own origination** (`data/processed/originated_lines.csv`): the fair number the
   model published, and the market number it was originated against. This is a MODEL_ONLY row: it
   is not an observed price and is never counted as one.

The three archive files overlap only in 2013–2018 and only for the spread, so the honest statement
is not "we have open and close for every market". It is: **every originated market has a snapshot
row**, and each row says which of its two endpoints is populated, from which file, and at what
price coverage. The page `price-store.html` prints those counts, and the gaps are listed on
`flagged.html`.

Outputs
  data/prices/price_snapshots.csv        the store (one row per game/market/side/snapshot)
  data/prices/price_snapshot_coverage.csv  per market: endpoint and price coverage
  data/prices/price_snapshot_gaps.csv    every originated market with a missing endpoint
  assets/data/ mirrors of all three
  price-store.html

Run:  python pipeline/price_snapshot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, resolve_ref, write_csv  # noqa: E402

URL_NFL = "https://www.nfl.com/scores/"
OUT = ROOT / "data" / "prices"
OUT.mkdir(parents=True, exist_ok=True)

SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
BASE = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/"
URL_CLOSING = BASE + "closing_lines.csv"
URL_INITIAL = BASE + "initial_lines.csv"
URL_SCLINES = BASE + "sc_lines.csv"
URL_GAMES = BASE + "games.csv"

MARKET_ORDER = ["SIDE", "TOTAL", "MONEYLINE"]
SIDE_ORDER = {"SIDE": ["HOME", "AWAY"], "TOTAL": ["OVER", "UNDER"],
              "MONEYLINE": ["HOME", "AWAY"]}
MARKET_LABEL = {"SIDE": "Side (spread)", "TOTAL": "Total", "MONEYLINE": "Moneyline"}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return v if np.isfinite(v) else np.nan


def _blank(x) -> str:
    """Blank cell that prints as an em dash and is explicitly not zero."""
    return BLANK if x is None or (isinstance(x, float) and np.isnan(x)) or str(x).strip() == "" else str(x)


# --------------------------------------------------------------------------- #
# 1. The archive extracts
# --------------------------------------------------------------------------- #
def load_games() -> pd.DataFrame:
    g = pd.read_csv(RAW / "games.csv", low_memory=False)
    g = g[["game_id", "season", "week", "game_type", "gameday", "gametime",
           "home_team", "away_team", "home_score", "away_score", "spread_line",
           "total_line", "home_moneyline", "away_moneyline"]].copy()
    # nflverse game_id is "2026_08_WAS_NYG"; closing_lines.csv uses the GSIS id.
    g["alt"] = g.game_id
    return g


def load_closing(games: pd.DataFrame) -> pd.DataFrame:
    """closing_lines.csv → one row per (alt_game_id, market, side) with line and odds."""
    c = pd.read_csv(RAW / "closing_lines.csv", dtype=str, keep_default_na=False)
    c["alt"] = c.alt_game_id
    # The GSIS `game_id` in this file has no join key in games.csv (games.csv carries
    # both); keep the nflverse alt id, which is the key every other table uses.
    c = c[["alt", "type", "side", "line", "odds"]].copy()
    # the pinned file writes a missing value as an empty string; a blank price is not 0
    for col in ("line", "odds"):
        c[col] = c[col].replace("", np.nan).map(_num)
    c["market"] = c["type"].map({"SPREAD": "SIDE", "TOTAL": "TOTAL", "MONEYLINE": "MONEYLINE"})
    c = c.dropna(subset=["market"])
    home = games.set_index("alt")[["home_team", "away_team"]]
    c = c.join(home, on="alt")
    side = []
    for r in c.itertuples():
        s = str(r.side).upper()
        if r.market == "TOTAL":
            side.append(s if s in ("OVER", "UNDER") else None)
        elif s == str(r.home_team).upper():
            side.append("HOME")
        elif s == str(r.away_team).upper():
            side.append("AWAY")
        else:
            side.append(None)  # e.g. a neutral-site designation we do not recognise
    c["side_key"] = side
    c = c.dropna(subset=["side_key"])
    return c.groupby(["alt", "market", "side_key"], as_index=False).agg(
        close_line=("line", "first"), close_price=("odds", "first"))


def load_sclines(games: pd.DataFrame) -> pd.DataFrame:
    """SuperContest consensus spread lines 2013–2020 → an *open* endpoint for SIDE."""
    s = pd.read_csv(RAW / "sc_lines.csv", dtype=str, keep_default_na=False)
    s["line"] = s["line"].replace("", np.nan).map(_num)
    s["season"] = s.season.astype(int)
    s["week"] = pd.to_numeric(s.week, errors="coerce")
    g = games.copy()
    s = s.merge(g[["alt", "season", "week", "home_team", "away_team"]],
                left_on=["season", "week", "home_team", "away_team"],
                right_on=["season", "week", "home_team", "away_team"], how="left")
    s = s.dropna(subset=["alt"])
    side = []
    for r in s.itertuples():
        t = str(r.side).upper()
        side.append("HOME" if t == str(r.home_team).upper()
                    else "AWAY" if t == str(r.away_team).upper() else None)
    s["side_key"] = side
    s = s.dropna(subset=["side_key"])
    return s.groupby(["alt", "side_key"], as_index=False).agg(open_line=("line", "first"))


def load_initial(games: pd.DataFrame) -> pd.DataFrame:
    """2021 openers (book WSGT), SPREAD + TOTAL, no prices."""
    i = pd.read_csv(RAW / "initial_lines.csv", dtype=str, keep_default_na=False)
    i["line"] = i["line"].replace("", np.nan).map(_num)
    i["season"] = i.season.astype(int)
    g = games[games.season == 2021].copy()
    # initial_lines.csv keys on "2021_01_DAL_TB" which is the nflverse alt id itself.
    i["alt"] = i["about"]
    i = i.merge(g[["alt", "home_team", "away_team"]], on="alt", how="left")
    i = i.dropna(subset=["home_team"])
    side = []
    for r in i.itertuples():
        s = str(r.side).upper()
        if r.type == "TOTAL":
            side.append(s if s in ("OVER", "UNDER") else None)
        elif s == str(r.home_team).upper():
            side.append("HOME")
        elif s == str(r.away_team).upper():
            side.append("AWAY")
        else:
            side.append(None)
    i["side_key"] = side
    i = i.dropna(subset=["side_key"])
    i["market"] = i["type"].map({"SPREAD": "SIDE", "TOTAL": "TOTAL"})
    return i.groupby(["alt", "market", "side_key"], as_index=False).agg(
        open_line=("line", "first"))


# --------------------------------------------------------------------------- #
# 2. The model's origination, in the required market order
# --------------------------------------------------------------------------- #
def load_origination() -> pd.DataFrame:
    o = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    o = o[["game_id", "season", "week", "home_team", "away_team", "fair_spread",
           "fair_total", "originated_home_ml", "originated_away_ml",
           "market_spread", "market_total", "market_home_ml", "market_away_ml"]].copy()
    o["alt"] = o.game_id
    rows = []
    for r in o.itertuples():
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="SIDE", side_key="HOME", fair=r.fair_spread,
                         market_at_origination=r.market_spread,
                         order=0))
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="SIDE", side_key="AWAY",
                         fair=(np.nan if pd.isna(r.fair_spread) else -float(r.fair_spread)),
                         market_at_origination=(np.nan if pd.isna(r.market_spread)
                                                else -float(r.market_spread)),
                         order=0))
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="TOTAL", side_key="OVER", fair=r.fair_total,
                         market_at_origination=r.market_total, order=1))
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="TOTAL", side_key="UNDER", fair=r.fair_total,
                         market_at_origination=r.market_total, order=1))
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="MONEYLINE", side_key="HOME",
                         fair=r.originated_home_ml,
                         market_at_origination=r.market_home_ml, order=2))
        rows.append(dict(alt=r.alt, game_id=r.game_id, season=r.season, week=r.week,
                         home_team=r.home_team, away_team=r.away_team,
                         market="MONEYLINE", side_key="AWAY",
                         fair=r.originated_away_ml,
                         market_at_origination=r.market_away_ml, order=2))
    d = pd.DataFrame(rows)
    d["market"] = pd.Categorical(d.market, MARKET_ORDER, ordered=True)
    return d


# --------------------------------------------------------------------------- #
# 3. Assemble
# --------------------------------------------------------------------------- #
def build() -> pd.DataFrame:
    games = load_games()
    closing = load_closing(games)
    sc = load_sclines(games)
    init = load_initial(games)
    org = load_origination()

    d = org.merge(closing, on=["alt", "market", "side_key"], how="left")

    # opening endpoint: 2013–2020 spread from SuperContest, 2021 spread+total from WSGT.
    op = pd.concat([
        sc.assign(market="SIDE")[["alt", "market", "side_key", "open_line"]],
        init[["alt", "market", "side_key", "open_line"]],
    ], ignore_index=True).drop_duplicates(subset=["alt", "market", "side_key"], keep="first")
    d = d.merge(op, on=["alt", "market", "side_key"], how="left")

    # the games.csv closing number is an independent cross-check of closing_lines.csv
    gx = games.set_index("alt")
    cross = []
    for r in d.itertuples():
        if r.alt not in gx.index:
            cross.append(np.nan)
            continue
        row = gx.loc[r.alt]
        if r.market == "SIDE":
            v = row.spread_line
            cross.append(np.nan if pd.isna(v) else (float(v) if r.side_key == "HOME" else -float(v)))
        elif r.market == "TOTAL":
            cross.append(row.total_line)
        else:
            cross.append(row.home_moneyline if r.side_key == "HOME" else row.away_moneyline)
    d["games_csv_closing"] = cross

    # provenance, per value
    def prov(r):
        has_open = pd.notna(r.open_line)
        has_close = pd.notna(r.close_line)
        return has_open, has_close

    provs, books, notes = [], [], []
    for r in d.itertuples():
        has_open, has_close = prov(r)
        if has_open and r.market == "SIDE" and int(r.season) <= 2020:
            open_src, open_book = URL_SCLINES, "SuperContest consensus"
        elif has_open and int(r.season) == 2021:
            open_src, open_book = URL_INITIAL, "WSGT"
        else:
            open_src, open_book = None, None
        close_src = URL_CLOSING if has_close else None
        close_book = "closing_lines.csv (unattributed)" if has_close else None
        if has_open and has_close:
            p = "PINNED_COMMUNITY_OPEN_AND_CLOSE"
        elif has_close:
            p = "PINNED_COMMUNITY_CLOSE_ONLY"
        elif has_open:
            p = "PINNED_COMMUNITY_OPEN_ONLY"
        elif pd.notna(r.fair) or pd.notna(r.market_at_origination):
            p = "MODEL_ONLY"
        else:
            p = "MISSING"
        provs.append(p)
        books.append((open_book, close_book))
        n = []
        if not has_open:
            n.append("no pinned opener for this market/season")
        if not has_close:
            n.append("no pinned closer for this market/season")
        if has_close and pd.isna(_num(r.close_price)) and r.market != "SIDE":
            n.append("closer carries a number but no price in the pinned file")
        if has_close and r.market == "SIDE" and pd.isna(_num(r.close_price)):
            n.append("closer carries a number but no price in the pinned file")
        notes.append("; ".join(n))
    d["provenance"] = provs
    d["open_book"] = [b[0] for b in books]
    d["close_book"] = [b[1] for b in books]
    d["open_source"] = [URL_SCLINES if p in ("PINNED_COMMUNITY_OPEN_AND_CLOSE", "PINNED_COMMUNITY_OPEN_ONLY") and r.market == "SIDE" and int(r.season) <= 2020
                        else URL_INITIAL if p in ("PINNED_COMMUNITY_OPEN_AND_CLOSE", "PINNED_COMMUNITY_OPEN_ONLY") else None
                        for p, r in zip(provs, d.itertuples())]
    d["close_source"] = [URL_CLOSING if p in ("PINNED_COMMUNITY_OPEN_AND_CLOSE", "PINNED_COMMUNITY_CLOSE_ONLY") else None
                         for p in provs]
    d["note"] = notes
    d["side"] = d.side_key
    # an archive row's date is the *archive* date, not the game date. Join the pinned schedule so
    # a reader can see when the game was actually played and age the number correctly.
    gsched = games.set_index("alt")[["gameday", "gametime"]]
    d["kickoff_date"] = d.alt.map(lambda a: gsched.loc[a, "gameday"] if a in gsched.index else None)
    d["official_schedule"] = URL_GAMES
    d = d.sort_values(["season", "week", "game_id", "order", "side_key"],
                      kind="stable").reset_index(drop=True)
    return d


def coverage(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for m in MARKET_ORDER:
        s = d[d.market == m]
        rows.append(dict(
            market=m, market_label=MARKET_LABEL[m],
            originated_rows=len(s), games=s.game_id.nunique(),
            open_line=s.open_line.notna().sum(),
            close_line=(s.close_line.notna() | s.close_price.notna()).sum(),
            open_price=s.open_price.notna().sum() if "open_price" in s else 0,
            close_price=s.close_price.notna().sum(),
            both=s[(s.open_line.notna()) & (s.close_line.notna())].shape[0],
            model_only=(s.provenance == "MODEL_ONLY").sum(),
            official_rows=0,
            seasons=f"{int(s.season.min())}–{int(s.season.max())}",
        ))
    return pd.DataFrame(rows)


def gaps(d: pd.DataFrame) -> pd.DataFrame:
    g = d[d.provenance.isin(["MODEL_ONLY", "MISSING", "PINNED_COMMUNITY_CLOSE_ONLY"])].copy()
    has_close = g.close_line.notna() | g.close_price.notna()
    g["missing"] = np.where(g.open_line.isna() & has_close, "opener",
                            np.where(g.open_line.isna() & ~has_close, "opener and closer",
                                     "closer"))
    out = g[["market", "season", "week", "game_id", "side_key", "provenance", "missing", "note"]]
    return out.rename(columns={"side_key": "side"})


# --------------------------------------------------------------------------- #
# 4. Render
# --------------------------------------------------------------------------- #
def build_page(d: pd.DataFrame, cov: pd.DataFrame, gap: pd.DataFrame) -> str:
    total = len(d)
    both = int((d.open_line.notna() & d.close_line.notna()).sum())
    official = int((d.provenance == "OFFICIAL").sum()) if (d.provenance == "OFFICIAL").any() else 0
    cards = (
        '<div class="cards">'
        f'<div class="card">{total}<div class="card-label">originated market rows</div>'
        f'<div class="card-note">side, total and moneyline · {d.game_id.nunique():,} games</div></div>'
        f'<div class="card">{both:,}<div class="card-label">rows with open and close</div>'
        f'<div class="card-note">both endpoints populated from the pinned archive</div></div>'
        f'<div class="card bad">{total - both:,}<div class="card-label">rows with a missing endpoint</div>'
        f'<div class="card-note">listed on the gaps table and on Flagged for review</div></div>'
        f'<div class="card bad">{official}<div class="card-label">official price snapshots</div>'
        f'<div class="card-note">no official price feed is reachable from this build; every value is a pinned community mirror or a model estimate</div></div>'
        "</div>"
    )
    cov_rows = [[clean(r.market_label), f"{r.originated_rows:,}", f"{r.open_line:,}",
                 f"{r.close_line:,}", f"{r.close_price:,}", f"{r.both:,}", f"{r.model_only:,}",
                 clean(r.seasons), ref_link("NFL scores", URL_NFL),
                 ref_link("closing_lines.csv", URL_CLOSING)]
                for r in cov.itertuples()]

    def fmt(v, price=False):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return BLANK
        if price:
            iv = int(round(float(v)))
            return f"{iv:+d}" if iv else BLANK
        return f"{float(v):+.1f}"

    sample = d[(d.season >= 2026)].copy()
    if sample.empty:
        sample = d.sort_values(["season", "week"], ascending=False).head(36)
    rows = []
    for r in sample.itertuples():
        rows.append([
            f"W{int(r.week)}", e(r.game_id.split("_", 3)[-1].replace("_", " @ ")),
            clean(MARKET_LABEL[r.market]), clean(r.side),
            fmt(r.open_line), fmt(r.close_line),
            BLANK, fmt(r.close_price, True),
            fmt(r.market_at_origination, r.market == "MONEYLINE"),
            fmt(r.fair, r.market == "MONEYLINE"),
            clean(r.provenance.replace("_", " ").title()),
            ref_link("NFL scores", URL_NFL), ref_link("closing", URL_CLOSING),
        ])
    if not rows:
        rows = [["—"] * 13]

    gap_rows = [[clean(r.market), f"{int(r.season)} W{int(r.week)}", e(r.game_id),
                 clean(r.side), clean(r.provenance), clean(r.missing), clean(r.note),
                 ref_link("NFL scores", URL_NFL), ref_link("closing_lines.csv", URL_CLOSING)]
                for r in gap.head(60).itertuples()]

    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 1 of the 2026-11-14 brief: a
price-snapshot store that records an <em>opening</em> and a <em>closing</em> number for every market
this project originates. It is built from the pinned archive only — no value is typed in, and no
value is inferred across weeks. Every row names the file its number came from and the evidence class
that file belongs to.</p>
{cards}
<section>
<div class="section-head"><h2>1 · What the store can and cannot say</h2></div>
<p>The pinned archive is not a price feed. Three separate files each carry one endpoint, and they
overlap only in 2013–2018 and only for the spread. So the correct statement is <strong>not</strong>
"opening and closing for every market" — it is that every originated market has a snapshot row, and
each row carries the endpoints the archive can actually support:</p>
<ul>
<li><strong>Side (spread)</strong> — opener from SuperContest consensus 2013–2020
({ref_link("sc_lines.csv", URL_SCLINES)}) or WSGT 2021 ({ref_link("initial_lines.csv", URL_INITIAL)});
closer from {ref_link("closing_lines.csv", URL_CLOSING)} 2006–2018.</li>
<li><strong>Total</strong> — opener limited to the 2021 WSGT file; closer from
{ref_link("closing_lines.csv", URL_CLOSING)} 2006–2018.</li>
<li><strong>Moneyline</strong> — closer only, from {ref_link("closing_lines.csv", URL_CLOSING)};
no pinned opener exists in any of the three files.</li>
</ul>
<p><strong>Prices are much rarer than numbers.</strong> In <code>closing_lines.csv</code> the
spread and total <code>odds</code> column is blank for most rows, so a closing <em>number</em> is
available far more often than a closing <em>price</em>. The coverage table below counts each
separately rather than implying a price exists wherever a number does. That shortage is the same
blocker the validation gates name (G1): without a timestamped executable price, no strategy can be
called validated.</p>
</section>
<section>
<div class="section-head"><h2>2 · Coverage by market</h2></div>
{table(cov_rows, ["Market", "Rows", "Opening number", "Closing number", "Closing price",
                  "Open + close", "Model-only", "Seasons", "Official source", "Pinned source"],
       caption="Snapshot coverage per market. A number is not a price; they are counted separately.")}
</section>
<section>
<div class="section-head"><h2>3 · 2026 board — every originated market, in the required order</h2></div>
<p>Side first, then total, then moneyline (requirement 3). <em>Open</em> is blank for the 2026 board
because no pinned file carries a 2026 opener; the opener column is blank, not zero, and the row says
so in its provenance cell.</p>
{table(rows, ["Week", "Game", "Market", "Side", "Open", "Close", "Open price", "Close price",
              "Market at origination", "Model fair", "Provenance", "Official source", "Archive input"],
       caption="2026 originated markets with the snapshot endpoints the pinned archive can support")}
</section>
<section>
<div class="section-head"><h2>4 · Gaps: every originated market with a missing endpoint</h2></div>
<p>This is the work queue for the store. It is published, not hidden: {len(gap):,} rows have at
least one endpoint the archive cannot populate. Closing the gap needs a licensed price feed with a
timestamp per quote (suggestion PRICE-01 on <a href="suggestions-review-2026-11-14.html">the suggestions page</a>),
not another community mirror — a mirror cannot prove a price was executable.</p>
{table(gap_rows, ["Market", "Season/week", "Game", "Side", "Provenance", "Missing", "Why",
                  "Official source", "Archive input"],
       caption="Originated markets with at least one missing endpoint (first 60 shown)")}
<p class="flag warn">Unverified values are blank. Nothing here is drawn from a future row, an
adjacent week, or a line the archive does not carry.</p>
</section>
<section>
<div class="section-head"><h2>5 · Downloads and reproducibility</h2></div>
<ul>
<li><a href="assets/data/price_snapshots.csv">price_snapshots.csv</a> — the store, one row per
game / market / side.</li>
<li><a href="assets/data/price_snapshot_coverage.csv">price_snapshot_coverage.csv</a> — the counts
above.</li>
<li><a href="assets/data/price_snapshot_gaps.csv">price_snapshot_gaps.csv</a> — the gap queue.</li>
<li>Rebuild: <code>python pipeline/price_snapshot.py</code> (no network; reads the pinned files
under <code>data/raw/</code>).</li>
</ul>
</section>
"""
    return layout("price-store.html", "Price-snapshot store",
                  "Opening and closing numbers for every originated market, with the evidence class of each value.",
                  body, wide=True)


def main() -> None:
    d = build()
    cov = coverage(d)
    gap = gaps(d)
    write_csv(d, "price_snapshots.csv")
    write_csv(cov, "price_snapshot_coverage.csv")
    write_csv(gap, "price_snapshot_gaps.csv")
    (OUT / "price_snapshots.csv").write_text(d.to_csv(index=False), encoding="utf-8")
    (OUT / "price_snapshot_coverage.csv").write_text(cov.to_csv(index=False), encoding="utf-8")
    (OUT / "price_snapshot_gaps.csv").write_text(gap.to_csv(index=False), encoding="utf-8")
    (ROOT / "price-store.html").write_text(build_page(d, cov, gap), encoding="utf-8")
    print(f"  price_snapshots.csv          {len(d):,} rows")
    print(f"  price_snapshot_coverage.csv  {len(cov)} markets")
    print(f"  price_snapshot_gaps.csv      {len(gap):,} rows")
