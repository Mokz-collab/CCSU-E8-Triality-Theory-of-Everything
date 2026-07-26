from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import yaml

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
OUTER_CRUST_DATA = (
    ROOT / "ns_eos_v1_1" / "data" / "outer_crust_koliogi_2026"
)
OUTER_CRUST_MANIFESTS = tuple(
    OUTER_CRUST_DATA / name
    for name in (
        "manifest_DDME2.yaml",
        "manifest_DDPC1.yaml",
        "manifest_DDPCX.yaml",
        "manifest_ELMA.yaml",
    )
)
CHIRAL_EFT_DATA = (
    ROOT / "ns_eos_v1_1" / "data" / "chiral_eft_muses_v1_0_1"
)
CHIRAL_EFT_MANIFESTS = tuple(
    CHIRAL_EFT_DATA / name
    for name in (
        "manifest_n3lo_414.yaml",
        "manifest_n3lo_450.yaml",
    )
)


class NSEOSLowDensityTests(unittest.TestCase):
    def _absolute_generated_manifest(self) -> dict:
        manifest_path = CHIRAL_EFT_MANIFESTS[0]
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["table_path"] = str(
            (CHIRAL_EFT_DATA / manifest["table_path"]).resolve()
        )
        manifest["license_path"] = str(
            (CHIRAL_EFT_DATA / manifest["license_path"]).resolve()
        )
        generated = manifest["generated_provenance"]
        for field in (
            "generator_path",
            "generation_record_path",
            "config_path",
            "raw_output_path",
        ):
            generated[field] = str(
                (CHIRAL_EFT_DATA / generated[field]).resolve()
            )
        return manifest

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

    def test_pinned_scientific_outer_crust_ensemble_validates(self):
        tables = [
            load_thermodynamic_table(manifest)
            for manifest in OUTER_CRUST_MANIFESTS
        ]
        self.assertEqual(
            {table.model_label for table in tables},
            {"DD-ME2", "DD-PC1", "DD-PCX", "ELMA"},
        )
        for table in tables:
            self.assertEqual(table.source_kind, "SCIENTIFIC_OUTER_CRUST")
            self.assertEqual(
                table.provenance_mode, "direct_upstream_git_blob"
            )
            self.assertEqual(table.raw_format, "koliogi_outer_crust_v1")
            self.assertEqual(table.license_spdx, "CC-BY-4.0")
            self.assertEqual(len(table.rows), 56)
            self.assertEqual(table.first.n_b_fm3, 7.0e-12)
            self.assertGreater(table.last.n_b_fm3, 2.0e-4)
            self.assertLess(table.last.n_b_fm3, 3.0e-4)

    def test_outer_crust_speed_ratio_is_squared_on_import(self):
        table = load_thermodynamic_table(OUTER_CRUST_MANIFESTS[0])
        self.assertAlmostEqual(
            table.first.cs2,
            (1.748879e-3) ** 2,
            places=18,
        )

    def test_neutron_drip_endpoint_remains_model_specific(self):
        tables = [
            load_thermodynamic_table(manifest)
            for manifest in OUTER_CRUST_MANIFESTS
        ]
        endpoints = {table.last.n_b_fm3 for table in tables}
        self.assertEqual(len(endpoints), 4)

    def test_generated_chiral_eft_reference_members_validate(self):
        tables = [
            load_thermodynamic_table(manifest)
            for manifest in CHIRAL_EFT_MANIFESTS
        ]
        self.assertEqual(
            {table.model_label for table in tables},
            {"MUSES-N3LO-414", "MUSES-N3LO-450"},
        )
        for table in tables:
            self.assertEqual(
                table.source_kind, "SCIENTIFIC_CHIRAL_EFT_REFERENCE"
            )
            self.assertEqual(
                table.provenance_mode, "deterministic_generated_output"
            )
            self.assertEqual(table.raw_format, "canonical_csv_v1")
            self.assertEqual(table.license_spdx, "GPL-3.0-or-later")
            self.assertEqual(len(table.rows), 25)
            self.assertEqual(table.first.n_b_fm3, 0.5 * 0.16)
            self.assertAlmostEqual(table.last.n_b_fm3, 1.1 * 0.16)
            self.assertGreater(table.first.cs2, 0.0)
            self.assertLess(table.last.cs2, 1.0)

    def test_chiral_eft_members_remain_distinct_coherent_eos(self):
        interaction_414, interaction_450 = [
            load_thermodynamic_table(manifest)
            for manifest in CHIRAL_EFT_MANIFESTS
        ]
        self.assertEqual(
            [row.n_b_fm3 for row in interaction_414.rows],
            [row.n_b_fm3 for row in interaction_450.rows],
        )
        self.assertTrue(
            all(
                row_414.p_mev_fm3 > row_450.p_mev_fm3
                for row_414, row_450 in zip(
                    interaction_414.rows,
                    interaction_450.rows,
                    strict=True,
                )
            )
        )

    def test_generated_chiral_eft_generator_hash_is_enforced(self):
        manifest = self._absolute_generated_manifest()
        manifest["generated_provenance"]["generator_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            temporary_manifest = Path(directory) / "manifest.yaml"
            temporary_manifest.write_text(
                yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                LowDensityContractError,
                "generated provenance hash mismatch: generator_path",
            ):
                load_thermodynamic_table(temporary_manifest)

    def test_generated_chiral_eft_cannot_claim_coverage(self):
        manifest = self._absolute_generated_manifest()
        record_path = Path(
            manifest["generated_provenance"]["generation_record_path"]
        )
        generation_record = json.loads(record_path.read_text(encoding="utf-8"))
        generation_record["scientific_semantics"]["probabilistic_coverage"] = 0.9
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            temporary_record = temporary / "generation_record.json"
            temporary_record.write_text(
                json.dumps(generation_record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest["generated_provenance"]["generation_record_path"] = str(
                temporary_record
            )
            manifest["generated_provenance"]["generation_record_sha256"] = (
                hashlib.sha256(temporary_record.read_bytes()).hexdigest()
            )
            temporary_manifest = temporary / "manifest.yaml"
            temporary_manifest.write_text(
                yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                LowDensityContractError,
                "cannot claim probabilistic coverage",
            ):
                load_thermodynamic_table(temporary_manifest)


if __name__ == "__main__":
    unittest.main()
