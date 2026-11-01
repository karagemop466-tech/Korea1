# NFL Line Lab

Line origination, strategy competition and luck removal for NFL markets.

**Live site:** https://karagemop466-tech.github.io/Korea1/

Every number on that site is produced by the code in this repository from a pinned,
hash-verified upstream snapshot. Nothing is typed in by hand, and nothing is estimated to
fill a gap — where a value could not be verified it is left blank and listed on the
[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.

---

## What this is

| Question the project answers | Where |
|---|---|
| Can a market-free model originate a usable NFL spread, total and moneyline? | `pipeline/models.py` → `docs/lines.html` |
| Do any betting strategies beat the closing market after the vig? | `pipeline/strategies.py` → `docs/strategies.html` |
| Which of those results are skill, and which are luck? | `pipeline/validation.py` → `docs/validation.html` |
| How correlated are the legs of a parlay or same-game parlay? | `pipeline/correlations.py` → `docs/correlations.html` |
| What would a player-prop model need, and what is missing? | `docs/props.html` |
| What is unverified, contradictory or incomplete? | `docs/flagged.html` |

## Headline result

* The ensemble line is **good but not better than the market**: spread MAE 10.527 vs the
  closing line's 10.215; totals 10.727 vs 10.527, out of sample, 6,073 games, 2004–2026.
* **0 of 18 strategies clear all eight validation gates.** The best raw ROI (+21.6% on a 3-leg
  parlay ladder, 377 tickets) is what a high-variance long-shot book looks like, not an edge.
* **White's reality check does not reject** (p = 0.144 across 18 strategies and 425 weekly
  blocks): the library's best performance is consistent with luck.
* The closing prices used carry a **2.7% two-way hold**, so break-even is ≈51.4%, not 52.4%.
* Same-game legs are **not** independent: cover↔moneyline φ ≈ 0.68, cover↔total φ ≈ 0.024,
  cross-game legs φ ≈ 0.01 (interval spans zero).

## Data

Single pinned commit of `nflverse/nfldata`, archived from `codeload.github.com` and SHA-256
hashed on arrival. The exact commit and per-file hashes are in
[`data/sources.json`](data/sources.json).

| File | Rows | Use |
|---|---|---|
| `games.csv` | 7,548 | schedules, final scores, closing spread/total/moneyline and prices |
| `closing_lines.csv` | 20,490 | independent per-side price + outcome (settlement cross-check) |
| `initial_lines.csv` | 1,088 | 2021 openers only |
| `sc_lines.csv` | 4,092 | SuperContest consensus lines 2013–2020 |
| `win_totals.csv` | 576 | season win totals with prices |

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pandas numpy scipy
make build        # fetch → build → models → backtest → strategies → correlations → site → verify
```

`make build` ends with `pipeline/verify_site.py`, which fails the build if any table row lacks a
source link, any internal link is broken, or any unformatted missing value reaches a table.

## Repository layout

```
pipeline/            all analysis code (see docs/methodology.html for the dataflow)
data/processed/      generated tables (committed; the site reads them)
data/sources.json    pinned commit SHA + per-file SHA-256
docs/                the GitHub Pages site (static HTML/CSS, no CDN, no framework)
COORDINATION.md      multi-session task board and work log
```

## Honesty rules used in this build

1. No value is inferred, interpolated or back-filled. Missing → blank → flagged.
2. Models never see the market, and never see anything after kickoff (asserted in code).
3. Every bet is settled at the **recorded** closing price; `-110` is never substituted.
4. All strategies are declared before they are run; every result is published, including failures.
5. The settlement engine is cross-checked against nflverse's own outcome column (99.93% exact
   agreement where the two files carry the same line).

## Licence and attribution

Data: [nflverse](https://github.com/nflverse/nfldata) (open data). Official NFL rules:
[operations.nfl.com](https://operations.nfl.com/the-rules/nfl-rulebook/). This repository contains
analysis code and derived tables only; it redistributes no play-by-play data.
