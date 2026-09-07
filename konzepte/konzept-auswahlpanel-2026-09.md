# Konzept: Ein Ort für die Auswahl (07.09.2026)

**Status:** entschieden in den Punkten A bis H (Robert, 07.09.2026), Umsetzung
als Serie P1 bis P6 im Register von `ROADMAP.md`. Der Ist-Stand unten ist am
Code gemessen, nicht aus der Doku übernommen.

**Gemessen gegen den Arbeitsbaum vom 07.09.2026 nach `975bd6bf`** („Die rechte
Spalte trennt sich, und ihre Aktionen folgen der Auswahl"). Dieser Commit ist
die unmittelbare Vorarbeit: Er hat die Auswahlkarte von der Berichtskarte
getrennt und ihre Hauptaktionen an Art und Menge der Auswahl gebunden. Was
dieses Konzept beschreibt, setzt darauf auf — die Befunde unten sind **nach**
dieser Arbeit erhoben und keiner davon ist durch sie erledigt.

**Anlass:** Robert hat am 07.09.2026 die laufende Anwendung mit
`weg2-halter-konstruieren.p3d` durchgesehen und neun Befunde genannt — von der
Mehrfachauswahl im Bild bis zu den grauen Knöpfen an einer gewählten Fläche.
Sieben davon haben zwei gemeinsame Ursachen; deshalb ist das ein Konzept und
keine Liste von neun Fixes.

---

## 1. Die zwei Ursachen

**Erstens: Es gibt zwei Panels für dieselbe Frage.** Das Merkmalpanel
(`FeaturePanel`, `panels.py`) liegt im Dock `featureDock` rechts, das
Auswahl-Panel (`SelectionOperationsPanel`, `selection_operations.py`) in der
Overlay-Spalte über der Ansicht. Beide beantworten „was kann ich mit dem
Gewählten tun". Bei einer gewählten Senkung zeigt das Dock die Handlungen als
Felder mit Zahlen und das Panel dieselben drei als Knöpfe — *Merkmal ändern*,
*Merkmal verschieben*, *Merkmal entfernen*, an zwei Orten, in zwei
Darstellungen.

Daraus folgen vier Befunde unmittelbar: der Wunsch, beides
zusammenzulegen; der Formatverlust der Berichtskarte, weil zwei Karten sich
eine Spalte teilen müssen; die Zeile „1 Objekt gewählt" über
Merkmalshandlungen; und der Knopf *Merkmale*, der nichts tut außer vom einen
Ort zum anderen zu führen.

**Zweitens: Die Auswahl hat eine Tiefe, das Panel kennt nur eine Zahl.**
Bauplan §18.5 legt fest: der erste Linksklick wählt den Körper, der nächste
das Merkmal darunter. `SelectionOperationsPanel.set_context` bekommt aber
`selected: int` — die Zahl gewählter Körper — plus die Merkmalsart. Die
Freigabe je Knopf entscheidet `MainWindow._palette_availability`, und die
fragt dieselbe Körperauswahl. Ein gewähltes Merkmal hat immer einen Körper
unter sich, also gelten die Körperhandlungen als anwendbar.

Gemessen am geladenen Register (07.09.2026):

| | Anzahl |
|---|---|
| Operationen im Register | 102 |
| davon im Panel als Körperhandlung | 38 |
| davon im Panel als Merkmalshandlung | 17 |
| Merkmalsarten in `applies_to` | 6 |

Die 38 Körperhandlungen stehen also auch dann in der Liste, wenn eine Fläche
gewählt ist — darunter *Auf dem Bett anordnen*, *Objekt duplizieren*,
*Objekt umbenennen*, *Druckoptimal ausrichten*. Keine davon wird je an einer
Fläche ausgeführt.

---

## 2. Ist-Stand, Befund für Befund

Alle Belege sind Fundstellen, keine Vermutungen.

| Befund | Ursache | Fundstelle |
|---|---|---|
| Shift wählt im Bild nicht mehrfach | `objectPicked` trägt nur eine Kennung, keine Modifiertaste; der Empfänger ersetzt die Auswahl immer | `viewport.py` (Signal), `main_window._on_object_picked` |
| Zwei Panels für eine Frage | zwei getrennte Orte, beide an derselben Auswahl | `main_window._build_feature_dock`, `main_window` (Aufbau der Auswahlspalte) |
| Viermal derselbe Erklärabsatz | die Begründung der Gruppe wird je Handlung erneut angehängt | `panels._feature_group_note`, Aufruf in der Handlungsschleife |
| Berichtskarte verliert ihr Format | der Höhendeckel trifft den **Inhalt** `self.right`, nicht die Karte `right_card`; der Rahmen bleibt hoch, der Inhalt schrumpft und wird von seinem Layout vertikal zentriert (siehe §2.1) | `main_window._fit_right_column` |
| Linke Spalte schlecht verteilt | vier `collapsible` ohne Streckfaktor untereinander; der Objektbaum ist der einzige mit dehnbarer Größenpolitik und nimmt den Rest | `main_window` (Aufbau der linken Spalte) |
| **Jedes** Dach wählt nichts | beide Dachsorten setzen die Merkmalskennung auf leer, also meldet `selected_feature` nichts und das Dock zeigt seinen Leerzustand | `panels.py:1282` (Gleichart-Dach), `panels.py:1303` (Baustein-Schritt-Dach) |
| Körperhandlungen an einer Fläche | `set_context` setzt ausschließlich `setEnabled`, nie die Sichtbarkeit | `selection_operations.set_context` |

### 2.1 P1 genauer: zwei Mechanismen für eine Höhe

Der Aufbau der rechten Spalte nach `975bd6bf`:

| Ebene | Eigenschaft |
|---|---|
| `right_column` (`CardColumn`) | senkrechtes Layout, Abstand `MARGIN` |
| `right_card` | Streckfaktor **1** — will allen übrigen Platz |
| `self.right` darin | Größenpolitik senkrecht `Ignored`, Höhe von `_fit_right_column` gedeckelt |
| `selection_card` | Streckfaktor 0 — nimmt, was ihr Inhalt wünscht |

Damit gibt es **zwei** Rechnungen für dieselbe Höhe: den Streckfaktor der
Spalte und den Deckel auf den Inhalt. Sie widersprechen sich, sobald der Deckel
kleiner ausfällt als die Karte: Die Karte behält ihren Platz aus dem
Streckfaktor, das Widget darin darf ihn nicht füllen, und ein senkrechtes
Layout mit einem einzigen Kind, das nicht wachsen darf, **zentriert es** — der
Leerraum verteilt sich oben und unten. Genau das zeigen die Bildschirmfotos:
Reiter und Inhalt sitzen mitten in einer hohen, leeren Karte.

**Und der Deckel fällt zu klein aus, weil er zu früh rechnet.** Die
Untergrenze in `_fit_right_column` ist 120, und der Kommentar in
`_reflow_right_column` benennt genau diesen Fall: „Sonst blieb der Bericht
nach einem frühen Auswahlereignis auf 120 Pixeln, obwohl das danach gezeigte
Fenster Platz bot." Das Zurücksetzen davor ist die Gegenmaßnahme und greift
nicht durch — im Bild bleibt es bei den 120.

Daraus folgt für P1: **Nicht den Deckel verschieben, sondern ihn abschaffen.**
Die Spalte verteilt schon, und eine zweite Rechnung daneben ist die zweite
Wahrheit. Was die Auswahlkarte braucht, sagt ihr eigener Wunsch
(`minimumHeight` 280, `maximumHeight` 420); was übrig bleibt, gehört der
Berichtskarte über den Streckfaktor. Bleibt ein Deckel nötig, gehört er an die
**Karte** und nicht an ihren Inhalt, damit kein Leerraum entsteht, den niemand
verteilt hat.

**Gemessen wird das am gebauten Fenster**, nicht an der Rechnung: Höhen von
`right_card`, `self.right` und `selection_card` bei mehreren Fensterhöhen, mit
und ohne Auswahl. Eine Zahl aus dem Layout allein sagt hier nichts — dieselbe
Lage hat die Gegenmaßnahme oben schon einmal für richtig gehalten.

Zwei Dinge sind besser als erwartet und tragen die Lösung:

* **Die Bohrungskette rechnet der Kern schon.**
  `perceive.relations.cavity_chains` liefert die geordnete Kette, und der Baum
  hängt die Senkung deshalb bereits unter ihre Bohrung. Was fehlt, ist die
  Kette als *ein* wählbares Ding.
* **Eine Handlung für mehrere Merkmale in einer Transaktion gibt es.**
  `FeaturePanel.operationRequestedForEach` und die Gruppen aus
  `perceive.actions` sind gebaut und geprüft. Sie gruppieren heute
  „alle gleichartigen"; gemeint ist zusätzlich „diese Kette".

---

## 3. Entscheidungen

### A — Ein Ort für die Auswahl, und der liegt rechts

Die Handlungen zur Auswahl ziehen in das Panel rechts. Es trägt dann beides:
die Maße des Gewählten als änderbare Felder und die Handlungen dazu. Die
Overlay-Spalte behält Prüfbericht, Chat und Tour und teilt ihre Höhe mit
nichts mehr.

*Warum rechts und nicht in der Spalte:* Die Felder mit Zahlen brauchen Breite
und Ruhe, die Overlay-Karten liegen über der Ansicht und verdecken sie. Und
der Formatverlust aus §2 verschwindet damit als Nebenwirkung, statt behandelt
zu werden.

### B — Die Zusammenfassungszeile nennt die Tiefe, nicht die Menge

Statt „1 Objekt gewählt" steht dort, was gewählt ist:

| Auswahl | Zeile |
|---|---|
| ein Körper | `Halter` |
| eine Fläche daran | `Halter · Oberseite` |
| eine Bohrungskette | `Halter · Schraubenloch mit Senkung` |
| mehrere Körper | `2 Objekte` |

„1 Objekt gewählt" über Merkmalshandlungen war nicht bloß unschön: Die Zeile
nannte die Körperzahl, während die Knöpfe darunter dem Merkmal galten.

### C — Zwei Sorten Nichtverfügbarkeit, und nur eine verschwindet

Wörtlich nach Roberts Entscheidung vom 07.09.2026:

* **Vorbedingung fehlt.** Vereinigen braucht zwei Körper, gewählt ist einer.
  Der Kunde kann das erfüllen, der Grund führt ihn hin. **Bleibt grau mit
  Grund.**
* **Andere Auswahlstufe.** *Auf dem Bett anordnen* gilt dem Körper, gewählt
  ist eine Fläche. Da ist nichts zu erfüllen, eine Fläche wird nie angeordnet.
  **Verschwindet.**

*Das ist kein Bruch der Entscheidung vom 23.08.2026*, die für Menüs gilt
(`_hide_dead_menus`): Dort bleibt eine graue Zeile stehen, weil die Erklärung
neben einem Eintrag steht, der geht, und weil eine Oberfläche, die sich unter
dem Kunden bewegt, schlimmer ist. Beides trifft hier nicht: Eine Handlung der
falschen Stufe hat keinen Grund, den man erfüllen könnte, und sie kommt beim
Wechsel der Stufe wieder — nicht beim zufälligen Klick.

**Woraus die Stufe abgelesen wird, steht schon im Register.** Ein neues Feld
braucht es nicht, und ein zweites neben dem vorhandenen wäre die zweite
Wahrheit:

| Stufe | Angabe im Register | Beispiel |
|---|---|---|
| die ganze Szene | `takes_whole_scene` | *Auf dem Bett anordnen*, *Überschneidungen prüfen* |
| ein Körper | kein `applies_to` | *Aushöhlen*, *Objekt duplizieren* |
| ein Merkmal | `applies_to` nennt die Arten | *Senken*, *Verschließen* |

`selection_operations.body_operations` und `feature_operations` trennen die
Menge heute bereits genau daran; was fehlt, ist die Verbindung zur gewählten
Stufe. Nicht zu verwechseln mit `requires_kind`: Das nennt die **Bauart** des
Körpers (Netz oder exakter Kern) und beantwortet eine andere Frage — dort ist
Grau mit Grund richtig, denn wer umwandelt, erfüllt die Bedingung.

Damit fällt auch der Knopf *Merkmale* unter dieselbe Regel: Mit einem Ort für
die Auswahl führt er nirgendwohin.

### D — Das rechte Panel darf zugehen, aber nicht dauerhaft leer bleiben

Heute merkt sich das Dock, wenn der Kunde es selbst schließt, und öffnet
danach nur noch über das Ansichtsmenü. Trägt es die Handlungen, wäre das der
Verlust aller Handlungen auf Dauer.

Der Merker gilt deshalb künftig **der laufenden Auswahl und nicht der
Sitzung**: Wer das Panel zumacht, sieht es bei dieser Auswahl nicht wieder; die
nächste Auswahl bringt es zurück. Das hält die Zusage „ein Fenster, das nach
jedem Klick aufspringt, ist keine Hilfe" für den Fall, für den sie geschrieben
wurde, und nimmt ihr die Dauerwirkung.

### E — Was der Baum unter einer Zeile bündelt, wählt die Zeile mit

Robert am 07.09.2026, auf die Rückfrage: „nicht nur bei Schraubenloch mit
Senkung ist es so, bei allen Dach einträgen." Die Regel gilt deshalb allen
Bündelungen des Baums und nicht einer:

| Zeile | was sie bündelt | was ein Klick künftig wählt |
|---|---|---|
| Gleichart-Dach „Hohlkehle (17)" | alle gleich benannten Merkmale | alle siebzehn |
| Baustein-Schritt-Dach „Schraubenloch mit Senkung" | die Merkmale eines Schritts | Bohrung **und** Senkung |
| Bohrung mit Senkung als Kind | die Kette aus `cavity_chains` | beide Glieder |

Heute wählt keine der drei etwas: Die zwei Dächer tragen die Merkmalskennung
leer (`panels.py:1282` und `1303`), und bei der Bohrung mit Kind wählt der
Klick nur die Bohrung.

**Der Weg dorthin ist klein, weil das Sammeln schon existiert.**
`ObjectTree.selected_features` läuft über die markierten Zeilen und nimmt
jede mit Körper- und Merkmalskennung. Eine Dachzeile löst sich künftig dort in
ihre Kinder auf, statt eine leere Kennung zu liefern. Die Dachzeile bleibt
selbst kein Merkmal — sie ist keines, und `selected_feature` darf bei mehr als
einer Antwort weiterhin nichts sagen.

Die Handlungen gelten dann allen Gliedern in **einer** Transaktion
(`operationRequestedForEach` gibt es dafür schon), die Felder zeigen die Maße
des führenden Glieds, und ein Rückgängig nimmt alles zusammen zurück — es war
eine Handlung (Regel 16). Hervorgehoben wird ebenfalls die ganze Menge, im
Baum und im Bild; `Viewport.select_feature_refs` nimmt Paare und kann das
bereits.

*Und ein Baustein-Dach hat zwei richtige Antworten.* Die Merkmale einzeln zu
ändern ist die eine, „Diesen Schritt ändern" die andere — bei einem
Schraubenloch aus der Bibliothek ist der Bausteinparameter der direktere Weg,
und die Dachzeile trägt ihren Schritt (`_STEP_ROLE`) längst. Beide gehören ins
Panel, mit dem Schritt zuerst: Wer den Baustein ändert, ändert Bohrung und
Senkung an ihrer Quelle statt an ihrem Ergebnis.

*Abgrenzung:* „Alle gleichartigen" und „diese Kette" bleiben zwei Dinge. Die
Kette ist **eine** Bohrung mit ihrer Senkung, die Gleichartigen sind **alle**
Senkungen des Körpers. Im Panel müssen sie unterscheidbar benannt sein, sonst
ändert jemand siebzehn Radien, während er einen meinte.

### F — Die Begründung einer Gruppe steht einmal

Der Absatz über parallele Achsen, gleiche Rolle in der Bohrungskette und
gleich liegende Abschnitte gehört der Gruppe, nicht der einzelnen Handlung. Er
steht künftig einmal an der Gruppe, nicht in jeder Handlungs-Box.

### G — Shift und Strg nehmen im Bild dazu

Im Objektbaum tun beide Tasten heute dasselbe (`ExtendedSelection`), und für
Listen steht die Regel bereits im Code: „damit Strg- und Umschalt-Klick überall
dasselbe tun". Im Bild gilt sie ab jetzt auch. Die Fehlermeldung, die heute nur
Strg nennt, zieht nach.

*Was das nicht ändert:* Die gestufte Tiefe aus §18.5 bleibt. Ein Klick ohne
Taste wandert weiter vom Körper zum Merkmal; die Taste nimmt auf der aktuellen
Stufe dazu.

### H — Die linke Spalte teilt ihre Höhe, statt sie zu verschenken

Vier Abschnitte mit veränderlichem Inhalt teilen eine Spalte. Jeder bekommt,
was er braucht, bis zu einer Grenze; der Rest wird geteilt. Roberts Vorgaben
vom 07.09.2026:

* *Filamente* ist heute kaum zu sehen.
* *Verlauf* wird unlesbar, sobald er wächst.
* *Parameter* wird bei vielen schwierig.
* Der *Baum* darf bei vielen Objekten nicht zu klein werden.

Das Muster dafür existiert schon rechts: `OverlayHost._share_room` verteilt
eine Höhe auf Karten, die `wanted_height`, `least_height` und `set_room`
beantworten. Die linke Spalte bekommt dieselbe Rechnung statt einer zweiten —
Konsistenz vor Vollständigkeit.

---

## 4. Umsetzung als Serie

Jedes Paket endet mit grünem Tor und einem Commit. Additiv zuerst, der
eigentliche Schnitt in P6.

| Paket | Inhalt | Entscheidung | Umfang |
|---|---|---|---|
| P1 | Der Höhendeckel trifft die Karte statt ihres Inhalts | §2 | S |
| P2 | Shift und Strg nehmen im Bild dazu, Meldung nachgezogen | G | S |
| P3 | Die Gruppenbegründung steht einmal | F | S |
| P4 | Die linke Spalte teilt ihre Höhe über den Raumvertrag | H | M |
| P5 | Das Panel kennt die Auswahltiefe: Zeile, Sichtbarkeit, Freigabe | B, C | M |
| P6 | Jede Bündelung des Baums ist wählbar, und die Panels werden eines | A, D, E | L |

**P1 vor allem anderen**, obwohl A den Fehler von selbst auflöst: Bis P6 steht,
sieht die Berichtskarte bei jeder Auswahl kaputt aus, und ein sichtbarer Fehler
wartet nicht auf einen Umbau.

**P5 vor P6**, weil das zusammengelegte Panel die Tiefe braucht: Ohne sie zöge
der Umbau die 38 falschen Knöpfe in seinen neuen Ort mit.

### Verifikation je Paket

| Paket | Nachweis |
|---|---|
| P1 | Reiter der Berichtskarte stehen oben, bei sichtbarem und verborgenem Auswahl-Panel; Höhenmessung am gebauten Fenster |
| P2 | je Taste ein Test am Pick-Pfad, dazu die Meldung im Katalog aller Sprachen |
| P3 | ein Test zählt die Vorkommen des Begründungssatzes bei mehr als einer Handlung |
| P4 | Zuteilung bei 600, 900 und 1400 Pixeln Spaltenhöhe gegen die vier Mindesthöhen |
| P5 | je Auswahltiefe die Menge der sichtbaren Knöpfe; *Auf dem Bett anordnen* fehlt an der Fläche und steht am Körper |
| P6 | je Bündelungsart ein Fall — Gleichart-Dach, Baustein-Dach, Kette: der Klick wählt alle Glieder, eine Änderung ist eine Transaktion, ein Rückgängig nimmt alle zurück |

---

## 5. Nicht-Ziele

* **Keine Betriebsart.** Die Tiefe der Auswahl ist ein Zustand der Szene, kein
  Modus, den man umschaltet (§2.5, „Was NICHT gebaut wird").
* **Keine zweite Nachbarschaftsrechnung.** Ketten kommen aus
  `cavity_chains`, Gruppen aus `perceive.actions`.
* **Keine neue Operation.** Die Serie ordnet, was das Register schon hat.
* **Kein Umbau des Objektbaums.** Seine Bündelung nach Schritt und Gleichart
  bleibt, wie sie ist; E gibt dem Dach nur eine Auswahl.
* **Keine Änderung an §18.5.** Die gestufte Tiefe bleibt der Bauplan; dieses
  Konzept löst sie nur in der Oberfläche ein.

## 6. Was offen bleibt

* **Die Breite des rechten Panels.** Mit Feldern *und* Handlungen darin wird es
  voller. Ob es eine neue Vorgabebreite braucht, entscheidet sich am gebauten
  Fenster in P6 und nicht hier.
* **Die Mehrfachauswahl von Merkmalen über Körpergrenzen.**
  `featuresSelected` und `select_feature_refs` tragen sie bereits; welche
  Handlungen dabei sinnvoll sind, ist eine eigene Frage und keine dieser Serie.
