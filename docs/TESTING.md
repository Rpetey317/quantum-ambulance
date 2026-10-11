# Testing (issue #8, versión básica)

Pruebas locales deterministas para el prototipo y los casos de datos. Ningún
test usa un backend remoto, credenciales de proveedores ni jobs pagos.

## Cómo correr

```bash
python -m pip install qiskit==2.5.2 numpy scipy
python -m unittest discover -s tests -v   # suite completa
python tools/validate_cases.py            # contrato de data/cases/*.json
python baseline.py                        # regresión del prototipo original
```

Solo datos (no requiere Qiskit): `python -m unittest tests.test_cases_data -v`.

Con `uv`, sin tocar el entorno:

```bash
uv run --no-project --with qiskit==2.5.2 --with numpy --with scipy python -m unittest discover -s tests -v
```

CI (`.github/workflows/tests.yml`) corre lo mismo en cada PR y push a `main`,
en pasos separados para distinguir el tipo de falla:

| Paso | Qué detecta |
| --- | --- |
| Data | Contrato, totales de población, cobertura greedy/exacta y unidades de los casos CABA |
| Unit tests | Regresiones del modelo (`baseline.py`) y de todo `tests/` |
| Baseline regression | Que `python baseline.py` corra y mantenga los resultados deterministas |

## Qué cubre

`tests/test_baseline.py` (prototipo original, 8 sitios):

- Población total 2315, greedy `[2, 5, 6]` → 1845 y óptimo exacto 2086, con
  los dos óptimos empatados `[1, 2, 5]` y `[2, 4, 5]`.
- Selección vacía, superposición contada una sola vez y exacto ≥ greedy.
- Cambiar K (1 a 8): se eligen exactamente K sitios, más ambulancias nunca
  cubren menos, con K=1 greedy y exacto coinciden, y con K=8 se alcanza la
  cobertura máxima.
- El costo QAOA por pares es una cota inferior de la cobertura real y no es
  exacto en este ejemplo, por eso la selección final usa cobertura real.
- Orden de bits de Qiskit: `bits_a_sitios` invertido y consistente con el
  orden del statevector.
- Invariante de exactamente K: el estado de Dicke tiene soporte en las 56
  combinaciones y el ansatz no deja probabilidad fuera de peso K para
  parámetros aleatorios (statevector sin ruido).

`tests/test_cases_data.py` (solo stdlib):

- Todos los casos pasan `tools/validate_cases.py`.
- Valores fijos de la revisión 1 de cada caso:

| Caso | Zonas | Sitios | K | Radio | Población | Greedy | Exacto |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `caba-comuna4` | 252 | 8 | 3 | 1.8 km | 218,245 | 176,818 (81.0%) | 185,708 (85.1%) |
| `caba` | 3,552 | 8 | 3 | 3.0 km | 2,890,151 | 1,682,455 (58.2%) | 1,682,455 (58.2%) |

- El validador **rechaza** datos rotos: población 0 o negativa, ID de zona
  repetido, sin sitios, K fuera de rango, radio ≤ 0, sitio fuera de la ciudad
  y falta de procedencia.
- Cambiar radio y K sobre Comuna 4: un radio mayor nunca cubre menos (cada
  sitio cubre un superconjunto de zonas), más ambulancias nunca cubren menos,
  K=1 greedy = exacto y K=8 alcanza el máximo.
- CRS EPSG:9498 declarado, coordenadas en km plausibles (no lon/lat), la
  Comuna 4 cae dentro de la ciudad, y fuentes con licencia y URL.

Si una regeneración de datos cambia estos valores a propósito, actualizar
`EXPECTED` en `tests/test_cases_data.py` y esta tabla.

## Mediciones (2026-10-11, Linux, Python 3.13.7, Qiskit 2.5.2)

| Medición | Valor |
| --- | --- |
| `caba-comuna4.json` | 31,981 bytes |
| `caba.json` | 400,968 bytes |
| Límite de tamaño de asset (`validate_cases.py`) | 1024 KB por archivo |
| Suite completa (37 tests) | ~0.3 s |
| `python baseline.py` | ~22 s |

El límite de 1024 KB es provisional: todavía no se midió el límite real de
tamaño de proyecto en Qollab (issue #1). Son mediciones de una sola máquina,
no garantías de rendimiento en el navegador.

## Checklist manual de Qollab (pendiente)

No se automatiza: el backend lo elige quien presiona *Run* en Qollab. Para cada
corrida, registrar:

- [ ] Backend seleccionado (nombre exacto en *Select QPU*) y si es local o remoto.
- [ ] Caso y revisión (`meta.id`, `meta.revision`), con los sitios o K editados si los hay.
- [ ] Shots pedidos. En IonQ empezar con 64 y usar una sola corrida (1 job por run).
- [ ] Porcentaje de mediciones con exactamente K sitios (muestras válidas).
- [ ] Cobertura real de la mejor muestra válida, comparada con greedy y exacto del mismo caso.
- [ ] Errores textuales, si los hubo.

No usar QPUs pagas sin aprobación del equipo. Estas corridas miden calidad de
solución y ruido por backend, no una ventaja de velocidad cuántica.

## Pendiente para la versión completa de #8

- Tests del núcleo y del adaptador QAOA (`ambulance/`), que ya existen en la
  rama `feat/core-quantum-contract` y se suman a esta suite al mergearla.
- Muestras inválidas o todas inválidas: requieren el adaptador de esa rama.
- Tamaños de geometría simplificada y render del mapa, cuando exista la app (#5, #6).
- Umbral de tamaño basado en mediciones reales de Qollab.
