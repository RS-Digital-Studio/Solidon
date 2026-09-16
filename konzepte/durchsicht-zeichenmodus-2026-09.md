# Durchsicht — Zeichenmodus: einfache und anspruchsvolle Körper zeichnen und ändern

**Stand 16.09.2026, untersucht am Stand `0e9f5b61`** (nach dem Wegfall des
Formenmenüs und den beiden Lochbild-Werkzeugen). Anlass: Robert, 16.09.2026 —
„zeichenmodus mal gründlich durchgehen, damit alles sinnvoll ist und man
anspruchsvolle und einfache körper erzeugen/bearbeiten usw kann".

**Was diese Durchsicht ist und was nicht.** Die Abläufe sind aus den wirklichen
Aufrufern abgeleitet (`app/ui/main_window.py`, `app/ui/sketch_editor.py`,
`app/ui/op_dialog.py`, `app/core/sketch/ops.py`) und am Bildschirmfoto des
Handbuchs (`app/images/manual/de/sketch-mode.png`, Stand 16.09.) geprüft. **Am
laufenden Fenster gefahren wurde nicht** — offscreen fehlen die Schriften, und
eine Fernsteuerung des echten Fensters gibt es nicht. Wo das einen Unterschied
macht, steht es dabei. Eine Expertenprüfung ist kein Test mit echten Nutzern.

## §1 Startzustände

| Kennung | Wer, was, womit |
|---|---|
| S1 | Leeres Projekt, Anfänger ohne CAD, Maus und Tastatur: eine Grundplatte mit Aussparung |
| S2 | Vorhandener Körper (Platte), erfahrener Drucker: ein Lochbild als Tasche auf der Oberseite |
| S3 | Anspruchsvoll: Drehteil (Drehen), Rohrbogen (Führen entlang Bahn), Trichter (Überblenden) |
| S4 | Bestehender Skizzenschritt im Verlauf: eine Linie zwei Millimeter versetzen |

## §2 Ist-Abläufe

Jede Zeile ein Schritt; „Zeile" ist die Statuszeile der Skizzenkarte unten,
„Banner" die Karte über der Zeichnung im Bild.

### A — Einstieg (S1)

| Ausgangszustand | Was der Nutzer sieht | Handlung | Rückmeldung und neuer Zustand | Rückweg |
|---|---|---|---|---|
| Hauptfenster, leere Szene | Werkzeugleiste oben mit *Zeichnen* (Weg 2, §2.2) | Klick *Zeichnen* | Ansicht schwenkt, im Bild drei Ebenen zur Wahl, unten die Skizzenkarte, rechts der Reiter *Bedingungen*; Zeile: „Leere Skizze — mit dem Rechteck beginnen …" | Esc verlässt den Modus |
| Ebenenwahl steht | Drei Ebenen im Bild, Auswahlfeld „Zeichenebene:" in der Karte, Ziffern 1/2/3 | Klick auf eine Ebene oder Ziffer | Ebene fest, Schichthinweis-Satz unter der Wahl (`layer_note`, im Bildmodus verborgen) | Auswahlfeld wechselt, solange nichts gezeichnet ist |
| Körper gewählt, Fläche markiert | Rechtsklick auf Fläche: *Auf dieser Fläche zeichnen* | Klick | Modus öffnet auf der Fläche, keine Ebenenwahl nötig | Esc |

### B — Einfacher Körper: Rechteck hochziehen (S1)

| Schritt | Handlung | Rückmeldung |
|---|---|---|
| 1 | *Zeichnen*, Ebene wählen | siehe A |
| 2 | Rechteck (`R`), erster Klick, zweiter Klick — oder Breite und Höhe tippen | Vorschau am Zeiger; getippt heißt bemaßt |
| 3 | *Fertig* | Dialog „Was soll daraus werden?" — fünf Arten, *Grundform hochziehen* vorn; *Zurück zum Zeichnen* verwirft nichts |
| 4 | *Weiter* | Operationsdialog *Grundform hochziehen*, Skizze eingetragen, Höhe im Feld |
| 5 | Höhe, *OK* | Körper steht, ein Schritt im Verlauf |

Fünf Schritte, zwei Dialoge in Folge. **Die kurze Hand:** Vorder- oder
Seitenansicht wählen, den Pfeil am Umriss ziehen — Dialog öffnet mit der
gezogenen Höhe (`_on_sketch_pulled`), drei Schritte. Das Banner sagt es
(„Pfeil: Körper hochziehen · Kreuz: Tasche schneiden"), die Zeile sagte es bis
heute noch einmal.

### C — Lochbild als Tasche (S2)

| Schritt | Handlung | Rückmeldung |
|---|---|---|
| 1 | Rechtsklick Oberseite → *Auf dieser Fläche zeichnen* | Modus auf der Fläche |
| 2 | *Lochraster*, Spalten/Zeilen/Ø in der Leiste, erstes Loch, Gegenecke | Raster als Vorschau, zu eng: „Die Löcher überschneiden sich — weiter ziehen oder …" |
| 3 | *Fertig* | Dialog „Was soll daraus werden?", *Tasche schneiden* vorn, weil ein Körper darunter liegt |
| 4 | *Weiter*, Tiefe, *OK* | zwölf Löcher in der Platte |

Kreuz-Geste als kurze Hand wie bei B (Tasche nach innen).

### D — Anspruchsvoll (S3)

| Körper | Weg | Beleg |
|---|---|---|
| Drehteil | Profil neben der Achse zeichnen → *Fertig* → *Drehen* → Dialog | `SketchRevolveParams`: Grundform, Länge, Breite, Skizze |
| Rohrbogen | Kreis → *Fertig* → *Führen* → Dialog: *Bahn* „Bogen" mit Radius und Winkel — **oder** „gezeichnet" mit *Gezeichnete Bahn: Zeichnen …* | `SketchSweepParams.along` in `("arc", "drawn")`, `path_sketch` kind `sketch` |
| Trichter | Umriss → *Fertig* → *Überblenden* → Dialog: *Oberer Umriss* „verjüngt" mit *Verjüngung* — oder „gezeichnet" mit *Obere Zeichnung: Zeichnen …* | `SketchLoftParams.top` in `("scaled", "drawn")`, `top_sketch` |

Die zweite Skizze (Bahn, oberer Umriss) entsteht **im Dialog** über
*Zeichnen …* — das öffnet den Editor als eigenes Fenster
(`SketchField._edit` → `SketchEditorDialog`), nicht im Bild. Wie Profil und
Bahn zueinander liegen (Bahnanfang am Profil?), ist aus dem Code nicht zu
sehen und am Fenster nicht geprüft (§6).

### E — Bestehende Skizze ändern (S4)

| Schritt | Handlung | Rückmeldung |
|---|---|---|
| 1 | Doppelklick auf den Schritt im Verlauf | Operationsdialog mit den Werten des Schritts |
| 2a | *Skizze: Zeichnen …* | Editor als eigenes Fenster, Dialog bleibt offen |
| 2b | *Im Raum zeichnen …* | Dialog schließt, Modus öffnet im Bild mit der Zeichnung; *Fertig* öffnet den Dialog wieder, ohne zweiten Schritt (`_draw_sketch_in_space`) |
| 3 | Linie greifen, ziehen | Löser zieht nach, was daran hängt; Maßkarten per Doppelklick änderbar |
| 4 | *Fertig* → *OK* | derselbe Schritt, neu gerechnet (§15, `change_params`) |

## §3 Befunde, priorisiert

| Nr. | Befund | Beleg | Auswirkung | Vorschlag | Stand |
|---|---|---|---|---|---|
| Z1 | **Der Gestensatz stand zweimal**: „Pfeil: Körper hochziehen · Kreuz: Tasche schneiden" im Banner **und** in der Zeile der Skizzenkarte | `_update_sketch_hint`: `line = f"{line} {action}"` neben `show_sketch_action(action)`; Bildschirmfoto | Die Karte wuchs auf vier Textzeilen, die Zeichnung stand dahinter | Der Satz nur im Bild, wo die Geste stattfindet | **umgesetzt 16.09.** |
| Z2 | **Fünfzehn Werkzeugsymbole in historischer Reihenfolge**: Rechteck hinter Langloch, Trimmen zwischen Kurve und Vieleck, keine Gruppen | `SketchPanel.__init__`, Werkzeugschleife | Wer ein Werkzeug sucht, liest fünfzehn Bilder | Vier Gruppen mit Trennstrichen: Auswählen — Zeichnen — Lochbilder — Ändern | **umgesetzt 16.09.** |
| Z3 | **„Bedingungen erscheinen, sobald …" stand dauerhaft**, sobald etwas gezeichnet und nichts gewählt war — also die meiste Zeit | `_refresh_buttons`: `setVisible(not fitting and drawn)` | Ein Satz über Bekanntes, jede Abwahl wieder | Bis die Knöpfe einmal da waren (`_constraints_seen`) | **umgesetzt 16.09.** |
| Z4 | **Die Ebene steht zweimal**: Auswahlfeld „Zeichenebene: Draufsicht (XY)" und darunter „Zeichenebene: Draufsicht (XY) · Geschlossenen Umriss zeichnen …" | `plane_role`/`plane_choice` gegen `_update_sketch_hint`; Entscheidung 24.08.2026 (Robert zeichnete auf z = 0), Test `test_the_sketch_hint_names_the_plane_being_drawn_on` | Eine Zeile Karte für eine Auskunft, die zwei Zentimeter höher schon steht | Der Satz nennt die Ebene nur noch, wenn der Blick abweicht („Blick aus der Vorderansicht · Zeichenebene: Draufsicht"); sonst nur den Zustand | **Entscheidung** (kippt 24.08.) |
| Z5 | **Zwei Stellen für einen Rasterzustand**: Haken „Auto" **und** Sonderwert „Automatisch" im Rasterfeld | `snap_auto`, `snap_step.setSpecialValueText`, `_automatic_grid_changed`, `_step_typed` | Zwei Bedienelemente, ein Zustand; wer eines umschaltet, sieht das andere springen | Der Haken fällt, das Feld mit „Automatisch" bleibt — ganz herunterdrehen heißt Auto | **Entscheidung** |
| Z6 | **Zwei Editoren für dieselbe Skizze**: *Zeichnen …* öffnet ein eigenes Fenster, *Im Raum zeichnen …* den Modus im Bild; Bahn und oberer Umriss (Führen, Überblenden) kennen nur das Fenster | `SketchField.edit_button` → `SketchEditorDialog`; `offer_space` nur für die Hauptskizze eines Schritts (`edit_operation`) | Zwei Umgebungen für eine Sache; im Fenster fehlt der Körper als Bezug | Das Bild als Regel für jede Skizze eines Schritts, auch Bahn und oberen Umriss; das Fenster nur als Rückfall ohne Bild | **Entscheidung**, Umfang M |
| Z7 | **Zwei Dialoge nach *Fertig*** im Hauptweg: „Was soll daraus werden?" und danach der Operationsdialog | `finish_sketch` → `_offer_sketch_use` → `SketchUseDialog` → `edit_operation` | Fünf Schritte für die Grundplatte; die kurze Hand (Pfeil) kennt nur, wer das Banner liest | *Fertig* als Knopf mit Pfeil: Klick nimmt die Vorgabe (hochziehen, auf einem Körper Tasche), der Pfeil zeigt die anderen vier — der Zwischendialog fällt | **Entscheidung**, Umfang M |
| Z8 | **Anspruchsvolle Körper hängen an einer zweiten Skizze im Dialogfenster** (Bahn, oberer Umriss); die Lage von Profil zu Bahn ist im Code nicht erklärt | `SketchSweepParams.path_sketch`, `SketchLoftParams.top_sketch` | Ohne Probe am Fenster nicht bewertbar | Rohrbogen mit gezeichneter Bahn und Trichter mit gezeichnetem Umriss am Fenster fahren, Ergebnis mit dem Bauplan-Versprechen „entlang eines Bogens führen" vergleichen | **offen**, am Fenster |
| Z9 | **Kürzel ungleich verteilt**: Werkzeuge auf Buchstaben, von sechzehn Bedingungen nur Abstand (`D`), Versetzen (`O`), Hilfslinie (`X`); Lochkreis und Lochraster ohne | `TOOL_KEYS`, `ACTION_KEYS` | Wer aus einem CAD kommt, greift ins Leere | Bewusst so gelassen: Fusion belegt dort nichts, freie Buchstaben ohne Eselsbrücke vergisst man. Kürzel für die Lochbilder nur, wenn Robert sie will | **Entscheidung**, klein |
| Z10 | **Die Handbuchbilder zeigen die alte Leiste** mit dem Menü | `app/images/manual/*/sketch-mode.png` | Handbuch und Fenster gehen auseinander | Beim nächsten Release erzeugen (`/erzeugen`), nicht vorher — Regel in `app/images/CLAUDE.md` | offen bis Release |

**Was trägt und bleibt:** Esc in zwei Stufen (Werkzeug ablegen, Modus
verlassen); *Verwerfen* ohne Nachfrage, aber gemerkt (`_remember_discarded`);
getippt heißt bemaßt, gezeichnet heißt frei; die Einladung der leeren Skizze
ist ein Verweis, der das Rechteck wählt; die Lochbilder sagen bei zu engem Zug,
woran es liegt.

## §4 Heute umgesetzt

Z1, Z2, Z3 — in `app/ui/sketch_editor.py` und `app/ui/main_window.py`, Regel
in `.claude/rules/zeichenflaeche.md`, Tests
`test_the_tools_stand_in_four_groups_with_dividers` und
`test_the_constraint_hint_retires_once_the_buttons_were_seen`.

## §5 Entscheidungen — delegiert und gefallen (16.09.2026)

Robert: „die entscheidungen mach das beste für kunden daraus, denk auch dran
weniger ist manchmal mehr". So sind sie gefallen und am selben Tag gebaut:

| Nr. | Entscheidung | Umsetzung |
|---|---|---|
| Z7 | *Fertig* klappt die sechs Arten direkt auf, Hochziehen und Tasche vorn, gesperrte Einträge sagen warum; der Dialog „Was soll daraus werden?" ist gefallen. Ohne Wahl gilt der wahrscheinlichere Fall. | `MainWindow._fill_finish_menu`, `_update_sketch_actions`, `_finish_sketch_as`; `SketchUseDialog` entfernt; `test_finish_lists_the_kinds_and_says_why_cutting_is_locked` |
| Z4 | Die Zeile der Karte sagt nur, was sonst nirgends steht: abweichender Blick, Fläche eines Körpers. Der Grund, aus dem der Griff nicht geht, steht in der Karte im Bild. Die Ebene bleibt sichtbar (Entscheidung 24.08.), nur einmal. | `_update_sketch_hint`; Tests in `test_ui.py` und `test_sketch_editor.py` umgestellt |
| Z5 | Der Haken „Auto" fällt; die Null im Feld heißt Automatisch, wie im Handbuch. | `SketchPanel`, `_step_typed`, `follow_grid`; `test_automatic_grid_is_visible_and_typing_pins_it` |
| Z6 | Ein Zeichnen-Knopf je Skizzenfeld: im Bild, wo ein Schritt da ist, sonst im Fenster. Bahn und oberer Umriss gehen denselben Weg. | `SketchField.offer_space` |
| Z9 | Keine Kürzel für die Lochbilder. | — |

Offen bleibt Z8 (am Fenster fahren) im Register unter
[RM-183](../ROADMAP.md#rm-183).

## §6 Nicht geprüft

Nichts hier wurde am laufenden Fenster gefahren. Offen sind insbesondere: die
Tastaturfolge durch die Karte (Tabulator von den Werkzeugen über Ebene und
Raster bis *Fertig*), ein Bildschirmleser an den Symbolknöpfen, die Lage von
Profil und gezeichneter Bahn beim Führen, der Trichter mit gezeichnetem
oberen Umriss, und ob die drei Trennstriche im dunklen Thema sichtbar sind.
