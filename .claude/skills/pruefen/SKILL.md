---
name: pruefen
description: >
  Führt das vollständige Tor von Solidon aus — pytest, ruff check, ruff format
  --check und mypy über die virtuelle Umgebung — und meldet das Ergebnis
  zusammengefasst. Benutzen, bevor etwas als fertig gilt, vor jedem Commit und
  nach jedem Arbeitsschritt an app/ oder tests/.
argument-hint: "[optional: Testdatei oder -pfad]"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Prüfen

Vier Läufe. Rot heißt nicht fertig — es gibt keine Ausnahme, keine
„unwichtige" Warnung und kein „das war vorher schon so", ohne dass du es
nachweist.

## Ablauf

Wenn ein Argument übergeben wurde, läuft `pytest` nur darauf; die anderen drei
Läufe bleiben vollständig.

```
.venv\Scripts\python.exe -m pytest -q $ARGUMENTS
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

Alle vier ausführen, auch wenn einer früh fehlschlägt — ein vollständiges Bild
ist mehr wert als ein schneller Abbruch. Fehlt `.venv`, sag das mit dem
Einrichtungsbefehl aus `CLAUDE.md`, statt auf das System-Python auszuweichen.

## Melden

Eine Zeile je Lauf: bestanden oder nicht, bei Fehlschlag die Anzahl und die
betroffenen Dateien. Danach die Fehler selbst, gruppiert nach Ursache — nicht
die rohe Ausgabe durchgereicht.

`ruff format --check` meldet nur, dass eine Datei anders aussehen würde. Das
behebst du mit `ruff format .` ohne Rückfrage. Alles andere ist eine
inhaltliche Änderung: erst verstehen, warum der Lauf rot ist, dann beheben —
nie einen Test anpassen, damit er grün wird, und nie eine Warnung
unterdrücken, die `filterwarnings = ["error"]` absichtlich zum Fehler macht.

## Danach

War alles grün und es liegen ungestagte Änderungen vor, nenne den nächsten
Schritt: committen (`/liefern`) oder weiterarbeiten. War etwas rot, ist der
nächste Schritt die Behebung — nicht der Commit.
