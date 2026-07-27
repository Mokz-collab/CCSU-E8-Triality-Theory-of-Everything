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


def relation_vector(
    projection: Mapping[str, Sequence[float]],
    *,
    log_pressure_scale_decades: float,
    pressure_over_energy_scale: float,
    sound_speed_squared_scale: float,
) -> np.ndarray:
    scales = (
        float(log_pressure_scale_decades),
        float(pressure_over_energy_scale),
        float(sound_speed_squared_scale),
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in scales):
        raise ValueError("relation scales must be finite and positive")
    fields = (
        "log10_pressure_mev_fm3",
        "pressure_over_energy",
        "sound_speed_squared",
    )
    blocks = [
        np.asarray(projection[field], dtype=float) / scale
        for field, scale in zip(fields, scales, strict=True)
    ]
    if (
        any(block.ndim != 1 or block.size == 0 for block in blocks)
        or len({block.size for block in blocks}) != 1
        or not all(np.all(np.isfinite(block)) for block in blocks)
    ):
        raise ValueError("relation projection blocks are incompatible")
    return np.concatenate(blocks)


def relation_distance_matrix(vectors: Sequence[np.ndarray]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=float)
    if (
        matrix.ndim != 2
        or matrix.shape[0] == 0
        or matrix.shape[1] == 0
        or not np.all(np.isfinite(matrix))
    ):
        raise ValueError("relation vectors must form a finite matrix")
    differences = matrix[:, None, :] - matrix[None, :, :]
    return np.sqrt(np.mean(differences * differences, axis=2))


def relation_components(
    distance_matrix: np.ndarray,
    *,
    epsilon: float,
) -> tuple[tuple[int, ...], ...]:
    distances = np.asarray(distance_matrix, dtype=float)
    if (
        distances.ndim != 2
        or distances.shape[0] != distances.shape[1]
        or not np.all(np.isfinite(distances))
    ):
        raise ValueError("distance matrix must be finite and square")
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    seen: set[int] = set()
    components: list[tuple[int, ...]] = []
    for start in range(distances.shape[0]):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[int] = []
        while stack:
            index = stack.pop()
            component.append(index)
            neighbors = np.flatnonzero(distances[index] <= epsilon)
            for neighbor_value in neighbors:
                neighbor = int(neighbor_value)
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(tuple(sorted(component)))
    return tuple(components)


def equal_component_measure(
    atoms: Sequence[Mapping[str, object]],
    distance_matrix: np.ndarray,
    *,
    epsilon: float,
) -> dict[str, object]:
    if len(atoms) != distance_matrix.shape[0]:
        raise ValueError("atom and distance counts differ")
    components = relation_components(distance_matrix, epsilon=epsilon)
    component_mass = 1.0 / len(components)
    atom_weights = [0.0] * len(atoms)
    component_records: list[dict[str, object]] = []
    provenance_mass: Counter[str] = Counter()
    mixed_components = 0
    for component_index, component in enumerate(components):
        atom_mass = component_mass / len(component)
        observers = sorted(
            {str(atoms[index]["observer"]) for index in component}
        )
        if len(observers) > 1:
            mixed_components += 1
        for index in component:
            atom_weights[index] = atom_mass
            provenance_mass[str(atoms[index]["observer"])] += atom_mass
        component_records.append(
            {
                "component_index": component_index,
                "atom_indices": list(component),
                "atom_count": len(component),
                "observers": observers,
                "mass": component_mass,
            }
        )
    return {
        "epsilon": epsilon,
        "component_count": len(components),
        "mixed_observer_component_count": mixed_components,
        "component_mass": component_mass,
        "components": component_records,
        "atom_weights": atom_weights,
        "observer_attributed_mass": dict(sorted(provenance_mass.items())),
        "total_mass": sum(atom_weights),
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
