---
name: was-die-suite-nicht-findet
description: "Sechs Fehler an einem Tag, sechs verschiedene Finder, kein einziger davon pytest — ein grüner Lauf ist eine Aussage über die Tests, die man geschrieben hat, und über nichts sonst."
metadata:
  type: feedback
---

**Am 25.08.2026 sind sechs Fehler in meiner eigenen Arbeit gefunden worden, und
die Suite hat keinen davon gefunden.** Gezählt wurde nicht, um sich zu geißeln,
sondern weil die Liste der *Finder* etwas sagt, das keine einzelne
Fehlerbeschreibung sagt:

| Fehler | Wer ihn fand |
|---|---|
| Gruppe des Rezepts würde `InternalError` werfen | ein Bildschirmfoto (der Wert stand deutsch im portugiesischen Dialog) |
| Drei Feldzeilen ohne Angabe, zu welchem Parameter sie gehören | dasselbe Bildschirmfoto |
| Eine von drei Knopfbedingungen war ungeprüft | eine Mutation im Code, nicht im Test |
| `op_ids` als Plätze statt IDs — der letzte Schritt fiel aus jedem Rezept | eine Nachbarsitzung im echten Fenster |
| Szene und Körper sind Wörterbücher — Kennungen statt Merkmale weitergereicht | das Lesen des Typs, weil ein `getattr(…, default)` verdächtig aussah |
| Ein deutscher Bezeichner unter 142 | eine vollständige AST-Durchsicht, angeregt von einer Nachbarsitzung |

Dazu am selben Tag: *Einpassen* wirkte im Skizzenmodus überhaupt nicht (Kamera
vor und nach dem Druck identisch), und ein Test, den ich dafür geschrieben
hatte, rechnete die Formel nach statt die Methode zu rufen — er blieb grün, als
der Fehler zurück in den Code gesetzt wurde.

**Why:** Ein grüner Lauf ist eine Aussage über die Tests, die man geschrieben
hat, und über nichts sonst. Er sagt nichts über das, was keinen Test hat, und
er sagt besonders wenig über die Nähte zwischen zwei Modulen: Dort baut jeder
Test die eine Seite selbst und bekommt die andere als Attrappe — und eine
Attrappe bestätigt die Annahme, die man beim Schreiben hatte. Vier der sechs
Fehler oben liegen genau dort.

**How to apply:** Nach einer Änderung an der Oberfläche gilt die Reihenfolge
**ansehen, mutieren, durchfahren** — und zwar zusätzlich zur Suite, nicht
statt ihrer.

* **Ansehen** heißt: das Fenster rendern und das Bild lesen, unter der echten
  Plattform und in einer fremden Sprache ([[oberflaeche-von-hand-fahren]]).
  Zwei der sechs standen im Bild und in keinem Testergebnis.
* **Mutieren** heißt: jede Bedingung einzeln kaputt machen und den Test dabei
  ansehen — **im Code, nicht im Test**. Eine Gegenprobe, die den Test ändert,
  prüft, ob der Test zu sich selbst passt ([[sollwert-aus-dem-pruefling]]).
* **Durchfahren** heißt: den Weg gehen, den der Kunde geht, vom Knopf bis zum
  Ergebnis. Die Methode dahinter zu rufen prüft die Methode und nicht den Weg.

Und wenn ein Prüfstand nichts findet, ist die erste Frage, ob er etwas
angesehen hat ([[messwerkzeug-misst-sich-selbst]]): Mein Sprachprüfstand baute
denselben Dialog sechsmal auf Deutsch, schrieb sechs Dateien und sah
vollständig aus. Dieselbe Falle wie ein Verbotstest über eine leere Menge.

Verwandt: [[eine-kette-endet-am-letzten-glied]], [[text-gesetzt-heisst-nicht-gezeigt]].
