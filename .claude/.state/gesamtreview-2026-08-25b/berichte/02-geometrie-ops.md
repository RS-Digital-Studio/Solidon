# Gebietsbericht: Geometrie-Ops (`app/core/geom/`, `lid_flow.py`)

Alle Befunde am laufenden Code nachgemessen; Skripte unter `review-geom\`.

## Hoch

### 1 [hoch] Ein durchgehender Stopfen ab der Mündung füllt nur die halbe Bohrung — VERIFIZIERT
`geom/prepare.py:376` — `plug()` baut bei `depth==0` mit `height=_through_length(...)`, zentriert auf `position`; der Zwilling `drill()` nimmt `*2.0`, damit der Zylinder in beide Richtungen reicht. Wer die Mündung anklickt (Vorgabe) und Tiefe 0 lässt, bekommt eine halb offene Bohrung, kein Befund. Gemessen (Klotz 20³, Ø6 durch = 7436,127): Stopfen ab Oberseite depth=0 → 7718,627 (exakt die Hälfte gefüllt); ab Mitte → 8000,0 (richtig). Beide Docstrings behaupten das Gegenteil. **Fix:** `height = _through_length(...)*2.0 if through else depth` (wird gegen `_shell` verschnitten).

### 2 [hoch] Bohren und Stopfen entscheiden die Richtung am Hüllquader — Zwilling des Senkungs-Fixes vom 25.08. — VERIFIZIERT
`prepare.py:153`, `:384`, Ursache `:425` — `countersink()` fragt seit 25.08. den Körper (`open_sides`); `drill()`/`plug()` nutzen weiter `into_the_body()` (entscheidet an der Hälfte des Hüllquaders). An gestuften Teilen zeigt das in die Luft. Gemessen (L-Profil): Klick auf Plattenoberseite → `into_the_body=+1` (ins Leere), `open_sides=(1.0,)`; Sackbohrung Ø6×6 → **0,282 mm³ statt 169,65**, kein Befund (`without_effect` schlägt wegen 0,01 mm Überlappung nicht an); Senkung an gleicher Stelle 76,812 (richtig, weil sie den Körper fragt); Stopfen → +170 mm³ Zapfen nach oben. **Fix:** in `drill`/`plug` `open_sides` verwenden, `-sides[0]` bei genau einer offenen Seite, sonst `into_the_body` als Rückfall.

### 3 [hoch] Die Gewindenut frisst die Decke des Drehdeckels — VERIFIZIERT
`geom/lid.py:696-716` — `_screw_cap` baut Höhe `skirt+thickness`, schneidet Nut mit `thread_body(..., skirt, internal=True)`; `thread_body` reicht real bis `height + pitch·0.8` (`shapes.py:260`). Sobald `pitch·0.8 >= thickness`, ist die Deckelstärke aufgezehrt. Gemessen (Deckel thickness=2,4): pitch 3,0 (Vorgabe) → Restwand 0,007 mm; pitch 4,0 → Loch 21,99 mm²; pitch 5,0 → 64,52 mm². Alle im erlaubten Bereich 1–10. Nebenwirkung: Gewindehals immer um `pitch·0.8` höher als eingestellt. **Fix:** Aufrufe auf ihre Zusage kürzen (`skirt - pitch*RIDGE_END`), oder `thread_body` bekommt die Gesamthöhe als Vertrag.

### 4 [hoch] Das Würfelgitter setzt Stäbe außerhalb des Teils ab — VERIFIZIERT
`geom/lattice.py:197-198` — `_cubic` verteilt Stabmitten mit `arange(low, high+cell, cell)`, bis zu einer Zellweite über den Hohlraum hinaus; `lattice_fill` beschneidet nur gegen den Körper, Außenliegendes überlebt und wird angefügt. Gemessen (Hohlwürfel 40, Wand 2, cell 8): Gitter −18,5…+22,5; Ergebnis Bounds bis +22,5 statt ±20, **35 Komponenten, 33 frei schwebend**. Gyroid/Wabe halten den Quader ein — nur `cubic` betroffen. **Fix:** Obergrenze auf den Quader begrenzen und Gitter vor der Differenz gegen den Hüllquader verschneiden.

## Mittel

### 5 [mittel] Zwei Stellen rechnen boolesch, ohne zu fragen, ob sie etwas bewirkt haben — VERIFIZIERT
`texture_ops.py:630` (`apply_texture`), `ops.py:450-462` (`_boolean_op` → union/subtract/intersect). `operationen.md`: „Wer Boolesches rechnet, fragt danach — ohne Ausnahme." Gemessen: `subtract_objects` mit entferntem Werkzeug → 8000,0, keine Befunde; `apply_texture` erhaben bei x=200 → 62 Komponenten (61 lose Rauten), keine Befunde — genau der Schaden, vor dem der `label_text`-Kommentar warnt. **Fix:** `without_effect(...)` in beiden anhängen; in `boolean.py:461-466` fehlt der `intersection`-Satz (greift heute der `union`-Zweig).

### 6 [mittel] „Schnittmenge" fährt bei getrennten Körpern die volle Rückfallkette und meldet den falschen Grund — VERIFIZIERT
`ops.py:455` — `_boolean_op` ruft `boolean()` ohne `allow_empty`. Gemessen: `intersect_objects` auf zwei getrennte Quader → `('direct','welded','jittered','voxel')`, 2,62 s für 12-Dreieck-Körper, dann „das Werkzeug deckt ihn vollständig ab" (falsch; sie berühren sich nicht). `test_piece` macht es mit `allow_empty=True` vor. **Fix:** für `intersection` `allow_empty=True` + eigene Meldung „keine gemeinsame Fläche".

### 7 [mittel] „Kugel anlegen": Segmentregler wirkt exponentiell, keine Obergrenze — VERIFIZIERT
`primitive_ops.py:203-205` — `icosphere(subdivisions=max(1, segments//12))`, jede Unterteilung ×4. Gemessen: segments 96 → 1,3 Mio, 128 → 21 Mio Dreiecke; 8–23 ändert nichts, dann Sprung. `mesh_ops` hat `MAX_REMESH_TRIANGLES = 8 Mio` mit Meldung; die Kugel nicht. **Fix:** `subdivisions` aus `log4(...)` ableiten und deckeln, oder Schema-Maximum auf ≤90.

### 8 [mittel] Druckbarkeitsprüfung der Texturen wertet das Muster nicht aus — VERIFIZIERT
`texture_ops.py:295` — `check_printable(pattern, ...)` liest `pattern` nie, rechnet immer `pitch*LAND_SHARE`. Gemessen (Düse 0,4, min 0,8): rib 0,400 (richtig), noise 0,009, voronoi 0,009 — vier von acht Mustern kommen durch und drucken glatt. **Fix:** schmalste Struktur je Muster unterscheiden, oder die erzeugten Polygone messen.

### 9 [mittel] Aushöhlen reicht `cancelled` an keinen seiner bis zu sechs Booleschen weiter — VERIFIZIERT
`hollow.py:125,145,363` — `hollow()` fragt `cancelled` in `_step`, die drei `boolean(...)` bekommen es nicht (obwohl `boolean()` den Parameter hat, §15.6). Zwischen zwei `_step` liegen bis zu vier Rückfallstufen inkl. Voxel — Minuten, in denen Abbrechen nichts tut. `lattice_fill`/`_boolean_op` machen es richtig. Kleiner: `add_pins` (`pins.py:449-450`) kennt `cancelled` gar nicht. **Fix:** durchreichen.

### 10 [mittel] Mindestwand um einen Passstift ist fest, obwohl das Profil sie kennt — VERIFIZIERT
`pins.py:85` (`PIN_WALL=1.6`), `:81` (`SNAP_MIN_REACH=8.0`) — beide aus 0,4-mm-Düse abgeleitet; `Profile.minimum_wall_thickness` liefert es aus `extrusion_width`, `lattice.check_printable` nutzt es schon. `plan_pins(..., wall=PIN_WALL)` hat einen Parameter, den kein Aufrufer setzt; `_cut_and_pin` hat `ctx.profile` und reicht ihn nicht. **Fix:** `wall` aus dem Profil füllen, Konstanten als Rückfall.

## Gering
- **11** Kommentar sagt Gegenteil des Codes (`lid.py:161-165`, „beidseitig zweimal" über einfachem Abzug; Code richtig); lädt zum Wiedereinbau des Fehlers ein. Umschreiben.
- **12** `_pipe` rechnet immer `quality="fine"` (`lid.py:502`), obwohl `screw_lid` `ctx.quality` hat. Durchreichen.
- **13** Vier rohe `ValueError`/`TypeError` ohne Handlungsvorschlag (`hollow.py:99`, `transform.py:67`, `boolean.py:104`, `texture.py:113`, `mesh.py:533`); heute nur über direkten Aufruf erreichbar → auf `InternalError`/`require_positive` heben.
- **14** `deterministic=False` nur bei einem Teil der Ops mit gleicher Rückfallkette (`prepare_ops.py:213` vs `:397,475,785`, `label_ops.py:216`, `lid.py:378/590`, `lattice.py:322`); Registerauskunft für acht Ops falsch. Vereinheitlichen + Gegenrichtung im Konsistenztest.
- **15** Zwei Parameter ohne `depends_on` (`label_ops.py:160-173` `slot` nur bei `raised`; `prepare_ops.py:435-453` `vents`/`vent_diameter` bei `open_top` still übergangen). Ergänzen.
- **16** Öffnung auf z=0 nicht angebbar (`lid.py:252`, `stated or ...` behandelt 0 wie „nichts"); betrifft `create_lid`/`screw_lid`. Vorgabe auf None/NaN.

## Geprüft und in Ordnung
Senkung/Sackbohrung/Sackstopfen an allen sechs Flächen identisch (Fix vom 25.08. hält); Teilen/Verstiften über x/y/z + schräge Normale, beide Hälften wasserdicht, Stifte/Bohrungen gesetzt; Deckelpassung Durchmessermaß stimmt; Aushöhlen (offene Dose, gedrehter Würfel, U-Profil) einteilig auf Maß; Rückfallkette alle fünf Stufen, `attempted`/`solver`/`deepest` korrekt; `orient.candidates` (NumPy-2-Falle greift nicht); `enclosure._install` idempotent, rtree draußen; Regel 11 (`create_from_scad` über `openscad.render` mit Quelltextprüfung); Regeln 1/10/12; `lid_flow.apply_lid` (Passung als `DocumentChange` in einer Transaktion, `unique_name`, Kragen 0 → keine Passung).

**Kann das so rein: nein** — vier Befunde liefern falsche Geometrie, drei stumm (halber Stopfen, Bohrung in die Luft, Deckel mit Loch, Gitter außen klebend). Zwillinge 2, 5, 9 mit ihren behobenen Geschwistern zusammen fixen.
