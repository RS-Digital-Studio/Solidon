---
paths:
  - "app/ui/**/*.py"
---

# Regeln für die Oberfläche

PySide6. Die Oberfläche darf `core` benutzen, nie umgekehrt. Sie rechnet keine
Geometrie und ändert keine — sie ruft Ops auf.

## Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op rücknehmbar, jeder
Wert nachträglich änderbar. Praktisch heißt das: **keine Bestätigungsdialoge
vor rücknehmbaren Handlungen**, kein „Möchten Sie wirklich", keine Sackgassen
(Regel 19). Die ausdrücklich gewünschte Ausnahme ist das Löschen im Verlauf:
Die Nachfrage nennt mitbetroffene Schritte und den Rückweg über Strg+Z.

## Texte

Keine feste Zeichenkette in der Oberfläche — alles über `tr()`, deutsche
Quelle, und jeder Katalog aus `app/i18n/locales/` zieht nach. **Das gilt auch
für Auswahlwerte**: `raised`, `flat`, `linear` sind
Schlüssel und keine Beschriftungen. Der Name steht in `_CHOICE_NAMES`
(`app/ui/labels.py`), und `tests/test_translations.py` lässt nur durch, was
sein eigener Name ist — M4, 6x3, mm, x, DejaVu Sans.

**Eine Tabelle, und Auswahlwerte stehen an zwei Stellen.** Die
Druckeinstellungen führen ihre sechsundfünfzig Felder in einer eigenen Liste
(`print_settings_dialog.FIELDS`), und dort stand auch eine zweite
Namenstabelle mit einer gleichnamigen `choice_label`-Funktion davor — die eine
verdeckte die andere. Beide beschrifteten dieselben Schlüssel und waren schon
auseinandergelaufen: `cubic` hieß hier „Würfelgitter" und dort „Würfel", `none`
hier „Ohne" und dort „Keine". Zwei Werte hatte keine von beiden, und im
deutschen Fenster stand „Wandbahnen: classic" und „arachne". Der Test prüft
deshalb **beide Feldquellen** gegen die eine Tabelle; wer eine dritte Liste von
Auswahlwerten anlegt, hängt sie dort ein.

Wo der englische Begriff der ist, unter dem der Kunde die Sache in seinem
Slicer wiederfindet, bleibt er stehen: `skirt`, `brim` und `raft` heißen so,
und die Felder daneben heißen „Skirt-Runden", „Brim-Breite",
„Raft-Schichten" — ein Wert, der anders heißt als sein Feld, ist eine Fährte
ins Nichts. Dasselbe gilt für Algorithmennamen (`gyroid`, `arachne`).

**Jedes Feld sagt, was es tut — und zwar alle.** Das gilt an zwei Orten: Die
sechsundfünfzig Felder der Druckeinstellungen tragen je einen `note`-Satz, die
582 Parameter der 95 Operationen ihren `doc`-Satz aus dem Register. Beide Male
hängt er an **beiden** Hälften der Zeile; im Operationsdialog holt
`QFormLayout.labelForField` die Beschriftung, die `addRow` aus der Zeichenkette
gebaut hat (`_explain` in `op_dialog.py`). Ist eine Zeile gesperrt, tragen beide
Hälften den *Grund* statt des Satzes — in ein ausgegrautes Feld zeigt niemand,
man zeigt auf das Wort davor.

Die sechsundfünfzig Felder der Druckeinstellungen tragen je einen `note`-Satz: nicht den Titel noch
einmal, sondern was passiert, wenn man den Wert bewegt („Rechnet die Außenwand
auf ihr Sollmaß statt auf die Bahnmitte. Für Passungen richtig, sonst
unnötig."). Der Satz gehört an **beide** Hälften der Zeile — `_editor` setzt
ihn am Eingabefeld, `_label` an der Beschriftung, denn wer eine Zeile nicht
versteht, zeigt auf das unverständliche Wort und nicht auf den Kasten daneben.
Dazu `statusTip` und `accessibleDescription`: die Statuszeile zeigt ihn ohne
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
Stapelabzug im Nutzerdialog.

**Ein Text, der eine Grenze beschreibt, altert mit der Grenze.** „Es wird
nichts geladen und nichts ersetzt" stand am Kästchen in den Einstellungen, am
Menüeintrag und im Docstring von `_check_for_updates` — richtig, solange der
Update-Weg wirklich nur ein Link war, und mit `download()` und
`start_installer()` still falsch geworden. Für diesen einen Satz waren es drei
Stellen im Code, zweimal fünf Kataloge, eine Website-Seite und der
Vertragstext.

Wer eine Fähigkeit hinzufügt, sucht deshalb **vorher** die Sätze, die ihre
Abwesenheit versprechen. Der Suchbegriff ist die Verneinung dessen, was man
baut („nichts", „nie", „kein", „ohne") — nicht der Name der neuen Sache, denn
den kennen die alten Texte ja gerade nicht.

Und beim Tauschen eines Katalogtexts muss der **alte Schlüssel hinaus**:
`test_every_text_is_translated` prüft beide Richtungen und meldet ihn sonst als
„no longer used". Zwei gegenläufige Zusicherungen decken einander — genau das
hat hier zweimal an einem Tag einen halben Umzug gefangen.

## Zahlen

**Eine Zahl, eine Schreibweise — in beiden Richtungen.**

*Hinaus:* Der Kern rechnet und schreibt mit Punkt, das ist richtig; dort ist
eine Zahl ein Wert. Wer sie **anzeigt**, schickt sie durch `localised`
(`app/ui/labels.py`). Neun Stellen taten das nicht, und keine war auf eine
Sprache beschränkt: Die Parameterleiste schrieb im deutschen Fenster
„12.50 mm" neben ein Eingabefeld mit „12,50", der Chat „+1.25 cm³", die
Kalibrierung „Spiel 0.25 mm". Zwei setzten umgekehrt das Komma fest ein und
zeigten im englischen Fenster „8,4 g". `test_no_number_reaches_the_user_past_
the_localisation` prüft jede Datei unter `app/ui`; wer eine Kommazahl in einen
Anzeigetext schreibt, kommt daran nicht vorbei.

**Zwei Prüfungen von zwei Seiten.** Die Regelprüfung liest den Quelltext und
sieht f-Strings mit Formatangabe — nicht `"%.2f" %`, nicht `.format()`, nicht
ein nacktes `f"{wert}"` auf einer Fließkommazahl.
`test_no_visible_text_writes_a_decimal_point` schaut deshalb auf das Ergebnis:
Fenster mit Modell, Druckeinstellungen und fünf Operationsdialoge aufgebaut,
jeden sichtbaren Text und jeden Tooltip gelesen, und im deutschen Fenster darf
dort keine Zahl mit Punkt stehen. Über vierhundert Texte, und die Wächter der
Suche lassen Pfade, Adressen und Versionsnummern durch.

`localised` tauscht **jeden** Punkt. Um eine Zahl darf es liegen, um einen
Pfad, eine Adresse oder eine Versionsnummer nie — dafür gibt es
`localised_value`, das prüft, ob überhaupt eine Zahl dasteht.

**Die Einheit gehört in den Wert, nicht in den Satz** — und nicht in die
Beschriftung. Ein Befundwert trägt sie über `value_text`
(`_VALUE_UNITS` in `app/ui/labels.py`), nicht über `value_label`: „Übermaß
(mm): 12,4" konnte nicht umschalten, und bei einem Volumen war es falsch, weil
der Wert selbst zwischen mm³ und cm³ wechselt.

**Die Einheit gehört in den Wert, nicht in den Satz.** Länge, Volumen *und
Fläche* folgen der Umschaltung aus §19.3 — `labels.length`, `labels.volume`,
`labels.area`. Wer sie selbst anschreibt, baut eine Zeile, die in Zoll nicht
sprechen kann: „Fläche an {object} — {area} mm², {side}" stand als
*übersetzter* Satz im Katalog, mit der Einheit darin, und die Schichtanalyse
schrieb `f"{layer.area:.0f} mm²"` neben ein `z {length(layer.z)}`, das
umschaltet.

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

## Rückmeldung und Fehlerbericht

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
  deshalb im Fenster und nicht im Dialog. `grab()` und nicht der Bildschirm:
  was daneben offen ist, geht den Support nichts an.
* **Der abgelegte Ordner ist ein Weg, kein Notausgang.** *Bericht ablegen*
  steht dauerhaft in der Knopfleiste (§37.2); *Selbst per E-Mail senden*
  erscheint erst, wenn ein Versand scheiterte — ein zweiter Weg neben einem
  Knopf, der gerade funktioniert, liest sich wie eine Warnung.

Die Sitzung wird für den Anhang **einmal** gespeichert und behalten: zweimal
hieße, dass die Vorschau eine andere Größe nennt als die Sendung trägt.

## Fenster

Höchstens drei sichtbare Zonen: links Objektbaum, Parameter und Verlauf als
einklappbare Abschnitte; Mitte der Viewport; rechts **entweder** Chat **oder**
Prüfbericht, umschaltbar und ganz ausblendbar. Die Umschaltung springt zum
Bericht, wenn eine Warnung entsteht.

Solange ein Beispielprojekt offen ist, hat die rechte Spalte einen dritten
Reiter: die Tour (`app/ui/tour.py`, Schritte in `app/core/tour.py`). Sie
erkennt getane Schritte über `projectChanged` am Dokument und Verlauf, „Weiter"
schaltet jeden Schritt auch ohne Erkennung — Angebot, keine Sperre. Der
Warnungssprung zum Bericht lässt der aktiven Tour den Reiter; jedes andere
Projekt räumt ihn weg. Die Erkennungswerte müssen zu `tools/make_examples.py`
passen — driftet beides, wird `tests/test_tour.py` rot.

**Keine Betriebsarten.** Kein Umschalten zwischen „Bearbeiten" und
„Konstruieren" — es gibt einen Zustand, und der ist die Szene.

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

**Und wo keiner gesetzt wird, setzt Qt selbst einen.** Das ist die stille
Hälfte derselben Regel, und sie ist die häufigere: `QDialog` macht beim
**ersten `show()`** den ersten Knopf mit `autoDefault` zum Default, gleich wo
er im Fenster sitzt. Er trägt damit die Akzentfarbe aus `QPushButton:default`
— aber **nicht** die halbfette Schrift, die `make_primary` am Widget setzt.
Übrig bleibt Bedeutung allein über Farbe, also Regel 18.

Gemessen am 30.08.2026 über vierzehn Dialoge: **vier** trugen einen
ausdrücklichen Hauptknopf, **neun** einen von Qt vergebenen. Drei davon saßen
auf „Schließen" (Kürzelfenster, Über, Änderungen) — dort ist der Akzent eine
Empfehlung, das Fenster zu verlassen. Der schlimmste Fall war der
Zusatzprogramme-Dialog: Unter seinen vierzig Knöpfen traf es Nummer eins, das
„Installieren" der **ersten Listenzeile**. Sechs Zeilen tragen denselben Text,
eine stand hervorgehoben da, und was wie eine Empfehlung aussah, war die
Reihenfolge im Layout.

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
  asked_for` am gebauten Fenster. Der zweite hat beim ersten Lauf sofort einen
  zehnten Fall gefunden, den die Handmessung nicht bauen konnte.

**Und ein typloses Stylesheet am Vorfahren nimmt ihm seine Farben.** Eine
Regel ohne Selektor — `setStyleSheet("background: #202225;")` an einer Karte,
einer Leiste, einem Rahmen — gilt für den Träger **und jeden Nachkommen** und
**ersetzt** dort die Regeln des Anwendungs-Stylesheets, statt sie zu ergänzen.
`QPushButton:default` greift dann nicht mehr, und weil diese Regel neben
`font-weight` auch `background` und `color` trägt, steht der Hauptknopf mit
Rahmen und **ohne lesbare Beschriftung** da.

Gemessen an einem Hauptknopf in vier Lagen, jeweils die häufigste Farbe seiner
Fläche im gerenderten Fenster:

| Was ein Stylesheet trägt | Füllung | |
|---|---|---|
| nichts | `#f0a54a` | färbt |
| die Eltern, typlos `background:` | `#202225` | färbt **nicht** |
| die Großeltern, typlos `background:` | `#202225` | färbt **nicht** — es wirkt über Ebenen |
| die Eltern, typlos `border:` | `#f0a54a` | färbt |
| die Eltern, typlos `color:` | `#f0a54a` | färbt, nur die Schrift wechselt |
| die Großeltern, `#nurIch { … }` | `#f0a54a` | färbt |

**Und nur für die Eigenschaften, die sie selbst setzt.** Das ist die Hälfte,
ohne die man an fünf Stellen sucht, an denen nichts ist: Ein typloses
`border:` — wie es `_flash` beim Aufblinken eines Bereichs setzt
(`main_window.py`) — nimmt dem Hauptknopf gar nichts, weil `QPushButton` im
Anwendungs-Stylesheet eine eigene `border`-Regel trägt und die gewinnt.
Gefährlich ist allein dieselbe Eigenschaft, die der Knopf braucht, und das ist
`background`.

**Und die Abhilfe steht in der letzten Zeile: Eine Regel mit Kennung trifft
nur ihr Ziel.** Wer einem Träger ein Stylesheet gibt, schreibt es an dessen
`objectName` und nicht typlos. Wo eine breite Regel bleiben muss, bekommt der
Hauptknopf darin seine Farben ausdrücklich (`#surveyNotice #surveyGive` in
`app/ui/survey.py`). `make_primary` bleibt in beiden Fällen — es rechnet die
Breite gegen die halbfette Schrift.

**Ein `QDialog` ist dabei nicht der Unterschied**, auch wenn es zuerst so
aussah: Ohne Stylesheet färbt der Knopf in einem schlichten `QWidget` genauso
wie im Dialog. Der falsche Schluss entstand an einem Vergleichsbild, in dem
**beide** Knöpfe unter einem typlosen Stylesheet hingen — und ein
Gegenbeispiel, das dieselbe Bedingung trägt wie der Fall, ist keines. Gefunden
hat den Fehler die Nachbarsitzung, die ihn nicht reproduzieren konnte.

**Gefunden hat den leeren Knopf kein Test, sondern ein Blick auf das Bild.**
Die zwei Klicktests auf ihm waren grün: Ein Knopf ohne sichtbare Beschriftung
nimmt Klicks entgegen wie jeder andere.

**Und er heißt nicht wie sein Werkzeug.** Der Umschalter der Werkzeugzeile
nennt das Werkzeug, der Knopf darin seine Handlung — „Trennen" oben, „Jetzt
trennen" unten. `tests/test_interface_limits.py` hält das fest.

## Ein Zustand darf die Farbe wechseln, nicht die Rahmenbreite

Gilt für jedes Eingabefeld, und gebrochen hat es genau **eines**: die
Combobox. `QComboBox:focus` gab dem Rahmen einen zweiten Punkt und nahm ihn
über den Innenabstand wieder weg, damit die Box beim Fokussieren nicht
springt — dieselbe Bauart wie bei Knopf und Werkzeugknopf, und dort richtig.

Qt leitet die Höhe des Aufklappmenüs aber aus dem **Innenrechteck** der
Combobox ab (`SC_ComboBoxListBoxPopup` über den `QStyleSheetStyle`). Mit dem
zweiten Rahmenpunkt verliert es zwei Punkte, kippt damit in den Rollbetrieb
und verliert an dessen zwei Pfeilen weitere zehn. Gemessen, dunkles Thema:

| Einträge | Platz | gebraucht |
|---|---|---|
| 2 | 36 px | 48 px |
| 3 | 60 px | 72 px |
| 5 | 108 px | 120 px |

Zwölf Punkte sind ein halber Eintrag. Im Bohrdialog stand unter dem
hervorgehobenen „Mündung" ein waagerecht durchgeschnittenes „Mitte" — und
getroffen hat es **jede** Combobox mit Tastaturfokus, also jede, die man
anklickt. Ohne Fokus rechnet Qt richtig; das ist der Grund, aus dem eine
Messung ohne `setFocus` nichts findet.

Drei Auswege sind gemessen und untauglich: `:on` (der Pseudozustand für das
offene Menü) wird erst nach der Höhenrechnung gesetzt, `outline` zeichnet Qt
an einer Combobox nur einen Punkt breit, und ein Rahmen, der in einen
`margin` hineinwächst, vergrößert stattdessen das Feld. Es bleibt: **konstante
Breite, wechselnde Farbe.**

Der Ruherahmen ist deshalb zwei Punkte breit und nimmt eine gedämpfte
Mischfarbe (`_blend(line, base, 0.55)` in `style.py`), damit er so leise
bleibt wie der einpunktige vorher. Das kostet Regel 18 nichts: Ein Punkt
Rahmenbreite ist keine wahrnehmbare zweite Kodierung — die Kachel des
Startbildschirms hat das schon einmal gezeigt —, und der Abstand zwischen
Ruhe und Fokus ist jetzt größer als zuvor.

`tests/test_style.py` hält beide Enden: eine Messung am gebauten Fenster
(`test_an_open_combo_box_shows_every_entry_it_has`, samt Gegenprobe mit der
alten Regel, die fallen **muss**) und eine am Text der Regel
(`test_the_focus_ring_never_changes_the_size_of_a_field`).

**Und der Ruhezustand behält die volle Linienfarbe.** Der doppelt breite
Rahmen legte es nahe, ihn zur Feldfläche hin zu dämpfen, damit er so leise
wirkt wie der einfache vorher. Im Bild sah das richtig aus und war gemessen
falsch: 3,33 auf 1,90 im dunklen Thema, 2,43 auf 1,57 im hellen — unter den
3,0, die WCAG 1.4.11 für die Umrandung eines Bedienelements verlangt und die
zwei Absätze weiter oben für den Fokusring zitiert werden.

Die Fläche fängt das nicht auf: Feld gegen Fenster sind 1,45 im dunklen und
1,22 im hellen Thema. **Der Rahmen ist die einzige Kante, die ein Feld hat.**
`test_a_field_keeps_the_edge_that_is_its_only_one` prüft gegen die
Linienfarbe des Themas und nicht gegen 3,0 — was diese Farbe leistet, ist eine
Frage an das Thema (im hellen bringt sie seit je nur 2,43), dass der Rahmen sie
nicht unterschreitet, eine an das Stylesheet.

## Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn die zwei bis drei Werte, die man ändert; hinten
Toleranzen, Auflösungen, Rückfallverhalten. Die Vorgaben kommen aus dem
Drucker- und Materialprofil. **Eine gute Vorgabe ist mehr wert als eine gute
Einstellmöglichkeit.**

**Was entscheidet, was später überhaupt geht, gehört nach vorn.** Der
Umschalter der zwei Rechenkerne stand hinten, zugeklappt — und an ihm hängen
sieben Operationen: Fase, Verrundung, Formschräge, Fläche versetzen, exaktes
Aushöhlen, Tasche schneiden, Umwandeln. Wer den Quader ohne ihn anlegte, fand
sie später alle grau. Das ist weder Toleranz noch Auflösung noch
Rückfallverhalten; die Regel oben trennt nach *Häufigkeit der Änderung*, und
eine Entscheidung, die man einmal trifft und nie wieder ändern kann, fällt
durch beide Raster. Sein Hinweis zählt die Werkzeuge auf, statt „STEP-Export
und spätere Verrundungen" zu nennen — wer eine Tasche wollte, hatte damit
keinen Anlass, den Haken zu setzen.

**Und derselbe Umschalter steht im Verlauf.** `History.change_kernel` stellt
einen Schritt auf seinen Zwilling um, `edit_operation` zeigt den Haken auf dem
Stand, der im Dokument steht — an beiden Enden des Paars, also auch zum
Abwählen. Ohne ihn war ein Quader, den jemand ohne den Haken angelegt hatte,
endgültig ein Netz: der einzige Weg dorthin war, den Schritt zu löschen und
alles darüber neu zu bauen. Getauscht wird nur zwischen `MENU_TWINS` —
beliebige Operationen gegeneinander wäre kein Bearbeiten mehr, sondern ein
Umschreiben der Geschichte. Und der Dialog wird immer aus dem **sichtbaren**
Zwilling gebaut, gleich welcher im Verlauf steht: aus dem exakten heraus gäbe
es kein `anchor`, und wer den Haken abwählte, bekäme einen Dialog ohne die
Felder, die er gerade freigeschaltet hat.

**Ein gesperrtes Werkzeug kennt zwei Lagen, nicht eine.** Der Körper war nie
exakt — dann geht es um den Haken. Oder er war es und ist es nicht mehr, weil
eine Mesh-Operation dazwischen liegt; dann hilft kein Haken.
`spoiled_the_exact_body()` liest den Schuldigen aus
`evaluate.exact_became_mesh` und `kind_requirement` nennt ihn beim Titel. Der
Vorschlag muss dabei ausführbar sein: Der erste Entwurf schlug vor, „den
Schritt im Verlauf nach hinten zu nehmen" — und das kann der Verlauf nicht,
aus gutem Grund (spätere Operationen bauen auf seinen Ausgaben auf).

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

## Die Oberfläche wächst nicht mit

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). Die Zahlen
dazu stehen in `tests/test_interface_limits.py` und werden rot, wenn sie
gerissen werden — die Breitengrenze des Skizzenbereichs in
`tests/test_sketch_editor.py`, weil sie ein gebautes Fenster **mit Thema**
braucht und nicht das Register:

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 — heute sieben: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen — auf `Alt+1` bis `Alt+7` |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
| Breite des Skizzenbereichs, der Werkzeug- und der Bedingungszeile | je ≤ 900 Bildpunkte |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut das mit Absicht und begründet es im Commit.
Die Werkzeugzeile hat sieben von acht Plätzen belegt, seit das Bemalen mit dem
Punkt-Radius-Pinsel fiel — Färben läuft über das Kontextmenü am Merkmal. Der
achte Platz ist keine Einladung: Eine Funktion, die eine Leiste will,
verdrängt eine andere, oder sie ist keine wert (`MAX_TOOLS` in
`tests/test_interface_limits.py`).

**Und gefaltet wird, weil es sein muss — je Kategorie, nicht je Gruppe.** Wer
ein Menü über die Zeilengrenze wachsen lässt, bekommt kein Untermenü für die
ganze Gruppe: `folded_categories` (`app/core/registry/surfaces.py`) faltet nur
so weit, bis der Rest passt, und nimmt sich dabei die **hinteren** Kategorien
aus `MENU_GROUPS` — die Reihenfolge dort geht von häufig nach selten. Die
Rechnung liegt im Kern, damit `menu_path` sie fragen kann; sie war einmal in
`panels.py`, und deshalb nannten Handbuch, Agent und Tour einen Weg, den die
Leiste anders baute.

Zwei Folgen für die Oberfläche, beide gemessen am 27.08.2026:

* **Eine Kategorie, die direkt im Menü steht, behält ihren Namen als
  Überschrift** (`addSection`, nicht `addSeparator`). Ein nackter Trennstrich
  hält sie auseinander und **benennt** sie nicht; man erfuhr den Namen nur,
  wenn ein Untermenü ihn trug — also genau dann, wenn der Weg einen Klick
  länger war. Eine Überschrift ist ein Trennstrich mit Text und zählt in der
  Zeilengrenze nicht mit (`isSeparator()` bleibt wahr).
* **Bei einer einzigen besetzten Kategorie bleibt die Überschrift weg** —
  sie wäre ein zweiter Name für dasselbe Menü („Bausteine → Bausteine").
* **Die direkten Kategorien stehen vor den gefalteten**, getrennt durch einen
  nackten Trennstrich. Eine Überschrift benennt alles bis zum nächsten
  Trennstrich, und eine Untermenü-Zeile dazwischen liest sich als Teil der
  Kategorie davor: „Transformation" und „Formgebung" standen unter „Verbinden
  und Abziehen". **Den Fall gab es vorher nicht** — eine Gruppe war ganz flach
  oder ganz gefaltet, und die Mischung entsteht erst mit
  `folded_categories`. Wer eine Unterscheidung einführt, führt die
  Anordnungsfrage mit ein; keine der acht bestehenden Menüprüfungen hat sie
  gestellt, und der Trennstrich hinter dem letzten direkten Block ist die ganze
  Antwort — die Zeilen dahinter tragen ihre Namen selbst.

**Ob eine Operation überhaupt einen Menüort hat, entscheidet ihre Kachel im
Katalog — nicht ihre Kategorie.** `catalogue_operations()`
(`app/core/registry/surfaces.py`) ist die eine Quelle; Menüleiste,
Kontextmenü, `menu_path` und drei Wächter fragen sie. Ein Baustein der
Bibliothek steht im Katalog mit Bild, weil ein räumliches Teil als Textzeile
die schlechtere Darstellung ist (§2.6) — im Menü standen 29 davon in sechs
Untermenüs, jede Zeile eine Vokabel statt einer Form.

Die Frage hing bis zum 29.08.2026 an der Kategorie (`WITHOUT_MENU = {"parts"}`),
und das ist die Sorte Näherung, die stimmt, bis sie nicht mehr stimmt: 27 der
29 Operationen dieser Kategorie haben eine Kachel, `create_lid` und
`screw_lid` nicht. Beide verschwanden damit aus der Menüleiste, ohne im
Katalog aufzutauchen — gemessen 114 Menüeinträge, kein *Deckel erzeugen*
darunter, und im Kontextmenü der Fläche ebenso wenig, also an genau dem Ort,
den §18.5 dafür vorsieht.

Zwei Sätze daraus, und der zweite ist der teurere:

* **Was der Katalog vertritt, ist genau das, was er zeigt.** Ein Untermenü
  oder ein Eintrag, der auf ihn verweist, darf nur die Ops ersetzen, die
  darin vorkommen; alles andere steht daneben.
* **Der Katalogeintrag tritt an die Stelle der gefalteten Gruppe, auf der
  obersten Ebene.** *Baustein einsetzen …* ist damit **einen** Klick vom
  gewählten Teil entfernt, so hat Robert die Bedingung gestellt, und
  `test_a_chosen_part_reaches_the_catalogue_in_one_click` führt sie wörtlich.
  Ein Zwischenstand legte ihn in ein Untermenü *Bausteine* und machte aus dem
  einen Klick zwei; der Test hat es gefangen. **Eine Zusage, die man dreimal
  zitiert hat, ist damit nicht eingehalten.**

**Und an dieser Stelle schließen sich vier Zusagen gegenseitig aus.** Alle vier
sind gemessen, keine ist erfunden:

| | |
|---|---|
| §40 (P0) | jede Operation steht im Kontextmenü |
| §35 | höchstens zwölf Zeilen je Menü |
| Robert | ein Klick vom gewählten Teil zum Katalog |
| §18.5, §2.6 | am Merkmal steht alles direkt, ohne Aufklappen |

An einer Fläche ergeben alle vier zusammen **vierzehn** Zeilen. Drei Fassungen
sind durchgemessen, jede bricht genau eine:

| Fassung | Preis |
|---|---|
| Katalog ersetzt die Gruppe | *Deckel erzeugen* fehlt im Flächenmenü |
| die zwei Deckel daneben | vierzehn Zeilen statt zwölf |
| die zwei Deckel mitfalten | *Bohrung setzen* eine Ebene tiefer |

Gewählt ist die erste, weil ihr Preis den seltensten Fall trifft: Die beiden
Baustein-Operationen ohne Kachel stehen im Menü *Bausteine* der Menüleiste.
**Das ist eine Bedienentscheidung und keine Bugfrage** — sie liegt Robert vor,
und wer sie ändert, ändert eine der vier Zusagen mit.
* **Ein Wächter ist so scharf wie seine weiteste Ausnahme.** Der Test, der
  „jede Operation ist im Menü auffindbar" zusichert, nahm die *Kategorie* aus
  — und blieb deshalb grün, während zwei Operationen nirgends standen. Wer
  eine Ausnahme formuliert, prüft sie an ihren Rändern und nicht an ihrem
  Normalfall.

**Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort.** An jeder
Fläche stand *Bohrung setzen* zweimal: `drill_hole` und `drill_brep_hole`
tragen denselben Titel, und der Kunde traf seine Wahl blind — je nach Zeile
bekam er einen anderen Rechenkern. Die Menüleiste legt das Paar seit je über
`MENU_TWINS` zusammen; `panels.operations_for_feature` gab
`REGISTRY.for_feature` ungefiltert weiter und kannte die Zusammenlegung nicht.
**Dieselbe Frage, zwei Rechnungen** — genau der Grund, aus dem die Menütiefe in
den Kern gewandert ist.

Weggelassen wird ein Zwilling nur, wenn sein Partner tatsächlich mit angeboten
wird; sonst wäre er spurlos weg statt zusammengelegt.

`surfaces.context_menu()` bleibt dabei die **Rohmenge** — der Name legt anderes
nahe, und `tests/test_acceptance_p0.py` nagelt diese Lesart ausdrücklich fest.
Was daraus Zeilen werden, entscheidet die Oberfläche.

**Und die Testfalle dazu, weil sie allgemeiner ist als der Fall:** Der
bestehende Test nimmt `operations_for_feature` als *Sollmenge* („alles, was sie
liefert, steht im Menü"). Ein Filter in dieser Methode lässt Erwartung und
Menü gemeinsam schrumpfen — der Test bleibt grün, ganz gleich was die Methode
tut. Das ist die Schwester von „Sollwert aus dem Prüfling": Dort erzeugt die
geprüfte Funktion die Erwartung, hier definiert sie die Grundmenge. Gezählt
wird deshalb am **gebauten** Menü, und die Zusage lautet nicht „*Bohrung
setzen* genau einmal", sondern „kein Kontextmenü zeigt zwei Zeilen mit
demselben Text" — die engere Fassung wäre am Tag des nächsten Zwillings still.

**Ein Zeichen darf allein stehen, wenn es entweder ein geeinigtes Bild ist
oder die Zahl klein und die Stelle fest bleibt.** Der Skizzeneditor lebt vom
ersten Fall: Linie, Kreis und Bogen sehen in jedem CAD gleich aus. Die obere
Werkzeugleiste vom zweiten — Blatt, Ordner und Diskette sind geeinigt, „Modell
einfügen", „Zeichnen", „Formen" und „Skelett" nicht; was sie trägt, sind
sieben Knöpfe an unveränderlicher Position mit einem Tooltip, der Namen,
Kürzel und Zweck in einem Satz nennt. Die Werkzeugzeile unter dem Viewport
bleibt beschriftet: sieben Umschalter, die mit dem Zustand wechseln, und für
„Schnitt" und „Explosion" gibt es kein Bild. (Sieben ist der Bestand, acht die
Grenze — ``MAX_TOOLS`` in ``test_interface_limits.py``, wo der Kommentar den
Unterschied ebenfalls führt.) Regel 18 verlangt eine zweite
Kodierung neben der **Farbe**, nicht eine Beschriftung neben jedem Zeichen.

Wo das Wort vom Knopf verschwindet, muss es an drei Stellen weiterstehen: am
`QAction` (Barrierefreiheitsbaum), im Tooltip und im `statusTip`. Den Satz
dafür holt `_button_tip` aus dem Menüeintrag derselben Handlung, samt Kürzel —
zwei eigene Erklärungen für einen Knopf driften auseinander. Der `statusTip`
ist dabei nicht nur Anzeige: `_lock_hint` und `_pick_hint` stellen den eigenen
Hinweis daraus wieder her, und ein ungesetzter macht den Knopf nach dem
Freischalten stumm. Beide Helfer ersetzen den Hinweis vollständig; damit am
unbeschrifteten Knopf nicht ein Bild und ein zusammenhangloser Satz übrig
bleiben, stellt `_with_name` den Namen voran (Merkmal `wordless` am `QAction`).
Getrennt wird mit dem Zeichen, das der Satz dahinter **nicht** schon führt:
Gedankenstrich vor dem Zweck, Doppelpunkt vor einem Grund, der selbst einen
Gedankenstrich hat.

**Wer eine Beschriftung ausblendet, zieht die Anleitungstexte mit.** Handbuch
(`app/core/manual.py`) und Tour (`app/core/tour.py`) verweisen auf Knöpfe beim
Namen; steht der Name nicht mehr am Knopf, sucht der Leser. Die Tour wiegt
schwerer als das Handbuch — ihre Schritte haben `done=`-Bedingungen und rücken
nicht weiter.

**Eine Operation je Handlung, nicht je Variante.** Neun Texturmuster sind ein
Menüeintrag mit einem Auswahlparameter, nicht neun Einträge. Rechteck aus zwei
Ecken oder aus Mitte und Maß ist dasselbe Werkzeug mit einem Umschalter. Die
Mesh/B-Rep-Zwillinge (Quader, Zylinder) sind dieselbe Handlung in zwei
Rechenkernen: ein Eintrag, „Exakt (B-Rep)" ist ein Umschalter hinten im
Dialog, und `MENU_TWINS` im Register hält die Zuordnung — auch für den
Menüort, den der Agent nennt (§2.6).

**Nicht jeder Zwilling braucht einen Umschalter.** Die Beschriftung liegt in
`TWIN_TOGGLES`, nicht als Zeichenkette in der Oberfläche; wer dort fehlt, hat
seinen Umschalter als **Wert** im Dialog des Partners. *An Ebene teilen* ist
*Teilen* mit `pins = 0` — ein Haken „Exakter Körper (B-Rep)" wäre dort eine
Wegbeschreibung zu etwas, das es nicht gibt. Solange das fest verdrahtet war,
taugte die ganze Zusammenlegung für nichts als die zwei Rechenkerne.

**Ein Umschalter, dessen Zwilling eine Bedingung hat, fragt sie — vorher.**
Das Menü graut eine Operation des exakten Kerns (`requires_kind="brep"`) an
einem Netz aus und schreibt den Grund in den Tooltip. Seit die Zwillinge
zusammengelegt sind, hat `drill_brep_hole` gar keinen eigenen Menüeintrag mehr:
Der **Haken ist der Weg zu ihr**, und dort wurde nicht gefragt. Gemessen an
einer eingelesenen STL — Haken wählbar, Dialog geht durch, Auswertung hält bei
op 2 an, Absage im Prüfbericht. Der Satz des Kerns ist gut und bleibt; er ist
die *zweite* Hürde, und die erste fehlte.

`_lock_twin_toggle` fragt dafür `_reason_locked`, also dieselbe Kette wie
Menüleiste und Kontextmenü — eine dritte Formulierung derselben Auskunft wäre
eine dritte Gelegenheit, auseinanderzulaufen.

**Und ein Menü zeigt Hinweise nur, wenn man es ihm sagt.** `QMenu` steht mit
`toolTipsVisible == False` auf der Welt: Der Satz, den `_add_operation` an die
gesperrte Handlung schreibt, kommt an — und Qt zeigt ihn nie. Die Menüleiste
setzt die Eigenschaft an ihren drei Stellen seit je; das Kontextmenü am Körper
und das der Skizze taten es nicht, und damit war die ganze Kette umsonst.
**Untermenüs erben sie nicht** — und am ganzen Körper stehen die Operationen
gerade dort drin, nach Kategorie gruppiert, weil siebenundfünfzig Zeilen kein
Menü mehr sind.

Der Test daneben prüfte den **Wert** von `toolTip()`, und der war immer
richtig. Eine Zusage über einen Text ohne die Zusage, dass er erscheint, ist
die Hälfte einer Prüfung — wer einen Grund an eine Handlung schreibt, prüft
`toolTipsVisible()` des Menüs mit, in dem sie steht.

**Grau ohne Grund gibt es auch ohne `requires_kind`.** Im Kontextmenü der
Skizze standen die zehn Bedingungen, die halbe Liste gesperrt, und keine sagte,
welche Auswahl ihr fehlt — obwohl der Halbsatz seit je existiert
(`_needs_phrase`) und am Knopf in der Leiste und in der Meldung nach dem Kürzel
schon steht. Die dritte Stelle bekommt ihn aus derselben Quelle, nicht neu
formuliert.

**Bei den ersten beiden Zwillingen konnte das nicht auffallen:**
`create_brep_box` und `create_brep_cylinder` verbrauchen nichts (`consumes=0`),
es gibt keinen Eingangskörper, der der falsche sein könnte. Wer einen Zwilling
mit Eingang dazunimmt, nimmt diese Frage mit.

**Und der Zwilling heißt genau wie sein Partner.** `create_brep_box` trägt
„Quader anlegen", `drill_brep_hole` „Bohrung setzen" (`app/core/brep/ops.py`)
— denselben Titel wie `create_box` und `drill_hole`. Den Unterschied nennt
nicht der Titel, sondern der Haken im Dialog des Partners („Flächen und Kanten
später bearbeiten", `_EXACT_TOGGLE` in `registry.py`); in der Palette steht
der Zwilling nicht ein zweites Mal (`hidden_from_the_menu`). Zwei Stufen
davor lagen falsch: „Exakt bohren" ließ `test_theme_and_palette` fallen, weil
die Befehlspalette nach Titel sortiert und der Eintrag bei der Suche nach
„bohren" *vor* „Bohrung setzen" landete; „Exakten Quader anlegen" mit dem
Wort davor las sich wie eine Qualitätsstufe („das andere ist also ungenau?"),
obwohl es den Rechenkern meint. Dahinter steht der Kunde: Er sucht das
**Substantiv** („Bohrung"), und wer den Zwilling umformuliert, nimmt ihm eine
der beiden Antworten aus der Liste.

**Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**, nicht nur
die Rechnung: `OperationDialog.switch_variant` blendet aus, was die gewählte
Variante nicht kennt, und tauscht die Beschreibung. Die Werte beim Anwenden zu
filtern genügt nicht — was stehen bleibt, verspricht eine Wirkung. Der
Bezugspunkt des Netz-Quaders stand in derselben aufgeklappten Gruppe wie der
Umschalter selbst, also genau dort, wo jeder vorbeikommt; auf „Ecke" gestellt
kam ein mittiger Quader und kein Ton dazu.

**Ein Feld ohne Wirkung sagt es.** Eine Nummer kleiner als der Umschalter:
*Fläche* in „Relief auflegen" gilt nur, solange *Auflegen* auf „Auf eine
Fläche" steht, und die Operation übergeht den Wert sonst wortlos. Solche
Abhängigkeiten stehen in `DEPENDENT_FIELDS` (`app/ui/op_dialog.py`), nicht als
Sonderfall im Aufbau. Das Feld wird **grau und begründet**, nicht unsichtbar —
verschwinden darf nur, was die gewählte Variante gar nicht kennt; wer eine
Zeile vermisst, sucht sie.

**Die Angabe steht am Parameter** (`ParamSpec.depends_on`), nicht in einer
Tabelle der Oberfläche. Als Tabelle hatte sie einen Eintrag, während fünf
Operationen bedingte Felder trugen — *Kopien in Reihe oder Kreis* allein sechs —
und sie hatte damit ihre eigene Begründung widerlegt: Dieselbe Auskunft brauchen
vier Oberflächen, und genau eine hatte sie. Der Dialog graut aus und begründet,
das Handbuch schreibt die Bedingung in die Parametertabelle, der Agent bekommt
sie in der Werkzeugbeschreibung, die Kommandozeile liest dasselbe `json_schema`.

**Agent und Mensch bekommen verschiedene Anreden, nicht verschiedene Inhalte.**
„Gilt bei Art = circular" hilft im Handbuch; der Agent kennt kein *Art*, er
setzt `kind` (`condition_text(..., keys=True)`). Der Dialog formuliert
eigenständig („Wirkt nur, wenn …"), weil er einen Tooltip an einem ausgegrauten
Feld schreibt und die Werte durch `choice_label` schickt — zwei Formulierungen,
eine Quelle.

`tests/test_operation_ui.py` liest deshalb
den Quelltext jeder Operation und meldet jeden Parameter, dessen sämtliche
Lesestellen in einem Zweig über einen Umschalter derselben Operation liegen.
Zwei Regeln machen die Prüfung brauchbar statt abgeschaltet: **in genau einem
Zweig** gelesen (was in beiden steht, wirkt immer), und **kein Aufruf, der den
ganzen Parametersatz weitergibt** (dort endet der Blick von außen). Ohne die
zweite meldete sie acht Funde, von denen sieben keine waren.

Ein **Haken** als Umschalter braucht zwei Dinge, die eine Auswahl nicht
braucht: einen typtreuen Vergleich — über `str()` hieße der gesuchte Wert
„True", und weil `1 == True` ist, machte eine Anzahl von 1 einen Haken wahr —
und einen eigenen Satz. „Wirkt nur, wenn „Gründlich suchen" auf „True" steht"
ist die Bauart der Anwendung und nicht ihre Bedienung.

Wer eine neue Abhängigkeit deklariert, prüft die **Art** des Umschalters mit:
Ein Wahrheitswert an einem Aufklappmenü oder ein Auswahlwert an einem Haken wäre
eine Bedingung, die nie zutrifft — und ein Feld, das immer grau bleibt.

**Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat.** Der
Skizzentext hat ihn seit je, die Stellung eines Skeletts bekam ihn spät:
`kind="armature"` fiel auf ein Textfeld durch, und der kürzeste Weg zu einem
gebeugten Arm ging über getipptes JSON. `ArmatureField` baut je Knochen eine
Zeile mit drei Winkeln — sobald der Dialog ein Skelett hat (aus dem Editor
oder aus dem Wert der Operation), sonst bleibt das Textfeld als Rückfall. Die
Winkel sind `ValueField`, denn §13 gilt für einen Winkel wie für eine Länge.
Im **Schema** bleibt der Sammelparameter hinten (`tests/test_gesture_ops.py`);
im Dialog steht er vorn, wenn er der Grund ist, aus dem der Dialog aufgeht.

**Eine Grenze steht dort, wo gewählt wird.** `caveat` im Registereintrag sagt,
wann eine Operation die falsche Wahl ist. Sechsundzwanzig von fünfundneunzig
Operationen tragen einen (gemessen am 29.08.2026; hier stand „zwölf", und die
Zahl war mit dem Bestand nicht mitgewachsen — sie ist deshalb jetzt geprüft,
siehe `tests/test_registry_consistency.py`). Gelesen hat ihn lange allein die
Handbuchreferenz — nicht der Dialog, in dem
gerade jemand die Operation anwendet, nicht der Tooltip am Menüeintrag, nicht
die Werkzeugliste des Agenten. `caveat_line()` (`app/core/registry/surfaces.py`)
ist die eine Quelle und trägt das Wort davor: Ohne Vorwort liest sich die Grenze
als Fortsetzung des `doc`-Satzes. Im Dialog ein **eigenes Label**, halbfett, mit
dem Wort als zweiter Kodierung (Regel 18); im Tooltip unter dem Satz; beim
Agenten in der Werkzeugbeschreibung. **Nicht in die Statuszeile** — die ist eine
Zeile, und eine abgeschnittene Warnung ist schlimmer als keine.

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Kontextmenü am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Trennen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen": erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig"), Menü *Erzeugen* / *Ändern* |
| Weg 3 — generieren | Chat und Generierungsdialog |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — beide brauchen einen gewählten Körper und sagen das, bevor man klickt), Menü *Ändern* |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

**Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt hat**
(§21.2). Der Eintrag *Diesen Schritt ändern* steht im Kontextmenü am Merkmal,
ganz oben und vor der Sichtbarkeit — er gilt dem Merkmal, die Sichtbarkeit
gilt dem Körper. Er ist der einzige Weg vom *Ergebnis* zurück zum *Schritt*:
sonst sucht der Kunde unter vierzehn Zeilen des Verlaufs die eine, die das
Ding erzeugt hat, das er gerade ansieht.

Die Frage lautete lange, welche Operation fachlich auf ein fertiges Gewinde
gehört, und `for_feature("thread")` gab darauf nichts zurück. Über
`applies_to` wäre die Antwort eine neue Operation je Merkmalsart gewesen;
über die Provenienz (`Feature.created_by`) ist sie **ein** Eintrag, der für
alle gilt und jede neue Merkmalsart von selbst mitnimmt. Ein **erkanntes**
Merkmal trägt `None` und bekommt ihn nicht — er führte dort ins Leere, und
das ist schlechter als keiner.

Damit bleibt `thread` in den `known_gaps` von
`tests/test_registry_consistency.py`, und das ist kein Rückstand: Die Prüfung
dort fragt `for_feature`, also `applies_to`, und über diesen Weg ist die Art
weiterhin leer. Wer die Ausnahme streicht, weil „das Gewinde jetzt etwas
anbietet", macht den Test rot.

Erzeugte Merkmale kommen aus **Bausteinen** (`knowledge/parts/build.py`) und
aus dem Verstiften, nicht aus jeder Operation: `drill_hole` rechnet Geometrie
und deklariert nichts, seine Bohrung findet die Erkennung wieder. Wer den
Eintrag testet, nimmt deshalb einen Baustein und nicht das Bohren.

**Was zur Auswahl passt, steht vorn.** `applies_to` sortiert nicht nur das
Kontextmenü, sondern auch die Befehlspalette
(`palette_entries(for_feature=...)`). Es ist eine Reihenfolge, keine Auswahl —
eine Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen.

**Und sortiert wird nach dem Titel, überall mit `i18n.sort_key`.** Die
Menüleiste tat es (`by_category`), Palette und Kontextmenü gaben die Ordnung
von `Registry.all()` weiter — die der internen englischen Bezeichner. Gelesen
hat man dort „An Merkmal ausrichten", „Textur aufbringen", „Auf dem Bett
anordnen". Nicht `str` und nicht `casefold`: 23 der 85 Titel tragen einen
Umlaut, und „Überhangfächer" landet nach Codepunkt hinter allem anderen. Nicht
zu verwechseln mit `command_palette.fold`, der **Suchfaltung** — dort wird „ä"
zu „ae", weil jemand „aushoehlen" tippt; beim Sortieren zählt „ä" wie „a"
(DIN 5007-1), damit „Ändern" zwischen „Analyse" und „Anordnen" steht. Zwei
Aufgaben, zwei Tabellen, und der Kommentar an jeder sagt, welche.

## Wie die Karten ihre Höhe teilen

`OverlayHost._share_room` verteilt die Höhe einer Zone auf ihre `RoomTaker`.
Drei Zusagen, und alle drei sind schon gebrochen worden:

* **Gerechnet wird nie mit den Höhen, die gerade gesetzt wurden.** Eine
  Zuteilung, die ihr eigenes Ergebnis liest, bekommt beim nächsten Durchlauf
  andere Zahlen und die Karte läuft auf und ab — bei einem einzigen Aufklappen
  waren es 905 Geometriewechsel. Deshalb taugt `natural_height` **innerhalb**
  der Zuteilung nicht: sie liest für ihre Rollbereiche die gelegten Höhen und
  schwankte zwischen 389 und 1275 Pixeln. `extra_height` rechnet strukturell —
  je Posten der Unterschied zwischen dem, was er als Ganzes wünscht, und dem,
  was die Karten darin wünschen — und stand über Zuteilungen von 60 bis 900
  Pixeln unverändert auf 217.
* **Was nicht den Karten gehört, wird abgezogen.** Abschnittsköpfe,
  Parameterleiste, Layoutabstände. Ungekürzt verteilt die Zuteilung mehr Höhe,
  als die Zone hat: Der Objektbaum stand auf 500 Pixeln in einem Abschnitt von
  121, das Elternwidget schnitt die Differenz weg, und weil der Baum von seiner
  eigenen Höhe ausging, meldete sein Rollbalken dazu nichts. Zehn Zeilen waren
  nicht abgeschnitten, sondern unerreichbar.
* **Jede Karte nennt ihren Boden** (`RoomTaker.least_height`), und verteilt wird
  nur, was darüber liegt. Sonst ist die Zuteilung eine Bitte: Der leere Verlauf
  meldete vier Pixel Bedarf, bekam anteilig drei und setzte 112 durch. Der Boden
  hat zwei Quellen, und beide zählen — `fit_to_rows` mit seinen drei
  Mindestzeilen und der leere Zustand, dessen Höhe aus dem umbrochenen Satz
  kommt (`fit_wrapped`) und nicht aus der Zeilenrechnung. **Und nie höher als
  der Wunsch**: Eine Karte, die überhaupt nur eine Zeile *hat*, forderte über
  jene drei Mindestzeilen 130 Punkte für 128 gewünschte — Platz, den sie
  niemandem zeigen kann, während die Nachbarn ihn brauchen.

`tests/test_overlay.py` hält alle drei: „settles on one answer",
„moves a card once", „no card is pushed outside its section".

**`fit_to_rows` rechnet mit *einer* Zeilenhöhe** — der ersten, mal der Zahl
der Zeilen. Für einen Baum, in dem jede Zeile gleich aussieht, ist das
richtig; für eine Liste mit fetten Zwischenüberschriften ist es zu wenig. Die
Filamentkarte brauchte bei fünf Zeilen 172 Punkte und bekam 156, und die
letzte Zeile fehlte auch dann, wenn die Spalte ihre volle Wunschhöhe hatte und
ringsum Platz frei war. Wer eine Liste mit ungleichen Zeilen bemisst, nimmt
`overlay.rows_height` — es misst jede Zeile einzeln, und `wanted_height` muss
dieselbe Quelle nehmen wie das Setzen, sonst fordert die Karte etwas anderes,
als sie einrichtet.

**Und was unter der Liste steht, gehört in beide Rechnungen.** Hinweis und
Knöpfe einer Karte sind kein Beiwerk der Zone, sondern Teil der Karte: Wer der
Liste die ganze Zuteilung gibt, schiebt sie unten heraus. Bei der
Filamentkarte waren das *Filament anlegen …* und *Druckwerte …* — der einzige
Weg zu einer neuen Spule, und er stand außerhalb des Fensters.

## Barrierefreiheit

- **Keine Bedeutung allein über Farbe** (Regel 18). Immer eine zweite
  Kodierung: Muster, Schraffur, Symbol, Beschriftung.
- **Aber auch keine Bedeutung ohne Farbe, wo Farbe die Sache ist.** Ein
  Materialslot ohne eigene Farbe bekam in der Ansicht die Körperfarbe — bei
  zwei bemalten Slots zwei gleiche Einträge in derselben Tabelle, und das
  Bemalen war im Bild folgenlos. `theme.slot_colour` gibt die Ersatzfarbe
  (Okabe/Ito, sieben Einträge; Slot 0 ist das unbemalte Teil und bekommt
  `None`); im **Dokument** steht sie nicht, denn keine Farbe zu haben ist ein
  Zustand, den „Slot zuweisen" auflöst. Die Zahl daneben bleibt: Die
  Pinselleiste zeigt Farbfeld **und** Name, „neu" für einen Slot, den der
  gewählte Körper noch nicht hat.
- **Dasselbe Problem bietet dieselben Handlungen**, gleich wer es meldet.
  „Nicht geschlossen" meldet der Kern beim Einlesen, beim Exportieren und nach
  jedem Zug des Agenten; zwei trugen ihre zwei Handlungen, der dritte nichts.
  **Seit dem Filament-Konzept (26.08.2026) ist die Ersatzpalette eine
  Grauleiter, keine Buntpalette mehr:** Okabe/Ito begann mit einem Orange,
  das von der Auswahlfarbe nicht zu unterscheiden war (Kontrast 1,09) — die
  allererste Bemalung sah aus wie eine Auswahl. Echte Farben kommen vom
  Kunden (Farbwähler, Filamentkatalog); die Leiter zeigt nur den Zustand
  davor, unbunt und je Stufe unterscheidbar
  (`test_no_fallback_colour_can_be_mistaken_for_the_selection`).
  `FINDING_ACTIONS` (`app/ui/panels.py`) hält die Zuordnung, und
  `tests/test_value_labels.py` prüft die **Familie**: Befunde mit demselben
  Namen hinter dem Punkt melden dasselbe Problem, und trägt einer eine
  Handlung, müssen es alle.
- **Die Kennung entscheidet über die Handlung, also muss sie den Fall
  treffen.** „Passt nicht" und „liegt woanders" sind zwei Fälle, und die
  Trennlinie ist nicht, über welche Seite ein Körper hinaussteht, sondern ob er
  überhaupt hineinpasst (`prepare._fits_at_all`). Gemessen am häufigsten
  Importfall überhaupt: Eine 3MF aus Bambu Studio, Orca oder Elegoo führt
  **Bettkoordinaten**, ihre Körper liegen also rechts neben dem Bett — 132 mm
  breit auf einem 256er Bett. Angeboten wurden *Modell teilen*, *Auf den
  Bauraum verkleinern* und *Anderen Drucker wählen*, dreimal, gleich beim
  Öffnen. Was hilft, ist *Auf dem Bett anordnen*.
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
  wird ohne sie nicht angeboten.
- **Ein Klick auf einen Befund bleibt nie folgenlos.** Er ist die Geste, die
  §2.7 dem Prüfbericht ausdrücklich verspricht, und sie war leer: Gemessen am
  30.08.2026 über alle 58 Befunde der Beispielprojekte löste **keiner** eine
  sichtbare Reaktion aus. Zwei Ursachen — ein Operationsfehler trägt weder Ort
  noch Merkmale (der Kern gibt ihm `object_id` und `op_id`), und der Ort eines
  Kartenbefunds steht erst fest, wenn die Karte gerechnet ist, was beim ersten
  Klick nie der Fall ist. Beim zweiten ging es, und damit sah es aus wie ein
  Bedienfehler des Kunden.

  Geantwortet wird gestuft, nach dem, was der Befund hergibt: **Ort** → die
  Kamera fliegt hin und eine vergängliche Marke steht dort (`mark_finding`,
  Ring in Auswahlfarbe plus Titel); **Körper** → er wird ausgewählt und trägt
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
- Differenzansicht in Blau/Orange als Vorgabe, nicht Rot/Grün.
- Analysekarten mit wahrnehmungsgleicher Palette (Viridis-Art), kein
  Regenbogen — der erzeugt Kanten, wo keine sind.
- Alles über die Befehlspalette erreichbar; Kürzel stehen daneben, so lernt man
  sie nebenbei. Undo und Redo gelten überall, auch im Chat.

**Ein Kürzel folgt dem deutschen Titel.** So hält es der Bestand seit je —
*Bohrung setzen* auf Strg+B, *Drehen* auf Strg+R, *Aushöhlen* auf Strg+H —, und
eine Übersetzung ändert daran nichts: Kürzel sind keine Texte, sie stehen im
Register. Ist der einfache Buchstabe belegt, kommt Umschalt dazu (*Vereinigen*
Strg+Umschalt+V, *Abziehen* Strg+Umschalt+A); ist auch das belegt, **bleibt die
Operation ohne Kürzel**. *Skalieren* ist der Fall: S gehört dem Speichern,
Umschalt+S dem Speichern unter, und ein erfundener Buchstabe wäre schlechter als
keiner. Vierzehn von sechsundachtzig führen eines; wer eine fünfzehnte Taste
vergibt, prüft vorher am **gebauten Fenster** gegen die dreiundvierzig, die
nicht aus dem Register kommen — Ansichten, Werkzeugzeile, Dateibefehle,
Navigation. Eine doppelt belegte Taste führt keine der beiden Aktionen aus
(„Ambiguous shortcut overload"), und das merkt man erst beim Drücken;
`tests/test_ui.py` (`test_no_two_shortcuts_in_the_window_collide`) hält es fest,
`tests/test_registry_consistency.py` allein sähe nur die eine Hälfte.
- HiDPI, skalierbare Schrift, Kontrast in hellem und dunklem Thema,
  Anzeigeeinheit zwischen Millimeter und Zoll umschaltbar.

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
  Feld, und dafür muss niemand `value()` schreiben. Sechs Stellen im Fenster
  nahmen sie: Der Pinselradius kam als 0,1969 in der Szene an, wo 5 mm
  eingestellt waren, und `stroke_at` schrieb damit **Geometrie ins Dokument**.
  `valueChangedMm` ist dieselbe Nachricht in der Einheit des Kerns;
  `valueChanged` bleibt für alles, was den Wert fallen lässt und selbst
  `value_mm()` liest.
* **Ein Einheitenwechsel meldet nichts.** `refresh_unit` legte die neue Spanne,
  während noch der Wert der alten stand — Qt klemmt ihn und feuert damit. Ein
  Feld auf 10 mm gab seinem Empfänger 99,9998, bevor es 10,0 gab. In
  Millimetern ändert sich beim Wechsel nichts, also gibt es nichts zu melden:
  der Tausch läuft unter `blockSignals`.
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

Wer den Zustand in einem Test setzt, bekommt ihn zurückgesetzt
(`tests/conftest.py`); sonst nähme ein Test jeden folgenden mit.

## Tests

Oberflächentests laufen offscreen (`QT_QPA_PLATFORM=offscreen`, von
`tests/conftest.py` gesetzt). Eine neue Ansicht ohne Test in `tests/test_ui.py`
oder einer der spezielleren Dateien ist unfertig.

**Ein modaler Dialog auf einem Startweg hält die ganze Suite an.** Am
03.09.2026 kam ein Hinweis vor den Druckeinstellungs-Dialog — richtig gebaut,
fehlerfrei, am falschen Ort: `QDialog.exec()` wartet offscreen auf einen Klick,
den es nie gibt. Betroffen war jeder Test, der die Druckeinstellungen öffnet,
und die CI bis zu ihrem Sechs-Stunden-Limit.

Das Tückische ist nicht der Fehler, sondern seine Anzeige: **Die Suite wird
nicht rot, sie steht.** Kein Name, kein Fehlschlag, nur ein Protokoll, das
nicht mehr wächst — gefunden hat es eine Nachbarsitzung mit
`py-spy dump --native`, und dort stand die Stelle wörtlich.

Wer einen Dialog auf einen Weg setzt, den ein Test geht, fragt vorher
`QT_QPA_PLATFORM != "offscreen"` — dasselbe Muster wie
`motion.animations_enabled`, und aus demselben Grund: Wer offscreen läuft,
prüft Verhalten und wird nicht bedient. Der Merker eines solchen Hinweises
wird dabei **nicht** gesetzt; sonst hätte der Kunde ihn nie gesehen und bekäme
ihn trotzdem nie wieder.

**Ein Widget braucht die `QApplication` in der Signatur, nicht im Glück.** Wer
ein Widget ohne sie baut, bringt den ganzen Lauf mit 0xC0000409 um — ohne ein
Wort Ausgabe, nur mit einem Rückgabewert. In der vollen Datei fällt das nicht
auf, weil ein früherer Test die Anwendung schon gebaut hat; ob das passiert,
entscheidet `pytest-randomly`. Also nimmt jeder Test, der ein Widget anfasst,
`qt_app` oder eine Fixture, die darauf aufbaut — auch der, der scheinbar nur
eine Zeichenkette prüft.

## Die Zeichenfläche

Der Skizzeneditor hat eigene Regeln, und sie laden mit ihm:
`zeichenflaeche.md`.
## Die Ansicht, der Zeiger, die Platten

Sie haben eigene Regeln, und sie laden mit den Dateien, die sie betreffen:
`ansicht.md`.

## Wartezeit und Nebenläufigkeit

Ebenso — `wartezeit.md` lädt mit `session.py`, `loading.py`, `leash.py`,
`splash.py` und `main_window.py`.

