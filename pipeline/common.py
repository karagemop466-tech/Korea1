"""Shared paths, constants and helpers for the NFL line-origination pipeline.

Every number published by this project is produced by code in `pipeline/` from
the pinned source snapshot recorded in `data/sources.json`. Nothing is typed in
by hand.
"""
from __future__ import annotations

import hashlib
import json
import os
import math
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
# Independent official-source verification artefacts (session arena/917fe36e-korea1).
LIVE_DIR = ROOT / "data" / "live"
# The moment the official pages were read for the 2026-11-13 verification pass. It is a
# constant, not a clock reading, so that `make build` is byte-reproducible: the extract in
# data/live/ is a fixed document and its capture time is part of that document.
LIVE_CAPTURE_UTC = "2026-11-13T22:57:59Z"
SITE = ROOT
SITE_DATA = SITE / "assets" / "data"

for _p in (RAW, PROC, SITE_DATA, LIVE_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pinned upstream snapshot
# ---------------------------------------------------------------------------
# nflverse/nfldata is a public data repository maintained by Lee Sharpe that
# mirrors the nflverse game-level tables (schedules + closing lines). We pin an
# exact commit SHA so the build is byte-reproducible.
NFD, NFDATA_REPO = "nflverse/nfldata", "nfldata"
NFDATA_SHA = os.environ.get("NFDATA_SHA", "")  # filled by fetch_data.py


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


def read_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fmt(x, nd=2, dash="—", signed=False):
    """Format a number for the site; None/NaN renders as an em dash, never 0."""
    if x is None:
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f != f:  # NaN
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


# American odds helpers ------------------------------------------------------
def american_to_decimal(a: float) -> float:
    """Convert valid American odds to decimal (payout multiple incl. stake)."""
    a = float(a)
    if not math.isfinite(a) or -100 < a < 100:
        raise ValueError(f"invalid American odds: {a}")
    if a > 0:
        return 1.0 + a / 100.0
    return 1.0 + 100.0 / abs(a)


def decimal_to_american(d: float) -> float:
    d = float(d)
    if d >= 2.0:
        return (d - 1.0) * 100.0
    return -100.0 / (d - 1.0)


def implied_prob(american: float) -> float:
    a = float(american)
    return (-a) / (-a + 100.0) if a < 0 else 100.0 / (a + 100.0)


def novig_probs(odds_a: float, odds_b: float):
    """Multiplicative (proportional) de-vig for a two-way market."""
    pa, pb = implied_prob(odds_a), implied_prob(odds_b)
    s = pa + pb
    if s <= 0:
        return float("nan"), float("nan")
    return pa / s, pb / s


SOURCES = {
    "nflverse_nfldata": {
        "label": "nflverse/nfldata — games.csv (nflverse game-level schedule + closing lines)",
        "url": "https://github.com/nflverse/nfldata/blob/master/data/games.csv",
        "kind": "open data mirror of NFL GSIS game results; maintained by nflverse",
    },
    "nflverse_nfldata_repo": {
        "label": "nflverse/nfldata repository (data dictionary: DATASETS.md)",
        "url": "https://github.com/nflverse/nfldata/blob/master/DATASETS.md",
        "kind": "documentation",
    },
    "nflverse_closing": {
        "label": "nflverse/nfldata — closing_lines.csv (per-side close price + outcome, 2006-2018)",
        "url": "https://github.com/nflverse/nfldata/blob/master/data/closing_lines.csv",
        "kind": "open data",
    },
    "nflverse_initial": {
        "label": "nflverse/nfldata — initial_lines.csv (2021 openers, book WSGT)",
        "url": "https://github.com/nflverse/nfldata/blob/master/data/initial_lines.csv",
        "kind": "open data",
    },
    "nflverse_sclines": {
        "label": "nflverse/nfldata — sc_lines.csv (SuperContest consensus lines 2013-2020)",
        "url": "https://github.com/nflverse/nfldata/blob/master/data/sc_lines.csv",
        "kind": "open data",
    },
    "nflverse_schedules_release": {
        "label": "nflverse-data release `schedules` (canonical games.csv distribution point)",
        "url": "https://github.com/nflverse/nflverse-data/releases/tag/schedules",
        "kind": "open data release",
    },
    "nfl_operations": {
        "label": "NFL Football Operations — official playing rules (scoring, overtime, spots)",
        "url": "https://operations.nfl.com/the-rules/nfl-rulebook/",
        "kind": "official NFL",
    },
    "nfl_rule_ot": {
        "label": "NFL Rulebook, Rule 16 — sudden death / overtime procedures",
        "url": "https://operations.nfl.com/the-rules/nfl-rulebook/",
        "kind": "official NFL",
    },
    "nfl_gsis": {
        "label": "NFL Game Statistics & Information System (GSIS) — source of the game IDs used here",
        "url": "https://www.nfl.com/",
        "kind": "official NFL",
    },
}
