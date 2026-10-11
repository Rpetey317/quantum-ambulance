#!/usr/bin/env python3
"""
Construye los casos de datos reales para el demo (issue #3).

Descarga los datasets publicos de GCBA en data/raw/ (no se commitean) y genera
data/cases/*.json con el contrato de caso: zonas ponderadas (id, x_km, y_km,
weight), sitios candidatos (id, x_km, y_km), radio_km, k_default y metadatos de
procedencia/CRS/licencia.

Solo usa la stdlib. Las coordenadas geograficas se proyectan a EPSG:9498
(POSGAR 2007 / CABA 2019, metros) antes de cualquier calculo de distancia;
nunca se usan grados lon/lat como km.

Casos generados:
  - caba-comuna4: caso compacto. Los 252 radios censales de la Comuna 4 como
    zonas; la comuna tiene 11 instituciones de emergencia reales (hospitales
    de agudos/ninos + cuarteles de bomberos) y el caso toma el subconjunto
    de 8 que maximiza la brecha greedy-vs-exacto a r=1.8 km, para que la
    comparacion de metodos discrimine.
  - caba: caso grande. Los 3552 radios censales de CABA con poblacion > 0 como
    zonas (resolucion completa, sin agregacion; los 2 radios sin poblacion se
    excluyen y se listan en meta) y 8 sitios curados por k-centro de los
    hospitales de agudos y de ninos de la ciudad (los establecimientos con
    guardia de emergencias, analogos a las bases de ambulancias del SAME).

Reproducir:  python tools/build_cases.py [--force]
Validar:     python tools/validate_cases.py
"""

import argparse
import itertools
import json
import math
import os
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data", "cases")

UA = {"User-Agent": "quantum-ambulance seed-data builder (research/demo)"}

# ---------------- Fuentes (verificadas 2026-10-11) ----------------
# El portal data.buenosaires.gob.ar bloquea curl sin navegador (WAF); los
# archivos se bajan directo del CDN. Las paginas de dataset se citan como
# referencia estable en data/README.md.

SOURCES = {
    "radios": {
        "name": "Información Censal por Radio (Censo 2010) — GCBA",
        "dataset_page": "https://data.buenosaires.gob.ar/dataset/informacion-censal-por-radio",
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/direccion-general-de-estadisticas-y-censos/informacion-censal-por-radio/caba_radios_censales.geojson",
        "file": "caba_radios_censales.geojson",
        "license": "CC-BY-2.5-AR (GCBA datos abiertos)",
    },
    "hospitales": {
        "name": "Hospitales públicos de la Ciudad — GCBA Ministerio de Salud",
        "dataset_page": "https://data.buenosaires.gob.ar/dataset/hospitales",
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-salud/hospitales/hospitales.geojson",
        "file": "hospitales.geojson",
        "license": "CC-BY-2.5-AR (GCBA datos abiertos)",
    },
    "bomberos": {
        "name": "Cuarteles y Destacamentos de Bomberos — GCBA",
        "dataset_page": "https://data.buenosaires.gob.ar/dataset/cuarteles-destacamentos-bomberos",
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-justicia-y-seguridad/cuarteles-destacamentos-bomberos/cuarteles_destacamentos_bomberos.geojson",
        "file": "cuarteles_destacamentos_bomberos.geojson",
        "license": "CC-BY-2.5-AR (GCBA datos abiertos)",
    },
    "barrios": {
        "name": "Barrios (polígonos) — GCBA",
        "dataset_page": "https://data.buenosaires.gob.ar/dataset/barrios",
        "url": "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/barrios/barrios.geojson",
        "file": "barrios.geojson",
        "license": "CC-BY-2.5-AR (GCBA datos abiertos)",
    },
}

# ---------------- EPSG:9498 (POSGAR 2007 / CABA 2019) ----------------
# Transverse Mercator: lat_0=-34.6292667, lon_0=-58.4633083, k=1,
# x_0=20000, y_0=70000, elipsoide WGS84. POSGAR~WGS84 (error <1m).

_A = 6378137.0
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_LAT0 = math.radians(-34.6292666666667)
_LON0 = math.radians(-58.4633083333333)
_X0, _Y0 = 20000.0, 70000.0


def _meridional(phi):
    """Arco de meridiano desde el ecuador (series de Snyder)."""
    return _A * (
        (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256) * phi
        - (3 * _E2 / 8 + 3 * _E2**2 / 32 + 45 * _E2**3 / 1024) * math.sin(2 * phi)
        + (15 * _E2**2 / 256 + 45 * _E2**3 / 1024) * math.sin(4 * phi)
        - (35 * _E2**3 / 3072) * math.sin(6 * phi)
    )


def to_9498(lon, lat):
    """WGS84 (grados) -> EPSG:9498 (metros). Devuelve (x_este, y_norte)."""
    lam, phi = math.radians(lon), math.radians(lat)
    sinp, cosp, tanp = math.sin(phi), math.cos(phi), math.tan(phi)
    n = _A / math.sqrt(1 - _E2 * sinp * sinp)
    t = tanp * tanp
    c = _EP2 * cosp * cosp
    a = (lam - _LON0) * cosp
    m = _meridional(phi)
    m0 = _meridional(_LAT0)
    x = _X0 + n * (
        a
        + (1 - t + c) * a**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * _EP2) * a**5 / 120
    )
    y = _Y0 + (m - m0) + n * tanp * (
        a * a / 2
        + (5 - t + 9 * c + 4 * c * c) * a**4 / 24
        + (61 - 58 * t + t * t + 600 * c - 330 * _EP2) * a**6 / 720
    )
    return x, y


def to_lonlat(x, y):
    """EPSG:9498 -> WGS84 (grados). Solo para chequeos internos."""
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    m = _meridional(_LAT0) + (y - _Y0)
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256))
    phi = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    sinp, cosp, tanp = math.sin(phi), math.cos(phi), math.tan(phi)
    n = _A / math.sqrt(1 - _E2 * sinp * sinp)
    r = _A * (1 - _E2) / (1 - _E2 * sinp * sinp) ** 1.5
    t = tanp * tanp
    c = _EP2 * cosp * cosp
    d = (x - _X0) / n
    lat = phi - (n * tanp / r) * (
        d * d / 2
        - (5 + 3 * t + 10 * c - 4 * c * c - 9 * _EP2) * d**4 / 24
        + (61 + 90 * t + 298 * c + 45 * t * t - 252 * _EP2 - 3 * c * c) * d**6 / 720
    )
    lon = _LON0 + (
        d
        - (1 + 2 * t + c) * d**3 / 6
        + (5 - 2 * c + 28 * t - 3 * c * c + 8 * _EP2 + 24 * t * t) * d**5 / 120
    ) / cosp
    return math.degrees(lon), math.degrees(lat)


# ---------------- Utilidades geograficas ----------------

def _ring_centroid_km(ring):
    """Centroide planar (shoelace) de un anillo ya proyectado a km."""
    area2 = cx = cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        cr = x1 * y2 - x2 * y1
        area2 += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    if abs(area2) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys), 0.0
    area = area2 / 2
    return cx / (3 * area2), cy / (3 * area2), abs(area)


def geometry_centroid_km(geom):
    """Centroide de Polygon/MultiPolygon WGS84, proyectado a km EPSG:9498."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    sx = sy = st = 0.0
    for poly in polys:
        exterior = [(lon, lat) for lon, lat, *_ in poly[0]]
        ring_km = [(x / 1000.0, y / 1000.0) for x, y in (to_9498(lon, lat) for lon, lat in exterior)]
        cx, cy, area = _ring_centroid_km(ring_km)
        sx += cx * area
        sy += cy * area
        st += area
    if st == 0:
        lon, lat = exterior[0]
        x, y = to_9498(lon, lat)
        return x / 1000.0, y / 1000.0
    return sx / st, sy / st


def point_in_polygon_km(px, py, geom_km):
    """Ray casting; geom_km = lista de anillos exteriores en km."""
    inside = False
    for ring in geom_km:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


# ---------------- Descarga y parseo ----------------

def fetch(key, force=False):
    path = os.path.join(RAW_DIR, SOURCES[key]["file"])
    if force or not os.path.exists(path):
        os.makedirs(RAW_DIR, exist_ok=True)
        req = urllib.request.Request(SOURCES[key]["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=300) as res, open(path, "wb") as f:
            f.write(res.read())
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def load_inputs(force=False):
    radios = fetch("radios", force)["features"]
    hospitales = fetch("hospitales", force)["features"]
    bomberos = fetch("bomberos", force)["features"]
    barrios = fetch("barrios", force)["features"]

    zones_all = []
    for ft in radios:
        p = ft["properties"]
        x, y = geometry_centroid_km(ft["geometry"])
        zones_all.append({
            "id": "R" + p["CO_FRAC_RA"].replace("_", "-"),
            "co_frac_ra": p["CO_FRAC_RA"],
            "comuna": int(p["COMUNA"]),
            "x_km": round(x, 4),
            "y_km": round(y, 4),
            "weight": int(p["TOTAL_POB"]),
        })

    # Establecimientos con guardia apta para emergencias: el analogo mas
    # cercano a una base de ambulancias del SAME (los hospitales cabecera).
    EMERG_GNA = {"Hospital General de Agudos", "Hospital de Niños"}

    sites_all = []
    for ft in hospitales:
        p = ft["properties"]
        if p["gna"] not in EMERG_GNA:
            continue  # especializados (salud mental, odontologia, zoonosis...)
        ex, ny = ft["geometry"]["coordinates"]  # ya viene en EPSG:9498 (metros)
        sites_all.append({
            "id": "H%02d" % (len(sites_all) + 1),
            "name": p["fna"],
            "type": "hospital",
            "comuna": int(p["com"]),
            "x_km": round(ex / 1000.0, 4),
            "y_km": round(ny / 1000.0, 4),
        })
    for ft in bomberos:
        p = ft["properties"]
        x, y = to_9498(p["x"], p["y"])
        sites_all.append({
            "id": "B%02d" % (len(sites_all) + 1),
            "name": p["dcia"],
            "type": "bomberos",
            "comuna": int(str(p["comuna"]).replace("Comuna", "").strip()),
            "x_km": round(x / 1000.0, 4),
            "y_km": round(y / 1000.0, 4),
        })

    barrio_rings = []  # [(nombre, [rings en km])]
    for ft in barrios:
        geom = ft["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings = []
        for poly in polys:
            rings.append([
                (x / 1000.0, y / 1000.0)
                for x, y in (to_9498(lon, lat) for lon, lat, *_ in poly[0])
            ])
        barrio_rings.append((ft["properties"]["BARRIO"].title(), rings))

    return zones_all, sites_all, barrio_rings


# ---------------- Curacion de sitios ----------------

def covered_weight(site, zones, radius_km):
    r2 = radius_km * radius_km
    return sum(z["weight"] for z in zones
               if (z["x_km"] - site["x_km"]) ** 2 + (z["y_km"] - site["y_km"]) ** 2 <= r2)


def curate_sites(candidates, zones, radius_km, n_sites):
    """Elige n_sites: siembra con el de mayor cobertura y luego k-centro
    (maximiza la distancia al elegido mas cercano). Deterministico."""
    seed = max(candidates, key=lambda s: (covered_weight(s, zones, radius_km), s["id"]))
    chosen = [seed]
    while len(chosen) < n_sites and len(chosen) < len(candidates):
        nxt = max(
            (s for s in candidates if s not in chosen),
            key=lambda s: (min(math.dist((s["x_km"], s["y_km"]), (c["x_km"], c["y_km"]))
                               for c in chosen), s["id"]),
        )
        chosen.append(nxt)
    return chosen


def _covered_ids(site, zones, radius_km):
    r2 = radius_km * radius_km
    return {i for i, z in enumerate(zones)
            if (z["x_km"] - site["x_km"]) ** 2 + (z["y_km"] - site["y_km"]) ** 2 <= r2}


def _weight_of(zones, ids):
    return sum(zones[i]["weight"] for i in ids)


def gap_maximizing_subset(candidates, zones, radius_km, n_sites, k):
    """Elige el subconjunto de n_sites sitios que maximiza la brecha entre
    greedy y el optimo exacto a este radio (para que el caso discrimine
    metodos). Desempata a mas hospitales y despues por orden determinista."""
    cubre = [_covered_ids(s, zones, radius_km) for s in candidates]

    def cubierto(indices, sel):
        ids = set()
        for i in sel:
            ids |= cubre[indices[i]]
        return _weight_of(zones, ids)

    def brecha(sub):
        sel = []
        for _ in range(k):
            sel.append(max((i for i in range(len(sub)) if i not in sel),
                           key=lambda i: (cubierto(sub, sel + [i]), -i)))
        exacta = max(itertools.combinations(range(len(sub)), k),
                     key=lambda s: (cubierto(sub, list(s)),))
        return cubierto(sub, list(exacta)) - cubierto(sub, sel)

    def criterio(sub):
        return (brecha(list(sub)),
                sum(1 for i in sub if candidates[i]["type"] == "hospital"),
                tuple(-i for i in sub))

    mejor = max(itertools.combinations(range(len(candidates)), n_sites),
                key=criterio)
    return [candidates[i] for i in mejor]


# ---------------- Ensamblado de casos ----------------

def zone_label(zone, barrio_rings):
    for name, rings in barrio_rings:
        if point_in_polygon_km(zone["x_km"], zone["y_km"], rings):
            return name
    return "Comuna %d" % zone["comuna"]


def make_meta(case_id, desc, zone_note, site_note, radius_note):
    return {
        "id": case_id,
        "revision": 1,
        "name": desc,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "tools/build_cases.py",
        "crs": "EPSG:9498 POSGAR 2007 / CABA 2019 (metros, Transverse Mercator)",
        "coordinate_units": "km (x=easting, y=northing en EPSG:9498)",
        "weight_units": "personas",
        "weight_source": "TOTAL_POB por radio censal, Censo Nacional 2010 (INDEC/GCBA)",
        "zone_resolution": zone_note,
        "site_selection": site_note,
        "radius_note": radius_note,
        "sources": [
            {"key": k, "name": s["name"], "url": s["url"],
             "dataset_page": s["dataset_page"], "license": s["license"]}
            for k, s in SOURCES.items() if k in ("radios", "hospitales", "bomberos", "barrios")
        ],
        "license_note": "Derivado de datos abiertos GCBA (CC-BY-2.5-AR): atribuir a GCBA/INDEC. El Censo 2022 existe a nivel comuna/radio (IDECBA); este caso usa 2010 por disponibilidad del archivo.",
    }


def build_cases(force=False):
    zones_all, sites_all, barrio_rings = load_inputs(force)
    k = 3
    n_sites = 8

    # etiquetar zonas por barrio (join espacial, no afecta distancias)
    for z in zones_all:
        z["label"] = zone_label(z, barrio_rings)

    # radios sin poblacion (espacios verdes/reserva): se excluyen y se cuentan
    sin_pob = [z for z in zones_all if z["weight"] <= 0]
    zones_all = [z for z in zones_all if z["weight"] > 0]
    excl = ("; %d radios sin poblacion excluidos (%s)" % (
        len(sin_pob), ", ".join(sorted({z['label'] for z in sin_pob}))
    )) if sin_pob else ""

    cases = []

    # ---- Caso compacto: Comuna 4 ----
    # La comuna tiene 11 instituciones de emergencia reales; el cap de la app
    # es 8 sitios. Regla de curaduria, reproducible abajo: el subconjunto de 8
    # que MAXIMIZA la brecha greedy-vs-exacto a este radio (el caso existe para
    # discriminar metodos), desempatando a mas hospitales y luego por orden.
    COMUNA = 4
    radius_c = 1.8  # ~3-4 min a 40 km/h en tejido urbano denso
    cz = [z for z in zones_all if z["comuna"] == COMUNA]
    pool = [s for s in sites_all if s["comuna"] == COMUNA]
    sel = gap_maximizing_subset(pool, cz, radius_c, n_sites, k)
    dropped = [s["name"] for s in pool if s not in sel]
    cases.append({
        "meta": make_meta(
            "caba-comuna4",
            "Comuna 4 (CABA) — caso compacto",
            "un punto por radio censal (centroide), sin agregacion; %d zonas" % len(cz),
            "%d de %d instituciones reales de la comuna (cap app = 8 sitios): subconjunto que maximiza la brecha greedy-vs-exacto a este radio, para que el caso discrimine metodos. Omitidos: %s" % (len(sel), len(pool), "; ".join(dropped)),
            "radio 1.8 km (~3-4 min a 40 km/h): greedy ~81% vs optimo ~85%; a r>=2.4 km todo queda cubierto y no discrimina",
        ),
        "radius_km": radius_c,
        "k_default": k,
        "zones": [{"id": z["id"], "label": z["label"], "x_km": z["x_km"],
                   "y_km": z["y_km"], "weight": z["weight"]} for z in cz],
        "sites": [{"id": s["id"], "name": s["name"], "type": s["type"],
                   "comuna": s["comuna"], "x_km": s["x_km"],
                   "y_km": s["y_km"]} for s in sel],
    })

    # ---- Caso grande: toda CABA ----
    # candidatos: los hospitales de agudos/ninos de la ciudad (bases naturales
    # de ambulancias); bomberos quedan como pool alternativo documentado.
    radius = 3.0  # ~4-5 min a 40 km/h, mismo criterio del pitch
    hosp_pool = [s for s in sites_all if s["type"] == "hospital"]
    sel2 = curate_sites(hosp_pool, zones_all, radius, n_sites)
    cases.append({
        "meta": make_meta(
            "caba",
            "Ciudad de Buenos Aires completa — caso grande",
            "un punto por radio censal (centroide), resolucion completa; %d zonas con poblacion > 0%s" % (len(zones_all), excl),
            "%d candidatos (hospitales de agudos/ninos con guardia), curados a %d por k-centro" % (len(hosp_pool), len(sel2)),
            "radio 3.0 km (~4-5 min a 40 km/h), mismo criterio del pitch",
        ),
        "radius_km": radius,
        "k_default": k,
        "zones": [{"id": z["id"], "label": z["label"], "x_km": z["x_km"],
                   "y_km": z["y_km"], "weight": z["weight"]} for z in zones_all],
        "sites": [{"id": s["id"], "name": s["name"], "type": s["type"],
                   "comuna": s["comuna"], "x_km": s["x_km"],
                   "y_km": s["y_km"]} for s in sel2],
    })

    os.makedirs(OUT_DIR, exist_ok=True)
    for case in cases:
        path = os.path.join(OUT_DIR, case["meta"]["id"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(case, f, ensure_ascii=False, indent=1)
        kb = os.path.getsize(path) / 1024
        print("%s: %d zonas, %d sitios, pob total %d -> %s (%.0f KB)"
              % (case["meta"]["id"], len(case["zones"]), len(case["sites"]),
                 sum(z["weight"] for z in case["zones"]), path, kb))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-descargar los archivos fuente")
    args = ap.parse_args()
    build_cases(force=args.force)
