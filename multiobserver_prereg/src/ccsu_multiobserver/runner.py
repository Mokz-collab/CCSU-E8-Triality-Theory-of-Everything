from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from .core import cell_label, deterministic_seed, enumerate_cells, load_config, run_metric, sha256_file


BLOCKS = ("P1", "P2", "P3", "P4", "P5")


def iter_schedule(config, requested: Iterable[str]):
    for block in requested:
        for cell in enumerate_cells(config, block):
            label = cell_label(block, cell)
            for replicate in range(config.replicates):
                seed = deterministic_seed(config.master_seed, label, replicate)
                yield block, cell, label, replicate, seed


def emit_seeds(config, path: Path) -> dict[str, int | str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["block", "cell", "replicate", "seed_uint64"])
        for block, _cell, label, replicate, seed in iter_schedule(config, BLOCKS):
            writer.writerow([block, label, replicate, seed])
            count += 1
    return {"rows": count, "sha256": sha256_file(path), "path": str(path)}


def execute(config, requested: list[str], output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / str(config.data["analysis"]["raw_output"])
    if raw_path.exists() and raw_path.stat().st_size:
        raise FileExistsError(f"refusing to overwrite append-only output: {raw_path}")
    counts: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    with raw_path.open("x", encoding="utf-8") as handle:
        for block, cell, label, replicate, seed in iter_schedule(config, requested):
            row = {
                "registration_id": config.data["registration_id"],
                "confirmatory": config.confirmatory,
                "block": block,
                "cell": label,
                "replicate": replicate,
                "seed": seed,
                **cell,
            }
            try:
                row.update(run_metric(config, block, cell, seed))
                row["status"] = "ok"
            except Exception as exc:
                row["status"] = "failed"
                row["error_type"] = type(exc).__name__
                row["error"] = str(exc)
                failures[block] += 1
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            counts[block] += 1
    summary = {
        "registration_id": config.data["registration_id"],
        "confirmatory": config.confirmatory,
        "config_sha256": sha256_file(config.path),
        "raw_sha256": sha256_file(raw_path),
        "counts": dict(counts),
        "failures": dict(failures),
    }
    summary_path = output / str(config.data["analysis"]["summary_output"])
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CCSU multi-observer preregistered simulator")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--block", choices=[*BLOCKS, "ALL"], default="ALL")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--emit-seeds", type=Path)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.emit_seeds:
        print(json.dumps(emit_seeds(config, args.emit_seeds), sort_keys=True))
        return 0
    if args.output is None:
        parser.error("--output is required unless --emit-seeds is used")
    requested = list(BLOCKS) if args.block == "ALL" else [args.block]
    print(json.dumps(execute(config, requested, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

