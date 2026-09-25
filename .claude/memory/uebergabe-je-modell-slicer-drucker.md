---
name: uebergabe-je-modell-slicer-drucker
description: "Robert, 25.09.2026 (Waschschüssel): Die Slicer-Übergabe muss für jedes Modell, jeden Slicer und jeden Drucker richtig eingestellt sein — belegt wird das im echten Slicer, nicht an Solidons Tabelle"
metadata:
  type: feedback
---

Robert am 25.09.2026, nachdem die HydroBowl-Waschschüssel mit Solidons
Übergabe im ElegooSlicer auf dem Centauri Carbon 2 schon in Schicht 1–2
scheiterte (Fäden, verschobene Stützen, Stützen im Wasserkanal): „sowas
sollten wir dann aber immer für jedes Modell und Slicer/Drucker richtig
einstellen."

**Why:** Solidon überschreibt das abgestimmte Herstellerprofil mit eigenen
Werten. Jede allgemeine Vorgabe, die dabei nicht zum Drucker passt (150 statt
500 mm/s Leerfahrt), jede Absicht, die nicht vollständig hinausgeht („Gitter"
ohne Muster → Elegoos `rectilinear`), und jede Geometrieregel, die ein Modell
falsch liest (Kanaldecke → „Stützen überall"), macht den Druck schlechter als
das, was der Slicer allein täte. Dann hat Solidon als Vorstufe keinen Wert
([[solidon-ist-die-vorstufe-vor-dem-slicer]]).

**How to apply:**
- Bei jeder Änderung an `advise.py`, `slicer_keys.py`, `handover.py`,
  `print_settings.toml` oder `printers.toml`: die Übergabe an einem echten
  Modell aus `F:\3D Dateien` im echten Slicer schneiden und den G-Code lesen
  ([[slicer-lokal-zum-gegenmessen]], [[verifikation-an-echten-modellen]]) —
  Schicht 1–3 (Stützbahn, Leerfahrten), Stütze in Hohlräumen, Zeit.
- Solidons Werte gegen das Herstellerprofil derselben Maschine abgleichen
  (Erbkette unter `%APPDATA%\ElegooSlicer\system\` bzw. Orcas
  `resources\profiles`); jede Abweichung braucht einen Grund, der am Modell
  oder Material hängt.
- Was eine Maschine kann (Leerfahrt, Tempo, Volumenstrom), gehört in
  `printers.toml`, nicht in die Qualitätsstufe. Stand und offene Reste:
  RM-247 in `ROADMAP.md`.
