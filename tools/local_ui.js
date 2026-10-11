import { mount } from "../ui/app.js";

async function request(path, data) {
  const response = await fetch(
    path,
    data === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
  );
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "Local preview request failed.");
  return result;
}
mount(document.getElementById("app"), {
  loadCase: (id) => request(`/api/case?id=${encodeURIComponent(id)}`),
  loadMap: (style) => request(`/api/map?style=${encodeURIComponent(style)}`),
  preview: (data) => request("/api/preview", data),
  backendInfo: async () => ({
    name: "Local test · BasicSimulator",
    class: "BasicSimulator",
    module: "qiskit.providers.basic_provider",
    is_simulator: true,
  }),
  runQuantum: (data, shots) => request("/api/quantum", { data, shots }),
});
