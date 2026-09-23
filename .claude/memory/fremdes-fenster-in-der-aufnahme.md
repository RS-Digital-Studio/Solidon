---
name: fremdes-fenster-in-der-aufnahme
description: "Mehrere Sitzungen nehmen auf denselben Schirm auf — eine Bildschirmaufnahme greift, was obenauf liegt; make_figures.foreign_window_over fragt Windows vor jedem Bild, wem das Fenster gehört"
metadata:
  type: project
---

Am 23.09.2026 stand in einem Website-Bild (`beleg-dialog`) statt des eigenen
Dialogs das **Hauptfenster einer anderen Sitzung**: fremdes Projekt
(Schraubdose), fremder Drucker, die Statuszeile mit der Demo-Restlaufzeit.
Gleichzeitig nahmen andere Agenten auf demselben Schirm auf (Schirm 1, die
Vorgabe von `make_figures.SCREEN_INDEX` für alle Werkzeuge) — Fenstertitel wie
„Unbenannt — Solidon3D", „Teil-links (ungespeichert)",
„weg1-halter-anpassen.p3d".

**Warum man es nicht sieht:** Die Aufnahme ist technisch fehlerfrei, Maße und
Dateigröße stimmen. Nur der Inhalt gehört jemand anderem. Eine Prüfung auf
Bildzahl oder Größe fängt es nie.

**Die Wache:** `tools/make_figures.foreign_window_over(widget, rect)` fragt
Windows an 25 Punkten des Rechtecks (`WindowFromPoint`), welchem Prozess das
Fenster dort gehört; eigene Dialoge zählen nicht. `wait_until_uncovered`
holt das eigene Fenster nach vorn und wartet (höchstens fünf Minuten), dann
bricht es mit dem Titel des fremden Fensters ab. Benutzt von
`make_video.record` (vor jedem Bild) und `make_web_images.grab`; die
Handbuchaufnahme (`make_figures.shoot`) fragt sie noch nicht.

**Und umgekehrt:** Wer selbst aufnimmt und dabei das eigene Fenster nach vorn
holt, liegt über der Aufnahme der anderen. Große Aufnahmeläufe deshalb nicht
parallel zu einer zweiten Sitzung fahren, die auf denselben Schirm aufnimmt —
oder einen anderen Schirm wählen (`--schirm N`).

Verwandt: [[parallele-sitzung-baut-dasselbe-feature]],
[[zweite-sitzung-im-selben-baum]].
