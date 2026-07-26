from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .ns_eos_low_density import (
    ChemicalPotentialDerivativeTemplate,
    LowDensityContractError,
    ThermodynamicRow,
    build_chemical_potential_connector,
    build_reference_tilted_connector,
    git_blob_sha_file,
    sha256_file,
)


ORACLE_COLUMNS = (
    "n_b_fm3",
    "epsilon_mev_fm3",
    "p_mev_fm3",
)

ORACLE_UNITS = {
    "baryon_number_density": "fm^-3",
    "pressure": "MeV_fm^-3",
    "energy_density": "MeV_fm^-3",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LowDensityContractError(message)


def _relative_residual(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


@dataclass(frozen=True)
class UnifiedEOSRow:
    n_b_fm3: float
    epsilon_mev_fm3: float
    p_mev_fm3: float

    @property
    def mu_b_mev(self) -> float:
        return (
            self.epsilon_mev_fm3 + self.p_mev_fm3
        ) / self.n_b_fm3

    def as_thermodynamic_row(self, cs2: float = 0.0) -> ThermodynamicRow:
        return ThermodynamicRow(
            n_b_fm3=self.n_b_fm3,
            p_mev_fm3=self.p_mev_fm3,
            epsilon_mev_fm3=self.epsilon_mev_fm3,
            mu_b_mev=self.mu_b_mev,
            cs2=cs2,
        )


@dataclass(frozen=True)
class UnifiedEOSTable:
    manifest_id: str
    model_label: str
    validation_role: str
    source_commit: str
    table_path: str
    sha256: str
    upstream_git_blob_sha: str
    lower_anchor_n_b_fm3: float
    lower_predecessor_n_b_fm3: float
    upper_anchor_n_b_fm3: float
    target_upper_n_b_fm3: float
    rows: tuple[UnifiedEOSRow, ...]

    def inner_crust_rows(self) -> tuple[UnifiedEOSRow, ...]:
        lower_index = _find_exact_density(
            self.rows, self.lower_anchor_n_b_fm3
        )
        upper_index = _find_exact_density(
            self.rows, self.upper_anchor_n_b_fm3
        )
        _require(
            lower_index > 0 and upper_index > lower_index,
            "unified-EOS inner-crust slice indices are invalid",
        )
        predecessor = self.rows[lower_index - 1]
        _require(
            predecessor.n_b_fm3 == self.lower_predecessor_n_b_fm3,
            "unified-EOS lower-anchor predecessor changed",
        )
        _require(
            self.rows[lower_index].n_b_fm3
            / predecessor.n_b_fm3
            > 1.2,
            "unified-EOS lower anchor no longer follows the registered gap",
        )
        selected = self.rows[lower_index : upper_index + 1]
        for index, (left, right) in enumerate(
            zip(selected, selected[1:], strict=False)
        ):
            _require(
                right.n_b_fm3 > left.n_b_fm3,
                f"inner-crust rows {index}/{index + 1}: density is not increasing",
            )
            _require(
                right.epsilon_mev_fm3 > left.epsilon_mev_fm3,
                f"inner-crust rows {index}/{index + 1}: energy is not increasing",
            )
            _require(
                right.p_mev_fm3 > left.p_mev_fm3,
                f"inner-crust rows {index}/{index + 1}: pressure is not increasing",
            )
        return selected


@dataclass(frozen=True)
class ConnectorMetrics:
    pressure_log_weighted_rms: float
    pressure_log_max: float
    chemical_potential_span_weighted_rms: float
    chemical_potential_span_max: float
    cs2_interval_weighted_rms: float
    cs2_interval_max: float
    lower_endpoint_max_relative_residual: float
    upper_endpoint_max_relative_residual: float
    minimum_cs2: float
    maximum_cs2: float


def _find_exact_density(
    rows: tuple[UnifiedEOSRow, ...],
    target: float,
) -> int:
    matches = [
        index
        for index, row in enumerate(rows)
        if row.n_b_fm3 == target
    ]
    _require(
        len(matches) == 1,
        f"registered unified-EOS density {target} is not unique",
    )
    return matches[0]


def load_unified_eos_oracle(
    manifest_path: str | Path,
) -> UnifiedEOSTable:
    resolved_manifest = Path(manifest_path).resolve()
    manifest = yaml.safe_load(resolved_manifest.read_text(encoding="utf-8"))
    _require(manifest.get("schema_version") == 1, "oracle schema_version must equal 1")
    _require(
        manifest.get("source_kind") == "SCIENTIFIC_UNIFIED_EOS_ORACLE",
        "unified-EOS source_kind is invalid",
    )
    _require(
        manifest.get("provenance_mode") == "direct_upstream_git_blob",
        "unified-EOS provenance mode is invalid",
    )
    _require(
        manifest.get("raw_format") == "hcdas_unified_eos_v1",
        "unified-EOS raw format is invalid",
    )
    _require(
        tuple(manifest.get("columns", ())) == ORACLE_COLUMNS,
        "unified-EOS columns changed",
    )
    _require(
        manifest.get("canonical_units") == ORACLE_UNITS,
        "unified-EOS units changed",
    )
    _require(
        manifest.get("license_spdx") == "GPL-3.0-only",
        "unified-EOS licence identifier changed",
    )
    _require(
        manifest.get("redistribution_permitted") is True,
        "unified-EOS bytes are not marked redistributable",
    )

    source_commit = str(manifest.get("source_commit", ""))
    immutable_source_url = str(manifest.get("immutable_source_url", ""))
    _require(
        len(source_commit) == 40
        and all(character in "0123456789abcdef" for character in source_commit),
        "unified-EOS source commit is invalid",
    )
    _require(
        source_commit in immutable_source_url,
        "unified-EOS source URL is not commit-pinned",
    )
    _require(
        bool(manifest.get("retrieval_timestamp_utc")),
        "unified-EOS retrieval timestamp is missing",
    )

    table_path = (resolved_manifest.parent / manifest["table_path"]).resolve()
    expected_sha256 = str(manifest.get("sha256", "")).lower()
    expected_blob_sha = str(manifest.get("upstream_git_blob_sha", "")).lower()
    _require(
        sha256_file(table_path) == expected_sha256,
        "unified-EOS table sha256 mismatch",
    )
    _require(
        git_blob_sha_file(table_path) == expected_blob_sha,
        "unified-EOS table differs from the upstream Git blob",
    )
    license_path = (resolved_manifest.parent / manifest["license_path"]).resolve()
    _require(
        sha256_file(license_path) == manifest.get("license_sha256"),
        "unified-EOS licence sha256 mismatch",
    )

    lines = table_path.read_text(encoding="utf-8").splitlines()
    _require(
        lines
        and lines[0]
        == "# baryon density (fm^-3) energy density (MeV/fm^3) pressure (MeV/fm^3)",
        "unified-EOS header changed",
    )
    parsed_rows: list[UnifiedEOSRow] = []
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split()
        _require(
            len(fields) == 3,
            f"unified-EOS row {line_number} does not have three fields",
        )
        try:
            row = UnifiedEOSRow(*(float(field) for field in fields))
        except ValueError as exc:
            raise LowDensityContractError(
                f"unified-EOS row {line_number} contains invalid numeric data"
            ) from exc
        _require(
            all(math.isfinite(value) for value in asdict(row).values()),
            f"unified-EOS row {line_number} contains a non-finite value",
        )
        _require(
            row.n_b_fm3 > 0
            and row.epsilon_mev_fm3 > 0
            and row.p_mev_fm3 >= 0,
            f"unified-EOS row {line_number} is outside its physical domain",
        )
        parsed_rows.append(row)

    inner = manifest.get("inner_crust_slice", {})
    table = UnifiedEOSTable(
        manifest_id=str(manifest["oracle_manifest_id"]),
        model_label=str(manifest["model_label"]),
        validation_role=str(manifest["validation_role"]),
        source_commit=source_commit,
        table_path=str(table_path),
        sha256=expected_sha256,
        upstream_git_blob_sha=expected_blob_sha,
        lower_anchor_n_b_fm3=float(inner["lower_anchor_n_b_fm3"]),
        lower_predecessor_n_b_fm3=float(
            inner["lower_predecessor_n_b_fm3"]
        ),
        upper_anchor_n_b_fm3=float(inner["upper_anchor_n_b_fm3"]),
        target_upper_n_b_fm3=float(inner["target_upper_n_b_fm3"]),
        rows=tuple(parsed_rows),
    )
    table.inner_crust_rows()
    return table


def load_derivative_template(
    template_path: str | Path,
) -> ChemicalPotentialDerivativeTemplate:
    path = Path(template_path).resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    _require(
        record.get("schema")
        == "ccsu.multiobserver.inner-crust-derivative-template.v1",
        "inner-crust template schema changed",
    )
    source = record.get("calibration_source", {})
    manifest_path = (path.parent / source.get("manifest_path", "")).resolve()
    _require(
        sha256_file(manifest_path) == source.get("manifest_sha256"),
        "inner-crust template calibration-manifest hash mismatch",
    )
    oracle = load_unified_eos_oracle(manifest_path)
    _require(
        oracle.sha256 == source.get("table_sha256")
        and oracle.upstream_git_blob_sha == source.get("upstream_git_blob_sha"),
        "inner-crust template calibration-table provenance mismatch",
    )
    _require(
        oracle.source_commit == source.get("source_commit"),
        "inner-crust template calibration-source commit mismatch",
    )
    generator = record.get("generator", {})
    generator_path = (path.parent / generator.get("path", "")).resolve()
    _require(
        sha256_file(generator_path) == generator.get("sha256"),
        "inner-crust template generator hash mismatch",
    )
    fit = record.get("fit", {})
    template = ChemicalPotentialDerivativeTemplate(
        template_id=str(record["template_id"]),
        exponents=tuple(float(value) for value in fit["exponents"]),
        mass_weights=tuple(float(value) for value in fit["mass_weights"]),
    )
    _require(
        fit.get("weights_non_negative") is True,
        "inner-crust template does not freeze non-negative weights",
    )
    _require(
        record.get("scientific_semantics", {}).get("probabilistic_prior")
        is False,
        "inner-crust template cannot be promoted to a probabilistic prior",
    )
    return template


def _node_weights(rows: tuple[UnifiedEOSRow, ...]) -> tuple[float, ...]:
    span = rows[-1].n_b_fm3 - rows[0].n_b_fm3
    weights: list[float] = []
    for index, row in enumerate(rows):
        if index == 0:
            width = (rows[1].n_b_fm3 - row.n_b_fm3) / 2.0
        elif index == len(rows) - 1:
            width = (row.n_b_fm3 - rows[index - 1].n_b_fm3) / 2.0
        else:
            width = (
                rows[index + 1].n_b_fm3
                - rows[index - 1].n_b_fm3
            ) / 2.0
        weights.append(width / span)
    return tuple(weights)


def _weighted_rms(
    residuals: list[float],
    weights: list[float] | tuple[float, ...],
) -> float:
    return math.sqrt(
        sum(
            residual**2 * weight
            for residual, weight in zip(residuals, weights, strict=True)
        )
        / sum(weights)
    )


def connector_metrics(
    oracle: UnifiedEOSTable,
    connector_kind: str,
    template: ChemicalPotentialDerivativeTemplate | None = None,
) -> ConnectorMetrics:
    rows = oracle.inner_crust_rows()
    lower = rows[0].as_thermodynamic_row()
    upper = rows[-1].as_thermodynamic_row()
    if connector_kind == "endpoint_exponential_v0_4":
        connector = build_chemical_potential_connector(lower, upper)
    elif connector_kind == "reference_tilted_v0_5_candidate":
        _require(template is not None, "reference-tilted connector needs a template")
        connector = build_reference_tilted_connector(lower, upper, template)
    else:
        raise LowDensityContractError(
            f"unknown connector kind: {connector_kind}"
        )

    node_weights = _node_weights(rows)
    chemical_potential_span = upper.mu_b_mev - lower.mu_b_mev
    pressure_residuals: list[float] = []
    chemical_potential_residuals: list[float] = []
    connector_cs2: list[float] = []
    for row in rows:
        reconstructed = connector.evaluate(row.n_b_fm3)
        pressure_residuals.append(
            abs(math.log(reconstructed.p_mev_fm3 / row.p_mev_fm3))
        )
        chemical_potential_residuals.append(
            abs(reconstructed.mu_b_mev - row.mu_b_mev)
            / chemical_potential_span
        )
        connector_cs2.append(reconstructed.cs2)

    density_span = rows[-1].n_b_fm3 - rows[0].n_b_fm3
    cs2_residuals: list[float] = []
    interval_weights: list[float] = []
    for left, right in zip(rows, rows[1:], strict=False):
        midpoint_density = (
            left.n_b_fm3 + right.n_b_fm3
        ) / 2.0
        oracle_cs2 = (
            right.p_mev_fm3 - left.p_mev_fm3
        ) / (
            right.epsilon_mev_fm3 - left.epsilon_mev_fm3
        )
        reconstructed_cs2 = connector.evaluate(midpoint_density).cs2
        cs2_residuals.append(abs(reconstructed_cs2 - oracle_cs2))
        interval_weights.append(
            (right.n_b_fm3 - left.n_b_fm3) / density_span
        )
        connector_cs2.append(reconstructed_cs2)

    endpoint_fields = (
        "n_b_fm3",
        "p_mev_fm3",
        "epsilon_mev_fm3",
        "mu_b_mev",
    )
    lower_reconstructed = connector.evaluate(lower.n_b_fm3)
    upper_reconstructed = connector.evaluate(upper.n_b_fm3)
    lower_endpoint_residual = max(
        _relative_residual(
            getattr(lower_reconstructed, field),
            getattr(lower, field),
        )
        for field in endpoint_fields
    )
    upper_endpoint_residual = max(
        _relative_residual(
            getattr(upper_reconstructed, field),
            getattr(upper, field),
        )
        for field in endpoint_fields
    )
    return ConnectorMetrics(
        pressure_log_weighted_rms=_weighted_rms(
            pressure_residuals, node_weights
        ),
        pressure_log_max=max(pressure_residuals),
        chemical_potential_span_weighted_rms=_weighted_rms(
            chemical_potential_residuals, node_weights
        ),
        chemical_potential_span_max=max(chemical_potential_residuals),
        cs2_interval_weighted_rms=_weighted_rms(
            cs2_residuals, interval_weights
        ),
        cs2_interval_max=max(cs2_residuals),
        lower_endpoint_max_relative_residual=lower_endpoint_residual,
        upper_endpoint_max_relative_residual=upper_endpoint_residual,
        minimum_cs2=min(connector_cs2),
        maximum_cs2=max(connector_cs2),
    )


def evaluate_thresholds(
    metrics: ConnectorMetrics,
    thresholds: dict[str, Any],
) -> dict[str, bool]:
    result: dict[str, bool] = {}
    values = asdict(metrics)
    for metric, limit in thresholds.items():
        _require(metric in values, f"unknown connector metric threshold: {metric}")
        if metric == "minimum_cs2":
            result[metric] = values[metric] >= float(limit)
        else:
            result[metric] = values[metric] <= float(limit)
    return result


def validation_record_sha256(record: dict[str, Any]) -> str:
    encoded = (
        json.dumps(record, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
