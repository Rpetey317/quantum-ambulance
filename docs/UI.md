# Interactive map and comparison (#6 / #7)

Root `index.html`, `main.js`, `main.css` provide a minimal JS/Qiskit Qollab shell.
`ui/app.js` exports `mount(root, transport)` so the scaffold workstream can
replace the shell without rewriting editor/comparison behaviour. No framework,
geographic tile service or production HTTP backend is introduced.

## Local preview and checks

From repository root, with `requirements.txt` installed:

```bash
python -m tools.preview_ui
```

Open `http://127.0.0.1:8765`. This localhost-only QA harness serves the real
Python JSON bridge. Its quantum button uses **local BasicSimulator**, labelled
in the UI; it never creates providers or submits remote jobs. Stop with Ctrl+C.
Without Qiskit installed, classical editing works and quantum reports the
missing dependency.

```bash
npm test
python -m unittest discover -s tests -v
python -m pip install playwright
python tests/browser_ui.py --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

Alternatively omit `--browser` after `playwright install chromium`. Browser
screenshots go to the system temporary directory (`ambulance-ui-qa`). Runtime
UI has no npm dependencies/build step; Node is only for controller/model tests.

## Qollab packaging and smoke procedure

Upload root `index.html`, `main.js`, `main.css`, `requirements.txt`, all four
`ui/*.js` files, the `ambulance/` package and three `data/cases/*.json` assets,
preserving paths. Do not use `tools/local_ui.js` or the local HTTP harness as a
Qollab entrypoint. Root HTML contains body content only; Qollab loads the single
`main.css` and executes `main.js`.

The shell uses relative JS imports and dotted Python imports with
`.callPromising`. Python names packaged data paths as literals; JS never fetches
project assets. The global visitor-selected `backend` is passed to the adapter;
there is no provider selection, enumeration, sampler fallback or retry.

1. Select the built-in simulator in a Qollab Run. Load all cases, drag and
   numerically edit candidates, change K, remove/add a site, and compare layers.
2. Sample eight shots. Check exactly-K validity, separate local tuning and
   backend/job wall time, then edit again and verify quantum staleness.
3. Copy portable JSON, Stop, start a new Run, paste and restore. Edits reset;
   restore uses original demand zones/provenance and saved candidate edits.
4. After platform/circuit/shot-cost checks, select an IonQ **simulator** in a new
   Run and use 64 shots. The UI reserves one attempt before awaiting the bridge,
   including failures. Resetting a dataset does not replenish it. Hardware and
   unidentified IonQ simulator identity are blocked. Record actual observations.

Runtime/reset constraints follow the official
[JS project docs](https://qollab.xyz/learn/docs/js-qiskit-projects) and
[runtime docs](https://qollab.xyz/learn/docs/runtime-environment).
Actual Qollab and IonQ remote checks have **not** been run by this implementation.

## Editor and result behaviour

- All three cases are selectable. Full CABA retains all 3,552 centroids. Canvas
  is only a display layer: all solvers use the original full-resolution zones.
  No administrative polygon or aggregated weights are invented.
- Bounds are a fixed 6%-padded extent of original zones/sites (minimum padding
  0.1 km). Equal x/y scale preserves metric distances; north points up. Coverage
  means centroid distance-radius coverage, never road travel time.
- IDs remain stable; marker labels and result indices are zero-based current
  array positions. Drag, numeric coordinates and arrow keys (100 m, Shift 10 m)
  edit candidate bases. Institution names remain labelled seed provenance.
- One to eight sites, positive finite radius, `1 <= K <= N`, finite coordinates
  inside the extent, and at least one metre between candidates are enforced.
  Removal clamps K. New candidate IDs avoid collisions.
- Every accepted edit increments revision and recomputes both classical methods
  in Python. Classical layers disappear while recomputing. Generation guards
  discard late responses, including edits during asset loading. Repeated commits
  of identical inputs do not invalidate results.
- Quantum layers require matching case ID, revision and fingerprint. Not-run,
  running, unavailable, failed/unsupported, all-invalid and stale states display
  explicitly. Stale metrics/layers are withheld. Current failed/all-invalid
  results retain shot/timing diagnostics when available.
- Percentages use true union covered weight / the same total weight. Timings
  come directly from the contract; queue/execution-only estimates are not
  invented. Optimum probabilities require a matching exact result; otherwise
  they read “Not evaluated”. Approximate QAOA energy is never coverage.
- Manual copy/restore avoids unavailable Qollab persistent storage. Source
  assets retain GCBA/INDEC attribution and CC-BY-2.5-AR provenance.

## Observed validation

On 2026-10-11, local Chrome checks passed at 1440 px and 390 px: all datasets,
real Python previews, compact/full-case dragging, numeric edits, duplicate
rejection, site cap, safe K on removal, add, matching selected-site overlay,
portable restore, and a real eight-shot BasicSimulator job followed by staleness.
The browser test also injects transport fixtures for exact-unavailable,
all-invalid, unsupported-backend and missing-asset displays; those are not
remote-backend observations. Screenshot inspection confirmed readable mobile
layout with no horizontal overflow. Controller tests cover async races and the
single-attempt IonQ budget. The full regression suite passes 35 Python and 18
JavaScript tests. Design rationale: [UI_DESIGN.md](UI_DESIGN.md).

UI/editor/bridge/tests/docs were developed with OpenAI Codex assistance.
