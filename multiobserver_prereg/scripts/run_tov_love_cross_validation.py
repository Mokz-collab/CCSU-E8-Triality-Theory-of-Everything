#!/usr/bin/env python3
"""Cross-check radial RK4 and enthalpy DOP853 TOV/Love implementations."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

import scipy
import yaml

from ccsu_multiobserver.ns_eos_enthalpy_oracle import solve_star_enthalpy
from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_stellar_impact import (
    MEV_FM3_TO_GEOMETRIC_KM2,
    build_low_density_barotrope,
    solve_physical_star,
)


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def run_cross_validation(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    stellar_contract_path = (
        root / contract["source_stellar_contract"]
    ).resolve()
    stellar_results_path = (
        root / contract["source_stellar_results"]
    ).resolve()
    pairing_contract_path = (
        root / contract["pairing_contract"]
    ).resolve()
    stellar_contract = yaml.safe_load(
        stellar_contract_path.read_text(encoding="utf-8")
    )
    stellar_results = json.loads(
        stellar_results_path.read_text(encoding="utf-8")
    )
    pairing_contract = yaml.safe_load(
        pairing_contract_path.read_text(encoding="utf-8")
    )
    template_path = (
        root / stellar_contract["template"]
    ).resolve()
    template = load_derivative_template(template_path)
    outer_tables = {
        table.model_label: table
        for table in (
            load_thermodynamic_table((root / path).resolve())
            for path in pairing_contract["outer_crust_manifests"]
        )
    }
    eft_tables = {
        table.model_label: table
        for table in (
            load_thermodynamic_table((root / path).resolve())
            for path in pairing_contract["chiral_eft_manifests"]
        )
    }
    registered_models = {
        (
            model["pair_id"],
            float(model["target_mass_msun"]),
        ): model
        for model in stellar_results["models"]
        if model["connector"] == "candidate"
    }
    target_mass = float(contract["cases"]["all_pairings_at_mass_msun"])
    selected_cases = [
        (pair_id, target_mass)
        for pair_id in sorted(
            {
                pair_id
                for pair_id, model_mass in registered_models
                if model_mass == target_mass
            }
        )
    ]
    selected_cases.extend(
        (
            case["pair_id"],
            float(case["target_mass_msun"]),
        )
        for case in contract["cases"]["edge_cases"]
    )
    if len(selected_cases) != int(contract["cases"]["expected_case_count"]):
        raise ValueError("cross-validation case count changed")

    radial_options = stellar_contract["solver"]
    enthalpy_options = contract["implementation_B"]
    tolerances = contract["relative_tolerances"]
    results: list[dict[str, object]] = []
    for pair_id, model_mass in selected_cases:
        outer_label, eft_label = pair_id.split("__", 1)
        registered = registered_models[(pair_id, model_mass)]
        eos = build_low_density_barotrope(
            outer_tables[outer_label],
            eft_tables[eft_label],
            template,
            connector_kind=stellar_contract["connectors"]["candidate"],
            connector_points=int(
                stellar_contract["connectors"][
                    "sampled_points_including_endpoints"
                ]
            ),
            core_cs2=float(
                stellar_contract["high_density_extension"]["cs2"]
            ),
            projection_tolerance=float(
                stellar_contract["connectors"][
                    "rounded_outer_endpoint_projection_tolerance"
                ]
            ),
        )
        central_pressure_mev = float(
            registered["central_pressure_mev_fm3"]
        )
        radial = solve_physical_star(
            eos,
            central_pressure_mev,
            maximum_step_km=float(radial_options["maximum_step_km"]),
            minimum_step_km=float(radial_options["minimum_step_km"]),
            pressure_step_fraction=float(
                radial_options["pressure_step_fraction"]
            ),
        )
        enthalpy = solve_star_enthalpy(
            eos,
            central_pressure_mev * MEV_FM3_TO_GEOMETRIC_KM2,
            relative_tolerance=float(
                enthalpy_options["relative_tolerance"]
            ),
            absolute_tolerance=float(
                enthalpy_options["absolute_tolerance"]
            ),
            maximum_enthalpy_step=float(
                enthalpy_options["maximum_enthalpy_step"]
            ),
            initial_enthalpy_offset=float(
                enthalpy_options["initial_enthalpy_offset"]
            ),
        )
        comparisons = {
            field: _relative_difference(
                getattr(radial, field),
                getattr(enthalpy, field),
            )
            for field in ("mass", "radius", "love_k2", "tidal_lambda")
        }
        checks = {
            field: comparisons[field] <= float(tolerances[field])
            for field in comparisons
        }
        registered_replay = {
            "radius": _relative_difference(
                radial.radius, registered["radius_km"]
            ),
            "love_k2": _relative_difference(
                radial.love_k2, registered["love_k2"]
            ),
            "tidal_lambda": _relative_difference(
                radial.tidal_lambda, registered["tidal_lambda"]
            ),
        }
        results.append(
            {
                "pair_id": pair_id,
                "target_mass_msun": model_mass,
                "central_pressure_mev_fm3": central_pressure_mev,
                "radial_RK4": asdict(radial),
                "enthalpy_DOP853": asdict(enthalpy),
                "relative_differences": comparisons,
                "registered_radial_replay_relative_differences": (
                    registered_replay
                ),
                "checks": checks,
                "all_checks_pass": all(checks.values()),
            }
        )
    maxima = {
        field: max(
            result["relative_differences"][field]
            for result in results
        )
        for field in ("mass", "radius", "love_k2", "tidal_lambda")
    }
    all_pass = all(result["all_checks_pass"] for result in results)
    decision = (
        "TOV_LOVE_CROSS_IMPLEMENTATION_AGREEMENT_PASSED"
        if all_pass
        else "TOV_LOVE_CROSS_IMPLEMENTATION_AGREEMENT_FAILED"
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.tov-love-cross-validation-result.v1",
        "validation_id": contract["validation_id"],
        "status": "DEVELOPMENT_NOT_CONFIRMATORY",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "source_stellar_contract_sha256": sha256_file(
            stellar_contract_path
        ),
        "source_stellar_results_sha256": sha256_file(
            stellar_results_path
        ),
        "pairing_contract_sha256": sha256_file(pairing_contract_path),
        "implementations": {
            "A": contract["implementation_A"],
            "B": contract["implementation_B"],
        },
        "cases": results,
        "case_count": len(results),
        "maximum_relative_differences": maxima,
        "all_cases_pass": all_pass,
        "decision": decision,
        "decision_scope": contract["decision_scope"],
        "remaining_nonvalidated_items": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "scipy": scipy.__version__,
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
    record = run_cross_validation(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
