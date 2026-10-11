"""Regresiones deterministas del prototipo original (baseline.py).

Fijan los valores del ejemplo de 8 sitios reportados en Idea.pdf/README.md y
los invariantes del circuito QAOA (exactamente K sitios, orden de bits de
Qiskit). Ningun test depende de una corrida estocastica ni de un backend remoto.
"""

import itertools
import unittest

import numpy as np
from qiskit.quantum_info import Statevector

import baseline as b


class OriginalExampleTests(unittest.TestCase):
    """Datos y lineas base clasicas del ejemplo sintetico de 8 sitios."""

    def test_problem_size(self):
        self.assertEqual(b.N, 8)
        self.assertEqual(b.K, 3)
        self.assertEqual(len(b.ZONAS), 15)
        self.assertEqual(b.RADIO_KM, 3.0)
        self.assertEqual(b.POB_TOTAL, 2315)

    def test_empty_selection_covers_nothing(self):
        self.assertEqual(b.poblacion_cubierta([]), 0)

    def test_overlap_is_counted_once(self):
        # La cobertura es la union de zonas: nunca supera la suma por sitio.
        for sel in itertools.combinations(range(b.N), b.K):
            union = b.poblacion_cubierta(list(sel))
            suma = sum(b.poblacion_cubierta([i]) for i in sel)
            self.assertLessEqual(union, suma)
            self.assertLessEqual(union, b.POB_TOTAL)

    def test_greedy_matches_reported_result(self):
        g = b.greedy()
        self.assertEqual(g, [2, 5, 6])
        self.assertEqual(b.poblacion_cubierta(g), 1845)

    def test_exact_optimum_and_ties(self):
        e = b.exacta()
        v_opt = b.poblacion_cubierta(e)
        self.assertEqual(v_opt, 2086)
        optimos = {
            s for s in itertools.combinations(range(b.N), b.K)
            if b.poblacion_cubierta(list(s)) == v_opt
        }
        # Idea.pdf reporta dos optimos empatados.
        self.assertEqual(optimos, {(1, 2, 5), (2, 4, 5)})
        self.assertIn(tuple(e), optimos)

    def test_exact_is_never_worse_than_greedy(self):
        self.assertGreaterEqual(
            b.poblacion_cubierta(b.exacta()), b.poblacion_cubierta(b.greedy())
        )


class QuadraticApproximationTests(unittest.TestCase):
    """El costo QAOA es una aproximacion por pares, no la cobertura real."""

    def test_pairwise_cost_is_lower_bound_of_true_coverage(self):
        # Desigualdad de Bonferroni: sum w_i - sum o_ij <= |union|.
        for sel in itertools.combinations(range(b.N), b.K):
            x = [1 if i in sel else 0 for i in range(b.N)]
            aprox = -b.costo(x) * b.POB_TOTAL
            self.assertLessEqual(aprox, b.poblacion_cubierta(list(sel)) + 1e-9)

    def test_approximation_is_not_exact_for_this_example(self):
        # Documenta por que la seleccion final se elige por cobertura real.
        diffs = []
        for sel in itertools.combinations(range(b.N), b.K):
            x = [1 if i in sel else 0 for i in range(b.N)]
            diffs.append(b.poblacion_cubierta(list(sel)) + b.costo(x) * b.POB_TOTAL)
        self.assertTrue(any(d > 1e-6 for d in diffs))


class BitOrderTests(unittest.TestCase):
    """Qiskit invierte los bits: el ultimo caracter es el qubit 0."""

    def test_known_bitstrings(self):
        self.assertEqual(b.bits_a_sitios("00000001"), [0])
        self.assertEqual(b.bits_a_sitios("10000000"), [7])
        self.assertEqual(b.bits_a_sitios("00100110"), [1, 2, 5])
        self.assertEqual(b.bits_a_sitios("00000000"), [])

    def test_matches_statevector_index_order(self):
        # ESTADOS[k][i] es el qubit i del indice k; format(k) es la cadena Qiskit.
        for k in range(2 ** b.N):
            esperado = [i for i, bit in enumerate(b.ESTADOS[k]) if bit]
            self.assertEqual(b.bits_a_sitios(format(k, f"0{b.N}b")), esperado)


class ExactlyKInvariantTests(unittest.TestCase):
    """Estado de Dicke + mezclador XY: toda la probabilidad queda en peso K."""

    def test_dicke_state(self):
        v = b.estado_dicke()
        self.assertAlmostEqual(float(np.linalg.norm(v)), 1.0)
        self.assertTrue(np.all(v[b.PESO != b.K] == 0))
        soporte = v[b.PESO == b.K]
        self.assertEqual(len(soporte), 56)  # C(8, 3)
        self.assertTrue(np.allclose(soporte, soporte[0]))

    def test_ansatz_preserves_hamming_weight(self):
        rng = np.random.default_rng(0)
        for _ in range(5):
            params = rng.uniform(-np.pi, np.pi, 2 * b.P)
            probs = Statevector(b.ansatz.assign_parameters(params)).probabilities()
            self.assertAlmostEqual(float(probs[b.PESO != b.K].sum()), 0.0, places=9)
            self.assertAlmostEqual(float(probs.sum()), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
