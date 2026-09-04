#!/bin/sh
# Installiert Solidon3D 0.3.4 — erzeugt von tools/make_linux_packages.py.
# Von Hand geänderte Zeilen verliert der nächste Lauf.
#
#   ./install.sh                          fragt nach Lizenz und Ort
#   ./install.sh --accept --prefix DIR    fragt nichts
#   ./install.sh --uninstall              entfernt eine Installation wieder
set -eu

NAME="Solidon3D"
SHORT="solidon3d"
VERSION="0.3.4"
IDENTIFIER="de.rsdigital.solidon3d"
WEBSITE="https://solidon3d.de/"
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
