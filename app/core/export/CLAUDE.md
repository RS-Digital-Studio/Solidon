# `app/core/export/` — hinaus

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29).

Die Regeln stehen in `.claude/rules/dateiformat.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3) |
| `threemf.py` | 3MF **schreiben** — ein Körper oder eine Baugruppe, mit Farbgruppen und Slicer-Beilagen (§20, §29). Gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1) — **2 000 Zeilen**, das größte Modul hier |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt |
| `slicer_profiles.py` | Die Profile finden, die ein installierter Slicer mitbringt |

STEP geht über `brep/step.py`, nicht von hier.

Profilvererbung wird mit sämtlichen Profilwurzeln des gewählten Slicers
aufgelöst: Nutzerprofile können von installierten Profilen erben. Diese
Wurzeln gehören auch in Filamenterkennung, Materialvergleich und Auslesen
der Werte im Druckdialog; der Ordner der Blattdatei allein reicht nicht.

## Warum `slicer_keys.py` existiert

Weil dieselbe Einstellung in Cura, PrusaSlicer, OrcaSlicer und ElegooSlicer
vier verschiedene Namen hat. Eine Übersetzungstabelle an einer Stelle ist der
Preis dafür, dass §29 überhaupt einlösbar ist — verstreute Sonderfälle wären
es nicht.

## Der Slicer wird gerufen, nie mitgeliefert

**Keine GPL-Abhängigkeit** (Regel 15). Ein externer Aufruf ist erlaubt, ein
mitgeliefertes Binärprogramm nicht. Deshalb sucht `slicer_profiles.py`, was
installiert ist, statt etwas mitzubringen.

## Die Prüfung vor dem Export

Sie läuft **vorher**, nicht nachher: Wasserdichtheit, Bauraum, Wandstärken.
Was sie findet, ist ein Befund mit Handlungsvorschlag (Regel 17) — kein
abgebrochener Export.

## Grenzen

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.
- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).
