---
description: "Operationen an beiden Kernen — Register, Parameter, Rückfallkette, Befunde, Merkmalshandlungen an Bohrung, Kette und Langloch, Szene und Verlauf"
paths:
  - "app/core/geom/**/*.py"
  - "app/core/registry/**/*.py"
  - "app/core/scene/**/*.py"
  - "app/core/brep/**/*.py"
---

# Regeln für Operationen

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert (Regel 2, §30.1). Messwerte und Anlässe, gegliedert wie hier:
`konzepte/begruendungen/regel-operationen.md`.

## Vollständig oder gar nicht

Regel 4 mit der Checkliste in `AGENTS.md` (`/neue-op`);
`tests/test_registry_consistency.py` fängt unvollständige Ops und doppelte
Kürzel. `ctx.quality`: Entwurf zum Iterieren, Fein für Export und Prüfbericht;
**eine Entwurfsstufe nur über einem Budget und mit Befund** (`blend.draft_grid`).

## Was die Operation verlangt, steht im Register

- `requires_kind="brep"` nur bei fachlicher Notwendigkeit (Formschräge auf
  Fläche, Schalenkörper, STEP). Menü nennt den Sperrgrund am Netz; der Kern
  prüft ebenfalls. Keine UI-Zweitliste (Regel 19).
- `requires_body`: `open`, `parts`, `cavity` (`void` oder durch Aushöhlen).
  `labels.body_requirement` verwendet dieselbe Konstante wie die Op
  (`mesh_ops.ALREADY_CLOSED`, `prepare_ops.ONE_PIECE`, `lattice.NO_CAVITY`).
  `labels.body_facts` misst je Körper/Auswertung; über `BODY_FACTS_LIMIT`
  bleibt der Zustand unbekannt und sperrt nicht.
- Flächenabhängige Voraussetzungen fragt das Fenster an der Op:
  `lid.reason_against`, `MainWindow._lid_reason`, `LID_OPS`.
- Ops prüfen Merkmalsarten über ihren `applies_to`-Registereintrag und
  `perceive.actions.reason_against`, auch für Chat/CLI; keine Modulliste.
- Ebene verlangt `face`; reine Dreiecksarbeit (`paint_slot`, `clear_filament`)
  nimmt zusätzlich die eigene Art `curved_face`.

## Den Kern wählt der Körper, nicht der Kunde

`SceneObject.kind` wählt den Rechenweg (`geom/edge_ops.py`), kein `MENU_TWINS`-
Paar oder Haken. Das gilt auch für `drill_brep_hole`/`shell_exact`, Erzeuger am
Träger samt neuem Teil; Netz-Zwillinge der Grundkörper sind über das
Kontextmenü ihres Verlaufsschritts erreichbar.
Alles bleibt bearbeitbar (Robert). `caveat` erklärt Sehnenzug bis
`units.MAX_FACET_SAG` und wann der andere Kern nötig ist.

## Ein Parameter sagt, was er bewirkt

Titel, Vorgabe, Einheit, Grenzen und ein `doc`-Satz über die Wirkung. Vorn die
zwei, drei Werte, die man ändert, der Rest hinter „Weitere Einstellungen"
(§2.4).

### Eine Zahl, die nicht gesagt wurde (`optional`)

`ParamSpec.optional` erlaubt `None` nur, wo die Null selbst gültig ist
(Koordinaten), nie bei Länge, Durchmesser, Anzahl. Vier Stellen, jede nötig:
`params._coerce` lässt `None` zuerst durch, `json_schema` trägt `"null"`, der
Dialog setzt den leeren Zustand unter den Mindestwert (`setSpecialValueText`),
die Op fragt `is None` (`prepare_ops._named_place`). Eine Achse mit Zahl nennt
einen Ort; die übrigen behalten den gemessenen Wert, nicht null.

### Sammelparameter (`kind` in `sketch`, `strokes`, `armature`)

Fünf Eigenschaften, geprüft über das Register (`tests/test_gesture_ops.py`): im
Op-Hash, übersteht die Projektdatei, reiner Text, für den Agenten unsichtbar
(`json_schema()` lässt ihn aus, die Sitzung lehnt ihn ab), auf der Rückseite des
Dialogs. **Projektparameter, die darin gelesen werden, gehören in den
Cache-Schlüssel** (`resolve_params` sieht nur die oberste Ebene):
`nested_references()` (`scene/evaluate.py`) ordnet jedem `kind` seinen Sammler
zu, `_with_nested_context()` mischt ein; ein neuer Sammelparameter mit
Ausdrücken wird dort eingetragen; `strokes` fehlt mit Absicht.

### Eine Operation, die an ihren eigenen Eingängen vorbei liest, bringt das Gelesene in den Schlüssel

`_with_nested_context` mischt die Hashes aller Träger ein, die ein Parameter
benennt (`align_to_feature`-Ziel, `up_to`-Fläche `TARGET_FIELD`,
`feature:<id>`-Skizzenebene über `feature_ref_of_sketch`, auch durch
`standing_on_feature`), und bei `OperationSpec.reads_other_bodies` am Register
alle Objekte unter `#scene` (`orient_for_print`, `keep_on_bed`). Eine neue
Lesart aus `ctx.scene` kommt hierher. Den Rahmen einer Ebene fragt eine Op mit
den Projektparametern (`sketch.planes.frame_in_scene`), nie über
`frame_for_plane` ohne Werte.

**`keep_on_bed` holt vom Rand zurück, nicht aus einem Nachbarn** (Entscheidung
Robert): Zwei Körper am selben Ort sind eine Absicht; die Überschneidung melden
`check_collisions` und `check_bodies_in_one_place`, ohne zu bewegen.

### Ein Maß mit Verlauf braucht einen Anfang, den die Kante kennt

Offene Kante: linkes Ende, dann vorn, dann unten (`edges.starts_at_first`);
Ring: Punkt kleinster Lage (`LOOP_START`), Richtung `LOOP_WAY` — nie
Knotennummer oder erster Punkt; beide Kerne und jeder Verbraucher fragen
dieselben Funktionen. Ohne Form (Ring mit verschiedenen Endradien, verschiedene
Radien an einer Ecke) eine Absage mit Weg (Regel 21).

### Kantengruppen und gebogene Züge

Stehen in `kanten.md`.

### Eine angestellte Fläche darf nicht durch fremdes Material laufen

Liegt ein Werkzeug der Formschräge nicht ganz im Material (oder ganz davor),
sagen beide Kerne mit demselben Satz ab — keine still niedrigere Wand, kein von
`ShapeFix` formal geheilter Körper. Tangentiale Nachbarflächen gehen mit
(`draft.tangent_faces`).

## Boolesches geht durch die Rückfallkette

Die Stufen (§17.2) stehen im Docstring von `boolean.py`; die erreichte gehört
in `solver`, `jittered` mit Startwert.

- Stufe 4 steht im Prüfbericht, nie still; danach werden die Materialslots neu
  übertragen (§20). Im Entwurf endet die Kette nach Stufe 2.
- **Überlappende Teile je Szenenkörper vorab vereinen, mit Befund**
  (`boolean.parts_united`), auch am Werkzeug einer Differenz; interne Werkzeuge
  (`None`) ausnehmen; Mehrschaler durch `boolean()` mit `object_ids` und
  `ctx.cancelled`, auch über `prepare.drill` u. a.
- **Nicht Vereinbares rechnet und warnt** (`boolean.parts_not_united`), halt nur
  am Treffer einer selbstkreuzenden Schale (`CROSSING_SHELL_IN_THE_WAY`,
  Entscheidung Robert); keine Teilegrenze für die vollständige Vorfrage; wer
  Proben beurteilt, fängt `GeometryError`.
- **Was der Kern nicht geschnitten hat, kommt in der Darstellung des Eingangs
  und an seinem Ort zurück** (`attributes.in_source_layout`,
  `prepare_ops._without_scars`): Werkzeuge wandern in die Welt, nie Körper in
  ihren Rahmen (`prepare.drill` u. a.); sonst holt `edges._back_in_place`
  durchgereichte Ecken zurück.
- **„Koplanar robust" gilt nur für exakt koplanare float64-Geometrie.** Am
  float32-Netz einer STL bekommen abziehende Keile `BOOLEAN_OVERLAP` als
  Überstand (`edges.rounding_tool`), ebenso Werkzeugenden in Flächen mit Luft
  dahinter (`prepare._open_ends`); Stufe 2 entnadelt nur mit der
  Zusicherung des Imports (`boolean._welded_input`), die Ausgabe wird wie im
  Slicer verschweißt (`boolean._tidied`).

## Befunde statt Protokoll

- **Eine Operation, die nichts bewirkt hat, sagt das**, auch ohne Ausnahme
  (Regel 17); `boolean.without_effect` braucht nur `volume` (`HasVolume`).
- **Wer Boolesches rechnet, fragt danach — ohne Ausnahme**, an beiden Kernen;
  eine Op mit `boolean(...)` ist erst damit fertig.
- **Gemessen wird die Wirkung, nicht der Treffer**, auch ohne Boolesches
  (`sculpt.no_effect` gegen die Schichthöhe,
  `sculpt.strokes_missed`), mit dem Profil (`Profile.smallest_printable_volume`
  statt `EPS_GEOM`; ohne `profile` das Epsilon). Ein abtragender Baustein fragt
  die Tiefe (`parts.cuts_no_layer`); die Richtung wird nie aus der nächsten
  Fläche geraten (Regel 21).
- **Was ein späterer Schritt am selben Körper behoben hat, wird gestrichen,
  nicht herabgestuft** (`SETTLED_BY`). **Was der Endstand widerlegt, fällt auch
  so** (`evaluate._without_outdated`); neue Befunde über Dichtheit, Teilezahl
  oder Wicklung gehören in `CLOSED_STATE_CODES`, `ONE_PIECE_CODES` oder
  `WOUND_STATE_CODES`, was der Export nennt, in `CARRIED_TO_EXPORT`.
- **Die Reparatur löst Überschneidungen von sich aus auf** (Entscheidung Robert,
  `RepairParams.self_intersections`, alte Schritte nicht; `repair.self_crossing`).
- **Was aus einem Verhältnis entsteht, fragt die Auswertung am Endstand**, nicht
  die Op je Schritt (`check_placement`, `check_bodies_in_one_place`,
  `check_thin_walls`; Restwand `relations.thinnest_sleeve` wie `sleeve_at`,
  gegen `Profile.minimum_wall_thickness`, ohne Profil keine Aussage). Eine neue
  Verhältnisfrage gehört dorthin; Warnungen über eingetragene Werte (`hollow`)
  bleiben in der Op.

## Eine grobe Vorauswahl darf nicht das Urteil sein

Schlägt sie an, wird an der Sache nachgemessen; ohne Netz bleibt die Näherung,
zu streng, nie zu milde. **Wie oft schlägt sie im Normalfall an?** Schweigt sie,
ist das kein Freispruch: Mit `reach` fragt `over_the_edge_along` am Netz nach
(`_flank_opens_within`, Bedingungen im Docstring), nie über die ganze Hülle;
jeder Weg, der eine Bohrung setzt, gibt `reach` mit, an beiden Kernen.

### Wo die Vorprüfung selbst urteilt, beweist sie es gegen die Toleranzen der genauen

`intersections._separated` und `_touching_apart` verwerfen nur, was die genaue
Prüfung mit all ihren Toleranzen auch verwürfe: Abstand über allen, gemeinsame
Ecke nur zwischen parallelen Ebenen, dort Spiel unter der Treffschwelle, oder
freie Ecken über `margin`, nie fast parallel. **Jede Sicherung hat
einen konstruierten Fall, an dem ihr Fehlen einen Treffer kostet**
(`_pairs_at_the_tolerance`): Jede Bedingung einmal herausnehmen; ohne roten Fall
ihn an der Toleranz konstruieren, sonst ist sie überflüssig. Sie zählt im Budget
mit (`SEPARATION_COST`) und steigt früh aus.

## Eine Zahl beschreibt die Regel, nicht die Lage

**Wer aus einer Zahl auf einen Sachverhalt schließt, schreibt dazu, unter
welcher Bedingung der Schluss gilt — und prüft die Bedingung, nicht die Zahl.**

Ob ein Hohlraum einem Merkmal allein gehört, sagt
`perceive.relations.cavity_chain_state_at`; „nicht sicher einzeln" trägt seinen
Grund (`CavityState.reason`: `NO_OWN_BODY` oder `CAVITY_TOPOLOGY_UNKNOWN`, im
Gruppenweg `cavity_topology_unavailable`), und wer den Zustand liest, liest ihn
mit. Geteilt steht einmal (`relations.cavity_is_shared`). Was einen geteilten
Hohlraum nicht nehmen kann, sagt ab statt still ein Stück zu bearbeiten — nur
noch *Zum Langloch ziehen* (`NEEDS_A_PLAIN_BORE`, derselbe Satz im
Merkmalfenster); Versetzen, Drehen und Verdoppeln nehmen die ganze Kette mit
(Entscheidung Robert).

## Gekippt wird bis zur alten Randebene

Eine Kette kippt mit Werkzeug aus den Kennzahlen — Bohrung über die Mündung,
Senkung als größerer Kegel —, so weit die Neigung verlangt, ohne Neigung um die
Zugabe aus §39, nie bis zum Hüllquader (`_chain_tool`). Was über die Mündung
hinausreicht, endet an der alten Randebene (`_old_rim_caps`); Zugabe nur an
offenen Mündungen — außen immer (unter einem Deckel ohne), fern nur beim
Durchgang, der Sacklochboden kippt ohne mit. Beide Kerne fragen danach die
Nachbarwand. Senkung ohne Bohrung und Sackbohrung kippen genauso; ab dem halben
Öffnungswinkel sagt eine Senkung mit dem größten Winkel ab (`_sink_must_close`).

## Ein Loch versetzt man an beiden Kernen gleich

Alte Stelle schließen (`prepare_ops._closed_at`, `brep.edit.fill_bore`), an der
neuen schneiden — kein Unterschied zwischen den Kernen (Entscheidung Robert).

- **Der exakte Körper bleibt exakt**; vernetzt wird nur, wo der Kern die Form
  nicht hergibt (`evaluate.exact_became_mesh`). Mündung und Materialseite fragt
  ein Helfer für beide Kerne (`prepare.sink_placement`,
  `prepare.plug_placement`). „Nur das gewählte Merkmal" einer Kette geht erst
  ganz zu und wird frisch geschnitten. Verliert die Vereinigung des Stopfens
  Material, sagt `brep.edit.fill_bore` ab (`FILL_DID_NOT_HOLD`).
- **Starr:** gleiche Länge, bis zu den mitbewegten Randebenen, Kragen längs
  der Wand (`_continued_walls`); `no_longer_through` meldet, was stehen bleibt;
  Einrücken bis zur Facettengrenze ist Rauschen (`_seated`).
- **Eine Kette reist aus ihren Flächen**, mit Kragen `FEATURE_OVERLAP` an jeder
  Mündung ohne Materialseite davor (`_past_the_mouths`); Sacklochboden,
  Ringstufe und vergrabene Mündung bleiben bündig; ohne Flächenkörper füllt der
  Stopfen. Weitet sie sich an beiden Enden, wird je Seite gefragt
  (`relations.cavity_sides`), nie `chain[-1]` als einzige Mündung.
- **Die gerundete Mündungskante einer Zylindersenkung reist mit**
  (`mouth_blends=True`), außer bei *Bohrung ändern* und *Kippen*.
- **In einer gekrümmten Mündung nimmt nur der Stopfen die fortgesetzte Fläche
  als Deckel, ein bündig schneidendes Werkzeug nie** (`geom.mouth_cap` in
  Grundrechenarten; exakt `edit._continued_cap`, an derselben Nachbarschaft
  gemessen); der Klick ins Bild nimmt dasselbe Paar.
- **Eine exakte Differenz gilt erst mit dichtem Zwilling** (`CUT_OVERLAPS`,
  sonst `CUT_DID_NOT_HOLD`; Ketten, Bohrung, Langloch): OpenCASCADE scheitert
  lagenabhängig still. Exakte Kopien werden nach Lage und Maß zugeordnet, dann
  benannt; der äußere Zylinder einer Kette ist beim Wiederfinden entlang der
  Achse frei; unlesbar heißt `CHAIN_NOT_READABLE`.
- **Langloch und Lippentasche reisen ganz aus ihren Flächen** (gedreht, skaliert
  oder ohne zwei ebene Ränder aus Kennzahlen). Steht im Zylinder nur ein Rand —
  nicht „Merkmal ohne Dreiecke" —, ist das Werkzeug die Hülle der erklärten Maße
  minus Körper; Nabe oder Zapfen bleiben `HOLE_IS_NOT_EMPTY`. Die Lippe
  (`narrowing`) ändert sich über ihr eigenes Profil und wird nie gekippt
  (`perceive.actions.narrowing_reason`), solange die Erkennung keine gekippte
  Lippe liest; was sie nicht sieht, wird nicht nachgemessen.
- **Zwei Werkzeuge stoßen am Netz nie nur in einer Ebene aneinander** — das
  hintere reicht ins vordere; geprüft an Flächen dieser Ebene, nicht am Volumen.
- **Eine Senkung auf ihrer Bohrung ändert ihr Maß über dieselben Profile**
  (Absage an einer Stelle: `countersink_resize_refusal`).
- **Versetzen und Verdoppeln fragen die Nachbarwand**, beim Verdoppeln samt
  Vorlage; eine aufgerissene Wand ist nicht zusätzlich „über die Kante".
- **Narben des Schließens werden zusammengelegt** (`_without_scars`, nur unter
  `boolean._tidied`). **Eine Op gibt nur Merkmale ihres Ausgangsnetzes zurück**,
  auch am Bausteinwirt.
- **Gebohrt, nicht geändert; Tiefe vor dem Verschließen ablesen; an der neuen
  Mitte zuordnen; `moved_hole` statt Volumenvergleich.** Das Maß bleibt das
  gemessene; `bore.compensated` hängt der Versetzweg eigens an.
- **Ein Langloch ist parametrisch** (`PARAMETRIC_KINDS`), sein ganzer Umriss
  wird gefüllt; **null Grad ist eine Richtung** (`slot_angle`).
  `slot_hole` nutzt in Baugruppen die Merkmaltiefe, am Einzelkörper die Hülle.

## Wulst und Kehle schließen je Kern anders, ein Gewinde wird nicht bewegt

Wulst und Kehle tragen die Merkmalshandlungen mit dem vollen Ring aus den
Kennzahlen (`brep.edit.torus`); geschlossen wird exakt mit
`brep.edit.defeatured`, am Netz aus den eigenen Dreiecken. **Ein parametrisches
Werkzeug deckt sich nie mit einer vorhandenen Netzfläche.** Ein Ring als ganzer
Körper sagt `TORUS_IS_THE_BODY`; zerfällt er, meldet `feature_lost`.

Ein Gewinde wird geändert (`build.threaded`) oder verschlossen, je Kern mit
denselben Werkzeugen; die Enden fragen die Nachbarschaft (`_thread_span`: hinter
Material um `BOOLEAN_OVERLAP` früher, in der Luft außen hinaus, innen nicht).
Das neue wird an seiner Stelle belegt; innen nennt das Merkmal den Grund-Ø der
Gänge (`_tool_diameter`), am Netz misst es sich an seinen Ecken. Sperren darf
nur ein belegtes Linksgewinde (`types.thread_is_left_handed`); linksgängig,
mehrgängig, Steigung ohne Kern und Gewinde ohne Strecke sind Absagen mit
Vorschlag. Das neue Maß fragt seine Wand (`_thread_wall`): Durchbruch sagt ab,
eine dünner gewordene unter der Mindestwand meldet `thread.thin_wall`.

## Gemeldet wird, was am Ergebnis steht

- **Das gemessene Maß** (Kegelwinkel am Netz mit `FACETED_CONE_ANGLE`); trägt
  die Wand das gesetzte Maß, bleibt es; ein Durchgang, der nicht mehr durchgeht,
  bleibt dasselbe Merkmal.
- **Eine Mündung unter Material** (`{op}.mouth_covered`: ab der Hälfte des
  Rands, `COVERED_SHARE`, nie nach einer Kantenprobe; exakt zusätzlich die Säule
  im Werkzeug).
- **Eine Kopie, die es nicht gibt**, an beiden Kernen: wiedergefunden heißt neu
  und seitlich auf der gesetzten Achse bis zur Facettengrenze.
- **Eine Bohrung, in deren Zylinder Material steht, ist keine** (`hole_is_clear`
  über jede Oberfläche, `HOLE_IS_NOT_EMPTY`); ob man hindurchsieht, sagt die
  ganze Mündung, nicht die Achse.
- **Jeder Weg, der eine Bohrung neu setzt, fragt nach der Kante**
  (`prepare_ops._edge_findings`, am gefüllten Körper vor dem Schnitt, über die
  Schnittlänge; den Zerfall gegen den Körper davor, `_split_counted_from`):
  Mitte, beide Enden eines Langlochs (`prepare.slot_ends`), Austritte der Achse
  (erster Durchstoß) — einmal, an beiden Kernen; eine Senkung nur am weiten
  Ende, am Austritt nur einen halben Radius tief (`prepare.mouth_over_the_edge`),
  starr unter einer Haut nie. Eine ungeschlossen überdeckte alte Öffnung zählt
  als Material (`prepare.OpeningSpace`).

## Ein Winkel gilt dem Rahmen, den er bekommt

`drill_hole` nutzt Flächennormale, `slot_hole` Merkmalsachse. `slot_frame` baut
den Rahmen; `positive_axis` normiert. `seat_of` prüft beide Mündungen,
Vorzeichen sagen nichts.

`measured_frame` hält Altwinkel: Auswertung/Vorschau rechnen je Lauf mit aktueller
Achse um. Griff/Panel löschen ihn nur bei Richtungswechsel; Länge/Position
behalten Marker und Ausdruck.

## Die Werkzeugzugabe steht einmal, und ein Langloch bekommt sie nie

`prepare.FEATURE_OVERLAP`, nie eine zweite Konstante gleichen Werts. `slot_hole`
schließt auch die runde Bohrung vor dem ersten Zug (`closes_the_old`) und
schneidet ohne Zugabe (`overlap=0.0`).

## Ein Füllkörper hat die Form des Werkzeugs, nicht die des Hohlraums

Überall breiter als der Hohlraum, an der Körpergrenze gekappt (`_closed_at`);
wieder ausgeschnitten wird exakt das Merkmal, ohne Zugabe.

## Ein Vieleck aus einem gemessenen Durchmesser ist enger als er

`trimesh.creation.cylinder` ist eingeschrieben. Wiederhergestellt wird mit dem
gemessenen Konturmaß und dem Wandmantel (`_tool_for`, `_placing_tool`); nur der
Stopfen, der umschreiben muss, bekommt `units.inscribed_ratio`. Stolperfalle:
`FEATURE_OVERLAP` deckt den Vieleckverlust zu — ohne sie fehlt die Deckung.
## Toleranzen sind Durchmessermaße

`clearance` und `press` gelten im Durchmesser (`diameter + play`,
`hole_diameter - pin_diameter`); wer radial einzieht, nimmt die Hälfte. Keine
Konstante als Fertigungszugabe (Regel 7).

## Ein Langloch in neuer Richtung ist ein gedrehtes Langloch

`slot_hole` schließt die alte Öffnung und schneidet die neue, bei anderem Winkel
wie bei kürzerer Länge (`slot_hole.turned`). Auf genau die Breite gezogen wird
es wieder rund (Entscheidung Robert; `slot_hole.round_again`,
`slot_hole.already_round`); `prepare.is_round_length` entscheidet das für alle
Wege, auf die halbe Anzeigestufe, gegen eingetragene und geschnittene Breite,
dazwischen `NEITHER_ROUND_NOR_SLOT`. **Die kürzeste Länge ist gemessen:**
`prepare.shortest_slot` fragen Kern, Bohrdialog und Griff, gegen den gemessenen
Durchmesser — das Doppelte der Kippgrenze der Erkennung, mindestens 0,3 mm.

## Ein Langloch trägt keine Aufweitung, und seine Länge ist nicht sein Weg

Kein Langloch mit Senkung (Entscheidung Robert; Regel 21), auf drei Ebenen:
Dialog (`depends_on=("slotted", (False,))`), `prepare_ops.bore_shape` nullt die
beiden Maße, `prepare.slot_travel` weist sie ab; `transition_angle` bleibt. Ein
Haken ohne Länge ist eine Absage; Vorgabelänge ist der doppelte Durchmesser.
Die Materialtoleranz weitet überall, auf dem Radius:
`Mittellinie = Länge − nominaler Durchmesser`, der Verschiebeweg bleibt.

## Ein Langloch ist an beiden Kernen ein Merkmal und ein Hohlraum

Erkannt topologisch (`perceive.slots`,
`brep.features._slots_instead_of_half_bores`): zwei gleiche, parallele, ins Loch
gewölbte Bögen, die sich genau zwei ebene Nachbarn teilen, die an beide grenzen;
der Boden eines Sacklanglochs gehört nicht dazu. **Der Mantel ist geschlossen**:
Setzt eine weitere Wand ihn längs der Achse fort, ist es keines
(`brep.features._continues_the_mantle`, am Netz `_connected_shell`). Offene
Ausschnitte bleiben Langlöcher (Entscheidung Robert); ihr Füllkörper endet an
der Außenwand, verlorene Form meldet `slot_hole.feature_lost`.

`types.is_a_cavity` führt `slot`. Drehen schließt mit der alten und setzt mit
der neuen Richtung; *Bohrung ändern* ändert die Breite, die Länge folgt aus dem
Weg, gefüllt wird immer, ohne Zugabe; `resize_feature` gilt Materie. Die Wand
zählt an der dünnsten Stelle (`Sleeve.bore_travel`, der Weg der Höhlung); nicht
positiv heißt offene Flanke.

- **Eine Op sucht ihr eigenes Loch streng** (`prepare_ops._sits_at`: an der
  genannten Mitte auf `match_tolerance`, mit der eingetragenen Länge; Durchgänge
  dürfen entlang der Achse wandern) — nie per `perceive.matching.match` (acht
  Prozent der Diagonale), nie per `any(kind == "slot")`.
- **Die Auswertung prüft erklärte Merkmale gegen ihre Erklärung**
  (`perceive.matching.near_its_declaration`).

## Beide Kerne sagen dasselbe, und zwar aus der Nachbarschaft

Dasselbe heißt Art, Maße, Herkunft, Träger, Rolle und Handlung; Anzahl oder
Volumen beweisen keine Parität.

- Eine kleine Ebene ist Fläche, wenn ihre Ränder es belegen (`MIN_FACE_AREA`,
  darunter `_facets_standing_apart`); wer die Schranke anfasst, hält vier
  Gegenrichtungen (Kugel, Mantelstreifen, T-Stöße, Achteck). Unter
  `MIN_SURFACE_WIDTH` bleibt es Streifen.
- Die Mündungsfase eines Langlochs gehört zu ihm; ein Kegelstück zwischen zwei
  Langlöchern bleibt unentschieden, nie dem alphabetisch ersten. Ob eine exakte
  Freiformfläche ein Kegelstück ist, sagt die Netzeinpassung
  (`partial_cone_patch`), keine zweite Schwelle.
- Unter `FULL_TURN_SPAN` ist eine Bohrung angeschnitten (`partial`), die
  Schwelle steht einmal; bearbeitbar ist sie nach ihrer Nachbarschaft, nicht
  nach dem Winkel, und der Steckbrief sagt es mit den Sätzen des Panels.
- Gleiche Form sagt der Abstand zur Fläche (`_same_surface_patch`), nie die
  Vernetzung. Ein strittiges Dreieck gehört dem innersten Merkmal oder keinem
  (`CONTESTED`), nie nach der Reihenfolge der Erkennung.
- Ein Zylinder, der quer zu seiner Achse nicht in den Körper passt, ist an
  beiden Kernen keine Rundform, sondern Oberfläche
  (`perceive.features.cylinder_fits_in_the_body`); ob eine Rundung eine Kante
  ersetzt (`replaces_an_edge`), fragen Panel und Bearbeitung, nicht der Name.
- Eine Kugel an Rundungen ihres Radius (`perceive.features.rounds_the_corner`)
  heißt an beiden Kernen Eckverrundung, ohne Achse.
- `native` heißt belegt: am offenen Langloch Durchmesser, Achse, Bogenmitte,
  Richtung, nie Mündung und Weg.

## Ein Muster ist die Quelle, bewegt — und es bleibt ein Körper

`pattern_feature` wiederholt Merkmale, `pattern` kopiert Körper — nie
versehentlich den ganzen. Jede Instanz ist das Werkzeug der Quelle, bewegt
(`transformed_features`), nie eine zweite Beschreibung; eine neue Art bringt ihr
Werkzeug an der Quelle und ein exaktes Gegenstück mit. Ein Platz, der nicht
passt (Überschneidung, kein Material), entsteht nicht und wird mit Nummer und
Ausweg genannt (Regel 17). Die Quelle bleibt maßgebend; ein Merkmal ohne belegte
Flächen ist keine (`not_evidenced`).

## Aushöhlen: eine Öffnung ist eine fehlende Fläche, eine Entlüftung ein Loch

`openings` nennt fehlende Flächen, `vents` bohrt in einen sonst geschlossenen
Hohlraum; `open_at` bleibt für gespeicherte Schritte, mit `openings` eine
Absage; Resin erweitert `vents`. Ein offener Hohlraum bekommt keine Entlüftung.
Exakt (`shell_exact` bei offener Oberseite ohne Entlüftung, sonst Netzweg mit
Befund; `MakeThickSolidByJoin`) zählt nur ein gültiger, geschlossener und
veränderter Körper; ohne Innenwand fragt das Raster nach Platz —
`hollow.too_thin` oder `exact_fallback` (fragen über `ctx.ask`, Dreiecksmodell
mit Befund, oder lassen). Nie still der Netzweg.

## Menütiefe: gefaltet wird hinten, nicht beim Größten

`surfaces.folded_groups` faltet die hinterste Gruppe aus `MENU_GROUPS`, die
allein genügt, erst sonst die größte; `keep` hält die häufige Geste oben
(Entscheidung Robert), ohne Qt. Wer die Tiefe ändert, misst neu und sucht die
Menüwege in den Texten (`menu_path`).

## Auto Split: die Folge, die Spiegelebene, der Rand

Die ganze Folge entscheidet (`autosplit._plan_step`): alles passt, dann weniger
Stücke, weniger Klebestellen (eine Lücke kostet nichts), Nahtbewertung; das
Stützvolumen nur beim letzten Schnitt. Begrenzt über `PLAN_BUDGET`, nie über die
Uhr (§11.3); danach gilt die Naht der Suche, fertig wird die Teilung immer. Die
Spiegelebene gewinnt nur, was sie nicht verschlechtert (`symmetry.mirror_plane`:
Konturzahl, keine Einschnürung, Stützvolumen, gleiche Stiftzugabe). Die
Stiftzugabe gehört der Hälfte mit Stiften (`_child_reserves`), eine Lücke ist
die beste Naht (`Candidate.gap`), der Rand ist `split.bed_margin`. Stiftnummern
vergibt der Plan (`first_pin`), ein gleichnamiges Merkmal weicht aus
(`_clear_of`).

## Szene: Platzierung, Kennungen, Cache, Projektdatei

- **Platzieren verändert kein Dokument:** `prepare_surface()` rechnet Fläche und
  Randtopologie einmal; alle Punktabfragen (`at_point()`,
  `point_with_distances()`, `point_with_centre()`) teilen seine Prüfung samt
  Aussparungen; lineare Maße nur zu zwei unabhängigen geraden Kanten, nie zu
  Diagonalen oder Kreisfacetten, die zweite quer (`CROSSING_STEP`), gekrümmt
  nur Punkt und Normale; Mittelpunkt-Offsets von der Bohrungsmitte entlang U/V.
- **Ohne Tiefe und Achse keine Mitte** — die Mündung wandert nie als Mitte
  weiter (Regel 21); das Vorzeichen kommt aus der gezielten Fläche.
- **Wo etwas sitzt, wird nicht neu gezielt:** `seat_of()` sucht die Ebene der
  Mündung, ohne eigene Mitte und Aussparungskanten als Bezug, eine gefaste
  Mündung bis `mouth_reach` dahinter; die Fasenkorrektur gilt nur der eigenen
  Mündungsfläche (`mouth_on`), gemessen an der Mündung, nicht am Ziel.
- **Sichtstrahlen prüft das Originalnetz** (`original_surface_hit()`); Kappen
  und die positive Seite einer Schnittebene sind kein Ziel. **Vorschau und
  Operation teilen das Werkzeug** (`prepare_tool()`, `PlacementTool`: Winkel,
  Einsenkung und Spiegelung stecken darin); `frame_of()` nur am Anzeigeaktor.

- **Ein Verweis folgt seinem Körper durch den Stapel** (`orphans.lineage`); ein
  Operationsverweis (`kind="feature"`) bleibt bei `inputs[0]`. Vergebene
  Kennungen bleiben reserviert (`reserved_feature_ids`).
- **Wer einen exakten Körper neu baut, belegt die Bezüge, die danach noch jemand
  braucht — oder die Kette hält an.** Beleg ist Durchreichen, eindeutige
  Zuordnung auf denselben Namen oder ein unberührtes Merkmal
  (`_unchanged_continuations`), oder ein geometrisch nachgewiesener Übergang
  (`OpResult.feature_continuations`) — nie aus Namen, `created_by` oder
  `provenance` geraten, und `touches_features` ist kein Erhaltungsflag. Ein Halt
  ist atomar und nennt den Verbraucher (`NativeReferenceLost`); ohne Beleg wählt
  der Kunde am neuen Körper (`native-group:`, erweitert über `match_records`,
  kein zweiter Speicher); „Nicht weiterführen" wird nicht gespeichert.
- **Ein Kantenfeld wird vor dem Cache gebunden** (`ctx.bound_edges`): nie einen
  Schlüssel zweimal auflösen, bei Kollision nie „alle" oder den ersten; wer am
  Netz rechnet, deklariert `edges_on_mesh=True`. Kein Token, Index oder Handle
  in die Projektdatei.
- **Beim Umbau folgt ein Verweis seinem Merkmal, nicht seinem Namen**
  (`revision.verdict`, Lage in reinem Python); mehrdeutig heißt fragen oder
  absagen.

- Geometrische Auskünfte sind versioniert; ein mitgeführter exakter Innenraum
  zählt zu Budget und Identität. Eine festgehaltene Antwort legt ihr Ergebnis
  unter beiden Schlüsseln ab (`_key_after_answers`); den Schlüssel baut nur
  `resolve_params`.
- **Bewegte und fein geteilte Kopien werden nicht neu untersucht:** Wer nur
  bewegt, nimmt `apply` (Vermerk `note_movement`), wer nur teilt, meldet die
  Herkunft (`note_refinement`); übertragen wird unter Beleg, nie auf Zusage. Ein
  einzeln bewegter Körper meldet seine Matrix in `OpResult.transform`; bei
  mehreren Körpern reist sie je Netz über `note_movement`. Alle Verbraucher
  teilen den einmal gemessenen `moved_twin`-Beleg für Netzpaar und Matrix.
- **Die Live-Vorschau erkennt nur, was jemand braucht**
  (`detect_features=False`); ihre Szene ist nie Dokumentstand, Merkmale liest
  der Agent über den genauen Weg.
- **Erkannt wird bis 1,5 Millionen Dreiecke je Körper, nach Bestätigung bis fünf
  Millionen** (§21.1, `FEATURE_LIMIT_TRIANGLES`); über `FEATURE_LIMIT_COUNT`
  bleibt, was schon da war, dann die größte Oberfläche, nie eine Hälfte ohne
  Zuordnung; reduziert wird dafür nie, angehoben nur nach Messung an echten
  Netzen.

- **Objektzahländerung hält an** (`kern.md`); wer zerlegen will, schlägt es vor,
  und das Fenster setzt die Zerlegung davor (`History.split_and_retry`), nur
  wenn jedes Teil für sich passt. Reparieren, Verringern und Verfeinern setzen
  ebenso einen Schritt davor und planen den Suffix atomar neu
  (`repair_targets()` ohne Ops des exakten Kerns), mit nachgezählter Zahl
  (`DECIMATE_AND_RETRY`) oder durchgespielter Länge (`REMESH_AND_RETRY`), nie
  geschätzt.
- **Wer die Dreieckszahl vorab zählt, deklariert es** (`expected_triangles`,
  dieselbe Prüfung in Op und Vorschau), **wer nur das Netz ändert, auch**
  (`retriangulates`) — beides nur bei einem Körper hinein und heraus.
- **Einfügen und Verschieben planen genauso neu**, gefragt am Zustand an der
  Stelle; Vorwärtsbezug, Kreis oder verlorenes Merkmal werden abgesagt. **Ein
  ausgeschalteter Schritt erzeugt nichts, und nichts tritt an seine Stelle**;
  wer ihn braucht, ruht mit, seine Passungen auch.

- **Slots reisen nur mit, wenn die Operation sie mitnimmt:**
  `MeshData.replacing` behält die Slotliste nur bei gleicher Dreieckszahl, sonst
  gibt es keine (der Export ergänzt stumm „Slot 0"). `Trimesh.split` und
  `submesh` kennen die Liste nicht: Wer Dreiecke auswählt, schneidet sie selbst
  (`prepare_ops._loose_parts`).
