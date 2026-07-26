from __future__ import annotations

import math
import unittest

import numpy as np

from ccsu_multiobserver.control_recovery import (
    _fiedler_control,
    _floor_ratio,
    _normalized_laplacian,
    _spectral_original_tau,
)
from ccsu_multiobserver.core import dispersion


class ControlRecoveryTests(unittest.TestCase):
    def test_normalized_laplacian_has_expected_path_spectrum(self):
        adjacency = np.array(
            [[0.0, 1.0, 0.0], [1.0, 0.0, 1.0], [0.0, 1.0, 0.0]]
        )
        values = np.linalg.eigvalsh(_normalized_laplacian(adjacency))
        np.testing.assert_allclose(values, [0.0, 1.0, 2.0], atol=1e-12)

    def test_spectral_original_matches_direct_iteration(self):
        adjacency = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        laplacian = _normalized_laplacian(adjacency)
        initial = np.random.default_rng(42).normal(size=(4, 3))
        expected = _spectral_original_tau(laplacian, initial, 0.2, 0.1, 3, 200)
        state = initial.copy()
        threshold = 0.1 * dispersion(initial)
        consecutive = 0
        observed = 200
        for step in range(1, 201):
            state = state - 0.2 * (laplacian @ state)
            if dispersion(state) <= threshold:
                consecutive += 1
                if consecutive >= 3:
                    observed = step - 2
                    break
            else:
                consecutive = 0
        self.assertEqual(expected, observed)

    def test_irregular_graph_can_have_nonzero_public_dispersion_floor(self):
        adjacency = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        laplacian = _normalized_laplacian(adjacency)
        initial = np.arange(12, dtype=float).reshape(4, 3)
        self.assertGreater(_floor_ratio(laplacian, initial), 0.0)

    def test_fiedler_control_matches_closed_form(self):
        n = 9
        adjacency = np.zeros((n, n))
        for index in range(n - 1):
            adjacency[index, index + 1] = 1.0
            adjacency[index + 1, index] = 1.0
        result = _fiedler_control(
            _normalized_laplacian(adjacency),
            kappa=0.2,
            threshold_fraction=0.1,
            consecutive_needed=10,
            horizon=4000,
            public_dim=3,
        )
        self.assertTrue(result["exact_match"])
        self.assertFalse(result["censored"])
        self.assertEqual(
            result["exact_tau"],
            math.ceil(float(result["exact_real_tau"]) - 1e-12),
        )


if __name__ == "__main__":
    unittest.main()
