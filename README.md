# SubGlyph 2026

**Version 1.11 — current stable release**

This branch contains **1.12-test**, an evaluation version with administrator
permissions, dynamic FANUC serial numbers and static date markings. See
[TESTVERSION-1.12.md](TESTVERSION-1.12.md) for usage, verification and limitations.
The documentation below describes the stable 1.11 release.

SubGlyph 2026 is a free graphical NC generator for marking and engraving.
It generates subprograms for FANUC, OKUMA OSP and SIEMENS SINUMERIK using a
single-stroke font and displays the markings on the workpiece in an interactive
3D preview.

The application supports **Swedish, Finnish, German, French, English, Bosnian
and Polish**. This documentation is in English; the application remains multilingual.

SubGlyph was created by **Kristian Simontaival**. You can support the project via
[Buy Me a Coffee](https://buymeacoffee.com/FarfarSpelar).

> **Simple should remain simple. Don't overcomplicate things.**

## Important safety information

SubGlyph generates **subprograms**, not complete main programs. Before calling a
generated subprogram, the main program must specify and verify:

- tool selection and tool compensation;
- spindle speed and direction of rotation;
- working and interpolation planes;
- unit mode, such as G20 or G21;
- work origin and coordinate system;
- initial safe positioning;
- the machine's C-axis functions and other machine-specific M/G codes.

SubGlyph does not output G17, G20 or G21. Okuma XYZ+C specifies G19 for circular
interpolation in the Y/Z plane. The main program is responsible for other plane
selections, unit mode and restoring the required modes after the subprogram.

> **Warning:** Always review and simulate the generated NC code. Then perform a
> reduced-feed dry run before using the program in production. Pay particular
> attention to axis directions, work origins, rotational clearance, circular
> interpolation and the controller's programming language.

## Main features

- FANUC (ISO), OKUMA OSP (ISO) and SIEMENS SINUMERIK (ISO) posting.
- One shared program or individual program numbers for each marking entry.
- Up to six marking entries.
- Automatic merging of marking entries with the same O number.
- Cylindrical surface marking with `XZ+C`.
- Flat side marking with `XYZ+C` and C-axis indexing.
- Front-face marking in X/Y with Z as the depth axis and C-axis indexing.
- Round, hexagonal and rectangular stock.
- Individual position, size, rotation, mirroring and Z direction for each entry.
- Selectable rotary axis address, such as `C` or `CS`, in generated NC code.
- Engraving support for the double quotation mark (`"`).
- Individually adjustable character spacing for each marking text.
- Marking along the Z axis or around the circumference of cylindrical surfaces.
- Explicit feed values in every generated program.
- MM and INCH display with conversion of entered values.
- Swedish, Finnish, German, French, English, Bosnian and Polish.
- Interactive 3D preview with orbit, workpiece rotation and zoom.
- Project files in `.SG` format.
- Optional opening of generated programs in the system text editor.
- Localized version and timestamp comments in every NC program.
- Application icon included in distributions.

## System requirements

Prebuilt distributions do not require a separate Python installation.

- The Linux distribution is built for x86-64.
- The Windows distribution is built for 64-bit Windows.
- The macOS version is built locally on a Mac and can be adapted to the target
  Intel or Apple Silicon environment.

Running from source requires Python 3.10 or later, Tkinter and Pillow.
Runtime dependencies are listed in `requirements.txt`; `requirements-build.txt`
adds PyInstaller for packaging. Tests have been run with Python 3.12.

## Quick start

1. Start SubGlyph 2026.
2. Select a language and `MM` or `INCH`.
3. Select FANUC (ISO), OKUMA OSP (ISO) or SIEMENS SINUMERIK (ISO).
4. Enter the project name, program number and program comment.
5. Select the marking surface, active axes and stock type.
6. Enter stock dimensions, marking depth, clearance and feeds.
7. Fill in one or more marking entries.
8. Check the result in the 3D view.
9. Click **Generate NC program**.
10. Review, simulate and dry-run the program using a correctly prepared
    main program.

## User interface

### Program

Select the controller and how the programs should be organized here.

- **FANUC/OKUMA OSP/SIEMENS SINUMERIK:** selects the ISO postprocessor.
- **Project name:** identifies the project.
- **Program number:** supplies the O number for a shared program.
- **Separate programs:** enables one program number per marking entry.
- **Comment:** appears after the O number in the program header.
- **Open after generation:** opens saved files in the system text editor.

The Program tab also reminds you that the tool, spindle speed, working plane
and initial positioning must be defined in the main program.

### Machine and surface

Select the spindle, marking surface, active axes, stock type, depth, clearance
and feed method here.

- **Marking surface:** `Around an axis` or `Front face`.
- **Active axes:** `XZ+C` or `XYZ+C`, depending on the surface and Y axis.
- **Machine has Y axis:** required for `XYZ+C` and front-face machining.
- **Depth direction:** sets the positive or negative direction of the depth axis.
- **Stock type:** Round, Hexagonal or Rectangular.
- **Stock length:** controls workpiece proportions in the 3D preview but does
  not affect the NC code.
- **Marking depth:** radial or axial engagement, depending on the selected surface.
- **Clearance:** normal safety distance from the selected surface.

### Marking text

The **Program name** field is enabled for OKUMA OSP (ISO) and determines the
`.SSB` filename. It does not affect the O number inside the program.

Up to six marking entries can be defined. Each entry can have:

- its own marking text;
- its own program number in separate-program mode;
- an X/Z position, depending on the marking surface;
- a Y position when Y is used;
- a C angle;
- character height and width;
- text rotation;
- individual mirroring.

Empty marking entries are skipped during posting.

## Machining modes

### XZ+C — cylindrical surface

Use this mode for engraving around round stock.

- X specifies engraving depth and clearance.
- Z specifies the position along the workpiece's longitudinal axis. For text
  along the Z axis, ZPos refers to the text's left edge, not its center.
  `ZPos -20` therefore gives Z-20 as the innermost coordinate even when the
  text is rotated 180° with Z direction Z-.
- C forms the marking around the cylindrical surface.
- Y is locked.
- Rounded shapes are approximated with G1 segments because Z/C is not a
  conventional Cartesian circular interpolation plane.

With diameter 50, marking depth 0.5 and clearance 2, the engraving level is
X49.5 and normal clearance is X52.

### XYZ+C — flat side of round, hexagonal or rectangular stock

Use this mode to mark a flat, C-indexed side.

- C selects the workpiece side or angle and remains stationary during marking.
- Z and Y form the engraving path on the surface.
- X specifies depth and normal surface clearance.
- The same C value is not indexed again between marking entries.
- Normal surface clearance is used between characters and separate strokes.
- Rotational clearance is used before indexing to a new C region.

Rotational clearance for hexagonal stock:

```text
2 × NV / √3 + frigång
```

Rotational clearance for rectangular stock:

```text
√(bredd² + höjd²) + frigång
```

In these formulas, `NV` is the across-flats dimension, `bredd` is width,
`höjd` is height and `frigång` is clearance.

Explicitly defined font arcs are posted with G2/G3 and J/K offsets in Y/Z.
The main program must select the correct interpolation plane, except that
Okuma XYZ+C explicitly outputs G19. If character width and height scale an arc
elliptically, the shape is split into several short circular G2/G3 blocks.
This avoids radius-tolerance errors without replacing the arc with G1 segments.

### Front face — X/Y path with Z depth

Use front-face mode to engrave the end face of the workpiece.

- X and Y form the engraving path.
- Z specifies engraving depth and clearance.
- C indexes the marking position and text around the workpiece center.
- Text rotation rotates the text further around its own marking position.
- The same C value is not indexed again between marking entries.
- Front-face mode requires a machine with a Y axis.

Explicitly defined font arcs are posted with G2/G3 and I/J offsets in X/Y.
The main program must select the correct interpolation plane; SubGlyph does
not output G17.

Curved text using a bend radius is not yet enabled for front-face posting.
Leave this field empty in version 1.11.

## Stock types

- **Round:** specified by workpiece diameter.
- **Hexagonal:** specified by the across-flats dimension, `NV`.
- **Rectangular:** specified by width and height. Equal values produce square stock.

For hexagonal and rectangular stock, the distance to the indexed surface is
calculated from the stock dimensions and C angle. Rotational clearance takes
the stock's maximum radius into account so that the tool is clear before the
workpiece rotates.

## Text geometry and arcs

SubGlyph uses a single-stroke font intended for engraving. Characters consist
of lines and, where explicit arc data is available, circular arcs.

- In `XZ+C`, rounded shapes use G1 segments.
- In planar `XYZ+C`, G2/G3 with J/K is used where arc data is available.
- In front-face mode, G2/G3 with I/J is used where arc data is available.
- The characters `O`, `0` and `C` have explicit arc definitions in version 1.11.
- The double quotation mark (`"`) is engraved as two short, separate strokes.
- Lowercase letters are normalized to their uppercase equivalents in the engraving font.
- Other rounded shapes are represented by short G1 segments.

The **Spacing** field on the Marking text tab specifies the free distance,
in the current unit, between adjacent character edges on that row. `0,4`
therefore gives 0.4 mm between characters when MM is selected. `0` adds no
extra free space. The value cannot be negative and is saved separately for
each marking text in the `.SG` project.

## Rotary axis NC address

The **C axis** field on the Marking text tab determines the address used for
all rotary movements. The default is `C`. Machines that use a different address
can be configured with, for example, `CS`, which posts a 60-degree angle as
`CS60` instead of `C60`. The value is saved in the `.SG` project; older projects
without this setting automatically use `C`.

SubGlyph does not add an extra G1 solely to leave G2/G3 mode. Retraction uses
G0. Verify this behavior against the FANUC, OKUMA OSP or SIEMENS SINUMERIK
variant in use.

## Program numbers and files

### Shared program

All active marking entries are written under the program number specified on
the Program tab.

### Separate programs

Each marking entry has its own program number field. Entries with the same
O number are automatically merged into one program, preserving their order.

Example:

```text
Märkpost 1: 1200
Märkpost 2: 1200
Märkpost 3: 1201
```

Here, `Märkpost` means marking entry. The result is one program `O1200` with
the first two entries and one program `O1201` with the third.

### FANUC (ISO)

- The filename is `O` followed by the program number, such as `O1000`.
- Files are saved without a filename extension.
- One file is created per unique O number in separate-program mode.
- Subprograms end with `M99`.

### OKUMA OSP (ISO)

- The file is saved as `Programnamn.SSB`, using the Program name field on the
  Marking text tab (`Programnamn` means program name).
- Several O programs can reside in the same `.SSB` file.
- Each subprogram specifies `G94` before marking so that F values are
  interpreted as feed per minute even if the main program uses `G95`.
- C movements receive explicit `M15` (positive direction) or `M16` (negative
  direction). C targets are written within 0–360°, and unchanged C targets
  are omitted. Engraving-stroke direction is calculated before angle conversion,
  including movements across zero.
- Initial C positioning uses `M15` because the entry angle is unknown.
  Subsequent rapid movements take the shortest path. The main program must
  ensure clearance on entry and absolute programming.
- A single engraving movement of one full revolution or more is rejected.
- For XZ+C, Okuma text orientation is corrected by reversing the C deviation
  around the marking's index position before calculating M15/M16. No fixed
  angular offset is added. Front-face posting retains its previous behavior.
- XYZ+C specifies `G19` before movement. X values for plunging, clearance and
  rotational clearance are output as radii (half the internal diameter values).
  Y/Z and C indexing retain their dimensions.
- In XYZ+C, the single-stroke font's defined circular arcs (O, C and 0) use G2/G3.
  Round shapes use arcs of at most 180 degrees. Elliptically scaled shapes
  retain their circular-arc approximations. Connected arcs run without
  intermediate retractions and re-plunges.
- System-font raster contours and XZ+C's Z/C movements continue to use G1.
  These paths cannot generally be replaced with circular arcs in G17/G19.
- `G138` and `G136` are not posted. The main program controls these modes and
  must activate `G138` before XYZ+C engraving. `G19` remains active after return;
  the main program is responsible for subsequent plane selection.
- Subprograms end with `RTS`.
- `G94` remains active after return. The main program must specify `G95` and an
  appropriate F value before subsequent machining that requires feed per revolution.

The updated Okuma XYZ+C posting has not yet been verified on a physical machine.

### SIEMENS SINUMERIK (ISO)

SIEMENS SINUMERIK support is implemented but has not yet been verified on a physical Siemens-controlled machine.

- The filename is based on the program number and has the `.spf` extension.
- One file is created per unique O number in separate-program mode.
- Subprograms end with `M17`.

## Generated comments

Each program receives a localized comment containing the product version,
date and time. Comments omit language-specific special characters for better
compatibility with older controllers.

```text
(CREATED WITH SUBGLYPH VERSION 1.11)
(CREATED 2026-08-12 21:15:30)
```

## Units

The `MM` and `INCH` buttons change the display unit and convert existing linear
dimensions and feeds in the project.

SubGlyph never outputs G20 or G21. The main program must use the same unit mode
that was selected when the subprogram was generated.

## Feeds

Two feeds are used:

- **Plunge feed:** movement from clearance to engraving depth.
- **Engraving feed:** movements that form the marking.

SubGlyph always outputs explicit F values. Parameter-driven feed has deliberately
been removed to keep subprograms simple and reduce the risk of accidentally
changing or reusing a machine parameter.

Feed is treated as modal and is output on the first relevant movement of a
continuous engraving sequence.

## 3D preview

- **Left mouse button + drag:** orbit and tilt the entire 3D view.
- **Right mouse button + drag:** rotate the workpiece around its longitudinal
  axis to inspect other C-indexed sides.
- **Mouse wheel:** zoom in or out.
- **Solid:** displays shaded stock.
- **Wireframe:** displays stock edges.
- **Off:** hides the stock while retaining the marking.

The preview shows HSP, active axes and the current marking geometry. It is a
visual aid and does not replace machine simulation.
The Lower/Upper selection does not affect text reading direction in the preview;
turret compensation is applied only to the generated NC code.
For Upper + Z-, posting inverts C indexing: a displayed C60 position is output
as C-60 to reach the same visible side on the machine.

## Project files

**File → Save project** saves your work in `.SG` format. **File → Open project**
restores it.

The project file includes:

- language and unit;
- controller and program organization;
- marking surface, active axes, stock type and stock length;
- dimensions, depth, clearance and feeds;
- all six marking entries;
- the setting for opening the result in a text editor.

Older projects are migrated where possible. Missing marking entries are filled
with empty default values.

## Help, bug reports and feature requests

The **Help** menu contains **Report a bug**, **Request a feature**, **About
SubGlyph** and the **Buy Me a Coffee** link. Forms follow the selected language.

Both forms include:

- the fixed recipient `subglyph@gmail.com`;
- the user's email address for replies;
- a subject line and message;
- optional attachments;
- an option to generate and attach a diagnostic log.

The bug-report form can also attach the latest automatically saved crash dump.
Completing the form creates an unsent `.eml` draft containing the recipient,
reply address, text and attachments, and opens it in the system email client.
The user reviews the draft and chooses **Send**. SubGlyph stores no SMTP
passwords and sends nothing automatically.

### Diagnostic log

The **Generate log** button creates a text file containing:

- SubGlyph, Python and operating system versions;
- machine architecture and executable path;
- current project and machine settings;
- recent recorded activities, such as attempts to load, save or generate a program.

The log may contain project data and marking text. Review its contents before
sending the file.

### Crash dump

Unhandled application errors automatically create a timestamped crash dump
with system information and a Python traceback. Tk event errors also include
current settings and the activity log. Reports and logs are saved in the user's
local SubGlyph directory:

- Linux: `$XDG_STATE_HOME/SubGlyph`, or `~/.local/state/SubGlyph`;
- Windows: `%LOCALAPPDATA%\SubGlyph`;
- macOS: `~/Library/Application Support/SubGlyph`.

## Installation and distributions

Download prebuilt binaries and checksums from [GitHub Releases](https://github.com/farfarspelar/SubGlyph-2026/releases).
Binaries are not included in the source repository. The filenames below correspond
to local build outputs in `dist/`.

### Linux

Extract the archive and run the executable. The archive also includes
`SubGlyph.desktop`, `SubGlyph.png` and `README.md`.

- `dist/SubGlyph-2026-1.11-linux-x86_64`
- `dist/SubGlyph-2026-1.11-linux-x86_64.tar.gz`

### Windows

The Windows version is a standalone `.exe` with an embedded application icon.
The ZIP distribution also includes `README.md`:

- `dist/SubGlyph-2026-1.11-windows-x86_64.exe`
- `dist/SubGlyph-2026-1.11-windows-x86_64.zip`

Windows SmartScreen may warn about an unsigned application. This alone does
not mean the file is malicious, but always check its SHA-256 checksum and
obtain the program from a trusted source.

### macOS

A macOS build must be created on macOS because PyInstaller cannot build a
macOS application from Linux or Windows. The macOS workflow has not been verified
in this Linux environment, and no prebuilt macOS package is available for 1.11.
The supplied script creates `SubGlyph 2026.app` and a ZIP archive:

```bash
./build_macos.sh
```

For distribution beyond your own computer, the application should be code-signed
and notarized with an Apple Developer ID. The script creates:

- `dist/SubGlyph 2026.app`
- `dist/SubGlyph-2026-1.11-macos.zip`

### Checksums

SHA-256 checksums for prebuilt 1.11 files are provided in:

- `dist/SubGlyph-2026-1.11-SHA256SUMS.txt`

## Running from source

Install Python 3, Tkinter and the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 subglyph.py
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
If Tkinter is missing, install it through the operating system's Python packages.
The current version opens directly in the main window.

## Automated tests

Run the complete regression suite with:

```bash
python3 -m unittest -v
```

Tests cover program formats, O-number grouping, responsibility for unit modes,
feeds, parameters, rotational clearance, front-face machining and G2/G3 geometry,
among other areas.

## Building distributions

Install the build dependencies:

```bash
python3 -m pip install -r requirements-build.txt
```

Linux:

```bash
./build_linux.sh
```

Windows, from a Windows Python environment:

```bat
build_windows.bat
```

macOS, on a Mac:

```bash
./build_macos.sh
```

Linux and Windows builds include `SubGlyphIcon.png`. The macOS script includes
the same application icon in the application bundle.

## Project structure

- `subglyph.py` — user interface, project format, preview and postprocessor workflow.
- `nc_geometry.py` — coordinate transformations and G0/G1/G2/G3 blocks.
- `vector_font.py` — single-stroke font and arc definitions.
- `test_subglyph.py` — automated regression tests.
- `SubGlyphIcon.png` — application and distribution icon.
- `build_linux.sh` — Linux build and distribution archive.
- `build_windows.bat` — Windows build.
- `build_macos.sh` — macOS application and ZIP archive.
- `packaging/linux/SubGlyph.desktop` — Linux menu integration.

## Known limitations in version 1.11

- SIEMENS SINUMERIK support is implemented but has not yet been verified on a physical Siemens-controlled machine.
- The updated Okuma XYZ+C posting has not yet been verified on a physical machine.
- Curved text using a bend radius is not yet posted on the front face.
- Only certain characters have explicit G2/G3 arcs; other curves use G1.
- Okuma XYZ+C specifies G19. Interpolation planes for other modes and unit mode
  are specified in the main program.
- Machine-builder-specific C-axis codes must be handled in the main program.
- The application does not replace CAM verification or machine simulation.
- Generated code must be adapted and verified for the specific machine,
  controller version and company safety procedures.

## Version status

Version 1.11 is the current version. The focus is on stability, machine testing,
bug fixes, documentation and packaging.

## Public Git release

Source code, images, build scripts and current documentation belong in the Git
repository. `build/`, `dist/`, virtual environments, generated `.spec` files and
local NC programs are excluded by `.gitignore`. Prebuilt binaries and distribution
archives are attached to the release together with their SHA-256 checksums.

Keep the version number consistent across `subglyph.py`, build scripts and
release notes. Run the regression tests before new builds. Build on each target
platform and check archive contents before publication.

`RELEASE_NOTES-1.11.md` describes the current release. README is the entry point
for the source project and is included in distribution archives.
Translation review documents can be regenerated with
`python3 generate_translation_reviews.py`.

## License

Copyright (C) 2026 Kristian Simontaival.

SubGlyph is distributed under the **GNU General Public License version 3
(GPL-3.0-only)**. See [LICENSE](LICENSE) for the full terms.
The application is provided without warranty. When distributing binaries,
make the corresponding source code and license terms available as required
by the license.
