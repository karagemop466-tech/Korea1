PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

# `make build` pins and fetches whatever nflverse/nfldata master is at run time, then rebuilds
# everything. To reproduce a *published* build instead (the numbers on the live site), pin the
# snapshot recorded in data/sources.json:
#     NFDATA_SHA=a270278f3ac4e937295fe6a27814b3c4a2b62645 make build
.PHONY: build data model backtest requirements summary site audit audit-full verify serve clean all

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

requirements:
	$(PY) pipeline/render_requirements.py

summary:
	$(PY) pipeline/render_summary.py

site:
	$(PY) pipeline/render_site.py

# the audit re-fetches the pinned archive, rebuilds every artefact in a throwaway tree and
# re-derives published table cells; it exits non-zero on any mismatch. `audit-full` is the same
# with the clean-room rebuild included.
audit:
	$(PY) pipeline/audit.py

audit-full:
	$(PY) pipeline/audit.py --rebuild

verify:
	$(PY) pipeline/verify_site.py

build: data model backtest requirements site summary audit verify
	@echo "build complete — site at the repository root, audit and site verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw docs/data
