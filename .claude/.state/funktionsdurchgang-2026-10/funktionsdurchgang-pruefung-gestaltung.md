# Prüfbericht `bedienlogik` zu Z1–Z6 und I1–I6 (11.10., Konzept Funktionsdurchgang)

Urteil: nicht tragfähig in dieser Fassung; mit den Textänderungen tragfähig. Aus Code und Regeln.

## Schwer
1. Z1 „Vorschau ≤ 100 ms“ gegen §31 (Parameteränderung, Boolesche < 2 s,
   `3d-agent-bauplan.md:2739ff.`), §2.8, `wartezeit.md:28-36`; „Zwischenform“ gibt es nicht (grob nur ab
   `COARSE_PREVIEW_ABOVE`, sonst „Voriger Stand“, `oberflaeche.md:242`, `:272`); ≤ 33 ms nur mit
   Bildzähler messbar. Vorschlag: Griff, Geist, Zahl im nächsten gemalten Bild ≤ 33 ms (Bildzähler,
   umgerechnet wie §31); Vorschau hält §2.8 und §31, sonst Prüfpunkt 6.
2. Z3 „Rechtsklick“ gegen §2.6/§18.5 („Der Rechtsklick führt keine Operation aus“,
   `3d-agent-bauplan.md:233-236`, `:1446-1451`); Panel = Blickwechsel (E4); Lesart schwebende Leiste.
   Vorschlag: nach Klick auf die Stelle ohne Menü und Suche da, als Feld oben im Merkmalfenster oder
   Hauptaktion im Reiter *Auswahl*; ja/nein.
3. I-Einstufung „Vorschlag, kein Mangel“ stuft Bauplanzusagen herab (I1 §18.5, I5 §18.7, I6 Chat
   §2.6/Regel 16) → Bauplanzusagen sind Funde.

## Mittel
4. Z2: `OperationDialog` nicht modal (`main_window.py:22974` `show()`); echte Treffer `QMessageBox.information`
   im Freischaltweg (`dialogs.py:2302, 2318, 2361, 2804`); bewusst modal Regel 19 (`main_window.py:8988`),
   KI-/Druckhinweis (`ai_disclosure.py:360`, `print_disclosure.py:179`). Vorschlag:
   `QApplication.activeModalWidget()` nach jeder Handlung = `None`, Ausnahmen Regel 19, KI-/Druckhinweis,
   Speicherfrage, Systemdateidialoge.
5. Z5 Ansichtssache, doppelt Z2/G4; Bestand `QInputDialog` (filament_picker, sketch_editor, main_window,
   install_dialog), `QColorDialog` (filament_picker, print_settings_dialog). Vorschlag: Instanzen von
   `QMessageBox`, `QInputDialog`, `QColorDialog` im Kundenweg = 0, außer `QFileDialog` und Z2-Liste.
6. I3 „wahrscheinlichste“ nicht messbar (`grenzen.md:111-116`, `selection_operations.py:251-302`);
   „Schnellaktion“ heißt „Hauptaktion“; Feld im Merkmalfenster ist kürzerer Weg (`grenzen.md:136-140`).
   Vorschlag: Liste häufigster Kundenziele, ≥ 80 % ohne Suche und Aufklappen als Hauptaktion
   (`quick_names`) oder Feld oben (`ACTION_ORDER`).
7. I2 Band nennt Befunde schon (`oberflaeche.md:247-250`, `review_difference`); Vorschau lässt
   Druckprüfung bewusst aus (`wartezeit.md:283-287`); Druckzeitanteil braucht Herkunft (Regel 14, §22.5).
8. I4 zirkulär; Vorschlag: Befundarten mit behebender Handlung zählen, Art ohne Handlung = Vorschlag.
9. I6 Suche arbeitet mit Wörtern; Chat nur Stufe C; doppelt Prüfpunkt 1 und 17. Vorschlag: Suchproben
   als Frage formuliert, Treffer unter den ersten drei; Chat Prüfpunkt 17.

## Leicht
10. I1 „anfassen“ doppelt G9; Arten ohne Operation (Torus, Verrundung, Gewinde,
    `selection_operations.py:278-286`) → Name und Maß beim Überfahren (§18.5); anfassen nur mit
    `REGISTRY.for_feature`.
11. I5 bezieht sich auf die Transaktion und die Szene (§18.7, `panels.py:5017`); nur Zeile D11.
12. Z4 doppelt E7; gewollt leere Karten → nur „hat der Zustand eine nächste Handlung, steht sie als
    Knopf dabei“.
13. Z6 doppelt G6/Prüfpunkt 9; Startgröße 1280 × 820 (`main_window.py:3067`); Vorschlag 1280 × 820 und
    1366 × 728 ohne Rollleiste, Symbole scharf 100/150/200 %, hell/dunkel gleiche Flächen und Akzente.
14. „Die Grenze“ doppelt; schärfen: Fix oder Vorschlag aus Z/I nur, wenn E/V an derselben Zeile
    vorher/nachher nicht schlechter.
15. Vergleich: Z1/Z2 nicht am Bild; Bilder je Durchgang fest (Programm, Version, Datum) außerhalb des
    Baums; Bambu Studio/OrcaSlicer, Tinkercad, Shapr3D (Plasticity ist CAD-Zielgruppe); besser/gleich/
    schlechter mit Unterschied.

## Fehlt
- a) Neuerung zählt nur, wenn im gewöhnlichen Weg ohne Handbuch sichtbar (Prüfpunkt 1, V6).
- b) Z7 erste fünf Minuten (§2.3): Start bis erster übernommener Schritt am eigenen Modell, Schritte und
  Fehlklicks, Stufe C.
- c) Kamera: eigene Belegung ist Roberts Entscheidung (§2.9), kein „wie im Slicer“.
