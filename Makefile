PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest props injuries site verify test audit annex serve clean all

all: build

data:
	$(PY) pipeline/fetch_data.py
	$(PY) pipeline/build_datasets.py

model: data
	$(PY) pipeline/models.py

props:
	$(PY) pipeline/fetch_pbp.py
	$(PY) pipeline/props_model.py

injuries:
	$(PY) pipeline/injuries.py

backtest:
	$(PY) pipeline/backtest.py
	$(PY) pipeline/validation.py
	$(PY) pipeline/correlations.py

site:
	$(PY) pipeline/render_requirements.py
	$(PY) pipeline/render_summary.py
	$(PY) pipeline/render_site.py
	$(PY) pipeline/render_annex.py

verify:
	$(PY) pipeline/verify_site.py
	$(PY) tests/check_sources.py
	$(PY) tests/check_links.py

audit:
	$(PY) pipeline/audit.py

test:
	$(PY) -m pytest -q tests/test_integration.py tests/test_no_lookahead.py tests/test_weather_fold.py tests/test_future_lines.py tests/test_props_integrity.py tests/test_injuries.py

annex:
	bash scripts/run_all.sh
	$(PY) pipeline/render_annex.py

build: data model backtest props injuries site verify
	@echo "build complete — site in repository root/, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw
