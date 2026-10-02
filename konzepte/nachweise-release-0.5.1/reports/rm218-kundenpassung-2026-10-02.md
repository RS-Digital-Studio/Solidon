# RM-218: Passungen beim Umbau des exakten Kundenmodells

Fachnachweis vom 02.10.2026. Die enge Parserkorrektur und ihre Kernregressionen
sind unabhängig ohne offenen Befund freigegeben. Die unveränderte Kundensonde
besteht alle sechs Fälle; ihr Datenreview ist ebenfalls ohne Befund freigegeben.
Zentrales Entwicklungstor und Übernahme stehen noch aus.

## Ausgangspunkt und enger Fix

Der bereits übernommene RM284-Anschluss erhält eindeutig zugeordnete,
unveränderte Merkmale des exakten Körpers. Für RM218 fehlte noch der
vollständige Passungsnachweis am echten `build_tray_v3.step`: B vor A
verschieben sowie vor B eine weitere Bohrung bei x = 0 oder x = 80 mm
einfügen, jeweils mit Entwurf, Feinrechnung, Warmcache und echtem Undo.

Die neue Probe entdeckte schon im Ausgangsstand einen Produktfehler: Der
gültige freie Passungsname `RM218: Bohrung B und Prüfpin` wurde aus dem
Schlüssel `fit:<Name>:a/b` nur bis zum ersten Doppelpunkt gelesen. Die
Seitenlesung lieferte ebenfalls den falschen Teil. Dadurch verschwanden
beide Passungssichten trotz vorhandener, maßlich gültiger Merkmale.

`orphans.fit_name_from_key` liest jetzt den vollständigen Namen zwischen
festem Präfix und letztem Seitenmarker. `Reference` verwendet diesen Leser
und liest die Seite vom letzten Trenner. Die drei gleichen Zerlegungen in
`revision.dependencies` und beiden Passungswegen von `revision.drifts`
nutzen denselben Leser. Auch Neuzuordnung und Entfernen treffen damit die
richtige Passung. Das gespeicherte Format ändert sich nicht; eine Migration
oder Operationscache-Version ist dafür nicht erforderlich.

## Regressionen und tatsächliche Läufe

Die 36 neuen Fälle prüfen normale Namen, einen und mehrere Doppelpunkte,
auch am Anfang oder Ende, sowie beide Seiten. Sie prüfen Neuzuordnung und
Entfernen neben einer gleich beginnenden anderen Passung, Abhängigkeiten,
den Vergleich mit Grundstand und Ruhevermerk sowie echten Umbau,
Speichern/Laden und genau ein Undo an Netz und exaktem Körper.

Lokale vollständige Belege: `tmp/rm218-20261002/name-fix/`.

| Beleg | Tatsächlicher Ausgang |
|---|---|
| `red-valid.txt` | 24 fehlgeschlagen, 12 Normalnamen-Kontrollen bestanden, 64 abgewählt; 2,96 s, Exit 1 |
| `green.txt` | 36 bestanden, 64 abgewählt; 2,06 s, Exit 0 |
| `scoped.txt` | 531 bestanden; 33,38 s, Exit 0 |
| `ruff-final.txt`, `format-final.txt` | Vier eigene Pythondateien ohne Befund, jeweils Exit 0 |
| `mypy.txt` | Zwei Produktdateien ohne Fehler, Exit 0 |

Der 531er-Lauf enthält die vollständigen Orphans-/Revision-Module sowie
Sprach- und Kartenprüfungen; die 36 Fälle werden nicht nochmals addiert.
Der erste Rotlauf hatte zusätzlich zwei Fixturefehler: Beim Öffnen wurde
die Bibliotheksversion 0 korrekt aktualisiert. Die Fixture beginnt nun mit
`LIBRARY_VERSION`; kein Vergleichsfeld wurde entfernt. Maßgeblicher
Produktgegenlauf ist deshalb `red-valid.txt`.

Der Importgraph nennt 358 von 383 Testdateien. Dieser Auswahllauf ist kein
ausgeführtes Entwicklungstor. Die vollständige Prüfung bleibt bei der
zentralen Integration.

## Kundensonde und historische Läufe

Original: `F:/3D Dateien/build_tray_v3.step`, SHA256
`BB0656D93EB3EDD4F188579A32F21F567689193D17F703482B2800B69FB5AF12`.
Die Baugruppe liefert fünf Körper; der erste ist das bearbeitete Kundenteil.
A und B beginnen mit physischem Durchmesser 5 mm bei x = −50 und x = 50 mm.
Die Bohrungskompensation ist ausdrücklich ausgeschaltet. Ein getrennt
erzeugter nativer Pin erhält den Durchmesser `8 mm − auto:petg` für die
Passungsart `clearance`. Der tatsächlich gelesene Profilwert ist 0,25 mm,
also Pin-Ø 7,75 mm; die spätere B-Bohrung hat Ø 8 mm.

Die echte Passung wird mit `History.apply(DocumentChange)` angelegt und
ist vor der Vergrößerung verletzt. Danach muss sie maßlich gültig sein.
Der Pin liegt neben der Baugruppe; das belegt eine Maß-/Merkmalsbeziehung,
keine mechanische Einbau- oder Kollisionsabnahme.

Die ursprünglichen drei roten Kundenläufe bleiben erhalten:

- 46,80 s, sechs fehlgeschlagen: Die erste Fixture ließ die vorhandene
  Bohrungskompensation an und erwartete dennoch Ø 5 statt der richtigen 5,2 mm.
- 64,25 s, sechs fehlgeschlagen: Der Sollname für den nativen Import war in
  der Fixture `load` statt des tatsächlich richtigen `load_step`.
- 55,25 s, sechs fehlgeschlagen: Produktfehler durch den gültigen Namen mit
  Doppelpunkt; die Prüfung hielt vor Revision und Undo an.

Die zwei Fixturekorrekturen wurden eng und unabhängig geprüft. Die seitdem
unveränderte Sonde trägt SHA256
`1E17BCDBE8BC8E350FB72CB32984A516CE5C667815CDBD0A933392FA3FC7F12D`.
Der ursprüngliche Doppelpunktname bleibt im Schlusslauf erhalten.

## Vollständiger Kundenlauf nach dem Fix

Der vierte serielle Lauf ist beendet: **6 bestanden in 96,79 s, Exit 0**.
Startprozess 67872, Pytest-Prozess 72944. `process-20261002-172417/` enthält
Start, tatsächlichen Exit, stdout/stderr und denselben Sondenhash vor/nach.
Die sechs Original-JSONs liegen unter
`runs/20261002T152419Z-72944/`, jeweils relativ zum lokalen Belegordner
`tmp/rm218-20261002/`.

| Qualität | Tatsächlicher Umbau / Bohrungsfolge x in mm | B-Bezug danach | Treffer im warmen Umbau | Erstes Undo / warmes Undo |
|---|---|---|---:|---:|
| Entwurf | B vor A: `[50, −50]` | `obj_1:hole_1` | 5/5 | 5/5 / 5/5 |
| Entwurf | Einfügen bei x = 0: `[−50, 0, 50]` | `obj_1:hole_3` | 6/6 | 5/5 / 5/5 |
| Entwurf | Einfügen bei x = 80: `[−50, 80, 50]` | `obj_1:hole_3` | 6/6 | 5/5 / 5/5 |
| Fein | B vor A: `[50, −50]` | `obj_1:hole_1` | 5/5 | 5/5 / 5/5 |
| Fein | Einfügen bei x = 0: `[−50, 0, 50]` | `obj_1:hole_3` | 6/6 | 5/5 / 5/5 |
| Fein | Einfügen bei x = 80: `[−50, 80, 50]` | `obj_1:hole_3` | 6/6 | 5/5 / 5/5 |

Der Passungsname bleibt in allen Phasen vollständig erhalten. Der Pin-Bezug
bleibt `obj_6:pin_1`. B bleibt physisch bei `(50, −110, 2,5)` mm mit Ø 8 und
Tiefe 5 mm, während A und die neue Bohrung Ø 5 behalten. Der ursprüngliche
B-Bezug `obj_1:hole_2` wird beim Umbau geometrisch verfolgt und an die neue
Kennung gebunden; nach Undo gilt wieder die ursprüngliche Zuordnung.

Die verlangte, geprüfte und tatsächlich übernommene Operationsfolge stimmen
jeweils überein. Der Commit verändert den Dokumentinhalt wirklich. Genau
ein `History.undo()` nimmt diese Umbautransaktion zurück und stellt die Folge
`[−50, 50]` wieder her. Vollständiger serialisierter Projektinhalt mit einzig
ausgenommenem monotonem Zähler, eingebettete Quelldateibytes und die direkten
Ausgabedaten aller sechs Körper stimmen danach mit dem Ausgangsstand überein.

Die Warmvergleiche umfassen tatsächliche native Körperbytes, externe
Tessellierungswerte/Flächenzuordnung, Mesharrays und sämtliche Objektfelder.
Operations-/Merkmalsschlüssel werden zusätzlich geprüft und nicht als
vollständige Geometriehashes ausgegeben. In jedem geforderten warmen Lauf,
bereits beim ersten Undo und seiner Wiederholung, trifft jeder erwartete
Schritt den Cache; es gibt dort keine Fehlzugriffe oder Schreibzugriffe.
Das schließt jede Bohrung und die spätere Vergrößerung ein. Alle sechs Fälle
erreichen `undo_warm`, ohne unerwartete Rückfrage. Jeder Fall enthält 13
vollständige Auswertungen. Die 24 vorgeschriebenen Warmphasen liefern
zusammen 124 Treffer bei 0 Fehlzugriffen und 0 Schreibzugriffen.

Die Auswertung `customer-final-summary.json` ist mit den Original-JSONs
verknüpft und verifiziert 260 archivierte Quellbytes sowie 82 Ausgabeblobs
gegen ihre SHA256. Alle 260 erfassten Quellen bleiben vor/nach und zwischen
den sechs Fällen unverändert; alle Driftlisten sind leer. Der gemeinsame
Quellendigest ist
`4B16EDE55DCDF47A5366E302FA33FF17DA0C77C8CE287FB81C5A24DDF8C55BE1`.
Auch das Original und die Sonde sind unverändert. Jeder Fall meldet sowohl
`checks_passed` als auch `stable_evidence`, nicht allein einen grünen Prozess-Exit.

## Review und Übernahmegrenze

Der enge Code-/Test-/Kartenreview las alle eigenen Hunks, Gegenfälle und
Schlusslogs. Die fünf Quellhashes entsprachen dem gesicherten Stand;
freigegeben sind die zwei Produktdateien, zwei Testdateien und ausschließlich
der dreizeilige Passungsschlüssel-Zusatz der Szene-Karte.

Root hat zusätzlich Prozessende, unveränderten Sondenhash, sechs Fallstände,
Passungsbezüge, konkrete Cachezahlen und direkte Undo-Vergleiche gelesen.
Der unabhängige Kundenbelegreview hat alle sechs Original-JSONs und die Sonde
gelesen, die direkten Daten-/Undo-Vergleiche nachgerechnet und sämtliche 343
eindeutig referenzierten Quell-/Ausgabedateien auf Hash und Größe geprüft.
Auch der aktuelle Originalhash stimmt. Seine Freigabe enthält keinen offenen
Befund; die Produktquellen des Kundenlaufs entsprechen dem freigegebenen Fix.

Zentrales Tor und tatsächlicher Commit-/Pushnachweis fehlen noch. Fenster-,
Renderer- und Leistungsprüfungen gehören zur Release-Abnahme RM213 und werden
mit diesen Kernläufen nicht behauptet.
