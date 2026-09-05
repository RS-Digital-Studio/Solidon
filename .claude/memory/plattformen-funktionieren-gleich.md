---
name: plattformen-funktionieren-gleich
description: "Robert (05.09.2026) — alles soll auf jeder Plattform gleich funktionieren; ein Weg, der nur unter Windows geht, ist ein Fehler und keine Entscheidung"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 95e497f0-4c76-4675-bd77-72812e9a19e3
  modified: 2026-09-05T10:26:13.802Z
---

Robert am 05.09.2026, nachdem das macOS-Update an der Download-Seite endete
und die 3D-Maus auf dem Mac still blieb: „es sollte schon alles bei jeder
Plattform gleich funktionieren." Beides wurde daraufhin nachgebaut, nicht
dokumentiert.

**Why:** Der Kunde kauft die Anwendung, nicht die Plattform; ein Mac-Kunde,
der das Paket von Hand holen muss, während Windows es einspielt, erlebt ein
schlechteres Produkt für denselben Preis. Begründungen im Code („LaunchServices
erbt den Deskriptor nicht") beschreiben ein Hindernis, sie rechtfertigen keine
dauerhafte Lücke.

**How to apply:** Wer einen Weg für eine Plattform baut oder behält, baut ihn
für alle drei oder trägt die Lücke als offenen Punkt ins Register — nicht als
Entscheidung in den Docstring. Plattformzweige als Parameter bauen, damit sie
auf jeder Maschine prüfbar sind (`install_kind(system)`, `default_reader(platform)`).
Offen nach diesem Muster: das AppImage ersetzt sich noch nicht selbst.
Verwandt: [[aus-kundensicht-perfekt]], [[zusage-ueber-die-umgebung]].
