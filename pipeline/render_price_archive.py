"""BF1 (session `arena/bfcd9879-korea1`) — publish `price-archive.html`.

Companion to `price-snapshot.html`: that page is the strict store (opening and
closing cells blank because no official/operator-timestamped quote exists).
This page publishes the **archive-populated view** — the third-tier numbers the
repository actually holds (Sportsbook Review 10-year archive opens and closes
for 2011–2021, pinned community closes for 1999–2026, and forward-ledger
freezes for 2026 W8–W10) — each row labelled with its tier and the standing
flag that no price on the page is an authenticated bookmaker quote (gate G1
fails for all of them).

Design rules inherited from ``render_site.py``:

* every table row carries an official/primary reference;
* a snapshot that does not exist stays blank and its flag says why;
* archive dates that differ from the official date by ±1 day are shown with
  their match kind, never silently swapped.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT  # noqa: E402
from render_site import layout, table, flag, e, src_link  # noqa: E402

DASH = "—"


def _csv(name: str) -> pd.DataFrame:
    # dtype=str + keep_default_na=False: blanks stay empty strings, so no
    # table cell can ever render the literal token "nan" (verify V3).
    p = PROC / name
    return (pd.read_csv(p, dtype=str, keep_default_na=False)
            if p.exists() else pd.DataFrame())


def _n(x) -> str:
    try:
        v = float(str(x))
    except (TypeError, ValueError):
        return DASH
    if v != v:
        return DASH
    return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:g}"


def _num(x) -> str:
    try:
        v = float(str(x))
    except (TypeError, ValueError):
        return DASH
    if v != v:
        return DASH
    return f"{v:g}"


def render() -> dict[str, str]:
    store = _csv("price_archive.csv")
    games = _csv("price_archive_games.csv")
    cov = _csv("price_archive_coverage.csv")
    if store.empty:
        return {}
    gidx = games.set_index("game_id")
    # game_status lives in the game-level file; attach it for the freeze tables
    store["game_status"] = store.game_id.map(
        gidx.game_status if len(gidx) else {}).fillna("")
    store["gameday"] = store.game_id.map(
        gidx.gameday if len(gidx) else {}).fillna("")
    store["matchup"] = store.game_id.map(
        gidx.matchup if len(gidx) else {}).fillna("")

    def url_for(game_id: str) -> str:
        if game_id in gidx.index:
            return str(gidx.at[game_id, "official_url"])
        return "https://www.nfl.com/scores/"

    # ---- coverage by season ------------------------------------------------
    cov_num = cov.copy()
    for c in ("games", "open_snapshots", "archive_closes", "pin_closes",
              "freeze_snapshots"):
        cov_num[c] = pd.to_numeric(cov_num[c], errors="coerce").fillna(0)
    by_season = cov_num.groupby("season", as_index=False).agg(
        games=("games", "max"),
        opens=("open_snapshots", "sum"),
        arch=("archive_closes", "sum"),
        pins=("pin_closes", "sum"),
        frz=("freeze_snapshots", "sum"))
    cov_rows = []
    for r in by_season.sort_values("season").itertuples():
        season = int(r.season)
        if r.opens > 0:
            status = "Open + close archive coverage"
        elif r.arch > 0:
            status = "Close only — no opening source for this season"
        elif r.pins > 0:
            status = "Pinned community close only"
        else:
            status = "No price snapshot held"
        cov_rows.append([
            e(str(season)), _n(r.games), _n(r.opens), _n(r.arch),
            _n(r.pins), _n(r.frz), status,
            src_link(f"https://www.nfl.com/scores/{season}/week-1",
                     "official season scores")])

    # ---- 2026 W10 freeze card (spread rows) ------------------------------
    w10 = store[(store.market == "SPREAD")
                & store.game_status.str.contains("W10", na=False)]
    w10_rows = []
    for r in w10.sort_values("game_id").itertuples():
        w10_rows.append([
            e(r.game_id), e(r.gameday),
            _num(r.our_frozen_line), _num(r.freeze_market),
            _num(r.pin_close),
            e(r.freeze_flag), e(r.pin_close_flag),
            e(r.game_status),
            src_link(url_for(r.game_id), "official source")])

    # ---- archive sample: most recent archive season -----------------------
    sample = store[(store.season == "2021") & (store.market == "SPREAD")]
    sample = sample.sort_values("game_id").head(12)
    sample_rows = []
    for r in sample.itertuples():
        sample_rows.append([
            e(r.game_id), e(r.gameday), _num(r.open_price), _num(r.archive_close),
            _num(r.pin_close), _num(r.archive_minus_pin),
            e(r.open_flag), e(r.archive_close_flag),
            src_link(url_for(r.game_id), "official source")])

    # ---- date-adjusted matches (audit) -----------------------------------
    adj = store[(store.archive_match.isin(["date_minus_1", "date_plus_1"]))
                & (store.market == "SPREAD")]
    adj_rows = []
    for r in adj.sort_values("game_id").itertuples():
        adj_rows.append([
            e(r.game_id), e(r.gameday),
            "archive stores the game one day earlier"
            if r.archive_match == "date_minus_1"
            else "archive stores the game one day later",
            "identity confirmed: same season and both club codes, exactly "
            "one archive row in the ±1-day window",
            src_link(url_for(r.game_id), "official source")])

    # ---- genuine archive gaps --------------------------------------------
    gaps = store[(store.open_flag == "GAME_NOT_IN_ARCHIVE")
                 & (store.market == "SPREAD")]
    gap_rows = []
    for r in gaps.sort_values("game_id").itertuples():
        reason = ("Super Bowl — the archive excludes neutral-site games "
                  "(10 dropped at ingest, data/lab/integrity.json)"
                  if int(r.gameday[5:7]) in (1, 2)
                  else "not present anywhere in the archive's date range")
        gap_rows.append([
            e(r.game_id), e(r.gameday), e(r.matchup), reason,
            src_link(url_for(r.game_id), "official source")])

    # ---- schema -----------------------------------------------------------
    schema = [
        ["open_price", "Opening number for the market",
         "Sportsbook Review 10-year archive, 2011–2021 only "
         "(verified_third_party tier; data/lab/sources.json)",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
        ["archive_close", "Closing number for the market (moneyline is a "
         "single daily price in that archive)",
         "Same archive; hash recorded in the coverage file",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
        ["pin_close", "Closing line in the hash-verified pinned snapshot",
         "Pinned community snapshot (nflverse mirror); research input, "
         "not an executable quote",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
        ["freeze_market", "Market number at the moment our line was frozen",
         "Forward ledger: audit sets for 2026 W8–W9, freeze card for W10",
         src_link("https://www.nfl.com/scores/2026/week-10",
                  "NFL week 10 scores")],
        ["our_frozen_line", "The line this pipeline originated at the same "
         "freeze", "Forward ledger, commit-provenanced",
         src_link("https://www.nfl.com/scores/2026/week-10",
                  "NFL week 10 scores")],
        ["*_flag / archive_match", "Why a cell is blank, or how the archive "
         "row was identified", "Never inferred; every blank has a reason",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
    ]

    n_open = int(pd.to_numeric(store.open_price, errors="coerce").notna().sum())
    n_arch = int(pd.to_numeric(store.archive_close, errors="coerce").notna().sum())
    n_pin = int(pd.to_numeric(store.pin_close, errors="coerce").notna().sum())
    n_frz = int(pd.to_numeric(store.freeze_market, errors="coerce").notna().sum())

    body = f"""{flag('What this page is. The archive-populated companion to '
                     '<a href="price-snapshot.html">price-snapshot.html</a>, which keeps every '
                     'opening and closing cell blank because no official NFL source publishes '
                     'betting lines. This page shows the third-tier numbers the repository '
                     'actually holds — each row labelled with its source tier, each blank '
                     'carrying the reason it is blank. NO PRICE HERE IS AN AUTHENTICATED '
                     'BOOKMAKER QUOTE: gate G1 fails for every one of them. Treat the columns '
                     'as recorded captures for review, not as executable offers.', 'warn')}
<section><h2>The store in numbers</h2>
<div class="cards">
<div class="card"><div class="card-value">{len(store):,}</div><div class="card-label">snapshot rows (game × market)</div></div>
<div class="card"><div class="card-value">{store.game_id.nunique():,}</div><div class="card-label">games covered</div></div>
<div class="card"><div class="card-value">{n_open:,}</div><div class="card-label">opening prices (2011–2021 archive)</div></div>
<div class="card"><div class="card-value">{n_arch:,}</div><div class="card-label">archive closes</div></div>
<div class="card"><div class="card-value">{n_pin:,}</div><div class="card-label">pinned closes</div></div>
<div class="card"><div class="card-value">{n_frz}</div><div class="card-label">forward-freeze snapshots</div></div>
</div>
<p><a href="data/processed/price_archive.csv">Download the full store</a> ·
<a href="data/processed/price_archive_games.csv">game-level file (dates, matchups, official URLs)</a> ·
<a href="data/processed/price_archive_coverage.csv">coverage + file hashes</a></p></section>

<section><h2>Coverage by season: where an opening exists and where it does not</h2>
<p>Opening prices exist only for 2011–2021 (the archive's own span). Before
2011 and after 2021 the store holds the pinned community close only, and the
status column says so. Nothing is filled across a gap.</p>
{table(cov_rows, ["Season", "Games", "Opening prices", "Archive closes",
                  "Pinned closes", "Freeze snapshots", "Coverage status",
                  "Official scores"],
       caption="Price-snapshot coverage per season — blanks are structural, not estimated")}
</section>

<section><h2>The 2026 week-10 freeze: our line against the market, at the moment of freezing</h2>
<p>All 14 week-10 games were frozen before kickoff on 2026-11-12T13:26:48Z
(server-side receipt in the forward ledger). Spread rows shown; total and
moneyline rows are in the download. The close column fills in only after an
official final exists.</p>
{table(w10_rows, ["Game", "Date", "Our frozen line", "Market at freeze",
                  "Close", "Freeze flag", "Close flag", "Status",
                  "Official source"],
       caption="Week-10 freeze card — originated line versus market at freeze")}
</section>

<section><h2>Archive sample: 2021, the most recent season with opening prices</h2>
<p>Twelve spread rows from the last archive season. The archive-minus-pin
column is the difference between the third-party close and the pinned close —
two different community sources, not an official measurement.</p>
{table(sample_rows, ["Game", "Date", "Open", "Archive close", "Pinned close",
                     "Archive − pin", "Open flag", "Close flag",
                     "Official source"],
       caption="Opening and closing numbers with their provenance flags")}
</section>

<section><h2>Archive date quirks: identity-confirmed ±1-day matches</h2>
<p>The third-party archive sometimes stores a game one day off the official
date (the entire 2015 week-6 Sunday slate is dated 10-17 for 10-18; two
Monday games are stored a day late). Those rows are joined only when the
season and <em>both</em> club codes match exactly one archive row inside the
±1-day window — identity is confirmed by the clubs, never guessed from
proximity. The match kind is printed on the store row.</p>
{table(adj_rows, ["Game", "Official date", "Archive behaviour",
                  "Why the join is safe", "Official source"],
       caption="Date-adjusted archive joins, all identity-confirmed")}
</section>

<section><h2>Genuine archive gaps ({len(gap_rows)} games)</h2>
<p>These games are not in the third-party archive at all: the Super Bowls were
dropped as neutral-site rows at ingest, and one 2013 London game is absent.
The store flags them GAME_NOT_IN_ARCHIVE; their cells stay blank.</p>
{table(gap_rows, ["Game", "Date", "Matchup", "Why it is blank",
                  "Official source"],
       caption="Games with no archive row — blank and flagged, never filled")}
</section>

<section><h2>Store schema</h2>
{table(schema, ["Column", "Meaning", "Source tier", "Official context"],
       caption="Every column of the store and the tier of its evidence")}
<p class="small">Every row of every table above carries an official NFL link.
The price columns themselves are third-party or community data — the NFL
publishes no odds — which is exactly why each row repeats the standing flag:
not an authenticated bookmaker quote, gate G1 fails.</p></section>"""

    return {"price-archive.html": layout(
        "price-archive.html", "Price archive",
        "Opening and closing numbers we actually hold — opens for 2011–2021, "
        "closes, freezes — each with its tier and its blanks' reasons.",
        body, wide=True)}


def main() -> int:
    pages = render()
    for name, html_text in pages.items():
        (ROOT / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
