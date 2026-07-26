from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_enthalpy_oracle import EnthalpyBarotrope
from ccsu_multiobserver.ns_eos_stellar_impact import (
    MEV_FM3_TO_GEOMETRIC_KM2,
    PiecewiseLinearBarotrope,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "ns_eos_v1_1" / "tov_love_cross_validation_contract_v0_1.yaml"
)
RESULTS = (
    ROOT / "ns_eos_v1_1" / "tov_love_cross_validation_results_v0_1.json"
)


class NSEOSTOVLoveCrossValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        cls.results = json.loads(RESULTS.read_text(encoding="utf-8"))

    def test_enthalpy_transform_round_trip(self):
        eos = PiecewiseLinearBarotrope(
            pressure_mev_fm3=(1.0, 2.0, 4.0),
            energy_mev_fm3=(10.0, 14.0, 20.0),
            core_cs2=0.5,
        )
        transformed = EnthalpyBarotrope.from_piecewise(eos)
        for pressure_mev in (1.0, 1.5, 2.0, 3.0, 4.0, 7.0):
            pressure = pressure_mev * MEV_FM3_TO_GEOMETRIC_KM2
            enthalpy = transformed.enthalpy_of_pressure(pressure)
            recovered_pressure, recovered_energy, recovered_cs2 = (
                transformed.state_at_enthalpy(enthalpy)
            )
            self.assertTrue(math.isfinite(enthalpy))
            self.assertAlmostEqual(recovered_pressure, pressure, places=16)
            self.assertAlmostEqual(
                recovered_energy,
                eos.energy_density(pressure),
                places=16,
            )
            if pressure_mev > eos.pressure_mev_fm3[0]:
                self.assertAlmostEqual(
                    recovered_cs2,
                    eos.sound_speed_squared(pressure),
                    places=14,
                )

    def test_registered_result_passes_without_confirmation(self):
        self.assertFalse(self.results["confirmatory_authorization"])
        self.assertTrue(self.results["all_cases_pass"])
        self.assertEqual(self.results["case_count"], 10)
        self.assertEqual(
            self.results["decision"],
            "TOV_LOVE_CROSS_IMPLEMENTATION_AGREEMENT_PASSED",
        )
        tolerances = self.contract["relative_tolerances"]
        for field, maximum in self.results[
            "maximum_relative_differences"
        ].items():
            self.assertLessEqual(maximum, tolerances[field], field)

    def test_implementations_are_numerically_distinct(self):
        first = self.results["cases"][0]
        implementation_a = self.results["implementations"]["A"]
        implementation_b = self.results["implementations"]["B"]
        self.assertEqual(implementation_a["independent_variable"], "radius")
        self.assertEqual(
            implementation_b["independent_variable"],
            "relativistic_enthalpy",
        )
        self.assertNotEqual(
            implementation_a["integrator"],
            implementation_b["integrator"],
        )
        self.assertNotEqual(
            first["radial_RK4"]["steps"],
            first["enthalpy_DOP853"]["accepted_steps"],
        )

    def test_registered_result_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cross-validation.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "run_tov_love_cross_validation.py"
                    ),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-26T23:28:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
