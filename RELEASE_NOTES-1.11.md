# SubGlyph 2026 — version 1.11

## Changes

- Only Okuma XYZ+C is changed in this version. X values for plunging,
  clearance and rotational clearance are output as radii for the main program's
  G138 mode. Diameter dimensions entered in the application are retained.
- G138 and G136 are not posted; the main program controls these modes.
- XYZ+C specifies G19 for circular interpolation in the Y/Z plane.
- The standard font's defined circular arcs (O, C and 0) use G2/G3 without
  retraction and re-plunging between connected arc segments. Round shapes use
  arcs of at most 180 degrees. Elliptically scaled shapes retain their
  circular-arc approximations.
- Okuma XZ+C and front-face engraving, as well as FANUC and Siemens posting,
  retain their previous behavior.

## Verification

73 automated regression tests passed, covering radial X positions, rotational
clearance, connected small circular arcs, mirroring and unchanged XZ+C posting.
The absence of G138/G136 in NC output is checked.
The updated XYZ+C posting has not yet been verified on a physical machine.
SIEMENS SINUMERIK support is implemented but has not yet been verified on a physical Siemens-controlled machine.

The main program is responsible for G138/G136, C-axis activation, clearance,
absolute programming and unit mode. G19 and G94 remain active after return;
the main program is responsible for subsequent plane and feed-mode selections.

## Distribution

Linux x86-64 is provided as an executable and a tar.gz archive. Windows x86-64
is provided as an exe and a zip archive. SHA-256 checksums are provided separately.
The builds are unsigned.
