#!/usr/bin/env python3
"""Create a deterministic, nonconfirmatory NS-EOS development checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccsu_multiobserver.ns_eos_low_density import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _registered_files() -> tuple[Path, ...]:
    files = [
        path
        for path in (PROJECT_ROOT / "ns_eos_v1_1").rglob("*")
        if path.is_file()
        and not path.name.startswith("ns_eos_development_checkpoint_")
    ]
    files.extend(
        PROJECT_ROOT / relative
        for relative in (
            "scripts/create_ns_eos_development_checkpoint.py",
            "scripts/fit_inner_crust_reference_template.py",
            "scripts/generate_muses_chiral_eft_anchor.py",
            "scripts/run_inner_crust_validation.py",
            "src/ccsu_multiobserver/ns_eos_decisions.py",
            "src/ccsu_multiobserver/ns_eos_inner_crust_validation.py",
            "src/ccsu_multiobserver/ns_eos_low_density.py",
            "tests/test_ns_eos_decisions.py",
            "tests/test_ns_eos_inner_crust_validation.py",
            "tests/test_ns_eos_low_density.py",
        )
    )
    return tuple(sorted(set(files)))


def create_checkpoint(created_utc: str) -> dict[str, object]:
    validation_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "inner_crust_validation_results_v0_1.json"
    )
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    files = {
        str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
        for path in _registered_files()
    }
    return {
        "schema": "ccsu.multiobserver.ns-eos-development-checkpoint.v1",
        "registration_id": "CCSU-MO-NS-EOS-001",
        "version": "0.5-development",
        "status": "DEVELOPMENT_NOT_FROZEN",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "branch": "multiobserver-control-recovery-v1-20260726",
        "parent_commit": "679115740f6214d4abe15b29a0931d54b5307889",
        "scientific_source_bytes_embedded": True,
        "tests": {
            "command": "PYTHONPATH=src python -m unittest discover -s tests -v",
            "passed": 61,
            "failed": 0,
        },
        "reproducibility_replay": {
            "muses_anchor": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "binary_sha256": (
                    "4da03ecfb458accae7443c7525a3a9ba4dd237f3c833ecb584c11ce1ccc893ea"
                ),
                "products_compared": 8,
                "mismatches": 0,
            },
            "inner_crust_template": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(
                    PROJECT_ROOT
                    / "ns_eos_v1_1"
                    / "data"
                    / "unified_eos_hcdas_2022"
                    / "inner_crust_derivative_template_v0_1.json"
                ),
            },
            "inner_crust_validation": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(validation_path),
                "canonical_record_sha256": validation[
                    "canonical_record_sha256"
                ],
            },
        },
        "inner_crust_decision": {
            "retired_rule": "endpoint_exponential_v0_4",
            "retired_rule_status": "FAILED_EXTERNAL_LOCAL_SHAPE_VALIDATION",
            "active_candidate": "reference_tilted_v0_5_candidate",
            "active_candidate_status": (
                "ACCEPTED_FOR_CONTINUED_DEVELOPMENT_ONLY"
            ),
            "calibration_model": "IOPB",
            "primary_holdout_model": "G3",
            "secondary_advisory_model": "FSUGarnet",
            "validation_decision": validation["decision"],
        },
        "files": files,
        "remaining_freeze_blockers": [
            (
                "validate_final_outer_crust_EFT_pairings_and_"
                "stellar_radius_tidal_impact"
            ),
            "independent_review_of_parameter_ranges",
            "TOV_and_Love_cross_implementation_agreement",
            "pilot_calibration_of_P1_to_P4_thresholds",
            "power_derived_confirmatory_budget",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    record = create_checkpoint(args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
