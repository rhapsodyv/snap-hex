"""Quick shaded PNG previews of build123d shapes with matplotlib (no viewer needed)."""

from math import cos, sin, radians

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def _triangles(shape, tol=0.02):
    if isinstance(shape, (list, tuple)):  # e.g. the pieces returned by split()
        return np.vstack([_triangles(s, tol) for s in shape])
    verts, tris = shape.tessellate(tol, angular_tolerance=0.2)
    v = np.array([tuple(p) for p in verts])
    return v[np.array(tris)]


def section_lines(shape, z):
    """Outline of a horizontal cut at height z, as a list of (n, 2) point arrays."""
    from build123d import GeomType, Plane, section

    out = []
    for e in section(shape, section_by=Plane(origin=(0, 0, z), x_dir=(1, 0, 0), z_dir=(0, 0, 1))).edges():
        n = 2 if e.geom_type == GeomType.LINE else int(np.clip(e.length / 0.3, 3, 200))
        out.append(np.array([tuple(e.position_at(u))[:2] for u in np.linspace(0, 1, n)]))
    return out


def layout_map(path, quadrants):
    """Top view: lower floor outline (thin) and upper floor (thick), one color per quadrant."""
    colors = {"BL": "#4a4a4a", "BR": "#3b6fc4", "FL": "#2a9a72", "FR": "#c8653a"}
    fig, ax = plt.subplots(figsize=(14, 14))
    for q, shape in quadrants.items():
        for z, lw in ((0.0, 0.35), (6.0, 1.6)):
            for p in section_lines(shape, z):
                ax.plot(p[:, 0], p[:, 1], "-", color=colors.get(q, "k"), lw=lw)
        ax.plot([], [], color=colors.get(q, "k"), label=q)
    ax.set_aspect("equal")
    ax.set_title("grid: corte em z=0 (fino) e andar de cima em z=6 (grosso)")
    ax.legend(loc="upper right")
    ax.grid(True, lw=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def png(path, items, elev, azim, title="", zoom=1.0, size=(10, 8)):
    """items: [(shape, color)]. All triangles go in one collection so depth sorting is global."""
    e, a = radians(elev), radians(azim)
    eye = np.array([cos(e) * cos(a), cos(e) * sin(a), sin(e)])
    light = eye + np.array([-0.3, 0.2, 0.6])
    light /= np.linalg.norm(light)

    polys, colors = [], []
    for shape, color in items:
        tri = _triangles(shape)
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        shade = 0.3 + 0.7 * np.abs(n @ light)
        polys.append(tri)
        colors.append(np.clip(np.array(to_rgb(color))[None, :] * shade[:, None], 0, 1))
    polys, colors = np.vstack(polys), np.vstack(colors)

    fig = plt.figure(figsize=size)
    ax = fig.add_subplot(projection="3d")
    ax.add_collection3d(Poly3DCollection(polys, facecolors=colors, edgecolors="none", linewidths=0))
    pts = polys.reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    mid, half = (lo + hi) / 2, (hi - lo).max() / 2 * zoom
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)
    ax.set_zlim(mid[2] - half, mid[2] + half)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_proj_type("ortho")
    ax.set_axis_off()
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
