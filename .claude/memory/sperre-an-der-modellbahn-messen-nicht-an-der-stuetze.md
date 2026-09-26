---
name: sperre-an-der-modellbahn-messen-nicht-an-der-stuetze
description: Eine Stützsperre, die der Slicer als Kunststoff druckt, verdrängt die Stütze auch — Wirkung einer Sperre immer an der Modellbahn mit und ohne Sperre prüfen.
metadata:
  type: feedback
---

Am 25./26.09.2026 (RM-247) galt die Kanalsperre als belegt: im ElegooSlicer
„Gitter überall" 22,9 → 0,5 m Stütze im Wasserkanal, „Baum nur vom Bett"
6,2 → 0,7 m. Tags darauf zeigte ein Rücklesen des vom Slicer gespeicherten
Projekts ein Teil `normal_part` mit dem Volumen von Schüssel **und** Sperre:
Der ElegooSlicer las Solidons Orca-Beilage, übersah die Bereichsart der
Prusa-Beilage und druckte die Sperre als Kunststoff — 161,8 statt 49,5 m
Modellbahn im Kanal, 22,8 g mehr. Die Stütze war weg, weil der Kanal voll war.

**Why:** Gemessen war nur die Größe, die sich ändern sollte (Stütze). Ein
Pfropfen senkt sie genauso wie eine wirksame Sperre. Die Gegengröße (Modellbahn,
Filament) stand in derselben G-Code-Datei und wurde nicht gelesen.

**How to apply:** Jede Änderung an dem, was der Slicer als Hilfsgeometrie
bekommt (Sperre, Verstärker, Modifikator), wird mit und ohne sie geschnitten
und an **beiden** Größen gemessen: Modellbahn und Filament müssen gleich
bleiben, erst dann zählt die Stütze — und die im Sperrkörper selbst, nicht in
einer Nachbarregion. Je Slicerfamilie getrennt: Jede liest nur ihre
Schreibweise (`slicer_keys.helpers_as_parts`), PrusaSlicer zusätzlich nur mit
`slic3rpe:Version3mf`. Sonde: `sperre_gegenprobe.py` im Scratchpad der Sitzung
(Bauart in [[uebergabe-je-modell-slicer-drucker]]); siehe auch
[[index-messen-und-pruefen]].
