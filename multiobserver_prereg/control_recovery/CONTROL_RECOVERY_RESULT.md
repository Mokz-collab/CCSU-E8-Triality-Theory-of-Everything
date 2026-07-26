# CCSU-MO-CONTROL-RECOVERY-001 — result

**Frozen before execution:** yes  
**Freeze commit:** `c75f9c8c497a5a43645d2ce99dd8b0f6d8876f65`  
**Freeze timestamp:** 2026-07-26T20:53:12Z  
**Trajectories:** 2,750  
**Execution failures:** 0  
**Formal classification:** **RECOVERED**

## Gate decisions

| Phase | Gate | Result | Required | Decision |
|---|---|---:|---:|---|
| A | Exact first-passage agreement | 1.000000 | 1.000000 | PASS |
| A | Maximum \(\lambda_2\) error | 0 | \(\le10^{-12}\) | PASS |
| C | Exact recovered-control agreement | 1.000000 | 1.000000 | PASS |
| C | Uncensored fraction | 1.000000 | 1.000000 | PASS |
| C | Slow-mode slope | 1.001579 | [0.95, 1.05] | PASS |
| C | Slow-mode \(R^2\) | 0.999895 | \(\ge0.995\) | PASS |

## What failed in historical P5

Phase A reproduced the frozen P5 recurrence exactly in all 1,500 cases. The historical implementation of \(x_{t+1}=(I-\kappa L_{\mathrm{norm}})x_t\), its \(\lambda_2\), and its first-passage calculation are therefore internally consistent.

Phase B found no operational threshold obstruction: the largest asymptotic dispersion-floor ratio was 0.026713, below the frozen 0.10 threshold. The normalized-Laplacian/median-dispersion pairing is not a general mathematical distance to the kernel, but this incompatibility did not trigger the registered obstruction rule in the tested grid.

The decisive evidence is Phase C. When the initial state isolates the Fiedler mode and the outcome measures distance to the operator kernel, every simulated first passage equals the closed-form oracle and the slow-regime \(1/\lambda_2\) scaling is recovered.

As a descriptive cross-check, applying the historical random-initial-state metric to the Phase A cases again yields slope 0.405801 and \(R^2=0.449019\), close to the historical failure. Because the spectral oracle reproduces each of those trajectories exactly, this poor regression is attributable to the original estimand/design—mixed spectral modes, initial-condition variability, a relatively early threshold, and a global \(1/\lambda_2\) approximation—not to a defective recurrence.

## Canonical consequence

The frozen historical P5 `FAIL` remains unchanged. Its interpretation is now:

> The original P5 regression was an invalidly coarse positive-control specification for the simulated dynamics. It does not establish a failure of the linear update implementation and must not be counted as a substantive refutation of P1–P4.

For future v1.1 studies, the positive control should use:

1. kernel-projection error;
2. a preregistered Fiedler-mode control;
3. the exact rate \(-2\log|1-\kappa\lambda_2|\) as primary oracle;
4. \(1/\lambda_2\) only as a secondary approximation restricted to a frozen slow-mode regime.

This recovery authorizes preparation of a domain-specific v1.1 protocol. It does not retroactively validate P1–P4.

## Integrity

- `runs.jsonl`: `62dc41dbf8324b66a64f28135fda6460339b0c53da4d647c054d4080b732b409`
- public `runs.jsonl.gz` payload: `d21400e2c5350916cc36ab59bc040fded8097d8229332ab15720e91815acc017`
- `summary.json`: `01d55449914f4cb5669ae31443baf13f89a5d502bdde2d6630b331c7618f184a`
- Independent replay: byte-identical for both files.

The public file `runs.jsonl.gz.b64` is decoded with `base64 -d` and then decompressed with `gzip -d`.
