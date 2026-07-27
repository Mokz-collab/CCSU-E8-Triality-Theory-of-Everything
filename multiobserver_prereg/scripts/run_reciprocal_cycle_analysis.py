#!/usr/bin/env python3
"""Combine robust point transitions and classify reciprocal graph cycles."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import sha256_file
from run_transition_holonomy_analysis import directed_cycles


def run_analysis(contract_path: Path, created_utc: str) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    inputs: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    for specification in contract["optimization_results"]:
        path = (ns_root / specification["path"]).resolve()
        digest = sha256_file(path)
        if digest != specification["sha256"]:
            raise ValueError(f"optimization result hash mismatch: {path.name}")
        result = json.loads(path.read_text(encoding="utf-8"))
        inputs.append(
            {
                "path": path.name,
                "sha256": digest,
                "canonical_record_sha256": result[
                    "canonical_record_sha256"
                ],
            }
        )
        for problem in result["problems"]:
            if not (
                problem["relation_reachable"]
                and problem["robust_cross_chart_overlap"]
                and problem["exact_stellar_status"]
                == "PASS_BOTH_EFT_MEMBERS"
            ):
                continue
            from_chart = str(problem["target_chart"])
            to_chart = str(problem["source_chart"])
            transitions.append(
                {
                    "transition_id": (
                        f"{from_chart}_TO_{to_chart}_CELL_"
                        f"{problem['target_component_index']}"
                    ),
                    "from_chart": from_chart,
                    "to_chart": to_chart,
                    "record_kind": (
                        "point_to_relation_cell_correspondence"
                    ),
                    "state_aligned_map": False,
                    "target_component_index": problem[
                        "target_component_index"
                    ],
                    "target_medoid_atom_id": problem[
                        "target_medoid_atom_id"
                    ],
                    "paired_worst_case_relation_loss": problem[
                        "optimized_paired_worst_case_loss"
                    ],
                    "member_relation_losses": problem[
                        "optimized_member_losses"
                    ],
                    "candidate_parameter_sha256": problem[
                        "optimized_parameter_sha256"
                    ],
                    "stellar_status": problem["exact_stellar_status"],
                    "local_parameter_vector_in_public_record": False,
                    "source_result": path.name,
                }
            )
    transitions.sort(key=lambda row: str(row["transition_id"]))
    nodes = tuple(str(node) for node in contract["observer_order"])
    edges = tuple(
        (str(row["from_chart"]), str(row["to_chart"]))
        for row in transitions
    )
    cycles = directed_cycles(
        nodes,
        edges,
        minimum_length=int(
            contract["cycle_rule"]["minimum_directed_cycle_length"]
        ),
    )
    graph_cycles_available = bool(cycles)
    state_aligned_maps_available = all(
        bool(row["state_aligned_map"]) for row in transitions
    )
    numeric_holonomy_identifiable = (
        graph_cycles_available and state_aligned_maps_available
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-reciprocal-cycles.v1",
        "registration_id": contract["registration_id"],
        "version": contract["version"],
        "status": "DEVELOPMENT_NONCONFIRMATORY",
        "confirmatory_authorization": False,
        "pilot_entry_authorized": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "source": {
            "path": contract["source"],
            "sha256": sha256_file(project_root / contract["source"]),
        },
        "inputs": inputs,
        "transition_records": transitions,
        "transition_count": len(transitions),
        "directed_edges": [
            {"from_chart": source, "to_chart": target}
            for source, target in edges
        ],
        "closed_directed_cycles": [list(cycle) for cycle in cycles],
        "closed_directed_cycle_count": len(cycles),
        "graph_cycles_available": graph_cycles_available,
        "state_aligned_composable_maps_available": (
            state_aligned_maps_available
        ),
        "numeric_holonomy_identifiable": numeric_holonomy_identifiable,
        "holonomy_status": (
            "NUMERIC_HOLONOMY_IDENTIFIABLE"
            if numeric_holonomy_identifiable
            else "GRAPH_CYCLES_FOUND_STATE_ALIGNED_MAPS_MISSING"
        ),
        "holonomy_value": None,
        "zero_holonomy_claimed": False,
        "scalar_path_loss_interpreted_as_holonomy": False,
        "decision": (
            "RECIPROCAL_ROBUST_CYCLES_FOUND_"
            "HOLONOMY_REQUIRES_STATE_ALIGNED_MAPS"
        ),
        "does_not_validate": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
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
    record = run_analysis(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
