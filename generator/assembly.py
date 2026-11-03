"""The assembled grid: the loose part that joins the quadrants and where each one goes.
Used by build.py and by the web configurator."""

from build123d import Pos, Rot

import grid
import layout as L
import params as P
import plug


def joiner():
    """The loose part that joins the quadrants, for the current seam style."""
    if P.seam_style == "spline":
        return "spline", plug.spline()
    if P.seam_style == "dovetail":
        return "dovetail_key", plug.dovetail_key()
    return "union_plug", plug.union_plug()


def joiner_locations():
    """Where each joiner goes in the assembled grid (applied to the part as built)."""
    if P.seam_style == "v8":
        return [Pos(c) * Rot(0, 0, angle) for c, angle in L.union_plugs()]
    out, seen = [], set()
    for cell, walls in grid.union_walls().items():
        for k in walls:
            key = frozenset((cell, L.neighbor(*cell, k)))
            if key in seen:
                continue
            seen.add(key)
            if P.seam_style == "spline":
                out.append(grid.spline_location(cell, k) * Pos(0, 0, -P.spline_thickness / 2))
            else:
                m = (L.center(*cell) + L.center(*L.neighbor(*cell, k))) * 0.5
                out.append(Pos(m.X, m.Y, P.dovetail_floor_z) * Rot(0, 0, 60 * k))
    return out
