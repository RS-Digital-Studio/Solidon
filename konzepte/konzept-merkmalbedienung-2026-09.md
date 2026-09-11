# Eine Stelle für das gewählte Merkmal

> **Stand:** umgesetzt, 11.09.2026 — alle sieben Pakete sind gefahren.
> Die manuelle Abnahme am laufenden Fenster (§4) steht aus.
> **Anlass:** Robert am 11.09.2026, an einer gewählten Bohrung: „wenn ich das
> langloch zieh, fehlen die Maße zu den kanten usw die wir bei bohrungen
> sehen", „im dialog das im modell platzieren brauchen wir auch nicht",
> „außerdem haben wir werte im dialog und in der rechten merkmalleiste
> doppelt, sehr verwirrend für den Kunden", „auch 2 mal übernehmen einmal
> unten und einmal rechts, glaube wir sollten das über den viewport wieder
> über einen button aktivieren, und die untere leiste uns sparen und nur die
> rechte verwenden mit dem was schon drin ist".
> **Entscheidung Robert, 11.09.2026:** Beide unteren Leisten fallen; der Knopf
> steht rechts im Merkmalfenster; der Dialog fällt.

## §1 Der Ist-Zustand, gemessen

Alles hier ist am laufenden Stand nachgeschlagen oder an einer Sonde gemessen,
nicht aus der Doku übernommen.

### §1.1 Vier Stellen zeigen dieselbe Bohrung

Wer eine Bohrung anklickt, bekommt heute:

| Stelle | Was dort steht | Wo gebaut |
|---|---|---|
| Merkmalfenster rechts | Felder je Handlung, **ein** Übernehmen unten | `panels.py:4644`, Knopf `panels.py:4753` |
| Operationsdialog | Durchmesser, X, Y, Z, „Im Modell platzieren" | `op_dialog.py`, Knopf `op_dialog.py:1555` |
| Platzierungsleiste unten | Hinweis, „Werte bearbeiten", „Position übernehmen" | `placement_flow.py:341` |
| Maßlinien in der Szene | Abstände zu Kanten und Mitten, je ein Zahlenfeld | `placement_flow.py` (`_canvas`) |

Die vierte will Robert — sie ist der Grund, aus dem die Platzierung überhaupt
am Merkmal startet (§18.5). Die ersten drei sagen dasselbe dreimal.

Beim Zug am Langlochgriff kommt eine **fünfte** dazu: `SlotBar` unten mittig
mit Länge, Richtung, Abbrechen, Übernehmen (`viewport.py:4184`) — dieselben
zwei Werte, die rechts unter *Zum Langloch ziehen* schon stehen.

### §1.2 Der Dialog trägt die Platzierung

`PlacementFlow.__init__` nimmt einen `OperationDialog` und lebt von ihm
(`placement_flow.py:253`): `super().__init__(dialog)` macht ihn zum Elternteil,
`dialog.values()` liefert die Werte, `dialog.surface_button.isEnabled()` ist an
drei Stellen die **Bedingung**, ob platziert werden darf, und drei Signale
hängen daran (`surfaceRequested`, `valuesChanged`, `finished`).

**Ohne Dialog gibt es heute keine Platzierung.** Sieben Stellen bauen den Fluss
so auf — eine in `main_window.py:12311`, sechs in den Tests.

### §1.3 Der Selbststart und sein Rest

`MainWindow._measure_in_the_view` öffnet den Dialog von selbst, sobald das
Merkmalfenster eine Bohrung oder ein Langloch zeigt
(`MEASURED_IN_THE_VIEW = {"hole": "resize_hole", "slot": "slot_hole"}`).

Gemessen am 11.09.2026 (Sonde am Hauptfenster mit `plate_holes.stl`):

| Schritt | `flow.active` | Maßlinien sichtbar | Dialog sichtbar |
|---|---|---|---|
| Bohrung gewählt | True | ja | **ja** |
| nach *Merkmal verschieben* | **False** | **nein** | ja |
| danach am Langloch gezogen | False | nein | ja |

Zwei Befunde stecken darin:

* **Der Dialog steht neben der Platzierung, nicht hinter ihr.** Das war einmal
  Absicht („Er trägt die Maße, die man beim Platzieren braucht") — heute trägt
  das Merkmalfenster dieselben Maße, und der Dialog ist die Doppelung.
* **Jede Operation beendet die Platzierung.** `_scene_changed` und
  `_document_changed` rufen `back()`; die Maßlinien verschwinden, der Dialog
  bleibt mit **veralteten** Werten stehen (gesehen: X 25,00 im Dialog gegen
  29,90 rechts). Der Selbststart springt nicht neu an, weil
  `_a_dialog_is_open()` genau diesen toten Dialog sieht.

Das ist Roberts erster Befund vollständig erklärt: Beim Langlochziehen fehlen
die Maße, weil sie schon seit dem Verschieben davor fehlen.

### §1.4 Der Weg ins Bild existiert bereits

`FeaturePanel.inViewRequested` (`panels.py:4681`) → `MainWindow._place_from_feature_panel`
(`main_window.py:11378`) ist genau der Weg, den Robert zurückhaben will. Er
lebt, nur der Knopf dazu ist am 10.09.2026 gefallen. Ausgelöst wird er heute
vom Übernehmen-Knopf für die zwei Operationen in
`LEADS_INTO_THE_VIEW = {"slot_hole", "resize_hole"}` (`panels.py:4562`) — der
Knopf *führt* also schon ins Bild, statt auszuführen. Er heißt nur nicht so.

## §2 Was daraus folgt

### §2.1 Der Schnitt: Merkmal gegen Neuanlage

Ein gewähltes Merkmal hat ein Merkmalfenster, eine neue Bohrung hat keines.
**Der Umbau gilt dem Merkmal; die Neuanlage bleibt, wie sie ist.** Sonst hätte
das Setzen einer neuen Bohrung nach dem Umbau keine Bedienstelle mehr.

Das ist die einzige Stelle, an der ich Roberts Antwort ergänzt habe — er hat
vom Merkmal gesprochen. Widerspricht er, ist es ein eigenes Paket.

### §2.2 Entscheidung A — der Dialog fällt am Merkmal weg

`_measure_in_the_view` öffnet keinen Operationsdialog mehr. Die Platzierung
braucht dafür einen Träger ohne Dialog: `PlacementFlow` bekommt die drei
Auskünfte, die es heute aus dem Dialog zieht (Werte, „darf platziert werden",
„ist zu"), über eine schmale Schnittstelle statt über das Widget.

**API-Spiegelung als Risikosenker:** Der Träger behält die Membernamen, die der
Fluss heute anspricht — der Rebind wird mechanisch.

### §2.3 Entscheidung B — beide unteren Leisten fallen

`PlacementFlow._bar` und `SlotBar` verschwinden **am Merkmal**. Was sie trugen,
steht rechts:

| war unten | steht rechts |
|---|---|
| „Position übernehmen" | der eine Übernehmen-Knopf (`panels.py:4753`) |
| „Werte bearbeiten" | entfällt — die Werte stehen ohnehin rechts |
| Langlochlänge, Richtung | die Felder unter *Zum Langloch ziehen* |
| der Hinweissatz | die Statuszeile des Fensters |
| „Abbrechen" | Escape, wie bisher |

### §2.4 Entscheidung C — ein Knopf rechts aktiviert die Maße

Kein Selbststart mehr. Im Merkmalfenster steht neben den Feldern ein Knopf, der
die Maßlinien in die Szene bringt. Der Weg dafür ist `inViewRequested` (§1.4) —
er wird vom Übernehmen-Knopf abgekoppelt und bekommt seinen eigenen.

Damit verschwindet auch `MEASURED_IN_THE_VIEW`, `_measured_for`,
`_a_dialog_is_open` als Selbststart-Wächter und `_measured_in_the_view_discards_nothing`.

### §2.5 Entscheidung D — der Knopf im Dialog fällt

`op_dialog.surface_button` verschwindet als **Knopf**. Seine zweite Rolle —
`isEnabled()` als Bedingung an drei Stellen — wird eine eigene Frage
(`PlacementFlow.can_place()`), sonst reißt der Einstieg bei der Neuanlage.

### §2.6 Was nicht angefasst wird

* Der Zug am Langlochgriff selbst und `slot_hole` — nur seine Leiste fällt.
* Die Neuanlage einer Bohrung über Menü oder Katalog (§2.1).
* Die Vorschau-Griffe und `previewDragged`.
* Die Maßlinien und ihre Zahlenfelder — sie sind der Teil, der bleiben soll.

**Nachtrag vom Abend des 11.09.2026 — die Griffe gehören zum Knopf.** Am
gefahrenen Stand war das Gizmo an einer gewählten Bohrung schon da, bevor der
Knopf gedrückt war, und am Langloch fehlte es auch danach (Robert: „noch bevor
ich auf im Bild einstellen anklicke ist das Gizmo schon da" / „beim langloch
bearbeiten fehlt das gizmo noch wenn wir auf im Bild einstellen klicken").
Entschieden: An Bohrung und Langloch bringt *Im Bild einstellen* Maße **und**
Griffe zusammen und nimmt sie zusammen; die Auswahl allein zeigt, was gewählt
ist. Umgesetzt in `viewport.set_gizmo` über den Zeiger der Platzierung
(`placed_feature_kinds()` liest dieselbe Quelle wie der Knopf). Das Langloch
trägt dabei beide Griffe, seit es versetzbar ist (RM-153).

## §3 Die Pakete

Jedes endet mit grünem Tor und einem Commit.

| Nr. | Inhalt | Umfang | Stand |
|---|---|---|---|
| P1 | Die Maße überleben die eigene Operation (§1.3, zweiter Befund) | S | **fertig** (`5a18c950`) |
| P2a | `can_place()` trägt die Bedingung, nicht mehr der Knopf | S | **fertig** (`c2522e99`) |
| P5 | `surface_button` entfernen — **vorgezogen**, siehe Notiz unten | S | **fertig** (`afc15641`) |
| P2b | `PlacementFlow` ohne Dialog tragbar machen (additiv) | L | **fertig** (`341fdb35`) |
| P3 | Knopf rechts im Merkmalfenster, Selbststart aus — **das Umschalt-Paket** | L | **fertig** |
| P4 | Untere Leisten abbauen: `_bar` am Merkmal, `SlotBar` | L | **fertig** |
| P6 | Toter Alt-Pfad raus, Doku und Regeln nachziehen | S | **fertig** |

**Leitplanke:** P2b baut additiv, der Dialogweg bleibt bis P3 funktionsfähig.
P3 ist der Schnitt. Außer dem gefallenen Knopf ist vor P3 nichts anders.

**Rückfalloption für P3:** Der Selbststart bleibt als Schalter, bis Robert den
neuen Weg einmal gefahren ist.

## §5 Übergabe zwischen den Schritten

**P5 wurde vor P2b gezogen**, und zwar aus der Sache heraus: Der Träger
braucht ein Protokoll, und solange der Knopf darin vorkäme, trüge das
Protokoll ein Widget, das gleich fällt. Ohne ihn ist es sauber.

**Was der Knopf hinterlässt, ist eine Lücke und sie ist benannt:** Wer die
Platzierung mit Escape verlässt, kommt heute nur über eine neue Auswahl
zurück. `surfaceRequested` ist der Weg von außen hinein und lebt; es sendet
nur niemand mehr. P3 hängt den Knopf im Merkmalfenster daran.

**Der Vertrag, den P2b abbilden muss** — erhoben am 11.09.2026 über alle
`self.dialog.`-Zugriffe in `placement_flow.py`:

| Was | Wofür |
|---|---|
| `values()` | die eingetippten Werte lesen (sieben Stellen) |
| `take_placement(values)` | Ort und Maße zurückschreiben (drei Stellen) |
| `accept()` | die Operation ausführen |
| `show()`, `raise_()`, `activateWindow()`, `isVisible()` | der Rückweg aus der Platzierung (`back`) |
| `surfaceRequested`, `valuesChanged`, `finished` | die drei Signale |
| Qt-Elternteil | `super().__init__(dialog)` |

**P3 hat einen Fehler im Kern freigelegt, den der Dialog verdeckt hatte.**
`surface_values` gab die Merkmalskennung nur für `move_feature` und
`duplicate_feature` zurück und leerte sie sonst — richtig beim Setzen einer
neuen Bohrung, falsch an einer bestehenden. Aufgefallen ist es nie, weil
`OperationDialog.take_placement` nur Editoren setzt und es für `at_feature`
keinen gibt: Der Dialog schützte die Kennung **zufällig**. Ein Träger ohne
Fenster nimmt jeden Wert an und verlor damit genau die Kennung, aus der er
sein Merkmal sucht. `AT_AN_EXISTING_FEATURE` (`scene/placement.py`) nennt die
vier Operationen jetzt beim Namen; nebenbei geht damit auch *Merkmal
verschieben* über diesen Weg, was vorher still scheiterte.

Das ist die allgemeine Form: **Ein zufälliger Schutz sieht aus wie eine
Zusage, bis jemand den Träger austauscht.**

**Und eine Warnung an den nächsten Schritt:** Am 11.09.2026 arbeitete eine
zweite Sitzung im selben Baum an derselben Ecke (`panels.py`,
`main_window.py`, `perceive/slots.py`, die Kataloge). Die vier Commits oben
sind deshalb **hunkweise** gestaget worden, nicht dateiweise. Wer P3 angeht,
prüft zuerst, wem was gehört.

## §3.1 Was P4 noch gekostet hat

**Eine Testattrappe, die mehr konnte als die Sache.** `_Viewport` in
`test_surface_placement_ui.py` baute sich eine echte `SlotBar` ein — nur damit
`PlacementFlow` sie fragen konnte. Nach dem Ausbau der Leiste blieben dort 65
Tests grün, während `placement_flow.py` an **fünf** Stellen auf
`viewport.slot_bar` zugriff; der breite Lauf über `test_ui.py` brachte 27
Fehler mit derselben Zeile. Die Attrappe beantwortet die Frage jetzt mit einem
Wahrheitswert, und der Fluss fragt den Zustand (`slot_drag_waits`) statt ein
Widget.

Das ist die Regel aus `tests.md` in ihrer teuersten Gestalt: **Ein Test, der
nur in einer Lage grün ist, die es im Betrieb nicht gibt, ist keine
Zusicherung, sondern eine Tarnung** — und eine Attrappe mit einem Widget zu
viel baut genau so eine Lage.

**Und ein Hänger ohne Zeichen.** Der Klick auf *Übernehmen* stand offscreen
still; `faulthandler.dump_traceback_later` nannte die Stelle:
`session.apply` → `_on_error` → ein **modaler** Fehlerdialog, der auf einen
Klick wartet, den es offscreen nie gibt. Die Meldung dahinter war „Diesen
Parameter gibt es bei dieser Operation nicht" — derselbe zufällige Schutz des
Dialogs wie bei `at_feature`, diesmal für `nx`/`ny`/`nz`.

## §4 Verifikation

Je Paket: `tools/affected_tests.py --run`, vor dem Commit `/pruefen`.

Die Wege, die am Ende von Hand zu fahren sind — offscreen ist keiner davon
beweisbar (`.claude/rules/tests.md`, „Was nur das Bild zeigt"):

1. Bohrung wählen → Knopf → Maße stehen in der Szene → Wert ändern → rechts
   übernehmen → Maße stehen **danach immer noch**.
2. Bohrung wählen → am Gizmo verschieben → Maße stehen danach.
3. Bohrung wählen → am Langlochknopf ziehen → Länge und Richtung rechts →
   rechts übernehmen; keine Leiste unten.
4. Neue Bohrung über das Menü → unverändert wie heute.
