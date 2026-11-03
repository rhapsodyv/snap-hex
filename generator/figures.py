"""Figures for the README, in docs/: the mount plug cut open, its locks in color.
Needs matplotlib:  .venv/bin/python generator/figures.py"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from build123d import Plane, Rot, section
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath

import params as P
import plug
import render

DOCS = Path(__file__).parent.parent / "docs"
BODY, LOCK = "#cfc8b8", "#e8846b"
EDGE = "#4a4740"


def final_options():
    return {k: v for k, v in P.mount_variants[P.mount_final].items() if k != "full_face"}


def split(shape, opts, open_top=False):
    """The plug's body, and its six locks (bar, zig-zag spring, bump): what lies in the pockets."""
    z0, z1 = opts.get("window_z", P.window_z)
    pocket = plug._full_face_layout(opts.get("spring_gaps"))[0]
    region = [Rot(0, 0, 60 * k) * plug._plan_prism(pocket, z0 - 0.01, z1 + (1 if open_top else 0.01)) for k in range(6)]
    region = region[0].fuse(*region[1:])
    return shape - region, shape & region


def fill(ax, shape, plane, axes, color):
    """A cut of shape, filled, with its holes."""
    for f in section(shape, section_by=plane).faces():
        verts, codes = [], []
        for wire in [f.outer_wire()] + list(f.inner_wires()):
            pts = [tuple(wire.position_at(t))[axes] for t in np.linspace(0, 1, 1200)]
            verts += pts + [pts[0]]
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 1) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor=EDGE, lw=0.5))


def note(ax, text, xy, xytext, **kw):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=9, color="#222",
                arrowprops=dict(arrowstyle="-", color="#555", lw=0.7, shrinkA=0, shrinkB=2), **kw)


def cutaway():
    opts = final_options()
    body, lock = split(plug.full_face_plug(open_top=True, **opts), opts, open_top=True)
    render.png(DOCS / "mount-plug-cutaway.png", [(body, BODY), (lock, LOCK)], elev=52, azim=-62, zoom=0.6,
               size=(7, 6), dpi=150, transparent=True)


def sections():
    opts = final_options()
    body, lock = split(plug.full_face_plug(**opts), opts)
    a = P.plug_apothem
    _, (bx_in, bx_out, bs), segs, x_floor = plug._full_face_layout(opts.get("spring_gaps"))
    zc = P.plug_height / 2
    fig = plt.figure(figsize=(13, 6.6))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.5, 1], hspace=0.6, wspace=0.05)
    below = dict(ha="center", va="top", fontsize=9.5, color="#333")

    ax = fig.add_subplot(grid[:, 0])                         # plan, cut half way up, notes on the right
    plane = Plane(origin=(0, 0, zc), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    fill(ax, body, plane, slice(0, 2), BODY)
    fill(ax, lock, plane, slice(0, 2), LOCK)
    ax.set_xlim(-11, 21); ax.set_ylim(-11, 11)
    s1 = segs[0]
    note(ax, "zig-zag spring:\nthree 0.6 mm walls", ((s1[0] + s1[1]) / 2, 2.6), (13, 6.5))
    note(ax, "bump: round nose,\nno hook", (a + 0.7, 0.4), (13, 1.2))
    note(ax, "lock bar, 1 mm", ((bx_in + bx_out) / 2, -1.6), (13, -4.0))
    ax.set_title("Cut half way up: one lock on each of the six faces", fontsize=11)

    ax = fig.add_subplot(grid[0, 1])                         # radial cut through the +X face
    plane = Plane(origin=(0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    fill(ax, body, plane, slice(0, 3, 2), BODY)
    fill(ax, lock, plane, slice(0, 3, 2), LOCK)
    ax.set_xlim(x_floor - 0.6, a + 1.6); ax.set_ylim(-0.3, P.plug_height + 0.3)
    ax.set_title("Cut through one face", fontsize=11)
    ax.text(0.5, -0.06, "the bar pushed in closes the zig-zag; every wall starts\none layer (0.2 mm) "
            "above the pocket floor, so nothing prints in the air", transform=ax.transAxes, **below)

    ax = fig.add_subplot(grid[1, 1])                         # along the bar, seen from outside
    plane = Plane(origin=((bx_in + bx_out) / 2, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    fill(ax, body, plane, slice(1, 3), BODY)
    fill(ax, lock, plane, slice(1, 3), LOCK)
    ax.set_xlim(-6, 6); ax.set_ylim(-0.3, P.plug_height + 0.3)
    ax.set_title("Cut along the lock bar", fontsize=11)
    ax.text(0.5, -0.06, "the bar bears only on its ends, next to the stiff corners,\nclear of the thin top and base "
            "in the middle", transform=ax.transAxes, **below)

    for ax in fig.axes:
        ax.set_aspect("equal")
        ax.set_axis_off()
    fig.savefig(DOCS / "mount-plug-sections.png", dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    cutaway()
    sections()
    print("docs/mount-plug-cutaway.png, docs/mount-plug-sections.png")
