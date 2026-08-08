---
paths:
  - "app/core/slice/**/*.py"
  - "app/core/perceive/**/*.py"
---

# Regeln für Schichtanalyse und Wahrnehmung

## Die Abgrenzung, die nicht verhandelbar ist

Solidon baut **keinen G-Code-Slicer**. Die Datei, die auf den Drucker geht,
kommt vom externen Slicer. Was hier entsteht, ist Analyse: Ebene-Mesh-Schnitt,
Konturen, Kennzahlen — in Millisekunden, ohne Fremdprozess.

**Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** (Regel 14).
Jeder Wert weist seine Herkunft aus. Ein geschätztes Stützvolumen aus der
Schichtanalyse ist etwas anderes als ein gemessenes aus dem G-Code, und der
Prüfbericht sagt welches.

Beschriftung in der Oberfläche: „Schichtanalyse", nicht „Vorschau". Sie zeigt
die Geometrie, nicht die Werkzeugwege.

## Die Einstellungen bleiben trotzdem hier

Kein eigener Slicer heißt **nicht** kein eigenes Profil. `PrintSettings`
(§29) hält alles, was gedruckt wird — Schichten, Wände, Füllung,
Temperaturen, Kühlung, Geschwindigkeiten, Stützen, Haftung, Rückzug,
Filamentfarbe. `export/handover.py` schreibt daraus die Konfiguration des
externen Slicers, ruft ihn und liest den G-Code zurück. Der Slicer führt aus,
er entscheidet nicht mehr.

Drei Sachen, die dabei nicht verhandelbar sind:

- **Aufgelöst wird aus drei Ebenen** — Qualitätsstufe, Material, Drucker, in
  dieser Reihenfolge. Die Düse skaliert die Schichthöhe, die Maschinengrenzen
  deckeln die Temperatur, ein offener Bauraum bekommt keine Kammertemperatur.
- **Das Maschinenprofil wird nicht erfunden.** Bettform, Anfahrwege, Start-
  und Endcode kennt Solidon nicht; sie kommen aus dem Bestand des Slicers.
  Bei der Orca-Familie gilt das auch für das Prozessprofil: Solidon liest das
  benannte Systemprofil und legt seine Werte darüber, sonst bricht der Lauf
  mit „process not compatible with printer" ab, bevor er das Modell ansieht.
- **Ein neuer Slicer kostet eine Tabelle**, keinen Eingriff — `slicer_keys.py`
  ist das Wörterbuch, `handover.py` der Ablauf.

**Bei `CuraEngine` gehen die Werte zweimal hinaus.** Es hält zwei Ebenen —
global und Extruder-Zug —, und das meiste, was einen Druck ausmacht, liest es
vom Zug. Was nur global steht, wird nicht übernommen, sondern von der Vorgabe
der Definition überschrieben; was nur auf dem Zug steht, fehlt der
Zeitrechnung. Beide Male dasselbe zu setzen kommt am selben Ort heraus und
spart es, `settable_per_extruder` aus der Definition zu lesen.

**Was der Kopf einer Cura-Datei sagt, ist keine Messung.** `Filament used`,
`MINX` und `TIME` schreibt CuraEngine, *bevor* es rechnet; im Fenster werden
sie ersetzt, von der Kommandozeile aus bleiben sie stehen — `;TIME:6666` sieht
mit 111 Minuten plausibel aus und gilt für jedes Modell. Gelesen wird deshalb
die Datei selbst: die E-Achse für das Material, die letzte `TIME_ELAPSED` für
die Zeit. Ein Kopfwert gilt weiter, wo er einen trägt — er kennt Vorgänge, die
keine Bahn zeigt.

## Vorschlag oder Befund

`slice/advise.py` schließt aus Geometrie, Material und Maschine auf
Einstellungen. Die Unterscheidung ist verbindlich:

- Was ein Wert behebt, wird ein **Vorschlag** (`SettingAdvice`) — mit Pfad,
  altem Wert, neuem Wert und **Begründung**. Ohne Grund kein Vorschlag: eine
  Zahl, die niemand nachprüfen kann, ist schlechter als die Vorgabe.
- Was kein Wert behebt, wird ein **Befund** (`Finding`). ASA auf einem offenen
  Drucker bleibt heikel, auch wenn Lüfter und Brim schon stimmen; das als
  Vorschlag zu verkleiden hieße, eine richtige Einstellung zu ändern.

Übernommen wird auf Klick, nie von allein.

**Ein Vorschlag je Einstellung**, und `was` ist immer der Ausgangswert. Regeln,
die auf denselben Wert zielen, werden zusammengeführt; die spätere gewinnt,
weil sie den Stand der früheren gesehen hat. Der Volumenstrom läuft deshalb
zuletzt: er hängt an Schichthöhe, Bahnbreite und Tempo, an denen die anderen
Regeln gedreht haben können.

**Der Volumenstrom ist die Grenze, die kein Feld zeigt.** Schichthöhe mal
Bahnbreite mal Geschwindigkeit gegen `max_flow` des Materials — darüber
fördert der Antrieb mehr, als das Hotend flüssig bekommt, die Bahn wird dünner
als gerechnet, und an den Einstellungen sieht man nichts. Zwei Auswege, beide
werden genannt und keiner erzwungen: heißer, solange die Maschine das kann,
sonst langsamer.

## Das Maschinenprofil des Slicers

`export/slicer_profiles.py` liest den Bestand des installierten Slicers. Vier
Eigenheiten, die dabei nicht angenommen werden dürfen:

- **Die Ordnertiefe ist nicht einheitlich** — Bambu legt in `machine/`, Elegoo
  in `machine/ECC2/`. Gesucht wird nach dem Ordnernamen irgendwo im Pfad.
- **Verträglichkeit wird vererbt.** Ein Profil je Familie trägt
  `compatible_printers`, die Geschwister erben sie über `inherits`. Wer nur
  das eigene Feld liest, bietet eines von sieben an.
- **Eigene Profile tragen kein `type`** und kein `instantiation` — sie erben
  und stehen unter `from: User`. Genau die gehören in die Liste.
- **Zugeordnet, nicht erfragt.** `printer_model`, Düse und
  `default_print_profile` reichen. Trifft nichts, bleibt die Auswahl leer:
  eine falsche Vorauswahl sieht aus wie eine Entscheidung.

## Was geschrieben wird, ist nicht alles, was im Modell steht

Skirt, Brim und Raft sind Maße **ihrer jeweiligen Art**, keine unabhängigen
Schalter — die Slicer lesen sie aber als solche. Wer alle drei schreibt,
bekommt alle drei: einen Raft unter einem Teil, für das „Skirt" eingestellt
war. `_only_chosen_adhesion` nullt deshalb die Maße der nicht gewählten Arten.

Dieselbe Vorsicht gilt für jede künftige Einstellung, die eine Art *und* ihre
Maße hat. Der Fehler ist geräuschlos, kostet Material und Zeit und fällt erst
auf der Platte auf.

## Die Druckdatei gehört dem Nutzer

Der Lauf endet nicht bei den Kennzahlen. Was der Slicer schreibt, liegt im
Arbeitsordner und verschwindet mit ihm — es muss speicherbar sein, sonst war
der ganze Weg eine Zahl auf dem Bildschirm. Vorgeschlagen werden Ordner und
Name des Projekts.

Die Druckeinstellungen selbst gehören ins **Projekt** (`format_version` 4),
nicht in die Anwendungskonfiguration: sie beschreiben das Teil, nicht den
Rechner. Slicer-Pfad und Profilwahl bleiben dagegen bei der Anwendung — ein
Projekt wird auch auf einem Rechner geöffnet, wo ein anderer Slicer liegt.

## Eine Platte ist eine Datei

Was zusammen gedruckt wird, geht als **eine 3MF-Baugruppe** hinaus
(`threemf.write_assembly`), nicht als eine Datei je Objekt. Der Unterschied
ist nicht das Format: ein Slicer, der eine Baugruppe bekommt, ordnet sie als
Ganzes an und schreibt eine Druckdatei. Bekommt er fünf Dateien, entscheidet
er über ihre Zusammengehörigkeit selbst, und was Solidon über die Platte
weiß, ist verloren.

Die Materialslots werden dabei über **alle** Teile zusammengelegt
(`merge_slots`), über Name und Farbe. Ein Slot ist ein Filament, kein
Objektmerkmal — zwei Teile in derselben Farbe kommen aus derselben Düse. Die
Reihenfolge der zusammengelegten Liste *ist* die Extruderbelegung.

## Die Gegenprobe ersetzt die Dokumentation

`handover.verify` liest die Konfigurationskommentare der erzeugten Druckdatei
und meldet, was der Slicer anders übernommen hat, als Solidon es schrieb.
Das ist die einzige Auskunft, die vom Programm selbst kommt statt aus einer
Beschreibung, die für die installierte Fassung gelten mag oder nicht — und
damit prüft sich auch ein Slicer, den beim Bauen der Tabelle niemand vorliegen
hatte.

Gemeldet wird nur, was **nachweislich** abweicht. Ein Schlüssel, den die Datei
nicht nennt, sagt nichts: kein Slicer schreibt alles, und eine Gegenprobe, die
bei jedem Lauf zwanzig Fehler meldet, wird nach dem dritten Mal übersehen.
Verglichen wird nachsichtig — `0.2` gegen `0.20`, `15%` gegen `15`, eine Liste
aus einem Element gegen dieses Element.

## Was die Analyse liefert

Überhangfläche je Schicht, Stützvolumen, Querschnittsverlauf, **Inseln**
(Konturen ohne Verbindung nach unten), erste Schichtfläche, Brückenweiten,
kleinste Strukturbreite gegen den Düsendurchmesser. Der Gewinn ist der
Maßstab: hunderte Rotationen in der Orientierungssuche statt drei extern
geslicter Kandidaten.

## Stabile IDs

Feature-Erkennung liefert Provenienz-IDs, an denen Ops und Passungen hängen.
Eine ID muss eine Neuberechnung überleben — sonst zeigt der Op-Stack nach der
nächsten Änderung ins Leere. Mehrdeutige Zuordnung hält an und fragt, statt
die nächstbeste zu nehmen.

Analysekarten sind teuer: sie laufen im Hintergrund, sind abbrechbar und
halten das Budget aus §31 ein (Wandstärke unter 3 s, Schichtanalyse bei
200 000 Dreiecken und 0,2 mm unter 300 ms). Farbskala wahrnehmungsgleich, nie
Regenbogen.
