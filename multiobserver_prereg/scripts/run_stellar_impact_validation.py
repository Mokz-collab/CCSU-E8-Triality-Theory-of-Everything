#!/usr/bin/env python3
"""Quantify low-density connector impact under a shared synthetic CSS core."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_stellar_impact import (
    build_low_density_barotrope,
    fractional_spread,
    solve_target_masses,
)


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def run_stellar_impact(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    pairing_contract_path = (
        root / contract["pairing_contract"]
    ).resolve()
    pairing_contract = yaml.safe_load(
        pairing_contract_path.read_text(encoding="utf-8")
    )
    template_path = (root / contract["template"]).resolve()
    template = load_derivative_template(template_path)
    outer_tables = [
        load_thermodynamic_table((root / path).resolve())
        for path in pairing_contract["outer_crust_manifests"]
    ]
    eft_tables = [
        load_thermodynamic_table((root / path).resolve())
        for path in pairing_contract["chiral_eft_manifests"]
    ]
    solver = contract["solver"]
    common_solver_options = {
        "central_pressure_bounds_mev_fm3": tuple(
            solver["central_pressure_bounds_mev_fm3"]
        ),
        "scan_points": int(solver["stable_branch_scan_points"]),
        "mass_tolerance_msun": float(
            solver["target_mass_tolerance_msun"]
        ),
        "maximum_bisection_iterations": int(
            solver["maximum_bisection_iterations"]
        ),
        "maximum_step_km": float(solver["maximum_step_km"]),
        "minimum_step_km": float(solver["minimum_step_km"]),
        "pressure_step_fraction": float(
            solver["pressure_step_fraction"]
        ),
    }
    target_masses = tuple(float(value) for value in contract["target_masses_msun"])
    models: list[dict[str, object]] = []
    eos_cache: dict[tuple[str, str, str], object] = {}
    for outer in outer_tables:
        for eft in eft_tables:
            pair_id = f"{outer.model_label}__{eft.model_label}"
            for connector_label, connector_kind in contract[
                "connectors"
            ].items():
                if connector_label == "sampled_points_including_endpoints":
                    continue
                if connector_label == "rounded_outer_endpoint_projection_tolerance":
                    continue
                eos = build_low_density_barotrope(
                    outer,
                    eft,
                    template,
                    connector_kind=connector_kind,
                    connector_points=int(
                        contract["connectors"][
                            "sampled_points_including_endpoints"
                        ]
                    ),
                    core_cs2=float(
                        contract["high_density_extension"]["cs2"]
                    ),
                    projection_tolerance=float(
                        contract["connectors"][
                            "rounded_outer_endpoint_projection_tolerance"
                        ]
                    ),
                )
                eos_cache[(outer.model_label, eft.model_label, connector_label)] = eos
                solved = solve_target_masses(
                    eos,
                    target_masses,
                    **common_solver_options,
                )
                for model in solved:
                    models.append(
                        {
                            "pair_id": pair_id,
                            "outer_crust_model": outer.model_label,
                            "chiral_eft_model": eft.model_label,
                            "connector": connector_label,
                            **asdict(model),
                        }
                    )

    indexed = {
        (
            model["pair_id"],
            model["connector"],
            model["target_mass_msun"],
        ): model
        for model in models
    }
    connector_impacts: list[dict[str, object]] = []
    for outer in outer_tables:
        for eft in eft_tables:
            pair_id = f"{outer.model_label}__{eft.model_label}"
            for target_mass in target_masses:
                baseline = indexed[(pair_id, "baseline", target_mass)]
                candidate = indexed[(pair_id, "candidate", target_mass)]
                connector_impacts.append(
                    {
                        "pair_id": pair_id,
                        "target_mass_msun": target_mass,
                        "radius_absolute_difference_km": abs(
                            candidate["radius_km"] - baseline["radius_km"]
                        ),
                        "tidal_lambda_relative_difference": (
                            _relative_difference(
                                candidate["tidal_lambda"],
                                baseline["tidal_lambda"],
                            )
                        ),
                    }
                )

    outer_crust_spreads: list[dict[str, object]] = []
    for eft in eft_tables:
        for target_mass in target_masses:
            selected = [
                indexed[
                    (
                        f"{outer.model_label}__{eft.model_label}",
                        "candidate",
                        target_mass,
                    )
                ]
                for outer in outer_tables
            ]
            radii = [model["radius_km"] for model in selected]
            lambdas = [model["tidal_lambda"] for model in selected]
            outer_crust_spreads.append(
                {
                    "chiral_eft_model": eft.model_label,
                    "target_mass_msun": target_mass,
                    "radius_spread_km": max(radii) - min(radii),
                    "tidal_lambda_fractional_spread": fractional_spread(
                        lambdas
                    ),
                }
            )

    convergence = solver["convergence_check"]
    convergence_eos = eos_cache[
        ("DD-ME2", "MUSES-N3LO-414", "candidate")
    ]
    coarse = indexed[
        (
            convergence["pair_id"],
            convergence["connector"],
            float(convergence["target_mass_msun"]),
        )
    ]
    fine_options = dict(common_solver_options)
    fine_options["maximum_step_km"] = float(
        convergence["fine_maximum_step_km"]
    )
    fine = asdict(
        solve_target_masses(
            convergence_eos,
            (float(convergence["target_mass_msun"]),),
            **fine_options,
        )[0]
    )
    convergence_result = {
        "pair_id": convergence["pair_id"],
        "target_mass_msun": convergence["target_mass_msun"],
        "coarse_maximum_step_km": solver["maximum_step_km"],
        "fine_maximum_step_km": convergence["fine_maximum_step_km"],
        "radius_relative_difference": _relative_difference(
            coarse["radius_km"], fine["radius_km"]
        ),
        "tidal_lambda_relative_difference": _relative_difference(
            coarse["tidal_lambda"], fine["tidal_lambda"]
        ),
    }
    thresholds = contract["impact_thresholds"]
    threshold_results = {
        "candidate_vs_baseline_radius": max(
            item["radius_absolute_difference_km"]
            for item in connector_impacts
        )
        <= float(
            thresholds[
                "maximum_candidate_vs_baseline_radius_absolute_km"
            ]
        ),
        "candidate_vs_baseline_tidal": max(
            item["tidal_lambda_relative_difference"]
            for item in connector_impacts
        )
        <= float(
            thresholds[
                "maximum_candidate_vs_baseline_tidal_lambda_relative"
            ]
        ),
        "outer_crust_radius_spread": max(
            item["radius_spread_km"] for item in outer_crust_spreads
        )
        <= float(
            thresholds[
                "maximum_outer_crust_radius_spread_km_within_EFT_and_mass"
            ]
        ),
        "outer_crust_tidal_spread": max(
            item["tidal_lambda_fractional_spread"]
            for item in outer_crust_spreads
        )
        <= float(
            thresholds[
                "maximum_outer_crust_tidal_fractional_spread_within_EFT_and_mass"
            ]
        ),
        "target_mass_accuracy": max(
            abs(model["mass_msun"] - model["target_mass_msun"])
            for model in models
        )
        <= float(
            thresholds["maximum_target_mass_absolute_error_msun"]
        ),
        "radius_step_convergence": (
            convergence_result["radius_relative_difference"]
            <= float(
                convergence["maximum_radius_relative_difference"]
            )
        ),
        "tidal_step_convergence": (
            convergence_result["tidal_lambda_relative_difference"]
            <= float(
                convergence[
                    "maximum_tidal_lambda_relative_difference"
                ]
            )
        ),
    }
    decision = (
        "STELLAR_IMPACT_WITHIN_REGISTERED_DEVELOPMENT_LIMITS"
        if all(threshold_results.values())
        else "STELLAR_IMPACT_LIMIT_FAILED"
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.stellar-impact-result.v1",
        "validation_id": contract["validation_id"],
        "status": contract["status"],
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "pairing_contract": {
            "path": pairing_contract_path.name,
            "sha256": sha256_file(pairing_contract_path),
        },
        "template": {
            "path": str(template_path.relative_to(root)),
            "sha256": sha256_file(template_path),
        },
        "high_density_extension": contract["high_density_extension"],
        "models": models,
        "connector_impacts": connector_impacts,
        "outer_crust_spreads": outer_crust_spreads,
        "convergence": convergence_result,
        "threshold_results": threshold_results,
        "all_thresholds_pass": all(threshold_results.values()),
        "decision": decision,
        "decision_scope": contract["decision_scope"],
        "remaining_nonvalidated_items": contract["does_not_validate"],
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
    record = run_stellar_impact(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
