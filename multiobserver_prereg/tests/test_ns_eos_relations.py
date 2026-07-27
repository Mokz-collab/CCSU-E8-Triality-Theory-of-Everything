from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
)
from ccsu_multiobserver.ns_eos_local_charts import generate_local_chart
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
)
from ccsu_multiobserver.ns_eos_relations import (
    RelationTranslationError,
    build_finite_domain_barotrope,
)
from ccsu_multiobserver.ns_eos_stellar_impact import (
    MEV_FM3_TO_GEOMETRIC_KM2,
)


ROOT = Path(__file__).resolve().parents[1]
NS_ROOT = ROOT / "ns_eos_v1_1"
CONTRACT = NS_ROOT / "local_to_public_relation_contract_v0_1.yaml"
RESULTS = NS_ROOT / "local_to_public_relation_results_v0_1.json"
CHART_CONTRACT = NS_ROOT / "local_chart_generator_contract_v0_1.yaml"


class NSEOSRelationTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        cls.chart_contract = yaml.safe_load(
            CHART_CONTRACT.read_text(encoding="utf-8")
        )
        cls.results = json.loads(RESULTS.read_text(encoding="utf-8"))

    def test_translation_runs_but_registered_stellar_gates_fail(self):
        self.assertTrue(self.results["translations_completed"])
        self.assertEqual(self.results["case_count"], 8)
        self.assertEqual(self.results["full_stellar_gate_pass_count"], 0)
        self.assertEqual(
            self.results["domain_truncated_before_turnover_count"],
            8,
        )
        self.assertFalse(self.results["pilot_entry_authorized"])
        self.assertEqual(
            self.results["decision"],
            "TRANSLATION_IMPLEMENTED_REGISTERED_EXEMPLARS_FAILED_"
            "FINITE_DOMAIN_STELLAR_GATES",
        )

    def test_maximum_mass_is_not_invented_at_domain_boundary(self):
        for case in self.results["cases"]:
            stellar = case["stellar_translation"]
            self.assertIsNone(stellar["maximum_mass_msun"])
            self.assertGreater(
                stellar["maximum_mass_lower_bound_msun"],
                0,
            )
            self.assertFalse(
                stellar["gates"]["domain_contains_mass_turnover"]
            )
            self.assertFalse(case["finite_domain"]["extension_used"])

    def test_only_nuclear_exemplars_support_two_solar_masses(self):
        passed = {
            case["case_id"]
            for case in self.results["cases"]
            if case["stellar_translation"]["gates"][
                "maximum_mass_at_least_2_0_msun"
            ]
        }
        self.assertEqual(
            passed,
            {
                "NUCLEAR__MUSES-N3LO-414",
                "NUCLEAR__MUSES-N3LO-450",
            },
        )

    def test_public_projections_preserve_roles_and_provenance(self):
        expected_relation = {
            "GW": {"tidal_deformability_mass", "maximum_mass_msun",
                   "maximum_mass_lower_bound_msun"},
            "XRAY": {"mass_radius", "maximum_mass_msun",
                     "maximum_mass_lower_bound_msun"},
            "RADIO": {"maximum_mass_msun",
                      "maximum_mass_lower_bound_msun"},
            "NUCLEAR": {"pressure_energy_density"},
        }
        required = set(
            self.contract["public_projection"]["required_provenance"]
        )
        for case in self.results["cases"]:
            public = case["public_projection"]
            self.assertEqual(set(public["provenance"]), required)
            self.assertEqual(
                set(public["relations"]),
                expected_relation[case["observer"]],
            )
            self.assertFalse(public["local_parameters_included"])

    def test_pressure_above_six_nsat_is_a_hard_error(self):
        low = self.contract["low_density"]
        outer = load_thermodynamic_table(
            NS_ROOT / low["outer_crust_reference"]["manifest"]
        )
        eft = load_thermodynamic_table(
            NS_ROOT / low["chiral_eft_anchors"][0]
        )
        template = load_derivative_template(
            NS_ROOT / low["inner_crust_template"]
        )
        parameters = self.chart_contract["charts"]["NUCLEAR"][
            "registered_exemplar"
        ]
        chart = generate_local_chart("NUCLEAR", parameters, eft.last)
        eos = build_finite_domain_barotrope(
            outer,
            eft,
            template,
            chart,
            connector_points=int(low["connector_sample_count"]),
            projection_tolerance=float(
                low["rounded_outer_mu_projection_tolerance"]
            ),
        )
        above = (
            eos.maximum_pressure_mev_fm3
            * 1.001
            * MEV_FM3_TO_GEOMETRIC_KM2
        )
        with self.assertRaisesRegex(
            RelationTranslationError,
            "exceeds",
        ):
            eos.energy_density(above)

    def test_registered_convergence_check_passes(self):
        convergence = self.results["convergence_check"]
        self.assertTrue(convergence["all_checks_pass"])
        self.assertTrue(all(convergence["checks"].values()))

    def test_registered_result_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "relations.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "run_local_to_public_relation_validation.py"
                    ),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-27T10:49:15Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
