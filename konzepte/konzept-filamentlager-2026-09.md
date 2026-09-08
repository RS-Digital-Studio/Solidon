# Konzept: Das Filamentlager

> **Stand: ENTWURF mit getroffenen Entscheidungen, 08.09.2026.** Im Code ist
> nichts davon gebaut; die vier Fragen, die der Entwurf offenließ, hat Robert
> am selben Tag delegiert und stehen in §13 entschieden. Auftrag Robert: „Auf der Startseite einen
> Button, wo man zu seinem Filamentlager kommt. Hier sollen Regale mit den
> Filamenten sein (schön modern visualisiert), die der Nutzer hat und hier
> anlegen und bearbeiten kann. Außerdem sollen diese Filamente dann in einer
> Schnellauswahl in den Projekten immer vorhanden sein."
>
> **Nachtrag Robert am selben Tag:** „Die Menge an Material bei einem Druck
> soll auch abgezogen werden bzw. nachgefragt werden, wenn wir auf slicen
> klicken, im Slicer öffnen oder die 3MF-Datei erstellen." Das ändert §8 —
> dort stand vorher, Solidon solle gar nicht buchen.
>
> Nichts davon ist gebaut. Die Hälfte davon liegt aber schon da, und das ist
> der Grund, warum dieses Konzept mit dem Bestand anfängt und nicht mit dem
> Entwurf.

---

## 1. Was es schon gibt

Der Filamentkatalog ist seit dem 28.08.2026 in Betrieb (Konzept
[Filamente statt nummerierter Slots](konzept-filamente-2026-08.md), Bauplan
§20). Er kann mehr, als man ihm ansieht:

| Was | Wo | Zustand |
|---|---|---|
| Katalog aus Name, Farbe, Materialart, Slicer-Profil | `app/core/knowledge/filaments.py` | projektübergreifend im Einstellungsordner, atomar geschrieben, beliebig viele Einträge |
| Anlegen, Ändern, Löschen, Sammelübernahme | `remember`, `forget`, `synchronise` | vollständig, mit Prüfung von Name und Farbe |
| Übernahme der im Slicer eingelegten Spulen | `slicer_filaments()` im Wähler | vorhanden, mit Hersteller- und Materialfilter |
| Auswahl beim Zuweisen | `app/ui/filament_picker.py` | drei Quellen: belegte Slots, Katalog, freie Nummern |
| Druckwerte je Filament | `handover.settings_for_slot` | Temperatur, Kühlung, Rückzug, Materialwerte |
| Materialverbrauch eines Drucks in Gramm | `app/core/slice/estimate.py` (`Estimate.grams`) | gerechnet mit der Dichte des eingestellten Filaments |

**Was daraus folgt:** Das Lager ist kein neues Gebiet, sondern ein Ort für ein
Gebiet, das keinen hat. Heute erreicht man seine Spulen nur, indem man ein
Projekt öffnet, einen Körper wählt und etwas färben will. Wer wissen möchte,
was er im Regal hat, muss so tun, als wolle er etwas anderes.

---

## 2. Die eine Entscheidung, an der alles hängt

In `filaments.py` steht der Satz, der das Lager blockiert:

> Ein Filament ist sein Name: Wer „PETG Rot" noch einmal anlegt, meint dasselbe
> Filament mit anderer Farbe, nicht ein zweites.

Für einen Katalog ist das richtig. Für ein Lager ist es falsch: Im Regal liegen
**zwei** Spulen PETG Rot, eine angebrochen mit 240 Gramm, eine ungeöffnet. Ein
Lager, das sie nicht auseinanderhalten kann, beantwortet die einzige Frage
nicht, die man ihm stellt — „reicht das noch?".

Drei Wege, und sie unterscheiden sich in den Folgekosten erheblich:

**A — Der Katalog bleibt die Sorte, der Bestand hängt an ihr.** Ein Eintrag
„PETG Rot" trägt „1,4 Spulen" oder „580 Gramm gesamt". Kostet nichts an
Migration, weil der Name Schlüssel bleibt. Verliert die angebrochene Spule als
Einzelding — und genau die ist die interessante.

**B — Ein Eintrag ist eine Spule, mit eigener Kennung.** Das Regal zeigt, was
im Regal liegt. Der Schlüssel wird eine Kennung, der Name wird ein Etikett, das
mehrfach vorkommen darf. Kostet: Kennungen vergeben, Katalogformat erhöhen,
`slot_profiles` und die Vorwahl vom Namen auf die Kennung umschlüsseln,
Migration alter Kataloge (Name wird Kennung).

**C — Zwei Ebenen: Sorte und Spule.** Sauber, und für einen Einzelnutzer
mit zwanzig Spulen zwei Bildschirme statt einem.

**Entschieden: B** (Robert hat die Wahl am 08.09.2026 delegiert). Das Regal ist
ein Bild der Wirklichkeit, und in der
Wirklichkeit liegen Spulen, keine Sorten. Die Gruppierung nach Sorte ist dann
eine Ansichtssache — das Regal stellt gleiche Etiketten nebeneinander ins
selbe Fach, ohne dafür eine zweite Datenebene zu brauchen. Die Migration ist
einmalig und additiv: Ein alter Katalogeintrag wird eine Spule ohne
Bestandsangabe, seine Kennung leitet sich aus dem Namen ab, und jede
Projektdatei, die auf den Namen zeigt, findet sie weiter.

---

## 3. Das Datenmodell

Additiv zu `CatalogueFilament`; jedes neue Feld hat eine Vorgabe, damit ein
alter Katalog unverändert öffnet.

| Feld | Bedeutung | Vorgabe |
|---|---|---|
| `identifier` | stabile Kennung der Spule | aus dem Namen abgeleitet |
| `name` | Etikett, darf mehrfach vorkommen | Pflicht, wie heute |
| `colour`, `material_type`, `slicer_profile` | unverändert | wie heute |
| `diameter_mm` | 1,75 oder 2,85 | 1,75 |
| `spool_grams` | Nettogewicht der vollen Spule | 1000 |
| `remaining_grams` | geschätzter Rest | gleich `spool_grams` |
| `location` | Regalfach, Trockenbox, Schrank — freier Text | leer |
| `opened_on`, `bought_on` | Daten, für die Trockenfrage | leer |
| `price` | Anschaffungspreis **der Spule**, nicht je Kilo — man kauft Spulen | leer |
| `note` | alles, was sonst nirgends passt | leer |
| `bookings` | Verlauf der Abzüge: Zeitpunkt, Menge, Projekt, Herkunft der Zahl, Projektstand | leer |

**`density` kommt nicht dazu.** Sie steht in den Druckeinstellungen
(`settings.filament.density`), und zwei Wahrheiten über dieselbe Zahl sind eine
zu viel. Das Lager liest sie, wo sie steht.

**Der Preis ist kein Buchhaltungsfeld.** Er dient einer einzigen Antwort:
„Dieser Druck kostet 1,80 Euro Material." Wer ihn leer lässt, verliert nur
diese Zeile.

---

## 4. Der Weg hinein

**Von der Startseite** (Bauplan §2.3): eine eigene Kachel in der Mittelspalte,
unterhalb der Beispiele, nicht in der Knopfzeile. Die Knopfzeile trägt schon
vier Einträge und beantwortet die Frage „womit fange ich an" — das Lager ist
keine Antwort darauf. Die Kachel folgt dem vorhandenen Kartenmuster aus
`start_screen.py` (`StartActionCard`, Schattentiefe, Anheben unter dem Zeiger)
und zeigt statt eines Symbols **die Farben der eingelagerten Spulen als Reihe**.
Damit ist der Zustand des Lagers auf der Startseite sichtbar, bevor man es
öffnet — und ein leeres Lager lädt mit „Noch keine Spule eingetragen" ein,
statt eine leere Fläche zu zeigen.

**Aus dem Projekt heraus**: ein Eintrag im vorhandenen Menü, das die
Einstellungen trägt. **Kein neues Hauptmenü** — `MAX_MENUS = 9` in
`tests/test_interface_limits.py` ist keine Empfehlung, und ein Lager rechtfertigt
keinen zehnten Kopf in der Leiste.

**Als was**: eine Ansicht im vorhandenen `QStackedWidget` des Hauptfensters,
neben Startseite und Arbeitsfläche — kein eigenes Fenster. Ein zweites Fenster
müsste seinen Zustand mit dem ersten abgleichen; die geteilte Katalogdatei
verträgt das schlecht (siehe §9). Zurück führt derselbe Weg wie von der
Startseite in ein Projekt.

---

## 5. Das Regal

Nicht eine Liste mit Farbtupfern, sondern das Regal, das der Nutzer vor sich
hat.

**Die Spule.** Von vorn gezeichnet: zwei Flanken, dazwischen der Wickel in der
Filamentfarbe. Der Füllstand ist **die Wickeldicke** — bei einer vollen Spule
reicht der Ring fast bis zur Flanke, bei einer angebrochenen wird der Kern
sichtbar. Das ist die Darstellung, die jeder sofort liest, weil sie stimmt.
Darunter das Etikett: Name, Materialart, Restmenge in Gramm.

**Regel 18 ist hier keine Formalie.** Der Füllstand darf nie allein über die
Farbe oder allein über das Bild sprechen: Die Restmenge steht als Zahl daneben,
und wer wenig hat, bekommt zusätzlich das Wort — „fast leer" ab einem
einstellbaren Rest. Eine schwarze und eine dunkelblaue Spule sind sonst
dasselbe Bild.

**Das Fach.** Spulen mit gleichem Etikett stehen nebeneinander in einem Fach,
Fächer stapeln sich zu einem Regal. Sortiert wird nach Materialart, dann nach
Name; ein Suchfeld filtert. Wer `location` gepflegt hat, kann stattdessen nach
Lagerort gruppieren — dann bildet das Regal auf dem Bildschirm das Regal im
Raum ab, und das ist der Moment, in dem das Feature aufhört, hübsch zu sein,
und anfängt, nützlich zu sein.

**Gezeichnet wird mit QPainter oder SVG, nicht im Viewport.** Das Lager braucht
keine 3D-Schicht, keine Grafikkarte und keinen `pygfx`-Kontext; es muss auch
auf einem Rechner aufgehen, dem die Ansicht fehlt.

**Modern heißt hier:** großzügige Abstände, weiche Schatten wie auf den
Startkacheln, ein ruhiges Anheben unter dem Zeiger, keine Rahmen. Dieselbe
Formsprache wie die Startseite — ein zweiter Stil im selben Programm wäre
teurer und schlechter.

---

## 6. Anlegen und Bearbeiten

Der Dialog dafür existiert (`filament_picker.py`, „Neues Filament") und bekommt
die Bestandsfelder dazu — **einen Dialog, nicht zwei**. Wer im Projekt eine
Spule anlegt, legt sie im Lager an; wer sie im Lager ändert, ändert sie im
Projekt.

Drei Wege hinein, alle drei schon vorhanden oder billig:

1. **Von Hand** — Name, Typ, Farbe, Gewicht.
2. **Aus dem Slicer** — `slicer_filaments()` liest die eingelegten Filamente
   mitsamt Herstellerprofil; im Lager wird daraus ein Mehrfach-Übernehmen mit
   Haken statt einer Einzelwahl.
3. **Als Kopie** — „Noch eine davon": die zweite Spule derselben Sorte in
   einem Klick, voll. Das ist der Weg, der aus dem Katalog ein Lager macht.

Löschen bleibt `forget`, mit dem Hinweis, dass Projekte, die diese Spule
benutzen, ihre Farbe behalten — die Zuweisung steht in der Projektdatei, nicht
im Katalog. Kein Bestätigungsdialog (Regel 19), sondern Rückgängig.

---

## 7. Die Schnellauswahl im Projekt

Robert: „immer vorhanden". Heute ist die Auswahl ein Feld in einem Dialog, plus
seit 0.3.5 die Filamente des gewählten Körpers in der Auswahl-Karte.

**Vorschlag:** eine Filamentzeile in der Auswahl-Karte, dauerhaft sichtbar,
sobald ein Körper gewählt ist. Links die im Projekt belegten Slots als
beschriftete Farbchips, rechts durch eine Trennlinie abgesetzt die Spulen aus
dem Lager. Ein Klick weist zu, das Überfahren zeigt Name, Typ und Restmenge.
Kein Dialog für den häufigen Fall; der volle Wähler bleibt einen Klick
entfernt für alles andere.

**Die Achtergrenze wird erklärt, nicht durchgesetzt.** `MAX_SLOTS = 8` ist die
Wirklichkeit des 3MF-Farbwechsels. Wer die neunte Spule anklickt, bekommt
keinen stumpfen Fehler, sondern die Frage, welches der acht belegten Filamente
sie ersetzen soll (Regel 17, Regel 21).

---

## 8. Der Abzug: wann gefragt wird, und mit welcher Zahl

**Entschieden (Robert, 08.09.2026): Der Verbrauch wird abgezogen, und gefragt
wird an dem Punkt, an dem das Material den Rechner verlässt.** Vier Stellen
gibt es dafür, und sie sind im Code schon benannt:

| Auslöser | Wo | Welche Zahl |
|---|---|---|
| *Slicen* | `print_settings_dialog.py` | **aus dem G-Code**, je Extruder |
| *Im Slicer öffnen …* | `print_settings_dialog.py` | Schätzung |
| *An den Slicer übergeben …* | `panels.py` | Schätzung |
| *Exportieren …* als 3MF | `main_window.py`, Strg+E | Schätzung |

Die dritte Zeile stand nicht in Roberts Aufzählung und gehört dazu: Sie ist
derselbe Vorgang wie *Im Slicer öffnen*, nur von der Auswahlkarte aus
angestoßen. Zwei Wege in dieselbe Handlung, von denen einer bucht und der
andere nicht, wären ein Fehler, den niemand erklären kann.

**Die Zahl trägt ihre Herkunft, und die beiden werden nie vermischt**
(Regel 14, Bauplan §22.5). Nach dem Slicen liegt eine Druckdatei vor, und
`slice/gcode.py` liest daraus `filament used [g]` — je Extruder einzeln. Das
ist der wahre Wert und wird als solcher gebucht. Die drei anderen Wege haben
nur `Estimate.grams`; dort steht „geschätzt" an der Buchung, im Regal und im
Verlauf. Wer später sieht, dass 42 g geschätzt und 47 g gemessen waren, weiß
warum.

**Gefragt wird nach dem Vorgang, nicht davor** (Regel 19). Kein modaler Dialog
schiebt sich vor den Export — die Handlung läuft, und danach steht in der
Statuszeile eine Leiste: „47 g PETG Rot und 6 g PLA Weiß abziehen?" mit
*Abziehen*, *Andere Spule …* und *Nicht buchen*. Sie verschwindet von selbst,
wenn niemand sie beachtet; ein nicht gebuchter Druck ist ein gültiger Zustand,
kein Defekt.

**Drei Fälle, die dieses Feature falsch machen kann, und ihre Antworten:**

*Doppelt buchen.* Wer erst *Im Slicer öffnen* klickt und dann *Slicen*, hat
einmal gedruckt und würde zweimal abziehen. Deshalb hängt die Frage nicht am
Klick, sondern am **Ergebnis**: Solidon vermerkt zur Buchung, für welchen
Projektstand sie galt. Derselbe unveränderte Stand fragt nicht noch einmal,
sondern sagt „am 8.9. um 14:12 schon gebucht" und bietet das erneute Buchen an
— für den, der wirklich ein zweites Mal druckt. Nach der geschätzten Buchung
korrigiert der echte G-Code-Wert die vorhandene Buchung, statt eine zweite
anzulegen.

*Die falsche Spule.* Liegen zwei Spulen derselben Sorte im Regal,
schlägt die Leiste die **angebrochene mit dem kleinsten ausreichenden Rest**
vor — sonst wandert der Verbrauch auf die volle und die Reste sterben nie.
*Andere Spule …* öffnet die Wahl. Ist die Farbe im Lager gar nicht vorhanden,
wird nicht gebucht, sondern angeboten, sie anzulegen.

*Es reicht nicht.* Wenn der Rest kleiner ist als der Bedarf, sagt das die
Leiste **vor** dem Buchen und im Druckeinstellungs-Dialog schon vorher — als
Hinweis, nie als Sperre. Wer weiß, dass seine Spule mehr trägt, als das Lager
glaubt, hat recht und nicht das Lager.

**Jede Buchung ist rücknehmbar**, und dafür führt jede Spule einen kurzen
Verlauf: Zeitpunkt, Menge, Projektname, Herkunft der Zahl. Er beantwortet die
Frage, die sonst niemand beantworten kann — wo ist das Material geblieben —
und macht einen Fehlabzug in einem Klick rückgängig.

**Eine Einstellung mit drei Werten**, Vorgabe die mittlere: *nie buchen*,
*fragen*, *ohne Rückfrage buchen*. Wer den dritten Wert wählt, hat den Abzug
ausdrücklich verlangt — und nur dann verstellt sich der Bestand ohne
Zutun.

---

## 9. Fallen

- **Die Katalogdatei ist geteilter Zustand.** Lager-Ansicht und Projekt
  schreiben dieselbe `filaments.json`; wer sie zeitgleich anfasst,
  überschreibt still. Deshalb eine Ansicht im selben Fenster (§4) und ein
  Neulesen vor jedem Schreiben, nicht ein im Speicher gehaltener Stand.
- **Der Schlüsselwechsel Name → Kennung reicht weiter, als er aussieht.**
  `settings.slot_profiles` schlüsselt heute über den Namen; das Konzept von
  2026-08 hat dieselbe Stelle schon einmal umgeschlüsselt. Wer sie diesmal
  vergisst, erbt nach dem Update stumm falsche Zuordnungen.
- **Kein Qt im Kern** (Regel 1): Bestand und Migration in
  `knowledge/filaments.py`, Zeichnung und Regal in `app/ui/`.
- **Sechs Kataloge** (Regel 20): Jede Zeichenkette über `tr()`, und ein Feature
  mit vielen kleinen Texten ist genau das, bei dem eine Sprache hängenbleibt.
- **Der Kunde pflegt nur, was ihm sofort etwas gibt.** Deshalb ist die
  Reihenfolge in §11 so gewählt: erst Regal und Sichtbarkeit, dann Bestand.
  Ein Lager, das beim ersten Öffnen leere Felder verlangt, wird einmal
  ausprobiert und nie wieder geöffnet.

---

## 10. Was nicht gebaut wird

Keine Anbindung an einen Shop, keine Preisabfrage im Netz, kein Konto, keine
Synchronisierung zwischen Rechnern — Solidon bleibt ohne Netz vollständig
nutzbar. Keine Fremdabhängigkeit an eine bestehende Lagerverwaltung. Kein
Barcode- oder NFC-Zwang, keine Waagenanbindung, kein Trocknungstimer mit
Sensorik. **Kein Abzug ohne Zutun** — gebucht wird auf Antwort, und ohne
Rückfrage nur, wer das ausdrücklich einstellt (§8). Und keine zweite
Formsprache: Das Regal sieht aus wie der Rest der Anwendung.

---

## 11. Reihenfolge und Aufwand

| Schritt | Inhalt | Aufwand |
|---|---|---|
| 1 | Kennung statt Name als Schlüssel, Katalogformat erhöhen, Migration, `slot_profiles` nachziehen | mittel, und der einzige Schritt mit Rückwärtsrisiko |
| 2 | Regalansicht mit Spulenzeichnung, Suche, Gruppierung; Einstieg von der Startseite und aus dem Menü | groß, aber ohne Kernrisiko |
| 3 | Bestandsfelder im vorhandenen Dialog, „Noch eine davon", Mehrfachübernahme aus dem Slicer | klein |
| 4 | Schnellauswahl in der Auswahl-Karte, Achtergrenze als Frage | mittel |
| 5 | Der Abzug an allen vier Auslösern: Leiste nach dem Vorgang, Buchung mit Herkunft, Verlauf je Spule, Rücknahme, die drei Einstellungswerte | mittel |

Die Schritte 1 bis 3 stehen für sich: Danach hat das Lager seinen Ort, sein
Bild und seinen Inhalt, auch wenn 4 und 5 nie kämen. Schritt 5 ist der, an dem
die Sorgfalt sitzt — nicht in der Rechnung, sondern in der Frage, wann **nicht**
gebucht wird.

---

## 12. Abnahmekriterien

1. Ein frisch installiertes Solidon öffnet das Lager von der Startseite aus in
   einem Klick und zeigt dort einen leeren Zustand, der beide Wege hinein
   nennt: von Hand anlegen oder aus dem Slicer übernehmen. Vorgefüllt ist
   nichts.
2. Zwei Spulen desselben Namens lassen sich anlegen, unterscheiden und einzeln
   bearbeiten; ein Katalog aus 0.3.5 öffnet unverändert und verliert nichts.
3. Der Füllstand ist ohne Farbwahrnehmung ablesbar (Regel 18, geprüft im
   Barrierefreiheitstest).
4. Eine im Lager geänderte Farbe steht im geöffneten Projekt zur Wahl, ohne
   Neustart.
5. Die Schnellauswahl weist ein Filament ohne Dialog zu; der neunte Versuch
   nennt seine Grenze und bietet den Tausch an.
6. Alle Texte liegen in allen sechs Katalogen; `test_translations` ist grün.
7. Das Lager öffnet auf einem Rechner ohne funktionierende 3D-Ansicht.
8. Jeder der vier Auslöser aus §8 bietet den Abzug an, keiner bucht von selbst
   (außer bei ausdrücklich gewählter Einstellung), und kein modaler Dialog
   steht vor dem Export.
9. *Im Slicer öffnen* und danach *Slicen* auf demselben Stand erzeugen **eine**
   Buchung, und die zweite Zahl korrigiert die erste, statt sie zu addieren.
10. An jeder Buchung steht, ob ihre Zahl gemessen oder geschätzt ist; beide
    werden nirgends zu einer Summe vermischt (Regel 14).
11. Eine Buchung lässt sich aus dem Verlauf der Spule zurücknehmen.

---

## 13. Die vier Entscheidungen

Robert hat sie am 08.09.2026 delegiert. Sie stehen hier mit ihrer Begründung,
damit sie widerlegbar bleiben — wer eine davon umdreht, weiß, was sie gekostet
hat.

**1. Eine Spule ist ein Eintrag** (Weg B aus §2). Der Schlüssel wird eine
Kennung, der Name ein Etikett, das mehrfach vorkommen darf. Die beiden anderen
Wege scheitern an derselben Stelle: Die angebrochene Spule ist die
interessante, und sie ist nur als eigenes Ding zu führen.

**2. Der Bestand steht in Gramm, die Anzeige nennt beides.** Gramm sind die
Einheit, in der `Estimate.grams` rechnet — aus Gramm und `spool_grams` folgen
Prozent, umgekehrt nicht. Eingetragen wird trotzdem so, wie man schätzt: ein
Schieber „ungefähr noch" von voll bis leer, der in Gramm umrechnet und den
Zahlenwert daneben zeigt. Ein Feld, zwei Darstellungen — nicht zwei Felder, die
sich widersprechen können.

**3. Der Preis kommt hinein, freiwillig.** Er kostet ein Feld und bringt die
Zeile „dieser Druck kostet 1,80 Euro Material" — die einzige Zahl, die einen
Druck mit etwas vergleichbar macht, das man kaufen könnte. Gespeichert wird
eine blanke Zahl; das Währungszeichen kommt aus dem Gebietsschema der
Anwendung, weil sie in sechs Sprachen läuft und ein hart eingetragenes Euro in
der portugiesischen Fassung falsch wäre. Wer das Feld leer lässt, verliert nur
diese Zeile.

**4. Das Lager füllt sich beim ersten Start nicht von selbst.** Die
Slicer-Übernahme steht als Knopf im leeren Zustand, neben „Spule von Hand
anlegen" — angeboten, nicht ausgeführt. Der Grund ist der Zweck des Regals: Es
soll zeigen, was **im Raum** liegt. Die Slicer-Liste ist eine Konfiguration und
sagt darüber nichts; ein vorgefülltes Regal wäre auf den ersten Blick voll und
auf den zweiten falsch, und ein falscher Bestand ist schlechter als ein leerer
(dasselbe Argument wie gegen den automatischen Abzug in §8).
