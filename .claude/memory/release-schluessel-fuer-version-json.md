---
name: release-schluessel-fuer-version-json
description: "Der private Release-Schlüssel liegt als Hex in Roberts Dokumenten; ohne ihn ist version.json unsigniert, und jede Installation verwirft sie — dann bekommt niemand ein Update angeboten."
metadata:
  node_type: memory
  type: project
---

`C:\Users\rober\Documents\solidon3d-release-key.txt` — 32 Byte als Hex, am
03.09.2026 gegen `updates.RELEASE_PUBLIC_KEY` geprüft und passend. **Nicht
derselbe** wie [[lizenz-privater-schluessel]]: Der stellt Kaufschlüssel aus,
dieser unterschreibt `website/version.json`.

**Why:** `make_download.py` entfernt die Unterschrift beim Bauen des
Download-Kastens (`data.pop("signature")`) und sagt nur in einer Zeile Ausgabe,
dass sie fehlt. Wer danach hochlädt, hat eine Datei oben liegen, die jede
bestehende Installation verwirft — die Website zeigt die neue Fassung, und kein
Kunde bekommt sie angeboten. Der Fehler meldet sich nirgends: Der Upload
gelingt, die Seite stimmt, und die Stille sieht aus wie „niemand hat
aktualisiert".

**How to apply:** Nach `make_download.py` und **vor** `stamp_assets.py`:

    .venv\Scripts\python.exe tools/sign_version.py --private "C:\Users\rober\Documents\solidon3d-release-key.txt"
    .venv\Scripts\python.exe tools/sign_version.py --check

Den Pfad benutzen, nie den Inhalt lesen oder weitergeben — auch nicht an eine
andere Sitzung. Gehört wie der Lizenzschlüssel in den Passwortmanager; die
Datei in Dokumenten ist die Zwischenstation.
