# Abhakliste D10

Erzeugt von `tools/function_report.py` (Konzept Funktionsdurchgang §7); nicht von Hand bearbeiten — die Prüfsumme merkt es.

| | |
|---|---|
| Paket | D10 |
| Prüfsumme | c7979e9a168bb69d622f1638b0a470053315b3f022357dc46533d4427a19f93e |
| Commit | d9f7a81f9436165c8b2e58cb3013ecf2e07d6602 |
| Datum | 2026-10-17 |
| Laufordner | `schlusslauf-d9f7a81f/L4-d0` |
| Zeilen | 30 |
| gut | 0 |
| gut nach Fix | 0 |
| offen mit RM | 30 |
| nicht geprüft | 0 |

## Funktionen

`ja` erfüllt · `FD-n` Fund · `—` entfällt · `B` Urteil der Stufe B steht aus · `C` nur Stufe C · `?` nicht gelaufen · `n.p.` nicht prüfbar

| Kennung | Art | Szene | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | Urteil | Funde |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| assign_slot | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | FD-242 | offen RM-737, RM-747 | FD-131, FD-242, FD-268 |
| clear_filament | operation | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-136, FD-138, FD-268 |
| create_label | operation | leer | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-9, FD-95, FD-134 |
| inlay_text | operation | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-2, FD-137 |
| label_text | operation | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-1, FD-241 |
| paint_slot | operation | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | ja | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-43, FD-132, FD-136, FD-138, FD-241, FD-251, FD-268, FD-284 |
| slots_from_texture | operation | farbig.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-747 | FD-135 |
| Bearbeiten/Material kalibrieren … | fensterbefehl | leer | offen | offen | offen | offen | offen | offen | offen | FD-267 | FD-223 | offen | ja | offen | offen | offen | offen | offen | — | offen | offen | offen RM-747, RM-812 | FD-8, FD-10, FD-13, FD-14, FD-176, FD-199, FD-223, FD-251, FD-267, FD-277, FD-280 |
| Bearbeiten/Parameter anlegen … | fensterbefehl | quader.exakt | ja | FD-265 | — | offen | offen | ja | FD-265 | FD-281 | FD-125 | offen | ja | offen | offen | — | offen | FD-128 | FD-129 | FD-26 | offen | offen RM-737, RM-747, RM-812 | FD-11, FD-26, FD-39, FD-41, FD-94, FD-125, FD-126, FD-127, FD-128, FD-129, FD-137, FD-139, FD-155, FD-166, FD-198, FD-265, FD-266, FD-281, FD-282 |
| Erzeugen/Bausteine/Gegenstücke setzen … | fensterbefehl | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-747 | FD-42, FD-50, FD-52, FD-66, FD-133 |
| dialog:binding_dialog | bedienflaeche | parameter.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101 |
| dialog:calibration_dialog | bedienflaeche | leer | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101, FD-176, FD-199 |
| dialog:counterpart_dialog | bedienflaeche | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101 |
| dialog:parameter_dialog | bedienflaeche | leer | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-737 | FD-101, FD-129, FD-198 |
| dialog:recipe_dialog | bedienflaeche | parameter.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101 |
| dialog:slicer_filament_dialog | bedienflaeche | quader_mit_slicer.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101 |
| filament.colour | bedienflaeche | leer | offen | FD-237 | — | offen | offen | offen | offen | FD-313 | ja | offen | FD-323 | offen | — | — | offen | offen | — | offen | offen | offen RM-747, RM-812 | FD-237, FD-313, FD-314, FD-315, FD-316, FD-323 |
| filament.picker | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-747 | FD-19, FD-243, FD-251, FD-268 |
| filament.profile | bedienflaeche | leer | offen | FD-237 | — | offen | offen | offen | offen | FD-313 | ja | offen | FD-323 | offen | — | offen | offen | offen | — | offen | offen | offen RM-747, RM-812 | FD-237, FD-313, FD-314, FD-316, FD-322, FD-323 |
| filament.section | bedienflaeche | quader.exakt | offen | offen | — | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | — | offen | offen | — | offen | offen | offen RM-747 | FD-132, FD-243 |
| filament.spool | bedienflaeche | sieben_filamente.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | FD-323 | offen | offen | offen | offen | offen | — | offen | offen | offen RM-747 | FD-315, FD-317, FD-319, FD-323 |
| meldung:_pick_colour | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-22, FD-101, FD-237 |
| meldung:_replacement_slot | bedienflaeche | sieben_filamente.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101 |
| meldung:action_counterpart | bedienflaeche | gewinde_zwei_reihen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101, FD-186 |
| menu:parameters.edit | bedienflaeche | parameter.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737 | FD-101, FD-174 |
| parameters | bedienflaeche | leer | offen | offen | — | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | — | offen | offen | — | offen | offen | offen RM-737, RM-747 | FD-126, FD-130 |
| parameters.bind | bedienflaeche | parameter.exakt | offen | offen | — | offen | offen | offen | offen | FD-313 | offen | offen | ja | offen | — | offen | offen | offen | — | offen | offen | offen RM-747 | FD-313, FD-318 |
| parameters.first | bedienflaeche | parameter.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-747 | FD-130, FD-174 |
| parameters.first.label | bedienflaeche | parameter.exakt | offen | offen | — | offen | offen | offen | offen | FD-313 | offen | offen | FD-323 | offen | — | — | offen | — | — | offen | offen | offen RM-747 | FD-313, FD-323 |
| parts.save | bedienflaeche | parameter.exakt | offen | offen | — | offen | offen | offen | offen | FD-313 | offen | offen | FD-320 | offen | offen | offen | offen | offen | — | offen | offen | offen RM-747 | FD-237, FD-313, FD-314, FD-320, FD-321 |

## Kriterien, die nicht erfüllt sind

| Kennung | Kriterium | Messwert | Schwelle | Fund |
|---|---|---|---|---|
| assign_slot | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| assign_slot | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| assign_slot | E3 | nicht gemessen | ≤ 1 | — |
| assign_slot | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| assign_slot | E5 | 36 Wörter über dem ersten Feld, erlaubt 25; 41 Wörter über dem ersten Feld, erlaubt 35; 43 Wörter über dem ersten Feld, erlaubt 35; 40 Wörter über dem ersten Feld, erlaubt 35; 38 Wörter über dem ersten Feld, erlaubt 35; 37 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| assign_slot | E6 | nicht gemessen | 0 | — |
| assign_slot | E7 | nicht gemessen | 0 | — |
| assign_slot | V1 | 0 Treffer | 0 | — |
| assign_slot | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| assign_slot | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| assign_slot | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| assign_slot | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| assign_slot | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| assign_slot | Z3 | Wegklick nach der Auswahl: klappe auf filament.picker | ja je Zeile mit Merkmals- oder Körperbezug | FD-242 |
| assign_slot | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| assign_slot | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | FD-242 |
| clear_filament | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| clear_filament | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| clear_filament | E3 | nicht gemessen | ≤ 1 | — |
| clear_filament | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| clear_filament | E6 | nicht gemessen | 0 | — |
| clear_filament | E7 | nicht gemessen | 0 | — |
| clear_filament | V1 | 0 Treffer | 0 | — |
| clear_filament | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| clear_filament | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| clear_filament | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| clear_filament | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| clear_filament | G4 | 29 Schriften | nur die Stufen aus `LEVELS`; keine Größe oder Farbe im Stylesheet | — |
| clear_filament | Z3 | Wegklick nach der Auswahl: klappe auf filament.picker | ja je Zeile mit Merkmals- oder Körperbezug | FD-268 |
| clear_filament | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| create_label | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| create_label | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| create_label | E3 | nicht gemessen | ≤ 1 | — |
| create_label | E6 | nicht gemessen | 0 | — |
| create_label | E7 | nicht gemessen | 0 | — |
| create_label | V1 | 0 Treffer | 0 | — |
| create_label | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| create_label | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| create_label | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| create_label | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| inlay_text | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| inlay_text | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| inlay_text | E3 | nicht gemessen | ≤ 1 | — |
| inlay_text | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| inlay_text | E6 | nicht gemessen | 0 | — |
| inlay_text | E7 | nicht gemessen | 0 | — |
| inlay_text | V1 | 0 Treffer | 0 | — |
| inlay_text | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| inlay_text | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| inlay_text | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| inlay_text | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| label_text | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| label_text | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| label_text | E3 | nicht gemessen | ≤ 1 | — |
| label_text | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| label_text | E6 | nicht gemessen | 0 | — |
| label_text | E7 | nicht gemessen | 0 | — |
| label_text | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| label_text | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| label_text | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| label_text | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| label_text | Z3 | Wegklick nach der Auswahl: reiter auf operation:label_text | ja je Zeile mit Merkmals- oder Körperbezug | FD-241 |
| paint_slot | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| paint_slot | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| paint_slot | E3 | nicht gemessen | ≤ 1 | — |
| paint_slot | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| paint_slot | E6 | nicht gemessen | 0 | — |
| paint_slot | E7 | nicht gemessen | 0 | — |
| paint_slot | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| paint_slot | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| paint_slot | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| paint_slot | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| paint_slot | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| paint_slot | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| paint_slot | Z3 | Wegklick nach der Auswahl: reiter auf filament.picker; Wegklick nach der Auswahl: klappe auf filament.picker | ja je Zeile mit Merkmals- oder Körperbezug | FD-241 |
| paint_slot | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| paint_slot | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| slots_from_texture | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| slots_from_texture | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| slots_from_texture | E3 | nicht gemessen | ≤ 1 | — |
| slots_from_texture | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| slots_from_texture | E6 | nicht gemessen | 0 | — |
| slots_from_texture | E7 | nicht gemessen | 0 | — |
| slots_from_texture | V2 | zu lang (eingefrorener Bestand): „Rechnet die Textur eines Objekts auf die Anzahl eingelegter Filamente um und speichert das Ergebnis als Filamentzuweisung.“ | die Grenzen aus `test_text_length` | — |
| slots_from_texture | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| slots_from_texture | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| slots_from_texture | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| slots_from_texture | Z3 | Wegklick nach der Auswahl: rollen auf operation:slots_from_texture | ja je Zeile mit Merkmals- oder Körperbezug | — |
| Bearbeiten/Material kalibrieren … | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| Bearbeiten/Material kalibrieren … | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| Bearbeiten/Material kalibrieren … | E3 | nicht gemessen | ≤ 1 | — |
| Bearbeiten/Material kalibrieren … | E6 | nicht gemessen | 0 | — |
| Bearbeiten/Material kalibrieren … | E7 | nicht gemessen | 0 | — |
| Bearbeiten/Material kalibrieren … | V3 | 9 von 9 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-267 |
| Bearbeiten/Material kalibrieren … | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-277 |
| Bearbeiten/Material kalibrieren … | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| Bearbeiten/Material kalibrieren … | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| Bearbeiten/Material kalibrieren … | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| Bearbeiten/Material kalibrieren … | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| Bearbeiten/Material kalibrieren … | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| Bearbeiten/Material kalibrieren … | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| Bearbeiten/Parameter anlegen … | E2 | 2 Eingaben | ≤ 1 bei 90% der Funktionen | — |
| Bearbeiten/Parameter anlegen … | E7 | Meldung ohne Handlung: „!  Der Name muss sich in einem Ausdruck als @name schreiben lassen — Buchstaben, Ziffern und Unterstriche.“ | 0 | FD-265 |
| Bearbeiten/Parameter anlegen … | V5 | Meldung ohne Handlung: „!  Der Name muss sich in einem Ausdruck als @name schreiben lassen — Buchstaben, Ziffern und Unterstriche.“ | jede Handlung löst das Problem | FD-265 |
| Bearbeiten/Parameter anlegen … | G5 | Anlegen: hover und rest sehen gleich aus | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | FD-266 |
| Bearbeiten/Parameter anlegen … | Z6 | 12 Flächen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | FD-282 |
| Bearbeiten/Parameter anlegen … | I1 | Art face ohne Name und Maß beim Überfahren | ja an jeder erkannten Art | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | E3 | nicht gemessen | ≤ 1 | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | E6 | nicht gemessen | 0 | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | E7 | nicht gemessen | 0 | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| Erzeugen/Bausteine/Gegenstücke setzen … | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:binding_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:binding_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:binding_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:binding_dialog | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:binding_dialog | E5 | 2 Felder, 20 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:binding_dialog | E6 | nicht gemessen | 0 | — |
| dialog:binding_dialog | E7 | nicht gemessen | 0 | — |
| dialog:binding_dialog | V1 | 0 Treffer | 0 | — |
| dialog:binding_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:binding_dialog | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Operation 1: Quader anlegen — Höhe: 20,00 mm“ ohne Kurzhilfe; Feld „Operation 1: Quader anlegen — Höhe: 20,00 mm“ ohne Beschreibung; Feld „Operation 1: Add a box — Height: 20.00 mm“ ohne Kurzhilfe; Feld „Operation 1: Add a box — Height: 20.00 mm“ ohne Beschreibung; Feld „Operación 1: Añadir una caja — Altura: 20,00 mm“ ohne Kurzhilfe; Feld „Operación 1: Añadir una caja — Altura: 20,00 mm“ ohne Beschreibung; Feld „Opération 1 : Ajouter un pavé — Hauteur : 20,00 mm“ ohne Kurzhilfe; Feld „Opération 1 : Ajouter un pavé — Hauteur : 20,00 mm“ ohne Beschreibung; Feld „Operazione 1: Crea un parallelepipedo — Altezza: 20,00 mm“ ohne Kurzhilfe; Feld „Operazione 1: Crea un parallelepipedo — Altezza: 20,00 mm“ ohne Beschreibung; Feld „Operação 1: Criar um paralelepípedo — Altura: 20,00 mm“ ohne Kurzhilfe; Feld „Operação 1: Criar um paralelepípedo — Altura: 20,00 mm“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:binding_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:binding_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:binding_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:binding_dialog | G2 | Abstand [11.0] in BindingDialog kein Vielfaches von 4; Abstand [9.0] in BindingDialog kein Vielfaches von 4; Abstand [6.0] in BindingDialog kein Vielfaches von 4 | Vielfaches von `SPACE` (4), je Gruppe einheitlich | — |
| dialog:binding_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:binding_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:calibration_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:calibration_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:calibration_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:calibration_dialog | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:calibration_dialog | E5 | 3 Felder, 18 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:calibration_dialog | E6 | nicht gemessen | 0 | — |
| dialog:calibration_dialog | E7 | nicht gemessen | 0 | — |
| dialog:calibration_dialog | V1 | 0 Treffer | 0 | — |
| dialog:calibration_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:calibration_dialog | V3 | 9 von 9 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:calibration_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:calibration_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:calibration_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:calibration_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:calibration_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:counterpart_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:counterpart_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:counterpart_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:counterpart_dialog | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:counterpart_dialog | E5 | 3 Felder, 18 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:counterpart_dialog | E6 | nicht gemessen | 0 | — |
| dialog:counterpart_dialog | E7 | nicht gemessen | 0 | — |
| dialog:counterpart_dialog | V1 | 0 Treffer | 0 | — |
| dialog:counterpart_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:counterpart_dialog | V3 | 6 von 6 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:counterpart_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:counterpart_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:counterpart_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:counterpart_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:counterpart_dialog | Z3 | Wegklick nach der Auswahl: aufklappen auf tree.row:obj_1.face_1; Wegklick nach der Auswahl: aufklappen auf tree.row:obj_2.face_1; Wegklick nach der Auswahl: menue auf menu:menubar.gegenstuecke_setzen; Wegklick nach der Auswahl: untermenue auf menu:menubar.gegenstuecke_setzen | ja je Zeile mit Merkmals- oder Körperbezug | — |
| dialog:counterpart_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:parameter_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:parameter_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:parameter_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:parameter_dialog | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:parameter_dialog | E5 | 3 Felder, 23 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:parameter_dialog | E6 | nicht gemessen | 0 | — |
| dialog:parameter_dialog | E7 | nicht gemessen | 0 | — |
| dialog:parameter_dialog | V1 | 0 Treffer | 0 | — |
| dialog:parameter_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:parameter_dialog | V3 | 6 von 6 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:parameter_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:parameter_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:parameter_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:parameter_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:parameter_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:recipe_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:recipe_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:recipe_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:recipe_dialog | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:recipe_dialog | E5 | 12 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:recipe_dialog | E6 | nicht gemessen | 0 | — |
| dialog:recipe_dialog | E7 | nicht gemessen | 0 | — |
| dialog:recipe_dialog | V1 | 0 Treffer | 0 | — |
| dialog:recipe_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:recipe_dialog | V3 | Feld „Breite“ ohne Kurzhilfe; Feld „Breite“ ohne Beschreibung; Feld „Name“ ohne Kurzhilfe; Feld „Name“ ohne Beschreibung; Feld „Beschreibung“ ohne Kurzhilfe; Feld „Beschreibung“ ohne Beschreibung; Feld „Autor“ ohne Kurzhilfe; Feld „Autor“ ohne Beschreibung; Feld „Beschriftung“ ohne Kurzhilfe; Feld „Beschriftung“ ohne Beschreibung; Feld „Linke Seite · 600 mm²“ ohne Kurzhilfe; Feld „Linke Seite · 600 mm²“ ohne Beschreibung; Feld „Rechte Seite · 600 mm²“ ohne Kurzhilfe; Feld „Rechte Seite · 600 mm²“ ohne Beschreibung; Feld „Vorderseite · 800 mm²“ ohne Kurzhilfe; Feld „Vorderseite · 800 mm²“ ohne Beschreibung; Feld „Rückseite · 800 mm²“ ohne Kurzhilfe; Feld „Rückseite · 800 mm²“ ohne Beschreibung; Feld „Unterseite · 1200 mm²“ ohne Kurzhilfe; Feld „Unterseite · 1200 mm²“ ohne Beschreibung; Feld „Oberseite · 1200 mm²“ ohne Kurzhilfe; Feld „Oberseite · 1200 mm²“ ohne Beschreibung; Feld „Lizenz“ ohne Kurzhilfe; Feld „Lizenz“ ohne Beschreibung; Feld „Einheit“ ohne Kurzhilfe; Feld „Einheit“ ohne Beschreibung; Feld „Platz im Dialog“ ohne Kurzhilfe; Feld „Platz im Dialog“ ohne Beschreibung; Feld „Description“ ohne Kurzhilfe; Feld „Description“ ohne Beschreibung; Feld „Author“ ohne Kurzhilfe; Feld „Author“ ohne Beschreibung; Feld „Label“ ohne Kurzhilfe; Feld „Label“ ohne Beschreibung; Feld „Left side · 600 mm²“ ohne Kurzhilfe; Feld „Left side · 600 mm²“ ohne Beschreibung; Feld „Right side · 600 mm²“ ohne Kurzhilfe; Feld „Right side · 600 mm²“ ohne Beschreibung; Feld „Front · 800 mm²“ ohne Kurzhilfe; Feld „Front · 800 mm²“ ohne Beschreibung; Feld „Back · 800 mm²“ ohne Kurzhilfe; Feld „Back · 800 mm²“ ohne Beschreibung; Feld „Bottom · 1200 mm²“ ohne Kurzhilfe; Feld „Bottom · 1200 mm²“ ohne Beschreibung; Feld „Top · 1200 mm²“ ohne Kurzhilfe; Feld „Top · 1200 mm²“ ohne Beschreibung; Feld „Licence“ ohne Kurzhilfe; Feld „Licence“ ohne Beschreibung; Feld „Unit“ ohne Kurzhilfe; Feld „Unit“ ohne Beschreibung; Feld „Place in the dialog“ ohne Kurzhilfe; Feld „Place in the dialog“ ohne Beschreibung; Feld „Nombre“ ohne Kurzhilfe; Feld „Nombre“ ohne Beschreibung; Feld „Descripción“ ohne Kurzhilfe; Feld „Descripción“ ohne Beschreibung; Feld „Etiqueta“ ohne Kurzhilfe; Feld „Etiqueta“ ohne Beschreibung; Feld „Lado izquierdo · 600 mm²“ ohne Kurzhilfe; Feld „Lado izquierdo · 600 mm²“ ohne Beschreibung; Feld „Lado derecho · 600 mm²“ ohne Kurzhilfe; Feld „Lado derecho · 600 mm²“ ohne Beschreibung; Feld „Cara frontal · 800 mm²“ ohne Kurzhilfe; Feld „Cara frontal · 800 mm²“ ohne Beschreibung; Feld „Cara trasera · 800 mm²“ ohne Kurzhilfe; Feld „Cara trasera · 800 mm²“ ohne Beschreibung; Feld „Cara inferior · 1200 mm²“ ohne Kurzhilfe; Feld „Cara inferior · 1200 mm²“ ohne Beschreibung; Feld „Cara superior · 1200 mm²“ ohne Kurzhilfe; Feld „Cara superior · 1200 mm²“ ohne Beschreibung; Feld „Licencia“ ohne Kurzhilfe; Feld „Licencia“ ohne Beschreibung; Feld „Unidad“ ohne Kurzhilfe; Feld „Unidad“ ohne Beschreibung; Feld „Lugar en el diálogo“ ohne Kurzhilfe; Feld „Lugar en el diálogo“ ohne Beschreibung; Feld „Nom“ ohne Kurzhilfe; Feld „Nom“ ohne Beschreibung; Feld „Auteur“ ohne Kurzhilfe; Feld „Auteur“ ohne Beschreibung; Feld „Libellé“ ohne Kurzhilfe; Feld „Libellé“ ohne Beschreibung; Feld „Côté gauche · 600 mm²“ ohne Kurzhilfe; Feld „Côté gauche · 600 mm²“ ohne Beschreibung; Feld „Côté droit · 600 mm²“ ohne Kurzhilfe; Feld „Côté droit · 600 mm²“ ohne Beschreibung; Feld „Avant · 800 mm²“ ohne Kurzhilfe; Feld „Avant · 800 mm²“ ohne Beschreibung; Feld „Arrière · 800 mm²“ ohne Kurzhilfe; Feld „Arrière · 800 mm²“ ohne Beschreibung; Feld „Dessous · 1200 mm²“ ohne Kurzhilfe; Feld „Dessous · 1200 mm²“ ohne Beschreibung; Feld „Face supérieure · 1200 mm²“ ohne Kurzhilfe; Feld „Face supérieure · 1200 mm²“ ohne Beschreibung; Feld „Unité“ ohne Kurzhilfe; Feld „Unité“ ohne Beschreibung; Feld „Place dans le dialogue“ ohne Kurzhilfe; Feld „Place dans le dialogue“ ohne Beschreibung; Feld „Nome“ ohne Kurzhilfe; Feld „Nome“ ohne Beschreibung; Feld „Descrizione“ ohne Kurzhilfe; Feld „Descrizione“ ohne Beschreibung; Feld „Autore“ ohne Kurzhilfe; Feld „Autore“ ohne Beschreibung; Feld „Etichetta“ ohne Kurzhilfe; Feld „Etichetta“ ohne Beschreibung; Feld „Lato sinistro · 600 mm²“ ohne Kurzhilfe; Feld „Lato sinistro · 600 mm²“ ohne Beschreibung; Feld „Lato destro · 600 mm²“ ohne Kurzhilfe; Feld „Lato destro · 600 mm²“ ohne Beschreibung; Feld „Fronte · 800 mm²“ ohne Kurzhilfe; Feld „Fronte · 800 mm²“ ohne Beschreibung; Feld „Retro · 800 mm²“ ohne Kurzhilfe; Feld „Retro · 800 mm²“ ohne Beschreibung; Feld „Lato inferiore · 1200 mm²“ ohne Kurzhilfe; Feld „Lato inferiore · 1200 mm²“ ohne Beschreibung; Feld „Lato superiore · 1200 mm²“ ohne Kurzhilfe; Feld „Lato superiore · 1200 mm²“ ohne Beschreibung; Feld „Licenza“ ohne Kurzhilfe; Feld „Licenza“ ohne Beschreibung; Feld „Unità“ ohne Kurzhilfe; Feld „Unità“ ohne Beschreibung; Feld „Posizione nella finestra“ ohne Kurzhilfe; Feld „Posizione nella finestra“ ohne Beschreibung; Feld „Descrição“ ohne Kurzhilfe; Feld „Descrição“ ohne Beschreibung; Feld „Rótulo“ ohne Kurzhilfe; Feld „Rótulo“ ohne Beschreibung; Feld „Lado esquerdo · 600 mm²“ ohne Kurzhilfe; Feld „Lado esquerdo · 600 mm²“ ohne Beschreibung; Feld „Lado direito · 600 mm²“ ohne Kurzhilfe; Feld „Lado direito · 600 mm²“ ohne Beschreibung; Feld „Frente · 800 mm²“ ohne Kurzhilfe; Feld „Frente · 800 mm²“ ohne Beschreibung; Feld „Traseira · 800 mm²“ ohne Kurzhilfe; Feld „Traseira · 800 mm²“ ohne Beschreibung; Feld „Face inferior · 1200 mm²“ ohne Kurzhilfe; Feld „Face inferior · 1200 mm²“ ohne Beschreibung; Feld „Face superior · 1200 mm²“ ohne Kurzhilfe; Feld „Face superior · 1200 mm²“ ohne Beschreibung; Feld „Licença“ ohne Kurzhilfe; Feld „Licença“ ohne Beschreibung; Feld „Unidade“ ohne Kurzhilfe; Feld „Unidade“ ohne Beschreibung; Feld „Lugar na caixa de diálogo“ ohne Kurzhilfe; Feld „Lugar na caixa de diálogo“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:recipe_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:recipe_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:recipe_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:recipe_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:recipe_dialog | Z3 | Wegklick nach der Auswahl: menue auf menu:menubar.bausteinkatalog | ja je Zeile mit Merkmals- oder Körperbezug | — |
| dialog:recipe_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:slicer_filament_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:slicer_filament_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:slicer_filament_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:slicer_filament_dialog | E4 | 3 Blickwechsel (karte_links → menue → menue → kopf → dialog → dialog → dialog) | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:slicer_filament_dialog | E5 | 3 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:slicer_filament_dialog | E6 | nicht gemessen | 0 | — |
| dialog:slicer_filament_dialog | E7 | nicht gemessen | 0 | — |
| dialog:slicer_filament_dialog | V1 | 0 Treffer | 0 | — |
| dialog:slicer_filament_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:slicer_filament_dialog | V3 | Feld „Suche“ ohne Kurzhilfe; Feld „Suche“ ohne Beschreibung; Feld „Hersteller“ ohne Kurzhilfe; Feld „Hersteller“ ohne Beschreibung; Feld „Material“ ohne Kurzhilfe; Feld „Material“ ohne Beschreibung; Feld „Search“ ohne Kurzhilfe; Feld „Search“ ohne Beschreibung; Feld „Manufacturer“ ohne Kurzhilfe; Feld „Manufacturer“ ohne Beschreibung; Feld „Búsqueda“ ohne Kurzhilfe; Feld „Búsqueda“ ohne Beschreibung; Feld „Fabricante“ ohne Kurzhilfe; Feld „Fabricante“ ohne Beschreibung; Feld „Recherche“ ohne Kurzhilfe; Feld „Recherche“ ohne Beschreibung; Feld „Fabricant“ ohne Kurzhilfe; Feld „Fabricant“ ohne Beschreibung; Feld „Matériau“ ohne Kurzhilfe; Feld „Matériau“ ohne Beschreibung; Feld „Ricerca“ ohne Kurzhilfe; Feld „Ricerca“ ohne Beschreibung; Feld „Produttore“ ohne Kurzhilfe; Feld „Produttore“ ohne Beschreibung; Feld „Materiale“ ohne Kurzhilfe; Feld „Materiale“ ohne Beschreibung; Feld „Pesquisa“ ohne Kurzhilfe; Feld „Pesquisa“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:slicer_filament_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:slicer_filament_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:slicer_filament_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:slicer_filament_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:slicer_filament_dialog | Z3 | Wegklick nach der Auswahl: menue auf menu:menubar.filamentlager; Wegklick nach der Auswahl: klappe auf filament.profile | ja je Zeile mit Merkmals- oder Körperbezug | — |
| dialog:slicer_filament_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:slicer_filament_dialog | Z6 | Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369; Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369; Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369; Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369; Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369; Rollleiste vorn in SlicerFilamentDialog bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| filament.colour | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| filament.colour | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| filament.colour | E3 | nicht gemessen | ≤ 1 | — |
| filament.colour | E5 | 7 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-314 |
| filament.colour | E6 | nicht gemessen | 0 | — |
| filament.colour | E7 | nicht gemessen | 0 | FD-237 |
| filament.colour | V3 | Feld „Gekauft am“ ohne Beschreibung; Feld „Geöffnet am“ ohne Beschreibung; Feld „Name“ ohne Kurzhilfe; Feld „Name“ ohne Beschreibung; Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Restmenge“ ohne Kurzhilfe; Feld „Restmenge“ ohne Beschreibung; Feld „Spulenpreis eintragen“ ohne Kurzhilfe; Feld „Spulenpreis eintragen“ ohne Beschreibung; Feld „Purchased on“ ohne Beschreibung; Feld „Opened on“ ohne Beschreibung; Feld „Remaining amount“ ohne Kurzhilfe; Feld „Remaining amount“ ohne Beschreibung; Feld „Enter spool price“ ohne Kurzhilfe; Feld „Enter spool price“ ohne Beschreibung; Feld „Fecha de compra“ ohne Beschreibung; Feld „Fecha de apertura“ ohne Beschreibung; Feld „Nombre“ ohne Kurzhilfe; Feld „Nombre“ ohne Beschreibung; Feld „Cantidad restante“ ohne Kurzhilfe; Feld „Cantidad restante“ ohne Beschreibung; Feld „Introducir precio de la bobina“ ohne Kurzhilfe; Feld „Introducir precio de la bobina“ ohne Beschreibung; Feld „Date d'achat“ ohne Beschreibung; Feld „Date d'ouverture“ ohne Beschreibung; Feld „Nom“ ohne Kurzhilfe; Feld „Nom“ ohne Beschreibung; Feld „Quantité restante“ ohne Kurzhilfe; Feld „Quantité restante“ ohne Beschreibung; Feld „Saisir le prix de la bobine“ ohne Kurzhilfe; Feld „Saisir le prix de la bobine“ ohne Beschreibung; Feld „Data di acquisto“ ohne Beschreibung; Feld „Data di apertura“ ohne Beschreibung; Feld „Nome“ ohne Kurzhilfe; Feld „Nome“ ohne Beschreibung; Feld „Quantità residua“ ohne Kurzhilfe; Feld „Quantità residua“ ohne Beschreibung; Feld „Inserisci il prezzo della bobina“ ohne Kurzhilfe; Feld „Inserisci il prezzo della bobina“ ohne Beschreibung; Feld „Data de compra“ ohne Beschreibung; Feld „Data de abertura“ ohne Beschreibung; Feld „Quantidade restante“ ohne Kurzhilfe; Feld „Quantidade restante“ ohne Beschreibung; Feld „Introduzir preço da bobina“ ohne Kurzhilfe; Feld „Introduzir preço da bobina“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-313 |
| filament.colour | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| filament.colour | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| filament.colour | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| filament.colour | G1 | 2 Hauptknöpfe in NewFilamentDialog; 2 Akzente in NewFilamentDialog | ≤ 1 Hauptaktion je Dialog oder Karte, ≤ 1 Akzent je Fenster | FD-315 |
| filament.colour | G3 | Felder in NewFilamentDialog nicht bündig: [0.0, 77.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 110.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 111.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 101.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 118.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 141.0] | bündig; Werte rechtsbündig mit Einheit | FD-316 |
| filament.picker | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| filament.picker | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| filament.picker | E3 | nicht gemessen | ≤ 1 | — |
| filament.picker | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| filament.picker | E5 | 36 Wörter über dem ersten Feld, erlaubt 25; 41 Wörter über dem ersten Feld, erlaubt 35; 43 Wörter über dem ersten Feld, erlaubt 35; 40 Wörter über dem ersten Feld, erlaubt 35; 38 Wörter über dem ersten Feld, erlaubt 35; 37 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-243 |
| filament.picker | E6 | nicht gemessen | 0 | — |
| filament.picker | E7 | nicht gemessen | 0 | — |
| filament.picker | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| filament.picker | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| filament.picker | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| filament.picker | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| filament.picker | Z3 | Wegklick nach der Auswahl: klappe auf filament.picker | ja je Zeile mit Merkmals- oder Körperbezug | FD-268 |
| filament.picker | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| filament.profile | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| filament.profile | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| filament.profile | E3 | nicht gemessen | ≤ 1 | — |
| filament.profile | E5 | 14 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-314 |
| filament.profile | E6 | nicht gemessen | 0 | — |
| filament.profile | E7 | nicht gemessen | 0 | FD-237 |
| filament.profile | V3 | Feld „Gekauft am“ ohne Beschreibung; Feld „Geöffnet am“ ohne Beschreibung; Feld „Name“ ohne Kurzhilfe; Feld „Name“ ohne Beschreibung; Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Restmenge“ ohne Kurzhilfe; Feld „Restmenge“ ohne Beschreibung; Feld „Spulenpreis eintragen“ ohne Kurzhilfe; Feld „Spulenpreis eintragen“ ohne Beschreibung; Feld „Purchased on“ ohne Beschreibung; Feld „Opened on“ ohne Beschreibung; Feld „Remaining amount“ ohne Kurzhilfe; Feld „Remaining amount“ ohne Beschreibung; Feld „Enter spool price“ ohne Kurzhilfe; Feld „Enter spool price“ ohne Beschreibung; Feld „Fecha de compra“ ohne Beschreibung; Feld „Fecha de apertura“ ohne Beschreibung; Feld „Nombre“ ohne Kurzhilfe; Feld „Nombre“ ohne Beschreibung; Feld „Cantidad restante“ ohne Kurzhilfe; Feld „Cantidad restante“ ohne Beschreibung; Feld „Introducir precio de la bobina“ ohne Kurzhilfe; Feld „Introducir precio de la bobina“ ohne Beschreibung; Feld „Date d'achat“ ohne Beschreibung; Feld „Date d'ouverture“ ohne Beschreibung; Feld „Nom“ ohne Kurzhilfe; Feld „Nom“ ohne Beschreibung; Feld „Quantité restante“ ohne Kurzhilfe; Feld „Quantité restante“ ohne Beschreibung; Feld „Saisir le prix de la bobine“ ohne Kurzhilfe; Feld „Saisir le prix de la bobine“ ohne Beschreibung; Feld „Data di acquisto“ ohne Beschreibung; Feld „Data di apertura“ ohne Beschreibung; Feld „Nome“ ohne Kurzhilfe; Feld „Nome“ ohne Beschreibung; Feld „Quantità residua“ ohne Kurzhilfe; Feld „Quantità residua“ ohne Beschreibung; Feld „Inserisci il prezzo della bobina“ ohne Kurzhilfe; Feld „Inserisci il prezzo della bobina“ ohne Beschreibung; Feld „Data de compra“ ohne Beschreibung; Feld „Data de abertura“ ohne Beschreibung; Feld „Quantidade restante“ ohne Kurzhilfe; Feld „Quantidade restante“ ohne Beschreibung; Feld „Introduzir preço da bobina“ ohne Kurzhilfe; Feld „Introduzir preço da bobina“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-313 |
| filament.profile | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| filament.profile | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| filament.profile | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| filament.profile | G3 | Felder in NewFilamentDialog nicht bündig: [0.0, 77.0]; Wert in NewFilamentDialog nicht rechtsbündig mit Einheit; Felder in NewFilamentDialog nicht bündig: [0.0, 110.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 111.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 101.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 118.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 141.0] | bündig; Werte rechtsbündig mit Einheit | FD-316 |
| filament.profile | G8 | Übergang -1 ms an Die Profile des Slicers werden gelesen — beim ersten Mal bis zu einer halben Minute., erlaubt 110 bis 220; Übergang -1 ms an Reading the slicer's profiles — up to half a minute the first time., erlaubt 110 bis 220; Übergang -1 ms an Leyendo los perfiles del slicer; la primera vez, hasta medio minuto., erlaubt 110 bis 220; Übergang -1 ms an Lecture des profils du slicer — jusqu'à une demi-minute la première fois., erlaubt 110 bis 220; Übergang -1 ms an Lettura dei profili dello slicer: la prima volta fino a mezzo minuto., erlaubt 110 bis 220; Übergang -1 ms an A ler os perfis do slicer; na primeira vez, até meio minuto., erlaubt 110 bis 220 | Übergang aus `motion`, 110-220 ms, abschaltbar | FD-316 |
| filament.section | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| filament.section | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| filament.section | E3 | nicht gemessen | ≤ 1 | — |
| filament.section | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| filament.section | E5 | 36 Wörter über dem ersten Feld, erlaubt 25; 41 Wörter über dem ersten Feld, erlaubt 35; 43 Wörter über dem ersten Feld, erlaubt 35; 40 Wörter über dem ersten Feld, erlaubt 35; 38 Wörter über dem ersten Feld, erlaubt 35; 37 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-243 |
| filament.section | E6 | nicht gemessen | 0 | — |
| filament.section | E7 | nicht gemessen | 0 | — |
| filament.section | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| filament.section | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| filament.section | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| filament.section | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| filament.section | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| filament.section | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| filament.spool | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| filament.spool | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| filament.spool | E3 | nicht gemessen | ≤ 1 | — |
| filament.spool | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| filament.spool | E5 | 17 Felder vorn, erlaubt 4; 46 Wörter über dem ersten Feld, erlaubt 25; 49 Wörter über dem ersten Feld, erlaubt 35; 55 Wörter über dem ersten Feld, erlaubt 35; 51 Wörter über dem ersten Feld, erlaubt 35; 50 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-319 |
| filament.spool | E6 | nicht gemessen | 0 | — |
| filament.spool | E7 | nicht gemessen | 0 | — |
| filament.spool | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| filament.spool | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| filament.spool | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| filament.spool | G1 | 2 Hauptknöpfe in OperationDialog; 2 Akzente in OperationDialog | ≤ 1 Hauptaktion je Dialog oder Karte, ≤ 1 Akzent je Fenster | FD-315 |
| filament.spool | Z3 | Wegklick nach der Auswahl: menue auf operation:label_text; Wegklick nach der Auswahl: klappe auf field:slot | ja je Zeile mit Merkmals- oder Körperbezug | FD-317 |
| meldung:_pick_colour | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| meldung:_pick_colour | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| meldung:_pick_colour | E3 | nicht gemessen | ≤ 1 | — |
| meldung:_pick_colour | E4 | 3 Blickwechsel (karte_links → menue → menue → kopf → dialog → dialog) | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| meldung:_pick_colour | E5 | 7 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| meldung:_pick_colour | E6 | nicht gemessen | 0 | — |
| meldung:_pick_colour | E7 | nicht gemessen | 0 | FD-237 |
| meldung:_pick_colour | V1 | 0 Treffer | 0 | — |
| meldung:_pick_colour | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| meldung:_pick_colour | V3 | Feld „Gekauft am“ ohne Beschreibung; Feld „Geöffnet am“ ohne Beschreibung; Feld „Name“ ohne Kurzhilfe; Feld „Name“ ohne Beschreibung; Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Restmenge“ ohne Kurzhilfe; Feld „Restmenge“ ohne Beschreibung; Feld „Spulenpreis eintragen“ ohne Kurzhilfe; Feld „Spulenpreis eintragen“ ohne Beschreibung; Feld „Purchased on“ ohne Beschreibung; Feld „Opened on“ ohne Beschreibung; Feld „Remaining amount“ ohne Kurzhilfe; Feld „Remaining amount“ ohne Beschreibung; Feld „Enter spool price“ ohne Kurzhilfe; Feld „Enter spool price“ ohne Beschreibung; Feld „Fecha de compra“ ohne Beschreibung; Feld „Fecha de apertura“ ohne Beschreibung; Feld „Nombre“ ohne Kurzhilfe; Feld „Nombre“ ohne Beschreibung; Feld „Cantidad restante“ ohne Kurzhilfe; Feld „Cantidad restante“ ohne Beschreibung; Feld „Introducir precio de la bobina“ ohne Kurzhilfe; Feld „Introducir precio de la bobina“ ohne Beschreibung; Feld „Date d'achat“ ohne Beschreibung; Feld „Date d'ouverture“ ohne Beschreibung; Feld „Nom“ ohne Kurzhilfe; Feld „Nom“ ohne Beschreibung; Feld „Quantité restante“ ohne Kurzhilfe; Feld „Quantité restante“ ohne Beschreibung; Feld „Saisir le prix de la bobine“ ohne Kurzhilfe; Feld „Saisir le prix de la bobine“ ohne Beschreibung; Feld „Data di acquisto“ ohne Beschreibung; Feld „Data di apertura“ ohne Beschreibung; Feld „Nome“ ohne Kurzhilfe; Feld „Nome“ ohne Beschreibung; Feld „Quantità residua“ ohne Kurzhilfe; Feld „Quantità residua“ ohne Beschreibung; Feld „Inserisci il prezzo della bobina“ ohne Kurzhilfe; Feld „Inserisci il prezzo della bobina“ ohne Beschreibung; Feld „Data de compra“ ohne Beschreibung; Feld „Data de abertura“ ohne Beschreibung; Feld „Quantidade restante“ ohne Kurzhilfe; Feld „Quantidade restante“ ohne Beschreibung; Feld „Introduzir preço da bobina“ ohne Kurzhilfe; Feld „Introduzir preço da bobina“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| meldung:_pick_colour | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| meldung:_pick_colour | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| meldung:_pick_colour | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| meldung:_pick_colour | G1 | 2 Hauptknöpfe in NewFilamentDialog; 2 Akzente in NewFilamentDialog | ≤ 1 Hauptaktion je Dialog oder Karte, ≤ 1 Akzent je Fenster | — |
| meldung:_pick_colour | G3 | Felder in NewFilamentDialog nicht bündig: [0.0, 77.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 110.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 111.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 101.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 118.0]; Felder in NewFilamentDialog nicht bündig: [0.0, 141.0] | bündig; Werte rechtsbündig mit Einheit | — |
| meldung:_pick_colour | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| meldung:_pick_colour | Z3 | Wegklick nach der Auswahl: menue auf menu:menubar.filamentlager | ja je Zeile mit Merkmals- oder Körperbezug | — |
| meldung:_pick_colour | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| meldung:_replacement_slot | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| meldung:_replacement_slot | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| meldung:_replacement_slot | E3 | nicht gemessen | ≤ 1 | — |
| meldung:_replacement_slot | E4 | 3 Blickwechsel (karte_links → karte_rechts → menue → menue → dialog → dialog → dialog → dialog) | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| meldung:_replacement_slot | E5 | 17 Felder vorn, erlaubt 4; 46 Wörter über dem ersten Feld, erlaubt 25; 49 Wörter über dem ersten Feld, erlaubt 35; 55 Wörter über dem ersten Feld, erlaubt 35; 51 Wörter über dem ersten Feld, erlaubt 35; 50 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| meldung:_replacement_slot | E6 | nicht gemessen | 0 | — |
| meldung:_replacement_slot | E7 | nicht gemessen | 0 | — |
| meldung:_replacement_slot | V1 | 0 Treffer | 0 | — |
| meldung:_replacement_slot | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| meldung:_replacement_slot | V3 | 18 von 18 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| meldung:_replacement_slot | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| meldung:_replacement_slot | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| meldung:_replacement_slot | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| meldung:_replacement_slot | G1 | 2 Hauptknöpfe in OperationDialog; 2 Akzente in OperationDialog | ≤ 1 Hauptaktion je Dialog oder Karte, ≤ 1 Akzent je Fenster | — |
| meldung:_replacement_slot | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| meldung:_replacement_slot | Z3 | Wegklick nach der Auswahl: reiter auf operation:label_text; Wegklick nach der Auswahl: menue auf operation:label_text; Wegklick nach der Auswahl: klappe auf field:slot | ja je Zeile mit Merkmals- oder Körperbezug | — |
| meldung:_replacement_slot | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| meldung:action_counterpart | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| meldung:action_counterpart | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| meldung:action_counterpart | E3 | nicht gemessen | ≤ 1 | — |
| meldung:action_counterpart | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| meldung:action_counterpart | E5 | 0 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| meldung:action_counterpart | E6 | nicht gemessen | 0 | — |
| meldung:action_counterpart | E7 | nicht gemessen | 0 | — |
| meldung:action_counterpart | V1 | 0 Treffer | 0 | — |
| meldung:action_counterpart | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| meldung:action_counterpart | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| meldung:action_counterpart | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| meldung:action_counterpart | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| meldung:action_counterpart | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| meldung:action_counterpart | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| meldung:action_counterpart | Z3 | Wegklick nach der Auswahl: aufklappen auf tree.row:obj_1.thread_1; Wegklick nach der Auswahl: aufklappen auf tree.row:obj_2.face_1; Wegklick nach der Auswahl: menue auf menu:menubar.gegenstuecke_setzen; Wegklick nach der Auswahl: untermenue auf menu:menubar.gegenstuecke_setzen | ja je Zeile mit Merkmals- oder Körperbezug | — |
| meldung:action_counterpart | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| menu:parameters.edit | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| menu:parameters.edit | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| menu:parameters.edit | E3 | nicht gemessen | ≤ 1 | — |
| menu:parameters.edit | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| menu:parameters.edit | E5 | 3 Felder, 23 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| menu:parameters.edit | E6 | nicht gemessen | 0 | — |
| menu:parameters.edit | E7 | nicht gemessen | 0 | — |
| menu:parameters.edit | V1 | 0 Treffer | 0 | — |
| menu:parameters.edit | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| menu:parameters.edit | V3 | 6 von 6 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| menu:parameters.edit | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| menu:parameters.edit | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| menu:parameters.edit | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| menu:parameters.edit | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| menu:parameters.edit | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| parameters | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| parameters | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| parameters | E3 | nicht gemessen | ≤ 1 | — |
| parameters | E6 | nicht gemessen | 0 | — |
| parameters | E7 | nicht gemessen | 0 | — |
| parameters | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| parameters | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| parameters | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| parameters | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| parameters.bind | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| parameters.bind | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| parameters.bind | E3 | nicht gemessen | ≤ 1 | — |
| parameters.bind | E6 | nicht gemessen | 0 | — |
| parameters.bind | E7 | nicht gemessen | 0 | — |
| parameters.bind | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Operation 1: Quader anlegen — Höhe: 20,00 mm“ ohne Kurzhilfe; Feld „Operation 1: Quader anlegen — Höhe: 20,00 mm“ ohne Beschreibung; Feld „Operation 1: Add a box — Height: 20.00 mm“ ohne Kurzhilfe; Feld „Operation 1: Add a box — Height: 20.00 mm“ ohne Beschreibung; Feld „Operación 1: Añadir una caja — Altura: 20,00 mm“ ohne Kurzhilfe; Feld „Operación 1: Añadir una caja — Altura: 20,00 mm“ ohne Beschreibung; Feld „Opération 1 : Ajouter un pavé — Hauteur : 20,00 mm“ ohne Kurzhilfe; Feld „Opération 1 : Ajouter un pavé — Hauteur : 20,00 mm“ ohne Beschreibung; Feld „Operazione 1: Crea un parallelepipedo — Altezza: 20,00 mm“ ohne Kurzhilfe; Feld „Operazione 1: Crea un parallelepipedo — Altezza: 20,00 mm“ ohne Beschreibung; Feld „Operação 1: Criar um paralelepípedo — Altura: 20,00 mm“ ohne Kurzhilfe; Feld „Operação 1: Criar um paralelepípedo — Altura: 20,00 mm“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-313 |
| parameters.bind | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| parameters.bind | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| parameters.bind | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| parameters.bind | G2 | Abstand [11.0] in BindingDialog kein Vielfaches von 4; Abstand [9.0] in BindingDialog kein Vielfaches von 4; Abstand [6.0] in BindingDialog kein Vielfaches von 4 | Vielfaches von `SPACE` (4), je Gruppe einheitlich | FD-318 |
| parameters.first | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| parameters.first | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| parameters.first | E3 | nicht gemessen | ≤ 1 | — |
| parameters.first | E6 | nicht gemessen | 0 | — |
| parameters.first | E7 | nicht gemessen | 0 | — |
| parameters.first | V3 | Feld „Breite“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| parameters.first | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| parameters.first | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| parameters.first | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| parameters.first.label | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| parameters.first.label | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| parameters.first.label | E3 | nicht gemessen | ≤ 1 | — |
| parameters.first.label | E6 | nicht gemessen | 0 | — |
| parameters.first.label | E7 | nicht gemessen | 0 | — |
| parameters.first.label | V3 | Feld „Breite“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-313 |
| parameters.first.label | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| parameters.first.label | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| parameters.first.label | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| parts.save | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| parts.save | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| parts.save | E3 | nicht gemessen | ≤ 1 | — |
| parts.save | E5 | 12 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-314 |
| parts.save | E6 | nicht gemessen | 0 | — |
| parts.save | E7 | nicht gemessen | 0 | FD-237 |
| parts.save | V3 | Feld „Breite“ ohne Kurzhilfe; Feld „Breite“ ohne Beschreibung; Feld „Name“ ohne Kurzhilfe; Feld „Name“ ohne Beschreibung; Feld „Beschreibung“ ohne Kurzhilfe; Feld „Beschreibung“ ohne Beschreibung; Feld „Autor“ ohne Kurzhilfe; Feld „Autor“ ohne Beschreibung; Feld „Beschriftung“ ohne Kurzhilfe; Feld „Beschriftung“ ohne Beschreibung; Feld „Linke Seite · 600 mm²“ ohne Kurzhilfe; Feld „Linke Seite · 600 mm²“ ohne Beschreibung; Feld „Rechte Seite · 600 mm²“ ohne Kurzhilfe; Feld „Rechte Seite · 600 mm²“ ohne Beschreibung; Feld „Vorderseite · 800 mm²“ ohne Kurzhilfe; Feld „Vorderseite · 800 mm²“ ohne Beschreibung; Feld „Rückseite · 800 mm²“ ohne Kurzhilfe; Feld „Rückseite · 800 mm²“ ohne Beschreibung; Feld „Unterseite · 1200 mm²“ ohne Kurzhilfe; Feld „Unterseite · 1200 mm²“ ohne Beschreibung; Feld „Oberseite · 1200 mm²“ ohne Kurzhilfe; Feld „Oberseite · 1200 mm²“ ohne Beschreibung; Feld „Lizenz“ ohne Kurzhilfe; Feld „Lizenz“ ohne Beschreibung; Feld „Einheit“ ohne Kurzhilfe; Feld „Einheit“ ohne Beschreibung; Feld „Platz im Dialog“ ohne Kurzhilfe; Feld „Platz im Dialog“ ohne Beschreibung; Feld „Description“ ohne Kurzhilfe; Feld „Description“ ohne Beschreibung; Feld „Author“ ohne Kurzhilfe; Feld „Author“ ohne Beschreibung; Feld „Label“ ohne Kurzhilfe; Feld „Label“ ohne Beschreibung; Feld „Left side · 600 mm²“ ohne Kurzhilfe; Feld „Left side · 600 mm²“ ohne Beschreibung; Feld „Right side · 600 mm²“ ohne Kurzhilfe; Feld „Right side · 600 mm²“ ohne Beschreibung; Feld „Front · 800 mm²“ ohne Kurzhilfe; Feld „Front · 800 mm²“ ohne Beschreibung; Feld „Back · 800 mm²“ ohne Kurzhilfe; Feld „Back · 800 mm²“ ohne Beschreibung; Feld „Bottom · 1200 mm²“ ohne Kurzhilfe; Feld „Bottom · 1200 mm²“ ohne Beschreibung; Feld „Top · 1200 mm²“ ohne Kurzhilfe; Feld „Top · 1200 mm²“ ohne Beschreibung; Feld „Licence“ ohne Kurzhilfe; Feld „Licence“ ohne Beschreibung; Feld „Unit“ ohne Kurzhilfe; Feld „Unit“ ohne Beschreibung; Feld „Place in the dialog“ ohne Kurzhilfe; Feld „Place in the dialog“ ohne Beschreibung; Feld „Nombre“ ohne Kurzhilfe; Feld „Nombre“ ohne Beschreibung; Feld „Descripción“ ohne Kurzhilfe; Feld „Descripción“ ohne Beschreibung; Feld „Etiqueta“ ohne Kurzhilfe; Feld „Etiqueta“ ohne Beschreibung; Feld „Lado izquierdo · 600 mm²“ ohne Kurzhilfe; Feld „Lado izquierdo · 600 mm²“ ohne Beschreibung; Feld „Lado derecho · 600 mm²“ ohne Kurzhilfe; Feld „Lado derecho · 600 mm²“ ohne Beschreibung; Feld „Cara frontal · 800 mm²“ ohne Kurzhilfe; Feld „Cara frontal · 800 mm²“ ohne Beschreibung; Feld „Cara trasera · 800 mm²“ ohne Kurzhilfe; Feld „Cara trasera · 800 mm²“ ohne Beschreibung; Feld „Cara inferior · 1200 mm²“ ohne Kurzhilfe; Feld „Cara inferior · 1200 mm²“ ohne Beschreibung; Feld „Cara superior · 1200 mm²“ ohne Kurzhilfe; Feld „Cara superior · 1200 mm²“ ohne Beschreibung; Feld „Licencia“ ohne Kurzhilfe; Feld „Licencia“ ohne Beschreibung; Feld „Unidad“ ohne Kurzhilfe; Feld „Unidad“ ohne Beschreibung; Feld „Lugar en el diálogo“ ohne Kurzhilfe; Feld „Lugar en el diálogo“ ohne Beschreibung; Feld „Nom“ ohne Kurzhilfe; Feld „Nom“ ohne Beschreibung; Feld „Auteur“ ohne Kurzhilfe; Feld „Auteur“ ohne Beschreibung; Feld „Libellé“ ohne Kurzhilfe; Feld „Libellé“ ohne Beschreibung; Feld „Côté gauche · 600 mm²“ ohne Kurzhilfe; Feld „Côté gauche · 600 mm²“ ohne Beschreibung; Feld „Côté droit · 600 mm²“ ohne Kurzhilfe; Feld „Côté droit · 600 mm²“ ohne Beschreibung; Feld „Avant · 800 mm²“ ohne Kurzhilfe; Feld „Avant · 800 mm²“ ohne Beschreibung; Feld „Arrière · 800 mm²“ ohne Kurzhilfe; Feld „Arrière · 800 mm²“ ohne Beschreibung; Feld „Dessous · 1200 mm²“ ohne Kurzhilfe; Feld „Dessous · 1200 mm²“ ohne Beschreibung; Feld „Face supérieure · 1200 mm²“ ohne Kurzhilfe; Feld „Face supérieure · 1200 mm²“ ohne Beschreibung; Feld „Unité“ ohne Kurzhilfe; Feld „Unité“ ohne Beschreibung; Feld „Place dans le dialogue“ ohne Kurzhilfe; Feld „Place dans le dialogue“ ohne Beschreibung; Feld „Nome“ ohne Kurzhilfe; Feld „Nome“ ohne Beschreibung; Feld „Descrizione“ ohne Kurzhilfe; Feld „Descrizione“ ohne Beschreibung; Feld „Autore“ ohne Kurzhilfe; Feld „Autore“ ohne Beschreibung; Feld „Etichetta“ ohne Kurzhilfe; Feld „Etichetta“ ohne Beschreibung; Feld „Lato sinistro · 600 mm²“ ohne Kurzhilfe; Feld „Lato sinistro · 600 mm²“ ohne Beschreibung; Feld „Lato destro · 600 mm²“ ohne Kurzhilfe; Feld „Lato destro · 600 mm²“ ohne Beschreibung; Feld „Fronte · 800 mm²“ ohne Kurzhilfe; Feld „Fronte · 800 mm²“ ohne Beschreibung; Feld „Retro · 800 mm²“ ohne Kurzhilfe; Feld „Retro · 800 mm²“ ohne Beschreibung; Feld „Lato inferiore · 1200 mm²“ ohne Kurzhilfe; Feld „Lato inferiore · 1200 mm²“ ohne Beschreibung; Feld „Lato superiore · 1200 mm²“ ohne Kurzhilfe; Feld „Lato superiore · 1200 mm²“ ohne Beschreibung; Feld „Licenza“ ohne Kurzhilfe; Feld „Licenza“ ohne Beschreibung; Feld „Unità“ ohne Kurzhilfe; Feld „Unità“ ohne Beschreibung; Feld „Posizione nella finestra“ ohne Kurzhilfe; Feld „Posizione nella finestra“ ohne Beschreibung; Feld „Descrição“ ohne Kurzhilfe; Feld „Descrição“ ohne Beschreibung; Feld „Rótulo“ ohne Kurzhilfe; Feld „Rótulo“ ohne Beschreibung; Feld „Lado esquerdo · 600 mm²“ ohne Kurzhilfe; Feld „Lado esquerdo · 600 mm²“ ohne Beschreibung; Feld „Lado direito · 600 mm²“ ohne Kurzhilfe; Feld „Lado direito · 600 mm²“ ohne Beschreibung; Feld „Frente · 800 mm²“ ohne Kurzhilfe; Feld „Frente · 800 mm²“ ohne Beschreibung; Feld „Traseira · 800 mm²“ ohne Kurzhilfe; Feld „Traseira · 800 mm²“ ohne Beschreibung; Feld „Face inferior · 1200 mm²“ ohne Kurzhilfe; Feld „Face inferior · 1200 mm²“ ohne Beschreibung; Feld „Face superior · 1200 mm²“ ohne Kurzhilfe; Feld „Face superior · 1200 mm²“ ohne Beschreibung; Feld „Licença“ ohne Kurzhilfe; Feld „Licença“ ohne Beschreibung; Feld „Unidade“ ohne Kurzhilfe; Feld „Unidade“ ohne Beschreibung; Feld „Lugar na caixa de diálogo“ ohne Kurzhilfe; Feld „Lugar na caixa de diálogo“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-313 |
| parts.save | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| parts.save | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| parts.save | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |

## Paketwerte

| Wert | Messung | Schwelle | Stand |
|---|---|---|---|
| E2-Anteil | 0% (0 von 1) | ≥ 90% | markiert |
| E5-Anteil | 70% (21 von 30) | ≥ 90% | markiert |
| I3-Anteil | 0% (0 von 1) | ≥ 80% | markiert |
| I4-Zahl | 38 von 394 mit Handlung, 356 Vorschläge | Zahl genannt | — |
| Zweitprüfer | 10% (3 von 30) | ≥ 10% der Zeilen | erfüllt |
| Runde | schlusslauf-d9f7a81f/L4-d0: D4, D8, D10 | — | — |
| Übereinstimmung 1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 8 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 9 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 10 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 11 in der Runde | 92% (12 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 12 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 13 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 14 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 15 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 16 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 17 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 18 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 19 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G8 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G9 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I1 in der Runde | 92% (12 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I3 in der Runde | 90% (9 von 10) | ≥ 90% | erfüllt |
| Übereinstimmung I4 in der Runde | 100% (9 von 9) | ≥ 90% | erfüllt |
| Übereinstimmung I5 in der Runde | 100% (9 von 9) | ≥ 90% | erfüllt |
| Übereinstimmung I6 in der Runde | 100% (11 von 11) | ≥ 90% | erfüllt |
| Übereinstimmung 1 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 3 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 4 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 5 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 6 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 7 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 8 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 9 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 10 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 11 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 12 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 13 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 14 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 15 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 16 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 17 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 18 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung 19 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E1 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E3 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E4 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E5 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E6 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung E7 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V1 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V3 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V4 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V5 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung V6 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G1 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G3 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G4 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G5 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G6 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G7 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G8 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung G9 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z1 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z3 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z4 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z5 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung Z6 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung I1 im Paket | 67% (2 von 3) | Auskunft | — |
| Übereinstimmung I2 im Paket | 100% (3 von 3) | Auskunft | — |
| Übereinstimmung I6 im Paket | 100% (1 von 1) | Auskunft | — |
