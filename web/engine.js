// The configurator's engine, a module Web Worker: Pyodide with the packages pinned in pyodide-lock.json (build123d and
// OCP.wasm, the OpenCascade compiled to WebAssembly), the generator files of generator/files.json and engine.py.
// Messages in: {id, action, args}; out: {type: 'step' | 'log' | 'ready' | 'failed' | 'result' | 'error', ...}.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs';

const ROOT = '/home/pyodide/web';
const t0 = performance.now();
const secs = () => ((performance.now() - t0) / 1000).toFixed(1);
const send = (type, data = {}) => postMessage({ type, ...data });
let engine = null;
self.addEventListener('unhandledrejection', (e) => send('failed', { text: String(e.reason && e.reason.message || e.reason) }));
self.addEventListener('error', (e) => send('failed', { text: String(e.message || e) }));

async function start() {
  send('step', { text: 'Loading Python (Pyodide)…' });
  const lock = new URL('pyodide-lock.json', location.href).href;
  const py = await loadPyodide({ lockFileURL: lock, stdout: (s) => send('log', { text: s }), stderr: (s) => send('log', { text: s }) });
  send('step', { text: `Python ready in ${secs()} s.` });
  py.setStdout({ batched: (s) => send('log', { text: s }) });
  py.setStderr({ batched: (s) => send('log', { text: s }) });
  const names = Object.keys((await (await fetch(lock)).json()).packages).filter((n) => n !== 'micropip');
  send('step', { text: `Loading ${names.length} packages (about 60 MB on the first visit)…` });
  await py.loadPackage(names, { messageCallback: (s) => send('log', { text: s }), errorCallback: (s) => send('log', { text: s }) });
  send('step', { text: 'Copying the generator…' });
  const files = await (await fetch('generator/files.json')).json();
  await Promise.all(['engine.py', ...files].map(async (f) => {
    const data = new Uint8Array(await (await fetch(f)).arrayBuffer());
    py.FS.mkdirTree(ROOT + '/' + f.split('/').slice(0, -1).join('/'));
    py.FS.writeFile(ROOT + '/' + f, data);
  }));
  py.runPython(`import sys\nsys.path.insert(0, '${ROOT}')`);
  for (const [mod, text] of [['OCP.TopoDS', 'Loading OpenCascade…'], ['build123d', 'Loading build123d…'], ['engine', 'Loading the generator…']]) {
    send('step', { text: `${text} (${secs()} s)` });
    await py.runPythonAsync(`import ${mod}`);
  }
  engine = py.globals.get('engine');
  send('log', { text: `generator loaded (${secs()} s)` });
  send('ready', { catalog: JSON.parse(engine.catalog()), time: secs() });
}

// Python data (dicts, lists, bytes) -> JS objects with Uint8Arrays, and the buffers to transfer
function toJs(proxy) {
  const js = proxy.toJs ? proxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false }) : proxy;
  if (proxy.destroy) proxy.destroy();
  const buffers = [];
  (function collect(o) {
    if (o instanceof Uint8Array) buffers.push(o.buffer);
    else if (Array.isArray(o)) o.forEach(collect);
    else if (o && typeof o === 'object') Object.values(o).forEach(collect);
  })(js);
  return [js, buffers];
}

const queue = [];
let busy = false;
onmessage = (e) => { queue.push(e.data); next(); };

const ACTIONS = {
  evaluate: (a) => [JSON.parse(engine.evaluate(...a)), []],
  parts: (a) => toJs(engine.parts(...a)),
  build: (a) => toJs(engine.build_part(...a)),
  frame: (a) => toJs(engine.frame(...a)),
  stl: (a) => toJs(engine.stl(...a)),
  zip: (a) => toJs(engine.zip_all(...a)),
};

async function next() {
  if (busy || !engine || !queue.length) return;
  busy = true;
  const { id, action, args } = queue.shift();
  try {
    if (!ACTIONS[action]) throw new Error('unknown action: ' + action);
    const [result, buffers] = ACTIONS[action](args);    // every action: its result and the buffers to transfer
    postMessage({ type: 'result', id, result }, buffers);
  } catch (err) {
    // a Python error: its last line (the exception) is what the user needs
    const lines = String(err.message || err).trim().split('\n');
    postMessage({ type: 'error', id, text: lines[lines.length - 1], full: String(err.message || err) });
  }
  busy = false;
  next();
}

start().then(next).catch((err) => send('failed', { text: String(err.message || err) }));
