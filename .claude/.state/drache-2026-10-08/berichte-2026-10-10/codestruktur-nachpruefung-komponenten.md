# Nachprüfung `konzept`-Agent zur Komponentenfassung (11.10.)

Urteil: knapp nicht abgabefähig; mit den Textvorschlägen ohne neue Prüfrunde abgabefähig. 15 Funde
eingearbeitet, Fund 7 und 11 teilweise. Stand main `ee6b810fe`.

- **N1 (mittel)** W1 sperrt 4c (neue `_build_<bereich>`-Methoden) und belohnt das Verlängern
  bestehender Methoden. Vorschlag: Liste ändern nur Programmschritte — Ordnungsschritt (4c, CS-1) hebt
  die Zahl um genau die im Commit benannten Abschnitte, Verschiebe-/Komponentenschritte senken sie;
  Regel 9 Klammer „nur Programmschritte ändern“; Regel 6: neue Handlung am Fenster = neue Komponente,
  fremden Fall in bestehende Methode = Workaround.
- **N2 (mittel)** Ersetzungsliste: `window()` liefert nur bei MainWindow und PrintSettingsDialog den
  Wirt; Viewport/SketchCanvas eingebettet (window() = Hauptfenster), Session/PlacementFlow ohne
  window(). Gleichnamig aus Qt: `self.findChild…` 8×, `installEventFilter(self)` 1×. Form 4 setzt
  QObject-Kind voraus (`weak_slot[Owner: QObject]` leash.py:626, QTimer, isValid,
  session.disconnect). `self` als Wirt eines Flusses (`DrawFlow(self)`, `SealFlow(self, …)`) fehlt.
  Ring über `_host` (DrawFlow hält Fenster stark, draw_flow.py:252; Fenster hält `_draw_flow`,
  main_window.py:15719) gegen WorkerLeash-Absicht (leash.py:431–436). Vorschläge: Komponente =
  QObject-Kind, Wirt übergibt sich als `host` (Protokoll) und `parent` (QWidget); `release()` löst
  beide Rückverweise; Form 3 → `self._parent`; Form 4 auch `WorkerLeash(self)`; Zeilen für ererbte
  Qt-Member (über `_parent`/`_host`) und `self` als Filter/Flusswirt; Test „Fenster ohne gc.collect fort“.
- **N3 (mittel)** Aufwand: MainWindow braucht ≥ 11 Komponenten (26 529 − 5 000)/2 000, realistisch
  14–18 → 21–26 Tage; Summe 53–69, elf bis vierzehn Wochen; 7.1: alte Posten ergaben schon vier bis
  acht Wochen. „Robert ist informiert“ erst nach Mitteilung.
- **N4 (leicht)** Reste „meldet“: Regel 3, CS-11; CS-2 „Ausnahme mit Grund“ gegen W4; W5 „nennt
  einzeln“ → Zuschnittliste, sonst Abbruch; Schritt 0 vorher auch CS-2, CS-12.
- **N5 (leicht)** `getattr(window, "_op_actions", None) or {}` in `shortcuts_window.py:111` (dazu 118,
  123, 137) und neun Zeilen in make_video, make_figures, run_ui_audit → vorher gewöhnliche Zugriffe.
- **N6 (leicht)** Abschnitt 6 und 4.5 nennen die Fenstertest-Frage offen bzw. „nur Release“; 4.2
  Punkt 4 ohne Fenstertests.
- **N7 (leicht)** Zusicherung „keine Unterordner“ für activation gibt es nicht → neu in
  `test_licence_build.py` ab W4.
- **N8 (leicht)** Messstände gemischt: 3.3/W5-Zahlen von `ee6b810fe` (895 Methoden).
