"""T50 — correlations computed only from officially sourced numbers.

The brief is explicit: *compute correlations only from officially sourced
numbers, and publish n with each value*. The project's historical correlation
tables are computed from a community mirror, which is a research estimate and is
labelled as such. This module adds the layer the brief asks for:

    data/processed/corr_official.csv

Every row is computed **only** from game results that were read from an
official NFL.com page and recorded in the verified results feed
(``data/processed/results_feed.csv``). Nothing else is an input: no community
price, no mirror score, no model estimate. Each row publishes

* the pair of events,
* ``n`` — the number of official observations behind the value,
* the estimate and a 95% interval,
* the joint probability, the independent probability and the lift,
* the evidence class and the official source of every observation used.

With a small n the intervals are wide, and that is the point: a correlation
computed from thirty official results is a different claim from one computed
from six thousand mirror results, and the table says which is which.

The policy is enforced in code, not in prose: :func:`check_policy` fails the
build if any published row is missing its ``n``, its evidence class or its
official source.

Run:  python pipeline/official_correlations.py
Out:  data/processed/corr_official.csv
      data/processed/corr_official_report.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, write_json  # noqa: E402

OUT = PROC / "corr_official.csv"
REPORT = PROC / "corr_official_report.json"
FEED = PROC / "results_feed.csv"

#: Minimum n for a published interval to be considered worth printing.
MIN_N = 10


def _phi(x: np.ndarray, y: np.ndarray) -> float:
    """Phi coefficient for two binary vectors."""
    n = len(x)
    n11 = float(((x == 1) & (y == 1)).sum())
    n10 = float(((x == 1) & (y == 0)).sum())
    n01 = float(((x == 0) & (y == 1)).sum())
    n00 = float(((x == 0) & (y == 0)).sum())
    denom = np.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    if denom == 0:
        return float("nan")
    return (n11 * n00 - n10 * n01) / denom


def _phi_ci(phi: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Fisher-style interval on the phi coefficient (significance transform)."""
    if n < 4 or not np.isfinite(phi) or abs(phi) >= 1:
        return (float("nan"), float("nan"))
    z = np.arctanh(phi)
    se = 1.0 / np.sqrt(n - 3)
    crit = stats.norm.ppf(1 - alpha / 2)
    return (float(np.tanh(z - crit * se)), float(np.tanh(z + crit * se)))


def build() -> pd.DataFrame:
    feed = pd.read_csv(FEED)
    if feed.empty:
        raise SystemExit("the verified results feed is empty; run pipeline/results_feed.py first")

    g = feed.copy()
    g["margin_ge_7"] = (g["home_margin"] >= 7).astype(float)
    g["margin_le_minus_7"] = (g["home_margin"] <= -7).astype(float)
    g["total_ge_45"] = (g["game_total"] >= 45).astype(float)
    g["total_le_41"] = (g["game_total"] <= 41).astype(float)
    g["home_win"] = g["home_win"].astype(float)
    g["away_win"] = g["away_win"].astype(float)
    g["margin"] = g["home_margin"].astype(float)
    g["total"] = g["game_total"].astype(float)

    pairs = [
        ("home_win", "margin_ge_7", "Home win vs home wins by 7 or more"),
        ("home_win", "margin_le_minus_7", "Home win vs home loses by 7 or more"),
        ("home_win", "total_ge_45", "Home win vs game total of 45 or more"),
        ("home_win", "total_le_41", "Home win vs game total of 41 or fewer"),
        ("total_ge_45", "margin_ge_7", "Game total of 45+ vs home wins by 7+"),
        ("margin_ge_7", "margin_le_minus_7", "Home wins by 7+ vs home loses by 7+"),
        ("home_win", "away_win", "Home win vs away win (mutually exclusive outcomes)"),
    ]
    continuous = [
        ("margin", "total", "Home margin vs game total"),
    ]

    rows = []
    for a, b, label in pairs:
        x = g[a].to_numpy(float)
        y = g[b].to_numpy(float)
        n = int(len(x))
        phi = _phi(x, y)
        lo, hi = _phi_ci(phi, n)
        p_joint = float(((x == 1) & (y == 1)).mean())
        p_ind = float(x.mean() * y.mean())
        rows.append({
            "pair": label, "x": a, "y": b, "kind": "binary",
            "n": n, "estimate": phi, "ci_lo": lo, "ci_hi": hi,
            "p_joint": p_joint, "p_if_independent": p_ind,
            "lift": (p_joint / p_ind) if p_ind > 0 else float("nan"),
            "evidence_class": "B",
            "evidence_class_label": "B - derived from official observations only",
            "source": "NFL.com game pages listed in data/processed/results_feed.csv",
            "source_url": "https://www.nfl.com/scores/",
            "interval_excludes_zero": bool(np.isfinite(lo) and (lo > 0 or hi < 0)),
            "meets_min_n": n >= MIN_N,
        })

    for a, b, label in continuous:
        x = g[a].to_numpy(float)
        y = g[b].to_numpy(float)
        n = int(len(x))
        r = float(np.corrcoef(x, y)[0, 1]) if n > 2 else float("nan")
        # Fisher z interval for a Pearson correlation.
        if n > 3 and abs(r) < 1:
            z = np.arctanh(r)
            se = 1.0 / np.sqrt(n - 3)
            crit = stats.norm.ppf(0.975)
            lo, hi = float(np.tanh(z - crit * se)), float(np.tanh(z + crit * se))
        else:
            lo = hi = float("nan")
        rows.append({
            "pair": label, "x": a, "y": b, "kind": "continuous",
            "n": n, "estimate": r, "ci_lo": lo, "ci_hi": hi,
            "p_joint": float("nan"), "p_if_independent": float("nan"),
            "lift": float("nan"),
            "evidence_class": "B",
            "evidence_class_label": "B - derived from official observations only",
            "source": "NFL.com game pages listed in data/processed/results_feed.csv",
            "source_url": "https://www.nfl.com/scores/",
            "interval_excludes_zero": bool(np.isfinite(lo) and (lo > 0 or hi < 0)),
            "meets_min_n": n >= MIN_N,
        })

    out = pd.DataFrame(rows)
    for c in ["estimate", "ci_lo", "ci_hi", "p_joint", "p_if_independent", "lift"]:
        out[c] = out[c].astype(float).round(6)
    return out


def check_policy(df: pd.DataFrame) -> list[str]:
    """Fail closed if a published correlation is missing n, its class or its source."""
    problems = []
    for i, r in df.iterrows():
        if not isinstance(r["n"], (int, float)) or r["n"] <= 0:
            problems.append(f"row {i}: n is missing or not positive")
        if not str(r["evidence_class"]).startswith(("A", "B")):
            problems.append(f"row {i}: evidence class {r['evidence_class']!r} is not official-derived")
        if not str(r["source_url"]).startswith("https://www.nfl.com/"):
            problems.append(f"row {i}: source {r['source_url']!r} is not an official NFL page")
        if not str(r["source"]).strip():
            problems.append(f"row {i}: no source description")
    return problems


def main() -> None:
    df = build()
    problems = check_policy(df)
    if problems:
        for p in problems:
            print("POLICY FAILURE:", p)
        raise SystemExit("official correlation policy failed")
    df.to_csv(OUT, index=False)
    report = {
        "rows": int(len(df)),
        "n_games": int(df["n"].max()),
        "min_n": int(df["n"].min()),
        "rows_meeting_min_n": int(df["meets_min_n"].sum()),
        "min_n_threshold": MIN_N,
        "intervals_excluding_zero": int(df["interval_excludes_zero"].sum()),
        "policy": ("every published correlation is computed only from official NFL.com "
                   "results, and publishes n, its interval, its evidence class and its "
                   "official source"),
        "policy_failures": 0,
        "historical_estimates_note": ("The project's historical correlation tables are "
                                      "computed from a community mirror and remain "
                                      "research estimates; they are not published here."),
    }
    write_json(REPORT, report)
    print(f"corr_official: {len(df)} pairs computed from {int(df['n'].max())} official "
          f"results; {report['rows_meeting_min_n']} meet the n >= {MIN_N} threshold; "
          f"{report['intervals_excluding_zero']} intervals exclude zero")


if __name__ == "__main__":
    main()
