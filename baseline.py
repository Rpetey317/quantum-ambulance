"""
Ubicacion de ambulancias con QAOA (Qiskit)
Hackathon Qollab x IonQ - tema Quantum Impact
Problema: elegir K bases entre N sitios candidatos para cubrir a la mayor
cantidad de poblacion dentro de un radio (tiempo de respuesta).
Se compara: greedy clasico, solucion exacta (fuerza bruta) y QAOA.
QAOA usa un mezclador XY y empieza en un estado de Dicke, asi que todas
las mediciones usan exactamente K ambulancias (no hace falta penalidad).
"""

import itertools, math
import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Statevector
from qiskit.primitives import StatevectorSampler

# ---------------- 1. Datos ----------------

# Zonas: (x km, y km, poblacion en miles). Reemplazar por datos reales.

ZONAS = [(1.78, 7.39, 63), (6.65, 7.93, 66), (4.61, 7.41, 164), (6.98, 8.69, 159), (7.44, 6.24, 245), (2.22, 9.49, 133), (2.72, 1.54, 227), (0.63, 2.21, 167), (5.30, 6.01, 76), (8.57, 6.31, 145), (7.45, 7.56, 191), (0.82, 7.34, 232), (4.00, 8.25, 150), (5.13, 7.23, 235), (4.78, 10.89, 62)]

# Sitios candidatos para bases (x km, y km)

SITIOS = [(4.63, 1.72), (3.37, 3.95), (2.28, 7.15), (10.65, 8.67), (3.67, 4.16), (8.42, 7.39), (6.36, 9.73), (10.90, 6.11)]

RADIO_KM = 3.0 # a 40 km/h, 3 km son unos 4-5 minutos de respuesta
K = 3 # ambulancias disponibles
N = len(SITIOS) # un qubit por sitio candidato
POB_TOTAL = sum(z[2] for z in ZONAS)

# ---------------- 2. Cobertura ----------------
CUBRE = [{z for z, (x, y, _) in enumerate(ZONAS) if math.dist((x, y), s) <= RADIO_KM} for s in SITIOS]
def poblacion_cubierta(sel):
	zonas = set().union(*[CUBRE[i] for i in sel]) if sel else set()
	return sum(ZONAS[z][2] for z in zonas)

# ---------------- 3. Lineas base clasicas ----------------
def greedy():
	"""Agrega en cada paso el sitio que mas poblacion nueva cubre."""
	sel = []
	for _ in range(K):
		mejor = max((i for i in range(N) if i not in sel), key=lambda i: poblacion_cubierta(sel + [i]))
		sel.append(mejor)
	return sorted(sel)

def exacta():
	"""Prueba todas las combinaciones (solo posible porque N es chico)."""
	return list(max(itertools.combinations(range(N), K), key=lambda s: poblacion_cubierta(list(s))))

# ---------------- 4. Funcion de costo cuadratica ----------------
# Minimizar -sum_i w_i x_i + sum_{i<j} o_ij x_i x_j
# w_i = poblacion que cubre el sitio i
# o_ij = poblacion que cubren i y j a la vez (para no contarla dos veces)

w = np.array([sum(ZONAS[z][2] for z in CUBRE[i]) for i in range(N)]) / POB_TOTAL
Q = np.diag(-w)

for i, j in itertools.combinations(range(N), 2):
	Q[i, j] = sum(ZONAS[z][2] for z in CUBRE[i] & CUBRE[j]) / POB_TOTAL

def costo(x):
	x = np.array(x)
	return float(x @ Q @ x)

ESTADOS = [[(k >> i) & 1 for i in range(N)] for k in range(2 ** N)]
COSTOS = np.array([costo(x) for x in ESTADOS])
PESO = np.array([sum(x) for x in ESTADOS])

# ---------------- 5. Circuito QAOA ----------------
P = 3 # capas
ESCALA = 5.0 # escala del costo dentro del circuito
def estado_dicke():
	"""Superposicion pareja de todas las formas de elegir K sitios."""
	v = (PESO == K).astype(float)
	return v / np.linalg.norm(v)

def circuito_qaoa(p=P):
	g, b = ParameterVector("g", p), ParameterVector("b", p)
	qc = QuantumCircuit(N)
	qc.initialize(estado_dicke())
	for capa in range(p):
		# Capa de costo: x_i = (1 - Z_i)/2 -> rotaciones RZ y RZZ
		for i in range(N):
			vecinos = sum(Q[min(i, j), max(i, j)] for j in range(N) if j != i)
			qc.rz(-g[capa] * ESCALA * (Q[i, i] + vecinos / 2), i)

		for i, j in itertools.combinations(range(N), 2):
			if Q[i, j] != 0:
				qc.rzz(g[capa] * ESCALA * Q[i, j] / 2, i, j)
		# Capa de mezcla XY en anillo: mueve una ambulancia de un sitio
		# a otro sin cambiar cuantas hay
		for inicio in (0, 1):
			for i in range(inicio, N, 2):
				j = (i + 1) % N
				qc.rxx(b[capa], i, j)
				qc.ryy(b[capa], i, j)
	return qc

ansatz = circuito_qaoa()

def energia(params):
	probs = Statevector(ansatz.assign_parameters(params)).probabilities()
	return float(probs @ COSTOS)

def optimizar(intentos=4, semilla=1):
	"""Optimiza los angulos en simulacion local (parte clasica del hibrido)."""
	rng = np.random.default_rng(semilla)
	mejor = None
	for t in range(intentos):
		if t == 0: # arranque tipo "recocido": gamma crece, beta baja
			x0 = np.concatenate([np.linspace(0.1, 1, P), np.linspace(0.5, 0.05, P)])
		else:
			x0 = rng.uniform(0, 1.5, 2 * P)
		r = minimize(energia, x0, method="COBYLA", options={"maxiter": 500})
		if mejor is None or r.fun < mejor.fun:
			mejor = r
	return mejor.x

def bits_a_sitios(bits):
# Qiskit ordena los bits al reves: el ultimo caracter es el qubit 0
	return [i for i in range(N) if bits[N - 1 - i] == "1"]

def muestrear(params, shots=4096):
	circ = ansatz.assign_parameters(params)
	circ.measure_all()
	# Un solo job: compatible con el limite de 1 job por ejecucion en IonQ
	res = StatevectorSampler().run([circ], shots=shots).result()[0]
	return res.data.meas.get_counts()

# ---------------- 6. Ejecutar y comparar ----------------
def pct(v):
	return f"{v} mil ({100 * v / POB_TOTAL:.1f}%)"

if __name__ == "__main__":
	g, e = greedy(), exacta()
	v_opt = poblacion_cubierta(e)
	print(f"Poblacion total: {POB_TOTAL} mil | {N} sitios | {K} ambulancias\n")
	print(f"Greedy : sitios {g} -> {pct(poblacion_cubierta(g))}")
	print(f"Exacta : sitios {e} -> {pct(v_opt)}")
	params = optimizar()
	counts = muestrear(params)
	shots = sum(counts.values())
	mejor = max(counts, key=lambda b: poblacion_cubierta(bits_a_sitios(b)))
	q = bits_a_sitios(mejor)
	print(f"QAOA : sitios {q} -> {pct(poblacion_cubierta(q))}\n")
	validas = sum(c for b, c in counts.items() if b.count("1") == K) / shots
	p_opt = sum(c for b, c in counts.items() if poblacion_cubierta(bits_a_sitios(b)) == v_opt) / shots
	n_opt = sum(1 for s in itertools.combinations(range(N), K) if poblacion_cubierta(list(s)) == v_opt)
	azar = n_opt / math.comb(N, K)
	print(f"Mediciones con exactamente {K} ambulancias: {100 * validas:.1f}%")
	print(f"Prob. de medir una solucion optima: {100 * p_opt:.1f}% (eligiendo al azar: {100 * azar:.1f}%, {p_opt / azar:.1f}x mejor)")
	print("\nTop 5 resultados medidos:")
	for b, c in sorted(counts.items(), key=lambda kv: -kv[1])[:5]:
		s = bits_a_sitios(b)
		print(f" sitios {s}: {100 * c / shots:.1f}% de las mediciones, cubre {pct(poblacion_cubierta(s))}")
