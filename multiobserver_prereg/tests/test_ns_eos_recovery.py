from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    LocalChartEOS,
)
from ccsu_multiobserver.ns_eos_recovery import (
    centered_factorial_proposals,
    classify_screening_result,
    common_relation_projection,
    deterministic_sobol_proposals,
    equal_component_measure,
    relation_components,
    relation_distance_matrix,
    relation_vector,
    select_paired_minimax_candidate,
    summarize_acceptance,
)
from scripts.run_transition_holonomy_analysis import directed_cycles


class NSEOSRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.results = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "finite_domain_recovery_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )

    def test_sobol_proposals_are_reproducible_and_inside_box(self):
        specification = CHART_SPECIFICATIONS["GW"]
        left = deterministic_sobol_proposals(
            specification, sample_power=5, seed=20260727
        )
        right = deterministic_sobol_proposals(
            specification, sample_power=5, seed=20260727
        )
        self.assertEqual(left, right)
        self.assertEqual(len(left), 32)
        for proposal in left:
            for name, bounds in zip(
                specification.parameter_names,
                specification.parameter_bounds,
                strict=True,
            ):
                self.assertGreaterEqual(proposal[name], bounds[0])
                self.assertLessEqual(proposal[name], bounds[1])

    def test_frozen_gate_classification(self):
        self.assertEqual(
            classify_screening_result(
                local_status="PASS",
                turnover=False,
                stable_mass_limit_msun=3.0,
            ),
            "NO_TURNOVER_INSIDE_6_NSAT",
        )
        self.assertEqual(
            classify_screening_result(
                local_status="PASS",
                turnover=True,
                stable_mass_limit_msun=2.1,
            ),
            "TURNOVER_BELOW_2_2_MSUN",
        )
        self.assertEqual(
            classify_screening_result(
                local_status="PASS",
                turnover=True,
                stable_mass_limit_msun=2.3,
                exact_gates_pass=True,
            ),
            "ACCEPTED",
        )

    def test_centered_factorial_stays_inside_original_xray_box(self):
        specification = CHART_SPECIFICATIONS["XRAY"]
        proposals = centered_factorial_proposals(
            specification,
            unit_levels=(0.125, 0.375, 0.625, 0.875),
        )
        self.assertEqual(len(proposals), 256)
        for proposal in proposals:
            for name, bounds in zip(
                specification.parameter_names,
                specification.parameter_bounds,
                strict=True,
            ):
                self.assertGreater(proposal[name], bounds[0])
                self.assertLess(proposal[name], bounds[1])

    def test_common_projection_uses_physical_relations_not_parameters(self):
        chart = LocalChartEOS(
            observer="TEST",
            chart="test",
            parameter_names=("hidden",),
            parameter_values=(99.0,),
            density_nsat=(1.1, 2.0, 3.0, 6.0),
            pressure_mev_fm3=(1.0, 4.0, 9.0, 36.0),
            energy_mev_fm3=(10.0, 20.0, 30.0, 60.0),
            chemical_potential_mev=(1.0, 1.0, 1.0, 1.0),
            sound_speed_squared=(0.1, 0.2, 0.3, 0.6),
        )
        projection = common_relation_projection(
            chart,
            (2.0, 3.0, 6.0),
        )
        self.assertNotIn("parameters", projection)
        self.assertEqual(
            projection["pressure_over_energy"],
            [0.2, 0.3, 0.6],
        )

    def test_relation_measure_is_invariant_to_same_provenance_duplicate(self):
        vectors = [
            relation_vector(
                {
                    "log10_pressure_mev_fm3": [1.0, 1.1],
                    "pressure_over_energy": [0.1, 0.2],
                    "sound_speed_squared": [0.2, 0.3],
                },
                log_pressure_scale_decades=1.0,
                pressure_over_energy_scale=1.0,
                sound_speed_squared_scale=1.0,
            ),
            relation_vector(
                {
                    "log10_pressure_mev_fm3": [2.0, 2.1],
                    "pressure_over_energy": [0.4, 0.5],
                    "sound_speed_squared": [0.6, 0.7],
                },
                log_pressure_scale_decades=1.0,
                pressure_over_energy_scale=1.0,
                sound_speed_squared_scale=1.0,
            ),
        ]
        atoms = [{"observer": "GW"}, {"observer": "XRAY"}]
        base = equal_component_measure(
            atoms,
            relation_distance_matrix(vectors),
            epsilon=0.05,
        )
        duplicated = equal_component_measure(
            atoms + [{"observer": "GW"}],
            relation_distance_matrix(vectors + [vectors[0]]),
            epsilon=0.05,
        )
        self.assertEqual(base["component_count"], 2)
        self.assertEqual(
            base["observer_attributed_mass"],
            duplicated["observer_attributed_mass"],
        )

    def test_relation_components_use_transitive_occupancy(self):
        distances = relation_distance_matrix(
            [
                np.asarray([0.00]),
                np.asarray([0.04]),
                np.asarray([0.08]),
                np.asarray([1.00]),
            ]
        )
        self.assertEqual(
            relation_components(distances, epsilon=0.05),
            ((0, 1, 2), (3,)),
        )

    def test_inverse_selection_minimizes_paired_worst_case_loss(self):
        result = select_paired_minimax_candidate(
            np.asarray([0.0, 0.0]),
            [
                {
                    "candidate_id": "asymmetric",
                    "member_vectors": [
                        np.asarray([0.0, 0.0]),
                        np.asarray([0.4, 0.0]),
                    ],
                },
                {
                    "candidate_id": "paired",
                    "member_vectors": [
                        np.asarray([0.2, 0.0]),
                        np.asarray([0.2, 0.0]),
                    ],
                },
            ],
        )
        self.assertEqual(result["candidate_id"], "paired")
        self.assertAlmostEqual(
            result["paired_worst_case_loss"],
            np.sqrt(0.02),
        )

    def test_zero_acceptance_is_reported_as_imbalance(self):
        cases = [
            {"observer": "GW", "outcome": "ACCEPTED"},
            {"observer": "GW", "outcome": "NO_TURNOVER_INSIDE_6_NSAT"},
            {"observer": "XRAY", "outcome": "NO_TURNOVER_INSIDE_6_NSAT"},
            {"observer": "XRAY", "outcome": "NO_TURNOVER_INSIDE_6_NSAT"},
        ]
        summary = summarize_acceptance(cases, ("GW", "XRAY"))
        self.assertIsNone(summary["max_to_min_acceptance_ratio"])
        self.assertEqual(summary["zero_acceptance_observers"], ["XRAY"])
        self.assertFalse(summary["balanced_acceptance_demonstrated"])

    def test_registered_recovery_result_is_imbalanced(self):
        self.assertEqual(self.results["case_count"], 256)
        self.assertEqual(self.results["accepted_count"], 65)
        per_observer = self.results["acceptance_summary"]["per_observer"]
        self.assertEqual(per_observer["GW"]["accepted"], 2)
        self.assertEqual(per_observer["XRAY"]["accepted"], 0)
        self.assertEqual(per_observer["RADIO"]["accepted"], 3)
        self.assertEqual(per_observer["NUCLEAR"]["accepted"], 60)
        self.assertFalse(
            self.results["acceptance_summary"][
                "balanced_acceptance_demonstrated"
            ]
        )
        self.assertFalse(self.results["pilot_entry_authorized"])

    def test_recovery_did_not_change_finite_domain_rules(self):
        rule = self.results["finite_domain_rule"]
        self.assertEqual(rule["maximum_density_nsat"], 6.0)
        self.assertTrue(rule["parameter_box_expansion_forbidden"])
        self.assertTrue(rule["pressure_extrapolation_forbidden"])
        self.assertTrue(rule["registered_stellar_gates_unchanged"])

    def test_registered_xray_factorial_finds_sparse_support(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "xray_relation_space_diagnostic_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["case_count"], 512)
        self.assertEqual(result["accepted_count"], 9)
        self.assertEqual(result["accepted_unique_proposal_count"], 5)
        self.assertEqual(result["accepted_for_both_eft_members"], 4)
        self.assertEqual(
            result["decision"],
            "XRAY_FINITE_DOMAIN_SUPPORT_FOUND_IN_SPARSE_INTERACTION_REGION",
        )
        self.assertFalse(result["pilot_entry_authorized"])

    def test_xray_acceptance_is_joint_not_gamma1_specific(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "xray_relation_space_diagnostic_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        accepted = [
            case for case in result["cases"]
            if case["outcome"] == "ACCEPTED"
        ]
        self.assertEqual(
            {case["unit_coordinates"]["log10_p1_cgs"] for case in accepted},
            {0.8750000000000008},
        )
        self.assertEqual(
            {case["unit_coordinates"]["gamma2"] for case in accepted},
            {0.625},
        )
        self.assertEqual(
            {case["unit_coordinates"]["gamma1"] for case in accepted},
            {0.125, 0.375, 0.625, 0.875},
        )

    def test_registered_common_measure_is_stable_but_not_coverage(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "common_relation_measure_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["atom_count"], 74)
        self.assertEqual(
            result["primary_measure"]["component_count"],
            35,
        )
        self.assertEqual(
            result["primary_measure"][
                "mixed_observer_component_count"
            ],
            0,
        )
        self.assertTrue(result["local_plateau_pass"])
        self.assertTrue(result["duplicate_atom_invariance_pass"])
        self.assertTrue(result["local_parameters_excluded"])
        self.assertFalse(result["cross_observer_overlap_demonstrated"])
        self.assertFalse(
            result["equal_relation_space_coverage_demonstrated"]
        )
        self.assertFalse(result["pilot_entry_authorized"])

    def test_registered_inverse_map_has_no_cross_chart_overlap(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "relation_cell_inverse_reachability_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["target_cell_count"], 35)
        self.assertEqual(
            result["cross_chart_robust_overlap_cell_count"],
            0,
        )
        self.assertEqual(result["uncovered_target_cell_count"], 1)
        self.assertFalse(result["cross_chart_overlap_demonstrated"])
        self.assertFalse(
            result["all_targets_have_robust_source_chart"]
        )
        self.assertFalse(
            result["local_parameter_vectors_in_public_matrix"]
        )
        self.assertFalse(result["pilot_entry_authorized"])

    def test_targeted_optimization_recovers_two_robust_overlaps(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "targeted_cross_chart_optimization_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["problem_count"], 4)
        self.assertEqual(result["relation_reachability_success_count"], 4)
        self.assertEqual(
            result["robust_cross_chart_overlap_success_count"], 2
        )
        self.assertTrue(result["cross_chart_overlap_demonstrated"])
        self.assertFalse(result["sampling_completeness_demonstrated"])
        self.assertFalse(result["local_parameter_vectors_in_public_record"])
        self.assertFalse(result["pilot_entry_authorized"])
        self.assertTrue(
            all(
                problem["local_parameters_in_public_record"] is False
                for problem in result["problems"]
            )
        )

    def test_directed_cycle_detection_does_not_invent_reverse_edges(self):
        self.assertEqual(
            directed_cycles(
                ("GW", "XRAY", "RADIO", "NUCLEAR"),
                (("NUCLEAR", "GW"), ("NUCLEAR", "RADIO")),
            ),
            (),
        )
        self.assertEqual(
            directed_cycles(
                ("GW", "NUCLEAR"),
                (("GW", "NUCLEAR"), ("NUCLEAR", "GW")),
            ),
            (("GW", "NUCLEAR"),),
        )

    def test_registered_transition_graph_makes_holonomy_unidentifiable(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "transition_holonomy_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result["transition_count"], 2)
        self.assertEqual(result["closed_directed_cycle_count"], 0)
        self.assertFalse(result["holonomy_identifiable"])
        self.assertEqual(
            result["holonomy_status"], "HOLONOMY_NOT_IDENTIFIABLE"
        )
        self.assertIsNone(result["holonomy_value"])
        self.assertFalse(result["zero_holonomy_claimed"])
        self.assertFalse(
            result["scalar_path_loss_interpreted_as_holonomy"]
        )

    def test_reciprocal_search_finds_cycles_not_numeric_holonomy(self):
        root = Path(__file__).resolve().parents[1]
        optimization = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "reciprocal_transition_optimization_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        cycle = json.loads(
            (
                root
                / "ns_eos_v1_1"
                / "reciprocal_cycle_results_v0_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            optimization["robust_cross_chart_overlap_success_count"], 2
        )
        self.assertEqual(cycle["closed_directed_cycle_count"], 2)
        self.assertTrue(cycle["graph_cycles_available"])
        self.assertFalse(
            cycle["state_aligned_composable_maps_available"]
        )
        self.assertFalse(cycle["numeric_holonomy_identifiable"])
        self.assertIsNone(cycle["holonomy_value"])
        self.assertFalse(cycle["zero_holonomy_claimed"])


if __name__ == "__main__":
    unittest.main()
