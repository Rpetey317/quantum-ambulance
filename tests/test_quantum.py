"""No remote jobs: circuit invariants, sample handling, and the backend adapter."""

import json
import math
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Operator, Statevector

from ambulance import bridge
from ambulance.core import (
    QUANTUM_SITE_CAP,
    load_case,
    prepare_case,
    solve_exact,
)
from ambulance.quantum import (
    IONQ_SITE_CAP,
    build_qaoa,
    decode_bitstring,
    optimize_angles,
    run_qaoa,
    summarize_counts,
)


class CountingSimulator(BasicSimulator):
    def __init__(self, fail=False):
        super().__init__()
        self.calls = 0
        self.fail = fail

    def run(self, circuit, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("unsupported backend example")
        return super().run(circuit, seed_simulator=17, **kwargs)


class QuantumTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.coverage = prepare_case(self.case)
        self.exact = solve_exact(self.coverage)

    def test_reversed_bit_order_and_stable_site_ids(self):
        self.assertEqual(decode_bitstring("00100110", 8), (1, 2, 5))
        self.assertEqual(decode_bitstring("0011 0100", 8), (2, 4, 5))
        for value in range(256):
            expected = tuple(i for i in range(8) if value & (1 << i))
            self.assertEqual(decode_bitstring(f"{value:08b}", 8), expected)
        for malformed in ("001", "00100x10", "0x26", None):
            with self.assertRaises(ValueError):
                decode_bitstring(malformed, 8)

    def test_dicke_and_xy_constraint_for_dynamic_even_odd_single_site_cases(self):
        for n, k in (
            (1, 1),
            (2, 1),
            (2, 2),
            (3, 1),
            (3, 2),
            (3, 3),
            (5, 2),
            (8, 3),
            (8, 8),
        ):
            with self.subTest(n=n, k=k):
                case = deepcopy(self.case)
                case["sites"] = case["sites"][:n]
                case["k"] = k
                model = build_qaoa(case, layers=2)
                self.assertEqual(model.circuit.num_qubits, n)
                self.assertEqual(np.count_nonzero(model.dicke), math.comb(n, k))
                self.assertAlmostEqual(float(np.linalg.norm(model.dicke)), 1)
                np.testing.assert_allclose(
                    model.dicke[model.weights == k] ** 2, 1 / math.comb(n, k)
                )
                state = Statevector(
                    model.circuit.assign_parameters(
                        model.bind([0.17, 0.43, -0.26, 0.31])
                    )
                )
                self.assertLess(
                    float(state.probabilities()[model.weights != k].sum()), 1e-20
                )
                self.assertNotIn("reset", model.circuit.decompose(reps=4).count_ops())
                self.assertNotIn(
                    "state_preparation", model.circuit.count_ops()
                )

    def test_edits_rebuild_coverage_cost_and_circuit_dimensions(self):
        before = build_qaoa(self.case, layers=1)
        edited = deepcopy(self.case)
        edited["sites"] = edited["sites"][:5]
        edited["sites"][2].update(x_km=100, y_km=100)
        edited.update(k=2, radius_km=1.5)
        after = build_qaoa(edited, layers=1)
        self.assertEqual(after.q.shape, (5, 5))
        self.assertEqual(len(after.costs), 32)
        self.assertEqual(np.count_nonzero(after.dicke), 10)
        self.assertEqual(after.coverage.covers[2], frozenset())
        self.assertNotEqual(after.coverage.fingerprint, before.coverage.fingerprint)
        self.assertEqual(before.circuit.num_qubits, 8)

    def test_parameter_mapping_and_hamiltonian_phase_are_correct(self):
        model = build_qaoa(self.case, layers=1)
        binding = model.bind([0.23, 0])
        self.assertEqual(binding[model.gamma[0]], 0.23)
        self.assertEqual(binding[model.beta[0]], 0)
        diagonal = np.diag(Operator(model.evolution.assign_parameters(binding)).data)
        expected = np.exp(-1j * 0.23 * 5 * model.costs)
        ratio = diagonal / expected
        np.testing.assert_allclose(ratio / ratio[0], np.ones(256), atol=1e-12)

    def test_local_tuning_state_and_submitted_state_are_equivalent(self):
        model = build_qaoa(self.case, layers=1)
        binding = model.bind([0.7, -0.2])
        local = Statevector(model.dicke).evolve(
            model.evolution.assign_parameters(binding)
        )
        submitted = Statevector(model.circuit.assign_parameters(binding))
        self.assertTrue(local.equiv(submitted))

    def test_wrong_weight_and_malformed_shots_never_win(self):
        result = summarize_counts(
            self.coverage, {"11111111": 500, "00100110": 2, "bad": 3}, self.exact
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected_site_indices"], [1, 2, 5])
        self.assertEqual(result["covered_weight"], 2086)
        self.assertEqual(result["valid_shots"], 2)
        self.assertEqual(result["invalid_shots"], 503)
        self.assertEqual(result["malformed_shots"], 3)
        self.assertAlmostEqual(result["optimal_probability"], 2 / 505)
        self.assertEqual(result["optimal_probability_given_valid"], 1)

    def test_all_invalid_and_empty_samples_have_explicit_states(self):
        result = summarize_counts(
            self.coverage, {"00000000": 5, "11111111": 5}, self.exact
        )
        self.assertEqual(result["status"], "no_valid_sample")
        self.assertEqual(result["selected_site_ids"], [])
        self.assertIsNone(result["covered_weight"])
        self.assertEqual(result["valid_shot_rate"], 0)
        self.assertEqual(result["optimal_probability"], 0)
        self.assertIsNone(result["optimal_probability_given_valid"])
        empty = summarize_counts(self.coverage, {})
        self.assertEqual(empty["status"], "no_valid_sample")
        self.assertIsNone(empty["valid_shot_rate"])

    def test_optimal_ties_probability_denominators_and_deterministic_sample_ties(self):
        counts = {"00100110": 7, "00110100": 3, "01100100": 10, "00000000": 5}
        result = summarize_counts(self.coverage, counts, self.exact)
        self.assertAlmostEqual(result["optimal_probability"], 0.4)
        self.assertAlmostEqual(result["optimal_probability_given_valid"], 0.5)
        self.assertAlmostEqual(result["uniform_optimal_probability"], 2 / 56)
        self.assertAlmostEqual(result["optimal_probability_amplification"], 11.2)
        for counts in ({"00110100": 2, "00100110": 2}, {"00100110": 2, "00110100": 2}):
            self.assertEqual(
                summarize_counts(self.coverage, counts)["selected_site_indices"],
                [1, 2, 5],
            )
        frequent_tie = summarize_counts(self.coverage, {"00100110": 1, "00110100": 2})
        self.assertEqual(frequent_tie["selected_site_indices"], [2, 4, 5])

    def test_best_sample_uses_true_coverage_even_when_quadratic_cost_favours_another(
        self,
    ):
        self.case.update(k=3, radius_km=1)
        self.case["zones"] = [
            {"id": "triple", "x_km": 0, "y_km": 0, "weight": 100},
            {"id": "single", "x_km": 10, "y_km": 0, "weight": 70},
        ]
        self.case["sites"] = [
            {"id": str(i), "x_km": x, "y_km": y}
            for i, (x, y) in enumerate(
                ((0, 0), (0.1, 0), (0, 0.1), (10, 0), (20, 0), (30, 0))
            )
        ]
        model = build_qaoa(self.case, layers=1)
        self.assertGreater(model.costs[7], model.costs[56])
        result = summarize_counts(model.coverage, {"000111": 1, "111000": 99})
        self.assertEqual(result["selected_site_indices"], [0, 1, 2])
        self.assertEqual(result["covered_weight"], 100)

    def test_no_optimum_probability_without_matching_exact_search(self):
        no_reference = summarize_counts(self.coverage, {"00100110": 10})
        unavailable = solve_exact(self.coverage, max_combinations=1)
        no_exact = summarize_counts(self.coverage, {"00100110": 10}, unavailable)
        for result in (no_reference, no_exact):
            self.assertIsNone(result["optimal_probability"])
            self.assertIsNone(result["uniform_optimal_probability"])
        for key, bad_value in (
            ("input_fingerprint", "stale"),
            ("case_revision", 2),
            ("method", "greedy"),
        ):
            stale = deepcopy(self.exact)
            stale[key] = bad_value
            with self.assertRaises(ValueError):
                summarize_counts(self.coverage, {}, stale)

    def test_backend_count_contract_rejects_probabilities_and_negative_counts(self):
        for counts in (
            {"00100110": 0.5},
            {"00100110": -1},
            {"00100110": True},
            {0: 1},
            [],
        ):
            with self.assertRaises(ValueError):
                summarize_counts(self.coverage, counts)

    def test_local_optimizer_is_bounded_and_returns_finite_explicit_angles(self):
        model = build_qaoa(self.case, layers=1)
        tuning = optimize_angles(model, restarts=1, maxiter=12, seed=3)
        self.assertEqual(len(tuning["gamma"]), 1)
        self.assertEqual(len(tuning["beta"]), 1)
        self.assertLessEqual(tuning["evaluations"], 12)
        self.assertTrue(np.all(np.isfinite(tuning["angles"])))

    def test_built_in_backend_one_job_valid_counts_and_distinct_timings(self):
        backend = CountingSimulator()
        with patch(
            "ambulance.quantum.optimize_angles", return_value={"angles": [0, 0]}
        ):
            result = run_qaoa(
                self.case, backend, shots=32, layers=1, exact_result=self.exact
            )
        self.assertEqual(result["status"], "ok", result["message"])
        self.assertEqual(backend.calls, 1)
        self.assertEqual(result["backend_run_calls"], 1)
        self.assertEqual(result["shots"], 32)
        self.assertEqual(result["requested_shots"], 32)
        self.assertEqual(result["valid_shot_rate"], 1)
        self.assertEqual(result["input_fingerprint"], self.coverage.fingerprint)
        for component in (
            "coverage_s",
            "quantum_prepare_s",
            "local_optimization_s",
            "transpile_s",
            "backend_job_s",
        ):
            self.assertIsNotNone(result["timings"][component])
            self.assertGreaterEqual(result["timings"][component], 0)
        self.assertNotIn("state_preparation", result["circuit"]["compiled_operations"])
        self.assertNotIn("reset", result["circuit"]["compiled_operations"])
        json.dumps(result, allow_nan=False)

    def test_backend_failure_has_no_retry_and_transpilation_failure_submits_nothing(
        self,
    ):
        backend = CountingSimulator(fail=True)
        with patch(
            "ambulance.quantum.optimize_angles", return_value={"angles": [0, 0]}
        ):
            result = run_qaoa(self.case, backend, shots=8, layers=1)
        self.assertEqual(backend.calls, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_stage"], "backend_job")
        self.assertIn("unsupported backend", result["message"])
        self.assertIsNotNone(result["timings"]["backend_job_s"])
        backend = CountingSimulator()
        with (
            patch("ambulance.quantum.optimize_angles", return_value={"angles": [0, 0]}),
            patch(
                "ambulance.quantum.transpile",
                side_effect=ValueError("unsupported gates"),
            ),
        ):
            result = run_qaoa(self.case, backend, shots=8, layers=1)
        self.assertEqual(backend.calls, 0)
        self.assertEqual(result["backend_run_calls"], 0)
        self.assertEqual(result["error_stage"], "transpilation")

    def test_site_and_run_limits_fail_before_a_backend_job(self):
        oversized = deepcopy(self.case)
        for i in range(QUANTUM_SITE_CAP - len(oversized["sites"]) + 1):
            oversized["sites"].append(
                {"id": f"extra-{i}", "x_km": 30 + i, "y_km": 30}
            )
        backend = CountingSimulator()
        result = run_qaoa(oversized, backend)
        self.assertEqual(result["status"], "failed")
        self.assertIn(f"{QUANTUM_SITE_CAP} candidate sites", result["message"])
        for settings in (
            {"shots": 0},
            {"shots": True},
            {"layers": 0},
            {"restarts": 5},
            {"maxiter": 2},
        ):
            result = run_qaoa(self.case, backend, **settings)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error_stage"], "validation")
        self.assertEqual(backend.calls, 0)

    def test_adapter_transports_no_valid_sample_without_faking_a_selection(self):
        backend = CountingSimulator()
        job = SimpleNamespace(
            result=lambda: SimpleNamespace(get_counts=lambda: {"00000000": 8})
        )
        with (
            patch("ambulance.quantum.optimize_angles", return_value={"angles": [0, 0]}),
            patch.object(backend, "run", return_value=job) as backend_run,
        ):
            result = run_qaoa(
                self.case, backend, shots=8, layers=1, exact_result=self.exact
            )
        backend_run.assert_called_once()
        self.assertEqual(result["status"], "no_valid_sample")
        self.assertEqual(result["requested_shots"], 8)
        self.assertEqual(result["invalid_shots"], 8)
        self.assertEqual(result["selected_site_ids"], [])
        self.assertIsNone(result["covered_weight"])
        self.assertEqual(result["optimal_probability"], 0)
        self.assertIsNotNone(result["timings"]["backend_job_s"])

    def test_ionq_simulator_shot_policy_and_hardware_guard(self):
        class IonQStub:
            name = "ionq_simulator"

            def configuration(self):
                return type("Config", (), {"simulator": True})()

            def run(self, *args, **kwargs):
                raise AssertionError("guard should run before submission")

        result = run_qaoa(self.case, IonQStub(), shots=129)
        self.assertEqual(result["error_stage"], "validation")
        self.assertIn("application policy", result["message"])
        backend = IonQStub()
        backend.name = "ionq_qpu"
        backend.configuration = lambda: type("Config", (), {"simulator": False})()
        result = run_qaoa(self.case, backend, shots=8)
        self.assertEqual(result["backend_run_calls"], 0)
        self.assertIn("paid hardware", result["message"])
        oversized = deepcopy(self.case)
        for i in range(IONQ_SITE_CAP - len(oversized["sites"]) + 1):
            oversized["sites"].append(
                {"id": f"extra-{i}", "x_km": 30 + i, "y_km": 30}
            )
        result = run_qaoa(oversized, IonQStub(), shots=8)
        self.assertEqual(result["error_stage"], "validation")
        self.assertIn(f"{IONQ_SITE_CAP} candidate sites", result["message"])

    def test_quantum_bridge_keeps_every_comparison_on_the_same_revision(self):
        self.case["k"] = 1
        self.case["sites"] = self.case["sites"][:3]
        self.case["meta"]["revision"] = "map-edit-1"
        with patch(
            "ambulance.quantum.optimize_angles", return_value={"angles": [0, 0]}
        ):
            comparison = json.loads(
                bridge.run_quantum(
                    json.dumps(self.case), CountingSimulator(), shots=8, layers=1
                )
            )
        for method in ("greedy", "exact", "qaoa"):
            result = comparison[method]
            self.assertEqual(
                result["input_fingerprint"], comparison["input_fingerprint"]
            )
            self.assertEqual(result["case_revision"], "map-edit-1")
            self.assertEqual(len(result["selected_site_ids"]), 1)


if __name__ == "__main__":
    unittest.main()
