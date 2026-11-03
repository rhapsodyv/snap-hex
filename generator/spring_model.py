"""Beam model of one mount plug lock, to compare variants: force the cell wall needs
to push the lock in until the bump clears it, and the highest bending strain in the
spring on the way. Then the pull-out: the groove's lower edge cams the bump in as the
plug comes down; at each step the pull is the spring force there times what the
flank angle at the contact (and friction) makes of it, and the contact force is
what presses on the bump.

In-plane beams (x outward from the face, s along it), with contacts where leaves or
spring segments touch each other as gaps close. E for printed ABS is a round guess,
so read the forces as relative; strains don't depend on it. A, the gridv8 plug, is
the reference for how much strain the leaves take in use.

    .venv/bin/python generator/spring_model.py
"""

from math import atan2, cos, hypot, pi, sin

import numpy as np

import params as P
import plug
import profiles

E = 2000.0      # MPa, printed ABS
MU = 0.35       # ABS on ABS friction, estimated
DS = 0.1        # node spacing along the beams


class Frame:
    def __init__(self):
        self.nodes, self.elems, self.contacts, self.fixed, self.pres = [], [], [], set(), {}

    def node(self, x, s):
        self.nodes.append((x, s))
        return len(self.nodes) - 1

    def beam(self, pts, t, h, group):
        ids = [self.node(x, s) for x, s in pts]
        for a, b in zip(ids, ids[1:]):
            self.elems.append((a, b, t, h, group))
        return ids

    def link(self, a, b, t, h, group):
        self.elems.append((a, b, t, h, group))

    def contact(self, a, b, gap):
        """Node a moving in (-x) closes `gap` toward node b (None: the pocket floor)."""
        self.contacts.append((a, b, gap))

    def _kel(self, n1, n2, t, h):
        (x1, s1), (x2, s2) = self.nodes[n1], self.nodes[n2]
        L = hypot(x2 - x1, s2 - s1)
        c, s = (x2 - x1) / L, (s2 - s1) / L
        A, I = h * t, h * t ** 3 / 12
        a, b, d, e = E * A / L, 12 * E * I / L ** 3, 6 * E * I / L ** 2, E * I / L
        k = np.array([[a, 0, 0, -a, 0, 0], [0, b, d, 0, -b, d], [0, d, 4 * e, 0, -d, 2 * e],
                      [-a, 0, 0, a, 0, 0], [0, -b, -d, 0, b, -d], [0, d, 2 * e, 0, -d, 4 * e]])
        T = np.zeros((6, 6))
        T[:3, :3] = T[3:, 3:] = [[c, s, 0], [-s, c, 0], [0, 0, 1]]
        return T.T @ k @ T, T, k

    def solve(self, kc=1e5):
        """Returns reactions and the highest strain per group; contacts by active set."""
        N = len(self.nodes)
        K0 = np.zeros((3 * N, 3 * N))
        for n1, n2, t, h, _ in self.elems:
            idx = [3 * n1, 3 * n1 + 1, 3 * n1 + 2, 3 * n2, 3 * n2 + 1, 3 * n2 + 2]
            K0[np.ix_(idx, idx)] += self._kel(n1, n2, t, h)[0]
        pres = dict(self.pres)
        for n in self.fixed:
            pres.update({3 * n: 0, 3 * n + 1: 0, 3 * n + 2: 0})
        pd = list(pres)
        free = [d for d in range(3 * N) if d not in pres]
        closing = lambda u, a, b, g: -u[3 * a] + (u[3 * b] if b is not None else 0) - g
        active = set()
        for _ in range(60):
            K, f = K0.copy(), np.zeros(3 * N)
            for j in active:      # penalty spring along x across the closed gap
                a, b, g = self.contacts[j]
                K[3 * a, 3 * a] += kc
                f[3 * a] -= kc * g
                if b is not None:
                    K[3 * b, 3 * b] += kc
                    K[3 * a, 3 * b] -= kc
                    K[3 * b, 3 * a] -= kc
                    f[3 * b] += kc * g
            u = np.zeros(3 * N)
            u[pd] = [pres[d] for d in pd]
            u[free] = np.linalg.solve(K[np.ix_(free, free)], f[free] - K[np.ix_(free, pd)] @ u[pd])
            new = {j for j, c in enumerate(self.contacts) if closing(u, *c) > (-1e-7 if j in active else 0)}
            if new == active:
                break
            active = new
        strain = {}
        for n1, n2, t, h, group in self.elems:
            _, T, k = self._kel(n1, n2, t, h)
            fe = k @ T @ np.concatenate([u[3 * n1:3 * n1 + 3], u[3 * n2:3 * n2 + 3]])
            eps = max(abs(fe[2]), abs(fe[5])) * (t / 2) / (E * h * t ** 3 / 12) + abs(fe[0]) / (E * h * t)
            strain[group] = max(strain.get(group, 0), eps)
        return K @ u - f, strain


def _height(zr):
    return zr[1] - zr[0]


def leaves(extra_travel=0.0):
    """gridv8's lock (variants A, C): outer leaf with the bump, backing leaf behind it."""
    a, L, w = P.plug_apothem, P.plug_flat_half, P.lock_wall_width
    tip_s = L - P.outer_leaf_end_gap
    F = Frame()
    outer = F.beam([(a - w / 2, s) for s in np.arange(-L, tip_s + 1e-9, DS)], w, _height(P.outer_leaf_z), "lâmina externa")
    F.fixed.add(outer[0])
    root, tip = (-L, P.inner_leaf_root_d), (P.inner_leaf_tip_s, P.inner_leaf_tip_d)
    ds, dd = tip[0] - root[0], tip[1] - root[1]
    n = hypot(ds, dd)
    ns, nd = -dd / n, ds / n                       # across the backing leaf, inward
    c0 = np.array([root[0] + w / 2 * ns, root[1] + w / 2 * nd])
    c1 = np.array([tip[0] + w / 2 * ns, tip[1] + w / 2 * nd])
    k = max(2, int(n / DS) + 1)
    inner = F.beam([(a - d, s) for s, d in np.linspace(c0, c1, k)], w, _height(P.inner_leaf_z), "lâmina interna")
    F.fixed.add(inner[0])
    for i in inner:
        x, s = F.nodes[i]
        j = min(outer, key=lambda m: abs(F.nodes[m][1] - s))
        F.contact(j, i, (a - x) - w / 2 * nd - w)  # outer leaf back face to backing leaf front face
    # the wall pushes the bump in where its nose flat starts (the most outward point once the leaf bends)
    push = min(outer, key=lambda m: abs(F.nodes[m][1] - (tip_s - P.lock_length + P.bump_height)))
    travel = P.bump_height - P.grid_gap + extra_travel
    F.pres[3 * push] = -travel
    R, strain = F.solve()
    return travel, -R[3 * push], strain


def full_face(element_z=None, spring_gaps=None, extra_travel=0.0, **_):
    """Bar plus zig-zag lock (variants E to I); the wall pushes the bar straight in."""
    w = P.lock_wall_width
    h = _height(element_z or P.outer_leaf_z)
    _, (bx_in, bx_out, bs), segs, x_floor = plug._full_face_layout(spring_gaps)
    gaps = list(spring_gaps or [P.spring_gap] * (P.spring_segments + 1))
    grid = lambda s0, s1: sorted({round(s0, 6), round(s1, 6), *np.round(np.arange(np.ceil(s0 / DS) * DS, s1, DS), 6)})
    F = Frame()
    rows = [dict(zip(grid(-bs, bs), F.beam([((bx_in + bx_out) / 2, s) for s in grid(-bs, bs)], bx_out - bx_in, h, "barra")))]
    for i, (x_in, x_out, sl) in enumerate(segs):
        rows.append(dict(zip(grid(-sl, sl), F.beam([((x_in + x_out) / 2, s) for s in grid(-sl, sl)], w, h, f"mola {i + 1}"))))
    near = lambda row, s: row[min(row, key=lambda k: abs(k - s))]
    joint_s = lambda i, sl: -sl + w / 2 if i % 2 == 0 else sl - w / 2        # joints alternate ends
    for i, (_, _, sl) in enumerate(segs):
        F.link(near(rows[i], joint_s(i, sl)), near(rows[i + 1], joint_s(i, sl)), w, h, f"junta {i + 1}")
    sl = segs[-1][2]
    core = F.node(x_floor, joint_s(len(segs), sl))
    F.fixed.add(core)
    F.link(near(rows[-1], joint_s(len(segs), sl)), core, w, h, f"junta {len(segs) + 1}")
    for i, (up, lo) in enumerate(zip(rows, rows[1:])):
        for s in set(up) & set(lo):
            F.contact(up[s], lo[s], gaps[i])
    for n in rows[-1].values():
        F.contact(n, None, gaps[-1])
    travel = P.bump_height - P.full_face_bump_inset - P.grid_gap + extra_travel
    for n in rows[0].values():
        F.pres.update({3 * n: -travel, 3 * n + 1: 0, 3 * n + 2: 0})
    R, strain = F.solve()
    return travel, -sum(R[3 * n] for n in rows[0].values()), strain


def lock(opts, extra_travel=0.0):
    return full_face(extra_travel=extra_travel, **opts) if opts.get("full_face") else leaves(extra_travel)


ZS = np.arange(-3.0, 3.0, 0.0005)


def _reach(segs):
    """How far a profile from profiles.py reaches (largest u) at each height in ZS."""
    pts = []
    for seg in segs:
        if seg[0] == "line":
            p0, p1 = np.array(seg[1]), np.array(seg[2])
            pts += [p0 + (p1 - p0) * t for t in np.linspace(0, 1, 2000)]
        else:
            _, c, p0, p1 = seg
            a0, a1 = atan2(p0[1] - c[1], p0[0] - c[0]), atan2(p1[1] - c[1], p1[0] - c[0])
            d, r = (a1 - a0 + pi) % (2 * pi) - pi, hypot(p0[0] - c[0], p0[1] - c[1])
            pts += [(c[0] + r * cos(a0 + d * t), c[1] + r * sin(a0 + d * t)) for t in np.linspace(0, 1, 2000)]
    pts = np.array(pts)
    pts = pts[pts[:, 0] > 0.01]
    out = np.full(len(ZS), -np.inf)
    np.maximum.at(out, np.clip(np.round((pts[:, 1] - ZS[0]) / (ZS[1] - ZS[0])).astype(int), 0, len(ZS) - 1), pts[:, 0])
    have = np.isfinite(out)
    inside = (ZS >= ZS[have].min()) & (ZS <= ZS[have].max())
    return np.where(inside, np.interp(ZS, ZS[have], out[have]), 0.0)


def pull_out(opts):
    """Seated retraction, and the highest pull and contact force on the way out (N, one lock)."""
    full = opts.get("full_face")
    segs = profiles.bump(0.0, opts.get("retention_angle"), opts.get("flank_angle"), opts.get("nose_round"))
    bump, groove = _reach(segs), _reach(profiles.groove_cut(0.0))
    offset = P.grid_gap + (P.full_face_bump_inset if full else 0)       # bump origin to the wall face
    step = ZS[1] - ZS[0]
    dzs = np.arange(0, 2.6, 0.005)
    c = []
    for dz in dzs:                                                     # plug down by dz
        shift = int(round(dz / step))
        b = np.concatenate([bump[shift:], np.zeros(shift)])
        c.append(max((b - offset - groove).max(), 0.0))
    c = np.array(c)
    th = np.arctan2(1, np.gradient(c, dzs))                            # flank angle at the contact, from horizontal
    on = (c > 1e-3) & (c < c.max() - 1e-3)
    travel = lock(opts)[0]
    cs = np.linspace(0, travel, 12)
    springs = [0.0] + [lock(opts, x - travel)[1] for x in cs[1:]]
    spring = np.interp(c[on], cs, springs)
    den = np.sin(th[on]) - MU * np.cos(th[on])
    den = np.where(den > 1e-3, den, 1e-3)                              # self-locking: capped
    pull = spring * (np.cos(th[on]) + MU * np.sin(th[on])) / den
    contact = spring / den
    k = int(np.argmax(pull))
    return c[0], pull[k], np.degrees(th[on][k]), contact.max()


def main():
    print("força para recolher a trava (N, por trava) e maior deformação da mola")
    print("+0,1: a mesma coisa com 0,1 mm a mais de curso (peça impressa mais gorda)\n")
    ref = None
    for name, opts in P.mount_variants.items():
        travel, force, strain = lock(opts)
        _, force2, strain2 = lock(opts, 0.1)
        ref = ref or force
        worst = max(strain, key=strain.get)
        print(f"  {name}: curso {travel:.2f}, {force:4.1f} N ({force / ref:.1f}x A), deformação {strain[worst] * 100:.1f}% ({worst})"
              f" | +0,1: {force2:4.1f} N, {max(strain2.values()) * 100:.1f}%")
    print(f"\npara arrancar, por trava (atrito {MU}); recuo encaixado = quanto a mola já está apertada")
    for name, opts in P.mount_variants.items():
        if opts.get("flank_angle") is None and opts.get("retention_angle") is None:
            # the drawn S has a ~20 degree stretch where it rests on the groove edges that
            # would almost self-lock; printed it comes out as a stepped tooth, and the
            # tests (C holds harder than A) say that stretch is not there
            print(f"  {name}: ressalto em S, fora do modelo (impresso não sai como desenhado)")
            continue
        seated, pull, angle, contact = pull_out(opts)
        print(f"  {name}: recuo encaixado {seated:.2f}, puxão máx {pull:4.1f} N (flanco a {angle:.0f}° no contato), contato máx {contact:4.1f} N")


if __name__ == "__main__":
    main()
