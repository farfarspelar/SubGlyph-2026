#!/usr/bin/env bash
set -euo pipefail

SUBGLYPH_PYTHON="python3"
if [[ -x .build-venv/bin/python ]]; then
  SUBGLYPH_PYTHON=".build-venv/bin/python"
fi

"$SUBGLYPH_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --icon SubGlyphIcon.png \
  --add-data README.md:. \
  --add-data LICENSE:. \
  --add-data RELEASE_NOTES-1.11.md:. \
  --add-data SubGlyph2026Splash.png:. \
  --osx-bundle-identifier se.subglyph.app2026 \
  --name "SubGlyph 2026" \
  subglyph.py

ditto -c -k --sequesterRsrc --keepParent \
  "dist/SubGlyph 2026.app" \
  "dist/SubGlyph-2026-1.11-macos.zip"

echo "macOS-program: dist/SubGlyph 2026.app"
echo "macOS-distribution: dist/SubGlyph-2026-1.11-macos.zip"
