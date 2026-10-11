# Standalone public web app

Public app: https://quantum-ambulance.vercel.app.

The Vercel app reuses `ui/`, `ambulance.core`, and `ambulance.quantum`. Its
transport is `web/main.js`; the original root `main.js` remains the Qollab entrypoint.
`npm run build` wraps the shared HTML fragment and copies only web runtime assets
to `dist/`. Vercel serves these files and the Python handler `api/index.py`.

The public web backend is **Qiskit BasicSimulator on Vercel**, not an IonQ device
or the Qollab visitor-selected backend. The page links to Qollab for that workflow.
It performs the same local angle optimization and exactly one simulator sampling
job per accepted quantum request. Actual union coverage, case identities, stale
results, bit order, invalid-shot filtering and separated timing fields retain the
shared contract. Sampling varies between runs; matching the optimum is not guaranteed.

Public limits: 16 sites for editing/classical comparisons, 4,000 zones, 2 MB request
bodies, **8 sites and 128 shots for QAOA**, three layers, two restarts and 150
optimizer evaluations per restart. Exact search retains the documented 10,000
combinations / 5,000,000 zone-work cutoff. A process-local semaphore rejects
simultaneous QAOA calls with 429; it is not a global quota. Vercel's function
timeout is 60 seconds. No provider credentials, remote QPU jobs, accounts,
database or persistence are used. Cases can be exported from the editor.

## Deployment

Python 3.13 and `requirements.txt` provide the server runtime. Node 22+ builds
the static shell without npm dependencies. The output directory and function
settings are in `vercel.json`; `.vercelignore` excludes local videos, branding,
raw data and development artifacts. The Python bundle also excludes static assets.
This dependency bundle requires Vercel's Large Functions beta on Fluid compute:
set `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` for production and previews in project
environment settings. This was enabled for the published project.

```sh
npm run build
npm test
python -m unittest discover -s tests -v
vercel link --project quantum-ambulance
vercel git connect https://github.com/Rpetey317/quantum-ambulance
vercel --prod
```

Git-connected production deploys follow `main`; other branches can receive
previews. Keep Vercel's local project metadata and all credentials out of Git.
Vercel deployment protection can protect preview URLs; production must be public
for visitors to use it without a Vercel account.

Native Git linking requires the Vercel GitHub integration to be installed with
access to `Rpetey317/quantum-ambulance`. A manual deployment works independently
of that integration; enabling Git access is an account/repository-owner action.

## Observed validation

On 2026-10-11: 80 Python tests and 27 Node UI tests passed. Real Chrome tested
the deployed HTTP transport without Vercel login: all three cases, street and
satellite assets, changed K, stale QAOA handling, nine-site classical preview
with QAOA disabled, and a 390px mobile layout without horizontal overflow.
One 16-shot simulator request returned 16 valid exactly-K shots and 84.0% best
actual coverage for Comuna 4 (exact: 85.1%). Local tuning took 1.972s, transpilation
0.026s and the single backend job 0.014s. These timings belong to this sampled
run, not a speed claim. `tests/browser_web.py --url URL` repeats that smoke check
with one simulator job; screenshots/results are written to ignored `.vercel/`.

Software is MIT; the existing UI preserves census-data and map attributions.
This remains a research proof of concept using distance-radius coverage, not
road routing, dispatch or a demonstrated quantum speedup. The standalone adapter
and deployment configuration were developed with OpenAI Codex assistance.
