---
name: kundenweg-im-fenster-messen-nicht-im-kern
description: "Leistung am echten Fenster offscreen messen (MainWindow + session.apply, bis das Fenster still ist) — die Kernsonde sah 1,4 s, der Kunde wartete 8,6 s; cProfile in 3.14 misst alle Fäden, cumtime von Signal-Emits ist Wartezeit"
metadata:
  type: feedback
---

Am 22.09.2026 (Roberts Auftrag: „kompletter performancefix von merkmalen,
operationen, verschieben, bearbeiten, erkennen … ob alles überhaupt nötig
ist") maß die Kernsonde (`evaluate` allein) für ein Verschieben an 204 000
Dreiecken 1,4 s. Dieselbe Geste im echten Fenster — `MainWindow(Session(),
UiSettings())` offscreen, `session.apply(...)`, dann warten, bis Sitzung
**und** alle Arbeiter des Fensters still sind — kostete 8,6 s. Die fehlenden
sieben Sekunden waren ein Vorschaubild im Objektbaum (Dezimierer stand still)
und ein zweiter Import (Cache-Schlüssel nach der Einheitenantwort). Beides
liegt außerhalb von `evaluate` und wäre in keiner Kernsonde je erschienen.

**Why:** Der Kunde wartet auf das Fenster, nicht auf den Kern. Die
Leistungstests messen Kernfunktionen (§31-Zeilen), die UI-Arbeiter daneben
(Vorschaubilder, Ketten, Kennzahlen, Vorschau) misst keiner — und genau dort
lagen sechs von acht Sekunden.

**How to apply:** Eine Leistungsfrage zu einem Kundenweg zuerst am Fenster
messen: Sonde nach dem Muster der Fixture `window` aus `test_analysis_ui.py`
(Umgebung wie `tests/conftest.py` isolieren — §38, sonst trifft die Sonde den
echten Plattencache), je Schritt `evaluate` im Arbeiter stoppen (Wrapper um
`session.evaluate`) und den Rest als UI-Anteil ausweisen. Dazu drei
Lesehilfen:

- **cProfile unter Python 3.14 misst alle Fäden** (`sys.monitoring`): Im
  Hauptthread eingeschaltet, zeigt es die Arbeiter mit. Gut für das Ganze;
  wer den Hauptthread allein will, misst `processEvents` oder filtert nach
  `app\ui`.
- **`cumtime` eines Signal-`emit` oder von `report_progress` ist GIL-Wartezeit,
  keine Arbeit.** 0,75 s in zwölf Aufrufen sahen wie ein Fund aus; ohne
  Profiler waren es 0,0 ms.
- **Ein roter Test während der Arbeit kann fremd sein.** Im Baum schrieb
  parallel eine zweite Sitzung dieselbe Datei (`features.py`, `test_evaluation.py`);
  der Test war einmal rot und zweimal grün, ohne dass ich etwas geändert
  hatte. Vor „flaky" erst `git status` und die Sitzungsliste lesen
  ([[zweite-sitzung-im-selben-baum]]).
