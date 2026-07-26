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

KOLIOGI_OUTER_CRUST_COLUMNS = (
    "density",
    "A",
    "Z",
    "Nucleus",
    "energy",
    "pressure",
    "chemical_potential",
    "electron_chemical_potential",
    "B/A",
    "Gamma",
    "cs/c",
    "BE_source",
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


def git_blob_sha_file(path: str | Path) -> str:
    payload = Path(path).read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


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
    provenance_mode: str
    raw_format: str
    license_spdx: str
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


def _parse_koliogi_outer_crust_row(
    raw: dict[str, str], row_number: int
) -> ThermodynamicRow:
    try:
        speed_ratio = float(raw["cs/c"])
        row = ThermodynamicRow(
            n_b_fm3=float(raw["density"]),
            p_mev_fm3=float(raw["pressure"]),
            epsilon_mev_fm3=float(raw["energy"]),
            mu_b_mev=float(raw["chemical_potential"]),
            cs2=speed_ratio**2,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LowDensityContractError(
            f"invalid Koliogi outer-crust row {row_number}"
        ) from exc
    _require(
        all(math.isfinite(value) for value in asdict(row).values()),
        f"non-finite value in Koliogi outer-crust row {row_number}",
    )
    return row


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

    source_kind = str(manifest["source_kind"])
    provenance_mode = str(
        manifest.get("provenance_mode", "direct_upstream_git_blob")
    )
    raw_format = str(manifest.get("raw_format", "canonical_csv_v1"))
    if source_kind != "SYNTHETIC_TEST_ONLY":
        source_commit = str(manifest.get("source_commit", ""))
        immutable_source_url = str(manifest.get("immutable_source_url", ""))
        _require(
            len(source_commit) == 40
            and all(
                character in "0123456789abcdef" for character in source_commit
            ),
            "scientific manifest source_commit is invalid",
        )
        _require(
            source_commit in immutable_source_url,
            "scientific source URL is not pinned to source_commit",
        )
        _require(
            bool(manifest.get("retrieval_timestamp_utc")),
            "scientific retrieval timestamp is required",
        )
        license_path = (resolved_manifest.parent / manifest["license_path"]).resolve()
        _require(license_path.is_file(), "scientific license file is missing")
        _require(
            sha256_file(license_path) == manifest.get("license_sha256"),
            "scientific license sha256 mismatch",
        )
        if provenance_mode == "direct_upstream_git_blob":
            upstream_git_blob_sha = str(
                manifest.get("upstream_git_blob_sha", "")
            )
            _require(
                len(upstream_git_blob_sha) == 40,
                "scientific upstream Git blob SHA is invalid",
            )
            _require(
                git_blob_sha_file(table_path) == upstream_git_blob_sha,
                "scientific table differs from the pinned upstream Git blob",
            )
        elif provenance_mode == "deterministic_generated_output":
            generated = manifest.get("generated_provenance", {})
            _require(
                isinstance(generated, dict),
                "generated scientific provenance must be a mapping",
            )

            def require_generated_file(
                path_field: str, hash_field: str
            ) -> Path:
                generated_path = (
                    resolved_manifest.parent / generated.get(path_field, "")
                ).resolve()
                expected_hash = str(generated.get(hash_field, "")).lower()
                _require(
                    generated_path.is_file(),
                    f"generated provenance file is missing: {path_field}",
                )
                _require(
                    len(expected_hash) == 64,
                    f"generated provenance hash is invalid: {hash_field}",
                )
                _require(
                    sha256_file(generated_path) == expected_hash,
                    f"generated provenance hash mismatch: {path_field}",
                )
                return generated_path

            generator_path = require_generated_file(
                "generator_path", "generator_sha256"
            )
            generation_record_path = require_generated_file(
                "generation_record_path", "generation_record_sha256"
            )
            config_path = require_generated_file(
                "config_path", "config_sha256"
            )
            raw_output_path = require_generated_file(
                "raw_output_path", "raw_output_sha256"
            )
            _require(
                generator_path.suffix == ".py",
                "generated scientific data require a Python generator",
            )
            with generation_record_path.open("r", encoding="utf-8") as handle:
                generation_record = json.load(handle)
            _require(
                generation_record.get("source", {}).get("commit")
                == source_commit,
                "generation record source commit mismatch",
            )
            _require(
                generation_record.get("build", {}).get("binary_sha256")
                == generated.get("build_binary_sha256"),
                "generation record build-binary hash mismatch",
            )
            _require(
                generation_record.get("build_dependency", {})
                .get("yaml_cpp", {})
                .get("commit")
                == generated.get("yaml_cpp_commit"),
                "generation record yaml-cpp commit mismatch",
            )
            member_label = str(generated.get("member_label", ""))
            product = generation_record.get("products", {}).get(
                member_label, {}
            )
            _require(
                product.get("config", {}).get("sha256")
                == sha256_file(config_path),
                "generation record config hash mismatch",
            )
            _require(
                product.get("raw", {}).get("sha256")
                == sha256_file(raw_output_path),
                "generation record raw-output hash mismatch",
            )
            _require(
                product.get("anchor", {}).get("sha256") == actual_sha256,
                "generation record anchor hash mismatch",
            )
            semantics = generation_record.get("scientific_semantics", {})
            _require(
                semantics.get("envelope_type")
                == "coherent_interaction_reference_envelope",
                "generated χEFT envelope semantics are not frozen",
            )
            _require(
                semantics.get("probabilistic_coverage") is None
                and semantics.get("formal_chiral_truncation_error") is False,
                "generated χEFT members cannot claim probabilistic coverage",
            )
        else:
            raise LowDensityContractError(
                f"unsupported scientific provenance_mode: {provenance_mode}"
            )

    with table_path.open("r", encoding="utf-8", newline="") as handle:
        if raw_format == "canonical_csv_v1":
            reader = csv.DictReader(handle)
            _require(
                tuple(reader.fieldnames or ()) == REQUIRED_COLUMNS,
                "table columns or column order violate the contract",
            )
            rows = tuple(
                _parse_row(raw, row_number)
                for row_number, raw in enumerate(reader, start=2)
            )
        elif raw_format == "koliogi_outer_crust_v1":
            reader = csv.DictReader(handle, delimiter="\t")
            _require(
                tuple(reader.fieldnames or ()) == KOLIOGI_OUTER_CRUST_COLUMNS,
                "Koliogi table columns or column order violate the contract",
            )
            rows = tuple(
                _parse_koliogi_outer_crust_row(raw, row_number)
                for row_number, raw in enumerate(reader, start=2)
            )
        else:
            raise LowDensityContractError(f"unsupported raw_format: {raw_format}")

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
        source_kind=source_kind,
        provenance_mode=provenance_mode,
        raw_format=raw_format,
        license_spdx=manifest["license_spdx"],
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
        "provenance_mode": table.provenance_mode,
        "raw_format": table.raw_format,
        "license_spdx": table.license_spdx,
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
