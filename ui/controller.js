import {
  boundsFor,
  validate,
  edited,
  matches,
  backendPolicy,
  clone,
} from "./model.js";

export class Controller {
  constructor(transport, onChange = () => {}) {
    this.transport = transport;
    this.onChange = onChange;
    this.generation = 0;
    this.loadRequest = 0;
    this.sessionReserved = false;
    this.state = {
      data: null,
      bounds: null,
      comparison: null,
      quantum: null,
      quantumState: "not_run",
      previewState: "loading",
      error: "",
      backend: null,
      busy: false,
    };
  }
  emit() {
    this.onChange(this.state);
  }
  async init(id = "caba-comuna4") {
    const backendTask = this.transport
      .backendInfo()
      .then((info) => {
        this.state.backend = info;
        this.emit();
      })
      .catch((error) => {
        this.state.backendError = error.message;
        this.emit();
      });
    await this.load(id);
    await backendTask;
  }
  async load(id) {
    const request = ++this.loadRequest;
    ++this.generation;
    this.state.quantumState =
      this.state.quantum || this.state.busy ? "stale" : "not_run";
    this.state.previewState = "loading";
    this.state.error = "";
    this.emit();
    try {
      const data = await this.transport.loadCase(id);
      if (request !== this.loadRequest) return;
      const bounds = boundsFor(data);
      validate(data, bounds);
      // Supersede previews/edits that occurred while this asset was loading.
      ++this.generation;
      this.state.data = data;
      this.state.bounds = bounds;
      this.state.comparison = null;
      this.state.quantumState =
        this.state.quantum || this.state.busy ? "stale" : "not_run";
      await this.refresh();
    } catch (error) {
      if (request !== this.loadRequest) return;
      this.state.data = null;
      this.state.comparison = null;
      this.state.previewState = "failed";
      this.state.error = error.message;
      this.emit();
    }
  }
  edit(change) {
    try {
      const next = edited(this.state.data, this.state.bounds, change);
      if (next === this.state.data) {
        this.state.error = "";
        this.emit();
        return Promise.resolve(false);
      }
      this.state.data = next;
      ++this.generation;
      this.state.quantumState =
        this.state.quantum || this.state.busy ? "stale" : "not_run";
      this.state.error = "";
      return this.refresh();
    } catch (error) {
      this.state.error = error.message;
      this.emit();
      return Promise.resolve(false);
    }
  }
  async refresh() {
    const generation = this.generation;
    const snapshot = clone(this.state.data);
    this.state.comparison = null;
    this.state.previewState = "loading";
    this.emit();
    try {
      const comparison = await this.transport.preview(snapshot);
      if (generation !== this.generation) return false;
      if (
        comparison.case_id !== snapshot.meta.id ||
        comparison.case_revision !== snapshot.meta.revision
      )
        throw new Error(
          "Preview returned a different case revision. Reload the dataset.",
        );
      this.state.comparison = comparison;
      this.state.previewState = "ok";
      this.emit();
      return true;
    } catch (error) {
      if (generation !== this.generation) return false;
      this.state.previewState = "failed";
      this.state.error = error.message;
      this.emit();
      return false;
    }
  }
  canRun() {
    const policy = backendPolicy(this.state.backend);
    return (
      this.state.previewState === "ok" &&
      !this.state.busy &&
      !!this.state.backend &&
      !policy.unsupported &&
      !(policy.singleJob && this.sessionReserved)
    );
  }
  async run(shots = 64) {
    if (!this.canRun()) return false;
    const policy = backendPolicy(this.state.backend);
    if (!Number.isInteger(shots) || shots < 1 || shots > policy.shotCap) {
      this.state.error = `Shots must be an integer between 1 and ${policy.shotCap}.`;
      this.emit();
      return false;
    }
    const generation = this.generation,
      identity = this.state.comparison;
    const snapshot = clone(this.state.data);
    if (policy.singleJob) this.sessionReserved = true;
    this.state.busy = true;
    this.state.quantumState = "running";
    this.state.error = "";
    this.emit();
    try {
      const result = await this.transport.runQuantum(snapshot, shots);
      const quantum = result.qaoa;
      if (!matches(quantum, identity))
        throw new Error("Quantum response does not match the submitted case.");
      this.state.quantum = quantum;
      this.state.quantumState =
        generation === this.generation ? quantum.status : "stale";
    } catch (error) {
      this.state.quantum = null;
      this.state.quantumState =
        generation === this.generation ? "failed" : "stale";
      this.state.quantumError = error.message;
    } finally {
      this.state.busy = false;
      this.emit();
    }
    return true;
  }
}
