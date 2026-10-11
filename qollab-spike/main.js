import * as svc from 'spike.service';

const $ = (id) => document.getElementById(id);
const ns = 'http://www.w3.org/2000/svg';
const fetchUrl = 'https://raw.githubusercontent.com/Rpetey317/quantum-ambulance/main/README.md';
const state = {
  startedAt: new Date().toISOString(),
  backendAtStart: typeof backend !== 'undefined',
  revision: 0,
  preview: null,
  file: null,
  fetch: null,
  jobAttempts: 0,
  jobs: [],
  running: false,
};
let currentCase = null;
let timer = null;
let dragging = false;

function backendName() {
  if (typeof backend === 'undefined') return null;
  try { return String(backend.name ?? backend.backend_name ?? 'selected backend'); }
  catch { return 'selected backend'; }
}

async function python(name, ...args) {
  return JSON.parse(String(await svc[name].callPromising(...args)));
}

function evidence() {
  $('evidence').value = JSON.stringify({
    started_at: state.startedAt,
    backend_at_start: state.backendAtStart,
    backend_now: backendName(),
    revision_now: state.revision,
    case_now: currentCase,
    preview_now: state.preview,
    packaged_file: state.file,
    external_get: state.fetch,
    job_attempts: state.jobAttempts,
    jobs: state.jobs.map((job) => ({ ...job, stale_now: job.revision !== state.revision })),
  }, null, 2);
}

function jobDisplay() {
  $('jobResult').textContent = state.jobs.length
    ? state.jobs.map((job) => JSON.stringify({ ...job, stale_now: job.revision !== state.revision }, null, 2)).join('\n\n')
    : 'No counts yet.';
  const latest = state.jobs.at(-1);
  if (latest?.status === 'done' && latest.revision !== state.revision) {
    $('jobStatus').textContent = `Job ${latest.attempt} belongs to revision ${latest.revision}; current revision ${state.revision} is not sampled. The old counts are stale.`;
  }
}

function jobButtons() {
  $('firstJob').disabled = state.running || !state.preview || state.jobAttempts !== 0;
  $('secondJob').disabled = state.running || state.jobAttempts !== 1 || !state.jobs.some((job) => job.attempt === 1 && job.status === 'done');
}

function point(x, y) {
  return { x: 20 + 36 * x, y: 380 - 36 * y };
}

function marker(x, y) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  const p = point(x, y);
  $('siteMarker').setAttribute('cx', String(p.x));
  $('siteMarker').setAttribute('cy', String(p.y));
  $('siteLabel').setAttribute('x', String(p.x + 18));
  $('siteLabel').setAttribute('y', String(p.y - 6));
}

function zones(preview) {
  const group = $('zones');
  group.replaceChildren();
  for (const zone of preview.case.zones) {
    const p = point(zone.x, zone.y);
    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', String(p.x));
    circle.setAttribute('cy', String(p.y));
    circle.setAttribute('r', '12');
    circle.setAttribute('class', preview.covered_zone_ids.includes(zone.id) ? 'zone covered' : 'zone');
    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', String(p.x + 15));
    label.setAttribute('y', String(p.y + 5));
    label.setAttribute('class', 'zone-label');
    label.textContent = `${zone.id}: ${zone.population}`;
    group.append(circle, label);
  }
}

function showPreview(preview) {
  state.preview = preview;
  currentCase = preview.case;
  $('siteX').value = String(currentCase.site.x);
  $('siteY').value = String(currentCase.site.y);
  $('radius').value = String(currentCase.radius);
  marker(currentCase.site.x, currentCase.site.y);
  zones(preview);
  $('caseStatus').textContent = `Revision ${state.revision}: JS input reached Python; no backend job was used.`;
  $('preview').textContent = `Python: site ${currentCase.site.id} (${currentCase.site.x}, ${currentCase.site.y}), radius ${currentCase.radius} → zones ${preview.covered_zone_ids.join(', ') || 'none'}, covered ${preview.covered_population}/${preview.total_population} synthetic population units. RY = ${preview.ry_angle_radians.toFixed(4)} rad; ideal P(1) = ${(preview.ideal_probability_one * 100).toFixed(1)}%.`;
  jobButtons();
  jobDisplay();
  evidence();
}

async function refresh(revision) {
  try {
    const preview = await python('evaluate', JSON.stringify(currentCase));
    if (revision === state.revision) showPreview(preview);
  } catch (error) {
    if (revision === state.revision) {
      $('caseStatus').textContent = `Python preview failed: ${error.message || error}`;
      $('preview').textContent = 'Fix the input, then retry.';
      jobButtons();
      evidence();
    }
  }
}

function editCase() {
  if (!currentCase) return;
  const fields = ['siteX', 'siteY', 'radius'];
  const values = fields.map((id) => $(id).value.trim() === '' ? NaN : Number($(id).value));
  state.revision++;
  state.preview = null;
  clearTimeout(timer);
  if (values.some((value) => !Number.isFinite(value))) {
    $('caseStatus').textContent = 'Enter finite numeric values for x, y and radius.';
    $('preview').textContent = 'Waiting for valid input.';
    jobButtons();
    jobDisplay();
    evidence();
    return;
  }
  [currentCase.site.x, currentCase.site.y, currentCase.radius] = values;
  marker(values[0], values[1]);
  $('caseStatus').textContent = `Revision ${state.revision}: recalculating Python preview…`;
  jobButtons();
  jobDisplay();
  evidence();
  const revision = state.revision;
  timer = setTimeout(() => refresh(revision), 120);
}

function dragPosition(event) {
  const svg = $('map');
  const xy = svg.createSVGPoint();
  xy.x = event.clientX;
  xy.y = event.clientY;
  const p = xy.matrixTransform(svg.getScreenCTM().inverse());
  $('siteX').value = String(Math.round(Math.max(0, Math.min(10, (p.x - 20) / 36)) * 10) / 10);
  $('siteY').value = String(Math.round(Math.max(0, Math.min(10, (380 - p.y) / 36)) * 10) / 10);
  editCase();
}

function toCounts(raw) {
  const converted = raw && typeof raw.toJs === 'function' ? raw.toJs() : raw;
  const counts = converted instanceof Map ? Object.fromEntries(converted) : converted;
  if (!counts || typeof counts !== 'object') throw new Error('Backend did not return a counts mapping');
  return counts;
}

async function runJob(second) {
  if (state.running || (second ? state.jobAttempts !== 1 : !state.preview || state.jobAttempts !== 0)) return;
  const first = state.jobs.find((job) => job.attempt === 1 && job.status === 'done');
  if (second && !first) return;
  const snapshot = JSON.parse(JSON.stringify(second ? first.case : state.preview.case));
  const revision = second ? first.revision : state.revision;
  const path = second ? first.path : $('jobPath').value;
  const name = backendName();
  const shots = name && /ionq/i.test(name) ? 4 : 32;
  state.running = true;
  jobButtons();
  $('jobStatus').textContent = `Preparing ${second ? 'second' : 'first'} circuit for revision ${revision} using ${path}…`;
  const row = { attempt: state.jobAttempts + 1, revision, case: snapshot, backend: name, shots, path, stage: 'prepare', started_at: new Date().toISOString() };
  try {
    if (typeof backend === 'undefined') throw new Error('Qollab did not inject a backend in this Run');
    if (path === 'python') {
      row.stage = 'python_promising';
      state.jobAttempts++;
      evidence();
      $('jobStatus').textContent = `Python is submitting job ${row.attempt}: ${shots} shots on ${name}…`;
      const response = await python('run_on_backend', backend, JSON.stringify(snapshot), shots);
      row.counts = response.counts;
      row.measured_shots = response.measured_shots;
    } else if (path === 'js') {
      row.stage = 'build_circuit';
      const circuit = await svc.audit_circuit.callPromising(JSON.stringify(snapshot));
      state.jobAttempts++;
      evidence();
      row.stage = 'js_submit';
      $('jobStatus').textContent = `JS is submitting job ${row.attempt}: ${shots} shots on ${name}…`;
      const job = await backend.run(circuit, { shots });
      row.stage = 'js_result';
      row.counts = toCounts((await job.result()).get_counts());
      row.measured_shots = Object.values(row.counts).reduce((sum, count) => sum + Number(count), 0);
    } else {
      throw new Error('Unknown submission path');
    }
    row.stage = 'complete';
    row.status = 'done';
    $('jobStatus').textContent = `Job ${row.attempt} returned ${row.measured_shots} shots from ${name} via ${path}. ${revision === state.revision ? 'Result matches the current revision.' : 'Result is stale after input edits.'}`;
  } catch (error) {
    row.status = 'failed';
    row.error = String(error.message || error);
    $('jobStatus').textContent = `Job ${row.attempt} failed at ${row.stage} via ${path}: ${row.error}. ${state.jobAttempts ? 'Start a fresh Qollab Run if the backend request consumed the job slot.' : 'No backend request was sent.'}`;
  } finally {
    row.ended_at = new Date().toISOString();
    state.jobs.push(row);
    state.running = false;
    jobButtons();
    jobDisplay();
    evidence();
  }
}

async function readFile() {
  try {
    const file = await python('load_fixture');
    state.file = { status: 'ok', path: file.path, bytes: file.bytes, sha256: file.sha256 };
    $('fileStatus').textContent = `Python read ${file.path}: ${file.bytes} bytes, SHA-256 ${file.sha256}.`;
    if (!currentCase) {
      currentCase = file.case;
      state.revision++;
      await refresh(state.revision);
    }
  } catch (error) {
    state.file = { status: 'failed', error: String(error.message || error) };
    $('fileStatus').textContent = `Packaged file check failed: ${state.file.error}`;
  }
  evidence();
}

async function externalGet() {
  $('fetchAsset').disabled = true;
  $('fetchStatus').textContent = 'Fetching public static file with GET…';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(fetchUrl, { method: 'GET', signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bytes = (await response.arrayBuffer()).byteLength;
    state.fetch = { status: 'ok', url: fetchUrl, http_status: response.status, bytes };
    $('fetchStatus').textContent = `GET succeeded: HTTP ${response.status}, ${bytes} bytes.`;
  } catch (error) {
    state.fetch = { status: 'failed', url: fetchUrl, error: String(error.message || error) };
    $('fetchStatus').textContent = `GET failed: ${state.fetch.error}. Check Qollab/browser console for CORS details.`;
  } finally {
    clearTimeout(timeout);
    $('fetchAsset').disabled = false;
    evidence();
  }
}

for (const id of ['siteX', 'siteY', 'radius']) $(id).addEventListener('input', editCase);
$('siteMarker').addEventListener('pointerdown', (event) => {
  dragging = true;
  $('siteMarker').setPointerCapture(event.pointerId);
  dragPosition(event);
});
$('siteMarker').addEventListener('pointermove', (event) => { if (dragging) dragPosition(event); });
for (const type of ['pointerup', 'pointercancel']) $('siteMarker').addEventListener(type, () => { dragging = false; });
$('showCase').onclick = () => {
  $('caseTransfer').value = JSON.stringify(currentCase, null, 2);
  $('caseTransfer').focus();
  $('caseTransfer').select();
};
$('loadCase').onclick = async () => {
  try {
    const candidate = JSON.parse($('caseTransfer').value);
    const revision = ++state.revision;
    state.preview = null;
    clearTimeout(timer);
    jobButtons();
    jobDisplay();
    const preview = await python('evaluate', JSON.stringify(candidate));
    if (revision === state.revision) showPreview(preview);
  } catch (error) {
    $('caseStatus').textContent = `Could not load pasted case: ${error.message || error}`;
    jobButtons();
    jobDisplay();
    evidence();
  }
};
let completeFirstJob, completeSecondJob;
const firstJobCompleted = new Promise((resolve) => { completeFirstJob = resolve; });
const secondJobCompleted = new Promise((resolve) => { completeSecondJob = resolve; });
$('firstJob').onclick = async () => {
  try { await runJob(false); }
  finally { completeFirstJob(); }
};
$('secondJob').onclick = async () => {
  try { await runJob(true); }
  finally { completeSecondJob(); }
};
$('checkFile').onclick = readFile;
$('fetchAsset').onclick = externalGet;
$('selectEvidence').onclick = () => { $('evidence').focus(); $('evidence').select(); };
$('backendStatus').textContent = state.backendAtStart
  ? `Backend available at JS startup: ${backendName()}. Qollab's Run dialog chooses it; this app does not.`
  : 'No backend available at JS startup. The first-job button will report whether one appeared later.';
evidence();
await readFile();
if (state.preview) {
  await firstJobCompleted;
  if (state.jobs.some((job) => job.attempt === 1 && job.status === 'done')) await secondJobCompleted;
}
