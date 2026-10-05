# Sollliste Teil C — Drucken, Dateien, Lager (Unterprüfer der Sollliste, 22.09.2026)

Nur gelesen. Sonden im Scratchpad `C\` (`ops.py`, `findings.py`, `fitprobe.py`).

| ID | Einlösung | Urteil | Beleg bzw. was fehlt | Risiko |
|---|---|---|---|---|
| C1 | ReportPanel `panels.py:3656`; `_by_severity` :306-312; Zählzeile :4434-4438; Klick `_on_finding_activated` `main_window.py:12152-12174`, `maps.location_of` `maps.py:1323-1353`; `actions_for` `panels.py:538-571`, `FINDING_ACTIONS` 33 Kennungen (:328) | **teilweise** | AST-Sonde: 324 Befundstellen mit fester Kennung, **276 ohne `suggestions` und ohne Tabelleneintrag**, darunter 97 Warnungen und 7 Fehler: `fit.violated` (`scene/fits.py:373`, :842-844), `gcode.spool_left_out` (Fehler, `export/handover.py:2710`), `join.blocked` (Fehler, `geom/prepare.py:2751`), `orient.support_likely` (`geom/orient.py:588`). `Finding.suggestions` Vorgabe leer (`types.py:1398`). Handbuchbild `website/handbuch/de/report.png` fünf Befunde ohne Knopf. Wände unter zwei Bahnen nur Bohrungsmantel (`evaluate.py:3401-3455`) und Aushöhlen; allgemein nur Karte. „Fehlende Einheiten" Rückfrage, kein Berichtseintrag. Sprung nur mit Ort/Merkmal („über alle elf Beispiele trägt genau ein Befund einen Ort", `main_window.py:12204`). | Umsteiger ohne nächsten Schritt |
| C2 | Chat `agent/analysis.py:148-160, 271-277`; Schichtwerkzeug `analysis_bar.py:552-556`; `orient.searched` `slice/orientation.py:510-522` | **nicht eingelöst** | Kein Inselbefund, kein Stützvolumen je Insel, kein Drehwinkel. Schichtleiste nur Inselzahl und Überhangfläche. Bauplan §22.3 („Insel-Warnungen im Prüfbericht") offen. | Kernsatz von fünf Pressemails (01, 04, 08, 17, 19) |
| C3 | `slice/analysis.py:194-221`; Karten Überhang/Wandstärke/Stützbedarf; `orient_for_print` | **teilweise** | Brückenweiten gemessen, im Fenster unsichtbar: `slice.long_bridge` nur in `advise.warnings_for` (`advise.py:1127, 1310, 1324-1357`) — **kein Aufrufer in app/**. Stützvolumen nur Tooltip/Chat. §31 hohle Schale 1,49–1,62 s (RM-201). RM-190. | Kunde sucht weiter im Slicer |
| C4 | Herkunft im Tooltip; Menüwege Drucken vorbereiten, An den Slicer übergeben, Slicen, Im Slicer öffnen, G-Code gegenprüfen | **überwiegend eingelöst** | Familien `slicer_keys.py:763-783`. Orca-Familie 3MF-Beilage + `--load-settings`, Prusa INI (`handover.py:2180-2211`). **Cura: STL mit allen Plattenteilen; Werte nur beim „Slicen" als `-s` an CuraEngine (:2212-2243), ein Filamentsatz; „Im Slicer öffnen" gibt Cura STL ohne Einstellungen (:3261).** Herkunft nur im Tooltip. RM-163/164/191. | Cura-Nutzer erwartet Einstellungen |
| C5 | `resolve_tolerance` `profiles.py:494-523`; „Material kalibrieren …" | **teilweise** | Alle Materialien `calibrated = false` (`materials.toml:39, 51 …`); Hinweis `settings.uncalibrated_material` in toter `warnings_for` (`advise.py:1165-1176`). Presssitz misst die Leiter nicht; bündig = 0. **Passungen aus Automatisch teilen/Deckel speichern `auto:<id>` bei Anlage (`split.py:576`, `lid_flow.py:90`); `change_scene_profile` (`ui/session.py:1650-1677`) schreibt sie nicht um.** Sonde: teilen mit PETG, auswerten mit TPU → zweimal `fit.violated` ohne Knopf. | falsche Passungswarnungen |
| C6 | Kalibrierbausteine, Kalibrierdialog | eingelöst | Werte von Hand; „Toleranzleiter" heißt „Toleranz-Testkörper". | gering |
| C7 | Automatisch teilen | eingelöst | nur achsparallel (RM-080), Stiftseite (RM-005), Materialbindung wie C5. | gering |
| C8 | `split_line`, Stiftformen | teilweise | **„Teilen" (`split_pinned`) aus dem Operationsdialog legt keine Passungsbeziehung an** (`main_window.py:14870-14884`); Website zählt es dazu (`funktionen.html:485`). | falsche Sicherheit |
| C9 | `cut_away` | eingelöst | nur achsparallel; **offenes Netz: kein Deckel, keine Meldung**. | gering |
| C10 | 16 FDM + 2 Resin; eigener Drucker | überwiegend | **Schichthöhe kein Feld** (FAQ ix:975-981 „Bauraum und Schichthöhe"). | gering |
| C11 | Bett, Ausrichten, Anordnen, Kollision | eingelöst | | |
| C12 | Filamentlager | überwiegend | **Slicer-Übernahme liest Orca-Familie und Prusa, nicht Cura** (`slicer_profiles.py:406-473`). Kopfzeile zeigt kein Filament mehr (`header.py:343-348`). | gering |
| C13 | Formate | eingelöst | STEP nur exakt; Export-Tooltip nennt kein GLB (`main_window.py:3297-3299`). | gering |
| C14 | Drop `main_window.py:19214-19237` → `accepted_url` (`start_screen.py:474-491`); `fetch.py:183-265`, Abweisung Webseiten :342-362 | **weitgehend nicht eingelöst** | Nur direkte http(s)-Links mit Modell-Endung. **Modellseiten-Link beim Ziehen stumm abgewiesen (Verbotszeiger, kein Satz)**; Test sichert Ablehnung von `…/modelle/17`. Seiten nicht ausgewertet, ZIP nicht lesbar. | **hoch:** erste Geste aus dem Weg-1-Film scheitert stumm |
| C15 | Schließen beim Einlesen, Einheitenfrage, Textur, Slots | teilweise | (c) automatische Kette nur im Generatorweg (abgeschaltet); (e) Filamentzahl Eingabe, nichts aus Drucker/AMS/Slicer. | mittel |
| C16 | Kennzahlen, Netzfehler, Bett | teilweise | Überhangwinkel je Schicht nur Fläche; Brückenweiten/schmalste Stelle nur Chat. | Vergleichstabelle |
| C17 | Slicersuche | eingelöst | | |
| C18 | `confirm_export` | eingelöst (Export) | **Slicer-Übergabe fragt vorher nicht**; nur Berichtsknopf verschwindet bei Fehler. | gering |
| C19 | `resize_hole` + Übergabe | eingelöst | Menüname „Drucken vorbereiten …". | gering |
| C20 | Mehrfarbige Spule, Platten nach Filament, Düsen | eingelöst mit Vorbehalt | RM-163: Bambu-Konsole halb; `gcode.spool_left_out` Fehler ohne Handlung. | AMS-Nutzer ohne Ausweg |

## Widersprüche Text ↔ App
1. „Jeder Befund trägt einen Handlungsvorschlag" (fk:427, ix:386-388, ix:640-642) — 276 Stellen ohne Knopf.
2. Bild zum Prüfbericht (fk:432-435): Alternativtext/Bildunterschrift passen nicht zum Bild (Dose, 0/1/4); zitierte Sätze gibt es nicht.
3. Presse Insel/Lage/Drehwinkel (01, 04, 08, 17, 19) — nicht gebaut.
4. „Wechselt man auf PLA, ändert sich das Spiel mit" (Mail 18:28) — Passung bleibt `auto:petg`.
5. „nicht geschätzt" (ix:432-433) — alle Materialien Startwerte, Hinweis erscheint nie.
6. FAQ Schichthöhe (ix:975-981).
7. Link von der Modellseite ziehen (ix:460-462).
8. Brückenweiten/schmalste Stelle (fk:442-446, ki:118-119).
9. „Die Kopfzeile nennt, was die Szene trägt" (fk:565-567).
10. Weg 3 „teilt oder verstiftet bei Bedarf", „Zahl, die wirklich in der Maschine steckt" (ix:489-491, ki:94-97).
11. `split_pinned` Passung (fk:485).
12. Namen: Toleranzleiter/Toleranz-Testkörper; Auto-Split/Automatisch teilen; Materialart/Typ; Drucken vorbereiten; GLB fehlt ix:804-805 und Export-Tooltip; „Überhangwinkel je Schicht".
13. Bauplan §22.3 selbst nicht eingelöst.

## Lücken nach Schwere
1. C2/C3/C16 Prüfbericht ohne Inseln/Brücken/Stützmengen; `advise.warnings_for` tot (`slice.long_bridge`, `settings.wall_below_nozzle`, `settings.uncalibrated_material`, Material-/Temperaturwarnungen).
2. C1 Warnungen/Fehler ohne Handlung (`fit.violated`, `gcode.spool_left_out`, `join.blocked`).
3. C14 Modellseiten-Link stumm abgewiesen.
4. C5 Passungen am Anlagematerial; Startwerte nie genannt.
5. C8 „Teilen" ohne Passung.
6. C10, C12, C15e, C4 Cura, RM-163/164/191, RM-201.
