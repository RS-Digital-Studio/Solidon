# Begründungen zu `.claude/rules/operationen.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Die Absätze stehen wörtlich, wie sie in der Regel standen, geordnet unter die
Überschriften der verdichteten Fassung. Wo die Regel einen Abschnitt neu
geschnitten hat, stehen hier die Absätze aller alten Abschnitte, aus denen er
entstand. Der Abschnitt „Szene" war in der Regel eine Liste ohne
Unterüberschriften; hier gliedern ihn die Leitsätze der Regel.

**Warum `app/core/brep/**` im Geltungsbereich der Regel steht** (Kommentar im
Frontmatter, wörtlich): „Und der exakte Kern, seit dieselbe Operation an beiden
Kernen rechnet: Langloch, Versetzen, Verrunden und Fase stehen unten mit ihrem
brep-Zweig, und wer nur dort arbeitet, bekam die Regel nicht zu sehen."

## Vollständig oder gar nicht

Keine Op ohne Registereintrag, Parameterschema, Geometrietest und übersetzte
Texte. Die acht Schritte stehen als Checkliste in `AGENTS.md`; `/neue-op`
führt sie durch. Der Registereintrag braucht `name`, `title`, `category`,
`params`, `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`,
`doc`, optional `shortcut`.

`tests/test_registry_consistency.py` parametrisiert über das Register: eine
unvollständige Op fällt dort auf, ein doppeltes Kürzel auch.

`ctx.quality` kennt Entwurf und Fein. Entwurf ist das, womit iteriert wird und
worin der Agent arbeitet; Fein gilt beim Export und im finalen Prüfbericht.
Eine Op, die beide gleich behandelt, sollte das bewusst tun.

**Wer Eingänge unter ihrer Kennung zurückgibt, sagt, ob er sie unverändert
lässt oder einen mit einem anderen formt** (Review zu `bbd41ff2d`, F1 und U2).
`history.discarded` entscheidet daran, welche Schritte am Endstand nichts mehr
hinterlassen; der Prüfbericht streicht ihre Befunde, der Verlauf faltet sie
unter die Löschung. *Stift für Bohrung* reichte den Träger unverändert durch und
war nicht markiert — nach dem Entfernen des Stifts stand im Kundenfall
S-20261006-2a0261 weiter „Der Stift … steht noch in der Bohrung“. Die
Gegenrichtung zeigte die Sonde zum Review: Ein Schritt über Platte und Stift
(*Auf dem Bett anordnen*, beide verschieben, *Überschneidungen prüfen*)
erklärte alle seine Eingänge für lebend und holte den entfernten Stift zurück.
Seitdem reicht ein solcher Schritt jeden Körper für sich weiter; nur wer einen
mit einem anderen formt, trägt `shapes_with_other_inputs` (*Gegenform
einlassen*: die Tasche trägt die Form des entfernten Teils). Lage zählt dabei
nicht als Form. Beide Felder sind Entscheidungen, keine Vorgaben:
`tests/test_history.py` verlangt sie von jeder Operation dieser Bauart und
belegt „jeder für sich“ an einem Lauf mit zwei Körpern.

Mit diesem Satz kamen drei Verweise aus der Regel heraus, die wortgleich in den
Karten stehen: `tests/test_registry_consistency.py` (Registerkarte,
`tests/CLAUDE.md`), `tests/test_gesture_ops.py` (`tests/CLAUDE.md`) und „vorn
die zwei, drei Werte“ (`AGENTS.md`, Checkliste neue Operation, Punkt 2).

## Was die Operation verlangt, steht im Register

**Was die Operation von ihrer Eingabe verlangt, steht im Register.** Eine Op
des exakten Kerns trägt `requires_kind="brep"`; das Menü graut sie bei einem
Netz aus und schreibt den Grund in den Tooltip, statt sie anzubieten und nach
dem ausgefüllten Dialog abzulehnen (Regel 19). Der gute Satz im Kern bleibt —
er ist die zweite Hürde, nicht die erste. Eine Aufzählung in der Oberfläche
wäre beim nächsten Zuwachs des exakten Kerns unvollständig.

**Und was der Körper mitbringen muss, steht daneben: `requires_body`.**
Nicht die Bauart, sondern der Zustand — `"open"` (nicht wasserdicht),
`"parts"` (mehr als ein Stück), `"cavity"` (ein Hohlraum, als `void` erkannt
oder von *Aushöhlen* eingetragen). Drei Operationen tragen es: *Offene Fläche
schließen*, *In Einzelteile aufteilen*, *Gitter füllen*. Gemessen am
13.09.2026 über alle Dialoge: Ohne die Angabe öffneten sie an einem sauberen
Quader einen Dialog, dessen Vorschau nur „Keine Vorschau: …" sagen konnte.
`labels.body_requirement` liest die Angabe und sagt am Eintrag **denselben
Satz**, den die Operation beim Rechnen wirft — die Sätze stehen deshalb als
Konstanten in ihren Modulen (`mesh_ops.ALREADY_CLOSED`, `prepare_ops.ONE_PIECE`,
`lattice.NO_CAVITY`) und nicht zweimal. Was der Körper hat, misst
`labels.body_facts` einmal je Körper und Auswertung; über
`BODY_FACTS_LIMIT` Dreiecken bleibt der Zustand unbekannt, und unbekannt
sperrt nie. `test_the_register_says_what_a_body_must_bring` hält die drei fest.

**Und wo der Zustand an der Fläche hängt, fragt das Fenster die Operation
selbst.** Ein Deckel braucht eine Öffnung nach oben — das ist keine
Körpertatsache, sondern eine der gewählten Fläche, und die ist bekannt, wenn
die Karte den Knopf zeigt. `lid.reason_against(source, name)` gibt den Satz
zurück, den `create_lid` beim Rechnen würfe (`plane_of` und `opening`, ohne
zu werfen); `MainWindow._lid_reason` fragt ihn für `LID_OPS` einmal je Merkmal
und Auswertung. Gemessen am 14.09.2026: Beide Deckel standen an jeder Fläche
einer massiven Platte bedienbar da (Bedienweg-Durchsicht).

**Und die zweite Hürde muss es wirklich geben.** `applies_to` war bis zum
03.09.2026 eine Zusage, die nur Menü und Merkmalspanel eingelöst haben; die
Auswertung selbst hat nie gefragt. Über Chat oder Kommandozeile lief damit
`resize_feature` auf einer **Bohrung** durch — am exakten Kern und an der
Materialkompensation vorbei — und `rotate_feature` auf einer **Kugelfläche**,
die keine Lage hat. Beide Male blieb der Körper wasserdicht, und nichts wurde
rot. Wer eine Op schreibt, die ein erkanntes Merkmal annimmt, prüft die Art
gegen den **eigenen** Registereintrag, nicht gegen eine Liste im Modul; den
Satz dazu liefert `perceive.actions.reason_against`, damit Panel und Kern
denselben sagen.

**Und eine gerundete Seite ist keine Fläche mit Vermerk, sondern eine eigene
Art** (`curved_face`, seit dem 11.09.2026: der Bogen eines D, der Mantel eines
o). Zwölf Operationen an `face` setzen eine Ebene voraus — Bohren, Zeichnen,
Versetzen —, und ein Bogen hat keine. Wer eine Op schreibt, die ohne Ebene
auskommt, weil sie nur Dreiecke braucht (`paint_slot`, `clear_filament`),
nennt beide Arten in `applies_to`; wer eine Ebene braucht, nennt nur `face`.
Ein `applies_to=["face"]`, das stillschweigend auch für den Bogen gelten
sollte, gibt es nicht.

## Den Kern wählt der Körper, nicht der Kunde

**Aber die Frage davor lautet, ob es die Beschränkung überhaupt braucht.**
`requires_kind="brep"` ist richtig, wo ein Netz die Sache nicht hergibt — eine
Formschräge auf einer benannten Fläche, ein Schalenkörper, STEP. Es ist
falsch, wo nur der *Rechenweg* verschieden ist: *Verrunden* und *Fase* trugen
es bis zum 10.09.2026 und waren an jedem eingelesenen STL ausgegraut, obwohl
das Netz beide Handlungen hergibt (Entscheidung Robert: „alles soll immer
bearbeitbar sein, egal ob importiert Format egal und beim selbst zeichnen").
Sie stehen jetzt in `geom/edge_ops.py`, fragen `SceneObject.kind` im Rumpf und
wählen danach den Kern.

**Das ist kein Zwillingspaar** (`MENU_TWINS`, `registry/registry.py`), und der
Unterschied ist keine Feinheit: Ein Zwillingspaar sind zwei registrierte
Operationen für dieselbe Handlung, und bis P2.8 wählte der **Kunde** über
einen Haken im Dialog, welche entstehen soll. Hier wählt der **Körper**, und
dem Kunden bliebe gar nichts zu wählen — ein Netz lässt sich nicht exakt
verrunden (§30, der Rückweg zur Topologie existiert nicht), und ein exakter
Körper hat keinen Grund für den gröberen Weg. Ein Haken dafür wäre eine Frage
ohne Antwortmöglichkeit. **Seit P2.8 gilt dieselbe Weiche auch für die
Zwillinge** (Konzept §10.1, Entscheidung 4): *Bohrung setzen* und *Aushöhlen*
fragen die Körperart ihres Eingangs und rufen den exakten Zwilling selbst
(`drill_brep_hole`, `shell_exact` — Aushöhlen nur, wenn die Oberseite offen
bleibt und keine Entlüftung gewünscht ist, sonst der Netzweg mit Befund;
gewählte Öffnungsflächen rechnet seit P6.3 der exakte Kern selbst,
`brep.profiles.shell_open_at`);
die fünf Grundkörper entstehen exakt, wo der Kern da ist, ihr Netz-Zwilling
ist versteckt und über die Befehlspalette erreichbar. Der Haken ist aus beiden
Dialogen verschwunden; der Kernwechsel eines gespeicherten Schritts steht im
Kontextmenü des Verlaufs (`History.change_kernel`, `oberflaeche.md`). Dieselbe
Weiche, ohne Zwilling, tragen *Text aufbringen*, *Dichtung erzeugen*, *Deckel
erzeugen* und *Drehdeckel erzeugen*: Am exakten Träger entsteht exakt, auch
das neue Teil daneben. **Ein Erzeuger ohne Eingang hat keinen Körper, den er
fragen könnte** — ob Organizer, Text, Zeichnung und eigenständige Bausteine
neu exakt entstehen, ist eine offene Entscheidung (ein Zwilling je Erzeuger
sprengt den Werkzeugsatz des lokalen Modells, `agentenschicht.md`).

**Was der Kunde stattdessen erfährt, steht im `caveat`.** Am Netz ist der
Bogen ein Sehnenzug; die Grenze dafür (`units.MAX_FACET_SAG`) ist dieselbe,
mit der der exakte Kern tesselliert, und der Satz sagt, wann man den anderen
Weg braucht. Ein Unterschied, den man benennt, ist eine Eigenschaft; einer,
den man verschweigt, ist ein Fehlerbericht.

## Ein Parameter sagt, was er bewirkt

Jeder Parameter hat Titel, Vorgabe, Einheit, Grenzen und einen `doc`-Satz, der
sagt, was er bewirkt — nicht, wie er heißt. Vorderseite des Dialogs: die zwei
bis drei Werte, die man tatsächlich ändert. Alles Weitere hinter „Weitere
Einstellungen" (§2.4).

Toleranzen verweisen ins Materialprofil (`auto:<material>`), nie als Zahl.
Wo ein Projektparameter passt, steht keine Streuzahl.

### Eine Zahl, die nicht gesagt wurde (`optional`)

`ParamSpec.optional` erlaubt einer Zahl den Wert `None`. Gebraucht wird das,
**wo die Null selbst ein gültiger Wert ist**: Ein Textfeld hat den leeren Text,
ein Merkmalsfeld die leere Kennung, eine Koordinate hat nichts dergleichen.
`slot_hole` und `resize_hole` lasen drei Nullen in `x/y/z` als „lass das Loch,
wo es ist" — damit ließ es sich in jede Stelle versetzen außer in den Ursprung,
und Solidon legt einen Quader **um** den Ursprung. An einer mittig gelegten
Platte war (0 | 0 | 0) also nicht der Randfall, sondern die Mitte des Teils.

Wo eine Null **physisch unmöglich** ist — eine Länge, ein Durchmesser, eine
Anzahl —, braucht es das nicht: Dort ist die Null schon eindeutig „nicht
gesagt", und ein zweiter Mechanismus daneben liefe mit dem ersten auseinander.

Vier Stellen lösen es ein, und jede ist nötig:

* **Der Kern** (`params._coerce`) lässt `None` als Erstes durch — ein `None`
  hat weder Art noch Grenzen, jede Prüfung darunter schlüge daran fehl.
* **Der Agent** bekommt `"null"` in die Typliste (`json_schema`). Ohne das
  bliebe ihm nur, eine Zahl zu erfinden, und die naheliegendste wäre die Null.
* **Der Dialog** setzt den leeren Zustand **einen Schritt unter** den
  Mindestwert und schreibt dort einen Sondertext (Qts `setSpecialValueText`).
  Ein Drehfeld hat immer eine Zahl; ohne diesen Platz gäbe es keinen Wert für
  „habe ich nicht gesagt", und ein bloßes Bestätigen schöbe jedes Loch in den
  Ursprung.
* **Die Operation** fragt `is None` und nicht `is_zero` — `prepare_ops.
  _named_place` beantwortet das einmal für beide Lochoperationen.

Und die Gegenrichtung gehört zur Zusage: Genannt ist eine Stelle, sobald
**eine** der drei Achsen eine Zahl trägt. Wer eine Achse nennt, beschreibt
einen Ort und keine Verschiebung.

**Die ungenannten Achsen behalten dabei den gemessenen Wert** (14.09.2026).
Sie fielen auf null zurück, und damit sagte ein `x=20` aus Chat,
Kommandozeile oder Agent zweierlei: „setz das Loch auf x = 20" und „setz es
in y und z auf null". An einer mittig gelegten Platte sprang das Loch damit in
die Mitte des Teils, während das Feld daneben zusagt, eine leere Achse bleibe,
wo sie ist. Der Dialog merkte davon nichts — er belegt alle drei Felder mit der
gemessenen Mitte vor, dort ist keine Achse je ungenannt; der Fehler traf allein
die Wege, für die `optional` überhaupt gebaut wurde. **Ein Vorgabewert im
Dialog ist keine Prüfung des Kerns**, und ein Feld, das die Lücke immer füllt,
verbirgt sie.

### Sammelparameter (`kind` in `sketch`, `strokes`, `armature`)

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert — auch nicht „kurz" im Viewport, auch nicht im Agenten (Regel 2).

**Eine Geste ist nicht dasselbe wie ein Schritt.** Eine Op darf beliebig viele
Nutzergesten sammeln, solange ihr Ergebnis vollständig aus ihren Parametern
folgt: Der Editor schreibt in einen Parameterwert, die Geometrie entsteht erst
bei der Auswertung, und was das Fenster währenddessen zeigt, ist eine Vorschau.
Die Skizze macht es so (§30.1), das Sculpting wird es so machen. Was dabei
einzuhalten ist, steht unten unter „Sammelparameter" und wird von
`tests/test_gesture_ops.py` über das ganze Register geprüft.

Ein Editor sammelt darin, was er nicht in Zahlen fassen kann: eine Skizze als
JSON-Text (§30.1), eine Strichliste, ein Skelett. Fünf Eigenschaften machen
aus so einem Wert einen zulässigen Schritt statt eines Lochs in Regel 2 —
`tests/test_gesture_ops.py` prüft alle fünf über das Register: er geht in den
Op-Hash ein, er übersteht die runde Reise durch die Projektdatei, er ist
reiner Text, der Agent sieht ihn nicht, und er steht auf der Rückseite des
Dialogs.

Zwei davon sind leicht zu übersehen:

**Der Cache-Schlüssel muss die Parameter enthalten, die *in* einem
Sammelparameter gelesen werden.** Ein Maß in der Skizze darf ein Ausdruck sein,
ein Gelenkwinkel einer Stellung auch; ändert sich der Projektparameter
dahinter, ändert sich der **Text** nicht — die Auswertung gäbe das alte
Ergebnis zurück. `resolve_params` hilft dabei nicht: Sie sieht die **oberste**
Ebene eines Parametersatzes, und ein Sammelparameter steht dort als *ein* Wert.

`nested_references()` in `scene/evaluate.py` ordnet jedem betroffenen `kind`
seinen Sammler zu — `sketch` → `sketch_parameter_references()`, `armature` →
`pose_parameter_references()` —, und `_with_nested_context()` mischt die Werte
in den Schlüssel. Eine Funktion und keine Konstante, denn `geom.pose` schließt
als gewöhnlicher Import oben einen Kreis über `scene.expressions`; der Sammler
der Pose kommt deshalb erst beim ersten Aufruf dazu. **Eine Zuordnung und keine Bedingung**, weil genau das schon
einmal schiefging: `"sketch"` stand dort hart verdrahtet, die Pose kam später
dazu und wurde übersehen — obwohl vier Stellen zusagten, dass ein Gelenkwinkel
ein Projektparameter sein darf. Wer einen neuen Sammelparameter mit Ausdrücken
baut, trägt ihn hier ein; das ist eine Zeile und keine Suche.

`strokes` steht bewusst nicht drin: Ein Pinselstrich *ist* eine Koordinate,
kein Maß, das jemand an einen Parameter hängt.

**Der Agent bekommt den Parameter nicht zu sehen.** Skizzen entstehen über
benannte Grundformen und Maße, nie über rohe Punktlisten (§26, Leitprinzip 5).
`json_schema()` lässt `kind="sketch"` deshalb ganz aus, und die Sitzung lehnt
ein trotzdem mitgeschicktes Argument ab. Zwei Ebenen, weil eine Lücke im
Schema noch kein Verbot ist.

### Eine Operation, die an ihren eigenen Eingängen vorbei liest, bringt das Gelesene in den Schlüssel

**Und der Schlüssel muss die Träger kennen, von denen eine Operation an den
eigenen Eingängen vorbei liest.** `operation_hash` deckt die Hashes der
Eingänge — drei Lesarten greifen aber auf fremde Körper der Szene zu: das
Ziel von `align_to_feature` (`kind="feature"`), die `up_to`-Fläche
(`TARGET_FIELD`) und die `feature:<id>`-Ebene jeder Skizze
(`feature_ref_of_sketch`, dieselbe Funktion wie im Verweisfilter) — auch durch eine
abgeleitete Ebene hindurch (`standing_on_feature`), am Feldschnitt und am
Dichtweg genauso wie an der Extrusion. **Den Rahmen einer Ebene fragt eine
Operation mit den Projektparametern** (`sketch.planes.frame_in_scene(plane,
ctx.scene)`, derselbe Weg wie im Skizzenmodus): Eine Versatzebene darf ihren
Abstand als `@name` schreiben, und `frame_for_plane` ohne Werte gibt dann
`None` — gebaut für Ansichten, die nichts zeichnen müssen. Feldschnitt und
Dichtweg fragten so und endeten in einem `AssertionError` bzw. „Wählen Sie
eine vorhandene Zeichenebene" (RM-188 P3.2, Durchsicht 0.5.0).
`_with_nested_context` mischt die Hashes **aller** Träger des benannten
Merkmals in den Schlüssel — alle, weil zwei Körper denselben Merkmalsnamen
tragen können. Ohne das behielt ein ausgerichteter Körper mit Cache die alte
Lage und eine `up_to`-Extrusion die alte Höhe, über das Schließen hinaus.
**Und die vierte hängt an keinem Parameter.** `orient_for_print` liest die
*übrigen* Körper der Szene — es dreht seine Eingänge und ordnet sie danach an,
ohne einen in einen fremden zu legen. Über die Oberfläche sind das alle
(`whole_scene`), ein **gespeicherter** Auftrag trägt aber die Teilmenge von
damals, und genau der liest an seinen Eingängen vorbei. Kein Feld benennt sie, also
findet sie keiner der drei Zweige oben. Sie ist am **Register** deklariert
(`OperationSpec.reads_other_bodies`), und `_with_nested_context` mischt dann
die Hashes **aller** Objekte unter `#scene` in den Schlüssel. Ohne das wich
ein gedrehter Körper einem Nachbarn aus, der längst woanders stand — mit
Cache-Treffer, über das Schließen hinaus.

**Und die fünfte kam mit der Rückholung auf das Bett.** `translate_object`,
`rotate_object` und `scale_object` tragen `keep_on_bed`: Führt die Bewegung
den Körper über den Rand der Druckfläche, wird er zurückgeholt — und die
freie Stelle dafür sucht `back_onto_bed` um die **übrigen** Körper derselben
Platte herum. Kein Parameter benennt sie, also steht auch diese Lesart am
Register (`reads_other_bodies`). Ohne sie behielte ein zurückgeholter Körper
seine Stelle, nachdem der Nachbar, dem er auswich, längst woanders steht.

**Zurückgeholt wird vom Rand, nicht aus einem Nachbarn** (Entscheidung
Robert, 18.09.2026: „beim bewegen und einer Kollision werden die Körper
versetzt, vllt will man sie aber zusammenhieben zum verschmelzen, so nicht
möglich"). Die Bindung hielt bis dahin zwei Bedingungen — innerhalb der
Fläche *und* ohne Überschneidung —, und damit war das Zusammenschieben
zweier Teile über den Griff nicht mehr zu machen: Wer sie ineinanderzog,
bekam sie auseinandergeschoben, bevor er *Vereinigen* oder *Weich
verschmelzen* anklicken konnte. Zwei Körper am selben Ort sind eine
**Absicht**; ein Körper neben dem Bett ist es nie. Gemeldet wird die
Überschneidung weiterhin — `check_collisions` und
`scene.evaluate.check_bodies_in_one_place` sagen es, ohne etwas zu bewegen.

Wer eine neue Lesart aus `ctx.scene` baut, trägt sie hier ein — dieselbe
Pflicht wie bei `nested_references()` darüber. Und die Frage davor lautet, ob
ein *Parameter* das Gelesene benennt: Wenn ja, gehört sie zu den drei oben;
wenn nein, ist sie eine Eigenschaft der Operation und gehört ins Register.

### Ein Maß mit Verlauf braucht einen Anfang, den die Kante kennt

Ein veränderlicher Radius hängt an **Stellen**, und eine Stelle braucht einen
Anfang, der eine Neuauswertung überlebt: bei einer offenen Kante das linke
Ende (dann vorn, dann unten — `edges.starts_at_first`, dieselbe Regel wie die
Richtung im Kantenschlüssel), bei einem Ring der Punkt kleinster Lage in
`LOOP_START` mit Laufrichtung nach `LOOP_WAY`. Nie eine Knotennummer, nie der
erste Punkt des Zugs. Beide Kerne fragen dieselben Funktionen; ein neuer
Verbraucher auch. Wo es keine Form gibt — Ring mit verschiedenem Anfangs- und
Endradius, verschiedene Radien an einer gemeinsamen Ecke —, ist das eine
Absage mit Weg, nicht eine stille Wahl (Regel 21).

**Eine Tabelle für den exakten Kern gilt einer Kante, nicht der Kontur.**
`SetRadius(UandR, IC, IinC)` legt die Tabelle auf Kante `IinC`; wer die ganze
Kontur an Kante 1 hängt, verrundet eine Kette zur Hälfte mit dem Endradius.
Und ein eigenes `Law_Function` nimmt OCCT 8.0.1 gar nicht an.

### Kantengruppen und gebogene Züge

Ein geschlossener Ring hat keine Richtung von Anfang zu Ende, und `flat`
(`|z| < 0,1`) galt bis Format 36 an jedem: „alle waagerechten Kanten“ nahm am
Quader 40 × 30 × 20 mit Querbohrung Ø 6 zehn Kanten statt acht, die zwei
stehenden Mündungen eingeschlossen, und *Verrunden* rundete sie mit (RM-279).
Die Beschriftung nannte den Ring da schon nach seiner Ebene „Senkrecht“
(RM-269). Die naheliegende Einheit — die Mündung auch zu „alle senkrechten
Kanten“ zu zählen — hat die Release-Sitzung 0.5.1 nach Messung verworfen: Die
Vorgabe von Verrunden, Fase und Wulst ist „senkrecht“, und sie hätte an jedem
Teil mit Querbohrung die Mündungen mitgerundet, bei R 5 an Ø 6 zum Trichter;
am Netz kam die Rundung eines Rings damals zudem zu flach heraus, und an
`pegboard-gs-100` sank der größte passende Radius von 0,85 auf 0,71 mm. Für den
Kunden ist eine senkrechte Kante eine gerade Kante und kein Lochrand. Ein Rand
in einer Seitenwand gehört deshalb zu keiner Gruppe, und die doc-Sätze von
`edges` und `rings_by_plane` sagen es, weil die Beschriftung „Senkrecht“ zeigt.
Gespeicherte Schritte behalten den alten Weg (Migration 36 → 37).

**Ein gebogener Zug ist kein Satz Prismen.** Am Netz bekam jedes Stück eines
Zugs sein eigenes Prisma, mit Stirnflächen quer zum eigenen Stück. Biegt der Zug
und liegt der Zwickel außen um die Biegung — am Rand einer Bohrung in einer
Wand —, klafft zwischen zwei Prismen ein Keil, und dort bleibt Material stehen:
Quader mit Bohrung Ø 6, R 2 5,4 % und R 5 20,5 % zu wenig, Fase 2 14,4 %, die
Rundung bis 1,95 mm neben dem Torus, als Sägezahn um die Mündung. Jetzt liegt
je Knoten ein Querschnitt mit gemittelter Richtung und gemittelten Normalen,
dazwischen verbindet das Werkzeug gerade, wie der exakte Kern einen Torus
tesselliert; ein Ring wird ein Schlauch ohne Stirnflächen. Danach liegt die
Rundung höchstens 0,043 mm (R 5) neben dem Torus, innerhalb
`units.MAX_FACET_SAG`; der Sehnenzug des Bogens trägt rund 4 % mehr ab als der
Kreis — dieselbe Grenze. Ein gerader Zug, ein Knick über `SWEEP_TURN_LIMIT`
(45 Grad) und eine Fase mit zwei Maßen (`shape`) bleiben beim Prisma; ein
Radiusverlauf geht denselben Weg (2 → 4 → 2 an der Mündung: 0,87 → 1,05 × exakt),
und nur wo er nicht trägt, bleibt es beim Loft je Stück (`_varying_tool`).

**Eine Gruppe lässt aus, was das Maß nicht trägt** (28.09.2026, Entscheidung der
Release-Sitzung 0.5.1 nach Kundensicht; Robert gemeldet). Vom 23.09. an sagte
die ganze Gruppe ab, sobald eine Kante auf einer schmalen Fläche lag — mit dem
größten Maß, das überall passt (Durchsicht vor 0.5.0, Paket „merkmalsops“:
vorher machte das Netz die Wand still niedriger). An Kundenteilen mit einer
einzigen schmalen Fläche war „senkrecht“ damit bei jedem Radius unbenutzbar
(pegboard-goot ab 0,37 mm, pb3041 ab 0,21 mm), und einzeln wählen kann ein
Kunde ohne CAD nicht. Jetzt fragt `edges.contact_band_limits` je Kante; die
Gruppe bearbeitet, was trägt, und `edges.too_narrow` nennt die übrigen mit dem
kleinsten Maß, das dort passt, und *Stelle zeigen* — derselbe Grundsatz wie für
Züge ohne Winkel (`edges.skipped`). Stoßen zwei gewählte Kanten auf derselben
schmalen Fläche aneinander, fallen beide heraus: welche bleiben soll, wäre
geraten. Trägt keine Kante das Maß, bleibt die Absage; eine einzeln gewählte
Kante hält weiter an. Die Wand bleibt dabei so hoch, wie sie war.

**Der exakte Kern fragt dasselbe, baut aber nicht immer den Rest.** Die Frage
stellt er an seiner Tessellierung (`edge_ops._group_that_fits`) und nimmt die
exakten Kanten, die auf einem tragenden Zug liegen (zwei innere Punkte, die
Enden teilt eine Kante mit ihren Nachbarn); glatte Kanten ohne Zug fallen wie am
Netz mit `edges.skipped` heraus. Wo OpenCASCADE die verkleinerte Gruppe nicht
baut (Hohlkasten 3 mm, „alle“ R 2: 17 Kanten, jede einzeln baubar, zusammen
nicht) oder offen tesselliert (zwei Rundungen an pegboard-goot, bei jedem Radius
und auch einzeln), bleibt die Absage mit der größten Zahl. Ein Suchen nach dem
baubaren Rest durch wiederholtes Bauen wurde gemessen und verworfen: 15 bis 37 s
je Vorschau an den Pegboards, und der Rest war teils offen.

**Seit RM-435 sucht die exakte Gruppe gezielt, je Kontur** (02.10.2026). Mit
der Bindung an native Kanten (RM-322, `0041000a0`) lief jede exakte
Gruppenrundung durch die Auslass-Suche von RM-284, die jede Kante einzeln und
jede Gruppe ohne eine Kante baute: an `pegboard-gs-100-v2.step` („alle“ R 0,5)
134 Bauten und 263,6 s statt 3,0 s, an goot 288 Bauten und 148 s für eine
Absage. Jetzt fragt sie zuerst, was der Builder selbst meldet
(`NbFaultyContours`/`FaultyVertex`; `FaultyContour` zählt Streifen, nur die
ersten `NbContours` sind Konturen — am Prüfkasten Streifen 25 bei 17 Konturen),
ortet ungültige Flächen und offene Dreiecke über `Generated` und die
Kopierabbildung, und erst ohne Hinweis folgen Proben je Kontur und das
Weglassen je einer Kontur. gs-100: 3 Bauten, 61 statt 58 Kanten gerundet;
goot senkrecht R 1: 4 statt 10 Bauten, dasselbe Ergebnis (26 798,415 mm³);
goot „alle“ R 0,5: 101 von 143 gerundet nach 8 Bauten statt Absage nach 288;
pb3041 „alle“ R 0,5: 73 von 104 wie vorher, aus 28 statt 210 Bauten.
Ausgelassen wird je Kontur, weil `Add(radius, edge)` die Rundung über
tangentiale Nachbarkanten fortsetzt; am Crimper läuft so die Kontur der
eindeutigen 20-mm-Kante über eine Kante, an der der Knick tangential ausläuft,
und baut bei keinem Radius gültig — dort bietet der Befund das
Dreiecksmodell an. Die Wand wird je Kontur geprüft, weil drei durch die
Bindung je Kante neu belegte Crimper-Kanten an einer 0,37-mm-Wand die ganze
Gruppe absagen ließen. Gezählt wird in nativen Kanten: pb3041 meldete für
dieselbe Geometrie erst 14, dann 2 zu schmale Kanten.

### Eine angestellte Fläche darf nicht durch fremdes Material laufen

Die Formschräge rechnet am Netz Werkzeuge zwischen alter und neuer Fläche;
liegt eines nicht ganz im Material (oder ganz davor), schneiden sich zwei
Flächen in einer Wand. Das ist eine Absage an **beiden** Kernen mit demselben
Satz — nicht ein Ergebnis mit stillschweigend niedrigerer Wand, und nicht ein
exakter Körper, den `ShapeFix` formal heilt. Tangential anschließende Flächen
sind notwendige Übergänge und gehen mit (Befund `draft.tangent_faces`, wo der
Kunde Flächen gewählt hat).

**Neben einer liegenden Rundung gibt es keine Schräge, und gefragt wird vorher**
(RM-230, 06.10.2026). Am Tray `build_tray_v3.step` tragen alle Wände unten eine
Rundung R 2; OpenCASCADE meldet an der ersten Wand `Draft_FaceRecomputation`,
weil es die Rundung neben der gekippten Wand nicht nachrechnet. Am Netz scheiterte
die Ecke, wo Fuß- und Eckrundung zusammenlaufen, und am einfachen Quader baute es
bei 1° und 2° mit der alten Rundung samt Knick (22 921 statt 22 909 mm³ über den
Weg aus dem Satz), bei 0,5°, 3° und 5° sagte es ab. Beide Kerne sagten „kleineren
Winkel oder weniger Flächen“ — beides half nicht, und „in Gruppen rechnen“ (der
erste Gedanke im Register) auch nicht: Jeder der fünf Körper scheitert für sich.
Der Weg einer CAD-Konstruktion — erst anstellen, dann runden — trägt in Solidon
noch nicht: *Merkmal entfernen* nimmt eine Fußrundung, die mit Eckstücken in
einer Kette liegt, nicht weg (am exakten Tray meldete es Erfolg und änderte
nichts, jetzt sagt es ab, `IsDeleted` in `_unround`). Der Satz nennt deshalb nur
die Wände ohne diese Verrundung (RM-230).

Die erste Fassung fragte erst nach dem Scheitern und nach jeder schrägen
Nachbarfläche; dann hieß auch eine Fase oder eine Querbohrung „Rundung“, und der
Rat zum Winkel, der dort hilft, fiel weg (Review Einheit 2). Gefragt wird jetzt
an beiden Kernen vor der Rechnung, und nach der eigentlichen Ursache: eine Fläche,
die nicht mitgestellt wird, ohne Knick an eine Wand anschließt und schräg zur
Entformungsrichtung liegt. Exakt sammelt `_tangent_chain` sie mit: Normalen an der
Kantenmitte, Schräglage an neun Punkten der Fläche (eine Vollrundung aus einer
Fläche liegt in ihrer Mitte waagerecht). Eine tangentiale Fläche, die steht und
sich nicht anstellen lässt — eine B-Spline-Ecke, ein fast stehender Zylinder —,
ließ `BRepOffsetAPI_DraftAngle` still senkrecht, und die gekippten Wände schnitten
sich in sie ein; dort sagt der exakte Kern jetzt `DRAFT_BESIDE_A_FREE_FACE`. Am
Netz heißt ohne Knick: unter der Knickschwelle des Bildes; weil eine ebene
Schräge, die mit 15° an eine Wand stößt, das auch tut, muss sich die Neigung
dahinter um mehr als die Knickschwelle ändern — ein Kegelstück am Fuß einer
gerundeten Ecke krümmt sich nur um die Entformungsrichtung und zählt nicht.
Eine Fase am Fuß aller Wände eines Quaders schneiden beide Kerne
mit, mit dem Volumen des analytischen Querschnitts
(`test_a_wall_on_a_chamfered_foot_is_drafted_on_both_kernels`); an nur einer Wand
oder am dünnen Kasten sagen die Kerne noch Verschiedenes (RM-230).

## Boolesches geht durch die Rückfallkette

Die Rückfallkette (§17.2) hat fünf Stufen, und die erreichte Stufe gehört in
`solver`:

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, entnadeln — ohne ein dichtes Netz aufzureißen —, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie, gleichverteilt aus den Rohbits des Generators | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen, zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag | — |

Stufe 4 kostet Genauigkeit und wird im Prüfbericht ausgewiesen, nie
stillschweigend verwendet. In Entwurfsqualität endet die Kette nach Stufe 2.

**Ein Eingang, dessen Teile einander durchdringen, wird vorher vereinigt —
mit Befund, nie still** (RM-221, `boolean.parts_united`). Der Slicer druckt
solche Teile ohnehin als eines; an ihnen einzeln zu rechnen gab Ergebnisse,
die weder das Modell noch den Druck beschrieben. Wer eine Operation baut,
die mehrschalige Körper an den Kern gibt, geht deshalb durch `boolean()` und
nicht an ihm vorbei.
Nach `voxel` ist die Materialslot-Zuweisung neu zu übertragen — die Vernetzung
wurde ersetzt (§20).

**Was sich nicht vereinigen lässt, hält nur dort an, wo es das Ergebnis
verdirbt** (RM-382, Entscheidung Robert 02.10.2026: „Das Beste für Kunden,
damit sie bearbeiten können."). Seit `eab5f4f47` hielt jede Boolesche an einem
Mehrschaler mit einer selbstkreuzenden Schale an: Der Laptop-Ständer (21 Teile,
eines kreuzt sich 1 121-mal selbst) ließ sich an keiner Stelle mehr bohren,
auch wo die Bohrung nichts traf, und der Satz nannte weder Grund noch Weg.
Verlässlich ist das Ergebnis aber überall, wo das Werkzeug die kaputte Schale
nicht berührt; dort rechnet die Kette wie in 0.5.1 mit den Teilen, wie sie
sind, und warnt. *Reparieren* fehlt am Halt mit Absicht: Die Reparatur meldet
eine Eigenkreuzung (`repair.self_crossing`), löst sie aber nicht auf — der
Knopf endete am selben Halt.

**Die Vorfrage zählt Paare, die sich überdecken, nicht Achsenläufe** (RM-381).
Am Besenhalter (59 740 Dreiecke, drei Schalen, lange Splitterdreiecke) zählte
die Achsensuche 55,7 Millionen Grobkandidaten für 14 058 Paare, deren
Hüllquader sich überdecken; ohne Paarbudget kostete das 3,9 s vor jeder
Booleschen, mit Budget gab sie sofort auf. Auch eine Draufsicht trennt dort nur
auf 1,85 Millionen Paare. Zwei Hüllquaderbäume, die gemeinsam absteigen, kommen
mit 0,05–0,08 s aus; an 64 mehrschaligen Korpuskörpern sind die Antworten
dieselben. Damit entfällt auch die Teilegrenze für die vollständige Frage
(RM-383): 300 getrennte Würfel hielten jede Boolesche an.

**Was der Kern nicht geschnitten hat, gibt er in der Darstellung des Eingangs
zurück** (RM-261, `attributes.in_source_layout`): dieselbe Eckenfolge je
Dreieck, dieselbe Reihenfolge der Ecken. `manifold3d` übernimmt ein
unberührtes Dreieck bitgleich, beginnt es aber an einer anderen Ecke und
nummeriert neu — und die Erkennung liest Normalen aus der Eckenfolge und
summiert in der Reihenfolge der Ecken. Nach der ersten Booleschen stand
deshalb jede Rundform in den letzten Stellen anders da, und an einer Schwelle
kippte ein Merkmal fern vom Schritt (am Gartenschlauchhalter ging eine
Verrundung 113 mm von der versetzten Bohrung in einem Kegel auf). Die
Dreiecksfolge bleibt die des Kerns, keine Koordinate ändert sich. **Wer
`manifold3d` außerhalb von `boolean()` ein Netz zurückgeben lässt, das in der
Szene landet** (`prepare_ops._without_scars` mit `simplify`), legt es ebenso
zurück. Das ist die Voraussetzung dafür, dass der Merker über die
Körpergrenze (`kern.md`) nach einem Schritt trifft.

**Und an seinem Ort: Das Werkzeug wandert in die Welt** (RM-274). *Bohrung
setzen* mit der Normalen einer angeklickten Fläche, *Bohrung ändern* und *Zum
Langloch ziehen* legten bis zur Durchsicht 0.5.1 den ganzen Körper in den
Rahmen der Bohrung und zurück. Am Gartenschlauchhalter (Ø 3 × 2 mm in die
größte Fläche, Normale +y) standen danach 17 490 Ecken außerhalb des Schnitts
woanders, 352 862 von 392 696 Dreiecken waren bitgleich, und der Merker über
die Körpergrenze rechnete 1 078 statt 79 Fragen neu. Mit dem Werkzeug in der
Welt ist das Ergebnis Bit für Bit das des achsparallelen Wegs (0 versetzt,
Merker 79). Die gemischte Ecke von *Verrunden* und *Fase* rechnet weiter im
Rahmen ihres Knotens, weil Bereich und Zielkörper genau in dessen drei Ebenen
liegen und eine gedrehte Ecke sie in der Welt nicht träfe; dafür bekommt jede
durchgereichte Ecke ihre Weltkoordinate zurück (am L-Profil mit Kugel vorher
481 von 511 fernen Ecken versetzt, gedreht alle, danach keine).

**Ein Werkzeugende in einer Fläche mit Luft dahinter reicht über sie hinaus**
(`prepare._open_ends`). Ein Werkzeug in Weltlage, das bündig in einer schrägen
Fläche endet, lässt eine Haut stehen — gemessen an einer um 17,5° gedrehten
Platte an der Mündung, bei 33° am Boden in der Unterseite, an jeder auf
float32 gerundeten Fläche. Der Weg über den Rahmen bereinigte nur
Float64-Rauschen und ließ deshalb an einer schrägen STL-Fläche über jedem
Sackloch, Langloch und jeder Aufweitung eine Scheibe in der Mündung stehen
(zwei Teile, keine Bohrung erkannt). In der Fläche heißt näher als die
Schweißtoleranz; Luft dahinter heißt, alle Dreiecke dort, die die Scheibe um
die Achse berühren, zeigen vom Werkzeug weg. Eine Haut unter der
Schweißtoleranz ist damit keine mehr — am Würfel 20 mm liegt die Grenze bei
3,5·10⁻⁵ mm, ein Tausendstel Millimeter bleibt ein echter Abstand
(`test_surface_placement.py::test_a_real_offset_from_the_drill_mouth_survives_roundoff_cleanup`).

**An einem eingelesenen Netz ist „koplanar" nur fast koplanar** (RM-166,
14.09.2026). Eine STL trägt float32, und ein Fasenkeil, dessen Flanke exakt in
der Körperfläche steht, ließ dort Haut ohne Dicke stehen — per Index dicht,
nach der nächsten STL-Runde nicht mehr. `edges.rounding_tool` gibt abziehenden
Keilen deshalb `BOOLEAN_OVERLAP` als Flankenüberstand; und weil sich die
Keilstücke eines Bohrkreises damit zu einem Werkzeug mit Nadeln an den
Stoßstellen vereinigen, hat Stufe 2 der Rückfallkette seither dieselbe
Zusicherung wie der Import: Entnadeln reißt kein dichtes Netz auf
(`boolean._welded_input`). Die Ausgabe des Kerns wird außerdem so verschweißt,
wie jeder Slicer sie verschweißen wird (`boolean._tidied`) — Eckpunktpaare
unter der Schweißtoleranz und Dreiecke mit doppeltem Index fallen weg, und
übernommen wird das nur bei unverändertem Volumen und dichtem Netz. Der
Kundenweg STL → Operation → STL → Import steht als Test in
`tests/test_export.py`.

## Befunde statt Protokoll

Findings zurückgeben, nicht selbst protokollieren. Der Prüfbericht setzt sie
zusammen, der Agent liest sie über `read_report`.

**Eine Operation, die nichts bewirkt hat, sagt das.** Das steht unterhalb
dessen, was Regel 17 erfasst — dort geht es um Ausnahmen, und hier gab es
keine: im Verlauf ein Schritt, im Bild dasselbe Teil, und der Nutzer sucht den
Fehler in der Geometrie statt in der Position. `boolean.without_effect`
vergleicht die Volumina und verlangt dafür nur ein `volume` (`HasVolume`) —
`MeshData` und der exakte `Solid` bringen beide eines mit. Die Skizzen-Ops
rechnen im exakten Kern (§30.1) und kamen deshalb lange nicht daran: eine
Tasche neben dem Körper lief genauso stumm durch, wie es die Magnettasche
einmal tat. Gemessen wurde an vier Fällen — Oberkante unter dem Körper, Ort
daneben —, und in allen vieren sagte niemand etwas.

**Wer Boolesches rechnet, fragt danach — ohne Ausnahme.** Bohren, Stopfen, jeder
Baustein und die Skizzentasche taten es; `label_text` nicht, und darum kam
„BASIS" graviert auf einem Rahmen mit unverändertem Volumen und unveränderter
Dreieckszahl zurück, ohne eine Zeile im Prüfbericht. Eine neue Operation mit
`boolean(...)` ist erst fertig, wenn diese Frage darin steht.

**Und die Frage gilt nicht nur dem Booleschen.** Am 31.08.2026 hat sie
`sculpt_strokes` gefehlt, und dort war der Ausgang schlimmer als Schweigen: Die
Operation meldete „Die Züge dieser Sitzung wurden auf den Körper übertragen",
während kein einziger Eckpunkt sich bewegt hatte. Der Vorbehalt im eigenen
Registereintrag beschreibt genau diesen Fall — „Ein Strich sitzt an einer Stelle
im Raum, und wer die Form darunter ändert, verschiebt die Fläche unter ihm
weg" —, und geprüft wurde er nicht. Gemessen am Schaustück des vierten Wegs, das
im Bild ein glatter Kiesel war: drei Fingerrillen 18 mm über dem Körper in der
Luft, null Abtrag, zwei Schritte im Verlauf, kein Wort im Bericht.

**Wo „getroffen" nicht „gewirkt" heißt, wird die Wirkung gemessen und nicht der
Treffer.** Der vierte Zug desselben Schaustücks griff 321 von 5770 Eckpunkten
und trug dabei 0,41 mm ab, bei eingestellter Stärke 5,0 — formal ein Treffer,
im Druck nichts. `sculpt.no_effect` misst deshalb die größte Verschiebung
gegen `Profile.printer.layer_height`: Was unter einer Schichthöhe bleibt,
entsteht auch im Druck nicht. Daneben nennt `sculpt.strokes_missed` die Zahl
der Züge, die gar nichts erreicht haben — die beiden Aussagen sind verschieden,
und die zweite sagt dem Nutzer, wo er suchen muss.

**Und gefragt wird mit dem Profil.** Die Grenze ist nicht `EPS_GEOM`, sondern
`Profile.smallest_printable_volume` — ein Stück Extrusionsbahn von einer
Bahnbreite Länge. Ein Werkzeug, das den Körper knapp verfehlt, schneidet keine
Null: es nimmt den Span mit, den die beiden Hüllen gemeinsam haben. Eine
Bohrung Ø4,2 durch eine 14 mm dicke Platte, gesetzt in die Öffnung eines
Rahmens statt aufs Material, trug **0,002 mm³** ab statt 194 — mehr als das
Rechenepsilon und trotzdem nichts, was jemand je zu sehen bekommt. Ohne
`profile` bleibt es beim Epsilon: ein Aufrufer, der keinen Drucker kennt, soll
keinen erfinden (Regel 7).

**Und ein abtragender Baustein fragt die Tiefe** (`parts.ops._cuts_no_layer`,
Durchsicht 0.5.1). Eine Magnettasche, auf der Unterseite eines Deckels
eingetippt und ohne Fläche nach oben geöffnet, hing unter dem Deckel in der
Luft und trug nur die Haut über ihrer Öffnung ab: 0,5 mm³, mehr als ein Stück
Bahn, und kein Kern sagte etwas. Das Abgetragene über den mittleren
Querschnitt des Bausteins verteilt ist eine Tiefe; unter einer Schichthöhe
entsteht davon nichts, und `parts.cuts_no_layer` nennt beide Wege — die
Fläche anklicken oder Position und Richtung im Schritt prüfen. Die Richtung
wird nicht aus der nächsten Fläche geraten (Regel 21): Auf einer Kante sind
es zwei, im Material keine, und gespeicherte Schritte rechneten still anders.

**Was ein späterer Schritt behoben hat, warnt nicht mehr.** `SETTLED_BY`
(`scene/evaluate.py`) streicht einen Befund, sobald einer aus seiner Menge an
einem **späteren** Schritt und am **selben Körper** steht. Beides gehört zur
Bedingung: Ein Reparieren vor dem Einlesen des nächsten Modells hebt dessen
Befunde nicht auf, und zwei Modelle in einer Szene teilen sich den Bericht,
nicht ihre Löcher. Gestrichen und nicht herabgestuft — „Das Modell ist nicht
geschlossen" steht im Präsens und beschreibt einen Zustand, den es nicht mehr
gibt; als Hinweis wäre der Satz nicht milder, sondern falsch. Übrig bleibt der
Satz des Schritts, der es behoben hat, und der erzählt die ganze Geschichte.

**Und ein Zustandssatz, den der Endstand widerlegt, fällt auch ohne späteren
Befund** (`evaluate._without_outdated`, 24.09.2026). „Nicht geschlossen" an
einem Körper, der am Ende dicht ist (`CLOSED_STATE_CODES`), und „aus mehreren
Teilen" oder „ein Teil im Teil" an einem, der am Ende ein Stück ist
(`ONE_PIECE_CODES`), und „Außenseiten gegeneinander" an einem einheitlich
gewickelten (`WOUND_STATE_CODES`), sagen Präsens über einen Zustand, den es
nicht mehr gibt — gleich welcher Schritt ihn aufgehoben hat. Wer einen neuen
Befund über Dichtheit, Teilezahl oder Wicklung baut, trägt ihn in eine der
drei Mengen ein.

**Die Reparatur löst Überschneidungen von sich aus auf** (Entscheidung Robert,
24.09.2026): `RepairParams.self_intersections` steht auf an. Gespeicherte
Schritte behalten, was sie hatten — die Migration 34→35 schreibt dort `False`
hinein (`_keep_repairs_as_they_were`), und ein Befund bietet
*Überschneidungen auflösen* an. Eine Schale, die sich selbst kreuzt, wird
dabei benannt und nicht vereinigt (`repair.self_crossing`).

**Und was aus einem Verhältnis entsteht, wird gar nicht erst je Schritt
gefragt.** `SETTLED_BY` streicht nachträglich, was ein späterer Schritt behoben
hat — das setzt voraus, dass es einen zweiten Befund gibt, der die Heilung
ausspricht. Drei Fragen haben den nicht, weil niemand sie beantwortet: ob ein
Körper auf dem Bett liegt, ob zwei am selben Ort stehen, und **was von der Wand
übrig ist** (`check_placement`, `check_bodies_in_one_place`, `check_thin_walls`
in `scene/evaluate.py`, RM-127). Sie laufen einmal, am fertigen Zustand, und
genau deshalb tragen beide Reihenfolgen derselben zwei Änderungen denselben
Bericht: Wer Ø 19 in einen Zylinder Ø 20 bohrt und den Mantel danach auf Ø 30
vereinigt, hat zwischendurch 0,5 mm Wand und am Ende 5,5 — die Zwischenzahl ist
keine Aussage über das Teil, das dasteht.

Die Wand steht dabei in **keinem** Merkmal: `relations.thinnest_sleeve` rechnet
sie aus einer Bohrung und dem Mantel um sie herum — dieselbe Regel wie
`sleeve_at` am einzelnen Merkmal, in einem Durchgang über den Körper, weil sie
nach jeder Auswertung läuft. Die Grenze ist
`Profile.minimum_wall_thickness` und keine Zahl im Code (Regel 7) — ohne Profil
gibt es keine Aussage. Wer eine vierte solche Frage baut, fragt zuerst, ob sie
an einem Verhältnis hängt; wenn ja, gehört sie hierher und nicht in die
Operation. Und die Warnungen **in** den Operationen bleiben, wo sie stehen:
`hollow` spricht über den Wert, den jemand eingetragen hat, und der bleibt wahr,
gleich was danach kommt.

## Eine grobe Vorauswahl darf nicht das Urteil sein

`over_the_edge_along` fragte den Hüllquader: Ragt die Mündungsscheibe hinaus,
hat die Bohrung eine offene Flanke. Der Docstring nannte die Näherung
ausdrücklich („gemessen am Hüllquader und nicht an der wirklichen Form") — und
genau deshalb hat zwei Monate niemand nachgesehen, was sie kostet: **jede**
Bohrung auf einen Zylinder, eine Kugel oder einen Ring bekam die Warnung, weil
der Scheitel einer gekrümmten Fläche auf der Hülle liegt und die getroffene
Facette schräg steht (gemessen 09.09.2026: Normale (0,9988 | 0,0491 | 0),
0,0785 mm Überstand). Der Körper war danach jedes Mal wasserdicht, einteilig
und richtig gebohrt.

**Eine Warnung, die im Normalfall kommt, ist keine Warnung mehr.** Sie ist der
Lärm, nach dem niemand mehr in den Prüfbericht sieht — und sie schickt den
Kunden an einen Rand, an dem nichts ist. Wo die grobe Frage anschlägt, wird
deshalb an der Sache nachgemessen; wo kein Netz vorliegt, bleibt es bei der
Näherung, und die ist dort zu streng und nie zu milde.

**Und wo sie nicht anschlägt, ist das noch kein Freispruch** (RM-249). Eine
Seite, die schmaler ist als die Hülle, liegt innerhalb des Hüllquaders: An der
Lochplatte gs-100 lief eine Kopie 3,4 mm über die Seite, und keiner der beiden
Kerne sagte etwas. Mit ``reach`` — der Länge der Bohrung von ihrer Stelle aus —
fragt `over_the_edge_along` dann am Netz nach (`_flank_opens_within`): der
Kranz über die eigene Länge der Bohrung, nur an Tiefen, an denen sie
schneidet, und von den Punkten in Luft nur die, von denen ein Strahl quer zur
Achse frei nach außen geht. Ein Punkt in einer Nachbarbohrung trifft deren
Wand und ist kein Rand; dafür gibt es den Nachbarbefund. Über die ganze Hülle
getastet, wie `_flank_is_open`, hieße jede Bohrung in einer dünnen Platte
„über die Kante". Jeder Weg, der eine Bohrung setzt, gibt ``reach`` mit —
Bohren, Ändern, Langloch, Versetzen, Verdoppeln, Kippen, Muster, an beiden
Kernen.

Die Frage davor, für jede Näherung im Haus: **Wie oft schlägt sie im Normalfall
an?** Eine Näherung, die nur Fehlalarme in einem seltenen Fall erzeugt, ist
richtig; eine, die den häufigsten Fall trifft, ist ein Fehler mit Docstring.

**Und der Test dazu muss den Weg des Kunden gehen.** Der erste Anlauf setzte
die Bohrachse von Hand auf (1, 0, 0) — ideal achsparallel, damit `extent = 0`,
und der Fall entsteht gar nicht. Er blieb ohne den Fix grün. Was ihn trägt,
ist die Normale aus dem echten Treffer (`original_surface_hit`), denn erst die
tesselierte Facette erzeugt den Überstand.

**`_flank_opens_within`** fragt nur dort, wo die Bohrung schneidet, zählt nur
Luft mit freiem Strahl quer zur Achse, und eine Nachbarbohrung ist kein Rand.

### Wo die Vorprüfung selbst urteilt, beweist sie es gegen die Toleranzen der genauen

Die Trennprüfung der Schnittsuche (`intersections._separated`, RM-244)
verwirft Paare, ohne dass die genaue Prüfung sie je sieht — ihr Nein **ist**
das Urteil. Sie darf deshalb nur verwerfen, was die genaue Prüfung mit all
ihren Toleranzen ebenfalls verwürfe, und nicht, was „geometrisch offensichtlich
getrennt" ist. Die genaue Prüfung nimmt eine Lücke unter `EPS_GEOM` als
Schnitt, legt Ecken innerhalb `EPS_GEOM` zusammen und zählt eine Ecke bis zu
ihrer Rechengrenze als in der Ebene des Partners. Jede dieser Toleranzen
brauchte eine eigene Sicherung: einen Abstand, der über allen liegt; eine
gemeinsame Ecke nur zwischen parallelen Ebenen, weil schräg zueinander kein
fester Abstand die Toleranz an der Ecke deckt; ein Spiel an der gemeinsamen
Ecke, das unter der Schwelle eines Treffers bleibt.

**Jede Sicherung hat einen konstruierten Fall, an dem ihr Fehlen einen Treffer
kostet** (`_pairs_at_the_tolerance` in `tests/test_self_intersections.py`).
Zufällige Paare und echte Netze fanden keinen davon: Zweitausend Zufallspaare
und ein Fächer von Nadeln blieben grün, als der Abstand auf null stand. Wer
eine Vorprüfung dieser Art baut, nimmt jede ihrer Bedingungen einmal heraus
und sucht den Fall, der dann rot wird — findet er keinen, konstruiert er ihn an
der Toleranz, die die Bedingung deckt, oder die Bedingung ist überflüssig.

Gemessen werden an ihr Vollständigkeit und Abdeckung, nicht die Zeit allein.

**Und sie bezahlt ihre Rechnung selbst.** Ein Budget, das die genauen
Prüfungen zählt, zählt die Vorprüfung mit (`SEPARATION_COST`) — sonst liefe
sie an einem Netz, dessen Paare sie alle trennt, ohne Grenze. Und sie steigt
früh aus, wo sie nicht trennen kann: Die erste Fassung rechnete jedes Paar
ganz und kostete an einem organischen Netz fast so viel wie die genaue
Prüfung, die sie ersparen sollte. **Gemessen wird dabei beides, die
Vollständigkeit und die Abdeckung dort, wo die Vorprüfung nichts bringt:**
Ein eigener Anteil für den frühen Ausstieg ließ die Netzfehlerkarte an
organischen Netzen acht Prozent weniger Dreiecke prüfen — obwohl die Zeit je
Paar gesunken war, weil die genaue Prüfung gleiche Ecken seither nicht mehr
zusammenlegt.

**`_touching_apart` vor der Suche um aktive Dreiecke** (`crossings_at`, RM-419):
Der Formschritt fragte die ganze Suche über den gemeinsamen Hüllquader aller
bewegten Punkte; an einer Kugel aus 327 680 Dreiecken kosteten sechs kleine
Züge 29 bis 32 Sekunden statt 0,22. Neun von zehn Kandidaten einer glatten
Fläche teilen eine Ecke und stehen schräg — `_separated` gab sie alle an die
genaue Prüfung (an der Kugel mit R 10: 91 351 von 93 211). Getrennt werden sie
über die Seite ihrer freien Ecken jenseits `margin` und, wenn beide über die
Ebene des anderen reiten (am Rand einer Mulde), über auseinanderlaufende
Schnittstrecken. Die eine Sicherung, nie fast parallel, hat ihren roten Fall
(`_folds_at_the_tolerance`: Sinus 8,5·10⁻⁷, freie Ecken 4,8·10⁻⁶ über der
Ebene); eine zweite gegen zusammengelegte nahe Ecken hatte keinen — eine Ecke
näher als `EPS_GEOM` liegt selbst innerhalb `margin`, gesucht an 200 000
schmalen Dreiecken — und fiel. Was die Auswertung so findet, sagt der Export
weiter (`writer.CARRIED_TO_EXPORT`); nachmessen hieße, jeden Körper ganz zu
prüfen.

## Eine Zahl beschreibt die Regel, nicht die Lage

`_feature_body` lehnte einen Flächenausschnitt mit zwei Randringen ab, weil
zwei Ringe hießen: „dieses Merkmal geht in ein anderes über". Der Schluss war
richtig gemessen und galt für **eine** Lage. Nach dem Verschließen der Bohrung
unter einer Senkung bleiben es zwei Ringe — unten liegt jetzt aber Material
statt eines weiteren Hohlraums, und die Senkung war damit nicht mehr zu
löschen (Befund Robert, 09.09.2026; gemessen an `plate_countersunk.stl`:
zwei Ringe zu 48 Ecken vorher, zwei zu 65 und 48 danach).

**Gefragt wird an der Sache, nicht an ihrer Kennzahl.**
`perceive.relations.cavity_chain_state_at` beantwortet beides — ob das Merkmal
Abschnitt einer Kette ist und ob es sicher einzeln ist —, und erst
wenn beides verneint ist, gehört der Hohlraum ihm allein (`_stands_alone`).
**Nicht sicher einzeln hat zwei Gründe, und die Absage nennt den richtigen:**
ein berührter fremder Rand (`NO_OWN_BODY`) oder eigene Ränder, die keine
Ringe ergeben (`CAVITY_TOPOLOGY_UNKNOWN`) — derselbe Grund, den der
Gruppenweg als `cavity_topology_unavailable` führt (`CavityState.reason`,
`prepare_ops.cavity_refusal`). Wer den Zustand liest, liest den Grund mit;
ein `(None, False)` war bis zum 20.09.2026 auch die Antwort auf „weiß nicht“.
`feature_placement_geometry` traf diese Unterscheidung seit je; sie fehlte
allein im Werkzeugbau.

**Und die Bedingung steht einmal** (`relations.cavity_is_shared`), nicht
zweimal wörtlich gleich in `slot_hole` und `perceive.actions` — bis zum
14.09.2026 hätte sich eine Seite lösen können, ohne dass etwas rot wurde.
Was einen geteilten Hohlraum **nicht** nehmen kann, sagt ab statt still ein
Stück zu bearbeiten — heute ist das allein *Zum Langloch ziehen*, mit
`NEEDS_A_PLAIN_BORE`, demselben Satz, den das Merkmalfenster an der Zeile
zeigt. *Merkmal drehen* und *Merkmal verdoppeln* sagten einen Tag lang
ebenso ab: An der Bohrung einer gesenkten Bohrung hatte *Drehen* nur den
Stumpf unter der Senkung gekippt, *Verdoppeln* einen Stumpf ohne Senkung
gesetzt (gemessen 14.09.2026). Seit dem 15.09.2026 nehmen beide die Kette mit
(RM-172, Entscheidung Robert), wie `move_feature` seit dem 09.09.

Die allgemeine Form, weil sie über diesen Fall hinausgeht: **Wer aus einer
Zahl auf einen Sachverhalt schließt, schreibt dazu, unter welcher Bedingung
der Schluss gilt — und prüft die Bedingung, nicht die Zahl.**

## Gekippt wird bis zur alten Randebene

**Und wer eine Kette kippt, baut ihr Werkzeug mit Überstand** (`_chain_tool`).
Der exakte Hohlraum aus den Flächen endet bündig in den Oberflächen: gedreht
um die Bohrungsmitte lag seine Decke 0,9 mm **unter** der Platte — ein
Einschluss statt einer gekippten Senkung —, und schon unverdreht ließ die
Differenz an der neuen Stelle eine Haut von 5 µm über der Mündung stehen
(§39; gemessen 15.09.2026: 0,25 mm³ im Schlauch, „nicht mehr durchgehend"). Das
Werkzeug fürs Kippen kommt deshalb aus den Kennzahlen: die Bohrung über ihre
Mündung hinaus, die Senkung als **größerer Kegel** nach oben — derselbe Kegel,
weitergeführt, bis er die gekippte Fläche überall verlässt. Wie weit, sagt die
Neigung (`_reach_past_a_tilted_face`, `_cone_past_a_tilted_face`): bei 30° an
einer 90°-Senkung Ø 16, 7 mm über der Bohrungsmitte, sind es 13,5 mm; ohne
Neigung bleibt die Zugabe aus §39. Mehr als nötig schnitte Luft — oder eine
Wand, die niemand gemeint hat; darum die Rechnung und nicht der Hüllquader.
Abnahme: 30° an der gesenkten Bohrung ergibt eine gekippte Senkung über einer
gekippten, durchgehenden Bohrung, und `detect` findet beide mit derselben
Achse (`test_turning_a_countersunk_bore_takes_its_sink_along`).

**Und was über die Mündung hinausreicht, endet an der alten Randebene**
(`_old_rim_caps`, RM-220). Vor der Fläche liegt sonst Luft; wo dort Material
steht, nahm die Verlängerung es mit — an einer Platte mit Rippe über der
Senkung 738 mm³ an beiden Kernen, am Schraubenhalter mit Wabenmuster 314 von
714 mm³ in den Waben, und der exakte Kern bohrte eine gekippte
Durchgangsbohrung über die ganze Hülle durch Rippe und Fuß. Die Ebenen sind
die echten Randringe bis zur äußeren Mündung (`_bore_end_planes`), mit der
Zugabe nur an offenen Mündungen: **die äußere immer**, auch unter einem
Deckel — dort ohne Zugabe, der Deckel bleibt —, **die ferne nur bei einer
Durchgangsbohrung**; am Sackloch ist sie der Boden, und der kippt mit. Beide
Kerne fragen dasselbe, der exakte an seinem Netz-Zwilling, und kappen am Netz
mit `section.cut`, am exakten Körper mit `edit.clipped_bore_tool`; scheitert
der ebene Schnitt — an der Öffnung eines Mini-Topfs, die Ebenen 0,44 mm
auseinander —, kappen Quader über die Boolesche Kette (`_boxed_in`), und nur
wenn auch das nichts Geschlossenes gibt, bleibt das Werkzeug ungekappt. Und der
exakte fragt danach die Nachbarwand wie das Netz (`_neighbour_bore_findings`).
**Eine Senkung ohne Bohrung kippt genauso** — am Netz über `_turned_open_cone`
(der gemessene Hohlraum, bloß gedreht, behielt auf einer Seite eine Decke),
am exakten Körper über `_exact_rotate_cone`; eine spitze hat nur einen
Randring, ihre Mündung, und `_bore_end_rims` nimmt ihn als äußeres Ende. **Und wer eine Senkung um ihren
halben Öffnungswinkel oder mehr kippt, bekommt eine Absage** mit dem größten
Winkel (`_sink_must_close`): Ihre Flanke liegt dann flacher als die Fläche, und
das Werkzeug lief als Rinne bis an den Rand des Körpers — 671 mm³ aus einer
Platte von 8 256. Abnahme:
`test_a_tilted_bore_takes_nothing_from_what_stands_before_its_mouths`,
`test_a_tilted_bore_reports_its_neighbour_on_both_kernels`,
`test_a_countersink_tilted_past_its_flank_is_refused_with_the_largest_angle`.
**Und eine einzelne Sackbohrung kippt genauso** (RM-263, Durchsicht 0.5.1):
Ihr Werkzeug war die gemessene Bohrung, gedreht, und endete an ihrem alten
Deckel — über der Seite, zu der die Mündung sinkt, blieb eine Haut stehen
(Magnettasche ohne Lippe um 10°: bis 0,72 mm, an beiden Kernen; die Kerne lagen
nur um die Zugabe aus §39 auseinander). `_blind_mouth` liest die offene
Mündung an den Randringen, `_blind_reach` rechnet die Verlängerung wie an
Kette und Durchgang, der Boden kippt ohne Zugabe mit, und `_old_rim_caps`
kappt an der alten Mündung (Netz `_turned_blind_bore`, exakt
`_exact_turned_blind_tool`). Abnahme:
`test_a_tilted_blind_hole_stays_open_at_its_mouth`,
`test_a_magnet_pocket_tilts_only_without_its_lip`.

## Ein Loch versetzt man an beiden Kernen gleich

`slot_hole` und `resize_hole` nehmen eine Stelle entgegen (`x/y/z`; **leer
heißt „lass es, wo es ist"**, seit die drei Felder `optional` tragen — siehe
„Eine Zahl, die nicht gesagt wurde" oben unter *Parameter*). Wer versetzt, schließt zuerst die alte Stelle —
am Netz über `prepare_ops._closed_at`, am exakten Körper über
`brep.edit.fill_bore` — und schneidet an der neuen. Bis dahin lehnte der exakte
Kern das mit einem Satz ab; die Absage ist gefallen, weil ihr Grund gefallen
ist (Robert: „zwischen den beiden soll es keinen unterschied geben bei
garnichts").

**Und seit dem 20.09.2026 gilt das für alle vier Merkmalshandlungen** (P2.4):
Versetzen, Verdoppeln, Drehen und Entfernen einer Bohrung oder eines
Langlochs lassen den exakten Körper exakt — schließen mit `fill_bore`,
schneiden mit `cut_bore`/`slot_bore`, nativ erkennen, Kennung belegt
fortführen; Senken und Verschließen ebenso, und wo die Frage nach Mündung
und Materialseite am Netz gestellt wird, stellt sie derselbe Helfer für
beide Kerne (`prepare.sink_placement`, `prepare.plug_placement`). Wer eine
Merkmalshandlung baut, die einen exakten Körper
vernetzt, tut es nur, wo der Kern die Form nicht hergibt, und der Befund
`evaluate.exact_became_mesh` sagt es; seit dem Einschluss (`edit.void_body`)
tut das keine Merkmalshandlung mehr. Zapfen, Kuppe und Kegelstumpf — und eine
Senkung oder Pfanne, die allein steht — gehen aus ihren nativen Flächen
(`brep.edit.solid_from_faces`); gekippt reichen Zapfen und Kegelstumpf in die
Grundfläche hinein und die Senkung ins Freie, so weit die Neigung verlangt
(`_reach_past_a_tilted_face`, `_cone_past_a_tilted_face`). Eine Kette aus Bohrung und Senkung
bleibt exakt — Stopfen und Werkzeug sind Rotationskörper ihrer Einlaufprofile
an den wirklichen Randebenen, beim Kippen um den Überstand der Neigung nach
außen gerückt; „nur das gewählte Merkmal“ einer Kette geht wie am Netz erst
ganz zu und schneidet dann frisch, was bleibt.

**Wer eine Kette nur versetzt, verlängert den exakten Körper an seinen
Mündungen** (`_past_the_mouths`). Das Werkzeug aus Kennzahlen stand am
15.09.2026 einen Tag lang auch hier — und trug je Versetzen bis zu 0,9 mm³ mehr
ab, als der Pfropfen zurückgab: Sein Vieleck umschrieb den Kreis, die echten
Flächen füllen nur den Kreis (sieben Tests der Senkungsübergänge rot). Jetzt
bekommt jeder ebene Deckel des Flächenkörpers, vor dem entlang seines Rands
keine Materialseite liegt, einen Kragen von `FEATURE_OVERLAP` — das ist die
Mündung; der Boden eines Sacklochs und die Ringstufe einer Zylindersenkung
bleiben bündig, sonst würde die Bohrung tiefer oder die Stufe abgetragen
(0,18 mm³, an der Stufe gemessen). **Und am exakten Körper stellt der Einlauf
dieselbe Frage** (`_BoreEntrance.open`, `_entrance_is_open`): Eine Senkung,
deren Mündung unter der Oberfläche liegt, ist ein vergrabener Hohlraum mit
einem Deckel aus Material, und ein Werkzeug, das dort um die Zugabe über die
Ebene hinausreicht, trug bei jedem Versetzen ein Scheibchen ab — 1,33 mm³ an
Ø 9,2 (Review, 21.09.2026).

**Den Kragen trägt die Wand, nicht die Deckelnormale** (RM-226, Nachtrag
04.10.2026). `_past_the_mouths` hob den Deckel längs seiner Normale an; an
einer schrägen Mündung ist das ein gescherter Ring — an der Platte mit
Oberseite z = 10 + x/4 um 14,04°, der Arkustangens der Neigung. In der Luft
schneidet er nichts. Starr längs der Schräge versetzt, verdoppelt oder
vervielfacht, liegt die mitbewegte Mündung aber im Material, und der Ring
wurde Wand der Kopie: 98 von 192 Wanddreiecken kippten bis 14,03° aus der
Senkrechten zur Achse. Vor der tangentialen Trennung (RM-226 Teil 2) las die
Erkennung die ganze Wand deshalb als gekrümmte Fläche, und die Kopie hieß am
Netz verloren (`duplicate_feature.feature_lost`, exakt eine Sackbohrung);
danach zählte sie den Ring nicht mit — Tiefe 10,750 gegen 10,771 mm, die
Senkung Ø 13,333 gegen 13,388 mm. Der exakte Kern schneidet die Bohrung als
Zylinder bis in die verschobene Randebene (`clipped_bore_tool`), die Kette als
Drehkörper ihrer Profile (`_exact_chain_tool_placed`). Jetzt setzt
`_continued_walls` jede Randecke in den Schnitt ihrer zwei Wandebenen mit der
verschobenen Deckelebene; am Facettenzylinder ist das die Achse, am Kegel die
Mantellinie. Langloch und Tasche mit Lippe bleiben beim Kragen längs der
Normale, weil der exakte Kern sie aus ihren Flächen ebenso anhebt
(`edit.collared`); eine Wand, die fast parallel zum Deckel ausläuft (eine
gerundete Mündungskante), auch — dort gibt es keine Fortsetzung, und die Ecke
rutschte weiter als `GRAZING_SLIDE`-mal die Zugabe.

**Die gerundete Mündungskante einer Zylindersenkung reist mit** (RM-259,
Durchsicht 0.5.1): Versetzen, Verdoppeln, Muster und Entfernen der ganzen
Kette fragen die Hohlraumflächen mit `mouth_blends=True`
(`relations.cavity_surface_indices`); dann gehört die Rundung zur Kette, ihr
äußerer Rand ist die Mündung, und der exakte Kern geht den Weg aus den
eigenen Flächen (`_carries_a_blend` → `_exact_chain_own_cavity`). Ohne sie
blieb an einer ebenen Platte an der alten Stelle eine Mulde von 1 mm, und an
der neuen deckte eine Haut die Senkung zu. *Bohrung ändern* und *Kippen*
fragen ohne — sie schneiden aus Profilen und Kennzahlen neu, die keine
Rundung kennen, und ein Stopfen samt Rundung ließ dort eine Haut über der
neuen Mündung stehen. In einer **gekrümmten** Fläche reist die Rundung noch
nicht (gs-100, Registerpunkt): Am Netz findet die Erkennung die Senkung hinter
einer Rollkugelrundung nicht, und um den Rand von gs-100 steht keine Fläche,
sondern drei. Abnahme: `test_a_rounded_mouth_travels_with_its_counterbore`.

**Gibt der Flächenkörper nichts her, füllt der Stopfen und schneidet das
Werkzeug der Kopie** (`_cavity_plug`, `_chain_copy_tool`) — wie beim Kippen
und Verdoppeln derselben Kette; bis zum 25.09.2026 sagte allein das Versetzen
ab. **Und ein Rand in einer schrägen, leicht gekrümmten Fläche wird aus den
Flächen gefüllt, mit der Fläche um ihn als Deckel** (`_body_from_faces`,
`curved_rims`, bis `CURVED_RIM` des Durchmessers neben der Ebene): Der
Zylinderstopfen reichte bis an den äußersten Punkt des Rands, an der konvexen
Hülle gekappt, und füllte die Luft vor dem Rest der Mündung — am
Gartenschlauchhalter 58 und 148 mm³ beim Kippen um 5° und 15°, in einer Rinne
11 und 43 mm³. Der Fächer vom Mittelpunkt des Rands, der danach kam, lag auf
dessen mittlerer Höhe und nicht auf der Fläche (RM-248): eine Mulde von
4,9 mm³ unter einer Senkung Ø 10 in einem Zylinder R 40, eine Beule von
26 mm³ in der Hohlkehle des Gartenschlauchhalters. **Jetzt wird die Fläche
gemessen und fortgesetzt** (`geom.mouth_cap`): als Höhenfeld über der
Ausgleichsebene des Rands, an den Facetten selbst abgetastet, bis zu einem
halben Radius um ihn, ein Polynom dritten Grades eingepasst — in
Grundrechenarten, denn seine Höhe setzt jede Ecke (RM-187, der Weg steht in
`test_platform_identity._WAYS`) —, und der Deckel ist ein Gitter auf ihm.
Proben, die um mehr als `MAX_FACET_SAG` danebenliegen, gehören zu einer
anderen Fläche (eine Kante im Ring) und fallen heraus; trägt die Fläche dann
nicht die Hälfte des Rings oder weicht sie am Rand weiter ab, gibt es keinen
fortgesetzten Deckel, und es bleibt beim Fächer. Das ist die Mündung mit
eigener Rundung an der Lochplatte gs-100: Die Rundung gehört nicht zur Kette
und bleibt beim Versetzen stehen. **Das Werkzeug an der neuen Stelle kommt
dann auch aus den Flächen** (`_past_curved_mouths`, `past_curved`): die Wand
des Rands entlang der Achse bis hinter den äußersten Punkt von Rand **und**
Fläche verlängert — ein Zylinder aus Kennzahlen trug eine andere Teilung als
der Stopfen und schnitt 1,1 mm³ mehr ab, und eine Ebene nur durch den
äußersten Randpunkt ließe über einer Kuppe eine Haut. Nur der Stopfen nimmt
den fortgesetzten Deckel; ein Werkzeug, das bündig schneiden muss, nie.
**Der Klick ins Bild nimmt dasselbe Paar** (`feature_placement_geometry`,
`flush`): Geist und Schnitt an der neuen Stelle sind das Werkzeug, gefüllt
wird mit dem Stopfen — der Geist reicht über die Mündung hinaus und stünde als
Stumpf vor der Fläche, 8,3 mm³ an der Platte mit Zylinder R 40. Wo die Flächen
keinen Körper hergeben, gilt auch dort das Werkzeug aus Kennzahlen.
Abnahme: `test_a_widened_bore_whose_mouth_lies_in_a_curved_face_is_moved_on_both_kernels`
(Zylinder, Rinne, Naht Ebene-Zylinder, beide Kerne, unter 0,5 mm³),
`test_a_bore_under_a_curved_face_is_closed_up_to_that_face` (exakt, gegen das
integrierte Profil) und
`test_a_chain_whose_mouth_lies_in_a_curved_face_can_be_placed_by_hand`.

**Eine Bohrung, die sich an beiden Enden weitet, ist eine Kette mit zwei
Seiten** (RM-245). Die Kette beginnt mit der engsten Bohrung, dahinter stehen
je Seite ihre Erweiterungen nach außen; welche zu welcher Seite gehört, sagt
`relations.cavity_sides`. Kein Kettenweg nimmt an, dass `chain[-1]` die
einzige Mündung ist: Werkzeug, Kappen, Senkungsprüfung, Randebenen und der
exakte Einlauf (`_BoreEntrance.back`) fragen je Seite, und die Bohrung
dazwischen hat keine eigene Mündung. **Die äußere Zylindersenkung darf am
exakten Kern in eine gekrümmte Fläche münden** (`_curved_mouth_planes`,
offen und bis `CURVED_RIM` neben der Ebene): Das Werkzeug reicht bis zur
Ebene durch den weitesten Randpunkt, gefüllt wird aus den nativen Flächen
(`edit.solid_from_faces`, `fan_caps`). Der Deckel ist dort die Fläche um den
Rand (`edit._continued_cap`, RM-248): Liegt der Rand in **einer**
Nachbarfläche, eine Fläche auf deren Träger, begrenzt vom Lochdraht —
exakt, der Zylinder läuft unter dem Loch weiter; liegt er in mehreren, eine
Füllung mit dem Randdraht als Grenze und Stützpunkten auf der gemessenen
Fläche; sonst der Fächer. Hält das Nähen mit der fortgesetzten Fläche nicht,
gilt ebenfalls der Fächer. **Gemessen wird die Füllung an derselben
Nachbarschaft wie am Netz** (`edit._faces_near`: jede Fläche im Ring von
`MOUTH_REACH` um den Rand, fein vernetzt, ohne die des Hohlraums) — nicht nur
an den Flächen, an denen der Rand liegt: An `pegboard-gs-100-v2.step` sind das
die Flächen einer Mündungsrundung, und ihr Polynom lief als Trichter ins Loch
(Versetzen um 1 mm −7,8 statt −4,1 mm³). **Und der äußere Zylinder einer Kette ist beim Wiederfinden entlang der
Achse frei** (`_chain_mouths`): Wie weit er reicht, sagt die Fläche, in die er
mündet. Die exakten Kopien werden erst nach Lage und Maß zugeordnet und dann
benannt (`_exact_copy_result`); ein Fund, der zufällig den Namen einer Kopie
trägt, ist deshalb noch nicht diese Kopie. Kann der exakte Kern die Kette
nicht lesen, sagt die Kettenhandlung mit `CHAIN_NOT_READABLE` ab, nicht mit dem
Satz des Einlaufs.

**Und eine exakte Differenz gilt erst mit dichtem Zwilling**
(`_exact_chain_cut_holding`). OpenCASCADE scheitert lagenabhängig still: An der
Lochplatte gs-100 kam die Kette, 1,5 mm nach oben versetzt, mit dem Volumen des
gefüllten Körpers zurück, gültig laut `BRepCheck`, der Zwilling undicht. Dann
schneidet dasselbe Werkzeug mit doppeltem und dreifachem Mündungsüberstand
(`CUT_OVERLAPS`); hält keiner, sagt die Handlung mit `CUT_DID_NOT_HOLD` ab.
Versetzen, Verdoppeln, Kippen und das Muster einer Kette gehen diesen Weg —
**und eine einzelne Bohrung oder ein Langloch beim Versetzen und Verdoppeln
auch** (`_exact_rigid_cut`): Am Teppichclip kam das Langloch, entlang seiner
Richtung versetzt, mit undichtem Zwilling und bis 16 mm³ zu viel zurück, ohne
Befund. Ohne offene Mündung gibt es nichts zu verlängern, dann einmal.

**Versetzt und verdoppelt wird starr, an beiden Kernen** (RM-220). Eine
Bohrung ist danach so lang wie vorher; entlang ihrer Achse oder in dickeres
Material gesetzt, bleibt Material stehen, und `no_longer_through` sagt es
(entschieden am 03.09.2026). Der exakte Kern schnitt eine Durchgangsbohrung
über die ganze Zielhülle und blieb dort durchgehend; jetzt endet sie an ihren
alten Randebenen, um die Bewegung mitgenommen (`_exact_rigid_cut`).
**Ein Einrücken bis zur Facettengrenze ist Messrauschen**
(`_seated`): Die Mitte einer gekippten Bohrung lag bei z = 4,9576, und wer sie
auf 5 setzte, hätte eine Haut von 0,022 mm über der Mündung stehen lassen. Das
Netz folgt derselben Regel über den Kragen (`_past_the_mouths(travel=)`).
**Ein Langloch reist ganz, aus seinen Flächen** (Durchsicht 0.5.1): Fasen und
schräge Mündungen gehören zu ihm. Am Netz füllt `_closed_at` es mit dem
Körper aus seinen Flächen und `_tool_for` setzt ihn starr samt Kragen; am
exakten Kern `_exact_own_cavity` mit `_exact_own_filled` und
`_exact_own_cut` (Kragen `edit.collared`). Aus Kennzahlen schnitt es die
gemessene Tiefe um die Mitte und ließ am Wedge-Lock unter der schrägen
Unterseite Häute stehen. Gedreht und skaliert bleibt es bei den Kennzahlen;
wo die Flächen keinen Körper mit zwei ebenen Rändern hergeben, ebenso.
**Eine Tasche mit Haltelippe reist mit ihrer Luft** (BOHRUNG-13): Die Lippe
galt als Material im Zylinder, und jede Handlung sagte „keine Bohrung“. Steht
im Zylinder nur ein Rand an der Wand (`_only_a_rim_inside`, äußeres Viertel
des Radius), ist das Werkzeug die Hülle der erklärten Maße minus Körper
(`_air_of_the_bore`, exakt `_exact_air_of_the_bore`), samt Lippe; eine Nabe
oder ein Zapfen reicht weiter zur Achse und bleibt `HOLE_IS_NOT_EMPTY`. Das
Kriterium ist der Rand, nicht „Merkmal ohne Dreiecke“: Die Erkennung ordnet
einem Baustein-Merkmal Flächen zu (`declared_partners`) und führt die Lippe
dann als Kegel einer Kette, markiert als Verengung (`narrowing`). Eine
solche Kette (`_narrows_outward` liest dasselbe Flag über
`perceive.actions.narrows_the_mouth`) reist beim Versetzen, Verdoppeln, im
Muster und beim Entfernen am exakten Kern ganz aus ihren Flächen: gefüllt
(`_exact_own_chain_filled`) und geschnitten (`_exact_own_cut`). **Ändern geht
über ihr eigenes Einlaufprofil** (Durchsicht 0.5.1, rest-lippe;
`_narrowing_outline`): Der Schaft endet an ihrem Fuß, der Kegel läuft auf die
Öffnung — an beiden Kernen dieselben Zahlen, also dieselbe Tasche. Bis dahin
kannten die Profile nur den Kegel, der sich zur Mündung weitet; der Einlauf
sagte an der Lippe ab, und die Kerne schnitten *Nur Bohrungsdurchmesser*
verschieden. **Gekippt wird sie nicht** (`perceive.actions.narrowing_reason`,
Panel und Operation mit demselben Satz): Schräg zur Fläche schneidet die
Fläche die Lippe auf der hohen Seite weg, auf der tiefen führt die Öffnung als
Schacht bis zur Fläche — und das liest keine Erkennung wieder als Verengung.
Probeweise zugelassen rechnete jede folgende Handlung ohne die Lippe (am Netz
still weg, ein zweites Kippen Material in der Öffnung, am exakten Körper ein
undichter Körper). Wer das Kippen zulässt, bringt zuerst der Erkennung die
gekippte Lippe bei (Registersatz im Bericht rest-lippe). Die Kopie eines
Merkmals, das die Erkennung nicht sieht, wird nicht nachgemessen
(`_copies_found`).
**Und zwei Werkzeuge stoßen nie nur in einer Ebene aneinander, wenn sie am Netz
vereinigt werden** (rest-lippe): Manifold legt die beiden Deckel dann nicht
zusammen, sondern lässt sie stehen — nach dem Schnitt eine Haut ohne Dicke quer
durch den Hohlraum, die das Volumen nicht sieht (Magnettasche, *Nur
Bohrungsdurchmesser* auf Ø 8,1: 472 Dreiecke in der Fußebene der Lippe, die
Tasche eine gerundete Seite). Das hintere Werkzeug reicht in das vordere
hinein, wie der Kegel einer Senkung in ihren Schaft. Geprüft wird es nicht am
Volumen, sondern an Flächen in dieser Ebene und an der Erkennung danach.
**Eine Senkung auf ihrer Bohrung ändert ihr Maß über dieselben Profile**
(`_resize_chain_countersink`): Der exakte Kern streckte den Kegelstumpf aus
seinen Flächen um die Mündung und ließ enger eine Haut über der Bohrung
stehen, das Netz sagte ab. Was eine Operation an einem Kegel einer Kette
nicht kann, fragen Operation und Merkmalfenster an derselben Stelle
(`countersink_resize_refusal`).

**Versetzen und Verdoppeln fragen die Nachbarwand, an beiden Kernen**
(`_neighbour_bore_findings`, 25.09.2026) — Kippen und der Neuschnitt an neuer
Stelle taten es schon, *Merkmal versetzen* und *Merkmal verdoppeln* nicht:
Eine Bohrung Ø 6, 4,5 mm auf die Bohrung daneben zu versetzt, riss die
Trennwand auf, und kein Kern sagte etwas. Beim Verdoppeln ist die Vorlage
selbst eine Nachbarin, und jede zu dünne Wand zählt (`copy=True`), denn
vorher gab es keine. **Reißt die Wand auf, ist das der Nachbarbefund und nicht
dazu „über die Kante"** (`_without_opened_twice`, wie schon für
`bore.breaks_out`): Die Mündung der Nachbarin ist Luft, und die Kantenprüfung
hielt sie für die Außenkante. Abnahme:
`test_a_bore_moved_towards_its_neighbour_says_what_is_left_of_the_wall`,
`test_a_copy_set_beside_its_original_says_what_is_left_of_the_wall`.

**Und was das Schließen an der alten Stelle zurücklässt, wird zusammengelegt**
(`_without_scars`): Der Stopfen endet an der Hülle in den Deckelflächen, und
die Vereinigung ließ seine Kappen dort als Dreiecke in der Ebene stehen — je
Versetzen rund 270, 796 → 1042 → 1308 → 1576 → 1852 an der Lochplatte nach
vier Zügen, und jeder spätere Schritt rechnete mit. `Manifold.simplify` legt
sie zusammen, übernommen nur unter der Zusicherung von `boolean._tidied`:
dicht, gleiches Volumen, weniger Dreiecke; sonst bleibt die rohe Vereinigung.
**Beide Wege zur neuen Stelle tun es**, der mit Zahlen und der Klick ins Bild
(`_place_oriented_feature`): Dem Klickweg fehlte es bis zur Durchsicht 0.5.1,
und eine Senkbohrung aus 768 Dreiecken wuchs dort um 260 je Zug
(`test_a_chain_moved_by_hand_leaves_no_scars_in_the_face`).
Das Netz wird dabei neu nummeriert — **und eine Operation gibt nur Merkmale
ihres Ausgangsnetzes zurück** (`_without_old_triangles`): Was sie nur
weiterreicht, verliert Flächennummern und Teilträger, Ort und Maß bleiben; die
Oberfläche gibt die Auswertung an der neuen Erkennung zurück (`_with_features`,
„Der Name bleibt, die aktuelle Oberfläche geht mit"). Mit den alten Nummern
hielt `cavity_chain_state_at` eine unberührte Bohrung für unlesbar, und das
Verdoppeln nach dem Entfernen sagte ab. Dieselbe Regel gilt für den Wirt eines
Bausteins (`parts.ops._merged_features`).

Vier Dinge daran, alle gemessen:

* **An der neuen Stelle wird gebohrt, nicht geändert.** Dort ist volles
  Material; `resize_bore` verglich stattdessen die zwei Durchmesser, fand sie
  gleich und gab den Körper unverändert zurück — das Loch blieb, wo es war, und
  der Befund sagte „Die Bohrung hat bereits diesen Durchmesser".
* **Die Tiefe wird vor dem Verschließen abgelesen.** `feature.face_indices`
  zeigen danach auf fremde Dreiecke; dass der Fallback an der Prüfplatte
  denselben Wert trägt, macht die Reihenfolge nicht richtig.
* **Die Zuordnung sucht das Merkmal an seiner neuen Mitte.** Mit der alten
  meldete der Netz-Weg es als verloren und der exakte warf einen Programmfehler.
* **Beim Versetzen sagt das Volumen nichts.** Eine Bohrung, die ihre Stelle
  wechselt und ihr Maß behält, lässt genau so viel Material stehen wie vorher;
  `without_effect` las das als „hat nichts hinzugefügt". Dass etwas geschehen
  ist, steht anders fest: `moved_hole` ist erst wahr, wenn die Mitte wirklich
  wandert.

**Und das Maß bleibt das gemessene**, ohne Vieleckzugabe: Das Werkzeug an der
neuen Stelle ist der tatsächliche Wandmantel der Bohrung, und ein
eingeschriebenes 48-Eck, das ein zweites Mal als 48-Eck gesetzt wird, ist
dasselbe 48-Eck — Ø 5,20000 vor und nach vier Versetzungen (21.09.2026). Die
Zugabe von früher (siehe „Ein Vieleck aus einem gemessenen Durchmesser ist
enger als er") ist gefallen, mit ihr der Unterschied zwischen stehendem und
versetztem Weg. Am exakten Körper ist der Zylinder ohnehin ein Zylinder.

Der Toleranzbefund (`bore.compensated`) wird beim Versetzen **eigens**
angehängt — `drill` erzeugt ihn nur bei `compensate=True`, und der versetzte
Aufruf setzt `False`, weil `cut` sie schon trägt.

**Ein Langloch ist parametrisch.** Es steht seit dem 11.09.2026 in
`PARAMETRIC_KINDS`, und `_feature_solid` zieht seinen Umriss auf statt einen
Zylinder zu drehen. Ohne den Eintrag fiel `_tool_for` auf `_feature_body`,
bekam aus dem Flächenausschnitt keinen geschlossenen Körper und endete in der
Absage über Senkungen: Wer ein **vorhandenes** Langloch versetzen wollte, las
einen Satz über einen Fall, den es dort nicht gibt.

**Null Grad ist eine Richtung.** `slot_hole` übernimmt `slot_angle` auch bei
null; die Oberfläche belegt das Feld mit der gemessenen Richtung vor. Beim
Versetzen eines vorhandenen Langlochs wird dessen ganzer Umriss gefüllt.
Durchgehende Bohrungen erhalten im Änderungsweg eine Schneidtiefe über den
gesamten Zielkörper. Beim allgemeinen Versetzen und Duplizieren einer
Mesh-Bohrung entsteht das Werkzeug aus ihren tatsächlichen Wandflächen,
damit ein fremder Sehnenzug weder schrumpft noch beim Füllen zurückbleibt.

**Jeder schließende Weg verbindet vorher berührende Schalen** (RM-386). Am
Netz trägt jede schließende Vereinigung `merge_face_contacts`, am exakten Kern
füllt jeder Weg in den Körper aus `_exact_closing_base`; Ketten lesen ihren
Einlauf am verbundenen Körper (`_exact_closing_chain`,
`_exact_entrance_context`). RM-319 hatte das nur am Langlochzug eingelöst. An
zwei 40 x 20 x 10 mm großen Platten, die sich bei z = 10 berühren, verlor die
versetzte Senkbohrung (Ø 6, Senkung Ø 12) am Netz 2 516,3 mm³ und zerfiel in
zwei halbe Bohrungen; am exakten Kern ließ *Bohrung ändern* auf Ø 8 mit
Versatz einen losen Zylinder von 502,7 mm³ stehen, Versetzen und Kippen
sagten mit dem Rat ab, die Stelle anders zu setzen, und *Merkmal entfernen*
wie *Bohrung verschließen* gaben einen Körper mit undichtem Netz — alles ohne
Befund. Der Stopfen verband beide Platten über der alten Bohrung, ihre
gemeinsame Grenzfläche blieb im Körper, und der Schnitt danach traf sie.
Gemessen werden die Merkmale am unverbundenen Körper: Ihre Dreiecksbezüge
zeigen am verbundenen auf fremde Dreiecke. Die Vorfrage kostet am Netz mit
Flächenkontakt so viel wie ohne (Besenhalter, drei Schalen, 6,3 gegen 6,3 s je
schließender Vereinigung); am exakten Kern fällt sie nur bei mehreren
Volumenkörpern an. Der Wächter: `test_feature_moves_keep_shape.py`, beide
Kerne gegen die Platte aus einem Stück.

**Ein exakter Stopfen, der den Körper verliert, ist eine Absage** (RM-411,
04.10.2026). An einer Stufenplatte (9 326,282 mm³) mit einem Langlochende in
der Wand des Aufsatzes gab `BRepAlgoAPI_Fuse` aus Körper und Stopfen
(1 156,435 mm³, an der konvexen Hülle gekappt) einen gültigen, geschlossenen
Volumenkörper von 1 156,435 mm³ zurück — den Stopfen allein, ohne Fehler und
ohne Warnung; ohne Kappung kamen zwei Volumenkörper mit der Summe beider
Volumina zurück, verbunden war auch dort nichts. Der Zug danach ließ 431,5 mm³
stehen. `fill_bore` vergleicht deshalb am Zwilling: Füllen fügt
nur hinzu, und was über dem Sehnenfehler der Stopfenflächen fehlt
(`deflection` mal Stopfenfläche), sagt mit `FILL_DID_NOT_HOLD` ab
(`test_a_fill_that_loses_the_body_is_refused`). Ausgelöst hatte den Fall eine
falsche Erkennung (siehe „Ein Langloch ist an beiden Kernen ein Merkmal und ein
Hohlraum"); die Absage bleibt, weil sie zum Vertrag des Füllens gehört.

## Wulst und Kehle schließen je Kern anders, ein Gewinde wird nicht bewegt

**Und seit P2.6 gilt es für Wulst und Kehle** (21.09.2026): Ein Torusmerkmal
trägt dieselben fünf Handlungen, und das Werkzeug ist in beiden Kernen der
volle Ring aus den Kennzahlen (`brep.edit.torus`, `prepare_ops._torus_ring_mesh`)
— vereinigt der Wulst, abgezogen die Kehle. **Nur das Schließen an der alten
Stelle ist je Kern anders**, weil der volle Ring dem Schaft eine Rille
nähme: exakt streicht `brep.edit.defeatured` die Ringfläche, am Netz ist der
Wulst der Körper aus den eigenen Dreiecken der Ringfläche ohne den Schaftkern
zwischen den Randringen (`_torus_tool_mesh`). **Ein parametrisches Werkzeug
deckt sich nie mit einer vorhandenen Fläche des Netzes** — der erste Versuch
mit einem Netzring hinterließ 679 Splitter; wer am Netz etwas schließt,
nimmt die Dreiecke, die schon da sind. Ein Ring, der der ganze Körper ist,
sagt es (`TORUS_IS_THE_BODY`) statt zu raten; um seine eigene Achse gedreht
bleibt ein Ring, was er ist (Konzept §13.4), und ein quer gestellter Wulst
zerfällt in zwei Lappen — dann meldet `feature_lost`, dass die Kennung nicht
weiterlief.

**Und ein Gewinde wird geändert und verschlossen, nicht bewegt** (P2.6,
21.09.2026): *Merkmal ändern* setzt Durchmesser und Steigung mit dem
Bausteingewinde neu (`build.threaded`, außen Hülle weg und neu vereinigt,
innen gefüllt und neu geschnitten), *Merkmal entfernen* nimmt außen den Gang
bis auf den Kern und schließt innen die Bohrung — je Kern mit denselben
Werkzeugen. **Die Enden fragen die Nachbarschaft** (`_thread_span`): Hinter
Material endet ein eingesunkenes Bausteingewinde um `BOOLEAN_OVERLAP` früher
(sonst ein Ring von einem Hundertstel im Sockel), in der Luft reicht das
äußere Werkzeug hinaus und das innere nicht (sonst ein Zapfen an der Mündung,
die Lehre von `fill_bore`). Das neue Gewinde ist aus seinen Zahlen bekannt
und wird so benannt; die Erkennung sucht es an seiner Stelle und belegt den
Bezug (`_exact_features_after` mit `expected`), statt ihn zu behaupten — ein
behaupteter ließ daneben ein zweites Gewinde unter frischem Namen stehen.
**Innen nennt ein Merkmal die Gewindebezeichnung**, also den Grund-Ø der
Gänge (so schreibt es der Baustein, so lesen es beide Kerne); das Werkzeug
rechnet in der Bohrung darunter (`_tool_diameter`) — ohne die Umrechnung
wurde aus einer M6-Mutter beim Ändern der Steigung eine mit Bohrung Ø 6
(Review, 21.09.2026). **Ein erkanntes Gewinde am Netz misst sich an seinen
Ecken** (`_thread_corners`): Der Fit über Dreiecksmitten liegt radial
innerhalb der Kammecken und axial neben der Stange; auf den gemessenen Kamm
gesetzt blieben 51 Splitter, auf die gemessene Mitte eine Scheibe. Es
sperrt nur ein **belegtes** Linksgewinde (`types.thread_is_left_handed`:
gesetzt, nativ gelesen oder am Netz an den Kanten gemessen — nicht die
Schätzung des Spektrums, `fit`), und ein mehrgängiges sagt ab, statt still
eingängig zu werden. Linksgängig, mehrgängig, eine Steigung ohne Kern und ein Gewinde
ohne Strecke sind Absagen mit Vorschlag. Und ein Feld, das nur eine
Merkmalsart trägt — Rohrdicke, Steigung — steht nur an ihr
(`actions._carried_by`): „Steigung 0 mm“ an einem Zapfen ist eine Frage
ohne Gegenstand.

## Gemeldet wird, was am Ergebnis steht

**Und eine Mündung, die an der neuen Stelle unter Material liegt, wird
gemeldet** (`_mouth_covered`, `{op}.mouth_covered`): Eine Sackbohrung hat keinen
Durchgang, den sie verlieren könnte, und schwieg — an einer schrägen
Außenfläche um 3 mm quer versetzt lag die Senkung unter 0,24 mm Material.
Zugedeckt heißt: vor mindestens der Hälfte des Rands Material
(`COVERED_SHARE`) — eine einzelne Kantenprobe antwortet mit dem Vorzeichen der
falschen Fläche. Am exakten Körper fragt `_exact_through_checked` zusätzlich
die Säule im Schlauch, um die Facettengrenze schlanker: Die Erkennung nennt
eine Bohrung in eine vergrabene Senkung durchgehend. **Und die Säule liegt im
Werkzeug** (`_inscribed_radius`): Versetzt wird das Vieleck der Datei, und eine
Säule 0,02 mm unter dem Durchmesser traf an einem 32-Eck jede Sehne — „geht
nicht mehr durch" an einer glatt versetzten Bohrung einer Furnierplatte.
**Und der einzelne Hohlraum fragt dieselbe Säule** (RM-411, 04.10.2026): Nur
die Kette rief `_exact_through_checked`, `_exact_move_cavity` und
`_exact_duplicate_cavity` nicht. An der schrägen Platte (z = 10 + x/4) blieb ein
Langloch, 2 mm längs der Schräge versetzt, unter der mitgenommenen Randebene
hinter einer Haut von 0,5 mm; das Netz sagte „geht nicht mehr durch“, der exakte
Kern „Mündung zugedeckt“ und nannte das Langloch weiter durchgehend — quer
versetzt und verdoppelt ebenso. Eine Bohrung traf das nicht, ihre Erkennung
misst den Durchgang selbst
(`test_a_slot_set_up_a_slanted_plate_says_the_same_on_both_kernels`).

**Gemeldet wird, was am Ergebnis steht** (`_measured_on`). Der exakte Kern
erkennt nach jeder Merkmalshandlung neu; das Netz trug beim Versetzen, Kippen
und Verdoppeln die alten Maße weiter — eine Senkung, 1 mm entlang ihrer Achse
nach außen versetzt, stand als Ø 8,8 vor der Fläche, am Körper mit Ø 6,8 in
ihr. Gesucht wird wie am exakten Körper (`_bore_match_id`, `_same_cone`); der
Öffnungswinkel eines Kegels am Netz trägt dabei den Facettenfehler
(`FACETED_CONE_ANGLE`, 89,80° statt 90°). Wo die Wand das gesetzte Maß trägt,
bleibt es (`_with_nominal_bore`). **Ein Durchgang, der nicht mehr durchgeht,
bleibt derselbe** (`_free_along_the_axis`): Er kommt als Sackloch zurück, und
der exakte Kern hielt ihn für verloren, solange die Mitte entlang der Achse
nicht frei war.

**Eine Kopie, die es nicht gibt, sagen beide Kerne** (RM-249). Der exakte
erkennt nach dem Schnitt neu und meldet, was er nicht wiederfindet
(`_exact_copy_result`); das Netz misst seine Kopien nach (`_copies_found`)
und tut dasselbe — beim Verdoppeln einzeln und als Kette und im Muster.
Wiedergefunden heißt: seitlich auf der Achse, auf die sie gesetzt wurde, bis
zur Facettengrenze. Die Messung am Netz nimmt sonst auch einen
angeschnittenen Zylinder über einer Seite als Bohrung, mit seiner Mitte bis
1,25 mm daneben, und die Auswertung verwarf ihn danach still. **Und neu**
(RM-226, Nachtrag 04.10.2026): Eine Durchgangsbohrung darf entlang ihrer
Achse wandern, und längs dieser Achse verdoppelt liegt die Vorlage auf ihr.
An `pegboard-gs-100-v2` fiel die 12 mm verschobene Kette in einen Durchbruch,
nichts wurde abgetragen; der exakte Kern nannte alle drei Kopien verloren, das
Netz zwei — die Kopie der Bohrung Ø 6 fand es in der Vorlage, deren Dreiecke
danach den Namen der Kopie trugen. Die Ketten waren an beiden Kernen gleich.
Der exakte Kern nimmt nur Merkmale mit neuem Namen; am Netz ist kein Fund eine
Kopie, der in Art, Mitte und Durchmesser bis zur Facettengrenze auf einem
Merkmal der Quelle liegt (`_already_there`) — ohne Freiheit entlang der Achse,
damit eine Kopie in eine zweite Wand Kandidat bleibt
(`test_a_copy_along_its_own_axis_into_the_air_is_lost_on_both_kernels`, vorher
am Netz alle sechs Fälle rot). **Und eine Senkung findet sich an beiden Kernen
über ihre Spitze wieder** (`_same_cone`): Mitte und Durchmesser beschreiben
ihren weitesten Rand, und den schneidet an der neuen Stelle eine Seite ab. Eine
Senkbohrung, 25 mm längs der schrägen Platte über die Stirn verdoppelt oder
vervielfacht, maß dort Ø 12,54 bei z = 11,27 statt 13,33 bei 11,67; das Netz
fand sie über die Spitze, der exakte Kern suchte an der Mitte und nannte sie
verloren (`test_a_buried_sink_reaching_past_the_end_is_over_the_edge_on_both_kernels`,
ohne die Spitzensuche in `_exact_copy_result` acht von zwölf Fällen rot).

**Und eine Bohrung, in deren Zylinder Material steht, ist keine** —
`hole_is_clear` fragt die Dreiecksmitten des Körpers zwischen den Mündungen
und innerhalb des Radius, abzüglich der eigenen Wand. Die Innenwand eines
Rades mit Speichen, ein Becher mit Stegen, ein Topf mit Zapfen: Ihr Werkzeug
wäre der volle Zylinder aus den Kennzahlen, und der nähme die Speichen mit
(Uhrenteil 06: minus 49 Prozent, Zahnräder des Kartenmischers: minus 62
Prozent, 15.09.2026). `_tool_for` sagt mit `HOLE_IS_NOT_EMPTY` ab, und das
Panel stellt an so einer Bohrung jede Zeile grau — nicht nach einer Stichprobe
von Punkten, die zwischen zwölf Stegen hindurchsah, sondern nach jeder
Oberfläche im Zylinder. Und ob man durch eine Bohrung **hindurchsieht**,
entscheidet ihre ganze Mündung, nicht ihre Achse: Über der Achse des Bechers
Ø 116 lag kein Dreieck, weil im Boden eine Bohrung Ø 8 sitzt (`_is_through`,
`THROUGH_RINGS`). **Und die Antwort wird je Körper und Bohrung einmal
gerechnet** (`features.remembered`, wie `relations.cavity_surface_indices`):
Das Merkmalfenster fragt sie bei jedem Klick zweimal, und an der Lochplatte
mit 360 000 Dreiecken kostete jede Antwort 90 ms, weil die Endebenen dafür
eine Kopie des Netzes verschweißen — der Bohrungsklick 258 → 83 ms
(22.09.2026). Der Merker stirbt mit dem Körper.

**Gehört das Material einem anderen Teil, sagt es ein eigener Satz**
(`OTHER_PART_IN_THE_BORE`, RM-413/RM-253, 06.10.2026). Das Menü stellte die
Zeilen schon grau, die Operationen rechneten aber: Am Netz galt ein Stift Ø 5
in einer Bohrung Ø 6 als Haltelippe (`_only_a_rim_inside`), der exakte Weg
fragte gar nicht, und *Versetzen*, *Verschließen*, *Entfernen* und *Kippen*
füllten die alte Stelle und verschmolzen den Stift still mit der Platte
(ein Körper statt zwei; *Bohrung ändern* schnitt ihn ab oder ließ einen losen
Ring stehen). Am Laptop-Ständer trug `hole_3` seinen Mantel auf zwei Platten
mit einem Zapfen darin; *Versetzen* verschmolz die Platten, der Zapfen
verschwand im Stopfen, 531 mm³ ohne Befund. Eigen sind deshalb alle Teile, die
den Mantel tragen (`_own_part_bore_clear`), und `_movable_feature` sowie
*Bohrung ändern* sagen ab, mit *In Einzelteile aufteilen* als Weg. „Sie ist eine
Wand, keine Bohrung“ war dort auch als Satz falsch. Allein *Zum Langloch
ziehen* schneidet ein belegt freies Teil darin mit; die Kontakt- und
Materialfrage dafür gilt dem Träger und den Teilen, deren Hüllquader seinen
berühren (`_near_the_carrier`) — zwei Würfel, die sich weit daneben
berühren, sperrten vorher den Zug (Review `e3dff1907`, F10). Wer über eine
Kette fremder Teile am Träger hängt, berührt ihn mit dem letzten Glied und
sperrt weiter.

**Ein Dreieck zählt mit dem Stück, das zwischen den Mündungen liegt, nicht
mit seiner Mitte** (`_reaching_in`, RM-253, 09.10.2026). Am Laptop-Ständer
steckt in vier Plattenbohrungen Ø 5,33 eine geschlitzte Hülse von 43 mm; jedes
ihrer Manteldreiecke läuft über die ganze Länge, und alle Mitten lagen 9 bis
23 mm vor der Bohrungsmitte, hinter den Mündungen bei ±4,93 mm. Ebenso stecken
Schraubenschäfte mit Streifen von 8 mm in Scheiben von 0,9 mm. Neun von 28
Bohrungen galten so als frei: *Versetzen* und *Drehen* rechneten durch die
Hülse (−127 mm³, „geht nicht mehr durch“, um y gedreht 84 statt 22 Teile),
*Bohrung ändern* auf ein kleineres Maß nahm Material weg, und das Kippen von
`hole_11` schnitt die Schraube. Gemessen wird jetzt das Stück zwischen den
Grenzen, quer zur Achse projiziert, an seinem kleinsten Achsabstand — das fängt
auch den Querstift, dessen Mitten neben der Bohrung liegen. Grenze ist die
eigene Wand, mit derselben Rechnung gemessen: Ein grobes Vieleck liegt mit
seinen Seitenmitten innerhalb des Radius, und die Wand einer Querbohrung endet
auf der Bohrungswand (Gegenfall `test_a_cross_bore_alone_leaves_the_bore_free`).
Die Dreiecksmitten bleiben die erste Frage; die zweite fügt nur hinzu.

**Und was für eine runde Bohrung an ihrer Mitte gefragt wird, wird an einem
Langloch an beiden Enden gefragt** (`prepare.slot_ends`). Die Mitte steckt tief
im Material, während ein Ende schon über die Kante ragt; wer nur sie fragt,
schweigt zu einer aufgerissenen Flanke. Gemeldet wird trotzdem höchstens
einmal — zwei gleichlautende Sätze über dasselbe Loch sagen nichts Zweites.
**An beiden Kernen:** Der exakte Zweig von `slot_hole` stellte die Frage bis
zum 11.09.2026 als einziger nicht — eine Bohrung neun Millimeter vor der
Kante, auf 20 gezogen, meldete am Netz `bore.over_the_edge` und am exakten
Körper nichts (Fund des Reviews). **Und an allen Wegen, die eine Bohrung
neu setzen:** *Versetzen* und *Verdoppeln* schwiegen bis zum 15.09.2026 — die
Fahne eines Minigolf-Satzes gewann beim Versetzen um 2 mm 8,5 Prozent
Volumen, weil der Pfropfen die ganze Bohrung füllte und das Messer nur noch
teilweise traf. `prepare_ops._edge_findings` fragt je Abschnitt des gesetzten
Hohlraums am gefüllten Körper vor dem Schnitt — an der neuen Mitte, an den
beiden Enden eines Langlochs und an den **Austritten** der Achse aus dem
Körper — und meldet höchstens einmal. Der Austritt ist der erste Durchstoß
der Achse durch die Oberfläche, höchstens der Rand des Hüllquaders
(`_axis_exits`, RM-220): Am Quader gefragt, lag er über jedem Vorsprung, auf
einer Rippe oder in den Waben des Schraubenhalters, und deren Kante meldete
„über die Kante". Eine Senkung mündet nur an ihrem weiten Ende; am engen fragt
die Bohrung mit ihrem eigenen Durchmesser. Angeschlossen sind alle sechs Wege:
Versetzen und Verdoppeln einzeln, als Kette und frei platziert mit Normale,
Drehen einzeln und als Kette, und Ändern (das Review fand die letzten drei
stumm). An einem Austritt fragt `prepare.mouth_over_the_edge` nur den halben
Radius hinter der Mündung: Eine um 60° gedrehte Bohrung steckt in der Mitte
tief im Material und reißt 2,3 mm hinter ihrem unteren Austritt trotzdem auf
— über die ganze Länge gefragt, wie `_flank_is_open` es tut, hieße das
geschlossen (`test_moving_or_duplicating_a_bore_over_the_edge_says_so`,
`test_every_way_that_sets_a_bore_anew_asks_about_the_edge`,
`test_a_widened_countersink_over_the_edge_says_so`).

**Eine starr gesetzte Senkung unter einer Haut ragt nicht über die Kante**
(RM-226, Nachtrag 04.10.2026). Am Austritt setzt `mouth_over_the_edge` den
Kegel von der Spitze bis in die Fläche fort; liegt das weite Ende darunter,
wächst der Kranz mit jedem Millimeter Haut. Eine Senkbohrung, 20 mm längs der
60 mm langen schrägen Platte verdoppelt, versetzt oder als dritter Platz eines
Musters, endet 5 mm unter der Oberseite mit dem weiten Ende bei x = 26,7; ihr
gedachter Kranz reichte bis x = 33,3 über die Stirn bei x = 30, und beide Kerne
sagten „über die Kante“. Jetzt fragt `_sink_under_a_skin` vorher, ob der Kreis
des weiten Endes ringsum mindestens eine Facettengrenze unter der nächsten
Fläche liegt (`prepare.ring_in_material`). Die Tiefe zählt: Der Kreis einer
bündigen Senkung liegt in ihrer Mündungsfläche, ein Punkt neben der Kante hat
dort zur Deckfläche den Abstand null längs ihrer Normale, und die über die
Kante versetzte Senkung schwieg
(`test_a_moved_countersink_over_the_edge_is_reported_once`). Und nur starr
(`rigid`): Gekippt schneidet ein größerer Kegel bis zur alten Randebene, über
den Kreis hinaus — die vergrabene Senkung der Rippenplatte läuft so aus der
Seite. Plansenkung und Langloch fragen mit ihrem eigenen Durchmesser und
meldeten an derselben Stelle nichts; reicht der Kreis seitlich hinaus (24 mm
statt 20), bleibt es an beiden Kernen bei „über die Kante“
(`test_a_copy_under_the_top_is_not_over_the_edge_on_both_kernels`,
`test_a_buried_sink_reaching_past_the_end_is_over_the_edge_on_both_kernels`).

**Den Zerfall zählt derselbe Weg gegen den Körper vor dem Schritt**
(30.09.2026). `drill`, `slot_bore` und `resize_bore` zählen die Teile gegen den
Körper, den sie bekommen, und nach dem Schließen der alten Öffnung ist das der
gestopfte. Der Stopfen verbindet aber, was durch die Öffnung geht: Die
vernetzte Teppichecke (zwei Körper im STEP) war beim Drehen ihres Langlochs
gestopft ein Stück, der Besenhalter (drei Schalen im STL) beim ersten Zug zwei,
und nach dem Schnitt hatten beide wieder 2 und 3 Teile — darüber stand „Die
Bohrung schneidet den Körper ganz durch — er zerfällt in mehrere Teile". Am
Besenhalter traf das jeden Zug an den sechs Bohrungen Ø 6,12; gegen den Körper
vor dem Schritt gezählt bleibt bei 7,12 mm nichts, bei 12,24 mm nur in einer
von vier Richtungen ein echtes loses Stück von 66 mm³. Der exakte Zweig von
`slot_hole` zählte schon gegen den Schritt davor;
`prepare_ops._split_counted_from` tut es jetzt am Netz, für *Zum Langloch
ziehen* und *Bohrung ändern*
(`test_a_second_body_in_the_bore_does_not_make_the_pull_a_split`,
`test_widening_a_slot_with_a_second_body_in_it_is_no_split`, Gegenrichtung
`test_a_pull_through_the_plate_beside_a_second_body_still_says_it_splits`).

**Gefüllt und über die Länge des Schnitts, an beiden Kernen** (RM-411,
04.10.2026). Der exakte Zweig von *Zum Langloch ziehen* fragte die Kante am
Körper vor dem Füllen und nur über die halbe Bohrungstiefe, das Netz am
gefüllten über die halbe Schnitttiefe. An einer schrägen Platte (Oberseite
z = 10 + x/4, Bohrung Ø 6, Zug auf 16 mm ganz in der Fläche) sahen Punkte in
der alten Bohrung unter der tiefen Seite der Mündung hindurch ins Freie: exakt
„über die Kante", am Netz nichts. An einer Stufenplatte, deren Langlochende
1 mm in die Wand eines Aufsatzes läuft, sah der Kranz über die Bohrungstiefe
nur die Grundplatte: am Netz „über die Kante" und `feature_lost`, exakt nur
die Umbenennung. *Bohrung ändern* fragte exakt ebenfalls ungefüllt
(Verbreitern auf Ø 8 an der schrägen Platte: exakt „über die Kante", Netz
nichts). **Eine alte Öffnung, die ein Zug ohne Schließen überdeckt, zählt als
Material** (`prepare.OpeningSpace`): Wer ein Langloch an derselben Stelle
verlängert, schließt es nicht, und seine Luft lag im inneren Halbkranz der
neuen Enden — an der schrägen Platte sagten beide Kerne „über die Kante". Den
inneren Halbkranz wegzulassen genügt nicht: Läuft ein Ende genau in eine
Stufenwand, liegt der Riss dort
(`test_both_kernels_report_the_same_at_a_slanted_and_a_stepped_carrier`,
`test_a_slot_changed_inside_a_slanted_plate_is_not_over_the_edge`; Gegenproben:
ungefüllt sind die schrägen Fälle rot, mit der Bohrungstiefe die sechs
gestuften, ohne gefüllten Körper beim Ändern das Verbreitern).

## Ein Winkel gilt dem Rahmen, den er bekommt

**Der Winkel zählt gegen den Rahmen, den er bekommt — und die zwei Wege
bekommen verschiedene.** `drill_hole` baut ihn aus der Normalen der
angeklickten **Fläche**, `slot_hole` aus der Achse des erkannten Merkmals, und
die normiert die Erkennung auf „größte Komponente positiv". `frame_of` spiegelt
seine erste Achse mit der Normalen; gemessen an derselben Platte ergeben
45 Grad von oben gebohrt 45 Grad, von unten gebohrt 135, an der erkannten
Bohrung beide Male 45. **Das bleibt so**: Eine erkannte Bohrung hat zwei
Mündungen, und welche gemeint ist, hat niemand gesagt (Regel 21). Wer eine
Zahl von einem Weg auf den anderen überträgt, überträgt sie nicht.

**Und „die Erkennung" heißt beide Kerne** (11.09.2026). Bis dahin normierte
nur `fit_cylinder` am Netz; der exakte Kern gab die Achse so zurück, wie
OpenCASCADE die Fläche gebaut hatte — eine Bohrung von unten trug dort minus
Z, und ein Langloch nach *Zum Langloch ziehen* die Gegenrichtung seiner
Bohrung. Gemessen: 45 Grad an derselben Bohrung von unten ergaben am Netz 45
und am exakten Körper 135; und nach einem Zug mit 45 zeigte das Feld
*Richtung* am exakten Körper minus 45, ein zweiter Zug mit derselben 45
schnitt ein Kreuz. `units.positive_axis` trifft die Wahl jetzt einmal, für
die Achse **und** für die Richtung eines Langlochs, an beiden Kernen (Fund
des Reviews). Was daran hängt, darf das Vorzeichen deshalb **nicht** als
Auskunft lesen: `placement.seat_of` fragt beide Mündungen, denn die Achse
sagt nicht, an welchem Ende die Öffnung liegt — ein Sackloch von unten hatte
mit ihr keine Trägerfläche und kein Maß im Bild.

**Und eine gemessene Achse neben einer Hauptachse bekommt deren Rahmen**
(30.09.2026). `frame_of` nimmt das Kreuzprodukt aus Z und der Achse als erste
Rahmenachse und die Weltachse erst unter `PLANE_PARALLEL` (1e-9); eine am Netz
eingepasste Bohrungsachse liegt nie so genau. An der vernetzten Teppichecke
stand sie 0,024°, 0,028° und 0,071° neben Z (Feinheit 0,01, 0,02, 0,05), und
das Feld *Richtung* zeigte für dasselbe Langloch, in der Welt 90°, -168,5°,
132,0° und 91,8°, exakt 90°. Ein bei 0,01 vorbelegter Zug drehte nach einer
geänderten Feinheit um rund 100°, ragte über die Kante, zerteilte das Teil und
verlor das Merkmal; ein getippter Winkel 90 tat dasselbe schon beim ersten
Mal. Am Besenhalter lagen sechs Bohrungen 3e-6° neben Z, und Winkel 0 zeigte
auf 53,1° bis 126,9°. `prepare.slot_frame` gibt innerhalb `SLOT_FRAME_CONE`
(bis RM-325 hieß der Kegel wie die Drehschwelle `SLOT_ACROSS_LIMIT`)
den Rahmen der Hauptachse, gegen die gemessene Achse gestellt; eine genau
liegende oder wirklich geneigte Achse behält `frame_of`. Danach, am selben
Lauf: Feld 90,000°, 90,000°, 90,000° und 89,982° (Spanne 0,018°), der Zug
behält nach geänderter Feinheit Richtung, Länge und Merkmal, der getippte
Winkel schneidet an beiden Kernen 90°, und Winkel 0 zeigt an allen sechs
Bohrungen auf 0°. `plane_axes` bleibt, wie es ist: Eine Skizzenebene hat
keine gemessene Achse. Gespeicherte Winkel rechnet die Migration 38 → 39 in
den neuen Rahmen um — dieselbe Richtung, die der Kunde gesehen und gedruckt
hat (`slot_angle_from_measured_frame`; bei *Zum Langloch ziehen* einmal in der
Auswertung über `measured_frame`, weil die Achse erst dort feststeht).

## Die Werkzeugzugabe steht einmal, und ein Langloch bekommt sie nie

**Und die Zugabe, die einen Werkzeugkörper vom gemessenen Maß fernhält, steht
einmal** — `prepare.FEATURE_OVERLAP`. Sie stand am 10.09.2026 zweimal da, mit
demselben Wert und dem Vermerk „dieselbe Zahl, derselbe Grund"; genau diese
Form hat `BOOLEAN_OVERLAP` schon einmal gekostet. Ihr Grund ist außerdem nicht
mehr die Koplanarität — die rechnet `manifold3d` robust, gemessen 27.08.2026,
**an exakt koplanarer float64-Geometrie** —, sondern der **Tangentialkontakt**:
Ein Langlochkörper ohne Zugabe legte sich entlang zweier Linien an die alte
Bohrungswand.

**Und ein Langloch bekommt sie nie** (seit 23.09.2026; vorher „nur beim
ersten Zug", 11.09.2026). Mit der Zugabe wurde das Loch bei jedem Zug
breiter — am Netz 5,2057, 5,2213, 5,2371 an einer Bohrung von 5,1901 —, und
beim ersten Zug kam es um genau sie zu breit und zu lang heraus: 5,02 x 20,02,
wo *Bohrung setzen* mit dem Haken *Langloch* 5,00 x 20,00 schneidet. Zwei Wege
zum selben Auftrag, zwei Maße. `slot_hole` schließt deshalb auch die **runde**
Bohrung vor dem ersten Zug (`closes_the_old`) und schneidet aus vollem
Material ohne Zugabe (`overlap=0.0`) — die Wand, von der die Zugabe fernhielt,
gibt es dann nicht mehr. Beide Wege und beide Kerne schneiden dasselbe
Langloch (`test_slot_features.test_both_ways_to_a_slot_cut_the_same_slot`).

## Ein Füllkörper hat die Form des Werkzeugs, nicht die des Hohlraums

Einen Hohlraum zu schließen heißt nicht, ihn nachzubauen. Ein Körper, der die
Kegelwand einer Senkung nachbildet, endet **auf** ihr, und die Vereinigung
lässt dort zwei Flächen nebeneinander stehen statt einer: Im Objektbaum standen
danach zwei Senkungen (Ø 10,34 und Ø 10,36), und der Oberseite fehlte weiterhin
das Stück, das der Trichter aus ihr geschnitten hatte (Robert, 10.09.2026).

Was trägt, ist die Bauart, die `_closed_at` für jede Bohrung geht: ein Körper,
der **überall breiter** ist als der Hohlraum, dessen Mantelfläche also im
vollen Material liegt, mit Zugabe an den Enden und danach an der Körpergrenze
gekappt. Übrig bleibt genau eine ebene Fläche.

**Und die Gegenrichtung dazu:** Was nach dem Füllen wieder ausgeschnitten wird,
ist exakt das Merkmal — dort ist jede Zugabe ein Maßfehler. Ein Durchgang mit
der üblichen Werkzeugzugabe war 0,02 mm weiter als die Bohrung darunter, und
der Baum zeigte danach zwei Bohrungen übereinander.

## Ein Vieleck aus einem gemessenen Durchmesser ist enger als er

`trimesh.creation.cylinder` baut ein **eingeschriebenes** Vieleck: Der
angegebene Durchmesser ist sein Umkreis, seine Flanken liegen um
`cos(π/sections)` weiter innen. Wer aus einem **gemessenen** Maß ein Werkzeug
baut, das dieses Maß wiederherstellen soll, verliert deshalb bei jedem Zyklus
ein Stück: gemessen 7,9848 vor dem Zug, 7,9696 danach, also 0,015 mm je
Durchgang. Eine Zugabe dagegen (`_polygon_gain`) war die
zweite Näherung über der ersten. Was heute trägt: Eine wiederhergestellte
Bohrung oder ein Langloch nimmt das **gemessene Konturmaß** ohne
Vieleckkorrektur, und `_tool_for` schneidet mit dem tatsächlichen Wandmantel
der Bohrung an seinen Randringen; `_placing_tool` trennt das maßhaltige
Setzen vom vergrößerten Werkzeug zum Schließen. Nur ein Werkzeug, das die
Kontur wirklich **umschreiben** muss — der Stopfen in `_closed_at` —, bekommt
die geometrisch nötige Sehnenzugabe (`units.inscribed_ratio`). Nachgemessen
am 21.09.2026: Ø 5,20000 hält über vier Versetzungen der Lochplatte.

Dass der Verlust lange nicht auffiel, hat einen Grund, und der ist Zufall: Die
Zugabe aus §39 (`FEATURE_OVERLAP`, 0,02 mm) hat bei den üblichen Durchmessern
dieselbe Größenordnung wie der Vieleckverlust und deckt ihn zu. Wer sie
weglässt — weil sein Werkzeug exakt sein muss —, verliert diese Deckung mit.

## Toleranzen sind Durchmessermaße

`clearance` und `press` aus dem Materialprofil gelten **im Durchmesser**, wie
überall im Haus: Ein Passstift bekommt seine Bohrung als `diameter + play`
(`knowledge/parts/mechanics.py`), und die Passungsprüfung rechnet
`hole_diameter - pin_diameter` (`scene/fits.py`). Wer eine Kontur radial
einzieht, nimmt die Hälfte.

Der Deckelkragen tat es nicht und bekam damit das doppelte Spiel — die Passung
des Beispiels „Dose mit Deckel" meldete bei jedem Öffnen 0,90 mm statt
0,25 mm. Daneben stand `COLLAR_RELIEF = 0.2`, „damit der Deckel nicht auf dem
Kragen sitzt": eine Zahlenkonstante für eine Toleranz, also ein Verstoß gegen
Regel 7 im Gewand einer Fertigungszugabe. Sie untergrub die Kalibrierung
(§28.3) — wer sein Material misst und 0,15 mm einträgt, bekam trotzdem 0,55 mm
je Seite. **Dass etwas nicht klemmt, ist die Aufgabe des Gleitspiels aus dem
Profil**; dafür ist es da, und dafür wird es gemessen.

*Stift für Bohrung* mit Senkkopf (RM-536) zeigt, warum die Hälfte senkrecht zur
Wand gilt und nicht im Halbmesser: Eine Mündung „Senkung minus Spiel“ mit dem
Winkel der Senkung ließe an einer 90°-Flanke nur `Spiel/2 · cos 45°` Luft, an
`plate_countersunk.stl` mit PETG 0,088 statt 0,125 mm. Die Flanke rückt deshalb
um `Spiel/2` senkrecht zu sich ein, die Mündung wird um `Spiel · √2` enger. Das
Gewinde darin stand nach dem Bau zunächst auf seinem Absatz: An der Achse ist
unter einem gedruckten M6 in Ø 5,2 Luft, der Kamm des Bolzens saß aber auf dem
Ring, an dem die Gänge der Bohrung enden — Abstand null, ohne gemeinsames
Volumen. Seither fragt das Ende des Gewindes die Weite dahinter
(`bore_pin.room_beyond`). Die Lage der Gänge wird an den Ecken des Trägers
gemessen (`bore_pin.thread_turn`): Ein um 100° gedrehter Träger ließ den
ungedrehten Bolzen über 1 mm³ in seinen Gängen stehen.

## Ein Langloch in neuer Richtung ist ein gedrehtes Langloch

Nicht ein zweites quer über dem ersten. Bis zum 15.09.2026 schnitt `slot_hole`
mit einem anderen Winkel ein Kreuz und **warnte** davor (`slot_hole.crosses`);
Robert: „habe ich 2 langlöcher". Eine Warnung ist keine Antwort auf eine Geste,
die etwas anderes verspricht — der Ring am Griff dreht das Loch, also dreht
die Operation es: alte Öffnung schließen, neue schneiden, derselbe Weg wie beim
Versetzen. Was bleibt, ist die Auskunft (`slot_hole.turned`, info). **Wer eine
Operation baut, die eine Geste einlöst, baut die Wirkung, nicht den Hinweis auf
die andere.**

Dasselbe gilt für eine kürzere Länge: `slot_hole` schließt den alten Umriss,
bevor es den kürzeren schneidet. Ein kleineres Werkzeug allein trägt an den
alten Enden nichts auf. Griff, Felder und Operation erlauben die Länge in
beiden Richtungen bis `prepare.shortest_slot` für die gewünschte Breite —
**und genau die Breite selbst**: Dann schneidet `slot_hole` wieder eine
runde Bohrung (Entscheidung Robert, 24.09.2026). Die Frage „ist das rund"
beantwortet `prepare.is_round_length` für alle — Griff, Felder,
Vorschauwerkzeug, beide Kerne —, auf die halbe Anzeigestufe genau und gegen
die eingetragene wie die geschnittene Breite. Dazwischen bleibt es eine
Absage, die beide Auswege nennt (`NEITHER_ROUND_NOR_SLOT`). Aus einem
Langloch wird dabei eine Bohrung mit neuem Namen (`slot_hole.round_again`);
eine runde Bohrung auf ihre eigene Breite gezogen bleibt unangetastet und
sagt es (`slot_hole.already_round`), statt dasselbe Loch zu füllen und neu
zu schneiden.

`prepare.shortest_slot(diameter)` beantwortet, ab wann ein Langloch eines ist —
und diese eine Funktion fragen alle: die Prüfung in `slot_travel`, die Prüfung
in `slot_hole`, der Haken im Bohrdialog und der Griff im Bild
(`ui.slot_handle`, `ui.viewport`).

**Vorher waren es zwei Grenzen.** Der Kern verlangte „länger als der
Durchmesser", der Griff rastete bei `1.05` mal Durchmesser, und dazwischen lag
ein Streifen, in dem die Merkmalserkennung das Ergebnis nicht mehr hält: Bis
rund **fünf Prozent** Weg passt ein Zylinder auf den Mantel, und das Merkmal
heißt danach **Bohrung**; knapp darüber passt weder Zylinder noch Bogenpaar,
und dann steht **gar kein** Merkmal mehr da — kein Eintrag im Objektbaum, keine
Maße im Bild, nichts zum Anklicken (Robert: „es gibt noch Fälle, wo das
Langloch keine Maße im Viewport hat, nicht wählbar ist, im Objektbaum
verschwindet").

Die Zahl kommt aus einem Raster über Ø 2 bis Ø 40 in beiden Qualitätsstufen:
Ø 5 kippt bei 0,25 mm Weg, Ø 12 bei 0,55, Ø 20 bei 1,0, Ø 40 bei 1,8 — überall
rund fünf Prozent des Durchmessers. Gewählt ist das **Doppelte**, mit drei
Zehntel Millimetern als Untergrenze für kleine Löcher. Nicht das Dreifache:
Das nähme einem Langloch Ø 40 sechs Millimeter Verschiebeweg ab, und der
Verschiebeweg ist der Grund, aus dem es Langlöcher gibt.

**Gefragt wird gegen den gemessenen Durchmesser**, nicht gegen den
eingetragenen. Gegen ihn misst auch die Erkennung, und die Materialtoleranz
liegt dazwischen.

## Ein Langloch trägt keine Aufweitung, und seine Länge ist nicht sein Weg

Zwei Entscheidungen zum Langloch, beide vom 10.09.2026, beide leicht in die
falsche Richtung zu drehen.

**Kein Langloch mit Senkung** (Entscheidung Robert). Eine Senkung über einem
Langloch wäre entweder rund — dann säße ein Schraubenkopf nur in dessen Mitte
versenkt — oder selbst ein Langloch, und dann bliebe offen, welche der beiden
Längen der Kunde meint. Solange die Frage nicht gestellt ist, wird sie nicht
geraten (Regel 21). Der Dialog graut alle drei Aufweitungsfelder aus
(`depends_on=("slotted", (False,))`), `prepare_ops.bore_shape` nullt für Chat
und Kommandozeile die beiden **Maße**, und `prepare.slot_travel` weist sie ab,
wenn sie doch zusammen ankommen. Drei Ebenen für eine Entscheidung: Der Dialog
ist kein Vertrag, und der Kern ist keine Oberfläche.

**Zwei von drei, und das dritte mit Absicht:** `transition_angle` beschreibt
den Übergang *zwischen* Bohrung und Aufweitung, und ohne eine Aufweitung liest
ihn `drill_outline` gar nicht. Ihn mitzunullen hieße, einen Wert
zurückzusetzen, den der Kunde beim nächsten Runden wiederhaben will — die
Begründung steht am Feld selbst.

**Und ein gesetzter Haken ohne Länge ist eine Absage, keine runde Bohrung.**
`slot_travel` liest die Null als „rund" — richtig für einen direkten Aufruf,
falsch für den Haken: Wer *Langloch* anhakt und die Länge stehen lässt, bekäme
ein rundes Loch und ein Häkchen, das das Gegenteil behauptet. Gefunden wurde
das am gebauten Dialog und nicht im Code; die Vorgabe der Länge steht deshalb
auf dem Doppelten des vorgegebenen Durchmessers, damit der erste Klick
durchgeht. **Ein Feld, das mit einer Absage begrüßt, ist keine Vorgabe.**

**Die Materialtoleranz weitet ein Langloch überall, auch an den Enden.**
Gerechnet wird deshalb `Mittellinie = Länge − nominaler Durchmesser`, und
die Zugabe liegt auf dem Radius. Wer stattdessen die *Gesamtlänge* festhielte,
nähme dem Kunden bei jedem Druck ein Stück Verschiebeweg ab — und der
Verschiebeweg ist der Grund, aus dem es Langlöcher gibt.

## Ein Langloch ist an beiden Kernen ein Merkmal und ein Hohlraum

Am Netz setzt `perceive.slots` zwei Halbzylinder und ihre Flanken zusammen; am
exakten Körper tut es seit heute `brep.features._slots_instead_of_half_bores`.
Vorher beschrieb der exakte Kern jede Topologiefläche für sich, und ein
Langloch hat vier: Im Objektbaum standen `fillet_1` und `fillet_2`, wo eine
Öffnung ist, und die Handlungen eines Langlochs standen an keiner von beiden
(Robert: „auf einem langloch 2 werden und nicht mehr wählbar").

Gefragt wird topologisch, nicht an einer Kennzahl: zwei zylindrische Flächen
unter einer vollen Umdrehung, gleicher Radius, parallele Achse, beide ins Loch
gewölbt (`recess`), die sich **genau zwei** ebene Nachbarn teilen — und diese
zwei Ebenen grenzen ihrerseits an **beide** Bögen. Die letzte Bedingung ist
die, auf die es ankommt: Eine Tasche mit vier verrundeten Ecken hat dieselben
Paare, aber zwei benachbarte Ecken teilen **eine** Wand, nicht zwei. Die
Flanken gehen im Langloch auf, der Boden eines Sacklangloch nicht — seine
Normale zeigt entlang der Achse, er liegt gar nicht im Mantel.

**Und der Mantel ist geschlossen** (RM-411, 04.10.2026). Das Netz flutet den
Mantel über Flächen quer zur Achse (`_connected_shell`); läuft ein Bogen in
eine weitere Wand längs der Achse weiter, erreicht die Flut die Außenseiten,
und es ist kein Langloch. Der exakte Kern fragte nur die vier Flächen: An der
Stufenplatte, deren Langlochende in der Wand des Aufsatzes liegt, las er ein
Langloch der Tiefe 20 über Grundplatte und Aufsatz, und ein zweiter Zug auf
8 mm füllte dessen Umriss bis an die konvexe Hülle — aus 9 327,48 mm³ wurden
431,5. `_continues_the_mantle` fragt jetzt jede Nachbarfläche der vier: eine
Ebene längs der Achse oder ein paralleler Zylinder, der keiner der beiden
Bögen ist, setzt den Mantel fort
(`test_a_slot_whose_end_opens_into_a_step_wall_is_no_slot_on_either_kernel`;
dasselbe Langloch ganz in der Grundplatte bleibt an beiden Kernen eines).

**Offene Ausschnitte bleiben Langlöcher** (Entscheidung Robert, 11.09.2026).
Eine angeschnittene Rundbohrung und ein Langloch mit offenen parallelen
Flanken werden beide als `slot` erkannt und über dieselbe Handlung geändert.
Der gemeinsame Netzprüfer beider Kerne verlangt einen Innenbogen, tangentiale
Flanken soweit vorhanden und eine freie ebene Mündung; vorhandenes Material
hinter dieser Mündung verhindert einen falschen Treffer an einer Kreuztasche.
Der Füllkörper endet an der Außenwand, damit beim Versetzen kein Pfropfen
außerhalb des Teils stehen bleibt. Eine gekreuzte Aussparung kann ihre
Langlochform verlieren; dann meldet `slot_hole.feature_lost` den verlorenen
Bezug und den Rückweg über Strg+Z.

**Gesucht wird das eine Loch, und die Zuordnung wird nachgeprüft**
(`prepare_ops._sits_at`, für `slot_hole` und `resize_hole` gleichermaßen).
`perceive.matching.match` nimmt ein Merkmal an, solange Lage und Durchmesser
unter seiner Schwelle liegen — acht Prozent der Modelldiagonale, an einer
Platte von 200 mm sechzehn Millimeter. Das ist die richtige Großzügigkeit für
eine Zuordnung über eine fremde Operation hinweg und die falsche für eine,
die die Stelle selbst genannt hat: Stand das gezogene Loch nicht mehr da,
traf die Zuordnung das Nachbarloch, das trug von da an die fremde Kennung,
und der Befund blieb aus (Fund des Reviews, 11.09.2026, an beiden
Operationen gemessen). Genommen wird deshalb nur, was auf `match_tolerance`
an der genannten Mitte liegt — und beim geschlossenen Langloch die eingetragene
Länge trägt. Bei einer Randöffnung wird der verbliebene Bogen gegen die Enden
des gewünschten Schnitts geprüft. Bei durchgehenden Bohrungen darf die Mitte
entlang der Achse wandern, wenn die Zielwand eine andere Stärke besitzt.
Am exakten Kern gilt dieselbe Suche gegen `features_of`; ein `any(kind ==
"slot")` schwieg, sobald ein zweites Langloch im Körper stand.

**Und dieselbe Frage stellt die Auswertung jedem erklärten Merkmal**
(`perceive.matching.near_its_declaration`, über `declared_partners` — am Netz
in der Auswertung, am exakten Körper im Baustein): Was eine Operation als `generated`
ausgibt, bekommt einen erkannten Partner nur, wenn der quer zur Achse
innerhalb der Breite des erklärten liegt und entlang der Achse innerhalb
seiner erklärten Tiefe. `_sits_at` bleibt die strengere Prüfung der
Operation, die ihr eigenes Loch sucht; die Auswertung prüft allgemein und
großzügiger, weil ein Baustein seine Mitte an der Mündung erklären darf, die
Erkennung sie in die Mitte legt. Ohne diese Grenze nahm eine verschobene
Senkung die der Nachbarbohrung 18 mm daneben, und deren Name verwaiste.

`types.is_a_cavity` führt `slot` neben `hole` und `void`. Ohne den Eintrag hielt
jede Operation das Langloch für Materie und kehrte Füllen und Schneiden um — an
Luft und in vollem Material, sodass das Volumen gleich blieb und nichts es
verriet (RM-153). Versetzen, Verdoppeln und Entfernen brauchten sonst nichts:
Der Werkzeugkörper kommt aus `_feature_solid` und wird aufgezogen wie beim
Schneiden. **Drehen** braucht die mitgedrehte Mittellinie
(`_with_turned_direction`) — geschlossen wird mit der alten Richtung, gesetzt
mit der neuen; wer beides mit der neuen tut, füllt neben dem Loch und
schneidet ein Kreuz hinein.

**Und seine Breite ändert *Bohrung ändern*** (12.09.2026, RM-156). Der
Durchmesser ist dort seine **Breite**, und die Länge folgt daraus: `resize_hole`
rechnet sie aus dem gemessenen **Weg** plus der neuen Breite — Ø 6 auf 20 wird
zu Ø 8 auf 22. Gerechnet wird über den Weg und nicht über die Länge, denn er ist
der Grund, aus dem es Langlöcher gibt; wer ihn beim Verbreitern verlöre, bekäme
ein anderes Bauteil.

**Gefüllt wird dabei immer, auch ohne Versatz.** Beim Verbreitern deckt der
neue Umriss den alten zwar mit ab; beim Verschmälern bliebe ohne das Füllen die
alte Breite stehen, und das Maß im Objektbaum wäre eine Behauptung über
Material, das nicht mehr da ist. Ein Weg für beide Richtungen ist billiger als
zwei, die sich in einer unterscheiden. Die Zugabe entfällt (`overlap=0.0`): Sie
hält den Werkzeugkörper von der alten Bohrungswand fern, und die ist eben
zugegangen.

Was das Langloch **nicht** nimmt, ist `resize_feature` — das gilt Materie, und
ein Langloch ist ein Hohlraum. Der Satz in
`perceive.actions.NOT_APPLICABLE_HERE` nennt dafür die zwei Zeilen, die es gibt.

**Und seine Wand wird an der dünnsten Stelle genannt** (12.09.2026, RM-152).
`relations.sleeve_at` schloss es aus, weil seine Rechnung der halbe
Unterschied zweier Durchmesser ist — an einem Zapfen Ø 20 mit einem Langloch
Ø 8 auf 14 mm ergibt das 6 mm, wo die dünnste Stelle 3 misst. `Sleeve` führt
jetzt den Weg der Mittellinie mit (`bore_travel`), und `thickness` zieht seine
Hälfte ab: Die Enden sitzen um `travel / 2` aus der Mitte, und dort reißt das
Teil. Der Weg gehört dabei der **Höhlung** und nicht dem gefragten Merkmal —
von außen geklickt ist das Langloch der Kandidat. Wo daraus keine positive
Wand mehr wird, ist es kein Rohr, sondern eine offene Flanke; bei der runden
Bohrung fängt das der Durchmesservergleich ab, beim Langloch erst die fertige
Zahl.

## Beide Kerne sagen dasselbe, und zwar aus der Nachbarschaft

Drei Gegenfälle, an denen die Kerne auseinanderlagen, und drei Regeln, die
seither für beide gelten — Namen, Träger und Handlung, nicht bloß die Zahl:

* **Eine kleine Ebene ist eine Fläche, wenn ihre Ränder es belegen.**
  `MIN_FACE_AREA` (4 mm²) gilt ohne weiteren Beleg; darunter zählt ein
  Fleck, der an jedem Rand mit einem scharfen Knick an fremde Dreiecke
  stößt — und jeder Rand hat einen Nachbarn, ein unbelegter Rand ist
  nicht scharf —, auf keiner Rundung sitzt und kein Streifen ist
  (`_facets_standing_apart`). Wer die Schranke anfasst, hält die vier
  Gegenrichtungen: keine Flut auf der Kugel, keine fünfzig Mantelstreifen,
  keine Streifen einer STL mit T-Stößen (`plate_countersunk.stl`), die
  Seiten eines Achtecks bleiben. Eine Wand unter `MIN_SURFACE_WIDTH`
  bleibt ein Streifen; die Formschräge ergänzt sie weiter selbst
  (`tests/test_mesh_faces.py`, die Folie).
* **Die Mündungsfase eines Langlochs gehört zum Langloch** — Teilkegel und
  schräge Flanken, mit ihren Trägern, an beiden Kernen
  (`_partial_cones_folded`/`_mouth_flanks_folded`, `_mouth_chamfers_folded`).
  Die Zugehörigkeit kommt aus der Nachbarschaft; ein Kegelstück zwischen
  zwei Langlöchern bleibt unentschieden, nie dem alphabetisch ersten. Ob
  eine Freiformfläche des exakten Körpers ein Kegelstück ist, entscheidet
  die Einpassung des Netzes an ihren Dreiecken (`partial_cone_patch`) —
  keine zweite Schwelle am exakten Kern.
* **Eine Bohrung unter der vollen Umdrehung ist angeschnitten** (`partial`),
  und ob sie für sich bearbeitbar ist, sagt nicht der Winkel: Grenzt ihr
  Mantel an eine andere Höhlung, ist sie berührt — keine Kette, kein eigener
  Körper, `NO_OWN_BODY` in jeder Körperzeile — und wo die Ränder eines
  Merkmals gar nicht lesbar sind, sagt der Einzelweg das wie der Gruppenweg
  (`CavityState`, `CAVITY_TOPOLOGY_UNKNOWN`) statt „steht allein“ — und der
  Steckbrief sagt es dem Agenten unter der Auswahlzeile mit denselben Sätzen
  wie das Panel, samt Kette und Handlungsgruppen (`digest._selection_lines`,
  `relations.group_reason_texts`). Und ob zwei Merkmale dieselbe vollständige
  Form haben, sagt der Abstand zur Fläche (`_same_surface_patch`,
  `units.MAX_FACET_SAG`), nie die Vernetzung: Eine Kopie, deren Dreiecke
  nur feiner geteilt sind, bleibt in der Ganzkörpergruppe
  (`tests/test_feature_groups.py`), die Kalotte bleibt draußen. Ein Dreieck,
  das zwei Merkmale beanspruchen, gehört dem innersten oder niemandem
  (`relations.cell_owner_table`, `CONTESTED`); der Klick im Bild entscheidet
  nie nach der Reihenfolge der Erkennung. Und eine Maßquelle heißt `native`,
  wenn ein nativer Träger sie belegt — am offenen Langloch des exakten Kerns
  Durchmesser, Achse, Bogenmitte und Richtung, nie Mündung und Weg
  (`slots.native_open_slot_measures`); keine pauschale Hochstufung. Die
  Umfangsschwelle steht
  einmal (`FULL_TURN_SPAN`, 300 Grad); der exakte Kern liest sie von dort
  (`brep.features._full_turn`).
  Am Netz erkennt den Anschnitt der Rand (zwei Linien längs der Achse über
  die ganze Tiefe), am exakten Körper der Umfang — nach dem Zusammenführen
  der Nahtstücke. Eine gleiche Anzahl oder ein gleiches Volumen beweist
  keine Parität; geprüft werden Art, Maße, Herkunft, Träger, Rolle und
  Handlung je Fall (`tests/test_features.py`, `tests/test_partial_bores.py`).

## Ein Muster ist die Quelle, bewegt — und es bleibt ein Körper

`pattern_feature` wiederholt Merkmale; `pattern` kopiert Körper. Die zwei
bleiben getrennt, denn der Kundenweg verlangt ausdrücklich „keine
versehentliche Kopie des gesamten Körpers" (Konzept §13.9). Drei Regeln:

- **Jede Instanz entsteht aus dem Werkzeug der Quelle, bewegt** — nie aus
  einer zweiten Beschreibung. Wer eine Art dazunimmt, gibt ihr ein Werkzeug
  an der Stelle der Quelle (`_pattern_probe`) und ein exaktes Gegenstück
  (`_exact_place_tool`); die Merkmale der Kopie führt
  `transformed_features` nach, damit Achsen, Richtungen und Öffnungen
  drehen und spiegeln wie beim ganzen Körper. Das exakte Gegenstück ist
  starr wie beim Verdoppeln (RM-226, Nachtrag 04.10.2026): Die
  Durchgangsbohrung endet an ihren mitbewegten Randebenen
  (`_clipped_at_moved_rims`), und jede Kopie fragt die Säule
  (`_exact_through_checked`, je Bohrung). Mit der ganzen Zielhülle als Tiefe
  bohrte das Muster längs der schrägen Platte bis an die höhere Oberseite
  durch — 69,9 mm³ mehr, durchgehend, ohne Satz —, die vervielfachte
  Senkbohrung sagte exakt nichts, wo das Netz „geht nicht mehr durch“
  meldete, und nach dem ersten Satz schwieg die Frage für jeden weiteren
  Platz. Am Netz liegt die Säule im Werkzeug des Platzes wie bei allen
  Geschwistern: Ohne meldete ein 32-Eck Ø 6,1, um 9,1 mm vervielfacht, „geht
  nicht mehr durch“ bei unverändertem Volumen.
- **Ein Platz, der nicht passt, entsteht nicht und wird genannt.**
  Überschneidung mit der Quelle oder einem anderen Platz, kein Material
  unter dem Werkzeug — beides ein Befund mit den Platznummern und einem
  Ausweg, nie ein halb geschnittenes Langloch (Regel 17).
- **Die Quelle bleibt maßgebend**, weil der Schritt sie beim Namen nennt und
  bei jeder Auswertung neu liest. Ein erkanntes Merkmal ohne belegte
  Flächen ist keine Quelle (`not_evidenced`): Sein Werkzeug wäre an jedem
  Platz eine Vermutung.

## Aushöhlen: eine Öffnung ist eine fehlende Fläche, eine Entlüftung ein Loch

`openings` nennt Flächen, die fehlen; `vents` bohrt Löcher in einen sonst
geschlossenen Hohlraum. Ein offener Hohlraum bekommt keine Entlüftung. Der
ältere `open_at` öffnet in eine Achsrichtung über den ganzen Querschnitt und
behält diese Bedeutung für gespeicherte Schritte; zusammen mit `openings`
ist er eine Absage, keine stille Mischung. **Die Resin-Stufe 2 (P9.3)
erweitert `vents`, nicht einen zweiten Aushöhlen-Weg.**

Am exakten Körper rechnet `MakeThickSolidByJoin`; ein Ergebnis zählt nur,
wenn es ein gültiger, geschlossener **und veränderter** Körper ist — die
Bibliothek gibt bei zu dicker Wand und an konkaven Formen den Eingang
unverändert zurück, ohne zu werfen. Findet sie keine Innenwand, fragt das
Raster, ob Platz wäre: Ohne Platz ist die Wand zu dick (`hollow.too_thin`),
mit Platz entscheidet `exact_fallback` — nachfragen (`ctx.ask`, die Antwort
reist über `OpResult.answered` in den Schritt), am Dreiecksmodell mit Befund
und Umwandlungshinweis, oder das Teil lassen. Nie still der Netzweg.

## Menütiefe: gefaltet wird hinten, nicht beim Größten

`surfaces.folded_groups` entscheidet, welche Gruppe ein Untermenü bekommt,
damit ein Menü in die Grenze aus §2.6 passt. Genügt **eine** Gruppe, fällt die
**hinterste** aus `MENU_GROUPS` — die Leiste ordnet von häufig nach
vorbereitend, und wer falten muss, faltet hinten. Erst wenn keine allein
genügt, entscheidet die Größe; sonst käme die Rechnung nicht voran.

**Vorher entschied allein die Größe, und das war am Flächenklick die falsche
Frage.** Nach dem Falten von „Bausteine" fehlt dort genau **eine** Zeile, und
die größte der übrigen ist „Ändern" — mit der Bohrung darin, also genau dem
Eintrag, dessen zweiter Klick den Umbau des Kontextmenüs ausgelöst hat.
Gemessen am gebauten Fenster stand „Filament auf eine Fläche" nach der Faltung
im Untermenü von „Vorbereiten", unter einem Wort, unter dem niemand Farbe
sucht. Entscheidung Robert, 27.08.2026: Die häufige Geste bleibt oben, das
Seltenere wandert — dafür gibt es `keep`.

**Die Zahlen dazu wandern mit dem Register.** Am 27.08.2026 waren es
einunddreißig Operationen — 22 Bausteine, 5 Ändern, 2 Erzeugen, 2 Vorbereiten —
und drei feste Zeilen darüber; „Bausteine" sparte einundzwanzig Zeilen und
genügte trotzdem nicht. Im Menü *Ändern* trugen die Kategorien bei einer Grenze
von zwölf 9, 9, 4, 4, 3, 3 und 1 Zeilen, zusammen 33: **vier** mussten falten,
dann waren es elf, und *Bohrungen*, *Oberfläche* und *Reparatur* blieben direkte
Zeilen. Dieselben Zahlen standen im Docstring schon einmal als „19 Operationen,
davon 10 Bausteine" — das stimmte einmal und lag mit jedem neuen Baustein
weiter daneben. **Wer die Rechnung anfasst, misst sie neu, statt die Tabelle zu
glauben.**

**Die Rechnung kommt ohne Qt aus, und das ist keine Stilfrage.** Gemessen am
24.08.2026: Jeder Test, der über die `window`-Fixture ein `MainWindow` baut,
hebt die Abrissquote der **ganzen** Testdatei — von zwei Abrissen in neun
Läufen auf zwei in drei. Eine Frage, die eine Funktion über Namen und Zahlen
beantworten kann, bekommt kein Fenster.

**Und ein Menüweg in einem Text ist ein Messwert, kein Beispiel.** Die
Werkzeugbeschreibungen des Agenten nannten Gruppe und Titel ohne die
Kategorie-Ebene, und das traf **72 von 77** Operationen: Der Chat schickte den
Kunden nach „Ändern → Fase anbringen", während der Eintrag unter „Ändern →
Formgebung → Fase anbringen" steht. `menu_path` baut die Ebenen seither aus
denselben Daten wie die Leiste. Wer die Menütiefe ändert, sucht die Wege, die
als Zeichenketten in Docstrings, Katalogen und Tests stehen — beim letzten Mal
waren es fünf, vier davon in `tests/test_agent_suite.py`.

## Auto Split: die Folge, die Spiegelebene, der Rand

- **Braucht ein Stück mehr als einen Schnitt, entscheidet die ganze Folge**
  (`autosplit._plan_step`). Die Rangfolge einer Folge ist fest: alles passt
  vor nicht alles, dann weniger Stücke, dann weniger Klebestellen (Summe der
  Konturen, eine Lücke kostet keine), dann die Summe der Nahtbewertungen. Die
  Stückzahl steht vor den Klebestellen, weil ein weiteres Stück immer eine
  weitere Naht ist. Das Stützvolumen entscheidet nur den letzten Schnitt eines
  Stücks — vorher hat eine Hälfte keine Lage.
- **Begrenzt wird über eine Zahl, nie über die Uhr.** `PLAN_BUDGET`
  Probeschnitte je Teilung; nach Zeit begrenzt, teilte dieselbe Datei auf
  einem belasteten Rechner anders (§11.3). Ist das Budget weg, gilt die Naht,
  die die Suche allein nähme — die Teilung wird trotzdem fertig.
- **Die Spiegelebene wird gemessen und gewinnt nur, was sie nicht
  verschlechtert** (`symmetry.mirror_plane`, `units.match_tolerance`): gleiche
  Konturzahl wie die beste Naht, keine Einschnürung (T1), Stützvolumen
  innerhalb derselben Fünf-Prozent-Grenze. Die Querschnittsänderung zählt an
  ihr nicht — beide Schnittflächen sind dort dieselbe. Gespiegelt geschnitten
  werden die Stücke beiderseits nur bei gleicher Stiftzugabe.
- **Die Stiftzugabe gehört der Hälfte, die die Stifte trägt**
  (`_child_reserves`). Was ein Stück schon trug, erben beide Hälften.
- **Eine Lücke ist die beste Naht.** Wo keine Kante die Ebene kreuzt, trennt
  der Schritt ohne Stifte (`Candidate.gap`, `pins=0` im Verlauf).
- **Der Rand ist der des Anordnens** (`split.bed_margin`). Wer Auto Split mit
  kleinerem Rand fährt als *Auf dem Bett anordnen*, bekommt Stücke, die nach
  dem Anordnen über dem Bettrand liegen.
- **Die Nummern der Stifte vergibt der Plan, nicht das Stück** (RM-267). Die
  Passungen einer Teilung nennen ihre Stifte, bevor ein Schritt rechnet;
  `apply_planned` schreibt jedem Schritt die erste Nummer in `first_pin`, und
  `_cut_and_pin` nimmt sie. Nach den Namen am Stück gezählt
  (`pins.next_connector_index`, der Weg jedes Schritts ohne das Feld), zählte
  ein erkannter Stift ohne Zwilling mit, und die Passungen zeigten ins Leere
  oder auf ihn (ERKENNUNG-16). Trägt ein erkanntes Merkmal schon den Namen
  eines neuen Verbinders, weicht es aus (`_clear_of`) — überschrieben wird
  nichts.
- **Befunde der Suche stehen in keinem Schritt** und überleben die folgende
  Auswertung nur, weil das Fenster sie wieder anhängt, solange der Verlauf da
  steht, wo die Teilung ihn ließ (`MainWindow._split_findings`).

## Szene: Platzierung, Kennungen, Cache, Projektdatei

### Platzieren verändert kein Dokument

- **Oberflächenplatzierung verändert kein Dokument.** `prepare_surface()`
  bestimmt die zusammenhängende Originalfläche und ihre Randtopologie einmal
  und merkt sie am Netz, je Dreieck und Merkmalsnamen (`remembered`, dieselbe
  Grenze wie die Stützpunktlesung); der Worker hält den unveränderlichen
  Kontext zusätzlich je Patch.
  `at_point()`, `point_with_distances()` und `point_with_centre()` verwenden
  dieselbe Flächenprüfung einschließlich Aussparungen. Zwei geradlinige
  Bezugskanten müssen unabhängig sein; Triangulationsdiagonalen und belegte
  Kreisfacetten liefern keine scheinbaren linearen Maße. Auf gekrümmten
  Flächen bleiben Punkt und Normale nutzbar, aber keine ebenen Abstände.
  Mittelpunkt-Offsets zeigen von der Bohrungsmitte zum Ziel entlang U/V.
- **Ohne Tiefe und Achse gibt es keine Mitte.** `surface_values` rechnet die
  Mündung eines Lochs auf seine Mitte um; fehlte eines von beiden, blieb der
  Wert die **Mündung** und wanderte als Mitte weiter — das Loch saß um die
  halbe Tiefe daneben, ohne Befund und ohne Absage. `seat_of` beantwortet
  dieselbe Frage seit je mit `None` (Regel 21). Und das Vorzeichen kommt aus
  der **Fläche**, auf der gezielt wird, nicht aus der Achse allein: Nach einem
  freien Klick kann das die Gegenseite sein.
- **Und die eigene Mitte ist kein Bezug.** `seat_of` nimmt das Merkmal selbst
  aus den Mittenbezügen der Fläche: Der Abstand eines Lochs zu seiner eigenen
  Mitte ist null, und zwar immer — im Bild standen dafür zwei Zahlenfelder, die
  keine Frage beantworteten. Was bleibt, sind die Mitten der **anderen**
  Löcher.
- **Wo etwas schon sitzt, wird nicht neu gezielt.** `prepare_surface()`
  beantwortet „wohin darf ich setzen" und verlangt einen Klick auf Material;
  `seat_of()` beantwortet „wo sitzt das, was schon da ist" — die ebene Fläche,
  deren Normale auf der Achse des Merkmals liegt und deren Ebene seine Mündung
  enthält. Zwei Dinge unterscheiden sie, und beide sind gemessen: Die Mitte
  eines Lochs liegt in **seiner eigenen Aussparung**, `at_point` lehnt sie
  sonst als „außerhalb der Fläche" ab; und die geraden Flanken eines Langlochs
  sind vom Merkmal aus die nächsten Bezugskanten überhaupt — an einer Platte
  60 x 40 kamen ohne Filterung minus 3,00 und minus 3,30 zurück statt 15 und
  20. Gefragt ist der Abstand zum **Rand des Teils**; was in einer Aussparung
  liegt, ist keine Antwort darauf. Wo es keine solche Fläche gibt, kommt
  `None` — eine Verrundung mündet nirgends, und geraten wird nichts (Regel 21).
  **Eine gefaste Mündung liegt nicht in ihrer Fläche**: Die gemessene
  Bohrungswand endet an der Fase, eine Fasenbreite unter der Oberfläche.
  `seat_of` sucht deshalb nach dem genauen Durchgang ein zweites Mal entlang
  der Achse, höchstens einen Radius weit (`mouth_reach`), und darf dabei um
  `MAX_FACET_SAG` hinter der Mündung liegen — eine eingepasste Wand endet
  nicht auf den Mikrometer in ihrer Ebene (am Wedge-Lock 3,5 µm). Die Mitte
  bleibt die gemessene: `surface_values` rechnet von der gefundenen Mündung
  zurück und nimmt die halbe Tiefe nur, wo sie zwischen Mündung und Fläche
  passt. Korpus: `plate_chamfered_mouths.stl`.
- **Beim Binden wird die Öffnung gefüllt wie beim Setzen** (RM-520,
  Kundenmeldung zu 0.5.2). Ein Baustein für Bohrungen sitzt über `seat_of` in
  der Mündung, und gespeichert wird ihre Mitte. `bind_surface` bereitete die
  Fläche beim Rechnen frisch vor, **mit** der Öffnung, und lehnte die Mitte als
  „außerhalb der gewählten Fläche“ ab — jedes Gewinde, jede Einpressbuchse und
  Mutternfalle, die so gesetzt wurde, hielt an. `_at_its_mouth` füllt die
  Öffnung nur, wenn die Achse einer Bohrung durch den Punkt läuft
  (`bore_through`, quer höchstens `MAX_FACET_SAG`); ein Punkt neben ihr bleibt
  eine Absage, denn dorthin setzt kein Klick, und wer dort landet, weil sich die
  Geometrie unter dem Bezug geändert hat, soll es erfahren.
- **Die Fasenkorrektur gilt nur der eigenen Mündungsfläche** (G5,
  25.09.2026). `surface_values(..., mouth=...)` bekommt den Durchstoßpunkt
  der Achse durch die eigene Fläche — aus `seat_of`, wo am Merkmal begonnen
  wurde, sonst aus `mouth_on` an der frisch vorbereiteten Fläche (dieselbe
  Frage wie `seat_of` je Ende: Ebene der Mündung, sonst bis `mouth_reach`
  dahinter mit einer Öffnung um die Achse). Ohne `mouth` oder auf einer
  anderen Ebene liegt die Mündung auf der getroffenen Fläche. Vorher galt
  jede parallele Fläche im Fenster als die eigene, und ein Sackloch, auf die
  2 mm darüber liegende Oberseite versetzt, wurde ein Hohlraum im Material.
  **Und der Abstand zur Mitte wird an der Mündung gemessen, nicht am
  Ziel:** Eine gemessene Achse steht um Rechenrauschen schief, und am
  verschobenen Punkt gemessen wanderte die Mitte mit dem Versatz in der Höhe
  — am Schaber 2,9 µm auf 43 mm, genug, dass `move_to` beim nächsten
  Tastendruck eine getippte Tiefe las und die Maßgruppe ans Merkmalfenster
  ging.
- **Ein Sichtstrahl wird am Originalnetz geprüft.** `original_surface_hit()`
  ersetzt unbekannte LOD-Zellen durch Originaldreiecke und berücksichtigt alle
  Schnittebenen. Ihre positive Seite entfällt; künstliche Kappen sind kein
  Platzierungsziel. Ergebnisse und freie Normalen bleiben Float64-Werte.
- **Werkzeugvorschau und Operation teilen die Geometrie.** `prepare_tool()`
  liefert einen unveränderlichen `PlacementTool` mit lokalem Körper und
  ausgewähltem Merkmalsversatz. `surface_values(..., prepared_tool=...)`
  berechnet daraus neue Koordinaten ohne weiteren Körperbau; dieser Kontext
  gehört zu genau den gewählten Eingaben; wer nur den Körper braucht, liest
  `prepare_tool(...).mesh`. Mündung oder Basis liegt bei null. Nur der
  temporäre Anzeigeaktor erhält den `frame_of()`-Rahmen am Treffer. Winkel,
  Einsenkung und Schnittspiegelung stecken bereits im Werkzeug. Bausteine
  deklarieren ihre Richtungsfelder über `normal_fields()`, damit gleichnamige
  Rezeptmaße erhalten bleiben. Beim Merkmalsversetzen ist `source` zusammen
  mit `feature` Pflicht; vollständige Bohrketten bilden ein Werkzeug.

### Kennungen und Verweise brauchen Belege

- **Ein Verweis folgt seinem Körper durch den Stapel** (`scene/orphans.lineage`,
  RM-023). Er nennt die Kennung, die der Körper **damals** hatte; teilt eine
  spätere Operation ihn, trägt nur das erste Stück sie weiter
  (`History._outputs_for`). Der Verweisfilter sucht die Kandidaten deshalb an
  allen Körpern, in deren Herkunft der genannte steht — nicht an dem einen mit
  der alten Kennung (dort kam statt der Frage aus §21.3 eine Sackgasse) und
  nicht an allen (zwei Platten tragen beide ein `hole_1`, und eine Frage nach
  einem fremden Loch ist schlechter als keine). Hängen die Kandidaten an
  mehreren Körpern, nennt jede Antwort ihren — `obj_3:hole_1`; sonst bleibt es
  bei der bloßen Kennung.

  **Ein Operationsverweis bleibt dabei bei seinem Körper**, und das ist keine
  Vorsicht, sondern die Darstellung: Ein `kind="feature"`-Parameter trägt nur
  die Merkmalskennung und wird gegen `inputs[0]` aufgelöst. Eine Antwort auf
  einen anderen Körper ließe sich dort nicht hinschreiben — angeboten wird
  deshalb nur, was auch ankommt.
- **Vergebene Merkmalskennungen bleiben reserviert.** Die Auswertung führt
  `SceneObject.reserved_feature_ids` über Zwischenoperationen fort und
  verhindert eine neue Zuordnung gelöschter Namen. Cache und Objekthash
  tragen die sortierte Sammlung; ein Projekt rekonstruiert sie aus den Ops.
- **Wer einen exakten Körper neu baut, belegt die Bezüge, die danach noch
  jemand braucht — oder die Kette hält an** (20.09.2026, P1.4c.2). Die
  native Erkennung nummeriert frisch; ein `face_1` nach `features_of` ist
  kein Beleg für das `face_1` davor. Belegt ist ein Bezug nur durch
  Durchreichen, durch die eindeutige Zuordnung auf denselben Namen, durch die
  eindeutige Zuordnung auf ein **bis auf Rechenrauschen unverändertes**
  Merkmal (`_unchanged_continuations`: jede Lage und Richtung auf `EPS_GEOM`,
  jede Größe relativ auf `EPS_GEOM` — gemessen bitgleich an unberührten
  Flächen, 23.09.2026; ohne ihn fragte Solidon nach einer Sackbohrung in eine
  Seite nach der Deckfläche einer Passung, weil die Erkennung neu nummeriert)
  oder durch einen von der Operation selbst ausgestellten Übergang
  (`OpResult.feature_continuations`). **Unverändert heißt unberührt:** Die
  Nachbarn einer versetzten Fläche wachsen mit und gelten nicht als
  unverändert; sie belegt *Fläche versetzen* selbst
  (`faces.pushed_features`). Den Übergang stellt nur aus, wer die
  Änderungsabsicht geometrisch nachgewiesen hat — `resize_hole` über
  `_preserved_exact_features`, und jede exakte Merkmalshandlung über
  `_exact_features_after` (Versetzen, Verdoppeln, Drehen, Entfernen, Senken,
  Verschließen in `_exact_cavity_result` und `_exact_copy_result`, das
  Gewinde in `_thread_result`) —, und nur für Paare, die der Anspruchsschluss
  tatsächlich freigegeben hat. Die Auswertung errät ihn weder aus dem
  Operationsnamen noch aus gleichen Kennungen, `created_by` oder
  `provenance`; `touches_features` ist kein Erhaltungsflag. Der Beleg reist
  wie `transform` durch den Ergebniscache (`CachedResult.continuations`,
  Cacheformat 21) und nie in die Projektdatei. Gezählt werden nur spätere
  Verbraucher und aktive Passungen, nicht der eigene Eingang des Schritts und
  nicht, was ein früherer Schritt benannt hat. Ein Halt ist atomar, nennt den
  Verbraucher (`NativeReferenceLost`) und wird von `orphans.check` nicht an
  der alten Szene „geheilt" (`blocked`, Befund `feature.blocked`).
  **Was kein Beleg trägt, wählt der Kunde am tatsächlich neu gebauten
  Körper** — nie die Auswertung: Die Frage läuft über denselben Weg wie am
  Netz, die Antwort liegt in der eigenen Domäne `native-group:` mit `scope`
  (roher Erzeugerschlüssel plus Ausgabeindex, Projektformat 28). Eine
  Netzantwort unter demselben Namen gilt nicht, ein anderer Scope fragt neu,
  „Nicht weiterführen" bleibt ein Halt und wird nicht gespeichert. Wer eine
  weitere Antwortdomäne braucht, erweitert `match_records` (Schlüsselpräfix,
  Pflichtfelder) und `_answer_matches` — keinen zweiten Speicher, keine
  zweite Gruppenlogik.
- **Ein Kantenfeld wird vor dem Cache gebunden, und die gebundene Auswahl
  geht in den Schlüssel des Verbrauchers** (20.09.2026, P1.4c.4b). Ein
  Kantenschlüssel ist eine gerundete Lage; zwei Kanten können denselben
  tragen. Wer eine Operation mit `kind="edges"` baut, liest ihre Kanten
  über `ctx.bound_edges` und reicht sie als `selected_edges` an den Kern —
  nie einen Schlüssel ein zweites Mal auflösen, nie bei Kollision auf „alle"
  oder den ersten Treffer zurückfallen. Rechnet die Operation am Netz, obwohl
  der Körper exakt ist, deklariert sie `edges_on_mesh=True`, sonst fragt die
  Auswertung nach Kanten, die die Operation nie sieht. Eine echte Kollision
  (gleicher aktueller Schlüssel) liegt als `edge-answer:` am Eingang mit
  dessen Objekthash als Scope; der Aliasfall (eindeutiger aktueller Schlüssel)
  ist ein Parameter über `answered`. Kein Token, kein Index und kein Handle
  reist in die Projektdatei.

- **Ein Verweis folgt beim Umbau seinem Merkmal, nicht seinem Namen.** Was
  ein Verweis vorher traf, steht in der Sichtung vor seinem Schritt
  (`ReferenceSight`); nach dem Umbau entscheidet `revision.verdict` in fester
  Folge — Herkunft (`Feature.created_by` über die Umnummerierung), Abdruck,
  Lage — und die Lage rechnet in reinem Python, weil eine BLAS-Summe auf
  einer anderen Maschine anders rundet und hier eine Entscheidung fällt
  (`kern.md`). Eindeutig: Der Verweis wird umgeschrieben und ein Befund sagt
  es. Mehrdeutig oder fort: fragen oder absagen, nie raten (Regel 21).

### Der Cache kennt, was ein Ergebnis bestimmt

- **Der Ergebniscache versioniert geometrische Auskünfte.** Alte Einträge
  ohne den aktuellen Formatstand sind Fehltreffer. Auch Änderungen erzeugter
  Geometrie und Merkmalsmetadaten gehören zu dieser Kompatibilitätsgrenze.
  Ein exakter mitgeführter
  Innenraum zählt zum Speicherbudget und zur Objektidentität.
- **Eine festgehaltene Antwort legt ihr Ergebnis unter beiden Schlüsseln ab**
  (22.09.2026). Wer über `OpResult.answered` etwas in die Parameter schreibt,
  ändert damit den Schlüssel seines Schritts; die Auswertung bildet den
  Schlüssel des nächsten Laufs auf demselben Weg (`_key_after_answers`) und
  legt das Ergebnis auch dort ab — mit derselben Herkunftsregel für die
  Platte. Sonst läuft der Schritt nach der ersten Antwort ein zweites Mal,
  und auf der Platte liegt ein Eintrag, nach dem beim Wiederöffnen niemand
  fragt. Wer den Schlüssel anderswo nachbaut statt über `resolve_params`,
  baut einen zweiten Ort, an dem die Auflösung steht.
- **Eine bewegte Kopie wird nicht neu untersucht.** Meldet eine Operation
  `transform`, gibt die Auswertung der Merkmalsbindung das Eingangsnetz
  derselben Stelle mit, und `perceive.features.carry_detection` überträgt
  die gemerkte Erkennung — unter Beleg am Netz (starre Matrix, dieselben
  Dreiecke, jede Ecke am bewegten Ort), nie auf Zusage der Operation.
  `geom.transform.apply` reicht dazu die Topologie im Cache des Netzes
  weiter. Eine Operation, die einen Körper nur bewegt, geht deshalb durch
  `moved_object`/`apply` und meldet ihre Matrix; wer eine Bewegung anders
  baut, verliert beides.
- **Eine feiner geteilte Kopie auch nicht.** *Kanten verfeinern* vermerkt am
  Ergebnis, aus welchem Dreieck jedes neue stammt
  (`perceive.features.note_refinement`), und die Auswertung glaubt den
  Vermerk erst nach dem Beleg am Netz (`refined_twin`: derselbe Eingang,
  jede Ecke in der Ebene ihres Ursprungs, je Ursprung dieselbe Fläche). Dann
  leben die Merkmale in den Dreiecken weiter, die aus ihren hervorgingen —
  unter der Grenze über den Merker (`carry_refined_detection`), darüber als
  stehend ohne örtliche Nachmessung. Wer eine weitere Operation baut, die nur
  teilt, gibt die Herkunft ebenso mit; ohne sie maß die Auswertung am
  Bohrmaschinenhalter nach 0,5 mm 317 Merkmale in 644 s nach und verlor sie
  danach.
- **Die Live-Vorschau erkennt nur, was jemand braucht.** `evaluate(...,
  detect_features=False)` ist der Weg des Dialogs; er lässt die Erkennung
  aus, wo kein späterer Schritt und keine Passung ein Merkmal des Körpers
  nennt. Eine Szene daraus ist ein Bild und wird nie zum Dokumentstand — wer
  Merkmale aus einer Vorschau liest (der Agent), ruft den genauen Weg.

- **Die Merkmalerkennung nimmt bis 1,5 Millionen Dreiecke je Körper
  automatisch an, beim Laden nach Bestätigung bis fünf Millionen** (§21.1).
  `FEATURE_LIMIT_TRIANGLES` begrenzt die Auswertung, darüber prüft
  `detect_known` örtlich; die Generator-Reduktion bleibt darunter
  (`generate.GENERATED_TRIANGLE_LIMIT`), nie darüber. Karten, Darstellung und die
  höchstens `FEATURE_LIMIT_COUNT` (fünftausend seit dem 22.09.2026)
  zuzuordnenden Merkmale haben eigene Leistungsbudgets. Über der Merkmalsgrenze
  bleibt zuerst, was mit denselben Dreiecken schon da war, dann die mit der
  größten Oberfläche, und zugeordnet wird wie sonst (`evaluate._heaviest`,
  RM-235) — nie eine Hälfte ohne Zuordnung, nie eine Auswahl, die ein
  Skalieren umsortiert.
  Eine Anhebung wird an echten feinen Netzen einschließlich der oberen
  Gegenprobe gemessen; die Geometrie wird für die Erkennung nicht reduziert.

### Der Verlauf plant neu, statt umzubiegen

- **`OpContext.scene` ist nur lesend** (Regel 3). Ops erzeugen Objekte, sie
  ändern keine.
- **Reparieren und erneut versuchen ersetzt den angehaltenen Suffix atomar.**
  Die Reparatur steht vor dem fehlerhaften Schritt; dieser und alle jüngeren
  Schritte werden mit neuen Kennungen neu geplant. Alte Fassungen liegen in
  `DocumentChange.before.edited_ops`, ihre Entfernung in `after.edited_ops`.
  Reparatur und neue Fassungen gehören zu einer Transaktion, damit ein Undo
  exakt den alten Suffix zurückholt. Die gemeinsame Zielprüfung in
  `repair_targets()` verlangt lebende Eingänge und schließt Operationen des
  exakten Kerns aus: Eine Netzreparatur würde ihre bearbeitbaren Flächen in
  feste Dreiecke umwandeln und den erneuten Versuch unbrauchbar machen.
- **Objektzahländerung hält die Auswertung an** statt sie zu verschlucken.
  Daraus folgt für eine Operation, die einen Körper gern zerlegen würde:
  Sie darf nicht. Ihre Ausgänge stehen fest, bevor gerechnet wird
  (`History._outputs_for`), und eine andere Zahl ist ein Halt. Der Weg ist
  Regel 17 — die Absage nennt die Zerlegung als Vorschlag, und das Fenster
  setzt sie **vor** den angehaltenen Schritt (`History.split_and_retry`,
  Muster wie die Reparatur darüber): *Druckoptimal ausrichten* wirft für
  einen Körper aus losen Teilen, der als Ganzes nirgends hinpasst,
  `NoFittingOrientationError` mit `SPLIT_AND_RETRY` an erster Stelle und
  der Stückzahl in `values["count"]`, gezählt wie `split_bodies` zählt —
  und nur, wenn jedes Teil für sich in eine Lage passt; sonst hielte die
  Kette nach dem Klick am selben Schritt noch einmal an. Beim Neuplanen des
  Suffixes stehen die Teile dort, wo der Körper stand, in jedem Schritt,
  der die ganze Szene nimmt; jeder andere behält seine Kennung, denn die
  erste Kennung der Zerlegung ist die des Ausgangskörpers.
- **Verringern und erneut versuchen nennt eine nachgezählte Zahl.** Ein Netz,
  das zum Teilen zu dicht ist (*Kanten verfeinern*, *Dreiecke angleichen*,
  *Fläche unterteilen*), bekommt `DECIMATE_AND_RETRY` nur, wo das Verringern
  wirklich trägt: `mesh_ops._thinning` verringert auf dem schnellen Weg
  (`decimate_for_display`, derselbe wie *Methode: Schnell*) und zählt am
  Ergebnis mit derselben Vorabzählung wie das Teilen danach; die Zahl steht in
  `values["decimate_to"]`, und `History.decimate_and_retry` setzt genau diesen
  Schritt vor den angehaltenen (Muster wie die Reparatur, dieselbe
  Zielschranke `repair_targets`). Keine Schätzung aus dem Netz davor — sie lag
  an echten Modellen bis zum 3,6-Fachen daneben, und das Verringern riss zwei
  Körper auf. Wo die Fläche allein schon zu viele Dreiecke braucht, wird nicht
  gesucht und nichts angeboten; ein offenes Netz bekommt zuerst *Erst
  reparieren, dann neu rechnen*.
- **Verfeinern und erneut versuchen nennt eine durchgespielte Länge.** Ein
  *Glätten*, das den Körper umstülpt (`inverted`), ihn durch sich selbst
  schiebt (`folded`: über ein Viertel **mehr** Volumen, am Kumiko-Organizer
  das Vierfache) oder mehr als ein Viertel kostet (`mesh.smooth_shrank`),
  bekommt `REMESH_AND_RETRY` nur mit der Kantenlänge, bei der *Kanten
  verfeinern* und dasselbe *Glätten* danach durchlaufen und das Volumen um
  höchstens `SMOOTH_LOSS_WARN` ändern (`mesh_ops._smoothing_holds`,
  `_remeshing_for_smoothing`: runde Längen aus `SMOOTHING_EDGES`, die längste
  zuerst, bis `SMOOTHING_REMESH_BUDGET` Dreiecke). Die Länge steht in
  `values["remesh_to_mm"]`, `History.remesh_and_retry` setzt den Schritt davor
  — auch vor einen, der durchlief (die Warnung), wie die Reparatur vor einen
  gerundeten. *Weniger Durchgänge* steht nur da, wo ein Durchgang trägt; trägt
  nichts, bleibt *Eingabe korrigieren* (Regel 17). Gemessen am STL-Korpus bei
  fünf Durchgängen: fünf Umstülpungen, zwei Faltungen, zwölf Schrumpfungen —
  jede bekam eine Länge, und jede lief damit durch.
- **Wer die Dreieckszahl vorab zählt, deklariert es** (`expected_triangles`,
  RESTVERLAUF-04): *Kanten verfeinern*, *Dreiecke angleichen*, *Fläche
  unterteilen* und *Dreiecke verringern*. Dieselbe Funktion prüft in der
  Operation vor dem ersten Schnitt und in der Vorschau am Original — eine
  Absage ist an beiden Orten dieselbe Ausnahme mit denselben Werten. Wer eine
  neue teilende Operation baut, trägt ihre Vorabzählung dort ein, statt sie
  im Rumpf zu wiederholen.
- **Wer nur das Netz ändert, deklariert es** (`retriangulates`): *Kanten
  verfeinern*, *Dreiecke angleichen*, *Dreiecke verringern* — Operationen,
  deren Abweichung sie selbst zusagen oder messen. Ihre Vorschau zeigt das
  neue Netz und die Dreieckszahl, keinen Booleschen Vergleich
  (`compare_scenes(retriangulated=…)`). *Glätten* und *Fläche unterteilen*
  ändern die Form mit Absicht und tragen die Angabe nicht. Das Register lehnt
  beide Angaben an einer Operation ab, die nicht einen Körper nimmt und
  zurückgibt.
- **Einfügen und Verschieben planen den Suffix genauso neu** (RM-188 P7):
  ab der ersten geänderten Stelle neue Kennungen, dieselben Werte, Körper
  und Startwerte, eine Transaktion (`_clone` teilt sich das mit
  `_retried_after`). Gefragt wird am Zustand **an der Stelle**: Ein Körper,
  den erst ein späterer Schritt anlegt, ist dort nicht da; ein Schritt, der
  einen Körper verbraucht, den ein späterer braucht, bekommt keine Stelle.
  Ein Vorwärtsbezug, ein Kreis oder ein verlorenes Merkmal wird abgesagt,
  nie umgebogen.

- **Ein ausgeschalteter Schritt erzeugt nichts, und nichts tritt an seine
  Stelle.** Die Auswertung überspringt ihn mit Befund; ein Körper, den nur er
  anlegt, fehlt, statt durch einen Ersatz vorgetäuscht zu werden. Wer ihn
  braucht, ruht mit — gewählt (`Suppression.chosen`) ist nur, was der Nutzer
  ausgeschaltet hat. Ein Schritt, der die ganze Szene nimmt (Ausgänge gleich
  Eingängen, etwa Anordnen), rechnet mit dem, was da ist. Passungen, deren
  Merkmal mit ihm ruht, ruhen mit (`fits.paused_fits`) und werden nicht als
  verletzt gemeldet.

### Slots reisen nur mit, wenn die Operation sie mitnimmt

- **Die Slots je Dreieck reisen nur mit, wenn die Operation sie mitnimmt.**
  `MeshData.replacing` behält die Slotliste allein bei gleicher Dreieckszahl;
  wer Teilnetze bildet, hat eine andere und bekommt **keine** — nicht eine
  falsche, sondern gar keine, und der Export ergänzt dann stumm den
  Platzhalter „Slot 0" (Robert, 11.09.2026: ein zerlegter Schriftzug kam im
  Slicer auf einem zweiten Filament an). `Trimesh.split` und `submesh`
  kennen Solidons Liste nicht; wer Dreiecke auswählt, nimmt ihre Nummern mit
  und schneidet die Liste selbst (`prepare_ops._loose_parts`, über
  `face_components` — dieselbe Zählung wie „besteht aus N Teilen" im
  Prüfbericht). `test_split_bodies_keeps_the_filament_of_every_triangle`
  misst es am Ort jedes Dreiecks, `test_a_lettering_split_into_letters_
  keeps_its_one_filament` bis in die 3MF.
- **Keine absoluten Pfade** in der Projektdatei (Regel 12), **kein
  ausführbarer Code** darin (Regel 13).
- Format geändert? Dann alle fünf Schritte: Version, Migration,
  Beispieldatei, Test, alte Migrationen behalten.

## Entwurfsstufe nur über einem Budget (RM-427)

Darunter ist der Entwurf dasselbe Netz wie fein; darüber gröber, und ein Befund
sagt es (`blend.draft`). Das Budget zählt, was kostet: beim Verschmelzen
Rasterpunkte, gewogen mit der Oberfläche über `DRAFT_SURFACE` — an 327 680
Dreiecken knapp unter dem Punktebudget dauerte der Entwurf 3,8 s statt 0,9 s.
Kegel und Ring halbierten ihre Segmente ohne Befund und sparten nichts, was
zählt; sie haben keine Entwurfsstufe mehr. Export und Slicer nehmen ohnehin die
feine Rechnung (RM-426, `wartezeit.md`).

## Füllkörper, Toleranzen, Langlochvorgabe — die Gründe zu drei Regeln

**Füllkörper:** Wer statt des breiteren Werkzeugkörpers die Wand des Hohlraums
nachbaut, lässt zwei Flächen stehen, mit Zugabe an den Enden. Was danach wieder
ausgeschnitten wird, ist exakt das Merkmal — jede Zugabe dort wäre ein Maßfehler.

**Toleranzen:** Keine Konstante als Fertigungszugabe, weil das Gleitspiel des
Materialprofils diese Aufgabe leistet; eine zweite Zugabe verfälschte die
Kalibrierung (§28.3).

**Langlochvorgabe:** Die Länge steht auf dem Doppelten des vorgegebenen
Durchmessers, weil ein Feld, das mit einer Absage begrüßt, keine Vorgabe ist.

**Gedrehtes Langloch:** Wer eine Geste einlöst, baut die Wirkung, nicht den
Hinweis auf die andere — ein Zug in neuer Richtung dreht das Langloch
(`slot_hole.turned`), statt auf *Merkmal drehen* zu verweisen.

**Langloch ohne Zugabe:** `slot_hole` schneidet ohne `FEATURE_OVERLAP`
(`overlap=0.0`), damit beide Wege — Ziehen und Ändern — und beide Kerne
dasselbe Langloch schneiden.

## Versetzen: Kette, Material, eine Frage (RM-535)

**Ganze Kette:** Versetzen, Drehen und Verdoppeln nehmen die ganze Hohlraumkette
mit — Entscheidung Robert; nur *Zum Langloch ziehen* sagt an einer geteilten
Kette ab.

**Material, wie es ist:** Der volle Körper aus den Flächen füllte, was im
Merkmal hohl ist, und die Hohlräume aus Kennzahlen gaben es nur grob zurück.
Am Minitopf (Zapfen Ø 30 um eine Tasche Ø 28 mit Deckelfalz) stand nach jedem
Versetzen +240,65 mm³, gleich wie weit; der nachgebaute Becher im Korpus
(`cup_on_stem.stl`) verlor 529,6 mm³. Eine Tasche, die den Zapfen umschließt,
schnitt ihn ab 0,5 mm ganz weg (Kundenmodell minus 189 mm³, Korpus
`pocket_with_pin.stl` minus 178 mm³). Ein Sackloch, das von unten in einen
Stift reicht, ging bis zu dessen anderem Ende (minus 5 722 mm³), und eine
Endfase füllte die Mündung eines nicht erkannten Sacklochs (+2 218 mm³ beim
Kunden). Das Material an der alten Stelle zu schneiden und zu verschieben ist
die Antwort der Bohrung, die ihre Luft versetzt (`_air_of_the_bore`).

**Eine Frage:** Die Karte bot an Wulst und Kehle X/Y/Z an, an denen die
Operation absagte, und sperrte die Tasche um einen Zapfen, in der sie rechnete;
der Griff fragte nur die Art. `actions.move_refusal` ist die Zeile der Karte,
und Operation und Griff lesen sie. Robert (d): Die Tasche um einen Zapfen sagt
ab, statt beide gemeinsam zu versetzen.
