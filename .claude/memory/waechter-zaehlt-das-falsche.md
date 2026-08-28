---
name: waechter-zaehlt-das-falsche
description: "Ein Test mit einem Wächter „prüft mein Aufbau überhaupt etwas" muss die Größe zählen, an der er scheitert — nicht eine, die immer stimmt."
metadata:
  type: feedback
---

**Der Wächter eines Tests muss die Größe messen, an der der Test scheitert.**
Am 27.08.2026 schrieb ich einen Anschlusstest: Der Menüweg, den der Kern nennt
(`menu_path`, gelesen von Handbuch, Agent und Tour), muss der Weg sein, den das
Fenster baut. Zuordnung über `action.data()`, und darunter mein Wächter:

```python
assert gebaut, "keine Operation im Menü gefunden — dann prüft dieser Test nichts"
```

Von 158 Menüeinträgen tragen **sechs** ein `data`, und keiner davon ist eine
Operation — es sind zwei Themen und vier Navigationsarten. Der Test sammelte
diese sechs, verglich **null** Operationen und war grün. In der Mutationsprobe
blieb er grün, obwohl `menu_path` auf die alte, falsche Frage zurückgesetzt war.

Der Wächter war da, war formuliert, und **fragte das Falsche**: „ist das
Wörterbuch voll" statt „stehen darin Operationen". Gerettet hat es nur die
Mutationsprobe — ohne sie hätte ich einen Anschlusstest vorgelegt, der nichts
anschließt.

**Why:** Ein solcher Wächter ist genau dafür da, dass ein Test nicht über eine
leere Menge iteriert und dafür grün gemeldet wird. Er schützt aber nur, wenn er
**dieselbe** Menge zählt, über die der Test läuft. `gebaut` und „die
Operationen, die verglichen wurden" waren zwei verschiedene Mengen, und
zwischen ihnen lag der ganze Fehler. Verwandt mit
[[messwerkzeug-misst-sich-selbst]] (zu weit, zu eng, gar nicht — hier: gar
nicht) und mit [[fuenf-tests-eine-lage]], aber eigenständig: Dort waren die
Tests blind, hier war der Wächter blind, der die Blindheit hätte melden sollen.

**How to apply:** Der Wächter zählt, was die Zusicherung durchlaufen hat, nicht
was der Aufbau gesammelt hat — also eine Variable, die **innerhalb** der
Schleife hochgezählt wird, hinter dem `continue`:

```python
verglichen += 1
...
assert verglichen >= 60, f"nur {verglichen} … — dann prüft dieser Test seine Zuordnung"
```

Die Zahl deutlich unter den Bestand setzen, damit sie nicht bei jedem Zuwachs
reißt, und **über** null, damit sie überhaupt trägt. Und: Jeder Test, der eine
Zuordnung zwischen zwei Welten herstellt (Kern gegen Fenster, Katalog gegen
Code), bekommt eine Mutationsprobe — die Zuordnung selbst ist die Stelle, an
der so ein Test still wird ([[was-die-suite-nicht-findet]]).
