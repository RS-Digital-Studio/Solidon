# `app/core/ingest/` — die Eingangsstufe

Jede geladene Datei geht dieselben sechs Schritte (§17.1). Was danach in der
Szene liegt, ist normalisiert — der Rest der Anwendung muss nicht mehr wissen,
woher es kam.

Die Regeln stehen in `.claude/rules/dateiformat.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `loader.py` | Die Eingangsstufe selbst — die sechs Schritte; lokale GLTF-Begleitdateien werden sicher eingebettet. `read_model` liest eine Datei aus dem Speicher als einen Körper (3MF als Baugruppe verschweißt), `READABLE_SUFFIXES` ist **die** Liste dessen, was sich öffnen lässt |
| `threemf.py` | 3MF **lesen** — Objekte, Farbgruppen, erklärte Einheit, Baugruppe mit Production-Erweiterung (§17.1, §20). Bis zum 02.09.2026 lag der Leser beim Schreiber in `export/`; die Konstanten des Containers stehen hier, `export/threemf.py` holt sie sich |
| `ops.py` | Die `load`-Operation. **Auch Laden ist eine Operation** und steht im Stapel |
| `plan.py` | Welche Operation eine Datei einliest — für Fenster und Kommandozeile |
| `fetch.py` | Eine Modelldatei aus dem Netz holen (§16.3, §32) |
| `outline.py` | Flache Umrisse mit einer Höhe: SVG und DXF mit Extrusion |

## Warum Laden eine Operation ist

Weil die Auswertung sonst keine reine Funktion wäre. Die Datei ist eine
Quelle, der Ladeschritt steht im Stapel, und ein Projekt lässt sich später
gegen eine geänderte Quelle neu rechnen.

## Was die Stufe entscheidet

- **Einheiten**: STL trägt keine. Erkannt wird aus der Größe, und bei
  Mehrdeutigkeit **wird gefragt** (`ctx.ask`, Regel 21) — nicht geraten.
- **3MF ist eine Baugruppe**, kein Körper. Sie kommt als mehrere Objekte an.
- **GLTF darf Begleitdateien haben.** Beim lokalen Import werden Puffer und
  Bilder aus demselben Ordner eingebettet; Verweise aus dem Ordner heraus
  bleiben gesperrt.
- **Herkunft** wird vermerkt (`scene/foreign.py`, §32): Der Nutzer soll
  wissen, woher der Inhalt stammt.

## Grenzen

- Ein Fehlerbild wird eine **Testdatei** in `tests/data/`, kein Sonderfall im
  Code.
- Nichts aus einer geöffneten Datei wird ausgeführt (Regel 13).
