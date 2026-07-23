# CCSU Multi-Observer Simulator

This package implements the frozen simulation design for
`CCSU-MO-PREREG-001`. It tests P1–P5 for the proposed multi-observer lift:
local observer states, partial translations, a provenance-aware public Atlas,
and a relational interaction graph.

## Integrity boundary

- `config.yaml` is the confirmatory configuration.
- `config_smoke.yaml` uses a different observer count, noise level, seed, and
  horizon. It is safe for implementation checks and must not be used as
  confirmatory evidence.
- Confirmatory output is append-only JSON Lines. The change from Parquet was
  made before freezing because JSON Lines is natively append-only and avoids an
  unpinned storage engine.
- P1–P4 are confirmatory. P5 is a positive control for the linear consensus
  implementation.

## Run the review suite

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m ccsu_multiobserver.runner \
  --config config_smoke.yaml --block ALL --output artifacts/smoke
```

## Emit the frozen seed schedule without running simulations

```bash
PYTHONPATH=src python -m ccsu_multiobserver.runner \
  --config config.yaml --emit-seeds artifacts/seeds.csv.gz
```

## Confirmatory execution

Run one block at a time. The runner refuses to overwrite an existing raw file.

```bash
PYTHONPATH=src python -m ccsu_multiobserver.runner \
  --config config.yaml --block P1 --output outputs/P1
```

Each JSONL row is one trajectory. Cell labels and seeds are deterministic from
the master seed and are also listed in the compressed seed schedule.

