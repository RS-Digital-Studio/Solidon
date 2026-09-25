# Bedienweg der Reparatur-Durchsicht — Stand je Punkt (25.09.2026)

Grundlage: `.claude/.state/dreieck-reparatur-claude-2026-09-24/bericht-bedienweg.md`.
Entscheidungsmaßstab: Roberts Vorgabe vom 25.09.2026 — „das Beste für den
Kunden, den Druck und das Modell".

| Punkt | Stand | Wo |
|---|---|---|
| A1 große Öffnung: Ort, *Stelle zeigen*, *Offen lassen* | erledigt | `repair.wide_hole_filled` (Ort, `SHOW_LOCATION`), `MainWindow._show_error_place` |
| A2 Fläche ohne Dicke | erledigt (Reparatursitzung) | `repair.no_thickness`, *Dicke geben* |
| A3 Volumen der Flosse | erledigt (Reparaturkern); Volumenwarnung verworfen | offenes/verzweigtes Netz hat vorher kein belastbares Volumen |
| A4 zu viele Infozeilen | erledigt: Leerlauf-Zeilen nur im Protokoll; Sammelzeile verworfen | `weld_skipped`, `degenerate_kept` |
| A5 ineinandersteckende Teile | erledigt | `repair.parts_that_cross`, `loader._count_components` |
| A6 unlesbare Einschlüsse | erledigt | `perceive.voids_unreadable` mit `SHOW_LAYERS`, `SHOW_LOCATIONS` |
| B1 Karte → Reparatur | erledigt | `MainWindow._offer_repair_on_the_map` |
| B2 Legende in Kundenwörtern | erledigt (Reparatursitzung) | `maps.DEFECT_LEVELS` |
| B3 „in Ordnung" in Körperfarbe | erledigt | `palette.category_colours`, `viewport`, `analysis_bar` |
| C1–C4 Überschneidungen | erledigt (Reparatursitzung) | `RESOLVE_INTERSECTIONS`, Texte, Vorgabe an |
| C5 verlorene Formdetails | erledigt: am `repair`-Schritt still | `evaluate._with_features` |
| D1, D2, D5 | erledigt (Reparatursitzung) | `SETTLED_BY`, `ONE_PIECE_CODES`, Rest-Texte |
| D3 Suche beim Kleinteile-Knopf | bleibt; Ursache (eigene Lochfüllung) behoben | Migration 34 → 35 braucht die Suche |
| D4 `not_watertight` | erledigt: Zustandssatz | `loader`, `step_ops` |
| D6 Dauerwarnung | bleibt Warnung (begründet) | am Korpus 0 von 485 Körpern |
| E1–E7 große Modelle | RM-238 (Mausoleum), eingelöst | `perceive.local`, `ui.local_recognition*` |
| RM-241 | erledigt, archiviert | `wide_holes`, Bauplan §17.1 |

## Messungen

- `korpus_import.py` über `F:\3D Dateien` (172 Dateien, 485 Körper), zweiter
  Lauf mit der Paarsuche: 0 Fehler, Import 98,7 s, davon Durchdringungsfrage
  3,9 s (erster Anlauf über alle Dreiecke: 14,0 s). 16 von 56 mehrteiligen
  Körpern stecken ineinander. Rohdaten: `korpus_import.jsonl`.
- `sonde_karte.py` (offscreen, außerhalb der Suite): B3-Tabelle identisch,
  erste Stufe in Körperfarbe; B1-Knopf legt genau einen Reparaturschritt an.
- Die zwei neuen Fenstertests in `tests/test_analysis_ui.py` laufen nach
  Projektregel erst beim Release.
