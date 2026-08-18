# Durchsicht vom 16.08.2026 — Code, Oberfläche, Wettbewerb

Sechs Durchgänge an einem Tag über den ganzen Stand: drei Code-Reviews über den
Kern (Geometrie · Fertigung · Wissen und Agentenschicht), ein Review der
Oberfläche, eine Bedienlogik-Durchsicht der vier Hauptwege und eine
Wettbewerbsrecherche als Erweiterung des Live-Vergleichs vom 05.08. Nichts
wurde geändert — das hier ist der Befund, nicht der Fix.

**Baseline vor der Durchsicht:** Umgebung auf `constraints.txt` gebracht
(darunter trimesh 4.12 → 5.0.0 — der Major-Sprung ist in beiden Kern-Gebieten
nachweislich folgenlos, alle benutzten API-Pfade gegen die installierte
Fassung aufgelöst). Suite portionsweise in acht Blöcken: **4009 Tests grün**,
ruff, `ruff format --check` und mypy grün. Der Lauf am Stück stirbt weiterhin
am bekannten nativen rtree-Abriss — das ist Umgebung, nicht Code.

Im Arbeitsbaum lagen ungestagte Änderungen einer Nebensitzung
(3MF-Export mit Druckeinstellungen); Bewertung ganz unten.

---

## Stopper — vor der nächsten Auslieferung

Alle sieben sind belegt, keiner ist eine Vermutung. Das Muster hinter fünf von
ihnen: die Suite ist grün, weil kein Test die Form kennt, in der der Fehler
auftritt.

### K1 · Division durch einen Parameterverweis ist grundsätzlich unmöglich

`app/core/scene/expressions.py:186` — §13. `references()` und `check()` bauen
den Parser mit `values=None`; `_lookup` liefert dann `0.0`, und der
Divisionsschutz lehnt **jeden** Ausdruck der Form `=@width/@count` ab — im
Op-Dialog, bei Projektparametern, beim Auswerten. `=@width/2` geht, Division
durch einen Parameter nie. Zusatzschaden: `sketch/serialize.py:151` fängt die
`ValidationError` still, ein Skizzenmaß `=@d/@n` liefert eine leere
Referenzmenge und rechnet nach Parameteränderung mit altem Cache weiter.
*Fix:* Im Prüfmodus die Divisionsprüfung überspringen (oder Platzhalter `1.0`);
die Division-durch-null-Prüfung gehört zu `evaluate()`, wo echte Werte stehen.
Test: kein einziger Fall in `tests/test_expressions.py` dividiert durch einen
Parameter — genau das Loch schließen.

### K2 · Die OpenSCAD-Quelltextprüfung ist umgehbar

`app/core/backends/openscad.py:60` — Regel 11, §32. Das Muster kennt nur
`include|use|import|surface` mit Klammer. Die veralteten, aber lauffähigen
Formen gehen durch: `import_stl("/etc/passwd")`, `import_dxf(…)`,
`linear_extrude(file=…)`, `dxf_linear_extrude(file=…)`. Gegen das installierte
OpenSCAD belegt — die Datei wird wirklich gelesen (Warnung über den Inhalt von
`win.ini` im Lauf). Damit greift LLM- oder Fremdquelltext an der Prüfung
vorbei nach außen. *Fix:* Muster um die Altformen erweitern und jedes
`\bfile\s*=` als nicht prüfbare Einbindung werten; die sechs Formen in die
Parametrisierung von `tests/test_openscad.py` aufnehmen.

### K3 · Die Filamentwahl je Slot erreicht die Übergabe nie

`app/core/export/handover.py:388` liest `slot.material` — und
`MaterialSlot.material` (`app/core/types.py:220`) wird nirgends im Produkt
gesetzt. Was der Dialog je Slot einsammelt, liegt in
`PrintSettings.slot_profiles` und wird nur vom Dialog selbst gelesen. Folge:
alle Slots slicen mit `setup.base_filament`, nur die Farbe stimmt — während
der Dialog „{slot} druckt mit {profil}." meldet. Der einzige Test dazu
(`tests/test_print_settings.py:1521`) baut den Wert von Hand, den keine
Produktionsstelle erzeugt. *Fix:* `PlateRun.slots` in `_plate_run` aus
`settings.slot_profiles` befüllen und `_orca_filament` den Namen über
`profile_file(…, "filament")` auflösen lassen.

### K4 · Die exportierte 3MF trägt absolute Pfade als Profil-IDs

`app/core/export/handover.py:487-492` schreibt `machine_profile` /
`base_process` / `base_filament` unverändert in die `*_settings_id`-Felder —
und die Oberfläche legt dort Pfade ab
(`C:\Program Files\ElegooSlicer\resources\…`). Zwei Schäden: der Pfad des
eigenen Rechners reist in einer Datei mit, die weitergegeben wird (Regel 12
dem Sinn nach, gegen den eigenen `SlicerSetup`-Docstring), und die
Orca-Familie erwartet dort **Namen** — ein Pfad trifft kein Preset. Die
Referenzumsetzung `3D Drucker/08_Gewuerzregal_Strebergarten/make_3mf.py:263`
macht es richtig. *Fix:* IDs aus Namen bilden; `SlicerSetup` braucht Name und
Pfad, oder Rücklesen über `find_profiles`.

### K5 · Der Slicer-Lauf: Timeout tötet den Dialog, Schließen friert ein, Abbrechen fehlt

Drei Teile desselben Wegs (§2.8, Regel 17):
- `handover.py:926` ruft `subprocess.run(…, timeout=300)` ohne Behandlung von
  `TimeoutExpired`/`OSError`; `_SliceWorker.run` fängt nur `AppError`
  (`print_settings_dialog.py:772`) — der Thread stirbt, der Dialog steht
  dauerhaft auf „Der Slicer rechnet …". Der Zwilling ist längst gelöst:
  `openscad.render` samt Test.
- `closeEvent` (`print_settings_dialog.py:1828`) wartet mit `worker.wait()`
  **ohne Zeitgrenze** im Hauptthread — Minuten Stillstand bei großen Platten.
  „Schließen"/Escape gehen zudem über `reject()`, das gar kein `closeEvent`
  auslöst: der Arbeiter läuft unsichtbar weiter, `_temporary` bleibt liegen.
- Es gibt im ganzen Dialog **kein Abbrechen**, der Balken ist unbestimmt
  (`setRange(0, 0)`), obwohl die Plattenzahl bekannt ist.
*Fix:* `try/except (TimeoutExpired, OSError)` → `ExternalToolError` mit
Vorschlägen; `_SliceWorker` bekommt `cancel()` mit Prozess-Handle;
`closeEvent`/`reject()` rufen `cancel()` und warten mit Grenze; Balken
`setRange(0, len(runs))`.

### K6 · CuraEngine scheitert am eigenen Türsteher

`print_settings_dialog.py:1613` verlangt für alles außer `prusa` ein
Maschinenprofil — für Cura findet `find_profiles` strukturell **null**
(sucht `machine/process/filament`-Ordner, Cura hat
`definitions/variants/quality`; gegen Cura 5.13 gemessen). Dabei ist der Kern
vorbereitet: `_machine_keys` beschreibt die Maschine selbst, `_command` fällt
auf `_cura_base` zurück. Der Nutzer sieht stattdessen „Keine Profile
gefunden" und soll aus einer leeren Liste wählen (Regel 17, §2.7). *Fix:*
Bedingung auf `flavour == "orca"` einengen; Hinweistext für Cura: Solidon
bringt die Maschine mit.

### K7 · Weg 4 (organisch formen) ist gebaut, aber nicht benutzbar

P16 hat einen vollständig getesteten Kern und eine Oberfläche ohne Abnahme —
kein Durchlauf am laufenden Programm, wie ihn P15 hatte. Vier Teile:

- **Skeletteditor endet in einer Operation, die nichts tut**
  (`main_window.py:3215`): `finish_armature` schickt `pose: ""` — der Körper
  bleibt, wie er war, ohne Ansage. Weiter geht es nur über Verlauf →
  Doppelklick → „Weitere Einstellungen" → **rohes JSON** tippen
  (`kind="armature"` fällt in `op_dialog.py:458` auf `QLineEdit` durch, die
  Vorderseite des Dialogs ist leer). 14 Klicks und eine unbekannte Syntax für
  einen gebeugten Arm. *Fix sofort:* `finish_armature` gibt an
  `run_operation(…, given={"armature": …})` ab, wie `finish_sketch`. *Fix
  richtig:* ein `ArmatureField` mit drei Zahlenfeldern je Knochen, `pose`
  nach vorn.
- **Eine getippte Pose tötet den Auswertungs-Thread, die Sitzung meldet
  Erfolg** (`app/core/geom/pose.py:262/278`): `json.loads` ungeschützt,
  `JSONDecodeError` ist kein `AppError`, läuft an `evaluate` vorbei aus
  `QThread.run` heraus — danach `vollständig=True`, kein Fehlersignal, altes
  Ergebnis steht. *Fix:* beide Leser fangen und werfen `ValidationError` mit
  Beispiel-Vorschlag; `evaluate` wandelt fremde Ausnahmen unterhalb von
  `spec.fn` generell in `InternalError` mit Op-Bezug.
- **„Relief auflegen" ist eine Sackgasse** (`displace.py:257`,
  `main_window.py:240`): Das Feld „Bild" listet Quellen aus
  `document.sources`, und dorthin führt kein Bildformat — `MODEL_SUFFIXES`
  kennt keines. Der Befund schlägt „Ein Bild wählen." vor, eine Handlung, die
  die Oberfläche nicht anbietet. *Fix:* Bildimport in den Quellenweg (Knopf
  *Bild wählen …* + Drop auf den Viewport); bis dahin gehört die Op nicht ins
  Menü.
- **Der Startbildschirm-Import lädt ins Unsichtbare** (`main_window.py:2007`):
  `action_import` ist von acht Aufrufstellen die einzige ohne
  `_show_start_screen(False)` — und genau darauf zeigt der Schlussknopf der
  Erstinbetriebnahme (`main_window.py:4962`). Modell geladen, Startbildschirm
  bleibt stehen. *Fix:* wie `open_path` beginnen; dasselbe für
  `action_generate` und `action_catalog` prüfen.

---

## Mittel

**Geometrie-Kern**
- `scene/cache.py:194-259` — der Platten-Cache verliert `findings`, `solver`
  und `transform`: nach Cache-Treffer wandern Merkmalsbezeichner (§21.2) und
  die Voxel-Warnung verschwindet (§17.2). Round-Trip-Test fehlt.
- `geom/repair.py:85-316` — T-Kreuzungs-Vernähen quadratisch (gemessen 10,7 s
  bei 2100 Randkanten, ~41 s am eigenen Limit) und läuft doppelt
  (`repair()` → `stitch` + `fill_holes` → intern erneut, Faktor 2,1).
  KD-Baum-Vorfilter + `stitch=False`-Schalter.
- `geom/boolean.py:62-154` — die Rückfallkette kennt keinen Abbruch (§15.6);
  im ganzen Gebiet fragt nur die Orientierungssuche den `CancelToken` ab.
- `scene/fits.py:34` — `FIT_TOLERANCE = 0,05 mm` widerspricht §14
  (`EPS_GEOM`) ohne Vermerk; bei Presspassungen ist das die halbe Aussage.
  Entweder begründen und §14 nachziehen oder angleichen.
- `brep/edit.py:218` — Fehlertext endet wörtlich mit „fehlgeschlagen"
  (Regel 17), die geerbten Vorschläge (Reparatur, offene Kanten zeigen) gibt
  es für B-Rep nicht.
- `sketch/profile.py:254` — `if sweep == 0.0` fängt den Vollkreisfall nie
  (Löser-Restfehler ~1e-12); Winkeltoleranz statt Gleichheit (Regel 6).

**Fertigungskern**
- `slicer_keys.py:352` — Baumstützen erreichen Cura nicht:
  `support_structure` wird nie geschrieben, der Test bestätigt nur An/Aus.
- `perceive/maps.py:113` — `MapTooLarge` ist kein `AppError`: kein Vorschlag,
  fällt durch die Regel-17-Prüfung; Oberfläche zeigt nur „zu groß".
- `ingest/ops.py:97` + `threemf.py:392` — beim 3MF ist nur die gepackte Größe
  gedeckelt; 2,6 MB → 1,08 GB entpackt, über `fetch` aus dem Netz erreichbar
  (§32). Entpackte Summe aus `infolist()` vorab prüfen.
- `ingest/ops.py:262` — die Antwort auf die Einheitenfrage wird nicht in die
  Op-Parameter geschrieben: gleicher Cache-Schlüssel für verschiedene
  Antworten (§15.1), erneute Frage bei jedem Öffnen; die CLI macht es richtig.
- `handover.py:687` — `profile_differences` löst Profil-**Namen** nicht auf
  (nur Pfade), die Gegenüberstellung entfällt wortlos.
- `slice/gcode.py:280` — eine Nullmessung gilt als Übereinstimmung:
  `deviation` liefert bei `measured <= 0` glatt `0.0`; `filament_grams` hat
  die Null-Absicherung nicht, die `filament_mm` seit dem Cura-Vorfall hat.

**Wissen und Agentenschicht**
- `knowledge/parts/fasteners.py:207/297` — `nut_trap` (0,2) und
  `printed_thread` (0,15) tragen ihre Toleranz als Konstante; der
  Profil-Füllzweig (`ops.py:262`) greift nur bei `0.0` — die Kalibrierung
  nach §28.3 erreicht beide nie (Regel 7). TPU baut die Mutternfalle mit
  PLA-Spiel.
- `bootstrap.py:47` — **eigene Bausteine werden nie geladen**:
  `parts/user.py::load()` hat keinen Aufrufer im Produkt (§24.5 nicht
  umgesetzt); `travelling_parts` ist toter Code, der Katalogzweig
  `spec.own` unerreichbar.
- `knowledge/licences.py:29` — die Lizenzprüfung deckt nur `geom,ui`,
  ausgeliefert wird `geom,ui,agent,brep`: acht Pakete ungeprüft und ohne
  Hinweis im Über-Dialog; `cadquery-ocp-novtk` meldet Apache, der
  OCCT-Kern darunter ist LGPL-2.1+Ausnahme (§36).
- `profiles.py:45` / `print_settings.py:67` / `calibration.py:137` — eine von
  Hand beschädigte Nutzer-TOML stürzt beim Start mit rohem Stacktrace ab
  (`TOMLDecodeError` ist kein `AppError`); dazu `calibration.py:162`:
  `_literal` maskiert Anführungszeichen nicht — ein Materialtitel mit `"`
  macht die Kalibrierdatei unlesbar.
- `manual.py:1315` — „Meldungen im Wortlaut" verspricht Vollständigkeit und
  erfasst nur `errors.py`: die fünf Ausnahmen aus anderen Modulen fehlen
  (`BackendUnavailable`, `GenerationFailed`, `LicenceKeyError`,
  `ScadUnavailable`, `UnsafeSource`) — ausgerechnet die nachschlagbaren.
- `tools/make_licence_keys.py:112` — zwei Vorratsläufe am selben Tag erzeugen
  **identische Schlüssel** (Nutzlast vollständig determiniert); `--start`
  oder Zufallsanteil, plus Kollisionsprüfung.
- `backends/llm.py:151` — ein nicht erreichbares Modell bietet nur
  „Abbrechen" (§33.1 will `ExternalToolError` mit „Einstellungen öffnen").
- `backends/keys.py:62` — `store()` fängt die Schlüsselbund-Ausnahme nicht
  (`read()` schon): Absturz beim Eintragen des Schlüssels bei gesperrtem
  Schlüsselbund.
- `print_settings.py:127` — unbekanntes Material bekommt still PLA-Werte,
  nur als `_log.info`; ein Befund `settings.material_without_profile` in
  `advise` fehlt (Regel 21).

**Oberfläche**
- Fünf Dialoge lassen Arbeiter zu früh los (`self._worker = None` im
  `finished`-Slot): `print_settings_dialog.py:1826/1287`, `dialogs.py:470`,
  `generate_dialog.py:347`, `install_dialog.py:248` — genau die Falle aus
  `.claude/rules/oberflaeche.md`; das Hauptfenster macht es mit
  `_retire`/`_hold_until_done` vor. Die Halteleine in ein gemeinsames Modul
  heben. Dazu `main_window.py:3445`: `_hold_until_done` versucht die
  Freigabe genau einmal — `_retired` wächst über die Sitzung.
- `main_window.py:2429-2530` — `action_export` rechnet und schreibt komplett
  im Hauptthread (§2.8), ohne Wartezeiger; `main_window.py:2311` blockiert
  bis 2 s vor den Druckeinstellungen; `session.py:669/395` lesen Dateien
  synchron.
- `viewport.py:3620-3730` — der Interaktionsstil hält den Plotter stark in
  einer Closure (Zyklus bis zum GC), und `_end_drag` baut je Zugende einen
  neuen Stil; `main_window.py:2262` — `PrintSettingsDialog` ohne
  `WA_DeleteOnClose`, jede Öffnung bleibt samt Profilliste hängen.
- Bedienlogik Weg 4: Sculpting kennt kein Ziehen (ein Klick = ein Zug; 20
  Züge = 20 Klicks; `apply_strokes` kostet gemessen 2 ms/25 Züge — Ziehen
  wäre billig); während Form-/Skelettsitzung bleiben alle Ops anklickbar,
  „Objekt entfernen" + *Fertig* verliert die Züge mit falschem Fehlertitel
  („Ein Wert liegt außerhalb des zulässigen Bereichs"); *Formen*/*Skelett*
  liegen unter *Ändern → Netz* zwischen Reparaturwerkzeugen statt in der
  Werkzeugleiste (Widerspruch zur Hauptwege-Tabelle der Gebietsregel), die
  Tour nennt den falschen Pfad und verspricht „malen".
- Befehlspalette (`main_window.py:3288`): umgeht die Gestenmodi
  (`run_operation` statt der Verzweigung aus `_operation_action`) und kennt
  keine Verfügbarkeit — die Sackgasse, die `_update_actions` im Menü
  ausdrücklich beseitigt hat, steht dort offen.
- `viewport.py:690` — die Differenzlegende färbt beide Kodierungen in der
  Farbe von `added` (Regel 18 formal erfüllt, Farbe sagt die Unwahrheit);
  `print_settings_dialog.py:912` — Labels ohne `setBuddy`, Screenreader liest
  namenlose Felder; `app.py:144` — Fenstergeometrie wird nie gespeichert.
- `main_window.py:3072` — die mitlaufende Wandprüfung rechnet im Hauptthread:
  273 ms bei 82k Dreiecken, nach jedem Pinselzug (§2.8-Grenze 200 ms).

---

## Gering

- **Sprachregelung** — AGENTS.md sagt „vollständig übersetzt", das stimmt an
  ~30 Stellen nicht: englische Docstrings/Kommentare in
  `registry/registry.py`, `brep/edit.py`, `brep/kernel.py`, `geom/hollow.py`,
  `geom/difference.py`, `scene/__init__.py`, `scene/serialise.py`,
  `geom/measure.py`, `export/__init__.py`, `export/writer.py`,
  `slice/analysis.py`, `slice/orientation.py`, `ingest/loader.py`,
  `perceive/features.py`, `perceive/maps.py`, `perceive/matching.py`,
  `agent/prompt.py`, `agent/proposal.py`, `agent/session.py`,
  `knowledge/licences.py`, `knowledge/parts/registry.py`,
  `knowledge/standards.py`, `backends/keys.py`. Dazu acht **englische
  nutzersichtbare Fehlertexte** in `backends/mesh.py` (u. a. „the generation
  ran into its time limit"), ein zerrissener Modul-Docstring ebenda
  (`mesh.py:16-33`), „aufgeloest" in `slice/advise.py:652`, und
  `tools/check_env.py` voller deutscher Bezeichner (`WURZEL`,
  `verlangte_fassung`, …) — `test_language_rules.py` prüft `tools/` nicht.
- `registry/params.py:234` doppelter Kommentarblock ·
  `slicer_keys.py:375` Kommentar an der falschen Zuweisung ·
  `estimate.py:15` behauptet ein Feld `source`, das es nicht führt ·
  `slicer_profiles.py:376` stiller `except` ohne Protokollzeile ·
  `perceive/features.py:162` Zylinder-Sortierung ohne Z (koaxiale Bohrungen
  instabil nummeriert, §21.2) · `ingest/fetch.py:89` Weiterleitung kann
  `check_url` umgehen (Redirect-Handler erlaubt auch ftp) ·
  `perceive/maps.py:136` Analysekarten ohne `CancelToken` (Regel verspricht
  abbrechbar; gemessen 3,4 s bei 51k Dreiecken) · `cli/main.py:261` ein
  Fehlerausgang ohne Vorschlag · `geom/mesh.py:87`+`boolean.py:176`
  Slot-Übernahme allein über Flächenzahl (billiges Zweitkriterium fehlt) ·
  `agent/context.py:88` der Steckbrief reist ohne Injektions-Rahmensatz
  (Nachbar `CARRIED_CHAT_NOTICE` hat ihn) · `print_settings.py:149`
  `round()` im Kern statt an der Übergabe (Regel 6) · `main_window.py:2158`
  Kommentar „einzige Nachfrage" stimmt nicht mehr · `bake_sculpt` mit
  Qt-Standardknöpfen statt Handlungsnamen · `displace_image`-Dialog schaltet
  bei „Auflegen" nicht um (`at_feature` bleibt wirkungslos stehen) ·
  *Hilfe → Beispiele* aus der August-Durchsicht (2.2) fehlt weiterhin.

## Testlücken (übergreifend)

Kein Test dividiert durch einen Parameter · kein `DiskCache`-Round-Trip mit
`findings`/`transform` · keine selbst zurückfallende Boolesche Kette (jede
Stufe nur erzwungen) · kein Repair-Fall mit vielen Randkanten samt
Zeitschranke · kein Test für Slicer-Timeout (Zwilling `test_openscad.py:432`
existiert) · `*_settings_id`-Inhalte ungeprüft · Cura-Stützen nur An/Aus ·
`profile_differences` nie mit Namen · `test_errors.py` läuft nur
`AppError`-Nachkommen ab (sieht `MapTooLarge` nicht) · `test_ui.py` prüft den
3MF-Export nicht für Einzelkörper und nicht ohne gesetzte `print_settings`.

---

## Der ungestagte Diff der Nebensitzung (3MF-Export mit Druckeinstellungen)

**Urteil: nachbessern, nicht so committen.** Absicht richtig (§29), aber:

- **A1** `main_window.py:2493` — `document.print_settings` ist im Normalfall
  `None` (Dialog nie geöffnet): genau dann exportiert weiter reine Geometrie.
  Rückfall `or print_settings.resolve(self.session.profile)` wie in
  `_compare_totals`.
- **A2** `main_window.py:2509` — der Einzelkörper-Export (häufigster Fall)
  läuft über `plan_export`/`write_plan`, die `settings`/`setup` nicht kennen.
  3MF immer über `write_assembly` führen oder die beiden erweitern.
- **A3** `remembered_setup` nimmt `slicer_base_filament` global statt je
  Material (Dialog löst je Material auf) — nach PETG-Lauf trägt ein
  TPU-Projekt das PETG-Profil.
- **A4** `find_program` (~0,5 s) läuft im Hauptthread nach dem Dateidialog,
  auch wenn `settings is None` es sinnlos macht.
- **A5** `slicer_machine_profile` wird nur beim **Slicen** gemerkt, nicht beim
  Schließen des Dialogs — der Docstring verspricht mehr.
- **A6** kein Abgleich des gemerkten Profils mit dem Drucker des Projekts.
- **A7** der neue Test (zwei Körper, Einstellungen vorher gesetzt) lässt A1
  und A2 grün durchlaufen — denselben Zip-Test für Einzelkörper und ohne
  gesetzte Einstellungen wiederholen.

---

## Was hält (geprüft, kein Fund)

trimesh 5.0.0: kein Migrationsbedarf in geom/scene/slice/ingest/export ·
Regel 3 (Szene nur lesend): kein Schreibzugriff, alles `dataclasses.replace` ·
Regel 9: alle vier Zufallsstellen mit Startwert · Regel 10: kein
`eval`/`exec`/`pickle` auf fremden Daten · Regel 12 in der Projektdatei
(`_check_relative`) · Regel 14 durchgehend (`source="internal"`/`"gcode"`,
`combine()` mischt nichts) · Regel 16 von beiden Seiten
(`_refuse_mixed`, alles in einer Transaktion) · Regel 19: genau zwei
Nachfragen, beide begründet · Regel 20: keine feste Zeichenkette ·
§22: nirgends wird G-Code erzeugt · die drei Fixes vom 15.08. halten der
Nachmessung stand (Platten je Lauf, `match_filament` ohne Drucker 0,56 s,
Stiftrechnung exakt auf der Schwelle) · `vtkCellPicker` hat das
Picking-Problem vom August erledigt · Erstinbetriebnahme sauber (Regel 18,
Knopfnamen, Überspringen zählt) · MCP-Schnittstelle dreifach geprüft ·
Ed25519 lehnt Small-Order-Schlüssel ab · alle sechs Sprachkataloge
vollständig · Weg 1 trägt vollständig (8 Klicks + 1 Zug), Weg 2 mit 3 Klicks
vorbildlich, die Mehrplatten-Übergabe sauber geschnitten · die
Sculpting-Leiste selbst ist der beste neue Teil (Warnung mit dem Knopf, der
sie behebt).

---

## Wettbewerb — Stand 16.08.2026

Erweiterung des Messvergleichs vom 05.08. um Markt, Preise, Funktionsumfang.
Quellen und Detailmatrix im Rechercheprotokoll; Kernaussagen:

**Die Chat-Alleinstellung ist seit Januar 2026 nicht mehr konkurrenzlos.**
Zoo hat mit „Zookeeper" (Design Studio v1.1) einen konversationalen
Parametrik-Agenten marktreif: erzeugt KCL-Modelle, bearbeitet, fragt zurück —
aber Cloud-Pflicht, Abo, Ingenieurs-Zielgruppe. AdamCAD (YC, 4,1 Mio. Seed)
macht Text→OpenSCAD mit Slidern im Web. Backflip AI liefert seit 03.08.2026
Scan/STL→**parametrischer Feature-Baum** ab ~10 USD je Teil — das trifft
Solidons Weg 1 von der anderen Seite. Verteidigungsfähig ist die Position nur
als Paket: **lokal + kalibrierte Passungen + Schichtanalyse speist die
Konstruktion + Einmalkauf** — kein Wettbewerber hat die Kombination.

**Kalibrierte Passungen hat sonst niemand.** Bambus Schnittverbinder sind
laut Community Ausrichthilfen, keine Presspassungen. Bedrohung gering — das
braucht Konstruktions- und Slicer-Wissen in einem Produkt.

**Gefährlichstes Ökosystem: Bambu Studio / MakerWorld.** Meshy-6
(Bild→farbiges 3MF, seit 17.03.2026), Hunyuan 3.1 und Tripo 3.0 im Browser,
dazu OpenSCAD-Customizer („Parametric Model Maker") und
Slicer-Konstruktionswerkzeuge in einem Gratis-Konto. Die Slicer besetzen die
einfachen Hälften von Solidons Feldern (Orca: Auto-Orient-Heuristik;
Schneiden mit Verbindern) — was ihnen fehlt, ist die Rückkopplung in die
Konstruktion. Diese Formulierung („Schichtanalyse speist die Konstruktion")
sollte auch das Marketing tragen.

**Die fünf größten Lücken aus Kundensicht (priorisiert):**
1. Weg-3-Einstieg: MakerWorld macht Foto→Druckdatei in Minuten im Browser,
   Solidon verlangt lokale ComfyUI-Installation. Optionaler, klar
   gekennzeichneter Cloud-Generator-Anschluss (BYOK wie beim Chat).
2. Verrundung/Fase auf importierten STLs — bewusst ausgeschlossen, aber die
   Kundenerwartung existiert; mindestens eine geführte Erklärung im Produkt.
3. Gridfinity-Baustein fehlt — meistgedruckte Funktionsteil-Kategorie, mit
   `register_part` klein und ein Verkaufsargument.
4. Messen am Referenz-Mesh: gescanntes/generiertes Netz laden, Passmaße
   daran abgreifen — die native Antwort auf Backflip im Rahmen der eigenen
   Doktrin.
5. Anschluss ans Customizer-Ökosystem: fremde `.scad`-Customizer öffnen und
   deren Parameter als Projektparameter anbieten (§32-Prüfung existiert).

**Preis-Einordnung:** Markt bei 0 € geankert (Fusion Personal, FreeCAD,
alle Slicer); einzige akzeptierte Einmalkauf-Referenz ist Plasticity
(150 USD, 12 Monate Updates). Sinnvoller Korridor **69–99 € einmalig**,
optional ein Update-Jahr nach Plasticity-Muster; über 149 € konkurriert man
gegen „Fusion Personal ist gratis", unter 49 € wirkt es wie ein Tool.

---

## Reihenfolge (Wirkung je Aufwand)

1. **K1** Division (Fix + Test — Stopper für §13)
2. **K2** OpenSCAD-Muster (Sicherheit, vor jeder Auslieferung)
3. **K7** Weg 4 benutzbar: `finish_armature` → `run_operation` (eine Zeile),
   `json.loads` fangen + `evaluate` härten, Bildquelle, Startbildschirm
4. **K3/K4** Übergabe: Slot-Filamente verdrahten, Profil-IDs als Namen
5. **K5/K6** Slicer-Lauf: Timeout, Abbrechen, `closeEvent`; Cura-Türsteher
6. Nebensitzung: A1/A2 nachbessern, dann committen
7. Mittel-Block Kern (Cache-Round-Trip, Vernähen, `FIT_TOLERANCE`,
   Bausteintoleranzen, eigene Bausteine, Lizenz-Extras, TOML-Robustheit)
8. Mittel-Block Oberfläche (Halteleine vereinheitlichen, Export asynchron,
   Sculpt-Ziehen, Ops-Sperre in Gestensitzungen, Palette)
9. Gering-Block (Sprache, Kommentare, Kleinigkeiten) als eigene Runde
10. Wettbewerb: Gridfinity-Baustein und Weg-3-Anschluss als nächste
    Produktentscheidungen mit Robert
