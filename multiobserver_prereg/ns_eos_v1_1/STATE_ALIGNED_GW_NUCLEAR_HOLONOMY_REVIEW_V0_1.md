# State-aligned GW–NUCLEAR holonomy review v0.1

## Design

The paired accepted state `GW__S0029` was frozen as \(x_{\rm GW}\). The
registered composition was evaluated sequentially:

\[
x_{\rm GW}\xrightarrow{T_{\rm GW\to NUCLEAR}}y_{\rm NUCLEAR}
\xrightarrow{T_{\rm NUCLEAR\to GW}}x'_{\rm GW}.
\]

The reverse optimizer targeted the actual paired NUCLEAR projections returned
by the forward leg. It did not target an independently selected cell.
Parameters remained private in memory; the public record contains hashes.

## Results

| Quantity | N3LO-414 | N3LO-450 | Paired worst case |
|---|---:|---:|---:|
| Forward relation loss | 0.010907 | 0.010530 | 0.010907 |
| Reverse relation loss | 0.009422 | 0.009467 | 0.009467 |
| Round-trip holonomy \(H_c\) | 0.005986 | 0.005861 | 0.005986 |

Both legs pass the unchanged \(\epsilon=0.05\) relation threshold and every
frozen stellar gate under both EFT members.

## Interpretation

The measured value is a state-conditioned round-trip residual in the frozen
15-coordinate public relation metric. It demonstrates that numeric holonomy
is identifiable for this particular GW–NUCLEAR state-aligned cycle.

It does not establish global curvature, path independence, an atlas-wide
holonomy distribution, observational viability, or confirmatory evidence.
The value is nonzero, but no inferential threshold has yet been calibrated
for deciding whether its magnitude is scientifically exceptional.

## Decision

`STATE_ALIGNED_GW_NUCLEAR_HOLONOMY_MEASURED`

The state-aligned composition blocker is closed for one registered state.
The next development requirement is a frozen local state ensemble and null
calibration capable of distinguishing numerical/optimization closure error
from stable chart-transition holonomy. Pilot and confirmatory authorization
remain false.

