#!/usr/bin/env python3
"""Map common relation cells back to each local EOS chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import scipy
import yaml

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
    select_paired_minimax_candidate,
)
from ccsu_multiobserver.ns_eos_relations import (
    RelationTranslationError,
    build_finite_domain_barotrope,
    translate_stellar_relations,
)


def _parameter_sha256(parameters: dict[str, float]) -> str:
    payload = json.dumps(
        parameters,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parameter_key(
    observer: str,
    parameters: dict[str, float],
) -> tuple[float, ...]:
    return tuple(
        float(parameters[name])
        for name in CHART_SPECIFICATIONS[observer].parameter_names
    )


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


def run_inverse_reachability(
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
    recovery_path = (ns_root / contract["recovery_result"]).resolve()
    xray_path = (ns_root / contract["xray_diagnostic_result"]).resolve()
    measure_path = (ns_root / contract["common_measure_result"]).resolve()
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    xray = json.loads(xray_path.read_text(encoding="utf-8"))
    measure = json.loads(measure_path.read_text(encoding="utf-8"))
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
    observer_order = tuple(str(value) for value in contract["observer_order"])

    accepted_seeds: dict[
        str, dict[tuple[float, ...], dict[str, object]]
    ] = {observer: {} for observer in observer_order}
    for case in recovery["cases"]:
        if case["outcome"] != "ACCEPTED":
            continue
        observer = str(case["observer"])
        key = _parameter_key(observer, case["parameters"])
        accepted_seeds[observer].setdefault(
            key,
            {
                "parameters": case["parameters"],
                "source_case_ids": [],
            },
        )["source_case_ids"].append(case["case_id"])
    for case in xray["cases"]:
        if case["outcome"] != "ACCEPTED":
            continue
        key = _parameter_key("XRAY", case["parameters"])
        accepted_seeds["XRAY"].setdefault(
            key,
            {
                "parameters": case["parameters"],
                "source_case_ids": [],
            },
        )["source_case_ids"].append(case["case_id"])

    bank_design = contract["inverse_bank"]
    sample_power = int(bank_design["sobol_sample_power_per_chart"])
    base_seed = int(bank_design["sobol_seed"])
    banks: dict[str, list[dict[str, object]]] = {}
    private_parameters: dict[tuple[str, str], dict[str, float]] = {}
    bank_summaries: dict[str, dict[str, object]] = {}
    for observer_index, observer in enumerate(observer_order):
        specification = CHART_SPECIFICATIONS[observer]
        raw_candidates: list[dict[str, object]] = []
        seen: set[tuple[float, ...]] = set()
        for seed_index, (key, seed_record) in enumerate(
            sorted(accepted_seeds[observer].items())
        ):
            parameters = dict(seed_record["parameters"])
            identifier = f"{observer}__PUBLIC_SEED__{seed_index:04d}"
            raw_candidates.append(
                {
                    "candidate_id": identifier,
                    "parameters": parameters,
                    "source": "PUBLIC_ACCEPTED_SEED",
                    "source_case_ids": sorted(
                        seed_record["source_case_ids"]
                    ),
                }
            )
            seen.add(key)
        sobol = deterministic_sobol_proposals(
            specification,
            sample_power=sample_power,
            seed=base_seed + observer_index,
        )
        for proposal_index, parameters in enumerate(sobol):
            key = _parameter_key(observer, parameters)
            if key in seen:
                continue
            raw_candidates.append(
                {
                    "candidate_id": (
                        f"{observer}__SOBOL__{proposal_index:04d}"
                    ),
                    "parameters": parameters,
                    "source": "SOBOL_INVERSE_BANK",
                    "source_case_ids": [],
                }
            )
            seen.add(key)

        paired_candidates: list[dict[str, object]] = []
        rejection_types: Counter[str] = Counter()
        for raw in raw_candidates:
            member_vectors: list[list[float]] = []
            member_projections: list[dict[str, list[float]]] = []
            rejected = False
            for eft in eft_tables:
                try:
                    chart = generate_local_chart(
                        observer,
                        raw["parameters"],
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
                    vector = relation_vector(
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
                    member_vectors.append(vector.tolist())
                    member_projections.append(projection)
                except (LocalChartError, RelationTranslationError) as error:
                    rejection_types[type(error).__name__] += 1
                    rejected = True
                    break
            if rejected:
                continue
            identifier = str(raw["candidate_id"])
            private_parameters[(observer, identifier)] = dict(
                raw["parameters"]
            )
            paired_candidates.append(
                {
                    "candidate_id": identifier,
                    "parameter_sha256": _parameter_sha256(
                        raw["parameters"]
                    ),
                    "source": raw["source"],
                    "source_case_ids": raw["source_case_ids"],
                    "member_vectors": member_vectors,
                    "member_projections": member_projections,
                    "local_parameters_in_public_record": False,
                }
            )
        if not paired_candidates:
            raise RuntimeError(f"inverse bank is empty for {observer}")
        banks[observer] = paired_candidates
        bank_summaries[observer] = {
            "raw_candidates": len(raw_candidates),
            "public_seed_candidates": len(accepted_seeds[observer]),
            "paired_local_pass_candidates": len(paired_candidates),
            "paired_local_rejections": (
                len(raw_candidates) - len(paired_candidates)
            ),
            "rejection_types": dict(sorted(rejection_types.items())),
        }

    measure_atoms = measure["atoms"]
    target_components = measure["primary_measure"]["components"]
    target_rows: list[dict[str, object]] = []
    exact_cache: dict[tuple[str, str], dict[str, object]] = {}
    exact_solver = contract["exact_stellar_solver"]
    target_masses = tuple(
        float(value) for value in contract["mass_anchors_msun"]
    )
    reachability_epsilon = float(
        contract["inverse_selection"]["relation_reachability_epsilon"]
    )
    for component in target_components:
        medoid_index = int(component["medoid_atom_index"])
        medoid_atom = measure_atoms[medoid_index]
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
        chart_rows: dict[str, dict[str, object]] = {}
        for observer in observer_order:
            selected = select_paired_minimax_candidate(
                target_vector,
                banks[observer],
            )
            candidate = next(
                row
                for row in banks[observer]
                if row["candidate_id"] == selected["candidate_id"]
            )
            relation_reachable = (
                float(selected["paired_worst_case_loss"])
                <= reachability_epsilon
            )
            row: dict[str, object] = {
                "candidate_id": candidate["candidate_id"],
                "parameter_sha256": candidate["parameter_sha256"],
                "candidate_source": candidate["source"],
                "source_case_ids": candidate["source_case_ids"],
                "paired_worst_case_translation_loss": selected[
                    "paired_worst_case_loss"
                ],
                "member_translation_losses": dict(
                    zip(
                        [eft.model_label for eft in eft_tables],
                        selected["member_losses"],
                        strict=True,
                    )
                ),
                "relation_reachable": relation_reachable,
                "stellar_exact_status": (
                    "NOT_RUN_RELATION_UNREACHABLE"
                    if not relation_reachable
                    else "NOT_RUN"
                ),
                "robust_reachable": False,
                "local_parameters_in_public_record": False,
            }
            if relation_reachable:
                cache_key = (observer, str(candidate["candidate_id"]))
                if cache_key not in exact_cache:
                    member_results: dict[str, object] = {}
                    for eft in eft_tables:
                        try:
                            parameters = private_parameters[cache_key]
                            chart = generate_local_chart(
                                observer,
                                parameters,
                                eft.last,
                                sample_count=int(
                                    chart_contract["sample_count"]
                                ),
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
                                anchor_pressure_mev_fm3=(
                                    eft.last.p_mev_fm3
                                ),
                                **_solver_arguments(
                                    exact_solver,
                                    target_masses,
                                ),
                            )
                            member_results[eft.model_label] = {
                                "status": exact["status"],
                                "all_stellar_gates_pass": exact[
                                    "all_stellar_gates_pass"
                                ],
                                "gates": exact["gates"],
                                "maximum_mass_msun": exact[
                                    "maximum_mass_msun"
                                ],
                            }
                        except (
                            ValueError,
                            RuntimeError,
                            FloatingPointError,
                        ) as error:
                            member_results[eft.model_label] = {
                                "status": "NUMERICAL_REJECTION",
                                "error_type": type(error).__name__,
                                "all_stellar_gates_pass": False,
                            }
                    exact_cache[cache_key] = member_results
                member_results = exact_cache[cache_key]
                robust = all(
                    bool(result["all_stellar_gates_pass"])
                    for result in member_results.values()
                )
                row["stellar_exact_status"] = (
                    "PASS_BOTH_EFT_MEMBERS"
                    if robust
                    else "FAILED_ONE_OR_BOTH_EFT_MEMBERS"
                )
                row["stellar_member_results"] = member_results
                row["robust_reachable"] = robust
            chart_rows[observer] = row
        robust_observers = [
            observer
            for observer, row in chart_rows.items()
            if row["robust_reachable"]
        ]
        target_rows.append(
            {
                "target_component_index": component["component_index"],
                "target_medoid_atom_id": medoid_atom["atom_id"],
                "target_source_observer": medoid_atom["observer"],
                "target_component_observers": component["observers"],
                "chart_reachability": chart_rows,
                "robust_reachable_observers": robust_observers,
                "robust_reachable_observer_count": len(robust_observers),
                "cross_chart_robust_overlap": len(robust_observers) >= 2,
            }
        )

    chart_summary: dict[str, dict[str, object]] = {}
    for observer in observer_order:
        relation_count = sum(
            bool(target["chart_reachability"][observer][
                "relation_reachable"
            ])
            for target in target_rows
        )
        robust_count = sum(
            bool(target["chart_reachability"][observer][
                "robust_reachable"
            ])
            for target in target_rows
        )
        losses = [
            float(target["chart_reachability"][observer][
                "paired_worst_case_translation_loss"
            ])
            for target in target_rows
        ]
        chart_summary[observer] = {
            "target_count": len(target_rows),
            "relation_reachable_targets": relation_count,
            "robust_reachable_targets": robust_count,
            "median_paired_worst_case_translation_loss": float(
                np.median(losses)
            ),
            "maximum_paired_worst_case_translation_loss": max(losses),
        }
    shared_count = sum(
        target["cross_chart_robust_overlap"] for target in target_rows
    )
    uncovered_count = sum(
        target["robust_reachable_observer_count"] == 0
        for target in target_rows
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-inverse-reachability.v1",
        "diagnostic_id": contract["diagnostic_id"],
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
            "recovery_result_sha256": sha256_file(recovery_path),
            "xray_diagnostic_result_sha256": sha256_file(xray_path),
            "common_measure_result_sha256": sha256_file(measure_path),
            "local_chart_contract_sha256": sha256_file(
                chart_contract_path
            ),
        },
        "finite_domain_rule": contract["finite_domain_rule"],
        "relation_space": contract["relation_space"],
        "inverse_bank_design": bank_design,
        "inverse_selection": contract["inverse_selection"],
        "bank_summaries": bank_summaries,
        "target_cells": target_rows,
        "target_cell_count": len(target_rows),
        "chart_summary": chart_summary,
        "cross_chart_robust_overlap_cell_count": shared_count,
        "uncovered_target_cell_count": uncovered_count,
        "cross_chart_overlap_demonstrated": shared_count > 0,
        "all_targets_have_robust_source_chart": uncovered_count == 0,
        "local_parameter_vectors_in_public_matrix": False,
        "exact_stellar_candidate_evaluations": len(exact_cache),
        "decision": (
            "INVERSE_RELATION_CELL_REACHABILITY_MAPPED_"
            + (
                "CROSS_CHART_OVERLAP_FOUND"
                if shared_count > 0
                else "NO_CROSS_CHART_OVERLAP_AT_REGISTERED_RESOLUTION"
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
    record = run_inverse_reachability(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
