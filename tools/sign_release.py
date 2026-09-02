"""Signiert das Windows-Paket lokal aus der Signierübergabe der CI (Bauplan §37.2).

Die CI baut die Anwendung und legt sie als prüfsummengebundenes Archiv ab
(Artefakt ``solidon3d-windows-signing-input``). Signiert wird nicht dort,
sondern hier: Das Certum-Zertifikat liegt in der SimplySign-Cloud, und
SimplySign verlangt einen Einmalcode vom Handy — ein Weg, den GitHub Actions
nicht gehen kann und nicht gehen soll (``Signierung/README.md``). Dieses
Werkzeug fährt die Kette am Stück und hält bei jeder abweichenden Prüfsumme an:

    Archiv prüfen → entpacken → Übergabe gegen Produkt und Prüfsummen prüfen
    → Anwendung signieren und prüfen → Übergabe neu binden → Installer bauen
    → Setup-Datei signieren und prüfen → Prüfsumme daneben schreiben
    → Release-Evidenz neu schreiben und die Releaseakte prüfen

Der letzte Schritt ist derselbe wie im CI-Prüfjob, nur gegen den signierten
Installer: Die Evidenz nennt den Hash des äußeren Pakets, und das ist nach
der Signatur ein anderes als das, das die CI geprüft hat.

    python tools/sign_release.py --subject "Robert Schneider"
    python tools/sign_release.py --run 123456789 --subject "Robert Schneider"

Voraussetzungen: SimplySign Desktop verbunden, ``signtool`` aus dem Windows SDK
und Inno Setup 6 installiert; für ``--run`` die GitHub-Kommandozeile ``gh``.
Das Ergebnis liegt unter ``dist/`` neben seiner ``.sha256`` — von dort geht
es wie bisher weiter mit ``make_download.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import (
    APP_ID,
    APP_NAME,
    APP_VENDOR,
    PART_FILE_MIME_TYPE,
    PART_FILE_SUFFIX,
    PROJECT_SUFFIX,
    WEBSITE_URL,
)
from tools import make_installer
from tools.make_installer import _sha256

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_NAME = "solidon3d-windows-signing-input"
ARCHIVE_NAME = "windows-signing-input.zip"
DEFAULT_ARCHIVE = ROOT / "dist" / ARCHIVE_NAME
DEFAULT_STAGE = ROOT / "build" / "signing"
OUTPUT_DIR = ROOT / "dist"
DEFAULT_EVIDENCE = ROOT / "build" / "release-evidence.json"
HANDOFF_NAME = "packaging/build/windows-signing.json"
#: Certums eigener RFC-3161-Zeitstempeldienst. Ohne Zeitstempel verfiele die
#: Signatur mit dem Zertifikat; mit ihm bleibt ein einmal signiertes Paket
#: gültig, auch wenn das Zertifikat nach 459 Tagen abläuft oder wechselt.
TIMESTAMP_URL = "http://time.certum.pl"
#: Wo das Windows SDK sein ``signtool`` ablegt, wenn es nicht auf dem PATH steht.
SDK_BIN = Path("C:/Program Files (x86)/Windows Kits/10/bin")

#: Die Produktpfade, die eine Übergabe tragen muss — dieselben, die
#: ``make_installer.signing_handoff`` schreibt. Ein anderes Produkt wird nicht
#: signiert, auch wenn seine Prüfsummen stimmen.
FIXED_PATHS: dict[str, str] = {
    "application": f"dist/{APP_NAME}/{APP_NAME}.exe",
    "source_dir": f"dist/{APP_NAME}",
    "output_dir": "dist",
    "script": "packaging/solidon3d.iss",
    "licence": "packaging/eula.txt",
    "icon": "packaging/solidon3d.ico",
    "licence_manifest": "packaging/build/licence.manifest",
}
FIXED_PRODUCT: dict[str, object] = {
    "schema_version": 1,
    "app_name": APP_NAME,
    "app_vendor": APP_VENDOR,
    "app_id": APP_ID,
    "app_url": WEBSITE_URL,
    "project_suffix": PROJECT_SUFFIX,
    "part_file_suffix": PART_FILE_SUFFIX,
    "part_file_mime_type": PART_FILE_MIME_TYPE,
}

_ARCHIVE_LINE = re.compile(rf"^([0-9a-f]{{64}})  {re.escape(ARCHIVE_NAME)}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")

#: Der Prozessaufruf, den die Tests austauschen, um signtool, ISCC und gh
#: nachzustellen, ohne sie zu haben.
_run = subprocess.run


class SigningError(RuntimeError):
    """Ein Halt in der Kette — die Meldung sagt, was zu tun ist."""


def _step(title: str) -> None:
    print(f"== {title}")


def download_handoff(run_id: str, target: Path) -> Path:
    """Holt die Signierübergabe eines CI-Laufs über ``gh`` nach ``target``."""
    if shutil.which("gh") is None:
        raise SigningError(
            "Die GitHub-Kommandozeile gh fehlt — installieren (winget install GitHub.cli) "
            f"oder das Artefakt {ARTIFACT_NAME} von Hand nach {target} legen."
        )
    target.mkdir(parents=True, exist_ok=True)
    completed = _run(
        ["gh", "run", "download", run_id, "-n", ARTIFACT_NAME, "-D", str(target)],
        check=False,
    )
    if completed.returncode != 0:
        raise SigningError(
            f"gh konnte das Artefakt {ARTIFACT_NAME} aus Lauf {run_id} nicht laden — "
            "Laufnummer prüfen (gh run list) und ob das Artefakt noch nicht verfallen ist."
        )
    return target / ARCHIVE_NAME


def verify_archive(archive: Path) -> str:
    """Prüft das Archiv gegen seine ``.sha256`` und liefert die Prüfsumme."""
    checksum = archive.with_name(archive.name + ".sha256")
    if not archive.is_file() or not checksum.is_file():
        raise SigningError(
            f"Archiv oder Prüfsumme fehlt unter {archive.parent} — zuerst: "
            f"python tools/sign_release.py --run <lauf> … oder das Artefakt {ARTIFACT_NAME} "
            "aus dem CI-Lauf dorthin laden."
        )
    line = checksum.read_text(encoding="ascii").strip()
    match = _ARCHIVE_LINE.match(line)
    if match is None:
        raise SigningError(f"Ungültige Archiv-Prüfsumme in {checksum.name} — Artefakt neu laden.")
    expected = match.group(1)
    actual = _sha256(archive)
    if actual != expected:
        raise SigningError(
            f"Geändertes Übergabearchiv: {archive.name} hat {actual}, erwartet {expected} — "
            "Artefakt neu aus dem CI-Lauf laden, nichts davon signieren."
        )
    return actual


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _entry_names(zip_file: zipfile.ZipFile, stage: Path) -> list[str]:
    """Prüft jeden Archivpfad, bevor irgendetwas geschrieben wird."""
    seen: set[str] = set()
    names: list[str] = []
    root = stage.resolve()
    for info in zip_file.infolist():
        raw = info.filename
        name = raw.rstrip("/")
        parts = name.split("/")
        if (
            not name
            or "\\" in raw
            or Path(name).is_absolute()
            or "" in parts
            or "." in parts
            or ".." in parts
            or name.casefold() in seen
        ):
            raise SigningError(
                f"Unzulässiger oder doppelter Archivpfad: {raw!r} — das Archiv ist kein "
                "Signiereingang der CI; neu laden."
            )
        seen.add(name.casefold())
        if not _inside(root, (root / name).resolve()):
            raise SigningError(f"Archivpfad verlässt das Ziel: {name!r} — Archiv neu laden.")
        if not raw.endswith("/"):
            names.append(name)
    return names


def extract_archive(archive: Path, stage: Path) -> None:
    """Entpackt das geprüfte Archiv in einen leeren Arbeitsordner."""
    if stage.exists():
        raise SigningError(
            f"Der Arbeitsordner {stage} ist schon da — räumen (Remove-Item -Recurse) "
            "oder mit --stage einen anderen wählen. Ein alter Stand wird nie überschrieben."
        )
    with zipfile.ZipFile(archive) as zip_file:
        names = _entry_names(zip_file, stage)
        for name in names:
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(name) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    for path in stage.rglob("*"):
        status = path.lstat()
        attributes = getattr(status, "st_file_attributes", 0)
        if stat.S_ISLNK(status.st_mode) or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise SigningError(
                f"Die Übergabe enthält eine Verknüpfung: {path.relative_to(stage)} — "
                "Archiv neu laden, nichts davon signieren."
            )


def resolve_handoff_path(stage: Path, name: str) -> Path:
    """Löst einen relativen Übergabepfad auf und hält ihn im Arbeitsordner."""
    if Path(name).is_absolute() or "\\" in name or ".." in name.split("/"):
        raise SigningError(f"Unzulässiger Übergabepfad: {name!r} — Archiv neu laden.")
    root = stage.resolve()
    path = (root / name).resolve()
    if not _inside(root, path):
        raise SigningError(f"Pfadausbruch in der Übergabe: {name!r} — Archiv neu laden.")
    return path


def load_handoff(stage: Path) -> dict[str, Any]:
    """Liest die Übergabe und prüft, dass sie dieses Produkt beschreibt."""
    path = resolve_handoff_path(stage, HANDOFF_NAME)
    try:
        handoff = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SigningError(
            f"Die Übergabe {HANDOFF_NAME} fehlt oder ist unlesbar — Archiv neu laden."
        ) from exc
    if not isinstance(handoff, dict):
        raise SigningError(f"Die Übergabe {HANDOFF_NAME} ist kein Objekt — Archiv neu laden.")
    for key, expected in {**FIXED_PRODUCT, **FIXED_PATHS}.items():
        if handoff.get(key) != expected:
            raise SigningError(
                f"Unbekannte Produktangabe in der Übergabe: {key} = {handoff.get(key)!r}, "
                f"erwartet {expected!r} — das ist nicht der Bau dieses Produkts."
            )
    version = str(handoff.get("app_version", ""))
    if _VERSION.match(version) is None:
        raise SigningError(f"Ungültige Version in der Übergabe: {version!r}.")
    if handoff.get("setup_filename") != f"{APP_NAME}-Setup-{version}.exe":
        raise SigningError(
            f"Unerwarteter Setup-Name in der Übergabe: {handoff.get('setup_filename')!r}."
        )
    for key in FIXED_PATHS:
        resolve_handoff_path(stage, str(handoff[key]))
    return handoff


def verify_inputs(stage: Path, handoff: dict[str, Any]) -> None:
    """Vergleicht Dateiliste und jede Prüfsumme mit dem, was tatsächlich da ist."""
    declared = handoff.get("input_sha256")
    if not isinstance(declared, dict) or not declared:
        raise SigningError("Die Übergabe nennt keine Prüfsummen — Archiv neu laden.")
    actual = sorted(
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file() and path.relative_to(stage).as_posix() != HANDOFF_NAME
    )
    if sorted(declared) != actual:
        extra = sorted(set(actual) - set(declared))
        missing = sorted(set(declared) - set(actual))
        raise SigningError(
            "Dateiliste und Übergabe weichen voneinander ab — "
            f"zu viel: {extra or 'nichts'}, fehlt: {missing or 'nichts'}. Archiv neu laden."
        )
    for name, digest in declared.items():
        if not isinstance(digest, str) or _DIGEST.match(digest) is None:
            raise SigningError(f"Ungültige Datei-Prüfsumme in der Übergabe: {name}.")
        path = resolve_handoff_path(stage, name)
        if _sha256(path) != digest:
            raise SigningError(
                f"Geänderter Signiereingang: {name} — Archiv neu laden, nichts davon signieren."
            )


def find_signtool(explicit: Path | None = None) -> Path:
    """Sucht ``signtool`` auf dem PATH oder im neuesten Windows SDK."""
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise SigningError(f"--signtool zeigt auf keine Datei: {explicit}")
    on_path = shutil.which("signtool")
    if on_path:
        return Path(on_path)
    candidates = sorted(SDK_BIN.glob("*/x64/signtool.exe")) if SDK_BIN.is_dir() else []
    if candidates:
        return candidates[-1]
    raise SigningError(
        "signtool nicht gefunden — das Windows SDK installieren "
        "(winget install Microsoft.WindowsSDK.10.0.26100) oder --signtool <pfad> angeben."
    )


def _identity_arguments(subject: str | None, thumbprint: str | None) -> list[str]:
    if thumbprint:
        return ["/sha1", thumbprint]
    if subject:
        return ["/n", subject]
    raise SigningError("Zertifikat nicht benannt — --subject <Name> oder --thumbprint <SHA-1>.")


def sign_file(
    signtool: Path,
    target: Path,
    *,
    subject: str | None,
    thumbprint: str | None,
    timestamp_url: str,
) -> None:
    """Signiert eine Datei mit Zeitstempel und prüft die Signatur sofort."""
    command = [
        str(signtool),
        "sign",
        "/fd",
        "SHA256",
        "/tr",
        timestamp_url,
        "/td",
        "SHA256",
        *_identity_arguments(subject, thumbprint),
        "/d",
        APP_NAME,
        "/du",
        WEBSITE_URL,
        str(target),
    ]
    if _run(command, check=False).returncode != 0:
        raise SigningError(
            f"signtool konnte {target.name} nicht signieren — ist SimplySign Desktop "
            "verbunden und das Zertifikat im Windows-Zertifikatspeicher sichtbar? "
            "Bei mehreren Zertifikaten --thumbprint statt --subject."
        )
    if _run([str(signtool), "verify", "/pa", "/v", str(target)], check=False).returncode != 0:
        raise SigningError(
            f"Die Signatur von {target.name} ist ungültig — die Datei wird nicht weitergegeben. "
            "Zertifikatskette und Zeitstempel prüfen (signtool verify /pa /v)."
        )


def rebind_handoff(stage: Path, handoff: dict[str, Any]) -> None:
    """Trägt die Prüfsumme der signierten Anwendung in die Übergabe ein."""
    application = resolve_handoff_path(stage, str(handoff["application"]))
    handoff["input_sha256"][str(handoff["application"])] = _sha256(application)
    path = resolve_handoff_path(stage, HANDOFF_NAME)
    path.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_installer(stage: Path, handoff: dict[str, Any]) -> Path:
    """Baut die Setup-Datei mit Inno Setup aus dem signierten Arbeitsordner."""
    compiler = make_installer.find_compiler()
    if compiler is None:
        raise SigningError(
            "Inno Setup 6 nicht gefunden — installieren (winget install JRSoftware.InnoSetup) "
            "oder ISCC auf den PATH legen."
        )
    resolved = {key: resolve_handoff_path(stage, str(handoff[key])) for key in FIXED_PATHS}
    completed = _run(
        [
            str(compiler),
            f"/DAppName={APP_NAME}",
            f"/DAppVersion={handoff['app_version']}",
            f"/DAppVendor={APP_VENDOR}",
            f"/DAppId={APP_ID}",
            f"/DAppUrl={WEBSITE_URL}",
            f"/DProjectSuffix={PROJECT_SUFFIX}",
            f"/DPartFileSuffix={PART_FILE_SUFFIX}",
            f"/DPartFileMimeType={PART_FILE_MIME_TYPE}",
            f"/DSourceDir={resolved['source_dir']}",
            f"/DOutputDir={resolved['output_dir']}",
            f"/DLicenseFile={resolved['licence']}",
            f"/DSetupIconFile={resolved['icon']}",
            str(resolved["script"]),
        ],
        check=False,
    )
    if completed.returncode != 0:
        raise SigningError("Inno Setup konnte den Installer nicht bauen — Ausgabe darüber lesen.")
    setup = resolved["output_dir"] / str(handoff["setup_filename"])
    if not setup.is_file():
        raise SigningError(f"Die exakt benannte Setup-Datei fehlt: {setup}")
    return setup


def write_checksum(target: Path) -> Path:
    """Schreibt ``<sha256>  <name>`` neben die Datei, wie die CI es tut."""
    checksum = target.with_name(target.name + ".sha256")
    checksum.write_text(f"{_sha256(target)}  {target.name}\n", encoding="ascii", newline="\n")
    return checksum


def release_check(stage: Path, handoff: dict[str, Any], setup: Path, evidence: Path) -> str:
    """Schreibt die Release-Evidenz für den signierten Installer und prüft die Akte.

    Dieselben zwei Aufrufe wie im CI-Prüfjob ``windows-release-check``. Der
    Installer wird vorher in die Ablage der Evidenz kopiert, weil der Prüfer
    nur relative Pfade darin auflöst.

    Liefert leer, wenn beides gelungen ist, sonst die Warnung. Ein Fehlschlag
    dieser zwei Schritte hält die Kette **nicht** an — Entscheidung Robert,
    02.09.2026, dieselbe wie in der CI: Kein Release hängt an einer Prüfung,
    die zum ersten Mal läuft. Was fehlt, kommt ins Register. Eine fehlende
    SBOM im Arbeitsordner bleibt dagegen ein Halt, weil sie den gebundenen
    App-Baum selbst betrifft.
    """
    artifact_root = resolve_handoff_path(stage, str(handoff["source_dir"]))
    sboms = sorted(artifact_root.rglob(f"{APP_NAME}.cdx.json"))
    if len(sboms) != 1:
        raise SigningError("Die Endartefakt-SBOM fehlt im Arbeitsordner oder ist mehrdeutig.")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    package = evidence.parent / setup.name
    shutil.copy2(setup, package)
    notices = str(ROOT / "tools" / "make_licence_notices.py")
    written = _run(
        [
            sys.executable,
            notices,
            "--write-evidence",
            "--sbom",
            str(sboms[0]),
            "--release-evidence",
            str(evidence),
            "--package",
            f"windows-installer={package}",
        ],
        check=False,
    )
    if written.returncode != 0:
        return (
            "Die Release-Evidenz wurde nicht geschrieben — Ausgabe darüber lesen; "
            "die Umgebung braucht die Extras geom, ui, agent und brep."
        )
    checked = _run(
        [
            sys.executable,
            notices,
            "--release-check",
            "--artifact-root",
            str(artifact_root),
            "--sbom",
            str(sboms[0]),
            "--release-evidence",
            str(evidence),
        ],
        check=False,
    )
    if checked.returncode != 0:
        return "Die Releasebelege passen nicht zum signierten Installer — Ausgabe darüber lesen."
    return ""


def run(
    *,
    archive: Path,
    stage: Path,
    subject: str | None,
    thumbprint: str | None,
    timestamp_url: str,
    signtool: Path | None,
    evidence: Path,
    output_dir: Path,
) -> Path:
    """Fährt die ganze Kette und liefert den signierten Installer unter ``output_dir``."""
    _identity_arguments(subject, thumbprint)
    tool = find_signtool(signtool)
    _step(f"Archiv prüfen: {archive}")
    verify_archive(archive)
    _step(f"Entpacken nach {stage}")
    extract_archive(archive, stage)
    _step("Übergabe gegen Produkt und Prüfsummen prüfen")
    handoff = load_handoff(stage)
    verify_inputs(stage, handoff)
    application = resolve_handoff_path(stage, str(handoff["application"]))
    _step(f"Anwendung signieren: {application.name} ({handoff['app_version']})")
    sign_file(
        tool, application, subject=subject, thumbprint=thumbprint, timestamp_url=timestamp_url
    )
    rebind_handoff(stage, handoff)
    _step("Installer bauen")
    setup = build_installer(stage, handoff)
    _step(f"Setup-Datei signieren: {setup.name}")
    sign_file(tool, setup, subject=subject, thumbprint=thumbprint, timestamp_url=timestamp_url)
    checksum = write_checksum(setup)
    _step("Release-Evidenz schreiben und Releaseakte prüfen")
    warning = release_check(stage, handoff, setup, evidence)
    if warning:
        print(f"WARNUNG: {warning}")
        print(
            "Der signierte Installer wird trotzdem abgelegt — kein Release hängt an einer "
            "Prüfung, die zum ersten Mal läuft. Den Befund ins Register von ROADMAP.md."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    result = output_dir / setup.name
    shutil.copy2(setup, result)
    shutil.copy2(checksum, output_dir / checksum.name)
    print(f"Signierter Installer: {result}")
    print(f"Prüfsumme: {output_dir / checksum.name}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", metavar="LAUF", help="CI-Laufnummer; holt das Artefakt mit gh")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
    parser.add_argument("--subject", help="Name im Zertifikat, wie ihn signtool /n erwartet")
    parser.add_argument(
        "--thumbprint", help="SHA-1 des Zertifikats, wenn der Name nicht eindeutig ist"
    )
    parser.add_argument("--timestamp", default=TIMESTAMP_URL)
    parser.add_argument("--signtool", type=Path)
    parser.add_argument(
        "--release-evidence",
        type=Path,
        default=DEFAULT_EVIDENCE,
        help="wohin die Release-Evidenz des signierten Installers geschrieben wird",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    arguments = parser.parse_args(argv)
    try:
        archive = arguments.archive
        if arguments.run:
            archive = download_handoff(arguments.run, archive.parent)
        run(
            archive=archive,
            stage=arguments.stage,
            subject=arguments.subject,
            thumbprint=arguments.thumbprint,
            timestamp_url=arguments.timestamp,
            signtool=arguments.signtool,
            evidence=arguments.release_evidence,
            output_dir=arguments.output,
        )
    except SigningError as problem:
        print(problem)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
