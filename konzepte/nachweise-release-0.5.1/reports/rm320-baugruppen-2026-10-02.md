# RM-320: Langlochzug mit getrennten Körpern und inneren Hohlschalen

Nachprüfung vom 02.10.2026 am gemeinsam bearbeiteten Quellstand nach
`4449e3370`. Dieser Bericht hält die gezielten Nachweise fest. Die zentrale
Zweitprüfung fand nach dem internen Schlussreview noch fehlenden Abbruch aus
Erkennungsarbeitern und die falsche Ablehnung einer gültigen Innenkammer mit
freiem Stift. Beide Nachgänge sind test-first korrigiert; 1010 Fachtests und
sechs Kundenrechnungen am letzten Stand sind grün. Der unabhängige Schlussreview
hat keine offenen Codebefunde. Entwicklungstor und Integration stehen noch aus.

## Fehler und Korrektur

Der exakte Langlochzug schnitt ursprünglich durch die ganze Baugruppenhülle.
Dadurch ging auch der Überstand eines zweiten Stifts außerhalb der gemessenen
Bohrung verloren. Bei mehreren Körpern begrenzen beide Kerne den Schnitt jetzt
auf die gemessene Bohrungstiefe. Ein Einzelkörper behält den Durchzug durch seine
Hülle. Die Operationsversion von `slot_hole` steigt von 14 auf 15.

Die erste Probe mit einem nur einseitig überstehenden Stift deckte den
Sicherheitsweg nicht vollständig ab: Einen beidseitigen Stift lehnte der
Netzkern weiterhin als Material in der Bohrung ab. Die neue gemeinsame Prüfung
`hole_has_separate_contents` erlaubt ausschließlich `slot_hole`, wenn der
gewählte Bohrungsträger selbst frei ist und die gesamte Baugruppe aus räumlich
getrennten, geschlossenen Materialkörpern mit gültig zugeordneten Innenhäuten
besteht. Menü und
Operation verwenden denselben Beleg; die allgemeine Frage `hole_is_clear`
behält ihren bisherigen Vertrag.

## Gegenfälle aus dem unabhängigen Review

Ein reiner Komponentenbeleg genügte nicht. Acht Gegenfälle aus Flächenkontakt
oder Überlappung, Netz oder exaktem Kern und mit oder ohne weiterem Körper
ließen eine angeschlossene Nabe fälschlich zum Schnitt zu. Der korrigierte
Beleg nutzt die vollständige vorhandene Kontaktprüfung:
`include_face_contacts=True`, `max_pairs=None`, `require_complete=True`.
Kontakt, Überschneidung oder ein unvollständiger Suchbeleg verweigern die
Sonderfreigabe. Die acht Nabenfälle werden vor einer Geometrieänderung mit
`HOLE_IS_NOT_EMPTY` abgewiesen; ihre Menüzeilen bleiben gesperrt.

Ein weiterer Gegenfall zeigte einen zu kurzen Netzschnitt an einem einzelnen
Körper mit geschlossener innerer Hohlschale. Die Netzentscheidung zählt jetzt
positive Außenkörper über die stabile Rechnung `signed_volume`; eine negative
Innenhaut erzeugt keinen zweiten Körper.

Der Gegenkörper besteht aus einer Grundplatte 40 × 20 × 10 mm, einem Aufsatz
10 × 20 × 10 mm und wahlweise einem inneren Würfel 4 × 4 × 4 mm. Der Prüfpunkt
(5,5; 0; 15) mm muss nach dem Langlochzug außerhalb liegen. Das unabhängige
Sollvolumen ist

`10000 − (36 + 9π)·10 − (9·acos(2/3) − 2·sqrt(5))·10`,

mit Innenwürfel zusätzlich minus 64 mm³. Die Abnahme nutzt 1e-6 mm³ am exakten
Kern und 2 mm³ am facettierten Netz.

Die neun neuen Gegenfälle waren vor der Korrektur rot. Zusätzlich prüfen die
Regressionen Abbruch vor und während der Komponentenprüfung, die Weitergabe
des Tokens an die Kontaktprüfung, einen bereits abgebrochenen Cachetreffer,
das Ausbleiben eines unvollständigen Merkers und dessen Entwertung nach einer
Geometrieänderung. Der Beleg wird über genau einen neuen Schlüssel in
`SHARED_ANSWERS` zwischen Menü und Ausführung geteilt.

### Zweiter Nachgang: vollständige Einschließung

Der erneute unabhängige Review fand einen weiteren Fehler: Ohne Schnitt der
Oberflächen kann ein positiver Körper vollständig im Material eines anderen
liegen. Eine innere Platte 40 × 20 × 10 mm von z = 0 bis 10 mm mit Ø6-Durchgang
liegt im größeren Körper 60 × 40 × 20 mm von z = −5 bis 15 mm mit koaxialem
Ø4-Durchgang. `parts_that_cross` liefert vollständig geprüft keinen Treffer,
während `parts_inside_parts` genau eine Materialeinschließung erkennt.

Die Sonderfreigabe bot diese Bearbeitung trotzdem in beiden Menüs an und ließ
sie an beiden Kernen in `draft` und `fine` durch. Alle sechs Gegenfälle waren
vor der Korrektur rot. Zwei unentschiedene Strahlenfälle und ein Abbruchfall
wiesen zusätzlich nach, dass die bisherige Diagnoseliste als Freigabe nicht
ausreichte.

`repair.has_nested_parts` verwendet die vorhandenen Schalen- und
Vorzeichenfragen und antwortet jetzt ausdrücklich mit `True`, `False` oder
`None`. Nur das entschiedene `False` erlaubt die Sonderfreigabe. Die
Diagnose `parts_inside_parts` teilt über `_part_containment` dieselbe Rechnung,
behält aber ihre bisherige Auswahl und Signatur. Ein freier kurzer Stift von
z = 2 bis 8 mm in der tatsächlichen Luft der Bohrung bleibt an beiden Kernen
mit Ø2 und Ø5 zulässig. Negative Innenhäute und freie Teile in einem Innenraum
werden getrennt von positiv eingeschlossenem Material geprüft.

Der abschließende Review fand noch einen fehlenden Abbruchcallback im
vorhandenen Gitterzertifikat `_shells_do_not_cross`. Der neue Gegenfall war
vor dem Fix rot und verlangt den Abbruch bei der zweiten tatsächlichen
Prüfstelle innerhalb des Zertifikats. Mit weitergereichtem
`check_cancelled=self._check_cancelled` bestehen alle sieben gezielt gewählten
Abbruch- und Merkerfälle. Der Reviewer hat diesen Fix und die übrigen
RM320-Kernhunks ohne offenen Befund geprüft.

### Tatsächliche Erkennungsarbeiter und Speichergrenze

Die bisherigen Abbruchgegenfälle erreichten den Helfer direkt mit einem
Token. Die tatsächlichen Arbeiter verloren den Abbruch vor dem vollständigen
Beleg: Der örtliche Weg reichte seinen Token nicht an `actions_for` weiter;
`_FeatureAnswersWorker` besaß keinen eigenen Abbruchschalter. Vier echte
Aufrufketten durch Kontakt- und Einschließungsprüfung sowie Ersatzauftrag
und Fensterende waren deshalb rot.

`actions_for` und `feature_answers` nehmen jetzt einen optionalen Token an.
Der örtliche Arbeiter reicht seinen vorhandenen Schalter durch. Der
Panelarbeiter und die tatsächlich gestartete Rechnung an der gesperrten
Arbeiterkopie teilen denselben Schalter. Ersatzauftrag und `wait_for_workers`
brechen die Rechnung ab. `OperationCancelled` erzeugt weder ein veraltetes
Ergebnis noch einen Fehlerbericht.

Zwei weitere rote Gegenfälle betrafen die Speichergrenze: Ein unmittelbar
nach der Rechnung gesetzter Abbruch wurde erst bemerkt, nachdem die Antwort
bereits gespeichert war. `remembered` prüft seinen vorhandenen Callback nun
auch direkt nach `compute()` vor dem Speichern; der RM320-Helfer gibt diesen
Callback mit. Beide tatsächlichen Arbeiterwege belegen fehlende Ausgabe und
fehlenden Merker nach Abbruch, eine neue Berechnung beim Wiederholen und die
Ablehnung eines schon abgebrochenen Cachelesers. Alle acht Fälle bestehen.

Diese Nichtfensterprüfungen führen die echten Arbeitsrümpfe aus. Beim örtlichen
Weg sind bereits vorhandene Auswertung und Regionsauswahl vorbereitet; beim
Panel sind Fensterträger und Threadstart ersetzt. Kontakt-, Einschließungs-,
Merker- und Signalwege laufen durch den Produktcode. Das belegt den Anschluss,
keine native Fensterbedienung oder Wartezeit.

### Gültige Innenkammer zusammen mit einem freien Stift

Eine weitere Probe ergänzt die Platte mit einer geschlossenen Kammer von
4 × 4 × 4 mm um (12; 0; 5) mm. Die Kammer liegt außerhalb von Bohrung,
Langlochwerkzeug und freiem Stift. Der bisherige Beleg verlangte dennoch
positive Orientierung jeder einzelnen Schale und verweigerte diese gültige
Baugruppe. Sechs Gegenfälle waren rot: Menü sowie `draft` und `fine`, jeweils
am Netz und am exakten Kern.

`repair.material_part_families` liest die vorhandenen Beziehungen aus
`_Shells.containers_of`, einschließlich ihrer Strahlen-, Zertifikats- und
Kreuzungssuche mit demselben Abbruchtoken. Jede Beziehung muss entschieden
sein. Der unmittelbare Elternteil muss eine konsistente Vorfahrenkette
bilden: Wurzeln sind positiv, entlang der Kette wechseln die Vorzeichen.
Negative Wurzeln, gleichgerichtete Eltern und Kinder oder unbekannte
Beziehungen sperren die Freigabe.

Eine Materialfamilie enthält die positive Haut und ihre direkten negativen
Innenhäute. Positive Materialinseln in Hohlräumen bleiben eigene Körper.
Der Langlochbeleg prüft vorher weiterhin Dichtheit, Orientierung und
vollständige Kontaktfreiheit aller Häute. Die Bohrung wird anschließend am
vollständigen Träger einschließlich seiner Innenhäute geprüft.

Der Ausgangskörper und beide Stiftreste haben dieselben hergeleiteten
Außenvolumina wie in der folgenden Tabelle. Nur das Materialvolumen der
Platte sinkt um 64 mm³. Das unabhängige gesamte Sollvolumen ist

`8000 − 64 − (36 + 9π)·10 + π·2,5²·15 mm³`.

Die Toleranz beträgt 1e-6 mm³ am nativen Körper und 4 mm³ am Netz für Sehnen
und Endzugaben. Der exakte Kern enthält drei Solids; das Netz enthält drei
positive Materialkörper und eine vierte Schale als Innenhaut mit −64 mm³.
Die Stiftenden bleiben 5 und 10 mm hoch. 19 Familien-/Kammer-/Abbruchfälle
und ein getrennt ausgewählter Lauf mit 30 neuen und bisherigen
Sicherheitsgegenfällen bestehen. Die beiden Mengen werden nicht addiert.

## Analytischer beidseitiger Stift

Platte 40 × 20 × 10 mm, Bohrung Ø 6 mm, Langloch 12 × 6 mm, getrennter Stift
Ø 5 mm von z = −5 bis 20 mm. Nachher müssen drei wasserdichte Teile und genau
ein Langloch vorliegen. Die Eingangskoordinaten und Dreiecke bleiben unverändert.

| Teil | Unabhängiges natives Sollvolumen |
|---|---|
| Unterer Stiftrest, 5 mm hoch | π·2,5²·5 = 98,174770424681 mm³ |
| Oberer Stiftrest, 10 mm hoch | π·2,5²·10 = 196,349540849362 mm³ |
| Platte | 8000 − (36 + 9π)·10 = 7357,256661176919 mm³ |

Die native Volumentoleranz beträgt 1e-6 mm³. Am Netz liegen die Restgrenzen bei
z = −5 bis −0,01 mm und z = 10,01 bis 20 mm; die Axialprüfung erlaubt 0,02 mm.
Sehnenzug und Endzugabe erklären die getrennt geprüften Netzabweichungen.
Die gemessenen Stiftvolumina 97,6 und 195,4 mm³ am Netz beziehungsweise 97,8
und 195,6 mm³ an der B-Rep-Tessellierung sind keine nativen Sollwerte.
Die ursprüngliche einseitige Probe, ein fremder 20-mm³-Klotz hinter der
Bohrung und der bisherige Einzelkörperweg bleiben ebenfalls abgedeckt.

## Unveränderte Kundenmodelle

Die Dateien wurden aus dem lokalen Kundenkorpus gelesen und nicht verändert:

| Datei | SHA-256 |
|---|---|
| `carpet-corner-clip.step` | `b551014308ba413a1142181f7cf5d0d183ad1f088305a674ceeed5c83164af4b` |
| `broomholdervcd_d35mm.stl` | `0cfeea3ff0fe897fcd2ed69e82749411c30c69515a5dd7437cb3d6fb3a74baab` |

Jeder der folgenden Fälle wurde in `draft` und `fine` gerechnet, insgesamt
sechs erfolgreiche Rechnungen:

| Fall | Änderung | Volumen vorher → nachher | Ergebnis |
|---|---|---|---|
| Teppichclip, exakt | Länge 15,5 → 17,5 mm | 9115,968705 → 9089,510230 mm³ | dicht, zwei Körper, ein Langloch, keine Befunde |
| Teppichclip, Netzzwilling | gemessene Länge 15,505582 → 17,505582 mm | 9114,314669 → 9065,302452 mm³ | dicht, zwei Körper, ein Langloch, Solver `direct` |
| Besenhalter, Netz, `hole_5` | Ø 6,120001 → Länge 8,120001 mm | 40473,781544 → 40201,168640 mm³ | dicht, drei Körper, ein Langloch, ausgewiesener Solver `welded` |

Die Verlängerung folgt jeweils dem gemessenen Ausgangswinkel. Die erste
Teppichclip-Sonde hatte irrtümlich den Vorgabewinkel 0° statt der gemessenen
90° benutzt; ausschließlich der korrigierte Lauf begründet diese Tabelle.
Der reguläre Ersatzweg am Besenhalter bleibt als `boolean.welded` sichtbar.

## Prüfung und Wiederholung

- Der letzte betroffene Lauf vor diesen beiden zusätzlichen Nachgängen über
  `python tools/affected_tests.py tests/test_slot_features.py tests/test_repair.py --run`
  bestand mit **569 Tests in 30,90 s**, Exit 0. **Drei Fälle wurden abgewählt**.
  Der Lauf umfasst Reparatur, Langlöcher, Rundflächen und Flächenträger.
- Die Nachgänge ergänzten gegenüber dem übernommenen Arbeitsstand 48
  Langlochfälle und neun Reparaturfälle. Frühere Auswahlmengen mit 373
  beziehungsweise 568 bestandenen Tests gehören zu
  Zwischenständen und werden nicht zur Schlusszahl addiert.
- Drei vorhandene Boolean-Einschließungsfälle und 417 Sprachprüfungen
  bestanden zusammen mit **420 Tests**, Exit 0. Vier vorhandene globale
  Sicherheits- und Merkerverträge waren ebenfalls grün.
- Ruff und Format der sechs betroffenen Python-Dateien sowie mypy der vier
  Produktmodule bestanden. Nach der letzten Callbackkorrektur wurden die
  beiden geänderten Dateien erneut mit Ruff und Format und `repair.py` erneut
  mit mypy geprüft: jeweils Exit 0. Der Diffcheck war ohne Befund.
- Die OCP-Verfügbarkeit wird vor der gemeinsamen B-Rep-Fixture geprüft;
  auch ihre Netzzwillinge werden ohne dieses Extra sauber übersprungen.
- Nach dem Arbeiter- und Kammerfix bestanden acht tatsächliche
  Arbeiteranschlussfälle, 19 Familien-/Kammer-/Abbruchfälle und der Lauf mit
  30 Sicherheitsgegenfällen. Ruff und Format über zehn Python-Dateien sowie
  mypy über sieben Produktmodule bestanden.
- Der erneute betroffene Lauf nach diesen Korrekturen bestand mit **1010
  Tests in 122,52 s**, Exit 0. **708 Fälle blieben abgewählt**. Die neun
  Nichtfensterdateien sind `test_feature_panel`, `test_features`,
  `test_local_recognition_flow`, `test_local_recognition_ui`, `test_repair`,
  `test_round_surface_measurements`, `test_slot_features`,
  `test_surface_patches` und `test_ui`. Damit sind auch die vorhandenen
  Merker-, Kopier-, Lebensdauer-, Invalidierungs- und Abbruchverträge geprüft.
  Die früheren Fachzahlen werden nicht zur abschließenden Menge addiert.
- Alle sechs Kundenrechnungen wurden danach am eingefrorenen Endstand
  wiederholt, Exit 0. Die oben genannten Volumina, Körperzahlen, Dichtheit,
  Langlocherkennung und ausgewiesenen Solver bleiben bestätigt.
- Der abschließende unabhängige Review hat die vollständigen RM320-Hunks
  einschließlich Materialfamilien, tatsächlicher Arbeiter, Signalwegen und
  Speichergrenze ohne offene Codebefunde freigegeben. Gegen HEAD enthält die
  Einheit 64 neue RM320-Langlochfälle, 16 Reparaturfälle und acht
  Arbeiteranschlussfälle. Frühere Zahlen zusätzlicher Fälle beziehen sich
  ausdrücklich auf den damals übernommenen Zwischenstand.

Für den echten Modellweg werden STEP-Dateien über `brep.step.read`, STL über
`read_mesh` gelesen. Der Netzzwilling entsteht aus `as_mesh_data`; Erkennung
und Menüfreigabe bestimmen die bearbeitbare Öffnung. Die registrierte Operation
`slot_hole` erhält deren `at_feature`, die gemessene Länge plus 2 mm und den
unveränderten Winkel aus `slot_angle_of`.

## Grenzen

Die Sonderfreigabe lehnt konservativ auch Kontakt zwischen zwei anderen
Komponenten der Baugruppe ab. Die Tiefenentscheidung setzt korrekt orientierte
Eingangsgeometrie voraus. Der erste Menüaufruf ohne Token berechnet den Beleg
synchron; Folgeaufrufe verwenden den Merker. Daraus wird kein Leistungsnachweis
abgeleitet.

Ein echtes Kundenmodell mit genau dem konzentrischen beidseitigen Fremdstift
lag für diese Prüfung nicht vor; hierfür stehen die analytischen Zwillinge.
Fenster-, Renderer- und Leistungsprüfungen wurden nicht ausgeführt und bleiben
Release-Abnahmen. Die früheren unabhängigen Reviews fanden die dokumentierten
Geometrie- und Abbruchfehler im Kern; diese sind test-first korrigiert. Der
interne unabhängige Nachreview war ohne offene Befunde. Die danach zentral
gefundenen Aufrufer- und Innenhautreste sind korrigiert, durch den erneuten
Fachlauf belegt und im unabhängigen Schlussreview ohne offene Codebefunde
freigegeben.
Das vollständige Entwicklungstor und der tatsächliche Commit/Push stehen
für RM320 ebenfalls noch aus.
