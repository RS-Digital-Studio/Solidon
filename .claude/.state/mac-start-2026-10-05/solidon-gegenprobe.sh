#!/bin/bash
# Solidon3D: Gegenprobe für Intel-Macs mit macOS 26 (RM-104).
#
# Prüft, ob Solidon3D an der fehlenden Berechtigung für ausführbaren Speicher
# hängt. Dafür signiert es die installierte Kopie zweimal selbst neu, ad hoc und
# mit Hardened Runtime wie das Paket von solidon3d.de: einmal ohne und einmal
# mit genau der Ausnahme, die das nächste Update mitbringt. Beide Male wird
# Solidon3D gestartet und beobachtet. Hängt es ohne und startet mit, ist die
# Ursache bestätigt.
#
# Am Ende ist Solidon3D wieder so signiert wie nach
#     sudo codesign --force --deep --sign - /Applications/Solidon3D.app
# auch wenn das Skript abgebrochen wird. Für das Neusignieren fragt macOS nach
# dem Passwort Ihres Mac-Benutzers. Ergebnis, Stichproben und Absturzberichte
# landen in einer ZIP-Datei auf dem Schreibtisch; verschickt wird nichts.
#
# Aufruf im Terminal:   bash ~/Downloads/solidon-gegenprobe.sh
#
# Läuft mit dem /bin/bash von macOS (3.2), ohne Xcode. Die Umgebungsvariable
# SOLIDON_GEGENPROBE_SEKUNDEN verkürzt die Wartezeit, nur für Prüfläufe.

APP="/Applications/Solidon3D.app"
NAME="Solidon3D"
WAIT_SECONDS="${SOLIDON_GEGENPROBE_SEKUNDEN:-180}"
STAMP=$(date +%Y%m%d-%H%M%S)
LOGS="$HOME/Library/Logs/Solidon3D"
REPORTS="$HOME/Library/Logs/DiagnosticReports"
KEY_MEMORY="com.apple.security.cs.allow-unsigned-executable-memory"
KEY_LIBRARIES="com.apple.security.cs.disable-library-validation"

OUT=""
say() {
    printf '%s\n' "$*"
    [ -n "$OUT" ] && printf '%s  %s\n' "$(date +%H:%M:%S)" "$*" >> "$OUT/ablauf.txt"
    return 0
}

newest_pid() { pgrep -n -x "$NAME" 2>/dev/null; }

if [ ! -d "$APP" ]; then
    say "Unter $APP ist kein Solidon3D installiert. Bitte zuerst installieren."
    exit 1
fi

if [ "$(uname -m)" != "x86_64" ]; then
    say "Diese Gegenprobe ist für Intel-Macs gedacht; auf Apple-Prozessoren tritt der Fehler nicht auf."
    exit 1
fi

# Ein laufendes Solidon beendet nur der Nutzer selbst: Es könnte ungesicherte
# Arbeit enthalten. Läuft noch ein hängendes, holte ein Start nur dieses nach
# vorn, und die Gegenprobe sähe einen Hänger, wo keiner neu entstand.
if [ -n "$(newest_pid)" ]; then
    say "Solidon3D läuft gerade. Bitte zuerst beenden: Solidon3D > Beenden, oder, wenn es"
    say "hängt, in der Aktivitätsanzeige Solidon3D auswählen und beenden (zur Not den Mac"
    say "neu starten). Danach das Skript noch einmal starten."
    exit 1
fi

OUT="$HOME/Desktop/solidon-gegenprobe-$STAMP"
mkdir -p "$OUT" 2>/dev/null || OUT="$HOME/solidon-gegenprobe-$STAMP"
mkdir -p "$OUT" || { echo "Der Ordner $OUT ließ sich nicht anlegen."; exit 1; }
say "Solidon3D-Gegenprobe, Ergebnisse in $OUT"

{
    sw_vers
    echo "--- Hardware"; sysctl -n hw.model machdep.cpu.brand_string
    echo "--- Systemintegritätsschutz"; csrutil status 2>&1
    echo "--- Signatur vorher"; codesign -dvv "$APP" 2>&1
    codesign -d --entitlements - --xml "$APP" 2>&1; echo
} > "$OUT/01-vorher.txt" 2>&1

# Die beiden Listen unterscheiden sich in genau einer Ausnahme. Beide erlauben
# Bibliotheken ohne Team-ID: Ad hoc signiert trägt keine Datei eine, und ohne
# diese Erlaubnis lehnte die Hardened Runtime schon Python.framework ab.
plist() {
    printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
        '<plist version="1.0">' '<dict>'
    for key in "$@"; do
        printf '    <key>%s</key>\n    <true/>\n' "$key"
    done
    printf '%s\n' '</dict>' '</plist>'
}
plist "$KEY_LIBRARIES" > "$OUT/ohne.plist"
plist "$KEY_LIBRARIES" "$KEY_MEMORY" > "$OUT/mit.plist"
plutil -lint "$OUT/ohne.plist" "$OUT/mit.plist" > /dev/null || { say "Die Listen sind ungültig."; exit 1; }

say "Für das Neusignieren fragt macOS jetzt nach dem Passwort Ihres Mac-Benutzers."
sudo -v || { say "Ohne Passwort lässt sich Solidon3D nicht neu signieren. Abgebrochen."; exit 1; }
( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null; sleep 30; done ) &
KEEPALIVE=$!

restored=0
restore() {
    # Die Umleitung schreibt mit den Rechten des Nutzers in seine eigene Datei — gewollt.
    # shellcheck disable=SC2024
    sudo codesign --force --deep --sign - "$APP" >> "$OUT/signatur.txt" 2>&1
    codesign -dvv "$APP" 2>&1 | grep -E '^(CodeDirectory|Signature)' >> "$OUT/signatur.txt"
    restored=1
}
cleanup() {
    pkill -9 -x "$NAME" 2>/dev/null
    if [ "$restored" -eq 0 ]; then
        say "Solidon3D wird wieder wie vorher signiert ..."
        restore
    fi
    kill "$KEEPALIVE" 2>/dev/null
}
# Strg+C, Schließen des Terminalfensters (HUP) und TERM enden über exit, und
# exit läuft über cleanup: Der Rückweg kommt in jedem dieser Fälle.
trap cleanup EXIT
trap 'say "Abgebrochen."; exit 130' INT TERM HUP

sign() {
    {
        echo "=== $1"
        sudo codesign --force --deep --options runtime --sign - "$APP" &&
            sudo codesign --force --options runtime --entitlements "$OUT/$1.plist" --sign - "$APP"
    } >> "$OUT/signatur.txt" 2>&1 || { say "Das Neusignieren ist gescheitert, Einzelheiten in signatur.txt."; exit 1; }
    {
        codesign -dvv "$APP" 2>&1 | grep -E '^(CodeDirectory|Signature)'
        codesign -d --entitlements - --xml "$APP" 2>/dev/null; echo
    } >> "$OUT/signatur.txt"
}

# Startet Solidon3D und beobachtet es. Ergebnis in $result: startet (die Profile
# sind geladen, das liegt nach dem Ladebildschirm), haengt, beendet.
observe() {
    label=$1
    before=0
    [ -f "$LOGS/app.log" ] && before=$(wc -l < "$LOGS/app.log" | tr -d ' ')
    mark="$OUT/.$label"
    touch "$mark"
    result=""
    seen=0
    open -n -a "$APP"
    SECONDS=0
    while [ "$SECONDS" -lt "$WAIT_SECONDS" ]; do
        sleep 1
        pid=$(newest_pid)
        fresh=""
        [ -f "$LOGS/app.log" ] && fresh=$(tail -n "+$((before + 1))" "$LOGS/app.log" 2>/dev/null)
        lines=$(printf '%s' "$fresh" | grep -c .)
        if [ -n "$pid" ]; then
            seen=1
            state=$(ps -o stat= -o %cpu= -o etime= -p "$pid" 2>/dev/null | tr -s ' ')
        else
            state="(kein Prozess)"
        fi
        echo "${SECONDS}s  pid=${pid:--}  zustand=[$state]  neue-app.log-zeilen=$lines" >> "$OUT/$label-verlauf.txt"
        if printf '%s' "$fresh" | grep -q -e "material profiles" -e " started"; then
            result=startet
            break
        fi
        if [ "$seen" -eq 1 ] && [ -z "$pid" ]; then
            result=beendet
            break
        fi
    done
    pid=$(newest_pid)
    if [ -z "$result" ] && [ -n "$pid" ]; then
        result=haengt
        sample "$pid" 3 -file "$OUT/$label-stichprobe.txt" > "$OUT/$label-stichprobe-meldung.txt" 2>&1
        say "     Solidon3D steht. Es wird hart beendet, damit macOS die Stapel festhält."
        # Deutsche Anführungszeichen in der Meldung, keine Shell-Quotes.
        # shellcheck disable=SC1111
        say "     Meldet macOS gleich, Solidon3D sei unerwartet beendet worden: bitte „Ignorieren“."
        kill -ABRT "$pid" 2>/dev/null
        kill -CONT "$pid" 2>/dev/null
    elif [ "$result" = "startet" ]; then
        osascript -e "quit app \"$NAME\"" > /dev/null 2>&1
        sleep 8
    fi
    # Den Absturzbericht schreibt macOS mit Verzögerung.
    if [ "$result" != "startet" ]; then
        waited=0
        while [ "$waited" -lt 45 ] && [ -z "$(find "$REPORTS" -name "$NAME*.ips" -newer "$mark" 2>/dev/null)" ]; do
            sleep 3
            waited=$((waited + 3))
        done
        find "$REPORTS" -name "$NAME*.ips" -newer "$mark" -exec cp -p {} "$OUT/" \; 2>/dev/null
    fi
    pkill -9 -x "$NAME" 2>/dev/null
    sleep 3
    # Nur die Berichte dieses Durchgangs; ohne Datei läse grep sonst von der Tastatur.
    libffi="nein"
    find "$OUT" -name "$NAME*.ips" -newer "$mark" > "$OUT/.berichte" 2>/dev/null
    while IFS= read -r report; do
        grep -q -E 'ffi_closure_alloc|dlmmap|open_temp_exec_file' "$report" < /dev/null && libffi="ja"
    done < "$OUT/.berichte"
    rm -f "$OUT/.berichte"
    echo "$label: $result (libffi im Stapel: $libffi)" >> "$OUT/ergebnis.txt"
}

say "1/3  Ohne die Ausnahme signieren und starten. Bitte bis zu $WAIT_SECONDS Sekunden nur zusehen."
sign ohne
observe ohne
result_ohne=$result
libffi_ohne=$libffi
say "     ohne: $result_ohne"

say "2/3  Mit der Ausnahme signieren und starten."
sign mit
observe mit
result_mit=$result
say "     mit: $result_mit"

say "3/3  Solidon3D wird wieder wie vorher signiert ..."
restore

if [ "$result_ohne" = "haengt" ] && [ "$result_mit" = "startet" ]; then
    verdict="Bestätigt: Ohne die Ausnahme hängt Solidon3D, mit ihr startet es."
    [ "$libffi_ohne" = "ja" ] && verdict="$verdict Der Stapel zeigt libffi."
elif [ "$result_ohne" = "startet" ]; then
    verdict="Nicht bestätigt: Auch ohne die Ausnahme startet Solidon3D hier."
elif [ "$result_mit" != "startet" ]; then
    verdict="Nicht bestätigt: Auch mit der Ausnahme startet Solidon3D nicht ($result_mit)."
else
    verdict="Unklar: ohne $result_ohne, mit $result_mit."
fi
echo "$verdict" >> "$OUT/ergebnis.txt"

rm -f "$OUT"/.ohne "$OUT"/.mit
ditto -c -k --keepParent "$OUT" "$OUT.zip"
say ""
say "$verdict"
say "Solidon3D ist wieder so signiert wie nach Ihrem codesign-Befehl und startet wie gewohnt."
say "Bitte diese Datei an support@solidon3d.de schicken:"
say "     $OUT.zip"
