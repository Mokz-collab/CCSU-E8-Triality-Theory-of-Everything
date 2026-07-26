from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Sequence

from .ns_eos_low_density import (
    ChemicalPotentialDerivativeTemplate,
    ThermodynamicTable,
    build_chemical_potential_connector,
    build_reference_tilted_connector,
    project_rounded_chemical_potential,
)
from .ns_eos_oracle import StellarModel, solve_star


MEV_FM3_TO_GEOMETRIC_KM2 = 1.3238333135663825e-6
SOLAR_MASS_GEOMETRIC_KM = 1.4766250380501249


class StellarImpactError(RuntimeError):
    pass


@dataclass(frozen=True)
class PiecewiseLinearBarotrope:
    """Physical P(epsilon) table with a constant-sound-speed core extension."""

    pressure_mev_fm3: tuple[float, ...]
    energy_mev_fm3: tuple[float, ...]
    core_cs2: float

    def __post_init__(self) -> None:
        if not 0 < self.core_cs2 <= 1:
            raise ValueError("core c_s^2 must lie in (0, 1]")
        if len(self.pressure_mev_fm3) != len(self.energy_mev_fm3) < 2:
            raise ValueError("barotrope requires paired pressure/energy nodes")
        for left, right in zip(
            self.pressure_mev_fm3,
            self.pressure_mev_fm3[1:],
            strict=False,
        ):
            if not right > left >= 0:
                raise ValueError("barotrope pressure nodes must increase")
        for left, right in zip(
            self.energy_mev_fm3,
            self.energy_mev_fm3[1:],
            strict=False,
        ):
            if not right > left >= 0:
                raise ValueError("barotrope energy nodes must increase")
        for left_p, right_p, left_e, right_e in zip(
            self.pressure_mev_fm3[:-1],
            self.pressure_mev_fm3[1:],
            self.energy_mev_fm3[:-1],
            self.energy_mev_fm3[1:],
            strict=True,
        ):
            cs2 = (right_p - left_p) / (right_e - left_e)
            if not 0 < cs2 <= 1:
                raise ValueError("barotrope interval is unstable or acausal")

    @property
    def surface_pressure(self) -> float:
        return (
            self.pressure_mev_fm3[0]
            * MEV_FM3_TO_GEOMETRIC_KM2
        )

    @property
    def transition_pressure_mev_fm3(self) -> float:
        return self.pressure_mev_fm3[-1]

    def _pressure_mev_fm3(self, pressure: float) -> float:
        return pressure / MEV_FM3_TO_GEOMETRIC_KM2

    def energy_density(self, pressure: float) -> float:
        if pressure <= 0:
            return 0.0
        p_value = self._pressure_mev_fm3(pressure)
        if p_value <= self.pressure_mev_fm3[0]:
            epsilon = (
                self.energy_mev_fm3[0]
                * p_value
                / self.pressure_mev_fm3[0]
            )
        elif p_value >= self.pressure_mev_fm3[-1]:
            epsilon = (
                self.energy_mev_fm3[-1]
                + (
                    p_value - self.pressure_mev_fm3[-1]
                )
                / self.core_cs2
            )
        else:
            upper = bisect.bisect_right(self.pressure_mev_fm3, p_value)
            lower = upper - 1
            p0 = self.pressure_mev_fm3[lower]
            p1 = self.pressure_mev_fm3[upper]
            e0 = self.energy_mev_fm3[lower]
            e1 = self.energy_mev_fm3[upper]
            fraction = (p_value - p0) / (p1 - p0)
            epsilon = e0 + fraction * (e1 - e0)
        return epsilon * MEV_FM3_TO_GEOMETRIC_KM2

    def sound_speed_squared(self, pressure: float) -> float:
        if pressure <= 0:
            return 0.0
        p_value = self._pressure_mev_fm3(pressure)
        if p_value <= self.pressure_mev_fm3[0]:
            return (
                self.pressure_mev_fm3[0]
                / self.energy_mev_fm3[0]
            )
        if p_value >= self.pressure_mev_fm3[-1]:
            return self.core_cs2
        upper = bisect.bisect_right(self.pressure_mev_fm3, p_value)
        lower = upper - 1
        return (
            self.pressure_mev_fm3[upper]
            - self.pressure_mev_fm3[lower]
        ) / (
            self.energy_mev_fm3[upper]
            - self.energy_mev_fm3[lower]
        )


@dataclass(frozen=True)
class TargetMassModel:
    target_mass_msun: float
    central_pressure_mev_fm3: float
    mass_msun: float
    radius_km: float
    love_k2: float
    tidal_lambda: float
    integration_steps: int


def build_low_density_barotrope(
    outer_crust: ThermodynamicTable,
    chiral_eft: ThermodynamicTable,
    template: ChemicalPotentialDerivativeTemplate,
    *,
    connector_kind: str,
    connector_points: int,
    core_cs2: float,
    projection_tolerance: float,
) -> PiecewiseLinearBarotrope:
    projected_lower, _ = project_rounded_chemical_potential(
        outer_crust.last,
        maximum_original_relative_residual=projection_tolerance,
    )
    if connector_kind == "endpoint_exponential_v0_4":
        connector = build_chemical_potential_connector(
            projected_lower,
            chiral_eft.first,
        )
    elif connector_kind == "reference_tilted_v0_5_candidate":
        connector = build_reference_tilted_connector(
            projected_lower,
            chiral_eft.first,
            template,
        )
    else:
        raise ValueError(f"unknown connector kind: {connector_kind}")
    connector_rows = connector.sample(connector_points)
    combined = (
        list(outer_crust.rows)
        + list(connector_rows[1:])
        + list(chiral_eft.rows[1:])
    )
    return PiecewiseLinearBarotrope(
        pressure_mev_fm3=tuple(row.p_mev_fm3 for row in combined),
        energy_mev_fm3=tuple(row.epsilon_mev_fm3 for row in combined),
        core_cs2=core_cs2,
    )


def solve_physical_star(
    eos: PiecewiseLinearBarotrope,
    central_pressure_mev_fm3: float,
    *,
    maximum_step_km: float,
    minimum_step_km: float,
    pressure_step_fraction: float,
) -> StellarModel:
    return solve_star(
        eos,
        central_pressure_mev_fm3 * MEV_FM3_TO_GEOMETRIC_KM2,
        maximum_step=maximum_step_km,
        minimum_step=minimum_step_km,
        pressure_step_fraction=pressure_step_fraction,
        surface_pressure_absolute=eos.surface_pressure,
        initial_radius=1.0e-6,
        maximum_radius=50.0,
        maximum_steps=2_000_000,
    )


def solve_target_mass(
    eos: PiecewiseLinearBarotrope,
    target_mass_msun: float,
    *,
    central_pressure_bounds_mev_fm3: tuple[float, float],
    scan_points: int,
    mass_tolerance_msun: float,
    maximum_bisection_iterations: int,
    maximum_step_km: float,
    minimum_step_km: float,
    pressure_step_fraction: float,
) -> TargetMassModel:
    return solve_target_masses(
        eos,
        (target_mass_msun,),
        central_pressure_bounds_mev_fm3=central_pressure_bounds_mev_fm3,
        scan_points=scan_points,
        mass_tolerance_msun=mass_tolerance_msun,
        maximum_bisection_iterations=maximum_bisection_iterations,
        maximum_step_km=maximum_step_km,
        minimum_step_km=minimum_step_km,
        pressure_step_fraction=pressure_step_fraction,
    )[0]


def solve_target_masses(
    eos: PiecewiseLinearBarotrope,
    target_masses_msun: Sequence[float],
    *,
    central_pressure_bounds_mev_fm3: tuple[float, float],
    scan_points: int,
    mass_tolerance_msun: float,
    maximum_bisection_iterations: int,
    maximum_step_km: float,
    minimum_step_km: float,
    pressure_step_fraction: float,
) -> tuple[TargetMassModel, ...]:
    if not target_masses_msun or any(
        target <= 0 for target in target_masses_msun
    ):
        raise ValueError("target masses must be positive")
    lower_pressure, upper_pressure = central_pressure_bounds_mev_fm3
    if not 0 < lower_pressure < upper_pressure:
        raise ValueError("central-pressure bounds are invalid")
    if scan_points < 3:
        raise ValueError("mass scan requires at least three points")
    pressure_grid = [
        math.exp(
            math.log(lower_pressure)
            + index
            / (scan_points - 1)
            * math.log(upper_pressure / lower_pressure)
        )
        for index in range(scan_points)
    ]
    models = [
        solve_physical_star(
            eos,
            pressure,
            maximum_step_km=maximum_step_km,
            minimum_step_km=minimum_step_km,
            pressure_step_fraction=pressure_step_fraction,
        )
        for pressure in pressure_grid
    ]
    masses = [
        model.mass / SOLAR_MASS_GEOMETRIC_KM
        for model in models
    ]
    maximum_index = max(range(len(masses)), key=masses.__getitem__)
    stable_pressures = pressure_grid[: maximum_index + 1]
    stable_masses = masses[: maximum_index + 1]
    results: list[TargetMassModel] = []
    for target_mass_msun in target_masses_msun:
        bracket: tuple[float, float] | None = None
        for left_p, right_p, left_m, right_m in zip(
            stable_pressures,
            stable_pressures[1:],
            stable_masses,
            stable_masses[1:],
            strict=True,
        ):
            if left_m <= target_mass_msun <= right_m:
                bracket = (left_p, right_p)
                break
        if bracket is None:
            raise StellarImpactError(
                f"target mass {target_mass_msun} Msun is not bracketed "
                f"on the stable branch; maximum is {max(stable_masses)} Msun"
            )
        left_pressure, right_pressure = bracket
        final_pressure = left_pressure
        final_model = solve_physical_star(
            eos,
            final_pressure,
            maximum_step_km=maximum_step_km,
            minimum_step_km=minimum_step_km,
            pressure_step_fraction=pressure_step_fraction,
        )
        for _ in range(maximum_bisection_iterations):
            midpoint = (left_pressure + right_pressure) / 2.0
            model = solve_physical_star(
                eos,
                midpoint,
                maximum_step_km=maximum_step_km,
                minimum_step_km=minimum_step_km,
                pressure_step_fraction=pressure_step_fraction,
            )
            mass_msun = model.mass / SOLAR_MASS_GEOMETRIC_KM
            final_pressure = midpoint
            final_model = model
            if abs(mass_msun - target_mass_msun) <= mass_tolerance_msun:
                break
            if mass_msun < target_mass_msun:
                left_pressure = midpoint
            else:
                right_pressure = midpoint
        mass_msun = final_model.mass / SOLAR_MASS_GEOMETRIC_KM
        if abs(mass_msun - target_mass_msun) > mass_tolerance_msun:
            raise StellarImpactError("target-mass bisection did not converge")
        results.append(
            TargetMassModel(
                target_mass_msun=target_mass_msun,
                central_pressure_mev_fm3=final_pressure,
                mass_msun=mass_msun,
                radius_km=final_model.radius,
                love_k2=final_model.love_k2,
                tidal_lambda=final_model.tidal_lambda,
                integration_steps=final_model.steps,
            )
        )
    return tuple(results)


def fractional_spread(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("spread requires at least one value")
    midpoint = (max(values) + min(values)) / 2.0
    return (max(values) - min(values)) / midpoint
