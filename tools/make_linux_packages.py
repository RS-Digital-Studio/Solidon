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
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.branding import (
    APP_ID,
    APP_NAME,
    APP_VENDOR,
    APP_VERSION,
    DISTRIBUTION_NAME,
    PART_FILE_MIME_TYPE,
    PART_FILE_SUFFIX,
    PROJECT_SUFFIX,
    WEBSITE_URL,
)
from tools import asset_rights

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "dist" / APP_NAME
OUTPUT_DIR = ROOT / "dist"
PACKAGING = ROOT / "packaging"

#: Die Beschreibungen, die dieses Werkzeug schreibt. Alle drei sind erzeugt und
#: gehören nicht von Hand bearbeitet — der Test hält sie an ``app/branding``.
DESKTOP_FILE = PACKAGING / f"{DISTRIBUTION_NAME}.desktop"
FLATPAK_MANIFEST = PACKAGING / f"{APP_ID}.yml"
METAINFO_FILE = PACKAGING / f"{APP_ID}.metainfo.xml"

#: Das Installationsskript, das im Archiv neben dem Bau liegt. Es ist der Teil,
#: der auf Linux die beiden Fragen stellt, die der Windows-Installer stellt:
#: den Lizenzvertrag und den Ort.
INSTALL_SCRIPT = PACKAGING / "install.sh"

#: Die MIME-Beschreibung der Projektdatei für shared-mime-info.
MIME_FILE = PACKAGING / f"{APP_ID}.xml"

#: Wie der Typ heißt. Der Menüeintrag nennt ihn seit je in seiner
#: ``MimeType``-Zeile — **ohne dass ihn jemand definiert hätte**. Eine
#: Zuordnung auf einen Typ, den das System nicht kennt, ordnet nichts zu: Der
#: Doppelklick auf ein Projekt landete beim Archivierungsprogramm, denn eine
#: Projektdatei ist ein ZIP (§16.1), und das erkennt shared-mime-info am
#: Inhalt.
MIME_TYPE = f"application/x-{DISTRIBUTION_NAME}-project"

#: Der AppImage-Laufzeitkern wird Bestandteil der Kundendatei. Der Wrapper
#: verlangt deshalb eine bereits geprüfte, feste Datei, statt appimagetool
#: während des Baus den jeweils neuesten Stand aus dem Netz holen zu lassen.
APPIMAGE_RUNTIME_ENV = "APPIMAGETOOL_RUNTIME_FILE"

#: Wie der Dateimanager den Typ nennt. Der englische Text steht als
#: ``<comment>`` ohne Sprache und ist zugleich der Rückfall für jede Sprache,
#: die hier fehlt.
MIME_COMMENTS = {
    "de": f"{APP_NAME}-Projekt",
    "es": f"Proyecto de {APP_NAME}",
    "fr": f"Projet {APP_NAME}",
    "it": f"Progetto {APP_NAME}",
    "pt": f"Projeto {APP_NAME}",
}

#: Bezeichnung der portablen Bausteindatei in denselben Sprachen. Ihr MIME-Typ
#: ist herstellergebunden und zentral in :mod:`app.branding` festgelegt.
PART_MIME_COMMENTS = {
    "de": f"{APP_NAME}-Baustein",
    "es": f"Componente de {APP_NAME}",
    "fr": f"Composant {APP_NAME}",
    "it": f"Componente {APP_NAME}",
    "pt": f"Componente do {APP_NAME}",
}

#: Was der Eintrag im Menü sagt. Kurz, denn die Software-Verwaltung schneidet
#: ab, und ohne Punkt am Ende — so hält es die Freedesktop-Empfehlung.
SUMMARY = "3D-Modelle konstruieren, erzeugen und druckfertig machen"

#: Die Kategorien der Freedesktop-Spezifikation, in denen ein CAD-Programm
#: gesucht wird. ``Graphics`` ist die Hauptkategorie, die beiden anderen führen
#: es in den Untermenüs der Arbeitsumgebungen.
CATEGORIES = ("Graphics", "3DGraphics", "Engineering")

#: Die Vorlage des Installationsskripts. Die Werte kommen über die Platzhalter
#: aus :mod:`app.branding` herein — dieselbe Regel wie für alle anderen
#: Beschreibungen hier. POSIX ``sh``, nicht Bash: das Skript läuft auch dort,
#: wo ``/bin/sh`` ein Dash ist, und das ist auf Debian und Ubuntu der Normalfall.
_INSTALL_TEMPLATE = r"""#!/bin/sh
# Installiert @APP_NAME@ @VERSION@ — erzeugt von tools/make_linux_packages.py.
# Von Hand geänderte Zeilen verliert der nächste Lauf.
#
#   ./install.sh                          fragt nach Lizenz und Ort
#   ./install.sh --accept --prefix DIR    fragt nichts
#   ./install.sh --uninstall              entfernt eine Installation wieder
set -eu

NAME="@APP_NAME@"
SHORT="@SHORT_NAME@"
VERSION="@VERSION@"
IDENTIFIER="@IDENTIFIER@"
WEBSITE="@WEBSITE@"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Deutsch, wenn die Umgebung deutsch ist, sonst Englisch. Die Anwendung selbst
# spricht sechs Sprachen; ein Installationsskript, das in jeder von ihnen
# dieselben acht Sätze doppelt, liest sich schlechter, nicht besser.
case "${LANG-}" in
  de*) LANGUAGE=de ;;
  *) LANGUAGE=en ;;
esac

say() {
  if [ "$LANGUAGE" = de ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi
}

ask() {
  if [ "$LANGUAGE" = de ]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}

usage() {
  say "Aufruf: ./install.sh [--prefix VERZEICHNIS] [--accept] [--uninstall]" \
      "Usage: ./install.sh [--prefix DIRECTORY] [--accept] [--uninstall]"
  say "  --prefix     wohin das Programm kommt" \
      "  --prefix     where the program goes"
  say "  --accept     dem Lizenzvertrag zustimmen, ohne ihn anzuzeigen" \
      "  --accept     accept the licence agreement without showing it"
  say "  --uninstall  entfernt eine Installation wieder" \
      "  --uninstall  removes an installation again"
}

# Als root ins System, sonst ins Profil. Kein sudo, keine Empfehlung dazu: wer
# es für alle installieren will, ruft es als root auf.
if [ "$(id -u)" = 0 ]; then
  DEFAULT_TARGET="/opt/$SHORT"
  BIN_DIR="/usr/local/bin"
  APP_DIR="/usr/share/applications"
  ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
  META_DIR="/usr/share/metainfo"
  MIME_DIR="/usr/share/mime"
else
  DEFAULT_TARGET="$HOME/.local/lib/$SHORT"
  BIN_DIR="$HOME/.local/bin"
  APP_DIR="$HOME/.local/share/applications"
  ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
  META_DIR="$HOME/.local/share/metainfo"
  MIME_DIR="$HOME/.local/share/mime"
fi

TARGET=""
ACCEPTED=0
MODE=install

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      shift
      if [ $# -eq 0 ]; then
        say "--prefix ohne Verzeichnis." "--prefix without a directory."
        exit 2
      fi
      TARGET="$1"
      ;;
    --prefix=*) TARGET="${1#--prefix=}" ;;
    --accept|-y) ACCEPTED=1 ;;
    --uninstall) MODE=uninstall ;;
    -h|--help) usage; exit 0 ;;
    *)
      say "Unbekannte Angabe: $1" "Unknown option: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

# Ein eingetipptes „~/…" expandiert die Shell nicht, wenn es aus `read` kommt —
# hier von Hand, sonst entstünde ein Verzeichnis, das wörtlich „~" heißt.
expand() {
  case "$1" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s%s' "$HOME" "${1#\~}" ;;
    *) printf '%s' "$1" ;;
  esac
}

if [ "$MODE" = uninstall ]; then
  if [ -z "$TARGET" ]; then TARGET="$DEFAULT_TARGET"; fi
  TARGET=$(expand "$TARGET")
  if [ -x "$TARGET/uninstall.sh" ]; then
    exec "$TARGET/uninstall.sh"
  fi
  say "Dort liegt keine Installation: $TARGET" "No installation found there: $TARGET"
  say "Den Ort mit --prefix angeben." "Name the location with --prefix."
  exit 1
fi

if [ ! -d "$HERE/$NAME" ]; then
  say "Im Archiv fehlt der Ordner $NAME — bitte vollständig auspacken." \
      "The archive is missing the $NAME folder — please extract all of it."
  exit 1
fi

say "$NAME $VERSION wird installiert." "Installing $NAME $VERSION."
echo

if [ "$ACCEPTED" -eq 0 ]; then
  # Ohne Terminal fragt niemand und niemand antwortet. Eine Zustimmung
  # anzunehmen, die keiner gegeben hat, ist der falsche Ausweg.
  if [ ! -t 0 ]; then
    say "Ohne Terminal kann niemand zustimmen — mit --accept aufrufen." \
        "Nobody can agree without a terminal — call it with --accept."
    exit 1
  fi
  if [ -f "$HERE/eula.txt" ]; then
    say "Der Lizenzvertrag folgt. Er liegt auf Deutsch vor; verlassen mit q." \
        "The licence agreement follows. It is in German; press q to leave it."
    echo
    if command -v less >/dev/null 2>&1; then
      less "$HERE/eula.txt"
    else
      cat "$HERE/eula.txt"
    fi
    echo
  fi
  ask "Stimmen Sie dem Lizenzvertrag zu? [j/N] " \
      "Do you accept the licence agreement? [y/N] "
  read -r ANSWER
  case "$ANSWER" in
    j|J|ja|Ja|JA|y|Y|yes|Yes|YES) ;;
    *)
      say "Abgebrochen. Es wurde nichts installiert." "Cancelled. Nothing was installed."
      exit 1
      ;;
  esac
  echo
fi

if [ -z "$TARGET" ]; then
  if [ -t 0 ]; then
    ask "Wohin soll es? [$DEFAULT_TARGET] " "Where should it go? [$DEFAULT_TARGET] "
    read -r ANSWER
    if [ -n "$ANSWER" ]; then TARGET="$ANSWER"; else TARGET="$DEFAULT_TARGET"; fi
  else
    TARGET="$DEFAULT_TARGET"
  fi
fi
TARGET=$(expand "$TARGET")
case "$TARGET" in
  /*) ;;
  *) TARGET="$(pwd)/$TARGET" ;;
esac

# Das Ziel bekommt immer ein eigenes Verzeichnis. Der Schalter heißt --prefix,
# und wer das von autotools kennt, gibt /usr/local an — dorthin gehört ein
# Programm aber nicht als Haufen Dateien, und vor allem darf das rm -rf
# darunter ein solches Verzeichnis niemals treffen. Endet das Ziel schon auf
# den eigenen Namen, bleibt es unangetastet; die Vorgaben tun das bereits.
case "$TARGET" in
  */"$SHORT") ;;
  *) TARGET="$TARGET/$SHORT" ;;
esac

if [ -e "$TARGET" ] && [ ! -d "$TARGET" ]; then
  say "Dort liegt eine Datei, kein Verzeichnis: $TARGET" \
      "That is a file, not a directory: $TARGET"
  exit 1
fi
if [ -e "$TARGET/$NAME" ]; then
  say "Eine vorhandene Version an dieser Stelle wird ersetzt." \
      "An existing version in this place is being replaced."
  # Gelöscht wird das Verzeichnis der Anwendung — dass es eines ist, stellt
  # der Fall oben sicher. Ohne ihn machte ein --prefix /usr/local aus dem
  # zweiten Lauf ein rm -rf /usr/local, mit allem, was sonst darin liegt.
  rm -rf "$TARGET"
fi

mkdir -p "$TARGET" "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$META_DIR" "$MIME_DIR/packages"
cp -a "$HERE/$NAME/." "$TARGET/"
chmod 755 "$TARGET/$NAME"

# Der Starter ist ein Skript: der Bootloader sucht seine Bibliotheken neben
# sich, und ein exec mit vollem Pfad stimmt auf jeder Distribution.
cat > "$BIN_DIR/$NAME" <<LAUNCHER
#!/bin/sh
exec "$TARGET/$NAME" "\$@"
LAUNCHER
chmod 755 "$BIN_DIR/$NAME"
ln -sf "$NAME" "$BIN_DIR/$SHORT"

cp "$HERE/$SHORT.desktop" "$APP_DIR/$IDENTIFIER.desktop"
cp "$HERE/icon.svg" "$ICON_DIR/$IDENTIFIER.svg"
if [ -f "$HERE/$IDENTIFIER.metainfo.xml" ]; then
  cp "$HERE/$IDENTIFIER.metainfo.xml" "$META_DIR/$IDENTIFIER.metainfo.xml"
fi

# Der Dateityp. Ohne ihn nennt der Menüeintrag einen MIME-Typ, den das System
# nicht kennt — und ein Doppelklick auf ein Projekt landet beim
# Archivierungsprogramm, weil eine Projektdatei ein ZIP ist. Die Datenbank muss
# danach neu gebaut werden; ohne den Lauf liegt die Beschreibung da und gilt
# nicht.
if [ -f "$HERE/$IDENTIFIER.xml" ]; then
  cp "$HERE/$IDENTIFIER.xml" "$MIME_DIR/packages/$IDENTIFIER.xml"
  if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "$MIME_DIR" >/dev/null 2>&1 || true
  fi
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "${ICON_DIR%/scalable/apps}" >/dev/null 2>&1 || true
fi

cat > "$TARGET/uninstall.sh" <<UNINSTALL
#!/bin/sh
# Entfernt $NAME wieder. Projektdateien und Einstellungen bleiben, wo sie sind.
set -eu
echo "$NAME wird entfernt / removing $NAME"
rm -f "$BIN_DIR/$NAME" "$BIN_DIR/$SHORT"
rm -f "$APP_DIR/$IDENTIFIER.desktop" "$ICON_DIR/$IDENTIFIER.svg"
rm -f "$META_DIR/$IDENTIFIER.metainfo.xml"
rm -f "$MIME_DIR/packages/$IDENTIFIER.xml"
if command -v update-mime-database >/dev/null 2>&1; then
  update-mime-database "$MIME_DIR" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
rm -rf "$TARGET"
UNINSTALL
chmod 755 "$TARGET/uninstall.sh"

echo
say "Fertig. $NAME liegt in $TARGET." "Done. $NAME is in $TARGET."
say "Starten: $NAME — oder über das Anwendungsmenü." \
    "Start it with: $NAME — or from the application menu."
say "Entfernen: $TARGET/uninstall.sh" "Remove it with: $TARGET/uninstall.sh"
say "Handbuch und Hilfe: $WEBSITE" "Manual and help: $WEBSITE"

case ":${PATH-}:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo
    say "Hinweis: $BIN_DIR liegt nicht im PATH — der Menüeintrag geht trotzdem." \
        "Note: $BIN_DIR is not in PATH — the menu entry works regardless."
    ;;
esac
"""


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
        f"MimeType={MIME_TYPE};{PART_FILE_MIME_TYPE};\n"
    )


def flatpak_manifest() -> str:
    """Das Flatpak-Manifest um den fertigen PyInstaller-Ordner.

    **Gebaut wird nicht aus den Quellen, sondern um den Bau herum.** Das ist für
    Flatpak der ungewöhnlichere Weg und hier der richtige: Die Anwendung bringt
    ihr Python und ihre Bibliotheken schon mit (dieselbe Spec wie Windows und
    macOS), und ein zweiter Bauweg wäre eine zweite Version, die auseinanderläuft
    — genau das, was die eine Spec verhindert.

    Die Berechtigungen sind so knapp wie möglich, und jede hat einen Grund:

    * ``--socket=x11`` — die Oberfläche. Der eingebettete VTK-Viewport braucht
      den X11-Display auch in einer Wayland-Sitzung. ``fallback-x11`` gäbe ihn
      dort gerade nicht frei; im Flatpak blieb ``DISPLAY`` leer und VTK brach
      beim ersten Modell ab. Auch Qt läuft deshalb über Xwayland: zwei
      Fenstersysteme innerhalb eines Fensters sind keine stabile Kombination.
    * ``--device=dri`` — der Viewport rechnet mit OpenGL (§18).
    * ``--filesystem=home`` — Modelle liegen beim Nutzer, und ein Dateidialog,
      der nur in einen Sandkasten sehen darf, ist kein Dateidialog. Portale
      wären der feinere Weg; sie setzen voraus, dass jeder Öffnen- und
      Speichern-Pfad darüber läuft, und das ist ein eigener Schritt.
    * ``--talk-name=org.freedesktop.secrets`` — der Schlüssel des Agenten liegt
      im Schlüsselbund (§26) und nicht in der Projektdatei.
    * ``--share=network`` — Rückmeldung an den Support, Aktualisierungsprüfung,
      Chat gegen einen Dienst und das Holen eines Modells aus dem Netz. Siehe
      unten.
    * ``--talk-name=org.freedesktop.Flatpak`` — **der Slicer läuft auf dem
      Rechner, nicht im Sandkasten.** Ohne diese Zeile ist die Übergabe (§29)
      im Linux-Paket tot, und zwar lautlos: ``discover`` sucht in ``/opt``,
      ``/usr/local`` und den Flatpak-Exporten des Rechners, und aus einem
      Sandkasten heraus ist keiner dieser Pfade sichtbar. Es stürzt nichts ab,
      es findet nur nichts. Mit der Berechtigung fragt ``discover`` über
      ``flatpak-spawn --host which`` und ``handover`` startet über denselben
      Weg. Der Arbeitsordner liegt schon im Nutzer-Cache, weil
      ``discover.sandboxed`` den eigenen Fall jetzt mitzählt.
    * ``--talk-name=org.fcitx.Fcitx5`` und ``--talk-name=org.freedesktop.portal.Fcitx``
      — die Eingabemethode. Derselbe Kunde meldete: „So muss ich diesen Text in
      einer anderen Anwendung schreiben und nach Solidon3D copypasten." Eine
      Eingabemethode spricht über den Sitzungsbus, und dieses Manifest gibt
      **gezielten** Zugriff statt des ganzen Busses — was nicht genannt ist,
      ist nicht erreichbar. Ohne diese Zeilen bleibt jedes Textfeld stumm, und
      zwar nur im Flatpak.

      **Ungeprüft**, und das gehört dazu: Von Windows aus lässt sich das nicht
      messen. Die beiden Namen sind die üblichen aus Flathub-Manifesten für
      Qt-Anwendungen; ob sie bei diesem Kunden reichen, sagt erst ein Lauf auf
      seinem System. IBus liegt im Runtime und braucht keine eigene Zeile.

    **Netzzugang: seit dem 27.08.2026 drin, und die Kehrtwende hat einen
    Anlass.** Hier stand vorher das Gegenteil, mit einer Begründung, die
    plausibel klang: Ohne Netz gebe es kein Konto, keine Telemetrie und keine
    Frage danach.

    Ein Kunde auf CachyOS hat gezeigt, was das kostet. Sein Fehlerbericht kam
    per Hand über Robert, mit dem Satz „Ich kann den Bericht aus der App nicht
    senden: urlopen error" — im Protokoll steht der Grund zweiundzwanzigmal:
    ``[Errno -3] Temporärer Fehler bei der Namensauflösung``, bei jedem Start
    für die Aktualisierungsprüfung und einmal für die Sendung. Was für uns eine
    saubere Sandbox war, war für ihn eine Anwendung, deren Knöpfe nicht
    funktionieren.

    **Und die Zusage hing nie an der Sandbox.** Sie hängt an der Bauart:
    ``support.send()`` hat genau einen Aufrufer, und der sitzt an einem Knopf —
    ``tests/test_support.py`` zählt ihn. Auf Windows und macOS gibt es keine
    Sandbox, und dort gilt dieselbe Zusage seit je. Eine Grenze, die nur auf
    einer der drei Plattformen steht, ist keine Zusage, sondern ein
    Unterschied — und der Kunde erlebt ihn als Fehler.

    Entscheidung Robert, 27.08.2026: „jede plattform sollte das gleiche haben
    und alles funktionieren."
    """
    permissions = "\n".join(
        f"  - {entry}"
        for entry in (
            "--socket=x11",
            "--share=ipc",
            "--share=network",
            "--device=dri",
            "--filesystem=home",
            "--talk-name=org.freedesktop.secrets",
            "--talk-name=org.freedesktop.Flatpak",
            "--talk-name=org.fcitx.Fcitx5",
            "--talk-name=org.freedesktop.portal.Fcitx",
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
        # Der Dateityp reist mit: Flatpak trägt ihn beim Installieren in die
        # MIME-Datenbank des Systems ein, und erst damit führt ein Doppelklick
        # auf ein Projekt hierher statt zum Archivierungsprogramm.
        f"      - install -Dm644 {MIME_FILE.name}"
        f" /app/share/mime/packages/{APP_ID}.xml\n"
        f"    sources:\n"
        # Die Quelle ist **das Anwendungsverzeichnis**, nicht ``dist``: Dorthin
        # schreibt der Bau selbst — ``flatpak-repo`` und ``flatpak-build`` aus
        # dem Vorlauf, dazu das AppDir des AppImage-Baus. Ungenau gefasst
        # packte das Flatpak seine eigene Zwischenausgabe mit ein und wuchs bei
        # jedem Lauf. ``dest`` hält das Unterverzeichnis, das die Baubefehle
        # oben nennen, damit die unverändert bleiben.
        f"      - type: dir\n"
        f"        path: ../dist/{APP_NAME}\n"
        f"        dest: {APP_NAME}\n"
        f"      - type: file\n"
        f"        path: {DESKTOP_FILE.name}\n"
        f"      - type: file\n"
        f"        path: {METAINFO_FILE.name}\n"
        f"      - type: file\n"
        f"        path: {MIME_FILE.name}\n"
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


def mime_definition() -> str:
    """Die Typbeschreibung für shared-mime-info.

    Drei Angaben, und jede hat eine Aufgabe: ``glob`` erkennt die Datei an der
    Endung, ``sub-class-of`` sagt, dass sie ein ZIP ist (§16.1) — ohne das
    ordnet die Erkennung sie beim Öffnen wieder dem Archivierungsprogramm zu,
    weil der Inhalt eben ein ZIP ist —, und ``icon`` gibt ihr das Symbol der
    Anwendung im Dateimanager.

    Die Kommentare stehen in allen Sprachen, die die Anwendung spricht: Was der
    Dateimanager unter „Art" anzeigt, kommt von hier, und es auf Englisch
    stehen zu lassen wäre die einzige Stelle der Auslieferung, an der eine
    Übersetzung fehlt.
    """
    comments = "".join(
        f'    <comment xml:lang="{code}">{text}</comment>\n' for code, text in MIME_COMMENTS.items()
    )
    part_comments = "".join(
        f'    <comment xml:lang="{code}">{text}</comment>\n'
        for code, text in PART_MIME_COMMENTS.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Erzeugt von tools/make_linux_packages.py — Werte aus app/branding.py. -->\n"
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        f'  <mime-type type="{MIME_TYPE}">\n'
        f"    <comment>{APP_NAME} project</comment>\n"
        f"{comments}"
        '    <sub-class-of type="application/zip" />\n'
        f'    <glob pattern="*{PROJECT_SUFFIX}" />\n'
        f'    <icon name="{APP_ID}" />\n'
        "  </mime-type>\n"
        f'  <mime-type type="{PART_FILE_MIME_TYPE}">\n'
        f"    <comment>{APP_NAME} part</comment>\n"
        f"{part_comments}"
        '    <sub-class-of type="application/json" />\n'
        f'    <glob pattern="*{PART_FILE_SUFFIX}" />\n'
        f'    <icon name="{APP_ID}" />\n'
        "  </mime-type>\n"
        "</mime-info>\n"
    )


def install_script() -> str:
    """Das Installationsskript, das im Archiv neben dem Bau liegt.

    **Es stellt auf Linux dieselben zwei Fragen wie der Windows-Installer**:
    den Lizenzvertrag mit einer Zustimmung, die auch abgelehnt werden kann, und
    den Ort. Ein Archiv, das man irgendwohin auspackt, beantwortet die erste
    gar nicht und die zweite ohne Vorschlag — und der Menüeintrag fehlt danach
    ebenfalls.

    Es fragt nur, wenn ein Terminal da ist. ``--accept`` und ``--prefix``
    machen denselben Lauf unbeaufsichtigt, für Paketbauer und für den, der es
    über eine Verwaltung ausrollt; ohne Terminal und ohne ``--accept`` bricht
    es ab, statt eine Zustimmung anzunehmen, die niemand gegeben hat.

    Als root geht es nach ``/opt`` und ``/usr/share``, als Nutzer in dessen
    Profil — ohne ``sudo`` zu verlangen und ohne es zu empfehlen. Beide Wege
    hinterlassen ein ``uninstall.sh``, das alles wieder entfernt und die
    Projektdateien in Ruhe lässt.

    Der Starter ist ein Skript und kein Link auf die ausgelieferte Datei: der
    Bootloader von PyInstaller sucht seine Bibliotheken neben sich, und ein
    ``exec`` mit vollem Pfad ist der Weg, der auf jeder Distribution stimmt.
    """
    return (
        _INSTALL_TEMPLATE.replace("@APP_NAME@", APP_NAME)
        .replace("@SHORT_NAME@", DISTRIBUTION_NAME)
        .replace("@VERSION@", APP_VERSION)
        .replace("@IDENTIFIER@", APP_ID)
        .replace("@WEBSITE@", WEBSITE_URL)
    )


def write_files() -> list[Path]:
    """Schreibt alle fünf Beschreibungen und gibt zurück, was entstanden ist."""
    PACKAGING.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(desktop_entry(), encoding="utf-8", newline="\n")
    FLATPAK_MANIFEST.write_text(flatpak_manifest(), encoding="utf-8", newline="\n")
    METAINFO_FILE.write_text(metainfo(), encoding="utf-8", newline="\n")
    MIME_FILE.write_text(mime_definition(), encoding="utf-8", newline="\n")
    INSTALL_SCRIPT.write_text(install_script(), encoding="utf-8", newline="\n")
    # Auf Windows ohne Wirkung, auf Linux der Unterschied zwischen „ausführbar"
    # und „./install.sh: Permission denied". Das Archiv unten trägt das Recht
    # dann weiter.
    INSTALL_SCRIPT.chmod(0o755)
    return [DESKTOP_FILE, FLATPAK_MANIFEST, METAINFO_FILE, MIME_FILE, INSTALL_SCRIPT]


def build_tarball() -> int:
    """Packt Bau, Installationsskript, Lizenz, Menüeintrag und Symbol in ein
    Archiv.

    **Das Archiv ist mehr als der Bau.** Vorher war es genau der Ordner aus
    ``dist`` und sonst nichts — wer es auspackte, hatte ein Programm ohne
    Menüeintrag, ohne Symbol, ohne gelesenen Lizenzvertrag und ohne einen Ort,
    an dem es hingehört. Jetzt liegt daneben, was ``install.sh`` dafür braucht.

    Als ``.tar.gz`` und nicht als ``.zip``: es trägt die Ausführungsrechte, und
    ohne die startet weder das Skript noch das Programm darin.
    """
    if not (SOURCE_DIR / APP_NAME).is_file():
        print(
            f"Kein Bau unter {SOURCE_DIR} — zuerst: pyinstaller packaging/{DISTRIBUTION_NAME}.spec"
        )
        return 1
    licence = PACKAGING / "eula.txt"
    if not licence.is_file():
        print("packaging/eula.txt fehlt — zuerst: python tools/make_legal.py")
        return 1

    stem = f"{APP_NAME}-{APP_VERSION}-linux-x86_64"
    staging = OUTPUT_DIR / stem
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    shutil.copytree(SOURCE_DIR, staging / APP_NAME, symlinks=True)
    shutil.copyfile(INSTALL_SCRIPT, staging / "install.sh")
    (staging / "install.sh").chmod(0o755)
    shutil.copyfile(licence, staging / "eula.txt")
    shutil.copyfile(DESKTOP_FILE, staging / DESKTOP_FILE.name)
    shutil.copyfile(METAINFO_FILE, staging / METAINFO_FILE.name)
    shutil.copyfile(MIME_FILE, staging / MIME_FILE.name)
    shutil.copyfile(
        ROOT / "app" / "images" / "icon" / f"{DISTRIBUTION_NAME}.svg", staging / "icon.svg"
    )

    target = OUTPUT_DIR / f"{stem}.tar.gz"
    target.unlink(missing_ok=True)
    with tarfile.open(target, "w:gz") as archive:
        # Ein Wurzelverzeichnis im Archiv, damit ein Auspacken im Downloadordner
        # nicht dreihundert Dateien danebenlegt.
        archive.add(staging, arcname=stem)
    shutil.rmtree(staging)
    print(f"Archiv → {target.relative_to(ROOT)}")
    return 0


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

    runtime_value = os.environ.get(APPIMAGE_RUNTIME_ENV, "").strip()
    runtime = Path(runtime_value).expanduser() if runtime_value else None
    if runtime is None or not runtime.is_file():
        print(
            f"{APPIMAGE_RUNTIME_ENV} zeigt auf keinen geprüften AppImage-Laufzeitkern — "
            "feste Laufzeitdatei laden, SHA-256 prüfen und den absoluten Pfad setzen."
        )
        return 1

    appdir = OUTPUT_DIR / f"{APP_NAME}.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr").mkdir(parents=True)
    shutil.copytree(SOURCE_DIR, appdir / "usr" / "bin")

    mime_target = appdir / "usr" / "share" / "mime" / "packages" / f"{APP_ID}.xml"
    mime_target.parent.mkdir(parents=True)
    shutil.copyfile(MIME_FILE, mime_target)

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
    completed = subprocess.run(
        [tool, "--runtime-file", str(runtime.resolve()), str(appdir), str(target)],
        check=False,
    )
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
    # Die drei Formate einzeln, weil die CI das interne Archiv getrennt von den
    # beiden öffentlichen Paketen baut. Ein Fehler in AppImage oder Flatpak
    # macht den Linux-Zweig rot; Windows und macOS laufen in eigenen Zweigen
    # weiter. Ohne Angabe entstehen alle drei.
    parser.add_argument("--tarball", action="store_true", help="nur das Archiv mit install.sh")
    parser.add_argument("--appimage", action="store_true", help="nur das AppImage")
    parser.add_argument("--flatpak", action="store_true", help="nur das Flatpak")
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
    try:
        asset_rights.require_customer_artifact_cleared(SOURCE_DIR, "linux")
    except RuntimeError as problem:
        print(problem)
        return 1

    chosen = arguments.tarball or arguments.appimage or arguments.flatpak
    result = 0
    # Ein Fehlschlag des einen hält die anderen nicht auf: Wer nur
    # appimagetool hat, soll sein AppImage bekommen.
    if arguments.tarball or not chosen:
        result |= build_tarball()
    if arguments.appimage or not chosen:
        result |= build_appimage()
    if arguments.flatpak or not chosen:
        result |= build_flatpak()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
