from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from ccsu_multiobserver.core import (
    deterministic_seed,
    geometric_median,
    load_config,
    make_graph,
    metric_p1,
    metric_p2,
    metric_p4,
    metric_p5,
    robust_atlas,
)
from ccsu_multiobserver.runner import emit_seeds


ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config_smoke.yaml")

    def test_seed_derivation_is_stable_and_label_sensitive(self):
        first = deterministic_seed(42, "P1", "cell", 0)
        self.assertEqual(first, deterministic_seed(42, "P1", "cell", 0))
        self.assertNotEqual(first, deterministic_seed(42, "P1", "cell", 1))

    def test_geometric_median_resists_one_extreme_point(self):
        points = np.array([[0.0, 0.0], [0.1, -0.1], [-0.1, 0.1], [100.0, 100.0]])
        estimate = geometric_median(points)
        self.assertLess(np.linalg.norm(estimate), 0.5)

    def test_replay_is_deduplicated_by_provenance(self):
        claims = np.array([[0.0, 0.0], [1.0, 1.0], [100.0, 100.0], [100.0, 100.0]])
        origins = ["a", "b", "c", "c"]
        confidence = np.ones(4)
        result = robust_atlas(claims, origins, confidence, self.config.data["atlas"])
        unique = robust_atlas(claims[:3], origins[:3], confidence[:3], self.config.data["atlas"])
        np.testing.assert_allclose(result, unique)

    def test_all_graphs_are_connected(self):
        for topology in ["path", "ring", "star", "er", "complete"]:
            adjacency, _ = make_graph(topology, 4, np.random.default_rng(9), 0.47)
            self.assertEqual(np.linalg.matrix_power(adjacency + np.eye(4), 3).min() > 0, True)

    def test_block_metrics_are_finite(self):
        p1 = metric_p1(self.config, 4, 0.22, "HYBRID", 11)
        p2 = metric_p2(self.config, 4, "ring", 0.17, 12)
        p4 = metric_p4(self.config, 4, 0.22, "HYBRID", "replay", 13)
        p5 = metric_p5(self.config, 4, "path", 14)
        values = [p1["r_q"], p1["r_private"], p2["h_c"], p2["repair_cost"], p4["delta_omega"], p5["lambda2"], p5["tau"]]
        self.assertTrue(np.all(np.isfinite(values)))

    def test_seed_manifest_row_count(self):
        expected_cells = 4 + 1 + 8 + 12 + 5
        with tempfile.TemporaryDirectory() as tmp:
            result = emit_seeds(self.config, Path(tmp) / "seeds.csv.gz")
        self.assertEqual(result["rows"], expected_cells * self.config.replicates)


if __name__ == "__main__":
    unittest.main()

