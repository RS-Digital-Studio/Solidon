# Gesamtdurchsicht 11.09.2026 — was offen bleibt

Neun Durchsichten über alle Bereiche, danach eine Nacht Arbeit, danach eine
Nachkontrolle über die eigenen Commits. Dreizehn Commits sind draußen
(`d9c48907` bis `cb876947`) — die letzten drei behoben, was die Nachkontrolle
an der Arbeit der Nacht selbst gefunden hat. Was hier steht, ist **nicht**
erledigt und gehört ins Register von `ROADMAP.md`, sobald die Datei frei ist —
sie lag während der ganzen Nacht mit ungestagten Änderungen einer zweiten
Sitzung im Baum, und offene Arbeit steht im Register und nirgends sonst.

## Der zweite Torlauf, und was er sagt

Gefahren 11.09.2026, 02:48, gegen den reparierten Stand
(`suite-getrennt.sh`, Ausgabe in eine Datei, Code unmittelbar danach gelesen):
**Exit 1, fünf Läufe mit Fehler.** Jeder ist zugeordnet, keiner ist
unerklärt:

| Rot | Ursache | Wem es gehört |
|---|---|---|
| `test_analysis_ui` (1) | Menüfaltung kippt bei neun Handlungen | **mir** — entschieden und behoben, siehe unten |
| `test_feature_label_layout` (1) | Layout baut Geometrie neu auf | zweite Sitzung (`viewport.py`, schreibt noch) |
| `test_manual` (12) | Handbuch noch nicht erzeugt | Erzeugerlauf, gehört ans Release |
| `test_wording` (6) | dieselbe Ursache | Erzeugerlauf |
| `test_value_labels` (1) | `distance_mm` ohne Beschriftung | zweite Sitzung, **von mir behoben** |

`test_translations` war in Torlauf 1 rot und ist es nicht mehr.

**Ein dritter Torlauf steht aus, und er wäre jetzt wertlos.** Die zweite
Sitzung schreibt weiter: `prepare_ops.py` 05:54, `prepare.py` 05:51,
`test_slot_features.py` 05:51, `test_slot_handle.py` 05:49, `viewport.py`
05:46. Wer während eines Tors in den Baum schreibt, macht seinen Lauf zu
einer Aussage über keinen Stand. Der Lauf gehört in den Augenblick, in dem
der Baum still ist.

**Der Erzeugerlauf (`make_manual.py`) gehört in denselben Augenblick.** Er
bäckt die Oberflächentexte ins Handbuch, und die sind gerade im Fluss; ein
Lauf jetzt erzeugte sechs Sprachen auf einem halben Stand. `AGENTS.md` sagt
dasselbe von der anderen Seite: „Bilder und Handbuch nur beim Release".
Die 18 roten Fälle sind damit kein Rückschritt, sondern der bekannte Zustand
zwischen zwei Erzeugerläufen.

## Blockiert durch fremde Arbeit im selben Baum

Beide Befunde sind gemessen und beide kundenwirksam. `app/ui/panels.py` und
`app/core/scene/placement.py` trugen die ganze Nacht ungestagte Änderungen
einer zweiten Sitzung; ein Eingriff dort hätte ihre Arbeit überschrieben.

### Der Weg zu den Bohrungshandlungen ist einen Klick länger geworden

Mit `slot_hole` trägt eine Bohrung **15** Operationen — über der Grenze von
zwölf Zeilen aus §35. Gefaltet wird seitdem die Gruppe „Ändern" statt
„Bausteine": Alle neun Merkmalshandlungen — *Bohrung ändern*, *Senken*,
*Bohrung verschließen*, *Merkmal entfernen* und auch das neue *Zum Langloch
ziehen* — liegen einen Klick tiefer, während die fünf Bausteine direkt
dastehen. `tests/test_analysis_ui.py::test_a_feature_menu_names_the_operations_of_its_kind`
ist deshalb rot, und das ist **kein veralteter Wächter**, sondern der Test, der
genau diese Zusage hält („was die Bohrung selbst angeht, steht direkt da").

**Nachgemessen am 11.09.2026, 06:20 — die Ursache ist der Kippunkt, und er
liegt bei genau neun.** `groups_to_keep` liefert korrekt `{'Ändern'}`, der
Schutz ist also gesetzt; `folded_groups` faltet die Gruppe trotzdem. Gemessen
über `folded_groups({'Ändern': n, 'Bausteine': 5, 'Vorbereiten': 1}, fixed=2,
keep={'Ändern'})`:

| Handlungen an der Bohrung | gefaltet | Zeilen |
|---|---|---|
| 7 | Bausteine | 11 |
| 8 | Bausteine | 12 |
| **9** | **Ändern** | 9 |
| 10 | Ändern | 9 |

Bis acht genügt „Bausteine" allein, um unter die Grenze zu kommen, und der
Schutz greift. Ab neun genügt sie nicht mehr (spart 4, gebraucht werden 5),
und damit steht in `surfaces.py:265` nur noch „Ändern" in `enough` — der
`keep`-Rang hat dort nichts mehr zu wählen. **Die neunte Handlung ist *Zum
Langloch ziehen*, also meine.**

**Der Ansatz, der hier stand, reicht nicht**, und das ist der Grund, warum
der Punkt offen bleibt statt behoben zu sein: „Ändern" hart zu halten ergibt
2 feste + 9 Handlungen + 1 Katalogzeile + 1 *Prüfstück erzeugen* = **13
Zeilen**. Die Grenze von zwölf steht im Bauplan (§2.6, Oberflächengrenzen)
und wird von zwei weiteren Tests gehalten
(`test_interface_limits.py:427`, `test_analysis_ui.py:1343`). Ein Fix, der
den einen Test grün macht, macht die zwei anderen rot.

An einer Bohrung stehen 17 Dinge zur Wahl und 12 Zeilen zur Verfügung. Die
Frage ist deshalb nicht, wie gefaltet wird, sondern **welche eine Zeile
entfällt** — und das ist eine Produktentscheidung, wie es die drei
Nachbarentscheidungen im selben Code auch waren (`KEEP_VISIBLE`,
`ALWAYS_DIRECT`, Katalog statt Untermenü, alle mit „Entscheidung Robert"
vermerkt). Drei Wege, mit ihren Kosten:

1. **`prepare` („Prüfstück erzeugen") nicht mehr am Merkmal anbieten.**
   Billigste Zeile — aber ein Passungsprüfstück an einer Bohrung ist genau
   der Maker-Kernnutzen.
2. ***Zum Langloch ziehen* aus dem Merkmalsmenü nehmen.** Der Weg bliebe
   über *Bohrung ändern* (der Haken „Langloch" ist Teil von `DrillParams`)
   und über den Viewport-Griff, an dem die zweite Sitzung gerade baut
   (`app/ui/slot_handle.py`). Kostet die direkte Geste.
3. **Die Grenze an dieser Stelle auf 13 heben.** Ändert eine Bauplanzusage
   und trifft jedes Menü — nicht ohne Ansage.

`MENU_TWINS` ist **kein** Weg: Die Tabelle ist in `registry.py:177`
ausdrücklich den zwei Rechenkernen vorbehalten.

**Entschieden und behoben (Robert, 11.09.2026, 06:45): Weg 2.** Eine
Korrektur zur Begründung oben: `resize_hole` („Bohrung ändern") kennt keinen
Haken „Langloch" — der sitzt an `drill_hole`, also am *Setzen*. Was bleibt,
sind Griff, Menüleiste und Befehlspalette; die Entscheidung trägt das.
`HANDLE_INSTEAD` in `app/ui/panels.py` nimmt die Zeile an der Bohrung aus
dem Menü, `applies_to` bleibt. Am gebauten Menü: zwölf Zeilen, acht
Handlungen direkt, der Katalog als eine Zeile, *Prüfstück erzeugen* da. Am
Langloch bleibt die Operation die einzige Zeile. Drei neue Tests, Mutation
mit leerer Tabelle macht drei rot. Was der Changelog-Satz zum Langloch
später nennt, ist der **Griff**, nicht das Menü — das gehört dem, der das
Langloch abschließt.

### Der gezeichnete Vorschau-Umriss eines Langlochs ist 22 Prozent zu schmal

Gemessen an Ø 5 × 20 mm: Der Schneidkörper (`drill_tool`) misst in der
Mündungsebene 19,995 × 5,000, der gezeichnete Umriss (`placement.mouth_outline`)
19,995 × **3,890**, mit abgeschnittenen Enden. Ursache ist
`app/core/scene/placement.py:630-639`: Je Winkelsektor (32 Sektoren) wird nur
der äußerste Punkt behalten. Am Kreis stimmt das, an einem langgestreckten
Umriss fallen fast alle Punkte in wenige Sektoren, und der äußerste ist nicht
der Rand. Der Kunde sieht genau diesen Umriss — `app/ui/placement_flow.py:1646`
blendet den Werkzeugkörper aus, sobald einer da ist.

Ansatz: Den Rand über die Ringreihenfolge der Mündungspunkte oder eine konvexe
Hülle bestimmen statt über Winkelsektoren. Die Sektorbegrenzung ist die
Antwort auf die Punktzahl, nicht auf die Form. Dazu fehlt ein Test:
`tests/test_surface_placement.py` prüft `placement_tool` für `drill_hole`,
aber nie mit `slotted`.

## Geometrie

### Der B-Rep-Zweig von `slot_hole` stellt als einziger die Kantenfrage nicht

`app/core/geom/prepare_ops.py:3149-3174` sammelt Befunde und Aufweitung, aber
keine Kantenprüfung. Alle drei Nachbarn tun es: der Netz-Zwilling
(`prepare.py:512-521`), `resize_hole` am exakten Kern (`prepare_ops.py:2923`)
und `drill_brep_hole` mit Langloch (`brep/ops.py:675-690`). Ein exakter Körper
mit einer Bohrung nahe der Kante bekommt bei Länge 40 eine offene Flanke und
keinen Befund. `.claude/rules/operationen.md` sagt zu, dass an einem Langloch
an **beiden Enden** gefragt wird.

### Die Breite eines Langlochs wächst bei jedem Zug um 0,016 mm

`prepare.py:493` baut das Werkzeug mit `radius=(diameter + FEATURE_OVERLAP)/2`,
gibt aber `diameter=diameter` im `BoreResult` zurück. Die geraden Flanken sind
exakte Geraden bei ±(d+0,02)/2, und `perceive/slots.py` liest daraus **d + 0,02**.

**Gemessen über drei Züge** (Platte 80 × 40 × 10, Bohrung Ø 5 mit
Materialtoleranz, dann dreimal gezogen):

| Zug | eingegeben | gemessene Länge | gemessene Breite |
|---|---|---|---|
| 1 | 20,00 | 20,0156 | 5,2057 |
| 2 | 24,00 | 24,0158 | 5,2215 |
| 3 | 28,00 | 28,0156 | 5,2371 |

Die **Länge** summiert sich nicht auf — die Abweichung bleibt bei +0,016 mm,
weil `slot_travel` gegen den nominalen Durchmesser rechnet. Die **Breite**
wächst je Zug um 0,0157 mm: nach drei Zügen 0,047 mm über dem gemessenen Maß,
ein Viertel der Materialtoleranz. Der zweite Eingang zur selben Form
(`drill_tool`, `prepare.py:820`) legt die Zugabe **nicht** auf — zwei Wege,
zwei Maße. Der Test `tests/test_slot_features.py:272` deckt es mit `abs=0.05`
zu.

### `_widening_findings` spricht bei `slot_hole` von einer Durchmesseränderung, die es nicht gab

`prepare_ops.py:3170` und `:3193` übergeben den unveränderten Durchmesser, also
`values["previous"] == values["diameter"]`. Am Kunden steht dann
„Sie ist stehen geblieben und sitzt jetzt nicht mehr im gemessenen Verhältnis
zur Bohrung" mit der Handlung *Senkung mitziehen* — und die belegt
`resize_feature` mit dem **jetzigen** Maß vor, endet also in „Die Bohrung hat
bereits diesen Durchmesser". Eine Handlung, die nichts tut.

### Zwei nackte `ValueError` ohne Handlungsvorschlag (Regel 17)

`prepare.py:464` (`"a bore direction must not be zero"`) und `:466`
(`"a detected bore must have a positive depth"`), beide in `slot_bore`. Die
erste ist erreichbar: `_bore_vector` prüft nur auf „Dreiertupel aus Zahlen",
`(0,0,0)` kommt durch. Dieselben zwei Zeilen stehen schon in `resize_bore`
(`prepare.py:335`, `:343`) — die Lücke ist also verdoppelt worden, nicht neu.

### `DrillParams.slot_length` hat keine Obergrenze

`prepare_ops.py:293-308`: `minimum=0.0`, kein `maximum`, und `drill_hole` ruft
`_reject_oversized` nicht. Der Zwilling `slot_hole` tut beides.

**Nachgemessen am 11.09.2026 — die zweite Hälfte des Befunds stimmt nicht.**
`diameter=5` auf einem 20-mm-Würfel:

| `slot_length` | Volumen | Teile | Befunde |
|---|---|---|---|
| 15,0 | 6535,80 mm³ | 1 | `bore.compensated` |
| 100,0 | 5920,00 mm³ | **2** | `bore.over_the_edge`, `bore.compensated` |
| 100000,0 | 5920,00 mm³ | **2** | `bore.over_the_edge`, `bore.compensated` |

Der Würfel zerfällt tatsächlich in zwei Teile — aber **nicht stillschweigend**:
`bore.over_the_edge` steht dabei. Was bleibt, ist zweierlei, und beides ist
kleiner als gemeldet:

* Das fehlende `maximum` (100 km werden angenommen) und der ungenutzte
  `_reject_oversized` — eine Ungleichheit zum Zwilling `slot_hole`.
* Der Befundtext spricht von einer **Kante**, während der Körper in zwei
  Teile zerfällt. Das ist die schlechtere Auskunft, nicht die fehlende.

## Tests, die fehlen

- **`drill_brep_hole` mit `slotted=True`** — nur über den direkten Import von
  `_slotted_bore` geprüft; der Zweig `brep/ops.py:627` und die Kantenschleife
  `:675-690` werden nie betreten. (Der Zwilling am Netz-Kern ist seit
  `256cd62a` gefahren.)
- **Zwei Langlöcher in einem Körper** — `slot_1`/`slot_2`, ihre Vergabe und der
  gierige `break` in `slots.find_slots` sind unbelegt.
- **Ein gekipptes Langloch** — jede Achse in den Tests ist +Z.
- **Ein Steg quer über der Mitte.** `slots.py:414` sagt zu, dass er ein
  Langloch verschließt, ohne über einem Bogenmittelpunkt zu liegen. Mit
  `steps = 2` mutiert bleibt jeder vorhandene Test grün; der Körper, für den
  die Abtastung gebaut wurde, fehlt.
- **`SLOT_ACROSS_LIMIT` (0,5°)** — nur 90° gefahren. Die Zahl ist als gemessen
  dokumentiert und wird von nichts gehalten.
- **Die Vorschau mit Langloch** — kein Test nennt `_creation_tool`.

## Auslieferung

**Vor dem nächsten Release muss `tools/make_manual.py` laufen.** Zwölf Tests in
`tests/test_manual.py` sind rot; sie tragen `@pytest.mark.rendered`, hängen
also an einem Erzeugerlauf und nicht am Code. Vermisst werden `bead_edges`,
`create_label.style` und die drei Langlochfelder von `drill_brep_hole` — die
Website-Referenz hängt seit mehreren Commits hinterher. Die Handbuchergänzung
aus `525de37f` fällt in denselben Lauf.

## Zwei Katalogtexte ohne Übersetzung

`app/core/scene/placement.py` führt zwei neue `tr()`-Texte, die in keinem der
fünf Kataloge stehen: „Zu dieser Kennung gibt es kein Merkmal. Wählen Sie es im
Bild erneut." und „Zu diesem Merkmal sind Durchmesser und Tiefe nicht
bekannt." Die Datei liegt ungestaged im Baum; der Text gehört der zweiten
Sitzung, und `tests/test_translations.py` ist bis dahin rot. Der reparierte
`pre-commit`-Wächter (`e1a63f82`) fängt sie bei ihrem Commit.

**Stand 11.09.2026, 06:00: erledigt.** Beide Texte stehen in allen fünf
Katalogen, `test_translations` ist grün über alle 200 Fälle.

## Wertschlüssel ohne Beschriftung

`tests/test_value_labels.py::test_every_value_key_has_a_label` fand zwei
Schlüssel, die dem Kunden als roher Bezeichner im Tooltip erschienen wären:

* **`distance_mm` in `app/core/geom/faces.py:94`** — aus Commit `2b915e1b`
  der zweiten Sitzung, seit dem Abend committet und liegengeblieben.
  **Behoben:** `"distance": _("Abstand")` in `app/ui/labels.py`. Kein neuer
  Katalogeintrag nötig — „Abstand" steht in allen fünf Katalogen und
  übersetzt durchweg richtig. „Weg" wäre die nähere Übersetzung des
  Befundtextes gewesen und im Italienischen zu „Percorso" geworden, also zu
  *Pfad*.
* **`shortest` in `app/core/geom/prepare.py:753`** — vier Minuten alt beim
  Fund (`shortest_slot`, mtime 05:51), also die laufende Baustelle der
  zweiten Sitzung. **Nicht angefasst**: Die Beschriftung bräuchte einen neuen
  Text in fünf Katalogen, und zwei Sitzungen, die gleichzeitig in dieselben
  Katalogdateien schreiben, überschreiben einander still. Vorschlag, wenn
  die Datei frei ist: „Mindestlänge" (in keinem Katalog vorhanden, also fünf
  neue Einträge).

## Ein deutscher Bezeichner im B-Rep-Langloch

`app/core/brep/features.py:326` trägt `ende = _axis_point(...)`, direkt neben
`near_end` — offenbar sollte es `far_end` heißen.
`test_language_rules::test_identifiers_are_english` ist deshalb rot.

Gefunden hat es der `pre-commit`-Hook bei meinem Commit um 06:39, und er hat
richtig entschieden: Keine Datei *meines* Commits war genannt, also lief er
durch. Die Datei ist ungestaget und war 37 Minuten alt (mtime 06:05) — die
zweite Sitzung baut dort gerade `_slot_from`. **Nicht angefasst**: Ein Edit in
einer Datei, die gerade geschrieben wird, geht in die eine oder andere
Richtung verloren. Ihr eigener `pre-commit`-Lauf hält sie damit auf.

## Aus der Nachkontrolle: was in den Commits steckt, das nicht hineingehört

`7354f62d` heißt „Zwei Funde an derselben Operation" und nennt als Beifang zwei
Katalogzeilen. Tatsächlich sind es **301 eingefügte Zeilen** in
`prepare_ops.py`, davon zwei Hunks zu den genannten Funden. Mitgekommen ist
ungestagte Arbeit der zweiten Sitzung: `x/y/z` als Vorderseitenfelder für
`ResizeHoleParams` und `SlotHoleParams`, `moved_hole`/`moved` samt
`edit.fill_bore` und `_closed_at`, `_polygon_gain_for`, und der Tausch
`applies_to` — `fillet` wandert von `move_feature` zu `remove_feature`, also
eine Änderung daran, was das Menü anbietet. `8aeae333` bringt zusätzlich den
Regelabschnitt „Ein Loch versetzt man an beiden Kernen gleich" zu eben dieser
Arbeit.

Nichts davon wird rückabgewickelt (kein Revert). Was bleibt, ist die Lehre:
**`git add <datei>` nimmt die ganze Datei, auch die fremden Zeilen darin.** Im
geteilten Baum gehört `git diff --cached --stat` vor jeden Commit — und gelesen
wird er gegen die eigene Absicht, nicht gegen das Gefühl.

Die zweite Sitzung hat auf dieser Arbeit inzwischen weitergebaut
(`compensation_findings` beim Versetzen, `slot` in `PARAMETRIC_KINDS`), beides
mit dem Vermerk „Fund des Reviews, 11.09.2026".

## Nachgeprüft und **nicht** zu ändern

- **`types.is_a_cavity` führt `slot` bewusst nicht.** Zwei Durchsichten haben
  es als „eine Zeile Fix" gemeldet; sieben Zeilen darunter steht, warum das
  falsch wäre: `relations.sleeve_at` meldete an einem Langloch die doppelte
  Stärke der dünnsten Stelle (gemessen an Zapfen Ø 20 mit Langloch Ø 8 auf
  14 mm: Flanken 6 mm, Enden 3 mm), und Wandstärke ist druckkritisch. Der
  Punkt ist RM-152 mit Abnahmekriterium. Der Verweis im Code zeigte auf RM-151
  und ist berichtigt.
- **`.claude/rules/schichtanalyse.md` zu `detect_voids`.** Gemeldet als „nennt
  zwei Bedingungen statt vier" — nachgesehen, die Regel nennt inzwischen alle
  vier.
- **`slot_hole` hat sehr wohl eine Vorgabe für die Länge** (20,0). Gemeldet war
  „begrüßt mit einer Absage bei Ø 6,6"; am Stand vom 11.09.2026 trifft das
  nicht zu. **Eine Absage gab es trotzdem**, und zwar durch die Prüfung, die in
  derselben Nacht dazukam — behoben in `cb876947`.

## `mushroom.stl`

Liegt seit dem 25.08.2026 getrackt in der Wurzel, 1,4 KB, und wird von keiner
Datei genannt. Der Commit, der sie hereinbrachte, heißt „Ein leerer Index sieht
aus wie ein Baum, in dem alles gelöscht wurde". Die neue `.gitignore`-Regel
nimmt sie ausdrücklich aus, statt sie zu verdecken — ob sie bleibt, entscheidet
jemand, der weiß, wofür sie da war.
