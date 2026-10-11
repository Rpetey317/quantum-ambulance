"""Deterministic regressions for input validation, true coverage, and contracts."""

import ast
import json
import unittest
from copy import deepcopy
from pathlib import Path

from ambulance import bridge
from ambulance.core import (
    CaseValidationError,
    evaluate_case,
    load_case,
    prepare_case,
    solve_exact,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case()

    def test_fixture_matches_original_data_without_importing_quantum_globals(self):
        tree = ast.parse(Path("baseline.py").read_text(encoding="utf-8"))
        original = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("ZONAS", "SITIOS", "RADIO_KM", "K")
        }
        self.assertEqual(
            [(z["x_km"], z["y_km"], z["weight"]) for z in self.case["zones"]],
            original["ZONAS"],
        )
        self.assertEqual(
            [(s["x_km"], s["y_km"]) for s in self.case["sites"]], original["SITIOS"]
        )
        self.assertEqual(self.case["radius_km"], original["RADIO_KM"])
        self.assertEqual(self.case["k_default"], original["K"])

    def test_original_solutions_and_all_tied_optima(self):
        comparison = evaluate_case(self.case)
        self.assertEqual(comparison["greedy"]["selected_site_indices"], [2, 5, 6])
        self.assertEqual(comparison["greedy"]["covered_weight"], 1845)
        self.assertEqual(comparison["exact"]["covered_weight"], 2086)
        self.assertEqual(comparison["exact"]["total_weight"], 2315)
        self.assertEqual(
            comparison["exact"]["optimal_selections"], [[1, 2, 5], [2, 4, 5]]
        )
        self.assertEqual(comparison["exact"]["n_optimal_solutions"], 2)
        self.assertEqual(comparison["exact"]["selected_site_ids"], ["1", "2", "5"])

    def test_true_union_counts_triple_overlap_once(self):
        model = prepare_case(self.case)
        self.assertEqual(model.covered_weight([0, 1, 4]), 303)
        covered_ids = model.covered_zones([0, 1, 4])
        self.assertEqual(len(covered_ids), 2)
        self.assertEqual(model.covered_weight([]), 0)

    def test_radius_boundary_is_inclusive(self):
        self.case["zones"] = [{"id": "a", "x_km": 0, "y_km": 0, "weight": 10}]
        self.case["sites"] = [{"id": "boundary", "x_km": 3, "y_km": 4}]
        self.case.update(radius_km=5, k=1)
        self.assertEqual(evaluate_case(self.case)["greedy"]["covered_weight"], 10)
        self.case["radius_km"] = 4.999
        self.assertEqual(evaluate_case(self.case)["exact"]["covered_weight"], 0)

    def test_large_finite_weights_keep_percentages_serializable(self):
        self.case["zones"] = [{"id": "a", "x_km": 0, "y_km": 0, "weight": 1e307}]
        self.case["sites"] = [{"id": "a", "x_km": 0, "y_km": 0}]
        self.case["k"] = 1
        result = evaluate_case(self.case)
        self.assertEqual(result["exact"]["coverage_pct"], 100)
        json.dumps(result, allow_nan=False)

    def test_dynamic_edits_recompute_and_fingerprint_changes(self):
        before = evaluate_case(self.case)
        edited = deepcopy(self.case)
        edited["sites"][2].update(x_km=100, y_km=100)
        after = evaluate_case(edited)
        self.assertNotEqual(before["input_fingerprint"], after["input_fingerprint"])
        self.assertNotEqual(
            before["greedy"]["selected_site_indices"],
            after["greedy"]["selected_site_indices"],
        )
        self.assertNotEqual(
            before["exact"]["covered_weight"], after["exact"]["covered_weight"]
        )
        edited["k"] = 1
        changed_k = evaluate_case(edited)
        self.assertNotEqual(after["input_fingerprint"], changed_k["input_fingerprint"])
        self.assertEqual(len(changed_k["exact"]["selected_site_ids"]), 1)
        self.assertEqual(self.case["sites"][2]["x_km"], 2.28)

    def test_every_input_component_and_order_participates_in_identity(self):
        before = prepare_case(self.case).fingerprint
        changes = [
            lambda c: c.update(k=2),
            lambda c: c.update(radius_km=2),
            lambda c: c["zones"][0].update(weight=64),
            lambda c: c["zones"][0].update(x_km=1.8),
            lambda c: c["sites"].reverse(),
            lambda c: c["meta"].update(weight_units="people"),
        ]
        for change in changes:
            case = deepcopy(self.case)
            change(case)
            self.assertNotEqual(prepare_case(case).fingerprint, before)

    def test_json_identity_stable_and_inputs_not_mutated(self):
        saved = deepcopy(self.case)
        as_json = json.dumps(self.case, sort_keys=True)
        self.assertEqual(
            prepare_case(self.case).fingerprint, prepare_case(as_json).fingerprint
        )
        evaluate_case(self.case)
        self.assertEqual(saved, self.case)
        self.case["meta"]["revision"] = "edited-2"
        result = evaluate_case(self.case)
        self.assertEqual(result["exact"]["case_revision"], "edited-2")

    def test_exact_bounds_do_not_report_a_fake_optimum(self):
        for limits in ({"max_combinations": 55}, {"max_zone_work": 839}):
            result = solve_exact(prepare_case(self.case), **limits)
            self.assertEqual(result["status"], "unavailable")
            self.assertIsNone(result["covered_weight"])
            self.assertIsNone(result["n_optimal_solutions"])
            self.assertIsNone(result["timings"]["solve_s"])
        self.assertEqual(
            solve_exact(
                prepare_case(self.case), max_combinations=56, max_zone_work=840
            )["status"],
            "ok",
        )

    def test_ties_follow_current_input_order_and_keep_stable_ids(self):
        self.case["zones"] = [{"id": "a", "x_km": 0, "y_km": 0, "weight": 1}]
        self.case["sites"] = [
            {"id": "z-first", "x_km": 1, "y_km": 0},
            {"id": "a-second", "x_km": -1, "y_km": 0},
        ]
        self.case["k"] = 1
        result = evaluate_case(self.case)
        self.assertEqual(result["greedy"]["selected_site_ids"], ["z-first"])
        self.assertEqual(result["exact"]["selected_site_ids"], ["z-first"])
        self.assertEqual(result["exact"]["n_optimal_solutions"], 2)

    def test_empty_no_coverage_and_coincident_zones(self):
        self.case["zones"] = [
            {"id": "a", "x_km": 100, "y_km": 100, "weight": 5},
            {"id": "b", "x_km": 100, "y_km": 100, "weight": 7},
        ]
        result = evaluate_case(self.case)
        self.assertEqual(result["exact"]["covered_weight"], 0)
        self.assertEqual(result["exact"]["total_weight"], 12)
        self.assertEqual(result["exact"]["n_optimal_solutions"], 56)

    def test_invalid_k_radius_and_schema(self):
        for field, values in (
            ("k", [0, 9, 1.5, True, None]),
            ("radius_km", [0, -1, True, float("nan"), float("inf"), "3"]),
            ("schema_version", [True, 2, "1"]),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    case = deepcopy(self.case)
                    case[field] = value
                    with self.assertRaises(CaseValidationError):
                        prepare_case(case)

    def test_invalid_records_metadata_and_geographic_units(self):
        changes = [
            lambda c: c.update(zones=[]),
            lambda c: c.update(sites=[]),
            lambda c: c["zones"][0].update(weight=0),
            lambda c: c["zones"][0].update(weight=-1),
            lambda c: c["zones"][0].update(weight=True),
            lambda c: c["zones"][0].update(x_km=float("nan")),
            lambda c: c["sites"][0].update(y_km=float("inf")),
            lambda c: c["sites"][0].update(id=c["sites"][1]["id"]),
            lambda c: c["zones"][0].update(id=c["zones"][1]["id"]),
            lambda c: c["meta"].update(revision=True),
            lambda c: c["meta"].update(sources=[]),
            lambda c: c["meta"].update(coordinate_units="degrees"),
            lambda c: c["meta"].update(crs="EPSG:4326"),
        ]
        for change in changes:
            case = deepcopy(self.case)
            change(case)
            with self.subTest(case=case), self.assertRaises(CaseValidationError):
                prepare_case(case)
        for case in ({}, None, [], "not JSON"):
            with self.assertRaises(CaseValidationError):
                prepare_case(case)

    def test_close_candidate_sites_rejected_and_bad_selections_rejected(self):
        self.case["sites"][0].update(
            x_km=self.case["sites"][1]["x_km"] + 0.0001,
            y_km=self.case["sites"][1]["y_km"],
        )
        with self.assertRaises(CaseValidationError):
            prepare_case(self.case)
        model = prepare_case(load_case())
        for selected in ([0, 0], [-1], [8], [True], [1.0]):
            with self.assertRaises(ValueError):
                model.covered_weight(selected)

    def test_bridge_returns_serializable_comparison_and_loads_fixture(self):
        result = json.loads(bridge.preview(bridge.synthetic_case()))
        self.assertEqual(result["exact"]["covered_weight"], 2086)
        self.assertEqual(
            result["input_fingerprint"], result["greedy"]["input_fingerprint"]
        )
        self.assertEqual(
            result["input_fingerprint"], result["exact"]["input_fingerprint"]
        )


if __name__ == "__main__":
    unittest.main()
