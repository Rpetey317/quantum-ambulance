# Evidence behind the pitch

Checked 11 October 2026. Dates below distinguish publication from observation. These are external context, repository measurements or explicitly labelled hypotheses; they cannot be combined into a claimed number of lives saved.

## Primary-source context

| Source | Verified fact | Correct use / boundary |
| --- | --- | --- |
| [American Heart Association, 2026 statistics update, top takeaways](https://www.heart.org/-/media/PHD-Files-2/Science-News/2/2026-Heart-and-Stroke-Stat-Update/Top-Takeaways-from-the-2026-AHA-Heart-Disease-and-Stroke-Statistics-Update-PDF.pdf), second PDF page, item 6 | U.S. out-of-hospital cardiac-arrest survival to hospital discharge was **10.5% in 2024**. | Establishes clinical stakes. It is not an Argentine survival rate or an app result. |
| [Bürger, Wnent et al., German Resuscitation Registry study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6156551/), 2018, eTable 4 | The adjusted continuous model estimates discharge-survival odds ratio **0.951 per extra response minute**, 95% CI **0.93–0.97**; analysis covers 10,853 patients, 2010–2016. | About **4.9% lower odds**, not five percentage points lower survival. Retrospective association; response means alarm to first vehicle arrival, not driving alone. No causal effect from this app follows. |
| [MedPAC June 2026 report, chapter 6](https://www.medpac.gov/wp-content/uploads/2026/06/Jun26_Ch6_MedPAC_Report_To_Congress_SEC.pdf), printed p.255 / PDF p.7 | In **2024**, about **10,600** providers/suppliers delivered **11.3 million** Medicare FFS ground-ambulance transports; AFS-covered Medicare payments were **$5.3bn**. | Payment-system context, not software TAM, emergency-only spending or recoverable savings. |
| [GCBA census-tract open data](https://data.buenosaires.gob.ar/dataset/informacion-censal-por-radio) | The packaged population weights derive from the **2010 national census**. | Credit GCBA Datos Abiertos / INDEC, Censo Nacional 2010, CC-BY-2.5-AR. Dataset-page update date does not make those weights current. |
| [GCBA SAME operational description](https://buenosaires.gob.ar/gcaba_historico/salud/noticias/el-trabajo-del-same-en-detalle), **1 August 2022** | Reports roughly **350,000 annual medical actions**, **2,700 calls/day**, and **14 extrahospital bases**. | Optional local context only, dated 2022. These categories are not unique cardiac-arrest incidents or current fleet counts. Do not infer demand incidence from them. |
| [SAME institutional remit](https://buenosaires.gob.ar/perfil_institucional/direccion-general-sistema-de-atencion-medica-de-emergencia-same), page updated 6 April 2026 | SAME's directorate coordinates human, technical and financial resources for emergency care. | Supports a proposed operator/planning contact. It does not establish interest, procurement budget, access to call data or a partnership. |

The speech deliberately uses just three external numerical claims: survival, response-time odds association and payment context. Keep their geography, year and denominator attached.

## Reproducible repository evidence

Coverage is the sum of zone weights within the radius of **at least one** selected candidate. Overlap is counted once. All sites are hypothetical candidate choices based on seed institutions, not a representation of the deployed SAME ambulance network.

| Case | Zones / candidates / K / radius | Greedy | Exact | Interpretation |
| --- | --- | --- | --- | --- |
| Comuna 4 | 252 / 8 / 3 / 1.8 km | 176,818 / 218,245 = **81.0181%**; indices [1, 2, 7] | 185,708 / 218,245 = **85.0915%**; [2, 3, 7] | **8,890** more modelled residents; **4.0734 percentage points**. The eight sites were chosen from eleven to maximize this gap; selection bias is disclosed. |
| Full CABA | 3,552 / 8 / 3 / 3 km | 1,682,455 / 2,890,151 = **58.2134%**; [0, 2, 6] | Same | More zones improve demand resolution but do not enlarge the candidate search; both eight-site cases have only 56 combinations. |
| Original synthetic | 15 / 8 / 3 / 3 km | **1,845 thousand**; [2, 5, 6] | **2,086 thousand**; tied [1, 2, 5], [2, 4, 5] | Invented demonstration weights. Never describe the gap as observed residents or patients. |

Comuna 4 also has a **5.0279% relative covered-weight increase** and **21.459% reduction in uncovered weight**. Those use different denominators; use the count difference in the main speech. None is a survival effect.

Run from the repository root:

```powershell
python -c "import json; from pathlib import Path; from ambulance.core import evaluate_case; r=evaluate_case(json.loads(Path('data/cases/caba-comuna4.json').read_text())); print(r['greedy']['covered_weight'], r['exact']['covered_weight'])"
```

For the site's demo edit, move candidate index 0 from x=26.5496 to x=27.0496 km at unchanged y=69.9225. Revision 2 shows greedy **177,449**, exact **185,708**, and stale quantum output. Moving a point invalidates derived quantum components even when the exact winning set stays unchanged.

The local recording saves its backend identity, counts, result revision, one-job counter and timing components in [media/evidence.json](media/evidence.json). Optimizer convergence and sampling probability must be read from that run; they are not guaranteed. A small sample reaching exact is not proof of a computational advantage.

In the saved take, the local best sample covers **185,708**, all **64/64** shots have K=3, and **2/64** are optimal. The observed optimum frequency is **3.125%**, versus a uniform reference of **1/56 = 1.786%**. This small sample does not establish reliable amplification. Local angle tuning took **4.560 s**, transpilation **0.220 s**, and backend/job wall time **0.036 s** on this machine. COBYLA reached its evaluation budget; the result explicitly reports **not converged**. The best sample matching exact does not mean the optimizer converged.

## Compare against the actual state of the field

[Hexagon's EMS product page](https://hexagon.com/industries/public-safety/emergency-medical-services) already describes dispatch and resource-deployment support. [FirstWatch](https://firstwatch.net/ems/) already offers EMS monitoring/analytics. This prototype cannot claim to invent ambulance planning or to be the first such dashboard.

[Guigues, Kleywegt and Nascimento, ambulance-fleet heuristics](https://arxiv.org/abs/2409.09158v3), revised 8 March 2026, studies classical stochastic deployment/dispatch methods. A future quantum comparison needs stronger classical references and matched end-to-end resources; a greedy gap alone is insufficient.

## Claims requiring new evidence

“Saves lives”: needs verified operational response improvement and appropriately evaluated patient outcomes. Census-radius coverage alone cannot estimate it.

“Saves money”: needs measured operator resource use and costs, including extra relocation, staffing, integration and solver expense. Medicare reimbursement per mile is not a marginal operating-cost estimate.

“Quantum advantage”: needs quality/runtime/cost benchmarks versus competitive classical solvers across larger candidate counts, including local tuning and backend wait. The current local statevector optimizer scales exponentially.

“Runs on IonQ hardware”: requires actual job evidence for that hardware. Local simulator results, offline payload conversion and a remote-runtime source fix do not establish a hardware run.

“World-changing business”: an ambition. Customer pain, willingness to pay, procurement, repeatable integration and defensibility remain unvalidated.
