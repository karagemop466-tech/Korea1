# Official availability snapshot audit — 2026-11-13

> Dated audit of the committed snapshot, not a live feed or a prediction. No missing status, roster role, or point impact is inferred.

## Snapshot and source inventory

- Captured: `2026-11-13T18:32:20Z` (2026 Week 10).
- The current data snapshot was committed as [`43a946a`](https://github.com/karagemop466-tech/Korea1/commit/43a946aed4c3ec86b17b920757dc780ced73ea93).
- The scheduled official-source capture run completed successfully: [GitHub Actions run 43483547465](https://github.com/karagemop466-tech/Korea1/actions/runs/43483547465).
- The site deploy for that snapshot completed successfully: [GitHub Pages run 43483664141](https://github.com/karagemop466-tech/Korea1/actions/runs/43483664141); public site: <https://karagemop466-tech.github.io/Korea1/>.
- Source HTML response bodies are not retained in this snapshot directory; each manifest row stores the official URL, response metadata and response SHA-256. The digest cannot be recomputed without the original body.
- Data page: [availability.html](../availability.html).

The table below lists all 33 source attempts: the NFL injury-report page and every club's official depth-chart page. Every source row links directly to the official NFL or club page. `Parsed rows` is the captured manifest value; `Published depth rows` counts current rows actually available for the club after the explicit failure/fallback rule.

| Kind | Club | Capture result | HTTP | Parsed rows | Published depth rows | Response bytes | Response SHA-256 | Official source |
|---|---|---|---:|---:|---:|---:|---|---|
| injury_report | NFL | Captured | 200 | 326 | — (see injury rows) | 406320 | `7b4a9c83247c9d86367f1a0b33af514e106a91f8b46eba407e252c5549fb25d3` | [official source](https://www.nfl.com/injuries/) |
| depth_chart | ARI | Captured | 200 | 58 | 58 | 293266 | `531dc9e6cb0ad724fc6565abbec0adce2c4df8610859023ce9e7e88066ec13a4` | [official source](https://www.azcardinals.com/team/depth-chart) |
| depth_chart | ATL | Captured | 200 | 59 | 59 | 319915 | `b08df7ace4f57fb8aad7f7c8a63d4db57453a734e2f422ee18581a9238758cf6` | [official source](https://www.atlantafalcons.com/team/depth-chart) |
| depth_chart | BAL | Captured | 200 | 59 | 59 | 298556 | `089c0cdb751ed9b7f22e655f5d81ae79cd4735ab4fe5edc8994f0ff700b28975` | [official source](https://www.baltimoreravens.com/team/depth-chart) |
| depth_chart | BUF | Captured | 200 | 61 | 61 | 301552 | `45b989be581d841195a98cd49dc8bb6eff5746673b6b3714c8206e04e548ef8b` | [official source](https://www.buffalobills.com/team/depth-chart) |
| depth_chart | CAR | Captured | 200 | 57 | 57 | 330638 | `f3b3a316af74a61749488f1e60a22a6a147b5a451edf2fb09b53db6c84517074` | [official source](https://www.panthers.com/team/depth-chart) |
| depth_chart | CHI | Captured | 200 | 59 | 59 | 291599 | `f5ddc3eb76bdc97c7cba80d9c16beb200f77c79f32743063caaa4da237d7fba1` | [official source](https://www.chicagobears.com/team/depth-chart) |
| depth_chart | CIN | Captured | 200 | 60 | 60 | 295813 | `f6754d262ccd3dd00fc7a4a4a5a96b1dc1b80cb2fea3006c8dfff491e82f6fd5` | [official source](https://www.bengals.com/team/depth-chart) |
| depth_chart | CLE | Captured | 200 | 58 | 58 | 297841 | `b15ca9a56421d263eca0a64abb1876cde5a1bd6dfcdae4847382257bcaeace67` | [official source](https://www.clevelandbrowns.com/team/depth-chart) |
| depth_chart | DAL | Captured | 200 | 61 | 61 | 281052 | `ec3836f7779b1797614fd9154f8e70653bf40daab34e250d5417dbb7c6699e75` | [official source](https://www.dallascowboys.com/team/depth-chart) |
| depth_chart | DEN | Captured | 200 | 60 | 60 | 295270 | `0be12cc7ff5dd6c0f58e9bc4332d435f84a40e41fd87b9430b8c0b9ccf30e19c` | [official source](https://www.denverbroncos.com/team/depth-chart) |
| depth_chart | DET | Captured | 200 | 57 | 57 | 292193 | `74cbc7ea41b58400fc1b68812642d22754c2d4a5c11d7bebbfca2c17de619d3f` | [official source](https://www.detroitlions.com/team/depth-chart) |
| depth_chart | GB | Captured | 200 | 57 | 57 | 294131 | `192f5e2cc80c87cb304374de3e3f588ae90e676ee3b446904cb44d93a2942525` | [official source](https://www.packers.com/team/depth-chart) |
| depth_chart | HOU | FAILED — blank and flagged | 200 | 0 | 0 | 490113 | `c80fd81a023d1bb80481740a7b3845d163275ecb6b78480e6284abd734c00d5e` | [official source](https://www.houstontexans.com/team/depth-chart) |
| depth_chart | IND | Captured | 200 | 57 | 57 | 347534 | `789bffbad4f7a196cb50385bfe71db9551c71d8ab1b93a6dcf4807416cf29ab6` | [official source](https://www.colts.com/team/depth-chart) |
| depth_chart | JAX | Captured | 200 | 58 | 58 | 310383 | `bd0480f01295da370e2d23ec2500b91e7a1d8c8e845cc6f7783e86985f1cfd17` | [official source](https://www.jaguars.com/team/depth-chart) |
| depth_chart | KC | Captured | 200 | 60 | 60 | 302338 | `d6e7732bf5a28c14ed1eb3936aea14b1f193507531292b42747bc6c44b8c237d` | [official source](https://www.chiefs.com/team/depth-chart) |
| depth_chart | LV | Captured | 200 | 58 | 58 | 297614 | `f394c61274e0a67cde3769a187113110e7a949ce5fc9e4efcaa84c645ce31a5e` | [official source](https://www.raiders.com/team/depth-chart) |
| depth_chart | LAC | Captured | 200 | 62 | 62 | 360011 | `a895efd92701c571261076679fa64d39c02cc39e8fda4d0cad888d224c2ca440` | [official source](https://www.chargers.com/team/depth-chart) |
| depth_chart | LA | Captured | 200 | 57 | 57 | 293120 | `87020bb20c9df5bd33908f9c730bb811aded96aef2349d39761f3e95a65b82c9` | [official source](https://www.therams.com/team/depth-chart) |
| depth_chart | MIA | Captured | 200 | 56 | 56 | 285560 | `7369ebc447615ec1d58d06836535de7c7a71aa88f3c3b2e4cd2cedeffa9ccd99` | [official source](https://www.miamidolphins.com/team/depth-chart) |
| depth_chart | MIN | Captured | 200 | 59 | 59 | 307899 | `dfe100350a3f54ecfe2d0d29bab78eb67dcb6f1f684f009e756d0ef062a3af57` | [official source](https://www.vikings.com/team/depth-chart) |
| depth_chart | NE | Captured | 200 | 62 | 62 | 356532 | `fdea2dc5b7931224e06ee2f7f57c05657b8e5d4c296a7dbaeb374d1d0ede146a` | [official source](https://www.patriots.com/team/depth-chart) |
| depth_chart | NO | Captured | 200 | 61 | 61 | 509410 | `36ccb38856e09d971761f3132a3ae0d14fa222b6617d20af6807a1f0e38cedee` | [official source](https://www.neworleanssaints.com/team/depth-chart) |
| depth_chart | NYG | Captured | 200 | 60 | 60 | 295831 | `2b5a96fad9306adc759f03c21cc6e83efb15948860a96c1028e1b05b4856e3d0` | [official source](https://www.giants.com/team/depth-chart) |
| depth_chart | NYJ | Captured | 200 | 58 | 58 | 293683 | `44932533e6a3dde8dd65f7737b1664d7264a693b88e72bd99e365b434ca312ba` | [official source](https://www.newyorkjets.com/team/depth-chart) |
| depth_chart | PHI | Captured | 200 | 54 | 54 | 361198 | `b45a4674bec78287f59ceaa1c0bd339540eb5a6fb7c38425d7b33d05e9be5337` | [official source](https://www.philadelphiaeagles.com/team/depth-chart) |
| depth_chart | PIT | Captured | 200 | 59 | 59 | 308994 | `272625f3d82b4b76281fd0e8724cf126b3f80f9b95320bc7d515b703719e832d` | [official source](https://www.steelers.com/team/depth-chart) |
| depth_chart | SF | Captured | 200 | 58 | 58 | 288774 | `ed037d485557888fd5a14ca58657f98ac42b08285ae9a2805bbdfb951fadc3ac` | [official source](https://www.49ers.com/team/depth-chart) |
| depth_chart | SEA | Captured | 200 | 63 | 63 | 311885 | `5ada37d63802a957b74f8edb0ff164e437a8ec80bb132c5416f42fd0e6d33dd3` | [official source](https://www.seahawks.com/team/depth-chart) |
| depth_chart | TB | Captured | 200 | 60 | 60 | 295800 | `38ce4e6e6909cc0e09fd70afc793374f0905bc019911d97a3d148e14413f7612` | [official source](https://www.buccaneers.com/team/depth-chart) |
| depth_chart | TEN | Captured | 200 | 65 | 65 | 303887 | `1dc1d9a2490f20329263707688a1d607f5f29b9c3d8cc4d604e701d63b3da1de` | [official source](https://www.tennesseetitans.com/team/depth-chart) |
| depth_chart | WAS | Captured | 200 | 60 | 60 | 301955 | `52214a81b971d18137aefb60dd553ebc15e7876f3bb8aa47bcfe805ee2b7c3a5` | [official source](https://www.commanders.com/team/depth-chart) |

## Reconciled findings

- The NFL injury page yielded **326 player rows from 28 clubs**. The four club codes not present in that report are **CHI, DEN, PHI, TB**; their absence is not interpreted as injury-free. Source: [NFL.com injury report](https://www.nfl.com/injuries/).
- **31/32** depth-chart fetches parsed successfully; the committed depth dataset has **1833 rows for 31 clubs**. The capture failure(s) remain visible in the table above and on [availability.html](../availability.html).
- The deterministic join produced **909 depth-chart slots**, with status-flag counts `{"FIRST-LISTED DID NOT PRACTICE (no game status posted)": 59, "FIRST-LISTED OUT": 4, "FIRST-LISTED QUESTIONABLE": 3, "unflagged": 843}`. These are official report labels joined to published chart order—not confirmed game-day starters and not a points adjustment.
- **68** injury-report player rows were not joined to a chart slot: `{"club depth chart not machine-readable at capture": 16, "name on injury report not found on the club's published depth chart": 52}`. They remain in the separate unmatched table and are excluded from lineup counts, not guessed into a slot. Source: [NFL.com injury report](https://www.nfl.com/injuries/).
- The site shows injury-report coverage as the number of clubs actually listed, rather than presenting absent clubs as clear. Its current capture log flags each source failure; each published availability table row passed the official-domain source check.

## Verification performed

- `python pipeline/current_snapshot_audit.py`: passed. Validated the `33`-source inventory against configured official URLs, row-level provenance and timestamps, parsed-source counts, per-team depth rows, failure/fallback declaration, summary totals, and the dated-history copies.
- Rebuilt and compared all **3** derived availability CSVs from the committed injury/depth inputs using `depth_status.build`: exact row-for-row match.
- Parsed `availability.html`: **5** captioned tables and **544** table rows; every data row has an official NFL/club reference.
- Full build before PR #39 merged: `make build` passed with 0 verification failures; it checked 24 canonical pages and 1,676 sourced rows, then the 33-page local link checker passed. `make test` — 58 passed; T24-specific checks — 4 passed.
- Re-run after rebasing onto `main` at `d2b5610` (PR #39 merged): `make build` passed with 0 failures and checked 24 canonical pages / 1,681 sourced rows; the 33-page link check passed. `make test` — 58 passed; T24-specific checks — 4 passed.
- Interim combined build after PR #43 merged as `90e9df8`: `make build` passed with 0 failures, checking 26 canonical pages / 2,085 sourced rows and 35 pages for links; `make test` — 86 passed; the T24-specific suite — 5 passed.
- Combined build after PRs #44 and #45 merged as `5fa44db`: `make build` passed with 0 failures, checking 26 canonical pages / 2,085 sourced rows and 35 pages for links; `make test` — 88 passed; the T24-specific suite — 5 passed. Pages deployment run 43527643082 succeeded.
- Latest T24 combined verification after rebasing onto `main` at `9cca4bc` (the upstream addition since `c16c25c` was coordination-only): the audit passed; `make build` passed with 0 failures, checking 27 canonical pages / 2,134 sourced rows and 36 pages for links; `make test` — 107 passed; the T24-specific suite — 5 passed; `py_compile` and `git diff --check` passed. Pages deployments for `c16c25c` and `9cca4bc` succeeded (43528119880 and 43528589107); current `main` Verify run 43528589459 passed.
- Verification history: PR #42's two Verify checks passed (43527870229, 43527864112). The post-merge `main` Verify run 43528121286 on `c16c25c` failed at `Verify pinned inputs and rebuild`; GitHub's job API identifies the failing step, but its log download ended with EOF, so the cause remains unknown. The subsequent `main` Verify run on `9cca4bc` succeeded; no cause is attributed to T24.
- PR #40's pushed `d340ead` head had two passing Verify runs (43528077260 and 43528084771), but it was based on `5fa44db` and is stale. The current local T24 branch is rebased onto `9cca4bc`; the remote PR head still needs a lease-guarded refresh and updated checks before merge.
- GitHub Actions recorded successful availability capture and deployment for the snapshot: [capture run](https://github.com/karagemop466-tech/Korea1/actions/runs/43483547465), [Pages deployment](https://github.com/karagemop466-tech/Korea1/actions/runs/43483664141). Pages API reports public, built, and served from `main:/`.

## Flagged for review and evidence boundaries

- **HOU depth chart — capture/parser failure.** HTTP 200, 490113 response bytes, `parsed 0 rows`; previous snapshot kept: `False`. No depth rows were promoted for this club in the current capture. Review the [official club depth-chart page](https://www.houstontexans.com/team/depth-chart) and [source ledger row on availability.html](../availability.html).
- **Post-snapshot official-source discrepancy (flagged, not rewritten).** The line-by-line comparison in the merged [V1–V3 review](../live-verification.html), generated at `2026-11-13T22:57:59Z`, compares the captured DET Kerby Joseph row (`Full Participation in Practice` / `Out`) with the later official Week 10 page (`Did Not Participate In Practice` / `Out`; [NFL source](https://www.nfl.com/injuries/league/2026/reg10)). That review classifies the practice-status cell as `INCONSISTENT`; the issue is recorded as [IR-2026-11-13-03](../flagged.html). It also records eight player rows present in the later official page but absent from the capture as unresolved, not as proven parser drops ([IR-2026-11-13-04](../flagged.html)). The raw capture HTML is not retained, so this audit cannot reconstruct the official page as served at `2026-11-13T18:32:20Z` or determine the cause of the difference. No historical value was overwritten, and no lineup role or impact was inferred.
- **Response-body limitation.** The scheduled workflow commits parsed CSVs and a manifest with response hashes, not the original HTML bytes. This audit verifies the recorded metadata and row lineage but cannot independently recompute the source-body hashes. A digest is an integrity identifier, not proof that a remote response was complete. GitHub's API showed successful job and step statuses, but the runner log archive could not be retrieved from this sandbox (the log-download request ended with EOF); the linked run is available for manual review.
- **Historical snapshot distinction.** The executive summary's 2026-11-12 hand-checked lineup sample is a separate, narrower evidence set from this scheduled all-club capture. It must not be read as a count for this 2026-11-13 snapshot; a freshness update is logged as a cross-scope request rather than editing another completed task's summary files.
- **No betting inference.** The model does not assign points to absences. A club's depth-chart order is not proof of who will play, and a tracked absence has not passed impact-validation gates. See [decision-board.html](../decision-board.html) and [open-questions.html](../open-questions.html).

## Repository-only build irregularity

A full rebuild on the pre-PR-#39 tree regenerated the archived snapshot manifest with `sha256: null` for `news_register.md`; the original manifest at the snapshot pin likewise lacks a digest. The file hashes to `f57ba2f9447b4f286af912c348871fa9c6b9d266c628ce8126bf8ce051f56527`; the adjacent official injury-report file has SHA-256 `d7c832ec7b32d04563a81584cc978e33f26808a3a427b45697540cb11e5455b4`. At the pinned commit, the ingestion code set missing hashes to null and only refreshed the injury-report file ([pinned pipeline/fetch_injuries.py](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/pipeline/fetch_injuries.py)); the historical source metadata is in the [snapshot manifest](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/data/evidence/nfl_injuries/week10_2026/manifest.json) and [news register](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/data/evidence/nfl_injuries/week10_2026/news_register.md). This is an evidence-manifest defect, not an NFL fact. The incidental pre-fix build diff was restored. The issue was subsequently repaired upstream by [PR #39](https://github.com/karagemop466-tech/Korea1/pull/39), merged as [`d2b5610`](https://github.com/karagemop466-tech/Korea1/commit/d2b56108614c99b10ed62766a5571518bb3612b1): `pipeline/fetch_injuries.py` now hashes each staged file, and the current manifest records the verified `news_register.md` digest. T24 did not implement that out-of-scope repair; this audit remains pinned to the earlier snapshot and does not rewrite its historical manifest.

### Official / primary references

- NFL injury report: <https://www.nfl.com/injuries/>
- Official club depth charts: direct club links in the source ledger above.
- Availability capture source and deterministic join: [`pipeline/fetch_availability.py`](../pipeline/fetch_availability.py), [`pipeline/depth_status.py`](../pipeline/depth_status.py), [workflow](../.github/workflows/availability.yml).
- Rendered row-source and internal-link checks: [`pipeline/verify_site.py`](../pipeline/verify_site.py), [`tests/check_sources.py`](../tests/check_sources.py), [`tests/check_links.py`](../tests/check_links.py).
