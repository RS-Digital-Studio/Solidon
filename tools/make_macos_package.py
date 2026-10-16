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
import copy
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import branding
from app.branding import APP_ID, APP_NAME, APP_VENDOR, MACOS_MINIMUM, WEBSITE_URL
from tools import asset_rights

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

#: Wie Apples Installer mit einem vorhandenen Bundle derselben Kennung umgeht
#: (``pkgbuild``, „COMPONENT PROPERTY LIST“). Gilt für das Bundle und jedes
#: eingebettete (Qt- und Python-Frameworks).
#:
#: ``BundleIsRelocatable`` aus: Sonst sucht der Installer eine Kopie mit
#: derselben Kennung irgendwo auf der Platte und aktualisiert **diese** —
#: ``/Applications`` behält die alte Version, und der Kunde startet sie weiter.
#: ``BundleIsVersionChecked`` aus: Sonst überspringt der Installer das Bundle
#: still, wenn am Ziel eine höhere Nummer liegt, und meldet trotzdem Erfolg —
#: dieselbe Fehlerklasse; wer bewusst zur vorigen Version zurückgeht, bekommt
#: sie. ``BundleOverwriteAction`` ``upgrade``: Das neue Bundle ersetzt das alte
#: ganz; Dateien, die die neue Version nicht mehr hat, blieben sonst liegen und
#: brächen das Siegel der Signatur.
COMPONENT_SETTINGS: dict[str, Any] = {
    "BundleIsRelocatable": False,
    "BundleIsVersionChecked": False,
    "BundleOverwriteAction": "upgrade",
}


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
        f"    <title>{APP_NAME} {branding.APP_VERSION}</title>\n"
        f"    <organization>{APP_ID.rsplit('.', 1)[0]}</organization>\n"
        f'    <license file="eula.txt" mime-type="text/plain" />\n'
        f'    <conclusion file="conclusion.txt" mime-type="text/plain" />\n'
        '    <options customize="allow" require-scripts="false"'
        ' hostArchitectures="' + architecture + '" />\n'
        '    <domains enable_anywhere="true" enable_currentUserHome="true"'
        ' enable_localSystem="true" />\n'
        # Das Volume trägt dieselbe Systemversion wie die Plist (MACOS_MINIMUM).
        "    <volume-check>\n"
        f'        <allowed-os-versions><os-version min="{MACOS_MINIMUM}" /></allowed-os-versions>\n'
        "    </volume-check>\n"
        f'    <pkg-ref id="{APP_ID}" version="{branding.APP_VERSION}">component.pkg</pkg-ref>\n'
        "    <choices-outline>\n"
        f'        <line choice="{APP_ID}" />\n'
        "    </choices-outline>\n"
        f'    <choice id="{APP_ID}" title="{APP_NAME}" visible="true"'
        f' description="{APP_NAME} {branding.APP_VERSION} — {APP_VENDOR}">\n'
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


#: Wo Paketverwalter auf einem Mac Bibliotheken ablegen: Homebrew auf Intel
#: und Apple Silicon, MacPorts. Was PyInstaller von dort einsammelt, stammt vom
#: Runner, nicht aus einem Rad — Fassung und Lizenz hängen am Runner-Image.
FOREIGN_PREFIXES: tuple[str, ...] = ("/usr/local/", "/opt/homebrew/", "/opt/local/")


def _library_stem(name: str) -> str:
    """``libfreetype.6.dylib`` → ``libfreetype``: der Name ohne Fassung und Endung."""
    return name.replace("\\", "/").rsplit("/", 1)[-1].split(".", 1)[0]


def trim_foreign_macos_binaries(
    binaries: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Nimmt Bibliotheken des Runners aus PyInstallers Binaries-Liste.

    Ein Eintrag ist ``(zielname, quellpfad, typ)``. PyInstallers ctypes-Analyse
    findet über ``ctypes.util.find_library`` auch, was ein Paketverwalter unter
    ``/usr/local/lib`` abgelegt hat (so kam Homebrews ``libfreetype.dylib`` ins
    Intel-Paket 0.6.0, obwohl freetype-py seine eigene mitbringt und zuerst
    lädt). Bringt ein Rad dieselbe Bibliothek mit — gleicher Name ohne Fassung
    —, fällt die Runner-Kopie weg; sonst hält der Bau an, denn eine solche
    Datei hätte weder Besitzer noch belegte Fassung und wiche je Runner-Image
    ab.
    """
    foreign = [entry for entry in binaries if str(entry[1]).startswith(FOREIGN_PREFIXES)]
    if not foreign:
        return list(binaries)
    wheels = {
        _library_stem(entry[0])
        for entry in binaries
        if entry not in foreign and "site-packages" in Path(str(entry[1])).parts
    }
    unowned = [entry for entry in foreign if _library_stem(entry[0]) not in wheels]
    if unowned:
        listed = "\n".join(f"  {target} ← {source}" for target, source, _kind in unowned)
        raise ValueError(
            "Der macOS-Bau sammelte Bibliotheken eines Paketverwalters des Runners "
            f"ein, die kein Rad mitbringt:\n{listed}\n"
            "Die Abhängigkeit über ein Rad beziehen oder in der .spec ausschließen."
        )
    for target, source, _kind in foreign:
        print(f"Runner-Bibliothek ausgelassen, ein Rad bringt sie mit: {target} ← {source}")
    return [entry for entry in binaries if entry not in foreign]


def component_settings(analysed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Komponentenliste aus ``pkgbuild --analyze``, nicht umziehbar gemacht.

    Die Nutzlastwurzel trägt genau das Bundle; findet die Analyse dort etwas
    anderes, ist die Wurzel falsch gebaut, und das Paket installierte es mit.
    """
    paths = [entry.get("RootRelativeBundlePath") for entry in analysed]
    if paths != [f"{APP_NAME}.app"]:
        raise ValueError(
            f"pkgbuild fand in der Nutzlastwurzel {paths!r}, erwartet war nur "
            f"{APP_NAME}.app — die Wurzel neu anlegen."
        )
    settled = copy.deepcopy(analysed)
    pending = list(settled)
    while pending:
        entry = pending.pop()
        entry.update(COMPONENT_SETTINGS)
        pending.extend(entry.get("ChildBundles", []))
    return settled


def analyse_command(root: Path, plist: Path) -> list[str]:
    """``pkgbuild`` liest die Bundles der Wurzel in eine Komponentenliste."""
    return ["pkgbuild", "--analyze", "--root", str(root), str(plist)]


def component_command(root: Path, plist: Path, component: Path) -> list[str]:
    """``pkgbuild`` schnürt die Wurzel mit der bearbeiteten Komponentenliste."""
    return [
        "pkgbuild",
        "--root",
        str(root),
        "--component-plist",
        str(plist),
        "--install-location",
        INSTALL_LOCATION,
        "--identifier",
        APP_ID,
        "--version",
        branding.APP_VERSION,
        str(component),
    ]


def package_info_problems(text: str) -> list[str]:
    """Was an einer ``PackageInfo`` den Kunden die falsche Kopie starten ließe.

    ``<relocate>`` heißt, der Installer aktualisiert eine Kopie gleicher Kennung
    dort, wo sie liegt; ``<bundle-version>`` heißt, er überspringt ein Bundle,
    wenn am Ziel eine höhere Nummer liegt. Dazu muss das Bundle mit seiner
    Kennung unter ``/Applications`` stehen.
    """
    root = ET.fromstring(text)
    problems = []
    for section in ("relocate", "bundle-version"):
        for element in root.iter(section):
            for bundle in element.iter("bundle"):
                problems.append(f"<{section}> nennt {bundle.get('id')}")
    if root.get("install-location") != INSTALL_LOCATION:
        problems.append(f"install-location ist {root.get('install-location')!r}")
    top = [bundle for bundle in root.findall("bundle") if bundle.get("id") == APP_ID]
    if [bundle.get("path") for bundle in top] != [f"./{APP_NAME}.app"]:
        problems.append(f"das Bundle {APP_ID} steht nicht als ./{APP_NAME}.app in der Nutzlast")
    return problems


def check_package(package: Path) -> int:
    """Liest jede ``PackageInfo`` aus dem fertigen ``.pkg`` (``pkgutil --expand``).

    Läuft nach dem Bau und in der Releaseakte am signierten Paket; nur auf
    macOS, weil ``pkgutil`` dort liegt.
    """
    with tempfile.TemporaryDirectory() as scratch:
        expanded = Path(scratch) / "expanded"
        completed = subprocess.run(
            ["pkgutil", "--expand", str(package), str(expanded)], check=False
        )
        if completed.returncode:
            print("pkgutil --expand ist gescheitert — die Ausgabe darüber sagt, woran.")
            return completed.returncode
        infos = sorted(expanded.rglob("PackageInfo"))
        if not infos:
            print(f"{package.name} trägt keine PackageInfo — kein Komponentenpaket darin.")
            return 1
        problems = [
            f"{info.relative_to(expanded)}: {problem}"
            for info in infos
            for problem in package_info_problems(info.read_text(encoding="utf-8"))
        ]
    for problem in problems:
        print(f"Paketfehler: {problem}")
    if problems:
        print(
            "Das Paket würde eine Kopie gleicher Kennung irgendwo auf der Platte "
            "aktualisieren oder überspringen — Komponentenliste in "
            "tools/make_macos_package.py prüfen."
        )
        return 1
    print(f"{package.name}: nicht umziehbar, ohne Versionssperre, nach {INSTALL_LOCATION}.")
    return 0


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
    try:
        asset_rights.require_customer_artifact_cleared(BUNDLE, "darwin")
    except RuntimeError as problem:
        print(problem)
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

    # Eine Wurzel mit nur dem Bundle: ``pkgbuild --component`` nähme keine
    # Komponentenliste, und ohne sie wäre das Paket umziehbar
    # (``COMPONENT_SETTINGS``). ``ditto`` behält Symlinks und erweiterte
    # Attribute — an ``THIRD-PARTY-NOTICES.md`` hängt dort die Signatur.
    payload = scratch / "root"
    payload.mkdir()
    completed = subprocess.run(["ditto", str(BUNDLE), str(payload / BUNDLE.name)], check=False)
    if completed.returncode:
        print("ditto ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode
    plist = scratch / "component.plist"
    completed = subprocess.run(analyse_command(payload, plist), check=False)
    if completed.returncode:
        print("pkgbuild --analyze ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode
    try:
        settled = component_settings(plistlib.loads(plist.read_bytes()))
    except ValueError as problem:
        print(problem)
        return 1
    plist.write_bytes(plistlib.dumps(settled))

    component = scratch / "component.pkg"
    completed = subprocess.run(component_command(payload, plist, component), check=False)
    if completed.returncode:
        print("pkgbuild ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode
    shutil.rmtree(payload)

    target = OUTPUT_DIR / f"{APP_NAME}-{branding.APP_VERSION}-macos-{architecture}.pkg"
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
    if check_package(target):
        return 1

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
    parser.add_argument(
        "--check",
        type=Path,
        metavar="PAKET",
        help="nur prüfen: ist das fertige .pkg nicht umziehbar? (nur auf macOS)",
    )
    arguments = parser.parse_args()
    if arguments.check:
        return check_package(arguments.check)
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
