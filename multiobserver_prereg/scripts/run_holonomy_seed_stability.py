#!/usr/bin/env python3
"""Estimate descriptive GW-cycle holonomy stability across frozen seeds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import sha256_file
from run_state_aligned_gw_nuclear_cycle import run_cycle


def summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    mean = float(np.mean(array))
    standard_deviation = float(np.std(array, ddof=1))
    return {
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "coefficient_of_variation": standard_deviation / mean,
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
        "range": float(np.ptp(array)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    ns_root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    cross_contract = ns_root / contract["cross_contract"]
    null_contract = ns_root / contract["null_contract"]
    rows = []
    for replicate in contract["replicates"]:
        if replicate["source"] == "existing_public_results":
            records = {}
            for condition, key in (
                ("cross", "existing_cross_result"),
                ("null", "existing_null_result"),
            ):
                specification = contract[key]
                path = ns_root / specification["path"]
                if sha256_file(path) != specification["sha256"]:
                    raise ValueError(f"{condition} existing result hash mismatch")
                records[condition] = json.loads(path.read_text(encoding="utf-8"))
        else:
            records = {
                "cross": run_cycle(
                    cross_contract,
                    args.created_utc,
                    tuple(int(x) for x in replicate["cross_seeds"]),
                ),
                "null": run_cycle(
                    null_contract,
                    args.created_utc,
                    tuple(int(x) for x in replicate["null_seeds"]),
                ),
            }
        cross = float(records["cross"]["paired_worst_case_holonomy"])
        null = float(records["null"]["paired_worst_case_holonomy"])
        rows.append(
            {
                "replicate": replicate["replicate"],
                "cross_seeds": replicate["cross_seeds"],
                "null_seeds": replicate["null_seeds"],
                "source": replicate["source"],
                "cross_holonomy": cross,
                "null_holonomy": null,
                "cross_to_null_ratio": cross / null,
                "cross_minus_null": cross - null,
                "cross_exceeds_null": cross > null,
                "cross_cycle_valid": records["cross"][
                    "cycle_valid_under_frozen_gates"
                ],
                "null_cycle_valid": records["null"][
                    "cycle_valid_under_frozen_gates"
                ],
                "cross_canonical_record_sha256": records["cross"][
                    "canonical_record_sha256"
                ],
                "null_canonical_record_sha256": records["null"][
                    "canonical_record_sha256"
                ],
            }
        )
    cross_summary = summary([row["cross_holonomy"] for row in rows])
    null_summary = summary([row["null_holonomy"] for row in rows])
    rule = contract["descriptive_stability_rule"]
    direction_consistent = all(row["cross_exceeds_null"] for row in rows)
    all_cycles_valid = all(
        row["cross_cycle_valid"] and row["null_cycle_valid"] for row in rows
    )
    stable = (
        all_cycles_valid
        and direction_consistent
        and cross_summary["coefficient_of_variation"]
        <= float(rule["maximum_cross_coefficient_of_variation"])
        and null_summary["coefficient_of_variation"]
        <= float(rule["maximum_null_coefficient_of_variation"])
    )
    record = {
        "schema": "ccsu.multiobserver.ns-eos-holonomy-seed-stability.v1",
        "registration_id": contract["registration_id"],
        "version": contract["version"],
        "status": "DEVELOPMENT_NONCONFIRMATORY",
        "confirmatory_authorization": False,
        "pilot_entry_authorized": False,
        "created_utc": args.created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "source": {
            "path": contract["source"],
            "sha256": sha256_file(ns_root.parent / contract["source"]),
        },
        "state": contract["state"],
        "replicates": rows,
        "replicate_count_per_condition": len(rows),
        "cross_summary": cross_summary,
        "null_summary": null_summary,
        "cross_exceeds_null_count": sum(
            row["cross_exceeds_null"] for row in rows
        ),
        "direction_consistent": direction_consistent,
        "all_cycles_valid_under_frozen_gates": all_cycles_valid,
        "descriptive_stability_rule": rule,
        "descriptive_seed_stability_pass": stable,
        "statistical_significance_identifiable": False,
        "p_value": None,
        "decision": (
            "DESCRIPTIVE_SEED_STABILITY_PASSED"
            if stable
            else "DESCRIPTIVE_SEED_STABILITY_FAILED"
        ),
        "does_not_validate": contract["does_not_validate"],
    }
    record["canonical_record_sha256"] = validation_record_sha256(record)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
