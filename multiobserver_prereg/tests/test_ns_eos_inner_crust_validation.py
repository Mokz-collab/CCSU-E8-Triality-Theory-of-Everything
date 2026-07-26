from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    connector_metrics,
    evaluate_thresholds,
    load_derivative_template,
    load_unified_eos_oracle,
)
from ccsu_multiobserver.ns_eos_low_density import (
    LowDensityContractError,
    build_reference_tilted_connector,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ns_eos_v1_1" / "data" / "unified_eos_hcdas_2022"
CONTRACT = (
    ROOT
    / "ns_eos_v1_1"
    / "inner_crust_validation_contract_v0_1.yaml"
)
RESULTS = (
    ROOT
    / "ns_eos_v1_1"
    / "inner_crust_validation_results_v0_1.json"
)
TEMPLATE = DATA / "inner_crust_derivative_template_v0_1.json"
MANIFESTS = {
    "IOPB": DATA / "manifest_IOPB.yaml",
    "G3": DATA / "manifest_G3.yaml",
    "FSUGarnet": DATA / "manifest_FSUGarnet.yaml",
}


class NSEOSInnerCrustValidationTests(unittest.TestCase):
    def test_pinned_unified_eos_oracles_validate(self):
        tables = {
            label: load_unified_eos_oracle(path)
            for label, path in MANIFESTS.items()
        }
        self.assertEqual(set(tables), {"IOPB", "G3", "FSUGarnet"})
        self.assertEqual(
            {table.source_commit for table in tables.values()},
            {"80eadb3820c337765659bd204719cedba2221649"},
        )
        self.assertEqual(len(tables["IOPB"].inner_crust_rows()), 241)
        self.assertEqual(len(tables["G3"].inner_crust_rows()), 171)
        self.assertEqual(len(tables["FSUGarnet"].inner_crust_rows()), 105)

    def test_unified_eos_hash_gate_precedes_parse(self):
        manifest = yaml.safe_load(
            MANIFESTS["G3"].read_text(encoding="utf-8")
        )
        manifest["table_path"] = str(
            (DATA / manifest["table_path"]).resolve()
        )
        manifest["license_path"] = str(
            (DATA / manifest["license_path"]).resolve()
        )
        manifest["sha256"] = hashlib.sha256(b"wrong").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            temporary_manifest = Path(directory) / "manifest.yaml"
            temporary_manifest.write_text(
                yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                LowDensityContractError,
                "table sha256 mismatch",
            ):
                load_unified_eos_oracle(temporary_manifest)

    def test_template_provenance_and_nonprobabilistic_semantics_validate(self):
        template = load_derivative_template(TEMPLATE)
        self.assertEqual(
            template.template_id,
            "CCSU-MO-NS-EOS-001-INNER-CRUST-TEMPLATE-001",
        )
        self.assertEqual(template.exponents, (-40.0, 0.0, 40.0))
        self.assertAlmostEqual(sum(template.mass_weights), 1.0)
        self.assertTrue(all(weight >= 0 for weight in template.mass_weights))

    def test_reference_tilted_connector_is_endpoint_exact_and_causal(self):
        oracle = load_unified_eos_oracle(MANIFESTS["G3"])
        rows = oracle.inner_crust_rows()
        connector = build_reference_tilted_connector(
            rows[0].as_thermodynamic_row(),
            rows[-1].as_thermodynamic_row(),
            load_derivative_template(TEMPLATE),
        )
        sampled = connector.sample(129)
        for expected, actual in (
            (rows[0].as_thermodynamic_row(), sampled[0]),
            (rows[-1].as_thermodynamic_row(), sampled[-1]),
        ):
            for field in (
                "n_b_fm3",
                "p_mev_fm3",
                "epsilon_mev_fm3",
                "mu_b_mev",
            ):
                self.assertAlmostEqual(
                    getattr(actual, field),
                    getattr(expected, field),
                    places=10,
                )
        self.assertTrue(all(0 <= row.cs2 <= 1 for row in sampled))

    def test_baseline_fails_and_candidate_passes_primary_holdout(self):
        contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        oracle = load_unified_eos_oracle(MANIFESTS["G3"])
        template = load_derivative_template(TEMPLATE)
        baseline = connector_metrics(
            oracle, "endpoint_exponential_v0_4"
        )
        candidate = connector_metrics(
            oracle,
            "reference_tilted_v0_5_candidate",
            template,
        )
        baseline_checks = evaluate_thresholds(
            baseline, contract["primary_thresholds"]
        )
        candidate_checks = evaluate_thresholds(
            candidate, contract["primary_thresholds"]
        )
        self.assertFalse(all(baseline_checks.values()))
        self.assertTrue(all(candidate_checks.values()))
        self.assertGreater(
            baseline.pressure_log_weighted_rms,
            5 * candidate.pressure_log_weighted_rms,
        )

    def test_holdout_members_are_absent_from_template_fit(self):
        record = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        semantics = record["scientific_semantics"]
        self.assertEqual(semantics["calibration_member_only"], "IOPB")
        self.assertEqual(semantics["holdout_members_used_in_fit"], [])
        self.assertFalse(semantics["probabilistic_prior"])

    def test_template_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "template.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "fit_inner_crust_reference_template.py"),
                    "--manifest",
                    str(MANIFESTS["IOPB"]),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-26T23:03:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), TEMPLATE.read_bytes())

    def test_validation_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_inner_crust_validation.py"),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-26T23:08:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
