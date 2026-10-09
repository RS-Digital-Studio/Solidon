---
description: "Druckerwahl und Druckdialog — Slicer vor Drucker in Erststart, Einstellungen und Druckdialog, eine Erhebung der Drucker, Reihenfolge der Angaben im Druckdialog; Fenster allgemein steht in fenster.md"
paths:
  - "app/ui/first_run.py"
  - "app/ui/settings_dialog.py"
  - "app/ui/print_settings_dialog.py"
  - "app/core/discover.py"
  - "app/core/knowledge/profiles.py"
  - "app/core/export/handover.py"
  - "app/core/export/slicer_profiles.py"
  - "app/core/export/appimage.py"
  - "app/core/export/squashfs.py"
  - "app/core/export/cura_linux.py"
  - "app/core/tools.py"
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

## Die Slicerwahl

**Überall dieselbe** (Entscheidung Robert, RM-601): ein Auswahlfeld, sobald ein
Slicer bekannt ist — auch bei einem, der gemerkte schon beim Öffnen —, daneben
„Programm wählen …“ (`ask_slicer_program`). Ein selbst gewählter Slicer, den die
Suche nicht findet, bleibt in der Liste und gewählt. Der Druckdialog bietet
kein „Später auswählen“.

**Nur unterstützte Slicer, auf jeder Plattform** (Entscheidung Robert): Was
den Slicer bestimmt, fragt `tools.slicer_programs()` oder
`tools.slicer_program()`, nie `discover.find_program(s)` direkt — die stellen
den gemerkten Pfad ungeprüft vorn hin. Zur Wahl steht, was
`tools.is_supported_slicer` bejaht: eine Familie, die Solidon übersetzt
(`flavour_of`, auch ohne Trenner wie im AppImage „Bambu_Studio_…“), oder ein
Resin-Slicer aus `tools.RESIN_SLICERS`. Jeder Slicer unter Linux (AppImage,
Flatpak, Paket) und macOS (Bündel) gehört dazu; `test_real_slicers.py` hält es
in der CI. Ein fremdes Programm lehnt die Programmwahl mit *Einen anderen
Slicer auswählen* ab und nennt `tools.SLICER_TITLES`.

## Ein Gerät, zwei Identitäten

Ein Drucker kann eingebaut und aus dem Slicer übernommen bekannt sein. Wer
fragt, ob eine Maschine dem Projektdrucker gehört, übergibt ihn als `prefer`
an `printer_for`/`chosen_printer` (RM-600); ohne gewinnt der längere Titel,
also der übernommene, und Maschinenliste, Vorwahl und Maschinenseite verlieren
die passende Düsenvariante.

**Hinter dem Druckernamen folgt nur die Düse** (`_names_the_printer`): „Kobra 2
Max“ ist nicht der Kobra 2, „K1 SE“ nicht der K1 — sonst bekäme der kleinere
Drucker Startcode und Bauraum des größeren. Eine High-Flow-Düse („HF0.4
nozzle“) ist kein anderes Gerät, und was ein Drucker in PrusaSlicers Bündel
festhält (`prusaslicer_printer`), meint er weiter (`names_the_printer_profile`,
auch für `prefer`). Eine Herstellermaschine eines Verwandten gehört keinem
bekannten Drucker und ist trotzdem kein eigenes Profil (`related_printer` in
`_fits_the_printer`); ein eigenes Profil ohne Düse im Namen bleibt eines.

**Ein Lesedurchgang je Antwort**: Was im Druckdialog mehrere Profilfragen
hintereinander stellt, läuft in `slicer_profiles.single_read()` — jede Datei
einmal gelesen, danach verworfen. Länger hält kein Speicher, denn der Kunde
ändert seine Profile im Slicer.

## Herstellerdrucker ohne ersten Start

**Ein AppImage wird gelesen, nie gestartet** (RM-549, RM-599, Regel 11): Den
Bestand der Orca-Familie und Curas Drucker samt der Frage, ob seine
Rechenmaschine da ist, liest `export/squashfs.py` aus dem Abbild; je Fassung
liegt eine Kopie im Nutzer-Cache (`appimage.profiles`,
`cura_linux.appimage_resources`) — kein `--appimage-extract`, kein Einhängen.
Eingehängt wird nur, um Cura rechnen zu lassen. Sonst sähe ein Kunde, der den
Slicer nie geöffnet hat, keinen Herstellerdrucker. Beide Kopien verwaltet
`appimage.ImageCopies` — eine Stelle, weil die zwei Fassungen schon
auseinanderliefen: Ein geleerter Cache wird neu gelesen, eine Absage gilt je
Fassung bis *Neu suchen*, kein Zwischenordner bleibt liegen. Der Fensterfaden
wartet nie auf die Kopie (`appimage.never_wait_in`), Arbeiter legen sie an.
Alles aus dem Abbild ist fremde Eingabe: Längen gegen die Datei geprüft, Blöcke
nur bis zur Blockgröße entpackt, Namen mit Trennern verworfen, Verknüpfungen
nur innerhalb des Abbilds gefolgt, Größen vor dem Lesen begrenzt; was ein
Entpacker als beschädigt meldet, ist ein unlesbares Abbild wie jeder andere
Bruch. Ob das Paket gzip und zstd entpackt, prüft der Starttest
unter Linux (`image_compressions`). Ist ein Orca-Abbild unlesbar, fehlt nur
der mitgelieferte Bestand: Eigene Profile bleiben, ohne Profil rät der
Druckdialog, den Slicer einmal zu öffnen, und danach gilt `system/`. Ein Slicertest simuliert keinen ersten Start; wer einen braucht,
legt ihn im Test selbst an.
