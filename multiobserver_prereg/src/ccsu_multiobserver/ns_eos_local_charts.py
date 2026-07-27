from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator

from .ns_eos_low_density import ThermodynamicRow


N_SAT_FM3 = 0.16
MEV_FM3_TO_DYN_CM2 = 1.602176634e33


class LocalChartError(ValueError):
    pass


class LocalChartProposalRejected(LocalChartError):
    pass


@dataclass(frozen=True)
class ChartSpecification:
    observer: str
    chart: str
    parameter_names: tuple[str, ...]
    parameter_bounds: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class LocalChartEOS:
    observer: str
    chart: str
    parameter_names: tuple[str, ...]
    parameter_values: tuple[float, ...]
    density_nsat: tuple[float, ...]
    pressure_mev_fm3: tuple[float, ...]
    energy_mev_fm3: tuple[float, ...]
    chemical_potential_mev: tuple[float, ...]
    sound_speed_squared: tuple[float, ...]

    def as_record(self) -> dict[str, object]:
        return {
            "observer": self.observer,
            "chart": self.chart,
            "parameters": dict(
                zip(
                    self.parameter_names,
                    self.parameter_values,
                    strict=True,
                )
            ),
            "density_nsat": list(self.density_nsat),
            "pressure_mev_fm3": list(self.pressure_mev_fm3),
            "energy_mev_fm3": list(self.energy_mev_fm3),
            "chemical_potential_mev": list(
                self.chemical_potential_mev
            ),
            "sound_speed_squared": list(self.sound_speed_squared),
        }


CHART_SPECIFICATIONS: dict[str, ChartSpecification] = {
    "GW": ChartSpecification(
        observer="GW",
        chart="spectral_adiabatic_index",
        parameter_names=("gamma0", "gamma1", "gamma2", "gamma3"),
        parameter_bounds=(
            (0.2, 2.0),
            (-1.6, 1.7),
            (-0.6, 0.6),
            (-0.02, 0.02),
        ),
    ),
    "XRAY": ChartSpecification(
        observer="XRAY",
        chart="piecewise_polytrope",
        parameter_names=(
            "log10_p1_cgs",
            "gamma1",
            "gamma2",
            "gamma3",
        ),
        parameter_bounds=(
            (33.6, 34.8),
            (1.0, 4.5),
            (1.0, 4.5),
            (1.0, 4.5),
        ),
    ),
    "RADIO": ChartSpecification(
        observer="RADIO",
        chart="monotone_eos_spline",
        parameter_names=tuple(
            f"delta_log10_p_{index}" for index in range(1, 6)
        ),
        parameter_bounds=((0.02, 0.80),) * 5,
    ),
    "NUCLEAR": ChartSpecification(
        observer="NUCLEAR",
        chart="speed_of_sound_nodes",
        parameter_names=tuple(f"cs2_{index}" for index in range(1, 7)),
        parameter_bounds=((0.01, 1.0),) * 6,
    ),
}


def _coerce_parameters(
    specification: ChartSpecification,
    parameters: Mapping[str, float],
) -> tuple[float, ...]:
    if set(parameters) != set(specification.parameter_names):
        missing = sorted(set(specification.parameter_names) - set(parameters))
        extra = sorted(set(parameters) - set(specification.parameter_names))
        raise LocalChartError(
            f"parameter names changed; missing={missing}, extra={extra}"
        )
    values = tuple(
        float(parameters[name]) for name in specification.parameter_names
    )
    for name, value, bounds in zip(
        specification.parameter_names,
        values,
        specification.parameter_bounds,
        strict=True,
    ):
        if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise LocalChartError(
                f"{name}={value!r} lies outside {bounds}"
            )
    return values


def _density_grid(
    density_nodes_nsat: Sequence[float],
    sample_count: int,
) -> np.ndarray:
    if sample_count < 33:
        raise LocalChartError("sample_count must be at least 33")
    nodes = np.log(
        np.asarray(density_nodes_nsat, dtype=float)
        / float(density_nodes_nsat[0])
    )
    regular = np.linspace(nodes[0], nodes[-1], sample_count)
    return np.asarray(sorted(set(regular) | set(nodes)), dtype=float)


def _integrate_energy(
    anchor: ThermodynamicRow,
    x_grid: np.ndarray,
    pressure: Callable[[float | np.ndarray], float | np.ndarray],
) -> np.ndarray:
    def derivative(x_value: float, state: np.ndarray) -> np.ndarray:
        return np.asarray(
            [state[0] + float(pressure(x_value))],
            dtype=float,
        )

    result = solve_ivp(
        derivative,
        (float(x_grid[0]), float(x_grid[-1])),
        (anchor.epsilon_mev_fm3,),
        t_eval=x_grid,
        method="DOP853",
        rtol=1.0e-11,
        atol=1.0e-12,
        max_step=0.01,
    )
    if not result.success:
        raise LocalChartProposalRejected(result.message)
    return np.asarray(result.y[0], dtype=float)


def _build_result(
    specification: ChartSpecification,
    values: tuple[float, ...],
    x_grid: np.ndarray,
    pressure: np.ndarray,
    energy: np.ndarray,
    dp_dx: np.ndarray,
) -> LocalChartEOS:
    density_nsat = 1.1 * np.exp(x_grid)
    density_fm3 = density_nsat * N_SAT_FM3
    chemical_potential = (energy + pressure) / density_fm3
    sound_speed_squared = dp_dx / (energy + pressure)
    return LocalChartEOS(
        observer=specification.observer,
        chart=specification.chart,
        parameter_names=specification.parameter_names,
        parameter_values=values,
        density_nsat=tuple(float(value) for value in density_nsat),
        pressure_mev_fm3=tuple(float(value) for value in pressure),
        energy_mev_fm3=tuple(float(value) for value in energy),
        chemical_potential_mev=tuple(
            float(value) for value in chemical_potential
        ),
        sound_speed_squared=tuple(
            float(value) for value in sound_speed_squared
        ),
    )


def _generate_spectral(
    specification: ChartSpecification,
    values: tuple[float, ...],
    anchor: ThermodynamicRow,
    sample_count: int,
) -> LocalChartEOS:
    x_grid = _density_grid((1.1, 6.0), sample_count)

    def adiabatic_index(x_value: float | np.ndarray) -> float | np.ndarray:
        exponent = sum(
            coefficient * np.asarray(x_value) ** order
            for order, coefficient in enumerate(values)
        )
        if np.any(np.asarray(exponent) > 700):
            raise LocalChartProposalRejected(
                "spectral adiabatic index overflow"
            )
        return np.exp(exponent)

    def derivative(x_value: float, state: np.ndarray) -> np.ndarray:
        pressure, energy = state
        gamma = float(adiabatic_index(x_value))
        return np.asarray(
            [gamma * pressure, energy + pressure],
            dtype=float,
        )

    result = solve_ivp(
        derivative,
        (float(x_grid[0]), float(x_grid[-1])),
        (anchor.p_mev_fm3, anchor.epsilon_mev_fm3),
        t_eval=x_grid,
        method="DOP853",
        rtol=1.0e-11,
        atol=1.0e-12,
        max_step=0.01,
    )
    if not result.success:
        raise LocalChartProposalRejected(result.message)
    pressure = np.asarray(result.y[0], dtype=float)
    energy = np.asarray(result.y[1], dtype=float)
    dp_dx = np.asarray(adiabatic_index(x_grid), dtype=float) * pressure
    return _build_result(
        specification,
        values,
        x_grid,
        pressure,
        energy,
        dp_dx,
    )


def _generate_piecewise_polytrope(
    specification: ChartSpecification,
    values: tuple[float, ...],
    anchor: ThermodynamicRow,
    sample_count: int,
) -> LocalChartEOS:
    log10_p1_cgs, gamma1, gamma2, gamma3 = values
    p0 = anchor.p_mev_fm3
    p1 = 10.0**log10_p1_cgs / MEV_FM3_TO_DYN_CM2
    if not p1 > p0:
        raise LocalChartProposalRejected(
            "p1 must exceed the pinned 1.1 n_sat anchor pressure"
        )
    density_nodes = np.asarray((1.1, 2.0, 3.5, 6.0), dtype=float)
    x_nodes = np.log(density_nodes / density_nodes[0])
    first_ratio = density_nodes[1] / density_nodes[0]
    first_denominator = first_ratio**gamma1 - 1.0
    p2 = p1 * (density_nodes[2] / density_nodes[1]) ** gamma2

    def pressure_and_derivative(
        x_value: float | np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(x_value, dtype=float)
        density = density_nodes[0] * np.exp(x)
        pressure = np.empty_like(density)
        derivative = np.empty_like(density)
        first = density <= density_nodes[1]
        second = (density > density_nodes[1]) & (
            density <= density_nodes[2]
        )
        third = density > density_nodes[2]

        ratio = density[first] / density_nodes[0]
        pressure[first] = p0 + (p1 - p0) * (
            ratio**gamma1 - 1.0
        ) / first_denominator
        derivative[first] = (
            (p1 - p0)
            * gamma1
            * ratio**gamma1
            / first_denominator
        )

        ratio = density[second] / density_nodes[1]
        pressure[second] = p1 * ratio**gamma2
        derivative[second] = gamma2 * pressure[second]

        ratio = density[third] / density_nodes[2]
        pressure[third] = p2 * ratio**gamma3
        derivative[third] = gamma3 * pressure[third]
        return pressure, derivative

    x_grid = _density_grid(density_nodes, sample_count)

    def pressure_function(
        x_value: float | np.ndarray,
    ) -> float | np.ndarray:
        pressure, _ = pressure_and_derivative(x_value)
        if np.ndim(x_value) == 0:
            return float(pressure)
        return pressure

    pressure, dp_dx = pressure_and_derivative(x_grid)
    energy = _integrate_energy(anchor, x_grid, pressure_function)
    return _build_result(
        specification,
        values,
        x_grid,
        pressure,
        energy,
        dp_dx,
    )


def _generate_monotone_spline(
    specification: ChartSpecification,
    values: tuple[float, ...],
    anchor: ThermodynamicRow,
    sample_count: int,
) -> LocalChartEOS:
    density_nodes = np.asarray(
        (1.1, 1.5, 2.0, 3.0, 4.5, 6.0),
        dtype=float,
    )
    x_nodes = np.log(density_nodes / density_nodes[0])
    log_pressure_nodes = np.asarray(
        [math.log10(anchor.p_mev_fm3)]
        + list(math.log10(anchor.p_mev_fm3) + np.cumsum(values)),
        dtype=float,
    )
    interpolator = PchipInterpolator(x_nodes, log_pressure_nodes)
    derivative_interpolator = interpolator.derivative()

    def pressure_function(
        x_value: float | np.ndarray,
    ) -> float | np.ndarray:
        return 10.0 ** interpolator(x_value)

    x_grid = _density_grid(density_nodes, sample_count)
    pressure = np.asarray(pressure_function(x_grid), dtype=float)
    dp_dx = (
        pressure
        * math.log(10.0)
        * np.asarray(derivative_interpolator(x_grid), dtype=float)
    )
    energy = _integrate_energy(anchor, x_grid, pressure_function)
    return _build_result(
        specification,
        values,
        x_grid,
        pressure,
        energy,
        dp_dx,
    )


def _generate_sound_speed_nodes(
    specification: ChartSpecification,
    values: tuple[float, ...],
    anchor: ThermodynamicRow,
    sample_count: int,
) -> LocalChartEOS:
    density_nodes = np.asarray(
        (1.1, 1.5, 2.0, 3.0, 4.5, 6.0),
        dtype=float,
    )
    x_nodes = np.log(density_nodes / density_nodes[0])
    cs2_interpolator = PchipInterpolator(x_nodes, values)
    x_grid = _density_grid(density_nodes, sample_count)

    def derivative(x_value: float, state: np.ndarray) -> np.ndarray:
        pressure, energy = state
        cs2 = float(cs2_interpolator(x_value))
        enthalpy_density = energy + pressure
        return np.asarray(
            [cs2 * enthalpy_density, enthalpy_density],
            dtype=float,
        )

    result = solve_ivp(
        derivative,
        (float(x_grid[0]), float(x_grid[-1])),
        (anchor.p_mev_fm3, anchor.epsilon_mev_fm3),
        t_eval=x_grid,
        method="DOP853",
        rtol=1.0e-11,
        atol=1.0e-12,
        max_step=0.01,
    )
    if not result.success:
        raise LocalChartProposalRejected(result.message)
    pressure = np.asarray(result.y[0], dtype=float)
    energy = np.asarray(result.y[1], dtype=float)
    cs2 = np.asarray(cs2_interpolator(x_grid), dtype=float)
    dp_dx = cs2 * (energy + pressure)
    return _build_result(
        specification,
        values,
        x_grid,
        pressure,
        energy,
        dp_dx,
    )


def generate_local_chart(
    observer: str,
    parameters: Mapping[str, float],
    anchor: ThermodynamicRow,
    *,
    sample_count: int = 257,
) -> LocalChartEOS:
    if observer not in CHART_SPECIFICATIONS:
        raise LocalChartError(f"unknown observer: {observer}")
    expected_density = 1.1 * N_SAT_FM3
    if not math.isclose(
        anchor.n_b_fm3,
        expected_density,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise LocalChartError("anchor is not at 1.1 n_sat")
    specification = CHART_SPECIFICATIONS[observer]
    values = _coerce_parameters(specification, parameters)
    generators = {
        "GW": _generate_spectral,
        "XRAY": _generate_piecewise_polytrope,
        "RADIO": _generate_monotone_spline,
        "NUCLEAR": _generate_sound_speed_nodes,
    }
    return generators[observer](
        specification,
        values,
        anchor,
        sample_count,
    )


def evaluate_local_physics(
    eos: LocalChartEOS,
    anchor: ThermodynamicRow,
    *,
    relative_matching_tolerance: float = 1.0e-10,
    identity_tolerance: float = 1.0e-12,
) -> dict[str, object]:
    density = np.asarray(eos.density_nsat, dtype=float) * N_SAT_FM3
    pressure = np.asarray(eos.pressure_mev_fm3, dtype=float)
    energy = np.asarray(eos.energy_mev_fm3, dtype=float)
    chemical_potential = np.asarray(
        eos.chemical_potential_mev,
        dtype=float,
    )
    cs2 = np.asarray(eos.sound_speed_squared, dtype=float)

    finite = bool(
        np.all(np.isfinite(density))
        and np.all(np.isfinite(pressure))
        and np.all(np.isfinite(energy))
        and np.all(np.isfinite(chemical_potential))
        and np.all(np.isfinite(cs2))
    )
    matching = {
        "density": abs(density[0] - anchor.n_b_fm3)
        / anchor.n_b_fm3,
        "pressure": abs(pressure[0] - anchor.p_mev_fm3)
        / anchor.p_mev_fm3,
        "energy": abs(energy[0] - anchor.epsilon_mev_fm3)
        / anchor.epsilon_mev_fm3,
        "chemical_potential": abs(
            chemical_potential[0] - anchor.mu_b_mev
        )
        / anchor.mu_b_mev,
    }
    identity_residual = np.max(
        np.abs(
            chemical_potential
            - (energy + pressure) / density
        )
        / np.maximum(np.abs(chemical_potential), 1.0e-300)
    )
    checks = {
        "finite": finite,
        "density_strictly_increasing": bool(np.all(np.diff(density) > 0)),
        "pressure_strictly_increasing": bool(
            np.all(np.diff(pressure) > 0)
        ),
        "energy_strictly_increasing": bool(np.all(np.diff(energy) > 0)),
        "thermodynamic_identity": bool(
            identity_residual <= identity_tolerance
        ),
        "anchor_matching": bool(
            max(matching.values()) <= relative_matching_tolerance
        ),
        "sound_speed_positive": bool(np.all(cs2 > 0)),
        "sound_speed_causal": bool(np.all(cs2 <= 1.0)),
    }
    return {
        "checks": checks,
        "all_local_checks_pass": all(checks.values()),
        "matching_relative_residuals": matching,
        "maximum_identity_relative_residual": float(
            identity_residual
        ),
        "minimum_sound_speed_squared": float(np.min(cs2)),
        "maximum_sound_speed_squared": float(np.max(cs2)),
        "pressure_ratio_6_to_1_1_nsat": float(
            pressure[-1] / pressure[0]
        ),
        "sample_count": len(density),
    }
