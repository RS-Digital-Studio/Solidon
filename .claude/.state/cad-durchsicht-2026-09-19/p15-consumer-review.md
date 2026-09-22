# P1.5 – gemeinsamer Merkmalsanschluss an seine Verbraucher

Rein lesende Vorbereitung auf Basis von `p15-entry-plan.md`, Konzept P1.5
und Recherche §§3/5.4. Keine Tests, Sonden oder Fensterfahrten ausgeführt;
keine Produktdatei geändert. Aussagen über Kontrollfluss sind keine
abgeschlossene Geometrie- oder Kundenabnahme.

## Tragfähiger Bestand

`Feature` ist bereits das gemeinsame Vokabular beider Kerne. `params`,
`face_indices`, `created_by`, `measure_sources` und `surface_patches` trennen
Werte, Auswahl, Herkunft und belegte Originalhaut. `recognised` sagt, ob ein
deklarierter Name wiedererkannt wurde; es ist kein allgemeines Gütesiegel
für vollständige Form oder sichere Bearbeitbarkeit (`types.py:286/314`).

`SurfacePatch` belegt einen analytischen Träger auf ausdrücklich benannten
Originaldreiecken. Ein Kegel-, Zylinder- oder Ebenenträger beweist allein weder
eine vollständige Bohrung noch deren eigenen Bearbeitungsumfang. Native
`features_of` verbindet Topologie, gerichtete Materialseite und wirkliche
Trimmung; abschließendes `clipped_patches` gibt nativen Belegen Vorrang.
Offene Rundmäntel benutzen teilweise den gemeinsamen Netzfit. Dessen
Maßquellen werden nicht durch das abschließende native Trägerpatch automatisch
zu nativen Maßen (`brep/features.py:185–260`). Das sind getrennte Auskünfte,
kein Anlass zu einer pauschalen Hochstufung.

`cavity_chain_state_at` und `cavity_chains` liefern bereits zusammengehörige
Bohrungs-/Senkungsabschnitte. Vollständig gemeinsame Randringe und Schultern
tragen die Verbindung; drei Ringbesitzer, doppelte Flächenbelegung und
verzweigte/ungültige Ketten werden nicht zu einer beliebigen sicheren Kette.
`FeatureActionGroup` ergänzt operationsabhängige Mitglieder, vollständigen
`scope`, Nachweise und begründete `uncertain`-Einträge. Diese Verträge weiter
anschließen; keine zweite Gruppenverwaltung oder zweite Maßrechnung bauen.

## Datei-/Verbrauchermatrix

| Bereich / konkrete Stellen | Bereits gemeinsam | Noch zu schließen oder bewusst begrenzt |
|---|---|---|
| `types.py:286/314`, `perceive/surfaces.py`, `brep/features.py:99`, `perceive/features.py` | Gemeinsame Feature-/Träger- und Maßquellen, Originaldreiecke; native und gemessene Werte bleiben unterscheidbar | `partial`, `open`, `radial`, `recess` sind fachliche Einzelangaben. Eine allgemeine sichere Bearbeitbarkeit folgt weder aus `kind` noch aus `measure_sources` |
| `features.py:5000`, `local.py:191` | Globale und lokale Erkennung benutzen denselben Ebenenweg; lokale Rückzuordnung erhält Originalindizes und Träger | Die absolute 4-mm²-Grenze wirkt auch lokal; echtes Anklicken umgeht sie nicht |
| `relations.py:756–938/1389` | Randgraph, Ketten, Schultern, getrennte Berührung und Gruppenunsicherheit | Kandidaten sind ausschließlich innere `hole`/`cone`. Slot-/Taschenkontakte und allgemein überlappende Deutungen sind damit nicht vollständig beschrieben. `invalid` wird im Gruppenweg als Grund erhalten, in `cavity_chain_state_at` jedoch nicht als eigene Auskunft zurückgegeben |
| `relations.py:1162/1260/1507` | Maßänderung und vollständige Formhandlung werden getrennt geprüft; Rolle und Kettenumfang bleiben erhalten | Vollformvergleich enthält Vernetzungsmerkmale und trennt dadurch auch geometrisch identische, anders unterteilte Flächen |
| `panels.py:1679/5366`, `viewport.py:9388/9631` | Baum schachtelt dieselben Ketten; Markierung erweitert auf denselben Umfang und Originaldreiecke | Bei überlappender Auswahl verliert der Ortsfang die Mehrdeutigkeit wieder; siehe unten. Das Panel lässt `action.op is None` weg (`panels.py:5490`), daher erreicht ein vorhandener Ablehnungsgrund nicht automatisch den sichtbaren Kundenweg |
| `scene/placement.py:128/946`, `ui/labels.py:2093/2149` | Historischer Bohrschritt benutzt Kette/Erzeuger; aktuelle Maßwerte nutzen `measure_status`. Bezugsflächen und Kanten entstehen aus tatsächlicher Geometrie, Mitten/Achsen aus Features | `prepare_surface` prüft Planarität und Geometrie selbst, liest aber keine Gruppenunsicherheit. Das ist ein geometrischer Bezug, keine Zusage eines eindeutig selbstständig änderbaren Merkmals. Auch ohne benanntes Kleinflächen-Feature kann eine reale Dreiecksfläche weiterhin platzierbar sein |
| `panels.py:5476`, `main_window.py:13319` | Panel erhält `alike_for_actions`; Vorschau/Übernahme prüfen die aktuelle gleiche Gruppe erneut. `params_for_members` erhält eigene Orte, Bündel bleibt eine Transaktion | Der korrekte Auftragsweg hängt vollständig an richtiger Gruppen-/Umfangsauskunft; keine lokale UI-Ersatzgruppierung ergänzen |
| `perceive/digest.py:118/270`, `agent/context.py:143`, `agent/session.py:555` | Agent erhält dieselben einzelnen Features, Auswahlkennung, Maßquellen, Passungsbefunde und Rohrwandbeziehungen | Digest liefert keine Kettenmitglieder, `FeatureActionGroup.scope/uncertain` oder `actions_for`-Gründe. Vor einer Operation fehlt damit die Auskunft, die das Panel bereits benutzt |
| `geom/prepare_ops.py:820/2081/2557/2865/3360/4625/5375` | Dieselbe Kette steuert Einzelumfang, Platzierungswerkzeug, Bewegen/Drehen/Kopieren, Langlochsperre und Einlauf-Mitnahme beider Kerne | Ketten- und Berührungsgrenzen des gemeinsamen Erzeugers wirken bis hierher. Eine später abgelehnte Werkzeugbildung ersetzt keine vorher passende Auskunft an Auswahl und Agent |

## Belegte Grenzen und enge Folgerungen

**Kleine echte Fläche gegenüber Kugelfacette.**
`MIN_FACE_AREA = 4.0` wurde gegen 180 falsche Ebenen auf einer facettierten
Kugel eingeführt (`features.py:116–127`; bestehender Gegenfall
`test_features.py::test_a_generated_mesh_does_not_drown_in_faces`). Das bleibt
ein sinnvoller Schutz. Die damalige Begründung „unter 2 × 2 mm setzt niemand
etwas an“ ist dagegen keine ausreichende Grenze für P1.5. `_planar_face_entries`
verwirft jede 1-mm²-Ebene, auch bei lokalem Aufruf; `_describe` am nativen Kern
verlangt nur Fläche größer `EPS_GEOM` (`brep/features.py:1013`). Nicht einfach
den Schutz löschen: vorhandene Koplanarität, reale Kanten/Nachbarn und schon
belegte Rundträger müssen die echte kleine Funktionsfläche von Facetten einer
Rundung trennen. Der vorhandene Test mit einer kleinen Stiftoberseite liegt
oberhalb dieser absoluten Grenze und deckt 1 mm² nicht ab.

**Gleiche vollständige Form hängt noch an der Vernetzung.**
`relations._build_surface_patch` speichert Eckpunkte und drei Kantenlängen je
Dreieck. `_same_surface_patch` vergleicht diese Mengen mit `EPS_DISPLAY`
(`relations.py:1545–1598`). Schon eine reine Dreiecksunterteilung einer
unveränderten ebenen Teilfläche erzeugt andere Kantenlängen und neue Punkte;
die vollständige Formhandlung kann deshalb „verschieden“ liefern. Die
analytischen `Feature.surface_patches` werden dafür nicht gelesen. Der interne
Typ `_SurfacePatch` dient hier dem Vergleich der ganzen Auswahl und ist nicht
der analytische `types.SurfacePatch`. Den bestehenden Vergleich auf die
belegte Flächenabdeckung/Trimgrenze richten; bloße Radiusgleichheit wäre wegen
des vorhandenen Kugel-/Kalottengegenfalls wiederum zu schwach.

**Ungültig, angeschnitten und überlappend ist noch nicht überall dieselbe
Aussage.** Der Gruppenweg unterscheidet `invalid` von einem sicheren
Einzelmerkmal (`_feature_group_topology`). Der Einzelweg gibt dagegen nur
Kette und `touching` zurück; ein ungültiger Rand ohne bereits belegte
Mehrfachbelegung kann `(None, False)` ergeben. `_stands_alone` wertet genau
dieses Paar als alleinstehend. Das ist ein belegter Informationsverlust,
noch kein Nachweis einer falschen fertigen Operation. Randkontakte anderer
Merkmalsarten fehlen bereits in der Kandidatenmenge. Diese Auskunft zuerst
an `relations` vervollständigen und den vorhandenen Grund-/Umfangsvertrag
durchreichen, statt in jedem Verbraucher neue Ausnahmen einzubauen.

Zusätzlich markiert `Viewport._feature_on_cell` mehrfach belegte Dreiecke
korrekt mit `-2` und liefert keinen eindeutigen Treffer. `_feature_hit` fällt
danach auf Dreiecksabstände zurück; bei gleichem Abstand gewinnt durch
`offset < best_offset` der erste vorbereitete Eintrag (`viewport.py:9661–9674`).
Eine berechtigte Eltern-/Kind-Auswahl muss von widersprüchlichen Kandidaten
unterschieden werden; derzeit kommt diese Unterscheidung dort nicht an.
Das ist statisch belegt, kein ausgeführter Fenstertest.

**Agentenanschluss.** `digest._object_lines` schreibt Einzelmerkmale und
`sleeves_of`, jedoch keine Hohlraumketten oder Handlungsgruppen. Die bestehende
lesende Steckbriefauskunft für die gewählte Stelle um dieselben Mitglieder,
Umfänge und Gründe erweitern, die das Panel schon liest. Kein zusätzlicher
Erkenner und kein Werkzeug nötig, das eigene Gruppen erfindet. Kosten- und
Abbruchanschluss einer größeren Gruppenauskunft gesondert berücksichtigen.

## Höchstens drei erste funktionale Gegenfallfamilien

1. **1-mm²-Funktionsfläche mit Rundungsgegenprobe.** Analytischer 1-mm-Würfel
   sowie kleine scharf begrenzte ebene Fläche an größerem Körper, jeweils
   B-Rep und Mesh mit zwei Unterteilungen. Fläche, Normale, Originalanteil,
   lokale Wiedererkennung und dieselbe benannte Auswahl nachweisen. Daneben
   unveränderten organischen/Kugelfacettenfall aus `test_features.py` halten:
   keine Flut falscher Ebenen. Vorhandene Dateien: `test_features.py`,
   `test_local_detection.py`, `test_brep_surfaces.py`.
2. **Gleicher vollständiger Umfang mit anderer Vernetzung.** Zwei gleiche
   Bohrungen bzw. dreigliedrige Profile aus `test_feature_groups.py`;
   an einer Kopie nur die vorhandenen Dreiecke unterteilen, ohne die
   Originalfläche zu ändern. Gleiche vollständige Sammelgruppe und eigener
   Ortsversatz müssen bleiben. Der vorhandene Halb-/Vollkugelgegenfall muss
   weiterhin trennen. Native Geschwister zusätzlich mit zwei
   Tessellierungsqualitäten vergleichen; Maßänderung und Vollformhandlung
   getrennt beurteilen.
3. **Gekoppelte Bohrung mit eindeutigem und offenem Umfang bis zum Verbraucher.**
   Vorhandenes Bohrung-/Kegel-/Schulterprofil aus `garden_pattern` bzw.
   `test_bore_mouth_resize.py` als kontrollierten Anfang benutzen, danach
   echten Flankenanschnitt und eine quer anschließende Höhlung vorsehen.
   Beide Kerne müssen denselben belegten Ketten-/Einzelumfang oder denselben
   begründeten unbekannten Zustand liefern; Nachbarflächen und Teilträger
   bleiben erhalten. Diese Aussage muss vor einer Handlung im Digest,
   Gruppenangebot und Operationsaufruf übereinstimmen. Vorhandenen
   Drei-Ringbesitzerfall mitnehmen; überlappende globale Auswahl zusätzlich
   als Release-Fensterfall vorbereiten. Aktuelle Fehlerausprägung der neuen
   realen Schnittkörper ist noch zu reproduzieren, nicht vorweg behauptet.

Nach diesen Gegenfällen erst den nötigen Vertragsausbau festlegen. Reale
Körper-/Nachbarinvarianten zählen mehr als gleiche Featurezahlen; keine
Produkt- oder Fensterabnahme ist durch diese Notiz ersetzt.
