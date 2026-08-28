"""Baut das macOS-Installationspaket aus dem Bundle (Bauplan §37.2).

    python tools/make_macos_package.py            # .pkg bauen (nur auf macOS)
    python tools/make_macos_package.py --files    # nur die Beschreibung schreiben

**Warum ein ``.pkg`` und nicht nur das Archiv.** Bis hierher reiste macOS als
``.zip`` mit dem Bundle darin: herunterladen, auspacken, selbst nach
``/Programme`` ziehen. Das ist der Mac-Weg für kleine Programme und für dieses
hier der falsche — es gibt nichts zu lesen und nichts zu wählen. Ein
Installationspaket zeigt beides: den Lizenzvertrag mit einem Knopf
„Akzeptieren", und die Seite, auf der sich zwischen „für alle Benutzer",
„nur für mich" und einem anderen Volume entscheiden lässt. Dieselben zwei
Fragen, die der Windows-Installer stellt.

Das ``.zip`` bleibt daneben bestehen: es trägt die Signatur des Bundles
unverändert und ist der kürzere Weg für alle, die ihn kennen.

Gebaut wird mit den Werkzeugen, die macOS selbst mitbringt — ``pkgbuild``
schnürt die Nutzlast, ``productbuild`` legt Lizenz, Sprachen und die
Zielwahl darum. Beide gehören zu den Command Line Tools und werden nicht
mitgeliefert (§36).

Wie beim Windows-Installer und den Linux-Paketen trägt keine Datei eigene
Werte: Name, Version, Hersteller und Kennung stehen in :mod:`app.branding`.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import APP_ID, APP_NAME, APP_VENDOR, APP_VERSION, WEBSITE_URL

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "dist"
PACKAGING = ROOT / "packaging"
BUNDLE = OUTPUT_DIR / f"{APP_NAME}.app"

#: Die Beschreibung, die ``productbuild`` liest. Erzeugt, nicht gepflegt.
DISTRIBUTION_FILE = PACKAGING / "macos-distribution.xml"

#: Wohin das Bundle geht, wenn der Nutzer nichts anderes wählt.
INSTALL_LOCATION = "/Applications"

#: Der Lizenzvertrag, den der Installer auf seiner zweiten Seite zeigt.
#: Dieselbe Textversion wie beim Windows-Installer — ``tools/make_legal.py``
#: legt sie aus ``EULA.md`` an.
LICENCE_FILE = PACKAGING / "eula.txt"


def distribution(architecture: str) -> str:
    """Die Beschreibung des Installationsablaufs.

    Drei Dinge stehen hier, und jedes ist eine Seite im Installationsfenster:

    ``license``
        Der Lizenzvertrag mit „Akzeptieren" oder „Ablehnen". Ohne Zustimmung
        geht es nicht weiter — das ist der Sinn der Seite, und es ist derselbe
        Text, den der Windows-Installer zeigt.

    ``domains``
        Die Zielwahl. ``enable_localSystem`` ist „für alle Benutzer dieses
        Computers" (braucht ein Kennwort), ``enable_currentUserHome`` ist
        „nur für mich" (braucht keines), ``enable_anywhere`` erlaubt ein
        anderes Volume — die externe Platte, wenn die interne voll ist.

    ``options customize``
        Erlaubt die Seite „Anpassen". Bei einer einzigen Komponente ist dort
        nichts abzuwählen; sie steht offen, weil sie zeigt, was installiert
        wird und wie viel Platz es braucht.

    ``hostArchitectures`` hält ein auf Apple Silicon gebautes Paket von einem
    Intel-Mac fern. Ohne die Zeile installiert es sich dort anstandslos und
    startet dann nicht — der Fehler fiele erst nach dem Neustart des Rechners
    auf, an dem er nicht liegt.
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- Erzeugt von tools/make_macos_package.py — Werte aus app/branding.py. -->\n"
        '<installer-gui-script minSpecVersion="2">\n'
        f"    <title>{APP_NAME} {APP_VERSION}</title>\n"
        f"    <organization>{APP_ID.rsplit('.', 1)[0]}</organization>\n"
        f'    <license file="eula.txt" mime-type="text/plain" />\n'
        f'    <conclusion file="conclusion.txt" mime-type="text/plain" />\n'
        '    <options customize="allow" require-scripts="false"'
        ' hostArchitectures="' + architecture + '" />\n'
        '    <domains enable_anywhere="true" enable_currentUserHome="true"'
        ' enable_localSystem="true" />\n'
        # Das Volume muss die Systemversion tragen, die auch die Plist nennt
        # (LSMinimumSystemVersion in packaging/solidon3d.spec).
        "    <volume-check>\n"
        '        <allowed-os-versions><os-version min="12.0" /></allowed-os-versions>\n'
        "    </volume-check>\n"
        f'    <pkg-ref id="{APP_ID}" version="{APP_VERSION}">component.pkg</pkg-ref>\n'
        "    <choices-outline>\n"
        f'        <line choice="{APP_ID}" />\n'
        "    </choices-outline>\n"
        f'    <choice id="{APP_ID}" title="{APP_NAME}" visible="true"'
        f' description="{APP_NAME} {APP_VERSION} — {APP_VENDOR}">\n'
        f'        <pkg-ref id="{APP_ID}" />\n'
        "    </choice>\n"
        "</installer-gui-script>\n"
    )


def conclusion(notarized: bool = False) -> str:
    """Der Text auf der letzten Seite — wo die Anwendung liegt und was folgt.

    Ohne Notarisierung nennt er den gesperrten Erststart ausdrücklich:
    Gatekeeper lässt das Paket nicht per Doppelklick starten, und wer das nicht
    weiß, hält ein frisch installiertes Programm für kaputt. Im notarisierten
    Paket fällt der Absatz beim Bau weg; ein Fehlschlag danach hält die CI an,
    sodass nie ein Paket mit der falschen Zusage ausgeliefert wird.
    """
    paragraphs = [
        f"{APP_NAME} ist installiert.\n\n"
        "Sie finden die Anwendung im Ordner „Programme“ (oder dort, wohin Sie sie "
        "installiert haben)."
    ]
    if notarized:
        paragraphs.append(
            "Das Paket wurde von Apple geprüft. Für den ersten Start ist keine "
            "besondere Freigabe erforderlich."
        )
    else:
        paragraphs.append(
            "Beim ersten Start meldet macOS, dass die Anwendung von einem nicht "
            "verifizierten Entwickler stammt. Im Hinweis „Fertig“ wählen und die "
            "Anwendung dann in den Systemeinstellungen unter „Datenschutz & "
            "Sicherheit“ mit „Trotzdem öffnen“ freigeben. Danach startet sie wie "
            "jede andere."
        )
    paragraphs.append(f"Handbuch, Hilfe und Kontakt: {WEBSITE_URL}")
    return "\n\n".join(paragraphs) + "\n"


def write_files(architecture: str, *, notarized: bool = False) -> list[Path]:
    """Schreibt die Beschreibung und den Schlusstext."""
    PACKAGING.mkdir(parents=True, exist_ok=True)
    DISTRIBUTION_FILE.write_text(distribution(architecture), encoding="utf-8", newline="\n")
    conclusion_file = PACKAGING / "macos-conclusion.txt"
    conclusion_file.write_text(conclusion(notarized), encoding="utf-8", newline="\n")
    return [DISTRIBUTION_FILE, conclusion_file]


def build(architecture: str, identity: str = "") -> int:
    """Schnürt Nutzlast und Installationsfenster zu einer ``.pkg``.

    ``identity`` ist der Name eines „Developer ID Installer"-Zertifikats —
    ein anderes als das, mit dem das Bundle signiert wird. Fehlt es, entsteht
    ein unsigniertes Paket; das ist kein Fehlschlag, sondern der Stand vor dem
    Apple-Konto, und der Schlusstext oben sagt es dem Nutzer.
    """
    if not BUNDLE.is_dir():
        print(f"Kein Bundle unter {BUNDLE} — zuerst: pyinstaller packaging/solidon3d.spec")
        return 1
    if not LICENCE_FILE.is_file():
        print("packaging/eula.txt fehlt — zuerst: python tools/make_legal.py")
        return 1

    scratch = OUTPUT_DIR / "macos-pkg"
    if scratch.exists():
        shutil.rmtree(scratch)
    resources = scratch / "Resources"
    resources.mkdir(parents=True)

    # ``productbuild`` liest Lizenz und Schlusstext aus dem Ressourcenordner,
    # und zwar unter genau den Namen, die die Beschreibung nennt.
    shutil.copyfile(LICENCE_FILE, resources / "eula.txt")
    shutil.copyfile(PACKAGING / "macos-conclusion.txt", resources / "conclusion.txt")

    component = scratch / "component.pkg"
    completed = subprocess.run(
        [
            "pkgbuild",
            "--component",
            str(BUNDLE),
            "--install-location",
            INSTALL_LOCATION,
            "--identifier",
            APP_ID,
            "--version",
            APP_VERSION,
            str(component),
        ],
        check=False,
    )
    if completed.returncode:
        print("pkgbuild ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode

    target = OUTPUT_DIR / f"{APP_NAME}-{APP_VERSION}-macos-{architecture}.pkg"
    command = [
        "productbuild",
        "--distribution",
        str(DISTRIBUTION_FILE),
        "--resources",
        str(resources),
        "--package-path",
        str(scratch),
    ]
    if identity:
        command += ["--sign", identity]
    command.append(str(target))
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        print("productbuild ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode

    print(f"Installationspaket → {target.relative_to(ROOT)}")
    if not identity:
        print("Unsigniert gebaut — der Schlusstext des Installers erklärt den ersten Start.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--files",
        action="store_true",
        help="nur die Beschreibung schreiben, nichts bauen (läuft überall)",
    )
    parser.add_argument(
        "--sign",
        default="",
        metavar="IDENTITÄT",
        help='Name eines "Developer ID Installer"-Zertifikats; ohne ihn unsigniert',
    )
    parser.add_argument(
        "--notarized",
        action="store_true",
        help="Schlusstext für ein Paket, das die CI anschließend notarisiert",
    )
    arguments = parser.parse_args()
    if arguments.notarized and not arguments.sign:
        print("Notarisierung setzt ein signiertes Installationspaket voraus — --sign fehlt.")
        return 2

    # Die Architektur des laufenden Rechners — auf einem fremden System die
    # von Apple Silicon, damit die erzeugte Beschreibung überall gleich
    # aussieht und der Test sie prüfen kann.
    architecture = platform.machine() if sys.platform == "darwin" else "arm64"
    if architecture == "AMD64":  # ein Windows-Rechner nennt sich so
        architecture = "x86_64"

    for path in write_files(architecture, notarized=arguments.notarized):
        print(f"geschrieben: {path.relative_to(ROOT)}")
    if arguments.files:
        return 0

    if sys.platform != "darwin":
        print(f"Gebaut wird auf macOS, hier läuft {sys.platform} — nur die Datei ist entstanden.")
        return 0
    return build(architecture, arguments.sign)


if __name__ == "__main__":
    raise SystemExit(main())
