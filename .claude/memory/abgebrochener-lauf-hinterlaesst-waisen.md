---
name: abgebrochener-lauf-hinterlaesst-waisen
description: Ein getötetes suite-getrennt.sh lässt seine pytest-Kinder weiterlaufen; sie sehen wie fremde Arbeit aus.
metadata:
  type: project
---

`suite-getrennt.sh` startet je Fensterdatei einen eigenen `pytest`. Stirbt der
Bash-Rahmen, laufen die Kinder weiter und werden umgehängt — sie stehen dann mit
CPU 0 in der Prozessliste, oft stundenlang.

Am 03.09.2026 hielten drei Sitzungen zwei solche Prozesse von 07:06:50 für
fremde Arbeit und sprachen sich darüber ab, wer sie gestartet habe. Niemand
bekannte sich, weil der Urheber sich längst beendet hatte. Nach dem Abbruch
meines eigenen Laufs lebten vier weiter:

    54156  bash /tmp/tmp.apDQ1iQ0mx      (das ist suite-getrennt.sh)
    48840  bash /tmp/tmp.apDQ1iQ0mx
    65372  pytest -m "not performance" tests/test_chat_ui.py::…
    46468  pytest (Kind davon)

**Zwei Fragen, nicht eine.** „Rechnet der Prozess?" und „wem gehört er?" sind
verschieden, und nur die zweite beantwortet die Elternkette. 3d-druck-7b hat sie
zweimal gemessen und beide Male nur die erste gestellt. Ein Prozess mit CPU 0 ist
kein Beweis für einen Hänger und erst recht keiner für einen Urheber — siehe
[[zustandswert-widerlegt-keinen-haenger]].

**Also:** Nach jedem abgebrochenen geteilten Lauf nachsehen. Elternkette bis zur
Wurzel verfolgen; ist die tot, sind es Waisen und niemandes laufende Arbeit.
Erst dann beenden — nie über die Kommandozeile filtern, siehe
[[eigenen-lauf-ueber-die-elternkette-beenden]].

Ein hängender Lauf mit acht xdist-Arbeitern nimmt jeder anderen Sitzung
Rechenzeit, und Leistungstests unter Fremdlast melden Regressionen, die es nicht
gibt ([[leistungstests-fremdlast]]).
