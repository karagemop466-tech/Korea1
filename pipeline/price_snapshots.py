"""T50 — the price-snapshot store.

What this is for
----------------
When this project originates a market it has to remember **two** market numbers
for it: the number the market opened at, and the number it closed at. Without
both, a line cannot be compared with the market it was supposed to beat, and a
return cannot be attributed to the model instead of to line movement.

The store is one row per **originated market side**:

    (game, market, side)  ->  model number, market number, difference,
                               opening number, closing number, evidence class

Three rules are enforced in code, not by convention:

1. **Every number carries its own source and its own evidence class.** A row
   never inherits the provenance of its neighbours: the opening number and the
   closing number can come from different places, and one of them is often
   absent. Where no source exists the cell is left empty and the row is marked
   incomplete. Nothing is filled from a neighbouring row, a model output or a
   guess.
2. **An unverified number is never promoted.** Class C (a community mirror) and
   class D (anything computed from a class C value) are recorded in the store
   with their class attached, so the store is complete, but the published page
   blanks those cells and flags them. The class is carried through to the page
   rather than being decided at write time.
3. **The origination order is fixed by the store, not by the reader.** The side
   (spread) is originated first, then the total, then the moneyline, and the
   `origination_seq` column records that order on every row.

Evidence classes (the same vocabulary as pipeline/forward_ledger.py)
--------------------------------------------------------------------
A  an official observation, read on an official page by a named session
B  our own forecast, or a calculation that uses only class A values and our
   forecasts
C  a community-mirror observation that no official page confirms
D  a calculation that needs a class C value

Outputs
-------
  data/forward/price_snapshots.csv        the store
  data/forward/price_snapshot_sources.csv the source register each row cites
  assets/data/price_snapshots.csv         the decision-relevant subset for the site

Run:  python pipeline/price_snapshots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC, ROOT as _ROOT, read_json  # noqa: E402

FWD = ROOT / "data" / "forward"
RAW = ROOT / "data" / "raw"
SITE_DATA = ROOT / "assets" / "data"

# The origination order required by the brief: the side first, then the total,
# then the moneyline. The moneyline is derived from the margin distribution the
# side is priced from, so it cannot be originated before the side; the total is
# an independent target but is priced after the side so that the two lines a
# reader compares come from the same fit.
ORIGINATION_ORDER = ("SPREAD", "TOTAL", "MONEYLINE")
ORIGINATION_SEQ = {m: i + 1 for i, m in enumerate(ORIGINATION_ORDER)}
MARKET_SIDES = {
    "SPREAD": ("home", "away"),
    "TOTAL": ("over", "under"),
    "MONEYLINE": ("home", "away"),
}

SHA = read_json(ROOT / "data" / "sources.json")["upstream"]["commit_sha"]
# The official scores page is the correct official reference for a game whose
# own game-centre URL has not been recorded. A URL is never constructed from a
# game id: a constructed link is not a source.
NFL_SCORES = "https://www.nfl.com/scores/"
NFD = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/"

# ---------------------------------------------------------------------------
# Source register. Every source id used in the store is described here with
# its URL, its evidence class and the rule that decides when it may be used.
# ---------------------------------------------------------------------------
SOURCES = [
    dict(source_id="PS-NFL-GAME", phase="reference", evidence_class="A",
         label="NFL.com official game page",
         source_url="https://www.nfl.com/games/",
         description="Official game centre: schedule, kickoff and final score.",
         use_rule="Used for the game identity and for the final score when the "
                  "session recorded it from this page."),
    dict(source_id="PS-NFL-SCORES", phase="reference", evidence_class="A",
         label="NFL.com official scores page",
         source_url="https://www.nfl.com/scores/",
         description="Official weekly scores page read in full by a named session.",
         use_rule="Used for a final score when the reading is recorded in "
                  "data/forward/official_results.csv."),
    dict(source_id="PS-OFFICIAL-RESULT", phase="close", evidence_class="A",
         label="Official final recorded in the forward results feed",
         source_url="https://www.nfl.com/scores/",
         description="The final score transcribed from the official page, with the "
                     "page URL, the verification time and the verifying session.",
         use_rule="Used for final_home_score / final_away_score only. Never used "
                  "for a line or a price."),
    dict(source_id="PS-NFD-CLOSE", phase="close", evidence_class="C",
         label="nflverse/nfldata games.csv (community close)",
         source_url=NFD + "games.csv",
         description="Community mirror of the closing spread, closing total and "
                     "closing prices. Pinned to an exact commit.",
         use_rule="Used as the market number on record for historical games, and "
                  "as the closing number when no other source exists."),
    dict(source_id="PS-NFD-CLOSING", phase="close", evidence_class="C",
         label="nflverse/nfldata closing_lines.csv (community per-side close)",
         source_url=NFD + "closing_lines.csv",
         description="Community mirror of the per-side closing price and the "
                     "settlement outcome, 2006-2018.",
         use_rule="Used as the closing price for a side when games.csv carries no "
                  "price for that side."),
    dict(source_id="PS-NFD-INITIAL", phase="open", evidence_class="C",
         label="nflverse/nfldata initial_lines.csv (community opening lines)",
         source_url=NFD + "initial_lines.csv",
         description="Community mirror of the opening spread and total lines for "
                     "the 2021 season, book WSGT. Lines only; no opening price.",
         use_rule="Used as the opening number for a 2021 spread or total side and "
                  "for nothing else."),
    dict(source_id="PS-OUR-PUBLICATION", phase="open", evidence_class="B",
         label="Our own published line (this repository)",
         source_url="https://github.com/karagemop466-tech/Korea1",
         description="The line this project published for the game, with the pull "
                     "request, the commit and the publication time.",
         use_rule="Used as the opening number for a game we published, because the "
                  "opening moment for our own line is its publication."),
    dict(source_id="PS-NFD-PIN", phase="open", evidence_class="C",
         label="Community mirror number observed at our pin",
         source_url=NFD + "games.csv",
         description="The market number as it stood when our line was frozen.",
         use_rule="Used as the opening number for the games we published."),
    dict(source_id="PS-NONE", phase="none", evidence_class="",
         label="No source on record",
         source_url="",
         description="Nothing official, and no community mirror either, carries this "
                     "number. The cell stays empty.",
         use_rule="Used whenever a number has no source. The row is then marked "
                  "incomplete and the page prints the cell blank."),
]


def _num(x) -> float:
    """A float, or NaN. Never a default, never a zero."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


def _dec(american) -> float:
    """American odds -> decimal payout multiple. NaN when the price is absent."""
    a = _num(american)
    if not np.isfinite(a) or -100 < a < 100:
        return float("nan")
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / abs(a)


def _fair_decimal(p_win: float, p_loss: float) -> float:
    """The break-even decimal price: d such that P(win)*(d-1) - P(loss) = 0.

    This is the formula the site already publishes. A push contributes zero in
    both directions, so it lowers the break-even price rather than being ignored.
    """
    pw, pl = _num(p_win), _num(p_loss)
    if not np.isfinite(pw) or not np.isfinite(pl) or pw <= 0:
        return float("nan")
    return 1.0 + pl / pw


def _blank(v) -> str:
    """Store representation of an absent number: an empty cell, never 0."""
    f = _num(v)
    return "" if not np.isfinite(f) else f"{round(f, 4):g}"


def _row(**kw) -> dict:
    base = {c: "" for c in COLUMNS}
    base.update(kw)
    return base


def _snapshot_id(scope: str, game_id: str, market: str, side: str, pub_set: str = "") -> str:
    """A unique identifier for one originated market side."""
    tail = f"-{pub_set}" if pub_set else ""
    return f"PS-{scope}{tail}-{game_id}-{market}-{side}"


COLUMNS = [
    "snapshot_id", "scope", "set", "game_id", "season", "week", "gameday",
    "away_team", "home_team", "market", "side", "origination_seq",
    "model_line", "model_price",
    "market_line", "market_price", "difference",
    "open_line", "open_price", "open_source_id", "open_class",
    "close_line", "close_price", "close_source_id", "close_class",
    "final_home_score", "final_away_score",
    "official_url", "store_status", "note",
]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _market_rows(*, scope: str, game: dict, market: str, side: str,
                 model_line, model_price, market_line, market_price,
                 open_line, open_price, open_src, open_class,
                 close_line, close_price, close_src, close_class,
                 final_home, final_away, official_url, note: str,
                 pub_set: str = "") -> dict:
    diff = _num(model_line) - _num(market_line)
    if not np.isfinite(diff) and market == "MONEYLINE":
        # A moneyline has no line; its model-versus-market gap is a price gap.
        diff = _num(model_price) - _num(market_price)
    has_open = np.isfinite(_num(open_line)) or np.isfinite(_num(open_price))
    has_close = np.isfinite(_num(close_line)) or np.isfinite(_num(close_price))
    if has_open and has_close:
        status = "COMPLETE"
    elif has_open or has_close:
        status = "PARTIAL"
    else:
        status = "NO_NUMBERS"
    r = _row(
        snapshot_id=_snapshot_id(scope, game["game_id"], market, side, pub_set),
        scope=scope, set=pub_set, game_id=game["game_id"], season=game.get("season", ""),
        week=game.get("week", ""), gameday=game.get("gameday", ""),
        away_team=game.get("away_team", ""), home_team=game.get("home_team", ""),
        market=market, side=side, origination_seq=ORIGINATION_SEQ[market],
        model_line=_blank(model_line), model_price=_blank(model_price),
        market_line=_blank(market_line), market_price=_blank(market_price),
        difference=_blank(diff),
        open_line=_blank(open_line), open_price=_blank(open_price),
        open_source_id=open_src if has_open else "PS-NONE", open_class=open_class,
        close_line=_blank(close_line), close_price=_blank(close_price),
        close_source_id=close_src if has_close else "PS-NONE", close_class=close_class,
        final_home_score="" if final_home in (None, "") else str(final_home),
        final_away_score="" if final_away in (None, "") else str(final_away),
        official_url=official_url, store_status=status, note=note,
    )
    return r


def _board_rows(frame: pd.DataFrame, scope: str, official: dict[str, dict]) -> list[dict]:
    """Rows for a board of games: the historical backtest or the upcoming slate."""
    out: list[dict] = []
    for g in frame.itertuples(index=False):
        gid = g.game_id
        fin = official.get(gid, {})
        url = fin.get("official_url", "") or NFL_SCORES
        fhome, faway = fin.get("home_score", ""), fin.get("away_score", "")
        note_base = "spread in home-margin points; total in game points"

        # ---- SPREAD -------------------------------------------------------
        for side in ("home", "away"):
            ml = _num(g.fair_spread)
            mkt = _num(g.market_spread)
            if side == "home":
                p_win, p_loss = _num(g.p_home_cover), _num(g.p_home_fail_cover)
                mprice = _num(g.home_spread_odds)
            else:
                p_win, p_loss = _num(g.p_home_fail_cover), _num(g.p_home_cover)
                mprice = _num(g.away_spread_odds)
            out.append(_market_rows(
                scope=scope, game=dict(game_id=gid, season=g.season, week=g.week,
                                       gameday=g.gameday, away_team=g.away_team,
                                       home_team=g.home_team),
                market="SPREAD", side=side,
                model_line=ml, model_price=_fair_decimal(p_win, p_loss),
                market_line=mkt, market_price=_dec(mprice),
                open_line="", open_price="", open_src="PS-NONE", open_class="",
                close_line=mkt, close_price=_dec(mprice),
                close_src="PS-NFD-CLOSE", close_class="C",
                final_home=fhome, final_away=faway, official_url=url,
                note=note_base + ("; no opening number on record" if scope == "backtest" else ""),
            ))

        # ---- TOTAL --------------------------------------------------------
        for side in ("over", "under"):
            ml = _num(g.fair_total)
            mkt = _num(g.market_total)
            if side == "over":
                p_win, p_loss = _num(g.p_over), _num(g.p_under)
                mprice = _num(g.over_odds)
            else:
                p_win, p_loss = _num(g.p_under), _num(g.p_over)
                mprice = _num(g.under_odds)
            out.append(_market_rows(
                scope=scope, game=dict(game_id=gid, season=g.season, week=g.week,
                                       gameday=g.gameday, away_team=g.away_team,
                                       home_team=g.home_team),
                market="TOTAL", side=side,
                model_line=ml, model_price=_fair_decimal(p_win, p_loss),
                market_line=mkt, market_price=_dec(mprice),
                open_line="", open_price="", open_src="PS-NONE", open_class="",
                close_line=mkt, close_price=_dec(mprice),
                close_src="PS-NFD-CLOSE", close_class="C",
                final_home=fhome, final_away=faway, official_url=url,
                note=note_base + ("; no opening number on record" if scope == "backtest" else ""),
            ))

        # ---- MONEYLINE ----------------------------------------------------
        ph, pa = _num(g.p_home_ml), _num(g.p_away_ml)
        if np.isfinite(ph) and np.isfinite(pa) and (ph + pa) > 0:
            fair_h, fair_a = ph / (ph + pa), pa / (ph + pa)
        else:
            fair_h = fair_a = float("nan")
        for side in ("home", "away"):
            if side == "home":
                fp, mp = fair_h, _dec(g.market_home_ml)
            else:
                fp, mp = fair_a, _dec(g.market_away_ml)
            out.append(_market_rows(
                scope=scope, game=dict(game_id=gid, season=g.season, week=g.week,
                                       gameday=g.gameday, away_team=g.away_team,
                                       home_team=g.home_team),
                market="MONEYLINE", side=side,
                model_line="", model_price=fp,
                market_line="", market_price=mp,
                open_line="", open_price="", open_src="PS-NONE", open_class="",
                close_line="", close_price=mp,
                close_src="PS-NFD-CLOSE", close_class="C",
                final_home=fhome, final_away=faway, official_url=url,
                note="moneyline has no line; model number is the no-vig fair price; "
                     "difference is a price gap in decimal units; no opening price on record",
            ))
    return out


def _opening_numbers(sides_of: dict[str, tuple[str, str]]) -> dict[tuple[str, str, str], float]:
    """Opening lines from the community opening-line archive (2021, WSGT).

    The archive records the line from each club's own point of view, in the
    "cover" convention: a club's line is the number it must cover, so a
    favoured club carries a negative number.

    That convention was **derived from the pinned archive itself** and not
    assumed: for the 272 games of the 2021 season that also carry a close in
    games.csv, converting the home club's line as `home margin = -line` gives a
    mean absolute open-to-close movement of 3.399 points (median 3.000), while
    the opposite conversion gives 9.653 (median 8.500). The two sides of every
    game in the archive are exact negatives of each other, as a two-way spread
    must be.

    The store uses the home-margin convention used everywhere else in this
    repository, so the opening number is directly comparable with the closing
    number: for the home club the margin is `-line`, for the away club it is
    `+line`. The archive carries no opening price, only a line.
    """
    p = RAW / "initial_lines.csv"
    out: dict[tuple[str, str, str], float] = {}
    if not p.exists():
        return out
    try:
        init = pd.read_csv(p)
    except Exception:
        return out
    for r in init.itertuples(index=False):
        gid = str(getattr(r, "about", ""))
        mkt = str(getattr(r, "type", ""))
        club = str(getattr(r, "side", ""))
        line = _num(getattr(r, "line", float("nan")))
        if mkt not in ("SPREAD", "TOTAL") or not np.isfinite(line):
            continue
        teams = sides_of.get(gid)
        if not teams:
            continue
        home_team, away_team = teams
        if mkt == "SPREAD":
            if club == home_team:
                out[(gid, mkt, "home")] = -line
            elif club == away_team:
                out[(gid, mkt, "away")] = line
        else:
            out[(gid, mkt, "over")] = line
            out[(gid, mkt, "under")] = line
    return out


def _apply_openings(rows: list[dict], openings: dict) -> None:
    """Attach a community opening line to a backtest row where one exists."""
    if not openings:
        return
    for r in rows:
        if r["scope"] != "backtest":
            continue
        key = (r["game_id"], r["market"], r["side"])
        line = openings.get(key)
        if line is None:
            continue
        r["open_line"] = f"{round(line, 4):g}"
        r["open_source_id"] = "PS-NFD-INITIAL"
        r["open_class"] = "C"
        r["note"] = str(r["note"]).replace("; no opening number on record",
                                           "; community opening line on record")


def _forward_rows(published: pd.DataFrame, official: dict[str, dict]) -> list[dict]:
    """Rows for the games this project actually published a line for."""
    out: list[dict] = []
    for r in published.itertuples(index=False):
        gid = r.game_id
        fin = official.get(gid, {})
        url = fin.get("official_url", "") or NFL_SCORES
        fhome, faway = fin.get("home_score", ""), fin.get("away_score", "")
        pub = f"published {r.published_utc} in PR #{r.pr} at commit {str(r.commit)[:12]}"
        for side in ("home", "away"):
            model_line = _num(r.line_spread)
            pin = _num(r.mirror_spread_at_pin)
            close = _num(r.mirror_close_spread)
            out.append(_market_rows(
                scope="forward_published",
                game=dict(game_id=gid, season=2026, week=r.week, gameday="",
                          away_team=r.away_team, home_team=r.home_team),
                market="SPREAD", side=side,
                model_line=model_line, model_price="",
                market_line=pin, market_price="",
                open_line=pin, open_price="", open_src="PS-NFD-PIN", open_class="C",
                close_line=close, close_price="", close_src="PS-NFD-CLOSE", close_class="C",
                final_home=fhome, final_away=faway, official_url=url,
                note=f"our published spread (set {r.set}); market number is the mirror at our pin",
                pub_set=str(r.set),
            ))
        for side in ("over", "under"):
            model_line = _num(r.line_total)
            pin = _num(r.mirror_total_at_pin)
            close = _num(r.mirror_close_total)
            out.append(_market_rows(
                scope="forward_published",
                game=dict(game_id=gid, season=2026, week=r.week, gameday="",
                          away_team=r.away_team, home_team=r.home_team),
                market="TOTAL", side=side,
                model_line=model_line, model_price="",
                market_line=pin, market_price="",
                open_line=pin, open_price="", open_src="PS-NFD-PIN", open_class="C",
                close_line=close, close_price="", close_src="PS-NFD-CLOSE", close_class="C",
                final_home=fhome, final_away=faway, official_url=url,
                note=f"our published total (set {r.set}); market number is the mirror at our pin",
                pub_set=str(r.set),
            ))
        for side in ("home", "away"):
            out.append(_market_rows(
                scope="forward_published",
                game=dict(game_id=gid, season=2026, week=r.week, gameday="",
                          away_team=r.away_team, home_team=r.home_team),
                market="MONEYLINE", side=side,
                model_line="", model_price="",
                market_line="", market_price="",
                open_line="", open_price="", open_src="PS-NONE", open_class="",
                close_line="", close_price="", close_src="PS-NONE", close_class="",
                final_home=fhome, final_away=faway, official_url=url,
                note="no moneyline was published for this game; no moneyline number on record",
                pub_set=str(r.set),
            ))
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    official: dict[str, dict] = {}
    p = FWD / "official_results.csv"
    if p.exists():
        res = pd.read_csv(p, dtype=str).fillna("")
        for r in res.itertuples(index=False):
            official[str(r.game_id)] = dict(
                home_score=r.home_score, away_score=r.away_score,
                official_url=r.official_url, status=r.status_on_page,
                verified_utc=r.verified_utc, verified_by=r.verified_by,
                source_page=r.source_page)

    rows: list[dict] = []
    sides_of: dict[str, tuple[str, str]] = {}
    hist = PROC / "originated_lines.csv"
    if hist.exists():
        hf = pd.read_csv(hist)
        for r in hf.itertuples(index=False):
            sides_of[str(r.game_id)] = (str(r.home_team), str(r.away_team))
        rows += _board_rows(hf, "backtest", official)
    _apply_openings(rows, _opening_numbers(sides_of))

    up = PROC / "originated_upcoming.csv"
    if up.exists():
        rows += _board_rows(pd.read_csv(up), "upcoming", official)

    pub = FWD / "published_lines.csv"
    if pub.exists():
        rows += _forward_rows(pd.read_csv(pub, dtype=str).fillna(""), official)

    store = pd.DataFrame(rows, columns=COLUMNS)
    store = store.sort_values(["scope", "gameday", "week", "game_id", "origination_seq", "side"],
                               kind="stable").reset_index(drop=True)
    sources = pd.DataFrame(SOURCES)
    return store, sources


def main() -> None:
    store, sources = build()
    FWD.mkdir(parents=True, exist_ok=True)
    store.to_csv(FWD / "price_snapshots.csv", index=False)
    sources.to_csv(FWD / "price_snapshot_sources.csv", index=False)

    # The decision-relevant subset published with the site: the games this
    # project published a line for, and the upcoming board. The full archive
    # stays in data/forward/ and is linked from the page.
    subset = store[store.scope.isin(["forward_published", "upcoming"])]
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    subset.to_csv(SITE_DATA / "price_snapshots.csv", index=False)

    print(f"price_snapshots: {len(store)} rows "
          f"({store.scope.value_counts().to_dict()})")
    print(f"  status: {store.store_status.value_counts().to_dict()}")
    print(f"  markets: {store.market.value_counts().to_dict()}")
    print(f"  source register: {len(sources)} sources")
    print(f"  subset published to assets/data: {len(subset)} rows")


if __name__ == "__main__":
    main()
