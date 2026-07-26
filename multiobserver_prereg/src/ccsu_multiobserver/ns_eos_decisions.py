from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from .ns_eos_domain import load_and_validate


class DecisionLockError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionLockError(message)


def load_and_validate_decisions(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        decisions = yaml.safe_load(handle)

    _require(decisions.get("schema_version") == 1, "schema_version must equal 1")
    _require(decisions.get("decision_lock_id") == "CCSU-MO-NS-EOS-001-DECISIONS", "unexpected decision lock id")
    _require(decisions.get("status") == "DRAFT_LOCKED_FOR_IMPLEMENTATION", "decision lock must remain draft")
    _require(
        decisions.get("confirmatory_authorization") is False,
        "development decision lock cannot authorize confirmation",
    )

    base_path = resolved.parent / decisions["base_domain_spec"]
    base = load_and_validate(base_path)
    _require(base["status"] == "DRAFT_NOT_FROZEN", "base domain must be the draft v0.1 lock")

    low = decisions["low_density_matching"]
    _require(low["status"] == "LOCKED", "low-density decision is not locked")
    _require(
        low["outer_crust"]["density_nsat"][1]
        == low["inner_crust"]["density_nsat"][0],
        "outer/inner crust interval gap",
    )
    _require(
        low["inner_crust"]["density_nsat"][1]
        == low["nuclear_band"]["density_nsat"][0],
        "inner-crust/nuclear interval gap",
    )
    _require(low["nuclear_band"]["density_nsat"][1] == low["local_chart_start_nsat"], "nuclear/local interval gap")
    _require(
        low["outer_crust"]["semantic_limit"]
        == "BPS_label_ends_at_neutron_drip",
        "BPS label must end at neutron drip",
    )
    _require(
        set(low["outer_crust"]["model_labels"])
        == {"DD-ME2", "DD-PC1", "DD-PCX", "ELMA"},
        "outer-crust sensitivity ensemble changed",
    )
    _require(
        low["outer_crust"]["same_model_for_all_arms_within_trajectory"] is True,
        "outer-crust nuisance must remain paired across arms",
    )
    _require(
        low["outer_crust"]["observer_conditioned_selection_forbidden"] is True,
        "outer-crust model cannot be selected by observer",
    )
    _require(
        low["inner_crust"]["observer_specific_parameters_forbidden"] is True,
        "inner crust cannot vary by observer",
    )
    if (
        low["inner_crust"]["prescription"]
        == "shared_reference_tilted_chemical_potential_connector"
    ):
        inner = low["inner_crust"]
        components = inner["derivative_template_components"]
        _require(
            components["exponents"] == [-40.0, 0.0, 40.0],
            "inner-crust derivative-template exponents changed",
        )
        _require(
            abs(sum(components["mass_weights"]) - 1.0) <= 1.0e-12
            and all(weight >= 0 for weight in components["mass_weights"]),
            "inner-crust derivative-template weights are invalid",
        )
        _require(
            inner["template_calibration_model"] == "IOPB"
            and inner["primary_holdout_model"] == "G3",
            "inner-crust calibration/holdout split changed",
        )
        _require(
            inner["template_probabilistic_prior"] is False
            and inner["sampled_free_parameters"] == 0
            and inner["endpoint_tilt_deterministically_solved"] is True,
            "inner-crust template semantics changed",
        )
    nuclear_band = low["nuclear_band"]
    _require(
        set(nuclear_band["model_labels"])
        == {"MUSES-N3LO-414", "MUSES-N3LO-450"},
        "χEFT reference-member ensemble changed",
    )
    _require(
        nuclear_band["same_model_for_all_arms_within_trajectory"] is True,
        "χEFT reference member must remain paired across arms",
    )
    _require(
        nuclear_band["observer_conditioned_selection_forbidden"] is True,
        "χEFT reference member cannot be selected by observer",
    )
    _require(
        nuclear_band["pointwise_envelope_sampling_forbidden"] is True,
        "pointwise χEFT envelope sampling must remain forbidden",
    )
    _require(
        nuclear_band["probabilistic_coverage"] is None
        and nuclear_band["formal_chiral_truncation_error"] is False,
        "reference-member envelope cannot claim formal χEFT coverage",
    )
    _require(low["no_observer_specific_crust"] is True, "observer-specific crust must be forbidden")
    _require(
        set(low["continuity_required_at_smooth_matches"])
        == {"pressure", "energy_density", "baryon_chemical_potential"},
        "matching continuity lock is incomplete",
    )
    _require(
        low["registered_density_discontinuities_preserved"] is True,
        "registered density discontinuities must be preserved",
    )

    charts = decisions["local_chart_proposals"]
    _require(charts["status"] == "LOCKED", "local charts are not locked")
    for observer in ("GW", "XRAY", "RADIO", "NUCLEAR"):
        _require(charts[observer]["chart"] == base["observers"][observer]["local_chart"], f"{observer} chart changed from domain lock")
    _require(charts["NUCLEAR"]["cs2_range"] == [0.01, 1.0], "NUCLEAR causality proposal range is invalid")
    _require("causal_sound_speed" in charts["common_acceptance_filters"], "causal filter is missing")

    likelihoods = decisions["synthetic_likelihoods"]
    _require(likelihoods["status"] == "LOCKED", "likelihood decision is not locked")
    _require(likelihoods["signal_levels"] == ["LOW", "MEDIUM", "HIGH"], "signal level order changed")
    _require(float(likelihoods["balance_rule"].split("_")[4].replace("pct", "")) == 60, "information balance rule changed")
    for observer in ("GW", "XRAY", "RADIO", "NUCLEAR"):
        values = [
            value
            for key, value in likelihoods[observer].items()
            if key.startswith("sigma_") or key == "network_snr"
        ]
        _require(values and all(len(value) == 3 for value in values), f"{observer} lacks three signal levels")

    transition = decisions["phase_transition_proxy"]
    _require(transition["status"] == "LOCKED", "phase-transition proxy is not locked")
    _require(transition["not_claimed_as_unique_first_order_signature"] is True, "proxy overclaims first-order identification")
    _require(0 < float(transition["softening"]["cs2_upper"]) < float(transition["restiffening"]["cs2_lower"]) <= 1, "invalid sound-speed proxy")
    _require(float(transition["softening"]["minimum_width_nsat"]) > 0, "softening width must be positive")

    comparators = decisions["comparator_roles"]
    _require(comparators["status"] == "LOCKED", "comparator roles are not locked")
    _require(comparators["P1_primary"] == "HYBRID_vs_IND", "P1 primary comparator changed")
    _require(comparators["P3_primary"] == "HYBRID_vs_NAIVE_POOL", "P3 primary comparator changed")
    _require(comparators["raw_posterior_pooling_forbidden"] is True, "raw posterior pooling must be forbidden")

    budget = decisions["trajectory_budget_rule"]
    _require(budget["status"] == "LOCKED", "budget decision is not locked")
    confirm = budget["confirmatory_budget"]
    _require(float(confirm["minimum_power"]) >= 0.90, "minimum power is too low")
    _require(float(confirm["maximum_monte_carlo_se_directional_fraction"]) <= 0.01, "MCSE tolerance is too large")
    _require(int(confirm["minimum_trajectories_per_cell"]) >= 250, "minimum cell budget is too low")
    _require(int(confirm["maximum_trajectories_per_cell"]) <= 1000, "maximum cell budget is too high")
    _require(budget["budget_chosen_before_confirmatory_seed_schedule"] is True, "budget must precede seeds")

    expected = set(base["open_decisions"])
    _require(set(decisions["resolved_open_decisions"]) == expected, "not all v0.1 decisions are resolved")
    return decisions


def decision_summary(decisions: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_lock_id": decisions["decision_lock_id"],
        "version": decisions["version"],
        "status": decisions["status"],
        "resolved": decisions["resolved_open_decisions"],
        "remaining_freeze_blockers": decisions["remaining_freeze_blockers"],
        "confirmatory_authorization": decisions["confirmatory_authorization"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an NS-EOS development decision lock"
    )
    parser.add_argument("decisions", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(decision_summary(load_and_validate_decisions(args.decisions)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
