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
<<<<<<< HEAD
  errors out. The platform spike observed this explicitly on the free Aria 1
  simulator while the Qollab Run was still active. This matches the existing
  comment in `muestrear()`. Providers that support multi-circuit jobs accept a
  *list* of circuits in the single `run`.
=======
  errors out. The new adapter attempts at most one supplied-backend job;
  `baseline.py`'s local sampler does not itself prove IonQ compatibility. Providers that
  support multi-circuit jobs accept a *list* of circuits in the single `run`.
>>>>>>> 7707ec81281392787005e8284c4e52330980e9ed

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
  grow. The adapter prepares the Dicke state deterministically in O(N·K) gates
  (generic `StatePreparation` and the prototype's `qc.initialize()` synthesized
  ~2**N gates; those serialized jobs were rejected in remote transport). Local
  and offline serialization checks passed; **test on the IonQ Forte sim
  early**.

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

Local built-in-style simulator runs and offline IonQ payload conversion passed.
Remote checks have since run: the spike submitted Aria 1 jobs (see the evidence
table below), and the packaged app ran CABA Comuna 4 on Qollab's built-in, IBM
Boston noise and IonQ Aria 2 simulators (`docs/PROJECT_PAGE.md`). Start remote
checks with 64 shots. The adapter caps identified IonQ simulators at 128
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

Recommendation for the deadline: **B, or A if time allows** — publish the Python
project first (required), then wrap it in the JS/Qiskit page only if the port is
clean.

## Issue #1 platform spike: upload and record live evidence

`qollab-spike/` is an isolated JS/Qiskit compatibility probe, **not** the ambulance
QAOA app. Its single measured qubit checks whether a site edit travels through
JS → Python → the backend chosen in Qollab's Run dialog. The synthetic zone
preview is a simple true-coverage calculation. Local tests do not establish
that Qollab's browser sandbox accepts this project; a teammate must run it
there before marking issue #1's live acceptance criteria complete.

Upload **the contents** of `qollab-spike/` with their relative paths intact:
`index.html`, `main.js`, `main.css`, `LICENSE`, `spike/__init__.py`,
`spike/service.py`, and `data/fixture.json`. The first two files must be at
the Qollab project root to select the JS/Qiskit project type. Do not upload
`baseline.py`, the repository's root README, the tests, or this document as
part of the spike. If the upload picker flattens paths, recreate the `spike/`
and `data/` paths in Qollab's editor before running. The Python package
imports as `spike.service`; it reads the packaged JSON through the literal
path `data/fixture.json`. No dependencies beyond Qollab's bundled Qiskit and
the Python standard library are needed.
Do not choose a paid QPU. If creating a project by upload asks for a project
write-up, describe this as an **unverified platform spike**, not a QAOA result.

Use a desktop browser that supports WebAssembly JSPI. In Qollab:

1. Create a project from these files (or add them to a new project), keeping
   the two subdirectories. Press **Run**, select the **free built-in simulator**,
   and note whether the app starts and whether `backend` is available at JS
   startup. Note any import, console, or permissions error exactly.
2. Confirm the packaged-file check reports `data/fixture.json`, size and
   SHA-256. Change site x from its default 5 to **0** and then **10** by the
   numeric input. Python should report coverage of zone A/10 of 60 at 0, and
   zone C/30 of 60 at 10; predicted ideal P(1) should be 0% and 100%.
   Drag the red S0 marker once; check that coordinates and Python preview
   change without starting a backend job.
3. The **Submission path** selector defaults to Python `.callPromising(backend)`;
   the JS `backend.run` option is the original spike path. Select a path
   **before** the first job. Set x back to **0** and press **Run first backend
   job**. It requests 32 shots on a non-IonQ backend; an ideal built-in
   simulator should report `{"0": 32}`. Change x to **10** after the result:
   the previous counts must say stale, while Python's preview says 100% P(1).
   Copy the evidence JSON, which includes the selected path and failing stage.
4. Press **Try second job with same case**. Record whether another request
   works during the same Run (it uses the first job's case and path), and
   whether the backend still exists afterwards. Press **Try read-only external
   GET** and record the HTTP status/bytes or exact error. This tests the
   public GitHub raw host only, not every possible static host.
5. Press **Show current case JSON** and copy it into a note **outside Qollab**.
   Press Qollab **Run** again using the built-in simulator; report whether
   the edited coordinates and job results survive or reset and whether a
   new first job is possible. If inputs reset, paste that saved case into
   the textarea and press **Load pasted case**; check that the Python preview
   restores the edits without a backend job.
6. Start a **fresh** Run on **free IonQ Aria 1 simulator**, not a hardware
   QPU. The current spike keeps its top-level JS Run pending through both
   button clicks. Select **Python .callPromising(backend)** and, to reproduce
   the successful first job, set x=1.7 and y=4.7. Press the first-job button
   (4 shots) while Qollab shows the Run as active, then **copy the evidence
   before pressing the second-job button**. Try the second job once **while
   Run is still active**; record its exact error and whether Qollab stops the
   Run. If you do not want to test the limit, press Qollab Stop after saving
   the first result. If the UI cannot be clicked while Run is active, record
   that constraint rather than silently substituting a built-in simulator.

For each run record browser/version, project revision, selected Qollab device,
reported backend name, chosen x/y/radius, preview and covered population,
shot count and counts, whether job 2 works, what survives a new Run, packaged
file bytes/hash, external GET result, and any console error. Share the copied
evidence JSON (before a potentially fatal second IonQ call) plus any screenshot
or exact error text. Keep observed facts separate from expectations. If edits
cannot cross a fresh Run, the copy/paste case workaround is a manual fallback;
flag it for review in the core/app/quantum/data workstreams before building the
full UI.

The docs state limits of 100 project files, 2 MB per file and 200 MB per
account, but this tiny probe **does not measure those maximums**. Locally, the
seven upload files total **25,421 bytes** (largest: `main.js`, 12,733 bytes;
packaged JSON: 228 bytes); these are local file measurements for the updated
spike, not confirmed Qollab upload limits. Record the actual accepted file
count/sizes and any Qollab rejection message rather than claiming the
bounds were reached. Only after a specific public CORS-enabled host succeeds
should external hosting be considered for larger assets. Check compatibility
of the full QAOA circuit, edited `K`, and IonQ transpilation in issues #2/#4/#5;
none of those are established by one qubit.

Live findings from both spike revisions, 2026-10-11:

| Probe | Backend / run | Observation or exact error | Verified? |
| --- | --- | --- | --- |
| JS import and Python preview after edit | Built-in and IonQ | `evidence.json` and `new-evidence-3.json`: edits reached Python; Aria 1 preview at x=3.2 covered B/20 of 60 | Yes |
| Packaged JSON and size | Built-in and IonQ | Original and new Aria 1 evidence: 228 bytes, matching SHA-256 | Yes |
| Draggable marker | Qollab app | User confirms dragging updated numeric coordinates and Python preview without a backend job | User-confirmed |
| First and second jobs, original JS path | Built-in | `evidence.json`: both returned `{"0": 32}` | Yes |
| First job, updated Python path | Built-in | `new-evidence-1.json`: x=0 yielded `{"0": 32}`; `new-evidence-2.json`: x=3 yielded 26 zeros and 6 ones (32 shots) | Yes |
| Second job, updated Python path | Built-in | User reports no additional errors, but both new files contain only `attempt: 1`; outcome not captured | User-reported |
| New Run reset and copy/paste recovery | Qollab app | User confirms edited inputs and job result reset on a new Run; manually pasting saved case JSON restored the Python preview | User-confirmed |
| External GET from public raw host | Built-in and IonQ | HTTP 200 in original evidence; new Aria 1 evidence did not run this probe | Yes (original) |
| First job, original JS path | IonQ remote sim | `evidence2.json`: four shots, first request failed in under a second with Pyodide/urllib3 `NetworkError when attempting to fetch resource` | Failure confirmed |
| First job, updated Python path | Aria 1 free remote sim | `new-evidence-3.json`: `ionq_simulator`, four shots, `path: python`, first request failed at `python_promising` with the same network error; no counts | Failure confirmed |
| Python-console control on same one-qubit circuit | Free IonQ simulators | User reports counts on some devices; one may stall during package loading. Device-level results not recorded | User-reported |
| Official JS/Qiskit Bell control | Aria 1 free remote sim | User reports the official "Bell state from JS and Python" project runs successfully | User-reported |
| First job, top-level-Run-pending spike | Aria 1 free remote sim | `new-evidence-4.json`: x=1.7/y=4.7, `path: python`, 4 shots returned `{"0": 4}` in 13.5 s | Yes |
| Second job after top-level Run completed | Aria 1 free remote sim | `new-evidence-5.json`: attempt 2 failed at `python_promising` with `NetworkError`; the script had already completed, so this does not isolate the one-job limit | Failure confirmed, cause ambiguous |
| First job while Run stays pending through second click | Aria 1 free remote sim | `new-evidence-6.json`: x=1.7/y=4.7, `path: python`, four shots returned `{"0": 4}` in 14.5 s | Yes |
| Second request while top-level Run stays pending | Aria 1 free remote sim | `new-evidence-7.json`: same `started_at` and revision as job 1; attempt 2 was rejected in 22 ms with `The code has already filed one circuit execution job; only one job is allowed per code run` | Yes, explicit limit |
| Fresh-Run allowance after earlier second-job failure | IonQ remote sim | `new-evidence-4.json` and `new-evidence-6.json` have different Run start times; another first job succeeded. Selected QPU name is user-reported, not embedded in JSON | Yes for new Run |

The user reports that the original JS project's first request failed on all
four free remote simulators (Aria 1/2 and Forte 1/Enterprise 1), while a
Qollab Python-console Bell example worked on those devices and this exact
one-qubit Python-console circuit returned counts on some. The updated spike
also failed on Aria 1 when its Python function called `backend.run` through
`.callPromising(backend, ...)`, but the official **JS/Qiskit** Bell project
worked there. Qollab's public Bell source calls its Python `run_bell` function
at the top level of `main.js`; the spike instead called its first quantum job
after `main.js` finished, on a later button click. Holding the top-level Run
pending allowed **one** Aria 1 job to return counts. This strongly supports a
backend-access lifetime issue for deferred jobs in this setup, although the
successful case's x coordinate also differed from the earlier failed case.
The second click in that earlier run happened after the script finished, so
its `NetworkError` did not establish the one-IonQ-job rule. On the subsequent
run, the script stayed pending through both clicks: the first Aria 1 job
returned counts and the second received the explicit one-job-per-run error.
For the app, keep the Run active while accepting edits and submit only one
final quantum job; use local Python calls for immediate classical previews.
The user confirmed that dragging the marker updates coordinates and the
Python preview without a job. Edits and quantum results reset on a new Run,
but copying the case JSON out and pasting it back restored the preview. The
v1 app needs an explicit manual copy/paste or other tested pre-Run input
handoff, a visible stale-result state, and a fresh Qollab Run for another
IonQ request. A working one-qubit spike does not establish that the full
QAOA circuit or the other IonQ simulators will work.
