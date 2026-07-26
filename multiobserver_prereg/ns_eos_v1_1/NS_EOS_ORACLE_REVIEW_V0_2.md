# CCSU-MO-NS-EOS-001 — TOV/Love Oracle Review v0.2

**Status:** internal self-consistency passed; external cross-validation pending  
**Scientific use:** development only; no confirmatory authorization

## Purpose

The oracle is a deliberately small implementation of the nonrotating TOV
equations and the quadrupolar (\(l=2\)) tidal Love equation. It provides an
independent target for later EOS-chart translation tests without importing the
production inference stack.

It uses the dimensionless relativistic polytrope

\[
\rho=(p/K)^{1/\Gamma},\qquad
\varepsilon=\rho+\frac{p}{\Gamma-1},
\]

with \(K=1\) and \(\Gamma=2\). These values define a numerical benchmark, not a
physical neutron-star EOS.

## Locked development contract

The executable defaults and reference sequence are recorded in
`ns_eos_oracle_contract_v0_2.yaml`. The solver jointly integrates mass,
pressure, and the Love response variable with a pressure-limited fourth-order
Runge–Kutta step. The surface is the registered fractional pressure floor,
not an inferred physical crust boundary.

At central pressure \(p_c=0.2\), reducing the maximum step from \(10^{-3}\) to
\(5\times10^{-4}\) changes all registered observables by much less than 1%:

| Quantity | \(h_{\max}=10^{-3}\) | \(h_{\max}=5\times10^{-4}\) |
|---|---:|---:|
| \(M\) | 0.1606394896 | 0.1606394793 |
| \(R\) | 0.6907219992 | 0.6907218779 |
| \(k_2\) | 0.0207139761 | 0.0207139637 |
| \(\Lambda\) | 20.29677673 | 20.29675330 |

The reference sequence also has the expected qualitative behavior: mass rises
on the tested low-pressure stable branch, while increasing compactness reduces
\(k_2\) and \(\Lambda\). Acausal central states and horizon crossing are explicit
errors.

## What passed

1. finite positive \(M\), \(R\), \(k_2\), and \(\Lambda\);
2. \(0<M/R<1/2\);
3. stable-branch mass monotonicity at the registered low-pressure points;
4. step-halving convergence within the 1% internal threshold;
5. deterministic reproduction of the contract sequence;
6. rejection of an EOS with \(c_s^2>1\).

## What has not passed

This is not yet independent cross-implementation validation. TOV and Love are
implemented in the same module, so a shared equation or convention error could
survive every current test. The oracle also omits physical-unit conversion,
tabulated crust/EFT matching, density discontinuity surface corrections, rapid
rotation, temperature, composition evolution, and production interpolation.

Before a public freeze:

1. reproduce the contract with a separately maintained TOV/Love code;
2. compare \(M\), \(R\), \(k_2\), and \(\Lambda\) at all registered points;
3. add at least one tabulated EOS benchmark with pinned bytes and units;
4. register the tolerance and discrepancy policy before viewing production-grid
   results.

## Decision

The internal oracle is accepted as a translation-development tool. The
`TOV_and_Love_cross_implementation_agreement` freeze blocker remains open, and
no result from this module may be treated as confirmatory evidence.
