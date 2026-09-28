# Begründungen zu `.claude/rules/fenster.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Wo ein Absatz auf „(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)“ verweist, steht
der Vorfall selbst in `ROADMAP-ARCHIV.md` unter „### `.claude/rules/oberflaeche.md`“,
gegliedert nach den Abschnitten, in denen die Regeln damals standen.

## Fenster

**Eine Einladung steht über der Ansicht, nie unter einer Karte** (Entscheidung
Robert, 23.09.2026, für die Zeile zur Unterstützung). Zwei gibt es: die
Rückfrage nach 15 aktiven Minuten (`SurveyNotice`) und die Zeile zur
Unterstützung nach dem dritten erfolgreichen Export oder Slicer-Start einer
Version (`SupportNotice`). Beide sind `survey.ViewNotice`, nicht modal, ohne
Fokus beim Erscheinen, und sie gehen erst auf einen Klick. Vier Zusagen:

* **Der Platz wird gesucht, nicht angenommen.** Die schwebenden Karten liegen
  über der Ansicht; eine Einladung darunter sieht niemand (am 1024er Fenster
  blieben zwischen Objektbaum und Prüfbericht 101 Punkte). `spot` nimmt die
  oberste freie Stelle zwischen allem, was über `keep_clear_of` gemeldet ist
  — Zonen, Ansichtsleiste, Vorschauband, Ziehwert-Leiste —, zuerst oben
  zwischen den Karten, sonst unter der kürzeren. **Wer etwas Neues über die
  Ansicht legt, meldet es dort an.**
* **Ausgewichen wird in einer Richtung.** Die Unterstützung weicht der
  Rückfrage aus, nicht umgekehrt; zwei Karten, die einander ausweichen,
  schieben sich über ihre Verschiebungsereignisse im Kreis.
* **Angeboten wird nur, wo sie jemand sieht.** Nicht hinter einem modalen
  Dialog (der Druckdialog zählt mit dem Ergebnis, angeboten wird nach
  `exec`), nicht über dem Startbildschirm. Dann kommt sie mit dem nächsten
  Ergebnis; „gesehen" merkt erst das Zeigen.
* **Gezählt wird das Ergebnis, nicht der Versuch.** `_announce_written` und
  `PrintSettingsDialog.handedOver` kommen nur nach geschriebener Datei bzw.
  gelungenem Slicen oder Öffnen an; Abbruch, Fehler und die Rückfrage vor
  Fehlern erreichen sie nie.

**Wer auf dem Startbildschirm zu arbeiten beginnt, beginnt das leere
Projekt.** Der Startbildschirm verbirgt die Arbeitsmenüs, nicht die Kürzel
und nicht die Befehlspalette — *Quader anlegen* oder *Zeichnen* ist von dort
erreichbar, und die Sitzung dahinter ist noch nie ausgewertet worden. Seit
Übernehmen auf die aktuelle dargestellte Vorschau wartet (20.09.2026), gibt
es die nur zu einem ausgewerteten Stand: Ein Dialog über dem Startbildschirm
hatte einen freien Übernehmen-Knopf, der nichts tat (gemessen am 21.09.2026).
`run_operation` und `start_sketch` gehen deshalb über
`_begin_from_the_start_screen`: dieselbe Regel wie beim Einfügen und beim
Download von dort — der Anfang ersetzt das offene Projekt, mit derselben
Frage (`_may_discard`), wenn eines verloren ginge, und mit dem Wechsel in
den Arbeitsbereich, damit die Vorschau nicht hinter dem Startbildschirm
liegt. `start_empty` sagt, ob es dazu kam.

**Ein Klick baut das Fenster einmal, auch wenn er mehrere Signale sendet**
(22.09.2026). Der Objektbaum meldet einen Klick als `selectionChanged` **und**
`featureSelected`/`featuresSelected`, und `select_feature` leert die Auswahl
vorher noch einmal. Jeder Empfänger rechnete alles: `_update_actions` lief
zweimal je Paar, und an einer Senkbohrung (zwei Merkmale) entstand das
Merkmalfenster zweimal. Der Baum geht deshalb über `_on_tree_selection`, das
die Menüeinträge dem Merkmalsignal überlässt, und `_fields_this_round` merkt
sich das Merkmal, das `featureSelected` in derselben Runde schon gebaut hat,
samt Aufbaustand des Fensters (`FeaturePanel.serial`). Wer ein weiteres Signal an
dieselbe Geste hängt, prüft mit einem Zähler, wie oft der teure Teil läuft.

## Rückfragen

*Bis zur Verdichtung in `oberflaeche.md`:*

**Eine weitere Ausnahme verlässt das Dokument** (§29, RM-140): Eine
geschriebene Datei holt kein Undo zurück, sie liegt danach auf der Platte und
im Zweifel im Slicer. Der Export prüft deshalb zuerst, zeigt die Befunde im
Prüfbericht und fragt dann — mit zwei Knöpfen, von denen einer weitergeht
(`dialogs.confirm_export`). Drei Dinge halten den Dialog davon ab, zur
Blockade zu werden, die §29 ausdrücklich nicht will:

* **Gefragt wird nur, wenn es etwas zu fragen gibt** — ab `warning`. Der
  Lizenzhinweis (§16.3) ist `info` und hält niemanden auf, und ein Dialog, der
  „alles in Ordnung" sagt, ist ein Klick ohne Auskunft.
* **Weitergehen ist die Vorgabe.** Format, Ordner und Namen stehen schon; eine
  Eingabetaste, die diese Arbeit wegwirft, wäre die schlechtere Voreinstellung.
* **Der Bericht steht daneben, nicht im Dialog.** Der Prüfbericht bekommt die
  Befunde und rückt nach vorn — dort stehen sie vollständig, mit Werten,
  Körpernamen und dem Klick, der hinführt; der Dialog zeigt die ersten Sätze
  und verweist für den Rest dorthin.

**Dieselbe Ausnahme gilt der Übergabe an den Slicer** (22.09.2026). Das Modell
liegt danach im Slicer, ein Slicen schreibt eine Druckdatei, und kein Strg+Z
holt beides zurück — der Export fragte, die Übergabe nicht. `confirm_handover`
fragt vor *Slicen* und *Im Slicer öffnen*, aber **nur bei Fehlern** der
gewählten Platten aus dem Prüfbericht, nicht bei Warnungen: Die Übergabe ist
oft der Blick ins gewohnte Programm, und eine Frage bei jedem Überhang wäre die
Blockade, die §29 nicht will. Weitergehen ist auch hier die Vorgabe.

**Und danach weiß der Kunde, wo die Datei liegt.** „Exportiert: dose.3mf" in
der Statuszeile war alles — alle vier Wege enden hier, und kein Knopf führte
zum Ordner (Bedienweg-Durchsicht 14.09.2026). *Ordner zeigen* steht daneben,
solange die Ankündigung steht (`announce` nimmt ihn mit der nächsten mit), und
öffnet den Ordner über `QDesktopServices` — Qt kennt die Plattform und im
Flatpak das Portal; ein `explorer /select` wäre eine Zusage für eine von
dreien.

**Und dieselbe Regel andersherum: Wer nur hinsieht, wird nicht gefragt**
(RM-130). Eine STL öffnen, drehen, schließen — dabei entsteht nichts, was es
nicht schon gäbe. Bis zum 12.09.2026 kam trotzdem „Ungesicherte Änderungen",
weil der Import eine Operation im Stapel ist und die Sitzung danach als
geändert gilt (gemessen an allen neunzehn Kundendateien; Robert, 04.09.2026:
eine Frage nach etwas, das er nicht getan hat). Gefragt wird jetzt nur, wenn
etwas verloren ginge, das nicht in seinen Dateien steht
(`ingest.plan.is_only_imported`, gelesen über `Session.only_imported`).

Zwei Dinge gehören dazu, und ohne sie wäre es ein Verlust statt einer
Erleichterung:

* **Gesichert wird weiter.** `Session.modified` bleibt, was es war — die
  automatische Sicherung (§38) hängt daran, und ein Absturz nach einem
  vierzehn Sekunden langen Import soll den Stand nicht kosten. Nur das
  **bewusste** Schließen fragt nicht mehr; es räumt die Sicherung dabei
  selbst weg, sonst böte der nächste Start sie an.
* **Der Weg zurück ist ein Klick.** Ein eingelesenes Modell steht seither in
  „Zuletzt geöffnet" — vorher stand dort nur, was als Projekt geöffnet wurde,
  und ohne die Frage beim Schließen wäre die Datei eine Suche im Dateidialog.

## Hinter einen Halt kommt kein Schritt

**Hinter einen Halt kommt kein Schritt** (§15.3). Hält die Kette an einem
Schritt an, zeigt das Bild den letzten vollständig gerechneten Zustand — und
was hinter dem Halt steht, wird nicht gerechnet. Ein neuer Schritt landete
dort trotzdem: durch den Dialog, in den Verlauf, nie ins Bild (Robert,
11.09.2026, nach einem Schriftwechsel: „da geht nichts mehr wenn ich die
operation ausführe"). Zwei Stellen halten das, und beide sind nötig:

* **Die Sitzung nimmt ihn nicht an** (`Session.halt_in_the_way`, gefragt in
  `apply` mit Entwürfen, `split_async`, `auto_split`, `split_along`,
  `create_lid`, `add_generated` und `accept_proposal`). Die Absage trägt die
  Handlungen des Halts selbst — dieselben Knöpfe wie im Prüfbericht, mit
  Schrittkennung, Werten und Körper, damit `error_handlers` sie ausführen
  kann (Regel 17). Eine Änderung **ohne** Schritt (Parameter, Passung,
  Drucker) geht weiter, denn die kann den Halt lösen; ebenso Rückgängig,
  *Schritt löschen* und die Wege des Verlaufs (`change_params`,
  `repair_and_retry`, `split_and_retry`, `recount_and_retry`,
  `decimate_and_retry`, `remesh_and_retry`).
* **Die Oberfläche sagt es vorher** (`_halt_reason`, die erste Frage in
  `_reason_locked`): Aktion, Palette, Karte und Zwillingshaken tragen den
  Grund mit Schrittnummer und Titel, dazu Automatisch teilen, Einfügen,
  Erzeugen, Zeichnen, Formen, Skelett und der Filamentwähler — dieselbe
  Bauart wie die Lizenzsperre und die Gestensperre daneben. Die Werkzeugzeile
  bleibt frei: Messen, Analyse und Schichten lesen nur.
* **Und das Merkmalfenster gehört dazu** (`FeaturePanel.set_locked`,
  13.09.2026). Es war die eine Bedienstelle, an der der Halt nicht ankam:
  Felder und beide Knöpfe blieben aktiv, und der Versuch endete in einem
  modalen „Das hat so nicht funktioniert" — eine Sackgasse hinter einem Klick,
  den die Oberfläche vorher hätte abraten können (Regel 19). Zwei Kodierungen
  (Regel 18): graue Knöpfe **und** der Grund als sichtbare Zeile über ihnen,
  dazu in Kurzhilfe, Statuszeile und zugänglicher Beschreibung. Die Sperre
  überlebt den Neuaufbau der Zeilen — ein Klick auf ein anderes Merkmal hebt
  sie nicht auf — und fällt nach einem Undo ohne Neuauswahl, weil
  `_update_actions` mit dem neuen Ergebnis den leeren Grund meldet.

Gemessen: Vorher standen nach dem Halt drei Schritte im Verlauf und einer im
Bild; nachher keiner, und der erste Knopf der Absage („Stückzahl anpassen und
erneut versuchen") löst den Halt — `test_a_halted_chain_takes_no_new_step_
and_names_the_way_on`.

## Der Prüfbericht

*Bis zur Verdichtung in `oberflaeche.md`:*

- **Dasselbe Problem bietet dieselben Handlungen**, gleich wer es meldet.
  „Nicht geschlossen" meldet der Kern beim Einlesen, beim Exportieren und nach
  jedem Zug des Agenten; zwei trugen ihre zwei Handlungen, der dritte nichts.
  **Die Ersatzpalette ist eine Grauleiter, keine Buntpalette:** Eine bunte
  Ersatzfarbe ist von der Auswahlfarbe nicht sicher zu unterscheiden. Echte
  Farben kommen vom Kunden (Farbwähler, Filamentkatalog); die Leiter zeigt nur
  den Zustand davor, unbunt und je Stufe unterscheidbar
  (`test_no_fallback_colour_can_be_mistaken_for_the_selection`).
  `FINDING_ACTIONS` (`app/ui/panels.py`) hält die Zuordnung, und
  `tests/test_value_labels.py` prüft die **Familie**: Befunde mit demselben
  Namen hinter dem Punkt melden dasselbe Problem, und trägt einer eine
  Handlung, müssen es alle.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

- **Die Kennung entscheidet über die Handlung, also muss sie den Fall
  treffen.** „Passt nicht" und „liegt woanders" sind zwei Fälle, und die
  Trennlinie ist nicht, über welche Seite ein Körper hinaussteht, sondern ob er
  überhaupt hineinpasst (`prepare._fits_at_all`). Der häufigste Importfall
  überhaupt: Eine 3MF aus Bambu Studio, Orca oder Elegoo führt
  **Bettkoordinaten**, ihre Körper liegen also rechts neben dem Bett. Was
  hilft, ist *Auf dem Bett anordnen*, nicht *Modell teilen*.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

- **Gleiche Meldungen sind eine Zeile, die Zahl davor in Klammern** (Robert,
  11.09.2026: „gleiche Meldungen zusammenfassen und anzahl dann davor in
  Klammer anzeigen"). Der Prüfbericht bündelt ab zwei nach Satz, Kennung,
  Schwere, Schritt und Handlungen — nicht mehr nach Körper, Ort oder Wert.
  Was dabei nicht verloren gehen darf, ist der Klick: Die Sammelzeile trägt
  alle ihre Körper und wählt sie beim Klick **alle**; ihre Handlung fragt,
  für welche sie gelten soll; Ort und Merkmale trägt sie nur, wenn alle
  Mitglieder dieselben haben. Die Karte in `app/ui/CLAUDE.md` nennt die
  Stellen.

- **Und sie stehen sichtbar da, nicht im Rechtsklick.** Unter der Befundliste
  liegt eine Knopfzeile mit den Handlungen des gewählten Befunds (leer, solange
  es keine gibt). Gefragt wird über `actions_for(finding)` — dieselbe Quelle,
  aus der auch das Kontextmenü liest; zwei Zugänge, eine Wahrheit. Ein
  Kontextmenü auf einer Listenzeile ist kein Angebot, das jemand sucht, und
  §2.7 verspricht anklickbare Handlungen.

- **Ein Fehler aus einer Operation ist ein Befund, kein Dialog.** Der Kern
  macht daraus `op.<operation>.<Ausnahme>` und hält die Kette an — deshalb ist
  der Prüfbericht und nicht der Fehlerdialog der Ort, an dem die häufigsten
  Bedienfehler landen. Ihre Handlung ist *Eingabe korrigieren*:
  `edit_operation(op_id, field)` öffnet den Schritt mit dem Cursor in dem Feld,
  das der Kern genannt hat, und ersetzt ihn beim Übernehmen (§15.4). Eine
  Handlung, die eine Schrittkennung braucht, steht in `dialogs.NEEDS_OP` und
  wird ohne sie nicht angeboten. Eine, die den **Körper** des Befunds braucht,
  steht in `panels.NEEDS_LIVE_BODY` und fällt an einem verbrauchten Körper weg
  (RM-268); `test_finding_actions` hält die Menge am Handlerverzeichnis
  vollständig — wer einen Handler baut, der `_object_of`, `_entry_of` oder
  `error.object_id` liest, trägt seine Kennung dort ein.

- **Und eine Befundzeile aus einer Operation steht nie ohne Knopf da.** Viele
  Absagen tragen Räte, die nur der Kunde ausführen kann („Weniger Durchgänge
  nehmen.“); der Fehlerdialog zeigt sie als Sätze (`dialogs.unhandled_advice`),
  der Prüfbericht nur Knöpfe. Bleibt nach dem Abgleich mit `error_handlers`
  nichts übrig, bietet `panels.handled_actions` *Eingabe korrigieren* an, und
  der Rat steht in der Kurzhilfe dieses Knopfs. Knopfzeile, Kontextmenü und
  Vorwahl fragen dieselbe Funktion.

- **Ein Klick auf einen Befund bleibt nie folgenlos.** Er ist die Geste, die
  §2.7 dem Prüfbericht ausdrücklich verspricht. Zwei Hürden — ein
  Operationsfehler trägt weder Ort noch Merkmale (der Kern gibt ihm `object_id`
  und `op_id`), und der Ort eines Kartenbefunds steht erst fest, wenn die Karte
  gerechnet ist, was beim ersten Klick nie der Fall ist.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

  Geantwortet wird gestuft, nach dem, was der Befund hergibt: **Ort** → die
  Kamera fliegt hin und eine vergängliche Marke steht dort (`mark_finding`,
  Ring plus Titel, seit dem Code-Review 0.5.1 in der Befundfarbe statt der
  Auswahlfarbe — der gewählte Körper trägt die Auswahlfarbe, und der Ring
  verschwand darin — der Ring vor dem Material an seiner
  Stelle, sein Radius aus dem Abstand in der Perspektive, der Titel in der
  Oben-Richtung der Kamera darüber; Bildbeleg RM-074, 22.09.2026); **Körper** → er wird ausgewählt und trägt
  damit Auswahlfarbe, Objektbaum und Statuszeile; **`op_id`** → der Verlauf
  zeigt den Schritt (`HistoryPanel.point_at`). Die Stufen schließen einander
  nicht aus; der Schritt gilt auch dann, wenn es keinen Körper gibt.

  Drei Fallen dabei, alle drei gemessen: Der Ort kommt aus der **Szene** und
  muss für die Ansicht verschoben werden (`view_point_of` — `fly_to` nahm ihn
  roh, und bei einem Körper auf Platte 2 flog die Kamera eine Bettbreite
  daneben). Der Ort eines Kartenbefunds wird in `_map_ready` **nachgeholt**,
  sonst bleibt der erste Klick immer stumm. Und eine Transaktion aus mehreren
  Schritten trägt keine `UserRole`, nur `OPS_ROLE` am Gruppenknoten — wer nur
  die erste liest, zeigt bei jedem Sammelschritt ins Leere.

  **Die Marke wird nicht nach vorn gezogen.** Der Ort einer Warnung liegt oft
  im Material, und der Ring verschwindet dort zur Hälfte hinter der Wand; ihn
  entlang der Blickachse davorzuziehen setzt eine orthografische Projektion
  voraus, und die Ansicht ist perspektivisch. Im Bild wanderte die Marke damit
  sichtbar von der Stelle weg, die sie meint. Eine Marke neben der Sache ist
  schlechter als eine halb verdeckte; die Beschriftung trägt `always_visible`
  und steht in jedem Fall.

## Das Merkmalfenster

**Und darüber schweigt das Merkmalfenster.** Sein leerer Zustand ist ein
Satz und keine leere Fläche — richtig, solange er etwas sagt, das sonst
niemand sagt. Ohne jede Auswahl stand er über „Nichts gewählt" und „Wählen
Sie einen Körper oder eine Fläche — Bausteine gehen auch so": derselbe
Zustand, dreimal, und nur die Karte nennt dabei den Weg zu den Bausteinen.
`FeaturePanel.say_nothing_is_chosen` nimmt ihn weg, solange gar nichts
gewählt ist; mit gewähltem Körper kommt er zurück, denn dort trägt die Karte
Handlungen und er sagt, wie man an die Maße kommt.

*Bis zur Verdichtung in `oberflaeche.md`:*

Der Haken „Auf alle N gleichartigen anwenden" gibt jedem Mitglied der Gruppe
dieselben Werte — und die Felder x, y, z des Merkmalfensters standen mit
drin. Sechs Bohrungen auf einen Durchmesser zu bringen legte sie damit an
einen Ort (Robert, 16.09.2026: „alle sind übereinander"). Die Stelle gehört
jedem Merkmal selbst: `relations.params_for_members` gibt jedem Mitglied
seine eigene gemessene Mitte, und was am gewählten Merkmal gegenüber seiner
Mitte verschoben wurde, geht als **Versatz** mit — *Merkmal verschieben* für
alle heißt „alle um dasselbe". Eine am gewählten ungenannte Achse bleibt bei
allen ungenannt (RM-154). Das Fenster baut daraus die Drafts
(`MainWindow._apply_to_each_feature`); das Panel kennt die Regel nicht, es
nennt nur Werte und Ziele.

Das Merkmalpanel begründet, warum „Auf alle N gleichartigen anwenden"
zulässig ist: parallele Achsen, gleiche Rolle in der Bohrungskette, gleich
liegende Abschnitte. Die Nachweise kommen je Handlung aus dem Kern, und an
einer Bohrungskette sind sie für alle Handlungen dieselben — der Absatz stand
damit an einer Senkung **viermal** untereinander, wörtlich gleich (Befund
Robert, 07.09.2026: „im merkmalpanel ist zu viel text").

`FeaturePanel._said_notes` merkt, welcher Absatz schon steht; geleert wird die
Menge in `clear()`, und `show_feature` beginnt damit. Dasselbe Muster wie
`_folded` eine Ebene höher — dort für den Grund einer Absage, hier für den
Nachweis einer Gruppe.

**Weggelassen wird die Wiederholung, nicht die Auskunft.** Ab der zweiten
Handlung trägt der Haken sie in Tooltip, Statuszeile und zugänglicher
Beschreibung; er ist das Feld, über das sie entscheidet. Ohne das verlöre ein
Screenreader sie an jeder Handlung außer der ersten.

### Ein zusammengelegter Grund spricht für alle, unter denen er steht

`_folded` macht aus fünf gleich begründeten Absagen **eine** Zeile:
„Verschieben, Ändern, Drehen, Verdoppeln und Entfernen — <Satz>". Der Satz
steht damit unter fünf Titeln und darf keinen einzelnen davon aufgreifen.

Eine Durchsicht aller zehn Merkmalsarten am 10.09.2026 (Robert: „auch alle
anderen mal gründlich kontrollieren") fand vier Stellen, an denen er es tat:

| Art | stand unter fünf Titeln | begründete |
|---|---|---|
| `face` | „lässt sich nicht einzeln **versetzen**" | eine von fünf |
| `torus` | „lässt sich nicht direkt **ändern**" | eine von fünf |
| `fillet` | „**Versetzt** man sie allein …" | auch das Verdoppeln |
| `thread` | „gibt es noch keine Handlung" | gar nichts (Regel 17) |

Die gute Form verneint die **Voraussetzung** statt der Handlung: „trägt kein
Maß, an dem sich Lage oder Größe ändern ließen" gilt für jede Zeile, die daran
ansetzen wollte, und nennt danach den Weg, der bleibt.

**Maschinell ist das nicht zu prüfen, und der Versuch ist gemessen
gescheitert:** Ein Wächter, der den Titel im Satz sucht, schlug auf „ändern" in
„kein Maß, das sich ändern ließe" an — drei Fehlalarme auf drei Prüflinge, weil
„ändern" im Deutschen beides ist. Er ist deshalb nicht eingecheckt; was bleibt,
ist der scharfe Teil derselben Durchsicht
(`test_no_feature_kind_falls_back_to_the_sentence_that_says_nothing`): Keine
erkennbare Art fällt auf `_UNKNOWN_KIND` zurück. Der Rest ist Lesen, und dieser
Absatz sagt, worauf.

*Aus `fenster.md`:*

**Eine Anzahl ist keine Länge.** `count`, `steps`, `holes` sind ganze Zahlen
ohne Einheit; als Längenfeld hießen sie im Merkmalfenster „2,00 mm", in Zoll
„0,08 in", und gingen als `4.0` in den Schritt. `perceive.actions._kind_of`
nennt `int` deshalb `count`, das Fenster baut dafür ein Ganzzahlfeld, und was
zurückgeht, ist `int`. Wer eine neue Feldart in `ActionField.kind` einführt,
baut sie an beiden Enden — im Kern benannt, im Fenster gebaut und eingesammelt.

## Ein Merkmal aus einem Baustein meint den Baustein

**Und der Organizer gehört dazu, obwohl er kein Baustein ist** (Befund
Robert, 18.09.2026: „Baustein verschieben bei Trennwand organizer keine
Wirkung" und „keine Ahnung wie man hinkommt"). Er steht unter `primitive`,
weil er aus eigenen Maßen entsteht, und bringt je Fach und je Trennwand
Merkmale mit; an einer Trennwandfläche standen die Handlungen einer Fläche.
Keine davon meint die Trennwand, und ihre **Lage steht in keinem Parameter**
— sie folgt aus den Fachmaßen, und die ändert der Fächereditor.
`panels.SPEAKS_FOR_ITS_FEATURES` nennt ihn namentlich; eine zweite Kategorie
zöge Menüort und Katalogkachel mit, und beides soll bleiben.

**Und der Name allein entscheidet dort nicht.** Anders als bei einem Baustein
spricht der Schritt nicht für **jedes** seiner Merkmale: Der Eintrag nennt
neben der Operation die **Rollen**, für die er gilt (`divider`), und
`part_step_of` fragt sie am Merkmal (`organizer_role`). Fachböden und
Innenboden behalten damit ihre Flächenhandlungen — an ihnen ist eine Bohrung
oder eine Tasche eine sinnvolle Geste, an einer Trennwand nicht.

**Der Griff folgt einer zweiten Frage: Kennt der Schritt eine Lage?** Ein
Organizer führt kein `x/y/z` — seine Trennwände folgen den Fachmaßen —, und
ein Zug an seinem Merkmal fiele sonst auf `move_feature` zurück, das die
Auswertung sofort anhält. `MainWindow._asks_for_the_part` verlangt deshalb
`x/y/z` am Schritt, und das trifft gemessen vier der 49 Schritte, die hier
ankommen (die Kategorie `parts` und was in `SPEAKS_FOR_ITS_FEATURES` steht):
den Organizer, beide Deckel und die Profil-Einlagen. Dort bleibt der Griff
der der Fläche.

**Und was kein Zahlenfeld werden kann, bekommt seinen Weg statt zu
verschwinden.** Eine Fachaufteilung ist ein Sammelparameter mit eigenem
Editor (`perceive.actions.COLLECTED_KINDS`, dieselben Arten wie in
`operationen.md` unter „Sammelparameter"); `_kind_of` kennt sie nicht und
gäbe ihr ein Längenfeld — „Fachaufteilung: 0,00 mm". Sie steht deshalb in
`FeatureAction.elsewhere`, und das Panel hängt darunter einen Knopf, der den
vollständigen Dialog des Schritts öffnet. Dieselbe Bauart wie *Weitere
Einstellungen …* an einer Textur. Wer einen neuen Sammelparameter baut, trägt
seine Art dort ein — sonst steht sie als Länge im Merkmalfenster.

Ein Schlüsselloch bringt zwölf Merkmale mit, zehn davon
Verrundungen, und `fillet` trägt im Register keine einzige Operation — wer
eine Schlitzkante anklickte, sah die Handlungen der Fläche darunter
(Robert, 10.09.2026: „hier sollten wir aber alles für das Schlüsselloch
sehen"). Gefragt wird über `Feature.created_by` und die **Kategorie**
`parts`, nicht über den Namen der Operation: `drill_hole` erzeugt ebenfalls
eine Bohrung mit Provenienz und ist kein Baustein.

Drei Handlungen, und sie gelten dem **Schritt**: Maße ändern, verschieben,
entfernen. Ein `resize_feature` auf die runde Tasche bohrte sie auf und
ließe den Schlitz stehen; was die Größe wirklich ändert, ist die
Schraubengröße im Schritt, und die ändert beide Hälften zusammen. Die Werte
kommen aus dem Schritt und nicht aus der Messung — aus zwei gemessenen
Durchmessern käme keine Schraubengröße zurück, und jedes Zurückschreiben
verlöre ein Stück.

**Und jede Handlung schickt nur ihren eigenen Ausschnitt.** Das Fenster
legt ihn über die Werte, die im Schritt stehen (`_change_part_step`); wer
beim Verschieben den Rest mit Vorgaben überschriebe, setzte die
Schraubengröße zurück, und das fiele erst beim nächsten Öffnen auf.

**Und der Griff im Bild hält sich an dieselbe Regel.** Sie galt bis zum
14.09.2026 nur für die Felder rechts: Der Zug am Griff der Tasche wurde ein
`move_feature` auf die Tasche — der Schlitz blieb bei (10 | 13) stehen, zehn
Verrundungen verloren ihre Erkennung, und der Verlauf trug einen zweiten
Schritt. Jeder Zug an einem Bausteinmerkmal — Griff, Körpergriff,
Bewegen-Leiste — geht in den Schritt des Bausteins
(`MainWindow._move_the_part`); und der Griff hängt an **jedem** seiner
Merkmale, auch an denen ohne eigene Operation (`Viewport.moves_as_a_part`).
Wer eine neue Geste an einem Merkmal baut, fragt zuerst, ob es aus einem
Baustein kam. **Und die Drehachse ist die des Bausteins, nie die des
angefassten Merkmals**: An einem benannten Sitz (`at_feature`) gibt das
Sitzmerkmal die Richtung (`direction_of`, dieselbe Funktion wie im Kern), mit
freier Richtung rechnet die Rundreise `placement_transform` →
`placement_values_of`, und was keins von beidem hat, dreht nur um sein Feld
*Achse* — jede andere Achse bekommt einen Satz mit dem Weg, nicht eine stille
Drehung um die falsche.

**Und die Fläche eines Bausteins ist der Baustein** (16.09.2026). Die Rippe
besteht aus nichts als Flächen, und an einer Fläche hing der Griff der Fläche:
ein Pfeil entlang der Normalen, dessen Zug ein `push_face` auf den
verschmolzenen Körper wurde (Robert: „bei manchen bausteinen keine
möglichkeit zum verschieben"). `Viewport.gizmo_target` kennt an einer
Bausteinfläche kein Press/Pull, `gizmo_feature` hängt den Bewegungsgriff
daran, und der Satz in der Statuszeile nennt den Baustein. Dieselbe Frage
stellen drei weitere Wege, und alle drei gingen bis dahin am Baustein vorbei:

* **Entf.** Am Dach im Baum wie an einer einzelnen Verrundung fällt der
  Schritt des Bausteins (`MainWindow._delete_the_chosen_feature`, derselbe
  Weg wie *Baustein entfernen* rechts) — und nie der Körper. Ohne Baustein
  gilt der Zwilling `remove_feature`; wo auch der nicht greift (eine Fläche,
  ein Gewinde, eine Verrundung), **fällt der Körper**, mit der Ansage in der
  Statuszeile und dem Rückweg über Strg+Z. Diese dritte Lage hat am
  16.09.2026 zweimal die Richtung gewechselt: Morgens fiel an einem
  Bausteindach still der ganze Körper (Robert: „wenn ich etwas im objektbaum
  oder viewport auswähle und entf drücke … wird der ganze körper gelöscht")
  — dafür ist die erste Lage da. Danach löschte Entf an einer Fläche gar
  nichts mehr und verwies auf Escape, und abends am eingelesenen Tray hieß
  es „warum kann ich kein körper mehr löschen": Im Bild trifft ein Klick
  immer eine Fläche, und ein Teil, das sich mit Entf nicht löschen lässt,
  ist eine Sackgasse (Regel 19). Eine Fläche ist kein Ding, das man löscht —
  der Körper ist gemeint. Der Eintrag *Ausblenden* im Kontextmenü heißt an
  einem Merkmal deshalb *Körper ausblenden* — er trifft den Körper, und der
  Name sagt es.
* **Körpergriff und Bewegen-Leiste bei gewähltem Dach.** `selected_feature`
  schweigt bei mehreren Zeilen; `_move_the_part` fragt dann
  `_common_part_step` statt den Zug an den ganzen Körper durchzulassen. **Und
  im Bild bekommt das Dach einen eigenen Griff**
  (`MainWindow._part_grip_anchor` → `Viewport.set_part_grip`): Vorher hing
  dort der Griff des Körpers mit seinem Skalierwürfel, der auf einen Zug die
  Maße des ganzen Teils ändert (Robert: „warum kann ich die bausteine nicht
  über den viewport verschieben?"). Welches Merkmal ihn trägt, sagt das
  Fenster — die Ansicht kann je Merkmal nur fragen, ob es aus *irgendeinem*
  Baustein kam.
* **Und die Bohrung eines Bausteins bekommt ihn ohne *Im Bild einstellen*.**
  Der Knopf steht nur an einem freien Loch (`placed_feature_kinds`), und ein
  Baustein bietet ihn nicht an — an einem Schraubenloch trug die Senkung
  einen Griff und die Bohrung daneben keinen. Die Langlochknöpfe bleiben dort
  weg: Ihr Zug schnitte ein Langloch neben den Schritt des Bausteins, und
  beim nächsten Verschieben bliebe es stehen.
* **Ein gebundener Wert bricht das Merkmalfenster nicht mehr ab.** Steht an
  einer Achse ein Ausdruck, bekommt das Feld das `ValueField` des
  Operationsdialogs (`FeaturePanel._part_fields`); `float("=@staerke")`
  beendete den Aufbau vorher mitten in der Liste, und rechts stand nur noch
  *Maße ändern* — ohne Verschieben und ohne Entfernen. Das ist dieselbe
  Lücke, die §13 beim Operationsdialog schon einmal geschlossen hat.
* **Filament.** Der Schnellwähler färbt an einer Bausteinfläche **alle**
  Flächen des Bausteins (`_part_faces_of_selection`, „Die Zuweisung gilt dem
  ganzen Baustein: 7 Flächen."); Wähler, Zuweisen und Entfernen lesen
  dieselbe Menge (`_filament_targets`). Die Rippe hat kein Filament je Seite
  (Robert: „wo stelle ich von der Versteifungsrippe insgesamt das filament
  ein?"). Die Chips in der Filamentspalte des Baums bleiben je Fläche — wer
  dort klickt, zeigt auf genau eine.

**Und eine gebundene Lage folgt dem Griff.** Hängt `z` eines Bausteins an
`=@staerke`, wandert der Zug als Versatz in den Ausdruck
(`expressions.shifted`: `=@staerke + 5`), statt ihn durch eine Zahl zu
ersetzen oder — wie bis zum 16.09.2026 — jede Bewegung abzulehnen; im
Beispielprojekt, dessen Bausteine ihre Höhe so binden, sprang damit jeder Zug
zurück (Robert: „das verschieben geht nicht springt immer wieder zurück").
Eine Achse ohne Zug bleibt unangetastet, auch ihr Ausdruck. Abgelehnt mit
Satz wird nur noch, was eine **Drehung** an einem gebundenen Wert ändern
würde — die Rundreise rechnet mit Zahlen und könnte den Ausdruck nicht
zurückschreiben.

**Und ein Langloch aus einem Schritt gehört dazu.** Es ist kein Baustein, aber
dieselbe Regel: Hat `slot_hole` es gezogen, ändert *Übernehmen* diesen Schritt
(`_prepare_slot_change`, geschrieben über `_commit_slot_change`) und legt
keinen zweiten obenauf — der schnitt bis zum
15.09.2026 quer über das erste (Robert: „habe ich 2 langlöcher"). Wer eine
weitere Operation baut, die ein Merkmal aus ihrem eigenen früheren Schritt
noch einmal anfasst, fragt zuerst `created_by`.

## Der Hauptknopf

**Ein Hauptknopf entsteht über `style.make_primary()`, nie über
`setDefault(True)`.** Das Stylesheet zeichnet `QPushButton:default` halbfett;
Qt rechnet die bevorzugte Breite aus der **normalen** Schrift des Widgets. Wo
ein Layout dem Knopf genau diese Breite gibt — in einer engen Leiste tut es
das —, wird die Beschriftung abgeschnitten: Auf dem Hauptknopf des
Trennwerkzeugs stand „etzt trenne", 89 Bildpunkte Text in 104 minus
Innenabstand. `make_primary` setzt die Schrift am Widget, damit die Rechnung
sie kennt; das Fett bleibt, denn es ist neben der Akzentfarbe die zweite
Kodierung (Regel 18). `tests/test_style.py` misst gegen die Schrift, mit der
wirklich gezeichnet wird, und verbietet `setDefault(True)` außerhalb von
`style.py`.

**Ein Knopf, der verwirft, entsteht über `style.make_danger()`** — das
Fehlerrot der Palette (`ROLES["error"]`) als Fläche, die Schrift darauf aus
`readable_on`, das Wort als zweite Kodierung (Regel 18). *Abbrechen* unter
*Übernehmen* im Merkmalfenster ist der Fall: gleich breit wie der Hauptknopf,
und ohne eigene Farbe dessen Zwilling (Robert, 11.09.2026). `tests/test_style.py`
misst die Fläche am gezeichneten Knopf.

**Und wo keiner gesetzt wird, setzt Qt selbst einen.** Das ist die stille
Hälfte derselben Regel, und sie ist die häufigere: `QDialog` macht beim
**ersten `show()`** den ersten Knopf mit `autoDefault` zum Default, gleich wo
er im Fenster sitzt. Er trägt damit die Akzentfarbe aus `QPushButton:default`
— aber **nicht** die halbfette Schrift, die `make_primary` am Widget setzt.
Übrig bleibt Bedeutung allein über Farbe, also Regel 18 — und was wie eine
Empfehlung aussieht, ist die Reihenfolge im Layout.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Zwei Dinge folgen daraus:

* **Ein Fenster ohne Handlung nimmt `style.no_primary()`.** Es räumt den
  Default ab (`setAutoDefault(False)`), und das ist kein Verstoß gegen „ein
  Hauptknopf je Fenster", sondern deren Kehrseite: Wer nichts zu tun anbietet,
  hat auch nichts zu empfehlen. Wer eine Handlung hat, nimmt `make_primary` —
  auch wenn der Knopf gesperrt startet.
* **Gefunden wird das nur am angezeigten Fenster.** Vor dem `show()` meldet
  `isDefault()` überall `False`; ein Quelltext-Wächter nach `setDefault(True)`
  sieht gar nichts, weil es niemand ruft. `tests/test_style.py` hält deshalb
  **beide** Richtungen — `test_every_default_button_of_the_surface_goes_
  through_make_primary` am Text und `test_no_window_wears_an_accent_it_never_
  asked_for` am gebauten Fenster.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und ein typloses Stylesheet am Vorfahren nimmt ihm seine Farben.** Eine
Regel ohne Selektor — `setStyleSheet("background: #202225;")` an einer Karte,
einer Leiste, einem Rahmen — gilt für den Träger **und jeden Nachkommen** und
**ersetzt** dort die Regeln des Anwendungs-Stylesheets, statt sie zu ergänzen.
`QPushButton:default` greift dann nicht mehr, und weil diese Regel neben
`font-weight` auch `background` und `color` trägt, steht der Hauptknopf mit
Rahmen und **ohne lesbare Beschriftung** da. Es wirkt über Ebenen — auch aus
dem Stylesheet der Großeltern.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und nur für die Eigenschaften, die sie selbst setzt.** Das ist die Hälfte,
ohne die man an fünf Stellen sucht, an denen nichts ist: Ein typloses
`border:` — wie es `_flash` beim Aufblinken eines Bereichs setzt
(`main_window.py`) — nimmt dem Hauptknopf gar nichts, weil `QPushButton` im
Anwendungs-Stylesheet eine eigene `border`-Regel trägt und die gewinnt.
Gefährlich ist allein dieselbe Eigenschaft, die der Knopf braucht, und das ist
`background`.

**Ein `QDialog` ist dabei nicht der Unterschied**, auch wenn es zuerst so
aussah: Ohne Stylesheet färbt der Knopf in einem schlichten `QWidget` genauso
wie im Dialog — und ein Gegenbeispiel, das dieselbe Bedingung trägt wie der
Fall, ist keines.

**Ein Knopf ohne sichtbare Beschriftung nimmt Klicks entgegen wie jeder
andere** — ein grüner Klicktest sagt nichts über sein Bild.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## `setParent(None)` macht ein Kind zum Fenster

Qt kennt keinen „elternlosen Zustand" — ein Widget ohne Elternteil **ist** ein
Top-Level-Fenster. Wer ein Kind-Widget wegräumen will und ihm den Elternteil
nimmt, stellt es für die Dauer bis zum Löschen als eigenes Fenster auf den
Bildschirm. Gemessen am 12.09.2026 im Prüfbericht: vier Knöpfe „Auf das Bett
setzen" als Top-Level nach einem Befundwechsel, zwei davon sichtbar — und
genau das hatte jemand gesehen.

**Weggeräumt wird deshalb mit `hide()` und `deleteLater()`**, nie über den
Elternteil. `takeAt` nimmt es aus dem Layout, `hide` aus dem Bild, und der
Elternteil trägt es bis zum Löschen.

Dasselbe Wissen stand vorher zweimal als Kommentar im Code und einmal nicht:
`MainWindow._close_sketch` nennt den Absturz („ein Fenster, das im selben
Atemzug gelöscht wird"), `SketchEditor.take_constraint_list` die falsch
aufgelösten Tastenkürzel („`plane:xy` statt `plane:xz`"), und
`ReportPanel._show_offers` tat es trotzdem. Ein Kommentar an zwei Stellen ist keine Regel.

## Die automatische Sicherung

Sie ist für den **Absturz** da (§38) und nie dafür, eine Entscheidung des
Nutzers zu überstimmen. Drei Regeln, alle drei einmal gebrochen gewesen:

* **Verworfen heißt verworfen.** `_may_discard` räumt die Sicherung, wenn der
  Nutzer *Verwerfen* wählt. `closeEvent` schrieb dort eine — nach der Frage,
  also genau dann, wenn jemand gerade Nein gesagt hatte.
* **Abgelehnt heißt einmal gefragt.** Eine Sicherung, die man nicht öffnen
  will, wird gelöscht; sonst ist sie weiter neuer als die Datei und dieselbe
  Frage kommt bei jedem Öffnen wieder. Gemessen waren es sechs Öffnungen und
  sechs Fragen. Was das Ablehnen kostet, steht im Dialog — eine Löschung ohne
  Ansage wäre der nächste Fehler.
* **Angenommen speichert in die Datei des Nutzers.** `Session.recover(candidate,
  path)` nimmt den Inhalt der Sicherung und behält den Pfad des Projekts.
  Über `open_project(candidate)` wurde die Sicherung zum Projekt: ein
  „Speichern" schrieb nach `…p3d.autosave`, die eigentliche Datei blieb
  unberührt, und die wiederhergestellte Arbeit war beim nächsten Öffnen wieder
  fort.
* **Namenlos heißt je Dokument eine Kennung, nicht je Rechner eine Datei.**
  Zwei Fenster mit je einem neuen, ungespeicherten Projekt schrieben beide
  `unsaved.p3d.autosave`: Die zweite Sicherung ersetzte die erste, und das
  Aufräumen aus dem einen Fenster löschte die des anderen (Gesamtreview
  05.09.2026, CORE-09). `Session.recovery_token` kommt aus
  `project.recovery_token()`, `_reset_for` zieht je Dokument eine neue, und
  jede der vier Sicherungsfunktionen nimmt sie entgegen. Angeboten wird beim
  Start die jüngste **fremde** Sicherung; abgelehnt wird genau sie geräumt
  (`discard_recovery`), angenommen wandert sie unter die eigene Kennung.

## Wie die Karten ihre Höhe teilen

`OverlayHost._share_room` verteilt die Höhe einer Zone auf ihre `RoomTaker`.
Drei Zusagen, und alle drei sind schon gebrochen worden:

* **Gerechnet wird nie mit den Höhen, die gerade gesetzt wurden.** Eine
  Zuteilung, die ihr eigenes Ergebnis liest, bekommt beim nächsten Durchlauf
  andere Zahlen und die Karte läuft auf und ab. Deshalb taugt `natural_height`
  **innerhalb** der Zuteilung nicht: sie liest für ihre Rollbereiche die
  gelegten Höhen. `extra_height` rechnet strukturell — je Posten der
  Unterschied zwischen dem, was er als Ganzes wünscht, und dem, was die Karten
  darin wünschen.
* **Was nicht den Karten gehört, wird abgezogen.** Abschnittsköpfe,
  Parameterleiste, Layoutabstände. Ungekürzt verteilt die Zuteilung mehr Höhe,
  als die Zone hat: Der Objektbaum stand auf 500 Pixeln in einem Abschnitt von
  121, das Elternwidget schnitt die Differenz weg, und weil der Baum von seiner
  eigenen Höhe ausging, meldete sein Rollbalken dazu nichts. Zehn Zeilen waren
  nicht abgeschnitten, sondern unerreichbar.
* **Jede Karte nennt ihren Boden** (`RoomTaker.least_height`), und verteilt wird
  nur, was darüber liegt. Sonst ist die Zuteilung eine Bitte. Der Boden hat
  zwei Quellen, und beide zählen — `fit_to_rows` mit seinen drei Mindestzeilen
  und der leere Zustand, dessen Höhe aus dem umbrochenen Satz kommt
  (`fit_wrapped`) und nicht aus der Zeilenrechnung. **Und nie höher als der
  Wunsch**: Eine Karte, die überhaupt nur eine Zeile *hat*, forderte über jene
  drei Mindestzeilen 130 Punkte für 128 gewünschte — Platz, den sie niemandem
  zeigen kann, während die Nachbarn ihn brauchen.

`tests/test_overlay.py` hält alle drei: „settles on one answer",
„moves a card once", „no card is pushed outside its section".
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**`fit_to_rows` rechnet mit *einer* Zeilenhöhe** — der ersten, mal der Zahl
der Zeilen. Für einen Baum, in dem jede Zeile gleich aussieht, ist das
richtig; für eine Liste mit fetten Zwischenüberschriften ist es zu wenig. Wer
eine Liste mit ungleichen Zeilen bemisst, nimmt `overlay.rows_height` — es
misst jede Zeile einzeln, und `wanted_height` muss dieselbe Quelle nehmen wie
das Setzen, sonst fordert die Karte etwas anderes, als sie einrichtet.

**Und was unter der Liste steht, gehört in beide Rechnungen.** Hinweis und
Knöpfe einer Karte sind kein Beiwerk der Zone, sondern Teil der Karte: Wer der
Liste die ganze Zuteilung gibt, schiebt sie unten heraus — und mit ihnen den
einzigen Weg, den die Karte anbietet.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Gesetzt wird einmal je Ereignisdurchlauf, nicht je Ereignis.** Der Filter
des Trägers sieht jedes `Resize`, `Show`, `Hide` und `LayoutRequest` jedes
Kindes, und jedes davon rechnete die Zonen sofort neu: 433 Durchläufe beim
Start, 671 auf Weg 1, 81 bis 115 ms je Undo (Review 21.09.2026).
`_place_later` merkt vor und setzt über einen Nullzeitgeber — ein Zeitgeber
und kein nachgereichtes Ereignis, weil die Listen ihre Zeilen selbst über
einen Nullzeitgeber legen und `rows_height` an `visualRect` misst; ein
Ereignis käme vor den Zeilen dran und läse die alte Höhe. `resizeEvent` und
`reflow` setzen weiter sofort. **Für Tests heißt das: mehrere Runden
`processEvents`**, bis Karte und Liste zur Ruhe gekommen sind (gemessen drei
für eine gewachsene Berichtkarte) — eine Zusicherung nach einer Runde misst
einen Zwischenstand. `is_room_taker` beantwortet die Frage je Widget-Typ
einmal; sie ist strukturell, und der Typ ändert sich nicht.

## Rückmeldung und Fehlerbericht

*Bis zur Verdichtung in `oberflaeche.md`:*

Ein Dialog für beides (`app/ui/support_dialog.py`), aufgerufen aus *Hilfe →
Rückmeldung senden* und aus `report_error` — dort mit `kind=crash`, eigenem
Titel und der Ansage „Das war ein Programmfehler, nicht Ihre Schuld" (§33.1).
Zwei Fenster, die zu vier Fünfteln dasselbe taten, waren zwei Menüeinträge zu
viel.

Vier Zusagen, alle vier tragend:

* **Von allein geht nichts.** `support.send()` hat genau einen Aufrufer, und
  der hängt am Knopf; `tests/test_support.py` zählt ihn. Was die Grenze zur
  verbotenen Telemetrie hält, ist nicht die Formulierung, sondern diese Zahl.
* **Nichts ungesehen.** Die Vorschau zeigt den vollständigen Text der Sendung
  samt Anhängen und Gesamtgröße, bevor gesendet wird.
* **Das Bildschirmfoto entsteht vor dem Dialog.** Eine Sekunde später zeigt es
  den Dialog statt dessen, was darunter schiefging — `window_shot(self)` steht
  deshalb im Fenster und nicht im Dialog. Das sichtbare Fenster wird über
  `screen().grabWindow(winId())` aus vorhandenen Bildpunkten aufgenommen,
  ohne das möglicherweise defekte Modell erneut zu rendern. Nur wenn diese
  Aufnahme leer bleibt, folgt `grab()` mit den Viewport-Bildern. Aufgenommen
  wird ausschließlich das Solidon-Fenster, nie der gesamte Bildschirm.
* **Der abgelegte Ordner ist ein Weg, kein Notausgang.** *Bericht ablegen*
  steht dauerhaft in der Knopfleiste (§37.2); *Selbst per E-Mail senden*
  erscheint erst, wenn ein Versand scheiterte — ein zweiter Weg neben einem
  Knopf, der gerade funktioniert, liest sich wie eine Warnung.

Die Sitzung wird für den Anhang **einmal** im Arbeiter gespeichert und behalten:
zweimal hieße, dass die Vorschau eine andere Größe nennt als die Sendung trägt.
Der Arbeiter besitzt eine Kopie von Dokument und Bericht sowie eine eigene
Quellzuordnung; unveränderliche Datei-Bytes dürfen geteilt werden. Bis der
gewählte Anhang fertig ist, zeigt der Dialog die Vorbereitung und sperrt den
Versand. Abwahl und Schließen bleiben möglich; geschlossene Dialoge verwerfen
späte Antworten. Auch die Protokollbytes werden einmal behalten und für
Vorschau, Versand und Ablage identisch verwendet. `report.log_tail()` liest
rückwärts höchstens 1 MiB für die letzten 400 Zeilen, nie das gesamte Protokoll.
