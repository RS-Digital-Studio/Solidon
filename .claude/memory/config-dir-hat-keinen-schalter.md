---
name: config-dir-hat-keinen-schalter
description: "Es gibt keine Umgebungsvariable für das Konfigurationsverzeichnis — eine Sonde, die save_settings ruft, überschreibt Roberts echte settings.json."
metadata: 
  node_type: memory
  type: project
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T04:20:38.823Z
---

`app/core/paths.user_config_dir()` liest unter Windows **`APPDATA`** und sonst
`XDG_CONFIG_HOME` — einen eigenen Schalter wie `SOLIDON_CONFIG_DIR` gibt es
nicht. Am 04.09.2026 habe ich einen gesetzt, ihn für wirksam gehalten und mit
`save_settings(UiSettings())` Roberts echte Datei
`C:\Users\rober\AppData\Roaming\RS Digital\Solidon3D\settings.json` mit den
Vorgaben überschrieben: zuletzt geöffnete Datei, Fenstergeometrie, Material und
`first_run_done` waren weg. Wiederherstellbar war nur, was ich vorher zufällig
ausgelesen hatte — und der Ausdruck war bei 2000 Zeichen abgeschnitten, die
letzten fünf Felder blieben auf Vorgabe.

**Why:** In der Suite fällt das nicht auf: `tests/conftest.py` biegt die
Nutzerverzeichnisse in einen Temp-Ordner um (§38). Eine Sonde im Scratchpad
läuft **ohne** conftest und trifft damit die echte Datei — dieselbe Falle wie
bei jedem Werkzeug, das man außerhalb der Suite fährt.

**How to apply:** Wer in einer Sonde etwas schreiben lässt, das im
Nutzerverzeichnis landet (`save_settings`, `report`, Aktivierung, Cache),
setzt vorher `APPDATA` auf einen Temp-Ordner — oder liest die Datei **ganz**
und legt eine Kopie daneben. Und wer nur wissen will, ob ein Feld die Runde
übersteht, prüft `UiSettings.__slots__` und `load_settings` im Code, statt es
zu schreiben. Wenn es doch passiert: sofort und ungefragt wiederherstellen und
sagen, was nicht mehr herstellbar war ([[beheben-statt-notieren]]).
