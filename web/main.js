import { mount } from "./ui/app.js";

async function request(url, data) {
  const response = await fetch(url, data === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await response.json().catch(() => {
    throw new Error("The server could not finish this request. Please try again later.");
  });
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}

const maps = {
  streets: "Street map © OpenStreetMap contributors, rendered from the BBBike Buenos Aires extract",
  satellite: "Contains modified Copernicus Sentinel-2 data (2024), rendered via Microsoft Planetary Computer",
};
mount(document.getElementById("app"), {
  loadCase: id => {
    if (!["synthetic", "caba-comuna4", "caba"].includes(id)) throw new Error("Unknown case.");
    return request(`/data/cases/${id}.json`);
  },
  loadMap: async style => {
    if (!Object.hasOwn(maps, style)) throw new Error("Unknown map style.");
    return { image: `/data/map/caba-${style}.webp`,
      bounds: { minX: 11, maxX: 33, minY: 60, maxY: 83 }, attribution: maps[style] };
  },
  preview: data => request("/api?action=preview", data),
  backendInfo: () => request("/api"),
  runQuantum: (data, shots) => request("/api?action=quantum", { data, shots }),
});
