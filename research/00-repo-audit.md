# Repo audit — `karagemop466-tech/Korea1`

**Audit time:** 2026-11-01 13:19–13:35 UTC
**Auditor session:** S-ARENA-EA02C4FB
**Method:** every claim below was produced by a command run against the live repository and the
GitHub API, not from memory. Commands are reproducible.

## 1. What existed before this session

| Item | Finding | Evidence |
|---|---|---|
| Commits | 1 — `d8d7d81 Initial commit`, author `karagemop466-tech <karagemop466@gmail.com>`, 2026-10-31 15:32 −0700 | `git log --oneline -5` |
| Files | 1 — `README.md`, 8 bytes, content `# Korea1` with no trailing newline | `git show --stat HEAD` → `1 file changed, 1 insertion(+)`; file size 8 bytes |
| Branches | `main`, `arena/ea02c4fb-korea1` (this session's fixed branch) | `git branch -a` |
| Licence | none (`license: null` in the API) | `gh api repos/karagemop466-tech/Korea1` |
| Description / homepage | both null | same API call |
| CI / workflows | none | repository tree |
| `.gitignore` | none | repository tree |
| GitHub Pages | **enabled**, `status: built`, `build_type: legacy`, source branch `main`, path `/`, URL https://karagemop466-tech.github.io/Korea1/ | `gh api repos/karagemop466-tech/Korea1/pages` |
| Repo size | 0 KB (empty apart from the one-line README) | same API call |

## 2. Irregularities flagged

| # | Irregularity | Why it matters | Disposition |
|---|---|---|---|
| I-01 | **The repository was empty.** No data, no analysis, no site, no licence, no CI. | There was nothing to "review line by line"; the entire project had to be built. Everything published by this session is new and is evidenced by its own scripts. | Logged. All new data files are reproducible from `scripts/00_ingest.py` with pinned SHA-256 hashes in `data/raw_manifest.json`. |
| I-01a | **No licence file.** | Publishing derived datasets without a licence leaves the owner's rights undefined. Only the owner can choose one; inventing one would be worse than leaving it out. | Flagged, not resolved. Recommend the owner add a licence. |
| I-02 | **No official historical NFL odds source exists.** The NFL does not publish betting lines, and no sportsbook publishes a licence-clean machine-readable history of its own prices. | Every odds-derived number in this project is therefore *third-party*, not official. Presenting it as official would be a fabricated claim. | Odds are labelled `verified_third_party` on every page, with the archive URL and a per-row verification column. |
| I-03 | **The only reachable odds archive covers 2011–2021 and has field-level defects** (260 corrupted closing spreads, 259 corrupted closing totals, 4 impossible moneyline pairs, 10 missing Super Bowls because neutral-site games are stored with `home_team = "0"`, 1 unresolvable "New York" row). | Silently repairing those rows would fabricate prices. | The integrity gate (`G0`) nulls the bad *field* and keeps the row; nothing is imputed. Coverage is printed on every affected page. |
| I-04 | **No historical player-prop prices were reachable.** | Prop *correlations* are computed from real play-by-play, but the prop *lines* those legs would be priced against cannot be verified, so no prop ROI is claimed anywhere. | Prop pages show correlations and fair prices only; prop P&L is marked unverified/absent. |
| I-05 | **No live 2026 data feed.** Play-by-play reachable here stops at a partial 2023 season; the odds archive stops at 2021. | The line-origination engine therefore cannot be pointed at this week's games without a feed. Publishing "this week's lines" would be invention. | The live board is explicitly marked as blocked on a data feed; the engine is demonstrated walk-forward on real seasons instead. |
| I-06 | **The odds archive stores teams under 44 different names**, including `BuffaloBills`, `KCChiefs`, `Fortyniners`, `LosAngeles`, `SanDiego`, `St.Louis`, `Tampa`, `Washingtom` (sic) and `0`. | Fuzzy matching would silently merge the Jets and the Giants. | An explicit normalisation table maps every nickname to one club; the two genuinely ambiguous names (`NewYork`, `0`) are excluded rather than guessed. |
| I-07 | **Play-by-play flag columns are stored as `"1.0"`/`"0.0"`, not `"1"`/`"0"`.** | A parser that tests `== "1"` silently reports **zero** touchdowns and **zero** receptions for every player — a total data corruption that produces plausible-looking garbage. This bug was actually hit and fixed during the build; the first run of `05_props.py` produced `P(both WR1/WR2 receptions over) = 1.000`, which is what exposed it. | Fixed with a single `_flag()` parser; the failure mode is documented in the script and in `COORDINATION.md`. |
| I-08 | **`2H_total` and `2H_spread` columns in the archive are unusable** (values like `2H_total = 3.0`). | They cannot support second-half betting research. | Not used anywhere in the project. |

## 3. Things that were checked and found consistent

* `aria`/`nflverse` division map: 32/32 clubs match, zero mismatches (`scripts/99_verify.py`).
* 2021 final scores: 263/263 overlapping games agree between the odds archive and independent
  play-by-play.
* 2021 closing totals: 97.1% within 1 point between the two sources; closing spreads 86.5% within
  1 point. The gap is what you expect from two different books/snapshots, and is reported rather
  than hidden.
* Quarter scores sum exactly to the final score in 2,845 of 2,945 games; the remaining 100 are
  overtime games, identified by an overtime-sized gap (2/3/6/7/9 points). One game has a 12-point
  gap that is not a legal overtime score and is flagged as a scrape defect.
* Moneyline conventions: the archive stores the spread from the home club's perspective with
  **negative = home favoured**; nflverse stores `spread_line` with **positive = home favoured**.
  The two were verified to be exact sign-flips on the overlap, which is what makes the
  cross-validation meaningful.

## 4. What this session did not do

* Did not modify `README.md` history or the initial commit.
* Did not create a licence, a description, or a CI workflow — those are owner decisions
  (`COORDINATION.md` §5 logs the licence gap).
* Did not claim any value that a script in this repository does not compute.
