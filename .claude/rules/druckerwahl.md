---
description: "Druckerwahl und Druckdialog — Slicer vor Drucker in Erststart, Einstellungen und Druckdialog, eine Erhebung der Drucker, Reihenfolge der Angaben im Druckdialog; Fenster allgemein steht in fenster.md"
paths:
  - "app/ui/first_run.py"
  - "app/ui/settings_dialog.py"
  - "app/ui/print_settings_dialog.py"
  - "app/core/discover.py"
  - "app/core/knowledge/profiles.py"
  - "app/core/export/handover.py"
---

# Druckerwahl und Druckdialog

Aus `fenster.md` ausgelagert, weil es nur diese Dialoge betrifft; dort gilt
weiter „Was eine Angabe bestimmt, steht vor ihr“.

## Die Reihenfolge im Druckdialog

Druckeinstellungen: Slicer, Drucker, Düse, Platte, Filamente, Qualität,
Profile des Slicers, Grundlage, Werte; *Werte mitgeben* bei der Übergabe
(`test_the_print_dialog_asks_in_the_order_its_answers_depend_on`). Register:
`tests/test_dependency_order.py`. Vorn davon nur Fülldichte und Stützen;
Zustand und Mitgabe über den Knöpfen, außerhalb des Rollbereichs.

## Slicer vor Drucker

**Slicer vor Drucker, überall** (Entscheidung Robert): Erststart, Einstellungen
und Druckdialog lesen die Drucker über dieselbe Erhebung, bieten dieselbe Liste
(`printers_on_offer`), beides jederzeit wechselbar. Der Slicer steht unter
„Anwendung“ vor den Druckervorgaben. Ein neues Profil bleibt im Entwurf, bis
gespeichert oder im Druckdialog gewählt (`keep_slicer_printer`), auch beim
Sprachwechsel, ebenso der Programmpfad; danach steht es nur unter seinem
Slicer, eigene ohne Marke unter jedem. Ohne eigene Drucker des Slicers bietet
der Druckdialog alle bekannten; Gründe stehen unter der Druckerwahl, Kurzhilfe
und Suche nennen den Slicer (`SlicerPrinters`). Im Erstlauf gelten Sprache, Slicerpfad und
gespeicherte Drucker sofort. Verspätete Antworten früherer Auswahl ändern
nichts. Je Modell eine Zeile ohne Düse (Entscheidung Robert,
`add_printer_choices`); die Düse wählt der Druckdialog, Speichern behält sie
(`with_saved_nozzle`). Die Suchzeile filtert live, erst eine ausdrückliche
Auswahl übernimmt, Escape schließt nur die Liste.
