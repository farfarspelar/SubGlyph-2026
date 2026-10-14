#!/usr/bin/env bash
set -euo pipefail

SUBGLYPH_PYTHON="python3"
if [[ -x .build-venv/bin/python ]]; then
  SUBGLYPH_PYTHON=".build-venv/bin/python"
fi

"$SUBGLYPH_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --icon SubGlyphIcon.png \
  --add-data SubGlyph2026Splash.png:. \
  --name SubGlyph-2026-1.13-test-linux-x86_64 \
  subglyph.py

echo "Linux-program: dist/SubGlyph-2026-1.13-test-linux-x86_64"

mkdir -p dist/SubGlyph-2026-1.13-test-linux-x86_64-distro
cp dist/SubGlyph-2026-1.13-test-linux-x86_64 dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
cp SubGlyphIcon.png dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/SubGlyph.png
cp SubGlyph2026Splash.png dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
cp packaging/linux/SubGlyph.desktop dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
cp README.md dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
cp RELEASE_NOTES-1.13-test.md dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
cp LICENSE dist/SubGlyph-2026-1.13-test-linux-x86_64-distro/
tar -C dist -czf dist/SubGlyph-2026-1.13-test-linux-x86_64.tar.gz SubGlyph-2026-1.13-test-linux-x86_64-distro
echo "Linux-distribution: dist/SubGlyph-2026-1.13-test-linux-x86_64.tar.gz"
