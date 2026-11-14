"""Render the three pages this session adds on top of the parallel sessions' work.

  prices.html            the price-observation store, the origination order and the
                         three-column comparison (model fair line / market line /
                         difference)
  official-roi.html      the verified results feed and the return it makes
                         computable: the bets settled against an official final
  replacement-slots.html the depth of the replacement, not only the fact of one —
                         who steps in, from which string, and how much depth is
                         left behind them

The pages that the parallel sessions already published — `signal-staking.html`,
`replacement-depth.html`, `results-feed.html`, `correlation-official.html`,
`price-annex.html`, `origination.html` — are left exactly as they are. This
module adds the surfaces that do not exist yet; it does not re-publish theirs.

Every table row carries an official or primary reference. Values that depend on
the community mirror or on a model output are labelled as research estimates in
the row itself; nothing is presented as an official observation that is not one.

Run:  python pipeline/render_final.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import OFFICIAL, layout, table  # noqa: E402
from session_common import BLANK, clean, clip, e, ref_link, resolve_ref  # noqa: E402

PRICES = ROOT / "data" / "prices"
RESULTS = ROOT / "data" / "results"
AVAIL = ROOT / "data" / "availability"
INT = ROOT / "data" / "integration"

NFL_SCORES = OFFICIAL["NFL scores"]
NFL_SCHEDULE = OFFICIAL["NFL schedule"]
NFL_INJURIES = OFFICIAL["NFL injuries"]
WEEK_PAGE = "https://www.nfl.com/schedules/2026/by-week/week-{week}"
MIRROR_NOTE = ("research estimate · the price is the pinned community mirror and the "
               "fair line is a model output, not an official observation")


def link(url: str, label: str = "official source") -> str:
    return ref_link(label, url)


def val(x, dash: str = "") -> str:
    """A cell value: an empty string for a missing value, never the text 'nan'."""
    if x is None:
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        s = str(x).strip()
        return s if s else dash
    if f != f:
        return dash
    return str(x)


def fmt(x, nd=2, dash="—", signed=False):
    if x is None:
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f != f:
        return dash
    return f"{f:+,.{nd}f}" if signed else f"{f:,.{nd}f}"


def pct(x, nd=1, dash="—"):
    if x is None:
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f != f:
        return dash
    return f"{f * 100:.{nd}f}%"


# ---------------------------------------------------------------------------
# prices.html
# ---------------------------------------------------------------------------
def build_prices() -> str:
    store = pd.read_csv(PRICES / "price_store.csv")
    oc = pd.read_csv(PRICES / "open_close.csv")
    cmp_df = pd.read_csv(PRICES / "line_comparison.csv")
    order = pd.read_csv(PROC / "origination_order.csv")

    order_rows = []
    for r in order.to_dict("records"):
        order_rows.append([
            f'<strong>{e(r["step"])}</strong>', e(r["market"]), e(r["label"]),
            e(r["depends_on"]), clip(r["description"], 260), e(r["published_as"]),
            link(NFL_SCHEDULE, "NFL.com schedule")])

    snaps = (store.groupby(["snapshot_utc", "source_sha", "source_kind"])
             .agg(games=("game_id", "nunique"), rows=("snapshot_id", "count"))
             .reset_index().sort_values("snapshot_utc"))
    snap_rows = []
    for r in snaps.to_dict("records"):
        sha = str(r["source_sha"])
        url = (store.loc[store.source_sha == sha, "source_url"].iloc[0]
               if sha and (store.source_sha == sha).any() else "")
        snap_rows.append([
            e(r["snapshot_utc"]), e(sha[:12]) if sha else "forward ledger freeze",
            e(r["source_kind"]), f'{int(r["games"]):,}', f'{int(r["rows"]):,}',
            e("community mirror — not an official price source"),
            link(NFL_SCHEDULE, "NFL.com schedule")
            + (f'<br><span class="small">{link(url, "pinned commit")}</span>' if url else "")])

    board = cmp_df[cmp_df.game_status == "scheduled"].copy()
    board = board[board.week.isin([10, 11])].sort_values(["week", "gameday", "market"])
    board_rows = []
    for r in board.to_dict("records"):
        url = WEEK_PAGE.format(week=int(r["week"]))
        board_rows.append([
            e(r["gameday"]), f'{e(r["away_team"])} @ {e(r["home_team"])}',
            e(r["market"].title()), e(r["side"]),
            fmt(r["model_fair_line"], 2), fmt(r["market_line"], 2),
            fmt(r["difference"], 2, signed=True), e(r["unit"]),
            fmt(r["observed_open"], 2), fmt(r["observed_close"], 2),
            e(MIRROR_NOTE),
            link(url, "NFL.com week page")])

    moved = oc[oc.line_move.notna() & (oc.line_move != 0)]
    cover_rows = []
    for market in ["SPREAD", "TOTAL", "MONEYLINE"]:
        sub = oc[oc.market == market]
        cover_rows.append([
            e(market.title()), f'{sub.game_id.nunique():,}', f'{len(sub):,}',
            f'{int((sub.n_pre_kickoff > 0).sum()):,}',
            f'{int(sub.line_move.notna().sum()):,}',
            e("the store records the numbers this project observed; it cannot recover an "
              "opening price that no source published before kickoff"),
            link(NFL_SCHEDULE, "NFL.com schedule")])

    body = f"""
<p class="flag info"><strong>What this page is.</strong> A price-observation store: every
number this project observed for every market it originates, with the time it was observed,
the source it came from and the evidence class of that source. The opening number is the
<em>first number this project saw</em> for that market, and the closing number is the last
one seen before kickoff. Where no source published a price before kickoff, the cell is
blank — it is never filled in from a later source. <strong>No cell on this page is an
official price:</strong> no official source publishes a historical record of executable
quotes, and the official price gap is measured on
<a href="price-annex.html">the price-snapshot annex</a>.</p>

<section><h2>Origination order: the side, then the total, then the moneyline</h2>
<p>The moneyline is not an independent model. It is priced from the same margin prediction
that produces the side, so it can only be originated after it; the total is a separate
prediction and is originated second. The order is published here so that the board can be
read in the order it was built.</p>
{table(order_rows, ["Step", "Market", "What is originated", "Depends on", "Why it comes here", "Published as", "Official context"],
       caption="The order in which each market is originated and what each step depends on")}
</section>

<section><h2>The observation register</h2>
<p>Each row is one capture of the upstream price archive. The archive is a community
mirror of market prices, not an official source: no official source publishes a historical
record of executable quotes. Every capture is pinned to an exact commit and the file's
hash was verified before the rows were written.</p>
{table(snap_rows, ["Captured (UTC)", "Commit", "Source kind", "Games covered", "Rows recorded", "Evidence class", "Reference"],
       caption="Every price observation on record, with the commit it was read from")}
</section>

<section><h2>Coverage by market</h2>
{table(cover_rows, ["Market", "Games", "Market-side records", "With a pre-kickoff observation", "With a recorded line move", "What the store can and cannot say", "Official context"],
       caption="Coverage of the observation store, market by market")}
<p><strong>Open versus close.</strong> {len(moved)} market records carry a line that moved
between two observations. The rest carry one observation, which is the mirror's closing
line for a game that had already been played when the archive was last captured.</p>
</section>

<section><h2>Current board — the model's fair line, the market's line, and the difference</h2>
<p>Three separate columns, for every market this project originates, on the games it
originates now. The model's fair line and the difference are model outputs; the market
line is the mirror's. None of the three is an official observation, and each row says so
and links the official week page for the game.</p>
{table(board_rows, ["Date", "Matchup", "Market", "Side", "Model fair line", "Market line", "Difference", "Unit", "First observed", "Last observed", "Evidence", "Official context"],
       caption="The published board: model fair line, market line and their difference, side by side")}
<p><a href="assets/data/line_comparison.csv">Download the full comparison</a> ·
<a href="assets/data/open_close.csv">Download the open/close table</a> ·
<a href="assets/data/price_store.csv">Download the append-only observation log</a></p>
</section>
"""
    return layout("prices.html", "Price observations & originated lines",
                  "Every number this project observed for every market it originates — the opening "
                  "and the closing line, the model's fair line, the market's line and the difference.",
                  body, wide=True)


# ---------------------------------------------------------------------------
# official-roi.html
# ---------------------------------------------------------------------------
def build_official_roi() -> str:
    feed = pd.read_csv(RESULTS / "official_results_feed.csv")
    settle = pd.read_csv(RESULTS / "settlement_feed.csv")
    settle26 = settle[settle.season == 2026]
    roi = pd.read_csv(RESULTS / "official_roi.csv")
    corr_path = INT / "official_correlations.csv"
    corr = pd.read_csv(corr_path) if corr_path.exists() else pd.DataFrame()

    week_rows = []
    for wk, grp in settle26.groupby("week"):
        off = int((grp.verification == "official").sum())
        week_rows.append([
            f'Week {int(wk)}', f'{len(grp):,}', f'{off:,}', f'{len(grp) - off:,}',
            e("official final read on NFL.com" if off else "no official final captured yet"),
            link(WEEK_PAGE.format(week=int(wk)), "NFL.com week page")])

    feed_rows = []
    for r in feed.sort_values(["season", "week", "game_id"]).to_dict("records"):
        feed_rows.append([
            f'{int(r["season"])} wk {int(r["week"])}',
            f'{e(r["away_team"])} {int(r["away_score"])} — {int(r["home_score"])} {e(r["home_team"])}',
            e(r["status_on_page"]),
            e(r["readers"]),
            e("yes" if str(r["readers_agree"]).lower() == "yes" else "NO"),
            e(r["verified_utc"]),
            link(r["official_url"], "NFL.com game page")])

    roi_rows = []
    for r in roi.sort_values("officially_settled_bets", ascending=False).to_dict("records"):
        n = int(r["officially_settled_bets"])
        roi_rows.append([
            f'<strong>{e(r["strategy"])}</strong>', f'{n:,}', f'{int(r["total_bets"]):,}',
            pct(r["coverage"], 2), f'{int(r["wins"])}-{int(r["pushes"])}-{int(r["losses"])}',
            fmt(r["profit"], 3), pct(r["roi"], 2),
            e("the result is an official NFL.com final; the price that decides the return is "
              "the mirror's, so the return is a research estimate"),
            link(NFL_SCORES, "NFL.com scores")])

    corr_rows = []
    for r in corr.to_dict("records"):
        corr_rows.append([
            e(r["relationship"]), e(r["what_it_measures"]), e(r["kind"]),
            f'{int(r["n"]):,}', f'{int(r["n_weeks"]):,}', fmt(r["rho"], 4),
            f'{fmt(r["ci_lo"], 4)} … {fmt(r["ci_hi"], 4)}',
            e("yes" if str(r["zero_in_ci"]).lower() == "true" else "no"),
            e(r["verdict"]),
            link(NFL_SCORES, "NFL.com scores") + "<br>" + link(r["source_url"], "pinned archive row")])

    body = f"""
<p class="flag info"><strong>What this page is.</strong> The settlement feed and the return it
makes computable. A backtest and a return calculation cannot exist without a result for every
game, and a result that was never checked against an official page is an assumption. Every
game below was read on an official NFL.com page, with the page recorded. Games whose final
has not been read on an official page are counted, not guessed, and no bet on them is
settled at all — not as a loss and not as a push.</p>

<section><h2>Coverage by week — the 2026 season</h2>
{table(week_rows, ["Week", "Games played", "Officially confirmed", "Not yet confirmed", "Basis", "Official context"],
       caption="How much of the played 2026 season is confirmed against an official NFL.com final")}
<p>{int((settle26.verification == "official").sum())} of {len(settle26)} played games carry an
official final. The rest are blank in every table on this site until an official page is
read for them. Nothing is filled in from the mirror.</p>
</section>

<section><h2>The verified results feed</h2>
<p>Several independent readers have read the finals: the forward ledger's capture, the
independent score audit and the canonical verified feed. Where two readers read the same
game, the column <em>readers agree</em> records whether their readings match; a
disagreement is reported as a disagreement and is never averaged away.</p>
{table(feed_rows, ["Season", "Final", "Status on page", "Read by", "Readers agree", "Verified (UTC)", "Official source"],
       caption="Every final score read on an official NFL.com page, with the page it was read on")}
</section>

<section><h2>The return the feed makes computable</h2>
<p>Settled only against official finals. A bet whose game has no official final is not
counted at all. The coverage column is the share of the strategy's own sample that is
settled this way, and it is small: this is a plumbing check, not a verdict. The
signal-versus-staking reading of the same strategies — including the probability check
that stands behind the expected values — is on
<a href="signal-staking.html">the signal and staking page</a>.</p>
{table(roi_rows, ["Strategy", "Officially settled bets", "Total bets", "Coverage", "W-P-L", "Profit (units)", "Return", "Evidence", "Official source"],
       caption="Return per strategy over the bets whose result is an official NFL.com final")}
</section>

<section><h2>Correlations computed with n published on every row</h2>
<p>Every value carries the number of observations and the number of distinct weeks it was
computed from, because games in a week are not independent. An interval that contains
zero means the estimate is not distinguishable from no relationship, and the row says so.
The register is published in full on
<a href="correlation-official.html">the correlations page</a>.</p>
{table(corr_rows, ["Relationship", "What it measures", "Kind", "n", "n weeks", "Estimate", "95% interval", "Zero in interval", "Verdict", "Source"],
       caption="The correlation register, with the sample size on every row")}
</section>
"""
    return layout("official-roi.html", "Verified results & the return they make computable",
                  "Official finals, the coverage they give, and the return that can be computed "
                  "from them — with the sample size published next to every number.",
                  body, wide=True)


# ---------------------------------------------------------------------------
# replacement-slots.html
# ---------------------------------------------------------------------------
def build_depth() -> str:
    df = pd.read_csv(AVAIL / "replacement_depth_slots.csv")
    rows = []
    for r in df.sort_values(["team", "unit", "slot"]).to_dict("records"):
        rows.append([
            e(r["team"]), e(r["unit"]), str(int(r["slot"])), e(r["position"]),
            e(val(r["starter"])), e(val(r["starter_status"])),
            e(val(r["replacement"])) or BLANK,
            e(val(r["replacement_depth_string"])) or BLANK,
            e(val(r["replacement_status"])),
            f'{int(r["same_position_available_behind"]):,}',
            e(val(r["bench_depth_note"])),
            link(r["depth_source_url"], "club depth chart") + "<br>" + link(NFL_INJURIES, "NFL injury report")])

    summary = []
    for key, grp in df.groupby("replacement_depth_string"):
        summary.append([
            e(key if key else "no replacement listed"),
            f'{len(grp):,}',
            e(", ".join(sorted(grp["team"].unique()))),
            e(", ".join(sorted(grp["position"].unique()))),
            link(NFL_INJURIES, "NFL injury report")])

    body = f"""
<p class="flag info"><strong>What this page is.</strong> The depth of the replacement, not only
the fact of a replacement. For every slot whose first-listed player is unavailable, this page
names the player who steps in, the depth string they come from (second string, third string,
fourth string), and how many further players the club still has at that position. The depth
chart is the club's own published chart; the availability is the official NFL injury report.
The club-level depth impact, the cliff and the evidence state are published on
<a href="replacement-depth.html">the replacement-depth page</a>.</p>

<section><h2>Replacement depth by club</h2>
{table(rows, ["Club", "Unit", "Slot", "Position", "First-listed player", "Availability", "Replacement", "Depth", "Replacement's own status", "Further players available at that position", "Bench note", "Official sources"],
       caption="Every slot whose first-listed player is unavailable, with the depth of the replacement")}
</section>

<section><h2>How deep the replacements are</h2>
{table(summary, ["Depth", "Slots", "Clubs", "Positions", "Official context"],
       caption="Distribution of replacement depth across the clubs in the current capture")}
<p>A second-string replacement and a fourth-string replacement are different events. The
first is a rotation; the second is a vacancy. The count of further players available at the
same position is the number of times the club can absorb one more injury at that position
before the position is exposed.</p>
<p><a href="assets/data/replacement_depth_slots.csv">Download the replacement-depth table</a> ·
<a href="availability.html">Injuries and depth across all clubs</a></p>
</section>
"""
    return layout("replacement-slots.html", "Depth of the replacement",
                  "Who steps in when a starter cannot, how deep they come from, and how much "
                  "depth is left behind them.",
                  body, wide=True)


def main() -> None:
    for name, builder in [("prices.html", build_prices),
                           ("official-roi.html", build_official_roi),
                           ("replacement-slots.html", build_depth)]:
        html = builder()
        (ROOT / name).write_text(html, encoding="utf-8")
        print(f"  wrote {name} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
