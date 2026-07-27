# CCSU-MO-NS-EOS-001 — Local-to-public relation review v0.1

**Status:** numerical translation implemented; registered exemplars fail the
finite-domain stellar gates  
**Pilot entry:** forbidden  
**Confirmatory authorization:** false

## Frozen question

Can each registered local chart be translated into its permitted public
relations while remaining entirely inside the EOS domain ending at
\(6\,n_{\rm sat}\)?

The registered rule forbids a constant-sound-speed or other extrapolation
above that endpoint. \(M_{\max}\) is reported only when the stable sequence
turns over inside the registered domain. Otherwise the result is a lower
bound at \(6\,n_{\rm sat}\), not an estimated maximum.

## What worked

All eight chart/χEFT cases were translated numerically. Required provenance is
present, local parameters are excluded from Atlas records, and observer roles
remain distinct:

- GW publishes \(\Lambda(M)\) and maximum-mass information;
- XRAY publishes \(M\!-\!R\) and maximum-mass information;
- RADIO publishes maximum-mass information only;
- NUCLEAR publishes \(P(\varepsilon)\) density anchors.

The registered step-halving check passed. Maximum relative changes were
\(7.89\times10^{-7}\) in mass, \(4.16\times10^{-7}\) in radius,
\(6.38\times10^{-4}\) in \(k_2\), and \(6.36\times10^{-4}\) in
\(\Lambda\).

## What failed

None of the eight exemplars reaches a mass turnover before
\(6\,n_{\rm sat}\). Consequently:

- no case has an identified \(M_{\max}\);
- no case translates every mass anchor from \(1.0\) to \(2.2\,M_\odot\);
- zero cases pass all stellar gates;
- pilot entry remains forbidden.

Mass supported at the finite-domain endpoint:

| Chart | N3LO-414 | N3LO-450 |
|---|---:|---:|
| GW spectral | 1.0269 | 0.9861 |
| XRAY piecewise polytrope | 1.0594 | 1.0595 |
| RADIO monotone spline | 0.3268 | 0.3082 |
| NUCLEAR sound-speed nodes | 2.1844 | 2.1837 |

The NUCLEAR exemplars demonstrate stable \(2\,M_\odot\) models, so their true
maximum mass is at least \(2.18\,M_\odot\). That does not identify
\(M_{\max}\), and it still misses the registered \(2.2\,M_\odot\) anchor.

## Interpretation

This is a failure of the registered exemplar choices under the finite-domain
gate, not a failure of TOV/Love integration and not evidence that one observer
is scientifically superior. The examples were selected to test local
thermodynamics; they were not calibrated to produce viable stellar branches.

The frozen inference rule responsible for the refusal is:

> Do not infer \(M_{\max}\) from the last sampled mass when the sequence is
> still rising at \(6\,n_{\rm sat}\).

Relaxing this rule would convert an unobserved extrapolation into apparent
evidence and could manufacture acceptance.

## Required recovery

Before any P1–P4 pilot:

1. define a deterministic, nonconfirmatory search over each existing proposal
   box;
2. measure rejection causes and accepted-volume imbalance by chart;
3. require support for the full \(1.0\)–\(2.2\,M_\odot\) relation grid;
4. require a mass turnover inside \(6\,n_{\rm sat}\), or openly revise the
   registered density domain in a new protocol version;
5. submit the resulting ranges and acceptance diagnostics to independent
   physics review.

No existing public lock is rewritten by this result.
