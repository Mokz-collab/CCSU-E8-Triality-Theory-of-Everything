# CCSU-MO-NS-EOS-001 — Decision Lock v0.2

**Status:** draft locked for implementation; not confirmatory  
**Purpose:** resolve the six Domain Lock v0.1 decisions before writing the scientific simulator

## Decisions

### 1. Low-density matching

All observers share one pinned low-density prescription, split into physically
distinct regions:

- a pinned BPS-family outer-crust table from the surface to neutron drip;
- one common, thermodynamically consistent inner-crust connector from neutron
  drip to \(0.5\,n_{\mathrm{sat}}\);
- chiral-EFT-spanning polytropes from \(0.5\) to \(1.1\,n_{\mathrm{sat}}\);
- observer-specific high-density charts begin at \(1.1\,n_{\mathrm{sat}}\).

The phrase “BPS through \(0.5\,n_{\mathrm{sat}}\)” is explicitly rejected:
BPS identifies the outer-crust treatment and must not silently name the
inner-crust connector. Pressure, energy density, and baryon chemical potential
must be continuous at smooth matches. Any registered density discontinuity must
be preserved rather than interpolated away. An observer-specific crust is
forbidden because it would turn a nominal chart difference into an untracked
physical difference.

The numerical polytropic range \(\Gamma\in[1.77,3.23]\) is a proposal envelope for implementation review, motivated by low-density chiral-EFT spanning constructions. It is not a posterior constraint.

### 2. Local EOS charts

Each observer receives a distinct proposal coordinate system:

- GW: four-coefficient spectral adiabatic index;
- XRAY: three-segment piecewise polytrope;
- RADIO: monotone log-pressure spline;
- NUCLEAR: speed-of-sound nodes.

The declared ranges generate proposals only. Every accepted EOS must independently pass common matching, stability, causality, maximum-mass, and stable-branch filters. This prevents a positive CCSU result from being produced by giving one observer a narrower prior.

### 3. Synthetic likelihoods

LOW, MEDIUM, and HIGH information levels are fixed. Heavy-tailed Student-\(t_8\) likelihoods are used for GW and XRAY to avoid making the pilot depend on exact Gaussianity. RADIO is Gaussian; NUCLEAR uses a correlated Gaussian log-pressure band.

At the MEDIUM level, no observer may contribute more than 60% of expected information gain. If this balance condition fails in the pilot, the signal grid must be revised and re-registered before confirmatory seeds exist.

### 4. Phase-transition proxy

The minority-evidence truth is called **rapid softening followed by restiffening**, not “detected first-order phase transition.”

Operationally:

\[
c_s^2\le0.08
\]

over at least \(0.40\,n_{\mathrm{sat}}\), beginning between \(1.5\) and \(4.5\,n_{\mathrm{sat}}\), followed within \(1.50\,n_{\mathrm{sat}}\) by

\[
c_s^2\ge0.45.
\]

This is a falsifiable simulation class. It is not claimed to be a unique observational signature of a Maxwell transition.

### 5. Comparator roles

NAIVE_POOL has a mixed, preregistered role:

- diagnostic comparator in P1;
- primary comparator for minority-evidence recall in P3;
- never a raw posterior mixture.

NAIVE_POOL means a prior-harmonized likelihood product expressed in one reference chart. HYBRID vs IND remains the primary P1 contrast.

### 6. Trajectory budget

The development pilot uses 200 trajectories per out-of-grid cell. It cannot set scientific conclusions.

The confirmatory count is chosen mechanically before the seed schedule:

1. at least 90% power for the smallest frozen effect;
2. directional-fraction Monte Carlo standard error at most 0.01;
3. take the larger requirement;
4. round upward to the next 50;
5. enforce 250–1,000 trajectories per cell.

This resolves the budget rule without pretending to know the final count before pilot variance exists.

## Consequence

All six conceptual decisions are resolved. The remaining blockers are
evidential and implementation-specific: pin and license outer-crust and EFT
reference bytes, validate the common inner-crust connector against a unified
EOS, obtain independent review of proposal ranges, cross-validate TOV/Love
solvers, calibrate P1–P4 thresholds out of grid, and derive the final power
budget.

No public freeze or registered scientific trajectory is authorized by v0.2.
