"""Signiert das Windows-Paket lokal aus der Signierübergabe der CI (Bauplan §37.2).

Die CI baut die Anwendung und legt sie als prüfsummengebundenes Archiv ab
(Artefakt ``solidon3d-windows-signing-input``). Signiert wird nicht dort,
sondern hier: Das Certum-Zertifikat liegt in der SimplySign-Cloud, und
SimplySign verlangt einen Einmalcode vom Handy — ein Weg, den GitHub Actions
nicht gehen kann und nicht gehen soll (``Signierung/README.md``). Dieses
Werkzeug signiert in zwei Phasen und hält bei jeder abweichenden Prüfsumme an:

    Archiv prüfen → lokale Voraussetzungen prüfen → entpacken
    → Übergabe gegen Produkt und Prüfsummen prüfen
    → Anwendung signieren und prüfen → Herkunft für die CI schreiben
    → Installer in der CI bauen lassen → CI-Rückweg prüfen
    → Setup-Datei lokal signieren und prüfen → Prüfsumme daneben schreiben
    → Release-Evidenz neu schreiben und die Releaseakte prüfen

Der letzte Schritt ist derselbe wie im CI-Prüfjob, nur gegen den signierten
Installer: Die Evidenz nennt den Hash des äußeren Pakets, und das ist nach
der Signatur ein anderes als das, das die CI geprüft hat.

    python tools/sign_release.py --check --subject "Name im Zertifikat"
    python tools/sign_release.py --phase application --run 123 --thumbprint <SHA-1>
    python tools/sign_release.py --phase installer --installer-run 456 --thumbprint <SHA-1>

``--check`` liest nur lokale Voraussetzungen. Sichtbarkeit und Schlüsselzuordnung
belegen weder eine aktive Cloud-Sitzung noch eine erfolgreiche Signatur.

Voraussetzungen: SimplySign Desktop verbunden, ``signtool`` aus dem Windows SDK
und die GitHub-Kommandozeile ``gh``. Inno Setup läuft ausschließlich in der CI.
Das Ergebnis liegt unter ``dist/`` neben seiner ``.sha256`` — von dort geht
es wie bisher weiter mit ``make_download.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

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
from tools import make_installer
from tools.make_installer import _sha256
from tools.make_sbom import ARTIFACT_SBOM_NAME

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_NAME = "solidon3d-windows-signing-input"
INSTALLER_ARTIFACT_NAME = "solidon3d-windows-installer-signing-input"
APPLICATION_METADATA = "windows-application-signature.json"
INSTALLER_METADATA = "windows-installer-build.json"
REPOSITORY = "RS-Digital-Studio/Solidon"
BUILD_WORKFLOW = ".github/workflows/build.yml"
INSTALLER_WORKFLOW = ".github/workflows/windows-signed-installer.yml"
#: Jobs des Hauptbaus, die melden und nichts anhalten (RM-350): Kein Job hängt
#: an ihnen, und ihr Rot sagt nichts über das Paket. Der Name steht so in
#: ``build.yml``; wird nur einer von ihnen rot, endet der Lauf trotzdem mit
#: „failure“ (:func:`_only_advisory_jobs_failed`).
ADVISORY_JOBS = frozenset({"Neueste Versionen"})
INSTALLER_ORCHESTRATION_FILES = frozenset(
    {
        INSTALLER_WORKFLOW,
        "tools/sign_release.py",
        "tools/windows_signed_installer.py",
        "tests/test_sign_release.py",
        "tests/test_windows_signed_installer.py",
        "tools/CLAUDE.md",
        "packaging/CLAUDE.md",
        "Signierung/README.md",
        # Der Release-Skill beschreibt dieselbe Kette; kein Paket liest ihn.
        ".claude/skills/erzeugen/SKILL.md",
        ".agents/skills/erzeugen/SKILL.md",
    }
)
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
_CODE_SIGNING_OID = "1.3.6.1.5.5.7.3.3"
# Fester, ausschließlich lesender Befehl: Nutzereingaben werden erst in Python
# ausgewertet. HasPrivateKey liest nur die Zuordnung, niemals den Schlüssel.
_POWERSHELL_PREFIX = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$securityModule = 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
Import-Module (Join-Path $PSHOME $securityModule)
"""
_CERTIFICATE_SCRIPT = (
    _POWERSHELL_PREFIX
    + r"""
$certificates = @(Get-ChildItem -LiteralPath 'Cert:\CurrentUser\My' | ForEach-Object {
    [PSCustomObject]@{
        Thumbprint = $_.Thumbprint
        Subject = $_.Subject
        NotBefore = $_.NotBefore.ToUniversalTime().ToString('o')
        NotAfter = $_.NotAfter.ToUniversalTime().ToString('o')
        HasPrivateKey = $_.HasPrivateKey
        EnhancedKeyUsage = @($_.EnhancedKeyUsageList | ForEach-Object { $_.ObjectId })
    }
})
ConvertTo-Json -InputObject $certificates -Depth 3 -Compress
"""
)
_SIGNATURE_SCRIPT = (
    _POWERSHELL_PREFIX
    + r"""
$signature = Get-AuthenticodeSignature -LiteralPath $env:SOLIDON_SIGNATURE_PATH
[PSCustomObject]@{
    Status = $signature.Status.ToString()
    Thumbprint = $signature.SignerCertificate.Thumbprint
} | ConvertTo-Json -Compress
"""
)

#: Der Prozessaufruf, den die Tests austauschen, um signtool, ISCC und gh
#: nachzustellen, ohne sie zu haben.
_run = subprocess.run


class SigningError(RuntimeError):
    """Ein Halt in der Kette — die Meldung sagt, was zu tun ist."""


@dataclass(frozen=True)
class Certificate:
    """Öffentliche Metadaten und Schlüsselzuordnung im persönlichen Speicher."""

    thumbprint: str
    subject: str
    not_before: datetime
    not_after: datetime
    has_private_key: bool
    enhanced_key_usage: tuple[str, ...]


@dataclass(frozen=True)
class SigningEnvironment:
    """Geprüfte Werkzeuge und die feste Identität für beide Signaturen."""

    signtool: Path
    certificate: Certificate


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
        [
            "gh",
            "run",
            "download",
            run_id,
            "--repo",
            REPOSITORY,
            "-n",
            ARTIFACT_NAME,
            "-D",
            str(target),
        ],
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
    try:
        line = checksum.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise SigningError(
            f"Unlesbare Archiv-Prüfsumme in {checksum.name} — Artefakt neu laden."
        ) from exc
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


def normalize_thumbprint(thumbprint: str) -> str:
    """Normalisiert kopierte SHA-1-Fingerabdrücke und lehnt andere Werte ab."""
    normalized = re.sub(r"[\s:\-\u200e\u200f]", "", thumbprint).upper()
    if re.fullmatch(r"[0-9A-F]{40}", normalized) is None:
        raise SigningError(
            "Ungültiger Fingerabdruck — --thumbprint muss genau 40 Hexadezimalstellen "
            "des SHA-1-Fingerabdrucks im Zertifikatspeicher enthalten."
        )
    return normalized


def _certificate_selector(
    subject: str | None, thumbprint: str | None
) -> tuple[str | None, str | None]:
    """Verlangt genau eine ausdrückliche Zertifikatswahl vor jedem Seiteneffekt."""
    if subject is not None and thumbprint is not None:
        raise SigningError("Nur --subject oder --thumbprint angeben, nicht beide zugleich.")
    if thumbprint is not None:
        return None, normalize_thumbprint(thumbprint)
    if subject is not None and subject.strip():
        return subject.strip(), None
    raise SigningError("Zertifikat nicht benannt — --subject <Name> oder --thumbprint <SHA-1>.")


def _read_powershell_json(script: str, environment: dict[str, str] | None = None) -> Any:
    """Führt eine feste lesende Vorlage aus; zusätzliche Werte reisen nur in der Umgebung."""
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise SigningError("Windows PowerShell fehlt — powershell.exe auf dem PATH bereitstellen.")
    try:
        completed = _run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise SigningError(
            "Windows PowerShell konnte die Signierdaten nicht lesen — Windows PowerShell, "
            "Dateipfad und persönlichen Zertifikatspeicher prüfen, dann --check erneut starten."
        ) from exc
    if completed.returncode != 0:
        raise SigningError(
            "Windows PowerShell konnte die Signierdaten nicht lesen — Dateipfad und "
            "persönlichen Zertifikatspeicher prüfen, dann --check erneut starten."
        )
    try:
        return json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise SigningError(
            "Windows PowerShell lieferte keine lesbaren Signierdaten — Dateipfad und "
            "persönlichen Zertifikatspeicher prüfen, dann --check erneut starten."
        ) from exc


def read_certificates() -> list[Certificate]:
    """Liest ausschließlich Metadaten aus CurrentUser/My über Windows PowerShell."""
    try:
        records = _read_powershell_json(_CERTIFICATE_SCRIPT)
        if not isinstance(records, list):
            raise ValueError("Keine Zertifikatsliste")
        certificates = []
        for record in records:
            if not isinstance(record, dict) or not all(
                isinstance(record.get(key), str)
                for key in ("Thumbprint", "Subject", "NotBefore", "NotAfter")
            ):
                raise ValueError("Unvollständige Zertifikatsmetadaten")
            usages = record.get("EnhancedKeyUsage")
            if (
                not isinstance(record.get("HasPrivateKey"), bool)
                or not isinstance(usages, list)
                or not all(isinstance(usage, str) for usage in usages)
            ):
                raise ValueError("Ungültige Schlüsselzuordnung oder EKU-Liste")
            not_before = datetime.fromisoformat(record["NotBefore"])
            not_after = datetime.fromisoformat(record["NotAfter"])
            if not_before.tzinfo is None or not_after.tzinfo is None or not_before >= not_after:
                raise ValueError("Ungültiger Gültigkeitszeitraum")
            certificates.append(
                Certificate(
                    normalize_thumbprint(record["Thumbprint"]),
                    record["Subject"],
                    not_before,
                    not_after,
                    record["HasPrivateKey"],
                    tuple(usages),
                )
            )
        return certificates
    except (ValueError, TypeError) as exc:
        raise SigningError(
            "Windows PowerShell lieferte keine lesbaren Zertifikatsmetadaten — "
            "CurrentUser/My prüfen, dann --check erneut starten."
        ) from exc


def check_prerequisites(
    *, subject: str | None, thumbprint: str | None, signtool: Path | None = None
) -> SigningEnvironment:
    """Prüft lokale Voraussetzungen ohne Archivzugriff, Schreibzugriff oder Signatur."""
    subject, thumbprint = _certificate_selector(subject, thumbprint)
    if sys.platform != "win32":
        raise SigningError(
            "Die lokale Signierung braucht Windows — auf dem Signierrechner starten."
        )
    tool = find_signtool(signtool)
    matches = [
        certificate
        for certificate in read_certificates()
        if certificate.thumbprint == thumbprint
        or (subject is not None and subject.casefold() in certificate.subject.casefold())
    ]
    if not matches:
        raise SigningError(
            "Kein passendes Zertifikat in CurrentUser/My — SimplySign Desktop verbinden "
            "und --subject oder --thumbprint mit dem persönlichen Zertifikatspeicher abgleichen."
        )
    now = datetime.now(UTC)
    usable = [
        certificate
        for certificate in matches
        if certificate.not_before <= now <= certificate.not_after
        and certificate.has_private_key
        and _CODE_SIGNING_OID in certificate.enhanced_key_usage
    ]
    if len(usable) > 1:
        raise SigningError(
            "Mehrere gültige Code-Signing-Zertifikate passen — das gewünschte "
            "Zertifikat mit --thumbprint eindeutig auswählen."
        )
    if not usable:
        raise SigningError(
            "Kein aktuell gültiges Code-Signing-Zertifikat mit privater Schlüsselzuordnung "
            "gefunden — Gültigkeitszeitraum, Code-Signing-EKU und HasPrivateKey in "
            "CurrentUser/My prüfen; SimplySign Desktop verbinden und --check wiederholen."
        )
    return SigningEnvironment(tool, usable[0])


def sign_file(
    signtool: Path,
    target: Path,
    *,
    thumbprint: str,
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
        "/sha1",
        normalize_thumbprint(thumbprint),
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
    verify_file(signtool, target)
    verify_signature_identity(target, thumbprint)


def verify_file(signtool: Path, target: Path) -> None:
    """Prüft alle Signaturen samt Zeitstempel; auch ein Warnexit hält die Kette an."""
    command = [str(signtool), "verify", "/pa", "/all", "/tw", "/v", str(target)]
    if _run(command, check=False).returncode != 0:
        raise SigningError(
            f"Die Signatur von {target.name} ist ungültig oder ihr Zeitstempel fehlt — "
            "die Datei wird nicht weitergegeben. Zertifikatskette und Zeitstempel prüfen "
            "(signtool verify /pa /all /tw /v)."
        )


def verify_signature_identity(target: Path, expected_thumbprint: str) -> None:
    """Bindet eine gültige Authenticode-Signatur an den ausdrücklich gewählten Herausgeber."""
    expected = normalize_thumbprint(expected_thumbprint)
    record = _read_powershell_json(
        _SIGNATURE_SCRIPT, {**os.environ, "SOLIDON_SIGNATURE_PATH": str(target.resolve())}
    )
    if (
        not isinstance(record, dict)
        or record.get("Status") != "Valid"
        or not isinstance(record.get("Thumbprint"), str)
        or normalize_thumbprint(record["Thumbprint"]) != expected
    ):
        raise SigningError(
            f"Die Signatur von {target.name} gehört nicht gültig zum gewählten Zertifikat — "
            "Herausgeber und Fingerabdruck prüfen, dann die Datei erneut signieren."
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


def build_installer(stage: Path, handoff: dict[str, Any], compiler: Path | None = None) -> Path:
    """Baut ausschließlich im CI-Einstieg die Setup-Datei aus dem signierten Arbeitsordner."""
    compiler = compiler or make_installer.find_compiler()
    if compiler is None:
        raise SigningError(
            "Inno Setup (7 oder 6) nicht gefunden — im CI-Baujob installieren "
            "(winget install JRSoftware.InnoSetup) oder ISCC auf den PATH legen."
        )
    resolved = {key: resolve_handoff_path(stage, str(handoff[key])) for key in FIXED_PATHS}
    # Welche Fassung gebaut hat, gehört ins Protokoll (RM-055) — dieselbe
    # Zeile wie im CI-Job, der den unsignierten Installer baut.
    print(f"Inno Setup: {compiler} ({make_installer.compiler_version(compiler) or 'unbekannt'})")
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


def release_check(stage: Path, handoff: dict[str, Any], setup: Path, evidence: Path) -> None:
    """Schreibt die Release-Evidenz für den signierten Installer und prüft die Akte.

    Dieselben zwei Aufrufe wie im CI-Prüfjob ``windows-release-check``. Der
    Installer wird vorher in die Ablage der Evidenz kopiert, weil der Prüfer
    nur relative Pfade darin auflöst.

    **Seit 0.5.0 hält ein Fehlschlag die Kette an** (RM-115), wie in der CI.
    Bis dahin warnte er nur (Entscheidung Robert, 02.09.2026: kein Release an
    einer Prüfung, die zum ersten Mal läuft) — und im Tag-Lauf von 0.4.4 war
    die Windows-Akte rot, weil ``_zstd.pyd`` keinen Besitzer hatte, ohne dass
    es jemand las. Gegen genau dieses Artefakt ist sie mit der Korrektur grün.
    """
    artifact_root = resolve_handoff_path(stage, str(handoff["source_dir"]))
    sboms = sorted(artifact_root.rglob(ARTIFACT_SBOM_NAME))
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
        raise SigningError(
            "Die Release-Evidenz wurde nicht geschrieben — Ausgabe darüber lesen; die "
            "Umgebung braucht die Extras geom, ui, agent und brep sowie pyinstaller."
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
        raise SigningError(
            "Die Releasebelege passen nicht zum signierten Installer — Ausgabe darüber "
            "lesen, beheben und die Kette neu starten. Der signierte Installer wird "
            "nicht abgelegt."
        )


def _github_metadata(suffix: str) -> dict[str, Any]:
    """Liest eine GitHub-Auskunft aus dem festen Repository ohne Shellauswertung."""
    try:
        completed = _run(
            ["gh", "api", f"repos/{REPOSITORY}/{suffix}"],
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        record = json.loads(completed.stdout)
        if completed.returncode != 0 or not isinstance(record, dict):
            raise ValueError("GitHub-Auskunft fehlt")
    except (OSError, UnicodeError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        raise SigningError(
            "CI-Lauf oder Release-Tag nicht lesbar — gh-Anmeldung und Verbindung prüfen, "
            "dann erneut starten."
        ) from exc
    return record


def _verify_release_tag(commit: str) -> None:
    """Bindet den echten Versionstag direkt oder einmal annotiert an den Baucommit."""
    tag = f"v{APP_VERSION}"
    reference = _github_metadata(f"git/ref/tags/{tag}")
    try:
        if reference["ref"] != f"refs/tags/{tag}":
            raise ValueError("Andere Referenz")
        target = reference["object"]
        object_sha = target["sha"]
        if re.fullmatch(r"[0-9a-fA-F]{40}", object_sha) is None:
            raise ValueError("Ungültiges Tagziel")
        if target["type"] == "tag":
            annotation = _github_metadata(f"git/tags/{object_sha}")
            if annotation["sha"] != object_sha or annotation["tag"] != tag:
                raise ValueError("Andere Annotation")
            target = annotation["object"]
        if target["type"] != "commit" or target["sha"] != commit:
            raise ValueError("Tag und Baucommit weichen ab")
    except (KeyError, TypeError, ValueError) as exc:
        raise SigningError(
            f"Release-Tag {tag} belegt den Baucommit nicht — echten Versionstag und "
            "CI-Lauf prüfen, dann den passenden Lauf auswählen."
        ) from exc


#: Einträge je Seite einer GitHub-Liste; mehr gibt die API nicht heraus.
LISTING_PAGE = 100
#: Oberhalb davon gilt eine Liste als unvollständig statt als endlos.
LISTING_PAGES = 20


def paged_listing(fetch: Callable[[str], Any], path: str, key: str) -> list[Any] | None:
    """Eine GitHub-Liste über alle Seiten — ``None``, wenn sie nicht vollständig aufgeht.

    Eine Seite trägt höchstens :data:`LISTING_PAGE` Einträge. Ein Taglauf
    hatte mit 0.5.3 schon 31 Artefakte, und jede neue Plattform im Vertrag
    der CI bringt weitere; wer nur die erste Seite liest, findet das
    Signierarchiv auf der zweiten nie. Vollständig heißt: so viele Einträge,
    wie ``total_count`` auf der ersten Seite nennt, und jede weitere Seite
    nennt dieselbe Zahl — ändert sich die Liste zwischen zwei Abfragen, kann
    ein Eintrag doppelt kommen oder fehlen.
    """
    items: list[Any] = []
    expected: int | None = None
    for page in range(1, LISTING_PAGES + 1):
        listing = fetch(f"{path}?per_page={LISTING_PAGE}&page={page}")
        chunk = listing.get(key) if isinstance(listing, dict) else None
        total = listing.get("total_count") if isinstance(listing, dict) else None
        if not isinstance(chunk, list) or type(total) is not int:
            return None
        if expected is None:
            expected = total
        elif total != expected:
            return None
        items.extend(chunk)
        if len(items) >= expected or len(chunk) < LISTING_PAGE:
            return items if len(items) == expected else None
    return None


def _only_advisory_jobs_failed(run_id: str, record: dict[str, Any]) -> bool:
    """Sagt, ob ein rot beendeter Hauptbau allein an einem meldenden Job hängt.

    So entschiede GitHub selbst, trüge der Job ``continue-on-error``: Die
    Jobliste des letzten Versuchs ist vollständig gelesen, jeder Job
    abgeschlossen, jeder außer :data:`ADVISORY_JOBS` erfolgreich oder
    übersprungen, und mindestens einer von ihnen ist tatsächlich rot."""
    jobs = paged_listing(_github_metadata, f"actions/runs/{run_id}/jobs", "jobs")
    if not jobs:
        return False
    advisory_failed = False
    for job in jobs:
        if (
            not isinstance(job, dict)
            or str(job.get("run_id")) != run_id
            or job.get("run_attempt") != record.get("run_attempt")
            or job.get("status") != "completed"
        ):
            return False
        if job.get("name") in ADVISORY_JOBS and job.get("conclusion") == "failure":
            advisory_failed = True
        elif job.get("conclusion") not in {"success", "skipped"}:
            return False
    return advisory_failed


def verify_ci_run(run_id: str, workflow: str) -> dict[str, Any]:
    """Bindet einen erfolgreichen GitHub-Lauf an Repository, Workflow und Commit.

    Erfolgreich heißt „success“ — oder beim Hauptbau ein „failure“, das allein
    an einem meldenden Job hängt (:data:`ADVISORY_JOBS`, RM-350)."""
    if re.fullmatch(r"[1-9][0-9]*", run_id) is None:
        raise SigningError(
            "Ungültige CI-Laufnummer — die numerische ID aus GitHub Actions angeben."
        )
    if shutil.which("gh") is None:
        raise SigningError("GitHub CLI fehlt — gh installieren und für das Repository anmelden.")
    record = _github_metadata(f"actions/runs/{run_id}")
    try:
        manual_main = (
            record.get("event") == "workflow_dispatch" and record.get("head_branch") == "main"
        )
        release_tag = (
            workflow == BUILD_WORKFLOW
            and record.get("event") == "push"
            and record.get("head_branch") == f"v{APP_VERSION}"
        )
        if (
            workflow not in {BUILD_WORKFLOW, INSTALLER_WORKFLOW}
            or str(record.get("id")) != run_id
            or record.get("status") != "completed"
            or record.get("conclusion") not in {"success", "failure"}
            or not (manual_main or release_tag)
            or record.get("path") != workflow
            or record.get("repository", {}).get("full_name") != REPOSITORY
            or record.get("head_repository", {}).get("full_name") != REPOSITORY
            or re.fullmatch(r"[0-9a-fA-F]{40}", str(record.get("head_sha", ""))) is None
        ):
            raise ValueError("Lauf passt nicht")
        if record.get("conclusion") == "failure" and not (
            workflow == BUILD_WORKFLOW and _only_advisory_jobs_failed(run_id, record)
        ):
            raise ValueError("Lauf ist rot")
    except (ValueError, TypeError, AttributeError) as exc:
        raise SigningError(
            f"CI-Lauf {run_id} ist kein erfolgreich abgeschlossener Lauf von {workflow} "
            f"in {REPOSITORY} — passenden Lauf in GitHub Actions auswählen."
        ) from exc
    if release_tag:
        _verify_release_tag(record["head_sha"])
    return record


def _git_tree_leaves(commit: str) -> dict[str, tuple[str, str, str]]:
    """Prüft Commitbindung und rekonstruiert jeden Baum gegen seine Objekt-SHA."""
    try:
        record = _github_metadata(f"git/commits/{commit}")
        if record["sha"] != commit:
            raise ValueError("Anderer Commit")
        root_sha = record["tree"]["sha"]
        if not isinstance(root_sha, str) or re.fullmatch(r"[0-9a-f]{40}", root_sha) is None:
            raise ValueError("Root-Baum fehlt")
        tree = _github_metadata(f"git/trees/{root_sha}?recursive=1")
        if (
            tree["sha"] != root_sha
            or tree["truncated"] is not False
            or not isinstance(tree["tree"], list)
        ):
            raise ValueError("Baum unvollständig")
        entries: dict[str, tuple[str, str, str]] = {}
        modes = {
            "040000": "tree",
            "100644": "blob",
            "100755": "blob",
            "120000": "blob",
            "160000": "commit",
        }
        for item in tree["tree"]:
            path, kind, mode, sha = (item[key] for key in ("path", "type", "mode", "sha"))
            if not all(isinstance(value, str) for value in (path, kind, mode, sha)):
                raise ValueError("Ungültiger Baumeintrag")
            relative = PurePosixPath(path)
            if (
                not path
                or relative.is_absolute()
                or relative.as_posix() != path
                or ".." in relative.parts
                or "\\" in path
                or "\x00" in path
                or path in entries
                or modes.get(mode) != kind
                or re.fullmatch(r"[0-9a-f]{40}", sha) is None
            ):
                raise ValueError("Ungültiger oder doppelter Baumpfad")
            entries[path] = (kind, mode, sha)
        directories = {
            "": root_sha,
            **{path: value[2] for path, value in entries.items() if value[0] == "tree"},
        }
        children: dict[str, list[tuple[str, tuple[str, str, str]]]] = {
            path: [] for path in directories
        }
        for path, value in entries.items():
            parent, _, name = path.rpartition("/")
            if parent not in children:
                raise ValueError("Elternbaum fehlt")
            children[parent].append((name, value))
        for path, expected in directories.items():
            ordered = sorted(
                children[path],
                key=lambda item: (item[0] + ("/" if item[1][0] == "tree" else "")).encode("utf-8"),
            )
            content = b"".join(
                (mode.lstrip("0") + " " + name).encode("utf-8") + b"\x00" + bytes.fromhex(sha)
                for name, (_kind, mode, sha) in ordered
            )
            actual = hashlib.sha1(
                b"tree " + str(len(content)).encode("ascii") + b"\x00" + content
            ).hexdigest()
            if actual != expected:
                raise ValueError("Bauminhalt passt nicht zur Objekt-SHA")
        return {path: value for path, value in entries.items() if value[0] != "tree"}
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise SigningError(
            "Git-Baum ist nicht vollständig gebunden — API-Beleg und Quellcommit prüfen."
        ) from exc


def verify_installer_source(source_commit: str, installer_commit: str) -> None:
    """Erlaubt nur einen Nachfolgecommit mit unveränderten Produkt- und Paketblättern."""
    if any(
        re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (source_commit, installer_commit)
    ):
        raise SigningError(
            "Ungültige Commitbindung — vollständige Quell- und Installer-SHA angeben."
        )
    if source_commit == installer_commit:
        return
    comparison = _github_metadata(f"compare/{source_commit}...{installer_commit}")
    try:
        if (
            comparison["status"] != "ahead"
            or comparison["base_commit"]["sha"] != source_commit
            or comparison["merge_base_commit"]["sha"] != source_commit
        ):
            raise ValueError("Kein Nachfolgecommit")
    except (KeyError, TypeError, ValueError) as exc:
        raise SigningError(
            "Installer ist kein Nachfolgecommit — Herkunft unverändert lassen."
        ) from exc
    source, installer = _git_tree_leaves(source_commit), _git_tree_leaves(installer_commit)
    if source.keys() != installer.keys():
        raise SigningError(
            "Dateibestand des Installercommits weicht ab — Produktbaum unverändert lassen."
        )
    for path, original in source.items():
        current = installer[path]
        if original == current:
            continue
        if (
            path not in INSTALLER_ORCHESTRATION_FILES
            or original[:2] != current[:2]
            or original[0] != "blob"
            or original[1] not in {"100644", "100755"}
        ):
            raise SigningError(
                f"Installercommit verändert {path} — ausschließlich benannte Orchestrierung ändern."
            )


def signing_metadata(value: object) -> dict[str, Any]:
    """Prüft den kleinen Herkunftsvertrag beider CI-Übergaben vollständig."""
    keys = {
        "schema_version",
        "app_version",
        "source_run_id",
        "source_commit",
        "source_archive_sha256",
        "unsigned_application_sha256",
        "signed_application_sha256",
        "certificate_thumbprint",
    }
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
    ):
        raise SigningError(
            "Die Signierherkunft ist unvollständig — die Anwendungsphase neu starten."
        )
    if (
        not isinstance(value["app_version"], str)
        or _VERSION.fullmatch(value["app_version"]) is None
        or not isinstance(value["source_run_id"], str)
        or re.fullmatch(r"[1-9][0-9]*", value["source_run_id"]) is None
        or not isinstance(value["source_commit"], str)
        or re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]) is None
        or not isinstance(value["certificate_thumbprint"], str)
        or re.fullmatch(r"[0-9A-F]{40}", value["certificate_thumbprint"]) is None
        or any(
            not isinstance(value[key], str) or _DIGEST.fullmatch(value[key]) is None
            for key in (
                "source_archive_sha256",
                "unsigned_application_sha256",
                "signed_application_sha256",
            )
        )
    ):
        raise SigningError("Die Signierherkunft ist ungültig — die Anwendungsphase neu starten.")
    return value


def _publish_pair(source: Path, companion: Path, output_dir: Path) -> Path:
    """Prüft beide Kopien vollständig, bevor die sichtbare Datei ersetzt wird."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = output_dir / source.name
    expected_hash = _sha256(source)
    with tempfile.TemporaryDirectory(prefix=".signing-output-", dir=output_dir) as directory:
        staged = Path(directory) / source.name
        staged_companion = Path(directory) / companion.name
        shutil.copy2(source, staged)
        shutil.copy2(companion, staged_companion)
        if (
            _sha256(staged) != expected_hash
            or staged_companion.read_bytes() != companion.read_bytes()
        ):
            raise SigningError(
                "Die abschließende Kopie stimmt nicht mit der signierten Datei überein. "
                "Freien Speicher und Datenträger prüfen; die bisherige Datei bleibt erhalten."
            )
        staged.replace(result)
        try:
            staged_companion.replace(output_dir / companion.name)
        except OSError:
            (output_dir / companion.name).unlink(missing_ok=True)
            raise
    return result


def sign_application(
    *,
    run_id: str,
    stage: Path,
    subject: str | None,
    thumbprint: str | None,
    timestamp_url: str,
    signtool: Path | None,
    output_dir: Path,
) -> Path:
    """Signiert ausschließlich die Anwendung aus einem erfolgreichen CI-Bau."""
    subject, thumbprint = _certificate_selector(subject, thumbprint)
    source = verify_ci_run(run_id, BUILD_WORKFLOW)
    with tempfile.TemporaryDirectory(prefix=".application-input-") as directory:
        archive = download_handoff(run_id, Path(directory))
        _step(f"Archiv prüfen: {archive}")
        archive_hash = verify_archive(archive)
        environment = check_prerequisites(subject=subject, thumbprint=thumbprint, signtool=signtool)
        _step(f"Entpacken nach {stage}")
        extract_archive(archive, stage)
    tool = environment.signtool
    thumbprint = environment.certificate.thumbprint
    _step("Übergabe gegen Produkt und Prüfsummen prüfen")
    handoff = load_handoff(stage)
    verify_inputs(stage, handoff)
    application = resolve_handoff_path(stage, str(handoff["application"]))
    unsigned_hash = _sha256(application)
    _step(f"Anwendung signieren: {application.name} ({handoff['app_version']})")
    sign_file(tool, application, thumbprint=thumbprint, timestamp_url=timestamp_url)
    metadata = {
        "schema_version": 1,
        "app_version": handoff["app_version"],
        "source_run_id": run_id,
        "source_commit": source["head_sha"].lower(),
        "source_archive_sha256": archive_hash,
        "unsigned_application_sha256": unsigned_hash,
        "signed_application_sha256": _sha256(application),
        "certificate_thumbprint": thumbprint,
    }
    handoff["signing"] = metadata
    rebind_handoff(stage, handoff)
    with tempfile.TemporaryDirectory(prefix=".application-output-") as directory:
        companion = Path(directory) / APPLICATION_METADATA
        companion.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        result = _publish_pair(application, companion, output_dir)
    print(f"Signierte Anwendung für den CI-Installerbau: {result}")
    print(f"Herkunft: {output_dir / APPLICATION_METADATA}")
    return result


def sign_installer(
    *,
    installer_run_id: str,
    stage: Path,
    subject: str | None,
    thumbprint: str | None,
    timestamp_url: str,
    signtool: Path | None,
    evidence: Path,
    output_dir: Path,
) -> Path:
    """Prüft den CI-Rückweg, signiert ausschließlich dessen Setup und belegt das Ergebnis."""
    subject, thumbprint = _certificate_selector(subject, thumbprint)
    handoff = load_handoff(stage)
    verify_inputs(stage, handoff)
    metadata = signing_metadata(handoff.get("signing"))
    application = resolve_handoff_path(stage, str(handoff["application"]))
    if metadata["app_version"] != handoff["app_version"] or (
        metadata["signed_application_sha256"] != _sha256(application)
    ):
        raise SigningError(
            "Der Anwendungsstand passt nicht zur Herkunft — Anwendungsphase neu starten."
        )
    source = verify_ci_run(metadata["source_run_id"], BUILD_WORKFLOW)
    installer_run = verify_ci_run(installer_run_id, INSTALLER_WORKFLOW)
    if source["head_sha"].lower() != metadata["source_commit"]:
        raise SigningError(
            "CI-Commits und Signierherkunft weichen ab — passenden Installerlauf auswählen."
        )
    installer_commit = installer_run["head_sha"].lower()
    verify_installer_source(metadata["source_commit"], installer_commit)
    # Die umgebundene lokale Übergabe ist kein unabhängiger Herkunftsnachweis.
    # Auch der unveränderte Restbaum bleibt an den ursprünglichen CI-Eingang gebunden.
    with tempfile.TemporaryDirectory(prefix=".source-input-") as directory:
        archive = download_handoff(metadata["source_run_id"], Path(directory))
        if verify_archive(archive) != metadata["source_archive_sha256"]:
            raise SigningError(
                "Der ursprüngliche CI-Eingang weicht ab — die Anwendungsphase neu starten."
            )
        with zipfile.ZipFile(archive) as zipped:
            try:
                original = json.loads(zipped.read(HANDOFF_NAME))
            except (KeyError, ValueError) as exc:
                raise SigningError(
                    "Die ursprüngliche CI-Übergabe fehlt — den Anwendungsbau prüfen."
                ) from exc
        restored = {key: value for key, value in handoff.items() if key != "signing"}
        restored["input_sha256"] = {
            **handoff["input_sha256"],
            handoff["application"]: metadata["unsigned_application_sha256"],
        }
        if original != restored:
            raise SigningError(
                "Der lokale Arbeitsstand weicht von der CI-Herkunft ab — "
                "Anwendungsphase neu starten."
            )
    environment = check_prerequisites(subject=subject, thumbprint=thumbprint, signtool=signtool)
    expected_identity = metadata["certificate_thumbprint"]
    if environment.certificate.thumbprint != expected_identity:
        raise SigningError(
            "Anderes Signierzertifikat gewählt — denselben Fingerabdruck "
            "wie für die Anwendung angeben."
        )
    verify_file(environment.signtool, application)
    verify_signature_identity(application, expected_identity)
    with tempfile.TemporaryDirectory(prefix=".installer-input-") as downloaded:
        folder = Path(downloaded)
        completed = _run(
            [
                "gh",
                "run",
                "download",
                installer_run_id,
                "--repo",
                REPOSITORY,
                "-n",
                INSTALLER_ARTIFACT_NAME,
                "-D",
                str(folder),
            ],
            check=False,
        )
        if completed.returncode != 0:
            raise SigningError(
                "Die CI-Installerübergabe fehlt — erfolgreichen Installerlauf und Artefakt prüfen."
            )
        setup_name = str(handoff["setup_filename"])
        expected_names = {setup_name, setup_name + ".sha256", INSTALLER_METADATA}
        if {path.name for path in folder.iterdir()} != expected_names or any(
            not path.is_file() or path.is_symlink() for path in folder.iterdir()
        ):
            raise SigningError(
                "Unerwartete Dateien in der CI-Installerübergabe — Artefakt neu bauen lassen."
            )
        package = folder / setup_name
        package_hash = _sha256(package)
        try:
            returned = json.loads((folder / INSTALLER_METADATA).read_text(encoding="utf-8"))
            checksum_line = (folder / (setup_name + ".sha256")).read_text(encoding="ascii").strip()
        except ValueError as exc:
            raise SigningError(
                "Unlesbare Installerherkunft — CI-Installerlauf erneut ausführen."
            ) from exc
        if returned != {
            **metadata,
            "installer_sha256": package_hash,
            "installer_commit": installer_commit,
            "installer_run_id": installer_run_id,
        } or (checksum_line != f"{package_hash}  {setup_name}"):
            raise SigningError(
                "CI-Installer, Prüfsumme und Signierherkunft weichen ab — "
                "passenden CI-Rückweg laden."
            )
        with tempfile.TemporaryDirectory(prefix=".installer-signing-", dir=stage) as directory:
            setup = Path(directory) / setup_name
            shutil.copy2(package, setup)
            if _sha256(setup) != package_hash:
                raise SigningError(
                    "Die Installerkopie weicht ab — Datenträger prüfen und erneut starten."
                )
            sign_file(
                environment.signtool,
                setup,
                thumbprint=expected_identity,
                timestamp_url=timestamp_url,
            )
            checksum = write_checksum(setup)
            release_check(stage, handoff, setup, evidence)
            result = _publish_pair(setup, checksum, output_dir)
    print(f"Signierter Installer: {result}")
    print(f"Prüfsumme: {output_dir / (result.name + '.sha256')}")
    return result


def run(**arguments: object) -> Path:
    """Hält Aufrufer des alten lokalen Komplettbaus vor jeder Änderung an."""
    raise SigningError(
        "Die CI baut den Installer — --phase application oder --phase installer wählen."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="nur lokale Voraussetzungen lesen; nichts signieren"
    )
    parser.add_argument("--run", metavar="LAUF", help="CI-Laufnummer; holt das Artefakt mit gh")
    parser.add_argument("--installer-run", metavar="LAUF", help="CI-Lauf des Installerbaus")
    parser.add_argument("--phase", choices=("application", "installer"))
    parser.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
    parser.add_argument(
        "--subject", help="eindeutiger Teil des Zertifikatsnamens in CurrentUser/My"
    )
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
        subject, thumbprint = _certificate_selector(arguments.subject, arguments.thumbprint)
        if arguments.check:
            if arguments.run or arguments.installer_run or arguments.phase:
                raise SigningError("--check und CI-Phasen nicht kombinieren — getrennt aufrufen.")
            environment = check_prerequisites(
                subject=subject, thumbprint=thumbprint, signtool=arguments.signtool
            )
            certificate = environment.certificate
            print(f"SignTool: {environment.signtool}")
            print(f"Zertifikat in CurrentUser/My: {certificate.subject}")
            print(f"SHA-1: {certificate.thumbprint}")
            print(f"Gültig bis: {certificate.not_after.isoformat()}")
            print(
                "Lokale Voraussetzungen vorhanden; HasPrivateKey bestätigt die Zuordnung. "
                "Dies ist kein Cloud-Signiertest: SimplySign-Sitzung, Zeitstempeldienst "
                "und tatsächliche Signatur sind damit noch nicht geprüft."
            )
            return 0
        common = {
            "stage": arguments.stage,
            "subject": subject,
            "thumbprint": thumbprint,
            "timestamp_url": arguments.timestamp,
            "signtool": arguments.signtool,
            "output_dir": arguments.output,
        }
        if arguments.phase == "application":
            if not arguments.run or arguments.installer_run:
                raise SigningError("Für --phase application genau --run <Bau-Lauf> angeben.")
            sign_application(run_id=arguments.run, **common)
        elif arguments.phase == "installer":
            if not arguments.installer_run or arguments.run:
                raise SigningError("Für --phase installer genau --installer-run <Lauf> angeben.")
            sign_installer(
                installer_run_id=arguments.installer_run,
                evidence=arguments.release_evidence,
                **common,
            )
        else:
            raise SigningError(
                "Zuerst --phase application wählen; nach dem CI-Installerbau --phase installer."
            )
    except SigningError as problem:
        print(problem)
        return 1
    except OSError, UnicodeError, zipfile.BadZipFile, subprocess.TimeoutExpired:
        print(
            "Die Signierdateien ließen sich nicht vollständig lesen oder ablegen. "
            "Eingangsarchiv, freien Speicher und Schreibrechte prüfen, dann erneut starten."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
