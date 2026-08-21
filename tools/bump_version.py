"""Erhöht die Fassung an beiden Stellen, die sie tragen (Bauplan §37.1).

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
Laufen sie auseinander, nennt ein Paket eine andere Fassung als das Fenster
darin, und keines von beiden ist kaputt — niemand merkt es.
``tests/test_toolchain.py`` hält sie zusammen, dieses Werkzeug bewegt sie
gemeinsam.

**Was hier nicht passiert:** ``website/version.json`` bleibt unberührt. Sie
sagt, welche Fassung *veröffentlicht* ist, und das ist erst wahr, wenn die
Pakete oben liegen — sie wird zuletzt hochgeladen, nicht zuerst geschrieben.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Dieselbe Zeile wie in tools/make_download.py, aus demselben Grund: Die
# Windows-Konsole steht auf cp1252, und ein Pfeil zwischen zwei Fassungen
# beendet das Werkzeug sonst mit einem UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BRANDING = ROOT / "app" / "branding.py"
PROJECT = ROOT / "pyproject.toml"

#: Die Zeile in ``branding.py``, die die Fassung trägt.
BRANDING_LINE = re.compile(r'^(APP_VERSION: Final = ")(\d+\.\d+\.\d+)(")$', re.MULTILINE)

#: Und die in ``pyproject.toml`` — die **erste** ``version =``-Zeile. Weiter
#: unten stehen Fassungsangaben von Abhängigkeiten, und die gehen uns nichts an.
PROJECT_LINE = re.compile(r'^(version = ")(\d+\.\d+\.\d+)(")$', re.MULTILINE)


def current() -> str:
    """Die Fassung, wie sie jetzt dasteht — aus ``branding.py``."""
    found = BRANDING_LINE.search(BRANDING.read_text(encoding="utf-8"))
    if found is None:
        raise SystemExit(
            "In app/branding.py steht keine Zeile 'APP_VERSION: Final = \"x.y.z\"' mehr. "
            "Ohne sie weiß dieses Werkzeug nicht, was es erhöhen soll."
        )
    return found.group(2)


def raised(version: str, step: str) -> str:
    """Die nächste Fassung. Eine erhöhte Stelle setzt die dahinter auf null."""
    major, minor, patch = (int(part) for part in version.split("."))
    if step == "major":
        return f"{major + 1}.0.0"
    if step == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write(path: Path, pattern: re.Pattern[str], version: str) -> None:
    """Setzt die Fassung in einer Datei — genau einmal.

    ``count=1`` ist keine Vorsicht, sondern die Regel: In ``pyproject.toml``
    stehen weiter unten die Fassungen der Abhängigkeiten, und ein Ersetzen
    über die ganze Datei träfe sie mit.
    """
    text = path.read_text(encoding="utf-8")
    updated, hits = pattern.subn(rf"\g<1>{version}\g<3>", text, count=1)
    if hits != 1:
        raise SystemExit(f"{path.name}: die Fassungszeile ist nicht (mehr) zu finden.")
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
    print(f"Fassung: {was} → {wird}")
    print("  app/branding.py")
    print("  pyproject.toml")
    print(
        "\nwebsite/version.json bleibt, wie sie ist: Sie sagt, was veröffentlicht\n"
        "ist, und das stimmt erst, wenn die Pakete oben liegen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
