# Ambulancias Cuánticas (Quantum Ambulances)

A Qollab x IonQ **Quantum Impact** hackathon project exploring where to place a limited number of ambulance bases so that the greatest possible population lies within a response radius. The repository contains the original **proof of concept** plus input-driven core and quantum modules for the planned Qollab app. The interactive app is not implemented here yet.

## The problem and the prototype

Given population-weighted zones, candidate base locations, a coverage radius, and exactly `K` available ambulances, choose `K` locations to maximize the population covered by at least one base. In `baseline.py`, there are 15 synthetic zones, 8 candidate sites (one qubit per site), `K = 3`, and a radius of 3 km. Coverage uses straight-line distance, not road travel time; the pitch treats 3 km as a rough 4–5 minute response at 40 km/h.

The prototype computes actual covered population with `poblacion_cubierta()`. It then compares:

- `greedy()`: repeatedly choose the site with the greatest marginal coverage.
- `exacta()`: search all 56 combinations of 3 among 8 sites to find the optimum for this small case.
- QAOA: minimize a quadratic approximation to coverage using a Dicke initial state and an XY mixer to preserve exactly `K` selected sites. A classical COBYLA optimizer tunes three circuit layers with local statevector simulation. A single `StatevectorSampler` job takes 4,096 shots; the best sampled selection is chosen using **actual** coverage, not the approximate QAOA objective.

The pitch (`Idea.pdf`) reports the following example results from a Qiskit simulator run (sampled values can vary):

| Method | Selected site indices (zero-based) | Covered population |
| --- | --- | --- |
| Greedy | 2, 5, 6 | 1,845 thousand (79.7%) |
| Exact | 1, 2, 5 | 2,086 thousand (90.1%) |
| QAOA | 1, 2, 5 | 2,086 thousand (90.1%) |

In that run, QAOA sampled an optimal solution in 27.5% of shots versus 3.6% for uniform random selection, with exactly three sites selected in every shot. The pitch notes two tied optimal selections, `[1, 2, 5]` and `[2, 4, 5]`. These are **prototype observations**, not evidence of a quantum speedup: at eight sites, exhaustive classical search is easy, and quantum advantage at larger scale is not established.

## Run the proof of concept

The pitch states it was tested with Qiskit 2.5.2, NumPy, and SciPy. Install those Python dependencies in your preferred environment, then run:

```bash
python baseline.py
```

The script prints the greedy, exact, and sampled QAOA results, the fraction of valid shots, the probability of measuring an optimum relative to random selection, and the five most frequent measured bitstrings. In `baseline.py`, optimization and `StatevectorSampler` run locally. The new adapter accepts a supplied backend and has been checked with local `BasicSimulator`; IonQ circuit/payload conversion was checked offline, with no remote or hardware execution. The pitch estimates roughly 1–2 minutes for the original simulator run, depending on the environment.

To experiment, edit `ZONAS`, `SITIOS`, `RADIO_KM`, `K`, or the circuit settings in `baseline.py`. The data and all derived arrays/circuit state are created at import time, so rerun the script after changing inputs.

## Input-driven core and quantum adapter

`ambulance.core.evaluate_case(case)` validates a case JSON, rebuilds coverage,
and returns deterministic greedy and bounded exact results. The independent
`ambulance.quantum.run_qaoa(case, backend, ...)` rebuilds QAOA for edited sites,
radius and K, optimizes locally, transpiles, and attempts one supplied-backend
job. It rejects invalid shots before choosing by actual union coverage.

The shared [case/result contract](docs/CONTRACT.md) documents stable IDs,
revision/fingerprint checks, bounds, timings and the JSON-string JS/Python
bridge. [Local validation](docs/LOCAL_VALIDATION.md) records what was tested
and which actual Qollab checks remain. `examples/qollab_smoke.py` is a
Python-only Qollab entrypoint example, not the final UI.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests submit no remote or paid jobs. To check only the dependency-free core:
`python -m unittest discover -s tests -p test_core.py -v`.

## App direction and limitations

The pitch proposes a project page showing the problem, a map of zones and selected bases, a comparison of methods, plots of measured results, instructions, limitations, and credits. The current issue plan targets a Qollab JS/Qiskit app. Core/quantum functions support changed radius, sites and ambulance count, but no map editor or comparison UI is implemented here yet. Actual Qollab lifecycle and remote-backend behavior remain to be verified by the platform workstream. Road travel times and demand over time are future model extensions.

The QAOA cost is only a pairwise approximation of true union coverage. The original prototype uses synthetic data; the packaged CABA cases use static census-population proxies and curated candidate sites. Exact statevector-based angle optimization does not scale to large numbers of sites. Do not describe this prototype as an operational emergency dispatch tool or claim a demonstrated speed advantage over classical methods.

## Repository files

- `baseline.py` — executable Qiskit proof of concept (Python; code/comments in Spanish).
- `ambulance/` — input-driven core, dynamic QAOA adapter, and JSON-string bridge.
- `data/cases/synthetic.json` — original synthetic inputs in the shared case format.
- `tests/` — deterministic core and quantum adapter regressions, using local jobs only.
- `docs/` — integration contract and observed validation.
- `examples/qollab_smoke.py` — intermediate Python-only Qollab smoke entrypoint.
- `Idea.pdf` — Spanish pitch, methodology, reported results, hackathon checklist, and proposed presentation.
- `QOLLAB.md` — Qollab backend notes, job limits, platform-spike validation findings, and the plan for porting `baseline.py`.
- `qollab-spike/` — local-only JS/Python/one-qubit probe for issue #1 (not committed); not the ambulance app. See `QOLLAB.md` for validation steps.
- `data/` — GCBA open-data seed cases: processed `cases/*.json` plus `README.md` with provenance, schema, and regeneration steps. Raw downloads are not committed.
- `tools/` — `build_cases.py` regenerates the case assets from public datasets (stdlib only); `validate_cases.py` checks the case contract and coverage sanity.
- `LICENSE` — MIT license.

The pitch asks for attribution of prior work and AI assistance in the eventual hackathon submission; confirm the actual contributions and disclosures before publishing. Core/adapter work used OpenAI Codex assistance, as recorded in the contract. No interactive app or CI configuration is present yet.
