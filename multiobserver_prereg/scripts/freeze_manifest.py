from __future__ import annotations

import argparse
import json
from pathlib import Path


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    tracked = [
        root / "config.yaml",
        root / "config_smoke.yaml",
        root / "environment.lock",
        root / "pyproject.toml",
        root / "README.md",
        root / "REVIEW.md",
        root / "artifacts" / "seeds.sha256",
        root / "artifacts" / "seed_schedule_metadata.json",
        args.seeds.resolve(),
    ]
    source_files = sorted((root / "src").rglob("*.py")) + sorted((root / "tests").rglob("*.py"))
    tracked.extend(source_files)
    manifest = {
        "schema_version": 1,
        "registration_id": "CCSU-MO-PREREG-001",
        "statement": "Hashes fixed before confirmatory execution; no confirmatory results inspected.",
        "files": {str(path.relative_to(root)): sha256(path) for path in tracked},
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
