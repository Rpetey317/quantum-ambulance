"""JSON-string entrypoints for Qollab's JS -> Python .callPromising bridge."""

import json

from .core import evaluate_case, load_case


def synthetic_case():
    return json.dumps(load_case(), allow_nan=False)


def preview(case_json):
    return json.dumps(evaluate_case(case_json), allow_nan=False)


def run_quantum(
    case_json, backend, shots=64, layers=3, restarts=2, maxiter=150, seed=1
):
    # Lazy import: loading/editing a case and classical previews need no Qiskit.
    from .quantum import run_qaoa

    comparison = evaluate_case(case_json)
    comparison["qaoa"] = run_qaoa(
        case_json,
        backend,
        shots=shots,
        layers=layers,
        restarts=restarts,
        maxiter=maxiter,
        seed=seed,
        exact_result=comparison["exact"],
    )
    return json.dumps(comparison, allow_nan=False)
