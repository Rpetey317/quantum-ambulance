"""Copy to Qollab's root main.py; package ambulance/, the fixture and requirements."""

from ambulance.bridge import run_quantum, synthetic_case


def main(shots: int = 64, layers: int = 3):
    chosen_backend = globals().get("backend")
    if chosen_backend is None:
        raise RuntimeError("Qollab must supply the visitor-selected backend")
    print(run_quantum(synthetic_case(), chosen_backend, shots=shots, layers=layers))


# Qollab automatically calls a correctly annotated main(); do not call it twice.
