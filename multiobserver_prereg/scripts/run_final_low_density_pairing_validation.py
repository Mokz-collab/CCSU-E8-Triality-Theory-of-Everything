#!/usr/bin/env python3
"""Validate every allowed outer-crust/χEFT endpoint pairing."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from pathlib import Path

import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_low_density import (
    build_reference_tilted_connector,
    load_thermodynamic_table,
    project_rounded_chemical_potential,
    sha256_file,
)


def _relative_residual(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def run_pairing_validation(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != 1:
        raise ValueError("pairing validation schema_version must equal 1")
    template_path = (
        root / contract["connector"]["template"]
    ).resolve()
    template = load_derivative_template(template_path)
    outer_manifests = [
        (root / path).resolve()
        for path in contract["outer_crust_manifests"]
    ]
    eft_manifests = [
        (root / path).resolve()
        for path in contract["chiral_eft_manifests"]
    ]
    outer_tables = [
        load_thermodynamic_table(path) for path in outer_manifests
    ]
    eft_tables = [
        load_thermodynamic_table(path) for path in eft_manifests
    ]
    sample_count = int(
        contract["connector"]["sampled_points_including_endpoints"]
    )
    projection_tolerance = float(
        contract["rounded_source_projection"][
            "maximum_original_relative_residual"
        ]
    )
    checks = contract["required_checks"]
    pairs: list[dict[str, object]] = []
    for outer in outer_tables:
        projected_lower, original_projection_residual = (
            project_rounded_chemical_potential(
                outer.last,
                maximum_original_relative_residual=projection_tolerance,
            )
        )
        for eft in eft_tables:
            connector = build_reference_tilted_connector(
                projected_lower,
                eft.first,
                template,
            )
            sampled = connector.sample(sample_count)
            identity_residuals = [
                _relative_residual(
                    row.mu_b_mev,
                    (
                        row.epsilon_mev_fm3 + row.p_mev_fm3
                    )
                    / row.n_b_fm3,
                )
                for row in sampled
            ]
            endpoint_residuals: list[float] = []
            for expected, actual in (
                (projected_lower, sampled[0]),
                (eft.first, sampled[-1]),
            ):
                endpoint_residuals.extend(
                    _relative_residual(
                        getattr(expected, field),
                        getattr(actual, field),
                    )
                    for field in (
                        "n_b_fm3",
                        "p_mev_fm3",
                        "epsilon_mev_fm3",
                        "mu_b_mev",
                    )
                )
            pressure_increasing = all(
                right.p_mev_fm3 > left.p_mev_fm3
                for left, right in zip(sampled, sampled[1:], strict=False)
            )
            energy_increasing = all(
                right.epsilon_mev_fm3 > left.epsilon_mev_fm3
                for left, right in zip(sampled, sampled[1:], strict=False)
            )
            mu_increasing = all(
                right.mu_b_mev > left.mu_b_mev
                for left, right in zip(sampled, sampled[1:], strict=False)
            )
            pair_checks = {
                "projection_within_tolerance": (
                    original_projection_residual <= projection_tolerance
                ),
                "endpoint_residual_within_tolerance": (
                    max(endpoint_residuals)
                    <= float(checks["maximum_endpoint_relative_residual"])
                ),
                "identity_residual_within_tolerance": (
                    max(identity_residuals)
                    <= float(
                        checks[
                            "maximum_sampled_identity_relative_residual"
                        ]
                    )
                ),
                "minimum_cs2_pass": (
                    min(row.cs2 for row in sampled)
                    >= float(checks["minimum_cs2"])
                ),
                "maximum_cs2_pass": (
                    max(row.cs2 for row in sampled)
                    <= float(checks["maximum_cs2"])
                ),
                "pressure_strictly_increasing": pressure_increasing,
                "energy_density_strictly_increasing": energy_increasing,
                "chemical_potential_strictly_increasing": mu_increasing,
            }
            pairs.append(
                {
                    "pair_id": f"{outer.model_label}__{eft.model_label}",
                    "outer_crust_model": outer.model_label,
                    "chiral_eft_model": eft.model_label,
                    "density_range_fm3": [
                        projected_lower.n_b_fm3,
                        eft.first.n_b_fm3,
                    ],
                    "outer_endpoint_projection": {
                        "original_mu_b_mev": outer.last.mu_b_mev,
                        "projected_mu_b_mev": projected_lower.mu_b_mev,
                        "absolute_correction_mev": abs(
                            projected_lower.mu_b_mev
                            - outer.last.mu_b_mev
                        ),
                        "original_relative_identity_residual": (
                            original_projection_residual
                        ),
                    },
                    "tilt": connector.tilt,
                    "sampled_points": sample_count,
                    "minimum_cs2": min(row.cs2 for row in sampled),
                    "maximum_cs2": max(row.cs2 for row in sampled),
                    "maximum_endpoint_relative_residual": max(
                        endpoint_residuals
                    ),
                    "maximum_identity_relative_residual": max(
                        identity_residuals
                    ),
                    "checks": pair_checks,
                    "all_checks_pass": all(pair_checks.values()),
                }
            )
    expected_pair_count = int(checks["expected_pair_count"])
    decision = (
        "ACCEPT_ALL_FINAL_LOW_DENSITY_PAIRINGS_FOR_STELLAR_IMPACT_TESTING"
        if len(pairs) == expected_pair_count
        and all(pair["all_checks_pass"] for pair in pairs)
        else "REJECT_FINAL_LOW_DENSITY_PAIRINGS"
    )
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.final-low-density-pairing-result.v1",
        "validation_id": contract["validation_id"],
        "status": "DEVELOPMENT_NOT_CONFIRMATORY",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "template": {
            "path": str(template_path.relative_to(root)),
            "sha256": sha256_file(template_path),
            "template_id": template.template_id,
        },
        "source_manifests": {
            str(path.relative_to(root)): sha256_file(path)
            for path in outer_manifests + eft_manifests
        },
        "pairs": pairs,
        "pair_count": len(pairs),
        "all_pairs_pass": all(pair["all_checks_pass"] for pair in pairs),
        "decision": decision,
        "decision_scope": contract["decision_scope"],
        "remaining_nonvalidated_items": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
    }
    record["canonical_record_sha256"] = validation_record_sha256(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-utc", required=True)
    args = parser.parse_args()
    record = run_pairing_validation(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
