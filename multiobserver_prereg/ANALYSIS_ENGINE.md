# Confirmatory analysis engine

`ccsu_multiobserver.analysis` turns the complete append-only P1–P5 JSONL run
into independent confirmatory decisions. It does not calculate a global CCSU
score.

## Frozen boundary

The engine verifies the public attestation, the original content manifest,
every file named in that manifest, `config.yaml`, `environment.lock`, and the
compressed seed schedule before reading confirmatory output. New analysis
files are deliberately outside the original simulator manifest: the frozen
simulator remains byte-for-byte unchanged.

`analysis_addendum.json` fixes operational choices that the original protocol
left implicit. The engine and addendum must receive a public commit and
timestamp before any confirmatory JSONL is read.

## Confirmatory command

Run the five blocks into separate output directories, then provide their common
parent (or repeat `--input` for individual JSONL files):

```bash
PYTHONPATH=src python -m ccsu_multiobserver.analysis \
  --config config.yaml \
  --attestation public_attestation.json \
  --input outputs \
  --output analyses/CCSU-MO-PREREG-001
```

The analysis refuses an incomplete or duplicate schedule, a seed mismatch, a
changed frozen file, an environment mismatch, an input hash mismatch, or an
existing output directory.

## Outputs

- `analysis_report.json`: machine-readable estimands, BCa limits, gates,
  multiplicity correction, and P1–P5 decisions.
- `analysis_report.md`: compact human-readable report.
- `deviations.jsonl`: immutable-style ledger of non-finite outcomes and
  execution failures.
- `analysis_manifest.json`: SHA-256 hashes of inputs and analysis outputs.

Every written failed row and every non-finite primary metric in a
preregistered primary contrast arm forces its prediction to fail. Failures in
other arms remain disclosed without changing the primary decision.
Infrastructure-incomplete schedules are not silently converted into
scientific failures; the engine refuses them until the same frozen seeds have
completed.

## Non-confirmatory development

Development fixtures require an explicit flag and may use a lower bootstrap
count:

```bash
PYTHONPATH=src python -m ccsu_multiobserver.analysis \
  --config path/to/nonconfirmatory.yaml \
  --input path/to/runs \
  --output path/to/analysis \
  --allow-nonconfirmatory \
  --bootstrap-resamples 200
```
