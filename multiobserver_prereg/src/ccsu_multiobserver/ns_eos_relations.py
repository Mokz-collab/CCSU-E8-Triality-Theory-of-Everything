from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import numpy as np

from .ns_eos_local_charts import LocalChartEOS, evaluate_local_physics
from .ns_eos_low_density import (
    ChemicalPotentialDerivativeTemplate,
    ThermodynamicTable,
)
from .ns_eos_oracle import StellarModel
from .ns_eos_stellar_impact import (
    MEV_FM3_TO_GEOMETRIC_KM2,
    SOLAR_MASS_GEOMETRIC_KM,
    PiecewiseLinearBarotrope,
    build_low_density_barotrope,
    solve_physical_star,
)


class RelationTranslationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FiniteDomainBarotrope:
    """A tabulated EOS that refuses central states above its density domain."""

    delegate: PiecewiseLinearBarotrope
    maximum_pressure_mev_fm3: float
    maximum_density_nsat: float

    @property
    def surface_pressure(self) -> float:
        return self.delegate.surface_pressure

    def _check_pressure(self, pressure: float) -> None:
        maximum = (
            self.maximum_pressure_mev_fm3
            * MEV_FM3_TO_GEOMETRIC_KM2
        )
        if pressure > maximum * (1.0 + 1.0e-12):
            raise RelationTranslationError(
                "pressure exceeds the registered finite EOS domain"
            )

    def energy_density(self, pressure: float) -> float:
        self._check_pressure(pressure)
        return self.delegate.energy_density(pressure)

    def sound_speed_squared(self, pressure: float) -> float:
        self._check_pressure(pressure)
        return self.delegate.sound_speed_squared(pressure)


def build_finite_domain_barotrope(
    outer_crust: ThermodynamicTable,
    chiral_eft: ThermodynamicTable,
    template: ChemicalPotentialDerivativeTemplate,
    chart: LocalChartEOS,
    *,
    connector_points: int,
    projection_tolerance: float,
) -> FiniteDomainBarotrope:
    if not math.isclose(
        chart.pressure_mev_fm3[0],
        chiral_eft.last.p_mev_fm3,
        rel_tol=1.0e-12,
        abs_tol=0.0,
    ):
        raise RelationTranslationError(
            "chart pressure does not match the pinned EFT endpoint"
        )
    if not math.isclose(
        chart.energy_mev_fm3[0],
        chiral_eft.last.epsilon_mev_fm3,
        rel_tol=1.0e-12,
        abs_tol=0.0,
    ):
        raise RelationTranslationError(
            "chart energy does not match the pinned EFT endpoint"
        )
    diagnostics = evaluate_local_physics(chart, chiral_eft.last)
    if not diagnostics["all_local_checks_pass"]:
        raise RelationTranslationError(
            "chart failed local thermodynamic filters"
        )
    low_density = build_low_density_barotrope(
        outer_crust,
        chiral_eft,
        template,
        connector_kind="reference_tilted_v0_5_candidate",
        connector_points=connector_points,
        core_cs2=0.5,
        projection_tolerance=projection_tolerance,
    )
    pressure = (
        low_density.pressure_mev_fm3
        + chart.pressure_mev_fm3[1:]
    )
    energy = low_density.energy_mev_fm3 + chart.energy_mev_fm3[1:]
    final_interval_cs2 = (
        pressure[-1] - pressure[-2]
    ) / (
        energy[-1] - energy[-2]
    )
    delegate = PiecewiseLinearBarotrope(
        pressure_mev_fm3=pressure,
        energy_mev_fm3=energy,
        core_cs2=final_interval_cs2,
    )
    return FiniteDomainBarotrope(
        delegate=delegate,
        maximum_pressure_mev_fm3=chart.pressure_mev_fm3[-1],
        maximum_density_nsat=chart.density_nsat[-1],
    )


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def _stellar_record(
    target_mass: float,
    central_pressure: float,
    model: StellarModel,
) -> dict[str, float | int]:
    return {
        "target_mass_msun": target_mass,
        "central_pressure_mev_fm3": central_pressure,
        "mass_msun": model.mass / SOLAR_MASS_GEOMETRIC_KM,
        "radius_km": model.radius,
        "love_k2": model.love_k2,
        "tidal_lambda": model.tidal_lambda,
        "integration_steps": model.steps,
    }


def translate_stellar_relations(
    eos: FiniteDomainBarotrope,
    *,
    anchor_pressure_mev_fm3: float,
    target_masses_msun: Sequence[float],
    scan_points: int,
    target_mass_tolerance_msun: float,
    maximum_bisection_iterations: int,
    maximum_step_km: float,
    minimum_step_km: float,
    pressure_step_fraction: float,
    turnover_mass_drop_tolerance_msun: float,
) -> dict[str, object]:
    if scan_points < 12:
        raise ValueError("finite-domain scan requires at least 12 points")
    lower_pressure = anchor_pressure_mev_fm3 * (1.0 + 1.0e-6)
    upper_pressure = eos.maximum_pressure_mev_fm3 * (1.0 - 1.0e-12)
    if not lower_pressure < upper_pressure:
        raise RelationTranslationError("stellar pressure domain is empty")

    @lru_cache(maxsize=None)
    def solve(pressure: float) -> StellarModel:
        return solve_physical_star(
            eos,
            pressure,
            maximum_step_km=maximum_step_km,
            minimum_step_km=minimum_step_km,
            pressure_step_fraction=pressure_step_fraction,
        )

    pressure_grid = tuple(
        math.exp(
            math.log(lower_pressure)
            + index
            / (scan_points - 1)
            * math.log(upper_pressure / lower_pressure)
        )
        for index in range(scan_points)
    )
    models = tuple(solve(pressure) for pressure in pressure_grid)
    masses = tuple(
        model.mass / SOLAR_MASS_GEOMETRIC_KM for model in models
    )
    maximum_index = max(range(len(masses)), key=masses.__getitem__)
    maximum_sampled_mass = masses[maximum_index]
    endpoint_mass = masses[-1]
    domain_contains_turnover = (
        maximum_index < len(masses) - 1
        and maximum_sampled_mass - endpoint_mass
        > turnover_mass_drop_tolerance_msun
    )
    stable_end_index = (
        maximum_index if domain_contains_turnover else len(masses) - 1
    )
    stable_pressures = pressure_grid[: stable_end_index + 1]
    stable_masses = masses[: stable_end_index + 1]

    relation: list[dict[str, float | int]] = []
    unbracketed: list[float] = []
    for target in target_masses_msun:
        bracket: tuple[float, float] | None = None
        for left_p, right_p, left_m, right_m in zip(
            stable_pressures,
            stable_pressures[1:],
            stable_masses,
            stable_masses[1:],
            strict=False,
        ):
            if left_m <= target <= right_m:
                bracket = (left_p, right_p)
                break
        if bracket is None:
            unbracketed.append(float(target))
            continue
        left_pressure, right_pressure = bracket
        final_pressure = left_pressure
        final_model = solve(final_pressure)
        for _ in range(maximum_bisection_iterations):
            midpoint = (left_pressure + right_pressure) / 2.0
            model = solve(midpoint)
            mass = model.mass / SOLAR_MASS_GEOMETRIC_KM
            final_pressure = midpoint
            final_model = model
            if abs(mass - target) <= target_mass_tolerance_msun:
                break
            if mass < target:
                left_pressure = midpoint
            else:
                right_pressure = midpoint
        achieved_mass = (
            final_model.mass / SOLAR_MASS_GEOMETRIC_KM
        )
        if abs(achieved_mass - target) > target_mass_tolerance_msun:
            raise RelationTranslationError(
                f"target-mass solve failed for {target} Msun"
            )
        relation.append(
            _stellar_record(target, final_pressure, final_model)
        )

    stable_mass_limit = max(stable_masses)
    maximum_mass = (
        maximum_sampled_mass if domain_contains_turnover else None
    )
    gates = {
        "domain_contains_mass_turnover": domain_contains_turnover,
        "maximum_mass_at_least_2_0_msun": stable_mass_limit >= 2.0,
        "stable_branch_covers_1_0_to_2_2_msun": (
            stable_mass_limit >= 2.2
            and min(stable_masses) <= 1.0
        ),
        "all_registered_mass_anchors_translated": not unbracketed,
    }
    status = (
        "FINITE_DOMAIN_STELLAR_GATES_PASSED"
        if all(gates.values())
        else (
            "DOMAIN_TRUNCATED_BEFORE_MASS_TURNOVER"
            if not domain_contains_turnover
            else "FINITE_DOMAIN_STELLAR_GATES_FAILED"
        )
    )
    return {
        "status": status,
        "finite_domain_maximum_density_nsat": (
            eos.maximum_density_nsat
        ),
        "central_pressure_scan_mev_fm3": {
            "minimum": pressure_grid[0],
            "maximum": pressure_grid[-1],
            "points": len(pressure_grid),
        },
        "sampled_mass_range_msun": {
            "minimum": min(masses),
            "maximum": maximum_sampled_mass,
            "endpoint_at_6_nsat": endpoint_mass,
        },
        "maximum_mass_msun": maximum_mass,
        "maximum_mass_lower_bound_msun": stable_mass_limit,
        "maximum_mass_sample_index": maximum_index,
        "mass_radius_tidal_relation": relation,
        "unbracketed_mass_anchors_msun": unbracketed,
        "gates": gates,
        "all_stellar_gates_pass": all(gates.values()),
    }


def public_relation_projection(
    observer: str,
    chart: LocalChartEOS,
    stellar: dict[str, object],
    chiral_eft: ThermodynamicTable,
    density_anchors_nsat: Sequence[float],
) -> dict[str, object]:
    stellar_rows = stellar["mass_radius_tidal_relation"]
    maximum_mass = stellar["maximum_mass_msun"]
    maximum_lower_bound = stellar["maximum_mass_lower_bound_msun"]
    provenance = {
        "observer": observer,
        "local_chart": chart.chart,
        "source_event": "REGISTERED_SYNTHETIC_EXEMPLAR",
        "likelihood_family": "NONE_FORWARD_TRANSLATION",
        "prior_identifier": "PROPOSAL_BOX_NOT_PHYSICAL_PRIOR_v0.7",
        "translation_version": (
            "CCSU-MO-NS-EOS-001-RELATIONS-001-v0.1"
        ),
        "calibration_state": "DEVELOPMENT_NOT_CONFIRMATORY",
    }
    if observer == "GW":
        payload = {
            "tidal_deformability_mass": [
                {
                    "mass_msun": row["mass_msun"],
                    "tidal_lambda": row["tidal_lambda"],
                }
                for row in stellar_rows
            ],
            "maximum_mass_msun": maximum_mass,
            "maximum_mass_lower_bound_msun": maximum_lower_bound,
        }
    elif observer == "XRAY":
        payload = {
            "mass_radius": [
                {
                    "mass_msun": row["mass_msun"],
                    "radius_km": row["radius_km"],
                }
                for row in stellar_rows
            ],
            "maximum_mass_msun": maximum_mass,
            "maximum_mass_lower_bound_msun": maximum_lower_bound,
        }
    elif observer == "RADIO":
        payload = {
            "maximum_mass_msun": maximum_mass,
            "maximum_mass_lower_bound_msun": maximum_lower_bound,
        }
    elif observer == "NUCLEAR":
        density = np.asarray(
            [row.n_b_fm3 / 0.16 for row in chiral_eft.rows]
            + list(chart.density_nsat[1:]),
            dtype=float,
        )
        pressure = np.asarray(
            [row.p_mev_fm3 for row in chiral_eft.rows]
            + list(chart.pressure_mev_fm3[1:]),
            dtype=float,
        )
        energy = np.asarray(
            [row.epsilon_mev_fm3 for row in chiral_eft.rows]
            + list(chart.energy_mev_fm3[1:]),
            dtype=float,
        )
        anchors = [
            value
            for value in density_anchors_nsat
            if density[0] <= value <= density[-1]
        ]
        payload = {
            "pressure_energy_density": [
                {
                    "density_nsat": value,
                    "pressure_mev_fm3": float(
                        np.interp(value, density, pressure)
                    ),
                    "energy_mev_fm3": float(
                        np.interp(value, density, energy)
                    ),
                }
                for value in anchors
            ]
        }
    else:
        raise ValueError(f"unknown observer: {observer}")
    return {
        "provenance": provenance,
        "relations": payload,
        "local_parameters_included": False,
    }


def convergence_comparison(
    eos: FiniteDomainBarotrope,
    central_pressure_mev_fm3: float,
    *,
    coarse_step_km: float,
    fine_step_km: float,
    minimum_step_km: float,
    pressure_step_fraction: float,
) -> dict[str, object]:
    coarse = solve_physical_star(
        eos,
        central_pressure_mev_fm3,
        maximum_step_km=coarse_step_km,
        minimum_step_km=minimum_step_km,
        pressure_step_fraction=pressure_step_fraction,
    )
    fine = solve_physical_star(
        eos,
        central_pressure_mev_fm3,
        maximum_step_km=fine_step_km,
        minimum_step_km=minimum_step_km,
        pressure_step_fraction=pressure_step_fraction,
    )
    differences = {
        field: _relative_difference(
            getattr(coarse, field),
            getattr(fine, field),
        )
        for field in ("mass", "radius", "love_k2", "tidal_lambda")
    }
    return {
        "central_pressure_mev_fm3": central_pressure_mev_fm3,
        "coarse_maximum_step_km": coarse_step_km,
        "fine_maximum_step_km": fine_step_km,
        "relative_differences": differences,
    }
