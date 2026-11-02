PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest props site summary verify test serve clean all

all: build

data:
	$(PY) pipeline/fetch_data.py
	$(PY) pipeline/build_datasets.py

model: data
	$(PY) pipeline/models.py

backtest:
	$(PY) pipeline/backtest.py
	$(PY) pipeline/validation.py
	$(PY) pipeline/correlations.py

props:
	$(PY) pipeline/fetch_pbp.py
	$(PY) pipeline/props_model.py

site:
	$(PY) pipeline/render_site.py
	$(PY) pipeline/render_summary.py

verify:
	$(PY) pipeline/verify_site.py

test:
	$(PY) -m pytest tests/test_props_integrity.py -q
	$(PY) tests/check_links.py
	$(PY) tests/check_sources.py

build: data model backtest props site verify
	@echo "build complete — site rendered to the repository root, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw assets/data
