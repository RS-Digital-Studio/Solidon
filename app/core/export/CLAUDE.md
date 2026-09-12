# `app/core/export/` — hinaus

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29).

Die Regeln stehen in `.claude/rules/dateiformat.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3); `default_scheme` nennt das Namensmuster, nach dem ohne eigene Angabe benannt wird — das Fenster zeigt es im Dateidialog (RM-141) |
| `threemf.py` | 3MF **schreiben** — ein Körper oder eine Baugruppe, mit Farbgruppen und Slicer-Beilagen (§20, §29). Gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1) |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt |
| `slicer_profiles.py` | Die Profile finden, die ein installierter Slicer mitbringt |

STEP geht über `brep/step.py`, nicht von hier.

Die Erhebung eingelegter Slicerfilamente nimmt einen `CancelToken` an.
Orca-Dateisuche, Namensindex und Vererbung sowie Prusa-Dateien und Abschnitte
prüfen ihn zwischen ihren Schritten; auch das Einsammeln vor dem Sortieren
bleibt abbrechbar. Ein Abbruch liefert keinen unvollständigen Profilbestand.

Der SCAD-Ausgabeweg von CLI und Bausteinkatalog läuft über
`writer.export_part_scad`: erst `activation.require(EXPORT)`, dann die
Textkonvertierung. Damit liegt er in derselben vom Manifest gedeckten Grenze
wie die anderen Exporte. `knowledge.parts.scad.to_scad` bleibt als Teil der
MIT-Bibliothek unabhängig verwendbar.

Objektbezogene Druckvorschläge werden vor der Formatwahl ausgewertet. Eine
STL-Übergabe meldet nicht übertragbare Werte als Warnung mit dem konkreten
Vorschlag; sie behauptet keine angewendete Einstellung. 3MF nennt die
tatsächlich mitgeschriebenen Abweichungen als Information.

Geometrieblöcke ersetzen ausschließlich vollständige `<mesh>`-Platzhalter.
Titel, Körper- und Materialnamen bleiben XML-maskierte Nutzerdaten, selbst
wenn sie eine der zufälligen Geometriemarken enthalten. Die Gegenprobe liest
die erzeugte 3MF wieder ein und prüft Namen, Materialien und Geometrie.

`threemf.assembly_slots()` ergänzt tatsächlich verwendete, aber nicht
deklarierte Materialplätze neutral. Export, globales Zusammenlegen und
Verbrauchsplanung benutzen diese gemeinsame Liste. Fehlende Plätze dürfen
keine bekannte Spule durch einen pauschalen Rückfall auf Werkzeug null erben.
`slots_for_object` erhält deklarierte Slots unverändert und übernimmt nur bei
vollständig fehlender Slotliste eine ausdrücklich gespeicherte alte
Körpermaterialart. Beratung und Export benutzen dieselbe Sicht; eine
vollständige Materialabwahl entfernt deshalb auch die alte Körperangabe.

Baugruppen schreiben die globale Werkzeugnummer zugleich als native
`extruder`-Objektmetadaten für Orca/Bambu und Prusa. Bemalte ganze Dreiecke
tragen `paint_color` und `slic3rpe:mmu_segmentation`; Standard-`p1` allein
wählt in diesen Slicern kein Filament. Alle drei Darstellungen benutzen
dieselbe globale Reihenfolge einschließlich der Lücken einer Teilplatte.

`bind_slot_profiles` übernimmt alte Profilpositionen an der ursprünglichen
vollständigen Szene in `slot_profile_bindings`. `configured_slots` verwendet
anschließend diese Identitäten; ein leeres gebundenes Tupel hat ausdrücklich
keine Profilwahl. Nur `None` liest noch die alte Positionsfolge. Export und
Verbrauchsplanung benutzen dieselbe Auflösung, auch nach Abwahl, Undo,
Plattenwechsel oder Auswahl-Export.

`handover.values_for` prüft sämtliche zusammengeführten Einstellungen auf
Zeilentrenner, bevor sie den gemeinsamen Weg verlassen. Damit gilt dieselbe
Grenze für Slicer-Konfigurationen und eingebettete Prusa-3MF-Einstellungen.
Nach dem Ergänzen von Profilwerten wird an der Schreibstelle erneut geprüft.

Profilvererbung wird mit sämtlichen Profilwurzeln des gewählten Slicers
aufgelöst: Nutzerprofile können von installierten Profilen erben. Diese
Wurzeln gehören auch in Filamenterkennung, Materialvergleich und Auslesen
der Werte im Druckdialog; der Ordner der Blattdatei allein reicht nicht.

Nach dem Übergang aus einem Nutzerprofil in den Herstellerbestand wird die
Familie für jeden weiteren Vorfahren neu bestimmt. Orca-/Bambu-Profile werden
in der Reihenfolge Erbbasis, `include`-Vorlagen, eigene Werte aufgelöst;
fehlende oder zyklische Vorlagen verhindern das Ausschreiben. Die Auswahl
liest Kompatibilitätsangaben auch aus unsichtbaren Erbbasen.

`profile_by_name` liefert eine native Profilidentität; bei Prusa gehört
`SlicerProfile.section` zum Pfad. `resolve_profile` löst Prusa-Bündel und
eigene INIs einschließlich Mehrfachvererbung sowie Cura-Definitionen und
Material-XML als Daten auf. Prusa-Werte bleiben INI-serialisiert, einschließlich
der literalen `\n` in G-Code. `filament_values` akzeptiert diese Profilobjekte
oder einzelne Dateien und liefert Solidon-Feldpfade. Prusa-Update-Caches
sind kein aktiver Bestand. Cura-Formeln werden nicht ausgeführt; solche Werte
bleiben unbekannt, Materialwerte ohne Maschinenkontext kommen ausschließlich
aus den allgemeinen XML-Feldern.

Die Übergabe erhält diese Identität über `profile_source` bis zum Auslesen
der Slotwerte. `profile_file` reduziert sie ausschließlich für Schnittstellen,
die tatsächlich einen Dateipfad verlangen.

`settings_for_slot` löst jede Spule gegen ihre eigene Materialart auf,
berücksichtigt mit `setup` das vollständige Herstellerprofil und legt
ausdrückliche Spulenwerte darüber. Gemeinsame Prozesswerte bleiben
erhalten. Schreiben, eingebettete 3MF-Einstellungen und Gegenprobe benutzen
dieselbe Auflösung. Eine lokale Spule anderen Typs erbt keine Startsequenzen
aus dem allgemeinen Filamentprofil des Projekts.

`SlicerConfig.written` hält die tatsächlich ausgegebenen Sollwerte, auch
Listen je Werkzeug. Die G-Code-Gegenprobe vergleicht diese Werte vollständig
und meldet keine Abweichung gegen eine überholte Projektvorgabe.
Teilbezogene Prusa-Einstellungen stehen in
`Metadata/Slic3r_PE_model.config`, Orca-Einstellungen in dessen eigener
Beilage. Ein nicht unterstützter Mehrmaterialumfang wird auch ohne manuelle
Spulenüberschreibungen vor der Übergabe benannt.

## Die vier Gegenproben nach dem Lauf

`slice_model` fragt vier Mal, ob die Druckdatei den Auftrag wirklich enthält.
Jede sieht etwas, das die anderen durchlassen:

| Prüfung | Frage |
|---|---|
| `off_the_bed` | Liegt der Druck im Bauraum? |
| `too_short` | Ist das ganze Modell darin, oder wurde unten abgeschnitten? |
| `verify_settings` | Hat der Slicer die geschriebenen Werte übernommen? |
| `spools_left_out` | Sind **alle übergebenen Spulen** gedruckt worden? |

Die vierte fragt gegen `expected_tools`, und das kommt aus
`threemf.tools_in_use` — den Werkzeugen, die die **Flächen** einer Platte
benutzen, nicht den deklarierten Slots. Ein Körper darf einen Slot tragen, den
keines seiner Dreiecke benutzt; gegen die Deklaration geprüft, meldete jeder
solche Druck eine verlorene Spule. Ohne `expected_tools` entfällt der
Vergleich, und für Familien ohne Filamentprofile je Spule schweigt sie ganz —
dort sagt `unreachable_overrides` dasselbe schon vor dem Lauf.

`crashed` trennt den abgestürzten Slicer vom ablehnenden: Beide enden ohne
Druckdatei, aber „prüfen Sie Ihr Profil" hilft bei einem Absturz niemandem.
POSIX zählt Signale negativ, Windows meldet einen `NTSTATUS` ab `0xC0000000`.

## Warum `slicer_keys.py` existiert

Weil dieselbe Einstellung in Cura, PrusaSlicer, OrcaSlicer und ElegooSlicer
vier verschiedene Namen hat. Eine Übersetzungstabelle an einer Stelle ist der
Preis dafür, dass §29 überhaupt einlösbar ist — verstreute Sonderfälle wären
es nicht.

Drei Familien decken sechs Programme ab: `prusa` (PrusaSlicer, SuperSlicer),
`orca` (OrcaSlicer, Bambu Studio, ElegooSlicer, **Creality Print** ab Version 6)
und `cura` (CuraEngine). `FLAVOUR_BY_NAME` ordnet über den Dateinamen zu;
`flavour_of` ist die einzige Stelle, an der ein Programm zu einer Familie wird.

## Der Slicer wird gerufen, nie mitgeliefert

**Keine GPL-Abhängigkeit** (Regel 15). Ein externer Aufruf ist erlaubt, ein
mitgeliefertes Binärprogramm nicht. Deshalb sucht `slicer_profiles.py`, was
installiert ist, statt etwas mitzubringen.

## Die Prüfung vor dem Export

`wants_bed_coordinates` beschreibt die ausgegebenen Maschinenkoordinaten;
`needs_bed_translation` beschreibt getrennt die Eingabe. CuraEngine versetzt
ein zentriertes STL selbst, Prusa- und Orca-Projekte erhalten versetzte Punkte.
Ein fehlgeschlagener Anordnungsversuch gilt nur für seinen Auftrag. Erst eine
ausdrückliche Ablehnung der CLI-Option wird für weitere Aufträge gemerkt.

Unbrauchbare Bett- und Sperrkonturen der Druckdatei bleiben als Warnung im
Prüfbericht. Ein gleichzeitig nachgewiesener Bauraumübertritt hat Vorrang und
trägt den Profilrückfall oder die ausgelassene Sperre als Einzelheit mit.

Curas Lüfterhochlauf bildet keine feste Zahl ausgeschalteter Schichten ab.
Der gemeinsame Exaktwert bleibt deshalb gesperrt; `setting_limitations`
benennt die abweichende Bedeutung bei der Übergabe.

Sie läuft **vorher**, nicht nachher: Wasserdichtheit, Bauraum, Wandstärken.
Was sie findet, ist ein Befund mit Handlungsvorschlag (Regel 17) — kein
abgebrochener Export.

**Zwei der fünf Fragen aus §29 stehen in keinem einzelnen Körper**, und
deshalb nimmt `check_before_export` seit dem 12.09.2026 die Szene entgegen
(RM-140): Eine verletzte Passung steht zwischen zwei Merkmalen
(`scene.fits.check`), eine Wand unter der Mindeststärke zwischen einer Bohrung
und dem Mantel um sie herum (`scene.evaluate.check_thin_walls`, RM-127). Die
Prüfung sah bis dahin nur die **Auswahl**, und damit lagen diese zwei Zeilen
des Bauplans seit je brach.

Gefragt wird an der ganzen Szene, geantwortet über die Auswahl: Eine Passung,
deren zweite Hälfte nicht mit exportiert wird, muss dennoch aufgelöst werden —
sonst käme „Merkmal verloren" zurück, und das ist eine andere Aussage. Ohne
Szene bleiben beide Fragen ungestellt; ein Aufrufer, der keine hat, bekommt
den Bericht, den er belegen kann, und keinen erfundenen (Regel 21). Der Import
liegt dafür in der Funktion — `export → scene` ist eine **träge** Kante und
steht so in `tests/test_core_package_direction.py`.

**Und `checked` nimmt einen Bericht entgegen, statt ihn zweimal zu erheben.**
Die Oberfläche prüft, zeigt, fragt und schreibt erst dann (siehe
`app/ui/CLAUDE.md`); die Prüfung ist der teure Teil, und ein zweites Ergebnis
wäre auch ein zweiter Zustand. Eine **leere** Liste ist dabei eine Antwort und
kein fehlender Wert — geprüft wird auf `None`.

## Grenzen

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.
- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).
