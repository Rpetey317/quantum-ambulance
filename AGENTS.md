# Project guidance

- This is the Qollab x IonQ Quantum Impact ambulance-base placement hackathon project. Read `README.md` for current status, `Idea.pdf` for the original Spanish pitch, and `baseline.py` for the only implemented prototype.
- The repository currently has no app framework, backend, deployment setup, or test suite. Do not assume any has been chosen; clarify new app requirements with the team before fixing architecture or data sources.
- Keep prototype results separate from app capabilities. `baseline.py` uses synthetic population/coordinates, Euclidean coverage, local statevector optimization, and local `StatevectorSampler` sampling; it does not run on IonQ hardware.
- Preserve the distinction between the pairwise quadratic QAOA cost approximation and actual union-of-zones population coverage. Compare final selections using actual coverage and retain greedy/exact baselines for small instances.
- The Dicke initial state and XY mixer maintain exactly `K` selected sites; preserve that constraint if changing the circuit. Site indices in printed results are zero-based; Qiskit bitstrings are reversed when mapped to site indices.
- Be precise about claims: the pitch's 8-site example demonstrates solution quality and sampling probability, not a proven quantum speedup. Avoid representing a simple distance-radius model as actual emergency response time.
- For the existing prototype, the documented dependencies are Python with Qiskit 2.5.2, NumPy, and SciPy; run `python baseline.py` to check changes. Run `python -m unittest discover -s tests -v` for the deterministic suite (see `docs/TESTING.md`); CI runs it on every PR.
- The project is MIT-licensed (`LICENSE`). The pitch requests attribution for prior code and AI assistance in the hackathon submission; verify disclosures against actual work before publishing.
