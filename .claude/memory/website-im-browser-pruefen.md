---
name: website-im-browser-pruefen
description: "Die Website lässt sich mit dem installierten QtWebEngine wirklich ansehen — hell, dunkel und ohne Bewegung. Zwei der Handgriffe dafür sind anders, als sie aussehen."
metadata: 
  node_type: memory
  type: project
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-27T08:34:00.090Z
---

`website/` muss nicht geraten werden: PySide6 bringt in dieser `.venv`
**QtWebEngine** mit (`from PySide6.QtWebEngineWidgets import QWebEngineView`).
Ein kurzes Skript lädt die Datei über `QUrl.fromLocalFile`, scrollt per
`runJavaScript` und speichert Ausschnitte mit `view.grab().save(...)`.

**Zwei Handgriffe, die stillschweigend das Falsche tun** — beide am 27.08.2026
gemessen, nachdem ich dreizehn „dunkle" Bilder aufgenommen hatte, die alle
hell waren:

- **`--blink-settings=preferredColorScheme=0` ist dunkel, `=1` ist hell.**
  `=2` fällt still auf hell zurück — kein Fehler, keine Warnung, dieselbe
  Seite ein zweites Mal. Diese Notiz sagte bis dahin, `2` sei dunkel.
  Gegenprobe kostet nichts: `matchMedia('(prefers-color-scheme: dark)').matches`
  oder die Hintergrundfarbe (`rgb(23,22,20)` gegen `rgb(247,246,243)`).
  `app.styleHints().setColorScheme(...)` wirkt auf QtWebEngine **nicht**.
- **`runJavaScript` gibt ein JS-Objekt als leeren String zurück.** Nicht
  `None`, keine Ausnahme — `""`. Zahlen, Zeichenketten und Wahrheitswerte
  kommen heil an, ein `{a: 1}` und jede IIFE, die eines zurückgibt, nicht.
  Wer etwas aus der Seite holt, gibt **`JSON.stringify(…)`** zurück und lädt
  es außen. Sonst sucht man den Fehler im eigenen JavaScript, und dort ist
  keiner — [[messwerkzeug-misst-sich-selbst]].
- **`--force-prefers-reduced-motion`** für den Fall ohne Animationen. Genau
  dort lagen bei den erklärenden Zeichnungen beide Zustände übereinander.
  `document.getAnimations()` mit gesetzter `currentTime` bricht still ab; für
  die Bewegungsprüfung die Flags nehmen.

Wie bei der Anwendung gilt [[oberflaeche-von-hand-fahren]]: echte Qt-Plattform,
nicht `offscreen`, sonst fehlen die Schriften und **jede Breitenmessung ist
falsch**.

**Beim Scrollen 700 ms je Schritt warten.** Die Seite lässt Abbildungen über
`animation-timeline: view()` aufsteigen; wer sofort abdrückt, fotografiert
Zwischenzustände und meldet blasse Texte als Kontrastfehler. Und ein Bild über
die **volle Seitenhöhe** zeigt umgekehrt alles im Endzustand — es taugt für
den Inhalt, nicht für den Eindruck.

Was so gefunden wurde: waagerechter Rollbalken durch einen Schein über den
Rand (`overflow-x: clip` auf `body`, nicht `hidden` — das löst die stehende
Kopfzeile), die 40 px, die jeder Browser einem `<figure>` mitgibt, und am
27.08. der Handy-Rand: 189 px Rand um 171 px Text im Download-Kasten.
