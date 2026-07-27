#!/usr/bin/env python3
"""Optimize the four frozen cross-chart near misses inside existing boxes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
import yaml
from scipy.optimize import differential_evolution

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    LocalChartError,
    generate_local_chart,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_recovery import (
    common_relation_projection,
    deterministic_sobol_proposals,
    relation_vector,
)
from ccsu_multiobserver.ns_eos_relations import (
    RelationTranslationError,
    build_finite_domain_barotrope,
    translate_stellar_relations,
)


def _parameter_sha256(parameters: dict[str, float]) -> str:
    return hashlib.sha256(
        json.dumps(
            parameters,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _solver_arguments(
    settings: dict[str, object],
    target_masses: tuple[float, ...],
) -> dict[str, object]:
    return {
        "target_masses_msun": target_masses,
        "scan_points": int(settings["logarithmic_scan_points"]),
        "target_mass_tolerance_msun": float(
            settings["target_mass_tolerance_msun"]
        ),
        "maximum_bisection_iterations": int(
            settings["maximum_bisection_iterations"]
        ),
        "maximum_step_km": float(settings["maximum_step_km"]),
        "minimum_step_km": float(settings["minimum_step_km"]),
        "pressure_step_fraction": float(
            settings["pressure_step_fraction"]
        ),
        "turnover_mass_drop_tolerance_msun": float(
            settings["turnover_mass_drop_tolerance_msun"]
        ),
    }


def run_optimization(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    chart_contract_path = (
        ns_root / contract["local_chart_contract"]
    ).resolve()
    measure_path = (ns_root / contract["common_measure_result"]).resolve()
    inverse_path = (
        ns_root / contract["inverse_reachability_result"]
    ).resolve()
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    measure = json.loads(measure_path.read_text(encoding="utf-8"))
    inverse = json.loads(inverse_path.read_text(encoding="utf-8"))
    low = contract["low_density"]
    outer_path = (
        ns_root / low["outer_crust_reference_manifest"]
    ).resolve()
    template_path = (ns_root / low["inner_crust_template"]).resolve()
    outer = load_thermodynamic_table(outer_path)
    template = load_derivative_template(template_path)
    eft_tables = [
        load_thermodynamic_table((ns_root / relative).resolve())
        for relative in low["chiral_eft_anchors"]
    ]
    density_anchors = tuple(
        float(value)
        for value in contract["relation_space"]["density_anchors_nsat"]
    )
    scaling = contract["relation_space"]["scaling"]
    reachability_epsilon = float(
        contract["success_rule"]["relation_reachability_epsilon"]
    )
    target_masses = tuple(
        float(value) for value in contract["mass_anchors_msun"]
    )
    exact_solver = contract["exact_stellar_solver"]
    optimizer = contract["optimizer"]
    observer_order = tuple(str(value) for value in contract["observer_order"])
    inverse_targets = {
        int(row["target_component_index"]): row
        for row in inverse["target_cells"]
    }
    measure_components = {
        int(row["component_index"]): row
        for row in measure["primary_measure"]["components"]
    }

    results: list[dict[str, object]] = []
    for problem_index, problem in enumerate(contract["problems"]):
        target_index = int(problem["target_component_index"])
        target_chart = str(problem["target_chart"])
        source_chart = str(problem["source_chart"])
        specification = CHART_SPECIFICATIONS[target_chart]
        component = measure_components[target_index]
        medoid_atom = measure["atoms"][int(component["medoid_atom_index"])]
        target_vector = relation_vector(
            medoid_atom["relation_projection"],
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
        starting_candidate_id = str(problem["starting_candidate_id"])
        prefix = f"{target_chart}__SOBOL__"
        if not starting_candidate_id.startswith(prefix):
            raise ValueError("targeted start must be a Sobol bank candidate")
        starting_index = int(starting_candidate_id.removeprefix(prefix))
        chart_seed = int(optimizer["inverse_bank_sobol_seed"]) + (
            observer_order.index(target_chart)
        )
        starting_parameters = deterministic_sobol_proposals(
            specification,
            sample_power=int(
                optimizer["inverse_bank_sobol_sample_power"]
            ),
            seed=chart_seed,
        )[starting_index]
        x0 = np.asarray(
            [
                starting_parameters[name]
                for name in specification.parameter_names
            ],
            dtype=float,
        )
        bounds = list(specification.parameter_bounds)
        evaluation_count = 0
        invalid_evaluation_count = 0
        best_seen_loss = float("inf")
        best_seen_member_losses: list[float] | None = None
        best_seen_projections: list[dict[str, list[float]]] | None = None

        def evaluate(vector: np.ndarray) -> float:
            nonlocal evaluation_count
            nonlocal invalid_evaluation_count
            nonlocal best_seen_loss
            nonlocal best_seen_member_losses
            nonlocal best_seen_projections
            evaluation_count += 1
            parameters = {
                name: float(value)
                for name, value in zip(
                    specification.parameter_names,
                    vector,
                    strict=True,
                )
            }
            losses: list[float] = []
            projections: list[dict[str, list[float]]] = []
            try:
                for eft in eft_tables:
                    chart = generate_local_chart(
                        target_chart,
                        parameters,
                        eft.last,
                        sample_count=int(chart_contract["sample_count"]),
                    )
                    build_finite_domain_barotrope(
                        outer,
                        eft,
                        template,
                        chart,
                        connector_points=int(
                            low["connector_sample_count"]
                        ),
                        projection_tolerance=float(
                            low[
                                "rounded_outer_mu_projection_tolerance"
                            ]
                        ),
                    )
                    projection = common_relation_projection(
                        chart,
                        density_anchors,
                    )
                    candidate_vector = relation_vector(
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
                    losses.append(
                        float(
                            np.sqrt(
                                np.mean(
                                    (candidate_vector - target_vector) ** 2
                                )
                            )
                        )
                    )
                    projections.append(projection)
            except (LocalChartError, RelationTranslationError):
                invalid_evaluation_count += 1
                return float(optimizer["invalid_proposal_penalty"])
            worst = max(losses)
            if worst < best_seen_loss:
                best_seen_loss = worst
                best_seen_member_losses = losses
                best_seen_projections = projections
            return worst

        initial_loss = evaluate(x0)
        seed = int(optimizer["base_seed"]) + problem_index
        optimized = differential_evolution(
            evaluate,
            bounds,
            strategy=str(optimizer["strategy"]),
            maxiter=int(optimizer["maximum_generations"]),
            popsize=int(optimizer["population_multiplier"]),
            tol=float(optimizer["relative_tolerance"]),
            atol=float(optimizer["absolute_tolerance"]),
            mutation=tuple(float(x) for x in optimizer["mutation"]),
            recombination=float(optimizer["recombination"]),
            seed=seed,
            polish=False,
            init="sobol",
            updating="immediate",
            workers=1,
            x0=x0,
        )
        final_parameters = {
            name: float(value)
            for name, value in zip(
                specification.parameter_names,
                optimized.x,
                strict=True,
            )
        }
        final_loss = evaluate(np.asarray(optimized.x, dtype=float))
        relation_reachable = final_loss <= reachability_epsilon
        exact_results: dict[str, object] = {}
        robust_overlap = False
        if relation_reachable:
            for eft in eft_tables:
                try:
                    chart = generate_local_chart(
                        target_chart,
                        final_parameters,
                        eft.last,
                        sample_count=int(chart_contract["sample_count"]),
                    )
                    finite_eos = build_finite_domain_barotrope(
                        outer,
                        eft,
                        template,
                        chart,
                        connector_points=int(
                            low["connector_sample_count"]
                        ),
                        projection_tolerance=float(
                            low[
                                "rounded_outer_mu_projection_tolerance"
                            ]
                        ),
                    )
                    exact = translate_stellar_relations(
                        finite_eos,
                        anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                        **_solver_arguments(exact_solver, target_masses),
                    )
                    exact_results[eft.model_label] = {
                        "status": exact["status"],
                        "all_stellar_gates_pass": exact[
                            "all_stellar_gates_pass"
                        ],
                        "gates": exact["gates"],
                        "maximum_mass_msun": exact["maximum_mass_msun"],
                    }
                except (
                    ValueError,
                    RuntimeError,
                    FloatingPointError,
                ) as error:
                    exact_results[eft.model_label] = {
                        "status": "NUMERICAL_REJECTION",
                        "error_type": type(error).__name__,
                        "all_stellar_gates_pass": False,
                    }
            robust_overlap = all(
                bool(row["all_stellar_gates_pass"])
                for row in exact_results.values()
            )
        normalized_movement = [
            abs(float(value) - float(start))
            / (upper - lower)
            for value, start, (lower, upper) in zip(
                optimized.x,
                x0,
                bounds,
                strict=True,
            )
        ]
        results.append(
            {
                "problem_id": problem["problem_id"],
                "target_component_index": target_index,
                "source_chart": source_chart,
                "target_chart": target_chart,
                "target_medoid_atom_id": medoid_atom["atom_id"],
                "starting_candidate_id": starting_candidate_id,
                "starting_parameter_sha256": _parameter_sha256(
                    starting_parameters
                ),
                "optimized_parameter_sha256": _parameter_sha256(
                    final_parameters
                ),
                "local_parameters_in_public_record": False,
                "initial_paired_worst_case_loss": initial_loss,
                "optimized_paired_worst_case_loss": final_loss,
                "optimized_member_losses": dict(
                    zip(
                        [eft.model_label for eft in eft_tables],
                        best_seen_member_losses or [],
                        strict=True,
                    )
                ),
                "loss_improvement": initial_loss - final_loss,
                "maximum_normalized_parameter_movement": max(
                    normalized_movement
                ),
                "relation_reachable": relation_reachable,
                "exact_stellar_status": (
                    "NOT_RUN_RELATION_UNREACHABLE"
                    if not relation_reachable
                    else (
                        "PASS_BOTH_EFT_MEMBERS"
                        if robust_overlap
                        else "FAILED_ONE_OR_BOTH_EFT_MEMBERS"
                    )
                ),
                "exact_stellar_member_results": exact_results,
                "robust_cross_chart_overlap": robust_overlap,
                "optimizer": {
                    "seed": seed,
                    "evaluations": evaluation_count,
                    "invalid_evaluations": invalid_evaluation_count,
                    "reported_success": bool(optimized.success),
                    "message": str(optimized.message),
                    "generations_completed": int(optimized.nit),
                },
            }
        )

    relation_successes = sum(
        result["relation_reachable"] for result in results
    )
    robust_successes = sum(
        result["robust_cross_chart_overlap"] for result in results
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-targeted-overlap.v1",
        "optimization_id": contract["optimization_id"],
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
            "common_measure_result_sha256": sha256_file(measure_path),
            "inverse_reachability_result_sha256": sha256_file(
                inverse_path
            ),
            "local_chart_contract_sha256": sha256_file(
                chart_contract_path
            ),
        },
        "finite_domain_rule": contract["finite_domain_rule"],
        "relation_space": contract["relation_space"],
        "optimizer_contract": optimizer,
        "problems": results,
        "problem_count": len(results),
        "relation_reachability_success_count": relation_successes,
        "robust_cross_chart_overlap_success_count": robust_successes,
        "cross_chart_overlap_demonstrated": robust_successes > 0,
        "sampling_completeness_demonstrated": False,
        "local_parameter_vectors_in_public_record": False,
        "decision": (
            "TARGETED_OPTIMIZATION_"
            + (
                "FOUND_ROBUST_CROSS_CHART_OVERLAP"
                if robust_successes > 0
                else (
                    "FOUND_RELATION_OVERLAP_BUT_STELLAR_GATES_FAILED"
                    if relation_successes > 0
                    else "DID_NOT_CROSS_RELATION_THRESHOLD"
                )
            )
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
    record = run_optimization(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
