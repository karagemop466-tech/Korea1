PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
PY := python3
else
PY := .venv/bin/python
endif

.PHONY: build data model backtest props injuries review liveverify reviewall site verify test annex serve clean all forward-capture

all: build

data:
	$(PY) pipeline/fetch_data.py
	$(PY) pipeline/build_datasets.py
	$(PY) pipeline/price_snapshot.py   # P1 (arena/a6bbbf24-korea1): opening/closing numbers per originated market

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

# Independent official-source re-verification (session arena/917fe36e-korea1).
# Reads the committed official extracts under data/live/ and the pinned snapshot;
# no network access, so this is safe in CI. Writes only data/live/**.
liveverify:
	$(PY) pipeline/live_verify.py
	$(PY) pipeline/live_verify_depth.py
	$(PY) pipeline/lineup_claims.py

# Consolidated review surface across the four suggestion registers.
reviewall: liveverify
	$(PY) pipeline/review_consolidated.py

site: injuries review reviewall
	$(PY) data/review/_author.py
	# CS4/CS6 (arena/db6cd525-korea1): official spot-check rows and flagged rows F-42 onward.
	# Reads committed captures and data/live/spotcheck_2026_11_18/ only (no network).
	$(PY) pipeline/session_20261118.py
	# CR1 (arena/f84bc1d7-korea1): the standing-request register (one row per request item,
	# with the gate that blocks it and the number that would clear it). Reads only committed
	# files, including the CR2 live spot-check excerpts (no network).
	$(PY) pipeline/request_register.py
	$(PY) pipeline/depth_status.py
	$(PY) pipeline/lineup_deficiencies.py
	$(PY) pipeline/decision_readiness.py
	# T40 (arena/84e42ecc-korea1): the referent register must be part of the build.
	# It reads the committed probe output only (no network), so it is reproducible.
	# Without this line the page went stale while verify_site.py counted its rows,
	# which is exactly the drift tests/check_rebuild.py caught on PR #50.
	$(PY) pipeline/render_referents.py
	# X1-X4 (session arena/132e7ca2-korea1), additive: repository review, merged
	# suggestion / question registers, competition page. Every existing recipe step
	# is unchanged and still runs first.
	$(PY) pipeline/session_review.py
	$(PY) pipeline/session_decide.py
	$(PY) pipeline/session_competition.py
	# T43 (session arena/6b1f0c9a-korea1): the nine requirement pages. All read committed data
	# only (no network), so `make build` stays reproducible in CI.
	$(PY) pipeline/price_annex.py
	$(PY) pipeline/results_feed.py
	$(PY) pipeline/origination_order.py
	$(PY) pipeline/signal_staking.py
	$(PY) pipeline/replacement_depth.py
	$(PY) pipeline/corr_official.py
	$(PY) pipeline/demotion_rules.py
	$(PY) pipeline/session_20261114.py
	# CB1/CB6/CB8 (arena/c79b2684-korea1, 2026-11-15): brief tracker, mind-changers, flagged rows.
	# Must run before render_site.py, which reads the CSVs it writes.
	$(PY) pipeline/session_20261115.py
	$(PY) pipeline/render_site.py
	# U3 (arena/fcba7eb5-korea1): price-snapshot store, one row per originated market. Reads committed
	# originated lines and the forward cards only; no network.
	$(PY) pipeline/price_snapshots.py
	# BF1/BF2 (arena/bfcd9879-korea1): archive-populated price store + its page,
	# and the full-history tiered results feed (published as section 5 of T43's
	# results-feed.html). Read committed files only; no network.
	$(PY) pipeline/price_archive.py
	$(PY) pipeline/render_price_archive.py
	$(PY) pipeline/results_feed_history.py
	$(PY) pipeline/render_forward.py  # T41 (arena/8a322b62-korea1): publishes forward.html from data/forward/
	$(PY) pipeline/render_review.py
	$(PY) pipeline/render_summary.py
	$(PY) pipeline/render_readiness.py
	$(PY) pipeline/render_annex.py

# T40 (arena/84e42ecc-korea1): resolve every external URL printed on the site.
# Needs outbound network access to NFL/club/publisher domains, so `make build` does NOT
# run it - the nightly .github/workflows/referent-audit.yml does, on a GitHub-hosted runner,
# and commits the result.  Run it here only to regenerate referents.html from a committed
# probe, or to re-probe from a shell that has egress.
referents:
	$(PY) scripts/referent_probe.py
	$(PY) pipeline/render_referents.py

referent-render:
	$(PY) pipeline/render_referents.py

verify:
	$(PY) pipeline/verify_site.py
	$(PY) tests/check_sources.py
	$(PY) tests/check_links.py

test:
	$(PY) -m pytest -q tests/test_integration.py tests/test_no_lookahead.py tests/test_weather_fold.py tests/test_future_lines.py tests/test_props_integrity.py tests/test_decisions.py tests/test_review_registers.py tests/test_availability_tracker.py tests/test_governance_and_lineups.py tests/test_live_verify.py tests/test_review_consolidated.py tests/test_forward_settlement.py tests/test_evidence_integrity.py tests/test_forward_capture.py tests/test_demotion_gate.py tests/test_demotion_register.py tests/test_price_snapshots.py tests/test_brief_2026_11_14.py tests/test_origination_order.py tests/test_reserve_list.py tests/test_control_baseline.py tests/test_brief_2026_11_15.py tests/test_gamebooks.py tests/test_request_register.py tests/test_reconcile_depth_charts.py

# Forward-ledger automation. Cannot run in this build sandbox (nfl.com unreachable from the
# shell); .github/workflows/forward-ledger.yml runs it on a GitHub-hosted runner. It archives
# official pages and writes data/forward/official_candidates.csv for review -- it never writes
# data/forward/official_results.csv.
forward-capture:
	$(PY) pipeline/forward_fetch_official.py
	$(PY) pipeline/forward_grade.py
	$(PY) pipeline/render_forward.py

annex:
	bash scripts/run_all.sh
	$(PY) pipeline/render_annex.py

build: data model backtest props injuries site verify
	@echo "build complete — site in repository root/, verification passed"

serve: build
	$(PY) -m http.server 8000 --bind 0.0.0.0 --directory .

clean:
	rm -rf data/raw
