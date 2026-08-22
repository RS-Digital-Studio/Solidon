---
name: marke-im-span-zerteilt
description: "Nach einer Umbenennung entkommt der alte Name jeder Suche, wenn er im HTML durch ein Tag zerteilt ist — Form<span>werk</span>."
metadata: 
  node_type: memory
  type: project
  originSessionId: 138068b6-212a-4249-851c-c4d91253c692
  modified: 2026-08-08T05:11:54.277Z
---

Der Commit „Aus Formwerk wird Solidon3D, und zwar überall" (`9c420bf`) hat vier
Seiten nicht erwischt: `index.html`, `en/index.html`, `impressum.html` und
`datenschutz.html` trugen den alten Namen noch drei Tage später in Zeile 15 —
als `Form<span>werk</span>`, weil das Logo die zweite Silbe farbig setzt.
`grep -r Formwerk` findet das nicht, und niemand liest die Kopfzeile einer
Seite, die er schon hundertmal gesehen hat.

**Why:** Der Name war nicht beliebig. Er ist gefallen, weil eine
Wort-/Bildmarke „3D FORMWERK" für „Entwurf von 3D-Modellen für den 3D-Druck"
bestandskräftig wurde — also für genau das, was die Seite anbietet. Der alte
Name stand damit an der prominentesten Stelle des Angebots, das ihn nicht mehr
führen darf.

**How to apply:** Nach jeder Umbenennung zusätzlich zur Wortsuche eine Suche,
die Tags überspringt — `grep -rEn "Form[^a-zäöüß]{0,30}werk"` findet die
zerteilte Form. Dasselbe gilt für jeden Wert, der in der Oberfläche gestaltet
wird: Marken in Logos, Versionsnummern mit hervorgehobener Hauptziffer, Preise
mit eigener Auszeichnung für die Nachkommastellen. Wo ein Wort optisch geteilt
ist, ist es im Quelltext zerteilt.

Verwandt: [[parallele-sitzungen-solidon3d]] — dieselbe Datei kann gleichzeitig
von einer zweiten Sitzung umgebaut werden.
