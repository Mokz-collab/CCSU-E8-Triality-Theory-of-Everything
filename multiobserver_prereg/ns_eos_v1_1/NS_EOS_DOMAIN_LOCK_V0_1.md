# CCSU-MO-NS-EOS-001 — Domain Lock v0.1

**Status:** draft, not frozen  
**Study class:** simulation-first domain validation  
**Canonical basis:** CCSU Multiobserver Canonical Correction v1.1  
**Purpose:** define the scientific niche before implementing or calibrating the simulator

## 1. Domain tuple

\[
\mathcal D_{\mathrm{NS}}=
(\text{nuclear multimessenger astronomy},
\text{dense-matter relation inference},
\text{cold nonrotating neutron stars},
\{\mathrm{GW,XRAY,RADIO,NUCLEAR}\},
\text{relational EOS Atlas},
\text{TOV/Love/likelihood translations},
\{p(\varepsilon),M\!-\!R,\Lambda(M),M_{\max}\}).
\]

The target is not a universally preferred equation-of-state parameterization. It is the compatibility of relations that different scientific pipelines can translate and test.

## 2. Why simulation first

Joint neutron-star EOS studies already combine NICER mass–radius information, gravitational-wave tidal information, pulsar masses, and nuclear theory. They also show that the result depends materially on pulse-profile choices, priors, and EOS parameterization. A simulation-first phase gives a known truth and allows failures to be assigned to translation, aggregation, inference, or control rather than to unresolved observational systematics.

Primary technical anchors:

- Joint NICER and LIGO/Virgo EOS inference: https://arxiv.org/abs/1912.11031
- GW170817 radii and EOS constraints: https://arxiv.org/abs/1805.11581
- Nuclear multimessenger framework with NICER J0740+6620: https://arxiv.org/abs/2105.08688
- Current NICER systematic sensitivity: https://arxiv.org/html/2507.12540v1
- Modular nuclear multimessenger inference: https://arxiv.org/html/2607.03045v1

## 3. Observers

### GW

The gravitational-wave observer works in a spectral adiabatic-index chart. Its native evidence is a likelihood over binary masses and effective tidal deformability. It publishes translated samples of \(\Lambda(M)\) and admissible \(M_{\max}\), with waveform and prior provenance.

### XRAY

The X-ray observer works in a piecewise-polytropic chart. Its native evidence is a mass–radius likelihood plus a pulse-profile model label. It publishes \(M\!-\!R\) relation anchors and \(M_{\max}\), retaining surface-emission and calibration provenance.

### RADIO

The radio observer uses a monotone EOS spline only to express the constraint induced by precision mass likelihoods. It publishes support for \(M_{\max}\); it does not fabricate radius or tidal information.

### NUCLEAR

The nuclear-theory observer works in speed-of-sound nodes and publishes a low-density \(p(\varepsilon)\) band. Its information is explicitly partial and cannot determine the high-density relation alone.

## 4. Public Atlas

The Atlas aggregates **relation anchors**, not local EOS coefficients. Every public item carries observer, event, chart, likelihood, prior, translation, and calibration identifiers.

Forbidden operations:

1. averaging parameter vectors from different charts;
2. pooling posterior samples before prior harmonization;
3. replacing every local chart with an Atlas chart;
4. treating HYBRID agreement as ground truth.

This is the operational meaning of domain-conditioned public coherence: the public relations become jointly more predictive while local model families remain non-identical.

## 5. Synthetic truth classes

The first simulator uses three predeclared classes:

1. smooth hadronic;
2. rapid softening followed by restiffening, as a phase-transition proxy;
3. stiff high-density behavior.

All truths must pass thermodynamic stability, causal sound speed, \(M_{\max}\ge2.0\,M_\odot\), and a monotone stable mass branch. The class label is hidden from every inference arm.

The grid covers \(M\in[1.0,2.2]\,M_\odot\) and baryon density \(n\in[1,6]n_{\mathrm{sat}}\). These bounds are design choices for review, not yet frozen scientific claims.

## 6. Predictions

### P1 — domain-conditioned cross-messenger coherence

HYBRID should improve leave-one-observer-out log predictive density relative to IND, while retaining at least half the local-model diversity and maintaining calibrated 90% predictive coverage.

### P2 — translation-cycle holonomy

Controlled bias inserted into an EOS → observable → public relation → local-chart cycle should increase holonomy and held-out predictive loss monotonically. The association, not zero disagreement, is primary.

### P3 — minority phase-transition evidence

A weak phase-transition signature initially present in one observer should retain provenance and be recovered when a second messenger confirms it. The primary p-value comes from recall efficacy. The false-positive rate in no-transition controls is a separate safety gate whose one-sided 95% upper bound must not exceed 0.05.

### P4 — provenance robustness

HYBRID should bound public predictive displacement under duplicated events, substituted priors, and calibration shifts. Every attack is applied to otherwise paired trajectories.

### P5 — recovered spectral control

The positive control from CCSU-MO-CONTROL-RECOVERY-001 is inherited unchanged: Fiedler-mode initialization, kernel-projection error, exact spectral-rate oracle, and \(1/\lambda_2\) only in the preregistered slow regime.

## 7. Decision architecture

P1–P4 form one Holm–Bonferroni family with one efficacy p-value per prediction. P3 safety is separate. P5 is a prerequisite control; its failure yields `CONTROL INVALID / INTERPRETATION SUSPENDED`. No global CCSU score is calculated.

## 8. What remains open

The next review must settle:

- low-density matching prescription;
- numerical ranges for each local EOS chart;
- likelihood and signal-to-noise grids;
- an operational phase-transition definition;
- whether NAIVE_POOL is a primary comparator or a diagnostic arm;
- the confirmatory trajectory budget after an out-of-grid power pilot.

No public freeze or confirmatory simulation is authorized at v0.1.
