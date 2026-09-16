---
name: teardown-riss-bei-gewaehlter-flaeche
description: "Ein Fenstertest, der mit gewählter Fläche endet, reißt im Abbau der Suite mit Exit 127 — am unveränderten HEAD genauso; der echte Schließweg der Anwendung ist mit derselben Auswahl sauber (16.09.2026)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 337c8da1-518d-4c2c-9ac1-9020b4cc1a65
  modified: 2026-09-16T17:28:28.124Z
---

`tests/test_ui.py` und `tests/test_analysis_ui.py`: Ein Test, der eine
**Fläche** wählt (`select_feature`) und so endet, reißt im Teardown der
Fixtures mit Exit 127 — auch wenn alle Zusicherungen grün sind. Gemessen am
16.09.2026 mit einer Wegwerfsonde: nur wählen → 127; wählen und den Körper
löschen → 0; wählen, abwählen, löschen → 0; am unveränderten HEAD im Worktree
→ 127. Der echte Schließweg (`closeEvent`, `forget_changes`, `close`, `quit`,
`gc`) endet mit derselben Auswahl sauber — es ist die Aufräumfamilie der
Suite (RM-021), kein Kundenfehler.

`py-spy` findet Python 3.14 nicht („Failed to find python version"); den
Stapel eines hängenden Prüfstands liefert
`faulthandler.dump_traceback_later(15, exit=True)` in der Sonde selbst.

**How to apply:** Ein Test, der Entf, Undo oder eine Auswahl prüft, leert
die Auswahl vor seinem Ende (`select_object(None)`, dann `processEvents`),
und der Kommentar sagt warum. Ein Riss beim Abbau nach grünen Zusicherungen
wird zuerst mit „nur wählen" isoliert, bevor jemand den Fix verdächtigt.
Siehe [[verwaiste-widgets-sterben-im-falschen-moment]] und
[[gefahren-ist-nicht-gefordert]].
