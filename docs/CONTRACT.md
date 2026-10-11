# Core and quantum integration contract (v1)

Implements the local portions of GitHub issues #2 (Core) and #4 (Quantum).
The source modules are `ambulance/core.py`, `ambulance/quantum.py`, and
`ambulance/bridge.py`. `baseline.py` remains the original executable example.

## Case JSON

Compatible with the CABA assets merged in data PR #10. The core/quantum change
does not alter those assets. Read-only assets use `k_default`; an edited case sets
`k`, which takes precedence. Preserve metadata and stable IDs while editing.

```json
{
  "schema_version": 1,
  "meta": {
    "id": "my-case",
    "revision": 1,
    "crs": "local Cartesian plane",
    "coordinate_units": "km",
    "weight_units": "people",
    "zone_resolution": "one weighted point per zone",
    "sources": [{"name": "Synthetic example", "license": "MIT"}]
  },
  "radius_km": 3.0,
  "k_default": 1,
  "zones": [{"id": "zone-a", "x_km": 0, "y_km": 0, "weight": 100}],
  "sites": [{"id": "site-a", "x_km": 1, "y_km": 0}]
}
```

- `schema_version` may be omitted for the existing PR #10 assets; only v1 is accepted.
- `meta.revision`: nonnegative integer or nonempty string. Increment it on any
  model edit. Dataset ID and revision are echoed in each result.
- IDs: unique nonempty strings within each collection. Original synthetic site
  IDs are `"0"` through `"7"`; numeric `selected_site_indices` remain zero-based.
- `x_km`, `y_km`: finite Cartesian/projected coordinates already in kilometres.
  `coordinate_units` accepts `km` or the PR's descriptive `km (...)` form.
  Raw longitude/latitude is unsupported. The core does not project coordinates.
- Positive finite zone weights and radius; nonempty zones/sites;
  integer `1 <= k <= N`. Boolean values are rejected as numbers.
- Candidate sites less than 0.001 km apart are rejected. Coincident zone
  centroids are allowed: independent weights still represent different zones.
- Provenance and resolution fields are required. Other metadata, labels, and
  display geometry can remain in the JSON; they do not replace coverage points.
  Study-area editing bounds and display geometry belong to the map workstream.
- All coverage uses distance `<= radius_km` and the union of covered zones.
  Weight units stay unchanged: the original fixture uses **thousand people**;
  the CABA assets use **people** (`personas`).

## Classical API and ties

```python
from ambulance.core import evaluate_case, load_case, prepare_case, solve_exact

case = load_case()  # literal packaged path: data/cases/synthetic.json
case["k"] = 2
case["meta"]["revision"] = "edit-1"
comparison = evaluate_case(case)  # JSON-compatible dict; accepts a JSON string too
```

No case-dependent module globals or shared mutable caches are used. Each call
validates and rebuilds coverage. The caller's input is not mutated.

Greedy breaks equal marginal-weight ties by the first site in current array
order. Exact search enumerates lexicographically in that same zero-based order,
returns the first optimum, and records every tied selection in
`optimal_selections` plus `n_optimal_solutions`. Weight sums use `math.fsum`
in zone order; ties mean equal computed sums, without an arbitrary tolerance.

Exact is available only when both `C(N,K) <= 10,000` and
`C(N,K) * number_of_zones <= 5,000,000`. The second value is a conservative
zone-work estimate, not a measured runtime guarantee. Limits can be lowered
through `evaluate_case(..., max_combinations=..., max_zone_work=...)`.
Above either bound, exact returns `status="unavailable"`, its bound details,
and null coverage/optimal-solution count. It does not run a partial search.

## Result envelope

`evaluate_case` returns `schema_version`, `case_id`, `case_revision`,
`input_fingerprint`, `greedy`, and `exact`. The quantum bridge adds `qaoa`.
Every method result includes:

| Field | Meaning |
| --- | --- |
| `case_id`, `case_revision`, `input_fingerprint` | Identity of the evaluated inputs |
| `method`, `status`, `message` | Method and outcome; missing explanation is null |
| `k`, `n_sites`, `radius_km` | Evaluated settings |
| `selected_site_indices`, `selected_site_ids` | Ordered logical indices and stable IDs |
| `covered_zone_ids` | True union overlay, using the case's zone IDs |
| `covered_weight`, `coverage_pct`, `total_weight`, `weight_units` | Actual union weight; percentage is 0..100 |
| `timings` | Wall-clock seconds for labeled components; absent components are null |

The fingerprint is SHA-256 of canonical model inputs: dataset ID, CRS, weight
units, effective K/radius, ordered zone IDs/coordinates/weights and ordered
site IDs/coordinates. It excludes labels and display geometry. Reject/mark stale
results if **any** of case ID, revision, or fingerprint differs. A revision alone
cannot detect an edit whose caller forgot to increment it.

For `unavailable`, `failed`, or `no_valid_sample`, selected/covered ID arrays are
empty and coverage values are null. Zero coverage from a valid selection is an
actual numeric zero. Do not render null coverage as an evaluated solution.
Invalid cases raise `CaseValidationError` before a result exists; the UI should
display the validation message. Quantum provider failures return `failed` with
`error_stage` and `message`, without retrying or silently sampling locally.

## Quantum API

```python
from ambulance.quantum import run_qaoa

qaoa = run_qaoa(case, backend, shots=64, exact_result=comparison["exact"])
```

`backend` must come from Qollab's selected device. Defaults: three layers, two
local COBYLA restarts, 150 evaluations per restart, seed 1, 64 shots. Limits:
eight sites, one to five layers, one to four restarts, at most 500 evaluations
per restart, and at most 4096 shots. `maxiter` must be at least `2*layers+2`.
Known IonQ simulators have a **128-shot application guard**; request 64 for smoke
checks. This is a conservative demo policy, not a claimed provider limit.
Identified IonQ hardware is disabled in this adapter; no paid jobs are authorized.

All coverage and quantum components are rebuilt from the supplied case.
The initial state is the uniform Dicke K-weight state; unitary `StatePreparation`
avoids `initialize` resets. The XY mixer supports N=1, N=2, and odd N, as well as
the original eight-site ring. Parameters are explicitly mapped as gamma then
beta, independent of Qiskit's alphabetic parameter ordering.

Local energy evaluations evolve the already prepared Dicke state through the
parameterized layers. They do not repeatedly synthesize state preparation and
never call the selected backend. The chosen bounded optimizer iterate is
reported even if COBYLA reaches its budget; `optimizer.converged` and its
message make this visible. No optimality or speedup guarantee is implied.

The measured circuit is transpiled for the supplied backend at optimization
level 1 before **one** `backend.run`. Counts refer to the logical classical
register, even if routing increases physical circuit width. There is no backend
enumeration, provider creation, sampler fallback, or retry. `backend_run_calls`
is 0 or 1 and counts attempted calls, including rejected submissions.

QAOA-specific fields:

- `backend`: best-effort name/class/module and simulator identity;
  `circuit`: local compiled width/depth/operations, layers, cost scale, objective.
  These counts are not IonQ's later proprietary native compilation counts.
- `counts`, `shots` (returned frequency sum), `requested_shots`, `valid_shots`,
  `invalid_shots`, `malformed_shots`, `valid_shot_rate` (0..1; null if no shots).
  Qiskit strings are reversed into indices. Wrong-width/nonbinary strings and
  wrong-K samples cannot win. Fractional probabilities are not accepted as counts.
- Selection maximizes **actual union coverage** among valid, observed shots.
  Coverage ties prefer higher frequency, then lexicographic input indices.
  Empty/all-invalid samples return `no_valid_sample`.
- `optimal_probability`: optimum shots / all shots;
  `optimal_probability_given_valid`: optimum shots / valid shots;
  `uniform_optimal_probability`: exact optimum count / C(N,K);
  `optimal_probability_amplification`: first probability / uniform probability.
  All optimum fields require a successful exact result matching this identity;
  otherwise they are null. Amplification is a sampling ratio, not quantum speedup.
- `optimizer`: gamma/beta angles, seed, evaluations, budget, convergence and
  **approximate** energy. The pairwise objective is never the displayed coverage.

`timings.coverage_s` measures validation, fingerprinting and coverage rebuild.
`solve_s` measures a classical solver. Quantum results instead provide
`quantum_prepare_s`, `local_optimization_s`, `transpile_s` and `backend_job_s`.
The last interval covers `backend.run` through `job.result().get_counts()`;
it includes submission/wait/queue/execution/result retrieval where applicable.
No queue or execution-only timing is invented.

## Qollab JS integration

Keep the `ambulance/` package and all `data/cases/*.json` assets at project root.
The minimal root `index.html`, `main.js`, and `main.css` now mount reusable `ui/`
modules; see [UI.md](UI.md) for packaging and transport integration.
The JSON-string bridge avoids dict/Map conversion ambiguity in JavaScript.
`case_data(id)` loads `synthetic`, `caba-comuna4` or `caba` using literal asset
paths. `describe_backend(backend)` returns best-effort identity without jobs:

```javascript
import * as model from 'ambulance.bridge';

const caseData = JSON.parse(await model.synthetic_case.callPromising());
caseData.k = 2;
caseData.meta.revision = 'edit-1';
const classical = JSON.parse(await model.preview.callPromising(JSON.stringify(caseData)));

// User-requested quantum action: one call using the injected backend.
const comparison = JSON.parse(await model.run_quantum.callPromising(
  JSON.stringify(caseData), backend, 64
));
```

Use `.callPromising` for these Python functions, as Qollab documents. The app
must snapshot edited inputs, manage backend lifetime/one-IonQ-job restrictions,
and handle platform resets. This change does not prove that edits survive a new
Run; that remains issue #1's actual-platform check. See
[runtime docs](https://qollab.xyz/learn/docs/runtime-environment),
[JS bridge docs](https://qollab.xyz/learn/docs/js-qiskit-projects), and
[transpilation docs](https://qollab.xyz/learn/docs/transpilation).

For a Python-only check, copy `examples/qollab_smoke.py` to root `main.py` in a
Qollab project, together with these modules, the fixture and `requirements.txt`.
Its annotated `main()` is invoked by Qollab; do not call it again yourself.
This check is an intermediate integration step, not the final interactive app.

## Validation and attribution

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python baseline.py
```

Core-only checks require only the standard library:
`python -m unittest discover -s tests -p test_core.py -v`.
See [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md) for observed local checks and
the outstanding Qollab/IonQ remote smoke procedure.

The extracted model and quantum method derive from this repository's MIT
prototype. The new extraction, adapter, documentation and tests were produced
with OpenAI Codex assistance. Data sources retain their separate licenses;
final submission credits still need the team's actual contributor review.
