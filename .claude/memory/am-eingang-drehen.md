---
name: am-eingang-drehen
description: "Eine Messung, die auf jede Änderung dieselbe Antwort gibt, misst nichts — einmal absichtlich am Eingang drehen kostet dreißig Sekunden."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-31T07:52:53.002Z
---

Wer eine Größe misst, dreht einmal **absichtlich am Eingang** und sieht nach,
ob sich das Ergebnis bewegt. Bewegt es sich nicht, misst die Messung nicht,
was man glaubt — und zwar unabhängig davon, ob man den richtigen Wert kennt.

Am 31.08.2026 zweimal an einem Tag, in zwei Sitzungen:

* Eine Breitenmessung an einer zugeklappten `<details>` gab für 891 und für
  530 Punkte **denselben** Wert (81 Zeichen je Zeile). Chromium nimmt den
  Inhalt einer geschlossenen Klappe über `content-visibility` aus dem Layout.
  Beinahe wäre eine CSS-Regel auf diesen Zahlen gebaut worden.
* Eine Sichtbarkeitsmessung meldete „sechs sichtbar", während sich darunter
  alles verschoben hatte — zweimal dieselbe Zahl über zwei verschiedene
  Zustände.

**Why:** Das ist die billigere Schwester von
[[messwerkzeug-misst-sich-selbst]]. Dort prüft man an einem Fall, **dessen
Ausgang man kennt** — das ist schärfer, setzt aber voraus, dass es so einen
Fall gibt. Hier genügt eine beliebige Variation: Man muss nicht wissen, was
herauskommen soll, nur dass sich *etwas* ändern muss. Deshalb geht es immer
und kostet nichts. Und es erkennt den Fall ohne technischen Hintergrund: Dass
eine tote Zahl nicht antwortet, sieht man, ohne `content-visibility` zu
kennen.

**How to apply:** Vor jedem Schluss aus einer Messreihe einen Eingangswert
verändern, von dem das Ergebnis abhängen **muss** — die Breite, die Anzahl,
die Datei, das Thema. Bleibt die Ausgabe gleich, ist der Weg zwischen Eingang
und Messpunkt unterbrochen; erst danach lohnt die Frage, wo. In einer
Messreihe fällt das von selbst auf, sobald man **mehr als zwei** Werte fährt
und sie nebeneinanderlegt — eine Reihe aus vier Breiten mit vier gleichen
Antworten liest sich anders als ein einzelner Wert, der plausibel aussieht.
