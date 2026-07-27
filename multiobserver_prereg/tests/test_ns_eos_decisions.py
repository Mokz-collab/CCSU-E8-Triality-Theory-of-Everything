from __future__ import annotations

import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_decisions import (
    decision_summary,
    load_and_validate_decisions,
)


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "ns_eos_v1_1" / "ns_eos_decisions_v0_11.yaml"
LEGACY_DECISIONS = ROOT / "ns_eos_v1_1" / "ns_eos_decisions_v0_10.yaml"


class NSEOSDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decisions = load_and_validate_decisions(DECISIONS)

    def test_all_six_domain_decisions_are_resolved(self):
        result = decision_summary(self.decisions)
        self.assertEqual(len(result["resolved"]), 6)
        self.assertFalse(result["confirmatory_authorization"])

    def test_previous_decision_checkpoint_remains_valid(self):
        previous = load_and_validate_decisions(LEGACY_DECISIONS)
        self.assertEqual(previous["version"], "0.10-development")

    def test_cross_implementation_blocker_is_closed_in_development_only(self):
        evidence = self.decisions["implementation_evidence"][
            "TOV_Love_cross_implementation"
        ]
        self.assertEqual(
            evidence["status"],
            "INTERNAL_INDEPENDENT_FORMULATION_AGREEMENT_PASSED",
        )
        self.assertTrue(evidence["all_registered_cases_passed"])
        self.assertFalse(evidence["independent_external_software_package"])
        self.assertNotIn(
            "TOV_and_Love_cross_implementation_agreement",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_four_local_generators_do_not_close_range_review(self):
        evidence = self.decisions["implementation_evidence"][
            "local_chart_generators"
        ]
        self.assertTrue(evidence["all_registered_cases_passed"])
        self.assertTrue(
            evidence["local_parameter_vector_averaging_forbidden"]
        )
        self.assertFalse(evidence["independent_parameter_range_review"])
        self.assertIn(
            "independent_review_of_parameter_ranges",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_failed_stellar_gates_forbid_pilot_entry(self):
        evidence = self.decisions["implementation_evidence"][
            "local_to_public_relations"
        ]
        self.assertEqual(evidence["numerical_translations_completed"], 8)
        self.assertEqual(evidence["full_stellar_gate_passed"], 0)
        self.assertFalse(evidence["constant_sound_speed_extension_used"])
        self.assertFalse(
            evidence["maximum_mass_invented_at_domain_boundary"]
        )
        self.assertFalse(evidence["pilot_entry_authorized"])
        self.assertNotIn(
            "finite_domain_stellar_gate_recovery_without_extrapolation",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_recovery_candidates_do_not_authorize_imbalanced_pilot(self):
        evidence = self.decisions["implementation_evidence"][
            "finite_domain_recovery_search"
        ]
        self.assertEqual(evidence["evaluated_cases"], 256)
        self.assertEqual(evidence["numerical_rejections"], 0)
        self.assertEqual(evidence["accepted_cases"]["XRAY"], 0)
        self.assertEqual(evidence["accepted_cases"]["NUCLEAR"], 60)
        self.assertFalse(
            evidence["accepted_volume_balance_demonstrated"]
        )
        self.assertFalse(evidence["pilot_entry_authorized"])
        self.assertNotIn(
            "finite_domain_acceptance_imbalance_and_XRAY_zero_acceptance",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_xray_support_closes_zero_acceptance_not_measure_blocker(self):
        evidence = self.decisions["implementation_evidence"][
            "XRAY_relation_space_diagnostic"
        ]
        self.assertEqual(evidence["evaluated_cases"], 512)
        self.assertEqual(evidence["accepted_unique_proposals"], 5)
        self.assertTrue(
            evidence["XRAY_finite_domain_support_demonstrated"]
        )
        self.assertFalse(
            evidence["equal_relation_space_coverage_demonstrated"]
        )
        self.assertFalse(evidence["pilot_entry_authorized"])
        self.assertNotIn(
            "common_relation_space_proposal_measure_not_defined",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_common_measure_closes_definition_not_coverage(self):
        evidence = self.decisions["implementation_evidence"][
            "common_relation_space_measure"
        ]
        self.assertEqual(evidence["accepted_relation_atoms"], 74)
        self.assertEqual(evidence["occupied_components"], 35)
        self.assertTrue(evidence["local_plateau_passed"])
        self.assertTrue(evidence["duplicate_atom_invariance_passed"])
        self.assertFalse(evidence["local_parameters_in_measure"])
        self.assertFalse(
            evidence["cross_observer_overlap_demonstrated"]
        )
        self.assertFalse(evidence["pilot_entry_authorized"])
        self.assertIn(
            "common_relation_space_sampling_coverage_and_"
            "cross_chart_overlap_not_demonstrated",
            self.decisions["remaining_freeze_blockers"],
        )

    def test_low_density_intervals_are_contiguous(self):
        low = self.decisions["low_density_matching"]
        self.assertEqual(
            low["outer_crust"]["density_nsat"][1],
            low["inner_crust"]["density_nsat"][0],
        )
        self.assertEqual(
            low["inner_crust"]["density_nsat"][1],
            low["nuclear_band"]["density_nsat"][0],
        )
        self.assertEqual(low["nuclear_band"]["density_nsat"][1], low["local_chart_start_nsat"])

    def test_bps_semantics_stop_at_neutron_drip(self):
        low = self.decisions["low_density_matching"]
        self.assertEqual(
            low["outer_crust"]["semantic_limit"],
            "BPS_label_ends_at_neutron_drip",
        )
        self.assertTrue(
            low["inner_crust"]["observer_specific_parameters_forbidden"]
        )

    def test_inner_crust_template_is_shared_and_nonprobabilistic(self):
        inner = self.decisions["low_density_matching"]["inner_crust"]
        self.assertEqual(
            inner["prescription"],
            "shared_reference_tilted_chemical_potential_connector",
        )
        self.assertEqual(inner["template_calibration_model"], "IOPB")
        self.assertEqual(inner["primary_holdout_model"], "G3")
        self.assertFalse(inner["template_probabilistic_prior"])
        self.assertEqual(inner["sampled_free_parameters"], 0)

    def test_outer_crust_is_a_paired_shared_nuisance(self):
        outer = self.decisions["low_density_matching"]["outer_crust"]
        self.assertEqual(
            set(outer["model_labels"]),
            {"DD-ME2", "DD-PC1", "DD-PCX", "ELMA"},
        )
        self.assertTrue(outer["same_model_for_all_arms_within_trajectory"])
        self.assertTrue(outer["observer_conditioned_selection_forbidden"])

    def test_chiral_eft_members_are_paired_without_coverage_claim(self):
        nuclear = self.decisions["low_density_matching"]["nuclear_band"]
        self.assertEqual(
            set(nuclear["model_labels"]),
            {"MUSES-N3LO-414", "MUSES-N3LO-450"},
        )
        self.assertTrue(nuclear["same_model_for_all_arms_within_trajectory"])
        self.assertTrue(nuclear["pointwise_envelope_sampling_forbidden"])
        self.assertIsNone(nuclear["probabilistic_coverage"])
        self.assertFalse(nuclear["formal_chiral_truncation_error"])

    def test_phase_transition_language_is_bounded(self):
        proxy = self.decisions["phase_transition_proxy"]
        self.assertTrue(proxy["not_claimed_as_unique_first_order_signature"])
        self.assertLess(proxy["softening"]["cs2_upper"], proxy["restiffening"]["cs2_lower"])

    def test_naive_pool_never_pools_raw_posteriors(self):
        roles = self.decisions["comparator_roles"]
        self.assertTrue(roles["raw_posterior_pooling_forbidden"])
        self.assertEqual(roles["P3_primary"], "HYBRID_vs_NAIVE_POOL")

    def test_budget_precedes_confirmatory_seeds(self):
        budget = self.decisions["trajectory_budget_rule"]
        self.assertTrue(budget["budget_chosen_before_confirmatory_seed_schedule"])
        self.assertGreaterEqual(budget["confirmatory_budget"]["minimum_power"], 0.90)


if __name__ == "__main__":
    unittest.main()
