#!/usr/bin/env python3
"""Build a chart-neutral occupied-relation measure with provenance."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_local_charts import generate_local_chart
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_recovery import (
    common_relation_projection,
    equal_component_measure,
    relation_distance_matrix,
    relation_vector,
)


def _observer_mass_close(
    left: dict[str, float],
    right: dict[str, float],
    tolerance: float,
) -> bool:
    return set(left) == set(right) and all(
        abs(float(left[key]) - float(right[key])) <= tolerance
        for key in left
    )


def run_measure(contract_path: Path, created_utc: str) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    chart_contract_path = (
        ns_root / contract["local_chart_contract"]
    ).resolve()
    recovery_path = (ns_root / contract["recovery_result"]).resolve()
    xray_path = (ns_root / contract["xray_diagnostic_result"]).resolve()
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    xray = json.loads(xray_path.read_text(encoding="utf-8"))
    eft_paths = [
        (ns_root / relative).resolve()
        for relative in contract["chiral_eft_anchors"]
    ]
    eft_tables = [load_thermodynamic_table(path) for path in eft_paths]
    eft_by_label = {table.model_label: table for table in eft_tables}
    density_anchors = tuple(
        float(value) for value in contract["relation_space"][
            "density_anchors_nsat"
        ]
    )

    atoms: list[dict[str, object]] = []
    projections: list[dict[str, list[float]]] = []
    for case in recovery["cases"]:
        if case["outcome"] != "ACCEPTED":
            continue
        eft = eft_by_label[case["chiral_eft_model"]]
        chart = generate_local_chart(
            case["observer"],
            case["parameters"],
            eft.last,
            sample_count=int(chart_contract["sample_count"]),
        )
        projection = common_relation_projection(chart, density_anchors)
        atoms.append(
            {
                "atom_id": case["case_id"],
                "observer": case["observer"],
                "chiral_eft_model": case["chiral_eft_model"],
                "source_result": recovery_path.name,
                "source_case_id": case["case_id"],
                "relation_projection": projection,
                "local_parameters_included": False,
            }
        )
        projections.append(projection)
    for case in xray["cases"]:
        if case["outcome"] != "ACCEPTED":
            continue
        projection = case["relation_projection"]
        atoms.append(
            {
                "atom_id": case["case_id"],
                "observer": "XRAY",
                "chiral_eft_model": case["chiral_eft_model"],
                "source_result": xray_path.name,
                "source_case_id": case["case_id"],
                "relation_projection": projection,
                "local_parameters_included": False,
            }
        )
        projections.append(projection)

    scaling = contract["relation_space"]["scaling"]
    vectors = [
        relation_vector(
            projection,
            log_pressure_scale_decades=float(
                scaling["log10_pressure_decades"]
            ),
            pressure_over_energy_scale=float(
                scaling["pressure_over_energy"]
            ),
            sound_speed_squared_scale=float(
                scaling["sound_speed_squared"]
            ),
        )
        for projection in projections
    ]
    distances = relation_distance_matrix(vectors)
    sensitivity_epsilons = tuple(
        float(value) for value in contract["occupancy_measure"][
            "sensitivity_epsilons"
        ]
    )
    sensitivity = {
        str(epsilon): equal_component_measure(
            atoms,
            distances,
            epsilon=epsilon,
        )
        for epsilon in sensitivity_epsilons
    }
    primary_epsilon = float(
        contract["occupancy_measure"]["primary_epsilon"]
    )
    primary = sensitivity[str(primary_epsilon)]
    plateau_epsilons = tuple(
        float(value) for value in contract["occupancy_measure"][
            "required_local_plateau_epsilons"
        ]
    )
    plateau_rows = [sensitivity[str(value)] for value in plateau_epsilons]
    plateau_tolerance = float(
        contract["occupancy_measure"]["mass_stability_tolerance"]
    )
    plateau_pass = (
        len({row["component_count"] for row in plateau_rows}) == 1
        and all(
            _observer_mass_close(
                plateau_rows[0]["observer_attributed_mass"],
                row["observer_attributed_mass"],
                plateau_tolerance,
            )
            for row in plateau_rows[1:]
        )
    )

    duplicated_atoms = atoms + [dict(atoms[0])]
    duplicated_vectors = vectors + [vectors[0].copy()]
    duplicated_measure = equal_component_measure(
        duplicated_atoms,
        relation_distance_matrix(duplicated_vectors),
        epsilon=primary_epsilon,
    )
    duplicate_invariance = (
        duplicated_measure["component_count"]
        == primary["component_count"]
        and _observer_mass_close(
            duplicated_measure["observer_attributed_mass"],
            primary["observer_attributed_mass"],
            plateau_tolerance,
        )
    )

    for component in primary["components"]:
        indices = component["atom_indices"]
        within = distances[np.ix_(indices, indices)]
        medoid_offset = int(np.argmin(np.sum(within, axis=1)))
        medoid_index = int(indices[medoid_offset])
        component["medoid_atom_index"] = medoid_index
        component["medoid_atom_id"] = atoms[medoid_index]["atom_id"]

    local_parameters_excluded = all(
        set(atom)
        == {
            "atom_id",
            "observer",
            "chiral_eft_model",
            "source_result",
            "source_case_id",
            "relation_projection",
            "local_parameters_included",
        }
        and atom["local_parameters_included"] is False
        for atom in atoms
    )
    mixed_components = int(primary["mixed_observer_component_count"])
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-common-relation-measure.v1",
        "measure_id": contract["measure_id"],
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
        "inputs": {
            "recovery_result": {
                "path": recovery_path.name,
                "sha256": sha256_file(recovery_path),
            },
            "xray_diagnostic_result": {
                "path": xray_path.name,
                "sha256": sha256_file(xray_path),
            },
            "local_chart_contract": {
                "path": chart_contract_path.name,
                "sha256": sha256_file(chart_contract_path),
            },
        },
        "relation_space": contract["relation_space"],
        "occupancy_measure_rule": contract["occupancy_measure"],
        "atoms": atoms,
        "atom_count": len(atoms),
        "local_parameters_excluded": local_parameters_excluded,
        "primary_measure": primary,
        "sensitivity": sensitivity,
        "local_plateau_pass": plateau_pass,
        "duplicate_atom_invariance_pass": duplicate_invariance,
        "cross_observer_components_at_primary_epsilon": mixed_components,
        "cross_observer_overlap_demonstrated": mixed_components > 0,
        "equal_relation_space_coverage_demonstrated": False,
        "decision": (
            "COMMON_RELATION_MEASURE_DEFINED_LOCAL_STABILITY_PASSED_"
            "SAMPLING_COVERAGE_UNRESOLVED"
            if (
                plateau_pass
                and duplicate_invariance
                and local_parameters_excluded
            )
            else "COMMON_RELATION_MEASURE_IMPLEMENTATION_FAILED"
        ),
        "does_not_validate": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "numpy": np.__version__,
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
    record = run_measure(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
