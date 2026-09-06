---
paths:
  - "app/core/geom/**/*.py"
  - "app/core/registry/**/*.py"
  - "app/core/scene/**/*.py"
---

# Regeln für Operationen

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert — auch nicht „kurz" im Viewport, auch nicht im Agenten (Regel 2).

**Eine Geste ist nicht dasselbe wie ein Schritt.** Eine Op darf beliebig viele
Nutzergesten sammeln, solange ihr Ergebnis vollständig aus ihren Parametern
folgt: Der Editor schreibt in einen Parameterwert, die Geometrie entsteht erst
bei der Auswertung, und was das Fenster währenddessen zeigt, ist eine Vorschau.
Die Skizze macht es so (§30.1), das Sculpting wird es so machen. Was dabei
einzuhalten ist, steht unten unter „Sammelparameter" und wird von
`tests/test_gesture_ops.py` über das ganze Register geprüft.

## Vollständig oder gar nicht

Keine Op ohne Registereintrag, Parameterschema, Geometrietest und übersetzte
Texte. Die acht Schritte stehen als Checkliste in `AGENTS.md`; `/neue-op`
führt sie durch. Der Registereintrag braucht `name`, `title`, `category`,
`params`, `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`,
`doc`, optional `shortcut`.

`tests/test_registry_consistency.py` parametrisiert über das Register: eine
unvollständige Op fällt dort auf, ein doppeltes Kürzel auch.

**Was die Operation von ihrer Eingabe verlangt, steht im Register.** Eine Op
des exakten Kerns trägt `requires_kind="brep"`; das Menü graut sie bei einem
Netz aus und schreibt den Grund in den Tooltip, statt sie anzubieten und nach
dem ausgefüllten Dialog abzulehnen (Regel 19). Der gute Satz im Kern bleibt —
er ist die zweite Hürde, nicht die erste. Eine Aufzählung in der Oberfläche
wäre beim nächsten Zuwachs des exakten Kerns unvollständig.

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

## Parameter

Jeder Parameter hat Titel, Vorgabe, Einheit, Grenzen und einen `doc`-Satz, der
sagt, was er bewirkt — nicht, wie er heißt. Vorderseite des Dialogs: die zwei
bis drei Werte, die man tatsächlich ändert. Alles Weitere hinter „Weitere
Einstellungen" (§2.4).

Toleranzen verweisen ins Materialprofil (`auto:<material>`), nie als Zahl.
Wo ein Projektparameter passt, steht keine Streuzahl.

### Sammelparameter (`kind` in `sketch`, `strokes`, `armature`)

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

`NESTED_REFERENCES` in `scene/evaluate.py` ordnet jedem betroffenen `kind`
seinen Sammler zu — `sketch` → `sketch_parameter_references()`, `armature` →
`pose_parameter_references()` —, und `_with_nested_context()` mischt die Werte
in den Schlüssel. **Eine Zuordnung und keine Bedingung**, weil genau das schon
einmal schiefging: `"sketch"` stand dort hart verdrahtet, die Pose kam später
dazu und wurde übersehen — obwohl vier Stellen zusagten, dass ein Gelenkwinkel
ein Projektparameter sein darf. Wer einen neuen Sammelparameter mit Ausdrücken
baut, trägt ihn hier ein; das ist eine Zeile und keine Suche.

`strokes` steht bewusst nicht drin: Ein Pinselstrich *ist* eine Koordinate,
kein Maß, das jemand an einen Parameter hängt.

**Und der Schlüssel muss die Träger kennen, von denen eine Operation an den
eigenen Eingängen vorbei liest.** `operation_hash` deckt die Hashes der
Eingänge — drei Lesarten greifen aber auf fremde Körper der Szene zu: das
Ziel von `align_to_feature` (`kind="feature"`), die `up_to`-Fläche
(`TARGET_FIELD`) und die `feature:<id>`-Ebene jeder Skizze
(`face_of_sketch`, dieselbe Funktion wie im Verweisfilter).
`_with_nested_context` mischt die Hashes **aller** Träger des benannten
Merkmals in den Schlüssel — alle, weil zwei Körper denselben Merkmalsnamen
tragen können. Ohne das behielt ein ausgerichteter Körper mit Cache die alte
Lage und eine `up_to`-Extrusion die alte Höhe, über das Schließen hinaus.
Wer eine neue Lesart aus `ctx.scene` baut, trägt sie hier ein — dieselbe
Pflicht wie bei `NESTED_REFERENCES` darüber.

**Der Agent bekommt den Parameter nicht zu sehen.** Skizzen entstehen über
benannte Grundformen und Maße, nie über rohe Punktlisten (§26, Leitprinzip 5).
`json_schema()` lässt `kind="sketch"` deshalb ganz aus, und die Sitzung lehnt
ein trotzdem mitgeschicktes Argument ab. Zwei Ebenen, weil eine Lücke im
Schema noch kein Verbot ist.

## Boolesche Operationen

Die Rückfallkette (§17.2) hat fünf Stufen, und die erreichte Stufe gehört in
`solver`:

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen, zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag | — |

Stufe 4 kostet Genauigkeit und wird im Prüfbericht ausgewiesen, nie
stillschweigend verwendet. In Entwurfsqualität endet die Kette nach Stufe 2.
Nach `voxel` ist die Materialslot-Zuweisung neu zu übertragen — die Vernetzung
wurde ersetzt (§20).

## Beide Qualitätsstufen

`ctx.quality` kennt Entwurf und Fein. Entwurf ist das, womit iteriert wird und
worin der Agent arbeitet; Fein gilt beim Export und im finalen Prüfbericht.
Eine Op, die beide gleich behandelt, sollte das bewusst tun.

## Befunde

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

**Was ein späterer Schritt behoben hat, warnt nicht mehr.** `SETTLED_BY`
(`scene/evaluate.py`) streicht einen Befund, sobald einer aus seiner Menge an
einem **späteren** Schritt und am **selben Körper** steht. Beides gehört zur
Bedingung: Ein Reparieren vor dem Einlesen des nächsten Modells hebt dessen
Befunde nicht auf, und zwei Modelle in einer Szene teilen sich den Bericht,
nicht ihre Löcher. Gestrichen und nicht herabgestuft — „Das Modell ist nicht
geschlossen" steht im Präsens und beschreibt einen Zustand, den es nicht mehr
gibt; als Hinweis wäre der Satz nicht milder, sondern falsch. Übrig bleibt der
Satz des Schritts, der es behoben hat, und der erzählt die ganze Geschichte.

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

## Szene: Platzierung, Kennungen, Cache, Projektdatei

Bis zum 06.09.2026 standen diese Regeln in der Karte `app/core/scene/CLAUDE.md`;
eine Karte sagt, was wo liegt, eine Regel, was zu halten ist.

- **Oberflächenplatzierung verändert kein Dokument.** `prepare_surface()`
  bestimmt die zusammenhängende Originalfläche und ihre Randtopologie einmal;
  der Worker hält den unveränderlichen Kontext je Netz und Patch im Cache.
  `at_point()`, `point_with_distances()` und `point_with_centre()` verwenden
  dieselbe Flächenprüfung einschließlich Aussparungen. Zwei geradlinige
  Bezugskanten müssen unabhängig sein; Triangulationsdiagonalen und belegte
  Kreisfacetten liefern keine scheinbaren linearen Maße. Auf gekrümmten
  Flächen bleiben Punkt und Normale nutzbar, aber keine ebenen Abstände.
  Mittelpunkt-Offsets zeigen von der Bohrungsmitte zum Ziel entlang U/V.
- **Ein Sichtstrahl wird am Originalnetz geprüft.** `original_surface_hit()`
  ersetzt unbekannte LOD-Zellen durch Originaldreiecke und berücksichtigt alle
  Schnittebenen. Ihre positive Seite entfällt; künstliche Kappen sind kein
  Platzierungsziel. Ergebnisse und freie Normalen bleiben Float64-Werte.
- **Werkzeugvorschau und Operation teilen die Geometrie.** `prepare_tool()`
  liefert einen unveränderlichen `PlacementTool` mit lokalem Körper und
  ausgewähltem Merkmalsversatz. `surface_values(..., prepared_tool=...)`
  berechnet daraus neue Koordinaten ohne weiteren Körperbau; dieser Kontext
  gehört zu genau den gewählten Eingaben. `placement_tool()` bleibt der
  kompatible reine Mesh-Zugriff. Mündung oder Basis liegt bei null. Nur der
  temporäre Anzeigeaktor erhält den `frame_of()`-Rahmen am Treffer. Winkel,
  Einsenkung und Schnittspiegelung stecken bereits im Werkzeug. Bausteine
  deklarieren ihre Richtungsfelder über `normal_fields()`, damit gleichnamige
  Rezeptmaße erhalten bleiben. Beim Merkmalsversetzen ist `source` zusammen
  mit `feature` Pflicht; vollständige Bohrketten bilden ein Werkzeug.

- **Vergebene Merkmalskennungen bleiben reserviert.** Die Auswertung führt
  `SceneObject.reserved_feature_ids` über Zwischenoperationen fort und
  verhindert eine neue Zuordnung gelöschter Namen. Cache und Objekthash
  tragen die sortierte Sammlung; ein Projekt rekonstruiert sie aus den Ops.
- **Der Ergebniscache versioniert geometrische Auskünfte.** Alte Einträge
  ohne den aktuellen Formatstand sind Fehltreffer. Auch Änderungen erzeugter
  Geometrie und Merkmalsmetadaten gehören zu dieser Kompatibilitätsgrenze.
  Ein exakter mitgeführter
  Innenraum zählt zum Speicherbudget und zur Objektidentität.

- **Die Merkmalerkennung nimmt bis zu eine Million Dreiecke je Körper an.**
  `FEATURE_LIMIT_TRIANGLES` begrenzt die Auswertung; Importhinweise und
  Generator-Reduktion lesen dieselbe Grenze. Karten, Darstellung und die
  höchstens tausend zuzuordnenden Merkmale haben eigene Leistungsbudgets.
  Eine Anhebung wird an echten feinen Netzen einschließlich der oberen
  Gegenprobe gemessen; die Geometrie wird für die Erkennung nicht reduziert.
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
- **Keine absoluten Pfade** in der Projektdatei (Regel 12), **kein
  ausführbarer Code** darin (Regel 13).
- Format geändert? Dann alle fünf Schritte: Version, Migration,
  Beispieldatei, Test, alte Migrationen behalten.

## Test

Kennzahlen gegen eine Datei aus `tests/data/`, nicht gegen ein selbst
erzeugtes Ergebnis. Bei Geometrie zuerst der Test, dann die Umsetzung. Ein
neues Fehlerbild wird eine Testdatei, kein Sonderfall im Code.
