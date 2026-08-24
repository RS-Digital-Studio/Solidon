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
(Regel 19).

## Texte

Keine feste Zeichenkette in der Oberfläche — alles über `tr()`, deutsch und
englisch. **Das gilt auch für Auswahlwerte**: `raised`, `flat`, `linear` sind
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
457 Parameter der 86 Operationen ihren `doc`-Satz aus dem Register. Beide Male
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

## Was nur das Bild zeigt

Vier Fehler am selben Tag, alle vier durch eine grüne Suite gekommen, alle vier
im gerenderten Fenster sofort zu sehen:

| Fehler | Warum kein Test ihn fand |
|---|---|
| Hauptknopf ohne Beschriftung | `click()` funktioniert auf einem leeren Knopf |
| Skala in vier von sechs Sprachen abgeschnitten | die Werte stimmten, nur die Breite nicht |
| Nebenfeld doppelt so hoch wie die Hauptfrage | ein Layout hat kein Richtig und Falsch |
| Aufklappmenü als erste Zeile über einer Frage | es tat genau das, was es sollte |

Die Regel dazu ist keine neue, sondern die aus §35 an ein Widget gerichtet:
**Was man nicht angesehen hat, ist ungeprüft.** Ein Dialog wird deshalb einmal
gerendert und angesehen, bevor er als fertig gilt.

**Und angesehen wird unter der echten Plattform.** Unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien:
Jede Beschriftung wird ein leeres Kästchen, und **jede Breitenmessung ist
damit falsch**. Der erste Blick auf den Bogen sagte „die Skala passt"; unter
der echten Plattform brauchte sie in Portugiesisch 635 Punkte, wo 598 da
waren. Dieselbe Falle steht bei den erzeugten Bildern (`/erzeugen`) — sie gilt
für jede Messung an einem Widget, nicht nur für Bildschirmfotos.

Der Aufruf dafür ist drei Zeilen und braucht kein Fenster auf dem Schirm:

```python
app = QApplication([])
apply_style(app, "dark")
dialog = SupportDialog(kind=KIND_SURVEY)
dialog.show()
app.processEvents()
dialog.grab().save("bogen.png")
```

Für eine Zeile, die nicht umbrechen kann — eine Skala, eine Knopfleiste —
lohnt daneben die Zahl: `sizeHint().width()` gegen `width()`, **in jeder
Sprache**. Was gequetscht wird, meldet Qt nicht.

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
| Umschalter in der Werkzeugzeile | ≤ 8 — **erreicht**: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen, Bemalen — auf `Alt+1` bis `Alt+8` |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
| Breite des Skizzenbereichs, der Werkzeug- und der Bedingungszeile | je ≤ 900 Bildpunkte |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut das mit Absicht und begründet es im Commit.
Die Werkzeugzeile ist voll: Ein neuntes Werkzeug heißt, dass eines der acht
kein Werkzeug mehr ist.

**Ein Zeichen darf allein stehen, wenn es entweder ein geeinigtes Bild ist
oder die Zahl klein und die Stelle fest bleibt.** Der Skizzeneditor lebt vom
ersten Fall: Linie, Kreis und Bogen sehen in jedem CAD gleich aus. Die obere
Werkzeugleiste vom zweiten — Blatt, Ordner und Diskette sind geeinigt, „Modell
einfügen", „Zeichnen", „Formen" und „Skelett" nicht; was sie trägt, sind
sieben Knöpfe an unveränderlicher Position mit einem Tooltip, der Namen,
Kürzel und Zweck in einem Satz nennt. Die Werkzeugzeile unter dem Viewport
bleibt beschriftet: acht Umschalter, die mit dem Zustand wechseln, und für
„Schnitt" und „Explosion" gibt es kein Bild. Regel 18 verlangt eine zweite
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

**Und der Zwilling heißt wie sein Partner, mit einem Wort davor.** „Quader
anlegen" → „Exakten Quader anlegen", „Bohrung setzen" → „Exakte Bohrung
setzen": das Substantiv bleibt stehen, „exakt" tritt flektiert davor. Nicht neu
formuliert — „Exakt bohren" war der erste Entwurf und ließ `test_theme_and_
palette` fallen, weil die Befehlspalette nach Titel sortiert und der Eintrag
bei der Suche nach „bohren" *vor* „Bohrung setzen" landete. Der
Reihenfolgefehler war die Folge; die Ursache war die abweichende Benennung.
Dahinter steht der Kunde: Er sucht das **Substantiv** („Bohrung"), und wer den
Zwilling umformuliert, nimmt ihm eine der beiden Antworten aus der Liste.

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
wann eine Operation die falsche Wahl ist. Zwölf Operationen tragen einen, und
gelesen hat ihn lange allein die Handbuchreferenz — nicht der Dialog, in dem
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
  kommt (`fit_wrapped`) und nicht aus der Zeilenrechnung.

`tests/test_overlay.py` hält alle drei: „settles on one answer",
„moves a card once", „no card is pushed outside its section".

## Wartezeit

| Dauer | Anzeige |
|---|---|
| unter 0,2 s | nichts |
| bis 2 s | Mauszeiger und Statusleiste |
| darüber | Fortschritt mit **Abbrechen**, Oberfläche bedienbar |
| über 10 s | zusätzlich eine Schätzung, wenn möglich |

Die letzte gültige Darstellung bleibt sichtbar — nie ein leerer Viewport, nie
ein blockierendes Fenster. Lange Rechnungen laufen nicht im Qt-Hauptthread.

**Wo nichts steht, steht die Ladeanzeige.** Der Balken in der Statusleiste ist
für die Fälle richtig, in denen ein Modell im Bild bleibt; beim Öffnen eines
Projekts bleibt keines, und dann liegt er als einzige Auskunft dort, wo beim
Warten niemand hinsieht. `LoadingVeil` (`app/ui/loading.py`) legt sich deshalb
über die Ansicht — das Anwendungssymbol wird gedruckt wie beim Start,
darunter Linie, Prozentzahl, laufender Schritt und *Abbrechen*.

Drei Bedingungen, alle drei tragend:

* **Nur bei leerem Bild.** Steht ein Körper da, bleibt er stehen; wer
  entscheidet das, ist `MainWindow._update_veil`.
* **Unter den Karten, nicht darüber** (`OverlayHost.set_veil`). Über ihnen wäre
  es ein Vorhang ohne Ausgang.
* **Erst nach 200 ms.** Ein leeres Projekt ist schneller gerechnet, und eine
  Anzeige, die dabei aufblitzt, ist Unruhe ohne Auskunft.

Deckend gezeichnet, mit dem Verlauf aus `viewport_colours` — ein
halbdurchsichtiges Qt-Widget über dem OpenGL-Fenster zeigt die Fensterfarbe,
nicht die Ansicht dahinter.

**Die Ladeanzeige beginnt später, als das Warten beginnt.** Sie hängt am
Fortschritt der Auswertung; was *davor* liegt — `load()` für eine Projektdatei,
`read_bytes()` für ein Modell —, sieht sie nicht, und ihre 200 ms kommen
obendrauf. Diese Zeile der Tabelle bedient `waiting()` in `main_window.py`, ein
Kontextmanager um genau eine Rechnung: Datei lesen, Dialog aufbauen, Slicer
suchen. Als Kontextmanager, weil ein Wartezeiger, der an einem Fehlerausgang
stehen bleibt, aussieht wie ein hängendes Programm — und eine Frage, die
darunter gestellt wird, sagt zweierlei. `_offer_recovery` liegt deshalb
außerhalb.

**Ein Export bekommt Fortschritt, aber kein Abbrechen** (`_ExportWorker`). Die
Regel darüber ist nicht aufgeweicht, sie greift hier nur anders: Ein halb
geschriebener Export ist eine halbe Datei, und der Schreiber im Kern hat keinen
Punkt, an dem er sauber aufhören könnte. Was §2.8 an dieser Stelle trägt, ist
die Bedienbarkeit — der Balken läuft, das Fenster reagiert, der Menüeintrag ist
gesperrt, solange geschrieben wird. Wer einen Arbeiter ohne Abbrechen baut,
schreibt diese Begründung in seinen Docstring; ohne sie ist es Bequemlichkeit.

**Was nicht sofort da ist, wird nachgereicht statt erwartet.** Der
Druckeinstellungen-Dialog wartete bis zu zwei Sekunden auf die Schichtanalyse —
die schlechtere Hälfte beider Möglichkeiten: lang genug, um sich wie ein Hänger
zu lesen, und ohne Zusage, denn wer den Zeitraum riss, bekam den Dialog eben
doch ohne sie. Er geht jetzt sofort auf, `take_slice_result` trägt sie in die
Vorschlagsliste nach. Der Rückruf zeigt dabei auf ein **Feld des Fensters**
(`_settings_dialog`), nicht auf eine gebundene Methode des Dialogs: der wird
nach `exec` weggeräumt, und ein Rückruf in ein zerstörtes C++-Objekt ist der
Absturz ohne Zeile.

### Ein Arbeiter erbt von `leash.Worker` und schreibt `work`

**Niemals direkt von `QThread`.** Ein `run`, das eine Ausnahme durchlässt,
sendet sein Ergebnissignal nie — und wer darauf wartet, wartet für immer.
Nachgestellt am Einrichtungsdialog für ComfyUI: Liegt die Installation unter
`Program Files`, wirft das Kopieren der Knoten einen `PermissionError`. Die
Ausnahme landet auf stderr, wo sie kein Kunde sieht; im Fenster steht „Wird
eingerichtet …", der Balken läuft, der Knopf sagt „Abbrechen" — und dabei
bleibt es, bis jemand das Programm beendet.

Von dreiundzwanzig Arbeitern fing genau **einer** eine unerwartete Ausnahme:
der Versand der Rückmeldung. Die anderen zweiundzwanzig konnten dasselbe
anrichten — die Ladeanzeige der Auswertung, der für den Rest der Sitzung
gesperrte Export-Menüeintrag, „Der Profilbestand wird durchgesehen …" als
Dauerzustand.

```python
class _Survey(Worker):
    done = Signal(object)

    def work(self) -> None:  # nicht run
        self.done.emit(install.statuses())
```

Zwei Pflichten hängen daran, und `tests/test_leash.py` prüft beide:

* **Erwartete Fehler bleiben in `work`** und kommen als *Ergebnis* zurück —
  `InstallResult.reason`, ein Satz von `pull_model`, ein eigenes Signal für
  `SetupFailed`. Was bei `crashed` ankommt, ist ausdrücklich das, womit niemand
  gerechnet hat.
* **`crashed` wird verbunden**, sonst ist der Fund nur verschoben. Wo ein
  Fehlerpfad existiert, geht das Unerwartete denselben Weg als `InternalError`
  — §33.1 ordnet ihm den Fehlerbericht zu, und genau der gehört dorthin. Wo
  keiner existiert, löst der Slot mindestens den Wartezustand: Balken weg,
  Knöpfe frei, ein Satz, der sagt, dass etwas schiefging.

**Und nach einem Absturz wird nicht neu erhoben.** Der Installationsdialog tat
das und überschrieb seine eigene Meldung eine Sekunde später mit der
Zusammenfassung der Erhebung — der Kunde hatte den Satz gesehen und nicht
gelesen.

### Ein Rückruf an ein eigenes Kind hält schwach

**Die allgemeine Form, und sie ist häufiger als ihre bekannten Fälle:** Ein
Rückruf, der `self` stark fängt, an einem Sender, der ein **Kind von `self`**
ist, schließt einen Ring — `self` → Sender → Rückruf → `self`. Er läuft über
die C++-Grenze, und Pythons Speicherbereiniger sieht die mittlere Kante nicht;
er kann den Ring also nicht brechen. Das Objekt lebt bis zum Prozessende.

```python
self.timer.timeout.connect(lambda: self.rebuild())  # Ring
self.button.clicked.connect(lambda: self.apply())  # Ring
button = QToolButton(self)
button.clicked.connect(lambda: self.apply())  # auch ein Ring
```

**Das Mittel ist fast immer die gebundene Methode, nicht `weakref`.** Qt hält
eine gebundene Methode von sich aus schwach; den Ring baut allein das Lambda.
Gemessen am selben Aufbau, je zehn Objekte losgelassen:

| Form | überleben |
|---|---|
| `connect(self.rebuild)` | **0 von 10** |
| `connect(lambda: self.rebuild())` | 10 von 10 |
| `connect(partial(self.rebuild, 1))` | 10 von 10 |
| `connect(lambda x=1: self.rebuild(x))` | 10 von 10 |
| `connect(lambda *_a, s=self: s.rebuild())` | 10 von 10 |

Bemerkenswert daran ist die dritte Zeile: `functools.partial` hilft **nicht**,
obwohl es wie die saubere Fassung eines Lambdas aussieht — es hält die
gebundene Methode und damit `self`. Dasselbe gilt für das Vorgabeargument, das
im Arbeiter-Abschnitt unten steht; dort ist es richtig, weil der Sender geht.

Also, in dieser Reihenfolge. **Erste Wahl, die gebundene Methode:**

```python
self.timer.timeout.connect(self.rebuild)
```

**Zweite Wahl, wo feste Werte im Spiel sind** — sie gehören in eine Methode und
nicht in ein Lambda:

```python
def _rebuild_layer(self) -> None:
    self.show_scene(self._result)
```

**Dritte Wahl, für Werte aus einer Schleife:**

```python
button.toggled.connect(weak_slot(self, Editor._tool_chosen, name))
```

`weak_slot` (`app/ui/leash.py`) bleibt für zwei Fälle, die die ersten beiden
nicht abdecken. Der eine ist ein Wert aus einer **Schleife**, der an den
Rückruf gebunden werden muss; es hält den Besitzer schwach und reicht den
Schleifenwert vor den Signalargumenten durch.

**Der andere ist ein Rückruf, der nicht an einem Signal landet.** „Die
gebundene Methode ist frei" gilt für Qt-Verbindungen — Qt hält sie schwach.
Ein gewöhnlicher Python-Container tut das nicht: `ToolStrip.add(…, self._end_split)`
legte die Methode in ein `Tool` und das in ein Wörterbuch, und damit hielt sie
das Fenster genauso fest wie ein Lambda. Der Unterschied ist nicht die Form des
Rückrufs, sondern **wer ihn aufbewahrt**.

Das war der letzte Halter des Hauptfensters, und er ist gefunden worden,
nachdem alle 27 Lambdas darin schon umgebaut waren.

Von Hand geschriebene `weakref.ref`-Blöcke braucht es nur noch, wo mehrere
Rückrufe zusammen entstehen — `viewport._weak_callbacks` ist der Fall, fünf
Stück für einen Interaktionsstil.

**Der Interactor ist ein Fall davon, nicht der Fall.** Diese Regel nannte lange
allein ihn — Stil → Viewport → Plotter → Interactor → Stil —, und deshalb hat
niemand nach einem Zeitgeber gesucht. Gefunden wurde einer in
`viewport.py:1428`: ein Lambda am eigenen `QTimer` der Schichtvorschau.
Gemessen, am 22.08.2026:

| | Viewports, die ihr `del` + `gc.collect()` überleben |
|---|---|
| mit dem Lambda | **20 von 20** |
| mit `weakref` | 0 von 20 |

Dieselbe Probe am reinen Qt-Muster ohne Solidon-Code, zwei `QObject` mit
eigenem `QTimer`: stark 10 von 10 überlebt, schwach 0 von 10.

**Was es kostet, am Hauptfenster gemessen** — fünf bauen, schließen, loslassen,
den Arbeitssatz des Prozesses ablesen:

| | Zuwachs je Fenster | überleben |
|---|---|---|
| vorher | +21, +28, +35, +42, +50 MB — linear | 5 von 5 |
| nachher | +17, +17, +18, +17, +18 MB — flach | 0 von 5 |

Die Kurve **sättigt**: Das erste Fenster kostet einmalig rund 17 MB für Qt und
VTK, jedes weitere kostet nichts mehr. Vorher wuchs sie ungebremst, und die
Suite baut über siebenhundert Fenster nacheinander auf.

**Und die Kehrseite, die erst am 23.08.2026 sichtbar wurde: Ein Fenster,
das sterben kann, kann im falschen Thread sterben.** Solange die Lambda-Ringe
die Fenster hielten, sammelte sie niemand ein. Seither tut es der
Speicherbereiniger — und der läuft in dem Thread, dessen Allokation gerade die
Schwelle reißt, nicht zwangsläufig im Hauptthread. Findet er dort ein Fenster
ohne letzte Python-Referenz, gibt er dessen **Python-Hülle** frei — und
shibokens Deallocator zieht die C++-Zerstörung nach sich, **in diesem
Thread**. Ein QWidget-Destruktor gehört nie dorthin: Er nimmt den Qt-Mutex
und braucht dann den GIL für die Hülle, während der Hauptthread den GIL hält
und auf genau diesen Mutex wartet. Das Ergebnis ist kein Absturz, sondern ein
**Stillstand** bei 0,00 CPU.

**Und es ist kein Menü-Problem, auch wenn der erste Abzug eines zeigte.**
Zweimal unabhängig gefangen, mit verschiedenen Paarungen: einmal `~QMenuBar` →
`~QMenu`, während der Hauptthread eine `QComboBox` aufbaute, einmal ein
beliebiges `~QWidget`, während er eine `QScrollArea` aufbaute. **Jedes**
Widget, dessen letzte Python-Referenz in einem Nebenthread fällt, kann es
auslösen; wer nur Menüs schützt, schützt zu wenig. Im zweiten Abzug steht
`SbkDeallocWrapper` ganz unten und benennt den Auslöser: Nicht Qt räumt auf,
sondern Pythons Speicherbereiniger.

Der vollständige Stapelabzug beider Threads steht in `tests/conftest.py`,
zusammen mit dem, was **nicht** hilft: `gc.collect()` (der Lauf im Hauptthread
ist der harmlose), `leash.undisturbed()` (es hält den gc dieser Zeile an,
während der Nebenthread weiter alloziert) und `deleteLater` (zweimal versucht,
beide Male an VTK gescheitert). Wer einen vierten Anlauf nimmt, liest zuerst
diese Notiz.

Der Ring-Umbau bleibt trotzdem richtig — er hat den Speicher von linear auf
flach gebracht. Aber er ist die Ursache dafür, dass es diesen Deadlock geben
kann, und wer ihn für unbeteiligt hält, sucht an der falschen Stelle.

**Kurzlebige Sender sind ausgenommen.** Ein Arbeiter, ein Dialog, eine
Animation bauen denselben Ring, und er löst sich auf, sobald der Sender geht;
dort ist das Vorgabeargument aus dem Abschnitt unten richtig und ausreichend.
Der Unterschied ist nicht die Form, sondern die Lebensdauer: Wer so lange lebt
wie `self`, hält `self` ewig.

**Gefunden wird so etwas nicht durch Suchen, sondern durch einen Test, der
eine Annahme festnagelt.** Der Fund kam aus einem Test, der etwas *anderes*
behauptete — dass die Rückrufe an den Interaktionsstil die Ansicht nicht
festhalten. Sie taten es nicht; er wurde trotzdem rot, und
`gc.get_referrers(view)` nannte den wahren Halter. Wer einen Verdacht hat,
nimmt denselben Griff:

```python
for holder in gc.get_referrers(widget):
    if type(holder).__name__ == "cell":  # eine Closure hält es
        for user in gc.get_referrers(holder):
            ...  # __qualname__ und __code__ nennen die Zeile
```

**Eine geschachtelte Funktion ist dasselbe wie ein Lambda.** `OperationDialog`
hatte `def unfold(open_now, inner=inner)` in seinem Aufbau; die Form sieht
harmloser aus, die Zelle hält denselben Ring. Wer nach Lambdas grept, findet
sie nicht — `gc.get_referrers` schon.

**Und eine gebundene Methode hält ihr Objekt genauso.** Zwei Fälle am
23.08.2026, beide außerhalb jeder Signalverbindung:

* `QTimer.singleShot(0, self, self._render_pending)` in `PartCatalog` —
  die Kette reiht sich selbst neu ein, und jede eingereihte gebundene Methode
  hält den Katalog. Zehn losgelassene überlebten alle zehn. Sie hat jetzt ein
  `release()`, das die Kette anhält.
* `release = getattr(widget, "release", None)` in einer **Schleife** —
  nach dem letzten Durchgang steht in der Variablen das letzte Objekt.
  Betroffen waren `tests/test_widget_lifetime.py` und die Aufräum-Fixture in
  `tests/conftest.py`. Der Griff dagegen ist die ungebundene Funktion von der
  Klasse: `getattr(type(widget), "release", None)`, aufgerufen mit dem Widget
  als erstem Argument.

**Die Zahl selbst war dabei der Hinweis.** Der Test meldete „1 von 10
überlebten", dreimal reproduzierbar — nie null, nie zehn. Ein Ring hält
*jedes* Objekt; eine Eins ist ein Zeiger auf genau eine Referenz, und die
findet man, statt sie für Streuung zu halten.

### Wer eine `WorkerLeash` hält, hat ein `release()`

Wie man einem Fenster sagt, dass Schluss ist, hieß an jeder Klasse anders —
`release`, `wait_for_workers`, `wait_for_survey`, `wait_for_look`,
`wait_for_setup`, und an vier Klassen gar nichts. Wer eine Testfixture darauf
baut, sammelt Namen: Sie kannte zwei von fünf, dann drei, dann vier, und beim
fünften starb der Prozess beim Abbau an einem Thread, der sein Fenster
überlebt hatte.

Alle elf tragen jetzt `release()`, und es ruft intern das, was die Klasse
schon kann. **Die fachlichen Namen bleiben daneben**: `wait_for_survey` gibt
einen Wahrheitswert zurück und steht im Produktivcode (`FirstRunDialog.reject`),
`release` räumt auf und gibt nichts zurück. Zwei Sachen, zwei Namen — nur soll
die eine überall gleich heißen. `tests/test_widget_lifetime.py` liest per
`ast`, wer eine Leine anlegt, und verlangt von jedem dasselbe Wort; ein
sechster Name kann nicht mehr unbemerkt entstehen.

**Der Parameter gilt der Leine, nicht der Sache.** `release()` reichte seine
2000 ms an `wait_for_look` weiter, wo 30 000 stehen — damit bekam eine
Erhebung, die eine halbe Minute haben darf, zwei Sekunden. Gemessen an
`test_chat_ui`: 2 von 4 Läufen starben danach beim Abbau, gegen 4 von 4 nach
der Berichtigung. Die fachliche Methode wird ohne Argument gerufen.

### Loslassen allein räumt nicht auf

Der Weg, den `MainWindow` beim Schließen geht, und der einzige, der in einem
Test dasselbe misst:

```python
release(widget)  # von der Klasse geholt, siehe oben
leash.wait_for_all()
application.processEvents()  # mehrfach: ein finished reiht selbst wieder ein
gc.collect()
```

**Der `processEvents`-Schritt ist der, den man vergisst**, und ohne ihn liest
man ein Leck, wo keines ist: `leash._alive` hält einen Arbeiter modulweit, der
hält über sein `finished`-Lambda die Leine und damit den Dialog; abgeräumt
wird erst, wenn das Signal ankommt.

| | überleben |
|---|---|
| nur loslassen | 10 von 10 |
| `release()` | 10 von 10 |
| `release()` + Schleife | 0 von 10 |

Dass die mittlere Zeile sich nicht bewegt, ist der Grund, warum drei Klassen
zwei Monate lang als „hält, aber erklärbar" in einer Ausnahmeliste standen.

### `isVisible()` und `hasFocus()` lügen in einem nie gezeigten Fenster

Beide melden falsch, solange das Fenster nie gezeigt und nie aktiviert wurde —
also in jedem Offscreen-Lauf. Zweimal am 23.08.2026 zugeschnappt, einmal im
Code und einmal im Test:

* Eine Bedingung `if self.measure_field.isVisible()` im `keyPressEvent` hätte
  in der ganzen Suite nie gegriffen. Gefragt wird stattdessen nach der Sache:
  `if self.pending_measure() > 0.0`.
* Ein Test `assert field.hasFocus()` prüft, ob die Testumgebung ein aktives
  Fenster hat. Geprüft wird stattdessen die Wirkung: kommt die Ziffer im Feld
  an?

`isVisibleTo(eltern)` ist die brauchbare Frage, wenn es wirklich um
Sichtbarkeit geht — sie beantwortet „würde es erscheinen, wenn das Fenster
erschiene".

### Wer einen Arbeiter startet, hält ihn fest

Ein `QThread` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

**Nie als Lambda, das blind `None` schreibt:**

```python
worker.finished.connect(lambda: setattr(self, "_worker", None))  # falsch
```

Das geht zweimal schief. `finished` kommt, während Qt den Thread noch abräumt —
zu früh zum Loslassen. Und es trifft das Feld, nicht den Arbeiter: wird ein
Vorgänger fertig, nachdem sein Nachfolger im Feld steht, löscht er dessen
Referenz.

**Richtig** ist ein benannter Slot, der seinen *eigenen* Arbeiter erkennt und
ihn danach der gemeinsamen Halteleine übergibt:

```python
worker.finished.connect(lambda done=worker: self._worker_done(done))


def _worker_done(self, worker: Any) -> None:
    if self._worker is worker:
        self._worker = None
    self._hold_until_done(worker)
```

`_hold_until_done` legt ihn in `_retired` und lässt ihn erst los, wenn
`isRunning()` nein sagt. Ein ersetzter Arbeiter geht denselben Weg über
`_retire`. `wait_for_workers` wartet am Ende auf alle — auch auf die in
`_retired`, sonst überlebt einer sein Fenster und nimmt den Prozess mit.

**Gestartet wird über `WorkerLeash.start`, nicht über `worker.start()`.** Das
ist die wichtigere Hälfte derselben Regel, und sie fehlte: Gehalten wurde erst,
wenn ein Arbeiter *fertig* war — solange er lief, hing er allein am Feld seines
Dialogs. Ein Dialog, der vorher freigegeben wird (ein Fenster räumt ihn weg,
ein Test lässt ihn fallen), nimmt damit die letzte Referenz auf einen
**laufenden** `QThread` mit, und genau dagegen gibt es dieses Modul.

Sichtbar wurde es, als die Erstinbetriebnahme ihre Erhebung in einen Arbeiter
bekam: `tests/test_first_run.py` brach reproduzierbar an der Stelle ab, an der
ein Dialog aus einem vorigen Test einging. Betroffen war auch die
Werkzeugprobe des Chat-Dialogs, die es seit je gibt.

```python
worker.done.connect(self._show)
worker.finished.connect(lambda done=worker: self._worker_done(done))
self._worker = worker
self._leash.start(worker)  # hält ab diesem Moment, nicht ab dem Ende
```

Zwei Dinge hängen daran, und beide sind nötig: Die Menge der gehaltenen
Arbeiter ist **modulweit** (`leash._alive`) und nicht an der Leine — mit dem
Dialog stirbt sonst die Liste. Und der Zeitgeber, der nachsieht, ob ein Thread
ausgelaufen ist, hängt an einem Objekt, das die Widgets überlebt
(`leash._keeper`); an das Widget gebunden feuert er nach dessen Tod nie, und
der Arbeiter bliebe für immer gehalten.

Das Feld am Dialog bleibt — es ist danach nur noch die Antwort auf „läuft
gerade einer", nicht mehr die einzige Referenz.

**Fünfzehn Arbeiter hielten sich nicht daran, und gefunden hat sie kein
Suchen.** Ein `grep` nach `worker.start()` findet die Hälfte; die andere heißt
`self._worker.start()`. `tests/test_leash.py` liest deshalb den **Quelltext**
aller Dateien unter `app/ui/` — und zwar am Quelltext, weil das Verhalten es
nicht zeigt: Ein Arbeiter an der Leine vorbei läuft völlig normal, bis das
Fenster unter ihm weggeräumt wird. Dieselbe Bauart wie der Wächter, der jedes
`ResultCache(` ohne `disk=` findet.

Aufgefallen ist es an einer Frage zur Aufräum-Fixture der Suite: Wer über
`leash.alive()` melden will, wer einen Test überlebt hat, sieht nur, was über
`WorkerLeash.start` gestartet wurde — eine Zusicherung darüber verspricht sonst
mehr, als sie halten kann.

### Ein Dialog, der beim Öffnen nachsieht, öffnet erst danach

Dreimal derselbe Fund an drei Stellen, jedes Mal gemessen: Die Liste der
zusätzlichen Programme brauchte 2,97 Sekunden bis auf den Bildschirm, die
Erstinbetriebnahme 1,88, der Chat-Dialog 2,98. Der Grund war jedes Mal
dasselbe — im Konstruktor stand, was ein Programm sucht, eine Profildatei
liest oder einen Port fragt.

Das gehört in einen Arbeiter (§38), und der Dialog zeigt sofort seine Fragen.
Drei Dinge machen den Unterschied zwischen „geht auf" und „geht auf und lügt":

* **Kein Zustand ohne Erhebung.** Wo die Antwort fehlt, steht „Wird
  nachgesehen …" — nicht „fehlt", und kein Knopf, der auf eine Vermutung
  wirkt.
* **Eine Erhebung, nicht drei.** Die Liste fragte je Zeile dreimal dasselbe,
  bei den Diensten mit je einer Socket-Probe. Ein `Status`-Typ, der in einem
  Durchgang entsteht, ist billiger als drei Aufrufe, die sich gegenseitig nicht
  kennen.
* **Ein nachgereichter Vorschlag überschreibt keine Wahl.** Der Drucker aus
  dem Slicer-Profil kommt Sekunden später — wer in der Zwischenzeit selbst
  gewählt hat, behält seine Wahl (§2.4).

Und eine Methode, auf die Erhebung zu warten (`wait_for_survey`,
`wait_for_look`), gehört dazu: Ein Test, der sie nicht abwartet, prüft den
leeren Zustand, und ein Dialog, der mit laufender Suche zugeht, verwaist einen
Thread.

**Und er meldet auch nichts mehr.** Die Regel darüber galt als Sache der
Stabilität; sie ist genauso eine der Anzeige. Ein Nachzügler, der
`busyChanged(False)` sendet, räumt Balken, Abbrechen und Ladeanzeige eines
Laufs ab, der noch rechnet — sichtbar an der Stelle, an der jeder anfängt:
Eine Datei auf den Startbildschirm zu ziehen legt zwei Läufe hintereinander
(das leere neue Projekt, dann den Import), und bei 1,3 Millionen Dreiecken war
die Anzeige nach einer Zehntelsekunde weg und die restlichen vier Sekunden
stumm. Dasselbe gilt für sein Ergebnis: eingeblendet wurde die leere Szene des
Vorgängers über dem Modell, das gerade lud (§15.3). `Session._outdated`
beantwortet die Frage für alle vier Abschluss-Slots; ein Aufruf ohne Absender
(Tests, Kommandozeile) gilt als aktuell.

**Ein Ersetzen ist dabei kein Aufhören.** Steht `_rerun_pending`, folgt der
nächste Lauf sofort — dann wird kein `False` gemeldet, sonst flackert die
Anzeige beim Ziehen an einem Schieber im Sekundentakt. Dieselbe Begründung,
aus der `evaluationCancelled` einen ersetzten Lauf nicht meldet.

## Der Mauszeiger

Zeiger kommen aus `app/ui/cursors.py`, nie als `Qt.CursorShape` an der
Aufrufstelle. `cursor(rolle, widget)` gibt entweder eine eigene Zeichnung im
Akzent oder eine Systemform zurück — welche, entscheidet das Modul und nicht
der Anrufer.

Drei Dinge, die man beim Zeichnen einer neuen Rolle wissen muss:

* **Silhouette schlägt Bildidee.** Bei 32 Punkten wird ein Zeiger nicht
  gelesen. Der Schnittzeiger trug zuerst denselben Körper wie das Symbol der
  Werkzeugzeile und war ein Fleck mit Strich; erst die grobe Form — Linie,
  darüber und darunter eine Hälfte — erzählt etwas. **Angesehen wird auf vier
  Untergründen**: Viewport dunkel, Akzent (ein gewählter Körper!), Körpergrau,
  helles Thema.
* **Jede eigene Zeichnung trägt den dunklen Saum.** Der Akzent liegt über
  einem gewählten Körper auf sich selbst und wäre ohne ihn weg. Er entsteht
  aus zwei Durchgängen über dieselben Pfade, dick dunkel und dünn im Akzent.
* **Wo das System eine bekannte Form hat, gewinnt sie** (`SYSTEM`): geschlossene
  Hand beim Schieben, Verschiebekreuz am Griff. Sie folgt der eingestellten
  Zeigergröße und dem Hochkontrastmodus, unsere täte das nicht.

**Ein Maß in Millimetern gehört nicht an den Zeiger.** Der Pinselradius ist der
Fall, an dem das auffällt: Ein Zeiger hat feste Punktgröße und weiß nichts von
der Kamera — beim ersten Zoom behauptet er eine Größe, die er nicht mehr hat.
Was ein Weltmaß zeigt, gehört als Ring in die Szene.

**Gesetzt wird an einer Stelle**, `Viewport._update_cursor`. Alle Auslöser
melden nur ihren Zustand: `set_painting`, `set_measure_mode`,
`set_drag_cursor` (vom Interaktionsstil) und die Mausbewegung im
`eventFilter`. Verteilt auf die Aufrufer wäre jeder Pfad für sich richtig und
das Ergebnis trotzdem falsch — wer beim Loslassen den Auswahlzeiger setzt,
überschreibt damit den Pinsel. Die Rangfolge in `_resting_role` ist dieselbe
wie in `_on_picked`; laufen sie auseinander, verspricht der Zeiger etwas
anderes, als der Klick tut.

Drei Fallen an dieser Kette, alle drei schon zugeschnappt:

* **`setMouseTracking(True)`** auf dem Interactor, sonst kommt eine Bewegung
  erst mit gedrückter Taste — der Zeiger wüsste nie, worüber er schwebt.
* **VTK zählt Y von unten, Qt von oben.** Ohne die Umrechnung in
  `_note_pointer` sucht das Hover-Picking am gespiegelten Ort, was in der
  Bildmitte oft genug stimmt, um lange nicht aufzufallen.
* **Der Rückruf aus dem Interaktionsstil geht über `weakref`**, wie
  `on_context` und `on_pick` daneben (alle fünf in `_weak_callbacks`). Eine
  starke Referenz baut die Schleife Stil → Viewport → Plotter → Interactor →
  Stil, und die ist der Absturz ohne Zeile am Ende eines Laufs. Das ist **ein**
  Fall der allgemeinen Regel und nicht der einzige — sie steht oben unter „Ein
  Rückruf an ein eigenes Kind hält schwach", samt der Messung, die zeigt, dass
  ein Zeitgeber dasselbe anrichtet.

**Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`, einmaliger
Timer). Bei jeder Bewegung zu picken hieße, den Tiefenpuffer hunderte Male in
der Sekunde im Qt-Hauptthread zu lesen. Ein Zug an der Kamera stoppt die Suche
ganz — wer dreht, will nicht wissen, was unter dem Zeiger liegt.

**Offscreen gibt es keinen Plotter**, und jeder Setzpfad steigt vorher aus: Ein
Test, der nur `_cursor_role` prüft, wäre auch dann grün, wenn im Fenster nie
ein Zeiger ankommt. `tests/test_cursors.py` hält deshalb eine Attrappe mit
genau der einen Methode, die benutzt wird.

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

**Ein Widget braucht die `QApplication` in der Signatur, nicht im Glück.** Wer
ein Widget ohne sie baut, bringt den ganzen Lauf mit 0xC0000409 um — ohne ein
Wort Ausgabe, nur mit einem Rückgabewert. In der vollen Datei fällt das nicht
auf, weil ein früherer Test die Anwendung schon gebaut hat; ob das passiert,
entscheidet `pytest-randomly`. Also nimmt jeder Test, der ein Widget anfasst,
`qt_app` oder eine Fixture, die darauf aufbaut — auch der, der scheinbar nur
eine Zeichenkette prüft.

## Die Ansicht

### Die Auswahl hat eine Tiefe, und der Klick wandert durch sie

Drei Stufen: nichts, ein Körper, ein Merkmal (`Viewport.selection_depth`).
**Links wandert, rechts fragt** — und diese Aufteilung ist der Kern:

* **Der Linksklick geht eine Stufe.** Der erste wählt den Körper, der nächste
  das Merkmal unter dem Zeiger. Das Modell von Figma und Illustrator: erst die
  Gruppe, dann das Element darin. Vorher gewann sofort das Merkmal, und ein
  Körper mit erkannten Bohrungen war per Klick **überhaupt nicht auswählbar** —
  wer die Platte verschieben wollte, musste in den Objektbaum ausweichen.
* **Der Rechtsklick meint immer das Genaueste** (`_select_at(..., direct=True)`).
  Das folgt aus §18.5: Dort ist das Kontextmenü *am Merkmal* der Ort für Weg 1,
  „indem man auf die Stelle zeigt, die stört". Gestuft wäre diese Zusage an eine
  Vorbedingung geknüpft, die niemand kennt.
* **Ein offener Operationsdialog schaltet die Stufen ab**
  (`set_direct_picking`). Dann ist ein Klick eine *Antwort* und keine
  Navigation, und zwei Klicks für eine Antwort sehen aus wie ein verschluckter
  erster.
* **Escape geht zurück**, eine Stufe je Druck, hinter dem offenen Werkzeug in
  der Rangfolge von `MainWindow._escape`. Ohne ihn ist die Tiefe eine
  Einbahnstraße.

Zwei Dinge daran sind leicht falsch zu machen:

**Die Stufe wird aus der Auswahl gelesen, nicht nebenher geführt.** „Im Körper
drin" heißt genau „ein Merkmal dieses Körpers ist gewählt". Ein eigenes Feld
daneben wäre eine zweite Wahrheit — die Auswahl kommt auch aus dem Objektbaum,
und der weiß von keinem Feld im Viewport. Dazu kommt: `objectPicked` läuft
synchron durch den Baum zurück und setzt `_selected`, also muss die Stufe
**vor** dem Senden gelesen werden.

**Der Zeiger stellt dieselbe Frage mit derselben Rechnung**
(`_would_pick_feature` → `_click_target`). Das ist die schon bekannte Regel bei
`_resting_role`, einen Schritt weiter: Ein Zeiger, der die Merkmalsform über
einer Bohrung zeigt, während der Klick den Körper wählt, verspricht etwas, das
nicht eintritt. So wird die Stufe zugleich sichtbar, ohne dass ein Satz darüber
irgendwo stehen muss.

### Ein Merkmal hat eine Reichweite

`_feature_at` hatte keine, und das war der gemeldete Fehler: Es nahm das
Merkmal mit dem nächsten **Mittelpunkt**, es gab also immer einen Gewinner,
sobald der Körper ein Merkmal hatte. An der Korpusplatte wählte ein Klick auf
die Deckfläche sieben Millimeter neben einer Bohrung die Bohrung (8,1 mm zum
Bohrungsmittelpunkt gegen 36,1 mm zur Mitte der 80 mm langen Deckfläche), und
ein Klick nahe der Stirnseite wählte die Stirnfläche.

Gemessen wird gegen die **Dreiecke** des Merkmals
(`geom.mesh.distance_to_triangles`), gegen den nächsten Ort *auf* dem Dreieck
und nicht gegen den nächsten Eckpunkt — die Deckfläche der Platte hat zwei
Dreiecke, ein Klick in ihre Mitte liegt vierzig Millimeter von jedem Eckpunkt
entfernt. Die Reichweite wächst mit der Diagonale (`FEATURE_REACH_SHARE`),
weil im dezimierten Anzeigenetz gepickt wird (§18.9).

Drei Folgen davon:

* **Ein Klick trifft die Oberfläche, nie die Achse.** Der Mittelpunkt einer
  Bohrung liegt im Leeren. Drei Tests zeigten dorthin und prüften damit die
  Rechenweise statt einen Klick; wer einen neuen schreibt, nimmt die
  Bohrungswand (`on_the_bore_wall`).
* **Ein Merkmal ohne eigene Dreiecke bleibt über seinen Mittelpunkt
  erreichbar** — eine offene Kantenschleife hat keine, und sie ist der Befund,
  den man am ehesten anklicken will.
* **Vorbereitet wird je Körper und Auswertung** (`_feature_geometry`), mit dem
  Hüllquader als billiger Vorprüfung: Die Frage stellt der Zeiger bei jeder
  Ruhepause neu (90 ms), und der genaue Abstand ist nur für die ein oder zwei
  Merkmale nötig, deren Quader ihn überhaupt erreicht. Geleert wird in
  `show_scene` — die Dreiecke gehören einer Auswertung, nicht dem Viewport.

**Und jeder Klickpfad rechnet über `_from_view` in die Szene zurück** (§25).
Der Rechtsklick tat es nicht und die Zeigersuche auch nicht: Auf Platte 2
fragten beide eine Bettbreite daneben, fanden dort meist keinen Körper, und der
Rechtsklick hob die Auswahl auf, statt das Menü zu ihr zu zeigen.

### Ein Klick ist eine Blickrichtung, kein Punkt

Der Abschnitt darüber setzt voraus, dass unter dem Zeiger ein Dreieck liegt.
**Bei einer Bohrung liegt dort keines**, und das war der zweite gemeldete
Fehler an derselben Stelle: „wir erwischen oft nur die Oberfläche und kommen
nicht zur Bohrung". Gemessen am echten `vtkCellPicker` in einem sichtbaren
Fenster, Korpusplatte, Bohrung 32 Bildpunkte breit, Pixel neben der
Bohrungsmitte:

| | Draufsicht | Isometrisch | Vorderansicht |
|---|---|---|---|
| 0–8 px | **kein Treffer** | `hole_1` | `face_3` |
| 12 px | `hole_1` | **kein Treffer** | `face_3` |
| 16 px | `face_2` | `face_2` | `face_3` |

Zwei Ursachen, und beide liegen vor der Reichweite:

* **Senkrecht in eine Durchgangsbohrung trifft der Strahl nichts.** Die
  Zylinderwand liegt parallel zu ihm, dahinter kommt keine Fläche. Der Picker
  gab nichts zurück, `_on_left_click` machte daraus `objectPicked.emit("")` —
  ein Klick mitten in die Bohrung **hob die Auswahl auf**. Ausgerechnet in der
  Ansicht, in der man ein Lochbild anklickt.
* **Landet der Strahl daneben auf der Deckfläche, gewinnt sie immer.** Ihr
  Abstand ist null, der der Bohrung größer als null; die Reichweite ist eine
  Obergrenze und kein Vorrang. Gemessen gab schon ein Punkt 0,4 mm neben dem
  Bohrungsrand `face_2`, bei einer Reichweite von 0,95 mm.

Gefragt wird deshalb der **Sichtstrahl** (`_pick_ray` → `_bore_aim`, gerechnet
in `bore_span`): Welche Bohrung durchquert er, bevor er auf dem Sichtbaren
landet? Drei Eigenschaften daran sind tragend:

* **`until` ist der Auftreffpunkt, und ohne diese Grenze wird es falsch.** In
  der Vorderansicht liegt hinter der Stirnfläche jede Bohrung der Platte; was
  der Strahl erst dahinter durchquert, hat niemand gemeint. Die dritte Spalte
  oben ist die Gegenprobe und bleibt unverändert `face_3`.
* **Der Achsbereich kommt aus den Dreiecken des Merkmals**, nicht aus `depth`
  und nicht aus dem Hüllquader — der kennt die Achse nicht, und eine schräge
  Bohrung hat beides. Ohne die Begrenzung reicht der Zylinder unendlich weit
  und eine Bohrung am einen Ende fängt Klicks am anderen.
* **Zurück kommt ein Punkt auf der Achse**, nicht der Auftreffpunkt. Damit
  bleibt die ganze Kette dahinter unberührt — Stufung, Kontextmenü und Zeiger
  bekommen einen Punkt wie immer, und von einem Punkt im Loch findet
  `_feature_inside` die Bohrung. Auf der Achse und nicht in der Mitte des
  Durchtritts: Ein Punkt über der Öffnung liegt der Deckfläche näher als der
  Bohrungswand, und dann gewinnt wieder die Fläche.

Der entartete Fall ist der wichtigste und der einzige, den man leicht verliert:
**Blickt man senkrecht in die Bohrung, läuft der Strahl parallel zur Achse**,
es gibt keinen Ein- und Austritt durch den Mantel, und die quadratische
Gleichung dazu hat keinen Leitkoeffizienten. Wer dort durch null teilt,
verliert genau die Draufsicht.

**Gefragt wird an drei Stellen, und an allen drei derselbe Aufruf**
(`_aim_at`): Linksklick, Rechtsklick, Zeigersuche. Der Zeiger kostet damit
einen Zell-Pick je Ruhepause statt eines Blicks in den Tiefenpuffer — gemessen
0,16 ms, und die Zusage darunter ist es wert: Ein Zeiger, der die
Merkmalsform über einer Bohrung zeigt, wo der Klick sie nicht wählt,
verspricht etwas, das nicht eintritt. **Nicht** gefragt wird beim Messen,
Bemalen und Ziehen — dort ist eine Stelle auf der Oberfläche gemeint, und ein
Punkt in der Luft wäre falsch.

**Und die Reichweite wirkt hier als Zielhilfe**, nicht als Grenze: Gezielt wird
in Pixeln, und der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals, denn es ist
dieselbe Frage — wie weit daneben meint noch dies. Bei 24 Pixeln, also weit
außerhalb der Bohrung, bleibt es die Fläche.

### Was gefärbt wird

**Die Auswahlfarbe gehört dem Genauesten, was gewählt ist.** Ein Klick auf eine
Bohrung wählt zweierlei aus, den Körper und die Stelle; gefärbt wird die Stelle.
`highlighted_object()` gibt `None` zurück, solange ein Merkmal gewählt ist, und
`highlighted_faces()` nennt dessen Dreiecke — beide als eigene Auskunft, weil es
offscreen keinen Plotter gibt. Dass der Körper trotzdem ausgewählt ist, steht im
Objektbaum und in der Statusleiste; dieselbe Ausnahme gilt für einen Körper unter
einer Analysekarte (§19.1). Das gewählte Merkmal trägt seine Beschriftung auch
bei ausgeschalteter Überlagerung — ohne sie wäre die Aussage allein die Farbe
(Regel 18).

Gerechnet wird gegen das Netz der Szene, nicht gegen das dezimierte
Anzeigenetz: `face_indices` zählt dort. Den Unterschied fängt der Versatz
entlang der Flächennormalen ab (`FEATURE_PATCH_LIFT`).

Umgebungsverdeckung und Kontaktschatten weichen, solange eine Analysekarte
läuft: beide dunkeln nach, und die Karte färbt nach Zahlen — der abgelesene
Wert wäre ein anderer als der gemeldete. Beide hängen deshalb an einer
Eigenschaft (`ambient_occlusion`, `contact_shadows`) und nicht am Zustand des
Plotters: offscreen gibt es keinen, und ein Test, der sich dort überspringt,
prüft nie etwas.

Der Kontaktschatten ist **selbst projiziert**, nicht `enable_shadows`: VTKs
Schattenwurf verschattet ganze Seitenflächen schwarz und lässt die Ränder der
Platte auslaufen. Geworfen wird schräg — senkrecht projiziert liegt der
Schatten unter dem Körper und ist von ihm verdeckt.

**Der Schatten folgt der Kamera, weil das Licht es tut.** pyvistas Lichtsatz
hängt an der Kamera: ein Körper ist in jeder Ansicht von vorn beleuchtet. Eine
feste Weltrichtung für den Schatten passt deshalb zu *keinem* Blickwinkel —
sie stand hier, mit einer Begründung, die auf eine Standardansicht verwies, die
es so nicht gab. `shadow_direction` leitet sie aus der Kamerastellung ab,
`_redraw_shadows` zieht sie bei jedem Ansichtswechsel nach. Der Beobachter
hängt am **Interactor** (`EndInteractionEvent`) und nicht am Interaktionsstil:
den tauscht jeder Schemawechsel aus, und der Orientierungswürfel dreht an ihm
vorbei.

**Die Anwendung setzt ihre Startkamera selbst.** Ohne `view_from("iso")` beim
Aufbau erbt sie pyvistas Stellung über (1, 1, 1), und die eigene Vorgabe aus
`VIEW_DIRECTIONS` sieht nur, wer „Isometrisch" im Menü wählt — ein Sprung aus
einer Ansicht in eine andere, die man zu sehen glaubte.

**Ein Schatten fällt auf die Fläche, auf der sein Körper steht.** Nicht immer
auf die Platte: `_shadow_catchers` sucht zu jedem Körper die Flächen unter ihm
— die Druckplatte und jeden Körper, dessen Oberkante nicht höher liegt als
seine Unterkante. Ohne das löst sich der Schatten eines Turms auf einer 12 mm
hohen Grundplatte von ihm ab und taucht erst daneben auf. Beide Stücke werden
gezeichnet, und das ist kein Widerspruch: Licht, das an der Grundplatte
vorbeigeht, trifft die Druckplatte, und weil jedes Stück am Umriss seiner
Fläche geschnitten wird (`clip_polygon`, Sutherland-Hodgman), verdeckt die
Grundplatte genau den Teil, der sonst doppelt läge. Dasselbe Schneiden hält den
Schatten auf der Platte: außerhalb lag er auf blankem Hintergrund und
behauptete Boden, wo keiner ist. Die Plattenkante kommt aus `_bed_extent`,
gemerkt in `show_build_volume` — ohne gezeigten Bauraum gibt es nichts zu
schneiden. **Und sie gehört der Platte des Körpers**, nicht der ersten
(`_bed_outline_for`): seit die Betten nebeneinander stehen, liegt der Umriss
eines Körpers auf Platte 2 eine Bettbreite weiter, und am Umriss von Platte 1
geschnitten wäre sein Schatten restlos weg.

## Mehrere Druckplatten

Jede Platte hat ihren eigenen Nullpunkt, und `arrange_bed` setzt Platte 2 an
denselben Ort wie Platte 1 — das ist richtig, denn beide werden einzeln
gedruckt. Ein Bett für alle zeigt davon das Falsche: zwei identische Sockel
lagen Punkt auf Punkt übereinander, und gemeldet wurde es als „bei Projekten
mit mehreren Platten sehe ich trotzdem nur eine".

`show_build_volume` zeichnet deshalb **ein Bett je Platte**, mit `PLATE_GAP`
nach +X aufgereiht (`plate_shift`); eine gewählte Einzelplatte bekommt wieder
genau eines. Drei Dinge hängen daran:

* **Die erste Platte bleibt, wo sie ist.** Nach +X und nicht um die Mitte
  verteilt: Eine Szene mit einer Platte sieht danach Bild für Bild aus wie
  vorher, und wer eine zweite dazubekommt, sieht sie kommen statt die erste
  wegrutschen zu sehen.
* **Die Actors tragen die Nummer im Namen.** pyvistas `name=` ersetzt, was
  denselben Namen hat — mit festen Namen bliebe von vier Betten eines übrig.
* **Ein Klick muss zurückgerechnet werden** (`plate_at`, `_from_view`, ganz oben
  in `_on_picked`). Was der Nutzer trifft, liegt in der Ansicht; was eine
  Operation als Ort bekommt, muss in der Szene liegen. Ohne die Umkehrung setzte
  ein Klick auf Platte 2 die Bohrung eine Bettbreite daneben — und weil dort
  meistens nichts ist, hätte sie stumm nichts getan.

Der Versatz liegt mit dem Auseinanderziehen (§18.8) zusammen in
`_view_offset`, damit jede Zeichenstelle beides bekommt oder keines. Was
**nicht** mitgeht, sind die Überlagerungen in Szenenkoordinaten — Maße,
Schnittebene, Griffe. Sie folgten schon dem Auseinanderziehen nicht; das gehört
zusammen behoben, nicht halb.

**Was je Bild neu gerechnet wird, wird je Körper vorbereitet.** Der
Schattenumriss lief als Triangulierung über jeden Punkt des Anzeigenetzes: 129
ms bei zweiundachtzigtausend Dreiecken, je Körper und Szenenaufbau, im
Qt-Hauptthread. Die konvexe Hülle steht einmal (`_shadow_hull_of`), ein
Ansichtswechsel projiziert nur noch daraus. Und sie bekommt einen Kostendeckel:
bei einer feinen Kugel liegt *jeder* Punkt auf der Hülle, und die Rechnung wäre
teurer als das, was sie ersetzt. Über `SHADOW_HULL_POINTS` genügt eine
Stichprobe — plus die äußersten Punkte in vierzehn Hauptrichtungen, sonst
verliert ein gescannter Halter seine Ecken.

Zahlen an Bildern werden **angesehen, nicht nur gerechnet**. Der Radius der
Umgebungsverdeckung stand mit plausibler Begründung auf dem schwächsten Wert
seiner Messreihe; der doppelte ViewCube fiel erst im neu aufgenommenen
Handbuchbild auf. Beim Schatten war es dieselbe Sorte Fehler: der Kommentar
beschrieb, wohin er fallen sollte, und niemand hatte nachgesehen, wohin er
fiel.

**Ein Layout, das nur bei der geprüften Breite stimmt, ist ungeprüft.** Drei
Fehler wurden am selben Tag sichtbar, und alle drei erst, als das Handbuch die
Fenster bildschirmfüllend aufnahm statt in einem Kasten von 1180 Punkten: Der
Bausteinkatalog legte seine Gruppen ineinander, weil der Kachelmodus seine
Zeilen beim Einfügen rechnet und ein späteres `setSizeHint` nur speichert —
`doItemsLayout()` nach einer echten Änderung. Die zehn Bedingungsknöpfe der
Skizze blieben in zwei Zeilen à fünf, weil diese Aufteilung für den
Laptopschirm gedacht war und seither überall galt. Und das Raster der
Zeichenfläche war ein halber Millimeter fein, weil `MIN_GRID_PX` auf sieben
stand — ein Wert, der bei kleinem Fenster nie auffiel. Wer eine Ansicht ändert,
sieht sie bei **beiden** Enden an: der Mindestgröße und dem vollen Bildschirm.

**pyvista-Widgets werden nie weiterbenutzt, immer frisch gebaut.** Das
`AffineWidget3D` rechnet gegen die `user_matrix` seines Actors und merkt sie
sich über Züge hinweg — ein stehen gelassener Griff wendet den vorigen Zug
beim nächsten doppelt an, und nach einer Auswertung hängt er an einem Actor,
der nicht mehr im Bild ist. Und die API vor dem Aufruf lesen: `Off()` gab es
dort nie (`remove()`, `disable()`, `enable()` sind die Methoden), der
AttributeError verschwand in Qts Slot-Behandlung und fiel nirgends auf. Ein
Fake im Test spiegelt deshalb die **echte** API-Oberfläche, nicht die
vermutete — ein Fake mit `Off()` hätte den Absturz genau so versteckt wie
die Suite.

Zwei Nachbarn derselben Falle: pyvistas Widget schaltet beim Greifen auf
seinen Trackball-Stil um und stellt beim Loslassen **seinen** Standard
wieder her, nicht unseren — jedes Zugende ruft deshalb `set_navigation`,
sonst sind Auswahl-Klick, Kontextmenü und Schema nach dem ersten Zug weg.
Und der Skaliergriff (`app/ui/scale_widget.py`) ist diesem Widget
absichtlich Zeile für Zeile nachgebaut — wer dort etwas am
Interaktionsmuster ändert, ändert es an beiden Stellen.

## Die Zeichenfläche

Der Skizzeneditor hat eigene Regeln, und sie laden mit ihm:
`zeichenflaeche.md`.
