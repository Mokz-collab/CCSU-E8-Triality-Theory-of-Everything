from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Callable, Protocol, Sequence


class OracleError(RuntimeError):
    """Raised when a dimensionless stellar model is physically or numerically invalid."""


class BarotropicEOS(Protocol):
    def energy_density(self, pressure: float) -> float: ...

    def sound_speed_squared(self, pressure: float) -> float: ...


@dataclass(frozen=True)
class RelativisticPolytrope:
    """Cold one-component EOS in geometrized, dimensionless units.

    The rest-mass density is rho = (p / K) ** (1 / gamma), and the total
    energy density is epsilon = rho + p / (gamma - 1).
    """

    k: float = 1.0
    gamma: float = 2.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.k) or self.k <= 0:
            raise ValueError("k must be finite and positive")
        if not math.isfinite(self.gamma) or not 1 < self.gamma <= 2:
            raise ValueError("gamma must satisfy 1 < gamma <= 2")

    def energy_density(self, pressure: float) -> float:
        if pressure <= 0:
            return 0.0
        rho = (pressure / self.k) ** (1.0 / self.gamma)
        return rho + pressure / (self.gamma - 1.0)

    def sound_speed_squared(self, pressure: float) -> float:
        if pressure <= 0:
            return 0.0
        epsilon = self.energy_density(pressure)
        return self.gamma * pressure / (epsilon + pressure)


@dataclass(frozen=True)
class StellarModel:
    central_pressure: float
    mass: float
    radius: float
    compactness: float
    love_k2: float
    tidal_lambda: float
    surface_y: float
    steps: int
    pressure_floor: float


State = tuple[float, float, float]


def _add(state: State, slope: State, scale: float) -> State:
    return tuple(value + scale * derivative for value, derivative in zip(state, slope, strict=True))  # type: ignore[return-value]


def _rhs(eos: BarotropicEOS, radius: float, state: State, pressure_floor: float) -> State:
    mass, pressure, y_value = state
    evaluation_pressure = max(pressure, pressure_floor)
    epsilon = eos.energy_density(evaluation_pressure)
    cs2 = eos.sound_speed_squared(evaluation_pressure)

    if not all(math.isfinite(value) for value in (mass, pressure, y_value, epsilon, cs2)):
        raise OracleError("non-finite TOV/Love state")
    if epsilon <= 0:
        raise OracleError("EOS returned non-positive energy density")
    if not 0 < cs2 <= 1:
        raise OracleError("EOS violates the oracle sound-speed interval 0 < c_s^2 <= 1")

    metric = 1.0 - 2.0 * mass / radius
    if metric <= 0:
        raise OracleError("integration crossed the Schwarzschild radius")

    mass_gradient = 4.0 * math.pi * radius**2 * epsilon
    pressure_gravity = mass + 4.0 * math.pi * radius**3 * evaluation_pressure
    pressure_gradient = -(
        (epsilon + evaluation_pressure)
        * pressure_gravity
        / (radius**2 * metric)
    )

    f_term = (
        1.0
        - 4.0 * math.pi * radius**2 * (epsilon - evaluation_pressure)
    ) / metric
    q_term = (
        4.0
        * math.pi
        * (
            5.0 * epsilon
            + 9.0 * evaluation_pressure
            + (epsilon + evaluation_pressure) / cs2
            - 6.0 / (4.0 * math.pi * radius**2)
        )
        / metric
        - 4.0 * (pressure_gravity / (radius**2 * metric)) ** 2
    )
    y_gradient = -(
        y_value**2 + y_value * f_term + radius**2 * q_term
    ) / radius
    return mass_gradient, pressure_gradient, y_gradient


def _rk4_step(
    derivative: Callable[[float, State], State],
    radius: float,
    state: State,
    step: float,
) -> State:
    k1 = derivative(radius, state)
    k2 = derivative(radius + step / 2.0, _add(state, k1, step / 2.0))
    k3 = derivative(radius + step / 2.0, _add(state, k2, step / 2.0))
    k4 = derivative(radius + step, _add(state, k3, step))
    return tuple(
        value
        + step
        * (d1 + 2.0 * d2 + 2.0 * d3 + d4)
        / 6.0
        for value, d1, d2, d3, d4 in zip(state, k1, k2, k3, k4, strict=True)
    )  # type: ignore[return-value]


def _love_number(compactness: float, surface_y: float) -> float:
    c = compactness
    y = surface_y
    if not 0 < c < 0.5:
        raise OracleError("stellar compactness must satisfy 0 < M/R < 1/2")

    numerator = (
        (8.0 / 5.0)
        * c**5
        * (1.0 - 2.0 * c) ** 2
        * (2.0 + 2.0 * c * (y - 1.0) - y)
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
        * (2.0 - y + 2.0 * c * (y - 1.0))
        * math.log1p(-2.0 * c)
    )
    if denominator == 0:
        raise OracleError("singular Love-number denominator")
    k2 = numerator / denominator
    if not math.isfinite(k2) or k2 <= 0:
        raise OracleError("Love number is not finite and positive")
    return k2


def solve_star(
    eos: BarotropicEOS,
    central_pressure: float,
    *,
    maximum_step: float = 1.0e-3,
    minimum_step: float = 1.0e-8,
    pressure_step_fraction: float = 0.08,
    surface_pressure_fraction: float = 1.0e-8,
    surface_pressure_absolute: float | None = None,
    initial_radius: float = 1.0e-6,
    maximum_radius: float = 100.0,
    maximum_steps: int = 2_000_000,
) -> StellarModel:
    """Integrate a dimensionless TOV and l=2 Love system to a pressure floor."""

    if not math.isfinite(central_pressure) or central_pressure <= 0:
        raise ValueError("central_pressure must be finite and positive")
    if not 0 < minimum_step <= maximum_step:
        raise ValueError("step bounds must satisfy 0 < minimum_step <= maximum_step")
    if not 0 < pressure_step_fraction < 1:
        raise ValueError("pressure_step_fraction must lie in (0, 1)")
    if not 0 < surface_pressure_fraction < 1:
        raise ValueError("surface_pressure_fraction must lie in (0, 1)")
    if (
        surface_pressure_absolute is not None
        and (
            not math.isfinite(surface_pressure_absolute)
            or not 0 < surface_pressure_absolute < central_pressure
        )
    ):
        raise ValueError(
            "absolute surface pressure must lie between zero and central pressure"
        )
    if not 0 < initial_radius < maximum_radius:
        raise ValueError("radius bounds are invalid")

    central_epsilon = eos.energy_density(central_pressure)
    central_cs2 = eos.sound_speed_squared(central_pressure)
    if central_epsilon <= 0 or not 0 < central_cs2 <= 1:
        raise OracleError("central EOS state is non-positive or acausal")

    pressure_floor = (
        central_pressure * surface_pressure_fraction
        if surface_pressure_absolute is None
        else surface_pressure_absolute
    )
    radius = initial_radius
    state: State = (
        (4.0 / 3.0) * math.pi * central_epsilon * radius**3,
        central_pressure,
        2.0,
    )
    derivative = lambda r, values: _rhs(eos, r, values, pressure_floor)

    for step_count in range(1, maximum_steps + 1):
        old_radius = radius
        old_state = state
        pressure_gradient = derivative(radius, state)[1]
        pressure_scale = pressure_step_fraction * abs(state[1] / pressure_gradient)
        step = min(maximum_step, max(minimum_step, pressure_scale))
        if radius + step > maximum_radius:
            step = maximum_radius - radius
        if step <= 0:
            raise OracleError("maximum radius reached before the surface")

        state = _rk4_step(derivative, radius, state, step)
        radius += step

        if state[1] <= pressure_floor:
            old_pressure = old_state[1]
            new_pressure = state[1]
            fraction = (old_pressure - pressure_floor) / (old_pressure - new_pressure)
            fraction = min(1.0, max(0.0, fraction))
            radius = old_radius + fraction * step
            state = tuple(
                old + fraction * (new - old)
                for old, new in zip(old_state, state, strict=True)
            )  # type: ignore[assignment]
            mass, _, surface_y = state
            compactness = mass / radius
            love_k2 = _love_number(compactness, surface_y)
            tidal_lambda = (2.0 / 3.0) * love_k2 / compactness**5
            return StellarModel(
                central_pressure=central_pressure,
                mass=mass,
                radius=radius,
                compactness=compactness,
                love_k2=love_k2,
                tidal_lambda=tidal_lambda,
                surface_y=surface_y,
                steps=step_count,
                pressure_floor=pressure_floor,
            )

    raise OracleError("maximum step count reached before the surface")


def solve_sequence(
    eos: BarotropicEOS,
    central_pressures: Sequence[float],
    **solver_options: float | int,
) -> list[StellarModel]:
    return [
        solve_star(eos, pressure, **solver_options)
        for pressure in central_pressures
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the independent dimensionless NS-EOS TOV/Love oracle"
    )
    parser.add_argument(
        "--central-pressure",
        type=float,
        nargs="+",
        default=[0.05, 0.10, 0.20, 0.40],
    )
    parser.add_argument("--maximum-step", type=float, default=1.0e-3)
    args = parser.parse_args(argv)

    eos = RelativisticPolytrope()
    result = solve_sequence(
        eos,
        args.central_pressure,
        maximum_step=args.maximum_step,
    )
    print(json.dumps([asdict(model) for model in result], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
