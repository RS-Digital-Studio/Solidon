---
name: sonde-im-geteilten-baum
description: Eine Messung, die den Bestand verändert, gehört in einen eigenen Arbeitsbaum — im geteilten misst man, aber man baut nicht um.
metadata:
  type: feedback
---

Am 30.08.2026 habe ich einen Zähler in `app/ui/leash.py` eingebaut, um zu messen,
wie oft ein Codezweig wirklich läuft. Vier andere Sitzungen arbeiteten im selben
Baum. Innerhalb von zwei Minuten meldete eine davon, dass ihr Tor stehe.

**Der Syntaxfehler war nicht das Problem, sondern der Ort.** Ein Heredoc hatte
mir das `\n` gefaltet ([[heredoc-verschluckt-backslash-n]]), und die Datei parste
nicht mehr. Aber selbst mit heiler Syntax wäre das Tor rot geworden: Der
Sondenimport steht nicht am Dateikopf, und `ruff` sagt dazu `E402`. Die kaputte
Klammer hat nur beschleunigt, was ohnehin passiert wäre.

**Why:** Eine Sonde ist per Definition Code, der nicht bleiben soll — unsauber,
ungeprüft, mit Nebenwirkungen auf jeden, der dieselbe Datei anfasst. Im
geteilten Baum ist jede Sekunde ihrer Anwesenheit ein rotes Tor für alle
anderen, und sie können den Grund nicht sehen: In *ihrem* Gebiet ist alles in
Ordnung. Der Unterschied zu einer normalen Änderung ist, dass eine Sonde
absichtlich nicht durchs Tor soll — sie kann also nie „kurz drinbleiben, bis es
grün ist".

**How to apply:** Verändert eine Messung den Bestand, wird sie in einem eigenen
Worktree gefahren:

```
git worktree add "$TEMP/<name>" HEAD --detach
# die eigenen geänderten Dateien hineinkopieren, Sonde dort einbauen
cd "$TEMP/<name>" && "<hauptbaum>/.venv/Scripts/python.exe" -m pytest ...
```

Der Baum braucht keine eigene `.venv` — das Python des Hauptbaums findet `app`
über das Arbeitsverzeichnis. Danach `git worktree remove`, und der Baum ist ein
Zustand und kein Diff ([[probe-worktree-altert]]).

Im geteilten Baum bleibt, was **nur liest**: Läufe, `git diff`, Zählungen. Die
Grenze ist nicht „klein oder groß", sondern „verändert den Bestand oder nicht".

**Und der Baum fällt danach.** Roberts Betriebsregel vom 30.08.2026: am Ende
keine getrennten Worktrees, alles auf main. Ein stehengebliebener Messbaum ist
kein Archiv, sondern eine Falle — er ist ein vollständiger Zustand, kein Diff
([[probe-worktree-altert]]), und am selben Tag standen 25 davon mit 11 GB
herum, sechs eigene vom Vortag. `git worktree remove`, sobald die Zahl da ist.

Verwandt: [[parallele-sitzungen-solidon3d]], [[temp-dateien-sind-maschinenweit]],
[[sondenbau]] — dort steht, wie eine Sonde falsch *misst*; hier steht, wo sie
falsch *steht*.

**Eine Mutations-Gegenprobe ist eine solche Sonde, und das ist nicht
offensichtlich.** Ich hatte diese Notiz auf Messungen bezogen, die *lesen*.
Eine Gegenprobe **schreibt zweimal**: die Mutation hinein, den Bestand zurück.
Am 30.08.2026 hat mein `finally`-Rückbau in `main_window.py` den Stand einer
Nachbarsitzung überschrieben, die zwischen meinem Lesen und meinem
Zurückschreiben getippt hatte — und der nächste Schreibversuch scheiterte mit
`OSError: Invalid argument`, weil sie gleichzeitig in derselben Datei war.
Verloren war am Ende nur meine eigene Zeile, aber das war Glück.

Der Fehler davor ist derselbe wie bei `commit -o` und `update-index`: **Die
Datei ist die geteilte Einheit, nicht die Zeile.** Wer die ganze Datei
zurückschreibt, verwirft jede fremde Zeile, die inzwischen dazugekommen ist.

Gegenproben laufen deshalb in einem eigenen Worktree (`git worktree add
--detach <pfad> HEAD`, eigene Dateien hineinkopieren, dort mutieren, Baum
danach entfernen). Und der Schritt davor kostet eine Sekunde: `session_board.py
list` sagt, wer gerade in der Datei sitzt — die erwartete Zahl fängt es
hinterher, die Board-Liste vorher.
