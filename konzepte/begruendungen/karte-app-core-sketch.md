# Begründungen zu `app/core/sketch/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Einstiege
> und die einzuhaltenden Verträge verdichtet wurde. Die Karte steht dort;
> hier stehen die ausführlichen Beschreibungen, Messwerte und Anlässe ihres
> Tages — wörtlich, gegliedert nach den Überschriften der Karte. Die Absätze
> stammen aus der letzten gesicherten Fassung vor der Verdichtung (`main`);
> „Früher unter …“ nennt den Abschnitt, in dem ein Absatz dort stand.
>
> Die frühere Liste unter „Grenzen“ ist in der Karte auf vier Abschnitte
> verteilt: „Der Löser“, „Formen, Ecken und Kurven“, „Aus dem Körper“ und „Die
> Skizzen-Operationen“, alle vier unter „Stolperfallen“.

## Vorspann

2D-Geometrie, die durch einen Löser bestimmt wird statt durch gezogene Punkte
(§30.1). Die Grundlage für alles, was aus einem Umriss entsteht.

Der **grafische Editor** liegt in `app/ui/sketch_editor.py` und hat eine
eigene Regeldatei (`.claude/rules/zeichenflaeche.md`). Hier steht die Rechnung
darunter.

## Der Weg

```
shapes.py     Grundformen (Linie, Kreis, Bogen …)
     │
     ▼
solver.py     Zwangsbedingungen lösen  ──>  bestimmte Koordinaten
     │
     ▼
profile.py    geschlossene Umrisse finden, Hierarchie aus Außen und Löchern
     │
     ▼
ops.py        Extrudieren, Rotieren, Ausschneiden — die Skizzen-Operationen
```

`planes.py` beantwortet die Frage davor: **wo** die Skizze liegt — auf einer
Grundebene, auf einer Fläche des Modells oder auf einer abgeleiteten Ebene:
parallel versetzt, gekippt oder durch drei Punkte gelegt (§30.1). Die
abgeleiteten gehören **der Skizze** und stehen in keinem Objektbaum; sie sind
eine Zeichenkette im Parameter, deren Abstand ein Projektparameter sein darf.
`frame_for_plane` schweigt, wenn sie sich nicht auflösen lässt (eine Ansicht
ohne Parameter ist kein Fehlerfall), `frame_for_sketch` sagt warum.

## Die Karte

| Datei | Rolle |
|---|---|
| `solver.py` | Der 2D-Löser — und sein Zugmodus (`dragged`, `start`), begrenzt durch `DRAG_REACH_TRIES`/`DRAG_SLIDE_TRIES`; Rang über `_matrix_rank` (Einerzeilen abgeschält), Redundanz über `_losses` (eine Zerlegung); die eigenen Gleichungen der Elemente (`_element_equations`), die Kurvenbedingungen (`_curve_equation`, `CURVE_SLOTS`) und `closest_on_spline` |
| `profile.py` | Vom gelösten Element zum geschlossenen Umriss; `arc_sweep` ist die eine Antwort, wie weit ein Bogen läuft, `EllipseFrame`/`ellipse_turn` die für Ellipsen; `flat_curve` die Punktfolge der Ansicht |
| `shapes.py` | Die Grundformen und die zwei Lochbilder; `grid_centres` hält die gemeinsame mittige Rasterlage für Skizze und Feldschnitt |
| `planes.py` | Wo eine Skizze liegt; `frame_in_scene` löst eine Ebenenangabe gegen eine Szene mit ihren Projektparametern auf — der Weg für jeden Verbraucher außerhalb der Skizzen-Ops |
| `edit.py` | Trimmen (auch Ellipsen — so entsteht der Ellipsenbogen), Verlängern, Versetzen, Spiegeln — an einer Ecke Verrunden und Fase (`corner_at`, `fillet`, `chamfer`), die vier Formen aus zwei Klicks (`polygon_at`, `slot_between`, `hole_grid_between`, `bolt_circle_at` — die Lochbilder halten über Bedingungen zwischen den Mitten, nicht über Festpunkte), Projizieren (`project`, ein Ebenenschnitt — am exakten Körper exakt über `brep.section`: Kreise, Bögen und Strecken statt eines Sehnenzugs, fest wie am Netz über `_held_copy`) und die Flächenkontur (`face_outline`, der Rand der Fläche unter der Zeichnung); die Ellipse aus drei Klicks (`ellipse_from_clicks`), Splinepunkte einfügen und entfernen (`spline_point_added`, `spline_point_removed`), Löschen mit Umnummerieren (`removed`) und die Pläne der Kurvenbedingungen (`tangent_plan`, `curvature_plan`, `on_curve_plan`, `equal_axes_plan`, `taken_back`) |
| `ops.py` | Die Operationen der Kategorie „Skizze“; `cut_regions` teilt den bestehenden Taschenschnitt mit aufgelösten Feldern, einschließlich Ebene, Durchgang und Z-Bezug (`_cut_span`, auch für den Übergangsschnitt). Die drei Schnitte mit Werkzeug (`sketch_revolve_cut`, `sketch_sweep_cut`, `sketch_loft_cut`) bauen ihr Werkzeug über dieselben Helfer wie die Erzeuger (`_revolve_section`, `_swept`, `_loft_outlines`) und ziehen es über `_cut_with_tool` in beiden Kernen ab; `sketch_join` fügt den hochgezogenen Umriss an den Eingang an (exakt oder am Netz über die Rückfallkette) und teilt mit `sketch_extrude` das Schema `RaisedOutlineParams` |
| `serialize.py` | **Die ganze Skizze als ein Parameterwert** einer Operation |

## Warum `serialize.py` der Schlüssel ist

Eine Skizze wird mit hundert Mausbewegungen gezeichnet, und trotzdem ist sie
**ein** Schritt im Stapel. Das geht, weil der Editor in einen Parameterwert
schreibt und die Geometrie erst bei der Auswertung entsteht — Regel 2 erlaubt
genau das, solange das Ergebnis vollständig aus den Parametern folgt.

Das ist dasselbe Muster wie bei `geom/sculpt.py` und `geom/pose.py`. Wer es
bricht, bricht die Reproduzierbarkeit der Auswertung.

`sketch_parameter_references(strict=True)` reicht unlesbare Skizzen und
Maßausdrücke weiter, damit die Verwendungsabfrage ein beschädigtes Maß nicht
als unbenutzt ausweist. Ohne `strict` bleibt der Cachevertrag erhalten:
Die Operation meldet den Fehler bei ihrer Auswertung.

`resolve_sketch_values(text, parameters)` löst ausschließlich die Maßwerte
der Bedingungen in einer temporären Kopie auf. Damit kann ein Baustein ohne
eigenen Szenenkontext dieselbe Zeichnung bauen wie die Platzierungsvorschau.
Punkte, Ebene und Bedingungsarten bleiben unverändert; die Geometrie löst
weiterhin `solve_sketch`. Fehlende Projektmaße bleiben Ausdrucksfehler. Der
gespeicherte Originaltext und seine Cache-/Verwendungsabhängigkeiten bleiben
erhalten.

*Früher unter „Der Weg“.*

Die Merkmalsauskunft exakter Ergebnisse erhält denselben Abbruchauftrag wie
die erzeugende Operation. `_created` und `cut_regions` reichen `ctx.cancelled`
an `brep.features.features_of` weiter; auch die Erkennung rationaler Flächen
bleibt dadurch abbrechbar, bevor ein Ergebnis in Szene oder Cache erscheint.

## Der Löser

*Früher unter „Grenzen“.*

- **Der Löser rät nicht.** Ein unterbestimmtes System bleibt unterbestimmt;
  ein widersprüchliches meldet `SketchConflictError` mit Handlungsvorschlag.
  Gezeichnete Skizzen geben verbleibende Freiheitsgrade mit dem Ergebnis der
  Operation zurück. Vorgegebene Grundformen erzeugen diesen Hinweis nicht.

- **Bei gleich großem Rest nennt der Löser die später gesetzte Bedingung**
  (`_worst_constraints`, Gleichstand relativ 10⁻⁹): Eine Kette aus drei
  widersprüchlichen Bedingungen teilt den Fehler gleichmäßig, und die Meldung
  nannte sonst nie die, die eben dazukam.

- **Achtzehn Bedingungsarten, und „konzentrisch" ist keine davon.** Zwei
  Kreise mit gemeinsamer Mitte sind die Deckung ihrer Mittelpunkte; eine
  eigene Art wäre ein zweiter Weg, denselben Sachverhalt zu speichern, zu
  prüfen und zu migrieren. Das Wort steht trotzdem an einem Knopf der
  Oberfläche (`sketch_editor.ConstraintAction`) — eine Bedeutung, ein
  Datenmodell, zwei Namen für zwei Anlässe. Aus demselben Grund gibt es **ein**
  `equal` und kein `equal_radius`: Linienlänge und Radius sind beide der
  Abstand zweier Punkte, also dieselbe Gleichung.

- **Der Winkel rechnet als Sinus und nicht als Bogen** (`_angle_equation`).
  `sin(φ − θ)` ist bei θ = 0 die Gleichung von `parallel` und bei θ = 90° die
  von `perpendicular`; `atan2(…) − θ` hätte bei ±180° einen Sprung, den keine
  Ableitung kennt. Der Preis ist die Periode 180 — deshalb nimmt ein
  Winkelmaß nur Werte echt zwischen 0 und `MOST_ANGLE_DEGREES`. Die Zahl
  steht in **Grad** in der Datei und wird erst in der Gleichung Bogenmaß; §11
  gilt den Längen.

- **Eine neue Element- oder Bedingungsart erhöht `format_version`** (RM-188
  P6.6, Format 31). Der Aufbau der Projektdatei ändert sich dabei nicht, und
  jede ältere Datei liest sich unverändert — die Migration schreibt nichts um.
  Hier stand bis dahin das Gegenteil: Eine neue Datei in einer alten Version
  werde ohnehin am Versionsdeckel abgewiesen. Das gilt nur, wenn zwischen den
  beiden Versionen zufällig eine andere Formatänderung lag; sonst lädt das
  ältere Programm die Datei halb und hält mitten in der Auswertung mit „Diese
  Elementart gibt es nicht" an, als wäre die Skizze beschädigt. §16.2 sagt
  „neuer → freundlich ablehnen statt halb zu laden", und die Stufen 25→26,
  27→28 und 28→29 stehen aus genau diesem Grund. Die zwei Listen der Arten
  (`solver._CONSTRAINT_TARGETS`, `serialize._CONSTRAINT_KINDS`) hält
  `tests/test_sketch.py` deckungsgleich, die der Elementarten
  `tests/test_sketch_curves.py`.

- **Der Zug ist ein eigener Modus des Lösers** (`solve_sketch(..., dragged=,
  start=)`, 13.09.2026). Ohne ihn beginnt der Löser bei den gespeicherten
  Punkten und findet die *nächste* Lösung — beim Ziehen die falsche: Ein
  Rechteckpunkt, um zwanzig Millimeter gezogen, kam bei fünf an, weil die
  Deckung mit dem Nachbarn hälftig ausgeglichen wurde. Mit `dragged` stehen
  die gezogenen Punkte am Zeiger und alles andere folgt mit der kleinsten
  Bewegung ab `start`, dem zuletzt gelösten Stand. **Zwei Stufen**: erst
  werden die gezogenen Koordinaten aus dem System genommen (exakt — ein auf
  das Raster gefangener Punkt landet auf der Rasterzahl); lassen die
  Bedingungen den Ort nicht zu, rechnet die zweite Stufe sie als zähe
  Variablen mit (`DRAG_STIFFNESS`, ein Zwanzigstel wie in SolveSpace) — ein
  Punkt auf einer Waagerechten folgt seitlich, einer am festen Maß läuft auf
  seinem Kreis, ein `fixed` hält. Gemessen: 2 ms je Zugschritt am Rechteck;
  bei nichtlinearen Bedingungen (Radius, Senkrechte) driftet ein einzelner
  Sprung um zehn Millimeter im Nullraum um 2·10⁻⁴ mm, fünfzig Schritte à
  0,2 mm bleiben unter 10⁻⁸ — die Maus zieht in Schritten, und so prüft es
  `tests/test_sketch_edit.py`.

- **Der Zug ist begrenzt** (`DRAG_REACH_TRIES`, `DRAG_SLIDE_TRIES`). Die
  zweite Stufe beginnt am Stand der ersten; findet auch sie keine Lage, bleibt
  eine vorher widerspruchsfreie Zeichnung stehen. Ohne Grenze hielt ein Zug
  über die Reichweite einer bemaßten Kette das Fenster je Mausereignis
  Sekunden an. Kehren die gezogenen Punkte ganz zurück, bleibt sie ebenso
  stehen (RM-541): Was die erste Stufe auf der Suche nach dem unerreichbaren
  Zeiger an freien Punkten verschob, ist kein Ergebnis. Das biegsame Vieleck
  der Grundformen, an der Ecke neben der festen gezogen, stand sonst verbogen
  da, über `lsmr` um 0,26 mm, über `dogbox` um 10,7 mm an einer Ecke. Am
  Ausgang statt am Ende der ersten Stufe zu beginnen, half dort auch, ließ
  aber die Kette aus zwanzig Linien nicht mehr rutschen.

- **Feste Punkte kosten die Zerlegung nichts** (`_matrix_rank`). Eine Zeile
  mit genau einem Eintrag trägt eins zum Rang bei und nimmt ihre Spalte mit;
  so wird abgeschält, was `fixed` festhält, und was danach zur Einerzeile
  wird. Geschält wird **dünn** (`_solve` gibt die `csr_matrix` zurück), dicht
  wird nur der Rest. Deshalb zählt `fixed` auch nicht ins Budget der dichten
  Matrix (`MAX_JACOBIAN_BYTES`): Eine Kontur mit Tausenden fester Strecken
  bleibt lösbar. Die Redundanzsuche (`_losses`) macht im Fehlerfall die ganze
  Matrix dicht und prüft dafür dasselbe Budget.

- **Das Löserbudget zählt alle dichten Zeilen**, einschließlich der
  zusätzlichen Kreis-Eichzeilen bei ansonsten freien Skizzen.

- **Ein Bogen mit drei festen Punkten braucht seine Gleichung nicht.** Sie
  entfällt, wenn sie an den gespeicherten Punkten gilt — sonst wäre sie die
  siebte Zeile über sechs Koordinaten und der Löser meldete „legt fest, was
  schon festliegt". Gilt sie dort nicht, bleibt sie, und der Widerspruch wird
  gemeldet.

- **Je zusammenhängendem Teil, in Verschiebungen** (RM-541, 09.10.2026).
  `least_squares` mit `method="trf"` beginnt mit dem Vertrauensradius ‖x₀‖
  und misst `xtol` an ‖x‖. Mit Koordinaten als Unbekannten war das die
  Entfernung der Zeichnung vom Nullpunkt: Ein Winkel 45° kam unter macOS Intel
  als 135° an (Lauf 37495714708), am Windows-Stand verschob dieselbe Skizze
  tausend Millimeter daneben ihre Punkte um bis zu 292 mm, und mit `lsmr`
  endeten Läufe in einem Widerspruch, den es nicht gab. Der erste Ansatz —
  Verschiebungen ab null, scipy beginnt dann mit einem Millimeter — kostete
  die §31-Kette 16 statt 8 Auswertungen, ließ die zweite Zugstufe einer
  Kette nicht mehr rutschen und warf Linien im Maßstab 1:100 um mehr als das
  Fünffache ihrer Länge. Ein Radius aus der Streuung aller Punkte
  (‖x₀ − Schwerpunkt‖) hielt Budget und Zug, machte aber jeden anderen Teil
  der Zeichnung zum neuen Nullpunkt: Ein Winkelpaar neben einer bemaßten,
  gelösten Kette aus zwanzig Linien kippte in 11 von 60 Fällen, weil `lsmr`
  bei einer einzelnen gespannten Bedingung einen Zweierraum aus Rauschen
  bildet. Deshalb: Punkte, die eine Gleichung verbindet, sind ein Teil
  (`_parts`), jeder rechnet für sich (`_solve_part`), `lsmr` und der Zug mit
  der Streuung des Teils als `x_scale`, die dichte Rechnung höchstens mit
  `DENSE_FIRST_STEP` — an zwei Splines mit gleicher Krümmung setzte die
  Streuung den ersten Schritt so groß wie die Zeichnung, und sie trafen sich
  mit entgegengesetzter Tangente. Ein Teil ohne Spannung (alle Reste exakt
  null) bleibt ohne Lauf stehen; das hält Lochbilder schnell (20 × 20 Löcher
  wie vorher um 30 ms).

- **Im Zug rechnet ein kleiner Teil über `dogbox`** (RM-541). Im Zug steht
  der gezogene Punkt fest, und oft bleibt genau eine gespannte Gleichung
  übrig — zwei Linien mit *parallel*, *senkrecht*, *gleich lang* oder einem
  Winkel. Über `lsmr` war der Schritt dann Rauschen: Nach zehn Mausschritten
  standen die Linien tausend und hunderttausend Millimeter daneben 3,7 bis
  38 mm woanders (mit dem Löser von 0.5.3 bis 440 m), jeder Schritt nach
  allen 25 Auswertungen. Dichtes TRF hilft nicht: Hat ein Teil weniger
  Gleichungen als Unbekannte, rechnet scipy jeden Schritt auf den Rand des
  Vertrauensbereichs hoch, und ein Zugschritt am Rechteck brauchte alle 25
  statt 2 Auswertungen. `dogbox` nimmt den kürzesten Gauß-Newton-Schritt
  (`lstsq`), solange er in die Box aus der Streuung passt: höchstens
  1,5·10⁻¹⁰ mm Unterschied an jedem Ort, zwei bis fünf Auswertungen je
  Schritt, ein Zugschritt am Rechteck 1,9 statt 5,0 ms (unter Last, im
  Wechsel gemessen). Die Zähigkeit gezogener Punkte formt dort nur die Box:
  In gewichteten Veränderlichen fand die zweite Stufe an der gestreckten
  Kette aus fünf Linien in fünfzig Auswertungen keine Lage, so in vier.
  Beim Lösen bleibt dichtes TRF mit `DENSE_FIRST_STEP`; an ihm sind Korpus,
  gespeicherte Stände und echte Projekte gemessen (oben).

- **Ein Lauf ins Unendliche ist keine Lösung** (`FARTHEST_MOVE`). Eine Gerade
  und ein Bogen mit gleicher Krümmung erfüllen das nur mit unendlichem
  Radius; der Löser kroch dorthin, nach sechshundert Auswertungen lag der
  Rest bei 240 km Radius unter `_TOL`, und ob das als Widerspruch galt,
  entschied die letzte Stelle des Rangs. Was weiter als hundert Meter liefe,
  bleibt stehen, und die Meldung nennt die zwei Bedingungen am Start.

- **Gespeicherte Skizzen rechnen wie gespeichert** (`Sketch.solver`,
  Format 50). Bestimmte und schon gelöste Skizzen landen in beiden Fassungen
  am selben Ort (über 742 Eingaben aus den Skizzentests höchstens 3·10⁻¹³ mm),
  unterbestimmte nicht: Gespeichert sind die gezeichneten Punkte, und eine
  schief gezeichnete Platte wäre nach dem Update 30 mm³ größer oder kleiner.
  Die Migration 49 → 50 schreibt `"solver": 1` in jeden Skizzentext, der
  rechnet über `_solve_in_coordinates` wie 0.5.0 bis 0.5.3 — nicht wie der
  unveröffentlichte dichte Stand dazwischen, denn kein Kunde hat mit ihm
  gerechnet. Der Editor zeigt eine ältere Skizze, wie sie rechnet, und
  wechselt bei der ersten Änderung oder dem ersten Zug auf die heutige
  Fassung; erst wer übernimmt, ändert den Schritt. Die Fassung steht im
  Cache-Schlüssel jeder Skizze (`evaluate._with_nested_context`).

## Formen, Ecken und Kurven

*Früher unter „Grenzen“.*

- **Die zwei gezeichneten Formen halten sich selbst, ohne bemaßt zu sein**
  (`polygon_at`, `slot_between`). Das Vieleck hängt an einem **Hilfskreis**:
  alle Ecken auf ihm, alle Seiten gleich lang — zusammen genau so viele
  Gleichungen, wie ein geschlossener Zug an Formfreiheiten hat. Über Winkel
  an den Ecken ginge die Rechnung nicht auf, denn die letzten beiden bringt
  der Zug selbst mit. Gemessen: 3 Freiheitsgrade (Mitte und Radius), mit
  Festpunkt und bemaßtem Umkreis null. Das Langloch trägt vier
  `perpendicular` zwischen Flanke und Radiusstrahl und ein `equal` zwischen
  den beiden Radien — 5 Freiheitsgrade, beide Mitten und die Breite, und das
  in jeder Richtung gleich.

- **Eine Rundung trägt ihre Tangente als Senkrechte** (`edit.fillet`). Die
  Tangentenbedingung misst den Abstand der Mitte zur Geraden gegen den
  Radius; an einem Bogenende, das per Deckung *auf* der Linie liegt, ist das
  ein doppelter Nullpunkt — die Ableitung nach dem Ende ist null, die
  Jacobimatrix singulär, und die Rangprüfung meldete „legt fest, was schon
  festliegt" über eine bestimmte Skizze. `perpendicular` zwischen Linie und
  Radiusstrahl zum Berührpunkt sagt dasselbe mit einer Ableitung, die trägt.

- **Die gebrochene Ecke bleibt als Hilfspunkt** (`_held_by_the_virtual_corner`).
  Verrunden und Fase kürzen die Schenkel; was am Eckende hing — das Seitenmaß
  zuerst —, hängt danach am Hilfspunkt, der über zwei Gleichungen auf beiden
  verlängerten Schenkeln liegt: `horizontal`/`vertical` vom fernen Ende, wo
  der Schenkel so gehalten wird, sonst `parallel(fern, gekürzt, fern,
  Hilfspunkt)`. „Punkt auf Linie" braucht es dafür nicht. Die lineare Achse
  hat Vorrang, weil `parallel` über Einheitsvektoren rechnet und beim Ziehen
  einer unbemaßten Seite die freie Gegenseite um 1,9 µm je 10 mm schob
  (gemessen 23.09.2026; mit Achse unter 10⁻⁸). Die Fase misst vom Hilfspunkt
  aus (Maß plus `equal`) und ist damit bestimmt.

- **Die Ellipse trägt drei Punkte, der Ellipsenbogen fünf** (RM-188 P6.6a):
  Mitte, Ende der ersten, Ende der zweiten Achse, beim Bogen dazu Anfang und
  Ende, gegen den Uhrzeigersinn. Die zweite Achse steht senkrecht — die eigene
  Gleichung des Elements (`_ellipse_axes_equation`); welche Achse die längere
  ist, legt die Reihenfolge nicht fest. Die Bogenenden liegen über einen
  **winkelfreien radialen Rest** auf der Ellipse
  (`r = |d|·(1 − |det A| / |(d kreuz w, u kreuz d)|)`), für Kreise der genaue
  Abstand, sonst eine obere Schranke. Profil und Netzweg rechnen ohne
  Winkelfunktion: Parameter sind Einheitsvektoren, geteilt wird über
  normierte Summen, und der Sehnenfehler wird am Parametermittelpunkt exakt
  gemessen (affin invariant), höchstens `MAX_FACET_SAG` (RM-187). Der exakte
  Kern baut echte `Geom_Ellipse`-Kanten.

- **Nach einer Booleschen Operation ist die Ellipsenkante ein B-Spline**
  (OpenCASCADE schneidet Ebene und extrudierte Ellipse so). Die Flächenkontur
  holt die Ellipse trotzdem zurück (`brep.edit._section_ellipse`): Steht die
  Ebene senkrecht auf der Extrusion, ist der Schnitt die verschobene
  Grundellipse — geprüft gegen die Toleranz der Kante, sonst bleibt die
  Kette. Die Bogenenden rückt `_exact_outline` radial auf ihre Ellipse.

- **Kurvenbedingungen nennen eine Kurve über den ersten Punkt ihres Elements**
  (`CURVE_SLOTS`, RM-188 P6.6b): `on_curve` (Punkt, Kurve; eine Linie gilt
  als Gerade), `smooth` und `curvature` (Stelle an A, A, Stelle an B, B). Die
  Ableitungen von `smooth` und `curvature` kommen aus **Dualzahlen**
  (`_Dual`, Vorwärtsableitung) — dieselbe Rechnung wie das Residuum, keine
  zweite Herleitung; `curvature` misst den Unterschied der Krümmungsvektoren
  mal `L²/2` (Millimeter, `L` fest aus den gespeicherten Punkten). *Punkt auf
  Kurve* am Spline rechnet an der nächsten Kurvenstelle mit
  Hüllensatz-Ableitung. Ein Spline liest einen Übergang nur an einem seiner
  Punkte, *krümmungsstetig* nur an einem Ende.

- **Wer eine Kurve zerlegt, nimmt ihre Kurvenbedingungen mit**
  (`_curve_targets`): Trimmen einer Linie oder Ellipse, Splinepunkt einfügen
  oder entfernen — das Kurvenziel wandert zum Stück, das die Stelle trägt,
  und ein Splineanfang behält seine Nummer, wenn der erste Punkt fällt. Zwei
  Bögen aus einer getrimmten Ellipse hängen über Deckung von Mitte und
  Achsende und gleich lange zweite Achsen zusammen (eine dritte Deckung wäre
  redundant, gemessen).

- **Wie eine Bedingung zwischen Kurven entsteht, plant der Kern**
  (`tangent_plan` und Nachbarn, `CurvePlan`): Stoßen zwei Kurven aneinander,
  wird die Tangente *glatt* an der Stelle; Linie und Kreis oder Bogen ohne
  Stoß behalten die alte Abstandstangente, in jeder Reihenfolge der Auswahl;
  andere Paare ohne Stoß bekommen einen Hilfspunkt als Berührpunkt, den die
  Rücknahme wieder mitnimmt (`taken_back`). Die Oberfläche fragt nur nach dem
  Plan.

- **Eine Splinekurve für Vorschau und Körper.** `profile.spline_controls`
  liefert die Catmull-Rom-Bézierstücke; die 2D-Schnittprüfung und der
  B-Rep-Kern verwenden dieselben Kontrollpunkte. Jede kubische Teilkurve
  erhält eine eigene B-Rep-Kante, damit auch Flächenintegrale an den
  Stückgrenzen getrennt werden. Der Drehsinn folgt dem exakten Integral.

- **Ringe müssen getrennte Grenzen haben.** Kreisverschachtelung wird
  analytisch entschieden, andere exakte Umrisse über ihre B-Rep-Grenzen.
  Kreuzungen, Berührungen und doppelte Ringe halten mit Vorschlag an.

- **Eine Änderung der Profilbildung, die Ergebnisse ändert, hebt
  `profile.PROFILE_REVISION`** — sie steht in der Cache-Kennung aller sechs
  Verbraucher (Hochziehen, Tasche, Drehen, Führen, Überblenden, Lochfeld;
  `test_every_profile_consumer_carries_the_profile_revision`). Sonst käme ein
  falsches Ergebnis nach dem Fix weiter aus dem Speicher- oder Dateicache
  (B1 der P6.6-Arbeit: ein Loch außerhalb des Ursprungs ging verloren).

## Aus dem Körper

*Früher unter „Grenzen“.*

- **Die Flächenkontur ist der Rand und nicht der Schnitt** (`face_outline`,
  RM-188 P3.4). Genommen wird die Fläche, auf der die Zeichnung steht —
  direkt oder über parallele Versatzebenen (`standing_on_feature`); auf einer
  Grundebene, einer Dreipunktebene oder einer gegen die Fläche gekippten
  Ebene gibt es eine Absage mit Grund, keine Suche nach einer anderen Fläche.
  Am exakten Körper kommen die Ränder aus seinen Kurven
  (`brep.edit.face_loops`: Strecke, Kreis, Bogen, sonst nach `DEFLECTION`
  abgetastet), am Netz aus `perceive.relations.boundary_rings` und
  `ring_in_order`. Ein Netzring wird nur dann ein Kreis, wenn ein erkanntes
  Rundmerkmal ihn an Ecken **und** Sehnenmitten auf `MAX_FACET_SAG` belegt;
  sonst bleibt er, was das Netz sagt. Jeder Punkt trägt `fixed`, jedes
  Element ist Hilfsgeometrie, und es ist eine **Kopie**: Ändert sich der
  Körper, folgt sie nicht. Derselbe Rand zweimal übernommen kommt nicht
  doppelt (`_element_key`).

- **Was aus dem Körper kommt, kommt fest und einmal** (`_held_copy`):
  Flächenkontur und Projizieren gehen denselben Weg — jeder Punkt `fixed`,
  Punkte auf einer Geraden fallen weg (Schwelle: die Float32-Auflösung am Ort,
  `_straight_enough`), und was schon in der Zeichnung steht, kommt nicht noch
  einmal.

- **Flächenrahmen übernehmen die orientierte Merkmalsnormale.** Die Mitte
  des Hüllquaders entscheidet keine Innen-/Außenrichtung, insbesondere an
  Innenböden und konkaven Körpern. Eine blinde Tasche endet in beiden Kernen
  genau an ihrer eingegebenen Oberkante und Tiefe.

## Die Skizzen-Operationen

*Früher unter „Grenzen“.*

- **Eine gezeichnete Tasche verschiebt nicht** (`sketch_pocket`): X und Y
  setzen die Grundform; eine Zeichnung liegt schon in ihrer Ebene, auf einer
  Fläche mit der Flächenmitte als Ursprung. Zweimal verschoben schnitt sie auf
  jeder außermittigen Fläche ins Leere (Bedienabnahme Zeichnen, F2).

- **Die Zeichenfläche ist nie „Bis zur Fläche"** (`_is_the_drawing_face`): Von
  ihr aus gibt es kein Vorwärts; die Absage nennt das und bietet die Höhe als
  Zahl an.

- **Der Sweep läuft auch an einer gezeichneten Bahn entlang** (`sketch_sweep`,
  RM-147 E3). `along` entscheidet zwischen dem Bogen aus Radius und Winkel und
  der Zeichnung in `path_sketch`. Die Bahn kommt aus `profile.path_of` — eine
  **offene** Kette statt eines Rings, mit genau zwei freien Enden; ein Kreis
  ist keine. Sie liegt auf XZ oder YZ (`brep.profiles.PATH_PLANES`), und ihr
  Anfang wandert in den Ursprung: Sie beschreibt einen Verlauf, keinen Ort.
  Die Anfangstangente muss senkrecht zum XY-Querschnitt nach oben oder unten
  zeigen; ein schräger Beginn wird vor der Geometrieerzeugung zurückgewiesen.
  Die Umsetzungskennung der Operation hält ältere Sweep-Ergebnisse mit
  verlorenem Innenraum oder ungeprüftem Bahnbeginn aus dem Cache fern.

- **Der Übergang nimmt zwei unabhängige Zeichnungen** (`sketch_loft`, RM-147
  E2). `top` entscheidet, woher der obere Umriss kommt: aus dem unteren
  gerechnet (`top_scale`) oder als eigene Zeichnung (`top_sketch`). Geprüft
  wird vorher — dieselbe Ebene, gleich viele getrennte Umrisse; die gleiche
  Zahl der Löcher je Paar prüft `brep.profiles.loft` selbst. Verbunden wird in
  der Reihenfolge von `regions_of`, und der `doc`-Satz sagt das.

- **Drehen, Führen und Überblenden schneiden auch** (P6.5a–c). Je Werkzeug
  eine eigene Operation mit einem Eingang, direkt hinter ihrem Erzeuger in der
  Variantengruppe *Aus Skizze erzeugen …* — kein Umschalter am Erzeuger, weil
  das Register die Eingangszahl je Operation festschreibt (`grenzen.md`). Das
  Werkzeug entsteht exakt, wird mit einem geprüften Starrkörperzug an den
  Zielkörper gelegt und exakt (`brep.edit.boolean`) oder über die
  Rückfallkette gegen seine Tessellierung (`MAX_FACET_SAG`) abgezogen; die
  erreichte Stufe steht in `solver`, ein Werkzeug neben dem Körper gibt
  `boolean.without_effect` mit Vorschlag. Ein ungültiges exaktes Ergebnis
  (`brep.profiles.is_sound`) geht nicht hinaus: derselbe Schnitt rechnet am
  Netz weiter, mit `sketch.exact_cut_unsound`; die Umwandlung meldet die
  Auswertung vor der Übernahme. **Die Nut** legt den Querschnitt des
  Erzeugers um eine Achse aus Richtung und Punkt oder aus einer Bohrung bzw.
  einem Zapfen (`axis_feature`; der Punkt sagt dann nur die Höhe entlang der
  Achse). **Der Kanal** beginnt ohne Angabe an der Ober- oder Unterseite, je
  nach `heading`, und dreht um die Senkrechte (`turn`). Eine Bahn, die schon
  in diese Richtung beginnt, bleibt; sonst wird sie um die Querachse ihrer
  Bahnebene umgedreht (X bei Bogen und Vorderansicht, Y bei der Seitenansicht),
  damit sie zur gezeichneten Seite abbiegt. **Der Übergang** misst
  wie die Tasche von der Zeichenebene aus; durchgehend liegt der untere
  Umriss genau auf der Gegenseite, nicht darüber hinaus.

- **Eine Bahn wird geprüft, bevor der Kern sie baut** (`_check_path`, für
  Erzeuger und Schnitt): Kreuzung (`profile.crosses_itself`, dieselbe Prüfung
  wie für Umrisse) und Biegung enger als der Querschnitt zur Innenseite reicht
  (Bögen über `arc_through`, Splines an ihren Bézierstücken). Danach fragt
  `brep.profiles.intersects_itself` den fertigen Körper — `BRepCheck_Analyzer`
  hält einen Kreis Ø4 um einen Bogen R1 für gültig.

- **Ein Übergang zwischen zwei Vielecken fragt, wenn er drehen könnte**
  (`_paired_corners`, nur beim Schnitt): Die Ecken verbinden sich mit den
  nächsten, gemessen um die Mitte jedes Umrisses; Klickreihenfolge und
  Drehsinn der Zeichnung zählen nicht. Stehen zwei Zuordnungen gleich nah, geht
  die Frage über `ctx.ask` und die Antwort als `twist` in den Schritt. Der
  Erzeuger bleibt bei der Zuordnung von OpenCASCADE (`CheckCompatibility`),
  damit alte Projekte unverändert rechnen.

- **Ein Lochbild ist eine Grundform mit mehreren Umrissen** (`bolt_circle`,
  `hole_grid`, RM-147). Sie stehen in `shapes.PATTERN_CHOICES` und nicht in
  `SHAPE_CHOICES`: Nur *Grundform hochziehen* und *Tasche schneiden* rechnen
  mit mehreren Umrissen, Drehen, Ziehen und Übergang mit genau einem. Das
  Hauptmaß bleibt `length` — beim Lochkreis der Teilkreisdurchmesser, beim
  Raster der Abstand von Mitte zu Mitte —, dazu kommen `count`, `columns`,
  `rows` und `hole_diameter` über `depends_on`. Assoziativ ist daran nichts
  (Konzept P15, E11): Die Parametrik liegt eine Ebene höher, ein
  Projektparameter dreht den Teilkreis.

- **Kein Qt.** Der Editor ruft hier herein, nie umgekehrt.
