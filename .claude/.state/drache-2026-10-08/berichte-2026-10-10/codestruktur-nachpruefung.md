# Nachprüfung `solidon3d-review` zum überarbeiteten Konzept Codestruktur (11.10., ~14:00)

Urteil: abgabefähig, sobald M-1 bis M-6 eingetragen sind; keine schweren Funde mehr. S1–S4 und
M1–M7 beider Berichte behoben (M4 des konzept-Berichts teilweise → M-1). Skripte:
`F:\tmp-agenten\struktur\pruef3\` (laengen.out).

## Mittel
- **M-1** Selbsttyp `self: MainWindow` ändert `ast.dump` jeder Mixin-Methode; Beweis erlaubt ihn
  nicht, kein Werkzeug setzt ihn → Selbsttyp als erlaubte, vom Werkzeug gesetzte Änderung.
- **M-2** Wirtsprotokoll noch in 4.2 Punkt 1 und „Protokoll“ in Punkt 5.
- **M-3** Zwei Zählweisen gemischt: bei Namen, die das Modul selbst liest bzw. alle Patches —
  features 123, main_window 166, session 73, print_settings_dialog 72, viewport 39 (Modulobjekt,
  Text, mock.patch, Alias je Funktion; `pruef2/scan_patches2.out:204–213`).
- **M-4** Startzeit §31 je UI-Schritt wäre lokale Fenster-/Leistungsmessung (CI schließt
  `performance` aus, `build.yml:212`, `:1905`) → misst der nächste Release-Lauf.
- **M-5** W1 ohne Startpuffer: jede Zeile mehr in einer gelisteten Datei wäre rot → heutige Zahl
  plus 50; neue Funktionen in neues Modul, Fixe in bestehenden Rümpfen im Puffer.
- **M-6** Mit allen Karten auf dem Weg (dazu `app/CLAUDE.md` 2 708 B) liegen main_window
  (163,2 KB) und placement_flow (162,7 KB) schon heute über 160 KB → Ziel fest: höchstens 145 KB.

## Leicht
- **L-1** `ring.py`, `thread.py`, `shared.py` tragen keine Op (Ringhelfer ab 17136, Gewindehelfer ab
  17591; `_remove_thread` aus `remove_feature` :8194, `_resize_thread` aus `resize_feature` :9900) →
  Bootstrap nennt nur Module mit Ops.
- **L-2** Flache Leser: 17 Stellen in sieben Dateien (+ `test_translations.py:1763` über agent/);
  CS-2 nennt 1147 (Gegenprobe), Verbotsprüfung ist 1101; `test_features.py:3005` zweite Gegenprobe
  (`>= 10`) → CS-12.
- **L-3** CS-8 widerlegt: Bauplan Z. 3504 nennt `ui/panels`.
- **L-4** CS-1: 829 Zeilen sind `SketchPanel.__init__`.
- **L-5** CS-9: `tests/test_matching.py:22/180` ruft `_cost_matrix` direkt.
- **L-6** CS-14: Muster wird in 3.3 gewählt.
- **L-7** Kein Wächter für `# mypy: disable-error-code="misc"` → nur in Mixin-Modulen zulassen.
- **L-8** Frage 3 deckt nur Schritte 4–6; Schritt 2 und UI-Dateien aus 7 auch UI.
- **L-9** Weitere MainWindow-Importe in tools/: make_gallery 212, make_web_images 710,
  run_ui_audit 494, window_memory 107, window_bench 263, make_video 3373ff., make_longform_video 65.
- **L-10** „394 Commits im Monat“ → seit 01.09. (41 Tage); Session `super()` 1; Overrides auch
  PrintSettingsDialog 6, SketchCanvas 5, Session 1.
- **L-11** Offene Funde ohne Registernummer: CS-2, 6, 9, 10, 12, 13 unabhängig vom Programm ins
  Register.
- **L-12** Abdruck des Bereichsnachweises nicht transitiv (`range_proof.py:133–153`): beim Teilen von
  `geom/prepare` deckt er nur das Teilmodul mit `ray_hits_along` → Zuschnitt hält es mit Helfern zusammen.
