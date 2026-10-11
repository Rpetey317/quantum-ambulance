# Running on Qollab — platform notes and implementation plan

Notes for porting `baseline.py` into a published Qollab project that runs on the
platform's free simulators (hackathon checklist requirement). Sources: the Qollab
docs at <https://qollab.xyz/learn/docs/> (pages linked per-section below) as of
2026-10-11.

## How Qollab runs a project

- Projects run **in the visitor's browser**, not on a server. Python projects run
  on Pyodide (Python 3.14, Qiskit 2.x, NumPy 2.x, most of the stdlib);
  `requirements.txt` adds extra packages (SciPy is available in Pyodide).
  JS/Qiskit projects run JavaScript in a sandboxed iframe and render into your
  own HTML/CSS — that is the "app" format.
- Two project types:
  - **Python / Qiskit** — `main.py` plus your own `.py` files and data files.
    Output = `print()` to the run console.
  - **JS / Qiskit** — JavaScript calling the Qiskit API in the browser, with
    custom HTML/CSS for UI. Can call your Python functions via `.callPromising`.
- The code **does not choose the compute device**. Whoever presses *Run* picks
  one in the *Select QPU* dialog, and the runtime hands the code a pre-created
  global named `backend`. Nothing in the code can enumerate or select simulators.
- `backend` is a **real provider backend object**, not a wrapper: the built-in
  simulator is Qiskit's `BasicSimulator`, the IBM options are `Fake*` noise-model
  backends, the AWS option is Braket's `LocalSimulator`, and IonQ options come
  from `IonQProvider`. Whatever that provider's `run()` accepts works.

Docs: <https://qollab.xyz/learn/docs/python-qiskit-projects>,
<https://qollab.xyz/learn/docs/js-qiskit-projects>,
<https://qollab.xyz/learn/docs/runtime-environment>

## The API call to run a circuit

Inside a project, running a circuit is one call:

```python
job = backend.run(circuit, shots=4096)
counts = job.result().get_counts()
```

- Shots go in the `run` call. A `def main(shots: int)` parameter becomes a
  *Shots* field under *Run settings* in the dialog; omit it and the backend
  default applies (1024).
- On the built-in simulator and IonQ backends the runner shows a *Probabilities*
  panel charting the outcome distribution for free; IonQ runs also show the
  submitted circuit.
- JS equivalent: `const job = await backend.run(circuit, { shots })`, then
  `(await job.result()).get_counts().toJs()`.

**There is no documented external API to trigger a Qollab run from another app.**
Qollab is an interactive platform, not a job service. To run circuits from your
own backend you would integrate the providers directly (see "External option").

## Job limits — already satisfied by `baseline.py`

- **Local simulators** (built-in, Braket local, IBM noise models): unlimited
  `backend.run` calls per run.
- **IonQ backends** (remote sims *and* QPUs): **one job per run** — a second job
  errors out. This matches the existing comment in `muestrear()`. Providers that
  support multi-circuit jobs accept a *list* of circuits in the single `run`.

Docs: <https://qollab.xyz/learn/docs/compute-backends>

## Available backends (Select QPU dialog)

| Backend | Type | Qubits | Cost |
| --- | --- | --- | --- |
| Built-in simulator | local | 24 | free, instant |
| AWS Braket local simulator | local | 25 | free |
| IBM Boston/Kingston/Pittsburgh/Fez/Marrakesh/Aachen | local noise model | 156 | free |
| IBM Miami/Berlin (Nighthawk r1) | local noise model | 120 | free |
| IonQ Aria 1 / Aria 2 | remote sim (IonQ cloud) | 25 | free (hardware retired) |
| IonQ Forte 1 / Forte Enterprise 1 | remote sim | 29 | free |
| IonQ Forte 1 / Forte Enterprise 1 | QPU | 36 | credits |

Notes:

- The IBM noise-model backends simulate a real device's noise; the model is
  rebuilt each run, so first run is slower.
- IonQ remote sims are shot-aware: noise-model simulation runs once per shot, so
  large shot counts take proportionally longer. Test small `shots` first.
- IonQ recompiles the circuit to native gates before execution; gate count can
  grow. `qc.initialize()` (the Dicke state) is the risky part — it decomposes
  into many gates. Fine on local sims; **test on the IonQ Forte sim early**.

## What "run on various simulators" means for this project

Because the runner picks the backend, "various simulators" = **one Run per
backend choice**. Plan: publish the project, press Run once on each of: built-in
sim, Braket local sim, one IBM noise model, IonQ Aria sim, IonQ Forte sim.
Record the resulting `counts` per backend for a comparison table on the project
page (e.g. probability of measuring an optimal selection and % of shots with
exactly K sites per simulator — a nice noise-model comparison for the judges).

## Porting `baseline.py` to a Qollab Python project

Minimal restructure — keep all problem logic and the local optimizer:

1. Keep sections 1–5 (data, coverage, greedy/exact, `Q`, `costo`,
   `circuito_qaoa`, `energia`, `optimizar`, `bits_a_sitios`) as-is. The
   statevector-based angle optimization is **local classical work** — it does not
   count as a job and is fine under Pyodide for 8 qubits.
2. In `muestrear()`, replace the local sampler with the injected backend:

   ```python
   def muestrear(params, shots=4096):
       circ = ansatz.assign_parameters(params)
       circ.measure_all()
       job = backend.run(circ, shots=shots)   # one job: IonQ-safe
       return job.result().get_counts()
   ```

   (`StatevectorSampler` is not available on Qollab — there is no Aer; the
   built-in `BasicSimulator` backend is what a local run hands you.)
3. Wrap the `__main__` block in `def main(shots=4096):` so the Shots field
   appears in the Run dialog, and pass `shots` through to `muestrear`.
4. Qollab entrypoint convention: `main.py` top-level code runs on Run; guard or
   call `main()` at the bottom as the docs' starter does.
5. `requirements.txt`: `numpy`, `scipy` (Qiskit 2.x ships with the runtime).
   Skip matplotlib — not guaranteed in Pyodide; generate charts offline and ship
   them as images on the project page instead.

## App options

- **A. JS/Qiskit project on Qollab** — the deliverable *is* an app: custom
  HTML/CSS map + charts, JS calls into the ported Python via `.callPromising`.
  Backend still comes from the dialog. No browser storage (sandboxed iframe —
  recompute or re-run each time).
- **B. Python project + static page** — simplest: the Qollab project prints and
  charts results; the GitHub-side page has the write-up, map, and the
  per-simulator comparison table.
- **C. External app with own providers** — only if we leave Qollab's model.
  Real APIs exist: IonQ REST `POST https://api.ionq.co/v0.3/jobs` or
  `qiskit-ionq` (`IonQProvider(KEY).get_backend('ionq_simulator')`), AWS Braket
  SDK (`AwsDevice` SV1/DM1/TN1 or free `LocalSimulator()`), local
  `AerSimulator`/`StatevectorSampler`/`Fake*` backends. Requires our own API
  keys and cost management; does **not** satisfy the "published and executable
  on Qollab" checklist item by itself.

Recommendation for the deadline: **B, or A if time allows** — publish the Python
project first (required), then wrap it in the JS/Qiskit page only if the port is
clean.
