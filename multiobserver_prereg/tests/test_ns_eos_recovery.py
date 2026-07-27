from __future__ import annotations

import json
import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    LocalChartEOS,
)
from ccsu_multiobserver.ns_eos_recovery import (
    centered_factorial_proposals,
    classify_screening_result,
    common_relation_projection,
    deterministic_sobol_proposals,
    summarize_acceptance,
)


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


if __name__ == "__main__":
    unittest.main()
