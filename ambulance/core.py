"""Pure, deterministic maximum-coverage solvers over Cartesian km coordinates."""

import hashlib
import itertools
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter

SCHEMA_VERSION = 1
QUANTUM_SITE_CAP = 16
EXACT_COMBINATION_LIMIT = 10_000
EXACT_ZONE_WORK_LIMIT = 5_000_000


class CaseValidationError(ValueError):
    """The input cannot represent a supported coverage problem."""


def _number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CaseValidationError(f"{label} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (positive and value <= 0):
        raise CaseValidationError(
            f"{label} must be finite" + (" and > 0" if positive else "")
        )
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise CaseValidationError(f"{label} must be a nonempty string")
    return value


@dataclass(frozen=True)
class Zone:
    id: str
    x_km: float
    y_km: float
    weight: float


@dataclass(frozen=True)
class Site:
    id: str
    x_km: float
    y_km: float


@dataclass(frozen=True)
class CoverageModel:
    meta: dict
    fingerprint: str
    zones: tuple[Zone, ...]
    sites: tuple[Site, ...]
    radius_km: float
    k: int
    covers: tuple[frozenset[int], ...]
    total_weight: float
    coverage_s: float

    @property
    def n(self):
        return len(self.sites)

    def covered_zones(self, selected):
        indices = tuple(selected)
        if any(
            isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < self.n
            for i in indices
        ):
            raise ValueError("selected site indices must be integers in 0..N-1")
        if len(set(indices)) != len(indices):
            raise ValueError("selected site indices must be unique")
        return frozenset().union(*(self.covers[i] for i in indices))

    def covered_weight(self, selected):
        return math.fsum(
            self.zones[i].weight for i in sorted(self.covered_zones(selected))
        )


def load_case(path="data/cases/synthetic.json"):
    """The literal default path also allows Qollab's static asset loader to find it."""
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def prepare_case(case):
    """Validate and rebuild all coverage inputs. Does not mutate the caller's data.

    Accept a JSON object or its JSON string. `k` overrides the asset's `k_default`.
    Zone centroids may coincide; candidate sites closer than one metre may not.
    """
    started = perf_counter()
    if isinstance(case, str):
        try:
            case = json.loads(case)
        except (ValueError, TypeError) as exc:
            raise CaseValidationError("case must contain valid JSON") from exc
    if not isinstance(case, dict):
        raise CaseValidationError("case must be a JSON object")
    version = case.get("schema_version", SCHEMA_VERSION)
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != SCHEMA_VERSION
    ):
        raise CaseValidationError("unsupported case schema_version")
    meta = case.get("meta")
    if not isinstance(meta, dict):
        raise CaseValidationError("meta must be an object")
    for key in ("id", "crs", "coordinate_units", "weight_units", "zone_resolution"):
        _text(meta.get(key), f"meta.{key}")
    revision = meta.get("revision")
    if (
        isinstance(revision, bool)
        or not isinstance(revision, (int, str))
        or (isinstance(revision, int) and revision < 0)
        or (isinstance(revision, str) and not revision.strip())
    ):
        raise CaseValidationError(
            "meta.revision must be a nonnegative integer or nonempty string"
        )
    units = meta["coordinate_units"].strip().lower()
    if units != "km" and not units.startswith("km ("):
        raise CaseValidationError(
            "coordinates must already be Cartesian kilometres (km)"
        )
    crs = meta["crs"].lower().replace(" ", "")
    if any(term in crs for term in ("epsg:4326", "epsg:4269", "longlat", "lon/lat")):
        raise CaseValidationError(
            "geographic coordinates must be projected before coverage"
        )
    if not isinstance(meta.get("sources"), list) or not meta["sources"]:
        raise CaseValidationError("meta.sources must be a nonempty provenance list")
    if any(not isinstance(source, dict) for source in meta["sources"]):
        raise CaseValidationError("meta.sources entries must be objects")
    radius = _number(case.get("radius_km"), "radius_km", positive=True)
    records = {}
    for name, record_type in (("zones", Zone), ("sites", Site)):
        items = case.get(name)
        if not isinstance(items, list) or not items:
            raise CaseValidationError(f"{name} must be a nonempty array")
        parsed, ids = [], set()
        for index, item in enumerate(items):
            label = f"{name}[{index}]"
            if not isinstance(item, dict):
                raise CaseValidationError(f"{label} must be an object")
            record_id = _text(item.get("id"), label + ".id")
            if record_id in ids:
                raise CaseValidationError(f"duplicate {name} ID: {record_id}")
            ids.add(record_id)
            values = [
                record_id,
                _number(item.get("x_km"), label + ".x_km"),
                _number(item.get("y_km"), label + ".y_km"),
            ]
            if name == "zones":
                values.append(
                    _number(item.get("weight"), label + ".weight", positive=True)
                )
            parsed.append(record_type(*values))
        records[name] = tuple(parsed)
    zones, sites = records["zones"], records["sites"]
    k = case.get("k", case.get("k_default"))
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= len(sites):
        raise CaseValidationError(
            "k (or k_default) must be an integer with 1 <= K <= N"
        )
    for left, right in itertools.combinations(sites, 2):
        if math.hypot(left.x_km - right.x_km, left.y_km - right.y_km) < 0.001:
            raise CaseValidationError(
                f"candidate sites {left.id} and {right.id} are closer than 1 metre"
            )
    try:
        total = math.fsum(zone.weight for zone in zones)
    except OverflowError as exc:
        raise CaseValidationError("total zone weight must be finite") from exc
    if not math.isfinite(total):
        raise CaseValidationError("total zone weight must be finite")
    covers = tuple(
        frozenset(
            i
            for i, zone in enumerate(zones)
            if math.hypot(zone.x_km - site.x_km, zone.y_km - site.y_km) <= radius
        )
        for site in sites
    )
    # Hash every model input and its order, even when the UI forgets to bump revision.
    identity = {
        "case_id": meta["id"],
        "crs": meta["crs"],
        "weight_units": meta["weight_units"],
        "radius_km": float(radius),
        "k": k,
        "zones": [[z.id, float(z.x_km), float(z.y_km), float(z.weight)] for z in zones],
        "sites": [[s.id, float(s.x_km), float(s.y_km)] for s in sites],
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return CoverageModel(
        deepcopy(meta),
        fingerprint,
        zones,
        sites,
        radius,
        k,
        covers,
        total,
        perf_counter() - started,
    )


def result_for(model, method, selected=None, status="ok", message=None, solve_s=None):
    """Common JSON-compatible result envelope; absent measurements are null."""
    indices = sorted(selected) if selected is not None else []
    if selected is not None and len(indices) != model.k:
        raise ValueError("a solver selection must contain exactly K distinct sites")
    covered = model.covered_zones(indices) if selected is not None else None
    weight = model.covered_weight(indices) if selected is not None else None
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": model.meta["id"],
        "case_revision": model.meta["revision"],
        "input_fingerprint": model.fingerprint,
        "method": method,
        "status": status,
        "message": message,
        "k": model.k,
        "n_sites": model.n,
        "radius_km": model.radius_km,
        "selected_site_indices": indices,
        "selected_site_ids": [model.sites[i].id for i in indices],
        "covered_zone_ids": (
            [model.zones[i].id for i in sorted(covered)] if covered is not None else []
        ),
        "covered_weight": weight,
        "coverage_pct": (
            (weight / model.total_weight) * 100 if weight is not None else None
        ),
        "total_weight": model.total_weight,
        "weight_units": model.meta["weight_units"],
        "timings": {
            "coverage_s": model.coverage_s,
            "solve_s": solve_s,
            "quantum_prepare_s": None,
            "local_optimization_s": None,
            "transpile_s": None,
            "backend_job_s": None,
        },
    }


def solve_greedy(model):
    """Break equal marginal-coverage ties by the current zero-based input order."""
    started = perf_counter()
    selected, covered = [], frozenset()
    for _ in range(model.k):
        candidates = (i for i in range(model.n) if i not in selected)
        best = max(
            candidates,
            key=lambda i: math.fsum(
                model.zones[z].weight for z in sorted(model.covers[i] - covered)
            ),
        )
        selected.append(best)
        covered = covered | model.covers[best]
    return result_for(model, "greedy", selected, solve_s=perf_counter() - started)


def solve_exact(
    model, max_combinations=EXACT_COMBINATION_LIMIT, max_zone_work=EXACT_ZONE_WORK_LIMIT
):
    """Enumerate only below both cost limits; count every tied optimal selection."""
    for name, value in (
        ("max_combinations", max_combinations),
        ("max_zone_work", max_zone_work),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    combinations = math.comb(model.n, model.k)
    details = {
        "combination_count": combinations,
        "max_combinations": max_combinations,
        "estimated_zone_work": combinations * len(model.zones),
        "max_zone_work": max_zone_work,
        "optimal_selections": [],
        "n_optimal_solutions": None,
    }
    if (
        combinations > max_combinations
        or details["estimated_zone_work"] > max_zone_work
    ):
        result = result_for(
            model,
            "exact",
            status="unavailable",
            message="Exact search exceeds its documented cost bound",
        )
    else:
        started = perf_counter()
        best_weight, optima = -1, []
        for selection in itertools.combinations(range(model.n), model.k):
            weight = model.covered_weight(selection)
            if weight > best_weight:
                best_weight, optima = weight, [selection]
            elif weight == best_weight:
                optima.append(selection)
        result = result_for(model, "exact", optima[0], solve_s=perf_counter() - started)
        details["optimal_selections"] = [list(selection) for selection in optima]
        details["n_optimal_solutions"] = len(optima)
    result.update(details)
    return result


def evaluate_case(
    case, max_combinations=EXACT_COMBINATION_LIMIT, max_zone_work=EXACT_ZONE_WORK_LIMIT
):
    """Return both classical previews for one freshly prepared case."""
    model = prepare_case(case)
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": model.meta["id"],
        "case_revision": model.meta["revision"],
        "input_fingerprint": model.fingerprint,
        "greedy": solve_greedy(model),
        "exact": solve_exact(model, max_combinations, max_zone_work),
    }
