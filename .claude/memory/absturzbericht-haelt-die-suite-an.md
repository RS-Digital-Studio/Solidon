---
name: absturzbericht-haelt-die-suite-an
description: "Ein Hänger in einer Fensterdatei war kein nativer Abriss, sondern ein modaler Absturzbericht — _on_ask macht jede Ausnahme aus einem Dialogrückruf zum InternalError; offscreen hält report_error dann die Suite an, ohne rotes Wort"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T10:14:36.387Z
---

Gemessen am 21.09.2026: `test_ui.py::test_matching_choices_wait_for_the_actual_scene_and_restore_it_before_reply[enter]`
hing im Release-Tor ohne Ausgabe. `faulthandler` (`-X faulthandler`,
`-o faulthandler_timeout=45`) zeigte den Stapel: `report_error` → `dialog.exec()`,
gerufen aus `_on_error` aus `_on_ask`. Der Auslöser war eine **fehlgeschlagene
Zusicherung** im Testrückruf (`assert finished == [Accepted]`), und `_on_ask`
verpackt jede Ausnahme aus einem Dialog als `InternalError` — der Bericht
öffnete modal und wartete auf einen Klick, den es offscreen nie gibt.

**Why:** Die Suite-Beschreibung in `CLAUDE.md` führt den Hänger seit dem
16.08.2026 als „nativen Abriss bei über 3 GB". Ein Teil davon war ein
gewöhnlicher Testfehler, den der Fehlerweg der Anwendung in einen stehenden
Prozess verwandelte. Eine Suite, die steht, nennt keinen Namen — wer sie für
einen Speicherriss hält, sucht wochenlang an der falschen Stelle.

**How to apply:** Bei einem stehenden Fenstertest zuerst `faulthandler` mit
Zeitgrenze fahren und den Stapel lesen, bevor man an Speicher denkt. Steht
dort `report_error`/`exec`, ist es eine Ausnahme im Dialogrückruf: Mit einer
Sonde `report_error` patchen und `error.detail` in eine Datei schreiben, dann
steht der echte Traceback da. Seit dem 21.09.2026 geht `report_error`
offscreen ins Protokoll statt in den Dialog. Siehe
[[hintergrundlauf-meldet-seinen-wrapper]] und
[[leere-transkriptdatei-ist-kein-haenger]].
