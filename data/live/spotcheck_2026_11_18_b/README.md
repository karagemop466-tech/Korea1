# Live official transcription — 2026-11-18T04:52Z read (session `arena/ba09384a-korea1`)

These files hold the cells of four official pages as they were printed when the page-fetch tool
read them on **2026-11-18 at about 04:52 UTC**. They are transcriptions, not captures of raw
bytes: the build sandbox shell cannot open `www.nfl.com` (TLS refused), so the pages are read with
the page-fetch tool and the relevant table cells are copied here verbatim. A comparison against
`data/availability/**` therefore proves that the committed capture and this read agree; it does
prove nothing about bytes that were never transcribed.

Rules applied while transcribing:

* A cell is copied exactly as printed, including an empty cell (printed as nothing).
* A row is **omitted**, never guessed, when the page delivered it only in part. One row is
  affected: **KC Patrick Mahomes** was cut mid-cell by the reader's chunk boundary, so Kansas City
  is compared on 12 of its 13 rows and the omitted row is named in the page.
* Nothing is normalised. Where the league prints a club code that differs from the code the
  capture uses (`AZ` on the page vs `ARI` in the capture), the difference is recorded as a finding,
  not silently mapped in the transcription.

| File | Official page | Rows | Read at |
|---|---|---|---|
| `nfl_injuries_week10_WAS_NYG_NE_DET.md` | <https://www.nfl.com/injuries/> | 44 | 2026-11-18 ~04:52Z |
| `nfl_injuries_week10_ATL_MIN_GB_KC.md` | <https://www.nfl.com/injuries/> | 53 | 2026-11-18 ~04:52Z |
| `commanders_depth_chart.md` | <https://www.commanders.com/team/depth-chart> | 29 | 2026-11-18 ~04:53Z |
| `nfl_reserve_list_2026_11.md` | <https://www.nfl.com/transactions/league/reserve-list/2026/11> | 25 | 2026-11-18 ~04:55Z |
| `nfl_game_centre_KC_at_ATL.md` | <https://www.nfl.com/games/chiefs-at-falcons-2026-reg-10> | 1 | 2026-11-18 ~04:56Z |
