# `analysis/` — superseded prototype (not run, not published)

This package is the **first** implementation of the project, merged at `3453d41` (PR #12). It is kept
for provenance only. **`pipeline/` is authoritative**: it is what `make build` runs and what generates
every number on the published site.

Two facts a reader needs before touching anything here:

1. `analysis/build_games.py`, `analysis/model.py` and `analysis/signals.py` read the raw archive as
   `data/raw/nfldata/data/*.csv`. `pipeline/fetch_data.py` writes `data/raw/*.csv` instead, so those
   modules raise `FileNotFoundError` in a tree built by the current pipeline. Nothing in `pipeline/`,
   `scripts/`, the Makefile or the workflows imports `analysis/`.
2. The published artefacts are `data/processed/*.csv` (built by `pipeline/`), not the `data/derived/`
   frames this package produced. Where the two disagree, the `pipeline/` number is the published one.

The leak test that used to import this package (`tests/test_no_lookahead.py`) was rewritten to exercise
`pipeline/models.py` — the code that actually produces the published lines. The dead import path is
recorded as an irregularity in `COORDINATION.md`.
