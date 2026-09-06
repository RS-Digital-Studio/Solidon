"""Baut den Windows-Installer aus dem PyInstaller-Ordner (Bauplan §37.2).

Das Inno-Setup-Skript in packaging/solidon3d.iss trägt keine eigenen Werte:
Name, Version, Hersteller und Kennung liegen in app/branding.py fest — der
einen Stelle, an der sie festliegen. Dieses Werkzeug liest sie dort und ruft
ISCC mit den passenden Defines auf.

Voraussetzungen: ein Bau unter dist/Solidon (pyinstaller
packaging/solidon3d.spec) und ein installiertes Inno Setup (7 oder 6).

    python tools/make_installer.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import (
    APP_ID,
    APP_NAME,
    APP_VENDOR,
    APP_VERSION,
    PART_FILE_MIME_TYPE,
    PART_FILE_SUFFIX,
    PROJECT_SUFFIX,
    WEBSITE_URL,
)
from app.core.activation import integrity
from tools import asset_rights

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "dist" / APP_NAME
OUTPUT_DIR = ROOT / "dist"
SCRIPT = ROOT / "packaging" / "solidon3d.iss"
SIGNING_HANDOFF = ROOT / "packaging" / "build" / "windows-signing.json"

#: Wo ISCC üblicherweise liegt, wenn es nicht auf dem PATH steht.
#:
#: Version 7 steht vor 6: Wer beide hat, baut mit der neueren, und das
#: Skript in packaging/solidon3d.iss verwendet nichts, was 7 verändert hat.
#: Der jeweils dritte Ort ist der, an dem ``winget install
#: JRSoftware.InnoSetup`` landet: ins Nutzerprofil, ohne Adminrechte und ohne
#: PATH-Eintrag. Ohne ihn meldet dieses Werkzeug „nicht gefunden" neben einer
#: Installation, die einwandfrei daliegt.
COMPILER_CANDIDATES = (
    Path("C:/Program Files (x86)/Inno Setup 7/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 7/ISCC.exe"),
    Path.home() / "AppData/Local/Programs/Inno Setup 7/ISCC.exe",
    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",
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


def manifest_reason(manifest_file: Path | None = None) -> str:
    """Warum das signierte Manifest nicht zu den Grenzdateien passt — leer,
    wenn es passt.

    **Das ist die zweite Art, ein Paket kaputt auszuliefern.** Das Manifest
    entsteht beim Übersetzen des Prüfmoduls und deckt die vier Grenzdateien
    aus §2 C. Wer danach eine davon ändert und nur PyInstaller neu laufen
    lässt, baut ein Paket, das startet und in dem nichts geht:
    ``integrity.intact()`` sagt nein, und damit sind Ändern, Exportieren,
    Slicen und Chat gesperrt — genau so, wie es gegen einen Angreifer gedacht
    ist.

    Am 20.08.2026 ist das hier passiert. Von außen sah das Paket tadellos aus;
    aufgefallen ist es erst im Protokoll einer Testinstallation („licence
    boundary file does not match the manifest: core/export/handover.py"), und
    zwar nachdem die Anwendung ein Projekt, das sie öffnen sollte, wortlos
    nicht öffnete.

    Verglichen werden Prüfsummen und keine Zeitstempel — dieselbe Rechnung,
    die die Anwendung beim Start anstellt.
    """
    manifest_file = manifest_file or ROOT / "packaging" / "build" / "licence.manifest"
    try:
        signed = json.loads(manifest_file.read_text(encoding="utf-8"))["files"]
    except OSError, ValueError, KeyError:
        return (
            "Das signierte Manifest fehlt oder ist unlesbar — zuerst: "
            "python tools/build_licence_module.py"
        )
    drifted = sorted(
        name for name, digest in integrity.boundary_hashes().items() if signed.get(name) != digest
    )
    if not drifted:
        return ""
    return (
        f"Das Manifest deckt diese Datei(en) nicht mehr: {', '.join(drifted)}.\n"
        "Das Paket würde starten und wäre gesperrt. Zuerst: "
        "python tools/build_licence_module.py, dann neu bauen."
    )


def stale_reason() -> str:
    """Warum dieser Bau nicht paketiert werden darf — leer, wenn er darf.

    Die Setup-Datei bekommt Version und Adresse aus :mod:`app.branding`, ihr
    Inhalt aber aus ``dist``. Läuft beides auseinander, entsteht ein Paket, das
    außen neu aussieht und innen alt ist: die Anwendung darin fragte eine
    abgeschaltete Adresse und brachte die Beispiele von vorgestern mit — und
    nichts daran fiele auf, bis ein Kunde es installiert.
    """
    built = (SOURCE_DIR / f"{APP_NAME}.exe").stat().st_mtime
    newest = max(
        (path.stat().st_mtime for path in (ROOT / "app").rglob("*") if path.is_file()),
        default=0.0,
    )
    if newest > built:
        return "Der Bau ist älter als app/ — zuerst neu bauen: pyinstaller packaging/solidon3d.spec"

    drift = manifest_reason()
    if drift:
        return drift

    try:
        asset_rights.require_customer_artifact_cleared(SOURCE_DIR, "win32")
    except RuntimeError as problem:
        return str(problem)

    leftovers = sorted(path.name for path in SOURCE_DIR.rglob("*.autosave"))
    if leftovers:
        return f"Im Bau liegen Sicherungsdateien eines Laufs: {', '.join(leftovers)} — entfernen"
    return ""


def _licence_file() -> Path:
    """Die Lizenzseite des Installers: der Endnutzer-Lizenzvertrag.

    Bis hierher stand dort ``LICENSE`` — eine Urheberrechtsnotiz („alle Rechte
    vorbehalten"), die nicht sagt, was der Käufer erwirbt. Der Vertrag steht in
    ``EULA.md``; ``tools/make_legal.py`` legt die Textversion daneben, weil
    Inno Setup die Datei roh anzeigt und Markdown-Zeichen dort als Zeichen
    stünden.
    """
    text = ROOT / "packaging" / "eula.txt"
    if not text.is_file():
        print("packaging/eula.txt fehlt — zuerst: .venv\\Scripts\\python.exe tools/make_legal.py")
        raise SystemExit(1)
    return text


def _sha256(path: Path) -> str:
    """Liefert die Prüfsumme eines Übergabebestandteils."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _handoff_name(path: Path) -> str:
    """Liefert einen kanonischen relativen Namen innerhalb des Repositorys."""
    root = ROOT.resolve()
    try:
        relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"Signiereingang liegt außerhalb des Repositorys: {path}") from exc
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"Signiereingang darf kein symbolischer Verweis sein: {path}")
    try:
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Signiereingang verlässt das Repository: {path}") from exc
    name = relative.as_posix()
    if not name or name.startswith("/") or ".." in Path(name).parts or "\\" in name:
        raise ValueError(f"Ungültiger relativer Signierpfad: {name}")
    return name


def _signing_inputs() -> list[Path]:
    """Liefert den vollständigen, unveränderlich gebundenen Installer-Eingang."""
    licence = _licence_file()
    fixed = (
        SCRIPT,
        licence,
        ROOT / "packaging" / "solidon3d.ico",
        ROOT / "packaging" / "build" / "licence.manifest",
    )
    entries = list(SOURCE_DIR.rglob("*"))
    links = [path for path in entries if path.is_symlink()]
    if links:
        names = ", ".join(sorted(path.relative_to(SOURCE_DIR).as_posix() for path in links))
        raise ValueError(f"Der Windows-Bau enthält symbolische Verweise: {names}")
    files = [path for path in entries if path.is_file()]
    files.extend(fixed)
    return sorted(files, key=_handoff_name)


def signing_handoff() -> dict[str, object]:
    """Beschreibt den geprüften Windows-Bau für den isolierten Signierjob."""
    application = SOURCE_DIR / f"{APP_NAME}.exe"
    licence = _licence_file()
    manifest = ROOT / "packaging" / "build" / "licence.manifest"
    icon = ROOT / "packaging" / "solidon3d.ico"
    files = _signing_inputs()
    return {
        "schema_version": 1,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "app_vendor": APP_VENDOR,
        "app_id": APP_ID,
        "app_url": WEBSITE_URL,
        "project_suffix": PROJECT_SUFFIX,
        "part_file_suffix": PART_FILE_SUFFIX,
        "part_file_mime_type": PART_FILE_MIME_TYPE,
        "application": _handoff_name(application),
        "source_dir": _handoff_name(SOURCE_DIR),
        "output_dir": OUTPUT_DIR.relative_to(ROOT).as_posix(),
        "script": _handoff_name(SCRIPT),
        "licence": _handoff_name(licence),
        "icon": _handoff_name(icon),
        "licence_manifest": _handoff_name(manifest),
        "setup_filename": f"{APP_NAME}-Setup-{APP_VERSION}.exe",
        "input_sha256": {_handoff_name(path): _sha256(path) for path in files},
    }


def write_signing_handoff() -> int:
    """Schreibt die prüfsummengebundene Übergabe für den Signierjob."""
    if not (SOURCE_DIR / f"{APP_NAME}.exe").is_file():
        print(f"Kein Bau unter {SOURCE_DIR} — zuerst: pyinstaller packaging/solidon3d.spec")
        return 1
    stale = stale_reason()
    if stale:
        print(stale)
        return 1
    SIGNING_HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    SIGNING_HANDOFF.write_text(
        json.dumps(signing_handoff(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Signierübergabe: {SIGNING_HANDOFF}")
    return 0


def main() -> int:
    if not (SOURCE_DIR / f"{APP_NAME}.exe").is_file():
        print(f"Kein Bau unter {SOURCE_DIR} — zuerst: pyinstaller packaging/solidon3d.spec")
        return 1
    stale = stale_reason()
    if stale:
        print(stale)
        return 1
    compiler = find_compiler()
    if compiler is None:
        print("Inno Setup (7 oder 6) nicht gefunden — installieren oder ISCC auf den PATH legen.")
        return 1
    completed = subprocess.run(
        [
            str(compiler),
            f"/DAppName={APP_NAME}",
            f"/DAppVersion={APP_VERSION}",
            f"/DAppVendor={APP_VENDOR}",
            f"/DAppId={APP_ID}",
            f"/DAppUrl={WEBSITE_URL}",
            # Die Endung der Projektdatei — der Installer trägt sie in die
            # Registrierung ein. Auch sie steht in app/branding.py und
            # nirgends sonst.
            f"/DProjectSuffix={PROJECT_SUFFIX}",
            f"/DPartFileSuffix={PART_FILE_SUFFIX}",
            f"/DPartFileMimeType={PART_FILE_MIME_TYPE}",
            f"/DSourceDir={SOURCE_DIR}",
            f"/DOutputDir={OUTPUT_DIR}",
            f"/DLicenseFile={_licence_file()}",
            f"/DSetupIconFile={ROOT / 'packaging' / 'solidon3d.ico'}",
            str(SCRIPT),
        ],
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    print(f"Installer: {OUTPUT_DIR / f'{APP_NAME}-Setup-{APP_VERSION}.exe'}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--signing-handoff"]:
        raise SystemExit(write_signing_handoff())
    if sys.argv[1:]:
        print("Unbekannte Angabe — erlaubt: --signing-handoff")
        raise SystemExit(2)
    raise SystemExit(main())
