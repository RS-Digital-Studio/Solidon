---
name: arbeiter-verlegt-die-wartezeit-ans-ende
description: "Eine Suche aus dem Konstruktor in einen Arbeiter zu holen entfernt die Wartezeit nur, wenn auch das Schließen nicht auf ihn wartet — sonst steht sie am Ende statt am Anfang, und der Weg über finished bleibt zu."
metadata: 
  node_type: memory
  type: project
  originSessionId: 49da6b80-5991-4fc3-a51f-b6e09a938d38
  modified: 2026-09-13T05:39:43.746Z
---

Druckdialog, 13.09.2026: `find_programs` (3–13 s) kam aus dem Konstruktor in
einen `_SlicerWorker`; der Dialog stand nach 30 ms. Das Tor fand danach zwei
rote Tests am Weg *Filamente …* → Filamentwähler: `done()` wartet über
`_settle` auf **jeden** Arbeiter, und der neue stand in derselben Liste wie
der Slicerlauf, der den Arbeitsordner braucht. Wer gleich *Abbrechen* oder
*Filamente …* klickte, sah bis zu 13 s gesperrte Knöpfe, und `finished` kam
erst nach der Suche — dieselbe Wartezeit, ans Ende verlegt. Einer der beiden
Tests fiel auch allein; der Beheber hatte nur die Datei des Dialogs gefahren.

**Why:** Ein Arbeiter hat zwei Enden, und der Fix hatte nur das vordere
gemessen. Was ein Fenster beim Schließen alles abwartet, ist ein eigener Weg
mit eigenen Tests, und eine Sperre, die einen Ordner schützt, sperrt still
auch das, was den Ordner nicht braucht.

**How to apply:** Wer einen Arbeiter neu anlegt, prüft beide Enden: Öffnen
ohne ihn *und* Schließen ohne ihn. Ein Arbeiter, dessen Antwort nach dem
Schließen niemand will, gehört nicht in die Warteliste von `_settle`; am
Leben hält ihn die Leine (`leash._alive`), `release` wartet beim Abbau, und
`MainWindow.wait_for_workers` fragt über `leash.wait_for_all` nach dem, was
ein weggeräumter Dialog hinterließ — sonst überlebt der Thread den Prozess.
Betroffene Fensterdateien nach einem neuen Arbeiter mitfahren, nicht nur die
des Dialogs (`tools/affected_tests.py`). Siehe [[weg-nie-bis-zum-ende-gemessen]]
und [[eine-kette-endet-am-letzten-glied]].
