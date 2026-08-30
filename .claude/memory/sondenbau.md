---
name: sondenbau
description: "Eine Sonde ist ein pytest-Plugin, das nur bei Änderung meldet und in eine Datei schreibt. Fünf Bauarten, an denen sie am 30.08.2026 gescheitert ist — jede sah nach einem Befund aus."
metadata:
  node_type: memory
  type: feedback
---

Wenn ein Test in großen Läufen kippt und einzeln grün ist, ist die Frage nicht
„wie oft?", sondern „**welcher Zustand ist anders?**". Die Antwort gibt keine
Wiederholung, sondern eine **Sonde**: ein pytest-Plugin, das während des
laufenden Falls misst.

```
PYTHONPATH=<ordner> pytest <dateien> -p <modulname>
```

Am 30.08.2026 haben vier Sonden drei Ursachen gefunden — und fünfmal zuerst
sich selbst. Jeder dieser Fehlschläge sah aus wie ein Befund.

## Die Bauform, die trägt

```python
_letzte = 0  # der bekannte Nullwert, nicht None


def pytest_runtest_teardown(item):
    global _letzte
    jetzt = messen()
    if jetzt != _letzte:
        _schreib(f"{_letzte} -> {jetzt} nach {item.nodeid}")
        _letzte = jetzt
```

**Nur bei Änderung melden** — das nennt den Verursacher mit Node-ID, statt
eine Rate zu liefern. Schweigt die Sonde über den ganzen Lauf, ist die
Hypothese widerlegt, und zwar vollständig.

## Fünf Arten, sich selbst zu messen

* **Der Startwert darf nicht vom ersten Test kommen.** `_letzte = None` und
  „beim ersten Mal übernehmen" verschweigt genau den, der den Wert gesetzt
  hat. Meine Stylesheet-Sonde meldete darum **null** Änderungen über einen
  ganzen Lauf, während der Wert die ganze Zeit auf 13 448 stand.

* **`pytest_runtest_call`, nicht `pytest_runtest_setup`**, wenn der Zustand
  aus einer Fixture kommt. `setup` läuft davor; die Sonde sah „keine
  QApplication" und maß den leeren Vorzustand.

* **Kein `-s`.** Es hält das Capture offen, und der Lauf starb zweimal bei 97
  bzw. 95 Fortschrittszeichen an einer Zugriffsverletzung — beide Male **weit
  vor** dem Zieltest, an dem die Sonde überhaupt etwas tut. Der Abriss sah
  aus wie ein weiterer Befund. Geschrieben wird zeilenweise in eine Datei;
  siehe [[messwerkzeug-misst-sich-selbst]].

* **Am Eingang messen, nicht am Symptom.** Statt aus einer späteren Ausnahme
  rückwärts zu raten, das Modulattribut durch eine Unterklasse ersetzen, die
  beim Schreiben den Stack mitschreibt:

  ```python
  class _Wachset(set):
      def add(self, wert):
          if not hasattr(wert, "isRunning"):
              traceback.print_stack(file=datei)
          super().add(wert)


  leash._alive = _Wachset(leash._alive)
  ```

  Ein Lauf, und der Aufrufer steht mit Datei und Zeile da. Kein Eingriff in
  den Produktivcode.

* **Als Plugin, nicht als Testdatei.** Eine `tests/test_zz_probe.py` liegt
  Sekunden später als Waise im Baum, und eine Nachbarsitzung fragt zu Recht,
  wem sie gehört.

## Und der Lauf braucht das Schloss

Zwei Sondenläufe rissen ohne Schloss nach 81 bzw. 94 Zeichen — kein Ergebnis,
und beide Male sah es nach einem Fund aus. Was eine Sonde misst, ist erst dann
eine Aussage, wenn der Lauf sie zu Ende bringen konnte
(`tools/gate_lock.py run`).

Verwandt: [[exakte-passung-ist-kein-beweis]] — die Sonde ist das Gegengift
gegen eine Korrelation, die exakt passt. Sie prüft die **Kette**, nicht die
Passung.
