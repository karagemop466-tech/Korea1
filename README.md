# NFL Line Lab

Originating our own NFL lines, testing betting signals honestly, measuring the correlations that
actually price a same-game parlay, and scoring skill instead of luck.

**Live site:** https://karagemop466-tech.github.io/Korea1/
**Executive summary:** [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
**Task board:** [COORDINATION.md](COORDINATION.md)

---

## Result in one line

An 18-strategy battery, a walk-forward line model, measured correlation values and eight validation
gates on 2,945 real NFL games (2011–2021): **no strategy cleared all eight gates**, our own model is
measurably worse than the closing line, and the one genuine structure found is the QB/WR1 stack
(ρ = 0.441). A raw-profit leaderboard is a lottery; a closing-line-value leaderboard is a skill test.

## What is here

| Path | Contents |
|---|---|
| `docs/` | the static site served by GitHub Pages (9 pages, every table row sourced) |
| `data/derived/games.csv` | analysis-ready game table produced by the integrity gate |
| `data/*.json` | every computed result: `lines`, `strategies`, `correlations`, `props`, `validation`, `leaderboard`, `sources`, `verification`, `linkcheck` |
| `data/raw_manifest.json` | SHA-256 of every raw input byte used |
| `research/` | market structure, methodology, validation gates, competition design, repo audit |
| `scripts/` | the entire pipeline (Python standard library only) |
| `scripts/tests/` | formula verification, including Monte-Carlo checks of closed forms |

## Reproduce

```bash
bash scripts/run_all.sh
```

Standard-library Python 3.11 only — no dependencies to install. Raw inputs are downloaded from pinned
public sources and hashed; nothing is committed as raw bytes.

## Verification

```bash
python3 scripts/99_verify.py    # 9 checks: formulas, divisions, integrity, cross-source, bookkeeping, sources, gates
python3 scripts/98_linkcheck.py # links, assets, source ids, tag balance, navigation
python3 scripts/tests/test_math.py
```

Both are wired into `run_all.sh` and the site build refuses to publish on failure.

## Data sources and trust tiers

* **Official** — NFL Football Operations rulebook; Nevada Gaming Control Board revenue reports.
* **Peer reviewed** — Bailey & López de Prado (2014); Gray & Gray (1997); Levitt (2004); Shin (1993);
  Benjamini & Hochberg (1995); Kelly (1956).
* **Verified third party** — nflverse play-by-play and team reference; Sportsbook Review archive
  mirrored on GitHub.

The full register, including how each entry was verified, is in `data/sources.json` and on the site's
*Sources* page.

## Things this project does **not** claim

* No betting advice, no live wagering, no guarantee of profit.
* No player-prop profitability (no licence-clean prop price history was reachable).
* No live 2026 lines (no live feed; the engine is demonstrated walk-forward on real seasons instead).
* No "official odds": the NFL does not publish betting lines, so every price here is third-party and
  labelled as such.

Every defect, gap and unverified value is listed on the **Flagged for review** page with a source link.

## Licence

No licence is set on this repository. That is an owner decision, logged as item **I-01a** on the
Flagged for review page — choose a licence before reusing any of this material.
