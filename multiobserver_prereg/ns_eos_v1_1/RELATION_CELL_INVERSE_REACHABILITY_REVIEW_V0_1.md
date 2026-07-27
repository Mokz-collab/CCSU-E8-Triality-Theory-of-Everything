# CCSU-MO-NS-EOS-001 — Relation-cell inverse reachability review v0.1

**Status:** inverse map evaluated; no robust cross-chart overlap at
\(\epsilon=0.05\)  
**Study class:** deterministic nonconfirmatory diagnostic  
**Pilot entry:** forbidden  
**Confirmatory authorization:** false

## Design

The 35 medoids of the common-relation measure are treated as target cells.
For each of the four charts, an inverse bank contains 256 fixed scrambled
Sobol proposals plus the chart's distinct public accepted seeds. All
parameters stay inside the existing boxes.

Each proposal is translated under both χEFT members. Selection minimizes

\[
L_{\max}(\theta,r_\star)=
\max_{e\in\{414,450\}}d\!\left(r_e(\theta),r_\star\right).
\]

A target/chart pair is relation-reachable when
\(L_{\max}\le0.05\). Only reachable pairs receive exact 48-point stellar
revalidation. Robust reachability requires every frozen stellar gate to pass
under both χEFT members. The public matrix contains candidate identifiers and
parameter hashes, not local parameter vectors.

## Banks

| Chart | Raw candidates | Paired local passes | Paired rejections |
|---|---:|---:|---:|
| GW | 257 | 126 | 131 |
| XRAY | 261 | 179 | 82 |
| RADIO | 258 | 94 | 164 |
| NUCLEAR | 286 | 286 | 0 |

Invalid proposals were rejected, not clipped.

## Reachability

| Chart | Relation-reachable cells | Robustly reachable cells | Median loss |
|---|---:|---:|---:|
| GW | 1 | 1 | 0.14259 |
| XRAY | 2 | 2 | 0.18841 |
| RADIO | 1 | 1 | 0.15452 |
| NUCLEAR | 30 | 30 | 0.00049 |

No cell is robustly reachable by two charts. Thirty-four cells retain robust
support from their source chart only.

The remaining cell is the singleton
`RADIO__MUSES-N3LO-450__S0022`. It is not pair-robust: the best paired RADIO
candidate lies outside the relation threshold. Treating the one-member case
as shared support would violate the paired χEFT rule.

The closest cross-chart near misses are:

- RADIO cell 1 → NUCLEAR: \(L_{\max}=0.06032\);
- XRAY cell 34 → GW: \(L_{\max}=0.06151\);
- GW cell 0 → NUCLEAR: \(L_{\max}=0.06521\);
- RADIO singleton cell 2 → NUCLEAR: \(L_{\max}=0.06629\).

All remain above the frozen development resolution of 0.05.

## Interpretation

This result makes non-overlap explicit rather than inferring it from raw
parameter counts. Under the current deterministic banks, the translated
charts occupy distinct relation cells at the registered resolution. That is
compatible with persistent observer plurality, but it does not yet provide
cross-chart invariants for the proposed Atlas.

The result is not a proof of mathematical nonreachability. Sobol banks do not
solve the global inverse problem. The next search must target the four
cross-chart near misses directly with deterministic bounded optimization,
using the same minimax χEFT loss and without changing the 0.05 threshold.

No inverse candidate or weight enters P1–P4 calibration.
