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
  ns_eos_v1_1/ns_eos_decisions_v0_4.yaml
PYTHONPATH=src python scripts/run_inner_crust_validation.py \
  --contract ns_eos_v1_1/inner_crust_validation_contract_v0_1.yaml \
  --output /tmp/inner_crust_validation.json \
  --created-utc 2026-07-26T23:08:00Z
PYTHONPATH=src python -m ccsu_multiobserver.ns_eos_low_density \
  ns_eos_v1_1/data/chiral_eft_muses_v1_0_1/manifest_n3lo_414.yaml
PYTHONPATH=src python -m ccsu_multiobserver.ns_eos_low_density \
  ns_eos_v1_1/data/chiral_eft_muses_v1_0_1/manifest_n3lo_450.yaml
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
still pending.

The active checkpoint remains development-only until all blockers in
`ns_eos_decisions_v0_4.yaml` are closed.
