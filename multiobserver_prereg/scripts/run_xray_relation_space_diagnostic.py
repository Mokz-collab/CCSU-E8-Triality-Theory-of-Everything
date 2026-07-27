#!/usr/bin/env python3
"""Diagnose XRAY rejection in common finite-domain relation coordinates."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
import yaml

from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_local_charts import (
    CHART_SPECIFICATIONS,
    LocalChartError,
    generate_local_chart,
)
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_recovery import (
    centered_factorial_proposals,
    classify_screening_result,
    common_relation_projection,
)
from ccsu_multiobserver.ns_eos_relations import (
    RelationTranslationError,
    build_finite_domain_barotrope,
    translate_stellar_relations,
)


def _solver_arguments(
    settings: dict[str, object],
    target_masses: tuple[float, ...],
) -> dict[str, object]:
    return {
        "target_masses_msun": target_masses,
        "scan_points": int(settings["logarithmic_scan_points"]),
        "target_mass_tolerance_msun": float(
            settings["target_mass_tolerance_msun"]
        ),
        "maximum_bisection_iterations": int(
            settings["maximum_bisection_iterations"]
        ),
        "maximum_step_km": float(settings["maximum_step_km"]),
        "minimum_step_km": float(settings["minimum_step_km"]),
        "pressure_step_fraction": float(
            settings["pressure_step_fraction"]
        ),
        "turnover_mass_drop_tolerance_msun": float(
            settings["turnover_mass_drop_tolerance_msun"]
        ),
    }


def _coordinate_summary(
    projections: list[dict[str, list[float]]],
) -> dict[str, object] | None:
    if not projections:
        return None
    summary: dict[str, object] = {
        "count": len(projections),
        "density_nsat": projections[0]["density_nsat"],
    }
    for field in (
        "log10_pressure_mev_fm3",
        "pressure_over_energy",
        "sound_speed_squared",
    ):
        values = np.asarray([row[field] for row in projections], dtype=float)
        summary[field] = {
            "minimum": np.min(values, axis=0).tolist(),
            "median": np.median(values, axis=0).tolist(),
            "maximum": np.max(values, axis=0).tolist(),
        }
    return summary


def run_diagnostic(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    chart_contract_path = (
        ns_root / contract["local_chart_contract"]
    ).resolve()
    recovery_result_path = (
        ns_root / contract["recovery_result"]
    ).resolve()
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    recovery = json.loads(
        recovery_result_path.read_text(encoding="utf-8")
    )
    low = contract["low_density"]
    outer_path = (
        ns_root / low["outer_crust_reference_manifest"]
    ).resolve()
    template_path = (ns_root / low["inner_crust_template"]).resolve()
    outer = load_thermodynamic_table(outer_path)
    template = load_derivative_template(template_path)
    eft_tables = [
        load_thermodynamic_table((ns_root / relative).resolve())
        for relative in low["chiral_eft_anchors"]
    ]
    eft_by_label = {table.model_label: table for table in eft_tables}
    density_anchors = tuple(
        float(value) for value in contract["relation_density_anchors_nsat"]
    )

    reference_groups: dict[
        tuple[str, str], list[dict[str, list[float]]]
    ] = defaultdict(list)
    for case in recovery["cases"]:
        if case["local_status"] != "PASS":
            continue
        eft = eft_by_label[case["chiral_eft_model"]]
        chart = generate_local_chart(
            case["observer"],
            case["parameters"],
            eft.last,
            sample_count=int(chart_contract["sample_count"]),
        )
        group = (
            case["observer"],
            "ACCEPTED" if case["outcome"] == "ACCEPTED" else "REJECTED",
        )
        reference_groups[group].append(
            common_relation_projection(chart, density_anchors)
        )
    reference_summary = {
        observer: {
            status.lower(): _coordinate_summary(
                reference_groups[(observer, status)]
            )
            for status in ("ACCEPTED", "REJECTED")
        }
        for observer in contract["reference_observer_order"]
    }

    specification = CHART_SPECIFICATIONS["XRAY"]
    unit_levels = tuple(
        float(value) for value in contract["factorial_design"]["unit_levels"]
    )
    proposals = centered_factorial_proposals(
        specification,
        unit_levels=unit_levels,
    )
    screening_solver = contract["screening_solver"]
    exact_solver = contract["exact_revalidation_solver"]
    target_masses = tuple(
        float(value) for value in contract["mass_anchors_msun"]
    )
    cases: list[dict[str, object]] = []
    for eft in eft_tables:
        for proposal_index, parameters in enumerate(proposals):
            unit_coordinates = {
                name: (
                    parameters[name] - bounds[0]
                ) / (bounds[1] - bounds[0])
                for name, bounds in zip(
                    specification.parameter_names,
                    specification.parameter_bounds,
                    strict=True,
                )
            }
            case: dict[str, object] = {
                "case_id": (
                    f"XRAY__{eft.model_label}__F{proposal_index:04d}"
                ),
                "observer": "XRAY",
                "chart": specification.chart,
                "chiral_eft_model": eft.model_label,
                "proposal_index": proposal_index,
                "unit_coordinates": unit_coordinates,
                "parameters": parameters,
                "local_status": "NOT_RUN",
                "relation_projection": None,
                "screening": None,
                "exact_revalidation": None,
                "outcome": "NOT_RUN",
            }
            try:
                chart = generate_local_chart(
                    "XRAY",
                    parameters,
                    eft.last,
                    sample_count=int(chart_contract["sample_count"]),
                )
                finite_eos = build_finite_domain_barotrope(
                    outer,
                    eft,
                    template,
                    chart,
                    connector_points=int(low["connector_sample_count"]),
                    projection_tolerance=float(
                        low["rounded_outer_mu_projection_tolerance"]
                    ),
                )
                case["local_status"] = "PASS"
                case["relation_projection"] = common_relation_projection(
                    chart,
                    density_anchors,
                )
            except (LocalChartError, RelationTranslationError) as error:
                case["local_status"] = "REJECTED"
                case["local_rejection_type"] = type(error).__name__
                case["outcome"] = "LOCAL_PHYSICS_REJECTION"
                cases.append(case)
                continue
            try:
                screening = translate_stellar_relations(
                    finite_eos,
                    anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                    **_solver_arguments(screening_solver, ()),
                )
                turnover = bool(
                    screening["gates"]["domain_contains_mass_turnover"]
                )
                stable_mass = float(
                    screening["maximum_mass_lower_bound_msun"]
                )
                case["screening"] = {
                    "domain_contains_mass_turnover": turnover,
                    "stable_mass_limit_msun": stable_mass,
                    "endpoint_mass_msun": screening[
                        "sampled_mass_range_msun"
                    ]["endpoint_at_6_nsat"],
                }
                outcome = classify_screening_result(
                    local_status="PASS",
                    turnover=turnover,
                    stable_mass_limit_msun=stable_mass,
                )
                if outcome == "EXACT_REVALIDATION_REQUIRED":
                    exact = translate_stellar_relations(
                        finite_eos,
                        anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                        **_solver_arguments(exact_solver, target_masses),
                    )
                    case["exact_revalidation"] = exact
                    outcome = classify_screening_result(
                        local_status="PASS",
                        turnover=True,
                        stable_mass_limit_msun=stable_mass,
                        exact_gates_pass=bool(
                            exact["all_stellar_gates_pass"]
                        ),
                    )
                case["outcome"] = outcome
            except (ValueError, RuntimeError, FloatingPointError) as error:
                case["numerical_rejection_type"] = type(error).__name__
                case["outcome"] = "NUMERICAL_REJECTION"
            cases.append(case)

    outcome_counts = Counter(str(case["outcome"]) for case in cases)
    factor_effects: dict[str, dict[str, object]] = {}
    for parameter in specification.parameter_names:
        by_level: dict[str, object] = {}
        for level in unit_levels:
            selected = [
                case
                for case in cases
                if abs(
                    float(case["unit_coordinates"][parameter]) - level
                ) < 1.0e-12
            ]
            counts = Counter(str(case["outcome"]) for case in selected)
            masses = [
                float(case["screening"]["stable_mass_limit_msun"])
                for case in selected
                if case["screening"] is not None
            ]
            by_level[str(level)] = {
                "cases": len(selected),
                "accepted": counts.get("ACCEPTED", 0),
                "outcomes": dict(sorted(counts.items())),
                "median_stable_mass_limit_msun": (
                    float(np.median(masses)) if masses else None
                ),
            }
        factor_effects[parameter] = by_level

    accepted = [case for case in cases if case["outcome"] == "ACCEPTED"]
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-xray-diagnostic.v1",
        "diagnostic_id": contract["diagnostic_id"],
        "version": contract["version"],
        "status": "DEVELOPMENT_NONCONFIRMATORY",
        "confirmatory_authorization": False,
        "pilot_entry_authorized": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "source": {
            "path": contract["source"],
            "sha256": sha256_file(project_root / contract["source"]),
        },
        "recovery_result": {
            "path": recovery_result_path.name,
            "sha256": sha256_file(recovery_result_path),
        },
        "finite_domain_rule": contract["finite_domain_rule"],
        "factorial_design": contract["factorial_design"],
        "common_relation_reference": reference_summary,
        "cases": cases,
        "case_count": len(cases),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "accepted_count": len(accepted),
        "accepted_unique_proposal_count": len(
            {int(case["proposal_index"]) for case in accepted}
        ),
        "accepted_for_both_eft_members": sum(
            all(
                any(
                    case["proposal_index"] == proposal_index
                    and case["chiral_eft_model"] == eft.model_label
                    and case["outcome"] == "ACCEPTED"
                    for case in cases
                )
                for eft in eft_tables
            )
            for proposal_index in range(len(proposals))
        ),
        "factor_effects": factor_effects,
        "decision": (
            "XRAY_FINITE_DOMAIN_SUPPORT_FOUND_IN_SPARSE_INTERACTION_REGION"
            if accepted
            else "XRAY_ZERO_ACCEPTANCE_PERSISTS_ON_FACTORIAL_DESIGN"
        ),
        "causal_claim_limit": (
            "factorial_association_not_observational_or_physical_causation"
        ),
        "does_not_validate": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pyyaml": yaml.__version__,
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
    record = run_diagnostic(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
