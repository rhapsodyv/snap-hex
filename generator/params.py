"""Grid and plug dimensions (mm).

Names mirror the user parameters in the Fusion design "gridv8" where one exists;
the rest were measured from cross-sections of that design.
"""

from math import sqrt, tan, radians

# --- cell / grid (Fusion user parameters) ---------------------------------
hex_radius = 11.0            # sharp-vertex radius of the cell opening
hex_corner_radius = 3.0      # rounding of the cell opening corners
hex_edge_width = 2.9         # wall thickness between two cells
hex_internal_groove = 0.8    # depth of the snap groove in the wall
grid_thickness = 5.8         # height of the lower floor (mount plugs)
grid_gap = 0.15              # plug-to-wall clearance per side
lock_wall_width = 0.6        # snap leaf thickness (one 0.4-nozzle pass)
lock_length = 2.0            # bump length along the leaf
frame_size = 20.0
deck_panel_thickness = 3.0

hex_r = sqrt(3) / 2 * hex_radius                       # cell apothem, 9.526
hex_move_width = hex_edge_width + sqrt(3) * hex_radius  # pitch along X, 21.953
row_pitch = hex_move_width * sqrt(3) / 2                # pitch between rows along Y, 19.012

# --- wall profile (measured) ----------------------------------------------
z_bottom = -grid_thickness / 2                       # -2.9
z_floor_split = grid_thickness / 2                   # 2.9: lower floor | upper floor
z_top = frame_size / 2 - deck_panel_thickness        # 7.0, touches the deck panel
lower_groove_z = (z_bottom + z_floor_split) / 2      # 0.0, mount plugs lock here
upper_groove_z = (z_floor_split + z_top) / 2         # 4.95, union plugs lock here

groove_flat = 0.8            # height of the flat groove bottom
groove_round = 0.7           # rounding where the wall face turns into the groove
bottom_chamfer = 0.8         # lead-in on the cell side of the bottom edge
top_round = 0.8              # both top edges of each cell ring

# --- export ---------------------------------------------------------------
stl_tolerance = 0.02         # mm, chord error of the STL mesh
stl_angular_tolerance = 0.3  # rad: ~0.03 mm on the 3 mm cell corners, half the triangles of 0.2

# --- mount plug (measured) ------------------------------------------------
plug_apothem = hex_r - grid_gap                      # 9.376
plug_corner_radius = hex_corner_radius - grid_gap    # 2.85
plug_height = grid_thickness
plug_chamfer = 0.4
plug_flat_half = (plug_apothem - plug_corner_radius) * tan(radians(30))  # straight half-length of a face, 3.768

plug_hole_d = 3.0
plug_cbore_d = 5.7
plug_cbore_depth = 3.0
plug_cbore_chamfer = 0.4

window_depth = 2.6           # pocket behind the leaves, from the face inward
window_z = (1.0, 4.8)        # pocket height
outer_leaf_z = (1.4, 4.3)
outer_leaf_end_gap = 0.4     # free end to pocket end

bump_height = hex_internal_groove + 0.4   # 1.2: protrusion past the plug face
bump_half_height = 1.2       # half height of the bump base, centered on the leaf
bump_concave_r = 0.8         # middle (concave) arc of the S-shaped flank
bump_round = 0.4             # shoulder and nose rounding
bump_nose_round = 0.5        # nose of the straight-flank bump (flank_angle)

inner_leaf_z = (1.2, 4.5)
inner_leaf_root_d = 1.794    # outer edge of the backing leaf at its root, from the face
inner_leaf_tip_d = 0.8       # ... at its tip: 0.2 mm behind the outer leaf
inner_leaf_tip_s = 2.879     # tip position along the face (root is at the pocket end)
print_layer = 0.2            # supports under floating spring parts stop one layer short of them
plug_label_size = 6.0        # engraved letter on test plugs
plug_label_depth = 0.4
plug_label_radius = 6.4

# mount plug test variants, letter engraved on each (forces and strains: spring_model.py)
# tested: J, K, L all good and hard to tell apart, no whitening either; I is very good (firm in, firm hold, firm out, no stress whitening on the bumps after
# many cycles); E and F hold better than A; the flatter 30 degree load flank (C, F) holds harder
# but wears the locks when pulled out, so it is dropped
mount_variants = {
    "A": {},                                              # exactly as gridv8
    "C": {"retention_angle": 30.0, "supports": True},     # A + flatter load flank (~2x the hold), printed upside down
    "E": {"full_face": True},                             # lock bar along the whole face on a zig-zag spring
    "F": {"full_face": True, "retention_angle": 30.0},    # E + C's flatter load flank, printed upside down
    # E, stronger at the same travel without straining the spring more:
    "G": {"full_face": True, "element_z": (1.2, 4.5)},    # bar and spring as tall as gridv8's backing leaf
    "H": {"full_face": True, "element_z": (1.2, 4.5),     # G + gaps that let the 2nd segment work as hard
          "spring_gaps": (0.6, 0.5, 0.4, 0.5)},           # as the others
    "I": {"full_face": True, "window_z": (0.8, 5.0),      # H + taller pocket (0.8 skins instead of 1.0)
          "element_z": (1.0, 4.7), "spring_gaps": (0.6, 0.5, 0.4, 0.5)},
    # H with a symmetric bump of straight flanks and a round nose, no edges (see profiles.bump)
    "J": {"full_face": True, "element_z": (1.2, 4.5), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 40.0, "nose_round": 0.5},
    "K": {"full_face": True, "element_z": (1.2, 4.5), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.5},
    "L": {"full_face": True, "element_z": (1.2, 4.5), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.8},
    # I (the best so far) with the tips of J, K, L
    "M": {"full_face": True, "window_z": (0.8, 5.0), "element_z": (1.0, 4.7), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 40.0, "nose_round": 0.5},
    "N": {"full_face": True, "window_z": (0.8, 5.0), "element_z": (1.0, 4.7), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.5},
    "O": {"full_face": True, "window_z": (0.8, 5.0), "element_z": (1.0, 4.7), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.8},
    # O deforms its top and base: the bar rests on them while it holds (see plug.full_face_plug)
    "P": {"full_face": True, "window_z": (0.8, 5.0), "element_z": (1.0, 4.7), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.8,
          "bar_mid_z": (1.4, 4.3), "bar_pad": 1.0},       # O bearing only at the bar ends, next to the pillars
    "Q": {"full_face": True, "window_z": (1.0, 4.8), "element_z": (1.2, 4.5), "spring_gaps": (0.6, 0.5, 0.4, 0.5),
          "flank_angle": 45.0, "nose_round": 0.8,
          "bar_mid_z": (1.5, 4.25), "bar_pad": 1.0},      # P with 1.0 top and base (spring as tall as H's)
}
mount_final = "P"          # the mount plug build.py makes for use (tested: holds firm, no fatigue, no deformation)
mount_batch = ["P", "Q"]   # what build.py --mounts makes now
mount_open_top = True        # also export each full-face plug of the batch cut at the pocket ceiling (_open)
mount_test_cells = [(-6, 5), (-5, 5), (-4, 5), (-3, 5)]   # plain cells to hang weight from
# variants E/F: the lock is a bar along nearly the whole face, pushed out by a zig-zag
# spring behind it (segments run along the face, joined at alternating ends)
full_face_bar = 1.0          # bar thickness (radial)
full_face_end_gap = 0.35     # bar to pocket ends
spring_segments = 3          # flexing segments of the zig-zag
spring_gap = 0.5             # between bar, segments and pocket floor (closes as the bar moves in)
full_face_pocket_wall = 0.8  # wall left between neighboring pockets
full_face_bump_inset = 0.2   # bump set back into the bar: 0.85 travel, 0.05 preload (A: 1.05, 0.25)


# --- union plug (joins two quadrants across a seam, upper floor) ----------
union_z = (z_floor_split + 0.4, z_top)   # 3.3..7.0: 0.4 above the lowered seam half-walls
union_top_chamfer = 0.4
union_bridge_gap = 0.1       # bridge clearance to the ring ends, per side
lock_depth = 1.2             # tab protrusion past the plug face
lock_base = 0.8              # straight part of the tab before its 45 degree nose
lock_height = 1.0            # tab height at the base, centered on the upper groove

# --- frame and perimeter band ---------------------------------------------
frame_width_x = 470.0
frame_depth_y = 470.0
frame_center_y = row_pitch / 3   # 6.337: the outline is centered on the back/front seam
lateral_wall_width = 7.0         # perimeter band
corner_cut_width = 20.0          # clearance for the frame corners
corner_cut_depth = 35.0
center_notch_half_width = 20.0   # cut-out in the middle of the back and front edges
center_notch_depth = 17.0        # from the outer edge
perimeter_chamfer = 0.4          # bottom outer edges and seam faces (elephant-foot relief)

# M5 screws go sideways through the band into the inner T-slot of the 2020 frame
screw_hole_d = 5.0
pad_width = 10.0
pad_wall = 3.0               # band left between the frame and the screw-head pocket
pad_round = 4.0              # rounding of the tab that rises to the deck panel
pad_cols = (3, 8)            # back/front holes at x = +-n * hex_move_width
pad_rows = (2, 8, -1, -7)    # side holes at y = n * row_pitch

# --- deck panel standoffs (solid cap with an M5 slot) ---------------------
standoff_cells = ((-4, 3), (3, 3), (-4, -3), (3, -3))
standoff_cap_z = 5.0
standoff_chamfer = 0.8
slot_width = 5.4
slot_length = 16.0
slot_round = 2.0
slot_x = 75.0                # slots are at x = +-75, all opening toward +Y
slot_y_start = (58.337, -61.663)   # back pair, front pair

# --- seams: which walls get union plugs (the rest of the seam keeps both half-walls)
union_rows = range(-10, 12)              # vertical seam (x ~ 0), every row
union_cols = [i for i in range(-9, 10) if i not in (-1, 0)]   # back/front seam

# How the quadrants are joined:
#  "v8"        gridv8's design: upper rings open at the seam, snap union plugs on top
#  "dovetail"  the seam strip is solid on the panel side (a stiff cross through the
#              center) and a large dovetail key, pressed in from the panel side,
#              crosses the seam in every row; the mount side stays free
seam_style = "spline"   # "v8" (as gridv8), "dovetail" or "spline"; spline tested OK with 2.0 mm
block_z = z_floor_split + 0.3    # solid from here to z_top: 0.3 above a seated mount plug
dovetail_floor_z = block_z + 1.0  # socket floor, 1 mm above the bridged underside
dovetail_length = 13.0       # into each cell, from the seam
dovetail_neck = 6.3          # at the seam
dovetail_tail = 12.8         # at the far end, at the socket floor
# Angled side walls: the socket narrows toward the panel side faster than the solid
# key does. The key is snug at the socket mouth and its wider bottom is trapped below
# it: going in or out it has to squeeze past the mouth by key_height * tan(key_angle)
# per side (~0.24 mm at 5 degrees), so key_angle sets how hard it holds.
socket_angle = 10.0
key_angle = 5.0
key_angle_variants = (3.0, 5.0, 7.0)   # test keys, to find what suits the printer
key_top_fit = 0.0            # side clearance at the mouth (negative = press fit)
key_end_clearance = 0.2      # at the tail ends, which carry no load
key_lead_in = 0.4            # chamfer at the bottom of the key, also eats elephant foot
key_label_size = 7.0         # engraved label on test keys (bold, ~5 mm tall digits)
key_label_depth = 0.6

#  "spline"    same solid seam strip; each row is joined by a flat spline (a biscuit)
#              slid in sideways when the quadrants are pushed together. The frame holds
#              the quadrants in plane, so the seam only has to stop vertical movement,
#              and a spline's vertical play is just its slot clearance.
spline_z = (block_z + z_top) / 2   # 5.1, ~0.8 mm of block above and below the slot
spline_thickness = 2.0
spline_width = 8.0
spline_half_length = 9.0     # into each block
spline_clearance = 0.1       # per side in the slot: vertical play is twice this
spline_end_clearance = 0.3
spline_lead_in = 0.5         # chamfer on the spline ends
spline_variants = (1.9, 2.0, 2.1)   # test thicknesses, engraved on them
spline_label_size = 5.0
spline_label_depth = 0.4

# optional link on the mount side: double mount plugs bridging the seam from below
seam_bottom_link = False
bridge_height = 2.0          # bridge of the double plug, flush with the grid bottom
bridge_clearance = 0.2

# test coupons: 3x3 cells on each side of the vertical seam
coupon_cells = {
    "L": [(i, j) for j in (1, 2, 3) for i in (-3, -2, -1)],
    "R": [(i, j) for j in (1, 2, 3) for i in (0, 1, 2)],
}
# just the two seam cells joined by one dovetail key, to test the key alone
pair_cells = {"L": [(-1, 2)], "R": [(0, 2)]}
