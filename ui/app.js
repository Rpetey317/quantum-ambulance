import { Controller } from "./controller.js";
import {
  SITE_CAP,
  overlay,
  matches,
  removeSite,
  backendPolicy,
  restoreFields,
} from "./model.js";
import { MetricMap } from "./map.js";

const colors = { greedy: "#a85912", exact: "#007d83", qaoa: "#7150ad" };
const names = { greedy: "Greedy", exact: "Bounded exact", qaoa: "QAOA" };
const number = (value) =>
  new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value);
const seconds = (value) =>
  Number.isFinite(value) ? `${value.toFixed(3)} s` : "—";
const pct = (value) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "Not evaluated";
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function metric(list, label, value) {
  list.append(node("dt", label), node("dd", value));
}

export function mount(root, transport) {
  const $ = (selector) => root.querySelector(selector);
  let active = null,
    method = "greedy",
    nextSite = 1,
    currentDataset = "caba-comuna4";
  const map = new MetricMap(
    $("#map"),
    (id) => {
      active = id;
      render(controller.state);
    },
    (id, position) => {
      const before = controller.state.data?.sites.find((p) => p.id === id);
      if (
        before &&
        before.x_km === position.x_km &&
        before.y_km === position.y_km
      )
        return;
      controller.edit((data) => {
        const site = data.sites.find((p) => p.id === id);
        Object.assign(site, position, { edited_candidate: true });
      });
    },
  );
  const controller = new Controller(transport, render);
  function render(state) {
    const data = state.data,
      comparison = state.comparison;
    $("#error").hidden = !state.error;
    $("#error").textContent = state.error;
    $("#case-summary").textContent = data
      ? `${number(data.zones.length)} demand zones · ${data.sites.length} candidates · revision ${data.meta.revision}`
      : state.previewState === "loading"
        ? "Loading the study area…"
        : "No study area loaded";
    $("#map-empty").hidden = !!data;
    $("#map-empty").textContent =
      state.previewState === "failed"
        ? "Could not load this case. Choose a dataset to try again."
        : "Loading demand zones…";
    if (data && !data.sites.some((p) => p.id === active))
      active = data.sites[0].id;
    const result = method === "qaoa" ? state.quantum : comparison?.[method];
    const validLayer =
      state.previewState === "ok" &&
      (method !== "qaoa" || state.quantumState === "ok");
    root.style.setProperty("--layer-color", colors[method]);
    map.update(
      data,
      state.bounds,
      overlay(validLayer ? result : null, comparison),
      active,
      colors[method],
    );
    $("#map-method").textContent =
      validLayer && result?.status === "ok"
        ? `${names[method]} coverage`
        : "No current coverage layer";
    $("#map-method").style.color = colors[method];
    $("#coordinates button").disabled = !data;
    $("#export").disabled = !data;
    for (const id of [
      "k",
      "radius",
      "candidate",
      "x",
      "y",
      "add",
      "remove",
      "reset",
    ])
      $(`#${id}`).disabled =
        !data || (state.previewState === "loading" && !comparison);
    // Edits remain possible while a quantum job runs; it becomes stale on edit.
    if (data) {
      for (const id of ["k", "radius", "candidate", "x", "y", "reset"])
        $(`#${id}`).disabled = false;
      $("#k").value = data.k ?? data.k_default;
      $("#k").max = data.sites.length;
      $("#radius").value = data.radius_km;
      $("#candidate").replaceChildren(
        ...data.sites.map((site, i) => {
          const option = node("option", `${i}: ${site.id}`);
          option.value = site.id;
          return option;
        }),
      );
      $("#candidate").value = active;
      const site = data.sites.find((p) => p.id === active);
      $("#x").value = site.x_km;
      $("#y").value = site.y_km;
      $("#seed-note").textContent = site.name
        ? `${site.edited_candidate ? "Edited candidate. Original seed" : "Seed location"}: ${site.name}. Editing does not move the actual institution.`
        : "Candidate ambulance-base location.";
      $("#add").disabled = data.sites.length >= SITE_CAP;
      $("#remove").disabled = data.sites.length <= 1;
      $("#site-limit").textContent =
        `${data.sites.length} / ${SITE_CAP} candidates. Marker numbers are zero-based; IDs stay stable.`;
      $("#revision-note").textContent =
        `${data.meta.id} · revision ${data.meta.revision}${state.previewState === "loading" ? " · recomputing classical coverage…" : ""}`;
      const provenance = $("#provenance");
      provenance.replaceChildren();
      for (const text of [
        data.meta.zone_resolution,
        `Coordinate system: ${data.meta.crs}.`,
        data.meta.weight_source,
        data.meta.site_selection,
        data.meta.license_note,
      ])
        if (text) provenance.append(node("p", text));
      for (const source of data.meta.sources) {
        const p = node("p");
        p.append(
          node(
            "span",
            `${source.name || source.key || "Source"} · ${source.license || ""} `,
          ),
        );
        const url = source.dataset_page || source.url;
        if (/^https:\/\//.test(url || "")) {
          const a = node("a", "Source dataset");
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          p.append(a);
        }
        provenance.append(p);
      }
    }
    const policy = backendPolicy(state.backend);
    $("#shots").max = policy.shotCap;
    $("#run").disabled = !controller.canRun();
    $("#run").textContent = state.busy
      ? "QAOA running…"
      : "Run QAOA on selected backend";
    $("#backend-note").textContent = state.backend
      ? `${state.backend.name || state.backend.class || "Selected backend"}. ${policy.unsupported ? "Only identified IonQ simulators are enabled. Select a simulator in a new Qollab Run." : policy.singleJob && controller.sessionReserved ? "This session’s quantum attempt is used. Copy your case and start a new Qollab Run to sample again." : `${policy.shotCap} shots maximum. ${policy.singleJob ? "One quantum attempt per Qollab Run." : "One sampled job per click."}`}`
      : state.backendError
        ? `Backend unavailable: ${state.backendError}. Start a Qollab Run and select a supported simulator.`
        : "Checking the selected backend…";
    const methods = $("#methods");
    methods.replaceChildren();
    for (const key of ["greedy", "exact", "qaoa"]) {
      const q = key === "qaoa";
      const r = q ? state.quantum : comparison?.[key];
      const status = q
        ? state.quantumState
        : state.previewState === "loading"
          ? "running"
          : r?.status || "failed";
      const current =
        state.previewState === "ok" &&
        status === "ok" &&
        matches(r, comparison);
      const article = node("article", undefined, "method");
      article.style.setProperty("--method-color", colors[key]);
      article.dataset.method = key;
      const heading = node("div", undefined, "method-title");
      heading.append(node("h3", names[key]));
      const button = node("button", "Show on map");
      button.disabled = !current;
      button.setAttribute("aria-pressed", String(method === key && current));
      button.addEventListener("click", () => {
        method = key;
        render(controller.state);
      });
      heading.append(button);
      article.append(heading);
      const statusText =
        {
          not_run: "Not run",
          running: q ? "Local tuning + backend job in progress" : "Recomputing",
          stale: "Stale after a case edit",
          failed: "Failed / unsupported",
          no_valid_sample: "No valid exactly-K sample",
          unavailable: "Exact search unavailable",
          ok: "Current case",
        }[status] || status;
      article.append(node("p", statusText, "status"));
      if (current) {
        article.append(
          node("p", `${r.coverage_pct.toFixed(1)}%`, "percentage"),
        );
        article.append(
          node(
            "p",
            `${number(r.covered_weight)} / ${number(r.total_weight)} ${r.weight_units} covered`,
            "coverage",
          ),
        );
        article.append(
          node(
            "p",
            `Sites ${r.selected_site_indices.join(", ")} · ${r.selected_site_ids.join(", ")}`,
            "selection",
          ),
        );
      } else {
        article.append(node("p", "—", "percentage"));
        const message =
          status === "stale"
            ? `Previous quantum result is excluded. Run again for revision ${data?.meta.revision ?? "—"}.`
            : status === "not_run"
              ? "Choose a simulator in Qollab, then sample this case."
              : status === "running"
                ? q
                  ? "The bridge returns after tuning and the backend result; separate elapsed times appear on completion."
                  : "Rebuilding coverage and both classical baselines."
                : r?.message ||
                  (q ? state.quantumError : state.error) ||
                  "No result available.";
        article.append(node("p", message, "method-message"));
      }
      // Failed and all-invalid CURRENT runs still expose their shot and timing diagnostics.
      const diagnostics =
        matches(r, comparison) && status !== "stale" && status !== "running";
      if (diagnostics) {
        const dl = node("dl");
        metric(dl, "Coverage preparation", seconds(r.timings.coverage_s));
        if (!q) metric(dl, "Classical solve", seconds(r.timings.solve_s));
        else {
          metric(
            dl,
            "Circuit preparation",
            seconds(r.timings.quantum_prepare_s),
          );
          metric(
            dl,
            "Local angle tuning",
            seconds(r.timings.local_optimization_s),
          );
          metric(dl, "Transpilation", seconds(r.timings.transpile_s));
          metric(
            dl,
            "Backend / job wall time",
            seconds(r.timings.backend_job_s),
          );
          metric(
            dl,
            "Measured / requested shots",
            `${r.shots ?? 0} / ${r.requested_shots ?? "—"}`,
          );
          metric(
            dl,
            "Valid exactly-K shots",
            `${r.valid_shots ?? 0} (${pct(r.valid_shot_rate)})`,
          );
          metric(
            dl,
            "Rejected / malformed",
            `${r.invalid_shots ?? 0} / ${r.malformed_shots ?? 0}`,
          );
          metric(dl, "P(optimum), all shots", pct(r.optimal_probability));
          metric(
            dl,
            "P(optimum), valid shots",
            pct(r.optimal_probability_given_valid),
          );
          metric(
            dl,
            "Backend",
            r.backend?.name || state.backend?.name || "Unknown",
          );
          if (r.optimizer)
            metric(
              dl,
              "Local tuning converged",
              r.optimizer.converged
                ? "Yes"
                : "No (budget reached / see message)",
            );
          if (r.counts) {
            const details = node("details");
            details.append(
              node("summary", "Measured bitstring counts"),
              node("pre", JSON.stringify(r.counts, null, 2)),
            );
            article.append(details);
          }
        }
        article.append(dl);
      }
      methods.append(article);
    }
  }
  $("#dataset").addEventListener("change", async (event) => {
    currentDataset = event.target.value;
    active = null;
    await controller.load(currentDataset);
  });
  $("#candidate").addEventListener("change", (event) => {
    active = event.target.value;
    render(controller.state);
  });
  $("#k").addEventListener("change", (event) =>
    controller.edit((data) => {
      data.k = event.target.value === "" ? NaN : Number(event.target.value);
    }),
  );
  $("#radius").addEventListener("change", (event) =>
    controller.edit((data) => {
      data.radius_km =
        event.target.value === "" ? NaN : Number(event.target.value);
    }),
  );
  $("#coordinates").addEventListener("submit", (event) => {
    event.preventDefault();
    const x = Number($("#x").value),
      y = Number($("#y").value);
    controller.edit((data) =>
      Object.assign(
        data.sites.find((p) => p.id === active),
        { x_km: x, y_km: y, edited_candidate: true },
      ),
    );
  });
  $("#add").addEventListener("click", () =>
    controller.edit((data) => {
      const b = controller.state.bounds;
      let id;
      do {
        id = `candidate-${nextSite++}`;
      } while (data.sites.some((p) => p.id === id));
      let position;
      for (let i = 0; i < 100; i++) {
        const x = b.minX + (b.maxX - b.minX) * (0.5 + (i % 10) * 0.025),
          y = b.minY + (b.maxY - b.minY) * (0.5 + Math.floor(i / 10) * 0.025);
        if (
          data.sites.every((p) => Math.hypot(p.x_km - x, p.y_km - y) >= 0.001)
        ) {
          position = { x_km: x, y_km: y };
          break;
        }
      }
      if (!position)
        throw new Error(
          "No free candidate location found. Move an existing candidate first.",
        );
      data.sites.push({ id, ...position });
      active = id;
    }),
  );
  $("#remove").addEventListener("click", () =>
    controller.edit((data) => removeSite(data, active)),
  );
  $("#run").addEventListener("click", () =>
    controller.run(Number($("#shots").value)),
  );
  $("#reset").addEventListener("click", () => controller.load(currentDataset));
  $("#export").addEventListener("click", () => {
    if (controller.state.data) {
      $("#snapshot").value = JSON.stringify(controller.state.data, null, 2);
      $("#snapshot").focus();
      $("#snapshot").select();
    }
  });
  $("#restore").addEventListener("click", async () => {
    try {
      const saved = JSON.parse($("#snapshot").value);
      const key = {
        "synthetic-baseline": "synthetic",
        "caba-comuna4": "caba-comuna4",
        caba: "caba",
      }[saved.meta?.id];
      if (!key || !Array.isArray(saved.sites))
        throw new Error("Paste a snapshot of one of the packaged datasets.");
      // Load the trusted original zones/provenance, and restore only editable fields.
      const original = await transport.loadCase(key);
      const fields = restoreFields(original, saved);
      currentDataset = key;
      $("#dataset").value = key;
      active = null;
      await controller.load(key);
      if (controller.state.data)
        await controller.edit((data) => Object.assign(data, fields));
    } catch (error) {
      controller.state.error = `Cannot restore: ${error.message}`;
      controller.emit();
    }
  });
  controller.init();
  return controller;
}
