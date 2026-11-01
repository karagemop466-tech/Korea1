#!/usr/bin/env bash
# Full reproducible pipeline. Run from the repository root.
#   bash scripts/run_all.sh
# Order matters: the site is built from data/*.json, then verified, then rebuilt so that the
# verification table printed on the site matches the final state of the repository.
set -euo pipefail
python3 scripts/tests/test_math.py
python3 scripts/00_ingest.py
python3 scripts/02_line_model.py
python3 scripts/03_strategies.py
python3 scripts/04_correlations.py
python3 scripts/05_props.py
python3 scripts/06_validation.py
python3 scripts/08_leaderboard.py
python3 scripts/07_build_site.py
python3 scripts/99_verify.py
python3 scripts/98_linkcheck.py
python3 scripts/07_build_site.py
python3 scripts/99_verify.py
python3 scripts/98_linkcheck.py
echo "PIPELINE OK"
