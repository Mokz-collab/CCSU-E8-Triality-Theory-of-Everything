#!/usr/bin/env python3
"""Generate the pinned CCSU χEFT beta-equilibrium reference members.

This is a development-data generator, not a confirmatory sampler.  It runs the
MUSES Chiral EFT EoS v1.0.1 executable for the n3lo-414 and n3lo-450 parameter
sets, applies the module's documented quadratic-asymmetry and free-energy
ansatz, adds a zero-temperature electron/muon gas, and solves charge-neutral
beta equilibrium.

The two resulting EOS members define a coherent interaction envelope.  The
envelope is not assigned probabilistic coverage and is not a substitute for a
formal order-by-order χEFT truncation-error analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import brentq


MUSES_COMMIT = "6cf7fea41d2a2bac5f93e567d71279631168088b"
MUSES_TAG_OBJECT = "36e5e4ecc2d3572e48470deab820519b5e248b13"
MUSES_VERSION = "v1.0.1"
YAML_CPP_COMMIT = "f7320141120f720aecc4c32be25586e7da9eb978"
YAML_CPP_VERSION = "0.8.0"
MUSES_SOURCE_HASHES = {
    "LICENSE": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
    "README.md": "cf4bfb8be8393ff49c7f52543ee2d12dceb851f6351d913c264cc7a9e5787323",
    "input/config.yaml": "e2cd0281ad295c143ca9f76f3e336b143b334ce0c95a091b17bb98c19671da8f",
    "src/cheft-potential/fitted-parameters.yaml": (
        "12893b31cf204cb4f6f6f6939717b9a24ef50bc9ea43081038bc28ae72656d1b"
    ),
}
INTERACTIONS = ("n3lo-414", "n3lo-450")
RAW_COLUMNS = (
    "nucleon_density",
    "isospin_asymmetry",
    "temperature",
    "charge_fraction",
    "proton_density",
    "neutron_density",
    "proton_fermi_momentum",
    "neutron_fermi_momentum",
    "proton_mu0",
    "neutron_mu0",
    "proton_effective_mass",
    "neutron_effective_mass",
    "proton_energy_shift",
    "neutron_energy_shift",
    "f_0",
    "f_1",
    "f_2",
    "free_energy",
)
CANONICAL_COLUMNS = (
    "n_b_fm3",
    "p_mev_fm3",
    "epsilon_mev_fm3",
    "mu_b_mev",
    "cs2",
)

DENSITY_START_FM3 = 0.040
DENSITY_END_FM3 = 0.200
DENSITY_STEP_FM3 = 0.004
ANCHOR_LOWER_FM3 = 0.080
ANCHOR_UPPER_FM3 = 0.176
ASYMMETRY_STEP = 1.0

HBARC_MEV_FM = 197.327
PROTON_MASS_MEV = 938.272
NEUTRON_MASS_MEV = 939.5653
ELECTRON_MASS_MEV = 0.51099895000
MUON_MASS_MEV = 105.6583755


class GenerationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GenerationError(message)


def verify_upstream(source_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    result = subprocess.run(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    require(commit == MUSES_COMMIT, f"MUSES source commit is {commit}, not {MUSES_COMMIT}")
    require_tracked_files_unchanged(source_dir, "MUSES")
    for relative_path, expected_hash in MUSES_SOURCE_HASHES.items():
        path = source_dir / relative_path
        require(path.is_file(), f"missing pinned MUSES source file: {relative_path}")
        require(
            sha256_file(path) == expected_hash,
            f"pinned MUSES source hash mismatch: {relative_path}",
        )
    return {
        "repository": "https://gitlab.com/nsf-muses/chiral-eft-eos/chiral_eft_eos",
        "version": MUSES_VERSION,
        "tag_object": MUSES_TAG_OBJECT,
        "commit": MUSES_COMMIT,
        "source_hashes": MUSES_SOURCE_HASHES,
    }


def require_tracked_files_unchanged(repository: Path, label: str) -> None:
    for arguments in (
        ["git", "-C", str(repository), "diff", "--quiet", "HEAD", "--"],
        ["git", "-C", str(repository), "diff", "--cached", "--quiet"],
    ):
        result = subprocess.run(arguments, check=False)
        require(
            result.returncode == 0,
            f"{label} repository has modified tracked files",
        )


def verify_yaml_cpp(source_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    result = subprocess.run(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    require(
        commit == YAML_CPP_COMMIT,
        f"yaml-cpp source commit is {commit}, not {YAML_CPP_COMMIT}",
    )
    require_tracked_files_unchanged(source_dir, "yaml-cpp")
    return {
        "repository": "https://github.com/jbeder/yaml-cpp",
        "version": YAML_CPP_VERSION,
        "commit": YAML_CPP_COMMIT,
    }


def tracked_cpp_sources(repository: Path, pattern: str) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files", pattern],
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [
        (repository / relative_path).resolve()
        for relative_path in result.stdout.splitlines()
        if relative_path
    ]
    require(bool(paths), f"no tracked C++ sources match {pattern}")
    return paths


def build_muses_binary(
    *,
    muses_source_dir: Path,
    yaml_cpp_source_dir: Path,
    run_root: Path,
) -> dict[str, Any]:
    compiler = shutil.which("g++")
    require(compiler is not None, "g++ is required to build the pinned MUSES source")
    build_dir = run_root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    binary = build_dir / "chiraleft"
    muses_sources = tracked_cpp_sources(muses_source_dir, "src/*.cpp")
    yaml_cpp_sources = tracked_cpp_sources(yaml_cpp_source_dir, "src/*.cpp")
    command = [
        compiler,
        "-std=gnu++2a",
        "-O2",
        "-fopenmp",
        f"-I{muses_source_dir / 'src'}",
        f"-I{yaml_cpp_source_dir / 'include'}",
        *(str(path) for path in muses_sources),
        *(str(path) for path in yaml_cpp_sources),
        f"-L{muses_source_dir / 'lib'}",
        "-lcheft-potential",
        "-o",
        str(binary),
    ]
    build_log = build_dir / "build.log"
    started = datetime.now(timezone.utc)
    with build_log.open("wb") as log:
        subprocess.run(
            command,
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    finished = datetime.now(timezone.utc)
    compiler_version = subprocess.run(
        [compiler, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    return {
        "binary_path": str(binary),
        "binary_sha256": sha256_file(binary),
        "build_log_path": str(build_log),
        "build_log_sha256": sha256_file(build_log),
        "compiler": compiler,
        "compiler_version": compiler_version,
        "command": command,
        "muses_tracked_cpp_sources": [
            str(path.relative_to(muses_source_dir)) for path in muses_sources
        ],
        "yaml_cpp_tracked_cpp_sources": [
            str(path.relative_to(yaml_cpp_source_dir))
            for path in yaml_cpp_sources
        ],
        "started_utc": started.isoformat().replace("+00:00", "Z"),
        "finished_utc": finished.isoformat().replace("+00:00", "Z"),
    }


def normalized_parameters(source_dir: Path, interaction: str) -> tuple[dict[str, Any], list[str]]:
    fitted_path = source_dir / "src" / "cheft-potential" / "fitted-parameters.yaml"
    fitted = yaml.safe_load(fitted_path.read_text(encoding="utf-8"))
    require(interaction in fitted, f"missing fitted interaction {interaction}")
    parameters = dict(fitted[interaction])
    normalizations: list[str] = []
    three_body = dict(parameters["three_nucleon_forces"])
    if interaction == "n3lo-414":
        # v1.0.1 ships cD/cE, while its parser accepts c_D/c_E.  Preserve the
        # numerical source values while normalizing only the two key spellings.
        require("cD" in three_body and "cE" in three_body, "known v1.0.1 key issue absent")
        require("c_D" not in three_body and "c_E" not in three_body, "ambiguous 3NF keys")
        three_body["c_D"] = three_body.pop("cD")
        three_body["c_E"] = three_body.pop("cE")
        normalizations.append("three_nucleon_forces.cD->c_D")
        normalizations.append("three_nucleon_forces.cE->c_E")
    parameters["three_nucleon_forces"] = three_body
    return parameters, normalizations


def make_config(source_dir: Path, interaction: str) -> tuple[dict[str, Any], list[str]]:
    base = yaml.safe_load((source_dir / "input" / "config.yaml").read_text(encoding="utf-8"))
    parameters, normalizations = normalized_parameters(source_dir, interaction)
    base["run_name"] = f"ccsu-ns-eos-{interaction}-anchor-v0.4"
    base["chiraleft_parameters"] = parameters
    base["calculation_options"].update(
        {
            "n_threads": min(8, os.cpu_count() or 1),
            "use_multithreading": True,
            "use_quadratic_asymmetry_expansion": True,
            "use_free_energy_ansatz_fit": True,
        }
    )
    base["output_options"].update(
        {
            "output_format": "csv",
            "output_precision": 12,
            "include_output_stable": False,
            "include_output_lepton": False,
            "include_output_flavor": False,
            "include_output_self_energy": False,
            "include_output_saturation_properties": False,
            "verbose": False,
        }
    )
    base["eos_grid"] = {
        "density_start": DENSITY_START_FM3,
        "density_end": DENSITY_END_FM3,
        "density_step": DENSITY_STEP_FM3,
        "isospin_asymmetry_start": 0.0,
        "isospin_asymmetry_end": 1.0,
        "isospin_asymmetry_step": ASYMMETRY_STEP,
        "temperature_start": 0.0,
        "temperature_end": 0.0,
        "temperature_step": 0.0,
    }
    return base, normalizations


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def run_muses_member(
    *,
    source_dir: Path,
    binary: Path,
    run_root: Path,
    interaction: str,
) -> dict[str, Any]:
    config, normalizations = make_config(source_dir, interaction)
    member_root = run_root / interaction.replace("-", "_")
    input_dir = member_root / "input"
    output_dir = member_root / "output"
    executable_dir = member_root / "src"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    executable_dir.mkdir(parents=True, exist_ok=True)
    config_path = input_dir / "validated_config.yaml"
    write_yaml(config_path, config)
    executable = executable_dir / "chiraleft"
    if executable.exists() or executable.is_symlink():
        executable.unlink()
    executable.symlink_to(binary.resolve())
    log_path = member_root / "muses_run.log"
    started = datetime.now(timezone.utc)
    with log_path.open("wb") as log:
        subprocess.run(
            [str(executable)],
            cwd=executable_dir,
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    finished = datetime.now(timezone.utc)
    raw_path = output_dir / "raw_output.csv"
    require(raw_path.is_file(), f"MUSES did not create {raw_path}")
    return {
        "interaction": interaction,
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "raw_path": str(raw_path),
        "raw_sha256": sha256_file(raw_path),
        "log_path": str(log_path),
        "normalizations": normalizations,
        "started_utc": started.isoformat().replace("+00:00", "Z"),
        "finished_utc": finished.isoformat().replace("+00:00", "Z"),
    }


def read_raw(path: Path) -> pd.DataFrame:
    # The v1.0.1 executable calls writeResultstoFile(..., false); the OpenAPI
    # schema, rather than a CSV header row, defines this exact column order.
    frame = pd.read_csv(path, names=RAW_COLUMNS, header=None)
    require(tuple(frame.columns) == RAW_COLUMNS, "unexpected MUSES raw-output columns")
    require(np.isfinite(frame.to_numpy(dtype=float)).all(), "non-finite MUSES raw output")
    require((frame["temperature"] == 0.0).all(), "anchor generator requires T=0")
    return frame.sort_values(["isospin_asymmetry", "nucleon_density"]).reset_index(drop=True)


def ansatz_basis(density: np.ndarray) -> np.ndarray:
    return np.column_stack(
        (
            density,
            density ** (4.0 / 3.0),
            density ** (5.0 / 3.0),
            density**2,
        )
    )


@dataclass(frozen=True)
class InteractionFit:
    symmetric_coefficients: np.ndarray
    neutron_coefficients: np.ndarray

    def interaction_energy(self, density: float, delta: float) -> float:
        basis = ansatz_basis(np.asarray([density]))[0]
        symmetric = float(basis @ self.symmetric_coefficients)
        neutron = float(basis @ self.neutron_coefficients)
        return symmetric + (neutron - symmetric) * delta**2

    def interaction_density_derivative(self, density: float, delta: float) -> float:
        powers = np.asarray([1.0, 4.0 / 3.0, 5.0 / 3.0, 2.0])
        derivative_basis = powers * density ** (powers - 1.0)
        symmetric = float(derivative_basis @ self.symmetric_coefficients)
        neutron = float(derivative_basis @ self.neutron_coefficients)
        return symmetric + (neutron - symmetric) * delta**2

    def symmetry_interaction(self, density: float) -> float:
        basis = ansatz_basis(np.asarray([density]))[0]
        return float(basis @ (self.neutron_coefficients - self.symmetric_coefficients))


def fit_interaction(raw: pd.DataFrame) -> InteractionFit:
    fits: dict[float, np.ndarray] = {}
    for delta in (0.0, 1.0):
        rows = raw[np.isclose(raw["isospin_asymmetry"], delta)].copy()
        densities = rows["nucleon_density"].to_numpy()
        expected = np.arange(
            DENSITY_START_FM3,
            DENSITY_END_FM3 + DENSITY_STEP_FM3 / 2.0,
            DENSITY_STEP_FM3,
        )
        require(np.allclose(densities, expected, atol=1.0e-12, rtol=0.0), "raw density grid mismatch")
        interaction_energy = (rows["f_1"] + rows["f_2"]).to_numpy()
        coefficients, residuals, rank, singular_values = np.linalg.lstsq(
            ansatz_basis(densities), interaction_energy, rcond=None
        )
        require(rank == 4, "rank-deficient free-energy ansatz")
        require(np.isfinite(coefficients).all(), "non-finite ansatz coefficients")
        fits[delta] = coefficients
    return InteractionFit(fits[0.0], fits[1.0])


def kinetic_energy_per_baryon(density: float, delta: float) -> float:
    proton_fraction = (1.0 - delta) / 2.0
    neutron_fraction = (1.0 + delta) / 2.0
    common = (3.0 / 5.0) * (3.0 * math.pi**2) ** (2.0 / 3.0) * HBARC_MEV_FM**2 / 2.0
    return common * density ** (2.0 / 3.0) * (
        proton_fraction ** (5.0 / 3.0) / PROTON_MASS_MEV
        + neutron_fraction ** (5.0 / 3.0) / NEUTRON_MASS_MEV
    )


def kinetic_delta_derivative(density: float, delta: float) -> float:
    proton_fraction = (1.0 - delta) / 2.0
    neutron_fraction = (1.0 + delta) / 2.0
    common = (3.0 / 5.0) * (3.0 * math.pi**2) ** (2.0 / 3.0) * HBARC_MEV_FM**2 / 2.0
    return common * density ** (2.0 / 3.0) * (5.0 / 6.0) * (
        neutron_fraction ** (2.0 / 3.0) / NEUTRON_MASS_MEV
        - proton_fraction ** (2.0 / 3.0) / PROTON_MASS_MEV
    )


def lepton_number_density(chemical_potential: float, mass: float) -> float:
    if chemical_potential <= mass:
        return 0.0
    momentum = math.sqrt(chemical_potential**2 - mass**2)
    return momentum**3 / (3.0 * math.pi**2 * HBARC_MEV_FM**3)


def lepton_thermodynamics(chemical_potential: float, mass: float) -> tuple[float, float]:
    if chemical_potential <= mass:
        return 0.0, 0.0
    momentum = math.sqrt(chemical_potential**2 - mass**2)
    logarithm = math.log((momentum + chemical_potential) / mass)
    denominator = math.pi**2 * HBARC_MEV_FM**3
    energy = (
        momentum * chemical_potential * (2.0 * momentum**2 + mass**2)
        - mass**4 * logarithm
    ) / (8.0 * denominator)
    pressure = (
        momentum * chemical_potential * (2.0 * momentum**2 - 3.0 * mass**2)
        + 3.0 * mass**4 * logarithm
    ) / (24.0 * denominator)
    return energy, pressure


def chemical_potential_difference(fit: InteractionFit, density: float, delta: float) -> float:
    derivative = kinetic_delta_derivative(density, delta)
    derivative += 2.0 * fit.symmetry_interaction(density) * delta
    return 2.0 * derivative + NEUTRON_MASS_MEV - PROTON_MASS_MEV


def beta_equilibrium_delta(fit: InteractionFit, density: float) -> float:
    def charge_residual(delta: float) -> float:
        proton_density = density * (1.0 - delta) / 2.0
        chemical_potential = chemical_potential_difference(fit, density, delta)
        lepton_density = lepton_number_density(chemical_potential, ELECTRON_MASS_MEV)
        lepton_density += lepton_number_density(chemical_potential, MUON_MASS_MEV)
        return proton_density - lepton_density

    lower = 0.0
    upper = 1.0 - 1.0e-12
    require(charge_residual(lower) > 0.0, "beta-equilibrium lower bracket failed")
    require(charge_residual(upper) < 0.0, "beta-equilibrium upper bracket failed")
    return float(brentq(charge_residual, lower, upper, xtol=1.0e-13, rtol=1.0e-13))


def member_rows(fit: InteractionFit) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    full_rows: list[dict[str, float]] = []
    for density in np.arange(
        DENSITY_START_FM3,
        DENSITY_END_FM3 + DENSITY_STEP_FM3 / 2.0,
        DENSITY_STEP_FM3,
    ):
        density = float(round(density, 12))
        delta = beta_equilibrium_delta(fit, density)
        proton_fraction = (1.0 - delta) / 2.0
        lepton_mu = chemical_potential_difference(fit, density, delta)
        kinetic = kinetic_energy_per_baryon(density, delta)
        interaction = fit.interaction_energy(density, delta)
        rest_mass = (
            proton_fraction * PROTON_MASS_MEV
            + (1.0 - proton_fraction) * NEUTRON_MASS_MEV
        )
        electron_energy, electron_pressure = lepton_thermodynamics(
            lepton_mu, ELECTRON_MASS_MEV
        )
        muon_energy, muon_pressure = lepton_thermodynamics(
            lepton_mu, MUON_MASS_MEV
        )
        energy_density = density * (rest_mass + kinetic + interaction)
        energy_density += electron_energy + muon_energy
        nuclear_pressure = density * (
            (2.0 / 3.0) * kinetic
            + density * fit.interaction_density_derivative(density, delta)
        )
        pressure = nuclear_pressure + electron_pressure + muon_pressure
        chemical_potential = (energy_density + pressure) / density
        full_rows.append(
            {
                "n_b_fm3": density,
                "p_mev_fm3": pressure,
                "epsilon_mev_fm3": energy_density,
                "mu_b_mev": chemical_potential,
                "delta_beta": delta,
                "proton_fraction": proton_fraction,
                "lepton_mu_mev": lepton_mu,
            }
        )
    pressures = np.asarray([row["p_mev_fm3"] for row in full_rows])
    energies = np.asarray([row["epsilon_mev_fm3"] for row in full_rows])
    sound_speeds = np.gradient(pressures, energies, edge_order=2)
    for row, sound_speed in zip(full_rows, sound_speeds, strict=True):
        row["cs2"] = float(sound_speed)
    anchor_rows = [
        row
        for row in full_rows
        if ANCHOR_LOWER_FM3 - 1.0e-12
        <= row["n_b_fm3"]
        <= ANCHOR_UPPER_FM3 + 1.0e-12
    ]
    return full_rows, anchor_rows


def write_canonical_csv(path: Path, rows: Iterable[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: f"{row[column]:.12e}" for column in CANONICAL_COLUMNS})


def write_diagnostics_csv(path: Path, rows: Iterable[dict[str, float]]) -> None:
    columns = CANONICAL_COLUMNS + ("delta_beta", "proton_fraction", "lepton_mu_mev")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: f"{row[column]:.12e}" for column in columns})


def environment_record() -> dict[str, Any]:
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyyaml": yaml.__version__,
        "scipy": __import__("scipy").__version__,
    }


def generate(args: argparse.Namespace) -> int:
    source_dir = args.muses_source_dir.resolve()
    yaml_cpp_source_dir = args.yaml_cpp_source_dir.resolve()
    output_dir = args.output_dir.resolve()
    run_root = args.run_root.resolve()
    source_record = verify_upstream(source_dir)
    yaml_cpp_record = verify_yaml_cpp(yaml_cpp_source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    build_record = build_muses_binary(
        muses_source_dir=source_dir,
        yaml_cpp_source_dir=yaml_cpp_source_dir,
        run_root=run_root,
    )
    binary = Path(build_record["binary_path"])
    execution: list[dict[str, Any]] = []
    products: dict[str, dict[str, Any]] = {}
    for interaction in INTERACTIONS:
        run_record = run_muses_member(
            source_dir=source_dir,
            binary=binary,
            run_root=run_root,
            interaction=interaction,
        )
        execution.append(run_record)
        raw = read_raw(Path(run_record["raw_path"]))
        fit = fit_interaction(raw)
        full_rows, anchor_rows = member_rows(fit)
        label = interaction.replace("-", "_")
        config_target = output_dir / f"config_{label}.yaml"
        shutil.copyfile(run_record["config_path"], config_target)
        raw_target = output_dir / f"raw_{label}.csv"
        shutil.copyfile(run_record["raw_path"], raw_target)
        anchor_target = output_dir / f"beta_equilibrium_{label}.csv"
        diagnostics_target = output_dir / f"beta_equilibrium_{label}_diagnostics.csv"
        write_canonical_csv(anchor_target, anchor_rows)
        write_diagnostics_csv(diagnostics_target, full_rows)
        products[interaction] = {
            "config": {"path": config_target.name, "sha256": sha256_file(config_target)},
            "raw": {"path": raw_target.name, "sha256": sha256_file(raw_target)},
            "anchor": {
                "path": anchor_target.name,
                "sha256": sha256_file(anchor_target),
                "rows": len(anchor_rows),
            },
            "diagnostics": {
                "path": diagnostics_target.name,
                "sha256": sha256_file(diagnostics_target),
                "rows": len(full_rows),
            },
            "ansatz_coefficients": {
                "basis": ["n", "n^(4/3)", "n^(5/3)", "n^2"],
                "symmetric_matter": fit.symmetric_coefficients.tolist(),
                "pure_neutron_matter": fit.neutron_coefficients.tolist(),
            },
            "key_normalizations": run_record["normalizations"],
        }
    record = {
        "schema_version": 1,
        "generator": "generate_muses_chiral_eft_anchor.py",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source_record,
        "build_dependency": {"yaml_cpp": yaml_cpp_record},
        "build": build_record,
        "scientific_semantics": {
            "member_set": list(INTERACTIONS),
            "envelope_type": "coherent_interaction_reference_envelope",
            "probabilistic_coverage": None,
            "formal_chiral_truncation_error": False,
            "temperature_mev": 0.0,
            "matter": "charge_neutral_beta_equilibrated_npe_mu",
            "asymmetry_treatment": "quadratic_interaction_energy",
            "leptons": ["electron", "muon"],
        },
        "grid": {
            "calculation_density_fm3": [
                DENSITY_START_FM3,
                DENSITY_END_FM3,
                DENSITY_STEP_FM3,
            ],
            "published_anchor_density_fm3": [ANCHOR_LOWER_FM3, ANCHOR_UPPER_FM3],
            "isospin_asymmetry_step": ASYMMETRY_STEP,
        },
        "environment": environment_record(),
        "execution": execution,
        "products": products,
    }
    record_path = output_dir / "generation_record.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"generation_record": str(record_path), "products": products}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--muses-source-dir", type=Path, required=True)
    parser.add_argument("--yaml-cpp-source-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    return generate(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
