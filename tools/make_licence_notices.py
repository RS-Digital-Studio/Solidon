"""Erzeugt die vollständige Drittanbieter-Lizenzbeilage.

Die paketbezogenen Originaltexte liegen eingecheckt unter
``app/core/knowledge/data/third_party_licenses``. Das Werkzeug setzt sie in
der festen Reihenfolge des Manifests zusammen; dadurch hängt das Ergebnis
weder vom Betriebssystem noch vom Inhalt einer lokalen Python-Umgebung ab.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
DATA_DIR: Final = ROOT / "app" / "core" / "knowledge" / "data"
SOURCE_DIR: Final = DATA_DIR / "third_party_licenses"
MANIFEST_FILE: Final = DATA_DIR / "third_party_licenses.toml"
NOTICE_FILE: Final = ROOT / "THIRD-PARTY-NOTICES.md"


@dataclass(frozen=True, slots=True)
class PackageNotice:
    """Ein Paket und seine unveränderten Lizenz- oder Hinweisdateien."""

    name: str
    version: str
    licence: str
    files: tuple[str, ...]


def load_manifest() -> tuple[PackageNotice, ...]:
    """Liest und prüft das eingecheckte Notice-Manifest."""
    with MANIFEST_FILE.open("rb") as stream:
        data = tomllib.load(stream)
    if data.get("format") != 1:
        raise ValueError(f"Unbekanntes Notice-Format in {MANIFEST_FILE}")
    packages = tuple(
        PackageNotice(
            name=str(entry["name"]),
            version=str(entry["version"]),
            licence=str(entry["licence"]),
            files=tuple(str(path) for path in entry["files"]),
        )
        for entry in data.get("package", ())
    )
    names = [entry.name.casefold() for entry in packages]
    if names != sorted(names) or len(names) != len(set(names)):
        raise ValueError("Pakete im Notice-Manifest müssen eindeutig und alphabetisch sein")
    return packages


def _source(path: str) -> str:
    """Liest eine Quelle innerhalb des festgelegten Datenverzeichnisses."""
    candidate = (SOURCE_DIR / path).resolve()
    if SOURCE_DIR.resolve() not in candidate.parents:
        raise ValueError(f"Notice-Pfad verlässt das Datenverzeichnis: {path}")
    text = candidate.read_text(encoding="utf-8").replace("\r\n", "\n")
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"


def render(packages: tuple[PackageNotice, ...] | None = None) -> str:
    """Setzt die Beilage bytegenau aus Manifest und Quellen zusammen."""
    entries = packages if packages is not None else load_manifest()
    lines = [
        "# Drittanbieter-Lizenzen",
        "",
        "Diese Beilage enthält die Lizenz- und Hinweistexte der Python- und",
        "nativen Laufzeitbestandteile, die mit Solidon ausgeliefert werden.",
        "Sie wird deterministisch mit `python tools/make_licence_notices.py`",
        "aus den eingecheckten Originaltexten erzeugt.",
        "",
        "| Paket | Version | Lizenz |",
        "|---|---|---|",
    ]
    for entry in entries:
        lines.append(f"| {entry.name} | {entry.version} | {entry.licence} |")
    lines.extend(("", "---", ""))
    for entry in entries:
        lines.extend((f"## {entry.name} {entry.version}", "", f"Lizenz: {entry.licence}", ""))
        for path in entry.files:
            text = _source(path)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            lines.extend(
                (
                    f"### {Path(path).name}",
                    "",
                    f"Quelle im Paketdatensatz: `{path}` · SHA-256: `{digest}`",
                    "",
                    "```text",
                    text.rstrip(),
                    "```",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def write_notice(*, check: bool = False) -> bool:
    """Schreibt die Beilage oder prüft, dass sie unverändert erzeugbar ist."""
    expected = render()
    if check:
        try:
            actual = NOTICE_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
        except OSError:
            return False
        return actual == expected
    NOTICE_FILE.write_text(expected, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    """Führt Erzeugung oder Driftprüfung aus."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="nichts schreiben und bei einer veralteten Beilage ungleich null enden",
    )
    arguments = parser.parse_args(argv)
    if not write_notice(check=arguments.check):
        print(
            "THIRD-PARTY-NOTICES.md ist nicht aus den eingecheckten Quellen erzeugt. "
            "Bitte python tools/make_licence_notices.py ausführen.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
