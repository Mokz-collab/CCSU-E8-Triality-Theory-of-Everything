from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import yaml


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    data: dict[str, Any]

    @property
    def master_seed(self) -> int:
        return int(self.data["master_seed"])

    @property
    def replicates(self) -> int:
        return int(self.data["replicates_per_cell"])

    @property
    def confirmatory(self) -> bool:
        return bool(self.data["confirmatory"])


def load_config(path: str | Path) -> LoadedConfig:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    required = {"schema_version", "registration_id", "confirmatory", "master_seed", "state", "design", "atlas", "blocks", "analysis"}
    missing = sorted(required.difference(data))
    if missing:
        raise ValueError(f"configuration missing keys: {missing}")
    if int(data["schema_version"]) != 1:
        raise ValueError("unsupported schema_version")
    if float(data["design"]["coupling_kappa"]) <= 0 or float(data["design"]["coupling_kappa"]) >= 1:
        raise ValueError("coupling_kappa must be in (0,1)")
    if int(data["state"]["public_dim"]) < 1 or int(data["state"]["private_dim"]) < 1:
        raise ValueError("state dimensions must be positive")
    if data["blocks"]["P4"]["malicious_count_rule"] != "floor_N_over_3":
        raise ValueError("P4 malicious_count_rule must be floor_N_over_3")
    return LoadedConfig(resolved, data)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_seed(master_seed: int, *labels: object) -> int:
    label_text = "|".join(str(x) for x in labels).encode("utf-8")
    digest = hashlib.sha256(label_text).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint64)
    sequence = np.random.SeedSequence([int(master_seed), *(int(x) for x in words)])
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def random_orthogonal(rng: np.random.Generator, dimension: int) -> np.ndarray:
    q, r = np.linalg.qr(rng.normal(size=(dimension, dimension)))
    signs = np.sign(np.diag(r))
    signs[signs == 0] = 1.0
    return q @ np.diag(signs)


def _connected(adjacency: np.ndarray) -> bool:
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for neighbor in np.flatnonzero(adjacency[node]):
            j = int(neighbor)
            if j not in seen:
                seen.add(j)
                stack.append(j)
    return len(seen) == adjacency.shape[0]


def make_graph(topology: str, n: int, rng: np.random.Generator, er_probability: float) -> tuple[np.ndarray, int]:
    if n < 2:
        raise ValueError("a graph requires at least two observers")
    adjacency = np.zeros((n, n), dtype=float)
    attempts = 1
    if topology == "path":
        for i in range(n - 1):
            adjacency[i, i + 1] = adjacency[i + 1, i] = 1.0
    elif topology == "ring":
        for i in range(n):
            adjacency[i, (i + 1) % n] = adjacency[(i + 1) % n, i] = 1.0
    elif topology == "star":
        for i in range(1, n):
            adjacency[0, i] = adjacency[i, 0] = 1.0
    elif topology == "complete":
        adjacency[:] = 1.0
        np.fill_diagonal(adjacency, 0.0)
    elif topology == "er":
        attempts = 0
        while True:
            attempts += 1
            draws = rng.random((n, n))
            upper = np.triu(draws < er_probability, 1)
            adjacency = upper.astype(float) + upper.T.astype(float)
            if _connected(adjacency):
                break
            if attempts >= 10000:
                raise RuntimeError("unable to generate a connected ER graph")
    else:
        raise ValueError(f"unknown topology: {topology}")
    return adjacency, attempts


def normalized_laplacian(adjacency: np.ndarray) -> np.ndarray:
    degree = adjacency.sum(axis=1)
    if np.any(degree <= 0):
        raise ValueError("normalized Laplacian requires positive degree")
    inv_sqrt = np.diag(1.0 / np.sqrt(degree))
    return np.eye(adjacency.shape[0]) - inv_sqrt @ adjacency @ inv_sqrt


def neighbor_matrix(adjacency: np.ndarray) -> np.ndarray:
    degree = adjacency.sum(axis=1)
    return adjacency / degree[:, None]


def geometric_median(points: np.ndarray, weights: np.ndarray | None = None, tolerance: float = 1e-8, max_iterations: int = 200) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or len(points) == 0:
        raise ValueError("points must be a non-empty 2D array")
    if weights is None:
        weights = np.ones(len(points), dtype=float)
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (len(points),) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("invalid weights")
    weights = weights / weights.sum()
    estimate = np.average(points, axis=0, weights=weights)
    for _ in range(max_iterations):
        distances = np.linalg.norm(points - estimate, axis=1)
        close = np.flatnonzero(distances < tolerance)
        if close.size:
            return points[int(close[0])].copy()
        inverse = weights / distances
        updated = (inverse[:, None] * points).sum(axis=0) / inverse.sum()
        if np.linalg.norm(updated - estimate) <= tolerance:
            return updated
        estimate = updated
    return estimate


def _cap_weights(weights: np.ndarray, cap: float) -> np.ndarray:
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    for _ in range(64):
        over = weights > cap
        if not np.any(over):
            break
        excess = float((weights[over] - cap).sum())
        weights[over] = cap
        under = ~over
        if not np.any(under):
            break
        room = cap - weights[under]
        room_sum = float(room.sum())
        if room_sum <= 0:
            break
        weights[under] += excess * room / room_sum
    return weights / weights.sum()


def robust_atlas(claims: np.ndarray, provenance: Sequence[str], confidence: np.ndarray, atlas_cfg: dict[str, Any]) -> np.ndarray:
    claims = np.asarray(claims, dtype=float)
    confidence = np.asarray(confidence, dtype=float)
    if len(provenance) != len(claims) or confidence.shape != (len(claims),):
        raise ValueError("claims, provenance, and confidence must align")
    if atlas_cfg.get("provenance_deduplication", True):
        keep: list[int] = []
        seen: set[str] = set()
        for idx, origin in enumerate(provenance):
            if origin not in seen:
                keep.append(idx)
                seen.add(origin)
        claims = claims[keep]
        confidence = confidence[keep]
    center = np.median(claims, axis=0)
    mad = np.median(np.abs(claims - center), axis=0)
    scale = np.maximum(mad, 1e-12)
    limit = float(atlas_cfg["residual_clip_mad"]) * scale
    clipped = center + np.clip(claims - center, -limit, limit)
    confidence = np.clip(confidence, float(atlas_cfg["confidence_min"]), float(atlas_cfg["confidence_max"]))
    weights = _cap_weights(confidence, float(atlas_cfg["normalized_weight_cap"]))
    return geometric_median(
        clipped,
        weights,
        tolerance=float(atlas_cfg["weiszfeld_tolerance"]),
        max_iterations=int(atlas_cfg["weiszfeld_max_iterations"]),
    )


def dispersion(points: np.ndarray) -> float:
    center = np.median(points, axis=0)
    return float(np.median(np.sum((points - center) ** 2, axis=1)))


def mean_pairwise_distance(points: np.ndarray) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    values = [np.linalg.norm(points[i] - points[j]) for i in range(n) for j in range(i + 1, n)]
    return float(np.mean(values))


def generate_latent(config: LoadedConfig, n: int, horizon: int, sigma: float, seed: int) -> dict[str, np.ndarray]:
    cfg = config.data
    state = cfg["state"]
    public_dim = int(state["public_dim"])
    private_dim = int(state["private_dim"])
    total_dim = public_dim + private_dim
    rng = np.random.default_rng(seed)
    q = np.zeros((horizon, public_dim), dtype=float)
    private = np.zeros((horizon, n, private_dim), dtype=float)
    private[0] = rng.normal(scale=float(state["private_innovation_std"]), size=(n, private_dim))
    for t in range(1, horizon):
        q[t] = float(state["public_ar"]) * q[t - 1] + rng.normal(scale=float(state["public_innovation_std"]), size=public_dim)
        private[t] = float(state["private_ar"]) * private[t - 1] + rng.normal(scale=float(state["private_innovation_std"]), size=(n, private_dim))
    charts = np.stack([random_orthogonal(rng, total_dim) for _ in range(n)])
    decoded = np.zeros((horizon, n, total_dim), dtype=float)
    clip = float(state["local_clip"])
    for t in range(horizon):
        for i in range(n):
            local_true = np.concatenate([q[t], private[t, i]])
            psi = charts[i] @ local_true + rng.normal(scale=sigma, size=total_dim)
            decoded[t, i] = np.clip(charts[i].T @ psi, -clip, clip)
    return {"q": q, "private": private, "decoded": decoded, "charts": charts}


def run_public_dynamics(config: LoadedConfig, latent: dict[str, np.ndarray], architecture: str, adjacency: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cfg = config.data
    public_dim = int(cfg["state"]["public_dim"])
    observed = latent["decoded"][:, :, :public_dim]
    horizon, n, _ = observed.shape
    kappa = float(cfg["design"]["coupling_kappa"])
    neighbor = neighbor_matrix(adjacency)
    estimates = np.zeros_like(observed)
    omega = np.zeros((horizon, public_dim), dtype=float)
    confidence = np.ones(n, dtype=float)
    provenance = [f"observer-{i}" for i in range(n)]
    for t in range(horizon):
        claims = observed[t]
        robust = robust_atlas(claims, provenance, confidence, cfg["atlas"])
        if t == 0:
            previous_neighbor = claims
        else:
            previous_neighbor = neighbor @ estimates[t - 1]
        if architecture == "IND":
            estimates[t] = claims
            omega[t] = claims.mean(axis=0)
        elif architecture == "MEAN":
            estimates[t] = (1.0 - kappa) * claims + kappa * previous_neighbor
            omega[t] = estimates[t].mean(axis=0)
        elif architecture == "ATLAS":
            estimates[t] = (1.0 - kappa) * claims + kappa * robust
            omega[t] = robust
        elif architecture == "HYBRID":
            estimates[t] = (1.0 - kappa) * claims + kappa * (0.5 * robust + 0.5 * previous_neighbor)
            omega[t] = robust
        else:
            raise ValueError(f"unknown architecture: {architecture}")
    return estimates, omega


def metric_p1(config: LoadedConfig, n: int, sigma: float, architecture: str, seed: int) -> dict[str, Any]:
    block = config.data["blocks"]["P1"]
    latent = generate_latent(config, n, int(block["horizon"]), sigma, seed)
    rng = np.random.default_rng(deterministic_seed(seed, "P1-graph"))
    adjacency, attempts = make_graph("ring", n, rng, float(config.data["design"]["er_probability"]))
    estimates, _ = run_public_dynamics(config, latent, architecture, adjacency)
    dq = np.array([dispersion(x) for x in estimates])
    dp = np.array([mean_pairwise_distance(x) for x in latent["private"]])
    i0, i1 = (int(x) for x in block["initial_window"])
    f0, f1 = (int(x) for x in block["final_window"])
    early_q = float(np.mean(dq[i0 - 1 : i1]))
    late_q = float(np.mean(dq[f0 - 1 : f1]))
    early_p = float(np.mean(dp[i0 - 1 : i1]))
    late_p = float(np.mean(dp[f0 - 1 : f1]))
    return {
        "r_q": late_q / max(early_q, 1e-12),
        "r_private": late_p / max(early_p, 1e-12),
        "graph_attempts": attempts,
    }


def _cycle_nodes(topology: str, n: int, adjacency: np.ndarray) -> list[int]:
    if topology == "ring":
        return list(range(n))
    if topology == "complete":
        return [0, 1, 2]
    # Deterministic DFS cycle for a connected ER graph.
    parent = [-1] * n
    depth = [-1] * n
    stack = [(0, iter(int(x) for x in np.flatnonzero(adjacency[0])))]
    depth[0] = 0
    while stack:
        node, neighbors = stack[-1]
        try:
            nxt = next(neighbors)
        except StopIteration:
            stack.pop()
            continue
        if depth[nxt] == -1:
            parent[nxt] = node
            depth[nxt] = depth[node] + 1
            stack.append((nxt, iter(int(x) for x in np.flatnonzero(adjacency[nxt]))))
        elif nxt != parent[node] and depth[nxt] < depth[node]:
            path = [node]
            cur = node
            while cur != nxt:
                cur = parent[cur]
                path.append(cur)
            if len(path) >= 3:
                return list(reversed(path))
    # Connected ER draws may be trees; add a deterministic virtual diagnostic cycle.
    return [0, 1, 2 if n > 2 else 0]


def metric_p2(config: LoadedConfig, n: int, topology: str, translation_bias: float, seed: int) -> dict[str, Any]:
    block = config.data["blocks"]["P2"]
    horizon = int(block["horizon"])
    repair_window = int(block["repair_window"])
    noise_levels = config.data["design"]["noise_levels"]
    sigma = float(noise_levels[min(1, len(noise_levels) - 1)])
    latent = generate_latent(config, n, horizon, sigma, seed)
    rng = np.random.default_rng(deterministic_seed(seed, "P2-graph"))
    adjacency, attempts = make_graph(topology, n, rng, float(config.data["design"]["er_probability"]))
    cycle = _cycle_nodes(topology, n, adjacency)
    direction = rng.normal(size=int(config.data["state"]["public_dim"]))
    direction /= max(np.linalg.norm(direction), 1e-12)
    edge_bias = translation_bias * direction
    h_c = float(np.linalg.norm(edge_bias))
    observed = latent["decoded"][:, :, : int(config.data["state"]["public_dim"])]
    neighbor = neighbor_matrix(adjacency)
    kappa = float(config.data["design"]["coupling_kappa"])
    estimates = observed[0].copy()
    removal_step = horizon - repair_window
    cost = 0.0
    for t in range(1, horizon):
        messages = neighbor @ estimates
        if t < removal_step and translation_bias > 0:
            target = cycle[1 % len(cycle)]
            messages[target] += edge_bias
        robust = robust_atlas(observed[t], [f"observer-{i}" for i in range(n)], np.ones(n), config.data["atlas"])
        estimates = (1.0 - kappa) * observed[t] + kappa * (0.5 * robust + 0.5 * messages)
        if t >= removal_step:
            cost += float(np.mean((estimates - latent["q"][t]) ** 2))
    return {"h_c": h_c, "repair_cost": cost, "cycle_length": len(cycle), "graph_attempts": attempts}


def metric_p3(config: LoadedConfig, n: int, sigma: float, snr: float, architecture: str, condition: str, seed: int) -> dict[str, Any]:
    block = config.data["blocks"]["P3"]
    horizon = int(block["horizon"])
    event_step = int(block["event_step"])
    confirmation = int(block["confirmation_step"])
    latent = generate_latent(config, n, horizon, sigma, seed)
    observed = latent["decoded"][:, :, : int(config.data["state"]["public_dim"])].copy()
    rng = np.random.default_rng(deterministic_seed(seed, "P3-event"))
    direction = rng.normal(size=observed.shape[2])
    direction /= max(np.linalg.norm(direction), 1e-12)
    magnitude = snr * max(sigma, 1e-6)
    if condition == "event":
        observed[event_step:, 0] += magnitude * direction
        observed[confirmation:, 1:] += magnitude * direction
    elif condition != "no_event":
        raise ValueError(f"unknown P3 condition: {condition}")
    baseline = observed[max(0, event_step - 5) : event_step].mean(axis=(0, 1))
    early_local_score = float(np.dot(observed[event_step, 0] - baseline, direction) / max(sigma, 1e-6))
    early_mean_score = float(np.dot(observed[event_step].mean(axis=0) - baseline, direction) / max(sigma, 1e-6))
    threshold = 2.5
    memory_ok = confirmation - event_step <= int(block["memory_window"])
    if architecture in {"ATLAS", "HYBRID"}:
        detected = early_local_score >= threshold and memory_ok
    elif architecture == "MEAN":
        detected = early_mean_score >= threshold
    elif architecture == "IND":
        detected = early_local_score >= threshold
    else:
        raise ValueError(f"unknown architecture: {architecture}")
    recovered = bool(detected and condition == "event")
    false_positive = bool(detected and condition == "no_event")
    return {
        "recovered": recovered,
        "false_positive": false_positive,
        "early_local_score": early_local_score,
        "early_mean_score": early_mean_score,
    }


def _aggregate_claims(config: LoadedConfig, architecture: str, claims: np.ndarray, provenance: list[str], confidence: np.ndarray) -> np.ndarray:
    if architecture in {"ATLAS", "HYBRID"}:
        return robust_atlas(claims, provenance, confidence, config.data["atlas"])
    return np.average(claims, axis=0, weights=np.maximum(confidence, 1e-12))


def metric_p4(config: LoadedConfig, n: int, sigma: float, architecture: str, attack: str, seed: int) -> dict[str, Any]:
    block = config.data["blocks"]["P4"]
    horizon = int(block["horizon"])
    latent = generate_latent(config, n, horizon, sigma, seed)
    observed = latent["decoded"][:, :, : int(config.data["state"]["public_dim"])]
    malicious = max(1, n // 3)
    clean_omega = []
    attack_omega = []
    for t in range(horizon):
        clean_claims = observed[t]
        clean_origins = [f"observer-{i}" for i in range(n)]
        clean_confidence = np.ones(n)
        attacked = clean_claims.copy()
        origins = clean_origins.copy()
        confidence = clean_confidence.copy()
        if attack == "sign_flip":
            attacked[:malicious] *= -1.0
        elif attack == "confidence_inflation":
            confidence[:malicious] = 100.0
        elif attack == "replay":
            attacked = np.concatenate([attacked, attacked[:malicious]], axis=0)
            origins = origins + origins[:malicious]
            confidence = np.concatenate([confidence, np.ones(malicious)])
        else:
            raise ValueError(f"unknown P4 attack: {attack}")
        clean_omega.append(_aggregate_claims(config, architecture, clean_claims, clean_origins, clean_confidence))
        attack_omega.append(_aggregate_claims(config, architecture, attacked, origins, confidence))
    clean_arr = np.asarray(clean_omega)
    attack_arr = np.asarray(attack_omega)
    displacement = float(np.sqrt(np.mean((attack_arr - clean_arr) ** 2)) / max(np.sqrt(np.mean(clean_arr**2)), 1e-12))
    return {"delta_omega": displacement, "malicious_count": malicious}


def metric_p5(config: LoadedConfig, n: int, topology: str, seed: int) -> dict[str, Any]:
    block = config.data["blocks"]["P5"]
    rng = np.random.default_rng(seed)
    adjacency, attempts = make_graph(topology, n, rng, float(config.data["design"]["er_probability"]))
    laplacian = normalized_laplacian(adjacency)
    eigenvalues = np.linalg.eigvalsh(laplacian)
    lambda2 = float(eigenvalues[1])
    x = rng.normal(size=(n, int(config.data["state"]["public_dim"])))
    initial = max(dispersion(x), 1e-12)
    threshold = float(block["dispersion_fraction"]) * initial
    consecutive_needed = int(block["consecutive_steps"])
    kappa = float(config.data["design"]["coupling_kappa"])
    consecutive = 0
    tau = int(block["horizon"])
    for t in range(1, int(block["horizon"]) + 1):
        x = x - kappa * (laplacian @ x)
        if dispersion(x) <= threshold:
            consecutive += 1
            if consecutive >= consecutive_needed:
                tau = t - consecutive_needed + 1
                break
        else:
            consecutive = 0
    return {"lambda2": lambda2, "tau": tau, "graph_attempts": attempts}


def run_metric(config: LoadedConfig, block: str, cell: dict[str, Any], seed: int) -> dict[str, Any]:
    if block == "P1":
        return metric_p1(config, int(cell["n"]), float(cell["sigma"]), str(cell["architecture"]), seed)
    if block == "P2":
        return metric_p2(config, int(cell["n"]), str(cell["topology"]), float(cell["translation_bias"]), seed)
    if block == "P3":
        return metric_p3(config, int(cell["n"]), float(cell["sigma"]), float(cell["snr"]), str(cell["architecture"]), str(cell["condition"]), seed)
    if block == "P4":
        return metric_p4(config, int(cell["n"]), float(cell["sigma"]), str(cell["architecture"]), str(cell["attack"]), seed)
    if block == "P5":
        return metric_p5(config, int(cell["n"]), str(cell["topology"]), seed)
    raise ValueError(f"unknown block: {block}")


def enumerate_cells(config: LoadedConfig, block: str) -> Iterable[dict[str, Any]]:
    data = config.data
    counts = data["design"]["observer_counts"]
    noise = data["design"]["noise_levels"]
    architectures = data["design"]["architectures"]
    if block == "P1":
        for n in counts:
            for sigma in noise:
                for architecture in architectures:
                    yield {"n": n, "sigma": sigma, "architecture": architecture}
    elif block == "P2":
        for n in counts:
            for topology in data["blocks"]["P2"]["graphs"]:
                for bias in data["blocks"]["P2"]["translation_biases"]:
                    yield {"n": n, "topology": topology, "translation_bias": bias}
    elif block == "P3":
        for n in counts:
            for snr in data["blocks"]["P3"]["snr_levels"]:
                for architecture in architectures:
                    for condition in data["blocks"]["P3"]["conditions"]:
                        yield {"n": n, "sigma": noise[1 if len(noise) > 1 else 0], "snr": snr, "architecture": architecture, "condition": condition}
    elif block == "P4":
        for n in counts:
            for attack in data["blocks"]["P4"]["attacks"]:
                for architecture in architectures:
                    yield {"n": n, "sigma": noise[1 if len(noise) > 1 else 0], "attack": attack, "architecture": architecture}
    elif block == "P5":
        for n in counts:
            for topology in data["design"]["graph_topologies"]:
                yield {"n": n, "topology": topology, "architecture": data["blocks"]["P5"]["architecture"]}
    else:
        raise ValueError(f"unknown block: {block}")


def cell_label(block: str, cell: dict[str, Any]) -> str:
    parts = [block] + [f"{key}={cell[key]}" for key in sorted(cell)]
    return ";".join(parts)
