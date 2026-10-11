"""Bounded QAOA tuning locally, followed by one job on the supplied backend."""

import itertools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Integral
from time import perf_counter

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import ParameterVector
from qiskit.circuit.library import RYGate
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize

from .core import QUANTUM_SITE_CAP, CoverageModel, prepare_case, result_for

MAX_LAYERS = 5
MAX_RESTARTS = 4
MAX_ITERATIONS = 500
MAX_SHOTS = 4096
IONQ_SIMULATOR_SHOT_CAP = 128  # conservative application policy, not a provider limit
IONQ_SITE_CAP = 16  # conservative application policy, not a provider limit
COST_SCALE = 5.0


def _integer(value, name, minimum, maximum):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")


@dataclass(frozen=True)
class QAOAModel:
    coverage: CoverageModel
    q: np.ndarray
    costs: np.ndarray
    weights: np.ndarray
    dicke: np.ndarray
    circuit: QuantumCircuit
    evolution: QuantumCircuit
    gamma: ParameterVector
    beta: ParameterVector

    def bind(self, angles):
        # Explicit mapping: Qiskit sorts b before g, regardless of creation order.
        parameters = list(self.gamma) + list(self.beta)
        if len(angles) != len(parameters) or not np.all(np.isfinite(angles)):
            raise ValueError("expected finite gamma angles followed by beta angles")
        active = set(self.evolution.parameters)
        return {
            parameter: angle
            for parameter, angle in zip(parameters, angles)
            if parameter in active
        }


def _dicke_circuit(n, k):
    """Uniform weight-K state via SCS blocks (arXiv:1904.07358), O(N*K) gates.

    Generic state synthesis grows as 2**N; serialized remote jobs large
    enough to be truncated in transport motivated the deterministic form.
    """

    def scs(m, k):
        block = QuantumCircuit(k + 1)
        block.cx(k - 1, k)
        block.cry(2 * math.acos(math.sqrt(1 / m)), k, k - 1)
        block.cx(k - 1, k)
        for l in range(2, k + 1):
            block.cx(k - l, k)
            block.append(
                RYGate(2 * math.acos(math.sqrt(l / m))).control(2),
                [k, k - l + 1, k - l],
            )
            block.cx(k - l, k)
        return block

    circuit = QuantumCircuit(n)
    for i in range(n - k, n):
        circuit.x(i)
    if k == n:
        return circuit
    for l in range(n, k, -1):
        circuit.compose(scs(l, k), range(l - k - 1, l), inplace=True)
    for l in range(k, 1, -1):
        circuit.compose(scs(l, l - 1), range(l), inplace=True)
    return circuit


def build_qaoa(case, layers=3):
    """Rebuild Q, basis costs, Dicke state, and XY ring for this exact input."""
    _integer(layers, "layers", 1, MAX_LAYERS)
    coverage = case if isinstance(case, CoverageModel) else prepare_case(case)
    if coverage.n > QUANTUM_SITE_CAP:
        raise ValueError(f"QAOA is bounded to {QUANTUM_SITE_CAP} candidate sites")
    n = coverage.n
    q = np.zeros((n, n))
    for i in range(n):
        q[i, i] = -coverage.covered_weight([i]) / coverage.total_weight
    for i, j in itertools.combinations(range(n), 2):
        q[i, j] = (
            math.fsum(
                coverage.zones[z].weight
                for z in sorted(coverage.covers[i] & coverage.covers[j])
            )
            / coverage.total_weight
        )
    states = np.array([[(value >> i) & 1 for i in range(n)] for value in range(2**n)])
    weights = states.sum(axis=1)
    costs = np.einsum("bi,ij,bj->b", states, q, states)
    dicke = (weights == coverage.k).astype(float)
    dicke /= np.linalg.norm(dicke)
    gamma, beta = ParameterVector("g", layers), ParameterVector("b", layers)
    evolution = QuantumCircuit(n)
    for layer in range(layers):
        for i in range(n):
            overlaps = sum(q[min(i, j), max(i, j)] for j in range(n) if j != i)
            evolution.rz(-gamma[layer] * COST_SCALE * (q[i, i] + overlaps / 2), i)
        for i, j in itertools.combinations(range(n), 2):
            if q[i, j] != 0:
                evolution.rzz(gamma[layer] * COST_SCALE * q[i, j] / 2, i, j)
        # Each adjacent RXX/RYY pair preserves excitation count. For N=1
        # there are no edges; for N=2 do not repeat the same undirected edge.
        seen = set()
        for start in (0, 1):
            for i in range(start, n, 2):
                j = (i + 1) % n
                edge = tuple(sorted((i, j)))
                if i != j and edge not in seen:
                    seen.add(edge)
                    evolution.rxx(beta[layer], i, j)
                    evolution.ryy(beta[layer], i, j)
    circuit = QuantumCircuit(n)
    # The initial register is |0...0>; the deterministic blocks prepare exactly
    # the same uniform K-weight state as model.dicke, without resets.
    circuit.compose(_dicke_circuit(n, coverage.k), inplace=True)
    circuit.compose(evolution, inplace=True)
    return QAOAModel(
        coverage, q, costs, weights, dicke, circuit, evolution, gamma, beta
    )


def optimize_angles(model, restarts=2, maxiter=150, seed=1):
    """Evaluate bounded local statevectors; this function never contacts a backend."""
    _integer(restarts, "restarts", 1, MAX_RESTARTS)
    _integer(maxiter, "maxiter", 2 * len(model.gamma) + 2, MAX_ITERATIONS)
    _integer(seed, "seed", 0, 2**32 - 1)
    layers = len(model.gamma)
    initial = Statevector(model.dicke)

    def energy(angles):
        probabilities = initial.evolve(
            model.evolution.assign_parameters(model.bind(angles))
        ).probabilities()
        return float(probabilities @ model.costs)

    rng, best, evaluations = np.random.default_rng(seed), None, 0
    for attempt in range(restarts):
        angles = (
            np.concatenate(
                [np.linspace(0.1, 1, layers), np.linspace(0.5, 0.05, layers)]
            )
            if attempt == 0
            else rng.uniform(0, 1.5, 2 * layers)
        )
        result = minimize(energy, angles, method="COBYLA", options={"maxiter": maxiter})
        evaluations += int(result.nfev)
        if (
            np.isfinite(result.fun)
            and np.all(np.isfinite(result.x))
            and (best is None or result.fun < best.fun)
        ):
            best = result
    if best is None:
        raise RuntimeError("local angle optimization produced no finite iterate")
    return {
        "angles": best.x.tolist(),
        "gamma": best.x[:layers].tolist(),
        "beta": best.x[layers:].tolist(),
        "approximate_energy": float(best.fun),
        "converged": bool(best.success),
        "message": str(best.message),
        "evaluations": evaluations,
        "restarts": restarts,
        "maxiter": maxiter,
        "seed": seed,
    }


def decode_bitstring(bits, n):
    """Classical bit i maps to logical site index i, with the rightmost bit first."""
    if not isinstance(bits, str):
        raise ValueError("measurement keys must be bitstrings")
    bits = "".join(bits.split())
    if len(bits) != n or any(bit not in "01" for bit in bits):
        raise ValueError(f"expected a {n}-bit Qiskit bitstring")
    return tuple(i for i, bit in enumerate(reversed(bits)) if bit == "1")


def _check_exact(model, exact):
    if exact is None:
        return
    if not isinstance(exact, dict) or any(
        exact.get(key) != value
        for key, value in (
            ("method", "exact"),
            ("case_id", model.meta["id"]),
            ("case_revision", model.meta["revision"]),
            ("input_fingerprint", model.fingerprint),
        )
    ):
        raise ValueError(
            "exact reference does not match this case revision and input fingerprint"
        )
    if exact.get("status") == "unavailable":
        return
    if exact.get("status") != "ok":
        raise ValueError("exact reference must be successful or unavailable")
    count = exact.get("n_optimal_solutions")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 1 <= count <= math.comb(model.n, model.k)
    ):
        raise ValueError("exact reference has an invalid optimal-solution count")
    selected = exact.get("selected_site_indices", [])
    if len(selected) != model.k or model.covered_weight(selected) != exact.get(
        "covered_weight"
    ):
        raise ValueError(
            "exact reference has an inconsistent actual-coverage selection"
        )


def summarize_counts(model, counts, exact_result=None):
    """Choose the best valid measured union coverage; retain every invalid shot."""
    _check_exact(model, exact_result)
    if not isinstance(counts, Mapping):
        raise ValueError(
            "backend counts must be a mapping of bitstrings to integer frequencies"
        )
    normalized, candidates = {}, []
    invalid = malformed = total = valid = 0
    for bits, frequency in counts.items():
        if (
            isinstance(frequency, bool)
            or not isinstance(frequency, Integral)
            or frequency < 0
        ):
            raise ValueError("backend counts must have nonnegative integer frequencies")
        if not isinstance(bits, str):
            raise ValueError("backend counts must use string keys")
        key, frequency = "".join(bits.split()), int(frequency)
        normalized[key] = normalized.get(key, 0) + frequency
    for bits, frequency in normalized.items():
        total += frequency
        try:
            selection = decode_bitstring(bits, model.n)
        except ValueError:
            invalid += frequency
            malformed += frequency
            continue
        if len(selection) != model.k:
            invalid += frequency
        else:
            valid += frequency
            if frequency:
                candidates.append(
                    (selection, frequency, model.covered_weight(selection))
                )
    # Coverage first, frequency second, lexicographic input indices third.
    best = (
        min(candidates, key=lambda item: (-item[2], -item[1], item[0]))
        if candidates
        else None
    )
    result = result_for(
        model,
        "qaoa",
        best[0] if best else None,
        status="ok" if best else "no_valid_sample",
        message=None if best else "No measured sample selected exactly K valid sites",
    )
    result.update(
        {
            "counts": normalized,
            "shots": total,
            "requested_shots": None,
            "valid_shots": valid,
            "invalid_shots": invalid,
            "malformed_shots": malformed,
            "valid_shot_rate": valid / total if total else None,
            "optimal_probability": None,
            "optimal_probability_given_valid": None,
            "uniform_optimal_probability": None,
            "optimal_probability_amplification": None,
        }
    )
    if exact_result is not None and exact_result["status"] == "ok":
        optimum_shots = sum(
            frequency
            for _, frequency, weight in candidates
            if weight == exact_result["covered_weight"]
        )
        uniform = exact_result["n_optimal_solutions"] / math.comb(model.n, model.k)
        probability = optimum_shots / total if total else None
        result.update(
            {
                "optimal_probability": probability,
                "optimal_probability_given_valid": optimum_shots / valid
                if valid
                else None,
                "uniform_optimal_probability": uniform,
                "optimal_probability_amplification": probability / uniform
                if probability is not None
                else None,
            }
        )
    return result


def backend_identity(backend):
    """Best-effort identification without selecting devices or fetching providers."""
    info = {
        "name": None,
        "class": type(backend).__name__,
        "module": type(backend).__module__,
        "is_simulator": None,
    }
    try:
        name = getattr(backend, "name", None)
        info["name"] = (
            str(name() if callable(name) else name) if name is not None else None
        )
    except Exception:
        pass
    try:
        configuration = backend.configuration()
        simulator = getattr(configuration, "simulator", None)
        info["is_simulator"] = simulator if isinstance(simulator, bool) else None
    except Exception:
        pass
    if "simulator" in info["class"].lower():
        info["is_simulator"] = True
    return info


def run_qaoa(
    case,
    backend,
    shots=64,
    layers=3,
    restarts=2,
    maxiter=150,
    seed=1,
    exact_result=None,
):
    """One invocation submits at most one job, with no retry or sampler fallback.

    Known IonQ QPUs are rejected: this task authorizes simulator checks only.
    The platform/app owns backend lifetime and the one-job-per-Qollab-run UX.
    Invalid cases raise; provider/preparation failures return a failed envelope.
    """
    coverage = prepare_case(case)
    identity = backend_identity(backend)
    result = summarize_counts(coverage, {}, exact_result)
    result.update(
        {
            "status": "failed",
            "message": None,
            "backend": identity,
            "requested_shots": shots,
            "backend_run_calls": 0,
            "error_stage": None,
            "optimizer": None,
            "circuit": None,
        }
    )
    stage = "validation"
    try:
        if coverage.n > QUANTUM_SITE_CAP:
            raise ValueError(f"QAOA is bounded to {QUANTUM_SITE_CAP} candidate sites")
        _integer(shots, "shots", 1, MAX_SHOTS)
        _integer(layers, "layers", 1, MAX_LAYERS)
        _integer(restarts, "restarts", 1, MAX_RESTARTS)
        _integer(maxiter, "maxiter", 2 * layers + 2, MAX_ITERATIONS)
        _integer(seed, "seed", 0, 2**32 - 1)
        if backend is None or not callable(getattr(backend, "run", None)):
            raise ValueError("a visitor-selected backend with run() is required")
        is_ionq = (
            "ionq" in (identity["module"] + " " + (identity["name"] or "")).lower()
        )
        if is_ionq:
            if identity["is_simulator"] is not True:
                raise ValueError(
                    "Only identified IonQ simulators are enabled; paid hardware is outside this adapter's scope"
                )
            if coverage.n > IONQ_SITE_CAP:
                raise ValueError(
                    f"IonQ runs are bounded to {IONQ_SITE_CAP} candidate sites by application policy"
                )
            if shots > IONQ_SIMULATOR_SHOT_CAP:
                raise ValueError(
                    f"IonQ simulator smoke runs are capped at {IONQ_SIMULATOR_SHOT_CAP} shots by application policy"
                )
        stage = "quantum_preparation"
        started = perf_counter()
        model = build_qaoa(coverage, layers)
        result["timings"]["quantum_prepare_s"] = perf_counter() - started
        stage = "local_optimization"
        started = perf_counter()
        tuning = optimize_angles(model, restarts, maxiter, seed)
        result["timings"]["local_optimization_s"] = perf_counter() - started
        result["optimizer"] = tuning
        measured = model.circuit.assign_parameters(model.bind(tuning["angles"]))
        measured.measure_all()
        stage = "transpilation"
        started = perf_counter()
        compiled = transpile(
            measured, backend, optimization_level=1, seed_transpiler=seed
        )
        result["timings"]["transpile_s"] = perf_counter() - started
        result["circuit"] = {
            "logical_qubits": coverage.n,
            "compiled_qubits": compiled.num_qubits,
            "compiled_depth": compiled.depth(),
            "compiled_operations": dict(compiled.count_ops()),
            "layers": layers,
            "cost_scale": COST_SCALE,
            "objective": "normalized pairwise quadratic approximation",
        }
        stage = "backend_job"
        started = perf_counter()
        # This is the only backend.run call in the adapter. Never retry a failure.
        result["backend_run_calls"] = 1
        try:
            job = backend.run(compiled, shots=shots)
            counts = job.result().get_counts()
        finally:
            result["timings"]["backend_job_s"] = perf_counter() - started
        stage = "sample_analysis"
        sampled = summarize_counts(coverage, counts, exact_result)
        sampled["timings"] = result["timings"]
        result.update(sampled)
        result["requested_shots"] = shots
    except Exception as exc:
        result.update(
            {
                "status": "failed",
                "message": f"{type(exc).__name__}: {exc}",
                "error_stage": stage,
            }
        )
    return result
