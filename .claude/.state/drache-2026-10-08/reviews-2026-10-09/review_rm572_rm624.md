# Review RM-572 (F:\sl-befund, 02d32ac15) und RM-624 (F:\sl-kontakt, c95d542ed)

Agent solidon3d-review, 09.10.2026 abends. Rechner zu 100 % ausgelastet, Zeiten sind CPU-Zeit.
Sonden: Scratchpad der Sitzung, `probe_*.py`.

## RM-572 — Urteil: nicht

**Schwer**

1. Falscher zweiter Befund an Inseln und langen Brücken (`findings.py:457`, 460–479).
   `need.needed` ist auch wahr, wenn allein eine Insel oder lange Brücke Stützen verlangt; `need.overhang`
   enthält Inselflächen. Sockel mit schwebendem 12-mm-Würfel: neben `slice.island_needs_support` auch
   „Viele kleine Überhänge …“ (144 mm²) an derselben Stelle; 20-mm-Würfel ebenso (400 mm²). 10-mm-Würfel aus
   `test_print_findings.py` hat genau 100,0 mm², deshalb unbemerkt. Zwei 20-mm-Brücken je 58 mm² (Summe
   115,8, `worth_support` False): `slice.small_overhangs` neben `slice.long_bridge`. Docstring Z. 453–455
   behauptet das Gegenteil.
   Fix: `worth_support(need.patch, need.overhang)` statt `need.needed`; Inselstücke wie in
   `overhang_findings` (Z. 398–404) aus Fläche, Schichtwahl, Ort nehmen; ohne Inseln mehr als
   `OVERHANG_REPORTED_FROM` verlangen; Test auf Berichtsebene.

**Mittel**

2. Bedarfsfrage jetzt ungefragt (`findings.py:229–233`): vorher nur unter der Bedingung der Lagensuche
   (Z. 239–243). Laptop-Riser, Kumiko (großes Stück), Spiderman, Drache (fragten schon) kosten nichts.
   17 kleine Modelle: eines neu (`carcassonne-4x4-grid`, +0,45 s, kein Befund). Mehr als acht Körper:
   Schachsatz je Figur 3,7–7,0 s, fünf Figuren 23,9 s, kein Befund. Archiv (`ROADMAP-ARCHIV.md:27344`)
   verschweigt das.
   Fix: `need` nur unter derselben Bedingung wie die Lagensuche (`search and support_volume >=
   ORIENT_WORTH_SUPPORT`), Archiv mit Zahlen.
3. Tests prüfen den Anschluss nicht (`test_slice_findings.py:1883–1901`, `test_advise.py:830–834`): rufen
   `small_overhang_findings` direkt; Ortszusicherung unterscheidet nichts (30 von 31 Schichten im Fenster,
   x/y ungeprüft).
   Fix: Fall über `print_findings` mit Ort im Kinngrundriss und `map_for == "overhang"`, Gegenfälle aus 1.

**Leicht**

4. Ort kann auf selbsttragendem Rand landen (Z. 463–467, 474–478): `ledges(result)` dazunehmen.
5. Fachwörter: fr „porte-à-faux“ statt Katalog „surplomb“ (`fr.json:2632`, `changelog/fr.md:85`), it
   „sporgenze“ statt „sbalzi“ (`it.json:2632`, `changelog/it.md:84`).
6. `konzepte/begruendungen/regel-druckrat.md:372–374` sagt noch, der Bericht nenne keine Stelle.

Bestätigt: Drache bekommt den Befund (z 102,75, 663,3 mm²), Kinn/Kiefer je einen, Gitterbecher keinen;
Text 10 Wörter ohne Semikolon; Regeln 1, 6, 7, 14, 17, 20 eingehalten.
Nebenbefund (nicht vom Zweig): `support_need` am Drachen kalt 438,6 s, warm 4,9 s; `model_support` läuft
ohne `cancelled` (`advise.py:879`).

## RM-624 — Urteil: nicht

**Mittel**

1. Kein Lauf auf Linux/macOS (keine Slicerauswahl für den Zweig). Offen: Anycubic 2.0.0.5 (Linux) gegen
   2.0.0.3 (Mac), Laufzeit gegen 120-min-Joblimit (bisher bis 77 min). Nach Roberts Vorgabe läuft CI nur
   beim Push auf main.
2. Unter Bäumen wird ein verlorener Abstand nicht rot (`test_real_slicers.py:396, 436–437`): Erwartet 0,2;
   die 0,20-mm-Standardprozesse von Orca K1Max, Creality K1 Max, Bambu A1, Elegoo N4, Prusa MK4S führen
   selbst 0,2. Fix: unter Bäumen 0,44 setzen, 0,4 erwarten; unter Gitter ±0,02 statt ±0,04.
3. Verbotstest über womöglich leere Menge (`:448–449`): `not measured.bottom_interface_layers` auch bei
   `None` grün. Fix: `bottom_cells > 20` mitsichern (RM-622-G-Codes: 64–244 Zellen).
4. Unterseite unter Gitter nicht messbar: Stützschichthöhe aus allen Stützebenen zusammen
   (`helpers.py:2346`); Elegoo-Gitter liefert 0,0 mm mit 1 bzw. 0 Lagen, alte Sonde maß 0,2. Archivbegründung
   (`ROADMAP-ARCHIV.md:27348`) falsch: Kommentar zu `IGNORED_UNDER_TREES_BY_PROGRAM` sagt „unter Gitter mit
   unteren Lagen“. Fix: Unterseite gegen den eigenen Stützstapel der Zelle oder `;HEIGHT:` messen, unter
   Gitter mindestens eine Lage zusichern — sonst ins Register.

**Leicht**

5. PrusaSlicers `Skirt/Brim` zählt als Modell (`helpers.py:2241`): `inset=4.0` wirkt bei Prusa nicht
   (618/106 Zellen; mit dem Typ in `_CONTACT_SKIPPED` 482/89).
6. G2/G3 übergangen (`helpers.py:2326`): weder gezählt noch nachgeführt, nächster G1 zieht Phantomstrecke.
   Baum-G-Codes: 37 214 Bögen (Prusa), 33 088 (Bambu), 19 014 (Creality).
7. Docstring `helpers.py:2300` spricht von Aufsicht, Z. 2353 nimmt das Hüllrechteck.
8. Hilfe in `tests/helpers.py` verteuert die CI: 175 Dateien importieren sie, `ci_selection` wählt 39
   Fensterdateien mit. Besser in `test_real_slicers.py` oder eigenem Modul.
9. Karte `tests/CLAUDE.md:44` und `:114` nicht nachgezogen.

Bestätigt: G92-Gegenprobe hält (−0,4 statt 0,2, rot); unter Gitter wird ein hängengebliebener Abstand rot;
Regeln 11 und 15 eingehalten.
