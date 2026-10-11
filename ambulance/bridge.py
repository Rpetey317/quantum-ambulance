"""JSON-string entrypoints for Qollab's JS -> Python .callPromising bridge."""

import json
from base64 import b64encode

from .core import evaluate_case, load_case


def synthetic_case():
    return json.dumps(load_case(), allow_nan=False)


def case_data(case_id):
    # Literal paths let Qollab discover and package these assets.
    if case_id == "synthetic":
        case = load_case("data/cases/synthetic.json")
    elif case_id == "caba-comuna4":
        case = load_case("data/cases/caba-comuna4.json")
    elif case_id == "caba":
        case = load_case("data/cases/caba.json")
    else:
        raise ValueError("unknown packaged case")
    return json.dumps(case, allow_nan=False)


# Both backgrounds cover the same EPSG:9498 kilometre frame (see
# tools/build_map_assets.py); the UI crops it to each case extent.
MAP_FRAME_KM = {"minX": 11.0, "maxX": 33.0, "minY": 60.0, "maxY": 83.0}
MAP_STYLES = {
    "streets": (
        "data/map/caba-streets.webp",
        "Street map © OpenStreetMap contributors, rendered from the BBBike "
        "Buenos Aires extract",
    ),
    "satellite": (
        "data/map/caba-satellite.webp",
        "Contains modified Copernicus Sentinel-2 data (2024), rendered via "
        "Microsoft Planetary Computer",
    ),
}


def map_image(style):
    if style not in MAP_STYLES:
        raise ValueError("unknown map style")
    path, attribution = MAP_STYLES[style]
    with open(path, "rb") as source:
        image = source.read()
    return json.dumps(
        {
            "style": style,
            "image": "data:image/webp;base64," + b64encode(image).decode("ascii"),
            "bounds": MAP_FRAME_KM,
            "attribution": attribution,
        },
        allow_nan=False,
    )


def describe_backend(backend):
    from .quantum import backend_identity

    return json.dumps(backend_identity(backend), allow_nan=False)


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
