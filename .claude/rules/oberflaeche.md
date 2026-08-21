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
sein eigener Name ist — M4, 6x3, mm, x, DejaVu Sans, gyroid. Bilder statt
Wörter, wo ein Wort nichts zeigt: die Texturmuster tragen ihre Kachel aus
`figures.texture_tile`, erkannt an den Werten des Feldes und nicht an seinem
Namen. Ein Fehler endet nie mit „fehlgeschlagen": erst was nicht ging, dann
warum, dann was jetzt möglich ist, als anklickbare Handlungen (§2.7). Kein
Stapelabzug im Nutzerdialog.

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

**Und er heißt nicht wie sein Werkzeug.** Der Umschalter der Werkzeugzeile
nennt das Werkzeug, der Knopf darin seine Handlung — „Trennen" oben, „Jetzt
trennen" unten. `tests/test_interface_limits.py` hält das fest.

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
gerissen werden:

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 — **erreicht**: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen, Bemalen — auf `Alt+1` bis `Alt+8` |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
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
  `on_context` und `on_pick` daneben. Eine starke Referenz baut die Schleife
  Stil → Viewport → Plotter → Interactor → Stil, und die ist der Absturz ohne
  Zeile am Ende eines Laufs.

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

## Die Ansicht

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
