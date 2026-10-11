"""Bounded public-web adapter. Reuses the core/QAOA contracts, no remote jobs."""

import json
from threading import BoundedSemaphore

from .core import evaluate_case, prepare_case

MAX_BODY_BYTES = 2_000_000
MAX_ZONES = 4_000
MAX_SITES = 16
MAX_QUANTUM_SITES = 8
MAX_WEB_SHOTS = 128
# Per-process concurrency guard, not a distributed quota or persistent cache.
QUANTUM_SLOT = BoundedSemaphore(1)


def backend_info():
    return {
        "name": "Web simulator · Qiskit BasicSimulator",
        "class": "BasicSimulator",
        "module": "qiskit.providers.basic_provider",
        "is_simulator": True,
        "shot_cap": MAX_WEB_SHOTS,
        "site_cap": MAX_QUANTUM_SITES,
    }


def validate_public_case(case):
    if not isinstance(case, dict):
        raise ValueError("Case must be a JSON object.")
    for key, cap in (("zones", MAX_ZONES), ("sites", MAX_SITES)):
        if not isinstance(case.get(key), list) or not 1 <= len(case[key]) <= cap:
            raise ValueError(f"Web cases need between 1 and {cap} {key}.")
    prepare_case(case)
    return case


def evaluate_request(action, payload):
    if action == "preview":
        return evaluate_case(validate_public_case(payload))
    if action != "quantum":
        raise ValueError("Unknown action.")
    if not isinstance(payload, dict):
        raise ValueError("Quantum request must be a JSON object.")
    case = validate_public_case(payload.get("data"))
    shots = payload.get("shots", 64)
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= MAX_WEB_SHOTS:
        raise ValueError(f"Web quantum shots must be an integer between 1 and {MAX_WEB_SHOTS}.")
    if len(case["sites"]) > MAX_QUANTUM_SITES:
        raise ValueError(f"Web QAOA supports up to {MAX_QUANTUM_SITES} candidates. Remove candidates or use Qollab.")
    if not QUANTUM_SLOT.acquire(blocking=False):
        raise BlockingIOError("This simulator instance is busy. Please try again shortly.")
    try:
        from qiskit.providers.basic_provider import BasicSimulator
        from .bridge import run_quantum

        result = json.loads(run_quantum(
            json.dumps(case, allow_nan=False), BasicSimulator(),
            shots=shots, layers=3, restarts=2, maxiter=150, seed=1,
        ))
        result["qaoa"]["backend"].update(backend_info())
        return result
    finally:
        QUANTUM_SLOT.release()
