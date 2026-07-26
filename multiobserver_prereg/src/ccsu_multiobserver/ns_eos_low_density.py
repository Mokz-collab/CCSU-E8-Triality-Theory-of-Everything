from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


MEV_FM3_TO_PA = 1.602176634e32
MEV_FM3_TO_ERG_CM3 = 1.602176634e33
MEV_FM3_TO_G_CM3 = 1.7826619216278976e12
FM3_TO_CM3_NUMBER_DENSITY = 1.0e39

REQUIRED_COLUMNS = (
    "n_b_fm3",
    "p_mev_fm3",
    "epsilon_mev_fm3",
    "mu_b_mev",
    "cs2",
)

CANONICAL_UNITS = {
    "baryon_number_density": "fm^-3",
    "pressure": "MeV_fm^-3",
    "energy_density": "MeV_fm^-3",
    "baryon_chemical_potential": "MeV",
    "sound_speed_squared": "dimensionless_c_equals_1",
}


class LowDensityContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LowDensityContractError(message)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ThermodynamicRow:
    n_b_fm3: float
    p_mev_fm3: float
    epsilon_mev_fm3: float
    mu_b_mev: float
    cs2: float


@dataclass(frozen=True)
class ThermodynamicTable:
    manifest_id: str
    model_label: str
    source_kind: str
    table_path: str
    sha256: str
    rows: tuple[ThermodynamicRow, ...]

    @property
    def first(self) -> ThermodynamicRow:
        return self.rows[0]

    @property
    def last(self) -> ThermodynamicRow:
        return self.rows[-1]


@dataclass(frozen=True)
class MatchingResiduals:
    baryon_number_density: float
    pressure: float
    energy_density: float
    baryon_chemical_potential: float


@dataclass(frozen=True)
class ChemicalPotentialConnector:
    """Thermodynamically exact bridge between two cold-EOS endpoints.

    The dimensionless bridge coordinate is x=(n-n0)/(n1-n0), and
    mu(x)=mu0 + (mu1-mu0) expm1(k*x)/expm1(k).  The shape k is selected
    from the endpoint pressure difference.  Pressure and energy density then
    follow from dP=n dmu and epsilon=n*mu-P.
    """

    lower: ThermodynamicRow
    upper: ThermodynamicRow
    shape: float

    def evaluate(self, baryon_density_fm3: float) -> ThermodynamicRow:
        n0 = self.lower.n_b_fm3
        n1 = self.upper.n_b_fm3
        if not n0 <= baryon_density_fm3 <= n1:
            raise LowDensityContractError(
                "connector evaluation lies outside its density interval"
            )
        density_span = n1 - n0
        x = (baryon_density_fm3 - n0) / density_span
        chemical_potential_span = self.upper.mu_b_mev - self.lower.mu_b_mev
        h_value = _bridge_h(x, self.shape)
        h_integral = _bridge_h_integral(x, self.shape)
        h_derivative = _bridge_h_derivative(x, self.shape)

        chemical_potential = (
            self.lower.mu_b_mev + chemical_potential_span * h_value
        )
        energy_density = (
            self.lower.epsilon_mev_fm3
            + density_span
            * (
                self.lower.mu_b_mev * x
                + chemical_potential_span * h_integral
            )
        )
        pressure = baryon_density_fm3 * chemical_potential - energy_density
        chemical_potential_gradient = (
            chemical_potential_span * h_derivative / density_span
        )
        cs2 = (
            baryon_density_fm3
            * chemical_potential_gradient
            / chemical_potential
        )
        if not 0 <= cs2 <= 1:
            raise LowDensityContractError(
                "inner-crust connector violates 0 <= c_s^2 <= 1"
            )
        return ThermodynamicRow(
            n_b_fm3=baryon_density_fm3,
            p_mev_fm3=pressure,
            epsilon_mev_fm3=energy_density,
            mu_b_mev=chemical_potential,
            cs2=cs2,
        )

    def sample(self, points: int) -> tuple[ThermodynamicRow, ...]:
        if points < 2:
            raise ValueError("connector sample requires at least two points")
        n0 = self.lower.n_b_fm3
        span = self.upper.n_b_fm3 - n0
        return tuple(
            self.evaluate(n0 + span * index / (points - 1))
            for index in range(points)
        )


def pressure_mev_fm3_to_pa(value: float) -> float:
    return value * MEV_FM3_TO_PA


def energy_mev_fm3_to_erg_cm3(value: float) -> float:
    return value * MEV_FM3_TO_ERG_CM3


def energy_mev_fm3_to_mass_g_cm3(value: float) -> float:
    return value * MEV_FM3_TO_G_CM3


def number_density_fm3_to_cm3(value: float) -> float:
    return value * FM3_TO_CM3_NUMBER_DENSITY


def _relative_residual(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), 1.0e-300)
    return abs(left - right) / scale


def _bridge_mean(shape: float) -> float:
    if abs(shape) < 1.0e-5:
        return 0.5 - shape / 12.0 + shape**3 / 720.0
    return 1.0 / shape - 1.0 / math.expm1(shape)


def _bridge_h(x: float, shape: float) -> float:
    if abs(shape) < 1.0e-8:
        return x
    return math.expm1(shape * x) / math.expm1(shape)


def _bridge_h_integral(x: float, shape: float) -> float:
    if abs(shape) < 1.0e-6:
        return x**2 / 2.0 + shape * (x**3 / 6.0 - x**2 / 4.0)
    return (math.expm1(shape * x) / shape - x) / math.expm1(shape)


def _bridge_h_derivative(x: float, shape: float) -> float:
    if abs(shape) < 1.0e-8:
        return 1.0
    return shape * math.exp(shape * x) / math.expm1(shape)


def _solve_bridge_shape(target_mean: float) -> float:
    _require(0 < target_mean < 1, "connector target mean must lie in (0, 1)")
    lower_shape = -100.0
    upper_shape = 100.0
    _require(
        _bridge_mean(lower_shape) >= target_mean >= _bridge_mean(upper_shape),
        "connector endpoint geometry requires an extreme unsupported shape",
    )
    for _ in range(200):
        midpoint = (lower_shape + upper_shape) / 2.0
        midpoint_mean = _bridge_mean(midpoint)
        if midpoint_mean > target_mean:
            lower_shape = midpoint
        else:
            upper_shape = midpoint
    shape = (lower_shape + upper_shape) / 2.0
    return 0.0 if abs(shape) < 1.0e-12 else shape


def build_chemical_potential_connector(
    lower: ThermodynamicRow,
    upper: ThermodynamicRow,
    *,
    endpoint_identity_relative_tolerance: float = 1.0e-8,
) -> ChemicalPotentialConnector:
    _require(
        upper.n_b_fm3 > lower.n_b_fm3,
        "connector upper density must exceed lower density",
    )
    _require(
        upper.mu_b_mev > lower.mu_b_mev,
        "connector requires increasing baryon chemical potential",
    )
    _require(
        upper.p_mev_fm3 > lower.p_mev_fm3,
        "connector requires increasing pressure",
    )
    for label, endpoint in (("lower", lower), ("upper", upper)):
        identity_mu = (
            endpoint.epsilon_mev_fm3 + endpoint.p_mev_fm3
        ) / endpoint.n_b_fm3
        _require(
            _relative_residual(identity_mu, endpoint.mu_b_mev)
            <= endpoint_identity_relative_tolerance,
            f"{label} connector endpoint violates mu=(epsilon+p)/n",
        )

    density_span = upper.n_b_fm3 - lower.n_b_fm3
    chemical_potential_span = upper.mu_b_mev - lower.mu_b_mev
    pressure_span = upper.p_mev_fm3 - lower.p_mev_fm3
    pressure_weighted_density = pressure_span / chemical_potential_span
    _require(
        lower.n_b_fm3
        < pressure_weighted_density
        < upper.n_b_fm3,
        "endpoint pressure and chemical-potential spans violate dP=n dmu",
    )
    target_mean = (
        upper.n_b_fm3 - pressure_weighted_density
    ) / density_span
    connector = ChemicalPotentialConnector(
        lower=lower,
        upper=upper,
        shape=_solve_bridge_shape(target_mean),
    )
    reconstructed_lower = connector.evaluate(lower.n_b_fm3)
    reconstructed_upper = connector.evaluate(upper.n_b_fm3)
    for label, expected, reconstructed in (
        ("lower", lower, reconstructed_lower),
        ("upper", upper, reconstructed_upper),
    ):
        for field in (
            "n_b_fm3",
            "p_mev_fm3",
            "epsilon_mev_fm3",
            "mu_b_mev",
        ):
            _require(
                _relative_residual(
                    getattr(expected, field), getattr(reconstructed, field)
                )
                <= endpoint_identity_relative_tolerance,
                f"{label} connector reconstruction failed for {field}",
            )
    return connector


def _parse_row(raw: dict[str, str], row_number: int) -> ThermodynamicRow:
    try:
        values = {column: float(raw[column]) for column in REQUIRED_COLUMNS}
    except (KeyError, TypeError, ValueError) as exc:
        raise LowDensityContractError(
            f"invalid numeric value in table row {row_number}"
        ) from exc
    _require(
        all(math.isfinite(value) for value in values.values()),
        f"non-finite value in table row {row_number}",
    )
    return ThermodynamicRow(**values)


def _validate_rows(
    rows: tuple[ThermodynamicRow, ...],
    *,
    identity_tolerance: float,
    cs2_absolute_tolerance: float,
) -> None:
    _require(len(rows) >= 2, "thermodynamic table must contain at least two rows")
    for index, row in enumerate(rows):
        _require(row.n_b_fm3 > 0, f"row {index}: baryon density must be positive")
        _require(row.p_mev_fm3 >= 0, f"row {index}: pressure must be non-negative")
        _require(
            row.epsilon_mev_fm3 > 0,
            f"row {index}: energy density must be positive",
        )
        _require(row.mu_b_mev > 0, f"row {index}: chemical potential must be positive")
        _require(0 <= row.cs2 <= 1, f"row {index}: c_s^2 must lie in [0, 1]")
        identity_mu = (row.epsilon_mev_fm3 + row.p_mev_fm3) / row.n_b_fm3
        _require(
            _relative_residual(identity_mu, row.mu_b_mev) <= identity_tolerance,
            f"row {index}: mu != (epsilon + p) / n",
        )

    for index, (left, right) in enumerate(zip(rows, rows[1:])):
        _require(
            right.n_b_fm3 > left.n_b_fm3,
            f"rows {index}/{index + 1}: baryon density is not strictly increasing",
        )
        _require(
            right.p_mev_fm3 >= left.p_mev_fm3,
            f"rows {index}/{index + 1}: pressure decreases",
        )
        _require(
            right.epsilon_mev_fm3 > left.epsilon_mev_fm3,
            f"rows {index}/{index + 1}: energy density is not strictly increasing",
        )
        secant_cs2 = (
            (right.p_mev_fm3 - left.p_mev_fm3)
            / (right.epsilon_mev_fm3 - left.epsilon_mev_fm3)
        )
        tabulated_midpoint_cs2 = (left.cs2 + right.cs2) / 2.0
        _require(
            abs(secant_cs2 - tabulated_midpoint_cs2) <= cs2_absolute_tolerance,
            f"rows {index}/{index + 1}: c_s^2 conflicts with dp/dE",
        )


def load_thermodynamic_table(manifest_path: str | Path) -> ThermodynamicTable:
    resolved_manifest = Path(manifest_path).resolve()
    with resolved_manifest.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)

    _require(manifest.get("schema_version") == 1, "manifest schema_version must equal 1")
    _require(bool(manifest.get("table_manifest_id")), "table_manifest_id is required")
    _require(bool(manifest.get("model_label")), "model_label is required")
    _require(bool(manifest.get("source_kind")), "source_kind is required")
    _require(bool(manifest.get("license_spdx")), "license_spdx is required")
    _require(
        manifest.get("redistribution_permitted") is True,
        "table bytes cannot be loaded from a non-redistributable manifest",
    )
    _require(
        manifest.get("canonical_units") == CANONICAL_UNITS,
        "manifest units do not match the canonical unit contract",
    )

    table_path = (resolved_manifest.parent / manifest["table_path"]).resolve()
    expected_sha256 = str(manifest.get("sha256", "")).lower()
    _require(len(expected_sha256) == 64, "manifest sha256 is invalid")
    actual_sha256 = sha256_file(table_path)
    _require(actual_sha256 == expected_sha256, "table sha256 mismatch")

    with table_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ()) == REQUIRED_COLUMNS,
            "table columns or column order violate the contract",
        )
        rows = tuple(
            _parse_row(raw, row_number)
            for row_number, raw in enumerate(reader, start=2)
        )

    validation = manifest.get("validation", {})
    identity_tolerance = float(
        validation.get("thermodynamic_identity_relative_tolerance", 1.0e-8)
    )
    cs2_absolute_tolerance = float(
        validation.get("finite_difference_cs2_absolute_tolerance", 1.0e-3)
    )
    _require(identity_tolerance > 0, "identity tolerance must be positive")
    _require(cs2_absolute_tolerance > 0, "c_s^2 tolerance must be positive")
    _validate_rows(
        rows,
        identity_tolerance=identity_tolerance,
        cs2_absolute_tolerance=cs2_absolute_tolerance,
    )
    return ThermodynamicTable(
        manifest_id=manifest["table_manifest_id"],
        model_label=manifest["model_label"],
        source_kind=manifest["source_kind"],
        table_path=str(table_path),
        sha256=actual_sha256,
        rows=rows,
    )


def matching_residuals(
    lower_density_table: ThermodynamicTable,
    upper_density_table: ThermodynamicTable,
) -> MatchingResiduals:
    lower = lower_density_table.last
    upper = upper_density_table.first
    return MatchingResiduals(
        baryon_number_density=_relative_residual(lower.n_b_fm3, upper.n_b_fm3),
        pressure=_relative_residual(lower.p_mev_fm3, upper.p_mev_fm3),
        energy_density=_relative_residual(
            lower.epsilon_mev_fm3, upper.epsilon_mev_fm3
        ),
        baryon_chemical_potential=_relative_residual(
            lower.mu_b_mev, upper.mu_b_mev
        ),
    )


def validate_smooth_match(
    lower_density_table: ThermodynamicTable,
    upper_density_table: ThermodynamicTable,
    *,
    relative_tolerance: float | dict[str, float] = 1.0e-6,
) -> MatchingResiduals:
    residuals = matching_residuals(lower_density_table, upper_density_table)
    tolerance_by_field = (
        {field: float(relative_tolerance) for field in asdict(residuals)}
        if isinstance(relative_tolerance, (float, int))
        else relative_tolerance
    )
    for field, residual in asdict(residuals).items():
        _require(field in tolerance_by_field, f"missing matching tolerance for {field}")
        _require(
            residual <= float(tolerance_by_field[field]),
            f"smooth-match residual exceeds tolerance for {field}",
        )
    return residuals


def table_summary(table: ThermodynamicTable) -> dict[str, Any]:
    return {
        "manifest_id": table.manifest_id,
        "model_label": table.model_label,
        "source_kind": table.source_kind,
        "sha256": table.sha256,
        "rows": len(table.rows),
        "density_range_fm3": [table.first.n_b_fm3, table.last.n_b_fm3],
        "pressure_range_mev_fm3": [
            table.first.p_mev_fm3,
            table.last.p_mev_fm3,
        ],
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a pinned CCSU NS-EOS low-density table"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--match-upper-manifest", type=Path)
    args = parser.parse_args(argv)

    lower = load_thermodynamic_table(args.manifest)
    output: dict[str, Any] = {"table": table_summary(lower)}
    if args.match_upper_manifest is not None:
        upper = load_thermodynamic_table(args.match_upper_manifest)
        output["upper_table"] = table_summary(upper)
        output["matching_residuals"] = asdict(validate_smooth_match(lower, upper))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
