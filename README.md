# Ambulancias Cuánticas (Quantum Ambulances)

A Qollab x IonQ **Quantum Impact** hackathon project exploring where to place a limited number of ambulance bases so that the greatest possible population lies within a response radius. The current repository is a **proof of concept**, not yet an application: it compares a greedy baseline, an exact classical solution, and QAOA on a small synthetic example.

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

The script prints the greedy, exact, and sampled QAOA results, the fraction of valid shots, the probability of measuring an optimum relative to random selection, and the five most frequent measured bitstrings. Optimization uses local statevector simulation; `StatevectorSampler` also runs locally. **No IonQ hardware or remote backend integration is present in this repository.** The pitch estimates roughly 1–2 minutes for a simulator run, depending on the environment.

To experiment, edit `ZONAS`, `SITIOS`, `RADIO_KM`, `K`, or the circuit settings in `baseline.py`. The data and all derived arrays/circuit state are created at import time, so rerun the script after changing inputs.

## App direction and limitations

The pitch proposes a project page showing the problem, a map of zones and selected bases, a comparison of methods, plots of measured results, instructions, limitations, and credits. Potential follow-ups include changing the radius or ambulance count, testing multiple instances, using real city data and road travel times, modeling demand over time, and validating compatibility with IonQ simulation or hardware. **These are proposals, not implemented app features.** The UI, backend, deployment, and data sources have not been selected yet.

The QAOA cost is only a pairwise approximation of true union coverage. The current data are synthetic and static, and exact statevector-based angle optimization does not scale to large numbers of sites. Do not describe this prototype as an operational emergency dispatch tool or claim a demonstrated speed advantage over classical methods.

## Repository files

- `baseline.py` — executable Qiskit proof of concept (Python; code/comments in Spanish).
- `Idea.pdf` — Spanish pitch, methodology, reported results, hackathon checklist, and proposed presentation.
- `QOLLAB.md` — Qollab platform notes: backend model, job limits, and the plan for porting `baseline.py` into a published Qollab project.
- `data/` — real seed-data cases for the demo (GCBA open data): `cases/*.json` processed assets plus `README.md` with provenance, schema, and regeneration steps. Raw downloads are not committed.
- `tools/` — `build_cases.py` regenerates the case assets from the public datasets (stdlib only); `validate_cases.py` checks the case contract and coverage sanity.
- `tests/` — deterministic regressions for `baseline.py` and the data cases; see `docs/TESTING.md` (commands, coverage, manual Qollab checklist). CI runs them on every PR.
- `LICENSE` — MIT license.

The pitch asks for attribution of prior work and AI assistance in the eventual hackathon submission; confirm the actual contributions and disclosures before publishing. No app is present yet; the basic local test suite is described in `docs/TESTING.md`.
