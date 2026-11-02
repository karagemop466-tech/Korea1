# NFL Line Lab

Line origination, strategy competition and luck removal for NFL markets.

**Live site:** https://karagemop466-tech.github.io/Korea1/

Every number on that site is produced by the code in this repository from a pinned,
hash-verified upstream snapshot. Nothing is typed in by hand, and nothing is estimated to
fill a gap — where a value could not be verified it is left blank and listed on the
[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.

> **Audit note (2026-11-02).** Three sessions audited this repository the same day and their reports are
> published separately, not blended:
> an independent check against NFL.com found the sampled scores correct, but most table rows link to a
> community mirror and historical betting lines have no official source — published, not blanked, and
> flagged ([Independent audit](https://karagemop466-tech.github.io/Korea1/audit.html));
> a second audit re-derived every headline number (20/20 checks) and opened every citation
> ([Reproducibility audit](https://karagemop466-tech.github.io/Korea1/reproducibility.html));
> a third found two things neither of the others had: the weather imputer is fitted on the full sample
> before the walk-forward split (a leak our own tests did not catch), and the open board is empty and
> stale. Both are disclosed on the reproducibility page (IR-21, IR-22) and neither was fixed by
> back-filling or re-estimating — no published figure changed.

---

## What this is

| Question the project answers | Where |
|---|---|
| Can a market-free model originate a usable NFL spread, total and moneyline? | `pipeline/models.py` → `lines.html` |
| Do any betting strategies beat the closing market after the vig? | `pipeline/strategies.py` → `strategies.html` |
| Which of those results are skill, and which are luck? | `pipeline/validation.py` → `validation.html` |
| How correlated are the legs of a parlay or same-game parlay? | `pipeline/correlations.py` → `correlations.html` |
| What would a player-prop model need, and what is missing? | `props.html` |
| What is unverified, contradictory or incomplete? | `flagged.html` |
| Are the published numbers reproducible, and are the citations real? | `pipeline/audit.py` → `reproducibility.html` |
| Do the scores and sources match an *official* feed? | `pipeline/render_audit.py` → `audit.html` |

## Headline result

* The ensemble line is **good but not better than the market**: spread MAE 10.527 vs the
  closing line's 10.215; totals 10.727 vs 10.527, out of sample, 6,073 games, 2004–2026.
* **0 of 18 strategies clear all eight validation gates.** The best raw ROI (+21.6% on a 3-leg
  parlay ladder, 377 tickets) is what a high-variance long-shot book looks like, not an edge.
* **White's reality check does not reject** (p = 0.144 across 18 strategies and 425 weekly
  blocks): the library's best performance is consistent with luck.
* The closing prices carry a **2.72% mean two-way hold** over the whole sample — 2.25% for
  2006–2022 and 4.70% for 2023–2026 — so break-even is ≈51.4% on the earlier era and ≈52.4% on the
  later one. The site shows both rather than quoting one number for 20 seasons.
* Same-game legs are **not** independent: cover↔moneyline φ ≈ 0.68, cover↔total φ ≈ 0.024,
  cross-game legs r ≈ 0.01 (interval spans zero).
* Prop combos are **leg-specific**: QB passing + WR1 receiving co-move (r ≈ 0.44 within player),
  WR1/WR2 receiving yards are nearly independent (r ≈ 0.03), and QB passing vs RB1 rushing is
  negative (r ≈ −0.13). No prop *price* exists in any reached source, so no prop P&L is claimed.
* An independent audit session re-derived **20/20** headline checks from the pinned data and opened
  every citation (**10/13** verify today; the rest are flagged, not hidden). Two findings of parallel
  audits — a fold-preprocessing leak and an empty, stale open board — are disclosed, not repaired.

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
pipeline/            all analysis code (see methodology.html for the dataflow)
pipeline/audit.py    independent re-derivation of every headline number (reproducibility.html)
pipeline/render_audit.py  NFL.com score sample and per-row source tiers (audit.html)
data/processed/      generated tables (committed; the site reads them)
data/sources.json    pinned commit SHA + per-file SHA-256
*.html + assets/     the GitHub Pages site, including audit.html and reproducibility.html — served from
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
6. A second session audits the build rather than trusting it: `pipeline/audit.py` recomputes the
   headline numbers, hashes the raw files against the pinned commit, and records the status of every
   cited link with the date it was opened. It fails the build on a mismatch. See `reproducibility.html`.

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
