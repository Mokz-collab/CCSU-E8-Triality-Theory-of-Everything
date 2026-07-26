from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_OBSERVERS = {"GW", "XRAY", "RADIO", "NUCLEAR"}
REQUIRED_RELATIONS = {
    "pressure_energy_density",
    "mass_radius",
    "tidal_deformability_mass",
    "maximum_mass",
}
REQUIRED_PREDICTIONS = {"P1", "P2", "P3", "P4", "P5"}
REQUIRED_TRUTH_CLASSES = {
    "smooth_hadronic",
    "rapid_softening_then_restiffening",
    "stiff_high_density",
}
FORBIDDEN_ATLAS_OPERATIONS = {
    "average_local_parameter_vectors",
    "pool_posterior_samples_before_prior_harmonization",
    "replace_local_chart_with_atlas_chart",
    "treat_HYBRID_consensus_as_ground_truth",
}


class DomainSpecificationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DomainSpecificationError(message)


def load_and_validate(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    _require(spec.get("schema_version") == 1, "schema_version must equal 1")
    _require(spec.get("protocol_id") == "CCSU-MO-NS-EOS-001", "unexpected protocol_id")
    _require(spec.get("status") == "DRAFT_NOT_FROZEN", "v0.1 must remain draft")
    _require(spec.get("confirmatory") is False, "v0.1 cannot be confirmatory")

    domain = spec.get("domain", {})
    _require(set(domain.get("observers", [])) == REQUIRED_OBSERVERS, "observer set is incomplete")
    _require(set(domain.get("observables", [])) == REQUIRED_RELATIONS, "public relation set is incomplete")
    scale = domain.get("scale", {})
    mass = scale.get("gravitational_mass_msun", [])
    density = scale.get("baryon_density_nsat", [])
    _require(len(mass) == 2 and mass[0] < mass[1], "invalid mass range")
    _require(len(density) == 2 and density[0] < density[1], "invalid density range")

    observers = spec.get("observers", {})
    _require(set(observers) == REQUIRED_OBSERVERS, "observer definitions do not match domain tuple")
    charts = set()
    for code in REQUIRED_OBSERVERS:
        observer = observers[code]
        _require(observer.get("local_chart"), f"{code} has no local chart")
        _require(observer.get("native_evidence"), f"{code} has no native evidence")
        _require(observer.get("public_projection"), f"{code} has no public projection")
        _require(
            set(observer["public_projection"]).issubset(REQUIRED_RELATIONS),
            f"{code} publishes an undeclared relation",
        )
        charts.add(observer["local_chart"])
    _require(len(charts) == len(REQUIRED_OBSERVERS), "local charts must remain distinct in v0.1")

    atlas = spec.get("atlas", {})
    _require(atlas.get("aggregation_unit") == "relation_anchor_not_local_parameter", "Atlas aggregation unit is invalid")
    _require(atlas.get("preserve_local_models") is True, "Atlas must preserve local models")
    _require(
        set(atlas.get("forbidden_operations", [])) == FORBIDDEN_ATLAS_OPERATIONS,
        "Atlas forbidden-operation lock is incomplete",
    )
    metadata = set(atlas.get("required_metadata", []))
    _require({"observer", "local_chart", "prior_identifier", "translation_version"}.issubset(metadata), "Atlas provenance metadata is incomplete")

    truths = spec.get("synthetic_truths", {})
    _require(set(truths.get("classes", [])) == REQUIRED_TRUTH_CLASSES, "synthetic truth classes are incomplete")
    filters = truths.get("physical_filters", {})
    _require(filters.get("thermodynamic_stability") == "dp_depsilon_gt_0", "stability filter is missing")
    _require(filters.get("causality") == "cs2_in_0_1", "causality filter is missing")
    _require(float(filters.get("maximum_mass_msun_lower", 0)) >= 2.0, "maximum-mass filter is too weak")
    _require(truths.get("truth_visibility") == "hidden_from_inference_arms", "truth must be hidden")

    predictions = spec.get("predictions", {})
    _require(set(predictions) == REQUIRED_PREDICTIONS, "P1-P5 definitions are incomplete")
    for name in ("P1", "P2", "P3", "P4"):
        _require(
            predictions[name].get("threshold_status") == "PROPOSED_REQUIRES_PILOT",
            f"{name} thresholds must remain proposed before the pilot",
        )
    p3_safety = predictions["P3"].get("safety_gate", {})
    _require(
        p3_safety.get("rule") == "one_sided_95pct_upper_bound_le_0_05",
        "P3 FPR rule does not match canonical v1.1",
    )
    _require(p3_safety.get("enters_Holm") is False, "P3 FPR cannot enter Holm")
    p5 = predictions["P5"]
    _require(
        p5.get("primary_oracle") == "exact_rate_minus_2_log_abs_1_minus_kappa_lambda2",
        "P5 exact spectral oracle is not frozen",
    )
    _require(p5.get("exact_tau_match_fraction") == 1.0, "P5 exact-match gate must equal 1")
    _require(p5.get("uncensored_fraction") == 1.0, "P5 uncensored gate must equal 1")

    analysis = spec.get("analysis", {})
    _require(analysis.get("primary_family") == ["P1", "P2", "P3", "P4"], "primary family must be P1-P4")
    _require(analysis.get("one_efficacy_p_per_prediction") is True, "one efficacy p-value per prediction is required")
    _require(analysis.get("P3_FPR_separate_safety_gate") is True, "P3 safety separation is required")
    _require(
        analysis.get("P5_failure_status") == "CONTROL_INVALID_INTERPRETATION_SUSPENDED",
        "P5 failure status is invalid",
    )
    _require(analysis.get("no_global_ccsu_score") is True, "global CCSU score is forbidden")
    return spec


def summary(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_id": spec["protocol_id"],
        "version": spec["version"],
        "status": spec["status"],
        "niche": spec["domain"]["niche"],
        "observers": spec["domain"]["observers"],
        "public_relations": spec["domain"]["observables"],
        "truth_classes": spec["synthetic_truths"]["classes"],
        "predictions": list(spec["predictions"]),
        "open_decisions": spec["open_decisions"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate CCSU-MO-NS-EOS-001 domain lock")
    parser.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(summary(load_and_validate(args.spec)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
