@echo off
setlocal
set "SUBGLYPH_PYTHON=python"
where python >nul 2>nul
if errorlevel 1 set "SUBGLYPH_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
"%SUBGLYPH_PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed --icon SubGlyphIcon.png --add-data "SubGlyph2026Splash.png;." --name SubGlyph-2026-1.11-windows-x86_64 subglyph.py
if errorlevel 1 exit /b 1
echo Windows-program: dist\SubGlyph-2026-1.11-windows-x86_64.exe
if exist dist\SubGlyph-2026-1.11-windows-x86_64-distro rmdir /s /q dist\SubGlyph-2026-1.11-windows-x86_64-distro
mkdir dist\SubGlyph-2026-1.11-windows-x86_64-distro
copy dist\SubGlyph-2026-1.11-windows-x86_64.exe dist\SubGlyph-2026-1.11-windows-x86_64-distro\
copy SubGlyph2026Splash.png dist\SubGlyph-2026-1.11-windows-x86_64-distro\
copy README.md dist\SubGlyph-2026-1.11-windows-x86_64-distro\
copy RELEASE_NOTES-1.11.md dist\SubGlyph-2026-1.11-windows-x86_64-distro\
copy LICENSE dist\SubGlyph-2026-1.11-windows-x86_64-distro\
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\SubGlyph-2026-1.11-windows-x86_64-distro\*' -DestinationPath 'dist\SubGlyph-2026-1.11-windows-x86_64.zip'"
if errorlevel 1 exit /b 1
if not exist dist\SubGlyph-2026-1.11-windows-x86_64.zip exit /b 1
echo Windows-distribution: dist\SubGlyph-2026-1.11-windows-x86_64.zip
