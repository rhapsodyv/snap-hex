// The configurator's page: printer and parameters, the 3D view (three.js) and the STLs. With the default values all of
// it comes ready-made from pre/ (engine.py pregenerate, run by the Pages workflow), so the page works at once; a changed
// parameter goes to the engine (engine.js, a Web Worker running the generator in Pyodide), which loads meanwhile. The
// choice lives in the link (#p=…&c=…) and in this browser (localStorage), so it can be shared and comes back.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { FIELDS, PART_NAMES } from './fields.js';

const $ = (id) => document.getElementById(id);
const COLORS = { grid: 0xcfc8b8, joiner: 0x8a63c9, mount: 0xe8846b, frame: 0x8c8e94, deck: 0x30343a };
const state = { catalog: null, preset: 'trident-350', changes: {}, values: {}, errors: {}, built: null, busy: false,
  engineReady: false, engineFailed: false, step: '', parts: {} };
const num = (v, digits = 0) => v.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
const partName = (n) => PART_NAMES[n] || n;
const escape = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

// ---------------------------------------------------------------- the engine
const engine = new Worker(new URL('engine.js', import.meta.url), { type: 'module' });
const pending = new Map();
let nextId = 1;
function call(action, args) {
  const id = nextId++;
  if (!state.engineReady) progress('Waiting for the engine to finish loading…');
  return new Promise((ok, fail) => { pending.set(id, { ok, fail }); engine.postMessage({ id, action, args }); });
}
engine.onerror = (e) => { state.engineFailed = true; badge(); progress('The engine failed: ' + (e.message || e), true); console.error(e); };
engine.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'step') { state.step = m.text; badge(); if (!state.busy && !state.catalog) progress(m.text); }
  else if (m.type === 'log') { if (state.busy && state.engineReady && m.text.trim()) progress(m.text.trim()); }
  else if (m.type === 'ready') engineReady(m.catalog, m.time);
  else if (m.type === 'failed') { state.engineFailed = true; badge(); progress('The engine did not load: ' + m.text, true); }
  else if (m.type === 'result' || m.type === 'error') {
    const p = pending.get(m.id);
    pending.delete(m.id);
    if (m.type === 'result') p.ok(m.result); else p.fail(Object.assign(new Error(m.text), { full: m.full }));
  }
};
function badge() {
  const s = $('engine-state');
  if (state.engineFailed) { s.className = 'engine-state error'; s.textContent = 'engine failed'; return; }
  s.className = 'engine-state ' + (state.engineReady ? 'ready' : 'loading');
  s.textContent = state.engineReady ? 'engine ready' : 'engine loading…';
  s.title = state.engineReady ? 'You can change parameters and generate.' : state.step + ' The default configuration already works.';
}
function progress(text, error = false) { const p = $('progress'); p.textContent = text; p.classList.toggle('error-txt', error); }

// ---------------------------------------------------------------- the choice: link and this browser
function readChoice() {
  const h = new URLSearchParams(location.hash.slice(1));
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('snap-hex') || '{}'); } catch { saved = {}; }
  state.preset = h.get('p') || saved.preset || state.preset;
  try { state.changes = h.get('c') ? { [state.preset]: JSON.parse(h.get('c')) } : (saved.changes || {}); } catch { state.changes = {}; }
}
function saveChoice() {
  const h = new URLSearchParams({ p: state.preset });
  if (Object.keys(changes()).length) h.set('c', JSON.stringify(changes()));
  history.replaceState(null, '', '#' + h.toString());
  try { localStorage.setItem('snap-hex', JSON.stringify({ preset: state.preset, changes: state.changes })); } catch { /* private window */ }
}
const preset = () => state.catalog.presets.find((p) => p.name === state.preset);
const changes = () => state.changes[state.preset] || (state.changes[state.preset] = {});
const isDefault = () => !Object.keys(changes()).length;
const currentKey = () => JSON.stringify([state.preset, changes()]);
const args = () => [state.preset, JSON.stringify(changes())];

// ---------------------------------------------------------------- the ready-made default (pre/)
const pre = {};
function loadPre(name) {
  if (!pre[name]) pre[name] = fetch(`pre/${name}.json`).then((r) => { if (!r.ok) throw new Error(`pre/${name}.json: ${r.status}`); return r.json(); });
  return pre[name];
}
const fromB64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
async function readyMade() {
  const d = await loadPre(state.preset);
  const parts = Object.fromEntries(Object.entries(d.parts).map(([n, p]) => [n, { ...p, v: fromB64(p.v), t: fromB64(p.t) }]));
  return { parts, frame: d.frame.map((f) => ({ ...f, v: fromB64(f.v), t: fromB64(f.t) })) };
}

// ---------------------------------------------------------------- start
async function start() {
  badge();
  try {
    state.catalog = await (await fetch('pre/catalog.json')).json();
  } catch {
    progress('No ready-made configuration (pre/): waiting for the engine to load…');
    return;                                  // engineReady() starts the page with the engine's catalogue
  }
  begin();
}
function begin() {
  if (!state.catalog.presets.some((p) => p.name === state.preset)) state.preset = state.catalog.presets[0].name;
  $('preset').innerHTML = state.catalog.presets.map((p) => `<option value="${p.name}">${escape(p.title)}</option>`).join('');
  $('preset').value = state.preset;
  for (const id of ['preset', 'generate', 'download']) $(id).disabled = false;
  switchPreset(false);
  generate();
}
function engineReady(catalog, time) {
  state.engineReady = true;
  document.body.dataset.engine = time;
  badge();
  if (!state.catalog) { state.catalog = catalog; begin(); return; }
  if (!state.busy) progress(`Engine loaded in ${time} s: you can change parameters now.`);
  if (!isDefault()) evaluate();
}

const defaults = () => Object.fromEntries(state.catalog.parameters.map((p) => [p.name, p]));
function switchPreset(regenerate = true) {
  $('preset-description').textContent = preset().description;
  state.values = Object.fromEntries(state.catalog.parameters.map((p) => [p.name, p.value]));
  state.errors = {};
  drawParameters();
  if (!isDefault() && state.engineReady) evaluate();
  markStale();
  saveChoice();
  if (regenerate) generate();
}
$('preset').onchange = () => { state.preset = $('preset').value; switchPreset(); };

function markStale() {
  const w = $('warning');
  const stale = state.built && state.built !== currentKey();
  w.hidden = !stale;
  w.textContent = stale ? 'Changes not generated yet: press Generate.' : '';
}

// ---------------------------------------------------------------- parameters: the user's, and the rest under Advanced
function fmt(v) { return typeof v === 'number' ? (Math.abs(v) >= 100 ? String(+v.toFixed(2)) : String(+v.toFixed(4))) : String(v); }
function drawParameters() {
  const filter = $('filter').value.trim().toLowerCase();
  const only = $('changed-only').checked;
  const ch = changes();
  const table = defaults();
  const passes = (name, text) => (!filter || name.toLowerCase().includes(filter) || text.toLowerCase().includes(filter)) && (!only || name in ch);
  const fields = FIELDS.filter((f) => table[f.name]);
  const groups = {};
  for (const f of fields) if (passes(f.name, f.label + ' ' + f.help)) (groups[f.group] = groups[f.group] || []).push(f);
  let html = Object.entries(groups).map(([g, fs]) => `<h3 class="group">${g}</h3>` + fs.map((f) => {
    const p = table[f.name];
    const value = f.name in ch ? ch[f.name] : fmt(p.value);
    return `<div class="param ${f.name in ch ? 'changed' : ''} ${state.errors[f.name] ? 'invalid' : ''}" data-name="${f.name}" data-kind="number">
      <label class="label" for="p-${f.name}">${f.label}</label>
      <div class="entry"><input id="p-${f.name}" type="text" inputmode="decimal" spellcheck="false" value="${escape(value)}"><span class="unit">mm</span>
        <span class="default">default ${fmt(p.value)}</span></div>
      <div class="desc">${escape(f.help)}</div></div>`;
  }).join('')).join('');
  const ours = new Set(fields.map((f) => f.name));
  const rest = state.catalog.parameters.filter((p) => !ours.has(p.name) && passes(p.name, p.comment || ''));
  html += `<details id="advanced" ${filter || only ? 'open' : ''}><summary>Advanced: design values (${rest.length})</summary>
    <p class="note">The design's own parameters, by their names in <code>generator/params.py</code>, with its comments. They take
    Python expressions, and may use the other parameters' names. The mount plug's spring is tuned for the default cell: change
    the cell or the plug only if you know the design.</p>` +
    rest.map((p) => `<div class="param ${p.name in ch ? 'changed' : ''} ${state.errors[p.name] ? 'invalid' : ''}" data-name="${p.name}">
      <div class="top"><span class="name">${p.name}</span><span class="value" title="${escape(fmt(state.values[p.name]))}">= ${escape(fmt(state.values[p.name]))}</span></div>
      <input type="text" value="${escape(ch[p.name] ?? p.expression)}" spellcheck="false" aria-label="${p.name}">
      ${p.comment ? `<div class="desc">${escape(p.comment)}</div>` : ''}</div>`).join('') + '</details>';
  const open = $('advanced') && $('advanced').open;
  $('parameters').innerHTML = html;
  if (open) $('advanced').open = true;
  const n = Object.keys(ch).length;
  $('n-changed').textContent = n ? `${n} changed` : '';
}
$('parameters').addEventListener('change', (e) => {
  const row = e.target.closest('.param');
  if (!row) return;
  const name = row.dataset.name;
  const p = defaults()[name];
  const v = e.target.value.trim();
  if (row.dataset.kind === 'number') {
    const x = Number(v.replace(',', '.'));
    if (v !== '' && Number.isNaN(x)) {
      state.errors[name] = 'not a number';
      progress(`Invalid parameter: ${name} (not a number)`, true);
      row.classList.add('invalid');
      return;
    }
    delete state.errors[name];
    if (v === '' || Math.abs(x - p.value) < 1e-9) delete changes()[name];
    else changes()[name] = String(x);
  } else if (!v || v === p.expression) {
    delete changes()[name];
  } else {
    changes()[name] = v;
  }
  saveChoice();
  drawParameters();
  markStale();
  if (state.engineReady) evaluate();
});
$('filter').oninput = drawParameters;
$('changed-only').onchange = drawParameters;
$('reset').onclick = () => { state.changes[state.preset] = {}; saveChoice(); switchPreset(false); generate(); };

async function evaluate() {
  const r = await call('evaluate', args());
  state.errors = {};
  if (r.error) {
    // find the expression that fails: each change alone
    for (const [k, v] of Object.entries(changes())) {
      const s = await call('evaluate', [state.preset, JSON.stringify({ [k]: v })]);
      if (s.error) state.errors[k] = s.error;
    }
    if (!Object.keys(state.errors).length) state.errors._ = r.error;
    progress('Invalid parameter: ' + Object.entries(state.errors).map(([k, e]) => `${k} (${e})`).join('; '), true);
  } else {
    state.values = r.values;
    if ($('progress').classList.contains('error-txt')) progress('');
  }
  drawParameters();
  markStale();
}

// ---------------------------------------------------------------- generate and download
async function task(label, f) {
  if (state.busy) return;
  state.busy = true;
  for (const id of ['generate', 'download', 'preset']) $(id).disabled = true;
  const t = performance.now();
  try {
    const done = await f();
    progress(done || `${label}: ${((performance.now() - t) / 1000).toFixed(1)} s.`);
  } catch (err) {
    progress(`${label} failed: ${err.message}`, true);
    console.error(err.full || err);
  } finally {
    state.busy = false;
    for (const id of ['generate', 'download', 'preset']) $(id).disabled = false;
  }
}

function generate() {
  if (Object.keys(state.errors).length) { progress('Fix the invalid parameters before generating.', true); return; }
  return task('Generating', async () => {
    if (isDefault()) {
      const r = await readyMade();
      clearView();
      showFrame(r.frame);
      for (const p of Object.values(r.parts)) addPart(p);
      partsTable(r.parts);
      state.built = currentKey();
      markStale();
      return 'Default configuration (ready-made).';
    }
    const list = await call('parts', args());
    clearView();
    showFrame(await call('frame', args()));
    const parts = {};
    for (const [i, p] of list.entries()) {
      progress(`Generating ${partName(p.name)} (${i + 1} of ${list.length})…`);
      const r = await call('build', [...args(), p.name]);
      parts[p.name] = r;
      addPart(r);
      partsTable(parts);
    }
    state.built = currentKey();
    markStale();
    return null;
  });
}
$('generate').onclick = generate;

function save(data, filename, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 20000);
}
const suffix = () => (isDefault() ? '' : '-custom');
$('download').onclick = () => task('Exporting', async () => {
  if (isDefault()) { save(await (await fetch(`pre/${state.preset}/snap-hex-${state.preset}.zip`)).blob(), `snap-hex-${state.preset}.zip`); return null; }
  progress('Exporting every part (the ones not generated yet are built now)…');
  save(await call('zip', args()), `snap-hex-${state.preset}${suffix()}.zip`, 'application/zip');
  return null;
});
$('parts').addEventListener('click', (e) => {
  const a = e.target.closest('a[data-stl]');
  if (a) {
    e.preventDefault();
    const name = a.dataset.stl;
    task('Exporting', async () => {
      if (isDefault()) { save(await (await fetch(`pre/${state.preset}/${name}.stl`)).blob(), `${name}.stl`); return null; }
      save(await call('stl', [...args(), name]), `${name}${suffix()}.stl`, 'model/stl');
      return null;
    });
    return;
  }
  const tr = e.target.closest('tr[data-name]');
  if (tr) select(tr.dataset.name);
});

// ---------------------------------------------------------------- 3D view
const canvas = $('canvas');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
canvas.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, 1, 1, 50000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.addEventListener('change', draw);
scene.add(new THREE.HemisphereLight(0xffffff, 0x5a5a5a, 1.6));
const light = new THREE.DirectionalLight(0xffffff, 1.8);
light.position.set(0.4, 0.6, 1);
camera.add(light);
scene.add(camera);
const partsGroup = new THREE.Group();
const frameGroup = new THREE.Group();
const deckGroup = new THREE.Group();
scene.add(partsGroup, frameGroup, deckGroup);
const material = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.05, ...extra });
const materials = { grid: material(COLORS.grid), joiner: material(COLORS.joiner), mount: material(COLORS.mount),
  frame: material(COLORS.frame, { roughness: 0.5, metalness: 0.3 }),
  deck: material(COLORS.deck, { transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }),
  selected: material(0xffd23f, { emissive: 0x6b4f00 }) };

const background = () => getComputedStyle(document.documentElement).getPropertyValue('--view').trim() || '#eceae6';
function draw() { scene.background = new THREE.Color(background()); renderer.render(scene, camera); }
new ResizeObserver(() => {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
  draw();
}).observe(canvas);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);

function geometry(v, t) {
  const g = new THREE.BufferGeometry();
  const f = v.byteOffset % 4 ? new Float32Array(v.slice().buffer) : new Float32Array(v.buffer, v.byteOffset, v.byteLength / 4);
  const i = t.byteOffset % 4 ? new Uint32Array(t.slice().buffer) : new Uint32Array(t.buffer, t.byteOffset, t.byteLength / 4);
  g.setAttribute('position', new THREE.BufferAttribute(f, 3));
  g.setIndex(new THREE.BufferAttribute(i, 1));
  g.computeVertexNormals();
  return g;
}
function clear(group) {
  const geos = new Set(group.children.map((o) => o.geometry));
  geos.forEach((g) => g.dispose());
  group.clear();
}
let framed = false;
function clearView() { clear(partsGroup); clear(frameGroup); clear(deckGroup); state.parts = {}; $('empty').hidden = false; }

function addPart(p) {
  state.parts[p.name] = p;
  const g = geometry(p.v, p.t);
  for (const m of p.placements) {
    const mesh = new THREE.Mesh(g, materials[p.kind]);
    mesh.matrixAutoUpdate = false;
    mesh.matrix.copy(new THREE.Matrix4().set(...m));
    mesh.userData = { name: p.name, kind: p.kind };
    mesh.visible = p.kind !== 'mount' || $('show-mounts').checked;
    partsGroup.add(mesh);
  }
  $('empty').hidden = true;
  if (!framed && p.kind === 'grid') { framed = true; view('above'); } else draw();
}
function showFrame(list) {
  for (const f of list) {
    const mesh = new THREE.Mesh(geometry(f.v, f.t), materials[f.kind]);
    mesh.userData = { name: f.kind, kind: f.kind };
    (f.kind === 'deck' ? deckGroup : frameGroup).add(mesh);
  }
  frameGroup.visible = $('show-frame').checked;
  deckGroup.visible = $('show-deck').checked;
  draw();
}

function view(side) {
  partsGroup.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(partsGroup);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  const dir = new THREE.Vector3(0.35, -0.75, side === 'below' ? -0.8 : 0.9).normalize();
  camera.position.copy(center).addScaledVector(dir, size * 2.4);
  camera.near = size / 200; camera.far = size * 20; camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  draw();
}
$('from-below').onclick = () => view('below');
$('from-above').onclick = () => view('above');
$('show-frame').onchange = () => { frameGroup.visible = $('show-frame').checked; draw(); };
$('show-deck').onchange = () => { deckGroup.visible = $('show-deck').checked; draw(); };
$('show-mounts').onchange = () => {
  for (const m of partsGroup.children) if (m.userData.kind === 'mount') m.visible = $('show-mounts').checked;
  draw();
};

function partsTable(parts) {
  const css = { grid: 'var(--c-grid)', joiner: 'var(--c-joiner)', mount: 'var(--c-mount)' };
  $('parts').querySelector('tbody').innerHTML = Object.values(parts).map((p) =>
    `<tr class="clickable" data-name="${p.name}"><td><span class="swatch" style="background:${css[p.kind]}"></span>${escape(partName(p.name))}` +
    `${p.valid === false || p.solids > 1 ? ' <span class="error-txt">(check)</span>' : ''}</td>` +
    `<td class="num">${p.quantity || 'as needed'}</td><td class="num">${num(p.volume / 1000, 1)}</td>` +
    `<td class="num"><a href="#" data-stl="${p.name}">STL</a></td></tr>`).join('');
  $('parts-block').hidden = false;
}

function paint(test) {
  for (const m of partsGroup.children) m.material = test(m) ? materials.selected : materials[m.userData.kind];
  draw();
}
function select(name) {
  paint((m) => name && m.userData.name === name);
  document.querySelectorAll('#parts tr').forEach((tr) => tr.classList.toggle('sel', tr.dataset.name === name));
  const s = $('selection');
  const p = name && state.parts[name];
  if (!p) { s.hidden = true; return; }
  s.hidden = false;
  s.innerHTML = `<b>${escape(partName(name))}</b> <span class="note">${name}.stl</span><br>` +
    `${p.quantity ? p.quantity + '×' : 'as many as you need'} · ${num(p.volume / 1000, 1)} cm³` +
    (p.time !== undefined && !isDefault() ? ` · built in ${p.time} s` : '');
}

// click (not drag) on a part selects it
const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const hit = ray.intersectObjects(partsGroup.children.filter((m) => m.visible), false)[0];
  select(hit ? hit.object.userData.name : null);
});

readChoice();
start();
