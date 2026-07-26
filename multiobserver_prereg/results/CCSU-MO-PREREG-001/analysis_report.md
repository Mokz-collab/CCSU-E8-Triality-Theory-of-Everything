# CCSU Multi-Observer confirmatory analysis

- Registration: `CCSU-MO-PREREG-001`
- Engine: `1.0.0`
- Confirmatory input: `true`
- Bootstrap resamples: `10000`
- Config SHA-256: `d522fba2db9cb08316bed0bc0e39a9685bdf1b1355aa2054787ab79ed93b0d35`

## Decisions

| Prediction | Decision | Thresholds | Raw p | Holm p |
|---|---:|---:|---:|---:|
| P1 | **FAIL** | fail | 0.989701 | 1 |
| P2 | **FAIL** | fail | 1 | 1 |
| P3 | **FAIL** | pass | 0.0747925 | 0.29917 |
| P4 | **FAIL** | fail | 1 | 1 |
| P5 | **FAIL** | fail | — | — |

There is no global CCSU score. P1–P5 retain independent decisions; P5 is a positive control and is not included in Holm correction.

## Primary estimands

### P1

| Gate | Estimate | Lower 95% | Upper 95% | Pass |
|---|---:|---:|---:|---:|
| hybrid_r_q_below_1 | 1.00536 | 1.00162 | 1.00921 | no |
| private_retention_above_0_25 | 1.07295 | 1.07024 | 1.07558 | yes |
| hybrid_outperforms_ind | -0.0109773 | -0.0163133 | -0.00549771 | yes |

### P2

| Gate | Estimate | Lower 95% | Upper 95% | Pass |
|---|---:|---:|---:|---:|
| spearman_above_0_20 | -0.0721471 | -0.17431 | -0.0471731 | no |
| out_of_sample_delta_r2_above_0_02 | -0.0129926 | -0.0379198 | 1.55964e-05 | no |

### P3

| Gate | Estimate | Lower 95% | Upper 95% | Pass |
|---|---:|---:|---:|---:|
| mean_recall_gain_above_0 | 0.347111 | 0.335556 | 0.358889 | yes |
| median_recall_gain_at_least_0_10 | 0.332 | 0.314 | 0.372 | yes |
| hybrid_fpr_at_most_0_05 | 0.0455556 | 0.0406667 | 0.0508889 | yes |

### P4

| Gate | Estimate | Lower 95% | Upper 95% | Pass |
|---|---:|---:|---:|---:|
| sign_flip: median_at_most_0_15 | 0.342499 | 0.338809 | 0.344493 | no |
| sign_flip: p95_at_most_0_30 | 0.488855 | 0.48418 | 0.492488 | no |
| confidence_inflation: median_at_most_0_15 | 0.0350021 | 0.0347664 | 0.0351944 | yes |
| confidence_inflation: p95_at_most_0_30 | 0.0482638 | 0.0477713 | 0.0487609 | yes |
| replay: median_at_most_0_15 | 0 | 0 | 0 | yes |
| replay: p95_at_most_0_30 | 0 | 0 | 0 | yes |

### P5

| Gate | Estimate | Lower 95% | Upper 95% | Pass |
|---|---:|---:|---:|---:|
| slope_in_interval | 0.415319 | 0.403129 | 0.42781 | no |
| r_squared_at_least_0_80 | 0.415064 | 0.383677 | 0.439596 | no |

## Deviations and execution failures

Recorded deviations: `0`. See `deviations.jsonl`; any primary execution failure forces the corresponding prediction to fail.
