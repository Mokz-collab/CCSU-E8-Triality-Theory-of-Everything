from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from scipy.integrate import solve_ivp

from .ns_eos_stellar_impact import PiecewiseLinearBarotrope


class EnthalpyOracleError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnthalpyStellarModel:
    central_pressure: float
    central_enthalpy: float
    mass: float
    radius: float
    compactness: float
    love_k2: float
    tidal_lambda: float
    surface_y: float
    accepted_steps: int
    function_evaluations: int


@dataclass(frozen=True)
class EnthalpyBarotrope:
    """Analytic enthalpy transform of a piecewise-linear P(epsilon) EOS."""

    pressure_nodes: tuple[float, ...]
    energy_nodes: tuple[float, ...]
    enthalpy_nodes: tuple[float, ...]
    interval_cs2: tuple[float, ...]
    core_cs2: float

    @classmethod
    def from_piecewise(
        cls,
        eos: PiecewiseLinearBarotrope,
    ) -> EnthalpyBarotrope:
        conversion = 1.3238333135663825e-6
        pressure = tuple(
            value * conversion for value in eos.pressure_mev_fm3
        )
        energy = tuple(
            value * conversion for value in eos.energy_mev_fm3
        )
        cs2_values = tuple(
            (right_p - left_p) / (right_e - left_e)
            for left_p, right_p, left_e, right_e in zip(
                pressure[:-1],
                pressure[1:],
                energy[:-1],
                energy[1:],
                strict=True,
            )
        )
        enthalpy = [0.0]
        for index, cs2 in enumerate(cs2_values):
            enthalpy.append(
                enthalpy[-1]
                + _enthalpy_increment(
                    pressure[index],
                    energy[index],
                    pressure[index + 1],
                    cs2,
                )
            )
        return cls(
            pressure_nodes=pressure,
            energy_nodes=energy,
            enthalpy_nodes=tuple(enthalpy),
            interval_cs2=cs2_values,
            core_cs2=eos.core_cs2,
        )

    @property
    def surface_pressure(self) -> float:
        return self.pressure_nodes[0]

    def enthalpy_of_pressure(self, pressure: float) -> float:
        if pressure < self.surface_pressure:
            raise ValueError("pressure lies below the registered surface")
        if pressure >= self.pressure_nodes[-1]:
            return (
                self.enthalpy_nodes[-1]
                + _enthalpy_increment(
                    self.pressure_nodes[-1],
                    self.energy_nodes[-1],
                    pressure,
                    self.core_cs2,
                )
            )
        upper = bisect.bisect_right(self.pressure_nodes, pressure)
        lower = upper - 1
        return (
            self.enthalpy_nodes[lower]
            + _enthalpy_increment(
                self.pressure_nodes[lower],
                self.energy_nodes[lower],
                pressure,
                self.interval_cs2[lower],
            )
        )

    def state_at_enthalpy(
        self,
        enthalpy: float,
    ) -> tuple[float, float, float]:
        if enthalpy < 0:
            raise ValueError("enthalpy must be non-negative")
        if enthalpy >= self.enthalpy_nodes[-1]:
            return _invert_enthalpy_interval(
                self.pressure_nodes[-1],
                self.energy_nodes[-1],
                enthalpy - self.enthalpy_nodes[-1],
                self.core_cs2,
            )
        upper = bisect.bisect_right(self.enthalpy_nodes, enthalpy)
        lower = max(0, upper - 1)
        return _invert_enthalpy_interval(
            self.pressure_nodes[lower],
            self.energy_nodes[lower],
            enthalpy - self.enthalpy_nodes[lower],
            self.interval_cs2[lower],
        )


def _enthalpy_increment(
    pressure0: float,
    energy0: float,
    pressure1: float,
    cs2: float,
) -> float:
    if not pressure1 >= pressure0:
        raise ValueError("enthalpy interval pressure order is invalid")
    slope = 1.0 / cs2
    coefficient = energy0 - slope * pressure0
    factor = slope + 1.0
    denominator0 = coefficient + factor * pressure0
    denominator1 = coefficient + factor * pressure1
    if denominator0 <= 0 or denominator1 <= 0:
        raise EnthalpyOracleError("enthalpy interval has a non-positive denominator")
    return math.log(denominator1 / denominator0) / factor


def _invert_enthalpy_interval(
    pressure0: float,
    energy0: float,
    enthalpy_increment: float,
    cs2: float,
) -> tuple[float, float, float]:
    slope = 1.0 / cs2
    coefficient = energy0 - slope * pressure0
    factor = slope + 1.0
    denominator0 = coefficient + factor * pressure0
    denominator = denominator0 * math.exp(factor * enthalpy_increment)
    pressure = (denominator - coefficient) / factor
    energy = energy0 + slope * (pressure - pressure0)
    return pressure, energy, cs2


def _love_number_independent(
    compactness: float,
    surface_y: float,
) -> float:
    c = compactness
    y = surface_y
    first = 2.0 + 2.0 * c * (y - 1.0) - y
    numerator = (
        8.0
        * c**5
        * (1.0 - 2.0 * c) ** 2
        * first
        / 5.0
    )
    denominator = (
        2.0 * c * (6.0 - 3.0 * y + 3.0 * c * (5.0 * y - 8.0))
        + 4.0
        * c**3
        * (
            13.0
            - 11.0 * y
            + c * (3.0 * y - 2.0)
            + 2.0 * c**2 * (1.0 + y)
        )
        + 3.0
        * (1.0 - 2.0 * c) ** 2
        * first
        * math.log(1.0 - 2.0 * c)
    )
    if denominator == 0:
        raise EnthalpyOracleError("independent Love denominator is singular")
    value = numerator / denominator
    if not math.isfinite(value) or value <= 0:
        raise EnthalpyOracleError("independent Love number is invalid")
    return value


def solve_star_enthalpy(
    eos: PiecewiseLinearBarotrope,
    central_pressure: float,
    *,
    relative_tolerance: float = 1.0e-9,
    absolute_tolerance: float = 1.0e-11,
    maximum_enthalpy_step: float = 1.0e-3,
    initial_enthalpy_offset: float = 1.0e-8,
) -> EnthalpyStellarModel:
    transformed = EnthalpyBarotrope.from_piecewise(eos)
    if not central_pressure > transformed.surface_pressure:
        raise ValueError("central pressure must exceed the surface pressure")
    central_enthalpy = transformed.enthalpy_of_pressure(central_pressure)
    central_pressure_value, central_energy, _ = transformed.state_at_enthalpy(
        central_enthalpy
    )
    offset = min(initial_enthalpy_offset, central_enthalpy / 1000.0)
    start_enthalpy = central_enthalpy - offset
    radius = math.sqrt(
        3.0
        * offset
        / (
            2.0
            * math.pi
            * (central_energy + 3.0 * central_pressure_value)
        )
    )
    mass = 4.0 * math.pi * central_energy * radius**3 / 3.0
    initial_state = (radius, mass, 2.0)

    def derivative(
        enthalpy: float,
        state: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        r, m, y = state
        pressure, energy, cs2 = transformed.state_at_enthalpy(enthalpy)
        if not r > 2.0 * m >= 0:
            raise EnthalpyOracleError(
                "enthalpy integration crossed the Schwarzschild radius"
            )
        gravity = m + 4.0 * math.pi * r**3 * pressure
        if gravity <= 0:
            raise EnthalpyOracleError("enthalpy gravity denominator is invalid")
        dr_dh = -r * (r - 2.0 * m) / gravity
        dm_dh = 4.0 * math.pi * r**2 * energy * dr_dh

        metric = 1.0 - 2.0 * m / r
        f_term = (
            1.0 - 4.0 * math.pi * r**2 * (energy - pressure)
        ) / metric
        q_term = (
            4.0
            * math.pi
            * (
                5.0 * energy
                + 9.0 * pressure
                + (energy + pressure) / cs2
                - 6.0 / (4.0 * math.pi * r**2)
            )
            / metric
            - 4.0 * (gravity / (r**2 * metric)) ** 2
        )
        dy_dr = -(y**2 + y * f_term + r**2 * q_term) / r
        return dr_dh, dm_dh, dy_dr * dr_dh

    result = solve_ivp(
        derivative,
        (start_enthalpy, 0.0),
        initial_state,
        method="DOP853",
        rtol=relative_tolerance,
        atol=absolute_tolerance,
        max_step=maximum_enthalpy_step,
    )
    if not result.success:
        raise EnthalpyOracleError(result.message)
    surface_radius, surface_mass, surface_y = (
        float(value) for value in result.y[:, -1]
    )
    compactness = surface_mass / surface_radius
    love_k2 = _love_number_independent(compactness, surface_y)
    tidal_lambda = (2.0 / 3.0) * love_k2 / compactness**5
    return EnthalpyStellarModel(
        central_pressure=central_pressure,
        central_enthalpy=central_enthalpy,
        mass=surface_mass,
        radius=surface_radius,
        compactness=compactness,
        love_k2=love_k2,
        tidal_lambda=tidal_lambda,
        surface_y=surface_y,
        accepted_steps=len(result.t) - 1,
        function_evaluations=int(result.nfev),
    )
