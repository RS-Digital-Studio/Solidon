# RM-284: Exakte Rundungsgruppen und belegte Merkmalsfortführung

Nachprüfung vom 02.10.2026 am gemeinsam bearbeiteten Quellstand nach
`4449e3370`. Fachliche Nachweise und Eigenreview sind abgeschlossen.
Die Cacheversionen sind nach der RM225-Integration eingetragen. Die
Identitätsbefunde im automatischen Anschluss und nach ausdrücklicher
Merkmalswahl sind mit roten Gegenfällen korrigiert. Der erneute Fachlauf
bestand mit 1209 Tests. Eine danach zentral gefundene automatische Antwort
in zwei Verlaufstests ist entfernt und mit unabhängiger Sensitivitätsprobe
abgesichert; 13 gezielte Fälle bestehen. Ein weiterer Anschlussfix erhält
verschiedene Fundstellen im Abschlussbericht und besteht mit 21 gezielten
Fällen. Die unabhängigen Schlussreviews haben keine offenen Befunde.
Das vollständige Entwicklungstor ist grün. Die Einheit ist seit dem
02.10.2026 mit `57848fa72` auf `main` und `origin/main` integriert;
der Abschlussbeleg steht unten.

## Gruppenbildung und Rückmeldung

`fillet_group` versucht zunächst die ganze geometrisch zulässige Auswahl.
Kann der exakte Kern diese Gruppe nicht sicher bauen, prüft er gezielte
Auslassungen. Jede neue Kantenkombination wird höchstens einmal gerechnet;
bereits geprüfte Kombinationen werden wiederverwendet. Zusätzlich ausgelassene
Kanten bleiben scharf und werden mit ihrer Lage gemeldet. Die direkte exakte
Einzelwahl und der veränderliche Radius behalten ihren strengen Vertrag.

Die Meldung über eine zusätzlich ausgelassene Kante ist in allen fünf
Übersetzungskatalogen vorhanden. Auslassungen wegen einer zu schmalen Wand
behalten ihre getrennte Begründung.

## Drei reproduzierte Reviewfehler

1. Eine native Kopie kann die Kantenreihenfolge ändern. Die Gruppe verwendete
   bisher die Nummern des Originals an der Kopie und rundete dadurch eine
   andere Kante. Jetzt führt `_edges_for` jede Auswahl über die tatsächliche
   Kopierhistorie nach. Die Regression verwendet eine echte Umordnung.
2. Mehrere Kandidaten verwendeten dieselbe native Form. Jetzt beginnt jeder
   noch nicht geprüfte Kandidat mit einer frischen Kopie; die Regression
   vergleicht die nativen Formen der Bauversuche.
3. Bei fehlender Flächenhistorie wurde eine allgemeine geometrische Zuordnung
   als belegte `FeatureContinuation` ausgegeben. Die Fortführung setzt nun
   einen nichtleeren Flächenbeleg mit genau einem passenden Merkmal voraus.
   Ohne Beleg oder bei Mehrdeutigkeit bleibt die allgemeine Auswertung
   zuständig. Zwei Radiusänderungen hintereinander prüfen den tatsächlichen
   Anschluss an die nächste Operation.

Vor der Korrektur waren drei der fünf direkten Gegenfälle rot; danach
bestanden alle fünf.

### Anschluss nach der Merkmalsfortführung

Der unabhängige Schlussreview fand eine Kennungskollision im nachfolgenden
`_unchanged_continuations`-Schritt: Dessen Teilzuordnung an `apply_mapping`
reservierte belegte Selbstzuordnungen nicht. Die neue Rundung erhielt dadurch
die Kennung der ausdrücklich fortgeführten Rundung, die selbst umbenannt wurde.

Der Gegenfall verwendet echte Flächen an einem Quader 40 × 30 × 20 mm und den
unveränderten geometrischen Matcher. Beim Umbau bleibt links oben eine
R2-Rundung erhalten, rechts oben entsteht eine neue R2-Rundung und rechts
unten wird R2 auf R12 geändert. Die Operation belegt die untere geänderte
Rundung ausdrücklich als `fillet_3`. Vor dem Fix gab `_with_features` unter
dieser Kennung jedoch die neue R2-Rundung zurück. Eine anschließende registrierte
Radiusänderung im echten Verlauf bearbeitete ohne Nachfrage die falsche
Rundung oben rechts. Zwei Produktgegenfälle waren rot; die Negativkontrolle
ohne Herkunftsfortführung hielt bereits korrekt mit `NativeReferenceLost` an.

Die Teilumbenennung nimmt jetzt die schon gültigen Selbstzuordnungen mit.
Sie berechnet keine neuen Treffer und gibt keine offenen Kandidaten frei.
Alle drei Gegenfälle bestehen. Im kalten und warmen `History → evaluate`-Lauf
wechselt die untere Rundung R12 → R10, während beide anderen R2 bleiben.
Geprüft werden die tatsächlichen Dreiecke, die Lage und das unabhängige Volumen

`40·30·20 − (2·4 + 100)·(1 − π/4)·20 mm³`.

Es folgen zwei R2- und eine R10-Viertelkreisrundung über 20 mm Höhe;
Volumentoleranz 1e-6 mm³, relative Toleranz 0. Das Ergebnis ist geschlossen,
wasserdicht und ein Körper. Kein Test beantwortet eine Frage automatisch;
unerwartete Fragen lassen ihn scheitern.

Der anschließende vollständige Aufruferreview fand dieselbe Lücke noch in
`_native_reselection`: Nach einer korrekten manuellen Wahl übergab dieser
Weg nur `chosen` an `apply_mapping` und reservierte bereits belegte
Selbstzuordnungen aus `question.mapping` nicht. Zwei echte Gegenfälle waren
rot: die veröffentlichten Flächendreiecke gehörten zur neuen R2-Rundung,
und die Folgeoperation traf die obere statt der unteren rechten Ecke.

Beide nativen Teilumbenennungen verwenden jetzt `_native_alias_mapping`.
Der Helfer nimmt ausschließlich vorhandene Selbstzuordnungen zur gewählten
Teilmenge hinzu und erhält verwaiste beziehungsweise mehrdeutige Kennungen.
Der dritte Aufrufer im Netzweg übergibt bereits die vollständige Zuordnung
und seine reservierten Namen; er bleibt unverändert.

Im neuen echten Frageweg ist links oben zusätzlich R2 auf R3 geändert.
Die ausdrückliche richtige Wahl erhält diese Rundung unter `fillet_1`, die
belegte R12-Rundung bleibt `fillet_3`, die neue obere rechte Rundung wird
`fillet_4`. Der verwaiste Name `fillet_2` wird nicht neu vergeben. Zwei
tatsächliche Folgeoperationen ändern anschließend links oben R3 auf R4 und
rechts unten R12 auf R10. Das unabhängige Sollvolumen lautet

`40·30·20 − (2² + 4² + 10²)·(1 − π/4)·20 mm³`.

Lage, Radien, konkrete Dreiecke, Dichtheit und genau ein Körper sind geprüft;
Volumentoleranz 1e-6 mm³ bei relativer Toleranz 0. Die Wahl wird erst nach
vollständiger Auswertung gespeichert. Der warme Lauf trifft den Cache und
benötigt keine weitere Frage. „Nicht weiterführen“ hält unverändert mit
`NativeReferenceLost`. Alle sechs direkten Fälle bestehen; 49 andere Fälle
waren in diesem gezielten Lauf abgewählt. Der frühere Fachlauf mit 1206 Tests
belegt den Stand vor dieser zusätzlichen Korrektur.

## Unabhängige Abnahme des Prüfkastens

Der bestehende Reproduktionskörper wurde beibehalten. Seine frühere
Beschreibung als durchgehend 3 mm dünner Hohlkasten war falsch: `edit.box`
zentriert in XY. Die Differenz aus dem äußeren Quader 40 × 30 × 20 mm und dem
um (3; 3; 3) mm verschobenen Quader 34 × 24 × 20 mm lässt einen 3-mm-Boden,
zwei 6-mm-Seitenwände und zwei offene Seiten. Die ausgesparte Höhe im Körper
beträgt 17 mm; das unabhängige Quellvolumen ist deshalb

`40·30·20 − 34·24·17 = 10128 mm³`.

Bei Radius 2 mm werden exakt 16 Kanten gerundet, eine weitere Kante wird
gezielt ausgelassen, vier Kanten sind bereits zu schmal. Außenmaße und Höhe
bleiben erhalten. Die Abnahme prüft die nativen R2-Flächen und acht
Materialpunkte an Wandmitten, Boden, Hohlraum sowie auf beiden Seiten der
äußeren und inneren Kreisquerschnitte. Die Punkte liegen klar neben der
Oberfläche. Das gemessene Ergebnisvolumen 9951,972135 mm³ wird ausschließlich
als Messwert dokumentiert und nicht als unabhängiger Sollwert verwendet.

## Unverändertes Kundenmodell

Datei: `pegboard-goot-ceramic-screwdrivers-v3.step` aus dem lokalen Kundenkorpus.
SHA-256:
`7a3559b462fe3d542ecd890198d678cf5f2e4ce8604bd13878d860fa61616a48`.
Die Quelle ist geschlossen, hat eine Komponente, 3480 Dreiecke in ihrer
Tessellierung und ein natives Volumen von 26804,107869 mm³.

Die registrierte Operation `fillet_edges` wurde mit `radius=1.0` und
`edges="vertical"` jeweils in `draft` und `fine` ausgeführt:

| Kern | Güten | Ergebnisvolumen | Form und Rückmeldung |
|---|---|---|---|
| Exakt | `draft`, `fine` | 26798,415436 mm³ | geschlossen und wasserdicht, eine Komponente, sechs gerundete und zwei zusätzlich ausgelassene Stellen |
| Netz | `draft`, `fine` | 26809,840301 mm³ | wasserdicht, eine Komponente, acht gerundete Stellen, Solver `direct` |

Beide Kerne melden zusätzlich die 20 bereits zu schmalen Stellen. Die
Ergebnisvolumina sind Messwerte verschiedener Ergebnisse: Der exakte Kern
lässt zwei Stellen ausdrücklich aus. Quellnetz und Quelldatei blieben nach
allen vier Rechnungen unverändert.

Für die Wiederholung wird die STEP-Datei über `brep.step.read` gelesen.
Der Netzzwilling entsteht über `as_mesh_data`; beide werden als `SceneObject`
mit den obigen Parametern durch die registrierte Operation gerechnet.
Der erste Sondenlauf scheiterte ausschließlich an der JSON-Ausgabe von
`SolverInfo`. Der korrigierte Gesamtlauf mit vier Ergebnissen endete mit Exit 0.

Eine zusätzliche reale Folgeprobe ändert die radiale Rundung `fillet_18` des
unveränderten Imports über R4 → R3,5 → R3 im Verlauf. Die Kennung bleibt
erhalten; beide Ergebnisse sind geschlossen, wasserdicht und ein Körper.
Die gemessenen Volumina sind 26956,974354 beziehungsweise 27089,459677 mm³.
Der warme Verlauf zählt sechs Cachetreffer; unerwartete Fragen werden als
Fehler behandelt. Der Eingangs-Hash blieb unverändert. Diese Probe belegt
den realen Folgeweg, nicht dieselbe synthetisch erzeugte Namenskollision.

Zwei weitere versuchte Importwege bleiben getrennt dokumentiert: Nach einer
vorangestellten Gruppenrundung verlangt ein späterer Bezug auf `fillet_5`
eine native Neuwahl; die Sonde hat keine Auswahl getroffen. Der direkte
kantengestützte Importwechsel `fillet_10`, R2,5 → R2, wird vom exakten Kern
abgelehnt. Diese Wege werden durch den Identitätsfix nicht als erfolgreich
abgenommen ausgegeben.

## Fachlauf und Grenzen

Der Lauf über `tools/affected_tests.py` mit den fünf Ausgangsdateien
`test_brep.py`, `test_brep_canonical_surfaces.py`, `test_mesh_edges.py`,
`test_native_references.py` und `test_solid_ownership.py` wählte zusätzlich
Kalibrierung, Merkmalspanel, Geometriegegenproben und radiale Rundungen aus.
Dieser erste Lauf bestand mit **973 Tests in 103,71 s**, Exit 0. Der
abschließende Lauf nach dem Identitätsfix nimmt zusätzlich `test_matching.py`,
`test_matching_competition.py`, `test_matching_answers.py` und `test_revision.py`
auf. Er umfasst 13 Fachdateien und besteht mit **1206 Tests in 125,61 s**,
Exit 0. **104 Fälle blieben releasebedingt abgewählt**. Die frühere Anzahl
wird nicht zur Schlusszahl addiert. Ruff und Format für neun Dateien sowie
mypy für vier Produktmodule bestanden; nach dem letzten Fix wurden die
beiden geänderten Python-Dateien und `evaluate.py` statisch erneut geprüft,
jeweils ohne Befund. Nach der zusätzlichen Neuwahlkorrektur bestanden die
sechs direkten Fälle in 7,56 s sowie Ruff, Format und mypy. Der erneute Lauf
über dieselben 13 Fachdateien bestand mit **1209 Tests in 136,61 s**, Exit 0,
erneut 104 abgewählt. JUnit weist 1209 Fälle ohne Fehler, Fehlschläge oder
übersprungene Fälle aus. Diese abschließende Menge ersetzt die früheren
Fachzahlen und wird nicht zu ihnen addiert.

Nach der bestätigten RM225-Integration stehen `fillet_edges` auf Cacheversion
13 und `resize_feature` auf Cacheversion 14. Die Werte wurden über das geladene
Register geprüft; Ruff und Format der beiden Module sind grün.
Der neue Auswertungshelfer `_continued_match_result` und sein tatsächlicher
Aufruf gehören zusammen mit den Tests in dieselbe Einheit.
Die eigenständig integrierte Einheit benötigt außerdem den begrenzten
RM218-Anschluss: Bei einer merkmalverändernden Operation werden alle
unveränderten Vorgänger berücksichtigt, sonst nur die bisher unbewiesenen.
Die passende Helfersignatur, Kartenbeschreibung und Verschiebe-/Einfüge-/Undo-
Abnahme in `test_revision.py` gehören dazu. Die unabhängigen Änderungen zur
Fragevorschau und `previous_reference` bleiben außerhalb dieses Umfangs.

Der unabhängige Schlussreview gegen HEAD
`7f0de659d2c8fc1e35bd1067e738bcaef7f1ec72` hat die vollständige begrenzte
Einheit ohne offene Codebefunde freigegeben. Neben den Rundungs- und
Herkunftshunks umfasst diese Freigabe den notwendigen RM218-Anschluss und
dessen Tests für Verschieben, Einfügen, Passungsbezug und Undo. Ausdrücklich
nicht enthalten sind Fragevorschau, `previous_reference`, `SIDE_NAMES`,
RM320, der RM319-Testumzug und der B-Rep-Nullnormalenabsatz. Diese Freigabe
ging dem unten belegten zentralen Entwicklungstor und Commit/Push voraus.

### Strenge Verlaufstests nach der zentralen Gegenprüfung

Die zentrale Prüfung fand noch eine Schwäche in zwei älteren RM284-Testhunks:
Der kantengestützte Radiuswechsel R2 → R12 → R10 und der radiale Folgeweg
beantworteten unerwartete Fragen mit `choices[0]`. Damit konnte eine native
Neuwahl die fehlende automatische Merkmalsfortführung verdecken. Beide
Normalwege lassen unerwartete Fragen jetzt ausdrücklich scheitern.

Eine unabhängige Sensitivitätsprobe entfernt ausschließlich beim erneuten
Radiuslauf die tatsächlich erzeugten Builder-Dreiecksbelege. Der geometrische
Matcher bleibt unverändert. Beide strikten Normaltests werden dadurch genau
an der unerwarteten Neuwahl rot: zwei Fehlschläge, Exit 1. Die zusätzliche
radiale Negativkontrolle hält mit `NativeReferenceLost` am ersten
Radiuswechsel; der zweite Schritt wird nicht ausgeführt.

Ohne Eingriff bestehen die tatsächlichen Folgewege mit richtigen Radien,
hergeleiteten Volumina und geschlossenem Körper. Der abschließende kleine
Identitätsnachlauf besteht mit **13 Tests, 325 gezielt abgewählt**, Exit 0;
Ruff und Format sind grün. Die 325 abgewählten Fälle gelten nicht als
bestanden. Der frühere breite Lauf mit 1209 Tests liegt vor dieser zusätzlichen
Testverschärfung; die Produktquellen wurden dabei nicht verändert.
Der unabhängige enge Nachreview gibt diese Testhunks ohne weiteren Befund frei.
Die übrigen neuen Auswahlrückrufe erlauben ausschließlich die ausdrücklich
geprüfte Neuwahl mit festem Kandidaten und erwarteter Aufrufzahl.

### Räumliche Befunde im tatsächlichen Abschlussbericht

Bei der Vorbereitung von RM322 wurde ein weiterer RM284-Anschlussfehler
bestätigt: `_without_repeats` verglich Code, Körper, Schwere und Werte, aber
keine räumlichen Angaben. Die Meldungen zweier ausgelassener Kanten besitzen
gleiche Werte und unterscheiden sich nur im Ort. Zwei vollständige
Operationsbefunde wurden deshalb im abschließenden `Scene.report` zu einem.
Der echte Auswertungsgegenfall war zusammen mit sieben direkten Raum- und
Referenzfällen vor der Korrektur rot; vier bestehende Kontrollen bestanden.

Der vorhandene Wörterbuchschlüssel enthält jetzt zusätzlich `feature_ids`,
`location` und `outline`. Verglichen wird die vollständige Befundidentität,
keine geometrische Nähe. Eine zunächst versuchte Näherung wurde durch drei
rote Präzisionsgegenfälle verworfen. Auch sehr nahe unterschiedliche Daten
bis zum Unterschied eines Bits bleiben erhalten. Ein fehlender Ort ist
nicht der Ursprung; verschiedene Ränder am selben Ort und unterschiedliche
Zielmerkmale ohne Ort bleiben getrennt. Echte Wiederholungen behalten wie
bisher das letzte Vorkommen, die Reihenfolge der übrigen Meldungen bleibt
erhalten. Nicht hashbare Befundwerte werden weiterhin wie zuvor normalisiert.

Der vorhandene native Prüfkörper mit zwei räumlich getrennten Vereinigungen
überlappender Zylinder liefert vier gewählte Kanten: Zwei baut der echte
Gruppenbuilder, zwei lässt er aus. Für den Anschluss ist ausschließlich die
vorgelagerte Gruppenwahl auf diese bereits belegten Indizes festgelegt.
Die registrierte Operation, OpenCASCADE, die Befundfabrik und der
`History → evaluate`-Weg bleiben echt. Beide Rohbefunde bleiben unverändert;
kalter und warmer Abschlussbericht enthalten beide Orte samt Objekt- und
Schrittreferenz. Die eigentliche Rundungsoperation läuft wegen des Caches
nur einmal. Dies ist keine Abnahme der RM322-Netzzug-Zuordnung.

Der formatierte Endstand besteht mit **21 gezielten Fällen, 944 abgewählt**,
Exit 0, 2,84 s. Die Abwahlen stammen sowohl aus dem Namensfilter als auch
aus der Releasegrenze. Zusätzlich bestanden **610 Sprach- und Wertprüfungen**,
56 abgewählt, Exit 0. Ruff und Format der drei geänderten Python-Dateien
sowie mypy für `evaluate.py` sind grün. Der unabhängige enge Schlussreview
ist ohne Befund. Der frühere breite 1209-Lauf liegt vor diesem zusätzlichen
Fix; eine erneute breite Fachauswahl wurde nicht ausgeführt.

Eine weitere Cacheversion ist nicht nötig: Die rohen Operationsbefunde
waren vollständig, und der Abschlussfilter läuft auch nach Cachetreffern.
Die bestehende Oberflächenbündelung bleibt erhalten: `show_result` übernimmt
und zählt beide Rohbefunde, zeigt aber eine Sammelzeile. Bei verschiedenen
Orten hat diese Zeile keinen gemeinsamen Ort und keine einzelne
Ortsnavigation. Mehrstellenanzeige und der separate Vorschlagsnachschub
über `add_findings` sind nicht durch diesen Kernfix abgenommen.

**RM-322 bleibt offen:** Die sechs tragenden Netzkanten des
`pegboard-gs-100-v2.step` werden weiterhin nicht zuverlässig ihren exakten
Gegenkanten zugeordnet. Dieser Zuordnungsrest wird nicht durch die
Gruppenrückfälle als abgeschlossen erklärt. Fenster-, Renderer- und
Leistungsprüfungen gehören weiterhin zum Release.

## Abschluss auf dem Hauptzweig

Der Produktcommit `57848fa72c4ca229f5dc9bcdd2cca2baf6945987`
(23 Pfade) ist auf `main` und `origin/main`. Sein Nachfolger
`e3dff190728d4caf447cb3be7927d5d651dee168` integriert RM320 getrennt.
Die tatsächliche Gegenstelle wurde am 02.10.2026 zusätzlich mit
`git ls-remote origin refs/heads/main` geprüft; der erste Commit ist
nachweislich Vorfahr des zweiten. Der Abgleich von Commit-Dateiliste und
Restdiff bestätigt den vollständigen RM284-Umfang. Die oben ausdrücklich
ausgeschlossenen fremden Änderungen blieben außerhalb dieser Einheit.

Das gemeinsame vollständige Entwicklungstor
`commit-tor-abschlussrunde-45-final` prüfte den ausgewählten Stand beider
Einheiten: **19 187 bestanden, 62 übersprungen**, 432,53 s Testlauf;
Suite, Ruff, Format und mypy jeweils **Exit 0**. Es gab keine Quelldrift
während des Laufs. Die 62 übersprungenen Fälle zählen nicht als bestanden.
Das Tor enthält keine Fenster-, Renderer- oder Leistungsabnahme.

Damit ist RM284 abgeschlossen. Der notwendige begrenzte RM218-Anschluss
ist enthalten; RM218 insgesamt und RM322 werden damit nicht abgeschlossen.
