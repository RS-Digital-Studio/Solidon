# Begründungen zu `.claude/rules/oberflaeche.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Wo ein Absatz auf „(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)“ verweist, steht
der Vorfall selbst in `ROADMAP-ARCHIV.md` unter „### `.claude/rules/oberflaeche.md`“,
gegliedert nach den Abschnitten, in denen die Regeln damals standen.

## Kopf: warum die Oberflächenregeln in mehreren Dateien stehen

Diese Datei lud mit **jeder** der vierundachtzig Dateien unter `app/ui/` und
wog dabei 99 KB. Zwei Gebiete gelten nicht für alle und stehen jetzt für sich:

| Gebiet | Steht in | Lädt bei |
|---|---|---|
| Höchstens neun Menüs, zwölf Zeilen, acht Werkzeuge, acht Felder vorn — und die Begründungen dazu | `grenzen.md` | Register, Hauptfenster, Panels, Operationsdialog, Werkzeugzeile, Palette, Katalog |
| Die drei Zonen, der Hauptknopf, die automatische Sicherung, die Höhe der Karten, `setParent(None)` | `fenster.md` | Hauptfenster, Dialoge, Startbildschirm, Erststart, Handbuchfenster |

**Die Grenzen gelten weiter für jeden**, auch wo `grenzen.md` nicht lädt:
Neun Menüs, zwölf Zeilen je Menü, acht Umschalter, acht Felder auf der
Vorderseite, ein Menüeintrag je Operation. Wer eine dieser Zahlen erhöhen
will, tut es mit Absicht und begründet es im Commit —
`tests/test_interface_limits.py` wird sonst rot.

## Eine Auskunft, eine Quelle

Bei der Verdichtung neu gefasst. Derselbe Grundsatz stand vorher an vielen
Stellen einzeln — wörtlich unter anderem:

- `oberflaeche.md` (Merkmalfenster): „Die Bedingung reist als
  `ActionField.depends_on` aus dem Schema; eine zweite Liste in der Oberfläche
  wüsste beim nächsten Parameter nichts davon.“ und „Die Sperre gehört dem
  Kettenhalt (`_settle_lock`), und zwei Stellen, die dieselbe Sperre setzen,
  gewinnen abwechselnd.“
- `oberflaeche.md` (Prüfbericht): „Gefragt wird über `actions_for(finding)` —
  dieselbe Quelle, aus der auch das Kontextmenü liest; zwei Zugänge, eine
  Wahrheit.“
- `oberflaeche.md` (Anzeigeeinheit): „Zwei Wege zu derselben Auskunft sind einer
  zu viel, und welcher benutzt wird, entscheidet nicht der Vorsatz.“
- `fenster.md`: „anders als bei einer Angabe, die eine Fähigkeit ausspricht
  (`requires_kind`, `applies_to`): die gehört ins Register, weil eine Liste in
  der Oberfläche beim nächsten Zuwachs schweigt.“, „eine zweite Aufzählung in der
  Oberfläche wüsste bei der nächsten Feldhandlung die Hälfte“ und „zwei Stellen,
  die dasselbe verbergen, setzen es beim nächsten Nachbessern abwechselnd.“
- `grenzen.md`: „eine weitere Formulierung derselben Auskunft wäre eine weitere
  Gelegenheit, auseinanderzulaufen“, „zwei eigene Erklärungen für einen Knopf
  driften auseinander“ und „Dieselbe Frage, zwei Rechnungen — genau der Grund,
  aus dem die Menütiefe in den Kern gewandert ist.“

## Texte

**Eine Tabelle, und Auswahlwerte stehen an zwei Stellen.** Die
Druckeinstellungen führen ihre sechsundfünfzig Felder in einer eigenen Liste
(`print_settings_dialog.FIELDS`) — eine zweite Namenstabelle davor verdeckt
die erste und läuft auseinander. Der Test prüft deshalb **beide Feldquellen**
gegen die eine Tabelle; wer eine dritte Liste von Auswahlwerten anlegt, hängt
sie dort ein.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Jedes Feld sagt, was es tut — und zwar alle.** Das gilt an zwei Orten: Die
sechsundfünfzig Felder der Druckeinstellungen tragen je einen `note`-Satz, die
1334 Parameter der 142 Operationen ihren `doc`-Satz aus dem Register. Beide Male
hängt er an **beiden** Hälften der Zeile — wer eine Zeile nicht versteht, zeigt
auf das unverständliche Wort und nicht auf den Kasten daneben. In den
Druckeinstellungen setzt `_editor` ihn am Eingabefeld und `_label` an der
Beschriftung; im Operationsdialog holt `QFormLayout.labelForField` die
Beschriftung, die `addRow` aus der Zeichenkette gebaut hat (`_explain` in
`op_dialog.py`). Ist eine Zeile gesperrt, tragen beide
Hälften den *Grund* statt des Satzes — in ein ausgegrautes Feld zeigt niemand,
man zeigt auf das Wort davor. Die Regel nannte zuletzt 2296 Parameter der 178
Operationen (06.10.2026); sie nennt keine Zahl mehr, weil kein Test sie hält.

Der `note`-Satz ist nicht der Titel noch einmal, sondern sagt, was passiert,
wenn man den Wert bewegt („Rechnet die Außenwand
auf ihr Sollmaß statt auf die Bahnmitte. Für Passungen richtig, sonst
unnötig."). Dazu `statusTip` und `accessibleDescription`: die Statuszeile zeigt ihn ohne
Wartezeit, der Bildschirmleser liest ihn vor (Regel 18 — nicht nur eine
Kodierung). Ein Widget, das seinen Tooltip selbst führt, behält ihn: Der
Farbknopf nennt darin den Hexwert, den sonst nichts zeigt, und hängt den Satz
dahinter. Fünfzehn erklärte Felder von sechsundfünfzig wären schlimmer als
keines — dann lernt niemand, dass es hier Sätze gibt.

**Und die Auswahlwerte selbst tragen je einen Satz.** Der Name aus
`_CHOICE_NAMES` benennt, der Satz aus `_CHOICE_NOTES` daneben sagt, was der
Wert bewirkt und was er kostet — „Gyroid" ist ein Name, erst „in alle
Richtungen gleich fest" ist eine Entscheidungshilfe. `explain_choices(box)`
hängt ihn an jeden Eintrag (ToolTipRole **und** AccessibleDescriptionRole,
Regel 18), gelesen am rohen Schlüssel im `itemData`; nach jeder Neubefüllung
erneut aufrufen, `clear()` nimmt die Rollen mit. Dieselben zwei Zusagen wie
bei der Namenstabelle — flach (derselbe Schlüssel bedeutet überall dasselbe,
der Satz muss in jedem Kontext wahr sein: `grid` beschreibt Füllung und
Stützmuster zugleich) und vollständig (`test_every_named_choice_also_says_
what_it_does` hält Namen und Sätze deckungsgleich, Selbstnamen wie „M4"
stehen absichtlich in keiner der beiden). Anders als bei `QMenu` braucht die
offene Combo-Liste keinen Schalter: ToolTipRole zeigt sie von sich aus,
gemessen unter der echten Plattform per QHelpEvent.

Bilder statt
Wörter, wo ein Wort nichts zeigt: die Texturmuster tragen ihre Kachel aus
`figures.texture_tile`, erkannt an den Werten des Feldes und nicht an seinem
Namen. Ein Fehler endet nie mit „fehlgeschlagen": erst was nicht ging, dann
warum, dann was jetzt möglich ist, als anklickbare Handlungen (§2.7). Kein
Stapelabzug im Nutzerdialog. **Und keine Adresse aus dem Code:** `field` und
`constraint` einer `ValidationError` sagen dem Programm, welches Feld und
welche Regel; dem Kunden sagen sie nichts („Feld: bought_on / Bedingung:
format" unter einem Satz, der längst vom Datum spricht — Lagerdurchsicht
19.09.2026). `spoken_values` lässt sie weg; die Übersetzung der Adresse ist
der Cursor im Feld (`NewFilamentDialog.focus_field`). Titel und Detail stehen
in zwei Zeilen (`problem_text`), nie als „Titel.: Detail". Und wer eine
Handlung im Satz nennt („Laden Sie den Stand neu"), bietet genau sie als
Knopf an — `RELOAD`, nicht *Eingabe korrigieren*, das an dieser Eingabe
nichts ändern könnte.

**Ein Wort, das nur ein Konstrukteur kennt, steht nicht dort, wo ein Neuling es
lesen muss.** Gemessen am 14.09.2026 über alle Oberflächentexte
(Bedienweg-Durchsicht): *Manifold*, *B-Rep*, *Tessellation*, *Vertex*, *Fillet*
kamen nicht vor — zehn andere schon, und sie sind getauscht: **Richtung**
statt Normale (44 Operationen führten *Normale X/Y/Z*, bei *Bohrung setzen*
auf der Vorderseite), **Außenseiten angleichen** statt Normalen
vereinheitlichen (der Fortschrittsschritt bei jedem Import), **geschlossen**
statt wasserdicht (in der Mehrzahl hieß dieselbe Eigenschaft längst „1/2
geschlossen"), **auf einem Raster** statt Voxelstufe, **Vereinigen oder
Abziehen** statt boolesch, **jede Kante sichtbar** statt Facetten, **ohne
Zufall** statt deterministisch. Was bleibt, bleibt begründet: *Slot* im
3MF-Weg gehört zum Format und liegt bei RM-084; *Extrusionsbreite* an der
Wandstärkenleiter bleibt, weil das Handbuch-Glossar genau dieses Wort
definiert — es mit *Bahnbreite* der Druckeinstellungen zu vereinheitlichen
gehört ebenfalls zu RM-084; *Rasterweite* als Feldname hinter der Klappe
erklärt sich am Satz daneben. Wer einen neuen Text schreibt, sucht das Wort, das der Kunde in
seinem Slicer liest — und `test_translations` findet den alten Schlüssel, der
dann hinausmuss.

**Ein Text, der eine Grenze beschreibt, altert mit der Grenze.** Für einen
einzigen solchen Satz waren es drei Stellen im Code, zweimal fünf Kataloge,
eine Website-Seite und der Vertragstext.

Wer eine Fähigkeit hinzufügt, sucht deshalb **vorher** die Sätze, die ihre
Abwesenheit versprechen. Der Suchbegriff ist die Verneinung dessen, was man
baut („nichts", „nie", „kein", „ohne") — nicht der Name der neuen Sache, denn
den kennen die alten Texte ja gerade nicht.

**Drei Wächter halten das seit der Durchsicht 0.5.1**, alle ohne Fenster:
`test_wording::test_no_customer_text_uses_a_designer_word` (kuratierte
Wortliste für Quelle und englische Übersetzung, Ausnahmen mit Grund),
`test_wording::test_a_quoted_control_is_named_as_the_control_says` (ein Satz,
der „Werkzeuge prüfen“ zitiert, zitiert in jeder Sprache den Knopf) und
`test_finding_ways.py` (jede Warnung und jeder Fehler des Kerns trägt einen Weg
oder steht mit Grund in `OHNE_KNOPF`). Wer einen Befund baut, gibt ihm
`suggestions=`; *Eingabe korrigieren* nur an Befunden einer Operation — die
Auswertung trägt die Schrittkennung nach, und der Bericht blendet Handlungen
aus, die ohne Schritt oder Körper nichts täten (`panels.actions_for_document`,
`tests/test_finding_actions.py`).

Und beim Tauschen eines Katalogtexts muss der **alte Schlüssel hinaus**:
`test_every_text_is_translated` prüft beide Richtungen und meldet ihn sonst als
„no longer used". Zwei gegenläufige Zusicherungen decken einander.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## Texte, die der Kunde liest

Der Abschnitt ist bei der Verdichtung neu hinzugekommen. Er übernimmt Roberts
Vorgaben aus den Erinnerungen, die bis dahin nur auf einer Maschine lagen, damit
sie überall und für Codex gelten. Anlässe und Wortlaut:

- **Kurz:** Robert, 15.09.2026 — „achja kürzere Texte, aber trotzdem verständlich
  wäre auch besser bei allem in der app.“ Gemeint waren Befunde im Prüfbericht,
  graue Zeilen des Merkmalspanels, Absagesätze und Parameterhilfen. Beispiel:
  „Der Körper zerfällt nach diesem Schritt in lose Teile. Strg+Z nimmt ihn
  zurück.“ sagt in 13 Wörtern, wofür der alte Satz 20 brauchte.
- **Nicht nach KI klingen:** Robert, 31.08.2026, zu einem Mailentwurf — „und auch
  alles mehr so schreiben dass es nicht nach ki klingt“ und „was er geschrieben
  hat brauchen wir auch nicht wiederholen“. Die sieben Merkmale fanden sich alle
  im verworfenen Entwurf; die Gedankenstriche im Übermaß sind die auffälligste
  Signatur des Modells.
- **„Version“:** Robert, 03.09.2026, zu einem Mailentwurf — „statt Fassungen
  versionen“. Intern „Fassung“ umzubenennen wäre eine Massenänderung ohne
  Nutzen.
- **Zahlen:** Aus dem Changelog-Entwurf für 0.3.1 flog „Zwölf gesperrte Knöpfe
  in neun Fenstern nennen jetzt am Knopf, was ihnen fehlt“ — richtig gezählt,
  aber der Kunde liest daraus, dass bis gestern zwölf Knöpfe wortlos grau waren.
  Nach derselben Linie wurde „von zwölf Befunden ohne Handlung sind zwei
  geblieben“ zu „der Befund zeigt auf seinen Körper und trägt seine Handlung,
  und wo keine steht, ist er ein reiner Hinweis“ — die nützlichere Aussage. Die
  entscheidende Frage: Ist die Zahl an etwas gemessen, das dem Kunden gehört?
- **Druckzeit:** Robert, 26.09.2026, zu „Eine Schüssel am Centauri Carbon 2
  braucht 18 statt 31 Stunden“ — „40 Prozent kürzer finde ich aber besser als
  die zeit“. Stunden gehören zu einem Modell, das der Leser nicht kennt; ein
  Anteil überträgt sich auf den eigenen Druck.
- **Neuerungen-Seite:** Robert, 24.09.2026, in der Website-Durchsicht — „die
  seite changelog passt, mit der bin ich sehr zufrieden.“ Die Startseite war
  vorher „ein bisschen unübersichtlich geworden“ (verschieden hohe Karten, Kästen
  neben leeren Flächen, dieselbe Aussage in zwei Abschnitten).

## Zahlen

**Eine Zahl, eine Schreibweise — in beiden Richtungen.**

*Hinaus:* Der Kern rechnet und schreibt mit Punkt, das ist richtig; dort ist
eine Zahl ein Wert. Wer sie **anzeigt**, schickt sie durch `localised`
(`app/ui/labels.py`) — und setzt umgekehrt auch kein Komma fest ein.
`test_no_number_reaches_the_user_past_the_localisation` prüft jede Datei unter
`app/ui`; wer eine Kommazahl in einen Anzeigetext schreibt, kommt daran nicht
vorbei.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Zwei Prüfungen von zwei Seiten.** Die Regelprüfung liest den Quelltext und
sieht f-Strings mit Formatangabe — nicht `"%.2f" %`, nicht `.format()`, nicht
ein nacktes `f"{wert}"` auf einer Fließkommazahl.
`test_no_visible_text_writes_a_decimal_point` schaut deshalb auf das Ergebnis:
Fenster mit Modell, Druckeinstellungen und fünf Operationsdialoge aufgebaut,
jeden sichtbaren Text und jeden Tooltip gelesen, und im deutschen Fenster darf
dort keine Zahl mit Punkt stehen. Über vierhundert Texte, und die Wächter der
Suche lassen Pfade, Adressen und Versionsnummern durch.

**Die Einheit gehört in den Wert, nicht in den Satz** — und nicht in die
Beschriftung. Ein Befundwert trägt sie über `value_text`
(`_VALUE_UNITS` in `app/ui/labels.py`), nicht über `value_label`: „Übermaß
(mm): 12,4" konnte nicht umschalten, und bei einem Volumen war es falsch, weil
der Wert selbst zwischen mm³ und cm³ wechselt.

**Die Einheit gehört in den Wert, nicht in den Satz.** Länge, Volumen *und
Fläche* folgen der Umschaltung aus §19.3 — `labels.length`, `labels.volume`,
`labels.area`. Wer sie selbst anschreibt, baut eine Zeile, die in Zoll nicht
sprechen kann — auch als *übersetzter* Satz im Katalog, mit der Einheit darin.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

*Herein:* Ein Zahlenfeld ist eine `NumberSpin` (oder eine `LengthSpin`
darauf), **kein nacktes `QDoubleSpinBox`**. Qt liest den Punkt in einer
deutschen Anzeigesprache als Tausendertrennung: Wer „12.5" tippte, bekam 125 —
ohne Fehler, ohne Rückfrage, ein Teil zehnmal zu groß.

**Die Leseregel von `NumberSpin`: das letzte Trennzeichen ist das
Dezimaltrennzeichen, alle davor sind Tausendertrennungen.** Damit liest jedes
Feld „12.5", „12,5", „1.000,50", „1,000.50" und „1.234.567,89" richtig, in jeder
Sprache. Zweideutig bleibt allein eine Zahl *ohne* Nachkomma („1.000" ist nach
der Regel eins) — und was das Feld gelesen hat, steht danach darin.

**Der getippte Text wird dabei nicht angefasst.** Der erste Anlauf tauschte das
Trennzeichen und gab den getauschten Text an Qt zurück; Qt übernahm ihn ins
Feld, und damit war die Absicht beim zweiten Tastendruck entschieden — aus
„1.000,50" wurde 100,50, derselbe Fehler um den Faktor tausend, nur in der
anderen Richtung. `validate` prüft deshalb gegen **beide** Lesarten und gibt den
Text unverändert zurück; gelesen wird beim Übernehmen in `valueFromText`.

Als Typprüfung bleibt `QDoubleSpinBox` richtig — `isinstance` fragt „ist das ein
Dezimalfeld", nicht „ist das unsere Unterklasse".

**Eine Grenze lehnt ab, sie kürzt nicht**, weil Qt sonst still kürzt: An einem
Feld mit Obergrenze 100 verwirft es die Null von „150“, und die Eingabetaste
übernimmt 15. **Die Ablehnung in einer Maßgruppe ist eine eigene Sperre**
(`QuietHost.refuse_fields`): Jeder neue Vorschauauftrag, schon ein Griffzug,
der ein anderes Feld zurückschreibt, setzte den Sperrgrund des Trägers neu und
gab *Übernehmen* frei, während der abgelehnte Ausdruck sichtbar stehen blieb.

## Gestufte Tiefe

**Und was gerade nichts tut, steht nicht da.** Ein Feld mit `depends_on`,
dessen Bedingung nicht gilt, verschwindet aus dem Dialog und kommt mit ihr
wieder (`OperationDialog._couple_dependent_fields`; Entscheidung Robert,
14.09.2026, RM-171). Bis dahin blieb es grau stehen, mit dem Satz, woran es
liegt — begründet mit „wer es verschwinden sähe, suchte es". Der Preis stand in
der Sonde vom 13.09.: *Grundform hochziehen* trug bei einem Rechteck vier tote
Zeilen vorn, die Hälfte seiner Vorderseite. Die Zeile erscheint mit der
Grundform, die sie braucht, und nicht heimlich. Gesperrt und begründet bleibt
sie dahinter, damit kein verborgenes Feld den Fokus bekommt; der Dialog wächst
und schrumpft mit (`adjustSize`, nur wenn sich eine Zeile bewegt hat).
`test_a_rectangle_shows_only_the_rows_a_rectangle_has` hält die vier fest.

## Was eine Vorschau nicht zeigen kann, sagt sie

**Und was eine Vorschau nicht zeigen kann, sagt sie.** Über drei Lagen stand
dasselbe Band „Vorschau — noch nicht übernommen": über einer Bohrung, über
einem Verschieben um null und über einem Teilen, das nichts teilt. Nur beim
ersten war es wahr (gemessen am 13.09.2026 über alle 110 Operationen: 62
mit Bild, 17 mit leerer Differenz, 11 ohne Differenz). Seither trägt das Band
den Grund aus dem Kern (`Session.preview_async(explained=…)`, „Keine
Vorschau: Diese Ebene teilt das Objekt nicht."), sagt bei leerer Differenz
„am Volumen ändert sich nichts" und nach 0,2 s ohne Ergebnis „wird
gerechnet …" (§2.8). Ein leeres Bild ohne Satz sieht aus wie „nichts ändert
sich" — und das ist die eine Rückmeldung, die nie stimmt.

**Das Band nennt, was sich ändert, und sonst nichts** (RM-516, Durchsicht der
Oberfläche 0.5.2, Befund B9). Über einer verschobenen Bohrung
(guide-drill-a-hole-8) standen sieben Zeilen: Ziel, betroffene Körper,
„Körperzahl: 1 → 1", „Außenmaß … 80,000 × 50,000 × 8,000 mm → 80,000 ×
50,000 × 8,000 mm", zwei Grundlagensätze und „Warnungen oder Fehler: 0
vorher, 0 nachher". Das Außenmaß schrieb drei Nachkommastellen und ein festes
„mm" — in Zoll falsch. Seither steht unter dem Titel eine Zeile („Bohrung
setzen · plate_holes · Druckbefunde unverändert"), am echten Fenster gemessen
zwei Zeilen statt acht. Der Vertrag aus RM-090 bleibt: Was sich an Außenmaß,
Körperzahl und Material ändert, steht mit Vorher und Nachher da; was bleibt,
ist mit dem Körpernamen gesagt. Dass Druckbefunde noch nicht geprüft oder
nicht vollständig geprüft sind, sagt dieselbe Zeile, und „behoben" heißt
weiterhin nur, was eine vollständige Gegenprüfung nicht mehr findet. Neue
und behobene Befunde teilen sich höchstens drei Zeilen, die letzte zählt den
Rest — vorher je vier und je eine Zählzeile.

## Ein Feld ohne Namen ist für einen Bildschirmleser ein leeres Kästchen

Die Regel „jedes Feld sagt, was es tut" nannte zwei Orte — die
sechsundfünfzig Felder der Druckeinstellungen und die Parameter des
Operationsdialogs. Es gibt einen **dritten**: die Schnellbearbeitung am
Merkmal. Dort standen zehn Bedienelemente mit leerem ``accessibleName``,
darunter zweimal X, Y und Z — einmal für *Merkmal verschieben*, einmal für
*verdoppeln*. Vorgelesen wurde „Drehfeld, 0,00", sechsmal hintereinander
(gemessen 09.09.2026 an einer gewählten Bohrung).

Ein `QFormLayout` legt die Beschriftung **neben** das Feld und verbindet die
beiden nicht; wer sie nicht sieht, hat kein Feld, sondern ein Kästchen. Also:
`label.setBuddy(editor)` **und** ein Name am Feld selbst — `setBuddy` allein
hängt nur das Tastenkürzel an die Beschriftung und wird von den Vorlesern
verschieden ausgewertet.

**Der Name trägt die Handlung mit**, nicht nur die Beschriftung:
„Durchmesser" allein sagt nicht, welcher, denn an einer Bohrung stehen vier
Handlungen mit je eigenen Feldern. `tests/test_feature_panel.py` prüft
beides — keinen leeren Namen, und keine zwei gleichen.

Die allgemeine Frage dahinter, weil dieselbe Lücke an jedem neuen Ort mit
Feldern entsteht: **Wo Felder stehen, tragen sie ihren Namen — und „wo" heißt
jede Stelle, nicht die zwei, die man gerade im Kopf hat.**

Drei Formen derselben Lücke, alle drei in der Durchsicht 0.5.0 gefunden:

- **Wiederholte Zeilen nennen, wozu sie gehören.** Im Rezeptdialog trug jeder
  Parameter sieben Felder mit denselben Namen („Beschriftung", „Einheit" …);
  der Name trägt deshalb „· {Parameter}", wie die Merkmalsfelder die Handlung.
- **`setAccessibleName` überschreibt den sichtbaren Text.** Ein Haken, dessen
  Text der Parametername ist, wurde mit „Diesen Wert freigeben" benannt und
  verlor damit genau die Auskunft, welcher. Der Name bleibt der sichtbare
  Text; der erklärende Satz gehört in `setAccessibleDescription`.
- **Ein Zeichen als zweite Kodierung braucht ein Wort als Namen.** „+", „-",
  „?" neben der Farbe lesen sich für einen Vorleser als „plus", „minus",
  „Fragezeichen" — `setAccessibleName` und Tooltip sagen „Vorhanden",
  „Fehlt", „Wird gesucht …".

## Ein Haken in einer Formularzeile antwortet auf der ganzen Zeile

`QCheckBox` ohne Text nimmt nur Klicks auf sein Kästchen an — Qt prüft in
`hitButton` gegen Kästchen und Text, und ohne Text bleibt das Kästchen. In
einer Formularzeile füllt das Feld aber die ganze Spalte: **14 × 14
Bildpunkte waren heiß in einem Feld von 241 × 14** (Aushöhlen, „Oben öffnen",
gemessen 13.09.2026), und die Beschriftung links davon tat nichts. Für den
Kunden hieß das „die Checkbox reagiert ab und zu nicht" — je nachdem, wo der
Klick landete.

Also: In einer Formularzeile ist ein Haken ein `labels.RowCheckBox` (das
ganze Feld trifft), und seine Beschriftung bekommt `labels.caption_toggles`
(ein Klick auf das Wort schaltet; wer mit gehaltener Taste hinausfährt und
daneben loslässt, schaltet nichts — wie am Kästchen selbst). Vier Bauorte hatten den nackten
`QCheckBox`: Operationsdialog, Merkmalfenster, Druckeinstellungen (zweimal).
`tests/test_operation_ui.py` prüft die Klickfläche an einer echten Zeile und
die Bauart über alle `bool`-Parameter des Registers.

**Und die Zeile ist so hoch wie ihre Nachbarn.** Die Breite war die eine
Hälfte von „ab und zu"; die andere zeigte sich erst auf der echten Plattform
mit dem Stylesheet (14.09.2026): Die Zahlenfelder des Aushöhlen-Dialogs sind
31 Punkte hoch, der Haken ohne Text war 12 — `childAt` acht Punkte über oder
unter seiner Mitte: „nichts". Wer nach Augenmaß in die Zeile klickte, traf in
zwei von drei Fällen ins Leere. `RowCheckBox.sizeHint` meldet deshalb die
Höhe eines Eingabefelds unter dem geltenden Stil (`labels.input_field_height`,
an einem Drehfeld gemessen statt aus Padding und Rahmen nachgerechnet); das
Kästchen zeichnet der Stil mittig. Offscreen sieht man den Unterschied nicht —
dort gibt es kein Stylesheet und keine Schrift (siehe „Die Suite fährt ohne
Stylesheet" in `tests.md`); die Sonde dazu fährt auf der echten Plattform mit
`WA_DontShowOnScreen`.

## PySide legt seine Qt-Typen an, bevor das erste Fenster entsteht

**Der Filter ist der Haken selbst — und PySide legt seine Typen vollständig
an, bevor das erste Fenster entsteht.** Die erste Fassung hängte ein eigenes
`QObject` als Filter an die Beschriftung und importierte `QMouseEvent` für
den `isinstance`-Test; `tests/test_filament_picker.py` riss danach
deterministisch mit `0xc0000374` im `gc.collect` des Teardowns. Bisektiert am
14.09.2026 bis auf den ungenutzten Import — und am 15.09.2026 noch einmal
auf `QSpinBox` in `panels.py`, derselbe Riss, wobei derselbe Name über
`QtWidgets.QSpinBox` gelesen grün war. **Die Ursache ist nicht der Name,
sondern wann PySide 6.11.2 den Typ anlegt:** Mit der Vorgabe entsteht ein
Typ erst beim ersten Zugriff, welche Typen wann entstehen hängt damit an der
Importreihenfolge der Oberfläche, und irgendwo darin liegt ein Riss beim
Abbau. Mit `PYSIDE6_OPTION_LAZY=0` laufen **beide** Stände durch; der Preis
sind 60 ms beim PySide-Import und 6 MB.

Die Variable wirkt nur, bevor `PySide6` zum ersten Mal geladen wird.
`app/ui/__init__.py` setzt sie beim Betreten des Pakets, `app.py` lädt das
Paket als **ersten** Import (das gebaute Paket startet die Datei als Skript,
und `app.ui` wäre sonst erst hinter `PySide6` an der Reihe), und
`tests/conftest.py` lädt es vor jeder Testdatei.
`test_the_interface_loads_qt_types_before_the_first_window` in
`tests/test_language_rules.py` hält alle drei Stellen und läuft vor jedem
Commit an `app/`. Der `QMouseEvent`-Wächter von damals ist gefallen — er hielt
ein Symptom fern, und die Ursache ist behoben. Was von der Lehre bleibt:
**Bei einem Riss dieser Gestalt zuerst die Importe verdächtigen, dann den
Code** — und die Reichweite ist der Prozess, nicht das Symbol.

## Die Tabulatortaste geht denselben Weg wie das Auge

**Ein Widget im Layout zu verschieben verschiebt es nicht in der Fokuskette.**
Die folgt der Reihenfolge, in der die Widgets **entstanden** sind; wer ein
Bedienelement im Aufbau anlegt und später ans Ende hängt, hat es sichtbar unten
und in der Kette oben. Im Merkmalfenster traf es *Im Bild einstellen*: Es steht
über dem Haken „Auf alle N gleichartigen anwenden" und kam mit der
Tabulatortaste **nach** ihm (gemessen am gebauten Fenster, 13.09.2026).

Das Mittel ist `QWidget.setTabOrder`, von hinten aufgezogen — letztes Feld →
die Halte unten in ihrer Layoutreihenfolge (`FeaturePanel._settle_tab_order`).
Unsichtbare und gesperrte Halte übergeht Qt von selbst, ein Sonderfall für den
Haken ist also keiner nötig. Geprüft wird die **Kette gegen das Layout** und
nicht gegen Bildpunkte: Was das Auge sieht, sagt das Layout; offscreen wäre
jede Höhe erfunden (`test_the_tab_key_goes_down_the_panel_like_the_eye`).

## Ein Rad über einem Feld ohne Fokus rollt die Seite

In einem rollenden Fenster liegt der Zeiger beim Rollen zwangsläufig über
Feldern, und Qt gibt eine Radraste über einem Drehfeld dem Feld: Im
Merkmalfenster sprangen Werte, wo die Seite rollen sollte (Robert,
16.09.2026: „hier sollten wir erst reinklicken müssen").
`labels.wheel_needs_focus` setzt das Feld auf `StrongFocus` — das Rad nimmt
damit keinen Fokus mehr — und reicht eine Raste ohne Fokus weiter: ignoriert
heißt bei Qt an das Elternteil, also an den Rollbereich. Wer ins Feld klickt,
dreht danach wie gewohnt. Gilt für jedes Dreh- und Auswahlfeld im Merkmal-
und im Parameterfenster; wer ein Feld in einen Rollbereich setzt, ruft es auf.

## Eine Adresse im Browser öffnet `dialogs.open_link`

`QDesktopServices.openUrl` meldet `False`, wenn kein Programm die Adresse
annimmt — und fünf Stellen lasen das nicht: Der Klick tat nichts, ohne ein
Wort (Regel 17). `open_link(address, parent)` legt die Adresse dann in die
Zwischenablage und nennt sie im Satz. Wer `openUrl` direkt ruft, liest den
Rückgabewert und hat einen eigenen Rückweg (Aktivierung, Mail, Förderung).
Eine Funktion, die unmittelbar an `clicked` hängt, bekommt keinen
Parameter mit Vorgabe: PySide reicht ihm den `checked`-Wert hinein.

## Ein Zustand darf die Farbe wechseln, nicht die Rahmenbreite

Gilt für jedes Eingabefeld, und gebrochen hat es genau **eines**: die
Combobox. `QComboBox:focus` gab dem Rahmen einen zweiten Punkt und nahm ihn
über den Innenabstand wieder weg, damit die Box beim Fokussieren nicht
springt — dieselbe Bauart wie bei Knopf und Werkzeugknopf, und dort richtig.

Qt leitet die Höhe des Aufklappmenüs aber aus dem **Innenrechteck** der
Combobox ab (`SC_ComboBoxListBoxPopup` über den `QStyleSheetStyle`). Mit dem
zweiten Rahmenpunkt verliert es zwei Punkte, kippt damit in den Rollbetrieb
und verliert an dessen zwei Pfeilen weitere zehn. Zwölf Punkte sind ein halber
Eintrag, und getroffen hat es **jede** Combobox mit Tastaturfokus, also jede,
die man anklickt. Ohne Fokus rechnet Qt richtig; das ist der Grund, aus dem
eine Messung ohne `setFocus` nichts findet.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Drei Auswege sind gemessen und untauglich: `:on` (der Pseudozustand für das
offene Menü) wird erst nach der Höhenrechnung gesetzt, `outline` zeichnet Qt
an einer Combobox nur einen Punkt breit, und ein Rahmen, der in einen
`margin` hineinwächst, vergrößert stattdessen das Feld. Es bleibt: **konstante
Breite, wechselnde Farbe und Strichart.**

Der Ruherahmen ist deshalb zwei Punkte breit wie der Fokusrahmen, und der
Fokus sagt es über **Farbe und Strichart**: Der Ring bleibt zwei Punkte breit,
wechselt auf `accent_line` und wird gestrichelt (`style.py`). Nur die Farbe
wechseln zu lassen, mit dem Argument, ein Punkt Rahmenbreite sei ohnehin keine
wahrnehmbare Kodierung gewesen, trägt nicht: Regel 18 verlangt die zweite
Kodierung, nicht den Nachweis, dass die alte auch keine war.

`tests/test_style.py` hält beide Enden: eine Messung am gebauten Fenster
(`test_an_open_combo_box_shows_every_entry_it_has`, samt Gegenprobe mit der
alten Regel, die fallen **muss**) und eine am Text der Regel
(`test_the_focus_ring_never_changes_the_size_of_a_field`).

**Und der Ruhezustand behält die volle Linienfarbe.** Der doppelt breite
Rahmen legte es nahe, ihn zur Feldfläche hin zu dämpfen, damit er so leise
wirkt wie der einfache vorher. Im Bild sah das richtig aus und war gemessen
falsch — unter den 3,0, die WCAG 1.4.11 für die Umrandung eines Bedienelements
verlangt — dieselbe Grenze, an der `style.py` auch den Fokusring misst.

Die Fläche fängt das nicht auf: **Der Rahmen ist die einzige Kante, die ein
Feld hat.** `test_a_field_keeps_the_edge_that_is_its_only_one` prüft gegen die
Linienfarbe des Themas und nicht gegen 3,0 — was diese Farbe leistet, ist eine
Frage an das Thema (im hellen bringt sie seit je nur 2,43), dass der Rahmen sie
nicht unterschreitet, eine an das Stylesheet.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## Barrierefreiheit

Die Grauleiter der Ersatzfarben stand im Original mitten im Punkt „Dasselbe
Problem bietet dieselben Handlungen“; dieser Punkt steht wörtlich in
`regel-fenster.md` unter „Der Prüfbericht“.

- **Aber auch keine Bedeutung ohne Farbe, wo Farbe die Sache ist.** Ein
  Materialslot ohne eigene Farbe darf in der Ansicht nicht die Körperfarbe
  tragen — sonst ist das Bemalen im Bild folgenlos. `theme.slot_colour` gibt
  die Ersatzfarbe (sieben Einträge; Slot 0 ist das unbemalte Teil und bekommt
  `None`); im **Dokument** steht sie nicht, denn keine Farbe zu haben ist ein
  Zustand, den „Slot zuweisen" auflöst. Die Zahl daneben bleibt: Die
  Pinselleiste zeigt Farbfeld **und** Name, „neu" für einen Slot, den der
  gewählte Körper noch nicht hat.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

- Differenzansicht in Blau/Orange als Vorgabe, nicht Rot/Grün.
- Analysekarten mit wahrnehmungsgleicher Palette (Viridis-Art), kein
  Regenbogen — der erzeugt Kanten, wo keine sind.

**Die Anzeigeeinheit ist ein Zustand, wie die Sprache einer ist**
(`labels.set_display_unit`, `display_unit()`). Sie durch die Konstruktoren zu
reichen war der Weg dorthin und hatte elf von vierzehn Ausgaben vergessen:
`labels.length` rufen Funktionen **ohne Widget** — die Merkmalsbeschriftung
entsteht in der Überlagerung, im Objektbaum und in der Statusleiste. Ein
ausdrücklich übergebenes Argument gewinnt weiter; das ist kein zweites
Verzeichnis, sondern ein Vorrang.

Zwei Grenzen, und beide sind der Grund, warum der Umbau sicher ist. **Was in
ein Eingabefeld geschrieben wird, bleibt in Millimetern**: `measured_expression`
belegt das Maßfeld einer Skizzenbedingung vor, und dort wäre eine umgerechnete
Zahl ein Datenfehler und kein Anzeigefehler. Und **ein Suffix allein zu
tauschen ist falsch**: Ein Feld mit „in" über einem Wert von 20 mm behauptet
20 Zoll. Eingabefelder umzustellen heißt Wert **und** Grenzen in beide
Richtungen umzurechnen, ohne einen Parameterausdruck anzufassen — ein eigener
Schritt. Dieselbe Grenze gilt beim **Umschalten in den Ausdrucksmodus**:
`ValueField` belegte ihn aus dem Drehfeld vor, also aus der Anzeige, und in
Zoll stand „=1.5748" dort, wo 40 mm gemeint waren. Der Hinweis darunter
beschriftet mit `entry.unit` und las „= 1.5748 mm" — eine Anzeige, die ihren
eigenen Fehler bezeugt. `_number()` ist die eine Quelle für beide Stellen.

Drei weitere Lehren liegen **hinter** dem Umbau, denn sie betreffen nicht das
Umstellen, sondern das Lesen an ihm vorbei:

* **`valueChanged` ist eine Lesestelle, die die Umrechnung überspringt.** Der
  Docstring von `LengthSpin` versprach, es gebe keine — „`value()` heißt hier
  nicht mehr, was der Kern will". Qts Signal trägt aber genau die Zahl aus dem
  Feld, und dafür muss niemand `value()` schreiben — und was es weiterreicht,
  kann bis in die **Geometrie des Dokuments** gelangen. `valueChangedMm` ist
  dieselbe Nachricht in der Einheit des Kerns; `valueChanged` bleibt für alles,
  was den Wert fallen lässt und selbst `value_mm()` liest.
* **Ein Einheitenwechsel meldet nichts.** `refresh_unit` legte die neue Spanne,
  während noch der Wert der alten stand — Qt klemmt ihn und feuert damit. In
  Millimetern ändert sich beim Wechsel nichts, also gibt es nichts zu melden:
  der Tausch läuft unter `blockSignals`.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)
* **Gelesen wird über die Leiste, nicht an ihr vorbei.** `SculptBar.values()`
  beantwortete die Frage des Zugs mit den richtigen Einheiten und hatte
  **keinen Aufrufer**, während das Fenster dieselben vier Werte aus den Widgets
  neu zusammenstellte. Zwei Wege zu derselben Auskunft sind einer zu viel, und
  welcher benutzt wird, entscheidet nicht der Vorsatz. Der Rückgabetyp heißt
  deshalb `StrokeValues` und nicht `dict[str, object]`: Mit Namen im Typ prüft
  mypy das Auspacken, ohne sie nimmt es jede Verwechslung hin.

Und der Grund, aus dem all das durch eine grüne Suite kam: **kein Test fuhr
eine Leiste je in Zoll.** Die Umschaltung war an ihren Anzeigen geprüft und an
keiner Handlung. `tests/test_sculpt_session.py` fährt jetzt einen Pinselzug in
Zoll bis in den `Stroke` hinein — der eine Test, der alle drei Funde gefangen
hätte.

## Tests

**Ein modaler Dialog auf einem Startweg hält die ganze Suite an.**
`QDialog.exec()` wartet offscreen auf einen Klick, den es nie gibt — und die CI
bis zu ihrem Sechs-Stunden-Limit.

Das Tückische ist nicht der Fehler, sondern seine Anzeige: **Die Suite wird
nicht rot, sie steht.** Kein Name, kein Fehlschlag, nur ein Protokoll, das
nicht mehr wächst; `py-spy dump --native` nennt die Stelle wörtlich.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Wer einen Dialog auf einen Weg setzt, den ein Test geht, fragt vorher
`QT_QPA_PLATFORM != "offscreen"` — dasselbe Muster wie
`motion.animations_enabled`, und aus demselben Grund: Wer offscreen läuft,
prüft Verhalten und wird nicht bedient. Der Merker eines solchen Hinweises
wird dabei **nicht** gesetzt; sonst hätte der Kunde ihn nie gesehen und bekäme
ihn trotzdem nie wieder.

**Der Absturzbericht ist der Dialog, den man am wenigsten erwartet** — und der
gefährlichste: `_on_ask` macht aus **jeder** Ausnahme aus einem Fragedialog
einen `InternalError`, und `report_error` öffnete ihn modal. Eine
fehlgeschlagene Zusicherung in einem Testrückruf war damit kein rotes Wort,
sondern ein stehender Prozess — der Hänger in `test_ui.py`, den die
Suite-Beschreibung seit dem 16.08.2026 als „nativen Abriss" führte, war zur
Hälfte das (21.09.2026). Offscreen geht der Bericht seither ins Protokoll
(`_log.error`) und öffnet nichts.

**Ein Widget braucht die `QApplication` in der Signatur, nicht im Glück.** Wer
ein Widget ohne sie baut, bringt den ganzen Lauf mit 0xC0000409 um — ohne ein
Wort Ausgabe, nur mit einem Rückgabewert. In der vollen Datei fällt das nicht
auf, weil ein früherer Test die Anwendung schon gebaut hat; ob das passiert,
entscheidet `pytest-randomly`. Also nimmt jeder Test, der ein Widget anfasst,
`qt_app` oder eine Fixture, die darauf aufbaut — auch der, der scheinbar nur
eine Zeichenkette prüft.
