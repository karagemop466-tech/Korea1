"""T57 — correlations computed **only** from officially sourced numbers.

The brief asks for two things that the existing correlation tables do not do:

1. correlations computed only from officially sourced numbers, and
2. **n published with each value**.

This module answers both, on the sample that exists: the officially verified
results feed. Every number below is built from an official final score (class
A) and our own originated line (class B). Nothing from a community mirror
enters it — in particular the *market* lines do not, because those are class C,
so the legs are defined by our own model lines and the official result.

With n = 30 officially verified games these estimates are weak and are
published as weak. They exist so that the question "what is the correlation,
computed from official numbers only, and how many observations is it based on?"
has an answer that is not a guess, and so that the register can be re-run and
grow as the official feed is extended.

The mirror-based estimates remain in `data/processed/corr_*.csv` and stay blank
on the strict public page; they are published here only with their **n**, so a
reader can see how much data each claim rests on.

Outputs
-------
  data/processed/corr_official.csv   the official-only register
  assets/data/corr_official.csv       the same, for the site

Run:  python pipeline/official_correlations.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC  # noqa: E402

FWD = ROOT / "data" / "forward"
SITE_DATA = ROOT / "assets" / "data"

COLUMNS = [
    "pair", "leg_a", "leg_b", "n", "n_games",
    "phi", "ci_lo", "ci_hi", "p_joint", "p_if_independent", "lift",
    "evidence_class", "source", "note",
]


def _phi(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Phi (Matthews) correlation with a normal-approximation interval.

    The interval is the Fisher z transform on the phi scale. It assumes the
    observations are independent; with n this small that assumption is the
    weakest part of the estimate, and the note says so.
    """
    n = len(a)
    if n < 3:
        return float("nan"), float("nan")
    n11 = int(np.sum(a & b))
    n10 = int(np.sum(a & ~b))
    n01 = int(np.sum(~a & b))
    n00 = int(np.sum(~a & ~b))
    num = n11 * n00 - n10 * n01
    den = np.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    if den == 0:
        return float("nan"), float("nan")
    phi = float(num / den)
    phi = max(-0.999999, min(0.999999, phi))
    se = 1.0 / np.sqrt(n - 3.0)
    z = np.arctanh(phi)
    lo, hi = np.tanh(z - 1.959963985 * se), np.tanh(z + 1.959963985 * se)
    return phi, (float(lo), float(hi))


def build() -> pd.DataFrame:
    feed_path = FWD / "verified_results.csv"
    if not feed_path.exists():
        return pd.DataFrame(columns=COLUMNS)
    feed = pd.read_csv(feed_path, dtype=str).fillna("")
    if feed.empty:
        return pd.DataFrame(columns=COLUMNS)

    # One row per game: our model's line and the official final.
    games: dict[str, dict] = {}
    for r in feed.itertuples(index=False):
        g = games.setdefault(r.game_id, {})
        g.setdefault("margin", float(r.actual_margin))
        g.setdefault("total", float(r.actual_total))
        if r.market == "SPREAD" and r.side == "home":
            g["model_line"] = float(r.model_line) if r.model_line else float("nan")
            g["covers"] = (r.model_outcome == "WIN")
        if r.market == "TOTAL" and r.side == "over":
            g["model_total"] = float(r.model_line) if r.model_line else float("nan")
            g["over"] = (r.model_outcome == "WIN")
        if r.market == "MONEYLINE" and r.side == "home":
            g["home_win"] = (r.model_outcome == "WIN")

    rows = []
    usable = [g for g in games.values()
              if all(k in g for k in ("covers", "over", "home_win"))]
    n_games = len(usable)
    common_note = ("Computed only from officially verified final scores and our own "
                   "originated lines. The market's line is not used, because it is "
                   "not an official observation. The interval assumes independent "
                   "observations, which is the weakest assumption at this n.")
    for label, ka, kb, meaning in [
        ("Our spread side covers & our moneyline favours the home team",
         "covers", "home_win",
         "Both legs are read from the same margin distribution, so a high value "
         "here is expected by construction. It says the two legs of a same-game "
         "ticket are close to one signal, not that either has an edge."),
        ("Our spread side covers & the game goes over",
         "covers", "over",
         "The spread and the total are separate targets with separate fits, so "
         "this is a genuine dependence between two model outputs."),
        ("The game goes over & our moneyline favours the home team",
         "over", "home_win",
         "The total and the margin are separate targets, so this is a genuine "
         "dependence between two model outputs."),
    ]:
        a = np.array([bool(g[ka]) for g in usable])
        b = np.array([bool(g[kb]) for g in usable])
        n = int(len(a))
        phi, ci = _phi(a, b)
        if n:
            p_joint = float(np.mean(a & b))
            p_ind = float(np.mean(a) * np.mean(b))
            lift = p_joint / p_ind if p_ind else float("nan")
        else:
            p_joint = p_ind = lift = float("nan")
        rows.append(dict(
            pair=label, leg_a=ka, leg_b=kb, n=n, n_games=n_games,
            phi=round(phi, 6) if np.isfinite(phi) else "",
            ci_lo=round(ci[0], 6) if np.isfinite(ci[0]) else "",
            ci_hi=round(ci[1], 6) if np.isfinite(ci[1]) else "",
            p_joint=round(p_joint, 6), p_if_independent=round(p_ind, 6),
            lift=round(lift, 6) if np.isfinite(lift) else "",
            evidence_class="B (official final + our own line)",
            source="https://www.nfl.com/scores/",
            note=common_note + " " + meaning,
        ))
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    df = build()
    df.to_csv(PROC / "corr_official.csv", index=False)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    df.to_csv(SITE_DATA / "corr_official.csv", index=False)
    print(f"corr_official: {len(df)} pairs on "
          f"{int(df.n_games.iloc[0]) if len(df) else 0} officially verified games")
    if len(df):
        for r in df.itertuples(index=False):
            print(f"  {r.pair}: phi={r.phi} n={r.n}")


if __name__ == "__main__":
    main()
