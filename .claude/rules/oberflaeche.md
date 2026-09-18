---
description: "Die Oberfläche allgemein — Texte über tr(), Zahlen, gestufte Tiefe, Barrierefreiheit, Tests am Fenster; Fenster, Grenzen, Ansicht, Wartezeit und Zeichenfläche stehen in eigenen Dateien"
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

**Und die zweite Ausnahme verlässt das Dokument** (§29, RM-140): Eine
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

## Texte

Keine feste Zeichenkette in der Oberfläche — alles über `tr()`, deutsche
Quelle, und jeder Katalog aus `app/i18n/locales/` zieht nach. **Das gilt auch
für Auswahlwerte**: `raised`, `flat`, `linear` sind
Schlüssel und keine Beschriftungen. Der Name steht in `_CHOICE_NAMES`
(`app/ui/labels.py`), und `tests/test_translations.py` lässt nur durch, was
sein eigener Name ist — M4, 6x3, mm, x, DejaVu Sans.

**Eine Tabelle, und Auswahlwerte stehen an zwei Stellen.** Die
Druckeinstellungen führen ihre sechsundfünfzig Felder in einer eigenen Liste
(`print_settings_dialog.FIELDS`) — eine zweite Namenstabelle davor verdeckt
die erste und läuft auseinander. Der Test prüft deshalb **beide Feldquellen**
gegen die eine Tabelle; wer eine dritte Liste von Auswahlwerten anlegt, hängt
sie dort ein.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Wo der englische Begriff der ist, unter dem der Kunde die Sache in seinem
Slicer wiederfindet, bleibt er stehen: `skirt`, `brim` und `raft` heißen so,
und die Felder daneben heißen „Skirt-Runden", „Brim-Breite",
„Raft-Schichten" — ein Wert, der anders heißt als sein Feld, ist eine Fährte
ins Nichts. Dasselbe gilt für Algorithmennamen (`gyroid`, `arachne`).

**Jedes Feld sagt, was es tut — und zwar alle.** Das gilt an zwei Orten: Die
sechsundfünfzig Felder der Druckeinstellungen tragen je einen `note`-Satz, die
1197 Parameter der 132 Operationen ihren `doc`-Satz aus dem Register. Beide Male
hängt er an **beiden** Hälften der Zeile — wer eine Zeile nicht versteht, zeigt
auf das unverständliche Wort und nicht auf den Kasten daneben. In den
Druckeinstellungen setzt `_editor` ihn am Eingabefeld und `_label` an der
Beschriftung; im Operationsdialog holt `QFormLayout.labelForField` die
Beschriftung, die `addRow` aus der Zeichenkette gebaut hat (`_explain` in
`op_dialog.py`). Ist eine Zeile gesperrt, tragen beide
Hälften den *Grund* statt des Satzes — in ein ausgegrautes Feld zeigt niemand,
man zeigt auf das Wort davor.

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
Stapelabzug im Nutzerdialog.

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

Und beim Tauschen eines Katalogtexts muss der **alte Schlüssel hinaus**:
`test_every_text_is_translated` prüft beide Richtungen und meldet ihn sonst als
„no longer used". Zwei gegenläufige Zusicherungen decken einander.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

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

## Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn die zwei bis drei Werte, die man ändert; hinten
Toleranzen, Auflösungen, Rückfallverhalten. Die Vorgaben kommen aus dem
Drucker- und Materialprofil. **Eine gute Vorgabe ist mehr wert als eine gute
Einstellmöglichkeit.**

**Ein vorbelegter Wert kommt nach vorn — außer er ist eine Richtung.** Der
Dialog holt, was gerade entschieden wurde, vor die Klappe: die angeklickte
Fläche, die vorgewählte Position (§18.5, `decided` in `op_dialog.py`). Der
Klick trägt aber auch die Normale der Fläche ein, drei Zahlen, von denen je
nach Fläche eine ungleich null ist — und die stand dann vorn: *Normale Z* an
der Oberseite, *Achse* und *Normale X* an der linken, ein Dialog, der bei
jeder Bohrung anders aussah (Durchsicht 14.09.2026). Eine Vektorkomponente
tippt niemand von Hand. `direction_fields` (die Normale aus
`normal_fields_of`, dazu `axis`) bleibt hinten; der Wert gilt trotzdem.

**Die Vorgabe trifft den Körper, nicht den Ursprung.** *Teilen* beginnt in
der Mitte des gewählten Körpers (`_plane_through`, 13.09.2026), *Dreiecke
verringern* bei der Hälfte seiner Dreiecke und *Dreiecke angleichen* bei einem
Fünfzigstel seiner längsten Kante (`_measured_from_body`, `EDGE_SHARE`,
14.09.2026). Feste Zahlen trafen entweder das große Teil oder das kleine:
50 000 Dreiecke an einer Platte mit wenigen hundert ließen das Band „am
Volumen ändert sich nichts" sagen, und 1,0 mm waren an 200 mm grob und an
5 mm zerstörerisch. Gefragt wird nach den **Feldern** (`axis`/`position`,
`triangles`, `edge` in Millimetern), nicht nach dem Namen der Operation; die
Zahl bleibt im Feld und lässt sich ändern. *Druckplatten* bleibt bei seinem
Höchstwert: Das Feld steht hinter der Klappe und ist eine Obergrenze, keine
erwartete Zahl.

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

**Und der Satz kommt, wo es geht, vor den Dialog.** Elf der Dialoge ohne
Bild konnten am gewählten Körper nie etwas tun; drei davon sagen es seit dem
14.09.2026 am Menüeintrag (`requires_body`, `operationen.md`): *Offene Fläche
schließen* an einem geschlossenen, *In Einzelteile zerlegen* an einem Stück,
*Gitter füllen* ohne Hohlraum. *Deckel erzeugen* und *Drehdeckel erzeugen*
fragen seit der Bedienweg-Durchsicht die **gewählte Fläche**
(`lid.reason_against`, im Fenster einmal je Merkmal und Auswertung gerechnet,
unter derselben Dreiecksgrenze wie die Körperfakten): An einer massiven Platte
standen sie an jeder Fläche bedienbar und konnten nur scheitern. Ebenso *An
Merkmal ausrichten*, dessen Ziel ein zweiter Körper mit Merkmal ist
(`_NEEDS_TARGET`; das Ziel ist seither Pflicht, und der Dialog sperrt mit
demselben Satz, wenn die Liste leer ist). Was bleibt, ist *Teilen* auf einer
Ebene, die nichts trifft — das hängt an einer Zahl, die erst im Dialog
entschieden wird; dort trägt das Band den Satz.

## Und die Tabulatortaste geht denselben Weg wie das Auge

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

## Für alle heißt: dasselbe Maß, nicht dieselbe Stelle

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

## Ein Nachweis gehört der Gruppe, nicht jeder Handlung

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

## Barrierefreiheit

- **Keine Bedeutung allein über Farbe** (Regel 18). Immer eine zweite
  Kodierung: Muster, Schraffur, Symbol, Beschriftung.
- **Aber auch keine Bedeutung ohne Farbe, wo Farbe die Sache ist.** Ein
  Materialslot ohne eigene Farbe darf in der Ansicht nicht die Körperfarbe
  tragen — sonst ist das Bemalen im Bild folgenlos. `theme.slot_colour` gibt
  die Ersatzfarbe (sieben Einträge; Slot 0 ist das unbemalte Teil und bekommt
  `None`); im **Dokument** steht sie nicht, denn keine Farbe zu haben ist ein
  Zustand, den „Slot zuweisen" auflöst. Die Zahl daneben bleibt: Die
  Pinselleiste zeigt Farbfeld **und** Name, „neu" für einen Slot, den der
  gewählte Körper noch nicht hat.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)
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
  wird ohne sie nicht angeboten.
- **Ein Klick auf einen Befund bleibt nie folgenlos.** Er ist die Geste, die
  §2.7 dem Prüfbericht ausdrücklich verspricht. Zwei Hürden — ein
  Operationsfehler trägt weder Ort noch Merkmale (der Kern gibt ihm `object_id`
  und `op_id`), und der Ort eines Kartenbefunds steht erst fest, wenn die Karte
  gerechnet ist, was beim ersten Klick nie der Fall ist.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

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
keiner. Fünfzehn der hundertzweiunddreißig Operationen führen eines; wer eine sechzehnte Taste
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

Wer den Zustand in einem Test setzt, bekommt ihn zurückgesetzt
(`tests/conftest.py`); sonst nähme ein Test jeden folgenden mit.

## Tests

Oberflächentests laufen offscreen (`QT_QPA_PLATFORM=offscreen`, von
`tests/conftest.py` gesetzt). Eine neue Ansicht ohne Test in `tests/test_ui.py`
oder einer der spezielleren Dateien ist unfertig.

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
`ansicht.md`, dazu `griffe.md` und `kamera.md`.

## Wartezeit und Nebenläufigkeit

Ebenso — `wartezeit.md` lädt mit `session.py`, `loading.py`, `leash.py`,
`splash.py` und `main_window.py`.

## Was am 18.09.2026 von hier weggezogen ist

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
