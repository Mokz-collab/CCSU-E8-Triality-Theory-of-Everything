# Targeted cross-chart optimization review v0.1

## Scope

This development-only review evaluates four frozen near-miss problems from
the inverse relation-cell map. Each problem asks whether a second local chart
can reach a registered public-relation cell while remaining inside its
original parameter box and passing the unchanged finite-domain stellar gates
under both registered chiral-EFT members.

The optimization is not a global coverage search. It does not authorize a
pilot or contribute confirmatory evidence.

## Frozen method

- Public relation: the registered 15-coordinate relation vector.
- Relation threshold: paired worst-case normalized loss at or below
  \(\epsilon=0.05\).
- Optimizer: deterministic bounded differential evolution with four
  preregistered seeds and fixed budgets.
- Domain: unchanged, ending at \(6\,n_{\mathrm{sat}}\).
- Physical checks: exact TOV/Love gates, evaluated only after relation
  reachability, under complete N3LO-414 and N3LO-450 trajectories.
- Forbidden operations: parameter-box expansion, clipping, pressure
  extrapolation, stellar-gate changes, and averaging of local parameter
  vectors.

## Results

| Frozen problem | Initial loss | Optimized loss | Relation reachable | Robust stellar pass |
|---|---:|---:|---|---|
| RADIO cell 1 → NUCLEAR | 0.060322 | 0.028244 | yes | yes |
| XRAY cell 34 → GW | 0.061513 | 0.043026 | yes | no |
| GW cell 0 → NUCLEAR | 0.065211 | 0.002904 | yes | yes |
| RADIO cell 2 → NUCLEAR | 0.066290 | 0.044897 | yes | no |

All four problems cross the frozen relation threshold. Two also pass every
stellar gate under both EFT members:

1. RADIO cell 1 is robustly reachable from the NUCLEAR chart.
2. GW cell 0 is robustly reachable from the NUCLEAR chart.

The two remaining problems are informative incompatibilities rather than
optimizer failures:

- XRAY cell 34 becomes reachable from GW in relation space, but the N3LO-450
  trajectory fails the stable \(1.0\)–\(2.2\,M_\odot\) branch and registered
  mass anchors because its finite-domain maximum mass is
  \(2.1725\,M_\odot\).
- RADIO cell 2 becomes reachable from NUCLEAR in relation space, but both EFT
  trajectories fail the stable \(2.2\,M_\odot\) anchor, with maximum masses
  near \(2.16\,M_\odot\).

Every differential-evolution run consumed its fixed generation budget. The
reported optimizer termination therefore says that the numerical convergence
criterion was not reached before the frozen budget ended; it does not negate
the independently evaluated relation and stellar gates.

## Interpretation

The earlier sampled-bank statement, “no cross-chart overlap at the registered
resolution,” is superseded for these targeted cells. Robust cross-chart
overlap exists at \(\epsilon=0.05\), but only as a
domain-, resolution-, target-, and gate-conditioned result. It is not
“absolute public convergence,” global consensus, identity of observers, or
proof that all occupied relation cells are mutually reachable.

The result preserves the CCSU multiobserver semantics: translation is tested
before aggregation, local coordinates remain distinct, provenance is
retained, and failed translations remain first-class outcomes.

## Decision

`TARGETED_OPTIMIZATION_FOUND_ROBUST_CROSS_CHART_OVERLAP`

This closes the development blocker that required at least one demonstrated
cross-chart relation overlap at the frozen resolution. It does not close
sampling completeness, independent parameter-range review, threshold
calibration, or confirmatory power.

## Next registered development step

Freeze explicit transition records for the two robust overlaps, including
direction, target cell, EFT-member provenance, relation loss, and stellar
gate status. Then test translation-cycle holonomy only where the available
transition graph contains a closed cycle. Absence of a cycle must be reported
as non-identifiability, not silently treated as zero holonomy.

