# Integration verification record — 2026-11-18

Session `arena/8a075837-korea1`, applied on top of `origin/main` at `9933bba`
("availability: official snapshot 2026-11-18T04:24Z", which carries PR #75, PR #76, PR #77 and
PR #78). Nothing here repeats the depth-test restructuring or the chart reconciliation already on
`main`.

This is a record of what was checked **offline** on 2026-11-18, what the checks proved, and what
they deliberately did not prove. No live NFL or club page was opened during this pass — the
sandbox has no route to `nfl.com` — so every statement about an official page is inherited from
the dated, committed extract that recorded it, and each such extract is cited with the URL it was
read from. Nothing was inferred, and no dated file was edited to agree with another date.

## 1 · The defect this pass fixes

`main` published a depth-chart verification page reading **115 of 115 slots MATCH, all four clubs
PASS**, beside a snapshot that had just been replaced by the scheduled capture of
`2026-11-18T04:24:05Z`. The two inputs of that verdict had drifted apart:

* `pipeline/live_verify_depth.py` compared the 2026-11-13 official transcription against
  `data/availability/depth_charts.csv`, whose rows are re-numbered by file order; and
* `data/live/depth_slot_verification.csv`, `data/live/depth_verification_summary.csv` and the page
  were not part of the capture commit, so they still described the earlier, reconciled file.

Measured directly, the 2026-11-13 transcription and the `2026-11-18T04:24:05Z` capture agree on
94 of the 115 checked slots and differ on **21** (DET 4, NYG 3, WAS 14, NE 0). The same 21 slots
appear when the two immutable archives `data/availability/history/2026-11-13/depth_charts.csv` and
`data/availability/history/2026-11-18/depth_charts.csv` are compared, and they appear under both a
file-order-based and a slot-anchored re-numbering — so they are chart movement over five days, not
a keying artefact. A "PASS" that hides that movement is worse than no verdict: it is the exact
failure mode this repository's fail-closed rules exist to prevent.

The pass also followed an earlier one of the same kind. PR #77 rebuilt four clubs' rows inside the
`2026-11-17T19:51:56Z` snapshot from the 2026-11-13 transcription while leaving the 11-17
timestamp on them; the per-club row counts then contradicted `data/availability/manifest.json`, and
five tests in `tests/test_current_snapshot_audit.py` errored on `main` until the next scheduled
capture overwrote the file. That capture is why `main`'s data is now consistent again — and why
the rewriting script is removed here: a tool that makes a dated file look like a different date
will do it again on the next run.

## 2 · What changed

| # | Change | Files | Why |
|---|---|---|---|
| 1 | The depth verification compares the 2026-11-13 official transcription only with its immutable same-date archive (`data/availability/history/2026-11-13/depth_charts.csv`, `retrieved_utc 2026-11-13T18:32:20Z`), and publishes `latest_snapshot_utc` with `latest_snapshot_independently_verified: false`. | `pipeline/live_verify_depth.py`, `data/live/depth_verification_summary.json` | A verdict is only meaningful between observations taken at the same time, and the moving snapshot must never be implied to be the verified one. |
| 2 | The gap between the verified date and the published date is published: 21 divergent slots, each with both orders and the club URL, in `data/live/depth_capture_divergence.csv` and as Table 6b on `live-verification.html`, labelled capture movement. | `pipeline/live_verify_depth.py`, `pipeline/render_live.py`, `data/live/depth_capture_divergence.csv`, `live-verification.html` | "Not verified" without the size of the gap is not a disclosure. |
| 3 | Provenance invariants are pinned by tests: the published snapshot's per-club row counts must equal what the manifest recorded, every row must carry that capture's timestamp, and the movement file may only use non-defect vocabulary. | `tests/test_live_verify.py` | This is what a silent "reconciliation" broke; the guard has to live in the suite that CI runs. |
| 4 | `scripts/reconcile_depth_charts.py` is deleted. | `scripts/` | It rewrites a dated capture from an older transcription. Its review value is kept by the divergence report, which is read-only. |
| 5 | The injury comparison now prints both read dates: the published table is the `2026-11-18T04:24:05Z` scheduled capture, the transcription was read `2026-11-13T22:57:59Z`, and a match is published as "this cell has not moved", not "checked today". | `pipeline/live_verify.py`, `pipeline/render_live.py`, `data/live/verification_summary.json` | The same cross-date ambiguity as item 1 sat in Table 1 and Table 3. |
| 6 | `Current status — 2026-11-15` becomes `Decision status snapshot — 2026-11-15`, with the latest availability capture time read from the manifest on every build and an explicit note that the newer capture does not refresh the decision registers. | `pipeline/render_summary.py`, `pipeline/render_site.py`, `EXECUTIVE_SUMMARY.md`, `executive-summary.html` | The block had a hard-coded date while newer captures existed; a reader could take a 11-15 register for a 11-18 re-verification. |
| 7 | `make test` lists every committed test module (24 of 24; verified by enumeration against `tests/test_*.py`). Takeover of the stale PR #70 change. | `Makefile` | A green `make test` that skips a failing suite is how item 1's predecessor reached `main`. |
| 8 | Competitive-display policy (takeover of the stale PR #73 change) is carried and test-pinned: the strategy leaderboard and both competition standings tables withhold `Units staked`, `Mean signal edge`, `ROI` and `Adjusted p`, keep signal qualification separate from PAPER/LIVE status, and show two-sided move-up / stop criteria with current historical values omitted. | `pipeline/session_competition.py`, `pipeline/render_site.py`, `tests/test_brief_2026_11_15.py`, `strategies.html`, `competition.html` | Backtest results must not reach the leaderboard; only a test that reads the rendered table can keep that true. |
| 9 | The finding and the boundary are registered where a reviewer will meet them: check `V-09` and irregularity `IR-8A07-01`. | `pipeline/session_review.py`, `repo-review.html`, `assets/data/verification_log.csv`, `data/integration/irregularities.csv` | "Reviewed, not repaired" is the standing rule for this page. |

## 3 · Checks run on 2026-11-18, with their results

| Check | Result | What it proves, and does not |
|---|---|---|
| `make liveverify` — parser control | `PARSER_FAITHFUL`: 254/254 archive rows, 0 of 1,016 cells differ | The published parser reproduces the retained official transcript. It is not a re-read of the live page. |
| `make liveverify` — injury fields | 98 official rows vs 347 published rows; 392 graded fields: MATCH 392, confirmed defects 0, unresolved 0, drift-possible 0, no-basis 0, out of scope 249; all eight sampled clubs PASS | The 2026-11-13 transcription is faithful to the 2026-11-13 official page for the four week-10 matchups. Source: <https://www.nfl.com/injuries/league/2026/reg10> |
| `make liveverify` — internal consistency | 347 rows / 28 clubs; 4 contradictions (`unavailable_but_full_practice`: JAX B.J. Green II; CIN Jalen Davis, Andrei Iosivas, Brian Parker II); 0 vocabulary errors; 0 duplicates | Those four rows are faithful transcriptions of pairings that are themselves contradictory on the official page (F-29a); they are not repaired here. |
| `make liveverify` — depth charts, same date | 115 slots / 239 players: MATCH 115, MISMATCH 0, MISSING 0, EXTRA 0; DET, NE, NYG, WAS all PASS; 2 of 4 club charts are labelled *unofficial* by the club | Same-date source faithfulness for four clubs — a sample, not a census. Sources: <https://www.commanders.com/team/depth-chart>, <https://www.giants.com/team/depth-chart>, <https://www.detroitlions.com/team/depth-chart>, <https://www.patriots.com/team/depth-chart> |
| Same check against the newest capture | 21 of 115 slots differ (DET 4, NYG 3, WAS 14); 0 missing, 0 extra | Captured movement between 2026-11-13 and 2026-11-18. It is published as movement; it is neither a parser defect nor a verified current chart. |
| `make liveverify` — lineup claims | 59 claims: 41 CONFIRMED, 17 STALE, 0 CONTRADICTED, 1 OUT_OF_SCOPE, 0 quote-not-found; 107 of 347 player values changed between the 2026-11-12 and 2026-11-13 official captures | Staleness, not fabrication — and the reason every status carries its capture time. |
| `make test` | **275 passed, 1 skipped** across 24 modules | The combined tree is self-consistent, including the restored dating rules and the new provenance guards. |
| `make build` | **0 failing checks**; 44 canonical pages / 5,581 rows pass the strict official/primary reference check; 53 pages checked for links, anchors and assets, all resolve, no external dependencies | Every published row still carries an official or primary reference; nothing loads from a CDN. |
| Rebuild idempotence | A second `make build` left the working tree byte-identical | The committed artefacts are the build output, not hand-edited variants — the property that item 1 violated. |

## 4 · What is *not* verified, stated plainly

* The current availability capture (`2026-11-18T04:24:05Z`, 1 source error: HOU returns HTTP 200
  with the chart published as an image, 0 rows parsed) has **no time-matched official extract**, so
  its depth rows are published but not independently verified. The 21 moved slots are the concrete
  re-read list.
* Depth-chart order is an ordering, not a starting role. No Game Book starter list, inactives list
  or snap count was read in this pass, so expected-versus-played tracking is unchanged by it.
* Gate G1 (authenticated, timestamped executable quote provenance) fails for all 18 candidates:
  `price_snapshots.csv` reports opening verified 0 and closing verified 0. No live stake, no
  reward, no paper-to-live promotion.
* Decision state is unchanged and fail-closed: 18 strategies, 0 VALIDATED, 18 PAPER / 0 LIVE in
  the demotion register, and the forward ledger holds 4 OFFICIAL-settled with 61 PROVISIONAL
  tickets still open. Backtest values stay off the competitive tables by policy.
* Parlay and player-prop priceability remains UNVERIFIED — no executable joint price and no
  settlement-rule review. Singles stay first; parlays and props stay gated on joint-probability
  and settlement evidence that does not exist yet.
* Raw row data stays private pending the terms review; only aggregates, verdicts and per-row
  official references are published.

## 5 · Next steps that would change this record

1. A scheduled capture paired with a same-date official club-chart read — the only legitimate way
   to close the 21-slot gap. `data/live/depth_capture_divergence.csv` is the work list; the fix is
   never an edit to either file.
2. An authenticated, timestamped bookmaker quote archive, which is all that can clear G1.
3. Houston's image-only chart page, and the two club charts that call themselves unofficial: until
   these are settled, replacement depth for those clubs is reported as unverified, not inferred.
4. A live run of `reserve-list.yml` (F-37) and resolution of the Whyle reserve-list versus
   injury-report conflict (F-34).
5. The owner decisions still open: F-38 (the leaderboard display policy, now implemented and
   test-pinned, awaiting ratification) and F-41 (the frozen G3 power target against a 227–414-week
   archive).
