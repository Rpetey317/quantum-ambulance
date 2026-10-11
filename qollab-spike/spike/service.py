import hashlib
import json
import math

from qiskit import QuantumCircuit


def _coordinate(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10:
        raise ValueError(f"{name} must be a finite number from 0 to 10")
    return float(value)


def _case(case_json):
    if not isinstance(case_json, str) or len(case_json) > 16384:
        raise ValueError("Case must be a JSON string under 16 KiB")
    case = json.loads(case_json)
    if not isinstance(case, dict) or not isinstance(case.get("site"), dict):
        raise ValueError("Case must contain a site")
    site = case["site"]
    if not isinstance(site.get("id"), str) or not 1 <= len(site["id"]) <= 40:
        raise ValueError("Site needs a short ID")
    site = {"id": site["id"], "x": _coordinate(site.get("x"), "site.x"),
            "y": _coordinate(site.get("y"), "site.y")}
    radius = case.get("radius")
    if type(radius) not in (int, float) or not math.isfinite(radius) or not 0 < radius <= 10:
        raise ValueError("Radius must be a finite number greater than 0 and at most 10")
    source_zones = case.get("zones")
    if not isinstance(source_zones, list) or not 1 <= len(source_zones) <= 20:
        raise ValueError("Case needs 1–20 zones")
    zones = []
    seen = set()
    for zone in source_zones:
        if not isinstance(zone, dict) or not isinstance(zone.get("id"), str):
            raise ValueError("Every zone needs an ID")
        name = zone["id"]
        if not 1 <= len(name) <= 40 or name in seen:
            raise ValueError("Zone IDs must be short and unique")
        seen.add(name)
        population = zone.get("population")
        if type(population) is not int or not 1 <= population <= 1000000:
            raise ValueError("Zone population must be a positive integer at most 1000000")
        zones.append({"id": name, "x": _coordinate(zone.get("x"), "zone.x"),
                      "y": _coordinate(zone.get("y"), "zone.y"), "population": population})
    return {"site": site, "radius": float(radius), "zones": zones}


def load_fixture():
    with open("data/fixture.json", "rb") as file:
        data = file.read()
    case = _case(data.decode("utf-8"))
    return json.dumps({"case": case, "path": "data/fixture.json", "bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest()})


def evaluate(case_json):
    case = _case(case_json)
    site = case["site"]
    covered = [zone for zone in case["zones"]
               if math.dist((site["x"], site["y"]), (zone["x"], zone["y"])) <= case["radius"]]
    angle = math.pi * site["x"] / 10
    return json.dumps({"case": case, "covered_zone_ids": [zone["id"] for zone in covered],
                       "covered_population": sum(zone["population"] for zone in covered),
                       "total_population": sum(zone["population"] for zone in case["zones"]),
                       "ry_angle_radians": angle, "ideal_probability_one": math.sin(angle / 2) ** 2},
                      allow_nan=False)


def audit_circuit(case_json):
    site = _case(case_json)["site"]
    circuit = QuantumCircuit(1, 1)
    circuit.ry(math.pi * site["x"] / 10, 0)
    circuit.measure(0, 0)
    return circuit


def run_on_backend(selected_backend, case_json, shots):
    if type(shots) is not int or not 1 <= shots <= 128:
        raise ValueError("Shots must be an integer from 1 to 128")
    counts = selected_backend.run(audit_circuit(case_json), shots=shots).result().get_counts()
    return json.dumps({"counts": counts, "measured_shots": sum(counts.values())})
