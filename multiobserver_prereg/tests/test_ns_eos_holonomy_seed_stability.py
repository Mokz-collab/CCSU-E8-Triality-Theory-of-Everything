from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = (
    ROOT
    / "ns_eos_v1_1"
    / "holonomy_seed_stability_results_v0_1.json"
)


class NSEOSHolonomySeedStabilityTests(unittest.TestCase):
    def test_frozen_descriptive_rule_fails_without_significance_claim(self):
        result = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.assertTrue(result["all_cycles_valid_under_frozen_gates"])
        self.assertEqual(result["replicate_count_per_condition"], 3)
        self.assertEqual(result["cross_exceeds_null_count"], 2)
        self.assertFalse(result["direction_consistent"])
        self.assertGreater(
            result["cross_summary"]["coefficient_of_variation"],
            result["descriptive_stability_rule"][
                "maximum_cross_coefficient_of_variation"
            ],
        )
        self.assertGreater(
            result["null_summary"]["coefficient_of_variation"],
            result["descriptive_stability_rule"][
                "maximum_null_coefficient_of_variation"
            ],
        )
        self.assertFalse(result["descriptive_seed_stability_pass"])
        self.assertEqual(
            result["decision"],
            "DESCRIPTIVE_SEED_STABILITY_FAILED",
        )
        self.assertFalse(result["statistical_significance_identifiable"])
        self.assertIsNone(result["p_value"])


if __name__ == "__main__":
    unittest.main()
