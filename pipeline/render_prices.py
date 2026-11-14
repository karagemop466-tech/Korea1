"""T57 — render `prices.html`: the price-snapshot store and the verified results feed.

Two artifacts are published here, and the page is built so that a reader can
tell them apart at a glance:

* the **price-snapshot store** — one row per originated market side, with the
  opening and closing numbers and the evidence class of each;
* the **verified results feed** — the official finals, joined to our own
  published line, so that a settlement can be checked against the official
  page it came from.

Public-view rules (the same ones the rest of the site obeys):

* a number whose class is A or B is printed;
* a number whose class is C or D is printed blank and the row is marked
  UNVERIFIED, with the official reference beside it;
* every row carries an official/primary reference;
* `n` is published with every estimate, including the ones that are blank.

Run:  python pipeline/render_prices.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC, read_json  # noqa: E402
from render_site import (  # noqa: E402
    BLANK, card, e, flag, kpi_grid, layout, notice, official, table,
)

FWD = ROOT / "data" / "forward"
OUT = ROOT / "prices.html"

NFL_SCORES = "https://www.nfl.com/scores/"


def _f(x) -> str:
    """A number, or an em dash when it is not on record."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if v != v:
        return "—"
    return f"{v:,.2f}"


def _link(url: str, label: str = "official") -> str:
    if not url:
        return official("NFL scores")
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def build() -> str:
    manifest_p = PROC / "origination_manifest.json"
    manifest = read_json(manifest_p) if manifest_p.exists() else {}
    store_p = FWD / "price_snapshots.csv"
    store = pd.read_csv(store_p, dtype=str).fillna("") if store_p.exists() else pd.DataFrame()
    feed_p = FWD / "verified_results.csv"
    feed = pd.read_csv(feed_p, dtype=str).fillna("") if feed_p.exists() else pd.DataFrame()
    summ_p = FWD / "verified_summary.csv"
    summ = pd.read_csv(summ_p, dtype=str).fillna("") if summ_p.exists() else pd.DataFrame()
    roi_p = FWD / "verified_roi.csv"
    roi = pd.read_csv(roi_p, dtype=str).fillna("") if roi_p.exists() else pd.DataFrame()
    src_p = FWD / "price_snapshot_sources.csv"
    srcs = pd.read_csv(src_p, dtype=str).fillna("") if src_p.exists() else pd.DataFrame()

    # ---- cards ------------------------------------------------------------
    n_store = len(store)
    n_games = int(store.game_id.nunique()) if len(store) else 0
    n_official = int(feed.game_id.nunique()) if len(feed) else 0
    n_complete = int((store.store_status == "COMPLETE").sum()) if len(store) else 0
    cards = kpi_grid([
        card(f"{n_store:,}", "price snapshots", f"one row per originated market side · {n_games:,} games", ""),
        card(f"{n_complete:,}", "with an opening and a closing number",
             "the rest carry one of the two, or neither", ""),
        card(str(n_official), "officially verified games", "official finals with their official URL", "good"),
        card("3", "markets originated per game", "spread, total, moneyline — the side first", ""),
    ])

    # ---- the origination order -------------------------------------------
    stages = manifest.get("stages", {})
    order_rows = []
    for market in manifest.get("origination_order", []):
        st = stages.get(market, {})
        order_rows.append([
            e(st.get("seq", "")), e(st.get("label", market)),
            "<br>".join(e(x) for x in st.get("consumes", [])) or "—",
            "<br>".join(e(x) for x in st.get("produces", [])) or "—",
            e(st.get("why_first") or st.get("why_second") or st.get("why_third") or ""),
            official("NFL scores"),
        ])

    # ---- the price-snapshot store ----------------------------------------
    store_rows = []
    if len(store):
        pub = store[(store.scope == "forward_published")
                    & (store.market == "SPREAD") & (store.side == "home")
                    & (store.set == "D")].copy()
        pub = pub.sort_values(["week", "game_id"])
        for r in pub.itertuples(index=False):
            model = r.model_line if r.model_line else BLANK
            market_line = BLANK if r.market_line else BLANK
            diff = BLANK
            store_rows.append([
                e(f"{r.away_team} @ {r.home_team}"), e(r.week),
                model,
                market_line,
                diff,
                BLANK if not r.open_line else BLANK,
                BLANK if not r.close_line else BLANK,
                '<span class="pill unverified">UNVERIFIED</span>',
                _link(r.official_url, "official game page"),
            ])

    # ---- the verified results feed ----------------------------------------
    feed_rows = []
    if len(feed):
        one = (feed[feed.market == "SPREAD"]
               .sort_values(["week", "game_id"])
               .drop_duplicates("game_id"))
        for r in one.itertuples(index=False):
            feed_rows.append([
                e(f"{r.away_team} @ {r.home_team}"), e(r.week),
                e(r.gameday), e(r.official_final_away), e(r.official_final_home),
                e(r.actual_margin), e(r.actual_total), e(r.official_status),
                e(r.verified_utc), e(r.verified_by),
                _link(r.official_url, "official game page"),
            ])

    # ---- model vs market on the official results --------------------------
    mae_rows = []
    for r in summ.itertuples(index=False):
        mae_rows.append([
            e(r.market), e(r.games), e(r.model_mae_n),
            _f(r.model_mae),
            BLANK, e(r.market_mae_n),
            BLANK,
            '<span class="pill unverified">UNVERIFIED</span>',
            official("NFL scores"),
        ])

    # ---- return from the verified feed ------------------------------------
    roi_rows = []
    for r in roi.itertuples(index=False):
        roi_rows.append([
            e(r.strategy), e(r.settled_picks), e(r.wins), e(r.losses), e(r.pushes),
            BLANK, BLANK,
            '<span class="pill unverified">UNVERIFIED</span>',
            official("NFL scores"),
        ])

    # ---- the source register ----------------------------------------------
    src_rows = []
    for r in srcs.itertuples(index=False):
        if r.source_url and "nfl.com" in r.source_url:
            reference = _link(r.source_url, "official source")
        elif r.source_url:
            reference = ('<span class="unverified">community archive - not an '
                         'official source</span><br>' + _link(r.source_url, "archive"))
        else:
            reference = '<span class="muted">no source on record</span>'
        src_rows.append([
            e(r.source_id), e(r.phase), e(r.evidence_class or "-"),
            e(r.label), e(r.description), e(r.use_rule),
            reference,
            official("NFL scores"),
        ])

    body = f"""{notice()}
{cards}

<section id="origination-order"><div class="section-head"><h2>How a market is originated: the side, then the total, then the moneyline</h2>
<a href="data/processed/origination_manifest.json">Download the manifest →</a></div>
<p>The order is a property of the model, not a presentation choice. The side is originated
first because the moneyline is a read-out of the same margin distribution; the total is
originated next so that both published lines come from one fit of one training window.</p>
{table(order_rows, ["Order", "Stage", "What it consumes", "What it produces", "Why it sits here", "Official context"],
      caption="The origination order, as fixed in pipeline/models.py and published in the manifest")}
</section>

<section id="price-store"><div class="section-head"><h2>Price-snapshot store — the side (spread)</h2>
<a href="data/forward/price_snapshots.csv">Download the full store →</a></div>
<p>One row per originated market side, with the opening number, the closing number and the
evidence class of each. The store holds {n_store:,} rows over {n_games:,} games; every market
this project originates is in it — the spread, the total and the moneyline, both sides of
each.</p>
<p>Our own published line is a class B value and is printed. The market's number is a class C
value — a community mirror, not an official observation — so it is blank here and flagged,
and the difference, which depends on it, is blank for the same reason. The full store with
every class attached is downloadable above.</p>
{table(store_rows, ["Matchup", "Week", "Model line (fair)", "Market line", "Difference (model − market)",
                    "Opening number", "Closing number", "Status", "Official reference"],
      caption="The games this project published a line for; the market numbers are unverified and stay blank")}
</section>

<section id="results-feed"><div class="section-head"><h2>Verified results feed</h2>
<a href="data/forward/verified_results.csv">Download the feed →</a></div>
<p>Every final score below was read on an official NFL page by a named session, with the page
URL and the verification time recorded. This is the feed a backtest and a return are computed
from: the result is official, the line is ours, and the price is the part that is still
missing.</p>
{table(feed_rows, ["Matchup", "Week", "Official date", "Away score", "Home score", "Margin", "Total", "Status on page", "Verified (UTC)", "Verified by", "Official reference"],
      caption="Officially verified finals — the anchor every settlement rests on")}
</section>

<section id="model-vs-market"><div class="section-head"><h2>How close the line landed, on official results only</h2>
<a href="data/forward/verified_summary.csv">Download the summary →</a></div>
<p>On the {n_official} officially verified games, how far each line landed from the official
final. The model error uses an official final and our own line, so it is class B and is
printed. The market error uses a community mirror line, so it is class D and is blank here;
it is in the downloadable summary.</p>
{table(mae_rows, ["Market", "Games", "n (model)", "Model mean absolute error",
                   "Market mean absolute error", "n (market)", "Market error", "Status", "Official reference"],
      caption="Absolute error against the official final; n is published with every estimate")}
</section>

<section id="return-from-feed"><div class="section-head"><h2>Return computed from the verified feed</h2>
<a href="data/forward/verified_roi.csv">Download the return register →</a></div>
<p>The return is computable now that the result is official. The entry price is still a
community mirror, so the return is a class D value and stays blank in this strict view.
The number of settled picks is published beside it, because n is what decides whether a
return means anything.</p>
{table(roi_rows, ["Strategy", "Settled picks", "Wins", "Losses", "Pushes", "Return", "ROI", "Status", "Official reference"],
      caption="Return per strategy from officially settled picks only; unverified values are blank")}
</section>

<section id="sources"><div class="section-head"><h2>Where every number in the store comes from</h2></div>
<p>Each source carries its own evidence class and its own rule for when it may be used. A
number with no source stays empty.</p>
{table(src_rows, ["Source id", "Phase", "Class", "Label", "What it is", "When it may be used", "Source reference", "Official context"],
      caption="The price-snapshot source register; a community archive is labelled as one and never stands as an official source")}
</section>

<section id="what-is-missing"><h2>What is still missing, and how it would be found</h2>
<ul class="findings">
<li><strong>No official price exists.</strong> NFL.com publishes scores, injuries and
schedules; it does not publish betting lines or prices. Until a bookmaker's own quote is
captured with its timestamp and its limits, every market number in this project is class C
and every return computed from it is class D.</li>
<li><strong>No opening moneyline.</strong> The opening-line archive in the pinned upstream
covers the spread and the total for the 2021 season and carries no price at all, so the
opening number is blank for every other game and for the moneyline everywhere.</li>
<li><strong>The official results feed is 30 games.</strong> It is the anchor the whole
forward record rests on, and it is the first thing to extend: each game page is read, the
final is transcribed, and the page URL and the verification time are recorded.</li>
<li><strong>Discovery.</strong> The three sources above are the only routes to the missing
evidence, and each of them is a named, scheduled task rather than an assumption.</li>
</ul></section>
"""
    return layout("prices.html", "Prices, lines & verified results",
                  "The price-snapshot store, the verified results feed and the return they support.",
                  body, wide=True)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote prices.html ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
