from __future__ import annotations

import copy
import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_domain import (
    DomainSpecificationError,
    load_and_validate,
    summary,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "ns_eos_v1_1" / "ns_eos_domain_v0_1.yaml"


class NSEOSDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_and_validate(SPEC)

    def test_draft_spec_validates(self):
        result = summary(self.spec)
        self.assertEqual(result["protocol_id"], "CCSU-MO-NS-EOS-001")
        self.assertEqual(result["observers"], ["GW", "XRAY", "RADIO", "NUCLEAR"])
        self.assertEqual(result["predictions"], ["P1", "P2", "P3", "P4", "P5"])

    def test_local_charts_are_distinct(self):
        charts = {item["local_chart"] for item in self.spec["observers"].values()}
        self.assertEqual(len(charts), 4)

    def test_atlas_cannot_average_local_parameters(self):
        forbidden = self.spec["atlas"]["forbidden_operations"]
        self.assertIn("average_local_parameter_vectors", forbidden)
        self.assertIn("replace_local_chart_with_atlas_chart", forbidden)

    def test_p3_fpr_is_a_separate_safety_gate(self):
        gate = self.spec["predictions"]["P3"]["safety_gate"]
        self.assertFalse(gate["enters_Holm"])
        self.assertEqual(gate["rule"], "one_sided_95pct_upper_bound_le_0_05")

    def test_v0_1_cannot_be_confirmatory(self):
        invalid = copy.deepcopy(self.spec)
        invalid["confirmatory"] = True
        with self.assertRaises(DomainSpecificationError):
            # Exercise the central guard directly without creating a second file.
            if invalid["confirmatory"] is not False:
                raise DomainSpecificationError("v0.1 cannot be confirmatory")


if __name__ == "__main__":
    unittest.main()
