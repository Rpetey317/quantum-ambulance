# Local validation and Qollab handoff

Observed on 2026-10-11, Windows, CPython 3.13.5, Qiskit 2.5.2,
NumPy 2.5.4 and SciPy 1.18.1. These observations are local tests, not evidence
of execution inside Qollab, on IonQ's cloud, or on hardware.

## Reproduce local tests

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python baseline.py
```

An isolated version-matched alternative, if `uv` is installed:

```bash
uv run --no-project --with qiskit==2.5.2 --with numpy==2.5.4 --with scipy==1.18.1 python -m unittest discover -s tests -v
uv run --no-project --with qiskit==2.5.2 --with numpy==2.5.4 --with scipy==1.18.1 python baseline.py
```

The requirements file leaves NumPy/SciPy unpinned so Qollab can use the packages
available in its Pyodide distribution. Solver angles and stochastic outcomes can
vary across those versions. No test requires a stochastic run to find an optimum.

The 33-test suite covers the original fixture and exact ties, input validation, editing
and staleness, radius boundaries, overlap, exact cost bounds, bit order, even/odd
and one/two-site circuits, true-coverage sample selection, invalid/all-invalid
shots, probability denominators, bounded local tuning, and one-job/error paths.
Local `BasicSimulator` jobs are small; the suite contains no remote jobs.

`python baseline.py` still returned greedy 1845 and exact/QAOA 2086 thousand,
100% valid K=3 shots. Its observed optimal-shot rate was 25.9% on the final
regression run (4096 shots), versus 2/56 uniform probability. This is one
stochastic observation of the original script, not a speedup measurement.

## Three-case adapter smoke check

The two real assets were read from data PR #10's branch at commit
`7d7963b239f77e70c0b2a17977b58e83dbd84077`, without merging it. Their sizes were
31,981 bytes (`caba-comuna4.json`) and 400,968 bytes (`caba.json`).

Settings: K=3, eight sites, three layers, two restarts, at most 150 COBYLA
evaluations per restart, optimizer seed 1; `BasicSimulator(seed_simulator=11)`;
64 shots; an exact result for the identical case was supplied. Every run
attempted exactly one backend job and returned 64/64 valid shots.

| Case | Zones | Weight units | Total weight | Greedy | Exact | Best valid QAOA shot | Optimal shots |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Synthetic | 15 | thousand people | 2315 | 1845 | 2086 | 2086 | 14/64 |
| CABA Comuna 4 | 252 | people | 218245 | 176818 | 185708 | 185708 | 2/64 |
| CABA | 3552 | people | 2890151 | 1682455 | 1682455 | 1682455 | 3/64 |

Both optimizer restarts reached their 150-evaluation budget in each case;
the chosen iterate reported `converged=false`. Good sampled coverage does not
establish optimizer convergence, a guaranteed optimum, or quantum advantage.
The Comuna 4 candidates were deliberately curated in the data PR to increase
the greedy/exact gap; this is not an unbiased benchmark over all city sites.

| Case | Greedy solve | Exact solve | Local optimization | Transpilation | Backend job | Whole comparison |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Synthetic | 0.00004 s | 0.00017 s | 1.262 s | 0.082 s | 0.010 s | 1.359 s |
| CABA Comuna 4 | 0.00013 s | 0.00083 s | 1.525 s | 0.064 s | 0.011 s | 1.608 s |
| CABA | 0.00080 s | 0.00565 s | 1.362 s | 0.062 s | 0.011 s | 1.479 s |

Whole comparison also includes separate coverage rebuilds for the classical
preview and quantum adapter and postprocessing. These are single desktop
measurements, not browser performance guarantees or scalable benchmarks.
Full-case classical coverage preparation was approximately 0.015 seconds.

Reproduce after the data assets are present locally:

```python
from ambulance.core import evaluate_case, load_case
from ambulance.quantum import run_qaoa
from qiskit.providers.basic_provider import BasicSimulator

case = load_case("data/cases/caba.json")
preview = evaluate_case(case)
result = run_qaoa(case, BasicSimulator(seed_simulator=11), shots=64,
                  exact_result=preview["exact"])
assert result["backend_run_calls"] == 1
assert result["valid_shot_rate"] == 1
print(result)
```

For a Qollab app, write asset paths literally in imported Python code so its
static loader sees them. Dataset geometry/projection/license validation remains
the data/QA workstream's responsibility; this check confirms input compatibility
and execution against the proposed assets, not all their external claims.

## Offline IonQ compatibility check

Using `qiskit-ionq==1.0.2`, constructed an `IonQSimulatorBackend` locally with a
dummy offline token, transpiled the eight-site, three-layer measured circuit at
optimization level 1, and converted it with
`qiskit_ionq.helpers.qiskit_circ_to_ionq_circ(..., gateset="qis")`.
No provider run or network job was requested. Conversion succeeded: 803
serializable gates, compiled local depth 729, no `initialize` or `reset`.
IonQ may change this gate count in its own compiler and may still reject or
limit a remote job; this offline check cannot establish remote feasibility.

## Outstanding platform checks

1. In a Qollab project, package `ambulance/`, the synthetic fixture and
   `requirements.txt`; copy `examples/qollab_smoke.py` to root `main.py`.
   Select the free built-in simulator and 64 shots. Save the source revision,
   printed JSON identity/settings/counts/timings and backend name.
2. In the JS scaffold from issue #1/#5, use the documented `.callPromising`
   bridge. Edit a site and K; confirm preview and returned quantum result use
   the edited identity. Verify the actual Run/Stop/reset behavior and ensure
   stale results cannot be presented as current.
3. Repeat on the available free backends after checking circuit support.
   For an identified IonQ remote simulator, first request only 64 shots, in a
   fresh run. Save valid/invalid-shot rates and actual coverage, or the exact
   failure message. A second IonQ job requires the platform's supported new-run
   workflow, which must be observed rather than assumed.
4. Run both final packaged datasets and record their exact revisions and input
   fingerprints. Scope timings to the fields actually measured. The current
   adapter intentionally rejects IonQ QPUs; no paid hardware check was performed.

The actual Qollab browser run, reset/edit lifecycle and IonQ remote check remain
pending. They cannot be marked passed from these local/offline observations.
