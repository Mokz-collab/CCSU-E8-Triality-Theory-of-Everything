#!/usr/bin/env python3
"""Translate registered local EOS charts into bounded public relations."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy
import scipy
import yaml

from ccsu_multiobserver.ns_eos_decisions import (
    load_and_validate_decisions,
)
from ccsu_multiobserver.ns_eos_domain import load_and_validate
from ccsu_multiobserver.ns_eos_inner_crust_validation import (
    load_derivative_template,
    validation_record_sha256,
)
from ccsu_multiobserver.ns_eos_local_charts import generate_local_chart
from ccsu_multiobserver.ns_eos_low_density import (
    load_thermodynamic_table,
    sha256_file,
)
from ccsu_multiobserver.ns_eos_relations import (
    build_finite_domain_barotrope,
    convergence_comparison,
    public_relation_projection,
    translate_stellar_relations,
)


def run_validation(
    contract_path: Path,
    created_utc: str,
) -> dict[str, object]:
    contract_path = contract_path.resolve()
    root = contract_path.parent
    project_root = root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    decisions_path = (root / contract["decision_lock"]).resolve()
    domain_path = (root / contract["domain_lock"]).resolve()
    chart_contract_path = (
        root / contract["local_chart_contract"]
    ).resolve()
    chart_result_path = (
        root / contract["local_chart_result"]
    ).resolve()
    environment_path = (
        root / contract["environment_lock"]
    ).resolve()
    decisions = load_and_validate_decisions(decisions_path)
    domain = load_and_validate(domain_path)
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    chart_result = json.loads(
        chart_result_path.read_text(encoding="utf-8")
    )
    if not chart_result["all_cases_pass"]:
        raise ValueError("local-chart prerequisite did not pass")

    low = contract["low_density"]
    outer_path = (
        root / low["outer_crust_reference"]["manifest"]
    ).resolve()
    outer = load_thermodynamic_table(outer_path)
    eft_tables = [
        load_thermodynamic_table((root / relative).resolve())
        for relative in low["chiral_eft_anchors"]
    ]
    template_path = (
        root / low["inner_crust_template"]
    ).resolve()
    template = load_derivative_template(template_path)
    solver = contract["stellar_solver"]
    target_masses = tuple(
        float(value) for value in contract["atlas_anchors"]["mass_msun"]
    )
    density_anchors = tuple(
        float(value)
        for value in contract["atlas_anchors"]["density_nsat"]
    )

    cases: list[dict[str, object]] = []
    bounded_eos_by_case: dict[str, object] = {}
    for eft in eft_tables:
        for observer in ("GW", "XRAY", "RADIO", "NUCLEAR"):
            parameters = chart_contract["charts"][observer][
                "registered_exemplar"
            ]
            chart = generate_local_chart(
                observer,
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
            stellar = translate_stellar_relations(
                finite_eos,
                anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                target_masses_msun=target_masses,
                scan_points=int(solver["logarithmic_scan_points"]),
                target_mass_tolerance_msun=float(
                    solver["target_mass_tolerance_msun"]
                ),
                maximum_bisection_iterations=int(
                    solver["maximum_bisection_iterations"]
                ),
                maximum_step_km=float(solver["maximum_step_km"]),
                minimum_step_km=float(solver["minimum_step_km"]),
                pressure_step_fraction=float(
                    solver["pressure_step_fraction"]
                ),
                turnover_mass_drop_tolerance_msun=float(
                    solver["turnover_mass_drop_tolerance_msun"]
                ),
            )
            public = public_relation_projection(
                observer,
                chart,
                stellar,
                eft,
                density_anchors,
            )
            case_id = f"{observer}__{eft.model_label}"
            bounded_eos_by_case[case_id] = finite_eos
            cases.append(
                {
                    "case_id": case_id,
                    "observer": observer,
                    "chart": chart.chart,
                    "outer_crust_model": outer.model_label,
                    "chiral_eft_model": eft.model_label,
                    "parameters": parameters,
                    "finite_domain": {
                        "maximum_density_nsat": (
                            finite_eos.maximum_density_nsat
                        ),
                        "maximum_pressure_mev_fm3": (
                            finite_eos.maximum_pressure_mev_fm3
                        ),
                        "extension_used": False,
                    },
                    "stellar_translation": stellar,
                    "public_projection": public,
                }
            )

    convergence_contract = contract["convergence_check"]
    convergence_case_id = convergence_contract["case_id"]
    convergence_case = next(
        case for case in cases if case["case_id"] == convergence_case_id
    )
    target_mass = float(convergence_contract["target_mass_msun"])
    target_model = next(
        row
        for row in convergence_case["stellar_translation"][
            "mass_radius_tidal_relation"
        ]
        if row["target_mass_msun"] == target_mass
    )
    convergence = convergence_comparison(
        bounded_eos_by_case[convergence_case_id],
        target_model["central_pressure_mev_fm3"],
        coarse_step_km=float(
            convergence_contract["coarse_maximum_step_km"]
        ),
        fine_step_km=float(
            convergence_contract["fine_maximum_step_km"]
        ),
        minimum_step_km=float(solver["minimum_step_km"]),
        pressure_step_fraction=float(
            solver["pressure_step_fraction"]
        ),
    )
    convergence_limits = convergence_contract[
        "maximum_relative_differences"
    ]
    convergence["checks"] = {
        field: value <= float(convergence_limits[field])
        for field, value in convergence["relative_differences"].items()
    }
    convergence["all_checks_pass"] = all(
        convergence["checks"].values()
    )

    translations_completed = len(cases) == 8
    full_gate_pass_count = sum(
        case["stellar_translation"]["all_stellar_gates_pass"]
        for case in cases
    )
    domain_truncated_count = sum(
        not case["stellar_translation"]["gates"][
            "domain_contains_mass_turnover"
        ]
        for case in cases
    )
    maximum_mass_threshold_pass_count = sum(
        case["stellar_translation"]["gates"][
            "maximum_mass_at_least_2_0_msun"
        ]
        for case in cases
    )
    all_mass_anchors_count = sum(
        case["stellar_translation"]["gates"][
            "all_registered_mass_anchors_translated"
        ]
        for case in cases
    )
    all_public_metadata = all(
        set(
            case["public_projection"]["provenance"]
        )
        == set(contract["public_projection"]["required_provenance"])
        and not case["public_projection"]["local_parameters_included"]
        for case in cases
    )
    if (
        translations_completed
        and full_gate_pass_count == len(cases)
        and convergence["all_checks_pass"]
        and all_public_metadata
    ):
        decision = "LOCAL_TO_PUBLIC_RELATION_GATES_PASSED"
    elif (
        translations_completed
        and convergence["all_checks_pass"]
        and all_public_metadata
    ):
        decision = (
            "TRANSLATION_IMPLEMENTED_REGISTERED_EXEMPLARS_FAILED_"
            "FINITE_DOMAIN_STELLAR_GATES"
        )
    else:
        decision = "LOCAL_TO_PUBLIC_RELATION_IMPLEMENTATION_FAILED"

    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-relation-translation.v1",
        "translation_id": contract["translation_contract_id"],
        "status": "DEVELOPMENT_NOT_CONFIRMATORY",
        "confirmatory_authorization": False,
        "created_utc": created_utc,
        "contract": {
            "path": contract_path.name,
            "sha256": sha256_file(contract_path),
        },
        "prerequisites": {
            "decision_lock": {
                "path": decisions_path.name,
                "sha256": sha256_file(decisions_path),
                "resolved_version": decisions["version"],
            },
            "domain_lock": {
                "path": domain_path.name,
                "sha256": sha256_file(domain_path),
                "resolved_version": domain["version"],
            },
            "local_chart_contract": {
                "path": chart_contract_path.name,
                "sha256": sha256_file(chart_contract_path),
            },
            "local_chart_result": {
                "path": chart_result_path.name,
                "sha256": sha256_file(chart_result_path),
            },
            "environment_lock": {
                "path": environment_path.name,
                "sha256": sha256_file(environment_path),
            },
        },
        "source": {
            "path": contract["source"],
            "sha256": sha256_file(project_root / contract["source"]),
        },
        "scientific_inputs": {
            "outer_crust_manifest_sha256": sha256_file(outer_path),
            "inner_crust_template_sha256": sha256_file(template_path),
            "chiral_eft_table_sha256": {
                table.model_label: table.sha256 for table in eft_tables
            },
        },
        "finite_domain_rule": contract["finite_domain_rule"],
        "cases": cases,
        "case_count": len(cases),
        "translations_completed": translations_completed,
        "full_stellar_gate_pass_count": full_gate_pass_count,
        "domain_truncated_before_turnover_count": (
            domain_truncated_count
        ),
        "maximum_mass_threshold_pass_count": (
            maximum_mass_threshold_pass_count
        ),
        "all_mass_anchors_translated_count": all_mass_anchors_count,
        "all_public_provenance_complete": all_public_metadata,
        "convergence_check": convergence,
        "decision": decision,
        "pilot_entry_authorized": False,
        "remaining_nonvalidated_items": contract["does_not_validate"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "numpy": numpy.__version__,
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
    record = run_validation(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
