# CCSU-MO-NS-EOS-001 — XRAY relation-space diagnostic review v0.1

**Status:** finite-domain XRAY support found in a sparse interaction region  
**Study class:** deterministic nonconfirmatory diagnostic  
**Pilot entry:** forbidden  
**Confirmatory authorization:** false

## Question

Did XRAY have zero acceptance because the piecewise-polytrope chart cannot
satisfy the frozen stellar gates inside \(6\,n_{\rm sat}\), or because the
32-point Sobol design missed a small interaction region?

No parameter bound, density endpoint, stellar gate, or treatment of invalid
proposals was changed.

## Design

The four registered XRAY parameters were evaluated on the centred unit levels
\(\{0.125,0.375,0.625,0.875\}\). The full \(4^4\) factorial gives 256
proposals, paired with both χEFT members for 512 cases. Boundary points were
excluded. Every local pass was projected to the common physical coordinates

\[
\left\{\log_{10}P,\;P/\varepsilon,\;c_s^2\right\}
\quad\text{at}\quad
n/n_{\rm sat}\in\{2,3,4,5,6\}.
\]

The 24-point stellar screen and 48-point exact revalidation are unchanged
from finite-domain recovery v0.1.

## Result

| Outcome | Cases |
|---|---:|
| Accepted | 9 |
| Local-physics rejection | 120 |
| No turnover inside \(6\,n_{\rm sat}\) | 365 |
| Turnover below \(2.2\,M_\odot\) | 18 |
| Numerical rejection | 0 |

The nine accepted cases represent five distinct parameter proposals. Four
proposals pass for both χEFT members; one passes for one member only.

All accepted cases have

- \(\log_{10}p_1[\mathrm{dyn\,cm^{-2}}]=34.65\), the 0.875 interior level;
- \(\gamma_2=3.1875\), the 0.625 level;
- eight cases at \(\gamma_3=2.3125\), the 0.375 level;
- acceptance across all four tested \(\gamma_1\) levels.

The accepted exact maximum masses are approximately
\(2.305\)–\(2.311\,M_\odot\) for the four χEFT-robust proposals.

## Interpretation

The original XRAY 0/64 result was not evidence of structural impossibility.
The accepted set occupies a sparse joint region requiring high pressure at
\(2\,n_{\rm sat}\), substantial intermediate stiffening, and moderated final
stiffness. One-factor marginal summaries alone would not reveal this
interaction.

This is a factorial association, not a claim of observational or physical
causation. The diagnostic also does not establish a physical measure on the
XRAY parameter box. It only shows that the finite-domain gates are reachable
without extrapolation.

## Consequence for CCSU Multiobserver

“XRAY zero acceptance” is closed as a blocker. The deeper imbalance remains:
raw equal counts in four unrelated parameter spaces do not induce equal
coverage in the shared relation space. The next design object must therefore
be a chart-neutral proposal or weighting rule defined on physical relations,
with local charts retained as coordinate maps rather than averaged parameter
vectors.

No candidate enters P1–P4 calibration and pilot entry remains forbidden.
