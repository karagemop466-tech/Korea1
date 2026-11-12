# Suggestions register — site and decision-making improvements

**Purpose:** a dedicated section where suggestions can be reviewed and a best path chosen **before** any change is implemented. No suggestion is implemented without a recorded decision (adopted / under review / rejected) and, where it touches published numbers, a verification pass.

**Status of this register:** proposed — awaiting first review. This document and `suggestions.html` are the same register; the page is the public view.

## How suggestions are handled

1. A suggestion is entered here with ID, description, expected decision impact and source/reference.
2. It moves to **Under review** when a reviewer picks it up.
3. A **Decision** is recorded: adopt, adopt with modification, or reject — with rationale and the source that supports it.
4. Adopted changes are implemented in code, verified (`make build && make test`), and only then published. Rejected or deferred suggestions stay visible with their rationale — nothing is silently dropped.

## Register

| ID | Suggestion | Decision impact | Status | Decision (path chosen) | Reference |
|---|---|---|---|---|---|
| S-01 | Add the official NFL injury report (`nfl.com/injuries`) as a standing decision input before pricing any game; track starter vs replacement (2nd/3rd/4th string) deficiencies on offense and defense. | Changes which games are priced and how injuries are represented in features; directly affects line origination and strategy selection. | Proposed | None yet — see `injuries.html` for the official Week 10 data capture and the depth-chart gap. | https://www.nfl.com/injuries/ |
| S-02 | Make the pre-decision Q&A register (`decisions.html`) a mandatory gate: no strategy reward, no funding decision, no line publication for real money until every open question is answered or explicitly waived with rationale. | Prevents decisions on incomplete evidence; formalizes the current "do not fund" stance. | Proposed | None yet | `decisions.html` |
| S-03 | Publish a cache-busting note after every GitHub Pages deploy (previous deploys showed edge-cache lag on previously published paths; verify on a new path, e.g. `?v=`). | Avoids reviewers validating a stale deployment. | Proposed | None yet — observed in prior integration log IR-13. | https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-custom-publishing-source-for-your-github-pages-site |
| S-04 | Group navigation by category (lines, strategies, validation, correlations, props, injuries, decisions, suggestions, audit, sources) on the landing page so the dashboard is scannable. | Improves decision speed; no change to underlying numbers. | Adopted | Implemented in this change (category-grouped nav on `index.html` and every page). | `index.html` |
| S-05 | Keep one canonical strict-source view; relegate every unverified estimate to labelled research downloads, never blend them into public tables. | Protects the "blank, not filled" evidence rule. | Adopted | Already enforced by `pipeline/verify_site.py`; retained. | `pipeline/verify_site.py` |
| S-06 | Add a fold-change alert: if a re-pinned snapshot moves more than N% of originated lines or changes any gate verdict, block publication until review. | Prevents silent republication of different numbers under the same pin. | Proposed | None yet | `pipeline/fetch_data.py --refresh-pin` |
| S-07 | Record a timestamped quote for every simulated bet (entry time, book, line, price, limits) before any strategy can leave the research library. | G1 requires it; currently no source can supply it, so all strategies stay unverified. | Proposed | None yet — blocked by missing authenticated quotes (IR-REV-06). | `pipeline/validation.py` (G1) |
| S-08 | Extend the injury capture to a weekly snapshot archive so starter→backup transitions (2nd/3rd/4th string) can be studied historically, not just the current week. | Enables deficiency research; currently no historical official depth-chart source is integrated. | Proposed | None yet — see `injuries.html`, "missing information". | https://www.nfl.com/injuries/ |

## Review rule

Someone reviewing this register must choose one path per suggestion — adopt, adopt-with-modification, or reject — record it in the Decision column with a source link, and only then implement. Until a decision is recorded, the suggestion is not acted on.

## Sources

- https://docs.github.com/en/pages — GitHub Pages publishing and custom sources
- https://www.nfl.com/injuries/ — official NFL injury report
- `pipeline/verify_site.py` — fail-closed site verification