---
name: messung-galt-fuer-den-stand-davor
description: "Nach einem Umbau gilt jede frühere Messung nur noch für den alten Stand — und wer nur die Lage nachmisst, die der Umbau betraf, prüft die falsche."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-31T06:57:31.716Z
---

Am 31.08.2026 habe ich das Kopfmenü der Website gebaut: am Rechner eine Leiste,
am Handy ein Aufklapper, aus einem Markup. Gemessen in drei Breiten, alles
grün. Dann kam ein Umbau — die sechs Verweise bekamen einen `<div>` um sich,
damit das Panel am Handy schweben kann statt zu schieben.

**Danach habe ich nur noch bei 375 Punkt gemessen.** Die Handy-Lage war ja die,
die der Umbau betraf. Am Rechner standen die sechs Verweise seitdem
untereinander in einer 160 Punkt schmalen Spalte — alle bei x=1245, auf sechs
Zeilen von 31 bis 177. Es ging so über zwei Commits hinaus und fiel erst auf,
als ich ein Bildschirmfoto für etwas ganz anderes machte.

**Why:** Die Desktop-Messung von vorher war nicht falsch. Sie war *richtig* —
für einen Stand, den es nach dem Umbau nicht mehr gab. Genau deshalb ist sie
gefährlicher als ein Fehler: Ein falscher Wert fällt irgendwann auf, ein
gültiger Wert über einen vergangenen Zustand nie.

Der Denkfehler steckt in „die Lage, die der Umbau betraf". Ein Umbau am Markup
betrifft **jede** Lage, die dieses Markup rendert — die Media Query entscheidet
nur, welche Regeln dazukommen, nicht welche Struktur da ist.

**Die technische Lehre daneben ist eigenständig:** Chromium nimmt den Inhalt
eines geschlossenen `<details>` über `content-visibility` **aus dem Layout**.
Das Element bleibt im Baum, misst null, und seine Kinder liegen alle auf seiner
Position. Eine eigene `display`-Regel macht sie sichtbar — und gibt ihnen
**keinen Platz zurück**. Wer `display` benutzt, um Inhalt aus einem `details`
herauszuholen, bekommt sichtbare Elemente ohne Layout. Die Lösung ist, den
Inhalt gar nicht erst hineinzulegen: Das Panel steht als **Geschwister** neben
dem Aufklapper, und `[open] + .panel` blendet es ein.

**Und die Messung selbst hat gelogen, weil ich sie falsch gefragt habe.**
`offsetParent` und `getBoundingClientRect()` meldeten „sechs sichtbar" —
beide antworten auf „hat es eine Box", nicht auf „ist es zu sehen". Was die
Frage beantwortete: die Positionen **aller** Elemente nebeneinanderlegen. Sechs
gleiche x-Werte sind eine Antwort, „sechs sichtbar" ist keine.

**How to apply:**

* **Nach einem Umbau am Markup jede Lage neu messen, nicht die geänderte.**
  Die Frage ist nicht „was habe ich angefasst", sondern „welche Zustände
  rendern dieses Markup".
* **Eine Zählung ist keine Prüfung.** „Sechs sichtbar" hat hier zweimal
  bestanden, während nichts zu sehen war. Wo eine Anordnung geprüft wird,
  gehören die **Koordinaten** ins Protokoll — gleiche Werte verraten
  Stapelung, verteilte verraten eine Reihe.
* **Ein Bildschirmfoto ist keine Zierde am Ende.** Gefunden hat es das Auge,
  nicht der Wert. Bei allem, was Anordnung betrifft, ist das Foto die
  Messung und die Zahl nur der Beleg.

Verwandt: [[abgelesene-zahl-altert-still]] (dort altert die Zahl im Text, hier
im Kopf des Messenden), [[gemessene-frage-ist-nicht-die-gestellte]],
[[zusicherung-wird-stumpf-ohne-rot-zu-werden]] — auch dort bleibt eine Prüfung
formal gültig und sagt nichts mehr.
