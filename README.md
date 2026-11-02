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
| What does the brief actually require, and what proves each item? | `requirements/requirements.csv` → [`REQUIREMENTS.md`](REQUIREMENTS.md), `requirements.html` |
| Can a market-free model originate a usable NFL spread, total and moneyline? | `pipeline/models.py` → `lines.html` |
| Do any betting strategies beat the closing market after the vig? | `pipeline/strategies.py` → `strategies.html` |
| Which of those results are skill, and which are luck? | `pipeline/validation.py` → `validation.html` |
| How correlated are the legs of a parlay or same-game parlay? | `pipeline/correlations.py` → `correlations.html` |
| What would a player-prop model need, and what is missing? | `props.html` |
| What is unverified, contradictory or incomplete? | `flagged.html` |
| Is the published site actually reproducible, cell by cell? | `pipeline/audit.py` → `verification.html` |

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
* The **open board** publishes the model's own spread, total and both moneyline prices for every
  scheduled game at the snapshot — 164 games, 28 of which also carry a market number to compare
  against (fixed this session; before the fix every future line was blank).

## Independent audit of this build (2026-11-02)

`python pipeline/audit.py --rebuild` does not trust the build's own claims. It re-downloads the
**pinned** upstream archive and re-hashes every file, rebuilds every artefact from that archive in a
throwaway directory, and re-derives published table cells from the CSVs they name. Current result:

| Audit stage | Result |
|---|---|
| Provenance — pinned files re-hashed from the recorded commit | **7 / 7 match** |
| Rebuild — derived tables and rendered pages reproduced byte-for-byte | **36 / 36 identical** (only the `generated …` footer timestamp is normalised) |
| Claims — published cells re-derived from the underlying data | **60 / 60 exact** |
| Drift — upstream HEAD vs the pin | upstream has moved ahead; **12 games were settled upstream after the pin** |

That drift is published, not patched: the site's numbers stay tied to one snapshot so they are
reproducible, and the delta is measured on [`verification.html`](https://karagemop466-tech.github.io/Korea1/verification.html).
Defects found by this audit and fixed are recorded in `COORDINATION.md` — the largest was that every
future line on the "open board" was blank, because unplayed games carry no recorded kickoff weather
and the missing input propagated into the design matrix (D-01).

## Data

Single pinned commit of `nflverse/nfldata`, archived from `codeload.github.com` and SHA-256
hashed on arrival. The exact commit and per-file hashes are in
[`data/sources.json`](data/sources.json). Because upstream refreshes continuously, the site states
its snapshot date in every footer; `make build` re-pins to whatever master is at run time, while
`NFDATA_SHA=<pinned commit> make build` reproduces the published build exactly.

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
make build        # fetch → build → models → backtest → correlations → site → summary → audit → verify
make audit-full   # the same audit with the clean-room rebuild (~90 s)
```

`make build` ends with `pipeline/verify_site.py`, which fails the build if any table row lacks a
source link, any internal link is broken, or any unformatted missing value reaches a table. CI runs
that verifier, the offline form of the audit, and both page checkers on every push.

## Repository layout

```
pipeline/            all analysis code (see methodology.html for the dataflow)
data/processed/      generated tables (committed; the site reads them)
data/sources.json    pinned commit SHA + per-file SHA-256
*.html + assets/     the GitHub Pages site (static HTML/CSS, no CDN, no framework) — served from
                     the repository root, because Pages is configured as `main` / (verified against
                     the Pages API; an earlier note here said docs/, which does not exist)
lab/                 the replication annex (see below) — a second site, same questions, other data
scripts/             the annex pipeline and its own verifiers
requirements/        the requirement list (CSV) that generates REQUIREMENTS.md and requirements.html
COORDINATION.md      multi-session task board and work log
```

## Honesty rules used in this build

1. No value is inferred, interpolated or back-filled. Missing → blank → flagged. The one
   substitution in the build is disclosed on the flagged page: unplayed games have no recorded
   kickoff weather, so future lines use the training median for temperature and wind while the
   `temp_missing` / `wind_missing` flags stay at 1. No settled-game number uses it.
2. Models never see the market, and never see anything after kickoff (asserted in code).
3. Every bet is settled at the **recorded** closing price; `-110` is never substituted.
4. All strategies are declared before they are run; every result is published, including failures.
5. The settlement engine is cross-checked against nflverse's own outcome column (99.93% exact
   agreement where the two files carry the same line).

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
