# `app/core/geom/` — wo Geometrie entsteht

Die einzige Stelle, an der Geometrie entsteht oder sich ändert (Regel 2).
Gerechnet wird gegen `manifold3d` und `trimesh`.

`contours.section_of` übernimmt einen gezeichneten Querschnitt mit allen
Innenringen unabhängig von der Umlaufrichtung; ungültige Konturen werden
nicht still repariert. `polygons_of` gibt alle Komponenten mitsamt ihren
Löchern zurück. `offset_section` versetzt normal mit runden Übergängen:
positiv wächst Material, negativ schrumpft es; Aufspaltung oder Kollaps
bleiben sichtbar. Fertigungsspiel kommt ausschließlich vom Aufrufer.
`sketch_solid.outline_points(max_sag=...)` nutzt die gemeinsame echte
Splinekurve mit begrenzter Sehnenabweichung, Abbruch und Punktbudget.
Ohne diese optionale Grenze bleibt die bisherige Abtastung erhalten.

`seal.py` erzeugt Dichtnut und unverformten Dichtring aus demselben
geschlossenen Weg und normalem Versatz. Runde Querschnitte verwenden die
Vereinigung identisch facettierter Kugelhüllen, damit gemeinsame Bahnenden
keine inneren Kappen zurücklassen. `opening_choices` bindet Innenringe an
die tatsächlichen Dreiecke einer gewählten Trägerfläche; ihre begrenzte
versionierte Signatur beschreibt lokale Konturen und Topologie, keine
Listenposition. `match_opening` liefert nur eine eindeutige belegte Wahl.
Starre Bewegungen führen den lokalen Rahmen mit; veränderte oder mehrdeutige
Flächen verlangen über `ctx.ask` eine neue gespeicherte Antwort.

`seal_ops.create_seal` erhält den Träger und erzeugt eine separate Dichtung.
Beide Materialien sind ausdrückliche `material_params`; der gespeicherte
Gegenflächenbezug liest über `reads_other_bodies` den aktuellen Szenenstand.
Der gemeinsame `sketch.ops.cut_regions` erhält Mesh- und B-Rep-Schnittwege.
Ein geometrischer Materialmantel bestätigt Boden- und Seitenrestwand aus
dem aktuellen Material-/Druckprofil; die Dichtung darf den verbleibenden
Träger nicht schneiden. Die optionale Gegenfläche wird an ihren wirklichen
Dreiecken auf parallele Gegenrichtung und vollständige Überdeckung geprüft.
Abstand, unverformte Überdeckung und Schnittvolumen sind geometrische
Auskünfte und behaupten weder Materialverformung noch Dichtheit.

Beim ausdrücklichen Materialwechsel des Dichtträgers bleiben die über den
Taschenschnitt übertragenen Farbflächen und Slotnummern erhalten. Nur
inkompatible Herstellerprofil-/Materialbindungen werden am Ergebnis gelöst;
der Befund nennt die nötige Neuzuweisung. Gleiches Material behält seine
Zuordnung. Globale Spulenbindungen und der Eingabekörper werden nicht geändert.

`profile_clamp_ops` erzeugt vier feste Rollen: untere/obere Schale und
untere/obere Einlage. Beide Materialfelder sind ausdrückliche Profilkennungen
und über `material_params` Hashabhängigkeiten. Eine gemeinsame Kontur wird
einmal gelöst; originale Skizzenausdrücke bleiben im Operationsparameter.
Der Sitz hat normales Gesamtspiel aus beiden Profilen, die Gegenkontur das
Pressmaß der Einlage. Fertigungsspiel und Sehnenabweichung bleiben getrennt.
Alle vier Rollen liegen in einem Rahmen: Die Einlage sitzt mit ihrem Bund bei
null, die Schale bekommt die Bundhöhe als `lift` — die Schale allein kennt
dieses Maß nicht (`knowledge/parts/CLAUDE.md`).

Der Ersatzweg erhält beide Schalen unverändert und prüft den gesamten
Hohlraum, einen umlaufenden Materialstreifen sowie die wirklichen
Stirnflächen. Die Bindung liegt als `profile_clamp` auf der echten
Frontfläche; lokale Gegen-, Außen- und Sitzkonturen sind Beschreibungen,
keine eigenständigen Passungsmerkmale. Ein starrer oder gespiegelter Rahmen
wird über Mittelpunkt, Normalenrichtung, X und `profile_clamp_y` mitgeführt.
Skalierte oder veränderte Sitze bestehen die Geometrieprüfung nicht allein
wegen erhaltener Metadaten. Gleiches Sitzspiel erhält die vorhandene
Einlagenaußenkontur exakt; neues Spiel wird vom festen Sitz nach innen
abgetragen und erneut auf Mindestwand geprüft.

Alle vier Teile dürfen unabhängig angeordnet sein. Die Schalen werden jeweils
in ihrem eigenen Rahmen gegen den Sitz geprüft, die alten Einlagen gegen
ihre vollständige Konstruktion. `liner_clearance` und `counter_press` speichern
dazu die tatsächlich angewandten Zugaben, getrennt von der heutigen
Materialkalibrierung. Jede Ersatz-Einlage behält ihren eigenen belegten
starren Rahmen und ihre Druckplatte. Diese Prüfung beschreibt die Form des
Anschlusses, nicht einen behaupteten Kontakt der momentan angeordneten Teile.

Beim Einlagenwechsel erhält `attributes.transfer` bestehende Filamente am
gleichen Material. Ein ausdrücklicher Materialwechsel löst die alte
Spulenidentität und meldet die nötige Filamentauswahl. Die Operation schreibt
weder Projektzustand noch globale Spulenbindungen; ungenutzte Bindungen sind
kein Beleg für die neue Einlage.

`field_ops.field_tools` bereitet vollständige Öffnungen in bestehenden
Skizzenprofilen vor. Innenringe und getrennte Regionen bleiben erhalten,
Ausschlüsse werden mit Randabstand berücksichtigt. Das gemeinsame mittige
`sketch.shapes.grid_centres` liefert die Rasterlage; der Feldursprung bleibt bei
einer Größenänderung fest. Ränder und Stege prüfen den ganzen Werkzeugumriss,
nicht nur den Mittelpunkt. Gekrümmte Grenzen werden konservativ begrenzt;
exakte Splineflächen verwenden dieselbe B-Rep-Kurve wie der Schnittweg.
`field_cut` nimmt zwei normale Skizzenwerte (Pflichtbereich und optionale Ausschlüsse)
auf derselben Ebene. Der gemeinsame `sketch.ops.cut_regions` bewahrt Tiefe,
Durchgang und Flächenrahmen auf beiden Kernen. Materialkompensation ist
ausdrücklich auf Kreis und Langloch begrenzt; beim Langloch wachsen Breite
und Gesamtlänge um dieselbe Materialzugabe.
Runde Öffnungen erhalten stabile Rasterkennungen nur nach Wiedererkennung
am wirklichen Schnitt. Ihre Tiefe und ihr Durchgang bleiben gemessen;
`_with_nominal_bore(..., sections=ARC_STEPS)` belegt das bekannte Durchmessermaß
an sämtlichen Wandpunkten. Der Weg umgeht weder die gemeinsame Grenze der
Gesamterkennung noch behauptet er Nominalmaße nach Jitter- oder Voxelrückfall.

`move_feature` versetzt eine eindeutig topologisch verbundene Senkbohrung
als ganzen Hohlraum: alle Abschnitte aus `perceive.relations.cavity_chain_at`
begrenzen gemeinsam den Werkzeugkörper, alle Kennungen und Mittelpunkte
reisen mit. Zwei äußere Randringe werden geschlossen; eine unvollständige
oder mehrdeutige Fläche bleibt abgelehnt.

`remove_feature` fragt bei einer solchen Kette über `ctx.ask`, ob alle
Abschnitte mitgehen, und hält die Antwort im Parameter `sections`
(`OpResult.answered`) fest — derselbe Weg, den `load` mit der Einheit geht.

**Beide Antworten gehen denselben Weg: erst geht der ganze Hohlraum zu, dann
wird frisch geschnitten, was bleiben soll.** Bei „ganzer Hohlraum" entfällt der
zweite Schritt, bei „nur das gewählte" schneidet `_cavity_tool` die übrigen
Abschnitte wieder aus dem vollen Material — für die Abschnitte weiter innen
zusätzlich durch den gefüllten hindurch, sonst verlören sie ihren Weg nach
außen. Den Füllkörper liefert `_cavity_plug`: aus den Flächen des Hohlraums,
wo sie einen geschlossenen Körper hergeben, sonst als **Stopfen**
(`_chain_plug`) — ein Zylinder über die ganze Kette, wie ihn der Absagetext
seit je empfiehlt. Ein Füllkörper, der die Kegelwand nachbildet, endet auf ihr,
und die Vereinigung lässt dort zwei Flächen nebeneinander stehen.

Ob der zweite Randring eines einzelnen Abschnitts ein Übergang oder sein Boden
ist, beantwortet `_stands_alone` an derselben Kette und nicht die Ringzahl:
Nach dem Verschließen der Bohrung bleiben es zwei Ringe, und die Senkung
gehört sich dann selbst. Der Umfang `entrance_mode="keep"` ändert einen
Abschnitt und meldet die übrigen; `follow` nimmt den belegten Einlauf mit.
Eine unvollständige Änderung einer einzelnen Senkung bleibt ausgeschlossen.
Die geprüfte Eigenständigkeit erreicht Werkzeugbau und Verschluss auch beim
Versetzen, Verdoppeln und der freien Platzierung samt ihrer Vorschau.

`resize_hole` erhält mit `keep` beim Verkleinern Lage und Außenmaß der anderen Abschnitte.
Eine entstehende Ringschulter gehört anschließend weiter zur erkannten Kette.
Die Bodenkennung bleibt erhalten, wenn vor und nach dem Schnitt eine vollständige
Scheibe am ganzen Wandrand liegt und dieselbe reale Ebene bestätigt ist. Neue
koplanare B-Rep-Teilflächen dürfen dazu nur vollständig und ohne überlappende
Eigentümer zusammengefasst werden. Der vorhandene Erkennungslauf liefert die
neuen Bodenmaße; allgemeine Zuordnungsgrenzen bleiben unverändert.
Bei belegten Randebenen schließt `_section_closed(extend_inner=False)` zuerst
den gewählten Abschnitt und stellt die übrigen in ihren bisherigen Grenzen
wieder her; danach schneidet `resize_bore` den neuen Durchmesser. Dadurch
entstehen am quantisierten Sacklochboden keine nahezu koplanaren Füllhäute.
Das Entfernen eines Abschnitts behält dagegen `extend_inner=True`, damit
innere Abschnitte ihren Weg durch den gefüllten Abschnitt nach außen behalten.

`_bore_end_planes` misst vollständige Randringe am ursprünglichen Netz.
Der Schnitt reicht bis zur äußersten Mündung der zugehörigen Kette, auch bei
einer schrägen Senkung oder einem tangentialen Rundungsübergang. Offene
Mündungen erhalten die vorhandene Werkzeugzugabe; Böden und geschlossene
Stufen behalten ihre Ebene. Die Wiedererkennung vergleicht verschobene
axiale Mittelpunkte am ursprünglichen Wandintervall; sie ändert dafür nur
den Vergleichspunkt, nicht die gemessene Ergebnisgeometrie.
Nachbarbefunde messen den Abstand des tatsächlichen Schnittwerkzeugs zu
den geschlossenen benachbarten Hohlräumen. Hüllquader dienen nur zur Vorauswahl;
eine bestehende dünne Wand wird nur bei weiterer Verschlechterung gemeldet.

`bore_entrance` prüft für Operation und Handlungsvorgabe denselben gemeinsamen
Einlauf. Eine bereits geprüfte Kettenauskunft wird über `cavity` und
`touches_other` weitergegeben; `()` belegt, dass kein gemeinsamer Einlauf
existiert. Der Schema-Standard bleibt `keep`; eine belegte neue Merkmalsaktion
belegt `follow` vor. Dort erhalten alle radialen Profile denselben Zuwachs,
Senkungswinkel und axiale Stufenlagen bleiben. Die radiale Einführbreite ist
im Normalquerschnitt auf Höhe der Mündungsebene definiert; die Schnittkurve
auf einer schrägen Außenfläche folgt daraus. Echte Ringschultern bleiben
radiale Stufen. Eine schräge gemeinsame Kegel-/Zylinderkante wird dagegen
durch den kreisrunden Hals des neuen Kegels ersetzt, ohne künstliche Schulter.

Beide Kerne schneiden dieselben Profile an denselben Randebenen. Der exakte
Füllkörper bildet das alte Profil nach, damit er keine tieferen Nachbarlöcher
unter der weiten Senkung füllt. Hinterschnitte, Verzweigungen, doppelte Ränder,
versetzte Stufen und ungeklärte Profile nennen die vorhandene `keep`-Wahl.
Ein einzelner Zylinder behandelt beide Umfänge gleich. Eine gleichzeitige
Lageänderung mit Einlauf nennt den separaten Weg über `move_feature`.

Nach geometrisch bestätigter Zuordnung erhält `_with_nominal_bore` bekannte
Operationsmaße, damit der Fit an Dreiecksmitten Durchmesser und Senkungswinkel
nicht bei jeder Folgeänderung verkleinert. Alle Wandpunkte müssen das aus
der Werkzeugunterteilung abgeleitete Sehnenband einhalten; `voxel` und
`jittered` behaupten keine so bestätigten Nominalmaße. Bei Kegeln bleibt der
äußere Durchmesser das wirkliche maximale Maß der beschnittenen Mündung.

Die Nachprüfung einer Bohrungsänderung verwendet oberhalb der gemeinsamen
Grenze `perceive.local.FEATURE_LIMIT_TRIANGLES` die örtliche Suche
`detect_known`. Beim gemeinsamen Einlauf umfasst sie alle neu konstruierten
Abschnitte; der erforderliche Suchradius entsteht aus dem vollständig
gekappten Werkzeug. Das ist ein geometrisch belegter Umfang, keine größere
Erkennungstoleranz. Der Sollbeschreiber einer schrägen Senkung liegt wie der
Erkennungsbefund am äußersten Kegel-/Ebenenschnitt. Die Nominalprüfung kann
mit `sections` die tatsächliche Kreisunterteilung des Erzeugers übernehmen.

**Und eine Kette geht als Ganzes** (RM-172, 15.09.2026): `move_feature`,
`_rotate_cavity_chain` und `_duplicate_cavity_chain` nehmen Bohrung und
Senkung zusammen. Fürs Kippen baut `_chain_tool` das Werkzeug aus den
Kennzahlen der Abschnitte — mit Überstand an beiden Enden: die Bohrung über
ihre Mündung hinaus, die äußere Senkung als größerer Kegel
(`_measured_section` mit `outward`). Wie weit, rechnen
`_reach_past_a_tilted_face` und `_cone_past_a_tilted_face` aus der Neigung.
Fürs Versetzen bleibt es beim exakten Flächenkörper, den `_past_the_mouths`
an seinen Mündungen um die Zugabe aus §39 verlängert — das Werkzeug aus
Kennzahlen kostete dort Volumen, der bündige Körper ließ eine Haut von 5 µm
stehen. Gedreht wird um die Mitte des gewählten Abschnitts. Nur `slot_hole`
sagt an einer Kette weiter ab.

Die Regeln stehen in `.claude/rules/operationen.md`.

`repair()` übernimmt Verschweißen und Dreiecksbereinigung nur, wenn ein
geschlossener Eingang danach geschlossen bleibt. Andernfalls bleiben das
Netz und seine Materialzuweisungen erhalten; ein Befund nennt den ausgelassenen
Schritt. Die Zusicherung entspricht `ingest.loader.normalise`. Die einzelnen
Reparaturhilfen bleiben für ausdrücklich gesteuerte Reparaturketten verfügbar.

**Die Kantenwarnung misst am Hüllquader nur vor.** `over_the_edge_along`
meldet eine offene Flanke, wenn die Mündungsscheibe über die Hülle ragt — das
ist billig und für einen `Solid` der einzige Weg. Auf einer gekrümmten Fläche
trifft es aber immer zu: Der Scheitel liegt auf der Hülle, und die getroffene
Facette steht schräg. Wo ein Netz vorliegt, entscheidet deshalb
`_flank_is_open` nach: ein Kranz von Punkten auf dem Bohrungsumfang, an
mehreren Tiefen in beide Achsrichtungen; liegt er an einer davon vollständig
im Material, reißt dort nichts auf. Innen und außen trennt `mesh.on_surface`
über die Normale des nächsten Dreiecks — nicht `trimesh.contains` (führt durch
`rtree`) und nicht `ray_hit_distances` (Kantentreffer zählen mehrfach, die
Parität trägt nicht). Dieselbe Frage stellen seit dem 15.09.2026 alle Wege,
die eine Bohrung neu setzen — Versetzen, Verdoppeln, Drehen, Ändern, frei
platziert oder als Kette (`prepare_ops._edge_findings`): je Abschnitt des
gesetzten Hohlraums am gefüllten Körper vor dem Schnitt, an der Mitte, an den
Enden eines Langlochs und an den Austritten der Achse aus dem Hüllquader
(`_axis_exits`); dort fragt `prepare.mouth_over_the_edge` nur den halben
Radius hinter der Mündung, denn eine gekippte Bohrung reißt kurz hinter ihrem
Austritt auf und steckt weiter innen wieder im Material. Gemeldet wird
höchstens einmal — die Fahne eines Minigolf-Satzes gewann beim Versetzen um
2 mm 8,5 Prozent Volumen, und der Bericht schwieg.

**Was aus dem Review vom 15.09.2026 sonst noch hier steht:** `_rooted` und
`_tool_for` reichen Qualität, Startwert und Abbruchmarke an ihre Boolesche
durch (`_placing_tool`, `_closed_at`); `_tool_for` fragt `hole_is_clear` vor
dem Flächenkörper und gibt dem Flächenkörper einer Bohrung den Kragen aus
`_past_the_mouths` mit — den nimmt seither auch die Kettenkopie beim
Verdoppeln statt des Werkzeugs aus Kennzahlen. `hole_is_clear` lässt dem
Sacklochboden `FEATURE_OVERLAP` Spiel, nicht zehn Nanometer, und
`_without_cavities` nennt seine neun Achsproben (`_CAVITY_AXIS_SAMPLES`).
`MeshData.component_count` merkt sich seine Zahl im Cache des Netzes.

Merkmalswerkzeuge verwenden die gemessene Tiefe unabhängig vom Durchmesser.
`_tool_for` erhält bei Bohrungen den tatsächlichen Sehnenzug ihrer Wandflächen.
Füllkörper umschließen die äußersten Wandknoten auch bei fremder Tessellation;
an offenen Langlöchern begrenzt die Mündungsebene den Füllkörper (§21.1).
Nach einem Versatz entscheidet die Zielgeometrie über den Durchgang, auch bei
rein seitlicher Bewegung. Verlorener Durchgang erzeugt einen Befund und
korrigiert das Merkmal. Entfernte Kennungen bleiben in
`SceneObject.reserved_feature_ids` für spätere Kopien gesperrt (§21.2).

Materialslots werden nach einer Booleschen Operation anhand der erhaltenen
Eingangsflächen übertragen; eine gleiche Dreieckszahl beweist keine gleiche
Zuordnung. Rasterbudgets multiplizieren mit unbegrenzten Ganzzahlen.
`paint_slot.replace_filament` übernimmt eine ausdrücklich gewählte Spule
vollständig, auch unbekannte Materialwerte. Ohne dieses gespeicherte Flag
behält die Operation das historische Ergänzungsverhalten leerer Felder.
`clear_filament` entfernt eine Zuweisung am Körper oder an `at_features`;
das frühere einzelne `at_feature` bleibt lesbar. Die Dreiecke aller gewählten
Merkmale werden gemeinsam vor der Platzsuche betrachtet. Bei einer Teilmenge werden andere bisherige
Slot-0-Flächen mit ihrer unveränderten Definition auf einen freien Platz
verschoben. Ohne Platz bleibt der Körper unverändert und der Fehler nennt
die nötige größere Auswahl. Geometrie, Merkmale und exakte Hohlrauminformation
bleiben erhalten; ein neutrales Slot 0 besitzt keine Filamentdefinition.
Ein altes allein am Körper gespeichertes Material wird vor dem teilweisen
Färben oder Entfernen über `slots_for_object` in explizite Definitionen
übernommen. Vollständige Abwahl leert auch dieses alte Materialfeld.
Die Differenzansicht überspringt ausschließlich identische Netzarrays,
keine bloß gleichen Hüllquader und Volumina. Und identische Netzarrays mit
anderen Farben überspringt sie nicht mehr (RM-169): `Difference.recoloured`
trägt dann den Körper danach, `Difference.retriangulated` den Körper danach,
wenn die Dreiecke sich ändern und das Volumen unter dem bleibt, was der
Drucker hinterlässt — `compare_scenes` setzt beides, die Ansicht zeichnet den
Körper danach über den davor (`Viewport._cover_body`). `SceneDifference.changed`
bleibt die Volumenfrage; `reshaped` und `recoloured` sind die zwei anderen.
Eine unvollständige Differenz (`difference.incomplete`, ein Schnitt ist
gescheitert) trägt kein `retriangulated`: Zwei Volumina von null sind dann
keine Aussage über das Volumen.

`Difference.result` bewahrt den vollständigen Nachherkörper auch dann, wenn
der zusätzliche Volumenvergleich unvollständig ist. Bei überlappenden
positiven Schalen werden geometrisch identische Komponenten vor dem
Vergleich abgezogen; negative Innenschalen bleiben mit ihrem Körper
verbunden. Reine Kontaktschalen innerhalb des Float64-Rechenfehlers zählen
nicht als entferntes Material. Echte Änderungen hinter aufgesetzter Schrift
bleiben Teil des Vergleichs. `SceneDifference.findings` trägt daneben die
Befunde der vorgeschauten Schritte, nicht die Vorgeschichte des Imports.

Eine mitgeführte exakte `MeshData.cavity` folgt in `transform.apply` derselben
Matrix wie der Körper. Änderungen der Topologie verwerfen die Auskunft,
solange ihre Gültigkeit nicht eigens hergestellt wird.
Reine Slotzuweisungen in `attributes.with_slot` und `paint.fill_feature`
erhalten den Innenraum unverändert; sie ändern keine Geometrie.

Die allgemeinen Booleschen Nutzerbefehle verwenden bei ausschließlich
exakten Eingängen `brep.edit.boolean` und erhalten deren Körperart. Sobald
ein Mesh beteiligt ist, gilt die Netz-Rückfallkette. Beide Wege prüfen leere
Ergebnisse und wirkungslose Änderungen, bevor sie einen Körper zurückgeben.

## Die Boolesche Rückfallkette (§17.2)

Sie ist das Muster, das dieses Gebiet prägt — kein Sonderfall, sondern der
Normalweg:

| Stufe | Was sie tut | Vermerk |
|---|---|---|
| 1 | direkt durch den Kern | `direct` |
| 2 | verschweißen, entnadeln — ohne ein dichtes Netz aufzureißen —, erneut | `welded` |
| 3 | die Eingangsgeometrie minimal stören | `jittered` |
| 4 | auf Voxeln rechnen, neu vernetzen | `voxel` |
| 5 | aufgeben — mit Befund und Weg nach vorn | — |

**Die Stufe, die es geschafft hat, wird in die Operation geschrieben.** So
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft **nie
stillschweigend**. In Entwurfsqualität endet die Kette nach Stufe 2, damit das
Iterieren schnell bleibt (§31).

`tests/test_boolean.py` erzwingt jede Stufe einzeln.

**Dicht per Index ist noch nicht dicht.** `_kernel` verschweißt seine Ausgabe
so, wie jeder Slicer sie verschweißen wird (`_tidied`): Eckpunktpaare unter der
Schweißtoleranz und Dreiecke mit doppeltem Index fallen weg — übernommen nur,
wenn Netz und Volumen es überstehen. Warum, steht an der Funktion und in
`operationen.md` (RM-166); der Kundenweg STL → Operation → STL → Import ist
`test_export.py::test_a_mesh_op_result_on_an_stl_survives_the_weld`.

Kanten- und Flächenoperationen reichen `ctx.quality` durch alle Teilschritte,
auch Werkzeugvereinigung, Eckanschlüsse und Wiederherstellung einer Rundung.
Kein innerer Booleschritt darf den Entwurf auf feine Qualität hochstufen.

**Und `ctx.cancelled` geht denselben Weg.** *Verrunden*, *Fase*, *Wulst* und
die *Formschräge* fragen das Token zwischen den Kanten beziehungsweise den
Wänden und geben es an jeden Booleschritt weiter; innerhalb eines
Werkzeugkörpers ist nichts zu unterbrechen, davor schon. Der Grund ist
gemessen: Eine Lochplatte mit sechzig Bohrungen braucht 2,7 Sekunden für die
Fase über alle Kanten und 6,9 für die Verrundung (§15.6).

Die drei nativen Netzstufen übergeben `Mesh64` an Manifold und lesen dessen
Status und Volumen vor der Rückvernetzung. Nullvolumen bei flächigem Kontakt
wird als leeres Netz weitergegeben; erst `allow_empty` entscheidet, ob das
eine zulässige Antwort ist. Für gedrehte und gekrümmte Kontaktflächen begrenzt
`gamma(8) * max|Koordinate| * Oberfläche` die native Float64-Rundung.
Dieses datenabhängige Band ist keine Drucktoleranz; echte dünne Schnitte
oberhalb der Rechenunsicherheit bleiben erhalten. Dieselbe Grenze gilt je
nativer Zusammenhangskomponente, damit Kontaktreste auch neben echten Körpern
verschwinden. Verbleibende Schalen werden als orientierte Mesh-Puffer angefügt;
eine erneute native Vereinigung würde negative Hohlraumschalen füllen.
Änderungen am gemeinsamen Kern entwerten den Ergebnis-Cache über
`paths.results_cache_dir()` für alle Operationen: im Quellbetrieb durch den
Core-Zeitstempel, im Paket durch die Anwendungsfassung (§38).
Die Plausibilität verwendet
das orientierte Volumenintegral ohne
Schwerpunktdivision und lehnt offene oder umgestülpte Ergebnisse weiterhin ab.
Die native Eingangsgrenze fordert schreibbare C-Puffer; die Rückvernetzung
erzeugt eigene schreibbare Arrays, damit weitere Netzoperationen und
Abstandsmessungen dieselbe Ausgabe übernehmen können. `shared_volume`
verwendet denselben Kern und unterscheidet Kontakt von dünnem Schnittvolumen.

## Die Karte

**Grundlage**

`mesh.py` (die Mesh-Hülle um den Geometriekern, §9; `read_mesh` liest nur, was
trimesh zu einem Körper macht — kein 3MF, kein Dateiformatwissen darüber
hinaus, das liegt in `ingest/`) · `boolean.py` (die Kette
oben) · `repair.py` (Netze reparieren — und dort zwei Nachbarn, die man leicht
verwechselt: `remove_small_components` misst die **Fläche** gegen die größte
Komponente und wirft lose Fragmente, `remove_hollow_shells` misst das
**Volumen** gegen null und wirft Flächenpaare ohne Dicke; ein Bauteil von
einem halben Millimeter hat ein Volumen, eine Haut von hundert
Quadratmillimetern keines) · `attributes.py` (Materialslots durch
eine Operation hindurch behalten, §20) · `enclosure.py` (Konturverschachtelung
ohne `rtree`) · **`lathe.py`** (Drehkörper, deren Ecken auf jeder Maschine
dieselben Bits tragen — `cylinder`, `annulus`, `revolve`, `circle_points`;
die Topologie macht weiter `trimesh`, ersetzt werden nur die Ecken, und ob
die Struktur dafür passt, prüft es bei **jedem** Aufruf nach. Der Anlass
steht in RM-187: `np.cos` wählt seine Implementierung nach der CPU, und aus
drei Zehnteln eines Billiardstels Millimeter wurden nach einer Booleschen
Operation 1224, 1226 und 1228 Dreiecke an demselben Körper)

**Bewegen und Ausrichten**

`transform.py` · `ops.py` (Kategorie „Transformation") · `align.py` (Merkmale
in Flucht bringen)

**Körper erzeugen und formen**

`primitive_ops.py` (Quader, Zylinder, Kegel oder Kegelstumpf, Kugel und Ring;
Kegel und Ring dienen auch als verständliche Werkzeugkörper für Boolesche Ops)
· `blend.py` (weiches Verschmelzen) · `displace.py`
(Höhenfeld) · `lattice.py` (Gitterfüllung) · `texture_ops.py`
(Oberflächentexturen als echte Geometrie) · `sculpt.py` · `pose.py`
(Skelett und Stellung) · `sketch_solid.py` (einen Skizzenumriss zu einem Netz
aufziehen)

`texture_ops.texture_tool()` erzeugt den gemeinsamen Werkzeugkörper für
Vorschau und Operation. `coverage="whole_face"` bindet die gewählte ebene
Fläche über ihre Kennung, schneidet die Musterpolygone an ihren tatsächlichen
Dreiecken zu und hält Innenringe sowie konkave Ränder frei. Die Drehung gilt
innerhalb dieser festen Kontur. `rectangle` bleibt die Vorgabe für vorhandene
Operationen mit freier Position und Breite/Höhe.

Die fünf analytischen Grundkörper entstehen lokal über
`primitive_local_tool()`. Operation und temporäre Oberflächenvorschau beziehen
damit denselben Körper auf denselben Ursprung. `x/y/z` verschieben diesen
Bezugspunkt; eine gesetzte `nx/ny/nz`-Richtung legt sein lokales +Z über
`sketch.planes.frame_of()` in den Raum. Der Nullvektor bewahrt die bisherige
aufrechte Lage. `angle` dreht ihn zusätzlich um seine eigene Hochachse —
`frame_of` legt die Querachse deterministisch, aber nicht wählbar fest, und
für einen Quader ist das der Unterschied. Der Name ist derselbe wie bei den
Bausteinen; das Register zählt ihn zu den Platzierungsfeldern
(`PART_PLACEMENT_PARAMS`), und damit gehen die Grundkörper denselben Weg durch
die Oberflächenplatzierung.

`sketch_solid.py` ist das Gegenstück zu `brep/profiles.extrude` für den Fall,
dass kein exakter Körper vorliegt — und dieser Fall ist der häufigste: Wer ein
heruntergeladenes STL öffnet, hat ein Netz. Bis zum 30.08.2026 endete das
Abtragen dort an einem Satz („besteht bereits aus festen Dreiecken"); seitdem
schneidet `sketch_pocket` über die Boolesche Kette auch in ein Netz. Was dabei
entsteht, ist wieder ein Netz — der Unterschied bleibt, die Absage nicht.

`sculpt.py` und `pose.py` sind **Sammelparameter-Ops**: viele Gesten, ein
Schritt. Das Ergebnis folgt vollständig aus den Parametern, was das Fenster
währenddessen zeigt, ist Vorschau. `tests/test_gesture_ops.py` prüft das über
das ganze Register.

`pose_parameter_references(strict=True)` meldet unlesbare Stellungswerte
sofort. Die Verwendungsabfrage kann damit unbekannte Abhängigkeiten von
unbenutzten Maßen unterscheiden. Skelettlisten enthalten Koordinaten und
keine Projektmaße; nur die Winkelwerte der Stellung sammeln Referenzen.
Der Standardvertrag bleibt für den Cache erhalten: Die Operation meldet
beschädigte Texte bei ihrer Auswertung.

**Wandungen**

`hollow.py` (Aushöhlen — mit den Entlüftungen, die es druckbar machen; die
Öffnung liegt oben oder an der gewählten Seite: `open_towards` ist eine
Achsrichtung, `_mouth` zieht den äußersten Querschnitt des Hohlraums in dieser
Richtung durch, und die Operation leitet sie aus der Normalen der Fläche in
`open_at` ab, RM-087) ·
`lid.py` (ein Deckel für eine Öffnung — auch vor einer Seitenöffnung:
`opening_frame` nimmt jede achsparallele **Außen**fläche, `create_lid` dreht den
Körper mit `upright_normal` nach oben, baut wie immer und dreht Deckel und
Merkmale zurück; die Hohlraumdecke liegt innen und wird abgewiesen)

**Druckvorbereitung**

`prepare.py` und `prepare_ops.py` (Bohrungen, Teilen, Abschneiden — das halbe
Teilen mit einer bleibenden Seite, `cut_away` über `section.cut` —, Anordnen,
Kollisionen, §18.6) · `autosplit.py` (schneiden, bis es auf die Platte passt; nach einer
billigen Naht-Vorauswahl entscheidet das interne Stützvolumen der fertig
verstifteten Hälften, §22.3; `search_plane` sagt neben der Ebene, wie viele
Ebenen an einer gesperrten Sichtfläche gescheitert sind — daran unterscheidet
`split_to_fit` „keine Ebene" von „keine Ebene neben der Sperre",
`split.blocked_by_protection`) ·
`pins.py` (Passstifte; Auto Split wählt die Form aus Fügefläche und
Materialtiefe und hält den Kleberhinweis als Operationsparameter fest) ·
`orient.py`

**Die Nummer eines zerlegten Teils hängt an der Geometrie, nicht am Rauschen.**
`_loose_parts` ordnet nach Volumen — aber nach dem **gerundeten Verhältnis zum
größten Teil** (`_SAME_SIZE`), und bei Gleichstand entscheidet `_where_it_sits`,
die Mitte des Hüllquaders. Der Grund steht in beiden Docstrings: Zwei gleich
große Teile unterschieden sich in den letzten Stellen mit der Tessellierung,
und ihre Nummern tauschten bei manchen Größen. Die Kennung eines Objekts ist
der Anker für jeden späteren Schritt; ein Tausch nimmt ihm sein Ziel.

**Ein Langloch ist eine Bohrung mit zwei Bogenmittelpunkten.** Der Umriss
entsteht einmal (`prepare.slot_profile`) und wird von beiden Kernen aufgezogen
— vom Netz-Kern über `sketch_solid.extrude_profile`, vom exakten über
`brep.profiles.extrude`, wo die Enden echte Zylinderflächen bleiben.
Der Umriss normalisiert seinen Winkel auf eine halbe Umdrehung: geometrisch
gleiche Langlöcher erhalten dadurch auch dieselbe Facettierung und Schnittfolge.
`slot_travel` rechnet die Gesamtlänge des Dialogs in die Mittellinie um und
lehnt dabei die Aufweitung ab; `slot_ends` nennt die beiden Endpunkte, an
denen jede Prüfung fragen muss, die für eine runde Bohrung an der Mitte fragt.
`prepare.edge_findings` stellt diese Frage beim Setzen, Ziehen und
Verbreitern für beide Kerne und meldet eine offene Flanke höchstens einmal.
Der Weg dorthin hat zwei Eingänge: `drill_hole` setzt eines (`slotted`,
`slot_length`, `slot_angle`), `slot_hole` zieht eine **erkannte** Bohrung
nachträglich auseinander (`prepare.slot_bore`, exakt `brep.edit.slot_bore`).
Die Regel dazu steht in `.claude/rules/operationen.md`.

Auch beim nachträglichen Ziehen bleibt die Kombination mit einer Senkung
ausgeschlossen. `slot_hole` prüft vorher die topologische Hohlraumkette;
ein verbundener oder mehrdeutiger weiterer Abschnitt hält die Handlung an.
Eine gesonderte runde Aufweitung lässt sich nicht durch bloßes Ändern ihres
Durchmessers zu einer passenden Langlochsenkung machen.

**`slot_hole` und `resize_hole` nehmen dabei eine Stelle entgegen** (`x/y/z`,
**leer** heißt „lass es, wo es ist" — `_named_place` beantwortet das für beide,
und die Felder sind `optional`, weil die Null an einer Koordinate die Mitte des
Teils ist). Leer gilt dabei **je Achse**: Wer nur `x` nennt, versetzt nur in x,
und y und z behalten ihren gemessenen Wert. Wer versetzt, schließt zuerst die
alte Stelle — am Netz über `_closed_at`, am exakten Körper über
`brep.edit.fill_bore` — und schneidet an der neuen. **Wer dreht, ebenso**
(`_slot_turned`, seit dem 15.09.2026): Ein Langloch in neuer Richtung war bis
dahin ein zweites quer über dem ersten, mit Warnung — jetzt ist es ein
gedrehtes, und `slot_hole.turned` sagt den Winkel. **Geschnitten und nicht
geändert**: `resize_bore` verglich dort die zwei Durchmesser, fand sie gleich
und gab den Körper unverändert zurück; gemessen am 10.09.2026 blieb das Loch
bei (−20 | −10) und der Befund sagte „Die Bohrung hat bereits diesen
Durchmesser". Zwei Dinge hängen daran und sind beide gemessen: Die Tiefe wird
**vor** dem Verschließen abgelesen (`feature.face_indices` zeigen danach auf
fremde Dreiecke), und die Zuordnung sucht das Merkmal an seiner **neuen** Mitte
— mit der alten meldete der Netz-Weg es als verloren und der exakte warf einen
Programmfehler.

Die geometrische Vorauswahl projiziert dieselben Normalenrichtungen in
begrenzten Gruppen auf Z. Vollständige Netzkopien entstehen erst für die
Platzierungsprüfung; eine begrenzte Bestenliste prüft sie in der vollständigen
Bewertungsreihenfolge, bis genügend passende Lagen vorliegen. Ungenutzte
Vertices zählen wie bei den Netzbounds nicht zur Höhe. Gleiche Flächensummen
behalten die lexikographische Reihenfolge ihrer Normalengruppen.

`core/build_area.py` ist der gemeinsame Druckbereichsvertrag: `printable_area`
liefert eine polygonale Fläche ohne feste Sperrzonen, `printable_height` die
freigegebene Höhe. Beide lesen `PrinterProfile`; ohne optionale Kontur gilt
das nominelle Rechteck aus `build_volume`. Alle Konturen verwenden XY relativ
zur nominellen Bettmitte, Z beginnt auf dem Bett. Ein `margin` gehört zum
Auftrag und verändert das Maschinenprofil nicht. `fits_on_bed` prüft die
aktuelle Lage; `placement_offset` sucht eine passende Verschiebung aufs Bett.
Bei Sperrzonen zählt die tatsächliche XY-Projektion statt nur der Hüllbox.

Anordnung, Bauraumprüfung und Orientierung verwenden diesen Vertrag. Die
Orientierung prüft auch eine Vierteldrehung in der Platte und erhält die
XY-Mitte, solange sie passt. `SearchResult.transform` trägt die vollständige
Bewegung zum Originalkörper, einschließlich B-Rep; die Grundrichtung allein
beschreibt die Platzierung nicht. Auto Split prüft jedes Endstück samt
Verbinderreserve gegen dieselbe Kontur. `oversize` liefert nur dimensionale
Überstände; `fits` entscheidet zusätzlich über die polygonale Fläche.
Eine Zwischenhälfte ohne passende Lage hat unbekannten Stützbedarf (`inf`),
kann aber weitere Schnitte benötigen. Andere Geometriefehler bleiben Fehler.

**Gepackt wird in der Ecke, gelegt wird in der Mitte.** `arrange_on_bed` sucht
jede Lage weiter an der hintersten, dann linkesten freien Stelle (§29) — das
Verfahren bleibt mitsamt seiner Abnahme. Erst danach schiebt `_into_the_middle`
jede Platte als Ganzes in die Mitte der freigegebenen Fläche, wie es jeder
Slicer daneben tut (`best_object_pos` steht dort auf `0.5x0.5`). Verschoben
wird je Achse nur, was hineinpasst, und nur wenn die Zielfläche wirklich frei
ist — die Prüfung gegen Sperrzonen läge sonst hinter der Verschiebung.
`occupied` nennt Körper, die liegen bleiben und ihren Platz belegen; eine
Platte mit solchen wird nicht zentriert.

**`orient_for_print` legt hin, was es umgeworfen hat.** Ein gedrehter Körper
braucht mehr Fläche als ein stehender und lief sonst in seinen Nachbarn
(Befund Robert, 09.09.2026). Der Parameter `arrange` ruft dieselbe Anordnung
mit denselben Werten für Abstand und Platten. **Über die Oberfläche bekommt sie
die ganze Szene** (`whole_scene`, wie *Auf dem Bett anordnen*), es bleibt also
niemand liegen und die Platte wird zentriert. Ein **gespeicherter** Auftrag
trägt dagegen seine damalige Teilmenge; dort gehen die übrigen als `occupied`
mit und die Zentrierung entfällt. Was der Abstand enthalten
muss — Plattenhaftung und Stützrand —, rechnet `export.writer.clearance_margin`,
und vorbelegt wird er in der Oberfläche (`MainWindow._spacing_for`), weil
Druckeinstellungen nicht zur Auswertung gehören.

Der Parameter `arrange` steht dabei auf `True`, auch für **gespeicherte**
Aufträge: Ein alter Stapel ordnet beim Öffnen mit und legt seine Körper
auseinander (Entscheidung Robert, 10.09.2026). Ohne Migration, weil die
Änderung die Lage berichtigt und keine Maße umdeutet — Bauplan §29 führt die
Begründung.

**Und weil sie an ihren Eingängen vorbei liest, sagt sie es dem Schlüssel.**
Der Registereintrag trägt `reads_other_bodies=True`; ohne das behielte ein
Ergebnis seine Gültigkeit, nachdem jemand einen nicht gewählten Körper
verschoben hat — der gedrehte wiche einem Nachbarn aus, der längst woanders
steht. Die Regel dazu steht in `.claude/rules/operationen.md` unter „Und die
vierte hängt an keinem Parameter".

**Ein Zug speichert einen Weg, gemeint war ein Platz.** `back_onto_bed` holt
zurück, was eine Bewegung von der Druckfläche oder in ein anderes Teil
geschoben hat. Die drei Operationen, die ein Gizmo-Zug anlegt —
`translate_object`, `rotate_object`,
`scale_object` — rufen es über den Parameter `keep_on_bed`. Erst wird
zurückgeschoben, den kürzesten Weg, den `placement_offset` ohnehin zuerst
prüft; steht dort ein Nachbar, sucht `arrange_on_bed` eine freie Stelle **auf
derselben Platte**. Ist dort nichts frei, bleibt der Körper liegen und
die Bauraum- und Kollisionsprüfung sagen es wie bisher — ein Plattenwechsel
hinter dem Rücken des Kunden wäre ein Teil, das er beim Drucken nicht wiederfindet.

**Die Vorgabe ist aus, und den Haken setzt der Zug** (`MainWindow.
_on_transform_dragged`, vier Stellen). Ein getippter Wert ist eine Ansage und
wird ausgeführt; ein Zug ist ein Zeigen. Der Unterschied ist gemessen: Das
Galerieteil `website/teile/gehaeuse.p3d` schiebt seinen Deckel um 135 mm und
graviert danach bei x = 135 — mit stiller Rückholung fiel „SOLIDON" in sieben
lose Buchstaben —, und ein Kranz, der bewusst über den Bauraum gelegt wird,
soll das melden statt zurückzurücken.

Drei Bedingungen tragen das Verhalten, und jede hat ihren Grund: Geprüft wird
der **Eingang** (wer schon daneben stand, ist geparkt und wird nicht
eingefangen), bewegt wird nur in **XY** (die Höhe hat *Auf das Bett setzen*,
und ein für einen Schnitt angehobener Körper darf nicht heruntergezogen
werden), und die **gemeldete Matrix** trägt Bewegung und Rückholung zusammen
— sonst zeigte die Vorschau dorthin, wohin die Zahlen weisen, und der Körper
läge woanders. Auch diese drei lesen die übrigen Körper, also tragen auch sie
`reads_other_bodies=True`.

**Kanten**

Das Entfernen und Ändern einer erkannten Netzrundung rekonstruiert die
ursprüngliche Kante nur zwischen genau zwei nachgewiesenen ebenen Flächen.
Die Flächenerkennung grenzt diese von Mantelfacetten ab; eine Tangente einer
gekrümmten Nachbarwand darf keine Ersatzebene für einen Füllkörper werden.

`faces.py` — die **Flächen** eines Netzes bearbeiten, Gegenstück zu `edges.py`:
*Fläche versetzen* und die *Formschräge*. Über der gewählten Fläche entsteht ein
Prisma ihres eigenen Umrisses — Boden und Deckel sind ihre Dreiecke, der Mantel
steht auf den Kanten, die nur zu einem von ihnen gehören. Ein Polygon wird dabei
nie gebildet; das trifft auch einen Umriss mit Loch. `_prism_from` nimmt einen
**Versatz je Knoten**: fest ergibt das gerade Prisma des Versetzens, mit der
Höhe wachsend den Keil der Formschräge.

Die neutrale Ebene der Formschräge liegt in beiden Kernen auf der unteren
Z-Grenze des Körpers. Ein reiner Höhenversatz ändert weder Abtrag noch Maße;
auch vollständig unter Z = 0 entstehen vollwertige Keile statt Nullvolumen.

`face_ops.py` — *Fläche versetzen* und *Formschräge anstellen* im Register,
kernübergreifend wie `edge_ops.py`. **Und `push_face` hat dabei seinen
Parameter gewechselt**: Es nahm eine Richtung und bewegte jede Fläche, die
dorthin zeigte — an einer Treppe alle Stufen zugleich (24000,0 statt 21000,0).
Gemeint ist die gewählte Fläche, und die benennt jetzt ein Merkmalsverweis; die
Richtungsfelder tragen nur noch gespeicherte Schritte (§16).

`edge_ops.py` — *Verrunden*, *Fase anbringen* und *Wulst anlegen* im Register, **kernübergreifend**:
Der Rumpf fragt `SceneObject.kind` und wählt danach den Rechenweg — `edit.fillet`
am exakten Körper, `edges.round_edges` am Netz. Sie standen bis zum 10.09.2026
in `brep/ops.py` mit `requires_kind="brep"`; wer ein STL einlas, fand sie
ausgegraut (Entscheidung Robert: „alles soll immer bearbeitbar sein"). Kein
Zwillingspaar (`MENU_TWINS`) — dort wählt der **Kunde**, hier der Körper, und
für ein Netz gibt es den exakten Weg gar nicht (§30).

`edges.py` — die Kanten eines Netzes als **Züge**, mit denselben Schlüsseln,
die der exakte Kern vergibt. Eine Bauteilkante besteht in einem feinen Netz
aus vielen Dreieckskanten; wer sie einzeln ausgäbe, zeigte vierzig Kanten, wo
der Kunde eine sieht. `edge_key` steht hier und wird von `brep.edit`
mitbenutzt: Dieselbe Kante bekommt aus beiden Kernen denselben Schlüssel,
sonst müsste alles darüber — Anklicken, Beschriftung, der Parameter
`edge_keys` — die zwei Rechenwege auseinanderhalten. **Die Auswahl selbst
steht hier ebenfalls**: `choose` und `wanted` beantworten „alle senkrechten"
für beide Kerne, `brep.edit` ruft sie. `MeshEdge.convex` sagt zusätzlich, ob
Material weggeht oder dazukommt; am exakten Körper weiß das die Topologie
selbst — und daran hängt beim Verrunden, ob abgezogen oder vereinigt wird.

Geschlossene Kantenzüge tragen im Schlüssel zusätzlich ihre Ausdehnung vom
Linienschwerpunkt, am Kreis also den Radius. Mitte und Richtung allein
unterscheiden die konzentrischen Ränder eines Rohrs nicht. Alte Schlüssel
bleiben als Alias lesbar, wenn genau eine Kante passt. Mehrere Treffer
halten zur Neuauswahl an; keine Reihenfolge entscheidet über die Geometrie.
Eine explizite Auswahl muss vollständig auflösbar sein. Fehlt nur eine der
genannten Kanten, hält der ganze Bearbeitungsschritt an; die noch vorhandenen
Kanten werden nicht als stillschweigende Teilauswahl behandelt.

`edges.radial_rounding` bearbeitet positiv belegte Zylinderwände innerhalb
ihrer eigenen Randkurven. Ob eine Rundung überhaupt eine Kante ersetzt, fragt
`edges._around` bei der Erkennung nach (`perceive.features.planes_beside`),
mit der gemeinsamen Schwelle `units.UPRIGHT_TO_AXIS`; der Absagesatz
`edges.NOT_BETWEEN_TWO_PLANES` steht auch in der grauen Zeile des
Merkmalspanels. Eine gewölbte Wand des Baums, deren Facetten alle innerhalb
`features.NEARLY_FLAT_ANGLE` um ihre Mittelnormale liegen — eine Wand mit
Formschräge, wie eingelesene Halter sie tragen —, zählt dabei als Ebene
(`features.nearly_flat_mask`); dafür reisen die Merkmale des Objekts bis
`sharp_corner`, `unround` und `reround` mit. Ein konvexes Setzwerkzeug aus den Flächen (Kegel, Kuppel)
bekommt in `prepare_ops._placing_tool` einen Sockel in die Grundfläche und
spart die Hohlräume aus, die durch es laufen. Die ausgewählten Knoten skalieren radial samt
Sehnenunterteilungen; angrenzende Flächen müssen in ihren bisherigen Ebenen
bleiben. Ein geschlossener Zwischenkörper zwischen
alter und neuer Haut prüft boolesch auf fremdes Material und Wandverlust.
Sein Volumen muss auch zum Ergebnis mit der ursprünglichen Topologie passen;
Nullhäute einer bloßen Neuvernetzung werden damit kein Bestandteil des Modells.
Werden bisherige Dreiecksdiagonalen eines ebenen Randes durch die Änderung
ungültig, übernimmt stattdessen der geprüfte Schnitt dessen neue Triangulation.

`rounding_tool` baut den Werkzeugkörper: im Querschnitt der Zwickel zwischen
den zwei Flächen und dem Bogen, stückweise über den Zug gezogen. Wie fein der
Bogen wird, sagt `_arc_steps` — aus `units.MAX_FACET_SAG` und
`MAX_FACET_ANGLE`, denselben zwei Grenzen, mit denen OpenCASCADE tesselliert.
Eine feste Stückzahl wäre bei R = 30 zu grob und bei R = 0,5 Verschwendung.

Vollständig gewählte Eckknoten bekommen eigene Anschlussflächen. Der Knoten
stammt aus `MeshEdge.node_indices`, nicht aus gerundeten Ortskoordinaten.
Zwei zusammentreffende Kanten behalten den unmittelbaren Flankenschnitt.
Bei rein konvexen oder konkaven Knoten begrenzt der ursprüngliche
Normalenkegel den Kugelanschluss; ein Tetraeder aus den Berührpunkten
reicht dafür nicht. Mehr als drei Ebenen werden gemeinsam versetzt:
Gibt es mehrere Offsetzentren, verbindet sie die Minkowski-Summe des
versetzten lokalen Polyeders mit der Kugel. Die facettierte Kugel wird je
Operation einmal erzeugt und hält die Sehnenabweichung im Dreiecksinneren ein.

Fasen verbinden die tatsächlichen Schnittpunkte ihrer Flanken auf den
Nachbarflächen. Bei mehr als drei Flächen schließt deren ebene oder
facettierte konvexe Hülle die Ecke. Diese Mesh-Kappe kann von OpenCASCADEs
Splinekappe abweichen; Flankenabstände und Kontaktpunkte bleiben exakt.
Die Eckwerkzeuge werden gemeinsam mit den Kantenwerkzeugen geschnitten.
Ein Knoten, dessen Kontaktpunkte keinen Körper ergeben, bekommt **keine**
Haube: Die Flanken schneiden dort auch ohne sie, und eine fremde Ausnahme aus
der Hüllenrechnung wäre beim Kunden ein Programmfehler (`_corner_hull`).

Der gemischte orthogonale Dreiflächenknoten verwendet einen örtlich
begrenzten Ebenen- oder Torusübergang, auch in der komplementären Innenform.
Seine drei Zylinder teilen die feinere Winkelunterteilung der Torusfläche;
beide Parameterrichtungen teilen sich die zulässige Sehnenabweichung.
Die Auswahl wird zuerst im Weltsystem aufgelöst. Die Rechnung erfolgt im
Rahmen des gemischten Knotens; nur das aus den Float64-Rechenschritten
abgeleitete Rauschen an seinen drei belegten Ebenen wird bereinigt.
Knoten-IDs und Materialslots bleiben beim Hin- und Rückweg erhalten.
Unabhängige Gruppen gewählter Züge rechnen nacheinander in ihren eigenen
Rahmen, auch auf demselben Körper. Gemeinsame ursprüngliche Knoten bestimmen
die Gruppen; ihre Reihenfolge folgt der ursprünglichen Auswahlliste.
Die Ausgangspunkte und Normalen bleiben maßgeblich: Nach einer Gruppe sind
deren Knotennummern keine Vertexindizes des neu vernetzten Zwischenkörpers.
Rechenstufen und Befunde aller Gruppen gehen ins gemeinsame Ergebnis ein.
Die fünf künstlichen Kontaktseiten des Ersatzkörpers überlappen den
Anschluss um `EPS_GEOM`; die echte Oberfläche und die Kurven bleiben stehen.
Die ursprünglichen Kontaktflanken der drei Kantenwerkzeuge verwenden
denselben numerischen Überlapp statt einer Zugabe zum Bauteilmaß.
Vor einem lokalen Materialersatz müssen die tatsächlichen Eingangsflächen
und das Volumen den drei ursprünglichen Ebenen entsprechen. Ein weiteres
Detail im Bereich hält mit einem Vorschlag für ein kleineres Maß an.
Alle Booleschen Vorbereitungen tragen ihre Rechenstufe und Befunde bis zum
Operationsergebnis weiter.

**Den Überstand an den Enden bekommt, was abgezogen wird — nicht, was außen
liegt.** Beim Verrunden fällt beides zusammen (außen abziehen, innen
vereinigen), beim Wegnehmen einer Rundung nicht: Dort wird außen *vereinigt*,
und ein Überstand klebt an, statt zu helfen.
An einem gemischten Eckanschluss enden die Kantenwerkzeuge genau am Knoten;
ein Überstand könnte auf dessen anderer Seite eine innere Fehlstelle schneiden.

`unround` und `reround` gehen den Weg zurück: `sharp_corner` rechnet aus einer
erkannten Rundung die Kante, die sie ersetzt hat — über den **Schnitt der zwei
Nachbarebenen** und nicht über den Radius, denn der stammt aus einem Sehnenzug
und ist ein wenig zu klein (2,9772 an einer Rundung von 3,0). Der Füllkörper
ist der Zwickel **ohne** Bogen; er deckt die Rundung ab, und seine Flanken
liegen in den Nachbarebenen, wo ohnehin Material ist.
Beim erneuten Verrunden geht das vollständige `MeshData` aus `unround` in
`round_edges` weiter. So können beide Booleschen Schritte die Materialslots
erhaltener Flächen übertragen; ein Neuaufbau allein aus `raw` verlöre sie.

`bead_edges` legt einen **Wulst** auf: ein Rundstab auf der Kante, je Stück ein
Zylinder und je Knick eine Kugel. Die Stücke gehen einzeln in die Kette —
zusammengelegt überlappen sie sich, und ein Körper mit doppelt belegtem Raum
hat kein Volumen (24250 statt 24186). **Die Kehlnaht im Innenwinkel ist nicht
die glatte Hohlkehle**: Die macht `round_edges` an einer konkaven Kante, und
der Unterschied ist der Faktor zwischen 104,45 mm³ und 28,97.

Zylinder **und** Kugel hängen dabei am Radius: `_ring_steps` für den Umlauf,
`_ball` für den Knoten. Die Kugel des Wulstes hält nur die Sehnengrenze, die
des Eckanschlusses zusätzlich die Winkelgrenze — dort ersetzt sie die Flächen
der angrenzenden Zylinder, hier füllt sie nur deren Zwickel, und der
Unterschied ist eine Unterteilung, also viermal so viele Dreiecke.

**Messen und Schneiden**

`measure.py` (§18.3 — Abstand, Wandstärke, Winkel, und der **Fang**: `visible_edges` und `corner_points` sagen, was im Bild überhaupt eine Kante oder eine Ecke ist, `snap` zieht den Klick darauf) · `section.py` (Ebene durch einen Körper, §18.2) ·
`difference.py` (was eine Änderung hinzugefügt und was sie entfernt hat —
**ab wann das eine Änderung ist, sagt der Drucker**:
`Profile.smallest_printable_volume`, dieselbe Grenze und dieselbe Begründung
wie bei `boolean.without_effect`. Die Szene bringt das Profil mit; ohne eines
bleibt es beim Vernetzungsrauschen, denn wer keinen Drucker kennt, soll keinen
erfinden — Regel 7, RM-097)

`section.clip_triangles` begrenzt lose Markierungsdreiecke an denselben
Halbräumen wie Körper. Es bleibt eine offene Anzeigefläche ohne zusätzliche
Kappen; die übergebenen Eckpunkte und der ursprüngliche Körper bleiben erhalten.

**Netz, Farbe, Text**

`mesh_ops.py` (Arbeit am Netz selbst) · `colour_ops.py` · `paint.py` (Flächen
in ein Filament färben) · `texture.py` (von einer Textur zu druckbaren Slots)
· `label_ops.py` (Text und Logos auf einer Fläche; die Schriften dazu liegen
in `data/fonts/`)

**Eine Beschriftung sieht überall gleich aus, oder sie ist keine.** Ein Projekt
wandert zwischen Rechnern, und eine Systemschrift, die es hier gibt und dort
nicht, macht daraus zwei verschiedene Teile. Angeboten wird deshalb nur, was
mitreist: DejaVu bringt matplotlib mit, Liberation, Comfortaa und Dancing
Script liegen in `data/fonts/` (SIL OFL, Lizenztexte unter
`knowledge/data/third_party_licenses/`, Zuordnung in `BUNDLED_FONT_LICENCES`).
`FONT_STYLES` holt fett und kursiv über `weight` und `style` aus denselben
Dateien, die ohnehin im Paket liegen.

**Nicht jede Familie hat alle vier.** Comfortaa und Dancing Script sind
*variable* Schriften — eine Datei mit einer Gewichtsachse, die matplotlib nicht
instanziieren kann. „Fett" liefert dort dieselben Umrisse, und der Riegel für
die Familie greift nicht, weil die ja da ist. `FONT_STYLES_AVAILABLE` sagt
deshalb je Familie, was es wirklich gibt, und `FONTS_WITH_ALL_STYLES` daneben
ist dieselbe Auskunft für den Dialog: Das Feld *Schnitt* hängt über
`depends_on` an der Schrift und graut aus, wo es nichts zu wählen gibt — statt
anzubieten und danach abzulehnen.

**Und was zu dünn zum Drucken ist, misst `stroke_width` am gesetzten Text.**
Doppelte Fläche durch Umfang über die Umrisse, die die Operation ohnehin baut;
`too_thin_to_print` rechnet daraus die Höhe, ab der es trägt. **Keine Tabelle je
Familie** — eine solche hing an einem Beispielwort, verschwieg den Schnitt (fett
ist rund anderthalbmal so breit) und wäre acht Zahlen gewesen, die niemand
nachmisst. Verglichen wird gegen `narrowest_bead`, die schmalste Bahn dieses
Druckers: `NARROW_LINE_SHARE` aus `slice/advise.py`, dieselbe Zahl wie beim
Wandvorschlag und nicht der Düsendurchmesser. Die Operation macht daraus einen
Befund mit der Zahl, keine Sperre: Wer nur ansehen oder exportieren will, darf
klein bleiben.

**Und matplotlib fällt still zurück.** Wer eine Schrift verlangt, die fehlt,
bekommt keine Ausnahme, sondern DejaVu Sans und eine Zeile auf der
Fehlerausgabe. `font_properties` prüft deshalb nach, welche **Familie** die
gefundene Datei führt (`get_font(...).family_name`), und sagt es (Regel 21) —
die zweite Hürde hinter der Spec, die den Ordner mitnimmt. Am Dateinamen
gemessen wäre der Riegel halb: „DejaVu" steht auch in `DejaVuSans.ttf`, wenn
„DejaVu Serif" gemeint war.

## Was eine Operation hier einhalten muss

1. Registereintrag in `registry/` — ohne ihn gibt es sie nicht
2. Umsetzung als `OpFn`; Boolesches über die Kette, benutzte Stufe in `solver`
3. Bei Zufall: Startwert aus `ctx.seed`, `deterministic=False`
4. **Beide Qualitätsstufen bedienen** (`ctx.quality`)
5. Befunde als `findings` zurückgeben, nicht selbst protokollieren
6. Geometrietest gegen den Korpus in `tests/data/`
7. Texte übersetzbar, alle fünf Kataloge ziehen nach

## Grenzen

- **Freie Platzierung verwendet den gemeinsamen `frame_of()`-Rahmen.**
  Bei `drill_hole`, `move_feature` und `duplicate_feature` bewahrt der
  Nullvektor die frühere Achsen- beziehungsweise Verschiebungssemantik.
  Die freie Bohrungsnormale zeigt vom Material weg; ihr Werkzeug verläuft
  ab der Mündung nach lokal -Z. `drill_tool()` erzeugt auch Aufweitung und
  Übergang als einen geschlossenen Rotationskörper. Die tatsächliche Op
  und ihre Vorschau verwenden das Material des Zielkörpers.
  Das Werkzeug reicht exakt von null bis zur negativen Eingabetiefe; ein
  Blindboden erhält keine Überlappungszugabe, auch nicht beim Mittenanker.
  Durchgangsaufrufer wählen ausdrücklich größere Höhen. An den bekannten
  lokalen Werkzeugenden bereinigt `drill()` ausschließlich Float64-Rauschen
  der Koordinatentransformation, je Vertex begrenzt durch die wirklichen
  Matrixterme. Echte Flächenabstände oberhalb dieser Rechengrenze bleiben
  erhalten; Materialtoleranz und globale Schweißtoleranz ändern sich nicht.
- **Merkmalswerkzeuge umfassen die belegte vollständige Form.**
  `feature_placement_geometry()` bestimmt den wirklichen Materialanschluss
  und schließt zusammenhängende Bohrketten gemeinsam. `x/y/z` bleiben die
  Zielmitte des gewählten Merkmals; ein lokaler Versatz verbindet sie mit der
  angeklickten Mündung oder Basis. Weitere Kettenglieder behalten beim
  Versetzen ihre Kennungen und bekommen beim Kopieren jeweils neue.
- **Textvorschauen verwenden echte Konturen.** `local_text_body()` wird von
  der Operation und der Platzierung verwendet; lokale Drehung und
  Überlappung entstehen nur einmal. Der Anzeigeaktor verändert keine
  gespeicherte Geometrie. **Jeder Parameter der Form reist mit** — auch der
  Schnitt: Er fehlte in `scene/placement.py`, und die Vorschau zeigte den
  normalen, während die Operation den fetten baute.

- **Millimeter, doppelte Genauigkeit.** Vergleich über `units.is_close()`,
  nie mit `==`.
- **Keine Zahlenkonstante für Toleranzen** — `auto:<material>` verweist ins
  Materialprofil (Regel 7).
- **Nie eine Eingabe verändern.** `OpResult.outputs` sind neue Objekte.
- **Der Sehnenzug wird benannt, nicht versteckt.** Eine Verrundung am Netz
  ist ein Vieleck; wie fein, entscheidet `units.MAX_FACET_SAG` — dieselbe
  Zahl, mit der der exakte Kern tesselliert. Wer eine echte Kurve braucht,
  arbeitet an einem `brep`-Körper weiter, und der `caveat` der Operation sagt
  das auch.

## Innenraum und verlustfreie Netze

`MeshData.cavity` ist eine optionale, geschlossene Schnittgeometrie des
tatsächlich ausgehöhlten Innenraums. Sie hat höchstens eine Ebene und reist
als eigene Vertex-/Flächentabellen im NPZ-Cache. `transform.apply` führt
dieselbe Matrix auf beiden Netzen aus; sonstige Geometrieänderungen verwerfen
die Auskunft, solange kein belegbarer Folgeraum berechnet wird.
`lattice_fill` beschneidet das Gitter auf diesen Raum. Ohne Auskunft sind nur
geschlossene, nach innen gerichtete Innenschalen eine eindeutige Grundlage.
Ein Hüllquader oder eine konvexe Hülle ersetzt keinen Innenraum.

Neuvernetzung überträgt Slots über `attributes.transfer`; Skulptur-Etappen
verwenden das verlustfreie NPZ statt STL. Beim Lesen aus Projektquellen werden
NPY-Header und entpackte Größe vor der Array-Allokation geprüft.
`measure.surface_gap` verwendet den räumlichen Index von Manifold mit
`Mesh64`; fehlende Körperübernahme ist keine Abstandsaussage.
