---
name: handbuch-nur-beim-paketbau
description: "Robert, 12.09.2026: Das Handbuch wird nur noch beim Erstellen der Pakete erzeugt — test_wording ist zwischen Releases deshalb rot, und das ist kein Fund."
metadata:
  node_type: memory
  type: feedback
---

Robert am 12.09.2026, als `test_wording` sechsmal rot war, weil die erzeugten
Handbuchseiten hinter den Registertexten am HEAD lagen: „handbuch nur noch bei
erstellen der pakete machen".

**Why:** Ein `make_manual`-Lauf erzeugt sechs Sprachen samt PDFs und kostet
Minuten; zwischen zwei Releases ändern sich Registertexte laufend, und jeder
Lauf dazwischen wäre am nächsten Tag wieder veraltet. Die Regel steht schon in
AGENTS.md („Bilder und Handbuch nur beim Release"); neu ist die Folge für das
Tor: `test_every_manual_paragraph_reaches_the_generated_page` **darf** zwischen
Releases rot sein.

**How to apply:** Ein rotes `test_wording` gegen die erzeugten Seiten ist kein
Fund und wird nicht durch einen Handbuchlauf „behoben". Es gehört in die
Reihenfolge von `/erzeugen` beim Paketbau. Nur wenn ein Test in `test_wording`
etwas anderes als die erzeugten Seiten prüft, ist Rot ein Fund. Siehe
[[erzeugtes-laeuft-nicht-in-der-ci]] (dieselben Tests tragen den Marker
`rendered`) und [[make-manual-kennt-kein-help]].
