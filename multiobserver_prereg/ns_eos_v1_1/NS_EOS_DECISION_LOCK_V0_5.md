# CCSU-MO-NS-EOS-001 — Decision Lock v0.5

**Status:** development lock; not confirmatory  
**Purpose:** preserve the six Domain Lock decisions while registering final
low-density pairings and their internal stellar-impact test

## Decisions

### 1. Low-density matching

All observers share one pinned low-density prescription, split into physically
distinct regions:

- a pinned four-table outer-crust ensemble, constructed with the BPS
  formalism, from the surface to each model's neutron-drip endpoint;
- one common, reference-shaped and thermodynamically exact inner-crust
  connector from neutron drip to \(0.5\,n_{\mathrm{sat}}\);
- pinned MUSES v1.0.1 N3LO-414 and N3LO-450 reference members from
  \(0.5\) to \(1.1\,n_{\mathrm{sat}}\);
- observer-specific high-density charts begin at \(1.1\,n_{\mathrm{sat}}\).

The phrase “BPS through \(0.5\,n_{\mathrm{sat}}\)” is explicitly rejected:
BPS identifies the outer-crust treatment and must not silently name the
inner-crust connector. Pressure, energy density, and baryon chemical potential
must be continuous at smooth matches. Any registered density discontinuity must
be preserved rather than interpolated away. An observer-specific crust is
forbidden because it would turn a nominal chart difference into an untracked
physical difference.

The pinned outer-crust models are DD-ME2, DD-PC1, DD-PCX, and ELMA from
Koliogiannis & Paar (2026), at upstream commit
`d569b24d072d6746943ef6d107dabd6458d9730b`, licensed CC BY 4.0. They form a
balanced shared nuisance factor: every arm in a paired trajectory receives the
same outer-crust model. Observer-conditioned selection and averaging the four
tables are both forbidden.

The MUSES reference members are generated at zero temperature in
charge-neutral beta equilibrium with electrons and muons. They form a balanced
shared nuisance factor: every arm in a trajectory uses the same complete
member. Pointwise envelope sampling, observer-conditioned selection, and
coefficient or table averaging are forbidden.

The two members are an interaction-reference envelope, not a formal
order-by-order χEFT truncation band. No probabilistic coverage is attached to
their span. The earlier \(\Gamma\in[1.77,3.23]\) implementation proposal is
therefore retired from the active low-density contract rather than being
silently combined with the MUSES members.

The v0.3 normalized-exponential connector is retained as a rejected baseline.
It closed both endpoints but failed registered local-shape thresholds against
the IOPB calibration table and the held-out G3 unified EOS. In the primary
holdout, its density-weighted RMS log-pressure error was \(0.165\), above the
frozen development limit \(0.08\), and its maximum log-pressure error was
\(0.588\), above \(0.15\).

The v0.4 decision adopts, for continued development only, a positive
three-component derivative template for normalized baryon chemical potential.
The component exponents are \((-40,0,40)\); their fixed non-negative masses
are \((0.1019714,0.8427348,0.0552938)\). The masses were fitted only to the
licensed IOPB unified EOS. A single common exponential tilt is then solved
deterministically from the two endpoint pressures; it is not sampled and
cannot vary by observer.

G3 was not used in the fit and is the primary holdout. The candidate passed
all local thermodynamic thresholds there: density-weighted RMS log-pressure
error \(0.0319\), maximum \(0.0612\), normalized chemical-potential-span RMS
\(0.00618\), and density-weighted \(c_s^2\) RMS error \(9.37\times10^{-4}\).
FSUGarnet also passed its predeclared advisory thresholds, but its coarse
upper-density gap prevents it from becoming a primary gate. These three
tables are pinned to upstream commit
`80eadb3820c337765659bd204719cedba2221649` under GPL-3.0-only.

The template is a shared modelling rule, not a probability distribution.
It has no coverage level, no observer-specific parameter, and no permission
to select table points or weights by observer.

All eight allowed outer-crust/χEFT endpoint combinations pass the exact
identity, monotonicity, stability, and causality checks. The source
chemical-potential values at neutron drip are rounded; before joining, only
\(\mu\) is projected to \((\varepsilon+P)/n\), preserving the tabulated
\(n,P,\varepsilon,c_s^2\). The original relative residual must be at most
\(10^{-6}\); observed values range from \(6.25\times10^{-8}\) to
\(2.45\times10^{-7}\). A larger correction is rejected.

The radius/tidal sensitivity test uses one common constant-sound-speed
extension with \(c_s^2=0.6\) above the last MUSES row. This core is a synthetic
diagnostic, not a physical high-density prior. Across \(1.0,1.4,2.0\,M_\odot\),
the connector replacement changes radius by at most \(0.001405\) km and
\(\Lambda\) by at most 1.929%. The four outer-crust choices produce at most
\(0.004395\) km radius spread and \(5.44\times10^{-4}\) fractional
\(\Lambda\) spread. Step halving passes the registered numerical tolerances.

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

All six conceptual decisions are resolved. The low-density provenance,
calibration/holdout shape test, eight final pairings, and internal
radius/tidal sensitivity test are closed for development. The remaining
blockers are evidential and implementation-specific: obtain independent review
of proposal ranges, cross-validate TOV/Love solvers, calibrate P1–P4 thresholds
out of grid, and derive the final power budget.

No public confirmatory freeze or registered scientific trajectory is
authorized by v0.5.
