#!/usr/bin/env python3
"""Freeze robust transition records and classify holonomy identifiability."""

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


def directed_cycles(
    nodes: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
    minimum_length: int = 2,
) -> tuple[tuple[str, ...], ...]:
    adjacency = {
        node: tuple(sorted(target for source, target in edges if source == node))
        for node in nodes
    }
    cycles: set[tuple[str, ...]] = set()

    def canonical(cycle: tuple[str, ...]) -> tuple[str, ...]:
        rotations = tuple(
            cycle[index:] + cycle[:index] for index in range(len(cycle))
        )
        return min(rotations)

    def walk(start: str, current: str, path: tuple[str, ...]) -> None:
        for target in adjacency[current]:
            if target == start and len(path) >= minimum_length:
                cycles.add(canonical(path))
            elif target not in path:
                walk(start, target, path + (target,))

    for node in nodes:
        walk(node, node, (node,))
    return tuple(sorted(cycles))


def run_analysis(contract_path: Path, created_utc: str) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    input_spec = contract["targeted_optimization_result"]
    result_path = (ns_root / input_spec["path"]).resolve()
    if sha256_file(result_path) != input_spec["sha256"]:
        raise ValueError("targeted optimization result hash mismatch")
    optimization = json.loads(result_path.read_text(encoding="utf-8"))

    transitions: list[dict[str, object]] = []
    for problem in optimization["problems"]:
        if not (
            problem["relation_reachable"]
            and problem["robust_cross_chart_overlap"]
            and problem["exact_stellar_status"]
            == "PASS_BOTH_EFT_MEMBERS"
        ):
            continue
        from_chart = str(problem["target_chart"])
        to_chart = str(problem["source_chart"])
        member_results = problem["exact_stellar_member_results"]
        if len(member_results) != 2 or not all(
            row["all_stellar_gates_pass"]
            for row in member_results.values()
        ):
            raise ValueError("robust transition lacks paired stellar support")
        transitions.append(
            {
                "transition_id": f"{from_chart}_TO_{to_chart}_CELL_"
                f"{problem['target_component_index']}",
                "from_chart": from_chart,
                "to_chart": to_chart,
                "direction_semantics": (
                    "optimized_chart_to_target_cell_owner_chart"
                ),
                "target_component_index": problem[
                    "target_component_index"
                ],
                "target_medoid_atom_id": problem["target_medoid_atom_id"],
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
                "eft_member_provenance": {
                    label: {
                        "status": row["status"],
                        "maximum_mass_msun": row["maximum_mass_msun"],
                        "all_stellar_gates_pass": row[
                            "all_stellar_gates_pass"
                        ],
                    }
                    for label, row in sorted(member_results.items())
                },
                "local_parameter_vector_in_public_record": False,
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
            contract["holonomy_rule"]["minimum_cycle_length"]
        ),
    )
    holonomy_identifiable = bool(cycles)
    if holonomy_identifiable:
        holonomy_status = "CYCLE_FOUND_MAP_COMPOSITION_REQUIRES_EVALUATION"
    else:
        holonomy_status = contract["holonomy_rule"]["no_cycle_outcome"]

    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-transition-holonomy.v1",
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
        "input": {
            "path": result_path.name,
            "sha256": sha256_file(result_path),
            "canonical_record_sha256": optimization[
                "canonical_record_sha256"
            ],
        },
        "transition_records": transitions,
        "transition_count": len(transitions),
        "directed_edges": [
            {"from_chart": source, "to_chart": target}
            for source, target in edges
        ],
        "closed_directed_cycles": [list(cycle) for cycle in cycles],
        "closed_directed_cycle_count": len(cycles),
        "holonomy_identifiable": holonomy_identifiable,
        "holonomy_status": holonomy_status,
        "holonomy_value": None,
        "zero_holonomy_claimed": False,
        "scalar_path_loss_interpreted_as_holonomy": False,
        "decision": (
            "ROBUST_TRANSITIONS_FROZEN_"
            + (
                "CYCLE_AVAILABLE"
                if holonomy_identifiable
                else "HOLONOMY_NOT_IDENTIFIABLE"
            )
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

