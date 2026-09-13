---
name: config-dir-hat-keinen-schalter
description: "Es gibt keine Umgebungsvariable für das Konfigurationsverzeichnis — eine Sonde, die save_settings ruft, überschreibt Roberts echte settings.json."
metadata: 
  node_type: memory
  type: project
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-12T22:18:00.809Z
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

**Nachtrag 12.09.2026 — der Umweg über `paths.X = …` reicht nicht.** Dieselbe
Falle ein zweites Mal, diesmal an der echten `filaments.json` (6 Spulen mit
`{kaputt`, 7 Byte, überschrieben). Der Schreiber war eine Review-Sonde
(`…/review/ui_print/probe2.py`), die es „richtig" machen wollte und **nicht**
`APPDATA` setzte, sondern `paths.user_config_dir = lambda …: Path(room)` — und
danach `filaments.catalogue_path().write_text("{kaputt")`. Es traf trotzdem
Roberts echten Pfad. Grund: `filaments.py:29` bindet den Namen mit
`from app.core.paths import … user_config_dir`, und `catalogue_path()` ruft
diesen **lokal gebundenen** Namen, nicht `paths.user_config_dir`. Ein
`from X import Y` macht `Y` zu einem eigenen Modulattribut; wer `X.Y` umbiegt,
erreicht das verbrauchende Modul nicht. Also: die Funktion **im verbrauchenden
Modul** umstellen (`filaments.catalogue_path = …`, so machen es probe4–9
richtig) oder gleich `APPDATA` setzen — beides, wenn mehrere Module denselben
Namen gebunden haben. Die App selbst verhielt sich korrekt: `_read()`
überschreibt eine beschädigte Datei nie und meldet `catalogue/unreadable` mit
Handlungsvorschlag (Regel 17). Behoben durch Umbenennen des Schrotts nach
`filaments.json.kaputt-2026-09-12`; die gültige Datei war wieder da.
