"""Erhöht die Version an den zwei Stellen, die sie tragen — und zieht die drei
abgeleiteten nach (Bauplan §37.1).

    python tools/bump_version.py           # 0.1.1 → 0.1.2, der Normalfall
    python tools/bump_version.py --minor   # 0.1.1 → 0.2.0
    python tools/bump_version.py --major   # 0.1.1 → 1.0.0
    python tools/bump_version.py --zeigen  # nur sagen, was herauskäme

**Die letzte Stelle steigt mit jedem ausgelieferten Bau um eins.** Das ist die
Zählregel aus ``app/branding.py``, und sie hat einen Grund: Zwei Pakete mit
derselben Nummer sind zwei Pakete, die niemand auseinanderhalten kann — nicht
der Nutzer im Über-Dialog, nicht der Update-Hinweis, nicht der Support vor
einem Fehlerbericht. Die vorderen Stellen bewegen sich nur bei einer größeren
Änderung, und das ist eine Entscheidung; deshalb stehen sie hinter einem
Schalter und nicht in der Vorgabe.

Die Zahl steht an **zwei** Orten: ``APP_VERSION`` liest der Über-Dialog, jede
Projektdatei, das 3MF, der Fehlerbericht und der Update-Vergleich;
``pyproject.toml`` lesen die Paketmetadaten und alles, was pip daraus macht.
Laufen sie auseinander, nennt ein Paket eine andere Version als das Fenster
darin, und keines von beiden ist kaputt — niemand merkt es.
``tests/test_toolchain.py`` hält sie zusammen, dieses Werkzeug bewegt sie
gemeinsam.

**Und drei weitere Dateien leiten sie ab** — die Paketmanifeste für Linux und
macOS. Sie werden nicht hier gesetzt, sondern von ihren eigenen Werkzeugen neu
geschrieben (:data:`DERIVED`), damit die Vorlage an einer Stelle bleibt. Am
23.08.2026 standen sie nach einer Erhöhung noch auf der alten Nummer, weil
dieses Werkzeug sie nicht kannte: ein Paket, dessen Anwendung 0.1.3 ist und
dessen Installationsdatei 0.1.2 sagt. ``tests/test_packaging.py`` hat es
gefangen.

**Was hier nicht passiert:** ``website/version.json`` bleibt unberührt. Sie
sagt, welche Version *veröffentlicht* ist, und das ist erst wahr, wenn die
Pakete oben liegen — sie wird zuletzt hochgeladen, nicht zuerst geschrieben.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Dieselbe Zeile wie in tools/make_download.py, aus demselben Grund: Die
# Windows-Konsole steht auf cp1252, und ein Pfeil zwischen zwei Versionen
# beendet das Werkzeug sonst mit einem UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
BRANDING = ROOT / "app" / "branding.py"
PROJECT = ROOT / "pyproject.toml"

#: Was die Version **ableitet**, statt sie zu tragen — je Werkzeug die Dateien,
#: die es schreibt.
#:
#: Diese drei standen am 23.08.2026 noch auf 0.1.2, während `branding.py` schon
#: 0.1.3 sagte. `tests/test_packaging.py` hat es gefangen, und sein Docstring
#: nennt den Grund: *eine Versionsnummer im Manifest, die nicht zu
#: `app/branding.py` passt, ergibt ein Paket, das außen neu aussieht und innen
#: alt ist.* Der Test schlug **genau** in dem Lauf an, für den er gebaut wurde.
#:
#: **Gerufen statt genannt.** Ein Hinweis im Ausgabetext wäre die billigere
#: Lösung und die schlechtere: Die Notiz zu diesem Werkzeug sagte „beide
#: Stellen", und es waren drei. Wer die Version an einer Stelle erhöht, soll
#: nicht danach eine Liste abarbeiten müssen.
#:
#: Beide Werkzeuge schreiben mit ``--files`` nur Text und brauchen weder Qt noch
#: Linux noch einen Mac.
DERIVED: dict[str, tuple[str, ...]] = {
    "make_linux_packages.py": (
        "packaging/de.rsdigital.solidon3d.metainfo.xml",
        "packaging/install.sh",
    ),
    "make_macos_package.py": ("packaging/macos-distribution.xml",),
    # **Die vierte, und sie ist zweimal an einem Tag vergessen worden.** Der
    # Kopf der Lizenzbeilage nennt die Fassung, für die sie erzeugt wurde. Am
    # 03.09.2026 stand dort nach dem Bump auf 0.3.1 noch 0.3.0 — der Tag-Lauf
    # war rot, und zwar nur auf Windows, weil `test_licence_notices` sich auf
    # den anderen Plattformen überspringt. Von Hand nachgezogen, und beim
    # nächsten Bump lief es sofort wieder hinein.
    #
    # Der Lauf liest die **installierten** Wheels, erzeugt die Datei also für
    # die Plattform, auf der gebumpt wird. Das ist richtig so: Der Test prüft
    # sie nur dort, und das Kundenpaket bekommt seine Beilage ohnehin je
    # Plattform aus der Endartefakt-SBOM (`build.yml`).
    "make_licence_notices.py": ("THIRD-PARTY-NOTICES.md",),
}

#: Die Zeile in ``branding.py``, die die Version trägt.
BRANDING_LINE = re.compile(r'^(APP_VERSION: Final = ")(\d+\.\d+\.\d+)(")$', re.MULTILINE)

#: Und die in ``pyproject.toml`` — die **erste** ``version =``-Zeile. Weiter
#: unten stehen Versionsangaben von Abhängigkeiten, und die gehen uns nichts an.
PROJECT_LINE = re.compile(r'^(version = ")(\d+\.\d+\.\d+)(")$', re.MULTILINE)


def current() -> str:
    """Die Version, wie sie jetzt dasteht — aus ``branding.py``."""
    found = BRANDING_LINE.search(BRANDING.read_text(encoding="utf-8"))
    if found is None:
        raise SystemExit(
            "In app/branding.py steht keine Zeile 'APP_VERSION: Final = \"x.y.z\"' mehr. "
            "Ohne sie weiß dieses Werkzeug nicht, was es erhöhen soll."
        )
    return found.group(2)


def raised(version: str, step: str) -> str:
    """Die nächste Version. Eine erhöhte Stelle setzt die dahinter auf null."""
    major, minor, patch = (int(part) for part in version.split("."))
    if step == "major":
        return f"{major + 1}.0.0"
    if step == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write(path: Path, pattern: re.Pattern[str], version: str) -> None:
    """Setzt die Version in einer Datei — genau einmal.

    ``count=1`` ist keine Vorsicht, sondern die Regel: In ``pyproject.toml``
    stehen weiter unten die Versionen der Abhängigkeiten, und ein Ersetzen
    über die ganze Datei träfe sie mit.
    """
    text = path.read_text(encoding="utf-8")
    updated, hits = pattern.subn(rf"\g<1>{version}\g<3>", text, count=1)
    if hits != 1:
        raise SystemExit(f"{path.name}: die Versionszeile ist nicht (mehr) zu finden.")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    place = parser.add_mutually_exclusive_group()
    place.add_argument("--minor", action="store_true", help="mittlere Stelle statt der letzten")
    place.add_argument("--major", action="store_true", help="vordere Stelle — eine Entscheidung")
    parser.add_argument(
        "--zeigen", action="store_true", help="nur sagen, was herauskäme, und nichts schreiben"
    )
    arguments = parser.parse_args()

    step = "major" if arguments.major else "minor" if arguments.minor else "patch"
    was = current()
    wird = raised(was, step)

    if arguments.zeigen:
        print(f"{was} → {wird}")
        return 0

    write(BRANDING, BRANDING_LINE, wird)
    write(PROJECT, PROJECT_LINE, wird)
    print(f"Version: {was} → {wird}")
    print("  app/branding.py")
    print("  pyproject.toml")

    for tool_name in DERIVED:
        subprocess.run(
            [sys.executable, str(TOOLS / tool_name), "--files"], check=True, capture_output=True
        )
        print(f"  über {tool_name}:")
        for path in DERIVED[tool_name]:
            print(f"    {path}")

    print(
        "\nwebsite/version.json bleibt, wie sie ist: Sie sagt, was veröffentlicht\n"
        "ist, und das stimmt erst, wenn die Pakete oben liegen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
