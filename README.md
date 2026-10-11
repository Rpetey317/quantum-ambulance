# Ambulancias Cuánticas (Quantum Ambulances)

A Qollab x IonQ **Quantum Impact** hackathon project exploring where to place a limited number of ambulance bases so that the greatest possible population lies within a coverage radius. The repository contains the original **proof of concept**, input-driven core/quantum modules, and an interactive map editor and comparison UI with a minimal Qollab entrypoint. Run the app on the hosted [Qollab project](https://qollab.xyz/u/rpetey317/ambulance-localizer).

## Run it locally

Try the [public web app](https://quantum-ambulance.vercel.app), with the same map
editor and classical solvers plus bounded QAOA on a server-side Qiskit simulator.
See [standalone web setup and limits](docs/VERCEL.md). The Qollab entrypoint remains
available for its visitor-selected backends.

Everything below is local-only; it submits no remote or paid jobs.

```bash
python -m pip install -r requirements.txt   # qiskit==2.5.2, numpy, scipy
```

- `python baseline.py` — original proof of concept (~1–2 min; details below).
- `python -m tools.preview_ui` — interactive map editor and comparison UI at `http://127.0.0.1:8765` (Ctrl+C to stop). A localhost QA harness backed by the real Python bridge and local `BasicSimulator`; not for use inside Qollab. See [docs/UI.md](docs/UI.md).
- `python -m unittest discover -s tests -v` — Python core/adapter suite. `npm test` — UI controller/model tests (Node only, no build step or npm dependencies).

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

The script prints the greedy, exact, and sampled QAOA results, the fraction of valid shots, the probability of measuring an optimum relative to random selection, and the five most frequent measured bitstrings. In `baseline.py`, optimization and `StatevectorSampler` run locally. The new adapter accepts a supplied backend and has been run locally on `BasicSimulator` and remotely on Qollab's built-in, IBM-noise-model and IonQ simulators (results in `docs/PROJECT_PAGE.md`); no hardware execution. The pitch estimates roughly 1–2 minutes for the original simulator run, depending on the environment.

To experiment, edit `ZONAS`, `SITIOS`, `RADIO_KM`, `K`, or the circuit settings in `baseline.py`. The data and all derived arrays/circuit state are created at import time, so rerun the script after changing inputs.

## Results

Reference runs use Qiskit's local `BasicSimulator` (1,024 shots) through the same code path the app uses (`tools/reference_runs.py`); they are not Qollab or IonQ results. Full table and charts: `docs/results/REFERENCE.md`.

| Case | Greedy | Exact | QAOA best shot | P(optimum), QAOA | P(optimum), random | Amplification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Synthetic | 79.7% | 90.1% | 90.1% | 16.0% (26.6%*) | 3.6% | 4.5× (7.4×*) |
| CABA Comuna 4 | 81.0% | 85.1% | 85.1% | 1.8% | 1.8% | 1.0× |
| CABA full city | 58.2% | 58.2% | 58.2% | 10.4% (41.1%*) | 1.8% | 5.9× (23×*) |

\* With a larger angle-optimization budget (4 restarts × 500 iterations, as in the original prototype) instead of the app's default (2 × 150).

Runs on the packaged app in Qollab, using the CABA Comuna 4 case:

| Backend (Select QPU) | Shots | Valid exactly-K shots | QAOA best coverage | P(optimum) | Backend job time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Built-in simulator | 256 | 256 (100%) | 85.1% | 3.9% | 0.053s |
| IBM noise model (Boston) | 64 | 26 (40.6%) | 81.4% | 0.0% | 34.741s |
| IonQ simulator (Aria 2) | 64 | 14 (21.9%) | 83.7% | 0.0% | 14.701s |

Highlights: greedy misses the optimum on the synthetic and Comuna 4 cases; QAOA amplifies the optimum relative to random selection on the synthetic and full-city cases but not on Comuna 4; remote backends return shots that break the exactly-K constraint, which the adapter rejects. With 8 qubits, exhaustive classical search solves every case instantly — these runs measure solution quality and sampling behaviour, not a quantum speedup.

![Actual coverage by method](docs/results/coverage.png)
![CABA Comuna 4: greedy vs exact map](docs/results/map_caba-comuna4.png)

## Input-driven core and quantum adapter

`ambulance.core.evaluate_case(case)` validates a case JSON, rebuilds coverage,
and returns deterministic greedy and bounded exact results. The independent
`ambulance.quantum.run_qaoa(case, backend, ...)` rebuilds QAOA for edited sites,
radius and K, optimizes locally, transpiles, and attempts one supplied-backend
job. It rejects invalid shots before choosing by actual union coverage.

The shared [case/result contract](docs/CONTRACT.md) documents stable IDs,
revision/fingerprint checks, bounds, timings and the JSON-string JS/Python
bridge. [Local validation](docs/LOCAL_VALIDATION.md) records what was tested
locally; `docs/PROJECT_PAGE.md` records the actual Qollab runs.
`examples/qollab_smoke.py` is a
Python-only Qollab entrypoint example, not the final UI.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests submit no remote or paid jobs. To check only the dependency-free core:
`python -m unittest discover -s tests -p test_core.py -v`.

## App direction and limitations

The interactive editor loads compact/full CABA or the synthetic case, supports bounded site dragging/numeric edits, and recomputes greedy/exact previews after changes to sites, radius or K. The comparison panel uses shared actual-coverage layers and excludes stale quantum results. Root `index.html`, `main.js`, `main.css` provide the minimal Qollab shell; the UI modules accept an injected transport for integration with other scaffolding. See [UI setup and validation](docs/UI.md) for local preview commands, packaging and actual-platform checks. Road travel times and demand over time are future model extensions.

The QAOA cost is only a pairwise approximation of true union coverage. The original prototype uses synthetic data; the packaged CABA cases use static census-population proxies and curated candidate sites. Exact statevector-based angle optimization does not scale to large numbers of sites. Do not describe this prototype as an operational emergency dispatch tool or claim a demonstrated speed advantage over classical methods.

## Repository files

- `baseline.py` — executable Qiskit proof of concept (Python; code/comments in Spanish).
- `ambulance/` — input-driven core, dynamic QAOA adapter, and JSON-string bridge.
- `index.html`, `main.js`, `main.css`, `ui/` — Qollab entrypoint and reusable metric map/editor/comparison UI.
- `data/cases/synthetic.json` — original synthetic inputs in the shared case format.
- `tests/` — deterministic core, quantum adapter, bridge, `baseline.py` and data-case regressions, using local jobs only; see `docs/TESTING.md`. CI (`.github/workflows/tests.yml`) runs them on every PR.
- `docs/` — integration contract and observed validation.
- `examples/qollab_smoke.py` — intermediate Python-only Qollab smoke entrypoint.
- `docs/PROJECT_PAGE.md` — hackathon project page draft (problem, method, results, how to run, limitations, credits); `docs/results/` holds local reference results and charts from `tools/reference_runs.py`.
- `Idea.pdf` — Spanish pitch, methodology, reported results, hackathon checklist, and proposed presentation.
- `QOLLAB.md` — Qollab backend notes, job limits, platform-spike validation findings, and the plan for porting `baseline.py`.
- `qollab-spike/` — local-only JS/Python/one-qubit probe for issue #1 (not committed); not the ambulance app. See `QOLLAB.md` for validation steps.
- `data/` — GCBA open-data seed cases: processed `cases/*.json` plus `README.md` with provenance, schema, and regeneration steps. Raw downloads are not committed.
- `tools/` — `build_cases.py` regenerates the case assets from public datasets (stdlib only); `validate_cases.py` checks the case contract and coverage sanity.
- `LICENSE` — MIT license.

The pitch asks for attribution of prior work and AI assistance in the eventual hackathon submission; confirm the actual contributions and disclosures before publishing. Core/adapter and UI work used OpenAI Codex assistance, as recorded in the contract and UI documentation. CI runs the Python and UI test suites on every PR (see `docs/TESTING.md`).
