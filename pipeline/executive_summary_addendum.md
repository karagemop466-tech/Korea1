# SUPERSEDED — do not publish from this file

This addendum was written for the 2026-11-02 build and is **not wired into any renderer**
(`grep -rn executive_summary_addendum` returns no code reference). Two of its canonical figures are
now wrong: it states a reality-check `p = 0.186` and model/market errors of `10.527 / 10.216`, which
were the pre-refresh values.

From 2026-11-12 the annex paragraph is generated inside `pipeline/render_summary.py` from the current
artefacts, so it cannot drift from the data again. The replication findings themselves are unchanged
and remain available at `lab/` and `research/05-annex-executive-summary.md`.

Kept, not deleted, so the earlier text stays auditable (flagged on `flagged.html` as IR-3E57-04).
