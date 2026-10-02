"""Generate side-by-side review documents for the newest translations."""

from pathlib import Path

import subglyph


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def write_review(language: str, filename: str) -> None:
    lines = [
        f"# SubGlyph {subglyph.APP_VERSION} — {language}",
        "",
        "Svensk källtext och den text som visas i programmet. Dokumentet genereras",
        "direkt från programmets aktiva översättningar.",
        "",
        "## Gränssnitt, status och hjälptexter",
        "",
        "| # | Svenska | Översättning |",
        "|---:|---|---|",
    ]
    for index, source in enumerate(subglyph.TRANSLATIONS["English"], 1):
        lines.append(
            f"| {index} | {cell(source)} | {cell(subglyph.TRANSLATIONS[language][source])} |"
        )
    lines.extend((
        "",
        "## Felrapport och önskemål",
        "",
        "| # | Svenska | Översättning |",
        "|---:|---|---|",
    ))
    for index, source in enumerate(subglyph.SUPPORT_TRANSLATIONS["English"], 1):
        lines.append(
            f"| {index} | {cell(source)} | {cell(subglyph.SUPPORT_TRANSLATIONS[language][source])} |"
        )
    nc = subglyph.NC_COMMENT_TRANSLATIONS[language]
    lines.extend((
        "",
        "## Kommentarer i genererad NC-kod",
        "",
        "| Svenska betydelse | Text i NC-kod |",
        "|---|---|",
        f"| Skapat med SubGlyph version | {cell(nc['generated_with'])} |",
        f"| Skapat | {cell(nc['generated_at'])} |",
        "",
    ))
    Path(filename).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    write_review("Bosanski", "TRANSLATION_REVIEW-BOSNIAN.md")
    write_review("Polski", "TRANSLATION_REVIEW-POLISH.md")
