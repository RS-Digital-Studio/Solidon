#!/bin/bash
# Solidon3D: Startdiagnose für macOS.
#
# Startet Solidon3D einmal so wie ein Doppelklick, beobachtet zwei Minuten lang,
# was der Prozess tut, beendet es danach wieder und legt alles in eine
# ZIP-Datei auf den Schreibtisch. Am Programm und an Ihren Dateien ändert es
# nichts, es installiert und verschickt nichts. Die ZIP-Datei schicken Sie
# selbst, wenn Sie möchten.
#
# Gesammelt werden: macOS-Version, Modell, Prozessor, Grafik, Proxy-Einstellung,
# installierte Systemerweiterungen (etwa Virenschutz oder VPN), ob der Mac von
# einer Firma verwaltet wird, Signatur und Kopien von Solidon3D, Solidons
# eigene Protokolle und Absturzberichte, Stichproben des laufenden Prozesses
# und die Systemmeldungen der Start- und Signaturprüfung aus diesen Minuten.
#
# Aufruf im Terminal:   bash ~/Downloads/solidon-diagnose.sh
#
# Läuft mit dem /bin/bash von macOS (3.2), ohne sudo und ohne Xcode.

APP="/Applications/Solidon3D.app"
NAME="Solidon3D"
WAIT_SECONDS=120
STAMP=$(date +%Y%m%d-%H%M%S)
LOGS="$HOME/Library/Logs/Solidon3D"
REPORTS="$HOME/Library/Logs/DiagnosticReports"

OUT=""
say() {
    printf '%s\n' "$*"
    [ -n "$OUT" ] && printf '%s  %s\n' "$(date +%H:%M:%S)" "$*" >> "$OUT/ablauf.txt"
    return 0
}

oldest_pid() { pgrep -o -x "$NAME" 2>/dev/null; }

stop_all() {
    pkill -x "$NAME" 2>/dev/null
    sleep 3
    pkill -9 -x "$NAME" 2>/dev/null
}

if [ ! -d "$APP" ]; then
    say "Unter $APP ist kein Solidon3D installiert. Bitte zuerst installieren."
    exit 1
fi

# Ein laufendes Solidon beendet nur der Nutzer selbst: Es könnte ungesicherte
# Arbeit enthalten. Ein Prozess, der vor dem ersten Fenster hängt, hat kein Menü.
if [ -n "$(oldest_pid)" ]; then
    say "Solidon3D läuft gerade. Bitte zuerst beenden: Solidon3D > Beenden, oder, wenn es"
    say "hängt, in der Aktivitätsanzeige Solidon3D auswählen und beenden (zur Not den Mac"
    say "neu starten). Danach das Skript noch einmal starten."
    exit 1
fi

# Untersucht wird das Paket von solidon3d.de. Eine von Hand neu signierte Kopie
# startet ohnehin und sagt über den Fehler nichts.
if codesign -dvv "$APP" 2>&1 | grep -q '^Signature=adhoc'; then
    say "Diese Solidon3D-Kopie ist von Hand neu signiert. Bitte das Paket von"
    say "solidon3d.de neu installieren und das Skript danach noch einmal starten."
    exit 1
fi

# Der Schreibtisch, sonst der Benutzerordner: Verweigert macOS dem Terminal den
# Schreibtisch, geht die Diagnose trotzdem nicht verloren. Angelegt erst nach
# den Wächtern, damit kein leerer Ordner liegen bleibt.
OUT="$HOME/Desktop/solidon-diagnose-$STAMP"
mkdir -p "$OUT" 2>/dev/null || OUT="$HOME/solidon-diagnose-$STAMP"
mkdir -p "$OUT" || { echo "Der Ordner $OUT ließ sich nicht anlegen."; exit 1; }
say "Solidon3D-Startdiagnose, Ergebnisse in $OUT"

# Ab hier läuft nur das Solidon, das dieses Skript gestartet hat.
trap 'say "Abgebrochen."; stop_all; exit 130' INT TERM HUP

say "1/5  System und Paket werden gelesen ..."
{
    sw_vers
    echo "--- uname"; uname -a
    echo "--- Hardware"; sysctl -n hw.model machdep.cpu.brand_string hw.memsize hw.ncpu
    echo "--- Grafik"; system_profiler SPDisplaysDataType 2>&1
    echo "--- Systemintegritätsschutz"; csrutil status 2>&1
    echo "--- Proxy"; scutil --proxy 2>&1
    echo "--- Systemerweiterungen (Virenschutz, Firewall, VPN)"; systemextensionsctl list 2>&1
    echo "--- Geräteverwaltung"; profiles status -type enrollment 2>&1
} > "$OUT/01-system.txt" 2>&1

{
    echo "--- Version"; /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Contents/Info.plist" 2>&1
    echo "--- Signatur"; codesign -dvv --verbose=4 "$APP" 2>&1
    echo "--- Berechtigungen"; codesign -d --entitlements - --xml "$APP" 2>&1; echo
    echo "--- Gatekeeper"; spctl --assess --type execute -vv "$APP" 2>&1
    echo "--- Erweiterte Attribute der App"; xattr -l "$APP" 2>&1
    echo "--- Erweiterte Attribute des Programms"; xattr -l "$APP/Contents/MacOS/$NAME" 2>&1
    echo "--- Weitere Kopien"; mdfind "kMDItemCFBundleIdentifier == 'de.rsdigital.solidon3d'" 2>&1
} > "$OUT/02-paket.txt" 2>&1

say "2/5  Vorhandene Protokolle werden gesichert ..."
{
    echo "--- $LOGS"; ls -la "$LOGS" 2>&1
    echo "--- Absturzberichte"; find "$REPORTS" -iname '*solidon*' -exec ls -la {} \; 2>&1
} > "$OUT/03-vorher.txt" 2>&1
if [ -d "$LOGS" ]; then
    mkdir -p "$OUT/protokolle-vorher"
    cp -p "$LOGS"/* "$OUT/protokolle-vorher/" 2>/dev/null
fi
# Das Protokoll wird fortgeschrieben; zählen dürfen nur Zeilen dieses Starts.
before=0
[ -f "$LOGS/app.log" ] && before=$(wc -l < "$LOGS/app.log" | tr -d ' ')
new_lines() { [ -f "$LOGS/app.log" ] && tail -n "+$((before + 1))" "$LOGS/app.log" 2>/dev/null; }

say "3/5  Solidon3D wird gestartet. Bitte zwei Minuten nur zusehen und nichts anklicken, auch keine Meldung."
LOG_START=$(date "+%Y-%m-%d %H:%M:%S")
MARK="$OUT/.start"
touch "$MARK"
open --stdout "$OUT/stdout.txt" --stderr "$OUT/stderr.txt" -a "$APP"
echo "open beendet mit $?" >> "$OUT/04-verlauf.txt"

started=0
seen_process=0
sampled=0
SECONDS=0
next_note=20
while [ "$SECONDS" -lt "$WAIT_SECONDS" ]; do
    sleep 1
    now=$SECONDS
    pid=$(oldest_pid)
    crash="nein"
    [ -n "$(find "$LOGS" -name 'crash-*.log' -newer "$MARK" 2>/dev/null)" ] && crash="ja"
    lines=$(new_lines | wc -l | tr -d ' ')
    if [ -n "$pid" ]; then
        seen_process=1
        state=$(ps -o stat= -o %cpu= -o rss= -o etime= -p "$pid" 2>/dev/null | tr -s ' ')
        libs=$(lsof -p "$pid" 2>/dev/null | grep -c -E '\.(so|dylib)$|\.framework/')
    else
        state="(kein Prozess)"
        libs=0
    fi
    echo "${now}s  pid=${pid:--}  zustand=[$state]  bibliotheken=$libs  absturzdatei=$crash  neue-app.log-zeilen=$lines" >> "$OUT/04-verlauf.txt"
    if new_lines | grep -q " started"; then
        started=1
        say "     Solidon3D meldet nach $now Sekunden: gestartet."
        break
    fi
    if [ "$seen_process" -eq 1 ] && [ -z "$pid" ]; then
        break
    fi
    if [ -n "$pid" ] && [ "$sampled" -lt 1 ] && [ "$now" -ge 15 ]; then
        sampled=1
        sample "$pid" 3 -file "$OUT/stichprobe-15s.txt" > "$OUT/stichprobe-15s-meldung.txt" 2>&1
        lsof -p "$pid" > "$OUT/offene-dateien-15s.txt" 2>&1
    fi
    if [ -n "$pid" ] && [ "$sampled" -lt 2 ] && [ "$now" -ge 60 ]; then
        sampled=2
        sample "$pid" 3 -file "$OUT/stichprobe-60s.txt" > "$OUT/stichprobe-60s-meldung.txt" 2>&1
        lsof -p "$pid" > "$OUT/offene-dateien-60s.txt" 2>&1
    fi
    if [ "$now" -ge "$next_note" ]; then
        say "     ... $now Sekunden"
        next_note=$((next_note + 20))
    fi
done

pid=$(oldest_pid)
window=""
if [ "$started" -eq 0 ] && [ -n "$pid" ]; then
    # Ohne „started“ heißt nicht „hängt“: Beim ersten Start wartet der Dialog
    # Erste Schritte, und das Protokoll meldet den Start erst danach.
    echo
    printf 'Ist ein Fenster von Solidon3D zu sehen, etwa „Erste Schritte“? j/n, dann Eingabetaste: '
    read -r window
    echo "Fenster zu sehen: $window" >> "$OUT/04-verlauf.txt"
fi

case "$window" in
    [jJyY]*) window_seen=1 ;;
    *) window_seen=0 ;;
esac
if [ "$started" -eq 1 ] || { [ -n "$pid" ] && [ "$window_seen" -eq 1 ]; }; then
    say "4/5  Solidon3D läuft. Es wird jetzt wieder beendet."
    sample "$(oldest_pid)" 3 -file "$OUT/stichprobe-gestartet.txt" > "$OUT/stichprobe-gestartet-meldung.txt" 2>&1
    osascript -e "quit app \"$NAME\"" >/dev/null 2>&1
    sleep 10
    stop_all
elif [ -n "$pid" ]; then
    say "4/5  Solidon3D steht. Der Zustand wird gesichert, dann wird es hart beendet."
    say "     macOS meldet danach womöglich, Solidon3D sei unerwartet beendet worden:"
    # Deutsche Anführungszeichen in der Meldung, keine Shell-Quotes.
    # shellcheck disable=SC1111
    say "     bitte „Ignorieren“ wählen, nicht „Erneut öffnen“. Meldet Solidon beim nächsten"
    say "     Start einen Programmfehler, kommt er ebenfalls von diesem Test."
    sample "$pid" 5 -file "$OUT/stichprobe-ende.txt" > "$OUT/stichprobe-ende-meldung.txt" 2>&1
    lsof -p "$pid" > "$OUT/offene-dateien-ende.txt" 2>&1
    ps -M -p "$pid" > "$OUT/faeden-ende.txt" 2>&1
    # SIGABRT: macOS legt einen Absturzbericht mit den nativen Stapeln aller
    # Fäden an; ist Solidons Absturzprotokoll schon eingerichtet
    # (install_crash_logging), schreibt es dazu die Python-Stapel in seine
    # Absturzdatei. Hängt es vorher (RM-104, im Bootstrap), gibt es nur den Bericht.
    kill -ABRT "$pid" 2>/dev/null
    sleep 15
    stop_all
else
    say "4/5  Solidon3D hat sich von selbst beendet."
fi

say "5/5  Systemprotokoll und Absturzberichte werden gesammelt (dauert etwa eine Minute) ..."
log show --style compact --info --start "$LOG_START" --predicate \
    'process == "Solidon3D" OR process == "syspolicyd" OR process == "amfid" OR process == "trustd" OR process == "XprotectService" OR process == "tccd" OR process == "iconservicesagent" OR eventMessage CONTAINS[c] "solidon"' \
    > "$OUT/05-systemprotokoll.txt" 2>&1
if [ -d "$LOGS" ]; then
    mkdir -p "$OUT/protokolle"
    cp -p "$LOGS"/* "$OUT/protokolle/" 2>/dev/null
fi
mkdir -p "$OUT/absturzberichte"
find "$REPORTS" -iname '*solidon*' -newer "$MARK" -exec cp -p {} "$OUT/absturzberichte/" \; 2>/dev/null

echo
printf 'Haben Sie in den zwei Minuten etwas gesehen (Fenster, Ladebildschirm, Meldung)? Kurz eintippen, dann Eingabetaste: '
read -r seen
echo "Gesehen: $seen" >> "$OUT/04-verlauf.txt"

rm -f "$MARK"
ditto -c -k --keepParent "$OUT" "$OUT.zip"
say "Fertig. Bitte diese Datei an support@solidon3d.de schicken:"
say "     $OUT.zip"
