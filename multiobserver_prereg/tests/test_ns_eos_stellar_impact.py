from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_stellar_impact import (
    MEV_FM3_TO_GEOMETRIC_KM2,
    SOLAR_MASS_GEOMETRIC_KM,
    PiecewiseLinearBarotrope,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "ns_eos_v1_1" / "stellar_impact_contract_v0_1.yaml"
RESULTS = ROOT / "ns_eos_v1_1" / "stellar_impact_results_v0_1.json"


class NSEOSStellarImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = json.loads(RESULTS.read_text(encoding="utf-8"))

    def test_physical_unit_constants_are_frozen(self):
        self.assertEqual(
            MEV_FM3_TO_GEOMETRIC_KM2,
            1.3238333135663825e-6,
        )
        self.assertEqual(
            SOLAR_MASS_GEOMETRIC_KM,
            1.4766250380501249,
        )

    def test_piecewise_barotrope_interpolates_and_extends_causally(self):
        eos = PiecewiseLinearBarotrope(
            pressure_mev_fm3=(1.0, 2.0),
            energy_mev_fm3=(10.0, 14.0),
            core_cs2=0.5,
        )
        pressure = 1.5 * MEV_FM3_TO_GEOMETRIC_KM2
        epsilon = eos.energy_density(pressure) / MEV_FM3_TO_GEOMETRIC_KM2
        self.assertAlmostEqual(epsilon, 12.0)
        self.assertAlmostEqual(eos.sound_speed_squared(pressure), 0.25)
        high_pressure = 3.0 * MEV_FM3_TO_GEOMETRIC_KM2
        high_epsilon = (
            eos.energy_density(high_pressure)
            / MEV_FM3_TO_GEOMETRIC_KM2
        )
        self.assertAlmostEqual(high_epsilon, 16.0)
        self.assertEqual(eos.sound_speed_squared(high_pressure), 0.5)

    def test_registered_stellar_impact_passes_without_confirmation(self):
        self.assertFalse(self.results["confirmatory_authorization"])
        self.assertTrue(self.results["all_thresholds_pass"])
        self.assertEqual(
            self.results["decision"],
            "STELLAR_IMPACT_WITHIN_REGISTERED_DEVELOPMENT_LIMITS",
        )
        self.assertEqual(len(self.results["models"]), 48)
        self.assertTrue(
            all(
                math.isfinite(model["radius_km"])
                and math.isfinite(model["tidal_lambda"])
                and model["radius_km"] > 0
                and model["tidal_lambda"] > 0
                for model in self.results["models"]
            )
        )

    def test_stellar_impact_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "stellar.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "run_stellar_impact_validation.py"
                    ),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-26T23:32:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
