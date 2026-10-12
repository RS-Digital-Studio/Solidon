# Review RM-587 „Lange Brücken bekommen ihre Stütze, und was frei druckt, hält“ (rv587)

Gegenstand: Worktree `F:/sl-bruecken`, Zweig `einstellungen/bruecken-rm587`, Stand `31788ce82`
(welle3 `aff70cb91` enthalten). Eigener Diff: `git diff origin/welle3...31788ce82` (37 Dateien,
+2332/−49), vollständig gelesen, dazu `split_for_parts`, `part_advice`, `_from_geometry`,
`_bridge_width`, die Feldmarkierung und die Ablehnungslogik des Druckdialogs. Nur gelesen und
gemessen, im Worktree nichts geändert (`git status` am Ende leer). Gemessen an Archivabzügen beider
Stände (`rv587/alt` = `aff70cb91`, `rv587/neu` = `31788ce82`, je mit der übersetzten Kernbibliothek
des Hauptbaums; `_chain.pyx` ist in allen drei Ständen gleich), Slicer und Rechnungen gepinnt
(`FFFFF0FF`). Scratch: `scratchpad/rv587/`.

## Verlauf

- Auftrag, Bericht des Bauagenten (`berichte-2026-10-10/rm587.md`), Koordination gelesen.
- Ratsonde `probe_rat.py` (20 Prüfkörper × bis 6 Varianten) → `rat.out`, Exit 0.
- Bandsonde `probe_steil.py` (K1 Max, Kobra 2, MK4S; ABS) → `steil.out`, Exit 0.
- Wirkung je Teil mit der Sonde des Bauagenten gegen `neu`: OrcaSlicer, PrusaSlicer, Bambu
  Studio, Cura; Fälle dick, fluss, stuetze, rand, trichter, nat-frei → `gcode_runs.out`, alle Exit 0.
- SuperSlicer 2.5.59.13 am Dateiexport, `probe_ss.py` → `ss.out`, `ss2.out`, `ss3.out`, Exit 0.
- PrusaSlicer 2.9.6 am geschlossenen Deckel mit/ohne Zusatzwände, `deckel_prusa.py` →
  `deckel.out`, Exit 0.
- Gezielte Tests im Abzug `neu` (RM-587-Tests aus `test_advise`, ganz `test_slicer_part_settings`
  und `test_print_time`, vier aus `test_manufacturer`): 28 + 174 passed; ein Fehlschlag
  (`test_the_slicer_selection_installs_the_measured_versions`) ist ein Abzugsartefakt (fehlendes
  `.github/`). Text- und Unterlagentests im Worktree (`test_translations`, `test_wording`,
  `test_changelog`, `test_roadmap`, `test_directory_docs`, ohne Cache und Bytecode): 329 passed,
  4 skipped, Exit 0.
- Gegenproben per Mutation (`mutplugin.py`, Mutante zur Laufzeit im Abzug) → `mut_summary.out`.
- CPU-Zeit des Rats im Wechsel alt/neu, je zwei Runden, PLA und ABS (`mess_rat.py` → `mess.out`,
  8 × Exit 0), Stückschleife und Band am Drachen (`mess_flach.py` → `flach.out`, Exit 0).
- Konfliktauflösung des welle3-Merges je Datei gegen beide Eltern verglichen.

## Befunde

### M1 (mittel) Zusatzwände unter Decken, die ringsum aufliegen
`app/core/slice/analysis.py:3301–3332` (`cantilevers`, Zählung `:3330`), Rat
`advise.py:2205–2215`, `:2272`.
Ein Überhangstück, das von einem geschlossenen Wandring umgeben ist, berührt den Rest seiner
Schicht an **einer** zusammenhängenden Linie — dem ganzen Außenring — und zählt als „hängt an einer
Seite“. Beleg `rat.out`: Kasten mit Deckel (B1, Hohlraum umschlossen, keine Stütze nötig) bekommt
`shell.overhang_walls=True «Zusatzwände halten den Überhang ohne Stütze.»`, ebenso der umgedrehte
Becher (B2) mit abgelehnten Stützen („breit 1, einseitig 1“). Beide Decken liegen ringsum auf;
richtig still bleiben die beidseitige Brücke (A1, A3), die Fensterwand (B3) und der Rahmen auf vier
Beinen (B4). Wirkung im Slicer keine: PrusaSlicer legt beide Decken mit und ohne
`extra_perimeters_on_overhangs` gleich (Brückenbahn 3 575,0 / 2 825,0 mm, `deckel.out`) — der Rat
verspricht also eine Wirkung, die es nicht gibt, und widerspricht dem eigenen Docstring
(„Eine an beiden Enden gelagerte Brücke legt der Slicer mit und ohne Zusatzwände gleich“). Das ist
die Ringform aus RM-701, hier an einer neuen Stelle. Der Pilz (Ring um den Stiel) ist richtig
einseitig: Dort berührt der **Innenring**.
*Fix:* In `cantilevers` eine Berührung, die den Außenring des Stücks bis auf Rauschen ganz
umläuft, nicht als einseitig zählen; einseitig bleibt eine zusammenhängende Berührung entlang eines
Teils des Außenrings oder entlang eines Lochs (Pilz). Test in `test_advise.py`: B1 und B2 ohne
Zusatzwände, Pilz und 3-mm-Auskragung weiter mit.

### M2 (mittel) „Wandrichtung wechseln“ an Teilen ohne steile Wand
`app/core/slice/analysis.py:3249–3288` (`steep_overhang`), Rat `advise.py:2216–2229`. Das Band
„zwischen 45 Grad und der Stützgrenze“ zählt an **jeder flachen Decke** den Streifen zwischen den
beiden Zugaben entlang ihrer Auflage mit, Breite Schichthöhe · (tan Grenze − 1), am K1 Max
0,15 mm. Beleg `steil.out` (ABS): Kasten mit Deckel 14,9 mm², umgedrehter Becher 11,7 mm², je aus
**einer** Schicht (der ersten Deckenschicht, z 12,15 / 14,15), ohne jede steile Wand — über
`OVERHANG_LAYER_MINIMUM` (10), also `shell.overhang_reverse=True «Wechselnd gedruckt rollen sich
steile Wände nicht auf.»` (`rat.out`, B1, K1 ABS). Am K1 Max und am Kobra 2 genügt eine Decke mit
rund 68 mm Auflage, am MK4S (55°) rund 117 mm — ein Gehäuse mit Deckel, das typische ABS/ASA-Teil.
Eine Rundung von 2 mm an der Unterkante (C7) löst die Umkehr über ihre ersten zwei Schichten aus
(32,6 mm²). Die 10 mm² sind als Kantengrenze **je Stück und Schicht** eingeführt und werden hier als
Summe über den ganzen Körper gelesen. Richtig: Trichter 50° 430,8 mm² über 99 Schichten, Trichter
40° und volle/offene Kästen 0.
*Fix:* Den Streifen an Überhangstücken herausnehmen (Fläche jenseits 45 Grad ohne die
Überhangflächen jenseits der Grenze, diese um Schicht · (tan Grenze − 1) erweitert) und eine steile
Wand über mehrere Schichten verlangen statt einer Summe über den Körper. Test: Kasten mit Deckel und
umgedrehter Becher ohne Umkehr, Trichter 50° weiter mit, der Bandtest von Hand bleibt.

### M3 (mittel) SuperSlicer: eine 3MF der Prusa-Familie stürzt jetzt ab, und zwei Ausschlüsse sind falsch
Nachgestellt am echten SuperSlicer 2.5.59.13 (`superslicer_console --export-gcode`, gepinnt):
- **Absturz neu.** Dateiexport `write_assembly(..., flavour="prusa", setup=None,
  for_slicer=False)`, Solidons Satz, keine Übernahme: am **alten Stand Exit 0** (75 Schichten; die
  Platte trägt nur `scarf_seam_placement` als fremden Schlüssel), am **neuen Stand `0xc0000005`**.
  Die Platte trägt jetzt zusätzlich `extra_perimeters_on_overhangs = 0`, `thick_bridges = 0`,
  `bridge_flow_ratio = 1`, `dont_support_bridges = 0`. Zerlegt (`ss2.out`, `ss3.out`): ohne
  `scarf_seam_*` Exit 0, ohne `thick_bridges` + `extra_perimeters_on_overhangs` Exit 0, mit
  Schrägnaht + `extra_perimeters_on_overhangs` Absturz — die Grenze aus RM-459 (zwei unbekannte
  Schlüssel). Dieselbe Datei mit PrusaSlicer als Programm stürzt in SuperSlicer ebenso ab
  (`teil-ps`); am alten Stand trug sie nur den einen fremden Schlüssel. Mit SuperSlicer als
  Programm (`teil-ss`) öffnet alles (Exit 0). Über die Oberfläche entsteht die programmlose
  Prusa-Datei kaum (`main_window._assembly` nimmt ohne Programm `orca`), die PrusaSlicer-Datei, die
  jemand in SuperSlicer öffnet, schon.
- **`thick_bridges` und `bridge_flow_ratio` kennt SuperSlicer** (Altschlüssel, beim Laden
  umgesetzt). Platte `thick_bridges = 0` → `bridge_type = flow`, Brückenförderung 0,0336 statt
  0,0517 mm/mm; je Objekt `thick_bridges = 1` + `bridge_flow_ratio = 0.9` → links 0,0466, rechts
  0,0336; Platte `bridge_flow_ratio = 1` steht im G-Code als `100%`, 0,9 je Objekt wirkt als 90 %
  (0,0465 gegen 0,0517). Falsch sind damit `slicer_keys.py:1193–1198` („kennt nicht“, „0,9 hieße
  dort 0,9 %“), der Docstring `test_manufacturer.py:3871–3879`, `regel-druckrat.md` (Tabelle,
  SuperSlicer-Absatz), `.claude/rules/druckrat.md:166` („Cura und SuperSlicer keinen der fünf“)
  und das Archiv. Folge für den Kunden: SuperSlicer bekommt weder Rat noch Wert für dicke Brücken und Fluss,
  und die Felder sagen „SuperSlicer kennt diese Einstellung nicht — der Wert bleibt ohne Wirkung.“
*Fix:* (a) Für eine Datei ohne bekanntes Programm die Vereinigung von `NOT_TAKEN_BY_PROGRAM` der
Familie auch auf der Platte herausnehmen (wie `_part_paths` es für `PLATE_ONLY_BY_PROGRAM` tut),
mindestens `extra_perimeters_on_overhangs`; besser `extra_perimeters_on_overhangs` auf der Platte
nur schreiben, wenn es vom Programmwert 0 abweicht. (b) `shell.thick_bridges` und
`shell.bridge_flow` aus `NOT_TAKEN_BY_PROGRAM["superslicer"]` nehmen; `shell.overhang_walls` dort
lassen oder über `extra_perimeters_overhangs` als Programmschlüssel führen, wenn gemessen. (c) Die
fünf Texte berichtigen; Slicertest SuperSlicer in
`test_the_bridge_flow_of_one_part_stays_with_that_part` aufnehmen und ein Test, dass die
programmlose Prusa-Datei in SuperSlicer öffnet (oder höchstens einen fremden Schlüssel trägt).

### M4 (mittel) „Brückenstütze abgewählt“ führt im Produkt nie zu dicken Bahnen
`advise.py:2168–2186` fragt `"support.bridges" not in declined`, `_free_flat_overhang`
(`:2252–2255`) `"support.spare_ledges" not in declined`. Der Druckdialog reicht als `declined` nur
`advise.DECIDING_PATHS` = `{"support.style"}` weiter (`print_settings_dialog.py:8107–8115`), und nur
dort fragt er nach einer Abwahl neu (`:8413`); der Export lehnt ebenso nur die Stützart ab
(`writer.py:1385`). Wählt der Kunde am Kobra 2 *Brücken stützen* ab, druckt die 36-mm-Brücke frei
(Anycubics `bridge_no_support = 1`) und dünn — der Zweig „ohne Brückenstütze → dicke Bahnen und
0,9“ ist unerreichbar. Der Test (`test_advise.py`,
`test_a_long_bridge_printed_without_support_gets_thick_lines_and_less_flow`, `unheld`) übergibt
`declined={"support.bridges"}` direkt und prüft damit, was der Kern kann, nicht was der Dialog tut.
Changelog („Bleibt eine lange Brücke ohne Stütze, schlägt Solidon dicke Bahnen … vor“) und
`druckrat.md` („ohne Brückenstütze“) versprechen den Fall.
*Fix:* `support.bridges` (und `support.spare_ledges`) in `DECIDING_PATHS` aufnehmen, damit die
Abwahl neu fragt, und im Export `declined` aus allen entscheidenden Pfaden ohne Übernahme bilden.
Test am Dialogweg (`_PlateAdviceRequest` mit abgewählter Zeile) oder über `part_advice`.

### L1 (leicht) Zwei Zweige ohne Test
Mutationen im Abzug (`mut_summary.out`), Gegenprobe je gegen die RM-587-Testauswahl:
- `kanaldecke` (dicke Bahnen über Kanaldecken bei Stützen an, `or index in need.quiet_layers`
  entfernt): 0 rot.
- `fluss_max` (`shell.bridge_flow` aus der Minimum-Liste von `_combined_value`): 0 rot.
Gehalten sind: `brueckenstuetze_gehalten` (1 rot), `split_familie` (3 rot), `einseitig_immer`
(2 rot), `rand_spannt` (1 rot), `umkehr_ueberall` (1 rot), `gegenprobe_alt` (1 rot),
`breite_egal` (1 rot).
*Fix:* Test Kanaldecke über 15 mm bei Stützen an (dicke Bahnen ja), Test `combine` zweier Körper
mit 0,9 und 1,0 (Zeile 0,9).

### L2 (leicht) Zwilling: die Umkehr fragt den Namen statt der Eigenschaft
`advise.py:2218` `flavour not in ("prusa", "cura")` sagt dasselbe wie `NOT_TAKEN_BY["prusa"]` und
`["cura"]` (`slicer_keys.py:1124–1140`); kennt PrusaSlicer die Umkehr einmal, bleibt eine Stelle
stehen (`.claude/rules/zwillinge.md`, „hinter `== "orca"` gehört ein Prädikat“). *Fix:* Eine
benannte Menge im Rat wie `AUTO_BRIM_FLAVOURS`, aus der `NOT_TAKEN_BY` liest, oder ein Wächtertest,
der beide gleich hält.

### L3 (leicht) Texte, die nicht stimmen
- Docstring `_bridges_and_overhangs` (`advise.py:2142–2145`): „als Kanaldecke oder Rand, die
  Solidon freihält“ — Schichten nur aus Rändern nimmt `long_spans` gerade heraus.
- Cura, *Fluss bei Brücken*: „Cura kennt diese Einstellung nicht“ — Cura hat einen Brückenfluss
  (`bridge_skin_material_flow`), nur auf eigene Bahnen (`UNREACHED`). *Fix:* ein Satz über
  `slicer_keys.limitation`.
- PrusaSlicer ohne Bündel druckt Brücken jetzt dünn (`thick_bridges = 0` auf der Platte, Programmwert
  1; `ss.out` zeigt den Schlüssel neu auf der Platte). Gewollt laut `regel-druckrat.md`, aber
  kundenspürbar und weder im Changelog noch im Archiv. *Fix:* ein Halbsatz im Changelog-Punkt.

## Stichprobe der Wirkungstabelle (Schwerpunkt 3)

Mit der Sonde des Bauagenten gegen `neu` nachgefahren (`gcode_runs.out`), je Ziel / Bezug:
OrcaSlicer dick 0,0461/0,0262, Fluss 0,7 0,0204/0,0262, Brückenstütze aus 0/17 912 mm,
Zusatzwände 0/335 mm, Umkehr 99/0; PrusaSlicer 0,0529/0,0443, 0,0301/0,0443, 0/22 358,
996/1 254; Bambu Studio 0,0515/0,0413, 0,0283/0,0413, 0/18 963; Cura: nichts geschrieben, beide
Teile gleich. Echter Rat (nat-frei): OrcaSlicer nur das Ziel dick und mit Zusatzwänden
(0,0461/0,0262), PrusaSlicer 0,0485/0,0468 mit 0,9. **Alle Zahlen der Tabelle bestätigt**,
geschrieben nur am Ziel.

## Falscher Rat — Prüfkörper (Schwerpunkt 1)

`rat.out`, K1 Max/Orca bzw. Kobra 2 mit `support.bridges=False`:
- 36-mm-Brücke (Korpus und nachgebaut): Stützen; ohne Stützen dicke Bahnen + 0,9; Kobra 2
  Brückenstütze „Die lange Brücke …“. Richtig.
- 36 mm mit 3-mm-Auskragung: zusätzlich Ränder frei und Zusatzwände (einseitig). Richtig.
- 8-mm-Brücke: keine Brückenwerte; Kobra 2 bekommt die Brückenstütze („Sonst lässt der Slicer
  Decken frei …“), weil Solidons Flächenregel (160 mm² > 100) Stütze verlangt — folgerichtig, aber
  damit stützt der Kobra 2 auch kurze Brücken, die Anycubic frei spannt (Beobachtung, Regel älter).
- Brücke über Loch: Kasten mit Deckel und umgedrehter Becher → M1/M2; dicke Bahnen dort richtig
  (Decke 25,5 / 36,6 mm frei). RM-701 H5 (Rohr, Flanke, Sporn): die falsche Weite 39,3 mm zieht
  jetzt zusätzlich dicke Bahnen + 0,9 (ohne Stützen) und am Kobra 2 die Brückenstütze mit „Die lange
  Brücke hängt …“ nach sich — RM-587 verstärkt RM-701 um diese Zeilen, behebt sich mit RM-701
  (Vorschlag: H5 ohne Brückenwerte in dessen Abnahme). G4 (Flanke ringsum + Steg 20) bleibt still
  wie vorher.
- Überhang ohne Brücke: Auskragung 3 mm Zusatzwände, 1 mm nichts, 8 mm mit Stützen nichts, ohne
  Stützen dicke Bahnen, 0,9 und Zusatzwände (ihre Kante von 21,5 mm zählt als Brückenweite; der
  Grund „lange freie Brücke“ ist schief, die Wirkung unschädlich); Trichter 50° ABS Umkehr, PLA und
  40° nichts.
- Teil auf Teil: Deck allein und Säulen allein bekommen nichts — der Rat je Körper sieht eine Brücke
  zwischen zwei Körpern nicht. Das gilt seit jeher auch für die Stützart (Schnitt je Körper ab
  seiner Unterkante, `writer._body_analysis`), kein Befund dieses Zweigs.
- Alle Werte aus der Geometrie: Weite gegen `SPAN_INTERESTING`, Breite gegen Wandzahl ×
  Bahnbreite, Berührung gegen die Bahnbreite; `BRIDGE_FLOW`/`BRIDGE_FLOW_ENOUGH` mit
  Recherchebeleg. Regel 7/8 nur in M2 berührt (Kantengrenze als Körpersumme).

## Übergabe je Teil (Schwerpunkt 2)

Je Familie richtig, was gemessen ist: Orca-Familie fünf, Bambu drei, Anycubic vier, PrusaSlicer
vier, Cura keiner (`dick cura`: nichts geschrieben); der Split zählt Familienlücken nicht mehr als
„nur plattenweit“ (Mutation `split_familie` 3 rot). Falsch ist SuperSlicer (M3).

## Konfliktauflösung welle3 → rm587 (Schwerpunkt 4)

Je Konfliktdatei die Änderungen beider Seiten gegen die Merge-Basis `a9e4d3f64` verglichen
(Zeilen sortiert): ROADMAP-ARCHIV, `advise.py`, `types.py`, `test_manufacturer.py`,
`test_print_settings.py` auf beiden Seiten vollständig, nichts doppelt; `slicer_keys.py` vereinigt
`NOT_TAKEN_BY["prusa"]` richtig (Präzise Außenwand, Umkehr, Baumwände); `slice/CLAUDE.md` trägt
beide Einfügungen in derselben Zeile; RM-584-Felder (`tree_walls`, Hybrid) und RM-571 unberührt.
**Kein Befund.**

## Laufzeit

Rat kalt am Drachen (650 Schichten, gespeicherter Schnitt), CPU je Runde alt/neu: PLA 96,3/95,5 und
90,9/94,6 s, ABS 92,0/89,8 und 91,2/89,9 s; warm 3,7/3,3 und 4,7/5,0 s (PLA), 1,08/1,00 und
1,11/1,08 s (ABS); 36-mm-Brücke und Würfel unter 0,1 s. Kein messbarer Mehraufwand. Am Drachen
ohne Stützen kostet die Stückschleife `_free_flat_overhang` 0,016 s (2 137 Stücke), das ganze Band
1,7 s (im Rat mit `enough` abgebrochen).

## Regeldurchgang

Regeln 1, 6, 7, 17, 20, 22 am geänderten Code geprüft: kein Qt im Kern, Fließkomma mit `EPS_GEOM`,
alle Texte über `_()`, sechs Kataloge vollständig (17 neue Schlüssel je Sprache, alter entfernt),
keine Abhängigkeit, englische Bezeichner. Regel 8 siehe M2, Zwilling L2. Kein Dateiformatsprung
nötig (neue Felder mit Vorgabe, ältere Programme übergehen sie, `dateiformat.md`). Changelog: drei
Punkte als Eigenschaft, sechs Sprachen gleich gegliedert; die Ursache von N1 liegt in jedem Tag, als
Eigenschaft formuliert ist das zulässig. Karten (`slice/CLAUDE.md`) und Regel (`druckrat.md`)
nachgezogen, Text dort zu SuperSlicer falsch (M3). Budgets §31 unberührt (Laufzeit oben).

## Urteil

**Nicht** — vier mittlere Befunde (M1–M4) und drei leichte. Nach den Fixes ist eine Nachprüfung
nötig (mehrere mittlere), eng auf `cantilevers`, `steep_overhang`, die SuperSlicer-Übergabe samt
echtem Lauf und die Abwahl im Dialog.
