PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

# `make build` pins and fetches whatever nflverse/nfldata master is at run time, then rebuilds
# everything. To reproduce a *published* build instead, pin the snapshot recorded in
# data/sources.json:
#     NFDATA_SHA=a270278f3ac4e937295fe6a27814b3c4a2b62645 make build
.PHONY: build data model backtest props requirements summary site audit audit-full verify test serve clean all

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

requirements:
	$(PY) pipeline/render_requirements.py

site:
	$(PY) pipeline/render_site.py
	$(PY) pipeline/render_summary.py

# the audit re-fetches the pinned archive, rebuilds every artefact in a throwaway tree and
# re-derives published table cells; it exits non-zero on any mismatch. `audit-full` adds the
# clean-room rebuild (~90 s).
audit:
	$(PY) pipeline/audit.py

audit-full:
	$(PY) pipeline/audit.py --rebuild

verify:
	$(PY) pipeline/verify_site.py

test:
	$(PY) tests/test_future_lines.py
	$(PY) tests/test_weather_fold.py
	$(PY) tests/test_props_integrity.py
	$(PY) tests/check_links.py
	$(PY) tests/check_sources.py

build: data model backtest props requirements site audit verify
	@echo "build complete — site rendered to the repository root, audit and verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw assets/data
