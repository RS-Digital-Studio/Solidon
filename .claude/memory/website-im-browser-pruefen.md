---
name: website-im-browser-pruefen
description: "Die Website lässt sich mit dem installierten QtWebEngine wirklich ansehen — inklusive hellem Modus und reduzierter Bewegung, aber nur über Chromium-Flags."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1e60a9c0-96f0-4407-b65d-573ef2a49b9a
  modified: 2026-08-08T05:21:31.235Z
---

`website/` muss nicht geraten werden: PySide6 bringt in dieser `.venv`
**QtWebEngine** mit (`from PySide6.QtWebEngineWidgets import QWebEngineView`).
Ein kurzes Skript lädt die Datei über `QUrl.fromLocalFile`, scrollt per
`runJavaScript` und speichert Ausschnitte mit `view.grab().save(...)`.

Die beiden Zustände, die man sonst nie sieht, gehen **nur über
Chromium-Flags** in `QTWEBENGINE_CHROMIUM_FLAGS`:

- `--force-prefers-reduced-motion` — der Fall, in dem alle Animationen
  wegfallen. Genau dort lagen bei den erklärenden Zeichnungen beide Zustände
  übereinander.
- `--blink-settings=preferredColorScheme=1` — heller Modus (2 wäre dunkel).
  `app.styleHints().setColorScheme(...)` wirkt auf QtWebEngine **nicht**.

Zwei Stolpersteine: `document.getAnimations()` mit gesetzter `currentTime`
bricht still ab (das nachfolgende JS liefert dann gar nichts zurück) — für die
Bewegungsprüfung lieber die Flags nehmen. Und wie bei der Anwendung gilt
[[oberflaeche-von-hand-fahren]]: echte Qt-Plattform, nicht `offscreen`, sonst
fehlen die Schriften.

Was der erste Durchgang so gefunden hat: waagerechter Rollbalken durch einen
Schein, der über den Rand ragt (`overflow-x: clip` auf `body`, nicht `hidden`
— das löst die stehende Kopfzeile), und die 40 px, die jeder Browser einem
`<figure>` links und rechts mitgibt.
