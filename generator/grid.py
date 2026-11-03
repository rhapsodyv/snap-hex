"""Hex grid: cell openings, the upper floor along the seams, and the four quadrants.

A quadrant is built in four passes:
1. lower floor: the 2D region of its cells (seam walls pulled back by half the
   gap) plus its share of the perimeter band, extruded, bottom edge chamfered;
2. each cell opening is cut: rounded-hex core, snap groove, lead-in chamfers;
3. cells along the seams get the upper floor, a ring up to the deck panel that
   is open where a union plug bridges the seam; standoffs get a capped ring;
4. screw pads on the band, standoff slots, center notches.
"""

from functools import lru_cache, reduce
from math import cos, sin, radians, sqrt, tan

from build123d import (
    Align, Axis, Box, Cylinder, Face, Line, Location, Polyline, Pos, RectangleRounded,
    Rot, ThreePointArc, Transition, Vector, Wire, chamfer, extrude, loft, sweep,
)

import layout as L
import params as P
import profiles

W = P.hex_move_width
A_OUT = W / 2  # apothem of the wall-center hexagon
MIN = (Align.MIN, Align.MIN, Align.MIN)


def _n(k):
    a = radians(60 * k)
    return Vector(cos(a), sin(a), 0)


def _t(k):
    a = radians(60 * k)
    return Vector(-sin(a), cos(a), 0)


def rounded_hex_path(apothem, r):
    """Closed rounded hexagon, flats facing +-X, starting at (apothem, 0) going +Y."""
    h = (apothem - r) * sqrt(3) / 3
    start = _n(0) * apothem
    edges, prev = [], start
    for k in range(6):
        flat_end = _n(k) * apothem + _t(k) * h
        edges.append(Line(prev, flat_end))
        center = _n(k) * (apothem - r) + _t(k) * h
        nxt = _n(k + 1) * apothem - _t(k + 1) * h
        mid_dir = (flat_end + nxt) * 0.5 - center
        edges.append(ThreePointArc(flat_end, center + mid_dir.normalized() * r, nxt))
        prev = nxt
    edges.append(Line(prev, start))
    return Wire(edges)


def hex_path(apothems):
    """Closed sharp hexagon with one apothem per edge, starting at the middle of edge 0 going +Y."""
    a = list(apothems) if hasattr(apothems, "__len__") else [apothems] * 6
    verts = []
    for k in range(6):
        n1, n2, a1, a2 = _n(k), _n(k + 1), a[k], a[(k + 1) % 6]
        det = n1.X * n2.Y - n1.Y * n2.X
        verts.append(Vector((a1 * n2.Y - a2 * n1.Y) / det, (n1.X * a2 - n2.X * a1) / det, 0))
    pts = [Vector(a[0], 0, 0)] + verts + [Vector(a[0], 0, 0)]
    return Wire([Line(p, q) for p, q in zip(pts, pts[1:])])


def sharp_hex_path(apothem):
    return hex_path(apothem)


def _prism(face, z0, z1):
    return extrude(face.moved(Location((0, 0, z0))), amount=z1 - z0)


def _polygon(points):
    return Face(Wire(Polyline(*[Vector(x, y, 0) for x, y in points], close=True)))


def _rect(x0, x1, y0, y1):
    return _polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _inner_path():
    return rounded_hex_path(P.hex_r, P.hex_corner_radius)


@lru_cache
def lower_cutter():
    """Opening of one cell in the lower floor, centered at the origin."""
    inner = _inner_path()
    core = _prism(Face(inner), P.z_bottom - 1, P.z_floor_split + 1)
    swept = [
        sweep(profiles.to_face(profiles.groove_cut(P.lower_groove_z), P.hex_r), inner),
        sweep(profiles.to_face(profiles.bottom_chamfer_cut(), P.hex_r), inner),
        sweep(profiles.to_face(profiles.chamfer_cut(P.z_floor_split, P.bottom_chamfer, top=True), P.hex_r), inner),
    ]
    return reduce(lambda a, b: a + b, swept, core)


@lru_cache
def upper_ring(open_walls=(), apothems=(A_OUT,) * 6):
    """Upper floor ring of one cell. It starts below the floor split so it also
    fills the lower floor's top chamfer wherever the wall continues upward."""
    inner = _inner_path()
    outer = hex_path(apothems)
    ring = _prism(Face(outer), P.z_floor_split - 1.4, P.z_top)
    ring -= _prism(Face(inner), 0, P.z_top + 1)
    ring -= sweep(profiles.to_face(profiles.groove_cut(P.upper_groove_z), P.hex_r), inner)
    ring -= sweep(profiles.to_face(profiles.top_round_cut(), P.hex_r), inner)
    ring -= sweep(profiles.to_face(profiles.top_round_cut(overlap_below_top=False), apothems[0], -1), outer,
                  transition=Transition.RIGHT)
    h = (P.hex_r - P.hex_corner_radius) * sqrt(3) / 3   # straight part of the flat
    for k in open_walls:
        opening = Box(A_OUT + 0.1 - (P.hex_r - 1), 2 * h, 8, align=MIN).moved(Pos(P.hex_r - 1, -h, 1))
        ring -= Rot(0, 0, 60 * k) * opening
    return ring


@lru_cache
def capped_top(apothems=(A_OUT,) * 6, cap_z=P.standoff_cap_z):
    """Upper floor closed by a solid cap: standoffs, and the seam strip in the dovetail style."""
    outer = hex_path(apothems)
    body = _prism(Face(outer), P.z_floor_split - 1.4, P.z_top)
    body -= _prism(Face(_inner_path()), 0, cap_z)
    body -= sweep(profiles.to_face(profiles.chamfer_cut(P.z_top, P.standoff_chamfer, top=True), apothems[0], -1), outer,
                  transition=Transition.RIGHT)
    return body


def standoff_top():
    return capped_top()


def _wall_frame(cell, k):
    """Location at the middle of wall k of a cell: x across the wall (outward), y along it."""
    return Pos(L.center(*cell)) * Rot(0, 0, 60 * k) * Pos(A_OUT, 0, 0)


def bowtie(half_length, waist, end):
    """Bowtie outline across a wall, centered on the wall center line."""
    return _polygon([(-half_length, -end / 2), (0, -waist / 2), (half_length, -end / 2),
                     (half_length, end / 2), (0, waist / 2), (-half_length, end / 2)])


def dovetail_outline(side=0.0, end=0.0):
    """Dovetail outline centered on the seam, with the side walls moved in by `side`
    and the tail ends cut back by `end`, keeping the side walls on the same lines."""
    length, neck, tail = P.dovetail_length, P.dovetail_neck, P.dovetail_tail
    tail_at_end = neck + (tail - neck) * (length - end) / length
    return bowtie(length - end, neck - 2 * side, tail_at_end - 2 * side)


def socket_side_inset(z):
    """How far the socket's side walls have moved in at height z (they lean in going up)."""
    return (z - P.dovetail_floor_z) * tan(radians(P.socket_angle))


@lru_cache
def _socket():
    """Dovetail socket, open to the panel side; end walls vertical, side walls leaning in."""
    z1 = P.z_top + 0.5
    return loft([dovetail_outline().moved(Pos(0, 0, P.dovetail_floor_z)),
                 dovetail_outline(socket_side_inset(z1)).moved(Pos(0, 0, z1))], ruled=True)


def dovetail_socket(cell, k):
    return _wall_frame(cell, k) * _socket()


def spline_axis(k):
    """Splines run along X across the vertical seam and along Y across the back/front
    seam (even through its slanted walls), so each pair of quadrants slides together
    in one straight move."""
    return 0 if k in (0, 3) else 90


def spline_location(cell, k):
    """Center of the spline joining a cell to its neighbor across wall k."""
    m = (L.center(*cell) + L.center(*L.neighbor(*cell, k))) * 0.5
    return Pos(m.X, m.Y, P.spline_z) * Rot(0, 0, spline_axis(k))


def spline_slot(cell, k):
    c = P.spline_clearance
    box = Box(2 * (P.spline_half_length + P.spline_end_clearance), P.spline_width + 2 * c, P.spline_thickness + 2 * c)
    return spline_location(cell, k) * box


def bridge_notch(cell, k):
    """Opening at the bottom of a seam wall for the bridge of a double plug."""
    h = (P.hex_r - P.hex_corner_radius) * sqrt(3) / 3
    top = P.z_bottom + P.bridge_height + P.bridge_clearance
    box = Box(A_OUT + 0.1 - (P.hex_r - 1), 2 * h, top - P.z_bottom + 1, align=MIN)
    return Pos(L.center(*cell)) * Rot(0, 0, 60 * k) * box.moved(Pos(P.hex_r - 1, -h, P.z_bottom - 1))


def _slot(x, y_start):
    face = RectangleRounded(P.slot_width, P.slot_length, P.slot_round).moved(Pos(x, y_start + P.slot_length / 2))
    return extrude(face.moved(Pos(0, 0, P.z_floor_split)), amount=P.z_top - P.z_floor_split + 1)


def standoff_slots():
    """Slot cutters as (quadrant, solid); every slot opens toward +Y."""
    out = []
    for sx in (-P.slot_x, P.slot_x):
        for sy in P.slot_y_start:
            out.append((("B" if sy > P.frame_center_y else "F") + ("L" if sx < 0 else "R"), _slot(sx, sy)))
    return out


@lru_cache
def _pad_local():
    """Screw pad in a local frame: x goes inward from the band's outer face, y along the band."""
    w, t, r = P.pad_width / 2, P.pad_wall, P.pad_round
    z0, zt = P.z_floor_split - 0.4, P.z_top
    pts = [(-w, z0), (-w, zt - r), ("arc", (-w + r, zt - r), (-w + r, zt)), (w - r, zt),
           ("arc", (w - r, zt - r), (w, zt - r)), (w, z0)]
    segs = profiles._closed(pts)
    # profile drawn in the YZ plane: reuse to_face (XZ plane) and turn it
    tab = extrude(Rot(0, 0, 90) * profiles.to_face(segs, 0), amount=t, dir=(1, 0, 0))
    pocket = Box(P.lateral_wall_width - t, 2 * w, 10, align=MIN).moved(Pos(t, -w, -5))
    hole = Rot(0, 90, 0) * Cylinder(P.screw_hole_d / 2, t + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return tab, pocket, hole.moved(Pos(-1, 0, 0))


def _pad_location(side, pos):
    if side == "L":
        return Pos(-L.X_OUT, pos, 0)
    if side == "R":
        return Pos(L.X_OUT, pos, 0) * Rot(0, 0, 180)
    if side == "B":
        return Pos(pos, L.Y1, 0) * Rot(0, 0, -90)
    return Pos(pos, L.Y0, 0) * Rot(0, 0, 90)


def _apothems(cell, members=None):
    """Per-wall apothem of a cell's outline: pulled back at seams; in a free-standing
    piece (members given) pushed out to a full wall where there is no neighbor."""
    out = []
    for k in range(6):
        nb = L.neighbor(*cell, k)
        if members is not None and nb not in members:
            out.append(A_OUT + P.hex_edge_width / 2)
        elif L.quadrant(*nb) != L.quadrant(*cell):
            out.append(A_OUT - P.grid_gap / 2)
        else:
            out.append(A_OUT)
    return tuple(out)


def union_walls(members=None):
    """Seam walls that get a union (cell -> walls), limited to cells present in the piece."""
    out = {}
    for cell, walls in L.open_walls().items():
        ws = {k for k in walls if members is None or (cell in members and L.neighbor(*cell, k) in members)}
        if ws:
            out[cell] = ws
    return out


def lower_region(q, cells, members=None):
    """2D region of a piece's lower floor: its cells, plus its share of the band for a quadrant."""
    hexes = [Face(hex_path(_apothems(c, members))).moved(Pos(L.center(*c))) for c in cells]
    region = hexes[0].fuse(*hexes[1:]).clean() if len(hexes) > 1 else hexes[0]
    if members is not None:
        return region
    gap = P.grid_gap / 2
    inner = _polygon(L.outline(P.lateral_wall_width))
    outer = _polygon(L.outline())
    big = 1000
    xr = (-big, 0) if q[1] == "L" else (0, big)
    yr = (P.frame_center_y + gap, big) if q[0] == "B" else (-big, P.frame_center_y - gap)
    region = (region & inner) + ((outer - inner) & _rect(*xr, *yr))
    for x0, x1, y0, y1 in L.notches():
        region -= _rect(x0, x1, y0, y1)
    return region


def piece(q, cells, members=None, style=None):
    """Lower floor of the given cells, seam features and, for a full quadrant
    (members=None), the band, pads, standoffs and notches."""
    style = style or P.seam_style
    quadrant_mode = members is None
    body = _prism(lower_region(q, cells, members), P.z_bottom, P.z_floor_split)
    bottom = body.edges().filter_by_position(Axis.Z, P.z_bottom - 1e-3, P.z_bottom + 1e-3)
    body = chamfer(bottom, length=P.perimeter_chamfer)

    inner_prism = _prism(_polygon(L.outline(P.lateral_wall_width)), P.z_bottom - 2, P.z_top + 2)
    cut, cutters = lower_cutter(), []
    for c in cells:
        moved = cut.moved(Pos(L.center(*c)))
        cutters.append(moved & inner_prism if quadrant_mode and L.is_edge_cell(*c) else moved)
    body -= cutters

    adds, removes = [], []
    for cell, walls in union_walls(members).items():
        if cell not in cells:
            continue
        ap = _apothems(cell, members)
        if style == "v8":
            adds.append(upper_ring(tuple(sorted(walls)), ap).moved(Pos(L.center(*cell))))
        else:
            adds.append(capped_top(ap, P.block_z).moved(Pos(L.center(*cell))))
            for k in walls:
                removes.append(spline_slot(cell, k) if style == "spline" else dovetail_socket(cell, k))
                if P.seam_bottom_link:
                    removes.append(bridge_notch(cell, k))

    if quadrant_mode:
        for cell in P.standoff_cells:
            if L.quadrant(*cell) == q:
                adds.append(standoff_top().moved(Pos(L.center(*cell))))
        tab, pocket, hole = _pad_local()
        for side, pos in L.pads():
            if L.pad_quadrant(side, pos) == q:
                loc = _pad_location(side, pos)
                adds.append(loc * tab)
                removes += [loc * pocket, loc * hole]
        removes += [s for sq, s in standoff_slots() if sq == q]
    body += adds
    if removes:
        body -= removes
    return body


def quadrant(q, style=None):
    return piece(q, [c for c in L.cells() if L.quadrant(*c) == q], style=style)


def coupon(side, style, layout=None):
    """Half of a seam test coupon (side L or R), outer walls full thickness.
    layout: {"L": cells, "R": cells}, default the 3x3 coupon."""
    layout = layout or P.coupon_cells
    members = frozenset(c for cells in layout.values() for c in cells)
    cells = layout[side]
    return piece(L.quadrant(*cells[0]), cells, members, style)


def patch(centers):
    """A small free-standing piece of lower floor (for fit tests)."""
    outline = Face(hex_path(A_OUT))
    base = reduce(lambda a, b: a + b, [outline.moved(Pos(c)) for c in centers])
    body = _prism(base, P.z_bottom, P.z_floor_split)
    return body - [lower_cutter().moved(Pos(c)) for c in centers]


def lattice(i, j):
    return L.center(i, j)
