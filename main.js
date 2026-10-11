import * as bridge from "ambulance.bridge";
import { mount } from "./ui/app.js";

// Qollab injects the visitor-selected backend; never instantiate a provider here.
mount(document.getElementById("app"), {
  loadCase: async (id) => JSON.parse(await bridge.case_data.callPromising(id)),
  preview: async (data) =>
    JSON.parse(await bridge.preview.callPromising(JSON.stringify(data))),
  backendInfo: async () =>
    JSON.parse(await bridge.describe_backend.callPromising(backend)),
  runQuantum: async (data, shots) =>
    JSON.parse(
      await bridge.run_quantum.callPromising(
        JSON.stringify(data),
        backend,
        shots,
      ),
    ),
});
