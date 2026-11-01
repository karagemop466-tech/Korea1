# NFL Line Lab

An independent, evidence-first research blueprint for originating NFL game-line probabilities, player props, parlays, and player-prop combinations. It is **not affiliated with or endorsed by the NFL or any sportsbook**, is not a production forecasting or betting system, and publishes no betting recommendations.

➡️ [Open the dashboard](https://karagemop466-tech.github.io/Korea1/)

## Executive summary

The design starts with score-margin and total distributions for game markets, opportunity-first models for player props, and dependence-aware joint outcome models for combinations. Candidate forecasts would be converted to prices only after calibration and exact settlement definitions. Parlay legs are not treated as independent without evidence. Strategies must pass chronological holdouts, probability-score and calibration checks, uncertainty and multiplicity controls, price-aware benchmarks, and replication before they can appear on a leaderboard.

**No actual fair lines, edge/ROI/CLV, forecast scores, strategy rankings, or empirical NFL prop correlations are reported.** The repository has no rights-cleared joined outcome dataset or timestamped executable sportsbook-price archive. NFL season-stat pages do not establish market prices, settlement terms, or betting performance. NFL GSIS describes XML availability by inquiry, and its sample gamebook restricts other use without NFL written permission; no bulk data were ingested or republished. Unknown values remain blank and are identified on the **Flagged for Review** page. Luck cannot be removed; the proposed controls measure forecast skill separately from outcome noise.

## Site map

- [Overview and requirement coverage](index.html)
- [Strategy designs and pricing identities](pages/strategies.html)
- [Validation gates](pages/validation.html)
- [Correlation register](pages/correlation.html)
- [Leaderboard and proposed reward rules](pages/leaderboard.html)
- [Official and methodological source register](pages/sources.html)
- [Flagged for Review](pages/review.html)

## Important repository handoff

`index.md`, `EXECUTIVE_SUMMARY.md`, and `FLAGGED_FOR_REVIEW.md` were added by an earlier merged branch and are retained for provenance. They contain preliminary year-over-year correlation ranges and skill/luck labels that are **not verified by the official NFL pages reviewed in this integration**. Do not treat those estimates as findings; the canonical HTML dashboard keeps empirical fields blank and flags the legacy draft estimates for reconciliation. The Pages workflow uploads only `index.html`, `assets/`, and `pages/`, so the legacy Markdown drafts and internal coordination notes are not included in the published site artifact.

## Verified source families

- [NFL GSIS](https://www.nflgsis.com/Help/About.html) for official game-stat/gamebook scope and access notes; [official sample gamebook](https://www.nflgsis.com/2024/REG/08/59622/Gamebook.pdf) for schema and reuse restriction.
- Official NFL [passing](https://www.nfl.com/stats/player-stats/category/passing/2025/reg/all/passingyards/desc), [rushing](https://www.nfl.com/stats/player-stats/category/rushing/2025/reg/all/rushingyards/desc), [receiving](https://www.nfl.com/stats/player-stats/category/receiving/2025/reg/all/receivingreceptions/desc), and [team scoring](https://www.nfl.com/stats/team-stats/offense/scoring/2025/reg/all) pages, plus the [Next Gen Stats glossary](https://nextgenstats.nfl.com/glossary). These are source references only; no values were ingested.
- [NIST statistical guidance](https://www.itl.nist.gov/div898/handbook/glossary.htm), [scikit-learn scoring documentation](https://scikit-learn.org/stable/modules/model_evaluation.html), and primary publisher records linked from the source register.
- [GitHub Pages publishing-source guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) for the Actions-based static deployment.
- [Singapore GRA guidance on unlawful remote gambling](https://www.gra.gov.sg/harm-minimisation/unlawful-remote-gambling-activities): the project is research-only; this link is a regulatory caution, not legal advice.

## Local verification

This is a dependency-free static site. From the repository root:

```sh
python3 scripts/check_site.py
python3 -m http.server 8000
```

Open the local server in a development browser. The checker validates local page/file links and requires each published HTML data-table row to link to an approved NFL, NIST, GRA, GitHub Docs, or primary publisher domain. It does not guarantee external links remain live or establish data-use rights.

## Publishing

`.github/workflows/pages.yml` validates the site, assembles a clean `site-build/` artifact, and deploys it on pushes to `main`. GitHub Pages must be configured to publish via **GitHub Actions**. Deployment is not considered confirmed until that workflow succeeds and the canonical public pages return HTTP 200.
