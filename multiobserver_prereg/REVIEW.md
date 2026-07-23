# Pre-freeze review

Review date: 2026-07-23 UTC

## Static and unit checks

- Python byte-compilation: passed.
- `unittest`: 6 tests passed, 0 failed.
- Graph connectivity, seed determinism, robust median, provenance
  deduplication, all five metric implementations, and seed-manifest sizing were
  covered.

## Non-confirmatory smoke execution

The smoke configuration is outside the confirmatory grid:

- master seed: `4242424242`
- observers: `N=4`
- noise: `0.22`
- reduced horizons and three replicates per cell

Results:

- 90 trajectories completed.
- failures: 0
- raw JSONL SHA-256:
  `31befe500d1ad624fb5c388e713d6dc24061a7e08326cadf20b9353e03f464c7`
- an independent replay produced the same SHA-256 byte for byte.

Smoke outputs are deliberately excluded from the public freeze commit. They
are implementation evidence, not evidence for P1–P5.

## Confirmatory seed schedule

- rows: 97,500
- unique seeds: 97,500
- P1: 18,000
- P2: 18,000
- P3: 36,000
- P4: 18,000
- P5: 7,500
- compressed seed schedule SHA-256:
  `137ed9536561daa584a5d5304e6760dcb58c1408d7611f0e9d48140aa446ab26`

No confirmatory trajectory was executed or inspected before freezing.
