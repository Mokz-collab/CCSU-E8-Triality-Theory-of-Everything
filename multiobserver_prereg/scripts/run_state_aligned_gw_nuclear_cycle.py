#!/usr/bin/env python3
"""Evaluate a genuine state-aligned GW→NUCLEAR→GW translation cycle."""

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


def parameter_sha256(parameters: dict[str, float]) -> str:
    return hashlib.sha256(
        json.dumps(
            parameters, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def rms_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.sqrt(np.mean((left - right) ** 2)))


def solver_arguments(
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


def run_cycle(
    contract_path: Path,
    created_utc: str,
    seed_override: tuple[int, int] | None = None,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    recovery_path = (ns_root / contract["recovery_result"]).resolve()
    if sha256_file(recovery_path) != contract["recovery_result_sha256"]:
        raise ValueError("recovery result hash mismatch")
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    chart_contract = yaml.safe_load(
        (ns_root / contract["local_chart_contract"]).read_text(
            encoding="utf-8"
        )
    )
    low = contract["low_density"]
    outer = load_thermodynamic_table(
        ns_root / low["outer_crust_reference_manifest"]
    )
    template = load_derivative_template(
        ns_root / low["inner_crust_template"]
    )
    eft_tables = [
        load_thermodynamic_table(ns_root / path)
        for path in low["chiral_eft_anchors"]
    ]
    eft_labels = tuple(table.model_label for table in eft_tables)
    cycle = contract["cycle"]
    initial_chart = str(cycle["initial_chart"])
    intermediate_chart = str(cycle["intermediate_chart"])
    initial_cases = {
        case["case_id"]: case
        for case in recovery["cases"]
        if case["case_id"] in cycle["initial_state_case_ids"]
    }
    if set(initial_cases) != set(cycle["initial_state_case_ids"]):
        raise ValueError("initial GW state cases are incomplete")
    initial_parameters = dict(
        initial_cases[cycle["initial_state_case_ids"][0]]["parameters"]
    )
    if any(
        case["parameters"] != initial_parameters
        for case in initial_cases.values()
    ):
        raise ValueError("paired initial GW state does not share parameters")

    density_anchors = tuple(
        float(value)
        for value in contract["relation_space"]["density_anchors_nsat"]
    )
    scaling = contract["relation_space"]["scaling"]
    sample_count = int(chart_contract["sample_count"])
    optimizer = dict(contract["optimizer"])
    if seed_override is not None:
        optimizer["forward_seed"], optimizer["reverse_seed"] = seed_override
    target_masses = tuple(float(x) for x in contract["mass_anchors_msun"])
    exact_settings = contract["exact_stellar_solver"]

    def projections(
        chart_name: str,
        parameters: dict[str, float],
    ) -> tuple[list[dict[str, list[float]]], list[np.ndarray]]:
        public: list[dict[str, list[float]]] = []
        vectors: list[np.ndarray] = []
        for eft in eft_tables:
            chart = generate_local_chart(
                chart_name, parameters, eft.last, sample_count=sample_count
            )
            build_finite_domain_barotrope(
                outer,
                eft,
                template,
                chart,
                connector_points=int(low["connector_sample_count"]),
                projection_tolerance=float(
                    low["rounded_outer_mu_projection_tolerance"]
                ),
            )
            projection = common_relation_projection(chart, density_anchors)
            public.append(projection)
            vectors.append(
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
            )
        return public, vectors

    initial_public, initial_vectors = projections(
        initial_chart, initial_parameters
    )

    def optimize_leg(
        chart_name: str,
        start_parameters: dict[str, float],
        target_vectors: list[np.ndarray],
        seed: int,
    ) -> dict[str, object]:
        specification = CHART_SPECIFICATIONS[chart_name]
        names = specification.parameter_names
        bounds = list(specification.parameter_bounds)
        x0 = np.asarray([start_parameters[name] for name in names])
        evaluations = 0
        invalid = 0

        def evaluate(vector: np.ndarray) -> float:
            nonlocal evaluations, invalid
            evaluations += 1
            parameters = {
                name: float(value)
                for name, value in zip(names, vector, strict=True)
            }
            try:
                _, candidate_vectors = projections(chart_name, parameters)
            except (LocalChartError, RelationTranslationError, ValueError):
                invalid += 1
                return float(optimizer["invalid_proposal_penalty"])
            return max(
                rms_distance(candidate, target)
                for candidate, target in zip(
                    candidate_vectors, target_vectors, strict=True
                )
            )

        initial_loss = evaluate(x0)
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
        parameters = {
            name: float(value)
            for name, value in zip(names, optimized.x, strict=True)
        }
        public, vectors = projections(chart_name, parameters)
        member_losses = {
            label: rms_distance(candidate, target)
            for label, candidate, target in zip(
                eft_labels, vectors, target_vectors, strict=True
            )
        }
        stellar: dict[str, object] = {}
        for eft in eft_tables:
            chart = generate_local_chart(
                chart_name, parameters, eft.last, sample_count=sample_count
            )
            finite = build_finite_domain_barotrope(
                outer,
                eft,
                template,
                chart,
                connector_points=int(low["connector_sample_count"]),
                projection_tolerance=float(
                    low["rounded_outer_mu_projection_tolerance"]
                ),
            )
            exact = translate_stellar_relations(
                finite,
                anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                **solver_arguments(exact_settings, target_masses),
            )
            stellar[eft.model_label] = {
                "status": exact["status"],
                "all_stellar_gates_pass": exact[
                    "all_stellar_gates_pass"
                ],
                "maximum_mass_msun": exact["maximum_mass_msun"],
                "gates": exact["gates"],
            }
        return {
            "private_parameters": parameters,
            "public_projections": public,
            "vectors": vectors,
            "public_record": {
                "chart": chart_name,
                "parameter_sha256": parameter_sha256(parameters),
                "local_parameter_vector_in_public_record": False,
                "initial_paired_worst_case_loss": initial_loss,
                "optimized_member_losses": member_losses,
                "optimized_paired_worst_case_loss": max(
                    member_losses.values()
                ),
                "relation_reachable": max(member_losses.values())
                <= float(
                    contract["relation_space"][
                        "relation_threshold_epsilon"
                    ]
                ),
                "stellar_member_results": stellar,
                "robust_stellar_pass": all(
                    row["all_stellar_gates_pass"]
                    for row in stellar.values()
                ),
                "optimizer": {
                    "seed": seed,
                    "evaluations": evaluations,
                    "invalid_evaluations": invalid,
                    "reported_success": bool(optimized.success),
                    "message": str(optimized.message),
                    "generations_completed": int(optimized.nit),
                },
            },
        }

    order = tuple(str(x) for x in contract["observer_order"])
    sobol_seed = int(optimizer["inverse_bank_sobol_seed"])
    def frozen_start(chart_name: str, candidate_id: str) -> dict[str, float]:
        prefix = f"{chart_name}__SOBOL__"
        if not candidate_id.startswith(prefix):
            raise ValueError("cycle starts must be frozen Sobol candidates")
        index = int(candidate_id.removeprefix(prefix))
        return deterministic_sobol_proposals(
            CHART_SPECIFICATIONS[chart_name],
            sample_power=int(optimizer["inverse_bank_sobol_sample_power"]),
            seed=sobol_seed + order.index(chart_name),
        )[index]

    forward_start = frozen_start(
        intermediate_chart, cycle["forward_starting_candidate_id"]
    )
    reverse_start = frozen_start(
        initial_chart, cycle["reverse_starting_candidate_id"]
    )
    forward = optimize_leg(
        intermediate_chart,
        forward_start,
        initial_vectors,
        int(optimizer["forward_seed"]),
    )
    reverse = optimize_leg(
        initial_chart,
        reverse_start,
        forward["vectors"],
        int(optimizer["reverse_seed"]),
    )
    holonomy_by_member = {
        label: rms_distance(initial, returned)
        for label, initial, returned in zip(
            eft_labels,
            initial_vectors,
            reverse["vectors"],
            strict=True,
        )
    }
    holonomy = max(holonomy_by_member.values())
    forward_public = forward["public_record"]
    reverse_public = reverse["public_record"]
    cycle_valid = all(
        (
            forward_public["relation_reachable"],
            forward_public["robust_stellar_pass"],
            reverse_public["relation_reachable"],
            reverse_public["robust_stellar_pass"],
        )
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-state-aligned-cycle.v1",
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
        "initial_state": {
            "chart": initial_chart,
            "case_ids": cycle["initial_state_case_ids"],
            "parameter_sha256": parameter_sha256(initial_parameters),
            "local_parameter_vector_in_public_record": False,
            "paired_eft_members": list(eft_labels),
        },
        "forward_transition": forward_public,
        "reverse_transition": reverse_public,
        "reverse_target_is_actual_forward_output": True,
        "state_aligned_composition": True,
        "cycle_valid_under_frozen_gates": cycle_valid,
        "holonomy_definition": cycle["holonomy_definition"],
        "holonomy_by_eft_member": holonomy_by_member,
        "paired_worst_case_holonomy": holonomy,
        "holonomy_identifiable": cycle_valid,
        "zero_holonomy_claimed": False,
        "decision": (
            f"STATE_ALIGNED_{initial_chart}_{intermediate_chart}_"
            "HOLONOMY_MEASURED"
            if cycle_valid
            else "STATE_ALIGNED_CYCLE_FAILED_FROZEN_GATES"
        ),
        "finite_domain_rule": contract["finite_domain_rule"],
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
    record = run_cycle(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
