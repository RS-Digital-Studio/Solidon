# Konzept — Organische Modellierung (P16)

**Anlass:** Die Frage, ob Solidon organische Formen und Figuren nicht nur
generieren, sondern *machen* kann — mit Sculpting-Pinsel, Subdivision,
Symmetrie, Displacement und Posing. Ausdrücklicher Auftrag dazu: Regel 2
ändern.

**Ergebnis in drei Sätzen.** Regel 2 muss geändert werden, aber anders und
weniger tief als erwartet: Das Hindernis ist nicht das Op-Monopol auf
Geometrie, sondern eine unausgesprochene Nebenannahme darin — *eine Geste =
eine Operation*. Die Skizze hat diese Annahme bereits gebrochen und liefert das
Muster; Sculpting folgt ihr. Der teure Teil des Vorhabens ist nicht die Regel
und nicht die Geometrie — beides ist gemessen und tragfähig —, sondern die
Kundenkreis-Entscheidung aus §17.

> **Stand 13.08.2026 — entschieden.** Robert hat die vier offenen Fragen
> beantwortet: **Figuren werden dazugenommen**, **Posing wird mitgenommen**,
> Käfigmodellierung „wenn sinnvoll", und der Weg ist „sauber abarbeiten,
> verifizieren, optimieren". Das Ziel darüber: *die beste Anwendung für den
> 3D-Druck werden.* §17 ist entsprechend neu geschrieben, §18 sagt, was die
> Erweiterung außerhalb des Codes kostet. **P16.1 ist umgesetzt** (Regel 2 neu,
> `tests/test_gesture_ops.py`, 26 Tests grün).

---

## Inhalt

**Grundlage** — §1 Auftrag · §2 Ist-Zustand · §3 Der eigentliche Konflikt
**Entscheidungen** — §4 A–N · §5 Regel 2 neu · §6 Bauplan
**Die fünf Fähigkeiten** — §7
**Einbettung** — §8 Oberfläche · §9 Dateiformat · §10 Leistung · §11 Agent · §12 Druckbarkeit
**Leitplanken** — §13 Nicht-Ziele · §14 Risiken
**Umsetzung** — §15 Pakete · §16 Abnahme · §17 Positionierung · §18 Kosten außerhalb des Codes

---

## §1 Auftrag und Abgrenzung der Frage

Fünf Fähigkeiten sind benannt: **Sculpting-Pinsel, Subdivision-Modellierung,
Symmetriemodus, Displacement über Höhenfeld, Posing.** Sie gehören nicht
zusammen, weil sie technisch verwandt wären — sie gehören zusammen, weil sie
denselben Satz beantworten: *„Diese Form kann ich nicht bemaßen, ich muss sie
sehen und anfassen."*

Das ist die Gegenrichtung zu allem, was Solidon bisher ist. Bisher gilt: Eine
Form entsteht aus Maßen, und wer sie ändert, ändert eine Zahl. Organische
Modellierung sagt: Eine Form entsteht aus Gesten, und wer sie ändert, macht
eine weitere Geste. Beide Sätze sind richtig, und das Konzept muss sie in
einem Dokument koexistieren lassen, ohne dass einer den anderen auffrisst.

Was hier **nicht** verhandelt wird: Die Generierung über ComfyUI (§27) bleibt,
wie sie ist. Sie steht neben diesem Konzept, nicht darin.

---

## §2 Ist-Zustand — verifiziert, nicht vermutet

Jede Aussage hier ist im Code nachgeschlagen. Wo eine Zahl steht, ist sie
gemessen.

### 2.1 Was heute organisch schon geht

| Fähigkeit | Wo |
|---|---|
| Skizze mit `line`, `circle`, `arc`, **`spline`** | `app/ui/sketch_editor.py:1434` |
| `sketch_revolve`, `sketch_sweep`, `sketch_loft` | `app/core/sketch/ops.py` |
| `smooth_mesh` (Taubin-Filter) | `app/core/geom/mesh_ops.py:93` |
| `remesh_mesh` (`subdivide_to_size`, `subdivide`) | `app/core/geom/mesh_ops.py:102–137` |
| `decimate_mesh` | `app/core/geom/mesh_ops.py:76` |
| Texturen als echte Geometrie (Voronoi, Rauschen, Wabe) | `app/core/geom/texture_ops.py` |
| Gitterfüllung als Isofläche (Gyroid) | `app/core/geom/lattice.py` |
| `mirror_object` | `app/core/geom/ops.py` |
| `fillet_edges`, `draft_faces` (B-Rep) | `app/core/brep/ops.py` |

Das trägt organische **Flächen an technischen Teilen**. Es trägt keine Figur.
Der Unterschied ist nicht graduell: Ein Griff ist ein Rotationskörper mit
Verrundung, eine Figur ist eine Fläche ohne erzeugende Regel.

Bemerkenswert ist die Zeile `remesh_mesh`: Subdivision existiert bereits als
Op — nur als Vernetzungswerkzeug gedacht, nicht als Modellierparadigma. §7.2
knüpft daran an, statt daneben zu bauen.

### 2.2 Wie Regel 2 heute wirkt

> **2. Keine Geometrieänderung außerhalb einer Op** — auch nicht „kurz" im
> Viewport, auch nicht im Agenten.

Die Regel schützt vier Dinge auf einmal, und alle vier sind es wert:
Rücknehmbarkeit, Reproduzierbarkeit beim Wiederöffnen, Nachvollziehbarkeit im
Verlauf, und die Gleichbehandlung von Mensch, Menü, Kommandozeile und Agent
(Leitprinzip 1).

Was sie **nicht** sagt, aber alle bisherigen Umsetzungen annehmen: dass eine
Nutzergeste einer Operation entspricht. `app/ui/paint_bar.py` schreibt diese
Annahme sogar hin:

> „Jeder Klick ist eine Operation im Stapel — genau das macht das Malen Strich
> für Strich rücknehmbar."

Beim Bemalen trägt das, weil der Pinsel über Kantenerkennung ganze Flächen auf
einmal nimmt (`paint.py:87`, `_walk`): Ein Deckel ist mit drei Klicks bemalt.
Bei Sculpting trägt es nicht. Eine Figur sind mehrere tausend Striche, und ein
Verlauf mit viertausend Einträgen ist kein Verlauf mehr.

### 2.3 Die zwei Präzedenzfälle — einer trägt, einer nicht

**`paint_slot` trägt nicht** als Vorbild, aber es liefert einen wichtigen
Baustein: Der Strich speichert **Weltkoordinaten** (`x`, `y`, `z` als
Parameter, `paint.py:134–151`), keinen Dreiecksindex. Damit übersteht er eine
Änderung der Vernetzung darunter. Das ist genau die Eigenschaft, die ein
Sculpting-Strich braucht, und sie ist hier schon erprobt.

**Die Skizze trägt.** Bauplan §30.1 sagt:

> „Die Skizze lebt als Parameterwert der Operation, die sie verbraucht
> (`sketch_extrude`, `sketch_pocket`, …). Bearbeiten heißt `change_params` auf
> dem Schritt im Verlauf — dieselbe Regel wie für jede andere Zahl (§15). **Es
> entsteht kein zweiter Dokumentbegriff neben dem Stack.**"

Umgesetzt als `kind="sketch"` (`app/core/registry/params.py:229`): ein
JSON-Text in einem Parameter, `placement="advanced"`, aus dem Agentenschema
ausgeschlossen. Ein Skizzeneditor mit hunderten Klicks erzeugt **einen**
Op-Eintrag.

**Damit ist die Frage im Grunde beantwortet.** Solidon hat bereits einen
Editor, der eine unbegrenzte Zahl von Gesten in eine Operation faltet. Regel 2
steht dem nicht im Weg — sie wurde nur nie so gelesen.

### 2.4 Was die Geometriebibliothek kann

Nachgesehen in der installierten `manifold3d`:

| Funktion | Wofür |
|---|---|
| `warp_batch(f)` | Vertex-Verschiebung über ndarray — **Sculpting und Displacement** |
| `level_set(f, bounds, edge)` | SDF → Netz — weiches Verschmelzen, Metaballs |
| `refine(n)`, `refine_to_length(l)` | Subdivision |
| `smooth_out(min_sharp_angle)` | Tangenten für gekrümmte Interpolation |
| `calculate_curvature(g, m)` | Krümmung je Vertex — Werkzeug „Aufblasen/Glätten" |
| `mirror(normal)` | Symmetrie |
| `set_properties(n, f)` | Eigenschaften je Vertex — Sculpting-Masken |

Alles Nötige ist da. Zwei Eigenschaften von `warp_batch` sind für den Entwurf
entscheidend und stehen so in seiner Dokumentation:

- **„does not change the topology"** — Vertices verschieben ja, neue erzeugen
  nein. Die Auflösung muss also *vor* dem Sculpting stimmen (Entscheidung E).
- **„It is easy to create a function that warps a geometrically valid object
  into one which overlaps, but that is not checked here"** — Selbstdurch-
  dringung ist möglich und wird nicht gemeldet. Die Prüfung muss danach laufen
  (Entscheidung L).

### 2.5 Gemessen

Prüfkörper: Kugel mit 65 538 Vertices / 131 072 Dreiecken. Bestwert aus drei
Läufen.

| Verfahren | Zeit |
|---|---|
| `warp_batch`, ein Strich (16k Vertices) | 7,4 ms |
| **100 Striche sequenziell**, je ein `warp_batch` (16k Vertices) | **747 ms** |
| 100 Striche **akkumuliert**, ein Durchgang (65k Vertices) | 57 ms |
| 1 000 Striche akkumuliert (65k Vertices) | 252 ms |
| **5 000 Striche akkumuliert** (65k Vertices) | **586 ms** |
| `level_set`, 80-mm-Würfel, 1,0-mm-Gitter | 240 ms → 61 944 Dreiecke |
| `refine(2)` auf 131 072 Dreiecke | 204 ms → 524 288 Dreiecke |

**Das ist der wichtigste Befund des ganzen Dokuments.** Die naive Wiedergabe —
je Strich ein Durchgang über alle Vertices — kostet bei 100 Strichen auf einem
Viertel der Vertices bereits 747 ms und wächst mit dem Produkt aus Strichzahl
und Vertexzahl. Bei 200 000 Vertices und 1 000 Strichen wären das rund anderthalb
Minuten, und die Op wäre unbrauchbar.

Ein **akkumulierter Durchgang** — KD-Baum über die Vertices, dann alle Striche
in einem `warp_batch` — bleibt bei 5 000 Strichen unter 600 ms und damit
innerhalb des Budgets aus §31 („Parameteränderung → sichtbares Ergebnis unter
2 s"). Der Faktor ist etwa sechzig. Das entscheidet zwischen „geht nicht" und
„geht", und es hat einen Preis, der als Entscheidung C offengelegt wird.

---

## §3 Der eigentliche Konflikt

Nicht Regel 2. Drei andere Dinge:

**(1) Der Op-Stack ist wertorientiert, Sculpting ist gestenorientiert.**
Der Stapel wird neu gerechnet, wenn sich etwas darunter ändert
(`hashing.py:65`, `operation_hash`). Ein Sculpting-Strich ist aber an *die
Fläche gebunden, auf der er gemacht wurde*. Ändert jemand darunter einen
Durchmesser, ist die Fläche eine andere — und die Striche landen woanders. Das
ist ein echter, nicht wegzudefinierender Bruch. Entscheidung B mildert ihn,
löst ihn nicht; §14 sagt, was das im Betrieb heißt.

**(2) Bauplan §2.5 verbietet Betriebsarten.**

> „Keine Betriebsarten, keine Umschaltung zwischen ‚Bearbeiten' und
> ‚Konstruieren'. Es gibt einen Zustand, und der ist die Szene."

Ein Sculpting-Modus sieht danach aus. Entscheidung J zeigt, warum er es nicht
ist — und der Skizzenmodus aus P15 ist der Beleg, dass die Grenze schon einmal
sauber gezogen wurde.

**(3) Leitprinzip 5 verbietet dem Agenten Koordinaten.**

> „Die KI erzeugt niemals Koordinaten. Sie verweist auf erkannte Features,
> benutzt Projektparameter und setzt geprüfte Bausteine ein."

Ein Sculpting-Strich *ist* eine Koordinate. Entscheidung K zieht daraus die
Konsequenz, und sie ist unbequem: Der Agent kann nicht sculpten. Nie.

---

## §4 Design-Entscheidungen

### A — Ein Sculpting-Vorgang ist **eine** Operation

`sculpt_strokes` mit einem Parameter `strokes` vom `kind="strokes"`, gebaut
nach dem Vorbild von `kind="sketch"`. Der Parameter trägt die Strichliste;
der Editor bearbeitet ihn; `change_params` schreibt ihn zurück.

Verworfen:

- **Eine Op je Strich** (Muster `paint_slot`) — viertausend Verlaufseinträge.
- **Destruktives Überschreiben des Netzes** — bricht Leitprinzip 2 und macht
  jede Op darunter unveränderbar.
- **Ein zweiter Dokumentbegriff neben dem Stack** — §30.1 hat das für Skizzen
  ausdrücklich abgelehnt, und der Grund gilt hier unverändert.

**Undo innerhalb der Sitzung** läuft im Editor auf der Strichliste, nicht über
`History`. Das ist dieselbe Trennung wie beim Skizzeneditor: Der Editor hat
sein eigenes Rückgängig, die Transaktion entsteht beim Verlassen. Regel 16
bleibt gewahrt — der ganze Vorgang ist eine Transaktion.

### B — Striche im Raum, nicht auf Vertices

Ein Strich ist:

```
{ p: [x,y,z], n: [nx,ny,nz], r: float, s: float, tool: str, sym: int, cut: bool }
```

Punkt, Flächennormale zum Zeitpunkt des Strichs, Radius, Stärke, Werkzeug,
Symmetrieflaggen, erzwungene Etappengrenze (C). **Kein Vertex-Index, keine
Dreiecksnummer.** Präzedenzfall `paint_slot`, dessen Klickpunkt aus demselben
Grund in Weltkoordinaten liegt.

Folge: Eine Änderung der Vernetzung darunter (Dezimierung, Reparatur, andere
Qualitätsstufe) lässt die Striche gültig. Eine Änderung der *Form* darunter
lässt sie an der alten Stelle im Raum stehen — dort ist dann eventuell keine
Fläche mehr. §14 R2 sagt, was dann passiert.

### C — Akkumuliertes Offsetfeld statt sequenzieller Wiedergabe

Alle Striche werden in **einem** `warp_batch` ausgewertet: KD-Baum über die
Vertices, je Strich eine Kugelabfrage, Gewichte summieren, einmal verschieben.
Gemessener Gewinn: Faktor ~60 (§2.5).

**Der Preis, offen benannt:** Die Striche werden dadurch *kommutativ*. Zweimal
über dieselbe Stelle zu fahren addiert zwei Gewichte auf die
Ausgangsgeometrie, statt den zweiten Strich auf das Ergebnis des ersten zu
setzen. Wer aus ZBrush kommt, merkt den Unterschied bei starken, überlappenden
Strichen.

Das wird abgefedert, nicht versteckt:

- Die Verschiebung folgt der **Ursprungsnormale**, nicht der laufenden — dann
  ist die Summe der Offsets für moderate Stärken eine sehr gute Näherung.
- Werkzeuge, die sich nicht sinnvoll akkumulieren lassen (**Glätten**,
  **Aufblasen**), sind reihenfolgeabhängig und laufen in **Etappen**: Die
  Strichliste zerfällt an jedem solchen Strich in einen Abschnitt, und
  Abschnitte werden sequenziell ausgewertet. Ein Glättungsstrich kostet also
  einen zusätzlichen Durchgang — das ist der ehrliche Preis, und die
  Statusleiste zeigt die Zahl der Etappen.
- **Eine Etappe lässt sich erzwingen** (Robert, 13.08.2026). Jeder Strich kann
  eine Etappengrenze setzen, unabhängig von seinem Werkzeug: Wer zweimal
  übereinander fahren und dabei das Ergebnis des ersten Zuges treffen will,
  kauft sich die exakte Reihenfolge stückweise, statt sie für die ganze Sitzung
  zu bezahlen. Der Strich trägt dafür ein eigenes Feld; ein erzwungener
  Abschnitt kostet denselben zusätzlichen Durchgang wie ein Glättungsstrich.
- Ist die Etappenzahl über zwanzig, schlägt der Editor das **Einbacken** vor
  (Entscheidung D).

### D — Einbacken als ausdrückliche Handlung, nie automatisch

Ab 20 Etappen oder 20 000 Strichen bietet der Editor an, den bisherigen Stand
als neues Quellnetz in `sources/` festzuschreiben: Die Strichliste beginnt neu,
die alte bleibt in der eingebackenen Op erhalten.

Das ist ein **bewusster Verlust an Änderbarkeit** und darum eine Handlung mit
Nachfrage — der einzige Fall in diesem Konzept, in dem Regel 19 („keine
Bestätigungsdialoge vor rücknehmbaren Handlungen") nicht greift, weil die
Handlung eben nicht folgenlos rücknehmbar ist. Sie wird als das benannt, was
sie ist, mit dem Satz, was danach nicht mehr geht.

### E — Keine dynamische Tessellierung. Auflösung ist eine eigene Operation davor

`warp_batch` ändert die Topologie nicht (§2.4). Wer eine feine Falte in ein
grobes Netz sculpten will, braucht vorher Dreiecke.

Statt Dyntopo im Pinsel: die bestehende `remesh_mesh` davor, und der Editor
**misst und sagt es**. Beim Öffnen einer Sculpting-Sitzung steht in der Leiste
die mittlere Kantenlänge; ist der Pinselradius kleiner als das Doppelte davon,
erscheint der Hinweis mit der Handlung *[Feiner vernetzen]* — Fehler als
Vorschlag (§2.7), bevor der Fehler passiert.

Gründe gegen Dyntopo: Es macht die Auswertung nichtdeterministisch bezüglich
der Strichreihenfolge, es bricht Entscheidung C, und es macht aus jedem Strich
eine Topologieänderung, die kein Cache mehr überspringen kann.

**In P16.2 kam eine zweite Vorbedingung dazu, die vorher niemand genannt
hatte.** Der Versuch, `generated_figure.stl` aus dem Korpus direkt zu sculpten,
lieferte ein *leeres* Manifold: Die Datei trägt absichtlich die Fehler eines
Generators (fehlende Dreiecke, verdrehte Normalen, ein loser Splitter), und
`manifold3d` nimmt kein Netz an, das kein Volumen ist. Nach der Kette aus
`GENERATED_REPAIR` sind es 3 368 Dreiecke und wasserdicht, nach `refine(8)`
215 552 — Sculpting-Auflösung.

Die Kette für Weg 3 heißt damit vollständig: **generieren → reparieren →
verfeinern → sculpten.** Der Editor prüft beim Öffnen beides, Volumen *und*
Auflösung, und bietet die fehlenden Schritte als Handlung an, statt an einem
leeren Ergebnis zu scheitern.

### F — Symmetrie ist eine Eigenschaft der Operation, kein Modus

Kein „Symmetriemodus" im Fenster. Die Op `sculpt_strokes` trägt
`symmetry: str` (`none | x | y | z | xy | xz | yz | xyz` und `radial:n`), der
Editor hat dafür eine Umschaltgruppe in seiner Leiste, und jeder Strich merkt
sich in `sym`, ob er gespiegelt gemeint war.

Zwei Folgen, die den Ausschlag geben: Die Symmetrie überlebt das Speichern und
ist nachträglich änderbar — man kann eine ganze Sitzung nachträglich
symmetrisch machen. Und sie kostet keinen Menüpunkt und keinen der acht
erlaubten Umschalter aus `tests/test_interface_limits.py`.

### G — Displacement ist eine eigene Operation, kein Pinselwerkzeug

`displace_image`: Bild aus `sources/` (mit Prüfsumme, §16.1), Projektionsart
(planar, zylindrisch, sphärisch, per Fläche), Stärke, Mittelwert, Glättung.
Rechnet über `warp_batch` mit bilinearer Abtastung.

Getrennt vom Pinsel, weil es einen anderen Charakter hat: Es ist ein Wert, kein
Handgriff. Ein Displacement ändert man, indem man eine Zahl ändert — genau der
Fall, für den der Stapel gemacht ist. Es schließt an `texture_ops` an, ist aber
das Gegenstück dazu: Die Texturen dort sind exakte Gitter aus gutem Grund
(„wer dieselbe Form über ein Höhenfeld abtastet, bekommt an jeder Kante die
Auflösung des Rasters"), hier *ist* das Höhenfeld der Zweck.

**Dieselbe Prüfung wie bei den Texturen** (`texture_ops`, E1): Ein Relief
flacher als eine Schichthöhe oder schmaler als die Düse wird nicht gedruckt.
Das steht im Druckerprofil und wird als Befund gemeldet, bevor jemand eine
Stunde wartet.

### H — Subdivision: zwei verschiedene Dinge, eines davon vertagt

**H1 — Subdivision als Glättungsverfahren.** `subdivide_surface`:
`smooth_out(min_sharp_angle)` + `refine_to_length(l)`. Scharfe Kanten über dem
Winkel bleiben, alles darunter wird interpoliert glatt. Das ist eine Op nach
Checkliste, klein, und der größte Nutzen je Aufwand im ganzen Konzept.

**H2 — Subdivision-Modellierung mit Käfig** (Box-Modeling: ein grobes
Kontrollnetz bearbeiten, das Ergebnis ist die geglättete Fläche) ist **kein
Werkzeug, sondern ein Modellierparadigma**. Es braucht Vertex-, Kanten- und
Flächenauswahl, Extrudieren, Schleifen, Messerschnitt, Verschmelzen — einen
Editor vom Umfang des Skizzeneditors, und der war eine ganze Phase.

**Nachgeordnet, mit Prüfpunkt — nicht vage vertagt.** Der Auftrag lautet „wenn
es sinnvoll ist mitnehmen", und die ehrliche Antwort ist: *wahrscheinlich
nicht, aber die Messung entscheidet.* Drei Gründe:

- **Der Zweck des Käfigs ist das Basisnetz.** Wer eine Figur macht, braucht
  eine grobe Form zum Sculpten. Dafür gibt es in diesem Konzept bereits einen
  Weg, der zur Architektur passt: Primitive plus `blend_union` (N) sind unser
  Gegenstück zu ZSpheres und Dynamesh — parametrisch, im Stapel änderbar, drei
  Zahlen statt hundert Vertices.
- **Für harte Oberflächen haben wir den besseren Weg schon.** Käfigmodellierung
  konkurriert bei Gehäusen und technischen Formen mit den Skizzen aus P13 — und
  verliert dort, weil eine Skizze bemaßt ist und ein Käfig nicht.
- **Die Reihenfolge ist nicht umkehrbar.** Ein Käfigeditor nach dem
  Sculpting-Editor erbt dessen Auswahl-, Symmetrie- und Vorschauwerkzeuge.
  Umgekehrt entstünde beides doppelt.

**Prüfpunkt nach P16.6** (P16.11 im Plan): Wenn sich mit Primitiven,
`blend_union` und dem Pinsel kein brauchbares Basisnetz für die Figuren aus dem
Korpus bauen lässt, kommt der Käfig — und dann als eigene Phase mit eigenem
Konzept, nicht als Anhängsel.

**Das Kriterium steht seit P16.11 als Test** (`tests/test_base_mesh.py`),
geschrieben bevor P16.5 begann, damit es hinterher nicht passend gemacht wird.
Fünf Bedingungen an ein „brauchbares Basisnetz":

1. ein Körper ohne Löcher — wasserdicht, eine Komponente, Euler-Charakteristik
   zwei;
2. höchstens fünfzehn Schritte;
3. nach dem gleichmäßigen Vernetzen eine Kantenstreuung unter 0,5, sonst wirkt
   der Pinsel an verschiedenen Stellen verschieden;
4. Maße bleiben Zahlen — ein längerer Arm ist eine Parameteränderung;
5. der Pinsel bringt die grobe Form zur Figur, ohne dass Topologie fehlt.

**Vier davon sind erfüllt**, gemessen an einer humanoiden Grundfigur aus sechs
Primitiven und fünf Verschmelzungen: elf Schritte, eine Komponente, Euler
zwei. Nur die fünfte braucht P16.5 und steht offen. Der Käfig bleibt damit
nachgeordnet.

Der Prüfpunkt hat sich beim ersten Lauf bezahlt gemacht: Er meldete fünf
Komponenten statt einer, und die Ursache lag in P16.4 — das Vorzeichen des
Abstandsfeldes kam aus gemittelten Eckpunktnormalen, die an einer Zylinderkante
schräg stehen. Ein Rohr war nach dem Verschmelzen acht Millimeter länger als
vorher, bei richtigem Volumen und geschlossener Hülle; kein Test von P16.4
konnte das sehen.

### I — Posing: Skelett als Parameter, Vorwärtskinematik, automatische Gewichte

`pose_armature` mit zwei Parametern: `armature` (Knochenbaum:
Name, Kopf, Fuß, Elternteil) und `pose` (je Knochen drei Winkel). Skinning-
Gewichte werden gerechnet, nicht gespeichert — Abstand zum Knochensegment mit
Abfall, deterministisch aus der Geometrie.

Drei Dinge machen das im Vergleich zu einem Animationsprogramm klein:

- **Eine Pose, keine Animation.** Gedruckt wird ein Zustand. Keine Zeitachse,
  keine Interpolation, keine Kurven. Das ist der größte Streichposten.
- **Vorwärtskinematik reicht.** Inverse Kinematik ist Komfort beim Animieren
  langer Ketten; bei einer einzigen Pose an einem Modell mit acht Knochen ist
  sie es nicht wert.
- **Ein Gelenkwinkel darf ein Projektparameter sein** (§13). Das ist der Punkt,
  an dem Posing zu Solidon gehört statt zu Blender: `=@arm_angle` in einer
  Pose, und die Passung am Sockel rechnet mit.

**Ehrlich zur Einordnung:** Das ist das größte Paket und das am weitesten vom
heutigen Kundenkreis entfernte. Es steht in §15 bewusst am Ende und ist der
erste Kandidat zum Streichen, wenn die Phase zu lang wird.

### J — Der Sculpting-Modus ist ein Werkzeugmodus, kein Betriebsmodus

Bauplan §2.5 verbietet „Betriebsarten, Umschaltung zwischen ‚Bearbeiten' und
‚Konstruieren'". Die Grenze verläuft dort, wo der Skizzenmodus aus P15 sie
schon zieht:

| Betriebsmodus (verboten) | Werkzeugmodus (erlaubt) |
|---|---|
| Global, gilt für die ganze Anwendung | Gilt für **eine Operation**, die gerade bearbeitet wird |
| Man ist darin, bis man umschaltet | Man geht hinein, macht die Sache, geht heraus |
| Die Szene bedeutet je nach Modus etwas anderes | Die Szene bleibt die Szene |
| Funktionen verschwinden aus den Menüs | Menüs bleiben, was nicht anwendbar ist, ist ausgegraut |

Die Sculpting-Sitzung ist die rechte Spalte, Zeile für Zeile — sie ist die
Bearbeitung des `strokes`-Parameters einer bestimmten Op, sichtbar im Verlauf,
verlassbar mit Escape. Genau wie der Skizzeneditor.

### K — Der Agent bekommt Sculpting nicht

`kind="strokes"` wird wie `kind="sketch"` aus `json_schema()` ausgelassen, und
die Sitzung lehnt ein trotzdem mitgeschicktes Argument ab (zwei Ebenen, weil
eine Lücke im Schema kein Verbot ist — bestehendes Muster aus
`.claude/rules/operationen.md`).

Der Agent darf: die Op anlegen, ihre Symmetrie setzen, die Auflösung
vorbereiten, das Ergebnis prüfen, ein Displacement mit Werten belegen, eine
Pose über Projektparameter ändern. Er darf nicht: Striche erzeugen.
Leitprinzip 5, ohne Ausnahme.

Was er stattdessen tut, wenn jemand ihn darum bittet, gehört in die
Regelsammlung: Er sagt, dass er es nicht kann, und öffnet den Editor an der
richtigen Stelle. Das ist die bestehende Haltung — nicht raten, sondern sagen,
was geht.

### L — Druckbarkeit wird während des Sculptings geprüft, nicht danach

`warp_batch` prüft Selbstdurchdringung nicht (§2.4), und ein Pinsel macht
mühelos Wände dünner als die Düse. Ohne Gegenmaßnahme entsteht genau das
Ergebnis, das wir den Generatoren vorwerfen: eine schöne Form, die nicht
druckbar ist.

Also läuft die bestehende Wandstärkenkarte (`perceive/maps.py`) **in der
Sculpting-Sitzung mit**, in Entwurfsqualität, im Hintergrund, mit einer
Verzögerung nach dem letzten Strich. Zu dünne Stellen erscheinen als Einfärbung
*und* als Zahl in der Leiste (Regel 18 — nie Bedeutung allein über Farbe).

**Das ist der eigentliche Grund, warum dieses Vorhaben zu Solidon gehört und
nicht zu Blender.** Es ist kein Beiwerk, sondern §17.

### M — Ein neuer Op-Bereich, keine neue Kategorie im Menü

`tests/test_interface_limits.py` erlaubt höchstens neun Menüs und zwölf Zeilen
je Menü. Sechs neue Ops (`sculpt_strokes`, `subdivide_surface`,
`displace_image`, `pose_armature`, `blend_union`, `remesh_uniform`) passen
nicht ohne Weiteres irgendwo hinein.

Entscheidung: eine **Kategorie** `organic` im Register, im Menü **„Formen"**,
und der bestehende Menüaufbau wird dafür geprüft, nicht erweitert. Die Grenzen
sind vor dem Wachstum eingezogen worden (P15) und gelten auch für dieses
Wachstum.

### N — Weiches Verschmelzen als Zugabe, weil es fast geschenkt ist

`blend_union`: zwei Körper mit einem Radiusparameter ineinander übergehen
lassen, gerechnet über die geglättete Maximumsfunktion der beiden
Abstandsfelder. **Umgesetzt in P16.4 — „fast geschenkt" war es nicht, und der
Rechenweg ist ein anderer geworden.**

`level_set` ruft eine Python-Funktion je Rasterpunkt auf. Die gemessenen
240 ms galten einer analytischen Formel darin; mit zwei interpolierten
Abstandsfeldern sind es 25 Sekunden. Marching Cubes über
`skimage` auf dem **vektorisierten** Feld liefert dieselbe Isofläche in
200 ms — es ist derselbe Gedanke, nur ohne den Aufruf je Punkt.

Das Abstandsfeld eines Netzes war der eigentliche Brocken, und beide
naheliegenden Wege scheitern:

| Weg | Ergebnis |
|---|---|
| `voxelized().fill()` + Distanztransformation | acht Prozent zu viel Volumen — markiert jede berührte Zelle, misst ab Zellmitte |
| `Trimesh.contains` fürs Vorzeichen | richtig, aber Zugriffsverletzung in `rtree` nach 75 000 Punkten |
| **KD-Baum auf verdichteter Oberfläche, Vorzeichen aus der Normale** | **0,9956 an der Prüfkugel, 24 mal schneller als die exakte Abfrage** |

Die dritte Zeile ist die Umsetzung. `workers=-1` bringt weitere 6,3 — 1,5
statt 9,6 Sekunden bei identischem Ergebnis.

**Ein Rasterverfahren hat eine Falle, die kein Lehrbuch nennt:** Ein
achsparalleler Quader mit runden Maßen legt seine Flächen genau auf die
Rasterpunkte. Dort ist das Feld exakt null, es gibt keinen
Vorzeichenwechsel, und Marching Cubes spannt entartete Dreiecke auf — 793
Bruchstücke statt eines Körpers. Das Raster liegt deshalb um 0,37 Zellen
versetzt.

**Und eine Bedienauskunft, die sonst niemand findet:** Ein Spalt zwischen zwei
Körpern wird überbrückt, wenn der Übergang etwa dreimal so breit ist wie der
Spalt — der Wulst hebt das Feld in der Mitte um ein Viertel der Übergangsbreite
an und muss dort den halben Spalt überwinden. Der Dialogtext sagt es, und wer
zu schmal wählt, bekommt einen Befund statt zweier Körper, die er für einen
hält.

Kategorie `boolean`, nicht `organic` — dieselbe Abwägung wie in §7.2: Wer
„Vereinigen" sucht, findet „Weich verschmelzen" daneben.

Steht nicht im Auftrag, gehört aber hierher: Es ist die einzige Operation im
ganzen Konzept, die *parametrisch* organisch ist — drei Zahlen, kein Handgriff,
voll im Stapel änderbar. Für einen ergonomischen Griff an einem technischen
Teil ist sie das bessere Werkzeug als jeder Pinsel, und sie bedient damit den
**heutigen** Kundenkreis, während der Rest des Konzepts einen neuen anspricht.

---

## §5 Regel 2 — alt und neu

**Heute:**

> **2. Keine Geometrieänderung außerhalb einer Op** — auch nicht „kurz" im
> Viewport, auch nicht im Agenten.

**Neu:**

> **2. Keine Geometrieänderung außerhalb einer Op** — auch nicht „kurz" im
> Viewport, auch nicht im Agenten. Eine Op darf beliebig viele Nutzergesten
> zu einem Schritt zusammenfassen, wenn sie **vollständig aus ihren
> Parametern reproduzierbar** ist: Ein Editor sammelt Gesten in einen
> Parameterwert, das Ergebnis entsteht erst bei der Auswertung. Was der Editor
> zeigt, während er offen ist, ist eine Vorschau und kein Dokumentzustand.

Was sich damit **nicht** ändert, und das ist der größere Teil:

- Geometrie entsteht weiterhin ausschließlich in Ops.
- Jede Änderung ist rücknehmbar, im Verlauf sichtbar und reproduzierbar.
- Der Agent ruft dieselben Funktionen wie die Menüs (Leitprinzip 1).
- Nichts wird destruktiv überschrieben (Leitprinzip 2).

Was sich ändert: Die stille Gleichsetzung von Geste und Schritt fällt. Sie war
nie Teil der Regel — nur ihrer bisherigen Auslegung.

**Neuer Test** `tests/test_gesture_ops.py`: Für jede Op mit einem Sammel-
parameter (`kind` in `sketch`, `strokes`, `armature`) gilt — zweimal auswerten
gibt identische Geometrie; die Op überlebt Speichern und Laden mit gleichem
Ergebnis; der Parameter fehlt im Agentenschema. Ohne diesen Test ist die neue
Regel eine Absichtserklärung. Mit ihm ist sie prüfbar wie die anderen 21.

---

## §6 Was sich am Bauplan ändert

| Stelle | Änderung |
|---|---|
| §1 Leitprinzipien | unverändert — alle neun tragen |
| §2.5 | Satz zum Werkzeugmodus, Abgrenzung nach Entscheidung J |
| §9 Verträge | `Stroke`, `StrokeList`, `Armature`, `Bone`, `Pose` |
| §12 Dateiformat | `format_version` 7 → 8 |
| §25 Operationskatalog | sechs Ops, Kategorie `organic` |
| §31 Leistungsbudget | drei Zeilen (§10) |
| §42 Grenzen | zwei Zeilen zu den Grenzen des Verfahrens |
| **neu §44** | Organische Modellierung — die fachliche Heimat dieses Konzepts |
| Nicht-bauen-Liste | ergänzt um §13 dieses Dokuments |

Die Nicht-bauen-Liste in `AGENTS.md` bleibt in allen bestehenden Punkten
gültig. Insbesondere: keine Verzweigungen im Op-Stack (eine Sculpting-Sitzung
ist keine Verzweigung), kein Plugin-System (keine Pinsel von Dritten).

---

## §7 Die fünf Fähigkeiten

### 7.1 Sculpting-Pinsel

**Werkzeuge — sechs, nicht sechzig.** Konsistenz vor Vollständigkeit
(`AGENTS.md`).

| Werkzeug | Wirkung | Akkumulierbar |
|---|---|---|
| `draw` | Material entlang der Normale auftragen | ja |
| `carve` | dasselbe, negativ | ja |
| `smooth` | Nachbarschaftsmittel | **nein** — Etappe |
| `inflate` | entlang der Normale, gewichtet nach Krümmung | **nein** — Etappe |
| `flatten` | auf die mittlere Ebene des Pinselgebiets ziehen | **nein** — Etappe |
| `pinch` | zur Strichmitte ziehen — Kanten und Falten | ja |

Abfall wählbar (glatt, linear, scharf), Stärke druckabhängig, wenn ein
Grafiktablett Druck meldet — sonst konstant.

**Ablauf.** Op anlegen (Menü, Kürzel oder Kontextmenü an einem Körper) →
Sitzung öffnet, Viewport zeigt Pinselring und Leiste → malen → Escape oder
*[Fertig]* → eine Transaktion. Wieder hinein über Doppelklick auf den
Verlaufseintrag, genau wie bei der Skizze.

**Auswertung.** Strichliste → Etappen zerlegen → je Etappe ein `warp_batch`
mit KD-Baum → Ergebnis in den Cache unter dem Op-Hash. Der Platten-Cache
existiert bereits und ist über Prozesse hinweg stabil (`hashing.py:9–11`).

### 7.2 Subdivision

`subdivide_surface` nach Entscheidung H1. **Umgesetzt in P16.3, und dabei hat
sich der Weg dorthin geändert.**

Der naheliegende Weg — `smooth_out(min_sharp_angle)` + `refine_to_length(l)` —
bricht bei CAD-Netzen zusammen. `smooth_out` leitet die Tangenten aus der
Dreiecksgeometrie ab und fasst dabei je zwei koplanare Dreiecke zu einem
Viereck zusammen, dessen Diagonale beim Verfeinern übersprungen wird. Wo
*jede* ebene Fläche aus genau zwei Dreiecken besteht — also bei so ziemlich
jedem Netz, das aus einem CAD-Programm kommt —, ist das jede Fläche:
`plate_holes` verlor damit ein Sechstel seines Volumens (31 322 → 25 832 mm³)
und bekam 2 772 Kanten der Länge null. Es meldete sich weiter als wasserdicht;
keine Prüfung danach hätte das gefangen.

`calculate_normals(0, angle)` + `smooth_by_normals(0)` + `refine_to_length(l)`
leitet die Tangenten aus den Eckpunktnormalen ab, kennt keine Vierecke und
hält die Form exakt. Geglättet wird darüber genauso gut: das Ikosaeder mit
einer Unterteilung geht von 29 270 auf 33 436 mm³, bei 33 510 möglichen.

Parameter: **Zielkantenlänge und Kantenwinkel — zwei, nicht drei.** Die oben
genannten „Iterationen" sind bei diesem Verfahren wirkungslos: Eine zweite
Runde auf einem Netz, das die Zielkantenlänge bereits erreicht hat, erzeugt
keine neuen Punkte und interpoliert deshalb nichts.

`remesh_uniform` — gleichmäßige Kantenlängen ohne Formänderung, als
Vorbereitung für §7.1 (Entscheidung E). Ob es in `remesh_mesh` hineingehört,
war die Prüffrage von P16.3, und die Antwort ist **nein, gemessen**: Die
Streuung der Kantenlängen von `plate_holes` liegt vor `remesh_mesh` bei 2,224
und danach bei 2,224. Die Operation teilt jede Kante gleich oft und nimmt das
Verhältnis zwischen der längsten und der kürzesten damit mit — sie macht das
Netz feiner, nicht gleichmäßiger. Bezahlt wird das mit 3 260 416 Dreiecken für
1,5 mm; `remesh_uniform` (`simplify` + `refine_to_length`) kommt auf 30 648 bei
einer Streuung von 0,41.

Zwei verschiedene Zusagen, deshalb zwei Operationen: Die eine teilt nur und
verschiebt nie einen Punkt. Die andere teilt *und* fasst zusammen, in einer
zugesagten Schranke, und sagt, was das gekostet hat.

**Kategorie `mesh`, nicht `organic`** — Abweichung von Entscheidung M, mit
Absicht. Beide stehen neben ihren Geschwistern `remesh_mesh`, `smooth_mesh`
und `decimate_mesh`; wer „Neu vernetzen" sucht, findet „Gleichmäßig vernetzen"
daneben. Über `organic` entscheidet P16.5, wenn die vier wirklich neuen Ops
dazukommen und die Frage sich stellt, die M eigentlich beantwortet: wohin mit
sechs Einträgen, die nirgends hineinpassen.

Käfigmodellierung: vertagt, Begründung in H2.

### 7.3 Symmetriemodus

Kein Modus, sondern `symmetry` an `sculpt_strokes` (Entscheidung F). Ebenen
X/Y/Z einzeln und kombiniert, dazu radial mit Zähligkeit. Der Pinselring zeigt
die gespiegelten Positionen mit.

Die Spiegelebene ist der **Objektursprung**, nicht der Schwerpunkt — der
Schwerpunkt wandert beim Sculpten, und eine Symmetrieebene, die sich unter der
Hand bewegt, ist die Sorte Überraschung, die Vertrauen kostet.

### 7.4 Displacement über Höhenfeld

`displace_image` nach Entscheidung G. Bild in `sources/` mit Prüfsumme,
Projektion planar/zylindrisch/sphärisch/per Fläche, Stärke, Mittelwert,
Glättung, Kachelung.

Prüfung gegen das Druckerprofil vor der Rechnung: Ein Relief unter einer
Schichthöhe oder unter einer Düsenbreite wird als Befund gemeldet.

### 7.5 Posing

`pose_armature` nach Entscheidung I. Dazu ein kleiner Skeletteditor: Knochen
setzen, Kette bilden, Namen vergeben. Gewichte gerechnet, nicht gespeichert.

Nach dem Posieren steht in der Leiste, was der Druck davon hält: Ein
ausgestreckter Arm ist ein Überhang, und die bestehende Überhangkarte weiß
das bereits. Auch hier ist das die Verbindung, die den Unterschied macht.

---

## §8 Oberfläche

**Grenzen aus P15 gelten.** `tests/test_interface_limits.py`: höchstens neun
Menüs, zwölf Zeilen je Menü, acht Umschalter, acht Felder auf der Vorderseite
eines Dialogs, genau ein Menüeintrag je Operation. Der neue Bereich wird
**hineingeplant**, nicht drangehängt (Entscheidung M).

**Die Sculpting-Leiste** — nach dem Vorbild der Skizzenleiste, höchstens acht
Bedienelemente. Umgesetzt in P16.6 mit: Werkzeug, Radius, Stärke, Symmetrie,
*Neu ansetzen*, Auflösungshinweis, Wandstärkenwarnung, *[Fertig]*. Der
**Abfall** aus der ursprünglichen Liste ist entfallen und hat seinen Platz an
die erzwungene Etappe aus Entscheidung C verloren; die Auswertung hat eine
feste Gewichtsfunktion. Kein *[Verwerfen]* daneben, anders als bei der Skizze:
Eine Sitzung ohne Züge hinterlässt nichts, und eine mit Zügen ist eine
Transaktion, die ein Undo zurücknimmt (Regel 19) — ein Knopf für das, was
Strg+Z kann, wäre der neunte.

**Der Pinselring gehört in die Szene, nicht an den Zeiger.** Ein Zeiger hat
feste Punktgröße und weiß nichts von der Kamera; er behauptete beim ersten
Zoom eine Größe, die er nicht mehr hat. Und er liegt flach auf der Fläche
statt in der Bildebene — einer, der immer zum Betrachter zeigt, sagt nichts
darüber, wie schräg die Stelle unter ihm steht.

**Offscreen testbar.** Der Skizzeneditor hat vorgemacht, wie das geht
(`tests/test_sketch_editor.py`): Die Interaktion läuft über Methoden, die ein
Test direkt aufrufen kann, nicht über Qt-Ereignisse allein. Ein Strich ist im
Test drei Zahlen, kein Mausweg.

**Rückmeldung** (§2.8): Der Pinsel wirkt sofort auf einer Vorschau; die
Auswertung des Stapels und die Wandstärkenkarte laufen verzögert im
Hintergrund. Das Fenster friert nie ein.

---

## §9 Dateiformat

`format_version` 7 → 8, Migration `v7→v8`, Beispieldatei der alten Version
eingecheckt, Test „alte Datei öffnet und rechnet korrekt". Ältere Migrationen
bleiben bestehen (Checkliste `AGENTS.md`).

**Wo die Striche liegen.** Bis 2 000 Striche im `project.json` als kompakte
Zahlenliste — das sind etwa 200 kB, vergleichbar mit einer großen Skizze.
Darüber als binärer Block in `sources/strokes/<op>.npz`, mit Prüfsumme wie
jede andere Quelle (§16.1). Die Grenze ist eine Konstante, keine Streuzahl,
und sie steht im Modulkopf mit ihrer Begründung.

Keine absoluten Pfade (Regel 12). Das Bild eines Displacements reist im
Container mit, nicht als Verweis — sonst öffnet das Projekt auf einem anderen
Rechner ohne sein Relief.

---

## §10 Leistung — neue Zeilen für §31

| Vorgang | Zielwert | gemessen |
|---|---|---|
| Pinselstrich → Vorschau | unter 50 ms | **0,7 ms** bei 1,31 Mio. Dreiecken (P16.2) |
| Strichliste (1 000) neu auswerten | unter 2 s | **96 ms** auf dem §31-Prüfnetz (P16.5, ganze Auswertung) |
| Subdivision | unter 3 s | **1 778 ms** (P16.3, ganze Operation) |
| Gleichmäßig vernetzen | unter 3 s | **1 480 ms** (P16.3, ganze Operation) |
| Weich verschmelzen | unter 3 s | **1 607 ms** (P16.4, zwei gekreuzte Rohre) |

Regressionsschwelle wie überall 25 %. Fünf Tests in `tests/test_performance.py`
halten die Zahlen fest, dazu einer, der Entscheidung C selbst prüft statt sie
zu behaupten.

**Die Subdivisionszeile ist in P16.3 gewachsen, ohne dass etwas langsamer
wurde.** Sie stand bei 574 ms, und das war eine bequeme Messung: ein selbst
gebautes Manifold, `smooth_out(52.5).refine(2)`, ohne den Weg hin und zurück
ins Netz. Gemessen wird jetzt die Operation, die ausgeliefert wird — samt
Konvertierung, Normalenrechnung und Verschweißen, und mit halbierter
Kantenlänge als Ziel, was dieselbe Vervierfachung der Dreiecke bedeutet wie
`refine(2)`. Ein Budget, das den Aufruf nicht abdeckt, den es zu schützen
vorgibt, ist keines.

**R1 ist beantwortet, und deutlich.** Die riskante Zeile war die erste — sie
verlangt eine Vorschau, die nur die betroffenen Vertices anfasst. Gemessen an
`dense_1m.stl` (1 310 720 Dreiecke, 3 932 160 Vertices), also dem
Sechseinhalbfachen der Größe, für die das Budget gilt:

| Weg | Zeit |
|---|---|
| KD-Baum bauen — **einmal je Sitzung** | 786 ms |
| Ein Strich, mit Vollkopie des Vertex-Arrays | 28,4 ms |
| **Ein Strich, nur die getroffenen Vertices** | **0,7 ms** |

Der Strich trifft 10 595 von 3 932 160 Vertices. Die Vollkopie kostet das
Vierzigfache und ist der Fehler, den man an dieser Stelle leicht macht —
`test_a_brush_stroke_stays_inside_a_frame` verhindert ihn.

Daraus folgt der Vorschauweg: **Der Pinsel geht nicht über den Geometriekern.**
Er schreibt in das Vertex-Array des Anzeigenetzes; die Op wird erst beim
Verlassen der Sitzung ausgewertet. Die 786 ms für den KD-Baum sind die
Wartezeit beim Öffnen und bekommen eine Fortschrittsanzeige (§2.8).

---

## §11 Agentenschicht

Entscheidung K. Zusätzlich: Der Steckbrief (`perceive/digest.py`) meldet, dass
ein Körper gesculptet wurde, mit Strichzahl und Etappen — der Agent soll
wissen, dass er eine Form vor sich hat, deren Maße keine Absicht sind.

Regelsammlung ergänzen (`knowledge/data/rules.toml`), Version erhöhen, Suite
vorher und nachher, beide Ergebnisse festhalten. Verschlechtert sich die Quote,
wird die Regel zurückgenommen — Checkliste `AGENTS.md`.

---

## §12 Druckbarkeit — die Kopplung, um die es eigentlich geht

Entscheidung L, ausformuliert. Vier bestehende Fähigkeiten wirken in die
Sculpting-Sitzung hinein:

| Bestehend | Wirkung beim Sculpten |
|---|---|
| Wandstärkenkarte (`perceive/maps.py`) | zu dünne Stellen sofort sichtbar |
| Überhangkarte | was Stützen braucht, während man es formt |
| `check_build_volume` | passt es noch auf die Platte |
| Auto Split mit Verstiftung (§10) | was zu groß ist, wird geteilt statt verworfen |

Keine davon ist neu. Alle vier zusammen sind das, was ein Sculpting-Programm
nicht hat und ein Slicer zu spät sagt.

---

## §13 Nicht-Ziele

Ausdrücklich **nicht** gebaut, mit Grund:

- **PBR-Texturen, UV-Auslegung, Texturmalerei** — Solidon macht Körper für
  Drucker, keine Assets. Die Materialslots (§20) sind für Filamentwechsel da,
  nicht für Aussehen.
- **Animation, Zeitachse, Rigging für Bewegung** — gedruckt wird eine Pose (I).
- **Handretopologie** — wer sein Netz von Hand neu auslegen will, hat ein
  anderes Programm im Sinn.
- **Pinsel von Dritten, Alphas, Pinselbibliotheken** — das wäre ein
  Plugin-System, und das steht auf der Nicht-bauen-Liste.
- **Dyntopo** — Entscheidung E, mit Gründen.
- **Käfigmodellierung** — vertagt, H2. Wird nach P16 neu bewertet, nicht
  stillschweigend nachgeschoben.
- **Sculpting durch den Agenten** — Leitprinzip 5, K.
- **Mit ZBrush oder Blender in der Breite konkurrieren.** Sechs Werkzeuge
  gegen deren Hunderte. Der Anspruch ist nicht Gleichstand, sondern §17.

---

## §14 Risiken und Rückfalloptionen

**R1 — Die Vorschau ist zu langsam.** Das erste Risiko und der Grund, warum
P16.2 eine reine Messung ist. *Rückfall:* Vorschau auf einem dezimierten Netz,
volle Auflösung erst beim Loslassen.

**R2 — Striche überleben eine Formänderung darunter nicht.** Unauflösbar im
Kern (§3.1). *Milderung:* Bei der Auswertung wird jeder Strich auf die
nächstgelegene Fläche projiziert; findet sich in der doppelten Radiusdistanz
keine, wird der Strich **nicht still verworfen**, sondern als Befund gemeldet
(„142 Striche finden keine Fläche mehr") mit den Handlungen *[Zeigen]*,
*[Verwerfen]*, *[Änderung zurücknehmen]*. Ein still verschwundener Strich wäre
genau die Sorte Fehler, die niemand mit seiner Ursache verbindet.

**R3 — Die Kommutativität irritiert erfahrene Nutzer** (C). *Milderung:*
Etappen bei den reihenfolgeabhängigen Werkzeugen, Etappenzahl sichtbar, und
ein Absatz im Handbuch, der es benennt, statt es zu verschweigen. Nach dem
Vorbild der Auto-Split-Seite der Gegenseite (Befund B14 im Meshy-Konzept):
„Wann dieses Werkzeug nicht das richtige ist" gehört dazu.

**R4 — Die Phase wird zu groß.** Fünf Fähigkeiten sind viel. *Rückfall:* §15
ist so geschnitten, dass nach P16.6 ein vollständiges, abnahmefähiges Ergebnis
steht. Posing (P16.8) und der Skeletteditor sind ausdrücklich streichbar.

**R5 — Der Kundenkreis verschiebt sich, ohne dass es jemand entschieden hat.**
Das größte Risiko, und kein technisches. §17.

**R6 — Selbstdurchdringung durch zu starke Striche.** `warp_batch` prüft
nicht (§2.4). *Milderung:* Nach jeder Auswertung die bestehende Prüfung, und
bei Durchdringung ein Befund mit *[Reparieren]* — die `repair`-Op gibt es.

---

## §15 Umsetzungsplan

Jedes Paket endet mit grünem Tor (`pytest`, `ruff check`, `ruff format`,
`mypy`) und einem Commit. Umfang: S = ein Tag, L = eine Woche, XL = mehr.

| # | Paket | Umfang | Verifikation | Stand |
|---|---|---|---|---|
| **P16.1** | Regel 2 neu fassen; `tests/test_gesture_ops.py` gegen die **bestehenden** Skizzen-Ops; `AGENTS.md`, `.claude/rules/operationen.md`; Befund B13 im Meshy-Konzept zurücknehmen | S | neuer Test grün auf dem Bestand, ohne eine Zeile neuer Geometrie | **fertig** — 26 Tests, Tor grün |
| **P16.2** | **Reine Messung.** Vorschauweg, Strichwiedergabe, Subdivision, Entscheidung C als Test | S | Messwerte festgehalten; R1 beantwortet **bevor** P16.5 beginnt | **fertig** — 4 Tests, R1 entwarnt |
| **P16.3** | `subdivide_surface` und `remesh_uniform` — erst prüfen, ob letzteres in `remesh_mesh` gehört | S | Geometrietest gegen Korpus, beide Qualitätsstufen | **fertig** — 15 Tests, Prüffrage mit Zahlen beantwortet (§7.2) |
| **P16.4** | `blend_union` über `level_set` (N) — **zugleich das Basisnetz-Werkzeug für H2** | S | Volumen und Wasserdichtheit gegen analytische Körper | **fertig** — 10 Tests, Rechenweg geändert (N) |
| **P16.5** | Kern des Sculptings: `kind="strokes"`, `Stroke`-Verträge (§9), Auswertung mit Etappen, sechs Werkzeuge, Symmetrie — **ohne Oberfläche**, über CLI bedienbar; **bringt die saubere Figur in den Korpus mit** (§18, verschoben aus P16.2) | **XL** | Determinismus, Symmetrie, Etappen; zweimal auswerten identisch | **fertig** — 26 Tests, 96 ms für 1 000 Striche |
| **P16.6** | Sculpting-Sitzung im Viewport: Pinselring, Leiste, Vorschau, Wandstärke live, Editor-Undo | **XL** | offscreen wie `test_sketch_editor.py`; Grenzen aus `test_interface_limits.py` | **fertig** — 19 Tests, Grenzen gehalten |
| **P16.7** | `displace_image` samt Bild in `sources/` und Profilprüfung | L | Relief unter Düsenbreite wird gemeldet | offen |
| **P16.8** | `pose_armature`: Skelett, Gewichte, Vorwärtskinematik, Skeletteditor | **XL** | Pose deterministisch; Gelenkwinkel als Projektparameter | offen |
| **P16.9** | Dateiformat 7→8, Migration, Beispieldatei, Einbacken (D) | L | alte Datei öffnet und rechnet | offen |
| **P16.10** | Handbuch, Weg 4, Website, Beispielprojekt, Übersetzungen, Regelsammlung + Agenten-Suite vorher/nachher (§18) | L | Sprachdateien vollständig; Suitenquote nicht schlechter | offen |
| **P16.11** | **Prüfpunkt Käfigmodellierung** (H2): Reicht Primitive + `blend_union` + Pinsel als Basisnetz für die Korpusfiguren? | S | Kriterium **vor** P16.5 festgeschrieben; Ergebnis dokumentiert, nicht passend gemacht | **fertig** — 4 von 5 Bedingungen erfüllt (H2) |

**Reihenfolge mit Absicht.** P16.1 ändert die Regel und beweist sie am
Bestand — die neue Regel ist grün, bevor irgendetwas Neues sie braucht. P16.2
ist eine Messung, kein Feature: Sie darf das Vorhaben stoppen, und sie holt die
Figuren in den Korpus, ohne die es später keine Abnahme gibt. P16.3 und P16.4
sind kleine, für sich nützliche Ops, die auch dann etwas wert sind, wenn P16.5
scheitert — und `blend_union` ist zugleich der Grund, warum H2 nachgeordnet ist.

**P16.11 ist ein Prüfpunkt, kein Paket.** Sein Kriterium wird vor P16.5
festgeschrieben, damit die Antwort nicht davon abhängt, wie müde man nach P16.6
ist.

**Additiv, dann Schnitt, dann Abbau** — hier fällt der Abbau aus: Es wird
nichts ersetzt. `paint_slot` bleibt, wie es ist; ein Bemalvorgang ist keine
Sculpting-Sitzung, und die drei Klicks pro Deckel sind dort weiterhin richtig.

**Übergabenotizen** werden in `ROADMAP.md` unter P16 geführt, mit
Commit-Hashes und ausdrücklich markierten Abweichungen von diesem Konzept.

---

## §16 Abnahme

Die Phase ist fertig, wenn:

1. Alle vier Tore grün sind, auf Windows und in der CI.
2. `tests/test_gesture_ops.py` für Skizze, Striche und Skelett grün ist.
3. Eine Figur aus dem Korpus vom Grundkörper bis zum druckfertigen 3MF durch
   Solidon läuft, ohne dass ein zweites Programm geöffnet wird — Zeitmessung
   festgehalten.
4. Dieselbe Figur nach dem Wiederöffnen der Projektdatei **identische**
   Geometrie liefert (Hash-Vergleich).
5. Die drei Leistungszeilen aus §10 eingehalten sind.
6. Die Grenzen aus `test_interface_limits.py` gehalten haben, ohne dass eine
   Grenze angehoben wurde.
7. Die Agenten-Suite nicht schlechter ist als vorher.
8. Handbuchseiten in beiden Sprachen stehen, mit „wann nicht benutzen".

Punkt 6 ist der, der am ehesten verhandelt werden möchte. Er wird nicht
verhandelt — die Grenzen wurden vor dem Wachstum eingezogen, damit sie beim
Wachstum halten.

---

## §17 Positionierung — nach der Entscheidung

Der Kundenkreis ist erweitert: **Figuren gehören dazu.** Damit fällt der Satz
aus Befund B13 des Meshy-Konzepts („wer Figuren druckt, ist heute nicht unser
Kunde"), und er wird dort mit Datum und Verweis auf dieses Dokument
zurückgenommen — ein Befund, der still stehen bleibt und nicht mehr gilt, ist
schlimmer als keiner.

Das Ziel darüber ist „die beste Anwendung für den 3D-Druck". Dazu drei Sätze,
die zusammen den Weg beschreiben — der erste ist unbequem, und er bleibt stehen.

**Wir gewinnen kein Sculpting-Rennen, und wir müssen es nicht.** ZBrush,
Blender und Nomad haben zwanzig Jahre, Hunderte Werkzeuge und Nutzer, die sie
beherrschen. Sechs Pinsel sind sechs Pinsel. Wer eine Porträtbüste modelliert,
nimmt weiter Blender — und *das ist in Ordnung*, weil das Rennen, das wir
laufen, ein anderes ist: nicht „das beste Modellierprogramm", sondern „die
beste Anwendung für den 3D-Druck". Ein Werkzeug, das man für 90 % der
Druckfiguren nicht mehr verlassen muss, gewinnt dieses Rennen; eines, das
ZBrush in der Breite nachbaut, verliert beide.

**Die Lücke, die keiner besetzt, ist die Verbindung.** Die
Sculpting-Programme wissen nichts über Drucker: keine Wand unter der
Düsenbreite, kein Überhang, kein Bauraum, keine Teilung mit Verstiftung. Der
Slicer merkt es, aber zu spät — da ist die Form fertig, und was er sagt, ist
„Stützen an 340 Stellen", nicht „hier ist die Wand zu dünn, während du sie
formst". Umgekehrt weiß kein CAD-Programm, wie man eine Figur formt. Solidon
ist nach P16 das einzige Programm, in dem beides in einem Fenster steht (§12).
Das ist kein Werbesatz, sondern vier bestehende Fähigkeiten, die in ein neues
Fenster hineinreichen.

**Der Vergleich, an dem sich P16 messen lassen muss**, ist deshalb nicht
„haben wir so viele Pinsel wie X", sondern:

| Frage | Meshy / Rodin | ZBrush / Blender | Solidon nach P16 |
|---|---|---|---|
| Figur entsteht | Prompt | Hand | Hand **und** Prompt |
| Wandstärke beim Formen | — | — | **live** |
| Überhang beim Formen | — | — | **live** |
| Zu groß für die Platte | — | — | **Teilung mit Verstiftung** |
| Maßhaltige Anbauteile (Sockel, Steckverbindung) | — | mühsam | **Skizzen, Passungen, Parameter** |
| Reproduzierbar aus der Datei | nein | destruktiv | **Op-Stack** |
| Ohne Konto und ohne Netz | nein | ja | **ja** |

Die letzten vier Zeilen sind der Wettbewerbsvorsprung, und keine davon entsteht
in P16 neu — sie existieren alle und bekommen nur ein neues Anwendungsgebiet.

---

## §18 Was die Erweiterung außerhalb des Codes kostet

Der Kundenkreis zu erweitern ist nicht mit Ops erledigt. Was nachgezogen werden
muss, damit die Entscheidung nicht nur im Code steht:

| Was | Warum | Wo im Plan |
|---|---|---|
| **Referenzkorpus** um eine saubere Figur ergänzen | Ohne sie kein Geometrietest für Sculpting und keine Abnahme (§16.3). `generated_figure.stl` trägt absichtlich Generatorfehler und taugt erst nach der Reparaturkette — als Prüfstein für Weg 3 richtig, als Sculpting-Grundlage zu indirekt | P16.5, mit den ersten Geometrietests |
| **Beispielprojekt** „Figur drucken" als vierter Weg | Die drei Wege aus §2.2 bilden den Kundenkreis ab; ein vierter Kundenkreis ohne vierten Weg ist unsichtbar | P16.10 |
| **Website** — Weg 4, Vergleichstabelle aus §17 | Befund B3 des Meshy-Konzepts verlangt schon, die Kette für generierte Netze sichtbar zu machen; das hier ist dieselbe Sache für geformte | P16.10 |
| **Handbuch** — Sculpting-Seiten, „wann nicht benutzen" (R3) | Befund B14 | P16.10 |
| **Agenten-Regelsammlung** | Der Agent muss wissen, dass er nicht sculptet (K) und was er stattdessen anbietet | P16.10 |
| **Befund B13 zurücknehmen** in `konzept-meshy-hyper3d-2026-08.md` | Ein überholter Befund, der stehen bleibt, wird beim nächsten Lesen für gültig gehalten | P16.1 |
| **Nicht-planarer Schnitt neu bewerten** (B13 dort) | Er war abgelehnt mit der Begründung „Figurendrucker sind nicht unser Kunde". Diese Begründung ist entfallen — die *technische* Begründung (V-HACD-Näherung, §11.1) gilt weiter, die geneigte Ebene bleibt der offene Weg | nach P16 |

Die letzte Zeile ist die interessanteste: Die Kundenkreis-Entscheidung macht
einen abgelehnten Befund wieder zu einer offenen Frage. Wer Figuren teilt, will
die versteckte Naht.

---

## Übergabenotiz — Stand 13.08.2026

**Fertig, committet, Tor grün:**

- **P16.1** (`a046a05`) — Regel 2 in `AGENTS.md` neu gefasst, dieselbe
  Formulierung in Bauplan-Absicht in `.claude/rules/operationen.md`
  nachgezogen. `tests/test_gesture_ops.py`: 26 Tests, prüfen fünf
  Eigenschaften von Sammelparametern über das ganze Register. Befund B13 im
  Meshy-Konzept mit Datum zurückgenommen (technische Hälfte bleibt gültig).
- **P16.3** — `remesh_uniform` und `subdivide_surface` in `mesh_ops.py`,
  `tests/test_subdivision.py` mit 15 Tests, zwei Leistungszeilen in §10.
  Die Prüffrage („gehört das gleichmäßige Vernetzen in `remesh_mesh`?") ist
  mit Zahlen beantwortet — nein, Faktor hundert an Dreiecken und eine andere
  Zusage (§7.2). Zwei Funde in bestehendem Code mitbehoben: ein
  Handlungsvorschlag, der die Zahl nannte, die er gerade abgelehnt hatte
  (Regel 17), und ein Übergang in den exakten Netzkern über `float32`, wo
  `Mesh64` dieselbe Arbeit in doppelter Genauigkeit tut (Regel 6). Die
  Operationszahl auf beiden Websprachen von 77 auf 79 nachgezogen.
- **P16.2** (`4b1fa53`) — vier Leistungstests in `tests/test_performance.py`
  unter `pytest.mark.performance`. R1 entwarnt: Vorschau 0,7 ms statt der
  befürchteten Sekunden, weil der Pinsel nur die getroffenen Vertices
  anfasst und nicht über den Geometriekern geht. Nebenbefund: generierte
  Netze brauchen vor dem Sculpten `GENERATED_REPAIR` + `refine` — Kette für
  Weg 3 jetzt vollständig benannt in §2.4 dieses Dokuments.

**Voller Tor-Lauf zuletzt bestätigt:** 3553 pytest-Tests (aufgeteilt wie die
CI es tut — elf Fensterdateien einzeln, wegen des bekannten,
vorbestehenden VTK-Absturzes bei vielen Fenstern in einem Prozess), 16
Leistungstests, `ruff check`, `ruff format --check`, `mypy` — alle grün.
Ein Lauf in einem Rutsch stürzt ab; das ist nicht neu und nicht von P16
verursacht (nachgewiesen: tritt auch ohne `test_gesture_ops.py` auf, an
anderer Stelle).

- **P16.4** — `blend_union` in `app/core/geom/blend.py`,
  `tests/test_blend.py` mit 10 Tests, eine Leistungszeile in §10. Der
  Rechenweg ist ein anderer als in N vorgesehen; die drei verworfenen
  Varianten stehen dort mit ihren Zahlen, damit sie nicht ein zweites Mal
  probiert werden. Nebenbei behoben: vier deutsche Bezeichner in
  `slicer_profiles.py` und ein Oberflächentext ohne Übersetzung, beides aus
  `566e0af` und beides Ursache eines roten Laufs, der nicht aus P16 stammte.

**Noch nichts angefasst — keine Oberfläche, keine Verträge:**

- Der Adapter in den exakten Netzkern steht seit P16.3 in `mesh_ops.py`
  (`_as_solid`, `_as_mesh`); P16.4 brauchte ihn nicht, weil sein Weg über das
  Raster läuft. Die zwei Fallen darin sind bezahlt und stehen dort
  auskommentiert: `Mesh64` statt `Mesh`, und Verschweißen nach der
  Rückkonvertierung, weil der Kern an jeder scharfen Kante mehrere Eckpunkte
  an derselben Stelle herausgibt.
- **Das Abstandsfeld aus `blend.py` ist der Baustein, den P16.5 wieder
  braucht.** Ein Sculpting-Strich verschiebt Vertices entlang einer Normale;
  wo geprüft werden muss, ob eine Wand zu dünn wird, ist dasselbe Feld die
  Antwort. `distance_field()` steht dafür bereit — mit der Warnung im
  Docstring, welche zwei Wege dorthin nicht funktionieren.
- **P16.5** — Kern in `app/core/geom/sculpt.py`, `Stroke` in `types.py`,
  `kind="strokes"` im Schema, `clean_figure.stl` im Korpus.
  `tests/test_sculpt.py` mit 26 Tests. Der Gesten-Test aus P16.1 greift ohne
  Anpassung — er war für diesen Tag geschrieben.
- **P16.6** — Sitzung im Viewport: `app/ui/sculpt_bar.py`, die Sitzungslogik
  in `main_window.py`, Vorschau und Pinselring im Viewport, ein eigener
  Zeiger. `tests/test_sculpt_session.py` mit 19 Tests, offscreen.
- P16.6 bis P16.10: unverändert wie in §15 beschrieben, keiner begonnen.
  **P16.9 trägt jetzt eine bestätigte Entscheidung**: Einbacken mit Nachfrage
  (D), von Robert am 13.08.2026 so entschieden.

**Beide offenen Entscheidungen sind entschieden** (Robert, 13.08.2026, vor
dem Beginn von P16.5 zurückgefragt):

- **Entscheidung C** — kommutativ, **aber mit erzwingbarer Etappe**. Der
  Strich trägt dafür `cut`; wer die exakte Reihenfolge braucht, kauft sie
  stückweise statt für die ganze Sitzung. Umgesetzt in P16.5.
- **Entscheidung D** — Einbacken ab 20 000 Strichen oder 20 Etappen, mit
  Nachfrage, weil nicht folgenlos rücknehmbar. Gehört in P16.9.

- **P16.11** — Kriterium in `tests/test_base_mesh.py` festgeschrieben, vier
  von fünf Bedingungen erfüllt (H2). Die fünfte braucht den Pinsel. Der
  Prüfpunkt fand beim ersten Lauf einen Vorzeichenfehler in P16.4, der
  Volumen und Wasserdichtheit unbeschadet ließ und die Ausdehnung um acht
  Millimeter verfehlte.

**Nächster Schritt, wenn es weitergeht:** P16.7 — `displace_image`, ein
Höhenfeld als Geometrie. Umfang L, unabhängig von allem Bisherigen, und die
Rechnung dafür steht schon: Es ist dasselbe Verschieben entlang der Normale
wie beim Pinsel, nur dass die Stärke aus einem Bild kommt statt aus einer
Geste. Danach P16.8 (Posing, XL), P16.9 (Dateiformat 7 → 8 samt Einbacken)
und P16.10 (Weg 4, Handbuch, Website, Regelsammlung).

**Was P16.9 vorfindet:** Entscheidung D ist bestätigt, und der Ort dafür steht
— die Strichliste liegt bis 2 000 Zügen im `project.json` und darüber als
Block in `sources/` (§9). Das Einbacken schreibt den Stand als neues Quellnetz
und beginnt die Liste neu.

**Vorher zu klären, weil es ab P16.5 wirksam wird:** die beiden unten
genannten Entscheidungen C und D.

**Zwei Dinge, die P16.3 offen an den Bauplan zurückgibt** — beide brauchen
eine Ansage, deshalb stehen sie hier und nicht im Code:

- **Bauplan §25** kennt die zwei neuen Operationen noch nicht. §6 dieses
  Dokuments sieht die Änderung vor („sechs Ops, Kategorie `organic"'), aber
  der Bauplan wird nicht ungefragt geändert. Sinnvoll zusammen mit P16.4 oder
  P16.5, wenn feststeht, welche der sechs wirklich `organic` werden.
- **Die Kategoriefrage selbst.** P16.3 hat sie mit `mesh` beantwortet, weil
  zwei Netz-Operationen neben ihren Geschwistern gehören (§7.2). Für
  `sculpt_strokes`, `displace_image`, `pose_armature` und `blend_union` gilt
  das nicht — spätestens dort ist zu entscheiden, ob `organic` als Kategorie
  entsteht und unter welche Menügruppe sie fällt. Ein eigenes Menü ist es
  nicht: `test_interface_limits.py` deckelt bei neun, und neun sind es.
