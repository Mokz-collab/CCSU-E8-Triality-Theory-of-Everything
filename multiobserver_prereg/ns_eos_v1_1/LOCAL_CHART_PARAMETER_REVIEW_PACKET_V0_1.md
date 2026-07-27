# CCSU-MO-NS-EOS-001 — Local-chart parameter review packet v0.1

**Status:** internal implementation packet awaiting independent physics review  
**Authorization:** development only; no confirmatory trajectories

## Review question

Do the four proposal boxes generate a sufficiently broad but scientifically
defensible set of cold, beta-equilibrated neutron-star EOS candidates after
the common stability, causality, matching, maximum-mass, and stable-branch
filters are applied?

This question is deliberately narrower than asking whether one chart is the
“correct” EOS parameterization. CCSU requires four genuinely different local
models and compares only their translated physical relations.

## Common construction

Every chart begins at the pinned χEFT endpoint
\(n_0=1.1\,n_{\rm sat}\), preserves its pressure and energy density, and
extends to \(6\,n_{\rm sat}\). With
\(x=\ln(n/n_0)\), all generators enforce

\[
\frac{d\varepsilon}{dx}=\varepsilon+P,\qquad
\mu=\frac{\varepsilon+P}{n},\qquad
c_s^2=\frac{dP}{d\varepsilon}.
\]

Proposals are rejected rather than clipped when they violate a bound or a
physical filter. Parameter vectors from distinct charts are never averaged.
The Atlas receives only relation anchors such as \(P(\varepsilon)\),
\(M\!-\!R\), \(\Lambda(M)\), and \(M_{\max}\).

## Chart-specific decisions

| Observer | Local chart | Frozen proposal coordinates | Main review risk |
|---|---|---|---|
| GW | spectral adiabatic index | \(\gamma_0,\ldots,\gamma_3\) | broad coefficients can create extreme stiffness or causality rejection |
| XRAY | continuous piecewise polytrope | \(\log_{10}P_1,\Gamma_1,\Gamma_2,\Gamma_3\) | lower \(P_1\) values can lie below the pinned χEFT anchor |
| RADIO | monotone log-pressure PCHIP | five positive log-pressure increments | cumulative increments can create implausibly stiff high-density tails |
| NUCLEAR | sound-speed nodes | six \(c_s^2\) values | the upper boundary includes the causal limit and needs explicit treatment |

### GW

The implementation uses

\[
\Gamma(x)=\exp(\gamma_0+\gamma_1x+\gamma_2x^2+\gamma_3x^3),
\qquad
\frac{dP}{dx}=\Gamma P.
\]

Exponentiation guarantees positive adiabatic index, but not causality.
Therefore \(c_s^2\le1\) remains a separate common filter. Lindblom's spectral
construction motivates a low-dimensional faithful chart; it does not by
itself validate the numerical coefficient box used here.

### XRAY

The pressure at \(2\,n_{\rm sat}\) is \(P_1\). The first segment is a shifted
power law fixed at both the χEFT anchor and \(P_1\); later segments are
continuous ordinary power laws. This avoids silently moving the common match
point when \(P_1\) or \(\Gamma_1\) changes.

The lower registered range, \(\log_{10}P_1=33.6\), can be below the pinned
pressure at \(1.1\,n_{\rm sat}\). Such samples are intentionally rejected.
The independent reviewer should decide whether retaining this dead part of
the box is useful for testing rejection behavior or should be removed in a
newly registered version.

### RADIO

Five positive increments define pressure values on nodes
\((1.1,1.5,2,3,4.5,6)\,n_{\rm sat}\). PCHIP interpolation in log pressure and
log density preserves monotonicity without imposing a global polynomial.
This is a deliberately simple local chart, not a Gaussian-process posterior
and not a claim that radio mass data directly determine the full EOS.

### NUCLEAR

Six \(c_s^2\) nodes on the same density grid are interpolated with a
shape-preserving spline and integrated through the thermodynamic identities.
Node bounds \(0.01\le c_s^2\le1\) guarantee physical node values, but the
interpolated curve is still checked pointwise. The boundary \(c_s^2=1\) is
allowed but never exceeded.

## Primary methodological basis

- [Lindblom (2010)](https://arxiv.org/abs/1009.0738) constructs efficient,
  faithful spectral representations for cold barotropic EOSs.
- [Read et al. (2009)](https://arxiv.org/abs/0812.2163) establish the
  piecewise-polytropic approach and explicitly treat causality and
  observational constraints.
- [Landry and Essick (2019)](https://arxiv.org/abs/1811.12529) demonstrate a
  broad causal, thermodynamically stable nonparametric EOS ensemble and show
  the practical importance of prior sensitivity.
- [Altiparmak, Ecker and Rezzolla (2022)](https://arxiv.org/abs/2203.14974)
  construct large continuous-sound-speed EOS ensembles subject to nuclear,
  perturbative-QCD, and astronomical constraints.

These sources justify the chart families and physical gates. They do not
independently approve the CCSU numerical ranges.

## Required independent-review responses

The reviewer must answer, separately for each chart:

1. Are the coordinates and units unambiguous?
2. Is the proposal box broad enough to avoid favoring one observer?
3. Does any range contain a large unusable region that should be removed?
4. Are the match at \(1.1\,n_{\rm sat}\) and the endpoint at
   \(6\,n_{\rm sat}\) scientifically defensible?
5. Do the common filters produce materially unequal accepted prior volumes?
6. Are phase-transition truths unfairly disadvantaged by a smooth chart?
7. Should a pQCD high-density condition be added before confirmation?

An answer of “accept” must include reviewer identity, date, declared
conflicts, version/hash reviewed, and reasons. Silence or internal CCSU review
does not close the blocker.
