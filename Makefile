PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest props injuries review site verify test annex serve clean all

all: build

data:
	$(PY) pipeline/fetch_data.py
	$(PY) pipeline/build_datasets.py

model: data
	$(PY) pipeline/models.py

props:
	$(PY) pipeline/fetch_pbp.py
	$(PY) pipeline/props_model.py

backtest:
	$(PY) pipeline/backtest.py
	$(PY) pipeline/validation.py
	$(PY) pipeline/correlations.py

# Injury / availability tracking (session arena/774867ed-korea1, T14/T15).
# The official NFL injury snapshot is committed verbatim under data/evidence/
# (data/raw/ is gitignored); fetch_injuries.py parses it, injuries.py builds the
# availability / lineup-deficiency tables, build_review.py validates the
# suggestion and open-question registers.  Additive: these tables do not collide
# with the availability tracker already published by the merged sessions.
injuries: data
	$(PY) pipeline/fetch_injuries.py
	$(PY) pipeline/injuries.py

review: injuries
	$(PY) pipeline/build_review.py

site: injuries review
	$(PY) data/review/_author.py
	$(PY) pipeline/depth_status.py
	$(PY) pipeline/lineup_deficiencies.py
	$(PY) pipeline/decision_readiness.py
	$(PY) pipeline/render_site.py
	$(PY) pipeline/render_review.py
# 2026-11-13 (arena/534e771f-korea1, T30-T32): verified capture, 1st-4th string deficiency
# join, forward-ledger grading, decision hub and improvements register. build_hub must run
# after render_review (it indexes the registers render_review writes) and render_summary must
# run after all three, because it quotes their result files instead of retyping them.
	$(PY) pipeline/gameday_deficiency.py
	$(PY) pipeline/forward_settle.py
	$(PY) pipeline/build_hub.py
	$(PY) pipeline/render_gameday.py
	$(PY) pipeline/render_hub.py
	$(PY) pipeline/render_improvements.py
	$(PY) pipeline/official_review.py
	$(PY) pipeline/render_summary.py
	$(PY) pipeline/render_readiness.py
	$(PY) pipeline/render_annex.py

verify:
	$(PY) pipeline/verify_site.py
	$(PY) tests/check_sources.py
	$(PY) tests/check_links.py

test:
	$(PY) -m pytest -q tests/test_integration.py tests/test_no_lookahead.py tests/test_weather_fold.py tests/test_future_lines.py tests/test_props_integrity.py tests/test_decisions.py tests/test_review_registers.py tests/test_availability_tracker.py tests/test_governance_and_lineups.py tests/test_hub.py

annex:
	bash scripts/run_all.sh
	$(PY) pipeline/render_annex.py

build: data model backtest props injuries site verify
	@echo "build complete — site in repository root/, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw
