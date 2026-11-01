PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest strategies corr site verify serve clean all

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
	@echo "build complete — site in docs/, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory docs

clean:
	rm -rf data/raw docs/data
