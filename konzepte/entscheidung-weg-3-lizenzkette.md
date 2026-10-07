# Weg 3 — Lizenzkette des Erzeugermodells

> **Stand 06.10.2026, gilt.** Die Entscheidung über das Modell hinter Weg 3
> (Bauplan §2.2, Generieren über ComfyUI nach §27) und ihre Gründe stehen hier
> und nur hier. Die Konzepte, in denen sie über den Sommer entstanden ist,
> verweisen hierher. Offene Arbeit führt allein das Register:
> [RM-003](../ROADMAP.md#rm-003) (Lizenzkette und Ersatz) und
> [RM-004](../ROADMAP.md#rm-004) (Abnahme des echten Laufs je Plattform).

## Was gilt

1. **Weg 3 bleibt, ComfyUI bleibt draußen.** ComfyUI steht unter GPL und wird
   als eigener Prozess aufgerufen, nie mitgeliefert (§36, Regel 15). Solidon
   liefert keine Gewichte aus; `app/core/backends/comfy_setup.py` richtet
   Quelltext und Gewichte nur auf Wunsch ein, mit fester Revision.
2. **Ein Erzeugermodell muss für einen deutschen Anbieter verkäuflich sein,
   über die ganze Kette.** Kommerzielle Nutzung und Geltung in der EU werden
   für Quelltext, Gewichte und jedes eingebundene Teil geprüft, nicht nur an
   der Wurzel-`LICENSE` und der Modellkarte. Ein Modell, dessen Lizenz die EU
   ausnimmt, ist für Solidon kein Kleingedrucktes, sondern ein Ausschluss.
3. **Kein nicht-kommerzielles Modell in einem mitgelieferten Graphen.** Der
   Wächter ist `tests/test_backends.py::test_the_shipped_graphs_name_no_non_commercial_model`.
4. **Kundentexte sagen den Stand der Kette, wie er ist.** Handbuch, KI-Seite
   der Website und `README.md` nennen keine pauschale MIT-Freigabe, solange
   ein Teil der Kette sie nicht trägt.
5. **Bis zum Ersatz bleibt TripoSG eingerichtet** (Robert, 01.09.2026, `a81a647cf`: Weg 3,
   TripoSG, ComfyUI und die Medien werden weder entfernt noch deaktiviert noch
   vorsorglich ersetzt). Robert lässt seit dem 06.10.2026 einen Ersatz suchen;
   die Wahl fällt unter RM-003 und nach Punkt 2.

## Wie es dazu kam

| Datum | Was | Beleg |
|---|---|---|
| 12.08.2026 | Hunyuan3D, damals der Formkern, nimmt in seiner Lizenz die EU, das Vereinigte Königreich und Südkorea aus; das Freistellmodell RMBG-2.0 steht unter CC BY-NC 4.0. RMBG-2.0 fliegt sofort, Hunyuan3D bleibt vorerst mit Hinweis in Handbuch und Website | [Konzept Erzeugen, Teil 3](konzept-erzeugen-agent-oberflaeche-2026-08.md), Commit `7d800459b` |
| 20.08.2026 | TripoSG ersetzt Hunyuan3D; Quelltext und Modellkarte weisen MIT aus | [Archiv, 20.08.2026](../ROADMAP-ARCHIV.md#der-erzeuger-steht-jetzt-auf-einer-lizenz-die-hier-gilt-20082026), Commit `d2a9229be` |
| 01.09.2026 | Robert (`a81a647cf`): TripoSG bleibt während der Klärung in Betrieb. Git-Commit und Gewichte fest pinnen, `LICENSE` und `NOTICE` vollständig übernehmen, die im `NOTICE` genannten HunyuanDiT- und FlashVDM-Bedingungen gezielt klären. Kein Blocker für 0.3.0 | [Archiv, P9](../ROADMAP-ARCHIV.md#p9--säule-b-und-farbe) |
| 21.09.2026 | Für den Weg aus Text richtet Solidon auf Wunsch SDXL Base 1.0 ein (CreativeML Open RAIL++-M); es gehört in dieselbe Klärung | RM-003 |
| 23.09.2026 | Robert: Website und `README.md` sagen „wird derzeit geprüft“ statt „MIT, Quelltext wie Gewichte“ | RM-003 |
| 06.10.2026 | Kette der gepinnten Revisionen belegt. Wurzel-`LICENSE` und Modellkarte von TripoSG nennen MIT, aber `triposg_transformer.py`, den jede Erzeugung ausführt, trägt die Tencent Hunyuan Community License und `triposg/LICENSE` die FlashVDM Community License; beide nehmen die EU aus, auch für die Ergebnisse. BiRefNet ist byte-gleich mit dem MIT-Original, seine Trainingsdaten DIS5K sind nur nicht-kommerziell. Kundentexte und Kommentare nachgezogen, Ersatzsuche beauftragt | Commit `d25f12366`, Liste in `app/core/knowledge/data/licences.toml` |

## Was nicht hierher gehört

Die Lizenzprüfung der mitgelieferten Python-Abhängigkeiten (§36,
`app/core/knowledge/licences.py`) ist eine andere Frage: Sie prüft, was im
Paket landet. Diese Notiz betrifft Modelle, die der Kunde auf Wunsch in sein
eigenes ComfyUI holt.
