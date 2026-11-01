"""Numerical verification of the closed-form formulas used by the project.
Run: python3 scripts/tests/test_math.py
Any failure means a formula in scripts/lib/common.py is wrong and every dependent
number on the site is invalid -> the build must stop.
"""
import math, random, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.common import (american_to_decimal, american_to_prob, prob_to_american,
                        no_vig_proportional, no_vig_shin, margin_from_probs,
                        bivariate_normal_joint, kelly_fraction, deflated_sharpe_ratio,
                        norm_ppf, bh_qvalues, settle_spread, settle_total, settle_ml)

fails = []
def check(name, got, want, tol=1e-6):
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    if not ok:
        fails.append(f"{name}: got {got!r} want {want!r}")
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got!r}")

# 1. odds conversions (round-trip on standard US prices)
check("american_to_decimal(-110)", american_to_decimal(-110), 1.9090909090909092, 1e-12)
check("american_to_decimal(+150)", american_to_decimal(150), 2.5, 1e-12)
check("american_to_prob(-110)", american_to_prob(-110), 0.5238095238095238, 1e-12)
check("prob_to_american(0.5238...)", float(prob_to_american(110/210)), -110.0)

# 2. no-vig: symmetric -110/-110 must give exactly 50/50
p_h, p_a = american_to_prob(-110), american_to_prob(-110)
check("margin(-110/-110)", margin_from_probs(p_h, p_a), 0.04761904761904756, 1e-12)
h, a = no_vig_proportional(p_h, p_a)
check("no_vig proportional sums to 1", h + a, 1.0, 1e-12)
check("no_vig proportional 50/50", h, 0.5, 1e-12)

# 3. Shin de-vig on a lopsided market.
#    Direction check (this is the whole point of Shin): the model attributes the excess
#    margin on longshots to informed trading, so the de-margined UNDERDOG probability is
#    LOWER than the proportional one, while the favourite's is higher.
#    (An earlier version of this file asserted the opposite; that assertion was wrong,
#     the corrected direction was verified by direct computation - see research/02-methodology.md.)
p_h, p_a = american_to_prob(-400), american_to_prob(330)   # home heavy favourite, away dog
hp, ap = no_vig_proportional(p_h, p_a)
hs, as_ = no_vig_shin(p_h, p_a)
check("shin sums to 1", hs + as_, 1.0, 1e-9)
check("shin dog < proportional dog", float(as_ < ap), 1)
check("shin favourite > proportional favourite", float(hs > hp), 1)
check("shin(-110/-110) is exactly 50/50", no_vig_shin(*[american_to_prob(-110)]*2)[0], 0.5, 1e-9)

# 4. Bivariate normal joint probability vs Monte Carlo (Sheppard formula)
rng = random.Random(7)
for rho in (-0.6, -0.2, 0.0, 0.25, 0.62):
    n = 400000
    both = 0
    for _ in range(n):
        z1 = rng.gauss(0, 1)
        z2 = rho * z1 + math.sqrt(1 - rho**2) * rng.gauss(0, 1)
        if z1 > 0 and z2 > 0:
            both += 1
    p_mc = both / n
    p_cf = bivariate_normal_joint(0.5, 0.5, rho)
    ok = abs(p_mc - p_cf) < 0.004
    print(f"{'PASS' if ok else 'FAIL'}  bivariate joint rho={rho}: cf={p_cf:.5f} mc={p_mc:.5f}")
    if not ok: fails.append(f"bivariate rho={rho}")

# 5. Kelly: fair coin at even money -> 0; edge -> positive
check("kelly fair", kelly_fraction(0.5, 2.0), 0.0, 1e-12)
check("kelly 55% at 2.0", kelly_fraction(0.55, 2.0), 0.1, 1e-12)

# 6. normal quantile round-trip
for p in (0.01, 0.025, 0.5, 0.9, 0.975, 0.999):
    z = norm_ppf(p)
    back = 0.5 * math.erfc(-z / math.sqrt(2))
    ok = abs(back - p) < 1e-9
    print(f"{'PASS' if ok else 'FAIL'}  norm_ppf roundtrip p={p}: z={z:.6f}")
    if not ok: fails.append(f"norm_ppf {p}")

# 7. BH q-values: known example (Benjamini-Hochberg 1995 style ordering)
qs = bh_qvalues([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
# hand-computed by the step-up recursion q_(k) = min_{j>=k} (n/j)*p_(j); see test source
exp = [0.01, 0.04, 0.084, 0.084, 0.084, 0.1, 0.074 * 10 / 7, 0.216, 0.216, 0.216]
ok = all(abs(q - e) < 1e-6 for q, e in zip(qs, exp))
print(f"{'PASS' if ok else 'FAIL'}  BH q-values match hand-computed example: {[round(q,6) for q in qs]}")
if not ok: fails.append("bh_qvalues")

# 8. settlement logic
check("spread home -3 win by 7", settle_spread("home", -3.0, 27, 20), 1)
check("spread home -3 win by 3", settle_spread("home", -3.0, 23, 20), 0)
check("spread away +7.5 lose by 7", settle_spread("away", 7.5, 27, 20), 1)
check("total over push", settle_total("over", 47.0, 27, 20), 0)
check("total under 47 with 45", settle_total("under", 47.0, 24, 21), 1)
check("ml away win", settle_ml("away", 20, 27), 1)

# 9. DSR sanity: identical strategy with many trials must deflate
d1 = deflated_sharpe_ratio(0.06, 400, 0, 3, 1, 1.0)
d2 = deflated_sharpe_ratio(0.06, 400, 0, 3, 500, 1.0)
check("DSR decreases with n_trials", float(d2 < d1), 1)

print()
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL MATH CHECKS PASSED")
