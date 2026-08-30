---
name: sondenbau
description: "Eine Sonde ist ein pytest-Plugin, das nur bei Änderung meldet und in eine Datei schreibt. Sieben Bauarten, an denen sie am 30.08.2026 gescheitert ist — jede sah nach einem Befund aus."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9c480190-d910-460e-bc5c-c2d37eab6361
  modified: 2026-08-30T07:45:57.828Z
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

## Sieben Arten, sich selbst zu messen

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

* **`>>` erzeugt die Datei, und `git checkout --` setzt Erzeugtes nicht
  zurück.** Eine Mutations-Sonde an `app/ui/blend.py` — die Datei gab es
  nicht — legte sie an, der Wächter fand die Probe trotzdem (gut), aber die
  „Rücksetzung" per `checkout` lief bei einer untracked Datei ins Leere:
  Die zweite Probe maß beide Kennungen, und ruff/format meldeten danach
  zwei Fehler, die die Sonde selbst war. Die Nachbarsonde am selben Tag
  mutierte eine **vorhandene** Datei (`app/core/geom/blend.py`) und kam
  sauber zurück — der Unterschied ist genau die Existenzfrage. Vor dem
  Anhängen prüfen, ob die Zieldatei existiert; Erzeugtes räumt nur `rm`
  weg, und ein leerer `git diff --stat` beweist bei einer untracked Datei
  nichts. (Der Wächter liest `rglob` zur Laufzeit — dass er die erzeugte
  Datei fand, spricht für ihn, nicht gegen die Probe.)

* **Und der Rückkehr-Anker muss eindeutig sein — mit einer Zählung danach.**
  Eine Mutationsprobe an `app/ui/panels.py` nahm `if self.list.selectedItems():
  return` heraus und wollte es über den Anker `handlers = handlers_of(self)`
  zurückschreiben. Den gibt es in der Datei **zweimal**: Das Skript brach mit
  `AssertionError` ab, und der Code blieb ohne die Sicherung stehen.

  Drei Dinge trafen dabei zusammen, und jedes einzelne sah nach Entwarnung aus.
  `ruff check` meldete „All checks passed" — ein Formprüfer sieht keine
  fehlende Bedingung. Die Probe selbst war **rot gewesen, wie sie sollte**, war
  also gerade als Erfolg abgehakt. Und der Abbruch stand am Ende einer langen
  Ausgabe, unter der grünen Zeile des Testlaufs. Gefangen hat es allein ein
  `grep -c` hinterher.

  Zwei Regeln, und die zweite ist die teurere: Der Anker trägt genug Kontext,
  um einmalig zu sein — hier genügte das Docstring-Ende darüber. **Und nach
  jeder Rückkehr wird gezählt, nicht geglaubt.** Eine Mutation, die stehen
  bleibt, sieht aus wie ein sauberer Stand, denn die Probe hat ja geliefert,
  was sie sollte. Siehe [[was-die-suite-nicht-findet]].

* **Ein Filter, der nichts findet, und ein Filter, der nichts trifft, sehen
  gleich aus.** `pytest -k "list_top or drop"` meldete **4 passed** — der
  gemeinte Test heißt `test_a_list_in_the_bottom_bar_opens_upwards_when_it_
  has_to` und enthält keines der beiden Wörter. „Mein Fix bricht nichts" wäre
  die Meldung gewesen, und die Frage war nie gestellt (fb, 30.08.2026).

  Dieselbe Familie, am selben Tag, in der anderen Richtung: Ein
  Hintergrundlauf meldete *„completed (exit code 0)"* über einer Datei, in der
  `1 failed, 360 passed` stand. Der Aufruf endete auf
  `pytest … > datei; echo "Exit: $?"`, und der Status einer Kette ist der
  ihres **letzten** Befehls — `echo` gelingt immer. Die Hausordnung kennt die
  Falle für `| tail`; sie gilt für jedes nachgestellte Kommando und für die
  Fertigmeldung, die den Kettenstatus weiterreicht.

  Die Kontrolle ist billig und in beiden Fällen dieselbe: **die Zahl der
  gesammelten Tests lesen** (`-k` mit `--collect-only`, oder die
  `N deselected` in der Schlusszeile gegen die Erwartung halten), und **die
  Rohdatei lesen statt der Meldung darüber**. Wer prüft, ob eine Änderung
  etwas bricht, prüft zuerst, dass sein Muster den gemeinten Test überhaupt
  fängt.

## Und der Lauf braucht das Schloss

Zwei Sondenläufe rissen ohne Schloss nach 81 bzw. 94 Zeichen — kein Ergebnis,
und beide Male sah es nach einem Fund aus. Was eine Sonde misst, ist erst dann
eine Aussage, wenn der Lauf sie zu Ende bringen konnte
(`tools/gate_lock.py run`).

## Der Kontrollfall gehört in jede Sonde, und er verdient sich vierfach

Am 30.08.2026 sollte eine Sonde beantworten, ob ein Ereignis auch dann feuert,
wenn die Maus außerhalb des Fensters losgelassen wird. Die Frage war gut, die
erwartete Antwort plausibel — und die Sonde lieferte sie **viermal
hintereinander falsch**:

| Anlauf | Fehler im Aufbau | was sie meldete |
|---|---|---|
| 1 | kein Projekt geöffnet → Startbildschirm, Interactor 100 × 30 Pixel | „Ereignis 0×" |
| 2 | Qt-Ereignisse an den Interactor — VTK hört darauf nicht | „Ereignis 0×" |
| 3 | in der Bildmitte gegriffen (dort steht das Modell: Auswahl statt Drehung), dazu waagerecht gezogen (dreht azimutal, der gemessene Winkel bleibt gleich) | „Ereignis 0×" |
| 4 | **linke** Maustaste — im Vorgabe-Schema wählt sie, gedreht wird rechts | „Ereignis 0×" |

Jedes Mal dieselbe Zahl, jedes Mal eine perfekt aussehende Bestätigung der
Vermutung. Gefangen hat es allein der **Kontrollfall**: derselbe Zug, nur
innerhalb losgelassen — dort *musste* das Ereignis kommen. Kam es nicht, war
der Aufbau kaputt und nicht die Sache.

Das Ergebnis war am Ende das Gegenteil: Das Ereignis feuert in allen Fällen,
die vermutete Lücke gibt es nicht.

**Ein fünfter Fehler saß in der Größe der Geste**, und er ist die feinere
Hälfte: Die ersten Züge drehten über dreißig Grad — weit außerhalb des
Bereichs, um den es ging. Dass dort nichts einrastet, ist richtig und
beantwortet die Frage nicht. Eine Sonde muss den Fall **treffen**, nicht nur
auslösen.

**How to apply:** Jede Sonde bekommt einen Fall, dessen Ausgang feststeht,
bevor sie den Fall misst, dessen Ausgang offen ist. Steht kein solcher Fall zur
Verfügung, misst man vorerst das Werkzeug und nicht die Sache
([[messwerkzeug-misst-sich-selbst]]).

Verwandt: [[exakte-passung-ist-kein-beweis]] — die Sonde ist das Gegengift
gegen eine Korrelation, die exakt passt. Sie prüft die **Kette**, nicht die
Passung.
