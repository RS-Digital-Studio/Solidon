---
description: "Die Vorderseite eines Dialogs und bedingte Felder — zwei bis drei Werte und ein Satz, vorbelegte Werte, die Stelle als Lesezeile, benannte Null, fx, Vorgaben am Körper, Maße als Parameter, Felder, die mit ihrer Bedingung kommen und gehen"
paths:
  - "app/ui/op_dialog.py"
  - "app/ui/panels.py"
  - "app/ui/dialogs.py"
  - "app/core/registry/params.py"
---

# Regeln für die Vorderseite eines Dialogs

Die Grenze selbst (Felder vorn, Wörter über dem ersten Feld) steht in
`grenzen.md`, „Die Oberfläche wächst nicht mit“. Warum:
`konzepte/begruendungen/regel-grenzen.md`, Abschnitte „Die Vorderseite eines
Dialogs“ und „Bedingte Felder“.

## Was vorn steht

- **Vorn stehen zwei bis drei Werte und ein Satz** (RM-513): Was man ändert,
  steht vorn; Toleranzen, Auflösungen, Rückfallverhalten, Ausrichtungsfeinheiten
  und der Ersatz für eine Zeichnung (Grundform samt Maßen) hinten. Über dem
  ersten Feld stehen die Platzierungsanweisung als erste Zeile in normaler
  Schrift, der erste Satz der `doc` (`op_dialog.lead_sentence`, dieselbe
  Kürzung wie Palette und Menü, `surfaces.first_sentence`; die ganze `doc`
  im Tooltip) und die Grenze zugeklappt unter „Wann nicht?“ (`remember=`).
- **Ein vorbelegter Wert kommt nach vorn, außer er ist eine Richtung oder die
  Stelle — und nur, solange vorn Platz ist:** `_promoted_fields` holt
  angeklickte Fläche, gemessenes Maß und übergebene Zeichnung (§18.5) vor die
  Klappe, bis `MAX_FRONT_FIELDS` erreicht ist; `direction_fields` (Normale aus
  `normal_fields_of`, `axis`) bleiben hinten und gelten trotzdem.
- **Die Stelle ist eine Lesezeile** (Entscheidung Robert, RM-513): Wer am
  Körper ansetzt und seine Koordinaten hinten führt (`place_fields`: Bohrung,
  Beschriftung, Bausteine), zeigt vorn „Stelle: Oberseite · x / y / z mm“ mit
  *Stelle im Bild wählen*; Koordinaten und das Merkmal, an dem sie hängen,
  bleiben hinten bearbeitbar. Wo die Koordinaten selbst die Eingabe sind
  (*Merkmal verschieben*), stehen sie als Felder vorn.
- **Eine Null mit Bedeutung trägt ihren Namen** (`param(zero_text=…)`, nur bei
  Mindestwert 0, angezeigt über `setSpecialValueText`): „automatisch“, „ohne“,
  „aus dem Material“ — die Wörter stehen als `ZERO_*` in `registry/params.py`,
  `test_registry_consistency` sucht jedes `doc`, das die Null erklärt.
- **„fx“ steht nur, wenn das Projekt Parameter hat oder das Feld einen Ausdruck
  trägt**; „=“ und „@“ im Zahlenfeld führen weiter in den Ausdruck.
- **Die Vorgabe trifft den Körper, nicht den Ursprung:** *Teilen* in seiner
  Mitte (`_plane_through`), *Dreiecke verringern* bei der Hälfte seiner
  Dreiecke, *Dreiecke angleichen* bei einem Fünfzigstel seiner längsten Kante
  (`_measured_from_body`, `EDGE_SHARE`) — gefragt nach den Feldern
  (`axis`/`position`, `triangles`, `edge`), nicht nach der Operation; die Zahl
  bleibt änderbar. *Druckplatten* bleibt beim Höchstwert, das Feld ist eine
  Obergrenze.
- **Ein Erzeuger nimmt seine Lage nur von einer gezeigten Fläche** (RM-390):
  Ein gewählter Körper, eine Bohrung oder Kante setzen ihn nicht, er entsteht
  auf dem Bett (`values_for_object` gibt `consumes == 0` nichts). Auf einer
  gewählten Fläche steht er auf ihr und, wo nötig, in ihrer Ebene über das Bett
  gehoben (`placement.seats_on`, `seat_on_face`); vorn steht „Wird auf ‹Fläche›
  von ‹Körper› gesetzt“ mit *Auf das Bett* (`OperationDialog.show_seat`).
  Nach dem Übernehmen ist sein neuer Körper gewählt (`_queue_created_choice`).
- **Ein Grundkörper bietet an, seine Maße zu benennen** (§13, Entscheidung
  Robert): *Maße als Parameter anlegen* steht vorn in jedem Dialog der
  Kategorie `primitive` und im Erzeuger jedes Bausteins, der sich als Vorlage
  erklärt (`PartSpec.template`, die Halter; `offers_naming`). Gesetzt, wird
  jedes wirksame Millimetermaß der Vorderseite ein Projektparameter nach
  seiner Beschriftung (*Breite* → `breite`, vergeben → `breite_2`) mit
  übersetzbarem Titel und den Grenzen des Feldes, der Schritt verweist mit
  `=@breite` darauf, beides in **einer** Transaktion (`changes` an
  `Session.apply`); ein Feld mit Ausdruck bleibt, ein Feld, dessen
  `depends_on` gerade nicht gilt, wird keiner. Der Haken steht beim ersten Start an und übernimmt danach die letzte Wahl
  beim Übernehmen (`UiSettings.name_dimensions`).
- **Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat:**
  `ArmatureField` baut je Knochen drei Winkel (`ValueField`, §13), sobald der
  Dialog ein Skelett hat, sonst bleibt das Textfeld. Im Schema steht er hinten
  (`tests/test_gesture_ops.py`), im Dialog vorn, wenn er der Grund ist, aus dem
  der Dialog aufgeht.
- **Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**
  (`OperationDialog.switch_variant`): Was die Variante nicht kennt,
  verschwindet, die Beschreibung wechselt.

## Bedingte Felder

Die Bedingung steht am Parameter (`ParamSpec.depends_on`), denn Dialog,
Handbuch (Parametertabelle), Agent (Werkzeugbeschreibung) und Kommandozeile
(`json_schema`) lesen sie. Der Dialog blendet ein Feld ohne Wirkung aus
(`oberflaeche.md`, „Gestufte Tiefe“): `OperationDialog._couple_dependent_fields`
nimmt es samt Beschriftung heraus und bringt es mit der Bedingung wieder;
dahinter bleibt es gesperrt und begründet, damit kein verborgenes Feld den
Fokus bekommt, und `adjustSize` läuft nur, wenn sich eine Zeile bewegt hat
(`test_a_rectangle_shows_only_the_rows_a_rectangle_has`). Im Merkmalfenster
folgt `FeaturePanel._follow_conditions` demselben `ActionField.depends_on`: Das
Feld verschwindet samt Beschriftung, kommt mit seinem Wert zurück und wird
nicht gesperrt — die Sperre gehört dem Kettenhalt (`_settle_lock`). Ein
Zahlenfeld mit benannter Null geht beim Verschwinden auf seine Null und kommt
mit seinem Wert zurück: Was nicht dasteht, zählt nicht (*Aushöhlen* mit „Oben
öffnen“ verliert seine Entlüftung und bleibt am exakten Körper exakt).

- **Agent und Mensch bekommen verschiedene Anreden, nicht verschiedene
  Inhalte:** „Gilt bei Art = circular“ im Handbuch, `kind` für den Agenten
  (`condition_text(..., keys=True)`), „Wirkt nur, wenn …“ im Dialog mit Werten
  durch `choice_label`.
- **`tests/test_operation_ui.py` liest den Quelltext jeder Operation** und
  meldet jeden Parameter, der nur in **genau einem** Zweig über einen Umschalter
  derselben Operation gelesen wird — nicht über einen Aufruf, der den ganzen
  Parametersatz weitergibt.
- **Ein Haken als Umschalter** braucht einen typtreuen Vergleich (über `str()`
  hieße der Wert „True“, und `1 == True`) und einen eigenen Satz.
- **Die Art des Umschalters wird mitgeprüft:** Ein Wahrheitswert an einem
  Aufklappmenü oder ein Auswahlwert an einem Haken trifft nie zu.

Maßgruppen im Bild übernehmen dieselben `depends_on`-Bedingungen wie die rechte
Spalte, einschließlich Auswahlwerten und Ketten. Der Adapter `_saved_fields`
reicht sie aus dem Parameterschema weiter. Titel, Eingabe und Ablehnung
verschwinden gemeinsam; verborgene Werte bleiben erhalten und sperren die
Übernahme nicht. Stille Wertaktualisierung und wiederverwendete Gruppen
berechnen die Sichtbarkeit erneut (`FeaturePanel._follow_measure_conditions`).

## Die linken Karten zeigen nur, was gilt (RM-519)

Warum: `konzepte/begruendungen/regel-oberflaeche.md`, „Die linken Karten“.

- **Parameterkarte:** unter einer Zeile nur „Nicht verwendet“; wie viele feste
  Zahlen passen, sagt der Bindeknopf (`binding_button_text`), wo, die Kurzhilfe.
- **Objektbaum:** Die Filamentspalte trägt die Spule, das Wort steht in
  Kurzhilfe und Lesername; der Farbpunkt ist rund, ohne eigenes Filament
  gestrichelt (`filament_chip`). Die Maßspalte ist nie schmaler als ihr Kopf.
- **Verlauf:** Jede zugeklappte Zeile nennt die Nummern, die sie verbirgt
  (`step_span`), auch die Löschgruppe. Der Kernwechsel steht im Kontextmenü
  zuletzt hinter einem Trennstrich (`HistoryPanel.context_menu`).
