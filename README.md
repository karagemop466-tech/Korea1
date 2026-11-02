# NFL Line Lab

Line origination, strategy competition and luck control for NFL markets.

**Live site:** https://karagemop466-tech.github.io/Korea1/

Every number on that site is produced by the code in this repository from a pinned,
hash-verified upstream snapshot. Nothing is typed in by hand, and nothing is estimated to
fill a gap — where a value could not be verified it is left blank and listed on the
[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.

> **Audit note (2026-11-02):** an independent check against NFL.com found the sampled scores correct, but most table rows
> link to a community mirror and historical betting lines have no official source — they are published, not blanked, and flagged.
> See the [Independent audit](https://karagemop466-tech.github.io/Korea1/audit.html).

---

## What this is

| Question the project answers | Where |
|---|---|
| Can a market-free model originate a usable NFL spread, total and moneyline? | `pipeline/models.py` → `lines.html` |
| Do any betting strategies beat the closing market after the vig? | `pipeline/strategies.py` → `strategies.html` |
| Which of those results are skill, and which are luck? | `pipeline/validation.py` → `validation.html` |
| How correlated are the legs of a parlay or same-game parlay? | `pipeline/correlations.py` → `correlations.html` |
| Can player props be originated, and how correlated are the legs? | `pipeline/props_model.py` → `props.html` |
| What would a player-prop model need, and what is missing? | `props.html` |
| What is unverified, contradictory or incomplete? | `flagged.html` |

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
* **Player props are now modelled, not blank.** 21,033 player-games (2019–2022 play-by-play) produce
  9,730 walk-forward prop lines with out-of-sample AUC 0.66–0.73; QB passing yards and his own WR1's
  receiving yards lift the joint hit rate 1.14× over independence (φ = 0.152, CI excludes zero), and
  a cross-game control sits at φ = −0.036 with an interval spanning zero. No prop **price** exists in
  any reachable source, so every prop combo fails the economic gate and nothing is awarded.

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

A second source carries player-level play-by-play: 2019–2022 gzip blobs from
`clausherther/nfl-dbt`, fetched through the GitHub git-blob API (release assets are blocked at the
network level, git blobs are not), pinned by blob SHA and SHA-256 hashed into
[`data/sources_pbp.json`](data/sources_pbp.json). The aggregation is validated against seven
published season totals, keyed on player id — a name key silently merges J.J. Taylor into
Jonathan Taylor.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pandas numpy scipy
make build        # fetch → datasets → models → backtest → strategies → props → site → verify
make props        # player-level play-by-play → prop lines, calibration, correlations, combos
make test         # prop leakage/integrity tests + link check + per-row source check
```

`make build` ends with `pipeline/verify_site.py`, which fails the build if any table row lacks a
source link, any internal link is broken, or any unformatted missing value reaches a table.

## Repository layout

```
pipeline/            all analysis code (see methodology.html for the dataflow)
pipeline/fetch_pbp.py  pinned per-season play-by-play (git-blob API) → data/sources_pbp.json
pipeline/props_model.py prop lines, calibration, leg correlations, combo pricing → prop_*.csv
data/processed/      generated tables (committed; the site reads them)
data/sources.json    pinned commit SHA + per-file SHA-256
*.html + assets/     the GitHub Pages site (static HTML/CSS, no CDN, no framework) — served from
                     the repository root, because Pages is configured as `main` / (verified against
                     the Pages API; an earlier note here said docs/, which does not exist)
lab/                 the replication annex (see below) — a second site, same questions, other data
scripts/             the annex pipeline and its own verifiers
COORDINATION.md      multi-session task board and work log
```

## Honesty rules used in this build

1. No value is inferred, interpolated or back-filled. Missing → blank → flagged.
2. Models never see the market, and never see anything after kickoff (asserted in code).
3. Every bet is settled at the **recorded** closing price; `-110` is never substituted.
4. All strategies are declared before they are run; every result is published, including failures.
5. The settlement engine is cross-checked against nflverse's own outcome column (99.93% exact
   agreement where the two files carry the same line).
6. Prop lines carry no market input, are built only from earlier games, and are re-tested for
   prefix stability in `tests/test_props_integrity.py`: deleting every game after a cut-off must
   not move a single prediction at or before it.
7. A build re-pins nothing: `pipeline/fetch_data.py` reuses the commit recorded in
   `data/sources.json`, so `make build` reproduces the published numbers instead of drifting to
   today's upstream head.

## Licence and attribution

Data: [nflverse](https://github.com/nflverse/nfldata) (open data). Official NFL rules:
[operations.nfl.com](https://operations.nfl.com/the-rules/nfl-rulebook/). This repository contains
analysis code and derived tables only; it redistributes no play-by-play data.

---

## Replication annex: a fourth build, on different data (`lab/`)

Four sessions claimed this repository at the same moment and three of them built the whole thing. Rather
than delete a finished pipeline, session `arena/ea02c4fb-korea1` publishes its build as a **replication
annex**: the same four questions answered from a *different* odds archive by *different* code, so the main
results can be checked against an independent draw. Its site is at [`lab/index.html`](lab/index.html) and
it is reachable from the dashboard navigation ("Replication annex").

| | `pipeline/` (canonical) | `analysis/` (first build, retained) | `lab/` (annex) |
|---|---|---|---|
| Odds source | nflverse `nfldata` | nflverse `nfldata` | Sportsbook Review 10-year archive |
| Games | 7,384 (1999–2026) | 7,384 | 2,945 (2011–2021) |
| Priced bets | 26,168 | 27,330 | 959 qualifying of 2,280 |
| Strategies | 18 | 24 | 18 |
| Site | root | root pages superseded | `lab/` |

Reproduce the annex with `bash scripts/run_all.sh` (adds `data/lab/` + `lab/`, runs its two verifiers,
exits non-zero on any failure). Read its narrative in
[`research/05-annex-executive-summary.md`](research/05-annex-executive-summary.md).

**What replicated, independently:**

1. **No strategy clears every gate** — 0 of 18 in the annex, 0 of 24 in the first build, and the canonical
   build's best candidate fails its false-discovery gate.
2. **The originated line does not beat the close** — annex spread MAE 10.473 vs market 10.151; canonical
   10.527 vs 10.216.
3. **Apparent edge is mostly luck** — annex in-sample → out-of-sample ROI rank correlation 0.485 against an
   expected best Sharpe of 0.093 for 18 zero-skill trials.
4. **CLV, not ROI, is the skill-bearing statistic** — in a 20,000-trial field of 999 zero-skill bettors plus
   one skilled bettor, the skilled bettor finishes first 78.9% of the time by CLV and 0.32% by ROI.

The annex writes only to `data/lab/` and `lab/`; it never touches `pipeline/`, `analysis/`, `data/processed/`
or the root pages' content (the one shared edit is a single nav entry in `pipeline/render_site.py`, logged
in `COORDINATION.md`).
