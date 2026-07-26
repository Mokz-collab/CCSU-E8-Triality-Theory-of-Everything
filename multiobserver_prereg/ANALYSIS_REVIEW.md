# Confirmatory analysis engine review

Review date: 2026-07-26

## Scope

The review covered the new analysis engine and operational addendum. No
confirmatory trajectory was executed or inspected. The original simulator,
confirmatory configuration, environment lock, seed schedule, content manifest,
and public attestation remain byte-for-byte unchanged.

## Checks applied

- Python byte-compilation: passed.
- Unit and integration suite: 14 tests passed, 0 failed.
- Frozen-boundary verification: passed for all files in the original content
  manifest.
- Public config SHA-256: unchanged at
  `d522fba2db9cb08316bed0bc0e39a9685bdf1b1355aa2054787ab79ed93b0d35`.
- Non-confirmatory end-to-end execution: complete P1–P5 schedule analyzed
  twice; report hashes matched.
- Duplicate row: refused.
- Missing or unexpected schedule row: guarded by exact schedule validation.
- Seed or cell mismatch: guarded by deterministic schedule validation.
- Non-finite primary outcome: converted to a disclosed execution failure.
- Existing analysis output: refused rather than overwritten.
- Confirmatory bootstrap override: refused.

## Scale check

A synthetic 97,500-row schedule with no confirmatory simulator outcomes was
validated and analyzed successfully. With 100 development bootstrap resamples,
schedule validation took 1.679 seconds and analysis took 7.347 seconds in the
attested runtime. The confirmatory run remains fixed at 10,000 resamples.

## Decision

The engine is ready to freeze publicly. Its code and
`analysis_addendum.json` must receive a public commit and timestamp before the
first confirmatory JSONL is read. Until that occurs, its status is
implementation-complete but not yet part of the public preregistration chain.
