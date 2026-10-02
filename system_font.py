"""Discover system fonts and turn their filled outlines into engraving paths."""

from functools import lru_cache
from pathlib import Path
import os
import sys

from PIL import Image, ImageDraw, ImageFont

Point = tuple[float, float]
Stroke = list[Point]


def system_fonts() -> dict[str, str]:
    """Return display names mapped to usable TrueType/OpenType font files."""
    if sys.platform == "win32":
        roots = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    else:
        roots = [
            Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
            Path.home() / ".local/share/fonts", Path.home() / ".fonts",
        ]
    found: dict[str, str] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                family, style = ImageFont.truetype(str(path), 16).getname()
            except OSError:
                continue
            label = family if style.lower() in ("regular", "normal") else f"{family} — {style}"
            if label in found and found[label] != str(path):
                label = f"{label} ({path.stem})"
            found[label] = str(path)
    return dict(sorted(found.items(), key=lambda item: item[0].casefold()))


def _join_edges(edges: set[tuple[tuple[int, int], tuple[int, int]]]) -> list[list[tuple[int, int]]]:
    starts: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for start, end in edges:
        starts.setdefault(start, []).append(end)
    paths: list[list[tuple[int, int]]] = []
    while edges:
        start, end = next(iter(edges))
        edges.remove((start, end))
        path = [start, end]
        while path[-1] != path[0]:
            candidates = starts.get(path[-1], [])
            next_point = next((point for point in candidates if (path[-1], point) in edges), None)
            if next_point is None:
                break
            edges.remove((path[-1], next_point))
            path.append(next_point)
        if len(path) > 2:
            paths.append(path)
    return paths


@lru_cache(maxsize=512)
def _glyph_contours(font_path: str, character: str) -> tuple[tuple[Point, ...], ...]:
    font = ImageFont.truetype(font_path, 96)
    box = font.getbbox(character, stroke_width=0)
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    mask = Image.new("L", (width + 4, height + 4))
    ImageDraw.Draw(mask).text((2 - box[0], 2 - box[1]), character, font=font, fill=255)
    pixels = mask.load()
    active = {(x, y) for y in range(mask.height) for x in range(mask.width) if pixels[x, y] >= 128}
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for x, y in active:
        if (x, y - 1) not in active: edges.add(((x, y), (x + 1, y)))
        if (x + 1, y) not in active: edges.add(((x + 1, y), (x + 1, y + 1)))
        if (x, y + 1) not in active: edges.add(((x + 1, y + 1), (x, y + 1)))
        if (x - 1, y) not in active: edges.add(((x, y + 1), (x, y)))
    paths = _join_edges(edges)
    # Reduce the raster outline while preserving corners and small details.
    contours = []
    for path in paths:
        reduced = path[::2]
        if reduced[-1] != path[-1]:
            reduced.append(path[-1])
        contours.append(tuple(((x - 2) / width, 1 - (y - 2) / height) for x, y in reduced))
    return tuple(contours)


def outline_text_strokes(text: str, height: float, width: float, font_path: str,
                         spacing: float = 0.0) -> list[Stroke]:
    """Return centered contour-engraving paths scaled to the requested character box."""
    advance = width + spacing
    total_width = max(0.0, len(text) * width + max(0, len(text) - 1) * spacing)
    left = -total_width / 2
    result: list[Stroke] = []
    for index, character in enumerate(text):
        if character.isspace():
            continue
        offset = left + index * advance
        for contour in _glyph_contours(font_path, character):
            result.append([(offset + x * width, y * height - height / 2) for x, y in contour])
    return result
