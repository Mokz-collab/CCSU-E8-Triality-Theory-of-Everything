from __future__ import annotations

import hashlib
import math
import tempfile
import unittest
from pathlib import Path

from ccsu_multiobserver.ns_eos_low_density import (
    MEV_FM3_TO_ERG_CM3,
    MEV_FM3_TO_G_CM3,
    MEV_FM3_TO_PA,
    LowDensityContractError,
    ThermodynamicRow,
    build_chemical_potential_connector,
    energy_mev_fm3_to_erg_cm3,
    energy_mev_fm3_to_mass_g_cm3,
    load_thermodynamic_table,
    number_density_fm3_to_cm3,
    pressure_mev_fm3_to_pa,
    validate_smooth_match,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
LOWER_MANIFEST = FIXTURES / "low_density_lower_manifest.yaml"
UPPER_MANIFEST = FIXTURES / "low_density_upper_manifest.yaml"


class NSEOSLowDensityTests(unittest.TestCase):
    def test_pinned_synthetic_tables_validate_and_match(self):
        lower = load_thermodynamic_table(LOWER_MANIFEST)
        upper = load_thermodynamic_table(UPPER_MANIFEST)
        residuals = validate_smooth_match(lower, upper)
        self.assertEqual(residuals.baryon_number_density, 0.0)
        self.assertEqual(residuals.pressure, 0.0)
        self.assertEqual(residuals.energy_density, 0.0)
        self.assertEqual(residuals.baryon_chemical_potential, 0.0)
        self.assertEqual(lower.source_kind, "SYNTHETIC_TEST_ONLY")

    def test_exact_si_and_cgs_unit_conversions(self):
        self.assertEqual(pressure_mev_fm3_to_pa(1.0), MEV_FM3_TO_PA)
        self.assertEqual(
            energy_mev_fm3_to_erg_cm3(1.0), MEV_FM3_TO_ERG_CM3
        )
        self.assertEqual(
            energy_mev_fm3_to_mass_g_cm3(1.0), MEV_FM3_TO_G_CM3
        )
        self.assertEqual(number_density_fm3_to_cm3(1.0), 1.0e39)
        self.assertTrue(math.isclose(MEV_FM3_TO_PA, 1.602176634e32))

    def test_hash_mismatch_is_rejected_before_parsing(self):
        manifest_text = LOWER_MANIFEST.read_text(encoding="utf-8")
        manifest_text = manifest_text.replace(
            "1ab9668e9152ede0c7f34200b8ce5d5833f378798ca9a72f811ae1ad1c9c849a",
            hashlib.sha256(b"wrong").hexdigest(),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / "low_density_lower_synthetic.csv").write_bytes(
                (FIXTURES / "low_density_lower_synthetic.csv").read_bytes()
            )
            manifest = temporary / "manifest.yaml"
            manifest.write_text(manifest_text, encoding="utf-8")
            with self.assertRaisesRegex(LowDensityContractError, "sha256 mismatch"):
                load_thermodynamic_table(manifest)

    def test_thermodynamic_identity_violation_is_rejected(self):
        table_text = (
            FIXTURES / "low_density_lower_synthetic.csv"
        ).read_text(encoding="utf-8")
        table_text = table_text.replace("941.000000000000", "942.000000000000")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            table = temporary / "invalid.csv"
            table.write_text(table_text, encoding="utf-8")
            digest = hashlib.sha256(table.read_bytes()).hexdigest()
            manifest_text = LOWER_MANIFEST.read_text(encoding="utf-8")
            manifest_text = manifest_text.replace(
                "low_density_lower_synthetic.csv", "invalid.csv"
            ).replace(
                "1ab9668e9152ede0c7f34200b8ce5d5833f378798ca9a72f811ae1ad1c9c849a",
                digest,
            )
            manifest = temporary / "manifest.yaml"
            manifest.write_text(manifest_text, encoding="utf-8")
            with self.assertRaisesRegex(
                LowDensityContractError, r"mu != \(epsilon \+ p\) / n"
            ):
                load_thermodynamic_table(manifest)

    def test_nonredistributable_bytes_are_rejected(self):
        manifest_text = UPPER_MANIFEST.read_text(encoding="utf-8").replace(
            "redistribution_permitted: true",
            "redistribution_permitted: false",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / "low_density_upper_synthetic.csv").write_bytes(
                (FIXTURES / "low_density_upper_synthetic.csv").read_bytes()
            )
            manifest = temporary / "manifest.yaml"
            manifest.write_text(manifest_text, encoding="utf-8")
            with self.assertRaisesRegex(
                LowDensityContractError, "non-redistributable"
            ):
                load_thermodynamic_table(manifest)

    def test_chemical_potential_connector_recovers_known_polytrope(self):
        lower_table = load_thermodynamic_table(LOWER_MANIFEST)
        upper_table = load_thermodynamic_table(UPPER_MANIFEST)
        connector = build_chemical_potential_connector(
            lower_table.last, upper_table.last
        )
        self.assertAlmostEqual(connector.shape, 0.0, places=10)
        reconstructed = connector.sample(3)
        expected = upper_table.rows
        for actual, target in zip(reconstructed, expected, strict=True):
            for field in (
                "n_b_fm3",
                "p_mev_fm3",
                "epsilon_mev_fm3",
                "mu_b_mev",
                "cs2",
            ):
                self.assertAlmostEqual(
                    getattr(actual, field), getattr(target, field), places=9
                )

    def test_connector_rejects_inconsistent_endpoint_spans(self):
        lower = ThermodynamicRow(
            n_b_fm3=0.04,
            p_mev_fm3=0.16,
            epsilon_mev_fm3=37.72,
            mu_b_mev=947.0,
            cs2=0.008,
        )
        upper_pressure = 2.0
        upper_density = 0.08
        upper_mu = 955.0
        upper = ThermodynamicRow(
            n_b_fm3=upper_density,
            p_mev_fm3=upper_pressure,
            epsilon_mev_fm3=upper_density * upper_mu - upper_pressure,
            mu_b_mev=upper_mu,
            cs2=0.02,
        )
        with self.assertRaisesRegex(
            LowDensityContractError, r"violate dP=n dmu"
        ):
            build_chemical_potential_connector(lower, upper)


if __name__ == "__main__":
    unittest.main()
