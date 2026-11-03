"""Compare the generated geometry with Fusion's gridv8.

Builds the quadrants in gridv8's seam style ('v8') for the comparison.
Reference data in reference/gridv8/ was cut from gridv8 (Fusion export):
- section_*.json, sections_z.json: one cell and the mount plug, cut in several planes
- fusion_sections.npz: whole quadrants at z=0 and z=6, union plug at three heights
- fusion_volumes.json

Outlines are compared both ways (every reference point near ours and vice versa).
A few spots where gridv8 itself breaks its own rules are listed in KNOWN and
reported separately.
Writes an overlay plot of the detail cuts to out/validation.png.
"""

import json
from math import cos, sin, radians
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from build123d import GeomType, Plane, Pos, export_brep, import_brep, section
from scipy.spatial import cKDTree

import grid
import layout as L
import params as P
import plug

HERE = Path(__file__).parent
REF = HERE / "reference" / "gridv8"
OUT = HERE.parent / "out"

CELL = L.center(-1, 1)       # the cell holding the plug in gridv8, (-10.976, 19.012)
PLUG_Z = 7.0                 # gridv8 shows the plug 9.9 mm above its seated position
STEP = 0.02
TOL = 0.05

# (quadrant, x0, x1, y0, y1, why)
KNOWN = [
    ("BL", -177, -163, 4, 15, "gridv8: emenda sem folga (Offset Faces pulou estas faces)"),
    ("FL", -177, -163, 4, 15, "gridv8: emenda sem folga (Offset Faces pulou estas faces)"),
    ("BL", -166, -152, 4, 15, "gridv8: emenda sem folga de um lado"),
    ("BL", -133, -119, 4, 15, "gridv8: emenda sem folga (Offset Faces pulou estas faces)"),
    ("FL", -133, -119, 4, 15, "gridv8: emenda sem folga (Offset Faces pulou estas faces)"),
    ("BL", -122, -108, 4, 15, "gridv8: emenda sem folga de um lado"),
    ("BR", 218, 232, 4, 15, "gridv8: emenda sem folga de um lado"),
    ("FL", -1.5, 0, -212, -206, "gridv8: meia-parede da emenda aparada em y=-206,6 no entalhe da frente"),
    ("FR", 0, 1.5, -212, -206, "gridv8: meia-parede da emenda aparada em y=-206,6 no entalhe da frente"),
    ("FL", -21, -19, -229, -221, "gridv8: face do entalhe da frente com folga de emenda (0,075)"),
    ("FL", -229, -226, 6, 10, "gridv8: folga diferente onde a divisão da borda encontra a emenda"),
    ("BR", 222, 229, 195, 200, "gridv8: lasca do canto virou corpo separado (Body749, oculto)"),
    ("union", -10.5, -6.5, 26.5, 30.5, "gridv8: aba da face a 60 graus deslocada 0,2 mm"),
    ("union", 6.5, 10.5, 26.5, 30.5, "gridv8: aba da face a 120 graus deslocada 0,2 mm (espelho)"),
]


def seg_points(segs, step=STEP):
    pts = []
    for x0, y0, x1, y1 in segs:
        n = max(2, int(np.hypot(x1 - x0, y1 - y0) / step) + 1)
        u = np.linspace(0, 1, n)[:, None]
        pts.append(np.hstack([x0 + (x1 - x0) * u, y0 + (y1 - y0) * u]))
    return np.vstack(pts)


def ref_points(polylines):
    return seg_points([(*a, *b) for line in polylines for a, b in zip(line, line[1:])])


def our_points(shape, plane, axes, step=STEP):
    pts = []
    for e in section(shape, section_by=plane).edges():
        n = 2 if e.geom_type == GeomType.LINE else max(3, int(e.length / step) + 1)
        p = [[tuple(e.position_at(t))[i] for i in axes] for t in np.linspace(0, 1, n)]
        pts.append(np.hstack([p[:-1], p[1:]]))
    return seg_points(np.vstack(pts), step)


def zplane(z):
    return Plane(origin=(0, 0, z), x_dir=(1, 0, 0), z_dir=(0, 0, 1))


def hex_dist(p, center):
    q = p - np.array(center)
    return np.max(np.abs(np.stack([q @ np.array([cos(radians(a)), sin(radians(a))]) for a in (0, 60, 120)])), axis=0)


def compare(ref, ours, known=()):
    """Max distance both ways, outside and inside the known-difference boxes."""
    d1, _ = cKDTree(ours).query(ref)
    d2, _ = cKDTree(ref).query(ours)
    pts, d = np.vstack([ref, ours]), np.concatenate([d1, d2])
    inside = np.zeros(len(pts), dtype=bool)
    hits = []
    for x0, x1, y0, y1, why in known:
        m = (pts[:, 0] >= x0) & (pts[:, 0] <= x1) & (pts[:, 1] >= y0) & (pts[:, 1] <= y1)
        if (d[m] > TOL).any():
            hits.append((why, d[m].max()))
        inside |= m
    rest = d[~inside]
    return rest.max(), rest.mean(), hits


def detail_cases(bl):
    """Cuts through the plug's cell in the back-left quadrant, and through the mount plug."""
    y19 = json.load(open(REF / "section_y19.06.json"))
    x10 = json.load(open(REF / "section_x-10.97.json"))
    zs = json.load(open(REF / "sections_z.json"))
    mp = plug.mount_plug(supports=False).moved(Pos(CELL.X, CELL.Y, PLUG_Z))
    ply = Plane(origin=(0, 19.06, 0), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    plx = Plane(origin=(-10.97, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    c2 = (CELL.X, CELL.Y)
    cases = [
        ("parede entre células (Y=19,06)", ref_points(y19["grid-back-left"]), our_points(bl, ply, (0, 2)),
         lambda p: (p[:, 0] > -23.7) & (p[:, 0] < -20.2)),
        ("vértices da célula (X=-10,97)", ref_points(x10["grid-back-left"]), our_points(bl, plx, (1, 2)),
         lambda p: ((p[:, 0] > 7.4) & (p[:, 0] < 8.6)) | ((p[:, 0] > 29.4) & (p[:, 0] < 30.6))),
        ("célula no canal (Z=0)", ref_points(zs["grid_0.0"]), our_points(bl, zplane(0.0), (0, 1)),
         lambda p: hex_dist(p, c2) < P.hex_r + 1.0),
        ("célula parede cheia (Z=2)", ref_points(zs["grid_2.0"]), our_points(bl, zplane(2.0), (0, 1)),
         lambda p: hex_dist(p, c2) < P.hex_r + 1.0),
        ("mount plug (Y=19,06)", ref_points(y19["Body763"]), our_points(mp, ply, (0, 2)), lambda p: p[:, 0] < 99),
    ]
    for z in (9.0, 9.9, 11.0):
        cases.append((f"mount plug (Z={z})".replace(".", ","), ref_points(zs[f"plug_{z}"]), our_points(mp, zplane(z), (0, 1)),
                      lambda p: p[:, 0] < 99))
    return cases


def _v8_quadrant(q):
    """Build in a worker process; OCCT shapes don't pickle, so hand back a BREP file."""
    path = OUT / f"_v8_quadrant_{q}.brep"
    export_brep(grid.quadrant(q, style='v8'), path)
    return path


def main():
    OUT.mkdir(exist_ok=True)
    ref = np.load(REF / "fusion_sections.npz")
    vols = json.load(open(REF / "fusion_volumes.json"))
    worst = 0.0
    known_hits = []

    # gridv8's own seam style, whatever the default is (built in parallel)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=4) as pool:
        bodies = {q: import_brep(p) for q, p in zip(L.QUADRANTS, pool.map(_v8_quadrant, L.QUADRANTS))}

    print("== detalhes (célula e mount plug)")
    known_plug = [(x0, x1, y0, y1, why) for q, x0, x1, y0, y1, why in KNOWN if q == "union"]
    known_mount = [(x0, x1, y0, y1, "gridv8: lâminas da face a 60 graus deslocadas 0,2 mm") for x0, x1, y0, y1, _ in known_plug[:1]]
    fig, axes = plt.subplots(2, 4, figsize=(22, 11))
    for ax, (name, r, o, region) in zip(axes.flat, detail_cases(bodies["BL"])):
        r, o = r[region(r)], o[region(o)]
        mx, mean, hits = compare(r, o, known_mount if "Z=" in name and "plug" in name else ())
        worst = max(worst, mx)
        known_hits += hits
        print(f"  {name:34s} máx {mx:.3f}  média {mean:.4f}")
        ax.scatter(r[:, 0], r[:, 1], s=0.6, c="#333", label="gridv8 (Fusion)")
        ax.scatter(o[:, 0], o[:, 1], s=0.3, c="#e63", label="build123d")
        ax.set_title(f"{name}\nmáx {mx:.3f} mm", fontsize=9)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.3)
        ax.legend(fontsize=7, loc="upper right", markerscale=6)
    fig.tight_layout()
    fig.savefig(OUT / "validation.png", dpi=110)

    print("== union plug")
    up = plug.union_plug().moved(Pos(0, CELL.Y, 0))
    print(f"  volume {up.volume:.1f} vs {vols['union']} ({up.volume - vols['union']:+.1f})")
    for z in (3.5, 4.95, 6.8):
        mx, mean, hits = compare(seg_points(ref[f"union_z{z}"]), our_points(up, zplane(z), (0, 1)), known_plug)
        worst = max(worst, mx)
        known_hits += hits
        print(f"  z={z:<5} máx {mx:.3f}  média {mean:.4f}")

    print("== quadrantes")
    for q, body in bodies.items():
        print(f"  {q}: volume {body.volume:.1f} vs {vols[q]} ({body.volume - vols[q]:+.1f})")
        known = [(x0, x1, y0, y1, why) for kq, x0, x1, y0, y1, why in KNOWN if kq == q]
        for z in (0.0, 6.0):
            mx, mean, hits = compare(seg_points(ref[f"{q}_z{z}"]), our_points(body, zplane(z), (0, 1), 0.05), known)
            worst = max(worst, mx)
            known_hits += [(f"{q} z={z}: {why}", d) for why, d in hits]
            print(f"     z={z:<4} máx {mx:.3f}  média {mean:.4f}")

    print(f"\npior desvio fora das diferenças conhecidas: {worst:.3f} mm")
    if known_hits:
        print("diferenças conhecidas do gridv8 (ignoradas):")
        for why, d in known_hits:
            print(f"  {d:.3f} mm  {why}")


if __name__ == "__main__":
    main()
