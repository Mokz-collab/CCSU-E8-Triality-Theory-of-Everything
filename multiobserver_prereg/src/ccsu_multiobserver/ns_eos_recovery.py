from __future__ import annotations

import math
from collections import Counter
from itertools import product
from typing import Mapping, Sequence

import numpy as np
from scipy.stats import qmc

from .ns_eos_local_charts import ChartSpecification, LocalChartEOS


def deterministic_sobol_proposals(
    specification: ChartSpecification,
    *,
    sample_power: int,
    seed: int,
) -> tuple[dict[str, float], ...]:
    """Map a fixed scrambled Sobol design into one registered chart box."""
    if sample_power < 1:
        raise ValueError("sample_power must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    unit_points = qmc.Sobol(
        d=len(specification.parameter_names),
        scramble=True,
        seed=seed,
    ).random_base2(sample_power)
    lower = np.asarray(
        [bounds[0] for bounds in specification.parameter_bounds],
        dtype=float,
    )
    upper = np.asarray(
        [bounds[1] for bounds in specification.parameter_bounds],
        dtype=float,
    )
    scaled = qmc.scale(unit_points, lower, upper)
    return tuple(
        {
            name: float(value)
            for name, value in zip(
                specification.parameter_names,
                row,
                strict=True,
            )
        }
        for row in scaled
    )


def centered_factorial_proposals(
    specification: ChartSpecification,
    *,
    unit_levels: Sequence[float],
) -> tuple[dict[str, float], ...]:
    levels = tuple(float(value) for value in unit_levels)
    if not levels or any(not 0.0 < value < 1.0 for value in levels):
        raise ValueError("factorial levels must lie strictly inside (0, 1)")
    if tuple(sorted(set(levels))) != levels:
        raise ValueError("factorial levels must be unique and increasing")
    proposals = []
    for unit_point in product(levels, repeat=len(specification.parameter_names)):
        proposals.append(
            {
                name: lower + unit * (upper - lower)
                for name, unit, (lower, upper) in zip(
                    specification.parameter_names,
                    unit_point,
                    specification.parameter_bounds,
                    strict=True,
                )
            }
        )
    return tuple(proposals)


def common_relation_projection(
    chart: LocalChartEOS,
    density_anchors_nsat: Sequence[float],
) -> dict[str, list[float]]:
    density = np.asarray(chart.density_nsat, dtype=float)
    anchors = np.asarray(density_anchors_nsat, dtype=float)
    if (
        anchors.ndim != 1
        or anchors.size == 0
        or np.any(np.diff(anchors) <= 0.0)
        or anchors[0] < density[0] * (1.0 - 1.0e-12)
        or anchors[-1] > density[-1] * (1.0 + 1.0e-12)
    ):
        raise ValueError("relation anchors lie outside the chart domain")
    interpolation_anchors = np.clip(anchors, density[0], density[-1])
    pressure = np.interp(
        interpolation_anchors,
        density,
        np.asarray(chart.pressure_mev_fm3, dtype=float),
    )
    energy = np.interp(
        interpolation_anchors,
        density,
        np.asarray(chart.energy_mev_fm3, dtype=float),
    )
    sound_speed = np.interp(
        interpolation_anchors,
        density,
        np.asarray(chart.sound_speed_squared, dtype=float),
    )
    return {
        "density_nsat": anchors.tolist(),
        "log10_pressure_mev_fm3": np.log10(pressure).tolist(),
        "pressure_over_energy": (pressure / energy).tolist(),
        "sound_speed_squared": sound_speed.tolist(),
    }


def classify_screening_result(
    *,
    local_status: str,
    turnover: bool | None = None,
    stable_mass_limit_msun: float | None = None,
    exact_gates_pass: bool | None = None,
) -> str:
    if local_status != "PASS":
        return "LOCAL_PHYSICS_REJECTION"
    if turnover is None or stable_mass_limit_msun is None:
        return "NUMERICAL_REJECTION"
    if not turnover:
        return "NO_TURNOVER_INSIDE_6_NSAT"
    if stable_mass_limit_msun < 2.2:
        return "TURNOVER_BELOW_2_2_MSUN"
    if exact_gates_pass is False:
        return "EXACT_REVALIDATION_REJECTION"
    if exact_gates_pass is True:
        return "ACCEPTED"
    return "EXACT_REVALIDATION_REQUIRED"


def summarize_acceptance(
    cases: Sequence[Mapping[str, object]],
    observers: Sequence[str],
) -> dict[str, object]:
    per_observer: dict[str, dict[str, object]] = {}
    for observer in observers:
        selected = [case for case in cases if case["observer"] == observer]
        if not selected:
            raise ValueError(f"observer has no cases: {observer}")
        reasons = Counter(str(case["outcome"]) for case in selected)
        accepted = reasons.get("ACCEPTED", 0)
        per_observer[observer] = {
            "proposals": len(selected),
            "accepted": accepted,
            "acceptance_fraction": accepted / len(selected),
            "rejection_counts": dict(sorted(reasons.items())),
        }
    fractions = [
        float(row["acceptance_fraction"])
        for row in per_observer.values()
    ]
    positive = [value for value in fractions if value > 0.0]
    ratio = (
        max(positive) / min(positive)
        if len(positive) == len(fractions)
        else None
    )
    return {
        "per_observer": per_observer,
        "acceptance_fraction_range": {
            "minimum": min(fractions),
            "maximum": max(fractions),
        },
        "max_to_min_acceptance_ratio": ratio,
        "zero_acceptance_observers": [
            observer
            for observer, row in per_observer.items()
            if math.isclose(
                float(row["acceptance_fraction"]),
                0.0,
                rel_tol=0.0,
                abs_tol=0.0,
            )
        ],
        "balanced_acceptance_demonstrated": (
            ratio is not None and ratio <= 2.0
        ),
    }
