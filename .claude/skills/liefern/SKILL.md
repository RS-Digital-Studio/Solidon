---
name: liefern
description: >
  Schließt eine geprüfte Arbeitseinheit ab: Änderungen abgrenzen, über einen
  privaten Index mit deutschen Meldungen committen und Commit sowie Push
  prüfen. Bewahrt fremde Dateien und den gemeinsamen Index unverändert.
  Nur auf ausdrückliche Anweisung.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Liefern

## Umfang und Nachweis

Die aktuelle Anweisung von Robert bestimmt den Umfang. Das vollständige Tor
über `/pruefen` gehört vor den Commit; ein passender bereits grüner Lauf muss
nicht wiederholt werden. Liegt ein Fehllauf vor, seine Ursache und den
betroffenen Stand benennen und zuerst beheben. Ein expliziter Auftrag wie
„nur committen“ bezieht sich auf die bereits geprüften eigenen Änderungen.

`tools/session_board.py list`, den Verlauf und `git diff HEAD -- <eigene Pfade>`
lesen. Die Einheit umfasst genaue Dateien und, bei gemeinsam bearbeiteten
Dateien, nur die eigenen Änderungen darin. Verzeichnisangaben, `git add .`
und `git commit -a` gehören nicht in diesen Ablauf. Eine neue oder gelöschte
Datei muss ausdrücklich zur Liste gehören. `3D Drucker/`, Umgebungen,
Messdaten und Testartefakte bleiben draußen, soweit sie nicht beauftragt sind.

Der gemeinsame Index kann fremde vorgemerkte Änderungen tragen. **Er wird
weder bestückt noch nachgezogen, auch nicht auf vermeintlich eigenen Pfaden.**
`MM`, eine vorgemerkte Löschung oder eine vorhandene Arbeitsdatei beweisen
keine Absicht. Unklare Zuordnung mit der zuständigen Sitzung klären.

## Meldung und erwarteter Inhalt vorbereiten

Ein Thema ergibt einen Commit. Die deutsche Meldung verwendet echte Umlaute
und beschreibt das Ergebnis, etwa „Hohle Querschnitte kamen als nichts
zurück“. Der Rumpf nennt den nötigen Grund. Der tatsächliche Mitautor bleibt
angegeben: das verwendete Claude-Modell mit `noreply@anthropic.com` oder
`Codex <noreply@openai.com>`.

Vor dem Commitblock zwei Dateien außerhalb des Arbeitsbaums vorbereiten:
`message.txt` mit der vollständigen Meldung und `expected-numstat.txt` mit den
**inhaltlich geprüften erwarteten** Einfügungen, Löschungen und Pfaden. Das
Format entspricht `git -c core.quotepath=false diff --no-renames --numstat`:
Tabulatoren, eine Datei je Zeile, LF-Zeilenenden, Git-Sortierung. Die Zahlen
nicht erst aus dem später bestückten Index als Sollwert übernehmen. Bei
Binärdateien stehen `-` und `-` statt Zahlen. Dateizahlen ersetzen keine
Prüfung der eigenen Zeilen in gemeinsamen Dateien.

Die Ablage ist das von `git rev-parse --path-format=absolute --git-path
"delivery/<feste Sitzungskennung>"` gelieferte Verzeichnis. Die Kennung muss
über Aufrufe hinweg gleich bleiben; sie ist keine Shell-Prozessnummer. Der
Commitblock unten ermittelt sie aus den Sitzungsvariablen. Sind diese leer,
zuerst eine feste eigene Kennung für diese Arbeit wählen und im Block
wörtlich einsetzen. Meldung, Sollwert und gegebenenfalls der eigene Patch
liegen fertig vor, bevor der Block beginnt.

## Privaten Index aufbauen, prüfen und committen

**Die Commitphasen im selben Arbeitsbaum laufen nacheinander.** Das mit den
anderen Sitzungen vor Beginn koordinieren. Ein HEAD-Vergleich direkt vor
`git commit` sperrt nicht das verbleibende Prozessstartfenster. Der folgende
Block erkennt ein gewandertes HEAD und stoppt; er ersetzt diese Koordination
nicht. Jeder neue Versuch beginnt mit dem dann aktuellen HEAD.

Der folgende Bash-Block läuft vollständig in **einem Werkzeugaufruf**. In
PowerShell über das vorhandene Git Bash ausführen. Die beiden Beispielpfade
vorher durch die genaue geprüfte Dateiliste ersetzen. Die runden Klammern
halten `GIT_INDEX_FILE` in diesem Aufruf; der gemeinsame Index bleibt außen.

```bash
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  delivery_id="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_NAME:-}}}}"
  test -n "$delivery_id" || { printf '%s\n' 'Feste Sitzungskennung fehlt.' >&2; exit 1; }
  case "$delivery_id" in
    *[!a-zA-Z0-9_-]*) printf '%s\n' 'Sitzungskennung enthält ungeeignete Pfadzeichen.' >&2; exit 1 ;;
  esac
  delivery_dir="$(git rev-parse --path-format=absolute --git-path "delivery/$delivery_id")"
  test -s "$delivery_dir/message.txt"
  test -s "$delivery_dir/expected-numstat.txt"
  delivery_paths=('tools/sync_agents.py' 'tests/test_agent_mirror.py')
  export GIT_INDEX_FILE="$delivery_dir/index"

  delivery_base="$(git rev-parse --verify HEAD)"
  git read-tree "$delivery_base"
  git --literal-pathspecs add -- "${delivery_paths[@]}"
  git -c core.quotepath=false diff --cached --no-renames --numstat "$delivery_base" > "$delivery_dir/actual-numstat.txt"
  if ! cmp -s "$delivery_dir/expected-numstat.txt" "$delivery_dir/actual-numstat.txt"; then
    printf '%s\n' 'Inhalt weicht von der geprüften Erwartung ab; kein Commit.' >&2
    cat "$delivery_dir/actual-numstat.txt" >&2
    exit 1
  fi
  if test "$(git rev-parse HEAD)" != "$delivery_base"; then
    printf '%s\n' 'HEAD ist gewandert; neu abgleichen, kein Commit.' >&2
    exit 1
  fi
  git commit -F "$delivery_dir/message.txt"
  printf '%s\n' 'Commitkennung für die getrennte Ergebniskontrolle:'
  git rev-parse HEAD
)
```

Eine laufende Merge-, Rebase- oder Cherry-pick-Operation wird nicht durch
diesen Ablauf abgeschlossen. Vorher den Zustand lesen und deren Behandlung
mit dem Besitzer koordinieren. Einen Index-Lock nicht aufgrund seines Alters
löschen; er kann zu einem laufenden Prozess gehören.

**Bei gemeinsamen Dateien ersetzt der eigene Patch das vollständige `git add`
für diese Dateien.** Im selben Block nach `read-tree` den vorher geprüften
Patch mit `git apply --cached --check <patchdatei>` prüfen und mit
`git apply --cached <patchdatei>` ausschließlich auf den privaten Index
anwenden. Vollständig eigene Dateien können daneben über genaue Pfade
bestückt werden. Den Arbeitsbaum dafür nicht zurücksetzen.

Wer stattdessen gezielt Blobs mit `git update-index --cacheinfo` einsetzt,
baut deren vollständigen Inhalt aus dem **in diesem Block frisch gelesenen**
`delivery_base` plus der eigenen Änderung. Ein alter vorbereiteter Blob könnte
inzwischen committierte fremde Zeilen verlieren. **Danach normales
`git commit -F …`, niemals `-o`, `--only` oder Pfadargumente:** Diese würden
wieder den Dateistand vom Arbeitsbaum statt der geprüften Hunks übernehmen.

## Ergebnis in einem neuen Aufruf kontrollieren

Die vom Commit ausgegebene feste Kennung verwenden, nicht ein später
weitergewandertes `HEAD`. Mit `git show <kennung> --name-status` und
`git show <kennung> --numstat` die tatsächlich enthaltenen Dateien und Zahlen
gegen die Erwartung halten; bei gemeinsamen Dateien auch den tatsächlichen
Diff prüfen. Keine Behauptung über den Commit aus dem vorherigen Index ableiten.

Der eingerichtete `.githooks/post-commit` pusht nach `origin`, wie in
`CLAUDE.md` festgelegt. Seine Ausgabe und den Remote-Zweig getrennt prüfen:
Ein erfolgreicher Commit beweist keinen erfolgreichen Push. Ein Remote-Tip,
der genau die Commitkennung trägt, bestätigt die Veröffentlichung. Ist der
Remote-Zweig weiter, nach dem Lesen beziehungsweise Fetch seine Abstammung
prüfen; eine abweichende Spitze allein beweist weder Erfolg noch Verlust.

Eine ausdrücklich gewünschte lokale Sammlung nutzt `SOLIDON_KEIN_PUSH=1` im
Commitaufruf; eine vorhandene `solidon.noAutoPush`-Sperre bleibt bestehen. Bei
einer weitergewanderten Gegenstelle koordiniert zusammenführen, ohne
ungefragten Rebase oder Force-Push.

Den gemeinsamen Index danach **nur lesen**, außerhalb der privaten Umgebung:

```bash
env -u GIT_INDEX_FILE git --no-optional-locks status --short
env -u GIT_INDEX_FILE git --no-optional-locks diff --cached HEAD --name-status
```

Dessen Einträge bleiben unverändert. Keine automatische Reparatur mit
`reset`, `restore --staged`, `read-tree` oder erneutem `add`, auch nicht bei
neuen Dateien im eigenen Commit. Offene Zuordnung melden; fremde Stagingabsicht
niemals aus dem Arbeitsbaum erraten. Die private Ablage bis zum abgeschlossenen
Nachweis behalten. Zu keinem Zeitpunkt auf den gemeinsamen Index umschalten,
um dort zu schreiben.

Melden: Commitkennungen und Zweck, Prüfstand, Push-Ergebnis und welche eigenen
Arbeiten noch offen sind. `ROADMAP.md` nur fortschreiben, wenn die Einheit
das erfordert. Bei einem Fehler nach dem Commit den Besitzer informieren,
fehlende zusammengehörige Änderungen zuerst prüfen und vorwärts korrigieren;
keine History umschreiben.

Historische Ursachen, Zahlen und überholte Reparaturversuche stehen getrennt
in [references/git-fehlerfaelle.md](references/git-fehlerfaelle.md). Sie sind
Diagnosematerial und **keine aktuelle Handlungsanweisung**.
