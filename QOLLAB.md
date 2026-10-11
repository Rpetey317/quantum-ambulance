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

## Job limits

- **Local simulators** (built-in, Braket local, IBM noise models): unlimited
  `backend.run` calls per run.
- **IonQ backends** (remote sims *and* QPUs): **one job per run** — a second job
  errors out. The new adapter attempts at most one supplied-backend job;
  `baseline.py`'s local sampler does not itself prove IonQ compatibility. Providers that
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
  grow. The prototype's `qc.initialize()` and the adapter's unitary
  `StatePreparation` both synthesize the Dicke state into many gates. Local and
  offline serialization checks passed; **test on the IonQ Forte sim early**.

## What "run on various simulators" means for this project

Because the runner picks the backend, "various simulators" = **one Run per
backend choice**. Plan: publish the project, press Run once on each of: built-in
sim, Braket local sim, one IBM noise model, IonQ Aria sim, IonQ Forte sim.
Record the resulting `counts` per backend for a comparison table on the project
page (e.g. probability of measuring an optimal selection and % of shots with
exactly K sites per simulator — a nice noise-model comparison for the judges).

## Interactive JS entrypoint

Root `index.html`, `main.js`, `main.css` now mount the metric map editor and
comparison panel in `ui/`. The transport uses the supplied backend and JSON
Python bridge, without external runtime services. See [UI.md](docs/UI.md) for
packaged files, local preview, observed Chrome checks, and the remaining actual
Qollab Run/Stop/IonQ smoke procedure. This shell has not yet been exercised on
Qollab itself; local BasicSimulator results are not remote-platform evidence.

## Porting `baseline.py` to a Qollab Python project

The input-driven port is now available in `ambulance/`; the original script
remains executable. See [the integration contract](docs/CONTRACT.md).

1. Package `ambulance/`, `data/cases/synthetic.json`, and `requirements.txt`.
   For an intermediate Python check, copy `examples/qollab_smoke.py` to root
   `main.py`. The JS app workstream uses the same modules through the bridge.
2. `run_qaoa(case, backend, ...)` rebuilds all case-dependent quantum inputs,
   tunes locally, uses unitary Dicke preparation, transpiles at level 1, and
   attempts a single `backend.run`. The raw original circuit fails on local
   `BasicSimulator` with unsupported `initialize`; a direct sampler replacement
   without compilation is insufficient.
3. `StatevectorSampler` belongs to core Qiskit and does not require Aer. It
   would sample locally rather than honor the visitor-selected backend, so the
   port does not use it as a replacement for the Qollab job.
4. Use an annotated single-line signature such as
   `def main(shots: int = 64):`. Qollab calls a valid `main()` after executing
   the script; do not call it yourself as well. Unannotated parameters disable
   that automatic call and its form.
5. NumPy, SciPy and Matplotlib are available through Pyodide according to the
   runtime docs. Circuit graphical drawings need Qiskit Visualizations enabled.
   Offline charts are an option, not a consequence of Matplotlib being absent.

Local built-in-style simulator runs and offline IonQ payload conversion passed;
actual Qollab browser/lifecycle and IonQ remote smoke checks remain pending.
Start those with 64 shots. The adapter caps identified IonQ simulators at 128
shots as a conservative application policy and disables IonQ hardware.

Docs: <https://qollab.xyz/learn/docs/runtime-environment>,
<https://qollab.xyz/learn/docs/transpilation>

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

The current issue plan targets **A**. The Python smoke project is an intermediate
check. Actual interactive run/reset behavior must be established by issue #1
before the final app can claim that workflow is supported.
