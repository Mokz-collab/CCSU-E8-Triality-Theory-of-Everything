# CCSU-MO-CONTROL-RECOVERY-001

## Preregistered positive-control recovery protocol

**Version:** 1.0  
**Status before execution:** implementation review only; no recovery trajectory may be interpreted before the public freeze commit  
**Scope:** diagnose and recover P5; no P1–P4 claim is retested or reclassified  
**Historical boundary:** all CCSU-MO-PREREG-001 files, hashes, trajectories, analyses, and decisions remain immutable

## 1. Failure under investigation

Historical P5 predicted \(\tau\propto1/\lambda_2(L_{\mathrm{norm}})\), but the observed log–log slope was 0.415319 and \(R^2=0.415064\). The recovery study distinguishes:

1. **implementation mismatch:** the frozen recurrence disagrees with an independently evaluated spectral oracle;
2. **measurement mismatch:** the public-dispersion metric has a nonzero asymptotic floor under the symmetric normalized-Laplacian operator;
3. **design mismatch:** random initial spectral mixtures and a non-asymptotic threshold do not isolate the \(\lambda_2\) mode.

## 2. Frozen operator

The historical recurrence is reconstructed without changing its code:

\[
x_{t+1}=(I-\kappa L_{\mathrm{norm}})x_t,\qquad \kappa=0.20.
\]

For a connected graph, \(L_{\mathrm{norm}}\) has null vector

\[
v_1\propto(\sqrt{d_1},\ldots,\sqrt{d_N})^\top.
\]

Therefore, on an irregular graph, the limit \(v_1v_1^\top x_0\) need not be constant across observers. Dispersion around the componentwise median is not generally a distance to the operator’s consensus subspace.

## 3. Phase A — implementation equivalence

For every preregistered seed, the historical P5 function is compared with an independent spectral evaluation:

\[
x_t=V\,\mathrm{diag}\!\left((1-\kappa\lambda_j)^t\right)V^\top x_0.
\]

The original stopping metric, threshold and ten-consecutive-step rule are preserved.

Design: \(N\in\{3,5,9\}\), five topologies, 100 replicates per cell; 1,500 cases.

Pass only if:

- the first-passage time agrees in 100% of cases;
- the maximum absolute \(\lambda_2\) discrepancy is at most \(10^{-12}\);
- there are no execution failures.

Failure classifies P5 as an implementation problem and stops canonical interpretation.

## 4. Phase B — measurement audit

For the same cases, compute the asymptotic public-dispersion floor:

\[
F_Q=\frac{D_Q(v_1v_1^\top x_0)}{D_Q(x_0)}.
\]

If \(F_Q\ge0.10\), the historical stopping threshold is obstructed by the metric/operator pairing. The fraction of obstructed cases is reported by topology. This phase is classificatory and has no significance test.

## 5. Phase C — recovered spectral control

The recovered control keeps the symmetric normalized Laplacian but replaces the incompatible measurement and initial-state design:

- initial state lies in a Fiedler eigenspace;
- error is squared distance to the kernel projection \(v_1v_1^\top x_t\);
- threshold is \(E_t/E_0\le0.10\);
- the exact spectral first-passage oracle is

\[
\tau_*=
\left\lceil
\frac{\log(0.10)}
     {2\log|1-\kappa\lambda_2|}
\right\rceil .
\]

Design: \(N\in\{3,5,9,17,33\}\), five topologies, 50 replicates per cell; 1,250 cases. Repeated deterministic graphs test reproducibility; ER replicates sample graph variation.

Primary pass gates:

- simulated \(\tau=\tau_*\) in 100% of cases;
- uncensored fraction equals 1;
- no execution failures.

Secondary slow-mode scaling gate, restricted prospectively to \(\lambda_2\le0.25\):

\[
\log\tau=a+\beta\log(1/\lambda_2),
\]

with \(\beta\in[0.95,1.05]\) and \(R^2\ge0.995\), calculated over unique spectral cells so deterministic duplicates receive no extra weight.

## 6. Frozen decision rule

- **RECOVERED:** all Phase A and Phase C gates pass.
- **IMPLEMENTATION MISMATCH:** any Phase A equivalence gate fails.
- **MEASUREMENT/DESIGN MISMATCH:** Phase A passes, Phase B detects obstruction, and Phase C passes.
- **SPECTRAL CONTROL NOT RECOVERED:** Phase A passes but any Phase C gate fails.

Only **RECOVERED** authorizes preparation of a new domain-specific CCSU v1.1 confirmatory protocol. It does not itself validate P1–P4.

## 7. Integrity and reporting

The configuration, protocol, code, tests and environment are publicly committed before the registered recovery schedule is run. Output is append-only JSONL. The report must include all cases, failures, censoring, gate values, file hashes, the public freeze commit and a later result commit. No threshold, topology, observer count, metric or classification rule may change after the freeze.
