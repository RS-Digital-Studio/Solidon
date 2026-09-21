---
name: rote-fenstertests-waren-vor-dem-eigenen-stand-rot
description: "Vor dem Beheben roter Fensterdateien dieselben Dateien am Stand vor der eigenen Arbeit fahren und die FAILED-Listen mit comm vergleichen — am 21.09. waren 71 von 74 Fällen älter als P2.8, die meisten aus Commits desselben Tages, die ihre Tests nie mit ihrem eigenen Code gefahren hatten"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T10:14:52.506Z
---

Release-Tor am 21.09.2026 nach P2.8: 74 rote Fensterfälle in zwölf Dateien.
Ein zweiter Arbeitsbaum am Stand davor (`git worktree add --detach <hash>`),
dieselben zwölf Dateien dort gefahren, beide `FAILED`-Listen sortiert und mit
`comm -13 vorher nachher` verglichen: **drei** Fälle kamen von P2.8 (zwei
davon Tests zum entfernten Haken), 71 waren älter. Fast alle stammten aus
Commits vom 20.09. (`064e3095`, `1fc131a6`, `102d4bf7`, `5d451fe7`), die
Fenstertests mitbrachten oder änderten, ohne sie zu fahren — Fensterdateien
laufen laut Hausordnung nur beim Release, und niemand hatte seither eines
gefahren.

Zweite Runde am selben Tag, `test_ui` und die Viewport-Dateien: Zwölf weitere
Fälle, alle älter. Drei Muster: Tests riefen `dialog.accept()` direkt nach
dem Tippen — seit dem 20.09. wartet Übernehmen auf die dargestellte Vorschau,
und ein Klick davor tut nichts (`_accept_after_preview` in `test_ui`);
gestellte Merkmale ohne `measure_sources` trugen „Maßherkunft nicht bestimmt"
in der Beschriftung und fanden im Bild keinen Platz (49 Zeichen bei 12 px je
Glyphe der Offscreen-Schrift); und ein echter Fund: Das Fenster-Fixture steht
auf dem Startbildschirm mit **nie ausgewerteter** Sitzung, und genau dort
konnte auch der Kunde über Palette und Kürzel einen Dialog öffnen, dessen
Übernehmen-Knopf frei war und nichts tat (`_begin_from_the_start_screen`).

**Why:** Ohne den Vergleich hätte ich 74 Fälle als Folge meiner Arbeit
gelesen und an P2.8 gesucht. Mit ihm war klar, was ich verursacht hatte
(drei), was ein echter Fund war (Tippen verzehnfacht, Freigabe nie erteilt,
Karte nach Einheitenwechsel neu, Enter verwirft die Frage) und was ein Test
war, der einen alten Stand festhielt (Maß 5,1901 gegen die Vieleckkorrektur,
zwei Hinweise statt drei, Felder statt Boxen).

**How to apply:** Erst vergleichen, dann beheben. Je Fall entscheiden: Fund
in der Anwendung (beheben, Karte nachziehen), Test hält einen überholten
Stand fest (Test auf die geltende Regel stellen, mit Datum und Grund im
Kommentar), oder Test widerspricht einem anderen Test desselben Tages (die
Anwendung ist die Wahrheit, beide Tests darauf ausrichten). Ein Test, der mit
seinem eigenen Commit rot war, ist keine Zusage — `git log -L` auf die
Zusicherung zeigt es. Siehe [[messung-galt-fuer-den-stand-davor]] und
[[beheben-statt-notieren]].
