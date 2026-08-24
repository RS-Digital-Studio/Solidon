# Konzept: Varianten zusammenlegen — eine Handlung, ein Eintrag

Stand 24.08.2026. Anlass: Robert setzte eine Bohrung, wählte „Gewinde", und das
Gewinde saß außen. Der Fehler dahinter ist behoben (`7d0d9173`), der Satz
danach ist dieses Konzept: *„nicht für ähnliches gefühlt 20 verschiedene
aktionen, eine und dann im dialog präzisieren."*

Es gilt zusammen mit Bauplan §25 (Operationskatalog), §35 (Oberflächengrenzen),
§9 (Verträge), `AGENTS.md` (Regeln 4, 17, 20) und dem Kommentar über
`MENU_TWINS` in `app/core/registry/registry.py:101`.

**Beauftragt ist A bis D**, Konzept zuvor. E steht in §7 als Nicht-Ziel.

---

## §0 Ist-Zustand, gemessen am 24.08.2026 gegen `bc002f1a`

Jede Aussage hier ist am Register gemessen oder im Code belegt. Wo eine andere
Sitzung gemessen hat, steht sie dabei — vier haben mitgearbeitet.

**Der Bestand.** 86 Operationen im Register, 83 sichtbare Menüeinträge, 3 als
`MENU_TWINS` versteckt. Kategorien: 20 `parts`, 9 `transform`, 9 `mesh`,
7 `primitive`, 6 `prepare`, 5 je `scene`/`shaping`/`sketch`, 4 je
`boolean`/`holes`, 3 je `surface`/`colour`/`import`, 2 `label`, 1 `repair`.

**Das Prinzip existiert schon, und es ist wörtlich Roberts.**
`registry.py:101` nennt es „eine Operation je Handlung, nicht je Variante" und
setzt es an drei Paaren um: `create_brep_box`→`create_box`,
`create_brep_cylinder`→`create_cylinder`, `drill_brep_hole`→`drill_hole`. Der
sichtbare Eintrag trägt einen Umschalter „Exakter Körper (B-Rep)"
(`_EXACT_TOGGLE`, `registry.py:120`), und der Dialog wählt die Op. Die Ops
bleiben im Register getrennt — Verlauf und Provenienz brauchen das.

**Das Werkzeug für Varianten im Dialog existiert ebenfalls.**
`OperationDialog.switch_variant` (`app/ui/op_dialog.py:689`, gerufen aus
`app/ui/main_window.py:5327` und `:5605`) blendet aus, was die gewählte
Variante nicht kennt; `DEPENDENT_FIELDS` / `ParamSpec.depends_on`
(`op_dialog.py:862`) grauen aus, was ohne Wirkung wäre. `op_dialog.py:862`
spricht selbst von „demselben Versprechen, das `switch_variant` bei den
Zwillingen gibt" — der Mechanismus ist also schon verallgemeinert gedacht.
(Gefunden von `formwerk-9e`, von mir an den vier Stellen nachgeprüft.)

**Die Menügrenzen sind eingehalten.** `tests/test_interface_limits.py`
(`MAX_MENUS = 9`, `MAX_SUBMENU_ENTRIES = 12`) ist grün. Er misst **am gebauten
Fenster** und zählt ein Untermenü als *eine* Zeile; sein Docstring warnt
ausdrücklich, eine Zählung über das Register „sähe davon nichts". Die
Register-Zahlen (Ändern 34, Bausteine 20, Erzeugen 15) sind deshalb **nicht**
die Nutzersicht und taugen nicht als Begründung — die gemessene Nutzersicht
steht unten in derselben §.

**Die Nutzersicht, gemessen am gebauten Fenster** (`formwerk-be`, offscreen —
Menüs sind dort vollständig lesbar, nur VTK-Aktoren nicht). „Zeilen" zählt wie
§35 zählt, ein Untermenü als eine Zeile:

| Menü | Zeilen | Einträge dahinter | Untermenüs |
|---|---|---|---|
| Datei | 12 | 12 | — |
| Bearbeiten | 8 | 8 | — |
| Objekt | 5 | 5 | — |
| Erzeugen | 4 | 15 | 4 |
| Ändern | 7 | 34 | 7 |
| Bausteine | 9 | 20 | 7 |
| Vorbereiten | 10 | 10 | — |
| Ansicht | 7 | 23 | 3 |
| Hilfe | 10 | 10 | — |

**Neun Menüs — die Grenze aus §35 ist genau erreicht**, ein zehntes ist nicht
möglich. *Datei* liegt mit 12 Zeilen auf der Zwölf-Grenze. Kein Menü reißt sie.
Die 34 aus dem Register stimmen also, sie stehen nur nie zusammen auf dem
Schirm.

Zwei Beobachtungen daraus, die für dieses Konzept mehr wert sind als die
Zeilenzahl:

- **Das dickste Untermenü ist nicht das größte Menü.** *Netz* (9) und
  *Transformation* (9) unter *Ändern* sind die längsten Einzellisten der
  Anwendung. Und *Transformation* ist genau der Ort der drei Bett-Einträge,
  zwischen denen Robert nicht wählen konnte: Wer *Auf das Bett setzen* sucht,
  muss erst wissen, dass Absenken eine Transformation ist.
- **Ein Untermenü mit einem Eintrag ist eine Zwischenebene für nichts.**
  *Reparatur* hat einen, *Einlegeteile* einen. `main_window` kennt dafür eine
  Regel (`_fits_without_submenus`, „eine Gruppe, die ganz hineinpasst, braucht
  kein Untermenü"), die hier offenbar nicht greift. Das legt nichts zusammen
  und spart trotzdem einen Klick — **nicht beauftragt**, aber notiert.

> **Daraus folgt die Leitfrage dieses Konzepts.** Robert klagt nicht über zu
> lange Menüs — die sind formal in Ordnung. Er klagt über Einträge, die er
> nicht auseinanderhalten kann. Das Kriterium ist deshalb nicht „Menü zu
> lang", sondern: **muss der Nutzer diese zwei Einträge unterscheiden, und
> kann er es am Titel?**

**Und wir können nicht messen, was verwirrt.** `formwerk-20` hat alle 86 Titel
paarweise auf gemeinsame tragende Wörter geprüft — 36 Paare, nach Abzug der
bestehenden Zwillinge genau ein Kandidat. Dieselbe Messung hätte Roberts
Gewinde-Fall **nicht gefunden**: „Gewinde" und „Gewindebolzen" sind für einen
Wortvergleich zweierlei. Ein Suchmuster findet Namensähnlichkeit, nicht
Verwechselbarkeit. **Die belegten Verwechslungen sind der bessere Detektor**,
und es gibt zwei, beide von Robert selbst:

1. Bohrung gesetzt, „Gewinde" gewählt, Außengewinde bekommen (§5).
2. „das an druckbett ausrichten funktioniert nicht mehr" — `formwerk-be`
   musste zurückfragen, welcher von **drei** Einträgen gemeint ist
   (`place_on_bed`, `arrange_bed`, `orient_for_print`). Robert benutzte eine
   vierte Formulierung, die auf alle drei passt.

---

## §1 Entscheidung E1 (A): Aushöhlen wird ein Eintrag

**Der Fall.** Zwei Ops, dieselbe Handlung, zwei Rechenkerne:

| Op | Titel | Kategorie | verbraucht | `requires_kind` | Kürzel |
|---|---|---|---|---|---|
| `hollow_object` | Aushöhlen | `prepare` | 1 | — | `Ctrl+H` (Register) |
| `shell_exact` | Exakt aushöhlen | `shaping` | 1 | `brep` | `S` (Schema) |

Das ist das Twin-Muster in Reinform, mit zwei Verschärfungen: Die zwei stehen
in **verschiedenen Kategorien**, also in verschiedenen Menüs. Und
`_EXACT_TOGGLE` **verspricht die Funktion bereits** — sein Text zählt auf, was
nur im exakten Kern geht, und nennt darin „exaktes Aushöhlen"
(`registry.py:128`), während dieselbe Funktion als eigener Eintrag daneben
steht. (Kandidat gefunden von `formwerk-20`; der Registername lautet
`hollow_object`, nicht `hollow`.)

**E1: `shell_exact` wird vierter Eintrag in `MENU_TWINS`**, Schlüssel
`shell_exact`, Wert `hollow_object`. Kein neuer Mechanismus, kein neuer Text —
`_EXACT_TOGGLE` deckt den Umschalter ab, weil es genau um die zwei Rechenkerne
geht.

**Drei Nebenwirkungen, die A von „einer Tabellenzeile" unterscheiden.** Alle
drei sind belegt, nicht vermutet:

- **E1.1 — Ein Handlungsvorschlag wird zur Sackgasse.**
  `app/core/sketch/ops.py:203` sagt im Fehlerfall: *„wer aushöhlen muss, nimmt
  Exakt aushöhlen statt Aushöhlen."* Verschwindet der Menüeintrag, zeigt
  dieser Satz auf etwas, das es nicht mehr gibt — ein Verstoß gegen Regel 17
  in ihrem Kern, denn der Vorschlag *ist* die Handlung. `tests/test_sketch_ops.py:130`
  prüft ihn wörtlich. **Der Satz muss auf den Umschalter zeigen**, nicht auf
  den Eintrag: „… nimmt *Aushöhlen* mit gesetztem Haken *Exakter Körper
  (B-Rep)*."
- **E1.2 — `shell_exact` ist der erste Zwilling mit Kürzel.** Die drei
  bestehenden haben keines (gemessen: `shortcut=None` bei allen drei). Der
  Menüaufbau überspringt versteckte Zwillinge mit `continue`
  (`main_window.py:1650`), erzeugt also **keine `QAction`** — und
  `_operation_action` ist die einzige Stelle, die das Kürzel setzt
  (`main_window.py:2100`). Das „S" aus `shortcut_schemes.py:46` hätte danach
  keine Aktion mehr. **Entscheidung: Das Kürzel entfällt** und der Eintrag
  wird aus `shortcut_schemes.py` entfernt. Begründung: Ein Kürzel, das eine
  Variante *im Dialog* wählt, wäre ein Kürzel für einen Haken, nicht für eine
  Handlung; `Ctrl+H` auf `hollow_object` öffnet den Dialog, in dem der Haken
  steht. Wer „S" gewohnt ist, verliert einen Tastendruck, keine Funktion.
  Alternative wäre, `Ctrl+H` mit vorgesetztem Haken zu belegen — das wäre ein
  zweites Kürzel für dieselbe Op mit anderem Vorbelegungszustand, und dafür
  gibt es im Bestand kein Vorbild.
- **E1.3 — Erreichbarkeit bleibt Pflicht.** `MENU_TWINS` verlangt laut eigenem
  Kommentar, dass der versteckte Zwilling über Befehlspalette und Verlauf
  erreichbar bleibt. `app/ui/command_palette.py:183` führt `hollow_object` mit
  Suchbegriffen; `shell_exact` braucht dort einen eigenen Eintrag, sonst ist
  er nach dem Verstecken nur noch über den Haken zu finden.

**Betroffene Tests:** `tests/test_sketch_ops.py:130` (Fehlertext),
`tests/test_operation_ui.py:396` (`BREP_ONLY` führt `shell_exact`).

---

## §2 Entscheidung E2 (B): Aus Skizze erzeugen wird ein Eintrag

**Gemessen von `formwerk-9e`** an den fünf `sketch`-Ops:

| Op | verbraucht | erzeugt | `requires_kind` | `applies_to` | eigene Felder |
|---|---|---|---|---|---|
| `sketch_extrude` | 0 | 1 | — | — | `height` |
| `sketch_revolve` | 0 | 1 | — | — | `offset` |
| `sketch_sweep` | 0 | 1 | — | — | `bend_radius`, `bend_angle` |
| `sketch_loft` | 0 | 1 | — | — | `height`, `top_scale` |
| `sketch_pocket` | **1** | 1 | **brep** | **`("face",)`** | `depth` |

Die ersten drei vorderen Felder sind bei allen fünf identisch (`shape`,
`length`, `width`).

**E2: Die vier mit `consumes=0` werden ein Eintrag „Aus Skizze erzeugen"** mit
einem Art-Umschalter. Feldrechnung gegen §35: 3 gemeinsame + 1 Umschalter +
höchstens 2 variantenspezifische = **6 vorn, erlaubt sind 8**.

> **ZURÜCKGENOMMEN am 24.08.2026, noch am selben Tag. Es bleiben vier.** Die
> Abweichung unten war ein Fehlschluss von mir, und er steht hier, weil die
> Begründung mehr wert ist als ihre Löschung: **Ich habe aus den `doc`-Texten
> auf die Bedeutung geschlossen, statt dem Datenfluss zu folgen.** Der Code
> sagt es eindeutig — `sketch_revolve` ruft in `ops.py:521` dasselbe
> `_sketch_profile(shape, length, width, corners)` wie seine drei Geschwister
> und baut daraus dieselbe 2D-Grundform. Was danach mit dem Profil geschieht
> (an die Achse schieben, drehen; `ops.py:522` nimmt `width / 2` als Versatz),
> ist der Grund für den abweichenden Satz — **er beschreibt die Wirkung im
> Ergebnis, nicht eine andere Bedeutung der Zahl.** Die Zahl ist dieselbe, das
> gemeinsame Feld ist sicher, und der variantenabhängige `doc`-Satz soll
> bleiben.
>
> Widerlegt von `formwerk-9e`, von mir am Datenfluss nachgeprüft. Die Lehre ist
> dieselbe wie an drei anderen Stellen dieses Tages: Eine Dokumentationszeile
> ist ein Beleg für das, was jemand gemeint hat, nicht für das, was der Code
> tut. Ich hatte sie als Messung behandelt.
>
> **Ein echter Fund kam dabei heraus, und er gehört zu P3:** `width` wies über
> `depends_on` das Vieleck als wirksam aus, obwohl die Zahl dort nirgends
> ankommt — gemessen `revolve/polygon` mit `width=5` und `width=20`, beide
> 32648,3886. Behoben von `formwerk-9e` in `5c856212`, die Liste heißt jetzt
> bei allen vier `("rectangle", "slot")`. **Wäre das offen geblieben, hätte die
> Zusammenlegung den Fehler auf alle vier verteilt, und er hätte danach wie
> eine Folge des Umbaus ausgesehen.** Offen bleibt ein Katalogtext: Der
> `doc`-Satz sagt „Beim Kreis ohne Wirkung" und müsste „Beim Kreis und beim
> Vieleck ohne Wirkung" heißen, in fünf Sprachen — das gehört zu P3.
>
> *Der widerlegte Stand, zur Nachvollziehbarkeit:*
>
> **Abweichung vom Konzeptstand, gemessen am 24.08.2026 bei der Umsetzung:
> Es sind drei, nicht vier — `sketch_revolve` fällt heraus.** Die drei
> gemeinsamen Felder heißen bei allen vier gleich, sie **bedeuten** aber nicht
> dasselbe. Gemessen an den `doc`-Texten des Schemas:
>
> | Op | `length` | `width` |
> |---|---|---|
> | `sketch_extrude`, `_sweep`, `_loft` | „Länge in X" | „Breite in Y" |
> | `sketch_revolve` | „Ausdehnung des Querschnitts **von der Achse weg**" | „Höhe des Querschnitts **entlang der Achse**" |
>
> Ein gemeinsames Feld „Breite (Y)" wäre bei `revolve` eine stille
> Bedeutungsänderung — der Nutzer liest „Breite in Y" und stellt die Höhe
> entlang der Rotationsachse ein. `switch_variant` könnte es nicht auffangen:
> Es tauscht Op-Beschreibung und `caveat`, aber **nicht** Titel und `doc` der
> einzelnen Felder (gelesen an `op_dialog.py:1106`).
>
> `formwerk-9e`s Messung ist damit nicht falsch, sie war auf **Namens**gleichheit
> gerichtet — „in den ersten drei identisch" stimmt. Die Bedeutung stand nicht
> in der Frage, die ich gestellt hatte. **E2 gilt für `sketch_extrude`,
> `sketch_sweep` und `sketch_loft`;** `sketch_revolve` bleibt eigen wie
> `sketch_pocket`, nur aus einem anderen Grund. Feldrechnung bleibt 6 von 8.
>
> *(Ende des widerlegten Stands. Gültig ist: vier Ops, `sketch_pocket` bleibt
> eigen, `sketch_revolve` kommt mit.)*
>
> Die unterschiedlichen **Vorgaben** (extrude 40/20, sweep 10/10, loft 40/20)
> bleiben ein hingenommener Rest: Wer die Art wechselt, behält seine Werte.
> Das ist keine falsche Bedeutung, nur eine andere Ausgangsgröße.

**E2.1 — `sketch_pocket` bleibt eigen.** Sie verbraucht einen Körper, setzt an
einer Fläche an und verlangt einen exakten Eingang. `consumes` ist eine
statische Eigenschaft des Registereintrags; eine Op, die je nach
Umschalterstellung null oder einen Körper nimmt, gibt es nicht. Das wäre kein
Dialogumbau, sondern eine Änderung an Bauplan §9 — und die geht nur mit
Roberts Zustimmung.

**E2.2 — `MENU_TWINS` trägt das nicht.** Die Tabelle ist 1:1 (ein versteckter
Zwilling → ein sichtbarer) und ihr Umschaltertext `_EXACT_TOGGLE` spricht von
Rechenkernen. Hier sind es 4:1 und die Variante ist die *Art* der Erzeugung.
Es braucht eine zweite Tabelle mit eigenem Umschaltertext — Vorschlag
`MENU_VARIANTS: dict[str, str]` daneben, gleiche Bauart, eigener Text. Nicht
`MENU_TWINS` erweitern: Sein Kommentar warnt ausdrücklich davor, die Tabelle
für etwas anderes als die zwei Rechenkerne zu benutzen, weil dann „ein drittes
Paar einen Haken bekäme, der von einem exakten Körper spricht, den es nicht
gibt."

**E2.3 — Gebietsfrage, offen.** `app/core/sketch/ops.py` gehört derzeit
`formwerk-9e`. Ob die Ops selbst angefasst werden müssen, entscheidet sich an
E2.2: Steht die Zuordnung in `registry.py` und baut `main_window.py` den
Dialog, bleiben die Ops unberührt. Der Fehlertext in `ops.py:203` (E1.1) muss
ohnehin geändert werden — dafür ist eine Absprache nötig.

---

## §3 Entscheidung E3 (C): Was in eine Bohrung kommt, wird eine Frage

**Gemessen an den Bausteingruppen.** Drei Bausteine tragen `at_hole` und
beantworten dieselbe Nutzerfrage — *„ich habe ein Loch und will, dass darin
eine Schraube hält"*:

| Baustein | Titel | Gruppe | subtraktiv |
|---|---|---|---|
| `printed_thread` | Gewinde | `fasteners` | nein |
| `nut_trap` | Mutternfalle | `fasteners` | ja |
| `heatset_m4` | Heat-Set-Einpressbuchse | `inserts` | ja |

Sie stehen in **zwei verschiedenen Gruppen**, `heatset_m4` allein in
`inserts` — ein Untermenü mit einem einzigen Eintrag. Dass Robert bei genau
dieser Frage falsch abgebogen ist, ist damit kein Zufall.

**E3: Ein Eintrag „Schraubaufnahme einsetzen" mit drei Arten.** Die
Registereinträge bleiben getrennt (Provenienz, `parts_version`,
Änderungsverlauf je Baustein); zusammengelegt ist die Bedienung.

**E3.1 — Das ist der anspruchsvollste der vier, und zwar fachlich.** Die drei
haben verschiedene Parameterschemata und verschiedene `at_hole_values`: Eine
Buchse braucht die **kleinste** Größe, die die Bohrung *aufweitet*, ein Gewinde
die **größte**, die noch *hineinpasst* (`placement.py:78`, wörtlich: „eine
gemeinsame Formel wäre in einem der beiden Fälle falsch"). Der Umschalter muss
also beim Wechsel die Größenvorgabe **neu ableiten**, nicht nur Felder
ausblenden.

> **Geprüft am 24.08.2026, und die Antwort ist nein.** `switch_variant`
> (`op_dialog.py:1106`) tut genau drei Dinge: Zeilen über `setRowVisible`
> ein- und ausblenden, die Op-Beschreibung tauschen, den `caveat` tauschen.
> **Es setzt keine Werte.** Eine Größenvorgabe kann es nicht neu ableiten.
>
> Damit tritt die in §7 vorab festgelegte Folge ein: **P4 wird
> zurückgestellt und gemeldet**, statt einen Umschalter zu bauen, der die
> falsche Größe stehen lässt. Ein Nutzer, der von „Gewinde" auf
> „Einpressbuchse" wechselt, behielte sonst die größte Größe, die in die
> Bohrung *passt*, während die Buchse die kleinste braucht, die sie
> *aufweitet* — und das ist wörtlich der Fehler, den
> `test_a_bore_proposes_the_size_that_fits_it` seit dem 23.08.2026 verhindert
> (M3 an einer Ø 5,19-Bohrung, Schnitt trug ±0 mm³ ab).
>
> **Was P4 möglich machen würde**, als Entscheidung für Robert und nicht
> unterwegs zu treffen: `switch_variant` um das Neuableiten von Vorgaben
> erweitern. Das ist keine Zeile, sondern eine Bedienfrage — überschreibt der
> Wechsel einen Wert, den der Nutzer selbst eingetragen hat? Beide Antworten
> sind vertretbar und beide haben einen Preis.

**E3.2 — Reihenfolge:** E3 kommt zuletzt. Wenn E1 und E2 stehen, ist bekannt,
wie weit `switch_variant` trägt.

---

## §4 Entscheidung E4 (D): Die Gewinde-Titel sagen, was sie tun

**Der Fall.** Zwei Einträge, beide über Gewinde, verschiedene Handlungen:

| Op | Titel | verbraucht | erzeugt |
|---|---|---|---|
| `insert_printed_thread` | Gewinde | 1 | 1 |
| `thread_exact` | Exakten Gewindebolzen erzeugen | 0 | 1 |

**E4: Kein Zusammenlegen, keine Migration — die Titel werden geändert.**
Begründung (von `formwerk-20`, und ich schließe mich an): 0→1 gegen 1→1 heißt
„erzeugt ein Objekt" gegen „ändert eines". Das ist kein Wert in einem Dialog,
das sind zwei Handlungen — ein Umschalter wäre falsch. Migration ist genauso
falsch: Beide Ops sind sinnvoll und keine ist die alte Fassung der anderen
(`split_plane` ging auf, weil es *ersetzt* wurde).

Falsch sind die Titel. „Gewinde" verschweigt, dass es in einen Körper
schneidet; „Exakten Gewindebolzen erzeugen" verschweigt, dass ein neues Objekt
entsteht — es sagt „Bolzen", was ein Kundiger versteht und Robert nicht.

**Vorschlag:** „Gewinde in Bohrung schneiden" und „Gewindebolzen als neues
Objekt". Beide beantworten die Frage, an der Robert gescheitert ist.

**E4.1 — Kosten:** zwei Registereinträge, fünf Übersetzungskataloge
(`en`, `es`, `fr`, `it`, `pt`), und `tests/test_translations.py` prüft jeden.
Keine Migration, kein Formatwechsel: Titel sind Anzeige, nicht Schlüssel.

---

## §5 Was dieses Konzept **nicht** tut

- **`orient_for_print` wird nicht mit den Bett-Ops zusammengelegt.** Sie
  *dreht*, die anderen zwei *verschieben*. Ein Dialog mit „drehen oder
  verschieben?" wäre eine Frage, die man vorher stellen muss, nicht nachher.
  (`formwerk-be`)
- **`place_on_bed` + `arrange_bed` bleibt offen (Kandidat E).** Plausibel
  dieselbe Handlung mit Umschalter „nur das gewählte Objekt", aber
  `whole_scene=True` gegen `consumes=1` ist im Register ein echter
  Unterschied. Nicht beauftragt, nicht zu Ende gedacht — gehört geprüft, bevor
  jemand es anfasst.

  > **Und es ist teurer als es aussieht.** Gemeldet von `formwerk-be` am
  > 24.08.2026: Zwei Knöpfe im Prüfbericht nennen diese Registernamen als
  > **Zeichenkette**, und sie stehen nicht dort, wo man beim Zusammenlegen
  > sucht.
  >
  > | Datei | Stelle |
  > |---|---|
  > | `app/ui/panels.py` | `FINDING_ACTIONS`: `arrange.below_bed`, `arrange.above_bed`, `arrange.off_the_plate` |
  > | `app/ui/main_window.py` | `error_handlers()`: `"place_on_bed"`, `"arrange_on_bed"` |
  > | `app/ui/main_window.py:6353` | `REGISTRY.get("place_on_bed")` |
  > | `app/ui/main_window.py:6388` | `REGISTRY.get("arrange_bed")` |
  >
  > **Der Unterschied, auf den es ankommt, ist der zwischen Verstecken und
  > Auflösen.** Alle vier Pakete dieses Konzepts *verstecken* nur den
  > Menüeintrag; der Registereintrag bleibt, und `REGISTRY.get(…)` findet ihn
  > weiter. Wer eine Op dagegen **auflöst** — sie also im Register durch eine
  > andere ersetzt —, nimmt ihren Namen mit, und dann wirft `REGISTRY.get(…)`
  > einen `InternalError`: Der Kunde klickt im Prüfbericht auf *Auf das Bett
  > setzen* und bekommt „Im Programm ist ein unerwarteter Fehler aufgetreten"
  > samt Fehlerbericht-Ordner.
  >
  > **Der bestehende Test fängt es nicht.**
  > `test_every_offered_error_action_does_something` prüft, dass jede
  > angebotene Handlung einen *Handler hat* — nicht, dass er *wirkt*. Genau
  > diese Lücke war Roberts Fehler vom selben Tag: `_arrange_after_error`
  > existierte, war verdrahtet und tat nichts (`a22ffa48`), und der Test blieb
  > grün. Ein Namensabgleich gegen das Register wäre deshalb der schwächere
  > Wächter; der verlässliche misst die Wirkung, Muster in
  > `tests/test_ui.py::test_arranging_from_the_report_really_moves_the_bodies`.
  > `formwerk-be` schreibt ihn.
- **Keine Kandidaten**, damit sie später nicht aufgewärmt werden: „Textur
  aufbringen"/„Text aufbringen" (nur ein gemeinsames Verb), „Dreiecke
  verringern"/„Dreiecke angleichen" (dito), „Bohrung setzen"/„Bohrung
  verschließen" (Gegenteile). (`formwerk-20`)
- **Kein Verschmelzen von Registereinträgen.** In allen vier Fällen bleiben
  die Ops getrennt. Verschmelzen würde eine Formatmigration verlangen —
  `AGENTS.md` fordert dafür `format_version`, Migrationsfunktion,
  eingecheckte Beispieldatei und Test. Nichts davon ist hier nötig.

---

## §6 Fallen, die beim Umsetzen warten

Beide von `formwerk-20` heute selbst getroffen und gemessen:

- **`tr()` übersetzt sofort.** Eine Modulkonstante `X = tr("…")` friert die
  Sprache ein, die beim *Import* galt. Gemessen: nach `set_language("en")`
  liefert `str(_(…))` den englischen Satz, ein zur Importzeit ausgewertetes
  `tr(…)` weiter den deutschen. Also `_()` für Konstanten, `str()` erst an der
  Verwendungsstelle. `_EXACT_TOGGLE` macht es richtig und ist das Vorbild für
  jeden neuen Umschaltertext.
- **`i18n.extract` liest nur das erste Argument von `_()`/`tr()`, wenn es eine
  feste Zeichenkette ist.** Der naheliegende Weg — Satz als nackte Konstante,
  an der Stelle `tr(KONSTANTE)` — wirft ihn aus allen fünf Katalogen.
- **Beide Wege sehen richtig aus, keiner wird rot.** Der erste lügt nur bei
  einem Sprachwechsel, der zweite fehlt nur in fünf Katalogen.

Dazu aus §0: **Die Register-Zahl ist nicht die Nutzersicht.** Wer den Erfolg
dieses Umbaus belegen will, zählt am gebauten Fenster
(`test_interface_limits.py` tut es) und nicht über Kategorien.

---

## §7 Umsetzungsplan

Ein Commit je Paket, jedes Paket endet mit grünem Tor. Reihenfolge nach Kosten
und Erkenntnisgewinn: das billigste zuerst, das fachlich schwerste zuletzt.

| Paket | Inhalt | Umfang | Verifikation |
|---|---|---|---|
| **P1** | E4: Gewinde-Titel + fünf Kataloge | S | `test_translations.py`, `test_registry.py`, Sammelgruppe |
| **P2** | E1: `shell_exact` in `MENU_TWINS`, Fehlertext (E1.1), Kürzel entfernen (E1.2), Palette (E1.3) | M | `test_sketch_ops.py`, `test_operation_ui.py`, `test_interface_limits.py`, Fenstergruppe |
| **P3** | E2: `MENU_VARIANTS` + Dialog für die vier Skizzen-Ops | L | `test_interface_limits.py` (Felder vorn), `test_sketch*.py`, Fenstergruppe |
| **P4** | E3: Schraubaufnahme, drei Arten | L | `test_placement.py`, `test_parts.py`, Fenstergruppe |

**P1 zuerst und nicht P2**, obwohl P2 die Tabellenzeile ist: P1 ändert nur
Anzeigetexte und ist damit das Paket, an dem sich die Übersetzungsfallen aus §6
folgenlos zeigen. Wer sie in P3 zum ersten Mal trifft, sucht sie zwischen
Dialogumbau und Katalogen.

**Vor P3 zu klären:** die Gebietsfrage E2.3 mit `formwerk-9e`.
**Vor P4 zu klären:** ob `switch_variant` eine Größenvorgabe neu ableiten kann
(E3.1). Kann es das nicht, wird P4 zurückgestellt und gemeldet, statt einen
Umschalter zu bauen, der die falsche Größe stehen lässt.

---

## §8 Leitplanken

- **Die Registereinträge bleiben getrennt.** Zusammengelegt wird die
  Bedienung, nie die Op. Verlauf, Provenienz und `parts_version` hängen daran.
- **Jede versteckte Op bleibt erreichbar** — Befehlspalette und Verlauf, wie
  `MENU_TWINS` es verlangt. Eine Op, die nur noch über einen Haken zu finden
  ist, ist eine verlorene Op.
- **Kein Handlungsvorschlag zeigt auf einen entfernten Eintrag** (Regel 17).
  E1.1 ist der bekannte Fall; wer ein Paket baut, sucht vorher mit `grep` nach
  dem Titel, den er versteckt.
- **Keine Änderung an Bauplan §9.** Wo `consumes` im Weg steht (E2.1), bleibt
  die Op eigen. Der Vertrag wird nicht für eine Menüzeile gebeugt.
- **Erfolg wird am Fenster gemessen**, nicht am Register.
- **Jede Titel- oder `doc`-Änderung im Register verlangt einen Lauf von
  `tools/make_manual.py`.** `website/handbuch.html` und
  `website/en/manual.html` sind **erzeugte** Dateien, und
  `test_manual.py::test_the_website_page_carries_the_generated_reference`
  hält sie mit dem Register zusammen. Bei P1 ist genau das passiert: Die zwei
  neuen Gewinde-Titel machten beide Seiten veraltet, und `main` war rot.
  Weil weitere Titeländerungen folgen, wird **einmal am Ende** erzeugt und
  nicht nach jedem Paket.
- **Bei zwei Lesarten anhalten und fragen** (Regel 21). Dieses Konzept nennt
  drei offene Punkte (E2.3, E3.1, Kandidat E); keiner davon wird unterwegs
  still entschieden.

---

## §9 Übergabe-Notizen

*Wird je Paket fortgeschrieben. Commit-Hashes werden nachgetragen.*

- **P1** — **erledigt**, `520b10f0`. Die Falle aus §6 trat sofort ein: Der
  Katalogschlüssel „Gewinde" gehört auch dem Merkmalsnamen
  (`registry.py:168`); wer ihn mit dem Op-Titel mitnimmt, benennt in fünf
  Sprachen das erkannte Merkmal um. Vor dem Schreiben geprüft, Schlüssel
  unberührt. Verifiziert: `test_translations` 126, `test_interface_limits` 32,
  mypy 0, Sammelgruppe 3586 passed / 23 skipped.
> **Eine Lücke in meinem eigenen Prüfen, und sie hat `main` rot gemacht.**
> Nach P1 und P2 habe ich nur die Sammelgruppe gefahren, nicht die 30
> Fensterdateien — mit der Begründung, dass fremde UI-Zwischenstände im Baum
> lagen und die Fenstergruppe deshalb nicht aussagekräftig sei. Die
> Begründung stimmte, die Folgerung war falsch: `tests/test_manual.py` liegt
> in dieser Gruppe (es nennt `MainWindow` im Text), und es ist genau der
> Test, der meine Titeländerung geprüft hätte. Aus „nicht aussagekräftig"
> wurde „nicht gelaufen", und das ist dieselbe Verwechslung wie im Tor
> selbst (`3916cb1f`): **Ein Lauf, den ich auslasse, ist kein Lauf, dem ich
> misstraue.** Gefunden hat es `formwerk-20` in einem eigenen Arbeitsbaum —
> also dort, wo die Fenstergruppe aussagekräftig ist. Das ist die Antwort auf
> mein Problem, nicht das Auslassen.

- **P2** — läuft. Wartet auf **eine Zeile in fremdem Gebiet**: der Fehlertext
  `app/core/sketch/ops.py:203` (E1.1) gehört `formwerk-9e`, angefragt.
  `app/ui/shortcut_schemes.py` und `tests/test_sketch_ops.py` sind frei
  geworden. Ohne den Fehlertext wird der Eintrag in `MENU_TWINS` nicht gesetzt:
  Die Reihenfolge ist Vorschlag zuerst, Verstecken danach — andernfalls steht
  zwischen zwei Commits eine Sackgasse im Produkt.
- **P3** — **bleibt bei vier Ops**; meine Schrumpfung auf drei war ein
  Fehlschluss und ist am selben Tag zurückgenommen (§2). E2.3 ist beantwortet:
  Die Registereinträge werden **nicht** angefasst, die Zuordnung kommt in
  `registry.py`, den Dialog baut `main_window.py`, beide sind meine. Dazu ein
  Katalogtext in fünf Sprachen („Beim Kreis **und beim Vieleck** ohne
  Wirkung"), von `formwerk-9e` übergeben.
- **P4** — **zurückgestellt**, E3.1 geprüft und negativ: `switch_variant` setzt
  keine Werte. Nicht „später vielleicht", sondern eine Entscheidung für Robert
  (§3).

Beteiligt an §0 bis §6: `formwerk-20` (Titelmessung über 86 Ops, E4-Begründung,
Übersetzungsfallen), `formwerk-9e` (Skizzen-Messung, `switch_variant`),
`formwerk-be` (die drei Bett-Einträge, Menüs offscreen zählbar), `formwerk-d1`
(Signaturmessung als Methode). Die Zuordnung steht an jeder Aussage.
