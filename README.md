# K1 NFL Line Lab

Originating NFL lines, running a leaderboard of betting strategies, and measuring how much of each
strategy's record is skill versus luck.

**Live dashboard:** published with GitHub Pages from `main` (repository root — the Pages site is configured
as "deploy from branch `main`, `/`" and the session token has no Pages write scope, so the generated pages
live at the root). See `COORDINATION.md` for the deploy record and URL.

## Read this first

- **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)** — the whole project on one page, with every number.
- **[COORDINATION.md](COORDINATION.md)** — task board, sources, verification performed, flagged items,
  deploy record, handoff notes.

## What is in here

| Path | What it is |
|---|---|
| `analysis/common.py` | pinned sources, odds maths, bootstrap/FDR/Reality-Check statistics |
| `analysis/fetch_data.py` | stages the pinned raw data into `data/raw` (git-ignored) |
| `analysis/build_games.py` | canonical game table + leak-free pre-game features + integrity report |
| `analysis/model.py` | walk-forward ridge power ratings → originated spread and total |
| `analysis/residual_model.py` | walk-forward P(cover) / P(over) edge models |
| `analysis/signals.py` | the 24-strategy library (hypothesis, rule, motivation, source per strategy) |
| `analysis/backtest.py` | scoring, 8 validation gates, FDR, White Reality Check, leaderboard |
| `analysis/portfolio.py` | walk-forward "selective skill" allocation test |
| `analysis/parlays.py` | correlation values and parlay pricing (same-game and cross-game) |
| `analysis/build_players.py` | player-game stats from the official NFL Game Center feed |
| `analysis/props.py` | prop correlations, combo pricing framework, interval calibration |
| `analysis/verify.py` | automated integrity checks + the live official cross-check log |
| `analysis/build_site.py` | static dashboard generator → repository root (served by Pages) |
| `tests/` | look-ahead/leak tests and the site link checker |

## Results in one paragraph

24 strategies, 27,330 bets priced at real two-sided closing quotes (2006–2026). **No strategy passes all
eight validation gates.** The best raw performer (+7.14% ROI, wind-driven unders, n = 430) fails the
false-discovery-rate gate; White's Reality Check gives p = 0.970. The originated line model lands within
0.4 points of the market's spread error but has no exploitable edge (out-of-sample calibration slope
−0.0011). Correlations are measured rather than assumed: spread × moneyline φ = +0.672, spread × total
φ = +0.014, and player-prop QB pass yards × WR1 receiving yards φ = +0.249. Cross-game parlays cost
−7.9% (2 legs), −14.4% (3), −15.4% (4). Everything that could not be verified is blank and listed on the
site's **Flagged for review** page.

## Run it

```bash
pip install -r requirements.txt
python -m analysis.run_all     # fetch → build → model → backtest → verify → site  (~4 min)
python -m tests.check_links    # verify the generated site has no broken links
pytest -q tests                # leak / look-ahead tests
```

Raw data is git-ignored and re-staged from pinned commits on every run, so a fresh clone reproduces the
same numbers. The site is plain static HTML/CSS/JS with no external dependencies, emitted at the
repository root (`index.html` + eight subpages + `assets/`) plus `.nojekyll` so Pages serves it raw.

## Ground rules the code enforces

1. **No look-ahead.** Every feature, and every model output, is a function of games that kicked off
   earlier only — enforced by `tests/test_no_lookahead.py`.
2. **No invented prices.** Bets settle at the two-sided quotes stored upstream; a bet without a quote is
   dropped, never filled with −110.
3. **No hand-entered numbers on the site.** Pages are generated from `data/site/*.json` and
   `data/derived/*.csv`.
4. **Unverified stays blank.** Unconfirmed values are empty and flagged, never inferred.

---

## Parallel dashboard, kept for provenance

`origin/main` also merged a hand-written, design-only dashboard (session `arena/cbd229fe-korea1`) whose
position was that no empirical results could be published. It is preserved at
`archive/arena-cbd229fe/` (`index.html`, `pages/`, `assets/`, `docs/`, `index.md`,
`FLAGGED_FOR_REVIEW.md`, `check_site.py`) and is **not** the canonical site — the generated dashboard at the
repository root is. Two reconciliations matter:

- Its objection (no rights-cleared outcomes, no timestamped price archive) does not hold here: nflverse
  game data pinned to fixed commits supplies both outcomes and closing prices. It still holds for player
  props, which carry no prices — flagged as IR-03, not filled in.
- Its caution that the earlier draft's YoY correlation ranges (EPA ~0.55–0.65, ATS% −0.05, …) were
  unsupported by official sources was correct. Those numbers are used nowhere in this pipeline; the
  correlation table is measured from the data.

Their README's verified-source register (NFL GSIS, official NFL stats pages, NGS glossary, NIST,
scikit-learn, GitHub Pages docs, Singapore GRA) remains a useful list of *official* references and is
retained in their README, quoted here in the archived copy.

