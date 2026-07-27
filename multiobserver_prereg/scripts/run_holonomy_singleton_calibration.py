#!/usr/bin/env python3
"""Compare state-aligned cross-chart holonomy with a same-chart singleton null."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    ns_root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    loaded = {}
    inputs = {}
    for key in ("cross_chart_result", "same_chart_null_result"):
        specification = contract[key]
        path = (ns_root / specification["path"]).resolve()
        digest = sha256_file(path)
        if digest != specification["sha256"]:
            raise ValueError(f"{key} hash mismatch")
        loaded[key] = json.loads(path.read_text(encoding="utf-8"))
        inputs[key] = {
            "path": path.name,
            "sha256": digest,
            "canonical_record_sha256": loaded[key][
                "canonical_record_sha256"
            ],
        }
    cross = float(loaded["cross_chart_result"][
        "paired_worst_case_holonomy"
    ])
    null = float(loaded["same_chart_null_result"][
        "paired_worst_case_holonomy"
    ])
    record = {
        "schema": "ccsu.multiobserver.ns-eos-holonomy-singleton-calibration.v1",
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
        "inputs": inputs,
        "available_robust_GW_state_count": 1,
        "singleton_not_distribution": True,
        "cross_chart_paired_worst_case_holonomy": cross,
        "same_chart_null_paired_worst_case_holonomy": null,
        "cross_to_null_holonomy_ratio": cross / null,
        "cross_minus_null_holonomy": cross - null,
        "cross_exceeds_singleton_null": cross > null,
        "statistical_significance_identifiable": False,
        "p_value": None,
        "decision": (
            "CROSS_HOLONOMY_EXCEEDS_SINGLETON_NULL_"
            "SIGNIFICANCE_NOT_IDENTIFIABLE"
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
