---
name: pruefstand-ohne-profil-meldet-fremden-fehler
description: "Ein Prüfstand, der den Bedienweg unvollständig nachbaut, meldet einen Produktfehler, den es nicht gibt — am 12.09.2026 an den Kunden berichtet, bevor es auffiel."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 86b78383-e2c6-477b-9f82-d858e7955896
  modified: 2026-09-12T12:47:55.493Z
---

Am 12.09.2026 sollte die Slicer-Übergabe über alle installierten Slicer
gemessen werden. Mein Prüfstand baute `handover.SlicerSetup` mit
`machine_profile`, aber **ohne** `base_process`. Ohne Prozessprofil schreibt
`_orca_process` ein Profil aus 44 Schlüsseln statt 137 — es fehlen die
Bahnbreiten je Bereich —, und OrcaSlicer wie ElegooSlicer brachen jeden
mehrfarbigen Auftrag mit `Flow::spacing() produced negative spacing` ab.

Daraus wurde eine Diagnose, die ich Robert **berichtet** habe: „Mehrfarbige
Körper brechen den Lauf bei Orca und Elegoo ab, Ursache ist das Attribut
`paint_color`." Die Messkette dahin war sauber — Ursache isoliert, Gegenprobe
mit entferntem Attribut, alles reproduzierbar. Falsch war der Aufbau: Der
Druckdialog **hält an**, wenn kein Prozessprofil gewählt ist
(`_process_missing_line`), und wählt sonst eines vor. Den Zustand, den ich maß,
sieht kein Kunde je. Mit Prozessprofil laufen beide Slicer mehrfarbig über
drei Platten durch.

**Why:** Ein Prüfstand, der den Bedienweg „im Wesentlichen" nachbaut, misst
einen Zustand, den die Oberfläche gar nicht zulässt. Die Messung ist dann
korrekt und die Aussage trotzdem falsch — und weil die Messkette sauber
aussieht, prüft man den Aufbau nicht noch einmal. Verwandt mit
[[voraussetzung-im-namen-statt-hergestellt]] und
[[saubere-messung-falsche-frage]], aber der Preis ist höher: Es war eine
gemeldete Produktdiagnose, kein roter Test.

**How to apply:** Wer einen Weg von Hand nachbaut, zählt vorher die Felder,
die die Oberfläche dafür **füllt oder erzwingt** — hier Maschinen- *und*
Prozessprofil — und baut sie alle. Und bevor ein Fund als Produktfehler
hinausgeht: einmal gegen den echten Bedienweg gegenprüfen. Der Satz dafür
heißt „ich habe X nachgebaut; was setzt der Dialog außerdem?", und er kostet
zwei Minuten gegen eine falsche Meldung.
