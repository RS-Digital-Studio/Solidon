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
| `plan.py` | Welche Operation eine Datei einliest — für Fenster und Kommandozeile; `names_in_use` nennt die im Stapel vergebenen Objektnamen, damit der Plan einen freien wählt; `is_only_imported` sagt umgekehrt, ob ein ganzes Dokument nichts als eingelesene Dateien trägt (RM-130) |
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
- **Native 3MF-Farben**: Werkzeugpaletten aus Orca/Bambu-Projektmetadaten
  oder Prusa-Konfiguration, Objektwerkzeuge, objektspezifische Part-Werkzeuge
  und bemalte Dreiecke werden als Materialslots übernommen. Prusa-Volumen
  behalten ihre Dreiecksbereiche. **Teilflächenbemalung wird gelesen, nicht
  vergröbert**: `_decode_paint` liest den Bitstrom von
  `TriangleSelector::serialize` (PrusaSlicer, Bambu Studio, Orca), und
  `_refine` teilt die Dreiecke so, wie der Slicer sie beim Malen geteilt hat,
  Mittelpunkte über beide Seiten einer Kante geteilt, T-Stöße zu ungeteilten
  Nachbarn geschlossen. Was sich an Farben nicht lesen lässt, hält den Import
  **nicht** an (Entscheidung Robert, 14.09.2026): Der Körper kommt
  einfarbig, der Grund steht als Befund `ingest.colours_dropped` im
  Prüfbericht — je Körper, nicht je Datei; eine unlesbare Palette meldet
  `ingest.palette_dropped` für alle. **Der Rat dazu steht im Satz**, nicht
  in `suggestions`: Der Prüfbericht zeigt nur Handlungen mit Handler, und für
  „im Slicer nach Filamenten aufteilen" gibt es keinen. Ein Bemalungscode
  tiefer als `MAX_PAINT_DEPTH` ist ein Befund, kein `RecursionError`.
- **Was der Slicer außer druckbaren Teilen in ein Objekt legt**: Modifikator,
  Stützblocker und Stützverstärker (`HELPER_KINDS`) sind keine Geometrie des
  Drucks und werden übersprungen (`ingest.helper_skipped`); eine Aussparung
  (`negative_part`) wird von jedem druckbaren Teil ihres Objekts abgezogen
  (`ingest.negative_carved`), über die Rückfallkette des Kerns; die Stufe
  steht am Befund und als `Part.solver` am Körper, die `load`-Operation
  meldet die tiefste aller Körper (§17.2). Eine Art, die keiner kennt, ist
  ein Körper — geladen und gezählt, mit `ingest.unknown_part_kind` daneben.
  Der Zählweg (`_scan`) und der Leser fragen dasselbe Prädikat `_is_body` —
  die Körperzahl steht fest, bevor gerechnet wird (§11). **Das gilt für
  Bambu, Orca und Elegoo** (`subtype` in `model_settings.config`);
  PrusaSlicer führt Modifikator und Aussparung als `volume` im selben Netz,
  und dort wird nichts abgezogen: Der Körper kommt einfarbig, und
  `ingest.foreign_volume` sagt, dass der Bereich als Material geladen ist.
  Bleibt danach kein druckbarer
  Körper, ist das eine Absage (`no_printable_part`) und keine leere Liste:
  Leer hieße für `load` „keine lesbare 3MF", und der allgemeine Leser lüde
  die Aussparung als Körper.
- **`model_settings.config` wird ohne Namensräume gelesen** (`_slicer_config`):
  Bambu Studio und der Elegoo-Slicer schreiben ein SVG-Relief als
  `<slic3rpe:shape …/>` ohne den Präfix je zu deklarieren.
- **GLTF darf Begleitdateien haben.** Beim lokalen Import werden Puffer und
  Bilder aus demselben Ordner eingebettet; Verweise aus dem Ordner heraus
  bleiben gesperrt.
- **Herkunft** wird vermerkt (`scene/foreign.py`, §32): Der Nutzer soll
  wissen, woher der Inhalt stammt.

## Grenzen

- Ein Fehlerbild wird eine **Testdatei** in `tests/data/`, kein Sonderfall im
  Code.
- Nichts aus einer geöffneten Datei wird ausgeführt (Regel 13).
- Modelldownloads laufen immer über `fetch._open_download` und die gemeinsame
  HTTP-Grenze: geprüfte Weiterleitungen, Gesamtfrist einschließlich Headern
  und eine begrenzbare Leseantwort. Tests ersetzen nur den Transport; einen
  öffentlichen Umgehungsparameter gibt es nicht.
