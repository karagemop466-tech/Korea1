"""S1/S3 — the price-snapshot store, and the three-column line comparison.

Two things happen here, both offline and both reproducible:

1. **The store.** `data/prices/price_store.csv` is an append-only log: one row
   per (snapshot, game, market, side) with the number that was observed, the time it
   was observed, where it came from and what evidence class that source carries.
   Nothing is edited in place; a later capture adds rows, it never rewrites earlier
   ones. `data/prices/open_close.csv` is derived from that log: the *opening* number
   is the earliest pre-kickoff observation of a market, the *closing* number is the
   latest one.

2. **The comparison.** `data/prices/line_comparison.csv` publishes, for every market
   this project originates, three separate columns — the model's fair line, the
   market's line and the difference between them — plus the same three quantities in
   price space for the moneyline.

The origination order is published with the numbers: `data/processed/origination_order.csv`
records that the side (spread) is originated first, the total second and the moneyline
third, with the step each one depends on.

Sources
  data/prices/mirror_snapshots.csv   mirror snapshots, one per pinned upstream commit
                                     (written by scripts/capture_price_snapshot.py,
                                     each row's source file hash verified against the
                                     forward ledger's snapshot manifest)
  data/processed/originated_lines.csv / originated_upcoming.csv   model + market lines
  data/forward/picks.csv             the prices frozen in the forward ledger

Run:  python pipeline/price_store.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA, read_json  # noqa: E402

PRICES = ROOT / "data" / "prices"
FWD = ROOT / "data" / "forward"

# The order in which this project originates a market. The moneyline is derived from
# the same margin prediction that produces the spread, so it can only be originated
# after the side; the total is a separate prediction and is originated second.
ORIGINATION_ORDER = [
    dict(step=1, market="SPREAD", label="the side",
         depends_on="predicted home margin (ensemble)",
         description=("The side is originated first: the ensemble's home margin is mapped "
                      "to a handicap through the same empirical residual distribution that "
                      "prices pushes, so the spread is the first number a board can show."),
         published_as="fair_spread, market_spread, difference"),
    dict(step=2, market="TOTAL", label="the total",
         depends_on="predicted game total (ensemble)",
         description=("The total is originated second and independently of the side: it is a "
                      "separate two-member ensemble over the same walk-forward training "
                      "windows, so no information from the spread leaks into it."),
         published_as="fair_total, market_total, difference"),
    dict(step=3, market="MONEYLINE", label="the moneyline",
         depends_on="step 1 — the same home-margin prediction",
         description=("The moneyline is originated third because it is priced from the side's "
                      "margin prediction: the win/tie/loss probabilities come from the margin "
                      "distribution at zero, and the two-way quote adds the modelled hold."),
         published_as="originated odds, market odds, probability difference"),
]


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def load_snapshots() -> pd.DataFrame:
    path = PRICES / "mirror_snapshots.csv"
    if not path.exists():
        # The capture is a network step, so the build must not depend on it: the
        # store is then empty and the page says the store has not been captured.
        print("  price_store: no mirror capture on record "
              "(run scripts/capture_price_snapshot.py); the store stays empty")
        return pd.DataFrame(columns=["snapshot_sha", "snapshot_utc", "snapshot_date", "season",
                                     "week", "gameday", "away_team", "home_team", "game_id",
                                     "market", "side", "line", "odds", "source_url",
                                     "evidence_class"])
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in ("season", "week"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ("line", "odds"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["snapshot_date"] = df["snapshot_utc"].str.slice(0, 10)
    df["gameday"] = df["gameday"].str.slice(0, 10)
    return df


def build_store(snaps: pd.DataFrame) -> pd.DataFrame:
    """Append-only log of every observed number, with a stable id."""
    rows = snaps.copy()
    rows["source_kind"] = "mirror_commit"
    rows["source_sha"] = rows["snapshot_sha"]
    rows["note"] = "upstream commit captured by scripts/capture_price_snapshot.py; file hash verified"

    # The prices the forward ledger froze before kickoff are a further observation of
    # the same market. They are appended, never merged into an earlier row.
    picks_path = FWD / "picks.csv"
    if picks_path.exists():
        picks = pd.read_csv(picks_path, dtype=str).fillna("")
        extra = []
        for r in picks.to_dict("records"):
            markets = _split_list(r.get("leg_markets", ""))
            sides = _split_list(r.get("sides", ""))
            lines = _split_list(r.get("lines", ""))
            prices = _split_list(r.get("prices", ""))
            gids = _split_list(r.get("game_ids", ""))
            for i, gid in enumerate(gids):
                m = markets[i] if i < len(markets) else ""
                s = sides[i] if i < len(sides) else ""
                ln = _num(lines[i]) if i < len(lines) else None
                pr = _num(prices[i]) if i < len(prices) else None
                if not gid or not m:
                    continue
                extra.append(dict(
                    snapshot_sha="", snapshot_utc=r.get("frozen_utc", ""),
                    snapshot_date=(r.get("frozen_utc", "") or "")[:10],
                    season=int(r.get("season") or 0), week=int(r.get("week") or 0),
                    gameday="", away_team="", home_team="", game_id=gid,
                    market=m, side=s, line=ln, odds=pr,
                    source_url="", source_kind="frozen_ledger_pick",
                    source_sha="", evidence_class="D - depends on a community-mirror price",
                    note="price frozen in the append-only forward ledger before kickoff",
                ))
        if extra:
            rows = pd.concat([rows, pd.DataFrame(extra)], ignore_index=True)

    rows["snapshot_date"] = rows["snapshot_date"].fillna("")
    rows = rows.sort_values(["game_id", "market", "side", "snapshot_utc"]).reset_index(drop=True)
    rows.insert(0, "snapshot_id", [f"PS-{i:06d}" for i in range(1, len(rows) + 1)])
    cols = ["snapshot_id", "snapshot_utc", "snapshot_date", "season", "week", "gameday",
            "game_id", "away_team", "home_team", "market", "side", "line", "odds",
            "source_kind", "source_sha", "source_url", "evidence_class", "note"]
    return rows[cols]


def _split_list(text: str) -> list[str]:
    s = str(text or "").strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    if not s:
        return []
    return [x.strip().strip("'\"") for x in s.split(",") if x.strip()]


def derive_open_close(store: pd.DataFrame) -> pd.DataFrame:
    """Opening and closing number per (game, market, side)."""
    out = []
    for (gid, market, side), grp in store.groupby(["game_id", "market", "side"], sort=True):
        grp = grp.sort_values("snapshot_utc")
        gameday = next((g for g in grp["gameday"] if g), "")
        pre = grp[grp["snapshot_date"] <= gameday] if gameday else grp.iloc[0:0]
        pre = pre if len(pre) else grp
        first, last = pre.iloc[0], pre.iloc[-1]
        line_open, line_close = _num(first["line"]), _num(last["line"])
        odds_open, odds_close = _num(first["odds"]), _num(last["odds"])
        move = None
        if line_open is not None and line_close is not None:
            move = round(line_close - line_open, 4)
        out.append(dict(
            game_id=gid, market=market, side=side,
            season=int(first["season"] or 0), week=int(first["week"] or 0),
            gameday=gameday,
            away_team=first["away_team"], home_team=first["home_team"],
            open_line=line_open, open_odds=odds_open,
            open_snapshot_utc=first["snapshot_utc"], open_source_kind=first["source_kind"],
            open_source_url=first["source_url"],
            close_line=line_close, close_odds=odds_close,
            close_snapshot_utc=last["snapshot_utc"], close_source_kind=last["source_kind"],
            close_source_url=last["source_url"],
            n_snapshots=int(len(grp)), n_pre_kickoff=int(len(pre)),
            line_move=move,
            pre_kickoff_observations="yes" if len(pre) else "no",
            evidence_class=last["evidence_class"],
        ))
    return pd.DataFrame(out).sort_values(["game_id", "market", "side"]).reset_index(drop=True)


def model_lines() -> pd.DataFrame:
    """The model's fair lines and the market's lines, in one frame."""
    played = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    played["status"] = "played"
    fut = pd.read_csv(PROC / "originated_upcoming.csv", low_memory=False)
    fut["status"] = "scheduled"
    keep = ["game_id", "season", "week", "gameday", "away_team", "home_team", "status",
            "fair_spread", "market_spread", "edge_spread",
            "fair_total", "market_total", "edge_total",
            "originated_home_ml", "originated_away_ml", "market_home_ml", "market_away_ml",
            "p_home_ml", "p_away_ml", "p_tie"]
    frames = []
    for df in (played, fut):
        for c in keep:
            if c not in df.columns:
                df[c] = pd.NA
        frames.append(df[keep])
    return pd.concat(frames, ignore_index=True)


def build_comparison(model: pd.DataFrame, oc: pd.DataFrame) -> pd.DataFrame:
    """Three separate columns per market: model fair line, market line, difference.

    The market line is taken from the published board when the board carries one, and
    otherwise from the price store's latest pre-kickoff observation. Which of the two
    was used is published in `market_line_source`, because a board line and a store
    line can be a day apart.
    """
    key = {(r["game_id"], r["market"], r["side"]): r for r in oc.to_dict("records")}
    rows = []
    for r in model.to_dict("records"):
        gid = r["game_id"]
        for market, side, fair, mkt in [
            ("SPREAD", "home", r.get("fair_spread"), r.get("market_spread")),
            ("TOTAL", "over", r.get("fair_total"), r.get("market_total")),
            ("MONEYLINE", "home", r.get("originated_home_ml"), r.get("market_home_ml")),
            ("MONEYLINE", "away", r.get("originated_away_ml"), r.get("market_away_ml")),
        ]:
            fair_v, mkt_v = _num(fair), _num(mkt)
            store = key.get((gid, market, side))
            store_line = None
            store_utc = ""
            store_src = ""
            if store is not None:
                store_line = store["close_odds"] if market == "MONEYLINE" else store["close_line"]
                store_utc = store["close_snapshot_utc"]
                store_src = store["close_source_kind"]
            if mkt_v is None and store_line is not None:
                mkt_v = store_line
                source = f"price store close ({store_utc})"
            elif mkt_v is not None:
                source = "published board line"
            else:
                source = "no market line on record"
            diff = None
            if fair_v is not None and mkt_v is not None:
                diff = round(fair_v - mkt_v, 4)
            rows.append(dict(
                game_id=gid, season=r.get("season"), week=r.get("week"), gameday=r.get("gameday"),
                away_team=r.get("away_team"), home_team=r.get("home_team"), game_status=r.get("status"),
                market=market, side=side,
                model_fair_line=fair_v, market_line=mkt_v, difference=diff,
                unit=("points" if market in ("SPREAD", "TOTAL") else "American odds"),
                market_line_source=source, market_line_observed_utc=store_utc,
                model_price=None, market_price=None, probability_difference=None,
            ))
    cmp_df = pd.DataFrame(rows)

    # Moneyline in probability space: the model probability against the de-vigged
    # market probability. A points difference is meaningless on a price.
    mp = model.set_index("game_id")
    store_by_game: dict[str, dict[str, float]] = {}
    for (gid, market, side), row in key.items():
        if market != "MONEYLINE":
            continue
        store_by_game.setdefault(gid, {})[side] = row["close_odds"]
    for idx, r in cmp_df[cmp_df.market == "MONEYLINE"].iterrows():
        g, side = r["game_id"], r["side"]
        p_model = None
        if g in mp.index:
            m = mp.loc[g]
            p_model = _num(m.get("p_home_ml" if side == "home" else "p_away_ml"))
        h_ml, a_ml = None, None
        if g in mp.index:
            m = mp.loc[g]
            h_ml, a_ml = _num(m.get("market_home_ml")), _num(m.get("market_away_ml"))
        sg = store_by_game.get(g, {})
        if h_ml is None and sg.get("home") is not None:
            h_ml = sg.get("home")
        if a_ml is None and sg.get("away") is not None:
            a_ml = sg.get("away")
        p_market = None
        if h_ml is not None and a_ml is not None and h_ml != 0 and a_ml != 0:
            hp = (-h_ml) / (-h_ml + 100.0) if h_ml < 0 else 100.0 / (h_ml + 100.0)
            ap = (-a_ml) / (-a_ml + 100.0) if a_ml < 0 else 100.0 / (a_ml + 100.0)
            if hp + ap > 0:
                p_market = hp / (hp + ap) if side == "home" else ap / (hp + ap)
        cmp_df.loc[idx, "model_price"] = p_model
        cmp_df.loc[idx, "market_price"] = p_market
        if p_model is not None and p_market is not None:
            cmp_df.loc[idx, "probability_difference"] = round(p_model - p_market, 4)
            cmp_df.loc[idx, "difference"] = round(p_model - p_market, 4)
            cmp_df.loc[idx, "unit"] = "probability (de-vigged)"
    return cmp_df


def main() -> None:
    PRICES.mkdir(parents=True, exist_ok=True)
    snaps = load_snapshots()
    if not len(snaps):
        return
    store = build_store(snaps)
    oc = derive_open_close(store)
    model = model_lines()
    cmp_df = build_comparison(model, oc)

    # Attach the observed opening/closing numbers to the comparison table.
    key = {(r["game_id"], r["market"], r["side"]): r for r in oc.to_dict("records")}
    oc_open, oc_close = [], []
    for r in cmp_df.to_dict("records"):
        row = key.get((r["game_id"], r["market"], r["side"]))
        if row is None:
            oc_open.append(None)
            oc_close.append(None)
            continue
        moneyline = r["market"] == "MONEYLINE"
        oc_open.append(row["open_odds"] if moneyline else row["open_line"])
        oc_close.append(row["close_odds"] if moneyline else row["close_line"])
    cmp_df["observed_open"] = oc_open
    cmp_df["observed_close"] = oc_close
    # The comparison is published for the season this project originates.
    cmp_df = cmp_df[cmp_df.season.astype("Int64") == 2026].reset_index(drop=True)

    store.to_csv(PRICES / "price_store.csv", index=False)
    oc.to_csv(PRICES / "open_close.csv", index=False)
    cmp_df.to_csv(PRICES / "line_comparison.csv", index=False)
    pd.DataFrame(ORIGINATION_ORDER).to_csv(PROC / "origination_order.csv", index=False)
    for f in ("price_store.csv", "open_close.csv", "line_comparison.csv"):
        (SITE_DATA / f).write_bytes((PRICES / f).read_bytes())
    (SITE_DATA / "origination_order.csv").write_bytes((PROC / "origination_order.csv").read_bytes())

    moved = oc[oc.line_move.notna() & (oc.line_move != 0)]
    print(f"  price_store.csv       {len(store):,} rows")
    print(f"  open_close.csv        {len(oc):,} rows ({len(moved):,} with a recorded line move)")
    print(f"  line_comparison.csv   {len(cmp_df):,} rows")
    print(f"  origination_order.csv {len(ORIGINATION_ORDER)} steps")


if __name__ == "__main__":
    main()
