from __future__ import annotations

import math
import unittest
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_oracle import (
    OracleError,
    RelativisticPolytrope,
    solve_sequence,
    solve_star,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "ns_eos_v1_1" / "ns_eos_oracle_contract_v0_2.yaml"


class NSEOSOracleTests(unittest.TestCase):
    def setUp(self):
        self.eos = RelativisticPolytrope(k=1.0, gamma=2.0)

    def test_dimensionless_models_are_finite_and_physical(self):
        models = solve_sequence(self.eos, [0.05, 0.10, 0.20, 0.40])
        for model in models:
            values = (
                model.mass,
                model.radius,
                model.compactness,
                model.love_k2,
                model.tidal_lambda,
                model.surface_y,
            )
            self.assertTrue(all(math.isfinite(value) for value in values))
            self.assertGreater(model.mass, 0)
            self.assertGreater(model.radius, 0)
            self.assertLess(model.compactness, 0.5)
            self.assertGreater(model.love_k2, 0)
            self.assertGreater(model.tidal_lambda, 0)

    def test_mass_rises_on_low_pressure_stable_branch(self):
        models = solve_sequence(self.eos, [0.02, 0.04, 0.08])
        self.assertLess(models[0].mass, models[1].mass)
        self.assertLess(models[1].mass, models[2].mass)

    def test_halving_maximum_step_changes_observables_by_less_than_one_percent(self):
        coarse = solve_star(self.eos, 0.20, maximum_step=1.0e-3)
        fine = solve_star(self.eos, 0.20, maximum_step=5.0e-4)
        for name in ("mass", "radius", "love_k2", "tidal_lambda"):
            coarse_value = getattr(coarse, name)
            fine_value = getattr(fine, name)
            relative_difference = abs(coarse_value - fine_value) / abs(fine_value)
            self.assertLess(relative_difference, 0.01, name)

    def test_acausal_central_state_is_rejected(self):
        class AcausalEOS:
            @staticmethod
            def energy_density(pressure: float) -> float:
                return pressure

            @staticmethod
            def sound_speed_squared(pressure: float) -> float:
                return 1.1

        with self.assertRaises(OracleError):
            solve_star(AcausalEOS(), 0.1)

    def test_invalid_polytrope_is_rejected(self):
        with self.assertRaises(ValueError):
            RelativisticPolytrope(k=1.0, gamma=2.1)

    def test_registered_reference_sequence_is_reproduced(self):
        with CONTRACT.open("r", encoding="utf-8") as handle:
            contract = yaml.safe_load(handle)
        self.assertFalse(contract["confirmatory_authorization"])
        self.assertEqual(contract["status"], "INTERNAL_ORACLE_NOT_CROSS_VALIDATED")

        # The family label is metadata, not a constructor argument.
        eos = RelativisticPolytrope(
            k=contract["eos"]["k"],
            gamma=contract["eos"]["gamma"],
        )
        solver = contract["solver"]
        options = {
            key: solver[key]
            for key in (
                "maximum_step",
                "minimum_step",
                "pressure_step_fraction",
                "surface_pressure_fraction",
                "initial_radius",
                "maximum_radius",
                "maximum_steps",
            )
        }
        tolerance = contract["reference_sequence"]["relative_tolerance"]
        for reference in contract["reference_sequence"]["models"]:
            model = solve_star(eos, reference["central_pressure"], **options)
            for name in ("mass", "radius", "love_k2", "tidal_lambda"):
                relative_difference = (
                    abs(getattr(model, name) - reference[name]) / abs(reference[name])
                )
                self.assertLessEqual(relative_difference, tolerance, name)


if __name__ == "__main__":
    unittest.main()
