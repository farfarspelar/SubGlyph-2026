"""Compact single-line engraving font used for NC toolpaths."""

import math
from typing import Iterable

Point = tuple[float, float]
Stroke = list[Point]
Arc = tuple[Point, Point, Point, bool]


def _circumcenter(first: Point, middle: Point, last: Point) -> Point:
    """Return the centre of the circle through three non-collinear points."""
    ax, ay = first
    bx, by = middle
    cx, cy = last
    denominator = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(denominator) < 1e-12:
        return middle
    first_squared = ax * ax + ay * ay
    middle_squared = bx * bx + by * by
    last_squared = cx * cx + cy * cy
    return (
        (first_squared * (by - cy) + middle_squared * (cy - ay)
         + last_squared * (ay - by)) / denominator,
        (first_squared * (cx - bx) + middle_squared * (ax - cx)
         + last_squared * (bx - ax)) / denominator,
    )


def _scaled_arc_segments(
    start: Point, end: Point, center: Point, clockwise: bool,
    offset: float, height: float, width: float, compact_circles: bool = False,
) -> list[Arc]:
    """Approximate a scaled circular glyph arc with valid circular G2/G3 arcs."""
    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    if clockwise:
        while end_angle >= start_angle:
            end_angle -= 2 * math.pi
    else:
        while end_angle <= start_angle:
            end_angle += 2 * math.pi
    sweep = end_angle - start_angle
    max_sweep = math.pi if compact_circles and math.isclose(width, height, rel_tol=1e-12) else math.radians(30)
    segment_count = max(1, math.ceil(abs(sweep) / max_sweep))

    # ARC_GLYPHS describes a unit circle. Project its endpoint directions back
    # onto that circle before non-uniform scaling; width != height then becomes
    # an ellipse which is represented by short, controller-valid circle arcs.
    radius = 0.5

    def point_at(angle: float) -> Point:
        return (
            offset + (center[0] + radius * math.cos(angle)) * width,
            (center[1] + radius * math.sin(angle)) * height - height / 2,
        )

    result: list[Arc] = []
    for index in range(segment_count):
        angle_0 = start_angle + sweep * index / segment_count
        angle_1 = start_angle + sweep * (index + 1) / segment_count
        angle_mid = (angle_0 + angle_1) / 2
        first = point_at(angle_0)
        middle = point_at(angle_mid)
        last = point_at(angle_1)
        result.append((first, last, _circumcenter(first, middle, last), clockwise))
    return result


# Glyph coordinates use a 1 × 1 box with Y=0 at the baseline.
GLYPHS: dict[str, list[Stroke]] = {
    "A": [[(0, 0), (.5, 1), (1, 0)], [(.2, .4), (.8, .4)]],
    "B": [[(0, 0), (0, 1), (.65, 1), (1, .8), (1, .6), (.65, .5), (0, .5)],
          [(.65, .5), (1, .35), (1, .15), (.65, 0), (0, 0)]],
    "C": [[(1, .85), (.75, 1), (.25, 1), (0, .75), (0, .25), (.25, 0), (.75, 0), (1, .15)]],
    "D": [[(0, 0), (0, 1), (.6, 1), (1, .7), (1, .3), (.6, 0), (0, 0)]],
    "E": [[(1, 1), (0, 1), (0, 0), (1, 0)], [(0, .5), (.75, .5)]],
    "F": [[(0, 0), (0, 1), (1, 1)], [(0, .5), (.75, .5)]],
    "G": [[(1, .8), (.75, 1), (.25, 1), (0, .75), (0, .25), (.25, 0), (.8, 0), (1, .2), (1, .5), (.6, .5)]],
    "H": [[(0, 0), (0, 1)], [(1, 0), (1, 1)], [(0, .5), (1, .5)]],
    # Continuous paths retrace branches instead of lifting at the junctions.
    "I": [[(0, 1), (.5, 1), (1, 1), (.5, 1), (.5, 0), (0, 0), (.5, 0), (1, 0)]],
    "J": [[(0, .2), (.2, 0), (.65, 0), (.85, .2), (.85, 1)], [(.45, 1), (1, 1)]],
    "K": [[(0, 1), (0, .5), (0, 0), (0, .5), (1, 1), (0, .5), (1, 0)]],
    "L": [[(0, 1), (0, 0), (1, 0)]],
    "M": [[(0, 0), (0, 1), (.5, .45), (1, 1), (1, 0)]],
    "N": [[(0, 0), (0, 1), (1, 0), (1, 1)]],
    "O": [[(.25, 0), (0, .25), (0, .75), (.25, 1), (.75, 1), (1, .75), (1, .25), (.75, 0), (.25, 0)]],
    "P": [[(0, 0), (0, 1), (.7, 1), (1, .8), (1, .6), (.7, .5), (0, .5)]],
    "Q": [[(.25, 0), (0, .25), (0, .75), (.25, 1), (.75, 1), (1, .75), (1, .25), (.75, 0), (.25, 0)], [(.6, .3), (1, 0)]],
    "R": [[(0, 0), (0, 1), (.7, 1), (1, .8), (1, .6), (.7, .5), (0, .5)], [(.6, .5), (1, 0)]],
    "S": [[(1, .8), (.75, 1), (.25, 1), (0, .8), (0, .6), (.25, .5), (.75, .5), (1, .4), (1, .2), (.75, 0), (.25, 0), (0, .2)]],
    "T": [[(0, 1), (1, 1)], [(.5, 1), (.5, 0)]],
    "U": [[(0, 1), (0, .25), (.25, 0), (.75, 0), (1, .25), (1, 1)]],
    "V": [[(0, 1), (.5, 0), (1, 1)]],
    "W": [[(0, 1), (.2, 0), (.5, .55), (.8, 0), (1, 1)]],
    "X": [[(0, 1), (1, 0)], [(0, 0), (1, 1)]],
    "Y": [[(0, 1), (.5, .5), (1, 1)], [(.5, .5), (.5, 0)]],
    "Z": [[(0, 1), (1, 1), (0, 0), (1, 0)]],
    "0": [[(.25, 0), (0, .25), (0, .75), (.25, 1), (.75, 1), (1, .75), (1, .25), (.75, 0), (.25, 0)], [(.2, .15), (.8, .85)]],
    "1": [[(.25, .75), (.5, 1), (.5, 0)], [(.2, 0), (.8, 0)]],
    "2": [[(0, .75), (.25, 1), (.75, 1), (1, .75), (1, .55), (0, 0), (1, 0)]],
    "3": [[(0, .85), (.25, 1), (.75, 1), (1, .8), (1, .6), (.7, .5), (1, .4), (1, .2), (.75, 0), (.25, 0), (0, .15)]],
    "4": [[(.8, 0), (.8, 1), (0, .35), (1, .35)]],
    "5": [[(1, 1), (0, 1), (0, .5), (.7, .5), (1, .35), (1, .15), (.75, 0), (.25, 0), (0, .15)]],
    "6": [[(1, .85), (.75, 1), (.25, 1), (0, .7), (0, .2), (.25, 0), (.75, 0), (1, .2), (1, .4), (.75, .55), (0, .55)]],
    "7": [[(0, 1), (1, 1), (.3, 0)]],
    "8": [[(.25, .5), (0, .65), (0, .85), (.25, 1), (.75, 1), (1, .85), (1, .65), (.75, .5), (.25, .5), (0, .35), (0, .15), (.25, 0), (.75, 0), (1, .15), (1, .35), (.75, .5)]],
    "9": [[(1, .45), (.25, .45), (0, .6), (0, .8), (.25, 1), (.75, 1), (1, .8), (1, .3), (.75, 0), (.25, 0), (0, .15)]],
    "-": [[(.1, .5), (.9, .5)]],
    ".": [[(.45, 0), (.55, 0)]],
    '"': [[(.25, 1), (.2, .7)], [(.75, 1), (.7, .7)]],
    "/": [[(0, 0), (1, 1)]],
    "_": [[(0, 0), (1, 0)]],
    " ": [],
}

# Explicit circular segments for planar XYZ engraving. Coordinates are in the
# same 1 x 1 glyph box as GLYPHS. The boolean is clockwise in glyph X/Y space.
ARC_GLYPHS: dict[str, list[Arc]] = {
    "O": [((.5, 0), (.5, 1), (.5, .5), False), ((.5, 1), (.5, 0), (.5, .5), False)],
    "0": [((.5, 0), (.5, 1), (.5, .5), False), ((.5, 1), (.5, 0), (.5, .5), False)],
    "C": [((1, .15), (.5, 1), (.5, .5), True), ((.5, 1), (1, .85), (.5, .5), True)],
}


def text_arcs(text: str, height: float, width: float, spacing: float = 0.0,
              *, compact_circles: bool = False) -> list[Arc]:
    """Return controller-valid circular arcs approximating the scaled glyphs."""
    normalized = text.upper().replace("Å", "A").replace("Ä", "A").replace("Ö", "O")
    advance = width + spacing
    total_width = max(0.0, len(normalized) * width + max(0, len(normalized) - 1) * spacing)
    left = -total_width / 2
    result: list[Arc] = []
    for index, character in enumerate(normalized):
        offset = left + index * advance
        for start, end, center, clockwise in ARC_GLYPHS.get(character, []):
            result.extend(_scaled_arc_segments(
                start, end, center, clockwise, offset, height, width, compact_circles
            ))
    return result


def text_strokes(
    text: str, height: float, width: float, use_planar_arcs: bool = False,
    spacing: float = 0.0,
) -> list[Stroke]:
    """Return centered physical-coordinate strokes for a text string."""
    normalized = text.upper().replace("Å", "A").replace("Ä", "A").replace("Ö", "O")
    advance = width + spacing
    total_width = max(0.0, len(normalized) * width + max(0, len(normalized) - 1) * spacing)
    left = -total_width / 2
    result: list[Stroke] = []
    fallback = [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)], [(0, 0), (1, 1)]]
    for index, character in enumerate(normalized):
        glyph = GLYPHS.get(character, fallback)
        if use_planar_arcs and character in ARC_GLYPHS:
            if character == "0":
                glyph = GLYPHS["0"][1:]
            else:
                glyph = []
        offset = left + index * advance
        for stroke in glyph:
            result.append([(offset + x * width, y * height - height / 2) for x, y in stroke])
    return result
