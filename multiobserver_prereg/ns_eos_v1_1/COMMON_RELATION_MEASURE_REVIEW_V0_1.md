# CCSU-MO-NS-EOS-001 — Common relation measure review v0.1

**Status:** measure defined; local stability passed; sampling coverage unresolved  
**Study class:** deterministic nonconfirmatory diagnostic  
**Pilot entry:** forbidden  
**Confirmatory authorization:** false

## Measure

Each accepted chart/χEFT case is translated to the 15-dimensional physical
relation vector

\[
r=\left(
\log_{10}P(n_k),\;
P(n_k)/\varepsilon(n_k),\;
c_s^2(n_k)
\right)_{k=1}^{5},
\qquad
n_k/n_{\rm sat}\in\{2,3,4,5,6\}.
\]

The distance is the root-mean-square difference over the 15 scaled
coordinates. Observer identity, parameter names, and local parameter values
do not enter the metric. Provenance remains attached to every atom.

Atoms separated by at most \(\epsilon\) are linked. Each connected occupied
component receives equal mass, and that mass is divided equally among its
member atoms. Consequently, duplicating an existing atom cannot give its
relation cell additional mass.

The development value is \(\epsilon=0.05\), selected after recovery. It is
not a confirmatory threshold.

## Result

The input contains 74 accepted chart/χEFT atoms. At the primary resolution:

| Quantity | Result |
|---|---:|
| Occupied components | 35 |
| Mass per component | \(1/35\) |
| Mixed-observer components | 0 |
| Total measure | 1 |

Provenance-attributed mass is:

| Chart | Measure mass |
|---|---:|
| GW | 0.028571 |
| XRAY | 0.057143 |
| RADIO | 0.057143 |
| NUCLEAR | 0.857143 |

Component count and attributed masses are exactly stable for
\(\epsilon\in\{0.02,0.03,0.05\}\). Duplicate-atom invariance passes.

At \(\epsilon=0.075\), one cross-observer component appears. The system then
percolates progressively: 34 components at 0.075, 32 at 0.10, and 12 at 0.15.
Thus cross-chart overlap is resolution-sensitive and is not demonstrated at
the primary resolution.

## Interpretation

The undefined-measure blocker is closed: there is now an executable,
chart-neutral rule on translated physical relations. It does not average
local parameters or erase observer provenance.

The measure does not prove balanced physical coverage. NUCLEAR occupies 30 of
the 35 resolved relation components in the present candidate pool. This may
reflect broader physical coverage, denser exploration, or both; the current
samples cannot distinguish those explanations. It is not evidence that
NUCLEAR is the superior observer.

## Next requirement

The next diagnostic must sample toward relation-space cells rather than draw
equal counts from incomparable parameter boxes. For every target cell it must
record which local charts can reach it, translation loss, χEFT robustness,
and explicit nonreachability. Only then can inter-chart overlap and coverage
be evaluated without confusing parameterization density with physical
support.

No weight from this development measure enters P1–P4 calibration.
