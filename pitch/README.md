# Three-minute pitch kit

Prepared 11 October 2026 against current main plus the team's existing QA fix.
The delivery language is English; a human presenter supplies the voiceover.
Prepared with AI assistance (Codex) for research, narration, demo automation and Pitchr rehearsal. The existing QA fix comes from [team PR #14](https://github.com/Rpetey317/quantum-ambulance/pull/14); original project/code credits remain with their contributors. Confirm all team and prior-work disclosures for the official hackathon submission.

- [Spoken script](script-en.txt): 374 words, about 2:53 at 130 words/minute, leaving seven seconds for pauses.
- [Subtitle template](narration.srt): timed to the 3:00 plan; adjust to your actual human narration before exporting.
- [Demo cues and edit plan](DEMO.md): exact actions, timing, preflight and recovery.
- [Primary research and claim boundaries](RESEARCH.md): sources, dates and reproducible coverage calculations.
- [Business hypothesis and judge questions](QA.md): proposed buyer, pilot economics, validation gates and short answers.
- [Actual Pitchr evaluations](JUDGE_REVIEW.md): AI-persona results and evidence gaps; these are not endorsements by the named people.
- [Recorded app fallback](media/demo-local.mp4): 89 seconds, 1920×1080 H.264; real local browser footage with a persistent simulator label. The recording uses local **Qiskit BasicSimulator**, has **no narration**, and is not proof of Qollab, remote IonQ or hardware execution. Screenshots and the sampled-result evidence are in `media/`.

## Use it now

1. Rehearse the script once with a stopwatch. Aim for 2:55; cut commentary before cutting the closing request.
2. Put the app or the recorded fallback on the presentation machine. Use the preflight in [DEMO.md](DEMO.md). Keep the backend identity visible.
3. Record the opening and close on camera. Place the app clip between approximately 0:40 and 2:09, with your voiceover continuing throughout.
4. Verify a final export is no longer than 3:00, includes the source/data attribution and has legible metrics. Do not upload the silent rehearsal clip as a finished narrated pitch.

The useful promise is to **test a deployment decision before committing resources**. The demonstrated result is **8,890 additional modelled residents inside a distance radius with the same three selected bases**, relative to greedy in the curated Comuna 4 case. Patient survival, operational cost savings, sales traction and quantum advantage require further evidence.

## Validation observed

After pulling main, the data validator rejected the synthetic fixture because it required census-generation fields from all cases. This branch incorporates `origin/qa/issue8-fix-ci`, the team's existing fix. The resulting checkout passed 74 Python tests, 24 JavaScript tests, dataset validation, and real Chrome integration. The recorded demo additionally checks the displayed coverage, edited revision, stale-result exclusion, full-city equality and exactly one local sampled job.

The full ambulance app still needs recorded Qollab/selected-backend evidence. [QOLLAB.md](../QOLLAB.md) does document successful **one-qubit platform-spike** jobs on an IonQ remote simulator and its one-job limit; those do not establish a full ambulance QAOA run. A remote runtime fix in the app source alone does not establish that run.
