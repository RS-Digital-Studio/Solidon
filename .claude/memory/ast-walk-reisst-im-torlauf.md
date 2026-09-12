---
name: ast-walk-reisst-im-torlauf
description: "TypeError mitten in ast.walk (『'str' object is not an iterator』, 『'Constant' object is not iterable』) in test_translations und test_foreign — nur im abgekoppelten Torlauf, an wechselnder Stelle, standalone dreimal grün: eine Umgebungsstörung der Abriss-Familie, kein Testfehler."
metadata:
  type: project
---

Am 12.09.2026 in zwei aufeinanderfolgenden Torläufen (tor2, tor3 über
`suite-getrennt.sh`, abgekoppelt per pwsh): `test_every_text_is_translated`
riss einmal bei `[it]`, einmal bei `[fr]` — dieselbe Funktion, `[en]` und
`[es]` davor grün —, und `test_no_operation_runs_a_foreign_program` einmal.
Beide Tests parsen alle Quelldateien und laufen mit `ast.walk` darüber; die
Ausnahme kommt aus `ast.iter_fields` — `for field in node._fields` mit
„'str' object is not an iterator" oder „'Constant' object is not iterable".
Ein Tupel, dessen Iterator ein `str` ist, gibt es in reinem Python nicht.

Gemessen: kein `pytest-randomly`, feste Reihenfolge; die Tests davor in
beiden Dateien rechnen keine Geometrie (Dokument-, Tour-, Katalogprüfungen),
eine Heap-Beschädigung aus eigenem Code scheidet damit aus. Dreimal
nacheinander standalone gefahren (`tests/test_foreign.py
tests/test_translations.py`, 209 Tests): dreimal grün. Der Torlauf davor
(tor1, 11.09.2026, 22:30) hatte den Fehler nicht. Im selben Lauf riss der
Leistungslauf mit Zugriffsverletzung **beim Formatieren einer Fehlermeldung**
(`_pytest._code.code.firstlineno`), nicht im Test.

**Why:** Ein Fehler, der die Stelle wechselt, keine Spur hinterlässt und in
einem frischen Prozess nicht wiederkommt, ist eine Aussage über die Umgebung
und nicht über den Test — dieselbe Familie wie
[[speicherriss-hat-keine-ausloesende-zeile]] und
[[rtree-abstuerze-im-langen-lauf]]. Wer ihn als Testfehler liest, sucht in
Katalogen und Registern nach etwas, das nicht da ist.

**How to apply:** Steht `TypeError` in `ast.walk`/`iter_fields` in einem
Torprotokoll, die betroffene Datei **standalone dreimal** fahren; grün ist
der Nachweis, das Tor zählt trotzdem rot (die Regel aus `CLAUDE.md`: ein
späterer sauberer Lauf ist ein eigener Nachweis). Kommt es standalone wieder
oder häuft es sich über Torläufe, ist die Umgebung dran — CPython 3.14.7 und
die nativen Bibliotheken —, nicht der Test. Nicht in Python nach der Ursache
graben: Es gibt dort keine.
