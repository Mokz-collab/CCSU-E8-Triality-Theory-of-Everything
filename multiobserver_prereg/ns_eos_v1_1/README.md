# CCSU-MO-NS-EOS-001 — Development track

This directory is a separate, nonconfirmatory development track for the
neutron-star equation-of-state niche. It does not inherit confirmatory
authorization from the original frozen CCSU simulator.

The current low-density checkpoint contains:

- four byte-pinned modern outer-crust tables;
- three byte-pinned unified-EOS calibration/holdout tables;
- a reference-tilted, thermodynamically exact shared inner-crust connector;
- two deterministically generated MUSES v1.0.1 χEFT reference members,
  N3LO-414 and N3LO-450, in beta-equilibrated npeμ matter.

Validate the active decision lock, replay the inner-crust validation, and
verify the two χEFT members with:

```bash
PYTHONPATH=src python -m ccsu_multiobserver.ns_eos_decisions \
  ns_eos_v1_1/ns_eos_decisions_v0_8.yaml
PYTHONPATH=src python scripts/run_inner_crust_validation.py \
  --contract ns_eos_v1_1/inner_crust_validation_contract_v0_1.yaml \
  --output /tmp/inner_crust_validation.json \
  --created-utc 2026-07-26T23:08:00Z
PYTHONPATH=src python -m ccsu_multiobserver.ns_eos_low_density \
  ns_eos_v1_1/data/chiral_eft_muses_v1_0_1/manifest_n3lo_414.yaml
PYTHONPATH=src python -m ccsu_multiobserver.ns_eos_low_density \
  ns_eos_v1_1/data/chiral_eft_muses_v1_0_1/manifest_n3lo_450.yaml
PYTHONPATH=src python scripts/run_final_low_density_pairing_validation.py \
  --contract ns_eos_v1_1/final_low_density_pairing_contract_v0_1.yaml \
  --output /tmp/final_low_density_pairings.json \
  --created-utc 2026-07-26T23:18:00Z
PYTHONPATH=src python scripts/run_stellar_impact_validation.py \
  --contract ns_eos_v1_1/stellar_impact_contract_v0_1.yaml \
  --output /tmp/stellar_impact.json \
  --created-utc 2026-07-26T23:32:00Z
PYTHONPATH=src python scripts/run_tov_love_cross_validation.py \
  --contract ns_eos_v1_1/tov_love_cross_validation_contract_v0_1.yaml \
  --output /tmp/tov_love_cross_validation.json \
  --created-utc 2026-07-26T23:28:00Z
PYTHONPATH=src python scripts/run_local_chart_validation.py \
  --contract ns_eos_v1_1/local_chart_generator_contract_v0_1.yaml \
  --output /tmp/local_chart_validation.json \
  --created-utc 2026-07-27T10:14:00Z
PYTHONPATH=src python scripts/run_local_to_public_relation_validation.py \
  --contract ns_eos_v1_1/local_to_public_relation_contract_v0_1.yaml \
  --output /tmp/local_to_public_relations.json \
  --created-utc 2026-07-27T10:49:15Z
```

The two χEFT members form a coherent interaction-reference envelope. They do
not carry a formal truncation-error probability or confidence level. Every
observer and inference arm within a trajectory must use the same complete
member.

The endpoint-only exponential connector from v0.4 remains as a rejected
baseline: it closed the endpoints but failed local pressure and chemical-
potential shape thresholds. The active candidate uses a positive derivative
template calibrated on IOPB and tested on held-out G3; FSUGarnet is a
coarse-grid advisory holdout. This accepts the connector only for continued
development. Radius, tidal-deformability, and final endpoint-pairing tests are
complete under one shared synthetic CSS core. That core is diagnostic rather
than a physical prior. A second, enthalpy-based DOP853 implementation agrees
with the radius-based RK4 solver in all ten preregistered cases. This closes
the internal TOV/Love cross-implementation blocker, but it is not validation
by a separately maintained external package or independent research group.

The four local high-density charts are now executable and retain distinct
observer coordinates. Eight registered chart/χEFT-anchor cases pass local
matching, identity, monotonicity, stability, and causality checks. Parameter
boxes remain proposal regions rather than physical priors: invalid candidates
are rejected, never clipped, and the independent range review remains open.
The maximum-mass, stable-branch, and public-relation layer is now executable,
and it correctly refuses to authorize the
registered exemplars. All eight translations complete, but every mass
sequence is still rising at the finite \(6\,n_{\mathrm{sat}}\) boundary.
Consequently no \(M_{\max}\) is invented from the endpoint, zero cases pass
the full stellar gates, and pilot entry is forbidden. The result supplies
lower bounds and partial relation anchors only.

The first deterministic recovery search is now complete. It evaluates 32
Sobol proposals per chart against both χEFT members without changing the
boxes, gates, or finite domain. GW accepts 2/64 cases, XRAY 0/64, RADIO 3/64,
and NUCLEAR 60/64. The result proves that finite-domain candidates exist, but
also demonstrates severe proposal-volume imbalance. Pilot entry therefore
remains forbidden pending independent range review and recovery of XRAY
support. Extrapolation remains prohibited.

An XRAY-focused \(4^4\) centred factorial diagnostic resolves the apparent
zero-support result. Nine of 512 paired cases pass, representing five distinct
proposals; four pass under both χEFT members. The accepted region is a sparse
interaction requiring high \(p_1\), intermediate stiffening, and moderated
final stiffness. XRAY is therefore not structurally excluded by the
\(6\,n_{\mathrm{sat}}\) gate. The open problem is now to define a
chart-neutral proposal measure in common physical-relation coordinates,
rather than equating raw parameter-box volume across charts.

A first chart-neutral occupied-relation measure is now executable. It uses
\(\log_{10}P\), \(P/\varepsilon\), and \(c_s^2\) at five density anchors,
with no observer label or local parameter in the distance. Equal mass is
assigned to each occupied relation component and divided among duplicate
members. At \(\epsilon=0.05\), 74 accepted χEFT realizations form 35
components; the result is exactly stable over \(\epsilon=0.02\)–0.05 and
passes duplicate invariance. No primary component contains more than one
chart, and NUCLEAR accounts for 30/35 occupied cells. The measure is defined,
but balanced sampling coverage and cross-chart overlap are not demonstrated.

The active checkpoint remains development-only until all blockers in
`ns_eos_decisions_v0_11.yaml` are closed.
