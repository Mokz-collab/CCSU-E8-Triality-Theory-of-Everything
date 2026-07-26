from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import yaml

from .core import (
    cell_label,
    deterministic_seed,
    enumerate_cells,
    load_config,
    sha256_file,
)
from .runner import BLOCKS


ANALYSIS_ENGINE_VERSION = "1.0.0"
REQUIRED_METRICS = {
    "P1": ("r_q", "r_private"),
    "P2": ("h_c", "repair_cost"),
    "P3": ("recovered", "false_positive"),
    "P4": ("delta_omega",),
    "P5": ("lambda2", "tau"),
}
NORMAL = NormalDist()


class AnalysisError(RuntimeError):
    """Raised when the confirmatory analysis contract cannot be satisfied."""


@dataclass(frozen=True)
class IntegrityResult:
    config_sha256: str
    attestation_sha256: str | None
    content_manifest_sha256: str | None
    analysis_attestation_sha256: str | None
    analysis_engine_commit: str | None
    frozen_files_verified: int
    runtime_matches_lock: bool | None


@dataclass
class CellMeans:
    keys: list[tuple[Any, ...]]
    values: list[np.ndarray]

    @classmethod
    def from_pairs(
        cls,
        pairs: Iterable[tuple[tuple[Any, ...], float]],
    ) -> CellMeans:
        grouped: dict[tuple[Any, ...], list[float]] = {}
        for key, value in pairs:
            grouped.setdefault(key, []).append(float(value))
        if not grouped:
            raise AnalysisError("no valid observations are available for this estimand")
        keys = sorted(grouped, key=lambda item: tuple(str(part) for part in item))
        values = [np.asarray(grouped[key], dtype=float) for key in keys]
        if any(len(value) < 2 for value in values):
            raise AnalysisError("BCa analysis requires at least two valid observations per cell")
        return cls(keys=keys, values=values)

    @property
    def observed(self) -> np.ndarray:
        return np.asarray([float(np.mean(value)) for value in self.values])

    def bootstrap(self, resamples: int, rng: np.random.Generator) -> np.ndarray:
        result = np.empty((resamples, len(self.values)), dtype=float)
        batch_size = 512
        for column, values in enumerate(self.values):
            for start in range(0, resamples, batch_size):
                stop = min(start + batch_size, resamples)
                indices = rng.integers(0, len(values), size=(stop - start, len(values)))
                result[start:stop, column] = np.mean(values[indices], axis=1)
        return result

    def jackknife(self, statistic: Callable[[np.ndarray], float]) -> np.ndarray:
        means = self.observed
        estimates: list[float] = []
        for column, values in enumerate(self.values):
            total = float(np.sum(values))
            denominator = len(values) - 1
            for value in values:
                modified = means.copy()
                modified[column] = (total - float(value)) / denominator
                estimates.append(float(statistic(modified)))
        return np.asarray(estimates, dtype=float)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float, np.integer, np.floating, bool, np.bool_))
        and math.isfinite(float(value))
    )


def _rank_average(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=float)
    start = 0
    while start < len(array):
        stop = start + 1
        while stop < len(array) and array[order[stop]] == array[order[start]]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * (start + 1 + stop)
        start = stop
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y) or len(x) < 3:
        raise AnalysisError("Spearman correlation requires at least three paired values")
    rx = _rank_average(x)
    ry = _rank_average(y)
    rx -= float(np.mean(rx))
    ry -= float(np.mean(ry))
    denominator = math.sqrt(float(np.dot(rx, rx) * np.dot(ry, ry)))
    if denominator <= 0:
        raise AnalysisError("Spearman correlation is undefined for a constant input")
    return float(np.dot(rx, ry) / denominator)


def _design_matrix(
    n_values: Sequence[float],
    topologies: Sequence[str],
    h_c: Sequence[float] | None,
) -> np.ndarray:
    n_array = np.asarray(n_values, dtype=float)
    topology_array = np.asarray(topologies, dtype=object)
    columns = [np.ones(len(n_array), dtype=float)]
    unique_n = sorted(set(float(value) for value in n_array))
    for level in unique_n[1:]:
        columns.append((n_array == level).astype(float))
    unique_topologies = sorted(set(str(value) for value in topology_array))
    for level in unique_topologies[1:]:
        columns.append((topology_array == level).astype(float))
    if h_c is not None:
        h_array = np.asarray(h_c, dtype=float)
        scale = float(np.std(h_array))
        columns.append((h_array - float(np.mean(h_array))) / max(scale, 1e-12))
    return np.column_stack(columns)


def out_of_sample_delta_r2(
    repair_cost: Sequence[float],
    h_c: Sequence[float],
    n_values: Sequence[float],
    topologies: Sequence[str],
    bias_levels: Sequence[float],
) -> float:
    y = np.asarray(repair_cost, dtype=float)
    h_array = np.asarray(h_c, dtype=float)
    bias_array = np.asarray(bias_levels, dtype=float)
    if len(y) < 4 or len(set(float(value) for value in bias_array)) < 3:
        raise AnalysisError("P2 out-of-sample ΔR² requires at least three bias folds")
    base = _design_matrix(n_values, topologies, None)
    full = _design_matrix(n_values, topologies, h_array)
    base_prediction = np.empty(len(y), dtype=float)
    full_prediction = np.empty(len(y), dtype=float)
    for held_out in sorted(set(float(value) for value in bias_array)):
        test = bias_array == held_out
        train = ~test
        if int(np.sum(train)) <= full.shape[1]:
            raise AnalysisError("P2 fold has insufficient training cells for the fixed model")
        base_coef = np.linalg.lstsq(base[train], y[train], rcond=None)[0]
        full_coef = np.linalg.lstsq(full[train], y[train], rcond=None)[0]
        base_prediction[test] = base[test] @ base_coef
        full_prediction[test] = full[test] @ full_coef
    total = float(np.sum((y - float(np.mean(y))) ** 2))
    if total <= 0:
        raise AnalysisError("P2 out-of-sample R² is undefined for constant repair cost")
    base_r2 = 1.0 - float(np.sum((y - base_prediction) ** 2)) / total
    full_r2 = 1.0 - float(np.sum((y - full_prediction) ** 2)) / total
    return full_r2 - base_r2


def simple_regression(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    x_centered = x_array - float(np.mean(x_array))
    y_centered = y_array - float(np.mean(y_array))
    ssx = float(np.dot(x_centered, x_centered))
    ssy = float(np.dot(y_centered, y_centered))
    if ssx <= 0 or ssy <= 0:
        raise AnalysisError("simple regression requires variation in both variables")
    cross = float(np.dot(x_centered, y_centered))
    slope = cross / ssx
    r_squared = (cross * cross) / (ssx * ssy)
    return slope, r_squared


def _bca_limit(
    bootstrap: np.ndarray,
    observed: float,
    jackknife: np.ndarray,
    probability: float,
) -> float:
    less = float(np.sum(bootstrap < observed))
    equal = float(np.sum(bootstrap == observed))
    proportion = (less + 0.5 * equal) / len(bootstrap)
    epsilon = 0.5 / len(bootstrap)
    z0 = NORMAL.inv_cdf(min(max(proportion, epsilon), 1.0 - epsilon))
    jackknife_mean = float(np.mean(jackknife))
    influence = jackknife_mean - jackknife
    denominator = 6.0 * float(np.sum(influence**2)) ** 1.5
    acceleration = 0.0 if denominator <= 0 else float(np.sum(influence**3)) / denominator
    z_alpha = NORMAL.inv_cdf(probability)
    divisor = 1.0 - acceleration * (z0 + z_alpha)
    if abs(divisor) < 1e-12:
        adjusted = probability
    else:
        adjusted = NORMAL.cdf(z0 + (z0 + z_alpha) / divisor)
    adjusted = min(max(adjusted, 0.0), 1.0)
    return float(np.quantile(bootstrap, adjusted))


def bca_summary(
    observed: float,
    bootstrap: Sequence[float],
    jackknife: Sequence[float],
) -> dict[str, float]:
    bootstrap_array = np.asarray(bootstrap, dtype=float)
    jackknife_array = np.asarray(jackknife, dtype=float)
    if not np.all(np.isfinite(bootstrap_array)) or not np.all(np.isfinite(jackknife_array)):
        raise AnalysisError("BCa inputs contain non-finite estimates")
    return {
        "estimate": float(observed),
        "lower_95_one_sided": _bca_limit(
            bootstrap_array, float(observed), jackknife_array, 0.05
        ),
        "upper_95_one_sided": _bca_limit(
            bootstrap_array, float(observed), jackknife_array, 0.95
        ),
    }


def bootstrap_test_p(
    observed: float,
    bootstrap: Sequence[float],
    null: float,
    alternative: str,
) -> float:
    centered = np.asarray(bootstrap, dtype=float) - float(observed)
    observed_shift = float(observed) - float(null)
    if alternative == "greater":
        extreme = int(np.sum(centered >= observed_shift))
    elif alternative == "less":
        extreme = int(np.sum(centered <= observed_shift))
    else:
        raise ValueError("alternative must be 'greater' or 'less'")
    return float((extreme + 1) / (len(centered) + 1))


def _holm_adjust(p_values: dict[str, float], alpha: float) -> dict[str, dict[str, Any]]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * float(value)))
        adjusted[name] = running
    return {
        name: {
            "raw_p": float(p_values[name]),
            "holm_adjusted_p": float(adjusted[name]),
            "rejected": bool(adjusted[name] <= alpha),
        }
        for name in sorted(p_values)
    }


def _gate(
    summary: dict[str, float],
    bootstrap: np.ndarray,
    null: float,
    alternative: str,
    pass_rule: bool,
    criterion: str,
) -> dict[str, Any]:
    return {
        **summary,
        "null": float(null),
        "alternative": alternative,
        "raw_p": bootstrap_test_p(
            summary["estimate"], bootstrap, null, alternative
        ),
        "criterion": criterion,
        "threshold_pass": bool(pass_rule),
    }


def _analysis_rng(master_seed: int, block: str, estimand: str) -> np.random.Generator:
    seed = deterministic_seed(
        master_seed,
        f"analysis-engine-{ANALYSIS_ENGINE_VERSION}",
        block,
        estimand,
    )
    return np.random.default_rng(seed)


def _valid_rows(rows: Sequence[dict[str, Any]], block: str) -> list[dict[str, Any]]:
    required = REQUIRED_METRICS[block]
    return [
        row
        for row in rows
        if row["_effective_status"] == "ok"
        and all(_finite_number(row.get(metric)) for metric in required)
    ]


def _primary_row(block: str, row: dict[str, Any]) -> bool:
    if block == "P1":
        return row["architecture"] in {"HYBRID", "IND"}
    if block == "P2":
        return True
    if block == "P3":
        return (
            row["condition"] == "event"
            and row["architecture"] in {"HYBRID", "MEAN"}
        ) or (
            row["condition"] == "no_event"
            and row["architecture"] == "HYBRID"
        )
    if block == "P4":
        return row["architecture"] == "HYBRID"
    if block == "P5":
        return True
    raise ValueError(f"unknown block: {block}")


def _primary_failure_count(block: str, rows: Sequence[dict[str, Any]]) -> int:
    return sum(
        row["_effective_status"] == "failed" and _primary_row(block, row)
        for row in rows
    )


def _estimate_from_cell_means(
    cells: CellMeans,
    statistic: Callable[[np.ndarray], float],
    resamples: int,
    rng: np.random.Generator,
) -> tuple[float, np.ndarray, np.ndarray]:
    observed = float(statistic(cells.observed))
    bootstrap_cells = cells.bootstrap(resamples, rng)
    bootstrap = np.asarray(
        [float(statistic(sample)) for sample in bootstrap_cells], dtype=float
    )
    jackknife = cells.jackknife(statistic)
    return observed, bootstrap, jackknife


def _p1(
    config: Any,
    rows: Sequence[dict[str, Any]],
    resamples: int,
    failure_count: int,
) -> dict[str, Any]:
    valid = _valid_rows(rows, "P1")
    hybrid_rq = CellMeans.from_pairs(
        (
            (("HYBRID", int(row["n"]), float(row["sigma"])), float(row["r_q"]))
            for row in valid
            if row["architecture"] == "HYBRID"
        )
    )
    hybrid_private = CellMeans.from_pairs(
        (
            (
                ("HYBRID", int(row["n"]), float(row["sigma"])),
                float(row["r_private"]),
            )
            for row in valid
            if row["architecture"] == "HYBRID"
        )
    )
    contrast_cells = CellMeans.from_pairs(
        (
            (
                (str(row["architecture"]), int(row["n"]), float(row["sigma"])),
                float(row["r_q"]),
            )
            for row in valid
            if row["architecture"] in {"HYBRID", "IND"}
        )
    )
    contrast_index = {key: index for index, key in enumerate(contrast_cells.keys)}
    strata = sorted(
        {
            (int(row["n"]), float(row["sigma"]))
            for row in valid
            if row["architecture"] == "HYBRID"
        }
    )

    def contrast_statistic(means: np.ndarray) -> float:
        values = [
            means[contrast_index[("HYBRID", n, sigma)]]
            - means[contrast_index[("IND", n, sigma)]]
            for n, sigma in strata
        ]
        return float(np.mean(values))

    mean_statistic = lambda means: float(np.mean(means))
    rq_obs, rq_boot, rq_jack = _estimate_from_cell_means(
        hybrid_rq,
        mean_statistic,
        resamples,
        _analysis_rng(config.master_seed, "P1", "hybrid-rq"),
    )
    private_obs, private_boot, private_jack = _estimate_from_cell_means(
        hybrid_private,
        mean_statistic,
        resamples,
        _analysis_rng(config.master_seed, "P1", "hybrid-private"),
    )
    contrast_obs, contrast_boot, contrast_jack = _estimate_from_cell_means(
        contrast_cells,
        contrast_statistic,
        resamples,
        _analysis_rng(config.master_seed, "P1", "hybrid-minus-ind"),
    )
    rq_summary = bca_summary(rq_obs, rq_boot, rq_jack)
    private_summary = bca_summary(private_obs, private_boot, private_jack)
    contrast_summary = bca_summary(contrast_obs, contrast_boot, contrast_jack)
    rq_upper = float(config.data["blocks"]["P1"]["r_q_upper"])
    gates = {
        "hybrid_r_q_below_1": _gate(
            rq_summary,
            rq_boot,
            rq_upper,
            "less",
            rq_summary["upper_95_one_sided"] < rq_upper,
            f"BCa upper 95% bound < {rq_upper}",
        ),
        "private_retention_above_0_25": _gate(
            private_summary,
            private_boot,
            float(config.data["blocks"]["P1"]["r_private_lower"]),
            "greater",
            private_summary["lower_95_one_sided"]
            > float(config.data["blocks"]["P1"]["r_private_lower"]),
            "BCa lower 95% bound > 0.25",
        ),
        "hybrid_outperforms_ind": _gate(
            contrast_summary,
            contrast_boot,
            0.0,
            "less",
            contrast_summary["upper_95_one_sided"] < 0.0,
            "BCa upper 95% bound of HYBRID−IND rQ < 0",
        ),
    }
    observed_means = contrast_cells.observed
    favorable = int(sum(
        observed_means[contrast_index[("HYBRID", n, sigma)]]
        < observed_means[contrast_index[("IND", n, sigma)]]
        for n, sigma in strata
    ))
    fraction = favorable / len(strata)
    directional_minimum = float(config.data["analysis"]["directional_cell_fraction"])
    threshold_pass = (
        all(gate["threshold_pass"] for gate in gates.values())
        and fraction >= directional_minimum
        and failure_count == 0
    )
    return {
        "prediction": "P1",
        "gates": gates,
        "directional_cells": {
            "favorable": favorable,
            "total": len(strata),
            "fraction": fraction,
            "minimum": directional_minimum,
            "pass": fraction >= directional_minimum,
        },
        "primary_execution_failures": failure_count,
        "raw_p": max(gate["raw_p"] for gate in gates.values()),
        "threshold_pass": threshold_pass,
    }


def _p2(
    config: Any,
    rows: Sequence[dict[str, Any]],
    resamples: int,
    failure_count: int,
) -> dict[str, Any]:
    valid = _valid_rows(rows, "P2")
    cells = CellMeans.from_pairs(
        (
            (
                (
                    int(row["n"]),
                    str(row["topology"]),
                    float(row["translation_bias"]),
                ),
                float(row["repair_cost"]),
            )
            for row in valid
        )
    )
    h_by_key: dict[tuple[Any, ...], list[float]] = {}
    for row in valid:
        key = (
            int(row["n"]),
            str(row["topology"]),
            float(row["translation_bias"]),
        )
        h_by_key.setdefault(key, []).append(float(row["h_c"]))
    h_c = np.asarray([np.mean(h_by_key[key]) for key in cells.keys], dtype=float)
    n_values = np.asarray([key[0] for key in cells.keys], dtype=float)
    topologies = np.asarray([key[1] for key in cells.keys], dtype=object)
    biases = np.asarray([key[2] for key in cells.keys], dtype=float)

    def rho_statistic(means: np.ndarray) -> float:
        return spearman_rho(h_c, means)

    def delta_statistic(means: np.ndarray) -> float:
        return out_of_sample_delta_r2(
            means, h_c, n_values, topologies, biases
        )

    bootstrap_cells = cells.bootstrap(
        resamples, _analysis_rng(config.master_seed, "P2", "cell-means")
    )
    rho_observed = rho_statistic(cells.observed)
    delta_observed = delta_statistic(cells.observed)
    rho_bootstrap = np.asarray(
        [rho_statistic(sample) for sample in bootstrap_cells], dtype=float
    )
    delta_bootstrap = np.asarray(
        [delta_statistic(sample) for sample in bootstrap_cells], dtype=float
    )
    rho_jackknife = cells.jackknife(rho_statistic)
    delta_jackknife = cells.jackknife(delta_statistic)
    rho_summary = bca_summary(rho_observed, rho_bootstrap, rho_jackknife)
    delta_summary = bca_summary(
        delta_observed, delta_bootstrap, delta_jackknife
    )
    rho_lower = float(config.data["blocks"]["P2"]["spearman_lower"])
    delta_lower = float(config.data["blocks"]["P2"]["delta_r2_lower"])
    gates = {
        "spearman_above_0_20": _gate(
            rho_summary,
            rho_bootstrap,
            rho_lower,
            "greater",
            rho_summary["lower_95_one_sided"] > rho_lower,
            "BCa lower 95% bound of Spearman ρ > 0.20",
        ),
        "out_of_sample_delta_r2_above_0_02": _gate(
            delta_summary,
            delta_bootstrap,
            delta_lower,
            "greater",
            delta_observed > delta_lower,
            "point estimate of four-fold out-of-sample ΔR² > 0.02",
        ),
    }
    favorable = 0
    strata = sorted(set(zip(n_values, topologies, strict=True)))
    for n_value, topology in strata:
        mask = (n_values == n_value) & (topologies == topology)
        favorable += int(spearman_rho(h_c[mask], cells.observed[mask]) > 0)
    fraction = favorable / len(strata)
    directional_minimum = float(config.data["analysis"]["directional_cell_fraction"])
    threshold_pass = (
        all(gate["threshold_pass"] for gate in gates.values())
        and fraction >= directional_minimum
        and failure_count == 0
    )
    return {
        "prediction": "P2",
        "gates": gates,
        "directional_cells": {
            "unit": "N × topology strata",
            "favorable": favorable,
            "total": len(strata),
            "fraction": fraction,
            "minimum": directional_minimum,
            "pass": fraction >= directional_minimum,
        },
        "fixed_out_of_sample_rule": (
            "four folds grouped by translation-bias level; controls are categorical "
            "N and topology; the full model adds standardized Hc"
        ),
        "primary_execution_failures": failure_count,
        "raw_p": max(gate["raw_p"] for gate in gates.values()),
        "threshold_pass": threshold_pass,
    }


def _p3(
    config: Any,
    rows: Sequence[dict[str, Any]],
    resamples: int,
    failure_count: int,
) -> dict[str, Any]:
    valid = _valid_rows(rows, "P3")
    cells = CellMeans.from_pairs(
        (
            (
                (
                    str(row["architecture"]),
                    str(row["condition"]),
                    int(row["n"]),
                    float(row["snr"]),
                ),
                float(bool(row["recovered"]))
                if row["condition"] == "event"
                else float(bool(row["false_positive"])),
            )
            for row in valid
            if (
                row["architecture"] in {"HYBRID", "MEAN"}
                and row["condition"] == "event"
            )
            or (
                row["architecture"] == "HYBRID"
                and row["condition"] == "no_event"
            )
        )
    )
    index = {key: position for position, key in enumerate(cells.keys)}
    strata = sorted(
        {
            (int(row["n"]), float(row["snr"]))
            for row in valid
            if row["architecture"] == "HYBRID" and row["condition"] == "event"
        }
    )

    def deltas(means: np.ndarray) -> np.ndarray:
        return np.asarray(
            [
                means[index[("HYBRID", "event", n, snr)]]
                - means[index[("MEAN", "event", n, snr)]]
                for n, snr in strata
            ],
            dtype=float,
        )

    def mean_delta(means: np.ndarray) -> float:
        return float(np.mean(deltas(means)))

    def median_delta(means: np.ndarray) -> float:
        return float(np.median(deltas(means)))

    def hybrid_fpr(means: np.ndarray) -> float:
        return float(
            np.mean(
                [
                    means[index[("HYBRID", "no_event", n, snr)]]
                    for n, snr in strata
                ]
            )
        )

    bootstrap_cells = cells.bootstrap(
        resamples, _analysis_rng(config.master_seed, "P3", "cell-means")
    )
    observed_means = cells.observed
    mean_observed = mean_delta(observed_means)
    median_observed = median_delta(observed_means)
    fpr_observed = hybrid_fpr(observed_means)
    mean_bootstrap = np.asarray(
        [mean_delta(sample) for sample in bootstrap_cells], dtype=float
    )
    median_bootstrap = np.asarray(
        [median_delta(sample) for sample in bootstrap_cells], dtype=float
    )
    fpr_bootstrap = np.asarray(
        [hybrid_fpr(sample) for sample in bootstrap_cells], dtype=float
    )
    mean_summary = bca_summary(
        mean_observed, mean_bootstrap, cells.jackknife(mean_delta)
    )
    median_summary = bca_summary(
        median_observed, median_bootstrap, cells.jackknife(median_delta)
    )
    fpr_summary = bca_summary(
        fpr_observed, fpr_bootstrap, cells.jackknife(hybrid_fpr)
    )
    median_lower = float(config.data["blocks"]["P3"]["recall_gain_lower"])
    fpr_upper = float(config.data["blocks"]["P3"]["false_positive_upper"])
    gates = {
        "mean_recall_gain_above_0": _gate(
            mean_summary,
            mean_bootstrap,
            0.0,
            "greater",
            mean_summary["lower_95_one_sided"] > 0.0,
            "BCa lower 95% bound of HYBRID−MEAN recall > 0",
        ),
        "median_recall_gain_at_least_0_10": _gate(
            median_summary,
            median_bootstrap,
            median_lower,
            "greater",
            median_observed >= median_lower,
            "median cell recall gain ≥ 0.10",
        ),
        "hybrid_fpr_at_most_0_05": _gate(
            fpr_summary,
            fpr_bootstrap,
            fpr_upper,
            "less",
            fpr_observed <= fpr_upper,
            "equal-cell-weighted HYBRID no-event FPR ≤ 0.05",
        ),
    }
    favorable = int(np.sum(deltas(observed_means) > 0))
    fraction = favorable / len(strata)
    directional_minimum = float(config.data["analysis"]["directional_cell_fraction"])
    threshold_pass = (
        all(gate["threshold_pass"] for gate in gates.values())
        and fraction >= directional_minimum
        and failure_count == 0
    )
    return {
        "prediction": "P3",
        "gates": gates,
        "directional_cells": {
            "unit": "N × SNR strata",
            "favorable": favorable,
            "total": len(strata),
            "fraction": fraction,
            "minimum": directional_minimum,
            "pass": fraction >= directional_minimum,
        },
        "primary_execution_failures": failure_count,
        "raw_p": max(gate["raw_p"] for gate in gates.values()),
        "threshold_pass": threshold_pass,
    }


def _bootstrap_quantiles(
    groups: list[np.ndarray],
    quantiles: Sequence[float],
    resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    result = np.empty((resamples, len(quantiles)), dtype=float)
    batch_size = 256
    for start in range(0, resamples, batch_size):
        stop = min(start + batch_size, resamples)
        sampled_parts = []
        for values in groups:
            indices = rng.integers(0, len(values), size=(stop - start, len(values)))
            sampled_parts.append(values[indices])
        pooled = np.concatenate(sampled_parts, axis=1)
        result[start:stop] = np.quantile(
            pooled, quantiles, axis=1
        ).T
    return result


def _quantile_jackknife(groups: list[np.ndarray], quantile: float) -> np.ndarray:
    pooled = np.concatenate(groups)
    estimates = np.empty(len(pooled), dtype=float)
    for index in range(len(pooled)):
        estimates[index] = float(np.quantile(np.delete(pooled, index), quantile))
    return estimates


def _p4(
    config: Any,
    rows: Sequence[dict[str, Any]],
    resamples: int,
    failure_count: int,
) -> dict[str, Any]:
    valid = [
        row
        for row in _valid_rows(rows, "P4")
        if row["architecture"] == "HYBRID"
    ]
    attacks = [str(value) for value in config.data["blocks"]["P4"]["attacks"]]
    median_upper = float(
        config.data["blocks"]["P4"]["median_displacement_upper"]
    )
    p95_upper = float(config.data["blocks"]["P4"]["p95_displacement_upper"])
    attack_results: dict[str, Any] = {}
    all_gate_p: list[float] = []
    cell_passes = 0
    cell_total = 0
    for attack in attacks:
        attack_rows = [row for row in valid if row["attack"] == attack]
        grouped: dict[int, list[float]] = {}
        for row in attack_rows:
            grouped.setdefault(int(row["n"]), []).append(float(row["delta_omega"]))
        groups = [
            np.asarray(grouped[key], dtype=float)
            for key in sorted(grouped)
        ]
        if not groups or any(len(group) < 2 for group in groups):
            raise AnalysisError(f"P4 attack {attack} lacks valid replicated cells")
        pooled = np.concatenate(groups)
        observed = np.quantile(pooled, [0.5, 0.95])
        bootstrap = _bootstrap_quantiles(
            groups,
            [0.5, 0.95],
            resamples,
            _analysis_rng(config.master_seed, "P4", attack),
        )
        median_summary = bca_summary(
            float(observed[0]),
            bootstrap[:, 0],
            _quantile_jackknife(groups, 0.5),
        )
        p95_summary = bca_summary(
            float(observed[1]),
            bootstrap[:, 1],
            _quantile_jackknife(groups, 0.95),
        )
        gates = {
            "median_at_most_0_15": _gate(
                median_summary,
                bootstrap[:, 0],
                median_upper,
                "less",
                float(observed[0]) <= median_upper,
                "pooled equal-cell-weight median ΔΩ ≤ 0.15",
            ),
            "p95_at_most_0_30": _gate(
                p95_summary,
                bootstrap[:, 1],
                p95_upper,
                "less",
                float(observed[1]) <= p95_upper,
                "pooled equal-cell-weight P95 ΔΩ ≤ 0.30",
            ),
        }
        all_gate_p.extend(gate["raw_p"] for gate in gates.values())
        attack_results[attack] = {
            "gates": gates,
            "threshold_pass": all(
                gate["threshold_pass"] for gate in gates.values()
            ),
        }
        for n_value, values in sorted(grouped.items()):
            array = np.asarray(values, dtype=float)
            cell_total += 1
            cell_passes += bool(
                float(np.median(array)) <= median_upper
                and float(np.quantile(array, 0.95)) <= p95_upper
            )
    worst_attack = max(
        attacks,
        key=lambda attack: (
            max(
                attack_results[attack]["gates"]["median_at_most_0_15"]["estimate"]
                / median_upper,
                attack_results[attack]["gates"]["p95_at_most_0_30"]["estimate"]
                / p95_upper,
            ),
            attack,
        ),
    )
    fraction = cell_passes / cell_total
    directional_minimum = float(config.data["analysis"]["directional_cell_fraction"])
    threshold_pass = (
        all(result["threshold_pass"] for result in attack_results.values())
        and fraction >= directional_minimum
        and failure_count == 0
    )
    return {
        "prediction": "P4",
        "attacks": attack_results,
        "worst_attack": {
            "name": worst_attack,
            "selection_rule": (
                "largest of median/0.15 and P95/0.30; lexical tie-break"
            ),
        },
        "directional_cells": {
            "unit": "N × attack cells meeting both bounds",
            "favorable": cell_passes,
            "total": cell_total,
            "fraction": fraction,
            "minimum": directional_minimum,
            "pass": fraction >= directional_minimum,
        },
        "primary_execution_failures": failure_count,
        "raw_p": max(all_gate_p),
        "threshold_pass": threshold_pass,
    }


def _bootstrap_regression(
    groups: list[tuple[np.ndarray, np.ndarray]],
    resamples: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    slopes = np.empty(resamples, dtype=float)
    r_squared = np.empty(resamples, dtype=float)
    batch_size = 256
    for start in range(0, resamples, batch_size):
        stop = min(start + batch_size, resamples)
        x_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        for x_values, y_values in groups:
            indices = rng.integers(
                0, len(x_values), size=(stop - start, len(x_values))
            )
            x_parts.append(x_values[indices])
            y_parts.append(y_values[indices])
        x = np.concatenate(x_parts, axis=1)
        y = np.concatenate(y_parts, axis=1)
        x_centered = x - np.mean(x, axis=1, keepdims=True)
        y_centered = y - np.mean(y, axis=1, keepdims=True)
        ssx = np.sum(x_centered**2, axis=1)
        ssy = np.sum(y_centered**2, axis=1)
        cross = np.sum(x_centered * y_centered, axis=1)
        slopes[start:stop] = cross / ssx
        r_squared[start:stop] = (cross**2) / (ssx * ssy)
    return slopes, r_squared


def _regression_jackknife(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    count = len(x)
    sx = float(np.sum(x))
    sy = float(np.sum(y))
    sxx = float(np.dot(x, x))
    syy = float(np.dot(y, y))
    sxy = float(np.dot(x, y))
    n = count - 1
    sx_i = sx - x
    sy_i = sy - y
    ssx = (sxx - x * x) - sx_i * sx_i / n
    ssy = (syy - y * y) - sy_i * sy_i / n
    cross = (sxy - x * y) - sx_i * sy_i / n
    slopes = cross / ssx
    r_squared = (cross**2) / (ssx * ssy)
    return slopes, r_squared


def _p5(
    config: Any,
    rows: Sequence[dict[str, Any]],
    resamples: int,
    failure_count: int,
) -> dict[str, Any]:
    valid = _valid_rows(rows, "P5")
    grouped: dict[tuple[int, str], list[tuple[float, float]]] = {}
    for row in valid:
        lambda2 = float(row["lambda2"])
        tau = float(row["tau"])
        if lambda2 <= 0 or tau <= 0:
            continue
        key = (int(row["n"]), str(row["topology"]))
        grouped.setdefault(key, []).append(
            (math.log(1.0 / lambda2), math.log(tau))
        )
    groups = [
        (
            np.asarray([pair[0] for pair in grouped[key]], dtype=float),
            np.asarray([pair[1] for pair in grouped[key]], dtype=float),
        )
        for key in sorted(grouped)
    ]
    if not groups or any(len(group[0]) < 2 for group in groups):
        raise AnalysisError("P5 lacks valid replicated spectral cells")
    x = np.concatenate([group[0] for group in groups])
    y = np.concatenate([group[1] for group in groups])
    slope, r_squared = simple_regression(x, y)
    slope_bootstrap, r2_bootstrap = _bootstrap_regression(
        groups,
        resamples,
        _analysis_rng(config.master_seed, "P5", "spectral-regression"),
    )
    slope_jackknife, r2_jackknife = _regression_jackknife(x, y)
    slope_summary = bca_summary(
        slope, slope_bootstrap, slope_jackknife
    )
    r2_summary = bca_summary(
        r_squared, r2_bootstrap, r2_jackknife
    )
    lower, upper = (
        float(value) for value in config.data["blocks"]["P5"]["slope_interval"]
    )
    r2_lower = float(config.data["blocks"]["P5"]["r_squared_lower"])
    gates = {
        "slope_in_interval": {
            **slope_summary,
            "criterion": f"point slope in [{lower}, {upper}]",
            "threshold_pass": lower <= slope <= upper,
        },
        "r_squared_at_least_0_80": {
            **r2_summary,
            "criterion": f"point R² ≥ {r2_lower}",
            "threshold_pass": r_squared >= r2_lower,
        },
    }
    return {
        "prediction": "P5",
        "role": "positive_control",
        "gates": gates,
        "primary_execution_failures": failure_count,
        "threshold_pass": (
            all(gate["threshold_pass"] for gate in gates.values())
            and failure_count == 0
        ),
    }


def verify_freeze(
    root: Path,
    config_path: Path,
    attestation_path: Path | None,
    analysis_attestation_path: Path | None,
    enforce: bool,
) -> IntegrityResult:
    config_hash = sha256_file(config_path)
    if not enforce:
        return IntegrityResult(config_hash, None, None, None, None, 0, None)
    if attestation_path is None:
        raise AnalysisError("confirmatory analysis requires --attestation")
    if analysis_attestation_path is None:
        raise AnalysisError(
            "confirmatory analysis requires --analysis-attestation"
        )
    attestation_path = attestation_path.resolve()
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    if config_hash != attestation.get("config_sha256"):
        raise AnalysisError("config SHA-256 does not match the public attestation")
    manifest_path = root / "content_manifest.json"
    manifest_hash = sha256_file(manifest_path)
    if manifest_hash != attestation.get("content_manifest_sha256"):
        raise AnalysisError("content manifest SHA-256 does not match the attestation")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified = 0
    for relative, expected in manifest["files"].items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise AnalysisError(f"frozen file hash mismatch: {relative}")
        verified += 1
    if sha256_file(root / "environment.lock") != attestation.get(
        "environment_lock_sha256"
    ):
        raise AnalysisError("environment.lock hash mismatch")
    if sha256_file(root / "artifacts" / "seeds.csv.gz") != attestation.get(
        "seed_schedule_sha256"
    ):
        raise AnalysisError("seed schedule hash mismatch")
    environment = attestation["environment"]
    libc_name, libc_version = platform.libc_ver()
    runtime_libc = f"{libc_name}-{libc_version}"
    runtime_matches = (
        environment["python"] == f"{platform.python_implementation()} {platform.python_version()}"
        and environment["numpy"] == np.__version__
        and environment["pyyaml"] == yaml.__version__
        and environment["os"] == platform.system()
        and environment["architecture"] == platform.machine()
        and environment["libc"] == runtime_libc
    )
    if not runtime_matches:
        raise AnalysisError("runtime does not match the publicly attested environment")
    analysis_attestation_path = analysis_attestation_path.resolve()
    analysis_attestation = json.loads(
        analysis_attestation_path.read_text(encoding="utf-8")
    )
    analysis_manifest_path = root / "analysis_engine_manifest.json"
    analysis_addendum_path = root / "analysis_addendum.json"
    engine_path = Path(__file__).resolve()
    if sha256_file(engine_path) != analysis_attestation.get(
        "analysis_engine_sha256"
    ):
        raise AnalysisError("analysis engine hash mismatch")
    if sha256_file(analysis_addendum_path) != analysis_attestation.get(
        "analysis_addendum_sha256"
    ):
        raise AnalysisError("analysis addendum hash mismatch")
    analysis_manifest_hash = sha256_file(analysis_manifest_path)
    if analysis_manifest_hash != analysis_attestation.get(
        "analysis_engine_manifest_sha256"
    ):
        raise AnalysisError("analysis engine manifest hash mismatch")
    analysis_manifest = json.loads(
        analysis_manifest_path.read_text(encoding="utf-8")
    )
    analysis_verified = 0
    for relative, expected in analysis_manifest["files"].items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise AnalysisError(f"analysis file hash mismatch: {relative}")
        analysis_verified += 1
    cross_checks = {
        "original_config_sha256": config_hash,
        "original_environment_lock_sha256": attestation[
            "environment_lock_sha256"
        ],
        "original_seed_schedule_sha256": attestation["seed_schedule_sha256"],
        "original_simulator_commit": attestation["simulator_commit"],
        "registration_id": attestation["registration_id"],
    }
    for field, expected in cross_checks.items():
        if analysis_attestation.get(field) != expected:
            raise AnalysisError(
                f"analysis attestation disagrees with original freeze: {field}"
            )
    if analysis_attestation.get("confirmatory_results_inspected") is not False:
        raise AnalysisError(
            "analysis attestation does not assert a pre-result freeze"
        )
    if analysis_attestation.get("confirmatory_trajectories_executed") is not False:
        raise AnalysisError(
            "analysis attestation does not assert a pre-execution freeze"
        )
    return IntegrityResult(
        config_sha256=config_hash,
        attestation_sha256=sha256_file(attestation_path),
        content_manifest_sha256=manifest_hash,
        analysis_attestation_sha256=sha256_file(analysis_attestation_path),
        analysis_engine_commit=str(analysis_attestation["analysis_engine_commit"]),
        frozen_files_verified=verified + analysis_verified,
        runtime_matches_lock=runtime_matches,
    )


def _discover_inputs(inputs: Sequence[Path], raw_name: str) -> list[Path]:
    discovered: set[Path] = set()
    for supplied in inputs:
        path = supplied.resolve()
        if path.is_file():
            discovered.add(path)
        elif path.is_dir():
            direct = path / raw_name
            if direct.is_file():
                discovered.add(direct)
            else:
                discovered.update(candidate.resolve() for candidate in path.rglob(raw_name))
        else:
            raise AnalysisError(f"input does not exist: {path}")
    if not discovered:
        raise AnalysisError("no raw JSONL inputs were found")
    return sorted(discovered)


def _load_rows(paths: Sequence[Path], raw_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []
    for path in paths:
        record: dict[str, Any] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        summary_path = path.parent / "summary.json"
        if path.name == raw_name and summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary.get("raw_sha256") != record["sha256"]:
                raise AnalysisError(f"raw output hash disagrees with summary: {path}")
            record["summary_sha256"] = sha256_file(summary_path)
        with path.open("r", encoding="utf-8") as handle:
            before = len(rows)
            for line_number, line in enumerate(handle, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AnalysisError(
                        f"invalid JSON at {path}:{line_number}: {exc.msg}"
                    ) from exc
                row["_source"] = str(path)
                row["_line"] = line_number
                rows.append(row)
            record["rows"] = len(rows) - before
        input_records.append(record)
    return rows, input_records


def validate_schedule(
    config: Any,
    rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int], list[dict[str, Any]]]:
    expected: dict[tuple[str, str, int], tuple[int, dict[str, Any]]] = {}
    for block in BLOCKS:
        for cell in enumerate_cells(config, block):
            label = cell_label(block, cell)
            for replicate in range(config.replicates):
                key = (block, label, replicate)
                expected[key] = (
                    deterministic_seed(config.master_seed, label, replicate),
                    cell,
                )
    seen: set[tuple[str, str, int]] = set()
    by_block: dict[str, list[dict[str, Any]]] = {block: [] for block in BLOCKS}
    failure_counts = {block: 0 for block in BLOCKS}
    deviations: list[dict[str, Any]] = []
    for row in rows:
        source = f"{row.get('_source')}:{row.get('_line')}"
        required = {
            "registration_id",
            "confirmatory",
            "block",
            "cell",
            "replicate",
            "seed",
            "status",
        }
        missing = sorted(required.difference(row))
        if missing:
            raise AnalysisError(f"row missing {missing} at {source}")
        block = str(row["block"])
        if block not in by_block:
            raise AnalysisError(f"unknown block {block!r} at {source}")
        key = (block, str(row["cell"]), int(row["replicate"]))
        if key in seen:
            raise AnalysisError(f"duplicate schedule row {key} at {source}")
        if key not in expected:
            raise AnalysisError(f"unexpected schedule row {key} at {source}")
        seen.add(key)
        expected_seed, cell = expected[key]
        if int(row["seed"]) != expected_seed:
            raise AnalysisError(f"seed mismatch for {key} at {source}")
        if row["registration_id"] != config.data["registration_id"]:
            raise AnalysisError(f"registration_id mismatch at {source}")
        if bool(row["confirmatory"]) != config.confirmatory:
            raise AnalysisError(f"confirmatory flag mismatch at {source}")
        for name, expected_value in cell.items():
            if row.get(name) != expected_value:
                raise AnalysisError(f"cell field {name} mismatch for {key} at {source}")
        effective_status = str(row["status"])
        if effective_status == "ok":
            nonfinite = [
                metric
                for metric in REQUIRED_METRICS[block]
                if not _finite_number(row.get(metric))
            ]
            if nonfinite:
                effective_status = "failed"
                deviations.append(
                    {
                        "type": "nonfinite_primary_outcome",
                        "block": block,
                        "cell": row["cell"],
                        "replicate": row["replicate"],
                        "seed": row["seed"],
                        "metrics": nonfinite,
                    }
                )
        elif effective_status != "failed":
            raise AnalysisError(f"unknown row status {effective_status!r} at {source}")
        row["_effective_status"] = effective_status
        if effective_status == "failed":
            failure_counts[block] += 1
        by_block[block].append(row)
    missing_keys = sorted(set(expected).difference(seen))
    if missing_keys:
        preview = ", ".join(str(key) for key in missing_keys[:3])
        raise AnalysisError(
            f"incomplete schedule: {len(missing_keys)} rows missing; first: {preview}"
        )
    if len(seen) != len(expected):
        raise AnalysisError("schedule cardinality mismatch")
    for block, count in failure_counts.items():
        if count:
            deviations.append(
                {
                    "type": "execution_failures",
                    "block": block,
                    "count": count,
                    "decision_effect": (
                        "primary-arm failures force failure; non-primary-arm "
                        "failures remain disclosed"
                    ),
                }
            )
    return by_block, failure_counts, deviations


def _failed_block(block: str, failure_count: int, exc: Exception) -> dict[str, Any]:
    return {
        "prediction": block,
        "analysis_error": f"{type(exc).__name__}: {exc}",
        "primary_execution_failures": failure_count,
        "raw_p": 1.0 if block != "P5" else None,
        "threshold_pass": False,
    }


def analyze_rows(
    config: Any,
    by_block: dict[str, list[dict[str, Any]]],
    failure_counts: dict[str, int],
    resamples: int,
) -> dict[str, dict[str, Any]]:
    analyzers = {"P1": _p1, "P2": _p2, "P3": _p3, "P4": _p4, "P5": _p5}
    results: dict[str, dict[str, Any]] = {}
    for block in BLOCKS:
        primary_failures = _primary_failure_count(block, by_block[block])
        try:
            results[block] = analyzers[block](
                config, by_block[block], resamples, primary_failures
            )
        except Exception as exc:
            results[block] = _failed_block(block, primary_failures, exc)
        results[block]["all_arm_execution_failures"] = failure_counts[block]
    alpha = float(config.data["analysis"]["familywise_alpha"])
    holm = _holm_adjust(
        {block: float(results[block]["raw_p"]) for block in BLOCKS[:4]},
        alpha,
    )
    for block in BLOCKS[:4]:
        results[block]["multiplicity"] = holm[block]
        results[block]["decision"] = (
            "PASS"
            if results[block]["threshold_pass"] and holm[block]["rejected"]
            else "FAIL"
        )
    results["P5"]["decision"] = (
        "PASS" if results["P5"]["threshold_pass"] else "FAIL"
    )
    return results


def _format_number(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return str(value)
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.6g}"
    return str(value)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# CCSU Multi-Observer confirmatory analysis",
        "",
        f"- Registration: `{report['registration_id']}`",
        f"- Engine: `{report['analysis_engine_version']}`",
        f"- Confirmatory input: `{str(report['confirmatory']).lower()}`",
        f"- Bootstrap resamples: `{report['analysis']['bootstrap_resamples']}`",
        f"- Config SHA-256: `{report['integrity']['config_sha256']}`",
        "",
        "## Decisions",
        "",
        "| Prediction | Decision | Thresholds | Raw p | Holm p |",
        "|---|---:|---:|---:|---:|",
    ]
    for block in BLOCKS:
        result = report["predictions"][block]
        raw_p = result.get("raw_p", "—")
        holm_p = result.get("multiplicity", {}).get("holm_adjusted_p", "—")
        lines.append(
            f"| {block} | **{result['decision']}** | "
            f"{'pass' if result['threshold_pass'] else 'fail'} | "
            f"{_format_number(raw_p)} | {_format_number(holm_p)} |"
        )
    lines.extend(
        [
            "",
            "There is no global CCSU score. P1–P5 retain independent decisions; "
            "P5 is a positive control and is not included in Holm correction.",
            "",
            "## Primary estimands",
            "",
        ]
    )
    for block in BLOCKS:
        result = report["predictions"][block]
        lines.append(f"### {block}")
        lines.append("")
        if "analysis_error" in result:
            lines.append(f"Analysis error: `{result['analysis_error']}`")
            lines.append("")
            continue
        gate_containers: list[tuple[str, dict[str, Any]]] = []
        if block == "P4":
            for attack, attack_result in result["attacks"].items():
                for name, gate in attack_result["gates"].items():
                    gate_containers.append((f"{attack}: {name}", gate))
        else:
            gate_containers.extend(result.get("gates", {}).items())
        lines.extend(
            [
                "| Gate | Estimate | Lower 95% | Upper 95% | Pass |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for name, gate in gate_containers:
            lines.append(
                f"| {name} | {_format_number(gate['estimate'])} | "
                f"{_format_number(gate.get('lower_95_one_sided', '—'))} | "
                f"{_format_number(gate.get('upper_95_one_sided', '—'))} | "
                f"{'yes' if gate['threshold_pass'] else 'no'} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Deviations and execution failures",
            "",
            f"Recorded deviations: `{report['deviation_count']}`. "
            "See `deviations.jsonl`; any primary execution failure forces the "
            "corresponding prediction to fail.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def run_analysis(
    config_path: Path,
    inputs: Sequence[Path],
    output: Path,
    attestation_path: Path | None = None,
    analysis_attestation_path: Path | None = None,
    allow_nonconfirmatory: bool = False,
    bootstrap_resamples: int | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    if config.confirmatory and allow_nonconfirmatory:
        raise AnalysisError("--allow-nonconfirmatory cannot be used with a confirmatory config")
    if not config.confirmatory and not allow_nonconfirmatory:
        raise AnalysisError(
            "non-confirmatory input requires the explicit --allow-nonconfirmatory flag"
        )
    root = config.path.parent
    integrity = verify_freeze(
        root,
        config.path,
        attestation_path,
        analysis_attestation_path,
        enforce=config.confirmatory,
    )
    resamples = (
        int(config.data["analysis"]["bootstrap_resamples"])
        if bootstrap_resamples is None
        else int(bootstrap_resamples)
    )
    if resamples < 100:
        raise AnalysisError("bootstrap_resamples must be at least 100")
    if config.confirmatory and resamples != int(
        config.data["analysis"]["bootstrap_resamples"]
    ):
        raise AnalysisError("confirmatory bootstrap count cannot override config.yaml")
    raw_name = str(config.data["analysis"]["raw_output"])
    input_paths = _discover_inputs(inputs, raw_name)
    rows, input_records = _load_rows(input_paths, raw_name)
    by_block, failure_counts, deviations = validate_schedule(config, rows)
    primary_failure_counts = {
        block: _primary_failure_count(block, by_block[block]) for block in BLOCKS
    }
    predictions = analyze_rows(config, by_block, failure_counts, resamples)
    report: dict[str, Any] = {
        "schema_version": 1,
        "registration_id": config.data["registration_id"],
        "confirmatory": config.confirmatory,
        "analysis_engine_version": ANALYSIS_ENGINE_VERSION,
        "analysis": {
            "bootstrap": "BCa stratified by preregistered cell",
            "bootstrap_resamples": resamples,
            "one_sided_confidence": 0.95,
            "primary_p": "maximum one-sided centered-bootstrap p across gates",
            "multiplicity": "Holm-Bonferroni over P1-P4",
            "familywise_alpha": float(
                config.data["analysis"]["familywise_alpha"]
            ),
            "equal_cell_weighting": True,
        },
        "integrity": {
            "config_sha256": integrity.config_sha256,
            "attestation_sha256": integrity.attestation_sha256,
            "content_manifest_sha256": integrity.content_manifest_sha256,
            "analysis_attestation_sha256": integrity.analysis_attestation_sha256,
            "analysis_engine_commit": integrity.analysis_engine_commit,
            "frozen_files_verified": integrity.frozen_files_verified,
            "runtime_matches_lock": integrity.runtime_matches_lock,
            "analysis_engine_sha256": sha256_file(Path(__file__)),
        },
        "inputs": input_records,
        "schedule": {
            "expected_rows": sum(len(value) for value in by_block.values()),
            "observed_rows": len(rows),
            "rows_by_block": {
                block: len(by_block[block]) for block in BLOCKS
            },
            "execution_failures_by_block": failure_counts,
            "primary_execution_failures_by_block": primary_failure_counts,
            "complete": True,
        },
        "predictions": predictions,
        "deviation_count": len(deviations),
        "global_score": None,
        "global_score_reason": "not preregistered; predictions are decided independently",
    }
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {output}")
    output.mkdir(parents=True)
    report_path = output / "analysis_report.json"
    markdown_path = output / "analysis_report.md"
    deviations_path = output / "deviations.jsonl"
    _write_new(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write_new(markdown_path, _markdown_report(report))
    _write_new(
        deviations_path,
        "".join(
            json.dumps(deviation, sort_keys=True, separators=(",", ":")) + "\n"
            for deviation in deviations
        ),
    )
    manifest = {
        "schema_version": 1,
        "registration_id": config.data["registration_id"],
        "analysis_engine_version": ANALYSIS_ENGINE_VERSION,
        "files": {
            "analysis_report.json": sha256_file(report_path),
            "analysis_report.md": sha256_file(markdown_path),
            "deviations.jsonl": sha256_file(deviations_path),
        },
        "inputs": {
            str(path): sha256_file(path) for path in input_paths
        },
    }
    manifest_path = output / "analysis_manifest.json"
    _write_new(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {
        "output": str(output),
        "report_sha256": sha256_file(report_path),
        "manifest_sha256": sha256_file(manifest_path),
        "decisions": {
            block: predictions[block]["decision"] for block in BLOCKS
        },
        "confirmatory": config.confirmatory,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the complete CCSU multi-observer P1-P5 run"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--input",
        required=True,
        action="append",
        type=Path,
        help="raw JSONL file or directory; repeat for block outputs",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--attestation", type=Path)
    parser.add_argument("--analysis-attestation", type=Path)
    parser.add_argument("--allow-nonconfirmatory", action="store_true")
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        help="non-confirmatory development override only",
    )
    args = parser.parse_args(argv)
    try:
        result = run_analysis(
            config_path=args.config,
            inputs=args.input,
            output=args.output,
            attestation_path=args.attestation,
            analysis_attestation_path=args.analysis_attestation,
            allow_nonconfirmatory=args.allow_nonconfirmatory,
            bootstrap_resamples=args.bootstrap_resamples,
        )
    except (AnalysisError, FileExistsError, OSError, ValueError) as exc:
        print(f"analysis refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
