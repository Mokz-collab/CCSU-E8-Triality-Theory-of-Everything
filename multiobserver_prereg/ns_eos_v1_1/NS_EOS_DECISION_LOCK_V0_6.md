# CCSU-MO-NS-EOS-001 — Decision Lock v0.6

**Status:** development lock; not confirmatory  
**Base:** `ns_eos_decisions_v0_5.yaml`

This lock preserves every conceptual and low-density decision in v0.5 and
adds one evidential result: internal TOV/Love cross-implementation agreement
passed for the registered stellar-impact cases.

## New evidence

Two solvers now reproduce the same ten frozen models:

- the radius-based, pressure-limited custom RK4 implementation with state
  \((m,p,y)\);
- the enthalpy-based SciPy DOP853 implementation with state \((r,m,y)\), a
  separate right-hand side, and a separately coded Love-number expression.

All eight outer-crust/χEFT pairings were compared at \(1.4\,M_\odot\), with
additional \(1.0\) and \(2.0\,M_\odot\) edge cases. Maximum relative
differences were \(1.43\times10^{-6}\) in mass, \(2.02\times10^{-6}\) in
radius, \(7.69\times10^{-3}\) in \(k_2\), and \(7.69\times10^{-3}\) in
\(\Lambda\). These pass the preregistered limits of \(10^{-4}\), \(10^{-4}\),
\(10^{-2}\), and \(10^{-2}\), respectively.

The detailed contract, result, and interpretation are:

- `tov_love_cross_validation_contract_v0_1.yaml`;
- `tov_love_cross_validation_results_v0_1.json`;
- `TOV_LOVE_CROSS_VALIDATION_REVIEW_V0_1.md`.

## Consequence

The internal `TOV_and_Love_cross_implementation_agreement` blocker is closed.
The result is not validation by an external software package or independent
group and does not validate the synthetic core as a physical prior.

Three freeze blockers remain:

1. independent review of local-chart parameter ranges;
2. nonconfirmatory pilot calibration of P1–P4 thresholds;
3. a power-derived confirmatory trajectory budget.

No confirmatory trajectory is authorized by v0.6.
