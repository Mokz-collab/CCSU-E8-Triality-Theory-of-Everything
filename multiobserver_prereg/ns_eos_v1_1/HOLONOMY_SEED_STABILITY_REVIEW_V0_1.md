# Holonomy seed-stability review v0.1

This development-only diagnostic repeats the frozen GW–NUCLEAR cross-chart
cycle and the GW same-chart null at three predeclared optimizer-seed pairs.
It keeps the optimizer budget, relation threshold \(\epsilon=0.05\), local
parameter boxes, paired EFT rule, stellar gates, and
\(6\,n_{\mathrm{sat}}\) finite domain unchanged. The only independent state is
the paired GW state `S0029`; generalization across physical states is
explicitly deferred.

The descriptive rule was frozen before execution:

- cross-chart coefficient of variation no greater than 0.25;
- same-chart-null coefficient of variation no greater than 0.25;
- cross-chart holonomy greater than its paired null in all three replicates;
- sample standard deviation with `ddof=1`;
- no p-value, false-positive rate, or significance claim.

| Replicate | Cross seeds | Null seeds | Cross \(H_c\) | Null \(H_c\) | Cross/null | Cross > null |
|---:|---|---|---:|---:|---:|:---:|
| 1 | 20260735, 20260736 | 20260737, 20260738 | 0.00598615 | 0.00109427 | 5.47047 | yes |
| 2 | 20260739, 20260740 | 20260743, 20260744 | 0.00289042 | 0.00305283 | 0.94680 | no |
| 3 | 20260741, 20260742 | 20260745, 20260746 | 0.00209560 | 0.00096939 | 2.16177 | yes |

All six cycles pass the unchanged relation and stellar gates. The failure is
therefore not a physical-gate rejection. It is instability of the numerical
holonomy estimator under optimizer seeds:

| Condition | Mean \(H_c\) | Sample SD | CV | Frozen maximum CV |
|---|---:|---:|---:|---:|
| GW–NUCLEAR cross chart | 0.00365739 | 0.00205555 | 0.56203 | 0.25 |
| GW same-chart null | 0.00170550 | 0.00116850 | 0.68514 | 0.25 |

Both coefficients of variation exceed the frozen limit, and the direction
reverses in replicate 2. The original 5.47 cross/null ratio is thus a valid
record for its seed pair but is not a stable estimate.

Decision: `DESCRIPTIVE_SEED_STABILITY_FAILED`.

No threshold was changed after seeing the results. No p-value is reported,
and pilot and confirmatory authorization remain false. Before expanding to
multiple independent GW states, a separately frozen optimizer-convergence
diagnostic must determine whether a larger fixed budget or a deterministic
polishing rule makes the same seed grid converge to a stable estimator.
