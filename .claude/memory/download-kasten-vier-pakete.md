---
name: download-kasten-vier-pakete
description: "Der Download-Kasten zeigt vier Pakete, nicht die acht aus dem Baulauf — Setup, Flatpak, beide macOS-.pkg."
metadata:
  type: feedback
---

Ein Baulauf liefert acht Dateien; `tools/make_download.py` trägt jede ein, die
es bekommt. Angeboten werden aber **vier**: `Solidon3D-Setup-<v>.exe`,
`<v>-x86_64.flatpak`, `<v>-macos-arm64.pkg`, `<v>-macos-x86_64.pkg`. Archiv,
AppImage und die beiden `.zip` werden gebaut und geprüft, aber weder verlinkt
noch hochgeladen.

**Why:** Wer vor der Wahl steht, will einen Knopf sehen, nicht drei, die
dasselbe Programm enthalten. Am 22.08.2026 hatte ich alle acht eingetragen —
Robert hat es auf den Stand von 0.1.1 zurückgestellt.

**How to apply:** `make_download.py` nur mit diesen vier Pfaden aufrufen. Nach
der Veröffentlichung liegen im Serverordner `dl/` genau diese vier: die
Pakete der Vorfassung werden gelöscht, nicht liegen gelassen. Siehe
[[website-upload-grosse-dateien]] und [[version-vor-jedem-bau-erhoehen]].
