"""Convert engraving text into machine-independent ISO NC motion blocks."""

import math
from dataclasses import dataclass

from vector_font import text_arcs, text_strokes
from system_font import outline_text_strokes


@dataclass(frozen=True)
class MantleMarking:
    text: str
    c_degrees: float
    z: float
    diameter: float
    engraving_diameter: float
    clearance_diameter: float
    height: float
    width: float
    orientation: str
    rotation_clearance_diameter: float | None = None
    index_c: bool = True
    rotation_degrees: float = 0.0
    mirrored: bool = False
    plunge_feed: float | None = None
    engraving_feed: float | None = None
    plane: str = "XZ+C"
    y: float = 0.0
    z_direction: str = "Z+"
    c_axis: str = "C"
    character_spacing: float = 0.0
    font_path: str | None = None
    turret: str = "Lower"
    horizontal_offset: float = 0.0
    layout_width: float | None = None


@dataclass(frozen=True)
class FrontMarking:
    text: str
    x: float
    y: float
    c_degrees: float
    engraving_z: float
    clearance_z: float
    height: float
    width: float
    rotation_degrees: float = 0.0
    mirrored: bool = False
    index_c: bool = True
    plunge_feed: float | None = None
    engraving_feed: float | None = None
    c_axis: str = "C"
    character_spacing: float = 0.0
    font_path: str | None = None
    turret: str = "Lower"
    horizontal_offset: float = 0.0
    layout_width: float | None = None


def effective_mirror(mirrored: bool, turret: str) -> float:
    """Return the text transform, including upper-turret compensation."""
    upper_turret = turret.strip().lower() in ("upper", "övre")
    return -1.0 if mirrored != upper_turret else 1.0


def front_marking_blocks(marking: FrontMarking) -> list[str]:
    """Generate planar XY engraving with Z as depth and C as index only."""
    c_angle = math.radians(marking.c_degrees)
    angle = math.radians(marking.rotation_degrees + marking.c_degrees)
    mirror = effective_mirror(marking.mirrored, marking.turret)
    lines = [f"({marking.text})"]
    first_stroke = True
    anchor_x = marking.x * math.cos(c_angle) - marking.y * math.sin(c_angle)
    anchor_y = marking.x * math.sin(c_angle) + marking.y * math.cos(c_angle)

    def mapped(point: tuple[float, float]) -> tuple[float, float]:
        horizontal, vertical = point
        horizontal = (horizontal + marking.horizontal_offset) * mirror
        return (
            anchor_x + horizontal * math.cos(angle) - vertical * math.sin(angle),
            anchor_y + horizontal * math.sin(angle) + vertical * math.cos(angle),
        )

    def position(start_x: float, start_y: float) -> None:
        nonlocal first_stroke
        if first_stroke and marking.index_c:
            lines.append(
                f"G0 Z{nc_number(marking.clearance_z)} X{nc_number(start_x)} "
                f"Y{nc_number(start_y)} {marking.c_axis.upper()}{nc_number(marking.c_degrees)}"
            )
        else:
            lines.append(f"G0 X{nc_number(start_x)} Y{nc_number(start_y)}")
        plunge = f"F{feed_number(marking.plunge_feed)}" if marking.plunge_feed is not None else ""
        lines.append(f"G1 Z{nc_number(marking.engraving_z)}{plunge}")

    strokes = (outline_text_strokes(marking.text, marking.height, marking.width,
                                    marking.font_path, marking.character_spacing)
               if marking.font_path else
               text_strokes(marking.text, marking.height, marking.width,
                            use_planar_arcs=True, spacing=marking.character_spacing))
    for stroke in strokes:
        points = [mapped(point) for point in stroke]
        if not points:
            continue
        position(*points[0])
        for point_index, (x, y) in enumerate(points[1:]):
            feed = ""
            if point_index == 0:
                feed = f"F{feed_number(marking.engraving_feed)}" if marking.engraving_feed is not None else ""
            lines.append(f"G1 X{nc_number(x)} Y{nc_number(y)}{feed}")
        lines.append(f"G0 Z{nc_number(marking.clearance_z)}")
        first_stroke = False

    arcs = [] if marking.font_path else text_arcs(
        marking.text, marking.height, marking.width, spacing=marking.character_spacing)
    for start, end, center, clockwise in arcs:
        start_x, start_y = mapped(start)
        end_x, end_y = mapped(end)
        center_x, center_y = mapped(center)
        position(start_x, start_y)
        feed = f"F{feed_number(marking.engraving_feed)}" if marking.engraving_feed is not None else ""
        machine_clockwise = clockwise if mirror > 0 else not clockwise
        code = "G2" if machine_clockwise else "G3"
        lines.append(
            f"{code} X{nc_number(end_x)} Y{nc_number(end_y)} "
            f"I{nc_number(center_x - start_x)} J{nc_number(center_y - start_y)}{feed}"
        )
        lines.append(f"G0 Z{nc_number(marking.clearance_z)}")
        first_stroke = False
    return lines


def nc_number(value: float) -> str:
    result = f"{value:.3f}".rstrip("0")
    if result in ("-0.", "0."):
        return "0."
    return result


def feed_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def marking_text_width(text: str, width: float, spacing: float = 0.0) -> float:
    """Return the full engraving width used to place a text from its left edge."""
    return max(0.0, len(text) * width + max(0, len(text) - 1) * spacing)


def mantle_marking_blocks(
    marking: MantleMarking, *, reverse_rotary_c: bool = False, compact_circles: bool = False
) -> list[str]:
    """Generate G0/G1 blocks for a marking on a cylindrical surface."""
    if marking.diameter <= 0:
        raise ValueError("Märkdiametern måste vara större än noll.")
    radius = marking.diameter / 2
    along_z = marking.orientation in ("Axiell", "Längs Z-axeln")
    base_angle = 0.0 if along_z else math.pi / 2
    angle = base_angle + math.radians(marking.rotation_degrees)
    mirror = effective_mirror(marking.mirrored, marking.turret)
    text_width = (marking.layout_width if marking.layout_width is not None else
                  marking_text_width(marking.text, marking.width, marking.character_spacing))
    z_origin = (
        (abs(math.cos(angle)) * text_width + abs(math.sin(angle)) * marking.height) / 2
        if along_z else 0.0
    )
    # Turret machining direction is opposite the selected workpiece-facing
    # label: Z- uses the positive coordinate transform and Z+ the negative one.
    z_sign = -1.0 if marking.z_direction in ("+", "Z+") else 1.0
    upper_turret = marking.turret.strip().lower() in ("upper", "övre")
    reverse_index = upper_turret and marking.z_direction in ("-", "Z-")
    indexed_c = -marking.c_degrees if reverse_index else marking.c_degrees
    lines = [f"({marking.text})"]

    first_stroke = True
    planar_xyz = marking.plane in ("XY", "XYZ", "XYZC", "XYZ+C")
    strokes = (outline_text_strokes(marking.text, marking.height, marking.width,
                                    marking.font_path, marking.character_spacing)
               if marking.font_path else
               text_strokes(marking.text, marking.height, marking.width,
                            use_planar_arcs=planar_xyz, spacing=marking.character_spacing))
    for stroke in strokes:
        mapped: list[tuple[float, float]] = []
        for horizontal, vertical in stroke:
            horizontal = (horizontal + marking.horizontal_offset) * mirror
            z_offset = (horizontal * math.cos(angle)
                        + vertical * math.cos(angle + math.pi / 2) + z_origin)
            z = z_sign * (marking.z + z_offset)
            arc = horizontal * math.sin(angle) + vertical * math.sin(angle + math.pi / 2)
            if marking.plane in ("XY", "XYZC", "XYZ+C", "XYZ"):
                mapped.append((z, marking.y + arc))
            else:
                # A positive C movement turns the workpiece beneath the fixed
                # tool, so the visible surface direction is negative C.  This
                # compensation belongs to the post; the preview uses its own
                # viewing transform.
                # OSP rotary engraving uses the opposite C offset convention.
                # Reverse only the offset, preserving the selected index and
                # leaving planar XYZ+C geometry untouched.
                c_offset = math.degrees(arc / radius)
                c = indexed_c + (c_offset if reverse_rotary_c else -c_offset)
                mapped.append((z, c))
        if not mapped:
            continue
        start_z, start_secondary = mapped[0]
        if marking.plane in ("XY", "XYZC", "XYZ+C", "XYZ"):
            if first_stroke and marking.index_c and marking.rotation_clearance_diameter is not None:
                lines.append(f"G0 X{nc_number(marking.rotation_clearance_diameter)}")
                lines.append(
                    f"G0 Z{nc_number(start_z)} Y{nc_number(start_secondary)} "
                    f"{marking.c_axis.upper()}{nc_number(indexed_c)}"
                )
                lines.append(f"G0 X{nc_number(marking.clearance_diameter)}")
            elif first_stroke and marking.index_c:
                lines.append(
                    f"G0 X{nc_number(marking.clearance_diameter)} "
                    f"Z{nc_number(start_z)} Y{nc_number(start_secondary)} "
                    f"{marking.c_axis.upper()}{nc_number(indexed_c)}"
                )
            else:
                lines.append(
                    f"G0 Z{nc_number(start_z)} Y{nc_number(start_secondary)}"
                )
        else:
            lines.append(
                f"G0 X{nc_number(marking.clearance_diameter)} "
                f"Z{nc_number(start_z)} {marking.c_axis.upper()}{nc_number(start_secondary)}"
            )
        if marking.plunge_feed is not None:
            plunge_feed = f"F{feed_number(marking.plunge_feed)}"
        else:
            plunge_feed = ""
        lines.append(f"G1 X{nc_number(marking.engraving_diameter)}{plunge_feed}")
        for point_index, (z, secondary) in enumerate(mapped[1:]):
            engraving_feed = ""
            if point_index == 0:
                if marking.engraving_feed is not None:
                    engraving_feed = f"F{feed_number(marking.engraving_feed)}"
            secondary_axis = (
                "Y" if marking.plane in ("XY", "XYZC", "XYZ+C", "XYZ")
                else marking.c_axis.upper()
            )
            lines.append(
                f"G1 Z{nc_number(z)} {secondary_axis}{nc_number(secondary)}{engraving_feed}"
            )
        lines.append(f"G0 X{nc_number(marking.clearance_diameter)}")
        first_stroke = False

    if planar_xyz and not marking.font_path:
        for start, end, center, clockwise in text_arcs(
            marking.text, marking.height, marking.width, spacing=marking.character_spacing,
            compact_circles=compact_circles
        ):
            def map_planar(point: tuple[float, float]) -> tuple[float, float]:
                horizontal, vertical = point
                horizontal = (horizontal + marking.horizontal_offset) * mirror
                return (
                    z_sign * (marking.z + (
                        horizontal * math.cos(angle)
                        + vertical * math.cos(angle + math.pi / 2) + z_origin
                    )),
                    marking.y + horizontal * math.sin(angle) + vertical * math.sin(angle + math.pi / 2),
                )

            start_z, start_y = map_planar(start)
            end_z, end_y = map_planar(end)
            center_z, center_y = map_planar(center)
            if first_stroke and marking.index_c and marking.rotation_clearance_diameter is not None:
                lines.append(f"G0 X{nc_number(marking.rotation_clearance_diameter)}")
                lines.append(
                    f"G0 Z{nc_number(start_z)} Y{nc_number(start_y)} "
                    f"{marking.c_axis.upper()}{nc_number(indexed_c)}"
                )
                lines.append(f"G0 X{nc_number(marking.clearance_diameter)}")
            elif first_stroke and marking.index_c:
                lines.append(
                    f"G0 X{nc_number(marking.clearance_diameter)} Z{nc_number(start_z)} "
                    f"Y{nc_number(start_y)} {marking.c_axis.upper()}{nc_number(indexed_c)}"
                )
            else:
                lines.append(f"G0 Z{nc_number(start_z)} Y{nc_number(start_y)}")
            if marking.plunge_feed is not None:
                plunge_feed = f"F{feed_number(marking.plunge_feed)}"
            else:
                plunge_feed = ""
            lines.append(f"G1 X{nc_number(marking.engraving_diameter)}{plunge_feed}")
            engraving_feed = f"F{feed_number(marking.engraving_feed)}" if marking.engraving_feed is not None else ""
            # G19 interprets the circular plane as Y/Z, while the glyph mapping
            # above is built as Z/Y. That axis swap reverses arc direction in
            # addition to mirroring and the selected Z transform.
            determinant = -mirror * z_sign
            machine_clockwise = clockwise if determinant > 0 else not clockwise
            code = "G2" if machine_clockwise else "G3"
            lines.append(
                f"{code} Z{nc_number(end_z)} Y{nc_number(end_y)} "
                f"K{nc_number(center_z - start_z)} J{nc_number(center_y - start_y)}{engraving_feed}"
            )
            lines.append(f"G0 X{nc_number(marking.clearance_diameter)}")
            first_stroke = False
    return lines
