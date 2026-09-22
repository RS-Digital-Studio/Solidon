---
name: verifikation-an-echten-modellen
description: "Robert (22.09.2026, „für immer\"): Tests und Verifikation an richtigen Modellen aus F:\\3D Dateien fahren, nicht an unseren eigenen einfachen — die synthetische Platte findet, was sie kennt"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-22T06:42:10.608Z
---

Robert am 22.09.2026, nachdem der Halter mit Wabenmuster in einer Sitzung
fünf Befunde lieferte, die keine Platte aus `trimesh.creation.box` je gezeigt
hätte (Merkmalsgrenze, Felder am Bildrand, Langlochzug, Doppelschritt am
Einlauf): „Auch merken und das für immer: Tests und Verifikation am besten an
richtigen Modellen in F:\3D Dateien machen und nicht an unseren eigenen
einfachen."

**Why:** Eine selbst gebaute Platte hat die Eigenschaften, die ihr Erbauer
kennt — rechte Winkel, saubere Nähte, eine Bohrung an der Stelle, die der
Test erwartet. Ein Kundenmodell hat 1 213 Merkmale, Float32-Ecken, T-Stöße,
schräge Mündungen und 220 mm Ausdehnung, und genau daran fielen die Fehler
auf (siehe [[eigene-toleranz-gilt-nicht-fuer-fremde-netze]],
[[downloads-ordner-als-3mf-korpus]]).

**How to apply:** Jede Verifikation einer Änderung — Sonde, Gegenprobe,
Abnahme — zuerst an einem passenden Modell aus `F:\3D Dateien` (STL, 3MF,
STEP) fahren; die synthetische Platte bleibt für den Sollwert mit Herkunft
im Test (`tests.md`), ersetzt aber nicht die Messung am echten Teil. Wer
keinen passenden Fall im Ordner findet, sagt das und nennt, welches Modell
fehlt. Für eingecheckte Tests gilt weiter die Lizenzfrage: Ein Kundenmodell
wandert nicht nach `tests/data/`, ohne dass Robert es freigibt — die Sonde
läuft dann außerhalb der Suite, und ihr Ergebnis steht im Commit.
