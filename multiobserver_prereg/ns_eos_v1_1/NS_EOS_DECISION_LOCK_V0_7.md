# CCSU-MO-NS-EOS-001 — Decision Lock v0.7

**Status:** development lock; not confirmatory  
**Base:** `ns_eos_decisions_v0_6.yaml`

This lock preserves v0.6 and records implementation of the four distinct
local EOS charts.

## Implemented

- GW: spectral adiabatic index;
- XRAY: continuous piecewise polytrope;
- RADIO: monotone log-pressure PCHIP;
- NUCLEAR: speed-of-sound nodes.

All generators begin at the pinned \(1.1\,n_{\rm sat}\) χEFT endpoint and
produce pressure, energy density, chemical potential, and \(c_s^2\) through
thermodynamically consistent evolution to \(6\,n_{\rm sat}\).

The eight registered cases — four charts applied to both pinned MUSES
reference members — pass finite-value, exact matching, monotonicity,
thermodynamic-identity, stability, and causality checks. Extreme but
in-range proposals are not guaranteed to pass: they are rejected by the
common physical filters and are never clipped.

## Preserved CCSU distinction

Local parameters remain observer-specific coordinates. They are not placed
in a common vector space and cannot be averaged. Only translated physical
relations may enter the Atlas.

## Still open

The implementation result does not approve the parameter ranges. The review
packet explicitly requests an independent assessment of dead proposal
regions, unequal accepted volumes, smooth-chart bias against transitions,
the \(6\,n_{\rm sat}\) endpoint, and possible pQCD conditions.

Maximum-mass, stable-branch, and local-to-public translation gates are the
next implementation layer. The three freeze blockers remain unchanged:

1. independent review of local-chart parameter ranges;
2. pilot calibration of P1–P4;
3. power-derived confirmatory budget.

No confirmatory trajectory is authorized by v0.7.
