#!/usr/bin/env python3
"""
Valida los casos de data/cases/*.json contra el contrato (issue #3).

Chequea:
  - campos requeridos (meta completo, radius_km>0, k_default entero 1..N sitios)
  - ids unicos, pesos > 0, coordenadas finitas, sin duplicados (<1 m)
  - sitios dentro/near de la nube de zonas (los bounds de CABA en EPSG:9498)
  - tamaño de archivo (los assets se empaquetan en el proyecto Qollab)
  - sanity de cobertura: cada sitio cubre >=1 zona; cobertura union real y
    greedy con la misma matematica que baseline.py (distancia euclidea en km)

Sale con codigo != 0 si alguna validacion falla.
"""

import glob
import itertools
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_GLOB = os.path.join(ROOT, "data", "cases", "*.json")

REQUIRED_META = (
    "id", "revision", "name", "generated_at_utc", "generator", "crs",
    "coordinate_units", "weight_units", "weight_source", "zone_resolution",
    "site_selection", "sources", "license_note",
)
REQUIRED_SOURCE = ("key", "name", "url", "dataset_page", "license")
MAX_SIZE_KB = 1024  # los assets viajan dentro del proyecto Qollab


def fail(errors, msg):
    errors.append(msg)
    print("  FAIL", msg)


def coverage(zones, site, radius_km):
    r2 = radius_km * radius_km
    return {i for i, z in enumerate(zones)
            if (z["x_km"] - site["x_km"]) ** 2 + (z["y_km"] - site["y_km"]) ** 2 <= r2}


def union_weight(zones, covered_ids):
    return sum(zones[i]["weight"] for i in covered_ids)


def validate(path):
    errors = []
    name = os.path.basename(path)
    print(f"== {name}")
    try:
        with open(path, encoding="utf-8") as f:
            case = json.load(f)
    except Exception as e:
        fail(errors, f"no se pudo parsear JSON: {e}")
        return errors

    meta = case.get("meta", {})
    for k in REQUIRED_META:
        if k not in meta:
            fail(errors, f"meta.{k} ausente")
    for s in meta.get("sources", []):
        for k in REQUIRED_SOURCE:
            if k not in s:
                fail(errors, f"source '{s.get('key')}' sin campo '{k}'")

    radius = case.get("radius_km")
    k = case.get("k_default")
    zones = case.get("zones", [])
    sites = case.get("sites", [])
    if not isinstance(radius, (int, float)) or radius <= 0:
        fail(errors, "radius_km debe ser > 0")
    if not zones:
        fail(errors, "sin zonas")
    if not sites:
        fail(errors, "sin sitios")
    if errors:
        return errors
    if not isinstance(k, int) or not 1 <= k <= len(sites):
        fail(errors, f"k_default={k} fuera de 1..{len(sites)}")

    # ids unicos
    for coll, label in ((zones, "zona"), (sites, "sitio")):
        ids = [z["id"] for z in coll]
        if len(ids) != len(set(ids)):
            dupes = {i for i in ids if ids.count(i) > 1}
            fail(errors, f"ids de {label} duplicados: {sorted(dupes)[:5]}")

    # pesos y coordenadas
    for z in zones:
        if not isinstance(z.get("weight"), int) or z["weight"] <= 0:
            fail(errors, f"zona {z['id']} weight invalido: {z.get('weight')}")
            break
        if not (math.isfinite(z["x_km"]) and math.isfinite(z["y_km"])):
            fail(errors, f"zona {z['id']} coordenadas no finitas")
            break
    for s in sites:
        if not (math.isfinite(s["x_km"]) and math.isfinite(s["y_km"])):
            fail(errors, f"sitio {s['id']} coordenadas no finitas")
            break

    # coordenadas duplicadas (<1 m) entre sitios
    for a, b in itertools.combinations(sites, 2):
        if math.dist((a["x_km"], a["y_km"]), (b["x_km"], b["y_km"])) < 0.001:
            fail(errors, f"sitios {a['id']} y {b['id']} casi coincidentes")

    # sitios dentro de la nube de zonas (+2 km de margen)
    xs = [z["x_km"] for z in zones]
    ys = [z["y_km"] for z in zones]
    bx, by = (min(xs) - 2, max(xs) + 2), (min(ys) - 2, max(ys) + 2)
    for s in sites:
        if not (bx[0] <= s["x_km"] <= bx[1] and by[0] <= s["y_km"] <= by[1]):
            fail(errors, f"sitio {s['id']} fuera de bounds {bx}x{by}")

    # tamaño del asset (empaquetado en Qollab)
    kb = os.path.getsize(path) / 1024
    if kb > MAX_SIZE_KB:
        fail(errors, f"archivo de {kb:.0f} KB supera el limite {MAX_SIZE_KB} KB")

    # sanity de cobertura (misma matematica que baseline.py)
    cubre = [coverage(zones, s, radius) for s in sites]
    for s, c in zip(sites, cubre):
        if not c:
            fail(errors, f"sitio {s['id']} no cubre ninguna zona")
    def cubierto(sel):
        ids = set().union(*[cubre[i] for i in sel]) if sel else set()
        return union_weight(zones, ids)

    sel = []
    k_ok = isinstance(k, int) and 1 <= k <= len(sites)
    for _ in range(k if k_ok else 0):  # greedy (k invalido ya se reporto arriba)
        mejor = max((i for i in range(len(sites)) if i not in sel),
                    key=lambda i: cubierto(sel + [i]))
        sel.append(mejor)
    total = union_weight(zones, range(len(zones)))
    print(f"  zonas {len(zones)} | sitios {len(sites)} | K {k} | radio {radius} km"
          f" | pob {total:,} | {kb:.0f} KB")
    print(f"  greedy {sel} -> {cubierto(sel):,} ({100 * cubierto(sel) / total:.1f}%)")
    if not errors:
        print("  OK")
    return errors


def main():
    paths = sorted(glob.glob(CASES_GLOB))
    if not paths:
        print("no hay casos en data/cases/; correr tools/build_cases.py primero")
        return 1
    errs = 0
    for p in paths:
        errs += len(validate(p))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
