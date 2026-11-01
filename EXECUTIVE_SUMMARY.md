# Executive summary — NFL line origination, signal research & leaderboard design

**Live site:** https://karagemop466-tech.github.io/Korea1/
**Repository:** `karagemop466-tech/Korea1` · **Session:** `S-ARENA-EA02C4FB` · **Date:** 2026-11-01
**Data window:** 2,945 NFL games, 2011–2021 · 18 pre-specified strategies · 9/9 verification checks passing

---

## 1. What was asked, and what exists now

| Requirement | Delivered | Where |
|---|---|---|
| Collect and organize a full requirements list | Task board with 12 scoped tasks, claim log and integration log | `COORDINATION.md` |
| Originate our own NFL lines | Walk-forward Elo + pace engine producing spread, total and moneyline for every game | `scripts/02_line_model.py`, site → *Originated lines* |
| Research and develop useful signals | 18 pre-specified rules across model-edge, market-microstructure, situational, behavioural and price-structure families | `scripts/03_strategies.py`, site → *Strategies* |
| Single bets, parlays, prop combos | Full single-bet battery; parlay pricing kernel; measured prop-leg correlations from play-by-play | site → *Correlation & parlays*, *Player props* |
| Each strategy must pass validation gates | Eight pre-specified gates, applied to all 18 strategies | `scripts/06_validation.py`, site → *Validation gates* |
| Determine correlation values | Game-level, binary-leg and player-prop correlations measured from 2,945 games and 1,086 team-games | `data/correlations.json`, `data/props.json` |
| Remove luck; build selectively skill-based strategies | Deflated Sharpe, season overdispersion, signal persistence, and a mixed-field simulation that quantifies how much of a leaderboard is luck | `scripts/06_validation.py` §luck |
| Leaderboard competition with rewards | Luck-adjusted skill score (LASS), five tiers, reward weights, seven anti-gaming rules | `research/04-competition.md`, site → *Leaderboard design* |
| Executive summary | This document | `EXECUTIVE_SUMMARY.md` |
| Live GitHub Pages site with categories and tables | 9 pages, every table row carrying a source link | `docs/` |
| Flag irregularities and unverified values | 14 logged items, each with a source link and a disposition | site → *Flagged for review* |
| Verification line by line, no hallucination | 9 automated checks + per-field integrity gate + cross-source validation | `scripts/99_verify.py`, `data/verification.json` |

---

## 2. The ten numbers that matter

| # | Result | Value | Source of the number |
|---|---|---|---|
| 1 | Measured cost of a bet (mean overround on 2,941 closing moneylines) | **3.79%** | computed, `data/correlations.json` |
| 2 | Official realised hold, Nevada Sports Pool (12 months to Nov 2025) | **6.74%** | NGCB report |
| 3 | Official realised hold, Nevada Sports **Parlay Cards** (same period) | **19.94%** | NGCB report |
| 4 | Our model's spread error vs the closing market's | **10.47 vs 10.15 pts** | computed, `data/lines.json` |
| 5 | Strategies clearing all eight gates | **0 of 18** | `data/validation.json` |
| 6 | Expected best Sharpe of pure luck across 18 trials | **0.0926 per bet** | `data/validation.json` |
| 7 | Winner's median ROI in a **zero-skill** 1,000-bettor field (one season) | **+18.7%** | simulation |
| 8 | P(genuine 2% edge finishes 1st) — on ROI vs on CLV | **0.32% vs 78.9%** | simulation |
| 9 | Bets needed to prove a 2% edge by win/loss alone | **17,796 (≈67 seasons)** | power arithmetic |
| 10 | Measured QB × WR1 correlation (the one exploitable stack) | **ρ = 0.441** | play-by-play 2021–2022 |

---

## 3. Findings

### 3.1 The market is the benchmark, and our own model does not beat it
The line engine is legitimate — it produces a spread, total and moneyline for every game with
reasonable probability calibration — but out of sample it is **worse than the closing line on every
accuracy metric** (spread MAE 10.47 vs 10.15, straight-up 66.4% vs 67.3%, totals 10.86 vs 10.60).
Betting its disagreements loses **more than the vig**: S01 −10.9% (p < 0.001) and S17 −9.7%
(p = 0.0004) after false-discovery correction. The market's price is not merely good; our model's
errors are systematically in the direction the market already knows about.

### 3.2 No strategy survived the gates — and that is the correct outcome
Gate pass counts across the battery: G1 sample 16/18, G2 significance 0/18, G3 out-of-sample 2/18,
G4 robustness 1/18, G5 economic edge 4/18, G6 risk 2/18, G7 inputs 18/18, **G8 selection bias 0/18**.
Two results are published as *Watch* rather than *Fund*:

* **S12** — Over the lowest-decile totals: **+5.79% ROI**, out-of-sample +6.10%, survives −115
  (+3.69%) — but only 226 bets, p = 0.349, DSR = 0.326. It fails the sample-size, significance and
  selection-bias gates.
* **S11** — Under the highest-decile totals: **+0.79 points of CLV per bet**, the best in the battery,
  but ROI +0.91% and −1.16% at −115.

### 3.3 Correlation is where the real structure is
* **QB passing yards × WR1 receiving yards: ρ = 0.441** (within-player), replicated across two
  seasons (0.427, 0.457). Two 50/50 legs are worth **3.10**, not the 4.00 an independent price
  implies — a **39.7%** gap between the empirical joint and independence.
* **WR1 × WR2 is mildly positive**, not negative: ρ = +0.035 for yards, **+0.18 for receptions**.
  The intuitive "hedge" between two receivers on the same team is priced backwards.
* **QB × RB1 is the one clearly negative pair** (ρ = −0.135): game script moves them in opposition.
* The closed-form parlay kernel `P = 1/4 + arcsin(ρ)/(2π)` is verified against Monte Carlo and
  against the empirics (maximum prediction error 0.034).

### 3.4 A raw-profit competition is a lottery; a CLV competition is a skill test
* In a 1,000-bettor field with **zero** skill, the winner's median ROI after one 267-bet season is
  **+18.7%**. Any payout on that basis rewards luck.
* A bettor with a genuine **2% edge** finishes first **0.32%** of the time on an ROI board and
  **78.9%** of the time on a closing-line-value board.
* Proving a 2% edge by win/loss alone needs **17,796 bets (~67 seasons)** — so validation must run on
  CLV and volume, not on P&L.
* Therefore the competition scores **LASS** = shrinkage × (0.5·CLV t-stat + 0.3·return Sharpe +
  0.2·selection-bias correction), with a hard ceiling: a strategy failing G8 can never rank above
  *Paper*. Applying it to this battery yields **0 Gold, 0 Silver, 0 Bronze, 4 Watch, 14 Paper**.

---

## 4. What is verified, and how

| Verification | Result |
|---|---|
| Formula harness (odds, de-vig, Shin, copula, Kelly, BH, DSR, settlement) | 33 assertions pass, Monte-Carlo where a closed form is claimed |
| Cross-source validation, 2021 | final scores **263/263** agree; closing totals within 1 pt on **97.1%**; spreads **86.5%** |
| Field-level integrity gate | 2,945 usable games; 260 corrupted closing spreads and 259 corrupted totals **nulled, not repaired** |
| Club division map vs nflverse reference | **32/32** clubs match |
| Source register | 12 sources, each with URL, trust tier and verification note |
| Link check | 9 pages, 110 internal links, 33 source references, 0 broken |
| Site build | 9/9 verification checks pass at publish time |

**Two real data bugs were caught and fixed during the build** (both documented, not hidden): a
de-margining implementation that silently produced nonsense longshot probabilities, and a
play-by-play flag parser that silently reported zero touchdowns and receptions for every player.

---

## 5. What is *not* verified (published, never guessed)

| Item | Why | Effect |
|---|---|---|
| Player-prop **prices** and prop ROI | no licence-clean price history reachable | correlations only; no prop P&L claimed |
| **Live 2026 lines** | no live feed reachable (data stops 2021; play-by-play stops at a partial 2023) | live board explicitly marked blocked |
| Injury / weather / travel / officiating inputs | no feed | excluded from the model, stated openly |
| Two peer-reviewed DOIs (BH 1995, Kelly 1956) | not re-resolved this session | formulas unit-tested; citations flagged for manual confirmation |
| Postseason games in the sample | archive has no season-type field (~4% of games) | bounded impurity, flagged |

All of these sit on the **Flagged for review** page with source links, and none of them blocks the
site being live.

---

## 6. Honest limitations

1. **Odds are third-party.** No official historical line archive exists; every price is labelled as
   third-party with its verification note.
2. **The model is results-only.** No injuries, weather or personnel. It is a line-origination engine,
   not an edge.
3. **Prop work stops at correlation.** Without prop prices there is no way to claim a prop strategy.
4. **The simulation is a CLT approximation** to the exact binomial, validated against brute force
   (median winner 14.40% exact vs 14.29% approximate).
5. **One market, one era.** 2011–2021 NFL sides/totals; conclusions may not transfer to props,
   in-play, or other leagues.

---

## 7. Recommended next steps (in order)

1. **Attach a live odds + play-by-play feed.** That single unblock turns the *Originated lines* engine
   into a weekly board and lets the same gate set run forward. Nothing in the code needs rebuilding.
2. **Buy or build a historical player-prop price archive.** The correlation table is already done;
   prices are the missing half of the prop opportunity.
3. **Pre-register the inverse-model signal** (F-03: the model's edge is significantly negative) and
   test it forward — it may not be harvested ex post without a new trial counter.
4. **Choose a repository licence** (I-01a) before any external reuse.
5. **Run the leaderboard live** with LASS scoring on at least one full season before paying any reward.

---

## 8. How to reproduce everything

```bash
bash scripts/run_all.sh      # ingest → line model → strategies → correlations → props
                             # → validation → leaderboard → site → verification → link check
```

Every number on the site and in these documents is produced by that pipeline from hash-pinned raw
files (`data/raw_manifest.json`). Nothing is hand-typed, so nothing can drift.
