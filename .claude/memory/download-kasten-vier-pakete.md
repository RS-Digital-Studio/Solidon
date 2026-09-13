---
name: download-kasten-vier-pakete
description: "Der Download-Kasten zeigt die Plätze aus DELIVERED, nicht die acht aus dem Baulauf — seit 28.08.2026 fünf: Setup, AppImage, Flatpak, beide macOS-.pkg. Das Werkzeug erzwingt es."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T13:10:58.405Z
---

Ein Baulauf liefert acht Dateien; angeboten wird, was `DELIVERED` in
`make_download.py` führt. **Seit dem 28.08.2026 sind es fünf** (der Dateiname
dieser Notiz stammt vom Stand davor): `Solidon3D-Setup-<v>.exe`,
`<v>-x86_64.AppImage`, `<v>-x86_64.flatpak`, `<v>-macos-arm64.pkg`,
`<v>-macos-x86_64.pkg`. Archiv und die beiden `.zip` werden gebaut und
geprüft, aber weder verlinkt noch hochgeladen.

**Das AppImage ist der Sonderfall, und er hat zwei Seiten.** Es steht im
Kasten und im `dl/`-Ordner, aber **nicht** in den `packages` von
`version.json`: Ein AppImage aktualisiert sich nicht selbst, also hat es dort
nichts zu suchen. Damit trägt es als einziges Paket keine Prüfsumme im
Manifest — `verify_downloads()` liest seinen Link deshalb aus den
`index.html`, und wo keine Größe bekannt ist, sagt der Lauf `OHNE MASS` statt
„ok" ([[datei-ohne-manifest-hat-keinen-pruefer]]).

**Why:** Wer vor der Wahl steht, will einen Knopf sehen, nicht drei, die
dasselbe Programm enthalten. Am 22.08.2026 hatte ich alle acht eingetragen —
Robert hat es auf den Stand von 0.1.1 zurückgestellt.

**Und am 27.08.2026 habe ich es beim Release von 0.2.1 wiederholt**, obwohl
diese Notiz existierte. Die Startseiten verwiesen danach in sechs Sprachen
auf vier Dateien, die nie hochgeladen werden. Seither steht die Liste als
`DELIVERED` in `make_download.py` und wird in beide Richtungen geprüft: eine
zu viel ist ein toter Verweis, eine zu wenig lässt ein ganzes Zielsystem ohne
Download. Eine Notiz, die zweimal überlesen wird, gehört ins Werkzeug.

**How to apply:** `make_download.py` nur mit diesen fünf Pfaden aufrufen.
Die Reihenfolge danach ist eine Folge, keine Empfehlung:

1. Pakete **einzeln und zuerst** hochladen — mehrere am Stück reißen die
   Verbindung ([[website-upload-grosse-dateien]]), und der Pfad beginnt mit
   `website/`; `dl/…` allein sucht das Werkzeug im Repository-Stamm.
2. `sign_version.py --private <schlüsseldatei>` — ohne Unterschrift verwirft
   jede Installation ab 0.1.4 die Datei still, und niemand erfährt von der
   Fassung. `make_download.py` macht jede vorhandene ungültig.
3. `stamp_assets.py`, dann `upload_website.py --fehlend` für Seiten und
   `version.json`. Das Werkzeug hält sie inzwischen selbst zurück, solange
   ihre Pakete oben fehlen — verlass dich nicht darauf, lade sie vorher.
4. `--alte-pakete --wirklich` ganz zum Schluss.
5. **`--nachpruefen`**: ruft jede versprochene Datei ab wie ein Kunde und
   vergleicht die Größe. Lokal ist nach einem Release immer alles grün;
   falsch ist, was oben liegt ([[messung-traegt-nur-am-ort-ihrer-messung]]).

Beim Upload im Hintergrund die **Ausgabedatei** lesen, nie die
Abschlussmeldung: Sie gilt der Hülle, und sie sagte an dem Tag dreimal
„exit code 0" über einem Upload, der wegen des falschen Pfads nie stattfand.

Siehe [[version-vor-jedem-bau-erhoehen]].
