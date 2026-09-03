---
name: mutation-die-den-fall-nicht-trifft
description: "Bleibt eine Mutation grün, ist zuerst die Mutation verdächtig — nicht der Test; dreimal an einem Abend, drei verschiedene Ursachen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-30T20:52:45.051Z
---

Eine Mutationsprobe hat zwei mögliche Ergebnisse, und man liest fast immer das
falsche: „grün geblieben" heißt **nicht** zwangsläufig „der Test prüft nichts".
Es kann genauso heißen: **die Mutation hat den Fall nicht getroffen.**

Am 30.08.2026 dreimal an einem Abend, mit drei verschiedenen Ursachen:

* **Operator-Präzedenz.** `text = "Token " + tr("1 Schritt") if steps == 1`
  bindet als `("Token " + tr(...)) if …`, greift also nur im Einer-Zweig —
  gemessen wurde mit `steps = 3`. Die Mutation lief ins Leere.
* **Eine Marke, die achtmal dasteht.** `self._pending_world.clear()` kommt in
  `sketch_editor.py` achtmal vor; `str.replace(alt, neu, 1)` erwischte das
  erste Vorkommen und nicht das in der geprüften Methode.
* **Der Test baute seinen Sollwert selbst.** Er setzte den erwarteten Satz im
  Testcode zusammen und fragte, ob ein Wort darin steht — trivial wahr, und
  die Mutation im Produktivcode konnte ihn gar nicht erreichen. Das ist der
  einzige der drei Fälle, in dem wirklich der **Test** kaputt war.

**Why:** Zwei von drei Malen lag es an der Probe, einmal am Test. Wer „grün"
sofort als Testlücke liest, baut Tests um, die in Ordnung sind — und wer es
sofort als Probenfehler abtut, lässt echte Lücken stehen.

**How to apply:** Bei einer grün gebliebenen Mutation **zuerst prüfen, ob sie
überhaupt gegriffen hat**, bevor der Test in Verdacht gerät:

1. Kommt die Marke mehrfach vor? `grep -c` — bei mehr als eins ist der Schnitt
   zu kurz, mehr Kontext hineinnehmen.
2. Liegt die mutierte Zeile im Pfad, den der Test durchläuft? Bei Verzweigungen
   nach Wert oder Zweig: dieselben Eingaben wie der Test.
3. Erst wenn beides stimmt, ist der Test dran — und dann meist auf die Art aus
   [[sollwert-aus-dem-pruefling]].

Verwandt mit [[gegenprobe-bei-geaenderter-bauart]] (dort trifft die Mutation
die neue Bauart, aber die alte war gemeint) und [[rueckbau-kann-scheitern]] —
alle drei sagen dasselbe über Proben, was [[messwerkzeug-misst-sich-selbst]]
über Messwerkzeuge sagt.


## Und dieselbe Form eine Stufe früher: der Aufbau enthält den Fall nicht

Die drei Punkte oben prüfen, ob die **Mutation** greift. Davor liegt eine
Frage, die genauso grün aussieht: Enthält der Prüfstand den Fall überhaupt?

Am 03.09.2026 zweimal an einem Tag, in beiden Richtungen:

* 3d-druck-85 baute für einen Befundtest eine Baugruppe aus zwei sauberen
  Würfeln. Zwei saubere Würfel erzeugen keinen Befund — der Test prüfte eine
  leere Liste und war grün. Erst ein Körper mit einem entfernten Dreieck gab
  ihm seinen Gegenstand.
* Für die Merkmalsbündelung im Objektbaum suchte ich im Korpus ein Modell mit
  vier gleichnamigen Merkmalen und fand keines: `feature_name` nummeriert
  Bohrungen („Bohrung 1"), Verrundungen nicht. Der Fall, den ich prüfen
  wollte, war in zwanzig Testdateien nicht herstellbar — deshalb wurde er nie
  gefunden, und deshalb musste ich die Merkmalsmenge von Hand bauen.

**Wer eine Baugruppe für einen Befundtest baut, baut sie kaputt.** Und wer im
Korpus nichts findet, hat oft nicht schlecht gesucht, sondern gerade den Grund
gefunden, aus dem der Fehler so lange stand.

Verwandt: [[voraussetzung-im-namen-statt-hergestellt]], [[testprojekt-trifft-den-fall-nicht]].
