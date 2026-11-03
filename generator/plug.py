"""Mount plug: snaps into the lower floor of a cell from below.

Each of the six faces has a pocket with two cantilever leaves anchored at the
same end. The outer leaf carries the bump; the backing leaf is angled so it
sits 0.2 mm behind the outer one at the tip, so it starts sharing the load
right away while each leaf stays thin. Built for the +X face, then patterned.
"""

from functools import reduce
from math import cos, hypot, radians, sin, tan

from build123d import (
    Align, Axis, Box, Cone, Cylinder, Face, FontStyle, Location, Plane, Pos, Rot, Text, Vector,
    Wire, Polyline, chamfer, extrude, loft, mirror,
)

import params as P
import profiles
from grid import rounded_hex_path

MIN = (Align.MIN, Align.MIN, Align.MIN)


def _box(x0, x1, y0, y1, z0, z1):
    return Box(x1 - x0, y1 - y0, z1 - z0, align=MIN).moved(Pos(x0, y0, z0))


def _plan_prism(points_xy, z0, z1):
    face = Face(Wire(Polyline(*[Vector(x, y, 0) for x, y in points_xy], close=True)))
    return extrude(face.moved(Location((0, 0, z0))), amount=z1 - z0)


def _support(element_plan, zr, upside_down, window=None):
    """Floor raised under a floating spring element, one layer short of it, on the side
    that faces the bed when printing, so the element's first layer is not printed in
    the air. It is part of the pocket floor; the element breaks free on its first flex."""
    z0, z1 = window or P.window_z
    layer = P.print_layer
    lo, hi = (z0, zr[0] - layer) if not upside_down else (zr[1] + layer, z1)
    if hi - lo < 0.05:
        return None
    return extrude(element_plan.moved(Pos(0, 0, lo)), amount=hi - lo)


def _leaf_z(zr, upside_down):
    """Element heights as gridv8 has them over the bed: mirrored about mid-height when
    the plug prints upside down (the window is symmetric), so the elements and their
    supports still start on whole layers."""
    return (P.plug_height - zr[1], P.plug_height - zr[0]) if upside_down else zr


def envelope(height=None):
    body = extrude(Face(rounded_hex_path(P.plug_apothem, P.plug_corner_radius)), amount=height or P.plug_height)
    rims = body.edges().filter_by(Axis.Z, reverse=True)
    return chamfer(rims, length=P.plug_chamfer)


def face_features(retention_angle=None, supports=True):
    """Pocket, leaves and bump for the +X face. s runs along the face (+Y), d goes inward.
    retention_angle: see profiles.bump (also means the plug prints upside down).
    supports: raise the pocket floor under the leaves to one layer below them."""
    a, L = P.plug_apothem, P.plug_flat_half
    w = P.lock_wall_width
    tip_s = L - P.outer_leaf_end_gap

    pocket = _box(a - P.window_depth, a + 1, -L, L, *P.window_z)

    flip = retention_angle is not None
    outer_z, inner_z = _leaf_z(P.outer_leaf_z, flip), _leaf_z(P.inner_leaf_z, flip)
    outer_leaf = _box(a - w, a, -L - 0.3, tip_s, *outer_z)

    # backing leaf: a w-thick strip from the root (pocket end) to the tip, angled outward
    root = (-L, P.inner_leaf_root_d)
    tip = (P.inner_leaf_tip_s, P.inner_leaf_tip_d)
    ds, dd = tip[0] - root[0], tip[1] - root[1]
    n = hypot(ds, dd)
    us, ud = ds / n, dd / n          # along the leaf
    ns, nd = -ud, us                 # across it, pointing inward (+d)
    root_ext = (root[0] - 0.3 * us, root[1] - 0.3 * ud)
    strip = [root_ext, tip, (tip[0] + w * ns, tip[1] + w * nd), (root_ext[0] + w * ns, root_ext[1] + w * nd)]
    inner_leaf = _plan_prism([(a - d, s) for s, d in strip], *inner_z)
    if supports:
        outer_plan = Face(Wire(Polyline(*[Vector(x, y, 0) for x, y in
                                          ((a - w, -L - 0.3), (a, -L - 0.3), (a, tip_s), (a - w, tip_s))], close=True)))
        inner_plan = Face(Wire(Polyline(*[Vector(a - d, s, 0) for s, d in strip], close=True)))
        for plan, zr in ((outer_plan, outer_z), (inner_plan, inner_z)):
            sup = _support(plan, zr, flip)
            if sup is not None:
                inner_leaf += sup

    # bump at the free end, tapered at 45 degrees in plan toward the root
    zc = P.plug_height / 2
    b0 = tip_s - P.lock_length
    bump = extrude(profiles.to_face(profiles.bump(zc, retention_angle), a).moved(Pos(0, b0, 0)), amount=P.lock_length, dir=(0, 1, 0))
    o = profiles.OVERLAP
    H = P.bump_height
    taper = _plan_prism([(a - o, b0 - o), (a + H + o, b0 + H + o), (a + H + o, tip_s + o), (a - o, tip_s + o)], 0, P.plug_height)
    bump = bump & taper

    return pocket, outer_leaf + inner_leaf, bump


def union_plug():
    """Union plug: two hex plugs joined by a bridge over the lowered seam half-walls.

    Centered on the seam wall with the bridge along X, at its assembled height
    (upper floor). Rigid tabs snap into the upper groove; the open C-shaped rings
    of the grid are what flexes.
    """
    W = P.hex_move_width
    a, r = P.plug_apothem, P.plug_corner_radius
    h = P.plug_flat_half - P.union_bridge_gap
    hexes = [Face(rounded_hex_path(a, r)).moved(Pos(sx * W / 2, 0, 0)) for sx in (-1, 1)]
    xb = W / 2 - a + 0.5
    bridge = Face(Wire(Polyline((-xb, -h, 0), (xb, -h, 0), (xb, h, 0), (-xb, h, 0), close=True)))
    outline = hexes[0].fuse(hexes[1], bridge).clean()
    z0, z1 = P.union_z
    body = extrude(outline.moved(Pos(0, 0, z0)), amount=z1 - z0)
    top = body.edges().filter_by_position(Axis.Z, z1 - 1e-3, z1 + 1e-3)
    body = chamfer(top, length=P.union_top_chamfer)

    # tabs on faces 1..5 of the left hex (face 0 is the bridge), mirrored onto the right hex
    s0 = P.plug_flat_half - P.outer_leaf_end_gap - P.lock_length
    tab = extrude(profiles.to_face(profiles.lock_tab(P.upper_groove_z), a).moved(Pos(0, s0, 0)),
                  amount=P.lock_length, dir=(0, 1, 0))
    left = [Pos(-W / 2, 0, 0) * Rot(0, 0, 60 * k) * tab for k in range(1, 6)]
    return body + left + [mirror(t, Plane.YZ) for t in left]


def mount_plug(faces=(0, 1, 2, 3, 4, 5), retention_angle=None, label=None, supports=False):
    """Mount plug, base (mount side) at z = 0. Options for test variants: retention_angle
    and supports (see face_features), label engraved on the face that is up when
    printing: the top normally, the base when retention_angle asks for printing it
    upside down (see print_upside_down). The defaults give gridv8's plug exactly."""
    body = envelope()
    pocket, leaves, bump = face_features(retention_angle, supports)
    rot = [Rot(0, 0, 60 * k) for k in faces]
    body = body - [r * pocket for r in rot]
    body = body + ((reduce(lambda x, y: x + y, [r * leaves for r in rot])) & envelope())
    body = body + [r * bump for r in rot]

    return _finish(body, label)

def _finish(body, label=None, top=None, top_label=True):
    """Screw hole, counterbore and their chamfers; then the label, engraved on the base
    (mirrored, to read right from below) and on the top unless top_label is False, so it
    still shows when a test plug is cut down. top: height of the top face (default
    plug_height)."""
    top = top or P.plug_height
    hole = Cylinder(P.plug_hole_d / 2, P.plug_height + 2, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Pos(0, 0, -1))
    cbore_z = P.plug_height - P.plug_cbore_depth
    cbore = Cylinder(P.plug_cbore_d / 2, P.plug_cbore_depth + 1, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Pos(0, 0, cbore_z))
    c, r0, rh = P.plug_cbore_chamfer, P.plug_cbore_d / 2, P.plug_hole_d / 2
    lead = Cone(r0, r0 + c + 0.1, c + 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Pos(0, 0, top - c))
    entry = Cone(rh + c + 0.1, rh, c + 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Pos(0, 0, -0.1))
    body = body - hole - cbore - lead - entry
    if label:
        # over a corner pillar (30 degrees), clear of the hole and of the pockets
        text = Text(label, font_size=P.plug_label_size, font_style=FontStyle.BOLD, align=(Align.CENTER, Align.CENTER))
        d = P.plug_label_depth
        r, a = P.plug_label_radius, radians(30)
        cuts = [extrude(mirror(text, Plane.XZ).moved(Pos(0, 0, -1)), amount=d + 1)]
        if top_label:
            cuts.append(extrude(text.moved(Pos(0, 0, top - d)), amount=d + 1))
        body -= [Pos(r * cos(a), r * sin(a), 0) * cut for cut in cuts]
    return body


def _full_face_layout(spring_gaps=None):
    """Radial layout of one full-face lock in the +X face frame (x outward, s along
    the face). Each pocket stays inside its own 60 degree slice with a wall to the
    next one, so the deeper the zig-zag goes, the shorter its segments get.
    spring_gaps: bar to 1st segment, ..., last segment to pocket floor (one more than
    the segments). Returns the pocket outline, the bar and the segments as
    (x_in, x_out, s_lim), and the pocket floor."""
    a, h = P.plug_apothem, P.plug_flat_half
    w, e = P.lock_wall_width, P.full_face_end_gap
    gaps = spring_gaps or [P.spring_gap] * (P.spring_segments + 1)
    wall = P.full_face_pocket_wall / 2
    half = lambda x: min(h, x * tan(radians(30)) - wall)           # pocket half width at x
    bar = (a - P.full_face_bar, a, h - e)
    segs, inner = [], bar[0]
    for g in gaps[:-1]:
        x_out = inner - g
        x_in = x_out - w
        segs.append((x_in, x_out, half(x_in) - e))
        inner = x_in
    x_floor = inner - gaps[-1]
    pocket = [(a + 1, -h), (a + 1, h), ((h + wall) / tan(radians(30)), h), (x_floor, half(x_floor)),
              (x_floor, -half(x_floor)), ((h + wall) / tan(radians(30)), -h)]
    return pocket, bar, segs, x_floor


def full_face_plug(label=None, retention_angle=None, supports=True, element_z=None, window_z=None, spring_gaps=None,
                   flank_angle=None, nose_round=None, open_top=False, bar_mid_z=None, bar_pad=None):
    """Mount plug whose locks are bars along nearly the whole face (variants E to I).

    Each bar sits in a pocket and is pushed out by a zig-zag spring behind it: the
    segments run along the face, 0.6 thick, joined at alternating ends, so each one
    bends like a short beam held at both ends. Pushed in, the bar moves straight in
    (the cell wall keeps it parallel) by closing the gaps of the zig-zag. The bump
    runs along the whole bar, set back by full_face_bump_inset (less travel needed).
    element_z: height of bar and spring (default: gridv8's outer leaf); window_z: pocket
    height (default: gridv8's); spring_gaps: see _full_face_layout; flank_angle and
    nose_round: see profiles.bump. open_top: test plug cut off at the pocket ceiling, to
    watch the springs work (base down only; the label stays on the base only).
    bar_mid_z, bar_pad: the zig-zag gives the bar almost no vertical support (its short
    joints twist), so the bar rests on the top or the base of the pocket while it holds.
    With these, only bar_pad mm at each end of the bar keep the full height and bear
    there, next to the corner pillars where the top and base are stiff; the middle of
    the bar is cut down to bar_mid_z, clear of the thin free edge of the top and base,
    and prints as a bridge between the two ends.
    """
    a, h = P.plug_apothem, P.plug_flat_half
    w = P.lock_wall_width
    flip = retention_angle is not None
    window = _leaf_z(window_z or P.window_z, flip)
    lz = _leaf_z(element_z or P.outer_leaf_z, flip)
    pocket_pts, (bx_in, bx_out, bs), segs, x_floor = _full_face_layout(spring_gaps)

    assert not (open_top and flip), "open_top is for plugs printed base down"
    top = window[1] if open_top else P.plug_height
    pocket = _plan_prism(pocket_pts, window[0], window[1] + (1 if open_top else 0))
    if bar_mid_z:
        mid = _leaf_z(bar_mid_z, flip)
        spring = [_box(bx_in, bx_out, -bs, -bs + bar_pad, *lz), _box(bx_in, bx_out, bs - bar_pad, bs, *lz)]
        bridged = [_box(bx_in, bx_out, -bs + bar_pad - 0.01, bs - bar_pad + 0.01, *mid)]   # no support under it
    else:
        mid = lz
        spring, bridged = [_box(bx_in, bx_out, -bs, bs, *lz)], []          # the bar
    prev_in = bx_in
    for i, (x_in, x_out, s) in enumerate(segs):
        end = (-s, -s + w) if i % 2 == 0 else (s - w, s)              # joints alternate ends
        spring.append(_box(x_out - 0.01, prev_in + 0.01, *end, *lz))   # joint to the element above
        spring.append(_box(x_in, x_out, -s, s, *lz))                   # segment
        prev_in = x_in
    s = segs[-1][2]
    end = (-s, -s + w) if len(segs) % 2 == 0 else (s - w, s)
    spring.append(_box(x_floor - 0.3, prev_in + 0.01, *end, *lz))       # last joint, into the core

    x0 = a - P.full_face_bump_inset
    profile = profiles.bump(P.plug_height / 2, retention_angle, flank_angle, nose_round)
    bump = extrude(profiles.to_face(profile, x0).moved(Pos(0, -bs, 0)), amount=2 * bs, dir=(0, 1, 0))
    o, H = profiles.OVERLAP, P.bump_height
    trim = _plan_prism([(x0 - o, -bs - o), (x0 + H + o, -bs + H + o), (x0 + H + o, bs - H - o), (x0 - o, bs + o)],
                       0, P.plug_height)
    bump = (bump & trim & _box(x0 - 1, a + H + 1, -h, h, *mid)) - _box(x0 - 1, bx_in, -h, h, 0, P.plug_height)  # within the bar
    if supports:
        for part in list(spring):
            bb = part.bounding_box()
            plan = Face(Wire(Polyline(*[Vector(x, y, 0) for x, y in ((bb.min.X, bb.min.Y), (bb.max.X, bb.min.Y),
                                                                       (bb.max.X, bb.max.Y), (bb.min.X, bb.max.Y))], close=True)))
            sup = _support(plan, lz, flip, window)
            if sup is not None:
                spring.append(sup)

    rot = [Rot(0, 0, 60 * k) for k in range(6)]
    body = envelope(top) - [r * pocket for r in rot]
    body += [r * part for r in rot for part in spring + bridged + [bump]]
    return _finish(body, label, top=top, top_label=not open_top)

def final_mount_plug():
    """The mount plug chosen by the tests (params.mount_final), without a label."""
    opts = {k: v for k, v in P.mount_variants[P.mount_final].items() if k != "full_face"}
    return full_face_plug(**opts)


def print_upside_down(shape):
    """Flip a plug so its base faces up, with its new bottom at z = 0."""
    return Pos(0, 0, P.plug_height) * Rot(180, 0, 0) * shape


def double_plug():
    """Two mount plugs bridged at the bottom: snaps in from below across a seam wall
    (dovetail style, with seam_bottom_link) and holds the bottom of the seam together. Centered on the wall,
    bridge along X, bottom at z = 0 (the grid bottom)."""
    W = P.hex_move_width
    half = mount_plug(faces=(1, 2, 3, 4, 5)).moved(Pos(-W / 2, 0, 0))
    xb = W / 2 - P.plug_apothem + 0.5
    h = P.plug_flat_half - P.union_bridge_gap
    bridge = Box(2 * xb, 2 * h, P.bridge_height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return half + mirror(half, Plane.YZ) + bridge


def spline(thickness=None, label=None):
    """Flat spline joining two seam blocks; centered, bottom at z = 0, print it flat.
    The ends are chamfered so it slides into the slots as the quadrants come together.
    `label` is engraved near one end (to tell test splines apart)."""
    t = P.spline_thickness if thickness is None else thickness
    body = Box(2 * P.spline_half_length, P.spline_width, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = chamfer(body.edges().filter_by(Axis.Y), length=P.spline_lead_in)
    if label:
        text = Text(label, font_size=P.spline_label_size, font_style=FontStyle.BOLD, align=(Align.CENTER, Align.CENTER))
        cut = extrude(text.moved(Pos(P.spline_half_length / 2, 0, t - P.spline_label_depth)), amount=P.spline_label_depth + 1)
        body -= cut
    return body


def dovetail_key(angle=None, label=None):
    """Solid key pressed into the dovetail sockets of two seam cells from the panel side.

    Its side walls lean in at `angle` (key_angle), less than the socket's: snug at the
    socket mouth, wider below it, so it is trapped once in. Bottom at z = 0 (print it
    this way up, wide face on the bed); seated it sits 0.1 below z_top.
    `label` is engraved on the top of both tails (to tell test keys apart).
    """
    key = _dovetail_key_body(P.key_angle if angle is None else angle)
    if label:
        h = P.z_top - P.dovetail_floor_z - 0.1
        text = Text(label, font_size=P.key_label_size, font_style=FontStyle.BOLD, align=(Align.CENTER, Align.CENTER))
        cut = extrude(text.moved(Pos(0, 0, h - P.key_label_depth)), amount=P.key_label_depth + 1)
        x = P.dovetail_length * 0.65
        key -= [Pos(x, 0, 0) * cut, Pos(-x, 0, 0) * Rot(0, 0, 180) * cut]
    return key


def _dovetail_key_body(angle):
    from grid import dovetail_outline, socket_side_inset
    h = P.z_top - P.dovetail_floor_z - 0.1
    top = socket_side_inset(P.dovetail_floor_z + h) + P.key_top_fit   # matches the socket there
    inset = lambda z: top - (h - z) * tan(radians(angle))              # wider going down
    end, lead = P.key_end_clearance, P.key_lead_in
    sections = [dovetail_outline(inset(0) + lead, end + lead),         # lead-in chamfer
                dovetail_outline(inset(lead), end).moved(Pos(0, 0, lead)),
                dovetail_outline(inset(h), end).moved(Pos(0, 0, h))]
    return loft(sections, ruled=True)

