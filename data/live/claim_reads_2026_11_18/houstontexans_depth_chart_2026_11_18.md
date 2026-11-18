# Verbatim excerpt: Houston Texans club depth chart page structure (why the capture parses 0 rows)

- Source: https://www.houstontexans.com/team/depth-chart (title: "Depth Chart | Houston Texans - HoustonTexans.com")
- Retrieved by the page-fetch tool on 2026-11-18 (~04:55 UTC), single chunk.
- Claim under test (2026-11-18 brief): "The Texans publish depth as an image."

## What the page contains, as printed

Heading: `# Depth Chart | Houston Texans - HoustonTexans.com`
Sub-heading: `## Unofficial Depth Chart`
Content between the sub-heading and the next section ("Trending Headlines"): one image and nothing else.

```
## Unofficial Depth Chart

![](https://static.clubs.nfl.com/image/upload/texans/a5or0zowuo36y1txf4ly)

## Trending Headlines
```

- The retrieval contains **no** `<table>`, no Offense/Defense/Special Teams tab and no player-name cell.
  The depth content is the linked image only.
- Consequence for the capture: `data/availability/depth_charts.csv` carries **0 HOU rows**, and
  `data/availability/manifest.json` records `"rows": 0` for `team: HOU`. A zero-row parse is the faithful
  result for this page; it is not a parser defect. The brief's remedy ("the Texans image needs an
  authorized structured source, not transcription by eye") therefore remains open, and nothing here
  transcribes the image.
- Also read on the same page (used nowhere, recorded for completeness): the club's own Week 11 notice
  "How To Watch: Week 11 vs Colts ... at Reliant Stadium on November 19" and the linked club items
  "Houston Texans Transactions (11-17-2026)" and "Week 11 Injury Report | Texans vs Colts".
