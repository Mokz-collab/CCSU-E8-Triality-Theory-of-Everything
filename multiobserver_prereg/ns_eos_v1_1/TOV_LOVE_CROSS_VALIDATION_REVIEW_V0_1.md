# CCSU-MO-NS-EOS-001 — TOV/Love cross-validation review v0.1

**Status:** internal independent-formulation agreement passed  
**Scientific use:** development only; no confirmatory authorization

## Question

Can the registered stellar models be reproduced when the TOV and quadrupolar
Love equations are integrated with a different independent variable, state
layout, right-hand side, integrator, and Love-number implementation?

## Frozen comparison

Implementation A is the existing radius-based, pressure-limited custom RK4
solver with state \((m,p,y)\). Implementation B uses relativistic enthalpy as
the independent variable, state \((r,m,y)\), an independently coded right-hand
side and Love-number expression, and SciPy DOP853.

The comparison uses the same pinned low-density EOS bytes and the same shared
synthetic constant-sound-speed core. It covers all eight outer-crust/χEFT
pairings at \(1.4\,M_\odot\), plus registered edge cases at \(1.0\) and
\(2.0\,M_\odot\). Tolerances were set before this result:

| Quantity | Maximum allowed relative difference |
|---|---:|
| Mass | \(10^{-4}\) |
| Radius | \(10^{-4}\) |
| \(k_2\) | \(10^{-2}\) |
| \(\Lambda\) | \(10^{-2}\) |

## Result

All 10 registered cases pass.

| Quantity | Maximum observed relative difference |
|---|---:|
| Mass | \(1.4263\times10^{-6}\) |
| Radius | \(2.0211\times10^{-6}\) |
| \(k_2\) | \(7.6938\times10^{-3}\) |
| \(\Lambda\) | \(7.6943\times10^{-3}\) |

The larger tidal differences, compared with mass and radius, are consistent
with the greater surface sensitivity of the Love response. They remain below
the predeclared 1% numerical agreement limit. The radial implementation also
reproduces every source stellar-impact record exactly.

## What this closes

The development blocker
`TOV_and_Love_cross_implementation_agreement` is closed for the registered
piecewise-linear EOS and synthetic-core diagnostic. This is stronger than
step-halving within one solver because the two implementations use distinct
integration coordinates and numerical algorithms.

## What this does not close

This is not validation against a separately maintained external package or an
independent research group. It does not validate the synthetic core as a
physical prior, observational constraints, local-chart parameter ranges, or
the P1–P4 inferential thresholds. It therefore cannot authorize confirmatory
trajectories.

The remaining freeze blockers are:

1. independent review of local-chart parameter ranges;
2. nonconfirmatory pilot calibration of P1–P4 thresholds;
3. a power-derived confirmatory trajectory budget.
