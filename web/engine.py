"""The configurator's Python side. engine.js runs it inside Pyodide (in a Web Worker),
over the generator files package.py copies into web/generator/. It also runs natively,
to test it and to build the ready-made default configuration (pre/):

    .venv/bin/python web/engine.py trident-350 mount_plug     one part, with a summary
    .venv/bin/python web/engine.py pregenerate [preset ...]   pre/ (the Pages workflow runs this)

Every call takes a preset and the changed parameters (a JSON object {name: expression},
applied over the preset's own) and returns plain data: JSON text, or bytes for meshes,
STLs and the ZIP.
"""

import base64
import io
import json
import os
import sys
import tempfile
import time
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.join(HERE, "generator")
if not os.path.isdir(GENERATOR):                       # running from the repository: use the generator itself
    GENERATOR = os.path.join(os.path.dirname(HERE), "generator")
sys.path.insert(0, GENERATOR)

from build123d import Box, Pos, export_stl  # noqa: E402
from OCP.BRepTools import BRepTools  # noqa: E402

import assembly  # noqa: E402
import configure  # noqa: E402
import grid  # noqa: E402
import layout as L  # noqa: E402
import params as P  # noqa: E402  (the same module object after every configure.apply)
import plug  # noqa: E402

# Printers. Each preset is a set of parameter changes over params.py, which is the Trident 350.
PRESETS = {
    "trident-350": dict(title="Voron Trident 350", changes={},
                        description="470 × 470 mm frame (2020), the 4 quadrants joined by 39 splines."),
}
VIEW_TOLERANCE = {"grid": (0.1, 0.8), "joiner": (0.05, 0.4), "mount": (0.02, 0.3)}   # mm, rad: meshes for the 3D view
MOUNT_CELLS = [(-6, 5), (-5, 5), (-4, 5), (-3, 5), (2, -4), (3, -4), (4, -4), (6, 1), (6, 2), (-7, -2)]


# ---------------------------------------------------------------- parameters
_applied = None                                         # the changes the generator modules are built with now


def _merged(preset, changes):
    if isinstance(changes, str):
        changes = json.loads(changes or "{}")
    return {**PRESETS[preset]["changes"], **changes}


def _use(preset, changes):
    """Apply a preset and changes (if they are not the ones in use); on an error, go back."""
    global _applied
    merged = _merged(preset, changes)
    key = json.dumps(merged, sort_keys=True)
    if key == _applied:
        return key
    try:
        configure.apply(merged)
    except Exception:
        configure.apply(json.loads(_applied or "{}"))
        raise
    _applied = key
    return key


def _value(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return repr(v)
    return float(v)


def values():
    return {p["name"]: _value(getattr(P, p["name"])) for p in configure.parameters()}


def evaluate(preset, changes):
    """The parameters' values with the changes, or the error of the first one that fails."""
    try:
        _use(preset, changes)
    except Exception as e:                              # noqa: BLE001  (shown to the user as it is)
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
    return json.dumps({"values": values()})


# ---------------------------------------------------------------- parts
def parts(preset, changes="{}"):
    """The parts of the configuration, in order: name, kind, quantity (0: as many as wanted)."""
    _use(preset, changes)
    joiner = {"spline": "spline", "dovetail": "dovetail_key"}.get(P.seam_style, "union_plug")
    out = [dict(name=f"quadrant_{q}", kind="grid", quantity=1) for q in L.QUADRANTS]
    out.append(dict(name=joiner, kind="joiner", quantity=len(assembly.joiner_locations())))
    out.append(dict(name="mount_plug", kind="mount", quantity=0))
    return out


def _placements(name, kind):
    def matrix(loc):
        t = loc.wrapped.Transformation()
        return [t.Value(r, c) for r in (1, 2, 3) for c in (1, 2, 3, 4)] + [0.0, 0.0, 0.0, 1.0]
    if kind == "grid":
        return [matrix(Pos(0, 0, 0))]
    if kind == "joiner":
        return [matrix(loc) for loc in assembly.joiner_locations()]
    cells = set(L.cells())
    return [matrix(Pos(L.center(*c).X, L.center(*c).Y, P.z_bottom)) for c in MOUNT_CELLS
            if c in cells and not L.is_edge_cell(*c) and c not in P.standoff_cells]


_shapes = {}                                            # (changes key, part) -> shape


def _shape(preset, changes, name):
    key = _use(preset, changes)
    if (key, name) not in _shapes:
        if name.startswith("quadrant_"):
            shape = grid.quadrant(name.split("_")[1])
        elif name == "mount_plug":
            shape = plug.final_mount_plug()
        else:
            shape = assembly.joiner()[1]
        _shapes.clear() if len(_shapes) > 12 else None
        _shapes[(key, name)] = shape
    return _shapes[(key, name)]


def _stl(shape, tolerance, angular):
    BRepTools.Clean_s(shape.wrapped)                    # mesh anew, at these tolerances
    path = tempfile.mktemp(suffix=".stl")
    export_stl(shape, path, tolerance=tolerance, angular_tolerance=angular)
    with open(path, "rb") as fh:
        data = fh.read()
    os.remove(path)
    return data


def _mesh(shape, kind):
    """Indexed mesh for the view (float32 vertices, uint32 triangles), from an STL export:
    much faster than tessellate() on parts with hundreds of thousands of triangles."""
    data = _stl(shape, *VIEW_TOLERANCE[kind])
    n = int(np.frombuffer(data, "<u4", 1, 80)[0])
    tri = np.frombuffer(data, np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), n, 84)["v"]
    verts, index = np.unique(tri.reshape(-1, 3), axis=0, return_inverse=True)
    return verts.astype(np.float32).tobytes(), index.astype(np.uint32).tobytes()


def build_part(preset, changes, name):
    """One part: its mesh for the view, where it goes (4x4 matrices), volume and validity."""
    t = time.time()
    info = next(p for p in parts(preset, changes) if p["name"] == name)
    shape = _shape(preset, changes, name)
    v, tri = _mesh(shape, info["kind"])
    return dict(info, v=v, t=tri, placements=_placements(name, info["kind"]), volume=round(shape.volume, 1),
                valid=bool(shape.is_valid), solids=len(shape.solids()), time=round(time.time() - t, 1))


def stl(preset, changes, name):
    return _stl(_shape(preset, changes, name), P.stl_tolerance, P.stl_angular_tolerance)


def frame(preset, changes="{}"):
    """The printer around the grid, for the view: the bottom 2020 frame and the deck panel."""
    _use(preset, changes)
    w, d, cy, s = P.frame_width_x, P.frame_depth_y, P.frame_center_y, P.frame_size
    bars = [Pos(0, cy + sy * (d + s) / 2, 0) * Box(w + 2 * s, s, s) for sy in (-1, 1)]
    bars += [Pos(sx * (w + s) / 2, cy, 0) * Box(s, d, s) for sx in (-1, 1)]
    deck = Pos(0, cy, P.z_top + P.deck_panel_thickness / 2) * Box(w, d, P.deck_panel_thickness)
    out = []
    for kind, shape in [("frame", b) for b in bars] + [("deck", deck)]:
        v, tri = _mesh(shape, "joiner")
        out.append(dict(kind=kind, v=v, t=tri))
    return out


def readme(preset, changes):
    merged = _merged(preset, changes)
    lines = [f"SnapHex - {PRESETS[preset]['title']}", ""]
    for p in parts(preset, changes):
        lines.append(f"  {p['name']}.stl  x {p['quantity'] or 'as many as your electronics need'}")
    lines += ["", "Print everything base down, as the files come, with no supports.",
              "Use the same slicer profile for the quadrants and the mount plugs: the snap fit lives in the cells' groove.",
              "", "Changed parameters: " + (json.dumps(changes if isinstance(changes, dict) else json.loads(changes or "{}"))
                                           if merged != PRESETS[preset]["changes"] else "none (defaults)")]
    return "\n".join(lines) + "\n"


def zip_all(preset, changes, stls=None):
    """Every part's STL, parts.txt (quantities, how to print) and parameters.json, in a ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in parts(preset, changes):
            z.writestr(f"{p['name']}.stl", stls[p["name"]] if stls else stl(preset, changes, p["name"]))
        z.writestr("parts.txt", readme(preset, changes))
        z.writestr("parameters.json", json.dumps(dict(preset=preset, changes=_merged(preset, changes)), indent=1))
    return buf.getvalue()


# ---------------------------------------------------------------- catalogue
def catalog():
    """Presets, parameters (expression, comment, section, default value) and parts, as JSON text."""
    _use(next(iter(PRESETS)), {})
    vals = values()
    params = [dict(p, value=vals[p["name"]]) for p in configure.parameters()]
    presets = [dict(name=k, title=v["title"], description=v["description"], changes=v["changes"],
                    parts=parts(k)) for k, v in PRESETS.items()]
    return json.dumps(dict(presets=presets, parameters=params))


# ---------------------------------------------------------------- ready-made defaults
def _pre_part(job):
    preset, name = job
    r = build_part(preset, "{}", name)
    data = stl(preset, "{}", name)
    return name, r, data


def pregenerate(folder, presets=None):
    """Every preset with its default values, built natively for the site to show and
    download before its engine has loaded: pre/catalog.json, pre/<preset>.json (each
    part's view mesh, base64, and where it goes; the frame) and pre/<preset>/ with each
    part's STL and the ZIP of all of them."""
    from concurrent.futures import ProcessPoolExecutor
    b64 = lambda b: base64.b64encode(b).decode()          # noqa: E731
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "catalog.json"), "w") as fh:
        fh.write(catalog())
    for preset in presets or PRESETS:
        t = time.time()
        os.makedirs(os.path.join(folder, preset), exist_ok=True)
        names = [p["name"] for p in parts(preset)]
        with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
            done = list(pool.map(_pre_part, [(preset, n) for n in names]))
        out = dict(preset=preset, parts={}, frame=[dict(f, v=b64(f["v"]), t=b64(f["t"])) for f in frame(preset)])
        stls = {}
        for name, r, data in done:
            out["parts"][name] = dict(r, v=b64(r["v"]), t=b64(r["t"]), placements=[[round(x, 6) for x in m] for m in r["placements"]])
            stls[name] = data
            with open(os.path.join(folder, preset, f"{name}.stl"), "wb") as fh:
                fh.write(data)
            print(f"  {preset} {name}: {r['volume']:.0f} mm3, valid {r['valid']}, {r['solids']} solid(s), {r['time']} s", flush=True)
        with open(os.path.join(folder, f"{preset}.json"), "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        with open(os.path.join(folder, preset, f"snap-hex-{preset}.zip"), "wb") as fh:
            fh.write(zip_all(preset, "{}", stls))
        print(f"{preset}: {len(names)} parts, {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__" and sys.argv[1:2] == ["pregenerate"]:
    pregenerate(os.path.join(HERE, "pre"), sys.argv[2:] or None)
elif __name__ == "__main__":
    preset, name = sys.argv[1], sys.argv[2]
    changes = sys.argv[3] if len(sys.argv) > 3 else "{}"
    t0 = time.time()
    cat = json.loads(catalog())
    print("catalog:", [p["name"] for p in cat["presets"]], len(cat["parameters"]), "parameters", f"{time.time() - t0:.1f} s")
    r = build_part(preset, changes, name)
    print(name, {k: v for k, v in r.items() if k not in ("v", "t", "placements")}, len(r["placements"]), "placement(s),",
          len(r["v"]) // 12, "vertices", len(r["t"]) // 12, "triangles")
    print("stl:", len(stl(preset, changes, name)), "bytes;", "evaluate error:", evaluate(preset, '{"grid_gap": "0.15 +"}'))
