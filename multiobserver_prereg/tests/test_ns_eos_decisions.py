from __future__ import annotations

import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_decisions import (
    decision_summary,
    load_and_validate_decisions,
)


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "ns_eos_v1_1" / "ns_eos_decisions_v0_3.yaml"


class NSEOSDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decisions = load_and_validate_decisions(DECISIONS)

    def test_all_six_domain_decisions_are_resolved(self):
        result = decision_summary(self.decisions)
        self.assertEqual(len(result["resolved"]), 6)
        self.assertFalse(result["confirmatory_authorization"])

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
