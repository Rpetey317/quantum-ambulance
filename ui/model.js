export const SITE_CAP = 8;
export const clone = (value) => JSON.parse(JSON.stringify(value));

export function boundsFor(data) {
  const points = [...data.zones, ...data.sites];
  if (!points.length) throw new Error("This dataset has no locations.");
  const xs = points.map((p) => p.x_km),
    ys = points.map((p) => p.y_km);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs);
  const minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const pad = Math.max(0.1, Math.max(maxX - minX, maxY - minY) * 0.06);
  return {
    minX: minX - pad,
    maxX: maxX + pad,
    minY: minY - pad,
    maxY: maxY + pad,
  };
}

export function validate(data, bounds) {
  if (
    !data.meta?.crs ||
    /4326|4269|lon.?lat|geographic/i.test(data.meta.crs) ||
    !/^km(?:\s|$)/.test(data.meta.coordinate_units || "")
  )
    throw new Error(
      "This editor requires projected Cartesian coordinates in km.",
    );
  if (!data.zones?.length) throw new Error("This dataset has no demand zones.");
  if (!data.sites?.length || data.sites.length > SITE_CAP)
    throw new Error(`Keep between 1 and ${SITE_CAP} candidate sites.`);
  const k = data.k ?? data.k_default;
  if (!Number.isInteger(k) || k < 1 || k > data.sites.length)
    throw new Error(
      "K must be an integer between 1 and the number of candidates.",
    );
  if (!Number.isFinite(data.radius_km) || data.radius_km <= 0)
    throw new Error("Coverage radius must be a positive number of km.");
  for (const collection of [data.zones, data.sites]) {
    const ids = new Set();
    for (const p of collection) {
      if (typeof p.id !== "string" || !p.id.trim() || ids.has(p.id))
        throw new Error("Locations need unique, nonempty IDs.");
      ids.add(p.id);
      if (!Number.isFinite(p.x_km) || !Number.isFinite(p.y_km))
        throw new Error("Coordinates must be finite numbers.");
    }
  }
  if (data.zones.some((z) => !Number.isFinite(z.weight) || z.weight <= 0))
    throw new Error("Demand weights must be finite and positive.");
  for (let i = 0; i < data.sites.length; i++) {
    const p = data.sites[i];
    if (
      p.x_km < bounds.minX ||
      p.x_km > bounds.maxX ||
      p.y_km < bounds.minY ||
      p.y_km > bounds.maxY
    )
      throw new Error("Keep candidates inside the displayed study extent.");
    if (
      data.sites
        .slice(0, i)
        .some((q) => Math.hypot(p.x_km - q.x_km, p.y_km - q.y_km) < 0.001)
    )
      throw new Error("Candidate sites must be at least 1 metre apart.");
  }
  return data;
}

export function edited(data, bounds, change) {
  const next = clone(data);
  change(next);
  validate(next, bounds);
  if (JSON.stringify(next) === JSON.stringify(data)) return data;
  next.meta.revision =
    typeof data.meta.revision === "number"
      ? data.meta.revision + 1
      : `${data.meta.revision}:edit`;
  return next;
}

export function removeSite(data, id) {
  if (data.sites.length <= 1) throw new Error("Keep at least one candidate.");
  data.sites = data.sites.filter((p) => p.id !== id);
  data.k = Math.min(data.k ?? data.k_default, data.sites.length);
}

export function restoreFields(original, saved) {
  if (
    saved.meta?.id !== original.meta.id ||
    saved.meta.crs !== original.meta.crs ||
    saved.meta.coordinate_units !== original.meta.coordinate_units
  )
    throw new Error(
      "Snapshot dataset and coordinate system must match the packaged case.",
    );
  const sites = saved.sites.map((p) => {
    const seed = original.sites.find((s) => s.id === p.id);
    return {
      ...seed,
      id: p.id,
      x_km: p.x_km,
      y_km: p.y_km,
      edited_candidate: !seed || seed.x_km !== p.x_km || seed.y_km !== p.y_km,
    };
  });
  const fields = {
    sites,
    k: saved.k ?? saved.k_default,
    radius_km: saved.radius_km,
  };
  validate({ ...original, ...fields }, boundsFor(original));
  return fields;
}

export function matches(result, identity) {
  return (
    !!result &&
    !!identity &&
    ["case_id", "case_revision", "input_fingerprint"].every(
      (key) => result[key] === identity[key],
    )
  );
}

export function overlay(result, identity) {
  if (!matches(result, identity) || result.status !== "ok")
    return { sites: new Set(), zones: new Set() };
  return {
    sites: new Set(result.selected_site_ids),
    zones: new Set(result.covered_zone_ids),
  };
}

// The packaged CABA backgrounds are rendered over a shared EPSG:9498 km frame;
// only cases on that coordinate system can use them.
export const cabaFrame = (data) => /9498/.test(data?.meta?.crs || "");
export const MAP_STYLES = ["streets", "satellite", "abstract", "plain"];
export const defaultMapStyle = (data) =>
  cabaFrame(data) ? "streets" : "abstract";
export function mapBackground(data, style, imageReady) {
  if (!data || style === "plain") return "plain";
  if (style === "streets" || style === "satellite") {
    if (!cabaFrame(data)) return "abstract";
    return imageReady ? "image" : "plain";
  }
  return "abstract";
}

export function backendPolicy(info) {
  const ionq = /ionq/i.test(
    `${info?.module || ""} ${info?.name || ""} ${info?.class || ""}`,
  );
  const knownLocal =
    !ionq &&
    /basic_provider|fake_provider|qiskit_aer|braket.*local_simulator/i.test(
      info?.module || "",
    );
  return {
    singleJob: !knownLocal,
    shotCap: ionq ? 128 : 4096,
    unsupported: ionq && info?.is_simulator !== true,
  };
}
