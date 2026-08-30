---
name: exakte-passung-ist-kein-beweis
description: "Ein Wert, der aus N Kandidaten exakt passt, ist eine Korrelation mit N Kandidaten. Die Messung kann stimmen und die Schlussfolgerung daraus trotzdem erfunden sein."
metadata:
  node_type: memory
  type: feedback
---

Zwei Tests kippten am 30.08.2026 in großen Läufen und waren einzeln grün.
Einer davon meldete `assert 270 <= 260` — die Parameterkarte war zehn
Bildpunkte zu breit.

Ich habe den Testaufbau in allen sechs Sprachen gemessen:

| de | en | fr | es | it | pt |
|---|---|---|---|---|---|
| 258 | 246 | **270** | 234 | 222 | 234 |

Französisch trifft die Zahl **exakt**. Dazu passte, dass `tests/conftest.py`
die Anzeigeeinheit nach jedem Test zurücksetzt und die Sprache nicht — eine
echte Lücke, mit einer Begründung im Docstring der bestehenden Fixture, die
wörtlich für beide gilt. Ursache gefunden, dachte ich, und habe sie
weitergegeben; sie stand eine Viertelstunde später in einem Registereintrag.

**Sie war falsch.** Eine Sonde als pytest-Plugin, die nach *jedem* Test
`get_language()` liest und nur bei Änderung etwas sagt, meldete über **407
Tests null Wechsel**. Die Sprache bleibt durchgehend deutsch. Niemand setzt
Französisch — die 270 sind ein Zusammentreffen, und die Ursache ist bis heute
offen.

## Die Form des Fehlers

> **Ein Wert, der aus N Kandidaten exakt passt, ist eine Korrelation mit N
> Kandidaten — kein Beweis.**

Sechs Sprachen, sechs Breiten, eine trifft auf den Punkt. Das *fühlt* sich
an wie ein Beweis, gerade weil es exakt ist und nicht ungefähr. Aber bei
sechs Kandidaten trifft mit einiger Wahrscheinlichkeit einer, und die
Passgenauigkeit sagt nichts darüber, ob der Weg dorthin existiert.

Das ist die Schwester von [[gemessene-frage-ist-nicht-die-gestellte]], eine
Ebene später: Dort ist die **Messung** die falsche Frage. Hier war die Messung
richtig — 270 *ist* der französische Wert —, und erfunden war die **Kette**
dahinter, also die Behauptung, dass jemand die Sprache setzt.

Verwandt auch mit [[bekannte-familie-erklaert-nicht-den-ausloeser]]: Ein
plausibler Mechanismus ist noch kein Nachweis, dass er in diesem Fall gelaufen
ist.

## Das Gegengift

**Nicht die Passung prüfen, sondern die Kette.** Die Frage lautet nicht „passt
der Wert?", sondern „ist der Weg dorthin je gegangen worden?" — und die
beantwortet keine Tabelle, sondern eine Sonde am laufenden Fall.

Sie kostete zwanzig Zeilen und einen Lauf:

```
def pytest_runtest_teardown(item):
    global _letzte
    jetzt = get_language()
    if _letzte is not None and jetzt != _letzte:
        print(f"[SPRACHE] {_letzte!r} -> {jetzt!r} nach {item.nodeid}")
    _letzte = jetzt
```

Sie meldet **nur bei Änderung** und nennt damit den Verursacher, statt eine
Rate zu liefern. Schweigt sie über den ganzen Lauf, ist die Kette widerlegt —
und zwar vollständig, nicht wahrscheinlich.

Vier Dinge, die dabei zählen:

* **Als Plugin, nicht als Testdatei.** `PYTHONPATH=<ordner>` plus
  `-p <modulname>`; so liegt nichts in `tests/`, was jemand später für eine
  Waise hält.
* **`pytest_runtest_call`, nicht `pytest_runtest_setup`**, wenn der Zustand
  aus einer Fixture kommt: `setup` läuft davor, und die Sonde sieht „keine
  QApplication".
* **Der Startwert der Sonde ist keine Messung.** Meine zweite Sonde — auf das
  globale Stylesheet — übernahm ihren Anfangswert vom ersten Test und meldete
  über den ganzen Lauf **null** Änderungen. Sie verschwieg damit genau den,
  der ihn gesetzt hatte. Eine Sonde, die auf Änderungen wartet, beginnt beim
  bekannten Nullwert, nicht beim vorgefundenen.
* **Die Widerlegung wird genauso gemeldet wie der Fund.** Die falsche Zahl
  stand da schon in einem fremden Register; eine falsche Spur dort kostet den
  Nächsten mehr Zeit als gar keine.

## Und der Fund dahinter war größer als der Fehler

Die echte Ursache war das Stylesheet: null gegen 13 448 Zeichen bei sonst
identischem Zustand. Aber der Reihenfolgefehler war nur der **Aufdecker** — die
Parameterkarte passt in der Betriebslage nicht in ihre Zone, auf jedem Fenster
unter rund 2080 Pixeln. Der rote Test hatte recht, der grüne Einzellauf log.

Wer ihn über eine Rücksetz-Fixture „stabil grün" gemacht hätte, hätte den
Kundenfehler zugedeckt. Zwei Sitzungen hielten genau das für die richtige
Reparatur, bis die Messung kam. Die Lehre steht in
`.claude/rules/tests.md` unter „Isolation heißt Betriebslage, nicht
Nullzustand".
