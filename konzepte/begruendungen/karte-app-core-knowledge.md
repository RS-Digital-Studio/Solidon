# Begründungen zu `app/core/knowledge/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss
> und Stolperfallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen, das Warum und die Messwerte und Anlässe ihres Tages —
> wörtlich, gegliedert nach den Überschriften der Karte. *Früher unter …* nennt
> die Stelle der alten Karte.

## Die Karte

Die Tabelle der Daten steht jetzt einmal, in `data/CLAUDE.md`; die Angaben zu
`printers.toml` sind dorthin gewandert.

*Früher unter „Die Karte“.*

| Datei | Rolle |
|---|---|
| `profiles.py` | Drucker- und Materialprofile (§38). **Hier stehen die Toleranzen**, auf die `auto:<material>` verweist. Seit RM-071 trägt ein Drucker sein **Verfahren** (`technology`, `fdm` oder `resin`; ohne Angabe FDM, ohne Migration) und ein Material seines (`MaterialProfile.fits`); `default_material_for` und `material_for` halten beide zusammen — PLA gegen Harz, wenn das Verfahren wechselt, sonst nie. `project_profile` gibt das Paar eines Projekts samt mitgereistem Drucker, ohne es anzumelden (für die Migration). Ein Resin-Profil hat Düse, Bahn und Heiztemperaturen auf **null** und dafür `pixel_size` und `minimum_wall`; die Vorgaben dafür (`RESIN_*`) und die Vorlage `DEFAULT_RESIN_PRINTER` stehen oben im Modul |
| `standards.py` | Normteilmaße (§24.2) — M3, M4, Einpressbuchsen, Lager |
| `strength.py` | Blattfederrechnung für Schnapphaken und Klemmzungen; mechanische Kennwerte aus dem Materialprofil |
| `print_settings.py` | Löst Stufe + Material + Drucker zu Einstellungen auf (§29); das Tempo des Herstellers gilt für „Standard“, gedeckelt auf den Volumenstrom (`flow_speed_limit`, dieselbe Rechnung liest `slice/advise.py`). Dazu die Herkunft je Wert: `with_choice`, `with_accepted`, `without_choice`, `on_base` (Grundlage plus Abweichung), `own_part` (was dem Projekt gehört) und `legacy_choices` (Einordnung vor Format 36, gegen `resolve` von heute und `resolve(legacy=True)` wie bis 0.5.0). Eine gewählte Haftungsart bringt ihr Maß mit (`ADHESION_MEASURES`). Ohne Herstellerprofil ist `resolve` die Grundlage, sonst `export.manufacturer.base_settings` |
| `rules.py` | Die Regelsammlung für den Agenten (§39) |
| `calibration.py` | Selbstkalibrierung (§28.3) |
| `filaments.py` | Örtliches Filamentlager: Spulen mit beständiger Kennung, optionale Mengen und Angaben, Journal ganzer Druckvorgänge (§20) |
| `licences.py` | Lizenzprüfung der Abhängigkeiten (§36) |
| `tables.py` | Der eine TOML-Leser für Dateien, die auch von Hand geschrieben sein können — ein Syntaxfehler wird ein Satz mit Dateinamen (Regel 17); Profile, Druckeinstellungen und Kalibrierung rufen ihn mit ihrem Titel |
| `parts/` | Die Bausteinbibliothek — eigene `CLAUDE.md`, **eigene Lizenz** |
| `data/` | **Wo das Wissen wirklich steht**: sieben TOML-Dateien und die Lizenztexte (siehe unten) |

Eigene Drucker werden über `profiles.save_printer` in der Nutzerdatei
`printers.toml` gespeichert. Der Schreibweg prüft Name und positive, endliche
Maße, erhält andere Profile und ersetzt die Datei erst nach vollständigem
Schreiben. `user_printer_profiles` liefert die eigenen Einträge unabhängig vom
ausgewählten Slicer; `printer_profiles` verbindet sie mit dem Startbestand.

*Früher unter „Das Wissen steht in `data/`, nicht im Code“.*

| Datei | Inhalt |
|---|---|
| `printers.toml` | Druckerprofile — achtzehn FDM-Geräte und zwei Resin-Geräte nach Bauraum (`technology = "resin"`, Pixelgröße und Mindestwand statt Düse und Bahn); `travel_speed`, `speed_*`, die Beschleunigungen und `flow_factor` aus dem Standardprozess und dem allgemeinen PLA des Herstellers; `overhang_limit` aus dem Standardprozess im Slicer des Herstellers (Stützgrenze gegen die Senkrechte); `cura_definition` die Druckerdefinition in Cura, aus der die Konsolenübergabe Start- und Endcode nimmt; `first_layer_acceleration` und `overhang_speed_factors` (Überhangstufen in Prozent der Außenwand) aus demselben Standardprozess wie die Tempi, nur für Cura; `first_layer_line_factor` (erste Bahnbreite als Vielfaches der Düse) aus demselben Prozess, über `print_settings.resolve` für jeden Slicer |
| `materials.toml` | Materialprofile — hier stehen die Toleranzen; `resin` ist das Harz, mit `technology = "resin"` |
| `print_settings.toml` | Druckeinstellungen je Stufe |
| `standards.toml` | Normteilmaße |
| `rules.toml` | **Die Regelsammlung des Agenten** (§39) |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) |
| `third_party_licenses.toml` | Feste Quellen, Hashes und Zuordnung der Lizenztexte für Pakete, Laufzeitteile und Schriften (§36) |
| `third_party_licenses/` | Vollständige Lizenztexte und Anleitung zur Release-Lizenzakte in `README.md` |

`strength.py` verwendet E-Modul, Streckgrenze und `layer_bond_ratio` aus dem
Materialprofil. Die Lage bestimmt, ob der Schichtabschlag gilt; das Profil
bestimmt seine Größe. Ohne bekannte Druckrichtung gilt Querbelastung. Ein
fehlender mechanischer Kennwert ergibt keine erfundene Tragfähigkeitsangabe.

## Druckproben gelten für ihren Prozess

*Früher unter „Eine Regeländerung wird gemessen“.*

Kalibrierung schreibt TOML-Tabellen- und Feldkennungen als zitierte Literale.
Materialkennungen mit Leerraum, Punkten oder Anführungszeichen bleiben so
beim Aktualisieren eines anderen Profils unverändert lesbar.

*Früher unter „Druckproben gelten für ihren Prozess“.*

`calibration.apply(..., process=...)` speichert gemessene Mindestwand und
Überhanggrenze zusammen mit Druckerkennung, Düse, Schichthöhe und Linienbreite.
`profiles.for_process` übernimmt dafür das tatsächliche Druckraster aus den
Projekteinstellungen. `Profile` verwendet die Messwerte nur bei passendem
Prozess; andernfalls gelten zwei Linienbreiten und die Überhanggrenze des
Druckers (`PrinterProfile.overhang_limit`, aus dem Herstellerprofil), ohne
sie die Startregel. Derselbe Winkel geht als Stützgrenze in die Übergabe
(`print_settings.resolve`).
Ein Wechsel des Messprozesses nimmt keine Messung des anderen Felds mit.
Nicht ausgewählte Messfelder bleiben beim Speichern unverändert.

`analysis_limits` verbindet die Anforderungen der zugeordneten Materialien:
größte Mindestwand, kleinster Überhangwinkel. Unbekannte Materialarten
übernehmen keine Kalibrierung eines anderen Materials. Analyse und ihre
Zwischenspeicher müssen die wirksamen Grenzen berücksichtigen.

## Das Filamentlager ist örtlicher Bestand

*Früher unter „Das Filamentlager ist örtlicher Bestand“.*

`filaments.save` speichert eine Spule nach Kennung; eine leere Kennung legt
ein neues Exemplar an. Namen dürfen mehrfach vorkommen. Bearbeitungen behalten
die gelesene `revision`, damit ein offener Dialog keinen jüngeren Verbrauch
zurückschreibt; ein Konflikt trägt `RELOAD` als Handlung. Eine geänderte
`remaining_grams` ist eine Bestandsfeststellung (`stock_revision` springt) —
deshalb gibt der Spulendialog den gespeicherten Wert unverändert zurück,
solange niemand den Bestandsblock angefasst hat: Seine Anzeige rundet auf
eine Nachkommastelle, und die Rundung zählte sonst als Zählung und sperrte
jede Rücknahme. Archivieren erhält Kennung und Verlauf. Bearbeitet wird nur
nach Kennung: Zwei gleiche Etiketten sind zwei Spulen, und der alte Namensweg,
der dann raten musste, ist entfernt. `synchronise` (Übernahme aus dem
Slicer) erkennt eine schon übernommene Spule an **Profil und Farbe**, ohne
Profil an Name, Farbe und Materialart zugleich (`_same_slicer_spools`); alles
andere wird eine neue Spule mit unbekannter Menge, und eine Mehrdeutigkeit
hält die übrige Liste nicht auf. Eine Handspule gleichen Namens wird nie
umgefärbt (Regel 21). `valid_date` ist die eine Datumsprüfung für Kern und
Dialog. `reverse_booking` hat mit `restore_booking` ein Gegenstück: Der
Vorgang zählt wieder, das Journal bleibt vollständig, eine jüngere
Bestandsfeststellung sperrt beide gleich.

**Eine Spule trägt bis zu vier Farben** (`MAX_COLOURS`, Entscheidung Robert,
19.09.2026): `colour` bleibt die erste — für jeden Weg, der genau eine kennt —,
`extra_colours` die weiteren, `colours` alle in Spulenreihenfolge. Derselbe
Schnitt zieht sich durch: `MaterialSlot.extra_colours`, der Parameter `colour`
von *Filament zuweisen* mit Leerzeichen dazwischen, `filament_multi_colour`
in der Orca-Familie; PrusaSlicer, Cura, STL und die Ansicht bekommen die erste.

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
verweigert das Überschreiben einer beschädigten oder neueren Datei; eine
neuere trägt `too_new` und sagt es (die Datei ist nicht kaputt, nur jünger).
`_write` legt den Stand, den es ersetzt, als `filaments.json.bak` daneben
(`backup_path`) — den letzten lesbaren, denn die Transaktion hat ihn eben
gelesen. Ein Lesefehler bietet deshalb Handlungen, keinen Rat:
`RESTORE_BACKUP` (`restore_backup`: prüft die Sicherung, legt die
beschädigte Datei als `filaments.json.damaged-<Zeit>` beiseite, tauscht
atomar) steht nur, wenn die Sicherung da ist; `SET_ASIDE_FILE`
(`set_aside_unreadable`: benennt um, das Lager beginnt leer, ein heiler
Stand wird nie weggeräumt) immer; `RETRY` danach. Nicht den Vorschlag einer
`ValidationError`: Zu korrigieren ist hier kein Feld in einem Dialog.

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

*Früher unter „Was ein Schreibvorgang kostet“.*

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

**Das Serialisieren war der größte Posten, und der Leser danach der teuerste
im Hauptthread** (Durchsicht vor 0.5.0, 22.09.2026, 500 Spulen und 2000
Buchungen, 1,6 MB, Fremdlast aus sechzehn Prüfern — alt und neu abwechselnd
im selben Prozess, Median aus fünfzehn):

| Posten | vorher | nachher |
|---|---|---|
| `save` gesamt (im Arbeiter) | 176,9 ms | 130,5 ms |
| `catalogue()` danach (im Hauptthread) | 67,4 ms | 0,6 ms |

`_encoded` schreibt über `json.dumps` (C-Kodierer, seit Python 3.14 mit
Einrückung) statt über `json.dump` (Python-Kodierer in Zehntausenden
Stücken, 65,5 gegen 10,2 ms), und `_plain` ersetzt `asdict`, das jeden
Blattwert tief kopiert. Die Datei bleibt Byte für Byte dieselbe
(`test_the_file_keeps_its_bytes_when_the_writer_gets_faster`). Und was
`_write` geschrieben hat, ist danach die Momentaufnahme der Leser
(`_remember_written`, gestempelt nach dem Austausch unter der Sperre): Die
Oberfläche liest nach jedem Schreiben neu und zerlegte dafür die eben
geschriebene Datei ein zweites Mal. Ein fremder Austausch ändert den Stempel
und wird wie bisher gelesen. Die Zusage darüber bleibt: Der Schreibweg selbst
liest unter der Sperre neu und prüft vollständig.
