---
name: verweis-auf-nichtexistierendes
description: "Ein Text, der auf einen anderen Baustein zeigt, behauptet etwas über das Register — und das kann man nachschlagen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b6adb6f-44db-47df-ab5f-c380db59d248
  modified: 2026-08-25T12:49:30.280Z
---

Ein Verweis auf etwas Nichtexistierendes liest sich genauso glatt wie einer auf
etwas Vorhandenes. Am 24./25.08.2026 stand in einem Baustein-caveat „dafür ist
der Schraubdom da" — im Register gab es nie einen Baustein dieses Namens. Der
Satz überlebte drei Durchgänge: den des Schreibenden (3d-druck-b0), meinen beim
Übersetzen in fünf Sprachen, und einen Review.

**Why:** Kein Werkzeug prüft es. `ruff` sieht Zeilenlängen, `test_translations`
sieht Vollständigkeit, der Übersetzer sieht Grammatik. Ob der genannte Baustein
existiert, sieht niemand — die Prüfung liegt außerhalb dessen, was ein Text über
sich selbst aussagt. Und der Satz *warf keine Frage auf*: Er klang plausibel,
also fragte niemand.

Das ist nicht dasselbe wie [[texte-altern-mit-ihrer-grenze]], wo ein Text mit
dem altert, worauf er zeigt. Hier war der Verweis von Anfang an leer.

**How to apply:** Nennt ein Text einen Baustein, eine Operation, einen Parameter
oder eine Datei — nachschlagen, bevor er stehenbleibt. Das Register ist eine
Liste von 23 Namen, `PARTS.get("boss")` antwortet in einer Sekunde. Beim
Übersetzen gilt es genauso: Eine Übersetzung ist nicht die Stelle, an der ein
falscher Verweis entsteht, aber sie ist eine Stelle, an der er auffallen kann —
und sie vervielfacht ihn in fünf Sprachen.

Verwandt: [[messwerkzeug-misst-sich-selbst]] (was ein Werkzeug meldet, ist eine
Eigenschaft des Werkzeugs) und [[eine-kette-endet-am-letzten-glied]] (eine
zutreffende Begründung kann eine Lücke decken).
