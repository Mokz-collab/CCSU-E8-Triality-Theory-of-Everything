from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "ns_eos_v1_1"
    / "final_low_density_pairing_contract_v0_1.yaml"
)
RESULTS = (
    ROOT
    / "ns_eos_v1_1"
    / "final_low_density_pairing_results_v0_1.json"
)


class NSEOSFinalPairingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = json.loads(RESULTS.read_text(encoding="utf-8"))

    def test_all_eight_registered_pairings_pass(self):
        self.assertEqual(self.results["pair_count"], 8)
        self.assertTrue(self.results["all_pairs_pass"])
        self.assertTrue(
            all(pair["all_checks_pass"] for pair in self.results["pairs"])
        )
        self.assertEqual(
            self.results["decision"],
            "ACCEPT_ALL_FINAL_LOW_DENSITY_PAIRINGS_FOR_STELLAR_IMPACT_TESTING",
        )

    def test_pairings_are_the_complete_outer_crust_eft_cross_product(self):
        pair_ids = {pair["pair_id"] for pair in self.results["pairs"]}
        expected = {
            f"{outer}__MUSES-N3LO-{eft}"
            for outer in ("DD-ME2", "DD-PC1", "DD-PCX", "ELMA")
            for eft in ("414", "450")
        }
        self.assertEqual(pair_ids, expected)

    def test_pairing_validation_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pairings.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "run_final_low_density_pairing_validation.py"
                    ),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-26T23:18:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
