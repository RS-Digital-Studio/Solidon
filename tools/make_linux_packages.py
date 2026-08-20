"""Baut die beiden Linux-Formate aus dem PyInstaller-Ordner (Bauplan §37.2).

    python tools/make_linux_packages.py            # beide, soweit möglich
    python tools/make_linux_packages.py --files    # nur die Beschreibungen

Wie beim Windows-Installer trägt keine Paketierdatei eigene Werte: Name,
Version, Hersteller und Kennung liegen in :mod:`app.branding` fest, und dieses
Werkzeug schreibt sie von dort in die Beschreibungen. Eine zweite Stelle mit
einer Versionsnummer ist eine, die veraltet — beim Installer stand genau dieser
Satz, und er gilt hier dreifach: `.desktop`, AppImage und Flatpak wollen sie
alle.

**Die Beschreibungen entstehen auch ohne die Werkzeuge.** ``--files`` schreibt
`.desktop` und Flatpak-Manifest und hört auf; das läuft auf jeder Plattform und
ist der Teil, den ``tests/test_packaging.py`` prüft. Der Bau selbst braucht
Linux und je ein externes Programm — ``appimagetool`` und ``flatpak-builder``
—, und die liefert Solidon nicht mit (§36: kein Werkzeug im Paket, das man
extern aufrufen kann).

Warum zwei Formate: AppImage ist eine Datei, die überall läuft, und der kürzeste
Weg zu „ausprobieren". Flatpak ist der Weg in die Software-Verwaltung einer
Distribution, mit Aktualisierung und Sandbox. Wer nur eines wählt, verliert
entweder die Neugierigen oder die Dauernutzer.
"""

from __future__ import annotations

import argparse
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
    DISTRIBUTION_NAME,
    WEBSITE_URL,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "dist" / APP_NAME
OUTPUT_DIR = ROOT / "dist"
PACKAGING = ROOT / "packaging"

#: Die Beschreibungen, die dieses Werkzeug schreibt. Alle drei sind erzeugt und
#: gehören nicht von Hand bearbeitet — der Test hält sie an ``app/branding``.
DESKTOP_FILE = PACKAGING / f"{DISTRIBUTION_NAME}.desktop"
FLATPAK_MANIFEST = PACKAGING / f"{APP_ID}.yml"
METAINFO_FILE = PACKAGING / f"{APP_ID}.metainfo.xml"

#: Was der Eintrag im Menü sagt. Kurz, denn die Software-Verwaltung schneidet
#: ab, und ohne Punkt am Ende — so hält es die Freedesktop-Empfehlung.
SUMMARY = "3D-Modelle konstruieren, erzeugen und druckfertig machen"

#: Die Kategorien der Freedesktop-Spezifikation, in denen ein CAD-Programm
#: gesucht wird. ``Graphics`` ist die Hauptkategorie, die beiden anderen führen
#: es in den Untermenüs der Arbeitsumgebungen.
CATEGORIES = ("Graphics", "3DGraphics", "Engineering")


def desktop_entry() -> str:
    """Der Menüeintrag, wie beide Formate ihn brauchen.

    ``StartupWMClass`` steht dabei und ist keine Formalie: Ohne sie ordnet die
    Arbeitsumgebung das Fenster nicht dem Starter zu, und in der Leiste steht
    neben dem Symbol ein zweites, namenloses.
    """
    categories = ";".join(CATEGORIES)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Comment={SUMMARY}\n"
        f"Exec={APP_NAME} %f\n"
        f"Icon={APP_ID}\n"
        f"StartupWMClass={APP_NAME}\n"
        f"Categories={categories};\n"
        "Terminal=false\n"
        # Die eigene Projektdatei, damit ein Doppelklick im Dateimanager
        # ankommt. Der Typ wird in der Flatpak-Installation mitgeliefert.
        f"MimeType=application/x-{DISTRIBUTION_NAME}-project;\n"
    )


def flatpak_manifest() -> str:
    """Das Flatpak-Manifest um den fertigen PyInstaller-Ordner.

    **Gebaut wird nicht aus den Quellen, sondern um den Bau herum.** Das ist für
    Flatpak der ungewöhnlichere Weg und hier der richtige: Die Anwendung bringt
    ihr Python und ihre Bibliotheken schon mit (dieselbe Spec wie Windows und
    macOS), und ein zweiter Bauweg wäre eine zweite Fassung, die auseinanderläuft
    — genau das, was die eine Spec verhindert.

    Die Berechtigungen sind so knapp wie möglich, und jede hat einen Grund:

    * ``--socket=wayland`` und ``--socket=fallback-x11`` — die Oberfläche.
    * ``--device=dri`` — der Viewport rechnet mit OpenGL (§18).
    * ``--filesystem=home`` — Modelle liegen beim Nutzer, und ein Dateidialog,
      der nur in einen Sandkasten sehen darf, ist kein Dateidialog. Portale
      wären der feinere Weg; sie setzen voraus, dass jeder Öffnen- und
      Speichern-Pfad darüber läuft, und das ist ein eigener Schritt.
    * ``--talk-name=org.freedesktop.secrets`` — der Schlüssel des Agenten liegt
      im Schlüsselbund (§26) und nicht in der Projektdatei.

    **Kein Netzzugang.** Ohne ihn fällt die Aktualisierungsprüfung aus und der
    Chat bleibt auf ein lokales Modell beschränkt — beides ist abschaltbar und
    ohnehin so vorgesehen, und ohne Netz gibt es kein Konto, keine Telemetrie
    und keine Frage danach. Wer den Chat gegen einen Dienst fahren will,
    bekommt die Berechtigung über die Software-Verwaltung dazu.
    """
    permissions = "\n".join(
        f"  - {entry}"
        for entry in (
            "--socket=wayland",
            "--socket=fallback-x11",
            "--share=ipc",
            "--device=dri",
            "--filesystem=home",
            "--talk-name=org.freedesktop.secrets",
        )
    )
    return (
        f"# Erzeugt von tools/make_linux_packages.py — Werte aus app/branding.py.\n"
        f"# Von Hand geänderte Zeilen verliert der nächste Lauf.\n"
        f"id: {APP_ID}\n"
        f"runtime: org.freedesktop.Platform\n"
        f"runtime-version: '24.08'\n"
        f"sdk: org.freedesktop.Sdk\n"
        f"command: {APP_NAME}\n"
        f"finish-args:\n{permissions}\n"
        f"modules:\n"
        f"  - name: {DISTRIBUTION_NAME}\n"
        f"    buildsystem: simple\n"
        f"    build-commands:\n"
        f"      - mkdir -p /app/lib/{DISTRIBUTION_NAME}\n"
        f"      - cp -r {APP_NAME}/* /app/lib/{DISTRIBUTION_NAME}/\n"
        f"      - mkdir -p /app/bin\n"
        f"      - ln -s /app/lib/{DISTRIBUTION_NAME}/{APP_NAME} /app/bin/{APP_NAME}\n"
        f"      - install -Dm644 {DESKTOP_FILE.name}"
        f" /app/share/applications/{APP_ID}.desktop\n"
        f"      - install -Dm644 icon.svg"
        f" /app/share/icons/hicolor/scalable/apps/{APP_ID}.svg\n"
        f"      - install -Dm644 {METAINFO_FILE.name}"
        f" /app/share/metainfo/{APP_ID}.metainfo.xml\n"
        f"    sources:\n"
        f"      - type: dir\n"
        f"        path: ../dist\n"
        f"      - type: file\n"
        f"        path: {DESKTOP_FILE.name}\n"
        f"      - type: file\n"
        f"        path: {METAINFO_FILE.name}\n"
        f"      - type: file\n"
        f"        path: ../app/images/icon/{DISTRIBUTION_NAME}.svg\n"
        f"        dest-filename: icon.svg\n"
    )


def metainfo() -> str:
    """Die AppStream-Beschreibung für die Software-Verwaltung.

    **Ohne sie ist das Flatpak ein Eintrag ohne Text.** Der Menüeintrag reicht
    dem Startmenü; was GNOME Software oder Discover anzeigen — Zusammenfassung,
    Beschreibung, Hersteller, Lizenz, Adresse —, steht hier. Ein Programm, das
    dort namenlos und unbeschrieben steht, wird nicht installiert.

    ``metadata_license`` ist die Lizenz *dieser Datei* und nicht die der
    Anwendung; ``project_license`` die der Anwendung. Beides zu verwechseln ist
    der häufigste Fehler in AppStream-Dateien, und er fällt erst bei der
    Aufnahme in ein Verzeichnis auf.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Erzeugt von tools/make_linux_packages.py — Werte aus app/branding.py. -->\n"
        '<component type="desktop-application">\n'
        f"  <id>{APP_ID}</id>\n"
        f"  <name>{APP_NAME}</name>\n"
        f"  <summary>{SUMMARY}</summary>\n"
        f'  <developer id="{APP_ID.rsplit(".", 1)[0]}">\n'
        f"    <name>{APP_VENDOR}</name>\n"
        "  </developer>\n"
        "  <metadata_license>CC0-1.0</metadata_license>\n"
        "  <project_license>LicenseRef-proprietary</project_license>\n"
        f'  <launchable type="desktop-id">{APP_ID}.desktop</launchable>\n'
        f'  <url type="homepage">{WEBSITE_URL}</url>\n'
        "  <description>\n"
        "    <p>\n"
        f"      {APP_NAME} konstruiert, erzeugt und bereitet 3D-Modelle für den\n"
        "      Druck vor. Der Operationsstapel ist non-destruktiv: Jeder Schritt\n"
        "      bleibt änderbar, und eine geänderte Zahl baut das Modell neu.\n"
        "    </p>\n"
        "    <p>\n"
        "      Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat\n"
        "      benutzbar.\n"
        "    </p>\n"
        "  </description>\n"
        "  <releases>\n"
        f'    <release version="{APP_VERSION}" />\n'
        "  </releases>\n"
        "</component>\n"
    )


def write_files() -> list[Path]:
    """Schreibt alle drei Beschreibungen und gibt zurück, was entstanden ist."""
    PACKAGING.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(desktop_entry(), encoding="utf-8", newline="\n")
    FLATPAK_MANIFEST.write_text(flatpak_manifest(), encoding="utf-8", newline="\n")
    METAINFO_FILE.write_text(metainfo(), encoding="utf-8", newline="\n")
    return [DESKTOP_FILE, FLATPAK_MANIFEST, METAINFO_FILE]


def build_appimage() -> int:
    """Packt den Bau als AppImage — eine Datei, die ohne Installation läuft.

    Das AppDir ist die Verzeichnisform, die ``appimagetool`` erwartet: der Bau
    unter ``usr/``, daneben Menüeintrag, Symbol und ein ``AppRun``, das startet.
    ``AppRun`` ist ein Skript und kein Symlink, weil PyInstaller relativ zu
    seinem eigenen Ort sucht — ein Link von der Wurzel aus fände seine
    Bibliotheken nicht.
    """
    tool = shutil.which("appimagetool")
    if tool is None:
        print("appimagetool nicht gefunden — von appimage.github.io holen oder auf den PATH legen.")
        return 1

    appdir = OUTPUT_DIR / f"{APP_NAME}.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr").mkdir(parents=True)
    shutil.copytree(SOURCE_DIR, appdir / "usr" / "bin")

    (appdir / f"{APP_ID}.desktop").write_text(desktop_entry(), encoding="utf-8", newline="\n")
    icon = ROOT / "app" / "images" / "icon" / f"{DISTRIBUTION_NAME}.svg"
    shutil.copyfile(icon, appdir / f"{APP_ID}.svg")

    run = appdir / "AppRun"
    run.write_text(
        f'#!/bin/sh\nHERE=$(dirname "$(readlink -f "$0")")\nexec "$HERE/usr/bin/{APP_NAME}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    run.chmod(0o755)

    target = OUTPUT_DIR / f"{APP_NAME}-{APP_VERSION}-x86_64.AppImage"
    completed = subprocess.run([tool, str(appdir), str(target)], check=False)
    if completed.returncode:
        print("appimagetool ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode
    print(f"AppImage → {target.relative_to(ROOT)}")
    return 0


def build_flatpak() -> int:
    """Baut das Flatpak in ein lokales Ablagefach und packt es als ``.flatpak``.

    Ein Bundle und kein Ablagefach als Ergebnis: Das Fach ist ein Verzeichnis
    mit Verweisen und reist nicht, die Datei tut es — und die Download-Seite
    braucht eine Datei.
    """
    tool = shutil.which("flatpak-builder")
    if tool is None:
        print("flatpak-builder nicht gefunden — aus der Distribution installieren.")
        return 1

    repository = OUTPUT_DIR / "flatpak-repo"
    build_dir = OUTPUT_DIR / "flatpak-build"
    completed = subprocess.run(
        [
            tool,
            "--force-clean",
            f"--repo={repository}",
            str(build_dir),
            str(FLATPAK_MANIFEST),
        ],
        check=False,
        cwd=PACKAGING,
    )
    if completed.returncode:
        print("flatpak-builder ist gescheitert — die Ausgabe darüber sagt, woran.")
        return completed.returncode

    bundle = OUTPUT_DIR / f"{APP_NAME}-{APP_VERSION}-x86_64.flatpak"
    completed = subprocess.run(
        ["flatpak", "build-bundle", str(repository), str(bundle), APP_ID],
        check=False,
    )
    if completed.returncode:
        print("flatpak build-bundle ist gescheitert.")
        return completed.returncode
    print(f"Flatpak → {bundle.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--files",
        action="store_true",
        help="nur die Beschreibungen schreiben, nichts bauen (läuft überall)",
    )
    arguments = parser.parse_args()

    for path in write_files():
        print(f"geschrieben: {path.relative_to(ROOT)}")
    if arguments.files:
        return 0

    if sys.platform != "linux":
        print(
            f"Gebaut wird auf Linux, hier läuft {sys.platform} — nur die Dateien sind entstanden."
        )
        return 0
    if not (SOURCE_DIR / APP_NAME).is_file():
        print(
            f"Kein Bau unter {SOURCE_DIR} — zuerst: pyinstaller packaging/{DISTRIBUTION_NAME}.spec"
        )
        return 1

    # Beide Formate, und ein Fehlschlag des einen hält den anderen nicht auf:
    # Wer nur appimagetool hat, soll sein AppImage bekommen.
    return build_appimage() | build_flatpak()


if __name__ == "__main__":
    raise SystemExit(main())
