#!/usr/bin/env python3
"""Run the deterministic nonconfirmatory finite-domain recovery search."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy
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
    classify_screening_result,
    deterministic_sobol_proposals,
    summarize_acceptance,
)
from ccsu_multiobserver.ns_eos_relations import (
    RelationTranslationError,
    build_finite_domain_barotrope,
    translate_stellar_relations,
)


def _solver_arguments(
    settings: dict[str, object],
    *,
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


def run_search(contract_path: Path, created_utc: str) -> dict[str, object]:
    contract_path = contract_path.resolve()
    ns_root = contract_path.parent
    project_root = ns_root.parent
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    chart_contract_path = (
        ns_root / contract["local_chart_contract"]
    ).resolve()
    chart_contract = yaml.safe_load(
        chart_contract_path.read_text(encoding="utf-8")
    )
    low = contract["low_density"]
    outer_path = (
        ns_root / low["outer_crust_reference_manifest"]
    ).resolve()
    template_path = (ns_root / low["inner_crust_template"]).resolve()
    outer = load_thermodynamic_table(outer_path)
    template = load_derivative_template(template_path)
    eft_paths = [
        (ns_root / relative).resolve()
        for relative in low["chiral_eft_anchors"]
    ]
    eft_tables = [load_thermodynamic_table(path) for path in eft_paths]
    search = contract["search_design"]
    sample_power = int(search["sobol_sample_power_per_chart"])
    seed = int(search["sobol_seed"])
    screening_solver = contract["screening_solver"]
    exact_solver = contract["exact_revalidation_solver"]
    target_masses = tuple(
        float(value) for value in contract["mass_anchors_msun"]
    )

    cases: list[dict[str, object]] = []
    proposal_sets: dict[str, tuple[dict[str, float], ...]] = {}
    for observer_index, observer in enumerate(
        contract["observer_order"]
    ):
        specification = CHART_SPECIFICATIONS[observer]
        proposals = deterministic_sobol_proposals(
            specification,
            sample_power=sample_power,
            seed=seed + observer_index,
        )
        proposal_sets[observer] = proposals
        for eft in eft_tables:
            for proposal_index, parameters in enumerate(proposals):
                case: dict[str, object] = {
                    "case_id": (
                        f"{observer}__{eft.model_label}__"
                        f"S{proposal_index:04d}"
                    ),
                    "observer": observer,
                    "chart": specification.chart,
                    "chiral_eft_model": eft.model_label,
                    "proposal_index": proposal_index,
                    "parameters": parameters,
                    "local_status": "NOT_RUN",
                    "screening": None,
                    "exact_revalidation": None,
                    "outcome": "NOT_RUN",
                }
                try:
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
                    case["local_status"] = "PASS"
                except (LocalChartError, RelationTranslationError) as error:
                    case["local_status"] = "REJECTED"
                    case["local_rejection_type"] = type(error).__name__
                    case["outcome"] = classify_screening_result(
                        local_status="REJECTED"
                    )
                    cases.append(case)
                    continue

                try:
                    screening = translate_stellar_relations(
                        finite_eos,
                        anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                        **_solver_arguments(
                            screening_solver,
                            target_masses=(),
                        ),
                    )
                    case["screening"] = {
                        "domain_contains_mass_turnover": screening["gates"][
                            "domain_contains_mass_turnover"
                        ],
                        "stable_mass_limit_msun": screening[
                            "maximum_mass_lower_bound_msun"
                        ],
                        "endpoint_mass_msun": screening[
                            "sampled_mass_range_msun"
                        ]["endpoint_at_6_nsat"],
                    }
                    outcome = classify_screening_result(
                        local_status="PASS",
                        turnover=bool(
                            screening["gates"][
                                "domain_contains_mass_turnover"
                            ]
                        ),
                        stable_mass_limit_msun=float(
                            screening["maximum_mass_lower_bound_msun"]
                        ),
                    )
                    if outcome == "EXACT_REVALIDATION_REQUIRED":
                        exact = translate_stellar_relations(
                            finite_eos,
                            anchor_pressure_mev_fm3=eft.last.p_mev_fm3,
                            **_solver_arguments(
                                exact_solver,
                                target_masses=target_masses,
                            ),
                        )
                        case["exact_revalidation"] = exact
                        outcome = classify_screening_result(
                            local_status="PASS",
                            turnover=True,
                            stable_mass_limit_msun=float(
                                screening[
                                    "maximum_mass_lower_bound_msun"
                                ]
                            ),
                            exact_gates_pass=bool(
                                exact["all_stellar_gates_pass"]
                            ),
                        )
                    case["outcome"] = outcome
                except (ValueError, RuntimeError, FloatingPointError) as error:
                    case["numerical_rejection_type"] = type(error).__name__
                    case["outcome"] = "NUMERICAL_REJECTION"
                cases.append(case)

    observers = tuple(str(value) for value in contract["observer_order"])
    summary = summarize_acceptance(cases, observers)
    accepted_count = sum(case["outcome"] == "ACCEPTED" for case in cases)
    record: dict[str, object] = {
        "schema": "ccsu.multiobserver.ns-eos-recovery-search.v1",
        "recovery_id": contract["recovery_id"],
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
        "chart_contract": {
            "path": chart_contract_path.name,
            "sha256": sha256_file(chart_contract_path),
        },
        "finite_domain_rule": contract["finite_domain_rule"],
        "search_design": search,
        "proposal_sets_identical_across_eft_members": True,
        "cases": cases,
        "case_count": len(cases),
        "accepted_count": accepted_count,
        "acceptance_summary": summary,
        "decision": (
            "RECOVERY_CANDIDATES_FOUND_AWAITING_INDEPENDENT_REVIEW"
            if accepted_count
            else "NO_RECOVERY_CANDIDATES_IN_DIAGNOSTIC_DESIGN"
        ),
        "does_not_validate": contract["does_not_validate"],
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
    record = run_search(args.contract, args.created_utc)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
