# Paket p7step — RM-188 P7.4 STEP-Mehrkörperimport (Bericht, fortlaufend)

Arbeitsbaum `F:\3D Druck.review-050\wt-p7step`, Stand 56f70000.

## Stand

- 23.09.2026: Auftrag gelesen, Unterlagen (Konzept P7.4, Durchsicht §6.4, Bauplan §17.1/§20/§29/§30,
  Karten brep/ingest, Regeln dateiformat/kern/operationen/wartezeit) gelesen. Bestandsaufnahme läuft.

## Befunde (Bestandsaufnahme, 23.09.2026)

1. **OCP 8.0.1 trägt den XCAF-Leseweg vollständig**: `STEPCAFControl_Reader` mit `ReadStream`
   (BytesIO, keine Temporärdatei), `XCAFDoc_ShapeTool`/`ColorTool`, SHUO-Ketten über
   `GetAllComponentSHUO`/`GetSHUONextUsage`, `FileUnits`. Paketbau: `TKXCAF`, `TKDESTEP`,
   `TKLCAF`, `TKCAF` liegen in `cadquery_ocp_novtk.libs`; die Spec bekommt die Module als
   `hiddenimports`.
2. **`label.FindAttribute(TDataStd_Name.GetID_s(), TDataStd_Name())` stürzt nativ ab**
   (Zugriffsverletzung nach wenigen Aufrufen, reproduzierbar an den Körperlabels von
   `build_tray_v3.step`) — das Muster aus CadQuery. Namen werden über
   `TDF_AttributeIterator` gelesen, dessen Zeiger der Handle-Zähler hält. Dasselbe
   Ausgabeparameter-Problem bei `SetSHUO(labels, XCAFDoc_GraphNode())`: das Label bleibt leer;
   Instanzfarben entstehen im Erzeuger über `SetInstanceColor(located shape)`.
3. **Körpernamen eines Teils mit mehreren Körpern** (Fusion: Namen der
   `MANIFOLD_SOLID_BREP`) kommen nur mit `read.stepcaf.subshapes.name = 1`, und der Schlüssel
   existiert erst nach `STEPCAFControl_Controller.Init()` — vorher gibt `SetIVal` still
   `False` zurück.
4. **Farbraum**: OCCT hält Farben linear; `COLOUR_RGB 0.627` aus der Datei kam als `0.3515`
   an. Zurück über `Quantity_TOC_sRGB`, gerundet auf 8 Bit (`#rrggbb`) — die Genauigkeit der
   übrigen Anwendung und genug gegen den Float32-Speicher von `Quantity_Color`.
5. **Farbnamen aus der Datei taugen nicht als Filamentnamen**: `carpet-corner-clip.step` nennt
   ein cremefarbenes `#fff3ca` „ABS (Black)“ und ein oranges „ABS (Black) (1)“ (Fusion-
   Erscheinungsbilder, eingefärbt). Slots heißen deshalb „Slot n“ wie beim 3MF-Ersatz und bei
   *Filament zuweisen*; die Farbe trägt das Farbfeld.
6. **Bestehender Fehler behoben: `Solid.is_closed` meldete jede offene Schale als
   geschlossen** — `CheckOrientedShells` zählt freie Kanten nur mit `alsofree=True`. Gemessen
   an einer offenen Wanne aus fünf Flächen. Kugel-/Kegelpole zählen auch mit dem Schalter nicht
   als frei (Quader, Zylinder, Kugel, Kegel, Ring, fünf Gewindekörper, fünf Kundendateien:
   unverändert geschlossen). Die Wächter in `edit`, `profiles`, `prepare_ops`, `seal`,
   `parts` greifen damit erst jetzt.
7. **Bestehender Fehler behoben: der STEP-Export hängte eine Nummer an den Namen**
   („Lagerbock 1“ — `write.step.product.name` ist ein Präfix) und schrieb Umlaute als rohe
   UTF-8-Bytes, die ein normgerechter Leser als „GehÃ¤use“ liest. Der XCAF-Schreiber setzt
   den Namen wörtlich, `step.escaped` kodiert nach ISO 10303-21 (`\X2\…\X0\`).
8. **§17.1 Schritt 6 galt für STEP nicht**: Das erste Modell eines Projekts kam als STEP weder
   aufs Bett noch in die Mitte. `load_step` trägt jetzt dieselben zwei Haken wie `load`, als
   Lage an der Form (der Körper bleibt exakt); ältere Schritte behalten ihre Lage.
9. **Korpus**: `F:\3D Dateien` hat fünf STEP-Dateien, zwei davon mehrkörperig
   (`build_tray_v3.step` 5 Körper, `carpet-corner-clip.step` 2 Körper in zwei Farben), keine
   Baugruppe mit Instanzen. Der Downloads-Ordner dieses Rechners enthält keine STEP-Datei.

## Bauschritte

1. **Leser** `brep/step.py::read_assembly` (XCAF, `ReadStream`): flache Liste `StepBody` mit
   Kennung (Instanzpfad `1.3.2`, bei Teilen mit mehreren Körpern `1.3#2`), Name, Form in
   Weltlage, Farbe je Fläche (`#rrggbb`, sRGB), Teilkennung, Spiegelung, Weltlage (`gp_Trsf`).
   Starre Lagen bleiben `TopLoc_Location`, Spiegelung/Maßstab werden über
   `BRepBuilderAPI_Transform` eingerechnet (Flächenzuordnung über `ModifiedShape`). Geschlossene
   Schalen ohne Körper werden Körper, offene Schalen/lose Flächen ein offener Körper, reine
   Kanten-/Punktteile werden gezählt und gemeldet. Grenzen: `MAX_BODIES` = 10 000 (=
   Projektgrenze = 3MF), `MAX_DEPTH` 32, Besuchsgrenze; Abbruch vor/zwischen den Phasen und je
   Komponente.
2. **Vorrang festgelegt** (Docstring `read_assembly`, Karte brep):
   - *Name*: Instanz → Referenz (Teil) → Form (Körpername). Bei einem Teil mit mehreren
     Körpern geht der Körpername vor (Instanz/Referenz nennen die Gruppe), ohne ihn „Teil n“.
     Gleichnamige bekommen den nächsten unterscheidenden Vorkommensnamen in Klammern
     („Welle (Achse vorn)“), danach Nummern. Namenlose: ein Körper → Dateiname, sonst
     „Körper n“. Generierte Namen (OCCT-Übersetzername, NAUO-Nummer, XCAF-Typwörter) zählen
     nicht.
   - *Farbe je Fläche*: Instanz (äußerste Baugruppe zuerst, je Ebene SHUO vor
     Vorkommensfarbe) → Referenz (im Teil: Fläche → Schale → Körper → Teil) → Form
     (`ColorTool.GetColor(shape)`). Oberfläche vor allgemein, Kantenfarbe zählt nicht.
     **Abweichung von OCCTs eigener Darstellung** (`XCAFPrs`): Dort überstimmt eine
     Flächenfarbe im Teil die Instanzfarbe. Gewählt ist der Auftrag „Instanz vor Referenz“ —
     wer in der Baugruppe ein Vorkommen färbt, meint das ganze Vorkommen (so zeigt es
     SolidWorks). Frage an Robert unten.
3. **`load_step`**: `produces=VARIABLE`, `produces_from="bodies"`; neuer Parameter `bodies`
   (Art `step_bodies`, JSON-Liste der Kennungen; leer = Stand vor P7.4, ein Körper über
   `step.read`; `["*"]` = gemeldeter Rückfall), dazu `place_on_bed`, `centre`, `copy` wie
   `load`. Farben → Filamentslots nur, wenn die Datei ≥ 2 Farben kennt (dieselbe Regel wie
   3MF); Flächen ohne Farbe am neutralen Slot 0; mehr als 8 Farben je Körper → die häufigsten
   bleiben, Befund. Merkmale weiterer Instanzen desselben Teils werden übertragen statt neu
   gesucht (Beleg: gleiche `TShape`, starre Lage, gleiche Flächenzahl, nur Merkmale aus ganzen
   nativen Flächen mit Formmaßen; Dreiecke je nativer Fläche neu zugeordnet — `BRepMesh`
   trianguliert dieselbe Fläche an anderer Lage mit anderen Diagonalen, gemessen).
4. **Plan** (`ingest/plan.py`): liest die Baugruppe, schreibt alle Kennungen, `produces`,
   `copy`, beim ersten Modell `place_on_bed`/`centre`; `ImportPlan.choices` (Name, Farben,
   Maße, Teil) für die Importauswahl; `with_selection` kürzt. Nativer Fehler der
   Baugruppenlesung → `["*"]`.
5. **Verlauf** (`scene/history.py`): `_stated` zählt `step_bodies`; `change_params` verweigert
   auch einen Austausch gleicher Zahl, wenn spätere Schritte die Körper benutzen
   (`members_in_use`) — vorher blieben die Kennungen, und ein späterer Schritt hätte still einen
   anderen Körper getroffen.
6. **Format 30 → 31** (`_read_step_assemblies`, Identität, Versionsgrenze wie 25 → 26),
   `example_v31.p3d`, alte Beispieldatei `step_assembly_v30.p3d` (Mehrkörper-STEP im alten
   Schritt → ein Körper).
7. **Export**: `step.write_bodies` (XCAF, Namen wörtlich, Farben je Fläche, Wurzellage
   eingerechnet, ISO-10303-21-Kodierung); `writer._step_bytes` schreibt die Filamentfarben.
8. **Korpus** `tests/data/make_step_assembly_corpus.py` → `tests/data/step/*.step` (sechs
   Dateien); `--check` vergleicht den XCAF-Baum (die Bytes sind wegen adressabhängiger
   Stilreihenfolge in OCCT nicht wiederholbar — gemessen).
9. **Tests** `tests/test_step_assembly.py`: 55 Kerntests grün; `tests/test_step_assembly_ui.py`: 7 Fenstertests (nur beim Release).
10. **Oberfläche**: `app/ui/step_dialog.py` — Importauswahl (Liste mit Haken, Name, Maße,
    Farbfeld, Farbe als Wort im Tooltip — Regel 18 —, „Gespiegelt eingesetzt“, „Offene
    Flächen“, „Dasselbe Teil steht n-mal in der Datei“, Alle/Keine, Zählzeile), Vorschau der
    Lage als Hüllquader im Arbeiter (echte Vernetzung an 200 Teilen: 5,9 s + 3,6 s Bild,
    33 MB SVG — verworfen). `Session.choose_step_bodies`/`stepImportRequested`/
    `finish_step_import` nach dem Muster der Konturwahl; `StepBodiesField` (erbt
    `ContourField`) im Operationsdialog, „Körper wählen …“ öffnet dieselbe Auswahl (ohne Plan
    liest der Dialog die Datei im Arbeiter). `STEP_PLAN_IN_WORKER_ABOVE` = 2 MB (gemessen
    ≈ 0,6 s/MB). Offscreen-Sonde des Dialogs: Liste, Zählung, Tooltip, Vorschau, Leerwahl,
    Wiederherstellen einer gespeicherten Auswahl — alles wie erwartet (Fenstertests geschrieben,
    `tests/test_step_assembly_ui.py`, nicht gefahren — nur beim Release).
11. **Leistung**: `Solid.bounds` merkt sich seine Grenzen (vorher je Aufruf `AddOptimal`; an
    200 Instanzen 470 Aufrufe, 3,4 s); Gruppengrenzen fürs Bett misst `_group_bounds` nur an
    den Körpern, deren sicherer Quader über das bisher Äußerste reicht; die Auswahlliste nimmt
    die Maße des Teils (einmal je Teil) statt je Instanz zu messen (Plan an 1000 Instanzen
    9,45 s → 1,49 s).
12. **Plattformgleichheit**: neuer Weg `step_assembly` in `tests/test_platform_identity.py`
    (`_WAYS`): Lagen rechnet OCCT (`gp_Trsf`), Python nur Minimum/Maximum und Rundung;
    Fingerabdruck mit und ohne Rauschen gleich (Exit 0).
13. **`load_step` zog nach `app/core/ingest/step_ops.py`**: Die Richtung der Kernpakete erlaubt
    `ingest → brep`, nicht `brep → ingest` (`test_core_package_direction` meldete die trägen
    Importe von `bed_offset`, `copy_name`, `group_on_bed_finding`). Laden ist ohnehin
    Eingangsstufe; der Opname bleibt, alte Projekte laufen unverändert.

## Messungen an echten Dateien (`F:\3D Dateien`) und großen Baugruppen

Kundenweg: `import_plan(first_model=True)` → `History.apply` → `evaluate`, Entwicklungsrechner,
während parallel andere Pakete rechneten (Zeiten daher Obergrenzen).

| Datei | Größe | Körper | Plan | Auswertung | Namen | Farben → Slots | Befunde |
|---|---|---|---|---|---|---|---|
| `build_tray_v3.step` | 0,46 MB | 5 (1 Teil, 5 Körper) | 0,75–1,04 s | 2,6–4,4 s | `build_trayv22`, `internal_tray_subdivided4`, `internal_tray_blank`, `internal_tray_subdivided2`, `internal_tray1` (Fusion-Körpernamen) | eine Farbe (`#a0a0a0`) → keine Slots (3MF-Regel) | `load.assembly`, `load.assembly_on_bed`, `arrange.off_the_plate` (Baugruppe 391 × 421 mm größer als das Bett) |
| `carpet-corner-clip.step` | 0,37 MB | 2 | 0,12–0,27 s | 2,6–5,2 s | `Body1`, `Body4` | zwei Farben → je ein Slot (`#fff3ca`, `#ff8400`) | `load.assembly` |
| `Cat_1.stp` / `Cat_2.stp` / `Cat_3.stp` | 0,16/0,14/0,33 MB | je 1 | ≤ 0,3 s | 0,4–4,3 s | `Cica_1`/`Cica_2`/`Cica_3` (Produktname) | eine Farbe → keine Slots | — |
| synthetisch, 200 Instanzen (10 Teile, gerundet + Bohrung) | 0,82 MB | 200 | 0,44 s | 12,7–16,1 s | `Teil 1:1` … | je Teil eine Farbe → 1 Slot | Merkmale von 190 Instanzen übertragen |
| synthetisch, 1000 Instanzen (20 Teile) | 2,04 MB | 1000 | 1,49 s | 71–74 s | `Teil 1:1` … | wie oben | — |

Alle Körper geschlossen, Volumen je Datei plausibel; Ergebnis bei jedem Lauf vollständig
(`complete=True`). Aufschlüsselung an 200 Instanzen vor den Leistungsänderungen (cProfile,
17 s): `AddOptimal` 6,8 s (870 Aufrufe), Vernetzung 5,0 s (25 ms/Körper), Volumen der
Doppelprüfung 2,7 s (13 ms/Körper), Merkmale der 10 Referenzen 2,1 s, Übertragung auf 190
Instanzen 1,4 s. Die Auswertung läuft im Arbeiter mit Fortschritt je Körper und Abbruch; der
Plan ab 2 MB im Arbeiter.

**Downloads-Korpus**: Der Downloads-Ordner dieses Rechners enthält keine STEP-Datei (zwei
OneDrive-ZIPs mit Fotos). Mehrkörper-STEP mit Instanzen gibt es in `F:\3D Dateien` nicht; die
Instanzfälle deckt der synthetische Korpus (`tests/data/step/`).
14. **Nach dem ersten Tor**: `units.ASSEMBLY_BODIES`/`ASSEMBLY_DEPTH` als eine Quelle für
    3MF und STEP (`test_shared_constants` meldete die doppelten Zahlen), Vorschaugröße im Dialog
    privat (`_PREVIEW_PIXELS`, Name war in `examples.py` schon vergeben), eine Sperre für
    XCAF-Dokumente (`_XCAF`: Plan im Arbeiter und Auswertung eines zweiten Imports teilen die
    eine `XCAFApp_Application`), und eine Datei ohne Farbtabelle fragt keine Fläche nach ihrer
    Farbe (1000 Instanzen ohne Farbe: 1,71 s → 1,25 s).

## Übergabe an die Montageorganisation (P8) — geprüft, nicht gebaut

- **Montagelage ist heute die Ausgabe des Ladeschritts.** Jeder Körper steht nach `load_step`
  in seiner Weltlage aus der Datei (beim ersten Modell als Ganzes aufs Bett verschoben, die Lage
  zueinander bleibt). Späteres *Anordnen* überschreibt sie im Stapel; zurück führt nur Strg+Z.
  P8.2 („Montage- und Drucklagen derselben Körper speichern“) kann die Ausgabelage von
  `load_step` als erste Montagelage nehmen — sie ist reproduzierbar, weil sie aus der
  eingebetteten Datei und der Auswahl entsteht.
- **Gruppen**: `ingest.plan.imported_group` behandelt `load_step` wie `load` (beide in
  `PLAIN_IMPORT_OPS`); die unberührten Körper eines Imports bekommen schon heute das gemeinsame
  Aufsetzen. Für P8.1 („benannte Gruppen“) steckt die Baugruppenstruktur in den Kennungen
  (`1.2.1` = Vorkommen 2 → Vorkommen 1) und in der Datei; die Namen der Unterbaugruppen werden
  **nicht** gespeichert — P8.1 müsste sie aus der eingebetteten Quelle lesen (ein Zusatzfeld in
  `StepBody`).
- **Keine lebenden Instanzbeziehungen**: Zwei Instanzen desselben Teils sind unabhängige
  Körper; `StepBody.geometry` sagt nur beim Einlesen, welche dasselbe Teil sind (die Auswahl
  zeigt „Dasselbe Teil steht n-mal in der Datei“). Gespeichert wird diese Gleichheit nicht — P8
  darf sie nicht als lebende Beziehung versprechen; das deckt sich mit „keine dynamischen
  Bedingungen oder Instanzhierarchie“ (Konzept §13.11).

## Vorschlag für den Bauplan (nur mit Ansage übernehmen)

- **§20, Absatz „Import“**: statt „STEP keine Farbe aber echte Flächen (§30)“ → „STEP echte
  Flächen; eine Baugruppe kommt als einzelne exakte Körper mit Namen und Flächenfarben (§30).
  Farben werden Filamentslots, wenn die Datei mehr als eine kennt — dieselbe Regel wie bei der
  3MF.“
- **§29, „Formate“**: „STEP bei B-Rep-Objekten“ → „STEP bei exakten Körpern, mit Objektnamen und
  den Filamentfarben je Fläche“.
- **§30, neuer Absatz**: „Eine STEP-Baugruppe wird beim Einlesen in unabhängige exakte Körper
  aufgelöst: jede Komponenteninstanz in Weltlage, mit Namen und Flächenfarben; eine gespiegelte
  Instanz als Spiegelbild. Vor der Übernahme wählt der Kunde die Körper; die Auswahl steht im
  Ladeschritt, die Quelle bleibt die STEP-Datei. Lebende Instanzbeziehungen entstehen nicht.
  Vorrang von Name und Farbe: Instanz vor Referenz vor Form.“
- **§16/§9**: Formatversion 31; Parameterart `step_bodies` (zählt die Ausgänge, `produces_from`).

## Fragen an Robert (mit Empfehlung)

1. **Farbvorrang Instanz gegen Flächenfarbe.** Gebaut ist „Instanz vor Referenz vor Form“: Eine
   Farbe am Vorkommen färbt das ganze Vorkommen, auch Flächen, die im Teil eigens gefärbt sind
   (so zeigt es SolidWorks). OCCTs eigene Darstellung (`XCAFPrs`) ließe die Flächenfarbe stehen.
   *Empfehlung: so lassen.* Echte Dateien mit beidem gibt es im Korpus nicht.
2. **Name eines einzelnen Körpers.** Gebaut: der Name aus der Datei, wenn brauchbar
   (`Cat_1.stp` heißt „Cica_1“), sonst der Dateiname — dieselbe Regel wie bei der 3MF; vorher
   hieß jeder STEP-Körper nach der Datei. *Empfehlung: so lassen* (die Rundreise eines
   exportierten Körpers behält damit ihren Namen).
3. **Eine STEP-Datei für mehrere Körper beim Export.** Heute schreibt der Export je Körper eine
   Datei (Name und Farben reisen jetzt mit). `step.write_bodies` kann alle gewählten Körper als
   Baugruppe in eine Datei schreiben, wie die 3MF. *Empfehlung: als Vorgabe für STEP einbauen*
   — nicht gebaut (größere Variante, Exportdialog).
4. **Leistung großer Baugruppen.** 1000 Instanzen: Plan 1,5 s, Auswertung rund 70 s
   (Vernetzung 25 ms und Volumen 13 ms je Körper; exakte Körper liegen nicht im Plattencache,
   also auch beim Wiederöffnen). *Vorschlag:* Vernetzung und Volumen weiterer Instanzen vom
   ersten übernehmen (Beleg wie bei den Merkmalen: dieselbe `TShape`, starre Lage) und/oder
   exakte Körper im Plattencache ablegen (`Solid.to_bytes` gibt es). Beides greift in den
   Körpervertrag bzw. das Cacheformat — nicht ungefragt gebaut.
5. **Farbe als Filamentvorschlag aus dem Lager.** Gebaut ist der belegte 3MF-Weg (Farbe →
   Materialslot mit Farbe, „Slot n“). Eine nächstliegende Spule aus dem Lager je Farbe hat heute
   keinen belegten Weg — *Vorschlag* für das Filamentlager.
6. **Formatversion 31 beim Zusammenführen.** Hebt das Paket P7.1–P7.3 (`wt-p7verlauf`) ebenfalls
   auf 31, braucht eines von beiden 32 samt eigener Beispieldatei; die Migration hier ist eine
   Identität und lässt sich ohne Umbau umnummerieren.

## Tor

- Erstes Entwicklungstor (`tore/tor-p7step.txt`): 15988 passed, 6 failed, 49 skipped, Exit 1.
  Rot: `test_parts::…range_proof` (bekannt, nicht meins); `test_licence_notices`,
  `test_licences::…runtime_tree…`, `test_sbom::…native_libraries…` — die editierbare
  Installation zeigt auf den Hauptbaum, der seit `5a57e261` VTK ausgebaut hat; der Arbeitsbaum
  (56f70000) führt VTK noch in seinen Listen. Nicht durch dieses Paket, nicht behebbar ohne den
  Hauptbaum. Die zwei `test_shared_constants`-Fehler waren meine — behoben (Punkt 14).
- Zweites Entwicklungstor nach allen Änderungen (`tore/tor-p7step-2.txt`): **15990 passed,
  4 failed, 49 skipped, Exit 1** — rot nur noch der bekannte Bereichsnachweis und die drei
  Lizenz-/SBOM-Prüfungen, die die Paketmetadaten des Hauptbaums lesen (VTK-Ausbau `5a57e261`).
- `ruff check .` Exit 0, `ruff format --check .` Exit 0, `mypy` Exit 0 (314 Dateien).
- Fenstertests (`tests/test_step_assembly_ui.py`, 7) und Leistungsprüfungen nicht gefahren
  (nur beim Release); der Dialog ist per Offscreen-Sonde geprüft.

## Dateien

Kern: `app/core/brep/step.py` (Leser/Schreiber), `app/core/ingest/step_ops.py` (neu,
`load_step`), `app/core/ingest/plan.py`, `app/core/ingest/ops.py` (`group_on_bed_finding`),
`app/core/ingest/threemf.py` (Grenzen aus `units`), `app/core/units.py`,
`app/core/brep/kernel.py` (`is_closed`, `bounds`-Merker, `face_sources`),
`app/core/brep/ops.py` (`load_step` ausgezogen), `app/core/export/writer.py` (Farben in STEP),
`app/core/registry/params.py` (`step_bodies`, `body_keys`, `WHOLE_FILE`),
`app/core/scene/history.py` (`_stated`, `members_in_use`), `app/core/scene/migrations.py`
(30 → 31), `app/core/types.py`, `app/core/bootstrap.py`. Oberfläche: `app/ui/step_dialog.py`
(neu), `app/ui/session.py`, `app/ui/main_window.py`, `app/ui/op_dialog.py`. Kataloge: 33 neue
Texte in allen fünf Sprachen, ein toter entfernt. Paket: `packaging/solidon3d.spec`
(XCAF-Module). Tests: `tests/test_step_assembly.py` (neu), `tests/test_step_assembly_ui.py`
(neu), `tests/data/make_step_assembly_corpus.py` + `tests/data/step/*.step` (neu),
`tests/data/projects/example_v31.p3d`, `step_assembly_v30.p3d` (neu), angepasst
`test_cli`, `test_ingest`, `test_errors`, `test_export`, `test_platform_identity`. Doku: Karten
`brep`, `ingest`, `ui`, `tests/data`; Regeln `dateiformat.md`, `wartezeit.md`,
`oberflaeche.md` (Parameterzahl 1250); `ROADMAP.md` (P7.4).
