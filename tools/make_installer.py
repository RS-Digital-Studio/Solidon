"""Baut den Windows-Installer aus dem PyInstaller-Ordner (Bauplan §37.2).

Das Inno-Setup-Skript in packaging/formwerk.iss trägt keine eigenen Werte:
Name, Version, Hersteller und Kennung liegen in app/branding.py fest — der
einen Stelle, an der sie festliegen. Dieses Werkzeug liest sie dort und ruft
ISCC mit den passenden Defines auf.

Voraussetzungen: ein Bau unter dist/Formwerk (pyinstaller
packaging/formwerk.spec) und ein installiertes Inno Setup 6.

    python tools/make_installer.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import APP_ID, APP_NAME, APP_VENDOR, APP_VERSION, WEBSITE_URL

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "dist" / APP_NAME
OUTPUT_DIR = ROOT / "dist"
SCRIPT = ROOT / "packaging" / "formwerk.iss"

#: Wo ISCC üblicherweise liegt, wenn es nicht auf dem PATH steht.
COMPILER_CANDIDATES = (
    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
)


def find_compiler() -> Path | None:
    """Sucht ISCC auf dem PATH und an den üblichen Installationsorten."""
    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)
    for candidate in COMPILER_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    if not (SOURCE_DIR / f"{APP_NAME}.exe").is_file():
        print(f"Kein Bau unter {SOURCE_DIR} — zuerst: pyinstaller packaging/formwerk.spec")
        return 1
    compiler = find_compiler()
    if compiler is None:
        print("Inno Setup 6 nicht gefunden — installieren oder ISCC auf den PATH legen.")
        return 1
    completed = subprocess.run(
        [
            str(compiler),
            f"/DAppName={APP_NAME}",
            f"/DAppVersion={APP_VERSION}",
            f"/DAppVendor={APP_VENDOR}",
            f"/DAppId={APP_ID}",
            f"/DAppUrl={WEBSITE_URL}",
            f"/DSourceDir={SOURCE_DIR}",
            f"/DOutputDir={OUTPUT_DIR}",
            f"/DLicenseFile={ROOT / 'LICENSE'}",
            f"/DSetupIconFile={ROOT / 'packaging' / 'formwerk.ico'}",
            str(SCRIPT),
        ],
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    print(f"Installer: {OUTPUT_DIR / f'{APP_NAME}-Setup-{APP_VERSION}.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
