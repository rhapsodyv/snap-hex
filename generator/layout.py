"""Grid layout: cells, quadrants, seams, union plugs, perimeter outline and pads.

Cells sit on a hex lattice with flats facing +-X; cell (0, 0) is at the origin.
Walls are numbered k = 0..5 by the direction of their normal, 60*k degrees.
"""

from functools import lru_cache
from math import cos, sin, radians

from build123d import Vector

import params as P

W, RP = P.hex_move_width, P.row_pitch
QUADRANTS = ("BL", "BR", "FL", "FR")

X_OUT = P.frame_width_x / 2
Y0 = P.frame_center_y - P.frame_depth_y / 2   # front outer edge
Y1 = P.frame_center_y + P.frame_depth_y / 2   # back outer edge


def center(i, j):
    return Vector(i * W + (j % 2) * W / 2, j * RP, 0)


def neighbor(i, j, k):
    c = center(i, j) + Vector(cos(radians(60 * k)), sin(radians(60 * k)), 0) * W
    jj = round(c.Y / RP)
    return round((c.X - (jj % 2) * W / 2) / W), jj


def quadrant(i, j):
    """Back/front split between rows 0 and 1, left/right at x = 0 (x = 0 goes right)."""
    return ("B" if j >= 1 else "F") + ("L" if center(i, j).X < 0 else "R")


def is_seam(i, j, k):
    return quadrant(*neighbor(i, j, k)) != quadrant(i, j)


def outline(inset=0.0):
    """Outer edge of the grid (inset 0) or inner edge of the band (inset = band width)."""
    a = X_OUT - inset
    b = X_OUT - P.corner_cut_width - inset
    yb0, yb1 = Y0 + inset, Y1 - inset
    ys0, ys1 = Y0 + P.corner_cut_depth + inset, Y1 - P.corner_cut_depth - inset
    return [(-b, yb0), (b, yb0), (b, ys0), (a, ys0), (a, ys1), (b, ys1),
            (b, yb1), (-b, yb1), (-b, ys1), (-a, ys1), (-a, ys0), (-b, ys0)]


def notches():
    """Center cut-outs at the back and front edges, as (x0, x1, y0, y1)."""
    w, d = P.center_notch_half_width, P.center_notch_depth
    return [(-w, w, Y1 - d, Y1 + 10), (-w, w, Y0 - 10, Y0 + d)]


def inside(pt, poly):
    x, y = pt
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def hex_corners(i, j):
    c, R = center(i, j), (W / 2) / cos(radians(30))
    return [(c.X + R * cos(radians(30 + 60 * k)), c.Y + R * sin(radians(30 + 60 * k))) for k in range(6)]


def in_hex(pt, i, j):
    c = center(i, j)
    return all(abs((pt[0] - c.X) * cos(radians(60 * k)) + (pt[1] - c.Y) * sin(radians(60 * k))) <= W / 2 for k in range(3))


@lru_cache
def cells():
    """Every lattice cell that reaches inside the band (including ones that only
    cover a concave corner of it)."""
    inner = outline(P.lateral_wall_width)
    out = []
    for j in range(-14, 15):
        for i in range(-13, 13):
            if any(inside(p, inner) for p in hex_corners(i, j) + [tuple(center(i, j))[:2]]) \
                    or any(in_hex(p, i, j) for p in inner):
                out.append((i, j))
    return tuple(out)


def is_edge_cell(i, j):
    inner = outline(P.lateral_wall_width)
    return not all(inside(p, inner) for p in hex_corners(i, j))


@lru_cache
def open_walls():
    """Cell -> walls left open in the upper floor so a union plug can bridge the seam."""
    out = {}
    for j in P.union_rows:                 # vertical seam
        out.setdefault((-1, j), set()).add(0)
        out.setdefault((0, j), set()).add(3)
    for i in P.union_cols:                 # back/front seam
        out.setdefault((i, 1), set()).add(4)
        out.setdefault((i, 0), set()).add(1)
    return out


def upper_cells():
    """Cells with the upper floor ring (along the seams). Standoffs are separate."""
    return set(open_walls())


def union_plugs():
    """(center, rotation in degrees) of every union plug."""
    out = []
    for j in P.union_rows:
        out.append(((center(-1, j) + center(0, j)) * 0.5, 0))
    for i in P.union_cols:
        out.append(((center(i, 0) + center(i, 1)) * 0.5, 60))
    return out


def pads():
    """(side, position along the side) of every screw pad; side in L, R, B, F."""
    cols = [s * n * W for n in P.pad_cols for s in (-1, 1)]
    rows = [n * RP for n in P.pad_rows]
    return [("L", y) for y in rows] + [("R", y) for y in rows] + [("B", x) for x in cols] + [("F", x) for x in cols]


def pad_quadrant(side, pos):
    if side in "LR":
        return ("B" if pos > P.frame_center_y else "F") + side
    return side + ("L" if pos < 0 else "R")


def standoff_quadrant(cell):
    return quadrant(*cell)
