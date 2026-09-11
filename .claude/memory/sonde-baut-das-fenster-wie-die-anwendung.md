---
name: sonde-baut-das-fenster-wie-die-anwendung
description: "Ein Fensterbefund, den fünf Sonden nicht zeigen, hängt an der Reihenfolge des Startwegs — build_application, restoreGeometry, show, start, open_path — nicht an Schrift oder Skalierung."
metadata:
  type: feedback
---

RM-158 (11.09.2026): „Alle Platten" lag in Roberts Kopfzeile über dem
Druckernamen. Fünf Sonden sahen nichts — offscreen bei sechs Breiten, am
echten zweiten Bildschirm mit seiner Geometrie, mit Bildschirmwechsel, klein
gezeigt und groß gezogen, mit seiner Datei. Alle bauten das Fenster mit
`MainWindow(...)`, `resize`, `show`, dann das Projekt. Die Anwendung baut es
anders: 1280 breit (kompakt), `restoreGeometry` (breit, Wähler versteckt),
`show`, `start`, erst dann `open_path` (Wähler sichtbar). Genau diese Folge
ließ eine Spaltendehnung stehen, die am Zeitpunkt des Anordnens hing, und
`QGridLayout` gab der Spalte null Breite. `build_application` in der Sonde
zeigte es beim ersten Lauf.

**Why:** Ein Layoutzustand ist eine Geschichte, kein Zustand — was ein
Widget beim Anordnen war (versteckt, sichtbar, schmal), prägt Dehnungen und
Cache. Eine Sonde mit anderer Reihenfolge misst ein anderes Fenster
([[gemessene-frage-ist-nicht-die-gestellte]], [[oberflaeche-von-hand-fahren]]).

**How to apply:** Bei einem Befund aus Roberts laufendem Fenster die Sonde
über `app.ui.app.build_application` bauen und den Rest von `main()`
nachspielen (`restoreGeometry`, `show`, `start`, `open_path`), mit einer
Kopie seiner `settings.json` unter einem eigenen `APPDATA`; für das Bild
`Graphics.CopyFromScreen` am zweiten Bildschirm (x ab 3413). Erst wenn das
nichts zeigt, an Schrift oder Skalierung denken.
