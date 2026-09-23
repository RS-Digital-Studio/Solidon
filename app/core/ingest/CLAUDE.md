# `app/core/ingest/` — die Eingangsstufe

Jede geladene Datei geht dieselben sechs Schritte (§17.1). Was danach in der
Szene liegt, ist normalisiert — der Rest der Anwendung muss nicht mehr wissen,
woher es kam.

Die Regeln stehen in `.claude/rules/dateiformat.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `loader.py` | Die Eingangsstufe selbst — die sechs Schritte; lokale GLTF-Begleitdateien werden sicher eingebettet. `read_model` liest eine Datei aus dem Speicher als einen Körper (3MF als Baugruppe verschweißt), `READABLE_SUFFIXES` ist **die** Liste dessen, was sich öffnen lässt |
| `threemf.py` | 3MF **lesen** — Objekte, Farbgruppen, erklärte Einheit, Baugruppe mit Production-Erweiterung (§17.1, §20). Bis zum 02.09.2026 lag der Leser beim Schreiber in `export/`; die Konstanten des Containers stehen hier, `export/threemf.py` holt sie sich |
| `ops.py` | Die `load`-Operation. **Auch Laden ist eine Operation** und steht im Stapel |
| `step_ops.py` | Die `load_step`-Operation: eine STEP-Baugruppe als unabhängige exakte Körper mit Weltlage, Namen und Filamentslots aus den Flächenfarben (P7.4). Sie liest mit `brep.step` und wohnt hier, weil nur `ingest → brep` erlaubt ist, nicht umgekehrt |
| `plan.py` | Welche Operation eine Datei einliest — für Fenster und Kommandozeile; `names_in_use` nennt die im Stapel vergebenen Objektnamen, damit der Plan einen freien wählt; `is_only_imported` sagt umgekehrt, ob ein ganzes Dokument nichts als eingelesene Dateien trägt (RM-130). Eine STEP-Datei liest der Plan als Baugruppe (`BodyChoice`, `with_selection`, P7.4) |
| `fetch.py` | Eine Modelldatei aus dem Netz holen (§16.3, §32); eine Adresse von Printables, Thingiverse, MakerWorld, Cults3D, MyMiniFactory oder Thangs ohne Dateiendung ist eine Seite und wird ohne Netzzugriff mit dem Weg über den Herunterladen-Knopf beantwortet (`model_page_host`) |
| `archive.py` | Ein ZIP mit Modellen **vor** dem Einbetten auflösen: nur das Modell kommt ins Projekt, bei mehreren wird gefragt; dieselben Grenzen wie beim 3MF, Pfadtricks übergangen, GLTF-Begleitdateien aus demselben Archiv. `IMPORT_SUFFIXES` ist die Liste für Dateidialog, Ablage, Netz und Kommandozeile; `plan.MODEL_SUFFIXES` bleibt die der Operationen |
| `outline.py` | SVG/DXF-Profile mit Innenringen lesen, prüfen, auswählen und extrudieren; SVG-Standardwerte für fehlende Rechteckpositionen werden nur in der Parserkopie ergänzt |

## Warum Laden eine Operation ist

Weil die Auswertung sonst keine reine Funktion wäre. Die Datei ist eine
Quelle, der Ladeschritt steht im Stapel, und ein Projekt lässt sich später
gegen eine geänderte Quelle neu rechnen.

## Was die Stufe entscheidet

`plan.imported_group` bestimmt die vollständigen lebenden Ausgaben eines
unveränderten mehrteiligen Imports. Jede spätere Verwendung eines Mitglieds
beendet dieses Angebot konservativ. Auswahl und frühere Szenenobjekte gehören
nicht zum Umfang; Importkoordinaten bleiben erhalten. Gemeinsames Aufsetzen
ist die getrennte Operation `place_group_on_bed` und bleibt einzeln rücknehmbar.
`plan.imported_group_for_bed` prüft zusätzlich die aktuellen Körpergrenzen:
Liegt die tiefste Unterseite innerhalb `EPS_DISPLAY` auf dem Bett, bleibt am
schwebenden Mitglied die wirksame Einzelhandlung. Ein gemeinsamer Schritt mit
Nullwirkung ersetzt sie nicht.

- **Einheiten**: STL trägt keine. Erkannt wird aus der Größe, und bei
  Mehrdeutigkeit **wird gefragt** (`ctx.ask`, Regel 21) — nicht geraten.
- **Offene Stellen werden geschlossen, nicht gemeldet.** `normalise` ruft
  `geom.repair.repair` (ohne die Schritte, die es selbst schon gefahren hat),
  sobald ein verschweißtes Netz nicht dicht ist: verzweigte Kanten auflösen,
  Sanduhr-Ecken auftrennen, Ränder vernähen, Ringe schließen. Am Korpus
  `F:\3D Dateien` gehen damit 118 von 484 Körpern geschlossen heraus, die
  offen hereinkamen, und keiner bleibt offen. Die Befunde der Reparatur reisen
  in denselben Bericht; die Regel und ihre drei Sätze stehen in
  `.claude/rules/dateiformat.md`.
- **Dieselbe Schale zweimal** (`loader._without_doubled_shell`): Reißt das
  Verschweißen ein geschlossenes Netz auf, weil eine Kopie derselben Schale
  mit eigenen Ecken daneben liegt, bleibt von deckungsgleichen Dreiecken das
  erste, wenn das Netz danach dicht ist (`ingest.doubled_shell_removed`,
  unter `remove_degenerate`). Sonst wird das Verschweißen zurückgenommen wie
  bisher (`ingest.weld_skipped`) — zwei Körper, die sich nur berühren, bleiben
  zwei.
- **Dichtheit wird gefragt, wenn die Antwort gebraucht wird**, und am Stand,
  der gilt: erst am verschweißten Netz, am unverschweißten nur, wenn das
  Verschweißen es aufgerissen hat; das zurückgelegte Netz behält seine
  Antwort. `tests/test_ingest_figures.py` zählt die Fragen.
- **Dichtheit und Umlaufsinn reisen als Paar.** trimesh berechnet beide über
  dieselbe Topologieprüfung. `normalise` bewahrt vor Aufsetzen oder Zentrieren
  beide Antworten und legt sie danach gemeinsam zurück; ein halber Cache
  verhindert die fehlende Auskunft beim nachfolgenden booleschen Schnitt.
- **3MF ist eine Baugruppe**, kein Körper. Sie kommt als mehrere Objekte an.
- **STEP ist es auch** (P7.4). Der Plan liest die Datei über
  `brep.step.read_assembly`, schreibt die Kennungen aller Körper in
  `load_step.bodies` und legt die Liste als `ImportPlan.choices` daneben;
  das Fenster lässt daraus wählen (`with_selection`), bevor der Schritt
  entsteht. Die Zahl der Ausgänge steht damit vor der Operation fest (§11),
  wie bei der 3MF. Beim ersten Modell kommen `place_on_bed` und `centre`
  dazu — die Baugruppe geht als Ganzes aufs Bett, als Lage an der Form, der
  Körper bleibt exakt. Lässt sich die Baugruppe nicht auflösen, wählt der
  Plan `*`: ein Körper über den alten Leser, und der Schritt meldet, dass
  Namen und Farben fehlen.
- **Gleich benannte ZIP-Einträge** prüft `loader.check_unpacked` erst nach
  sämtlichen Archivgrenzen blockweise auf bytegleichen Inhalt. Alle Kopien
  zählen zu Anzahl und Entpackgröße; nur identische Inhalte sind eindeutig.
  Die Originalquelle bleibt unverändert. Größen- und CRC-Gleichheit allein
  genügen nicht, unlesbare oder widersprüchliche Dubletten werden abgewiesen.
- **Native 3MF-Farben**: Werkzeugpaletten aus Orca/Bambu-Projektmetadaten
  oder Prusa-Konfiguration, Objektwerkzeuge, objektspezifische Part-Werkzeuge
  und bemalte Dreiecke werden als Materialslots übernommen. Prusa-Volumen
  behalten ihre Dreiecksbereiche. **Teilflächenbemalung wird gelesen, nicht
  vergröbert**: `_decode_paint` liest den Bitstrom von
  `TriangleSelector::serialize` (PrusaSlicer, Bambu Studio, Orca), und
  `_refine` teilt die Dreiecke so, wie der Slicer sie beim Malen geteilt hat,
  Mittelpunkte über beide Seiten einer Kante geteilt, T-Stöße zu ungeteilten
  Nachbarn geschlossen. Was sich an Farben nicht lesen lässt, hält den Import
  **nicht** an (Entscheidung Robert, 14.09.2026): Der Körper kommt
  einfarbig, der Grund steht als Befund `ingest.colours_dropped` im
  Prüfbericht — je Körper, nicht je Datei; eine unlesbare Palette meldet
  `ingest.palette_dropped` für alle. **Der Rat dazu steht im Satz**, nicht
  in `suggestions`: Der Prüfbericht zeigt nur Handlungen mit Handler, und für
  „im Slicer nach Filamenten aufteilen" gibt es keinen. Ein Bemalungscode
  tiefer als `MAX_PAINT_DEPTH` ist ein Befund, kein `RecursionError`.
- **Was der Slicer außer druckbaren Teilen in ein Objekt legt**: Modifikator,
  Stützblocker und Stützverstärker (`HELPER_KINDS`) sind keine Geometrie des
  Drucks und werden übersprungen (`ingest.helper_skipped`); eine Aussparung
  (`negative_part`) wird von jedem druckbaren Teil ihres Objekts abgezogen
  (`ingest.negative_carved`), über die Rückfallkette des Kerns; die Stufe
  steht am Befund und als `Part.solver` am Körper, die `load`-Operation
  meldet die tiefste aller Körper (§17.2). Eine Art, die keiner kennt, ist
  ein Körper — geladen und gezählt, mit `ingest.unknown_part_kind` daneben.
  Der Zählweg (`_scan`) und der Leser fragen dasselbe Prädikat `_is_body` —
  die Körperzahl steht fest, bevor gerechnet wird (§11). **Das gilt für
  Bambu, Orca und Elegoo** (`subtype` in `model_settings.config`);
  PrusaSlicer führt Modifikator und Aussparung als `volume` im selben Netz,
  und dort wird nichts abgezogen: Der Körper kommt einfarbig, und
  `ingest.foreign_volume` sagt, dass der Bereich als Material geladen ist.
  Bleibt danach kein druckbarer
  Körper, ist das eine Absage (`no_printable_part`) und keine leere Liste:
  Leer hieße für `load` „keine lesbare 3MF", und der allgemeine Leser lüde
  die Aussparung als Körper.
- **`model_settings.config` wird ohne Namensräume gelesen** (`_slicer_config`):
  Bambu Studio und der Elegoo-Slicer schreiben ein SVG-Relief als
  `<slic3rpe:shape …/>` ohne den Präfix je zu deklarieren.
- **GLTF darf Begleitdateien haben.** Beim lokalen Import werden Puffer und
  Bilder aus demselben Ordner eingebettet; Verweise aus dem Ordner heraus
  bleiben gesperrt.
- **Neue GLB-/GLTF-Importe speichern `coordinates="gltf"`.** `load` dreht
  die bereits vom Leser angewandten Knoten aus Y-oben nach Z-oben und liest
  die Formateinheit Meter. Eine ausdrücklich gesetzte Einheit geht vor.
  **Meter sind eine Vorschrift des Formats, keine Aussage der Datei**
  (`_a_format_convention`): Ist die Meter-Lesart am Modell nicht plausibel
  (`PLAUSIBLE_MIN_MM` bis `plausible_reach`), fragt `_unit_for` mit Meter als
  erster Antwort und den plausiblen Lesarten daneben — ein Generator wie
  TripoSG schreibt seinen Einheitswürfel in die Datei, und als Meter gelesen
  war Roberts Drache 1,9 m hoch (20.09.2026). Die 3MF-Einheit bleibt davon
  unberührt; sie steht als Attribut in der Datei.
  `legacy_raw` erhält alte importierte und erzeugte Quellen; der Rohleser
  ändert sie nicht. Eine **neu erzeugte** GLB (`generate.into_project`)
  speichert `gltf` mit der Einheit `mm`: Sie steht auf glTF-Achsen, aber in
  keinen Metern. Die Zielgröße eines Generatormodells bleibt der eigene
  Schritt `fit_to_size` und wird nicht in die Einheitenumrechnung eingerechnet.
- **Herkunft** wird vermerkt (`scene/foreign.py`, §32): Der Nutzer soll
  wissen, woher der Inhalt stammt.
- **Wie der Körper heißt**, entscheidet der Plan und nicht die Auswertung:
  Trägt der Stapel die Datei schon, bekommt der neue Ladeschritt eine Nummer
  (`copy`, „plate_holes (2)", `plan.copy_name`). Die Nummer steht im Schritt,
  nicht im Namen, und gilt **jedem** Körper, den die Datei bringt — auch den
  Teilen einer Baugruppe, die ihre Namen aus der Datei mitbringen: Sonst stand
  der Siebhalter zweimal mit sieben gleichen Zeilen im Baum. Ein Einzelteil
  ohne eigenen Namen heißt nach der Datei. Gefragt wird der **Stapel**, nicht
  die gerechnete Szene — dieselbe Entscheidung wie bei `first_model`, und aus
  demselben Grund (§15.1): Sonst hinge der Name daran, was gerade sonst in der
  Szene steht, und dieselbe Datei käme beim nächsten Öffnen anders herein.
  Ältere Schritte mit „Name 2" im `name`-Parameter zählen beim Nummerieren
  mit.

## Grenzen

- **Konturauswahl ist ein Operationswert.** `read_profiles` liefert geometrisch
  stabile Kennungen samt Außen- und Innenringen; `load_outline.contours` speichert
  eine JSON-Liste dieser Kennungen. Eine leere Liste oder unbekannte Kennung
  hält an. Nur der historische leere Text übernimmt unverändert alle Profile,
  einschließlich ihrer bisherigen Extrusion. Neue ausdrückliche Auswahlen
  verlangen geschlossene Körper. `profile_reason` prüft denselben Rechenweg
  für die Vorschau; unbrauchbare Profile bleiben mit Grund sichtbar.
- **Vorschau und Operation teilen `extrude_profiles`.** Die Zielbreite skaliert
  die ausgewählten Profile zusammen in X/Y, bewahrt ihre relative Lage und
  ändert die ausdrücklich angegebene Höhe nicht. Löcher bleiben beim Profil.

- Ein Fehlerbild wird eine **Testdatei** in `tests/data/`, kein Sonderfall im
  Code.
- Nichts aus einer geöffneten Datei wird ausgeführt (Regel 13).
- Modelldownloads laufen immer über `fetch._open_download` und die gemeinsame
  HTTP-Grenze: geprüfte Weiterleitungen, Gesamtfrist einschließlich Headern
  und eine begrenzbare Leseantwort. Tests ersetzen nur den Transport; einen
  öffentlichen Umgehungsparameter gibt es nicht.
