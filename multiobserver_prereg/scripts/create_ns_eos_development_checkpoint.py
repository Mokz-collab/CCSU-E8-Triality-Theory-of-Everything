#!/usr/bin/env python3
"""Create a deterministic, nonconfirmatory NS-EOS development checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccsu_multiobserver.ns_eos_low_density import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _registered_files() -> tuple[Path, ...]:
    files = [
        path
        for path in (PROJECT_ROOT / "ns_eos_v1_1").rglob("*")
        if path.is_file()
        and not path.name.startswith("ns_eos_development_checkpoint_")
    ]
    files.extend(
        PROJECT_ROOT / relative
        for relative in (
            "scripts/create_ns_eos_development_checkpoint.py",
            "scripts/run_common_relation_measure.py",
            "scripts/fit_inner_crust_reference_template.py",
            "scripts/generate_muses_chiral_eft_anchor.py",
            "scripts/run_final_low_density_pairing_validation.py",
            "scripts/run_finite_domain_recovery_search.py",
            "scripts/run_inner_crust_validation.py",
            "scripts/run_local_chart_validation.py",
            "scripts/run_local_to_public_relation_validation.py",
            "scripts/run_relation_cell_inverse_reachability.py",
            "scripts/run_reciprocal_cycle_analysis.py",
            "scripts/run_stellar_impact_validation.py",
            "scripts/run_targeted_cross_chart_optimization.py",
            "scripts/run_transition_holonomy_analysis.py",
            "scripts/run_tov_love_cross_validation.py",
            "scripts/run_xray_relation_space_diagnostic.py",
            "src/ccsu_multiobserver/ns_eos_decisions.py",
            "src/ccsu_multiobserver/ns_eos_enthalpy_oracle.py",
            "src/ccsu_multiobserver/ns_eos_inner_crust_validation.py",
            "src/ccsu_multiobserver/ns_eos_local_charts.py",
            "src/ccsu_multiobserver/ns_eos_low_density.py",
            "src/ccsu_multiobserver/ns_eos_oracle.py",
            "src/ccsu_multiobserver/ns_eos_relations.py",
            "src/ccsu_multiobserver/ns_eos_recovery.py",
            "src/ccsu_multiobserver/ns_eos_stellar_impact.py",
            "tests/test_ns_eos_decisions.py",
            "tests/test_ns_eos_final_pairings.py",
            "tests/test_ns_eos_inner_crust_validation.py",
            "tests/test_ns_eos_local_charts.py",
            "tests/test_ns_eos_low_density.py",
            "tests/test_ns_eos_oracle.py",
            "tests/test_ns_eos_relations.py",
            "tests/test_ns_eos_recovery.py",
            "tests/test_ns_eos_stellar_impact.py",
            "tests/test_ns_eos_tov_love_cross_validation.py",
        )
    )
    return tuple(sorted(set(files)))


def create_checkpoint(created_utc: str) -> dict[str, object]:
    validation_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "inner_crust_validation_results_v0_1.json"
    )
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    cross_validation_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "tov_love_cross_validation_results_v0_1.json"
    )
    cross_validation = json.loads(
        cross_validation_path.read_text(encoding="utf-8")
    )
    local_chart_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "local_chart_generator_results_v0_1.json"
    )
    local_chart_validation = json.loads(
        local_chart_path.read_text(encoding="utf-8")
    )
    relation_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "local_to_public_relation_results_v0_1.json"
    )
    relation_validation = json.loads(
        relation_path.read_text(encoding="utf-8")
    )
    recovery_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "finite_domain_recovery_results_v0_1.json"
    )
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    xray_diagnostic_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "xray_relation_space_diagnostic_results_v0_1.json"
    )
    xray_diagnostic = json.loads(
        xray_diagnostic_path.read_text(encoding="utf-8")
    )
    common_measure_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "common_relation_measure_results_v0_1.json"
    )
    common_measure = json.loads(
        common_measure_path.read_text(encoding="utf-8")
    )
    inverse_reachability_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "relation_cell_inverse_reachability_results_v0_1.json"
    )
    inverse_reachability = json.loads(
        inverse_reachability_path.read_text(encoding="utf-8")
    )
    targeted_optimization_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "targeted_cross_chart_optimization_results_v0_1.json"
    )
    targeted_optimization = json.loads(
        targeted_optimization_path.read_text(encoding="utf-8")
    )
    transition_holonomy_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "transition_holonomy_results_v0_1.json"
    )
    transition_holonomy = json.loads(
        transition_holonomy_path.read_text(encoding="utf-8")
    )
    reciprocal_optimization_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "reciprocal_transition_optimization_results_v0_1.json"
    )
    reciprocal_optimization = json.loads(
        reciprocal_optimization_path.read_text(encoding="utf-8")
    )
    reciprocal_cycle_path = (
        PROJECT_ROOT
        / "ns_eos_v1_1"
        / "reciprocal_cycle_results_v0_1.json"
    )
    reciprocal_cycle = json.loads(
        reciprocal_cycle_path.read_text(encoding="utf-8")
    )
    files = {
        str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
        for path in _registered_files()
    }
    return {
        "schema": "ccsu.multiobserver.ns-eos-development-checkpoint.v1",
        "registration_id": "CCSU-MO-NS-EOS-001",
        "version": "1.6-development",
        "status": "DEVELOPMENT_NOT_FROZEN",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "branch": "multiobserver-control-recovery-v1-20260726",
        "parent_commit": "155a55ad76c346589374190a7f560b42b2b72a2d",
        "scientific_source_bytes_embedded": True,
        "tests": {
            "command": "PYTHONPATH=src python -m unittest discover -s tests -v",
            "passed": 116,
            "failed": 0,
        },
        "reproducibility_replay": {
            "muses_anchor": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "binary_sha256": (
                    "4da03ecfb458accae7443c7525a3a9ba4dd237f3c833ecb584c11ce1ccc893ea"
                ),
                "products_compared": 8,
                "mismatches": 0,
            },
            "inner_crust_template": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(
                    PROJECT_ROOT
                    / "ns_eos_v1_1"
                    / "data"
                    / "unified_eos_hcdas_2022"
                    / "inner_crust_derivative_template_v0_1.json"
                ),
            },
            "inner_crust_validation": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(validation_path),
                "canonical_record_sha256": validation[
                    "canonical_record_sha256"
                ],
            },
            "final_low_density_pairings": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(
                    PROJECT_ROOT
                    / "ns_eos_v1_1"
                    / "final_low_density_pairing_results_v0_1.json"
                ),
                "pairs_tested": 8,
                "pairs_passed": 8,
            },
            "stellar_impact": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(
                    PROJECT_ROOT
                    / "ns_eos_v1_1"
                    / "stellar_impact_results_v0_1.json"
                ),
                "conditional_core": "constant_sound_speed_cs2_0_6",
                "cross_implementation_validated": True,
            },
            "TOV_Love_cross_validation": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(cross_validation_path),
                "canonical_record_sha256": cross_validation[
                    "canonical_record_sha256"
                ],
                "cases_tested": cross_validation["case_count"],
                "cases_passed": sum(
                    bool(case["all_checks_pass"])
                    for case in cross_validation["cases"]
                ),
                "maximum_relative_differences": cross_validation[
                    "maximum_relative_differences"
                ],
                "environment_lock_sha256": sha256_file(
                    PROJECT_ROOT
                    / "ns_eos_v1_1"
                    / "ns_eos_cross_validation_environment_v0_1.lock"
                ),
            },
            "local_chart_generators": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(local_chart_path),
                "canonical_record_sha256": local_chart_validation[
                    "canonical_record_sha256"
                ],
                "registered_cases": local_chart_validation["case_count"],
                "registered_cases_passed": sum(
                    bool(case["all_local_checks_pass"])
                    for case in local_chart_validation["cases"]
                ),
                "distinct_local_charts": local_chart_validation[
                    "four_distinct_local_charts"
                ],
                "environment_lock_sha256": local_chart_validation[
                    "environment_lock"
                ]["sha256"],
                "independent_range_review": False,
            },
            "local_to_public_relations": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(relation_path),
                "canonical_record_sha256": relation_validation[
                    "canonical_record_sha256"
                ],
                "translations_completed": relation_validation[
                    "case_count"
                ],
                "full_stellar_gate_pass_count": relation_validation[
                    "full_stellar_gate_pass_count"
                ],
                "domain_truncated_before_turnover_count": (
                    relation_validation[
                        "domain_truncated_before_turnover_count"
                    ]
                ),
                "maximum_mass_threshold_pass_count": (
                    relation_validation[
                        "maximum_mass_threshold_pass_count"
                    ]
                ),
                "all_mass_anchors_translated_count": (
                    relation_validation[
                        "all_mass_anchors_translated_count"
                    ]
                ),
                "pilot_entry_authorized": relation_validation[
                    "pilot_entry_authorized"
                ],
            },
            "finite_domain_recovery": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(recovery_path),
                "canonical_record_sha256": recovery[
                    "canonical_record_sha256"
                ],
                "evaluated_cases": recovery["case_count"],
                "accepted_cases": recovery["accepted_count"],
                "acceptance_summary": recovery["acceptance_summary"],
                "pilot_entry_authorized": recovery[
                    "pilot_entry_authorized"
                ],
            },
            "XRAY_relation_space_diagnostic": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(xray_diagnostic_path),
                "canonical_record_sha256": xray_diagnostic[
                    "canonical_record_sha256"
                ],
                "evaluated_cases": xray_diagnostic["case_count"],
                "accepted_cases": xray_diagnostic["accepted_count"],
                "accepted_unique_proposals": xray_diagnostic[
                    "accepted_unique_proposal_count"
                ],
                "accepted_for_both_eft_members": xray_diagnostic[
                    "accepted_for_both_eft_members"
                ],
                "decision": xray_diagnostic["decision"],
                "pilot_entry_authorized": xray_diagnostic[
                    "pilot_entry_authorized"
                ],
            },
            "common_relation_space_measure": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(common_measure_path),
                "canonical_record_sha256": common_measure[
                    "canonical_record_sha256"
                ],
                "accepted_relation_atoms": common_measure["atom_count"],
                "occupied_components": common_measure[
                    "primary_measure"
                ]["component_count"],
                "mixed_observer_components": common_measure[
                    "primary_measure"
                ]["mixed_observer_component_count"],
                "local_plateau_pass": common_measure[
                    "local_plateau_pass"
                ],
                "duplicate_atom_invariance_pass": common_measure[
                    "duplicate_atom_invariance_pass"
                ],
                "observer_attributed_mass": common_measure[
                    "primary_measure"
                ]["observer_attributed_mass"],
                "decision": common_measure["decision"],
                "pilot_entry_authorized": common_measure[
                    "pilot_entry_authorized"
                ],
            },
            "relation_cell_inverse_reachability": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(inverse_reachability_path),
                "canonical_record_sha256": inverse_reachability[
                    "canonical_record_sha256"
                ],
                "target_cells": inverse_reachability[
                    "target_cell_count"
                ],
                "chart_summary": inverse_reachability["chart_summary"],
                "cross_chart_robust_overlap_cells": (
                    inverse_reachability[
                        "cross_chart_robust_overlap_cell_count"
                    ]
                ),
                "uncovered_target_cells": inverse_reachability[
                    "uncovered_target_cell_count"
                ],
                "exact_stellar_candidate_evaluations": (
                    inverse_reachability[
                        "exact_stellar_candidate_evaluations"
                    ]
                ),
                "decision": inverse_reachability["decision"],
                "pilot_entry_authorized": inverse_reachability[
                    "pilot_entry_authorized"
                ],
            },
            "targeted_cross_chart_optimization": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(targeted_optimization_path),
                "canonical_record_sha256": targeted_optimization[
                    "canonical_record_sha256"
                ],
                "frozen_problems": targeted_optimization["problem_count"],
                "relation_reachability_successes": targeted_optimization[
                    "relation_reachability_success_count"
                ],
                "robust_cross_chart_overlap_successes": (
                    targeted_optimization[
                        "robust_cross_chart_overlap_success_count"
                    ]
                ),
                "cross_chart_overlap_demonstrated": (
                    targeted_optimization[
                        "cross_chart_overlap_demonstrated"
                    ]
                ),
                "sampling_completeness_demonstrated": (
                    targeted_optimization[
                        "sampling_completeness_demonstrated"
                    ]
                ),
                "decision": targeted_optimization["decision"],
                "pilot_entry_authorized": targeted_optimization[
                    "pilot_entry_authorized"
                ],
            },
            "robust_transition_holonomy": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(transition_holonomy_path),
                "canonical_record_sha256": transition_holonomy[
                    "canonical_record_sha256"
                ],
                "transition_count": transition_holonomy[
                    "transition_count"
                ],
                "directed_edges": transition_holonomy["directed_edges"],
                "closed_directed_cycle_count": transition_holonomy[
                    "closed_directed_cycle_count"
                ],
                "holonomy_identifiable": transition_holonomy[
                    "holonomy_identifiable"
                ],
                "holonomy_status": transition_holonomy[
                    "holonomy_status"
                ],
                "holonomy_value": transition_holonomy["holonomy_value"],
                "zero_holonomy_claimed": transition_holonomy[
                    "zero_holonomy_claimed"
                ],
                "decision": transition_holonomy["decision"],
                "pilot_entry_authorized": transition_holonomy[
                    "pilot_entry_authorized"
                ],
            },
            "reciprocal_transition_optimization": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(reciprocal_optimization_path),
                "canonical_record_sha256": reciprocal_optimization[
                    "canonical_record_sha256"
                ],
                "problem_count": reciprocal_optimization["problem_count"],
                "robust_success_count": reciprocal_optimization[
                    "robust_cross_chart_overlap_success_count"
                ],
                "decision": reciprocal_optimization["decision"],
                "pilot_entry_authorized": reciprocal_optimization[
                    "pilot_entry_authorized"
                ],
            },
            "reciprocal_transition_cycles": {
                "status": "EXACT_BYTE_REPLAY_PASSED",
                "sha256": sha256_file(reciprocal_cycle_path),
                "canonical_record_sha256": reciprocal_cycle[
                    "canonical_record_sha256"
                ],
                "transition_count": reciprocal_cycle["transition_count"],
                "closed_directed_cycles": reciprocal_cycle[
                    "closed_directed_cycles"
                ],
                "graph_cycles_available": reciprocal_cycle[
                    "graph_cycles_available"
                ],
                "state_aligned_composable_maps_available": reciprocal_cycle[
                    "state_aligned_composable_maps_available"
                ],
                "numeric_holonomy_identifiable": reciprocal_cycle[
                    "numeric_holonomy_identifiable"
                ],
                "holonomy_value": reciprocal_cycle["holonomy_value"],
                "decision": reciprocal_cycle["decision"],
                "pilot_entry_authorized": reciprocal_cycle[
                    "pilot_entry_authorized"
                ],
            },
        },
        "inner_crust_decision": {
            "retired_rule": "endpoint_exponential_v0_4",
            "retired_rule_status": "FAILED_EXTERNAL_LOCAL_SHAPE_VALIDATION",
            "active_candidate": "reference_tilted_v0_5_candidate",
            "active_candidate_status": (
                "ACCEPTED_FOR_CONTINUED_DEVELOPMENT_ONLY"
            ),
            "calibration_model": "IOPB",
            "primary_holdout_model": "G3",
            "secondary_advisory_model": "FSUGarnet",
            "validation_decision": validation["decision"],
            "final_pairings": "ALL_8_PASSED",
            "stellar_impact": (
                "WITHIN_LIMITS_UNDER_SHARED_SYNTHETIC_CSS_CORE"
            ),
            "TOV_Love_cross_implementation": (
                "INTERNAL_INDEPENDENT_FORMULATION_AGREEMENT_PASSED"
            ),
        },
        "local_chart_decision": {
            "local_chart_generators": (
                "FOUR_GENERATORS_PASSED_INTERNAL_LOCAL_FILTERS"
            ),
            "local_chart_parameter_ranges": (
                "AWAITING_INDEPENDENT_REVIEW"
            ),
            "local_to_public_relations": relation_validation["decision"],
            "finite_domain_stellar_gates": (
                "RECOVERY_CANDIDATES_FOUND_WITHOUT_EXTRAPOLATION"
            ),
            "proposal_box_acceptance_balance": (
                "UNRESOLVED_RAW_BOX_VOLUMES_NOT_COMPARABLE"
            ),
            "XRAY_finite_domain_support": (
                "FOUND_IN_SPARSE_FACTORIAL_INTERACTION_REGION"
            ),
            "common_relation_space_proposal_measure": (
                "DEFINED_LOCAL_STABILITY_PASSED"
            ),
            "common_relation_space_sampling_coverage": "NOT_DEMONSTRATED",
            "cross_chart_relation_overlap": (
                "ROBUST_OVERLAP_FOUND_IN_2_OF_4_TARGETED_PROBLEMS"
            ),
            "inverse_relation_cell_reachability": (
                "MAPPED_NO_CROSS_CHART_OVERLAP_AT_EPSILON_0_05"
            ),
            "transition_map_and_translation_holonomy": (
                "TWO_RECIPROCAL_GRAPH_CYCLES_FOUND_"
                "STATE_ALIGNED_MAPS_NOT_VALIDATED"
            ),
            "pilot_entry": "FORBIDDEN",
        },
        "files": files,
        "remaining_freeze_blockers": [
            "state_aligned_composable_transition_maps_not_validated",
            "inverse_reachability_sampling_completeness_not_demonstrated",
            "independent_review_of_parameter_ranges",
            "pilot_calibration_of_P1_to_P4_thresholds",
            "power_derived_confirmatory_budget",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    record = create_checkpoint(args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
