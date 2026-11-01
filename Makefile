PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest strategies corr site verify serve clean all check analysis

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

site:
	$(PY) pipeline/render_site.py

verify:
	$(PY) pipeline/verify_site.py

build: data model backtest site verify
	@echo "build complete — published pages written to the repository root, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw docs/data

# The same three checks CI runs. `make check` is the gate before merging.
check:
	$(PY) -m tests.check_links
	$(PY) tests/check_sources.py
	$(PY) pipeline/verify_site.py

# Secondary, independent implementation (analysis/). Renders its own dashboard into build/dashboard/
# for cross-checking; it does not touch the published pages.
analysis:
	$(PY) -m analysis.run_all
