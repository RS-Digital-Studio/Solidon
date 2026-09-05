---
paths:
  - "app/core/ingest/**/*.py"
  - "app/core/export/**/*.py"
  - "app/core/scene/project*.py"
---

# Regeln für Projektdatei, Import und Export

## Migration ist Pflicht, nicht Kür

Eine Projektdatei ist zugleich Fehlerbericht und Archiv. Ändert sich das
Format:

1. `format_version` erhöhen
2. Migrationsfunktion `vN → vN+1` schreiben
3. Beispieldatei der alten Version einchecken
4. Test: die alte Datei öffnet und rechnet **korrekt**, nicht nur fehlerfrei
5. Ältere Migrationen bleiben bestehen und werden nie zusammengefasst

## Was nicht in die Datei gehört

Keine absoluten Pfade. Kein ausführbarer Code. Keine eigenen Bausteine — ein
Projekt verweist auf sie namentlich, und fehlt einer, hält die Auswertung an
und sagt welcher (§24.5, §32).

## Transaktionstitel

Seit Version 6 trägt ein Titel aus dem Code `title_translatable`: `title` ist
dann die Message-ID (der deutsche Quelltext) und wird erst bei der Anzeige
aufgelöst. Ohne die Markierung ist der Titel wörtlich gemeint — was ein Nutzer
selbst benannt hat, wird nie übersetzt. Wer irgendwo einen Transaktionstitel
vergibt, nimmt `_()` statt `tr()`, sonst friert der Text in der Sprache des
Speicherzeitpunkts ein. Ausnahme: zusammengesetzte Titel wie
`f"{tr('Parameter')} {name}"` bleiben wörtlich — eine Message-ID kennt keine
Platzhalter. Die Titel der Beispiel-Bauer sammelt die Extraktion über
`EXTRA_SOURCES` in `app/i18n/extract.py` mit ein.

## Ein Platzhalterwert kann selbst übersetzbar sein

Ein `TranslatableText` ist Vorlage **plus Werte**, und ein Wert darin ist nicht
zwingend eine Zahl: `perceive.actions._no_way` baut
`_("Dafür ist „{title}“ da.", title=<Titel einer Operation>)`, und der Titel
kommt als `TranslatableText` aus dem Register.

**Werte gehen deshalb durch `translatable_values_to_data` und
`translatable_values_from_data`** (`scene/serialise.py`), nie durch ein rohes
`dict(text.values)`. Das gilt für alle vier Ablagestellen — Parametertitel,
Transaktionstitel, Befundmeldung, Beschriftung eines Auswegs — und für
`cache._name_to_data`, das dieselben Helfer benutzt.

Was ein rohes `dict(...)` kostete, ist am 04.09.2026 gemessen worden: Der
eingebettete Text stand unverändert im Bericht, `json.dumps` in `project.save`
endete mit `Object of type TranslatableText is not JSON serializable`, und
weil das kein `AppError` ist, verlor der Kunde das Speichern ohne
Handlungsvorschlag (Regel 17). Im Plattencache wäre dieselbe Sache still
gewesen — der Eintrag fiele durch den `except`-Zweig, und jedes Projekt
rechnete neu.

**Abgelegt wird die Struktur, nicht der Satz.** Der eingebettete Text behält
Message-ID, Kontext und eigene Werte und übersetzt sich nach dem Laden wieder
selbst. Die beiden kürzeren Wege geben je etwas auf: `str(value)` friert die
Sprache des Speicherzeitpunkts ein, `source_text(value)` legt einem
französischen Kunden einen deutschen Operationstitel mitten in den Satz.
Zahlen bleiben dabei unangetastet — `{free:.1f}` steht so in den Katalogen,
und ein Wert, der als Zeichenkette zurückkäme, machte aus der Formatangabe
einen Fehler.

Dieselbe Regel greift eine Ebene höher beim Auflösen: `TranslatableText.translate(sprache)`
und `source_text()` reichen die verlangte Sprache an ihre Werte weiter, statt
sie über `__str__` gegen die global eingestellte laufen zu lassen.

## Eingangsstufe

Jede geladene Datei durchläuft dieselbe Kette, und das Ergebnis steht in
`sources`: Einheit bestimmen (bei Verdacht **nachfragen**, nicht annehmen),
Vertices verschweißen, entartete Dreiecke entfernen, Normalen vereinheitlichen,
Komponenten zählen (Kleinstteile **melden** statt still löschen), Lage
ermitteln und Aufsetzen anbieten — nicht erzwingen.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar
und änderbar bleiben.

Eine Datei aus dem Netz (`core/ingest/fetch.py`) geht **denselben** Weg:
`Session.import_payload` ist die gemeinsame Stelle, `import_model` liest nur
die Platte und ruft sie auf. Zwei Importwege wären zwei Stellen, an denen die
Einheitenfrage vergessen werden kann. Was aus dem Netz kommt, trägt seine
Herkunft in `Source.origin` (§16.3), wird nur über `http`/`https` geholt, und
die Größengrenze wird **während** des Lesens geprüft — `Content-Length` ist
eine Behauptung des Servers. Eine Adresse, unter der HTML liegt, ist eine
Modellseite und keine Modelldatei; sie wird als solche gemeldet, nicht
ausgewertet.

## Formate

3MF ist eine **Baugruppe**, keine einzelne Datei: mehrere Objekte, Stückzahlen,
Materialgruppen je Dreieck, Transformationen. Wer es als ein Mesh liest,
verliert genau das. STL kennt keine Einheiten und keine Farbe. STEP bringt
echte Flächen, aber keine Farbe.

Dreieckszahl und Dateigröße sind beim Import gedeckelt — mit klarer Meldung
statt Speicherüberlauf.

## Was welcher Slicer bekommt

`write_assembly` schreibt eine 3MF-Baugruppe — außer für `cura`. `CuraEngine`
liest kein 3MF (die 3MF-Seite sitzt in Curas Fenster, nicht in der
Rechenmaschine dahinter), und ein 3MF endete dort in „Der Slicer hat keine
Druckdatei geschrieben", ohne dass irgendwo stand, warum. Cura bekommt ein STL
mit allen Teilen der Platte; Namen und Materialslots liest es ohnehin nicht,
und die Einstellungen kommen bei ihm über die Kommandozeile.

**Bettkoordinaten für jede Familie** (`wants_bed_coordinates`). Solidon
rechnet um den Ursprung, der Drucker misst von der Ecke — und der Slicer
bekommt die Welt des Druckers: die Teile um den halben Bauraum verschoben
**und** ein Bett von `0` bis `256`, in derselben Übergabe. Bis zum 05.09.2026
bekamen Cura und PrusaSlicer stattdessen Solidons Welt erklärt
(`machine_center_is_zero`, eine Bettform von `-128` bis `128`) und die Teile
unverschoben; der Slicer war mit sich im Reinen und schrieb Bahnen bei
`-13,6`, die es auf einem MK4S oder Centauri nicht gibt, während die eigene
Gegenprobe gegen denselben erfundenen Ursprung maß (Gesamtreview, CORE-17,
mit PrusaSlicer 2.9.6 gemessen). Die ältere Messung „um den halben Bauraum
verschoben" — Würfel bei -10…10, im G-Code bei 118…138 — war die Bettmitte;
PrusaSlicers „All objects are outside of the print volume" kam aus dem
Widerspruch zwischen verschobenen Teilen und zentriert erklärtem Bett. Wer
das eine ändert, ändert das andere mit — beides fragt dasselbe Prädikat.

## Die drei Stufen der Übergabe

Was ein Slicer bekommt, entsteht in dieser Reihenfolge, und `values_for` ist
die einzige Stelle, an der sie zusammenkommen:

1. **Zuordnung** (`as_mapping`) — die Tabellen aus `slicer_keys`, dazu was
   sich allein aus den Einstellungen umrechnen lässt.
2. **Maschine** (`_machine_keys`) — Bauraum, Düse, und was `CuraEngine`
   sonst nirgends findet.
3. **Abgeleitetes** (`_cura_dependants`) — nur für Cura, und nur danach: die
   Ableitung rechnet auf Werte aus beiden Stufen.

Wer eine Stufe einzeln benutzt, bekommt einen halben Satz. Für Prusa und Orca
ist die dritte leer.

## CuraEngine löst keine Vererbung auf

In `fdmprinter.def.json` trägt jede abgeleitete Einstellung zweierlei: einen
`value`-Ausdruck und einen `default_value`. Das Fenster wertet den Ausdruck
aus, die Rechenmaschine dahinter nimmt den Vorgabewert. Ein geschriebener Wert
bleibt damit an seinem Schlüssel stehen und erreicht die nicht, aus denen
gerechnet wird — die Bahnbreite ihre zwölf Bahnbreiten nicht, die Füllung
ihren Linienabstand nicht.

Gemessen an einem 20-mm-Würfel: **1100 mm Filament statt 818, 753 Sekunden
statt 660.**

Wer eine Cura-Zuordnung ergänzt, prüft deshalb immer mit: hängt etwas an dem
neuen Schlüssel? Reine Kopien kommen in `CURA_MIRRORED`, einfache Faktoren in
`CURA_SCALED`, Gerechnetes in `_cura_rated` — dort **die Formel aus der
Definition**, nicht die eigene Meinung darüber, was richtig wäre. Was
absichtlich wegbleibt, kommt mit Begründung in `CURA_UNTOUCHED`;
`tests/test_print_settings.py` lässt keine dritte Möglichkeit zu.

## Winkel zählen nicht überall gleich

`support.threshold_angle` misst **gegen die Senkrechte**: 0° stützt jeden
Überhang, 90° keinen. Das ist Curas Zählweise. PrusaSlicer und die
Orca-Familie messen gegen die **Horizontale** und drehen die Bedeutung damit
um — für sie rechnet `_angle_from_horizontal` in `90 − Wert`. Gemessen an
einem Keil mit 30° Neigung: die beiden kippen zwischen 20 und 40, Cura
zwischen 50 und 70.

## Wie eine Zuordnung geprüft wird

Ein falscher Schlüsselname fällt nicht von selbst auf — kein Slicer meldet
ihn. Zwei Wege führen hin, und sie decken verschiedene Slicer ab:

- **Prusa und Orca schreiben ihre Konfiguration in den G-Code.** `verify()`
  vergleicht sie gegen das Geschriebene: 53 von 53 beim einen, 56 von 56 beim
  anderen.
- **CuraEngine schreibt dort nichts** — null von 47. Für es liegt die Auskunft
  daneben: `fdmprinter.def.json` nennt jeden gültigen Schlüssel der
  installierten Version. `unknown_keys()` liest sie zur Laufzeit, der Test
  `test_every_cura_key_exists_in_the_definition` beim Bauen.

In dieser Lücke saß `outer_inset_first`: ein Name aus Cura 4, in Cura 5
verworfen, ohne Fehler und ohne Warnung — null von fünfzig Lagen begannen
außen, obwohl der Wert geschrieben war.

## Einstellungen reisen mit der exportierten Datei

Eine 3MF soll man drucken können, nicht erst einrichten. Beide Familien lesen
dafür eine Beilage, in verschiedenen Formaten:

| Slicer | Beilage | Format |
|---|---|---|
| Orca-Familie | `Metadata/project_settings.config` | JSON |
| PrusaSlicer | `Metadata/Slic3r_PE.config` | `; schlüssel = wert` je Zeile |

PrusaSlicer **überspringt die erste Zeile** dieser Datei — bei ihm steht dort
seine eigene Kennung. Ohne `PRUSA_CONFIG_HEADER` fiel der alphabetisch erste
Schlüssel lautlos heraus. Cura bekommt seine Einstellungen ohnehin über die
Kommandozeile; seine 3MF-Seite sitzt im Fenster.
