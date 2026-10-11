"""Regresiones de los casos reales de data/cases/ (solo stdlib, sin Qiskit).

Reutiliza tools/validate_cases.py para el contrato y agrega valores fijos de
poblacion, cobertura greedy/exacta y unidades, para detectar si una
regeneracion de los datos cambia el caso que muestra la demo.
"""

import contextlib
import importlib.util
import io
import itertools
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"

_spec = importlib.util.spec_from_file_location(
    "validate_cases", ROOT / "tools" / "validate_cases.py"
)
validate_cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_cases)

# Valores observados en la revision 1 de cada caso (ver data/README.md y
# docs/TESTING.md). Si una regeneracion los cambia a proposito, actualizar aca.
EXPECTED = {
    "caba-comuna4": {
        "zones": 252, "sites": 8, "k": 3, "radius_km": 1.8,
        "total": 218245, "greedy": 176818, "exact": 185708,
    },
    "caba": {
        "zones": 3552, "sites": 8, "k": 3, "radius_km": 3.0,
        "total": 2890151, "greedy": 1682455, "exact": 1682455,
    },
}


def load(case_id):
    with open(CASES / f"{case_id}.json", encoding="utf-8") as f:
        return json.load(f)


def coverage_sets(case):
    zones, r = case["zones"], case["radius_km"]
    return [validate_cases.coverage(zones, s, r) for s in case["sites"]]


def covered(case, cubre, sel):
    ids = set().union(*[cubre[i] for i in sel]) if sel else set()
    return validate_cases.union_weight(case["zones"], ids)


def greedy(case, cubre, k):
    sel = []
    for _ in range(k):
        mejor = max((i for i in range(len(cubre)) if i not in sel),
                    key=lambda i: covered(case, cubre, sel + [i]))
        sel.append(mejor)
    return sel


class CaseContractTests(unittest.TestCase):

    def test_every_case_passes_validator(self):
        paths = sorted(CASES.glob("*.json"))
        self.assertTrue(paths, "no hay casos en data/cases/")
        for path in paths:
            with self.subTest(case=path.name):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    errors = validate_cases.validate(str(path))
                self.assertEqual(errors, [], out.getvalue())

    def test_expected_cases_are_present(self):
        for case_id in EXPECTED:
            self.assertTrue((CASES / f"{case_id}.json").is_file(), case_id)


class CaseRegressionTests(unittest.TestCase):

    def test_sizes_and_parameters(self):
        for case_id, exp in EXPECTED.items():
            with self.subTest(case=case_id):
                case = load(case_id)
                self.assertEqual(case["meta"]["id"], case_id)
                self.assertEqual(len(case["zones"]), exp["zones"])
                self.assertEqual(len(case["sites"]), exp["sites"])
                self.assertEqual(case["k_default"], exp["k"])
                self.assertEqual(case["radius_km"], exp["radius_km"])

    def test_population_totals(self):
        for case_id, exp in EXPECTED.items():
            with self.subTest(case=case_id):
                case = load(case_id)
                self.assertEqual(sum(z["weight"] for z in case["zones"]), exp["total"])

    def test_greedy_and_exact_coverage(self):
        for case_id, exp in EXPECTED.items():
            with self.subTest(case=case_id):
                case = load(case_id)
                cubre = coverage_sets(case)
                k = case["k_default"]
                g = covered(case, cubre, greedy(case, cubre, k))
                e = max(covered(case, cubre, list(s))
                        for s in itertools.combinations(range(len(cubre)), k))
                self.assertEqual(g, exp["greedy"])
                self.assertEqual(e, exp["exact"])
                self.assertGreaterEqual(e, g)

    def test_comuna4_keeps_a_greedy_vs_exact_gap(self):
        # El caso compacto existe para mostrar una brecha entre metodos.
        exp = EXPECTED["caba-comuna4"]
        self.assertGreater(exp["exact"], exp["greedy"])


def exact(case, cubre, k):
    return max(covered(case, cubre, list(s))
               for s in itertools.combinations(range(len(cubre)), k))


class ValidatorRejectsBadDataTests(unittest.TestCase):
    """El validador tiene que fallar con datos rotos, no solo pasar los buenos."""

    def assert_rejected(self, mutate):
        case = load("caba-comuna4")
        mutate(case)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                errors = validate_cases.validate(str(path))
        self.assertTrue(errors, "el validador acepto un caso invalido")

    def test_zero_or_negative_population(self):
        for weight in (0, -5):
            with self.subTest(weight=weight):
                self.assert_rejected(lambda c: c["zones"][0].update(weight=weight))

    def test_duplicate_zone_id(self):
        self.assert_rejected(
            lambda c: c["zones"][1].update(id=c["zones"][0]["id"]))

    def test_no_sites(self):
        self.assert_rejected(lambda c: c.update(sites=[]))

    def test_k_out_of_range(self):
        for k in (0, 9):
            with self.subTest(k=k):
                self.assert_rejected(lambda c: c.update(k_default=k))

    def test_non_positive_radius(self):
        for r in (0, -1.0):
            with self.subTest(radius=r):
                self.assert_rejected(lambda c: c.update(radius_km=r))

    def test_coincident_sites(self):
        def mover(c):
            c["sites"][1].update(x_km=c["sites"][0]["x_km"], y_km=c["sites"][0]["y_km"])
        self.assert_rejected(mover)

    def test_missing_provenance(self):
        self.assert_rejected(lambda c: c["meta"].pop("sources"))


class ChangingRadiusAndKTests(unittest.TestCase):
    """Reglas de sentido comun al editar K o el radio sobre datos reales."""

    def setUp(self):
        self.case = load("caba-comuna4")

    def test_larger_radius_never_covers_less(self):
        anterior_sets, anterior_opt = None, 0
        for r in (0.5, 1.0, 1.8, 3.0, 5.0):
            with self.subTest(radius_km=r):
                case = dict(self.case, radius_km=r)
                cubre = coverage_sets(case)
                if anterior_sets is not None:
                    for antes, ahora in zip(anterior_sets, cubre):
                        self.assertLessEqual(antes, ahora)  # subconjunto
                opt = exact(case, cubre, 3)
                self.assertGreaterEqual(opt, anterior_opt)
                anterior_sets, anterior_opt = cubre, opt

    def test_more_ambulances_never_cover_less(self):
        cubre = coverage_sets(self.case)
        anterior = 0
        for k in range(1, len(cubre) + 1):
            with self.subTest(K=k):
                opt = exact(self.case, cubre, k)
                self.assertGreaterEqual(opt, anterior)
                self.assertGreaterEqual(opt, covered(self.case, cubre, greedy(self.case, cubre, k)))
                anterior = opt

    def test_single_ambulance_greedy_equals_exact(self):
        cubre = coverage_sets(self.case)
        self.assertEqual(covered(self.case, cubre, greedy(self.case, cubre, 1)),
                         exact(self.case, cubre, 1))

    def test_all_sites_reach_maximum_coverage(self):
        cubre = coverage_sets(self.case)
        todos = list(range(len(cubre)))
        self.assertEqual(exact(self.case, cubre, len(cubre)),
                         covered(self.case, cubre, todos))


class CaseUnitsTests(unittest.TestCase):
    """Las coordenadas deben ser km proyectados (EPSG:9498), nunca lon/lat."""

    def test_projected_crs_declared(self):
        for case_id in EXPECTED:
            with self.subTest(case=case_id):
                meta = load(case_id)["meta"]
                self.assertIn("EPSG:9498", meta["crs"])
                self.assertTrue(meta["coordinate_units"].startswith("km"))

    def test_city_extent_is_plausible_in_km(self):
        # CABA mide ~20 km de lado; lon/lat daria valores negativos y spans < 1.
        zones = load("caba")["zones"]
        xs = [z["x_km"] for z in zones]
        ys = [z["y_km"] for z in zones]
        for span in (max(xs) - min(xs), max(ys) - min(ys)):
            self.assertTrue(10 <= span <= 30, span)
        self.assertTrue(all(v > 0 for v in xs + ys))

    def test_real_sites_are_useful_and_inside_study_area(self):
        # El validador solo advierte esto; para los casos CABA es obligatorio.
        for case_id in EXPECTED:
            with self.subTest(case=case_id):
                case = load(case_id)
                xs = [z["x_km"] for z in case["zones"]]
                ys = [z["y_km"] for z in case["zones"]]
                for s, cubre in zip(case["sites"], coverage_sets(case)):
                    self.assertTrue(cubre, f"{s['id']} no cubre ninguna zona")
                    self.assertTrue(min(xs) - 2 <= s["x_km"] <= max(xs) + 2, s["id"])
                    self.assertTrue(min(ys) - 2 <= s["y_km"] <= max(ys) + 2, s["id"])

    def test_comuna4_lies_inside_city(self):
        city = load("caba")["zones"]
        bx = (min(z["x_km"] for z in city), max(z["x_km"] for z in city))
        by = (min(z["y_km"] for z in city), max(z["y_km"] for z in city))
        for z in load("caba-comuna4")["zones"]:
            self.assertTrue(bx[0] <= z["x_km"] <= bx[1] and by[0] <= z["y_km"] <= by[1])
            self.assertTrue(math.isfinite(z["x_km"]) and math.isfinite(z["y_km"]))

    def test_generated_cases_keep_full_provenance(self):
        # Campos que agrega tools/build_cases.py y exige la atribucion GCBA.
        for case_id in EXPECTED:
            with self.subTest(case=case_id):
                meta = load(case_id)["meta"]
                for key in ("generator", "generated_at_utc", "weight_source",
                            "site_selection"):
                    self.assertTrue(meta.get(key), key)
                for s in meta["sources"]:
                    self.assertTrue(s.get("key"))
                    self.assertTrue(s.get("dataset_page"))

    def test_licenses_and_sources_recorded(self):
        for case_id in EXPECTED:
            with self.subTest(case=case_id):
                meta = load(case_id)["meta"]
                self.assertTrue(meta["sources"])
                for s in meta["sources"]:
                    self.assertTrue(s["license"])
                    self.assertTrue(s["url"])


if __name__ == "__main__":
    unittest.main()
