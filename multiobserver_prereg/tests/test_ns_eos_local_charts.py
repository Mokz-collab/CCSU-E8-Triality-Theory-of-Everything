from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    LocalChartError,
    LocalChartProposalRejected,
    evaluate_local_physics,
    generate_local_chart,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "ns_eos_v1_1" / "local_chart_generator_contract_v0_1.yaml"
)
RESULTS = (
    ROOT / "ns_eos_v1_1" / "local_chart_generator_results_v0_1.json"
)
ANCHOR = (
    ROOT
    / "ns_eos_v1_1"
    / "data"
    / "chiral_eft_muses_v1_0_1"
    / "manifest_n3lo_414.yaml"
)


class NSEOSLocalChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        cls.results = json.loads(RESULTS.read_text(encoding="utf-8"))
        cls.anchor = load_thermodynamic_table(ANCHOR).last

    def test_registered_four_chart_cross_anchor_result_passes(self):
        self.assertFalse(self.results["confirmatory_authorization"])
        self.assertTrue(self.results["all_cases_pass"])
        self.assertTrue(self.results["four_distinct_local_charts"])
        self.assertEqual(self.results["case_count"], 8)
        self.assertEqual(
            self.results["decision"],
            "FOUR_LOCAL_CHART_GENERATORS_PASSED_INTERNAL_LOCAL_FILTERS",
        )

    def test_registered_exemplars_match_anchor_and_identity(self):
        for observer, specification in CHART_SPECIFICATIONS.items():
            parameters = self.contract["charts"][observer][
                "registered_exemplar"
            ]
            eos = generate_local_chart(observer, parameters, self.anchor)
            diagnostics = evaluate_local_physics(eos, self.anchor)
            self.assertEqual(eos.chart, specification.chart)
            self.assertTrue(diagnostics["all_local_checks_pass"], observer)
            self.assertLessEqual(
                max(
                    diagnostics[
                        "matching_relative_residuals"
                    ].values()
                ),
                1.0e-10,
            )
            self.assertLessEqual(
                diagnostics["maximum_identity_relative_residual"],
                1.0e-12,
            )

    def test_parameter_names_and_bounds_are_enforced(self):
        with self.assertRaisesRegex(LocalChartError, "parameter names"):
            generate_local_chart(
                "GW",
                {"gamma0": 1.0},
                self.anchor,
            )
        parameters = dict(
            self.contract["charts"]["GW"]["registered_exemplar"]
        )
        parameters["gamma0"] = 2.01
        with self.assertRaisesRegex(LocalChartError, "outside"):
            generate_local_chart("GW", parameters, self.anchor)

    def test_invalid_in_range_xray_pressure_is_rejected_not_clipped(self):
        parameters = dict(
            self.contract["charts"]["XRAY"]["registered_exemplar"]
        )
        parameters["log10_p1_cgs"] = 33.6
        with self.assertRaisesRegex(
            LocalChartProposalRejected,
            "must exceed",
        ):
            generate_local_chart("XRAY", parameters, self.anchor)

    def test_causal_filter_rejects_extreme_but_in_range_gw_proposal(self):
        parameters = {
            "gamma0": 2.0,
            "gamma1": 1.7,
            "gamma2": 0.6,
            "gamma3": 0.02,
        }
        eos = generate_local_chart("GW", parameters, self.anchor)
        diagnostics = evaluate_local_physics(eos, self.anchor)
        self.assertFalse(diagnostics["all_local_checks_pass"])
        self.assertFalse(diagnostics["checks"]["sound_speed_causal"])
        self.assertGreater(
            diagnostics["maximum_sound_speed_squared"],
            1.0,
        )

    def test_local_parameters_are_not_an_atlas_aggregation_record(self):
        for case in self.results["cases"]:
            self.assertIn("parameters", case)
            self.assertNotIn("atlas_parameter_vector", case)
            self.assertIn(
                case["chart"],
                {
                    "spectral_adiabatic_index",
                    "piecewise_polytrope",
                    "monotone_eos_spline",
                    "speed_of_sound_nodes",
                },
            )

    def test_registered_result_replay_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "local-charts.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "run_local_chart_validation.py"
                    ),
                    "--contract",
                    str(CONTRACT),
                    "--output",
                    str(output),
                    "--created-utc",
                    "2026-07-27T10:14:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(output.read_bytes(), RESULTS.read_bytes())


if __name__ == "__main__":
    unittest.main()
