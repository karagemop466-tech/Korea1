PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest props strategies corr site verify test annex serve clean all

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

site:
	$(PY) data/review/_author.py
	$(PY) pipeline/depth_status.py
	$(PY) pipeline/lineup_deficiencies.py
	$(PY) pipeline/decision_readiness.py
	$(PY) pipeline/render_site.py
	$(PY) pipeline/render_review.py
	$(PY) pipeline/render_summary.py
	$(PY) pipeline/render_readiness.py
	$(PY) pipeline/render_annex.py

verify:
	$(PY) pipeline/verify_site.py
	$(PY) tests/check_sources.py
	$(PY) tests/check_links.py

test:
	$(PY) -m pytest -q tests/test_integration.py tests/test_no_lookahead.py tests/test_weather_fold.py tests/test_future_lines.py tests/test_props_integrity.py tests/test_decisions.py tests/test_review_registers.py tests/test_availability_tracker.py tests/test_governance_and_lineups.py

annex:
	bash scripts/run_all.sh
	$(PY) pipeline/render_annex.py

build: data model backtest props site verify
	@echo "build complete — site in repository root/, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw
