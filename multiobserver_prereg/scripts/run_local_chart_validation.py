#!/usr/bin/env python3
"""Validate the four registered NS-EOS local chart generators."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy
import scipy
import yaml

from ccsu_multiobserver.ns_eos_decisions import (
    load_and_validate_decisions,
)
from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    evaluate_local_physics,
    generate_local_chart,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)


def _assert_contract_matches_decisions(
    contract: dict[str, object],
    decisions: dict[str, object],
) -> None:
    decision_charts = decisions["local_chart_proposals"]
    contract_charts = contract["charts"]
    for observer, specification in CHART_SPECIFICATIONS.items():
        if contract_charts[observer]["chart"] != specification.chart:
            raise ValueError(f"{observer} contract chart changed")
        if decision_charts[observer]["chart"] != specification.chart:
            raise ValueError(f"{observer} decision chart changed")

    for name, bounds in contract_charts["GW"]["parameters"].items():
        if bounds != decision_charts["GW"]["parameters"][name]:
            raise ValueError(f"GW range changed for {name}")
    for name, bounds in contract_charts["XRAY"]["parameters"].items():
        if bounds != decision_charts["XRAY"]["parameters"][name]:
            raise ValueError(f"XRAY range changed for {name}")
    radio_bounds = decision_charts["RADIO"][
        "log_pressure_increment_dex"
    ]
    if any(
        bounds != radio_bounds
        for bounds in contract_charts["RADIO"]["parameters"].values()
    ):
        raise ValueError("RADIO increment range changed")
    nuclear_bounds = decision_charts["NUCLEAR"]["cs2_range"]
    if any(
        bounds != nuclear_bounds
        for bounds in contract_charts["NUCLEAR"]["parameters"].values()
    ):
        raise ValueError("NUCLEAR sound-speed range changed")


def run_validation(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    decision_path = (root / contract["decision_lock"]).resolve()
    environment_lock_path = (
        root / contract["environment_lock"]
    ).resolve()
    decisions = load_and_validate_decisions(decision_path)
    _assert_contract_matches_decisions(contract, decisions)

    anchor_tables = [
        load_thermodynamic_table((root / relative).resolve())
        for relative in contract["anchors"]
    ]
    cases: list[dict[str, object]] = []
    for table in anchor_tables:
        for observer in ("GW", "XRAY", "RADIO", "NUCLEAR"):
            chart_contract = contract["charts"][observer]
            parameters = chart_contract["registered_exemplar"]
            eos = generate_local_chart(
                observer,
                parameters,
                table.last,
                sample_count=int(contract["sample_count"]),
            )
            diagnostics = evaluate_local_physics(
                eos,
                table.last,
                relative_matching_tolerance=float(
                    contract["local_acceptance"][
                        "matching_relative_tolerance"
                    ]
                ),
                identity_tolerance=float(
                    contract["local_acceptance"][
                        "thermodynamic_identity_relative_tolerance"
                    ]
                ),
            )
            cases.append(
                {
                    "case_id": f"{observer}__{table.model_label}",
                    "observer": observer,
                    "chart": eos.chart,
                    "anchor_model": table.model_label,
                    "anchor_table_sha256": table.sha256,
                    "parameters": dict(
                        zip(
                            eos.parameter_names,
                            eos.parameter_values,
                            strict=True,
                        )
                    ),
                    "diagnostics": diagnostics,
                    "all_local_checks_pass": diagnostics[
                        "all_local_checks_pass"
                    ],
                }
            )

    all_pass = all(case["all_local_checks_pass"] for case in cases)
    distinct_charts = len({case["chart"] for case in cases}) == 4
    decision = (
        "FOUR_LOCAL_CHART_GENERATORS_PASSED_INTERNAL_LOCAL_FILTERS"
        if all_pass and distinct_charts
        else "LOCAL_CHART_GENERATOR_VALIDATION_FAILED"
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-local-chart-result.v1",
        "validation_id": contract["generator_contract_id"],
        "status": "DEVELOPMENT_NOT_CONFIRMATORY",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "decision_lock": {
            "path": decision_path.name,
            "sha256": sha256_file(decision_path),
            "resolved_version": decisions["version"],
        },
        "source": {
            "path": contract["source"],
            "sha256": sha256_file(
                contract_path.parents[0].parent / contract["source"]
            ),
        },
        "environment_lock": {
            "path": environment_lock_path.name,
            "sha256": sha256_file(environment_lock_path),
        },
        "cases": cases,
        "case_count": len(cases),
        "all_cases_pass": all_pass,
        "four_distinct_local_charts": distinct_charts,
        "decision": decision,
        "remaining_nonvalidated_items": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "pyyaml": yaml.__version__,
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
