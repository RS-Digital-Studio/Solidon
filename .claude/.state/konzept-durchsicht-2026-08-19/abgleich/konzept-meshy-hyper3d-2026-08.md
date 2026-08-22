# Abgleich — `konzept-meshy-hyper3d-2026-08.md` gegen den Stand vom 19.08.2026

Geprüft wurden **nur die intern prüfbaren Behauptungen**. Die zwanzig externen
Aussagen über Meshy und Hyper3D Rodin (Preise, Guthaben, Nutzerzahlen,
Endpunktumfang, Akademie) sind hier nicht bewertet — sie sind aus dem
Repository heraus nicht nachschlagbar.

**Zählung:** 45 Einzelbehauptungen — **17 stimmen**, **23 sind überholt**,
**4 sind falsch**, **1 ist unprüfbar**.

Das Dokument ist auf den 12.08.2026 datiert, trägt Nachträge vom 13. und
14.08. Zwischen dem 12.08. und heute liegen die Phase P16 (organische
Modellierung, Sculpting, Posing), die Erweiterung von zwei auf sechs Sprachen
und die Durchsicht vom 14.08. — und genau dort ist es gealtert.

---

## 1. Zählungen im Kopf des Dokuments und in Teil 3.7 / Teil 5

### 1.1 „alle 77 Operationen" — **überholt**

*Orte:* Methode (Kopf, Z. 37), 3.7 (Z. 352), Teil 5 Tabelle (Z. 575),
Schlussabsatz (Z. 1064).

**Beleg:**
```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations;
from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
→ 85
```
`website/funktionen.html:408` schreibt „85 Operationen", `README.md:165`
„fünfundachtzig Schemata". Die 77 waren am 12.08. richtig
(`ROADMAP.md:4427`: „die beworbenen **77 Operationen** sind richtig").

**Was stattdessen dastehen muss:** „alle 85 Operationen".

### 1.2 „fünfzehn Kategorien" — **stimmt**

15 Kategorien im Register (boolean, colour, holes, import, label, mesh, parts,
prepare, primitive, repair, scene, shaping, sketch, surface, transform).

### 1.3 „16 Bausteine" — **überholt**

*Orte:* Methode (Z. 39), Schlussabsatz (Z. 1064).

**Beleg:** `PARTS.all()` → 17 (`cable_gland, dowel, fit_ladder, heatset_m4,
keyhole, latch, living_hinge, magnet_pocket, nut_trap, overhang_fan,
printed_thread, rib, screw_hole, snap_connector, snap_fit, wall_ladder,
wall_mount`). `snap_connector` kam am 14.08. mit Commit `33031da` dazu;
`git grep -c 'register_part('` auf `3cb2871` (12.08.) ergibt 16.
`website/funktionen.html:244` sagt „Siebzehn geprüfte Bausteine".

**Was stattdessen dastehen muss:** „alle 17 Bausteine".

### 1.4 „18 Bausteine-Ops" (3.7 Tabelle, Z. 362; Teil 7, Z. 748) — **überholt**

**Beleg:** Kategorie `parts` zählt heute 19 Operationen (`create_lid`,
`screw_lid` und 17 × `insert_*`).

**Was stattdessen dastehen muss:** „19 Bausteine-Ops".

### 1.5 6 Materialprofile / 16 Druckerprofile / 40 Normteilmaße in acht
Tabellen / 11 Konstruktionsregeln Version 2 — **alle vier stimmen**

*Ort:* 5.2 Aufzählung (Z. 649–660), B4 (Z. 849–851).

**Beleg:**
```
material_profiles() → 6  (abs, asa, petg, petg-cf, pla, tpu-95a)
printer_profiles()  → 16
standards.load()    → screws 7, nuts 7, washers 4, inserts 6, magnets 5,
                      bearings 4, profiles 3, tubes 4 = 40 in acht Tabellen
rules.load()        → 11 Regeln, rules.version() → 2
```
Alle vier Zahlen unverändert.

---

## 2. Handbuch (Teil 5 Tabelle, 4.2, 5.2)

### 2.1 „20 geschriebene Seiten + 15 aus dem Register erzeugte" — **überholt**

**Beleg:** `manual.pages()` → 40 Seiten, davon `generated=False` **21** und
`generated=True` **19** (`rules`, `profiles`, `remote-tools`, `messages` plus
15 Kategorieseiten). Neu seit dem 12.08.: die geschriebene Seite `sculpting`
(„Formen"), eingefügt mit Commit `7ee4250` am 14.08.

**Was stattdessen dastehen muss:** „21 geschriebene Seiten + 19 erzeugte
(15 Kategorie-Referenzen und vier aus den Wissenstabellen)".

### 2.2 „~110.000 Zeichen, ~19.600 Wörter" — **überholt**

**Beleg:** Summe über `manual.pages()`: **147.692 Zeichen, 24.889 Wörter**.

### 2.3 „32 Verweise, 25 Abbildungen im Katalog, 6 Bildschirmfotos je Sprache"
— **stimmt**

**Beleg:** `FIGURE_PATTERN` über alle Seiten → 32 Treffer; `figures.FIGURES`
→ 25 Einträge (13 gezeichnet, 6 gerendert, 6 aufgenommen);
`app/images/manual/<lang>/` je 6 PNG.

### 2.4 „Sprachen: Deutsch und Englisch, beide vollständig" — **überholt**

**Beleg:** `app/i18n/locales/` führt `en, es, fr, it, pt` — mit Deutsch als
Quelle **sechs** Sprachen, eingecheckt mit Commit `6553566` („Sechs Sprachen,
und keine davon fällt mitten im Satz ins Deutsche zurück", 13.08.2026).
`app/images/manual/` hat sechs Sprachordner mit je sechs Bildschirmfotos.

**Was stattdessen dastehen muss:** „sechs Sprachen, alle vollständig — Deutsch
als Quelle, dazu en, es, fr, it, pt".

### 2.5 „Werkzeugliste der Fernsteuerung: nein" / „eine Handbuchseite,
980 Zeichen, ohne Werkzeugliste" — **überholt, und Widerspruch im Dokument**

*Orte:* 3.6 Tabelle (Z. 341), Teil 5 Tabelle (Z. 582), 3.6 Schlusssatz
(Z. 347), B6 (Z. 866). Teil 10 (Z. 1087) meldet dieselbe Sache als erledigt.

**Beleg:** Die Seite `remote` hat heute **1.332 Zeichen**; daneben steht die
erzeugte Seite `remote-tools` („Die Werkzeuge der Fernsteuerung",
**15.426 Zeichen**), die `remote_tools()` auflistet — **94 Werkzeuge**, davon
10 keine Operationen (`undo_transaction, add_parameter, set_parameter,
add_fit, read_report, find_part, read_digest, read_standard, read_analysis,
set_print_target`). Die Seite existierte bereits am 12.08.
(`git show 3cb2871:app/core/manual.py` führt `"remote-tools"`), der Haupttext
war also schon beim Schreiben überholt.

**Was stattdessen dastehen muss:** in 3.6 und Teil 5 „vollständige
Werkzeugliste, erzeugt aus dem Register — 94 Werkzeuge auf einer eigenen
Seite"; der Satz „Sie haben jedes Werkzeug benannt, wir haben keines" fällt
ersatzlos.

### 2.6 „Changelog: nein" — **stimmt**

Weder `website/` noch `manual.py` führen eine Änderungsliste.

### 2.7 „Glossar (3.330 Zeichen)" und „Fehlerbehebung: eine Seite (2.760
Zeichen)" — **stimmen auf das Zeichen**

`glossary` → 3.330, `trouble` → 2.760.

### 2.8 „…ohne Wortlaut der Meldungen" / „Wer im Programm eine Meldung liest
und im Handbuch danach sucht, findet den Wortlaut heute nicht" (5.2, Z. 612)
— **überholt, Widerspruch im Dokument**

**Beleg:** Die erzeugte Seite `messages` („Meldungen im Wortlaut",
2.325 Zeichen, `manual.messages_text()`) tut genau das. Teil 10 (Z. 1086)
meldet es als erledigt; 5.2 und die Teil-5-Tabelle sagen weiter „nein".

### 2.9 „Geschriebene Seiten … zwischen 980 und 6.177 Zeichen, im Schnitt
~2.100" (5.2, Z. 609) — **überholt**

**Beleg:** Kürzeste geschriebene Seite heute `what` mit **1.023** Zeichen
(die 980 waren `remote`, jetzt 1.332), längste weiter `sketch` mit 6.177,
Schnitt ~2.148.

### 2.10 „kein ‚Kurz gesagt'" (5.2, Z. 610) — **überholt**

**Beleg:** `Page.summary` (`app/core/manual.py:49`) ist ein eigenes Feld;
**alle 21** geschriebenen Seiten füllen es.

---

## 3. Oberfläche und Thema (4.2, 4.3, B12, B16)

### 3.1 `theme.py:30` setzt `_SELECTION = "#f0a54a"` — **stimmt**

Zeile 30, unverändert.

### 3.2 „Kontrast **7,27** gegen die Fensterfarbe" (4.3 Z. 454, B16 Z. 881)
— **falsch**

**Beleg:** `#f0a54a` gegen `window` `#343a45` ergibt nach WCAG **5,54**. Der
Kommentar in `theme.py:38` sagt selbst „Gegen das dunkle Fenster bringt er
5,4". Beide Farben stehen unverändert seit vor dem 12.08.
(`git show 3cb2871:app/ui/theme.py`), die Zahl war also schon damals falsch.
7,93 ist der Kontrast von Bernstein gegen die *Schrift darauf* (`#1c2026`) —
vermutlich die verwechselte Zahl.

**Was stattdessen dastehen muss:** „Kontrast 5,54 gegen die Fensterfarbe".

### 3.3 „Panel gegen Fenster 1,10 · Zebrazeile 1,16 · Viewport-Verlauf 1,21 ·
Trennlinie 1,43" (4.3 Tabelle Z. 492–497, B16 Z. 879) — **überholt**

**Beleg:** Aus `THEMES["dark"]` nachgerechnet:

| Flächenpaar | Dokument | heute |
|---|---|---|
| Panel (`base`) gegen Fenster | 1,10 | **1,45** |
| Zebrazeile gegen Panel | 1,16 | **1,28** |
| Viewport oben gegen unten | 1,21 | **1,56** |
| Trennlinie gegen Fenster | 1,43 | **2,30** |

Der Kommentar über `THEMES` (`app/ui/theme.py:49–55`) führt die alten Zahlen
ausdrücklich als „Der Stand davor". Teil 10 (Z. 1097) meldet „1,10 → 1,45,
Trennlinie 1,43 → 2,30" — 4.3 und B16 widersprechen der eigenen
Schlusstabelle.

Die Aussage „sieben Rollen … zwischen 1,3 % und 5,0 % Helligkeit" gilt für die
Flächen dem Sinn nach weiter (1,35 % bis 5,52 %); die Trennlinie ist aber
keine davon mehr — sie steht bei 16,13 %.

### 3.4 „`QTabBar::tab:selected` … **kein Akzent**" (4.3, Z. 480) — **überholt**

**Beleg:** `app/ui/style.py:410` — `border-top: 3px solid {accent_line}` auf
`QTabBar::tab:selected`, mit Kommentar auf Regel 18. Punkt 1 der Liste in 4.4
ist damit umgesetzt.

### 3.5 „`tests/test_accessibility.py` prüft die Kontraste mit" (B16, Z. 891)
— **falsch**

**Beleg:** Die Datei existiert nicht und hat nie existiert:
`git log --all -- tests/test_accessibility.py` liefert nichts. Die Kontraste
prüft **`tests/test_theme_and_palette.py`** (u. a.
`test_the_surfaces_stand_apart:157`, `test_a_border_is_actually_visible:143`,
`test_the_accent_line_carries_on_its_own_window:180`).

### 3.6 „rund 90 Pixel Leerraum über dem Beschreibungssatz" (4.2.3 Z. 428,
B12 Z. 975) — **überholt, Widerspruch im Dokument**

Teil 10 (Z. 1093) meldet „189 → 26 px; es war eine fehlende Größenrichtlinie".
Der Haupttext nennt weiter 90 px, die weder der alte noch der neue Wert sind.

### 3.7 „acht Beispielprojekte als Karten" auf dem Startbildschirm (4.2, Z. 405)
— **überholt**

**Beleg:** `app.core.examples.EXAMPLES` → **9** (`weg1-…`, `weg2-…`,
`weg3-…`, **`weg4-figur-formen`**, `gehaeuse-mit-bausteinen`,
`schild-zweifarbig`, `drucker-kalibrieren`, `aushoehlen-und-teilen`,
`dose-mit-deckel`). Die Beschriftung nennt seit P16 vier Wege, nicht drei
(`ROADMAP.md:5358`).

---

## 4. Teilen (3.2, B13, Teil 7, Teil 10)

### 4.1 „`split_plane` und `split_pinned` schneiden an einer Ebene … die
geneigte Ebene bleibt offen, **gebaut ist nichts**" — **überholt**

*Orte:* 3.2 (Z. 233), Teil 3 Einleitung, Teil 7 (Z. 750), B13 geprüfte Fassung
(Z. 940), B13 Nachtrag (Z. 1004), Teil 10 (Z. 1094).

**Beleg:** Seit dem 14.08.2026 gibt es die Operation **`split_line` — „An
gezeichneter Linie trennen"** (`app/core/geom/prepare_ops.py:905`,
Commit `2844f8b` „Eine Trennebene, die an keiner Achse hängt — und Stifte, die
darauf senkrecht stehen"). Sie nimmt eine freie Normale
(`normal_x/normal_y/normal_z`), legt die Ebene aus zwei Punkten auf dem Teil
plus Blickrichtung und **verstiftet auf der schiefen Fläche**: `plan_pins` und
`add_pins` nehmen jetzt eine `SectionPlane` statt eines Achsenbuchstabens.
`ROADMAP.md:5509` führt sie unter „Gebaut", mit `SplitBar` in der
Werkzeugzeile und elf Tests.

Genau das ist der Weg, den B13 als „offen, weil noch nicht gebaut"
beschreibt: *„Der offene Weg ist weiterhin die geneigte Ebene: `SectionPlane`
trägt schon eine freie Normale."*

**Was weiter stimmt:** die *automatische* Suche. `autosplit.py:249` ruft
`_axis_to_cut`, das aus `AXIS_NORMALS` (`geom/section.py:29`, drei Einträge)
wählt. Auch der formfolgende, nicht-planare Schnitt fehlt weiter — und der
Schnitt entlang V-HACD-Hüllen bleibt abgelehnt (Modulkopf `autosplit.py`,
Wortlaut unverändert).

**Was stattdessen dastehen muss:** „Die geneigte Ebene ist seit dem 14.08.2026
gebaut — `split_line` schneidet entlang einer im Bild gezeichneten Linie und
verstiftet senkrecht zur Schnittfläche. Offen bleiben zwei Dinge: die
automatische Suche kennt weiter nur drei Achsen, und ein formfolgender Schnitt
existiert nicht."

Diese Zeile ist der Fund mit dem größten Gewicht: Wer B13 heute liest, hält
eine gebaute Funktion für ungebaut und kann sie ein zweites Mal beauftragen.

### 4.2 „`AXIS_NORMALS`, die Suche kennt drei Achsen" — **stimmt**

`app/core/geom/section.py:29` → x, y, z. `_axis_to_cut`
(`autosplit.py:276`) unverändert.

---

## 5. Slicer-Übergabe (3.5)

### 5.1 „`handover.py` kennt drei Profilfamilien `prusa`, `orca`, `cura`
(`slicer_keys.py:25`)" — **stimmt**

`app/core/export/slicer_keys.py:25` → `SlicerFlavour = Literal["prusa",
"orca", "cura"]`. Zeilennummer und Inhalt unverändert.
`slicer_profiles.py` liest weiter den Profilbestand der installierten
Anwendung.

---

## 6. Die gemessene Kette (3.4) und die Abnahme

### 6.1 „read_mesh(glb) → 1.304 Dreiecke … export_bytes 3mf → 13.098 Bytes"
— **unprüfbar**

Die Messung lief gegen eine eigens gebaute GLB-Szene, die nicht im Repository
liegt. `tests/data/meshes/` enthält kein GLB (`bracket_inch.stl`,
`broken_open.stl`, …, `colored.3mf`). Die Aussage lässt sich weder bestätigen
noch widerlegen; die zugrunde liegende Fähigkeit ist belegt
(`tests/test_export.py:220 test_glb_carries_the_slot_colours`,
`tests/test_slots.py:240 test_3mf_written_here_can_be_read_here_again`).

### 6.2 Abnahmepunkt 2: „ein Test fährt die Kette aus 3.4 gegen eine Datei aus
`tests/data/` — GLB hinein, 3MF mit Materialgruppen heraus" — **falsch**
(als erfüllt gelesen)

**Beleg:** In `tests/data/meshes/` liegt keine GLB-Datei; kein Test in
`tests/` liest eine GLB aus dem Korpus. Die Farbkette ist über `colored.3mf`
getestet (`tests/test_corpus.py:66`), die GLB-Richtung nur schreibend
(`test_export.py:206–244`). B3 wurde stattdessen als Website-Abschnitt
umgesetzt (`website/ki-modelle.html`, sechs Sprachen) — der Prüfbericht-Befund
„trägt Farben, aber keine Filamentzuordnung" aus B3 Punkt 1 existiert
ebenfalls nicht (`grep` auf „Filamentzuordnung" in `app/` findet nichts).

**Was stattdessen dastehen muss:** Der Abnahmepunkt ist offen — es fehlen die
GLB im Korpus, der Test und der Prüfbericht-Befund; umgesetzt ist nur die
Website-Seite.

---

## 7. ComfyUI-Weg (B10)

### 7.1 „`Hy3DMeshGenerator` nimmt `model`, `image`, `steps`,
`guidance_scale`, `seed`, `attention_mode` — und sonst nichts" — **stimmt**

`app/core/backends/data/image_to_mesh.json:25–33` und
`text_to_mesh.json:68–76`, exakt diese sechs Eingänge. `fit_to_size` und
`check_build_volume` existieren wie beschrieben.

---

## 8. Preis, Fassung, Demo (Einordnung vorweg, Teil 6, B7)

### 8.1 „Solidon 1.0 ist noch nicht erschienen (Website: ‚Version 1.0
erscheint 2026')" — **überholt**

**Beleg:** Die Fassung ist `0.1.0` (`pyproject.toml:7`,
`website/version.json`), 1.0 ist weiter nicht erschienen — aber der zitierte
Satz steht nicht mehr auf der Website. `website/index.html:371` sagt heute:
„Bis zum 30. Oktober kostet Solidon3D nichts", `version.json` nennt „Erste
öffentliche Demo — vollständig, ohne Schlüssel, bis zum 30.10.2026".

### 8.2 „14 Tage vollständig testen" (Teil 6 Tabelle Z. 721, Teil 8 Punkt 3
Z. 778, Teil 6 Schlussabsatz Z. 738) — **überholt**

**Beleg:** `app/core/activation/store.py:50` —
`DEMO_UNTIL: Final[date | None] = date(2026, 10, 30)`. Der Modulkommentar:
„Ein Stichtag statt einer Frist ab dem ersten Start: die Demo endet für alle
am selben Tag." `TRIAL_DAYS = 14` (Z. 36) gilt nur noch für die Verkaufsfassung
(`DEMO_UNTIL is None`, Z. 152).

Damit fällt auch der Absatz „Ein Punkt gegen uns … Unsere vierzehn Tage sind
eine Testphase": Der Vergleich lautet heute „kostenlos und unbeschnitten bis
zum 30.10.2026" gegen „dauerhaft kostenlose Stufe mit Guthabendeckel".

### 8.3 „49 € einmalig (später 79 €), alle 1.x-Updates inklusive" — **stimmt**

`website/index.html:382`.

---

## 9. Teil 10 — die Schlusstabelle

Von sechzehn Zeilen sind vier heute nicht mehr richtig:

| Zeile | Urteil | Beleg |
|---|---|---|
| **B1** „Website, beide Sprachen" | **überholt** | `website/ki-modelle.html` und `website/{en,es,fr,it,pt}/ai-models.html` — **sechs** Sprachen; die Tabelle „Was eine Druckbarkeitsprüfung prüft" steht dort mit Datum 12.08.2026 |
| **B2** „teilweise — das Bild fehlt" | **stimmt** | `figures.FIGURES` führt sechs Aufnahmen (`start-screen, main-window, op-dialog, report, catalog, sketch-mode`), keine Analysekarte |
| **B5** „20 Kurzfassungen" | **überholt** | 21 geschriebene Seiten, alle mit `summary` |
| **B6** „erzeugt; zehn Werkzeuge waren gar keine Operationen" | **stimmt** | `remote_tools()` → 94, davon 10 außerhalb des Registers |
| **B7** „beide Sprachen" | **überholt** | sechs Sprachen |
| **B8** „gerendert, nach Objekt-Hash gecacht" | **stimmt** | `app/ui/panels.py:331`, `:430` |
| **B9** „wasserdicht · Volumen · Teile" | **stimmt** | `app/ui/panels.py:1359–1373` |
| **B12** „189 → 26 px" | **stimmt** (widerspricht 4.2.3) | s. o. |
| **B13** „gebaut ist nichts" | **überholt** | `split_line`, s. Abschnitt 4.1 |
| **B14** „fünf Operationen mit echter Grenze" | **überholt** | `caveat` gesetzt bei **12** Operationen: `blend_union, create_from_scad, decimate_mesh, displace_image, hollow_object, lattice_fill, pose_armature, remesh_uniform, sculpt_strokes, split_line, split_pinned, subdivide_surface` |
| **B16** „1,10 → 1,45, Trennlinie 1,43 → 2,30, Reiterkante" | **stimmt** | nachgerechnet, s. 3.3/3.4 |

### 9.1 „Was offen bleibt" (Z. 1104–1108)

| Punkt | Urteil | Beleg |
|---|---|---|
| Bildschirmfoto einer Analysekarte fehlt im Abbildungskatalog | **stimmt** | s. o.; ebenso fehlt eines der Formen-Sitzung (Weg 4) |
| „Die Website läuft mit 1456 px in einem Fenster von 1265 px über" | **überholt** | Ursache gefunden und behoben: `auto-fit`-Raster gab unter 544 px nicht mehr nach; `website/style.css:692` → `repeat(auto-fit, minmax(min(34rem, 100%), 1fr))`, Regel geprüft in `tests/test_website.py:339–375` (Commit `33031da`) |
| „In der Statuszeile überlappen sich ‚Keine Auswahl' und der Demo-Hinweis" | **überholt** | Behoben: die Demo-Zeile ist keine `showMessage` mehr, sondern ein `addPermanentWidget` (`app/ui/main_window.py:1208–1237`, Begründung Z. 2171–2175) |

---

## 10. Aussagen, die P16 überholt hat

### 10.1 Teil 2 Tabelle: „Rigging, Animation | **nein, und nie**" — **überholt**

**Beleg:** Die Operation **`pose_armature`** („Eine Pose, keine Animation")
liegt seit P16.8 im Register (`ROADMAP.md:5145`); dazu `sculpt_strokes`,
`subdivide_surface`, `remesh_uniform`, `displace_image`, `blend_union`.
Die Oberfläche hat `app/ui/sculpt_bar.py` und `app/ui/pose_bar.py`.

Der Satz „nein, und nie" gilt für Animation weiter, für das Skelett nicht mehr.

### 10.2 Teil 2 Tabelle: „Steuerung der Form | Prompt" — **überholt im Rahmen**

Für den *Generatorweg* stimmt es (B10 bestätigt). Daneben steht seit P16 ein
vierter Weg — „Weg 4 — Organisch formen" (Bauplan §2.2, Z. 120; nachgetragen
am 18.08.2026), mit sechs Pinseln und mitlaufender Wandstärkenprüfung
(`website/index.html:288–297`). Der Abschnitt „Erzeugen: der Bereich, den wir
verlieren" lässt heute offen, dass Formen ohne Generator möglich ist.

### 10.3 Teil 7: „Konstruieren mit Maß — konkurrenzlos … 18
Verbindungsbausteine" — **überholt in der Zahl** (19 Ops, 17 Bausteine).

---

## 11. Was unverändert stimmt

- **3.1, Tabelle „Was wir prüfen"** — alle vierzehn Zeilen belegt:
  `total_overhang`, `worst_overhang`, `island_layers`, `minimum_width`,
  `narrowest`, `_bridge_width` in `slice/analysis.py`; `check_build_volume`,
  `check_collisions` in `geom/prepare.py`; `check_adhesion_clearance`,
  `check_filament_changes` in `export/writer.py`; `scene/fits.py`,
  `geom/lattice.py::check_printable`, `geom/texture_ops.py`,
  `slice/orientation.py`, `slice/advise.py` existieren.
- **3.7** — alle genannten Operationsnamen existieren noch (`chamfer_edges`,
  `fillet_edges`, `draft_faces`, `shell_exact`, `thread_exact`, `push_face`,
  `create_brep_box`, `create_brep_cylinder`, `load_step`, `sketch_*`,
  `insert_fit_ladder`, `insert_wall_ladder`, `insert_overhang_fan`,
  `test_piece`, `hollow_object`, `compensate_first_layer`, `set_material`,
  `split_pinned`, `orient_for_print`).
- **4.2.5** — `Quality = Literal["draft", "fine"]` (`app/core/types.py:56`).
- **B6-Quelle** — `registry/surfaces.py:207 tool_schemas`.
- **Verweise auf andere Konzepte** — `konzept-wettbewerb-2026-08.md` trägt im
  Titel den 11.08.2026; `konzept-bedienung.md` und
  `konzept-organische-modellierung-2026-08.md` liegen vor, §17 dort
  (Z. 981) hält die Entscheidung fest: „Der Kundenkreis ist erweitert:
  **Figuren gehören dazu.**" `ROADMAP.md:4918` bestätigt sie mit Datum.
- **B13-Modulkopf-Zitat** aus `geom/autosplit.py` wörtlich unverändert.

---

## 12. Widersprüche im Dokument selbst

Fünf Stellen, an denen das Dokument sich schon beim Schreiben widersprach —
die häufigste Alterungsart in diesem Projekt:

1. **Kopf „Fünfte Fassung" (Z. 7) gegen Fußzeile „vierte Fassung" (Z. 1063).**
2. **4.3 / B16 nennen die alten Kontraste**, die Teil 10 in derselben Datei
   bereits als geändert meldet.
3. **4.2.3 / B12 nennen 90 px**, Teil 10 nennt 189 → 26 px — und keine der
   drei Zahlen passt zu einer anderen.
4. **3.6 / Teil 5 sagen „keine Werkzeugliste"**, Teil 10 meldet sie als
   erzeugt; sie existierte bereits am 12.08.
5. **5.2 sagt „den Wortlaut findet man nicht"**, Teil 10 meldet die erzeugte
   Meldungstabelle.

Dazu die bereits im Dokument beschriebene Doppelung: **B13 steht zweimal**,
mit unterschiedlichem Status. Beide Fassungen sind heute überholt.

---

## 13. Empfehlung für die Überarbeitung

Wer das Dokument fortschreiben will, muss vier Dinge tun, sonst führt es zu
falschen Entscheidungen:

1. **B13 auf „gebaut" setzen** und die verbleibende Lücke neu benennen
   (automatische Suche, formfolgender Schnitt).
2. **Alle Zählungen einmal nachziehen**: 85 Ops, 17 Bausteine, 19
   Bausteine-Ops, 21+19 Handbuchseiten, sechs Sprachen, neun Beispiele.
3. **4.3, B16, 4.2.3 und B12 an Teil 10 angleichen** oder als historischen
   Befund markieren — die alten Kontrastzahlen stehen sonst als geltender
   Stand da.
4. **Teil 6 auf das neue Demo-Modell umschreiben** (bis 30.10.2026 kostenlos
   statt 14 Tage) und den Abnahmepunkt 2 als offen führen.
