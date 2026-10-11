import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  boundsFor,
  edited,
  validate,
  removeSite,
  overlay,
  backendPolicy,
  clone,
  restoreFields,
} from "../../ui/model.js";
import { Controller } from "../../ui/controller.js";

const source = JSON.parse(
  readFileSync(new URL("../../data/cases/synthetic.json", import.meta.url)),
);
const identity = (data) => ({
  case_id: data.meta.id,
  case_revision: data.meta.revision,
  input_fingerprint: JSON.stringify([data.sites, data.k, data.radius_km]),
});
const result = (data) => ({
  ...identity(data),
  status: "ok",
  selected_site_ids: [data.sites[0].id],
  covered_zone_ids: [data.zones[0].id],
});
const preview = (data) => ({
  ...identity(data),
  greedy: result(data),
  exact: result(data),
});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
function transport(overrides = {}) {
  return {
    loadCase: async () => clone(source),
    preview: async (data) => preview(data),
    backendInfo: async () => ({
      name: "BasicSimulator",
      module: "qiskit.providers.basic_provider",
      is_simulator: true,
    }),
    runQuantum: async (data) => ({ qaoa: result(data) }),
    ...overrides,
  };
}

test("all packaged datasets have a valid fixed metric edit extent", () => {
  for (const name of ["synthetic", "caba-comuna4", "caba"]) {
    const data = JSON.parse(
      readFileSync(new URL(`../../data/cases/${name}.json`, import.meta.url)),
    );
    assert.equal(validate(data, boundsFor(data)), data);
  }
});
test("coordinate edit increments revision, preserves IDs and original input", () => {
  const data = edited(source, boundsFor(source), (d) => {
    d.sites[0].x_km += 0.1;
  });
  assert.equal(data.meta.revision, source.meta.revision + 1);
  assert.equal(data.sites[0].id, source.sites[0].id);
  assert.notEqual(data.sites[0].x_km, source.sites[0].x_km);
});
test("reject duplicates, nonfinite coordinates, out-of-bounds edits and invalid K", () => {
  for (const change of [
    (d) =>
      Object.assign(d.sites[0], {
        x_km: d.sites[1].x_km,
        y_km: d.sites[1].y_km,
      }),
    (d) => {
      d.sites[0].x_km = NaN;
    },
    (d) => {
      d.sites[0].x_km = Infinity;
    },
    (d) => {
      d.sites[0].x_km = 1e9;
    },
    (d) => {
      d.k = 0;
    },
    (d) => {
      d.k = 1.5;
    },
    (d) => {
      d.k = 9;
    },
    (d) => {
      d.radius_km = 0;
    },
  ])
    assert.throws(() => edited(source, boundsFor(source), change));
});
test("site cap, stable IDs and safe K after removal", () => {
  assert.throws(
    () =>
      edited(source, boundsFor(source), (d) =>
        d.sites.push({ id: "new", x_km: 1, y_km: 1 }),
      ),
    /8/,
  );
  const data = clone(source);
  data.k = data.sites.length;
  const removed = data.sites[2].id,
    survivor = data.sites[3].id;
  removeSite(data, removed);
  assert.equal(data.k, 7);
  assert.equal(data.sites[2].id, survivor);
  data.sites = [data.sites[0]];
  assert.throws(() => removeSite(data, data.sites[0].id));
});
test("reject geographic coordinates, empty zones and invalid demand", () => {
  for (const change of [
    (d) => {
      d.meta.crs = "EPSG:4326";
    },
    (d) => {
      d.zones = [];
    },
    (d) => {
      d.zones[0].weight = 0;
    },
  ])
    assert.throws(() => edited(source, boundsFor(source), change));
});
test("only successful matching identities produce overlays", () => {
  const r = result(source),
    id = identity(source);
  assert.equal(overlay(r, id).zones.size, 1);
  for (const wrong of [
    { ...id, case_revision: 9 },
    { ...id, input_fingerprint: "other" },
    { ...id, case_id: "other" },
  ])
    assert.equal(overlay(r, wrong).sites.size, 0);
  assert.equal(overlay({ ...r, status: "no_valid_sample" }, id).zones.size, 0);
});
test("portable restore keeps trusted zones/provenance and refuses coordinate-system changes", () => {
  const saved = clone(source);
  saved.sites[0].x_km += 0.1;
  saved.sites[0].name = "Untrusted institution";
  saved.zones[0].weight = 1e9;
  saved.k = 2;
  const fields = restoreFields(source, saved),
    restored = { ...source, ...fields };
  assert.equal(restored.zones[0].weight, source.zones[0].weight);
  assert.equal(restored.sites[0].name, source.sites[0].name);
  assert.equal(restored.sites[0].edited_candidate, true);
  saved.meta.crs = "EPSG:4326";
  assert.throws(() => restoreFields(source, saved), /coordinate system/);
});
test("late previews cannot replace newer edits", async () => {
  const requests = [];
  const c = new Controller(
    transport({
      preview: (data) => {
        const d = deferred();
        requests.push({ data, d });
        return d.promise;
      },
    }),
  );
  const loading = c.load("synthetic");
  await Promise.resolve();
  requests[0].d.resolve(preview(requests[0].data));
  await loading;
  const first = c.edit((d) => {
    d.k = 2;
  });
  const second = c.edit((d) => {
    d.k = 1;
  });
  requests[2].d.resolve(preview(requests[2].data));
  await second;
  requests[1].d.resolve(preview(requests[1].data));
  await first;
  assert.equal(c.state.data.k, 1);
  assert.equal(c.state.comparison.case_revision, 3);
});
test("dataset load races retain the last requested dataset", async () => {
  const a = deferred(),
    b = deferred();
  const c = new Controller(
    transport({ loadCase: (id) => (id === "a" ? a.promise : b.promise) }),
  );
  const first = c.load("a"),
    second = c.load("b");
  const newer = clone(source);
  newer.meta.id = "newer";
  b.resolve(newer);
  await second;
  a.resolve(source);
  await first;
  assert.equal(c.state.data.meta.id, "newer");
});
test("an edit preview started during an asset load cannot overwrite the new dataset", async () => {
  const asset = deferred(),
    oldPreview = deferred();
  let delay = false;
  const c = new Controller(
    transport({
      loadCase: (id) =>
        id === "next" ? asset.promise : Promise.resolve(clone(source)),
      preview: (data) =>
        delay && data.meta.id === source.meta.id
          ? oldPreview.promise
          : Promise.resolve(preview(data)),
    }),
  );
  await c.init();
  delay = true;
  const loading = c.load("next"),
    editing = c.edit((data) => {
      data.k = 2;
    });
  const old = clone(c.state.data),
    next = clone(source);
  next.meta.id = "next";
  asset.resolve(next);
  await loading;
  oldPreview.resolve(preview(old));
  await editing;
  assert.equal(c.state.data.meta.id, "next");
  assert.equal(c.state.comparison.case_id, "next");
});
test("editing during a quantum job makes its eventual result stale", async () => {
  const job = deferred();
  let submitted;
  const c = new Controller(
    transport({
      runQuantum: (data) => {
        submitted = data;
        return job.promise;
      },
    }),
  );
  await c.init();
  const run = c.run(8);
  await c.edit((data) => {
    data.k = 2;
  });
  job.resolve({ qaoa: result(submitted) });
  await run;
  assert.equal(c.state.quantumState, "stale");
  assert.equal(overlay(c.state.quantum, c.state.comparison).sites.size, 0);
});
test("the Qollab entrypoint awaits the first quantum attempt at top level", () => {
  const main = readFileSync(new URL("../../main.js", import.meta.url), "utf8");
  assert.match(main, /^await controller\.firstQuantumCompleted;$/m);
});
test("the Qollab Run stays pending through edits and its first quantum attempt", async () => {
  const job = deferred();
  let submitted;
  const c = new Controller(
    transport({
      runQuantum: (data) => {
        submitted = data;
        return job.promise;
      },
    }),
  );
  await c.init();
  assert.ok(c.firstQuantumCompleted instanceof Promise);
  let completed = false;
  c.firstQuantumCompleted.then(() => {
    completed = true;
  });
  await c.edit((data) => {
    data.k = 2;
  });
  assert.equal(await c.run(0), false);
  assert.equal(completed, false);
  const run = c.run(8);
  assert.equal(completed, false);
  job.resolve({ qaoa: result(submitted) });
  await run;
  await c.firstQuantumCompleted;
  assert.equal(c.state.quantumState, "ok");
  assert.equal(completed, true);
});
test("a failed quantum attempt also releases the Qollab Run after showing the error", async () => {
  const job = deferred();
  const c = new Controller(transport({ runQuantum: () => job.promise }));
  await c.init();
  assert.ok(c.firstQuantumCompleted instanceof Promise);
  const run = c.run(8);
  job.reject(new Error("Remote submission failed"));
  await run;
  await c.firstQuantumCompleted;
  assert.equal(c.state.quantumState, "failed");
  assert.equal(c.state.quantumError, "Remote submission failed");
});
test("IonQ reserves one attempt before awaiting, including failed jobs and resets", async () => {
  let calls = 0;
  const job = deferred();
  const c = new Controller(
    transport({
      backendInfo: async () => ({
        name: "IonQ simulator",
        module: "qiskit_ionq",
        is_simulator: true,
      }),
      runQuantum: () => {
        calls++;
        return job.promise;
      },
    }),
  );
  await c.init();
  const first = c.run(8);
  assert.equal(await c.run(8), false);
  job.reject(new Error("Unsupported circuit"));
  await first;
  assert.equal(c.state.quantumState, "failed");
  await c.load("synthetic");
  assert.equal(await c.run(8), false);
  assert.equal(calls, 1);
});
test("invalid shots, unsupported hardware and preview failures never submit", async () => {
  let calls = 0;
  const c = new Controller(
    transport({
      runQuantum: async (data) => {
        calls++;
        return { qaoa: result(data) };
      },
    }),
  );
  await c.init();
  assert.equal(await c.run(0), false);
  assert.equal(await c.run(1.5), false);
  c.state.backend = {
    name: "IonQ hardware",
    module: "qiskit_ionq",
    is_simulator: false,
  };
  assert.equal(await c.run(8), false);
  c.state.backend = { name: "BasicSimulator" };
  c.state.previewState = "failed";
  assert.equal(await c.run(8), false);
  assert.equal(calls, 0);
});
test("wrong-identity quantum results fail rather than mixing cases", async () => {
  const c = new Controller(
    transport({
      runQuantum: async (data) => ({
        qaoa: { ...result(data), input_fingerprint: "wrong" },
      }),
    }),
  );
  await c.init();
  await c.run(8);
  assert.equal(c.state.quantumState, "failed");
  assert.equal(c.state.quantum, null);
});
test("no-valid-sample and failed result states survive transport", async () => {
  for (const status of ["no_valid_sample", "failed"]) {
    const c = new Controller(
      transport({
        runQuantum: async (data) => ({ qaoa: { ...result(data), status } }),
      }),
    );
    await c.init();
    await c.run(8);
    assert.equal(c.state.quantumState, status);
  }
});
test("invalid edits preserve current revision and previous result", async () => {
  const c = new Controller(transport());
  await c.init();
  const before = c.state.comparison;
  await c.edit((data) => {
    data.k = 0;
  });
  assert.equal(c.state.data.meta.revision, 1);
  assert.equal(c.state.comparison, before);
  assert.match(c.state.error, /K/);
});
test("repeated native input commits leave revision and quantum validity unchanged", async () => {
  const c = new Controller(transport());
  await c.init();
  await c.run(8);
  const before = c.state.comparison;
  await c.edit((data) => {
    data.k = data.k ?? data.k_default;
  });
  const revision = c.state.data.meta.revision;
  await c.run(8);
  await c.edit((data) => {
    data.k = data.k;
  });
  assert.equal(c.state.data.meta.revision, revision);
  assert.equal(c.state.quantumState, "ok");
  assert.ok(before);
});
test("backend policy is conservative for unknown backends and bounded for IonQ", () => {
  assert.equal(backendPolicy(null).singleJob, true);
  assert.equal(
    backendPolicy({ name: "simulator", module: "qiskit_ionq" }).shotCap,
    128,
  );
  assert.equal(
    backendPolicy({
      name: "BasicSimulator",
      module: "qiskit.providers.basic_provider",
      is_simulator: true,
    }).singleJob,
    false,
  );
  assert.equal(backendPolicy({ name: "Unknown provider" }).singleJob, true);
});
