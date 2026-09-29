# P1.4c: unabhängiger Review der UI-/Kernelgrenze

Lesestand: eingefrorener P1.4b-Baum während des Entwicklungstors. Geprüft wurden
der native Referenzplan und die unten benannten tatsächlichen Aufrufer. Keine
Produktdatei geändert, kein Test und keine Sonde gestartet. Diese Notiz belegt
Schnittstellen und fehlende Anschlüsse; sie behauptet keine bisher ungeprüfte
OCCT-Historienleistung.

## 1. Kleinste sichere Zwischenstufe

**Direkte aktuelle Vollflächenauswahl für `push_faces` und `unround` ist ein
eigenständiger sinnvoller erster Abschnitt.** Er braucht weder eine neue
Kantenfrage noch eine Änderung des bisherigen Fragekontexts. Er beweist den
Transport einer bereits am aktuellen Eigentümer gewählten Fläche bis zur
privaten Arbeitsform. Er beweist noch keine Fortführung historischer Namen.

Die beiden Kernel-Einstiege erhalten einen zusätzlichen Schlüsselparameter:

```python
selected_faces: Sequence[int] | None = None
```

Der Indexraum ist ausdrücklich `solid.faces()`, niemals Merkmalsnummer oder
Tessellierungsdreieck. `None` lässt die vorhandenen älteren Richtungs-/Lagewege
bestehen. Eine ausdrücklich übergebene leere, ungültige oder unvollständige
Auswahl ist ein Auswahlfehler und fällt nicht auf diese Wege zurück.

Konkrete Anschlüsse:

- `geom/face_ops.py:_chosen_face` liest das Merkmal bereits aus
  `source.features`. `_on_a_solid` gibt heute nur Normale und Mitte weiter.
  Dort kommt die vollständige native Auswahl aus
  `body.complete_faces_of_triangles(chosen.face_indices)` hinzu.
- `brep/profiles.py:push_faces` kopiert bereits mit `replace(solid)`. Die
  ausdrückliche Auswahl wird durch die echte Kopierabbildung nachgeführt;
  `_facing` und `_nearest_face` werden in diesem Zweig nicht mehr aufgerufen.
  Trägerprüfung, tatsächliche Trimmung, Normalenrichtung, Prismenerzeugung und
  Ergebnisprüfung bleiben im bestehenden Algorithmus.
- `geom/prepare_ops.py:_exact_fillet` liest das Rundungsmerkmal ebenfalls am
  aktuellen Eigentümer. Für **Entfernen** reicht es dessen vollständige
  native Auswahl an `brep/edit.py:unround` weiter. Der Builder erhält genau
  diese privaten Flächen, keine neue `_cylinder_at`-Suche.
- Mehrteilige Merkmale werden nicht auf das erste Element verkürzt. Der
  bestehende Builder kann mehrere `AddFaceToRemove`-Aufrufe entgegennehmen;
  welche zusammengehörige Auswahl fachlich erlaubt ist und welches Ergebnis
  sie liefert, muss die Umsetzung an echten Körpern prüfen. Numerisch gültige
  Indizes allein machen beispielsweise eine beliebige Ebene nicht zur Rundung.

Der Radiuswechsel bleibt in dieser Zwischenstufe unverändert verfügbar. Er
darf aber noch nicht als vollständig angeschlossene ausdrückliche Neuwahl
ausgegeben werden. Ebenso bleiben allgemeine native Namensfortführung,
Kantenneuwahl und deren Antwortpersistenz eigene offene Anschlüsse.

Als spätere funktionale Abnahme genügen hier nicht Mittelpunktvergleiche:
zwei nahe, getrennte, gleichgerichtete Flächen mit ausgewählter fernerer Fläche;
mehrere gleich große Rundungen mit ausgewählter anderer Rundung; eine Auswahl
mit mehreren tatsächlichen nativen Flächen; Quelle vor/nach nativ unverändert;
Abbruch vor der Kopie und vor/nach dem Builder. Diese Fälle wurden im Review
nicht ausgeführt.

## 2. Bestehende Selektoren und Kopie verwenden

| Aufgabe | Vorhandener Weg | Konsequenz für die vorgeschlagene API |
|---|---|---|
| Aktuelles Merkmal lesen | `SceneObject.features`, etwa `_chosen_face` und `_exact_fillet` | Ein loses `Feature` beweist seinen Eigentümer nicht. |
| Dreiecke zu nativen Flächen | `Solid.faces_of_triangles` | Bereits validiert, einschließlich negativer/ungültiger Dreiecksindices. Nicht neu implementieren. |
| Vollständige native Auswahl | `Solid.complete_faces_of_triangles` | Bereits echte vollständige Abdeckung, keine bloße Indexgültigkeit. Der Aufrufer verwirft zusätzlich die leere Auswahl. |
| Native Arbeitskopie | `replace(solid)` → `Solid.__post_init__` → `copy_shape` | Bewahrt bestehende Attribute und Deflection; erzeugt eine private Form und kalten Cache. |
| Tatsächliche Kopierzuordnung | `copy_shape`, `Solid._copied_faces` | `ModifiedShape` plus `TopExp`-Maps, keine angenommene Besuchsreihenfolge. |
| Transformation mit Flächenzuordnung | `edit.transformed_with_faces`, `geom/transform.py:moved_object` | Bestehende vollständige Flächen-/Teilträgerprüfung wiederverwenden; die im Plan genannte Funktion `apply` heißt tatsächlich `moved_object`. |
| Kantenregel und Schlüssel | `geom/edges.py:edge_key`, `choose`, `named_edges`, `wanted` | Schon gemeinsame Quelle für Mesh und BRep; kein zweiter gerundeter Schlüssel oder zweiter Toleranzresolver. |

`native_feature_faces(solid, feature, ...)` würde in der vorgeschlagenen Form
nur zwei vorhandene Methoden umschalten. Der angekündigte Eigentumsbeleg steckt
nicht in seiner Signatur: Ein fremdes Feature mit zufällig gültigen Zahlen ist
dadurch nicht erkennbar. **Für die Zwischenstufe diese zusätzliche API
weglassen** und den schon vorhandenen Lookup am `SceneObject` unmittelbar mit
der bestehenden Vollständigkeitsmethode verbinden. Erst wenn tatsächlich
mehrere Aufrufer dieselbe Eigentümer-/Art-/Auswahlprüfung brauchen, wäre ein
gemeinsamer Helfer mit `SceneObject` und `FeatureId` statt losem Feature sinnvoll.

`copy_selected_faces(solid, face_indices, cancelled=...) -> (working, indices)`
ist dagegen ein vertretbarer kleiner öffentlicher Anschluss an die bislang
interne Kopierabbildung, sofern er **ausschließlich** eine private
`replace(solid)`-Kopie erstellt und deren `_copied_faces` benutzt. Er ersetzt
die bisherigen Kopien in beiden Verbrauchern. Er darf weder einen zweiten
Kopieralgorithmus einführen noch erst mit `BRepBuilderAPI_Copy` und danach
nochmals mit `Solid(...)` kopieren und die erste Zuordnung weiterreichen.
Gültigkeit, Ganzzahligkeit und Grenzen der nativen Auswahl werden vor der
Zuordnung geprüft; Abbruch vor und nach dem nativen Kopierer sowie beim
Zusammenstellen der Auswahl. Kein Teilcache oder Builder wird veröffentlicht.

Für den späteren Kantenabschnitt fehlt eine echte Edge-Kopierabbildung.
`_copied_faces` ist dafür ungeeignet. Eine analoge schmale
`copy_selected_edges`-API darf dieselbe erweiterte Kopierprimitive verwenden;
**kein unabhängiger zweiter Kopierweg**. Die Abbildung muss Quellen- und
Zielform mit `TopAbs_EDGE` und `ModifiedShape` verbinden. Die Position in
`edges_of(solid)` ist dabei kein nativer Kantenindex: Diese Liste filtert
Nullkanten und Nähte. Eine aktuelle `EdgeInfo.edge` wird zunächst durch echte
Mitgliedschaft in der `solid.edges()`-Map ihrem Eigentümer zugeordnet.

`carried_face_slots` bleibt ein Attributtransport. Sein früher Rücksprung ohne
Filamentwerte und seine Zusammenführungsregeln sind kein allgemeiner
Merkmals- oder Kantenidentitätsbeleg.

## 3. Was bei `reround` tatsächlich noch fehlt

Die Übergabe von `selected_faces` allein schließt den Radiuswechsel nicht:

1. `reround` ruft zunächst `radial_rounding`; auch dort steht derzeit eine
   `_cylinder_at`-Suche. Der Offsetzweig muss später dieselbe ausdrückliche
   Auswahl erhalten.
2. Im anderen Zweig ruft es `unround` auf. Dieses gibt nur den fertigen Solid
   zurück; der Builder wird nicht an `reround` weitergegeben.
3. Anschließend wählt `reround` mit
   `min(edges_of(sharp), key=Abstand_zur_alten_Mitte)` eine Kante und reicht
   deren gerundeten `edge_key` an `fillet`. Damit gehen ausdrückliche Auswahl
   und Kollisionsschutz ein zweites Mal verloren.

**Zur vorhandenen Defeaturing-Historie:** `unround` übergibt den tatsächlichen
Builder bereits an `working.replacing(..., history=builder)`. Der bestehende
Attributweg liest daraus, soweit verfügbar, `Modified(face)`. Es gibt also
einen vorhandenen Anschluss für Builder-Herkunft. Im Repository steht jedoch
kein Nachweis, dass die entfernte Rundungsfläche damit eindeutig ihre neu
entstandene scharfe Kante liefert. Auch eine verfügbare `Generated`- oder
`Modified`-Methode wäre noch kein solcher fachlicher Nachweis; die Kante kann
aus dem erneuten Schnitt verlängerter Nachbarflächen entstehen.

Die nächste Umsetzung muss deshalb einmal reproduzierbar belegen, welche
unveränderten/veränderten Nachbarflächen und gemeinsamen Ergebnisränder der
Builder für mehrere nahe Rundungen tatsächlich meldet. Die ausgewählte
Rundungsfläche, ihre echten Randnachbarn und das Ergebnis müssen dabei
topologisch zusammenpassen; Quellenbytes und alle anderen Rundungen bleiben
Kontrollen. Ergibt die Historie einen vollständigen eindeutigen Zusammenhang,
kann ein enger interner `unround`-Helfer ihn zusammen mit dem Ergebnis an
`reround` zurückgeben. Eine allgemeine Topologienamensbibliothek ist dafür
nicht nötig. Ergibt sie ihn nicht, braucht der vollständige Anschluss einen
eigens belegten geometrisch-topologischen Nachweis oder eine ausdrückliche
Wahl am **scharfen Zwischenkörper**. Die nächstgelegene Mitte ist keiner.

Eine solche Gegenprobe ist noch offen und wurde wegen des laufenden Tors hier
nicht gestartet. Die Zwischenstufe aus Abschnitt 1 hängt nicht von ihr ab.

## 4. Für echte Kantenwahl den äußeren Fragekanal typisieren

Der Satz im Plan zu `FeatureQuestionContext` trifft die falsche Schicht.
Dieser Typ in `scene/evaluate.py` ist nur der interne Adapter für **bereits
erkannte Operationsausgaben**. Er kann unverändert schmal bleiben.

Erweitert werden muss der gemeinsame äußere Vertrag:

```python
QuestionContext(preview: EvaluationResult | None,
                candidates: tuple[QuestionTarget, ...]) -> None
```

Empfohlene zwei klar unterscheidbare reine Datenträger, keine freie
Wörterbuchstruktur und keine als `FeatureId` getarnte Kante:

- Merkmalsziel: Antworttoken plus vorhandener `FeatureRef`.
- Kantenziel: Antworttoken, aktueller `ObjectId`, die am tatsächlichen
  Kandidaten erzeugte unveränderliche Polylinie und die bereits vorhandenen
  Anzeigefakten `middle`, `length`, `upright`, `flat`.

Das ist eine Darstellungsauskunft, keine zweite Geometrieeinpassung. Die
Fakten werden aus derselben `EdgeInfo`/`MeshEdge` übernommen; damit kann
`ui/labels.py:edge_label` weiterverwendet werden. `direction` und `extent`
für die Wiedererkennung bleiben im Kern. Insbesondere ist `EdgeInfo.extent`
heute aus `edge_points` abgetastet und kein analytischer Kurvenidentitätsbeweis.
Native Handles, Builder und dauerhafte Topologieindices gelangen nicht ins
Ask-Paket oder in die Projektdatei. Die Token→tatsächliche-Auswahl-Zuordnung
bleibt auf den laufenden aktuellen Körper begrenzt.

Die native Darstellungsgeometrie liefert bereits `brep/edit.py:edge_points`,
der Meshweg bereits `MeshEdge.points`. Gleiche vorhandene Deflection verwenden,
keine zweite Kurvenabtastung mit neuer Toleranz. Die Kandidatenvorbereitung
gehört in den Arbeiter und führt `ctx.cancelled` weiter; nicht alle Kurven
während eines UI-Callbacks synchron neu berechnen.

Der vorhandene Weg `Session.announce_question` → fadenlokaler Kontext →
`AskRequest` → `MainWindow._on_ask` bleibt **der eine** Frageweg. Seine
Projekt-/Arbeiterbindung, tatsächliche Vorschau, `sceneApplied`-Schranke,
Abbruchfreigabe und Wiederherstellung vor `reply` werden mitverwendet.
`AskFn` bleibt Text plus Antworttoken. `AskDialog` besitzt bereits `UserRole`
für den unveränderten Antwortwert und abgesicherte Annahmepfade einschließlich
Enter/Doppelklick; eine optionale Token→Anzeigetext-Zuordnung genügt dort.

`Viewport.show_candidates/_redraw_candidates` erhält einen zweiten Zeichenfall
in **derselben** Kandidaten-/Actorverwaltung. Linienzeichnung,
`_shown_offset`, `_in_pick_view`, Hervorhebung und Vordergrundbehandlung aus
`_redraw_edge_patch` können gemeinsam verwendet werden. Dagegen sind diese
Abkürzungen falsch:

- `select_edge(key)` verändert die normale Auswahl und findet eine einzelne
  Kante wieder über den möglicherweise kollidierenden Schlüssel.
- `_edge_names` baut ein Wörterbuch nach `edge_key`; zwei unterschiedliche
  Kandidaten würden zusammenfallen.
- `_prepared_edges`/`_edge_info` sind für normale Schlüsselauswahl ausgelegt:
  die Infomap überschreibt gleiche Schlüssel, während die Linienauswahl den
  ersten Treffer nimmt. Fragekandidaten brauchen ihre eigenen **Fragetoken**
  als Zeilenkennung innerhalb der bestehenden Kandidatenverwaltung.
- `EdgeSetField` ist der dauerhafte Parametereditor für Schlüsselbündel,
  nicht der Speicher für kurzlebige Fragetoken. Seine Gruppenauswahlregel und
  die gemeinsame `wanted`-Prüfung bleiben bestehen.

## 5. Fehlender realer Aufrufer zwischen Frage und Kernel

Die native Kantenarbeit läuft in `geom/edge_ops.py:_on_a_solid` →
`brep/edit.py:fillet/chamfer`, **bevor** `evaluate` den lokalen
`FeatureQuestionContext` für Ausgaben erstellt. `OpContext` hat derzeit nur
`ask`, aber weder Darstellungsadapter noch eine aufgelöste Kantenauswahl.
Nur den Typ des Nach-Erkennungsadapters zu ändern, erreicht diesen Aufrufer
deshalb nicht.

Der spätere vollständige Anschluss benötigt einen Eingangsschritt in
`evaluate`, der das registrierte ausdrücklich gewählte Kantenbündel am
aktuellen `SceneObject` vollständig bindet. Er benutzt den gemeinsamen
äußeren Fragekanal und stellt der Operation die **einmal gebundene** aktuelle
Auswahl bereit. Der Kernel erhält sie als optionalen ausdrücklichen Selektor
und führt sie über die private Kopie weiter; er schlägt anschließend keine
gerundeten Schlüssel erneut nach. Der normale eindeutige Schlüsselweg und
die Auswahlarten aus `geom/edges.py` bleiben dieselben für beide Körperarten.

Diese Bindung muss vor dem relevanten Operationscachetreffer feststehen:
`evaluate` fragt den Cache heute vor dem Op-Aufruf ab. Eine neue Frage nur
innerhalb von `fillet` würde bei warmem Cache vollständig übersprungen.
Außerdem ändert eine andere Kantenantwort die **Geometrie des Konsumenten**,
während P1.4b Merkmalsnamen nach dessen Geometrieausführung bindet. Der neue
Anschluss braucht daher die effektive Kantenbindung im Ausführungsschlüssel
dieses Konsumenten; ein unveränderter Eingangs-Featurehash allein reicht nicht.
Das ist eine neue P1.4c-Anforderung, kein erneuter Befund am abgeschlossenen
P1.4b-Folgecachefix.

Der genaue kleine `OpContext`-Zusatz sollte erst mit diesem tatsächlichen
Vorbindungsschritt festgelegt werden. Eine zweite Fragenverwaltung oder eine
neue hart codierte Operationsliste wäre jetzt ein Zwilling. Für die empfohlene
erste Vollflächenstufe ist der Zusatz überhaupt nicht erforderlich.

## Ergebnis

Zuerst aktuelle vollständige Flächen über vorhandene Auswahl- und
Kopierbelege direkt an `push_faces` und `unround` anschließen. Die bisherigen
unbenannten Modi und `reround` bleiben verfügbar. Für den danach folgenden
vollständigen Referenzanschluss sind der typisierte äußere Fragekanal, die
Eingangsbindung vor dem Cache, eine echte Edge-Kopierabbildung und beide
Übergänge des Radiuswechsels erforderlich. Keiner dieser offenen Teile ist
durch eine bloße Namenübernahme oder die vorhandene Filamenthistorie erfüllt.
