# Baltimore QB recheck — 2026-11-20 (task BQ1, session `arena/83a6b711-korea1`)

**Question.** The 2026-11-18 brief (claim C-09, and the identifiers VR-17 / VR-26 / VQ-07 that the brief
quotes) says: "Baltimore still publishes Lamar Jackson and Tyler Huntley at QB after both went on injured
reserve and a replacement was traded in." Is that true on the official pages, and does the repository's
depth and reserve evidence agree with them?

## Answer in one paragraph

- **The depth-chart claim is out of date.** The official Ravens depth chart, read on 2026-11-20, lists
  Jacoby Brissett, Joe Fagnano and Kedon Slovis at QB. It does not list Jackson or Huntley
  (`claims.csv` BQ-01). The committed capture of 2026-11-18 matches it exactly (BQ-02). The repository's
  own `depth_deltas.csv` already records the change: Jackson to Brissett at QB1 and Huntley to Fagnano at
  QB2 between the 2026-11-12 and 2026-11-13 captures.
- **The injured-reserve and trade facts are confirmed by NFL.com news**, not by a transaction row:
  Jackson (right thumb) and Huntley (toe) placed on IR, Huntley out for the season, Brissett acquired on
  a Friday trade (BQ-03 to BQ-06).
- **The reserve list cannot show those moves.** The official November page is a rolling window of the
  newest 25 rows and shows nothing dated before 11/12. Jackson's and Huntley's placements (early
  November) are outside the window. The repository's captures have the same 25-row shape, so the
  committed reserve data is also partial (BQ-07, BQ-08). "Not listed" therefore does not mean "not on IR".
- **The brief's identifiers VR-17, VR-26 and VQ-07 appear only as labels.** They occur in brief copies and
  registers, but no committed file maps them to a URL or a document, so they cannot be resolved to a
  source (BQ-09). An earlier register row (B9) says no such identifier exists anywhere in the repository;
  that is incorrect as a literal statement and is flagged for review.
- **Official text is inconsistent on Jackson's absence length.** The roundup says "at least four games";
  the later Jackson article says "at least six weeks", with a possible nine (BQ-10). Flagged, not reconciled.

## Files

| File | Contents |
|---|---|
| `claims.csv` | One row per claim under test: official URL, quoted text, read basis, repository comparison, verdict, note |
| `excerpts.md` | Verbatim text copied from each official read, with the page title as returned |
| `reserve_page_nov_2026.csv` | The 25 rows of the official November reserve-list page as read, with the page URL on every row |
| `tests/test_ravens_qb_recheck.py` (outside this folder) | Checks the schema, the source domains, the verdict vocabulary, the depth-chart order, the 25-row window, its overlap with the committed capture, and that every committed snapshot is a 25-row-per-month window |

## Method and limits

- Official text was read with the page-fetch tool, because the sandbox shell cannot reach nfl.com or
  baltimoreravens.com. The tool returns no clock time and no HTTP byte hash, so the read times are the
  session date only. This is a transcription, not a byte-level archive.
- Chunks were read in full where the page has two or more; the depth-chart page's chunk 1 (footer
  content) was not read because the tables are fully in chunk 0.
- The October reserve-list page was read only for its last chunk (rows 10/24 and later). Its earlier rows
  were not read, so no statement is made about October entries.
- Nothing here changes a model, a leaderboard, a strategy or a published site page. This folder is
  evidence only. Any site change belongs to the integration session.
- The sources and verdicts were checked against the page text in this folder; no value was inferred.

## Official sources (for manual review)

- https://www.baltimoreravens.com/team/depth-chart
- https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-thursday-nov-5
- https://www.nfl.com/news/ravens-qb-tyler-huntley-out-for-season-turf-toe-injury
- https://www.nfl.com/news/ravens-lamar-jackson-right-thumb-out-6-9-weeks-expects-to-return-this-season
- https://www.nfl.com/transactions/league/reserve-list/2026/11
- https://www.nfl.com/transactions/league/reserve-list/2026/10
