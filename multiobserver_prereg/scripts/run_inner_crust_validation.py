#!/usr/bin/env python3
"""Execute the registered development validation of the inner-crust bridge."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    connector_metrics,
    evaluate_thresholds,
    load_derivative_template,
    load_unified_eos_oracle,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import sha256_file


def run_validation(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != 1:
        raise ValueError("inner-crust validation schema_version must equal 1")
    template_path = (
        root / contract["connectors"]["candidate"]["template"]
    ).resolve()
    template = load_derivative_template(template_path)
    primary_thresholds = contract["primary_thresholds"]
    secondary_thresholds = contract["secondary_advisory_thresholds"]

    sources: dict[str, object] = {}
    results: dict[str, object] = {}
    split = contract["data_split"]
    for split_label, source_config in split.items():
        manifest_path = (root / source_config["manifest"]).resolve()
        oracle = load_unified_eos_oracle(manifest_path)
        thresholds = (
            secondary_thresholds
            if split_label == "secondary_coarse_grid_holdout"
            else primary_thresholds
        )
        sources[split_label] = {
            "model_label": oracle.model_label,
            "validation_role": oracle.validation_role,
            "manifest_path": str(manifest_path.relative_to(root)),
            "manifest_sha256": sha256_file(manifest_path),
            "table_sha256": oracle.sha256,
            "upstream_git_blob_sha": oracle.upstream_git_blob_sha,
            "source_commit": oracle.source_commit,
            "slice_rows": len(oracle.inner_crust_rows()),
            "density_range_fm3": [
                oracle.inner_crust_rows()[0].n_b_fm3,
                oracle.inner_crust_rows()[-1].n_b_fm3,
            ],
        }
        connector_results: dict[str, object] = {}
        for connector_label, connector_config in contract["connectors"].items():
            metrics = connector_metrics(
                oracle,
                connector_config["kind"],
                template if connector_label == "candidate" else None,
            )
            threshold_results = evaluate_thresholds(metrics, thresholds)
            connector_results[connector_label] = {
                "kind": connector_config["kind"],
                "metrics": asdict(metrics),
                "threshold_results": threshold_results,
                "all_thresholds_pass": all(threshold_results.values()),
            }
        results[split_label] = connector_results

    candidate_primary_pass = all(
        results[split_label]["candidate"]["all_thresholds_pass"]
        for split_label in ("calibration", "primary_holdout")
    )
    baseline_primary_failure = all(
        not results[split_label]["baseline"]["all_thresholds_pass"]
        for split_label in ("calibration", "primary_holdout")
    )
    secondary_advisory_pass = results[
        "secondary_coarse_grid_holdout"
    ]["candidate"]["all_thresholds_pass"]
    decision = (
        "ACCEPT_REFERENCE_TILTED_FOR_CONTINUED_DEVELOPMENT"
        if candidate_primary_pass and baseline_primary_failure
        else "DO_NOT_ACCEPT_CANDIDATE"
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.inner-crust-validation-result.v1",
        "validation_id": contract["validation_id"],
        "status": "DEVELOPMENT_NOT_CONFIRMATORY",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": str(contract_path.relative_to(root)),
            "sha256": sha256_file(contract_path),
        },
        "template": {
            "path": str(template_path.relative_to(root)),
            "sha256": sha256_file(template_path),
            "template_id": template.template_id,
        },
        "sources": sources,
        "results": results,
        "decision_checks": {
            "candidate_calibration_and_primary_holdout_pass": (
                candidate_primary_pass
            ),
            "baseline_fails_calibration_and_primary_holdout": (
                baseline_primary_failure
            ),
            "secondary_coarse_grid_advisory_pass": secondary_advisory_pass,
        },
        "decision": decision,
        "decision_scope": contract["decision_rule"]["success_scope"],
        "remaining_nonvalidated_items": contract["decision_rule"][
            "does_not_validate"
        ],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
    }
    record["canonical_record_sha256"] = validation_record_sha256(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    record = run_validation(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
