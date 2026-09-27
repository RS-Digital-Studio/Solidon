# Begründungen zu `app/core/perceive/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss,
> Einstiege und Stolperfallen verdichtet wurde. Die Karte steht dort; hier
> stehen die ausführlichen Beschreibungen, Messwerte und Anlässe ihres Tages —
> wörtlich, gegliedert nach den Überschriften der Karte.

Grundlage ist die ungesicherte Zwischenfassung der Karte vom selben Tag. Wo sie
einen Absatz gegenüber dem letzten Commit gekürzt oder gestrichen hatte, steht
hier die längere Fassung aus dem Commit (*HEAD-Fassung*); wo sie Neues trug —
die Absätze aus der Paketübernahme der Durchsicht 0.5.1 —, steht ihr Wortlaut.
Ein Vermerk *Früher unter „…“* nennt die Stelle der alten Karte. Was davon
inzwischen als Regel in `.claude/rules/` steht, gilt dort; die Absätze hier
sind der Hintergrund.

## Vorspann

*Früher unter „Wozu das gut ist“, HEAD-Fassung.*

Ohne diese Schicht könnte der Agent nur Zahlen sehen. Mit ihr sieht er
„Bohrung Ø5 auf der Oberseite" — und der Nutzer kann sie anklicken, ohne dass
jemand Dreiecke zählt.

```
features.py   ──> „hier ist eine Bohrung, eine Tasche, eine Fase"
helix.py      ──> „hier ist ein Gewinde" — und darum sind die anderen weg
slots.py      ──> „diese zwei Bögen sind ein Langloch" — dieselbe Bauart
patterns.py   ──> „diese 196 Zellen sind ein Wabenmuster" — und Zellen für Entfernen und Ändern
relations.py  ──> „diese zwei gehören zusammen" — und was daraus folgt
matching.py   ──> derselbe Name auch nach der nächsten Operation
digest.py     ──> der Steckbrief: was der Agent zu sehen bekommt
maps.py       ──> Analysekarten für die Ansicht (Überhang, Wandstärke …)
actions.py    ──> „was kann ich damit tun“ — und warum nicht, wo nichts geht
local.py      ──> vollständige Merkmale in einer begrenzten Umgebung des Originalnetzes
ops.py        ──> gespeicherter Erkennungsauftrag `detect_region`
```

## Die Karte

*Früher unter „Die Karte“, HEAD-Fassung — die Tabelle vor der Kürzung.*

| Datei | Rolle |
|---|---|
| `features.py` | Merkmalserkennung (§21.1): Flächenformen einpassen und benennen; `detect_voids` belegt Hohlräume ohne Weg nach außen über vier Tore |
| `helix.py` | Wendelflächen (§21.1): Achse, Steigung, Gangtiefe. Ein eingelesener Bolzen bringt sonst je nach Größe drei bis zwanzig Merkmale mit, die es nicht gibt — die Flanke eines Gewindegangs ist örtlich eine Kegelfläche und passt sich sauber ein. Wo eine Wendel liegt, steht danach **ein** `thread` statt vieler Erfundener. Das Spektrum findet sie, der **Kantenleser** misst sie (`_measured_helix`, P2.5): Händigkeit aus dem Vorzeichen der Steigung jeder windenden Kante, Vorschub aus dem Wert, den die meisten Kanten tragen, Wendeln nach Radius und Phase (`_dense_parts` trennt zwei überbrückte, schneidet den Auslauf ab), Gangzahl aus ihrer Periodizität (`starts_from_periodicity`, eine Regel für beide Kerne), die Rille gegen `MEASURED_GROOVE_RANGE`; die Händigkeit heißt dann `facets` und ist belegt. Welche Einpassungen eine Wendel verschluckt, sagt `features.without_phantoms_on` für beide Kerne — der exakte Leser `brep.thread` ruft dieselbe Regel |
| `slots.py` | Langlöcher (§21.1): zwei Halbzylinder, zwei ebene Flanken, ein Merkmal. Dieselbe Bauart wie `helix.py` und aus demselben Grund — die Einpassung findet darin zwei Verrundungen, und der Kunde sah zwei Rundungen, wo eine Öffnung ist. Die Paarsuche fragt einzeln nur, wer in Frage kommt (`_PairPlan`, siehe oben) |
| `relations.py` | Nachbarschaften zwischen Merkmalen (§21.1, §21.2): Was zusammengehört und was daraus folgt. Die Randringe der Hohlraumketten (`_cavity_links`) liegen im Cache des Netzes unter einem Schlüssel aus Name, Art und Flächen — **ohne Lage**, damit `geom.transform.apply` den Eintrag an die bewegte Kopie weiterreichen kann; `session._warm_metrics` fragt sie im Arbeiter, bevor der Objektbaum sie im Hauptfaden liest. Der vollständige Flächenvergleich zweier Ausschnitte (`_same_surface_patch`) fragt erst die Ecken über den Suchbaum und misst nur an Dreiecken, was weiter als die Sehnenhöhe von jeder Ecke liegt — vier gleich vernetzte Bohrungen kosteten je Klick 1,6 s im Hauptfaden, jetzt eine Baumabfrage. Heute das koaxiale Rohr — eine Bohrung und das Material um sie herum, mit der Wand dazwischen. Am Langloch ist das die **dünnste** Wand: Der Weg der Mittellinie geht zur Hälfte ab, denn dort sitzen die Enden. Eine Regel (`_sleeve_between`), drei Auskünfte: `sleeve_at` fragt für **ein** Merkmal; `sleeves_of` liefert die dünnste Wand an **jeder** Merkmalszeile des Steckbriefs; `thinnest_sleeve` liefert das Minimum für die Wandprüfung. Beide Körperabfragen lesen die Maße je Merkmal einmal und teilen dieselbe Paarprüfung (RM-127). Und wem ein Dreieck gehört, das zwei Merkmale beanspruchen, sagt `cell_owner_table` (innerstes bei Verschachtelung, `CONTESTED` bei Widerspruch) — der Viewport liest es für den Klick im Bild |
| `maps.py` | Analysekarten (§18.4). Die Netzfehlerkarte hat **vier** Stufen, und die dritte ist die einzige räumliche: offene und verzweigte Kanten stehen in der Kantentabelle, eine **Durchdringung** nicht — zwei Wände, die einander schneiden, haben lauter saubere Kanten mit je zwei Flächen (`repair.self_intersecting_faces`, RM-143). Wand- und Krümmungskarte nehmen `cancelled` bis in die Schrittschleife mit (ein Kartenwechsel hält die alte an); die Wand rechnet je Schritt nur die noch aktiven Dreiecke, die Krümmung ist vektorisiert. Die Überhanglegende nennt den Grenzwinkel der Karte, nicht fest 45 Grad |
| `digest.py` | Der Steckbrief der Szene für den Agenten (§23). Unter der Auswahlzeile steht seit P1.5, was das Merkmalfenster zur gewählten Stelle weiß (`_selection_lines`): die Hohlraumkette oder der Grund „nicht sicher einzeln“, und je Mitgliedschaft eine Zeile der Handlungsgruppen — gleiche Merkmale mit Umfang, unsichere mit Grund; Handlungen mit derselben Mitgliedschaft teilen eine Zeile (§26.1) |
| `recognition_time.py` | Zeitspanne der Vollerkennung auf diesem Rechner aus einer kurzen Rechenprobe je Prozess (§21.1) — nur Anzeige, nie in der Erkennung |
| `matching.py` | Merkmalsbezeichner über Operationen hinweg stabil halten (§21.2, §21.3) |
| `actions.py` | Was der Kunde mit einem erkannten Merkmal tun kann — und was nicht, mit Grund. Die Liste fürs Merkmalspanel, **aus dem Register abgeleitet** (§10, §21); `reason_against` beantwortet dieselbe Frage für den Kern |

*Früher im Kopf der Karte, HEAD-Fassung: Antwortschlüssel, Importstaffel und Zuordnungsentscheidungen.*

`match_records` ist die gemeinsame Quelle für reine JSON-Struktur und
kanonische, körperqualifizierte Antwortschlüssel — in vier Domänen:
`group:` für Netzantworten, `native-group:` für die native Neuwahl am
umgebauten exakten Körper, die zusätzlich ihren `scope` trägt (die
Erzeugerfassung, für die die Wahl gilt), und `edge-answer:` für die
Kantenwahl eines **Verbrauchers** (P1.4c): Sie gehört seinem Eingangskörper,
einem Feld und dem vollständigen Schlüsselbündel, ihr `scope` ist der
Objekthash dieses Eingangs, und `validate_matches` prüft sie gegen die
Eingänge statt gegen die Ausgaben (`validate_edge_answer`; `domain_of` liest
die Domäne aus dem Schlüssel). `recognition-answer:` hält die ausdrücklich
bestätigte oder ausgelassene Vollerkennung eines großen importierten
Ausgabekörpers. Ihr `scope` ist der vorhandene Netzinhaltabdruck aus
`features._mesh_key`, `allowed` ein strikt boolescher Wert, und eine Absage
aus einem Speicherfehler trägt zusätzlich `out_of_memory: true`; ein anderer
Körper oder Netzinhalt gibt nichts frei. Die Importstaffel und grobe
Schätzung stehen zusammen in `local`: automatische Erkennung bis
`FEATURE_LIMIT_TRIANGLES`, bestätigte Importe bis
`CONFIRMED_FEATURE_LIMIT_TRIANGLES`, darüber weiterhin lokale Auswahl;
`recognition_minutes` gibt die Zeitspanne auf diesem Rechner,
`recognition_gigabytes` den Spitzenbedarf des ganzen Imports
(`RECOGNITION_BYTES_PER_TRIANGLE`). Beide sind Anzeige, keine Grenze; die
Messungen stehen an den Konstanten. Die Spanne rechnet `recognition_time`:
Die Referenz (Drache, Aufschlag `RECOGNITION_TIME_FACTOR` für die Topologie)
wird mit einer kurzen deterministischen Python-/NumPy-Probe dieses Rechners
skaliert, einmal je Prozess und nur, wo eine Spanne angezeigt wird. Die
Erkennung selbst misst nichts: Aus vergangenen Läufen zu lernen hieße, in
`detect` die Uhr zu lesen und in den Nutzerordner zu schreiben (§15.1).
`match_decisions` bildet Gruppen, erkennt deren vollständiges
Kandidatenmuster geometrisch wieder und prüft die gesamte Wahl atomar;
`resolve_group(scope=...)` gibt eine native Wahl nur für denselben Scope frei
und eine Netzantwort nie für die native Frage. Kostenrechnung und letzte Injektivitätsgrenze
bleiben in `matching`; die Antwortschicht erzeugt keine zweite Zuordnung.
Das historische Fingerabdruckfeld `diameter` speichert unverändert das
Rohmaß aus `params.diameter`, ersatzweise `params.area`; nur die Position ist
körperbezogen normiert. Die Feldbenennung ist keine Einheitenumrechnung.

### `patterns.py`

*Früher unter „Muster (`patterns.py`)“, HEAD-Fassung.*

Viele gleiche Zellen auf einer Fläche sind **ein** Merkmal
(`pattern`, §21.1, RM-207) — die acht Stile von `geom.texture_ops.PATTERNS`
unter ihrem eigenen Namen, dazu `other` für ein Gitter, das Solidon so nicht
zeichnet. Eine Zelle ist ein zusammenhängendes Stück aus kleinen Merkmalen
**und unbesessenen Dreiecken** (die Wände einer Welle nennt die Flächensuche
nicht), das nur an große Träger grenzt — ebene Flächen, oder einen Stift, um
den ein Muster läuft (`CARRIER_KINDS`); gemessen werden Mündung (konvexe
Hülle in der **Abwicklung** des Trägers, `Frame`), Tiefe, Seite und Umriss.
Die Abwicklung ist auf der Ebene das Blatt ihrer Achsen, um den Zylinder
Umfang und Achse mit dem Abstand zum Radius als Höhe; ihre Naht legt
`_CellMeasure.seam_between` in die größte Lücke zwischen den Zellen, und ein
gelesenes Muster trägt seine Normale als erste Achse (`frame_for`: Mitte auf
dem Zylinder, Naht gegenüber, dazu `carrier_axis` und `carrier_diameter`).
Was auf dem Träger liegt, gehört dem Träger, auch ohne Namen, und was ein
Stift beim Einpassen an Wandstücken mitnahm, der Zelle. Ein **Gitter**
aus deckungsgleichen Zellen liefert Teilung und Richtung über die nächsten
Nachbarn (Streifen über ihre Achse, `_rows_of`), eine **Streuung** gleich
tiefer Zellen ohne Gitter ist Voronoi oder Rauschen mit der Dichte als
Teilung. Runde Zellen sind nur blind, flach, ab zwanzig und im Wabengitter
eine Noppe — ein Lochblech bleibt Bohrungen, 25 Magnettaschen im
Quadratraster auch; jeder Stil gilt nur im Gitter, in dem `apply_texture` ihn
zeichnet (`_GENERATOR_LATTICE`), sonst ist er `other`. Eine Reihe Streifen
entscheidet als Ganzes über Rippe oder Welle, gewichtet mit der Wandfläche.
Das Feld ist die kleinste Hülle über die Lagen, die das Gitter nicht
unterscheidet (`_LATTICE_TURNS`). Angeschnittene Randzellen zählen als `partial`
— vom Rand des Feldes wie vom Rand des Körpers: Ein Stück, das an Träger
quer zueinander grenzt, bleibt ein `EdgePiece`, bis ein Muster es an seinem
Träger nachmisst —, und `coverage` sagt, ob das Feld den Träger bis auf eine
halbe Teilung füllt (`whole_face`) oder ein Rechteck ist. `anchor` ist die
Mitte einer ganzen Zelle: Beim Neuzeichnen kommt dort wieder eine hin.
`mouths_of` zeichnet die Zellmündungen am Netz nach, `plug_for` baut daraus
den Stopfen (bündig mit der Trägerebene, bei durchgehenden Zellen auf beiden
Seiten; um den Zylinder auf dessen **Facetten** gelegt, `Frame.facets`, an
jeder Facettengrenze konform geteilt — `_split_along`/`_cut_at`, ohne
Boolesche Rechnung — und um einen Saum breiter als die Mündung, vertieft aber
nie über die Stirnflächen des Stifts hinaus, `Frame.span`; der Boden einer
Tasche mit parallelen Wänden nur im Umfang aufgeweitet),
`field_outline` das `Field` fürs Neuzeichnen — Umriss, Abwicklung und der
Weg zurück (`Field.placed` biegt das flache Werkzeug um die Achse; `around`
sagt, ob das Feld einmal herumreicht und der Umriss periodisch gilt).
Stopfen und neues Feld lesen denselben Mündungssaum (`_mouth_with_margin`):
Was bereits gefüllt ist, bleibt keine Aussparung im neuen Feld. Ein
Schneidwerkzeug durch den Stirnrand endet über dessen gemessener Ebene
(`Field.placed(beyond=...)`, `_through_the_ends`); ein aufgesetztes endet am
Feldrand. Beides
brauchen `remove_feature` und `resize_feature` in `geom/prepare_ops.py`. Den
Träger findet `carrier_of` über Ebene und Normale beziehungsweise Achse und
Durchmesser, nie über eine Kennung: Die altert beim Umbenennen.

Dreht eine Operation den ganzen Körper, dreht der Feldwinkel eines ebenen
Musters mit (`matching._turned_field_angle`): Er ist gegen die Flächenachsen
der Normale gemessen (`units.plane_axes`), und die gedrehte Normale hat
andere — ohne das stand ein gedrehtes Wabenmuster mit seinem alten Winkel da.

Gezählt wird das **Zellmaterial**, nicht die kleinen Merkmale: Ein Kreuzrändel
besteht aus Dreiecken ohne Namen, und die Suche fragt erst, nachdem sie dem
Stift sein mitgenommenes Wandmaterial abgenommen hat. Und von zwei Stiften um
dieselbe Achse ist der zersplitterte Boden oder Kopf der Zellen und kein
Träger (`_cell_floors`): Vertiefte Rillen mit breitem Boden hätten sonst zwei
Träger, und jede Rille wäre ein Randstück. Zerfallen beide gleich, trägt der
äußere — die Geometrie lässt dann beide Lesarten zu.

### `slots.py`

*Früher im Kopf der Karte.*

`slots.open_slots_instead_of_fillets` erkennt auch am Rand angeschnittene
Bohrungen und Langlöcher mit einer ebenen freien Mündung (§21.1). Die
vorhandenen Bogen- und Flankenflächen bilden ein `slot` mit `open`,
`arc_centre`, `mouth_centre` und `opening_normal`. `matching.moved_features`
transformiert diese Punkte und Richtungen zusammen mit der Merkmalsachse.
Die Suche nach Randöffnungen erweitert einen Bogen nur über erreichbare
Nachbarflächen. Tangenz und Kreisform werden lokal geprüft; die gemeinsame
Flächentabelle liefert auch die Randkanten. Der Abbruch wird innerhalb der
Flutung geprüft, ohne pro Bogen Felder über das gesamte Netz anzulegen.
Die Paarsuche normiert jede Bogenachse einmal und fragt einzeln nur, wer in
Frage kommt (`slots._PairPlan`): Radius und Achse als Feld für alle zweiten
Bögen, das gemeinsame Mantelstück je Gruppe gleichgerichteter Bögen einmal
— mit einem Randabstandsbeweis, dass die Quermaske für jede Paarachse der
Gruppe dieselbe ist; fehlt er, fragt jedes Paar selbst. Die Mantelstücke
sind Zusammenhangskomponenten je Quermaske (`_Components`), der Mantel eines
Bogens sein Fleck plus die Stücke, an die er grenzt (`_reach_of`), und ein
Mantel, der schon an einer Auswahl seiner Ecken breiter ist als jedes
Langloch, wird nicht geflutet (`_wider_than_a_slot`, eine Beweisgrenze in
Radien). Der Leistungstest misst zusätzlich den vollständigen
Erkennungslauf an vielen verrundeten Taschen.
Die vorgeschaltete Gewindeunterdrückung liest Zylinderachsen, Mitten und
Radien einmal und prüft je Ausgangszylinder ein lineares Feld. Axiale
Fortsetzung und die bestehenden Winkel-/Abstandsschranken bleiben maßgeblich.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Und ein Langloch ist ebenso wenig eine Grundform wie eine Wendel.**
  `slots.py` setzt es aus zwei Zylinderausschnitten zusammen, die die
  Einpassung als Verrundungen ausweist — an einem Netz sind sie genau das:
  Bögen von 180 Grad. Was ein Loch daraus macht, ist die **Topologie**: Beide
  hängen über einen Mantel zusammen, der quer zur Achse steht, und alles darin
  ist entweder einer der zwei Bögen oder eine ebene Flanke im Abstand eines
  Radius von der Mittellinie. Läuft der Mantel über etwas anderes, bleiben es
  zwei Verrundungen. Die Gegenprobe, die das trägt, ist eine rechteckige Tasche
  mit vier verrundeten Ecken: gleiche Radien, parallele Achsen, verbundener
  Mantel — und kein Langloch, weil er zu den anderen beiden Ecken weiterläuft.
  **Der exakte Kern beantwortet dieselbe Frage an der Topologie**
  (`brep.features._slots_instead_of_half_bores`); dass beide Kerne dasselbe
  Merkmal melden, ist eine Zusage und kein Zufall.

- **Und ein zweiter Weg zum selben Merkmal, für den Mantel aus einem Stück**
  (RM-155, `fit_stadium` / `slots.slots_from_stadiums`). Zwischen „ein
  Zylinder passt noch" (Weg unter rund fünf Prozent des Durchmessers) und
  „zwei Bögen lassen sich trennen" lag ein Streifen, in dem ein knapp
  aufgezogenes Langloch **gar kein** Merkmal ergab — Ø 12 auf 12,5 mm, Ø 20
  auf 20,5, Ø 40 auf 40,8. Solidon schneidet seit dem 11.09.2026 nicht mehr so
  knapp (`prepare.shortest_slot`); ein eingelesenes Netz kommt trotzdem
  dorthin. `_fitted` fragt deshalb als **dritte Runde** — nach Zylinder und
  nach dem Krümmungssplit, und nur wenn beides nichts ergab — den ganzen Fleck:
  ein Prisma (alle Normalen quer zu einer Achse), dessen Ecken in der
  Projektion auf einem Stadion liegen. Die Mittellinie kommt aus der Richtung
  der größten Ausdehnung, nicht aus der Hauptachse der Punktwolke — die zeigte
  bei zwei Prozent Weg quer. Der Rückstand ist streng (`STADIUM_TOLERANCE`,
  zwei Prozent wie bei Kugel und Torus): Ein Sechs- oder Achteck, ein
  gestrecktes Sechseck und eine Tasche 12 × 8 mit r = 3 bleiben draußen; eine
  Tasche, deren Eckradius die halbe Breite auf drei Prozent trifft, ist eines
  — auf zwei Prozent ist sie die Form. **Und der Weg muss dieselbe Toleranz
  übersteigen** (`StadiumFit.good`): Ein Kreis, den der Zylinderfit an
  seiner Streuung ablehnt — die Bohrung eines Bajonettrings mit drei Nasen
  —, kam sonst als Stadion mit Weg 0,00005 mm durch, und im Baum stand ein
  Langloch so lang wie breit. Was der Fit nicht von einem Kreis
  unterscheiden kann, meldet er nicht; die Wand bleibt eine Bohrung.

- **Die Langlochsuche rechnet je Bogen, nicht je Paar** (`slots._Reach`).
  Flutung, Flankenecken und Stadionfit hängen an Bogen und Achse; die Maske
  einer Achse ist ihr Schlüssel, nicht allein die gerundete Achse. Am
  Hemmungsrad mit 531 Verrundungen: 124 s → 4 s bei bitgleichen Merkmalen
  über 102 Körper. Der Stadionfit über den ganzen Mantel darf die Breite
  nicht unter das Maß der Bögen drücken — sonst stand „Langloch 0,01 auf
  97 mm" im Baum eines Organizer-Rahmens. **Und die Flanken gehen im
  Langloch auf**: `face` steht in `SWALLOWED_BY_A_SLOT`, denn was
  vollständig im Mantel liegt, ist eine Wand des Lochs und keine Fläche für
  sich (der Boden eines Sacklochs liegt nicht im Mantel und bleibt).

### `helix.py`

*Früher im Kopf der Karte.*

`helix._resolved_helix` prüft kurze breite Gewinde zusätzlich an einzelnen
zusammenhängenden Kammkanten. Planare Abschlussnormalen ergänzen die
Hauptachsen; konstantes Radiusband, mindestens zwei volle Umläufe,
punktweise Wendelabweichung und Gangtiefe müssen gemeinsam passen. Die
bisherige Spektrumsprüfung bleibt für lange Gewinde erhalten.

**Und die Konzentration kennt beide Vorzeichen** (P2.5, B1): `_best_pitch`
rechnet `z - p·θ/2π` und `z + p·θ/2π` in derselben rechtshändigen Basis, in
der auch `brep.thread` misst, und gibt die Richtung mit dem höheren Gipfel
als `Helix.handedness` zurück; das erkannte Gewinde trägt sie als Maß mit
Quelle `fit`. Bis dahin setzte die Rechnung den Rechtsgang voraus, und die
Spiegelung desselben Bolzens ergab null Wendeln. Die Gangzahl kennt das Netz
weiter nicht — ein Vielfaches der Steigung konzentriert nicht. **Beide
Vorzeichen kommen aus einem Durchlauf**: Sinus und Kosinus der Phasenmatrix
einmal je Block, die vier Mittelwerte als zwei Matrixprodukte mit `cos θ`
und `sin θ` — am M3-Bolzen mit 6 965 Kammpunkten 236 → 50 ms, Ergebnis
gleich bis auf die letzte Stelle (21.09.2026).

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Eine Wendel ist keine Grundform, und sie verschluckt die, die man auf ihr
  findet.** `helix.py` misst sie am Netz statt an den Einpassungen: scharfe
  Kanten zu Zügen verbinden, je Zug die Steigung über die Konzentration von
  `z − p·θ/2π` suchen, und dann fünf Bedingungen. Die tragende ist die
  **Gangtiefe** — 0,54 · Steigung nach Norm; über Korpus, Kundendatei und
  kurze Bolzen gezählt ist sie die einzige, die je allein ablehnt. Der Grund,
  aus dem es sie braucht: Ein Mantel mit Spiral-Naht ist eine echte Wendel
  über zwanzig Windungen und hat trotzdem kein Gewinde. Ein Gewinde aus einem
  **Baustein** läuft hier nie durch — es steht ohnehin in der Szene (§24.1).
  Die Steigungssuche berechnet nur begrenzte Zeilenblöcke der Phasenmatrix.
  Jede Zeile enthält weiterhin alle Punkte in derselben Reihenfolge; damit
  bleiben Konzentration, Grundton und Schärfe unabhängig von der Blockgröße.
  Die Anzahl der gleichzeitig berechneten Steigungen richtet sich nach der
  Punktzahl. `detect` reicht seine Abbruchprüfung bis in diese Blöcke und in
  die Kantenzugsuche weiter; ein Abbruch veröffentlicht keinen Merkmalscache.
  `thread_N` wird nach der räumlichen Mitte und bei gleicher Mitte nach den
  gemessenen Gewindemaßen vergeben, unabhängig von der Vertexreihenfolge.

## Der Weg durch die Erkennung

*Früher unter „Was die Erkennung sich merkt — und woher“, HEAD-Fassung.*

`detect` legt jede vollständige Erkennung unter dem Abdruck ihres Netzes ab
(`_mesh_key`: Ecken und Dreiecke, `blake2b`; der Abdruck selbst liegt im
Cache des Netzes und wird je Netz einmal gerechnet). Vier Nebentabellen gehen
mit — Flächenindizes als Gewicht der Verdrängung, weggelassene Rundformen
(`freeform_dropped`), das Freiformurteil (`recognised_as_freeform`), unlesbare
Schalen (`unreadable_void_shells`) —, und `_remember` führt alle fünf
zusammen. Drei Leser kommen ohne Rechnung aus:

- **`carry_detection`** überträgt die Erkennung eines Netzes auf seine starr
  bewegte Kopie, wenn drei Belege stehen — starre Matrix, dieselben Dreiecke
  über denselben Eckennummern, jede Ecke dort, wo die Matrix sie hinbewegt
  (`MOVED_TWIN_TOLERANCE`). Die Maße folgen der Bewegung über
  `matching.transformed_features`; bleibt eines hinter ihr zurück, wird
  nichts übertragen. Die Auswertung ruft es vor jeder Erkennung eines
  bewegten Körpers (`scene.evaluate._with_features`, `source_mesh`): Ein
  Verschieben oder Drehen an 204 000 Dreiecken kostete davor 1,3 s
  Neuerkennung für eine Antwort, die bis auf die Lage schon dastand.

- **`carry_refined_detection`** tut dasselbe für eine feiner geteilte Kopie
  (*Kanten verfeinern*). Die Operation vermerkt die Herkunft jedes Dreiecks
  am Ergebnis (`note_refinement`, im Cache des Netzes), `refined_twin`
  glaubt sie erst nach dem Beleg — derselbe Eingang nach `_mesh_key`, jede
  Ecke in der Ebene ihres Ursprungs, je Ursprung dieselbe Fläche, beides
  unter `MOVED_TWIN_TOLERANCE` —, und `refined_features` ersetzt die
  Dreiecksnummern jedes Merkmals und seiner Teilträger durch die ihrer
  Nachfahren. Maße und Namen bleiben, denn die Oberfläche ist dieselbe.
  **Der Vermerk reist über die Platte mit** (`refinement_note`,
  `restore_refinement_note`, im Plattencache als `<n>.origin.npy` neben
  dem Netz, `scene.cache`): Ohne ihn lief die Erkennung nach dem
  Wiederöffnen am feineren Netz neu, und dasselbe Dokument trug je nach
  Cache zwei Merkmalsstände. Geglaubt wird er auch von der Platte erst nach
  dem Beleg in `refined_twin`.

- **`known_detection`** gibt die gemerkte Antwort oder `None` — für die
  Live-Vorschau, die Geometrie zeigt und keine Merkmale braucht
  (`evaluate(..., detect_features=False)`).

*Früher unter „Was die Erkennung sich merkt — und woher“, Zwischenfassung (Paketübernahme).*

Wo das Netz neu ist und die Erkennung rechnen muss (§21.1 nach jedem
Schritt), **antworten die Einpassungen und ihre Nachweise über die
Körpergrenze** (`_by_geometry`, RM-261): Die Fragen aus
`GEOMETRY_KEYED_ANSWERS` sind Bit für Bit geschlüsselt nach dem Abdruck ihrer
Stützpunktlesung (`_SurfaceSupport.digest`, samt den Dreiecken des Flecks),
der Toleranz, dem geprüften Fit und den Löserbudgets. Die Rümpfe dahinter
(`_fit_cone_measured` und Geschwister) bekommen die Toleranz vom Aufrufer.
Die Antworten gehören den Abstammungen, die sie fragten
(`_Lineage.geometric`), und gehen mit der letzten. Treffen können sie, weil
eine Boolesche Unberührtes in der Darstellung ihres Eingangs zurückgibt
(`geom.attributes.in_source_layout`). Die Regeln stehen in `kern.md`.

*Früher unter „Grenzen“.*

- **Erkennung bleibt kooperativ abbrechbar.** `detect` nimmt optional
  `check_cancelled` entgegen und reicht die Prüfung zu Fitflecken und
  Flächensuche weiter. Die Auswertung übergibt `CancelToken.raise_if_cancelled`.
  Ein Abbruch zwischen Phasen oder Fitflecken veröffentlicht keinen Eintrag
  in den drei Merkmalscaches; ein bereits laufender nativer Aufruf kehrt erst
  zurück. Die planare Maske wird je `detect` einmal für Fits und Flächen
  aufgebaut, ohne einen weiteren globalen Cache. Auch die Nachtrennung nach
  Krümmung baut die Flächennachbarschaft einmal für alle ungeeigneten Flecken
  auf und prüft den Abbruch zwischen ihnen. Ihre Schwellen und die Reihenfolge
  der Kanten bleiben dabei dieselben. Facettenurteil (`_facet_verdicts`),
  Flecken (`_connected_patches`), Krümmungssprünge (`curvature_jumps`) und
  Facettenmitten (`facet_middles`, blockweise) prüfen zwischen ihren
  Schritten: Am Drachen lagen sie bis zu 9,6 s am Stück, jetzt höchstens
  3,1 s unter Last — je ein Schritt am großen Fleck: die Stützpunktlesung
  eines Ringfits, `body.facets` aus trimesh (2,5 s, nicht teilbar) und die
  Kerbenschließung.
  **Geteilt wird nur, was jemand liest** (RM-132): `_fitted` sagt der
  Nachtrennung über `worth_splitting`, welche Flecken groß genug zum
  Einpassen sind, und für die übrigen kommt der Fleck ungeteilt zurück. Ein
  Stück ist nie größer als sein Fleck, die Antwort ändert sich also nicht — an
  einer verrauschten Freiform sind es 1 650 von 120 610 Flecken.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Die Vollerkennung meldet ihren Anteil** (`detect(..., progress=...)`,
  `_Share`, Durchsicht 0.5.1): nur wachsend, in Tausendstelschritten, ohne
  Uhr. Die Etappen tragen ihre gemessenen Anteile (Ebenen ein Viertel,
  Einpassung zwei Drittel), die Einpassung zählt Flecken und Stücke nach
  `_fit_weight` (`SHARE_FACES_PER_FIT`). Den Bereich des Schritts rechnet die
  Auswertung um (`scene.evaluate._StepProgress`).

*Früher unter „Grenzen“.*

- **Rundmaße kommen aus belegten Mantelpunkten.** `_surface_support` baut
  für Zylinder, Kegel, Kugel und Torus denselben privaten Koordinaten- und
  Normalenindex. Zusammenhängende Facettenfächer mit mindestens drei
  verschiedenen Normalen belegen ursprüngliche Rundflächenecken. Geradlinig
  unterteilte Facetten und Nähte erzeugen keine zusätzlichen Maßstützen;
  getrennte Fächer und entgegengesetzte Doppelflächen teilen ihre Stützung
  nicht. Für nicht konforme Unterteilung werden nur die örtlich gleichen
  Kantenstrahlen im Leseindex verbunden. Das Originalnetz bleibt unverändert.
  Die Fragen je Facette — Größe, Fläche, ob sie ein gerundetes Dreieck
  trägt — beantwortet `_facet_table` für alle Facetten mit einem
  `bincount` statt je Dreieck einer Mengenfrage (115 000 davon an der
  unterteilten Lochplatte); die Mündungsprüfung einer Bohrung
  (`_mouth_covered`) fragt alle Stichpunkte in einem Feld ``(Dreiecke,
  Punkte)`` statt in einer Schleife.
  **Gelesen wird je Netz und Fleck einmal** (`remembered`: je Frage ein
  eigener Merker mit Identität des Netzes plus Abdruck der Flächenliste als
  Schlüssel — nicht der Datenhash, trimesh rechnet ihn je Frage neu; die
  Stützpunktlesung hält acht Antworten, weil ihre Felder so groß sind wie
  der Fleck, jede andere Frage viertausend, denn 218 Streifenfragen
  verdrängten sonst die Facettenantwort zwischen ihren zwei Lesern). Acht
  Fragen an denselben Fleck lasen die Ikosphäre mit 327 680 Dreiecken
  achtmal. Dasselbe gilt je Fleck für jeden Fit und jeden Nachweis (Kegel,
  Zylinder, Kugel, Ring, ihre `_is_recognisable` mit dem Fit im Schlüssel,
  die Streifenprüfung), je Körper für die gerundeten Dreiecke, die Flecken
  einer Dreiecksliste, die kleinen Flächen und die Frage nach
  deckungsgleichen Ecken; das Löserbudget gehört zum Schlüssel, und ein
  abgebrochener Auftrag bekommt keine gemerkte Antwort. Der Abdruck einer
  Flächenliste bleibt am Listenobjekt (`_patch_digest`, die Liste als Anker),
  denn dieselbe Liste wird je Erkennung zwei Dutzend Mal gefragt.
  **Die Antworten eines Körpers gehen mit ihm** (`_BodyMemory`,
  `weakref.finalize`): Vier Ikosphären hinterließen sonst 369 MiB an
  Lesungen zu Netzen, die niemand mehr hatte, bis die Grenze je Frage sie
  verdrängte. Und **ein Schloss um alle drei Merker** (`_MEMORY_LOCK`), weil
  das Merkmalfenster im Hauptfaden dieselben Fragen stellt wie der Arbeiter
  — `get` und `move_to_end` sind zwei Schritte, und dazwischen verdrängte
  der andere Faden den Schlüssel (21.09.2026).
  **Eine Kopie antwortet aus dem Merker ihres Originals**
  (`copy_with_answers`, `_Lineage`, Durchsicht 0.5.1): Schlüssel sind Marken
  statt Adressen, und eine Kopie samt trimesh-Cache gehört zur Abstammung
  ihres Originals. Antworten aus `SHARED_ANSWERS` (Fits, Nachweise, Mengen,
  Felder, Hohlraumflächen) gelten für die ganze Abstammung und gehen mit
  ihrem letzten Körper; `BODY_BOUND_ANSWERS` (verschweißte Lesungen,
  Oberflächenindex, Flächenausschnitt, Trägerfläche — Netze, Suchbäume,
  vorbereitete Flächen) bleiben am eigenen Körper, denn die Kopie gibt es
  gerade, damit ein Nebenfaden nichts davon mit dem Hauptfaden teilt. Eine
  verschweißte Lesung der Kopie teilt die Antworten der Lesung des Originals
  (`DERIVED_BODY_ANSWERS`). Geteilt wird über die Abstammung und nicht über
  einen Inhaltsabdruck: der kostete 6,7 ms je Körper mit 173 592 Dreiecken und
  hielte gleiche Netze verschiedener Herkunft für eines. Gemessen am
  Laptop-Ständer: Hohlraumfläche an der frischen Kopie 1,1 s → 65 ms.
  Der Fächer einer Ecke wird über die Bogenzahl aus dem Nachbarindex gezählt
  (`_fan_arcs`: Dreiecke minus innere Nähte, ein offener Bogen zählt eins,
  ein geschlossener Ring an einem wasserdichten Netz null); die zerrissenen
  fragt `_fans_connected` **alle auf einmal** — ein Graph aus Knoten
  „(Ecke, Nachbar)" für alle Ecken, dessen Komponenten eine Markenweitergabe
  in NumPy findet (kein `scipy`-Graph: dessen Aufbau kostete zwei
  Millisekunden je Aufruf, 219-mal je Erkennung an Flecken mit zwanzig
  Ecken) —, und nur wer dort auseinanderfällt, geht den Einzelweg mit dem
  Strahlenvergleich (`_one_vertex_fan`, an der Schüssel mit 215 000
  Dreiecken 368 217 Aufrufe und 5,8 Sekunden, bevor es so war). Die Punkte
  kommen aus den Ecken des Netzes, für einen großen Fleck markiert, für einen
  kleinen sortiert (`SORTED_CORNERS_SHARE`, dieselbe Schwelle zählt die Bögen
  in `_counted_at`): Ein Feld über alle Ecken des Netzes je Splitter kostete
  am erzeugten Puppenhausbett über 30 Sekunden, und kein Aufruf hält ein
  Feld in Netzgröße, das nur den Fleck betrifft — auch nicht die
  Wendelsuche (`helix._resolved_crest` rechnet an den Kantenecken,
  `_facet_of_face` einmal je Körper). Wo das Netz
  deckungsgleiche Ecken hat, legt `vertex_rank` sie **einmal je
  Körper** zusammen (im Cache des Netzes — dieselbe Nummer liest die
  Ordnung der Flecken und die Nachbarschaft der Platzierung), und die
  Lesung liest je Fleck nur Nummern
  (`_coincident_vertices` fragt dieselbe Tabelle und merkt sich die Antwort
  daneben im Cache des Netzes) — sonst ist jede Ecke ihr
  eigener Punkt. Gemessen am 21.09.2026, allein auf Roberts Maschine:
  Ikosphäre 22,8 → 1,4 s, Lochplatte mit 204 000 Dreiecken 1,4 → 1,0 s,
  Taschenplatte 1,3 → 0,95 s, verrauschte Freiform 5,9 → 4,3 s (Ziel §31:
  eine Sekunde). Was an der Freiform bleibt, ist die Verfeinerung selbst: je
  Fleck ein begrenzter Löser, 5 400 Flecken, und angenommene Kegel brauchen
  am Korpus bis zu 78 Auswertungen — ein kleineres Budget kostete echte
  Formen, ein lineares Sieb davor ist gemessen unsicher (Sieb gegen Endmaß bis
  10⁹ an echten kleinen Kugeln), und das Anfangsresiduum sagt beim Kegel und
  Ring nichts über das Ende (bis 10¹⁴ darüber). Die Marken der 0.4.4 galten
  den linearen Fits, die P1.2 bewusst ersetzt hat, und sind verworfen.
  Beim Kegel dürfen nachgewiesene gemeinsame Mantellinien auch echte
  Trimmpunkte liefern. Beliebige Sehnenränder werden nicht dazu erklärt.

*Früher unter „Grenzen“, Zwischenfassung (Paketübernahme).*

- **Der Ursprung vor dem Teilen reist mit** (`geom.mesh.refined_units`,
  R1 der Durchsicht 0.5.1). *Kanten verfeinern* schreibt je Dreieck die
  Nummer seines Herkunftsdreiecks an das Ergebnis; Boolesche Operationen
  (`geom.attributes.carry_refined_units`, an den unberührten Dreiecken),
  das Verschweißen, ein Ersetzen mit denselben Dreiecken und der
  Plattencache geben sie weiter, frische Dreiecke tragen −1. Die Zählregeln
  lesen daran das ungeteilte Netz: `_face_count` zählt Ursprünge statt
  Dreiecke, `_flat_counts` Knicke und Größen je Ursprung, `_outline_corners`
  nur die Ecken von vorher, `face_radii` den kleinsten Radius je Ursprung
  (`_by_origin`). Der Vermerk `note_refinement` trägt die Erkennung nur bis
  zur nächsten Operation; ohne die Ursprünge las sie einen verfeinerten
  Schriftzug nach einer Bohrung anders als vorher. `_mesh_key` nimmt ihren
  Abdruck mit — zwei gleiche Netze mit verschiedenen Ursprüngen sind zwei
  Fragen.

*Früher unter „Die Sache mit der Stabilität“.*

Ein Merkmal, das nach jeder Operation einen neuen Namen bekäme, wäre wertlos
— Passungen und Agentenverweise hingen ins Leere. `matching.py` hält die IDs;
was es trotzdem verliert, fängt `scene/orphans.py` auf und **fragt**, statt
zu raten.

*Früher unter „Die Sache mit der Stabilität“, HEAD-Fassung — die Regel dazu steht heute in `kern.md`.*

Die Nummer selbst kommt aus dem Körper (`features.numbering_order`, RM-211):
nach der Mitte, und wo Mitten zusammenfallen — in jeder Stelle höchstens
eine Einheit der letzten Nachkommastelle, über Ketten —, nach Maß, Länge,
Lage und zuletzt den Ecken. Eine Regel für alle Arten, Langloch, Muster,
Gewinde und Hohlraum eingeschlossen; wer allein steht, steht wie nach der
gerundeten Mitte. Und die Erkennung hängt nicht an der Reihenfolge der
Dreiecke: Flecken und ihre Dreiecke kommen in der Ordnung ihrer Ecken
(`features.in_body_order`), und Konturpunkte, die in der Projektion
zusammenfallen, zählen einmal (`_distinct_points`). Umgekehrte
Dreiecksfolge gab vorher an 12 von 101 Korpuskörpern andere Merkmale.

Die Ordnung der Ecken ist nicht drehfest, und drei Schritte durften deshalb
nicht an ihr hängen (RM-210). Gefragt werden die Flecken nach Größe, der
größte zuerst (`_in_size_order`) — die Folge entscheidet, welcher von
deckungsgleichen Flecken für die anderen antwortet. Welche Konturecken einen
Kreis tragen, wählt `_simplified_ring` nach den Abständen und nicht vom
Anfang der Hülle aus (Douglas-Peucker hielt ihn fest, und GEOS beginnt je
Lage woanders). Und jede Zusammenlegung — Zylinder, Kegel, Torus — fragt nach
der ersten Runde ihre Gruppen untereinander, bis keine zwei mehr
zusammengehören (`_joined_until_stable`); der Zylinder rechtfertigt eine
Vereinigung in beide Richtungen (`_joined_cylinders`).

Unter `MIN_ROUND_ARC` (fünf Grad, Entscheidung Robert zu RM-210) ist eine
Rundform eine Kante: Verrundung, Kegel- und Torusstück, beim Torus der Bogen
der Röhre (`_shows_enough_arc`). Der exakte Kern fragt dieselbe Zahl
(`brep/features._short_arcs_dropped`).

## Große Netze: örtlich statt ganz

*Früher unter „Lokale Erkennung großer Netze“.*

`local.detect_local(mesh, point, normal=..., radius=..., seed_faces=...)`
prüft einen Originaltreffer und veröffentlicht nur vollständig belegte
Merkmalsflächen mit globalen Dreiecksnummern. Ein Ausschnitt erzeugt keine
Randöffnung des Originals. Eine glatte Fortsetzung über den Suchrand sperrt
die glatt verbundene Fläche bis zum nächsten Krümmungssprung — derselben
Grenze, an der die Nachtrennung Stücke bildet (`features.curvature_jumps`,
am ganzen Körper, denn am Schnittrand fehlen dem Ausschnitt die Nachbarn):
Hinter dem Sprung liegt eine andere Fläche, die eigene Fortsetzung eines Fits
trägt dieselbe Krümmung. Hohlraumketten benötigen alle Abschnitte,
vollständige Anschlussringe und unbeschädigte Boden-/Mündungskanten; wo die
Wand glatt weiterläuft, muss der Nachbar eben oder ein vollständiges Merkmal
sein, hinter einem Knick oder Sprung nicht — so kommen die Magnettaschen des
Schabers mit gerundeter Mündung unter der gewölbten Oberseite.
**Ein Muster kommt an der Stelle, wenn sein Feld im Suchradius liegt**: Am
Wabenhalter stehen bei 5 und 15 mm die Wände als Flächen da (aus wenigen
Zellen entsteht kein Muster), bei 30 mm sagt die Stelle Suchrand, ab dem
ganzen Feld kommt das Muster der Vollerkennung. Ebenso braucht eine gesenkte
Bohrung einen Radius über die Senkung hinaus — die Kette ist erst dann
vollständig, und bis dahin bietet die Stelle den größeren Radius an.
Die Innenrolle einer Ebene kommt aus räumlich passenden Originalfacetten,
auch wenn der belegende Rand außerhalb der Suchkugel liegt. Nur ein
tatsächlich passender Beleg darf einen vollständigen Mantelfit auslösen.
Eine kleine Fläche unter `MIN_FACE_AREA` gilt hier wie global über ihre
Ränder (`_facets_standing_apart`, auch bei `all_facets`): Der Klick auf die
Spitze eines 1-mm-Nockens wählt genau diese Fläche, und die Zuordnung
hält ihren Namen über eine Verschiebung (`tests/test_local_detection.py`,
`tests/test_features.py`, P1.5).
Das Flächenbudget begrenzt diese Fits ebenso wie den Ausschnitt; es ändert
keine Erkennungstoleranz. Überschreitung oder fehlender Abschluss liefern
einen Handlungsvorschlag, keine Teilgeometrie.

Drei Dinge halten die Suche an großen, dicht vernetzten Netzen brauchbar
(RM-235, gemessen am Drachen mit 2,3 Millionen Dreiecken):

- **Der Treffer braucht nur die Dreiecke am Punkt** (`_region` mit
  `bounded=False` in Schweißtoleranz), nicht den ganzen Suchwürfel — und
  beide Würfel kommen aus einem Durchgang über das Original (`_within`).

- **Das Budget gilt dem Teil, der am Treffer hängt** (`_connected_to`), nicht
  jeder dichten Fläche in der Ecke des Würfels.

- **Die ebene Facette am Treffer gehört dazu**, auch über den Suchradius
  hinaus, und gilt als vollständig (`proven` in `_recognise_region`) —
  solange sie selbst ins Budget passt; eine größere Ebene trägt die Suche
  nicht, dann gilt der begrenzte Bereich wie ohne sie. Hängt an der Stelle
  mehr als das Budget, bleibt die Facette allein; findet sie dann nichts,
  heißt der Grund `budget`. Das steht fest, bevor der ganze Körper gefragt
  wird (`alone` in `_recognise_region`, RM-265): Trägt die Facette kein
  Merkmal, das vollständig sein könnte (`_could_be_complete`), und kann kein
  Einschluss den Treffer tragen (`_reaches_beyond`), entfallen Einschlüsse,
  Krümmungssprünge und Kantenzählung des Körpers — am Drachen kalt 2,3 bis
  3,8 s.

**Ob eine gefundene Fläche eine ist, sagt die Ebenenregel der Vollerkennung
am ganzen Körper** (`features.planar_facet`, Review R1) — nicht der
Ausschnitt, an dem `detect` lief: Dort war ein Mantelstreifen leicht fünf
Prozent der Fläche und ein halber Zapfenmantel kein vollständiger. Das Urteil
je Facette (`_facet_verdicts`, einmal je Körper) teilt sie mit
`_large_facet_faces`, den Mantelnachweis (`_round_surface`) ebenso. Der Fleck
dafür wird ganz geflutet (`_patch_around`, Ring um Ring), geprüft wird zuerst
an wachsenden Teilen ab `MANTLE_PROOF_LIMIT` Dreiecken: Trägt ein Teil keine
Rundform (`_could_be_round`), trägt das Ganze keine — so bleiben die zwei
Sohlen des Drachen, die über weiche Kanten an seiner Haut hängen, Flächen,
ohne zwei Millionen Dreiecke einzupassen —; trägt jeder Teil eine, wird der
ganze Fleck geprüft wie in der Vollerkennung (Review S1: die Abflachung eines
Knaufs, deren erster Teil auf die Kugelkuppe passt). Die Antwort merkt sich
die Hülle je Facette. **Und nur die ganze Facette ist die Fläche**: Am
Ausschnitt beanspruchten Nachbarmerkmale am Schaber sechs von 239 Dreiecken
einer Deckfläche, und die Stelle meldete den Rest als vollständig. Dieselbe
Auskunft fragt die Rollenprüfung für ihre Gegenfacetten (`face_roles` mit
`limit`); ihr früherer eigener Weg brach über dem Budget ab. Gefragt ist nur
die Ebenenregel — Mindestinhalt und Normalenstreuung
(`_planar_face_entries`) stellt die Erkennung am Ausschnitt selbst, und in
ein **Muster** falten kann sie aus wenigen Zellen nicht: Die Wabenwände
eines Schraubendreherhalters führt die Vollerkennung im Muster, die Stelle
als Flächen. Die Suchrandprüfung kommt vor der Ebenenregel — eine
abgeschnittene Fläche braucht keinen Mantelnachweis.

**Eine ebene Fläche ist vollständig, wenn ihre Facette es ist** — gefragt an
den Facetten des Bereichs samt Randring, nicht des ganzen Netzes: Setzt sich
eine Facette über den Rand fort, liegt ihr koplanarer Nachbar im Ring. Die
Sperre über den glatten Suchrand gilt Fits, die ihre äußerste Reihe verworfen
haben können; eine Facette hat keinen Fit. Ohne die Unterscheidung galt jede
Fläche als abgeschnitten, deren Rand unter 30° in eine Rundung übergeht — an
den Fußsohlen des Drachen ab 24,9°. **Ausgenommen ist die Flanke eines
Langlochs** (`continues_tangentially`): Knickt die Fläche an ihrem Rand
höchstens so stark wie das Rundungsstück dahinter, läuft dessen nächster
Knick parallel zur Randkante (`ALONG_THE_RIM_DEGREES`), **und ist die Rundung
ein Langlochende** (hohl, zur Seite der Flächennormalen gewölbt — geprüft für
alle Randkanten zugleich, bevor ein Stück entsteht —, und
`_turns_round_like_a_slot_end` findet, dass sie die Normale bis mindestens
`SLOT_END_TURN_DEGREES` umwendet), gilt die alte Sperre. Vorher fragt
`_may_turn_round` einmal für alle Randkanten, ob die angrenzende Rundung
überhaupt eine Normale gegen die Fläche trägt — an einer Hohlkehle nie, und
dann läuft kein Gang. Gegangen wird dafür
Stück für Stück quer zur Randkante über die einmal gelesenen Felder des
Körpers (`_Seams`), bis ein Stück breiter wird als eine Rundung
(`STRIP_GROWTH`) oder `ROUND_STEPS` erreicht sind; gemerkt wird nur, was der
Gang berührt, kein Feld in Netzgröße je Randkante (Review R2: 19,6 s an
einer Deckfläche mit 8 192 Randkanten, jetzt 3 s samt Mantelnachweis). So
bleibt die Flanke eines angeschnittenen Langlochs ein Teil des Langlochs,
wie in der Vollerkennung. **Dieser Gang beantwortet nur die Langlochfrage**:
Ob eine Fläche an einer Verrundung, in einer Innenecke oder auf einem Mantel
eine Fläche ist, sagt die Ebenenregel oben.

Ein Netz, dessen Vollerkennung am Arbeitsspeicher scheiterte, merkt sich der
Prozess (`remember_out_of_memory`, `ran_out_of_memory`, bis
`OUT_OF_MEMORY_LIMIT` Netze): kein Dokumentzustand, nur kein zweiter
Minutenlauf bis zum selben Fehler. `forget_out_of_memory` leert ihn nach
einer neuen Entscheidung — *Alle Merkmale erkennen*, `recognize`, ein
anderes Projekt.

`local_error` benennt den Grund zusätzlich als `ValidationError.constraint`
mit dem Präfix `local_`. Die Oberfläche wählt passende Rückwege über diese
Kennung; übersetzte Fehlersätze sind keine Ablaufsteuerung.

`detect_region` speichert Punkt, Normale, Radius und den optionalen
Originaltreffer als gewöhnliche Operation. Die Auswahl einer gemeinsam
triangulierten Fläche ist eindeutig; getrennte übereinanderliegende Flächen
laufen über `ctx.ask`. Der Schritt ändert keine Geometrie und erhält
vorhandene IDs, Provenienz und Erzeuger. Erkennung plus Bearbeitung können
dadurch gemeinsam in einer Transaktion gespeichert und zurückgenommen werden.

`features_in_region` begrenzt die lokale Auswahlliste anhand sämtlicher
belegter Originalflächenpunkte. Früher erkannte ferne Merkmale bleiben in der
Szene, erscheinen aber nicht als Treffer der aktuellen Suchkugel. Die Prüfung
verwendet dieselbe Umfangsgrenze wie die Erkennung, verwirft ferne Kandidaten
an ihren Originalpunkten früh und bleibt auch innerhalb großer Flächen
blockweise abbrechbar. Sie führt keine zweite Erkennung aus.

`detect_known` misst bekannte Merkmale nach einer Operation am großen Netz
erneut. **Anhalten darf es nur für ein Merkmal in `required`** — eines, das
ein späterer Schritt oder eine Passung noch braucht, ohne die starr
mitbewegten. Jedes andere, dessen Umgebung sich nicht nachmessen lässt
(Suchrand, Budget), fehlt im Ergebnis und verliert seine Belegung wie am Netz
üblich; `None` heißt alle. Das Ergebnis je Suchbereich wird einmal gerechnet,
die Entscheidung trifft jedes Merkmal selbst daran — sonst verdeckte ein
unbenötigtes Merkmal ein benötigtes mit demselben Bereich. Gesucht wird wie
an einer Stelle (`_face_seed`, `_connected_to`). Hat nur die Facette gesucht
und liefert sie das Merkmal nicht, heißt der Grund `budget` — nie ein stilles
Fehlen.
**Und es fragt örtlich, nicht den ganzen Körper.** Krümmungssprünge und
Radien liest es nur an den Nähten und Dreiecken seiner Suchbereiche
(`curvature_jumps_at`, `face_radii_at`), ob eine Bohrung frei ist, an den
Flächen neben ihrem Mantel (`_beside_covers`, `_surface_owners_near`: die
Rundflecken der ungeschützten Dreiecke in der Umgebung, mit derselben
Kerbenschließung und denselben Beweisen wie `_surface_owners`, je Körper
gemerkt als `surfaces_near`). Die Antworten sind dieselben wie die der
Ganzkörperfragen; steht eine davon schon, liest es sie (`_known_answer`).
Auch die Radien merkt sich der Körper (`radii_near`), und reichen die
Ausschnitte zusammen über `LOCAL_RADII_SHARE`, rechnet die nächste Frage den
ganzen Körper — örtlich kostet ein Dreieck etwa doppelt so viel. **Eine Kette
misst sich oft erst an der Suche ihres Nachbarn**: Bohrung, Senkung und
Aufweitung sind zusammen länger als jede Kugel um eine ihrer Mitten, und
angehalten wird für ein benötigtes Glied erst, wenn auch keine andere Suche
es vollständig zurückgab. Im Ausschnitt verwirft eine unvollständige
Nachbarhöhlung eine Bohrung nur, wenn sie ein Kettenglied sein kann — Bohrung
oder Kegel; eine Hohlkehle, in die die Mündung öffnet, ist keines
(REST-BOHRUNG-07).
``standing`` nennt Merkmale, deren Belege am neuen Netz unverändert gelten
(nach einer belegten starren Bewegung die exakt mitbewegten,
`features.moved_twin`, nach einer belegten Teilung die in ihre Nachfahren
übertragenen, `features.refined_twin`); sie werden übernommen, nicht
gesucht (Review R6).
**Und zuerst im eigenen
Umfang des Merkmals, dann im belegten Suchumfang** — der schließt die ganze
Umgebung der ursprünglichen Stelle ein und sprengte an dichten Netzen das
Budget; weitergetragen wird der größere (`recorded` in `_recognise_region`).
`local_search_radius` ist ein belegter diagnostischer Suchumfang um
die Merkmalsmitte, kein Nutzermaß. `transformed_searches` nimmt ihn über den
größten Dehnungsfaktor der Operation konservativ mit; Flächengröße allein
bestimmt keinen Radius. Maße werden nur bei nachgewiesen erhaltener Form
transformiert. Eine anisotrope Skalierung darf aus einer Ellipse keine
ungeprüfte runde Bohrung machen. Die anschließende Zuordnung bleibt bei den
bestehenden ID-, Mehrdeutigkeits- und Erzeugerverträgen. Cachekompatibilität
läuft über den bestehenden Versionsschlüssel der Auswertung, ohne Migration
von Dokumentgeometrie oder alten Operationsparametern.

*HEAD-Fassung, in der Zwischenfassung aus dem Absatz zu `detect_known` gestrichen:*

**Gesucht wird wie
an einer Stelle**: Eine ebene Fläche bringt ihre Facette mit (`_face_seed`:
das Dreieck an ihrer Mitte, sonst das nächste in ihrer Ebene — an einer
Platte mit Mittelbohrung liegt die Mitte im Loch —, und nur eines, dessen
Facette die Zuordnung als dieselbe Fläche nähme, `_same_face` mit
`matching.DIAMETER_TOLERANCE`: Die Insel einer Ringnut liegt so hoch wie die
Deckfläche, Review R4), und über dem Budget zählt nur der Teil, der am
Merkmal hängt (`_connected_to`).

Dieselbe Nachmessung wird einmal gerechnet: Das Ergebnis ist eine reine
Funktion von Netz, Merkmalen, Anspruch und Budgets (`_known_key`, bis
`KNOWN_MEMORY_LIMIT` Einträge); ein Halt wird nicht gemerkt.
`forget_known` leert den Merker für Tests.

## Zwei Fragen, zwei Dateien

*HEAD-Fassung.*

`features.py` beantwortet **„was ist das hier"**, `relations.py` die Frage
danach: **„gehören zwei davon zusammen?"** Das ist keine Aufteilung nach
Zeilenzahl, sondern nach Aufgabe — eine Wandstärke steht in keinem der beiden
Merkmale, sie entsteht erst aus ihrem Verhältnis.

Die Nachbarschaften werden nicht bei einer bleiben: Senkung über Bohrung, Rohr,
Bohrungsraster, Bohrung durch zwei Wände. Jede davon in das größte Modul des
Kerns zu hängen hieße, es weiter wachsen zu lassen.

**Die Richtung ist einseitig:** `relations.py` liest `features.py`, nie
umgekehrt — samt dessen Schwellen (`SINK_AXIS_LIMIT`, `SINK_FIT_LIMIT`). Zwei
Achsenprüfungen mit zwei Zahlen wären zwei Antworten auf dieselbe Frage.

Deshalb wohnt auch die **Bedingung** dort und nicht nur die Zahl:
`features.sits_at_the_mouth_of(bore, wider)` beantwortet „gehört diese
Aufweitung zu dieser Bohrung", und zwei Aufrufer fragen sie aus
entgegengesetzten Richtungen — `relations.widening_at_the_mouth` sucht von der
Bohrung aus die Senkung, `features._shapes_on_a_freeform` fragt umgekehrt, ob
eine Rundform an einer Bohrung hängt und damit keine Erfindung ist. `axis_of`
und `centre_of` sind aus demselben Grund mitgewandert.

`cavity_chain_at` verbindet achsengleiche Bohrungs- und Kegelflächen über
vollständig gemeinsame geschlossene Randringe des aktuellen Netzes. Eine
zusammenhängende ebene Ringschulter darf dazwischenliegen, wenn genau ihre
beiden vollständigen Randringe zu den Abschnitten gehören. `cavity_surface_indices`
liefert der Bearbeitung dieselben belegten Schulterflächen zusätzlich zu den
Merkmalsflächen; ein Abstand oder eine nur ähnliche Achse ersetzt sie nicht.
Ein vollständiger gemeinsamer Rand belegt den Anschluss auch dann, wenn
unabhängige Fits an schrägen Mündungen unterschiedliche Achswinkel liefern.
Die räumliche Prüfung beider Achslinien bleibt bestehen. Eine Ringschulter
muss eben sein und zwei vollständig belegte Ringe tragen; ihre Ebene darf
schräg zur Achse liegen. Glatte kleine Übergangsflächen gehören nur dazu,
wenn danach weiterhin genau zwei geschlossene äußere Ringe übrig bleiben.
Mit `mouth_blends=True` (Versetzen, Verdoppeln, Muster, Entfernen der ganzen
Kette, RM-259) genügen so viele Ringe wie vorher — eine Kette mit Schulter
hat vor ihren Schultern vier —, solange der Übergang nah an der Wand bleibt
(`_near_the_wall`); so reist die gerundete Mündungskante einer
Zylindersenkung mit. `cavity_blend_indices` nennt diese Übergänge allein
(der exakte Kern fragt danach, ob die Profile der Kette genügen). Eine
eindeutige Kette beginnt am engsten Bohrungszylinder. Liegt er in der Mitte
des Pfads (RM-245), folgen ihm die Erweiterungen der einen, dann die der
anderen Seite, je nach außen geordnet und die Seiten nach ihrer Bauart
(`_side_order`); `cavity_sides` liest sie an ihrer Lage entlang der
Bohrungsachse zurück. Doppelte Randbelegung, Verzweigung, Zyklus, ein
uneindeutiger Anfang oder Abschnitte, die nicht eindeutig auf einer Seite
liegen, liefern keine Auskunft.
`cavity_chains` bildet die Ringe einmal für den ganzen Objektbaum. Die alten
Paarfunktionen bleiben ohne Netz kompatibel; mit `mesh=` liefern sie nur
echte Zweierketten und kürzen längere Hohlräume nicht ab.
`cavity_chain_state_at` liefert einen `CavityState` — Kette, „nicht sicher
einzeln“ und den Grund mit demselben Wort wie der Gruppenweg
(`ambiguous_cavity_chain` für den berührten fremden Rand,
`cavity_topology_unavailable` für Ränder, die keine Ringe ergeben) —, damit
eine Geometrieoperation nicht auf das Versetzen nur eines Abschnitts
zurückfällt und ihre Absage den richtigen Satz trägt
(`prepare_ops.cavity_refusal`: `NO_OWN_BODY` oder `CAVITY_TOPOLOGY_UNKNOWN`).
Bis zum 20.09.2026 fielen unlesbare Ränder im Einzelweg auf „steht allein“,
während `_feature_group_topology` sie als unsicher führte (P1.5).

## Die Auskunft für das Merkmalspanel

`actions.py` ist die eine Stelle, an der steht, welche Handlung für welche
Merkmalsart gilt — **abgeleitet aus `applies_to` im Register**, nicht als
Liste daneben. Eine zweite Tabelle wüsste beim nächsten Registereintrag die
Hälfte.

`bore_action` bietet nach bestätigter Zuordnung durch `scene.placement.bore_step_of`
die ursprünglichen Bohrungsschrittwerte an, ausdrücklich beschriftet als Werte
vor späteren Größen- und Lageänderungen. Durchmesser und Tiefe stehen vorn;
weitere Felder folgen dem vorhandenen Schema. Die Feldaufbereitung teilt sich
`_saved_fields` mit den Bausteinhandlungen. Verborgene gespeicherte Werte bleiben
im festen Auftrag erhalten; eine Transformation wird nicht in Schrittmaße
zurückgerechnet. Die Handlung ändert über `step` den vorhandenen Verlaufsschritt.
Auch Parameterausdrücke bleiben ursprüngliche Eingaben. Die eindeutige
Erzeugerübernahme liegt gemeinsam in `matching.inherit_originators`: Der
Netzweg ruft sie in `apply_mapping`, die native Auswertung ohne Umbenennung
der Topologiekennungen auf.

Zwei Entscheidungen darin sind Absicht und keine Bequemlichkeit:

- **Was nicht gilt, steht trotzdem in der Liste**, mit `op=None` und einem
  Satz. Ein Panel, das bei einer Verrundung nur den Radius zeigt, lässt den
  Kunden raten, ob der Rest fehlt oder vergessen wurde.

- **Jedes Feld trägt seinen heutigen gemessenen Wert** als Vorgabe. Eine
  Vorgabe, die nicht der gemessene Wert ist, wäre eine stille Änderung, sobald
  jemand auf Übernehmen drückt.

- **Und was an einem geteilten Hohlraum absagen würde, steht grau mit dem
  Satz der Operation** (`_shares_its_cavity`): *Zum Langloch ziehen* an einer
  Bohrung mit Senkung — an der Bohrung wie an der Senkung, mit
  `prepare_ops.NEEDS_A_PLAIN_BORE`, dem Satz, mit dem `slot_hole` selbst
  absagt. Die Bedingung ist eine (`relations.cavity_is_shared`): eine Kette
  oder ein berührter fremder Rand. Was der Aufrufer aus
  `cavity_chain_state_at` mitbringt, gilt; bringt er nur ein Netz mit, fragt
  `actions_for` es selbst — und ohne Netz gibt es keine Sperre, denn
  `bore_and_widening_at` schätzt aus Parametern, und eine Schätzung stellt
  keine Zeile grau. *Merkmal drehen* und *Merkmal verdoppeln* standen vom 14.
  bis zum 15.09.2026 mit auf der Liste — gemessen hatten sie an der Bohrung
  nur den Stumpf unter der Senkung gekippt oder kopiert; seit RM-172 nehmen
  sie die Kette mit (`prepare_ops._chain_tool`), und die Zeile bleibt
  bedienbar.

- **An einer Verengung** (`cone_reason`, R3 der Durchsicht 0.5.1) stehen
  *Merkmal ändern* und *Zum Langloch ziehen* grau mit ihrem Satz — das eine
  setzte das weite Ende, also die Tasche selbst, das andere nahm die Lippe
  mit. *Senken* fehlt dort ganz (`not_offered_at`), auch in der Schnellzeile
  der Oberfläche. Dieselben Sätze sagen die Operationen selbst
  (`prepare_ops._movable_feature`, `_named_bore`), damit Chat und
  Kommandozeile hören, was das Panel zeigt. *Merkmal entfernen* bleibt: Es
  macht die Mündung so weit wie die Bohrung.

- **An der Bohrung einer Kette mit Verengung** sagen *Merkmal drehen* und
  *Zum Langloch ziehen* den Satz der Verengung (`narrowing_reason`: an der
  Verengung selbst über `cone_reason`, an ihrer Bohrung über die Kette), nicht
  den über eine Senkung; `prepare_ops.rotate_feature` und `slot_hole` lesen
  dieselbe Funktion.

- **An einem Kegel einer Bohrungskette** fragt die Zeile *Merkmal ändern*
  die Operation selbst (`_countersink_unsized` →
  `prepare_ops.countersink_resize_refusal`): Eine Senkung an der Mündung
  ihrer Seite wird neu geschnitten; ein Kegel zwischen zwei Stufen oder eine
  Kette, die sich nicht als Einlauf lesen lässt, steht grau — mit dem Satz,
  mit dem die Operation absagt. Bis zur Durchsicht 0.5.1 stand die Zeile an
  jeder Senkung offen, und am Netz sagte die Operation danach ab.

Die Oberfläche fragt die Merkmalsart **nicht** — sie rendert die Liste. Sonst
führt sie dieselbe Tabelle ein zweites Mal.

*HEAD-Fassung.*

Rundungen zeigen den gemessenen Radius. `ActionField.parameter_factor`
übersetzt dieses sichtbare Maß für Vorschau und Übernehmen in den
Durchmesserparameter von `resize_feature`. `feature_value_source` gibt auch
der Sammelhandlung denselben Radius als Vergleichsmaß; ein fehlender
Durchmesser darf weder einen Vorgabewert noch eine falsche Gruppe erzeugen.
Innen- und Außenrundungen bilden getrennte Gruppen. Positiv kreisförmig
belegte Zylinderwände tragen `radial=True`: Ihr Radius ist bearbeitbar,
„Merkmal entfernen“ kann dort keine scharfe Ersatzkante herstellen und nennt
stattdessen die Radiusbearbeitung. **Eine solche Wand heißt in Objektbaum und
Steckbrief „Runde Wand“**, nicht Verrundung — das Ende einer Lasche, der
Boden einer Nut, die Innenwand eines Clips haben keine Kante, zu der sie
gehören könnten; die grauen Zeilen des Panels sagen das mit einem eigenen
Satz (`actions.ROUND_WALL_HAS_NO_PLACE`). Ob die Ecken auf einem Kreis
liegen, prüft der gemeinsame `fit_cylinder` gegen `ROUND_WALL_TOLERANCE` (10 µm) und
nicht allein gegen die Schweißtoleranz: Die ist für Solidons eigene Netze
bemessen, und eine eingelesene Wand liegt Mikrometer neben ihrem Kreis
(Float32 der STL, Toleranz des fremden Kerns). `radial_cylinder` ergänzt
mindestens 180° Umfang und den strengeren Normalenvertrag der radialen
Bearbeitung. Die Haut muss zusammenhängen; ihre Trimmketten bleiben nach
Abtrennung axialer Seiten eben. Eine vom Krümmungssplit ausgesparte Delle
beweist keine vollständige runde Wand. **Und das Panel fragt die
Bedingung der Operation, bevor es eine Zeile anbietet** (`fillet_blocked`,
seit dem 15.09.2026): Eine Verrundung, die quer zu ihrer Achse nicht an
genau zwei erkannte ebene Flächen grenzt, lässt sich nicht auf eine Kante
zurückrechnen — `features.replaces_an_edge` stellt die Frage, dieselbe, die
`geom/edges.py` in `sharp_corner` stellt (`planes_beside`, gemeinsam
gelesen), und die Zeile trägt den Satz der Operation
(`edges.NOT_BETWEEN_TWO_PLANES`). Der Umrissbogen eines Uhrenankers, die
Rundung zwischen Klotz und Zylinder: 50 von 52 Versuchen an 34 Modellen aus
dem Netz endeten vorher erst nach dem Klick mit diesem Satz. Zwei Ebenen
zählen nur, wenn sie den Bogen **tangential** fortsetzen (`planes_beside`
mit `centre`): An den Gleisen einer Modellscheune trafen zwei Ebenen eine
Hohlkehle schräg, *Entfernen* rechnete daraus eine Kante, die es nicht gibt,
und trug 2,7 Prozent des Volumens ab, ohne die Hohlkehle zu treffen. Der
Name bleibt Verrundung — eine Rundung zwischen einer Ebene und einem
Zylindermantel ist eine verrundete Kante, auch wenn keine zwei Ebenen unter
ihr liegen. Eine
runde Wand sagt dazu, ob sie **tangential** in ihre Nachbarn übergeht
(`tangent`, `blends_into_its_neighbours`): Radial versetzt schöbe sie deren
Flanken aus ihrer Ebene, `radial_rounding` sagt dort ab, und beide Zeilen
tragen `actions.WALL_BLENDS_INTO_ITS_NEIGHBOURS` — auch `_drop_the_fillet`
und `_reshape_the_fillet` sagen mit diesem Satz ab.

Bei grob facettierten Langlöchern dürfen abgelehnte Bogenpaare über den
gesamten zusammenhängenden Mantel als Stadion belegt werden. Die Richtung
kommt aus einer vorhandenen ebenen Flanke, die Prüfung aus `fit_stadium`;
ein ähnlicher Radius allein belegt kein Langloch.

**Und der Kern fragt hier ebenfalls nach.** `reason_against(op, kind)` gibt
`None` zurück, wenn die Operation diese Art annimmt, und sonst den Satz, der im
Panel in der ausgegrauten Zeile steht. `geom/prepare_ops.py` ruft es, bevor es
ein Merkmal anfasst — damit gilt `applies_to` auch über Chat und
Kommandozeile, und der Kunde bekommt auf beiden Wegen denselben Wortlaut.

Dass beide Wege zusammenbleiben, hält
`tests/test_features.py::test_the_operation_refuses_exactly_what_the_panel_greys_out`
über alle Merkmalsarten und alle Zeilen fest — nicht ein Kommentar.

Wo eine Zeile zwei Operationen zusammenfasst, nennt der Satz die richtige beim
Namen: `instead_of(op, kind)` sucht die Schwester in derselben Zeile von
`ACTION_ORDER`, und wer `resize_feature` auf eine Bohrung ruft, liest „Dafür
ist *Bohrung ändern* da" statt „geht nicht".

`alike_for_action` beantwortet die nächste Frage des Panels: welche erkannten
Merkmale für **diese** Handlung wirklich gleichartig sind. Die Größenhandlung
vergleicht nur das skalare Längenmaß, aus dem ihr Feld laut
`feature_value_source` gespeist wird; Position und Drehwinkel werden dadurch
nicht versehentlich zu Formmaßen. Versetzen, Drehen, Verdoppeln und Entfernen
vergleichen dagegen den vollständigen echten Flächenausschnitt unter der
ermittelten Verschiebung, zusätzlich zu Profilmaßen und Achse. Gleiche Fläche
oder gleicher Kugelradius allein reichen damit nicht für gleiche Rand- oder
Patchform. **Verglichen wird die Fläche, nicht ihre Vernetzung**
(`_same_surface_patch`, P1.5, 20.09.2026): Jede Ecke des einen Ausschnitts
muss auf den Dreiecken des anderen liegen und umgekehrt, innerhalb von
`units.MAX_FACET_SAG` — eine feiner unterteilte Kopie bleibt dieselbe Form,
eine Kalotte liegt auf ihrer Kugel, die Kugel aber nicht auf der Kalotte.
Bis dahin verglich der Kern Eckpunktmengen und Kantenlängen, und eine
unveränderte Fläche mit anderer Unterteilung galt als verschieden. Die
Kandidatendreiecke kommen aus den `NEAREST_CORNERS` nächsten Ecken und der
Nachbarschaft Ecke → Dreiecke (`_distance_to_surface`), nicht aus einem
zweiten räumlichen Index.

Eine topologisch belegte Hohlraumkette bleibt dabei der Umfang jedes
Mitglieds. Verglichen werden dieselbe Kettenrolle und Artenfolge; für eine
Ganzkörperhandlung außerdem die relative Lage aller Abschnitte und der
gemeinsame Flächenausschnitt. Die Kennung der Gruppe und ihre Mitglieder sind
nach Merkmalskennung kanonisch sortiert und bleiben von Wörterbuchreihenfolge
und starrer Modelltransformation unabhängig. Fehlende Achsen, Flächen oder
eindeutige Randketten stehen als Reason-Code in `uncertain`; der Kern ergänzt
keine angenommene Schrauben- oder Musterabsicht.

Das Panel fragt seine Zeilen gemeinsam über `alike_for_actions` ab. Dieser
Batch bildet den Randgraph einmal für die aktuelle Auswahl; `alike_for_action`
delegiert denselben Weg für einzelne Aufrufer. Der Randgraph lebt nur während
dieses Aufrufs. **Die Flächenausschnitte, ihre Vergleiche und die belegten
Hohlraumflächen hängen dagegen am Körper** (`features.remembered`, Schlüssel
`_shape_key`: Kennung, Art, Dreiecke, Achse und Mitte je Merkmal — seit dem
22.09.2026): Ein Klick auf eine Bohrung der Lochplatte mit 360 000 Dreiecken
kostete 1,0 s im Hauptfaden, davon 0,47 s Flächenvergleiche und 0,22 s
Hohlraumflächen, die Ansicht, Merkmalfenster und Körperfrage nacheinander
neu rechneten; jetzt 0,25 s, und alle drei lesen dieselbe Antwort. Ein neues
Netz oder ein Merkmal mit anderen Dreiecken, anderer Achse oder Mitte ist
ein anderer Schlüssel und erbt nichts. Ebenso liest `_large_facet_faces` die
ebenen Flecken je Körper einmal, und `_one_body` verschweißt eine
ungeschweißte STL je Körper einmal statt bei jeder Frage.
**Und was die Handlungszeilen je Klick fragten, fragen sie je Körper**
(RM-181): `features.planar_mask` (die Ebenen für `fillet_blocked` und
`geom.edges._around`), `nearly_flat_mask` (je Abdruck der gerundeten
Seiten), `prepare_ops.has_own_body` (je Flächen und `alone`), die
verschweißte Kopie (`prepare_ops._welded`) und der Oberflächenindex
(`geom.prepare.surface_index_of`, von `mesh.on_surface(..., index=)` nur für genau diesen
Körper angenommen). Ganze Körperantworten zählen gegen `SUPPORT_CACHE_LIMIT`
(`features.WHOLE_BODY_ANSWERS`), nicht gegen die 4096 je Frage. Die
Randringe sucht `relations._face_boundary_rings` in der Nummerierung des
Rands statt des Körpers, und `_shoulder_connections` fragt nur Facetten, deren
Rand ganz aus belegten Ringkanten besteht (`_only_owned_rims`) — der erste
Klick am Gartenschlauchhalter fiel so von 2,8 auf 1,0 s. Der vollständige
Flächenvergleich (`_same_surface_patch`) sagt „verschieden“, sobald die
Hüllquader um mehr als die Sehnenhöhe auseinanderliegen, ohne ein Dreieck zu
messen. Die Gruppe vergleicht am Langloch Länge und Richtung
(`actions._SLOT_SOURCES`, dieselbe Zuordnung wie das Panel), Richtungen
vorzeichenlos.
**Und der Steckbrief fragt denselben Weg** (`digest._selection_lines`, P1.5):
Der Agent liest zur gewählten Stelle dieselben Mitglieder, Umfänge und Gründe
wie das Panel. Die Sätze zu Nachweis und Grund stehen deshalb einmal im Kern
(`relations.group_evidence_texts`, `group_reason_texts`); das Panel liest sie
von dort, und `test_feature_panel` hält sie mit den Literalen deckungsgleich.

*Früher unter „Grenzen“.*

- **Die direkte Merkmalbearbeitung teilt ihre Kettenauskunft.** Ein bereits
  ermittelter `cavity`-Umfang kann an `actions_for()` und `bore_advice()`
  weitergereicht werden. Ein leeres Tupel ist dabei eine geprüfte fehlende
  Kette, `None` fordert die Ermittlung an. Freie Normalenkomponenten bleiben
  im vollständigen Platzierungsdialog; die Schnellbearbeitung bietet dafür
  ihre eigene Drehhandlung.
  `resize_hole` belegt bei einem von `geom.prepare_ops.bore_entrance` bestätigten
  Einlauf den gespeicherten Umfang `follow` vor. Ohne eindeutigen Einlauf
  bleibt der Schema-Standard `keep`; die Operation prüft dieselben Grenzen.

*Früher im Kopf der Karte, HEAD-Fassung: Maßquellen.*

Maßquellen entstehen beim tatsächlichen Messen. Ein Fit bleibt auch nach
Übernahme eines erzeugten Namens `fit`; ein deklarierter Vorgabewert wird
durch angehängte Dreiecksnummern nicht neu gemessen. `matching` transportiert
Quellen bei belegter Formerhaltung und verwirft sie mit ungültigen Formmaßen.
Neu aus Dreiecken bestimmte Hüllmaße tragen `facets`. `actions` stellt
kurzen Maßzusatz und Erklärung gemeinsam für Steckbrief, Bohrhinweis und UI
bereit: **Jede Quelle hat ein sichtbares Wort**
(`actions.MEASURE_SOURCE_WORDS` — `native` „aus der Konstruktion“, `facets`
„gemessen“, `fit` „eingepasst“, `parameter` „aus dem Schritt“), der Satz dazu
steht im Tooltip (`measure_explanation`). Der Steckbrief nennt eine allen
Maßen einer Zeile gemeinsame Herkunft einmal am Zeilenende („— Maße
gemessen“, `digest._shared_source`), gemischte Quellen je Maß; der Agent liest
damit dieselben Wörter wie der Kunde. Die enge Form
(`measure_qualifier(..., compact=True)`) lässt das Wort der direkten Quellen
weg (`DIRECT_MEASURE_SOURCES`: `native`, `facets`) — für die Marken in der
Ansicht, wo viele einzeilige Beschriftungen um Platz ringen. `ActionField.measurement` beschreibt den Ausgangswert; ein neuer
Zielwert ist keine neue Messung. Historische Felder lesen weiterhin den Schritt.

## Analysekarten (`maps.py`)

*Früher im Kopf der Karte.*

Die Passungskarte übernimmt ausschließlich den aktuellen Prüfbericht.
Informationsbefunde markieren keine Verletzung; ungeklärte oder angenäherte
Proben heißen „Passung prüfen“, belegte Maß- oder Körperverletzungen
„Passung verletzt“. Eine benannte Beziehung führt denselben Befund zu beiden
Gegenstücken. Positive Lageproben überschreiben keine offenen oder verletzten Befunde.

Wandkarten beginnen bei null und deckeln ausschließlich die obere
Farbgrenze. So behalten Karte und Legende dieselbe geordnete Skala, auch
wenn jede gemessene Wand bereits dicker als der Deckel ist (§18.4).

Wand- und Stützkarten erhalten ihre Rasterweite über `maps.build` aus der
realen Extrusionsbreite des Profils. Ohne Profil gilt nur die geometrische
Rastergrenze. Erkennungsauflösung und Herstellbarkeit bleiben getrennt
(§11.2): Drucker- und Materialwechsel verändern keine Merkmale oder IDs.

*Früher unter „Die Auskunft für das Merkmalspanel“.*

`AnalysisMap` trennt Messwert und Farbdarstellung. `values`, `low`, `high` und
`threshold` bleiben immer physische Werte; Renderer und Legende lesen gemeinsam
`display_values`, `display_limits` und `value_at_display_fraction`. Die
Krümmung nutzt eine monotone Asinh-Skala mit `EPS_DISPLAY` als linearem Bereich:
Null bleibt endlich, große nahezu ebene Radien verdrängen kleine Verrundungen
nicht aus der Farbrampe, und kein Wert wird gekappt oder verschwiegen.

Die Netzfehlerkarte fragt dieselbe Schnittsuche wie die Reparatur
(`repair.crossings_of`, ein Ergebnis im Cache des Netzes) mit demselben Budget
(`repair.intersection_budget`): Beide sehen dasselbe, und die Suche läuft je
Netz einmal. Greift das Budget, bleiben belegte Fehler markiert, und
unbekannt (`nan`) sind nur die Dreiecke, die die Suche noch nicht geprüft hat
(`Crossings.checked`) — nicht der ganze Körper. Die Legende nennt die
unvollständige Prüfung ausdrücklich; eine leere Trefferliste aus einer
begrenzten Suche ist keine Entwarnung. Die vierte Stufe zeigt die Kanten, an
denen die Außenseiten gegeneinander zeigen (`repair.crossed_edge_faces`) —
der Ort zu `repair.normals_inconsistent`.

Die Formabweichungskarte liest ausschließlich vorhandene `SurfacePatch`-Belege
und prüft gefüllte Originaldreiecke. Identische Träger teilen die Rechnung;
widersprüchliche, fehlende oder numerisch nicht begrenzbare Anteile bleiben
`nan`. Ein zusätzliches Byte je Dreieck erhält dabei alle tatsächlich
verwendeten Quellen, auch über zusammengefasste gleiche Träger hinweg.
Die Werte sind obere Abstandsgrenzen. `maximum_interval` umfasst nur bekannte
Facetten; `numerical_error` ist ihre größte verbliebene Rechenbreite. Der
Zeugenpunkt gehört zur unteren Grenze, niemals zum behaupteten Erreichen
der oberen Grenze. `focus_point` mittelt für diese Karte keine Fundorte.
Fortschritt und Abbruch laufen durch denselben Kartenauftrag. Es entsteht
kein neuer Fit, keine automatische Geometrieänderung und kein G-Code-Messwert.

Die Stützkarte wird nach drei Sekunden beendet und bietet **Dreiecke
verringern** an. Das ist ein begründetes Interaktionsbudget für den direkten
Kartenklick, keine Vorhersage aus der Dreieckszahl: §2.8 verlangt bei langen
Rechnungen Abbruch und Bedienbarkeit, und §31 setzt für die andere aufwendige
Analysekarte Wandstärke drei Sekunden. Dreieckszahl und Schichtzahl sind dafür
keine Vorabschranke; die laufende Rechnung prüft ihr Budget zwischen
begrenzten Arbeitsstücken. Der vollständige Schichtanalyseweg bleibt davon
unberührt; das Budget gilt nur der Karte.

Die Wandkarte verfolgt nur Strahlen, die noch Material sehen. Ihre Zentren
und Normalen werden erst beim Ausscheiden kompakt gespeichert; der erste
Austritt bestimmt die Schrittzahl. So kosten massive Körper keine erneuten
Indexkopien je Schritt, und Material hinter einer Lücke zählt weiterhin
nicht zur ersten Wand. Rasterrundung und Abbruchpunkte bleiben gleich.

## Stolperfallen

### Auflösung ist nicht Herstellbarkeit

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Die automatische Erkennung hat eine profilunabhängige Auflösung.**
  `MIN_CYLINDER_DIAMETER` (0,5 mm) gilt für die eingepassten
  Rundformen. Die Frage steht
  einmal als `_too_small_to_make`, damit die nächste Art sie nicht wieder
  übersieht; beim Torus entscheidet das kleinere von Ring und Röhre.

*Früher im Kopf der Karte.*

Scharf begrenzte ebene Funktionsflächen hängen an der absoluten
Erkennungsauflösung, nicht an der größten Fläche des Körpers. Vor der
Veröffentlichung müssen ihre Normalen tatsächlich koplanar sein. `inner`
verlangt dieselbe Schale und eine örtlich darüberliegende parallele
Außenkontur; eine versetzte Lippe oder ein fremdes Teil genügt nicht. Die
Deckungsprobe läuft blockweise über die parallelen Kandidaten und hört beim
ersten Treffer auf (`_face_roles`, `FACE_ROLE_BLOCK`): Am Kumiko-Gitter mit
7 295 Flächen hat jede rund 200 Kandidaten, und ein Punkt samt `covers` je
Kandidat kostete 5,5 der 7 Sekunden der Flächenerkennung (21.09.2026).
An Rundflächen bestimmen nur gekrümmte Nähte die Innenlage, keine ebenen
Dreiecksdiagonalen.

### `matching.match`

*Früher im Kopf der Karte.*

`matching.match` bereitet dieselben körperbezogenen Merkmalsvektoren für
Vollvergleich und räumliche Vorauswahl auf. Ein `cKDTree` mit Maximumsnorm
und rational hergeleiteter Rundungsreserve verwirft nur räumlich unmögliche
Paare; weder Nachbarzahl noch neue Geometrietoleranz begrenzen die Auswahl.
Ein gemeinsamer Vektorkostenhelfer bedient Einzelpaar, vollständige Matrix,
selektive Paare und gespeicherte Zuordnungsantworten. Die ursprüngliche
Skalar- bzw. Batchreduktion der Norm bleibt dabei erhalten.
Die volle Matrix entfällt nur mit Zertifikat: Jede Zeile der kleineren
globalen Solverseite hat einen strikt besten angenommenen Partner, und
diese Partner sind paarweise verschieden. Sonst bleibt der vollständige
globale Solverkontext mit identischen Strafkosten erhalten; eine Aufteilung
in Zusammenhangskomponenten würde Gleichstände und alte IDs verändern.
Die Solverantwort ist noch keine freigegebene alte Identität. Eine exakte
Kostenhülle summiert die vorhandenen binären Kosten einschließlich Strafpaaren
auf der kleineren vollständigen Solverseite; pro Zeile abgerundete Grenzen
vermeiden einen Verlust kleiner Unterschiede in großen Strafsummen.
Maximalitätsprüfung, starke Zusammenhangskomponenten und gerichtete Wege ab
freien alten beziehungsweise zu freien neuen Knoten begrenzen die global
möglichen Partner. Daraus abgeleitete Referenzkosten bleiben beim Abschluss
lokaler Zeilenrivalen und aktivierter Besitzeransprüche unverändert.
Ein geöffneter Besitzer führt sämtliche eigenen Ansprüche nach; offene
Kandidaten können dadurch keinen außen fest zugeordneten Nachfolger belegen.
Die Lücke zwischen oberer und unterer Schranke gilt je
Zusammenhangskomponente der angenommenen Paare (`_accepted_components`):
Ein Optimum außerhalb der Komponente ändert die Wahl in ihr nicht, und ein
Hall-Defizit an ganz anderer Stelle öffnet kein eindeutiges Paar mehr. Die
Hülle behauptet weiter keine Kostengleichheit sämtlicher Kandidaten.
Auch mehrere alte Ansprüche auf nur einen neuen Kandidaten sind mehrdeutig.
`require_injective` sperrt doppelte Nachfolger gemeinsam vor Namen- und
Erzeugerübernahme. `fresh` bezeichnet alle Ziele ohne freigegebenen alten Namen.
Vektoraufbereitung, Baumabfragen, Kostenblöcke, Solverabschluss, Hülle,
Graphsuche, Anspruchsschluss und Ergebnisbildung prüfen den vorhandenen
Abbruchcallback. `resolve` führt ihn auch durch gespeicherte Antworten bis
vor die Rückgabe weiter. Die Merkmalsobergrenze bleibt eine gesonderte
Release-Entscheidung.
Gespeicherte Antworten verlangen einen gültigen historischen Fingerabdruck
und einen endlichen aktuellen Bezugsrahmen. Jede aktuelle Merkmalslage muss
tatsächlich dreidimensional vorliegen; nichtendliche Vektoren oder Kosten
lassen die gesamte Wiedererkennung offen. Auch ein ungültiger Nichtgewinner
darf keinen vermeintlich eindeutigen Treffer freigeben. Die historischen
Vorgaben optionaler Achsen- und Maßfelder bleiben unverändert.

### Erben nur mit Beleg

*Früher unter „Die Sache mit der Stabilität“.*

Eine eindeutig zugeordnete Neu-Erkennung übernimmt `created_by` vom
vorherigen Merkmal, wenn sie selbst keinen Erzeuger trägt. Formdaten und
Dreiecke stammen weiterhin aus der frischen Erkennung. Mehrdeutige oder
unverbundene Merkmale erhalten keinen geratenen Erzeuger. So bleibt eine
aufgebrachte Textur auch nach nachfolgenden Schritten am richtigen Schritt
des Verlaufs bearbeitbar.

### Maße reisen nur bei belegter Formerhaltung

*Früher unter „Lokale Erkennung großer Netze“.*

`matching.transformed_features` liefert die gemeinsame maßbewusste Auskunft
für globale und lokale Zuordnung: Suchkandidaten sowie die Teilmenge `exact`,
deren Formbeschreibung nach der Abbildung weiter gilt. Nur diese Teilmenge
darf ohne neue Messung erhalten bleiben. Normalen folgen der invers-transponierten
Matrix, Richtungsvektoren der linearen Matrix; Spiegelungen kehren eine bekannte
Gewindehändigkeit um. Gleichförmige Maßstäbe skalieren Längen, Flächen und Volumen
mit ihrer jeweiligen Dimension. Achsweise Skalierung erhält Kreisbohrungen nur
bei belegter gleicher radialer Dehnung und orthogonaler Achse. Zusätzliche
Kreismaße an einer ebenen Passungsfläche sind dabei ebenfalls Formzusagen.

`void.centre` und `void.size` beschreiben die Welt-AABB der Hohlraumschale.
Bei beliebigen Drehungen werden diese Werte aus den vorhandenen Originalflächen
am transformierten Netz neu gemessen; die gedrehte alte AABB ist nur eine
Suchhülle. Ungültige Gewindekandidaten dürfen keine anderen Merkmale als
vermeintliche Gewindeflanken unterdrücken.

*Früher im Kopf der Karte.*

Zylinder- und Stadionfits legen ihr Achsvorzeichen gemeinsam über
`units.positive_axis` fest; nahe Betragsgleichheit folgt derselben Regel wie
im exakten Kern.

`matching.moved_features` transportiert bei einer erzeugten Profilklemme
auch `profile_clamp_y`. Zusammen mit X und der Flächennormalen bleibt dadurch
die Händigkeit eines gespiegelten Rahmens erhalten. Die lokale Konturbeschreibung
`profile_clamp` bleibt untransformiert; beide Diagnosefelder gehören nicht
zu den numerischen Formmaßen im Gleichartigkeitsvergleich. Ein gültiger Sitz
wird im Ersatzweg gegen die wirkliche Geometrie erneut belegt.

### Träger und Stützen

*Früher im Kopf der Karte.*

`Feature.surface_patches` hält ausschließlich schon akzeptierte analytische
Teilträger mit ihren aktuellen Originaldreiecken. `surfaces.valid_patch`
prüft vollständige Parameter, endliche Zahlen und eindeutige Indizes;
`planar_patch` belegt die vorgegebene Ebene an allen Originalecken gegen
`EPS_GEOM`. Ein Artetikett, eine Auswahlmitte oder ein Vorgabemaß erzeugt
keinen Träger. Kegel speichern ihre wirkliche Spitze und gerichtete Achse
mit Halbwinkel in Radiant; die semantischen Anzeigeparameter bleiben getrennt.

Langlöcher behalten die einzelnen angenommenen Bogenfits und nachgewiesenen
Flanken. Der Stadionweg zerlegt den bereits akzeptierten Fit an seinen
Teilnähten; nahtüberspannende Dreiecke bleiben unbekannt. Offene Langlöcher
übernehmen auch während der Flutung belegte Bogenfacetten, Mündungsfasen
behalten ihre Kegelträger. Beim Zusammenfassen zum Innenraum werden nur die
tatsächlich überdeckten Originaldreiecke übernommen. Eine lokal ausschließlich
topologisch zugeordnete Materialinsel erhält ohne vorhandenen Fit keinen Träger.

Lokale Ausschnitte führen Trägerindizes über dieselbe Originalzuordnung wie
ihre Merkmale zurück. `clipped_patches` und `reindexed_patches` reparieren
keine ungültigen Indizes. `matching` transformiert jeden Träger genau einmal;
Ebenen bleiben affin erhalten, Kreisflächen nur bei nachgewiesener
Formerhaltung. Ein elliptisch verzerrter Rundträger entfällt. Die bestehenden
Erkennungscaches zählen zusätzlich die gespeicherten Trägerindizes. Eckentests
und Bereichszuordnung arbeiten blockweise mit dem vorhandenen Abbruchsignal;
es gibt keine zweite Erkennung, keine zusätzlichen Fitobjekte oder Eckpunktkopien.

### Eine Rundform braucht vollen Beleg

*Früher unter „Grenzen“.*

- **Ein Kandidat ist noch kein Endmaß.** Kegel, Kugel und Torus verfeinern
  ihre Maße gemeinsam mit dem geometrischen Punktabstand in zentrierten,
  skalierten Koordinaten. **Der Löser rechnet an höchstens
  `FIT_SOLVER_POINTS` Stützpunkten** (jeder k-te der koordinatensortierten,
  die belegte Kegelspitze bleibt darin); Residuum und Punktfehler lesen
  danach jeden belegten Punkt. Sechs Kegelgrößen aus hunderttausend Punkten
  sind keine bessere Antwort als aus viertausend — die Schüssel mit 215 000
  Dreiecken trägt ihre Haut als einen Fleck, und zwei Kegelfits daran
  kosteten 1,95 der 2,7 Sekunden der Facettenfrage (22.09.2026). Der begrenzte Löser muss konvergieren und alle
  freien Größen bestimmen; unvollständige oder rangdefiziente Ergebnisse
  werden nicht veröffentlicht. Die Ableitung bringt jedes Residuum geschlossen
  mit (`jacobian` an `_refined_fit`): dasselbe Minimum, ohne die numerische
  Schätzung, die je Schritt so viele Residuen kostete, wie es Größen gibt
  (am Korpus gemessen: Ableitung gegen Differenzen bis 10⁻⁹, Ergebnisse
  gleich bis auf flache Täler, in denen beide Wege gleich gut und gleich
  unbestimmt sind). Der Abbruch erreicht sowohl die Fächersuche
  als auch jede echte Residualauswertung. `fit_torus_samples` bleibt der
  gemeinsame Kandidatenweg für echte native D1-Punkte und Mesh-Normalen;
  eine Facettenkorrektur gehört dort nicht hinein.
  `fit_error` bezeichnet ausschließlich den größten geometrischen Abstand
  der verwendeten Stützpunkte in Millimetern, beim Kegel orthogonal zum
  Mantel. Er ist weder ein Band der wirklichen Netzhaut noch eine Zusage
  über unbekannte Ursprungsmaße. Maximaler örtlicher Punktfehler und alle
  tatsächlichen Flächennormalen begrenzen die Veröffentlichung zusätzlich.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Ein Kreis allein bestimmt keinen vollständigen Kegel.** Bleibt nur ein
  belegter Kreis, können die flächengewichteten Mantelnormalen Achse und
  Winkel binden. Dann müssen die drei Spitzenkoordinaten für sich bestimmt
  sein und sämtliche bestehenden Formprüfungen weiter gelten.
  `ConeFit.normal_constrained` nennt diesen internen Fall. Der daraus
  geschätzte Winkel trägt weiterhin `fit`; auch ein verschwindender
  Punktfehler beweist keinen ursprünglichen Konstruktionswinkel.

*Früher unter „Grenzen“.*

- **Eine Kugel braucht vier bestimmte Unbekannte.** Hat ihr lineares System
  nicht Rang vier, bleibt mindestens eine Mittelpunktkoordinate offen. Das ist
  bei senkrecht extrudierten Kurvenwänden der Regelfall; ihr Kugelfit hängt
  sonst von der absoluten Lage ab und wird abgelehnt.

- **Eine veröffentlichte Kugel braucht belegte Krümmung in zwei Richtungen.**
  Der algebraische Fit bleibt intern für die Formauswahl erhalten; erst die
  Ausgabe in den Objektbaum verlangt über die zentrierte Normalen-SVD einen
  belastbaren Mittelpunkt und zwei Richtungen. Der radiale Fehler wird
  zusätzlich an der lokalen Fleckausdehnung gemessen. Beides ist unabhängig
  von Lage, Drehung, Skalierung und Einheit. Ein schmaler Kugelstreifen oder
  ein fast kugeliges Ellipsoid wird damit kein bearbeitbares Kugelmerkmal und
  fällt auch nicht als Kegel oder Torus durch; zwei verschieden triangulierte
  echte 5°-Kalotten bleiben Kugeln.

- **Ein veröffentlichter Torus belegt auch seine Flächennormalen.** Der
  Punktabstand zur eingepassten Röhre bleibt Teil der Formauswahl, reicht aber
  für den Objektbaum nicht: Dort müssen die Normalen flächengewichtet zur
  nächsten Stelle der Ringmittellinie passen. Die größte Änderung der
  analytischen Normale vom Dreiecksschwerpunkt zu seinen Ecken wird als
  Tesselierungsauflösung abgezogen; ein grober echter Ring wird dadurch nicht
  an einer glatten Schwerpunktnormale gemessen. Diese Formgleichung ist von
  Lage, Drehung, Maßstab und Einheit unabhängig. Ein echter in beiden
  Richtungen beschnittener Ring bleibt erhalten; örtlich torusähnliche
  Freiformflecken werden nicht als bearbeitbarer Wulst ausgegeben.

- **Ein veröffentlichter Kegel erfüllt dieselbe Normalenprobe.** Ein guter
  Punktfit allein darf aus einem gekrümmten Freiformstreifen keine Senkung
  machen. Die flächengewichtete Prüfung berücksichtigt ebenfalls die
  Tesselierungsauflösung und verlangt keinen Vollumfang: echte Teilbogenkegel,
  beide Flächenrichtungen und die Randkegel einer mehrteiligen Bohrung bleiben
  erhalten. Zusätzlich müssen alle wirklichen Facettenecken den
  dimensionslosen Punktabstandsvertrag des Fits erfüllen. Ein breites
  Profilfasenband wird dadurch nicht zum einzelnen Kegel, nur weil seine
  Dreiecksschwerpunkte passen.

### Kreis und Zylinder

*Früher im Kopf der Karte.*

Kreisfits zentrieren ihre Punktmenge vor den quadratischen Termen, damit
eine Translation weder Kondition noch Formentscheidung verändert. Der
Kåsa-Ausgleich verwendet skalierte Householder-QR mit Spaltenpivotierung
und fest summierten Produkten. Er quadriert die Kondition schmaler Bögen
nicht durch Normalgleichungen und übernimmt keine LAPACK-Rundung als
Mittelpunkt einer Folgeoperation; ranglose Punktmengen tragen keinen Kreis.
Die gezielte Kreisfit-Plattformsonde rechnet beide Erkennungen mit geleertem
Merkmalscache neu. Ein Stadion muss auch seine schlechteste Konturecke
innerhalb der Formtoleranz halten; örtliche Mulden werden nicht über den
mittleren Fehler geglättet.

Geschlossene Langlöcher beziehen ihre Breite aus dem Abstand der geprüften
ebenen Flanken. Offene Langlöcher übernehmen Kreisradius und Achse aus
demselben geprüften `CylinderFit`; ein zweiter Kreisfit über Flanken- oder
Sehnenpunkte würde das Maß erneut verzerren. Beide Wege behalten die volle
Rechengenauigkeit bis zur Anzeige. **Am exakten Kern trägt das offene
Langloch, was seine nativen Träger belegen** (`native_open_slot_measures`,
P1.5): Deckt ein nativer Zylinder den ganzen Bogen, kommen Durchmesser,
Achse und Bogenmitte exakt aus ihm; liegen alle Flanken in nativen Ebenen,
die Richtung aus deren Normale — jeweils mit der Quelle `native`. Mündung,
Weg, Länge und Tiefe hängen am Rand des Netzes und bleiben `fit` und
`facets`; am reinen Netz ändert sich nichts. Keine pauschale Hochstufung —
und der native Zylinder muss den gemessenen Bogen treffen, Achse im Vertrag
von `PARALLEL_AXES`, Radius im Vertrag von `SAME_RADIUS`: Bis zum 21.09.2026
genügte ein Skalarprodukt der Achsen ungleich null.

*Früher unter „Grenzen“.*

- **Ein Zylindermittelpunkt kommt aus seinen Endringen.** Die Mitte entlang
  der Achse ist der Mittelwert der beiden Vertexextrema des Flecks. Ein
  Dreiecksschwerpunkt würde dicht unterteilte Abschnitte stärker gewichten und
  verschöbe das Werkzeug beim Ändern einer Bohrung.

- **Zylinderachsen behalten ihren gerichteten Bezug.** Bohrung, Zapfen,
  Verrundung, Langloch und Gewinde teilen diese Zuordnung. Beim ersten Fit ist
  die erste größte Betragskomponente positiv; nahezu gleich große Komponenten
  werden innerhalb der Rechengenauigkeit gleich behandelt. Nach einer
  Zuordnung richtet sich ausschließlich das Vorzeichen der neuen Messachse
  am Vorgänger aus. Dieser ist über `moved_features` bereits mit der
  Operationsmatrix transformiert. Eine alte Weltachse wird nie unverändert
  auf einen gedrehten Körper kopiert; Kegel und Flächennormalen bleiben
  geometrisch gerichtet. Der Torus behält die gemessene Normale seiner
  Symmetrieebene, da sie keine Längsrichtung darstellt.

- **Das Zylindermaß kommt aus belegten Konturecken.** Achse und
  Achslage verwenden flächengewichtete Normalen und echte axiale Extrema;
  alle quadratischen Terme liegen in einem zentrierten Maßrahmen. Die
  zyklische Konturprüfung entfernt kollineare Unterteilungen vor der
  Vereinfachung. Ein neuer Schnittendpunkt innerhalb einer Facette trägt
  keinen Kreis: Erst verschiedene angrenzende Mantelnormalen belegen eine
  ursprüngliche Kreisecke. Getrennte deckungsgleiche STL-Ecken zählen dabei
  gemeinsam. Ganze Haut, einzelne Konturecken, Normalenrichtung und
  aufgelöste Krümmung müssen passen; ein regelmäßiges Vieleck beweist keine
  ursprüngliche Konstruktionsabsicht. Die Winkelgrenze gilt der gesamten
  Krümmung, nicht jedem kleinen Facettenschritt. Auch ungestützte
  Schnittendpunkte bleiben innerhalb des belegten Umkreises: Ein richtiger
  Halbkreis macht lange Tangentenflanken nicht zu einem Zylindermantel.
  Der nachfolgende Größenfilter vergleicht das radiale Netzband mit einer
  konservativen Körperausdehnung quer zur Fitachse, nicht den größeren
  Umkreis mit einer einzelnen kleineren Weltachsenbreite des Vielecks.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Kreismaß, Fitfehler und tatsächliches Netzband bleiben getrennt.**
  `CylinderFit.radius` ist ein geschätzter Kreisradius. `residual` misst
  den mittleren Kontureckenfehler relativ dazu, `spread` normiert ihn mit
  der unterteilungsfesten Sehnenhöhe (`_chord_sag`) und der numerischen
  Untergrenze `ROUND_WALL_TOLERANCE`. `fit_error` ist der größte Fehler
  aller belegten Kreisecken in mm, keine Nennmaßunsicherheit.
  `radial_min` und `radial_max` messen die wirklichen Dreiecksflächen
  zur Fitachse; ein fehlender Bogen bekommt keine Schließsehne. Diese drei
  Diagnosewerte reisen an Bohrung, Zapfen und Zylinderverrundung mit.
  Sie enthalten kein Fertigungsspiel und ersetzen keine Einbau- oder
  Kollisionsprüfung. `None` an alten von Hand erzeugten Fits ist kein
  Nullfehler. Der Abbruch läuft durch Kontur- und Dreiecksblöcke; erst die
  vollständige Erkennung schreibt ihren Merkmalscache.
  `residual` bleibt beim Nachführen dimensionslos; `fit_error` und die
  beiden radialen mm-Maße skalieren mit der belegten radialen Dehnung.

*Früher unter „Grenzen“.*

- **Eine benachbarte Torusfacette gehört nicht zum Zylindermaß.** Bleibt
  sie beim Krümmungssplit an einer Säule hängen, schlägt die bereits
  belegte Torusachse eine Teilung vor. Der vollständige Zylinder und die
  vollständig ergänzte, angrenzende Rundung müssen beide ihre normalen
  Formprüfungen bestehen. Die Auskunft verwirft keine Restfläche und
  erweitert keine Maßtoleranz. **Gefragt werden nur die Ringe, die das Stück
  oder seine Nachbarn tragen** (`_TorusCandidates`, eine Karte Dreieck →
  Kandidat mit zwei Plätzen je Dreieck): Am Drachen aus TripoSG fragten
  27 168 Stücke jeden Kandidaten, 18 von 72 Sekunden eines Profils
  (21.09.2026). Die Karte ist eine Vorauswahl in Kandidatenreihenfolge; ob
  ein Stück wirklich angrenzt, prüft der Aufrufer weiter an den Dreiecken.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Was zerfällt, wird wieder zusammengeführt.** Ein Mantel kommt aus
  der Fleckenbildung oft in Stücken; `_merged_cylinders`, `_merged_cones`
  und `_merged_tori` machen daraus wieder **ein** Merkmal. Anker ist, was von
  der Größe des Ausschnitts unabhängig ist: beim Zylinder der
  Achsabschnitt, beim Kegel die **Spitze**, beim Ring der Mittelpunkt. Beim
  Zylinder darf der gemeinsame Fit nicht schlechter streuen als seine Teile
  — **oder** der neue Fleck liegt nachweislich auf der vorhandenen Wand
  (`_lies_on_the_cylinder`, im Vertrag von `CYLINDER_SPREAD`): Ein Fit über
  mehr Punkte streut immer etwas mehr, und an einer Bohrung Ø 30 blieb der
  vierte Bogen sonst draußen (zwei Hohlkehlen R 15 statt einer Bohrung,
  Kennung verloren; `REMONTOIRE ESCAPEMENT-12`, 15.09.2026).

### Ebenen

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Die Ebenenregel zählt ein geteiltes Teilstück höchstens je Umrissecke**
  (`_flat_counts`, `_outline_corners`): `MIN_FLAT_FACES` meint die Ecken eines
  Deckels, und ein Mantelstreifen, in den *Kanten verfeinern* innere Punkte
  gesetzt hat, hat vier. Gedeckelt wird nur eine Facette mit inneren Punkten
  und höchstens `_TESSELLATION_CORNERS` Ecken; jede andere zählt ihre
  Dreiecke. Splitter unter der Erkennungsauflösung — Breite
  (`_area_and_reach`) durch Randknick unter dem Radius von
  `MIN_CYLINDER_DIAMETER`, gefragt über `_a_sliver` und `_too_small_to_make`
  — behalten ihre Dreiecke und bleiben aus der Rundformsuche heraus. Ein
  geteilter Streifen zählt damit wie der ungeteilte.

*Früher unter „Grenzen“.*

- **Und ein geteiltes Teilstück trägt seinen Radius auch innen**
  (`face_radii` über `_through_the_piece`, dieselbe Frage `_divider_pieces`
  wie die Ebenenregel, R1 der Durchsicht 0.5.1). Ein Dreieck mitten im
  Mantelstreifen hat nur koplanare Nachbarn und damit keinen eigenen Radius;
  es bekommt den kleinsten, den die Dreiecke seines Streifens an ihren Nähten
  lesen. Ohne das zerfiel die Trennung der Prismabögen an jeder Grenze
  zwischen Innen und Naht, und aus zwei Verrundungen wurde eine gerundete
  Seite. Eine Facette ohne innere Punkte behält ihre eigenen Radien; an einem
  ungeteilten Netz ändert die Regel nichts.

- **Dreieckszahl macht aus einem Mantelstreifen keine Ebene.** Schmale oder
  längs unterteilte Facetten mit belegter Rundungsnaht dürfen den Planarfilter
  nur verlassen, wenn ihre zusammenhängende Gesamtfläche die vollständige
  Formprüfung für Kegel, Kugel oder Torus beziehungsweise einen Zylinderfit
  mit vollem Umfang trägt. Auch breite Facetten benötigen diesen gemeinsamen
  Nachweis; einzelne passende Dreiecke geben keine Deckfläche frei. Die
  bestehenden Größen-, Winkel- und Fitgrenzen gelten dabei weiter.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Was nach allen Einpassungen an gerundeter Haut übrig bleibt, ist eine
  gerundete Seite** (`detect_curved_faces`, Art `curved_face`). Der Bogen
  eines D, der Mantel eines o, die Schwünge einer S: kein Zylinder, keine
  Kugel, kein Ring, keine Ebene — und bis zum 11.09.2026 deshalb gar nichts,
  ohne Zeile im Baum und ohne Filament. Die Phase läuft **zuletzt**, weil sie
  den Rest nimmt: gerundete Dreiecke (`_curved_faces`), die kein Merkmal in
  seinen `face_indices` führt, zusammenhängend über glatte Nähte, mindestens
  ein Prozent der Haut (`CURVED_SIDE_SHARE`) und `MIN_FACE_AREA`. **Gerundet
  ist eine ganze koplanare Facette, wenn eines ihrer Dreiecke an einer
  Rundungsnaht liegt** (24.09.2026): Sonst fiel die Mitte einer geteilten
  Mantelfacette heraus, und dieselbe Seite war nach einer formgleichen
  Neuvernetzung kleiner. **Und die
  Flächenschranke ist keine harte Grenze mehr** (P1.5, 20.09.2026): Ein
  Fleck unter 4 mm² ist eine Fläche, wenn seine Ränder es belegen —
  an jeder Naht zu einem fremden Dreieck ein Knick von mindestens
  `CURVATURE_LIMIT`, **jede Randkante mit einem Nachbarn** (an
  `plate_countersunk.stl` stoßen die Mantelstreifen der Bohrung per
  T-Stoß aneinander, und ohne diese Bedingung galt jeder zweite als
  Fläche), **hinter jeder Naht ein Dreieck, das selbst zu einem Fleck
  gehört** (auf der verrauschten Freiform mit 200 000 Dreiecken sind zwei
  zufällig ebene Dreiecke ringsum scharf geknickt und grenzen an nichts, das
  eine Fläche wäre — zwei „Flächen" von 0,22 und 0,16 mm², gemessen am
  21.09.2026), nichts davon auf einer Rundung, kein Streifen
  (`_facets_standing_apart`, gelesen von `_large_facet_faces` und
  `_planar_face_entries`, auch bei der lokalen Rollenprüfung). Der
  1-mm-Nocken auf einer Platte hat so am Netz dieselben fünf Flächen wie
  am exakten Körper; die Facette einer Kugel und der Streifen eines
  Mantels stoßen an ihre Nachbarn nur mit der Stufe der Rundung und
  bleiben, wo sie waren. Auf einer
  Freiform läuft sie nicht — dort wäre die ganze Haut eine Seite. Am Korpus
  bleibt nichts übrig; das ist der Test, der die Phase in Schach hält.
  `inner` kommt aus der Konvexität der Nähte, nicht aus einer Normale: Ein
  Bogen hat keine. Eine **eigene Art** und nicht `face` mit Vermerk, weil
  zwölf Operationen an `face` eine Ebene voraussetzen; was an ihr geht, sagt
  `applies_to` — Filament, sonst nichts.

### Nachtrennung

*Früher unter „Grenzen“.*

- **Ein Fleck mit einer Kerbe von einem Dreieck bekommt es zurück**
  (`_notch_faces`, `_without_notches`, 17.09.2026). `relations.boundary_rings`
  verlangt an jedem Randknoten genau zwei Randkanten; fehlt einem Band ein
  einziges Dreieck, laufen dort vier zusammen, aus zwei Randringen wird einer,
  und ohne Ringe gibt es keine Nachbarschaft — also keine Bohrungskette. Der
  Fall ist plattformabhängig und gemessen: Dieselbe Senkung trägt auf Windows
  und Ubuntu 241 Dreiecke, auf dem Mac der CI 240, bei identischen Maßen.
  Geschlossen wird nur, was **eindeutig** ist: genau ein freies Dreieck bringt
  den Rand in Ordnung. Bringen es zwei, bleibt der Fleck, wie er ist — dort
  steht eine Gabelung, und die zu raten verbietet Regel 21.
  **Gesucht und geprüft wird am Knoten, nicht im Netz** (20.09.2026):
  `_rim_of` zählt Kanten und Randgrade eines Flecks einmal, `_candidates_at`
  liest die Kandidaten über den eigenen Index Ecke → Dreiecke
  (`_vertex_faces_index`, gepackt aus einer stabilen Sortierung; trimeshs
  `vertex_faces` fällt bei **einem** entarteten Dreieck in eine Schleife je
  Ecke — 20 s bei 300 000, sechs Minuten bei 1,3 Millionen) und den
  Nachbarindex (`_neighbour_index`, je Körper einmal im Cache von trimesh),
  und `_closes`
  prüft eine Kandidatenmenge an ihren eigenen Kanten. Vor der Kombinationssuche
  verwirft `_closing_set` ausschließlich unmögliche Fälle: Jedes ergänzte
  Dreieck kann höchstens drei ausgefranste Knoten berühren; mehr als
  `3 * NOTCH_AT_MOST` Knoten können daher niemals gemeinsam geschlossen werden.
  Am Rand dieser notwendigen Schranke bleibt die bisherige Prüfung unverändert;
  es entsteht weder ein weiterer Cache noch eine neue Geometrietoleranz.
  Die erste Fassung lief
  je Kandidatenmenge noch einmal über den ganzen Fleck und alle Paare des
  Netzes — am Drachen aus TripoSG (325 244 Dreiecke, ein Fleck mit 307 063
  und 65 Kandidaten) waren das 264 von 482 Sekunden. Denselben Index liest
  `_connected_patches`, das je Splitstück gerufen wird: 320 statt 11 Sekunden.
  Ein kleiner Fleck (unter `SORTED_CORNERS_SHARE` der Dreiecke) fragt dabei
  sortiert und rechnet seinen Zusammenhang in eigener, aufsteigender
  Nummerierung — keine Maske und kein Graph über das ganze Netz je Aufruf;
  Gruppen und Folge sind dieselben.

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Bohrungen teilen ihre Durchgangsvorarbeit.** `detect_holes` hält
  `_ThroughBounds` nur für seinen aktuellen, unveränderlichen Körper. Die
  Dreiecksgrenzen entstehen erst bei der ersten exakt achsenparallelen Bohrung.
  Achse und Querbasis müssen identisch zu vorzeichenbehafteten Koordinatenachsen
  sein; eine nur annähernd parallele Richtung benutzt vollständig den bisherigen
  Weg. Die Vorauswahl verwendet dieselben Abschnitts- und Mündungsgrenzen,
  danach folgt die unveränderte Ring-/Dreiecksprüfung. Sie ändert keine Toleranz,
  Merkmalskennung oder historische Zuordnung und erzeugt keinen persistenten Cache.

- **Gewindegänge schreiten entlang der Achse fort.** Drei gleich dicke Fits
  zählen nur, wenn sie an einem Teil liegen (`face_components`), dieselbe
  Materialseite tragen und jeder weitere Abschnitt in den Lauf hineinläuft
  und mehr Neues bringt, als er mit ihm teilt (`_one_run`, RM-219). Eine
  geometrisch erkannte Wendel entfernt ihre über die Flächenmehrheit belegten
  Fits bereits vorher, unabhängig von deren Zahl. Verschachtelte Restflecken
  einer geänderten Bohrung ohne diesen Wendelbeleg bleiben Merkmale — ebenso
  die Wandstücke, die um Hundertstel versetzt beginnen (die Flaschentaschen
  R 49 des Flaschenhalters), Absätze, die sich nur berühren (der Zapfen
  R 4,76 · R 5,10 · R 4,76 am Besenhalter), und Bögen getrennter Teile.
  Gemessen am 25.09.2026 über 208 Dateien und die gedruckten Gewinde M3 bis
  M8: Ohne Wendelbeleg fand die Regel vorher kein belegtes Gewinde, verwarf
  aber in 13 Dateien echte Zylinder.

- **Die Bögen eines Prismas werden einzeln eingepasst** (`_arcs_of_a_prism`,
  vierte Runde in `_fitted`, RM-219). Ein extrudierter Umriss aus
  tangentialen Bögen und Geraden bleibt nach `CURVATURE_JUMP` ein Stück, auf
  das kein Zylinder passt. Steht jede Normale eines solchen Stücks quer zu
  einer Achse und ist sein Radius je Dreieck ruhig (`face_radii`, einmal je
  Körper; höchstens `PRISM_QUIET_SHARE` der Nähte springen), wird es an
  jedem Wechsel über `PRISM_ARC_JUMP` (5 %, in der Lücke zwischen dem
  Rauschen von 2,4 % und dem kleinsten gezeichneten Wechsel von 6,3 %) und an
  jedem Übergang zwischen Bogen und Gerade getrennt. Ein Stück zählt nur als
  gezeichneter Bogen (`_exactly_an_arc`): ein Radius über das ganze Stück und
  die Ecken in der Schweißtoleranz auf seinem Kreis. Alles davon ist
  gemessen: An Schriftzügen, Logos und Griffen springt der Radius an jeder
  dritten Naht, die Streben des Eiffelturms wandern um zwei bis drei Prozent
  je Streifen, und kurze Splinestücke passen um Mikrometer auf einen Kreis —
  genau genug für `fit_cylinder`, nicht für einen CAD-Bogen. Am Besenhalter
  zerfallen seine acht gerundeten Seiten in Bögen mit den Radien der
  Konstruktion (R 0,54 bis R 5,44; zusammen mit dem Fix der Gewinderegel
  93 statt 12 Verrundungen), und *In Flächen und Kanten umwandeln* fiel von
  64 auf 14 s; die Bögen der Buchstaben und ein Ellipsenbogen bleiben in
  dieser Runde gerundete Seiten.

- **Eine Wand mit Absatz sind zwei Formen** (`_pieces_at_a_seam`, fünfte
  Runde in `_fitted`, Durchsicht 0.5.1). Ein ganzer Fleck, auf den nichts
  passt und den weder Krümmung noch Prisma geteilt haben, wird an einer
  weichen Naht geteilt: Knick ab `SEAM_ANGLE`, von beiden Seiten mindestens
  `SEAM_RATIO`-mal so scharf wie jeder andere weiche Knick seines Dreiecks,
  ringsum gleich (`SEAM_SPREAD`). So wird die Haltelippe einer Magnettasche
  am Netz ein Kegel an der Bohrung, wie am exakten Körper; eine grob geteilte
  Rundung knickt an jeder Reihe gleich und bleibt ungeteilt.

*Früher unter „Grenzen“.*

- **Ein Kegel, dessen weites Ende an der Bohrung liegt, verengt die Mündung**
  (`narrowings_marked`, nach `_partial_bores_marked`; der exakte Kern fragt
  dieselbe Regel an seiner Tessellierung). Er trägt `narrowing` und die Weite,
  die er lässt (`opening`); Baum, Maßspalte und Steckbrief nennen ihn
  Verengung, nicht Senkung. Welche Handlungen dort fehlen, steht bei
  `actions` (`not_offered_at`, `cone_reason`).

*Früher unter „Grenzen“, HEAD-Fassung — die Regeln dazu stehen heute in `schichtanalyse.md`.*

- **Ein Umriss mit wanderndem Radius ist eine gerundete Seite**
  (`_wandering_outline`, zweite Runde in `_fitted`, RM-243). Die
  Nachtrennung zerlegt einen verrauschten Schriftzug, eine geschwungene
  Strebe oder einen frei geformten Griff in kurze Stücke, und jedes passt
  für sich auf einen Kreis. Gezählt werden die Kreise von Stücken mit
  Gewicht, die weder gezeichnet sind (`_exactly_an_arc`) noch von einem
  zweiten Stück desselben Flecks bestätigt werden (eines liegt auf dem Kreis
  des anderen); ein bestätigter Kreis hält die Folge an. Hat einer davon
  tangential einen engeren und einen weiteren Nachbarn — der Radius wechselt
  zweimal in dieselbe Richtung —, ist der Fleck ein Umriss, und die Funktion
  gibt seine bestätigten und gezeichneten Stücke zurück. Alle anderen
  eingepassten Stücke werden vorgemerkt (`outline` in `_fitted`) und fallen
  erst nach der Zusammenlegung, wenn sie ganz auf vorgemerkten Dreiecken
  liegen (`_off_the_outline`); was dort mit einem Stück von woanders zu einer
  Fläche verschmolz, bleibt. Der Rest wird zur gerundeten Seite
  (`detect_curved_faces`). Warum es so und nicht einfacher geht, steht in
  `.claude/rules/schichtanalyse.md`. Die Paare, die eine Bestätigung prüfen
  muss, wählt `_circle_pairs` vor — nach Radius sortiert, feldweise nach
  Seite, Achse und Versatz, mit einem Spielraum von einem Milliardstel —, in
  derselben Folge wie die Doppelschleife davor.

- **Eine Freiform bekommt keine Rundformen.** Ein Scan oder eine Figur
  zerfällt an den Krümmungssprüngen in Dutzende Flecken, und auf jeden passt
  eine Kugel; `is_a_freeform` erkennt das an der fertigen Liste, und
  `_shapes_on_a_freeform` lässt Kugel, Ring, Kegel und Verrundung weg —
  Bohrung, Zapfen und Fläche bleiben. `freeform_dropped` nennt der Auswertung
  die Zahl für den Befund `perceive.freeform`. Die Regel steht in
  `.claude/rules/schichtanalyse.md`.

- **Die Haut einer Freiform wird nicht in ihre Splitter zerlegt und
  eingepasst** (RM-193). Das Urteil fällt **einmal je Körper**, direkt nach
  `_split_patches_by_curvature` und bevor ein Splitstück gelesen ist: Welcher
  Anteil der Oberfläche liegt in Flecken, die in `FREEFORM_SPLINTERS` oder
  mehr Stücke unter `FREEFORM_PIECE_SHARE` zerfallen? Über
  `FREEFORM_SKIN_SHARE` ist der Körper eine Figur, ein Scan, ein erzeugtes
  Netz (`Fitted.freeform_skin`, `recognised_as_freeform`) — dann werden von
  diesen Flecken nur die Stücke von Gewicht eingepasst (der tangential
  eingeblendete Zapfen, die Verrundung, die Kugelecke), und der Befund
  `perceive.freeform` kommt auch mit null weggelassenen Formen. Darunter
  bleibt alles, wie es war. Über **alle** Flecken zusammen, weil die
  Zauberturm-Figuren ihre Haut in zwei Flecken tragen (44 und 32 Prozent),
  und **vor** der Schleife, damit die Reihenfolge der Einpassungen bleibt:
  Ein zurückgestellter Fleck füllt die Ringkandidaten in anderer Folge, und
  `_cylinder_beside_a_torus` fand danach andere Zylinder. Kapsel, Ellipsoid
  und Buchstabenbogen zerfallen nicht und bleiben, was sie waren. Drache aus
  TripoSG 37,7 → 4,2 s, Roberts Schüssel 7,3 → 2,9 s, Zauberturm-Figuren
  41 bis 132 s → 6 bis 13 s, Katze 26 → 6,5 s — unter Fremdlast, mit
  denselben Merkmalen. **Raue Tafeln machen einen Körper für sich zur Haut**
  (`_rough_facet_area`: große Facetten ohne Ebene, deren Knicke gemischt und
  stark sind, ab `FREEFORM_ROUGH_SHARE` der Oberfläche) — ein erzeugtes Netz
  trägt ebene Partien als verrauschte Tafel, die die Splitterregel nicht
  sieht; die Messung an beiden Seiten steht an der Konstanten und in
  `.claude/rules/schichtanalyse.md`.

- **Das Urteil zählt nur Flecken ohne Grundform, und es fällt in einer
  eigenen Runde.** `_fitted` läuft zweistufig: erst `classify` über alle
  Flecken, dann `_split_patches_by_curvature` über die gescheiterten, dann
  deren Stücke. Vorher fiel das Urteil beim ersten Fleck ohne Form und zählte
  jeden zerfallenden Fleck mit — auch einen, der längst eine Kugel ergeben
  hatte. Drei Bowlingkugeln aus `BowlingGame.3mf` verloren so ihre Kugel
  (Ø 17,5, Rückstand 0,0 über 65 024 Dreiecke, 662 Stücke nach Krümmung, 659
  Splitter), und an einer Kugel auf einem Sockel mit 0,02 mm Rauschen fielen
  Kugel und Zapfen. Ein Donut, ein Kegel, ein Ball: Jede Grundform, die ein
  ganzes Modell ist, zerfällt nach Krümmung wie eine Figur — nur der Fit
  trennt sie, also entscheidet er zuerst. Nebenbei hängt das Urteil damit an
  keiner Fleckreihenfolge mehr, und `worth_splitting` trennt enger nach:
  Drache 4,02 → 3,83 s, Katze 8,62 → 8,17 s.

### Der Merkmalscache hat zwei Schranken

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Der Merkmals-Cache hat zwei Schranken.** `CACHE_LIMIT` zählt
  Einträge, `CACHE_INDEX_LIMIT` ihr Gewicht in Flächenindizes —
  ein Eintrag für ein 400 000-Dreieck-Modell wiegt 3,9 MiB, und
  die Anzahl allein ließe fast ein Gigabyte zu. Ein einzelner Eintrag über
  der Gewichtsgrenze bleibt trotzdem: Ihn wegzuwerfen hieße, ihn beim
  nächsten Schritt sofort neu zu rechnen — der Cache wäre nicht begrenzt,
  sondern aus (bis zum 21.09.2026 tat die Verdrängung genau das, und ein
  Test schrieb es fest).

### Langloch und Durchblick

*Früher unter „Grenzen“.*

- **Eine Bohrung unter der vollen Umdrehung ist angeschnitten** (`partial`,
  `_partial_bores_marked`, P1.5) — nicht am Winkel erkannt, der am Netz
  je nach Facettierung 345 bis 354 Grad misst, sondern am Rand: zwei
  gerade Linien längs der Achse, die die ganze Tiefe durchlaufen. Ein
  Querloch durch die Wand hat solche Linien nicht. Der exakte Kern sagt
  dasselbe Wort aus dem Umfang der Fläche (`FULL_TURN` ist dieselbe Zahl
  wie `FULL_TURN_SPAN`, 300 Grad; ein von der Naht geteilter Mantel wird
  vorher zusammengeführt, `_seam_split_cylinders_joined`). Was der Anschnitt
  bedeutet, sagt `relations._cut_open_neighbours`: Grenzt der Mantel an
  eine andere Höhlung, sind beide **berührt** — keine Kette, kein eigener
  Körper (`actions.no_own_body`, `NO_OWN_BODY`), Objektbaum und Steckbrief
  sagen „angeschnitten". Zwei Bohrungen, die sich zu je 315 Grad
  überlappen, sind so an beiden Kernen zwei angeschnittene Bohrungen, nicht
  drei Verrundungen und nicht zwei ganze.

- **Ein Kegelstück gehört zum Langloch, zur Bohrung — oder es ist eine
  Kegelfläche** (`_partial_cones_folded`, `span_about`). Ein Kegel unter
  `FULL_TURN_SPAN` ist kein voller Kegel, wie ein Zylinder darunter kein
  Zapfen ist. Grenzt er an den Mantel eines Langlochs, ist er dessen
  Mündungsfase und geht darin auf — **und die geraden Flanken zwischen den
  Halbkegeln mit ihm** (`_mouth_flanks_folded`, P1.5): das Band der Fase
  wächst von den Kegelstücken über freie, schräg zur Achse stehende
  Nachbarn, also die letzten Kegelfacetten, die der Fit an der Naht ausließ,
  und die ebenen Flanken, die ihren Ebenenträger behalten. Der exakte Kern
  tut dasselbe (`brep.features._mouth_chamfers_folded`); ein Kegelstück
  zwischen zwei Langlöchern bleibt dort, wo es ist. Grenzt er an eine
  Bohrung, bleibt er die Senkung einer angeschnittenen Bohrung; sonst
  bleibt er als **Kegelfläche**
  im Baum (`partial`, Objektbaum und Steckbrief sagen das Wort), und jede
  Körperhandlung steht grau mit `actions.CONE_PIECE_HAS_NO_BODY` —
  `prepare_ops._movable_feature` sagt denselben Satz. Weglassen ging nicht:
  Die Blütenblätter eines Gewindeprüfers sind Kegel von 259 Grad, und ohne
  sie hielt die Freiformprobe vier Körper eines Minigolf-Satzes für Figuren.
  Der Anlass: 126 „Senkungen 90° Ø 5,80" an 33 Langlöchern eines
  Organizer-Rahmens, an denen jede Operation absagte (`_body_from_faces`
  findet an einem Teilkegel keinen ebenen Rand).

- **Und was sonst keinen eigenen Körper hat, steht grau, bevor die Operation
  es sagt** (`actions.no_own_body`): eine Bohrung oder Senkung, die einen
  fremden Rand berührt, ohne dass daraus eine Kette wird
  (`prepare_ops.NO_OWN_BODY`), eine, deren eigene Ränder keine Ringe ergeben
  (`CAVITY_TOPOLOGY_UNKNOWN`, der Grund reist als `reason` aus dem
  `CavityState` bis in die Zeile), und ein Kegel oder eine Kuppel, aus deren
  Flächen kein Körper entsteht — drei Randringe, ein Kegelstumpf mit
  Querbohrung (`prepare_ops.has_own_body`, `NO_BODY_FROM_FACES`). Dazu eine
  Bohrung, in deren Zylinder Material steht — die Innenwand eines Rades mit
  Speichen, ein Topf mit Zapfen (`prepare_ops.hole_is_clear`,
  `HOLE_IS_NOT_EMPTY`): An ihr steht jede Zeile grau, denn ihr Werkzeug wäre
  ein voller Zylinder — gefragt **vor** der Kette, denn `_tool_for` fragt es
  an jeder Bohrung, auch an einer mit Fase am Mund. Alle Sätze sind die der
  Operation; die Kette wird je `actions_for` einmal gefragt und speist auch
  die Sperre an *Zum Langloch ziehen*. Und `fillet_blocked` liest dieselbe
  Flächenmenge wie `edges._around`: die Ebenen frisch aus `detect_faces`,
  nicht die `face`-Einträge des Baums — ein Langloch verschluckt die, und an
  einer Freiform gibt es keine.

- **Die runden Wände werden zusammen gefragt** (`tangent_walls`): ein Gang
  über `face_adjacency` für alle Verrundungen eines Körpers, nicht einer je
  Wand (531 am Hemmungsrad); `blends_into_its_neighbours` bleibt der Weg für
  eine einzelne. `_partial_cones_folded` zählt die Nachbarn seiner Kegelstücke
  im selben Muster und gibt ein Stück dem Langloch, mit dem es die meisten
  Kanten teilt — **und bei Gleichstand keinem** (Regel 21): Eine Senkung Ø 12
  zwischen zwei Langlöchern Ø 6 bei y = ±4 teilt mit beiden acht Kanten und
  bleibt Kegelfläche, wie am exakten Kern; bis zum 21.09.2026 gewann der
  alphabetisch spätere Name. Zwei Winkel, zwei Namen:
  `UPRIGHT_TO_AXIS` misst eine Normale gegen die Achse, `TANGENT_TO_THE_ARC`
  gegen den Radius (`planes_beside`). Durch eine Bohrung sieht man hindurch,
  wenn Achse und zwei Ringe bei 0,3 und 0,6 des Radius frei sind
  (`THROUGH_RINGS`) — innerhalb der Sehnen des Mantels und innerhalb des
  Kerns eines groben Gewindes. Frei heißt: kein Dreieck im Abschnitt der
  Bohrung darüber, **und keine Fläche, die an den Mantel grenzt, in ganzer
  Länge** (`_faces_beside`, `_surface_owners`: ebene Facetten und glatte
  Rundflecken als die Flächen des Netzes) — die Frage des exakten Kerns
  (`brep.features._axis_covered`). Der Abschnitt allein sah vom Übergangskegel
  einer Aufweitung Ø 9 über Ø 5 nur das Band, das ihre Endebene berührt: an
  der Tessellierung des exakten Körpers ein Streifen bis 3,8 mm Radius, und
  der Ring bei 0,6 blieb frei (Kreuzbefund Paket A, 22.09.2026). Der
  gegenüberliegende Schenkel eines U-Profils grenzt nicht an den Mantel und
  zählt weiter nicht. `relations.boundary_rings` ist öffentlich, weil
  `geom` es braucht.

### Im Ausschnitt

*Früher unter „Grenzen“, HEAD-Fassung.*

- **Ein Hohlraum ohne Weg nach außen ist keine Bohrung.** `detect_voids` findet
  geschlossene Innenschalen über vier Tore — dichtes Netz, einheitlicher
  Umlaufsinn, mehr als eine Komponente, und die Schale liegt im Material der
  **festen** Komponenten. `_shells_inside_the_material` bestimmt die
  Schalenhierarchie ohne einen Manifold je Paar: Ein Gitterzertifikat über
  die Hüllquader der Dreiecke belegt, dass zwei Schalen sich nicht kreuzen
  (`_shells_do_not_cross`), und dann entscheidet ein achsenparalleler Strahl
  von einer Ecke des Kinds, ob es in der Elternschale liegt
  (`_point_inside_shell`; Kante, Ecke oder ein fast paralleles Dreieck
  schicken ihn in die nächste Richtung, und nach sechs gibt er auf). Nur ohne
  Zertifikat rechnet die private positive Hülle und die leere Differenz im
  Float64-Kern wie bisher, ausschließlich über dessen direkte Stufe — am
  Quader mit acht Kammern aus 434 176 Dreiecken 1,2 s je Erkennung, mit
  Zertifikat 0,12 s (21.09.2026). Scheitert die Differenz, verschwinden die
  Einschlüsse nicht still: `unreadable_void_shells` nennt der Auswertung die
  Schalenzahl für einen Befund (Regel 17).
  Die nächste positive Oberfläche beweist kein Enthaltensein: Sie kann zu
  einer Materialinsel gehören. Bounds verwerfen unmögliche Schalenpaare;
  Material und Luft müssen entlang ihrer Verschachtelung abwechseln.
  Inselvolumen wird von der umgebenden Luft abgezogen; die Inseloberfläche
  gehört zur vollständigen Auswahl. Eigene Luftkammern in Inseln bleiben
  getrennte Merkmale. Abbruch reicht vom globalen und lokalen Aufrufer bis
  zwischen die Schalen und die nativen Differenzen. Es wird keine
  verschobene oder neu vernetzte Ersatzform zur Erkennung verwendet.
  Bei lokaler Suche bestimmt der angeklickte Originalpunkt die Luftkammer.
  Ihre vollständige Grenze muss einschließlich getrennter Inseloberflächen
  innerhalb des Suchradius liegen; eine zweite Kammer im selben Radius
  wird dadurch nicht zur gleichen Auswahl.
  `voids_instead_of_phantom_bores` nimmt danach in beiden Kernen die Merkmale weg,
  deren Flächen mehrheitlich darauf liegen. An einem offenen Netz wird nichts
  behauptet: Dort ist eine solche Schale genauso gut eine Lücke, und Raten
  verbietet Regel 21.
  **Anfassen lässt er sich trotzdem** — `void` steht in `geom.MOVABLE_KINDS`,
  und Versetzen wie Entfernen sind gemessen. Was fehlt, ist nicht die
  Erreichbarkeit, sondern das Maß; die Regel dazu steht in
  `.claude/rules/schichtanalyse.md`.

### Rohrwände

*Früher im Kopf der Karte.*

Rohrwände berücksichtigen den gemessenen Querversatz von Höhlung und Mantel.
Beim Langloch zählt der weiter entfernte Endmittelpunkt einschließlich seiner
Richtung; Versatz und halber Weg werden nicht pauschal addiert. Einzelabfrage,
Steckbrief und kleinste Rohrwand teilen diesen Messwert.

### Verlorene, erzeugte oder geschlossene Merkmale

*Früher unter „Die Sache mit der Stabilität“.*

Ein verlorenes erkanntes oder erzeugtes Merkmal und eine bereits geschlossene
Fehlstelle haben im aktuellen Körper keine Fläche mehr, die eine
Merkmalskarte ehrlich färben könnte. `perceive.orphaned`,
`perceive.generated_lost`, `perceive.referenced_lost` und `perceive.mended`
führen deshalb nur zum
betroffenen Körper und erzeugenden Schritt; eine Karte bleibt aus. Andere
`perceive.*`-Befunde behalten ihre Merkmalskarte.

*Früher unter „Die Sache mit der Stabilität“, HEAD-Fassung.*

Ein Verlust **ohne Verweis** (`perceive.orphaned`, `perceive.mended`) steht
einmal je Körper und Schritt: bei mehreren im Mehrzahlsatz, die Zahl in
`values["count"]`, die Kennungen in `values["feature"]`. Ein Verlust **mit**
Verweis bleibt je Merkmal eine Warnung
(`referenced_lost`, `generated_lost`).
