"""2D cross-section profiles, in (u, z) coordinates.

u is measured perpendicular to a face: for wall profiles it goes from the cell
face into the wall, for the bump it goes from the plug face outward. Each
profile is a list of segments ("line", p0, p1) or ("arc", center, p0, p1);
arcs always take the shorter way around their center.
"""

from math import atan2, cos, sin, pi, hypot, radians, sqrt, tan

from build123d import Face, Line, ThreePointArc, Vector, Wire

import params as P

OVERLAP = 0.3  # how far cutters reach past the face they cut, for clean booleans


def _arc_mid(c, p0, p1):
    a0 = atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = atan2(p1[1] - c[1], p1[0] - c[0])
    d = (a1 - a0 + pi) % (2 * pi) - pi
    r = hypot(p0[0] - c[0], p0[1] - c[1])
    return (c[0] + r * cos(a0 + d / 2), c[1] + r * sin(a0 + d / 2))


def _closed(points_and_arcs):
    """Turn a chain of points/arcs into segments, closing back to the start.

    Items are (u, z) points, or ("arc", center, end) to arc from the previous point.
    """
    segs, prev = [], points_and_arcs[0]
    for item in points_and_arcs[1:] + [points_and_arcs[0]]:
        if isinstance(item[0], str):
            _, c, end = item
            segs.append(("arc", c, prev, end))
            prev = end
        else:
            if item != prev:
                segs.append(("line", prev, item))
            prev = item
    return segs


def groove_cut(z0):
    """Material removed from the wall by one snap groove centered at height z0."""
    f, r, g = P.groove_flat / 2, P.groove_round, P.hex_internal_groove
    h = f + r
    return _closed([
        (-OVERLAP, z0 - h), (0, z0 - h),
        ("arc", (r, z0 - h), (r, z0 - f)),
        (g, z0 - f), (g, z0 + f), (r, z0 + f),
        ("arc", (r, z0 + h), (0, z0 + h)),
        (-OVERLAP, z0 + h),
    ])


def chamfer_cut(z_edge, c, top):
    """45 degree chamfer of size c on the edge at height z_edge (top or bottom edge)."""
    s = 1 if top else -1
    return _closed([(-OVERLAP, z_edge - s * (c + OVERLAP)), (c + OVERLAP, z_edge + s * OVERLAP), (-OVERLAP, z_edge + s * OVERLAP)])


def bottom_chamfer_cut():
    return chamfer_cut(P.z_bottom, P.bottom_chamfer, top=False)


def lock_tab(zc):
    """Rigid tab on the union plug: straight base, then a 45 degree nose into the groove."""
    h, b, d = P.lock_height / 2, P.lock_base, P.lock_depth
    n = h - (d - b)
    return _closed([(-OVERLAP, zc - h), (b, zc - h), (d, zc - n), (d, zc + n), (b, zc + h), (-OVERLAP, zc + h)])


def top_round_cut(overlap_below_top=True):
    """Rounds one top edge of a cell ring; applied from both sides of the wall.

    From the wall-center side the cutter must not reach past u = 0 below the top,
    or it would bite into the neighbor cell's rounded edge.
    """
    r, zt = P.top_round, P.z_top
    z_overlap = zt - r if overlap_below_top else zt
    return _closed([
        (-OVERLAP, z_overlap), (0, z_overlap), (0, zt - r),
        ("arc", (r, zt - r), (r, zt)),
        (r, zt + OVERLAP), (-OVERLAP, zt + OVERLAP),
    ])


def bump(zc, retention_angle=None, flank_angle=None, nose_round=None):
    """Snap bump on the outer leaf: S-shaped flanks (convex, concave, convex) and a short nose flat.

    With `retention_angle` (degrees from horizontal) the lower flank, the one that
    holds a hanging load, is a straight steeper ramp instead: inserting stays the
    same, pulling out has to cam the leaf in over a flatter slope. The groove's
    rounded edge meets any flank angle tangentially, so the grid does not change.

    With `flank_angle` both flanks are straight at that angle from horizontal and meet
    in a round nose of radius `nose_round`, with no edge anywhere: the S has a much
    flatter stretch (~20 degrees) right where it rests on the groove edges, which
    prints as a stepped tooth anyway.
    """
    H, Hh, rc, rr = P.bump_height, P.bump_half_height, P.bump_concave_r, P.bump_round
    if flank_angle is not None:
        t, r = radians(flank_angle), nose_round or P.bump_nose_round
        tu, tz = H - r + r * sin(t), r * cos(t)            # where the flank meets the nose
        zb = tz + tu * tan(t)                               # flank height at the leaf face
        pts = [(-OVERLAP, zb), (0, zb), (tu, tz), ("arc", (H - r, 0), (H, 0)),
               ("arc", (H - r, 0), (tu, -tz)), (0, -zb), (-OVERLAP, -zb)]
        return [(kind, *[(u, z + zc) for (u, z) in pts_]) for kind, *pts_ in _closed(pts)]
    k = sqrt((rr + rc) ** 2 - rr ** 2)
    A, B, C = (H - k, Hh - rr), (H, Hh), (H - rr, Hh - k)  # shoulder, concave, nose centers

    def toward(a, b, dist):
        L = hypot(b[0] - a[0], b[1] - a[1])
        return (a[0] + dist * (b[0] - a[0]) / L, a[1] + dist * (b[1] - a[1]) / L)

    t1, t2 = toward(A, B, rr), toward(C, B, rr)
    shoulder, nose = (A[0], Hh), (H, C[1])
    m = lambda p: (p[0], -p[1])  # mirror about the bump center
    upper = [shoulder, ("arc", A, t1), ("arc", B, t2), ("arc", C, nose)]
    if retention_angle is None:
        lower, z_low = [m(nose), ("arc", m(C), m(t2)), ("arc", m(B), m(t1)), ("arc", m(A), m(shoulder))], -Hh
    else:
        z_low = -(C[1] + H * tan(radians(retention_angle)))
        lower = [m(nose), (0, z_low)]
    pts = [(-OVERLAP, Hh)] + upper + lower + [(-OVERLAP, z_low)]
    return [(kind, *[(u, z + zc) for (u, z) in pts_]) for kind, *pts_ in _closed(pts)]


def to_face(segments, x0, sign=1.0):
    """Place a (u, z) profile in the XZ plane (y = 0) at x = x0 + sign * u."""
    v = lambda p: Vector(x0 + sign * p[0], 0, p[1])
    edges = []
    for seg in segments:
        if seg[0] == "line":
            edges.append(Line(v(seg[1]), v(seg[2])))
        else:
            _, c, p0, p1 = seg
            edges.append(ThreePointArc(v(p0), v(_arc_mid(c, p0, p1)), v(p1)))
    return Face(Wire(edges))
