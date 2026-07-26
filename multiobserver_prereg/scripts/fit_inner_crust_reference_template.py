#!/usr/bin/env python3
"""Fit the frozen positive derivative template from the IOPB calibration EOS."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import nnls

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_unified_eos_oracle,
)
from ccsu_multiobserver.ns_eos_low_density import sha256_file


TEMPLATE_ID = "CCSU-MO-NS-EOS-001-INNER-CRUST-TEMPLATE-001"
EXPONENTS = np.asarray((-40.0, 0.0, 40.0), dtype=float)
SUM_CONSTRAINT_WEIGHT = 100.0


def _component_cdf(x: np.ndarray, exponent: float) -> np.ndarray:
    if exponent == 0.0:
        return x
    return np.expm1(exponent * x) / np.expm1(exponent)


def _node_weights(x: np.ndarray) -> np.ndarray:
    weights = np.empty_like(x)
    weights[0] = (x[1] - x[0]) / 2.0
    weights[-1] = (x[-1] - x[-2]) / 2.0
    weights[1:-1] = (x[2:] - x[:-2]) / 2.0
    return weights


def fit_template(
    manifest_path: Path,
    output_path: Path,
    created_utc: str,
) -> dict[str, object]:
    oracle = load_unified_eos_oracle(manifest_path)
    rows = oracle.inner_crust_rows()
    lower = rows[0]
    upper = rows[-1]
    density_span = upper.n_b_fm3 - lower.n_b_fm3
    chemical_potential_span = upper.mu_b_mev - lower.mu_b_mev
    x = np.asarray(
        [
            (row.n_b_fm3 - lower.n_b_fm3) / density_span
            for row in rows
        ],
        dtype=float,
    )
    normalized_mu = np.asarray(
        [
            (row.mu_b_mev - lower.mu_b_mev) / chemical_potential_span
            for row in rows
        ],
        dtype=float,
    )
    weights = _node_weights(x)
    basis = np.column_stack(
        [_component_cdf(x, exponent) for exponent in EXPONENTS]
    )
    augmented_basis = np.vstack(
        (
            basis * np.sqrt(weights[:, np.newaxis]),
            np.full((1, len(EXPONENTS)), SUM_CONSTRAINT_WEIGHT),
        )
    )
    augmented_target = np.concatenate(
        (
            normalized_mu * np.sqrt(weights),
            np.asarray((SUM_CONSTRAINT_WEIGHT,)),
        )
    )
    mass_weights, _ = nnls(augmented_basis, augmented_target)
    mass_weights /= mass_weights.sum()
    fitted = basis @ mass_weights
    weighted_rms = float(
        np.sqrt(np.average((fitted - normalized_mu) ** 2, weights=weights))
    )
    maximum_absolute_residual = float(
        np.max(np.abs(fitted - normalized_mu))
    )

    generator_path = Path(__file__).resolve()
    manifest_relative = Path(manifest_path).name
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.inner-crust-derivative-template.v1",
        "template_id": TEMPLATE_ID,
        "status": "DEVELOPMENT_CALIBRATED_NOT_CONFIRMATORY",
        "created_utc": created_utc,
        "calibration_source": {
            "model_label": oracle.model_label,
            "validation_role": oracle.validation_role,
            "manifest_path": str(manifest_relative),
            "manifest_sha256": sha256_file(manifest_path),
            "table_sha256": oracle.sha256,
            "upstream_git_blob_sha": oracle.upstream_git_blob_sha,
            "source_commit": oracle.source_commit,
            "density_anchors_fm3": [
                lower.n_b_fm3,
                upper.n_b_fm3,
            ],
            "rows": len(rows),
        },
        "fit": {
            "method": "density_weighted_non_negative_least_squares",
            "target": "normalized_baryon_chemical_potential",
            "basis": "normalized_exponential_derivative_mixture",
            "exponents": [float(value) for value in EXPONENTS],
            "mass_weights": [float(value) for value in mass_weights],
            "weights_non_negative": bool(np.all(mass_weights >= 0.0)),
            "mass_weight_sum": float(mass_weights.sum()),
            "sum_constraint_weight": SUM_CONSTRAINT_WEIGHT,
            "density_weighted_rms": weighted_rms,
            "maximum_absolute_residual": maximum_absolute_residual,
        },
        "generator": {
            "path": "../../../scripts/fit_inner_crust_reference_template.py",
            "sha256": sha256_file(generator_path),
        },
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "scientific_semantics": {
            "calibration_member_only": "IOPB",
            "holdout_members_used_in_fit": [],
            "probabilistic_prior": False,
            "coverage_probability": None,
            "endpoint_tilt_is_deterministically_solved": True,
            "observer_specific_parameters": False,
        },
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    record = fit_template(args.manifest, args.output, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
