# Holonomy singleton calibration review v0.1

The frozen GW robust ensemble contains one paired state, `S0029`. A same-chart
GW → GW → GW null was therefore run from a different Sobol start under the
same 30-generation budget, paired EFT rule, relation threshold, finite domain,
and stellar gates.

| Quantity | Value |
|---|---:|
| GW–NUCLEAR cross-chart \(H_c\) | 0.00598615 |
| GW same-chart null \(H_c\) | 0.00109427 |
| Cross/null ratio | 5.47047 |
| Cross minus null | 0.00489188 |

Both null legs pass the relation and stellar gates. The null is nonzero,
showing a measurable optimizer/numerical closure floor. The cross-chart
residual exceeds this singleton floor, so it is not fully explained by that
one null execution.

This is not a null distribution: there is one state and one null run. No
p-value, false-positive rate, confidence interval, or significance claim is
identifiable.

Decision:
`CROSS_HOLONOMY_EXCEEDS_SINGLETON_NULL_SIGNIFICANCE_NOT_IDENTIFIABLE`.

The next step is seed-replicated null and cross-chart execution on a
predeclared local state ensemble. Confirmatory and pilot authorization remain
false.

