// The parameters a user is meant to change, as the page shows them. The rest of params.py are design decisions,
// listed under Advanced by their generator names (with expressions). All of these are in mm.

export const FIELDS = [
  { group: 'Printer frame', name: 'frame_width_x', label: 'Frame inner width (X)',
    help: 'Between the inner faces of the left and right bottom extrusions. The grid fills it.' },
  { group: 'Printer frame', name: 'frame_depth_y', label: 'Frame inner depth (Y)',
    help: 'Between the inner faces of the front and rear bottom extrusions.' },
  { group: 'Printer frame', name: 'corner_cut_width', label: 'Corner cut, width',
    help: 'Each corner is cut away to clear the vertical extrusion and its brackets.' },
  { group: 'Printer frame', name: 'corner_cut_depth', label: 'Corner cut, depth', help: 'Along the side, from the corner.' },
  { group: 'Printer frame', name: 'center_notch_half_width', label: 'Middle notch, half width',
    help: 'Cut-out in the middle of the front and rear edges.' },
  { group: 'Printer frame', name: 'center_notch_depth', label: 'Middle notch, depth', help: 'From the outer edge.' },
  { group: 'Fixing', name: 'screw_hole_d', label: 'Side screw holes',
    help: 'Through the edge band, for the M5 screws into the bottom extrusions\' inner T-slot.' },
  { group: 'Fixing', name: 'slot_x', label: 'Deck screw slots, X',
    help: 'The four standoffs that screw to the deck panel have their slots at ± this X.' },
  { group: 'Fixing', name: 'slot_width', label: 'Deck screw slot width', help: 'For an M5 screw: 5.4.' },
  { group: 'Print fit', name: 'grid_gap', label: 'Mount plug clearance',
    help: 'Per side, between the mount plug and the cell walls (the plug shrinks with it). More is looser and holds less.' },
  { group: 'Print fit', name: 'spline_thickness', label: 'Spline thickness',
    help: 'The flat splines that join the quadrants. Tested: 1.9 loose, 2.0 and 2.1 good.' },
  { group: 'Print fit', name: 'spline_clearance', label: 'Spline slot clearance',
    help: 'Per side, in the seam blocks\' slots: the seam\'s vertical play is twice this.' },
  { group: 'Print fit', name: 'perimeter_chamfer', label: 'Bed chamfer',
    help: 'On the grid\'s bottom outer edges and seam faces, against elephant\'s foot.' },
  { group: 'Mount plug', name: 'plug_hole_d', label: 'Screw hole',
    help: 'Through the plug, for the screw into your electronics\' plate or bracket (M3: 3.0).' },
  { group: 'Mount plug', name: 'plug_cbore_d', label: 'Screw head pocket, diameter', help: 'From the top of the plug.' },
  { group: 'Mount plug', name: 'plug_cbore_depth', label: 'Screw head pocket, depth', help: 'From the top of the plug.' },
];

export const PART_NAMES = {
  quadrant_BL: 'Grid, back left', quadrant_BR: 'Grid, back right', quadrant_FL: 'Grid, front left', quadrant_FR: 'Grid, front right',
  spline: 'Spline (joins the quadrants)', union_plug: 'Union plug (joins the quadrants)', dovetail_key: 'Dovetail key (joins the quadrants)',
  mount_plug: 'Mount plug',
};
