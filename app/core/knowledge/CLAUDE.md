# `app/core/knowledge/` — was die Anwendung weiß

Profile, Normteile, Regelsammlung, Kalibrierung — und in `parts/` die
Bausteinbibliothek (§24, §38, §39).

Die Regeln stehen in `.claude/rules/bausteine.md`.

## Der Grundsatz

**Der Agent setzt geprüfte Bausteine zusammen, statt Geometrie zu erfinden**
(§24). Was hier liegt, ist der Vorrat, aus dem er schöpft — und damit Teil des
Rechenwegs, nicht Beiwerk.

## Die Karte

| Datei | Rolle |
|---|---|
| `profiles.py` | Drucker- und Materialprofile (§38). **Hier stehen die Toleranzen**, auf die `auto:<material>` verweist |
| `standards.py` | Normteilmaße (§24.2) — M3, M4, Einpressbuchsen, Lager |
| `strength.py` | Blattfederrechnung für Schnapphaken und Klemmzungen; mechanische Kennwerte aus dem Materialprofil |
| `print_settings.py` | Löst Stufe + Material + Drucker zu Einstellungen auf (§29) |
| `rules.py` | Die Regelsammlung für den Agenten (§39) |
| `calibration.py` | Selbstkalibrierung (§28.3) |
| `filaments.py` | Örtliches Filamentlager: Spulen mit beständiger Kennung, optionale Mengen und Angaben, Journal ganzer Druckvorgänge (§20) |
| `licences.py` | Lizenzprüfung der Abhängigkeiten (§36) |
| `tables.py` | Der eine TOML-Leser für Dateien, die auch von Hand geschrieben sein können — ein Syntaxfehler wird ein Satz mit Dateinamen (Regel 17); Profile, Druckeinstellungen und Kalibrierung rufen ihn mit ihrem Titel |
| `parts/` | Die Bausteinbibliothek — eigene `CLAUDE.md`, **eigene Lizenz** |
| `data/` | **Wo das Wissen wirklich steht**: sieben TOML-Dateien und die Lizenztexte (siehe unten) |

## Das Wissen steht in `data/`, nicht im Code

Die Module hier **laden und lösen auf**; die Werte selbst liegen daneben:

| Datei | Inhalt |
|---|---|
| `printers.toml` | Druckerprofile |
| `materials.toml` | Materialprofile — hier stehen die Toleranzen |
| `print_settings.toml` | Druckeinstellungen je Stufe |
| `standards.toml` | Normteilmaße |
| `rules.toml` | **Die Regelsammlung des Agenten** (§39) |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) |
| `third_party_licenses.toml` | Feste Quellen, Hashes und Zuordnung der Lizenztexte für Pakete, Laufzeitteile und Schriften (§36) |
| `third_party_licenses/` | Vollständige Lizenztexte und Anleitung zur Release-Lizenzakte in `README.md` |

Der Eintrag für eine neue Agentenregel gehört in `data/rules.toml`.

`strength.py` verwendet E-Modul, Streckgrenze und `layer_bond_ratio` aus dem
Materialprofil. Die Lage bestimmt, ob der Schichtabschlag gilt; das Profil
bestimmt seine Größe. Ohne bekannte Druckrichtung gilt Querbelastung. Ein
fehlender mechanischer Kennwert ergibt keine erfundene Tragfähigkeitsangabe.

## Warum das keine Konstanten im Code sind

Weil sie sich ändern, ohne dass der Code sich ändert. Eine Toleranz gehört ins
Materialprofil, ein Gewindemaß in die Normteiltabelle — **eine Zahl im
Baustein ist ein Fehler** (Regel 7, Checkliste Baustein Punkt 6).

## Eine Regeländerung wird gemessen

Regelsammlung angefasst? Dann:

1. Eintrag in `data/rules.toml` mit Datum und Anlass
2. Version erhöhen
3. Agenten-Suite **vorher und nachher**, beide Ergebnisse festhalten
4. Verschlechtert sich die Quote, wird die Regel zurückgenommen — nicht
   „trotzdem behalten"

Der Suite-Lauf kostet Geld und rund anderthalb Stunden je Modell
(`tools/run_agent_suite.py`). Er ist kein Testlauf.

Kalibrierung schreibt TOML-Tabellen- und Feldkennungen als zitierte Literale.
Materialkennungen mit Leerraum, Punkten oder Anführungszeichen bleiben so
beim Aktualisieren eines anderen Profils unverändert lesbar.

## Druckproben gelten für ihren Prozess

`calibration.apply(..., process=...)` speichert gemessene Mindestwand und
Überhanggrenze zusammen mit Druckerkennung, Düse, Schichthöhe und Linienbreite.
`profiles.for_process` übernimmt dafür das tatsächliche Druckraster aus den
Projekteinstellungen. `Profile` verwendet die Messwerte nur bei passendem
Prozess; andernfalls gelten zwei Linienbreiten und die Überhang-Startregel.
Ein Wechsel des Messprozesses nimmt keine Messung des anderen Felds mit.
Nicht ausgewählte Messfelder bleiben beim Speichern unverändert.

`analysis_limits` verbindet die Anforderungen der zugeordneten Materialien:
größte Mindestwand, kleinster Überhangwinkel. Unbekannte Materialarten
übernehmen keine Kalibrierung eines anderen Materials. Analyse und ihre
Zwischenspeicher müssen die wirksamen Grenzen berücksichtigen.

## Das Filamentlager ist örtlicher Bestand

`filaments.save` speichert eine Spule nach Kennung; eine leere Kennung legt
ein neues Exemplar an. Namen dürfen mehrfach vorkommen. Bearbeitungen behalten
die gelesene `revision`, damit ein offener Dialog keinen jüngeren Verbrauch
zurückschreibt. Archivieren erhält Kennung und Verlauf. Die alten Namenswege
`remember`, `synchronise` und `forget` bearbeiten nur eindeutige Treffer;
sie raten bei zwei gleichen Etiketten keine physische Spule.

Spulen, letzte Bestandsfeststellungen und Buchungen stehen gemeinsam in der
versionierten `filaments.json`. Schreibendes Lesen, Prüfen und atomarer Dateitausch
liegen unter einer Betriebssystemsperre. Die Migration alter Listenkataloge speichert
Lager- und Spulenkennungen im selben Vorgang; unbekannte Mengen bleiben leer.
Die Lagerkennung wird bei ihrer ersten Abfrage gespeichert. Wiederholte
Abfragen einer bereits gespeicherten Kennung lösen keinen Dateitausch aus.
Reine Leser teilen eine unveränderliche `InventorySnapshot` ohne Schreibschloss.
Dateiidentität, Größe und Änderungszeit erneuern den Cache bei jedem geänderten
Stand; ein Lesefehler wird nie als leere Liste oder veralteter Cache beantwortet.
Spulen und Journal einer gemeinsamen Anzeige stammen aus derselben Momentaufnahme.
Eine erforderliche Migration wartet im Leser nicht auf eine fremde Sperre und
meldet bei Konkurrenz den Wiederholungsweg. Auf Windows erlaubt der offene
Dateigriff den Austausch; `FileRenameInfoEx` mit POSIX-Semantik erhält offene
Leser am vollständigen alten Stand. Wo ein Dateisystem diesen Aufruf ablehnt —
FAT32, exFAT, eine Netzfreigabe ohne diese SMB-Fähigkeit, Windows vor 1709 —
tauscht `_replace_snapshot` gewöhnlich aus; dort verlangt der Austausch eine
freie Zieldatei, und ein gleichzeitiger Leser ergibt einen wiederholbaren
Schreibfehler statt eines dauerhaft gesperrten Lagers. Jeder Schreibweg
verweigert das Überschreiben einer beschädigten oder neueren Datei. Ein
Lesefehler trägt `RETRY` als Handlung und nicht den Vorschlag einer
`ValidationError`: Zu korrigieren ist hier kein Feld in einem Dialog, sondern
eine Datei — der Satz nennt die Sicherung, und danach ist genau der
Wiederholungsknopf die Fortsetzung.

`book` nimmt einen ganzen Vorgang an. Seine Kennung macht Zustellungen
idempotent; ein gleicher Fingerabdruck mit neuer Vorgangskennung bedeutet
einen ausdrücklich wiederholten Druck. Jede Position bewahrt ihre Herkunft
und Druckfilamentidentität. G-Code ersetzt eine Schätzung mit dokumentierter
Differenz; `reverse_booking` nimmt sämtliche Positionen und Korrekturen zurück.
Der Bestand wird ab der letzten manuellen Feststellung gerechnet. Deren
`stock_revision` schützt jüngere Kenntnis vor alten Korrekturen und Rücknahmen.
Eine bestätigte Unterdeckung bleibt unbekannt, der volle Abzug im Journal.
Nach einem Bestandskonflikt kann eine ausdrücklich bestätigte Rücknahme
`preserve_newer_counts=True` setzen: jüngere Feststellungen bleiben erhalten,
übrige Spulen erhalten ihre Gutschrift. `preserved_counts` dokumentiert im
zurückgenommenen Vorgang, welche Bestände dabei unverändert geblieben sind.
Eine manuell eingetragene Menge oder Spulenaufteilung wird ausschließlich mit
`correct_manual_allocation=True` ausdrücklich ersetzt. Die Korrektur erhält
die Druckfilamentidentitäten und die vollständigen vorherigen Positionen;
automatische G-Code-Übernahmen dürfen diesen Schalter nicht setzen.

Eine manuelle Korrektur übergibt mit `expected_booking_updated_at` den
gelesenen Vorgangsstand. Eine inzwischen neuere Aufteilung wird abgewiesen;
die wiederholte Zustellung derselben unveränderten Positionen bleibt wirkungslos.
Zusätzliche G-Code-Werkzeuge dürfen Positionen ergänzen, ohne bestehende
Druckfilamentidentitäten zu entfernen. Auch frühere Positionen, Revisionen,
Zeitangaben und Rücknahmebelege werden beim Lesen vollständig geprüft.
Ein negativer Rest innerhalb der Maschinenrundung der verrechneten Werte
gilt als null; eine tatsächliche Unterdeckung bleibt unbekannt.

### Was ein Schreibvorgang kostet

Jeder Schreibweg liest die Datei unter der Sperre neu, prüft sie vollständig
und schreibt sie ganz — das ist die Zusage, und sie bleibt. Was daran wuchs,
war die Bestandsrechnung: `_remaining` ging für **jede** Spule durch **alle**
Buchungen, also einmal je Lesevorgang das Produkt aus beiden Zahlen.
`_booked_grams` ordnet die gebuchten Mengen stattdessen einmal nach Spule und
Bestandsstand zu; summiert wird weiter mit `math.fsum` über dieselben Werte,
und zwar erst beim Abruf — eine Summe im Voraus über einen Schlüssel, nach dem
niemand fragt, könnte mit einem `OverflowError` enden, den der alte Weg nie
gesehen hätte.

Gemessen am 14.09.2026 (Windows 11, SSD, Fremdlast aus vier Agenten; je Zelle
der Median aus drei Prozessen mit je drei `save`-Aufrufen), Spulen und
Buchungen wachsen gemeinsam:

| Spulen / Buchungen | Datei | `save` vorher | `save` nachher | Dekodieren vorher → nachher |
|---|---|---|---|---|
| 50 / 50 | 57 KB | 6,0 ms | 7,8 ms | 1,21 → 1,11 ms |
| 200 / 200 | 230 KB | 16,7 ms | 16,1 ms | 6,07 → 3,99 ms |
| 500 / 500 | 575 KB | 43,0 ms | 34,9 ms | 22,1 → 10,2 ms |
| 1000 / 1000 | 1,1 MB | **115,6 ms** | **70,5 ms** | 66,5 → 21,0 ms |

Die Bestandsrechnung allein fiel dabei von 47,1 auf 0,33 ms. An einem Lager
mit 500 Spulen und 2000 Buchungen (1,5 MB) waren es 47,7 von 117,8 ms. **Die
kleinen Zeilen sagen nichts**: Bei fünfzig Spulen liegt der Unterschied unter
der Streuung der Platte — `fsync` schwankte im selben Lauf zwischen 1,2 und
7,5 ms.

Was übrig bleibt, wächst linear mit der Datei: Lesen, `json`-Zerlegung, die
Prüfung je Spule und je Buchung, Serialisieren, `fsync`, Austausch. Ein
eigener Arbeiter dafür wäre keine Antwort und ist auch keine nötige:
`CatalogueWrites` (Spulenwähler) und `InventoryView._run` (Lagerfenster)
fahren jeden Schreibauftrag längst neben dem Hauptthread, mit
Wartezeiger ab 200 ms und Fortschritt ab zwei Sekunden (§2.8).
