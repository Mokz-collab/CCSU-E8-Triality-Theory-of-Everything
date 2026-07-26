from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from .core import (
    deterministic_seed,
    load_config,
    make_graph,
    metric_p5,
    sha256_file,
)


ENGINE_VERSION = "1.0.0"


def _load(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config.get("registration_id") != "CCSU-MO-CONTROL-RECOVERY-001":
        raise ValueError("unexpected control-recovery registration_id")
    if config.get("study_class") != "preregistered_control_recovery":
        raise ValueError("unexpected study_class")
    return config


def _normalized_laplacian(adjacency: np.ndarray) -> np.ndarray:
    adjacency = np.asarray(adjacency, dtype=float)
    degree = np.sum(adjacency, axis=1)
    if adjacency.ndim != 2 or adjacency.shape[0] != adjacency.shape[1]:
        raise ValueError("adjacency must be square")
    if np.any(degree <= 0):
        raise ValueError("graph contains an isolated node")
    scale = 1.0 / np.sqrt(degree)
    return np.eye(len(degree)) - scale[:, None] * adjacency * scale[None, :]


def _dispersion(points: np.ndarray) -> float:
    center = np.median(points, axis=0)
    return float(np.median(np.sum((points - center) ** 2, axis=1)))


def _kernel_error(points: np.ndarray, null_vector: np.ndarray) -> float:
    projection = np.outer(null_vector, null_vector @ points)
    return float(np.mean(np.sum((points - projection) ** 2, axis=1)))


def _graph_and_initial(
    n: int,
    topology: str,
    seed: int,
    er_probability: float,
    public_dim: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    rng = np.random.default_rng(seed)
    adjacency, attempts = make_graph(topology, n, rng, er_probability)
    initial = rng.normal(size=(n, public_dim))
    return adjacency, initial, attempts


def _spectral_original_tau(
    laplacian: np.ndarray,
    initial: np.ndarray,
    kappa: float,
    threshold_fraction: float,
    consecutive_needed: int,
    horizon: int,
) -> int:
    values, vectors = np.linalg.eigh(laplacian)
    coefficients = vectors.T @ initial
    initial_dispersion = max(_dispersion(initial), 1e-12)
    threshold = threshold_fraction * initial_dispersion
    multipliers = 1.0 - kappa * values
    consecutive = 0
    for step in range(1, horizon + 1):
        state = vectors @ ((multipliers**step)[:, None] * coefficients)
        if _dispersion(state) <= threshold:
            consecutive += 1
            if consecutive >= consecutive_needed:
                return step - consecutive_needed + 1
        else:
            consecutive = 0
    return horizon


def _floor_ratio(
    laplacian: np.ndarray,
    initial: np.ndarray,
) -> float:
    values, vectors = np.linalg.eigh(laplacian)
    null_vector = vectors[:, int(np.argmin(np.abs(values)))]
    limit = np.outer(null_vector, null_vector @ initial)
    return _dispersion(limit) / max(_dispersion(initial), 1e-12)


def _fiedler_control(
    laplacian: np.ndarray,
    kappa: float,
    threshold_fraction: float,
    consecutive_needed: int,
    horizon: int,
    public_dim: int,
) -> dict[str, float | int | bool]:
    values, vectors = np.linalg.eigh(laplacian)
    lambda2 = float(values[1])
    null_vector = vectors[:, 0]
    fiedler = vectors[:, 1]
    coefficients = np.resize(np.asarray([1.0, -0.5, 2.0]), public_dim)
    state = fiedler[:, None] * coefficients[None, :]
    initial_error = max(_kernel_error(state, null_vector), 1e-15)
    threshold = threshold_fraction * initial_error
    consecutive = 0
    simulated_tau = horizon
    for step in range(1, horizon + 1):
        state = state - kappa * (laplacian @ state)
        if _kernel_error(state, null_vector) <= threshold:
            consecutive += 1
            if consecutive >= consecutive_needed:
                simulated_tau = step - consecutive_needed + 1
                break
        else:
            consecutive = 0
    multiplier = abs(1.0 - kappa * lambda2)
    if not 0.0 < multiplier < 1.0:
        raise ValueError("Fiedler multiplier must lie in (0,1)")
    exact_real_tau = math.log(threshold_fraction) / (2.0 * math.log(multiplier))
    exact_tau = int(math.ceil(exact_real_tau - 1e-12))
    return {
        "lambda2": lambda2,
        "simulated_tau": simulated_tau,
        "exact_tau": exact_tau,
        "exact_real_tau": exact_real_tau,
        "exact_match": simulated_tau == exact_tau,
        "censored": simulated_tau >= horizon,
    }


def _simple_regression(x: Iterable[float], y: Iterable[float]) -> tuple[float, float]:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    x_centered = x_arr - float(np.mean(x_arr))
    y_centered = y_arr - float(np.mean(y_arr))
    ssx = float(x_centered @ x_centered)
    ssy = float(y_centered @ y_centered)
    if len(x_arr) < 3 or ssx <= 0 or ssy <= 0:
        raise ValueError("regression requires at least three varying points")
    cross = float(x_centered @ y_centered)
    return cross / ssx, (cross * cross) / (ssx * ssy)


def _iter_cases(config: dict[str, Any], phase_name: str):
    phase = config[phase_name]
    for n in phase["observer_counts"]:
        for topology in phase["topologies"]:
            for replicate in range(int(phase["replicates_per_cell"])):
                seed = deterministic_seed(
                    int(config["master_seed"]),
                    phase_name,
                    int(n),
                    str(topology),
                    replicate,
                )
                yield int(n), str(topology), replicate, seed


def run(config_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    root = config_path.parent
    config = _load(config_path)
    historical_path = root / config["historical_boundary"]["config"]
    historical = load_config(historical_path)
    if output_dir is None:
        output_dir = root / config["outputs"]["directory"]
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_path = output_dir / config["outputs"]["runs"]
    if runs_path.exists():
        raise FileExistsError(f"refusing to overwrite append-only output: {runs_path}")

    operator = config["operator"]
    kappa = float(operator["coupling_kappa"])
    er_probability = float(operator["er_probability"])
    public_dim = int(operator["public_dim"])
    phase_a = config["phase_a_implementation_equivalence"]
    phase_b = config["phase_b_measurement_audit"]
    phase_c = config["phase_c_recovered_control"]
    counts: dict[str, int] = defaultdict(int)
    failures: dict[str, int] = defaultdict(int)
    phase_a_rows: list[dict[str, Any]] = []
    phase_c_rows: list[dict[str, Any]] = []

    with runs_path.open("x", encoding="utf-8") as handle:
        for n, topology, replicate, seed in _iter_cases(
            config, "phase_a_implementation_equivalence"
        ):
            base = {
                "registration_id": config["registration_id"],
                "phase": "A",
                "n": n,
                "topology": topology,
                "replicate": replicate,
                "seed": seed,
            }
            try:
                adjacency, initial, attempts = _graph_and_initial(
                    n, topology, seed, er_probability, public_dim
                )
                laplacian = _normalized_laplacian(adjacency)
                historical_result = metric_p5(historical, n, topology, seed)
                oracle_tau = _spectral_original_tau(
                    laplacian,
                    initial,
                    kappa,
                    float(phase_a["dispersion_fraction"]),
                    int(phase_a["consecutive_steps"]),
                    int(phase_a["horizon"]),
                )
                oracle_lambda2 = float(np.linalg.eigvalsh(laplacian)[1])
                row = {
                    **base,
                    "status": "ok",
                    "graph_attempts": attempts,
                    "historical_tau": int(historical_result["tau"]),
                    "oracle_tau": oracle_tau,
                    "tau_exact_match": int(historical_result["tau"]) == oracle_tau,
                    "historical_lambda2": float(historical_result["lambda2"]),
                    "oracle_lambda2": oracle_lambda2,
                    "lambda2_abs_error": abs(
                        float(historical_result["lambda2"]) - oracle_lambda2
                    ),
                    "dispersion_floor_ratio": _floor_ratio(laplacian, initial),
                }
            except Exception as exc:
                failures["A"] += 1
                row = {
                    **base,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            phase_a_rows.append(row)
            counts["A"] += 1

        for n, topology, replicate, seed in _iter_cases(
            config, "phase_c_recovered_control"
        ):
            base = {
                "registration_id": config["registration_id"],
                "phase": "C",
                "n": n,
                "topology": topology,
                "replicate": replicate,
                "seed": seed,
            }
            try:
                rng = np.random.default_rng(seed)
                adjacency, attempts = make_graph(topology, n, rng, er_probability)
                laplacian = _normalized_laplacian(adjacency)
                result = _fiedler_control(
                    laplacian,
                    kappa,
                    float(phase_c["kernel_error_fraction"]),
                    int(phase_c["consecutive_steps"]),
                    int(phase_c["horizon"]),
                    public_dim,
                )
                row = {
                    **base,
                    "status": "ok",
                    "graph_attempts": attempts,
                    **result,
                }
            except Exception as exc:
                failures["C"] += 1
                row = {
                    **base,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            phase_c_rows.append(row)
            counts["C"] += 1

    valid_a = [row for row in phase_a_rows if row["status"] == "ok"]
    valid_c = [row for row in phase_c_rows if row["status"] == "ok"]
    exact_a = sum(bool(row["tau_exact_match"]) for row in valid_a) / max(len(valid_a), 1)
    max_lambda_error = max(
        (float(row["lambda2_abs_error"]) for row in valid_a), default=math.inf
    )
    exact_c = sum(bool(row["exact_match"]) for row in valid_c) / max(len(valid_c), 1)
    uncensored_c = sum(not bool(row["censored"]) for row in valid_c) / max(
        len(valid_c), 1
    )

    obstruction = float(phase_b["obstruction_threshold"])
    floor_by_topology: dict[str, dict[str, float | int]] = {}
    for topology in phase_a["topologies"]:
        rows = [row for row in valid_a if row["topology"] == topology]
        obstructed = sum(float(row["dispersion_floor_ratio"]) >= obstruction for row in rows)
        floor_by_topology[str(topology)] = {
            "cases": len(rows),
            "obstructed": obstructed,
            "obstructed_fraction": obstructed / max(len(rows), 1),
            "max_floor_ratio": max(
                (float(row["dispersion_floor_ratio"]) for row in rows), default=math.nan
            ),
        }

    unique_slow: dict[tuple[int, str, float], dict[str, Any]] = {}
    lambda_upper = float(phase_c["slow_mode_lambda2_upper"])
    for row in valid_c:
        if float(row["lambda2"]) <= lambda_upper:
            key = (
                int(row["n"]),
                str(row["topology"]),
                round(float(row["lambda2"]), 12),
            )
            unique_slow[key] = row
    slow_slope, slow_r2 = _simple_regression(
        (math.log(1.0 / float(row["lambda2"])) for row in unique_slow.values()),
        (math.log(float(row["simulated_tau"])) for row in unique_slow.values()),
    )

    gates_a = phase_a["gates"]
    gates_c = phase_c["gates"]
    slope_low, slope_high = (float(value) for value in gates_c["slow_mode_slope_interval"])
    phase_a_pass = (
        failures["A"] == 0
        and exact_a >= float(gates_a["tau_exact_match_fraction"])
        and max_lambda_error <= float(gates_a["lambda2_max_abs_error"])
    )
    phase_c_pass = (
        failures["C"] == 0
        and exact_c >= float(gates_c["tau_exact_match_fraction"])
        and uncensored_c >= float(gates_c["uncensored_fraction"])
        and slope_low <= slow_slope <= slope_high
        and slow_r2 >= float(gates_c["slow_mode_r_squared_lower"])
    )
    obstruction_detected = any(
        item["obstructed"] > 0
        for topology, item in floor_by_topology.items()
        if topology in phase_b["irregular_topologies"]
    )
    recovered = phase_a_pass and phase_c_pass
    if not phase_a_pass:
        classification = "IMPLEMENTATION MISMATCH"
    elif not phase_c_pass:
        classification = "SPECTRAL CONTROL NOT RECOVERED"
    elif obstruction_detected:
        classification = "MEASUREMENT/DESIGN MISMATCH"
    else:
        classification = "RECOVERED"

    summary = {
        "registration_id": config["registration_id"],
        "engine_version": ENGINE_VERSION,
        "historical_registration_id": historical.data["registration_id"],
        "historical_files_immutable": True,
        "counts": dict(counts),
        "execution_failures": dict(failures),
        "phase_a": {
            "tau_exact_match_fraction": exact_a,
            "lambda2_max_abs_error": max_lambda_error,
            "pass": phase_a_pass,
        },
        "phase_b": {
            "obstruction_threshold": obstruction,
            "obstruction_detected": obstruction_detected,
            "by_topology": floor_by_topology,
        },
        "phase_c": {
            "tau_exact_match_fraction": exact_c,
            "uncensored_fraction": uncensored_c,
            "unique_slow_spectral_cells": len(unique_slow),
            "slow_mode_slope": slow_slope,
            "slow_mode_r_squared": slow_r2,
            "pass": phase_c_pass,
        },
        "control_recovered": recovered,
        "classification": classification,
        "config_sha256": sha256_file(config_path),
        "historical_config_sha256": sha256_file(historical_path),
        "runs_sha256": sha256_file(runs_path),
    }
    summary_path = output_dir / config["outputs"]["summary"]
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run CCSU-MO-CONTROL-RECOVERY-001"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.config, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
