"""Generate every part into out/.

- quadrant_{BL,BR,FL,FR}: the four printable grid pieces (built in parallel)
- union_plug: joins quadrants across a seam (39 needed)
- mount_plug: snaps into any cell from below, for mounting electronics
- test_patch_7: 7 cells, to test the plug fit before printing a quadrant
- assembly.step (with --assembly, ~200 MB): quadrants + union plugs in place
STEP for Fusion, STL for the slicer, BREP for validate_gridv8.py.

usage: build.py [--no-previews] [--assembly] [quadrant ...]
       build.py --mounts      mount plug test variants and a strip of cells to test them
       build.py --coupons     seam test coupons (spline and v8 styles), the two-cell
                              spline pair, and their loose parts
"""

import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from build123d import Color, Compound, Pos, Rot, export_brep, export_step, export_stl, import_brep

import grid
import layout as L
import params as P
import plug
import render
from assembly import joiner, joiner_locations

OUT = Path(__file__).parent.parent / "out"
FLOWER = [(0, 0), (-1, 0), (1, 0), (-1, 1), (0, 1), (-1, -1), (0, -1)]


def export(name, shape):
    export_step(shape, OUT / f"{name}.step")
    export_stl(shape, OUT / f"{name}.stl", tolerance=P.stl_tolerance, angular_tolerance=P.stl_angular_tolerance)
    export_brep(shape, OUT / f"{name}.brep")


def build_quadrant(q):
    t = time.time()
    body = grid.quadrant(q)
    body.label = f"quadrant_{q}"
    export(f"quadrant_{q}", body)
    return q, body.is_valid, len(body.solids()), body.volume, time.time() - t


def build_coupons(previews):
    """Seam test coupons (spline style, and gridv8's for comparison), the two-cell
    spline pair, and the loose parts they need. Each also as an assembled STEP."""
    from build123d import Keep, Plane

    t = time.time()
    pieces = {(style, s): grid.coupon(s, style) for style in ("spline", "v8") for s in "LR"}
    for (style, s), shape in pieces.items():
        export(f"coupon_{style}_{s}", shape)
    sp, up, mp = plug.spline(), plug.union_plug(), plug.final_mount_plug()
    loose = [("spline", sp), ("union_plug", up), ("mount_plug", mp)]
    loose += [(f"spline_{v:.1f}mm", plug.spline(v, label=f"{v:.1f}")) for v in P.spline_variants]
    if P.seam_bottom_link:
        dp = plug.double_plug()
        loose.append(("double_plug", dp))
    for name, shape in loose:
        export(name, shape)
    rows = sorted({j for _, j in P.coupon_cells["L"]})
    mids = [(L.center(-1, j) + L.center(0, j)) * 0.5 for j in rows]
    print(f"coupons: {time.time() - t:.1f}s; spline style needs {len(rows)} splines, v8 needs {len(rows)} union plugs")

    grey, plugc, splinec, unionc = "#d9d4c7", "#e8846b", "#7fa7d9", "#c98bc4"

    def part(shape, label, color):
        shape.label, shape.color = label, Color(color)
        return shape

    def seated_spline(cell):
        return part(grid.spline_location(cell, 0) * sp.moved(Pos(0, 0, -P.spline_thickness / 2)), "spline", splinec)

    spline_parts = [part(pieces[("spline", s)], f"coupon_spline_{s}", grey) for s in "LR"]
    spline_parts += [seated_spline((-1, j)) for j in rows]
    if P.seam_bottom_link:
        spline_parts += [part(Pos(m.X, m.Y, P.z_bottom) * dp, "double_plug", plugc) for m in mids]
    # mount plugs seated from the mount side: one under a seam block, one in a plain cell
    spline_parts += [part(Pos(L.center(*c).X, L.center(*c).Y, P.z_bottom) * mp, "mount_plug", plugc) for c in ((-1, 2), (1, 2))]
    v8 = [part(pieces[("v8", s)], f"coupon_v8_{s}", grey) for s in "LR"]
    v8 += [part(Pos(m.X, m.Y, 0) * up, "union_plug", unionc) for m in mids]
    # smallest test: the two seam cells and one spline
    pair = [part(grid.coupon(s, "spline", P.pair_cells), f"spline_pair_{s}", grey) for s in "LR"]
    for shape in pair:
        export(shape.label, shape)
    pair.append(seated_spline(P.pair_cells["L"][0]))
    for name, parts in (("coupon_spline", spline_parts), ("coupon_v8", v8), ("spline_pair", pair)):
        export_step(Compound(children=parts, label=f"{name}_assembly"), OUT / f"{name}_assembly.step")
    if not previews:
        return
    items = [(s, grey if "coupon" in s.label else splinec if s.label == "spline" else plugc) for s in spline_parts]
    render.png(OUT / "preview_coupon_top.png", items, elev=45, azim=-60, title="corpo de prova (cavilha chata): lado do painel", zoom=0.75)
    cut = Plane.XZ.offset(-mids[1].Y)
    halves = [(h, color) for shape, color in items if (h := shape.split(cut, keep=Keep.BOTTOM))]
    render.png(OUT / "preview_coupon_cut.png", halves, elev=10, azim=-90, title="corte na emenda: lâmina no bloco, mount plug embaixo", zoom=0.45)


def build_mounts():
    """Mount plug test variants (letter engraved), a strip of plain cells to test them
    side by side, and an assembled STEP. Variants printed upside down come out flipped."""
    t = time.time()
    cells = P.mount_test_cells
    strip = grid.piece(L.quadrant(*cells[0]), cells, frozenset(cells), "v8")
    export("mount_test_cells", strip)
    parts = [strip]
    strip.label, strip.color = "mount_test_cells", Color("#d9d4c7")
    for name, cell in zip(P.mount_batch, cells):
        opts = P.mount_variants[name]
        if opts.get("full_face"):
            p = plug.full_face_plug(label=name, **{k: v for k, v in opts.items() if k != "full_face"})
        else:
            p = plug.mount_plug(label=name, **opts)
        upside_down = opts.get("retention_angle") is not None
        export(f"mount_plug_{name}", plug.print_upside_down(p) if upside_down else p)
        if P.mount_open_top and opts.get("full_face") and not upside_down:
            export(f"mount_plug_{name}_open", plug.full_face_plug(label=name, open_top=True,
                                                                  **{k: v for k, v in opts.items() if k != "full_face"}))
        seated = Pos(L.center(*cell).X, L.center(*cell).Y, P.z_bottom) * p
        seated.label, seated.color = f"mount_plug_{name}", Color("#e8846b")
        parts.append(seated)
        print(f"mount_plug_{name}: {p.volume:.0f} mm3{', printed upside down' if upside_down else ''}")
    export_step(Compound(children=parts, label="mount_test_assembly"), OUT / "mount_test_assembly.step")
    print(f"mounts: {time.time() - t:.1f}s")


def main(quadrants, previews, assembly):
    OUT.mkdir(exist_ok=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=len(quadrants) or 1) as pool:
        jobs = [pool.submit(build_quadrant, q) for q in quadrants]
        mp = plug.final_mount_plug()
        link_name, link = joiner()
        patch = grid.patch([L.center(i, j) for i, j in FLOWER])
        for name, shape in (("mount_plug", mp), (link_name, link), ("test_patch_7", patch)):
            export(name, shape)
        for job in jobs:
            q, valid, nsolids, vol, dt = job.result()
            print(f"quadrant {q}: {'ok' if valid and nsolids == 1 else 'INVALID'}, {vol:.0f} mm3, {dt:.1f}s")
    links = joiner_locations()
    print(f"mount plug {mp.volume:.1f} mm3, {link_name} {link.volume:.1f} mm3 (x{len(links)}, seam style {P.seam_style})")

    if assembly and len(quadrants) == 4:
        parts = [import_brep(OUT / f"quadrant_{q}.brep") for q in L.QUADRANTS]
        for i, loc in enumerate(links):
            u = loc * link
            u.label = f"{link_name}_{i + 1}"
            parts.append(u)
        export_step(Compound(parts), OUT / "assembly.step")

    if previews:
        seated = mp.moved(Pos(0, 0, P.z_bottom))
        render.png(OUT / "preview_plug.png", [(mp, "#e8846b")], elev=32, azim=-55, title="mount plug", zoom=0.7)
        render.png(OUT / f"preview_{link_name}.png", [(link, "#c98bc4")], elev=35, azim=-60, title=link_name, zoom=0.6)
        render.png(OUT / "preview_iso.png", [(patch, "#d9d4c7"), (seated, "#e8846b")], elev=40, azim=-60,
                   title="7 células + plug encaixado", zoom=0.8)
        if len(quadrants) == 4:
            render.layout_map(OUT / "preview_layout.png", {q: import_brep(OUT / f"quadrant_{q}.brep") for q in L.QUADRANTS})
    print(f"done in {time.time() - t:.1f}s -> {OUT}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    previews = "--no-previews" not in sys.argv
    OUT.mkdir(exist_ok=True)
    if "--coupons" in sys.argv:
        build_coupons(previews)
    elif "--mounts" in sys.argv:
        build_mounts()
    else:
        main([q for q in L.QUADRANTS if not args or q in args], previews, assembly="--assembly" in sys.argv)
