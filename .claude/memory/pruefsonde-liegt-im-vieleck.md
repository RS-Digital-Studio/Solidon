---
name: pruefsonde-liegt-im-vieleck
description: Eine Prüfsäule oder Randprobe gegen ein facettiertes Werkzeug muss im Innenkreis des Vielecks liegen und darf einer einzelnen Kantenprobe nicht glauben
metadata:
  type: project
---

Gefunden am 25.09.2026 beim Nachprüfen von RM-220 an neuen Modellen aus
`F:\3D Dateien`: Eine Furnierplatte (0,6 mm, Bohrungen Ø 6,1 als 32-Eck)
meldete nach jedem Versetzen „geht nicht mehr durch", bei unverändertem
Volumen. Die Säule der Durchgangsprüfung war 0,02 mm dünner als der
Durchmesser — dicker als der Innenkreis des 32-Ecks, das als Werkzeug
versetzt wird. An jeder Sehne blieb ein Splitter von 0,0001 mm³.

**Why:** Versetzt wird der Flächenkörper aus der Datei, nicht ein Kreis. Ein
Maß aus dem Merkmal (Durchmesser) beschreibt den Umkreis; was der Schnitt
wirklich frei macht, ist der Innenkreis. Und eine einzelne Probe an einer
Kante antwortet über `on_surface` mit der Normale der falschen Fläche: eine
von 32 Proben „im Material" machte eine glatt geschnittene Kopie „zugedeckt".

**How to apply:**
- Eine Säule oder Probe gegen ein Werkzeug misst dessen Wand
  (`prepare_ops._inscribed_radius`), nicht das Merkmalsmaß.
- „Überall Luft" (alle Proben) ist die richtige Frage für „offen"; für
  „zugedeckt" zählen (`_share_in_material`, `COVERED_SHARE`).
- Einen Befund an einem echten Modell gegen den alten Stand fahren: Kommt er
  dort auch, ist er alt — aber nicht deshalb richtig.

Siehe [[index-messen-und-pruefen]] und [[verifikation-an-echten-modellen]].
