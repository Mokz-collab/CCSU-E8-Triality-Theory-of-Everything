from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from ccsu_multiobserver.analysis import (
    AnalysisError,
    _holm_adjust,
    _primary_failure_count,
    bca_summary,
    out_of_sample_delta_r2,
    run_analysis,
    spearman_rho,
    validate_schedule,
    verify_freeze,
)
from ccsu_multiobserver.core import (
    cell_label,
    deterministic_seed,
    enumerate_cells,
    load_config,
)
from ccsu_multiobserver.runner import BLOCKS, execute


ROOT = Path(__file__).resolve().parents[1]


class StatisticalPrimitiveTests(unittest.TestCase):
    def test_spearman_handles_ties(self):
        x = [0.0, 0.0, 1.0, 1.0, 2.0]
        y = [1.0, 1.0, 2.0, 2.0, 4.0]
        self.assertAlmostEqual(spearman_rho(x, y), 1.0)

    def test_out_of_sample_delta_r2_rewards_holonomy_signal(self):
        n_values = []
        topologies = []
        biases = []
        h_c = []
        repair = []
        for n in [3, 5, 9]:
            for topology_index, topology in enumerate(["complete", "er", "ring"]):
                for bias in [0.0, 0.1, 0.3, 0.5]:
                    n_values.append(n)
                    topologies.append(topology)
                    biases.append(bias)
                    h_c.append(bias)
                    repair.append(
                        2.0 * bias
                        + 0.01 * n
                        + 0.02 * topology_index
                        + 0.002 * bias * topology_index
                    )
        delta = out_of_sample_delta_r2(
            repair, h_c, n_values, topologies, biases
        )
        self.assertGreater(delta, 0.5)

    def test_bca_summary_is_ordered(self):
        observed = 0.5
        bootstrap = np.linspace(0.2, 0.8, 1000)
        jackknife = np.linspace(0.45, 0.55, 30)
        summary = bca_summary(observed, bootstrap, jackknife)
        self.assertLess(summary["lower_95_one_sided"], observed)
        self.assertGreater(summary["upper_95_one_sided"], observed)

    def test_holm_is_monotone_in_sorted_p_values(self):
        result = _holm_adjust(
            {"P1": 0.001, "P2": 0.02, "P3": 0.04, "P4": 0.20},
            0.05,
        )
        adjusted = [
            result[name]["holm_adjusted_p"]
            for name in ["P1", "P2", "P3", "P4"]
        ]
        self.assertEqual(adjusted, sorted(adjusted))
        self.assertTrue(result["P1"]["rejected"])
        self.assertFalse(result["P4"]["rejected"])


class IntegrityTests(unittest.TestCase):
    def test_original_public_freeze_still_verifies(self):
        result = verify_freeze(
            ROOT,
            ROOT / "config.yaml",
            ROOT / "public_attestation.json",
            enforce=True,
        )
        self.assertEqual(
            result.config_sha256,
            "d522fba2db9cb08316bed0bc0e39a9685bdf1b1355aa2054787ab79ed93b0d35",
        )
        self.assertGreater(result.frozen_files_verified, 10)
        self.assertTrue(result.runtime_matches_lock)

    def test_duplicate_schedule_row_is_refused(self):
        config = load_config(ROOT / "config_smoke.yaml")
        rows = []
        for block in BLOCKS:
            for cell in enumerate_cells(config, block):
                label = cell_label(block, cell)
                for replicate in range(config.replicates):
                    row = {
                        "registration_id": config.data["registration_id"],
                        "confirmatory": False,
                        "block": block,
                        "cell": label,
                        "replicate": replicate,
                        "seed": deterministic_seed(
                            config.master_seed, label, replicate
                        ),
                        "status": "failed",
                        **cell,
                    }
                    rows.append(row)
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(AnalysisError, "duplicate schedule row"):
            validate_schedule(config, rows)

    def test_only_preregistered_contrast_arms_force_prediction_failure(self):
        rows = [
            {
                "architecture": "ATLAS",
                "condition": "event",
                "_effective_status": "failed",
            },
            {
                "architecture": "HYBRID",
                "condition": "event",
                "_effective_status": "failed",
            },
            {
                "architecture": "MEAN",
                "condition": "no_event",
                "_effective_status": "failed",
            },
        ]
        self.assertEqual(_primary_failure_count("P3", rows), 1)


class EndToEndTests(unittest.TestCase):
    def test_nonconfirmatory_complete_run_is_analyzed_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            data = yaml.safe_load(
                (ROOT / "config_smoke.yaml").read_text(encoding="utf-8")
            )
            data["registration_id"] = "CCSU-MO-ANALYSIS-SMOKE"
            data["master_seed"] = 8675309
            data["blocks"]["P2"]["translation_biases"] = [0.0, 0.1, 0.3, 0.5]
            config_path = tmp / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
            )
            config = load_config(config_path)
            run_dir = tmp / "run"
            summary = execute(config, list(BLOCKS), run_dir)
            self.assertEqual(sum(summary["counts"].values()), 99)
            first = run_analysis(
                config_path=config_path,
                inputs=[run_dir],
                output=tmp / "analysis-one",
                allow_nonconfirmatory=True,
                bootstrap_resamples=100,
            )
            second = run_analysis(
                config_path=config_path,
                inputs=[run_dir],
                output=tmp / "analysis-two",
                allow_nonconfirmatory=True,
                bootstrap_resamples=100,
            )
            self.assertEqual(first["report_sha256"], second["report_sha256"])
            report = json.loads(
                (tmp / "analysis-one" / "analysis_report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(set(report["predictions"]), set(BLOCKS))
            self.assertTrue(report["schedule"]["complete"])
            self.assertEqual(report["schedule"]["observed_rows"], 99)
            self.assertEqual(
                set(first["decisions"].values()).difference({"PASS", "FAIL"}),
                set(),
            )
            self.assertTrue(
                (tmp / "analysis-one" / "analysis_manifest.json").is_file()
            )
            self.assertTrue(
                (tmp / "analysis-one" / "deviations.jsonl").is_file()
            )


if __name__ == "__main__":
    unittest.main()
